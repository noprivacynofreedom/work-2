"""Contract tests for Phase 0 (Optional Module Registry) and Phase 1A (Blind Compare Mode)."""
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

ATLAS_DIR = Path(__file__).resolve().parents[1] / "src-tauri" / "resources" / "atlas"
if str(ATLAS_DIR) not in sys.path:
    sys.path.insert(0, str(ATLAS_DIR))

import optional_modules
import compare_mode


class OptionalModulesTests(unittest.TestCase):
    def test_non_destructive_settings_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            original = {
                "server_port": 8090,
                "workspace_dir": "/tmp/demo",
                "mcp_servers": [{"name": "atlas-commander", "enabled": True}],
            }
            path.write_text(json.dumps(original), encoding="utf-8")

            merged = optional_modules.save_module_flags(str(path), {"compare": False, "cookbook": True})
            self.assertFalse(merged["compare"])
            self.assertTrue(merged["cookbook"])

            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["server_port"], 8090)
            self.assertEqual(saved["workspace_dir"], "/tmp/demo")
            self.assertEqual(saved["mcp_servers"], original["mcp_servers"])
            self.assertFalse(saved["modules"]["compare"])
            self.assertTrue(saved["modules"]["cookbook"])

    def test_rejects_invalid_module_flags(self):
        with self.assertRaises(ValueError):
            optional_modules.validate_patch({"modules": {"nonexistent_pack": True}})
        with self.assertRaises(ValueError):
            optional_modules.validate_patch({"modules": {"compare": "yes"}})
        with self.assertRaises(ValueError):
            optional_modules.validate_patch({"bad": True})

    def test_catalog_and_is_enabled_defaults(self):
        rows = optional_modules.catalog_view({})
        ids = {r["id"] for r in rows}
        self.assertTrue({"compare", "deep_research", "cookbook", "productivity_mcp"} <= ids)
        self.assertTrue(optional_modules.is_enabled("compare", {}))
        self.assertFalse(optional_modules.is_enabled("productivity_mcp", {}))
        self.assertFalse(optional_modules.is_enabled("compare", {"modules": {"compare": False}}))


class BlindCompareTests(unittest.TestCase):
    def test_blind_masking_partial_failure_vote_and_leaderboard(self):
        def fake_invoker(model_id, prompt, system, temp, max_tok, timeout):
            if model_id == "broken-model":
                raise RuntimeError("simulated upstream timeout")
            source = "cloud" if model_id.startswith("cloud:") else "local"
            return f"Answer from {model_id} for {prompt}", source

        run = compare_mode.run_compare(
            "Explain Raft consensus",
            ["coder", "cloud:gemini", "broken-model"],
            invoker=fake_invoker,
            rng=random.Random(42),
        )
        self.assertFalse(run["revealed"])
        self.assertEqual(len(run["slots"]), 3)
        # Identities must be hidden prior to vote/reveal
        for slot in run["slots"]:
            self.assertNotIn("model", slot)
            self.assertNotIn("source", slot)
            self.assertIn(slot["label"], ("A", "B", "C"))

        ok_slots = [s for s in run["slots"] if s["ok"]]
        bad_slots = [s for s in run["slots"] if not s["ok"]]
        self.assertEqual(len(ok_slots), 2)
        self.assertEqual(len(bad_slots), 1)
        self.assertIn("timeout", bad_slots[0]["error"])

        with tempfile.TemporaryDirectory() as tmp:
            winner_label = ok_slots[0]["label"]
            voted = compare_mode.vote_run(tmp, run["run_id"], winner_label)
            self.assertTrue(voted["revealed"])
            self.assertEqual(voted["vote"], winner_label)
            for slot in voted["slots"]:
                self.assertIn("model", slot)
                self.assertIn("source", slot)

            hist = compare_mode.read_history(tmp)
            self.assertEqual(hist["total_runs"], 1)
            self.assertEqual(len(hist["leaderboard"]), 3)
            winner_model = next(s["model"] for s in voted["slots"] if s["label"] == winner_label)
            winner_row = next(r for r in hist["leaderboard"] if r["model"] == winner_model)
            self.assertEqual(winner_row["wins"], 1)
            self.assertEqual(winner_row["win_rate"], 100.0)

    def test_tie_and_reveal_flows(self):
        def fake_invoker(model_id, prompt, system, temp, max_tok, timeout):
            return f"Reply {model_id}", "local"

        with tempfile.TemporaryDirectory() as tmp:
            r1 = compare_mode.run_compare("Compare A vs B", ["coder", "mentor"], invoker=fake_invoker)
            tied = compare_mode.vote_run(tmp, r1["run_id"], "tie")
            self.assertTrue(tied["revealed"])
            self.assertEqual(tied["vote"], "tie")

            r2 = compare_mode.run_compare("Reveal only", ["coder", "mentor"], invoker=fake_invoker)
            rev = compare_mode.reveal_run(tmp, r2["run_id"])
            self.assertTrue(rev["revealed"])
            self.assertEqual(rev["vote"], "reveal")

            hist = compare_mode.read_history(tmp)
            self.assertEqual(hist["total_runs"], 2)
            coder_row = next(r for r in hist["leaderboard"] if r["model"] == "coder")
            self.assertEqual(coder_row["ties"], 1)
            self.assertEqual(coder_row["runs"], 2)

    def test_rejects_bad_model_counts(self):
        with self.assertRaises(ValueError):
            compare_mode.run_compare("Hi", ["only-one"])
        with self.assertRaises(ValueError):
            compare_mode.run_compare("Hi", ["a", "b", "c", "d", "e"])
        with self.assertRaises(ValueError):
            compare_mode.run_compare("   ", ["a", "b"])

    def test_ui_contracts_present(self):
        html = (ATLAS_DIR / "index.html").read_text(encoding="utf-8")
        for token in ('id="modulesDlg"', 'id="compareDlg"', '"/modules"', '"/compare"', "/api/modules", "/api/compare/run"):
            self.assertIn(token, html)


if __name__ == "__main__":
    unittest.main()
