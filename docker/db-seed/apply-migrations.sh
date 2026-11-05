#!/bin/sh
# Apply the Livestock schema and data migrations (migrations/*.sql) once each.
#
# These are not seed configuration: they add columns that the models gained
# after a database was created, relax a constraint, and backfill or clean
# register rows. A fresh install already gets the columns from the models, and
# the backfills find nothing to change there.
#
# Each file runs in its own transaction, in name order, and is recorded in
# oan_livestock_migrations; a recorded file is skipped on the next run. The
# files are also idempotent, so a database that already had them applied by
# the earlier meta_data copies is safe: they run once more, change nothing,
# and are recorded.
#
# Environment: PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD (libpq).
# MIGRATIONS_DIR overrides the folder (default: next to this script).
set -eu

dir="${MIGRATIONS_DIR:-$(dirname "$0")/migrations}"
export PGOPTIONS="${PGOPTIONS:-} -c client_min_messages=warning"

psql -v ON_ERROR_STOP=1 -qX <<'SQL'
CREATE TABLE IF NOT EXISTS oan_livestock_migrations (
    migration_id text PRIMARY KEY,
    applied_at   timestamptz NOT NULL DEFAULT now()
);
SQL

for file in "$dir"/*.sql; do
    [ -e "$file" ] || continue
    id=$(basename "$file" .sql)
    # psql substitutes :'id' only in input it reads, not in -c.
    done=$(echo "SELECT 1 FROM oan_livestock_migrations WHERE migration_id = :'id';" | psql -qtAX -v ON_ERROR_STOP=1 -v id="$id")
    if [ -n "$done" ]; then
        echo "[migrations] $id already applied"
        continue
    fi
    {
        echo "BEGIN;"
        cat "$file"
        echo
        echo "INSERT INTO oan_livestock_migrations (migration_id) VALUES ('$id');"
        echo "COMMIT;"
    } | psql -v ON_ERROR_STOP=1 -qX
    echo "[migrations] $id applied"
done
