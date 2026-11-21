# Atlas Chat: rules for every Claude session

Read this before any work. It exists because of a real mistake (2026-11-10, see the end).

## 1. Which app is the real one
- The real app is the **desktop app**: `atlas-rust-desktop/` (Tauri + Rust shell, React frame).
- The backend and chat UI that **ship in the installer** are in
  `atlas-rust-desktop/src-tauri/resources/atlas/` (`server.py`, `index.html`, `books.py`, ...).
  **Change these files.** The files with the same names in the repo root are older copies.
- Jason builds with `.\build-release.ps1`, then runs the installer that the build prints.
  He starts the app from the Start menu ("Atlas Chat"). He does NOT start it with `python app.py`.
- A branch that has no `atlas-rust-desktop/src-tauri/tauri.conf.json` is an OLD version of Atlas.
  Never build on one. Never send Jason to one.
- 2026-11-18: `main` was moved up to the desktop app (= `fix/queue-in-chat-dragdrop` at 7a95895c).
  The 29 old remote branches were deleted. Only `main` and `fix/queue-in-chat-dragdrop` stay on GitHub.

## 2. Before you write any code
1. `git fetch origin`, then list branches by date:
   `git for-each-ref --sort=-committerdate --format="%(committerdate:short) %(refname:short)" refs/remotes`
2. Find the newest branch that holds the desktop app. Build on that one.
   If Jason names another branch or file, check it against step 1 and tell him when it is older.
3. A `HANDOFF.md` only describes its own branch. Old branches hold old handoffs. Check the date and the branch.
4. If you are unsure which branch Jason runs, ask him for the output of `git status -sb`. Ask first.

## 3. How to give Jason your work
- Build on top of his app branch, so that his branch can fast-forward to yours.
- Then he runs ONE command in `F:\APP-DEV\projects\atlas-chat`:
  `python get_update.py <your branch>`
  It checks first, refuses old branches, never switches branch, and prints the next steps.
- **Never tell Jason to run `git checkout <branch>`, `git switch`, `git reset` or `git pull` on another branch.**
- **Always commit and push to Jason's app branch before telling him to delete or close the chat.** Confirm with `git status` that all commits are pushed.
- Never push to `main` without his clear yes.

## 4. How to write to Jason
- Checks and warnings come FIRST, before the steps. Never after.
- First line: one action. Numbered steps. One action per step. Short common words.
- Say plainly what is tested and what is not. "Tests pass in the cloud" is not "works on the PC".
- Do not say "you are missing nothing" unless you compared his branch with every remote branch.

## 5. Tests
- Backend (run in `atlas-rust-desktop/src-tauri/resources/atlas`):
  `python -m unittest discover -s ../../../validation-tests -p "test_*.py"`
- Repo root: `python -m unittest discover tests`
- Bundle check (also run by the build): `python check-bundle.py`
- Known before 2026-11-10: `validation-tests/test_knowledge_library.py` fails at import (stale stub),
  and `tests/test_conversation_api.py` has 1 error in the cloud. Both pass as of 2026-11-18.
  If one fails again, say so. Do not hide it.
- A test that runs a fake MCP tool through the tool loop must give the tool a tier
  (`patch.dict(mcp_chat.TOOL_TIERS, {"<tool>": "read"})`, or `ATLAS_WRITE_APPROVAL=auto` for write tools).
  Without it the approval gate waits 600 s for a click and the test hangs. Example: `tests/test_mcp_chat.py`.

## 6. Standing rules (from HANDOFF.md)
- Never send emails. Never delete files outside atlas-chat. Client installs use normal (non-abliterated) models.
- Accessibility: keyboard access, visible focus, reduced motion, works at phone width.
- Jason's data (chats, bots, library) lives outside git. Never reset or overwrite it.

## 7. Install folders on Jason's PC (checked 2026-11-11)
- **Live install:** `F:\APP-DEV\projects\atlas-chat\app`. The Start menu shortcut "Atlas Chat" points to `app\atlas-desktop.exe`.
  Updates keep it: the installer reads the old folder from the registry (`nsis/install-dir.nsh`).
  A new install on any PC defaults to `%LOCALAPPDATA%\atlas-chat\app` (since 2026-11-18, no F: rule in public code).
- **Old install (before 2026-11-10):** `F:\APP-DEV\projects\atlas-chat\Atlas Chat`. Do not use it. Do not edit it.
  Jason renames it to `Atlas Chat.old` and deletes it later. Never tell him to run its `uninstall.exe`:
  both installs share one app ID, so it may remove the shortcut and registry entry of the live install.
- The install folder is a **copy** of `src-tauri/resources/atlas` plus `atlas-desktop.exe`. Never edit files inside it.
  The build overwrites it. Edit the source in `atlas-rust-desktop/`.
- Data is outside the install: `F:\APP-DEV\data\Atlas Chat`. Jason's builds get this folder from `local-build.json`
  (private, on the core list) through build-release.ps1 and `option_env!("ATLAS_BUILD_DATA_ROOT")` in main.rs.
  The app uses it only when the folder exists. Otherwise: `%LOCALAPPDATA%\atlas-chat\data`. Never delete `local-build.json`:
  without it, Jason's next build opens an empty app (his data is still safe on F:). Folders `data`, `bots`, `exports`, `logs`, `runtime`,
  `swarm-workspaces`, `swpr`, `swr-user testing`, `vnc-workspace` in the project folder are Jason's work. Never delete them.
- Safe to delete (the build recreates them): `atlas-rust-desktop/node_modules`, `dist`, `src-tauri/target`, `__pycache__`.

## What went wrong on 2026-11-10
Jason pointed a cloud session at `HANDOFF.md` on `claude/intelligent-bohr-9laqiq`. That branch came from the old
Python app. The session built book import there without looking at the other branches, then told Jason to
`git checkout` its branch and said he was missing nothing. His project folder switched to the old app.
`git checkout -` put it back. Book import was then rebuilt inside the desktop app. Sections 1-4 prevent a repeat.

## 8. The chat page must never scroll (fixed in the cloud 2026-11-18, not checked on the PC)
- Only `#log` (the message list) and side panels scroll. The window and the page (`index.html` in the iframe) never scroll.
- Rules that keep it so: `.app{height:100%}` grid (never 100vh), `main{min-height:0}` flex column, and every flex box between
  `main` and `#log` (`#chatStage`) has `flex:1;min-height:0`. A new block above or below `#log` gets `flex:none`
  and a `max-height` with its own `overflow:auto`. Never put a tall block in `main` without that.
- The outer Tauri frame (`atlas-rust-desktop/src/style.css`, commit 2bf92ad) pins html/body/#root to 100% with overflow hidden.
- Check after every layout change, at 1400x900 with a long chat, the swarm bar and an approval card open:
  `document.scrollingElement.scrollHeight === document.scrollingElement.clientHeight` must be true.
- Fixed 2026-11-18 (branch claude/blissful-lovelace-1ejwjb). Cause: `.app{height:100vh}` in `index.html`. Under Windows
  display scaling (125%, 150%) 100vh rounds past the WebView window, and the new approval card (`#approvals`, approval
  gate commit 81a4b69) made it worse by adding a tall block above `#log`. Fix: `html,body{overflow:hidden}`,
  `.app{height:100%;grid-template-rows:minmax(0,1fr);overflow:hidden}`, `main{overflow:hidden}`,
  `#approvals{flex:none;max-height:35vh;overflow:auto}`. Guarded by `validation-tests/test_page_never_scrolls.py`.
- Browser check: `node atlas-rust-desktop/validation-tests/e2e_page_never_scrolls.mjs` (long chat, swarm bar,
  approval cards, 3 sizes). The old CSS fails it at phone width (input box 45 px below the window). The new CSS passes.
- The cloud browser does not show this rounding. Test at deviceScaleFactor 1.25 and 1.5, and still say "not tested on the PC".
