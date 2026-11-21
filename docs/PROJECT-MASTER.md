# Atlas Chat — Project Master Document
**Document date:** 8 November 2026  
**Status:** Living founder / engineering source of truth  
**Project phase:** Active development; pre-release; fundraising narrative is exploratory

## 1. Executive summary

Atlas Chat is being developed as a local-first AI desktop application with a longer-term ambition to become a hybrid AI platform. The product thesis is that powerful AI should not be confined to centralized cloud interfaces or datacentre infrastructure. Atlas seeks to bring together local inference, model/tool access, agent workflows, operational visibility and, over time, distributed compute and a broader developer/community ecosystem.

The desktop application is the practical product foundation. The broader platform is a strategic direction, not a claim that every planned service is already operational.

## 2. Vision, mission and product thesis

**Vision:** Make capable, controllable AI infrastructure accessible to individuals and organizations, including through hardware they already own.

**Mission:** Build a coherent desktop-to-platform experience for running models, coordinating agents, connecting tools and observing execution.

**Core thesis:** Local compute can improve user control, reduce dependence on centralized inference for suitable workloads, and create a foundation for optional hybrid and distributed execution. The product must prove that this can be delivered with a simpler, safer and more useful user experience than assembling separate tools.

### Product principles
- Local-first by default where technically practical.
- Hybrid connectivity is optional and explicit.
- User data and existing workflows must be preserved during upgrades.
- Agent execution must be observable, attributable and auditable.
- Privileged operations require scoped approval.
- Reliability and end-to-end validation outrank feature-count claims.
- Desktop and online products remain distinct, with deliberate integration boundaries.

## 3. Product definition

### Near-term product: Atlas Desktop
A Windows desktop experience that brings together chat, local model access, tools, knowledge and developer/operations capabilities in one application.

### Longer-term platform: Atlas Network / ecosystem (working concept)
Potential platform capabilities include node registration, distributed workload scheduling, contribution verification, workload consent, centralized coordination and commercial APIs/services. These are roadmap concepts unless separately demonstrated and accepted.

### User groups to validate
1. Individuals who want local AI and control over their data.
2. Developers who need model-powered tools, agent workflows and local automation.
3. Technical teams that need governed agent execution and observability.
4. Potential compute contributors or node operators, if distributed execution proves viable.

These are target hypotheses, not validated customer segments.

## 4. Architecture map

### Desktop and application layer
- React + TypeScript + Vite UI.
- Tauri + Rust desktop shell and native integration.
- Existing Python chat server retained as a compatibility/backend component.
- Launcher, process lifecycle and installer/updater responsibilities.

### AI and integration layer
- Local model serving via llama-swap and model endpoints.
- Model aliases historically recorded: `assist`, `coder`, `mentor`, `mentor-dense`, `tasks`.
- MCP host/tool integration, tool discovery, invocation, audit and approval boundaries.
- Knowledge Library, document ingestion and conversation import workflows.

### Agent and platform layer
- Atlas Node integration and hardware/runtime reporting.
- Operations dashboard for status, queue and audit visibility.
- Agent registry/telemetry concepts: identity, parent-child relationships, host/PID, task state, heartbeats, logs, traces and metrics.
- Dev Engine for local model-assisted development with isolated workspaces and reviewable patch proposals.
- Rust control-plane workstream for potential coordination and distributed workload foundations.

### Historical local endpoints (must be verified)
- Python API: `127.0.0.1:8090`
- llama-swap: `127.0.0.1:8080`
- llama-server: port `5801`

These are environment-specific records from prior handoffs, not product guarantees.

## 5. Workstream status snapshot

Status labels: **Documented installed**, **staged / unconfirmed**, **partially integrated**, **planned**, **blocked / needs runtime validation**.

| Workstream | What the record says | Current confidence |
|---|---|---|
| Existing Python chat/backend | Established foundation and compatibility requirement | Existing project component; exact current tree not re-inspected for this document |
| React/Tauri desktop | Production build and installer work progressed; Rust lifecycle and packaging repeatedly iterated | Partially validated; target-machine acceptance required |
| Operations Integration v0.1 | User ran installer; dashboard foundation installed without changing chat data/settings/Python files | Documented installed |
| Agent Observability v0.1 | Registry, telemetry, SQLite, SSE and SDK staged; 16 staged tests reported | Staged; installation not confirmed |
| MCP reliability | Handshake, tool loop, duplicate-call and round-budget fixes across patch iterations | Several staged/smoke validations reported; current end-to-end status must be retested |
| Dev Engine local worker v1.3 | Local coder model, disposable workspace and reviewable JSON patches | Staged; 22 tests reported; Windows production integration unconfirmed |
| Control Plane v0.1 / v0.3.0–0.3.1 integration | Rust service, Docker assets, migrations, scheduler/contribution utilities and desktop integration patches | Some files reported installed; merge conflicts/proposals and target runtime remain to validate |
| Knowledge Library | Local indexing and document support, conversation import and provenance features | Implemented across iterations; dependency/runtime acceptance required |
| UI / avatars / import | Selectable responses, copy actions, bot avatars, browser transcript import, MCP loop guardrails | Patch validation reported; installation state depends on latest installer |
| Conversation queue | Queue and Rust integration work exists; user reports items do not advance after removal and opening a conversation can cancel generation | Active blocker; not accepted |
| Operations navigation | User reports “open this conversation” does not navigate to Operations as intended | Active blocker; not accepted |
| Live agent desktop / SSH | Screenshot storage foundation described; live desktop/SSH viewing still outstanding in earlier handoff | Planned / incomplete |

## 6. Confirmed project constraints and engineering rules

- Project root recorded as `F:\APP-DEV\projects\atlas-chat`.
- Desktop project recorded as `F:\APP-DEV\projects\atlas-chat\atlas-rust-desktop`.
- Keep Atlas Desktop separate from Atlas Online.
- Preserve the existing Python-served chat UI and integrate rather than replace unnecessarily.
- Do not overwrite `settings.json`, `data.json`, chat history, knowledge data, model files, exports or Git metadata without an explicit, reviewed migration.
- Prefer in-place upgrade/replace of the installed application, with pre-update backup, version detection, cleanup of superseded generated artifacts and rollback on failure.
- Desktop must own and shut down only child processes it started. Track exact PIDs/process handles; graceful shutdown first, bounded forced termination only for owned children.
- Do not use broad process-kill commands.
- For Atlas troubleshooting, work one problem at a time and request only the files required for that problem.
- User expects complete copy-paste PowerShell blocks with project directory established first.
- Prefer direct in-place scripts/edits over patch ZIPs when safe; when a ZIP is necessary, explain why.
- Release discipline: inspect → plan → integrate → targeted tests → regression/integration tests → production build → fix/retest → end-to-end runtime acceptance.
- Clearly distinguish source-complete, tests-passing, build-passing and runtime-verified.
- Each milestone needs a concise completed / remaining / blocker recap.

## 7. Development history and version interpretation

Atlas history contains several parallel version namespaces:
- Legacy Python project snapshots and source archives.
- Feature patch versions (for example Operations v0.1, Agent Observability v0.1, Dev Engine v1.3, MCP v1.5).
- Full-source snapshots (v0.3.0 and v0.3.1).
- Control-plane integration patches (v0.3.0 / v0.3.1).
- Desktop build-sequence scripts (v0.3.3 / v0.3.4).
- Rust test-build and knowledge/queue upgrade iterations.
- Installer/release package versions.

These are not necessarily sequential public product releases. The project should not retroactively invent a single version chronology where the evidence only records separate patch streams. Future releases should have one canonical product version plus component versions in a manifest.

## 8. Roadmap

### P0 — Stabilize the desktop release path
- Establish one authoritative current source tree and clean working baseline.
- Verify installed application identity, launcher path and upgrade behavior.
- Ensure shortcuts launch the current installed build through the managed launcher.
- Validate backup, in-place replacement, cleanup and rollback.
- Confirm lifecycle ownership for every child process Atlas starts.
- Run clean Windows production build and installer acceptance.

### P0 — Fix core conversation reliability
- Repair queue advancement after deleting/removing queued messages.
- Ensure queue worker wakes, reorders and consumes the next eligible item correctly.
- Ensure opening a conversation does not cancel or invalidate active generation.
- Fix conversation-to-Operations navigation and task linkage.
- Add regression tests for queue mutation, cancellation, conversation switching and active generation.
- Validate through real UI runtime, not only unit tests.

### P1 — Complete MCP reliability and safety
- Verify initialize/discovery/call lifecycle.
- Verify child process cleanup on failed handshake and normal shutdown.
- Ensure advertised tool names match actual handlers.
- Bound tool loops, suppress duplicate calls and return honest incomplete-work summaries.
- Verify audit events and approval enforcement end to end.

### P1 — Integrate agent observability
- Connect actual workers to registry and heartbeat.
- Instrument real model/tool calls, task handoffs and failures.
- Correlate task IDs, trace IDs and spans.
- Add live logs, metrics and trace waterfall.
- Keep screenshot capture clearly distinct from interactive live desktop streaming.

### P1 — Finish Node / Control Plane integration
- Reconcile `.atlas-control-plane-proposed` files deliberately; do not blindly overwrite local changes.
- Validate gateway contract and node identity.
- Test scheduler, contribution verification and consent boundaries.
- Run integration tests against the actual desktop and service.
- Do not enable remote workload consent before security and acceptance gates pass.

### P2 — Product quality and developer experience
- Complete knowledge indexing and import reliability.
- Improve documentation, onboarding and diagnostics.
- Validate bot avatar and UI patch installation.
- Build coherent Operations selected-task evidence view, including artifacts, full paths, workspace evidence and live-feed capability, without destabilizing Chat/Node.

### P3 — Commercial validation
- Interview target users and define initial customer problem.
- Select a narrow paid use case.
- Validate willingness to pay and support requirements.
- Build pricing and unit economics from measured inference/compute costs.
- Establish security, privacy, licensing and legal review.
- Only then set a specific fundraising amount and use of funds.

## 9. Release acceptance gates

A release is not complete merely because source code exists or a patch ZIP was generated.

1. **Source gate:** changes are integrated into the authoritative working tree; no unresolved proposed merges.
2. **Targeted test gate:** tests for changed components pass.
3. **Regression gate:** existing chat, data persistence, MCP and lifecycle tests pass.
4. **Build gate:** frontend, Rust checks/tests and production Tauri bundle pass.
5. **Installer gate:** clean install and in-place upgrade tested; app identity and shortcuts correct.
6. **Data safety gate:** settings, chats, models and user data preserved; rollback proven.
7. **Runtime gate:** real target-machine end-to-end test passes.
8. **Release evidence gate:** version, manifest, hashes, logs and known limitations recorded.

## 10. Commercial model hypotheses

Potential models to validate rather than promise:
- Free/local desktop core with paid advanced features.
- Paid team/organization tier for managed agent workflows and governance.
- Optional hosted APIs or managed control-plane services.
- Marketplace or paid integrations, if an ecosystem develops.
- Distributed compute coordination or workload marketplace, only after proving reliable supply, demand, security and economics.

The core product should remain valuable without requiring speculative token economics or an unproven compute marketplace.

## 11. Fundraising readiness

A credible investor conversation needs more than a compelling architecture. Required proof:
- Working product demo on target hardware.
- Clear comparison against alternatives and a specific wedge.
- Customer discovery evidence and design partners.
- Usage, retention and task-success metrics.
- Measured local-vs-cloud cost/performance on representative workloads.
- Security model, licensing/IP review and data-handling documentation.
- Pricing experiments and cost-to-serve model.
- Hiring plan, milestones and evidence-based funding ask.

Do not invent TAM/SAM/SOM, revenue, users, partnerships, benchmark advantages, patents or funding requirements. Add sourced numbers only after research and validation.

## 12. Documentation governance

This document is the strategic and status overview. `DEVLOG.md` is the chronological change record. `EVIDENCE-REGISTER.md` distinguishes claims from proof. The GitHub README is the public entry point. Investor materials should be generated from the same facts and must not overstate maturity.

Each future iteration entry should include:
- Date/time and branch/commit (when available).
- Version namespace and patch identifier.
- Problem / user request.
- Discussion and decision.
- Files/components affected.
- Change summary.
- Backup/rollback reference.
- Tests run and exact results.
- Build/package result and hashes.
- Runtime acceptance result.
- Remaining issues and next action.

**Historical completeness note:** This document is reconstructed from available saved handoffs, devlogs, patch manifests, build logs and conversation summaries. It is not a verified export of every Atlas-related chat message or every commit. Missing historical entries must be added from source logs/Git rather than fabricated.


## 13. Reconciled repository roadmap (source-derived)

The repository already contains `ATLAS-ROADMAP-AND-RELEASE-GATES.md`. That file is retained as the canonical detailed delivery-gate document; it is not replaced by this master document.

The existing roadmap records the following architecture decision:
- Keep Atlas as one product/repository with separately deployable services.
- Do not merge the control plane into the desktop process.
- Keep the control plane as an independent Rust service.
- React + TypeScript is the desktop presentation layer.
- Rust/Tauri owns desktop lifecycle, node supervision, local resource limits, signing, Docker process ownership and native APIs.
- Python retains existing Atlas Chat API/MCP compatibility and model tooling where it preserves working integrations.
- Rust/Axum is the network control plane; PostgreSQL is the planned persistence layer for network identities, workload queue, node heartbeats and contribution receipts.
- llama-swap/Ollama adapters provide local inference-provider compatibility.

The existing roadmap describes a delivery that added a Rust/Axum control-plane service, PostgreSQL migrations, Ed25519 challenge-response registration, signed node request verification, replay fingerprints, heartbeats, eligibility checks, scheduler-signed workload envelopes, receipt signature validation, operator revocation, manual contribution review, localhost-only Docker Compose and key generation. It also records desktop heartbeat-consent reporting, Ollama/OpenAI-compatible model discovery and benchmarking, and improved Docker workload cancellation.

The same roadmap explicitly preserves the existing chat iframe, Python API, data files and plugin-manager architecture.

### Existing roadmap's outstanding gates (preserved)
- Windows Tauri/Rust compile, React production build and packaged NSIS/MSI build.
- Hardware telemetry and local model benchmark on the target PC.
- Docker isolation, resource enforcement, consent revocation and startup recovery.
- Safe GPU passthrough for approved worker images.
- Windows DPAPI-backed key storage and platform ACLs.
- Inference worker claim/result/stream protocol and node-side inference execution.
- Compatibility-aware model placement, model transfer/cache integrity, backpressure, cancellation and node failure recovery.
- Independent proof strategy; a node-signed receipt alone is not proof that work was honestly performed.
- Signed settlement statements and auditable contributor balances.
- Customer identity, API keys/scopes, quotas/rate limiting, billing, tax/invoices, refunds and chargebacks.
- Public ingress, WAF/rate limits, secret management, backups, monitoring, incident response, abuse controls and penetration testing.

### Existing roadmap's non-negotiable safety gates (preserved)
- Node participation and remote execution are separate opt-ins.
- The node off switch stops new work and terminates its owned active container.
- No global process-name kills; only Atlas-owned processes/containers are stopped.
- Default sandbox workloads have no network or host mounts.
- Use immutable image digests, not `latest` tags.
- Do not describe execution receipts as verified contributions until independent evidence is reviewed.
- No public endpoint, customer API sale or payment collection until public control-plane and commercial safeguards are complete.

This reconciliation is additive: the original root roadmap remains byte-for-byte unchanged and continues to be the detailed operational authority for these gates.
