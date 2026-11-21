"""Validation tests for Phase 2A (Docs Canvas), Phase 2B (Task Scheduler),
Phase 2C (Skills Registry), and Phase 3 (Opt-In External MCP Packs & Companion).

Runs purely in-process using Python stdlib + temporary data directories.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ATLAS_DIR = Path(__file__).resolve().parents[1] / "src-tauri" / "resources" / "atlas"
if str(ATLAS_DIR) not in sys.path:
    sys.path.insert(0, str(ATLAS_DIR))

import docs_canvas  # noqa: E402
import external_packs  # noqa: E402
import optional_modules  # noqa: E402
import skills_registry  # noqa: E402
import task_scheduler  # noqa: E402
from src import mcp_media_drawer, mcp_productivity  # noqa: E402


class TestDocsCanvas(unittest.TestCase):
    def test_save_read_list_and_optimistic_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            res = docs_canvas.save_doc(tmp, "notes/plan.md", "# Plan\n\nStep 1\n")
            self.assertTrue(res["created"])
            self.assertEqual(res["path"], "notes/plan.md")
            sha1 = res["sha256"]

            listing = docs_canvas.list_docs(tmp)
            self.assertEqual(listing["mode"], "atlas-docs")
            self.assertEqual(len(listing["docs"]), 1)
            self.assertEqual(listing["docs"][0]["path"], "notes/plan.md")

            opened = docs_canvas.read_doc(tmp, "notes/plan.md")
            self.assertEqual(opened["sha256"], sha1)
            self.assertIn("Step 1", opened["content"])

            # Update with matching sha succeeds
            res2 = docs_canvas.save_doc(
                tmp,
                "notes/plan.md",
                "# Plan\n\nStep 1\nStep 2\n",
                expected_sha256=sha1,
            )
            self.assertFalse(res2["created"])
            self.assertIn("+Step 2", res2["diff"])

            # Stale sha raises optimistic conflict error
            with self.assertRaises(RuntimeError) as ctx:
                docs_canvas.save_doc(
                    tmp,
                    "notes/plan.md",
                    "stale overwrite",
                    expected_sha256=sha1,
                )
            self.assertIn("Conflict", str(ctx.exception))

    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for bad in ("../escape.md", "sub/../../escape.md", "bad<name>.md", ""):
                with self.assertRaises(ValueError):
                    docs_canvas.save_doc(tmp, bad, "nope")

    def test_assist_doc_returns_diff_without_writing(self):
        out = docs_canvas.assist_doc(
            "# Title\nOld line\n",
            "Replace Old with New",
            path="draft.md",
            model="assist",
            invoker=lambda m, p: "# Title\nNew line\n",
        )
        self.assertEqual(out["proposed"], "# Title\nNew line\n")
        self.assertIn("-Old line", out["diff"])
        self.assertIn("+New line", out["diff"])


class TestTaskScheduler(unittest.TestCase):
    def test_defaults_paused_and_consent_gated_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = task_scheduler.status_view(tmp)
            self.assertTrue(st["paused"])
            self.assertEqual(st["tasks"], [])

            created = task_scheduler.upsert_task(
                tmp,
                {
                    "name": "Morning Digest",
                    "kind": "prompt",
                    "prompt": "Summarize priorities",
                    "interval_minutes": 15,
                    "enabled": False,
                },
            )
            tid = created["task"]["id"]
            self.assertFalse(created["task"]["enabled"])

            # Even if forced due, paused + disabled must not run
            ran_paused = task_scheduler.tick_due_tasks(
                tmp,
                {"modules": {"scheduler": True}},
                prompt_runner=lambda m, p: "should not run",
            )
            self.assertEqual(ran_paused, [])

            # Enable task, make next_run_at due in the past, still paused -> must not run
            task_scheduler.upsert_task(tmp, {"action": "toggle", "id": tid, "enabled": True})
            state_file = Path(tmp) / ".atlas" / "scheduler.json"
            raw = json.loads(state_file.read_text(encoding="utf-8"))
            raw["tasks"][0]["next_run_at"] = time.time() - 10
            state_file.write_text(json.dumps(raw), encoding="utf-8")

            self.assertEqual(
                task_scheduler.tick_due_tasks(
                    tmp,
                    {"modules": {"scheduler": True}},
                    prompt_runner=lambda m, p: "still paused",
                ),
                [],
            )

            # Resume global scheduler -> due task runs and records JSONL history
            task_scheduler.set_paused(tmp, False)
            runs = task_scheduler.tick_due_tasks(
                tmp,
                {"modules": {"scheduler": True}},
                prompt_runner=lambda m, p: f"Digest via {m}: ok",
            )
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0]["status"], "ok")
            self.assertIn("Digest via tasks", runs[0]["output"])

            hist = task_scheduler.read_history(tmp)
            self.assertEqual(len(hist), 1)
            self.assertEqual(hist[0]["task_id"], tid)

            # Health check task + delete
            hc = task_scheduler.upsert_task(
                tmp,
                {"name": "Local Health", "kind": "health_check", "interval_minutes": 30},
            )
            hc_run = task_scheduler.run_task_now(tmp, hc["task"]["id"])
            self.assertEqual(hc_run["status"], "ok")
            self.assertIn("Local llama-swap reachable", hc_run["output"])

            task_scheduler.upsert_task(tmp, {"action": "delete", "id": tid})
            remaining = task_scheduler.status_view(tmp)["tasks"]
            self.assertEqual([t["id"] for t in remaining], [hc["task"]["id"]])


class TestSkillsRegistry(unittest.TestCase):
    def test_versioning_rollback_starters_and_import_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            s1 = skills_registry.save_skill(
                tmp,
                name="API Reviewer",
                description="Reviews REST routes",
                prompt="Check auth and status codes.",
                tags="api, security",
            )
            self.assertEqual(s1["version"], "1.0.0")
            self.assertEqual(s1["slug"], "api-reviewer")
            self.assertEqual(s1["versions"], [])

            s2 = skills_registry.save_skill(
                tmp,
                slug="api-reviewer",
                name="API Reviewer",
                description="Reviews REST routes v2",
                prompt="Check auth, CSRF, and status codes.",
            )
            self.assertEqual(s2["version"], "1.0.1")
            self.assertEqual(len(s2["versions"]), 1)
            self.assertEqual(s2["versions"][0]["version"], "1.0.0")

            rolled = skills_registry.rollback_skill(tmp, "api-reviewer", "1.0.0")
            self.assertEqual(rolled["version"], "1.0.2")
            self.assertEqual(rolled["prompt"], "Check auth and status codes.")

            starter = skills_registry.install_starter(tmp, "strict-code-reviewer")
            self.assertEqual(starter["slug"], "strict-code-reviewer")

            bundle = skills_registry.export_bundle(tmp)
            self.assertEqual(bundle["format"], "atlas-skills-bundle-v1")
            self.assertEqual(len(bundle["skills"]), 2)
            self.assertTrue(bundle["checksum"])

            # Import SKILL.md frontmatter + JSON bundle into a fresh dir
            with tempfile.TemporaryDirectory() as tmp2:
                res_json = skills_registry.import_bundle(tmp2, json.dumps(bundle))
                self.assertEqual(res_json["count"], 2)

                skill_md = (
                    "---\n"
                    "name: Release Checklist\n"
                    "description: Pre-release checks\n"
                    "---\n"
                    "Verify tests, checksums, and changelog."
                )
                res_md = skills_registry.import_bundle(tmp2, skill_md)
                self.assertEqual(res_md["imported"], ["release-checklist"])

                view = skills_registry.registry_view(tmp2)
                slugs = {s["slug"] for s in view["skills"]}
                self.assertIn("release-checklist", slugs)
                self.assertIn("strict-code-reviewer", slugs)


class TestPhase3ExternalPacks(unittest.TestCase):
    def test_productivity_mcp_safety_and_local_stores(self):
        # Hard safety invariant: outbound email sending is permanently disabled
        self.assertIs(mcp_productivity.OUTBOUND_EMAIL_ALLOWED, False)
        tool_names = [t["name"] for t in mcp_productivity.TOOLS]
        for name in tool_names:
            self.assertNotIn("send", name.lower())
            self.assertNotIn("smtp", name.lower())

        with tempfile.TemporaryDirectory() as tmp:
            task = mcp_productivity.tasks_add("Ship Phase 3", due="2026-12-01", priority="high", data_dir=tmp)
            self.assertFalse(task["done"])
            toggled = mcp_productivity.tasks_toggle(task["id"], True, data_dir=tmp)
            self.assertTrue(toggled["done"])
            self.assertEqual(len(mcp_productivity.tasks_list(data_dir=tmp, status="done")), 1)
            self.assertEqual(len(mcp_productivity.tasks_list(data_dir=tmp, status="open")), 0)

            ev = mcp_productivity.calendar_add("Release Review", "2026-12-01 10:00", notes="Check gates", data_dir=tmp)
            self.assertEqual(ev["title"], "Release Review")
            self.assertEqual(len(mcp_productivity.calendar_list(data_dir=tmp)), 1)

            # Unconfigured IMAP returns safe read-only notice without raising
            old_host = os.environ.pop("ATLAS_IMAP_HOST", None)
            try:
                triage = mcp_productivity.email_triage_readonly(limit=5)
                self.assertFalse(triage["configured"])
                self.assertIs(triage["outbound_email_allowed"], False)
                self.assertEqual(triage["messages"], [])
            finally:
                if old_host is not None:
                    os.environ["ATLAS_IMAP_HOST"] = old_host

    def test_media_drawer_and_atomic_mcp_registration(self):
        self.assertEqual(
            mcp_media_drawer.validate_local_endpoint("http://127.0.0.1:7860/"),
            "http://127.0.0.1:7860",
        )
        with self.assertRaises(ValueError):
            mcp_media_drawer.validate_local_endpoint("ftp://bad-scheme")

        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(mcp_media_drawer.list_media(data_dir=tmp), [])
            saved_ep = external_packs.save_media_endpoint(tmp, "http://127.0.0.1:8188")
            self.assertEqual(saved_ep, "http://127.0.0.1:8188")
            self.assertEqual(external_packs.get_media_endpoint(tmp), "http://127.0.0.1:8188")

            settings_path = os.path.join(tmp, "settings.json")
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "workspace_dir": "/keep/me",
                        "mcp_servers": [{"name": "existing-server", "command": ["echo"], "enabled": True}],
                    },
                    f,
                )

            rows = external_packs.set_mcp_registration(settings_path, "atlas-productivity", True)
            names = [r["name"] for r in rows]
            self.assertIn("existing-server", names)
            self.assertIn("atlas-productivity", names)

            # Existing unrelated settings preserved
            persisted = json.loads(Path(settings_path).read_text(encoding="utf-8"))
            self.assertEqual(persisted["workspace_dir"], "/keep/me")

            rows_after = external_packs.set_mcp_registration(settings_path, "atlas-productivity", False)
            self.assertEqual([r["name"] for r in rows_after], ["existing-server"])

    def test_remote_companion_token_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            issued = external_packs.issue_companion_token(tmp, label="iPad", ttl_hours=12, port=8090)
            tok = issued["token_once"]
            self.assertTrue(tok.startswith("atc_"))
            self.assertTrue(external_packs.verify_companion_token(tmp, tok))
            self.assertFalse(external_packs.verify_companion_token(tmp, "atc_invalid"))

            revoked = external_packs.revoke_companion_tokens(tmp, token_id=issued["token_id"], port=8090)
            self.assertEqual(revoked["revoked"], 1)
            self.assertFalse(external_packs.verify_companion_token(tmp, tok))

    def test_registry_flags_and_ui_contracts(self):
        # Phase 3 modules stay opt-in (default False), Phase 2 modules default True
        self.assertTrue(optional_modules.is_enabled("docs_canvas", {}))
        self.assertTrue(optional_modules.is_enabled("scheduler", {}))
        self.assertTrue(optional_modules.is_enabled("skills_registry", {}))
        self.assertFalse(optional_modules.is_enabled("productivity_mcp", {}))
        self.assertFalse(optional_modules.is_enabled("media_drawer", {}))
        self.assertFalse(optional_modules.is_enabled("remote_companion", {}))

        html = (ATLAS_DIR / "index.html").read_text(encoding="utf-8")
        for token in (
            'id="docsDlg"',
            'id="schedulerDlg"',
            'id="skillsRegDlg"',
            'id="packsDlg"',
            '"/docs"',
            '"/schedule"',
            '"/skillsreg"',
            '"/packs"',
            "/api/docs/save",
            "/api/scheduler/task",
            "/api/skills-registry",
            "/api/packs/status",
        ):
            self.assertIn(token, html, f"Expected UI contract token missing: {token}")


if __name__ == "__main__":
    unittest.main()
