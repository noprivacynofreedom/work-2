"""Swarm Deep Research pipeline for Atlas Chat (Phase 1B — Odysseus integration).

Runs a non-blocking, cancellable 4-stage research pipeline:
  1. plan       - Decompose the topic into focused sub-questions
  2. gather     - Retrieve evidence from Atlas Knowledge Library + analyze each sub-question
  3. verify     - Cross-check claims, highlight gaps and potential contradictions
  4. synthesize - Produce a citation-backed Markdown brief

Standard library only. Persists runs in <DATA_DIR>/.atlas/research_runs.json.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import tempfile
import threading
import time
from typing import Any, Callable

import cloud_llm
import llm

STAGES = ("plan", "gather", "verify", "synthesize")
DEPTH_QUESTIONS = {"quick": 2, "standard": 4, "deep": 5}
MAX_SAVED_RUNS = 30

_LOCK = threading.Lock()
_RUNS: dict[str, dict[str, Any]] = {}
_STOPS: dict[str, threading.Event] = {}


def _store_path(data_dir: str) -> str:
    folder = os.path.join(data_dir, ".atlas")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "research_runs.json")


def _load_saved(data_dir: str) -> list[dict[str, Any]]:
    path = _store_path(data_dir)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _persist_run(data_dir: str, run: dict[str, Any]) -> None:
    path = _store_path(data_dir)
    snapshot = _public_run(run)
    with _LOCK:
        saved = [r for r in _load_saved(data_dir) if r.get("run_id") != snapshot["run_id"]]
        saved.insert(0, snapshot)
        saved = saved[:MAX_SAVED_RUNS]
        folder = os.path.dirname(path)
        fd, tmp = tempfile.mkstemp(prefix=".research-", suffix=".tmp", dir=folder)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(saved, f, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def _public_run(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run["run_id"],
        "topic": run["topic"],
        "model": run["model"],
        "depth": run["depth"],
        "status": run["status"],
        "stage": run["stage"],
        "stages": list(STAGES),
        "started_at": run["started_at"],
        "finished_at": run.get("finished_at"),
        "questions": list(run.get("questions") or []),
        "sources": list(run.get("sources") or []),
        "notes": list(run.get("notes") or []),
        "verification": run.get("verification", ""),
        "report": run.get("report", ""),
        "error": run.get("error", ""),
        "log": list(run.get("log") or [])[-40:],
    }


def _call_model(model_id: str, prompt: str, max_tokens: int = 1000, timeout: int = 90) -> str:
    if cloud_llm.is_cloud_model(model_id):
        comp, _ = cloud_llm.chat_completion(
            {
                "model": model_id,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": max_tokens,
            },
            timeout=timeout,
        )
        return str((comp.get("choices") or [{}])[0].get("message", {}).get("content") or "").strip()
    return str(llm.call_llm(prompt, temperature=0.3, max_tokens=max_tokens, model=model_id or "mentor", timeout=timeout) or "").strip()


def _parse_questions(raw: str, topic: str, count: int) -> list[str]:
    lines = []
    for line in (raw or "").splitlines():
        cleaned = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()
        if len(cleaned) >= 8 and cleaned not in lines:
            lines.append(cleaned)
    if len(lines) >= count:
        return lines[:count]
    fallbacks = [
        f"What are the core architecture, mechanisms, and definitions behind {topic}?",
        f"What are the primary trade-offs, failure modes, and limitations of {topic}?",
        f"How does {topic} compare against alternative approaches in real deployments?",
        f"What concrete implementation or validation steps matter most for {topic}?",
        f"What open questions or missing evidence remain around {topic}?",
    ]
    for fb in fallbacks:
        if len(lines) >= count:
            break
        if fb not in lines:
            lines.append(fb)
    return lines[:count]


def _default_retriever(query: str, limit: int = 4) -> list[dict[str, Any]]:
    return []


def _format_source_snippet(hit: dict[str, Any], idx: int) -> dict[str, Any]:
    title = str(hit.get("title") or hit.get("source") or hit.get("path") or f"Local Source {idx}")
    snippet = str(hit.get("snippet") or hit.get("text") or hit.get("content") or "").strip()[:500]
    score = hit.get("score")
    return {
        "ref": f"S{idx}",
        "title": title,
        "snippet": snippet,
        "score": round(float(score), 3) if isinstance(score, (int, float)) else None,
        "kind": str(hit.get("kind") or "knowledge"),
    }


def _log(run: dict[str, Any], stage: str, message: str) -> None:
    run["log"].append({"ts": time.time(), "stage": stage, "message": message})


def _execute_pipeline(
    data_dir: str,
    run: dict[str, Any],
    stop_event: threading.Event,
    model_fn: Callable[[str, str, int], str],
    retriever_fn: Callable[[str, int], list[dict[str, Any]]],
) -> None:
    topic = run["topic"]
    model = run["model"]
    q_count = DEPTH_QUESTIONS.get(run["depth"], 4)

    try:
        # Stage 1: Plan
        run["stage"] = "plan"
        _log(run, "plan", f"Decomposing topic into {q_count} focused research sub-questions...")
        plan_prompt = (
            f"You are a research planner. Break the following topic into exactly {q_count} crisp, "
            f"non-overlapping research questions (one per line, numbered 1-{q_count}).\n\nTopic: {topic}"
        )
        try:
            raw_plan = model_fn(model, plan_prompt, 500)
        except Exception as exc:
            _log(run, "plan", f"Model planner unavailable ({exc}); using structured fallback questions.")
            raw_plan = ""
        questions = _parse_questions(raw_plan, topic, q_count)
        run["questions"] = questions
        _log(run, "plan", f"Planned {len(questions)} sub-questions.")

        if stop_event.is_set():
            run["status"] = "stopped"
            run["finished_at"] = time.time()
            _persist_run(data_dir, run)
            return

        # Stage 2: Gather (Local Knowledge Library + focused synthesis per sub-question)
        run["stage"] = "gather"
        _log(run, "gather", "Searching local Knowledge Library and gathering evidence per sub-question...")
        seen_titles: set[str] = set()
        sources: list[dict[str, Any]] = []
        notes: list[dict[str, Any]] = []

        for q_idx, question in enumerate(questions, 1):
            if stop_event.is_set():
                run["status"] = "stopped"
                run["finished_at"] = time.time()
                _persist_run(data_dir, run)
                return

            local_hits = []
            try:
                local_hits = retriever_fn(question, 3) or []
            except Exception as exc:
                _log(run, "gather", f"Knowledge search skipped for Q{q_idx}: {exc}")

            q_refs = []
            evidence_lines = []
            for hit in local_hits:
                if not isinstance(hit, dict):
                    continue
                title = str(hit.get("title") or hit.get("source") or hit.get("path") or "")
                existing = next((s for s in sources if s["title"] == title and title), None)
                if existing:
                    src = existing
                else:
                    src = _format_source_snippet(hit, len(sources) + 1)
                    if title:
                        seen_titles.add(title)
                    sources.append(src)
                q_refs.append(src["ref"])
                if src["snippet"]:
                    evidence_lines.append(f"[{src['ref']}] {src['title']}: {src['snippet']}")

            run["sources"] = list(sources)
            evidence_blob = "\n".join(evidence_lines) if evidence_lines else "(No local library hits for this question; note assumptions clearly.)"
            gather_prompt = (
                f"Answer this research sub-question concisely in 3-5 bullet points. "
                f"Cite matching local evidence with [S#] when used, and explicitly flag anything that is general knowledge rather than local evidence.\n\n"
                f"Main Topic: {topic}\nSub-Question {q_idx}: {question}\n\nLocal Evidence:\n{evidence_blob}"
            )
            try:
                finding = model_fn(model, gather_prompt, 700)
            except Exception as exc:
                finding = f"Model synthesis unavailable ({exc})."
                if evidence_lines:
                    finding += "\n\nRetrieved local excerpts:\n" + "\n".join(f"- {e}" for e in evidence_lines)
            notes.append({"question": question, "refs": q_refs, "finding": finding})
            run["notes"] = list(notes)
            _log(run, "gather", f"Completed Q{q_idx}/{len(questions)} ({len(q_refs)} local source match(es)).")

        if stop_event.is_set():
            run["status"] = "stopped"
            run["finished_at"] = time.time()
            _persist_run(data_dir, run)
            return

        # Stage 3: Verify
        run["stage"] = "verify"
        _log(run, "verify", "Cross-checking findings for contradictions, assumptions, and missing evidence...")
        findings_text = "\n\n".join(
            f"### Q{i}: {n['question']}\n{n['finding']}" for i, n in enumerate(notes, 1)
        )
        verify_prompt = (
            f"Review these research notes on '{topic}'. List:\n"
            f"1. Claims backed by local sources ([S#])\n"
            f"2. Potential contradictions or unverified assumptions\n"
            f"3. Missing data or follow-up checks needed.\n\n{findings_text}"
        )
        try:
            verification = model_fn(model, verify_prompt, 600)
        except Exception as exc:
            verification = (
                f"Automated verification skipped ({exc}). "
                f"Local library sources cited: {len(sources)}. Review ungrounded claims manually before acting."
            )
        run["verification"] = verification
        _log(run, "verify", "Verification check finished.")

        if stop_event.is_set():
            run["status"] = "stopped"
            run["finished_at"] = time.time()
            _persist_run(data_dir, run)
            return

        # Stage 4: Synthesize
        run["stage"] = "synthesize"
        _log(run, "synthesize", "Synthesizing final cited Markdown brief...")
        sources_md = "\n".join(f"- **[{s['ref']}]** {s['title']}" for s in sources) or "- None (no local Knowledge Library matches; model knowledge only)"
        synth_prompt = (
            f"Write a crisp, executive-ready Markdown research brief on '{topic}'.\n"
            f"Required sections:\n"
            f"## Executive Summary\n## Key Findings\n## Evidence & Sources\n## Verification & Gaps\n## Recommended Next Steps\n\n"
            f"Preserve [S#] citations where supported.\n\n"
            f"### Research Notes\n{findings_text}\n\n"
            f"### Verification Audit\n{verification}\n\n"
            f"### Available Local Sources\n{sources_md}"
        )
        try:
            report = model_fn(model, synth_prompt, 1400)
        except Exception as exc:
            _log(run, "synthesize", f"Model synthesizer unavailable ({exc}); assembling structured brief from stage outputs.")
            report = (
                f"# Deep Research Brief: {topic}\n\n"
                f"## Executive Summary\nCollected {len(notes)} structured sub-question analyses and {len(sources)} local Knowledge Library source(s).\n\n"
                f"## Key Findings\n{findings_text}\n\n"
                f"## Evidence & Sources\n{sources_md}\n\n"
                f"## Verification & Gaps\n{verification}\n\n"
                f"## Recommended Next Steps\n- Connect a local or cloud model to expand synthesis.\n- Import additional source documents into Atlas Knowledge Library for grounded citations.\n"
            )

        run["report"] = report
        run["status"] = "done"
        run["finished_at"] = time.time()
        _log(run, "synthesize", "Deep research brief ready.")
        _persist_run(data_dir, run)

    except Exception as exc:
        run["status"] = "error"
        run["error"] = str(exc)[:400]
        run["finished_at"] = time.time()
        _log(run, run.get("stage") or "error", f"Research failed: {run['error']}")
        _persist_run(data_dir, run)


def start_research(
    data_dir: str,
    topic: str,
    *,
    model: str = "mentor",
    depth: str = "standard",
    retriever: Callable[[str, int], list[dict[str, Any]]] | None = None,
    model_fn: Callable[[str, str, int], str] | None = None,
    sync: bool = False,
) -> dict[str, Any]:
    """Start a deep research run (background thread by default; sync=True for tests)."""
    clean_topic = str(topic or "").strip()
    if not clean_topic:
        raise ValueError("Research topic is required")
    clean_depth = str(depth or "standard").strip().lower()
    if clean_depth not in DEPTH_QUESTIONS:
        clean_depth = "standard"

    run_id = "res-" + secrets.token_hex(6)
    stop_event = threading.Event()
    run = {
        "run_id": run_id,
        "topic": clean_topic,
        "model": str(model or "mentor").strip() or "mentor",
        "depth": clean_depth,
        "status": "running",
        "stage": "plan",
        "started_at": time.time(),
        "finished_at": None,
        "questions": [],
        "sources": [],
        "notes": [],
        "verification": "",
        "report": "",
        "error": "",
        "log": [{"ts": time.time(), "stage": "plan", "message": f"Started {clean_depth} research on: {clean_topic}"}],
    }
    with _LOCK:
        _RUNS[run_id] = run
        _STOPS[run_id] = stop_event

    call_fn = model_fn or (lambda m, p, mt: _call_model(m, p, max_tokens=mt))
    ret_fn = retriever or _default_retriever

    if sync:
        _execute_pipeline(data_dir, run, stop_event, call_fn, ret_fn)
        return _public_run(run)

    t = threading.Thread(
        target=_execute_pipeline,
        args=(data_dir, run, stop_event, call_fn, ret_fn),
        daemon=True,
        name=f"atlas-research-{run_id}",
    )
    t.start()
    return _public_run(run)


def stop_research(run_id: str) -> dict[str, Any]:
    with _LOCK:
        ev = _STOPS.get(str(run_id or ""))
        run = _RUNS.get(str(run_id or ""))
        if not run:
            raise KeyError("Research run not found")
        if ev:
            ev.set()
        if run["status"] == "running":
            run["status"] = "stopping"
            _log(run, run.get("stage") or "plan", "Cancellation requested by user.")
        return _public_run(run)


def get_run(data_dir: str, run_id: str) -> dict[str, Any] | None:
    rid = str(run_id or "").strip()
    with _LOCK:
        if rid in _RUNS:
            return _public_run(_RUNS[rid])
    for item in _load_saved(data_dir):
        if item.get("run_id") == rid:
            return item
    return None


def list_runs(data_dir: str, limit: int = 20) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for item in _load_saved(data_dir):
        rid = str(item.get("run_id") or "")
        if rid:
            merged[rid] = item
    with _LOCK:
        for rid, run in _RUNS.items():
            merged[rid] = _public_run(run)
    rows = sorted(merged.values(), key=lambda r: float(r.get("started_at") or 0), reverse=True)
    return rows[: max(1, int(limit))]
