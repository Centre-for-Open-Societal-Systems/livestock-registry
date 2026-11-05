-- Display text for the values the staff screens print from stored codes:
-- task and change request statuses, the change request task context (policy
-- keys, artifact types, change types) and register names. Lists, task
-- history, My tasks and change request details showed these raw.
--
-- Keys that are the stored value itself (a status code, a policy key, a
-- register mnemonic). Nothing here is ordinary English text used as a label
-- elsewhere. The desktop register table prints stored values without a
-- lookup (platform), so these help everywhere except there.
--
-- A named-key merge on the English row: named keys replace, every other key
-- is kept, so a replay changes nothing. Sorts after 90_display_text.sql.

UPDATE "public"."registry_languages"
SET "domain_translation" = (COALESCE("domain_translation"::jsonb, '{}'::jsonb) ||
'{
 "in_review": "In review",
 "request_created": "Request created",
 "completed": "Completed",
 "skipped": "Skipped",
 "Animal": "Animals",
 "Breeding": "Breeding records",
 "Vaccination": "Vaccinations",
 "registry.change_request.livestock.default": "Livestock change",
 "registry.change_request.livestock-farmer.default": "Farmer reference change",
 "registry.change_request.livestock-farmer.verified-update-skips-review": "Farmer reference change (verified)",
 "registry.intake_form.livestock.default": "Livestock intake",
 "registry.change_request": "Change request",
 "registry.intake_form": "Intake form"
}'::jsonb)::json
WHERE "language_code" = 'en';
