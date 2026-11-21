# START HERE (updated 2026-11-18)

**The real app is the desktop app in `atlas-rust-desktop/`.** Read `CLAUDE.md` first: it holds the rules.
- **Hyperswarm & 3 Swarm Modes**: Fully integrated (`/hyperswarm <goal>`, `/swarm local <goal>`, `/swarm hyper <goal>`, `/swarm abliterated <goal>`).
- **Build**: `.\build-release.ps1` (Fast NSIS is default; produces release installer in 30–60s). For compressed distribution, use `.\build-release.ps1 -Compress`.
- **Hot Sync (2 seconds)**: `.\build-release.ps1 -HotSync -Launch` syncs backend and UI directly into the live install and starts Atlas Chat.
- **Shipped backend + chat UI**: `atlas-rust-desktop/src-tauri/resources/atlas/` (`server.py`, `swarm_run.py`, `cloud_llm.py`, `index.html`, etc.).
- **Tests**: `validation-tests/test_hyperswarm_modes.py` (4/4 OK), `test_swarm_pipeline.py` (20/20 OK), `test_swarm_cloud.py` (9/9 OK), `check-bundle.py` (OK).
- **Themes**: Optik Dark and DedSec Dark available in Settings alongside Classic.
- **Documentation**: See `README.md` (Quickstart), `docs/COMPONENTS-AND-FAQ.md` (complete component map, FAQ, memory notes), `docs/DEVLOG.md`.

## OPEN PROBLEM: book import does not work on the PC (reported by Jason 2026-11-10, cause NOT found)
State when this was written
- PC branch `claude/modest-hamilton-solq6v` holds the book import code (fast-forward merge of
  `claude/sharp-thompson-r1ndji`, commit cf08be1). `git status -sb` showed `[ahead 4]`, clean.
- Build 1 ran BEFORE the merge (old code) and its installer was started. Build 2 was started AFTER the merge.
  It is not confirmed that build 2 finished, or that its installer was run.
- Jason then reported "book import dont work". No error text, no screenshot, no step was given.
  The cloud session could not see the PC. Do not guess: get the facts below first.
- Cloud tests: 15 book tests OK, bundle check OK. No real book and no real model was ever tested.

Step 1: ask Jason these, one at a time
1. Did the second build end with "ATLAS RELEASE BUILD VERIFIED", and did you run its installer after that?
2. Where does it fail? (a) the file picker does not show .mobi/.epub, (b) import shows an error (copy the text
   under the import button), (c) import seems to hang, (d) import works but the bot cannot read the book.
3. Which file? Name, type, size, and where it was bought (Amazon books have DRM).

Step 2: checks on the PC (PowerShell, in F:\APP-DEV\projects\atlas-chat)
- Is the new code installed?  `Get-ChildItem "Atlas Chat" -Recurse -Filter books.py`  (no result = old install)
- Is an old server still on port 8090?  `Get-NetTCPConnection -LocalPort 8090 | Select OwningProcess` then
  `Get-Process -Id <that id> | Select Path`. An old server on 8090 has caused wrong-code problems before
  (see the note in check-bundle.py).
- Do the tests pass with the bundled Python?  In `atlas-rust-desktop\src-tauri\resources\atlas` run
  `.\runtime\python\python.exe -m unittest discover -s ..\..\..\validation-tests -p "test_book_import.py"`
- Server log: `logs\atlas-server.log` under the app data folder.

Suspects, most likely first (none confirmed)
1. The installed app is build 1 (old code), or an old server process still serves port 8090.
2. After an import the UI calls `/api/library/index-status`, which rebuilds the whole library index. With the default
   `embedding_model` (fastembed) a full book is hundreds of chunks. This can take minutes and look like a hang, or fail
   if fastembed is not installed in the bundled Python. Test: set `"embedding_model": ""` in settings.json and import again.
3. The book has DRM or Kindle HUFF/CDIC compression. The import then shows a message with "DRM" or "Calibre".
4. Case (d): the chapter tools reach the model only when an MCP server is online. Check the MCP status in the app.
5. A large file: the UI builds base64 in memory (`index.html`, `#knowledgeFiles` change handler). Not measured over 5 MB.
6. A real-world file breaks a reader in `books.py` (only built test books were tried). Get the file name and the error
   text. To test one file: `python -c "import books,sys;b=books.load(sys.argv[1],open(sys.argv[1],'rb').read());print(b['title'],len(b['chapters']))" <file>`

Where the code is (all in `atlas-rust-desktop/src-tauri/resources/atlas/`)
- `books.py` readers. `book_tools.py` model tools. `server.py`: `_extract_book`, `_library_books`,
  `/api/library/import`, `_proxy_mcp_tools`. `index.html`: `#knowledgeFiles`.
- Tests: `atlas-rust-desktop/validation-tests/test_book_import.py`.

## Book import (2026-11-10, built in the cloud; first PC try FAILED, see the section above)
Use it: Knowledge panel > + IMPORT SOURCES > pick a book.
- Formats: .epub .mobi .azw .azw3 .fb2 .rtf .odt and .pdf. Up to 100 MB per file (was 5 MB), 20 MB of text per book.
- The book text goes into the knowledge library like other sources, so matching passages are added to each chat.
- The chapter list is saved next to it (`<id>.chapters.json` in `.atlas\knowledge`).
- A model can read the book in parts with 3 tools: `list_books`, `read_chapter` (contents list, or one chapter in
  parts of 24,000 characters), `search_book` (5 best passages with chapter numbers).
  The tools show as tool server `atlas_library` in the chat tool loop.
- Files: `books.py` (readers, standard library only), `book_tools.py` (tools), `server.py` (import, limits),
  `index.html` (file picker). Tests: `atlas-rust-desktop/validation-tests/test_book_import.py` (15 tests OK in the cloud).

Limits, stated plainly
- The book tools reach the model only when at least one MCP server is online, because only then does chat go
  through the tool loop. With no MCP server online the model still gets library passages, but no chapter tools.
- Books imported before this change have no chapter list. Remove and import them again to get the tools.
- DRM books (most Amazon purchases) and Kindle HUFF/CDIC files cannot be read. The import says why.
- PDF and RTF have no chapter names: "Pages 1-12" or "Part 3".
- No real store-bought book was tested: the cloud cannot download samples. All test books are built by the tests.
- The JavaScript in the UI builds base64 in memory. A 100 MB file can be slow in the window. Not measured.

Not moved into the desktop app (they exist only on the old-app branch `claude/intelligent-bohr-9laqiq`)
- Data-loss guards (revision check, backup before removals), per-bot file tools with write confirmation,
  plain-language error boxes, .docx reading in folder search. Decide per item whether the desktop app needs it.

Open items
1. Jason: `python get_update.py claude/sharp-thompson-r1ndji`, build, install, import one real .epub and one real
   .mobi/.azw3, ask "what are the chapters" and "what happens in chapter 2". Note any error text here.
2. `main` on GitHub is still the old app. Move it to the desktop app branch so new sessions start in the right place
   (Jason's call): `git push origin claude/modest-hamilton-solq6v:main`
3. Fix `validation-tests/test_knowledge_library.py` (fails at import: its MCP stub has no `build_mcp_specs`).

---

# Atlas Chat + local models: handoff notes (updated 2026-11-06, 8:20am NZDT, overnight run)
# Atlas Chat + local models: handoff notes (updated 2026-11-10, cloud session)

Read this first. Update it as you work: what you changed, what worked, what failed.

## Layout
- Models: F:\models (qwen3.6-35b-a3b-abl, gemma4-31b-heretic, gemma4-26b-a4b-abl, qwen3-14b-abl, gpt-oss-20b-abl). All complete.
- llama.cpp Vulkan b12125: F:\app-dev\tools\llama-vulkan
- llama-swap v270: F:\app-dev\tools\llama-swap (config.yaml, port 8080). Backup of the old config: config.yaml.bak-20261106
  Model names: coder (alias agent), mentor (aliases guide, teach, mentor-moe), mentor-dense (old Gemma 31B), assist, tasks.
- Atlas Chat: F:\app-dev\projects\atlas-chat (git repo, branch main, never pushed)
  - app.py = native window (pywebview + WebView2). Starts llama-swap and server if ports are down. Reads paths/ports from settings.json.
  - server.py = serves index.html, saves bots/chats (/api/state) to %APPDATA%\AtlasChat\data.json with backups,
    POST /api/export writes a backup, /api/tool runs file tools, /api/folder checks a folder, /api/info gives paths,
    proxies /v1/* to 8080, adds document snippets when a request carries docs_folder.
  - filetools.py = list_files / read_file / write_file for models, locked to the bot's workspace folder.
  - settings.json = ports and paths. settings.local.json (not in git) overrides it on one PC.
    Missing file, bad JSON or wrong types fall back to defaults in server.py.
  - docsearch.py = keyword search over a bot's documents folder (top 3 snippets, text + .docx + .pdf). Test set: sample-docs\
  - install.ps1 was removed (2026-11-10). The Tauri NSIS installer is used.
  - tests\ = test_atlas.py (python -m unittest discover tests), mock_llama.py (fake model server), ui-test.js (browser test).
  - index.html = UI: bot cards, chats per bot, editor (Ctrl+E, now has Documents folder), streaming, Stop, Export/Import.
  - test-models.ps1 = smoke test. Run: & 'F:\app-dev\projects\atlas-chat\test-models.ps1' -Models coder,mentor,assist,tasks
  - Desktop shortcut "Atlas Chat" -> C:\Users\zezu1\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe app.py
- Hardware: RX 9070 XT 16 GB VRAM, 31 GB RAM. Desktop apps hold about 3.9 GB dedicated VRAM right now (was 1.5-2 GB).

## Test results (latest, 2026-11-06, test-models.ps1 through 8090)
| Model | Result | Speed | Settings |
|---|---|---|---|
| coder (Qwen3.6 35B-A3B Q4_K) | OK | 39.7-41.6 tok/s (was 5.3) | -ngl 99 --n-cpu-moe 28 --load-mode none |
| mentor (Gemma 4 26B-A4B abliterated i1-Q4_K_M) | OK, good advisor answer | 45-47.5 tok/s (old dense mentor 5.2) | -ngl 99 --n-cpu-moe 14 |
| assist (Qwen3 14B) | OK | 54.6 tok/s | unchanged (--fit-target 2048) |
| tasks (gpt-oss 20B) | OK | 111-115 tok/s (had dropped to 35) | -ngl 99 --n-cpu-moe 2, --fit-target removed |

Tuning runs:
- coder --n-cpu-moe: 20=11.3, 22=8.8, 24=37.5, 26=40.2, 28=41.6, 30=36.5 tok/s.
- mentor --n-cpu-moe: 8=17.7 (spills), 12=51.4, 14=47.5. 14 chosen for about 1 GB more VRAM headroom.
- tasks: --fit-target 2048 = 35, --n-cpu-moe 4 = 92.6, 2 = 111-115, 0 = 34 (0 acts like unset, fit runs).
- Mentor quality test (blunt advisor, NZ dropshipping question, 1317 tokens in 29.9 s): clear decision, reasons, risks, one next action.

## Done
- 2026-11-06 Coder re-tested and tuned: --n-cpu-moe 28, 41.6 tok/s. Config comment has the full table.
- 2026-11-06 Mentor moved to MoE: downloaded mradermacher/Huihui-gemma-4-26B-A4B-it-abliterated-i1-GGUF
  file Huihui-gemma-4-26B-A4B-it-abliterated.i1-Q4_K_M.gguf (16,796,011,968 bytes, sha256 0f9077c9c7b40f1b056b89a48422017717190618e3136d2d3c20c758e3603676, matches HF)
  into F:\models\gemma4-26b-a4b-abl. "mentor" now points at it (45-51 tok/s). Old file kept as "mentor-dense".
- 2026-11-06 tasks fixed: 35 -> 111-115 tok/s by replacing --fit-target with -ngl 99 --n-cpu-moe 2.
- 2026-11-06 git init + .gitignore (data.json, .webview/, *.tmp, __pycache__/, settings.local.json, exports/). Commit 9c871ae.
- 2026-11-06 settings.json read by app.py and server.py, safe defaults tested (bad JSON, wrong types, missing file). Commit 608f522.
- 2026-11-06 Export/Import buttons (real buttons, keyboard focus, status text). Export writes
  F:\app-dev\projects\atlas-chat\exports\atlas-backup-<time>.json. Import checks the file, asks, backs up current data first.
  Tested: bad JSON and wrong shape rejected with nothing changed, good file imported, focus returns to Import. Commit 945440d.
- 2026-11-06 Document search per bot: Documents folder field in the bot editor, top 3 snippets added to the system prompt,
  answer stats show "docs: file names". Tested with sample-docs: "How many days does shipping to Australia take?" -> "5-8 days",
  header X-Atlas-Sources ["shipping.md","refund-policy.md"]. A missing folder still answers normally. Commit e266240.
- After each change: assist test OK (54 tok/s) and http://127.0.0.1:8090 loaded with no console errors.

- 2026-11-06 16:40-17:10 (chat session):
  - Header MODEL picker: change the current bot's model from the chat header, shows [LOADED] / [MISSING].
  - Team run (header button): Agent planner writes a JSON plan and assigns steps to chosen bots, each step is worked,
    then Reviewer replies PASS or FIX (1-3 rounds), the final work is handed to the next step. Every stage streams live
    with status and thinking. Saved as a "TEAM:" chat. Reviewer bot is created on first run (model tasks).
    Checked with node --check and an element-id check. NOT yet run end to end in the window.
  - assist: --fit-target removed, -ngl 99 set. Same speed (53.8 tok/s), no longer depends on fit.
  - bench.ps1 + bench-results.md: llama-bench sweep. Coder without MTP: 24=39.1 tok/s best, 32 collapses to 4.7.
    Config keeps the overnight setting (28 + MTP = 41.6 through the server).
  - Wasted: started downloads of HauhauCS Gemma4-26B-A4B QAT Q4_K_M and coder i1-IQ3_XS before reading this file.
    Both stopped as partial files: F:\models\gemma4-26b-a4b-qat (13.8 GB) and F:\models\qwen3.6-35b-a3b-abl-iq3 (4 GB).
    Jason can delete both folders. Lesson: read HANDOFF.md before starting.

## What worked
- huggingface_hub snapshot_download for 2 files; curl.exe -fL -C - --retry 5 for the rest (gemma 26B: 16.8 GB in about 8 min).
- HF API from the PC (Invoke-RestMethod https://huggingface.co/api/models/<repo>/tree/main) for real file names, sizes, sha256.
- --load-mode none (new name for --no-mmap in this build).
- Setting -ngl 99 + --n-cpu-moe by hand. Speed is the reliable spill signal (big drop = VRAM spilled).
- pywebview native window. WebView2 runtime 156 is installed.

## What failed (do not repeat)
- huggingface_hub froze on qwen3-14b at 3.44 GB. Use curl.exe -fL -C - with --retry.
- curl without -f wrote a 0-byte file on a wrong file name (bartowski files start with "huihui-ai_").
- --no-mmap: removed in this llama.cpp build -> llama-server exits, llama-swap returns 500. Use --load-mode none.
- --fit (default on) + --fit-target: wrong both ways on Vulkan/Windows. It over-filled VRAM before, and now (desktop apps
  using 3.9 GB) it under-filled and cut tasks to 35 tok/s. Set -ngl / --n-cpu-moe by hand. --n-cpu-moe 0 counts as unset.
- "Shared GPU memory under 0.3 GB" is not a usable target: the Windows counter also counts the CPU-side expert weights
  (llama-server shows 6-13 GB shared even at the fastest settings). Judge by tok/s and dedicated usage instead.
- test-models.ps1 max_tokens 600: thinking models (coder, mentor) sometimes use all 600 on reasoning, so the answer column
  is empty. Speed is still valid. Use a longer max_tokens to read answers.
- curl / Python requests from the cloud sandbox to huggingface.co are blocked. Query HF from the PC.
- Edge and Chrome are not installed. Launch via pywebview (app.py).
- C:\Users\zezu1\AppData\Local\Microsoft\WindowsApps\pythonw.exe is a Store stub without pywebview. Use the pythoncore-3.14-64 path.
- PowerShell -File with a [string[]] param only takes the first value. Use & 'script.ps1' -Models a,b,c.
- PowerShell -replace on config.yaml silently missed once. Use Desktop Commander edit_block for config edits.
- app.py takes about 6-10 s to open its window (pywebview import). Wait before checking port 8090.

## 2026-11-10 cloud session (branch claude/intelligent-bohr-9laqiq, pushed to GitHub on Jason's request)
Checked with: python -m unittest discover tests (30 tests OK) and tests/ui-test.js in Chromium against
tests/mock_llama.py (31 checks OK). NOT run on the Windows PC and NOT run against the real models yet.

Lost chats / lost Zeus bot: causes found and fixed
- The UI saved the default bots over data.json whenever /api/state failed to load once. Fixed: a failed load never saves.
- A second or old window saved its old copy over newer data. Fixed: each save carries a revision number, the server
  answers 409 to a stale window and the window shows "Reload".
- data.json lived in the app folder, so a fresh clone or a new build started empty. Fixed: data is now in
  %APPDATA%\AtlasChat\data.json (setting "data_dir"). First start copies the old app-folder data.json there.
- Backups: %APPDATA%\AtlasChat\backups. "removed-*" = made before any save that removes a bot, chat or message
  (never auto-deleted). "auto-*" = every 10 minutes while in use (newest 40 kept). "damaged-*" = unreadable file kept.
- To look for Zeus on the PC: F:\app-dev\projects\atlas-chat\exports\*.json and data.json.tmp, then Import the file.
  Nothing from before this change can be recovered from the cloud.

New
- File tools for models (filetools.py): list_files, read_file, write_file inside the bot's Workspace folder only.
  Edit bot > Workspace folder + File access (Off / Read only / Read and write, ask / Read and write, do not ask).
  Old file versions go to <workspace>\.atlas-backups. Bad tool calls return a plain ERROR text that names the fix,
  the model then retries. Models without native tool support switch to a text <tool_call> format on their own.
- Errors: plain title + "What to do" + technical details (folded). Saved with the chat. Red bar at the top for load/save problems.
- Vague questions: BASE_PROMPT in index.html is added in front of every bot's system prompt.
- Document search reads .docx and .pdf (pypdf if installed: pip install pypdf. Without it only simple PDFs work).
- settings.local.json now really overrides settings.json (it was in .gitignore but never read).
- Server only answers pages from this PC (Host/Origin check). Wrong state JSON is refused.
- Team run tested end to end with the fake model server. Stage titles now stay after a reload.
- Fixed: Stop on Windows (ConnectionAbortedError), partial answer lost on Stop, two same-role messages in a row
  (Gemma template error), numbered lists shown as bullets, keyboard focus lost every 5 s, Ctrl+E crash with a dialog open,
  switching chats while an answer streams, chunk order in docsearch, Attach is now a real button.
- bench-results.md converted to UTF-8. bench.ps1 now writes UTF-8. test-models.ps1 max_tokens 2000.

## Open items, in priority order
1. Jason: on the PC run  git pull, then  python -m unittest discover tests,  then open the app and check that
   "Data: C:\Users\zezu1\AppData\Roaming\AtlasChat\data.json" shows at the bottom left with all bots and chats.
2. Test file tools with the real models: Edit bot (Coder) > Workspace folder > Read only > ask "what is in this folder".
   llama-server needs --jinja for native tool calls. Without it the app uses the text format (slower, less reliable).
3. Book import: DONE (commit f00ff52): .epub .mobi .azw3 .fb2 .rtf .odt and big PDFs read in parts.
   Plan: add readers to docsearch._read_text (epub = zip of xhtml, standard library), strip markup, split into chunks,
   store chunks as JSON next to the data file, and give the model a search_book / read_chapter tool in filetools.py.
   A whole book does not fit in model memory, so the model must read it in parts ("truncate" = cut to the part that fits).
4. bench.ps1, launch.ps1, test-models.ps1 still hold F:\ paths. PowerShell changes here were not run (no PowerShell in the cloud).
5. Installer: Tauri NSIS (build-release.ps1). See "Release" below.
6. Jason: try mentor in the app on a few real advisor/teacher questions. If you prefer the old one, set the bots to "mentor-dense".
7. Scanned PDFs (images) have no text. They need OCR, not planned.

## Release: how to get a client install ready
install.ps1 was removed on 2026-11-10 (old Python and pywebview installer). The Tauri NSIS installer replaces it.
The installer already carries Python, llama-swap and llama.cpp (resources\atlas\runtime). The app finds them relative to its own folder.
Do the steps in order. Each one has a check.

1. On Jason's PC: .\BUILD-ATLAS.ps1, then .\build-release.ps1. Check: no FAIL, installer in target\release\bundle\nsis.
2. Real models test (15 minutes): open the app, send one message to each bot, run one Team run, and do the file tools test.
   Check: no red error box. If one shows, copy its TECHNICAL DETAILS into this file.
3. Decide the client model set (Jason). Rule: normal (non-abliterated) models only. Pick by client VRAM:
   8 GB, 12 GB, 16 GB tiers. Write the Hugging Face repo, file name, size and sha256 for each here.
4. runtime\llama-swap\config.yaml still points at F:\models\... (Jason's models). Make it find models by folder, not by fixed path.
5. On a clean Windows VM or the laptop: run the installer, copy the models, open the app.
   Check: badge shows SWAP ON, 4 bots answer.
6. Smoke test: .\test-models.ps1 -Models coder,mentor,assist,tasks   Check: 4 lines with OK.
7. Tag the release in git (for example v0.1.0) after steps 1, 2 and 5 pass.

Dependencies
- Windows 10 or 11, 64-bit. WebView2 runtime (part of Windows 11).
- Python, llama-swap and llama.cpp are bundled in the installer. Model files are NOT bundled (too big).
- Tests only: Node + Playwright for tests\ui-test.js (developer PC, not the client).

Known gaps before a paid client install
- No uninstaller. To remove: delete the shortcut, the atlas folder and %APPDATA%\AtlasChat (holds the client's chats).
- No auto update. An update = run the new installer. Data is kept.
- The installer is not code signed.
- Check the licence of each client model and of llama.cpp / llama-swap before a sale (all permit bundling as of last check: verify).
- Book import (open item 3) is not built.

## Docs (Claude Docs artifacts)
- Local Models Playbook: https://claude.ai/artifact/XuQtr2neFifyMmwtsg6CSH
- Local AI Business Plan: https://claude.ai/artifact/Msnhk9hogbg2tVgfjFWDJB (offer, deployment, training, leads, proposal)
- Gmail drafts (to Jason only, not sent): 3 proposal emails, law / accounting / physio.

## Rules
- Never send emails, never push to GitHub, never delete files outside atlas-chat without Jason.
- Client installs use normal (non-abliterated) models only.
- Accessibility: keyboard access, visible focus, reduced motion, works at phone width.
