# Fast local inference, 2026-11-18

Measured on Jason's PC: AMD RX 9070 XT (16 GB VRAM), 31 GB RAM, 8 cores / 16 threads, Windows 11.
llama.cpp Vulkan build 12125 (`F:\app-dev\tools\llama-vulkan`). The build in `F:\APP-DEV\models\llama-b10549-...`
is older (10549), so it was not used. Nothing was downloaded.
Windows, the browser and Wallpaper Engine use about 2.3 GB of VRAM before any model loads.
Rule used for every choice: keep at least 2 GB of VRAM free.

Scripts and raw numbers (JSON lines) were in the session scratchpad. The key numbers are copied here.
"Long prompt" = about 3000 tokens of `swarm_run.py` plus a question. TTFT = time to the first token.

## Before / after

| Alias | What | Before | After |
|---|---|---|---|
| coder | TTFT, 3000-token prompt | 10.3 s (292 t/s prompt) | **4.0 s** (769 t/s prompt) |
| coder | generation, long prompt | 70 t/s | **80 t/s** |
| mentor | TTFT, 3000-token prompt | 6.6 s (499 t/s prompt) | **2.8 s** (1208 t/s prompt) |
| mentor | generation | 45 t/s | 46 t/s (same) |
| tasks | 3 bots at once (wall) | ~10 s one after another | **6.0 s** (-np 3) |
| mentor | 2 bots at once (wall) | 11.6 s one after another | **7.4 s** (-np 2) |
| assist | unchanged | TTFT 1.9 s, 52 t/s | same |
| swarm | mentor on long swarm prompts | ~3 min, often empty (thinking) | ~3 s (thinking off) |
| swarm | real 3-bot swarm (2x mentor, 1x tasks) | 56.2 s (serial lane) | **47.0 s** (new scheduler) |

The 3-bot swarm number is one run each, so treat the 16 % as a rough figure.
Swap times (unload + load + first answer): coder 17-19 s, mentor 17 s, tasks 11-13 s, assist 9-12 s, vision 9 s.

## What changed

### llama-swap config (`F:\APP-DEV\tools\llama-swap\config.yaml`, backup `config.yaml.bak-20261118`)
- **coder**: `--n-cpu-moe 28` -> `24`, added `-ub 2048 -b 2048`. Keeps `-np 1` and the MTP draft. VRAM 13.5-13.7 GB.
- **mentor**: added `-ub 2048 -b 2048 -np 2 -kvu`. VRAM 13.3 GB.
- **tasks**: `-np 1` -> `-np 3 -kvu`. VRAM 13.3 GB.
- assist, mentor-dense, vision: unchanged.
- After the change all six aliases loaded and answered (coder, mentor, tasks, assist, mentor-dense, vision).

Why `-ub 2048` works: coder and mentor keep part of their MoE expert weights on the CPU. To read a prompt, llama.cpp
copies those weights to the GPU once per micro-batch (`-ub`, default 512). With 2048, a 3000-token prompt needs 2 copies
instead of 6. Generation speed does not change.

Why `-np N -kvu`: N requests share one loaded model at the same time. `-kvu` makes the slots share ONE 32k KV pool,
so a single chat still gets the full 32k context and VRAM stays almost the same.

### App (`atlas-rust-desktop/src-tauri/resources/atlas/`)
- `llm.call_llm` now sends `enable_thinking: false` by default. Only background work uses this client (swarm bots,
  `agents/atlas_coding_swarm.py`, the model self-test). User chats go through `server.py` and still think.
  `settings.json` `"llm_think": true` turns thinking back on. The empty-answer retry in `_ask_local` stays.
- `swarm_run`: weighted scheduler, **on by default**.
  - Bots of one model alias run together on the one loaded model, up to `ATLAS_SWARM_SLOTS` (default 3).
    Different aliases still run one after another, so llama-swap never loads two models at once.
  - Heaviest bot first (estimate from prompt size and measured tokens/s per alias, `ALIAS_TPS`).
  - Two different /swarm runs still take turns on this PC (machine lock per alias group).
  - **Serial fallback**: `ATLAS_SWARM_SLOTS=1` gives the old one-at-a-time lane. A server without `-np` just queues
    the extra requests, so a too-high value is safe (it only loses the gain).
- `compute_peers`: optional peer fields `"share": true` (this alias also runs on this PC, so Atlas may pick either
  machine) and `"speed"` (1.0 = as fast as this PC, default 0.5). With `share`, the heaviest bot stays on the
  faster machine and lighter bots spill to the other one. Without `share`, the old rule holds: the peer gets the alias.
  **Untested on real hardware** (no second PC here). Only fake-peer unit tests cover it.

## Tried and rejected

| Try | Result | Why rejected |
|---|---|---|
| coder `--n-cpu-moe 22` | TTFT 3.7 s, 86 t/s | 14.4 GB VRAM, under 2 GB free |
| coder `--n-cpu-moe 20` | TTFT 3.6 s, 86 t/s | 15.2 GB VRAM |
| coder `-ub 1024` | TTFT 6.0 s | 2048 is faster (4.5 s) |
| coder without MTP | 38-42 t/s | MTP gives 70-80 t/s, keep it |
| coder `-np 3 -kvu` + MTP | 3 bots in 10.8 s (1.5x) | 14.4 GB VRAM |
| coder `-np 3 -kvu`, no MTP | 3 bots in 14.3 s | single chat drops to ~44 t/s |
| mentor `--n-cpu-moe 12` | 15-19 t/s | spills out of VRAM (13.9 GB + spikes) |
| mentor `--n-cpu-moe 10` | 55 t/s, TTFT 2.4 s | 14.9 GB VRAM, 1.1 GB free |
| mentor `--n-cpu-moe 6` | **6 t/s**, TTFT 21 s | 15.4 GB: spills to shared memory |
| assist `-np 3 -kvu` | works | assist already uses 14.7 GB with `-np 1` |
| two models at once (mentor on GPU + tasks with experts on CPU) | tasks failed to load | not enough memory for both |
| speculative decoding with a separate draft model | not tried | no small model of the same family on disk (coder already uses its built-in MTP head) |
| newer llama.cpp | none on disk | 12125 is the newest present |

Note: the first baseline showed coder at 11.9 t/s on a cached prompt. It did not repeat in 4 later runs (68-82 t/s),
so it was a one-time drop, probably other load on the PC.

## Ideas left to try
- **assist VRAM**: 14.7 GB leaves 1.3 GB free. Try `-c 16384` or a Q4 quant. Measure first.
- **Two models at once**: only small pairs fit (vision uses ~5 GB). A swarm that needs two big models at once does
  not fit on 16 GB. Serial alias groups with fast swaps win here.
- **Swap time**: coder and mentor take ~17 s to load. llama-swap `groups` cannot help (they do not fit together).
  A faster disk, or `--load-mode` mmap with more RAM, may help.
- Use `think=False` in `server.py` distillation and `context_engine.compact` too (summaries, not chats). Not done:
  outside this task's files.
- Real two-PC test of `share`/`speed` placement.
