#!/usr/bin/env bash
# gen2-runbook/configure.sh - applies the environment-level configuration that
# CANNOT live in this repo's helm values, because it belongs to workloads the
# commons-services release owns.
#
#   ./configure.sh -n live -r livestock-registry -K keycloak-livestock-development.oanstaging.com
#   ./configure.sh -n live -r livestock-registry -K ... --apply
#
# Dry-run unless --apply is given. Every action is idempotent: re-running after a
# commons-services upgrade is the intended way to restore these.
set -uo pipefail
export KUBECONFIG=${KUBECONFIG:-/etc/rancher/rke2/rke2.yaml}

NS=live REL=livestock-registry KC_PUB="" APPLY=0
while [ $# -gt 0 ]; do case $1 in
  -n) NS=$2; shift 2 ;; -r) REL=$2; shift 2 ;; -K) KC_PUB=$2; shift 2 ;;
  --apply) APPLY=1; shift ;; *) echo "unknown arg $1"; exit 2 ;;
esac; done
[ -n "$KC_PUB" ] || { echo "-K <public keycloak host> is required"; exit 2; }

k() { if [ "$(id -u)" = 0 ]; then kubectl -n "$NS" "$@"; else sudo -E kubectl -n "$NS" "$@"; fi; }
DB=$(printf '%s' "$REL" | tr '-' '_')
run() { if [ "$APPLY" = 1 ]; then "$@"; else echo "      would run: $*"; fi; }
step() { printf '\n\033[1m%s\033[0m\n' "$1"; }
[ "$APPLY" = 1 ] || echo "DRY RUN - nothing will change. Add --apply to act."

# --------------------------------------------------------------------------- 1
step "1. pg_trgm in $DB"
# Extensions are PER-DATABASE and CREATE DATABASE does not carry them over. The
# registry builds a GIN trigram index on search_text; without pg_trgm the
# startup migration aborts at that index leaving a part-built schema (~27 of 93
# tables) and the only symptom is in the API pod log.
PGPW=$(k get secret commons-postgresql -o go-template='{{index .data "postgres-password"|base64decode}}')
HAVE=$(k exec commons-postgresql-0 -- env PGPASSWORD="$PGPW" psql -U postgres -d "$DB" -tAc \
       "select count(*) from pg_extension where extname='pg_trgm'" 2>/dev/null | tr -d ' \r')
if [ "${HAVE:-0}" = 1 ]; then echo "      already installed"
else run k exec commons-postgresql-0 -- env PGPASSWORD="$PGPW" psql -U postgres -d "$DB" \
         -c "CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public"; fi

# --------------------------------------------------------------------------- 2
step "2. GitLab image paths (openg2p/<project> -> openg2p/platform-services/<project>)"
# GitLab moved these projects around 2026-08-24; the old paths answer 403 to an
# anonymous pull. Running pods survive on the node's image cache and only fail
# on the NEXT restart - which is why this surfaces as a wedged rollout rather
# than an outage.
# Confirms the tag really is published at the new path before repointing.
# Setting an image that does not exist wedges the rollout while the old pod
# keeps serving from cache - a failure that looks like nothing happened.
img_exists() {
  local ref=$1 repo tag tok
  repo=${ref#registry.gitlab.com/}; tag=${repo##*:}; repo=${repo%:*}
  tok=$(curl -s --max-time 15 "https://gitlab.com/jwt/auth?scope=repository%3A${repo//\//%2F}%3Apull&service=container_registry" \
        | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
  [ -n "$tok" ] || return 1
  [ "$(curl -s -o /dev/null --max-time 15 -w '%{http_code}' -H "Authorization: Bearer $tok" \
       -H 'Accept: application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.oci.image.index.v1+json' \
       "https://registry.gitlab.com/v2/$repo/manifests/$tag")" = 200 ]
}

k get deploy,sts -o jsonpath='{range .items[*]}{.kind}{"/"}{.metadata.name}{" "}{.spec.template.spec.containers[0].name}{" "}{.spec.template.spec.containers[0].image}{"\n"}{end}' 2>/dev/null \
| grep 'registry.gitlab.com/openg2p/' | grep -v 'platform-services' > /tmp/gen2-old-images.txt
while read -r obj cname img; do
    [ -n "${obj:-}" ] || continue
    new=${img/registry.gitlab.com\/openg2p\//registry.gitlab.com/openg2p/platform-services/}
    if img_exists "$new"; then
      echo "    ${obj#*/}: ${img##*/}  -> platform-services (tag verified)"
      run k set image "$(printf '%s' "$obj" | tr 'A-Z' 'a-z')" "$cname=$new"
    else
      echo "    ${obj#*/}: ${img##*/}  -> SKIPPED, $new is not pullable"
    fi
done < /tmp/gen2-old-images.txt

# --------------------------------------------------------------------------- 3
step "3. AWE must accept this environment's public issuer"
# AWE validates a token's iss against keycloak.issuer PLUS
# keycloak.additional_issuers. The chart templates only the first, so every
# commons-services upgrade drops the extra one and the portal shows
# AWE-ERR-006 / "Invalid issuer" as soon as the AWE pod restarts.
ISS="https://${KC_PUB}/realms/staff"
CFG=$(k get cm commons-services-awe-config -o jsonpath='{.data.config\.yaml}' 2>/dev/null)
if printf '%s' "$CFG" | grep -qF -- "$ISS"; then echo "      already accepts $ISS"
elif [ "$APPLY" = 1 ]; then
  printf '%s' "$CFG" | awk -v iss="$ISS" '
    { print }
    /^[ ]*issuer:/ && !done { printf "%*sadditional_issuers:\n%*s- \"%s\"\n", 4,"", 6,"", iss; done=1 }
  ' > /tmp/awe-config.yaml
  k create configmap commons-services-awe-config --from-file=config.yaml=/tmp/awe-config.yaml \
    --dry-run=client -o yaml | k replace -f -
  k rollout restart deploy/commons-services-awe
  k rollout status  deploy/commons-services-awe --timeout=300s
else echo "      would add $ISS to keycloak.additional_issuers and restart AWE"; fi

# --------------------------------------------------------------------------- 4
step "4. id-generator pools"
# The pool tables are created at startup from the ConfigMap. A type added to
# values after the pod last started has no pool until it restarts.
POOLS=$(k exec commons-postgresql-0 -- env PGPASSWORD="$PGPW" psql -U postgres -d "${DB}_idgenerator" -tAc \
        "select string_agg(replace(tablename,'id_pool_',''),',' order by tablename) from pg_tables where schemaname='public' and tablename like 'id_pool%'" 2>/dev/null | tr -d ' \r')
TYPES=$(k get cm "${REL}-id-generator-config" -o jsonpath='{.data.config\.yaml}' 2>/dev/null | sed -n '/id_types:/,$p' | sed -n 's/^      \([a-z_]*\):$/\1/p' | paste -sd, -)
MISS=""; for t in $(printf '%s' "$TYPES" | tr ',' ' '); do case ",$POOLS," in *,"$t",*) ;; *) MISS="$MISS $t" ;; esac; done
if [ -z "$MISS" ]; then echo "      all pools present ($POOLS)"
else echo "      missing:$MISS"; run k rollout restart "deploy/${REL}-id-generator"; fi

printf '\n%s\n' "done. Re-run gen2-runbook/preflight.sh to confirm."
