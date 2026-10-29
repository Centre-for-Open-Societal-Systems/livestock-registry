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

Connector definitions, checkpoints and webhook secrets live in the connector database, not here.
The Farmer-reference definition for livestock is documented in
`integrations/farmer-reference/`.
