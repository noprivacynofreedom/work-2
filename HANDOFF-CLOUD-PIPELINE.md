# Handoff: cloud pipeline for /swarm (written 2026-11-11)

Read CLAUDE.md first. Build on branch `fix/queue-in-chat-dragdrop` (GitHub head `9ec143b`, pushed by Jason).
Do NOT use branch `claude/sharp-thompson-t3q5zr` (an old, redundant patch). Do NOT push to Jason's app branch.
Push to your own `claude/...` branch built on top of `origin/fix/queue-in-chat-dragdrop`. Jason then runs
`python get_update.py <your branch>` in `F:\APP-DEV\projects\atlas-chat`. Never tell him to checkout, reset or pull.

All code is in `atlas-rust-desktop/src-tauri/resources/atlas/` (this is what the installer ships).

## What Jason wants (his words, tidied)
1. Gemini reads the goal, splits it, and tells each bot its ONE portion of the work.
2. Local bots each do their own portion (one at a time, one local model).
3. Gemini combines all portions into one result.
4. DeepSeek (through OpenRouter) reviews the combined result.
5. The swarm RUNS TESTS on any code, so the result is proven to work, not only read. The test runner
   already exists in `agents/atlas_coding_swarm.py` (`ALLOWED_COMMANDS`: python-unittest, python-pytest, node-test).
6. The final plan, combined result, review and test result post back into the chat where `/swarm` was typed.
7. Later (second job): a GUI switch in the Operations tab for cloud routing.

## What already exists (verified by reading GitHub, NOT run on the PC)
- `swarm_run.py`: `/swarm` runs one chat per bot, sequentially, on the local model. Each bot sees only the goal and
  its own job. Bots do NOT get each other's answers. No combine step. No review step.
- `cloud_llm.py` (commit `049048b`): per-bot cloud routing. Uses `urllib`, no litellm. Keys from env only:
  `GEMINI_API_KEY`, `OPENROUTER_API_KEY`. Switch off with `ATLAS_CLOUD_SWARM=0`. Default is ON when a key exists.
  `CLOUD_ROUTES` in `swarm_run.py` sends PM, CTO, Principal Architect to Gemini and QA, Senior Engineer to DeepSeek.
  This is a per-bot split, NOT the plan/combine/review pipeline above. Reuse `cloud_llm.call()`. Do not duplicate it.
- `agents/atlas_coding_swarm.py`: separate coding swarm with its own cloud routing (`ATLAS_CLOUD_ROUTING=1`, litellm).
  `/swarm` does not call it. Only `agents/atlas_coding_swarm_worker.py` does.
- `atlas_orchestrator.py` only queues "programming" tasks. It does not run bots.
- `index.html` already has `swarmWatch` and `swarmFinishCheck`. The finish summary shows counts only, not the answers.
- `server.py` `_handle_swarm_command` starts a run. `/api/ops/swarm/log` feeds the per-bot logs.
- `compute_peers.py` and `_compute_post` in `server.py` are the pattern for a settings panel (save to
  `settings.json` in `ATLAS_DATA_DIR`, JSON endpoints, key never returned to the UI).
- The chat UI is plain HTML and JavaScript in one `index.html`. There is no React in it.

## Findings from the last session
- Jason's installed app was OLD: it printed "SWARM BREAKDOWN ... Executing in parallel" (old code that starts nothing).
  The new `/swarm` code prints "SWARM STARTED". He must run `.\build-release.ps1` and the installer to see new code.
- His env has `GEMINI_API_KEY`, `OPENROUTER_API_KEY` set (setx) and litellm installed. No separate DeepSeek key is needed.
- Windows PowerShell: use `Invoke-RestMethod`, not `curl.exe`, for JSON tests.

## Plan for the new session
1. `git fetch origin`. Branch from `origin/fix/queue-in-chat-dragdrop`. Check `tauri.conf.json` exists.
2. Read `swarm_run.py`, `cloud_llm.py`, `test_swarm_cloud.py`, `_handle_swarm_command` in `server.py`.
3. Add stage 1 (Gemini plan: JSON list of {bot, portion}), stage 3 (Gemini combine), stage 4 (DeepSeek review).
   Pass each bot only its portion. Keep local fallback at every cloud step, and log the fallback in plain words.
4. Add stage 5 (run tests on generated code with the existing runner). Report pass or fail in plain words.
5. Post the final result to the origin chat in `index.html` (extend `swarmFinishCheck`).
6. Tests: add to `validation-tests/` using the stub-server hooks in `cloud_llm.py` (`ATLAS_GEMINI_URL`,
   `ATLAS_OPENROUTER_URL`). Run: `python -m unittest discover -s ../../../validation-tests -p "test_*.py"`
   from the `atlas` folder, then `python check-bundle.py`.
7. Push your branch. Tell Jason the checks first, then the numbered steps, then what is NOT tested on his PC.
8. Second job: Operations tab GUI for cloud routing. Teach Jason how to add it (he asked to learn). Follow the
   `compute_peers` pattern. Keys must stay out of GET responses and out of git.

## Standing rules
No emails. Nothing outside atlas-chat gets deleted. Keyboard access, visible focus, works at phone width.
Jason's data (chats, bots, library) is outside git. Never reset or overwrite it.
Reply style: first line one action, numbered steps, short common words, warnings first, say what is tested.
