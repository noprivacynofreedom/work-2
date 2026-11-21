# Atlas Chat queue + Rust integration update v0.3.1

## Modified
- `index.html` — serial queue drain now has a single owner/promise lock; it processes pending jobs sequentially, retains failed/stopped messages and pauses retries instead of silently losing work; unexpected send exceptions restore the UI/controller state. Existing green active/recent chat-history highlighting remains in place.
- `atlas-rust-desktop/src-tauri/src/main.rs` — desktop shutdown now blocks the first close request while it stops Atlas-owned child processes, serializes against in-progress startup, shuts down the Atlas Node manager, and then permits exit. Manual stop uses the async mutex rather than silently skipping cleanup when locked. Added static regression checks for the lifecycle contract.
- `validation-tests/test_chat_queue.js` — expanded source regression checks.
- `validation-tests/test_chat_queue_runtime.js` — deterministic runtime harness tests multiple sequential messages, failed-item retention, held items and send-next behavior.
- `atlas-rust-desktop/validation-tests/test_chat_queue.js` — ESM-compatible test runner and expanded queue checks.
- `BUILD-ATLAS.ps1` — runs queue source and runtime tests as part of the Windows build gate.
- `INSTALL-ATLAS-CONTROL-PLANE.ps1` — now includes safe baseline checks for `index.html` and Rust `main.rs`; conflicting local files are preserved and proposed changes are emitted separately.

## Existing integration retained
- Rust desktop commands for health, metrics, owned process startup/shutdown, Node identity, registration, policy, model discovery, benchmark, sandbox execution and contribution ledger.
- Separately deployable Atlas Control Plane service and its PostgreSQL schema.
- Existing Python API and chat iframe architecture; no settings, user data or runtime databases are overwritten.

## Tests run in this environment
- `python -m pytest -q tests services/atlas-control-plane/tests` — 17 passed.
- `python -m compileall -q .` — passed.
- Inline `index.html` JavaScript — `node --check` passed.
- Root queue source regression — 16 passed.
- Queue runtime harness — 5 passed, including sequential 3-message drain and lock release paths.
- Desktop queue source regression — 11 passed.
- JavaScript test files — `node --check` passed.

## Not run / release gates
- Rust `cargo fmt`, `cargo check`, `cargo test` and Tauri packaging — Cargo is not installed in this authoring environment.
- `npm ci` / TypeScript-Vite production build — not run successfully here because the required Vite package was not cached and package registry access is unavailable.
- Windows runtime test of process shutdown, local GPU detection, llama-swap, Docker workload execution and PostgreSQL-backed control-plane end-to-end flow — not run.

**Important:** The queue fix is covered by a deterministic test of the actual extracted queue-drain function plus source checks, but still needs an interactive WebView2 test on the target Windows machine. Rust lifecycle changes are source-reviewed but not compiled here. This is an integration candidate, not a verified production release.
