-- G2R-134: Configure deduplication for the Livestock Registry.
--
-- The platform's deduplication engine compares every new intake submission /
-- change request against existing records using the per-register
-- `deduplicate_schema` (which fields, exact or fuzzy, and their weight) and
-- flags candidates whose weighted score reaches `dedup_threshold_score`.
-- It runs ONLY for registers with register_purpose = REGISTER (Farmer and
-- Livestock); child TABLE registers (Animal, events, ...) are never scored, so
-- their config is cleared here — duplicates there are blocked by the domain
-- services' validations instead (ear tag + species + breed, duplicate events).
--
-- The seed files (g2p_register_schemas.sql, g2p_register_definitions.sql) carry
-- the same values for a fresh database; this patch brings an EXISTING database
-- (local, staging, test) up to date. Safe to run more than once.

-- Livestock holding: "the same farmer registered a second holding".
-- farmer_id / fayda_fan_id are the two identifiers; farmer_name tolerates
-- spelling differences; woreda only supports. oan_id and registration_date are
-- dropped: oan_id is never populated by the form, and both only lowered the
-- score of genuine duplicates.
UPDATE "public"."g2p_register_schemas"
SET deduplicate_schema = '[
  {"field_name": "farmer_id",    "match_type": "exact", "weight": 0.35},
  {"field_name": "fayda_fan_id", "match_type": "exact", "weight": 0.35},
  {"field_name": "farmer_name",  "match_type": "fuzzy", "weight": 0.20, "similarity_threshold": 0.8},
  {"field_name": "woreda",       "match_type": "exact", "weight": 0.10}
]'::json
WHERE register_id = '997676d3-7008-59f9-b23e-613ad79bbb08';

-- Farmer: "the same person registered twice", including with a typo in the
-- name or a differing farmer code. Fayda (national ID) is the strongest
-- signal, then the farmer code, then fuzzy names, then DOB and mobile.
-- NOTE: the platform's intake dedup worker only scores sections whose
-- register_id equals the submission's own register (see
-- deduplication_intake_forms_vs_register_worker.py). The Farmer section
-- embedded in the Livestock intake form therefore is NOT scored; this config
-- takes effect for a Farmer intake form (register_id = Farmer) and for change
-- requests on Farmer records.
UPDATE "public"."g2p_register_schemas"
SET deduplicate_schema = '[
  {"field_name": "fayda_fan_id",  "match_type": "exact", "weight": 0.30},
  {"field_name": "farmer_id",     "match_type": "exact", "weight": 0.25},
  {"field_name": "first_name",    "match_type": "fuzzy", "weight": 0.15, "similarity_threshold": 0.8},
  {"field_name": "last_name",     "match_type": "fuzzy", "weight": 0.10, "similarity_threshold": 0.8},
  {"field_name": "date_of_birth", "match_type": "exact", "weight": 0.10},
  {"field_name": "mobile_number", "match_type": "exact", "weight": 0.10}
]'::json
WHERE register_id = 'f9c6a359-9563-5a43-b0fe-6c7e452037a3';

-- Child TABLE registers: the engine never runs for them; clear the dead config
-- so nobody mistakes it for an active rule.
UPDATE "public"."g2p_register_schemas"
SET deduplicate_schema = '[]'::json
WHERE register_id IN (
  '041a9f79-2142-548a-a15b-a4c76fc9f6f7',  -- Animal
  'a40e4a02-1b82-5b31-89df-71624bd96545',  -- HealthEvent
  '51c1f6d6-856a-5e2f-84e9-ff5abdc4fb75',  -- Vaccination
  '76811bf6-07df-5ed4-9466-13b782f627fe',  -- VitalEvent
  '192c08b0-5403-5167-968a-2676d4af2879',  -- Breeding
  '5cdf80bf-0cdb-53e4-a4cf-71927f809250',  -- VaccineSchedule
  '0fd11be9-83d7-5d2e-9dea-e0653add7059',  -- ImportBatch
  '6a3699f0-4b17-5d0d-b8b3-4822bfdab7aa'   -- AuditLog
);

-- Thresholds (score 0-100 at which a candidate is flagged for review).
-- Livestock 55: one identifier (farmer_id or fayda, 35) plus the same farmer
-- name (20) flags; both identifiers (70) flag; a lone matching identifier (35)
-- or a name alone (20) does not.
-- Farmer 55: Gen1-migrated farmers carry no DOB/mobile (those fields did not
-- exist in Gen1's livestock module), which caps their reachable score at 80;
-- same fayda + similar names must still clear the bar.
UPDATE "public"."g2p_register_definitions"
SET dedup_is_enabled = TRUE, dedup_threshold_score = 55
WHERE register_id = '997676d3-7008-59f9-b23e-613ad79bbb08';

UPDATE "public"."g2p_register_definitions"
SET dedup_is_enabled = TRUE, dedup_threshold_score = 55
WHERE register_id = 'f9c6a359-9563-5a43-b0fe-6c7e452037a3';
