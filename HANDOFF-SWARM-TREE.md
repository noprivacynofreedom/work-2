# Handoff: swarm folder tree, live bot chips, Lead test state (2026-11-12)

Branch: `claude/optimistic-dijkstra-yyrk7u`. It is `claude/funny-fermi-qpy08t` plus 1 commit.
Update command (Jason's PC): `python get_update.py claude/optimistic-dijkstra-yyrk7u`, then `.\build-release.ps1`.

## Tested / not tested
- Tested in the cloud: backend tests (117 OK), `check-bundle.py`, swarm JS tests, new `test_swarm_tree.js`,
  a Chromium render of the SWARM tab and state bar with a fake run (desktop and phone width, no page errors).
- NOT tested: the installed app on Jason's PC, a real `/swarm` run with live models.
- Fails on the base branch too (not this change): `test_atomic_chats.js` (uses `require` in an ES module),
  `test_conversation_bridge.js` (needs `src/App.tsx`).

## What changed (`atlas-rust-desktop/src-tauri/resources/atlas/index.html`)
- SWARM tab is a tree: one row per run, the Swarm Lead is the parent. Arrow (or Right/Left key) shows or hides the bot chats.
  Open state is saved on the Lead chat (`swarmOpen`). x on the parent deletes the whole run after a confirm.
- Chat rows use a state chip instead of the `[SWARM] Who:` text: `● SWARM LEAD`, `✓ SDE`, `✕ CTO`, then the goal or the bot's task.
  Old chats get role and goal from their title. New chats store `swarmRole`, `swarmGoal`, `swarmTask`.
- State bar: after the Lead steps it shows `BOTS n/m` and one live chip per bot. A click opens that bot's chat.
  A bot chat shows a chip for its Lead.
- Known gap fixed: the Lead reads `tests.status` from its saved result (`swarmLeadTests`). Failed tests show
  `DONE, TESTS FAILED` and a red TESTS step.
