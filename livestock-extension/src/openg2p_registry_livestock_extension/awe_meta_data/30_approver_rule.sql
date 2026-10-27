-- OpenG2P Farmer 1.2 default approval pattern. Domain-specific keys keep
-- old policies and in-flight tasks intact; no role/grant/task mutation.
INSERT INTO public.approver_rule (id,stage_id,rule_type,rule_value,kind,required,created_at,updated_at)
SELECT v.id,s.id,'user',v.rule_value::json,'approver',FALSE,NOW(),NOW()
FROM (VALUES
('d4a7ccb6-dc2f-5194-9a06-026d4228ff59','registry.change_request.livestock.default',1,'{"user_id": "alex.carter"}'),
('b99e3514-73b4-5630-a2d1-903cf1367b3d','registry.change_request.livestock.default',2,'{"user_id": "nina.patel"}'),
('c89b8f0d-0f39-5a5e-a6b7-79317e953bc2','registry.change_request.livestock-farmer.default',1,'{"user_id": "alex.carter"}'),
('20412aa3-2fe8-5d32-a1ac-1f14044064f5','registry.change_request.livestock-farmer.default',2,'{"user_id": "nina.patel"}'),
('08809ff1-429d-5f46-aebe-0c71d1841730','registry.intake_form.livestock.default',1,'{"user_id": "alex.carter"}'),
('89fc4f76-1ab8-5fd5-9af9-c7e1cdb1c143','registry.intake_form.livestock.default',2,'{"user_id": "nina.patel"}')) AS v(id,policy_key,stage_order,rule_value)
JOIN public.approval_policy p ON p.policy_key=v.policy_key AND p.version=1
JOIN public.approval_stage s ON s.policy_id=p.id AND s.stage_order=v.stage_order
WHERE NOT EXISTS (SELECT 1 FROM public.approver_rule r WHERE r.stage_id=s.id AND r.rule_type='user' AND r.rule_value::text=v.rule_value)
ON CONFLICT (id) DO NOTHING;
