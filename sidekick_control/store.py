"""Durable tasks, exact approvals and owner controls. Private SQLite; no account calls."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid


class ControlError(Exception):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def text(value, label, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ControlError(f"{label} must be nonempty text of at most {limit} characters")
    return value.strip()


def message(task):
    return {
        "queued": "I’ve saved the task. It’s waiting to run.",
        "running": "I’m working on it.",
        "awaiting_approval": "The exact action is ready for your approval in the owner controls.",
        "approved": "Approved. It’s waiting to run.",
        "succeeded": "The task finished; the result is available.",
        "failed": "I couldn’t finish this task. The failure is recorded for review.",
        "uncertain": "This may have gone through before the interruption. I won’t repeat it; please check the result.",
        "cancelled": "Cancelled. I won’t continue this task.",
        "expired": "That action expired. Prepare a fresh action before continuing.",
    }[task["state"]]


class Store:
    def __init__(self, directory, clock=time.time):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.directory.is_symlink() or self.directory.stat().st_mode & 0o077:
            raise ControlError("control state directory must be private (0700)")
        self.path = self.directory / "control.sqlite3"
        if self.path.is_symlink():
            raise ControlError("control database cannot be a symlink")
        self.clock = clock
        with self.db() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise ControlError("unsupported control database version")
            db.executescript('''
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                INSERT OR IGNORE INTO settings VALUES ('paused', 'true');
                CREATE TABLE IF NOT EXISTS connectors (
                    name TEXT PRIMARY KEY, enabled INTEGER NOT NULL, generation INTEGER NOT NULL,
                    hosts TEXT NOT NULL, storage TEXT
                );
                INSERT OR IGNORE INTO connectors VALUES ('browser', 0, 0, '[]', NULL);
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY, request_key TEXT NOT NULL UNIQUE, kind TEXT NOT NULL,
                    title TEXT NOT NULL, action TEXT NOT NULL, digest TEXT NOT NULL,
                    connector_generation INTEGER NOT NULL, state TEXT NOT NULL,
                    created REAL NOT NULL, updated REAL NOT NULL, expires REAL NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0, result TEXT, error TEXT,
                    approved_digest TEXT, approved_at REAL
                );
                CREATE INDEX IF NOT EXISTS tasks_digest ON tasks(digest);
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, event TEXT NOT NULL,
                    created REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY, content TEXT NOT NULL, source_task TEXT UNIQUE,
                    created REAL NOT NULL
                );
                PRAGMA user_version=1;
            ''')
        os.chmod(self.path, 0o600)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA secure_delete=ON")
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise

    def event(self, db, task_id, event):
        db.execute("INSERT INTO events(task_id,event,created) VALUES(?,?,?)", (task_id, event, self.clock()))

    def _task(self, db, task_id):
        row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            raise ControlError("task not found")
        return row

    def _view(self, row):
        task = dict(row)
        for field in ("action", "result"):
            task[field] = json.loads(task[field]) if task[field] is not None else None
        task["message"] = message(task)
        return task

    def get(self, task_id):
        with self.db() as db:
            return self._view(self._task(db, task_id))

    def list_tasks(self):
        with self.db() as db:
            # Full page/form evidence belongs in task(id). Returning it for every
            # task would exceed IPC limits and flood ordinary conversation context.
            rows = db.execute("SELECT id,kind,title,state,digest,created,updated,expires,attempts,error FROM tasks ORDER BY created DESC LIMIT 100")
            return [dict(row, message=message(row)) for row in rows]

    def status(self):
        with self.db() as db:
            return {
                "paused": json.loads(db.execute("SELECT value FROM settings WHERE key='paused'").fetchone()[0]),
                "counts": {row[0]: row[1] for row in db.execute("SELECT state,count(*) FROM tasks GROUP BY state")},
                "connectors": [dict(row) for row in db.execute("SELECT name,enabled,generation,hosts FROM connectors")],
            }

    def connector(self):
        with self.db() as db:
            row = dict(db.execute("SELECT * FROM connectors WHERE name='browser'").fetchone())
            row["hosts"] = json.loads(row["hosts"])
            row["storage"] = json.loads(row["storage"]) if row["storage"] else None
            return row

    def propose(self, request_key, kind, title, action):
        request_key = text(request_key, "request key", 160)
        title = text(title, "title", 160)
        if kind not in ("browser.inspect", "browser.submit", "memory.save") or not isinstance(action, dict):
            raise ControlError("unsupported task kind or action")
        # Exact browser schema is validated by the service before this storage boundary.
        if kind == "memory.save":
            if set(action) != {"content"}:
                raise ControlError("memory action must contain only content")
            action = {"content": text(action["content"], "memory", 4000)}
        encoded = canonical(action)
        if len(encoded) > 50000:
            raise ControlError("action is too large")
        now = self.clock()
        with self.transaction() as db:
            connector = db.execute("SELECT * FROM connectors WHERE name='browser'").fetchone()
            generation = connector["generation"] if kind.startswith("browser.") else 0
            identity = digest({"kind": kind, "action": action, "generation": generation})
            old = db.execute("SELECT * FROM tasks WHERE request_key=?", (request_key,)).fetchone()
            if old:
                if old["kind"] != kind or old["action"] != encoded:
                    raise ControlError("request key already belongs to different work")
                return self._view(old)
            if kind.startswith("browser.") and not connector["enabled"]:
                raise ControlError("browser connector is disconnected")
            if kind != "browser.inspect":
                # Repeated model tool calls with a new request key must not duplicate an
                # already accepted or uncertain action. A failed/not-sent proposal can be revised.
                old = db.execute("SELECT * FROM tasks WHERE digest=? AND state NOT IN ('cancelled','expired','failed') AND (expires>? OR state IN ('running','succeeded','uncertain')) ORDER BY created DESC LIMIT 1", (identity, now)).fetchone()
                if old:
                    return self._view(old)
            task_id = uuid.uuid4().hex
            state = "queued" if kind == "browser.inspect" else "awaiting_approval"
            db.execute("INSERT INTO tasks(id,request_key,kind,title,action,digest,connector_generation,state,created,updated,expires) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                       (task_id, request_key, kind, title, encoded, identity, generation, state, now, now, now + 900))
            self.event(db, task_id, state)
            return self._view(self._task(db, task_id))

    def approve(self, task_id, expected_digest):
        with self.transaction() as db:
            task = self._task(db, task_id)
            if task["state"] != "awaiting_approval" or expected_digest != task["digest"]:
                raise ControlError("approval does not match a pending exact action")
            if task["expires"] <= self.clock():
                raise ControlError("proposal expired; prepare a fresh action")
            if task["kind"].startswith("browser."):
                connector = db.execute("SELECT * FROM connectors WHERE name='browser'").fetchone()
                if not connector["enabled"] or connector["generation"] != task["connector_generation"]:
                    raise ControlError("connector changed; prepare a fresh action")
            db.execute("UPDATE tasks SET state='approved',approved_digest=digest,approved_at=?,updated=? WHERE id=?", (self.clock(), self.clock(), task_id))
            self.event(db, task_id, "approved")
        return self.get(task_id)

    def set_paused(self, paused):
        with self.transaction() as db:
            db.execute("UPDATE settings SET value=? WHERE key='paused'", (canonical(bool(paused)),))
            if paused:
                # A worker may already have sent a request. Conservatively hold for review.
                for row in db.execute("SELECT id,kind FROM tasks WHERE state='running'").fetchall():
                    state = "uncertain" if row["kind"] == "browser.submit" else "queued"
                    db.execute("UPDATE tasks SET state=?,error='paused_during_execution',updated=? WHERE id=?", (state, self.clock(), row["id"]))
                    self.event(db, row["id"], state)
            self.event(db, None, "paused" if paused else "resumed")
        return self.status()

    def configure_browser(self, enabled, hosts=None, storage=None):
        with self.transaction() as db:
            current = db.execute("SELECT * FROM connectors WHERE name='browser'").fetchone()
            db.execute("UPDATE connectors SET enabled=?,generation=generation+1,hosts=?,storage=? WHERE name='browser'",
                       (int(enabled), canonical(hosts if hosts is not None else json.loads(current["hosts"])),
                        canonical(storage) if storage is not None and enabled else None))
            for row in db.execute("SELECT id,state FROM tasks WHERE kind LIKE 'browser.%' AND state IN ('queued','awaiting_approval','approved','running')").fetchall():
                state = "uncertain" if row["state"] == "running" else "cancelled"
                db.execute("UPDATE tasks SET state=?,error='connector_changed',updated=? WHERE id=?", (state, self.clock(), row["id"]))
                self.event(db, row["id"], state)
            self.event(db, None, "browser_connected" if enabled else "browser_disconnected")
        return self.status()

    def cancel(self, task_id):
        with self.transaction() as db:
            task = self._task(db, task_id)
            if task["state"] in ("succeeded", "failed", "uncertain", "cancelled", "expired"):
                raise ControlError("task is already finished or requires outcome review")
            state = "uncertain" if task["state"] == "running" and task["kind"] == "browser.submit" else "cancelled"
            db.execute("UPDATE tasks SET state=?,error='cancel_requested',updated=? WHERE id=?", (state, self.clock(), task_id))
            self.event(db, task_id, state)
        return self.get(task_id)

    def recover(self):
        with self.transaction() as db:
            for row in db.execute("SELECT * FROM tasks WHERE state='running'").fetchall():
                state = "uncertain" if row["kind"] == "browser.submit" else ("queued" if row["attempts"] < 3 else "failed")
                db.execute("UPDATE tasks SET state=?,error='worker_interrupted',updated=? WHERE id=?", (state, self.clock(), row["id"]))
                self.event(db, row["id"], state)

    def claim(self):
        with self.transaction() as db:
            if json.loads(db.execute("SELECT value FROM settings WHERE key='paused'").fetchone()[0]):
                return None
            now = self.clock()
            for row in db.execute("SELECT id FROM tasks WHERE kind!='browser.inspect' AND state IN ('queued','awaiting_approval','approved') AND expires<=?", (now,)).fetchall():
                db.execute("UPDATE tasks SET state='expired',updated=? WHERE id=?", (now, row["id"]))
                self.event(db, row["id"], "expired")
            task = db.execute("SELECT * FROM tasks WHERE state IN ('queued','approved') ORDER BY created LIMIT 1").fetchone()
            if task is None:
                return None
            if task['attempts'] >= 3:
                db.execute("UPDATE tasks SET state='failed',error='attempt_limit',updated=? WHERE id=?", (now, task['id']))
                self.event(db, task['id'], 'failed')
                return None
            if task["kind"] != "browser.inspect" and task["approved_digest"] != task["digest"]:
                raise ControlError("task has no matching approval")
            if task["kind"].startswith("browser."):
                c = db.execute("SELECT * FROM connectors WHERE name='browser'").fetchone()
                if not c["enabled"] or c["generation"] != task["connector_generation"]:
                    db.execute("UPDATE tasks SET state='cancelled',updated=? WHERE id=?", (now, task["id"]))
                    self.event(db, task["id"], "cancelled")
                    return None
            db.execute("UPDATE tasks SET state='running',attempts=attempts+1,updated=? WHERE id=?", (now, task["id"]))
            self.event(db, task["id"], "running")
            return self._view(self._task(db, task["id"]))

    def finish(self, task_id, outcome, result=None, error=None):
        with self.transaction() as db:
            task = self._task(db, task_id)
            if task["state"] != "running":
                return  # pause/cancel/disconnect won the race; don't overwrite that decision
            if outcome not in ("succeeded", "failed", "uncertain"):
                raise ControlError("invalid execution outcome")
            db.execute("UPDATE tasks SET state=?,result=?,error=?,updated=? WHERE id=?",
                       (outcome, canonical(result) if result is not None else None, error, self.clock(), task_id))
            self.event(db, task_id, outcome)

    def save_memory_task(self, task_id):
        with self.transaction() as db:
            task = self._task(db, task_id)
            if task["kind"] != "memory.save" or task["state"] != "running" or task["approved_digest"] != task["digest"]:
                raise ControlError("memory change requires the approved running task")
            content = json.loads(task["action"])["content"]
            db.execute("INSERT OR IGNORE INTO memories VALUES(?,?,?,?)", (task_id, content, task_id, self.clock()))
            db.execute("UPDATE tasks SET state='succeeded',result=?,updated=? WHERE id=?", (canonical({"memory_id": task_id}), self.clock(), task_id))
            self.event(db, task_id, "succeeded")

    def memories(self):
        with self.db() as db:
            return [dict(r) for r in db.execute("SELECT id,content,created FROM memories ORDER BY created")]

    def forget(self, memory_id):
        with self.transaction() as db:
            row = db.execute("SELECT source_task FROM memories WHERE id=?", (memory_id,)).fetchone()
            if row is None:
                raise ControlError("memory not found")
            db.execute("DELETE FROM memories WHERE id=?", (memory_id,))
            # Forget also removes the saved text from its proposal/audit payload. Event
            # records contain only IDs/states. Backups and old model sessions are separate.
            db.execute("UPDATE tasks SET action=?,result=NULL,title='Forgotten memory' WHERE id=?", (canonical({"content": "[forgotten]"}), row["source_task"]))
            self.event(db, row["source_task"], "memory_forgotten")
        return {"forgotten": memory_id}

    def retry_read(self, task_id):
        with self.transaction() as db:
            task = self._task(db, task_id)
            if task["kind"] != "browser.inspect" or task["state"] != "failed" or task["attempts"] >= 3:
                raise ControlError("only failed inspections can retry, at most three attempts")
            db.execute("UPDATE tasks SET state='queued',error=NULL,updated=? WHERE id=?", (self.clock(), task_id))
            self.event(db, task_id, "queued")
        return self.get(task_id)

    def resolve(self, task_id, completed, note):
        note = text(note, "outcome evidence", 1000)
        with self.transaction() as db:
            task = self._task(db, task_id)
            if task["state"] != "uncertain":
                raise ControlError("only uncertain actions can be resolved")
            state = "succeeded" if completed else "failed"
            db.execute("UPDATE tasks SET state=?,result=?,error=NULL,updated=? WHERE id=?", (state, canonical({"owner_verified": True, "note": note}), self.clock(), task_id))
            self.event(db, task_id, "owner_verified_" + state)
        return self.get(task_id)

    def events(self, after=0):
        if type(after) is not int or after < 0:
            raise ControlError("event cursor must be a nonnegative integer")
        with self.db() as db:
            rows = [dict(r) for r in db.execute("SELECT * FROM events WHERE seq>? ORDER BY seq LIMIT 100", (after,))]
            return {"events": rows, "cursor": rows[-1]["seq"] if rows else after}
