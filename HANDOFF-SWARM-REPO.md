# Handoff: /swarm reads the repo, writes real files, runs async (2026-11-12)

Branch: `claude/funny-fermi-qpy08t`. Tested in the cloud only. NOT yet run on Jason's PC.

## What changed
1. **The bots read the repo.** `repo_context.py` (new) reads the Workspace folder (Settings) once per run, read-only.
   Every bot and the Swarm Lead's combine step get the file list and parts of the files that match the goal.
   It skips `.env`, keys, certificates, `settings.json`, databases, `.git`, `node_modules`, `target`, `runtime`, and symlinks.
   Limits: 6,000 characters, 4,000 files, 200 KB per file, 5 seconds.
   No Workspace set: each chat says so and tells you to set it.
2. **Real `.py` / `.rs` files.** Each bot now saves its code to `swarm-output/<run>/code/<bot>/`, and the Swarm Lead's code goes to
   `swarm-output/<run>/code/`. Blocks with a `FILE: path` line keep that path. Bare ```` ```python ```` / ```` ```rust ```` blocks become
   `snippet_<n>.py` / `.rs`. The `.md` copies stay. The repo itself is never written.
3. **Async.**
   - `/swarm` answers at once. The repo is read in the background thread.
   - Two `/swarm` runs at the same time take turns on one machine (one lock per machine), but different machines still work at once.
     The Swarm Lead's local steps use the same lock.
   - A hung bot no longer blocks the run forever. After `ATLAS_SWARM_BOTS_MINUTES` (default 30), unfinished bots are marked failed
     and the run goes on with the answers it has. A late answer cannot revive a closed chat.
   - `/swarm stop` no longer waits for a bot that is still thinking.

## Privacy
With a cloud key set, the Plan and Combine steps send text to Gemini. Combine now includes the repo snapshot
(file list and up to 5 file parts, secrets skipped). The Lead chat already says "This text leaves this PC" for those steps.

## Not done
- Rust code is saved but not built or tested (only Python unittest runs). `cargo test` would need a Rust toolchain on the PC.
- The bots cannot open more files on request. They see only the snapshot.

## Tests
`validation-tests/test_swarm_repo_async.py`, 12 tests. Each key test was checked by breaking the code on purpose
(no lock, no time-out, no secret filter): each break made a test fail.
