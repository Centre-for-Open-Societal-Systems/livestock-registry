-- Patch for already-seeded environments only; safe to re-run (every UPDATE
-- touches rows that are still blank, so the second run changes nothing).
--
-- The Livestock intake form collects First / Middle / Last Name only and
-- nothing composed farmer_name from them, so Farmer rows registered through
-- the form carry farmer_name NULL, their record_name is the bare FR- id, and
-- the Livestock record's approval-time mirror copied that NULL over the name
-- it had at intake. The code now composes the name at intake
-- (g2p_register_domain_service_farmer.py _fill_farmer_name) and falls back to
-- the parts when mirroring (g2p_register_domain_service_livestock.py
-- _sync_farmer_identity); this backfills rows created before that.

UPDATE "public"."g2p_register_farmers"
SET farmer_name = NULLIF(btrim(concat_ws(' ',
        NULLIF(btrim(first_name), ''), NULLIF(btrim(middle_name), ''), NULLIF(btrim(last_name), ''))), '')
WHERE (farmer_name IS NULL OR btrim(farmer_name) = '')
  AND (NULLIF(btrim(first_name), '') IS NOT NULL
       OR NULLIF(btrim(middle_name), '') IS NOT NULL
       OR NULLIF(btrim(last_name), '') IS NOT NULL);

UPDATE "public"."g2p_intake_form_farmers"
SET farmer_name = NULLIF(btrim(concat_ws(' ',
        NULLIF(btrim(first_name), ''), NULLIF(btrim(middle_name), ''), NULLIF(btrim(last_name), ''))), '')
WHERE (farmer_name IS NULL OR btrim(farmer_name) = '')
  AND (NULLIF(btrim(first_name), '') IS NOT NULL
       OR NULLIF(btrim(middle_name), '') IS NOT NULL
       OR NULLIF(btrim(last_name), '') IS NOT NULL);

-- Livestock register rows mirror the farmer they are linked to.
UPDATE "public"."g2p_register_livestocks" l
SET farmer_name = f.farmer_name
FROM "public"."g2p_register_farmers" f
WHERE l.farmer_uuid = f.internal_record_id
  AND (l.farmer_name IS NULL OR btrim(l.farmer_name) = '')
  AND f.farmer_name IS NOT NULL;

-- Pending submissions: the Livestock intake row carries the sibling Farmer
-- row's identity (deduplication input), keyed by application_reference.
UPDATE "public"."g2p_intake_form_livestocks" l
SET farmer_id   = COALESCE(NULLIF(btrim(l.farmer_id), ''), f.farmer_id),
    fayda_fan_id = COALESCE(NULLIF(btrim(l.fayda_fan_id), ''), f.fayda_fan_id),
    farmer_name  = COALESCE(NULLIF(btrim(l.farmer_name), ''), f.farmer_name)
FROM "public"."g2p_intake_form_farmers" f
WHERE f.application_reference = l.application_reference
  AND (((l.farmer_name IS NULL OR btrim(l.farmer_name) = '') AND f.farmer_name IS NOT NULL)
       OR ((l.farmer_id IS NULL OR btrim(l.farmer_id) = '') AND f.farmer_id IS NOT NULL)
       OR ((l.fayda_fan_id IS NULL OR btrim(l.fayda_fan_id) = '') AND f.fayda_fan_id IS NOT NULL));
