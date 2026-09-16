#!/usr/bin/env python3
"""Validate first, then reconcile Sidekick state. Check mode never writes or runs commands."""
import argparse
import copy
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

CATEGORIES = {"channels": "channel", "connectors": "connector", "automations": "automation"}


class SyncError(Exception):
    """An actionable error safe to display without credential or prompt contents."""


class UniqueKeyLoader(yaml.SafeLoader):
    """Reject duplicate YAML keys instead of silently replacing a user's choice."""

    def construct_mapping(self, node, deep=False):
        self.flatten_mapping(node)
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                duplicate = key in result
            except TypeError:
                raise yaml.YAMLError("mapping key must be scalar") from None
            if duplicate:
                raise yaml.YAMLError("duplicate mapping key")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def mapping(value, label):
    if not isinstance(value, dict):
        raise SyncError(f"{label}: expected a mapping")
    return value


def read_yaml(path):
    try:
        return mapping(yaml.load(path.read_text(), Loader=UniqueKeyLoader), path.name)
    except (OSError, UnicodeError, yaml.YAMLError):
        raise SyncError(f"{path.name}: missing, unreadable, or invalid YAML") from None


def env_values(path):
    """Inspect simple dotenv settings without executing them or logging their values."""
    if not path.exists():
        return {}
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[7:].lstrip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if value.startswith(("'", '"')) and value[-1:] == value[:1]:
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].rstrip()
        values[key.strip()] = value
    return values


def cron_expr(expression, time=None):
    if time is not None:
        if not isinstance(time, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", time):
            raise SyncError("automation time must be HH:MM (00:00–23:59)")
        hour, minute = map(int, time.split(":"))
        calendar_fields = cron_expr(expression).split()[2:] if expression else ["*", "*", "*"]
        expression = f"{minute} {hour} " + " ".join(calendar_fields)
    if not isinstance(expression, str):
        raise SyncError("schedule.cron must be a string")
    if not expression:
        return ""
    fields = expression.split()
    if len(fields) != 5:
        raise SyncError("schedule.cron must have five numeric cron fields")
    for field, (low, high) in zip(fields, [(0, 59), (0, 23), (1, 31), (1, 12), (0, 7)]):
        for term in field.split(","):
            match = re.fullmatch(r"(\*|\d+(?:-\d+)?)(?:/(\d+))?", term)
            if not match or (match[2] is not None and not 1 <= int(match[2]) <= high + 1):
                raise SyncError("invalid numeric cron field")
            if match[1] != "*":
                values = [int(x) for x in match[1].split("-")]
                if not all(low <= v <= high for v in values) or values[0] > values[-1]:
                    raise SyncError("cron field outside its allowed range")
    return expression


def load_catalog(root):
    catalog = {}
    for directory, category in CATEGORIES.items():
        parent = root / "plugins" / directory
        if not parent.is_dir():
            raise SyncError(f"catalog directory missing: {directory}")
        for folder in sorted(parent.iterdir()):
            if not folder.is_dir() or folder.name.startswith(("_", ".")):
                continue
            plugin = read_yaml(folder / "plugin.yaml")
            pid = folder.name
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", pid):
                raise SyncError("plugin directory must use a lowercase, hyphenated ID")
            if plugin.get("id") != pid or plugin.get("category") != category:
                raise SyncError(f"{pid}: id/category does not match its directory")
            for field in ("name", "summary"):
                if not isinstance(plugin.get(field), str) or not plugin[field].strip():
                    raise SyncError(f"{pid}: missing {field}")
            for field in ("security", "requires", "settings", "hermes", "schedule"):
                mapping(plugin.get(field, {}), f"{pid}.{field}")
            if plugin.get("security", {}).get("secrets_location") != "vm":
                raise SyncError(f"{pid}: secrets_location must be vm")
            deps = plugin.get("requires", {}).get("connectors", [])
            if not isinstance(deps, list) or any(not isinstance(d, str) for d in deps):
                raise SyncError(f"{pid}: requires.connectors must be a list of IDs")
            filename = "prompt.md" if category == "automation" else "recipe.md"
            try:
                content = (folder / filename).read_text()
            except OSError:
                raise SyncError(f"{pid}: missing {filename}") from None
            if not content.strip():
                raise SyncError(f"{pid}: empty {filename}")
            if category == "automation":
                cron_expr(plugin.get("schedule", {}).get("cron", ""))
                plugin["prompt"] = content
            key = (directory, pid)
            catalog[key] = plugin
    for (_, pid), plugin in catalog.items():
        for dep in plugin.get("requires", {}).get("connectors", []):
            if ("connectors", dep) not in catalog:
                raise SyncError(f"{pid}: unknown connector dependency")
    return catalog


def validate_profile(profile, catalog):
    if type(profile.get("version")) is not int or profile["version"] != 1:
        raise SyncError("profile.version must be 1")
    core = mapping(profile.get("core"), "profile.core")
    try:
        ZoneInfo(core.get("timezone", ""))
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise SyncError("core.timezone must be an IANA timezone") from None
    normalized = copy.deepcopy(profile)
    for directory in CATEGORIES:
        blocks = mapping(profile.get(directory), f"profile.{directory}")
        normalized[directory] = {}
        for key, block in blocks.items():
            if not isinstance(key, str):
                raise SyncError(f"{directory}: plugin keys must be strings")
            pid = key.replace("_", "-")
            if (directory, pid) not in catalog:
                raise SyncError(f"{directory}: unknown plugin ID")
            if pid in normalized[directory]:
                raise SyncError(f"{pid}: duplicate hyphen/underscore aliases")
            mapping(block, f"{pid} settings")
            if type(block.get("enabled")) is not bool:
                raise SyncError(f"{pid}.enabled must be true or false")
            if directory == "automations" and "time" in block:
                cron_expr("", block["time"])
            normalized[directory][pid] = block
    for (directory, pid), plugin in catalog.items():
        if normalized[directory].get(pid, {}).get("enabled", False):
            for dep in plugin.get("requires", {}).get("connectors", []):
                if not normalized["connectors"].get(dep, {}).get("enabled", False):
                    raise SyncError(f"{pid}: enable required connector {dep}, or disable {pid}")
    return normalized


def load_jobs(path):
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        raise SyncError("jobs.json: unreadable or invalid JSON") from None
    jobs = data.get("jobs", data) if isinstance(data, dict) else data
    if isinstance(jobs, dict):
        jobs = list(jobs.values())
    if not isinstance(jobs, list):
        raise SyncError("jobs.json: expected a list or mapping of jobs")
    result = {}
    ids = set()
    for job in jobs:
        mapping(job, "cron job")
        if not isinstance(job.get("id"), str) or not job["id"] or job["id"] in ids:
            raise SyncError("jobs.json: missing or duplicate job ID")
        ids.add(job["id"])
        name = job.get("name")
        if name is None:  # unrelated unnamed Hermes jobs are left alone
            continue
        if not isinstance(name, str) or name in result:
            raise SyncError("jobs.json: invalid or duplicate job name")
        schedule = job.get("schedule", {})
        if not isinstance(schedule, (dict, str)) or not isinstance(job.get("prompt", ""), str):
            raise SyncError("jobs.json: invalid schedule or prompt")
        if "enabled" in job and type(job["enabled"]) is not bool:
            raise SyncError("jobs.json: enabled must be boolean")
        result[name] = job
    return result


def paused(job):
    return bool(job.get("paused_at")) or job.get("state") == "paused" or job.get("enabled") is False


def build_plan(root, home):
    """Read and validate ALL inputs before returning any write or command operations."""
    catalog = load_catalog(root)
    profile = validate_profile(read_yaml(home / "sidekick/profile.yaml"), catalog)
    jobs = load_jobs(home / "cron/jobs.json")
    config = read_yaml(home / "config.yaml")
    original_config = copy.deepcopy(config)
    # Hermes schedules use its top-level timezone, not Sidekick's profile directly.
    desired_timezone = profile["core"]["timezone"]
    timezone_changed = config.get("timezone") != desired_timezone
    for override in (os.environ.get("HERMES_TIMEZONE"), env_values(home / ".env").get("HERMES_TIMEZONE")):
        if override and override != desired_timezone:
            raise SyncError("HERMES_TIMEZONE overrides core.timezone; align them before sync")
    config["timezone"] = desired_timezone
    servers = mapping(config.get("mcp_servers", {}), "config.mcp_servers")
    for name, server in servers.items():
        mapping(server, "MCP server settings")
        if "enabled" in server and type(server["enabled"]) is not bool:
            raise SyncError("MCP server enabled must be boolean")
    try:
        soul = (root / "config/SOUL.md").read_text()
    except OSError:
        raise SyncError("repo SOUL.md is missing or unreadable") from None
    if not soul.strip():
        raise SyncError("repo SOUL.md is empty")
    channels = [pid for pid, b in profile["channels"].items() if b["enabled"]]
    writes, commands, rows = {}, [], []
    for (directory, pid), plugin in catalog.items():
        block = profile[directory].get(pid, {})
        enabled = block.get("enabled", False)
        state = "enabled (policy)" if enabled else "off (policy)"
        if directory == "connectors" and plugin.get("hermes", {}).get("kind") == "mcp":
            # Recipes register one MCP server per plugin under its exact ID. Unknown/shared
            # registrations are deliberately not guessed or removed.
            if pid not in servers and enabled:
                raise SyncError(f"{pid}: MCP server missing; complete its setup recipe first")
            state = "off (not installed)"
            if pid in servers:
                server = servers[pid]
                state = "in sync"
                if server.get("enabled", True) != enabled:
                    server["enabled"] = enabled
                    state = "enable MCP" if enabled else "disable MCP"
        if directory == "automations":
            prompt = plugin["prompt"]
            writes[home / "sidekick" / f"{pid}.prompt.txt"] = prompt
            expr = cron_expr(plugin.get("schedule", {}).get("cron", ""), block.get("time"))
            job = jobs.get(pid)
            if enabled and expr:
                if len(channels) != 1:
                    raise SyncError("scheduled automations require exactly one enabled delivery channel")
                deliver = channels[0]
                state = "in sync"
                if job is None:
                    commands.append((f"{pid}: create", ["hermes", "cron", "create", expr, prompt,
                                                       "--name", pid, "--deliver", deliver]))
                    state = "create"
                else:
                    changes = []
                    schedule = job.get("schedule", {})
                    actual = schedule.get("expr", "") if isinstance(schedule, dict) else schedule
                    for flag, desired, current in [("prompt", prompt.rstrip(), job.get("prompt", "").rstrip()),
                                                   ("schedule", expr, actual),
                                                   ("deliver", deliver, job.get("deliver"))]:
                        if desired != current or (flag == "schedule" and timezone_changed):
                            commands.append((f"{pid}: {flag}", ["hermes", "cron", "edit", job["id"],
                                                                "--" + flag, desired]))
                            changes.append(flag)
                    if paused(job):
                        commands.append((f"{pid}: resume", ["hermes", "cron", "resume", job["id"]]))
                        changes.append("resume")
                    if changes:
                        state = "sync:" + ",".join(changes)
            else:
                state = "in brief / on demand" if enabled else "off"
                # Removing a standalone schedule must also pause any pre-existing cron.
                if job and not paused(job):
                    commands.append((f"{pid}: pause", ["hermes", "cron", "pause", job["id"]]))
                    state = "pause"
        rows.append((pid, enabled, state))
    if config != original_config:
        writes[home / "config.yaml"] = yaml.safe_dump(config, sort_keys=False)
    writes[home / "SOUL.md"] = soul
    writes = {p: content for p, content in writes.items() if not p.exists() or p.read_text() != content}
    restart = home / "SOUL.md" in writes or home / "config.yaml" in writes
    return writes, commands, rows, restart


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=".sidekick-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)  # mkstemp makes the new file mode 0600
    finally:
        if os.path.exists(name):
            os.unlink(name)


def run_command(args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        raise SyncError("command unavailable or timed out; inspect VM service logs") from None
    if result.returncode:
        # Commands may echo prompt, identity, or credential values. Never relay raw output.
        raise SyncError(f"command exited {result.returncode}; inspect VM service logs")


def gateway_command():
    for scope in ([], ["--user"]):
        result = subprocess.run(["systemctl", *scope, "show", "hermes-gateway", "--property=LoadState", "--value"],
                                capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip() == "loaded":
            return ["systemctl", "--user", "restart", "hermes-gateway"] if scope else ["sudo", "-n", "systemctl", "restart", "hermes-gateway"]
    raise SyncError("gateway service not installed; rerun bootstrap")


def sync(root, home, apply=False, runner=run_command, gateway=gateway_command):
    writes, commands, rows, restart = build_plan(root, home)
    marker = home / "sidekick/reload-required"
    restart = restart or marker.exists()
    print(f"Validation: passed ({len(rows)} plugins)")
    for pid, enabled, state in rows:
        print(f"  {pid:<22} {'yes' if enabled else 'no':<4} {state}")
    for path in writes:
        print(f"  deploy: {path.name}")
    if restart:
        print("  gateway: reload required")
    print("Channel flags do not reconfigure transports. Shell-based connectors use agent policy, not access revocation.")
    if not apply:
        print("Drift/actions above; run --apply." if writes or commands or restart else "Everything in sync.")
        return
    # Verify reload feasibility before writes; retain marker across partial failure so a
    # retry reloads even when files already match. Command effects are NOT transactional.
    restart_command = gateway() if restart else None
    if restart:
        atomic_write(marker, "Gateway reload required after Sidekick sync.\n")
    for path, content in writes.items():
        if path.exists():
            atomic_write(path.with_name(path.name + ".pre-sync.bak"), path.read_text())
        atomic_write(path, content)
    if restart:
        try:
            runner(restart_command)
            scope = ["--user"] if "--user" in restart_command else []
            runner(["systemctl", *scope, "is-active", "--quiet", "hermes-gateway"])
        except SyncError as exc:
            raise SyncError(f"gateway reload failed: {exc}; rerun --apply after repair") from None
        marker.unlink()
    for label, args in commands:
        print(f"Applying {label}")
        try:
            runner(args)
        except SyncError as exc:
            raise SyncError(f"{label} failed: {exc}; prior operations may have applied; rerun after repair") from None
    remaining_writes, remaining_commands, _, _ = build_plan(root, home)
    if remaining_writes or remaining_commands:
        raise SyncError("post-apply verification found remaining drift; a command had no effect or state changed concurrently; rerun --check")
    print("Apply complete.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["check", "apply"], nargs="?", default="check")
    parser.add_argument("root", type=Path, nargs="?", default=Path("."))
    args = parser.parse_args()
    home = Path.home() / ".hermes"
    try:
        if os.environ.get("HERMES_HOME") and Path(os.environ["HERMES_HOME"]).expanduser().resolve() != home.resolve():
            raise SyncError("Sidekick manages the default Hermes home; unset HERMES_HOME before sync")
        if args.mode == "apply":
            if not home.is_dir():
                raise SyncError("Hermes home missing; complete bootstrap first")
            # Lock the existing directory: no lock file and no writes before validation.
            lock = os.open(home, os.O_RDONLY)
            try:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise SyncError("another Sidekick sync is applying; retry later") from None
                sync(args.root, home, apply=True)
            finally:
                os.close(lock)
        else:
            sync(args.root, home)
    except (SyncError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc if isinstance(exc, SyncError) else 'unable to access state or service; inspect VM locally'}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
