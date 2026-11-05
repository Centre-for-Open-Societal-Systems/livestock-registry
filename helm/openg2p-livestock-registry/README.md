# OAN Livestock Registry

OpenAgriNet (OAN) application developed in the Centre for Open Societal Systems
(COSS) repositories. This chart reuses the pinned OpenG2P registry platform.

| Source | GitHub repository |
| --- | --- |
| OAN application | [livestock-registry](https://github.com/Centre-for-Open-Societal-Systems/livestock-registry) |
| OAN Helm sources | [oan-helm](https://github.com/Centre-for-Open-Societal-Systems/oan-helm/tree/main/charts/openg2p-livestock-registry) |
| OAN dashboard component | [livestock-registry-dashbaord-api](https://github.com/Centre-for-Open-Societal-Systems/livestock-registry-dashbaord-api) |
| OAN dashboard component | [oan_livestock_dashboard](https://github.com/Centre-for-Open-Societal-Systems/oan_livestock_dashboard) |

The Helm chart name retains its `openg2p-` prefix to preserve the existing release
and resource names. It does not identify the application source owner. The
OpenG2P dependency repository contains reused platform templates; application
images and provenance are configured by this OAN chart.

Use chart version **1.0.0-dev.5** and upgrade the current release in its current
namespace. Review private values, image digests and namespace-local Secret
references before applying changes. Optional dashboard components remain at
their explicit enablement settings; DA workloads await verified images/config.

See [included services](https://github.com/Centre-for-Open-Societal-Systems/oan-helm/blob/main/docs/service-catalog.md),
[readiness](https://github.com/Centre-for-Open-Societal-Systems/oan-helm/blob/main/docs/readiness.md) and
[Rancher instructions](https://github.com/Centre-for-Open-Societal-Systems/oan-helm/blob/main/docs/rancher-dev.md).

Dev URLs use `<service>.development.oanstaging.com`. The environment-owned
wildcard DNS/TLS and `istio-system/development` Gateway must be prepared first.
See the service onboarding and enablement guide in `docs/service-onboarding.md`.

## Farmer reference

The Livestock extension resolves the Farmer named on an intake with a signed,
consent-enforced DCI lookup of the Farmer registry, creates the local Farmer
reference through its own change request and AWE approval, and receives later
Farmer updates through Farmer outgestion (Kafka/WebSub) and the Livestock connector
as local UPDATE change requests. It is configured by `COSS_FARMER_*` variables
and read-only files, never by values carrying private material:

- `farmerReference` renders ConfigMap `<release>-farmer-reference` with the
  server-owned `record-contract.json` and the Farmer partner API's
  response-signing `source-public-key.pem` (from `openg2p-farmer-registry`'s
  `dciSigning` ConfigMap `<farmer release>-dci-signing-public`).
- The Livestock lookup key stays in a Secret provisioned in the namespace (on New
  Dev `livestock-farmer-lookup-signing-ed25519`, key `private-key.pem`, registered
  in Partner Management under `Live_stock_partner_internal`); the AWE client
  secret is the chart's own `<release>-staff-portal` Secret.
- `registry.staffApi`, `partnerApi`, `celeryWorker` and `celeryBeat` mount the
  three read-only and carry the variables; the celery worker also needs
  `REGISTRY_CELERY_WORKERS_AWE_ENABLED` and `_AWE_CALLBACK_SECRET_ID` because
  the extension's worker starts the Farmer change-request workflow.

`environments/dev/values/livestock.yaml` is the New Dev wiring. The extension's
deployment guard (`ci/refactor/deployment_guard.py` in the registry repository)
checks the rendered workloads for exactly this shape before every deploy.
