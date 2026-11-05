-- Databases seeded before this change hold these six stages with mode 'all'
-- (the named officer alone). Set them in place to 'any-n' with one decision so
-- the named officer or admin completes the stage; stage and rule ids, policy
-- keys and bindings are unchanged, and the statement is a no-op once applied.
UPDATE public.approval_stage SET mode='any-n', mode_value=1, updated_at=NOW()
WHERE id IN (
    'a5ca8625-143d-57b3-b220-912bdeda193d',
    'e072783f-27ad-582b-b30f-a942d329850a',
    '586da3d5-65f1-566a-80ea-3b4b30d17b82',
    '8536ea7d-7c57-5cb6-af1c-54f992ea3059',
    '580c4a2b-c638-5099-aac5-72860e9ff4ff',
    '23cd6619-b044-55a9-aa1c-ee3b190950d5'
)
  AND (mode <> 'any-n' OR mode_value IS DISTINCT FROM 1);

-- Display name only: the stage ids, orders, modes and rules are untouched.
UPDATE public.approval_stage SET name='First approval', updated_at=NOW()
WHERE id IN (
    'a5ca8625-143d-57b3-b220-912bdeda193d',
    '586da3d5-65f1-566a-80ea-3b4b30d17b82',
    '580c4a2b-c638-5099-aac5-72860e9ff4ff',
    'd2d6c2ea-3e4d-51e5-8e97-78a273e26ecc'
)
  AND name <> 'First approval';
-- Display name only: the stage ids, orders, modes and rules are untouched.
UPDATE public.approval_stage SET name='Second approval', updated_at=NOW()
WHERE id IN (
    'e072783f-27ad-582b-b30f-a942d329850a',
    '8536ea7d-7c57-5cb6-af1c-54f992ea3059',
    '23cd6619-b044-55a9-aa1c-ee3b190950d5',
    '96243f6c-b4d1-5bca-8f08-aaefad9d04ca'
)
  AND name <> 'Second approval';
-- Stages created on long-lived databases before the seeds carried them (no
-- seed row, so no id to list). Matched by policy key plus the exact old name;
-- only the display name changes, and the statement is a no-op once applied.
UPDATE public.approval_stage s SET name=v.new_name, updated_at=NOW()
FROM public.approval_policy p,
     (VALUES
        ('registry.change_request.livestock', 'Registry Admin Approval', 'Registry admin approval'),
        ('registry.intake_form.livestock', 'Region Approval (retired)', 'Region approval (retired)'),
        ('registry.intake_form.livestock', 'Zone Approval (retired)', 'Zone approval (retired)'),
        ('registry.intake_form.livestock', 'Woreda Approval', 'Woreda approval'),
        ('registry.intake_form.livestock', 'Woreda Approval (retired)', 'Woreda approval (retired)')
     ) AS v(policy_key, old_name, new_name)
WHERE s.policy_id=p.id AND p.policy_key=v.policy_key AND s.name=v.old_name;
