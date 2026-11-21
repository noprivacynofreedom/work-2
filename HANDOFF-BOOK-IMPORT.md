# Handoff: book import "fails, it is not JSON" (written 2026-11-10 by the cloud session on claude/sharp-thompson-r1ndji)

Read `CLAUDE.md` first. One line in it is now WRONG: it says `main` is the old app.
`main` is now the real desktop app (someone moved it on 2026-11-10). Correct that line.

## What Jason reported
"book import dont work", "it wont convert files to json for model to parse", "its failing on its not json", "it wont import".
He gave no screenshot and did not say which button he used.

## Most likely cause (NOT confirmed with Jason)
The app has two import controls. The words "is not valid JSON" belong to the wrong one for books.
- Sidebar button **Import** = restore a backup of bots and chats. It takes .json only. For any other file it shows:
  `<file name> is not valid JSON. Nothing changed.`
  Code: `atlas-rust-desktop/src-tauri/resources/atlas/index.html`, `$("#importFile").onchange`.
- Book import = sidebar **KNOWLEDGE // LIBRARY** > **+ IMPORT SOURCES** (`#knowledgeFiles`).
- The chat attach button and drag-and-drop on the chat box do not take books either (`#attach` accept list).
Evidence: that exact message exists only on the backup button. The 15 book tests pass on `origin/main` (d1452f6)
through the real HTTP endpoint `/api/library/import`.

## First thing to do
Ask Jason one question: "Which button did you click, and what are the exact words on screen?"
Then have him try: KNOWLEDGE // LIBRARY > + IMPORT SOURCES > pick the book.

## If that is the cause: make the app stop this mistake (not done yet)
1. Sidebar Import: when the file is a book or PDF, do not say "not valid JSON". Send it to the library import,
   or say "This button restores a backup. To add a book use KNOWLEDGE // LIBRARY > + IMPORT SOURCES."
2. Rename the sidebar button to "Restore backup".
3. Chat attach and drop: accept book files and send them to the library import, then tell the user.
4. Add a check to `atlas-rust-desktop/validation-tests/test_ui_safety_contracts.js` (or the nearest UI test).

## If it is NOT the cause
Use the suspect list and check commands in `HANDOFF.md`, section "OPEN PROBLEM: book import does not work on the PC".
Quick checks on the PC:
- New code running?  `(Invoke-WebRequest http://127.0.0.1:8090/ -UseBasicParsing).Content -match 'azw3'`  (True = yes)
- One real file, no app (run in `atlas-rust-desktop\src-tauri\resources\atlas`):
  `python -c "import books,sys; b=books.load(sys.argv[1], open(sys.argv[1],'rb').read()); print(b['title'], len(b['chapters']))" "<book file>"`

## State of the PC (from Jason's last output)
- Branch `main`, 1 commit ahead of `origin/main` (7f38a424 "Add Jason's pending edits ..."). Not pushed.
- 43 tracked files show as deleted in the working folder and are NOT committed (old zips, .bak files, old install scripts,
  `release/`, `resources/atlas/src/*`, and `mcp_agent.py` in the root and in the shipped backend). The cloud session did
  not delete them and does not know who did. Do not commit them blindly: `dev_cycle.py` lists `mcp_agent.py`.
  `git restore .` brings all of them back. Ask Jason first.
- Untracked: `atlas-rust-desktop/src-tauri/resources/atlas/.atlas/` = app data. Keep it out of git (add to .gitignore).
- It is not known which build is installed. Two builds ran on 2026-11-10; the first held code from before book import.
- `main` already holds the book import code (commit cf08be1 is in it). `python get_update.py claude/sharp-thompson-r1ndji`
  is NOT needed any more.

## Known weak points in the cloud session's own work
- `get_update.py` says "commit them first" for any change. For deleted files that advice is unsafe. Make it list
  deletions apart and say "check these on purpose" first. Its commit example needs quotes in PowerShell: `-m "my changes"`.
- No real store-bought book and no real model was ever tested. Only test books built by the tests.
- Book tools (`list_books`, `read_chapter`, `search_book`) reach the model only when an MCP server is online.
- After an import the app rebuilds the whole library index. With the fastembed model a full book may take minutes.

## Where the code is
`atlas-rust-desktop/src-tauri/resources/atlas/`: `books.py` (readers), `book_tools.py` (model tools),
`server.py` (`_extract_book`, `/api/library/import`, `_proxy_mcp_tools`), `index.html` (`#knowledgeFiles`).
Tests: `atlas-rust-desktop/validation-tests/test_book_import.py`.
