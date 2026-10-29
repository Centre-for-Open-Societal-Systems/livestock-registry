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

The connector service image is pinned to the crop build of the vendored connector at
cropsown-regsitry `d0cd4f9`, which carries the Farmer-reference receiver changes (WebSub content
envelope, Ed25519 registry-payload signing, mapped-payload validation). That build also creates crop's four ODK
pipelines in any connector database it starts against (`default_pipelines.py`, run at every API start),
which put four failing "Crop Sown" connectors into the livestock connector database on 29 Oct.
`docker/connector-service/` is the livestock-owned image: the same pinned build with that module replaced
by one that creates nothing. Jenkins builds it with the other images (`openg2p/livestock-registry/connector-service`);
the values pin moves to it, and the four rows are removed, in the next connector-upgrade. Moving connector
releases into oan-helm, built from OpenG2P/registry-connector, replaces both later.

Connector definitions, checkpoints and webhook secrets live in the connector database, not here.
The Farmer-reference definition for livestock is documented in
`integrations/farmer-reference/`.
