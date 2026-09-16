import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { once } from 'node:events';
import test from 'node:test';

const adapter = new URL('../sidekick_control/browser.mjs', import.meta.url);
function run(kind, action, origin, allowLoopback = true) {
  return new Promise((resolve, reject) => {
    const process = spawn('node', [adapter.pathname], { stdio:['pipe','pipe','pipe'] });
    let output='', errors='';
    process.stdout.on('data', d => output += d);
    process.stderr.on('data', d => errors += d);
    process.on('error', reject);
    process.on('close', code => {
      if (code) return reject(new Error(`adapter failed: ${code}; ${errors.slice(0,500)}`));
      try { resolve(JSON.parse(output)); } catch (error) { reject(error); }
    });
    process.stdin.end(JSON.stringify({kind, action, origins:[origin], allowLoopback}));
  });
}

test('appointment inspection, exact approval payload, one submission, stale page rejection', async t => {
  let submissions = 0, label = 'Appointment at 10am';
  const received=[];
  const server = createServer(async (req,res) => {
    if (req.method === 'POST') {
      submissions++;
      let body=''; for await (const chunk of req) body+=chunk;
      received.push(new URLSearchParams(body));
      assert.match(req.headers.cookie || '', /fixture_session=example/);
      res.writeHead(200, {'content-type':'text/html'});
      res.end('<h1>Appointment confirmed</h1>');
      return;
    }
    res.writeHead(200, {'content-type':'text/html', 'set-cookie':'fixture_session=example; HttpOnly; Path=/'});
    res.end(`<html><head><title>Appointments</title></head><body><h1>${label}</h1>
      <form method="post" action="/book"><input name="name" required><select name="slot"><option value="10">10am</option></select><button type="submit">Confirm appointment</button></form>
      <script>fetch('/unexpected', {method:'POST'})</script></body></html>`);
  });
  server.listen(0,'127.0.0.1');
  await once(server,'listening');
  t.after(() => new Promise(resolve => server.close(resolve)));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const inspection = await run('browser.inspect', {url:origin}, origin);
  assert.equal(inspection.outcome,'succeeded',JSON.stringify(inspection));
  assert.equal(submissions,0,'inspection must not run page scripts or submit');
  assert.ok(inspection.elapsed_ms < 15000, `inspection took ${inspection.elapsed_ms}ms`);
  const form=inspection.result.forms[0];
  const action={url:origin, target:form.action, form_index:0, form_fingerprint:form.fingerprint,
    fields:{name:'Fixture person',slot:'10'}, submit_index:0};
  const result=await run('browser.submit', action, origin);
  assert.equal(result.outcome,'succeeded',JSON.stringify(result));
  assert.equal(submissions,1);
  assert.equal(received[0].get('name'),'Fixture person');
  assert.equal(received[0].get('slot'),'10');
  label='Appointment at 11am';
  const stale=await run('browser.submit',action,origin);
  assert.equal(stale.outcome,'failed');
  assert.equal(stale.error,'form_changed');
  assert.equal(submissions,1,'a changed offer must not be submitted');
  console.log(JSON.stringify({inspection_ms:inspection.elapsed_ms,submission_ms:result.elapsed_ms}));
});

test('private addresses are rejected outside fixture mode', async () => {
  const result=await run('browser.inspect',{url:'https://127.0.0.1'},'https://127.0.0.1',false);
  assert.equal(result.outcome,'failed');
  assert.equal(result.error,'private_address_blocked');
});

test('POST redirect returns the confirmation; a lost response never triggers a second POST', async t => {
  let posts=0, loseResponse=false;
  const server=createServer((req,res)=> {
    if(req.method==='POST') {
      posts++;
      if(loseResponse) { req.socket.destroy(); return; }
      res.writeHead(303,{location:'/confirmation'});res.end();return;
    }
    res.writeHead(200,{'content-type':'text/html'});
    res.end(req.url==='/confirmation' ? '<h1>Confirmed redirected appointment</h1>' :
      '<title>Appointments</title><form method="post" action="/book"><input name="name"><button>Book</button></form>');
  });
  server.listen(0,'127.0.0.1');await once(server,'listening');
  t.after(()=>new Promise(resolve=>server.close(resolve)));
  const origin=`http://127.0.0.1:${server.address().port}`;
  const inspection=await run('browser.inspect',{url:origin},origin);
  assert.equal(inspection.outcome,'succeeded');
  const form=inspection.result.forms[0];
  const action={url:origin,target:form.action,form_index:0,form_fingerprint:form.fingerprint,fields:{name:'Fixture'},submit_index:0};
  const redirected=await run('browser.submit',action,origin);
  assert.equal(redirected.outcome,'succeeded',JSON.stringify(redirected));
  assert.match(redirected.result.text,/Confirmed redirected appointment/);
  assert.equal(posts,1);
  loseResponse=true;
  const lost=await run('browser.submit',action,origin);
  assert.equal(lost.outcome,'uncertain',JSON.stringify(lost));
  assert.equal(posts,2,'even a dropped response must consume the one-POST allowance');
});

test('long pages cannot hide unreviewed terms outside the approval preview', async t => {
  let posts=0;
  const server=createServer((req,res)=> {
    if(req.method==='POST') posts++;
    res.writeHead(200,{'content-type':'text/html'});
    res.end(`<p>${'x'.repeat(8100)}</p><form method="post" action="/book"><input name="name"><button>Book</button></form>`);
  });
  server.listen(0,'127.0.0.1');await once(server,'listening');
  t.after(()=>new Promise(resolve=>server.close(resolve)));
  const origin=`http://127.0.0.1:${server.address().port}`;
  const inspection=await run('browser.inspect',{url:origin},origin);
  assert.equal(inspection.result.text_truncated,true);
  const form=inspection.result.forms[0];
  const result=await run('browser.submit',{url:origin,target:form.action,form_index:0,form_fingerprint:form.fingerprint,fields:{name:'Fixture'},submit_index:0},origin);
  assert.equal(result.error,'review_too_large');
  assert.equal(posts,0);
});

test('inspection withholds hidden and password values and refuses login submission', async t => {
  let posts=0;
  const server=createServer((req,res)=> {
    if(req.method==='POST') posts++;
    res.writeHead(200,{'content-type':'text/html'});
    res.end('<form method="post" action="/login"><input type="hidden" name="csrf" value="fictional-hidden-value"><input type="password" name="password" value="fictional-password-value"><button>Login</button></form>');
  });
  server.listen(0,'127.0.0.1');await once(server,'listening');
  t.after(()=>new Promise(resolve=>server.close(resolve)));
  const origin=`http://127.0.0.1:${server.address().port}`;
  const inspection=await run('browser.inspect',{url:origin},origin);
  assert.equal(inspection.outcome,'succeeded');
  assert.doesNotMatch(JSON.stringify(inspection),/fictional-hidden-value|fictional-password-value/);
  const form=inspection.result.forms[0];
  const result=await run('browser.submit',{url:origin,target:form.action,form_index:0,form_fingerprint:form.fingerprint,fields:{},submit_index:0},origin);
  assert.equal(result.error,'sensitive_form_needs_human');
  assert.equal(posts,0);
});
