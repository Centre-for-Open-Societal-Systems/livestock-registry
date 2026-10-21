#!/usr/bin/env bash
set -euo pipefail
registry=$1
namespace=$2
image=$3
tag=$4
case "$registry" in cropsown|livestock) ;; *) echo 'Unknown registry' >&2; exit 1 ;; esac
test -n "$tag"
chart="helm/${registry}-registry-dashboard"
release="${registry}-registry-dashboard"
values="helm/environments/dev/dashboard-ui.yaml"
helm lint "$chart" -f "$values" --set-string "image.repository=$image" --set-string "image.tag=$tag"
helm template "$release" "$chart" -n "$namespace" -f "$values" \
  --set-string "image.repository=$image" --set-string "image.tag=$tag" > /dev/null
helm upgrade --install "$release" "$chart" -n "$namespace" -f "$values" \
  --set-string "image.repository=$image" --set-string "image.tag=$tag" \
  --wait --wait-for-jobs --timeout 15m
