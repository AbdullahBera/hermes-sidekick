import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import net from "node:net";
import { once } from "node:events";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { chromium } from "../sidekick_control/node_modules/playwright/index.mjs";

const root = new URL("../", import.meta.url).pathname;
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
function ipc(socket, method, params = {}) {
  return new Promise((resolve, reject) => {
    const c = net.createConnection(socket);
    let b = "";
    c.setTimeout(35000, () => c.destroy(new Error("IPC timeout")));
    c.on("connect", () => c.write(JSON.stringify({ method, params }) + "\n"));
    c.on("data", (d) => {
      b += d;
      if (b.includes("\n")) {
        c.end();
        resolve(JSON.parse(b));
      }
    });
    c.on("error", reject);
  });
}
async function stop(child) {
  if (child && child.exitCode === null) {
    const exited = once(child, "exit");
    child.kill("SIGTERM");
    await exited;
  }
}
async function task(socket, id) {
  for (let i = 0; i < 200; i++) {
    const r = (await ipc(socket, "task", { id })).result;
    if (r.state === "succeeded") return r;
    if (["failed", "uncertain", "cancelled"].includes(r.state))
      throw new Error(JSON.stringify(r));
    await delay(50);
  }
  throw new Error("task timeout");
}

test("private owner review and human login handoff produce a usable session without agent credential access", async (t) => {
  const base = await mkdtemp(path.join(tmpdir(), "sk-owner-"));
  const state = path.join(base, "state"),
    sockets = path.join(base, "sock"),
    tokenFile = path.join(base, "owner", "access-token");
  const owner = path.join(sockets, "owner.sock"),
    agent = path.join(sockets, "agent.sock");
  let broker, web, uiBrowser;
  const fixture = createServer(async (req, res) => {
    if (req.url === "/session" && req.method === "POST") {
      let body = "";
      for await (const chunk of req) body += chunk;
      const values = new URLSearchParams(body);
      assert.equal(values.get("password"), "fictional-secret");
      res.writeHead(303, {
        "set-cookie": "fixture_session=fixture-session; HttpOnly; Path=/",
        location: "/private",
      });
      res.end();
      return;
    }
    res.writeHead(200, { "content-type": "text/html" });
    if (req.url === "/private") {
      res.end(
        req.headers.cookie?.includes("fixture_session=fixture-session")
          ? "<title>Signed in</title><h1>Fixture account is connected</h1>"
          : "<h1>Sign in required</h1>",
      );
      return;
    }
    res.end(
      '<title>Fixture sign in</title><form method="post" action="/session"><input name="name" aria-label="Name" style="position:absolute;left:20px;top:60px;width:250px;height:35px"><input name="password" aria-label="Password" type="password" style="position:absolute;left:20px;top:110px;width:250px;height:35px"><button style="position:absolute;left:20px;top:170px;width:250px;height:35px">Sign in</button></form>',
    );
  });
  fixture.listen(0, "127.0.0.1");
  await once(fixture, "listening");
  t.after(async () => {
    if (uiBrowser) await uiBrowser.close();
    await stop(web);
    await stop(broker);
    await new Promise((resolve) => fixture.close(resolve));
    await rm(base, { recursive: true, force: true });
  });
  const origin = `http://127.0.0.1:${fixture.address().port}`;
  broker = spawn(
    "python3",
    [
      "-m",
      "sidekick_control.service",
      "--dev",
      "--state",
      state,
      "--sockets",
      sockets,
    ],
    { cwd: root, stdio: ["ignore", "pipe", "pipe"] },
  );
  for (let i = 0; i < 100; i++) {
    try {
      if ((await ipc(owner, "status")).ok) break;
    } catch {}
    await delay(30);
  }
  web = spawn(
    "python3",
    [
      "-u",
      "-m",
      "sidekick_control.owner_web",
      "--socket",
      owner,
      "--token-file",
      tokenFile,
      "--port",
      "0",
    ],
    { cwd: root, stdio: ["ignore", "pipe", "pipe"] },
  );
  let output = "";
  web.stdout.on("data", (d) => (output += d));
  for (let i = 0; i < 100 && !output.includes("Owner controls:"); i++)
    await delay(30);
  const url = output.match(/http:\/\/127\.0\.0\.1:\d+/)?.[0];
  assert.ok(url, "owner server should start");
  const token = (await readFile(tokenFile, "utf8")).trim();
  assert.ok(!output.includes(token), "owner secret must not enter logs");
  const memory = await ipc(agent, "propose", {
    request_key: "fixture-memory",
    kind: "memory.save",
    title: "Remember a reply preference",
    action: {
      content:
        "Prefer short replies. <script>window.fixtureInjected=true</script>",
    },
  });
  uiBrowser = await chromium.launch({ headless: true, chromiumSandbox: true });
  const page = await uiBrowser.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(url + "/#" + token);
  await page
    .getByRole("button", { name: "Review action", exact: true })
    .click();
  assert.equal(
    await page.locator("#review script").count(),
    0,
    "reviewed content must remain text",
  );
  assert.equal(await page.evaluate(() => window.fixtureInjected), undefined);
  await page.getByRole("button", { name: "Approve this exact action" }).click();
  await page
    .getByText("Approved. It will run when execution is resumed.")
    .waitFor();
  assert.equal(
    (await ipc(agent, "task", { id: memory.result.id })).result.state,
    "approved",
  );
  await page.getByRole("button", { name: "Resume approved work" }).click();
  await task(agent, memory.result.id);
  await page.getByRole("button", { name: "Pause everything" }).click();
  await page
    .getByRole("button", { name: "Browser connection", exact: true })
    .click();
  await page.locator("#origins").fill(origin);
  await page.locator("#login-url").fill(origin + "/login");
  await page.getByRole("button", { name: "Open private sign-in" }).click();
  await page
    .getByText(
      "Private sign-in is ready. You are operating this browser directly.",
    )
    .waitFor();
  const session = (await ipc(owner, "login_status")).result;
  assert.ok(session.active);
  assert.equal(
    (await ipc(agent, "login_view", { session_id: session.session_id })).ok,
    false,
  );
  assert.equal(
    (await ipc(owner, "resume")).ok,
    false,
    "task execution must stay paused during login",
  );
  async function ready() {
    await page.waitForFunction(() => document.body.dataset.busy !== "true");
  }
  async function clickRemote(x, y) {
    await ready();
    const box = await page.locator("#login-screen").boundingBox();
    await page
      .locator("#login-screen")
      .click({
        position: { x: (x * box.width) / 1024, y: (y * box.height) / 720 },
      });
    await ready();
  }
  await clickRemote(100, 78);
  await page.locator("#login-text").fill("Fixture user");
  await page.getByRole("button", { name: "Enter text", exact: true }).click();
  await ready();
  await clickRemote(100, 128);
  await page.locator("#login-text").fill("fictional-secret");
  await page.getByRole("button", { name: "Enter text", exact: true }).click();
  await ready();
  await clickRemote(100, 186);
  await page.getByRole("button", { name: "Refresh view", exact: true }).click();
  await page
    .locator("#login-location")
    .filter({ hasText: "/private" })
    .waitFor();
  await page
    .getByRole("button", { name: "Use this signed-in session" })
    .click();
  await page
    .getByText("Session connected. Work remains paused until you resume it.")
    .waitFor();
  assert.equal((await ipc(owner, "status")).result.paused, true);
  assert.equal(
    (await ipc(owner, "login_view", { session_id: session.session_id })).ok,
    false,
    "old session cannot be reused",
  );
  const inspection = await ipc(agent, "propose", {
    request_key: "signed-in-read",
    kind: "browser.inspect",
    title: "Read connected account",
    action: { url: origin + "/private" },
  });
  await ipc(owner, "resume");
  const inspected = await task(agent, inspection.result.id);
  assert.match(inspected.result.text, /Fixture account is connected/);
  const visible = JSON.stringify([
    await ipc(agent, "status"),
    await ipc(agent, "tasks"),
    await ipc(agent, "events"),
  ]);
  assert.doesNotMatch(visible, /fictional-secret|fixture-session|screenshot/);
  const db = await readFile(path.join(state, "control.sqlite3"));
  assert.ok(
    !db.includes(Buffer.from("fictional-secret")),
    "login password must never be persisted in control state",
  );
  await ipc(owner, "pause");
  await ipc(owner, "disconnect_browser");
  assert.equal(
    (
      await ipc(agent, "propose", {
        request_key: "after-disconnect",
        kind: "browser.inspect",
        title: "Read",
        action: { url: origin },
      })
    ).ok,
    false,
  );
  assert.deepEqual(errors, []);
});
