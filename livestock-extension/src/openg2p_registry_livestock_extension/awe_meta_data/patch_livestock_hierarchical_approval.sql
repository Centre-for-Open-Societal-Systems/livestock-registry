-- Patch for an environment already seeded with the OLD single-stage
-- registry.intake_form.livestock policy (20_approval_stage.sql / 30_approver_
-- rule.sql's INSERT..ON CONFLICT DO NOTHING will not update an existing
-- row). Brings it up to the real Kebele -> Woreda -> Zone -> Region
-- hierarchical chain described there. Safe to re-run (UPDATE + INSERT ON
-- CONFLICT DO NOTHING throughout). See [[livestock-4-level-approval-chain]]
-- plan for the full design.
--
-- Runs against the "awe" database.
UPDATE "public"."approval_stage"
SET "name" = 'Kebele Approval'
WHERE "id" = '71e2ee0d-0887-5e70-877e-1ca1998ee0e6';

INSERT INTO "public"."approval_stage" (
    "id", "policy_id", "stage_order", "name", "mode", "mode_value",
    "sla_hours", "parallel_group", "skip_if", "on_empty", "on_breach",
    "escalation_rules_json", "created_at", "updated_at"
) VALUES
    ('9c1f2a3b-4d5e-5f60-8a71-b2c3d4e5f601', '907339cb-744e-5fe9-9805-df7416d81dbe', 2, 'Woreda Approval', 'all', NULL, NULL, NULL, 'null', 'block', NULL, 'null', NOW(), NOW()),
    ('9c1f2a3b-4d5e-5f60-8a71-b2c3d4e5f602', '907339cb-744e-5fe9-9805-df7416d81dbe', 3, 'Zone Approval', 'all', NULL, NULL, NULL, 'null', 'block', NULL, 'null', NOW(), NOW()),
    ('9c1f2a3b-4d5e-5f60-8a71-b2c3d4e5f603', '907339cb-744e-5fe9-9805-df7416d81dbe', 4, 'Region Approval', 'all', NULL, NULL, NULL, 'null', 'block', NULL, 'null', NOW(), NOW())
ON CONFLICT ("id") DO NOTHING;

UPDATE "public"."approver_rule"
SET "rule_type" = 'http',
    "rule_value" = '{"url": "http://staff-api:8000/livestock/approver-resolver?level=kebele&secret=livestock-approver-resolver-secret"}'
WHERE "id" = '3fea9228-4636-5424-a80d-56b8fce8ae1d';

INSERT INTO "public"."approver_rule" (
    "id", "stage_id", "rule_type", "rule_value", "kind", "required", "created_at", "updated_at"
) VALUES
    ('4a0b1c2d-5e6f-5061-9182-b3c4d5e6f701', '9c1f2a3b-4d5e-5f60-8a71-b2c3d4e5f601', 'http', '{"url": "http://staff-api:8000/livestock/approver-resolver?level=woreda&secret=livestock-approver-resolver-secret"}', 'approver', 'FALSE', NOW(), NOW()),
    ('4a0b1c2d-5e6f-5061-9182-b3c4d5e6f702', '9c1f2a3b-4d5e-5f60-8a71-b2c3d4e5f602', 'http', '{"url": "http://staff-api:8000/livestock/approver-resolver?level=zone&secret=livestock-approver-resolver-secret"}', 'approver', 'FALSE', NOW(), NOW()),
    ('4a0b1c2d-5e6f-5061-9182-b3c4d5e6f703', '9c1f2a3b-4d5e-5f60-8a71-b2c3d4e5f603', 'http', '{"url": "http://staff-api:8000/livestock/approver-resolver?level=region&secret=livestock-approver-resolver-secret"}', 'approver', 'FALSE', NOW(), NOW())
ON CONFLICT ("id") DO NOTHING;

-- Runs against the "livestock" database.
-- (execute the block below separately -- different database connection)
-- UPDATE "public"."g2p_registry_awe_policy_configurations"
-- SET "context_field_names" = '["kebele","woreda","zone","region"]'
-- WHERE "awe_policy_config_id" = '8d2e9ba3-5c4e-4f26-ab37-6e9f1a4c82b5';
