-- Rename the extension's Farmer-reference tables from their old implementer prefix to
-- the OpenG2P g2p_ prefix, together with the constraints, indexes and sequences named
-- after them. Idempotent and safe to run on every start:
--   * a pair whose old table does not exist is skipped (fresh install, or already renamed);
--   * a pair whose new table already exists is left alone (nothing is merged or dropped);
--   * only objects whose name starts with the old table name are renamed, and only when
--     the new name is free.
-- schema_migration.rename_legacy_tables does the same at staff-api start-up; db-seed can run
-- first, so the seed carries this statement and it sorts before 00_archive_approval_bindings.sql.
-- Data is not touched. The inverse is the same statement with the two columns of the list
-- below swapped.
DO $rename$
DECLARE
  pairs text[] := ARRAY[
    'coss_farmer_references', 'g2p_farmer_references',
    'coss_farmer_reference_requests', 'g2p_farmer_reference_requests',
    'coss_farmer_submission_dependencies', 'g2p_farmer_submission_dependencies',
    'coss_farmer_workflow_outbox', 'g2p_farmer_reference_awe_outbox',
    'coss_farmer_pending_lookups', 'g2p_farmer_pending_lookups',
    'coss_approval_binding_archive', 'g2p_approval_binding_archive'];
  i int;
  old_name text;
  new_name text;
  schema_name text := current_schema();
  item record;
  renamed_to text;
BEGIN
  FOR i IN 1 .. array_length(pairs, 1) / 2 LOOP
    old_name := pairs[2 * i - 1];
    new_name := pairs[2 * i];
    IF to_regclass(format('%I.%I', schema_name, old_name)) IS NULL THEN
      CONTINUE;
    END IF;
    IF to_regclass(format('%I.%I', schema_name, new_name)) IS NOT NULL THEN
      RAISE WARNING 'both % and % exist; leaving the old table untouched', old_name, new_name;
      CONTINUE;
    END IF;
    EXECUTE format('ALTER TABLE %I.%I RENAME TO %I', schema_name, old_name, new_name);

    -- Constraints (a primary key or unique constraint carries its index along).
    FOR item IN
      SELECT conname FROM pg_constraint
      WHERE conrelid = format('%I.%I', schema_name, new_name)::regclass
        AND left(conname, length(old_name) + 1) = old_name || '_'
    LOOP
      renamed_to := new_name || substr(item.conname, length(old_name) + 1);
      IF NOT EXISTS (SELECT 1 FROM pg_constraint
                     WHERE conrelid = format('%I.%I', schema_name, new_name)::regclass AND conname = renamed_to) THEN
        EXECUTE format('ALTER TABLE %I.%I RENAME CONSTRAINT %I TO %I', schema_name, new_name, item.conname, renamed_to);
      END IF;
    END LOOP;

    -- Plain indexes: <old>_... and ix_<old>_... (not the ones a constraint owns).
    FOR item IN
      SELECT c.relname FROM pg_index x JOIN pg_class c ON c.oid = x.indexrelid
      WHERE x.indrelid = format('%I.%I', schema_name, new_name)::regclass
        AND NOT EXISTS (SELECT 1 FROM pg_constraint k WHERE k.conindid = x.indexrelid)
        AND (left(c.relname, length(old_name) + 1) = old_name || '_'
             OR left(c.relname, length(old_name) + 4) = 'ix_' || old_name || '_')
    LOOP
      IF left(item.relname, 3) = 'ix_' THEN
        renamed_to := 'ix_' || new_name || substr(item.relname, length(old_name) + 4);
      ELSE
        renamed_to := new_name || substr(item.relname, length(old_name) + 1);
      END IF;
      IF to_regclass(format('%I.%I', schema_name, renamed_to)) IS NULL THEN
        EXECUTE format('ALTER INDEX %I.%I RENAME TO %I', schema_name, item.relname, renamed_to);
      END IF;
    END LOOP;

    -- Sequences owned by a column of the table.
    FOR item IN
      SELECT s.relname FROM pg_class s JOIN pg_depend d ON d.objid = s.oid AND d.deptype = 'a'
      WHERE s.relkind = 'S' AND d.refobjid = format('%I.%I', schema_name, new_name)::regclass
        AND left(s.relname, length(old_name) + 1) = old_name || '_'
    LOOP
      renamed_to := new_name || substr(item.relname, length(old_name) + 1);
      IF to_regclass(format('%I.%I', schema_name, renamed_to)) IS NULL THEN
        EXECUTE format('ALTER SEQUENCE %I.%I RENAME TO %I', schema_name, item.relname, renamed_to);
      END IF;
    END LOOP;
  END LOOP;

  -- Constraints whose generated name Postgres cut to 63 characters keep the old prefix but
  -- not the full old table name (coss_farmer_reference_request_..._key), so the loop above
  -- skips them; this also covers tables renamed by an earlier run of this statement.
  FOR i IN 1 .. array_length(pairs, 1) / 2 LOOP
    new_name := pairs[2 * i];
    IF to_regclass(format('%I.%I', schema_name, new_name)) IS NULL THEN
      CONTINUE;
    END IF;
    FOR item IN
      SELECT conname FROM pg_constraint
      WHERE conrelid = format('%I.%I', schema_name, new_name)::regclass
        AND left(conname, 5) = 'coss_'
    LOOP
      renamed_to := left('g2p_' || substr(item.conname, 6), 63);
      IF NOT EXISTS (SELECT 1 FROM pg_constraint
                     WHERE conrelid = format('%I.%I', schema_name, new_name)::regclass AND conname = renamed_to)
         AND to_regclass(format('%I.%I', schema_name, renamed_to)) IS NULL THEN
        EXECUTE format('ALTER TABLE %I.%I RENAME CONSTRAINT %I TO %I', schema_name, new_name, item.conname, renamed_to);
      END IF;
    END LOOP;
  END LOOP;
END
$rename$;
