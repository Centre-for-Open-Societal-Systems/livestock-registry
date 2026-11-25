# Release

How a Livestock Registry version is numbered, built and promoted. Where each version goes is in
[deployment](deployment.md).

## Versions

| What | Where it is set | Example |
| --- | --- | --- |
| Repository version | `version` in [`init.yaml`](../init.yaml) | `1.0.0` |
| Build version: image tag and chart version | `<version>-<branch>.<BUILD_NUMBER>` ([`ci/image_names.py`](../ci/image_names.py)) | `1.0.0-develop.230` |
| Staging version | the rc of a develop build, added by the staging promotion | |
| OpenG2P platform (`rpVersion`) | `platformVersion` in [`ci/deploy/oan-chart.json`](../ci/deploy/oan-chart.json); copied to `appVersion` and the `openg2p-registry` dependency in `helm/openg2p-livestock-registry/Chart.yaml`, `ARG RP_VERSION` in the platform Dockerfiles, the pipelines and `ci/refactor` | `1.2.2-rc.614` |
| Livestock extension package | `__version__` in `livestock-extension/src/openg2p_registry_livestock_extension/__init__.py` | `1.0.0` |

The six platform images carry `-<rpVersion>` in their repository name, so a platform bump starts new ECR repositories:
`eoan/livestock-registry/staff-api-1.2.2-rc.614:1.0.0-develop.230`. The connector and dashboard images do not. ECR
tags are immutable. The naming follows oan-helm `docs/release/naming-standard.md`, section 6.

`helm/openg2p-livestock-registry/Chart.yaml` keeps `version: 0.0.0`. The build writes the real version into the
archive it packages.

## Release flow

1. **Merge to `develop`.** The build validates, publishes the images and deploys them to New Dev. It then publishes
   the packaged chart to oan-helm `repository/develop/`, where oan-helm's workflow updates the index, changelog and
   rollback history.
2. **Merge `develop` into `staging`.** The staging build promotes the chart develop built from the same tree. It adds
   the rc tag to the same image digests, deploys to staging and publishes the rc chart to `repository/staging/`.
   Nothing is rebuilt.
3. **Production.** Not defined yet ([deployment](deployment.md#production)).

Before step 2, add the changes to [CHANGELOG.md](../CHANGELOG.md) under a heading for the version being promoted.

## Changing the platform version

The platform version is owned centrally: update the chart and the pinned profile
([`ci/deploy/oan-chart.json`](../ci/deploy/oan-chart.json), with [`ci/deploy/bump_pin.py`](../ci/deploy/bump_pin.py))
first. Then run `scripts/bump-rp-version.sh`. It writes that version into every copy in the `Jenkinsfile`,
`ci/pipelines/*.groovy`, `ci/refactor/` (the test image among them) and the platform Dockerfiles, and refuses any
other version. `scripts/bump-rp-version.sh --check` prints the pinned version and changes nothing. Move `appVersion`
and the `openg2p-registry` dependency in `Chart.yaml` with it. These tests fail when the copies disagree:

- `test/test_rp_pin_lockstep.py`: every copy against `oan-chart.json`, and that the bump script moves them all;
- `test/test_image_names.py`: the Dockerfiles against the chart's `appVersion`;
- `test/test_metadata_consistency.py`, which checks the platform's base model columns against the pin.

## Rollback

What the pipelines do today:

- New Dev: a failed upgrade is rolled back to the last deployed Helm revision, and the build fails.
- Staging: a failed upgrade is rolled back to the last deployed Helm revision, and nothing is published.
- A Helm rollback restores the chart and values, not data that hooks or users wrote.
- Data is restored only from a backup. See [rollback and recovery](deployment.md#rollback-and-recovery).

The rollback policy is still to be agreed: when a release is rolled back instead of fixed forward, who decides, and
how a database change is undone.
