# Livestock Registry — dev runbook

For the current new dev server (`livestock` namespace, shared `commons`, ODK
project 6), use [Livestock ODK on new dev](odk-new-dev.md). The topology below
records the earlier deployment and its namespace/project settings.

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
| Master Data (geo + code lists) | commons master-data (1.1 or later) | geo and the livestock code lists (species, breed, disease, vaccine, ...) loaded by our db-seed |
| ODK Central | `https://odk-central-development.oanstaging.com`, project 14, form `livestock_registry` (v4) | form + media in `odk/` |
| ODK connector | namespace `common` | pipeline polls project 14 and posts to our partner API with data model `ODK_TO_LIVESTOCK_INTAKE` |

Platform base: registry-platform `1.2.2-rc.544` (chart dependency in
`helm/openg2p-livestock-registry/Chart.yaml`). From 1.2 on, the code lists
come from Master Data; the registry no longer has its own attribute tables.

## 2. How a deploy happens

- A push or merge to `develop` triggers Jenkins: images are built, pushed to
  ECR, and `helm upgrade --install livestock-registry` runs in namespace
  `live` with `values-dev.yaml`.
- The db-seed job runs on every deploy. It first converts any
  latitude / longitude / altitude column still stored as text (a database
  created on registry-platform 0.0.0-develop.296) to a number; a column that
  holds a non-numeric value is left as it is and named in a `WARNING` line of
  the job log. It then loads the registry metadata, the Ethiopia geo
  hierarchy and the livestock code lists into Master Data, the AWE policy/stages/approver
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
| 4 | ODK connector pipeline in namespace `common`: Central base URL, project 14, form `livestock_registry`, data model `ODK_TO_LIVESTOCK_INTAKE`, target our partner API, a Central web user with access to project 14 | DevOps | connector UI shows `last_poll_status = SUCCESS` |
| 5 | AWE trusts tokens issued by `keycloak-livestock-development` | DevOps | finalizing a submission does not answer `Invalid issuer` |
| 6 | SMTP for reminder and outbreak mails | DevOps | not configured on dev today; jobs run but no mail is sent |
| 7 | Master Data 1.1 or later in the commons, reachable by the registry with a bearer token: CSRF off for API reads (`MASTER_DATA_API_CSRF_ENABLED=false`) | DevOps | the Livestock form shows species and breed lists; db-seed log shows `code lists: ... values in 5 lists` |
| 8 | Partner Management: partners `Livestock` (ODK sender) and `Staff Portal` (File Import), or Partner Management not configured for the registry | DevOps | ODK ingest does not fail with `PARTNER_NOT_REGISTERED` |
| 9 | Secret `commons-services-staff-portal` exists in `live` | DevOps | staff API pod starts without a missing-secret error |
| 10 | IAM 1.4: column `staff_portal_applications.api_url` exists in the IAM database (an IAM database created on 1.3 lacks it) | DevOps | IAM registration job succeeds |
| 11 | The ODK connector's sender id is `Livestock` | DevOps / Asmit | same check as item 8 |

## 4. What the chart sets (for reference)

- Celery worker: `ODK_HOOKS_ENABLED=true`, AWE settings under its own prefix
  (`REGISTRY_CELERY_WORKERS_AWE_*`), the service-account token settings
  (`..._AWE_TOKEN_URL`, `..._CLIENT_ID`, client secret from the portal
  client's secret), and on dev the `live-ca-bundle` with `SSL_CERT_FILE`.
- Partner API and celery beat: `ODK_HOOKS_ENABLED=true`. The staff API never
  loads the ODK hooks.
- AWE: one approval stage, `Woreda Approval`, mode `any-n` with 1 (any one
  Woreda approver of the record's woreda approves). The earlier Woreda, Zone
  and Region stages are kept in the AWE database for the history of old
  requests, renamed `(retired)` and always skipped.
- Notifications: the 1.2 staff UI reads the Novu hosts from
  `global.notificationApiHostname` / `notificationWsHostname`; dev sets them to
  the internal domain because there is no public Novu yet.

## 5. Checking a deploy

Run these in order after every deploy. Each needs only a browser or the test
users.

1. **Pods.** All `livestock-registry-*` pods `Running`; the db-seed job
   `Completed`.
2. **Login.** Open the portal and log in as a field officer. Dashboard loads,
   no 401/500 toasts.
3. **Web record.** Create a submission with all sections (farmer, survey,
   location, one animal, health, vaccination, vital, breeding) and submit.
   It must show `Pending` and a task must appear for the Woreda approver of
   that woreda.
4. **Approval.** Approve as the Woreda approver. The record becomes
   `VERIFIED` and appears in the register with an `LS-` id, animals with
   `AN-` ids and a next due date on the vaccination.
5. **ODK.** Submit one test form in ODK Central (web form or Collect). Within
   about a minute it appears as a pending submission with coded values
   (species, breed, disease, vaccine) and location names filled, and a Woreda
   task exists. Approve it as in step 4.
6. **Rejection.** A value the registry does not know (for example an animal
   sex outside Male/Female/Mixed) is rejected with a message, not saved.

## 5a. Repairing records from before the fix (one time)

Two kinds of old records need a one-time repair after the first deploy that
carries the worker AWE settings and the webhook fix. Do this after section 5
passes for a fresh record.

**Finalized intakes with no approval workflow** (ODK / File Import records
that show `FINAL / PENDING` and no task for anyone). In the celery worker pod:

```
python3 /app/scripts/backfill_awe_workflows.py            # list only, changes nothing
python3 /app/scripts/backfill_awe_workflows.py --apply    # attach workflows
```

The list marks each record `WOULD ATTACH`, `INVALID` (fails today's
validation; the reason is printed), `DUPLICATE` (several intakes from one ODK
submission) or `NO_SOURCE` (no linked ingestion message). Only the first kind
is processed by `--apply`. Decide the others with the team, then process a
chosen record with `--apply --submission-id <id>`. Running it twice creates
nothing twice: AWE keys the request by the submission.

**Records AWE approved or rejected but the registry still shows PENDING**
(the AWE callback was refused before the webhook fix). Re-send those
callbacks from AWE: list the failed deliveries with
`GET /v1/awe/admin/deliveries?status=<failed status>` and re-queue each with
`POST /v1/awe/admin/deliveries/{id}/retry` (role `AWE_ADMIN`; the AWE admin
UI shows the same deliveries). The registry then applies the decision as it
does for a new one.

## 6. Where to look when something fails

| Symptom | Likely cause | Where to look |
|---|---|---|
| Approval stops after the first approver, request stays in review | AWE stage mode not supported (was `any`, fixed to `any-n`) | AWE `approval_stage.mode` for policy `registry.intake_form.livestock` |
| ODK ingest fails with `attached to a different loop` | celery worker image older than this branch | celery worker image tag |
| Saving a record with a location fails on a numeric column | geo columns still text; see the db-seed `WARNING` line | `kubectl logs job/livestock-registry-db-seed -n live` |
| Approved submission never reaches the register, staff API logs `AWE webhook HMAC secret is not configured` | staff API read an empty settings instance | fixed in the extension (`_create_app_settings_first`); check the staff API image is current |
| ODK submission finalized but no approver task | worker could not start the AWE request: token (item 1 above) or certificate (item 2) | celery worker logs around `AWE workflow` |
| ODK submission missing entirely | connector not polling, or partner/data model missing | connector UI; partner API logs for `DATA_MODEL_NOT_FOUND` / `PARTNER_NOT_REGISTERED` |
| Every helm upgrade fails with a `valueFrom` error | a variable was set by hand on the deployment | section 2 |
| db-seed job failed | read the job log; duplicate-key errors alone are not a failure | `kubectl logs job/livestock-registry-db-seed -n live` |

## 7. Known limits on dev today

- No reminder or outbreak mail (no SMTP).
- No in-app notifications (no public Novu on dev).
- The state label of a verified record still reads "Region approved
  (verified)" from the four-level days; the state itself is correct.
