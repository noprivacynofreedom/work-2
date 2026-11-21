"""Live stage view: the swarm keeps what each step's model is writing now, and llm.py streams it piece by piece."""
import json
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "src-tauri" / "resources" / "atlas"
sys.path.insert(0, str(APP))
import atlas_observability as OPS  # noqa: E402
import llm  # noqa: E402
import swarm_run  # noqa: E402


class SSE(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for d in ({"reasoning_content": "hmm "}, {"content": "Hel"}, {"content": "lo"}):
            self.wfile.write(b"data: " + json.dumps({"choices": [{"delta": d}]}).encode() + b"\n\n")
        self.wfile.write(b"data: [DONE]\n\n")

    def log_message(self, *a):
        pass


class SwarmLive(unittest.TestCase):
    def test_stream_parses_text_and_thinking(self):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), SSE)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        old = llm._base_url
        llm._base_url = lambda: f"http://127.0.0.1:{srv.server_address[1]}"
        self.addCleanup(setattr, llm, "_base_url", old)
        got = []
        text = llm.call_llm("hi", model="x", local_only=True, on_text=lambda k, p: got.append((k, p)))
        self.assertEqual(text, "Hello")
        self.assertEqual(got, [("think", "hmm "), ("text", "Hel"), ("text", "lo")])

    def test_bot_live_view_fills_while_the_model_writes(self):
        old_db = OPS.DB_PATH
        OPS.DB_PATH = Path(tempfile.mkdtemp(prefix="atlas-live-")) / "obs.sqlite3"
        self.addCleanup(setattr, OPS, "DB_PATH", old_db)
        seen = {}

        def streaming_llm(prompt, temperature=0, max_tokens=0, model=None, on_text=None, **kw):
            on_text("text", "part one, ")
            seen["mid"] = swarm_run.live_get(conv)["bot"]["text"]
            on_text("text", "part two")
            return "part one, part two"

        run = swarm_run.start("goal", [{"agent": "10x: SDE", "task": "t"}], call_llm=streaming_llm)
        conv = run["steps"][0]["conversation_id"]
        for _ in range(100):
            v = swarm_run.live_get(conv).get("bot")
            if v and v["done"]:
                break
            time.sleep(0.05)
        self.assertEqual(seen["mid"], "part one, ")  # visible before the answer is finished
        self.assertEqual(v["text"], "part one, part two")
        self.assertEqual((v["where"], v["label"]), ("pc", "This PC"))

    def test_stub_without_on_text_still_works(self):
        self.assertFalse(swarm_run._streams(lambda prompt, temperature=0, max_tokens=0, model=None: ""))
        self.assertTrue(swarm_run._streams(llm.call_llm))


if __name__ == "__main__":
    unittest.main()
