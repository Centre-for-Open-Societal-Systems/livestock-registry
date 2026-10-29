-- Record names written before the readable-name change keep the stored code
-- ("1 x ET7932913003 CATTLE", "LSD_CATTLE ..."); new records read
-- "1 x ET7932913003 Cattle". This rewrites the code part of existing names to
-- the same words register_domain/services/plain_text.py (plain_code_text)
-- gives new ones. Only the code field is touched: the "1 x" prefix, ear tags,
-- vaccine names and every other part of a name stay exactly as stored. A name
-- that no longer starts or ends with its code is left alone, so a second run
-- changes nothing.

CREATE OR REPLACE FUNCTION pg_temp.plain_code_text(code text) RETURNS text AS $$
DECLARE
    t text := btrim(coalesce(code, ''));
    words text;
BEGIN
    IF t = '' OR (position('_' IN t) = 0 AND NOT (t = upper(t) AND t <> lower(t))) THEN
        RETURN t;
    END IF;
    IF left(t, 13) = 'VACCINE_TYPE_' THEN
        t := substr(t, 14);
    ELSIF left(t, 17) = 'LIVESTOCK_DISEASE_' THEN
        t := substr(t, 18);
    ELSIF left(t, 6) = 'BREED_' THEN
        t := substr(t, 7);
    END IF;
    words := lower(btrim(replace(t, '_', ' ')));
    RETURN upper(left(words, 1)) || substr(words, 2);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

DO $$
DECLARE
    spec record;
    tbl record;
BEGIN
    FOR spec IN
        SELECT * FROM (VALUES
            ('animals', 'species', 'suffix'),
            ('vaccine_schedules', 'species', 'suffix'),
            ('health_events', 'event_type', 'prefix'),
            ('vital_events', 'event_type', 'prefix'),
            ('breedings', 'event_type', 'prefix'),
            ('vaccinations', 'vaccine_type', 'prefix'),
            ('audit_logs', 'action_type', 'prefix')
        ) AS v(entity, code_column, placement)
    LOOP
        FOR tbl IN
            SELECT t.table_name
            FROM information_schema.tables t
            WHERE t.table_schema = 'public'
              AND t.table_name IN ('g2p_register_' || spec.entity,
                                   'g2p_register_history_' || spec.entity,
                                   'g2p_intake_form_' || spec.entity)
        LOOP
            CONTINUE WHEN (
                SELECT count(*) FROM information_schema.columns c
                WHERE c.table_schema = 'public' AND c.table_name = tbl.table_name
                  AND c.column_name IN ('record_name', spec.code_column)) <> 2;
            IF spec.placement = 'suffix' THEN
                EXECUTE format(
                    'UPDATE public.%1$I SET record_name = left(record_name, length(record_name) - length(%2$I))'
                    ' || pg_temp.plain_code_text(%2$I)'
                    ' WHERE %2$I IS NOT NULL AND %2$I <> '''''
                    ' AND (record_name = %2$I OR right(record_name, length(%2$I) + 1) = '' '' || %2$I)'
                    ' AND pg_temp.plain_code_text(%2$I) <> %2$I',
                    tbl.table_name, spec.code_column);
            ELSE
                EXECUTE format(
                    'UPDATE public.%1$I SET record_name = pg_temp.plain_code_text(%2$I)'
                    ' || substr(record_name, length(%2$I) + 1)'
                    ' WHERE %2$I IS NOT NULL AND %2$I <> '''''
                    ' AND (record_name = %2$I OR left(record_name, length(%2$I) + 1) = %2$I || '' '')'
                    ' AND pg_temp.plain_code_text(%2$I) <> %2$I',
                    tbl.table_name, spec.code_column);
            END IF;
        END LOOP;
    END LOOP;
END;
$$;
