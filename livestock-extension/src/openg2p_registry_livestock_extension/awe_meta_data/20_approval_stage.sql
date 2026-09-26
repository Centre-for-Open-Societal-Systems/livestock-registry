-- Approval workflow stages.
--
-- registry.change_request.livestock (editing an already-VERIFIED Livestock
-- record) stays on ONE flat stage -- out of scope for the hierarchical
-- chain below; see [[livestock-4-level-approval-chain]] plan.
--
-- registry.intake_form.livestock (a Field Officer's new Livestock intake
-- submission) gets the REAL Kebele -> Woreda -> Zone -> Region ladder from
-- g2p_livestock_registry/models/livestock_registry.py, one stage per level,
-- stage_order 1-4. Each stage's approver is resolved per-record by the http
-- approver-resolver endpoint (30_approver_rule.sql), not a fixed user, so
-- only the actual Kebele/Woreda/Zone/Region Approver responsible for THIS
-- record's own location can act on it.
--
-- mode 'all'      — every resolved approver on the stage must approve.
-- on_empty 'block'— if no approver resolves (e.g. nobody is assigned to
--                   that specific kebele yet), the request stalls rather
--                   than auto-approving. Safer default for an approval gate.
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
    ('71e2ee0d-0887-5e70-877e-1ca1998ee0e6', '907339cb-744e-5fe9-9805-df7416d81dbe', 1, 'Kebele Approval', 'all', NULL, NULL, NULL, 'null', 'block', NULL, 'null', NOW(), NOW()),
    ('9c1f2a3b-4d5e-5f60-8a71-b2c3d4e5f601', '907339cb-744e-5fe9-9805-df7416d81dbe', 2, 'Woreda Approval', 'all', NULL, NULL, NULL, 'null', 'block', NULL, 'null', NOW(), NOW()),
    ('9c1f2a3b-4d5e-5f60-8a71-b2c3d4e5f602', '907339cb-744e-5fe9-9805-df7416d81dbe', 3, 'Zone Approval', 'all', NULL, NULL, NULL, 'null', 'block', NULL, 'null', NOW(), NOW()),
    ('9c1f2a3b-4d5e-5f60-8a71-b2c3d4e5f603', '907339cb-744e-5fe9-9805-df7416d81dbe', 4, 'Region Approval', 'all', NULL, NULL, NULL, 'null', 'block', NULL, 'null', NOW(), NOW())
ON CONFLICT ("id") DO NOTHING;
