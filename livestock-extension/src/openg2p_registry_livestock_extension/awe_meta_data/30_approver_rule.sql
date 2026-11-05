-- OpenG2P Farmer 1.2 default approval pattern. Domain-specific keys keep
-- old policies and in-flight tasks intact; no role/grant/task mutation.
-- Every stage lists the named officer and admin; one decision from either completes it.
INSERT INTO public.approver_rule (id,stage_id,rule_type,rule_value,kind,required,created_at,updated_at)
SELECT v.id,s.id,'user',v.rule_value::json,'approver',FALSE,NOW(),NOW()
FROM (VALUES
('d4a7ccb6-dc2f-5194-9a06-026d4228ff59','registry.change_request.livestock.default',1,'{"user_id": "alex.carter"}'),
('9cf24a14-ffd1-5c3c-bf25-1652612bbee2','registry.change_request.livestock.default',1,'{"user_id": "admin"}'),
('b99e3514-73b4-5630-a2d1-903cf1367b3d','registry.change_request.livestock.default',2,'{"user_id": "nina.patel"}'),
('730ae60a-aae1-5216-90c6-76a889fe06cd','registry.change_request.livestock.default',2,'{"user_id": "admin"}'),
('c89b8f0d-0f39-5a5e-a6b7-79317e953bc2','registry.change_request.livestock-farmer.default',1,'{"user_id": "alex.carter"}'),
('bcdfd5f2-a47a-5802-a96e-5e3d6e744c83','registry.change_request.livestock-farmer.default',1,'{"user_id": "admin"}'),
('20412aa3-2fe8-5d32-a1ac-1f14044064f5','registry.change_request.livestock-farmer.default',2,'{"user_id": "nina.patel"}'),
('3efd7410-f28d-5a25-9ff6-d32950516f68','registry.change_request.livestock-farmer.default',2,'{"user_id": "admin"}'),
('08809ff1-429d-5f46-aebe-0c71d1841730','registry.intake_form.livestock.default',1,'{"user_id": "alex.carter"}'),
('557c6bc0-3277-5a16-a1bc-f8437ee650fe','registry.intake_form.livestock.default',1,'{"user_id": "admin"}'),
('89fc4f76-1ab8-5fd5-9af9-c7e1cdb1c143','registry.intake_form.livestock.default',2,'{"user_id": "nina.patel"}'),
('b309312d-9225-5da4-8458-cd870a6fa368','registry.intake_form.livestock.default',2,'{"user_id": "admin"}')) AS v(id,policy_key,stage_order,rule_value)
JOIN public.approval_policy p ON p.policy_key=v.policy_key AND p.version=1
JOIN public.approval_stage s ON s.policy_id=p.id AND s.stage_order=v.stage_order
WHERE NOT EXISTS (SELECT 1 FROM public.approver_rule r WHERE r.stage_id=s.id AND r.rule_type='user' AND r.rule_value::text=v.rule_value)
ON CONFLICT (id) DO NOTHING;
