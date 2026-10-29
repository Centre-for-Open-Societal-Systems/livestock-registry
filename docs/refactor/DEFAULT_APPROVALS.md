# OpenG2P default approval configuration

The native AWE integration is used, without registering the geographic service
(geographic approval was deferred on 27 October 2026). The policy pattern is the
upstream Farmer 1.2 example under this registry's own `.default` keys: two
sequential stages, `on_empty=block`. Since 28 October 2026 each stage completes
on one decision (`mode=any-n`, `mode_value=1`) from either the named officer or
`admin`: Stage 1 Officers lists `alex.carter` and `admin`, Stage 2 Officers
lists `nina.patel` and `admin`. Self/repeat approval restrictions stay `false`,
so `admin` may decide both stages. The Farmer registry seeds the same shape, so
every registry approves the same way. These are example reviewer IDs; this
change creates no users or IAM grants.

Databases seeded before 28 October hold the six `.default` stages with
`mode=all`. `50_either_officer_or_admin.sql` moves exactly those stages, by id,
to `any-n`/1 in place; the insert-only rule file adds the `admin` rules. Policy
keys, stage ids, rule ids and the register bindings do not change, so open
tasks keep their policy and the Farmer-reference receiver keeps one binding.

Domain intake and Farmer-reference change requests remain separate. Identity
verification, durable onboarding, target approval, stale-update checks and
activation dependencies are unchanged; this does not add automatic approval.
Reference workflow delivery uses the effective native policy without resolving
geographic candidates unless a policy explicitly requests geographic context.

New `.default` policy keys isolate these definitions from old geographic policy
versions. Only the extension-owned future-request bindings are reset, retaining
their IDs. Existing policies, stages, tasks, decisions, assignments and IAM/DP
grants are neither edited nor deleted. Existing open tasks retain their policy.
The former geographic seed/administration examples are retained under
`configuration/deferred-geographic/` and are not included in the seed image.

Farmer itself already inherits the native two-stage defaults. No upstream
OpenG2P source or chart dependency was changed. Chart/seed promotion gates are
separate and remain closed; this source change does not claim a live reset.

Restored databases also contain competing legacy bindings. The native resolver
uses a single result per scope, so these must be reconciled during the reset.
The registered extension migration creates `coss_approval_binding_archive`.
Seeding snapshots original configurations before edits, resets future routing,
and retains the canonical binding ID for duplicate scopes. Retired metadata IDs
and complete row values remain in the archive for restoration through native
administration. Existing AWE policy/task rows are unchanged. No geographic IAM
or data-policy assignment is removed.

## No approval outside a task

Core also exposes two staff calls that apply a change on one user's say-so,
without an approval task: `/intake-form-data/approve_intake_form_submission`
(`intakeSubmission:approve`, held by Intake Validator and Technical
Administrator) and `/change-requests/approve_change_request` plus
`/change-requests/approve_change_request_for_core_data`
(`changeRequest:approve`, held by Technical Administrator). The role catalog
is registered by the platform chart and is not changed here, so
`direct_approval.py` refuses both service calls for every caller, `admin`
included. Decisions made in an approval task are unaffected: the workflow
engine's signed decision reaches `approve_submission_with_session` and
`approve_change_request_from_awe_webhook`, which the guard does not touch.
`reject` calls and the verification calls stay available.

## Whether a Farmer-reference change needs review is a policy setting

Whether an ADD or UPDATE of a Farmer reference waits for people is decided by the
approval policy bound to the Farmer section, not by code. The OpenG2P mechanism is
used: a stage's `skip_if` is a JSONLogic rule over the request context, and when
every stage is skipped the workflow engine approves the request itself
(`all_stages_skipped`).

**Context.** With every Farmer-reference request the registry sends two keys, which
the binding's `context_field_names` (`["change_type", "source"]`) copies into the
request context:

| Key | Value |
| --- | --- |
| `change_type` | `ADD` or `UPDATE`, the request's action |
| `source` | `farmer-registry` only for a change proven by the signed Farmer lookup of the configured source system (the ledger holds the response digest and the reference's `source_system` equals `COSS_FARMER_SOURCE_ID`); otherwise `unverified` |

Every Farmer-reference request is created from a verified lookup (ADD from the signed
lookup at intake, UPDATE only from the Kafka notification that passes the
source-partner check and a fresh signed lookup), so `source` is `farmer-registry`
whenever `COSS_FARMER_SOURCE_ID` is set on the process that delivers workflows. If it
is missing, `source` is `unverified` and nothing is ever skipped.

**Shipped setting: review stays on.** The binding in
`meta_data/register-metadata/zzz_farmer_reference_awe.sql` names the `.default`
policy: two human stages for every ADD and UPDATE.

**To turn off the second approval for verified UPDATEs**, change one value: the
`policy_key` of that binding from

```
registry.change_request.<registry>-farmer.default
```

to

```
registry.change_request.<registry>-farmer.verified-update-skips-review
```

(`<registry>` is `cropsown` or `livestock`) and seed. The other policy is seeded by
`awe_meta_data/60_verified_update_skips_review.sql` and is inert until a binding
names it. It has the same two stages and approvers; each stage carries

```json
{"and": [{"==": [{"var": "change_type"}, "UPDATE"]}, {"==": [{"var": "source"}, "farmer-registry"]}]}
```

so a verified UPDATE skips both stages and is approved without a task, while an ADD,
or anything unverified, still goes to two people. The same switch can be made at
runtime in AWE Policy Configuration (the staff API's `update_awe_policy_configuration`
on the Farmer section binding): set its policy key to the value above and keep
`context_field_names` as `["change_type", "source"]`. The next seed puts the value in
the seed file back, so make the lasting change in the seed. To turn review back on,
restore the `.default` key.

**What stays the same.** The skipped request is approved by AWE with the usual
`request_approved` callback, which reaches `approve_change_request_from_awe_webhook`
with the request's `awe_request_id`, so `guard_farmer_approval` accepts it; a direct
staff approval is still refused. Requests already in review keep the policy they
started with. An active policy version cannot be edited, so a different rule needs a
new policy version or key (retire a policy by explicit id, never with `NOT IN`).
`zzz_farmer_reference_awe.sql` owns this binding, so the default-binding reset in
`zzzzzzzzz_default_binding_reset.sql` excludes it. The policy definitions are
mirrored in `configuration/farmer-reference-awe-policy.json` (shipped) and
`configuration/farmer-reference-verified-update-skips-review.json` (optional).
