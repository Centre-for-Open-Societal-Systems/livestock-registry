-- Let staff enter every editable registry date in the Ethiopian calendar while
-- preserving the existing Gregorian field, API payload and database value.
-- Walking the complete schema also reaches date columns inside dialog tables.
CREATE OR REPLACE FUNCTION pg_temp.livestock_ethiopian_dates(node jsonb)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE
  result jsonb;
BEGIN
  IF jsonb_typeof(node) = 'array' THEN
    SELECT COALESCE(
      jsonb_agg(pg_temp.livestock_ethiopian_dates(value) ORDER BY ord),
      '[]'::jsonb
    )
    INTO result
    FROM jsonb_array_elements(node) WITH ORDINALITY AS items(value, ord);
  ELSIF jsonb_typeof(node) = 'object' THEN
    SELECT COALESCE(
      jsonb_object_agg(key, pg_temp.livestock_ethiopian_dates(value)),
      '{}'::jsonb
    )
    INTO result
    FROM jsonb_each(node);

    IF node->>'widget' IN ('date', 'oan-next-due-date')
       AND COALESCE((node->>'widget-readonly')::boolean, false) = false THEN
      result := result || '{"widget-variant": "ethiopian"}'::jsonb;

      -- Native TableCellDate bypasses the widget registry. Route editable
      -- table dates through WidgetRenderer so row updates still reach the
      -- table's standard onChange callback.
      IF node->>'widget' = 'date' AND node ? 'column-key' THEN
        result := result || '{"widget": "oan-ethiopian-date-input"}'::jsonb;
      END IF;
    END IF;
  ELSE
    result := node;
  END IF;

  RETURN result;
END $$;

UPDATE "public"."g2p_register_sections"
SET section_ui_schema = pg_temp.livestock_ethiopian_dates(section_ui_schema)
WHERE section_ui_schema IS NOT NULL;

-- Fail the seed immediately if an editable date escaped the transformation.
DO $$
DECLARE
  missing text;
BEGIN
  SELECT string_agg(
    DISTINCT section.section_id || '.' ||
      COALESCE(widget->>'widget-id', widget->>'column-key', '<unknown>'),
    ', '
  )
  INTO missing
  FROM "public"."g2p_register_sections" section,
       jsonb_path_query(
         section.section_ui_schema,
         'lax $.** ? (@.widget == "date" || @.widget == "oan-ethiopian-date-input" || @.widget == "oan-next-due-date")'
       ) widget
  WHERE COALESCE((widget->>'widget-readonly')::boolean, false) = false
    AND widget->>'widget-variant' IS DISTINCT FROM 'ethiopian';

  IF missing IS NOT NULL THEN
    RAISE EXCEPTION 'Editable dates missing the Ethiopian calendar variant: %', missing;
  END IF;
END $$;
