#!/usr/bin/env bash
# Render ci/connector/chart with the livestock-connector values and check what
# the upgrade relies on. Offline; needs helm.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
out=$(mktemp)
trap 'rm -f "$out"' EXIT
helm lint chart -f livestock-connector.values.yaml > /dev/null
helm template livestock-connector chart -n livestock -f livestock-connector.values.yaml > "$out"
digest=sha256:b911446ce1b289faab7280c7cbf51001cd7350117069a28447b786c32c7f3866
test "$(grep -c "image: \"379220350808.dkr.ecr.ap-south-1.amazonaws.com/openg2p/livestock-registry/registry-connector@$digest\"" "$out")" -eq 3
ui_digest=sha256:31d9c997d570da43750e7d0b029a0275d7735ffa8f65248b5de2e5acfb54858a
grep -q "image: \"379220350808.dkr.ecr.ap-south-1.amazonaws.com/openg2p/livestock-registry/registry-connector-ui@$ui_digest\"" "$out"
for name in CONNECTOR_VALIDATE_MAPPED_PAYLOAD CONNECTOR_SIGNING_KID CONNECTOR_SIGNING_KEY_PEM; do
  # api, worker and beat each render it in the container and in the postgres-checker init container.
  test "$(grep -c "name: $name\$" "$out")" -eq 6
done
grep -q 'name: livestock-farmer-lookup-signing-ed25519' "$out"
grep -q -- '- "istio-system/development"' "$out"
grep -q 'connector-livestock-registry.development.oanstaging.com' "$out"
if grep -q 'kind: Job' "$out"; then echo "FAIL: the chart renders a Job" >&2; exit 1; fi
echo "PASS: livestock-connector chart renders the pinned image, signing env and the existing route"
