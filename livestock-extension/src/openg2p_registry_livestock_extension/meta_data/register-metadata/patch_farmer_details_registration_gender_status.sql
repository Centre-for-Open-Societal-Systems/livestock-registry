-- Patch for already-seeded environments only (fresh databases get this from
-- g2p_register_sections.sql directly; the seed never updates existing rows).
--
-- Farmer section of the Livestock intake form (livestock_farmer_identity_section_01):
--   1. Registration Date defaults to today (widget-data-default "today"; the
--      server resolves the token on save, see
--      G2PRegisterDomainServiceFarmer.validate_record).
--   2. The Status dropdown is removed from the form.
--   3. Gender also offers OTHER (MALE / FEMALE / OTHER).
-- The seed runs every patch file on every deploy in name order, so each
-- substitution is a no-op once its change is in place. The Status widget is
-- matched by regexp, not literally: jsonb stores object keys in its own order
-- (e.g. "params" comes back as {"page_size": .., "attribute_id": ..}).
UPDATE "public"."g2p_register_sections"
SET section_ui_schema = replace(
    replace(
        regexp_replace(
            section_ui_schema::text,
            ', \{"widget": "select", "widget-id": "status", .*?"valueKey": "value_id"\}\}',
            ''
        ),
        '{"label": "FEMALE", "value": "FEMALE"}]}}',
        '{"label": "FEMALE", "value": "FEMALE"}, {"label": "OTHER", "value": "OTHER"}]}}'
    ),
    '"widget-data-path": "f9c6a359-9563-5a43-b0fe-6c7e452037a3.registration_date", "widget-data-format"',
    '"widget-data-path": "f9c6a359-9563-5a43-b0fe-6c7e452037a3.registration_date", "widget-data-default": "today", "widget-data-format"'
)::jsonb
WHERE section_id = 'livestock_farmer_identity_section_01';
