"""Helpers for the /swarm cloud pipeline: plan, combine, test, review.

Pure functions only (no database, no network). swarm_run.py calls them.
Flow: Gemini plans -> local bots do one portion each -> Gemini combines ->
tests run on any code -> DeepSeek reviews. Every cloud step falls back to the local model.
"""
from __future__ import annotations
import importlib.util
import json
import os
import re
import tempfile
from pathlib import Path

MAX_FILES = 20
MAX_FILE_CHARS = 60000
MAX_PORTION_CHARS = 1500
MAX_ANSWER_CHARS = 3500   # how much of each bot answer the combiner reads
HERE = Path(__file__).resolve().parent


def tests_enabled():
    return os.environ.get("ATLAS_SWARM_RUN_TESTS", "1").strip().lower() not in ("0", "false", "no", "off")


# ---------- stage 1: plan ----------
def plan_prompt(goal, bots):
    names = "\n".join(f"- {b}" for b in bots)
    return ("You lead a small software team. Split the goal into ONE separate portion of work for each team member. "
            "Portions must not overlap. Each portion must be short, concrete and stand alone.\n"
            f"GOAL: {goal}\nTEAM:\n{names}\n"
            'Return JSON only, no other text: [{"bot": "<exact team name>", "portion": "<their one job>"}]')


def _norm(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _match_bot(name, bots):
    """The exact bot, or the one bot whose name ends the same way ("SDE" matches "10x: SDE")."""
    n = _norm(name)
    if not n:
        return None
    for b in bots:
        if _norm(b) == n:
            return b
    hits = [b for b in bots if _norm(b).endswith(n) or n.endswith(_norm(b))]
    return hits[0] if len(hits) == 1 else None


def parse_plan(text, bots):
    """Return {bot_name: portion} for known bots only. Raises ValueError when nothing usable is found."""
    raw = (text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I)
    start, end = raw.find("["), raw.rfind("]")
    if start < 0 or end <= start:
        raise ValueError("the plan is not a JSON list")
    try:
        items = json.loads(raw[start:end + 1])
    except ValueError as exc:
        raise ValueError("the plan is not valid JSON") from exc
    out = {}
    for it in items if isinstance(items, list) else []:
        if not isinstance(it, dict):
            continue
        name = _match_bot(it.get("bot") or it.get("name") or it.get("agent") or it.get("role"), bots)
        portion = str(it.get("portion") or it.get("job") or it.get("task") or it.get("work") or "").strip()
        if name and portion and name not in out:
            out[name] = portion[:MAX_PORTION_CHARS]
    if not out:
        raise ValueError("the plan names no known bot")
    return out


# ---------- stage 3: combine ----------
def combine_prompt(goal, answers, repo=""):
    parts = "\n\n".join(f"### {bot}\n{(a or '(no answer)')[:MAX_ANSWER_CHARS]}" for bot, a in answers)
    repo_part = (f"\n\nTHE REAL PROJECT (use its file names and paths; change existing files instead of inventing new ones):\n{repo}"
                 "\n\nRULES FOR THE REAL PROJECT: Write FILE paths exactly as they are in the file list above. "
                 "Only a test_*.py file may be new; for any other new file, say why the existing files cannot do the job. "
                 "Keep the tools the project already uses (for example its installer tool). Do not name one tool and write code for another."
                 if repo else "")
    return ("Combine the team answers below into ONE result for the goal. Remove repeats. Fix conflicts. "
            "Write plain English headings. If the result has code, give EVERY file as its own code block, "
            "and write the line `FILE: relative/path.ext` directly above each block. Put tests in files named test_*.py "
            "so they can run with python unittest. Use relative paths only. The code runs on Windows with Python 3. "
            + package_hint() +
            " Use pathlib, and write paths with .as_posix() when a test compares them.\n"
            f"GOAL: {goal}{repo_part}\n\nTEAM ANSWERS:\n{parts}")


def _installed_version(name):
    try:
        from importlib import metadata
        return metadata.version(name)
    except Exception:
        return None


def package_hint(version_of=_installed_version):
    """Tell the combiner which packages the test Python really has.

    The tests run with Atlas's own Python. It has mcp 2.x, where FastMCP was renamed,
    so code written for mcp 1.x fails at import (seen 2026-11-11).
    """
    base = ("Use ONLY the standard library, except the packages named here. Do not import pytest or requests. "
            "Never import a third-party package in a module that a test imports: put that import only in the "
            "entry file (for example server.py) and keep the logic in plain modules, so the tests still run.")
    ver = version_of("mcp")
    if not ver:
        return base + " The mcp package is NOT installed: do not import mcp."
    major = ver.split(".", 1)[0]
    if major.isdigit() and int(major) >= 2:
        return (base + f" mcp {ver} is installed. This is mcp 2.x: write `from mcp.server.mcpserver import MCPServer`. "
                "`mcp.server.fastmcp` and `FastMCP` do NOT exist in mcp 2.x.")
    return base + f" mcp {ver} is installed (1.x): write `from mcp.server.fastmcp import FastMCP`."


# ---------- stage 4: tests ----------
_FILE_RE = re.compile(r"^[ \t]*(?:\*\*)?FILE:\s*`?([^\s`*]+)`?(?:\*\*)?[ \t]*\n[ \t]*```[^\n]*\n(.*?)\n[ \t]*```", re.M | re.S)


def _safe_rel(path):
    p = path.replace("\\", "/").strip()
    parts = p.split("/")
    if not p or p.startswith("/") or re.match(r"^[A-Za-z]:", p) or any(x in ("", ".", "..") for x in parts):
        return None
    if len(p) > 120 or not re.fullmatch(r"[A-Za-z0-9_./-]+", p):
        return None
    return p


# A code block tagged python or rust, with no FILE: line above it. Only used when saving (loose=True).
_BARE_RE = re.compile(r"^[ \t]*```[ \t]*(python|py|rust|rs)[ \t]*\n(.*?)\n[ \t]*```", re.M | re.S | re.I)
_BARE_EXT = {"python": ".py", "py": ".py", "rust": ".rs", "rs": ".rs"}


def extract_files(text, loose=False):
    """Return (files, skipped). files is {relative_path: content}. Unsafe paths are skipped, never written.

    loose=False: only blocks with a `FILE: path` line (what the tests run).
    loose=True: also python/rust blocks without a FILE line, saved as snippet_<n>.py / snippet_<n>.rs,
    so a bot that forgets the FILE line still gives real files instead of only markdown.
    """
    text = text or ""
    files, skipped, taken = {}, [], []
    for m in _FILE_RE.finditer(text):
        taken.append(m.span())
        rel = _safe_rel(m.group(1))
        body = m.group(2)
        if not rel or len(files) >= MAX_FILES or len(body) > MAX_FILE_CHARS:
            skipped.append(m.group(1)[:80])
            continue
        files[rel] = body + "\n"
    if loose:
        n = 0
        for m in _BARE_RE.finditer(text):
            if any(a <= m.start() < b for a, b in taken):
                continue  # this block already has a FILE line
            n += 1
            rel = f"snippet_{n}{_BARE_EXT[m.group(1).lower()]}"
            if len(files) >= MAX_FILES or len(m.group(2)) > MAX_FILE_CHARS or rel in files:
                skipped.append(rel)
                continue
            files[rel] = m.group(2) + "\n"
    return files, skipped


def pick_profile(files):
    """Only Python unittest is run. Node needs npm installs, so it is not run."""
    if any(re.fullmatch(r"(?:.*/)?test_[^/]*\.py", p) for p in files):
        return "python-unittest"
    return None


def clean_env():
    """Environment for generated code: no API keys, no tokens."""
    bad = ("KEY", "TOKEN", "SECRET", "PASSWORD")
    return {k: v for k, v in os.environ.items() if not any(w in k.upper() for w in bad)}


def _runner():
    spec = importlib.util.spec_from_file_location("atlas_coding_swarm_for_pipeline", HERE / "agents" / "atlas_coding_swarm.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_tests(combined_text, run_id, base_dir=None):
    """Write the code from the combined result into its own folder and run its tests.

    Returns {"status": "passed|failed|no_code|no_tests|off|error", "text": plain words, "workspace": str}.
    """
    if not tests_enabled():
        return {"status": "off", "text": "Tests were not run. They are turned off (ATLAS_SWARM_RUN_TESTS=0).", "workspace": ""}
    files, skipped = extract_files(combined_text)
    note = f" Skipped {len(skipped)} file(s) with an unsafe path or size: {', '.join(skipped)}." if skipped else ""
    if not files:
        return {"status": "no_code", "text": "No code files were found in the result, so no tests ran." + note, "workspace": ""}
    profile = pick_profile(files)
    root = Path(base_dir) if base_dir else Path(os.environ.get("ATLAS_DATA_DIR") or tempfile.gettempdir()) / "swarm-runs"
    ws = root / run_id
    for rel, body in files.items():
        dest = ws / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body, encoding="utf-8")
    listing = ", ".join(sorted(files))
    if not profile:
        return {"status": "no_tests", "text": f"Wrote {len(files)} file(s) ({listing}), but none is a test_*.py file, so NOTHING was proven.{note}", "workspace": str(ws)}
    # unittest discover only walks into importable packages, so a test in "my-app/" is never found.
    # Run from the test file's own folder when all tests share one.
    test_dirs = {str(Path(p).parent) for p in files if re.fullmatch(r"(?:.*/)?test_[^/]*\.py", p)}
    run_dir = ws / test_dirs.pop() if len(test_dirs) == 1 else ws
    try:
        res = _runner().run_allowed_tests(run_dir, profile, timeout=120, env=clean_env())
    except Exception as exc:
        return {"status": "error", "text": f"The tests could not start: {str(exc)[:200]}.{note}", "workspace": str(ws)}
    tail = ((res.get("stderr") or "") + "\n" + (res.get("stdout") or "")).strip()[-1200:]
    if res.get("timed_out"):
        return {"status": "failed", "text": f"TESTS FAILED: they ran longer than 120 seconds and were stopped. Files: {listing}.{note}", "workspace": str(ws)}
    if res.get("passed"):
        return {"status": "passed", "text": f"TESTS PASSED ({res['duration_seconds']} s). Files: {listing}.{note}\n\n{tail}", "workspace": str(ws)}
    if res.get("returncode") == 5 or "NO TESTS RAN" in tail:  # unittest/pytest: nothing was collected
        return {"status": "no_tests", "text": f"A test file was written, but 0 tests ran, so NOTHING was proven. Files: {listing}.{note}\n\n{tail}", "workspace": str(ws)}
    return {"status": "failed", "text": f"TESTS FAILED (exit code {res.get('returncode')}). Files: {listing}.{note}\n\n{tail}", "workspace": str(ws)}


# ---------- grounding: does the result fit the real repo? ----------
# Installer tools: (name, regex for "the text names it", regex for "a FILE path or body uses it").
TOOLS = (
    ("NSIS", r"\bnsis\b|makensis", r"\.ns[ih]$|makensis|!include|\bSection\s+\"|nsis"),
    ("WiX", r"\bwix\b", r"\.wxs$|<wix\b|candle\.exe|light\.exe|\bwix\b"),
    ("Inno Setup", r"\binno setup\b|\bISCC\b", r"\.iss$|\[Setup\]|\bISCC\b"),
)


def _is_test(path):
    return bool(re.fullmatch(r"(?:.*/)?test_[^/]*\.py", path))


def grounding_check(combined, repo_files):
    """Plain-language problems where the result does not fit the repo. Returns "" when nothing is wrong.

    1. FILE blocks for paths that are not in the repo (new test_*.py files are fine).
       The bots were told to change existing files, so an unknown path is most often an invented one.
    2. An installer tool the text names (or the repo uses) while the code is for another tool:
       for example "NSIS" in the words, but a WiX .wxs file in the code.
    repo_files: the paths repo_context listed. Empty = no repo was read, so only check 2 runs on the text alone.
    """
    files, _ = extract_files(combined)
    problems = []
    if repo_files:
        known = set(repo_files)
        by_name = {}
        for p in repo_files:
            by_name.setdefault(p.rsplit("/", 1)[-1], []).append(p)
        for path in sorted(files):
            if path in known or _is_test(path):
                continue
            same = by_name.get(path.rsplit("/", 1)[-1])
            problems.append(f"- {path} is NOT in the repo" + (f" (the repo has {', '.join(same[:3])})" if same else "")
                            + ". It is probably invented.")
    code = "\n".join(list(files) + list(files.values()))
    words = re.sub(r"```.*?```", "", combined or "", flags=re.S)  # the prose only
    repo_paths = "\n".join(repo_files or [])
    written = {name for name, _say, use in TOOLS if re.search(use, code, re.I | re.M)}
    for name, say, use in TOOLS:
        if not written or name in written:
            continue
        who = ("The repo uses" if re.search(use, repo_paths, re.I | re.M)
               else "The result names" if re.search(say, words, re.I) else None)
        if who:
            problems.append(f"- {who} {name}, but the code in the result is for {', '.join(sorted(written))}.")
    if not problems:
        return ""
    return "AUTOMATIC CHECK (Atlas compared the result with the real repo):\n" + "\n".join(problems)


# ---------- stage 5: review ----------
def review_prompt(goal, combined, test_text, grounding=""):
    check = (f"\n\n{grounding}\nList these problems first in your review, and say the result is not ready while they stay."
             if grounding else "")
    return ("You are a strict reviewer. Review the result for the goal. Say what is good, what is wrong or missing, "
            "and what to fix first. Use plain English and under 300 words. Use the test result as proof, not opinion. "
            "Flag any file path or tool the result names that the repo does not have.\n"
            f"GOAL: {goal}\n\nTEST RESULT:\n{test_text[:1500]}{check}\n\nRESULT:\n{combined[:9000]}")
