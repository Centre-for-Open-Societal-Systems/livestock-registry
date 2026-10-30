-- Holdings approved on registry-platform 1.2 before the Livestock service set
-- their state on ingest (mark_verified in g2p_register_domain_service_livestock.py)
-- were stored with a blank state. Every register Livestock row is an approved
-- intake, so a blank state there means VERIFIED, dated the day it was approved.
-- Rows with a state, ARCHIVED included, are left alone, so a second run
-- changes nothing.
UPDATE g2p_register_livestocks
SET state = 'VERIFIED',
    state_date = COALESCE(state_date, last_approved_at::date, created_at::date)
WHERE NULLIF(TRIM(state), '') IS NULL;
