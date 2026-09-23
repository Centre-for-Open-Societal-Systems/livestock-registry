-- Patch for already-seeded environments only (fresh databases get this from
-- g2p_register_sections.sql directly; the seed never updates existing rows).
--
-- The four event dialogs (Health Event, Vaccination, Vital Event, Breeding)
-- name their animal in ear_tag_id, but an animal of a species with no ear to
-- tag (poultry, beehives -- "Requires Ear Tag" off in the species config)
-- carries a secondary identifier instead, and that is what its event rows
-- hold. The column is labelled accordingly, both in the dialog and as the
-- section table's header. The Livestock Details dialog keeps "Livestock Ear
-- Tag": there the column really is the ear tag, and Secondary Identifier is
-- a separate field. Idempotent: matches the old label only.
--
-- The four patch_ls_*_sync_ui_schema.sql files carry the same text; this
-- patch exists so the label is fixed on an environment where those were
-- applied before this change, without waiting for the next regeneration.
UPDATE "public"."g2p_register_sections"
SET section_ui_schema = replace(
    section_ui_schema::text,
    '"column-key": "ear_tag_id", "widget-type": "input", "widget-label": "Livestock Ear Tag"',
    '"column-key": "ear_tag_id", "widget-type": "input", "widget-label": "Ear Tag / Secondary Identifier"'
)::jsonb
WHERE section_mnemonic IN ('ls_health_event_details', 'ls_vaccination_details', 'ls_vital_event_details', 'ls_breeding_details');
