#!/usr/bin/env python3
"""Read-only operational checks. Never run jobs, send messages, or show credential values."""
import argparse
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
import subprocess

from sync_engine import SyncError, load_catalog, load_jobs, mapping, paused, read_yaml, validate_profile, cron_expr, env_values


def command(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return subprocess.CompletedProcess(args, 1, "", "")


def active_service(name, runner=command):
    return any(runner(["systemctl", *scope, "is-active", "--quiet", name]).returncode == 0
               for scope in ([], ["--user"]))


def host_shares(mountinfo):
    """Conservative detection of host sharing, including bind aliases of shared filesystems."""
    shares = []
    for line in mountinfo.splitlines():
        fields = line.split()
        if "-" not in fields or len(fields) < 7:
            continue
        separator = fields.index("-")
        if len(fields) <= separator + 1:
            continue
        kind, target = fields[separator + 1], fields[4]
        if kind in ("virtiofs", "9p", "vboxsf", "fuse.vmhgfs-fuse", "fuse.orbstack") or target in ("/Users", "/mnt/mac", "/mnt/host"):
            shares.append(target)
    return shares


def parse_time(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else None
    except (AttributeError, TypeError, ValueError):
        return None


def health(root, home, require_isolation=False, probe=False, runner=command,
           now=None, mountinfo=None):
    now = now or datetime.now(timezone.utc)
    results = []

    def report(level, label, detail):
        results.append((level, label, detail))

    try:
        catalog = load_catalog(root)
        profile = validate_profile(read_yaml(home / "sidekick/profile.yaml"), catalog)
        config = read_yaml(home / "config.yaml")
        jobs = load_jobs(home / "cron/jobs.json")
        servers = mapping(config.get("mcp_servers", {}), "config.mcp_servers")
        for server in servers.values():
            mapping(server, "MCP server")
    except SyncError as exc:
        return [("FAIL", "configuration", str(exc))]
    report("OK", "configuration", "profile, catalog and cron state parse correctly")
    result = runner(["hermes", "--version"])
    report("OK" if result.returncode == 0 else "FAIL", "Hermes", "CLI executable check")
    for name in ["hermes-gateway"] + (["signal-cli"] if profile["channels"].get("signal", {}).get("enabled") else []):
        active = active_service(name, runner)
        report("OK" if active else "FAIL", name, "active" if active else "inactive or unavailable")
    if (home / "sidekick/reload-required").exists():
        report("FAIL", "gateway", "reload pending after incomplete sync; repair and rerun --apply")
    try:
        envpath = home / ".env"
        # Only inspect presence and permissions; never expose any values or identities.
        values = env_values(envpath)
        key_set = bool(values.get("ANTHROPIC_API_KEY", "").strip().strip("\"'"))
        report("OK" if key_set else "FAIL", "model key", "present" if key_set else "missing or empty")
        report("FAIL" if envpath.stat().st_mode & 0o077 else "OK", "secrets permissions", "VM .env must be private (0600)")
        effective_timezone = os.environ.get("HERMES_TIMEZONE") or values.get("HERMES_TIMEZONE") or config.get("timezone")
        report("OK" if effective_timezone == profile["core"]["timezone"] else "WARN", "scheduler timezone",
               "matches profile" if effective_timezone == profile["core"]["timezone"] else "not explicitly aligned with profile; sync and check service environment overrides")
        if profile["channels"].get("signal", {}).get("enabled"):
            configured = all(values.get(k, "").strip() for k in ("SIGNAL_ACCOUNT", "SIGNAL_HTTP_URL", "SIGNAL_ALLOWED_USERS", "SIGNAL_HOME_CHANNEL"))
            restricted = values.get("SIGNAL_ALLOW_ALL_USERS", "false").strip().lower() == "false"
            report("OK" if configured and restricted else "FAIL", "Signal settings", "required settings and restricted allowlist check; delivery not tested")
    except OSError:
        report("FAIL", "model key", "VM .env missing or unreadable")
    for (directory, pid), plugin in catalog.items():
        if directory != "connectors":
            continue
        enabled = profile[directory].get(pid, {}).get("enabled", False)
        if plugin.get("hermes", {}).get("kind") == "mcp":
            server = servers.get(pid, {})
            installed_enabled = bool(server) and server.get("enabled", True)
            if enabled != installed_enabled:
                report("FAIL", pid, "profile/MCP enablement mismatch; complete recipe or sync")
            elif enabled:
                report("OK", pid, "MCP configured; OAuth and API access not yet verified")
                if probe:
                    result = runner(["hermes", "mcp", "test", pid])
                    # Hermes 0.20 can print connection failure while exiting zero.
                    # Require affirmative discovery evidence; unknown output fails closed.
                    output = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
                    connected = result.returncode == 0 and re.search(r"\bConnected \(\d+ms\)", output) and re.search(r"\bTools discovered: [1-9]\d*\b", output)
                    report("OK" if connected else "FAIL", pid, "MCP discovery confirmed (not an account read)" if connected else "MCP discovery failed or success could not be verified; inspect locally")
        elif enabled:
            if pid == "notes":
                path = profile[directory][pid].get("path")
                exists = isinstance(path, str) and Path(path).expanduser().is_dir()
                report("OK" if exists else "FAIL", pid, "notes directory available" if exists else "notes directory missing")
            elif pid == "tasks":
                path = profile[directory][pid].get("file")
                valid = isinstance(path, str) and bool(path.strip())
                report("OK" if valid else "FAIL", pid, "task file configured; content not read" if valid else "task file missing from profile")
            else:
                report("INFO", pid, "enabled by policy; remote capability not probed")
    for (directory, pid), plugin in catalog.items():
        if directory != "automations":
            continue
        block = profile[directory].get(pid, {})
        enabled = block.get("enabled", False)
        scheduled = enabled and bool(cron_expr(plugin.get("schedule", {}).get("cron", ""), block.get("time")))
        job = jobs.get(pid)
        if not scheduled:
            if job and not paused(job):
                report("FAIL", pid, "unexpected active cron; sync to pause it")
            continue
        if not job or paused(job):
            report("FAIL", pid, "scheduled job missing or paused")
            continue
        if job.get("last_delivery_error") or job.get("last_status") not in (None, "ok", "success"):
            report("FAIL", pid, "last run or delivery failed; inspect VM logs locally")
        elif job.get("last_run_at"):
            report("OK", pid, "last recorded run succeeded; receipt/content not verified")
        else:
            report("WARN", pid, "no completed run recorded yet")
        next_run = parse_time(job.get("next_run_at"))
        if next_run is None:
            report("FAIL", pid, "missing or invalid next-run timestamp")
        elif next_run < now - timedelta(minutes=15):
            report("FAIL", pid, "schedule overdue by more than 15 minutes; check host uptime/scheduler")
    try:
        mounts = mountinfo if mountinfo is not None else Path("/proc/self/mountinfo").read_text()
        shared = host_shares(mounts)
        report(("FAIL" if require_isolation else "WARN") if shared else "OK", "host filesystem sharing",
               "host shares detected; agent can access mounted host files" if shared else "no known host-share filesystem detected (not a sandbox certification)")
    except OSError:
        report("FAIL" if require_isolation else "WARN", "host filesystem sharing", "mount inspection unavailable")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--require-isolation", action="store_true", help="fail if host filesystem sharing is detected or cannot be inspected")
    parser.add_argument("--probe-connectors", action="store_true", help="connect to enabled MCPs for tool discovery; never invoke account tools")
    args = parser.parse_args()
    try:
        if os.environ.get("HERMES_HOME") and Path(os.environ["HERMES_HOME"]).expanduser().resolve() != (Path.home() / ".hermes").resolve():
            raise SyncError("health checks target the default Hermes home; unset HERMES_HOME first")
        results = health(args.root, Path.home() / ".hermes", args.require_isolation, args.probe_connectors)
    except (OSError, SyncError):
        results = [("FAIL", "health", "unable to inspect state; review VM configuration locally")]
    for level, label, detail in results:
        print(f"{level:4} {label}: {detail}")
    return 1 if any(level == "FAIL" for level, _, _ in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
