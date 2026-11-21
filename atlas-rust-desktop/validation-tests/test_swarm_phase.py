import no_real_keys  # noqa: F401  (must run before cloud_llm is imported)
import os, sys, tempfile, unittest, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src-tauri", "resources", "atlas"))


class SwarmPhaseTest(unittest.TestCase):
    def test_phase_is_reported_and_hidden_from_lines(self):
        os.environ["ATLAS_DATA_DIR"] = tempfile.mkdtemp()
        import atlas_observability as O, swarm_run as R
        conv = "p-" + uuid.uuid4().hex[:8] + "-final"  # fresh id: the test DB can hold rows of an earlier run
        sub = O.submit_task({"type": "swarm_" + conv, "conversation_id": conv, "bot_id": "Swarm Lead", "payload": {}})
        f = {"task_id": sub["task_id"], "trace_id": sub["trace_id"], "conversation_id": conv}
        self.assertEqual(O.swarm_log(conv)["phase"], "")
        R._phase(f, "plan"); R._note(f, "hello"); R._phase(f, "tests")
        d = O.swarm_log(conv)
        self.assertEqual(d["phase"], "tests")
        self.assertEqual([l["kind"] for l in d["lines"]], ["swarm.log"])


if __name__ == "__main__":
    unittest.main()
