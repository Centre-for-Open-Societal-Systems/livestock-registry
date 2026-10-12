-- Approval workflow stages.
--
-- registry.change_request.livestock (editing an already-VERIFIED Livestock
-- record) stays on ONE flat stage -- out of scope for the hierarchical
-- chain below; see [[livestock-4-level-approval-chain]] plan.
--
-- registry.intake_form.livestock (a new Livestock intake submission, made
-- by a DA / field officer) has ONE stage: the Woreda Approver of the record's
-- own woreda approves it (decision of Oct 2026, replacing gen1's Kebele ->
-- Woreda -> Zone -> Region ladder). The approver is resolved per record by
-- the http approver-resolver endpoint (30_approver_rule.sql), level=woreda,
-- not a fixed user. An environment seeded with the old four stages is moved
-- over by patch_livestock_single_woreda_approval.sql.
--
-- on_empty 'block' -- if no approver resolves (nobody is assigned to that
--                     woreda yet), the request stalls rather than
--                     auto-approving. Safer default for an approval gate.
-- mode -- patch_livestock_approval_modes.sql sets any-n / 1 (any one of the
--         resolved approvers).
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
    ('71e2ee0d-0887-5e70-877e-1ca1998ee0e6', '907339cb-744e-5fe9-9805-df7416d81dbe', 1, 'Woreda Approval', 'all', NULL, NULL, NULL, 'null', 'block', NULL, 'null', NOW(), NOW())
ON CONFLICT ("id") DO NOTHING;
