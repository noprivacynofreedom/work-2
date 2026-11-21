"""Opt-in module registry for Atlas Chat (Odysseus-inspired optional capabilities).

Standard library only. Stores user module toggles under settings.json["modules"]
via atomic, non-destructive merging so all existing settings keys remain intact.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from typing import Any

_WRITE_LOCK = threading.Lock()

# Ordered catalog of optional modules. Safe defaults keep experimental/external packs OFF.
MODULE_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "id": "compare",
        "name": "Blind Compare Mode",
        "phase": "Phase 1A",
        "command": "/compare",
        "default": True,
        "status": "ready",
        "boundary": "core-local",
        "description": "Fan out a prompt to 2-4 local, LAN, or cloud models behind blind labels (Model A-D), measure latency and tok/s, vote, and track a local-vs-cloud leaderboard.",
    },
    {
        "id": "deep_research",
        "name": "Swarm Deep Research",
        "phase": "Phase 1B",
        "command": "/research",
        "default": True,
        "status": "ready",
        "boundary": "core-local",
        "description": "4-stage research pipeline (Plan -> Gather -> Verify -> Synthesize) combining Atlas Knowledge Library retrieval with local or cloud models to produce cited Markdown briefs.",
    },
    {
        "id": "cookbook",
        "name": "Hardware-Aware Model Cookbook",
        "phase": "Phase 1C",
        "command": "/cookbook",
        "default": True,
        "status": "ready",
        "boundary": "core-local",
        "description": "Detects host RAM/VRAM, scans installed .gguf models, grades curated open-weight recipes by hardware fit, and generates copy-ready llama-swap YAML snippets.",
    },
    {
        "id": "skills_registry",
        "name": "Skills Registry Sync",
        "phase": "Phase 2C",
        "command": "/skillsreg",
        "default": True,
        "status": "ready",
        "boundary": "opt-in-workspace",
        "description": "Versioned skill packs with starter catalog, rollback history, JSON/SKILL.md bundle import/export, and one-click sync into bot skills.",
    },
    {
        "id": "docs_canvas",
        "name": "Workspace Docs Canvas",
        "phase": "Phase 2A",
        "command": "/docs",
        "default": True,
        "status": "ready",
        "boundary": "opt-in-workspace",
        "description": "Side-by-side Markdown editor and live preview backed by your workspace folder with diff-safe saves and AI revision proposals.",
    },
    {
        "id": "scheduler",
        "name": "Local Task Scheduler",
        "phase": "Phase 2B",
        "command": "/schedule",
        "default": True,
        "status": "ready",
        "boundary": "opt-in-workspace",
        "description": "Consent-gated local recurring prompts, research briefs, and health checks (starts paused by default) with Run Now and history logs.",
    },
    {
        "id": "productivity_mcp",
        "name": "Productivity MCP Pack",
        "phase": "Phase 3",
        "command": "/packs",
        "default": False,
        "status": "ready",
        "boundary": "external-mcp",
        "description": "Standalone external MCP server for local tasks, calendar, and read-only IMAP triage. Outbound email send is permanently disabled.",
    },
    {
        "id": "media_drawer",
        "name": "Local Media Drawer",
        "phase": "Phase 3",
        "command": "/packs",
        "default": False,
        "status": "ready",
        "boundary": "external-mcp",
        "description": "Standalone external MCP bridge for local image generators (Automatic1111 / ComfyUI / OpenAI-compatible local image servers).",
    },
    {
        "id": "remote_companion",
        "name": "Remote Companion Access",
        "phase": "Phase 3",
        "command": "/packs",
        "default": False,
        "status": "ready",
        "boundary": "external-mcp",
        "description": "Authenticated LAN companion pairing tokens with one-click revocation, paired with Atlas Node device identity.",
    },
)

MODULE_BY_ID: dict[str, dict[str, Any]] = {m["id"]: m for m in MODULE_CATALOG}
DEFAULT_FLAGS: dict[str, bool] = {m["id"]: bool(m["default"]) for m in MODULE_CATALOG}


def resolve_flags(settings: dict[str, Any] | None = None) -> dict[str, bool]:
    """Return effective boolean flags for every known module, overlaying settings['modules']."""
    flags = dict(DEFAULT_FLAGS)
    raw = (settings or {}).get("modules") if isinstance(settings, dict) else None
    if isinstance(raw, dict):
        for mid in flags:
            val = raw.get(mid)
            if isinstance(val, bool):
                flags[mid] = val
    return flags


def is_enabled(module_id: str, settings: dict[str, Any] | None = None) -> bool:
    """True when module_id is a known optional module and currently enabled."""
    if module_id not in MODULE_BY_ID:
        return False
    return bool(resolve_flags(settings).get(module_id, False))


def catalog_view(settings: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return UI-ready catalog rows with live 'enabled' booleans."""
    flags = resolve_flags(settings)
    return [{**item, "enabled": flags[item["id"]]} for item in MODULE_CATALOG]


def validate_patch(payload: Any) -> dict[str, bool]:
    """Validate an incoming POST /api/modules payload and return {module_id: bool}.

    Accepts either:
      {"modules": {"compare": true, "cookbook": false}}
    or single-toggle form:
      {"id": "compare", "enabled": false}
    Rejects unknown module IDs and non-boolean values with ValueError.
    """
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object")

    raw_map: dict[str, Any]
    if "modules" in payload:
        if not isinstance(payload["modules"], dict) or not payload["modules"]:
            raise ValueError("'modules' must be a non-empty JSON object of {module_id: boolean}")
        raw_map = payload["modules"]
    elif "id" in payload and "enabled" in payload:
        raw_map = {str(payload["id"]): payload["enabled"]}
    else:
        raise ValueError("Provide either {'modules': {...}} or {'id': '...', 'enabled': true|false}")

    cleaned: dict[str, bool] = {}
    for key, val in raw_map.items():
        if not isinstance(key, str) or key not in MODULE_BY_ID:
            raise ValueError(f"Unknown optional module: {key!r}")
        if not isinstance(val, bool):
            raise ValueError(f"Module '{key}' value must be a boolean (true/false)")
        cleaned[key] = val
    return cleaned


def save_module_flags(settings_path: str, patch: dict[str, bool]) -> dict[str, bool]:
    """Atomically merge validated module flags into settings.json without losing other keys."""
    validated = validate_patch({"modules": patch})
    with _WRITE_LOCK:
        existing: dict[str, Any] = {}
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                existing = loaded
        except FileNotFoundError:
            existing = {}
        except (OSError, ValueError) as exc:
            raise RuntimeError(f"Could not read existing settings.json safely: {exc}") from exc

        merged_modules = resolve_flags(existing)
        merged_modules.update(validated)
        existing["modules"] = merged_modules

        folder = os.path.dirname(os.path.abspath(settings_path))
        os.makedirs(folder, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix=".settings-", suffix=".tmp", dir=folder)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, settings_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        return merged_modules
