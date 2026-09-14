-- Who may approve each stage.
--
-- registry.change_request.livestock keeps its single rule_type='user' rule
-- (literal {"user_id": "admin"}) -- AWE's resolver matches that against the
-- bearer token's preferred_username (then username, then sub); 'admin' is
-- the Registry Admin seeded into the Keycloak `staff` realm by
-- local/keycloak/realm-staff.json.
--
-- registry.intake_form.livestock's 4 stages each use rule_type='http'
-- instead: AWE POSTs {"context": {...}} to the given URL and expects
-- {"user_ids": [...]} back. The URL points at this extension's own
-- approver-resolver controller (g2p_approver_resolver_controller.py /
-- approver_resolver_service.py), one path segment per level (kebele/woreda/
-- zone/region) -- it looks up whichever Keycloak user holds BOTH the
-- matching client role (Kebele/Woreda/Zone/Region Approver) AND an
-- approver_location_value attribute equal to context[level], i.e. the
-- record's OWN kebele/woreda/zone/region (see context_field_names on
-- g2p_registry_awe_policy_configurations, meta_data/awe-integration/). This
-- is what makes each stage per-location rather than "any Woreda Approver
-- anywhere can approve any woreda's record". The `secret` query param is
-- APPROVER_RESOLVER_SECRET (local/.env) -- baked into the URL since AWE's
-- own http-resolver caller sends a plain unsigned POST with nothing else to
-- verify against.
--
-- NB the policies carry forbid_self_approval = FALSE, so the same operator
-- can raise a change request and approve it on the admin-only policy above.
-- That is what makes a single-operator test possible there; turn it on for
-- a real deployment.
--
-- `required` MUST stay FALSE on this AWE build regardless of rule_type. Its
-- required-approver gate (engine._recompute_stage) collects approvals as
-- `approval_decision.actor`, which AWE fills from the token's `name` claim
-- ("Registry Admin"), then compares them against required ids resolved as
-- `preferred_username` ("admin", "kebele.approver.test", ...). The two
-- identifier spaces never match, so a required approver can never be
-- satisfied and the stage rejects even a genuine approval. Verified against
-- openg2p/openg2p-awe:0.0.0-develop.64.
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
    ('3fea9228-4636-5424-a80d-56b8fce8ae1d', '71e2ee0d-0887-5e70-877e-1ca1998ee0e6', 'http', '{"url": "http://staff-api:8000/livestock/approver-resolver?level=kebele&secret=livestock-approver-resolver-secret"}', 'approver', 'FALSE', NOW(), NOW()),
    ('4a0b1c2d-5e6f-5061-9182-b3c4d5e6f701', '9c1f2a3b-4d5e-5f60-8a71-b2c3d4e5f601', 'http', '{"url": "http://staff-api:8000/livestock/approver-resolver?level=woreda&secret=livestock-approver-resolver-secret"}', 'approver', 'FALSE', NOW(), NOW()),
    ('4a0b1c2d-5e6f-5061-9182-b3c4d5e6f702', '9c1f2a3b-4d5e-5f60-8a71-b2c3d4e5f602', 'http', '{"url": "http://staff-api:8000/livestock/approver-resolver?level=zone&secret=livestock-approver-resolver-secret"}', 'approver', 'FALSE', NOW(), NOW()),
    ('4a0b1c2d-5e6f-5061-9182-b3c4d5e6f703', '9c1f2a3b-4d5e-5f60-8a71-b2c3d4e5f603', 'http', '{"url": "http://staff-api:8000/livestock/approver-resolver?level=region&secret=livestock-approver-resolver-secret"}', 'approver', 'FALSE', NOW(), NOW())
ON CONFLICT ("id") DO NOTHING;
