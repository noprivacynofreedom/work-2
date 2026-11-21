# Atlas Chat — Components, User Guide & FAQ

**Last Updated:** 18 November 2026  
**Applies to:** Atlas Desktop v2.x (Tauri + Rust + React + Python Backend)

---

## 1. System Component Map

```
┌────────────────────────────────────────────────────────┐
│               Atlas Desktop Shell (Tauri / Rust)       │
│  - Native window management & tray                     │
│  - NSIS installer with fast packaging (uncompressed)   │
│  - WebView2 integration (pins 100% height, no scroll)  │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│         Frontend Frame (React 18 / TypeScript / Vite)  │
│  - Optik Dark, DedSec Dark & Classic Dark Themes       │
│  - In-chat Swarm Bar (#swarmBar) & Tree Navigation     │
│  - Unified Swarm Board (atlas_botlogs.js)              │
│  - Test Suite Kanban Interface (test_suite.html)       │
│  - Memory Manager Dialog & Approval Card Rail          │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│      Python Backend Service (server.py on port 8090)   │
│  - SSE streaming (/v1/chat/completions)                │
│  - Hyperswarm coordinator (local, hyper, abliterated)  │
│  - Lightweight summary APIs (/api/conversations, runs) │
│  - State caching (_STATE_CACHE) & atomic persistence   │
│  - Local SQLite Observability DB (o.sqlite3)           │
└─────────────┬───────────────────────────┬──────────────┘
              │                           │
┌─────────────▼─────────────┐ ┌───────────▼──────────────┐
│   MCP Tool Suite          │ │   AI Inference Layer     │
│ - Commander (workspace)   │ │ - llama-swap on port 8080│
│ - Test Suite Kanban MCP   │ │ - Vulkan GPU acceleration│
│ - Browser MCP (automation)│ │ - Local models: coder,   │
│ - Book Library Tools      │ │   mentor, tasks, assist  │
│ - Bounded Approval Gate   │ │ - Free Cloud APIs: Groq, │
│   (read/write/consequential│ │   Gemini, Cerebras,     │
└───────────────────────────┘ │   OpenRouter, GitHub     │
                              └──────────────────────────┘
```

---

## 2. Hyperswarm & Multi-Agent Swarms

Atlas Chat features a multi-agent swarm architecture that can plan, distribute, implement, test, and review complex software and research goals.

### The 3 Swarm Modes

1. **`hyper` Mode** (`/hyperswarm <goal>` or `/swarm hyper <goal>`):
   - **Blended Hivemind**: Harnesses free cloud API tiers for rapid planning, synthesis, and review, while local models execute tasks or fall back when offline.
   - **Supported Free Providers**:
     - **Google Gemini Flash** (`GEMINI_API_KEY`): Planning and synthesis.
     - **Groq Llama 3.3 70B** (`GROQ_API_KEY`): Lightning-fast 300+ tok/s inference.
     - **Cerebras Llama 3.3 70B** (`CEREBRAS_API_KEY`): 1000+ tok/s high-throughput reasoning.
     - **OpenRouter Free Tier** (`OPENROUTER_API_KEY`): Free routing (`openrouter/free`, `qwen/qwen3-coder:free`).
     - **GitHub Models** (`GITHUB_TOKEN`): GPT-4o Mini free tier.
     - **DeepSeek** (`OPENROUTER_API_KEY`): Code review.
   - **Resilience**: If any cloud API experiences rate limits (HTTP 429) or connection issues, the swarm automatically falls back to alternative free providers or local GPU models.

2. **`local` Mode** (`/swarm local <goal>`):
   - **100% Offline & Air-Gapped**: Runs exclusively on local Vulkan models (`coder`, `mentor`, `tasks`, `assist`) on your PC and LAN compute peers.
   - **Zero Cloud Network Calls**: Completely safe for sensitive or proprietary codebases.

3. **`abliterated` Mode** (`/swarm abliterated <goal>`):
   - **Uncensored Technical Reasoning**: Routes to abliterated/unrestricted local models or uncensored cloud endpoints.
   - **No Refusal Filters**: Injects direct, objective system directives for security research, kernel audits, vulnerability analysis, and unconstrained coding.

### Swarm Lifecycle & Pipeline

When a swarm starts, it progresses through 5 transparent stages visible on the in-chat `#swarmBar` and the **Swarm Board**:
1. **Plan**: Specialist bots are assigned non-overlapping portions of the goal.
2. **Workers**: Bots work concurrently (cloud lanes run in parallel; local GPU lane coordinates model swaps).
3. **Combine**: Results are synthesized into cohesive code files (`FILE: path/to/file.ext`).
4. **Test**: Real unit tests execute on the generated code in a sandboxed runner.
5. **Review**: Grounding check compares against actual workspace files; reviewer audits code quality.

---

## 3. Slash Commands & How To Use

| Slash Command | Parameters | Description |
|---|---|---|
| `/hyperswarm` | `<goal>` | Run a hybrid multi-agent swarm in `hyper` mode. |
| `/swarm` | `[local\|hyper\|abliterated] <goal>` | Run swarm with specified operational mode. |
| `/swarm stop` | — | Cancel all active swarm tasks and unload models. |
| `/swarm help` | — | Print mode guide and usage examples. |
| `/remember` | `<fact>` | Save a persistent fact across all conversations (e.g. `/remember I use PowerShell on Windows`). |
| `/forget` | `<keywords>` | Delete matching stored memories. |
| `/memory` | — | Open the visual Memory Manager window. |
| `/compact` | — | Compact long chat history to save context tokens. |
| `/context` | — | Open the context inspector showing token usage. |
| `/new` | — | Start a fresh chat with the active bot. |
| `/retry` | — | Re-run the last assistant reply. |
| `/help` | — | List all available chat slash commands. |

---

## 4. MCP Tools & Approvals

Atlas implements Model Context Protocol (MCP) with a bounded 3-tier approval gate:

- **Read Tier** (Runs freely): `list_workspace_files`, `read_workspace_file`, `git_status`, `git_diff`, `list_books`, `read_chapter`, `test_suite_list`, `browser_get_text`, `browser_screenshot`.
- **Write Tier** (Asks for approval unless `ATLAS_WRITE_APPROVAL=auto`): `write_file`, `write_project_file`, `test_suite_add`, `test_suite_update`, `browser_click`, `browser_type`.
- **Consequential Tier** (Always asks for user confirmation): `web_search`, shell execution, network calls.

Approvals appear as interactive cards directly above the message log.

---

## 5. Frequently Asked Questions (FAQ)

### Q: How do I rebuild Atlas Chat quickly?
Run:
```powershell
.\build-release.ps1 -CloseApp
```
**Fast NSIS is now the default.** It skips single-threaded compression and outputs the installer in 30–60 seconds.

### Q: Can I update the Python backend and UI without running the installer?
Yes! Use **Hot Sync**:
```powershell
.\build-release.ps1 -HotSync -Launch
```
This syncs changes into `app/` in 2–3 seconds and restarts Atlas Chat immediately.

### Q: Where are my chats, models, and outputs stored?
- User data (chats, memory, bots): `F:\APP-DEV\data\Atlas Chat` (outside git; never overwritten).
- Swarm output files: `<Workspace>/swarm-output/<run_id>/` (or `<data_dir>/swarm-output`).
- Observability logs: Local SQLite database at `<AppData>/Local/Temp/.../o.sqlite3`.

### Q: How do I switch themes?
Click **Settings** (gear icon) in the sidebar:
- **Optik Dark**: Modern cyberpunk high-contrast dark theme.
- **DedSec Dark**: Neon hacker green/black terminal theme.
- **Classic Dark**: Standard neutral dark theme.

### Q: Does Atlas Chat run on Linux?
- The Python backend and Tauri frontend support Linux.
- Use `./setup-linux.sh` to install build dependencies on Ubuntu/Fedora/Arch.
- Use `./build-linux.sh` to build the frontend and Tauri executable.

---

## 6. Memory Notes & Best Practices

1. **Always edit files in `atlas-rust-desktop/src-tauri/resources/atlas/`**:
   The installer packages files from this directory. Never edit files directly in `app/` (the build will overwrite them).
2. **Page scrolling rule**:
   The outer window and HTML body must **never scroll**. Only `#log` and side panels scroll. Keep `.app{height:100%}` and `#approvals{max-height:35vh;overflow:auto}`.
3. **No git reset on user data**:
   Never reset or delete folders named `data`, `bots`, `exports`, `logs`, `runtime`, `swarm-workspaces`.
