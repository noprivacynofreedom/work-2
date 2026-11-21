"""ctxsync: shared project context (ctx_sync.py), its MCP server, and the /api/sync routes."""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ATLAS = os.path.join(os.path.dirname(HERE), "src-tauri", "resources", "atlas")
sys.path.insert(0, ATLAS)
_DATA = tempfile.TemporaryDirectory()
os.environ.setdefault("ATLAS_DATA_DIR", _DATA.name)  # never touch real data

import ctx_sync  # noqa: E402
import mcp_chat  # noqa: E402


class Store(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_note_appends_and_gitattributes_once(self):
        ctx_sync.note(self.data, "p", "We use SQLite", "codex", "decision")
        ctx_sync.note(self.data, "p", "second")
        rows = ctx_sync.read_log(self.data, "p")
        self.assertEqual([r["text"] for r in rows], ["We use SQLite", "second"])
        self.assertEqual(rows[0]["source"], "codex")
        self.assertEqual(rows[0]["kind"], "decision")
        attrs = ctx_sync._read(os.path.join(self.data, ".atlas", "ctxsync", ".gitattributes"))
        self.assertEqual(attrs.count("log.jsonl merge=union"), 1)
        with self.assertRaises(ValueError):
            ctx_sync.note(self.data, "p", "   ")

    def test_project_name_cannot_leave_the_store(self):
        path = ctx_sync.store(self.data, "../../etc")
        self.assertTrue(os.path.abspath(path).startswith(os.path.abspath(ctx_sync.root(self.data))))

    def test_broken_line_is_skipped(self):
        ctx_sync.note(self.data, "p", "good")
        with open(os.path.join(ctx_sync.store(self.data, "p"), "log.jsonl"), "a") as f:
            f.write("{half a line\n")
        self.assertEqual(len(ctx_sync.read_log(self.data, "p")), 1)

    def test_render_keeps_text_outside_markers(self):
        out = os.path.join(self.data, "repo")
        os.makedirs(out)
        with open(os.path.join(out, "CLAUDE.md"), "w", encoding="utf-8") as f:
            f.write("# My rules\nKeep me.\n")
        ctx_sync.note(self.data, "p", "first note")
        ctx_sync.render(self.data, "p", "claude", out)
        ctx_sync.note(self.data, "p", "second note")
        ctx_sync.render(self.data, "p", "claude", out)
        text = ctx_sync._read(os.path.join(out, "CLAUDE.md"))
        self.assertTrue(text.startswith("# My rules\nKeep me.\n"))
        self.assertEqual(text.count(ctx_sync.START), 1)
        self.assertIn("second note", text)
        with open(os.path.join(out, "CLAUDE.md"), "a", encoding="utf-8") as f:
            f.write("after the block\n")
        ctx_sync.render(self.data, "p", "claude", out)
        self.assertTrue(ctx_sync._read(os.path.join(out, "CLAUDE.md")).endswith("after the block\n"))

    def test_render_cursor_and_paste(self):
        out = os.path.join(self.data, "repo")
        path = ctx_sync.render(self.data, "p", "cursor", out)
        self.assertTrue(ctx_sync._read(path).startswith("---\n"))
        self.assertIn("CTXSYNC NOTES", ctx_sync.render(self.data, "p", "paste"))
        with self.assertRaises(ValueError):
            ctx_sync.render(self.data, "p", "nope", out)

    def test_bridge_memory_skips_duplicates(self):
        items = [{"text": "I use PowerShell"}, {"text": "i use powershell"}, {"text": "Windows 11"}]
        self.assertEqual(ctx_sync.bridge_memory(self.data, "p", items), 2)
        self.assertEqual(ctx_sync.bridge_memory(self.data, "p", items), 0)
        self.assertEqual({r["source"] for r in ctx_sync.read_log(self.data, "p")}, {"atlas-memory"})

    def test_ingest_one_note_per_paragraph(self):
        path = os.path.join(self.data, "paste.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("CTXSYNC NOTES\n\n- use port 8080\n\n- tests in validation-tests\n")
        self.assertEqual(ctx_sync.ingest(self.data, "p", path, "chatgpt"), 3)


class Summarize(unittest.TestCase):
    def test_summarize_uses_openai_style_api(self):
        seen = {}

        class Fake(BaseHTTPRequestHandler):
            def do_POST(self):
                seen["auth"] = self.headers.get("Authorization")
                seen["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                out = json.dumps({"choices": [{"message": {"content": "<think>x</think>Goal: ship ctxsync"}}]}).encode()
                self.send_response(200); self.send_header("Content-Length", str(len(out))); self.end_headers()
                self.wfile.write(out)

            def log_message(self, *a):
                pass

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        env = {"CTXSYNC_URL": f"http://127.0.0.1:{httpd.server_port}/v1/chat/completions",
               "OPENAI_API_KEY": "test-not-a-key", "ATLAS_CLOUD_PROXY": ""}
        old = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        try:
            with tempfile.TemporaryDirectory() as data:
                ctx_sync.note(data, "p", "decided to ship")
                self.assertEqual(ctx_sync.summarize(data, "p", "openai", timeout=10), "Goal: ship ctxsync")
                self.assertEqual(ctx_sync.read_context(data, "p"), "Goal: ship ctxsync")
                self.assertIn("decided to ship", seen["body"]["messages"][1]["content"])
                self.assertEqual(seen["auth"], "Bearer test-not-a-key")
        finally:
            httpd.shutdown()
            for k, v in old.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def test_missing_key_is_a_clear_error(self):
        old = os.environ.pop("XAI_API_KEY", None)
        try:
            with self.assertRaisesRegex(ValueError, "XAI_API_KEY"):
                ctx_sync.summarize(_DATA.name, "p", "xai")
        finally:
            if old is not None:
                os.environ["XAI_API_KEY"] = old


class McpServe(unittest.TestCase):
    def test_tiers_are_set(self):
        self.assertEqual(mcp_chat.tool_tier("ctx_read"), "read")
        self.assertEqual(mcp_chat.tool_tier("ctx_note"), "write")

    def test_stdio_server_round_trip(self):
        with tempfile.TemporaryDirectory() as data:
            msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
                    {"jsonrpc": "2.0", "method": "notifications/initialized"},
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                    {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                     "params": {"name": "ctx_note", "arguments": {"text": "Grüße from Claude Code", "source": "claude-code"}}},
                    {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "ctx_read", "arguments": {}}}]
            p = subprocess.run([sys.executable, os.path.join(ATLAS, "ctx_sync.py"), "--data", data, "--project", "p", "serve"],
                               input="\n".join(json.dumps(m) for m in msgs) + "\n", capture_output=True,
                               encoding="utf-8", timeout=30)
            replies = [json.loads(line) for line in p.stdout.splitlines()]
            self.assertEqual([r["id"] for r in replies], [1, 2, 3, 4])  # no reply to the notification
            self.assertEqual({t["name"] for t in replies[1]["result"]["tools"]}, {"ctx_read", "ctx_note"})
            self.assertIn("Grüße from Claude Code", replies[3]["result"]["content"][0]["text"])


class Routes(unittest.TestCase):
    """Real server.Handler with a temporary DATA_DIR."""

    @classmethod
    def setUpClass(cls):
        import server
        cls.server = server
        cls.tmp = tempfile.TemporaryDirectory()
        cls.saved = server.DATA_DIR
        server.DATA_DIR = cls.tmp.name
        cls.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.httpd.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.server.DATA_DIR = cls.saved
        cls.tmp.cleanup()

    def _call(self, path, body=None):
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())

    def test_note_then_status_with_memory_bridge(self):
        import context_engine
        context_engine.memory_action(self.tmp.name, {"action": "add", "text": "The user builds with build-release.ps1"})
        self.assertTrue(self._call("/api/sync/note", {"project": "web", "kind": "decision", "text": "Panel goes in the header"})["ok"])
        d = self._call("/api/sync/status?project=web")
        self.assertEqual(d["project"], "web")
        self.assertEqual(d["bridged"], 1)
        self.assertEqual({r["text"] for r in d["recent"]}, {"Panel goes in the header", "The user builds with build-release.ps1"})
        self.assertEqual(self._call("/api/sync/status?project=web")["bridged"], 0)



class GitSync(unittest.TestCase):
    """Two PCs append to the same log, then both run sync: merge=union keeps every line, no conflict."""

    def git(self, cwd, *args):
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                   GIT_COMMITTER_EMAIL="t@t")
        return subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True)

    def test_two_pcs_sync_without_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            remote = os.path.join(tmp, "remote.git")
            self.git(tmp, "init", "--bare", "-b", "main", remote)
            pc1, pc2 = os.path.join(tmp, "pc1"), os.path.join(tmp, "pc2")
            ctx_sync.note(pc1, "p", "first note", "pc1")
            r1 = ctx_sync.root(pc1)
            self.git(r1, "init", "-b", "main")
            self.git(r1, "remote", "add", "origin", remote)
            self.git(r1, "add", "-A")
            self.git(r1, "commit", "-m", "start")
            self.git(r1, "push", "-u", "origin", "main")
            os.makedirs(os.path.join(pc2, ".atlas"))
            self.git(os.path.join(pc2, ".atlas"), "clone", remote, "ctxsync")
            ctx_sync.note(pc1, "p", "from pc1", "pc1")
            ctx_sync.note(pc2, "p", "from pc2", "pc2")
            ctx_sync.sync(pc1)
            ctx_sync.sync(pc2)  # pulls pc1's line with --rebase: same file, both sides appended
            ctx_sync.sync(pc1)
            for pc in (pc1, pc2):
                texts = [r["text"] for r in ctx_sync.read_log(pc, "p")]
                self.assertEqual(sorted(texts), ["first note", "from pc1", "from pc2"])

    def test_sync_needs_a_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx_sync.init(tmp, "p")
            with self.assertRaisesRegex(ValueError, "not a git repo"):
                ctx_sync.sync(tmp)

if __name__ == "__main__":
    unittest.main()
