# Livestock bulk import from a file

The Livestock registry takes intakes from a CSV or Excel file through the staff portal menu **Import from file**. It has one intake form, so one entry. This page is the column specification. The blank header file is in `import-templates/`.

## How an upload is handled

1. Staff with the intake-submission edit permission upload a `.csv` or `.xlsx` file.
2. The platform import worker reads the first sheet and passes every row on as one flat record.
3. A Jinja incoming template (`templates/livestock_file_import_intake.j2`) maps the columns to the sections of the intake form. There is no Python mapping.
4. Every row becomes an intake submission. It waits for its Farmer to be approved in the Farmer registry, then goes through the two-stage approval (an officer, then a second officer; an admin can act at either stage). Nothing is written to the register directly.

## File rules

- The first row holds the column names exactly as below (letter case is ignored). Columns not listed are ignored; columns may be in any order.
- One row is one intake with exactly one animal, because the livestock details table needs at least one row. More animals and the health, vaccination, vital and breeding events are **not** imported. Add them in the staff portal or by change request.
- Dropdown columns take the Master Data **code**, never the label.
- A blank cell means "not given". Required columns are checked when the intake is saved and submitted.
- Numbers use a decimal point and no thousands separator. Dates are `YYYY-MM-DD` (a time after the date is dropped, as Excel writes it).
- A row with a value the register cannot take (for example a letter in a number column) fails on its own, with the column named in the error; the other rows of the file continue. Check the row errors of the upload when the count of imported rows is lower than the count in the file.
- The farmer is named by the Farmer ID and one Fayda ID (FIN or FAN). Nothing else about the farmer is imported; the Farmer registry owns it.

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
| `ear_tag_id` | Livestock details (`ls_animal_details`) | Conditional | ET followed by exactly 10 digits, for example ET0000000013. Required when the species needs an ear tag |
| `secondary_identifier` | Livestock details (`ls_animal_details`) | Conditional | Text (leg band, wing tag, hive number). Required instead of the ear tag for a species without an ear tag |
| `species` | Livestock details (`ls_animal_details`) | Yes | Code from the LIVESTOCK_SPECIES list below |
| `breed` | Livestock details (`ls_animal_details`) | Yes | Code from the LIVESTOCK_BREED list below; it must belong to the species |
| `quantity` | Livestock details (`ls_animal_details`) | Conditional | Whole number above zero. Required for a flock species (head count) |
| `weight` | Livestock details (`ls_animal_details`) | No | Number, digits and an optional decimal point |
| `date_of_birth` | Livestock details (`ls_animal_details`) | Conditional | YYYY-MM-DD, not in the future. Required except for a flock species |
| `age` | Livestock details (`ls_animal_details`) | No | Text; the registry works it out from the date of birth |
| `gender` | Livestock details (`ls_animal_details`) | Yes | `MALE`, `FEMALE`, `MIXED` (`MIXED` only for a species without an ear tag) |
| `health_status` | Livestock details (`ls_animal_details`) | Yes | `HEALTHY`, `SICK`, `QUARANTINED`, `DECEASED` |
| `vaccination_status` | Livestock details (`ls_animal_details`) | Yes | `UP_TO_DATE`, `OVERDUE`, `NONE` |
| `registration_date` | Livestock details (`ls_animal_details`) | Yes | YYYY-MM-DD, not in the future |

The place is written the way the staff portal's geo-hierarchy widget writes it: the deepest level given is the holding's place, the chain is kept in `geo_code_hierarchy_json`, and the registry fills the place names from Master Data on save.

## Code lists

`region` to `kebele` take Master Data geo unit ids. The animal columns take these:

### LIVESTOCK_SPECIES

Master Data list `LIVESTOCK_SPECIES` of the country pack. The validator (`validate_species_known`) accepts these codes and refuses the retired `LIVESTOCK_SPECIES_<NAME>` codes (`tests/test_species_from_master_data.py`). Whether a species needs an ear tag or is a flock is an attribute of the value in Master Data.

`CATTLE`, `GOATS`, `SHEEP`, `CAMELS`, `EQUINES`, `POULTRY`, `OTHER`

### LIVESTOCK_BREED

Master Data list `LIVESTOCK_BREED`, the breed type; the registry refuses a breed that does not belong to the row's species.

`BREED_IMPROVED`, `BREED_LOCAL`, `BREED_HYBRID`

### Fixed codes

Gender, health status and vaccination status are static options of the table, listed in the column table above.

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
