"""Read-only snapshot of the project folder for the /swarm bots.

The bots cannot open files themselves. Before a run starts, build() walks the Workspace folder once and returns
plain text: a list of the files, then short parts of the files that match the goal best. Every bot and the
Swarm Lead get the same text, so they write code that fits the real repo.

Safety rules:
- Read only. This module never writes, moves or deletes a file.
- Secret files (.env, keys, certificates, settings with tokens) are never read and never listed.
- Symlinks are not followed, so the walk cannot leave the folder.
- Hard limits on files scanned, bytes per file and characters returned, so a big repo cannot stall a run.
"""
from __future__ import annotations

import os
import re
import time

MAX_CHARS = 6000          # whole snapshot; about 1,500 tokens, small enough for a local model
MAX_TREE_LINES = 150      # file list lines (one per folder)
TREE_SHARE = 0.4          # the file list may use this part of MAX_CHARS; file text gets the rest
MAX_SCAN_FILES = 4000     # files looked at for matches
MAX_FILE_BYTES = 200_000  # bigger files are listed but not read
MAX_SHOWN_FILES = 5       # files whose text is shown
EXCERPT_CHARS = 600       # text shown per file
MAX_SECONDS = 5.0         # stop the walk after this, and use what was found

# Atlas's own run folders count as junk too: swarm-workspaces/ holds old task JSON, not the user's code.
SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", "target", "__pycache__", "dist", "build", ".venv", "venv",
             "env", ".next", ".idea", ".vscode", "runtime", "swarm-output", "swarm-runs", "swarm-workspaces",
             ".pytest_cache", ".mypy_cache"}
ARTIFACT_NAMES = {".atlas-swarm-task.json", ".git"}  # Atlas's task file; .git is a file in a git worktree
TEXT_EXT = {".py", ".rs", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".html", ".css", ".md", ".toml", ".json",
            ".yaml", ".yml", ".ps1", ".txt", ".cfg", ".ini", ".sh", ".bat", ".cmd", ".nsi", ".nsh", ".iss", ".wxs"}
NOT_SOURCE_EXT = {".json", ".md", ".txt"}  # data and notes: a folder with only these has no code to change
# A goal word also finds files named with these words. "package Atlas for production" must find build-release.ps1,
# tauri.conf.json and the NSIS files, though none of them holds the word "package".
# ponytail: fixed word list, grow it when a kind of goal keeps missing its files.
RELATED = {
    "package": ("build", "release", "installer", "nsis", "bundle", "tauri.conf"),
    "packaging": ("build", "release", "installer", "nsis", "bundle", "tauri.conf"),
    "production": ("build", "release", "installer", "server", "config"),
    "release": ("build", "installer", "nsis", "version"),
    "installer": ("nsis", "install", "build", "release"),
    "install": ("installer", "nsis", "setup"),
    "deploy": ("build", "release", "docker", "server"),
    "ship": ("build", "release", "installer"),
    "build": ("release", "cargo", "package.json", "tauri.conf"),
    "backend": ("server",),
    "api": ("server",),
    "frontend": ("index.html",),
}
SECRET_NAME = re.compile(r"(^\.env|\.pem$|\.key$|\.pfx$|\.p12$|\.crt$|^id_(rsa|ed25519|ecdsa)|secret|credential|token"
                         r"|password|^settings\.json$|\.sqlite3?$|\.db$)", re.I)
STOP_WORDS = {"the", "and", "for", "with", "that", "this", "from", "into", "make", "sure", "all", "can", "you", "are",
              "add", "use", "how", "what", "need", "needs", "want", "please", "code", "file", "files", "bot", "bots"}


def goal_words(goal):
    """Lower-case words of 3+ letters from the goal, without common filler words, plus their RELATED file words."""
    words = {w for w in re.findall(r"[a-z0-9_]{3,}", str(goal or "").lower()) if w not in STOP_WORDS}
    for w in list(words):
        words.update(RELATED.get(w, ()))
    return sorted(words)


def _walk(root, deadline):
    """Yield (relative posix path, full path) for files that may be listed. No symlinks, no secrets, no junk folders."""
    for current, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")
                         and not os.path.islink(os.path.join(current, d)))
        for name in sorted(names):
            if time.monotonic() > deadline:
                return
            full = os.path.join(current, name)
            if SECRET_NAME.search(name) or name in ARTIFACT_NAMES or os.path.islink(full):
                continue
            yield os.path.relpath(full, root).replace(os.sep, "/"), full


def _read(full):
    """Text of a small text file, or None (too big, binary, unreadable)."""
    try:
        if os.path.getsize(full) > MAX_FILE_BYTES:
            return None
        with open(full, "rb") as f:
            data = f.read()
    except OSError:
        return None
    if b"\0" in data[:4096]:
        return None  # binary
    return data.decode("utf-8", errors="replace")


def _excerpt(text, words):
    """EXCERPT_CHARS of text around the first goal word, or the start of the file."""
    low = text.lower()
    hits = [i for i in (low.find(w) for w in words) if i >= 0]
    start = max(0, min(hits) - EXCERPT_CHARS // 4) if hits else 0
    start = text.rfind("\n", 0, start) + 1 if start else 0  # begin on a whole line
    part = text[start:start + EXCERPT_CHARS]
    return part + ("\n..." if start + EXCERPT_CHARS < len(text) else "")


def _tree(paths, budget):
    """File list as one line per folder ("- folder/: a.py, b.py"), shallow folders first, within budget characters.

    One line per folder repeats no long path prefix, so a deep repo still fits and leaves room for file text.
    """
    by_dir = {}
    for p in sorted(paths, key=lambda p: (p.count("/"), p)):
        d, _, name = p.rpartition("/")
        by_dir.setdefault(d, []).append(name)
    lines, used = [], 0
    for d, names in list(by_dir.items())[:MAX_TREE_LINES]:
        line = f"- {d + '/' if d else '(top folder)'}: {', '.join(names)}"
        line = line if len(line) <= 400 else line[:396] + " ..."
        if used + len(line) > budget:
            break
        lines.append(line)
        used += len(line) + 1
    return [f"FILES ({len(paths)} found; {len(lines)} of {len(by_dir)} folders listed). Each line is a folder, then its "
            "files. A file's path is the folder plus the file name, for example src/app.py:"] + lines


def build(root, goal, max_chars=MAX_CHARS):
    """Return {"text", "listed", "shown", "files", "folder", "warn", "note"}.

    text: snapshot for the bots, or "". files: every listed path (the grounding check uses it).
    folder: full folder path. warn: True when the bots will mostly guess (no folder, no files, no source code).
    note: plain words for the chat log. It always names the folder. Never raises.
    """
    empty = {"text": "", "listed": 0, "shown": [], "files": [], "folder": str(root or ""), "warn": True}
    if not root or not os.path.isdir(root):
        return {**empty, "note": "No Workspace folder is set, so the bots cannot read the repo. Click Workspace "
                                 "(next to Send), set your project folder, then run /swarm again."}
    folder = os.path.abspath(root)
    try:
        deadline = time.monotonic() + MAX_SECONDS
        words = goal_words(goal)
        paths, found = [], []  # found: (rel, goal words in the path, {goal word: hits in the text})
        for rel, full in _walk(root, deadline):
            paths.append(rel)
            if not words or len(paths) > MAX_SCAN_FILES or os.path.splitext(rel)[1].lower() not in TEXT_EXT:
                continue
            low_rel, text = rel.lower(), (_read(full) or "").lower()
            found.append((rel, {w for w in words if w in low_rel}, {w: text.count(w) for w in words if w in text}))
        # A word found in most files (the project name, "atlas") says nothing about which file matters. Skip it.
        # Paths and texts are counted apart: "server" is in many texts, but only in a few file names.
        path_common, common = set(), set()
        if len(found) >= 10:
            path_common = {w for w in words if sum(1 for f in found if w in f[1]) > len(found) * 0.3}
            common = {w for w in words if sum(1 for f in found if w in f[2]) > len(found) * 0.3}
        scored = []
        for rel, ph, bh in found:
            score = 10 * len(ph - path_common) + min(15, sum(min(3, n) for w, n in bh.items() if w not in common))
            if os.path.splitext(rel)[1].lower() in (".md", ".txt"):
                score //= 2  # notes and plans: the bots need the code and config first
            if score:
                scored.append((score, rel))
        out = [f"REPO SNAPSHOT (read-only) of the project folder: {os.path.basename(os.path.normpath(root))}"] \
            + _tree(paths, int(max_chars * TREE_SHARE))
        shown, focus = [], [w for w in words if w not in common] or words
        for _score, rel in sorted(scored, key=lambda s: (-s[0], s[1])):
            if len(shown) >= MAX_SHOWN_FILES:
                break
            ext = os.path.splitext(rel)[1].lower()
            if sum(1 for s in shown if s.lower().endswith(ext)) >= 2:
                continue  # mix file types: two build scripts, then the config, not five build scripts
            text = _read(os.path.join(root, rel))  # read again: keeping every text in memory costs too much
            if text is None:
                continue
            block = f"\n--- {rel} ---\n{_excerpt(text, focus)}"
            if sum(len(x) + 1 for x in out) + len(block) > max_chars:
                break
            out.append(block)
            shown.append(rel)
        source = sum(1 for p in paths if os.path.splitext(p)[1].lower() in TEXT_EXT - NOT_SOURCE_EXT)
        fix = "Click Workspace (next to Send) and set your project folder, then run /swarm again."
        if not paths:
            note = (f"WARNING: the project folder {folder} has no files the bots can use (Atlas's own task and output "
                    f"files are skipped). The bots will guess. {fix}")
        elif not source:
            note = (f"WARNING: I read the project folder {folder} ({len(paths)} files), but it has no source code, only "
                    f"data or notes (.json, .md, .txt). The bots will guess file names. If this is not your project: {fix}")
        else:
            note = (f"I read the project folder {folder} ({len(paths)} files, {source} with source code). The bots see the file list"
                    + (f" and parts of: {', '.join(shown)}." if shown else ". No file matched the goal words."))
        return {"text": "\n".join(out)[:max_chars] if paths else "", "listed": len(paths), "shown": shown,
                "files": paths[:MAX_SCAN_FILES], "folder": folder, "warn": not source, "note": note}
    except Exception as exc:  # reading the repo is a help, never a reason to stop the swarm
        return {**empty, "folder": folder, "note": f"I could not read the project folder {folder} ({str(exc)[:150]})."}
