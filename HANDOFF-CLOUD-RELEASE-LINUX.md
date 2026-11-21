# Handoff: Laptop setup, public release, redaction, and Linux build in the cloud

Written 2026-11-18. Branch: `fix/queue-in-chat-dragdrop` (commit `94ac4f52`). Read `CLAUDE.md` first.
Target environment: Cloud Linux container or Windows runner.

## Warnings: read first
- Never commit or bundle `data.json` (user chat history) or personal model files.
- The real app is in `atlas-rust-desktop/`. Shipped backend is in `atlas-rust-desktop/src-tauri/resources/atlas/`.
- Never tell the user to run `git checkout`, `git switch`, or `git reset` on their PC.
- Check `tests/test_privacy_audit.py` before any release build or export.

## Status of existing chats and branch
- Local branch `fix/queue-in-chat-dragdrop` matches `origin/fix/queue-in-chat-dragdrop` at commit `94ac4f52`.
- `tests/test_privacy_audit.py` is updated to allow loopback test fixtures from `test_browser_mcp.py` and passes (4/4 tests OK).
- Scripts `setup-linux.sh` and `build-linux.sh` exist in the repo root for Linux environments.

## Cloud task list

### Task 1: verify privacy audit and path redaction (10 minutes)
1. Run `python -m unittest tests/test_privacy_audit.py`.
2. Confirm no personal paths (`F:\APP-DEV`, `zezu1`, `jason`) exist in public-tracked files.
3. Inspect `atlas-rust-desktop/src-tauri/resources/atlas/runtime/llama-swap/config.yaml`.
   Make sure it uses generic model paths or relative model placeholders.

### Task 2: clarify compute sharing and network terms (5 minutes)
1. Atlas Chat does not use the Node.js `hyperswarm` DHT package.
2. Atlas Chat uses `compute_peers.py` for LAN compute sharing over standard HTTP on port 8080.
3. For laptop-to-PC sharing, the laptop points to the PC IP (e.g. `http://192.168.1.50:8080`) in settings.

### Task 3: Linux build and compatibility verification (20 minutes)
1. In a Linux cloud runner, run `./setup-linux.sh --check` to verify dependencies.
2. Install required packages (WebKitGTK, libsoup, build-essential, curl, rust, nodejs).
3. Run `python3 check-bundle.py`.
4. Run `./build-linux.sh` to produce a Linux AppImage or `.deb` package.
5. Run backend validation tests:
   `cd atlas-rust-desktop/src-tauri/resources/atlas`
   `python3 -m unittest discover -s ../../../validation-tests -p "test_*.py"`

### Task 4: Windows public installer hygiene check (10 minutes)
1. Ensure `target/release/atlas/data.json` is not present before running NSIS.
2. Confirm `nsis/f-drive-only.nsh` falls back safely to `%LOCALAPPDATA%\atlas-chat\app` on PCs without an F: drive.
3. Test that installer runs and launches on a clean machine without F: drive.
