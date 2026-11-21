# Atlas Chat: handoff of all unfinished work (2026-11-10)

Read this first. HANDOFF.md is the older log and the rules file. This file lists only what is still open.
Repo: F:\APP-DEV\projects\atlas-chat (WSL: /mnt/f/APP-DEV/projects/atlas-chat), branch main.
Shipped backend and UI (the only copy now): atlas-rust-desktop/src-tauri/resources/atlas/

## Rules
- Never push, never send email, never delete files outside atlas-chat without Jason.
- Commit only your own files (git add <file>). Never git add -A. Do not git pull (tree is dirty).
- Client installs use normal (non-abliterated) models only.
- Keep keyboard access, visible focus, reduced motion, phone-width layout.
- Only one chat works on this project at a time. Jason runs builds in his own window (.\build-release.ps1).
  Do not edit resources/atlas while a build runs.
- WSL: no Windows .exe, no PowerShell, no Windows node, no push. Python: ~/atlas-venv/.venv/bin/python (uv, 3.12).
  git: git -c safe.directory='*' -c core.autocrlf=true <cmd>
- Keep .ps1 files ASCII only (PowerShell 5). Add a docs/DEVLOG.md entry for each change.
- Short ASD-STE100 sentences. First line = one action.

## State now
- Done and checked in code: Zeus load-fail guard, 10x bots (8) with merge into old installs, Jinja system-message fix,
  commander v0.3.0, stale src files and mcp_agent.py removed, root duplicates and old handoffs deleted (see DEVLOG).
- Tests in WSL: tests/ 82 OK, validation-tests/ 9 OK, atlas-rust-desktop/validation-tests 31 OK, check-bundle.py OK.
- Backups: F:\APP-DEV\backups\atlas-cleanup-20261110-full.tar.gz, atlas-duplicates-20261110.tar.gz.
  (atlas-cleanup-20261110.tar.gz is redundant.)

## Uncommitted work of mine (mixed with Jason's changes, so not committed). Commit these together:
- resources/atlas/server.py (empty llama_swap defaults, plus about 12 lines of the Jinja work)
- tests/test_no_hardcoded_paths.py (5 tests, fails until server.py is committed)
- BUILD-ATLAS.ps1 (runs both validation-tests folders, node tests use the shipped index.html)
- Also uncommitted from Jason: validation-tests/test_commander_paths.py, test_system_message_order.py, tests/_paths.py.

## UNFINISHED, in priority order

### A. Needs a decision from Jason
1. DONE: install.ps1 deleted for good on 2026-11-10 (Tauri installer replaces it).
   Restore it, or drop the client installer plan.
2. Shipped settings.json holds Jason's F:\ llama-swap paths and data_file. Make a clean client copy.
   Rust process_supervisor.rs (line ~1021) reads llama_swap_exe from settings.json.
3. Client model set: normal models, 8/12/16 GB tiers. Write repo, file name, size, sha256 for each in HANDOFF.md.
4. Keep "compression": "zlib" in tauri.conf.json? (source unknown)
5. Remove Desktop and Start Menu shortcuts for strict "F: only"? Claude-style context panel (never built)?
   Rename to Atlas Swarm Manager (keep dev.atlas.chat; test installer upgrades)?
6. Delete the redundant backup tar.gz, branch feat/ponytail-and-skills (obsolete), and stray root files
   (atlas-*.log, atlas-*.txt, s.txt, swpr, logs/) after Jason checks them.

### B. Must run on the PC (nothing here was run: no PowerShell in WSL)
7. .\BUILD-ATLAS.ps1 and the 3 node tests: validation-tests\test_chat_queue.js, test_chat_queue_runtime.js, test_ui_safety_contracts.js
   (pass the shipped index.html path).
8. .\launch.ps1 (now checks resources\atlas\server.py). The three Start *.bat files still hold F:\ paths and
   are modified by Jason: check them.
9. .\bench.ps1 -ToolsDir <folder> (or env ATLAS_TOOLS_DIR) and .\test-models.ps1 -Models coder,mentor,assist,tasks.
10. Rebuild Tauri (.\build-release.ps1), install, then runtime test in the Windows window: default prompt, knowledge library,
    10x bots on a fresh and an old data.json, /swarm, queue, bot drag, Stop. No regressions.
11. Real-model test of file tools (Edit bot > Workspace folder > Read only > "what is in this folder").
    llama-server needs --jinja for native tool calls. Also send one message per bot and run one Team run.
    A timeout or empty answer is a failure (the last smoke test returned empty after 302 s).
12. Installer checks (NSIS, F: only): folder page keeps Next disabled for a C: path, default
    F:\APP-DEV\projects\atlas-chat\Atlas Chat, no "Delete the application data" box. Nothing new in
    %APPDATA%\dev.atlas.chat or %LOCALAPPDATA%\dev.atlas.chat. Find out what the 2026-11-09 23:00 installer in
    target\release\bundle\nsis holds. Test data and settings preservation across install and rollback.
13. Data move to F:\APP-DEV\data\Atlas Chat\app (app closed, back up first, merge by chat id, delete C: copies only
    when Jason agrees). Two data sets: root data.json (1.9 MB) and %APPDATA%\dev.atlas.chat\data.json (19 bots).
    The installed app (F:\...\Atlas Chat\atlas) reads its own data.json.

### C. Code to write
14. Env vars: ATLAS_PROJECT_ROOT, ATLAS_RUNTIME_ROOT, ATLAS_WORKSPACE, ATLAS_CHAT_WORKSPACE, ATLAS_DATA_DIR.
    Unify and document one scheme. Rust data_root() falls back to root/.atlas-data, Python to its own folder: reconcile.
    Needs a Rust change and a build.
15. Queue and conversation switching (NEXT-RELEASE-SEQUENCE item 3): keep generation running when another chat opens,
    advance the queue after removal. Bot drag-to-reorder: #bots has no drop handler, gaps reject drops. Bot names must not be selectable.
16. Operations: "open this conversation" route check, selected-task detail view (artifacts, full paths, evidence,
    workspace, "View live feed"; label snapshots as snapshots). Activity endpoint /api/ops/conversations/{id}/activity
    and its panel are untested together.
17. Benchmark: split cold load, ready time, warm first token, prefill, decode, unload. The current tok/s mixes load and decode.
    Fix Ollama keep_alive "0" and the shared timer in atlas_node.rs. Then baseline CSV before any tuning
    (MODEL-PERFORMANCE-RELEASE-PLAN.md). Do not change model defaults without measurements.
18. Feature follow-ups (one at a time, small): workflow presets for Team run (save, rerun, stop and retry at step boundaries),
    retrieval source visibility in chat, image capability check per bot (unknown/vision/text-only), voice settings live checks.
19. Optional: safe write_workspace_file in the commander (inside root, create-only unless overwrite=true); review
    Desktop\at patches (Atlas-MCP-Supplement, Atlas-Dev-Engine-MCP-v1.8); package the /swarm skill
    (python -m scripts.package_skill <skill-path>) if it ships to others.
20. Client release: bundle folder (app, llama-swap, llama, models), clean-VM install, smoke test, git tag after merge.
    Missing: offline install (pip download wheels), uninstaller, auto update, code signing, licence check of models,
    llama.cpp and llama-swap. Scanned-PDF OCR: not planned.

### D. Checks by eye (untested)
21. Text selection CSS in index.html: MCP, Ops and Usage dialog text may be non-selectable. Message text must stay selectable.
22. Right-click opening the Windows Share panel (guards never tested live). Context/Plugins/MCP panels stack vertically.
    TEST/VERIFY/ITERATE hidden unless ?dev=1. Logo crop and animation.
23. Frontend mismatch after the 2026-11-09 source loss: atlas-rust-desktop/src (App.tsx, CSS, main.tsx) is not exact.
    Check the startup shell and Nodes/Operations panels. More copies may be in Desktop\at and Downloads.
    atlas-rust-desktop/index.html must stay the React startup page. Do not copy the chat page there.
24. Do not strip .pyc files from the bundle (main.rs sets PYTHONDONTWRITEBYTECODE=1).
25. Mentor test on real advisor questions; assist and coder tuning with live hardware readings.

## Warnings
- ZEUS bot gave wrong advice to commit .exe installers. target/ and "Atlas Chat/" are gitignored. Installers go in releases.
- Do not push. Branch feat/default-prompt exists locally. The old Desktop handoff said to push: ignore that.
- Other repo: atlas\atlas-components\scripts\kill-llama\Stop-LocalLLM.ps1 has an uncommitted change (stops llama-swap).
  Ask before committing.
- Unexplained: what removed the folders on 2026-11-09 23:39, and the chat request sent at 20:21:24.
