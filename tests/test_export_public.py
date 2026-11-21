"""export_public.py must never put the private core or a secret into the public ASM checkout."""
import tempfile
import unittest
from pathlib import Path

import export_public as EX

CORE = "atlas-rust-desktop/src-tauri/resources/atlas/swarm_run.py"
UI = "atlas-rust-desktop/src-tauri/resources/atlas/index.html"


class ExportPublicTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.src = Path(tmp.name) / "src"
        self.dest = Path(tmp.name) / "dest"
        self.dest.mkdir()
        (self.dest / ".git").mkdir()
        self.files = [UI, CORE, "settings.json", "atlas-rust-desktop/src-tauri/resources/atlas/settings.json",
                      "atlas-rust-desktop/build.log", "LICENSE.local", "HANDOFF.md", "README.md",
                      "public-overlay/LICENSE", "public-overlay/README.md"]
        for rel in self.files:
            path = self.src / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("from " + rel, encoding="utf-8")
        (self.src / "public-files.txt").write_text("atlas-rust-desktop/*\nsettings.json\nREADME.md\nHANDOFF.md\n", encoding="utf-8")
        (self.src / "core-files.txt").write_text("# core\n" + CORE + "\n", encoding="utf-8")

    def export(self):
        return EX.export(self.dest, root=self.src, files=self.files)

    def test_allowlisted_file_copied(self):
        self.export()
        self.assertTrue((self.dest / UI).is_file())

    def test_core_file_never_exported(self):
        self.export()
        self.assertFalse((self.dest / CORE).exists())

    def test_secret_never_exported(self):
        self.export()
        for rel in ["settings.json", "atlas-rust-desktop/src-tauri/resources/atlas/settings.json",
                    "atlas-rust-desktop/build.log", "LICENSE.local", "HANDOFF.md"]:
            self.assertFalse((self.dest / rel).exists(), rel)

    def test_stale_core_file_removed_from_dest(self):
        old = self.dest / CORE
        old.parent.mkdir(parents=True)
        old.write_text("old public copy", encoding="utf-8")
        removed = self.export()
        self.assertFalse(old.exists())
        self.assertIn(CORE, removed)

    def test_overlay_wins(self):
        self.export()
        self.assertEqual((self.dest / "README.md").read_text(encoding="utf-8"), "from public-overlay/README.md")
        self.assertTrue((self.dest / "LICENSE").is_file())
        self.assertFalse((self.dest / "public-overlay").exists())

    def test_git_folder_untouched(self):
        (self.dest / ".git" / "settings.json").write_text("x", encoding="utf-8")
        self.export()
        self.assertTrue((self.dest / ".git" / "settings.json").exists())


if __name__ == "__main__":
    unittest.main()
