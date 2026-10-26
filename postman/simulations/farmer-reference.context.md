# Farmer reference simulation

Created 2026-10-24 from official DCI, native AWE helper and standard Keycloak
Admin contracts. The synthetic record contract is a receiving requirement.

## Purpose

`farmer-reference.sim.yaml` and `../mocks/farmer-reference/default.js` exercise
the signed lookup client and native IAM/AWE clients without live credentials.

## Execution

Run `python ci/refactor/verify_onboarding.py cropsown --build` (or `livestock`)
from its registry checkout. The runner starts Postman on port 49182, waits for
`listening`, executes the production clients, captures safe counts and stops
the process tree. Docker Desktop must reach the host via `host.docker.internal`.

## Assumptions

- 2026-10-24: Keys are generated in memory. A stand-in verifies signatures and
  returns a required UID16 profile; it cannot prove deployed Farmer/consent
  support. The inspected Farmer source has a different identity contract.
- 2026-10-24: The AWE stand-in treats the native `cr-<id>` idempotency header as
  one request even after a lost response. The real engine, webhook signatures,
  realm authorization and Kafka delivery still need live acceptance.
- 2026-10-24: The native HTTP test uses synthetic functional roles and finite
  standard DP policies. Only OAuth POST and IAM GET are modeled; identity
  writes and unrelated endpoints return 501.

## Observations

<!-- begin:observations -->
2026-10-24: The initial signed lookup run served the Farmer member, including
successful signatures and non-success responses. The native IAM/AWE extension
is verified by the runner's current `native-cr-lifecycle` evidence.
<!-- end:observations -->

## What didn't work

- 2026-10-24: Reading the raw Node request stream with `interceptRequests: true`
  duplicated body processing and returned 400. Use the provided `req.body`.
- 2026-10-24: Native `AweHelper` retains its initialization-time base URL;
  changing settings afterwards left the HTTP test connecting to localhost.
  Configure the documented AWE environment values before initializing the app.

## Notification follow-up, 25 October

The native receiving-service case now uses its actual configured file-based
lookup client over HTTP to this dependency, then creates a native pending CR and
durable outbox. It checks approved local values stay unchanged. Source UID
correction is pinned to the same immutable source person and remains locally
approved; unsigned notification values do not authorize it.

Native tests run in separate core/workflow/notification groups within the
original command deadlines. The normal HTTP fixture has a two-second allowance;
only the deliberate hanging endpoint uses 100ms. Production timeout/retry
settings are unchanged. The runner labels/names its disposable containers and
cleans them before its private database/network, including on timeout. Failure
and timeout evidence explicitly remains verification_complete=false.
