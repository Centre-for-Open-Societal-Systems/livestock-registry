-- "Import from file" entry for the Livestock intake form (the only intake form).
-- Its file-import data model (file_import_to_livestock_intake, seeded in
-- zz-oan/60_file_import_to_livestock_intake.sql) has key paths, a pass-through
-- pattern and a Jinja template that take one flat CSV/Excel row per intake. The
-- ODK data model (odk_to_livestock_intake) belongs to the ODK connector and is
-- not used here. The configuration id is fixed and the row is upserted, so an
-- upgrade updates it in place and the seed can run again.
-- Columns: docs/file-import.md.

INSERT INTO g2p_registry_import_file_configurations (
    import_file_configuration_id,
    register_id,
    form_id,
    data_model_id,
    import_file_template_mnemonic,
    import_file_template_description
) VALUES
(
    '5353b3ca-1ee0-550c-a672-978cd478aead',
    '997676d3-7008-59f9-b23e-613ad79bbb08',
    'e92e8be1-207f-518e-99c2-8bc21cc1f112',
    'file_import_to_livestock_intake',
    'file_import_to_livestock_intake',
    'Import livestock intakes from a CSV or Excel file, one row per intake'
)
ON CONFLICT (import_file_configuration_id) DO UPDATE SET
    register_id = EXCLUDED.register_id,
    form_id = EXCLUDED.form_id,
    data_model_id = EXCLUDED.data_model_id,
    import_file_template_mnemonic = EXCLUDED.import_file_template_mnemonic,
    import_file_template_description = EXCLUDED.import_file_template_description;
