#!/usr/bin/env python3
"""
sync engine — deploy SOUL, validate the plugin catalog, and reconcile crons from the profile.

Runs INSIDE the VM (it has PyYAML, the profile, cron/jobs.json, and the `hermes` CLI), reading
the repo via the OrbStack mount. Invoked by scripts/sync.sh — not meant to be run by hand.

    python3 sync_engine.py <check|apply> <repo_root>

check  = report only (no changes).  apply = deploy + reconcile.
Makes automations plug-and-play: set `enabled: true` in the profile -> the cron is created;
`enabled: false` -> the cron is paused; prompt/schedule drift -> synced.
"""
import sys, os, json, glob, subprocess, difflib
import yaml

MODE  = sys.argv[1] if len(sys.argv) > 1 else "check"
ROOT  = sys.argv[2] if len(sys.argv) > 2 else "."
APPLY = (MODE == "apply")
HOME  = os.path.expanduser("~")
def hp(*a): return os.path.join(HOME, ".hermes", *a)
OK, WARN, ERR, ARROW = "✓", "⚠", "✗", "→"

def load_yaml(p):
    try:
        with open(p) as f: return yaml.safe_load(f) or {}
    except FileNotFoundError: return None
    except Exception: return "INVALID"

def sh(args): return subprocess.run(args, capture_output=True, text=True)

# ---------- state ----------
profile    = load_yaml(hp("sidekick", "profile.yaml"))
prof_ok    = isinstance(profile, dict)
profile    = profile if prof_ok else {}
prof_autos = profile.get("automations") or {}
prof_conns = profile.get("connectors") or {}
prof_chans = profile.get("channels") or {}
deliver = "signal"
for cid, c in (profile.get("channels") or {}).items():
    if isinstance(c, dict) and c.get("enabled"): deliver = cid; break

def load_jobs():
    p = hp("cron", "jobs.json")
    if not os.path.exists(p): return {}
    d = json.load(open(p)); jobs = d if isinstance(d, list) else d.get("jobs", d)
    it = jobs.values() if isinstance(jobs, dict) else jobs
    out = {}
    for j in it:
        if isinstance(j, dict) and j.get("name"):
            s = j.get("schedule", {})
            out[j["name"]] = {
                "id": j.get("id", ""),
                "prompt": j.get("prompt", ""),
                "expr": (s.get("expr") if isinstance(s, dict) else s) or "",
                "paused": bool(j.get("paused_at")) or j.get("state") == "paused",
            }
    return out
jobs = load_jobs()

def cron_expr(plugin_cron, prof_time):
    if prof_time and ":" in str(prof_time):
        hh, mm = str(prof_time).split(":")[:2]
        return f"{int(mm)} {int(hh)} * * *"
    return plugin_cron or ""

issues, rows, soul_changed = [], [], False

# ---------- 1) SOUL.md ----------
repo_soul = os.path.join(ROOT, "config", "SOUL.md")
vm_soul   = hp("SOUL.md")
try: rs = open(repo_soul).read()
except Exception: rs = None
vs = open(vm_soul).read() if os.path.exists(vm_soul) else ""
if rs is None:
    print(f"SOUL.md      : {ERR} repo config/SOUL.md not found")
elif rs == vs:
    print(f"SOUL.md      : {OK} in sync")
else:
    print(f"SOUL.md      : {WARN} drift" + ("  " + ARROW + " deploying" if APPLY else "  (run --apply)"))
    if APPLY:
        if vs: open(vm_soul + ".pre-sync.bak", "w").write(vs)
        open(vm_soul, "w").write(rs); soul_changed = True

# ---------- 2) profile.yaml ----------
if prof_ok:
    print(f"profile.yaml : {OK} present + valid (left untouched)")
elif profile == "INVALID" or os.path.exists(hp("sidekick", "profile.yaml")):
    print(f"profile.yaml : {ERR} present but INVALID yaml — fix it")
else:
    print(f"profile.yaml : {WARN} MISSING" + ("  " + ARROW + " creating from example" if APPLY else ""))
    if APPLY:
        os.makedirs(hp("sidekick"), exist_ok=True)
        ex = open(os.path.join(ROOT, "profile.example.yaml")).read()
        open(hp("sidekick", "profile.yaml"), "w").write(ex); os.chmod(hp("sidekick", "profile.yaml"), 0o600)

# ---------- 3) validate catalog + 4) reconcile crons ----------
REQ = ["id", "name", "category", "summary"]
DIRCAT = {"channels": "channel", "connectors": "connector", "automations": "automation"}
for catdir, cat in DIRCAT.items():
    for pdir in sorted(glob.glob(os.path.join(ROOT, "plugins", catdir, "*"))):
        pid = os.path.basename(pdir)
        if not os.path.isdir(pdir) or pid.startswith(("_", ".")): continue
        y = load_yaml(os.path.join(pdir, "plugin.yaml"))
        if y is None: issues.append((ERR, pid, "no plugin.yaml")); continue
        if y == "INVALID": issues.append((ERR, pid, "invalid YAML")); continue
        for f in REQ:
            if not y.get(f): issues.append((ERR, pid, f"missing '{f}'"))
        if y.get("category") != cat: issues.append((ERR, pid, f"category '{y.get('category')}' != dir"))
        if (y.get("security") or {}).get("secrets_location") != "vm":
            issues.append((WARN, pid, "security.secrets_location should be 'vm'"))
        if cat == "automation" and not os.path.exists(os.path.join(pdir, "prompt.md")):
            issues.append((ERR, pid, "automation missing prompt.md"))
        if cat in ("connector", "channel") and not os.path.exists(os.path.join(pdir, "recipe.md")):
            issues.append((WARN, pid, "missing recipe.md"))

        src = prof_autos if cat == "automation" else (prof_chans if cat == "channel" else prof_conns)
        block = src.get(pid, {}) or {}
        enabled = bool(block.get("enabled"))
        if cat == "automation" and enabled:
            for dep in ((y.get("requires") or {}).get("connectors") or []):
                if not (prof_conns.get(dep, {}) or {}).get("enabled"):
                    issues.append((WARN, pid, f"enabled but connector '{dep}' is off"))

        state, cronid = "-", "-"
        if cat == "automation":
            pmpath = os.path.join(pdir, "prompt.md")
            prompt = open(pmpath).read() if os.path.exists(pmpath) else ""
            if APPLY:
                os.makedirs(hp("sidekick"), exist_ok=True)
                open(hp("sidekick", f"{pid}.prompt.txt"), "w").write(prompt)
            expr = cron_expr((y.get("schedule") or {}).get("cron", ""), block.get("time"))
            job = jobs.get(pid); cronid = (job["id"][:6] if job else "-")
            if enabled and expr:
                if not job:
                    state = "create"
                    if APPLY:
                        r = sh(["hermes", "cron", "create", expr, prompt, "--name", pid, "--deliver", deliver])
                        state = "created" if r.returncode == 0 else "CREATE FAILED"
                else:
                    ch = []
                    if job["prompt"].rstrip() != prompt.rstrip():   # ignore trailing-newline noise
                        ch.append("prompt");   APPLY and sh(["hermes","cron","edit",job["id"],"--prompt",prompt])
                    if job["expr"] != expr:
                        ch.append("schedule"); APPLY and sh(["hermes","cron","edit",job["id"],"--schedule",expr])
                    if job["paused"]:
                        ch.append("resume");   APPLY and sh(["hermes","cron","resume",job["id"]])
                    state = ("sync:" + ",".join(ch)) if ch else "in sync"
            elif enabled and not expr:
                state = "in brief"          # folds into another automation (no standalone cron)
            elif not enabled and job and not job["paused"]:
                state = "pause"
                if APPLY: sh(["hermes", "cron", "pause", job["id"]]); state = "paused"
            elif not enabled:
                state = "off"
        rows.append((cat, pid, "yes" if enabled else "no", cronid, state))

# ---------- output ----------
print(f"\nCatalog  ({len(rows)} plugins)")
print(f"  {'plugin':<22}{'enabled':<9}{'cron':<8}state")
for cat, pid, en, cid, state in rows:
    print(f"  {pid:<22}{en:<9}{cid:<8}{state}")

errs = [i for i in issues if i[0] == ERR]
if issues:
    print("\nValidation")
    for lvl, pid, msg in issues: print(f"  {lvl} {pid}: {msg}")
else:
    print(f"\nValidation: {OK} all plugins conform")

if soul_changed:
    print("\nReloading gateway (SOUL changed)…")
    r = sh(["sudo", "systemctl", "restart", "hermes-gateway"])
    print("  gateway:", "active" if r.returncode == 0 else "restart manually")

print(f"\n{'Apply complete.' if APPLY else ('Drift/actions above — run --apply to reconcile.' if (errs or any(s not in ('in sync','in brief','off','-') for *_ , s in rows)) else 'Everything in sync.')}")
sys.exit(2 if errs else 0)
