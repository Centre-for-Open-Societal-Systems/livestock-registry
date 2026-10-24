-- Patch for already-seeded environments only (the seed only INSERTs).
--
-- Adds vaccination_status, gender and secondary_identifier to the Animal
-- register's search results, so the country-wide Animals list (header
-- "Animals" button, livestock-dialog-overlay.js) can show them from one
-- search call. Same value as the Animal line in g2p_register_schemas.sql;
-- keep the two in sync. Safe to re-run.
UPDATE "public"."g2p_register_schemas"
SET search_result_schema = '[{"field_name": "ear_tag_id", "display_label": "Ear Tag", "order": 1}, {"field_name": "species", "display_label": "Species", "order": 2}, {"field_name": "breed", "display_label": "Breed", "order": 3}, {"field_name": "health_status", "display_label": "Health Status", "order": 4}, {"field_name": "vaccination_status", "display_label": "Vaccination Status", "order": 5}, {"field_name": "gender", "display_label": "Sex", "order": 6}, {"field_name": "secondary_identifier", "display_label": "Secondary Identifier", "order": 7}]'
WHERE register_id = '041a9f79-2142-548a-a15b-a4c76fc9f6f7';
