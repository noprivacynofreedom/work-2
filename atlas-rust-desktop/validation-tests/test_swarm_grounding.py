import no_real_keys  # noqa: F401  (must run before cloud_llm is imported)
"""/swarm grounding: the chat names the folder the bots read, warns when it has no code,
the snapshot shows the files that fit the goal, and the review flags invented paths and tools.

No GPU and no network: call_llm is a fake, cloud keys are off.
"""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src-tauri" / "resources" / "atlas"))

import atlas_observability as OPS  # noqa: E402
import cloud_llm  # noqa: E402
import compute_peers  # noqa: E402
import repo_context  # noqa: E402
import swarm_pipeline as PIPE  # noqa: E402
import swarm_run  # noqa: E402


def write(root, rel, text):
    p = Path(root, rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def task_json_folder():
    """Like a user's swarm-workspaces on 2026-11-15: only Atlas task files."""
    root = Path(tempfile.mkdtemp(prefix="atlas-tasks-"))
    for i in range(3):
        write(root, f"python-calculator-{i}/.atlas-swarm-task.json", json.dumps({"goal": "calculator"}))
    write(root, "swarm-output/run1/answer.md", "old answer")
    return root


def atlas_like_repo():
    root = Path(tempfile.mkdtemp(prefix="atlas-like-"))
    write(root, "build-release.ps1", "# Build the release\nnpm run tauri build\n")
    write(root, "app/src-tauri/tauri.conf.json", '{"bundle": {"targets": ["nsis"]}}')
    write(root, "app/src-tauri/nsis/installer.nsi", '!include "MUI2.nsh"\nSection "Install"\nSectionEnd\n')
    write(root, "app/resources/server.py", "def main():\n    pass\n")
    for i in range(20):  # many files that only hold the project name
        write(root, f"docs/note_{i:02}.md", "atlas atlas notes\n")
        write(root, f"app/resources/mod_{i:02}.py", "# atlas helper\nX = 1\n")
    write(root, ".atlas/index.json", "{}")
    write(root, "swarm-workspaces/old/.atlas-swarm-task.json", "{}")
    return root


class FolderNote(unittest.TestCase):
    def test_task_json_only_folder_warns_and_names_the_folder(self):
        root = task_json_folder()
        ctx = repo_context.build(str(root), "package Atlas for production")
        self.assertTrue(ctx["warn"])
        self.assertIn("WARNING", ctx["note"])
        self.assertIn(str(root), ctx["note"])
        self.assertIn("Workspace", ctx["note"])
        self.assertEqual(ctx["files"], [])  # task JSON and swarm-output are Atlas's, never shown
        self.assertNotIn(".atlas-swarm-task.json", ctx["text"])

    def test_notes_only_folder_warns(self):
        root = Path(tempfile.mkdtemp())
        write(root, "plan.md", "# plan\n")
        write(root, "data.json", "{}")
        ctx = repo_context.build(str(root), "plan")
        self.assertTrue(ctx["warn"])
        self.assertIn("no source code", ctx["note"])

    def test_real_repo_note_names_folder_and_skips_artifacts(self):
        root = atlas_like_repo()
        ctx = repo_context.build(str(root), "package Atlas for production")
        self.assertFalse(ctx["warn"])
        self.assertIn(str(root), ctx["note"])
        self.assertNotIn("WARNING", ctx["note"])
        self.assertFalse([p for p in ctx["files"] if ".atlas" in p or "swarm-workspaces" in p])


class GoalFiles(unittest.TestCase):
    def test_packaging_goal_shows_build_and_installer_files(self):
        ctx = repo_context.build(str(atlas_like_repo()), "package Atlas for production")
        for want in ("build-release.ps1", "app/src-tauri/tauri.conf.json", "app/src-tauri/nsis/installer.nsi"):
            self.assertIn(want, ctx["shown"])
        self.assertFalse([p for p in ctx["shown"] if p.startswith("docs/")])  # "atlas" alone picks nothing
        self.assertIn("npm run tauri build", ctx["text"])
        self.assertLessEqual(len(ctx["text"]), repo_context.MAX_CHARS)

    def test_big_tree_leaves_room_for_file_text(self):
        root = atlas_like_repo()
        for i in range(400):
            write(root, f"deep/folder/number/{i:03}/file_{i:03}.py", "x = 1\n")
        ctx = repo_context.build(str(root), "package Atlas for production")
        self.assertIn("build-release.ps1", ctx["shown"])
        self.assertLessEqual(len(ctx["text"]), repo_context.MAX_CHARS)


class Grounding(unittest.TestCase):
    REPO = ["build-release.ps1", "app/src-tauri/tauri.conf.json", "app/src-tauri/nsis/installer.nsi", "app/resources/server.py"]

    def test_invented_paths_and_wrong_tool_are_listed(self):
        combined = ("We package Atlas with NSIS.\n\n"
                    "FILE: server.py\n```python\nimport fastapi\n```\n"
                    "FILE: Dockerfile\n```\nFROM python\n```\n"
                    "FILE: installer/Product.wxs\n```xml\n<Wix xmlns=\"x\"></Wix>\n```\n"
                    "FILE: build-release.ps1\n```powershell\ncandle.exe Product.wxs\n```\n"
                    "FILE: tests/test_build.py\n```python\nimport unittest\n```\n")
        text = PIPE.grounding_check(combined, self.REPO)
        self.assertIn("server.py is NOT in the repo (the repo has app/resources/server.py)", text)
        self.assertIn("Dockerfile is NOT in the repo", text)
        self.assertIn("installer/Product.wxs is NOT in the repo", text)
        self.assertNotIn("build-release.ps1 is NOT", text)      # a real file
        self.assertNotIn("test_build.py", text)                 # new tests are fine
        self.assertIn("The repo uses NSIS, but the code in the result is for WiX", text)

    def test_named_tool_without_repo(self):
        combined = "Use NSIS for the installer.\n\nFILE: setup.wxs\n```xml\n<Wix></Wix>\n```\n"
        self.assertIn("The result names NSIS, but the code in the result is for WiX", PIPE.grounding_check(combined, []))

    def test_clean_result_gives_nothing(self):
        combined = "NSIS installer.\n\nFILE: app/src-tauri/nsis/installer.nsi\n```nsis\n!include \"MUI2.nsh\"\n```\n"
        self.assertEqual(PIPE.grounding_check(combined, self.REPO), "")

    def test_review_prompt_carries_the_check(self):
        p = PIPE.review_prompt("g", "result", "tests", "AUTOMATIC CHECK: x")
        self.assertIn("AUTOMATIC CHECK: x", p)
        self.assertIn("List these problems first", p)
        self.assertNotIn("List these problems first", PIPE.review_prompt("g", "result", "tests"))

    def test_combine_prompt_has_the_repo_rules(self):
        self.assertIn("Do not name one tool and write code for another", PIPE.combine_prompt("g", [("a", "b")], "REPO"))
        self.assertNotIn("RULES FOR THE REAL PROJECT", PIPE.combine_prompt("g", [("a", "b")]))


def wait_done(convs, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        if all(OPS.swarm_log(c)["done"] for c in convs):
            return True
        time.sleep(0.05)
    return False


class PipelineEndToEnd(unittest.TestCase):
    """Fake model: the combine answer invents a path. The lead chat and the review must say so."""

    def test_lead_chat_names_folder_and_review_lists_invented_path(self):
        root, prompts = atlas_like_repo(), []

        def llm(prompt, **kw):
            prompts.append(prompt)
            if prompt.startswith("Combine the team answers"):
                return "Plan.\n\nFILE: Dockerfile\n```\nFROM python\n```\n"
            return "answer"
        out = os.path.join(tempfile.mkdtemp(), "swarm-output")
        with mock.patch.object(cloud_llm, "available", return_value=False), \
                mock.patch.object(compute_peers, "route", return_value=(None, None, None)), \
                mock.patch.dict(os.environ, {"ATLAS_SWARM_RUN_TESTS": "0"}):
            run = swarm_run.start("package Atlas for production", [{"agent": "10x: SDE", "task": "a"},
                                  {"agent": "10x: QA Engineer", "task": "b"}],
                                  call_llm=llm, pipeline=True, out_dir=out, repo_root=str(root))
            convs = [s["conversation_id"] for s in run["steps"]]
            self.assertTrue(wait_done(convs))
        lead = [s["conversation_id"] for s in run["steps"] if s.get("final")][0]
        log = " ".join(line["message"] for line in OPS.swarm_log(lead)["lines"])
        self.assertIn(str(root), log)
        self.assertIn("Dockerfile is NOT in the repo", log)
        review = [p for p in prompts if p.startswith("You are a strict reviewer")]
        self.assertEqual(len(review), 1)
        self.assertIn("Dockerfile is NOT in the repo", review[0])


if __name__ == "__main__":
    unittest.main()
