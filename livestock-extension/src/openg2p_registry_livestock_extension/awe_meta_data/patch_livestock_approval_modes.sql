-- Patch Livestock Approval Stages to mode = 'any'
-- Allows any single authorized approver at that level (Kebele, Woreda, Zone, Region)
-- to approve the submission, rather than requiring 100% of all assigned role-holders.

UPDATE approval_stage
SET mode = 'any'
WHERE policy_id IN (
    '907339cb-744e-5fe9-9805-df7416d81dbe',  -- Livestock Intake Form Approval Policy
    'b2477cdc-7db9-5f2a-bda9-828a713c5b4d'   -- Livestock Change Request Approval Policy
);
