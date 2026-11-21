# Atlas Network Control Plane v0.1.0

Rust/Axum + PostgreSQL service for Atlas Node registration, signed heartbeats, scheduler-signed container workload delivery, receipt intake, operator node revocation and manual contribution review.

## Current release boundaries

- Node registration is challenge-response Ed25519 proof-of-possession. The node ID is SHA-256(public key).
- Node API calls use bearer credentials stored as SHA-256 hashes server-side, plus Ed25519 request signatures over `timestamp.method.path.sha256(raw_body)`.
- Request timestamps have a 90-second clock-skew limit and request fingerprints are unique to reject replay.
- Workloads are queued only by the operator endpoint, use immutable image digests, and are signed by the scheduler key. The node independently checks owner opt-in, image allowlist, expiry, signature and local CPU/RAM ceilings before Docker execution.
- Node receipts are verified as authentic statements from the registered node and bound to an assigned workload. That is **not proof of physical computation**. `independently_verified` remains false and `billable_units` remains zero until an operator records an independent evidence review.
- The inference endpoint accepts requests into a queue but this release does not dispatch inference jobs to model workers or stream their output. Do not advertise distributed inference as live.
- There is no customer auth/API key, subscription, payment, payout, or commercial settlement implementation in this release.

## Local development

1. Install Rust stable and PostgreSQL 16.
2. Create a database and set `DATABASE_URL`.
3. Generate the scheduler signing key:

   ```powershell
   cargo run --bin generate-scheduler-key
   ```

   Keep `ATLAS_SCHEDULER_PKCS8_HEX` private. Copy only `ATLAS_SCHEDULER_PUBLIC_KEY_HEX` into the Atlas Node dashboard's trusted scheduler key field. Verify that public key out-of-band before trusting it.
4. Set `ATLAS_ADMIN_KEY` to a random secret of at least 32 characters.
5. Set `ATLAS_BIND=127.0.0.1:8181` for local development.
6. Run `cargo run`. Migrations run automatically.
7. Health check: `GET http://127.0.0.1:8181/healthz`.

## Docker Compose

Copy `.env.example` to `.env`, set `ATLAS_DB_PASSWORD`, `ATLAS_ADMIN_KEY` and `ATLAS_SCHEDULER_PKCS8_HEX`, then run:

```sh
docker compose up --build -d
```

The compose port is bound to localhost. For remote production use, place the service behind a TLS reverse proxy, add rate limiting/WAF, managed PostgreSQL backups, secret management, alerting, and an operational node revocation process. Never expose PostgreSQL.

## API contract

### Node
- `POST /v1/nodes/challenge` `{node_id, public_key_hex}`
- `POST /v1/nodes/register` `{node_id, public_key_hex, challenge, signature_hex}`
- `POST /v1/nodes/heartbeat` signed node request
- `POST /v1/workloads/claim` signed node request; returns 204 when empty
- `POST /v1/workloads/complete` signed node request containing a node-signed receipt
- `POST /v1/inference` signed node request; queues an inference request only (no worker dispatch yet)

Signed node request headers: `Authorization: Bearer <node_token>`, `x-atlas-node-id`, `x-atlas-timestamp`, `x-atlas-signature`. Signature message: `<unix_seconds>.POST.<exact_path>.<sha256(raw_body)>`.

### Operator (all require `x-atlas-admin-key`)
- `POST /v1/operator/workloads` queue a container workload `{image, command, max_memory_mb, max_cpu_percent, ttl_seconds?}`
- `GET /v1/operator/workloads/:id` inspect workload state
- `GET /v1/operator/nodes` list node health and consent
- `POST /v1/operator/nodes/:node_id/revoke` revoke a node credential
- `GET /v1/operator/contributions` list signed receipts
- `POST /v1/operator/contributions/:receipt_id/verify` `{evidence_reference, billable_units}` after a human reviewer independently validates evidence. This is an operator attestation, not an automated proof-of-compute protocol.

### Public
- `GET /healthz`
- `GET /v1/network/status`
- `GET /v1/scheduler/public-key` (display only; verify the key fingerprint out-of-band before pinning it)

## Security notes

The API defaults to localhost. It does not implement public customer access, account management, payments, proof-of-work, trusted execution environments, or privacy-preserving distributed model execution. Do not enable public access or paid API traffic until those controls are built and independently security-reviewed.
