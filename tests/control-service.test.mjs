import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import net from 'node:net';
import { once } from 'node:events';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import test from 'node:test';

const root = new URL('../', import.meta.url).pathname;
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
function request(socket, method, params={}) {
  return new Promise((resolve,reject) => {
    const client=net.createConnection(socket);
    let buffer='';
    client.setTimeout(5000,()=>client.destroy(new Error('socket timed out')));
    client.on('connect',()=>client.write(JSON.stringify({method,params})+'\n'));
    client.on('data',chunk=> { buffer+=chunk; if(buffer.includes('\n')) { client.end(); resolve(JSON.parse(buffer)); } });
    client.on('error',reject);
  });
}
async function start(state,sockets) {
  const child=spawn('python3',['-m','sidekick_control.service','--dev','--state',state,'--sockets',sockets],{cwd:root,stdio:['ignore','pipe','pipe']});
  let errors='';child.stderr.on('data',chunk=>errors+=chunk);
  for(let i=0;i<100;i++) {
    if(child.exitCode!==null) throw new Error(`service failed: ${errors}`);
    try { if((await request(path.join(sockets,'owner.sock'),'status')).ok) return child; } catch {}
    await delay(30);
  }
  child.kill('SIGKILL');throw new Error(`service start timed out: ${errors}`);
}
async function stop(child) {
  if(child.exitCode===null) { const exited=once(child,'exit'); child.kill('SIGTERM'); await exited; }
}
async function untilTask(socket,id,state) {
  for(let i=0;i<400;i++) {
    const response=await request(socket,'task',{id});
    if(response.result?.state===state) return response.result;
    if(['failed','uncertain','cancelled','expired'].includes(response.result?.state)) throw new Error(JSON.stringify(response));
    await delay(50);
  }
  throw new Error('task did not complete within test budget');
}

test('owner-approved appointment persists across service restart and never repeats on request replay',async t=> {
  const base=await mkdtemp(path.join(tmpdir(),'sk-'));
  const state=path.join(base,'state'),sockets=path.join(base,'sock');
  let posts=0, holdResponse=false;
  const web=createServer((req,res)=> {
    res.writeHead(200,{'content-type':'text/html'});
    if(req.method==='POST') { posts++;if(!holdResponse) res.end('<h1>Confirmed fixture appointment</h1>'); }
    else res.end('<title>Appointments</title><h1>10am is available</h1><form method="post" action="/book"><input name="name" required><button type="submit">Book 10am</button></form>');
  });
  web.listen(0,'127.0.0.1');await once(web,'listening');
  const origin=`http://127.0.0.1:${web.address().port}`;
  let child=await start(state,sockets);
  t.after(async()=> { await stop(child);await new Promise(resolve=>web.close(resolve));await rm(base,{recursive:true,force:true}); });
  const owner=path.join(sockets,'owner.sock'),agent=path.join(sockets,'agent.sock');
  assert.equal((await request(owner,'connect_browser',{origins:[origin]})).ok,true);
  const proposed=await request(agent,'propose',{request_key:'fixture-inspect',kind:'browser.inspect',title:'Find appointment',action:{url:origin}});
  assert.equal(proposed.ok,true,JSON.stringify(proposed));
  assert.equal((await request(agent,'resume')).ok,false);
  await request(owner,'resume');
  const inspected=await untilTask(agent,proposed.result.id,'succeeded');
  const parameters={request_key:'fixture-booking',kind:'browser.submit',title:'Book the 10am appointment',action:{inspection_id:inspected.id,form_index:0,fields:{name:'Fixture person'},submit_index:0}};
  const prepared=await request(agent,'propose',parameters);
  assert.equal(prepared.ok,true,JSON.stringify(prepared));
  assert.equal(prepared.result.state,'awaiting_approval');
  assert.equal(posts,0);
  await stop(child);child=await start(state,sockets);
  assert.equal((await request(agent,'task',{id:prepared.result.id})).result.state,'awaiting_approval');
  assert.equal((await request(agent,'approve',{id:prepared.result.id,digest:prepared.result.digest})).ok,false);
  assert.equal((await request(owner,'approve',{id:prepared.result.id,digest:'wrong'})).ok,false);
  assert.equal(posts,0);
  assert.equal((await request(owner,'approve',{id:prepared.result.id,digest:prepared.result.digest})).ok,true);
  const finished=await untilTask(agent,prepared.result.id,'succeeded');
  assert.match(finished.result.text,/Confirmed fixture appointment/);
  assert.equal(posts,1);
  for(const key of ['fixture-booking','model-retried-with-new-key']) {
    const repeated=await request(agent,'propose',{...parameters,request_key:key});
    assert.equal(repeated.result.id,finished.id);
  }
  await delay(500);assert.equal(posts,1);
  await request(owner,'pause');
  assert.equal((await request(owner,'status')).result.paused,true);
  // The server received the request, but no result reached the worker. Pause must
  // terminate the browser and preserve uncertainty across a restart/resume.
  holdResponse=true;
  const interruptedParams={...parameters,request_key:'interrupted-booking',action:{...parameters.action,fields:{name:'Second fixture person'}}};
  const interruptible=await request(agent,'propose',interruptedParams);
  assert.equal(interruptible.ok,true);
  await request(owner,'approve',{id:interruptible.result.id,digest:interruptible.result.digest});
  await request(owner,'resume');
  for(let i=0;i<200 && posts<2;i++) await delay(50);
  assert.equal(posts,2);
  await request(owner,'pause');
  assert.equal((await request(agent,'task',{id:interruptible.result.id})).result.state,'uncertain');
  await stop(child);child=await start(state,sockets);
  assert.equal((await request(owner,'status')).result.paused,true);
  await request(owner,'resume');
  const replay=await request(agent,'propose',{...interruptedParams,request_key:'repeat-after-interruption'});
  assert.equal(replay.result.id,interruptible.result.id);
  assert.equal(replay.result.state,'uncertain');
  await delay(500);assert.equal(posts,2,'pause/restart/resume must not repeat a received submission');
  await request(owner,'pause');
});
