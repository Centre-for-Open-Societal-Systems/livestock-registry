-- Patch for already-seeded environments only (fresh databases get this from
-- g2p_register_sections.sql directly; the seed never updates existing rows).
--
-- Reverts patch_farmer_name_required.sql (PR #26, 2026-09-17): First Name and
-- Last Name on the Farmer section of the Livestock intake form
-- (livestock_farmer_identity_section_01) are optional again. The matching
-- server-side require_field() calls were removed from
-- register_domain/services/g2p_register_domain_service_farmer.py in the same
-- change. That earlier patch file is deleted rather than kept alongside: the
-- seed runs every patch file on every deploy in name order, and a surviving
-- "required" patch would re-apply itself after this one.
UPDATE "public"."g2p_register_sections"
SET section_ui_schema = replace(
    replace(
        section_ui_schema::text,
        '"widget-id": "first_name", "widget-type": "input", "widget-label": "First Name", "widget-readonly": false, "widget-required": true',
        '"widget-id": "first_name", "widget-type": "input", "widget-label": "First Name", "widget-readonly": false, "widget-required": false'
    ),
    '"widget-id": "last_name", "widget-type": "input", "widget-label": "Last Name", "widget-readonly": false, "widget-required": true',
    '"widget-id": "last_name", "widget-type": "input", "widget-label": "Last Name", "widget-readonly": false, "widget-required": false'
)::jsonb
WHERE section_id = 'livestock_farmer_identity_section_01';
