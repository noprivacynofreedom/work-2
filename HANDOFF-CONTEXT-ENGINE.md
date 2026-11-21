# Handoff: context engine (RAG, memory, compaction, real token counts) — 2026-11-12

Branch: `claude/fervent-maxwell-un4jr8`. It is `claude/optimistic-dijkstra-yyrk7u` plus 1 commit.
Update command (Jason's PC, in `F:\APP-DEV\projects\atlas-chat`): `python get_update.py claude/fervent-maxwell-un4jr8`, then `.\build-release.ps1`.
No branch had work missing from this base on 2026-11-12 (checked every desktop branch with `git rev-list` and `git cherry`).

## Tested / not tested
- Tested in the cloud: backend tests (129 OK, 12 new in `validation-tests/test_context_engine.py`), `check-bundle.py`,
  swarm JS tests, and a new browser test `validation-tests/e2e_context_ui.mjs` (12 checks: real `server.py` + real
  `index.html` in Chromium against `validation-tests/fake_llama_swap.py`).
- NOT tested: the installed app on Jason's PC, a real llama-server / llama-swap, the installer build (Windows only).
- Fails on the base branch too (not this change): `test_atomic_chats.js`, `test_conversation_bridge.js`,
  `test_chat_queue.js` when run from the repo root (it passes from `src-tauri/resources/atlas`), 1 error in `tests/test_conversation_api.py`.

## What was wrong before
1. The CTX meter used the bot setting (32,768) but the generated llama-swap config starts models with `-c 16384`. The meter showed half the real fill.
2. Token counts were `characters / 3.2`. After the reply it used `timings.prompt_n`, which leaves out cached tokens (`cache_n`), so long chats looked small.
3. Library passages and the Atlas default prompt were added on the server, after the UI counted. The meter never saw them.
4. Retrieval always added the top 5 hits, relevant or not, with no size cap. It read the whole index file from disk on every message.
5. A short follow-up ("and the lens?") searched the library with only those words.
6. Old messages were silently dropped when the chat got long. No summary, no memory across chats.

## What changed
Backend (`atlas-rust-desktop/src-tauri/resources/atlas/`):
- New `context_engine.py`: real `n_ctx` from `/upstream/<model>/props`; exact prompt count with `/apply-template` + `/tokenize`
  (only when `/running` says the model is loaded, so it never starts a model); retrieval query + hit filter
  (relevance >= 35% of the top hit, no near-duplicates, token budget); memory store `<data>/.atlas/memory.json`; compaction prompt.
- `server.py`: `_inject_context` adds memory + filtered library passages; `_prepare_upstream_chat` asks for
  `stream_options.include_usage` and adds the exact count. New header `X-Atlas-Context` (counts, titles, `n_ctx`, `prompt_chars`).
  New routes: `GET /api/context/window?model=`, `GET|POST /api/memory`, `POST /api/context/compact`. Index records cached in memory by file mtime.
- `mcp_chat.py`: tool loop sums usage over all rounds (`atlas_usage_total`); `as_sse` passes `usage` and `timings` on.
- Settings (optional, in `settings.json`): `exact_token_count` (true), `memory_context_tokens` (1500),
  `knowledge_context_tokens` (3000), `default_context_window` (16384).

UI (`index.html`), same ATLAS // mono style:
- CTX meter: real window, EXACT / MEASURED / ESTIMATED label, live count while the reply streams, amber at the
  auto-compact threshold, red at 95%. Breakdown adds Memory, Retrieved knowledge, Compacted summary, Template/Atlas prompt, Reply.
  Characters-per-token is learned per model from real counts.
- Auto-compact (default 80%, setting in the usage panel) and `/compact` + COMPACT NOW: older messages become a summary,
  a dashed "CONTEXT COMPACTED" marker shows it in the log.
- MEMORY panel (`MEMORY // n` button): add, edit, delete, on/off. `/remember <fact>`, `/forget <words>`.
- Slash commands with a hint list (arrow keys, Tab, Esc): `/compact /context /remember /forget /memory /retry /new /help /swarm`.
- Per message: EDIT (user), RETRY (assistant), BRANCH (both), token line "in · out".
- Chat search box above the chat list (title and message text). Answers list `library:` titles and `memory: n` in the stats line.
- Phone width: the message box takes the full row.

## Known gaps
- Image tokens are a fixed 2,048 per image (the projector cost is not exposed by llama-server).
- Per-bot memory/knowledge switches exist in the request (`atlas_context_flags`) but have no checkbox in the bot editor yet.
- The Atlas default prompt is about 2,500 tokens. The breakdown now shows it as "Template / Atlas prompt / docs".
