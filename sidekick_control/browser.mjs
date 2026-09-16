// One bounded browser task per process. No model-supplied JavaScript or shell commands.
import { chromium } from 'playwright';
import { createHash } from 'node:crypto';
import { lookup } from 'node:dns/promises';
import { isIP } from 'node:net';
import { request as httpRequest } from 'node:http';
import { request as httpsRequest } from 'node:https';

// Chromium can resend a POST below Playwright's interception layer after a lost
// connection. Dispatch the one approved request ourselves: no connection pooling,
// redirect following or retry logic. Reuse the browser's exact encoded body/cookies.
async function submitOnce(request, address) {
  const url = new URL(request.url());
  const headers = await request.allHeaders();
  delete headers['accept-encoding'];
  delete headers['connection'];
  delete headers['transfer-encoding'];
  const body = request.postDataBuffer() || Buffer.alloc(0);
  headers['content-length'] = String(body.length);
  return new Promise((resolve, reject) => {
    const send = url.protocol === 'https:' ? httpsRequest : httpRequest;
    const outgoing = send(url, {method:'POST', headers, agent:false, family:4,
      autoSelectFamily:false, lookup:(_hostname, _options, done) => done(null, address, 4),
    }, response => {
      const chunks=[]; let size=0;
      response.on('data', chunk => {
        size += chunk.length;
        if(size > 1_000_000) outgoing.destroy(new Error('response_limit'));
        else chunks.push(chunk);
      });
      response.on('error', reject);
      response.on('end', () => {
        const received={};
        for(const [name,value] of Object.entries(response.headers)) {
          if(!['connection','transfer-encoding','content-length'].includes(name) && value !== undefined)
            received[name] = Array.isArray(value) ? value.join('\n') : value;
        }
        resolve({status:response.statusCode, headers:received, body:Buffer.concat(chunks)});
      });
    });
    const deadline=setTimeout(() => outgoing.destroy(new Error('submission_timeout')), 15000);
    outgoing.on('close', () => clearTimeout(deadline));
    outgoing.on('error', reject);
    outgoing.end(body);
  });
}

function stable(value) {
  if (Array.isArray(value)) return '[' + value.map(stable).join(',') + ']';
  if (value && typeof value === 'object') return '{' + Object.keys(value).sort().map(k => JSON.stringify(k) + ':' + stable(value[k])).join(',') + '}';
  return JSON.stringify(value);
}
const hash = value => createHash('sha256').update(stable(value)).digest('hex');
function publicIPv4(address) {
  if (isIP(address) !== 4) return false;
  const [a,b] = address.split('.').map(Number);
  return !(a === 0 || a === 10 || a === 127 || a >= 224 || (a === 169 && b === 254) ||
    (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168) ||
    (a === 100 && b >= 64 && b <= 127) || (a === 198 && (b === 18 || b === 19)) ||
    (a === 192 && (b === 0 || b === 2)) || (a === 198 && b === 51) || (a === 203 && b === 0));
}

let input = '';
for await (const chunk of process.stdin) {
  input += chunk;
  if (input.length > 2_000_000) throw new Error('input limit exceeded');
}
const request = JSON.parse(input);
let browser;
let sent = false;
let networkBlocked = false;
const started = performance.now();
try {
  const origins = new Set(request.origins);
  const mappings = [];
  const pinned = new Map();
  for (const origin of origins) {
    const url = new URL(origin);
    const records = await lookup(url.hostname, { all: true, family: 4 });
    if (!records.length || records.some(r => !publicIPv4(r.address) && !(request.allowLoopback && url.hostname === '127.0.0.1' && r.address === '127.0.0.1'))) {
      throw new Error('private_address_blocked');
    }
    mappings.push(`MAP ${url.hostname} ${records[0].address}`);
    pinned.set(url.hostname, records[0].address);
  }
  const allowed = raw => {
    try { const u = new URL(raw); return origins.has(u.origin) && !u.username && !u.password; }
    catch { return false; }
  };
  if (!allowed(request.action.url)) throw new Error('origin_not_allowed');
  browser = await chromium.launch({ headless: true, chromiumSandbox: true,
    args: ['--disable-dev-shm-usage', '--no-proxy-server', `--host-resolver-rules=${mappings.join(',')}`],
  });
  const context = await browser.newContext({ javaScriptEnabled: false, serviceWorkers: 'block',
    acceptDownloads: false, storageState: request.storage || undefined,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(5000);
  page.setDefaultNavigationTimeout(15000);
  let submitTarget = null;
  await context.route('**/*', async route => {
    const r = route.request();
    if (!allowed(r.url()) || ['image','media','font','script'].includes(r.resourceType())) {
      if (r.isNavigationRequest()) networkBlocked = true;
      return route.abort();
    }
    if (r.method() !== 'GET' && r.method() !== 'HEAD') {
      if (submitTarget && r.method() === 'POST' && r.url() === submitTarget && !sent && r.isNavigationRequest() && r.frame() === page.mainFrame()) {
        sent = true;  // consume before dispatch; never permit a repeated submission
        try {
          return await route.fulfill(await submitOnce(r, pinned.get(new URL(r.url()).hostname)));
        } catch {
          networkBlocked = true;
          return route.abort().catch(() => {});
        }
      }
      networkBlocked = true;
      return route.abort();
    }
    return route.continue();
  });
  await page.goto(request.action.url, { waitUntil: 'domcontentloaded' });
  if (networkBlocked || !allowed(page.url())) throw new Error('navigation_blocked');
  const snapshot = async () => page.evaluate(() => ({
    url: location.href,
    title: document.title,
    text: document.body?.innerText.slice(0, 8000) || '',
    text_truncated: (document.body?.innerText.length || 0) > 8000,
    links: Array.from(document.querySelectorAll('a[href]')).slice(0, 60).map(a => ({ text: a.innerText.slice(0, 100), url: a.href })),
    forms: Array.from(document.forms).slice(0, 15).map((form, index) => ({
      index, action: form.action, method: form.method.toUpperCase(), target: form.target, enctype: form.enctype,
      fields: Array.from(form.elements).filter(e => e.name && !e.disabled && !['submit','button','reset'].includes(e.type)).map(e => ({
        name: e.name, type: e.type, value: e.value, required: e.required || false, readOnly: e.readOnly || false,
        checked: Boolean(e.checked), options: e.options ? Array.from(e.options).map(o => ({value: o.value, text: o.text})) : undefined,
      })),
      buttons: Array.from(form.elements).filter(e => !e.disabled && e.type === 'submit').map(e => ({name: e.name, value: e.value, label: (e.innerText || e.value || 'Submit').slice(0, 150), action: e.hasAttribute('formaction') ? e.formAction : form.action, method: (e.hasAttribute('formmethod') ? e.formMethod : form.method).toUpperCase(), target: e.hasAttribute('formtarget') ? e.formTarget : form.target})),
    })),
  }));
  const data = await snapshot();
  for (const form of data.forms) {
    // Include hidden values in the fingerprint, but don't expose them as tool output.
    form.fingerprint = hash({url: data.url, title: data.title, text: data.text, form});
    form.fields = form.fields.map(f => ['hidden','password','file'].includes(f.type) ? { ...f, value: '[hidden]' } : f);
  }
  if (request.kind === 'browser.inspect') {
    process.stdout.write(JSON.stringify({ outcome: 'succeeded', result: data, elapsed_ms: Math.round(performance.now() - started) }));
  } else if (request.kind === 'browser.submit') {
    const action = request.action;
    const form = data.forms[action.form_index];
    if (data.text_truncated) throw new Error('review_too_large');
    if (!form || form.fingerprint !== action.form_fingerprint || form.action !== action.target || form.method !== 'POST') throw new Error('form_changed');
    const names = form.fields.map(f => f.name);
    if (new Set(names).size !== names.length) throw new Error('duplicate_fields_need_human');
    if (form.fields.some(f => f.type === 'password' || f.type === 'file')) throw new Error('sensitive_form_needs_human');
    if (!allowed(form.action)) throw new Error('submission_origin_blocked');
    const formLocator = page.locator('form').nth(action.form_index);
    for (const [name, value] of Object.entries(action.fields)) {
      const field = form.fields.find(f => f.name === name);
      if (!field || field.readOnly || !['text','email','tel','url','search','date','time','datetime-local','number','textarea','select-one'].includes(field.type)) throw new Error('unsupported_field');
      // Attribute equality is selected through a fixed DOM predicate; names aren't CSS/JS code.
      const handles = await formLocator.locator('[name]').elementHandles();
      let target;
      for (const handle of handles) { if (await handle.getAttribute('name') === name) { target = handle; break; } }
      if (!target) throw new Error('field_missing');
      if (field.type === 'select-one') await target.selectOption(value); else await target.fill(value);
    }
    if (!(await formLocator.evaluate(form => form.checkValidity()))) throw new Error('form_invalid');
    const button = form.buttons[action.submit_index];
    if (!button || button.action !== form.action || button.method !== 'POST' || !['','_self'].includes(button.target)) throw new Error('submit_button_changed');
    // Exact reviewed fields + the unchanged DOM determine the only permitted POST.
    submitTarget = action.target;
    const responsePromise = page.waitForResponse(r => r.request().method() === 'POST' && r.url() === submitTarget, {timeout: 15000}).catch(() => null);
    const navigationPromise = page.waitForNavigation({waitUntil: 'domcontentloaded', timeout: 15000}).catch(() => null);
    await formLocator.evaluate((form, index) => {
      const buttons = Array.from(form.elements).filter(e => !e.disabled && e.type === 'submit');
      form.requestSubmit(buttons[index]);
    }, action.submit_index);
    const response = await responsePromise;
    const navigation = await navigationPromise;
    if (!sent || networkBlocked || !response || response.status() >= 400 || !navigation?.ok()) throw new Error('submission_outcome_uncertain');
    process.stdout.write(JSON.stringify({ outcome: 'succeeded', result: {
      url: page.url(), status: response.status(), text: (await page.locator('body').innerText()).slice(0, 8000),
      note: 'The approved form was submitted and a response received. Verify the site confirmation; a response alone does not prove a booking.',
    }, elapsed_ms: Math.round(performance.now() - started) }));
  } else throw new Error('unsupported_action');
} catch (error) {
  // Raw browser exceptions can contain form values, cookies or URLs; return only bounded codes.
  const known = new Set(['private_address_blocked','origin_not_allowed','navigation_blocked','form_changed','review_too_large','duplicate_fields_need_human','sensitive_form_needs_human','submission_origin_blocked','unsupported_field','field_missing','form_invalid','submit_button_changed','submission_outcome_uncertain']);
  process.stdout.write(JSON.stringify({ outcome: sent ? 'uncertain' : 'failed',
    error: known.has(error.message) ? error.message : 'browser_failed_before_submission',
    elapsed_ms: Math.round(performance.now() - started),
  }));
} finally {
  if (browser) await browser.close();
}
