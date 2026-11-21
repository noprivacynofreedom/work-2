# Atlas Chat

**Local-first AI desktop application evolving toward a hybrid AI platform.**

> Project status: active development / pre-release. Feature maturity and deployment status vary by subsystem. See the internal project master document and evidence register before treating any capability as production-ready.

## Quickstart

### 1. Build & Install (Windows)
```powershell
cd F:\APP-DEV\projects\atlas-chat
.\build-release.ps1 -CloseApp
```
- **Fast NSIS is now default**: Produces the release installer in ~30–60 seconds without slow single-threaded compression.
- **Instant Hot Sync (2 seconds)**: Run `.\build-release.ps1 -HotSync -Launch` to sync backend & UI changes directly to the live app and launch.
- **Compressed Release**: Pass `-Compress` when building smaller distribution installers.

Launch **Atlas Chat** from the Windows Start menu.

### 2. Hyperswarm & Swarm Modes

Type `/hyperswarm` or `/swarm` in chat to orchestrate a team of specialist AI agents:

| Command | Mode | Behavior |
|---|---|---|
| `/hyperswarm <goal>` | `hyper` (default) | Blended Hivemind: Combines free cloud tier APIs (Gemini Flash, Groq 70B, Cerebras, OpenRouter, GitHub) + local models + parallel execution. |
| `/swarm local <goal>` | `local` | 100% Offline: Pure local models (`coder`, `mentor`, `tasks`) and LAN compute peers with zero cloud calls. |
| `/swarm abliterated <goal>` | `abliterated` | Uncensored: Uses abliterated models and direct objective prompts without refusal filters. |
| `/swarm stop` | — | Cancel active swarm runs and unload inference models. |
| `/swarm help` | — | Show full mode reference and usage examples. |

### 3. Key Slash Commands

- `/remember <fact>` — Save permanent facts for every chat (e.g. `/remember I use PowerShell on Windows`).
- `/forget <keywords>` — Remove matching memory facts.
- `/memory` — Open visual memory manager.
- `/compact` — Compact long conversation histories.
- `/context` — View live context window and token usage.
- `/new` — Start a fresh chat with the current bot.
- `/retry` — Re-run the last assistant response.

### 4. Linux Build (Preview)
```bash
./setup-linux.sh   # Check and install OS packages (Ubuntu / Fedora / Arch)
./build-linux.sh   # Build frontend and desktop binary via Tauri
```

## Vision

Atlas aims to make capable AI systems more accessible beyond centralized datacentres by combining local model inference, tool use, agent orchestration, observability and an extensible ecosystem. The desktop application is the user-facing foundation; the longer-term direction includes optional distributed compute and commercial services.

## Product direction

- Local-first desktop experience and model access.
- Hybrid operation: local models with optional remote services where explicitly enabled.
- Multi-agent orchestration, task execution and operational visibility.
- Model Context Protocol (MCP) integrations and extensible tools.
- Developer workflows, knowledge features and persistent conversations.
- A future ecosystem for nodes, contributors, integrations and commercial services.

## Architecture (documented design)

- **Frontend:** React, TypeScript, Vite.
- **Desktop shell:** Tauri and Rust.
- **Compatibility/backend layer:** existing Python chat server and services.
- **AI runtime:** llama-swap and local model endpoints.
- **Agent/platform components:** Atlas Node, Operations, MCP, Dev Engine and a Rust control-plane workstream.

The existing Python-served chat experience is to be preserved and integrated with the desktop shell rather than casually replaced. Atlas Desktop and Atlas Online are separate product surfaces and should remain architecturally distinct.

## Local development environment

Historical project root recorded in development handoffs:

`F:\\APP-DEV\\projects\\atlas-chat`

Desktop application:

`F:\\APP-DEV\\projects\\atlas-chat\\atlas-rust-desktop`

Previously recorded local endpoints (verify against current configuration):

| Service | Endpoint |
|---|---|
| Python API | `127.0.0.1:8090` |
| llama-swap | `127.0.0.1:8080` |
| llama-server | port `5801` |

Previously recorded model aliases: `assist`, `coder`, `mentor`, `mentor-dense`, `tasks`.

These are historical environment notes, not universal defaults. Consult local configuration before launching services.

## Development principles

1. Inspect the current implementation and dependencies before changing code.
2. Plan the complete feature and identify affected components.
3. Integrate related changes coherently rather than stacking disconnected patches.
4. Preserve user data, settings, chat history, model files and Git metadata.
5. Test the changed subsystem, then run regression/integration tests and production build checks.
6. End with end-to-end runtime validation on the target machine.
7. Report source-complete, test-passing, build-passing and runtime-verified as separate states.
8. Keep rollback paths and record exact release artifacts and hashes.
9. Track only processes Atlas owns; never terminate unrelated user processes.
10. Keep security-sensitive actions scoped, approved and auditable.

## Current known workstreams

- Desktop shell, launcher, installer and in-place upgrade lifecycle.
- Chat reliability, conversation queue and conversation navigation.
- MCP tool loop, approval and audit behaviour.
- Atlas Node and control-plane foundations.
- Operations dashboard and agent observability.
- Local Dev Engine and sandboxed patch workflow.
- Knowledge Library and conversation import.
- UI polish, bot avatars and usability improvements.

See `docs/PROJECT-MASTER.md`, `docs/DEVLOG.md` and `docs/EVIDENCE-REGISTER.md` for status and caveats.

## Build and release

Build instructions have changed across iterations. Use the current checked-in build scripts and the latest Windows build handoff rather than assuming old commands remain valid. A successful frontend build alone does not mean the Rust desktop application or installer is release-ready.

For a faster local installer, run `.\build-release.ps1 -FastNsis`. It turns off installer compression, so the installer is larger. The default build keeps ZLIB compression; use it for anything you share. Both modes keep the compiled-core leak check, output hashes and rollback steps. A wrong option name stops the build with an error.

## Security and privacy

Atlas is designed around local-first operation and explicit control over remote execution. Do not describe the product as fully offline, fully private, secure-by-default or production-hardened without validating the exact configuration and threat model. Remote workload participation and privileged actions require explicit consent and scoped authorization.

## Project status

Atlas is an active engineering project. Some subsystems have staged implementations and automated test evidence; target-Windows runtime acceptance remains necessary for several features. The conversation queue and open-conversation cancellation/navigation issues reported on 8 November 2026 remain active blockers until reproduced and verified fixed.

## Documentation

- `docs/PROJECT-MASTER.md` — founder-facing project direction, architecture, status and roadmap.
- `docs/DEVLOG.md` — dated development history and iteration ledger.
- `docs/EVIDENCE-REGISTER.md` — what is proven, what is only staged, and what still needs evidence.
- `docs/investors/INVESTOR-PITCH-NOTES.md` — fundraising narrative and evidence gaps.
- `docs/investors/Atlas-Chat-Investor-Pitch.pptx` — editable first-draft pitch deck.

## Versioning policy

Use semantic versioning for public releases once a stable release process is adopted. Do not equate patch ZIP labels, internal workstream versions, desktop build-sequence versions and public product versions. Record each separately in the devlog and release manifest.


## Repository roadmap

The existing [`ATLAS-ROADMAP-AND-RELEASE-GATES.md`](ATLAS-ROADMAP-AND-RELEASE-GATES.md) remains the canonical detailed roadmap and release-gate record. It is intentionally preserved rather than overwritten.

The founder-facing project overview in [`docs/PROJECT-MASTER.md`](docs/PROJECT-MASTER.md) reconciles that roadmap with the wider product direction and links the historical evidence.
