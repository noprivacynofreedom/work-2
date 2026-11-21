# Atlas Chat — Technical Evidence Register
**As of 8 November 2026**

This register prevents a staged patch, passing unit test or generated installer from being described as a fully working product capability.

| Claim / component | Evidence in recovered record | What it does NOT prove | Next proof required |
|---|---|---|---|
| Operations dashboard foundation installed | User ran Operations Integration v0.1 installer; installed paths and backups recorded | Full swarm execution or all Operations workflows | Verify current files and test UI against live services |
| Agent observability exists | Staged patch described registry, telemetry, SQLite, SSE and SDK; 16 tests reported | Patch installed or real workers instrumented | Install/merge review; register actual workers; verify traces and metrics |
| MCP handshake/tool loop | Smoke and regression tests reported across staged patches | Current production config and all real model/tool calls work | Clean real stdio + HTTP integration and Windows lifecycle tests |
| Dev Engine local worker | v1.3 staged patch and 22 tests reported | Windows model inference and production integration | Target-machine inference, isolation and approval tests |
| Dev Engine sandbox | v1.5 workstream and 31 unit tests reported | Windows Sandbox starts and guest toolchain runs | Windows Sandbox acceptance and hostile-input tests |
| Control Plane integration | Installer reported service files, migrations and tests installed; conflicting files preserved as proposals | All merges reconciled or remote workloads safe | Review proposed files, build, service integration, consent and security review |
| React frontend build | Windows log reported production build passed | Rust compile, Tauri bundle or installer passed | Full ordered build |
| Rust/Tauri release | One design-correction executable and NSIS/MSI generation reported | Latest source is included or installed artifact matches release | Compare hashes, version metadata, install path and launch route |
| Worker registration | Worker registered at localhost:8090 | Work completed; recorded task result was 1 failed / 0 completed | Capture failure reason and complete an actual task |
| Queue reliability | User reports queue does not advance after removal | Any current fix | Reproduce, add regression tests and runtime verify |
| Conversation switching | User reports opening conversation can cancel generation | Any current fix | Runtime test active generation while switching/opening chats |
| Operations navigation | User reports open-conversation action does not navigate correctly | Any current fix | UI end-to-end test from task to Operations |
| Live desktop view | Screenshot/latest-frame foundation described | Interactive live stream / VNC / SSH | Implement transport and demonstrate live interaction |

## Required release evidence bundle

For every release candidate, retain:
1. Git commit SHA and branch.
2. Version manifest with component versions.
3. Exact installer and executable SHA-256.
4. Frontend build output.
5. Rust formatting, check and test logs.
6. Tauri packaging output.
7. Installer upgrade and rollback logs.
8. Target-machine runtime test checklist and results.
9. Regression results for chat, queue, MCP, process lifecycle and data preservation.
10. Known issues and release decision.

## Investor proof checklist

- [ ] Repeatable product demo video and live demo script.
- [ ] Real user interviews and design-partner feedback.
- [ ] Active users, retention and task completion metrics.
- [ ] Representative local inference latency and throughput.
- [ ] Cost comparison using reproducible workload assumptions.
- [ ] Security threat model and permission boundaries.
- [ ] Open-source and third-party model licensing review.
- [ ] Pricing tests and unit economics.
- [ ] Customer pipeline / LOIs / pilots, if obtained.
- [ ] Market sizing with cited sources and a clearly defined initial segment.
- [ ] Funding amount, runway and milestone-linked use of funds.

No user count, revenue, customer contract, partnership, benchmark advantage, market-size figure or funding ask is asserted by this register.
