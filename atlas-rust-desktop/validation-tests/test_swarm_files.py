import no_real_keys  # noqa: F401  (must run before cloud_llm is imported)
import os, sys, tempfile, time, unittest
os.environ["ATLAS_OBSERVABILITY_DB"] = os.path.join(tempfile.mkdtemp(), "o.sqlite3")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src-tauri", "resources", "atlas"))
import atlas_observability as OPS
import swarm_run


def wait_done(convs, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        if all(OPS.swarm_log(c)["done"] for c in convs):
            return True
        time.sleep(0.05)
    return False


class SwarmFiles(unittest.TestCase):
    def test_each_bot_answer_is_saved_as_a_file_and_the_log_says_where(self):
        out = os.path.join(tempfile.mkdtemp(), "swarm-output")
        run = swarm_run.start("make a calculator", [{"agent": "10x: SDE", "task": "write it"}, {"agent": "10x: QA Engineer", "task": "test it"}],
                              call_llm=lambda *a, **k: "Here is my plan.", out_dir=out)
        convs = [s["conversation_id"] for s in run["steps"]]
        self.assertTrue(wait_done(convs))
        folder = os.path.join(out, run["run_id"])
        names = sorted(os.listdir(folder))
        self.assertEqual(names, ["10x_ QA Engineer.md", "10x_ SDE.md"])
        text = open(os.path.join(folder, "10x_ SDE.md"), encoding="utf-8").read()
        self.assertIn("Here is my plan.", text)
        self.assertIn("make a calculator", text)
        log = " ".join(l["message"] for l in OPS.swarm_log(convs[0])["lines"])
        self.assertIn("saved as a file", log)

    def test_unwritable_folder_never_stops_the_swarm(self):
        blocker = os.path.join(tempfile.mkdtemp(), "file")
        open(blocker, "w").close()  # a file where a folder is needed
        run = swarm_run.start("x", [{"agent": "10x: SDE", "task": "write it"}],
                              call_llm=lambda *a, **k: "answer", out_dir=os.path.join(blocker, "sub"))
        c = run["steps"][0]["conversation_id"]
        self.assertTrue(wait_done([c]))
        log = " ".join(l["message"] for l in OPS.swarm_log(c)["lines"])
        self.assertIn("Done. This is what I came up with", log)
        self.assertNotIn("saved as a file", log)

    def test_no_folder_means_no_files(self):
        self.assertEqual(swarm_run._save_file("", "r1", "bot", "text"), "")


if __name__ == "__main__":
    unittest.main()
