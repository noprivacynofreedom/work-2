"""Contract tests for Phase 1B (Swarm Deep Research) and Phase 1C (Hardware-Aware Model Cookbook)."""
import sys
import tempfile
import unittest
from pathlib import Path

ATLAS_DIR = Path(__file__).resolve().parents[1] / "src-tauri" / "resources" / "atlas"
if str(ATLAS_DIR) not in sys.path:
    sys.path.insert(0, str(ATLAS_DIR))

import deep_research
import cookbook


class DeepResearchTests(unittest.TestCase):
    def test_four_stage_pipeline_with_local_citations_and_persistence(self):
        calls = []

        def fake_model(model, prompt, max_tokens):
            calls.append((model, max_tokens))
            if "research planner" in prompt.lower():
                return "1. How does local indexing work?\n2. What are memory limits?"
            if "executive-ready markdown" in prompt.lower():
                return "# Deep Research Brief\n\n## Executive Summary\nLocal search uses [S1].\n"
            return "- Finding grounded in [S1]."

        def fake_retriever(query, limit=3):
            return [{"title": "Atlas Architecture Notes", "snippet": "Uses local SQLite and chunked embeddings.", "score": 0.92}]

        with tempfile.TemporaryDirectory() as tmp:
            run = deep_research.start_research(
                tmp,
                "Local hybrid search in Atlas",
                model="mentor",
                depth="quick",
                retriever=fake_retriever,
                model_fn=fake_model,
                sync=True,
            )
            self.assertEqual(run["status"], "done")
            self.assertEqual(run["stage"], "synthesize")
            self.assertEqual(len(run["questions"]), 2)
            self.assertEqual(len(run["sources"]), 1)
            self.assertEqual(run["sources"][0]["ref"], "S1")
            self.assertIn("[S1]", run["report"])
            self.assertGreaterEqual(len(calls), 4)

            loaded = deep_research.get_run(tmp, run["run_id"])
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded["topic"], "Local hybrid search in Atlas")
            self.assertEqual(len(deep_research.list_runs(tmp)), 1)

    def test_offline_model_fallback_still_completes_brief(self):
        def failing_model(model, prompt, max_tokens):
            raise RuntimeError("llama-swap offline")

        with tempfile.TemporaryDirectory() as tmp:
            run = deep_research.start_research(
                tmp,
                "Offline resilience",
                depth="quick",
                retriever=lambda q, lim=3: [{"title": "Local Doc", "snippet": "Offline excerpt."}],
                model_fn=failing_model,
                sync=True,
            )
            self.assertEqual(run["status"], "done")
            self.assertIn("## Executive Summary", run["report"])
            self.assertIn("Local Doc", run["report"])

    def test_requires_topic(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                deep_research.start_research(tmp, "   ", sync=True)


class ModelCookbookTests(unittest.TestCase):
    def test_hardware_fit_tiers_and_yaml_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            # High-VRAM desktop (24 GB VRAM, 64 GB RAM) -> big models fit in GPU VRAM
            high = cookbook.cookbook_payload(str(ATLAS_DIR), tmp, vram_override_gb=24, ram_override_gb=64)
            by_id_high = {r["id"]: r for r in high["recipes"]}
            self.assertEqual(by_id_high["qwen3-coder-30b-a3b-q4km"]["fit"], "gpu_fit")
            self.assertEqual(by_id_high["qwen3-coder-30b-a3b-q4km"]["recommended_ngl"], 99)
            self.assertIn("models:", high["yaml_snippet"])
            self.assertIn('"coder":', high["yaml_snippet"])

            # Mid-range laptop (8 GB VRAM, 32 GB RAM) -> 7B fits GPU, 14B hybrid
            mid = cookbook.cookbook_payload(str(ATLAS_DIR), tmp, vram_override_gb=8, ram_override_gb=32)
            by_id_mid = {r["id"]: r for r in mid["recipes"]}
            self.assertEqual(by_id_mid["qwen2.5-coder-7b-q5km"]["fit"], "gpu_fit")
            self.assertEqual(by_id_mid["qwen2.5-coder-14b-q4km"]["fit"], "hybrid_fit")

            # CPU-only low-RAM (0 GB VRAM, 8 GB RAM) -> 3B fits CPU, 30B too large
            low = cookbook.cookbook_payload(str(ATLAS_DIR), tmp, vram_override_gb=0, ram_override_gb=8)
            by_id_low = {r["id"]: r for r in low["recipes"]}
            self.assertEqual(by_id_low["llama-3.2-3b-q5km"]["fit"], "cpu_fit")
            self.assertEqual(by_id_low["qwen3-coder-30b-a3b-q4km"]["fit"], "too_large")

    def test_role_filtering(self):
        with tempfile.TemporaryDirectory() as tmp:
            only_vision = cookbook.cookbook_payload(str(ATLAS_DIR), tmp, role_filter="vision", vram_override_gb=12, ram_override_gb=32)
            self.assertTrue(only_vision["recipes"])
            self.assertTrue(all(r["role"] == "vision" for r in only_vision["recipes"]))

    def test_ui_contracts_present(self):
        html = (ATLAS_DIR / "index.html").read_text(encoding="utf-8")
        for token in ('id="researchDlg"', 'id="cookbookDlg"', '"/research"', '"/cookbook"', "/api/research/start", "/api/cookbook"):
            self.assertIn(token, html)


if __name__ == "__main__":
    unittest.main()
