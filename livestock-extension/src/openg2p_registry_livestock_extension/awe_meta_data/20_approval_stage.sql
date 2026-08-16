-- Basic approval workflow: ONE stage per policy.
--
-- The full Kebele -> Woreda -> Zone -> Region ladder from
-- g2p_livestock_registry/models/livestock_registry.py is the eventual target,
-- but it needs four real approver identities to be usable. This single stage
-- keeps the workflow exercisable end to end with one operator; add stages 2-4
-- (stage_order 2,3,4 against the same policy_id) when those identities exist.
--
-- mode 'all'      — every resolved approver on the stage must approve.
-- on_empty 'block'— if no approver resolves, the request stalls rather than
--                   auto-approving. Safer default for an approval gate.
INSERT INTO "public"."approval_stage" (
    "id",
    "policy_id",
    "stage_order",
    "name",
    "mode",
    "mode_value",
    "sla_hours",
    "parallel_group",
    "skip_if",
    "on_empty",
    "on_breach",
    "escalation_rules_json",
    "created_at",
    "updated_at"
) VALUES
    ('6a963145-a31a-5ee7-a59c-87acf62b1686', 'b2477cdc-7db9-5f2a-bda9-828a713c5b4d', 1, 'Registry Admin Approval', 'all', NULL, NULL, NULL, 'null', 'block', NULL, 'null', NOW(), NOW()),
    ('71e2ee0d-0887-5e70-877e-1ca1998ee0e6', '907339cb-744e-5fe9-9805-df7416d81dbe', 1, 'Registry Admin Approval', 'all', NULL, NULL, NULL, 'null', 'block', NULL, 'null', NOW(), NOW())
ON CONFLICT ("id") DO NOTHING;
