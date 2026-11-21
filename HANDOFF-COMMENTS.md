# Handoff: add comments to the Atlas code (2026-11-12)

This handoff is for the chat that adds comments. It is valid for branch `claude/funny-fermi-qpy08t`
and the branches built on it. Read `CLAUDE.md` first.

## Checks before you start
1. `git fetch origin`. Build on `origin/claude/funny-fermi-qpy08t`, or on a newer branch that contains it.
   It holds every desktop app branch, merged on 2026-11-12.
2. Ask the Swarm Lead chat (or Jason) if the swarm work is pushed. Until it is, do NOT edit the files in "Wait" below.
3. Ask if the knowledge library chat has pushed. Until it has, do NOT edit its files.

## The job
Add comments that explain WHY code exists and WHAT a block does. Change no code.
- Comments only. No renames, no reformatting, no moved lines, no fixed bugs. Note a bug you find in `HANDOFF-COMMENTS-FINDINGS.md` instead.
- Plain short English, the same style as `CLAUDE.md` section 4: active voice, short common words.
- Python: a docstring on each module, class and public function that lacks one. `#` comments for tricky lines.
- Rust: `///` on public items, `//` inside functions.
- JS / TS / HTML: `//` or `/* */`. In `index.html`, comment only inside `<script>` and `<style>`.
- Do not comment what the code already says (`i += 1  # add one`).
- Do not touch Jason's data, `runtime/`, built files, or `.md` handoffs.

## Files: where to start
Work in `atlas-rust-desktop/` only. The repo root copies are old (see `CLAUDE.md` section 1).
1. `src-tauri/src/*.rs` (Tauri shell)
2. `src/` (React frame)
3. `src-tauri/resources/atlas/`: `server.py`, `llm.py`, `cloud_llm.py`, `compute_peers.py`, `atlas_observability.py`,
   `mcp_*.py`, `agents/*.py`, `src/dev_engine/*.py`, `index.html`

## Wait: do not edit these until the owner chat says go
- Swarm Lead chat: `swarm_run.py`, `swarm_pipeline.py`, `repo_context.py`, `validation-tests/test_swarm_*`
- Knowledge library chat: `books.py`, `book_tools.py`, `knowledge_engine.py`, `docsearch.py` and their tests

## Prove that you changed only comments
Run in the repo root, after each commit:

```
python check-comments-only.py origin/claude/funny-fermi-qpy08t
```

It must print `OK: only comments and docstrings changed.` Python is compared with `ast`, so a code change cannot hide.
Then run the tests from `CLAUDE.md` section 5. Known failures before this work (2026-11-12, cloud):
- `tests/test_model_discovery.py`: needs `runtime/llama-swap/config.yaml`, which is only on Jason's PC.
- `validation-tests/test_atomic_chats.js`: uses `require` in an ES module.
- `validation-tests/test_conversation_bridge.js`: cannot find `src/App.tsx`.
Everything else passes: backend 105 tests, repo root 126 of 127, bundle check.

## How to give the work to Jason
Push your own branch. Tell Jason to run `python get_update.py <your branch>` (see `CLAUDE.md` section 3).
Commit in small pieces (one folder per commit), so a bad commit is easy to drop.
