# Livestock Registry — dev runbook

How the livestock registry is deployed and configured on the development
cluster, what has to be in place outside this repo, and how to check that a
deploy works end to end. Written for the deployment war room of 12 Oct 2026.

## 1. What runs where

| Piece | Where | Notes |
|---|---|---|
| Staff portal (UI) | `https://livestock-registry-development.oanstaging.com` | namespace `live`, release `livestock-registry` |
| Staff portal API, partner API, celery worker, celery beat, db-seed job | namespace `live` | images built by Jenkins from this repo |
| Keycloak (staff realm) | `https://keycloak-livestock-development.oanstaging.com`, realm `staff` | portal client `livestock-registry-staff-portal` |
| AWE (approvals) | `commons-services-awe` in `live` (`https://awe.live.openg2p.test`) | shared commons; certificate from the box's local CA |
| Master Data (geo + code lists) | `commons-postgresql` / commons master-data | geo loaded by our db-seed |
| ODK Central | `https://odk-central-development.oanstaging.com`, project 14, form `livestock_registry` (v3) | form + media in `odk/` |
| ODK connector | namespace `common` | pipeline polls project 14 and posts to our partner API with data model `LIVESTOCK_ODK_MODEL` |

Platform base on `develop`: registry-platform `0.0.0-develop.296` (chart
dependency in `helm/openg2p-livestock-registry/Chart.yaml`).

## 2. How a deploy happens

- A push or merge to `develop` triggers Jenkins: images are built, pushed to
  ECR, and `helm upgrade --install livestock-registry` runs in namespace
  `live` with `values-dev.yaml`.
- The db-seed job runs on every deploy. It loads the registry metadata, the
  Ethiopia geo hierarchy into Master Data, the AWE policy/stages/approver
  rules, the AWE callback secret, and rewrites the approver-resolver rule URLs
  to this release's staff API.
- Duplicate-key errors in the db-seed log are normal (seed files are re-run);
  the job must end `Completed`.

Do not set environment variables on the deployments by hand (`kubectl set
env`). When the chart later takes the same variable over, every helm upgrade
fails with `valueFrom ... may not be specified when value is not empty` (seen
23 Sep). Put the value in `values-dev.yaml` instead.

## 3. Configuration that lives outside this repo

These have to be in place once per environment. None of them is created by
the chart.

| # | What | Owner | Check |
|---|---|---|---|
| 1 | Keycloak client `livestock-registry-staff-portal` has **Service accounts enabled**, and its secret is in the `livestock-registry-staff-portal` Kubernetes secret (`client_secret`) | DevOps | A client-credentials token request for the client returns 200 |
| 2 | ConfigMap `live-ca-bundle` (key `ca-bundle.pem`) exists in `live` | DevOps | already used by the staff API; the celery worker now mounts it too |
| 3 | Partner `Livestock` (ODK sender) and `Staff Portal` (File Import) exist in Master Data `g2p_partners` | db-seed creates them; DevOps only if the seed cannot reach Master Data | ingest of an ODK submission does not fail with `PARTNER_NOT_REGISTERED` |
| 4 | ODK connector pipeline in namespace `common`: Central base URL, project 14, form `livestock_registry`, data model `LIVESTOCK_ODK_MODEL`, target our partner API, a Central web user with access to project 14 | DevOps | connector UI shows `last_poll_status = SUCCESS` |
| 5 | AWE trusts tokens issued by `keycloak-livestock-development` | DevOps | finalizing a submission does not answer `Invalid issuer` |
| 6 | SMTP for reminder and outbreak mails | DevOps | not configured on dev today; jobs run but no mail is sent |

## 4. What the chart sets (for reference)

- Celery worker: `ODK_HOOKS_ENABLED=true`, AWE settings under its own prefix
  (`REGISTRY_CELERY_WORKERS_AWE_*`), the service-account token settings
  (`..._AWE_TOKEN_URL`, `..._CLIENT_ID`, client secret from the portal
  client's secret), and on dev the `live-ca-bundle` with `SSL_CERT_FILE`.
- Partner API and celery beat: `ODK_HOOKS_ENABLED=true`. The staff API never
  loads the ODK hooks.
- AWE stages: Kebele, Woreda, Zone, Region, each `any-n` with 1 (any one
  resolved approver approves the stage).

## 5. Checking a deploy

Run these in order after every deploy. Each needs only a browser or the test
users.

1. **Pods.** All `livestock-registry-*` pods `Running`; the db-seed job
   `Completed`.
2. **Login.** Open the portal and log in as a field officer. Dashboard loads,
   no 401/500 toasts.
3. **Web record.** Create a submission with all sections (farmer, survey,
   location, one animal, health, vaccination, vital, breeding) and submit.
   It must show `Pending` and a Kebele task must appear for the Kebele
   approver of that kebele.
4. **Approval chain.** Approve as Kebele, Woreda, Zone, Region approver.
   After each step the record moves to the next stage; after Region it is
   `VERIFIED` and appears in the register with an `LS-` id, animals with
   `AN-` ids and a next due date on the vaccination.
5. **ODK.** Submit one test form in ODK Central (web form or Collect). Within
   about a minute it appears as a pending submission with coded values
   (species, breed, disease, vaccine) and location names filled, and a Kebele
   task exists. Approve it through the chain as in step 4.
6. **Rejection.** A value the registry does not know (for example an animal
   sex outside Male/Female/Mixed) is rejected with a message, not saved.

## 6. Where to look when something fails

| Symptom | Likely cause | Where to look |
|---|---|---|
| Approval stops after the first approver, request stays in review | AWE stage mode not supported (was `any`, fixed to `any-n`) | AWE `approval_stage.mode` for policy `registry.intake_form.livestock` |
| Approved submission never reaches the register, staff API logs `AWE webhook HMAC secret is not configured` | staff API read an empty settings instance | fixed in the extension (`_create_app_settings_first`); check the staff API image is current |
| ODK submission finalized but no approver task | worker could not start the AWE request: token (item 1 above) or certificate (item 2) | celery worker logs around `AWE workflow` |
| ODK submission missing entirely | connector not polling, or partner/data model missing | connector UI; partner API logs for `DATA_MODEL_NOT_FOUND` / `PARTNER_NOT_REGISTERED` |
| Every helm upgrade fails with a `valueFrom` error | a variable was set by hand on the deployment | section 2 |
| db-seed job failed | read the job log; duplicate-key errors alone are not a failure | `kubectl logs job/livestock-registry-db-seed -n live` |

## 7. Known limits on dev today

- Dialog text fields drop letters when typing fast. This is a platform bug,
  fixed in registry-platform 1.2.2; it goes away with the 1.2 upgrade.
- No reminder or outbreak mail (no SMTP).
- Approval is four levels. The decision to reduce it to one level (DA, then
  Woreda) is agreed and not yet implemented.
- The registry-platform 1.2 upgrade (G2R-320) is ready locally and not yet
  deployed; it needs the Master Data, Partner Management and Keycloak checks
  listed in the upgrade notes before it goes to dev.
