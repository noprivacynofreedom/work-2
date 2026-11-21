"""Coding swarm: cloud routing is opt-in, falls back to local, and workers get their own folders."""
import os, sys, tempfile, types, unittest
from pathlib import Path
from unittest import mock
import _paths  # noqa: F401
sys.path.insert(0, str(_paths.APP / "agents"))
import atlas_coding_swarm as swarm


class FakeLocal:
    def __init__(self): self.calls = []
    def call_llm(self, prompt, temperature=0, max_tokens=0, model=None):
        self.calls.append(model); return "local answer"


def fake_litellm(text="cloud answer", fail=False):
    mod = types.ModuleType("litellm")
    mod.calls = []
    def completion(model, messages, temperature, timeout):
        mod.calls.append(model)
        if fail: raise ConnectionError("offline")
        msg = types.SimpleNamespace(content=text)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])  # choices is a LIST
    mod.completion = completion
    return mod


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.local = FakeLocal()
        self.patches = [mock.patch.object(swarm, "llm", self.local),
                        mock.patch.dict(os.environ, {}, clear=False)]
        for p in self.patches: p.start()
        for k in ("ATLAS_CLOUD_ROUTING", "ATLAS_SWARM_MEMORY_DIR", "ATLAS_DATA_DIR"): os.environ.pop(k, None)
    def tearDown(self):
        for p in reversed(self.patches): p.stop()

    def test_default_never_touches_the_cloud(self):
        lite = fake_litellm()
        with mock.patch.dict(sys.modules, {"litellm": lite}):
            for role in ("architect", "reviewer", "coder", "debugger"):
                self.assertEqual(swarm._model("p", "coder", 10, role=role), "local answer")
        self.assertEqual(lite.calls, [])

    def test_cloud_only_for_planner_and_reviewer_when_turned_on(self):
        os.environ["ATLAS_CLOUD_ROUTING"] = "1"
        lite = fake_litellm()
        with mock.patch.dict(sys.modules, {"litellm": lite}):
            self.assertEqual(swarm._model("p", role="architect"), "cloud answer")
            self.assertEqual(swarm._model("p", role="reviewer"), "cloud answer")
            self.assertEqual(swarm._model("p", role="coder"), "local answer")
            self.assertEqual(swarm._model("p", role="debugger"), "local answer")
        self.assertEqual(lite.calls, [swarm.CLOUD_PLANNER, swarm.CLOUD_REVIEWER])

    def test_cloud_failure_falls_back_to_local(self):
        os.environ["ATLAS_CLOUD_ROUTING"] = "1"
        with mock.patch.dict(sys.modules, {"litellm": fake_litellm(fail=True)}):
            self.assertEqual(swarm._model("p", role="architect"), "local answer")

    def test_missing_litellm_falls_back_to_local(self):
        os.environ["ATLAS_CLOUD_ROUTING"] = "1"
        with mock.patch.dict(sys.modules, {"litellm": None}):  # None makes "import litellm" raise ImportError
            self.assertEqual(swarm._model("p", role="reviewer"), "local answer")

    def test_litellm_is_not_a_top_level_import(self):
        import ast
        tree = ast.parse(open(swarm.__file__, encoding="utf-8").read())
        top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        names = {a.name.split(".")[0] for n in top for a in n.names} | {n.module.split(".")[0] for n in top if isinstance(n, ast.ImportFrom) and n.module}
        self.assertNotIn("litellm", names)

    def test_no_drive_path_and_no_files_without_a_memory_dir(self):
        self.assertIsNone(swarm._history_file("coder"))
        self.assertNotIn("F:/", open(swarm.__file__, encoding="utf-8").read())

    def test_history_goes_to_the_chosen_folder_and_holds_no_prompt_text(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["ATLAS_SWARM_MEMORY_DIR"] = d
            swarm._model("SECRET PROMPT TEXT", role="coder")
            text = (Path(d) / "coder" / "thinking_history.jsonl").read_text(encoding="utf-8")
        self.assertIn('"route": "local"', text); self.assertNotIn("SECRET", text)

    def test_unwritable_history_never_breaks_a_run(self):
        with tempfile.NamedTemporaryFile() as f:  # a FILE used as a folder: mkdir must fail
            os.environ["ATLAS_SWARM_MEMORY_DIR"] = os.path.join(f.name, "sub")
            self.assertEqual(swarm._model("p", role="coder"), "local answer")

    def test_parallel_workers_get_separate_folders(self):
        with tempfile.TemporaryDirectory() as d:
            rows = [{"path": "a.py", "content": "1"}]
            one = swarm._write_files(Path(d), "demo", "tsk_1234567890", rows)
            two = swarm._write_files(Path(d), "demo", "tsk_1234567890", rows)  # same task id: old code raised here
            self.assertNotEqual(one["workspace"], two["workspace"])

    def test_json_parser_does_not_invent_success(self):
        with self.assertRaises(ValueError): swarm._json_from_model('{"goal_reached": false, "x": ')


if __name__ == "__main__":
    unittest.main()
