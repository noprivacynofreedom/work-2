"""Safety rules of headless dev mode (headless_dev.py, docs/HEADLESS-DEV-MODE.md).

No push, no model-written shell commands, no edits outside the allowed folders, budget stop,
pause on user activity, and a full night on a throwaway git repo that leaves the user's repo untouched.
Run from atlas-rust-desktop/src-tauri/resources/atlas (CLAUDE.md section 5).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src-tauri" / "resources" / "atlas"))
import headless_dev as HD  # noqa: E402

HAS_GIT = shutil.which("git") is not None


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="hd-test-")
        self.data = Path(self.tmp.name) / "data"
        self.env = mock.patch.dict(os.environ, {"ATLAS_DATA_DIR": str(self.data)})
        self.env.start()
        self.busy = mock.patch.object(HD, "_swarm_busy", return_value=False)
        self.busy.start()
        HD._ACT.update(inflight=0, last=0.0)
        HD._STOP.clear()

    def tearDown(self):
        self.busy.stop()
        self.env.stop()
        HD._ACT.update(inflight=0, last=0.0)
        self.tmp.cleanup()

    def box(self):
        box = HD.sandbox()
        (box / HD.APP_DIR).mkdir(parents=True, exist_ok=True)
        (box / "atlas-rust-desktop/validation-tests").mkdir(parents=True, exist_ok=True)
        return box


class GitAllowList(Base):
    def test_push_and_history_rewrites_are_refused(self):
        box = self.box()
        for args in (["push", "origin", "main"], ["push"], ["reset", "--hard"], ["clean", "-fd"],
                     ["branch", "-D", "main"], ["worktree", "remove", "x"], ["pull"], ["rm", "a.py"],
                     ["checkout", "main"], ["checkout", "-b", "main"], ["stash", "drop"], ["stash", "clear"],
                     ["remote", "add", "x", "url"], ["fetch", "https://example.com/repo.git"],
                     ["commit", "-m", "x"], ["clone", "--no-hardlinks", "a", str(self.data / "elsewhere")]):
            with self.subTest(args=args):
                with self.assertRaises(HD.SafetyError):
                    HD._check_git(args, box)

    def test_user_repo_is_read_only(self):
        repo = Path(self.tmp.name) / "user_repo"
        repo.mkdir()
        HD._check_git(["rev-parse", "HEAD"], repo)  # reading is fine
        for args in (["commit", "--no-verify", "-m", "x"], ["add", "a"], ["checkout", "-b", "atlas-auto/x"],
                     ["stash", "push"], ["apply", "p.patch"], ["config", "user.name", "x"], ["fetch", "--no-tags", "origin"]):
            with self.subTest(args=args):
                with self.assertRaises(HD.SafetyError):
                    HD._check_git(args, repo)

    def test_sandbox_actions_are_allowed(self):
        box = self.box()
        for args in (["checkout", "-b", "atlas-auto/20261118-1"], ["checkout", "--detach", "abc"], ["stash", "push", "-u"],
                     ["commit", "--no-verify", "-m", "x"], ["remote", "set-url", "--push", "origin", HD.NO_PUSH_URL],
                     ["fetch", "--no-tags", "origin"]):
            HD._check_git(args, box)


class NoModelShell(Base):
    def test_fixed_tests_are_the_claude_md_commands(self):
        self.assertEqual(HD.FIXED_TESTS, (
            ("Backend tests", HD.APP_DIR, ("-m", "unittest", "discover", "-s", "../../../validation-tests", "-p", "test_*.py")),
            ("Bundle check", ".", ("check-bundle.py",)),
        ))

    def test_run_fixed_tests_runs_only_fixed_commands_without_shell(self):
        box = self.box()
        calls = []

        def fake_run(cmd, **kw):
            calls.append((cmd, kw))
            return subprocess.CompletedProcess(cmd, 0, "OK", "")
        with mock.patch.object(HD.subprocess, "run", fake_run):
            result = HD.run_fixed_tests(box)
        self.assertTrue(result["passed"])
        self.assertEqual([c[0] for c in calls], [[sys.executable, *a] for _l, _f, a in HD.FIXED_TESTS])
        for _cmd, kw in calls:
            self.assertFalse(kw.get("shell"))
            self.assertNotEqual(kw["env"]["ATLAS_DATA_DIR"], str(self.data))  # throwaway data folder

    def test_tests_never_run_outside_the_sandbox(self):
        with self.assertRaises(HD.SafetyError):
            HD.run_fixed_tests(Path(self.tmp.name))

    def test_shell_text_in_a_model_answer_is_not_an_edit(self):
        self.assertEqual(HD.parse_edits("Run this:\n```bash\nrm -rf /\ngit push --force\n```\n"), [])


class Edits(Base):
    def edit(self, path, search, replace):
        return f"FILE: {path}\n<<<<<<< SEARCH\n{search}=======\n{replace}>>>>>>> REPLACE\n"

    def test_bad_paths_are_refused(self):
        box = self.box()
        (box / "atlas-rust-desktop/validation-tests/test_old.py").write_text("x = 1\n")
        for bad in ("/etc/passwd", "C:/Windows/x.py", "../outside.py", f"{HD.APP_DIR}/../../x.py", ".git/config",
                    f"{HD.APP_DIR}/.git/hooks/pre-commit", "CLAUDE.md", "get_update.py", "build-release.ps1",
                    "atlas-rust-desktop/src-tauri/tauri.conf.json", "atlas-rust-desktop/validation-tests/test_old.py"):
            with self.subTest(path=bad):
                with self.assertRaises(HD.SafetyError):
                    HD.check_path(bad, box)

    def test_new_test_file_is_allowed(self):
        rel, _ = HD.check_path("atlas-rust-desktop/validation-tests/test_new.py", self.box())
        self.assertTrue(rel.endswith("test_new.py"))

    def test_search_must_match_once_and_nothing_is_written_on_failure(self):
        box = self.box()
        a = box / HD.APP_DIR / "a.py"
        a.write_text("x = 1\ny = 2\n")
        text = self.edit(f"{HD.APP_DIR}/a.py", "x = 1\n", "x = 10\n") + self.edit(f"{HD.APP_DIR}/a.py", "nope\n", "z\n")
        with self.assertRaises(ValueError):
            HD.apply_edits(text, box)
        self.assertEqual(a.read_text(), "x = 1\ny = 2\n")

    def test_good_edit_and_new_file(self):
        box = self.box()
        a = box / HD.APP_DIR / "a.py"
        a.write_text("x = 1\ny = 2\n")
        text = self.edit(f"{HD.APP_DIR}/a.py", "x = 1\n", "x = 10\n") + self.edit("docs/NOTE.md", "", "hello\n")
        self.assertEqual(HD.apply_edits("```\n" + text + "```", box), [f"{HD.APP_DIR}/a.py", "docs/NOTE.md"])
        self.assertEqual(a.read_text(), "x = 10\ny = 2\n")
        self.assertEqual((box / "docs/NOTE.md").read_text(), "hello\n")

    def test_emptying_a_file_is_refused(self):
        box = self.box()
        (box / HD.APP_DIR / "a.py").write_text("x = 1\n")
        with self.assertRaises(HD.SafetyError):
            HD.apply_edits(self.edit(f"{HD.APP_DIR}/a.py", "x = 1\n", ""), box)

    def test_size_limits(self):
        box = self.box()
        many = "".join(self.edit(f"docs/N{i}.md", "", "x\n") for i in range(HD.MAX_EDIT_FILES + 1))
        with self.assertRaises(HD.SafetyError):
            HD.apply_edits(many, box)
        big = self.edit("docs/BIG.md", "", "line\n" * (HD.MAX_EDIT_LINES + 1))
        with self.assertRaises(HD.SafetyError):
            HD.apply_edits(big, box)

    def test_edits_never_written_outside_the_sandbox(self):
        other = Path(self.tmp.name) / "user_repo"
        (other / "docs").mkdir(parents=True)
        with self.assertRaises(HD.SafetyError):
            HD.apply_edits(self.edit("docs/X.md", "", "x\n"), other)
        self.assertFalse((other / "docs/X.md").exists())


class ApprovalGate(Base):
    def test_low_risk_runs(self):
        self.assertTrue(HD.request_action("sandbox_edit", {"files": ["a"]}))
        self.assertEqual(HD.status()["queue"], [])

    def test_above_low_risk_is_queued_not_run(self):
        for name in ("web_search", "send_email", "git_push", "shell", "write_file", "made_up_tool"):
            with self.subTest(name=name):
                self.assertFalse(HD.request_action(name, {"q": "x"}))
        queue = HD.status()["queue"]
        self.assertEqual([q["action"] for q in queue], ["web_search", "send_email", "git_push", "shell", "write_file", "made_up_tool"])
        self.assertTrue(HD.dismiss_queued(queue[0]["id"])["ok"])
        self.assertEqual(len(HD.status()["queue"]), 5)

    def test_read_tools_from_mcp_tiers_are_low(self):
        self.assertEqual(HD.action_tier("git_status"), "low")
        self.assertEqual(HD.action_tier("write_file"), "write")


class Budgets(Base):
    def night(self, **over):
        s = HD._clean({**HD.DEFAULTS, "idle_minutes": 0, **over})
        return HD.Night(s, call_llm=lambda *a, **k: "", sleep=lambda _s: None)

    def test_cycle_budget_stops_the_night(self):
        n = self.night(max_cycles=2)
        n.cycles = 2
        with self.assertRaises(HD._Halt) as cm:
            n.checkpoint()
        self.assertIn("2 of 2 cycles", str(cm.exception))

    def test_token_and_minute_budgets(self):
        n = self.night(night_tokens=1000)
        n.tokens = 1000
        self.assertIn("tokens", n.budget_reason())
        clock = [0.0]
        n = HD.Night(HD._clean({**HD.DEFAULTS, "idle_minutes": 0, "night_minutes": 5}), sleep=lambda _s: None,
                     clock=lambda: clock[0])
        clock[0] = 301
        with self.assertRaises(HD._Halt):
            n.checkpoint()

    def test_repeated_failures_stop(self):
        n = self.night(max_failures=3)
        n.failures = 3
        self.assertIn("3 cycles failed in a row", n.budget_reason())

    def test_cycle_token_budget_fails_the_cycle(self):
        n = self.night(cycle_tokens=500)
        n.cycle = {"seconds": 0.0, "tokens": 500}
        with self.assertRaises(TimeoutError):
            n.checkpoint()

    def test_settings_are_clamped(self):
        s = HD.save_settings({"max_cycles": 9999, "idle_minutes": -5, "cloud_spend_limit_usd": 500, "unknown": 1})["settings"]
        self.assertEqual((s["max_cycles"], s["idle_minutes"], s["cloud_spend_limit_usd"]), (50, 0, 20.0))
        self.assertNotIn("unknown", s)
        self.assertFalse(HD.DEFAULTS["cloud_enabled"])  # cloud is off until the user turns it on


class PauseOnActivity(Base):
    def test_chat_running_pauses_and_free_pc_resumes(self):
        s = HD._clean({**HD.DEFAULTS, "idle_minutes": 0})
        HD.chat_started()
        self.assertIn("chatting", HD.busy_reason(s))
        sleeps = []

        def sleep(sec):
            sleeps.append(sec)
            HD.chat_finished()
        n = HD.Night(s, sleep=sleep)
        n.checkpoint("build")
        self.assertEqual(sleeps, [30])
        msgs = [r["message"] for r in HD.read_log()]
        self.assertTrue(any(m.startswith("Paused:") for m in msgs))
        self.assertTrue(any("free again" in m for m in msgs))

    def test_recent_chat_and_swarm_pause(self):
        s = HD._clean({**HD.DEFAULTS, "idle_minutes": 10})
        HD._ACT["last"] = time.time() - 60
        self.assertIn("chatted", HD.busy_reason(s))
        HD._ACT["last"] = time.time() - 11 * 60
        self.assertEqual(HD.busy_reason(s), "")
        with mock.patch.object(HD, "_swarm_busy", return_value=True):
            self.assertIn("swarm", HD.busy_reason(s))

    def test_paused_time_is_not_counted_and_stop_works_while_paused(self):
        s = HD._clean({**HD.DEFAULTS, "idle_minutes": 0})
        HD.chat_started()

        def sleep(_sec):
            HD._STOP.set()
        n = HD.Night(s, sleep=sleep)
        with self.assertRaises(HD._Halt) as cm:
            n.checkpoint()
        self.assertIn("Stopped by the user", str(cm.exception))


@unittest.skipUnless(HAS_GIT, "git is not installed")
class FullNight(Base):
    """A real night on a throwaway repo. The user's repo must be byte-for-byte untouched."""

    def make_repo(self, test_body="import unittest\nclass T(unittest.TestCase):\n    def test_ok(self):\n        import calc\n        self.assertEqual(calc.add(2, 2), 4)\n"):
        repo = Path(self.tmp.name) / "user_repo"
        app = repo / HD.APP_DIR
        app.mkdir(parents=True)
        (repo / "atlas-rust-desktop/src-tauri/tauri.conf.json").write_text("{}\n")
        (repo / "atlas-rust-desktop/validation-tests").mkdir(parents=True)
        (repo / "atlas-rust-desktop/validation-tests/test_calc.py").write_text(
            "import sys, os\nsys.path.insert(0, os.getcwd())\n" + test_body)
        (app / "calc.py").write_text("def add(a, b):\n    return a + b\n")
        (repo / "check-bundle.py").write_text("print('Bundle check passed')\n")
        (repo / "docs").mkdir()
        (repo / "docs/PLAN.md").write_text("- [ ] Add a subtract function to calc.py\n")
        git("init", "-q", "-b", "fix/queue-in-chat-dragdrop", cwd=repo)
        git("-c", "user.name=J", "-c", "user.email=j@x", "add", "-A", cwd=repo)
        git("-c", "user.name=J", "-c", "user.email=j@x", "commit", "-q", "-m", "base", cwd=repo)
        return repo

    def snapshot(self, repo):
        return (git("rev-parse", "HEAD", cwd=repo), git("branch", "-a", cwd=repo), git("status", "--porcelain", cwd=repo),
                git("stash", "list", cwd=repo), git("worktree", "list", cwd=repo), git("remote", "-v", cwd=repo))

    def stub_llm(self, build_answer):
        answers = {"plan": f"FILES: {HD.APP_DIR}/calc.py\nPLAN: add subtract\nRISK: none",
                   "build": build_answer, "review": "Looks right and small.\nVERDICT: KEEP"}

        def call(prompt, **kw):
            if prompt.startswith("You improve"):
                return answers["plan"]
            if prompt.startswith("You write ONE"):
                return answers["build"]
            return answers["review"]
        return call

    def run_night(self, repo, build_answer, **settings):
        HD.save_settings({"repo": str(repo), "idle_minutes": 0, "max_cycles": 1, **settings})
        HD._write_json("backlog.json", [HD._item("Add a subtract function to calc.py", "", "docs/PLAN.md:1")])
        calls = []
        real_run = subprocess.run

        def spy(cmd, *a, **kw):
            calls.append(list(cmd))
            return real_run(cmd, *a, **kw)
        with mock.patch.object(HD.subprocess, "run", spy):
            self.assertTrue(HD.start(call_llm=self.stub_llm(build_answer), sleep=lambda _s: None)["ok"])
            HD._THREAD.join(120)
        self.assertFalse(HD._THREAD.is_alive())
        return calls

    def check_calls(self, calls):
        """Every command was git (allowed subcommand, never push) or python with a FIXED_TESTS command."""
        fixed = [[sys.executable, *a] for _l, _f, a in HD.FIXED_TESTS]
        for cmd in calls:
            if cmd[0] == "git":
                self.assertIn(cmd[1], HD.GIT_ALLOWED, cmd)
                self.assertNotIn("push", cmd[1:2])
            else:
                self.assertIn(cmd, fixed)

    def test_good_patch_becomes_a_package_and_user_repo_is_untouched(self):
        repo = self.make_repo()
        before = self.snapshot(repo)
        good = (f"FILE: {HD.APP_DIR}/calc.py\n<<<<<<< SEARCH\n    return a + b\n=======\n    return a + b\n\n\n"
                "def sub(a, b):\n    return a - b\n>>>>>>> REPLACE\n```bash\ngit push origin main\nrm -rf ~\n```\n")
        calls = self.run_night(repo, good)
        self.check_calls(calls)
        self.assertEqual(self.snapshot(repo), before)
        st = HD.status()
        self.assertEqual(st["state"]["mode"], "off")
        self.assertIn("1 of 1 cycles", st["state"]["stopped_reason"])
        pkgs = st["packages"]
        self.assertEqual(len(pkgs), 1, HD.read_log())
        p = pkgs[0]
        self.assertEqual((p["status"], p["verdict"], p["tests_passed"]), ("ready", "KEEP", True))
        self.assertTrue(p["branch"].startswith("atlas-auto/"))
        box = HD.sandbox()
        self.assertIn(p["branch"], git("branch", cwd=box))
        self.assertEqual(git("remote", "get-url", "--push", "origin", cwd=box), HD.NO_PUSH_URL)
        self.assertIn("def sub", HD.package_text(p["id"], "patch"))
        report = HD.package_text(p["id"], "report")
        for part in ("What and why", "Test results", "Review", "Risks"):
            self.assertIn(part, report)
        self.assertIn("get_update.py", HD.package_text(p["id"], "claude"))
        # Approve only marks it. The user's repo still does not change.
        self.assertEqual(HD.decide_package(p["id"], "approve")["package"]["status"], "approved")
        self.assertFalse(HD.decide_package(p["id"], "reject")["ok"])
        self.assertEqual(self.snapshot(repo), before)

    def test_patch_that_breaks_tests_is_stashed_not_kept(self):
        repo = self.make_repo()
        before = self.snapshot(repo)
        bad = (f"FILE: {HD.APP_DIR}/calc.py\n<<<<<<< SEARCH\n    return a + b\n=======\n    return a - b\n>>>>>>> REPLACE\n")
        calls = self.run_night(repo, bad, max_failures=1, max_cycles=5)
        self.check_calls(calls)
        self.assertEqual(self.snapshot(repo), before)
        st = HD.status()
        self.assertEqual(st["packages"], [])
        self.assertIn("failed in a row", st["state"]["stopped_reason"])
        box = HD.sandbox()
        self.assertIn("atlas-auto: failed", git("stash", "list", cwd=box))  # kept aside, not deleted
        self.assertEqual(git("status", "--porcelain", cwd=box), "")
        self.assertEqual((box / HD.APP_DIR / "calc.py").read_text(), "def add(a, b):\n    return a + b\n")

    def test_old_app_commit_is_refused(self):
        repo = self.make_repo()
        os.remove(repo / "atlas-rust-desktop/src-tauri/tauri.conf.json")
        git("-c", "user.name=J", "-c", "user.email=j@x", "commit", "-qam", "old", cwd=repo)
        self.run_night(repo, "")
        self.assertIn("OLD Atlas", HD.status()["state"]["stopped_reason"])
        self.assertFalse(HD.sandbox().exists())

    def test_failing_baseline_stops_before_any_change(self):
        repo = self.make_repo(test_body="import unittest\nclass T(unittest.TestCase):\n    def test_no(self):\n        self.fail('x')\n")
        self.run_night(repo, "")
        self.assertIn("Tests fail before any change", HD.status()["state"]["stopped_reason"])


class Endpoints(Base):
    """Real server.Handler: the panel's endpoints, local-only rules, and chat activity counting."""

    def setUp(self):
        super().setUp()
        import json
        import threading
        import urllib.request
        import server
        self.json, self.urllib = json, urllib.request
        self.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        super().tearDown()

    def call(self, path, body=None, headers=None):
        data = None if body is None else self.json.dumps(body).encode()
        h = {"Content-Type": "application/json"} if body is not None else {}
        h.update(headers or {})
        req = self.urllib.Request(self.base + path, data=data, headers=h, method="POST" if body is not None else "GET")
        try:
            with self.urllib.urlopen(req, timeout=10) as r:
                return r.status, self.json.loads(r.read())
        except self.urllib.HTTPError as e:
            return e.code, self.json.loads(e.read())

    def test_status_settings_backlog_queue(self):
        code, st = self.call("/api/headless/status")
        self.assertEqual((code, st["state"]["mode"]), (200, "off"))
        self.assertEqual(st["phases"], list(HD.PHASES))
        code, r = self.call("/api/headless/settings", {"max_cycles": 3})
        self.assertEqual((code, r["settings"]["max_cycles"]), (200, 3))
        code, r = self.call("/api/headless/backlog", {"title": "Make the send button bigger"})
        self.assertEqual(code, 200)
        code, r = self.call("/api/headless/item", {"id": r["item"]["id"], "status": "skipped"})
        self.assertEqual((code, r["item"]["status"]), (200, "skipped"))
        code, r = self.call("/api/headless/package", {"id": "20261118-1", "decision": "approve"})
        self.assertEqual(code, 409)
        code, r = self.call("/api/headless/package?id=../../etc&file=report")
        self.assertEqual(code, 404)

    def test_a_chat_request_counts_as_activity(self):
        import server
        old = server.UPSTREAM_PORT
        server.UPSTREAM_PORT = 9  # nothing listens: the proxy answers with an error at once
        try:
            self.call("/v1/chat/completions", {"model": "coder", "messages": [{"role": "user", "content": "hi"}]})
        finally:
            server.UPSTREAM_PORT = old
        self.assertEqual(HD._ACT["inflight"], 0)
        self.assertGreater(HD._ACT["last"], 0)
        self.assertIn("chatted", HD.busy_reason(HD._clean({**HD.DEFAULTS, "idle_minutes": 10})))

    def test_cross_site_posts_are_refused(self):
        code, _r = self.call("/api/headless/start", {}, {"Origin": "https://evil.example"})
        self.assertEqual(code, 403)
        self.assertEqual(HD.status()["state"]["mode"], "off")


if __name__ == "__main__":
    unittest.main()
