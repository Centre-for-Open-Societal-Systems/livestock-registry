# livestock-connector release (New Dev)

The New Dev `livestock-connector` release (namespace `livestock`) is defined here, so the
running release equals git:

| File | What it is |
| --- | --- |
| `chart/` | The `openg2p-connector` 0.1.0 chart, vendored from this repo at `ed9d6db^` (`openg2p-connector-service/deploy/charts/openg2p-connector`, retired by `ed9d6db`), with three OAN additions listed below. `Archive.zip` and the two unused environment values files were left out. |
| `livestock-connector.values.yaml` | The release's user values (revision 3, `helm get values`) plus the Farmer-reference receiver settings. No secret values. |
| `upgrade-livestock-connector.sh` | Plan or upgrade. Jenkins `NEW_DEV_DELIVERY_ACTION=connector-plan` prints the manifest diff and a server-side dry run and changes nothing; `connector-upgrade` archives the connector database to the New Dev box, then runs `helm upgrade --reset-values` and verifies image, env and API. |
| `check-chart.sh` | Offline render check used by CI. |

Additions to the vendored chart:

1. `extraEnv` / `extraEnvFrom` in `templates/_helpers.tpl` and `values.yaml`, taken verbatim from
   this repo's commit `8962ee4` (the ODK branch that never reached develop). The crop connector
   release renders the same keys.
2. `image.digest` per component (`openg2p-connector.image` helper). When set, the image is pulled
   as `repository@digest`.

The connector image is `openg2p/livestock-registry/registry-connector` (built from `docker/registry-connector/`:
OpenG2P's published connector plus the OAN extension for registry-payload signing, the WebSub content
envelope and admin-role access to the API) and `registry-connector-ui` (signs in with the staff token the admin-only API requires). The values pin names develop build 145 (commit `785f58c`,
`sha256:b911446c…`), the first build after the admin-role change; `check-chart.sh` asserts the same digest.
It replaces the stop-gap `connector-service` image (build 116, `sha256:c8edf177…`), which created no crop
pipelines but had no admin-role check. Plan W21 moves the connector into the `registryConnector` subchart of
the openg2p-registry chart (rc.601+).

Connector definitions are declared in git and applied by Helm
-------------------------------------------------------------

The rows of `connector_definitions` are declared in `definitions.newdev.yaml` (New Dev) and
`definitions.staging.yaml` (staging), under `connectorDefinitions`. The chart's post-install and
post-upgrade hook Job (`chart/templates/definitions-job.yaml`, script `chart/files/apply_definitions.py`)
calls the connector's own admin API on every deploy: it creates a missing definition, PATCHes an existing
one (matched by name, then `previous_names`, then slug) to the declared state, and for WebSub receivers
calls `POST /connectors/{id}/websub/sync-subscriptions` (register topic, subscribe callback with the hub
secret). The API does none of that by itself: creating a row neither subscribes nor validates, and a row
inserted with SQL is never subscribed, so the subscription call is part of the apply. Checkpoints
(`poll_state_json`) are not touched.

Secrets are never in values. `webhook_secret_from` / `auth_secret_from` name Kubernetes Secrets that the Job
reads through `secretKeyRef`; with `generate: true` the chart creates the Secret once (random, kept on
uninstall, never rotated) if it does not exist. A declared secret that is empty never overwrites a stored one.
The Keycloak client secret for the admin token is read at run time from `commons/registry-connector` by the
Job's ServiceAccount; apply `ci/k8s/connector-definitions-rbac.yaml` once as cluster admin.
`retired:` lists rows to delete. Unit tests: `python -m unittest discover ci/connector/tests`.

Checkpoints and the ODK credentials already stored in the connector database are kept until the declared Secrets exist.
The Farmer-reference definition for livestock is documented in
`integrations/farmer-reference/`.
