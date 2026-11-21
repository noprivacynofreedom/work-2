"""Skills Registry & Versioned Pack Sync for Atlas Chat (Phase 2C — Odysseus integration).

Provides versioned reusable prompt skills, curated starter packs, rollback to
earlier revisions, and checksummed JSON / SKILL.md bundle import/export stored
in <DATA_DIR>/.atlas/skills_registry.json without modifying user chats.

Standard library only.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import tempfile
import threading
import time
from typing import Any

_LOCK = threading.Lock()
MAX_SKILLS = 120
MAX_VERSIONS_PER_SKILL = 15

STARTER_PACKS: tuple[dict[str, Any], ...] = (
    {
        "slug": "strict-code-reviewer",
        "name": "Strict Code Reviewer",
        "tags": ["engineering", "review"],
        "description": "Checks diffs for security holes, race conditions, edge cases, and test gaps before approval.",
        "prompt": "Review code changes with high rigor. Lead with concrete bugs, security risks, race conditions, or missing test assertions citing exact line numbers. Keep stylistic nits brief and separate.",
    },
    {
        "slug": "adr-architect",
        "name": "Architecture Decision Record",
        "tags": ["architecture", "docs"],
        "description": "Turns open design questions into crisp Context / Options / Decision / Consequences ADRs.",
        "prompt": "Structure architectural analysis as a concise ADR with sections: Context, Constraints, Options Considered (with trade-offs), Recommended Decision, and Rollback / Verification Plan.",
    },
    {
        "slug": "security-audit-local",
        "name": "Local-First Security Auditor",
        "tags": ["security", "audit"],
        "description": "Audits endpoints for SSRF, path traversal, cross-origin writes, and secret leaks.",
        "prompt": "Audit the target code for path traversal, SSRF, cross-origin write bypasses, injection, and accidental secret logging. Propose minimal, fail-closed fixes.",
    },
    {
        "slug": "executive-synthesizer",
        "name": "Executive Brief Synthesizer",
        "tags": ["research", "writing"],
        "description": "Distills raw research notes into a decision-ready brief with explicit assumptions and open risks.",
        "prompt": "Distill input material into an executive brief: TL;DR (3 bullets), Evidence-Backed Findings, Assumptions & Gaps, and Concrete Next Actions with owners.",
    },
)


def _store_path(data_dir: str) -> str:
    folder = os.path.join(data_dir, ".atlas")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "skills_registry.json")


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-")
    return s[:48] or ("skill-" + secrets.token_hex(3))


def _bump_patch(version: str) -> str:
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", str(version or "").strip())
    if not m:
        return "1.0.0"
    return f"{m.group(1)}.{m.group(2)}.{int(m.group(3)) + 1}"


def _checksum(skills: list[dict[str, Any]]) -> str:
    canonical = json.dumps(
        [{"slug": s.get("slug"), "version": s.get("version"), "prompt": s.get("prompt")} for s in skills],
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _load_raw(data_dir: str) -> list[dict[str, Any]]:
    path = _store_path(data_dir)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("skills"), list):
            return [x for x in data["skills"] if isinstance(x, dict)]
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
    except (OSError, ValueError):
        pass
    return []


def _save_raw(data_dir: str, skills: list[dict[str, Any]]) -> None:
    path = _store_path(data_dir)
    folder = os.path.dirname(path)
    payload = {"schema": 1, "updated_at": time.time(), "checksum": _checksum(skills), "skills": skills[:MAX_SKILLS]}
    fd, tmp = tempfile.mkstemp(prefix=".skillsreg-", suffix=".tmp", dir=folder)
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


def registry_view(data_dir: str) -> dict[str, Any]:
    with _LOCK:
        skills = _load_raw(data_dir)
    installed_slugs = {s.get("slug") for s in skills}
    starters = [{**sp, "installed": sp["slug"] in installed_slugs} for sp in STARTER_PACKS]
    return {
        "skills": skills,
        "starter_packs": starters,
        "checksum": _checksum(skills),
        "bundle": export_bundle(data_dir),
    }


def save_skill(
    data_dir: str,
    *,
    name: str,
    prompt: str,
    description: str = "",
    tags: list[str] | str | None = None,
    slug: str = "",
    note: str = "",
) -> dict[str, Any]:
    clean_name = str(name or "").strip()[:80]
    clean_prompt = str(prompt or "").strip()[:12000]
    if not clean_name or not clean_prompt:
        raise ValueError("Skill name and prompt are required")
    clean_desc = str(description or "").strip()[:240]
    if isinstance(tags, str):
        clean_tags = [t.strip().lower()[:24] for t in tags.split(",") if t.strip()][:8]
    elif isinstance(tags, list):
        clean_tags = [str(t).strip().lower()[:24] for t in tags if str(t).strip()][:8]
    else:
        clean_tags = []

    target_slug = _slugify(slug or clean_name)
    now = time.time()

    with _LOCK:
        skills = _load_raw(data_dir)
        existing = next((s for s in skills if s.get("slug") == target_slug), None)
        if existing:
            prev_snap = {
                "version": existing.get("version", "1.0.0"),
                "prompt": existing.get("prompt", ""),
                "description": existing.get("description", ""),
                "saved_at": existing.get("updated_at") or now,
                "note": existing.get("note", ""),
            }
            history = list(existing.get("versions") or [])
            if prev_snap["prompt"] != clean_prompt or prev_snap["description"] != clean_desc:
                history.insert(0, prev_snap)
                history = history[:MAX_VERSIONS_PER_SKILL]
                next_ver = _bump_patch(existing.get("version", "1.0.0"))
            else:
                next_ver = existing.get("version", "1.0.0")
            existing.update({
                "name": clean_name,
                "description": clean_desc,
                "prompt": clean_prompt,
                "tags": clean_tags,
                "version": next_ver,
                "updated_at": now,
                "note": str(note or "").strip()[:120],
                "versions": history,
            })
            skill = existing
        else:
            if len(skills) >= MAX_SKILLS:
                raise ValueError(f"Maximum of {MAX_SKILLS} registry skills reached")
            skill = {
                "id": "skl-" + secrets.token_hex(4),
                "slug": target_slug,
                "name": clean_name,
                "description": clean_desc,
                "prompt": clean_prompt,
                "tags": clean_tags,
                "version": "1.0.0",
                "created_at": now,
                "updated_at": now,
                "note": str(note or "Initial version").strip()[:120],
                "versions": [],
            }
            skills.insert(0, skill)
        _save_raw(data_dir, skills)
        return skill


def delete_skill(data_dir: str, slug: str) -> str:
    clean = str(slug or "").strip()
    with _LOCK:
        skills = _load_raw(data_dir)
        kept = [s for s in skills if s.get("slug") != clean]
        if len(kept) == len(skills):
            raise KeyError("Registry skill not found")
        _save_raw(data_dir, kept)
    return clean


def rollback_skill(data_dir: str, slug: str, target_version: str) -> dict[str, Any]:
    clean = str(slug or "").strip()
    ver = str(target_version or "").strip()
    with _LOCK:
        skills = _load_raw(data_dir)
        hit = next((s for s in skills if s.get("slug") == clean), None)
        if not hit:
            raise KeyError("Registry skill not found")
        snap = next((v for v in (hit.get("versions") or []) if v.get("version") == ver), None)
        if not snap:
            raise KeyError(f"Version {ver} not found for skill {clean}")
        prev = {
            "version": hit.get("version", "1.0.0"),
            "prompt": hit.get("prompt", ""),
            "description": hit.get("description", ""),
            "saved_at": hit.get("updated_at") or time.time(),
            "note": hit.get("note", ""),
        }
        history = [prev] + [v for v in (hit.get("versions") or []) if v.get("version") != ver]
        hit["prompt"] = snap["prompt"]
        hit["description"] = snap.get("description", hit.get("description", ""))
        hit["version"] = _bump_patch(hit.get("version", "1.0.0"))
        hit["note"] = f"Rolled back to {ver}"
        hit["updated_at"] = time.time()
        hit["versions"] = history[:MAX_VERSIONS_PER_SKILL]
        _save_raw(data_dir, skills)
        return hit


def install_starter(data_dir: str, slug: str) -> dict[str, Any]:
    pack = next((p for p in STARTER_PACKS if p["slug"] == str(slug or "").strip()), None)
    if not pack:
        raise KeyError("Starter pack not found")
    return save_skill(
        data_dir,
        name=pack["name"],
        prompt=pack["prompt"],
        description=pack["description"],
        tags=pack["tags"],
        slug=pack["slug"],
        note="Installed from starter pack",
    )


def export_bundle(data_dir: str) -> dict[str, Any]:
    with _LOCK:
        skills = _load_raw(data_dir)
    return {
        "format": "atlas-skills-bundle-v1",
        "exported_at": time.time(),
        "checksum": _checksum(skills),
        "skills": [
            {
                "slug": s.get("slug"),
                "name": s.get("name"),
                "description": s.get("description", ""),
                "tags": s.get("tags") or [],
                "version": s.get("version", "1.0.0"),
                "prompt": s.get("prompt", ""),
            }
            for s in skills
        ],
    }


def _parse_skill_md(text: str) -> list[dict[str, Any]]:
    raw = str(text or "").strip()
    if not raw:
        return []
    name = "Imported Skill"
    desc = ""
    body = raw
    m = re.match(r"^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$", raw)
    if m:
        front, body = m.group(1), m.group(2).strip()
        for line in front.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip().lower()
                v = v.strip().strip('"').strip("'")
                if k == "name" and v:
                    name = v
                elif k == "description" and v:
                    desc = v
    return [{"name": name, "description": desc, "prompt": body}] if body else []


def import_bundle(data_dir: str, raw_payload: Any) -> dict[str, Any]:
    """Import a JSON skills bundle or SKILL.md document into the versioned registry."""
    items: list[dict[str, Any]] = []
    if isinstance(raw_payload, str):
        stripped = raw_payload.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                raw_payload = json.loads(stripped)
            except ValueError:
                items = _parse_skill_md(stripped)
        else:
            items = _parse_skill_md(stripped)

    if not items:
        if isinstance(raw_payload, dict) and isinstance(raw_payload.get("skills"), list):
            items = [x for x in raw_payload["skills"] if isinstance(x, dict)]
        elif isinstance(raw_payload, list):
            items = [x for x in raw_payload if isinstance(x, dict)]
        elif isinstance(raw_payload, dict) and raw_payload.get("name") and raw_payload.get("prompt"):
            items = [raw_payload]

    if not items:
        raise ValueError("No valid skills found in import payload (expected JSON bundle or SKILL.md)")

    imported = []
    for entry in items[:40]:
        if not entry.get("name") or not entry.get("prompt"):
            continue
        saved = save_skill(
            data_dir,
            name=str(entry.get("name")),
            prompt=str(entry.get("prompt")),
            description=str(entry.get("description") or ""),
            tags=entry.get("tags") or [],
            slug=str(entry.get("slug") or ""),
            note="Imported from bundle",
        )
        imported.append(saved["slug"])
    if not imported:
        raise ValueError("Imported entries were missing required 'name' and 'prompt' fields")
    return {"imported": imported, "count": len(imported)}
