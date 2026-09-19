# gen2 environment runbook

Everything an OpenG2P gen2 registry environment needs beyond `helm install`, in
the order it has to happen, with the reason for each step and a way to check it.

It exists because bringing `live` up took two days of finding the same class of
problem one symptom at a time. Every item below is something that actually
broke, on a real environment, with the evidence recorded next to it.

## Why bash and not Ansible

Neither the cluster nodes nor the deploy laptops have `ansible`, the
`kubernetes.core` collection, or the `kubernetes` python library. A playbook
would add three dependencies to a box that already has `kubectl`, `helm` and
`psql`. These scripts are idempotent and dry-run by default, which is the
property that actually matters. If Ansible arrives later, `configure.sh` maps
one-to-one onto tasks.

## The three kinds of configuration

Knowing which bucket a setting is in tells you whether it survives a deploy.

| Kind | Where it lives | Survives a deploy? |
| --- | --- | --- |
| **A. Release values** | `helm/openg2p-livestock-registry/values-<env>.yaml`, in git | Yes — this is the goal for everything possible |
| **B. One-time environment setup** | DNS, TLS certs, Istio Gateway, Keycloak users, database extensions | Yes, but nothing recreates it if lost |
| **C. Re-apply after a commons upgrade** | AWE issuers, commons image paths | **No.** A `commons-services` upgrade silently reverts these |

Category C is the trap. The workloads keep running from the node's image cache,
so nothing looks wrong until the next restart — then a rollout wedges and the
portal starts failing on something unrelated-looking.

## Files

| File | Use |
| --- | --- |
| `preflight.sh` | Read-only. Asserts ~29 prerequisites, prints the remedy for each failure. Run first, and after every change. |
| `configure.sh` | Applies category C (and the database extension). Dry-run unless `--apply`. |
| `values/staging.example.yaml` | Annotated template for a new environment's release overlay — category A. |

```sh
./preflight.sh -n <ns> -r <release> -H <public host> -K <public keycloak host>
./configure.sh -n <ns> -r <release> -K <public keycloak host> [--apply]
```

Both take `KUBECONFIG` from the environment, defaulting to the RKE2 admin path.

---

## Phase 0 — before anything

* The namespace exists and `commons` / `commons-services` are deployed and healthy.
* On a single node, check the pod ceiling before adding an environment:
  `kubectl get node <node> -o jsonpath='{.status.allocatable.pods}'` against the
  non-terminated count. Exhausting it presents as unrelated app failures —
  Keycloak crash-looping because postgres could not schedule, and so on.

## Phase 1 — names and routing (category B)

1. **DNS** — an A record per public hostname to the node's public IP. A registry
   needs three: the portal, IAM, and Keycloak.
2. **TLS** — a real certificate per hostname. nginx terminates and proxies to the
   Istio ingress gateway.
3. **Istio Gateway** — a Gateway whose `hosts` list contains those names. The
   built-in `internal` Gateway admits only `*.<ns>.openg2p.test`; a
   VirtualService bound to a Gateway that does not list its host **matches
   nothing, silently**.

Verify: `curl -s -o /dev/null -w '%{http_code}' https://<host>/` reaches nginx.

## Phase 2 — database (category B)

The registry database needs the `pg_trgm` extension. Extensions are
**per-database** and `CREATE DATABASE` does not carry them over, so a restored
or recreated database loses it.

Without it the startup migration aborts at the first GIN trigram index, leaving
roughly 27 of 93 tables, and the only evidence is in the API pod log.

`configure.sh` step 1 installs it. After a database recreate, complete the
schema with one single-threaded pass — gunicorn's three workers each migrate at
boot and race on `CREATE TYPE`:

```sh
kubectl -n <ns> exec deploy/<release>-staff-portal-api -- \
  python -m openg2p_registry_staff_api.main migrate
```

## Phase 3 — image paths (category C)

GitLab moved the OpenG2P projects under `openg2p/platform-services/` around
2026-08-24. The old paths answer **403** to anonymous pulls. Pods already
running are unaffected until they restart, so this shows up as a wedged rollout
weeks later.

`configure.sh` step 2 repoints every workload, verifying each tag is actually
pullable at the new path first.

## Phase 4 — the release overlay (category A)

Start from `values/staging.example.yaml`. The keys that bite:

* `global.registryHostname` — the chart default is a placeholder on a domain
  that does not exist. **Set it to the real public hostname**, so the release's
  own VirtualService owns the URL and every merge reaches it.
* `global.idGeneratorHostname`, `global.aweHostname`, `global.aweDefaultCallbackUrl`
  — independent keys that do **not** follow `registryHostname`.
* `global.minioHost` / `minioSecure` — the external MinIO host presents the local
  CA, which the seed's S3 client rejects; use the in-cluster Service.
* `staffApi` CA mount + `SSL_CERT_FILE` — without it every server-side https call
  fails `CERTIFICATE_VERIFY_FAILED`.
* `celeryWorker`/`celeryBeat` `--concurrency` — celery forks one process per
  **node** CPU; on a 48-core box both pods are OOMKilled at the chart defaults.

`extraVolumes`/`extraVolumeMounts` must sit under the **component** key. Each
component template rebinds `.Values` to its own sub-tree, so a root-level one is
dropped silently and the release still reports `deployed`.

## Phase 5 — AWE issuers (category C)

AWE validates a token's `iss` against `keycloak.issuer` **plus**
`keycloak.additional_issuers`. The chart templates only the first.

One Keycloak serves both the internal and public hostnames (`KC_HOSTNAME_STRICT=false`
means it stamps `iss` from the request Host), so tokens from the public portal
carry the public issuer while AWE expects the internal one — `AWE-ERR-006`,
`Invalid bearer token: Invalid issuer`.

Add the public issuer rather than replacing: other consumers in the namespace
authenticate on the internal one. `configure.sh` step 3 does this and restarts AWE.

**Every commons-services upgrade wipes it.** Re-run `configure.sh --apply` after one.

## Phase 6 — identity (category B)

1. **Keycloak users and roles**:

   ```sh
   KC_BASE_URL=https://<keycloak host> KC_CLIENT_ID=<release>-staff-portal \
   KC_ADMIN_USER=<admin> KC_ADMIN_PASSWORD=<pw> \
   python3 scripts/keycloak_livestock_test_users.py
   ```

   `KC_CLIENT_ID` is required: the chart names the client after the release
   (`<release>-staff-portal`), while the script defaults to the compose-stack name.

2. **IAM application registration** — the `iam-register` hook runs on every deploy
   with the chart's payload. If that payload lacks the approval-ladder roles,
   POST the full one to `/user-access/staff_portal_applications` on
   `commons-services-iam-staff-portal-api`. The client secret is in
   `secret/<release>-staff-portal`, key `client_secret` — no need for the
   Keycloak UI.

   The node can reach the IAM ClusterIP and the public Keycloak directly, so
   this needs no `kubectl cp` or pod shell — which matters, because the
   staff-api image has no `curl`.

3. **Approver-resolver credentials** — the resolver reads **bare, unprefixed**
   variables (`KEYCLOAK_BASE_URL`, `KEYCLOAK_REALM`, `AUTH_CLIENT_ID`,
   `AUTH_CLIENT_SECRET`), not the `registry_staff_portal_api_` prefixed settings.
   Put them in `staffApi.envVars` so they survive a deploy.

## Phase 7 — seed and verify

`db-seed` runs as a post-upgrade hook. Its `wait-for-apps` init container blocks
until staff-api, partner-api, staff-ui **and** AWE all answer, so scaling the
apps to zero makes the seed hang rather than fail.

Then run `preflight.sh`. It should be all PASS.

---

## Known upstream behaviour to design around

| Behaviour | Consequence |
| --- | --- |
| Seed files are bare `INSERT`s | Re-seeding never **updates** a definition. Changing one needs a `patch_*.sql`, or the whole database recreated. |
| `g2p_register_definitions.sql` is one multi-row `INSERT` | A single collision drops all 10 rows. If the app pre-creates a `Farmer` row, the seed silently plants none. |
| `create_migrate()` creates tables, never alters them | A new column needs a `register-metadata/patch_*.sql`. |
| Build-time core patches add models core does not migrate | They must be listed in the extension's `migrate_database()`, or the API 500s on first use. |
| `kubectl set env` / `set image` on a helm-managed object | Reverted by the next upgrade of the release that owns it. |
