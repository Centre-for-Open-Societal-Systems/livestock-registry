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
#
# Second post-seed step: the AWE approver rules. The seed writes the four
# http rules with the local compose address (http://staff-api:8000) and the
# default secret. On a cluster AWE cannot reach that name, so the rules are
# rewritten here to this deployment's own staff-api base URL and secret:
#   APPROVER_RESOLVER_BASE_URL  — explicit base (scheme://host[:port]); else
#                                 derived from AWE_CALLBACK_CALLER_SERVICE when
#                                 that is a URL (same host serves the resolver
#                                 and the webhook); else http://staff-api:8000
#   APPROVER_RESOLVER_SECRET    — must equal staff-api's APPROVER_RESOLVER_SECRET
#                                 (default livestock-approver-resolver-secret)
# Runs only when the AWE seed ran (AWE_DB_SEED_ENABLED=true, AWE_PG* set) and
# is idempotent: same inputs, same rows.
set -u
/seed/entrypoint.sh "$@"
rc=$?

load_ethiopia_geo() {
  GEO_FILE="/seed/geo/ethiopia_geo_seed.sql.gz"
  if [ "${LOAD_ETHIOPIA_GEO:-true}" != "true" ]; then
    echo "[db-seed] Ethiopia geo: skipped (LOAD_ETHIOPIA_GEO=${LOAD_ETHIOPIA_GEO})."
    return
  fi
  if [ -z "${MD_PGHOST:-}" ] || [ -z "${MD_PGDATABASE:-}" ]; then
    echo "[db-seed] Ethiopia geo: skipped (MD_PGHOST/MD_PGDATABASE not set)."
    return
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
}

rewrite_approver_rules() {
  if [ "${AWE_DB_SEED_ENABLED:-false}" != "true" ]; then
    echo "[db-seed] approver-resolver rules: skipped (AWE_DB_SEED_ENABLED=${AWE_DB_SEED_ENABLED:-false})."
    return
  fi
  if [ -z "${AWE_PGHOST:-}" ] || [ -z "${AWE_PGDATABASE:-}" ]; then
    echo "[db-seed] approver-resolver rules: skipped (AWE_PGHOST/AWE_PGDATABASE not set)."
    return
  fi
  base="${APPROVER_RESOLVER_BASE_URL:-}"
  if [ -z "$base" ]; then
    case "${AWE_CALLBACK_CALLER_SERVICE:-}" in
      http://*|https://*)
        # scheme://host[:port] of the webhook URL: the resolver lives on the same staff-api.
        base=$(printf '%s' "$AWE_CALLBACK_CALLER_SERVICE" | sed -E 's#^(https?://[^/]+).*$#\1#') ;;
      *)
        base="http://staff-api:8000" ;;
    esac
  fi
  base=$(printf '%s' "$base" | sed -E 's#/+$##')
  secret="${APPROVER_RESOLVER_SECRET:-livestock-approver-resolver-secret}"
  export PGHOST="$AWE_PGHOST" PGPORT="${AWE_PGPORT:-5432}" PGDATABASE="$AWE_PGDATABASE" PGUSER="${AWE_PGUSER:-}" PGPASSWORD="${AWE_PGPASSWORD:-}"
  echo "[db-seed] approver-resolver rules: pointing the http rules at ${base}/livestock/approver-resolver?level=<level>&secret=*** ..."
  n=$(psql -At -v ON_ERROR_STOP=1 -v base="$base" -v secret="$secret" <<'SQL'
WITH changed AS (
  UPDATE approver_rule
     SET rule_value = jsonb_set(rule_value::jsonb, '{url}',
           to_jsonb(:'base' || '/livestock/approver-resolver?level='
                    || substring(rule_value::jsonb->>'url' from 'level=([a-z]+)')
                    || '&secret=' || :'secret'))::json
   WHERE rule_type = 'http'
     AND rule_value::jsonb->>'url' LIKE '%/livestock/approver-resolver%'
     AND rule_value::jsonb->>'url' <> (:'base' || '/livestock/approver-resolver?level='
                    || substring(rule_value::jsonb->>'url' from 'level=([a-z]+)')
                    || '&secret=' || :'secret')
  RETURNING 1)
SELECT count(*) FROM changed;
SQL
  ) || { echo "[db-seed] approver-resolver rules: FAILED (see errors above) — AWE will not find approvers until the rule URLs point at this staff-api."; return; }
  total=$(psql -At -c "SELECT count(*) FROM approver_rule WHERE rule_type='http' AND rule_value::jsonb->>'url' LIKE '%/livestock/approver-resolver%';" 2>/dev/null || echo "?")
  echo "[db-seed] approver-resolver rules: ${n} rewritten, ${total} in place."
}

# Third post-seed step: the File Import partner. Every ingest is routed by the
# sender id in its envelope to a row of master_data.g2p_partners, and File Import
# (New Intake -> File Import) sends as the celery worker's import_file_sender_id,
# "Staff Portal" by default. Nothing seeded that row, so every imported row
# failed with PARTNER_NOT_REGISTERED. Idempotent (keyed on the mnemonic).
load_code_lists() {
  # The livestock code lists (species, breed, vaccine, disease, approval
  # status) live in Master Data since registry-platform 1.2: the registry reads
  # them over the Master Data API and keeps no copy. Upsert them into the Master
  # Data database the geo load already writes to (MD_PG*), so a fresh and an
  # upgraded environment end up with the same lists. LOAD_CODE_LISTS=false skips.
  if [ "${LOAD_CODE_LISTS:-true}" != "true" ]; then
    echo "[db-seed] code lists: skipped (LOAD_CODE_LISTS=${LOAD_CODE_LISTS})."
    return
  fi
  if [ -z "${MD_PGHOST:-}" ] || [ -z "${MD_PGDATABASE:-}" ]; then
    echo "[db-seed] code lists: skipped (MD_PGHOST/MD_PGDATABASE not set)."
    return
  fi
  dir=/seed/master_data/code_lists
  if [ ! -d "$dir" ]; then
    echo "[db-seed] code lists: no $dir in this image, skipped."
    return
  fi
  echo "[db-seed] code lists: loading into ${MD_PGDATABASE}@${MD_PGHOST}:${MD_PGPORT:-5432} ..."
  export PGHOST="$MD_PGHOST" PGPORT="${MD_PGPORT:-5432}" PGDATABASE="$MD_PGDATABASE" PGUSER="${MD_PGUSER:-}" PGPASSWORD="${MD_PGPASSWORD:-}"
  for f in $(find "$dir" -name '*.sql' -type f | sort); do
    echo "[db-seed]   -> $(basename "$f")"
    psql -v ON_ERROR_STOP=1 -q -f "$f" || { echo "[db-seed] code lists: FAILED on $(basename "$f")"; return 1; }
  done
  psql -At -c "select '[db-seed] code lists: '||count(*)||' values in '||count(distinct attribute_id)||' lists' from g2p_attribute_values where attribute_id in ('LIVESTOCK_SPECIES','LIVESTOCK_BREED','VACCINE_TYPE','LIVESTOCK_DISEASE','APPROVAL_STATUS');"
}

register_import_partner() {
  if [ -z "${MD_PGHOST:-}" ] || [ -z "${MD_PGDATABASE:-}" ]; then
    echo "[db-seed] import partner: skipped (MD_PGHOST/MD_PGDATABASE not set)."
    return
  fi
  # registry-platform 1.2 validates the ingest sender against Partner
  # Management (no partner table in Master Data); with Partner Management not
  # configured the sender is accepted as is. Only an older Master Data that
  # still has the table gets the rows.
  if ! PGHOST="$MD_PGHOST" PGPORT="${MD_PGPORT:-5432}" PGDATABASE="$MD_PGDATABASE" PGUSER="${MD_PGUSER:-}" PGPASSWORD="${MD_PGPASSWORD:-}" psql -At -c "select to_regclass('public.g2p_partners')" 2>/dev/null | grep -q g2p_partners; then
    echo "[db-seed] import partner: Master Data has no g2p_partners table (Partner Management owns partners on registry-platform 1.2); skipped."
    return
  fi
  export PGHOST="$MD_PGHOST" PGPORT="${MD_PGPORT:-5432}" PGDATABASE="$MD_PGDATABASE" PGUSER="${MD_PGUSER:-}" PGPASSWORD="${MD_PGPASSWORD:-}"
  # Two senders: File Import ("Staff Portal", the celery worker's
  # import_file_sender_id) and the ODK connector, whose envelope carries
  # sender_id "Livestock" (odk_ingest_hooks.py; the connector pipeline's
  # g2p_sender_id in local/postgres/seed_connector_pipelines.sql).
  for mnemonic in "${IMPORT_FILE_SENDER_ID:-Staff Portal}" "${ODK_SENDER_ID:-Livestock}"; do
    if psql -v ON_ERROR_STOP=1 -q -v m="$mnemonic" <<'SQL'
INSERT INTO g2p_partners (partner_id, partner_mnemonic, keymanager_reference_id, is_active)
SELECT md5('livestock-import-partner:' || :'m'), :'m', 'livestock-import:' || :'m', true
WHERE NOT EXISTS (SELECT 1 FROM g2p_partners WHERE partner_mnemonic = :'m');
SQL
    then
      echo "[db-seed] import partner: '${mnemonic}' registered."
    else
      echo "[db-seed] import partner: '${mnemonic}' FAILED (see errors above) — its ingests will fail with PARTNER_NOT_REGISTERED."
    fi
  done
}

load_ethiopia_geo
load_code_lists
rewrite_approver_rules
register_import_partner
exit $rc
