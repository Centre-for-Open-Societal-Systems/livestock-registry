-- New Intake -> File Import for the Livestock intake form.
-- One configuration: a CSV / Excel file in the livestock import template
-- (docs/import/livestock_import_template.xlsx, also served by the portal at
-- /livestock-import-template.xlsx). Rows go through the DCI data model; the
-- ingest hooks turn each farmer's rows into one Livestock record with its
-- animals and render it with ls_odk_transform.j2, and the record then goes
-- through the same validation, deduplication and Woreda approval as a web
-- entry. Re-running the seed keeps the row and refreshes its texts.
INSERT INTO "public"."g2p_registry_import_file_configurations"
  ("import_file_configuration_id","register_id","form_id","data_model_id","import_file_template_mnemonic","import_file_template_description")
VALUES
  ('5f3c9a1e-7b2d-4e8a-9c41-3d6f0a7b1e21','997676d3-7008-59f9-b23e-613ad79bbb08','e92e8be1-207f-518e-99c2-8bc21cc1f112','c331ba96-ac35-4014-9d13-4ef327f6b79b',
   'LIVESTOCK_IMPORT_V1',
   'Livestock records from the livestock import template (Excel or CSV): one row per animal; rows with the same Farmer ID become one record with all its animals.')
ON CONFLICT ("import_file_configuration_id") DO UPDATE SET
  "import_file_template_mnemonic" = EXCLUDED."import_file_template_mnemonic",
  "import_file_template_description" = EXCLUDED."import_file_template_description";
