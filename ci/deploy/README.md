# Immutable central chart consumer

Install the deploy-agent dependency with `python3 -m pip install -r ci/deploy/requirements.txt`.
The registry-owned Jenkins job and agent/credential IDs are unchanged.

`oan-chart.json` records the COSS oan-helm commit, chart version, SHA-256, native
platform version, public-values checksum, release and environment. CI downloads
and validates the archive before Helm uses it. There is no local Helm source,
dependency update, moving branch URL or chart-version stamping.

Read-only verification: `python3 ci/deploy/oan_chart.py fetch registry <directory>`
and `python3 ci/deploy/oan_chart.py values registry <public-values.yaml>`.
Unit checks: `python3 -m unittest discover -s test -p test_oan_chart.py` and
`python3 -m unittest discover -s test -p test_deployment_guard.py`.

All deployment entry points call require-deployable first: a profile deploys only
when `promotionReady` is true for its environment (the dev profile is). Accept
domain/source/Kafka/AWE/MDM and preservation behavior before marking a new
immutable release/profile promotion-ready.
Staging requires its own environment profile and restored-data rehearsal; it
must not use the dev public-values overlay as a fallback.

Live metadata is read only by ci/refactor/new_dev_metadata.py with an explicit
authorized --credentials path. It never captures registry records or submits
approval actions. Credentials/cookies remain in memory, and metadata snapshots
remove credential values. Rehearse/compare scripts run serially using disposable
test databases; they do not bypass the real seed promotion preflight.

Crop's build agent runs `prefetch registry` and `prefetch dashboard` before
stashing `.central-charts/**`. Archives and public values are cached by SHA-256;
the VPN deploy node rechecks the exact package and values without GitHub access.
A corrupt cached archive fails closed and does not trigger a network fallback.
Manual runs can prefetch on a connected machine and carry that directory with
the same immutable profile. Cached archives are not editable Helm sources.

## Deploy, rollback and pin updates (New Dev)

Every `develop` build builds and pushes the images and then runs
`ci/deploy/deploy-livestock-dev.sh` (no parameter to tick; the `NEW_DEV_DELIVERY_ACTION`
choice only carries the deliberate maintenance runs `fresh-install`, `connector-plan`
and `connector-upgrade`). The script records the last `deployed` Helm revision, upgrades
the release with the pinned chart and public values and this build's image tags, waits
for the rollouts and runs the guards. If anything fails from the upgrade onwards it saves
`deploy-failure-<build>.txt` (pods, events, hook and application logs; archived by the
build), runs `helm rollback` to that revision (`ci/deploy/release-rollback.sh`) and fails
the build. A first install has nothing to go back to. A rollback restores the chart and
values; it does not undo database changes made by hooks. There is no `--atomic`, so the
evidence survives. A release left in a `pending-*` Helm state is refused before any change.

The last stage, "Propose chart pin update", compares the pin with the head of oan-helm
`main` (`python3 ci/deploy/propose_pin_pr.py`). If the Livestock chart is newer, or its
public values changed, it opens a pull request to `develop` that rewrites only the
`registry` pin in `oan-chart.json`: the oan-helm commit, version, archive SHA-256,
public-values SHA-256 and platform version. It never deploys and never changes `develop`;
a person reviews and merges it, and the next `develop` build deploys the new pin. The stage
needs a GitHub credential (`oan-ci-app`) with Contents and Pull requests write; without it
the stage is UNSTABLE and the build still passes. It refuses a downgrade and a changed
archive for the same version, and does not propose a chart that needs another platform
version: the Dockerfiles and the pipeline have to move with it (run
`scripts/bump-rp-version.sh`, move `RP_VERSION` and the `openg2p/openg2p-registry-*` tags in
`ci/pipelines/dev.groovy` and `ci/refactor`, then
`python3 ci/deploy/bump_pin.py <oan-helm commit> --write`). The `dashboard` pin is separate
and is not touched.

Checks without a cluster or network:
`python3 -m unittest discover -s test -p test_deploy_ci.py -v`.
