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
