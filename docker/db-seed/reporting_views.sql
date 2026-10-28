-- Livestock Registry reporting layer
-- =============================================================================
-- Flattens the register into small, indexed materialized views that the
-- livestock-registry-dashboard-api service reads. That service reads ONLY
-- these views, never the g2p_register_* tables, so a change to the register's
-- schema is absorbed here, in the repository that owns the schema.
--
--   lr_rpt_holding  one row per livestock holding (g2p_register_livestocks):
--                   geography, workflow state, registration date, keeper
--                   gender and the holding's animal totals.
--   lr_rpt_animal   one row per animal line (g2p_register_animals): species,
--                   breed, sex, health and vaccination status and head count,
--                   with the holding's geography and state carried down.
--   lr_rpt_geo      a plain TABLE, not a view: the geography hierarchy copied
--                   from Master Data by the reporting job (see
--                   helm/openg2p-livestock-registry/files/reporting-geo-sync.sh).
--                   Master Data is a separate database, so it cannot be joined
--                   directly.
--
-- Geography
-- ---------
-- A holding stores its region/zone/woreda/kebele as the unit NAMES the intake
-- form wrote ("Oromia", "East Shewa"). The dashboards filter and draw maps by
-- P-code (ET04), so each level is resolved against lr_rpt_geo: by name within
-- the parent resolved one level up, or by id/code when a record already stores
-- one. A level whose own name does not resolve takes the unit Master Data
-- records as the parent of the resolved level below it. An unresolved unit
-- keeps its name and gets a NULL code rather than being dropped, so totals
-- never shrink because of a spelling difference.
--
-- Personal data
-- -------------
-- None. Names, phone numbers, ear tags and national/farmer ids are not carried.
-- A keeper is counted through keeper_key, a one-way hash of the keeper's id, so
-- "how many keepers" is answerable without the id itself.
--
-- Record status
-- -------------
-- Every row is kept, whatever its record_status: the service counts ACTIVE
-- records by default and needs the others for a status breakdown.
--
-- Refresh
-- -------
-- Materialized, so Postgres never updates them on its own. The reporting job
-- re-applies this file on every install/upgrade; a CronJob refreshes them in
-- dependency order (lr_rpt_holding before lr_rpt_animal, which reads it).
-- CONCURRENTLY needs the unique indexes created below.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Geography lookup (filled by the reporting job from Master Data)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lr_rpt_geo (
    level_value_id text PRIMARY KEY,   -- Master Data id, e.g. zone-ET0407
    level          text NOT NULL,      -- region | zone | woreda | kebele
    code           text,               -- P-code, e.g. ET0407
    name           text,               -- unit name, e.g. East Shewa
    parent_ref     text                -- parent's name (or id), as Master Data stores it
);
CREATE INDEX IF NOT EXISTS lr_rpt_geo_level_name_idx ON lr_rpt_geo (level, lower(name));
CREATE INDEX IF NOT EXISTS lr_rpt_geo_level_code_idx ON lr_rpt_geo (level, code);

DROP MATERIALIZED VIEW IF EXISTS lr_rpt_animal CASCADE;
DROP MATERIALIZED VIEW IF EXISTS lr_rpt_holding CASCADE;

-- ---------------------------------------------------------------------------
-- Holdings
-- ---------------------------------------------------------------------------
CREATE MATERIALIZED VIEW lr_rpt_holding AS
WITH animal AS (
    SELECT
        an.link_internal_record_id                          AS holding_id,
        COUNT(*)                                            AS animal_lines,
        SUM(COALESCE(an.quantity, 1))                       AS heads,
        COUNT(DISTINCT an.species)                          AS species_count
    FROM g2p_register_animals an
    WHERE an.record_status = 'ACTIVE'
    GROUP BY an.link_internal_record_id
)
SELECT
    ls.internal_record_id                                   AS holding_id,
    ls.record_status,
    -- The approval workflow's state (DRAFT, KEBELE_APPROVED, ..., VERIFIED).
    -- Older rows carry it in `status` only.
    NULLIF(TRIM(COALESCE(NULLIF(ls.state, ''), ls.status)), '') AS state,
    COALESCE(ls.registration_date, ls.created_at::date)     AS registration_date,
    md5(COALESCE(NULLIF(ls.farmer_uuid, ''), NULLIF(ls.farmer_id, ''),
                 NULLIF(ls.fayda_fan_id, ''), ls.internal_record_id)) AS keeper_key,
    UPPER(NULLIF(TRIM(k.gender), ''))                       AS keeper_gender,

    NULLIF(TRIM(ls.region), '')                             AS region_name,
    NULLIF(TRIM(ls.zone), '')                               AS zone_name,
    NULLIF(TRIM(ls.woreda), '')                             AS woreda_name,
    NULLIF(TRIM(ls.kebele), '')                             AS kebele_name,
    COALESCE(gr.code, pr.code)                              AS region_code,
    COALESCE(gz.code, pz.code)                              AS zone_code,
    COALESCE(gw.code, pw.code)                              AS woreda_code,
    gk.code                                                 AS kebele_code,

    COALESCE(a.animal_lines, 0)::bigint                     AS animal_lines,
    COALESCE(a.heads, 0)::bigint                            AS heads,
    COALESCE(a.species_count, 0)::bigint                    AS species_count
FROM g2p_register_livestocks ls
LEFT JOIN animal a ON a.holding_id = ls.internal_record_id
-- Keeper gender lives on the farmer record. The holding points at it by the
-- farmer's registry id, or by the farmer id the Farmer Registry issued.
LEFT JOIN LATERAL (
    SELECT f.gender
    FROM g2p_register_farmers f
    WHERE f.record_status = 'ACTIVE'
      AND (f.internal_record_id = ls.farmer_uuid
           OR (NULLIF(ls.farmer_id, '') IS NOT NULL
               AND ls.farmer_id IN (f.farmer_id, f.functional_record_id)))
    ORDER BY (f.internal_record_id = ls.farmer_uuid) DESC, f.created_at DESC
    LIMIT 1
) k ON true
LEFT JOIN LATERAL (
    SELECT g.level_value_id, g.code, g.name FROM lr_rpt_geo g
    WHERE g.level = 'region'
      AND (lower(g.name) = lower(TRIM(ls.region)) OR g.level_value_id = TRIM(ls.region)
           OR g.code = regexp_replace(TRIM(ls.region), '^[A-Za-z]+[-_]', ''))
    LIMIT 1
) gr ON true
LEFT JOIN LATERAL (
    SELECT g.level_value_id, g.code, g.name, g.parent_ref FROM lr_rpt_geo g
    WHERE g.level = 'zone'
      AND (g.level_value_id = TRIM(ls.zone)
           OR g.code = regexp_replace(TRIM(ls.zone), '^[A-Za-z]+[-_]', '')
           OR (lower(g.name) = lower(TRIM(ls.zone))
               AND (gr.level_value_id IS NULL OR lower(g.parent_ref) IN (lower(gr.name), lower(gr.level_value_id)))))
    ORDER BY (lower(g.parent_ref) IN (lower(gr.name), lower(gr.level_value_id))) DESC NULLS LAST
    LIMIT 1
) gz ON true
LEFT JOIN LATERAL (
    SELECT g.level_value_id, g.code, g.name, g.parent_ref FROM lr_rpt_geo g
    WHERE g.level = 'woreda'
      AND (g.level_value_id = TRIM(ls.woreda)
           OR g.code = regexp_replace(TRIM(ls.woreda), '^[A-Za-z]+[-_]', '')
           OR (lower(g.name) = lower(TRIM(ls.woreda))
               AND (gz.level_value_id IS NULL OR lower(g.parent_ref) IN (lower(gz.name), lower(gz.level_value_id)))))
    ORDER BY (lower(g.parent_ref) IN (lower(gz.name), lower(gz.level_value_id))) DESC NULLS LAST
    LIMIT 1
) gw ON true
LEFT JOIN LATERAL (
    SELECT g.level_value_id, g.code, g.name, g.parent_ref FROM lr_rpt_geo g
    WHERE g.level = 'kebele'
      AND (g.level_value_id = TRIM(ls.kebele)
           OR g.code = regexp_replace(TRIM(ls.kebele), '^[A-Za-z]+[-_]', '')
           OR (lower(g.name) = lower(TRIM(ls.kebele))
               AND (gw.level_value_id IS NULL OR lower(g.parent_ref) IN (lower(gw.name), lower(gw.level_value_id)))))
    ORDER BY (lower(g.parent_ref) IN (lower(gw.name), lower(gw.level_value_id))) DESC NULLS LAST
    LIMIT 1
) gk ON true
-- A level that did not resolve by its own name takes the unit Master Data
-- names as the parent of the resolved level below it: a woreda found by name
-- gives its zone even when the holding spells the zone differently.
LEFT JOIN LATERAL (
    SELECT g.level_value_id, g.code, g.name, g.parent_ref FROM lr_rpt_geo g
    WHERE gw.level_value_id IS NULL AND gk.parent_ref IS NOT NULL AND g.level = 'woreda'
      AND (g.level_value_id = gk.parent_ref OR lower(g.name) = lower(gk.parent_ref))
    LIMIT 1
) pw ON true
LEFT JOIN LATERAL (
    SELECT g.level_value_id, g.code, g.name, g.parent_ref FROM lr_rpt_geo g
    WHERE gz.level_value_id IS NULL AND COALESCE(gw.parent_ref, pw.parent_ref) IS NOT NULL AND g.level = 'zone'
      AND (g.level_value_id = COALESCE(gw.parent_ref, pw.parent_ref)
           OR lower(g.name) = lower(COALESCE(gw.parent_ref, pw.parent_ref)))
    LIMIT 1
) pz ON true
LEFT JOIN LATERAL (
    SELECT g.code FROM lr_rpt_geo g
    WHERE gr.level_value_id IS NULL AND COALESCE(gz.parent_ref, pz.parent_ref) IS NOT NULL AND g.level = 'region'
      AND (g.level_value_id = COALESCE(gz.parent_ref, pz.parent_ref)
           OR lower(g.name) = lower(COALESCE(gz.parent_ref, pz.parent_ref)))
    LIMIT 1
) pr ON true;

CREATE UNIQUE INDEX lr_rpt_holding_pk ON lr_rpt_holding (holding_id);
CREATE INDEX lr_rpt_holding_geo_idx ON lr_rpt_holding (region_code, zone_code, woreda_code, kebele_code);
CREATE INDEX lr_rpt_holding_date_idx ON lr_rpt_holding (registration_date);

-- ---------------------------------------------------------------------------
-- Animals
-- ---------------------------------------------------------------------------
-- An animal line is one animal, except for poultry and beehives, which are
-- captured as one line with a quantity. `heads` is what to SUM; counting rows
-- counts lines.
CREATE MATERIALIZED VIEW lr_rpt_animal AS
SELECT
    an.internal_record_id                                   AS animal_id,
    h.holding_id,
    an.record_status,
    h.record_status                                         AS holding_record_status,
    h.state                                                 AS holding_state,
    COALESCE(an.registration_date, an.created_at::date, h.registration_date) AS registration_date,
    h.keeper_key,

    NULLIF(TRIM(an.species), '')                            AS species,
    COALESCE(NULLIF(TRIM(sp.value_display), ''), NULLIF(TRIM(an.species), '')) AS species_name,
    NULLIF(TRIM(an.breed), '')                              AS breed,
    COALESCE(NULLIF(TRIM(br.value_display), ''), NULLIF(TRIM(an.breed), ''))   AS breed_name,
    UPPER(NULLIF(TRIM(an.gender), ''))                      AS sex,
    UPPER(NULLIF(TRIM(an.health_status), ''))               AS health_status,
    UPPER(NULLIF(TRIM(an.vaccination_status), ''))          AS vaccination_status,
    COALESCE(an.quantity, 1)::bigint                        AS heads,

    h.region_name, h.zone_name, h.woreda_name, h.kebele_name,
    h.region_code, h.zone_code, h.woreda_code, h.kebele_code
FROM g2p_register_animals an
JOIN lr_rpt_holding h ON h.holding_id = an.link_internal_record_id
LEFT JOIN g2p_attribute_values sp ON sp.value_id = an.species
LEFT JOIN g2p_attribute_values br ON br.value_id = an.breed;

CREATE UNIQUE INDEX lr_rpt_animal_pk ON lr_rpt_animal (animal_id);
CREATE INDEX lr_rpt_animal_holding_idx ON lr_rpt_animal (holding_id);
CREATE INDEX lr_rpt_animal_species_idx ON lr_rpt_animal (species);
CREATE INDEX lr_rpt_animal_geo_idx ON lr_rpt_animal (region_code, zone_code, woreda_code, kebele_code);
