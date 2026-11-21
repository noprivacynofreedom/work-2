"""Phase 3 Opt-In External Packs Coordinator (Productivity MCP, Local Media Drawer, Remote Companion).

Keeps IMAP/CalDAV/Media implementations cleanly isolated in their own standalone
MCP servers under src/ while giving the Atlas UI one-click MCP registration,
safe local previews, and authenticated LAN Remote Companion token management.

Standard library only.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import socket
import tempfile
import threading
import time
from typing import Any

from src import mcp_media_drawer, mcp_productivity

_LOCK = threading.Lock()

MCP_PACK_DEFS = {
    "atlas-productivity": {
        "name": "atlas-productivity",
        "command": ["{python}", "-u", "{project}/src/mcp_productivity.py"],
        "cwd": "{project}",
        "enabled": True,
    },
    "atlas-media-drawer": {
        "name": "atlas-media-drawer",
        "command": ["{python}", "-u", "{project}/src/mcp_media_drawer.py"],
        "cwd": "{project}",
        "enabled": True,
    },
}


def _read_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _write_json_atomic(path: str, payload: Any) -> None:
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".pack-", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def is_mcp_registered(settings: dict[str, Any], server_name: str) -> bool:
    rows = settings.get("mcp_servers") if isinstance(settings, dict) else None
    if not isinstance(rows, list):
        return False
    return any(isinstance(r, dict) and r.get("name") == server_name and r.get("enabled", True) for r in rows)


def set_mcp_registration(settings_path: str, server_name: str, registered: bool) -> list[dict[str, Any]]:
    """Atomically register or unregister a Phase 3 MCP pack in settings.json['mcp_servers']."""
    if server_name not in MCP_PACK_DEFS:
        raise ValueError(f"Unknown MCP pack: {server_name}")
    with _LOCK:
        existing = _read_json(settings_path, {})
        if not isinstance(existing, dict):
            existing = {}
        rows = [r for r in (existing.get("mcp_servers") or []) if isinstance(r, dict) and r.get("name") != server_name]
        if registered:
            rows.append(dict(MCP_PACK_DEFS[server_name]))
        existing["mcp_servers"] = rows
        _write_json_atomic(settings_path, existing)
        return rows


def _companion_path(data_dir: str) -> str:
    folder = os.path.join(data_dir, ".atlas")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "companion.json")


def _media_cfg_path(data_dir: str) -> str:
    folder = os.path.join(data_dir, ".atlas")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "media_drawer.json")


def _lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        return "127.0.0.1"


def companion_status(data_dir: str, port: int = 8090) -> dict[str, Any]:
    cfg = _read_json(_companion_path(data_dir), {})
    if not isinstance(cfg, dict):
        cfg = {}
    tokens = [t for t in (cfg.get("tokens") or []) if isinstance(t, dict) and not t.get("revoked")]
    now = time.time()
    active = [t for t in tokens if float(t.get("expires_at") or 0) > now]
    lan_ip = _lan_ip()
    return {
        "lan_url": f"http://{lan_ip}:{port}",
        "active_tokens": len(active),
        "tokens": [
            {
                "id": t["id"],
                "label": t.get("label", "Companion device"),
                "created_at": t.get("created_at"),
                "expires_at": t.get("expires_at"),
            }
            for t in active
        ],
        "note": "Remote Companion requires a valid bearer token and stays bound to localhost unless LAN sharing is explicitly enabled.",
    }


def issue_companion_token(data_dir: str, label: str = "Phone / Tablet", ttl_hours: int = 24, port: int = 8090) -> dict[str, Any]:
    hours = max(1, min(168, int(ttl_hours or 24)))
    raw_token = "atc_" + secrets.token_urlsafe(24)
    digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    now = time.time()
    record = {
        "id": "tok-" + secrets.token_hex(4),
        "label": str(label or "Companion device").strip()[:60] or "Companion device",
        "sha256": digest,
        "created_at": now,
        "expires_at": now + hours * 3600,
        "revoked": False,
    }
    with _LOCK:
        path = _companion_path(data_dir)
        cfg = _read_json(path, {})
        if not isinstance(cfg, dict):
            cfg = {}
        tokens = [t for t in (cfg.get("tokens") or []) if isinstance(t, dict)]
        tokens.insert(0, record)
        cfg["tokens"] = tokens[:20]
        _write_json_atomic(path, cfg)
    st = companion_status(data_dir, port=port)
    return {
        "token_once": raw_token,
        "token_id": record["id"],
        "expires_at": record["expires_at"],
        "status": st,
    }


def revoke_companion_tokens(data_dir: str, token_id: str = "", port: int = 8090) -> dict[str, Any]:
    with _LOCK:
        path = _companion_path(data_dir)
        cfg = _read_json(path, {})
        if not isinstance(cfg, dict):
            cfg = {}
        tokens = [t for t in (cfg.get("tokens") or []) if isinstance(t, dict)]
        revoked_count = 0
        for t in tokens:
            if not token_id or t.get("id") == token_id:
                if not t.get("revoked"):
                    t["revoked"] = True
                    revoked_count += 1
        cfg["tokens"] = tokens
        _write_json_atomic(path, cfg)
    return {"revoked": revoked_count, "status": companion_status(data_dir, port=port)}


def verify_companion_token(data_dir: str, bearer_token: str) -> bool:
    raw = str(bearer_token or "").strip()
    if not raw:
        return False
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    cfg = _read_json(_companion_path(data_dir), {})
    now = time.time()
    for t in (cfg.get("tokens") or []) if isinstance(cfg, dict) else []:
        if isinstance(t, dict) and not t.get("revoked") and float(t.get("expires_at") or 0) > now:
            if secrets.compare_digest(str(t.get("sha256") or ""), digest):
                return True
    return False


def get_media_endpoint(data_dir: str) -> str:
    cfg = _read_json(_media_cfg_path(data_dir), {})
    if isinstance(cfg, dict) and cfg.get("endpoint"):
        return str(cfg["endpoint"])
    return os.environ.get("ATLAS_MEDIA_URL") or mcp_media_drawer.DEFAULT_MEDIA_URL


def save_media_endpoint(data_dir: str, endpoint: str) -> str:
    clean = mcp_media_drawer.validate_local_endpoint(endpoint)
    _write_json_atomic(_media_cfg_path(data_dir), {"endpoint": clean, "updated_at": time.time()})
    return clean


def packs_overview(data_dir: str, settings: dict[str, Any], port: int = 8090) -> dict[str, Any]:
    endpoint = get_media_endpoint(data_dir)
    return {
        "productivity": {
            "mcp_registered": is_mcp_registered(settings, "atlas-productivity"),
            "outbound_email_allowed": mcp_productivity.OUTBOUND_EMAIL_ALLOWED,
            "imap_configured": bool(os.environ.get("ATLAS_IMAP_HOST") and os.environ.get("ATLAS_IMAP_USER")),
            "tasks": mcp_productivity.tasks_list(data_dir=data_dir),
            "events": mcp_productivity.calendar_list(data_dir=data_dir),
        },
        "media": {
            "mcp_registered": is_mcp_registered(settings, "atlas-media-drawer"),
            "endpoint": endpoint,
            "items": mcp_media_drawer.list_media(data_dir=data_dir),
        },
        "companion": companion_status(data_dir, port=port),
    }
