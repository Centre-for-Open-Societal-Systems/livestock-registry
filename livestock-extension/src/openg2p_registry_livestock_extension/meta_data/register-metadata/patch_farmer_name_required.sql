-- Patch for already-seeded environments only (fresh databases get this from
-- g2p_register_sections.sql directly; the seed never updates existing rows).
--
-- Makes First Name and Last Name mandatory on the Farmer section of the
-- Livestock intake form (livestock_farmer_identity_section_01). The single
-- "Farmer Name" input was removed from this section on 2026-09-14 (05531f1)
-- in favour of First/Middle/Last Name, so "farmer name is compulsory" means
-- these two widgets. widget-required only drives the asterisk and the
-- client-side check; the server-side guard lives in
-- register_domain/services/g2p_register_domain_service_farmer.py
-- (require_field on first_name / last_name).
UPDATE g2p_register_sections
SET section_ui_schema = replace(
    replace(
        section_ui_schema::text,
        '"widget-id": "first_name", "widget-type": "input", "widget-label": "First Name", "widget-readonly": false, "widget-required": false',
        '"widget-id": "first_name", "widget-type": "input", "widget-label": "First Name", "widget-readonly": false, "widget-required": true'
    ),
    '"widget-id": "last_name", "widget-type": "input", "widget-label": "Last Name", "widget-readonly": false, "widget-required": false',
    '"widget-id": "last_name", "widget-type": "input", "widget-label": "Last Name", "widget-readonly": false, "widget-required": true'
)::jsonb
WHERE section_id = 'livestock_farmer_identity_section_01';
