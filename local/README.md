# Local Docker Compose stack

Runs the whole Livestock Registry — including the real OIDC login chain — on a
laptop.

```bash
docker compose --env-file local/.env up -d --build
```

Then open the **Staff Portal at http://portal.localtest.me:3000** and log in with
`admin` / `admin`.

## Where this came from

The compose stack referenced by the top-level README was never committed to this
repo, so this is a reconstruction derived from the published Helm charts:

| Chart | Supplied |
|---|---|
| `openg2p-registry` 0.0.0-develop.296 | The env contract for staff-api, partner-api, celery worker/beat, db-seed and staff-ui, plus the `iam-register` role/permission catalog |
| `openg2p-commons-base` | Postgres, Redis, MinIO and Keycloak wiring, and the `staff` realm layout |
| `openg2p-commons-services` | IAM, master-data and the `staff-portal` client contract |

Every environment variable here corresponds to one in those charts. The chart is
**not** self-contained: it assumes an OpenG2P environment already runs Postgres,
Redis, MinIO, Keycloak, IAM, master-data and the id-generator as the
`commons-base` and `commons-services` releases. This stack stands those up too.

## Why `*.localtest.me` and not `localhost`

Signing in is a real OIDC round trip across three origins — the portal, the IAM
staff API and Keycloak. IAM sets a session cookie the portal must also send, so
all three need a **common parent domain**; a cookie scoped to `localhost` cannot
be shared with another host. Keycloak additionally advertises one issuer URL that
has to be reachable, and identical, from both the browser and the containers.

`*.localtest.me` is public DNS that resolves to `127.0.0.1`. From the browser
those names reach the published ports; inside the compose network the same names
are declared as network aliases and resolve to the containers. One URL therefore
works from both sides.

This is why each browser-facing service publishes a host port **equal to** its
container port. `staff-ui` does too (3000), but only for convenience — nothing
inside the network needs to reach the portal.

## Services

| Service | URL | Notes |
|---|---|---|
| Staff Portal UI | http://portal.localtest.me:3000 | `admin` / `admin` |
| Livestock dashboard | http://dashboard.localtest.me:3001 | Reached from the portal's Dashboard button; reads the registry DB read-only |
| Staff API | http://localhost:8001/docs | 8000 is taken by IAM, which must publish its container port |
| Partner API | http://localhost:8002/docs | |
| Keycloak | http://keycloak.localtest.me:8080 | admin console `admin` / `admin` |
| IAM staff API | http://iam.localtest.me:8000/docs | |
| Master data API | http://localhost:8010/docs | Geo hierarchy |
| MinIO console | http://minio.localtest.me:9001 | `minioadmin` / `minioadmin` |
| Postgres | `localhost:55432` | user `postgres`, password `postgres` |

One-shot containers that exit 0 when done: `minio-init` (creates the `default`,
`templates` and `documents` buckets), `db-seed` (register metadata, geo data, DCI
templates), `sample-data` (the ten seeded holdings and their animal/event lines)
and `iam-register` (registers the registry's roles/permissions into IAM).

## Integrations that are switched off

These are `commons-services` components with no counterpart here. Each is
disabled through its documented flag rather than left pointing at a host that
does not resolve — see the bottom of `local/.env`.

| Integration | Flag |
|---|---|
| AWE (approval workflow) | `AWE_ENABLED=false` |
| Audit manager | `AUDIT_ENABLED=false` |
| Partner signature validation | `PARTNER_SIGNATURE_VALIDATION_ENABLED=false` |
| Consent manager | `CONSENT_ENFORCEMENT_ENABLED=false` |
| Keymanager auth | `KEYMANAGER_AUTH_ENABLED=false` |

The Kebele → Woreda → Zone → Region approval ladder, partner-signed DCI calls and
consent enforcement therefore do not work locally. Everything else — records,
registers, the intake forms, the geo widget and the DCI templates — does.

## Notes and limitations

- **Everything is emulated.** The OpenG2P base images publish `linux/amd64` only,
  so on Apple Silicon every registry service runs under emulation. First start is
  slow. Keycloak, Postgres, Redis and MinIO use multi-arch images and run
  natively.
- **Keycloak is 24.0.4** and it is the upstream image rather than
  `openg2p/keycloak`. The upstream image is multi-arch and supports
  `--import-realm` directly; the only thing lost is the openg2p login theme.
- **The portal's CSP is overridden.** Left to itself the staff-ui image appends
  `upgrade-insecure-requests` to the policy it builds from the `CSP_SRC_*`
  variables, which makes the browser reissue every stylesheet, script and image
  over https. Nothing here serves TLS, so all of them fail and the portal is
  stuck on its "Loading..." shell. `CSP_HEADER` on the `staff-ui` service
  replaces the generated policy outright and is that same policy without the
  upgrade directive. A deployment behind TLS should drop the override and let the
  image build the policy itself.
- **Ports are baked into two files.** `local/keycloak/realm-staff.json` and
  `local/iam/login_providers.json` contain absolute URLs, so changing
  `STAFF_UI_PORT`, `IAM_PORT` or `KEYCLOAK_PORT` in `local/.env` means updating
  those too.
- **Sample records come from SQL, not `LOAD_SAMPLE_DATA`.** The platform's
  `load_sample_data.py` is hardcoded to the reference registry's tables, so the
  livestock sample set ships as SQL in `docker/db-seed/sample-data/` and the
  `sample-data` service applies it after `db-seed`. It skips itself when
  `g2p_register_livestocks` already has rows. To reload it by hand:

```bash
docker compose --env-file local/.env run --rm --entrypoint sh db-seed \
  -c 'for f in /seed/sample-data/*.sql; do psql -f "$f"; done'
```

## Resetting

```bash
docker compose --env-file local/.env down          # keep data
docker compose --env-file local/.env down -v       # wipe databases and MinIO
```

Note that `down -v` also discards the Keycloak realm, which is re-imported from
`local/keycloak/realm-staff.json` on the next start.

## Requirements

Docker needs roughly **8 GB or more** of memory; Postgres has been observed
crashing mid-import at Docker's 4 GB default. Docker Desktop's `overlay2` image
store is recommended over the containerd/stargz snapshotter.
