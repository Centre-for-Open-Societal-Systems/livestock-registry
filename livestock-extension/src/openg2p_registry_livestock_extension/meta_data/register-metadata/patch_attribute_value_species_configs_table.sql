-- Patch for already-created environments only.
--
-- Creates g2p_attribute_value_species_configs — NOT a livestock-extension
-- table, a CORE one (openg2p_registry_core.models.G2PAttributeValueSpeciesConfig,
-- added via docker/staff-api/core-patches/apply_patches.py "Fix 4", the same
-- way G2PAttributeValueSchedule already backs per-value vaccine scheduling).
-- It's the backing store for Configuration > Attributes > Species > Edit >
-- "Requires Ear Tag" / "Flock / Group Species" — see
-- domain_validation_utils.get_species_config, the only reader, in the
-- livestock extension (this table's only consumer today, hence the patch
-- living here rather than in some shared core migrations directory that
-- doesn't exist in this project).
--
-- A brand-new environment gets this table for free from SQLAlchemy at
-- container startup ("Migrating extensions database" in the staff-api
-- logs) the same way g2p_attribute_value_schedules does. An environment
-- whose database already existed before this patch was added did NOT pick
-- the new table up automatically on a plain container restart in practice
-- (verified directly against the running livestock-postgres-1 on
-- 2026-09-10 — table absent after a full staff-api rebuild+restart, despite
-- the "without Role" schedule table having been created that same way
-- previously) — so this statement creates it explicitly, idempotently
-- (CREATE TABLE IF NOT EXISTS), matching the model's columns exactly.

CREATE TABLE IF NOT EXISTS g2p_attribute_value_species_configs (
    value_id VARCHAR PRIMARY KEY,
    requires_ear_tag BOOLEAN,
    is_flock_species BOOLEAN
);
