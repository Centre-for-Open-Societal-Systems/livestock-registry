#!/usr/bin/env bash
# gen2-runbook/preflight.sh - read-only. Asserts every prerequisite an OpenG2P
# gen2 registry environment needs, and prints the remedy for each failure.
#
#   ./preflight.sh -n live -r livestock-registry \
#                  -H livestock-registry-development.oanstaging.com \
#                  -K keycloak-livestock-development.oanstaging.com
#
# Exit 0 = every FAIL-level check passed. Nothing is modified.
set -uo pipefail
export KUBECONFIG=${KUBECONFIG:-/etc/rancher/rke2/rke2.yaml}

NS=live REL=livestock-registry HOSTNAME_PUB="" KC_PUB="" 
while getopts n:r:H:K: o; do case $o in
  n) NS=$OPTARG ;; r) REL=$OPTARG ;; H) HOSTNAME_PUB=$OPTARG ;; K) KC_PUB=$OPTARG ;;
  *) echo "usage: $0 -n <ns> -r <release> -H <public host> -K <public keycloak host>"; exit 2 ;;
esac; done
[ -n "$HOSTNAME_PUB" ] || { echo "-H is required"; exit 2; }
[ -n "$KC_PUB" ] || KC_PUB="keycloak-${HOSTNAME_PUB#*-}"

k() { if [ "$(id -u)" = 0 ]; then kubectl -n "$NS" "$@"; else sudo -E kubectl -n "$NS" "$@"; fi; }
DB=$(printf '%s' "$REL" | tr '-' '_')
PGPW=$(k get secret commons-postgresql -o go-template='{{index .data "postgres-password"|base64decode}}' 2>/dev/null)
q() { k exec commons-postgresql-0 -- env PGPASSWORD="$PGPW" psql -U postgres -d "$1" -tAc "$2" 2>/dev/null | tr -d ' \r'; }
inpod() { k exec "deploy/$1" -- "${@:2}" 2>/dev/null; }

P=0; F=0; W=0
ok()   { printf '  \033[32mPASS\033[0m  %s\n' "$1"; P=$((P+1)); }
bad()  { printf '  \033[31mFAIL\033[0m  %s\n        -> %s\n' "$1" "$2"; F=$((F+1)); }
warn() { printf '  \033[33mWARN\033[0m  %s\n        -> %s\n' "$1" "$2"; W=$((W+1)); }
sec()  { printf '\n\033[1m%s\033[0m\n' "$1"; }

echo "preflight: namespace=$NS release=$REL host=$HOSTNAME_PUB keycloak=$KC_PUB"

# ---------------------------------------------------------------- platform ---
sec "PLATFORM"

k get ns "$NS" >/dev/null 2>&1 && ok "namespace $NS exists" || { bad "namespace $NS missing" "create the environment first"; echo; exit 1; }

CA_PEM=$(k get cm "${NS}-ca-bundle" -o jsonpath='{.data.ca-bundle\.pem}' 2>/dev/null)
CA_N=$(printf '%s' "$CA_PEM" | grep -c 'BEGIN CERTIFICATE')
if [ "${CA_N:-0}" -gt 0 ]; then
  ok "configmap ${NS}-ca-bundle holds ca-bundle.pem ($CA_N certs)"
else
  bad "configmap ${NS}-ca-bundle missing or empty" "the infra automation creates it; without it every server-side https call to a .test host fails"
fi

[ -n "$PGPW" ] && ok "postgres secret readable" || bad "cannot read secret/commons-postgresql" "postgres not deployed in $NS?"

EXT=$(q "$DB" "select string_agg(extname,',' order by extname) from pg_extension")
case "$EXT" in *pg_trgm*) ok "pg_trgm installed in $DB" ;;
  "") bad "database $DB not reachable or absent" "postgres-init should create it; see the runbook, phase 2" ;;
  *) bad "pg_trgm MISSING in $DB (has: $EXT)" "psql -d $DB -c 'CREATE EXTENSION IF NOT EXISTS pg_trgm' - the registry's GIN trigram index cannot be created without it and the schema migration aborts part-built" ;;
esac

MD_IMG=$(k get deploy commons-services-master-data-api -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null)
MD_ROUTE=$(inpod "${REL}-staff-portal-ui" sh -c 'wget -qS --timeout=5 --post-data="{}" --header="Content-Type: application/json" -O /dev/null "$MASTERDATA_BACKEND_API_URL/geo/get_all_geo_levels" 2>&1 | grep -o "HTTP/1.1 [0-9]*" | head -1')
case "$MD_ROUTE" in
  *400|*422|*200) ok "master-data serves /geo/get_all_geo_levels (${MD_IMG##*:})" ;;
  *404) bad "master-data has no /geo/get_all_geo_levels (${MD_IMG##*:})" "this build serves only the g2p_-prefixed names; Location dropdowns stay empty. Upgrade commons-services to 2.3.0-rc.217 (master-data 1.1.0-rc.55)" ;;
  *) warn "could not probe master-data (${MD_IMG##*:})" "check commons-services-master-data-api is Running" ;;
esac

OLD=$(k get deploy,sts -o jsonpath='{range .items[*]}{.metadata.name}{"="}{.spec.template.spec.containers[0].image}{"\n"}{end}' 2>/dev/null | grep 'registry.gitlab.com/openg2p/' | grep -vc 'platform-services')
if [ "${OLD:-0}" = 0 ]; then ok "no workload on a pre-move GitLab image path"
else bad "$OLD workload(s) still on registry.gitlab.com/openg2p/<project>" "GitLab moved these under openg2p/platform-services/ and the old paths 403 anonymous pulls. They keep running from the node cache and only fail on the NEXT restart - see runbook phase 3"; fi

# ------------------------------------------------------------------- AWE -----
sec "AWE"
AWE_IMG=$(k get deploy commons-services-awe -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null)
case "$AWE_IMG" in *platform-services*) ok "AWE image on the current path" ;;
  "") bad "commons-services-awe not found" "AWE is required for the approval ladder" ;;
  *) bad "AWE image on the dead path ($AWE_IMG)" "kubectl -n $NS set image deploy/commons-services-awe awe=registry.gitlab.com/openg2p/platform-services/awe/openg2p-awe:<tag>" ;;
esac

AWE_CFG=$(k get cm commons-services-awe-config -o jsonpath='{.data.config\.yaml}' 2>/dev/null)
if printf '%s' "$AWE_CFG" | grep -qF -- "$KC_PUB"; then ok "AWE accepts the public issuer ($KC_PUB)"
else bad "AWE does not accept https://$KC_PUB/realms/staff" "add it under keycloak.additional_issuers and restart AWE; EVERY commons-services upgrade wipes this - see runbook phase 5"; fi

# -------------------------------------------------------------- registry -----
sec "REGISTRY RELEASE"
ST=$(helm status "$REL" -n "$NS" -o json 2>/dev/null | sed -n 's/.*"status":"\([a-z]*\)".*/\1/p' | head -1)
[ "$ST" = deployed ] && ok "helm release $REL is deployed" || bad "helm release $REL is '${ST:-absent}'" "helm history $REL -n $NS"

PLACEHOLDER=$(k get deploy -l "app.kubernetes.io/instance=$REL" -o yaml 2>/dev/null \
  | grep -oE '[a-zA-Z0-9.-]*\.openg2p\.org' | grep -v '@' | sort -u | wc -l | tr -d ' ')
[ "$PLACEHOLDER" = 0 ] && ok "no chart placeholder domain (.openg2p.org) in any workload" \
  || bad "$PLACEHOLDER placeholder hostname(s) *.openg2p.org in the $REL workloads" "the chart defaults address the release at *.<ns>.openg2p.org which resolves nowhere; set global.registryHostname and the independent keys idGeneratorHostname / aweHostname / aweDefaultCallbackUrl"

VS_HOST=$(k get vs "${REL}-staff-portal-ui" -o jsonpath='{.spec.hosts[0]}' 2>/dev/null)
VS_GW=$(k get vs "${REL}-staff-portal-ui" -o jsonpath='{.spec.gateways[0]}' 2>/dev/null)
if [ "$VS_HOST" = "$HOSTNAME_PUB" ]; then ok "staff-ui VirtualService owns $HOSTNAME_PUB (gateway $VS_GW)"
else bad "staff-ui VirtualService host is '${VS_HOST:-none}', expected $HOSTNAME_PUB" "until the release owns the public host, deploys have no visible effect"; fi
if [ -n "$VS_GW" ] && k get gateway "$VS_GW" -o jsonpath='{.spec.servers[*].hosts}' 2>/dev/null | grep -q "$HOSTNAME_PUB"; then
  ok "gateway $VS_GW admits $HOSTNAME_PUB"
else bad "gateway '${VS_GW:-none}' does not admit $HOSTNAME_PUB" "a VirtualService bound to a gateway that does not list its host matches nothing"; fi

SA_ENV=$(k get deploy "${REL}-staff-portal-api" -o jsonpath='{range .spec.template.spec.containers[0].env[*]}{.name}={.value}{"\n"}{end}' 2>/dev/null)
printf '%s' "$SA_ENV" | grep -q '^SSL_CERT_FILE=' && ok "staff-api trusts the local CA (SSL_CERT_FILE)" \
  || bad "staff-api has no SSL_CERT_FILE" "server-side https to .test hosts fails CERTIFICATE_VERIFY_FAILED; mount ${NS}-ca-bundle and set SSL_CERT_FILE"
for v in KEYCLOAK_BASE_URL KEYCLOAK_REALM AUTH_CLIENT_ID AUTH_CLIENT_SECRET; do
  printf '%s' "$SA_ENV" | grep -q "^$v=" && ok "approver-resolver env $v set" \
    || bad "approver-resolver env $v missing" "the resolver reads BARE os.environ names (not the registry_staff_portal_api_ prefix) and resolves nobody without them"
done

for c in celery-worker celery-beat-producer; do
  OPTS=$(k get deploy "${REL}-${c}" -o jsonpath='{range .spec.template.spec.containers[0].env[*]}{.name}={.value}{"\n"}{end}' 2>/dev/null | sed -n 's/^CELERY_OPTS=//p')
  case "$OPTS" in *--concurrency=*) ok "$c pins celery concurrency" ;;
    "") warn "$c not found" "" ;;
    *) bad "$c has no --concurrency" "celery forks one process per NODE cpu (48 here) and is OOMKilled; append --concurrency=4 to CELERY_OPTS" ;;
  esac
done

# ------------------------------------------------------------------ data -----
sec "DATA"
TBL=$(q "$DB" "select count(*) from pg_tables where schemaname='public'")
[ "${TBL:-0}" -ge 90 ] && ok "$DB has $TBL tables" || bad "$DB has only ${TBL:-0} tables" "the startup migration aborted part-built - almost always pg_trgm (see above). Fix that, then run: kubectl -n $NS exec deploy/${REL}-staff-portal-api -- python -m openg2p_registry_staff_api.main migrate"

DEFS=$(q "$DB" "select count(*) from g2p_register_definitions")
DUP=$(q "$DB" "select count(*) from (select lower(register_mnemonic) m from g2p_register_definitions group by 1 having count(*)>1) x")
[ "${DEFS:-0}" -ge 10 ] && ok "g2p_register_definitions has $DEFS rows" \
  || bad "g2p_register_definitions has only ${DEFS:-0} rows" "its seed file is ONE multi-row INSERT, so a single collision drops all 10; delete the app-created Farmer rows and re-run db-seed"
[ "${DUP:-0}" = 0 ] && ok "no duplicate register mnemonics" || warn "$DUP duplicated mnemonic(s)" "a case-variant row will collide with the seed on every run"

for t in g2p_attribute_value_schedules g2p_attribute_value_species_configs; do
  [ "$(q "$DB" "select to_regclass('public.$t') is not null")" = t ] && ok "patched core table $t exists" \
    || bad "table $t missing" "it is added by a build-time core patch and migrated from the extension's migrate_database(); staff-api 500s on /api/attributes/values without it"
done
[ "$(q "$DB" "select count(*) from information_schema.columns where table_name='g2p_intake_form_animals' and column_name='colour'")" = 1 ] \
  && ok "g2p_intake_form_animals.colour present" || bad "column colour missing" "create_migrate() never ALTERs an existing table; add a register-metadata patch_*.sql"

POOLS=$(q "${DB}_idgenerator" "select string_agg(replace(tablename,'id_pool_',''),',' order by tablename) from pg_tables where schemaname='public' and tablename like 'id_pool%'")
CFG_TYPES=$(k get cm "${REL}-id-generator-config" -o jsonpath='{.data.config\.yaml}' 2>/dev/null | sed -n '/id_types:/,$p' | sed -n 's/^      \([a-z_]*\):$/\1/p' | paste -sd, -)
MISSING=""
for t in $(printf '%s' "$CFG_TYPES" | tr ',' ' '); do case ",$POOLS," in *,"$t",*) ;; *) MISSING="$MISSING $t" ;; esac; done
[ -z "$MISSING" ] && ok "every configured id type has a pool ($POOLS)" \
  || bad "id pools missing for:$MISSING" "kubectl -n $NS rollout restart deploy/${REL}-id-generator"

# -------------------------------------------------------------- identity -----
sec "IDENTITY"
CLIENT="${REL}-staff-portal"
ROLES=$(q iam "select count(*) from staff_roles r join staff_portal_applications a on a.id=r.application_id where a.application_mnemonic='$CLIENT'")
[ "${ROLES:-0}" -ge 16 ] && ok "IAM has $ROLES roles for $CLIENT" \
  || bad "IAM has only ${ROLES:-0} roles for $CLIENT" "the approval-ladder roles are missing; POST the roles payload to /user-access/staff_portal_applications - runbook phase 6"
APPR=$(q keycloak "select count(*) from user_attribute a join user_entity u on u.id=a.user_id join realm r on r.id=u.realm_id where r.name='staff' and a.name='approver_location_value'")
[ "${APPR:-0}" -ge 1 ] && ok "$APPR Keycloak user(s) carry approver_location_value" \
  || bad "no Keycloak user has approver_location_value" "run scripts/keycloak_livestock_test_users.py with KC_CLIENT_ID=$CLIENT - the default client name only exists on the compose stack"
KCR=$(q keycloak "select count(*) from keycloak_role cr join client c on c.id=cr.client where c.client_id='$CLIENT' and cr.name ilike '%approver%'")
[ "${KCR:-0}" -ge 4 ] && ok "$KCR approver client roles on $CLIENT" || bad "only ${KCR:-0} approver roles on $CLIENT" "same script creates them"

printf '\n\033[1mRESULT\033[0m  %d passed, %d failed, %d warnings\n' "$P" "$F" "$W"
[ "$F" -eq 0 ] || echo "fix the FAIL items above, then re-run. Each line names the remedy."
exit $([ "$F" -eq 0 ] && echo 0 || echo 1)
