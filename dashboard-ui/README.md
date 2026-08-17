# Livestock Registry Dashboard

The analytics view behind the Staff Portal's **Dashboard** header button. It is a
trimmed copy of the livestock screen from `oan_dashboards` — the other registry /
catalogue / A2C / DevOps dashboards from that repo are not included.

The Staff Portal ships as a prebuilt image, so this app runs as its own service
rather than as a portal route. `docker/staff-ui/assets/patch-dashboard-nav.js`
injects the header button that navigates here; the header's **Back** control
returns via the `?returnUrl=` the button appends.

## Where the numbers come from

Every panel reads the **registry database this stack runs** — the same one the
Staff Portal's API writes to — over a read-only connection. There is no fixture,
sample dataset or hardcoded fallback anywhere in the data path, so a registry
with no records renders empty panels rather than filler.

| What | Table |
| --- | --- |
| Holdings (keeper, address, status, registration date) | `g2p_register_livestocks` |
| Animal lines (ear tag, species, breed, health status) | `g2p_register_animals` |
| Keeper gender, for the women-keepers share | `g2p_register_farmers` |
| Labels for species / breed / status | `g2p_attribute_values` |

Two panels measure something different from their counterparts in the reference
dashboard, because this registry holds different data: **Livestock by Species**
counts the animals registered here rather than national census totals, and the
donut reports **Herd Health** rather than land tenure, which a livestock holding
does not record. Both narrow with the filters, as every panel here does.

### Geography

A livestock record stores geography as **free text** — `region = 'Oromia'` — not
as a lookup key. That is deliberate in the register (`admin_area.py`): a surveyor
must be able to file a record from a kebele master-data has not catalogued yet,
which a foreign key would reject.

The choropleth, however, matches its shapes on boundary P-codes (`ET04`). The
boundary files in `public/maps` carry both the name and the code, so they are what
`lib/geo-codes.ts` translates through — exactly, then scoped by the parent level
(which is what separates Amhara's "North Shewa (AM)" from Oromia's "North Shewa
(OR)"), then by prefix ("South Ethiopia" → "South Ethiopia People").

These are the 2021 ADM boundaries, and the regional restructuring since has
produced zones the files do not name. Such a place is listed with its figures
everywhere, but has no shape to shade on the map.

The filters are the columns a livestock holding can actually be narrowed by:
region, zone, woreda, kebele and record status. Every option is offered from the
values present on live records, so a filter can never select nothing.

## Local development

```bash
cp .env.example .env   # DB_* -> the registry database, plus NEXT_PUBLIC_PORTAL_URL
npm ci
npm run dev
```

Against the compose stack that is `DB_HOST=localhost`, `DB_PORT=55432` (see
`POSTGRES_PORT` in `../local/.env`) and the `REGISTRY_DB*` credentials.

### An empty dashboard

If every panel reads zero, the registry has no livestock records — create one in
the Staff Portal, or bring up the `sample-data` service, and reload. To confirm
from the database directly:

```bash
docker compose --env-file local/.env exec postgres \
  psql -U postgres -d livestock -c \
  'SELECT COUNT(*) FROM g2p_register_livestocks'
```

If that errors with `relation ... does not exist`, the platform migrations did
not complete. They abort partway unless `pg_trgm` exists in the registry database
— the register tables carry a GIN trigram index on `search_text`. It is created
by `local/postgres/init.sql`, which only runs on a fresh volume.

## Docker

Built from the repo root:

```bash
docker compose --env-file local/.env up -d --build dashboard-ui
```

`package-lock.json` must be regenerated under Linux whenever dependencies
change — a macOS-resolved lockfile is rejected by `npm ci` inside the image:

```bash
docker run --rm -v "$PWD":/w -w /w node:24-slim npm install --package-lock-only
```
