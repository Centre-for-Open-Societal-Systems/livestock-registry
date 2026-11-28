-- Validation message keys, rule ids and the location panel id lost their old prefix
-- (coss_input_<field> -> validation_<field>, coss_field_<rule> -> validation_rule_<rule>,
-- coss_code_choice -> validation_code_choice, panel coss_location_widgets -> location_widgets).
-- The seeds now write only the new names. Seeds upsert and never delete, so a database
-- seeded earlier still holds the old ones; this file moves them over and removes them.
-- Replays change nothing.

-- Translations: a value stored under an old key moves to the new key unless the new key
-- already has one (the new key wins); every old key is dropped.
UPDATE registry_languages AS l
SET domain_translation = (
  SELECT COALESCE(jsonb_object_agg(renamed.key, renamed.value), '{}'::jsonb)
  FROM (
    SELECT DISTINCT ON (moved.key) moved.key, moved.value
    FROM (
      SELECT regexp_replace(regexp_replace(regexp_replace(e.key,
               '^coss_input_', 'validation_'), '^coss_field_', 'validation_rule_'),
               '^coss_code_choice$', 'validation_code_choice') AS key,
             e.value,
             (e.key ~ '^coss_(input_|field_)' OR e.key = 'coss_code_choice') AS legacy
      FROM jsonb_each(l.domain_translation::jsonb) AS e
    ) AS moved
    ORDER BY moved.key, moved.legacy
  ) AS renamed
)::json
WHERE l.domain_translation IS NOT NULL
  AND EXISTS (SELECT 1 FROM jsonb_object_keys(l.domain_translation::jsonb) AS k(key)
              WHERE k.key ~ '^coss_(input_|field_)' OR k.key = 'coss_code_choice');

-- Saved section UI schemas: patternMessage / minDateMessage values, rule ids and the panel id.
DO $$
DECLARE target record;
BEGIN
  FOR target IN
    SELECT table_name, data_type FROM information_schema.columns
    WHERE table_schema = 'public' AND column_name = 'section_ui_schema' AND data_type IN ('json', 'jsonb')
  LOOP
    EXECUTE format(
      'UPDATE public.%I SET section_ui_schema = regexp_replace(regexp_replace(regexp_replace(regexp_replace('
      || 'section_ui_schema::text, ''coss_input_'', ''validation_'', ''g''), ''coss_field_'', ''validation_rule_'', ''g''), '
      || '''coss_code_choice'', ''validation_code_choice'', ''g''), ''coss_location_widgets'', ''location_widgets'', ''g'')::%s '
      || 'WHERE section_ui_schema::text ~ ''coss_(input_|field_|code_choice|location_widgets)''',
      target.table_name, target.data_type);
  END LOOP;
END $$;
