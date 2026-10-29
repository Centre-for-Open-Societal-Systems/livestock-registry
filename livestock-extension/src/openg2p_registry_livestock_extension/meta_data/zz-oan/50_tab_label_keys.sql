-- Register tab labels are translation keys, not display text.
-- The platform only accepts lowercase keys in g2p_register_ui_tabs.tab_label
-- (G2PRegisterUITab.validate_tab_label). Reading a tab straight from the
-- database skips that check, but the change request search rebuilds tabs from
-- the metadata cache, which runs it, so a label such as 'Farmer' made every
-- cached search fail with SYS-ERR-001. Each tab now uses its id as the label
-- key, and the display text comes from the domain translations, as Crop does.
--
-- Explicit-id UPDATEs, so a plain upgrade fixes databases seeded with the old
-- labels and a fresh install (already seeded with the keys) is unchanged.

UPDATE "public"."g2p_register_ui_tabs" SET "tab_label" = "tab_id"
WHERE "tab_id" IN (
  'livestock_livestock_tab',
  'livestock_animal_tab',
  'livestock_health_event_tab',
  'livestock_vital_event_tab',
  'livestock_import_batch_tab',
  'livestock_farmer_tab'
);

-- Display text for the tab keys. A language that already translates a key
-- keeps its own text.
UPDATE "public"."registry_languages"
SET "domain_translation" = ('{
 "livestock_livestock_tab": "Farmer",
 "livestock_animal_tab": "Livestock",
 "livestock_health_event_tab": "Health & vaccination",
 "livestock_vital_event_tab": "Breeding & vital events",
 "livestock_import_batch_tab": "Imports & audit",
 "livestock_farmer_tab": "Farmer"
}'::jsonb || COALESCE("domain_translation"::jsonb, '{}'::jsonb))::json;
