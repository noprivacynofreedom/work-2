# Unintegrated documents

Made 2026-11-12. One place for notes that no integrated hub document cites.
Hub documents: README.md, docs/PROJECT-MASTER.md, docs/DEVLOG.md, docs/EVIDENCE-REGISTER.md, docs/investors/INVESTOR-PITCH-NOTES.md, CLAUDE.md.
Each section below is the original file under a heading with its old path and its last change date. Headings inside a file moved down two levels to fit under its section. The text is otherwise unchanged.
Nothing reads these files: not the app, not the build, not the tests (checked).

## Contents

1. `BUILD-RESULTS-v0.3.1.md` : Old v0.3.1 build result
2. `MANIFEST-v0.3.1.md` : Old v0.3.1 file manifest
3. `MANIFEST.md` : Old file manifest
4. `TEST-RESULTS.md` : Old test results
5. `HANDOFF-RUST-INSTALLER.md` : Handoff: Rust installer work (10 Nov)
6. `README.txt` : Old MCP monitor patch notes
7. `atlas-rust-desktop/README-ATLAS-RUST-TEST.txt` : How to use Build-Atlas-Rust-Test (older test build)
8. `docs/ATLAS-MCP-AUDIT.md` : MCP audit
9. `docs/MCP-HARDENING-2026-11-10.md` : MCP hardening notes (10 Nov)
10. `docs/ATLAS-SWARM-MANAGER-DELIVERY-PLAN.md` : Swarm manager delivery plan
11. `docs/MODEL-PERFORMANCE-RELEASE-PLAN.md` : Model performance release plan
12. `docs/NEXT-RELEASE-SEQUENCE.md` : Next release sequence
13. `docs/compute-sharing/LAPTOP-SETUP.md` : Compute sharing: laptop setup
14. `docs/compute-sharing/laptop-llama-swap.config.yaml` : Compute sharing: laptop llama-swap config (YAML)
15. `services/atlas-control-plane/TEST-RESULTS.md` : Control plane test results


---

## 1. BUILD-RESULTS-v0.3.1.md
*Old v0.3.1 build result. Last changed 2026-11-09.*

### Atlas v0.3.1 — build and test report

#### Passed
- Python pytest: 19 passed, 0 failed.
- Python compileall: passed.
- Inline app JavaScript syntax: passed.
- Queue source checks: 16 passed.
- Queue runtime harness: 5 passed.
- Desktop queue source checks: 11 passed.
- JavaScript test-file syntax checks: passed.

#### Not verified
- Rust formatting/compilation/tests and Tauri bundle: Cargo unavailable.
- Frontend TypeScript/Vite production build: npm dependency install unavailable in this environment (Vite missing from local cache).
- Live Windows WebView2 queue behavior, service shutdown, AMD GPU telemetry, llama-swap inference, Docker and PostgreSQL end-to-end.

No Rust compile or final Windows production build is claimed. Run `.\BUILD-ATLAS.ps1` on the Windows development PC after installing Node.js and Rust stable with the Tauri prerequisites.

---

## 2. MANIFEST-v0.3.1.md
*Old v0.3.1 file manifest. Last changed 2026-11-09.*

### Atlas Chat queue + Rust integration update v0.3.1

#### Modified
- `index.html` — serial queue drain now has a single owner/promise lock; it processes pending jobs sequentially, retains failed/stopped messages and pauses retries instead of silently losing work; unexpected send exceptions restore the UI/controller state. Existing green active/recent chat-history highlighting remains in place.
- `atlas-rust-desktop/src-tauri/src/main.rs` — desktop shutdown now blocks the first close request while it stops Atlas-owned child processes, serializes against in-progress startup, shuts down the Atlas Node manager, and then permits exit. Manual stop uses the async mutex rather than silently skipping cleanup when locked. Added static regression checks for the lifecycle contract.
- `validation-tests/test_chat_queue.js` — expanded source regression checks.
- `validation-tests/test_chat_queue_runtime.js` — deterministic runtime harness tests multiple sequential messages, failed-item retention, held items and send-next behavior.
- `atlas-rust-desktop/validation-tests/test_chat_queue.js` — ESM-compatible test runner and expanded queue checks.
- `BUILD-ATLAS.ps1` — runs queue source and runtime tests as part of the Windows build gate.
- `INSTALL-ATLAS-CONTROL-PLANE.ps1` — now includes safe baseline checks for `index.html` and Rust `main.rs`; conflicting local files are preserved and proposed changes are emitted separately.

#### Existing integration retained
- Rust desktop commands for health, metrics, owned process startup/shutdown, Node identity, registration, policy, model discovery, benchmark, sandbox execution and contribution ledger.
- Separately deployable Atlas Control Plane service and its PostgreSQL schema.
- Existing Python API and chat iframe architecture; no settings, user data or runtime databases are overwritten.

#### Tests run in this environment
- `python -m pytest -q tests services/atlas-control-plane/tests` — 17 passed.
- `python -m compileall -q .` — passed.
- Inline `index.html` JavaScript — `node --check` passed.
- Root queue source regression — 16 passed.
- Queue runtime harness — 5 passed, including sequential 3-message drain and lock release paths.
- Desktop queue source regression — 11 passed.
- JavaScript test files — `node --check` passed.

#### Not run / release gates
- Rust `cargo fmt`, `cargo check`, `cargo test` and Tauri packaging — Cargo is not installed in this authoring environment.
- `npm ci` / TypeScript-Vite production build — not run successfully here because the required Vite package was not cached and package registry access is unavailable.
- Windows runtime test of process shutdown, local GPU detection, llama-swap, Docker workload execution and PostgreSQL-backed control-plane end-to-end flow — not run.

**Important:** The queue fix is covered by a deterministic test of the actual extracted queue-drain function plus source checks, but still needs an interactive WebView2 test on the target Windows machine. Rust lifecycle changes are source-reviewed but not compiled here. This is an integration candidate, not a verified production release.

---

## 3. MANIFEST.md
*Old file manifest. Last changed 2026-11-09.*

### Atlas response selection and copy patch

#### Modified
- `index.html` — forces selectable text in the chat log for Chromium/Tauri WebView, adds a per-assistant-message `COPY RESPONSE` control, and makes code-block copy use a clipboard API plus `execCommand` fallback.

#### Added
- `INSTALL-ATLAS-SELECTION-FIX.ps1` — backs up the existing root `index.html` and installs this replacement.
- `ROLLBACK.txt` — restoration instructions.
- `TEST-RESULTS.md` — validation performed in the patch build environment.

#### Not changed
No Rust, React shell, Python, MCP, bot data, chat history, settings, or knowledge-library data files are modified by this focused patch.

---

## 4. TEST-RESULTS.md
*Old test results. Last changed 2026-11-09.*

### Test results

- Extracted both inline application scripts and ran `node --check`: **PASS**.
- Static regression check for forced `user-select` and `-webkit-user-select` across the chat log: **PASS**.
- Static regression check for a per-assistant-message `COPY RESPONSE` control: **PASS**.
- Static regression check for Clipboard API plus `document.execCommand('copy')` fallback: **PASS**.
- Static regression check that the complete raw assistant response is copied (not rendered HTML): **PASS**.
- Static regression check that the earlier Development Cycle `COPY OUTPUT` control remains present: **PASS**.
- ZIP integrity: to be checked after packaging.

Not run: Windows PowerShell installer execution, interactive text selection in the user's Tauri WebView, and actual Windows clipboard round-trip. Those require the user's Windows desktop runtime.

---

## 5. HANDOFF-RUST-INSTALLER.md
*Handoff: Rust installer work (10 Nov). Last changed 2026-11-10.*

### Handoff: Rust and installer changes (2026-11-10)

Nothing here was compiled or built. WSL has no Rust, no NSIS and no PowerShell. Build and test on the PC.
Repo: F:\APP-DEV\projects\atlas-chat, branch main. Read HANDOFF-NEXT.md for the rest of the open work.

#### What changed (commits fb8b8919, 0f890035, a911d1ef)
1. `src-tauri/src/main.rs`: new `data_base()`. F: drive present: data in `F:\APP-DEV\data\Atlas Chat` (old data stays). No F: drive: `%LOCALAPPDATA%\atlas-chat\data`. Added `Path` to the imports.
2. `src-tauri/src/process_supervisor.rs`: new `discover_llama_config()`. It runs `resources\atlas\model_discovery.py` with the bundled Python before llama-swap starts. It uses the config path from the JSON it prints. Any failure keeps the bundled config.
3. `src-tauri/nsis/f-drive-only.nsh`: default install folder `F:\APP-DEV\projects\atlas-chat\app` (was `...\Atlas Chat`). No F: drive: `%LOCALAPPDATA%\atlas-chat\app`, F: checks skipped. With an F: drive, Next stays disabled for a non-F: path.
4. `build-release.ps1`: prints `app\atlas-desktop.exe`. `.gitignore`: `/app/` added.
5. `resources/atlas/model_discovery.py` (new, tested in WSL: 117 tests OK). Picks the llama-swap config:
   - Bundled config has `{models}` paths. First folder holding all 5 files wins. Output: `<data>\llama-swap.generated.yaml`.
   - Else it scans for `.gguf` files and maps roles coder, mentor, assist, tasks.
   - Search order: `ATLAS_MODELS_DIR`, `<data>\models`, `<runtime>\models`, `<install>\models`, `X:\models` on the data and install drives.
6. `resources/atlas/runtime/llama-swap/config.yaml`: `-m F:\models\...` is now `-m {models}/<sub>/<file>.gguf`. Tuned flags are unchanged.
   WARNING: `resources/atlas/runtime` is in .gitignore. This file is NOT in git. It lives only in the working tree. Check that the build copies it.
   `resources/atlas/settings.json` is also ignored. I removed `data_file`, `llama_swap_exe`, `llama_swap_config` from it.
7. `install.ps1` deleted. `HANDOFF.md` release steps use `build-release.ps1`.

#### Build and check (in order)
1. `cargo check` in `atlas-rust-desktop\src-tauri`. Fix any compile error in the two Rust edits first.
2. `.\BUILD-ATLAS.ps1` (also runs the 3 node tests that WSL could not run).
3. `.\build-release.ps1`. Check: installer in `target\release\bundle\nsis`. Check the build log for "makensis" errors in `f-drive-only.nsh` (labels `has_f`, `no_f`, `done`, `ok`, `atlas_pre_ok`).
4. Run the installer. Check: folder page shows `F:\APP-DEV\projects\atlas-chat\app`. A `C:\` path keeps Next disabled. Nothing new in `%APPDATA%\dev.atlas.chat` or `%LOCALAPPDATA%\dev.atlas.chat`.
5. Launch. Check: badge shows SWAP ON, 4 bots answer. Open `F:\APP-DEV\data\Atlas Chat\app\llama-swap.generated.yaml`: no `{models}` left, `-m` paths point at `F:/models/...`.
6. Fallback test: rename `F:\models` to `F:\models-off`. Copy one `.gguf` to `F:\APP-DEV\data\Atlas Chat\app\models`. Launch. Check: all 4 bots answer with that model (mode `generated`). Rename back.
7. Space test: put a model in a folder with a space and set `ATLAS_MODELS_DIR` to it. Check: llama-swap starts it (see `logs\llama-swap.log`).
8. No-F: test: a clean VM or the laptop with no F: drive. Check: installs to `%LOCALAPPDATA%\atlas-chat\app`, data in `%LOCALAPPDATA%\atlas-chat\data`, app starts.

#### Known risks
- Rust and NSIS edits are untested. NSIS label jumps are the likeliest build error.
- llama-swap with a quoted `-m "path with space"` is unconfirmed. Paths use forward slashes and `llama-server.exe` is relative, so only the model path can have a space.
- An old install at `...\atlas-chat\Atlas Chat` is kept by an upgrade (registry path starts with F:). Uninstall it, install fresh, then Jason deletes the old folder. Do not delete it without Jason.
- No models found: mode `none`. llama-swap reports a missing `{models}/...` file. Better message not written.
- Generated config uses `-ngl 99 -c 16384 -fa on -np 1 --jinja`. No `--n-cpu-moe`. Large MoE models on small GPUs may need tuning.
- Native tool calls need `--jinja` (included). Not tested with a real model.
- `F:\APP-DEV\data\Atlas Chat` still has capitals and a space. It is the old data path. Changing it needs a data move (HANDOFF-NEXT item 13).

---

## 6. README.txt
*Old MCP monitor patch notes. Last changed 2026-11-09.*

```text
ATLAS MCP MONITOR — targeted integration patch

WHAT IT DOES
* Launches only MCP servers explicitly listed in settings.json.
* Performs real MCP JSON-RPC initialize and tools/list requests.
* Reports process state, PID, discovered tools, latency, last check and errors.
* Exposes GET /api/mcp/status and POST /api/mcp/check.
* Adds MCP status to /api/health.
* Agents can retrieve authoritative status via GET http://127.0.0.1:8090/api/mcp/status.
* Never labels a server online based on model-generated text.

INSTALL
1. Back up server.py and settings.json.
2. Copy mcp_monitor.py into the project root.
3. Replace server.py with the supplied server.py.
4. Merge the mcp_servers array from settings.example.json into your existing
   settings.json (do not overwrite your other settings).
5. Start Atlas normally. MCP servers are started lazily by POST /api/mcp/check
   or when an agent/UI asks for status with ?refresh=1.
6. Only configure servers you trust. The current mcp_agent.py exposes shell and
   file-writing capabilities; do not enable it without restricting/approving tools.

IMPORTANT
* The archive's mcp_commander.py uses a fixed workspace path and a simplified
  JSON-RPC loop. It may not fully implement current MCP transport semantics.
  The monitor will show protocol errors rather than falsely reporting it online.
* mcp_agent.py requires the MCP Python SDK and exposes terminal/file-write tools.
  It is intentionally NOT enabled by default.
* This patch adds truthful health/status visibility, not full agent tool invocation.
* app.py shutdown integration must call server.stop_mcp_services() if it starts
  MCP children. This patch's MCP processes are owned by server.py and are stopped
  by stop_mcp_services() when the host calls it; standalone server exit hooks also
  attempt cleanup. For best Windows GUI lifecycle, wire that call into app.py's
  existing stop_owned() as described in README.
```

---

## 7. atlas-rust-desktop/README-ATLAS-RUST-TEST.txt
*How to use Build-Atlas-Rust-Test (older test build). Last changed 2026-11-09.*

```text
ATLAS DESKTOP — HYBRID RUST TEST BUILD + KNOWLEDGE ENGINE
=========================================================

This is the upgrade to the installed Atlas Rust Test Build. Rust/Tauri owns the
Windows desktop window, lifecycle, health checks, CPU/RAM telemetry and owned
child-process shutdown. The existing Python compatibility backend remains the
working model orchestration + MCP host while the native Rust service migration
continues. This is intentional: it keeps the existing Atlas features usable.

WHAT IS NOW IN THE KNOWLEDGE ENGINE
----------------------------------
1. SOURCE LIBRARY
   - Markdown, TXT, CSV, JSON, YAML, Python, SQL, LOG, EPUB and PDF imports.
   - Originals and extracted text remain local under .atlas/knowledge.
   - CSVs receive deterministic schema / sample profiling before teacher study.
   - Text PDFs use PyMuPDF or pypdf. Scanned PDFs use PyMuPDF + Tesseract OCR.

2. TEACHER / DISTILLER
   - Select a larger local teacher model in the Knowledge Library.
   - Every selected source is chunked and processed; the previous 120,000
     aggregate-character truncation has been removed.
   - Hierarchical map/reduce consolidates large source collections.
   - Distilled capsules preserve source IDs, source names, limitations, concepts,
     glossary, study questions and structured concept relationships.
   - A 50 MB aggregate distillation safety limit remains to prevent accidental
     unbounded runs. Import limit remains 5 MB per source.

3. EMBEDDING INDEX + RETRIEVAL
   - Default local embedding backend: fastembed BAAI/bge-small-en-v1.5 (CPU).
   - The model is downloaded on first setup/index build; allow internet for that
     first download. It is then cached by FastEmbed on the machine.
   - Optional alternative: set settings.json embedding_model to a llama-swap
     model alias that implements OpenAI-compatible POST /v1/embeddings.
   - If embeddings are unavailable, Atlas explicitly falls back to lexical search;
     it does not pretend that lexical retrieval is vector semantic search.
   - Search is available in the Knowledge Library UI and relevant retrieved
     chunks are injected into normal chat with source titles/provenance.
   - Rebuild the index after changing the embedding model or source corpus.

4. KNOWLEDGE GRAPH
   - The teacher is asked for structured concepts, typed relationships and
     grounded question/answer examples for student training.
   - Atlas persists them with source provenance and exposes an SVG graph view/API.
   - EXPORT STUDENT PACK creates a ZIP with Markdown/JSON knowledge, graph JSON,
     manifest and training.jsonl for retrieval or a later fine-tuning pipeline.
   - This creates teacher-generated training material; it does NOT update model
     weights or claim to fine-tune a student model. Actual weight training is a
     separate operation and must be run with a compatible training stack.

5. MCP / ATOMIC CHATS / DEVELOPMENT CYCLE
   - Existing live MCP chat tool loop, MCP audit, Atomic Chats and Development
     Cycle remain in the compatibility backend. No MCP server configuration,
     chat data, settings, model files or Git metadata is reset by this upgrade.

INSTALL THE UPGRADE
-------------------
Extract this package. Run in PowerShell:

  Unblock-File .\Update-Atlas-Rust-Knowledge.ps1
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Update-Atlas-Rust-Knowledge.ps1 -Project "F:\APP-DEV\projects\atlas-chat"

The updater expects the exact known Rust Test Build snapshot that was installed
in the previous step. It backs up managed files and stops if index.html/server.py
have changed unexpectedly. It does not overwrite data.json, settings.json,
.atlas/knowledge, .webview, exports, models or Git metadata.

INSTALL OPTIONAL KNOWLEDGE DEPENDENCIES
---------------------------------------
Run:

  powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Setup-Atlas-Knowledge.ps1

This installs FastEmbed, PyMuPDF, pypdf, Pillow and pytesseract into Python 3.
Scanned-PDF OCR also requires the Tesseract OCR application installed on
Windows and available on PATH. OCR is bounded to the first 100 pages per PDF.
The first FastEmbed model download needs internet; subsequent indexing is local.

RUST BUILD
----------
The previous direct script command can be blocked by PowerShell policy. Use the
included CMD wrapper instead (it launches a child PowerShell with process-scoped
ExecutionPolicy Bypass):

  .\Build-Atlas-Rust-Test.cmd

Or development mode:

  .\Build-Atlas-Rust-Test.cmd -Dev

Prerequisites: Node.js LTS, Rust stable via rustup, Visual Studio 2022 Build
Tools with Desktop development with C++, and WebView2 Runtime.

The small desktop/index.html is only the Tauri/Vite React bootstrap. Opening it
by double-click is not the way to run Atlas; it now displays an explanation if
opened directly. The actual Atlas web UI is the project-root index.html. The
generated desktop shell opens that UI served locally at 127.0.0.1:8090. It supervises only the child processes it starts; it does not
use global taskkill commands. Python continues to own MCP stdio and model
orchestration in this hybrid migration stage.

CONFIGURE EMBEDDING MODEL (OPTIONAL)
------------------------------------
The default is:
  "embedding_model": "fastembed:BAAI/bge-small-en-v1.5"

To use llama-swap embeddings instead, set that key in settings.json to the
exact model alias that supports /v1/embeddings. Restart Atlas, then use BUILD /
REBUILD KNOWLEDGE INDEX in the Knowledge Library. If the endpoint is not
supported, Atlas reports lexical_fallback and continues to work.

VALIDATION IN THIS BUILD ENVIRONMENT
------------------------------------
- 16 Python tests passed, including >120k character distillation, embedding
  adapter/vector ranking and student knowledge-pack export coverage.
- Python compilation passed.
- Both inline JavaScript blocks passed node --check.
- MCP stdio initialize/discovery/call/independent verification tests passed.
- HTTP smoke: import, reindex, search and graph routes passed in lexical fallback.
- Rust/Cargo Windows executable build was NOT run here: Rust toolchain is not
  installed in this build environment. Windows GPU/model runtime also remains
  to be verified on the user's PC.


CHAT QUEUE
-----------
You can submit messages while Atlas is generating. They are added to OUTGOING
QUEUE and are processed sequentially after the current response completes.
Each queued item captures its target chat, bot and attachments. The queue is
persisted in data.json, limited to 20 messages, supports removal/clear, and can
be manually resumed after an interrupted session.

RUST BUILD ERROR: link.exe NOT FOUND
------------------------------------
Your log shows the frontend build succeeded. Cargo then failed because the
Microsoft MSVC linker was not available in PATH. This is a Windows C++ toolchain
prerequisite, not an Atlas Rust source error.

Install Visual Studio 2022 Build Tools and select:
- Desktop development with C++
- MSVC v143 x64/x86 build tools
- Windows 10 or Windows 11 SDK

Then rerun Build-Atlas-Rust-Test.cmd. It attempts to load the Visual Studio
developer environment automatically using vswhere. If discovery fails, open
"x64 Native Tools Command Prompt for VS 2022" and run the .cmd from there.

The npm allow-scripts warning for esbuild is separate from the linker failure.
The log reports zero npm vulnerabilities; do not blindly approve install scripts.
```

---

## 8. docs/ATLAS-MCP-AUDIT.md
*MCP audit. Last changed 2026-11-10.*

### Atlas MCP Audit (Phase 1, read-only, no fixes applied)

Audited 2026-11-10 on branch `main` (CLAUDE.md warns `main` may be an OLD branch: confirm the real app branch before Phase 3).

#### Corrections to the handoff
- `resources/atlas/server.py` is NOT a copy of `src/mcp_commander.py`. It is the Atlas HTTP backend (port 8090). Different program.
- `src/mcp_commander.py` is NOT the file with the `HERE` write bug. `mcp_agent.py` is.
- "Duplicate" is real, but between the repo root and `resources/atlas/` (plus `Atlas Chat/atlas/`, `target/{debug,release}/atlas/`, `release/`, `backups/`).

#### File table
| File | Purpose | Creates/Reads | Depends on | Active? |
|---|---|---|---|---|
| `src/mcp_commander.py` | Stdio MCP server "atlas-commander", READ-ONLY tools: atlas_project_status, atlas_list_files, atlas_read_file, list/read/verify_workspace_file. No write tool. | Reads files under `ROOT` = env `ATLAS_WORKSPACE` else parent of `src/` | stdlib only | YES: the only server in `settings.json` |
| `server.py` (HTTP backend) | Proxy/chat API on 8090; injects system prompts, docs, runs MCP tool loop | settings.json, data.json, prompts/, workspace dir | mcp_monitor, mcp_chat, config, llm, docsearch, book_tools | YES (spawned by Rust `process_supervisor.rs:1128` as `root/server.py`) |
| `mcp_monitor.py` | Launches MCP servers from `settings.json` `mcp_servers`, substitutes `{python}`,`{project}`,`{workspace}`, sets `ATLAS_WORKSPACE` env only if workspace given | Popen child processes | settings.json | YES |
| `mcp_chat.py` | Tool loop: calls llama-swap, executes tools, re-posts. **Appends `role:system` messages at END** (lines 212, 414) | HTTP to upstream 8080 | mcp_monitor | YES |
| `mcp_agent.py` | A SECOND, separate MCP server "atlas-chat-rust-builder": `run_terminal_command`, `write_project_file`. Both use `cwd/target = HERE` (its own folder), not project root. Unrestricted shell. | writes to its own dir | `mcp` pip pkg | NO: not in settings.json; only referenced by `dev_cycle.py` compile check. Dead/dormant |
| `config.py` | Settings loader; `WORKSPACE_DIR` from env `ATLAS_CHAT_WORKSPACE` or settings `workspace_dir` | settings.json | stdlib | YES (identical hash in root, src/, resources) |
| `tauri.conf.json` | Bundles `resources/atlas` -> `atlas` in NSIS installer; `beforeBuildCommand: npm run build`. **No step copies Python files in.** | - | - | YES |
| `Cargo.toml` | Rust deps only. No build script copying Python. | - | - | YES |
| `process_supervisor.rs` | Finds runtime root: env `ATLAS_RUNTIME_ROOT`, then `ATLAS_PROJECT_ROOT`, then `resources/atlas` next to exe (lines 423-445); spawns python `server.py` | | | YES |

#### Phase 1B answers
- One MCP server or two? **One running** (atlas-commander). `mcp_agent.py` exists but is never launched.
- Which Python files does Tauri package? Everything in `src-tauri/resources/atlas/` (a directory mapping, so whatever is in that folder, including its own `src/mcp_commander.py`, runtime/python).
- Copies or symlinks? **Plain copies.** Zero symlinks found.
- When is server.py copied to resources/? **Never automatically.** `build-release.ps1` only checks bundled Python exists; no copy step. Resources is hand-edited (CLAUDE.md says it is the authoritative one). Hence drift.

#### Duplication / drift (md5)
- `src/mcp_commander.py` == resources == `Atlas Chat/atlas` == target/release == target/debug copies: IDENTICAL. Safe.
- `config.py`, `mcp_chat.py`, `mcp_monitor.py`, `mcp_agent.py`, `llm.py`: root == resources: identical.
- **`server.py`: root != resources** (resources has richer event projection around line 613). `src/server.py` and `release/server.py` are each different again. Three+ divergent server.py versions.
- `Atlas Chat/atlas/server.py` == resources (an installed copy).
- `src/` also holds stale `server.py`, `config.py`, `llm.py`, `test_local_model.py`.

#### Answers to the critical issues (hypotheses, to verify in Phase 2)
1. **Jinja "System message must be at the beginning"**: strong suspect is `mcp_chat.py:212` and `:414`, which `append` a system message after user/assistant/tool messages. Strict templates (Qwen etc.) reject that. Secondary: `server.py _add_docs` only checks `msgs[0]`, and `_inject` merges into the first system found anywhere, which can leave it non-first. Fix idea (not applied): send those instructions as the first system message or as a user message.
2. **Which file runs**: packaged app runs `resources/atlas/server.py`, which launches `resources/atlas/src/mcp_commander.py`. They are different programs, not duplicates of each other.
3. **File-writing bug**: only in dormant `mcp_agent.py` (`HERE`). The live commander has no write tool, so a model "writing files" through Atlas currently cannot; that is itself a gap.
4. **Project root**: commander uses `ATLAS_WORKSPACE`, set by mcp_monitor only if a workspace is given; else falls back to the parent of `src/` (the install dir when packaged). Rust uses `ATLAS_PROJECT_ROOT`/`ATLAS_RUNTIME_ROOT`; config.py uses `ATLAS_CHAT_WORKSPACE`. Three names, three meanings.

#### Proposed Phase 3 (awaiting your approval)
1. Declare `resources/atlas/` the single source (matches CLAUDE.md). Diff-merge root `server.py` into it first (nothing lost).
2. Remove stale root/`src/`/`release/` copies (git history keeps them); keep one unambiguous `mcp_commander.py`.
3. Fix message ordering in `mcp_chat.py` and `_add_docs`; log the outgoing payload once to confirm.
4. One env var `ATLAS_PROJECT_ROOT` for read, and a separate `ATLAS_WORKSPACE` for writes; decide whether to give the commander a safe write tool and retire `mcp_agent.py`.

---

## 9. docs/MCP-HARDENING-2026-11-10.md
*MCP hardening notes (10 Nov). Last changed 2026-11-10.*

### MCP and request handling: bugs found and fixed (2026-11-10)

Branch: `fix/mcp-request-hardening`. Code is in `atlas-rust-desktop/src-tauri/resources/atlas/` (the shipped copy).
Tests: `tests/test_mcp_hardening.py` (24 tests). Against the old code 22 of 23 original tests failed; all pass now.

#### Read first
- This branch has a first commit marked `SNAPSHOT (not my work)`. It is an exact copy of another session's
  uncommitted edits (`mcp_chat.py`, `server.py`, `src/mcp_commander.py`, tests). It exists only so the fixes sit on
  top of that code. Commit that other work on `main` first. The snapshot is then dropped (rebase).
- Not tested here: the Windows app itself (Tauri build, installer). Tests ran on Linux with Python 3.12.
  The Windows UTF-8 fix was tested by forcing `PYTHONIOENCODING=ascii`, not on a real cp1252 console.
- One test fails before and after, and is not MCP: `test_docsearch ... cached_postings_refresh` (file time stamps).

#### Bugs and fixes
| # | Where | Bug (what the user sees) | Fix |
|---|---|---|---|
| 1 | `server.py` bot files | `GET`/`POST /api/bot/<id>/files` always answered 404. The code read `parts[2]` (the bot id) as `"files"`, and used `"bot"` as the id. | One route parser `_bot_files_route`. 400 for bad id/name/JSON, 413 over 1 MB, name rules (no `..`, `/`, `\`, `:`). |
| 2 | `server.py` `_body` | A bad `Content-Length` dropped the connection. No size limit. Chunked bodies were read as empty. | 400 / 413 with a message. Limit 192 MB (a 100 MB book is about 134 MB of base64). |
| 3 | `server.py` chat | An online MCP server with no tools made every chat fail with 502. | `NoLiveTools`: fall back to plain chat. |
| 4 | `server.py` chat | A server that could not start was re-tried on EVERY chat message (each waited for the timeout). A server that died while another was up was never restarted. | `MCPMonitor.ensure_online(30)`: retry each down server at most once per 30 s. |
| 5 | `server.py` `/swarm` | `"  /swarm fix it"` lost its first letters (sliced the unstripped text). Keywords with a comma (`"test,"`) did not match. | Slice the stripped text. Match words with a regex. |
| 6 | `server.py` docs/retrieval | A system message with list content (images) raised `TypeError` in `_add_docs`. Retrieval skipped silently. | `_append_system_text` handles both shapes. |
| 7 | `server.py` errors | Bad chat request answered 502 (should be 400). Client leaving mid-reply gave a traceback. `BadStatusLine` from llama-swap was not caught. | Mapped to 400 / ignored / 502. |
| 8 | `mcp_monitor.py` | One stdout line that is valid JSON but not an object (`123`, `[]`) killed the reader thread. Every later call then timed out. | Skip non-objects. Never block on a full reply slot. Ignore server-to-client requests. |
| 9 | `mcp_monitor.py` | `tools/list` read only page 1 (spec uses `nextCursor`). A non-object tool entry crashed the handshake. | Read all pages (max 20). Drop bad entries. |
| 10 | `mcp_monitor.py` | Every status check sent `initialize` again. A strict server answered with an error and the monitor then KILLED the healthy server. | Healthy server: refresh `tools/list` only. |
| 11 | `mcp_monitor.py` | Two servers with one name replaced each other silently. | Name gets `-2`, `-3`. |
| 12 | `mcp_chat.py` | A tool with no parameters called with `"arguments": null` failed as invalid. | `null` means `{}`. |
| 13 | `mcp_commander.py` | `read_workspace_file` could read `.git/config` (remote URLs with tokens), `.env`, `*.pem`, `*.key`. Only listing hid `.git`. | Protected-file check in read, verify and list. |
| 14 | `mcp_commander.py` | `settings.json` was readable in clear text, including `upstream_api_key`. | Values of key/token/secret/password fields are masked. |
| 15 | `mcp_commander.py` | Whole file loaded before the size check. Binary files returned garbage. Hashing loaded the whole file. | `stat` first. Refuse NUL bytes. Hash in 1 MB blocks. |
| 16 | `mcp_commander.py` | `git_diff` said "truncated to 12 KB" but kept the LAST 12 KB (the start was lost). Listing cut at 200 without saying so. | Keep the start. `truncated` flag in both. |
| 17 | `mcp_commander.py` | Windows stdio is cp1252: non-ASCII file text broke or garbled the reply. | Force UTF-8 on stdin/stdout. |
| 18 | `mcp_commander.py` | An id-less message other than `notifications/*` got a reply with `"id": null`. `params` not an object gave -32603. Client protocol version ignored. | No reply to notifications. -32602 for bad params. Echo a supported version. |

#### Found, NOT changed (your decision)
- `/swarm` prints "Executing in parallel... each agent will execute" but nothing runs. It only prints a plan. The text is misleading.
- If the client sends its own `tools`, and the model calls one of them, the loop answers "Unknown MCP tool" instead of handing the call back. `as_sse` also drops `tool_calls` and `usage`.
- Duplicate-call suppression lasts for the whole request. A model that legitimately re-reads a file it just changed is told "duplicate".
- Dormant `mcp_agent.py` writes into its own folder (`HERE`). Not launched by default. Already in `docs/ATLAS-MCP-AUDIT.md`.
- `mcp_chat.max_tokens` is raised to at least 1024 even if the client asked for less.

---

## 10. docs/ATLAS-SWARM-MANAGER-DELIVERY-PLAN.md
*Swarm manager delivery plan. Last changed 2026-11-09.*

### Atlas Swarm Manager delivery plan

**Status:** baseline installer verification in progress. Feature source edits and folder rename wait until the current app install and startup checks pass.

#### History sweep

I checked 38 recent Codex history entries and 114 ChatGPT history records, filtered 16 Atlas-related conversations, and reviewed recent turns in those threads. I found overlapping work, so this plan treats old requests as backlog evidence and current owner reports as implementation evidence. Unrelated Nyx, Raspberry Pi, and general chats stay out of this Atlas plan.

#### Feature inventory

| Request | Current evidence | Next acceptance check |
| --- | --- | --- |
| Reliable current-app installer and in-place update | A 0.1.1 NSIS candidate exists. Release checks caught a benchmark regression before install. The reliability owner fixed the mock test; release owner is rebuilding and will install after checks. | Verify installer hash, install over current app, retain user data, launch app, confirm services and MCP start, close app, and confirm only owned services stop. |
| Model discovery, loading, switching, CPU/GPU split, KV cache, TTL, multiple models, speed and quality | llama-swap v270 and llama.cpp `0.9.0-dev`; five valid profiles. Current primary profile uses Q8 KV, 32K context, one slot, Vulkan offload and CPU MoE. Model benchmark timing patch is in the candidate. No on-device inference benchmark exists yet. | Measure cold load, warm time-to-first-token, prompt and decode rates, unload, VRAM/RAM, CPU/GPU load, and task-quality results. Compare one setting at a time. |
| Chat UI and model controls | Current UI stacks Context, Plugins and MCP panels, highlights the active panel, loads status at startup, and hides test controls by default. Source checks passed. | Verify panels, empty/error states, model selection, chat send/retry, and recovery in installed WebView. |
| Workflow and safe parallel agents | `dev_cycle.py` exists; prior project review reports Team Run currently executes sequentially. Older requests describe isolated workspaces, dependency-aware scheduling, per-agent progress/tests/review, and explicit approval before integration. | Run dependent and independent tasks; verify workspace isolation, dependency order, cancellation, failure recovery, test evidence, and no direct writes to the live tree. |
| Knowledge Library and retrieval | `server.py` and `knowledge_engine.py` provide import, PDF extraction with optional OCR, semantic retrieval with lexical fallback, distillation, graph and student packs. `docsearch.py` provides a separate simple keyword search. | Import text and PDF, test scanned-PDF OCR when installed, retrieve a known fact with source attribution, verify lexical fallback with inference offline, and test malformed/oversized input. |
| Image input and detection | Chat UI has image attachments. Current route still needs a verified vision-capable model path and a clear unsupported-model state. | Send one image to a vision model and a text-only model. Confirm the first receives the image and the second shows a useful error without losing the text prompt. |
| Voice input settings | Browser speech dictation exists, but current code uses the browser default language. | Select and persist a language; test allowed, denied, unavailable, and empty-recognition states. Confirm the transcript enters the intended chat only. |
| Bot activity companion | New request: a compact, pet-like Atlas companion that helps track every bot action. Existing Operations data has bot/chat/queue state and MCP audit records, but event coverage must be confirmed. | Show real time-stamped action, bot, status, and outcome events. Check queue, model, tool, failure, retry, and completion events. Label missing data instead of inventing status. |
| MCP and plugin integration | Atlas Chat already has an MCP monitor, tool loop, audit recorder, and internal `atlas-commander`. History also requests separate read-only Atlas and Atlas Chat Bridge connections, scoped roots, and no write/delete/arbitrary command tools. | Verify each adapter exposes only its approved roots and read tools; reject writes, deletes, and commands; test audit states and exact path errors end to end. |
| Node and Operations | Tauri UI has hardware telemetry, model benchmark, consent/policy controls, network status and contribution ledger. Existing lifecycle policy separates local node participation from remote execution. | Verify live telemetry, consent changes, owned-process cleanup, model list, audit view, and accurate unavailable states. |
| Product and project rename | Requested project folder `atlas-chat` → `atlas-swarm-manager` and visible app name `Atlas Swarm Manager`. The Codex project label already reads “ASM - ATLAS SWARM MANAGER”; no project-rename API is available in the connected app tools. Tauri `productName` also controls Windows install directory, Start Menu folder, and registry key, so keeping the app identifier alone does not preserve the old install destination. | Update active source paths, launch/build/install scripts, package/product labels, window titles and help text. Keep `dev.atlas.chat` to preserve the app data path. Test the old-to-new installer upgrade path and user-data access before release. Search again, build, upgrade, and verify existing app data remains available. |

#### Owners and file boundaries

| Owner | Scope | Order |
| --- | --- | --- |
| Validate Atlas Chat release build | Current installer, install, startup, packaged-resource checks | First. Do not add source changes to this candidate after its final regression run. |
| Improve model reliability and offloading | `atlas_node.rs` benchmark contract and subsequent runtime measurements | After baseline install. The current timing patch is in the candidate; verify its test before install. |
| Plan Atlas model loading fixes | `docsearch.py` and retrieval tests | After baseline install. Keep `server.py` and UI outside this scope. |
| Fix model loading and chat flow | `index.html`, packaged UI mirror, `App.tsx`, Knowledge Library UI and image/voice controls | After baseline install. Own visible activity companion UI; use real event sources. |
| Research model performance optimizations | `docsearch.py`, `dev_cycle.py`, and their focused tests after baseline install | Owns retrieval and workflow implementation; keep `server.py` and UI outside this scope. |
| Coordinate MCP tool development | `F:\APP-DEV\mcp-project-bridge` only | Keep Bridge changes outside Atlas release source until separately reviewed and integrated. |
| Research model performance optimizations | Rename inventory, release plan, integration checks | Keep the map current and review owner evidence. |

#### Rename sequence

1. Finish and verify the current 0.1.1 baseline install first.
2. Freeze the new project path and visible name: `F:\APP-DEV\projects\atlas-swarm-manager` and `Atlas Swarm Manager`.
3. Update first-party source, mirrored runtime, scripts, docs, icons/title surfaces, and release paths. Keep historical backups, generated logs, and old patch archives unchanged as audit records.
4. Keep the Tauri identifier `dev.atlas.chat` for the first rename release so user-data location remains stable. Test how the changed `productName` affects the existing install directory, Start Menu entry, and registry key before upgrading.
5. Rename the project folder only after every active source owner has finished. Update all path references, then validate the Codex project entry and launcher path.
6. Run static reference search, unit/regression checks, production build, installer upgrade, and installed app end-to-end tests.

#### Integration gates

1. Baseline installer passes hash verification, install, launch, service health, user-data preservation, and shutdown checks.
2. Owners complete their scoped edits and tests. Any schema change goes to the UI owner before labels or controls change.
3. Integrate workflow, retrieval, image, voice and activity events with no file-owner collisions.
4. Run the full test suite, including MCP and queue tests, Rust tests, frontend build, retrieval tests, and workflow tests.
5. Run installed end-to-end checks for every row above. Record actual model benchmarks and quality results; no speed or accuracy gain is claimed without a measured comparison.
6. Apply the project and product rename, build the renamed installer, upgrade in place, verify data and startup, then report hashes, test results, and unresolved gaps.

#### Known limits

- No model server was running during the source audit. Model load, unload, GPU/CPU use and quality measurements are still missing.
- The Codex app tools expose no project-path rename action. The local directory can be renamed after all active chats release it, but the Codex project registration may need a user-side path refresh.
- The current installer is still in baseline verification. Do not rename its active root path before the release owner finishes install and startup checks.

---

## 11. docs/MODEL-PERFORMANCE-RELEASE-PLAN.md
*Model performance release plan. Last changed 2026-11-09.*

### Model performance release plan

**Status:** v0.2 coordinated release plan. The current baseline app install comes first. Optimization source edits resume after startup checks. No model-runtime defaults changed.

#### Goal

Improve perceived response time and resource use for local inference without trading away task quality or stability. Treat cold model start, warm first-token delay, prompt processing, token generation, and model unload as separate measurements. Do not claim a speed or accuracy gain until the same hardware, model file, prompt set, and runtime build have been compared.

#### Current source audit

- Atlas routes local inference through llama-swap at `127.0.0.1:8080` and a Vulkan llama.cpp server.
- The local llama-swap configuration declares one model active at a time, five model aliases, and a 900-second idle TTL. The installed binary reports llama-swap `v270 (a093766)` and llama.cpp `0.9.0-dev` build `12125` (`7d516e25e`). Config validation passed for five models and zero peers. Confirm actual swap behavior before changing this policy.
- The configured primary model is a 35B-A3B MoE GGUF. It asks llama.cpp to offload layers to GPU, keep 28 MoE experts on CPU, use a 32K context, use Q8 KV, run one sequence slot, use Flash Attention, and enable draft MTP. These settings are hypotheses to benchmark, not proven wins.
- The primary GGUF file is 21.71 GB on disk, larger than the config comment's 16 GB VRAM figure. CPU placement and VRAM headroom matter. Measure peak usage rather than assuming full GPU residency.
- A second dense 31B profile uses 44 GPU layers and an 8K context. Compare its startup and quality against the MoE model for tasks that need a stronger dense model.
- The local config comment reports 16 GB VRAM and 31 GB RAM. This session could not read hardware telemetry. Verify these values on the target PC before using them as release facts.
- Atlas has a model benchmark command, but its Ollama path sends `keep_alive: "0"`, which forces unload after its request and cannot measure a warm request. Its OpenAI-compatible path estimates token speed from total wall time, so it mixes model startup, prompt processing, and generation. The fallback also reuses a timer started before the attempted Ollama request, which can contaminate its measurement. Do not use the displayed number as decode tokens per second.
- The active desktop release validation reports source checks passing and NSIS packaging in progress. No Atlas model endpoint was listening when checked, so this pass has no cold-start, warm-start, unload, GPU, or CPU benchmark result.
- All five configured model files exist. The local llama-swap config validator passed; this validates the YAML and declared model list, not model startup or GPU fit.

#### Release work map

| Stage | Work | Exit evidence |
| --- | --- | --- |
| 0. Freeze baseline | Record commit, binary hashes, model file hashes, llama-swap and llama.cpp versions, driver, GPU/VRAM, RAM, power mode, settings, and ambient load. Run each case three times after one warm-up. | Baseline CSV and raw logs are saved. |
| 1. Measure | Add separate cold load, ready time, warm TTFT, prompt tokens/sec, generation tokens/sec, total latency, unload time, peak VRAM/RAM, and CPU/GPU utilization. Test one request and two queued requests. | Metrics have definitions, units, sample count, and raw source fields. |
| 2. Tune one variable | Compare GPU/CPU MoE split, context size, KV type, mmap/load mode, draft MTP, flash attention, and idle TTL one at a time. Restore baseline between runs. | A result table reports median and p95 plus quality checks for each candidate. |
| 3. Check model quality | Use a fixed local task set for Atlas coding, tool selection, JSON schema validity, and general responses. Keep prompt, system text, decoding settings, and token limit fixed. Add a public benchmark only when the model/task license and scoring are suitable. | No critical task regresses. Report accuracy and failure examples beside speed. |
| 4. Change design | Add proper startup and unload measurements to the benchmark path. Keep defaults conservative; let profiles expose an explicit memory budget and concurrency policy. Do not refactor the provider interface until measurements show duplicated or blocking lifecycle code. | Tests prove endpoint compatibility, request timeout behavior, model swap correctness, and unload recovery. |
| 5. Release candidate | Run source tests, package build, startup/recovery tests, cold and warm benchmark matrix, idle expiry test, and UI model switch test. Save versioned results and hashes. | No unexplained regressions; rollback settings and previous package are available. |

#### Swarm delivery map

| Owner | File scope | Deliverable and handoff |
| --- | --- | --- |
| Fix model loading and chat flow | Root `index.html` and its packaged mirror | Scoped image attachment, voice availability/language, and benchmark result UI. Report source checks before release packaging. |
| Improve model reliability and offloading | `atlas-rust-desktop/src-tauri/src/atlas_node.rs` and isolated tests | Correct timer boundaries and distinguish Ollama server timings from OpenAI whole-request estimates. Report tests and fields before UI labels are finalized. |
| Plan Atlas model loading fixes | `docsearch.py` and isolated retrieval tests | Small retrieval correctness or latency improvement with a repeatable test. Keep `server.py` and UI out of scope. |
| Validate Atlas Chat release build | Build scripts, Tauri package artifacts, installer, and install checks | Wait for source owners, package the integrated files, preserve rollback, and report exact hashes and runtime checks. |
| Research model performance optimizations | This plan and integration review | Keep the shared work map current; compare owner evidence to release gates and record blockers. |

The release owner must package the updated root UI from the bundled runtime resources. A Vite rebuild alone does not copy that file. Install only after the resource hash matches and model benchmark labels match the runtime fields.

Workflow, retrieval, image, and voice work stays scoped to the existing features. Add broader feature work only when a check shows a concrete bug or missing control; do not combine unrelated redesigns with the model performance release.

**Sequence gate:** keep current candidate files frozen through the baseline app install and startup checks. Then resume the scoped model benchmark, workflow, retrieval, image, and voice improvements. Integrate those changes into a later candidate, run each owner’s regression checks, and rebuild only after all source owners report ready.

#### Baseline candidate record

- Built: 2026-11-09, isolated Rust target `atlas-rust-desktop/src-tauri/target/isolated-atlas-release`.
- Tauri release build and NSIS package: **passed**. The updated packaged `atlas/index.html` matches the root UI source SHA-256.
- Executable SHA-256: `BCC4D6D61A85D160D2C56667844240DC28271FE3FFB59DFB2C3AC0F051607749`.
- Installer: `atlas-rust-desktop/src-tauri/target/isolated-atlas-release/release/bundle/nsis/Atlas Chat_0.1.1_x64-setup.exe`, 327,963,936 bytes, SHA-256 `46C160BE0BCFF8C1B49BD939CF0579DE2111C44457166F8AC433D6152BBC0D3F`.
- Install and startup verification: **pending** with the release owner. Do not call this candidate installed or runtime-verified yet.
- Model load, first-token, generation, unload, CPU/GPU, and quality measurements: **not run** because no model server was active.

#### Benchmark protocol

1. Use the same machine and power mode. Close unrelated GPU jobs. Capture GPU VRAM, system RAM, CPU use, GPU utilization, and temperature before and during each run.
2. For each model profile, record one cold start after verified unload, then three warm requests. Record model-ready time from the request that triggers load until the endpoint is ready. Record API TTFT from request send until first streamed token; if streaming is unavailable, mark TTFT unavailable instead of estimating it.
3. Separate prompt prefill rate from generated-token rate. Preserve server token counts and timings when available. Do not divide generated tokens by whole request wall time and label it generation speed.
4. Test short prompt, long prompt, short answer, and fixed long answer. Keep maximum context and output tokens fixed within each comparison.
5. Test concurrency at 1 and 2. On this 16 GB VRAM target, never assume two large models should stay loaded together. Compare queued requests on one model with two simultaneously loaded models only if VRAM headroom is observed and both processes can be safely supervised.
6. Measure unload start-to-process-exit and resource return after the configured idle TTL. Check that an in-flight request completes and the next request reloads the right model.
7. Report median and p95 across repeated runs. Keep raw CSV and server logs with the release artifact.

#### Initial optimization hypotheses

- **Model residency:** a 900-second TTL may avoid repeated cold loads during active work but retain large models during idle. Compare 0, 120, 300, and 900 seconds against observed session gaps and memory pressure. Keep the current value until data supports a change.
- **Spin-down timing:** llama-swap v270 documents `POST /api/models/unload/:model_id`. Use that lifecycle API for repeatable cold-start tests, and time the unload response plus process/resource exit. Do not unload a model while a live request uses it.
- **CPU/GPU split:** GPU placement generally lowers latency only while VRAM fits weights, KV cache, and runtime headroom. Compare the current `--n-cpu-moe` and GPU layer settings with a small sweep. Reject configurations that cause paging, OOM, or unstable token speed.
- **KV cache:** KV demand grows with context length and concurrent sequences. Compare 8K, 16K, and 32K context at one slot before changing parallelism. Compare Q8 KV to the current profile only with quality and kernel compatibility checks.
- **Load mode:** compare mmap and the current load mode on this Windows system using cold start, resident RAM, page faults, and warm decode speed. Do not infer that loading less into RAM is faster from the config comment alone.
- **Speculative decoding:** compare draft MTP on and off using identical prompts. Keep it only if acceptance rate and end-to-end latency improve without quality or reliability loss.
- **Multiple models:** preserve single-active-model swapping as the default until memory telemetry shows safe headroom. If two models are needed at once, use an explicit compatible group and a shared concurrency/resource limit. A longer TTL alone does not guarantee safe simultaneous residency.
- **Quantization and accuracy:** compare candidate GGUF files on the same task set. Perplexity can catch distribution loss, but it does not replace task accuracy, tool-call validity, or human review of representative failures.

#### Refactor assessment

The current measurable gap is the benchmark contract, not evidence that the inference provider needs a broad rewrite. First split benchmark results into cold load, warm latency, prefill, decode, unload, and resource fields. Then isolate provider-specific telemetry behind a small adapter while retaining the current OpenAI-compatible request path. Avoid moving the Python compatibility server or changing the desktop lifecycle during this optimization release. Keep one-model swapping until the concurrency experiment demonstrates a safe memory budget.

#### Sources

- llama.cpp server options cover continuous batching, Flash Attention, KV cache types, parallel slots, and prompt cache behavior: [server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md).
- llama.cpp documents how context length and parallel slots affect KV memory, and recommends reducing context or slots before reducing GPU offload: [multi-GPU troubleshooting](https://github.com/ggml-org/llama.cpp/blob/master/docs/multi-gpu.md).
- llama.cpp describes importance matrices for quantization: [imatrix README](https://github.com/ggml-org/llama.cpp/blob/master/tools/imatrix/README.md). Quantization impact depends on model and calibration data; example perplexity deltas are not Atlas accuracy claims.
- llama.cpp describes perplexity as one way to compare quantized model quality: [perplexity tool README](https://github.com/ggml-org/llama.cpp/blob/master/tools/perplexity/README.md).
- llama-swap supports TTL-based unloading and explicit concurrent model groups; its runtime configuration must be checked before changing the local single-model policy: [llama-swap project](https://github.com/mostlygeek/llama-swap), [configuration schema](https://github.com/mostlygeek/llama-swap/blob/main/config-schema.json).
- EleutherAI's harness supports repeatable zero-shot and few-shot task evaluation with task and generation settings: [LM Evaluation Harness](https://github.com/EleutherAI/lm-evaluation-harness).

#### Current release decision

**Do not change model runtime defaults yet.** First collect an on-device baseline and correct the benchmark so it separates loading, prompt, generation, and unloading. The running release validation remains the source of build status. Hardware benchmark and packaged Windows runtime status remain open.

---

## 12. docs/NEXT-RELEASE-SEQUENCE.md
*Next release sequence. Last changed 2026-11-09.*

### Atlas Desktop — next release sequence

**Status:** planning, 9 November 2026. This document does not claim release readiness.

#### Release rule

Atlas is pre-release. Reliability, data preservation, observable behavior, and target-Windows evidence take priority over adding feature count. Keep Atlas Desktop separate from Atlas Online. Keep the Python chat backend as a compatibility layer. Do not change model defaults or the desktop lifecycle without measurements and an owner-approved release window.

#### Work map

| Order | Scope | Owner / dependency | Exit evidence |
|---|---|---|---|
| 1 | Finish the active Windows package and install validation. Include the latest chat UI source in the packaged resources. | Release validation chat owns the current package. No other session edits bundled UI during this step. | Artifact version and SHA-256; package/build logs; installed executable matches the intended artifact; launch and rollback results. |
| 2 | Verify local model discovery, selection, cold load, warm first token, response completion, and recovery after a failed request. | Model-loading chat; run after the package is installed. | Per-model pass/fail, measured load and first-token times, exact prompt outcome, and server logs. A timeout or empty response is a failure. |
| 3 | Fix the user-reported queue and conversation-switching blockers. Preserve active generation when opening another conversation; advance remaining queue items after removal. Also fix bot drag-to-reorder and prevent bot names from being selected. | Next source iteration after the package freeze. | Targeted regressions plus Windows UI checks with an active request, multiple queued messages, and repeated bot drag/drop. Preserve stored chats and queue state. |
| 4 | Verify the “open this conversation” route to Operations and selected-conversation diagnostics. | After item 1, using the installed package. | Chat-to-Operations route test, correct conversation identity, return to Chat, and no loss of in-flight work. |
| 5 | Add the planned selected-task detail view: created artifacts, full paths, evidence, workspace, and a “View live feed” action. Label snapshots as snapshots; do not imply live streaming until a stream exists. | Separate Operations feature after items 3–4 pass. Keep the existing visual design. | Keyboard and mouse interaction checks, empty/error states, path display, and evidence that the feed source is live or clearly marked as a snapshot. |
| 6 | Capture a reproducible local inference baseline before tuning CPU/GPU, KV cache, context, or model-residency defaults. | Model-performance release plan; do not overlap its benchmark work. | Raw logs/CSV, machine and model identity, cold/warm timings, prompt/decode rates, peak CPU/RAM/VRAM, median/p95, and quality checks. |

#### Release gates

Do not call the release accepted until all applicable gates pass:

- Chat send, stop, failed-request recovery, queue edit/hold/remove/reorder/advance, and conversation switching.
- Model discovery error and timeout states, model selection, cold load, warm response, and correct loaded status.
- Plugin and MCP status, refresh, error handling, and no duplicate in-flight discovery.
- Atlas Node and Operations navigation and primary controls.
- Data/settings preservation across package install and rollback.
- Windows package launch, owned-process shutdown, and logs tied to the packaged version.
- CPU/GPU performance claims supported by the benchmark protocol in `MODEL-PERFORMANCE-RELEASE-PLAN.md`.

#### Current known failures and limits

- A prior real-model smoke request returned an empty answer after 302 seconds. This is a failed smoke test, not a model pass.
- The latest chat UI source passes inline JavaScript syntax, six focused UI safety contracts, both queue suites, and the React TypeScript check. It did not receive live UI interaction or end-to-end verification. The packaged HTML mirror matches the source by SHA-256.
- An earlier NSIS dependency verification stopped on a blocked network download. The release owner now reports the full validation pipeline passed and a fresh isolated candidate build is underway. The package and installed application remain unverified. Keep release build inputs frozen until that owner reports its result.
- The model-performance plan found that the existing benchmark can combine load, prompt processing, and generation time. Do not treat its current tokens-per-second display as decode speed.
- The model reliability owner reports the focused benchmark regression suite passes and the OpenAI fallback now uses its own timer. No local inference endpoint or usable GPU telemetry was available for real measurements.
- Retrieval/workflow owner reports 6/6 focused tests and a synthetic 800-file, 6,400-chunk retrieval result of 63.54 ms baseline versus 2.42 ms optimized. This synthetic warm-query result is not a production benchmark. Their broader suite passed 66/69; two tests failed on denied localhost sockets and one 404 assertion remains unresolved.
- The redacted per-chat activity endpoint and its UI consumer are implemented in source, but the endpoint and live panel have not been tested together.
- The user reported bot drag-to-reorder does not work and bot names remain selectable. Release owner queued these for the next source update. Source review found that only each card accepts `dragover`; dropping in the 8 px gaps or blank list area is rejected because `#bots` has no drop handler. Live interaction still needs to confirm whether that matches the user's drag path. Do not change the current package inputs during packaging.
- Node registration, sandbox enforcement, GPU passthrough, and network workload execution remain separately gated roadmap work. They are outside this desktop release sequence.

#### Coordination boundaries

- Release chat owns package and install work.
- Model-loading chat owns model discovery and end-to-end chat checks.
- Model-performance work owns the benchmark protocol and resource measurements.
- The next implementation chat should take one reliability blocker at a time after the release owner clears the shared checkout.
- Do not run a second build or test suite while the release owner is active.

#### User-authorized feature follow-up

Implement these after the current package and core reliability gates. Keep the current visual style and use small, reviewable changes.

1. **Workflow presets:** save and rerun Team Run bot selections, round count, and task instructions. Add safe stop and retry at step boundaries without losing finished output.
2. **Retrieval visibility:** show retrieval mode, source references, and an optional-index failure in chat. Keep ordinary chat working when retrieval is unavailable.
3. **Image capability check:** detect image attachments and check explicit model capability metadata before sending. Explain unknown/text-only support and preserve text-only fallback.
4. **Voice settings:** let users choose recognition language and listening mode. Keep dictation insert-only, default it off, disclose that browser recognition may use an external service, and handle permission/API errors.

5. **Activity companion:** source implementation is present. The compact panel uses the redacted per-chat `/api/ops/conversations/{id}/activity?after=&limit=` projection, filters tool/task/error events, and avoids event messages and details. Live API/UI verification remains open. Add bot labels or trace-linked detail only through a separately reviewed safe projection.

The image capability control is explicit per bot (`unknown`, `vision`, or `text-only`); it does not auto-detect model capabilities. Unknown asks before sending images, and text-only blocks them. Voice settings and external-service disclosure are in source; live permission and recognition behavior remain unverified. Workflow presets and retrieval source visibility remain follow-up items.

Validate each feature separately before including it in a package. Do not claim image understanding or local speech processing without runtime evidence.

---

## 13. docs/compute-sharing/LAPTOP-SETUP.md
*Compute sharing: laptop setup. Last changed 2026-11-10.*

### Laptop setup (compute sharing)

Verify the llama-swap version first: `llama-swap --help` (the `--listen` flag is needed).

1. Copy `laptop-llama-swap.config.yaml` to the laptop. Replace every path.
2. Open PowerShell on the laptop. Start llama-swap for the home network:
   `llama-swap.exe --config C:\atlas\llama-swap\config.yaml --listen 0.0.0.0:8080`
3. Open the firewall for the private (home) profile only. Run PowerShell as Administrator:
   `New-NetFirewallRule -DisplayName "Atlas llama-swap (home only)" -Direction Inbound -Protocol TCP -LocalPort 8080 -Profile Private -Action Allow`
   Set the laptop network to "Private". Never use the Public profile. Never forward the port on your router.
4. Find the laptop address: `ipconfig` (IPv4 Address, for example 192.168.1.50).
5. On the PC, open Atlas, tab ATLAS NODE, section "Compute sharing". Enter `http://<laptop address>:8080`, press "Test connection", then "Save machine".
6. Chat with the model alias that the laptop reports (for example `laptop-7b`). The reply shows "answered by: Laptop".

Only the model port is open. The Atlas Chat API (127.0.0.1:8090) stays on its own machine.

---

## 14. docs/compute-sharing/laptop-llama-swap.config.yaml
*Compute sharing: laptop llama-swap config (YAML). Last changed 2026-11-10.*

```yaml
# Laptop llama-swap config. Copy to the laptop, for example C:\atlas\llama-swap\config.yaml
# Edit every path below. Do NOT keep the PC paths (F:\...). Wrong paths cause
# "upstream command exited prematurely".
# Use ONE small model for a laptop with a small GPU: 7B or 14B at Q4 (14B Q4 needs about 9 GB).
models:
  "laptop-7b":
    cmd: >
      C:\atlas\llama-cpp\llama-server.exe
      --port ${PORT}
      -m C:\atlas\models\YOUR-7B-MODEL-Q4_K_M.gguf
      -ngl 99 -c 8192
    ttl: 600
```

---

## 15. services/atlas-control-plane/TEST-RESULTS.md
*Control plane test results. Last changed 2026-11-09.*

### Atlas Control Plane v0.1.0 — test results

Executed in the available build environment:

| Test | Result |
|---|---|
| Desktop registration route contract | PASS |
| Signed workload route contract | PASS |
| Timestamp and replay guard source contract | PASS |
| Immutable image and scheduler signature contract | PASS |
| Owner consent and heartbeat freshness guard | PASS |
| Receipts default to non-verified and zero billable units | PASS |
| Network inference consent propagation | PASS |
| Loopback-only default binding | PASS |
| Customer billing/payments not falsely represented | PASS |

Command:

```sh
python services/atlas-control-plane/tests/test_contract.py
```

Result: **9 passed, 0 failed**.

Also executed across the existing project and control-plane contract suite:

```sh
python -m pytest -q tests services/atlas-control-plane/tests
python -m compileall -q .
node --check validation-tests/test_chat_queue.js
node --check atlas-rust-desktop/validation-tests/test_chat_queue.js
node --check atlas-rust-desktop/validation-tests/test_atomic_chats.js
```

Result: **15 pytest tests passed**; Python compileall and all three Node syntax checks passed.

Not run: Cargo check/test, Tauri build, TypeScript/Vite production build, PostgreSQL integration tests, Docker sandbox tests, Windows GPU tests or live node registration. Cargo is unavailable in the authoring environment; `npm ci --offline` could not resolve uncached Vite package files. These are build/runtime gates, not passed checks.
