# Atlas — integrated roadmap and release gates

## Architecture decision

Keep Atlas as one product and repository with separately deployable services. Do not merge the control plane into the desktop process. The control plane is integrated into the Atlas source tree, while running as its own Rust service. This preserves the desktop lifecycle boundary and lets the network service scale independently.

- React + TypeScript: Desktop presentation and interaction.
- Rust/Tauri: Desktop lifecycle, node supervisor, local resource limits, signing, Docker process ownership and native APIs.
- Python: existing Atlas Chat API/MCP compatibility and model tooling; retain where it preserves working integrations.
- Rust/Axum: network control plane.
- PostgreSQL: network identities, workload queue, node heartbeat state and contribution receipts.
- llama-swap/Ollama adapters: local inference provider compatibility.

## Completed in this delivery

- Added Rust/Axum control-plane service under `services/atlas-control-plane`.
- Added PostgreSQL schema/migrations, challenge-response Ed25519 registration, signed node request verification, replay fingerprints, heartbeats, node eligibility checks, scheduler-signed workload envelopes, receipt signature validation, operator node revocation and manual contribution review.
- Added localhost-only Docker Compose deployment and key-generation binary.
- Connected desktop heartbeat consent reporting to the server contract.
- Improved local model discovery and benchmarking to support both Ollama `/api/*` and OpenAI-compatible `/v1/*` endpoints, defaulting new profiles to the existing llama-swap port 8080.
- Improved Docker workload cancellation by recording the container ID file and stopping the container itself before terminating its owned CLI process.
- Preserved the existing chat iframe, Python API, data files and plugin-manager architecture.

## Still required before Atlas can be called complete

### Desktop and node
- Compile Tauri/Rust on Windows and fix any platform-specific compiler/runtime issues.
- Run the actual React production build and packaged NSIS/MSI build.
- Verify RX 9070 XT telemetry and llama-swap model benchmark on the user's PC.
- Verify Docker Desktop isolation, CPU/RAM enforcement, stop-on-consent-revocation and startup recovery.
- Implement GPU passthrough safely for approved worker images.
- Replace raw private-key file storage with Windows DPAPI-backed protected storage and platform ACLs.

### Network and distributed inference
- Add inference worker claim/result/stream protocol and node-side inference execution.
- Add compatibility-aware model placement and scheduling using GPU VRAM, RAM, model quantization, context length, throughput, bandwidth and node health.
- Add model transfer/cache integrity, backpressure, cancellation and node failure recovery.
- Add independent proof/verification strategy; node-signed receipts alone do not prove work was honestly performed.
- Add signed settlement statements and auditable contributor balances.

### Commercial production
- Customer identity, API keys, scopes, quotas and rate limiting.
- Subscription and payment provider integration, tax/invoice handling, refunds and chargebacks.
- Contributor payout/KYC compliance only when the business/legal model is defined.
- Public TLS ingress, WAF/rate limits, secret manager, backups, monitoring, incident response, abuse controls and penetration test.

## Non-negotiable safety gates

- Node participation and remote execution are separate opt-ins.
- A node's off switch stops accepting new work and terminates its owned active container.
- No global process-name kills; only processes/containers created by Atlas are stopped.
- No network or host mounts in default sandbox workloads.
- Immutable image digests only; no `latest` tags.
- Never call an execution receipt a verified contribution until independent evidence has been reviewed.
- No public endpoint, customer API sale or payment collection until the public control plane and commercial safeguards are complete.
