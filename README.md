# Livestock Registry

An installable **Livestock Registry** built as a thin extension of the OpenG2P
[registry platform](https://github.com/OpenG2P/registry-platform), following the
same inverted build model as the
[Farmer Registry](https://github.com/OpenG2P/farmer-registry): the platform
publishes the runnable base images and the `openg2p-registry` Helm chart; this
repo adds **only** the livestock domain on top.

The domain is ported from the Odoo module `g2p_livestock_registry`
(`g2p.livestock.registry` and its animal, health, vaccination, vital-event and
breeding lines) onto the platform's register model.

## What this repo owns

| Path | Purpose |
|---|---|
| `livestock-extension/` | The livestock domain package — models, schemas, services, seed metadata (registers, AWE policy, DCI templates) |
| `dashboard-ui/` | The Livestock Registry analytics dashboard — a Next.js app that reads this registry's own tables (see [dashboard-ui/README.md](dashboard-ui/README.md)) |
| `docker/` | Thin Dockerfiles (`FROM openg2p/openg2p-registry-*` + `pip install livestock-extension`) selected at runtime by `REGISTRY_EXTENSION_MODULE` (Option C) |
| `helm/openg2p-livestock-registry/` | A thin wrapper chart: pins `openg2p-registry` as a dependency and supplies the livestock values overlay (no templates) |
| `docker-compose.yml`, `local/` | Docker Compose stack for running the registry on a laptop (`local/` holds its env file and the mock master-data catalog API) |
| `test/sanity/` | The livestock **field-specific** sanity tests (Set 2); the harness + generic tests are inherited from the platform sanity image |

## Registers

Ported from `g2p_livestock_registry`. The livestock holding is the hub: every
line links directly to it, mirroring the module's `line_ids` / `*_event_ids`
one2many fields.

```
Livestock                    farmer identifiers, OAN ID, approval state, source system, sync status
├── Animal                   ear tag, species, breed, sex, age, weight, health & vaccination status
├── HealthEvent              disease/injury/treatment/recovery, onset, resolution, treatment, vet
├── Vaccination              vaccine, vaccination date, next due date, batch, administered by
├── VitalEvent               birth/mortality/disease, cause, offspring count, reporting officer
├── Breeding                 natural or AI, sire/semen, technician, expected calving, outcome
├── VaccineSchedule          vaccine, species, interval in days — drives the next due date
├── ImportBatch              bulk load from DOVAR/LITS/Case Book/ALIVE, row counts, error log
└── AuditLog                 actor, role, action, changes, timestamp, IP, session

Farmer                       farmer_id (FR- + 10 digits) + Fayda FAN, name, sex, contact, geo
                             referenced by the livestock holding
```

The Farmer Registry remains the system of record for people. The `Farmer`
register here holds the identity needed to attach livestock to a person, and the
livestock holding carries the same identifiers (`farmer_uuid`, `farmer_id`,
`fayda_fan_id`, `farmer_name`), mirroring the Fayda FAN into
`link_foundational_id`.

Approval follows the module's four-level ladder — **Kebele → Woreda → Zone →
Region** — seeded as the AWE policy stages in `awe_meta_data/`.

Each register has a `G2PRegister*`, a `G2PRegisterHistory*` and a
`G2PIntakeForm*` model, a matching pydantic schema trio, and a domain service
that validates the domain attributes and builds `search_text` / `record_name`.
Every field, section and tab carries a human-readable label. Species, breed,
vaccine and disease are seeded as attribute lookups — see
[livestock-extension/README.md](livestock-extension/README.md) for the full mapping.

## Run it locally

```bash
docker compose --env-file local/.env up -d --build
```

Then open the **Staff Portal at http://portal.localtest.me:3000** and log in with
`admin` / `admin`.

The stack runs the whole login chain — Keycloak (realm `staff`), the IAM staff
API and master data — alongside the registry, so this is a real OIDC login and
the registry resolves the user's roles into permissions exactly as a deployment
does. Staff API on http://localhost:8001/docs, Partner API on
http://localhost:8002/docs, master data API on http://localhost:8010/docs.
See [local/README.md](local/README.md) for the full service list, why the hosts
are `*.localtest.me` rather than `localhost`, and which integrations are off.

## Dashboard

The portal header carries a **Dashboard** button, left of Configuration, which
opens the Livestock Registry dashboard at
**http://dashboard.localtest.me:3001**. Its own **Back** button returns to the
page the portal was on.

The dashboard is a separate service because the platform ships the Staff Portal
as a finished build that cannot be given new routes — so the button is added to
the published bundle at image build time
(`docker/staff-ui/assets/patch-dashboard-nav.js`) and points at another origin.
It reads the registry database directly and issues nothing but `SELECT`s, so
every panel reflects the records the registry currently holds.

## Deploy

```bash
helm repo add openg2p https://openg2p.github.io/openg2p-helm
helm dependency build ./helm/openg2p-livestock-registry
helm install livestock-registry ./helm/openg2p-livestock-registry \
  --set global.registryHostname=livestock-registry.example.org
```

Set `registry.sanity.runE2e=true` to run the end-to-end sanity suite after install.

## Version pinning

The `openg2p-registry` base image tag (`RP_VERSION` in each Dockerfile) and the
chart dependency version in `helm/openg2p-livestock-registry/Chart.yaml` are
**hardcoded and pinned together**. The livestock images and the wrapper chart are
versioned in lockstep by CI (one version per commit).

To see which version it would pick, run `./scripts/bump-rp-version.sh -n` (dry-run,
writes nothing); `-h` prints help. To apply, run `./scripts/bump-rp-version.sh`
(latest published version) or `./scripts/bump-rp-version.sh <version>` — it updates
the Dockerfiles and the chart dependency together, so they can never drift. A CI
check (`test/test_rp_pin_lockstep.py`) fails the build if they ever do.

See the deployment & extension docs at [docs.openg2p.org](https://docs.openg2p.org).
