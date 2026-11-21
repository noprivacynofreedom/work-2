import no_real_keys  # noqa: F401  (must run before cloud_llm is imported)
import os, sys, tempfile, time, unittest
os.environ["ATLAS_OBSERVABILITY_DB"] = os.path.join(tempfile.mkdtemp(), "o.sqlite3")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src-tauri", "resources", "atlas"))
import atlas_observability as OPS
import swarm_run

def wait_done(convs, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        if all(OPS.swarm_log(c)["done"] for c in convs): return True
        time.sleep(0.05)
    return False

class SwarmRun(unittest.TestCase):
    def test_each_bot_gets_a_plain_log_and_result(self):
        before = OPS.task_snapshot()["counts"].get("completed", 0)
        run = swarm_run.start("make a calculator", [{"agent": "10x: SDE", "task": "write it"}, {"agent": "10x: QA Engineer", "task": "test it"}],
                              call_llm=lambda *a, **k: "Here is my plan for you.")
        convs = [s["conversation_id"] for s in run["steps"]]
        self.assertTrue(wait_done(convs))
        for c in convs:
            text = " ".join(l["message"] for l in OPS.swarm_log(c)["lines"])
            self.assertIn("Waiting in line", text); self.assertIn("My job:", text); self.assertIn("Done. This is what I came up with", text)
        self.assertEqual(OPS.task_snapshot()["counts"].get("completed", 0) - before, 2)

    def test_model_failure_is_explained_not_hidden(self):
        def boom(*a, **k): raise RuntimeError("model is offline")
        run = swarm_run.start("x", [{"agent": "10x: SDE", "task": "write it"}], call_llm=boom)
        c = run["steps"][0]["conversation_id"]; self.assertTrue(wait_done([c]))
        self.assertIn("Something went wrong", " ".join(l["message"] for l in OPS.swarm_log(c)["lines"]))

    def test_stop_cancels_waiting_bots(self):
        gate = []
        def slow(*a, **k):
            while not gate: time.sleep(0.02)
            return "late"
        run = swarm_run.start("x", [{"agent": "10x: SDE", "task": "a"}, {"agent": "10x: CTO", "task": "b"}], call_llm=slow)
        time.sleep(0.3); OPS.cancel_all_tasks(); gate.append(1)
        convs = [s["conversation_id"] for s in run["steps"]]; self.assertTrue(wait_done(convs))
        for c in convs: self.assertIn("You stopped the swarm", " ".join(l["message"] for l in OPS.swarm_log(c)["lines"]))

    def _first_done_snapshot(self, conv, timeout=5):
        """Poll like the chat window does. Return the first reply that says done."""
        end = time.time() + timeout
        while time.time() < end:
            d = OPS.swarm_log(conv)
            if d["done"]: return d
            time.sleep(0.001)
        self.fail("swarm chat never finished")

    def test_closing_line_is_there_the_moment_the_chat_sees_done(self):
        for i in range(15):  # the old code wrote this line after the status change, so a poll could miss it
            ok = swarm_run.start("x", [{"agent": "10x: SDE", "task": "t"}], call_llm=lambda *a, **k: "answer")
            d = self._first_done_snapshot(ok["steps"][0]["conversation_id"])
            self.assertEqual(d["status"], "completed")
            self.assertIn("Done. This is what I came up with", " ".join(l["message"] for l in d["lines"]))
            def boom(*a, **k): raise RuntimeError("model is offline")
            bad = swarm_run.start("x", [{"agent": "10x: SDE", "task": "t"}], call_llm=boom)
            d = self._first_done_snapshot(bad["steps"][0]["conversation_id"])
            self.assertEqual(d["status"], "failed")
            self.assertIn("model is offline", d["error"])
            self.assertIn("Something went wrong", " ".join(l["message"] for l in d["lines"]))

    def test_stopped_bots_report_cancelled(self):
        gate = []
        def slow(*a, **k):
            while not gate: time.sleep(0.02)
            return "late"
        run = swarm_run.start("x", [{"agent": "10x: SDE", "task": "a"}], call_llm=slow)
        time.sleep(0.3); OPS.cancel_all_tasks(); gate.append(1)
        d = self._first_done_snapshot(run["steps"][0]["conversation_id"])
        self.assertEqual(d["status"], "cancelled")

    def test_unexpected_crash_after_claim_is_a_reported_failure(self):
        real = OPS.heartbeat
        def bad(agent_id, token, payload):
            if payload.get("status") == "busy": raise RuntimeError("disk full")
            return real(agent_id, token, payload)
        OPS.heartbeat = bad
        try:
            run = swarm_run.start("x", [{"agent": "10x: SDE", "task": "t"}], call_llm=lambda *a, **k: "answer")
            d = self._first_done_snapshot(run["steps"][0]["conversation_id"])
        finally:
            OPS.heartbeat = real
        self.assertEqual(d["status"], "failed")
        self.assertIn("inside Atlas", " ".join(l["message"] for l in d["lines"]))

if __name__ == "__main__":
    unittest.main()
