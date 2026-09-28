# Livestock Extension

The Livestock domain package for the OpenG2P registry platform: SQLAlchemy
models, pydantic schemas, register domain services (validation, `search_text`
and `record_name` construction), the functional-ID generator, and the seed
metadata (register definitions/sections/UI tabs, lookup data, AWE policies, DCI
templates).

Installed into the registry-platform base images and selected at runtime by
`REGISTRY_EXTENSION_MODULE=openg2p_registry_livestock_extension`.

## Registers

Ported from the Odoo module `g2p_livestock_registry`: the livestock holding is
the hub, and every line links straight to it, mirroring the module's `line_ids`
and `*_event_ids` one2many fields.

| Mnemonic | Parent | Table | Odoo model |
|---|---|---|---|
| `Farmer` | — (root) | `g2p_register_farmers` | `res.partner` (farmer fields) |
| `Livestock` | — (root) | `g2p_register_livestocks` | `g2p.livestock.registry` |
| `Animal` | Livestock | `g2p_register_animals` | `g2p.livestock.registry.line` |
| `HealthEvent` | Livestock | `g2p_register_health_events` | `g2p.livestock.health.event` |
| `Vaccination` | Livestock | `g2p_register_vaccinations` | `g2p.livestock.vaccination` |
| `VitalEvent` | Livestock | `g2p_register_vital_events` | `g2p.livestock.vital.event` |
| `Breeding` | Livestock | `g2p_register_breedings` | `g2p.livestock.breeding` |
| `VaccineSchedule` | Livestock | `g2p_register_vaccine_schedules` | `g2p.livestock.vaccine.schedule` |
| `ImportBatch` | Livestock | `g2p_register_import_batches` | `g2p.livestock.import.batch` |
| `AuditLog` | Livestock | `g2p_register_audit_logs` | `g2p.livestock.audit.log` |

`live_stock_dashboard` is deliberately not ported: the staff portal renders its
own views over these registers.

### The farmer is identified, not owned

The Farmer Registry stays the system of record for people. The `Farmer` register
here carries only the identity needed to attach livestock to a person — the
externally issued `farmer_id` and `fayda_fan_id` alongside the internally
generated functional ID, plus name, sex and contact.

The livestock holding repeats those identifiers (`farmer_uuid`, `farmer_id`,
`fayda_fan_id`, and a denormalised `farmer_name`) so a holding can be read
without a join, and mirrors the Fayda FAN into the platform's
`link_foundational_id` — the column that exists for "this record belongs to a
person held elsewhere".

`farmer_id` is validated as `FR-` followed by exactly ten digits, matching
`_check_farmer_id_format` in the Odoo module.

### Two identifiers for a holding

* **`oan_id`** is the OAN identifier built from the farmer code and first name,
  e.g. `FR-1234567890-ABEBE-001`, with a running number per farmer — the format
  `_generate_oan_id` produces. It is what an operator reads and what
  `record_name` uses.
* **`functional_record_id`** is allocated by the platform's id-generator with the
  `LS-` prefix, and is the stable key other records reference.

Animals are identified by **`ear_tag_id`**, which with species and owner forms
the uniqueness rule the module enforces as `ear_tag_species_owner_uniq`.

### Approval

Kebele → Woreda → Zone → Region, each level gated on the previous one, as
`_APPROVAL_LEVELS` / `_APPROVAL_REQUIRED_STATE` define it. The ladder appears in
two places: as the `state` enum on the livestock holding, and as the four ordered
stages of the seeded AWE policies in `awe_meta_data/`.

### Catalogues and lookups

Values an administrator should be able to extend without a code change are
**attribute lookups** — String columns resolved against `g2p_attributes` /
`g2p_attribute_values`, seeded in `meta_data/lookup-data/` and refreshed from the
master-data catalogue by `catalog-sync`:

| Attribute | Hierarchy |
|---|---|
| `LIVESTOCK_SPECIES` | flat |
| `LIVESTOCK_BREED` | under species |
| `VACCINE_TYPE` | under species |
| `LIVESTOCK_DISEASE` | flat |
| `APPROVAL_STATUS` | flat |

`local/masterdata-mock/catalogs.json` is the same data in the catalogue API's
shape; the two share the `<catalog>_<code>` value-id scheme, so the seeded rows
and the synced rows are the same rows.

REGION / ZONE / WOREDA / KEBELE are not seeded here: the platform resolves the
geo hierarchy from master-data through `G2PGeo.geo_lowest_level_value_id`.

Closed value sets stay as Python enums (`register_domain/models/enums.py`):
livestock state, source system, sync status, animal state, sex, health status,
vaccination status, health-event type, vital-event type and cause, breeding event
type and outcome, event location, import source and state, and audit action type.
