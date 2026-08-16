-- Who may approve. rule_type 'user' takes a literal {"user_id": "<username>"},
-- which AWE's resolver matches against the bearer token's preferred_username
-- (then username, then sub). 'admin' is the Registry Admin seeded into the
-- Keycloak `staff` realm by local/keycloak/realm-staff.json.
--
-- Swap rule_type to 'role' with {"role": "..."} to approve by Keycloak role
-- rather than by named user once real approver groups exist.
--
-- NB the policies carry forbid_self_approval = FALSE, so the same operator can
-- raise a change request and approve it. That is what makes a single-operator
-- test possible; turn it on for a real deployment.
--
-- `required` MUST stay FALSE on this AWE build. Its required-approver gate
-- (engine._recompute_stage) collects approvals as `approval_decision.actor`,
-- which AWE fills from the token's `name` claim ("Registry Admin"), then
-- compares them against required ids resolved as `preferred_username`
-- ("admin"). The two identifier spaces never match, so a required approver
-- can never be satisfied and the stage rejects even a genuine approval.
-- Verified against openg2p/openg2p-awe:0.0.0-develop.64.
INSERT INTO "public"."approver_rule" (
    "id",
    "stage_id",
    "rule_type",
    "rule_value",
    "kind",
    "required",
    "created_at",
    "updated_at"
) VALUES
    ('eed867be-436b-5946-868e-147b34bfd7db', '6a963145-a31a-5ee7-a59c-87acf62b1686', 'user', '{"user_id": "admin"}', 'approver', 'FALSE', NOW(), NOW()),
    ('3fea9228-4636-5424-a80d-56b8fce8ae1d', '71e2ee0d-0887-5e70-877e-1ca1998ee0e6', 'user', '{"user_id": "admin"}', 'approver', 'FALSE', NOW(), NOW())
ON CONFLICT ("id") DO NOTHING;
