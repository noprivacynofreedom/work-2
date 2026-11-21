"""get_update.py: the safe update script must check first and never switch branch."""
import os
import subprocess
import sys
import tempfile
import unittest

# get_update.py lives at the repo root. Load it by path: putting the root on
# sys.path made every other test module's `import mcp_chat` / `import server`
# pick up the stale root copies instead of the shipped ones (test order bug).
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "get_update", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "get_update.py"))
get_update = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(get_update)


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
                   cwd=cwd, check=True, capture_output=True)


class GetUpdateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.remote = os.path.join(self.tmp.name, "remote")
        self.pc = os.path.join(self.tmp.name, "pc")
        os.makedirs(self.remote)
        git(self.remote, "init", "-q", "-b", "main")
        self.commit(self.remote, "app.py", "old app")                      # main = old Python app
        git(self.remote, "checkout", "-q", "-b", "old-feature")
        self.commit(self.remote, "books.py", "built on the old app")       # the 2026-11-10 mistake
        git(self.remote, "checkout", "-q", "-b", "app", "main")
        self.commit(self.remote, get_update.APP_MARK, "{}")                # the real desktop app
        git(self.tmp.name, "clone", "-q", "-b", "app", self.remote, self.pc)
        git(self.remote, "checkout", "-q", "-b", "good-feature", "app")
        self.commit(self.remote, "books.py", "built on the real app")
        git(self.remote, "checkout", "-q", "app")

    def tearDown(self):
        self.tmp.cleanup()

    def commit(self, repo, path, text):
        full = os.path.join(repo, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(text)
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "add " + path)

    def branch(self):
        return get_update.git("rev-parse", "--abbrev-ref", "HEAD", cwd=self.pc)

    def head(self):
        return get_update.git("rev-parse", "HEAD", cwd=self.pc)

    def test_survey_marks_old_branches_and_good_ones(self):
        rows = {r[0]: r[3] for r in get_update.survey(get_update.checks(self.pc), self.pc)}
        self.assertIn("DO NOT USE", rows["old-feature"])
        self.assertIn("python get_update.py good-feature", rows["good-feature"])
        self.assertNotIn("app", rows)   # nothing new there
        self.assertNotIn("main", rows)  # already contained

    def test_branch_built_on_the_old_app_is_refused(self):
        before = self.head()
        with self.assertRaises(get_update.Stop) as e:
            get_update.update("old-feature", self.pc, yes=True, out=lambda *_: None)
        self.assertIn("old version of Atlas", str(e.exception))
        self.assertEqual((self.head(), self.branch()), (before, "app"))

    def test_good_branch_is_added_without_switching_branch(self):
        out = []
        self.assertTrue(get_update.update("good-feature", self.pc, yes=True, out=out.append))
        self.assertEqual(self.branch(), "app")
        self.assertTrue(os.path.isfile(os.path.join(self.pc, "books.py")))
        self.assertTrue(os.path.isfile(os.path.join(self.pc, get_update.APP_MARK)))
        self.assertIn("build-release.ps1", out[-1])
        self.assertFalse(get_update.update("good-feature", self.pc, yes=True, out=out.append))  # second run: nothing to do

    def test_answer_no_changes_nothing(self):
        before = self.head()
        self.assertFalse(get_update.update("good-feature", self.pc, ask=lambda _q: "n", out=lambda *_: None))
        self.assertEqual(self.head(), before)

    def test_uncommitted_changes_stop_it_first(self):
        with open(os.path.join(self.pc, "app.py"), "w") as f:
            f.write("my edit")
        with self.assertRaises(get_update.Stop) as e:
            get_update.update("good-feature", self.pc, yes=True, out=lambda *_: None)
        self.assertIn("not committed", str(e.exception))
        with open(os.path.join(self.pc, "app.py")) as f:
            self.assertEqual(f.read(), "my edit")

    def test_on_an_old_branch_it_says_how_to_go_back(self):
        git(self.pc, "checkout", "-q", "old-feature")
        with self.assertRaises(get_update.Stop) as e:
            get_update.checks(self.pc)
        self.assertIn("git checkout -", str(e.exception))

    def test_branch_that_lacks_your_newest_work_is_refused(self):
        self.commit(self.pc, "local.txt", "work only on the PC")
        with self.assertRaises(get_update.Stop) as e:
            get_update.update("good-feature", self.pc, yes=True, out=lambda *_: None)
        self.assertIn("does not contain your newest work", str(e.exception))

    def test_unknown_branch(self):
        self.assertRaises(get_update.Stop, get_update.update, "nope", self.pc, True)


if __name__ == "__main__":
    unittest.main()
