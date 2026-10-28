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
