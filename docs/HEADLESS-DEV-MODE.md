# Headless development mode ("Night dev")

Status: built 2026-11-18 on branch `claude/headless-dev-mode`. Tested in the cloud only. Not tested on Jason's PC.

## What it does
While Jason is away, Atlas improves its own code with LOCAL models, one small change at a time.
Each kept change becomes a package that Jason approves or rejects. Atlas never merges anything.

One cycle = 7 phases, in this order:

| Phase | What happens | Model? |
|---|---|---|
| plan | Pick ONE open item from the backlog. The model writes a 3-5 line plan. | yes (plan alias) |
| analyse | Read the related files from the sandbox (`repo_context.build`). Read only. | no |
| build | The model writes SEARCH/REPLACE edits. Atlas checks them and applies them in the sandbox. One retry. | yes (build alias) |
| test | Run the fixed tests in the sandbox. Keep the change only if all pass. | no |
| review | A bigger local model reviews the diff and the test output. Verdict: KEEP or REJECT. | yes (review alias) |
| document | Write `report.md` (what, why, tests, review, risks) and `send-to-claude.md`. | no |
| hand off | Commit on a new local branch `atlas-auto/<date>-<n>` in the sandbox. Save `change.patch`. Status `ready`. | no |

A failed build or failed test puts the change aside with `git stash` (nothing is deleted) and marks the
item `failed` after 2 tries.

## States
`off` -> `starting` -> `running` <-> `paused` -> `stopping` -> `off`.
`running` holds the current cycle and phase. `stopped_reason` says in plain words why the mode ended:
"Stopped by Jason", "Night budget used: 6 of 6 cycles", "3 cycles failed in a row", "Tests fail before any change".

## Budgets (all in `headless-dev/settings.json`, editable in the panel)
| Key | Default | Meaning |
|---|---|---|
| `max_cycles` | 6 | cycles per night (a night = one start of the mode) |
| `night_minutes` | 240 | working minutes per night (paused time does not count) |
| `night_tokens` | 60000 | model output tokens per night (estimated: characters / 4) |
| `cycle_minutes` | 30 | one cycle stops at the next phase after this |
| `cycle_tokens` | 12000 | model output tokens per cycle |
| `max_failures` | 3 | failed cycles in a row, then the mode stops |
| `idle_minutes` | 10 | Jason's last chat must be this old before work starts or goes on |
| `plan_model` / `build_model` / `review_model` | `tasks` / `coder` / `mentor` | llama-swap aliases |
| `cloud_enabled` | false | cloud review only when Jason turns it on |
| `cloud_spend_limit_usd` | 0.0 | cloud stops at this estimate. 0 = no cloud at all |

## Safety limits (each one has a test in `validation-tests/test_headless_dev.py`)
1. **Never Jason's branches.** Atlas works in a separate `git clone` under the data folder
   (`<ATLAS_DATA_DIR>/headless-dev/sandbox`). The clone's push URL is set to `DISABLED://no-push`.
   Jason's own repository is only read (`git rev-parse HEAD`, `git clone`). No refs are added to it.
2. **Never push, fetch, reset, clean, delete branches.** Every git call goes through `_git()`, which only
   allows: `clone`, `rev-parse`, `status`, `diff`, `apply`, `add`, `commit`, `checkout -b`, `stash push`,
   `log`, `format-patch`, `remote set-url --push`, `config`. Anything else raises `SafetyError`.
3. **Never model-written shell commands.** The only commands that run are the fixed lists in
   `FIXED_TESTS` (the CLAUDE.md section 5 tests and `check-bundle.py`). The model only writes text.
4. **Edits only inside allowed folders.** `atlas-rust-desktop/src-tauri/resources/atlas/`,
   `atlas-rust-desktop/validation-tests/`, `docs/`. No absolute paths, no `..`, no `.git`. Existing test files cannot be changed (a new test file is fine),
   so a model cannot make a test pass by editing it. At most 3 files and 200 changed lines per cycle.
5. **Never delete files.** A failed change is stashed, not removed. An edit that deletes a file is refused.
6. **Approval gate.** Every action goes through `request_action()`. The tier comes from `mcp_chat.TOOL_TIERS`
   plus the headless actions (`sandbox_read`, `sandbox_edit`, `run_fixed_tests` = low risk).
   Anything above low risk is NOT run: it is added to the "Waiting for Jason" list in the panel.
7. **One local model at a time.** Every model call holds `swarm_run._machine_lock("")`, the same lock
   the /swarm bots use, so night work and a /swarm run take turns.
8. **Pause when Jason uses the PC.** Before each phase and each model call Atlas checks:
   a chat request is running, the last chat request is newer than `idle_minutes`, or a /swarm task is running
   (the GPU is busy). If yes, the mode goes to `paused` and checks again every 30 s.
9. **Stop on repeated failures** (`max_failures`) and on any budget limit.
10. **Base check.** The sandbox base must hold `atlas-rust-desktop/src-tauri/tauri.conf.json` (CLAUDE.md section 1).
    The tests must pass on the clean base first, else the night stops at once.

## Data folders (outside git, in the data folder)
```
<ATLAS_DATA_DIR>/headless-dev/
  settings.json     budgets and model aliases
  state.json        mode, current cycle, counters, stopped_reason
  backlog.json      items: id, title, detail, source, status (open/in_progress/done/failed/skipped), attempts
  log.jsonl         one line per phase event (the panel's live view)
  queue.json        actions waiting for Jason (above low risk)
  sandbox/          the git clone (own branches atlas-auto/<date>-<n>)
  packages/<id>/    change.patch, report.md, send-to-claude.md, meta.json
```
The backlog is seeded once from open TODO lines: `- [ ]` and `TODO:` in `docs/*.md`, and `# TODO` comments in
`atlas-rust-desktop/src-tauri/resources/atlas/*.py`. Jason can add items in the panel.

## Which repository
Setting `repo` in `headless-dev/settings.json`, else `ATLAS_DEV_REPO`, else the first folder above the app that
has `.git` and `atlas-rust-desktop/src-tauri/tauri.conf.json` (on Jason's PC: `F:\APP-DEV\projects\atlas-chat`).
The sandbox starts from the commit that repository's HEAD points to. Uncommitted changes are not copied.

## Endpoints (local only, same origin rules as the approval buttons)
| Method | Path | Body | Does |
|---|---|---|---|
| GET | `/api/headless/status` | - | state, settings, budget use, backlog, packages, queue, last 80 log lines |
| POST | `/api/headless/start` | - | start the mode (refuses when already on) |
| POST | `/api/headless/stop` | - | stop after the current phase |
| POST | `/api/headless/settings` | `{key: value}` | change budgets (checked and clamped) |
| POST | `/api/headless/backlog` | `{title, detail}` | add an item |
| POST | `/api/headless/package` | `{id, decision: approve/reject, note}` | Jason's decision |
| GET | `/api/headless/package?id=...&file=report` | - | `report.md` or `send-to-claude.md` text |
| POST | `/api/headless/queue` | `{id, decision: dismiss}` | clear a waiting action (it never runs) |

## Hand-off and review
- Review path (a): the `review_model` alias (default `mentor`, the bigger local model) writes the review
  in the review phase. Its verdict is in `report.md`. A REJECT verdict is shown with a warning; Jason still decides.
- Review path (b): `send-to-claude.md` is a ready prompt for a Claude Code session: base commit, patch, report,
  and the rules (apply on a new branch from Jason's app branch, run the tests, push only to its own branch,
  then Jason runs `python get_update.py <branch>`).
- **Approve** only marks the package `approved`. It does not merge, apply or push. Jason (or a Claude session)
  applies `change.patch` the normal way. **Reject** marks it `rejected` and the item goes back to `open` once.

## UI
Header button `NIGHT DEV // OFF`. It opens a `<dialog>` (top layer, own scroll, Esc closes), so the page never
scrolls (CLAUDE.md section 8). Inside: Start/Stop, budget form, the live cycle (7 phase chips, like the swarm stage
view), the log, the "Waiting for Jason" list, and the packages with Approve / Reject / Copy for Claude.
Keyboard: every control is a button or input; visible focus; no motion when reduced motion is set; one column at phone width.

## Tests
- `atlas-rust-desktop/validation-tests/test_headless_dev.py` (runs with the backend suite): git allow-list, fixed
  commands, edit checks, approval gate, budgets, pause, endpoints, and two full nights on a throwaway git repo
  (Jason's repo checked unchanged: HEAD, branches, status, stash, worktrees, remotes).
- `node atlas-rust-desktop/validation-tests/e2e_night_dev.mjs` (browser): panel opens by keyboard, page never scrolls,
  dialog fits at 1400x900 and 390x800, focus ring, Esc returns focus, reduced motion, Approve reaches the backend.
  Run with `DSF=1.25` and `DSF=1.5` too.

## Not done (on purpose)
- No GPU sensor. "GPU busy" = a chat request or a /swarm task is running. A game or another app on the GPU is not seen.
- No time window (for example 23:00-07:00). Jason starts and stops the mode himself.
- Cloud review uses a flat price setting (`cloud_usd_per_mtok`), not the provider bill.
