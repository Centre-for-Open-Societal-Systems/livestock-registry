# OpenG2P default approval configuration

The user deferred geographic approval configuration on 27 October 2026.
The native AWE integration is used, without registering the geographic service.
The policy pattern is the upstream Farmer 1.2 example: Stage 1 Officers uses
`alex.carter`, Stage 2 Officers uses `nina.patel`, both `mode=all`, `on_empty=block`.
Self/repeat approval restrictions match upstream defaults (`false`). These are
example default reviewer IDs; this change does not create users or IAM grants.
Configure reviewers later through standard AWE administration.

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
