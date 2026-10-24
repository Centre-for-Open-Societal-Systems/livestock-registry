-- Patch for already-seeded environments only (fresh databases get this from
-- g2p_register_sections.sql directly; the seed never updates existing rows).
--
-- The dialog-table widgets of the 8 dialog sections (Livestock Details, Health
-- Event, Vaccination, Vital Event, Breeding, Audit Log, Import Batch, Vaccine
-- Schedule) carried the section MNEMONIC as their on-screen text: the Add/Edit
-- dialog was titled "Add ls_health_event_details", and the widget label — which
-- the platform also prints in row validation messages ("Row 1,
-- ls_health_event_details: ...") — read the same. This rewrites all three
-- strings from the section's own description ("Add Health Event Details",
-- "Edit Health Event Details", "Health Event Details").
--
-- Generic on purpose: one statement covers every dialog section, keyed on the
-- row's own section_mnemonic / section_description, so a section added later
-- with the same mnemonic-as-title habit is fixed by the same patch. Idempotent:
-- once the mnemonic text is gone nothing matches and the row is left as it is
-- (a title changed by hand later is therefore never overwritten).
--
-- The five dialog sections that have their own patch_ls_*_sync_ui_schema.sql
-- get the same text from those (regenerated from the seed); this patch is what
-- reaches the other three, and it is harmless on all eight.
UPDATE "public"."g2p_register_sections" s
SET section_ui_schema = replace(
    replace(
        replace(
            s.section_ui_schema::text,
            '"widget-data-dialog-title-add": "Add ' || s.section_mnemonic || '"',
            '"widget-data-dialog-title-add": "Add ' || s.section_description || '"'
        ),
        '"widget-data-dialog-title-edit": "Edit ' || s.section_mnemonic || '"',
        '"widget-data-dialog-title-edit": "Edit ' || s.section_description || '"'
    ),
    '"widget-label": "' || s.section_mnemonic || '"',
    '"widget-label": "' || s.section_description || '"'
)::jsonb
WHERE s.section_ui_schema::text LIKE '%"widget-type": "dialog-table"%'
  AND s.section_description IS NOT NULL
  AND s.section_description <> '';
