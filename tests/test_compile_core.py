"""compile_core.py must ship compiled core only, and never a half-compiled bundle."""
import tempfile
import unittest
from pathlib import Path

import compile_core as CC

CORE = ["agents/*", "swarm_run.py", "src/dev_engine/*"]
FILES = {
    "server.py": "import swarm_run\n",
    "swarm_run.py": "SECRET_LOGIC = 1\n",
    "agents/worker.py": "def main():\n    return 0\nif __name__ == '__main__':\n    main()\n",
    "src/dev_engine/tests/test_engine.py": "pass\n",
    "runtime/python/python.exe": "binary",
    "__pycache__/server.cpython-314.pyc": "bytecode",
    "agents/__pycache__/worker.cpython-314.pyc": "bytecode",
}


def fake_nuitka(py):
    py.with_name(py.stem + ".cp314-win_amd64.pyd").write_text("compiled", encoding="utf-8")
    py.with_name(py.stem + ".pyi").write_text("def main(): ...", encoding="utf-8")
    return 0


class CompileCoreTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.bundle = Path(tmp.name) / "atlas"
        self.staging = Path(tmp.name) / "staging"
        for rel, text in FILES.items():
            path = self.bundle / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def run_compile(self, compiler=fake_nuitka):
        return CC.compile_core(self.bundle, self.staging, CORE, compiler)

    def test_success_replaces_core_source(self):
        self.assertEqual(self.run_compile(), [])
        self.assertFalse((self.staging / "swarm_run.py").exists())
        self.assertTrue((self.staging / "swarm_run.cp314-win_amd64.pyd").exists())
        self.assertEqual(list(self.staging.rglob("*.pyi")), [])
        self.assertEqual((self.staging / "server.py").read_text(encoding="utf-8"), FILES["server.py"])

    def test_script_with_main_gets_launcher(self):
        self.run_compile()
        launcher = (self.staging / "agents" / "worker.py").read_text(encoding="utf-8")
        self.assertIn("from worker import main", launcher)
        self.assertNotIn("return 0", launcher)

    def test_source_bundle_never_changed(self):
        self.run_compile()
        self.assertEqual((self.bundle / "swarm_run.py").read_text(encoding="utf-8"), FILES["swarm_run.py"])
        self.assertEqual(list(self.bundle.rglob("*.pyd")), [])

    def test_failure_keeps_every_source(self):
        problems = self.run_compile(lambda py: 1 if py.name == "worker.py" else fake_nuitka(py))
        self.assertTrue(problems)
        self.assertEqual((self.staging / "swarm_run.py").read_text(encoding="utf-8"), FILES["swarm_run.py"])

    def test_runtime_bytecode_and_core_tests_not_staged(self):
        self.run_compile()
        self.assertFalse((self.staging / "runtime").exists())
        self.assertEqual(list(self.staging.rglob("*.pyc")), [])
        self.assertFalse((self.staging / "src" / "dev_engine" / "tests").exists())

    def test_check_finds_readable_core_but_not_launchers(self):
        self.run_compile()
        self.assertEqual(CC.readable_core(self.staging, CORE), [])
        self.assertEqual(CC.readable_core(self.bundle, CORE), ["agents/worker.py", "src/dev_engine/tests/test_engine.py", "swarm_run.py"])

    def test_personal_data_not_staged(self):
        for rel in ["data.json", "data/observability.sqlite3", ".atlas/knowledge/semantic-index.json", "server.log"]:
            (self.bundle / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.bundle / rel).write_text("private", encoding="utf-8")
        (self.bundle / "settings.json").write_text('{"mcp_servers": []}', encoding="utf-8")
        self.assertEqual(self.run_compile(), [])
        for rel in ["data.json", "data", ".atlas", "server.log"]:
            self.assertFalse((self.staging / rel).exists(), rel)
        self.assertTrue((self.staging / "settings.json").exists())

    def test_settings_with_env_values_stops(self):
        (self.bundle / "settings.json").write_text(
            '{"mcp_servers": [{"name": "gh", "env": {"GITHUB_TOKEN": "x"}}]}', encoding="utf-8")
        problems = self.run_compile()
        self.assertTrue(any("gh" in p for p in problems))

    def test_main_guard_without_main_function_stops(self):
        (self.bundle / "agents" / "odd.py").write_text("if __name__ == '__main__':\n    print(1)\n", encoding="utf-8")
        problems = self.run_compile()
        self.assertTrue(any("odd.py" in p for p in problems))
        self.assertTrue((self.staging / "agents" / "odd.py").exists())



class TauriOverrideTests(unittest.TestCase):
    def test_default_build_keeps_tauri_conf_compression(self):
        self.assertNotIn("windows", CC.tauri_override()["bundle"])  # tauri.conf.json "zlib" applies

    def test_fast_nsis_turns_compression_off_and_keeps_core_resources(self):
        fast = CC.tauri_override(fast_nsis=True)
        self.assertEqual(fast["bundle"]["windows"], {"nsis": {"compression": "none"}})
        self.assertEqual(fast["bundle"]["resources"], CC.TAURI_OVERRIDE["bundle"]["resources"])
        self.assertNotIn("windows", CC.TAURI_OVERRIDE["bundle"])  # the shared default is not changed

    def test_build_script_passes_the_flag(self):
        script = (Path(CC.ROOT) / "build-release.ps1").read_text(encoding="utf-8")
        self.assertIn("[switch]$FastNsis", script)
        self.assertIn("--fast-nsis", script)
        self.assertIn("[switch]$HotSync", script)
        self.assertIn("[CmdletBinding()]", script)

    def test_installer_nsi_uses_non_solid_zlib(self):
        nsi = (Path(CC.ROOT) / "atlas-rust-desktop" / "src-tauri" / "nsis" / "installer.nsi").read_text(encoding="utf-8")
        self.assertNotIn('SetCompressor /SOLID "{{compression}}"', nsi)
        self.assertIn('SetCompressor "{{compression}}"', nsi)
        self.assertIn('SetCompressor /SOLID "lzma"', nsi)


class NuitkaCacheTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.bundle = Path(tmp.name) / "atlas"
        self.staging = Path(tmp.name) / "staging"
        self.cache = Path(tmp.name) / "cache"
        for rel, text in FILES.items():
            path = self.bundle / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def test_incremental_cache_skips_unchanged_and_recompiles_changed(self):
        compiled = []

        def tracking_compiler(py):
            compiled.append(py.name)
            return fake_nuitka(py)

        # Cold run: compiles both core files.
        self.assertEqual(CC.compile_core(self.bundle, self.staging, CORE, tracking_compiler, cache_dir=self.cache), [])
        self.assertEqual(sorted(compiled), ["swarm_run.py", "worker.py"])

        # Warm run with no changes: compiles nothing.
        compiled.clear()
        self.assertEqual(CC.compile_core(self.bundle, self.staging, CORE, tracking_compiler, cache_dir=self.cache), [])
        self.assertEqual(compiled, [])
        self.assertTrue((self.staging / "swarm_run.cp314-win_amd64.pyd").exists())
        self.assertFalse((self.staging / "swarm_run.py").exists())
        self.assertIn("from worker import main", (self.staging / "agents" / "worker.py").read_text(encoding="utf-8"))

        # Edit one core file: only that file is recompiled.
        (self.bundle / "swarm_run.py").write_text("SECRET_LOGIC = 2\n", encoding="utf-8")
        compiled.clear()
        self.assertEqual(CC.compile_core(self.bundle, self.staging, CORE, tracking_compiler, cache_dir=self.cache), [])
        self.assertEqual(compiled, ["swarm_run.py"])


class NuitkaVenvTests(unittest.TestCase):
    """2026-11-18 laptop: 3 parallel jobs each created the venv (WinError 183) and none installed Nuitka."""

    def test_parallel_jobs_set_up_the_venv_once_and_a_half_venv_is_finished(self):
        from concurrent.futures import ThreadPoolExecutor
        from unittest import mock
        calls = []

        def run(cmd, check):
            calls.append("venv" if "venv" in cmd else "pip")
            (venv / "Scripts").mkdir(parents=True, exist_ok=True)
            (venv / "Scripts" / "python.exe").touch()

        with tempfile.TemporaryDirectory() as tmp:
            venv = Path(tmp) / "nuitka-venv"
            with mock.patch.object(CC, "NUITKA_VENV", venv), mock.patch.object(CC.subprocess, "run", side_effect=run):
                with ThreadPoolExecutor(4) as pool:
                    list(pool.map(lambda _: CC.nuitka_python(), range(8)))
                self.assertEqual(calls, ["venv", "pip"])
                next(venv.glob("*.ok")).unlink()  # half-made venv: python.exe exists, Nuitka never installed
                CC.nuitka_python()
                self.assertEqual(calls, ["venv", "pip", "pip"])


if __name__ == "__main__":
    unittest.main()
