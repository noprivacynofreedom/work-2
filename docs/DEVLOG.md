# Atlas Chat — Development Log
**Living chronological engineering record**  
**Last reconstructed:** 8 November 2026

> Evidence discipline: entries distinguish reported actions, staged patch contents, test results and target-machine acceptance. A patch version is not automatically a public product release.

## 2026-11-07 — Project baseline and patch reconciliation

- A source archive upload was recorded with 474 entries verified.
- The archive was described as containing Python backend/chat, Rust/Tauri desktop, MCP, Dev Engine/sandbox, Atlas Node/Control Plane, Swarm patches, manifests, recovery/merge-review material and tests/release docs.
- Baseline testing was reported as 17 Python tests passing and 5 failing.
- Known baseline issues included missing root `docs/atlas-node/GATEWAY-CONTRACT.md`, absent `_post_completion`, child-process leakage after failed MCP handshake, and mismatch between advertised `atlas_list_files` and expected `list_workspace_files`.
- Root and nested v0.3.1 snapshots were both present; source reconciliation was required before treating either as canonical.
- Planned order: reconcile patches, repair MCP/process lifecycle, restore gateway contract, run regression and integrate Swarm/Node.

## 2026-11-07 — Atlas Swarm Operations Integration v0.1

- User ran `INSTALL-ATLAS-OPS.ps1` from `Atlas-Swarm-Operations-Integration-v0.1`.
- Installer reported installation into `atlas-rust-desktop/src-tauri/src/main.rs`, `atlas-rust-desktop/src/App.tsx` and `atlas-rust-desktop/src/atlas-node.css`.
- Backups recorded: `.atlas-ops-backup-20261107-201111` and `.atlas-ops-backup-20261107-201119`.
- Installer reported it did not modify existing chat UI, bot definitions, `settings.json`, `data.json` or Python server files.
- Scope: Operations dashboard foundation, saved-config bot inventory, model/chat/message counts, queue-state visibility, MCP audit-event visibility and periodic polling.
- Classification: documented installed; not equivalent to a complete distributed swarm execution system.

## 2026-11-07 — Agent Observability v0.1 (staged patch)

- Staged patch described an agent registry, IDs/parent IDs, PID/host/OS/model, current task/stage, heartbeats, stale-agent detection, CPU/memory metrics foundation, structured logs, task/trace/span identifiers, SQLite persistence, SSE activity transport, screenshot storage foundation and Python SDK `agents/atlas_agent_runtime.py`.
- Staged tests were reported as 16 passing.
- Installation on the user's Windows working tree was not confirmed.
- Remaining work: connect real workers, instrument model/tool calls, connect handoffs/failures, integrate Rust Node supervisor, build trace waterfall, live logs/metrics and real desktop/SSH viewing.
- Important distinction: screenshot capture is not live desktop streaming.

## 2026-11-07 — MCP Fix and Shortcuts Specification v0.1

- Staged contents included MCP handshake cleanup, `docs/atlas-node/GATEWAY-CONTRACT.md` and keyboard-shortcuts specification.
- MCP smoke test and three MCP monitor integration tests were reported passing in the staged tree.
- Installation not confirmed.
- Keyboard shortcuts remained a specification, not a completed UI feature.

## 2026-11-07 — Dev Engine Local Worker v1.3 (staged patch)

- Local model-powered development worker described using OpenAI-compatible llama-swap endpoint `http://127.0.0.1:8080`, default model `coder`.
- Design included isolated disposable workspace, JSON patch proposals, human review before application, no automatic live-repository writes and no automatic test execution.
- MCP tools: `dev_local_model_status`, `manager_execute_local`.
- Remote model endpoints gated by `ATLAS_DEV_ALLOW_REMOTE_LLM=1`.
- Staged test result reported: 22 tests passed; Python compile checks passed.
- Windows inference, MCP handshake and production integration were not confirmed.

## 2026-11-07 — Control Plane v0.3.0 / v0.3.1 integration

- Installer reported installation of roadmap/release gates, build scripts, manifests, Control Plane documentation, Docker assets, Rust service, migrations, scheduler-key utility, contribution-verification utility, contract tests and Atlas Node integration tests.
- Existing differing files were preserved as `.atlas-control-plane-proposed` rather than overwritten. Reported examples included `index.html`, `atlas-rust-desktop/src/App.tsx`, `src-tauri/src/main.rs` and `validation-tests/test_chat_queue.js`.
- Backup recorded: `.atlas-control-plane-backup-20261107-183856`.
- Installer reported it preserved `settings.json`, `data.json` and `server.py`.
- The integration was not considered complete until proposed merges were reviewed and `BUILD-ATLAS.ps1` and target runtime acceptance were run.
- Control-plane remote workload consent was explicitly not to be enabled before build and security gates.

## 2026-11-07 — Desktop build-sequence v0.3.3 / v0.3.4

- A strict build sequence was prepared: React production build → Rust formatting/check/tests → Tauri bundle; transcript logging and stop-at-first-failure behavior included.
- One authoring environment lacked Rust/Cargo and could not complete dependency installation; no build success was claimed there.
- A user-provided Windows log later reported Node 26.13.0, npm 11.20.0, rustc 1.99.1 and cargo 1.99.1.
- `npm ci --no-audit --no-fund`: PASS; 24 packages added.
- React production build (`tsc -b && vite build`): PASS.
- `cargo fmt --all -- --check`: FAIL due to formatting-only diffs in `build.rs`, `evidence.rs`, `main.rs`, `process_supervisor.rs` and `telemetry.rs`.
- Rust compile/check, Rust tests and Tauri bundle were not reached in that run.
- Next recorded action: run `cargo fmt --all`, then rerun with `-SkipInstall`.

## 2026-11-07 — Desktop design correction build

- A later design-correction production build was reported successful.
- Executable size: 12,370,432 bytes.
- SHA-256: `175516B88D9F250EBD77C2ADAC8E267607B906285BC7270E3AB8FBBA8D7848B4`.
- NSIS and MSI artifacts were generated.
- Five nonfatal `unused_mut` warnings were reported.
- Backup: `backups\\atlas-design-correction-20261108-003247`.
- This evidence establishes a reported build result for that snapshot, not proof that all later source changes were included or that the installed app is the same binary.

## 2026-11-08 — Swarm worker registration attempt

- Worker registration reported success at `127.0.0.1:8090`.
- Agent ID recorded: `agt_8abefe98530646ca8a34aa8498803e72`.
- Shell execution was disabled and workspace configured.
- Task outcome: 1 failed / 0 completed.
- Failure details were not known in the recovered record; do not represent this as a successful task execution.

## 2026-11-08 — Rust desktop / launcher and installation integrity

- Engineering handoff recorded the need to prioritize launcher/installer and defer Jinja, Node/Operations UI expansion and drag-drop.
- Release and installed executable hashes were recorded as different:
  - Release SHA-256 prefix/suffix: `1CD300...B60C2B`
  - Installed SHA-256 prefix/suffix: `5FEDED...A24DAD`
- Atlas was registered twice (NSIS/MSI), both labeled v0.1.0 and pointing to the same install path.
- Shortcuts bypassed the intended launcher.
- Runtime project location recorded as `F:` and models at `F:\\models`.
- A chat source file was restored from a verified pre-polish backup; restored file SHA-256 `688FE8...DCE54`, 130,196 bytes. The damaged version was backed up; Node/Operations were preserved.
- These details show why installation identity, launcher routing and artifact hashes must be part of the release evidence.

## 2026-11-08 — MCP, queue, UI and knowledge patch evidence

- A validation package reported Python compile checks passing.
- MCP loop regression tests: 2 passed, covering duplicate-call suppression and exhausted-round-budget behavior.
- Existing MCP Commander smoke test reported handshake, discovery, execution, verification and path containment passing.
- Avatar HTTP integration test reported PNG upload HTTP 201, correct content type and byte-identical retrieval; path-traversal bot ID rejected with HTTP 400.
- Frontend inline JavaScript syntax checks passed.
- A separate Dev Engine sandbox v1.5 workstream reported 31 unit tests passing. It added host approval-consumption API/CLI bridge, per-run staging copy, strict result schema/identity/consistency validation, bounded output, host-side SHA-256 snapshots, exclusive snapshot creation, audit events and CLI evidence verification.
- Windows Sandbox launch and guest toolchain execution remained target-machine acceptance tests.

## 2026-11-08 — Current user-reported blockers

- Queue advancement: after removing queued messages, remaining items do not reliably move up / get read by the AI.
- Conversation navigation: opening a conversation can cancel active generation.
- Operations navigation: selecting “open this conversation” does not take the user to the Operations page as expected.
- These are active, user-reported defects. They are not fixed or accepted in this record.
- User explicitly requested that fixes be end-to-end credible, not speculative or partial.

## 2026-11-08 — Operations selected-task requirements

- User requested selected-task detail view showing created artifacts, full file paths, evidence/workspace, and a “VIEW LIVE FEED” control similar to VNC.
- Requirement should be delivered without destabilizing Chat or Node.
- Actual live desktop streaming must not be implied by a screenshot-only implementation.

## Version and iteration register (reconstructed)

| Version / artifact label | Workstream | Evidence classification |
|---|---|---|
| Development Cycle / Atomic Chats v2 | Earlier source/reference project | Original project source/reference; not a replacement for current tree |
| Full Source v0.3.0 | Consolidated Python-era source snapshot | Archive exists in recovered records |
| Full Source v0.3.1 | Consolidated source snapshot | Archive exists; canonical/current status requires tree comparison |
| Deep Purple UI v0.3.0 | Rust desktop visual theme | Patch/archive listed; exact current installation not established |
| Control Plane v0.1.0 | Rust service foundation | Archive listed; integration later iterated |
| Control Plane merge v0.3.0 | Node/control-plane integration | Installer reported partial merge; proposed files remained |
| Queue/Rust integration v0.3.1 | Queue, Node and control-plane integration | Patch/archive listed; target runtime acceptance required |
| Desktop build sequence v0.3.3 | Ordered desktop build workflow | Script archive listed |
| Desktop build sequence v0.3.4 | Corrected build workflow | Windows user log recorded React pass, Rust fmt check fail |
| Operations Integration v0.1 | Operations UI foundation | Documented installed |
| Agent Observability v0.1 | Agent registry and telemetry | Staged; installation unconfirmed |
| MCP Fix / Shortcuts Spec v0.1 | MCP reliability and shortcut specification | Staged; installation unconfirmed |
| Dev Engine Local Worker v1.3 | Local development agent | Staged; Windows integration unconfirmed |
| MCP merged safe overlay v1.5 | MCP/Dev Engine integration | Archive and validation records exist; exact current state requires inspection |
| Dev Engine sandbox v1.5 | Isolated execution and evidence | 31 staged unit tests reported; Windows Sandbox acceptance pending |
| UI / avatars / browser import / MCP loop patch | UI and MCP usability/reliability | Staged validation reported; current installation must be verified |

## Ongoing entry template

### YYYY-MM-DD — [Iteration / version / patch]
- **Request / problem:**
- **Discussion / decision:**
- **Scope / files affected:**
- **Implementation:**
- **Backup / rollback:**
- **Targeted tests:**
- **Regression / integration tests:**
- **Build / package:**
- **Runtime acceptance:**
- **Evidence / hashes:**
- **Known limitations:**
- **Next action:**

## Historical completeness warning

This log is reconstructed from available saved handoffs, patch inventories, devlogs, pasted build/test logs and conversation summaries. It is not an exhaustive export of every message, every source diff or every Git commit. Dates and version labels are preserved where available; missing chronology is deliberately not fabricated. Continue by importing the repository's existing DEVLOG/CHANGELOG files, Git history, build logs and patch manifests.

## 2026-11-10 - Remove hard-coded drive paths, run all Python test folders (Claude, WSL, tested)

- `config.py`, `server.py`: `llama_swap_exe` and `llama_swap_config` now default to empty. They were `F:\app-dev\tools\...`. Set them in `settings.local.json`.
- `app.py`: if they are empty, the start-up error names the two settings. If a model server already runs on the upstream port, nothing changes.
- `bench.ps1`, `launch.ps1`, `test-models.ps1`: no `F:\` project paths. They use `$PSScriptRoot`. `bench.ps1` needs `-ToolsDir` or `ATLAS_TOOLS_DIR`. NOT run (no PowerShell here).
- `atlas-rust-desktop/validation-tests/test_mcp_stdio.py`: looked for the commander in the wrong folder. Now uses the shipped backend. 31 tests pass.
- New `tests/test_no_hardcoded_paths.py` (5 tests). Whole `tests` folder: 82 tests pass. `validation-tests`: 9 pass.
- `BUILD-ATLAS.ps1`: also runs both `validation-tests` folders. NOT run.
- Not changed: shipped `settings.json` still holds Jason's `F:\` paths (his own config). Rust `process_supervisor.rs` still reads `llama_swap_exe` from settings.json.

## 2026-11-10 - Delete root duplicates and finished handoffs (Claude, WSL)

- Deleted root copies of the backend (app, server, config, llm, mcp_*, docsearch, book_tools, books, dev_cycle, knowledge_engine, atlas_*, upstream_auth, test_*), root `index.html` and root `src/`. The shipped copy in `atlas-rust-desktop/src-tauri/resources/atlas/` is the only one.
- Deleted HANDOFF-LOCAL-INTEGRATION, HANDOFF-RECOVERY-REMAINING, HANDOFF-SWARM-FINALIZED, HANDOFF-TODO. Open items moved to HANDOFF-NEXT.md.
- Backup: `F:\APP-DEV\backups\atlas-duplicates-20261110.tar.gz` (62 entries).
- `launch.ps1` and `BUILD-ATLAS.ps1` use the shipped folder. Not run (no PowerShell).
- Tested: tests 82 OK, validation-tests 9 OK, desktop validation-tests 31 OK, `check-bundle.py` passes. Node UI tests not run (no node in WSL).

## 2026-11-10 - Bot drag-to-reorder and queue advance (Claude, WSL)

- `index.html`: the `#bots` list now has one dragover and drop handler. Gaps between bots and the space under the last bot accept drops. The drop uses the nearest bot by pointer position.
- `index.html`: bot cards and their text are not selectable (`user-select:none` on all children).
- `index.html`: removing the first queue item while idle and not paused starts the next item.
- Not run: no node in WSL, so the JS tests did not run. Test in the app: drag a bot to a gap, to the end, to the top. Remove the first queued item.
- Not done from item 15: keep generation running when another chat opens. `send()` needs a larger change.
- Only my hunks of `index.html` are committed. Jason's selection CSS, bot colour and state-load guard stay uncommitted in the working file.

## 2026-11-10 - Keep a reply visible when another chat opens (Claude, WSL)

- `index.html`: `send()` already kept streaming when you opened another chat, but the live reply box disappeared from view and the log scrolled in the wrong chat.
- New `liveGen` ({chatId, box}). `renderLog()` puts the live box back when you return to the generating chat. Scrolling only happens when the box is on screen.
- On finish, if the chat is open and the box is not on screen, `renderLog()` shows the saved reply.
- Not run: no node in WSL. Test in the app: send a long prompt, open another chat, come back. Stop must still work. Queue must still advance.

## 2026-11-10 - Make the sidebar Import button clearer (Claude, WSL)

- A user saw "is not valid JSON" while importing a book. That text only comes from the sidebar Import button, which restores a bots and chats backup. The book import (KNOWLEDGE // LIBRARY > + IMPORT SOURCES) was not the cause.
- `index.html`: button label is now "Import backup". Both error messages say to use KNOWLEDGE // LIBRARY > + IMPORT SOURCES for books and documents.
- Not run: no node in WSL.

## 2026-11-10 - Delete install.ps1, clean shipped settings.json (Claude, WSL)

- `install.ps1` deleted (old Python installer). `HANDOFF.md` release steps now use `BUILD-ATLAS.ps1` and `build-release.ps1` (Tauri NSIS).
- Shipped `resources/atlas/settings.json`: removed `data_file`, `llama_swap_exe`, `llama_swap_config` (Jason's C:\ and F:\ paths). Defaults apply.
- Existing installs keep their own settings: `main.rs` copies the shipped file only when the data folder has none. Release builds use `runtime\llama-swap` inside the install, not these settings.
- Still hard-coded: `runtime/llama-swap/config.yaml` points at `F:\models\...` (abliterated models). Next: find models by folder.

## 2026-11-10 - Find models on any PC (Claude, WSL)

- New `resources/atlas/model_discovery.py` (stdlib). Keeps the bundled `runtime/llama-swap/config.yaml` when every `-m` file in it exists. Otherwise it scans for `.gguf` files (env `ATLAS_MODELS_DIR`, `<data>/models`, `<install>/models`, `<runtime>/models`) and writes `<data>/llama-swap.generated.yaml`.
- Roles coder, mentor, assist, tasks map to files by name hints, then by size. Few models: roles share them. Skips `mmproj` files and later shards. No models found: keeps the bundled config.
- `process_supervisor.rs`: new `discover_llama_config()` runs it with the bundled Python before llama-swap starts. Any failure keeps the bundled config. NOT COMPILED (no Rust in WSL): run `.\build-release.ps1`.
- `tests/test_model_discovery.py`: 6 tests pass. Your PC: bundled config still wins because `F:\models` exists.
- Not checked: how llama-swap handles a quoted path with a space on Windows. Test with a models folder that has a space.
- Still hard-coded: `F_DATA_ROOT = F:\APP-DEV\data\Atlas Chat` in `main.rs` (the "F: only" rule). The app will not start on a PC with no F: drive.

## 2026-11-10 - No F: drive fallback, install folder without capitals or spaces (Claude, WSL)

- `main.rs`: new `data_base()`. F: drive present: `F:\APP-DEV\data\Atlas Chat` (existing data stays). No F: drive: `%LOCALAPPDATA%\atlas-chat\data`. NOT COMPILED.
- `nsis/f-drive-only.nsh`: default install folder is now `F:\APP-DEV\projects\atlas-chat\app` (was `...\atlas-chat\Atlas Chat`). No F: drive: `%LOCALAPPDATA%\atlas-chat\app`, and the F: checks are skipped. NOT BUILT (no NSIS here).
- `build-release.ps1`: prints `app\atlas-desktop.exe`. `.gitignore`: added `/app/`.
- `model_discovery.py`: model paths use forward slashes and double quotes only when they have a space. The `llama-server.exe` path is relative, so the install path never goes into the command. This avoids the llama-swap quoting question. Real test on the PC still needed.
- An old install at `...\atlas-chat\Atlas Chat` is kept by upgrades (the registry path starts with F:). To move: uninstall, then install. Jason deletes the old folder after checking it.
- Tests: 114 OK.

## 2026-11-10 - Model paths in the shipped llama-swap config no longer fixed (Claude, WSL)

- `runtime/llama-swap/config.yaml`: the 5 `-m F:\models\...` lines are now `-m {models}/<sub>/<file>.gguf`. All your tuned flags stay.
- `model_discovery.py`: finds the first models folder that holds all 5 files and writes `<data>/llama-swap.generated.yaml` with `{models}` replaced (mode `bundled-template`). Search order: `ATLAS_MODELS_DIR`, `<data>\models`, `<runtime>\models`, `<install>\models`, and a `models` folder at the root of the data and install drives (your `F:\models` is found this way). Not all files found: it scans for any `.gguf` and generates a config (mode `generated`). Nothing found: mode `none`, the bundled config is used and llama-swap reports the missing file.
- 3 new tests. Whole `tests` folder: 117 OK. `check-bundle.py` OK. A test checks the shipped config has no `X:` model path.
- Not run on Windows. Rust is unchanged since the last commit (it already calls `model_discovery.py`).

## 2026-11-11 - Remove last F:\ paths from start scripts (Claude, WSL)

- The three `Start Atlas Chat*.bat` files use `%~dp0` (their own folder) instead of `F:\APP-DEV\projects\atlas-chat`. NOT run (no Windows shell).
- `get_update.py` message and `test_local_model.py` docstring no longer name the F: folder.
- `settings.json` still holds the F: llama-swap paths (Jason's own config).
- `tests`: 126 of 127 pass. `test_mcp_hardening` swarm whitespace test fails before and after this change (swarm text changed in an earlier commit).

## 2026-11-18 — Hyperswarm, Fast NSIS Default, Optik/DedSec Themes, Test Suite Kanban MCP

- **Hyperswarm with 3 Operational Modes** (`server.py`, `swarm_run.py`, `cloud_llm.py`, `index.html`):
  - Added `/hyperswarm <goal>` and `/swarm [local|hyper|abliterated] <goal>`.
  - `hyper`: Blended hivemind leveraging free cloud API tiers (Google Gemini Flash, Groq Llama 3.3 70B, Cerebras 70B, OpenRouter free router, GitHub Models GPT-4o Mini, Mistral Small, DeepSeek) + local fallback. If a cloud API is rate-limited or busy, it automatically tries alternative free providers before local GPU execution.
  - `local`: 100% offline and air-gapped, using only local Vulkan models (`coder`, `mentor`, `tasks`, `assist`) on this PC and LAN compute peers. Zero cloud network calls.
  - `abliterated`: Unrestricted mode routing to abliterated/uncensored models (`_abliterated_local_model()` and open uncensored models) with direct objective prompts and no refusal filters.
  - Validation: `validation-tests/test_hyperswarm_modes.py` (4/4 passed), `test_swarm_pipeline.py` (20/20 passed), `test_swarm_cloud.py` (9/9 passed).
- **Fast NSIS Made Default** (`build-release.ps1`):
  - Changed default build mode to Fast NSIS (uncompressed installer packaging in ~30–60 s).
  - Added `-Compress` parameter when building smaller compressed installers for distribution.
  - Preserved `-HotSync -Launch` for instant 2-second backend/UI updates without installer.
- **Optik Dark & DedSec Dark Themes** (`style.css`, `App.tsx`, `index.html`):
  - Added Optik Dark (high-contrast cyberpunk) and DedSec Dark (terminal hacker green) alongside Classic Dark in Settings.
- **Test Suite Kanban MCP** (`test_suite_mcp.py`, `test_suite.html`):
  - Added MCP test tracking and interactive Kanban tickbox frontend with approval gating.
- **Unified Swarm Board & Archive** (`atlas_botlogs.js`, `server.py`):
  - Lightweight summary APIs (`/api/conversations?summary=1`, `/api/ops/swarm/runs?summary=1`).
  - Board filters: Live and open, Problems, Archive with category grouping.
- **Cross-Platform Linux Setup** (`setup-linux.sh`, `build-linux.sh`):
  - Added skip-if-installed package install script for Ubuntu/Fedora/Arch.
- **Documentation**:
  - Added Quickstart to `README.md`.
  - Created `docs/COMPONENTS-AND-FAQ.md` with complete architecture map, slash command guide, FAQ, and memory notes.
