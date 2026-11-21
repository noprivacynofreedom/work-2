"""Blind Compare Mode for Atlas Chat (Phase 1A — Odysseus integration).

Fans out one prompt concurrently to 2-4 local, LAN-peer, or ready cloud models,
shuffles answers behind blind labels (Model A-D), measures latency and tok/s,
hides identities until vote or explicit reveal, and logs outcomes to
<DATA_DIR>/.atlas/compare_history.jsonl for a local-vs-cloud leaderboard.

Standard library only.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import random
import secrets
import threading
import time
from typing import Any, Callable

import cloud_llm
import compute_peers
import llm

LABELS = ("A", "B", "C", "D")
MAX_RUNS_IN_MEMORY = 40

_RUNS_LOCK = threading.Lock()
_HISTORY_LOCK = threading.Lock()
_RUNS: dict[str, dict[str, Any]] = {}


def _history_path(data_dir: str) -> str:
    folder = os.path.join(data_dir, ".atlas")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "compare_history.jsonl")


def list_candidate_models() -> list[dict[str, Any]]:
    """Return available local, LAN-peer, and ready cloud models for Blind Compare."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    # 1. Local models from llama-swap
    try:
        for item in llm.list_models():
            mid = str(item.get("id") or "").strip() if isinstance(item, dict) else ""
            if mid and mid not in seen:
                seen.add(mid)
                out.append({
                    "id": mid,
                    "label": f"⌂ {mid} (Local)",
                    "source": "local",
                    "ready": True,
                })
    except Exception:
        pass

    # Fallback local aliases if llama-swap is not currently reachable
    if not out:
        for alias in ("coder", "mentor", "assist", "tasks"):
            seen.add(alias)
            out.append({
                "id": alias,
                "label": f"⌂ {alias} (Local alias)",
                "source": "local",
                "ready": False,
            })

    # 2. LAN compute peers
    try:
        peers = compute_peers.list_peers() if hasattr(compute_peers, "list_peers") else []
        for peer in peers if isinstance(peers, list) else []:
            if not isinstance(peer, dict):
                continue
            pname = str(peer.get("name") or "LAN Peer")
            for m in peer.get("models") or []:
                mid = str(m).strip()
                if mid and mid not in seen:
                    seen.add(mid)
                    out.append({
                        "id": mid,
                        "label": f"⇄ {mid} ({pname})",
                        "source": "lan",
                        "ready": True,
                    })
    except Exception:
        pass

    # 3. Cloud models from cloud_llm picker
    try:
        for cm in cloud_llm.picker_models():
            cid = str(cm.get("id") or "").strip()
            if cid and cid not in seen:
                seen.add(cid)
                out.append({
                    "id": cid,
                    "label": str(cm.get("label") or cid),
                    "source": "cloud",
                    "ready": bool(cm.get("ready")),
                    "free": bool(cm.get("free")),
                    "provider": cm.get("provider", ""),
                })
    except Exception:
        pass

    return out


def _source_of(model_id: str) -> str:
    if cloud_llm.is_cloud_model(model_id):
        return "cloud"
    try:
        peer_host, _, _ = compute_peers.route(model_id)
        if peer_host:
            return "lan"
    except Exception:
        pass
    return "local"


def _default_invoke(model_id: str, prompt: str, system: str, temperature: float, max_tokens: int, timeout: int) -> tuple[str, str]:
    """Call either cloud_llm or local llm.py and return (text, source)."""
    if cloud_llm.is_cloud_model(model_id):
        msgs = []
        if system.strip():
            msgs.append({"role": "system", "content": system.strip()})
        msgs.append({"role": "user", "content": prompt})
        comp, _machine = cloud_llm.chat_completion(
            {"model": model_id, "messages": msgs, "temperature": temperature, "max_tokens": max_tokens},
            timeout=timeout,
        )
        text = str((comp.get("choices") or [{}])[0].get("message", {}).get("content") or "").strip()
        return text, "cloud"

    full_prompt = f"{system.strip()}\n\n{prompt}" if system.strip() else prompt
    text = llm.call_llm(
        full_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        model=model_id,
        timeout=timeout,
    )
    return str(text or "").strip(), _source_of(model_id)


def _public_view(run: dict[str, Any]) -> dict[str, Any]:
    """Serialize a compare run, stripping true model identities unless revealed."""
    revealed = bool(run.get("revealed"))
    slots = []
    for slot in run["slots"]:
        item = {
            "label": slot["label"],
            "blind_name": f"Model {slot['label']}",
            "ok": slot["ok"],
            "text": slot["text"],
            "error": slot["error"],
            "latency_ms": slot["latency_ms"],
            "est_tokens": slot["est_tokens"],
            "tok_per_sec": slot["tok_per_sec"],
        }
        if revealed:
            item["model"] = slot["model"]
            item["source"] = slot["source"]
        slots.append(item)
    return {
        "run_id": run["run_id"],
        "prompt": run["prompt"],
        "created_at": run["created_at"],
        "revealed": revealed,
        "vote": run.get("vote"),
        "slots": slots,
    }


def run_compare(
    prompt: str,
    models: list[str],
    *,
    system: str = "",
    temperature: float = 0.4,
    max_tokens: int = 1200,
    timeout: int = 90,
    invoker: Callable[[str, str, str, float, int, int], tuple[str, str]] | None = None,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """Run a blind side-by-side comparison across 2-4 models and return masked view."""
    prompt_text = str(prompt or "").strip()
    if not prompt_text:
        raise ValueError("Prompt cannot be empty")
    if not isinstance(models, list):
        raise ValueError("models must be a list of 2 to 4 model IDs")

    clean_models: list[str] = []
    for m in models:
        mid = str(m or "").strip()
        if mid and mid not in clean_models:
            clean_models.append(mid)
    if len(clean_models) < 2 or len(clean_models) > 4:
        raise ValueError("Select between 2 and 4 distinct models to compare")

    call_fn = invoker or _default_invoke

    def _run_one(model_id: str) -> dict[str, Any]:
        t0 = time.monotonic()
        try:
            text, source = call_fn(model_id, prompt_text, system, float(temperature), int(max_tokens), int(timeout))
            dt = max(0.001, time.monotonic() - t0)
            est_tokens = max(1, len(text) // 4) if text else 0
            return {
                "model": model_id,
                "source": source or _source_of(model_id),
                "ok": True,
                "text": text,
                "error": "",
                "latency_ms": int(round(dt * 1000)),
                "est_tokens": est_tokens,
                "tok_per_sec": round(est_tokens / dt, 1) if est_tokens else 0.0,
            }
        except Exception as exc:
            dt = max(0.001, time.monotonic() - t0)
            return {
                "model": model_id,
                "source": _source_of(model_id),
                "ok": False,
                "text": "",
                "error": str(exc)[:400],
                "latency_ms": int(round(dt * 1000)),
                "est_tokens": 0,
                "tok_per_sec": 0.0,
            }

    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(clean_models)) as pool:
        futures = [pool.submit(_run_one, mid) for mid in clean_models]
        for fut in futures:
            results.append(fut.result())

    shuffler = rng or random.SystemRandom()
    shuffler.shuffle(results)
    slots = []
    for idx, res in enumerate(results):
        slots.append({"label": LABELS[idx], **res})

    run_id = "cmp-" + secrets.token_hex(6)
    run_record = {
        "run_id": run_id,
        "prompt": prompt_text,
        "created_at": time.time(),
        "revealed": False,
        "vote": None,
        "logged": False,
        "slots": slots,
    }
    with _RUNS_LOCK:
        _RUNS[run_id] = run_record
        if len(_RUNS) > MAX_RUNS_IN_MEMORY:
            oldest = sorted(_RUNS.items(), key=lambda kv: kv[1]["created_at"])[: len(_RUNS) - MAX_RUNS_IN_MEMORY]
            for old_id, _ in oldest:
                _RUNS.pop(old_id, None)

    return _public_view(run_record)


def _append_history(data_dir: str, run: dict[str, Any]) -> None:
    if run.get("logged"):
        return
    entry = {
        "run_id": run["run_id"],
        "ts": time.time(),
        "prompt_preview": run["prompt"][:160],
        "vote": run.get("vote"),
        "slots": [
            {
                "label": s["label"],
                "model": s["model"],
                "source": s["source"],
                "ok": s["ok"],
                "latency_ms": s["latency_ms"],
                "est_tokens": s["est_tokens"],
                "tok_per_sec": s["tok_per_sec"],
            }
            for s in run["slots"]
        ],
    }
    path = _history_path(data_dir)
    with _HISTORY_LOCK:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    run["logged"] = True


def vote_run(data_dir: str, run_id: str, winner: str) -> dict[str, Any]:
    """Record a vote ('A'|'B'|'C'|'D'|'tie'), reveal model identities, and log to JSONL."""
    win = str(winner or "").strip()
    if win.lower() == "tie":
        win = "tie"
    else:
        win = win.upper()

    with _RUNS_LOCK:
        run = _RUNS.get(str(run_id or ""))
        if not run:
            raise KeyError("Compare run not found or expired")
        valid_labels = {s["label"] for s in run["slots"]}
        if win != "tie" and win not in valid_labels:
            raise ValueError(f"Winner must be one of {sorted(valid_labels)} or 'tie'")
        run["vote"] = win
        run["revealed"] = True
        _append_history(data_dir, run)
        return _public_view(run)


def reveal_run(data_dir: str, run_id: str) -> dict[str, Any]:
    """Reveal model identities without casting a win vote."""
    with _RUNS_LOCK:
        run = _RUNS.get(str(run_id or ""))
        if not run:
            raise KeyError("Compare run not found or expired")
        run["revealed"] = True
        if run.get("vote") is None:
            run["vote"] = "reveal"
        _append_history(data_dir, run)
        return _public_view(run)


def read_history(data_dir: str, limit: int = 40) -> dict[str, Any]:
    """Read compare history JSONL and aggregate a local-vs-cloud leaderboard."""
    path = _history_path(data_dir)
    entries: list[dict[str, Any]] = []
    if os.path.isfile(path):
        with _HISTORY_LOCK:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                            if isinstance(obj, dict):
                                entries.append(obj)
                        except ValueError:
                            continue
            except OSError:
                pass

    stats: dict[str, dict[str, Any]] = {}
    by_source = {"local": {"wins": 0, "runs": 0}, "lan": {"wins": 0, "runs": 0}, "cloud": {"wins": 0, "runs": 0}}

    for entry in entries:
        vote = entry.get("vote")
        slots = entry.get("slots") or []
        is_scored = vote in LABELS or vote == "tie"
        for slot in slots:
            mid = str(slot.get("model") or "")
            if not mid:
                continue
            src = str(slot.get("source") or "local")
            row = stats.setdefault(
                mid,
                {
                    "model": mid,
                    "source": src,
                    "runs": 0,
                    "wins": 0,
                    "ties": 0,
                    "losses": 0,
                    "_latency_sum": 0,
                    "_tps_sum": 0.0,
                    "_ok_runs": 0,
                },
            )
            row["runs"] += 1
            if src in by_source:
                by_source[src]["runs"] += 1
            if slot.get("ok"):
                row["_ok_runs"] += 1
                row["_latency_sum"] += int(slot.get("latency_ms") or 0)
                row["_tps_sum"] += float(slot.get("tok_per_sec") or 0.0)
            if is_scored:
                if vote == "tie":
                    row["ties"] += 1
                elif vote == slot.get("label"):
                    row["wins"] += 1
                    if src in by_source:
                        by_source[src]["wins"] += 1
                else:
                    row["losses"] += 1

    leaderboard = []
    for row in stats.values():
        decided = row["wins"] + row["losses"] + row["ties"]
        win_rate = round((row["wins"] + 0.5 * row["ties"]) / decided * 100.0, 1) if decided else 0.0
        ok_n = row["_ok_runs"]
        leaderboard.append({
            "model": row["model"],
            "source": row["source"],
            "runs": row["runs"],
            "wins": row["wins"],
            "ties": row["ties"],
            "losses": row["losses"],
            "win_rate": win_rate,
            "avg_latency_ms": int(round(row["_latency_sum"] / ok_n)) if ok_n else 0,
            "avg_tok_per_sec": round(row["_tps_sum"] / ok_n, 1) if ok_n else 0.0,
        })

    leaderboard.sort(key=lambda r: (-r["win_rate"], -r["wins"], -r["runs"], r["model"]))
    return {
        "total_runs": len(entries),
        "by_source": by_source,
        "leaderboard": leaderboard,
        "recent": list(reversed(entries[-max(1, int(limit)) :])),
    }
