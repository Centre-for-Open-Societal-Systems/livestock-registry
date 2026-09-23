-- Patch for already-seeded environments (and fresh ones: the seed runs every
-- patch file on every deploy, in name order — after
-- patch_attribute_value_species_configs_table.sql, which creates the table).
--
-- Poultry and Beehive have no ear to attach a tag to, so they are registered
-- with a Secondary Identifier (leg band, wing tag, hive number, ...) and a
-- Quantity (head count) instead of an Ear Tag, and their Sex can be Mixed.
-- That is what the species' "Requires Ear Tag" (off) / "Flock / Group Species"
-- (on) config means (see domain_validation_utils.get_species_config). Without a
-- row a species defaults to "requires an ear tag, not a flock", which is why
-- neither species could be registered without one.
--
-- ON CONFLICT DO NOTHING: a species someone has already configured in
-- Configuration > Attribute Values is left exactly as they set it.
INSERT INTO "public"."g2p_attribute_value_species_configs" ("value_id", "requires_ear_tag", "is_flock_species")
SELECT v.value_id, FALSE, TRUE
FROM "public"."g2p_attribute_values" v
WHERE v.value_id IN ('LIVESTOCK_SPECIES_POULTRY', 'LIVESTOCK_SPECIES_BEEHIVE')
ON CONFLICT ("value_id") DO NOTHING;
