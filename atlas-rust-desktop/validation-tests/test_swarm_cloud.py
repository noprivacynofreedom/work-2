import no_real_keys  # noqa: F401  (must run before cloud_llm is imported)
"""Cloud steps of /swarm (Gemini + DeepSeek). Uses a local stub server: no real network, no real keys."""
import json
import os
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
import cloud_llm  # noqa: E402
import swarm_run  # noqa: E402

SECRET = "SECRET-KEY-123"
SEEN = []
MODE = {"fail": False}


class Stub(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        SEEN.append({"path": self.path, "auth": self.headers.get("Authorization"), "gkey": self.headers.get("x-goog-api-key"), "body": body})
        if MODE["fail"]:
            self.send_response(500)
            self.end_headers()
            return
        if "gemini" in self.path:
            out = {"candidates": [{"content": {"parts": [{"text": "GEMINI-ANSWER"}]}}]}
        else:
            out = {"choices": [{"message": {"content": "DEEPSEEK-ANSWER"}}]}
        raw = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *a):
        pass


def local_llm(prompt, temperature=0, max_tokens=0, model=None):
    return "LOCAL-ANSWER"


def run_swarm(agents):
    run = swarm_run.start("test goal", [{"agent": a, "task": "t"} for a in agents], call_llm=local_llm)
    convs = [s["conversation_id"] for s in run["steps"]]
    for _ in range(100):
        done = {e["conversation_id"] for e in OPS.events(0, 2000) if e.get("kind") in ("swarm.done", "swarm.failed")}
        if all(c in done for c in convs):
            break
        time.sleep(0.1)
    evs = OPS.events(0, 2000)
    return {c: [e for e in evs if e.get("conversation_id") == c] for c in convs}, run


def last_text(events):
    return [e["message"] for e in events if e["kind"] == "swarm.done"][-1]


class SwarmCloud(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Own database, so task counts of other test files are not changed. Restored in tearDownClass.
        cls._old_db = OPS.DB_PATH
        OPS.DB_PATH = Path(tempfile.mkdtemp(prefix="atlas-swarm-cloud-")) / "obs.sqlite3"
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        os.environ["ATLAS_GEMINI_URL"] = base + "/gemini"
        os.environ["ATLAS_OPENROUTER_URL"] = base + "/openrouter"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        OPS.DB_PATH = cls._old_db
        os.environ.pop("ATLAS_GEMINI_URL", None)
        os.environ.pop("ATLAS_OPENROUTER_URL", None)

    def setUp(self):
        old_waits = cloud_llm.RETRY_WAITS
        cloud_llm.RETRY_WAITS = (0, 0)  # a failing stub must not make the test wait for real
        self.addCleanup(setattr, cloud_llm, "RETRY_WAITS", old_waits)
        self._saved = {k: os.environ.get(k) for k in ("GEMINI_API_KEY", "OPENROUTER_API_KEY", "ATLAS_CLOUD_SWARM")}
        self.addCleanup(self._restore)
        SEEN.clear()
        MODE["fail"] = False
        os.environ["GEMINI_API_KEY"] = SECRET
        os.environ["OPENROUTER_API_KEY"] = SECRET
        os.environ.pop("ATLAS_CLOUD_SWARM", None)

    def _restore(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_planner_uses_gemini_reviewer_uses_deepseek_coder_stays_local(self):
        out, _ = run_swarm(["10x: Principal Architect", "10x: QA Engineer", "10x: SDE"])
        texts = [last_text(v) for v in out.values()]
        self.assertIn("GEMINI-ANSWER", texts[0])
        self.assertIn("DEEPSEEK-ANSWER", texts[1])
        self.assertIn("LOCAL-ANSWER", texts[2])
        # Bots are grouped by model alias, so the order of the two cloud calls is not fixed.
        self.assertEqual(sorted(s["path"] for s in SEEN), ["/gemini", "/openrouter"])
        self.assertEqual(next(s for s in SEEN if s["path"] == "/gemini")["gkey"], SECRET)
        self.assertEqual(next(s for s in SEEN if s["path"] == "/openrouter")["auth"], "Bearer " + SECRET)

    def test_chat_says_it_is_cloud(self):
        out, _ = run_swarm(["10x: Principal Architect"])
        msgs = " ".join(e["message"] for v in out.values() for e in v)
        self.assertIn("Gemini in the cloud", msgs)

    def test_no_key_means_local_and_no_request(self):
        os.environ.pop("GEMINI_API_KEY")
        out, _ = run_swarm(["10x: Principal Architect"])
        self.assertIn("LOCAL-ANSWER", last_text(list(out.values())[0]))
        self.assertEqual(SEEN, [])

    def test_cloud_off_switch(self):
        os.environ["ATLAS_CLOUD_SWARM"] = "0"
        out, _ = run_swarm(["10x: QA Engineer"])
        self.assertIn("LOCAL-ANSWER", last_text(list(out.values())[0]))
        self.assertEqual(SEEN, [])

    def test_cloud_failure_falls_back_to_local_without_leaking_key(self):
        MODE["fail"] = True
        out, _ = run_swarm(["10x: QA Engineer"])
        evs = list(out.values())[0]
        self.assertIn("LOCAL-ANSWER", last_text(evs))
        msgs = " ".join(e["message"] for e in evs)
        self.assertIn("did not work", msgs)
        self.assertNotIn(SECRET, msgs)

    def test_route_rail_records_cloud_then_local_fallback(self):
        MODE["fail"] = True
        out, _ = run_swarm(["10x: QA Engineer"])
        hops = OPS.swarm_log(list(out)[0])["routes"]["bot"]
        self.assertEqual([(h["where"], h["state"]) for h in hops], [("cloud", "fallback"), ("pc", "ok")])
        self.assertEqual(hops[0]["label"], "DeepSeek")
        self.assertTrue(all(h["started"] <= h["ts"] for h in hops))  # the UI shows ts - started as the time taken
        self.assertNotIn(SECRET, json.dumps(hops))

    def test_route_rail_records_cloud_ok_and_no_key(self):
        out, _ = run_swarm(["10x: Principal Architect"])
        self.assertEqual([(h["where"], h["state"]) for h in OPS.swarm_log(list(out)[0])["routes"]["bot"]], [("cloud", "ok")])
        os.environ.pop("GEMINI_API_KEY")
        out, _ = run_swarm(["10x: CTO"])
        self.assertEqual([(h["where"], h["state"]) for h in OPS.swarm_log(list(out)[0])["routes"]["bot"]], [("cloud", "nokey"), ("pc", "ok")])

    def test_route_lines_are_hidden_and_status_has_no_key(self):
        out, _ = run_swarm(["10x: Principal Architect"])
        self.assertNotIn("swarm.route", [l["kind"] for l in OPS.swarm_log(list(out)[0])["lines"]])
        st = cloud_llm.status()
        self.assertTrue(st["providers"]["gemini"]["key"])
        self.assertNotIn(SECRET, json.dumps(st))

    def test_key_never_written_to_the_log(self):
        run_swarm(["10x: Principal Architect", "10x: QA Engineer"])
        self.assertNotIn(SECRET, json.dumps(OPS.events(0, 5000)))


if __name__ == "__main__":
    unittest.main()
