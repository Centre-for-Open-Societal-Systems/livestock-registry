-- Patch for already-seeded environments only.
--
-- Adds offspring_ear_tags (G2PVitalEvent, models/vital_event.py) — the ear
-- tag(s) reserved for a Birth event's newborn(s) the moment the Vital Event
-- Details row is saved as part of an intake-form section (the "Next" step),
-- via G2PRegisterDomainServiceVitalEvent.post_intake_upsert, rather than only
-- once the submission is later approved/ingested. A fresh install picks this
-- up for free from the SQLAlchemy model at table-creation time; an
-- environment whose g2p_register_vital_events / _history_ / intake form
-- tables already exist needs it added in place, which is what this file
-- does, idempotently (ADD COLUMN IF NOT EXISTS), across all three
-- vital-event tables — same pattern as patch_vital_events_offspring_gender.sql.

ALTER TABLE g2p_register_vital_events
    ADD COLUMN IF NOT EXISTS offspring_ear_tags VARCHAR;

ALTER TABLE g2p_register_history_vital_events
    ADD COLUMN IF NOT EXISTS offspring_ear_tags VARCHAR;

ALTER TABLE g2p_intake_form_vital_events
    ADD COLUMN IF NOT EXISTS offspring_ear_tags VARCHAR;
