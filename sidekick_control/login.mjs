// Human-only browser: fixed input operations over private owner IPC, never agent tools.
import { chromium } from "playwright";
import { createInterface } from "node:readline";
import { networkPolicy } from "./network.mjs";

let browser,
  context,
  page,
  policy,
  taskOrigins,
  blocked = false;
const blockedOrigins = new Set();
const viewport = { width: 1024, height: 720 };
const keys = new Set([
  "Tab",
  "Shift+Tab",
  "Enter",
  "Backspace",
  "Escape",
  "ArrowUp",
  "ArrowDown",
  "ArrowLeft",
  "ArrowRight",
  "Control+A",
  "Meta+A",
]);
async function view() {
  if (page?.isClosed())
    page = context
      .pages()
      .filter((p) => !p.isClosed())
      .at(-1);
  if (!page || page.isClosed()) throw new Error("login_window_closed");
  return {
    url: page.url(),
    title: await page.title(),
    width: viewport.width,
    height: viewport.height,
    blocked,
    blocked_origins: [...blockedOrigins],
    screenshot: (
      await page.screenshot({ type: "jpeg", quality: 65, timeout: 5000 })
    ).toString("base64"),
  };
}
async function dispatch(command) {
  if (command.op === "start") {
    if (browser) throw new Error("login_already_started");
    taskOrigins = command.origins;
    policy = await networkPolicy(
      [...new Set([...taskOrigins, ...command.login_origins])],
      command.allowLoopback,
    );
    if (!policy.allowed(command.url)) throw new Error("origin_not_allowed");
    browser = await chromium.launch({
      headless: true,
      chromiumSandbox: true,
      args: [
        "--no-proxy-server",
        "--disable-dev-shm-usage",
        "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
        `--host-resolver-rules=${policy.mappings.join(",")}`,
      ],
    });
    context = await browser.newContext({
      viewport,
      serviceWorkers: "block",
      acceptDownloads: false,
    });
    await context.route("**/*", (route) => {
      if (!policy.allowed(route.request().url())) {
        blocked = true;
        try {
          if (blockedOrigins.size < 10)
            blockedOrigins.add(new URL(route.request().url()).origin);
        } catch {}
        return route.abort();
      }
      return route.continue();
    });
    await context.routeWebSocket("**/*", (socket) => socket.close());
    context.on("page", (next) => {
      page = next;
      next.setDefaultTimeout(5000);
      next.on("dialog", (d) => d.dismiss());
      next.on("close", () => {
        if (page === next)
          page = context
            .pages()
            .filter((p) => !p.isClosed())
            .at(-1);
      });
    });
    page = await context.newPage();
    await page.goto(command.url, {
      waitUntil: "domcontentloaded",
      timeout: 15000,
    });
    return view();
  }
  if (!browser) throw new Error("no_login_session");
  if (command.op === "view") return view();
  if (command.op === "input") {
    const event = command.event;
    if (
      event.type === "click" &&
      Number.isFinite(event.x) &&
      Number.isFinite(event.y) &&
      event.x >= 0 &&
      event.x < viewport.width &&
      event.y >= 0 &&
      event.y < viewport.height
    )
      await page.mouse.click(event.x, event.y);
    else if (
      event.type === "type" &&
      typeof event.text === "string" &&
      event.text.length <= 2000
    )
      await page.keyboard.insertText(event.text);
    else if (event.type === "key" && keys.has(event.key))
      await page.keyboard.press(event.key);
    else if (
      event.type === "scroll" &&
      Number.isFinite(event.y) &&
      Math.abs(event.y) <= 720
    )
      await page.mouse.wheel(0, event.y);
    else throw new Error("unsupported_login_input");
    return view();
  }
  if (command.op === "finish") {
    // Identity-provider credentials stay out of the agent's browser session.
    const state = await context.storageState();
    const hosts = taskOrigins.map((o) => new URL(o).hostname);
    state.cookies = state.cookies.filter((c) =>
      hosts.some(
        (h) =>
          h === c.domain.replace(/^\./, "") ||
          h.endsWith("." + c.domain.replace(/^\./, "")),
      ),
    );
    state.origins = state.origins.filter((o) => taskOrigins.includes(o.origin));
    return { storage: state };
  }
  throw new Error("unsupported_login_operation");
}
try {
  for await (const line of createInterface({
    input: process.stdin,
    crlfDelay: Infinity,
  })) {
    try {
      if (line.length > 100000) throw new Error("input_too_large");
      const result = await dispatch(JSON.parse(line));
      process.stdout.write(JSON.stringify({ ok: true, result }) + "\n");
    } catch {
      // Login inputs and browser errors may contain credentials. Never log them.
      process.stdout.write(
        JSON.stringify({
          ok: false,
          error:
            "Login browser operation failed; refresh or cancel the handoff.",
        }) + "\n",
      );
    }
  }
} finally {
  if (browser) await browser.close();
}
