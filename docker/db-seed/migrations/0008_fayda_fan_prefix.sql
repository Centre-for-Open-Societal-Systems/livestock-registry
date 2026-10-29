-- Fayda FAN ID is stored as 16 bare digits (the server checks
-- ^\d{16}$). Records saved before that format carry a "FAN-" prefix
-- (FAN-7777777777666666); on such a record every change request was
-- refused ("fayda_fan_id must be exactly 16 digits"), whatever field was
-- edited, because the whole section is validated again. The prefix is
-- dropped on the register and intake rows. History rows keep what was
-- recorded at the time. Re-runs change nothing.
UPDATE g2p_register_livestocks
SET fayda_fan_id = regexp_replace(fayda_fan_id, '^\s*FAN-\s*', '', 'i')
WHERE fayda_fan_id ~* '^\s*FAN-';

UPDATE g2p_register_farmers
SET fayda_fan_id = regexp_replace(fayda_fan_id, '^\s*FAN-\s*', '', 'i')
WHERE fayda_fan_id ~* '^\s*FAN-';

UPDATE g2p_intake_form_livestocks
SET fayda_fan_id = regexp_replace(fayda_fan_id, '^\s*FAN-\s*', '', 'i')
WHERE fayda_fan_id ~* '^\s*FAN-';

UPDATE g2p_intake_form_farmers
SET fayda_fan_id = regexp_replace(fayda_fan_id, '^\s*FAN-\s*', '', 'i')
WHERE fayda_fan_id ~* '^\s*FAN-';
