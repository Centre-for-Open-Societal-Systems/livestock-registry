# Livestock File Import

Bulk entry of Livestock records from an Excel or CSV file, through the
portal's own File Import. Each record goes through the same checks,
deduplication and Woreda approval as a record entered on screen.

## For the person importing

1. Download the template: `livestock_import_template.xlsx` in this folder,
   or from the portal at `/livestock-import-template.xlsx`
   (for dev: `https://livestock-registry-development.oanstaging.com/livestock-import-template.xlsx`).
   A CSV with the same columns is `livestock_import_template.csv`.
2. Fill the sheet **Livestock**, one row per animal (or per flock / hive).
   Species, breed, sex, health status and vaccination status are dropdowns;
   the sheet **Allowed values** lists every code with its name and, for a
   breed, its species. The sheet **Instructions** explains every column, and
   **Example** shows three filled rows.
3. Save with the **Livestock** sheet selected (the import reads the sheet that
   is open when the file is saved).
4. In the portal: Form Submissions > Create New Submission > Import from
   file > **LIVESTOCK_IMPORT_V1**, choose the file, Import.

What happens:

- Rows with the same Farmer ID (or, without one, the same Fayda FAN ID)
  become **one** Livestock record holding all of that farmer's animals.
- An empty Registration Date on an animal becomes today, as on screen.
- Each record is validated like a web entry. A record that fails (for
  example an ear tag that is not ET + 10 digits) is not created; the rest of
  the file still is. Fix the row and import a file with just those rows.
- Each created record waits for the Woreda approver of its woreda, then
  reaches the register.
- Created By on each record shows the person who uploaded the file,
  as `<name> (Import)`.

Known limits:

- The reason a row was refused is recorded on the ingestion
  (Incoming Messages), not shown to the uploader on the import screen.
- Health, vaccination, vital and breeding events are not in the template;
  add them on the record afterwards.

## For developers

- Configuration: `meta_data/registry-inbound-message-rules/import_file_configurations.sql`
  (seeded by db-seed; one configuration, `LIVESTOCK_IMPORT_V1`, on the DCI
  data model).
- Grouping rows by farmer: build-time patch of the celery worker's
  `import_file_process_worker.py` in `docker/celery/core-patches/apply_patches.py`
  (`_group_livestock_rows`), which also cuts Excel dates back to `YYYY-MM-DD`.
- Row to record: `_patch_ingest_service` in `odk_ingest_hooks.py` wraps the
  record and defaults an empty animal Registration Date;
  `templates/ls_odk_transform.j2` renders it into the intake sections.
- Rebuild the template after a code-list change, and commit all three copies:

  ```
  # in any container with openpyxl (the celery image has it)
  python3 docs/import/make_livestock_import_template.py \
      livestock-extension/src/openg2p_registry_livestock_extension/master_data/code_lists/20_g2p_attribute_values.sql \
      docs/import
  cp docs/import/livestock_import_template.xlsx docker/staff-ui/assets/
  ```
