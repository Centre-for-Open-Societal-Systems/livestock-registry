-- registry-platform 1.2 models latitude / longitude / altitude as double
-- precision; 0.0.0-develop.296 created them as varchar. The platform's
-- create_migrate never alters an existing column, so a database created on
-- 296 keeps varchar and every save that carries a coordinate fails (asyncpg
-- refuses a float for a varchar parameter). Converts, in the registry
-- database, each such column of a g2p_* table that is still text.
--
-- Safe to re-run: a column that is already double precision is not touched.
-- No data is dropped: blank text becomes NULL, and a column holding any value
-- that is not a number is left as text with a WARNING naming it, for someone
-- to clean by hand. Each column is converted on its own, so one failure
-- (e.g. a dependent view) does not stop the others.
DO $$
DECLARE
    r record;
    bad bigint;
    numeric_re constant text := '^[-+]?([0-9]+\.?[0-9]*|\.[0-9]+)([eE][-+]?[0-9]+)?$';
BEGIN
    FOR r IN
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name LIKE 'g2p\_%'
          AND column_name IN ('latitude', 'longitude', 'altitude')
          AND data_type IN ('character varying', 'text')
        ORDER BY table_name, column_name
    LOOP
        EXECUTE format(
            'SELECT count(*) FROM %I WHERE %I IS NOT NULL AND btrim(%I) <> '''' AND btrim(%I) !~ %L',
            r.table_name, r.column_name, r.column_name, r.column_name, numeric_re
        ) INTO bad;
        IF bad > 0 THEN
            RAISE WARNING 'geo columns: %.% has % non-numeric value(s); left as text',
                r.table_name, r.column_name, bad;
            CONTINUE;
        END IF;
        BEGIN
            EXECUTE format(
                'ALTER TABLE %I ALTER COLUMN %I TYPE double precision USING NULLIF(btrim(%I), '''')::double precision',
                r.table_name, r.column_name, r.column_name
            );
            RAISE NOTICE 'geo columns: %.% converted to double precision', r.table_name, r.column_name;
        EXCEPTION WHEN others THEN
            RAISE WARNING 'geo columns: %.% not converted: %', r.table_name, r.column_name, SQLERRM;
        END;
    END LOOP;
END
$$;
