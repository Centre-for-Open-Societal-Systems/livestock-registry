#!/bin/sh
# Livestock db-seed entrypoint: the platform's own seed first, then the real
# Ethiopia geo hierarchy into master_data.
#
# The platform image's /seed/entrypoint.sh loads this registry's metadata into
# the registry DB and, when LOAD_GEO_DATA=true, its own generic sample geo
# (country/region/district/ward/village, levels l0..l4) into master_data. This
# registry's Location section asks for level ids level-region / level-zone /
# level-woreda / level-kebele, so that generic set leaves the dropdowns EMPTY
# (seen on the dev cluster, 2026-09-17). Keep LOAD_GEO_DATA=false and let this
# step load the real hierarchy instead — the same file the local compose stack
# has always used (docker/db-seed/geo/ethiopia_geo_seed.sql.gz).
#
# Idempotent: the SQL uses ON CONFLICT DO NOTHING keyed on level_value_mnemonic,
# so the unique index it relies on is created first (IF NOT EXISTS). Needs the
# same MD_PG* variables the platform seed already receives (chart job and
# compose both set them); skipped with a notice when they are absent. A failure
# here is reported loudly but does not fail the job — the registry metadata
# loaded before it must stay in place.
#
# An environment that ever ran with LOAD_GEO_DATA=true (the dev cluster did)
# still holds the platform's sample geo, and the two sets cannot coexist: its
# level mnemonic "region" collides with ours (g2p_geo_levels.level_mnemonic is
# unique) and its village names repeat, which blocks the unique index above.
# That set is the platform's demo data (openg2p-data/geo/geo.csv: country >
# region > district > ward > village, level ids l0..l4); nothing in this
# registry references it and LOAD_GEO_DATA=false keeps it from coming back, so
# it is removed first — but only when it is exactly that set, level ids AND
# mnemonics, so real data under other ids is never touched.
set -u
/seed/entrypoint.sh "$@"
rc=$?

GEO_FILE="/seed/geo/ethiopia_geo_seed.sql.gz"
if [ "${LOAD_ETHIOPIA_GEO:-true}" != "true" ]; then
  echo "[db-seed] Ethiopia geo: skipped (LOAD_ETHIOPIA_GEO=${LOAD_ETHIOPIA_GEO})."
  exit $rc
fi
if [ -z "${MD_PGHOST:-}" ] || [ -z "${MD_PGDATABASE:-}" ]; then
  echo "[db-seed] Ethiopia geo: skipped (MD_PGHOST/MD_PGDATABASE not set)."
  exit $rc
fi
echo "[db-seed] Ethiopia geo: loading into ${MD_PGDATABASE}@${MD_PGHOST}:${MD_PGPORT:-5432} ..."
export PGHOST="$MD_PGHOST" PGPORT="${MD_PGPORT:-5432}" PGDATABASE="$MD_PGDATABASE" PGUSER="${MD_PGUSER:-}" PGPASSWORD="${MD_PGPASSWORD:-}"

sample_levels=$(psql -At -c "SELECT count(*) FROM g2p_geo_levels WHERE (level_id, level_mnemonic) IN (('l0','country'),('l1','region'),('l2','district'),('l3','ward'),('l4','village'));" 2>/dev/null || echo 0)
if [ "$sample_levels" = "5" ]; then
  sample_values=$(psql -At -c "SELECT count(*) FROM g2p_geo_level_values WHERE level_id IN ('l0','l1','l2','l3','l4');" 2>/dev/null || echo "?")
  echo "[db-seed] Ethiopia geo: removing the platform's sample geo first (levels l0..l4, ${sample_values} values) — it cannot coexist with the real hierarchy."
  # Leaves first, one transaction: nothing is half-removed if a statement fails.
  if ! psql -v ON_ERROR_STOP=1 -1 -q <<'SQL'
DELETE FROM g2p_geo_level_values WHERE level_id = 'l4';
DELETE FROM g2p_geo_level_values WHERE level_id = 'l3';
DELETE FROM g2p_geo_level_values WHERE level_id = 'l2';
DELETE FROM g2p_geo_level_values WHERE level_id = 'l1';
DELETE FROM g2p_geo_level_values WHERE level_id = 'l0';
DELETE FROM g2p_geo_levels WHERE level_id IN ('l4','l3','l2','l1','l0');
SQL
  then
    echo "[db-seed] Ethiopia geo: could not remove the sample geo (see errors above); the load below will most likely fail."
  fi
fi

if psql -v ON_ERROR_STOP=1 -q -c "CREATE UNIQUE INDEX IF NOT EXISTS ux_geo_level_values_mnemonic ON g2p_geo_level_values(level_value_mnemonic);" \
   && gunzip -c "$GEO_FILE" | psql -v ON_ERROR_STOP=1 -q; then
  psql -At -c "select '[db-seed] Ethiopia geo: levels='||(select count(*) from g2p_geo_levels where level_id like 'level-%')||' values='||(select count(*) from g2p_geo_level_values v join g2p_geo_levels l on l.level_id=v.level_id where l.level_id like 'level-%');"
else
  echo "[db-seed] Ethiopia geo: FAILED (see errors above) — Location dropdowns will be empty until it is loaded. Typical causes: another geo set already in master_data whose level mnemonics (e.g. 'region') or value names collide with this one."
fi
exit $rc
