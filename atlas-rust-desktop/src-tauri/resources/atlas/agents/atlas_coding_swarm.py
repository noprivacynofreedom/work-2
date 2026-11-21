"""Atlas six-capability coding Swarm orchestration core.

This module is intentionally additive. It uses Atlas' local OpenAI-compatible
llm.call_llm client, writes only inside a configured workspace, and never
executes model-supplied shell commands. Test commands are selected from a
small local allowlist by the operator.

Optional cloud routing (OFF by default). Set ATLAS_CLOUD_ROUTING=1 to send the
planner and the reviewer prompts (the request text and the plan) to a cloud model
through litellm. Everything else stays on the local model. Keys come from the
environment only (for example GEMINI_API_KEY, OPENROUTER_API_KEY). If litellm is
missing or a cloud call fails, the step falls back to the local model.
ATLAS_CLOUD_PLANNER and ATLAS_CLOUD_REVIEWER choose the cloud models.

Per-role history (optional): set ATLAS_SWARM_MEMORY_DIR, or ATLAS_DATA_DIR, and each
role appends one line per step to <dir>/<role>/thinking_history.jsonl. It holds
prompt lengths and the route, never prompt text.
"""
from __future__ import annotations
import hashlib, json, os, re, subprocess, sys, time, uuid
from pathlib import Path
from typing import Any

try:
    import llm
except ImportError:
    llm = None

MAX_FILES = 120
MAX_FILE_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024
ROLES = ("planner", "architect", "coder", "tester", "reviewer", "debugger")
ALLOWED_COMMANDS = {
    "python-unittest": [sys.executable, "-m", "unittest", "discover", "-v"],
    "python-pytest": [sys.executable, "-m", "pytest", "-q"],
    "node-test": ["npm", "test", "--", "--run"],
}

CLOUD_PLANNER = os.environ.get("ATLAS_CLOUD_PLANNER", "gemini/gemini-2.5-flash")
CLOUD_REVIEWER = os.environ.get("ATLAS_CLOUD_REVIEWER", "openrouter/deepseek/deepseek-chat")
CLOUD_TIMEOUT_SECONDS = 60

def _say(role: str, text: str) -> None:
    """One plain ASCII status line on stderr. Must never raise (a Windows pipe can reject other characters)."""
    try:
        sys.stderr.write(f"[{time.strftime('%H:%M:%S')}] [{role.upper()}] {text}\n")
        sys.stderr.flush()
    except Exception:
        pass

def _history_file(role: str) -> Path | None:
    base = os.environ.get("ATLAS_SWARM_MEMORY_DIR") or (
        os.path.join(os.environ["ATLAS_DATA_DIR"], "swarm_memory") if os.environ.get("ATLAS_DATA_DIR") else "")
    if not base or role not in ROLES:
        return None
    return Path(base) / role / "thinking_history.jsonl"

def _log_step(role: str, stage: str, details: dict) -> None:
    """Best effort. A logging problem must never break a swarm run."""
    try:
        target = _history_file(role)
        if target is None:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"timestamp": time.strftime("%H:%M:%S"), "stage": stage, "details": details}) + "\n")
    except Exception:
        pass

def _cloud_model_for(role: str | None) -> str | None:
    if os.environ.get("ATLAS_CLOUD_ROUTING", "").strip() != "1":
        return None
    return {"architect": CLOUD_PLANNER, "reviewer": CLOUD_REVIEWER}.get(role or "")

def _cloud_complete(cloud_model: str, prompt: str) -> str:
    import litellm  # imported only when cloud routing is on, so the module works without it
    litellm.drop_params = True
    response = litellm.completion(model=cloud_model, messages=[{"role": "user", "content": prompt}],
                                  temperature=0.1, timeout=CLOUD_TIMEOUT_SECONDS)
    text = response.choices[0].message.content
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("cloud model returned an empty answer")
    return text

def _model(prompt: str, model: str | None = None, max_tokens: int = 6000, role: str | None = None) -> str:
    cloud_model = _cloud_model_for(role)
    if cloud_model:
        _say(role, f"cloud routing is on, asking {cloud_model}")
        try:
            text = _cloud_complete(cloud_model, prompt)
            _log_step(role, "COMPLETE", {"route": "cloud", "model": cloud_model, "prompt_len": len(prompt), "output_len": len(text)})
            return text
        except Exception as exc:  # no litellm, no key, offline: use the local model instead
            _say(role, f"cloud call failed ({type(exc).__name__}), using the local model")
            _log_step(role, "CLOUD_FAILED", {"model": cloud_model, "error": type(exc).__name__})
    if llm is None:
        raise RuntimeError("Atlas local llm module is unavailable")
    result = llm.call_llm(prompt, temperature=0.15, max_tokens=max_tokens, model=model)
    _log_step(role or "coder", "COMPLETE", {"route": "local", "model": model or "default", "prompt_len": len(prompt), "output_len": len(result or "")})
    return result

def _json_from_model(text: str) -> dict:
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I)
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Model did not return a JSON object")
    value = json.loads(raw[start:end+1])
    if not isinstance(value, dict):
        raise ValueError("Model response must be a JSON object")
    return value

def _safe_rel(value: str) -> Path:
    raw = str(value or "").replace("\\", "/").strip()
    if not raw or raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        raise ValueError(f"Absolute/empty output path rejected: {value!r}")
    parts = raw.split("/")
    if any(p in ("", ".", "..") or ":" in p for p in parts):
        raise ValueError(f"Unsafe output path rejected: {value!r}")
    if any(p.casefold() in (".git", ".env", "__pycache__") for p in parts):
        raise ValueError(f"Protected output path rejected: {value!r}")
    return Path(*parts)

def _validate_files(value: Any) -> list[tuple[Path, bytes]]:
    if isinstance(value, dict):
        rows = [{"path": k, "content": v} for k, v in value.items()]
    elif isinstance(value, list):
        rows = value
    else:
        raise ValueError("files must be a list or object")
    if not rows or len(rows) > MAX_FILES:
        raise ValueError(f"File count must be 1..{MAX_FILES}")
    out, seen, total = [], set(), 0
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("content"), str):
            raise ValueError("Each generated file needs path and string content")
        rel = _safe_rel(row.get("path"))
        key = rel.as_posix().casefold()
        if key in seen or key == ".atlas-swarm-manifest.json":
            raise ValueError(f"Duplicate/reserved path: {key}")
        seen.add(key)
        data = row["content"].encode("utf-8")
        if len(data) > MAX_FILE_BYTES:
            raise ValueError(f"{key} exceeds per-file limit")
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise ValueError("Generated output exceeds total size limit")
        out.append((rel, data))
    return out

def _write_files(workspace: Path, project: str, task_id: str, rows: Any) -> dict:
    safe_project = re.sub(r"[^A-Za-z0-9._-]+", "-", project).strip(".-_")[:64] or "atlas-project"
    base = workspace.expanduser().resolve()
    base.mkdir(parents=True, exist_ok=True)
    if base.is_symlink():
        raise ValueError("Workspace root cannot be a symlink")
    worker_seed = uuid.uuid4().hex[:6]  # one folder per run, so parallel workers never share a directory
    dest = (base / f"{safe_project}-{task_id[-10:]}-{worker_seed}").resolve()
    if dest.parent != base or dest.exists():
        raise ValueError("Workspace destination exists or escaped workspace root")
    validated = _validate_files(rows)
    dest.mkdir()
    written, digest = [], hashlib.sha256()
    try:
        for rel, data in validated:
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            current = target.parent
            while current != dest:
                if current.is_symlink():
                    raise ValueError("Symlink detected in output path")
                current = current.parent
            with target.open("xb") as stream:
                stream.write(data)
            digest.update(rel.as_posix().encode()); digest.update(b"\0"); digest.update(data)
            written.append({"path": rel.as_posix(), "bytes": len(data)})
        manifest = {"task_id": task_id, "project": safe_project, "files": written,
                    "sha256": digest.hexdigest(), "created_at": time.time()}
        (dest / ".atlas-swarm-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return {"workspace": str(dest), "files": written, "sha256": digest.hexdigest()}
    except Exception:
        # Keep partial output for inspection; never recursively delete user data.
        raise

def plan_task(request: str, model: str | None = None) -> dict:
    prompt = (
        "You are Atlas lead software architect. Decompose the user's programming request "
        "into a concise dependency-ordered plan for specialist agents. Return JSON only: "
        '{"project_name":"...","summary":"...","tasks":[{"id":"...","role":"architect|coder|tester|reviewer|debugger",'
        '"title":"...","prompt":"...","depends_on":["..."]}]} . '
        "Use 2-8 tasks, unique ids, dependencies only on earlier tasks. Do not include shell commands.\\n\\n"
        f"USER REQUEST:\\n{request[:12000]}"
    )
    data = _json_from_model(_model(prompt, model, 3000, role="architect"))
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 8:
        raise ValueError("Planner must return 1..8 tasks")
    seen = set()
    for task in tasks:
        if not isinstance(task, dict) or task.get("role") not in ROLES[1:]:
            raise ValueError("Planner returned invalid task or role")
        tid = str(task.get("id") or "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", tid) or tid in seen:
            raise ValueError("Planner task IDs must be unique safe identifiers")
        deps = task.get("depends_on", [])
        if not isinstance(deps, list) or any(dep not in seen for dep in deps):
            raise ValueError("Dependencies must reference earlier tasks")
        seen.add(tid)
    data["tasks"] = tasks
    return data

def generate_project(request: str, plan: dict, model: str | None = None) -> dict:
    prompt = (
        "You are Atlas coding agent. Generate a complete minimal implementation for the request. "
        "Use the plan below. Return JSON only with project_name and files array [{path,content}]. "
        "No shell commands, no absolute paths, no secrets, no dependency on network unless asked. "
        "Include tests and README where appropriate. Keep implementation focused.\\n"
        f"REQUEST:\\n{request[:12000]}\\nPLAN:\\n{json.dumps(plan, ensure_ascii=False)[:16000]}"
    )
    data = _json_from_model(_model(prompt, model, 10000, role="coder"))
    _validate_files(data.get("files"))
    return data

def run_allowed_tests(workspace: str | Path, profile: str, timeout: int = 120, env: dict | None = None) -> dict:
    if profile not in ALLOWED_COMMANDS:
        raise ValueError(f"Test profile not allowlisted: {profile}")
    cwd = Path(workspace).resolve()
    if not cwd.is_dir():
        raise ValueError("Workspace does not exist")
    command = ALLOWED_COMMANDS[profile]
    started = time.time()
    try:
        proc = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True,
                              timeout=max(1, min(int(timeout), 300)), shell=False, env=env)
        return {"profile": profile, "command": command, "returncode": proc.returncode,
                "stdout": proc.stdout[-20000:], "stderr": proc.stderr[-20000:],
                "duration_seconds": round(time.time()-started, 3), "passed": proc.returncode == 0}
    except subprocess.TimeoutExpired as exc:
        return {"profile": profile, "command": command, "returncode": None,
                "stdout": str(exc.stdout or "")[-20000:], "stderr": "TIMEOUT",
                "duration_seconds": round(time.time()-started, 3), "passed": False, "timed_out": True}

def repair_project(request: str, plan: dict, workspace: str | Path, test_profile: str,
                   model: str | None = None, max_iterations: int = 2) -> dict:
    """Bounded repair loop. Model edits are limited to returned file paths in workspace."""
    root = Path(workspace).resolve()
    history = []
    for iteration in range(max(0, min(int(max_iterations), 3)) + 1):
        result = run_allowed_tests(root, test_profile)
        history.append(result)
        if result["passed"] or iteration >= max_iterations:
            break
        prompt = (
            "You are Atlas debugger. Inspect this project failure and propose corrected file contents. "
            "Return JSON only: {files:[{path,content}]}. Only modify files listed in the current project "
            "manifest; do not add commands.\\n"
            f"REQUEST:{request[:6000]}\\nPLAN:{json.dumps(plan)[:6000]}\\n"
            f"FAILURE:{json.dumps(result)[:16000]}"
        )
        patch = _json_from_model(_model(prompt, model, 6000, role="debugger"))
        changes = _validate_files(patch.get("files"))
        manifest_path = root / ".atlas-swarm-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        allowed = {x["path"] for x in manifest["files"]}
        for rel, data in changes:
            if rel.as_posix() not in allowed:
                raise ValueError(f"Repair attempted to add/modify untracked file: {rel}")
            target = (root / rel).resolve()
            if root not in target.parents:
                raise ValueError("Repair path escaped workspace")
            target.write_bytes(data)
    return {"history": history, "passed": bool(history and history[-1]["passed"]),
            "iterations": len(history)-1}

def run_coding_session(request: str, workspace: str | Path, model: str | None = None,
                       test_profile: str | None = None, max_repairs: int = 2) -> dict:
    """Local single-host orchestrator; emits a traceable plan and evidence bundle."""
    if not isinstance(request, str) or not request.strip():
        raise ValueError("A programming request is required")
    trace = uuid.uuid4().hex
    plan = plan_task(request, model)
    generated = generate_project(request, plan, model)
    task_id = "tsk_" + uuid.uuid4().hex
    written = _write_files(Path(workspace), generated.get("project_name") or plan.get("project_name") or "atlas-project",
                           task_id, generated.get("files"))
    review_prompt = (
        "Review this generated project against the request and plan. Return JSON only "
        '{"approved":true|false,"findings":["..."]}. Do not claim tests ran.\\n'
        f"REQUEST:{request[:6000]}\\nPLAN:{json.dumps(plan)[:6000]}\\nFILES:{json.dumps(written['files'])}"
    )
    review = _json_from_model(_model(review_prompt, model, 1500, role="reviewer"))
    tests = None
    repair = None
    if test_profile:
        repair = repair_project(request, plan, written["workspace"], test_profile, model, max_repairs)
        tests = repair["history"][-1] if repair["history"] else None
    return {"ok": bool(review.get("approved")) and (tests is None or tests.get("passed")),
            "task_id": task_id, "trace_id": trace, "plan": plan, "review": review,
            "workspace": written["workspace"], "files": written["files"],
            "test_result": tests, "repair": repair,
            "node_dispatch": {"status": "not_dispatched", "reason": "No second registered opted-in node was selected by this local runner"}}
