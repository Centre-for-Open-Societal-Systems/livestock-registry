-- Patch for already-seeded environments only.
--
-- Adds the `age` column (G2R-57 "auto-fill: entering an Ear Tag
-- auto-populates Species and Age") that G2PHealthEvent, G2PVaccination,
-- G2PVitalEvent and G2PBreeding (register_domain/models/*.py) gained after
-- those tables were first created. A fresh install picks this up for free
-- from the SQLAlchemy models at table-creation time; an environment whose
-- tables already exist needs it added in place, which is what this file
-- does, idempotently (ADD COLUMN IF NOT EXISTS), across the register,
-- history and intake-form variant of each of the four event tables.
--
-- Unlike species (looked up server-side), age is a display value copied
-- client-side from the matched Livestock Details row's own age-from-DOB
-- computation (see DialogTableWidget.tsx's widget-autofill / widget-age-
-- from-date) at the moment an Ear Tag is selected — there is no
-- server-side recomputation for it here, since these event records are
-- a point-in-time snapshot of the animal's age when the event was logged,
-- not a live-updating figure.

ALTER TABLE g2p_register_health_events
    ADD COLUMN IF NOT EXISTS age VARCHAR;
ALTER TABLE g2p_register_history_health_events
    ADD COLUMN IF NOT EXISTS age VARCHAR;
ALTER TABLE g2p_intake_form_health_events
    ADD COLUMN IF NOT EXISTS age VARCHAR;

ALTER TABLE g2p_register_vaccinations
    ADD COLUMN IF NOT EXISTS age VARCHAR;
ALTER TABLE g2p_register_history_vaccinations
    ADD COLUMN IF NOT EXISTS age VARCHAR;
ALTER TABLE g2p_intake_form_vaccinations
    ADD COLUMN IF NOT EXISTS age VARCHAR;

ALTER TABLE g2p_register_vital_events
    ADD COLUMN IF NOT EXISTS age VARCHAR;
ALTER TABLE g2p_register_history_vital_events
    ADD COLUMN IF NOT EXISTS age VARCHAR;
ALTER TABLE g2p_intake_form_vital_events
    ADD COLUMN IF NOT EXISTS age VARCHAR;

ALTER TABLE g2p_register_breedings
    ADD COLUMN IF NOT EXISTS age VARCHAR;
ALTER TABLE g2p_register_history_breedings
    ADD COLUMN IF NOT EXISTS age VARCHAR;
ALTER TABLE g2p_intake_form_breedings
    ADD COLUMN IF NOT EXISTS age VARCHAR;
