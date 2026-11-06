#!/usr/bin/env bash
# Upgrade the staging livestock-connector release (namespace live) to the OAN registry-connector images that
# were built from the same develop build as the registry just promoted. Run by ci/pipelines/staging.groovy
# right after scripts/ci/deliver_staging.sh of oan-helm promoted and deployed the registry; it takes no parameters.
#
# Which image: the promoted chart (built-chart/*.tgz) pins the staff-api image by digest. ECR lists the build
# tag of that digest (the 12-character commit); the connector and connector UI images carry the same tag, because one
# develop build pushes all of them. Their digests are resolved from ECR and the release is pinned to the digests.
# Nothing is built or tagged here, and no tag is guessed: if the build has no connector image the run fails
# before the cluster is touched.
#
# Values: ci/connector/livestock-connector.staging.values.yaml (release values, no secret values), the image
# override written below, and ci/connector/definitions.staging.yaml; --reset-values, so nothing saved in the
# release can override git. The rendered manifest diff against the running release is printed first, then
# a server-side dry run; the upgrade is `helm upgrade --atomic`, so a failed rollout or a failed definitions
# hook Job restores the previous revision (chart and values only: a database change made by the connector
# or the hook is not undone).
#
# Prerequisites on the cluster, checked here before anything changes: Secrets live/livestock-connector,
# live/livestock-farmer-lookup-signing-ed25519, live/ecr-pull-secret, live/commons-postgresql and commons/registry-connector. The hook's ServiceAccount
# also needs get on commons/registry-connector (Role connector-definitions-read-client-secret,
# ci/k8s/connector-definitions-rbac.yaml); without it the hook fails and --atomic rolls back.
#
# Env: KUBECONFIG and AWS credentials (set by the pipeline); PROMOTED_CHART (default: the one archive in
# built-chart/); PLAN_ONLY=1 stops after the diff and the dry run.
set -euo pipefail
set +x
umask 077

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
: "${KUBECONFIG:?The pipeline must bind staging-rke2-kubeconfig}"
: "${AWS_REGION:=ap-south-1}"
: "${PLAN_ONLY:=0}"
NAMESPACE=live
RELEASE=livestock-connector
CHART=ci/connector/chart
VALUES=ci/connector/livestock-connector.staging.values.yaml
DEFINITIONS=ci/connector/definitions.staging.yaml
BUILD_TAG_PATTERN='^[0-9a-f]{12}$'
PROMOTED_CHART="${PROMOTED_CHART:-$(ls built-chart/*.tgz 2> /dev/null | head -n 1)}"
test -f "${PROMOTED_CHART:-}" || { echo "No promoted chart archive (built-chart/*.tgz): the registry promotion must run first." >&2; exit 1; }
STATE=$(mktemp -d)
trap 'rm -rf "$STATE"' EXIT

# 1. The release must exist, be deployed, and come from the same chart.
status=$(helm list -n "$NAMESPACE" --filter "^${RELEASE}\$" -o json | python3 -c 'import json,sys; r=json.load(sys.stdin); print(" ".join((r[0]["status"], r[0]["chart"])) if r else "missing")')
echo "Current release: $RELEASE ($status)"
test "$status" = "deployed openg2p-connector-0.1.0"
helm history "$RELEASE" -n "$NAMESPACE" --max 5
for secret in "$NAMESPACE/livestock-connector" "$NAMESPACE/livestock-farmer-lookup-signing-ed25519" "$NAMESPACE/ecr-pull-secret" "$NAMESPACE/commons-postgresql" "commons/registry-connector"; do
  kubectl get secret -n "${secret%%/*}" "${secret#*/}" -o name > /dev/null || { echo "Secret $secret is missing." >&2; exit 1; }
done

# 2. The connector image of the build that was promoted.
read -r SERVICE_REPOSITORY SERVICE_DIGEST < <(python3 - "$PROMOTED_CHART" <<'PY'
import re, sys, tarfile
with tarfile.open(sys.argv[1]) as bundle:
    member = next(m for m in bundle.getmembers() if m.name.count("/") == 1 and m.name.endswith("/values.yaml"))
    values = bundle.extractfile(member).read().decode("utf-8")
repository = None
for line in values.splitlines():
    found = re.match(r"""^\s*repository:\s*["']?(\S+?/staff-api)["']?\s*$""", line)
    if found:
        repository = found.group(1)
        continue
    found = re.match(r"""^\s*tag:\s*["']?[^"'@\s]+@(sha256:[0-9a-f]{64})["']?\s*$""", line)
    if found and repository:
        print(repository, found.group(1))
        break
else:
    sys.exit("the promoted chart pins no staff-api image by digest")
PY
)
IMAGE_PREFIX=${SERVICE_REPOSITORY%/staff-api}
ECR_BASE=${IMAGE_PREFIX#*/}
CONNECTOR_IMAGE_REPOSITORY="$IMAGE_PREFIX/registry-connector"
CONNECTOR_UI_IMAGE_REPOSITORY="$IMAGE_PREFIX/registry-connector-ui"
ecr_digest() {
  aws ecr describe-images --region "$AWS_REGION" --repository-name "$1" --image-ids "imageTag=$2" \
    --query 'imageDetails[0].imageDigest' --output text 2> /dev/null || true
}
build_tags=$(aws ecr describe-images --region "$AWS_REGION" --repository-name "$ECR_BASE/staff-api" \
  --image-ids "imageDigest=$SERVICE_DIGEST" --query 'imageDetails[0].imageTags[]' --output text | tr '\t' '\n' \
  | grep -E "$BUILD_TAG_PATTERN" | sort || true)
test -n "$build_tags" || { echo "staff-api $SERVICE_DIGEST has no build tag matching $BUILD_TAG_PATTERN in ECR." >&2; exit 1; }
CONNECTOR_IMAGE_DIGEST=""
for tag in $build_tags; do
  CONNECTOR_IMAGE_DIGEST=$(ecr_digest "$ECR_BASE/registry-connector" "$tag")
  CONNECTOR_UI_IMAGE_DIGEST=$(ecr_digest "$ECR_BASE/registry-connector-ui" "$tag")
  if [[ "$CONNECTOR_IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ && "$CONNECTOR_UI_IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]; then
    BUILD_TAG=$tag
    break
  fi
  CONNECTOR_IMAGE_DIGEST=""
done
test -n "$CONNECTOR_IMAGE_DIGEST" || { echo "No registry-connector and registry-connector-ui image carries a build tag of the promoted staff-api ($build_tags)." >&2; exit 1; }
echo "Promoted staff-api $SERVICE_DIGEST is build $BUILD_TAG"
echo "api, worker, beat: $CONNECTOR_IMAGE_REPOSITORY@$CONNECTOR_IMAGE_DIGEST"
echo "ui: $CONNECTOR_UI_IMAGE_REPOSITORY@$CONNECTOR_UI_IMAGE_DIGEST"

python3 - "$STATE/override.values.json" "$CONNECTOR_IMAGE_REPOSITORY" "$CONNECTOR_IMAGE_DIGEST" "$CONNECTOR_UI_IMAGE_REPOSITORY" "$CONNECTOR_UI_IMAGE_DIGEST" "$BUILD_TAG" <<'PY'
import json, sys
path, repository, digest, ui_repository, ui_digest, tag = sys.argv[1:7]
override = {name: {"image": {"repository": repository, "tag": tag, "digest": digest}} for name in ("api", "worker", "beat")}
override["ui"] = {"image": {"repository": ui_repository, "tag": tag, "digest": ui_digest}}
json.dump(override, open(path, "w"), indent=2)
PY

# 3. Show what changes, then rehearse it on the server.
helm lint "$CHART" -f "$VALUES" -f "$STATE/override.values.json" -f "$DEFINITIONS"
helm get manifest "$RELEASE" -n "$NAMESPACE" > "$STATE/current.yaml"
helm template "$RELEASE" "$CHART" -n "$NAMESPACE" -f "$VALUES" -f "$STATE/override.values.json" -f "$DEFINITIONS" > "$STATE/target.yaml"
echo "=== manifest diff (running release -> git chart + values + image build $BUILD_TAG) ==="
diff -u "$STATE/current.yaml" "$STATE/target.yaml" || true
echo "=== end of diff ==="
helm upgrade "$RELEASE" "$CHART" -n "$NAMESPACE" --reset-values -f "$VALUES" -f "$STATE/override.values.json" -f "$DEFINITIONS" --dry-run=server > /dev/null
echo "Server-side dry run passed."
if [[ "$PLAN_ONLY" == 1 ]]; then
  echo "PLAN_ONLY: nothing was changed."
  exit 0
fi

# 4. Upgrade. --atomic restores the previous revision if the rollout or the definitions hook fails.
helm upgrade "$RELEASE" "$CHART" -n "$NAMESPACE" --reset-values -f "$VALUES" -f "$STATE/override.values.json" -f "$DEFINITIONS" \
  --atomic --wait --timeout 10m
for d in api worker beat ui; do
  kubectl rollout status -n "$NAMESPACE" "deployment/$RELEASE-$d" --timeout=300s
done

# 5. The running pods equal git, and the API is admin-only.
for d in api worker beat; do
  got=$(kubectl get deployment -n "$NAMESPACE" "$RELEASE-$d" -o jsonpath='{.spec.template.spec.containers[0].image}')
  test "$got" = "$CONNECTOR_IMAGE_REPOSITORY@$CONNECTOR_IMAGE_DIGEST" || { echo "$RELEASE-$d runs $got" >&2; exit 1; }
done
got=$(kubectl get deployment -n "$NAMESPACE" "$RELEASE-ui" -o jsonpath='{.spec.template.spec.containers[0].image}')
test "$got" = "$CONNECTOR_UI_IMAGE_REPOSITORY@$CONNECTOR_UI_IMAGE_DIGEST" || { echo "$RELEASE-ui runs $got" >&2; exit 1; }
API_POD=$(kubectl get pod -n "$NAMESPACE" -l "app.kubernetes.io/instance=$RELEASE,app.kubernetes.io/component=api" -o name | head -n 1)
kubectl exec -n "$NAMESPACE" "${API_POD#pod/}" -- python -c '
import urllib.error, urllib.request
try:
    urllib.request.urlopen("http://127.0.0.1:8050/connectors/meta", timeout=10)
except urllib.error.HTTPError as e:
    if e.code not in (401, 403):
        raise SystemExit("Unauthenticated GET /connectors/meta answered HTTP %s, expected 401 or 403" % e.code)
    print("Unauthenticated GET /connectors/meta refused with HTTP %s" % e.code)
else:
    raise SystemExit("Unauthenticated GET /connectors/meta succeeded: the connector API is NOT admin-only")
'
helm history "$RELEASE" -n "$NAMESPACE" --max 3
echo "Upgraded $RELEASE in $NAMESPACE to build $BUILD_TAG"
