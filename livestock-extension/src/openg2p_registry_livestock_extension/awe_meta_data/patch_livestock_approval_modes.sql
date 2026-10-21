-- AWE's quorum rule knows the modes all, any-n / quorum (mode_value = how many
-- approvals), and percentage. A bare 'any' is not one of them: the engine then
-- never finds the stage approved and a fully approved request stays in_review
-- at stage 1 forever. "Any one of the resolved approvers" is any-n with 1.
-- Patch Livestock Approval Stages to "any one approver" (mode any-n, 1)
-- Allows any single authorized approver at that level (Kebele, Woreda, Zone, Region)
-- to approve the submission, rather than requiring 100% of all assigned role-holders.

UPDATE approval_stage
SET mode = 'any-n', mode_value = 1
WHERE policy_id IN (
    '907339cb-744e-5fe9-9805-df7416d81dbe',  -- Livestock Intake Form Approval Policy
    'b2477cdc-7db9-5f2a-bda9-828a713c5b4d'   -- Livestock Change Request Approval Policy
);
