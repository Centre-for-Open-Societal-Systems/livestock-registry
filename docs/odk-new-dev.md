# Livestock ODK on new dev

Verified on 2026-10-19 over SSH to `new-gen2-development`. The registry and
connector run in namespace `livestock`; shared ODK, Partner Management (PM),
Keycloak and AWE run in `commons`. This is the current environment, rather than
the earlier `live` / project 14 topology in the historical runbook.

## Configuration for future submissions

| Setting | Verified value |
| --- | --- |
| Registry API/worker revision | `bf78e69a5fd6` |
| Connector ID | `39d1d807180545bf9c3fb7fdd83b904d` |
| Connector name | `Livestock ODK Central` |
| ODK Central | `https://odk-central-development.oanstaging.com` |
| ODK project / form / version | `6` / `livestock_registry` / `v4` |
| Connector data model | `ODK_TO_LIVESTOCK_INTAKE` (verified on 2026-10-19 as `LIVESTOCK_ODK_MODEL`; see the next section) |
| Envelope sender / register mnemonic | `Livestock` / `Livestock` |
| Active PM partner | `PARTNER_LIVESTOCK` |
| Registry ingestion target | `http://livestock-registry-partner-api.livestock.svc.cluster.local/partner/ingest_data` |

## Data model rename

The data model is named after its flow, `ODK_TO_LIVESTOCK_INTAKE` (id
`odk_to_livestock_intake`). It replaces both `LIVESTOCK_ODK_MODEL` and the
generic `MY_DATA_MODEL`. Its key path, semantic pattern, incoming template
(`odk_to_livestock_intake_template`, rendering `odk_to_livestock_intake.j2`)
and the response template are all seeded by
`meta_data/zz-oan/20_odk_to_livestock_intake.sql`, which also moves the
ingested history (`incoming_raw_data`, `incoming_classified_data`) to the new
model and deletes the two retired models and their rows by explicit id. The
seed fails if any row still references a retired model. Switch the connector
(PATCH `{"data_model_mnemonic":"ODK_TO_LIVESTOCK_INTAKE"}`) when this seed is
deployed; the retired mnemonics stop resolving at that point.

## Configuration verified on 2026-10-19

The connector previously selected the generic `MY_DATA_MODEL`. Following the
Farmer connector's explicit `FARMER_ODK_MODEL` configuration, only livestock's
`data_model_mnemonic` was changed through `PATCH /connectors/{connector_id}`.
The dedicated model, key paths and semantic routing were already seeded. This
also agrees with this repository's local connector seed. Credentials, source
configuration, enabled/paused state, sender and polling checkpoint were preserved.

The deployed registry looks up `Livestock` first, then its normalized reference
`PARTNER_LIVESTOCK`. With the registry's own service account, the latter returns
HTTP 200 and `status: active`; its public key endpoint also returns 200. The raw
`Livestock` lookup returns 404, which this implementation handles with the
fallback. An additional PM partner is unnecessary in this environment.

Keep the sender as `Livestock`: the dedicated model's matching expression is
`$.body.header.sender_id=>^Livestock$`. Changing the sender to the normalized PM
ID would also require changing that contract. A legacy Master Data partner row
or a `partner-id` source-config header does not onboard a PM partner; the
connector client sends the sender in the JSON envelope.

The historical `PARTNER_NOT_REGISTERED` failures were genuine, but the existing
partner resolved successfully before the model change. The live checks do not
establish the original cause of those historical failures.

## Operator checks

1. From the partner API pod, obtain the configured PM service token without
   printing it. Check `GET /partners/PARTNER_LIVESTOCK` with that token and
   `GET /keys/PARTNER_LIVESTOCK` on the configured PM partner API. Both must
   return 200, and the administrative response must report `active`.
2. Read the existing connector and confirm the table above. To align an older
   pipeline, PATCH only `{"data_model_mnemonic":"ODK_TO_LIVESTOCK_INTAKE"}` through
   the connector API. Do not rerun the local seed against dev: its connector ID
   and project 14 configuration describe a separate local pipeline.
3. Trigger `POST /connectors/{connector_id}/poll` or wait for the scheduled poll
   (about every 5 minutes on New Dev, so a new submission can take that long to arrive).
   Check the completed poll status and error, rather than treating the queue's
   HTTP 202 as success. An idle poll may legitimately fetch zero records.
4. For a new submission, require a successful connector run with a nonempty
   registry correlation ID. Follow it through `incoming_raw_data`,
   `incoming_classified_data` and `g2p_intake_form_submissions`. Partner API
   HTTP 200 alone is insufficient: inspect `response_header.response_status`.
5. Check that transformation and ingestion are `PROCESSED`, exactly one intake
   exists, and a finalized intake has an AWE request. Approval and register
   promotion remain separate checks.

The model-only change does not require resetting the checkpoint or changing
partner registration. The retired models are deleted by the seed, so there is no
PATCH back to `MY_DATA_MODEL` or `LIVESTOCK_ODK_MODEL`; roll back by deploying
the previous release, which seeds them again.

## Validation evidence

A new synthetic OData-shaped event was passed through the existing connector
ingestion service, real partner API and asynchronous registry workers. No ODK
submission was created for this synthetic event.

| Evidence | Value |
| --- | --- |
| Synthetic source instance | `uuid:295e48f1-d5e7-4cf3-96be-d266b676fda5` |
| Connector run | `45ea354dbcf446199feadbc99ef264d5` |
| Registry correlation ID | `d5348e387de841ad92ef0e4ff396592b` |
| Intake submission | `c728eba5-5cbe-463c-8c39-49d0462eafac` |
| AWE request | `ce04c75f-7c62-449f-a7d6-741e68b846a3` |

- Classification, transformation and ingestion completed without errors using
  the dedicated model and `PARTNER_LIVESTOCK`.
- Exactly one holding, farmer, animal, health event, vaccination, vital event
  and breeding event were staged. Geography resolved to Oromia / East Shewa /
  Ada'a / Dire 01. Species, breed, animal sex and vaccine became registry codes;
  the vaccination's supplied next-due date was retained.
- Redelivery returned the same connector run and correlation ID, with
  `redelivery_count=1`. Exactly one registry message and intake remained.
- A normal ODK poll completed `SUCCESS`, fetching zero records with no error.
  Its timestamp checkpoint remained `2026-10-16T06:29:32.318Z`.
- Existing `odk/test_transform.py` passed: five sample submissions plus targeted
  mapping and breed cases. It ran from an isolated temporary copy in the dev
  partner pod, which has Jinja installed; application files were not changed.

One targeted replay recovered historical source instance
`uuid:7bf197bc-25cb-4031-aa8a-f02f0d1d9c57` into intake
`0a4cfdc8-16b3-467a-ac05-cb7e424f5720`. Both that intake and the synthetic intake
remain `FINAL / PENDING` with AWE requests. Neither was approved in this work.
Repeated historical dead letters were retained and must not be bulk-replayed.

## Fresh Central upload verification

A fresh synthetic XML submission was accepted through Central's normal REST
endpoint on 2026-10-19 (HTTP 200), using an explicitly authorized upload identity.
No ODK permissions or accounts were changed. Record and request identifiers for
this test are retained in local evidence rather than published here.

- A normal poll fetched exactly one new Central submission. The connector run
  succeeded on its first attempt with no error, resolving `PARTNER_LIVESTOCK`.
- Classification, transformation and intake ingestion each reached `PROCESSED`.
  OData expansion retained one health, vaccination, vital and breeding event.
- Exactly one holding, farmer, animal and each event type reached intake.
  Geography resolved to Oromia / East Shewa / Ada'a / Dire 01; the animal became
  cattle / local zebu / female, and vaccination became
  `VACCINE_TYPE_ANTHRAX_CATTLE` with next-due date `2027-10-01`.
- The follow-up poll succeeded with zero fetched records. The checkpoint advanced
  to the fresh instance's submission timestamp; exactly one connector run,
  registry message and intake remained.
- The fresh intake is `FINAL / PENDING` with an AWE request. Approval, register
  promotion and web creation remain unverified by these checks. Historical
  submissions received no further changes during this fresh-upload test.

Postman CLI could not start because its managed Private Cloud manifest was
unreadable. Live checks used HTTP clients within the existing pods; no Postman
collection run is claimed.
