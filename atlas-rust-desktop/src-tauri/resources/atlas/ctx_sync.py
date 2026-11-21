"""ctxsync: one shared context per project for Atlas bots, Claude Code, Codex, Cursor, Gemini, Grok, ChatGPT.

Standard library only. Store: <data>/.atlas/ctxsync/<project>/
  context.md  the summary (written by `summarize`, or by hand)
  log.jsonl   append only, one JSON object per line: ts, source, kind, text
The ctxsync folder gets a .gitattributes with "log.jsonl merge=union", so two PCs that both append never conflict.

CLI (python ctx_sync.py <command> --help):
  init | note TEXT | show | ingest FILE --source S | render --target T | summarize --via P | sync | serve
Web apps (ChatGPT, Grok, AI Studio) have no session API: use `render --target paste` and `ingest` (paste in, paste out).
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import threading

START, END = "<!-- ctxsync:start -->", "<!-- ctxsync:end -->"
KINDS = ("note", "decision", "fact", "todo", "summary")
TARGETS = {"claude": "CLAUDE.md", "agents": "AGENTS.md", "gemini": "GEMINI.md",
           "cursor": os.path.join(".cursor", "rules", "ctxsync.mdc")}
# All four speak the OpenAI chat API. Keys only from the environment. CTXSYNC_MODEL overrides the model.
PROVIDERS = {
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY", "openrouter/auto"),
    "openai": ("https://api.openai.com/v1/chat/completions", "OPENAI_API_KEY", "gpt-4.1-mini"),
    "xai": ("https://api.x.ai/v1/chat/completions", "XAI_API_KEY", "grok-3-mini"),
    "google": ("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "GEMINI_API_KEY",
               "gemini-flash-latest"),
}
SUMMARY_PROMPT = ("You keep the shared project context for several AI coding tools. Merge the current summary and "
                  "the new log entries into one summary of at most 400 words. Headings: Goal, Decisions, Facts, "
                  "Open items. Keep file paths, names and numbers exact. Drop entries that later ones replace. "
                  "Write only the summary.")
_lock = threading.Lock()  # ponytail: one process lock; two processes that append at once rely on O_APPEND lines


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def data_dir():
    return os.environ.get("ATLAS_DATA_DIR") or os.getcwd()


def root(data):
    return os.path.join(data, ".atlas", "ctxsync")


def store(data, project):
    name = re.sub(r"[^\w.-]+", "-", str(project or "default")).strip(".-") or "default"
    return os.path.join(root(data), name[:80])


def init(data, project):
    path = store(data, project)
    os.makedirs(path, exist_ok=True)
    attrs = os.path.join(root(data), ".gitattributes")
    line = "log.jsonl merge=union"
    old = _read(attrs)
    if line not in old.splitlines():
        with open(attrs, "a", encoding="utf-8") as f:
            f.write(("" if not old or old.endswith("\n") else "\n") + line + "\n")
    for name in ("context.md", "log.jsonl"):
        open(os.path.join(path, name), "a", encoding="utf-8").close()
    return path


def note(data, project, text, source="user", kind="note"):
    text = " ".join(str(text or "").split())[:4000]
    if not text:
        raise ValueError("Note text is empty")
    kind = kind if kind in KINDS else "note"
    row = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "source": str(source or "user")[:40], "kind": kind, "text": text}
    path = init(data, project)
    with _lock, open(os.path.join(path, "log.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def read_log(data, project):
    rows = []
    try:
        with open(os.path.join(store(data, project), "log.jsonl"), encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue  # a half-written or hand-broken line never stops the reader
                if isinstance(row, dict) and str(row.get("text", "")).strip():
                    rows.append(row)
    except OSError:
        pass
    return sorted(rows, key=lambda r: str(r.get("ts", "")))  # union merges can mix the order


def read_context(data, project):
    try:
        with open(os.path.join(store(data, project), "context.md"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def bridge_memory(data, project, items):
    """Copy Atlas memory facts (context_engine memory.json items) into the shared log. Skips texts already there."""
    seen = {str(r.get("text", "")).casefold() for r in read_log(data, project)}
    added = 0
    for item in items or []:
        text = " ".join(str(item.get("text", "")).split()) if isinstance(item, dict) else ""
        if text and text.casefold() not in seen:
            note(data, project, text, "atlas-memory", "fact")
            seen.add(text.casefold())
            added += 1
    return added


def ingest(data, project, file_path, source):
    """Paste out of a web app into a file, then ingest it: one note per paragraph."""
    with open(file_path, encoding="utf-8") as f:
        parts = [p.strip() for p in re.split(r"\n\s*\n", f.read()) if p.strip()]
    for p in parts:
        note(data, project, p, source, "note")
    return len(parts)


def context_text(data, project, recent=20):
    """The block every tool sees: the summary, then the newest log entries."""
    lines = [f"# Shared project context ({project}, from ctxsync)", "",
             read_context(data, project) or "_No summary yet. Run `ctx_sync.py summarize`._"]
    log = read_log(data, project)[-recent:]
    if log:
        lines += ["", "## Recent notes"] + [f"- {r.get('ts', '')[:16]} [{r.get('source', '?')}/{r.get('kind', 'note')}] "
                                            f"{r['text']}" for r in log]
    return "\n".join(lines).strip() + "\n"


def replace_block(old, block):
    """Put block between the ctxsync markers. Text outside the markers never changes."""
    new = f"{START}\n{block.rstrip()}\n{END}"
    i, j = old.find(START), old.find(END)
    if i != -1 and j > i:
        return old[:i] + new + old[j + len(END):]
    return (old.rstrip() + "\n\n" if old.strip() else "") + new + "\n"


def render(data, project, target, out_dir="."):
    block = context_text(data, project)
    if target == "paste":
        return ("Below is the shared context of my project. Use it for this chat. When we decide something, "
                "end your answer with a short list under the heading CTXSYNC NOTES so I can paste it back.\n\n" + block)
    if target not in TARGETS:
        raise ValueError(f"Unknown target {target}. Use: {', '.join(list(TARGETS) + ['paste'])}")
    path = os.path.join(out_dir, TARGETS[target])
    old = _read(path)
    if target == "cursor" and not old:
        old = "---\ndescription: Shared project context from ctxsync\nalwaysApply: true\n---\n"
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(replace_block(old, block))
    return path


def summarize(data, project, via, timeout=120):
    if via not in PROVIDERS:
        raise ValueError(f"Unknown provider {via}. Use: {', '.join(PROVIDERS)}")
    url, env, model = PROVIDERS[via]
    key = os.environ.get(env, "").strip()
    if not key:
        raise ValueError(f"Set {env} in your environment first")
    log = read_log(data, project)
    body = ("CURRENT SUMMARY:\n" + (read_context(data, project) or "(none)") + "\n\nLOG ENTRIES:\n" +
            "\n".join(f"{r.get('ts', '')} [{r.get('source')}/{r.get('kind')}] {r['text']}" for r in log[-300:]))
    import cloud_llm  # reuse its proxy handling and key-safe errors
    reply = cloud_llm._post(os.environ.get("CTXSYNC_URL") or url, {"Authorization": f"Bearer {key}"},
                            {"model": os.environ.get("CTXSYNC_MODEL") or model, "temperature": 0.2,
                             "messages": [{"role": "system", "content": SUMMARY_PROMPT},
                                          {"role": "user", "content": body}]}, timeout)
    try:
        text = re.sub(r"<think>[\s\S]*?(</think>|$)", "", reply["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError):
        text = ""
    if not text:
        raise RuntimeError(f"{via} sent back no summary")
    with open(os.path.join(init(data, project), "context.md"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    note(data, project, f"Summary updated via {via}", "ctxsync", "summary")
    return text


def sync(data, message="ctxsync"):
    """git add, commit, pull --rebase, push in the ctxsync folder. You make it a repo with a remote once."""
    cwd = root(data)
    if not os.path.isdir(os.path.join(cwd, ".git")):
        raise ValueError(f"{cwd} is not a git repo. Run there once: git init, git remote add origin <url>")
    out = []
    for cmd in (["git", "add", "-A"], ["git", "commit", "-m", message], ["git", "pull", "--rebase"], ["git", "push"]):
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        out.append(f"$ {' '.join(cmd)}\n{(p.stdout + p.stderr).strip()}")
        if p.returncode and cmd[1] != "commit":  # "nothing to commit" is fine
            raise RuntimeError("\n".join(out))
    return "\n".join(out)


# ---------------------------------------------------------------- MCP stdio server
TOOLS = [
    {"name": "ctx_read", "description": "Read the shared project context (summary and recent notes) from ctxsync.",
     "inputSchema": {"type": "object", "properties": {"recent": {"type": "integer", "description": "How many recent notes"}}}},
    {"name": "ctx_note", "description": "Add a note or decision to the shared project context, so other AI tools see it.",
     "inputSchema": {"type": "object", "required": ["text"], "properties": {
         "text": {"type": "string"}, "kind": {"type": "string", "enum": list(KINDS)},
         "source": {"type": "string", "description": "Who writes: claude-code, codex, cursor, ..."}}}},
]


def handle_mcp(msg, data, project):
    """One JSON-RPC message in, one reply out (None for notifications)."""
    method, mid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if mid is None:
        return None
    if method == "initialize":
        result = {"protocolVersion": params.get("protocolVersion", "2024-11-05"), "capabilities": {"tools": {}},
                  "serverInfo": {"name": "ctxsync", "version": "1"}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        args = params.get("arguments") or {}
        try:
            if params.get("name") == "ctx_read":
                text = context_text(data, project, int(args.get("recent") or 20))
            elif params.get("name") == "ctx_note":
                row = note(data, project, args.get("text"), args.get("source") or "mcp", args.get("kind") or "note")
                text = f"Saved {row['kind']} at {row['ts']}"
            else:
                return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": "Unknown tool"}}
            result = {"content": [{"type": "text", "text": text}]}
        except (ValueError, OSError) as exc:
            result = {"content": [{"type": "text", "text": str(exc)}], "isError": True}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Unknown method {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def serve(data, project, inp=sys.stdin, out=sys.stdout):
    for line in inp:
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        reply = handle_mcp(msg, data, project) if isinstance(msg, dict) else None
        if reply is not None:
            out.write(json.dumps(reply, ensure_ascii=False) + "\n")
            out.flush()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ctx_sync.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--data", default=None, help="Atlas data folder (default: ATLAS_DATA_DIR, else this folder)")
    ap.add_argument("--project", default=os.environ.get("CTXSYNC_PROJECT", "default"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    p = sub.add_parser("note"); p.add_argument("text"); p.add_argument("--kind", default="note", choices=KINDS)
    p.add_argument("--source", default="user")
    sub.add_parser("show")
    p = sub.add_parser("ingest"); p.add_argument("file"); p.add_argument("--source", required=True)
    p = sub.add_parser("render"); p.add_argument("--target", required=True, choices=list(TARGETS) + ["paste"])
    p.add_argument("--out", default=".", help="Repo folder to write into (default: current folder)")
    p = sub.add_parser("summarize"); p.add_argument("--via", required=True, choices=list(PROVIDERS))
    p = sub.add_parser("sync"); p.add_argument("-m", "--message", default="ctxsync")
    sub.add_parser("serve")
    a = ap.parse_args(argv)
    data = a.data or data_dir()
    try:
        if a.cmd == "init":
            print(init(data, a.project))
        elif a.cmd == "note":
            print(json.dumps(note(data, a.project, a.text, a.source, a.kind), ensure_ascii=False))
        elif a.cmd == "show":
            print(context_text(data, a.project, 50))
        elif a.cmd == "ingest":
            print(f"{ingest(data, a.project, a.file, a.source)} notes added")
        elif a.cmd == "render":
            print(render(data, a.project, a.target, a.out))
        elif a.cmd == "summarize":
            print(summarize(data, a.project, a.via))
        elif a.cmd == "sync":
            print(sync(data, a.message))
        elif a.cmd == "serve":
            sys.stdin.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252
            sys.stdout.reconfigure(encoding="utf-8")
            serve(data, a.project)
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"ctxsync: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
