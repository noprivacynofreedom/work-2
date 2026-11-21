# Session coordination: read this first (updated 2026-11-18)

Every Claude session on Atlas reads this file before it changes code. Sessions cannot message
each other reliably (WSL and cloud sessions cannot reach Desktop sessions). This file is the channel.
Update it when you start or finish work that other sessions must know about.

## State now
- Jason's app branch: `fix/queue-in-chat-dragdrop`. GitHub has only `main` and that branch.
- `review/2026-11-18` holds ALL of today's work. It is built into the installer by the main review session.
  Do not build it a second time. Do not re-merge these branches, they are already in:
  - `claude/fast-inference-b592e9`: background calls do not think, bots of one alias share the loaded
    model (3 at most, `ATLAS_SWARM_SLOTS=1` = old behaviour), faster llama-swap flags.
    See `docs/FAST-INFERENCE-2026-11-18.md`.
  - `claude/swarm-quality-740227`: chat names the folder the bots read, warns when it has no code,
    review lists invented paths and tool mismatches.
  - `claude/release-checks-766a55`: 4 stale node test harnesses fixed. See `TEST-RESULTS-2026-11-18.md`.
  - `claude/ui-a11y-83cf3f`: queue buttons not selectable, live GPU telemetry on Operations, Node page.
    See `UI-A11Y-2026-11-18.md`.
- Their worktrees under `.claude/worktrees/` may be pruned now: the branches are merged.
- Outside git: `F:\APP-DEV\tools\llama-swap\config.yaml` was changed (backup `config.yaml.bak-20261118`).

## Done 2026-11-18 (evening, scheduled review run)
- `claude/agent-approval-gate-37eabf` (81a4b695) merged into `review/2026-11-18` (fast-forward). Backend 160 OK.
- `build-release.ps1` fix `d166c8b6`: tauri step no longer fails on stderr under `*>` redirect.
- `fix/queue-in-chat-dragdrop` = `review/2026-11-18` = `d166c8b6` (local, NOT pushed).
- Release build verified: `Atlas Chat_0.1.1_x64-setup.exe`, SHA256 7F6AF369...EDDEB. Not installed.
  Jason's notes: `REVIEW-2026-11-18.md`. Do not build this again.

## Done 2026-11-18 (cloud session, branch `claude/laughing-lamport-c4z13r`)
- Correction to the note above: `fix/queue-in-chat-dragdrop` (d166c8b) IS on GitHub now.
- `claude/laughing-lamport-c4z13r` holds `fix/queue-in-chat-dragdrop`, `claude/blissful-lovelace-1ejwjb`,
  `claude/relaxed-bell-9ycsfi` and `claude/atlas-nsis-speed`. Each can fast-forward to it.
- Root MCP tests no longer hang on the approval gate (fake tools get a tier). `test_swarm_tree.js` fixed.
- `validation-tests/e2e_page_never_scrolls.mjs` added. `build-release.ps1 -FastNsis` added (no installer compression).
- The other agent's `claude/atlas-nsis-speed` work was never committed. Reviewed from a zip; the version on
  `claude/laughing-lamport-c4z13r` was kept. The worktree `atlas-chat-nsis-speed` is no longer needed.
- Not checked on the PC: a Windows build, `-FastNsis`, and the page-scroll fix at desktop size.

## Still open (not started; Jason decides)
- `fix/mcp-request-hardening` (18 MCP/request fixes) is far behind. Rebase onto `review/2026-11-18` first.
- Agent mode plan (approval gate in `mcp_chat.py` first, then read-only email drafts, nothing ever sent).
  Waits for Jason's choice of option. Branch: `feat/agent-mode` off `review/2026-11-18`.
- WSL session work never committed: `server.py` (empty `llama_swap` defaults), `tests/test_no_hardcoded_paths.py`,
  `BUILD-ATLAS.ps1`. Compare with `review/2026-11-18` before committing: `server.py` changed a lot today.
- `resources/atlas/runtime/llama-swap/config.yaml` (not in git, ships in the installer) points to an
  abliterated model in Jason's Downloads folder. Fine on his PC, wrong for a client install.
- Peer (second PC) placement in the scheduler has only fake-peer tests.

## File ownership rule
One session per file set at a time. Before you edit, add a line here: session, branch, files.
- Codex book tools, branch `feat/commander-public-books`: `src/mcp_commander.py`, new `src/book_commander.py`, new `validation-tests/test_commander_books.py`, `docs/COMMANDER-BOOKS.md`.
- Codex book tools status: local tests pass; live Gutendex request timed out. No Z-Library provider or in-app webview is included; waiting on documented permitted account API details before adding that provider.
- Approval gate session, branch `claude/agent-approval-gate-37eabf` (committed, not merged): `mcp_chat.py` (gate + TOOL_TIERS), `server.py` (`/api/approvals`, gated `/api/mcp/call`), `index.html` (`#approvals`), `validation-tests/test_approval_gate.py`, `test_mcp_chat.py`.
