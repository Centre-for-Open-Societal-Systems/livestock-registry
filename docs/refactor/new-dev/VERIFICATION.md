# New Dev field and section verification

Authenticated metadata captured 2026-10-24T18:37:40.160506+00:00.

| Register | Live fields | Missing from native refactor register |
| --- | --- | --- |
| Farmer | 42 | None |
| Livestock | 49 | None |
| Animal | 28 | None |
| HealthEvent | 26 | None |
| Vaccination | 22 | None |
| VitalEvent | 34 | None |
| Breeding | 29 | None |
| Retagging | 21 | None |
| VaccineSchedule | 18 | None |
| ImportBatch | 25 | None |
| AuditLog | 22 | None |

All 316 live declared fields are present. All 14 section IDs and 1 form IDs are retained.
Register/history/intake mappings and every section path/binding are enumerated in comparison.json.

Domain fields are present in all three native register/history/intake models. Native history owns its version/audit metadata; the live-register control fields last_approved_at, last_approved_by and search_text are not copied into the history model.

Both native psql seed passes completed without SQL errors; final metadata is identical on repeat.

This verifies effective application metadata against native rc.557 ORM/DDL and seed results. Physical New Dev database columns, portal rendering, business-rule parity, restored-data upgrade and full live integration are not certified.

The Farmer identity pair is captured on the domain root. The retired sibling Farmer intake mapping is intentionally replaced by the separately approved reference dependency. All Farmer register sections and field names remain.

Crop's legacy registry-database lookup SQL is preserved as a Master Data administration prerequisite in the central Helm repository; it is not executed against a registry. Existing shared values are not changed.

The live Crop FARMER_REFERENCE_CHANGED_V1 pipeline configuration requires an explicit port and remains a promotion blocker. Livestock MY_DATA_MODEL is upstream example content and is intentionally not added to the domain extension.

No records, approvals, identity grants, environment settings or runtime workloads were modified.
