# Atlas Control Plane v0.1.0 — test results

Executed in the available build environment:

| Test | Result |
|---|---|
| Desktop registration route contract | PASS |
| Signed workload route contract | PASS |
| Timestamp and replay guard source contract | PASS |
| Immutable image and scheduler signature contract | PASS |
| Owner consent and heartbeat freshness guard | PASS |
| Receipts default to non-verified and zero billable units | PASS |
| Network inference consent propagation | PASS |
| Loopback-only default binding | PASS |
| Customer billing/payments not falsely represented | PASS |

Command:

```sh
python services/atlas-control-plane/tests/test_contract.py
```

Result: **9 passed, 0 failed**.

Also executed across the existing project and control-plane contract suite:

```sh
python -m pytest -q tests services/atlas-control-plane/tests
python -m compileall -q .
node --check validation-tests/test_chat_queue.js
node --check atlas-rust-desktop/validation-tests/test_chat_queue.js
node --check atlas-rust-desktop/validation-tests/test_atomic_chats.js
```

Result: **15 pytest tests passed**; Python compileall and all three Node syntax checks passed.

Not run: Cargo check/test, Tauri build, TypeScript/Vite production build, PostgreSQL integration tests, Docker sandbox tests, Windows GPU tests or live node registration. Cargo is unavailable in the authoring environment; `npm ci --offline` could not resolve uncached Vite package files. These are build/runtime gates, not passed checks.
