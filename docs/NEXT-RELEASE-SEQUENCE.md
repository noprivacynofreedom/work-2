# Atlas Desktop — next release sequence

**Status:** planning, 9 November 2026. This document does not claim release readiness.

## Release rule

Atlas is pre-release. Reliability, data preservation, observable behavior, and target-Windows evidence take priority over adding feature count. Keep Atlas Desktop separate from Atlas Online. Keep the Python chat backend as a compatibility layer. Do not change model defaults or the desktop lifecycle without measurements and an owner-approved release window.

## Work map

| Order | Scope | Owner / dependency | Exit evidence |
|---|---|---|---|
| 1 | Finish the active Windows package and install validation. Include the latest chat UI source in the packaged resources. | Release validation chat owns the current package. No other session edits bundled UI during this step. | Artifact version and SHA-256; package/build logs; installed executable matches the intended artifact; launch and rollback results. |
| 2 | Verify local model discovery, selection, cold load, warm first token, response completion, and recovery after a failed request. | Model-loading chat; run after the package is installed. | Per-model pass/fail, measured load and first-token times, exact prompt outcome, and server logs. A timeout or empty response is a failure. |
| 3 | Fix the user-reported queue and conversation-switching blockers. Preserve active generation when opening another conversation; advance remaining queue items after removal. Also fix bot drag-to-reorder and prevent bot names from being selected. | Next source iteration after the package freeze. | Targeted regressions plus Windows UI checks with an active request, multiple queued messages, and repeated bot drag/drop. Preserve stored chats and queue state. |
| 4 | Verify the “open this conversation” route to Operations and selected-conversation diagnostics. | After item 1, using the installed package. | Chat-to-Operations route test, correct conversation identity, return to Chat, and no loss of in-flight work. |
| 5 | Add the planned selected-task detail view: created artifacts, full paths, evidence, workspace, and a “View live feed” action. Label snapshots as snapshots; do not imply live streaming until a stream exists. | Separate Operations feature after items 3–4 pass. Keep the existing visual design. | Keyboard and mouse interaction checks, empty/error states, path display, and evidence that the feed source is live or clearly marked as a snapshot. |
| 6 | Capture a reproducible local inference baseline before tuning CPU/GPU, KV cache, context, or model-residency defaults. | Model-performance release plan; do not overlap its benchmark work. | Raw logs/CSV, machine and model identity, cold/warm timings, prompt/decode rates, peak CPU/RAM/VRAM, median/p95, and quality checks. |

## Release gates

Do not call the release accepted until all applicable gates pass:

- Chat send, stop, failed-request recovery, queue edit/hold/remove/reorder/advance, and conversation switching.
- Model discovery error and timeout states, model selection, cold load, warm response, and correct loaded status.
- Plugin and MCP status, refresh, error handling, and no duplicate in-flight discovery.
- Atlas Node and Operations navigation and primary controls.
- Data/settings preservation across package install and rollback.
- Windows package launch, owned-process shutdown, and logs tied to the packaged version.
- CPU/GPU performance claims supported by the benchmark protocol in `MODEL-PERFORMANCE-RELEASE-PLAN.md`.

## Current known failures and limits

- A prior real-model smoke request returned an empty answer after 302 seconds. This is a failed smoke test, not a model pass.
- The latest chat UI source passes inline JavaScript syntax, six focused UI safety contracts, both queue suites, and the React TypeScript check. It did not receive live UI interaction or end-to-end verification. The packaged HTML mirror matches the source by SHA-256.
- An earlier NSIS dependency verification stopped on a blocked network download. The release owner now reports the full validation pipeline passed and a fresh isolated candidate build is underway. The package and installed application remain unverified. Keep release build inputs frozen until that owner reports its result.
- The model-performance plan found that the existing benchmark can combine load, prompt processing, and generation time. Do not treat its current tokens-per-second display as decode speed.
- The model reliability owner reports the focused benchmark regression suite passes and the OpenAI fallback now uses its own timer. No local inference endpoint or usable GPU telemetry was available for real measurements.
- Retrieval/workflow owner reports 6/6 focused tests and a synthetic 800-file, 6,400-chunk retrieval result of 63.54 ms baseline versus 2.42 ms optimized. This synthetic warm-query result is not a production benchmark. Their broader suite passed 66/69; two tests failed on denied localhost sockets and one 404 assertion remains unresolved.
- The redacted per-chat activity endpoint and its UI consumer are implemented in source, but the endpoint and live panel have not been tested together.
- The user reported bot drag-to-reorder does not work and bot names remain selectable. Release owner queued these for the next source update. Source review found that only each card accepts `dragover`; dropping in the 8 px gaps or blank list area is rejected because `#bots` has no drop handler. Live interaction still needs to confirm whether that matches the user's drag path. Do not change the current package inputs during packaging.
- Node registration, sandbox enforcement, GPU passthrough, and network workload execution remain separately gated roadmap work. They are outside this desktop release sequence.

## Coordination boundaries

- Release chat owns package and install work.
- Model-loading chat owns model discovery and end-to-end chat checks.
- Model-performance work owns the benchmark protocol and resource measurements.
- The next implementation chat should take one reliability blocker at a time after the release owner clears the shared checkout.
- Do not run a second build or test suite while the release owner is active.

## User-authorized feature follow-up

Implement these after the current package and core reliability gates. Keep the current visual style and use small, reviewable changes.

1. **Workflow presets:** save and rerun Team Run bot selections, round count, and task instructions. Add safe stop and retry at step boundaries without losing finished output.
2. **Retrieval visibility:** show retrieval mode, source references, and an optional-index failure in chat. Keep ordinary chat working when retrieval is unavailable.
3. **Image capability check:** detect image attachments and check explicit model capability metadata before sending. Explain unknown/text-only support and preserve text-only fallback.
4. **Voice settings:** let users choose recognition language and listening mode. Keep dictation insert-only, default it off, disclose that browser recognition may use an external service, and handle permission/API errors.

5. **Activity companion:** source implementation is present. The compact panel uses the redacted per-chat `/api/ops/conversations/{id}/activity?after=&limit=` projection, filters tool/task/error events, and avoids event messages and details. Live API/UI verification remains open. Add bot labels or trace-linked detail only through a separately reviewed safe projection.

The image capability control is explicit per bot (`unknown`, `vision`, or `text-only`); it does not auto-detect model capabilities. Unknown asks before sending images, and text-only blocks them. Voice settings and external-service disclosure are in source; live permission and recognition behavior remain unverified. Workflow presets and retrieval source visibility remain follow-up items.

Validate each feature separately before including it in a package. Do not claim image understanding or local speech processing without runtime evidence.
