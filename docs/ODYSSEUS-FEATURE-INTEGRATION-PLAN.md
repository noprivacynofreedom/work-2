# Odysseus Feature Integration Plan for Atlas Chat

This document maps Odysseus's personal AI workspace capabilities onto Atlas Chat's shipped architecture (`atlas-rust-desktop/src-tauri/resources/atlas/`), keeping every new capability **opt-in**, **local-first**, **non-destructive to user data**, and compliant with `CLAUDE.md` rules.

## Guiding Boundaries

1. **Shipped Path Only**: All backend and chat UI modules live under `atlas-rust-desktop/src-tauri/resources/atlas/` and use Python's standard library only so `python check-bundle.py` and the Windows NSIS / Linux builds require zero extra pip packages.
2. **Page Never Scrolls (`CLAUDE.md` §8)**: Every new UI surface renders inside a native `<dialog>` (top layer with its own internal scrolling), never adding unbounded height to `main` or `.app`.
3. **Localhost-Only Writes**: All mutating endpoints (`/api/modules`, `/api/compare/*`, `/api/research/*`, `/api/cookbook/*`, `/api/docs/*`, `/api/scheduler/*`, `/api/skills-registry`, `/api/packs/*`) enforce `_local_ui_request(post=True)`.
4. **Non-Destructive Settings**: Module toggles merge atomically under `settings.json["modules"]`, preserving all existing keys (`mcp_servers`, `workspace_dir`, `browser_mode`, etc.).
5. **Email / Calendar / Media Isolation (`CLAUDE.md` §6)**: IMAP/CalDAV productivity and local media generation remain outside core `server.py` as opt-in MCP servers (`src/mcp_productivity.py`, `src/mcp_media_drawer.py`), with outbound email sending permanently disabled (`OUTBOUND_EMAIL_ALLOWED = False`).

---

## Phased Rollout

### Phase 0 — Optional Module Registry (`optional_modules.py`) — **Implemented**
- Central catalog of opt-in modules with safe defaults, phase metadata, and boundary descriptions.
- Atomic merge into `settings.json["modules"]` via `GET /api/modules` and `POST /api/modules`.
- UI: `/modules` slash command, `MODULES` header button, and `#modulesDlg` modal.

### Phase 1A — Blind Compare Mode (`compare_mode.py`) — **Implemented**
- Concurrent fan-out across 2–4 local (`llm.py`), LAN-peer (`compute_peers.py`), or ready cloud (`cloud_llm.py`) models.
- Shuffled blind labels (`Model A`–`Model D`), latency & tok/s measurement, reveal-on-vote or explicit reveal.
- Persistent JSONL history (`.atlas/compare_history.jsonl`) and local-vs-cloud leaderboard.
- Endpoints: `GET /api/compare/models`, `GET /api/compare/history`, `POST /api/compare/{run,vote,reveal}`.
- UI: `/compare [prompt]` slash command and `#compareDlg` modal.

### Phase 1B — Swarm Deep Research (`deep_research.py`) — **Implemented**
- Non-blocking 4-stage research pipeline (`plan` → `gather` → `verify` → `synthesize`) with cancellation support.
- Combines Atlas Knowledge Library retrieval (`_library_retrieve` / local docs) with local or cloud model synthesis.
- Persists completed briefs in `.atlas/research_runs.json` with citation list, gap analysis, and one-click Insert into Chat / Copy Markdown.
- Endpoints: `GET /api/research/runs`, `GET /api/research/run`, `POST /api/research/start`, `POST /api/research/stop`.
- UI: `/research [topic]` slash command and `#researchDlg` modal.

### Phase 1C — Hardware-Aware Model Cookbook (`cookbook.py`) — **Implemented**
- Detects host RAM, CPU cores, and GPU VRAM (stdlib-only across Windows/Linux, with "what-if" hardware simulation).
- Scans installed `.gguf` files via `model_discovery.py` and grades curated open-weight recipes (`coder`, `mentor`, `assist`, `tasks`, `vision`) as `gpu_fit`, `hybrid_fit`, `cpu_fit`, or `too_large`.
- Generates copy-ready `llama-swap` YAML snippets without touching existing user configs.
- Endpoints: `GET /api/cookbook`, `POST /api/cookbook/recommend`.
- UI: `/cookbook` slash command and `#cookbookDlg` modal.

### Phase 2A — Workspace Docs Canvas (`docs_canvas.py`) — **Implemented**
- Side-by-side Markdown document editor & preview backed by the configured workspace folder (or `<DATA_DIR>/.atlas/docs`).
- Strict path confinement (`_resolve_target`), extension allowlist, 1 MB cap, atomic saves with SHA-256 optimistic conflict checks, and non-destructive AI rewrite proposals returning a unified diff before saving.
- Endpoints: `GET /api/docs`, `GET /api/docs/read`, `POST /api/docs/save`, `POST /api/docs/assist`.
- UI: `/docs` slash command and `#docsDlg` modal.

### Phase 2B — Local Task Scheduler (`task_scheduler.py`) — **Implemented**
- Consent-gated local recurring prompts, research briefs, and local health checks stored in `.atlas/scheduler.json` with JSONL run logs in `.atlas/scheduler_history.jsonl`.
- Starts globally paused by default (`paused: True`) and tasks default to `enabled: False`; background daemon ticker checks due tasks every 15s only when unpaused and enabled.
- Endpoints: `GET /api/scheduler`, `POST /api/scheduler/task`, `POST /api/scheduler/run`, `POST /api/scheduler/pause`.
- UI: `/schedule` slash command and `#schedulerDlg` modal.

### Phase 2C — Skills Registry Sync (`skills_registry.py`) — **Implemented**
- Versioned reusable prompt skills stored in `.atlas/skills_registry.json` with automatic patch semver bumps, revision snapshots, one-click rollback, curated starter packs, SHA-256 bundle checksums, and JSON / `SKILL.md` frontmatter import/export.
- Endpoints: `GET /api/skills-registry`, `POST /api/skills-registry`.
- UI: `/skillsreg` slash command and `#skillsRegDlg` modal.

### Phase 3 — Opt-In External MCP Packs (`external_packs.py`, `src/mcp_productivity.py`, `src/mcp_media_drawer.py`) — **Implemented**
- **Productivity MCP Pack (`productivity_mcp`, default OFF)**: Standalone JSON-RPC 2.0 stdio MCP server (`src/mcp_productivity.py`) for local tasks, local calendar, and strictly read-only IMAP header triage (`OUTBOUND_EMAIL_ALLOWED = False`, no SMTP or send tool).
- **Local Media Drawer (`media_drawer`, default OFF)**: Standalone JSON-RPC 2.0 stdio MCP server (`src/mcp_media_drawer.py`) bridging local Automatic1111 / ComfyUI / OpenAI-compatible image endpoints and storing assets in `.atlas/media/`.
- **Remote Companion (`remote_companion`, default OFF)**: One-time SHA-256-hashed bearer token issue/verify/revoke for authenticated LAN companion pairing.
- Atomic MCP server registration into `settings.json["mcp_servers"]` preserving existing servers and keys.
- Endpoints: `GET /api/packs/status`, `POST /api/packs/productivity`, `POST /api/packs/media`, `POST /api/packs/companion`.
- UI: `/packs` slash command and `#packsDlg` modal.
