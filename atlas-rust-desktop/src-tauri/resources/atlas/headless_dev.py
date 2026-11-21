"""Headless development mode ("Night dev"): Atlas improves its own code with LOCAL models while the user is away.

Design: docs/HEADLESS-DEV-MODE.md. One cycle = plan -> analyse -> build -> test -> review -> document -> hand off.

Safety rules (each one has a test in validation-tests/test_headless_dev.py):
- Work only in a separate git clone under <data>/headless-dev/sandbox. The user's repository is only read.
- Every git call goes through _git(): a short allow-list. No push, fetch from the network, reset, clean or branch delete.
- The only commands that run are FIXED_TESTS. The model writes text, never a command.
- Edits only in ALLOWED_DIRS, at most MAX_EDIT_FILES files and MAX_EDIT_LINES changed lines. Existing tests are read-only.
- Nothing is deleted: a failed change is put aside with "git stash push".
- Every action goes through request_action(). Above low risk it is queued for the user, never run.
- One local model at a time (swarm_run's machine lock). Pause while the user uses the PC. Budgets per cycle and per night.
Standard library only.
"""
from __future__ import annotations

import difflib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP_MARK = "atlas-rust-desktop/src-tauri/tauri.conf.json"  # only the real desktop app has this file (CLAUDE.md 1)
APP_DIR = "atlas-rust-desktop/src-tauri/resources/atlas"
ALLOWED_DIRS = (APP_DIR + "/", "atlas-rust-desktop/validation-tests/", "docs/")
MAX_EDIT_FILES = 3
MAX_EDIT_LINES = 200
PHASES = ("plan", "analyse", "build", "test", "review", "document", "handoff")
NO_PUSH_URL = "DISABLED://atlas-headless-never-pushes"

# The ONLY commands headless mode runs (CLAUDE.md section 5). (label, folder inside the sandbox, args after python).
FIXED_TESTS = (
    ("Backend tests", APP_DIR, ("-m", "unittest", "discover", "-s", "../../../validation-tests", "-p", "test_*.py")),
    ("Bundle check", ".", ("check-bundle.py",)),
)
TEST_TIMEOUT = 900

DEFAULTS = {
    "repo": "",
    "max_cycles": 6, "night_minutes": 240, "night_tokens": 60000,
    "cycle_minutes": 30, "cycle_tokens": 12000, "max_failures": 3, "idle_minutes": 10,
    "plan_model": "tasks", "build_model": "coder", "review_model": "mentor",
    "cloud_enabled": False, "cloud_spend_limit_usd": 0.0, "cloud_usd_per_mtok": 2.0,
}
LIMITS = {"max_cycles": (1, 50), "night_minutes": (5, 720), "night_tokens": (1000, 500000), "cycle_minutes": (2, 120),
          "cycle_tokens": (500, 100000), "max_failures": (1, 10), "idle_minutes": (0, 240),
          "cloud_spend_limit_usd": (0.0, 20.0), "cloud_usd_per_mtok": (0.0, 100.0)}

# Risk tiers for headless actions. Low risk runs. Anything else (and any unknown name) waits for the user.
# cloud_review is only reached when the user turned cloud on AND set a spend limit above 0 (his yes in the panel).
HEADLESS_TIERS = {"sandbox_read": "low", "sandbox_edit": "low", "run_fixed_tests": "low", "sandbox_commit": "low",
                  "cloud_review": "low"}

_LOCK = threading.RLock()
_THREAD = None
_STOP = threading.Event()
_ACT = {"inflight": 0, "last": 0.0}  # User chat requests (server.py calls chat_started / chat_finished)


class SafetyError(RuntimeError):
    """A safety rule refused an action. The message says which rule."""


class _Halt(Exception):
    """Stop the night: budget, stop button, repeated failures. The message is the plain reason."""


# ---------- files ----------
def home():
    return Path(os.environ.get("ATLAS_DATA_DIR", str(HERE))) / "headless-dev"


def _read_json(name, default):
    try:
        data = json.loads((home() / name).read_text(encoding="utf-8"))
        return data if isinstance(data, type(default)) else default
    except (OSError, ValueError):
        return default


def _write_json(name, data):
    path = home() / name
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def log(message, level="info", phase=""):
    """One line in log.jsonl. The panel shows the last lines."""
    row = {"ts": time.time(), "level": level, "phase": phase, "message": str(message)[:1500]}
    try:
        home().mkdir(parents=True, exist_ok=True)
        with open(home() / "log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return row


def read_log(limit=80):
    try:
        lines = (home() / "log.jsonl").read_text(encoding="utf-8").splitlines()[-limit:]
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


# ---------- settings ----------
def load_settings():
    s = dict(DEFAULTS)
    s.update({k: v for k, v in _read_json("settings.json", {}).items() if k in DEFAULTS})
    return _clean(s)


def _clean(s):
    out = dict(DEFAULTS)
    for key, default in DEFAULTS.items():
        value = s.get(key, default)
        try:
            if isinstance(default, bool):
                value = value if isinstance(value, bool) else str(value).lower() in ("1", "true", "yes", "on")
            elif isinstance(default, int):
                value = int(float(value))
            elif isinstance(default, float):
                value = float(value)
            else:
                value = re.sub(r"[^\w.:\\/ -]", "", str(value))[:300 if key == "repo" else 60]
        except (TypeError, ValueError):
            value = default
        if key in LIMITS:
            lo, hi = LIMITS[key]
            value = max(lo, min(hi, value))
        out[key] = value
    return out


def save_settings(changes):
    if not isinstance(changes, dict):
        return {"ok": False, "error": "Send a JSON object"}
    with _LOCK:
        s = load_settings()
        s.update({k: v for k, v in changes.items() if k in DEFAULTS})
        s = _clean(s)
        _write_json("settings.json", s)
    return {"ok": True, "settings": s}


# ---------- User activity ----------
def chat_started():
    with _LOCK:
        _ACT["inflight"] += 1
        _ACT["last"] = time.time()


def chat_finished():
    with _LOCK:
        _ACT["inflight"] = max(0, _ACT["inflight"] - 1)
        _ACT["last"] = time.time()


SWARM_STALE_SECONDS = 2 * 3600  # a crashed run can leave rows 'queued' for days (seen 2026-11-18)


def _swarm_busy():
    """True while a /swarm task waits or runs: it uses the GPU. Rows untouched for 2 h are ignored."""
    try:
        import atlas_observability as OPS
        with OPS.LOCK, OPS._db() as c:
            row = c.execute("SELECT COUNT(*) AS n FROM tasks WHERE status IN ('queued','claimed') "
                            "AND task_type LIKE 'swarm_%' AND updated_at > ?",
                            (time.time() - SWARM_STALE_SECONDS,)).fetchone()
        return bool(row and row["n"])
    except Exception:
        return False


def busy_reason(settings, now=None):
    """Plain reason to pause, or "" when the PC is free."""
    now = time.time() if now is None else now
    with _LOCK:
        inflight, last = _ACT["inflight"], _ACT["last"]
    if inflight:
        return "User is chatting (a chat answer is running)."
    idle = settings["idle_minutes"] * 60
    if last and now - last < idle:
        return f"User chatted {int((now - last) // 60)} min ago. I wait until {settings['idle_minutes']} min pass."
    if _swarm_busy():
        return "A /swarm run is using the model (GPU busy)."
    return ""


# ---------- approval gate ----------
def action_tier(name):
    if name in HEADLESS_TIERS:
        return HEADLESS_TIERS[name]
    try:
        from mcp_chat import tool_tier
        tier = tool_tier(name)
    except Exception:
        tier = "consequential"
    return "low" if tier == "read" else tier


def request_action(name, args=None, why=""):
    """Every headless action asks here first. Low risk: True (run it). Anything else: queued for the user, False.
    Never blocks: the night goes on with other work, and the user decides later in the panel."""
    tier = action_tier(name)
    if tier == "low":
        return True
    row = {"id": uuid.uuid4().hex[:12], "action": str(name)[:80], "tier": tier, "created": time.time(),
           "args": _short(args), "why": str(why)[:300], "status": "waiting"}
    with _LOCK:
        queue = _read_json("queue.json", [])
        queue.append(row)
        _write_json("queue.json", queue[-200:])
    log(f"Not run: '{name}' is {tier} risk. It waits for the user in the panel.", "warn")
    return False


def _short(args):
    try:
        text = json.dumps(args, ensure_ascii=False)
    except (TypeError, ValueError):
        text = str(args)
    return text[:400]


def dismiss_queued(qid):
    with _LOCK:
        queue = _read_json("queue.json", [])
        for row in queue:
            if row.get("id") == qid and row.get("status") == "waiting":
                row["status"] = "dismissed"
                _write_json("queue.json", queue)
                return {"ok": True}
    return {"ok": False, "error": "No waiting action with this id"}


# ---------- git (allow-list) ----------
GIT_ALLOWED = {"clone", "rev-parse", "status", "diff", "apply", "add", "commit", "checkout", "stash", "log",
               "format-patch", "remote", "config", "cat-file", "fetch"}
GIT_READ_ONLY = {"rev-parse", "cat-file", "status", "log", "diff"}  # the only ones allowed outside the sandbox


def sandbox():
    return home() / "sandbox"


def _inside(path, folder):
    try:
        Path(path).resolve().relative_to(Path(folder).resolve())
        return True
    except ValueError:
        return False


def _check_git(args, cwd):
    if not args or not isinstance(args[0], str):
        raise SafetyError("git needs a subcommand")
    cmd = args[0]
    if cmd not in GIT_ALLOWED:
        raise SafetyError(f"git {cmd} is not allowed in headless mode")
    if any(a in ("--force", "-f", "-D", "--delete", "--mirror", "--hard") for a in args[1:]):
        raise SafetyError(f"git {cmd} with {args[1:]} is not allowed")
    in_box = _inside(cwd, sandbox())
    if cmd == "clone":
        if len(args) != 4 or args[1] != "--no-hardlinks" or Path(args[3]).resolve() != sandbox().resolve():
            raise SafetyError("git clone only into the sandbox folder")
        return
    if not in_box and cmd not in GIT_READ_ONLY:
        raise SafetyError(f"git {cmd} outside the sandbox is not allowed (the user's repository is read only)")
    if cmd == "checkout" and not (args[1:2] in (["-b"], ["--detach"])):
        raise SafetyError("git checkout only with -b (a new branch) or --detach")
    if cmd == "checkout" and args[1] == "-b" and not (len(args) > 2 and args[2].startswith("atlas-auto/")):
        raise SafetyError("new branches must be named atlas-auto/...")
    if cmd == "stash" and args[1:2] != ["push"]:
        raise SafetyError("git stash only with push (nothing is dropped)")
    if cmd == "remote" and args[1:3] != ["set-url", "--push"]:
        raise SafetyError("git remote only with set-url --push")
    if cmd == "fetch" and args[1:] != ["--no-tags", "origin"]:
        raise SafetyError("git fetch only from origin (the user's local folder)")
    if cmd == "commit" and "--no-verify" not in args:
        raise SafetyError("git commit must use --no-verify (no hooks run)")


def _git(args, cwd, check=True, timeout=300):
    args = [str(a) for a in args]
    _check_git(args, cwd)
    run = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
                         errors="replace", timeout=timeout, shell=False)
    if check and run.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed: {(run.stderr or run.stdout).strip()[:400]}")
    return run


def find_repo(settings):
    """The user's repository: settings "repo", then ATLAS_DEV_REPO, then a folder above the app with the desktop app."""
    for cand in (settings.get("repo"), os.environ.get("ATLAS_DEV_REPO")):
        if cand:
            return Path(cand)
    p = HERE
    for _ in range(6):
        p = p.parent
        if (p / ".git").exists() and (p / APP_MARK).is_file():
            return p
    return None


def plain_path(p):
    r"""Drop the Windows long-path prefix. An installed app path can start with \\?\D:\..., and git clone reads that as a host."""
    s = str(p)
    if s.startswith("\\\\?\\UNC\\"):
        s = "\\\\" + s[8:]
    elif s.startswith("\\\\?\\"):
        s = s[4:]
    return Path(s)


def prepare_sandbox(repo):
    """Clone (first night) or fetch the user's repo into the sandbox, then go to his HEAD commit. Returns the base sha."""
    repo = plain_path(repo)
    if not (repo / ".git").exists():
        raise _Halt(f"{repo} is not a git repository. Set the repository folder in the panel.")
    base = _git(["rev-parse", "HEAD"], repo).stdout.strip()
    if _git(["cat-file", "-e", f"{base}:{APP_MARK}"], repo, check=False).returncode != 0:
        raise _Halt(f"The commit the user's folder is on ({base[:8]}) is an OLD Atlas (no {APP_MARK}). I do not work on it.")
    box = sandbox()
    box.parent.mkdir(parents=True, exist_ok=True)
    if not (box / ".git").exists():
        log(f"First night: copying the repository into {box} (a separate clone).", phase="plan")
        _git(["clone", "--no-hardlinks", str(repo), str(plain_path(box))], box.parent, timeout=1800)
    else:
        _git(["fetch", "--no-tags", "origin"], box, timeout=600)
    _git(["remote", "set-url", "--push", "origin", NO_PUSH_URL], box)
    _git(["config", "user.name", "Atlas Night Dev"], box)
    _git(["config", "user.email", "atlas-night-dev@localhost"], box)
    _clean_tree("leftovers before a new night")
    _git(["checkout", "--detach", base], box)
    return base


def _clean_tree(why):
    """Put any change aside with git stash (nothing is deleted). True when something was stashed."""
    box = sandbox()
    if _git(["status", "--porcelain"], box).stdout.strip():
        _git(["stash", "push", "-u", "-m", f"atlas-auto: {why}"[:120]], box)
        return True
    return False


# ---------- edits ----------
EDIT_RE = re.compile(r"FILE:\s*`?([^\s`]+)`?\s*\n<{5,9} ?SEARCH[^\n]*\n(.*?)\n?={5,9}[^\n]*\n(.*?)\n?>{5,9} ?REPLACE",
                     re.S)


def parse_edits(text):
    """[(path, search, replace)] from SEARCH/REPLACE blocks. Code fence lines are ignored."""
    clean = "\n".join(line for line in str(text or "").splitlines() if not re.match(r"^\s*```[\w+-]*\s*$", line))
    return [(m.group(1).strip(), m.group(2), m.group(3)) for m in EDIT_RE.finditer(clean)]


def check_path(rel, root):
    """Safe relative path inside ALLOWED_DIRS, or SafetyError."""
    rel = str(rel).replace("\\", "/").strip()
    if not rel or rel.startswith("/") or re.match(r"^[A-Za-z]:", rel) or ".." in rel.split("/"):
        raise SafetyError(f"{rel!r}: only relative paths inside the repository")
    if any(part.startswith(".git") for part in rel.split("/")):
        raise SafetyError(f"{rel}: .git files are never changed")
    if not rel.startswith(ALLOWED_DIRS):
        raise SafetyError(f"{rel}: only files under {', '.join(ALLOWED_DIRS)} may change")
    full = Path(root) / rel
    if not _inside(full, root):
        raise SafetyError(f"{rel}: leaves the repository")
    name = full.name
    if full.exists() and (name.startswith("test_") or name.startswith("e2e_")):
        raise SafetyError(f"{rel}: existing tests are read only (a new test file is fine)")
    return rel, full


def plan_edits(edits, root):
    """Check all edits and return {rel: (full_path, new_text)} without writing anything. Raises SafetyError/ValueError."""
    if not edits:
        raise ValueError("no FILE / SEARCH / REPLACE block was found")
    result, changed = {}, 0
    for rel, search, replace in edits:
        rel, full = check_path(rel, root)
        if rel in result:
            old = result[rel][1]
        elif full.exists():
            old = full.read_text(encoding="utf-8")
        else:
            old = None
        if old is None:
            if search.strip():
                raise ValueError(f"{rel} does not exist, so SEARCH must be empty to create it")
            new = replace if replace.endswith("\n") else replace + "\n"
        else:
            if not search.strip():
                raise ValueError(f"{rel} exists: SEARCH must hold lines copied exactly from it")
            hits = old.count(search)
            if hits != 1:
                raise ValueError(f"{rel}: the SEARCH text is found {hits} times, it must be found exactly once")
            new = old.replace(search, replace, 1)
        if not new.strip():
            raise SafetyError(f"{rel}: an edit may not empty or delete a file")
        result[rel] = (full, new, result[rel][2] if rel in result else old)
    if len(result) > MAX_EDIT_FILES:
        raise SafetyError(f"{len(result)} files changed, at most {MAX_EDIT_FILES} per cycle")
    for rel, (_full, new, old) in result.items():
        diff = difflib.unified_diff((old or "").splitlines(), new.splitlines(), lineterm="", n=0)
        changed += sum(1 for d in diff if d[:1] in "+-" and not d.startswith(("+++", "---")))
    if changed > MAX_EDIT_LINES:
        raise SafetyError(f"{changed} lines changed, at most {MAX_EDIT_LINES} per cycle")
    return {rel: (full, new) for rel, (full, new, _old) in result.items()}


def apply_edits(text, root):
    """Check, ask the gate, then write. Returns the changed paths. Writes nothing when any edit is bad."""
    planned = plan_edits(parse_edits(text), root)
    if not request_action("sandbox_edit", {"files": sorted(planned)}, "small patch in the sandbox"):
        raise SafetyError("the edit was not allowed")
    if not _inside(root, sandbox()):
        raise SafetyError("edits only inside the sandbox")
    for rel, (full, new) in planned.items():
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(new, encoding="utf-8")
    return sorted(planned)


# ---------- tests (fixed commands only) ----------
def run_fixed_tests(root):
    """Run FIXED_TESTS in the sandbox with a throwaway data folder. Returns {"passed": bool, "steps": [...]}."""
    if not request_action("run_fixed_tests", {"root": str(root)}):
        raise SafetyError("tests were not allowed")
    if not _inside(root, sandbox()):
        raise SafetyError("tests only run inside the sandbox")
    steps = []
    with tempfile.TemporaryDirectory(prefix="atlas-night-test-") as tmp:
        env = dict(os.environ, ATLAS_DATA_DIR=tmp, ATLAS_OBSERVABILITY_DB=str(Path(tmp) / "obs.sqlite3"),
                   PYTHONDONTWRITEBYTECODE="1", ATLAS_WRITE_APPROVAL="ask")
        env.pop("ATLAS_DEV_REPO", None)
        for label, folder, args in FIXED_TESTS:
            started = time.time()
            try:
                p = subprocess.run([sys.executable, *args], cwd=str(Path(root) / folder), capture_output=True,
                                   text=True, errors="replace", timeout=TEST_TIMEOUT, shell=False, env=env)
                ok, out = p.returncode == 0, (p.stdout + "\n" + p.stderr).strip()
            except (subprocess.TimeoutExpired, OSError) as exc:
                ok, out = False, f"Could not finish: {exc}"
            steps.append({"name": label, "passed": ok, "seconds": round(time.time() - started, 1), "tail": out[-1500:]})
    return {"passed": all(s["passed"] for s in steps), "steps": steps}


def tests_text(result):
    return "\n".join(f"- {s['name']}: {'PASSED' if s['passed'] else 'FAILED'} ({s['seconds']} s)" for s in result["steps"])


# ---------- backlog ----------
SKIP_DOCS = re.compile(r"EVIDENCE|INVESTOR|PITCH", re.I)
STARTERS = [
    ("Add a test: dev_cycle.submit_feedback refuses a missing cycle_id",
     "New file atlas-rust-desktop/validation-tests/test_dev_cycle_feedback.py. Point dev_cycle.STATE_FILE at a temp folder."),
    ("Add a test: mcp_chat.summarize_args hides secret keys and cuts long values",
     "New file atlas-rust-desktop/validation-tests/test_summarize_args.py. Keys like api_key, token, password must show [hidden]."),
    ("Add a test: swarm_pipeline refuses absolute and '..' file paths",
     "New file atlas-rust-desktop/validation-tests/test_pipeline_paths.py. Use swarm_pipeline._safe_rel."),
]


def _item(title, detail, source):
    title = " ".join(str(title).split())[:200]
    return {"id": uuid.uuid5(uuid.NAMESPACE_URL, title.lower()).hex[:10], "title": title, "detail": str(detail)[:1000],
            "source": str(source)[:200], "status": "open", "attempts": 0, "added": time.time()}


def seed_items(repo):
    """Open work found in the user's repo (read only): - [ ] and TODO lines in docs/*.md, # TODO comments in the app."""
    items = [_item(t, d, "built-in starter") for t, d in STARTERS]
    repo = Path(repo) if repo else None
    if repo and repo.is_dir():
        for doc in sorted((repo / "docs").glob("*.md")):
            if SKIP_DOCS.search(doc.name):
                continue
            try:
                lines = doc.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for n, line in enumerate(lines, 1):
                m = re.match(r"^\s*[-*] \[ \]\s+(.+)$", line) or re.search(r"\bTODO[:\s]+(.{8,})$", line)
                if m:
                    items.append(_item(m.group(1), "", f"docs/{doc.name}:{n}"))
        for py in sorted((repo / APP_DIR).glob("*.py")):
            try:
                lines = py.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for n, line in enumerate(lines, 1):
                m = re.search(r"#\s*TODO[:\s]+(.{8,})$", line)
                if m:
                    items.append(_item(f"{py.name}: {m.group(1)}", "", f"{APP_DIR}/{py.name}:{n}"))
    return items


def backlog(repo=None, reseed=False):
    with _LOCK:
        items = _read_json("backlog.json", [])
        if not items or reseed:
            have = {i.get("id") for i in items}
            items += [i for i in seed_items(repo) if i["id"] not in have][:200]
            _write_json("backlog.json", items)
        return items


def add_item(title, detail=""):
    if not str(title or "").strip():
        return {"ok": False, "error": "A title is needed"}
    with _LOCK:
        items = _read_json("backlog.json", [])
        item = _item(title, detail, "added by the user")
        if any(i.get("id") == item["id"] for i in items):
            return {"ok": False, "error": "This item is already in the backlog"}
        items.insert(0, item)
        _write_json("backlog.json", items)
    return {"ok": True, "item": item}


def set_item(item_id, status):
    if status not in ("open", "skipped"):
        return {"ok": False, "error": "status must be open or skipped"}
    with _LOCK:
        items = _read_json("backlog.json", [])
        for i in items:
            if i.get("id") == item_id and i.get("status") != "in_progress":
                i["status"] = status
                if status == "open":
                    i["attempts"] = 0
                _write_json("backlog.json", items)
                return {"ok": True, "item": i}
    return {"ok": False, "error": "No such item, or it is in progress"}


def _update_item(item_id, **fields):
    with _LOCK:
        items = _read_json("backlog.json", [])
        for i in items:
            if i.get("id") == item_id:
                i.update(fields)
        _write_json("backlog.json", items)


def _next_item():
    for i in _read_json("backlog.json", []):
        if i.get("status") == "open" and int(i.get("attempts", 0)) < 2:
            return i
    return None


# ---------- state ----------
def _state():
    return _read_json("state.json", {"mode": "off"})


def _set_state(**fields):
    with _LOCK:
        s = _state()
        s.update(fields)
        s["updated"] = time.time()
        _write_json("state.json", s)
        return s


def status():
    with _LOCK:
        s = _state()
        alive = _THREAD is not None and _THREAD.is_alive()
        if s.get("mode") in ("starting", "running", "paused", "stopping") and not alive:
            s = _set_state(mode="off", phase="", stopped_reason=s.get("stopped_reason") or "Atlas restarted, so the mode stopped.")
        settings = load_settings()
        repo = find_repo(settings)
        return {"ok": True, "state": s, "settings": settings, "repo": str(repo or ""),
                "busy": busy_reason(settings), "phases": list(PHASES), "backlog": _read_json("backlog.json", [])[:100],
                "packages": list_packages(), "queue": [q for q in _read_json("queue.json", []) if q.get("status") == "waiting"],
                "log": read_log(80)}


# ---------- the night ----------
class Night:
    """One start of the mode. Holds the budget counters. call_llm and run_tests can be stubbed in tests."""

    def __init__(self, settings, call_llm=None, sleep=time.sleep, clock=time.time):
        self.s, self.sleep, self.clock = settings, sleep, clock
        self.call_llm = call_llm
        self.cycles = self.failures = self.tokens = 0
        self.spend = 0.0
        self.work_seconds = 0.0
        self.cycle = None
        self._mark = clock()

    # -- budget and pause --
    def _tick(self):
        now = self.clock()
        self.work_seconds += max(0.0, now - self._mark)
        if self.cycle:
            self.cycle["seconds"] += max(0.0, now - self._mark)
        self._mark = now

    def budget_reason(self):
        s = self.s
        if self.cycles >= s["max_cycles"]:
            return f"Night budget used: {self.cycles} of {s['max_cycles']} cycles."
        if self.work_seconds >= s["night_minutes"] * 60:
            return f"Night budget used: {s['night_minutes']} working minutes."
        if self.tokens >= s["night_tokens"]:
            return f"Night budget used: {self.tokens} of {s['night_tokens']} tokens."
        if self.failures >= s["max_failures"]:
            return f"{self.failures} cycles failed in a row, so I stopped."
        return ""

    def checkpoint(self, phase=""):
        """Before each phase and model call: stop, budget, pause while the user uses the PC."""
        self._tick()
        if _STOP.is_set():
            raise _Halt("Stopped by the user.")
        if self.cycle:
            if self.cycle["seconds"] >= self.s["cycle_minutes"] * 60:
                raise TimeoutError(f"the cycle used its {self.s['cycle_minutes']} minutes")
            if self.cycle["tokens"] >= self.s["cycle_tokens"]:
                raise TimeoutError(f"the cycle used its {self.s['cycle_tokens']} tokens")
        reason = self.budget_reason()
        if reason:
            raise _Halt(reason)
        paused = False
        while True:
            why = busy_reason(self.s)
            if not why:
                break
            if not paused:
                paused = True
                log(f"Paused: {why}", "info", phase)
                _set_state(mode="paused", pause_reason=why)
            self.sleep(30)
            self._mark = self.clock()  # paused time does not count
            if _STOP.is_set():
                raise _Halt("Stopped by the user.")
        if paused:
            log("The PC is free again. I go on.", "info", phase)
            _set_state(mode="running", pause_reason="")

    def phase(self, name):
        self.checkpoint(name)
        self.cycle["phase"] = name
        _set_state(mode="running", phase=name, cycle=self.cycle, counters=self.counters())

    def counters(self):
        return {"cycles": self.cycles, "failures": self.failures, "tokens": self.tokens,
                "minutes": round(self.work_seconds / 60, 1), "spend_usd": round(self.spend, 4)}

    # -- model calls --
    def ask(self, phase, prompt, model, max_tokens):
        self.checkpoint(phase)
        left = min(self.s["cycle_tokens"] - self.cycle["tokens"], self.s["night_tokens"] - self.tokens)
        limit = max(200, min(max_tokens, left))
        conv = f"headless-{self.cycle['id']}"
        import swarm_run
        swarm_run.live_begin(conv, phase, "pc", "This PC", model)
        try:
            with swarm_run._machine_lock(""):  # one model at a time, shared with /swarm
                text = swarm_run._ask_local(self.call_llm, prompt, model, local_only=True, limit=limit, live=(conv, phase))
        except Exception as exc:
            swarm_run.live_end(conv, phase, "", str(exc))
            raise
        swarm_run.live_end(conv, phase, text)
        used = len(text) // 4 + len(prompt) // 40 + 1  # output tokens (chars/4), plus prompt reading at ~1/10 cost
        self.cycle["tokens"] += used
        self.tokens += used
        return text

    def ask_review(self, prompt):
        """Review: cloud only when the user turned it on and the spend limit allows. Else the review_model alias."""
        s = self.s
        if s["cloud_enabled"] and s["cloud_spend_limit_usd"] > 0:
            cost = (len(prompt) / 4 + 1500) / 1e6 * s["cloud_usd_per_mtok"]
            try:
                import cloud_llm
                if cloud_llm.available("deepseek") and self.spend + cost <= s["cloud_spend_limit_usd"]:
                    if request_action("cloud_review", {"provider": "deepseek"}):
                        text = cloud_llm.call("deepseek", prompt, temperature=0.2, max_tokens=1500)
                        self.spend += cost
                        return text, "cloud (DeepSeek)"
                elif self.spend + cost > s["cloud_spend_limit_usd"]:
                    log("Cloud spend limit reached. The review uses the local model.", "warn", "review")
            except Exception as exc:
                log(f"Cloud review did not work ({str(exc)[:150]}). Local model instead.", "warn", "review")
        return self.ask("review", prompt, s["review_model"], 1500), f"local model ({s['review_model']})"

    # -- one cycle --
    def run_cycle(self, base, item):
        box = sandbox()
        self.cycle = {"id": uuid.uuid4().hex[:8], "item": item, "phase": "", "seconds": 0.0, "tokens": 0,
                      "started": self.clock(), "branch": ""}
        _clean_tree("leftovers before a cycle")
        _git(["checkout", "--detach", base], box)
        _update_item(item["id"], status="in_progress", attempts=int(item.get("attempts", 0)) + 1)
        log(f"Cycle {self.cycles + 1}: {item['title']}", "info", "plan")
        changed = []
        try:
            # 1 plan
            self.phase("plan")
            plan = self.ask("plan", plan_prompt(item, _file_list(box)), self.s["plan_model"], 600)
            files = parse_plan_files(plan, box)
            log(f"Plan: {' '.join(plan.split())[:400]}", "info", "plan")
            # 2 analyse (read only)
            self.phase("analyse")
            request_action("sandbox_read", {"files": files})
            context = read_context(box, files, item["title"] + " " + item.get("detail", ""))
            log(f"Read {len(files)} file(s): {', '.join(files) or 'none named'}", "info", "analyse")
            # 3 build
            self.phase("build")
            error = ""
            for attempt in (1, 2):
                reply = self.ask("build", build_prompt(item, plan, context, error), self.s["build_model"], 3000)
                try:
                    changed = apply_edits(reply, box)
                    break
                except (ValueError, SafetyError) as exc:
                    error = str(exc)
                    log(f"Patch {attempt} refused: {error}", "warn", "build")
            if not changed:
                raise ValueError(f"no usable patch ({error})")
            log(f"Patch applied to: {', '.join(changed)}", "info", "build")
            # 4 test
            self.phase("test")
            tests = run_fixed_tests(box)
            log("Tests:\n" + tests_text(tests), "info" if tests["passed"] else "warn", "test")
            if not tests["passed"]:
                raise ValueError("tests failed:\n" + tests_text(tests))
            diff = _git(["diff", "--", *changed], box).stdout + _new_files_diff(box, changed)
            # 5 review
            self.phase("review")
            review, reviewer = self.ask_review(review_prompt(item, plan, diff, tests_text(tests)))
            verdict = "REJECT" if re.search(r"VERDICT:\s*REJECT", review or "", re.I) else (
                "KEEP" if re.search(r"VERDICT:\s*KEEP", review or "", re.I) else "UNCLEAR")
            log(f"Review by {reviewer}: {verdict}", "info" if verdict == "KEEP" else "warn", "review")
            # 6 document + 7 hand off
            self.phase("document")
            pkg = make_package(self, base, item, plan, changed, diff, tests, review, reviewer, verdict)
            self.phase("handoff")
            log(f"Package {pkg['id']} is ready for the user (branch {pkg['branch']}).", "info", "handoff")
            _update_item(item["id"], status="review")
            self.failures = 0
            return pkg
        except _Halt:
            _clean_tree(f"stopped during {item['title'][:60]}")
            _update_item(item["id"], status="open")
            raise
        except Exception as exc:
            self.failures += 1
            stashed = _clean_tree(f"failed: {item['title'][:60]}")
            tries = int(item.get("attempts", 0)) + 1
            _update_item(item["id"], status="failed" if tries >= 2 else "open", last_error=str(exc)[:500])
            log(f"Cycle failed: {str(exc)[:600]}" + (" The change is kept aside with git stash." if stashed else ""),
                "warn", self.cycle.get("phase", ""))
            return None
        finally:
            self.cycles += 1
            self.cycle = None
            _set_state(cycle=None, phase="", counters=self.counters())


# ---------- prompts ----------
def _file_list(box):
    out = []
    for d in ALLOWED_DIRS:
        folder = box / d
        if folder.is_dir():
            out += [f"{d}{p.name}" for p in sorted(folder.iterdir()) if p.is_file() and p.suffix in (".py", ".html", ".js", ".md", ".mjs", ".cjs")]
    return out[:250]


def plan_prompt(item, files):
    return ("You improve the Atlas Chat app with ONE small, safe change.\n"
            f"TASK: {item['title']}\n{item.get('detail', '')}\n\n"
            "Files you may change or add (other files are read only):\n" + "\n".join(files) + "\n\n"
            "Answer in this form, nothing else:\nFILES: <1 to 3 paths from the list, or a new path in the same folders>\n"
            "PLAN: <3 to 5 short lines: what to change and why>\nRISK: <one line>")


def parse_plan_files(plan, box):
    """Up to 3 paths from the FILES: line. A path may be read when it is safe to change, or when it is an
    existing file in ALLOWED_DIRS (an existing test is read for context, never changed)."""
    m = re.search(r"FILES:\s*(.+)", plan or "")
    out = []
    for raw in re.split(r"[,\s]+", m.group(1) if m else ""):
        rel = raw.strip("`'\" ").replace("\\", "/")
        if not rel or rel in out:
            continue
        try:
            check_path(rel, box)
        except SafetyError:
            if not (rel.startswith(ALLOWED_DIRS) and ".." not in rel.split("/") and (box / rel).is_file()):
                continue
        out.append(rel)
    return out[:3]


def read_context(box, files, words, budget=9000):
    """Text of the planned files: whole when small, else a window around the task words."""
    parts, left = [], budget
    for rel in files:
        full = box / rel
        if not full.is_file():
            parts.append(f"--- {rel} (new file) ---")
            continue
        text = full.read_text(encoding="utf-8", errors="replace")
        if len(text) > left:
            hits = [text.lower().find(w) for w in re.findall(r"[a-z_]{5,}", words.lower())]
            hits = [h for h in hits if h >= 0]
            start = text.rfind("\n", 0, max(0, min(hits) - 500)) + 1 if hits else 0
            text = text[start:start + max(800, left // max(1, len(files)))] + "\n... (cut)"
        parts.append(f"--- {rel} ---\n{text}")
        left -= len(text)
        if left <= 0:
            break
    return "\n".join(parts)


def build_prompt(item, plan, context, error=""):
    again = f"\nYOUR LAST PATCH WAS REFUSED: {error}\nFix that and answer again.\n" if error else ""
    return ("You write ONE small patch for the Atlas Chat app. Follow the plan. Keep the change small and tested.\n"
            f"TASK: {item['title']}\n{item.get('detail', '')}\nPLAN:\n{plan}\n{again}\n"
            "Rules: at most 3 files and 200 changed lines. Do not change existing test files; add a new test file instead. "
            "Do not delete files. Standard library only.\n"
            "Answer ONLY with blocks like this (SEARCH must be copied exactly from the file and found once; "
            "an empty SEARCH creates a NEW file):\n"
            "FILE: path/from/the/repo.py\n<<<<<<< SEARCH\nexact old lines\n=======\nnew lines\n>>>>>>> REPLACE\n\n"
            f"FILES:\n{context}")


def review_prompt(item, plan, diff, tests):
    return ("You review a small patch for the Atlas Chat app before a person sees it. Be strict and short.\n"
            f"TASK: {item['title']}\nPLAN:\n{plan}\nTESTS:\n{tests}\nDIFF:\n{diff[:8000]}\n\n"
            "Check: does it do the task, is it correct, could it break something, is it small. "
            "Answer in 3 to 8 short lines, then a last line: VERDICT: KEEP or VERDICT: REJECT")


def _new_files_diff(box, changed):
    """git diff misses untracked files: show new files as added text."""
    out = []
    tracked = set(_git(["diff", "--name-only", "--", *changed], box).stdout.split())
    for rel in changed:
        if rel not in tracked and (box / rel).is_file():
            body = (box / rel).read_text(encoding="utf-8", errors="replace")
            out.append(f"\n--- /dev/null\n+++ b/{rel}\n" + "\n".join("+" + line for line in body.splitlines()))
    return "".join(out)


# ---------- packages ----------
def _risks(changed, verdict, tests):
    risks = []
    if any(c.endswith("index.html") for c in changed):
        risks.append("index.html changed: check on the PC that the chat page never scrolls (CLAUDE.md section 8) "
                     "and that keyboard focus still shows.")
    if any(c.endswith("server.py") for c in changed):
        risks.append("server.py changed: start the app once and send one chat before you approve.")
    if verdict != "KEEP":
        risks.append(f"The local reviewer said {verdict}. Read its notes.")
    risks.append("Tested in the headless sandbox only, not in the installed app and not on the PC screen.")
    return risks


def make_package(night, base, item, plan, changed, diff, tests, review, reviewer, verdict):
    box = sandbox()
    st = _state()
    day = time.strftime("%Y%m%d", time.localtime(night.clock()))
    seq = int(st.get("seq", {}).get(day, 0)) + 1
    branch = f"atlas-auto/{day}-{seq}"
    _set_state(seq={day: seq})
    _git(["checkout", "-b", branch], box)
    _git(["add", "--", *changed], box)
    _git(["commit", "--no-verify", "-m", f"Night dev: {item['title'][:60]}\n\nMade by Atlas headless dev mode. "
          f"Base {base[:12]}. Not reviewed by the user yet."], box)
    patch = _git(["format-patch", "-1", "--stdout"], box).stdout
    sha = _git(["rev-parse", "HEAD"], box).stdout.strip()
    _git(["checkout", "--detach", base], box)
    pid = f"{day}-{seq}"
    folder = home() / "packages" / pid
    folder.mkdir(parents=True, exist_ok=True)
    risks = _risks(changed, verdict, tests)
    report = (f"# Night dev package {pid}\n\n"
              f"- Item: {item['title']}\n- Source: {item.get('source', '')}\n- Branch (sandbox only): `{branch}` at `{sha[:12]}`\n"
              f"- Base commit: `{base[:12]}`\n- Files: {', '.join(changed)}\n- Review: {verdict} by {reviewer}\n\n"
              f"## What and why\n\n{plan.strip()}\n\n## Test results (fixed tests, sandbox)\n\n{tests_text(tests)}\n\n"
              f"## Review\n\n{(review or '(no review text)').strip()}\n\n## Risks\n\n" + "\n".join(f"- {r}" for r in risks) +
              "\n\n## How to use it\n\nNothing is merged. Approve only marks it. To bring it in, give "
              "`send-to-claude.md` to a Claude Code session, or apply `change.patch` on a new branch yourself.\n")
    claude = (f"# Task for Claude Code: review and land a night-dev patch\n\n"
              "Read CLAUDE.md first and follow it exactly.\n\n"
              f"Atlas headless dev mode made this patch on base commit `{base}` (the user's branch at that time).\n"
              f"Task item: {item['title']}\n\n"
              "1. Create your own branch from the user's newest app branch (CLAUDE.md section 2).\n"
              "2. Apply the patch below with `git apply`. If it does not apply, redo the change by hand, smaller.\n"
              "3. Review it for correctness and for CLAUDE.md sections 6 and 8. Fix or drop what is wrong.\n"
              "4. Run all tests from CLAUDE.md section 5 and report plainly what passes and fails.\n"
              "5. Push only to your own branch. Give the user `python get_update.py <your branch>` with checks first.\n\n"
              f"## Report from Atlas\n\n{report}\n\n## Patch\n\n```diff\n{patch}\n```\n")
    (folder / "change.patch").write_text(patch, encoding="utf-8")
    (folder / "report.md").write_text(report, encoding="utf-8")
    (folder / "send-to-claude.md").write_text(claude, encoding="utf-8")
    meta = {"id": pid, "item_id": item["id"], "title": item["title"], "branch": branch, "commit": sha, "base": base,
            "files": changed, "tests_passed": tests["passed"], "verdict": verdict, "reviewer": reviewer,
            "risks": risks, "status": "ready", "created": time.time(), "folder": str(folder)}
    (folder / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def list_packages():
    root = home() / "packages"
    out = []
    if root.is_dir():
        for meta in sorted(root.glob("*/meta.json"), reverse=True):
            try:
                out.append(json.loads(meta.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                pass
    return out[:50]


def package_text(pid, which):
    if not re.fullmatch(r"[0-9]{8}-[0-9]{1,4}", str(pid or "")):
        return None
    name = {"report": "report.md", "claude": "send-to-claude.md", "patch": "change.patch"}.get(which)
    try:
        return (home() / "packages" / pid / name).read_text(encoding="utf-8") if name else None
    except OSError:
        return None


def decide_package(pid, decision, note=""):
    """User's yes or no. Approve only marks the package; it never merges, applies or pushes."""
    if decision not in ("approve", "reject"):
        return {"ok": False, "error": "decision must be approve or reject"}
    if not re.fullmatch(r"[0-9]{8}-[0-9]{1,4}", str(pid or "")):
        return {"ok": False, "error": "bad package id"}
    path = home() / "packages" / pid / "meta.json"
    with _LOCK:
        try:
            meta = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"ok": False, "error": "No such package"}
        if meta.get("status") != "ready":
            return {"ok": False, "error": f"Already {meta.get('status')}"}
        meta.update(status="approved" if decision == "approve" else "rejected", decided=time.time(), note=str(note)[:1000])
        path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        items = _read_json("backlog.json", [])
        for i in items:
            if i.get("id") == meta.get("item_id"):
                i["status"] = "done" if decision == "approve" else ("open" if int(i.get("attempts", 0)) < 2 else "failed")
        _write_json("backlog.json", items)
    log(f"User {'approved' if decision == 'approve' else 'rejected'} package {pid}.", "info", "handoff")
    return {"ok": True, "package": meta}


# ---------- start / stop ----------
def _night_main(night):
    try:
        repo = find_repo(night.s)
        if not repo:
            raise _Halt("I cannot find the Atlas repository. Set the repository folder in the panel.")
        backlog(repo)
        _set_state(mode="running", phase="plan", repo=str(repo))
        night.checkpoint("plan")
        base = prepare_sandbox(repo)
        _set_state(base=base)
        log(f"Sandbox ready on user's commit {base[:8]}. Checking that the tests pass before any change.", "info", "test")
        first = run_fixed_tests(sandbox())
        if not first["passed"]:
            raise _Halt("Tests fail before any change, so I cannot tell good patches from bad. " + tests_text(first))
        while True:
            night.checkpoint()
            item = _next_item()
            if not item:
                raise _Halt("The backlog has no open items.")
            night.run_cycle(base, item)
    except _Halt as stop:
        reason = str(stop)
    except Exception as exc:  # never leave the mode half on
        reason = f"Atlas hit an error and stopped: {str(exc)[:300]}"
    log(f"Night dev stopped. {reason}", "info")
    _set_state(mode="off", phase="", cycle=None, stopped_reason=reason, counters=night.counters(), finished=time.time())


def start(call_llm=None, sleep=time.sleep):
    global _THREAD
    with _LOCK:
        if _THREAD is not None and _THREAD.is_alive():
            return {"ok": False, "error": "Night dev is already on."}
        settings = load_settings()
        if call_llm is None:
            import llm
            call_llm = llm.call_llm
        _STOP.clear()
        night = Night(settings, call_llm=call_llm, sleep=sleep)
        _set_state(mode="starting", phase="", started=time.time(), stopped_reason="", pause_reason="",
                   counters=night.counters(), cycle=None)
        log("Night dev started.", "info")
        _THREAD = threading.Thread(target=_night_main, args=(night,), name="atlas-night-dev", daemon=True)
        _THREAD.start()
    return {"ok": True}


def stop():
    _STOP.set()
    with _LOCK:
        if _THREAD is not None and _THREAD.is_alive():
            _set_state(mode="stopping")
            log("Stop asked. I stop after the current step.", "info")
            return {"ok": True, "stopping": True}
    return {"ok": True, "stopping": False}
