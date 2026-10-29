#!/usr/bin/env bash
# Upgrade the New Dev livestock-connector release so that it equals git:
# chart ci/connector/chart, values ci/connector/livestock-connector.values.yaml,
# installed with --reset-values (nothing carried over from earlier hand runs).
#
# Upgrade only. The connector database is archived to the New Dev box first
# (same key and host as fresh-install), then a server-side dry run and the
# rendered manifest diff against the running release are printed, and only then
# is the release upgraded. The registry release (livestock-registry), connector
# definitions, checkpoints and webhook secrets are not touched: they live in the
# connector database, which an upgrade does not migrate away.
#
# After the upgrade it removes, through the connector admin API, the four Crop Sown ODK
# pipelines that the crop connector build seeded into this database (step 6).
#
# PLAN_ONLY=1 (Jenkins connector-plan) stops after step 3: it changes nothing,
# needs no backup key, and prints the manifest diff and the dry-run result.
#
# Env: KUBECONFIG (livestock-dev-kubeconfig), BACKUP_SSH_KEY (farmer-new-dev-backup-ssh,
# not needed with PLAN_ONLY=1).
set -euo pipefail
set +x
umask 077

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
: "${KUBECONFIG:?Jenkins must bind livestock-dev-kubeconfig}"
: "${PLAN_ONLY:=0}"
[[ "$PLAN_ONLY" == 1 ]] || : "${BACKUP_SSH_KEY:?Bind farmer-new-dev-backup-ssh}"
NAMESPACE=livestock
RELEASE=livestock-connector
CHART=ci/connector/chart
VALUES=ci/connector/livestock-connector.values.yaml
CONNECTOR_DB="${CONNECTOR_DB:-livestock_connector_livestock}"
BACKUP_HOST=ubuntu@13.201.58.55
BACKUP_DIR=/var/backups/oan/livestock
KNOWN_HOSTS=ci/deploy/new-dev-known-hosts
STAMP=$(date -u +%Y%m%d-%H%M%S)
JOB="livestock-connector-backup-$STAMP"
STATE=$(mktemp -d)
cleanup() {
  kubectl delete job -n "$NAMESPACE" "$JOB" --ignore-not-found --wait=false > /dev/null 2>&1 || true
  rm -rf "$STATE"
}
trap cleanup EXIT
remote() {
  ssh -i "$BACKUP_SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=yes \
    -o UserKnownHostsFile="$KNOWN_HOSTS" -o ConnectTimeout=15 "$BACKUP_HOST" "$@"
}

# 1. The release must exist, be deployed, and come from the same chart.
# helm list, not helm status: the deploy node's helm prints no chart in status JSON.
status=$(helm list -n "$NAMESPACE" --filter "^${RELEASE}\$" -o json | python3 -c 'import json,sys; r=json.load(sys.stdin); print(" ".join((r[0]["status"], r[0]["chart"])) if r else "missing")')
echo "Current release: $RELEASE ($status)"
test "$status" = "deployed openg2p-connector-0.1.0"
helm history "$RELEASE" -n "$NAMESPACE" --max 5
kubectl get secret -n "$NAMESPACE" commons-postgresql -o name > /dev/null

plan() {
  helm lint "$CHART" -f "$VALUES"
  helm get manifest "$RELEASE" -n "$NAMESPACE" > "$STATE/current.yaml"
  helm template "$RELEASE" "$CHART" -n "$NAMESPACE" -f "$VALUES" > "$STATE/target.yaml"
  echo "=== manifest diff (running release -> git) ==="
  diff -u "$STATE/current.yaml" "$STATE/target.yaml" || true
  echo "=== end of diff ==="
  helm upgrade "$RELEASE" "$CHART" -n "$NAMESPACE" --reset-values -f "$VALUES" --dry-run=server > /dev/null
  echo "Server-side dry run passed."
}
if [[ "$PLAN_ONLY" == 1 ]]; then
  plan
  echo "PLAN_ONLY: nothing was changed."
  exit 0
fi
remote true

# 2. Archive the connector database (definitions, checkpoints, secrets live here).
kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: $JOB
  namespace: $NAMESPACE
  labels:
    app.kubernetes.io/name: livestock-connector-backup
spec:
  backoffLimit: 0
  ttlSecondsAfterFinished: 3600
  template:
    metadata:
      labels:
        app.kubernetes.io/name: livestock-connector-backup
    spec:
      restartPolicy: Never
      containers:
        - name: postgres
          image: docker.io/openg2p/postgresql:16.4.0-debian-12-r14
          env:
            - name: PGHOST
              value: commons-postgresql.commons.svc.cluster.local
            - name: PGUSER
              value: postgres
            - name: PGPASSWORD
              valueFrom:
                secretKeyRef:
                  name: commons-postgresql
                  key: postgres-password
            - name: CONNECTOR_DB
              value: "$CONNECTOR_DB"
          command: ["bash", "-c"]
          args:
            - |
              set -euo pipefail
              cd /tmp
              pg_dump -Fc -d "\$CONNECTOR_DB" -f "\$CONNECTOR_DB.dump"
              pg_restore --list "\$CONNECTOR_DB.dump" > /dev/null
              sha256sum ./*.dump > SHA256SUMS
              touch READY
              while [ ! -f DONE ]; do sleep 5; done
EOF
kubectl wait -n "$NAMESPACE" --for=condition=Ready pod -l "job-name=$JOB" --timeout=300s > /dev/null
POD=$(kubectl get pod -n "$NAMESPACE" -l "job-name=$JOB" -o name | head -n 1)
POD=${POD#pod/}
test -n "$POD"
for _ in $(seq 1 120); do
  if kubectl exec -n "$NAMESPACE" "$POD" -- test -f /tmp/READY 2> /dev/null; then break; fi
  if [[ "$(kubectl get pod -n "$NAMESPACE" "$POD" -o jsonpath='{.status.phase}')" == Failed ]]; then
    echo 'Connector database archive failed; nothing was changed.' >&2
    exit 1
  fi
  sleep 5
done
kubectl exec -n "$NAMESPACE" "$POD" -- test -f /tmp/READY
mkdir -p "$STATE/backup"
for name in "$CONNECTOR_DB.dump" SHA256SUMS; do
  kubectl cp -n "$NAMESPACE" "$POD:/tmp/$name" "$STATE/backup/$name" > /dev/null
done
(cd "$STATE/backup" && sha256sum -c SHA256SUMS > /dev/null)
kubectl exec -n "$NAMESPACE" "$POD" -- touch /tmp/DONE
remote "sudo -n install -d -m 700 -o root -g root $BACKUP_DIR"
for name in "$CONNECTOR_DB.dump" SHA256SUMS; do
  expected=$(sha256sum "$STATE/backup/$name" | cut -d ' ' -f 1)
  written=$(remote "sudo -n tee $BACKUP_DIR/$STAMP-connector-$name | sha256sum" < "$STATE/backup/$name" | cut -d ' ' -f 1)
  if [[ "$written" != "$expected" ]]; then
    echo "Archive $name did not arrive intact on the New Dev box; nothing was changed." >&2
    exit 1
  fi
done
echo "Archived $CONNECTOR_DB to $BACKUP_HOST:$BACKUP_DIR/$STAMP-connector-*"

# 3. Show what changes: rendered manifest diff and a server-side dry run.
plan

# 4. Upgrade.
helm upgrade "$RELEASE" "$CHART" -n "$NAMESPACE" --reset-values -f "$VALUES" --wait --timeout 10m
for d in api worker beat ui; do
  kubectl rollout status -n "$NAMESPACE" "deployment/$RELEASE-$d" --timeout=300s
done

# 5. Verify the running pods equal git and the API answers.
want=$(helm get values "$RELEASE" -n "$NAMESPACE" -o json | python3 -c 'import json,sys; i=json.load(sys.stdin)["api"]["image"]; print(i["repository"]+"@"+i["digest"])')
for d in api worker beat; do
  got=$(kubectl get deployment -n "$NAMESPACE" "$RELEASE-$d" -o jsonpath='{.spec.template.spec.containers[0].image}')
  test "$got" = "$want" || { echo "$RELEASE-$d runs $got, expected $want" >&2; exit 1; }
  names=$(kubectl get deployment -n "$NAMESPACE" "$RELEASE-$d" -o jsonpath='{range .spec.template.spec.containers[0].env[*]}{.name}{"\n"}{end}')
  for n in CONNECTOR_VALIDATE_MAPPED_PAYLOAD CONNECTOR_SIGNING_KID CONNECTOR_SIGNING_KEY_PEM; do
    grep -qx "$n" <<< "$names" || { echo "$RELEASE-$d lacks $n" >&2; exit 1; }
  done
done
API_POD=$(kubectl get pod -n "$NAMESPACE" -l app.kubernetes.io/instance=$RELEASE,app.kubernetes.io/component=api -o name | head -n 1)
kubectl exec -n "$NAMESPACE" "${API_POD#pod/}" -- python -c 'import json,urllib.request; print(json.load(urllib.request.urlopen("http://127.0.0.1:8050/connectors/meta", timeout=10))["webhook_verifiers"])'
kubectl exec -n "$NAMESPACE" "${API_POD#pod/}" -- sh -c 'grep -rl "websub_content_envelope" "$(python -c "import openg2p_connector_service,os; print(os.path.dirname(openg2p_connector_service.__file__))")" | head -3'
# 6. Remove the four Crop Sown ODK pipelines that the crop connector build (develop-116)
# seeded at every start. Only now, with the livestock image running, does a removal last.
# Through the connector's own admin API, by id, and only if the row still carries the
# seeded name; a missing row is already gone.
kubectl exec -i -n "$NAMESPACE" "${API_POD#pod/}" -- python - <<'PY'
import json, urllib.error, urllib.request
BASE = "http://127.0.0.1:8050/connectors/"
SEEDED = ("533b074b13544a8eb0a8fbd10c6f52ed", "24b12b2f3aac4ccdb5b876a604eb54aa",
          "54e73482cf304614a1f3db4982d907c5", "2e6c255ec645430e8f8a8c5d3d94f707")
for cid in SEEDED:
    try:
        row = json.load(urllib.request.urlopen(BASE + cid, timeout=10))
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        print(f"{cid}: already removed")
        continue
    if not str(row.get("name", "")).startswith("Crop Sown"):
        raise SystemExit(f"{cid} is named {row.get('name')!r}, not a seeded Crop Sown pipeline; not removed")
    urllib.request.urlopen(urllib.request.Request(BASE + cid, method="DELETE"), timeout=10)
    print(f"{cid}: removed {row['name']!r}")
rows = json.load(urllib.request.urlopen(BASE.rstrip("/"), timeout=10))
rows = rows if isinstance(rows, list) else rows.get("items") or rows.get("data") or []
left = [c["name"] for c in rows if str(c.get("name", "")).startswith("Crop Sown")]
if left:
    raise SystemExit(f"Crop Sown pipelines still present: {left}")
print("No Crop Sown pipelines in the livestock connector.")
PY
helm history "$RELEASE" -n "$NAMESPACE" --max 3
echo "Upgraded $RELEASE in $NAMESPACE to git (archive: $BACKUP_HOST:$BACKUP_DIR/$STAMP-connector-*)"
