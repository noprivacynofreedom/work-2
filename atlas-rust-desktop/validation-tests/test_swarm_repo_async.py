import no_real_keys  # noqa: F401  (must run before cloud_llm is imported)
"""/swarm reads the repo, writes real .py/.rs files, and never waits forever.

- repo_context: read-only snapshot of the Workspace folder, without secrets, junk folders or symlinks.
- Bots and the Swarm Lead get that snapshot in their prompt. Code blocks become real files.
- Async: start() returns at once, two runs take turns on one machine, a hung bot is closed on a time-out,
  and /swarm stop does not wait for a bot that is still thinking.
No network, no real model: call_llm is a fake.
"""
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

os.environ["ATLAS_OBSERVABILITY_DB"] = os.path.join(tempfile.mkdtemp(), "o.sqlite3")
APP = Path(__file__).resolve().parents[1] / "src-tauri" / "resources" / "atlas"
sys.path.insert(0, str(APP))
import atlas_observability as OPS  # noqa: E402
import cloud_llm  # noqa: E402
import compute_peers  # noqa: E402
import repo_context  # noqa: E402
import swarm_pipeline as PIPE  # noqa: E402
import swarm_run  # noqa: E402

SDE, QA = "10x: SDE", "10x: QA Engineer"


def wait_done(convs, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        if all(OPS.swarm_log(c)["done"] for c in convs):
            return True
        time.sleep(0.05)
    return False


def log_of(conv):
    return " ".join(line["message"] for line in OPS.swarm_log(conv)["lines"])


def make_repo():
    root = Path(tempfile.mkdtemp(prefix="atlas-repo-"))
    (root / "src").mkdir()
    (root / "src" / "calculator.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (root / "README.md").write_text("# Demo\n", encoding="utf-8")
    (root / ".env").write_text("API_KEY=LEAKED-SECRET\n", encoding="utf-8")
    (root / "server.key").write_text("LEAKED-SECRET\n", encoding="utf-8")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "junk.js").write_text("calculator junk\n", encoding="utf-8")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("calculator\n", encoding="utf-8")
    return root


class RepoContext(unittest.TestCase):
    def test_lists_files_shows_matches_and_hides_secrets(self):
        root = make_repo()
        ctx = repo_context.build(str(root), "fix the calculator add function")
        text = ctx["text"]
        self.assertIn("src/calculator.py", text)
        self.assertIn("README.md", text)
        self.assertIn("return a + b", text)               # the matching file is shown
        self.assertEqual(ctx["shown"], ["src/calculator.py"])
        self.assertNotIn("LEAKED-SECRET", text)
        self.assertNotIn(".env", text)
        self.assertNotIn("server.key", text)
        self.assertNotIn("node_modules", text)
        self.assertNotIn(".git/", text)
        self.assertIn("calculator.py", ctx["note"])

    def test_symlink_out_of_the_folder_is_not_followed(self):
        root, outside = make_repo(), Path(tempfile.mkdtemp())
        (outside / "calculator_secret.py").write_text("OUTSIDE-TEXT calculator\n", encoding="utf-8")
        try:
            os.symlink(outside, root / "linked")
            os.symlink(outside / "calculator_secret.py", root / "link.py")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks need extra rights on this machine")
        text = repo_context.build(str(root), "calculator")["text"]
        self.assertNotIn("OUTSIDE-TEXT", text)
        self.assertNotIn("linked/", text)

    def test_size_limit_and_missing_folder(self):
        root = make_repo()
        for i in range(300):
            (root / f"calculator_{i:03}.py").write_text("calculator " * 300, encoding="utf-8")
        ctx = repo_context.build(str(root), "calculator", max_chars=2000)
        self.assertLessEqual(len(ctx["text"]), 2000)
        none = repo_context.build("", "x")
        self.assertEqual(none["text"], "")
        self.assertIn("No Workspace folder", none["note"])


class RealFiles(unittest.TestCase):
    TEXT = ("FILE: app/main.py\n```python\nprint('hi')\n```\n"
            "And a bare one:\n```rust\nfn main() {}\n```\n"
            "```py\nx = 1\n```\n```js\nconsole.log(1)\n```\n")

    def test_loose_extract_saves_bare_python_and_rust_blocks(self):
        files, _ = PIPE.extract_files(self.TEXT, loose=True)
        self.assertEqual(sorted(files), ["app/main.py", "snippet_1.rs", "snippet_2.py"])
        self.assertEqual(files["snippet_1.rs"], "fn main() {}\n")

    def test_strict_extract_is_unchanged(self):
        files, _ = PIPE.extract_files(self.TEXT)
        self.assertEqual(sorted(files), ["app/main.py"])  # the tests only run files the model named

    def test_bot_reads_the_repo_and_its_code_becomes_real_files(self):
        root, out = make_repo(), os.path.join(tempfile.mkdtemp(), "swarm-output")
        prompts = []

        def llm(prompt, **kw):
            prompts.append(prompt)
            return ("Plan.\n\nFILE: src/calculator.py\n```python\ndef add(a, b):\n    return a + b\n```\n"
                    "FILE: src/lib.rs\n```rust\npub fn add(a: i32, b: i32) -> i32 { a + b }\n```\n")
        with mock.patch.object(compute_peers, "route", return_value=(None, None, None)):
            run = swarm_run.start("fix the calculator", [{"agent": SDE, "task": "write it"}],
                                  call_llm=llm, out_dir=out, repo_root=str(root))
            conv = run["steps"][0]["conversation_id"]
            self.assertTrue(wait_done([conv]))
        self.assertIn("REPO SNAPSHOT", prompts[0])
        self.assertIn("src/calculator.py", prompts[0])
        self.assertIn("FILE: relative/path.ext", prompts[0])
        code = Path(out, run["run_id"], "code", "10x_ SDE")
        self.assertEqual((code / "src" / "calculator.py").read_text(encoding="utf-8"), "def add(a, b):\n    return a + b\n")
        self.assertTrue((code / "src" / "lib.rs").is_file())
        self.assertTrue(Path(out, run["run_id"], "10x_ SDE.md").is_file())  # the .md copy stays
        log = log_of(conv)
        self.assertIn("I read the project folder", log)
        self.assertIn("2 code file(s) as real files", log)
        self.assertEqual((root / "src" / "calculator.py").read_text(encoding="utf-8"),
                         "def add(a, b):\n    return a + b\n")  # the repo itself is never written

    def test_no_workspace_is_said_in_the_chat(self):
        run = swarm_run.start("x", [{"agent": SDE, "task": "t"}], call_llm=lambda *a, **k: "ok", repo_root="")
        conv = run["steps"][0]["conversation_id"]
        self.assertTrue(wait_done([conv]))
        self.assertIn("No Workspace folder is set", log_of(conv))

    def test_swarm_lead_combines_with_the_repo(self):
        root, prompts = make_repo(), []

        def llm(prompt, **kw):
            prompts.append(prompt)
            return "answer"
        with mock.patch.object(cloud_llm, "available", return_value=False), \
                mock.patch.object(compute_peers, "route", return_value=(None, None, None)):
            run = swarm_run.start("fix the calculator", [{"agent": SDE, "task": "a"}, {"agent": QA, "task": "b"}],
                                  call_llm=llm, pipeline=True, repo_root=str(root))
            self.assertTrue(wait_done([s["conversation_id"] for s in run["steps"]], timeout=20))
        combine = [p for p in prompts if p.startswith("Combine the team answers")]
        self.assertEqual(len(combine), 1)
        self.assertIn("THE REAL PROJECT", combine[0])
        self.assertIn("src/calculator.py", combine[0])


class Async(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(compute_peers, "route", return_value=(None, None, None))
        p.start()
        self.addCleanup(p.stop)

    def test_start_returns_before_the_repo_is_read(self):
        real = repo_context.build

        def slow(*a, **k):
            time.sleep(1.0)
            return real(*a, **k)
        with mock.patch.object(repo_context, "build", side_effect=slow):
            t0 = time.monotonic()
            run = swarm_run.start("x", [{"agent": SDE, "task": "t"}], call_llm=lambda *a, **k: "ok",
                                  repo_root=str(make_repo()))
            self.assertLess(time.monotonic() - t0, 0.5)
            self.assertTrue(wait_done([run["steps"][0]["conversation_id"]]))

    def test_two_runs_take_turns_on_one_machine(self):
        # Bots of ONE run may share the loaded model at once (ATLAS_SWARM_SLOTS), but two runs never mix on this PC.
        busy, mixed, guard = {"one": 0, "two": 0}, [False], threading.Lock()

        def llm(prompt, **kw):
            run = "one" if "team goal is: one" in prompt else "two"
            with guard:
                busy[run] += 1
                mixed[0] = mixed[0] or (busy["one"] > 0 and busy["two"] > 0)
            time.sleep(0.15)
            with guard:
                busy[run] -= 1
            return "ok"
        a = swarm_run.start("one", [{"agent": SDE, "task": "t"}, {"agent": QA, "task": "t"}], call_llm=llm)
        b = swarm_run.start("two", [{"agent": SDE, "task": "t"}, {"agent": QA, "task": "t"}], call_llm=llm)
        convs = [s["conversation_id"] for s in a["steps"] + b["steps"]]
        self.assertTrue(wait_done(convs))
        self.assertFalse(mixed[0])  # never bots of two runs on this PC at once
        for c in convs:
            self.assertIn("Done. This is what I came up with", log_of(c))

    def test_hung_bot_is_closed_on_time_out_and_late_answer_does_not_revive_it(self):
        release = threading.Event()

        def llm(prompt, **kw):
            release.wait(10)
            return "LATE ANSWER"
        sub = [{"agent": SDE, "task": "t"}, {"agent": QA, "task": "t"}]
        run_id = "swtimeout1"
        steps = []
        for i, st in enumerate(sub, 1):
            conv = f"{run_id}-{i}"
            steps.append({"conversation_id": conv, "agent": st["agent"], "task": "t", "task_type": f"swarm_{conv}",
                          "run_id": run_id, "out_dir": ""})
            OPS.submit_task({"type": f"swarm_{conv}", "conversation_id": conv, "bot_id": st["agent"], "payload": {}})
        t0 = time.monotonic()
        swarm_run.run_steps(steps, "goal", llm, seconds=0.5)
        self.assertLess(time.monotonic() - t0, 3)
        convs = [s["conversation_id"] for s in steps]
        self.assertTrue(wait_done(convs, timeout=2))
        for c in convs:
            self.assertIn("ran out of time", log_of(c))  # the thinking bot AND the bot that never started
        release.set()
        time.sleep(0.5)
        for c in convs:
            self.assertNotIn("LATE ANSWER", log_of(c))

    def test_stop_does_not_wait_for_a_thinking_bot(self):
        release, flag = threading.Event(), {"stop": False}

        def llm(prompt, **kw):
            release.wait(10)
            return "x"
        conv = "swstop0001-1"
        step = {"conversation_id": conv, "agent": SDE, "task": "t", "task_type": f"swarm_{conv}", "run_id": "s", "out_dir": ""}
        OPS.submit_task({"type": step["task_type"], "conversation_id": conv, "bot_id": SDE, "payload": {}})
        done = threading.Event()
        threading.Thread(target=lambda: (swarm_run.run_steps([step], "g", llm, cancelled=lambda: flag["stop"]),
                                         done.set()), daemon=True).start()
        time.sleep(0.3)
        flag["stop"] = True
        self.assertTrue(done.wait(2))
        release.set()


if __name__ == "__main__":
    unittest.main()
