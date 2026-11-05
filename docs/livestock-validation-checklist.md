# Livestock Registry – validation of the native refactor

Yash Sontakke · 26–30 October 2026 · findings checked against OAN `develop` @ ed27841 (platform 1.2.2-rc.614, 30 Oct)

This is the "what we had / what is broken or missing / what comes next" list asked for on 27 October. It is updated as items are fixed.

## Status on develop head (2 Nov)

| Area | State |
|---|---|
| Approval chain (finalize → signed farmer lookup → Farmer ADD CR → AWE 2 stages → farmer + livestock in the register) | **Works** via API and browser |
| Web intake form in the browser, end to end | **Works**: farmer lookup, survey, location, livestock, health and vaccination saved in the browser (vital event and breeding checked through the API), Submit starts the approval, approved records reach the register with location names |
| Intake duplicate and animal-ownership checks across drafts | **Restored**: #163, #172 and #176 merged |
| Holding state after approval | **Fixed** by #177: an approved holding is VERIFIED |
| File import | **Works** (native, #135); needs the `Staff Portal` partner in Partner Management |
| ODK | In progress (Megha) |
| Reminders / outbreak alert | Scheduled and running (the beat-producer import was checked and is not a bug); mails with real data not checked |
| Dropdowns from Master Data | 11 of the 13 hardcoded dropdowns moved by #178 (openg2p-data #45). Sex, offspring sex and the farmer's gender: PR "Master Data codes" (`LIVESTOCK_SEX` with `SEX_MIXED` from openg2p-data, the farmer registry's `GENDER`) |

## How it was tested

**Run 1 – refactor snapshot 5db011b, 26–27 Oct.** Laptop docker compose with develop's commons (Keycloak, IAM, AWE, ID generator, old Master Data plus a small shim for the new endpoints), the five registry images built from the PR on the public rc.557 base images, and a mock Farmer Registry for the signed lookup. Test assets: API chain scripts, a 54-case validation matrix (51 pass), Playwright browser runs with screenshots, the DCI sanity test.

**Run 2 – develop head 3f2deb6 (#88), 29 Oct.** Asmit's `openg2p-developer` stack (`oan-developer` branch): livestock built from OAN `develop`, commons from the pinned charts, Master Data develop.118 seeded from the ETH-OAN pack (21 037 locations, P-codes), default reviewers `alex.carter` → `nina.patel`, the same mock Farmer Registry (the farmer registry alongside does not fit in the laptop's memory; Asmit: "mock is fine for now"). Local compose overrides only for the mock, the beat database settings and two stack issues listed in section 7.

**Run 3 – develop head 0e10773, 30 Oct.** Same stack; re-test of every open item, plus file import and DCI.

No registry code was modified in runs 1 and 2. Fixes found in run 3 are in their own branches and PRs (section 8).

## 1. What livestock had before the refactor (develop, deployed on dev)

- Web intake form with 8 sections: Farmer (ID, FAN, name, contact), Survey Personnel, Location, Livestock Details, Health Events, Vaccinations, Vital Events, Breeding. 11 registers: Farmer, Livestock, Animal, HealthEvent, Vaccination, VitalEvent, Breeding, Retagging, VaccineSchedule, ImportBatch, AuditLog.
- Farmer enrichment by Farmer ID from the Farmer Registry on submit.
- Single-stage Woreda approval through AWE with a custom approver resolver; change requests on approved records with version history.
- ODK: Collect form → ODK Central → connector → partner API → intake → approval. File import (Excel template, grouped by farmer). DCI search by Farmer ID and ear tag.
- Dialog behaviour: breed and vaccine filtered by species, ear-tag picker of the submission's animals, Species/Age auto-fill, live age, date defaults, ear-tag format check.
- Server rules: duplicate ear tag and event checks, BIRTH reserves offspring ear tags and creates calves, next due date from the vaccine schedule, health/vaccination status auto-update, deceased handling, Region/Zone/Woreda/Kebele names on records.
- Background jobs: vaccination, calving and approval-pending reminders, outbreak alert, audit retention. Animals finder with bulk status update. Dashboard reporting views. Local docker-compose stack.
- All of it was built on platform patches (core find/replace at build, runtime monkeypatches, compiled UI bundle edits). Removing those patches is the point of the refactor.

## 2. New in the refactor (verified)

- No platform patches: behaviour comes from registered service subclasses, `ui/staff-ui/overrides`, metadata seeds and `CELERY_IMPORTS`.
- Farmer linkage: the intake carries only Farmer ID and Fayda FIN/FAN. On submit a signed DCI lookup verifies the farmer; a new farmer gets a Farmer ADD change request, an approved farmer is reused ("Farmer reference linked"). Kafka UPDATE change requests are wired (not testable locally).
- Approval: default OpenG2P pattern, two sequential stages with fixed reviewers (`*.default` policies, `on_empty=block`). The geographic routing tested in run 1 is deferred (`configuration/deferred-geographic/`). Reviewers on dev are configuration (Asmit, 28 Oct).
- Location: one native `geo-hierarchy` widget with a holding-location map (#88), values from Master Data P-codes.
- Fayda eSignet verification popup with read-only FIN; manual FAN works without a provider.
- Field format rules (names, Farmer ID `FR-` + 12 digits, FAN 16, FIN 12, dates) and extension unit tests.
- Verified: API chain end to end in both runs (approval in either order, reject paths, dedup, admin edit → change request → history, DCI by FID in run 1); browser login and the first three sections in run 2.

## 3. Bugs

| # | Finding | Where | Impact | State on develop head |
|---|---|---|---|---|
| 1 | Farmer register seeded with `functional_id_generation_required=TRUE`; `farmer_reference` requires FALSE, so the final Farmer CR webhook returns 500 `FARMER_REFERENCE_EXTERNAL_IDENTIFIER_CONFIGURATION_REQUIRED` | `g2p_register_definitions.sql` | Farmer ADD CR never applies; the livestock record stays held | **Fixed by #95** (29 Oct). Reproduced on 3f2deb6; after setting FALSE by hand AWE's retry completed the chain |
| 2 | Hooks `post_intake_upsert`, `pre_finalize`, `post_approval_stage` came from our removed core patch; the platform only calls `validate_domain_attributes`, `pre_approve`, `post_approve`, `post_ingest`. The methods remain as dead code | all domain services | Lost: calves and offspring ear tags on BIRTH, location names, intake-side duplicate mortality/disease checks, ear-tag-belongs-to-submission check, section re-save fix, livestock state ladder | **Fixed by #163** (merged): a mixin on the intake service calls `post_intake_upsert` after the platform saves a section, so the cross-draft duplicate checks, the ear-tag-belongs-to-submission check and the BIRTH tag reservation run again. #172 (merged) runs the checks on the saving session, so the ingest worker's single transaction (ODK, File Import, partner) sees its own animals; verified with an ODK-shaped submission. #176 checks only the rows of the save and adds DB-backed tests. Calves were still created at ingest. State ladder: see item 17 |
| 3 | ODK: raw submission to `/partner/ingest_data` is rejected (signed envelope required); with an envelope the transform fails `Template not found` (template not registered in `incoming_templates`) | ODK path, seeds | No ODK record reaches the registry | In progress (Megha); ODK form v7 merged (#153) |
| 4 | partner-api returns 500 `Object of type datetime is not JSON serializable` on every ingest | platform rc.557 | Connector retries forever | Not re-run on rc.614 (platform) |
| 5 | Default vaccine schedules no longer seeded | seed | `next_due_date` blank, reminders never fire; works as soon as one schedule row exists | **Fixed on develop** (af5f002): intervals come from the Master Data vaccine list; `next_due_date` filled (2027-10-06 for a 2026-10-06 dose) with no schedule rows |
| 6 | db-seed image lost the callback secret template, code lists, geo seed and its entrypoint | `docker/db-seed/Dockerfile` | AWE webhooks 401; lists and locations not seeded | **Fixed by #81** (entrypoint, callback). Lists and geo now come from Master Data |
| 7 | Extension beat producers use the worker's database engine; beat connects to localhost unless `REGISTRY_CELERY_WORKERS_DB_*` is set on beat | celery-beat config | Producers crash | Open (set locally by override) |
| 8 | AWE seed runs before AWE has created its tables on a fresh stack | seed order | Policies missing on first install | Not reproduced on develop head |
| 9 | staff-api and partner-api both run `migrate` at start | platform | IntegrityError race; app still starts | Open (platform) |
| 10 | Location section showed two sets of Region/Zone/Woreda/Kebele selects | `zzzz_location_widgets.sql` | Confusing UI | **Fixed by #88** |
| 11 | **Species and breed deadlock.** The platform validates coded fields against Master Data and accepts only pack codes (`CATTLE`, `GOATS` …; breed `BREED_IMPROVED` …). The extension accepts only its own `LIVESTOCK_SPECIES_*` values and checks breed against its old list. Every combination is rejected | `g2p_register_domain_service_animal.py`, species config, vaccine schedule defaults | **No animal can be saved**, in the browser or the API; Health, Vaccination, Vital Event and Breeding sections cannot be used; browser Submit refused | **Fixed on develop** (af5f002, species and breeds from Master Data only) |
| 12 | #88 added `geo_hierarchy.py` to copy the widget's hierarchy into `region_id`…`kebele_id` and fill the names, but calls it only from `post_intake_upsert` (dead, see item 2) and `post_approve` (change requests). The intake → register path (`post_ingest`) never calls it | `g2p_register_domain_service_livestock.py` | Drafts from the browser have no region/woreda ids; register rows have no Region/Zone/Woreda/Kebele names | **Fixed** on develop: register rows carry Oromia / East Shewa / Ada'a / Ude Denkaka 01 from a single kebele code |
| 13 | Livestock beat producers (vaccination, calving and approval reminders, outbreak alert, audit retention) are imported through `CELERY_IMPORTS` and registered on the worker, but never enter beat's schedule (17 platform entries only) | `tasks/__init__.py` sets the schedule before beat is configured | Reminders and outbreak alerts never run | **Not a bug.** The producers are in beat's schedule; the run 2 check imported beat without `CELERY_IMPORTS`. The outbreak alert runs every 900 s |
| 14 | No vaccine list and no disease list in Master Data (Vaccine dropdown empty). Age stays blank in the Livestock dialog. Ear tag is a typed field in every event dialog | Master Data pack, UI | Vaccinations cannot be entered in the browser | **Lists fixed** by openg2p-data #24/#27. Age auto-fill and the ear-tag picker remain (section 4, dialogs) |
| 15 | The `lr-reporting-views` job fails: `reporting_views.sql` still joins `g2p_attribute_values` (species and breed names), which 1.2 no longer has. #90 (28 Oct) restored the views but kept that join; it is still on develop | `docker/db-seed/reporting_views.sql` | Dashboard views not created | **Fix in review**: PR "Reporting and small fixes" copies the names from the Master Data catalogue API (as the farmer registry's reporting does) and the oan-helm PR runs it before the views |
| 16 | 13 dropdowns hold hardcoded static options in the section metadata, and the register schemas type them as Enums: sex, health and vaccination status, event types, location, cause, outcome, retag reason. Nothing checks them on save, so an API, ODK or import value such as `Disease` for `DISEASE` is accepted, then fails the approval webhook and the change request stays pending | section metadata, `register_domain/schemas` | Stuck change requests; values not from Master Data | **New.** Fix in review: Master Data lists through openg2p-data #45 and widgets on those lists in #178 (11 of the 13; sex and offspring sex wait for the `LIVESTOCK_SEX` codes and a value for a flock). **#178 merged**; the last two in PR "Master Data codes" |
| 17 | `post_approval_stage` (dead, see item 2) set the holding state; every approved holding is stored with a blank state | `g2p_register_domain_service_livestock.py` | State empty on records and in reports | **Fixed by #177**: VERIFIED on ingest, migration 0011 for existing rows |
| 18 | The platform's default `application_reference_format` is `{DATE}-{SECONDS:5}{RAND:1}`: two intakes created in the same second get the same reference about one time in ten, and the second save fails on the unique index | `registry_core_application_reference_format` (deployment setting) | Lost submissions in ODK or File Import bursts; seen in CI on #176 | **Fix in review** (oan-helm PR): the livestock chart sets `{DATE:%Y%b%d|upper}-{SECONDS:5}{RAND:4}` on the staff API, partner API and workers |

## 4. Missing (removed, to be rebuilt the supported way)

- Dialog behaviour: **rebuilt** in `ui/staff-ui/overrides` (PR "Livestock form dialogs"): ear-tag picker of the form's or record's animals (no deceased animal; females only for breeding and births), Species/Age auto-fill, live age, ear-tag format check, vaccines of the animal's species, Next Due Date on screen; Species and Breed asked before the Ear Tag; a birth's offspring breed and weight. Mandatory approve/reject comment: PR "Staff portal pages". Date defaults are available as metadata (`widget-data-default`).
- File import: **rebuilt by #135** and verified through the portal (Livestock records → Import from file): rows become intakes, the farmer is linked, the approval starts, an approved row reaches the register as a VERIFIED holding with location names. Notes: one row is one holding (three rows of one farmer gave three holdings); the menu showed the configuration's code `file_import_to_livestock_intake` ("Livestock intake" in PR "Reporting and small fixes"); without the `Staff Portal` partner the queue stops at `PARTNER_NOT_REGISTERED` and does not retry.
- DCI search: by Farmer ID worked in run 1. Not re-run in run 3: the local partner API now enforces signatures and consent. Search by ear tag needs the `dci_id_type_columns` setting (deployment values) and a DCI response template for the Animal register; whether any consumer needs it is to be confirmed.
- Animals finder with bulk status update: **rebuilt** as a `ui/` override page (PR "Staff portal pages"): every animal through the platform's own search on the Animal register, filters by species and statuses, and a bulk Health / Vaccination Status update sent as change requests. No model change.
- The repository's own local compose stack and the vendored ODK connector. Reporting views: restored by #90, names fixed by the Master Data label copy.

## 5. Dependencies and environment

- Master Data: the platform needs develop.118 (new geo and attribute endpoints). Asmit's stack has it. The Commons chart in oan-helm ships develop.118; an environment that still runs an older Master Data has empty dropdowns until it is upgraded.
- Geography: P-codes from the ETH-OAN pack. Dev data uses older ids (`kebele-ET…`); the pack's `migration/id_map.csv` maps them.
- Farmer lookup (`COSS_FARMER_*`, keys, record contract, AWE client) is mandatory for Submit; there is no local skip. #81 wires it on New Dev to the real Farmer partner API.
- Reviewers: `alex.carter` / `nina.patel` are example users; real reviewers and roles must be configured in AWE and Keycloak on each environment, otherwise requests stall (`on_empty=block`).
- Fayda eSignet provider and Kafka for farmer UPDATE change requests: not configured locally.

## 6. Not tested yet

Vital event and breeding dialogs in the browser, ODK on develop head, DCI on develop head (signed partner and consent needed), Fayda eSignet popup, Kafka farmer updates, dashboards (report names), reminder and outbreak mails with real data, roles other than the seeded reviewers, New Dev.

## 7. Notes on the local developer stack

Found while running Asmit's `openg2p-developer` on a laptop; worth fixing in that repository:

- Rendered Redis start scripts are written as root with mode 0644, so Redis exits 126. Worked around by running the script through the container's command.
- `master-data-geo-seed` depends on every commons-services pod (MOSIP, ODK, Consent Manager), so a registry-only start pulls about 4 GB of MOSIP images. Worked around by trimming its dependencies to Postgres and the Master Data API.
- The farmer `db-seed` Dockerfile uses `COPY --chmod`, which needs BuildKit (`docker buildx`).
- First login of each seeded user forces a password change.

## 8. Next (order = priority)

1. openg2p-data `SEX_MIXED`, then its Master Data seed image pinned in Commons, before PR "Master Data codes".
2. PRs "Livestock form dialogs", "Master Data codes", "Staff portal pages", "Reporting and small fixes" and the oan-helm PR (label job, reference format): review and merge. The first two touch the same section metadata; the second to merge needs a rebase.
3. File import "one row = one holding", DCI by ear tag: decisions pending.
4. A livestock staging profile in oan-helm (staging deploys are skipped until it exists).
6. After each PR: re-run this validation on develop head; then test on New Dev with the real Farmer Registry.
