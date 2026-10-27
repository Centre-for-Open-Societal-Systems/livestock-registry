Current delivery: [26 October candidate and verification boundaries](../refactor-candidate.md) supersede the dated configuration and raw-path claims below. Crop has explicit reviewed season/projection transitions; current chart pins are dev.14.

Current follow-up: [native notification configuration and verification](NOTIFICATION_VERIFICATION.md) supersedes the initial missing-port finding below. Existing deployed semantic/template content and live Kafka/AWE still require acceptance.

# New Dev parity, registered location widgets and source cleanup

Authenticated native New Dev metadata was captured 2026-10-24T18:37:40.160506+00:00.
The effective declared model/metadata comparison is in [new-dev/VERIFICATION.md](new-dev/VERIFICATION.md).
All **316 fields**, **14 sections** and
**1 form IDs** are retained. Domain field names, UUIDs,
relationships and register/history/intake mappings are enumerated in comparison.json.
All declared register field types match. Native history retains its own audit
contract rather than copying last_approved_at, last_approved_by or search_text.

Section paths include string and object-valued widget mappings. All original
paths remain; the existing location section receives an additive registered map
widget. Livestock also receives the native geo-hierarchy control. The map reads
published geography through the authenticated native Master Data catalogue API.
No direct Master Data SQL, Keycloak location attributes, replacement worker,
compiled-asset patch or runtime method reassignment was introduced.

The four source files used from OAN Farmer, their source hashes and differences
are in LOCATION_WIDGET_SOURCE.json. Only the location widget is registered;
Farmer's FIN12 identity widget is not copied. The required onboarding contract
remains Farmer ID plus the user-confirmed UID/FAN16. The provider follows
Farmer's native widget registration pattern against registry rc.557.

Both UI images compile against the same upstream UI source revision. Four real
geometry/cache tests per registry cover holes, islands, reversed TopoJSON arcs,
outside-country rejection and authenticated fetch retry. This is source/build
evidence; it does not certify every translated portal interaction.

Both native psql metadata seed passes have zero SQL errors and identical final
metadata. Stable-ID inserts now tolerate repeated upgrades. Crop's legacy lookup
SQL is preserved in central Master Data reference material instead of being run
against non-native registry database lookup tables. No shared live values were
changed or fabricated. The initial pre-fix rehearsal is retained separately in
new-dev/baseline-20261025; only target-pass-1/2 and seed-rehearsal are current.

| Source/capability | Owning implementation | Decision/evidence |
| --- | --- | --- |
| Core Helm/dependency/reporting/auth | COSS oan-helm core chart 1.0.0-dev.10 | Exact commit ff16b7b7522d3e1e2c5cd0bf1b917ea69d195da9, archive SHA-256 in ci/deploy/oan-chart.json |
| Dashboard release chart | COSS oan-helm addon 0.1.2 | Existing independent release names, IAM settings, human Dashboard Viewer and service charts:read retained |
| Dashboard API/UI application | Existing independent COSS sources | Registry Jenkins still resolves source revisions, builds and pushes its existing ECR images |
| Connector service/UI source | Independently operated integration dependency | Vendored source/build/update paths retired; runtime releases, images and checkpoints untouched |
| Domain fields/forms/history/imports | Native extension metadata/models/services | Existing identifiers retained; full business/import/ODK acceptance still required |
| Location | Registered schema widget + native Master Data | MDM develop.118 source/image provenance in central Helm; seeding disabled |

180 tracked vendored Helm/connector files were retired through Git.
Every original path and Git blob is in RETIRED_SOURCE_MANIFEST.json; the source
commit remains in this branch's published ancestry. 5
ignored local files were hash-verified into the task preservation folder before
cleanup. Automatic approval review rejected their physical deletion, so those
ignored remnants also remain locally. They contain no tracked build entry point
and are not referenced by CI. No user branch, stash or primary checkout was reset.

CI now verifies/downloads immutable central archives and public values without
local-chart fallback, version stamping or dependency resolution. Deployment
profiles remain promotionReady=false; all dev/staging mutation entry points
stop before contacting an environment. Existing jobs, agents, credentials,
ECR paths, complete saved release values and preservation guards remain.
Staging requires separate acceptance and cannot inherit dev authorization.

The old method-patch enrichment log guard is replaced by validation of the
registered extension's COSS_FARMER_* contract and required read-only Secret/files
on staff API, worker and beat. Six tests reject missing configuration, wrong
namespace, query-secret URLs, private ConfigMap data and missing Secret keys.

Live Farmer UID16/provenance/geography response compatibility, Kafka-created AWE
tasks, independent target decisions, import/ODK/attachments, full domain rules,
all translated screens, authenticated dashboard behavior and restored-copy
preservation remain promotion requirements. Live Crop's additional
FARMER_REFERENCE_CHANGED_V1 configuration/template is captured in pipeline-metadata
and still needs a verified native configuration port; it must not be treated as
already delivered by the notification enricher. The generic Livestock
MY_DATA_MODEL example is intentionally retired.

No live registry records, documents, approvals, grants, environment settings,
connector checkpoints or deployments were changed by this work.

Hosted Linux [Helm CI](https://github.com/Centre-for-Open-Societal-Systems/oan-helm/actions/runs/40128364896) passes for the pinned dev.10 correction: 20 unit tests, six core packages/index and three independent dashboard charts. Published dev.9 bytes were retained after CI caught a Windows-only source newline seal; dev.10 fixes the source and rejects that condition before packaging. Registry Jenkins runtime status is unverified; its syntax and focused commands were checked locally.

Verified central cache transport preserves Crop deploy-node isolation: build-agent prefetch/stash plus deploy-time checksum checks, including rejection of corrupt cached archives without a network fallback. Ten chart-client tests and six configuration guard tests pass, plus the platform pin and four geometry checks.
