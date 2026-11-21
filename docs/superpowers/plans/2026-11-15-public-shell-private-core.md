# Public Shell / Private Core: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the Atlas Chat UI and docs in the public repo `noprivacynofreedom/ASM` under a new licence. Keep the swarm core private. Ship the core to testers only as Nuitka-compiled modules.

**Architecture:** The private repo holds everything. A script exports the public subset into an ASM checkout. The build compiles the core `.py` files to `.pyd` extension modules with the bundled Python, and removes the `.py` sources from the installer resources.

**Tech Stack:** Python 3.14.6 (bundled at `atlas-rust-desktop\src-tauri\resources\atlas\runtime\python`), Nuitka, Tauri 2 / Rust, PowerShell 5.1 (`build-release.ps1`).

**Spec:** the approved design in the session request of 2026-11-15 (public shell repo, private core, Nuitka, no self-hosted server, MCP README section).

## Findings from the survey (2026-11-15). These change the design.

1. **`src.zip` is a stale backup, not the live Rust.** It is dated 2026-11-07 and holds 11 files. The live Rust is
   `atlas-rust-desktop\src-tauri\src\*.rs` (6 files, 3,619 lines). `sandbox.rs` is not in the zip.
   All stray files (`.bak`, `.pre-delimiter-fix`, `.proposed`, `.fixed`, `.patch`) are inside the zip only.
   Action: delete `src.zip` from git. Sort the live `src\` folder instead.
2. **Sort of the live Rust (`atlas-rust-desktop\src-tauri\src\`):**
   - Plumbing: `main.rs` (Tauri commands, data paths), `process_supervisor.rs` (start/stop Python, llama-swap), `telemetry.rs`, `evidence.rs`, `sandbox.rs` (Docker noVNC sandbox start/stop).
   - Core candidate: `atlas_node.rs` (compute node: Ed25519 identity, workload envelopes, benchmarks, contribution ledger).
   - The crate is ONE Tauri binary. `main.rs` registers 12 `node_*` commands from `atlas_node.rs`.
     If `atlas_node.rs` goes private, the public repo cannot build. Rust also ships only as compiled `atlas-desktop.exe`, so testers never get readable Rust.
3. **The swarm core is more than `agents\*.py`.** `server.py` imports `swarm_run`, `dev_cycle`, `compute_peers`, `context_engine` directly.
   `swarm_run.py` imports `swarm_pipeline.py`. Other core files: `atlas_orchestrator.py`, `repo_context.py`, `src\dev_engine\`.
4. **Two copies of `agents\`.** The shipped copy is `atlas-rust-desktop\src-tauri\resources\atlas\agents\`.
   The repo-root `agents\` is an older copy (`atlas_coding_swarm.py` differs). Use the shipped copy.
5. **ASM already holds the core in public.** ASM has 2 commits (not 1), both 2026-11-10. They contain `agents\*.py`, `server.py` and all of this Rust under Apache-2.0. This is the accepted risk. Only new work stays private.
6. **The local repo is already private.** `origin` = `noprivacynofreedom/atlas-chat`, PRIVATE, licence "Other". ASM is a separate repo, not a remote here.
7. **MCP UI:** the Plugin manager in `index.html` adds any **stdio** MCP server (command, args, cwd, env). It has no URL field. Remote (HTTP/SSE) servers need a stdio bridge such as `npx -y mcp-remote <url>`.
8. **Nuitka risks.** `process_supervisor.rs` starts `server.py` and the programming worker by `.py` path. `check-bundle.py` globs `*.py` and imports `server.py`. Nuitka support for Python 3.14 is not yet checked on this PC.
9. Local branch `fix/queue-in-chat-dragdrop` is 28 commits ahead of `origin`. Nothing here is pushed.

## Global Constraints

- Edit the source in `atlas-rust-desktop\src-tauri\resources\atlas\`. Never edit `F:\APP-DEV\projects\atlas-chat\app\`.
- Never push to `main` or to Jason's app branch without his clear yes. Never push to ASM without his clear yes.
- No self-hosted server.
- The private repo has no open licence: `LICENSE` says "Copyright (c) 2026 Ziyad Jenkin. All rights reserved."
- Do not rewrite ASM history. The 2 old commits stay Apache-2.0.
- Jason's data folders (`data`, `bots`, `exports`, `logs`, `runtime`, `swarm-*`, `swpr`, `vnc-workspace`) never go to ASM.

## Review Focus

1. A secret in the export: `settings.json`, `data.json`, `.env`, `LICENSE.local`, `*.log`. The export must use an allow-list, and a test must fail if one of these lands in the ASM checkout.
2. A core file in the export: any file from the core list in finding 3. A test must fail if one lands in the ASM checkout.
3. The installer starts with compiled core: `server.py` must still import `swarm_run` when only `swarm_run.*.pyd` exists. `check-bundle.py` must accept `.pyd`.
4. The programming worker is started by `.py` path. After compile, a thin `.py` launcher must stay, or `process_supervisor.rs` must start the compiled module.
5. A Nuitka failure must stop the build. It must never ship a half-compiled bundle with `.py` removed.

---

### Task 1: Remove `src.zip`

**Files:** Delete: `atlas-rust-desktop\src-tauri\src.zip`

- [ ] **Step 1:** `cd F:\APP-DEV\projects\atlas-chat` then `git rm atlas-rust-desktop\src-tauri\src.zip`
- [ ] **Step 2:** Check: `grep -rn "src.zip" build-release.ps1 check-bundle.py atlas-rust-desktop\src-tauri\tauri.conf.json` gives no match.
- [ ] **Step 3:** Commit `chore: remove stale src.zip backup (live Rust is src/)`.

### Task 2: Private core list and export script

**Files:**
- Create: `F:\APP-DEV\projects\atlas-chat\core-files.txt` (one path per line: the core list, decision Q2)
- Create: `F:\APP-DEV\projects\atlas-chat\public-files.txt` (allow-list of paths for ASM)
- Create: `F:\APP-DEV\projects\atlas-chat\export_public.py`
- Test: `F:\APP-DEV\projects\atlas-chat\tests\test_export_public.py`

**Interfaces:** Produces `export_public.py <asm_checkout_dir>`: copies allow-listed files, refuses any path in `core-files.txt`, exits 1 on a refused path.

- [ ] **Step 1:** Write tests `test_core_file_refused`, `test_secret_refused` (settings.json, data.json, LICENSE.local, *.log), `test_allowlisted_file_copied`. Use a temp dir.
- [ ] **Step 2:** Run `python -m unittest tests.test_export_public -v`. Expected: FAIL (no module).
- [ ] **Step 3:** Implement with `pathlib`, `fnmatch`, `shutil.copy2`. No new dependency.
- [ ] **Step 4:** Run the test again. Expected: PASS.
- [ ] **Step 5:** Commit.

### Task 3: Licences

**Files:**
- Create: `F:\APP-DEV\projects\atlas-chat\public-overlay\LICENSE` (MIT or Apache-2.0, decision Q4), `public-overlay\NOTICE` (states: commits before 2026-11-15 are Apache-2.0)
- Modify: `F:\APP-DEV\projects\atlas-chat\LICENSE` to "All rights reserved" (private repo)

- [ ] **Step 1:** Write the files. `export_public.py` copies `public-overlay\*` last, so it wins.
- [ ] **Step 2:** Add `test_overlay_licence_wins` to `tests\test_export_public.py`. Run. Expected: PASS.
- [ ] **Step 3:** Commit.

### Task 4: Nuitka step in `build-release.ps1`

**Files:**
- Create: `F:\APP-DEV\projects\atlas-chat\compile_core.py`
- Modify: `F:\APP-DEV\projects\atlas-chat\build-release.ps1` (after the bundled-Python check near line 210, before `check-bundle.py`)
- Modify: `F:\APP-DEV\projects\atlas-chat\check-bundle.py` (accept `<name>.*.pyd` where it globs `*.py`)
- Test: `F:\APP-DEV\projects\atlas-chat\tests\test_compile_core.py`

**Interfaces:** `compile_core.py <bundle_dir> <staging_dir>`: copies the bundle to staging, runs `python -m nuitka --module <file> --output-dir=<dir>` per core file, removes the core `.py` only after every compile passes, exits 1 on the first failure.

- [ ] **Step 1:** Check Nuitka on the bundled Python: `F:\APP-DEV\projects\atlas-chat\atlas-rust-desktop\src-tauri\resources\atlas\runtime\python\python.exe -m pip install nuitka` then `-m nuitka --version`. Stop and report if 3.14 is not supported.
- [ ] **Step 2:** Write `test_failure_keeps_py` (fake compiler exits 1, every `.py` stays) and `test_success_removes_py`.
- [ ] **Step 3:** Implement. Compile in staging only, never in the source folder.
- [ ] **Step 4:** Keep thin `.py` launchers for scripts started by path (finding 8). Each launcher is 2 lines: import the compiled module, call its `main()`.
- [ ] **Step 5:** Run the tests, then the backend suite (CLAUDE.md section 5). Expected: PASS, apart from the known failures.
- [ ] **Step 6:** Commit.

### Task 5: README MCP section

**Files:** Create: `F:\APP-DEV\projects\atlas-chat\public-overlay\README.md`

- [ ] **Step 1:** Write the section: open Plugins, add command + args + env, Save, CHECK SERVERS in MCP Monitor. Example rows: `npx -y @modelcontextprotocol/server-filesystem {workspace}`, and a remote server through `npx -y mcp-remote https://<server>/mcp`.
- [ ] **Step 2:** Commit.

### Task 6: Publish (needs Jason's yes for each push)

- [ ] **Step 1:** `gh repo clone noprivacynofreedom/ASM F:\APP-DEV\projects\ASM-public`
- [ ] **Step 2:** `cd F:\APP-DEV\projects\atlas-chat` then `python export_public.py F:\APP-DEV\projects\ASM-public`
- [ ] **Step 3:** In `F:\APP-DEV\projects\ASM-public`: `git rm` the core files that the 2 old commits hold, commit "Move core to private repo; relicense".
- [ ] **Step 4:** Show Jason `git -C F:\APP-DEV\projects\ASM-public diff --stat HEAD~1`. Push only after his yes.
