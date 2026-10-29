# Livestock Registry – validation of the native refactor (PR #78)

Yash Sontakke · 26–29 October 2026 · findings checked against COSS `develop` @ cb8b9cf (29 Oct, 11:30)

This is the "what we had / what is broken or missing / what comes next" list asked for on 27 October. It is updated as items are fixed.

## Status on develop head (29 Oct)

| Area | State |
|---|---|
| Approval chain (finalize → signed farmer lookup → Farmer ADD CR → AWE 2 stages → farmer + livestock in the register) | **Works** via API (on 3f2deb6 with the Farmer flag set by hand; #95 fixes the seed) |
| Web intake form in the browser, end to end | **Blocked.** Farmer Identity, Survey and Location save; Livestock Details cannot be saved (B11), so no event section can be filled and Submit is refused |
| ODK | **Blocked** (B3, B4) |
| File import | **Missing** |
| Reminders / outbreak alert | **Not running** (B13) |
| Dropdowns from Master Data | Species, breed (3 generic values), location work; vaccine and disease lists missing (B14) |

## How it was tested

**Run 1 – PR #78 snapshot 5db011b, 26–27 Oct.** Laptop docker compose with develop's commons (Keycloak, IAM, AWE, ID generator, old Master Data plus a small shim for the new endpoints), the five registry images built from the PR on the public rc.557 base images, and a mock Farmer Registry for the signed lookup. Test assets: API chain scripts, a 54-case validation matrix (51 pass), Playwright browser runs with screenshots, the DCI sanity test.

**Run 2 – develop head 3f2deb6 (#88), 29 Oct.** Asmit's `openg2p-developer` stack (`oan-developer` branch): livestock built from COSS `develop`, commons from the pinned charts, Master Data develop.118 seeded from the ETH-OAN pack (21 037 locations, P-codes), default reviewers `alex.carter` → `nina.patel`, the same mock Farmer Registry (the farmer registry alongside does not fit in the laptop's memory; Asmit: "mock is fine for now"). Local compose overrides only for the mock, the beat database settings and two stack issues listed in section 7.

No registry code was modified in either run.

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
| B1 | Farmer register seeded with `functional_id_generation_required=TRUE`; `farmer_reference` requires FALSE, so the final Farmer CR webhook returns 500 `FARMER_REFERENCE_EXTERNAL_IDENTIFIER_CONFIGURATION_REQUIRED` | `g2p_register_definitions.sql` | Farmer ADD CR never applies; the livestock record stays held | **Fixed by #95** (29 Oct). Reproduced on 3f2deb6; after setting FALSE by hand AWE's retry completed the chain |
| B2 | Hooks `post_intake_upsert`, `pre_finalize`, `post_approval_stage` came from our removed core patch; the platform only calls `validate_domain_attributes`, `pre_approve`, `post_approve`, `post_ingest`. The methods remain as dead code | all domain services | Lost: calves and offspring ear tags on BIRTH, location names, intake-side duplicate mortality/disease checks, ear-tag-belongs-to-submission check, section re-save fix, livestock state ladder | **Open** |
| B3 | ODK: raw submission to `/partner/ingest_data` is rejected (signed envelope required); with an envelope the transform fails `Template not found` (template not registered in `incoming_templates`) | ODK path, seeds | No ODK record reaches the registry | Open (not re-run) |
| B4 | partner-api returns 500 `Object of type datetime is not JSON serializable` on every ingest | platform rc.557 | Connector retries forever | Open (platform) |
| B5 | Default vaccine schedules no longer seeded | seed | `next_due_date` blank, reminders never fire; works as soon as one schedule row exists | **Open** (0 schedule rows) |
| B6 | db-seed image lost the callback secret template, code lists, geo seed and its entrypoint | `docker/db-seed/Dockerfile` | AWE webhooks 401; lists and locations not seeded | **Fixed by #81** (entrypoint, callback). Lists and geo now come from Master Data |
| B7 | Extension beat producers use the worker's database engine; beat connects to localhost unless `REGISTRY_CELERY_WORKERS_DB_*` is set on beat | celery-beat config | Producers crash | Open (set locally by override) |
| B8 | AWE seed runs before AWE has created its tables on a fresh stack | seed order | Policies missing on first install | Not reproduced on develop head |
| B9 | staff-api and partner-api both run `migrate` at start | platform | IntegrityError race; app still starts | Open (platform) |
| B10 | Location section showed two sets of Region/Zone/Woreda/Kebele selects | `zzzz_location_widgets.sql` | Confusing UI | **Fixed by #88** |
| B11 | **Species and breed deadlock.** The platform validates coded fields against Master Data and accepts only pack codes (`CATTLE`, `GOATS` …; breed `BREED_IMPROVED` …). The extension accepts only its own `LIVESTOCK_SPECIES_*` values and checks breed against its old list. Every combination is rejected | `g2p_register_domain_service_animal.py`, species config, vaccine schedule defaults | **No animal can be saved**, in the browser or the API; Health, Vaccination, Vital Event and Breeding sections cannot be used; browser Submit refused | **New, blocker** |
| B12 | #88 added `geo_hierarchy.py` to copy the widget's hierarchy into `region_id`…`kebele_id` and fill the names, but calls it only from `post_intake_upsert` (dead, B2) and `post_approve` (change requests). The intake → register path (`post_ingest`) never calls it | `g2p_register_domain_service_livestock.py` | Drafts from the browser have no region/woreda ids; register rows have no Region/Zone/Woreda/Kebele names | **New.** One call in `post_ingest` fixes it |
| B13 | Livestock beat producers (vaccination, calving and approval reminders, outbreak alert, audit retention) are imported through `CELERY_IMPORTS` and registered on the worker, but never enter beat's schedule (17 platform entries only) | `tasks/__init__.py` sets the schedule before beat is configured | Reminders and outbreak alerts never run | **New** |
| B14 | No vaccine list and no disease list in Master Data (Vaccine dropdown empty). Age stays blank in the Livestock dialog. Ear tag is a typed field in every event dialog | Master Data pack, UI | Vaccinations cannot be entered in the browser | **New** |

## 4. Missing (removed, to be rebuilt the supported way)

- Dialog behaviour: breed and vaccine by species, ear-tag picker, Species/Age auto-fill, live age, ear-tag format check. Date defaults are available as metadata (`widget-data-default`).
- File import: no import configuration or template ("Import from file: No options available").
- DCI search by Farmer ID and ear tag (only FID; FAN as UIN rejected).
- Animals finder with bulk status update.
- The repository's own local compose stack and the vendored ODK connector. Reporting views were restored by #90 (29 Oct, not re-tested).

## 5. Dependencies and environment

- Master Data: the platform needs develop.118 (new geo and attribute endpoints). Asmit's stack has it; dev still runs the old Master Data, so dropdowns will be empty there until it is upgraded.
- Geography: P-codes from the ETH-OAN pack. Dev data uses older ids (`kebele-ET…`); the pack's `migration/id_map.csv` maps them.
- Farmer lookup (`COSS_FARMER_*`, keys, record contract, AWE client) is mandatory for Submit; there is no local skip. #81 wires it on New Dev to the real Farmer partner API.
- Reviewers: `alex.carter` / `nina.patel` are example users; real reviewers and roles must be configured in AWE and Keycloak on each environment, otherwise requests stall (`on_empty=block`).
- Fayda eSignet provider and Kafka for farmer UPDATE change requests: not configured locally.

## 6. Not tested yet

Health, vaccination, vital event and breeding sections on develop head (blocked by B11), next due date on develop head, ODK on develop head, Fayda eSignet popup, Kafka farmer updates, dashboards, reminder and outbreak mails with real data, roles other than the seeded administrators, New Dev.

## 7. Notes on the local developer stack

Found while running Asmit's `openg2p-developer` on a laptop; worth fixing in that repository:

- Rendered Redis start scripts are written as root with mode 0644, so Redis exits 126. Worked around by running the script through the container's command.
- `master-data-geo-seed` depends on every commons-services pod (MOSIP, ODK, Consent Manager), so a registry-only start pulls about 4 GB of MOSIP images. Worked around by trimming its dependencies to Postgres and the Master Data API.
- The farmer `db-seed` Dockerfile uses `COPY --chmod`, which needs BuildKit (`docker buildx`).
- First login of each seeded user forces a password change.

## 8. Next (order = priority; one PR each)

1. **B11 + B14**: move the extension to the pack codes (species config, breed, vaccine schedule defaults); PR to openg2p-data with breed names, vaccine and disease lists. This unblocks the browser intake.
2. **B5**: vaccine schedule seed keyed by pack codes (B1 done in #95).
3. **B12** and the rest of **B2**: call the geo sync from `post_ingest`; move calves on BIRTH, duplicate checks and the state ladder to `post_approve` / `post_ingest` or a registered intake-service subclass.
4. **B13, B7**: register the livestock beat schedule after beat is configured; document the beat database settings.
5. **ODK (B3)**: transform template seed and the signed envelope path; report B4 and B9 to OpenG2P.
6. **Dialog behaviour** as registered widgets under `ui/staff-ui/overrides` (ear-tag picker, auto-fill, live age); species cascade via `widget-cascade` where the metadata supports it.
7. **File import** as native import configuration and template, grouping by farmer.
8. DCI id types, reporting views, local compose notes.
9. After each PR: re-run this validation on develop head; then test on New Dev with the real Farmer Registry.
