-- Retire the custom ImportBatch child register of Livestock.
--
-- It mirrored an Odoo model, nothing ever wrote to it, and bulk import now runs
-- on the platform's own import queue (docs/file-import.md), so the register,
-- its section and its tab binding are no longer seeded. A seed upsert never
-- deletes, so databases that already hold the rows lose them here.
--
-- Configuration only, children first, by explicit id; never NOT IN. The data
-- tables g2p_register_import_batches, g2p_register_history_import_batches and
-- g2p_intake_form_import_batches are not dropped: they can hold rows on a
-- database nobody has inspected, and an empty orphan table costs nothing. A
-- later release can drop them once they are shown to be empty everywhere.
--
-- The "Imports & Audit" tab keeps its id and now holds the audit log only, so
-- its label becomes "Audit". Idempotent: every statement matches fixed ids and
-- does nothing once they are gone.

DELETE FROM "public"."g2p_register_ui_tab_sections"
 WHERE "tab_section_id" = '84721b63-f862-5ca7-aba5-fee321f2564b'
   AND "section_id" = 'livestock_import_batch_details_section_01';

DELETE FROM "public"."g2p_register_sections"
 WHERE "section_id" = 'livestock_import_batch_details_section_01'
   AND "section_register_id" = '0fd11be9-83d7-5d2e-9dea-e0653add7059';

DELETE FROM "public"."g2p_register_schemas"
 WHERE "register_id" = '0fd11be9-83d7-5d2e-9dea-e0653add7059';

DELETE FROM "public"."g2p_register_definitions"
 WHERE "register_id" = '0fd11be9-83d7-5d2e-9dea-e0653add7059'
   AND "register_mnemonic" = 'ImportBatch';

UPDATE "public"."g2p_register_ui_tabs"
   SET "tab_label" = 'Audit'
 WHERE "tab_id" = 'livestock_import_batch_tab'
   AND "tab_label" = 'Imports & Audit';

-- The section's translation key, named, in both translation columns.
UPDATE "public"."registry_languages"
   SET "core_translation" = (COALESCE("core_translation"::jsonb, '{}'::jsonb) - 'ls_import_batch_details')::json,
       "domain_translation" = (COALESCE("domain_translation"::jsonb, '{}'::jsonb) - 'ls_import_batch_details')::json
 WHERE "language_id" IS NOT NULL;

-- Guard: fail the seed if any configuration of the retired register survives.
DO $$
DECLARE
    leftovers integer;
BEGIN
    SELECT (SELECT count(*) FROM "public"."g2p_register_definitions"
             WHERE "register_id" = '0fd11be9-83d7-5d2e-9dea-e0653add7059')
         + (SELECT count(*) FROM "public"."g2p_register_schemas"
             WHERE "register_id" = '0fd11be9-83d7-5d2e-9dea-e0653add7059')
         + (SELECT count(*) FROM "public"."g2p_register_sections"
             WHERE "section_id" = 'livestock_import_batch_details_section_01'
                OR "section_register_id" = '0fd11be9-83d7-5d2e-9dea-e0653add7059')
         + (SELECT count(*) FROM "public"."g2p_register_ui_tab_sections"
             WHERE "section_id" = 'livestock_import_batch_details_section_01')
      INTO leftovers;
    IF leftovers <> 0 THEN
        RAISE EXCEPTION 'Retired livestock ImportBatch register still configured in % rows', leftovers;
    END IF;
END
$$;
