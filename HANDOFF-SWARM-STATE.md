# Handoff: swarm state badges, state bar, chat tabs (2026-11-11)

Branch: `claude/magical-volta-j7ozkm`. It is `jason-app-morning` (Jason's local `fix/queue-in-chat-dragdrop`,
pushed 2026-11-12, tip `725bb34`) plus the swarm state commits. It replaces `claude/funny-wright-1vuclq`, which was
built on an older base and is refused by `get_update.py`.
Update command (Jason's PC): `python get_update.py claude/magical-volta-j7ozkm`, then `.\build-release.ps1`.
Rebase note: `swarm_run.py` `_pipeline` had a conflict with the base's "one bot, no plan call" change. Both are kept:
`_phase(final, "plan")` runs first, then the one-bot shortcut.

## Tested / not tested
- Tested in the cloud after the rebase: backend tests (102 OK), `check-bundle.py` (passed),
  `test_swarm_lead_log.js`, `test_swarm_chats_atomic.js`, `test_swarm_result_delivery.js` (pass).
- `test_swarm_lead_log.js` stub got a `renderChats()` and a phase check (the new phase line calls `renderChats`).
- Fail on the base too, so not from this change: repo-root `tests` (1 failure `test_mcp_hardening` leading-whitespace swarm,
  1 error `test_model_discovery` shipped config), and `test_atomic_chats.js`, `test_chat_queue.js`, `test_conversation_bridge.js`.
- Earlier browser check of badges, bar and tabs was on the old base. Not repeated after the rebase.
- NOT tested: the installed app on Jason's PC, a real `/swarm` run with live models.
- `validation-tests/test_ui_safety_contracts.js` does not run here (missing `atlas-rust-desktop/src/App.tsx`). Not looked into.
- A page error "Invalid or unexpected token" shows in the browser check with stubbed requests. It is on the base branch too.

## What changed (all in `atlas-rust-desktop/src-tauri/resources/atlas/`)
- `index.html`
  - Chat list tabs: `CHATS | SWARM | LIBRARY` (`chatTab`, `setChatTab`). SWARM lists all swarm chats of every bot.
    LIBRARY is the old `#knowledgeBtn`. `/swarm` opens the SWARM tab (`startSwarmChats`).
  - `swarmBadge(c)`: badge on each swarm chat, same style as the model badge.
    Bot: QUEUED, RUNNING, DONE, FAILED, STOPPED. Lead: PLANNING, BOTS WORKING, COMBINING, TESTING, REVIEWING, DONE, FAILED, STOPPED.
  - `renderSwarmBar()`: state bar above the open swarm chat (`#swarmBar`) with steps and marks.
  - `swarmWatch` stores `swarmTaskStatus` and `swarmPhase` from the log poll.
- `swarm_run.py`: `_phase()` records the Lead's step (plan, bots, combine, tests, review) as a `swarm.phase` event.
- `atlas_observability.py`: `swarm_log()` returns `phase` and hides `swarm.phase` from the chat lines.
- `validation-tests/test_swarm_phase.py`: new test.

## Known gaps
- The Lead badge says DONE even when its tests failed. The result holds `tests.status`; the badge does not read it.
- Bot DONE/FAILED comes from the task status only.

## Open question (Jason asked, not built)
Make `/swarm` write real project files instead of one `.md` per bot.
Now: one `.md` per bot and one combined `.md`, in `<Workspace>\swarm-output\<run id>\`.
Real files only come from `FILE: path` + code blocks in the Lead's combined text (cloud pipeline only), into a temp
`swarm-runs\<run id>` folder, only for tests. `agents/atlas_coding_swarm_worker.py` writes to `swarm-workspaces`, but `/swarm` does not call it.
Plan: write `FILE:` blocks to `swarm-output\<run id>\project\` (same path checks), ask the bots for `FILE:` blocks, list the files in the Lead chat.
Need from Jason: which file holds his `workspaces` and `conf` settings, and the target folder.
