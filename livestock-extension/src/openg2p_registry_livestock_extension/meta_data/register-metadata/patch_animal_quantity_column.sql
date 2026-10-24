-- Patch for already-created environments only.
--
-- Adds `quantity` (G2PAnimal, models/animal.py) — the head count for a
-- _FLOCK_SPECIES row (poultry, beehive; see
-- G2PRegisterDomainServiceAnimal._FLOCK_SPECIES / _validate_quantity), which
-- stands for a whole flock/hive rather than one individually-tagged animal.
-- A fresh install picks this up for free from the SQLAlchemy model at
-- table-creation time; an environment whose g2p_register_animals /
-- g2p_register_history_animals / g2p_intake_form_animals tables already
-- exist needs it added in place, which is what this does, idempotently
-- (ADD COLUMN IF NOT EXISTS) — same pattern as
-- patch_vital_events_offspring_ear_tags.sql.

ALTER TABLE g2p_register_animals
    ADD COLUMN IF NOT EXISTS quantity INTEGER;

ALTER TABLE g2p_register_history_animals
    ADD COLUMN IF NOT EXISTS quantity INTEGER;

ALTER TABLE g2p_intake_form_animals
    ADD COLUMN IF NOT EXISTS quantity INTEGER;
