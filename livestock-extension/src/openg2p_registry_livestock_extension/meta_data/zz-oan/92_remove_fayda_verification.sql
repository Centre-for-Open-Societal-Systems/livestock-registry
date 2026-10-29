-- Crop and Livestock identify the farmer by Farmer ID and a typed Fayda ID (FAN or
-- FIN); Fayda (eSignet) verification belongs to the Farmer registry only. Long-lived
-- databases still hold the "Fayda verification" widget from the earlier identity
-- overlays, so drop it from every section by its widget name and widget id (the seed
-- files no longer add it), show the FIN under a plain label, and switch off the
-- registrant-authentication flag that enabled the Verify action. Idempotent.

CREATE OR REPLACE FUNCTION pg_temp.oan_drop_fayda_verification(node jsonb)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE result jsonb;
BEGIN
  IF jsonb_typeof(node) = 'array' THEN
    SELECT COALESCE(jsonb_agg(pg_temp.oan_drop_fayda_verification(item.value) ORDER BY item.position), '[]'::jsonb)
      INTO result
      FROM jsonb_array_elements(node) WITH ORDINALITY AS item(value, position)
      WHERE NOT COALESCE(jsonb_typeof(item.value) = 'object'
                 AND (item.value->>'widget' = 'oan-identity-verification'
                      OR (item.value ? 'widget' AND item.value->>'widget-id' = 'identity_verification')), false);
  ELSIF jsonb_typeof(node) = 'object' THEN
    SELECT COALESCE(jsonb_object_agg(key, pg_temp.oan_drop_fayda_verification(value)), '{}'::jsonb)
      INTO result FROM jsonb_each(node);
    IF node ? 'widget' AND node->>'widget-data-path' = '997676d3-7008-59f9-b23e-613ad79bbb08.fayda_fin'
       AND node->>'widget-label' = 'Fayda FIN (from verification)' THEN
      result := result || '{"widget-label": "Fayda FIN"}'::jsonb;
    END IF;
  ELSE
    result := node;
  END IF;
  RETURN result;
END $$;

UPDATE g2p_register_sections
SET section_ui_schema = pg_temp.oan_drop_fayda_verification(section_ui_schema::jsonb)
WHERE section_ui_schema IS NOT NULL
  AND (section_ui_schema::jsonb::text LIKE '%oan-identity-verification%'
       OR section_ui_schema::jsonb::text LIKE '%"identity_verification"%'
       OR section_ui_schema::jsonb::text LIKE '%Fayda FIN (from verification)%');

UPDATE g2p_register_definitions SET requires_registrant_authentication = false
WHERE register_id = '997676d3-7008-59f9-b23e-613ad79bbb08' AND requires_registrant_authentication;

DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM g2p_register_sections
      WHERE section_ui_schema::jsonb::text LIKE '%oan-identity-verification%'
         OR section_ui_schema::jsonb::text LIKE '%"widget-id": "identity_verification"%') THEN
    RAISE EXCEPTION 'The Fayda verification widget is still present in a Livestock section';
  END IF;
END $$;
