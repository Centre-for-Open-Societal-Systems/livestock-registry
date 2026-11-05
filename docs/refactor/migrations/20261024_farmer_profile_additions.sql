-- Review artifact only: NOT executed, and not an installation bypass.
-- Rehearse against a restored existing database before wiring into native
-- extension migrations. Preserve records, histories, pending approvals and geo
-- assignments. No column is renamed/dropped and no data is rewritten.
BEGIN;
ALTER TABLE g2p_register_farmers ADD COLUMN IF NOT EXISTS first_name_amh varchar;
ALTER TABLE g2p_register_farmers ADD COLUMN IF NOT EXISTS middle_name_amh varchar;
ALTER TABLE g2p_register_farmers ADD COLUMN IF NOT EXISTS last_name_amh varchar;
ALTER TABLE g2p_register_farmers ADD COLUMN IF NOT EXISTS first_name_other varchar;
ALTER TABLE g2p_register_farmers ADD COLUMN IF NOT EXISTS middle_name_other varchar;
ALTER TABLE g2p_register_farmers ADD COLUMN IF NOT EXISTS last_name_other varchar;
ALTER TABLE g2p_register_farmers ADD COLUMN IF NOT EXISTS email varchar;
ALTER TABLE g2p_register_farmers ADD COLUMN IF NOT EXISTS region_name varchar;
ALTER TABLE g2p_register_farmers ADD COLUMN IF NOT EXISTS zone_name varchar;
ALTER TABLE g2p_register_farmers ADD COLUMN IF NOT EXISTS woreda_name varchar;
ALTER TABLE g2p_register_farmers ADD COLUMN IF NOT EXISTS kebele_name varchar;
ALTER TABLE g2p_register_history_farmers ADD COLUMN IF NOT EXISTS first_name_amh varchar;
ALTER TABLE g2p_register_history_farmers ADD COLUMN IF NOT EXISTS middle_name_amh varchar;
ALTER TABLE g2p_register_history_farmers ADD COLUMN IF NOT EXISTS last_name_amh varchar;
ALTER TABLE g2p_register_history_farmers ADD COLUMN IF NOT EXISTS first_name_other varchar;
ALTER TABLE g2p_register_history_farmers ADD COLUMN IF NOT EXISTS middle_name_other varchar;
ALTER TABLE g2p_register_history_farmers ADD COLUMN IF NOT EXISTS last_name_other varchar;
ALTER TABLE g2p_register_history_farmers ADD COLUMN IF NOT EXISTS email varchar;
ALTER TABLE g2p_register_history_farmers ADD COLUMN IF NOT EXISTS region_name varchar;
ALTER TABLE g2p_register_history_farmers ADD COLUMN IF NOT EXISTS zone_name varchar;
ALTER TABLE g2p_register_history_farmers ADD COLUMN IF NOT EXISTS woreda_name varchar;
ALTER TABLE g2p_register_history_farmers ADD COLUMN IF NOT EXISTS kebele_name varchar;
ALTER TABLE g2p_intake_form_farmers ADD COLUMN IF NOT EXISTS first_name_amh varchar;
ALTER TABLE g2p_intake_form_farmers ADD COLUMN IF NOT EXISTS middle_name_amh varchar;
ALTER TABLE g2p_intake_form_farmers ADD COLUMN IF NOT EXISTS last_name_amh varchar;
ALTER TABLE g2p_intake_form_farmers ADD COLUMN IF NOT EXISTS first_name_other varchar;
ALTER TABLE g2p_intake_form_farmers ADD COLUMN IF NOT EXISTS middle_name_other varchar;
ALTER TABLE g2p_intake_form_farmers ADD COLUMN IF NOT EXISTS last_name_other varchar;
ALTER TABLE g2p_intake_form_farmers ADD COLUMN IF NOT EXISTS email varchar;
ALTER TABLE g2p_intake_form_farmers ADD COLUMN IF NOT EXISTS region_name varchar;
ALTER TABLE g2p_intake_form_farmers ADD COLUMN IF NOT EXISTS zone_name varchar;
ALTER TABLE g2p_intake_form_farmers ADD COLUMN IF NOT EXISTS woreda_name varchar;
ALTER TABLE g2p_intake_form_farmers ADD COLUMN IF NOT EXISTS kebele_name varchar;
COMMIT;
