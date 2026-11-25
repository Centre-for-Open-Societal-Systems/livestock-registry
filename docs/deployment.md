# Deployment

How the Livestock Registry reaches each environment, and where the detailed procedures are. Each change goes through
Jenkins. Never run `helm` or `psql` against an environment by hand. What has to be in place outside this repository,
and how to check a deploy end to end, is in the [dev runbook](runbook-dev.md).

## What is deployed

| Release | What it is |
| --- | --- |
| `livestock-registry` | The chart `helm/openg2p-livestock-registry`, which wraps the OpenG2P `openg2p-registry` chart at the platform version in its `appVersion`. It runs the six platform images built here: staff-api, staff-ui, partner-api, celery (worker and beat), db-seed and sanity-tests, and the dashboard API. |
| `livestock-connector` | The connector API and UI images (`registry-connector`, `registry-connector-ui`), with the chart in [`ci/connector/chart`](../ci/connector/chart). See [the connector release](../ci/connector/README.md). |
| dashboard UI | See [dashboard delivery](dashboard-delivery.md). On staging it is the release `livestock-registry-dashboard`. |

Image names follow [`ci/image_names.py`](../ci/image_names.py). Farmer, Crop and the shared Commons services
(Keycloak, AWE, ODK Central, MinIO, PostgreSQL) are separate releases with their own delivery.

On install and on every upgrade, the post-install hooks replay the seed (`meta_data/`, `awe_meta_data/`), run the
schema migrations, rebuild the reporting views, sync the ODK geography and the staff access, and run the sanity smoke
tests (`test/sanity`). The seed is written to be replayed: every INSERT has ON CONFLICT.

## Environments

| | Dev (New Dev) | Staging | Production |
| --- | --- | --- | --- |
| Source branch | `develop` | `staging` | not defined yet |
| Pipeline | [`ci/pipelines/dev.groovy`](../ci/pipelines/dev.groovy) | [`ci/pipelines/staging.groovy`](../ci/pipelines/staging.groovy) | not defined yet |
| Namespace, release | `livestock`, `livestock-registry` | `live`, `livestock-registry` | not defined yet |
| Registry UI | `https://livestock-registry.development.oanstaging.com` | `https://livestock-registry.qa.oanstaging.com` | not defined yet |
| Values | oan-helm `environments/dev/values/livestock.yaml` | oan-helm `environments/staging/values/livestock.yaml` | not defined yet |
| Chart installed | the chart the build packaged; [`oan-chart.json`](../ci/deploy/oan-chart.json) for a deploy run by hand | the rc of the chart develop built from the same tree | not defined yet |

### Dev

A develop build validates, builds and pushes the images, packages the chart with them
([`ci/deploy/package-chart.sh`](../ci/deploy/package-chart.sh)) and upgrades the release with that chart
([`ci/deploy/deploy-livestock-dev.sh`](../ci/deploy/deploy-livestock-dev.sh)), which also deploys the dashboard UI. It
then publishes the chart to oan-helm `repository/develop/`. The build has no parameters, so there is no separate
deploy button.

Other actions run from the operator job ([`Jenkinsfile.operator`](../Jenkinsfile.operator)), on `develop` only. A
person starts it, and the Jenkins `admin` user approves each run:

| `OPERATOR_ACTION` | Effect |
| --- | --- |
| `fresh-install` | Archives the registry and ID-generator databases to the New Dev box, uninstalls, drops them and installs again on empty databases ([`ci/deploy/fresh-install-livestock-dev.sh`](../ci/deploy/fresh-install-livestock-dev.sh)). The chart is not published. |
| `connector-plan`, `connector-upgrade` | The connector release only: the plan prints what the upgrade would do; the upgrade archives the connector database first. See [the connector release](../ci/connector/README.md). |

### Staging

A merge into `staging` from `develop` builds nothing. It promotes the chart develop built from the same tree: the same
image digests under an rc version, deployed with oan-helm `scripts/ci/deliver_staging.sh` and the staging values. If
develop never built the tree, the build fails, so staging only runs what New Dev ran first. The connector release
(with the connector images of the same develop build) and the dashboard UI follow in the same build.
`LOAD_SAMPLE_DATA` (off by default) loads the sample records.

### Production

Not defined yet. Open questions, to be decided before this section is written:

- the cluster, namespace and the Commons endpoints production uses;
- the backup method and when it runs;
- the rollback policy (see [release](release.md#rollback)).

## Gates before a deploy

- Every GitHub check of the commit is green ([`ci/deploy/require-green-checks.sh`](../ci/deploy/require-green-checks.sh)).
  This includes `ci/validate.sh`, the native extension tests and the chart lint and render ([CI](../ci/README.md)).
- The rendered release passes the route and Farmer-reference guards (`ci/check-new-dev-routes.py`,
  `ci/refactor/deployment_guard.py`) before Helm runs, and refuses placeholder domains.
- A deploy installs only a chart archive and values checked by SHA-256 against `oan-chart.json`
  (`ci/deploy/oan_chart.py`).

## Rollback and recovery

- Dev: if the upgrade, a rollout, the dashboard UI or the final guard fails, `deploy-livestock-dev.sh` saves the
  diagnostics (`deploy-failure-<build>.txt`) and runs `helm rollback` to the last `deployed` revision
  ([`ci/deploy/release-rollback.sh`](../ci/deploy/release-rollback.sh)), then fails the build. A first install has
  nothing to go back to.
- Staging: if the upgrade fails on a release that had a deployed revision, `deliver_staging.sh` rolls Helm back to
  it, and nothing is published. The connector and dashboard upgrades are `--atomic`.
- A Helm rollback restores the chart and values, not data that hooks or users wrote. Data is restored from a backup.
  On dev, that is the archive `fresh-install` and `connector-upgrade` write before they change a database. Staging
  has no backup step in its pipeline yet.

`ci/pipelines/dev.groovy` still has the stages `Prepare Deploy Values` and `Deploy to Live` for the `staging` branch.
They never run: the `Jenkinsfile` sends `staging` to `staging.groovy`.
