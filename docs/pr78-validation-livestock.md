# Livestock Registry – refactor PR #78 validation

Yash Sontakke · 26–28 October 2026 · tested @ 5db011b of `deploy/develop-refactor` (registry-platform 1.2.2-rc.557)

> **Status 28 Oct:** PR #78 was merged into `develop` on 27 Oct (330b9dd), followed by #81–#86 (develop @ 74f881a). The local run below is on the 5db011b snapshot and has not been repeated on develop head yet. Changes since the snapshot that affect this report, checked in the develop tree:
> - Approval routing: geographic routing deferred; all three livestock policies (`*.default`) use two fixed reviewers `alex.carter` then `nina.patel`, `on_empty=block` (`docs/refactor/DEFAULT_APPROVALS.md`).
> - Seed image (#81): the exit-1 guard is gone, `/seed/entrypoint.sh` runs again and `40_callback_secret.sql.tpl` is back, so B6 is partly fixed. Code lists and geo seed are still absent; B1 (Farmer `functional_id_generation_required=TRUE`) and B5 (no vaccine schedules) are unchanged.
> - #81 also wires the Farmer reference on "New Dev" to the real Farmer partner API (record contract + its response-signing key in Helm, EdDSA lookup key in Partner Management), which is where the real-registry end-to-end test can run.

The PR was run unchanged on a laptop with docker compose: develop's compose for Keycloak / IAM / Master Data / AWE / ID generator, the five registry images built from the PR on the public rc.557 base images, a mock Farmer Registry for the signed lookup, and a small Master Data shim because the local MDM image is older than the one the PR expects. No PR code was modified. Test assets: API chain scripts, a 54-case validation matrix, Playwright browser runs with screenshots, the sanity DCI test. This file is the "what we had / what is missing / what comes next" list asked for on 27 October and will be updated as items are fixed.

## Run 2 – develop head on Asmit's oan-developer stack (29 Oct)

Stack: `openg2p-developer` (`oan-developer` branch), livestock built from COSS `develop` @ 3f2deb6 (#88), commons from the pinned charts, Master Data develop.118 with the ETH-OAN pack, mock Farmer Registry for the signed lookup (Asmit: "mock is fine for now"), default reviewers alex.carter → nina.patel. No code modified; local-only compose overrides for the mock and the beat DB settings.

Verified: seeds (11 registers, 15 sections, 3 AWE policies + callback secret), Keycloak users, Master Data geography (21 037 units, P-codes) and the livestock lists in the pack, login, identity/survey/location sections in the browser, Livestock Details dialog with species/breed from Master Data, and the API chain end to end: finalize → signed lookup → Farmer ADD change request → AWE tasks → both stages approved by alex.carter and nina.patel → farmer FR-310000000002 in the register → ingest worker adds livestock LS-283958219081 linked to the farmer, with `woreda_id`/`geo_lowest_level_value_id` set.

Changes versus the 5db011b run: B6 entrypoint and callback secret fixed (#81); B8 not reproduced; **B10 fixed by #88** (one native geo widget with map). B1 reproduced exactly (webhook 500 until the Farmer flag is set to FALSE by hand; AWE's retry then completes the chain).

New findings on develop head (added to the table as B11–B14): the species/breed deadlock between core Master Data validation and the extension's own code lists (no animal can be saved at all), empty Vaccine dropdown, geo values landing only in the native columns, and the livestock beat producers missing from beat's schedule.

## 1. What we had before the refactor (develop, deployed on dev)

- Web intake form with 8 sections: Farmer (ID, FAN, name, contact), Survey Personnel, Location, Livestock Details, Health Events, Vaccinations, Vital Events, Breeding; 11 registers (Farmer, Livestock, Animal, HealthEvent, Vaccination, VitalEvent, Breeding, Retagging, VaccineSchedule, ImportBatch, AuditLog).
- Farmer enrichment by Farmer ID from the Farmer Registry on submit (name/contact replaced by the source).
- Single-stage Woreda approval through AWE with a custom approver resolver (Keycloak role + location attribute, fallbacks); change requests on approved records with version history.
- ODK: Collect form → ODK Central → connector → partner API → intake submission → approval. File import (Excel template, group by farmer). DCI search by Farmer ID / ear tag.
- Dialog behaviour: breed filtered by species, vaccine filtered by species, ear-tag picker of the submission's animals, Species/Age auto-fill, live age, date defaults, client-side ear-tag check.
- Server rules: duplicate ear tag / event checks (register and other drafts), BIRTH reserves offspring ear tags and creates calves, next due date from the vaccine schedule, health/vaccination status auto-update, deceased handling, Region/Zone/Woreda/Kebele names on records.
- Background jobs: vaccination / calving / approval-pending reminders, outbreak alert, audit retention. Animals finder with bulk status update. Dashboard reporting views. Local docker-compose stack.
- Implemented through platform patches (core find/replace at build, runtime monkeypatches, compiled UI bundle edits), which is what the refactor removes.

## 2. New in the refactor (working, verified locally)

- No platform patches left: behaviour comes from registered service subclasses, `ui/staff-ui/overrides`, metadata seeds and `CELERY_IMPORTS`.
- Farmer linkage: intake carries only Farmer ID + Fayda FIN/FAN; on submit a signed DCI lookup verifies the farmer, a Farmer ADD change request is created when the farmer is new, approved farmers are reused ("Farmer reference linked"); Kafka UPDATE change requests are wired (not testable locally).
- Geo approval (as tested @ 5db011b): Woreda approver chosen from the Keycloak role "Woreda Approver" + registry data policy for the record's woreda; no fallbacks; clear refusal messages. Change requests route by the record's approved woreda. **Deferred in the PR head c0ac3bd**: the geo service is no longer registered, the seeds moved to `configuration/deferred-geographic/`, and all three livestock policies (`*.default`) use two fixed reviewers `alex.carter` / `nina.patel` with `on_empty=block`.
- Fayda eSignet verification popup with FIN read-only (needs a provider; manual FAN fallback works).
- Field format rules (names, Farmer ID `FR-` + 12 digits, FAN 16, FIN 12, dates), 25 extension unit tests.
- Verified end to end: web intake (API and browser) → lookup → Farmer ADD CR → AWE tasks → approval in either order → farmer and livestock in the register; approver task UI; admin edit → change request → approval with history; reject paths; dedup; validation matrix 51/54; DCI search by FID.

## 3. Broken (bugs)

| # | Finding | Where | Impact |
|---|---|---|---|
| B1 | Farmer register seeded with `functional_id_generation_required=TRUE`; `farmer_reference` requires FALSE → webhook 500 `FARMER_REFERENCE_EXTERNAL_IDENTIFIER_CONFIGURATION_REQUIRED` | `g2p_register_definitions.sql` | Farmer ADD CR can never be approved; livestock stays held |
| B2 | Hooks `post_intake_upsert`, `pre_finalize`, `post_approval_stage` were added to the platform by our core patch; rc.557 only calls `validate_domain_attributes` / `pre_approve` / `post_approve` / `post_ingest`. The PR removed the patch but kept the methods → dead code | all domain services | Lost: offspring ear tags and calves on BIRTH (verified), Region/Zone/Woreda/Kebele names (NULL everywhere), intake-side duplicate mortality/disease checks, ear-tag-belongs-to-submission check, section re-save duplicate fix, livestock state ladder |
| B3 | ODK: raw submission to `/partner/ingest_data?data_model=LIVESTOCK_ODK_MODEL` rejected (envelope sender_id/signature required); with an envelope, transformation fails `Template not found` (ls_odk_transform.j2 not registered in `incoming_templates`) | hooks removed, no seed | No ODK record reaches the registry |
| B4 | partner-api answers HTTP 500 `Object of type datetime is not JSON serializable` on every ingest | platform rc.557 (hidden on develop by the removed JSON patch) | Connector retries forever |
| B5 | Default vaccine schedules no longer seeded (`add_default_vaccine_schedules` dropped from `app.py`, sample data removed) | seed | `next_due_date` blank, reminders never fire (verified: works as soon as one schedule row exists) |
| B6 | db-seed image: `40_callback_secret.sql.tpl` dropped, `master_data/code_lists` not copied, geo seed removed, entrypoint replaced by an exit-1 guard. **Partly fixed by #81** (entrypoint and callback template restored); code lists and geo still missing | `docker/db-seed/Dockerfile` | AWE decision webhooks 401 (fixed); species/breed/vaccine lists and locations never seeded |
| B7 | Extension beat producers use `openg2p_registry_celery_worker.engine`; without the removed settings bridge the beat process connects to localhost:5432 | celery-beat config | Reminders/outbreak alert crash unless `REGISTRY_CELERY_WORKERS_DB_*` is also set on celery-beat |
| B8 | AWE seed runs before AWE has created its tables on a fresh stack (to re-check with the #81 entrypoint) | seed order | AWE policies missing on first install |
| B9 | staff-api and partner-api both run `migrate` at start → IntegrityError race on a fresh DB | platform CMD | Startup noise; app still starts |
| B10 | Location section renders two sets of Region/Zone/Woreda/Kebele selects (original selects + new native geo-hierarchy widget). **Fixed by #88** (verified 29 Oct) | `zzzz_location_widgets.sql` | Confusing UI |
| B11 | **Species / breed deadlock.** Core `validate_attribute_values` (Master Data) accepts only the pack codes (`CATTLE`, `GOATS`, …; breed `BREED_IMPROVED`, …) while the extension accepts only its own `LIVESTOCK_SPECIES_*` values and checks breed against `LIVESTOCK_BREED` names; the old code-list seed that provided those values is gone. Every combination is rejected | `g2p_register_domain_service_animal.py`, Master Data lists | **No animal can be saved on develop head**, UI or API; health/vaccination/vital/breeding sections unusable |
| B12 | The native geo widget writes `geo_lowest_level_value_id` + `geo_code_hierarchy_json`; the extension's `region_id`/`zone_id`/`woreda_id`/`kebele_id` stay NULL from the UI and the name columns stay NULL (B2) | location section, domain services | Woreda-based logic and reports have no data unless they read the native columns |
| B13 | Livestock beat producers (vaccination/calving/approval reminders, outbreak alert, audit retention) are imported via `CELERY_IMPORTS` but never enter beat's effective schedule (17 platform entries only) | `tasks/__init__.py` sets `current_app.conf.beat_schedule` too early | Reminders and outbreak alerts never run |
| B14 | Vaccine dropdown has no options (no vaccine list in Master Data); no disease list either; Age stays blank in the Livestock dialog; ear tag is a typed field in every event dialog | Master Data pack, UI | Vaccinations cannot be entered in the UI |

## 4. Missing (removed, needs re-implementation the supported way)

- Dialog behaviour from the retired overlay: breed by species, vaccine by species, ear-tag picker, Species/Age auto-fill, live age, date defaults, client-side ear-tag format check.
- File Import ("Import from file: No options available"): no import-file configuration/template.
- DCI search by `FARMER_ID` / `EAR_TAG` (only FID remains; UIN by FAN rejected). Farmer register has no DCI template (same as develop).
- Animals finder + bulk status update (header patch removed).
- Dashboard reporting views (`lr_rpt_*`), local docker-compose stack and `local/` folder, vendored ODK connector.

## 5. Dependencies / environment (not code bugs, but blockers)

- Master Data: core calls `/geo/get_all_geo_levels`, `/geo/get_geo_level_values`, `/attributes/get_attribute_values` (MDM develop.118). The current MDM has the old paths and no attributes API → location and species/breed dropdowns empty.
- Geo data: `parent_level_value_id` holds the parent's name in the Ethiopia seed; rc.557 cascading needs the parent id.
- Farmer lookup (`COSS_FARMER_*`, signing keys, record contract, AWE client) is mandatory for Submit; a lookup-skip for local testing does not exist.
- Approvers: at c0ac3bd the default reviewers `alex.carter` / `nina.patel` are upstream example users that do not exist in our Keycloak; with `on_empty=block` every intake and change request would stall until real reviewers are configured through AWE administration. The geographic variant (Keycloak admin settings, roles "Woreda Approver" / "Farmer Reference Approver", `DP_<mnemonic>` data policies per woreda) is deferred and not seeded anywhere.
- Fayda eSignet provider, Kafka/connector for farmer UPDATE CRs: not configured.

## 6. Not tested locally

Fayda eSignet popup, Kafka `FARMER_REFERENCE_CHANGED_V1`, dashboard, file import (removed), outbreak alert and reminder mails with real data, ODK Collect form against the new transform, roles other than Field Officer / Woreda Approver / admin.

## 7. Next (to agree with Asmit; order = priority)

1. Seed fixes: B1, B5, B6 (code lists), B8; and B11: move the extension to the pack codes for species/breed (species config keyed by pack code, breed names from `LIVESTOCK_BREED_NAME`), add vaccine/disease lists to openg2p-data.
2. B2: port the dead-hook logic into what the platform calls (registered intake-service subclass or `post_approve` / `post_ingest`), or request a native post-section-save hook from OpenG2P.
3. ODK: template seed + envelope path (connector configuration or partner-api ingest subclass); B4 and B9 reported to OpenG2P.
4. Dialog behaviour as registered widgets under `ui/staff-ui/overrides`; remove the duplicated location selects.
5. File import as native import configuration + template; group-by-farmer in `post_ingest`.
6. Seeds into the openg2p-data fork: code lists, geo with parent ids, users/roles/data policies, vaccine schedules; decide where species config lives.
7. Beat schedule registration (B13) and settings (B7), geo columns (B12), DCI id types, reporting views, compose stack back.
8. Approval routing: decide between the two-fixed-reviewer default (c0ac3bd) and the Woreda-based routing we had on dev; configure real reviewers in AWE before any deployment.
9. Re-run this validation on develop head (74f881a or later), then align dev Master Data version and geo data with rc.557, configure farmer lookup, reviewers, eSignet, and run the full regression on dev.
