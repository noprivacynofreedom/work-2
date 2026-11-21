"""Context engine: real window, exact token counts, usage passthrough, retrieval filter, memory, compaction.

Unit tests for context_engine.py plus HTTP tests through the real server.Handler against a fake llama-swap
(fake_llama_swap.py: 1 token per 4 characters, so the numbers are exact and checkable).
"""
import json
import math
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src-tauri", "resources", "atlas"))
_DATA = tempfile.TemporaryDirectory(prefix="atlas-context-test-")
os.environ.setdefault("ATLAS_DATA_DIR", _DATA.name)  # never touch real chats, memory or library
os.environ.setdefault("ATLAS_OBSERVABILITY_DB", os.path.join(_DATA.name, "observability.sqlite3"))

import context_engine as ce  # noqa: E402
import fake_llama_swap  # noqa: E402
import mcp_chat  # noqa: E402
import server  # noqa: E402


class Unit(unittest.TestCase):
    def test_parse_n_ctx(self):
        self.assertEqual(ce.parse_n_ctx({"default_generation_settings": {"n_ctx": 16384}}), 16384)
        self.assertEqual(ce.parse_n_ctx({"n_ctx": 4096}), 4096)
        self.assertIsNone(ce.parse_n_ctx({"modalities": {}}))
        self.assertIsNone(ce.parse_n_ctx(None))

    def test_retrieval_query_uses_previous_turn_for_short_follow_up(self):
        msgs = [{"role": "user", "content": "How do I replace the lighthouse lantern glass after a storm?"},
                {"role": "assistant", "content": "..."}, {"role": "user", "content": "and the lens?"}]
        q = ce.retrieval_query(msgs)
        self.assertIn("lantern glass", q)
        self.assertTrue(q.endswith("and the lens?"))
        long = msgs + [{"role": "user", "content": "Explain how the brass sextant fixes the lens alignment in detail"}]
        self.assertEqual(ce.retrieval_query(long), long[-1]["content"])

    def test_select_hits_drops_weak_duplicate_and_over_budget(self):
        text = "The storm broke the lantern glass and Mara fixed the lens with a sextant. " * 3
        hits = [{"title": "A", "score": 10, "text": text},
                {"title": "A copy", "score": 9, "text": text},          # duplicate
                {"title": "Weak", "score": 1, "text": "unrelated words only here"},  # below 35% of top
                {"title": "B", "score": 8, "text": "Wellington letter news about the keeper cafe " * 2},
                {"title": "Huge", "score": 7, "text": "x " * 50000}]   # over budget
        kept = ce.select_hits(hits, token_budget=400)
        self.assertEqual([h["title"] for h in kept], ["A", "B"])
        self.assertEqual(ce.select_hits([{"title": "z", "score": 0, "text": "a"}], 100), [])

    def test_memory_actions_and_block(self):
        with tempfile.TemporaryDirectory() as d:
            ce.memory_action(d, {"action": "add", "text": "I use Windows 11 and PowerShell"})
            ce.memory_action(d, {"action": "add", "text": "i use windows 11 and powershell"})  # duplicate ignored
            ce.memory_action(d, {"action": "add", "text": "My shop sells VIP ranks for a CS2 server"})
            data = ce.load_memory(d)
            self.assertEqual(len(data["items"]), 2)
            text, kept = ce.memory_block(data, "which powershell command")
            self.assertIn("ATLAS MEMORY", text)
            self.assertIn("PowerShell", kept[0]["text"])  # most relevant first
            ce.memory_action(d, {"action": "forget", "text": "powershell"})
            self.assertEqual(len(ce.load_memory(d)["items"]), 1)
            with self.assertRaises(ValueError):
                ce.memory_action(d, {"action": "forget", "text": "nothing matches this"})
            ce.memory_action(d, {"action": "enable", "enabled": False})
            self.assertEqual(ce.memory_block(ce.load_memory(d), "x"), ("", []))

    def test_compact_messages_caps_size_and_strips_think(self):
        msgs = [{"role": "user", "content": "start " * 5000}, {"role": "assistant", "content": "<think>secret</think>visible"},
                {"role": "user", "content": "end marker"}]
        body = ce.compact_messages("old summary", msgs, max_chars=6000)
        self.assertLess(len(body), 6400)
        self.assertNotIn("secret", body)
        self.assertIn("end marker", body)
        self.assertIn("EARLIER SUMMARY", body)

    def test_mcp_as_sse_keeps_usage_and_round_total(self):
        completion = {"choices": [{"message": {"content": "hi"}}], "usage": {"prompt_tokens": 50, "completion_tokens": 2},
                      "atlas_usage_total": {"prompt_tokens": 90, "completion_tokens": 9, "rounds": 2}}
        chunk = json.loads(mcp_chat.as_sse(completion).split("\n\n")[0][6:])
        self.assertEqual(chunk["usage"]["prompt_tokens"], 50)
        self.assertEqual(chunk["atlas_usage_total"]["rounds"], 2)


class Http(unittest.TestCase):
    """Real server.Handler -> fake llama-swap."""

    @classmethod
    def setUpClass(cls):
        cls.fake = fake_llama_swap.serve(0, 8192)
        cls.fake_port = cls.fake.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.fake.shutdown()
        cls.fake.server_close()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = (server.UPSTREAM_PORT, server.LIBRARY_DIR, server.LIBRARY_INDEX, server.LIBRARY_INDEX_FILE,
                      server.DATA_DIR, dict(server.SETTINGS))
        server.UPSTREAM_PORT = self.fake_port
        server.LIBRARY_DIR = self.tmp.name
        server.LIBRARY_INDEX = os.path.join(self.tmp.name, "index.json")
        server.LIBRARY_INDEX_FILE = os.path.join(self.tmp.name, "semantic-index.json")
        server.DATA_DIR = self.tmp.name
        server.SETTINGS["embedding_model"] = ""      # deterministic lexical retrieval
        server.SETTINGS["mcp_auto_tools"] = False    # plain chat path
        ce._props_cache.clear()
        self.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        (server.UPSTREAM_PORT, server.LIBRARY_DIR, server.LIBRARY_INDEX, server.LIBRARY_INDEX_FILE,
         server.DATA_DIR, settings) = self.saved
        server.SETTINGS.clear(); server.SETTINGS.update(settings)
        ce._props_cache.clear()
        self.tmp.cleanup()

    def req(self, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(self.base + path, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(r, timeout=20) as resp:
                return resp.status, resp.read().decode(), dict(resp.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode(), dict(e.headers)

    def chat(self, messages, model="assist"):
        code, raw, headers = self.req("/v1/chat/completions", {"model": model, "stream": True, "messages": messages,
                                                               "_atlas_context": {"conversation_id": "t1", "bot_id": "b"}})
        self.assertEqual(code, 200, raw)
        chunks = [json.loads(l[6:]) for l in raw.split("\n") if l.startswith("data: ") and l[6:].strip() != "[DONE]"]
        text = "".join((c["choices"][0]["delta"].get("content") or "") for c in chunks if c.get("choices"))
        return text, chunks, json.loads(headers.get("X-Atlas-Context") or "{}")

    def last_upstream(self):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.fake_port}/_last", timeout=5) as r:
            return json.loads(r.read())["chat"]

    def test_window_endpoint_reports_real_n_ctx(self):
        code, raw, _ = self.req("/api/context/window?model=assist")
        self.assertEqual((code, json.loads(raw)["n_ctx"]), (200, 8192))

    def test_exact_prompt_count_matches_server_usage(self):
        server.SETTINGS["exact_token_count"] = True  # opt-in since the preflight count costs 3 local calls
        text, chunks, info = self.chat([{"role": "system", "content": "You are helpful."}, {"role": "user", "content": "Hello there, how are you today?"}])
        usage = next(c["usage"] for c in chunks if c.get("usage"))
        sent = self.last_upstream()
        self.assertTrue(sent["stream_options"]["include_usage"])           # real usage was requested
        self.assertNotIn("atlas_context_flags", sent)
        expected = math.ceil(len(fake_llama_swap.template(sent["messages"])) / 4)
        self.assertEqual(info["prompt_tokens_exact"], expected)            # counted before send
        self.assertEqual(usage["prompt_tokens"], expected)                 # and confirmed after
        self.assertEqual(info["prompt_chars"], sum(len(m["content"]) for m in sent["messages"]))

    def test_exact_count_skipped_for_unloaded_model(self):
        _, _, info = self.chat([{"role": "user", "content": "hi"}], model="coder")  # /running lists only assist
        self.assertNotIn("prompt_tokens_exact", info)

    def test_memory_goes_into_the_prompt_and_can_be_switched_off(self):
        code, raw, _ = self.req("/api/memory", {"action": "add", "text": "Call me Jay and answer in short steps"})
        self.assertEqual(code, 200, raw)
        text, _, info = self.chat([{"role": "user", "content": "What should you call me?"}])
        self.assertIn("memory=yes", text)
        self.assertEqual(info["memory_count"], 1)
        self.assertIn("Call me Jay", self.last_upstream()["messages"][0]["content"])
        code, raw, _ = self.req("/api/memory")
        self.assertEqual(len(json.loads(raw)["items"]), 1)
        _, _, _ = self.req("/v1/chat/completions", {"model": "assist", "stream": True, "atlas_context_flags": {"memory": False},
                                                    "messages": [{"role": "user", "content": "again"}]})
        self.assertNotIn("ATLAS MEMORY", json.dumps(self.last_upstream()["messages"]))
        self.assertEqual(self.req("/api/memory", {"action": "nope"})[0], 400)

    def test_library_retrieval_is_filtered_and_titled(self):
        code, raw, _ = self.req("/api/library/import", {"name": "lighthouse.md", "content":
                                "# Kestrel Light\nThe storm broke the lantern glass. Mara fixed the lens with a brass sextant.\n" * 3})
        self.assertIn(code, (200, 201), raw)
        self.req("/api/library/import", {"name": "recipes.md", "content": "# Soup\nBoil carrots and onions for twenty minutes.\n"})
        text, _, info = self.chat([{"role": "user", "content": "How was the lantern glass and lens fixed after the storm?"}])
        self.assertIn("knowledge=yes", text)
        self.assertEqual(info["knowledge_titles"], ["lighthouse.md"])        # soup recipe filtered out
        self.assertIn("[lighthouse.md]", self.last_upstream()["messages"][0]["content"])
        text, _, info = self.chat([{"role": "user", "content": "zzqx unrelated"}])
        self.assertEqual(info["knowledge_count"], 0)

    def test_compact_endpoint(self):
        msgs = [{"role": "user", "content": f"message {i} about the VIP store"} for i in range(6)]
        code, raw, _ = self.req("/api/context/compact", {"model": "assist", "messages": msgs, "summary": "", "max_chars": 5000})
        d = json.loads(raw)
        self.assertEqual(code, 200, raw)
        self.assertTrue(d["summary"].startswith("SUMMARY"))
        self.assertGreater(d["usage"]["prompt_tokens"], 0)
        self.assertEqual(self.req("/api/context/compact", {"model": "assist"})[0], 400)


if __name__ == "__main__":
    unittest.main()
