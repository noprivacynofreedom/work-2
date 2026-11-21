# Handoff: image input (vision) in the desktop app

Branch: `claude/relaxed-bell-9ycsfi` (2 commits on top of `jason-app-morning`, fast-forwardable).
Written 2026-11-18. This file describes only this branch. Other swarm work is in `HANDOFF.md`.

## Status
Code is pushed. Cloud tests pass. **Not tested on Jason's PC**: no real vision model, no build, no real image sent.

## What was wrong
1. `model_discovery.py` skipped every `mmproj` file and never passed `--mmproj` to llama-server. Vision never loaded.
2. Big photos went to the model at full size and could fill the context.
3. Bots started as "IMAGE ?" and always asked before sending an image.
4. Only the newest message carried its images. Follow-up questions lost the picture.

## What changed (all under `atlas-rust-desktop/src-tauri/resources/atlas/`)
- `model_discovery.py`: `find_mmproj()` matches a projector by name, or the only model+projector pair in a folder. `build_config()` adds `--mmproj`.
- `vision_probe.py` (new) and `server.py`: `GET /api/vision?model=X` reads `modalities.vision` from `/upstream/<model>/props` (llama-swap). Returns `true`, `false` or `null`.
- `index.html`:
  - `prepareImage()` shrinks images over 1568 px or 1.5 MB to JPEG.
  - Paste an image with Ctrl+V.
  - First image send on an "Unknown" bot calls `/api/vision` and sets the bot to vision or text-only. `null` falls back to the old confirm prompt.
  - Messages keep `images`. Only the 3 newest image messages keep pictures. A text-only bot never gets old images.
- Tests: `tests/test_model_discovery.py` (3 new), `tests/test_vision_probe.py` (new).

## Known failures that are not from this work
- `tests/test_model_discovery.py::test_shipped_config_has_no_fixed_model_paths` (shipped `config.yaml` missing in the cloud checkout).
- `tests/test_mcp_hardening.py::test_swarm_command_with_leading_whitespace_keeps_the_whole_goal` (fails on `jason-app-morning` too).
- `validation-tests/test_ui_safety_contracts.js` fails on file paths in the cloud. Not run.

## Open items
1. Run it on the PC (steps below). Nothing here proves it works with a real model.
2. The bundled `runtime/llama-swap/config.yaml` may need its own `--mmproj` line per vision model. Not checked.
3. `/api/vision` loads the model on the first check. This can take a while. No spinner beyond the status text.
4. Pictures are saved inside `data.json` (3 messages per chat). Watch the file size.
5. If `/props` has no `modalities` (old llama.cpp build), detection returns unknown and the user sees the confirm prompt.

## Steps for Jason
1. In `F:\APP-DEV\projects\atlas-chat`, run `python get_update.py claude/relaxed-bell-9ycsfi`.
2. Put the `mmproj-*.gguf` file in the same folder as the vision model.
3. Run `.\build-release.ps1`, install, start "Atlas Chat" from the Start menu.
4. Send a screenshot to a vision bot (IMAGE INPUT on "Unknown"). Ask a second question about the same image.

## Rules for the next session
- Read `CLAUDE.md` first. Build on this branch or on `jason-app-morning`. Never on `main`.
- Do not edit `HANDOFF.md` from here. Add notes to this file instead.
- Do not tell Jason to run `git checkout`, `git switch`, `git reset` or `git pull`.
