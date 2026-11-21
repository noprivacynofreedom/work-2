"""Automated privacy, public-export, and telemetry audit for Atlas Chat."""
import re
import subprocess
import unittest
from pathlib import Path

import export_public as EX

ROOT = Path(__file__).resolve().parent.parent
BIN_EXT = {
    ".png", ".ico", ".jpg", ".jpeg", ".gif", ".webp",
    ".woff", ".woff2", ".ttf", ".otf", ".exe", ".dll", ".pyd",
}
SKIP_NAMES = {"Cargo.lock", "package-lock.json"}

PERSONAL_NAME_RE = re.compile(r"\bjason\b|zezu1?", re.IGNORECASE)
PERSONAL_PATH_RE = re.compile(
    r"F:[/\\]+APP-DEV|C:[/\\]+Users[/\\]+zezu1?|\bF:[/\\]",
    re.IGNORECASE,
)
PRIVATE_IP_RE = re.compile(
    r"\b(?:192\.168|10\.\d+|172\.(?:1[6-9]|2\d|3[01])|100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7]))\.\d+\.\d+\b"
)
API_KEY_RE = re.compile(
    r"\b(?:sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z-_]{30,}|ghp_[0-9A-Za-z]{30,}|xai-[0-9A-Za-z]{20,})\b"
)
TELEMETRY_RE = re.compile(
    r"google-analytics\.com|googletagmanager\.com|posthog\.com|sentry\.io|mixpanel\.com|amplitude\.com|segment\.io",
    re.IGNORECASE,
)

# Explicitly allowed RFC1918 placeholder example in the compute-sharing UI.
ALLOWED_PLACEHOLDER_IPS = {
    "atlas-rust-desktop/src-tauri/resources/atlas/compute_page.py": {"192.168.1.50"},
    "atlas-rust-desktop/validation-tests/test_browser_mcp.py": {"10.0.0.5", "192.168.1.1", "10.0.0.1"},
}


def _public_tracked_files():
    core = EX.read_patterns(ROOT / "core-files.txt")
    rules = EX.read_patterns(ROOT / "public-files.txt")
    allow = [p for p in rules if not p.startswith("!")]
    deny = [p[1:] for p in rules if p.startswith("!")]
    files = EX.tracked_files(ROOT)
    return [
        rel
        for rel in files
        if rel.startswith(EX.OVERLAY)
        or (EX.matches(rel, allow) and not EX.matches(rel, deny) and not EX.is_private(rel, core))
    ]


def _shipped_app_files():
    prefixes = (
        "atlas-rust-desktop/src/",
        "atlas-rust-desktop/src-tauri/src/",
        "atlas-rust-desktop/src-tauri/nsis/",
        "atlas-rust-desktop/src-tauri/tauri.conf.json",
        "atlas-rust-desktop/src-tauri/resources/atlas/",
    )
    # Dev-engine standalone scripts/docs are in core-files.txt and not part of the UI/server runtime.
    excluded_prefix = "atlas-rust-desktop/src-tauri/resources/atlas/src/dev_engine/"
    return [
        rel
        for rel in EX.tracked_files(ROOT)
        if (rel in prefixes or rel.startswith(prefixes)) and not rel.startswith(excluded_prefix)
    ]


def _read_text(rel):
    path = ROOT / rel
    if not path.is_file() or path.suffix.lower() in BIN_EXT or path.name in SKIP_NAMES:
        return None
    return path.read_text(encoding="utf-8", errors="ignore")


class PrivacyAuditTests(unittest.TestCase):
    def test_public_export_has_no_private_files(self):
        core = EX.read_patterns(ROOT / "core-files.txt")
        for rel in _public_tracked_files():
            if rel.startswith(EX.OVERLAY):
                continue
            self.assertFalse(EX.is_private(rel, core), f"Private file in public export: {rel}")

    def test_public_export_has_no_personal_info_paths_ips_or_keys(self):
        for rel in _public_tracked_files():
            txt = _read_text(rel)
            if txt is None:
                continue
            self.assertIsNone(PERSONAL_NAME_RE.search(txt), f"Personal name leak in public file {rel}")
            self.assertIsNone(PERSONAL_PATH_RE.search(txt), f"Personal path leak in public file {rel}")
            self.assertIsNone(API_KEY_RE.search(txt), f"API key leak in public file {rel}")
            self.assertIsNone(TELEMETRY_RE.search(txt), f"Telemetry URL in public file {rel}")
            allowed_ips = ALLOWED_PLACEHOLDER_IPS.get(rel, set())
            for match in PRIVATE_IP_RE.finditer(txt):
                self.assertIn(match.group(0), allowed_ips, f"Private IP {match.group(0)} in public file {rel}")

    def test_shipped_desktop_app_has_no_personal_info_paths_or_telemetry(self):
        for rel in _shipped_app_files():
            txt = _read_text(rel)
            if txt is None:
                continue
            self.assertIsNone(PERSONAL_NAME_RE.search(txt), f"Personal name leak in shipped file {rel}")
            self.assertIsNone(PERSONAL_PATH_RE.search(txt), f"Personal path leak in shipped file {rel}")
            self.assertIsNone(API_KEY_RE.search(txt), f"API key leak in shipped file {rel}")
            self.assertIsNone(TELEMETRY_RE.search(txt), f"Telemetry URL in shipped file {rel}")

    def test_gitignore_blocks_local_private_files(self):
        private_samples = [
            "LICENSE.local",
            "HANDOFF-COMPUTE-SHARING.md",
            "REVIEW-2026-11-18.md",
            "mcp_commander_server.txt",
            ".claude/skills/x/SKILL.md",
            "swarm-output/run1/out.md",
            "swr-user testing/bug.md",
            "settings.local.json",
        ]
        for rel in private_samples:
            res = subprocess.run(
                ["git", "check-ignore", "--no-index", "-q", rel],
                cwd=ROOT,
            )
            self.assertEqual(res.returncode, 0, f".gitignore does not ignore private file: {rel}")


if __name__ == "__main__":
    unittest.main()
