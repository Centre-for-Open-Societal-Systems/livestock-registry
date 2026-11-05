#!/usr/bin/env bash
# New Dev only: rebuild the Livestock registry from an empty database.
#
# The standard OpenG2P first install of the pinned chart, done again: the
# release is uninstalled, the registry and ID-generator databases are dropped,
# and ci/deploy/deploy-livestock-dev.sh then installs the chart as it does on a
# first deploy — postgres-init recreates the databases, the applications migrate
# them on start and the post-install seed loads the metadata. Secrets the chart
# marks `resource-policy: keep` (database passwords, Keycloak client secrets,
# the AWE callback HMAC) survive the uninstall, and postgres-init re-syncs the
# database roles to them. Commons, the connector, the Farmer-reference lookup
# Secret and the dashboard releases are not touched.
#
# Every Livestock record, Farmer reference, document and approval on New Dev is
# lost. Both databases are archived to the New Dev box first, over the existing
# backup key, and the archive is checked before anything is removed.
#
# Env: those of deploy-livestock-dev.sh plus BACKUP_SSH_KEY (farmer-new-dev-backup-ssh).
# REGISTRY_DB / IDGEN_DB default to the New Dev release's database names.
set -euo pipefail
set +x
umask 077

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
: "${KUBECONFIG:?Jenkins must bind livestock-dev-kubeconfig}"
: "${BACKUP_SSH_KEY:?Bind farmer-new-dev-backup-ssh}"
: "${IMAGE_TAG:?set IMAGE_TAG}"
DEV_NAMESPACE="${DEV_NAMESPACE:-livestock}"
HELM_RELEASE="${HELM_RELEASE:-livestock-registry}"
test "$DEV_NAMESPACE" = livestock
test "$HELM_RELEASE" = livestock-registry
python3 ci/deploy/oan_chart.py require-deployable registry dev

REGISTRY_DB="${REGISTRY_DB:-livestock_registry}"
IDGEN_DB="${IDGEN_DB:-livestock_registry_idgen}"
BACKUP_HOST=ubuntu@13.201.58.55
BACKUP_DIR=/var/backups/oan/livestock
KNOWN_HOSTS=ci/deploy/new-dev-known-hosts
STAMP=$(date -u +%Y%m%d-%H%M%S)
JOB="livestock-fresh-install-$STAMP"
STATE=$(mktemp -d)
cleanup() {
  kubectl delete job -n "$DEV_NAMESPACE" "$JOB" --ignore-not-found --wait=false > /dev/null 2>&1 || true
  rm -rf "$STATE"
}
trap cleanup EXIT
remote() {
  ssh -i "$BACKUP_SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=yes \
    -o UserKnownHostsFile="$KNOWN_HOSTS" -o ConnectTimeout=15 "$BACKUP_HOST" "$@"
}

# 1. The release must exist and be stable; the Commons PostgreSQL Secret copy in
#    this namespace (what the chart's postgres-init uses) runs the archive.
helm status "$HELM_RELEASE" -n "$DEV_NAMESPACE" > /dev/null
kubectl get secret -n "$DEV_NAMESPACE" commons-postgresql -o name > /dev/null
remote true

# 2. Archive both databases from a Job in the namespace, copy the archive out,
#    check it and ship it to the New Dev box. Nothing is changed yet; a database
#    name that does not exist fails the archive before anything is removed.
kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: $JOB
  namespace: $DEV_NAMESPACE
  labels:
    app.kubernetes.io/name: livestock-fresh-install
spec:
  backoffLimit: 0
  ttlSecondsAfterFinished: 3600
  template:
    metadata:
      labels:
        app.kubernetes.io/name: livestock-fresh-install
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
            - name: REGISTRY_DB
              value: "$REGISTRY_DB"
            - name: IDGEN_DB
              value: "$IDGEN_DB"
          command: ["bash", "-c"]
          args:
            - |
              set -euo pipefail
              cd /tmp
              for db in "\$REGISTRY_DB" "\$IDGEN_DB"; do
                pg_dump -Fc -d "\$db" -f "\$db.dump"
                pg_restore --list "\$db.dump" > /dev/null
              done
              sha256sum ./*.dump > SHA256SUMS
              touch READY
              # Stay up until the archive is copied out and the databases are dropped.
              while [ ! -f DONE ]; do sleep 5; done
EOF
kubectl wait -n "$DEV_NAMESPACE" --for=condition=Ready pod -l "job-name=$JOB" --timeout=300s > /dev/null
POD=$(kubectl get pod -n "$DEV_NAMESPACE" -l "job-name=$JOB" -o name | head -n 1)
POD=${POD#pod/}
test -n "$POD"
for _ in $(seq 1 120); do
  if kubectl exec -n "$DEV_NAMESPACE" "$POD" -- test -f /tmp/READY 2> /dev/null; then break; fi
  if [[ "$(kubectl get pod -n "$DEV_NAMESPACE" "$POD" -o jsonpath='{.status.phase}')" == Failed ]]; then
    echo 'Database archive failed; nothing was changed.' >&2
    exit 1
  fi
  sleep 5
done
kubectl exec -n "$DEV_NAMESPACE" "$POD" -- test -f /tmp/READY
mkdir -p "$STATE/backup"
for name in "$REGISTRY_DB.dump" "$IDGEN_DB.dump" SHA256SUMS; do
  kubectl cp -n "$DEV_NAMESPACE" "$POD:/tmp/$name" "$STATE/backup/$name" > /dev/null
done
(cd "$STATE/backup" && sha256sum -c SHA256SUMS > /dev/null)
remote "sudo -n install -d -m 700 -o root -g root $BACKUP_DIR"
for name in "$REGISTRY_DB.dump" "$IDGEN_DB.dump" SHA256SUMS; do
  expected=$(sha256sum "$STATE/backup/$name" | cut -d ' ' -f 1)
  written=$(remote "sudo -n tee $BACKUP_DIR/$STAMP-$name | sha256sum" < "$STATE/backup/$name" | cut -d ' ' -f 1)
  if [[ "$written" != "$expected" ]]; then
    echo "Archive $name did not arrive intact on the New Dev box; nothing was changed." >&2
    exit 1
  fi
done
echo "Archived $REGISTRY_DB and $IDGEN_DB to $BACKUP_HOST:$BACKUP_DIR/$STAMP-*"

# 3. Remove the release, then the databases. Only now is anything destroyed.
helm uninstall "$HELM_RELEASE" -n "$DEV_NAMESPACE" --wait --timeout 15m
kubectl exec -n "$DEV_NAMESPACE" "$POD" -- psql -X -v ON_ERROR_STOP=1 -d postgres \
  -c "DROP DATABASE IF EXISTS \"$REGISTRY_DB\" WITH (FORCE);" \
  -c "DROP DATABASE IF EXISTS \"$IDGEN_DB\" WITH (FORCE);"
kubectl exec -n "$DEV_NAMESPACE" "$POD" -- touch /tmp/DONE
echo "Dropped $REGISTRY_DB and $IDGEN_DB."

# 4. A first install of the pinned chart through the ordinary deploy: with no
#    release to read values from it installs on the chart's public values and
#    this build's images, and waits for the hooks and rollouts.
bash ci/deploy/deploy-livestock-dev.sh
echo "Installed $HELM_RELEASE into $DEV_NAMESPACE on empty databases; archive: $BACKUP_HOST:$BACKUP_DIR/$STAMP-*"
