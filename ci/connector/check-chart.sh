#!/usr/bin/env bash
# Render ci/connector/chart with the livestock-connector values and check what
# the upgrade relies on. Offline; needs helm.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
out=$(mktemp)
trap 'rm -f "$out"' EXIT
helm lint chart -f livestock-connector.values.yaml > /dev/null
helm template livestock-connector chart -n livestock -f livestock-connector.values.yaml > "$out"
digest=sha256:198da6ff46db0c4f8ef20550163de78a4833075dbf08d361c5a2905b6bc8ede6
test "$(grep -c "image: \"379220350808.dkr.ecr.ap-south-1.amazonaws.com/gen2/cropsown-registry/connector-service@$digest\"" "$out")" -eq 3
grep -q 'image: "379220350808.dkr.ecr.ap-south-1.amazonaws.com/openg2p/livestock-registry/connector-ui:live-20260930-0452"' "$out"
for name in CONNECTOR_VALIDATE_MAPPED_PAYLOAD CONNECTOR_SIGNING_KID CONNECTOR_SIGNING_KEY_PEM; do
  # api, worker and beat each render it in the container and in the postgres-checker init container.
  test "$(grep -c "name: $name\$" "$out")" -eq 6
done
grep -q 'name: livestock-farmer-lookup-signing-ed25519' "$out"
grep -q -- '- "istio-system/development"' "$out"
grep -q 'connector-livestock-registry.development.oanstaging.com' "$out"
! grep -q 'kind: Job' "$out"
echo "PASS: livestock-connector chart renders the pinned image, signing env and the existing route"
