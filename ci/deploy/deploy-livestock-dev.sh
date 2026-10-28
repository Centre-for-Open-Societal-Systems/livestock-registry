#!/usr/bin/env bash
# Deploy a Livestock Registry build from ECR into New Dev (release
# livestock-registry, namespace livestock): the body of the Jenkins "Deploy to
# Development" stage, so the same deploy can be run by hand with the same
# credentials.
#
#   1. Verify the exact central chart archive and its public values
#      (ci/deploy/oan-chart.json; the pin must be promotion-ready).
#   2. Read the live release's values (hostnames, Keycloak/IAM wiring set on the
#      release) when a release exists; a first install goes ahead without them.
#   3. Render with this build's images, refuse placeholder domains, and run the
#      route and Farmer-reference guards on the rendered workloads.
#   4. helm upgrade --install, wait for the rollouts, deploy the dashboard UI and
#      run the Farmer-reference guard against the live Deployments.
#
# Env (Jenkins supplies them):
#   KUBECONFIG        livestock-dev-kubeconfig
#   DEV_NAMESPACE     default livestock
#   HELM_RELEASE      default livestock-registry
#   ECR_REGISTRY      <account>.dkr.ecr.<region>.amazonaws.com
#   ECR_PATH          default openg2p/livestock-registry
#   IMAGE_TAG         this build's image tag
#   DASHBOARD_UI_ECR, DASHBOARD_UI_SHA  dashboard UI image (ci/dashboard/deploy-ui.sh)
#   BUILD_NUMBER      names the archived rendered manifests
set -euo pipefail
set +x

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
: "${KUBECONFIG:?Jenkins must bind livestock-dev-kubeconfig}"
: "${ECR_REGISTRY:?set ECR_REGISTRY}"
: "${IMAGE_TAG:?set IMAGE_TAG}"
DEV_NAMESPACE="${DEV_NAMESPACE:-livestock}"
HELM_RELEASE="${HELM_RELEASE:-livestock-registry}"
ECR_PATH="${ECR_PATH:-openg2p/livestock-registry}"
BUILD_NUMBER="${BUILD_NUMBER:-local}"

# The deploy node's host Python has no PyYAML (build 121: "Install
# ci/deploy/requirements.txt before chart verification"). Verify the chart in a
# small image built on the node from ci/deploy/chart-tool (python:3.12-slim plus
# ci/deploy/requirements.txt, as Farmer's ci/validation does) instead of pulling
# the registry image over the VPN link, offline, with the repo and the work
# directory mounted at their host paths so printed paths stay valid. Helm and
# kubectl stay on the host, which keeps the cluster access.
CHART_TOOL_IMAGE="${CHART_TOOL_IMAGE:-}"
chart_tool() {
  if python3 -c 'import yaml' 2>/dev/null; then
    python3 ci/deploy/oan_chart.py "$@"
    return
  fi
  if [ -z "$CHART_TOOL_IMAGE" ]; then
    CHART_TOOL_IMAGE="coss-ci/chart-tool:$(sha256sum ci/deploy/requirements.txt ci/deploy/chart-tool/Dockerfile | sha256sum | cut -c1-12)"
    docker image inspect "$CHART_TOOL_IMAGE" >/dev/null 2>&1 || docker build -q -t "$CHART_TOOL_IMAGE" -f ci/deploy/chart-tool/Dockerfile ci/deploy >/dev/null
  fi
  local mounts=(-v "$PWD:/work")
  [ -z "${WORK:-}" ] || mounts+=(-v "$WORK:$WORK")
  docker run --rm --network none --user "$(id -u):$(id -g)" --entrypoint python \
    "${mounts[@]}" -w /work "$CHART_TOOL_IMAGE" ci/deploy/oan_chart.py "$@"
}
chart_tool require-deployable registry dev
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
CHART=$(chart_tool fetch registry "$WORK/chart")
CENTRAL_VALUES=$(chart_tool values registry "$WORK/public-values.yaml")
umask 077
# The live release's values. Only a missing release (a first install) may go
# ahead without them.
if ! helm get values "$HELM_RELEASE" -n "$DEV_NAMESPACE" --all -o yaml > "$WORK/current-values.yaml" 2> "$WORK/current.err"; then
  grep -q "release: not found" "$WORK/current.err" || { cat "$WORK/current.err" >&2; exit 1; }
  echo "No release $HELM_RELEASE in $DEV_NAMESPACE yet: installing on the chart's public values."
  : > "$WORK/current-values.yaml"
fi

IMAGE_SET_FLAGS=(
  --set "registry.staffApi.image.repository=${ECR_REGISTRY}/${ECR_PATH}/staff-api"
  --set "registry.staffApi.image.tag=${IMAGE_TAG}"
  --set "registry.partnerApi.image.repository=${ECR_REGISTRY}/${ECR_PATH}/partner-api"
  --set "registry.partnerApi.image.tag=${IMAGE_TAG}"
  --set "registry.celeryWorker.image.repository=${ECR_REGISTRY}/${ECR_PATH}/celery"
  --set "registry.celeryWorker.image.tag=${IMAGE_TAG}"
  --set "registry.celeryBeat.image.repository=${ECR_REGISTRY}/${ECR_PATH}/celery"
  --set "registry.celeryBeat.image.tag=${IMAGE_TAG}"
  --set "registry.dbSeed.image.repository=${ECR_REGISTRY}/${ECR_PATH}/db-seed"
  --set "registry.dbSeed.image.tag=${IMAGE_TAG}"
  --set "registry.staffUi.image.repository=${ECR_REGISTRY}/${ECR_PATH}/staff-ui"
  --set "registry.staffUi.image.tag=${IMAGE_TAG}"
  --set "registry.sanity.image.repository=${ECR_REGISTRY}/${ECR_PATH}/sanity-tests"
  --set "registry.sanity.image.tag=${IMAGE_TAG}"
  --set dashboardApi.enabled=true
  --set "dashboardApi.image.repository=${ECR_REGISTRY}/${ECR_PATH}/dashboard-api"
  --set "dashboardApi.image.tag=${IMAGE_TAG}"
  --set reporting.views.enabled=true
)

helm template "$HELM_RELEASE" "$CHART" -n "$DEV_NAMESPACE" \
  -f "$WORK/current-values.yaml" -f "$CENTRAL_VALUES" "${IMAGE_SET_FLAGS[@]}" \
  > "newdev-rendered-${BUILD_NUMBER}.yaml"
if grep -q 'openg2p\.org' "newdev-rendered-${BUILD_NUMBER}.yaml"; then
  echo "FATAL: rendered manifests still reference the placeholder domain openg2p.org:" >&2
  grep -n 'openg2p\.org' "newdev-rendered-${BUILD_NUMBER}.yaml" | head -20 >&2
  exit 1
fi
# Convert once and check each guard's exit status before Helm changes the
# release. Neither guard prints rendered Secrets or private key material.
kubectl create --dry-run=client --validate=false -n "$DEV_NAMESPACE" \
  -f "newdev-rendered-${BUILD_NUMBER}.yaml" -o json > "newdev-rendered-${BUILD_NUMBER}.json"
python3 ci/check-new-dev-routes.py livestock --release "$HELM_RELEASE" --namespace "$DEV_NAMESPACE" \
  < "newdev-rendered-${BUILD_NUMBER}.json"
python3 ci/refactor/deployment_guard.py --release "$HELM_RELEASE" --namespace "$DEV_NAMESPACE" --check-live-secret \
  < "newdev-rendered-${BUILD_NUMBER}.json"

helm upgrade --install "$HELM_RELEASE" "$CHART" -n "$DEV_NAMESPACE" \
  -f "$WORK/current-values.yaml" -f "$CENTRAL_VALUES" "${IMAGE_SET_FLAGS[@]}" \
  --cleanup-on-fail --timeout 15m

kubectl rollout status "deployment/$HELM_RELEASE-dashboard-api" -n "$DEV_NAMESPACE" --timeout=420s
if [ -n "${DASHBOARD_UI_SHA:-}" ]; then
  bash ci/dashboard/deploy-ui.sh livestock "$DEV_NAMESPACE" "${ECR_REGISTRY}/${DASHBOARD_UI_ECR:?set DASHBOARD_UI_ECR}" "$DASHBOARD_UI_SHA"
fi
for component in staff-portal-api staff-portal-ui partner-api celery-worker celery-beat-producer; do
  kubectl rollout status "deployment/$HELM_RELEASE-$component" -n "$DEV_NAMESPACE" --timeout=180s
done
kubectl get deployment "$HELM_RELEASE-staff-portal-api" "$HELM_RELEASE-celery-worker" "$HELM_RELEASE-celery-beat-producer" \
  -n "$DEV_NAMESPACE" -o json > "newdev-live-staff-api-${BUILD_NUMBER}.json"
python3 ci/refactor/deployment_guard.py --release "$HELM_RELEASE" --namespace "$DEV_NAMESPACE" --check-live-secret \
  < "newdev-live-staff-api-${BUILD_NUMBER}.json"
echo "Deployed $HELM_RELEASE ($IMAGE_TAG) to $DEV_NAMESPACE."
