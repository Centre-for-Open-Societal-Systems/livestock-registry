#!/usr/bin/env bash
# Fail the build if the chart carries a placeholder version or a branch name as
# a version. Both have bitten this project: `0.0.0-develop` makes `helm list`
# useless for telling what is deployed, and a branch name as a version is the
# same class of bug as a branch name as an image tag.
set -euo pipefail
CHART="${1:-helm/openg2p-livestock-registry/Chart.yaml}"
fail() { echo "FATAL: $1 (in $CHART)"; exit 1; }

v=$(awk -F': *' '/^version:/{print $2; exit}' "$CHART" | tr -d '"')
a=$(awk -F': *' '/^appVersion:/{print $2; exit}' "$CHART" | tr -d '"')

[[ "$v" == 0.0.0* ]] && fail "placeholder chart version '$v' - set a real semver"
[[ "$v" =~ ^(develop|main|master|staging)$ ]] && fail "branch name '$v' as chart version"
[[ "$a" =~ ^(develop|main|master|staging)$ ]] && fail "branch name '$a' as appVersion"
[[ -z "$v" || -z "$a" ]] && fail "version or appVersion missing"

echo "chart version '$v', appVersion '$a' - OK"
