-- Date fields: no "past-only" constraint in the section metadata.
--
-- On registry-platform 1.2 a date widget whose value breaks its
-- dateConstraint sets the field error from an effect that re-runs on every
-- render, so typing a future date into any past-only field (Date of Birth,
-- Registration Date, Date of Onset, Vaccination Date, Event Date, Breeding
-- Date, Date of Retagging) crashed the whole page with React error #185.
-- The date picker blocks future days, typing does not.
--
-- The server refuses a future date on every one of these fields (the domain
-- services' not-in-future checks), with a message naming the field, so the
-- widget constraint is dropped. The section files no longer carry it; this
-- updates sections stored before (Farmer identity has no sync patch of its
-- own). Runs last in this folder, after the sync patches; safe to re-run.
UPDATE g2p_register_sections
SET section_ui_schema = replace(section_ui_schema::text, '"dateConstraint": "past-only"', '"dateConstraint": "any"')::jsonb
WHERE section_ui_schema::text LIKE '%"dateConstraint": "past-only"%';
