#!/usr/bin/env bash
# Render ci/connector/chart with the livestock-connector values and check what
# the upgrade relies on. Offline; needs helm.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
out=$(mktemp)
base=$(mktemp)
trap 'rm -f "$out" "$base"' EXIT
helm lint chart -f livestock-connector.values.yaml > /dev/null
helm template livestock-connector chart -n livestock -f livestock-connector.values.yaml > "$base"
helm lint chart -f livestock-connector.values.yaml -f definitions.newdev.yaml > /dev/null
helm template livestock-connector chart -n livestock -f livestock-connector.values.yaml -f definitions.newdev.yaml > "$out"
digest=sha256:138d7ec301963da9b75cd4111ec2a8f393f56a44165580f4ba38ddcf05fc3236
test "$(grep -c "image: \"379220350808.dkr.ecr.ap-south-1.amazonaws.com/openg2p/livestock-registry/registry-connector@$digest\"" "$out")" -eq 4  # api, worker, beat and the definitions Job
ui_digest=sha256:9b49598c2f02c01a967cb5b2ec2be4ff43048261bf8de26b21f05439613b1fb0
grep -q "image: \"379220350808.dkr.ecr.ap-south-1.amazonaws.com/openg2p/livestock-registry/registry-connector-ui@$ui_digest\"" "$out"
for name in CONNECTOR_VALIDATE_MAPPED_PAYLOAD CONNECTOR_SIGNING_KID CONNECTOR_SIGNING_KEY_PEM; do
  # api, worker and beat each render it in the container and in the postgres-checker init container.
  test "$(grep -c "name: $name\$" "$out")" -eq 6
done
grep -q 'name: livestock-farmer-lookup-signing-ed25519' "$out"
grep -q -- '- "istio-system/development"' "$out"
grep -q 'connector-livestock-registry.development.oanstaging.com' "$out"
# Without definitions the chart renders no Job; with them, exactly the post-upgrade definitions hook.
if grep -q 'kind: Job' "$base"; then echo "FAIL: the chart renders a Job without definitions" >&2; exit 1; fi
test "$(grep -c 'kind: Job' "$out")" -eq 1
grep -q 'helm.sh/hook: post-install,post-upgrade' "$out"
grep -q 'name: livestock-connector-definitions$' "$out"
grep -q 'name: CD_0_WEBHOOK_SECRET$' "$out"
grep -q 'farmer-registry.farmer-profile.changed.v1' "$out"
helm lint chart -f livestock-connector.values.yaml -f definitions.staging.yaml > /dev/null
# Staging: the release values plus the digests the staging pipeline writes (any digests here).
staging=$(mktemp)
trap 'rm -f "$out" "$base" "$staging"' EXIT
sd=sha256:$(printf 'a%.0s' $(seq 1 64))
sui=sha256:$(printf 'b%.0s' $(seq 1 64))
repo=379220350808.dkr.ecr.ap-south-1.amazonaws.com/openg2p/livestock-registry
override='{"api":{"image":{"repository":"'$repo'/registry-connector","tag":"t","digest":"'$sd'"}},"worker":{"image":{"repository":"'$repo'/registry-connector","tag":"t","digest":"'$sd'"}},"beat":{"image":{"repository":"'$repo'/registry-connector","tag":"t","digest":"'$sd'"}},"ui":{"image":{"repository":"'$repo'/registry-connector-ui","tag":"t","digest":"'$sui'"}}}'
echo "$override" > "$staging.json"
helm lint chart -f livestock-connector.staging.values.yaml -f "$staging.json" -f definitions.staging.yaml > /dev/null
helm template livestock-connector chart -n live -f livestock-connector.staging.values.yaml -f "$staging.json" -f definitions.staging.yaml > "$staging"
rm -f "$staging.json"
test "$(grep -c "image: \"$repo/registry-connector@$sd\"" "$staging")" -eq 4  # api, worker, beat and the definitions Job
grep -q "image: \"$repo/registry-connector-ui@$sui\"" "$staging"
if grep -q 'connector-service\|postgres-init:develop' "$staging"; then echo "FAIL: staging renders a retired image or the database init Job" >&2; exit 1; fi
test "$(grep -c 'kind: Job' "$staging")" -eq 1
grep -q 'name: livestock-connector-postgres-init$' "$staging" && { echo "FAIL: staging renders the postgres-init ServiceAccount" >&2; exit 1; }
grep -q 'name: livestock-farmer-lookup-signing-ed25519' "$staging"
grep -q 'connector-livestock.oanstaging.com' "$staging"
grep -q 'livestock_connector_live' "$staging"
# The API must expect the issuer of the tokens the definitions hook fetches (tokenUrl in
# definitions.staging.yaml), not the New Dev issuer baked into the image.
token_url=$(sed -n 's/^ *tokenUrl: *//p' definitions.staging.yaml)
issuer=${token_url%/protocol/openid-connect/token}
test -n "$issuer"
test "$(grep -A1 'name: CONNECTOR_ADMIN_AUTH_ISSUER$' "$staging" | grep -c "value: \"$issuer\"")" -ge 3 || { echo "FAIL: staging API does not expect issuer $issuer" >&2; exit 1; }
echo "PASS: livestock-connector chart renders the pinned image, signing env, the existing route and the definitions hook"
