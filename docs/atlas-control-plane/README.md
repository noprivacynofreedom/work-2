# Atlas Node Control Plane — merged development service

The control plane now lives in the Atlas repository at `services/atlas-control-plane/`. It is a separate Rust service within the same project, not a second desktop app and not a replacement for the existing local gateway.

## How it fits Atlas

- Atlas Desktop remains the user-facing application.
- `atlas-rust-desktop/src-tauri/src/atlas_node.rs` remains the trusted local node supervisor and client.
- The existing Atlas Chat API and llama-swap continue to run locally on their existing ports.
- `services/atlas-control-plane/` provides node registration, signed heartbeat intake, scheduler-signed container workload dispatch, receipt intake and operator review APIs.
- PostgreSQL stores node identities, challenges, replay fingerprints, workloads, inference requests and contribution receipts.

The control plane binds to `127.0.0.1:8181` by default. Docker Compose also publishes only to loopback. Do not expose it publicly yet.

## Current capability truth

| Capability | State |
|---|---|
| Node challenge/registration | Implemented in control-plane source; live deployment not tested |
| Signed heartbeat and replay rejection | Implemented in source; live deployment not tested |
| Scheduler-signed immutable-image workloads | Implemented in source; node-side Docker execution exists; Windows runtime not tested |
| Receipt signature intake | Implemented; verifies registered-node signature and assigned workload |
| Independent compute verification | Manual operator review hook only; no cryptographic proof-of-compute |
| Contribution balance | Verified units are recorded; no wallet or settlement service |
| Distributed inference | Request queue endpoint exists; node inference worker, scheduling and response streaming remain incomplete |
| GPU container execution | Not implemented; current Docker workload path is CPU/memory constrained and does not pass through GPU devices |
| Customer API keys, subscriptions and payments | Not implemented |

## Launch checklist

1. Install Rust stable and Docker Desktop/Engine.
2. Provision PostgreSQL 16 and apply migrations (the service applies them at startup).
3. Generate a scheduler Ed25519 key and pin its public key on nodes after out-of-band verification.
4. Set `DATABASE_URL`, `ATLAS_ADMIN_KEY`, and `ATLAS_SCHEDULER_PKCS8_HEX` using a secret manager or protected environment file.
5. Start on localhost and test registration/heartbeat before adding any workload.
6. Add an exact immutable image digest to the node allowlist and separately enable remote workload consent.
7. Test disable/cancel, expiry, duplicate/replay rejection, node revocation and server restart recovery.
8. Only after independent security review, design TLS/public deployment and customer-facing auth.

See `services/atlas-control-plane/README.md` for exact commands and routes.
