#!/bin/sh
# Copy the geography hierarchy from Master Data into lr_rpt_geo.
#
# The livestock reporting views resolve a holding's region/zone/woreda/kebele
# names to P-codes against lr_rpt_geo (see reporting_views.sql). Master Data
# is a separate database, so the hierarchy is copied rather than joined. It is
# small (tens of thousands of rows) and replaced whole, in one transaction, so a
# reader never sees a half-filled table.
#
# Environment:
#   PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD   the registry database (libpq)
#   MDS_DB                                        Master Data database; unset or
#                                                 empty skips the copy
#   MDS_PGHOST MDS_PGPORT MDS_PGUSER MDS_PGPASSWORD
#                                                 Master Data connection; host and
#                                                 port default to the registry's
#
# Skipping is not a failure: the views still build, with NULL codes, and the
# dashboards fall back to unit names. It is reported on stderr.
set -eu

if [ -z "${MDS_DB:-}" ]; then
    echo "[reporting-geo-sync] MDS_DB not set; lr_rpt_geo left as it is" >&2
    exit 0
fi

# The table is normally created by reporting_views.sql; create it here too so
# the sync can run first.
psql -v ON_ERROR_STOP=1 -qX <<'SQL'
CREATE TABLE IF NOT EXISTS lr_rpt_geo (
    level_value_id text PRIMARY KEY,
    level          text NOT NULL,
    code           text,
    name           text,
    parent_ref     text
);
SQL

# level_id is 'level-<name>' and level_value_id '<level>-<P-code>' in the
# Ethiopia pack; both prefixes are stripped generically rather than by name.
PGHOST="${MDS_PGHOST:-${PGHOST:-}}" PGPORT="${MDS_PGPORT:-${PGPORT:-5432}}" \
PGDATABASE="$MDS_DB" PGUSER="${MDS_PGUSER:-}" PGPASSWORD="${MDS_PGPASSWORD:-}" \
psql -v ON_ERROR_STOP=1 -qX -c "\copy (
    SELECT v.level_value_id,
           lower(COALESCE(l.level_mnemonic, regexp_replace(v.level_id, '^level-', ''))),
           substr(v.level_value_id, strpos(v.level_value_id, '-') + 1),
           v.level_value_mnemonic,
           v.parent_level_value_id
    FROM g2p_geo_level_values v
    LEFT JOIN g2p_geo_levels l ON l.level_id = v.level_id
) TO STDOUT" \
| psql -v ON_ERROR_STOP=1 -qX -1 -c "TRUNCATE lr_rpt_geo" -c "\copy lr_rpt_geo FROM STDIN"

psql -qtAX -c "SELECT '[reporting-geo-sync] lr_rpt_geo: ' || count(*) || ' units' FROM lr_rpt_geo"
