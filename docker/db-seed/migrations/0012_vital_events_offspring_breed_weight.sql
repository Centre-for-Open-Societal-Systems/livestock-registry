-- Patch for already-seeded environments: the optional breed and birth weight
-- of a Birth event's offspring (G2PVitalEvent.offspring_breed /
-- offspring_weight, models/vital_event.py). A fresh install gets the columns
-- from the model; an existing database gets them here, on the register, its
-- history and the intake tables. Safe to re-run (ADD COLUMN IF NOT EXISTS).

ALTER TABLE g2p_register_vital_events
    ADD COLUMN IF NOT EXISTS offspring_breed VARCHAR,
    ADD COLUMN IF NOT EXISTS offspring_weight DOUBLE PRECISION;

ALTER TABLE g2p_register_history_vital_events
    ADD COLUMN IF NOT EXISTS offspring_breed VARCHAR,
    ADD COLUMN IF NOT EXISTS offspring_weight DOUBLE PRECISION;

ALTER TABLE g2p_intake_form_vital_events
    ADD COLUMN IF NOT EXISTS offspring_breed VARCHAR,
    ADD COLUMN IF NOT EXISTS offspring_weight DOUBLE PRECISION;
