"use strict";
const $ = (id) => document.getElementById(id);
let token = location.hash.slice(1),
  loginId = null,
  screenSize = { width: 1024, height: 720 },
  busy = false;
if (token) history.replaceState(null, "", location.pathname);
const feedback = (message, error = false) => {
  $("feedback").textContent = message;
  $("feedback").className = error ? "error" : "success";
};
const element = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
};
function button(label, handler, kind = "") {
  const node = element("button", label, kind);
  node.addEventListener("click", () => perform(handler));
  return node;
}
async function api(method, params = {}) {
  const response = await fetch("/api", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer " + token,
    },
    body: JSON.stringify({ method, params }),
    cache: "no-store",
  });
  const data = await response.json();
  if (!response.ok || data.error)
    throw new Error(data.error || "The request could not finish.");
  return data.result;
}
async function perform(operation) {
  if (busy) return;
  busy = true;
  document.body.dataset.busy = "true";
  try {
    await operation();
  } catch (error) {
    feedback(error.message, true);
  } finally {
    busy = false;
    document.body.dataset.busy = "false";
  }
}
function panel(name) {
  for (const key of ["tasks", "browser", "memory"])
    $(key + "-panel").hidden = key !== name;
  document
    .querySelectorAll("[data-panel]")
    .forEach((b) => b.classList.toggle("active", b.dataset.panel === name));
}
function showLogin(view) {
  loginId = view.session_id;
  screenSize = { width: view.width, height: view.height };
  $("handoff").hidden = false;
  $("login-location").textContent = view.url;
  $("login-screen").src = "data:image/jpeg;base64," + view.screenshot;
  $("login-blocked").hidden = !view.blocked;
  $("login-blocked").textContent =
    "Blocked origins: " +
    (view.blocked_origins || []).join(", ") +
    ". Cancel and add an origin only if it is required for sign-in and you trust it.";
}
function clearLogin() {
  loginId = null;
  $("handoff").hidden = true;
  $("login-screen").removeAttribute("src");
  $("login-text").value = "";
}
async function refresh() {
  const [status, tasks, memories, login] = await Promise.all([
    api("status"),
    api("tasks"),
    api("memories"),
    api("login_status"),
  ]);
  $("unlock").hidden = true;
  $("workspace").hidden = false;
  $("pause").disabled = false;
  $("run-state").textContent = status.paused ? "Paused" : "Running";
  $("run-state").className = "pill" + (status.paused ? " paused" : "");
  $("resume").disabled = !status.paused || login.active;
  $("pending-count").textContent =
    tasks.filter((t) => t.state === "awaiting_approval").length || "";
  $("task-list").replaceChildren();
  if (!tasks.length)
    $("task-list").append(
      element(
        "p",
        "No tasks yet. Prepared actions will appear here for review.",
        "muted",
      ),
    );
  for (const task of tasks) {
    const row = element("div", undefined, "task-row"),
      copy = element("div");
    copy.append(
      element("h3", task.title),
      element("p", task.state.replaceAll("_", " "), "state"),
    );
    row.append(
      copy,
      button(
        task.state === "awaiting_approval" ? "Review action" : "View details",
        () => review(task.id),
      ),
    );
    $("task-list").append(row);
  }
  $("memory-list").replaceChildren();
  if (!memories.length)
    $("memory-list").append(element("p", "No approved memories yet.", "muted"));
  for (const memory of memories) {
    const card = element("article", undefined, "card");
    card.append(
      element("p", memory.content),
      button(
        "Forget this memory",
        async () => {
          await api("forget", { id: memory.id });
          await refresh();
          feedback(
            "Memory forgotten here. Older chats and backups are separate.",
          );
        },
        "danger",
      ),
    );
    $("memory-list").append(card);
  }
  const browser = status.connectors.find((c) => c.name === "browser");
  $("connection-state").textContent = browser?.enabled
    ? "Connected · " + JSON.parse(browser.hosts).join(", ")
    : "Browser disconnected";
  if (login.active) {
    loginId = login.session_id;
    showLogin(await api("login_view", { session_id: loginId }));
  } else clearLogin();
  if (status.worker_failed)
    feedback(
      "The execution worker needs attention. Work is not being completed.",
      true,
    );
}
function detail(list, label, value) {
  list.append(element("dt", label), element("dd", String(value)));
}
async function review(id) {
  const task = await api("task", { id }),
    box = $("review");
  box.replaceChildren();
  box.hidden = false;
  box.append(
    element("p", task.state.replaceAll("_", " ").toUpperCase(), "eyebrow"),
    element("h2", task.title),
  );
  const facts = element("dl");
  detail(facts, "Action", task.kind);
  detail(facts, "Status", task.message);
  detail(facts, "Expires", new Date(task.expires * 1000).toLocaleString());
  if (task.action.target) detail(facts, "Destination", task.action.target);
  if (task.action.review?.button)
    detail(facts, "Submit button", task.action.review.button.label);
  box.append(facts);
  if (task.action.fields) {
    box.append(
      element("h3", "Values that will be submitted"),
      element("pre", JSON.stringify(task.action.fields, null, 2)),
    );
  }
  if (task.action.content)
    box.append(
      element("h3", "Memory to save"),
      element("p", task.action.content),
    );
  if (task.action.review?.page_text)
    box.append(
      element("h3", "Page at preparation"),
      element("pre", task.action.review.page_text),
    );
  if (task.error)
    box.append(element("p", "Recorded failure: " + task.error, "notice"));
  if (task.result)
    box.append(
      element("h3", "Result evidence"),
      element("pre", JSON.stringify(task.result, null, 2)),
    );
  const exact = element("details"),
    summary = element("summary", "Full exact action");
  exact.append(
    summary,
    element("pre", JSON.stringify(task.action, null, 2)),
    element("p", "Review digest: " + task.digest, "mono"),
  );
  box.append(exact);
  const actions = element("div", undefined, "actions");
  if (task.state === "awaiting_approval")
    actions.append(
      button(
        "Approve this exact action",
        async () => {
          await api("approve", { id: task.id, digest: task.digest });
          await refresh();
          await review(task.id);
          feedback("Approved. It will run when execution is resumed.");
        },
        "primary",
      ),
    );
  if (
    ["queued", "awaiting_approval", "approved", "running"].includes(task.state)
  )
    actions.append(
      button(
        "Cancel task",
        async () => {
          await api("cancel", { id });
          await refresh();
          await review(id);
        },
        "danger",
      ),
    );
  if (task.state === "uncertain") {
    box.append(
      element(
        "p",
        "Check the destination yourself. This action may already have completed; it will not be repeated automatically.",
        "notice",
      ),
    );
    for (const completed of [true, false])
      actions.append(
        button(
          completed
            ? "I verified it completed"
            : "I verified it did not complete",
          async () => {
            const note = window.prompt(
              "What did you verify at the destination? Do not include credentials.",
            );
            if (!note) return;
            await api("resolve", { id, completed, note });
            await refresh();
            await review(id);
            feedback(
              "Your outcome verification is saved. A new attempt still needs a fresh approval.",
            );
          },
        ),
      );
  }
  box.append(actions);
  box.scrollIntoView({ behavior: "smooth", block: "start" });
}
async function loginInput(event) {
  if (!loginId) throw new Error("Start a private sign-in first.");
  showLogin(await api("login_input", { session_id: loginId, event }));
}
const lines = (id) =>
  $(id)
    .value.split("\n")
    .map((v) => v.trim())
    .filter(Boolean);
$("unlock-button").onclick = () =>
  perform(async () => {
    token = $("access-key").value.trim();
    $("access-key").value = "";
    await refresh();
    feedback("Owner controls unlocked.");
  });
$("refresh").onclick = () => perform(refresh);
$("pause").onclick = async () => {
  try {
    await api("pause");
    clearLogin();
    await refresh();
    feedback(
      "Execution paused. Any request already sent still needs its outcome checked.",
    );
  } catch (error) {
    feedback(error.message, true);
  }
};
$("resume").onclick = () =>
  perform(async () => {
    await api("resume");
    await refresh();
    feedback("Execution resumed. Only approved actions can submit.");
  });
$("disconnect").onclick = () =>
  perform(async () => {
    await api("disconnect_browser");
    clearLogin();
    await refresh();
    feedback(
      "Browser disconnected; its saved session was removed. Provider-side sessions must be revoked at the provider.",
    );
  });
$("start-login").onclick = () =>
  perform(async () => {
    showLogin(
      await api("start_login", {
        origins: lines("origins"),
        login_origins: lines("login-origins"),
        url: $("login-url").value.trim(),
      }),
    );
    await refresh();
    feedback(
      "Private sign-in is ready. You are operating this browser directly.",
    );
  });
$("login-screen").onclick = (event) =>
  perform(async () => {
    const rect = $("login-screen").getBoundingClientRect();
    await loginInput({
      type: "click",
      x: ((event.clientX - rect.left) * screenSize.width) / rect.width,
      y: ((event.clientY - rect.top) * screenSize.height) / rect.height,
    });
  });
$("type-text").onclick = () =>
  perform(async () => {
    const text = $("login-text").value;
    $("login-text").value = "";
    await loginInput({ type: "type", text });
  });
$("refresh-login").onclick = () =>
  perform(async () =>
    showLogin(await api("login_view", { session_id: loginId })),
  );
$("finish-login").onclick = () =>
  perform(async () => {
    await api("finish_login", { session_id: loginId, confirmed: true });
    clearLogin();
    await refresh();
    feedback("Session connected. Work remains paused until you resume it.");
  });
$("cancel-login").onclick = () =>
  perform(async () => {
    await api("cancel_login", { session_id: loginId });
    clearLogin();
    await refresh();
    feedback("Sign-in cancelled. Work remains paused.");
  });
for (const b of document.querySelectorAll("[data-key]"))
  b.onclick = () =>
    perform(() => loginInput({ type: "key", key: b.dataset.key }));
for (const b of document.querySelectorAll("[data-scroll]"))
  b.onclick = () =>
    perform(() => loginInput({ type: "scroll", y: Number(b.dataset.scroll) }));
for (const b of document.querySelectorAll("[data-panel]"))
  b.onclick = () => panel(b.dataset.panel);
if (token) perform(refresh);
