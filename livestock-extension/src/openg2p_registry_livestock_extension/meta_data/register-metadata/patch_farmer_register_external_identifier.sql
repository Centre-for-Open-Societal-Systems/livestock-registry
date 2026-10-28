-- The Farmer register of this registry is a reference to the Farmer Registry:
-- every Farmer row is created from a signed Farmer-reference lookup and carries
-- the Farmer Registry's functional id (FR-...). The registry must therefore not
-- generate functional ids for it, otherwise the native Farmer-reference ADD
-- (farmer_reference/native.py approve_register) refuses the approved change
-- request with FARMER_REFERENCE_EXTERNAL_IDENTIFIER_CONFIGURATION_REQUIRED and
-- the AWE decision webhook keeps failing. The definitions seed is an insert with
-- ON CONFLICT DO NOTHING, so an existing database keeps its old value unless it
-- is updated here. Idempotent: a second run changes nothing.
UPDATE "public"."g2p_register_definitions"
   SET "functional_id_generation_required" = FALSE
 WHERE "register_id" = 'f9c6a359-9563-5a43-b0fe-6c7e452037a3'
   AND "functional_id_generation_required" IS DISTINCT FROM FALSE;
