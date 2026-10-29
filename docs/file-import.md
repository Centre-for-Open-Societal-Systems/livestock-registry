# Livestock bulk import from a file

The Livestock registry takes intakes from a CSV or Excel file through the staff portal menu **Import from file**. It has one intake form, so one entry. This page is the column specification. The blank header file is in `import-templates/`.

## How an upload is handled

1. Staff with the intake-submission edit permission upload a `.csv` or `.xlsx` file.
2. The platform import worker reads the first sheet and passes every row on as one flat record.
3. A Jinja incoming template (`templates/livestock_file_import_intake.j2`) maps the columns to the sections of the intake form. There is no Python mapping.
4. Every row becomes an intake submission. It waits for its Farmer to be approved in the Farmer registry, then goes through the two-stage approval (an officer, then a second officer; an admin can act at either stage). Nothing is written to the register directly.

## File rules

- The first row holds the column names exactly as below (letter case is ignored). Columns not listed are ignored; columns may be in any order.
- One row is one intake. Animal rows and the health, vaccination, vital and breeding events are **not** imported. Add them in the staff portal or by change request.
- A blank cell means "not given". Required columns are checked when the intake is saved and submitted.
- Numbers use a decimal point and no thousands separator.
- A row with a value the register cannot take (for example a letter in a number column) fails on its own, with the column named in the error; the other rows of the file continue. Check the row errors of the upload when the count of imported rows is lower than the count in the file.
- The farmer is named by the Farmer ID and one Fayda ID (FIN or FAN). Nothing else about the farmer is imported; the Farmer registry owns it.

## Known limit: the animal table is required at submit

The Livestock intake requires at least one animal row (`widget-required` on `ls_animal_details_table`, enforced for every channel by `required_intake.py`). A file row carries no animal, so the intake is saved from the row but is refused when it is finalized, with "Livestock Details: add at least one row". Until that rule or the file shape changes, an imported intake does not start approval. See the open question in the commit message.

## Livestock intake (`livestock_intake_import_template.csv`)

Import configuration: `file_import_to_livestock_intake`.

| Column | Maps to | Required | Format or allowed codes |
|---|---|---|---|
| `farmer_id` | Farmer lookup (`livestock_farmer_lookup`) | Yes | FR- followed by 12 digits, for example FR-000000000001 |
| `fayda_id` | Farmer lookup (`livestock_farmer_lookup`) | Yes | A 12-digit FIN or a 16-digit FAN, digits only (spaces are dropped) |
| `surveyor_name` | Survey personnel (`ls_survey_personnel`), shown as "DA name" | No | Text |
| `surveyor_mobile_number` | Survey personnel (`ls_survey_personnel`), shown as "DA mobile number" | No | Text |
| `supervisor_name` | Survey personnel (`ls_survey_personnel`) | No | Text |
| `supervisor_mobile_number` | Survey personnel (`ls_survey_personnel`) | No | Text |
| `region` | Location (`ls_livestock_location`) | No | Master Data geo unit id (P-code), for example ET04 |
| `zone` | Location (`ls_livestock_location`) | No | Master Data geo unit id (P-code), for example ET0404; needs the region |
| `woreda` | Location (`ls_livestock_location`) | No | Master Data geo unit id (P-code), for example ET040404; needs the zone |
| `kebele` | Location (`ls_livestock_location`) | No | Master Data geo unit id (P-code), for example ET040404888003; needs the woreda |
| `latitude` | Location (`ls_livestock_location`) | No | Decimal degrees, -90 to 90; needs the longitude too |
| `longitude` | Location (`ls_livestock_location`) | No | Decimal degrees, -180 to 180; needs the latitude too |

The place is written the way the staff portal's geo-hierarchy widget writes it: the deepest level given is the holding's place, the chain is kept in `geo_code_hierarchy_json`, and the registry fills the place names from Master Data on save.

## Code lists

The flat columns of this form have no dropdown other than the geography, which takes Master Data geo unit ids. No other code list is read by the template.

For the child lists that are left out, check the codes against the validators before they are added to a later file shape:

- Species (`LIVESTOCK_SPECIES`): the validator (`validate_species_known`) accepts the Master Data codes of the country pack (`CATTLE`, `GOATS`, `SHEEP`, `CAMELS`, `EQUINES`, `POULTRY`, `OTHER`) and refuses the retired `LIVESTOCK_SPECIES_<NAME>` codes (`tests/test_species_from_master_data.py`). The ODK template still reads `LIVESTOCK_SPECIES_<NAME>` values by their name and turns them into the pack codes. Which spelling a future species column takes is waiting on a decision; this file shape has no such column.
- Gender (`MALE`, `FEMALE`, `MIXED`), health status (`HEALTHY`, `SICK`, `QUARANTINED`, `DECEASED`) and vaccination status (`UP_TO_DATE`, `OVERDUE`, `NONE`) are static options of the animal table, not Master Data lists.

## Where the pieces live

| Piece | Where |
|---|---|
| Import configuration | `meta_data/registry-configurations/g2p_registry_import_file_configurations.sql` |
| Data model `file_import_to_livestock_intake`, key paths (`$.headers.*`, payload `$.body`), pattern with the pass-through enricher, template and document rows | `meta_data/zz-oan/50_file_import_to_livestock_intake.sql` |
| Pass-through enricher | `ingestion_pipeline/enricher_services/g2p_livestock_enricher_services.py` (`G2PPassThroughEnricherService`) |
| Jinja template | `templates/livestock_file_import_intake.j2` |
| Tests | `livestock-extension/tests/test_file_import.py` |

The ODK connector keeps its own data model `odk_to_livestock_intake`; file import does not touch it.

## Operating notes

- The import worker sends rows as the sender `Staff Portal`. That sender must exist as an active partner in Partner Management, or the first row aborts the whole file.
- The worker supplies the service token for the approval workflow itself: when a worker finalizes an intake without a user token, the Livestock intake service requests one from the approval engine (`farmer_reference/workflow.py`, `service_bearer`), so the worker needs the `COSS_FARMER_AWE_TOKEN_URL`, `COSS_FARMER_AWE_CLIENT_ID` and `COSS_FARMER_AWE_CLIENT_SECRET_FILE` settings. This repository does not set them; the chart that deploys the worker does.
- Sample rows are not kept here. Sample import files belong in the openg2p-data repository.
- The retired custom `ImportBatch` register is gone; the platform's own import queue and log (`import_file_process_queue`, `import_file_process_log`) hold the state of an upload. Its three data tables are kept, unused, until they are shown to be empty everywhere.
