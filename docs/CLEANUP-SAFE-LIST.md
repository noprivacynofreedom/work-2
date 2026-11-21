# Cleanup list: what is safe to delete (made 2026-11-12)

Rule: anything NOT in this list stays. Treat it as source code.
Nothing was deleted. This is advice only. Every item is tracked in git, so a deletion can be undone.

## How it was checked
1. Entry points the live app starts: `server.py`, `model_discovery.py`, `agents/atlas_programming_worker.py`
   (found in `src-tauri/src/main.rs` and `process_supervisor.rs`). Only `resources/atlas` ships in the installer (`tauri.conf.json`).
2. Every file was searched for by name in code, scripts, tests, settings, Rust and the build.
3. Each group below was deleted in a scratch copy. Then three checks ran: root tests, `validation-tests`, `check-bundle.py`.
   Result before and after: root tests 127 run, the same 2 failures (they fail on the branch without this work too);
   validation-tests 96 OK; bundle check passed.
4. NOT checked: a real Rust compile, the NSIS installer build, launching the app. Check those once after a cleanup.

## A. Safe to delete now
| Group | Paths |
|---|---|
| Old release backups (about 120 MB). Keep the newest `release-output-*` folder. The build makes the folder again. | `.atlas-patch-audit/` (5 old `release-output-*` folders) |
| Old logs and text dumps | `atlas-integration-test.err.log`, `atlas-integration-test.out.log`, `atlas-live-test.stderr.log`, `atlas-live-test.stdout.log`, `atlas-startup-swarm-diagnostics.txt`, `atlas-ui-source-review.txt`, `atlas-visual-reference.txt`, `atlas-lifecycle-current-source.txt` |
| Stale Rust backups (live `atlas_node.rs` is newer) | `atlas-rust-desktop/atlas_node.rs.fixed`, `atlas-rust-desktop/atlas_node-delimiter-fix.patch`, `atlas-rust-desktop/Build-Atlas-Rust-Test-BACKUP.ps1`, `atlas-rust-desktop/src-tauri/src.zip` |
| Old zip and test backup | `services/Atlas-Deep-Purple-UI-v0.3.0.zip`, `tests/test_atlas_node_integration.py.before-stop-assertion-20261108-175231` |
| Older duplicate copies. The app reads the copies inside `resources/atlas`. The root `agents/atlas_coding_swarm.py` is older. | `agents/` (7 files), `prompts/` (2 files) |
| Dead code in the bundle. No file imports or starts it. | `atlas-rust-desktop/src-tauri/resources/atlas/atlas_orchestrator.py`, `.../agents/atlas_node_dispatch.py`, `.../agents/atlas_swarm_acceptance.py` |
| Unintegrated notes. Their full text is now in `docs/UNINTEGRATED-DOCS.md`. Delete only after you have that file. | `BUILD-RESULTS-v0.3.1.md`, `MANIFEST-v0.3.1.md`, `MANIFEST.md`, `TEST-RESULTS.md`, `HANDOFF-RUST-INSTALLER.md`, `README.txt`, `atlas-rust-desktop/README-ATLAS-RUST-TEST.txt`, `docs/ATLAS-MCP-AUDIT.md`, `docs/MCP-HARDENING-2026-11-10.md`, `docs/ATLAS-SWARM-MANAGER-DELIVERY-PLAN.md`, `docs/MODEL-PERFORMANCE-RELEASE-PLAN.md`, `docs/NEXT-RELEASE-SEQUENCE.md`, `docs/compute-sharing/LAPTOP-SETUP.md`, `docs/compute-sharing/laptop-llama-swap.config.yaml`, `services/atlas-control-plane/TEST-RESULTS.md` |

## B. Safe for the app, but your call
- `bench-results.md`: copied into `docs/INTEGRATED-DOCS.txt`. `bench.ps1` makes it again. `HANDOFF.md` mentions it by name.
- `ClaudeContextMonitor/`: a separate C# tool. Nothing in the app, build or tests uses it. Delete it only if you no longer run it.
- `sample-docs/`: 3 tiny sample files. Only `HANDOFF.md` mentions them.
- `atlas-rust-desktop/Build-Atlas-Rust-Test.ps1` and `.cmd`: the older test build, replaced by `build-release.ps1`. Keep them if you use `-Dev`.

## C. Needs one small code change first (ask me)
- `atlas-rust-desktop/src-tauri/resources/atlas/app.py`: the old Python window launcher. The Rust shell never starts it.
  `tests/test_no_hardcoded_paths.py` names it, so deleting it alone makes that test fail.

## D. Do NOT delete (checked: used)
- `CLAUDE.md`, `HANDOFF.md`, `README.md`, `HANDOFF-NEXT.md`, `ATLAS-ROADMAP-AND-RELEASE-GATES.md`, `docs/PROJECT-MASTER.md`, `docs/DEVLOG.md`, `docs/EVIDENCE-REGISTER.md`, `docs/investors/`: the integrated set.
- `docs/atlas-node/GATEWAY-CONTRACT.md`: `tests/test_atlas_node_integration.py` reads it.
- `requirements.txt`, `requirements-knowledge.txt`, `Setup-Atlas-Knowledge.ps1`: knowledge setup uses them.
- `launch.ps1`, the three `Start Atlas Chat*.bat`, `build-release.ps1`, `build-progress.ps1`, `check-bundle.py`, `get_update.py`.
- `bench.ps1`, `test-models.ps1`, `BUILD-ATLAS.ps1`: tools (`BUILD-ATLAS.ps1` builds the control plane).
- `src/dev_engine/` in the bundle: an optional MCP server, off by default. Rust sets its data folder (`ATLAS_DEV_ENGINE_HOME`). It has its own tests.
- `services/atlas-control-plane/`, `docker/`: Rust and Docker code that other files use.
- `test_task_filter.py` (5 tests pass by hand) and `test_local_model.py` (a manual check) in the bundle: tests, not dead code.
- Everything on your PC that is not in git: `data/`, `bots/`, `backups/`, `logs/`, `runtime/`, `exports/`, `swarm-workspaces/`, `vnc-workspace/`, `data.json`, `.atlas/`, `.webview/`, `settings.json`.
  Your data lives there. I did not look at any of it.

## Not covered
Dead functions inside files that ARE used. That needs a separate pass.
