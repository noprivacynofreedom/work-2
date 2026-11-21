# Handoff: Rust and installer changes (2026-11-10)

Nothing here was compiled or built. WSL has no Rust, no NSIS and no PowerShell. Build and test on the PC.
Repo: F:\APP-DEV\projects\atlas-chat, branch main. Read HANDOFF-NEXT.md for the rest of the open work.

## What changed (commits fb8b8919, 0f890035, a911d1ef)
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

## Build and check (in order)
1. `cargo check` in `atlas-rust-desktop\src-tauri`. Fix any compile error in the two Rust edits first.
2. `.\BUILD-ATLAS.ps1` (also runs the 3 node tests that WSL could not run).
3. `.\build-release.ps1`. Check: installer in `target\release\bundle\nsis`. Check the build log for "makensis" errors in `f-drive-only.nsh` (labels `has_f`, `no_f`, `done`, `ok`, `atlas_pre_ok`).
4. Run the installer. Check: folder page shows `F:\APP-DEV\projects\atlas-chat\app`. A `C:\` path keeps Next disabled. Nothing new in `%APPDATA%\dev.atlas.chat` or `%LOCALAPPDATA%\dev.atlas.chat`.
5. Launch. Check: badge shows SWAP ON, 4 bots answer. Open `F:\APP-DEV\data\Atlas Chat\app\llama-swap.generated.yaml`: no `{models}` left, `-m` paths point at `F:/models/...`.
6. Fallback test: rename `F:\models` to `F:\models-off`. Copy one `.gguf` to `F:\APP-DEV\data\Atlas Chat\app\models`. Launch. Check: all 4 bots answer with that model (mode `generated`). Rename back.
7. Space test: put a model in a folder with a space and set `ATLAS_MODELS_DIR` to it. Check: llama-swap starts it (see `logs\llama-swap.log`).
8. No-F: test: a clean VM or the laptop with no F: drive. Check: installs to `%LOCALAPPDATA%\atlas-chat\app`, data in `%LOCALAPPDATA%\atlas-chat\data`, app starts.

## Known risks
- Rust and NSIS edits are untested. NSIS label jumps are the likeliest build error.
- llama-swap with a quoted `-m "path with space"` is unconfirmed. Paths use forward slashes and `llama-server.exe` is relative, so only the model path can have a space.
- An old install at `...\atlas-chat\Atlas Chat` is kept by an upgrade (registry path starts with F:). Uninstall it, install fresh, then Jason deletes the old folder. Do not delete it without Jason.
- No models found: mode `none`. llama-swap reports a missing `{models}/...` file. Better message not written.
- Generated config uses `-ngl 99 -c 16384 -fa on -np 1 --jinja`. No `--n-cpu-moe`. Large MoE models on small GPUs may need tuning.
- Native tool calls need `--jinja` (included). Not tested with a real model.
- `F:\APP-DEV\data\Atlas Chat` still has capitals and a space. It is the old data path. Changing it needs a data move (HANDOFF-NEXT item 13).
