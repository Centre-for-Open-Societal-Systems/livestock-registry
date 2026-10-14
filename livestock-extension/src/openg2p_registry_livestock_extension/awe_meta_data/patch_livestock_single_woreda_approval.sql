-- Moves an environment seeded with the old four-stage
-- registry.intake_form.livestock policy (Kebele -> Woreda -> Zone -> Region)
-- to the single Woreda approval (decision of Oct 2026). Runs against the
-- "awe" database on every deploy; safe to re-run.
--
-- Stage 1 keeps its id and becomes the Woreda stage, resolved with
-- level=woreda. The old stages 2-4 are not deleted: approval_task rows of
-- earlier requests reference them (approval_task.stage_id has no cascade), so
-- a DELETE fails on any environment that has used them. They are skipped
-- instead -- AWE evaluates skip_if (JSONLogic over the request context) when
-- a stage activates and treats a truthy result as approved -- so a new
-- request is approved as soon as its Woreda Approver approves. A request
-- already waiting at one of those stages keeps its open task and finishes
-- the old way.
UPDATE "public"."approval_stage"
SET "name" = 'Woreda Approval', "updated_at" = NOW()
WHERE "id" = '71e2ee0d-0887-5e70-877e-1ca1998ee0e6';

UPDATE "public"."approver_rule"
SET "rule_type" = 'http',
    "rule_value" = '{"url": "http://staff-api:8000/livestock/approver-resolver?level=woreda&secret=livestock-approver-resolver-secret"}',
    "updated_at" = NOW()
WHERE "id" = '3fea9228-4636-5424-a80d-56b8fce8ae1d';

-- The old stages are also renamed "(retired)", so the AWE console does not show
-- two "Woreda Approval" stages.
UPDATE "public"."approval_stage"
SET "skip_if" = '{"==": [1, 1]}',
    "name" = CASE WHEN "name" LIKE '% (retired)' THEN "name" ELSE "name" || ' (retired)' END,
    "updated_at" = NOW()
WHERE "id" IN (
    '9c1f2a3b-4d5e-5f60-8a71-b2c3d4e5f601',  -- old Woreda Approval (stage 2)
    '9c1f2a3b-4d5e-5f60-8a71-b2c3d4e5f602',  -- old Zone Approval (stage 3)
    '9c1f2a3b-4d5e-5f60-8a71-b2c3d4e5f603'   -- old Region Approval (stage 4)
);
