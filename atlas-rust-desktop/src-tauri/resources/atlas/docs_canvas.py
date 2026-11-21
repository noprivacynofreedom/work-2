"""Workspace Docs Canvas for Atlas Chat (Phase 2A — Odysseus integration).

Side-by-side Markdown document drafting backed by the configured workspace folder
(or <DATA_DIR>/.atlas/docs when no workspace is set). Enforces strict path
confinement, atomic diff-safe saves with optional SHA-256 optimistic locking,
and optional AI rewrite/transform proposals that return a unified diff before
anything is written.

Standard library only.
"""
from __future__ import annotations

import difflib
import hashlib
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

import cloud_llm
import llm

ALLOWED_EXTS = (".md", ".markdown", ".txt", ".json", ".yaml", ".yml")
MAX_DOC_BYTES = 1024 * 1024  # 1 MB safety cap
_BAD_SEGMENT = re.compile(r"(?:^\.\.?$|[<>:\"|?*\x00-\x1f])")


def resolve_docs_root(data_dir: str, workspace_dir: str = "") -> tuple[str, str]:
    """Return (root_path, mode) where mode is 'workspace' or 'atlas-docs'."""
    ws = str(workspace_dir or "").strip()
    if ws and os.path.isdir(ws):
        return os.path.realpath(ws), "workspace"
    fallback = os.path.join(os.path.realpath(data_dir), ".atlas", "docs")
    os.makedirs(fallback, exist_ok=True)
    return os.path.realpath(fallback), "atlas-docs"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _safe_rel_path(rel_path: str) -> str:
    raw = str(rel_path or "").strip().replace("\\", "/").lstrip("/")
    if not raw:
        raise ValueError("Document filename is required")
    parts = [p for p in raw.split("/") if p]
    if not parts or any(_BAD_SEGMENT.search(p) for p in parts):
        raise ValueError("Invalid document path")
    clean = "/".join(parts)
    if not any(clean.lower().endswith(ext) for ext in ALLOWED_EXTS):
        clean += ".md"
    return clean


def _resolve_target(root_dir: str, rel_path: str) -> tuple[str, str]:
    root = os.path.realpath(root_dir)
    clean_rel = _safe_rel_path(rel_path)
    full = os.path.realpath(os.path.join(root, clean_rel))
    if os.path.commonpath([root, full]) != root:
        raise ValueError("Path escapes the docs root")
    return clean_rel, full


def list_docs(data_dir: str, workspace_dir: str = "", limit: int = 120) -> dict[str, Any]:
    """List editable Markdown/text documents inside the active docs root."""
    root, mode = resolve_docs_root(data_dir, workspace_dir)
    items: list[dict[str, Any]] = []
    skip_dirs = {".git", "node_modules", "__pycache__", "target", "dist", ".venv", "venv"}

    for cur_root, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in skip_dirs and not d.startswith("."))
        rel_dir = os.path.relpath(cur_root, root)
        depth = 0 if rel_dir == "." else rel_dir.count(os.sep) + 1
        if depth > 3:
            dirs[:] = []
            continue
        for fname in sorted(files):
            if not any(fname.lower().endswith(ext) for ext in ALLOWED_EXTS):
                continue
            full = os.path.join(cur_root, fname)
            try:
                st = os.stat(full)
            except OSError:
                continue
            if st.st_size > MAX_DOC_BYTES:
                continue
            rel = os.path.relpath(full, root).replace("\\", "/")
            items.append({
                "path": rel,
                "name": fname,
                "bytes": st.st_size,
                "mtime": st.st_mtime,
            })
            if len(items) >= limit:
                break
        if len(items) >= limit:
            break

    items.sort(key=lambda r: (-float(r["mtime"]), r["path"]))
    return {"root": root, "mode": mode, "docs": items}


def read_doc(data_dir: str, rel_path: str, workspace_dir: str = "") -> dict[str, Any]:
    """Read one document with its SHA-256 fingerprint for optimistic conflict checks."""
    root, mode = resolve_docs_root(data_dir, workspace_dir)
    clean_rel, full = _resolve_target(root, rel_path)
    if not os.path.isfile(full):
        raise FileNotFoundError(f"Document not found: {clean_rel}")
    size = os.path.getsize(full)
    if size > MAX_DOC_BYTES:
        raise ValueError("Document exceeds 1 MB canvas limit")
    with open(full, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    return {
        "path": clean_rel,
        "mode": mode,
        "content": content,
        "sha256": _sha256(content),
        "bytes": len(content.encode("utf-8")),
        "mtime": os.path.getmtime(full),
    }


def make_diff(before: str, after: str, label: str = "document.md") -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{label}",
            tofile=f"b/{label}",
            n=3,
        )
    )


def save_doc(
    data_dir: str,
    rel_path: str,
    content: str,
    *,
    workspace_dir: str = "",
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    """Atomically write a document inside the docs root and return diff summary."""
    text = str(content if content is not None else "")
    encoded = text.encode("utf-8")
    if len(encoded) > MAX_DOC_BYTES:
        raise ValueError("Document exceeds 1 MB canvas limit")

    root, mode = resolve_docs_root(data_dir, workspace_dir)
    clean_rel, full = _resolve_target(root, rel_path)

    previous = ""
    existed = os.path.isfile(full)
    if existed:
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            previous = f.read()
        if expected_sha256 and _sha256(previous) != expected_sha256:
            raise RuntimeError("Conflict: document changed on disk since you opened it. Reload before saving.")

    parent = os.path.dirname(full)
    os.makedirs(parent, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".doc-", suffix=".tmp", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, full)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    diff_text = make_diff(previous, text, clean_rel)
    return {
        "path": clean_rel,
        "mode": mode,
        "created": not existed,
        "bytes": len(encoded),
        "sha256": _sha256(text),
        "mtime": time.time(),
        "diff": diff_text,
    }


def _call_transform_model(model_id: str, prompt: str, timeout: int = 90) -> str:
    if cloud_llm.is_cloud_model(model_id):
        comp, _ = cloud_llm.chat_completion(
            {
                "model": model_id,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 2048,
            },
            timeout=timeout,
        )
        return str((comp.get("choices") or [{}])[0].get("message", {}).get("content") or "").strip()
    return str(llm.call_llm(prompt, temperature=0.3, max_tokens=2048, model=model_id or "assist", timeout=timeout) or "").strip()


def assist_doc(
    content: str,
    instruction: str,
    *,
    path: str = "draft.md",
    model: str = "assist",
    invoker: Callable[[str, str], str] | None = None,
) -> dict[str, Any]:
    """Generate a non-destructive AI revision proposal + unified diff without saving."""
    instr = str(instruction or "").strip()
    if not instr:
        raise ValueError("Edit instruction is required")
    original = str(content or "")
    prompt = (
        "You are an expert technical editor. Apply the user's instruction to the Markdown document below.\n"
        "Return ONLY the revised full Markdown document with no surrounding commentary or code fences.\n\n"
        f"Instruction: {instr}\n\n"
        f"--- DOCUMENT ({path}) ---\n{original}"
    )
    fn = invoker or _call_transform_model
    proposed = fn(model or "assist", prompt)
    if not proposed.strip():
        raise RuntimeError("Model returned an empty revision")
    return {
        "path": path,
        "model": model or "assist",
        "proposed": proposed,
        "diff": make_diff(original, proposed, path),
    }
