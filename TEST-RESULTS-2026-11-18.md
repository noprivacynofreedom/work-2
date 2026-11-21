# Test results 2026-11-18 (branch claude/release-checks-766a55)

Run in a git worktree on Jason's PC, on top of 99c1b340. Not run: `build-release.ps1`, the installer, the Nuitka core compile.
No call went to the local model server 127.0.0.1:8080.

## Warning first: one file on the build PC fails a check

`atlas-rust-desktop/src-tauri/resources/atlas/runtime/llama-swap/config.yaml` in the main project folder
(gitignored, so not in any branch) has this line in the `deepseek-local` entry:

    -m C:/Users/zezu1/Downloads/DeepSeek-Coder-V2-Lite-Instruct-abliterated.Q4_K_M.gguf

- `runtime/` ships in the installer (`tauri.conf.json` bundles all of `resources/atlas`), so the installer carries
  this path and an abliterated model entry. Rule: client installs use normal models.
- On a client PC the file is missing, so `model_discovery.choose` falls back to a model scan. No crash.
- `tests/test_model_discovery.py::test_shipped_config_has_no_fixed_model_paths` FAILS in the main project folder
  because of this line. `build-release.ps1` does not run unit tests, so the build itself does not stop.
- Not edited here: the file is not in git, and the fast-inference session works on the llama-swap config.
  Fix: change the line to `-m {models}/<file>.gguf` (and copy the model under the models folder), or remove the
  `deepseek-local` entry before the release build.

## Results

| Command | Where | Before fixes | After fixes |
|---|---|---|---|
| `python -m unittest discover tests` | repo root | 148 run, 1 error | 148 run, OK, 1 skipped |
| `python -m unittest discover -s ../../../validation-tests -p "test_*.py"` | `src-tauri/resources/atlas` | 132 run, OK, 1 skipped | same |
| `python check-bundle.py` | repo root | pass | pass |
| `node validation-tests/test_chat_queue.js <index.html>` | repo root | 4/4 pass | same |
| `node validation-tests/test_chat_queue_runtime.js <index.html>` | repo root | 4/4 pass | same |
| `node validation-tests/test_ui_safety_contracts.js <index.html>` | repo root | pass | same |
| `node test_atomic_chats.cjs` (was `.js`) | `atlas-rust-desktop/validation-tests` | crash | pass |
| `node test_chat_queue.js` | same | pass | pass |
| `node test_conversation_bridge.js` | same | crash, then 1 FAIL | 12/12 pass |
| `node test_swarm_chats_atomic.js` | same | pass | pass |
| `node test_swarm_lead_log.js` | same | crash | pass |
| `node test_swarm_result_delivery.js` | same | crash | pass |
| `node test_swarm_tree.js` | same | pass | pass |
| `npm ci` | `atlas-rust-desktop` | exit 0 | - |
| `npm run build` (tsc + vite) | `atlas-rust-desktop` | exit 0 | - |
| `cargo check` | `src-tauri` | exit 0, 5 warnings (unused `mut`, unused assignment) | - |
| `cargo test` | `src-tauri` | 10 passed, 0 failed | - |

`<index.html>` = `atlas-rust-desktop/src-tauri/resources/atlas/index.html`.
Node total after fixes: 13 test files, 13 pass. `e2e_context_ui.mjs` is a browser e2e script, not run.

Note: `cargo check` fails with "frontendDist ../dist does not exist" when `npm run build` has not run first.
That is order, not a bug. The release build runs the frontend build first.

## The two known failures from before 2026-11-10

- `validation-tests/test_knowledge_library.py`: imports and passes now (part of the 132 OK). No change needed.
- `tests/test_conversation_api.py`: no error in this run. No change needed.

## What I fixed (tests only, no app code)

1. `atlas-rust-desktop/validation-tests/test_atomic_chats.js` -> `.cjs`. It uses `require`, and
   `package.json` sets `"type": "module"`. It also read `atlas-rust-desktop/index.html` (the Vite frame), which has no
   Atomic Chats code. It now reads the shipped `src-tauri/resources/atlas/index.html`.
2. `test_conversation_bridge.js`: default paths were relative to the working folder and pointed to old root copies.
   They now resolve from the test file and read the shipped files. The MCP tagging check now looks in
   `mcp_audit.py` (the tagging moved there from `server.py`) and checks that `server.py` imports `MCPAuditRecorder`.
3. `test_swarm_lead_log.js`, `test_swarm_result_delivery.js`: the shipped swarm code now starts with
   `setTimeout(swarmSync, 500)` and reads `document.hidden`. The vm sandbox now gives `document: {hidden: true}`
   (and a no-op `setTimeout` in lead_log), so the auto-sync stays off in the test. index.html is unchanged.
4. `tests/test_model_discovery.py`: the shipped-config test skips when `runtime/llama-swap/config.yaml` is missing
   (gitignored, so fresh clones and worktrees have none). On the build PC it still runs, and it fails today (see warning).

## Roadmap: private keys stored as raw files (`src-tauri/src/atlas_node.rs`)

Found in `F:\APP-DEV\data\Atlas Chat\node\` (`f_data("node")`):
- `identity.pk8`: the Ed25519 device private key, raw PKCS#8 bytes (`keypair()`).
- `node-token`: the gateway bearer token, plain text (`save_config()` writes, `NodeManager::new()` reads).
- File permissions are set to 0600 on Unix only. On Windows the files get the folder's default ACL.

Plan for Windows DPAPI (not implemented: a wrong step loses the device identity, and it needs a test on the PC):
1. Add `"Win32_Security_Cryptography"` to the `windows-sys` features in `Cargo.toml`.
2. Add `protect(&[u8]) -> Vec<u8>` and `unprotect(&[u8]) -> Result<Vec<u8>>` in `atlas_node.rs`, with
   `CryptProtectData` / `CryptUnprotectData` (user scope, `CRYPTPROTECT_UI_FORBIDDEN`), free the output with `LocalFree`.
   On non-Windows both return the input.
3. Write both files through `protect`. Read through `unprotect`.
4. Migration: a DPAPI blob starts with `01 00 00 00 D0 8C 9D DF`. A raw PKCS#8 key starts with `0x30`.
   If the file is raw, load it, then rewrite it protected. Never delete or regenerate on a failed unprotect:
   return the error (the current message already says "do not delete it").
5. Test: round trip `unprotect(protect(x)) == x`, and a raw-file migration test in a temp folder (`cargo test`).
- Limit: DPAPI user scope binds the key to this Windows user. A copy of the data folder to another PC or user
  cannot read the identity. That is the point, but backups of the data folder no longer move the node identity.
