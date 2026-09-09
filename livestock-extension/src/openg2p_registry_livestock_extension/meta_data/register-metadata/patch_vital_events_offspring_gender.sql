-- Patch for already-seeded environments only.
--
-- Adds the two columns G2PVitalEvent (models/vital_event.py) gained after this
-- was first deployed: offspring_gender and offspring_generated. A fresh
-- install picks these up for free from the SQLAlchemy model at table-creation
-- time; an environment whose g2p_register_vital_events / _history_ / intake
-- form tables already exist needs them added in place, which is what this
-- file does, idempotently (ADD COLUMN IF NOT EXISTS), across all three
-- vital-event tables.
--
-- offspring_gender: the sex of a Birth event's newborn(s) — see the model's
-- own comment for why nothing else can supply this for
-- G2PRegisterDomainServiceVitalEvent.post_approve to pass on to the new
-- Animal row(s) it creates (G2PRegisterAnimal.gender is G2R-135 mandatory).
-- offspring_generated: guards that same post_approve step against creating
-- the offspring Animal rows twice.

ALTER TABLE g2p_register_vital_events
    ADD COLUMN IF NOT EXISTS offspring_gender VARCHAR,
    ADD COLUMN IF NOT EXISTS offspring_generated BOOLEAN;

ALTER TABLE g2p_register_history_vital_events
    ADD COLUMN IF NOT EXISTS offspring_gender VARCHAR,
    ADD COLUMN IF NOT EXISTS offspring_generated BOOLEAN;

ALTER TABLE g2p_intake_form_vital_events
    ADD COLUMN IF NOT EXISTS offspring_gender VARCHAR,
    ADD COLUMN IF NOT EXISTS offspring_generated BOOLEAN;
