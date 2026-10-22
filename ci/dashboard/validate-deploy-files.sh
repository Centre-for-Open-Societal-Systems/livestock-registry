#!/usr/bin/env bash
set -euo pipefail
registry=${1:?registry required}
case "$registry" in cropsown|livestock) ;; *) echo 'Unknown registry' >&2; exit 1 ;; esac
for file in "helm/${registry}-registry-dashboard/Chart.yaml" \
  "helm/${registry}-registry-dashboard/values.yaml" \
  "helm/environments/dev/dashboard-ui.yaml" \
  ci/dashboard/deploy-ui.sh; do
  test -s "$file" || { echo "Required dashboard deployment file missing: $file" >&2; exit 1; }
done
for file in _helpers.tpl deployment.yaml iam-setup-job.yaml smoke-job.yaml; do
  test -s "helm/${registry}-registry-dashboard/templates/$file" || {
    echo "Required dashboard template missing: $file" >&2; exit 1;
  }
done
