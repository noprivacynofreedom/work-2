import no_real_keys  # noqa: F401  (must run before cloud_llm is imported)
"""Cloud pipeline of /swarm: Gemini plans, bots do one portion, Gemini combines, tests run, DeepSeek reviews.
Local stub server only: no real network, no real keys. The generated tests really run (python unittest)."""
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
import swarm_pipeline as PIPE  # noqa: E402
import cloud_llm  # noqa: E402
import swarm_run  # noqa: E402

SECRET = "SECRET-KEY-123"
SEEN = []
MODE = {"fail": False, "plan": None, "test_passes": True}
BOT_A, BOT_B = "10x: SDE", "10x: QA Engineer"


def combined_text():
    expect = "5" if MODE["test_passes"] else "6"
    return ("## Result\nHere is the code.\n\nFILE: calc.py\n```python\ndef add(a, b):\n    return a + b\n```\n\n"
            "FILE: test_calc.py\n```python\nimport os, unittest\nfrom calc import add\n\n"
            "class T(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(2, 3), " + expect + ")\n"
            "    def test_no_keys_leak(self):\n        self.assertIsNone(os.environ.get('GEMINI_API_KEY'))\n"
            "        self.assertIsNone(os.environ.get('OPENROUTER_API_KEY'))\n```\n")


class Stub(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        text = json.dumps(body)
        SEEN.append({"path": self.path, "text": text})
        if MODE["fail"]:
            self.send_response(500)
            self.end_headers()
            return
        if "gemini" in self.path:
            if "Split the goal" in text:
                answer = MODE["plan"] if MODE["plan"] is not None else json.dumps(
                    [{"bot": BOT_A, "portion": "PORTION-A write add()"}, {"bot": BOT_B, "portion": "PORTION-B write tests"}])
            else:
                answer = combined_text()
            out = {"candidates": [{"content": {"parts": [{"text": answer}]}}]}
        else:
            out = {"choices": [{"message": {"content": "DEEPSEEK-REVIEW"}}]}
        raw = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *a):
        pass


LOCAL_PROMPTS = []


def local_llm(prompt, temperature=0, max_tokens=0, model=None):
    LOCAL_PROMPTS.append(prompt)
    return "LOCAL-ANSWER"


def run_pipeline(goal="build a calculator"):
    run = swarm_run.start(goal, [{"agent": BOT_A, "task": "first job A"}, {"agent": BOT_B, "task": "first job B"}],
                          call_llm=local_llm, pipeline=True)
    final = run["steps"][-1]["conversation_id"]
    for _ in range(300):
        if OPS.swarm_log(final)["done"]:
            break
        time.sleep(0.1)
    log = OPS.swarm_log(final)
    return run, final, log, " ".join(l["message"] for l in log["lines"])


class Pipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._old_db = OPS.DB_PATH
        OPS.DB_PATH = Path(tempfile.mkdtemp(prefix="atlas-pipeline-")) / "obs.sqlite3"
        cls.data = tempfile.mkdtemp(prefix="atlas-pipeline-data-")
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        os.environ["ATLAS_GEMINI_URL"] = base + "/gemini"
        os.environ["ATLAS_OPENROUTER_URL"] = base + "/openrouter"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        OPS.DB_PATH = cls._old_db
        for k in ("ATLAS_GEMINI_URL", "ATLAS_OPENROUTER_URL"):
            os.environ.pop(k, None)

    def setUp(self):
        old_waits = cloud_llm.RETRY_WAITS
        cloud_llm.RETRY_WAITS = (0, 0)  # a failing stub must not make the test wait for real
        self.addCleanup(setattr, cloud_llm, "RETRY_WAITS", old_waits)
        keys = ("GEMINI_API_KEY", "OPENROUTER_API_KEY", "ATLAS_CLOUD_SWARM", "ATLAS_DATA_DIR", "ATLAS_SWARM_RUN_TESTS")
        self._saved = {k: os.environ.get(k) for k in keys}
        self.addCleanup(self._restore)
        SEEN.clear()
        LOCAL_PROMPTS.clear()
        MODE.update(fail=False, plan=None, test_passes=True)
        os.environ["GEMINI_API_KEY"] = SECRET
        os.environ["OPENROUTER_API_KEY"] = SECRET
        os.environ["ATLAS_DATA_DIR"] = self.data
        os.environ.pop("ATLAS_CLOUD_SWARM", None)
        os.environ.pop("ATLAS_SWARM_RUN_TESTS", None)

    def _restore(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_full_pipeline_with_passing_tests(self):
        run, final, log, text = run_pipeline()
        self.assertTrue(run["pipeline"])
        self.assertEqual(log["status"], "completed")
        res = OPS.swarm_result(final)["result"]
        self.assertEqual(res["where"], {"plan": "Gemini", "combine": "Gemini", "review": "DeepSeek"})
        self.assertEqual(res["tests"]["status"], "passed")
        self.assertIn("TESTS PASSED", res["tests"]["text"])  # also proves no API key reached the generated tests
        self.assertEqual(res["review"], "DEEPSEEK-REVIEW")
        self.assertIn("def add", res["combined"])
        self.assertEqual([s["path"] for s in SEEN], ["/gemini", "/gemini", "/openrouter"])
        self.assertIn("tests PASSED", text)
        routes = log["routes"]  # the connection rail: where each stage ran
        self.assertEqual({k: [(h["where"], h["state"]) for h in v] for k, v in routes.items()},
                         {"plan": [("cloud", "ok")], "combine": [("cloud", "ok")], "tests": [("pc", "ok")], "review": [("cloud", "ok")]})

    def test_each_bot_sees_only_its_own_portion(self):
        run_pipeline()
        bot_prompts = [p for p in LOCAL_PROMPTS if "Your job:" in p]
        self.assertEqual(len(bot_prompts), 2)
        a = next(p for p in bot_prompts if "PORTION-A" in p)
        b = next(p for p in bot_prompts if "PORTION-B" in p)
        self.assertNotIn("PORTION-B", a)
        self.assertNotIn("PORTION-A", b)
        self.assertEqual([s["path"] for s in SEEN if "Split the goal" not in s["text"]][:1], ["/gemini"])  # only the combine call
        self.assertFalse(any("/openrouter" == s["path"] and "PORTION" in s["text"] and "Split" in s["text"] for s in SEEN))

    def test_failing_tests_are_reported_as_failed(self):
        MODE["test_passes"] = False
        _, final, log, text = run_pipeline()
        res = OPS.swarm_result(final)["result"]
        self.assertEqual(res["tests"]["status"], "failed")
        self.assertIn("TESTS FAILED", res["tests"]["text"])
        self.assertIn("tests FAILED", text)
        self.assertIn("TESTS FAILED", [s["text"] for s in SEEN if "/openrouter" == s["path"]][0])  # reviewer is told

    def test_every_cloud_step_falls_back_to_local(self):
        MODE["fail"] = True
        _, final, log, text = run_pipeline()
        self.assertEqual(log["status"], "completed")
        res = OPS.swarm_result(final)["result"]
        self.assertEqual(res["where"], {"plan": "local model", "combine": "local model", "review": "local model"})
        self.assertEqual([(h["where"], h["state"]) for h in log["routes"]["combine"]], [("cloud", "fallback"), ("pc", "ok")])
        self.assertEqual(res["review"], "LOCAL-ANSWER")
        self.assertIn("did not work", text)
        self.assertNotIn(SECRET, text + json.dumps(res))

    def test_parse_plan_accepts_short_names_and_other_keys(self):
        text = '[{"bot": "SDE", "portion": "do A"}, {"name": "10x: QA Engineer", "job": "do B"}]'
        self.assertEqual(PIPE.parse_plan(text, [BOT_A, BOT_B]), {BOT_A: "do A", BOT_B: "do B"})
        with self.assertRaises(ValueError):
            PIPE.parse_plan('[{"bot": "E", "portion": "x"}]', ["10x: SDE", "10x: QE", "10x: CTO"])  # "E" fits two bots: no guess

    def test_one_bot_needs_no_plan_and_makes_no_cloud_plan_request(self):
        run = swarm_run.start("build a calculator", [{"agent": BOT_A, "task": "first job A"}], call_llm=local_llm, pipeline=True)
        final = run["steps"][-1]["conversation_id"]
        for _ in range(300):
            if OPS.swarm_log(final)["done"]:
                break
            time.sleep(0.1)
        text = " ".join(l["message"] for l in OPS.swarm_log(final)["lines"])
        self.assertIn("There is one bot", text)
        self.assertNotIn("Plan: sending to", text)
        self.assertEqual(OPS.swarm_result(final)["result"]["plan"], {BOT_A: "first job A"})

    def test_code_files_are_saved_beside_the_answers_and_unsafe_paths_are_not(self):
        out = tempfile.mkdtemp(prefix="atlas-code-out-")
        text = ("FILE: calc.py\n```python\ndef add(a, b):\n    return a + b\n```\n\n"
                "FILE: tests/test_calc.py\n```python\nimport unittest\n```\n\n"
                "FILE: ../evil.py\n```python\nx = 1\n```\n\n"
                "FILE: C:/evil.py\n```python\nx = 1\n```\n")
        folder, n = swarm_run._save_code(out, "run1", text)
        self.assertEqual(n, 2)
        self.assertEqual(Path(folder), Path(out) / "run1" / "code")
        self.assertIn("return a + b", (Path(folder) / "calc.py").read_text(encoding="utf-8"))
        self.assertTrue((Path(folder) / "tests" / "test_calc.py").is_file())
        self.assertFalse((Path(out) / "run1" / "evil.py").exists())
        self.assertFalse((Path(out) / "evil.py").exists())
        self.assertEqual(swarm_run._save_code("", "run1", text), ("", 0))          # no folder: nothing written
        self.assertEqual(swarm_run._save_code(out, "run2", "no code here"), ("", 0))

    def test_review_fallback_model_can_be_chosen(self):
        old = os.environ.pop("ATLAS_REVIEW_LOCAL_MODEL", None)
        try:
            self.assertEqual(swarm_run._review_local_model(), "mentor")
            os.environ["ATLAS_REVIEW_LOCAL_MODEL"] = " deepseek-local "
            self.assertEqual(swarm_run._review_local_model(), "deepseek-local")
        finally:
            os.environ.pop("ATLAS_REVIEW_LOCAL_MODEL", None)
            if old is not None:
                os.environ["ATLAS_REVIEW_LOCAL_MODEL"] = old

    def test_bad_plan_keeps_first_jobs(self):
        MODE["plan"] = "not json at all"
        run, final, log, text = run_pipeline()
        self.assertIn("The plan did not work", text)
        self.assertEqual(OPS.swarm_result(final)["result"]["plan"], {BOT_A: "first job A", BOT_B: "first job B"})
        self.assertEqual(log["status"], "completed")

    def test_no_keys_means_pipeline_not_wanted_and_no_request(self):
        os.environ.pop("GEMINI_API_KEY")
        os.environ.pop("OPENROUTER_API_KEY")
        self.assertFalse(swarm_run.pipeline_wanted())
        os.environ["GEMINI_API_KEY"] = SECRET
        self.assertTrue(swarm_run.pipeline_wanted())
        os.environ["ATLAS_CLOUD_SWARM"] = "0"
        self.assertFalse(swarm_run.pipeline_wanted())

    def test_tests_off_switch(self):
        os.environ["ATLAS_SWARM_RUN_TESTS"] = "0"
        _, final, _, _ = run_pipeline()
        self.assertEqual(OPS.swarm_result(final)["result"]["tests"]["status"], "off")

    def test_stop_cancels_the_pipeline(self):
        gate = []

        def slow(prompt, temperature=0, max_tokens=0, model=None):
            while not gate:
                time.sleep(0.02)
            return "late"
        os.environ.pop("GEMINI_API_KEY")  # no cloud: the first stage is local and slow
        os.environ.pop("OPENROUTER_API_KEY")
        run = swarm_run.start("x", [{"agent": BOT_A, "task": "a"}], call_llm=slow, pipeline=True)
        final = run["steps"][-1]["conversation_id"]
        time.sleep(0.4)
        OPS.cancel_all_tasks()
        gate.append(1)
        for _ in range(100):
            if OPS.swarm_log(final)["done"]:
                break
            time.sleep(0.05)
        self.assertEqual(OPS.swarm_log(final)["status"], "cancelled")
        time.sleep(0.5)
        self.assertEqual(OPS.swarm_result(final)["result"], None)  # nothing was posted after the stop


class Helpers(unittest.TestCase):
    def test_parse_plan_accepts_fences_and_drops_unknown_bots(self):
        text = '```json\n[{"bot": "10x: sde", "portion": "do A"}, {"bot": "Ghost", "portion": "x"}]\n```'
        self.assertEqual(PIPE.parse_plan(text, [BOT_A, BOT_B]), {BOT_A: "do A"})
        with self.assertRaises(ValueError):
            PIPE.parse_plan('[{"bot": "Ghost", "portion": "x"}]', [BOT_A])

    def test_package_hint_names_the_installed_mcp_api(self):
        # 2026-11-11: the combiner wrote mcp 1.x code (FastMCP); Atlas's Python has mcp 2.x.
        two = PIPE.package_hint(lambda name: "2.0.1" if name == "mcp" else None)
        self.assertIn("from mcp.server.mcpserver import MCPServer", two)
        self.assertIn("do NOT exist", two)
        one = PIPE.package_hint(lambda name: "1.9.4")
        self.assertIn("from mcp.server.fastmcp import FastMCP", one)
        none = PIPE.package_hint(lambda name: None)
        self.assertIn("NOT installed", none)
        for hint in (two, one, none):
            self.assertIn("module that a test imports", hint)
        self.assertIn(PIPE.package_hint(), PIPE.combine_prompt("goal", [("bot", "answer")]))

    def test_unsafe_file_paths_are_never_written(self):
        text = ("FILE: ../evil.py\n```\nx=1\n```\n\nFILE: /abs/evil.py\n```\nx=1\n```\n\n"
                "FILE: C:/evil.py\n```\nx=1\n```\n\nFILE: ok/good.py\n```python\nx=1\n```\n")
        files, skipped = PIPE.extract_files(text)
        self.assertEqual(list(files), ["ok/good.py"])
        self.assertEqual(len(skipped), 3)

    def test_code_without_tests_proves_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            r = PIPE.run_tests("FILE: a.py\n```python\nx=1\n```\n", "run1", base_dir=d)
            self.assertEqual(r["status"], "no_tests")
            self.assertIn("NOTHING was proven", r["text"])

    def test_tests_in_a_hyphen_folder_still_run(self):
        # 2026-11-15: test in "python-calculator-261cd09b4a4f/" was never found -> "exit code 5, TESTS FAILED".
        text = ("FILE: my-app/calc.py\n```python\ndef add(a, b): return a + b\n```\n\n"
                "FILE: my-app/test_calc.py\n```python\nimport unittest\nfrom calc import add\n"
                "class T(unittest.TestCase):\n    def test_add(self): self.assertEqual(add(1, 2), 3)\n```\n")
        with tempfile.TemporaryDirectory() as d:
            r = PIPE.run_tests(text, "run3", base_dir=d)
        self.assertEqual(r["status"], "passed", r["text"])

    def test_zero_tests_ran_is_not_a_failure(self):
        text = "FILE: a/test_x.py\n```python\nx = 1\n```\n"  # a test file with no test cases
        with tempfile.TemporaryDirectory() as d:
            r = PIPE.run_tests(text, "run4", base_dir=d)
        self.assertEqual(r["status"], "no_tests", r["text"])

    def test_no_code_means_no_tests(self):
        self.assertEqual(PIPE.run_tests("Only words here.", "run2", base_dir=tempfile.gettempdir())["status"], "no_code")

    def test_clean_env_drops_keys(self):
        os.environ["MY_FAKE_API_KEY"] = "x"
        try:
            self.assertNotIn("MY_FAKE_API_KEY", PIPE.clean_env())
        finally:
            os.environ.pop("MY_FAKE_API_KEY")


if __name__ == "__main__":
    unittest.main()
