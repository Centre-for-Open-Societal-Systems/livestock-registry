# Livestock refactor delivery candidate

> **Approval update, 27 October 2026:** The user deferred geographic/custom approval
> configuration. Current defaults follow OpenG2P Farmer: two sequential all/block
> stages, alex.carter then nina.patel. Separate Farmer-reference dependencies
> remain. Earlier geographic descriptions below are deferred design history.
> See [default approval configuration](refactor/DEFAULT_APPROVALS.md).

This review branch composes native extension source `08c4e53b61a1f492e918bca5a0b89e023bfc3a73` with the existing
COSS delivery base `35d21bbe07853324d9493279630fe35600d98c0f` and the changes described here. It does not merge
legacy core/worker implementations into the native refactor source branch.
Working primary checkouts and the local runtime worktrees remain separate.

## Verification boundary

The candidate uses OpenG2P rc.557 extension contracts, registered widgets and
metadata. No platform source, worker replacement or compiled-asset patch is
introduced. Runtime selection must be identical in APIs, ingestion workers and
beat. Dashboard UI/API are independently owned COSS repositories; connector
source retirement does not remove its running release or checkpoints.

Helm is owned by COSS oan-helm. The candidate profile pins dev.14 at
`c08497721ec93eda0b19c2a504255b1ea8a00d8f`, including the chart archive SHA-256.
The three archives were fetched from that immutable URL and their hashes verified
on 26 October 2026. All registry promotion flags remain false.

The Fayda popup collects FIN before navigation. A backing value is not verification:
failed/cancelled flows preserve approved proof, and optional unverified drafts do
not become trusted references. Main forms display FIN read-only. The independent
16-digit FAN field and signed Farmer-reference lookup contract remain separate.

Existing Jenkins agents, credentials, ECR paths and the dashboard tooling remain.
PR and feature-branch validation do not deploy. New Dev is a development
environment: the Jenkins `NEW_DEV_DELIVERY_ACTION` parameter deploys the build
over the existing release (the default), publishes images only, or rebuilds the
registry from an empty database (`fresh-install`: the registry and ID-generator
databases are archived to the New Dev box over the existing backup key, the
release is uninstalled, the databases dropped and the pinned chart installed
again). Staging requires its own preservation rehearsal.

Hosted native image, PostgreSQL replay and browser checks must pass on the exact
candidate commit. Earlier source/build receipts are dated evidence, not proof of
this commit. Real eSignet, signed consent lookup, both approval orders, independent
Kafka-created AWE tasks, imports/ODK, geographic denial, reporting and restored-copy
acceptance remain promotion requirements. A missing supported hook is a blocker.

Local runtime acceptance is serial: Commons + Farmer + Crop, then Commons + Farmer
+ Livestock. No New Dev or staging application/data was changed by preparing this
branch. The current local Docker control failure prevents fresh native containers;
running HTTP applications and source checks have separate evidence.

## New Dev metadata comparison

A fresh authenticated, read-only metadata capture on 26 October 2026 found no
field drift from the 24 October baseline. The curated reference files are in
`reference/new-dev/`. Crop has 482 fields and four forms; Livestock has 316 fields
and one form. Declared fields, identifiers and relationships remain comparison
inputs, rather than inferred runtime acceptance.

The comparator checks registered form bindings and section paths. Crop's reviewed
year/season move and read-only Farmer-name projection are recorded in
`reference/metadata-transitions.json`; it reports raw-path differences explicitly
and accepts only these exact reconciled capabilities. Unreviewed missing paths,
register changes or missing form bindings fail. Livestock retains its raw paths.

Native PostgreSQL checks apply metadata twice and count actual FIN/identity
widgets, including previously duplicated registered sections. They reject missing
or duplicate controls, a second editable FIN input and accidental FAN locking.
Those checks and the current-source lookup/approval suites must run in the native
image on this commit. See [the detailed blockers](refactor/STATUS.json).

## Expanded hosted verification, 26 October

[Run 40270037553](https://github.com/asmitonweb/livestock-registry/actions/runs/40270037553) at `4c7d9e65a9c5df51e965977161f226f18dbab1d1` passed 268 native extension cases with all 72 PostgreSQL executions, repeated metadata and source comparison. The 19 named HTTP cases skipped in that gate then all passed separately with zero skips, covering 13 distinct behaviors and 173 real synthetic-dependency HTTP events. All 54 popup browser assertions passed. This verifies the production clients against saved Postman stand-ins; actual central Farmer/consent and Kafka/AWE engine acceptance remain outstanding. No environment deployment or identity-grant write occurred.
