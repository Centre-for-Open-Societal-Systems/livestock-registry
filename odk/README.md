# Livestock ODK form and ingestion

Current new dev configuration and validation:
[Livestock ODK on new dev](../docs/odk-new-dev.md) (`livestock` namespace, project
6, `LIVESTOCK_ODK_MODEL`, active PM partner `PARTNER_LIVESTOCK`). The environment
table below describes the earlier project 14 deployment.

Field officers collect a livestock holding (farmer, location, animals and the
animals' health, vaccination, vital and breeding events) with ODK Collect or
Central's web form. The path to the registry is the same as the farmer
registry's: ODK Central → connector service (polls Central's OData API) →
`POST /partner/ingest_data` → the registry's ingestion workers (classify,
transform with `ls_odk_transform.j2`, save as an intake submission) → AWE
approval → register.

## Files

| File | What |
|---|---|
| `livestock_registry.xlsx` | The XLSForm (form id `livestock_registry`), published on the dev Central. v3 removed the animal Sex choice `other` (copied from the farmer gender list; the registry has MALE, FEMALE and MIXED only, as Gen1 had male/female). v4 adds "not in the future" to both resolution dates. |
| `media/region_odk.csv`, `zone_odk.csv`, `woreda_odk.csv`, `kebele_odk.csv` | Location choice lists the form loads (`select_one_from_file`), attached to the form in Central. Codes are the Master Data ids without the level prefix (zone `ET0101` = `zone-ET0101`; kebele `10101101001` = `kebele-ET010101101001`). |
| `sample_submissions.json` | Five real-shaped submissions as Central's OData API returns them (repeat groups inlined), for `test_transform.py`. |
| `breed_choices.csv` | The form's breed choices (species, name), a copy of the `breed` list on the choices sheet. Update it with the form. |
| `test_transform.py` | Renders the transform template against the samples and targeted cases, and checks that every breed choice in `breed_choices.csv` maps to a breed of its own species; run with `python odk/test_transform.py` (needs `jinja2`). |

## Where it runs

| Piece | Dev | Local |
|---|---|---|
| ODK Central | `https://odk-central-development.oanstaging.com`, project 14 "Gen2 Livestock Registry", form `livestock_registry` | same (the connector polls the dev Central) |
| Connector (api, worker, beat, ui) | namespace `common` | `connector-api` (8051), `connector-worker`, `connector-ui` (5174) from `docker-compose.yml` |
| Pipeline definition | connector DB `connector_definitions` | `local/postgres/seed_connector_pipelines.sql`, run by hand with the Central login from `local/.env` (`ODK_USER`, `ODK_PW`); see the file header |
| Partner | `livestock-partner` in Master Data `g2p_partners` | same |

The earlier sandbox `odk.13.207.43.8.nip.io` (project 14) was retired on 2026-10-07.

## Publishing a form change

1. Edit `livestock_registry.xlsx` and bump `version` on the `settings` sheet.
2. Central → project → form → Edit Form → Upload new Form Definition; keep the four
   media files attached.
3. Test the draft (Test in browser), then Publish Draft.
4. Keep this folder's copy identical to what Central serves.

## Form → registry mapping

| Form (survey sheet) | Intake section | Notes |
|---|---|---|
| `farmer/*` | `ls_farmer_identity`, `ls_livestock_record` | `fayda_fan_id` 16 digits, `farmer_id` `FR-` + 10 digits; `gender` upper-cased |
| `survey_personnel/*` | `ls_survey_personnel` | |
| `location/region_id … kebele_id` | `ls_farmer_location`, `ls_livestock_location` | region slug → name in the template; zone/woreda/kebele codes → names by `odk_ingest_hooks.resolve_geo_label` against Master Data (exact id first, suffix match last) |
| `livestock` (repeat) | `ls_animal_details` | species → `LIVESTOCK_SPECIES_*`; breed → `LIVESTOCK_BREED_*` through the exact map `_ODK_BREED_CHOICES` in `odk_ingest_hooks.py` (a breed that is not a choice of that species passes through and is rejected); poultry/beehive use `secondary_identifier` + `quantity` and Sex `mixed` |
| `livestock/health_events` | `ls_health_event_details` | `disease_type` → `LIVESTOCK_DISEASE_*` (DISEASE events only); `health_event_notes` → notes |
| `livestock/vaccinations` | `ls_vaccination_details` | `vaccine` → `VACCINE_TYPE_*` by species |
| `livestock/vital_events` | `ls_vital_event_details` | `birth_details/sex_of_offspring` → `offspring_gender`; `disease_details/*` → disease fields; `vital_event_details` → notes |
| `livestock/breeding_events` | `ls_breeding_details` | `natural_breeding` / `artificial_insemination` → NATURAL / AI; `artificial_insemination_tab/*` → AI fields |

Values the template and hooks do not recognise (a disease, vaccine or breed
that is neither a form choice nor an existing code) are passed through unchanged, so the same
domain validation that guards staff entry rejects the submission with its own
message; the ingest then stops as FAILED with that message in
`incoming_classified_data.ingestion_latest_error_code`. Nothing is relabelled
silently.

## Approval

An ODK submission is saved as a normal intake submission (livestock record
state DRAFT) and finalized by the ingest worker, which starts the AWE
approval with a service-account token
(`REGISTRY_CELERY_WORKERS_AWE_TOKEN_URL` / `_CLIENT_ID` / `_CLIENT_SECRET` on
the celery worker; the Keycloak client needs Service accounts enabled) and
its own AWE client settings (`REGISTRY_CELERY_WORKERS_AWE_ENABLED` /
`_BASE_URL` / `_DEFAULT_CALLBACK_URL` / `_CALLBACK_SECRET_ID`; the platform
chart gives those to staff-api only, so the livestock values add them for the
worker). From there it follows the same approval stages as a submission typed
in the staff portal. Without those settings the submission is finalized but no
approval request exists, and it sits PENDING with no task for any approver.
