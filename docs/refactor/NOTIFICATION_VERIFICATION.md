# Native Farmer notification port verification

The existing event, Kafka/WebSub topic, Crop metadata IDs and identity envelope
are preserved. Both receivers now carry native metadata and an identity-only
template. The registered enricher validates the event; the CR extension checks
the referenced local identity and source partner, then uses signed current-source
lookup. Source-approved UID correction is pinned to the same immutable source
person and still needs local approval. Notification demographic values are never
applied. New ADD approval derives the native functional identifier for later
classification; existing identifiers are untouched.

All 79 receiving/reference tests pass per registry: 25 contract, 8 projection,
5 notification contract, 14 PostgreSQL concurrency, 9 native CR, 3 real HTTP
IAM/AWE, 8 native notification lifecycle and 7 signed HTTP lookup cases. One new
receiving case reads the real configured lookup files, signs a real HTTP request
to the Postman dependency, and creates a native pending CR/outbox while keeping
approved local values. Duplicate updates, mismatched pairs/partners, unknown
Farmers, source failure and approved UID correction are covered.

Four production images build, and installed-wheel service registration and the
seed preservation gate pass. Current production source hashes match that run.
The native installed worker helpers pass two-pass classification, unknown-ADD
rejection, enricher selection, template environment, UPDATE validation and CR
payload construction using actual seeded metadata. Repeated native seeds are
identical and log zero SQL errors. The notification model retains a null
response-template pointer so native connector correlation-ID acknowledgement
is preserved. Four Crop API detail/model comparisons independently match.

The 300ms artificial timeout is isolated to the intended timeout fixture; normal
signed HTTP cases use a two-second test allowance. Production timeouts were not
changed. Larger native groups were split within the existing per-command bounds;
no production retries were increased. A failed/timed-out verification cannot
mark itself complete, and owned containers are removed before its test network.

Existing Jenkins jobs now run the native fresh/repeated metadata and notification
mapping probe and retain its artifacts. Groovy parse checks pass; Jenkins runtime
execution is not certified by these local checks. Central Helm dev.10 and its
passing hosted CI remain unchanged.

Live semantic-pattern detail and stored-template readback returned application
errors and remain unverified. Existing rows and document pointers are not
overwritten by seeds. Real Kafka delivery, actual target AWE engine tasks and
independent decisions/recovery, authoritative UID16 source compatibility and
restored-data preservation remain promotion requirements. Existing delivery
constraints/indexes, identities, grants, open tasks and connector checkpoints
must be retained and checked during that rehearsal. No subscription, connector,
checkpoint, live registry record or deployed environment was changed.

Exact evidence: ONBOARDING_VERIFICATION.json, NATIVE_NOTIFICATION_PIPELINE.json,
NOTIFICATION_CONFIG_VERIFICATION.json and DELIVERY_VERIFICATION.json.
