"""Run in an unmodified published base image, with no network or database.

Usage: python runtime_probe.py <repo> <domain> <staff|worker>
"""
from __future__ import annotations

import importlib
import inspect
import json
import sys
import asyncio
from datetime import date
from pathlib import Path

repo, domain, mode = sys.argv[1:]
source = Path(repo) / f"{domain}-extension/src"
sys.path.insert(0, str(source))
# Match Option C in the native entry points; do not patch runtime methods.
extension = importlib.import_module(f"openg2p_registry_{domain}_extension")
sys.modules["openg2p_registry_extensions"] = extension
app_package = "openg2p_registry_staff_api" if mode == "staff" else "openg2p_registry_celery_worker"
importlib.import_module(f"{app_package}.config").Settings.get_config()
models = importlib.import_module("openg2p_registry_extensions.register_domain.models")
schemas = importlib.import_module("openg2p_registry_extensions.register_domain.schemas")
services = importlib.import_module("openg2p_registry_extensions.register_domain.services")
from openg2p_registry_core.interfaces import G2PRegisterDomainFactory

counts = {}
schema_gaps = {}
for name, cls in vars(models).items():
    if inspect.isclass(cls) and name.startswith(("G2PRegister", "G2PIntakeForm")) and hasattr(cls, "__table__"):
        counts[name] = len(cls.__table__.columns)
        if name.startswith("G2PRegisterHistory"):
            schema = getattr(schemas, "G2PRegisterHistorySchema" + name.removeprefix("G2PRegisterHistory"), None)
            assert schema, f"Missing history schema: {name}"
            domain_fields = {field for base in cls.__mro__ if base.__module__.startswith("openg2p_registry_extensions.") for field in getattr(base, "__annotations__", {}) if not field.startswith("_")}
            missing = domain_fields - set(schema.model_fields)
            if missing:
                schema_gaps[name] = sorted(missing)
        elif name.startswith("G2PIntakeForm"):
            assert getattr(schemas, "G2PIntakeFormSchema" + name.removeprefix("G2PIntakeForm"), None), f"Missing intake schema: {name}"
        if name.startswith("G2PRegister") and not name.startswith("G2PRegisterHistory"):
            mnemonic = name.removeprefix("G2PRegister")
            service = G2PRegisterDomainFactory().get_domain_service(mnemonic)
            assert service is not None, f"Missing native domain service: {mnemonic}"
            assert getattr(schemas, f"G2PRegisterSchema{mnemonic}", None), f"Missing schema: {mnemonic}"
assert counts, "No domain tables loaded"
assert not schema_gaps, f"History schema discards domain fields: {schema_gaps}"
extension_app = importlib.import_module("openg2p_registry_extensions.app")
owned_models = {name for name, cls in vars(models).items() if inspect.isclass(cls) and cls.__module__.startswith("openg2p_registry_extensions.") and hasattr(cls, "__table__")}
assert owned_models == set(extension_app.MODEL_NAMES), f"Migration coverage mismatch: {owned_models.symmetric_difference(extension_app.MODEL_NAMES)}"
checks = []
from openg2p_registry_core.errors import G2PRegistryException
profile_rules = importlib.import_module("openg2p_registry_extensions.farmer_reference.profile")
for name in ("G2PRegisterFarmer", "G2PRegisterHistoryFarmer", "G2PIntakeFormFarmer"):
    assert profile_rules.PROFILE_FIELDS <= set(getattr(models, name).__table__.columns.keys()), f"Missing profile model field: {name}"
for name in ("G2PRegisterSchemaFarmer", "G2PRegisterHistorySchemaFarmer", "G2PIntakeFormSchemaFarmer"):
    cls = getattr(schemas, name)
    assert profile_rules.PROFILE_FIELDS <= set(cls.model_fields), f"Missing profile schema field: {name}"
    profile = profile_rules.local_profile({"farmer_id": "FR-000000000001", "approved_uid": "0000000000000001",
                                          "birth_date": "2000-01-01", "address_line_1": "Test address",
                                          "first_name_amh": "Test local name", "email": None})
    parsed = cls(**profile)
    assert parsed.date_of_birth == date(2000, 1, 1) and parsed.address_line_1 == "Test address"
checks.append("identity/contact/location fields survive every schema trio")


def rejects(name, callback):
    try:
        callback()
    except G2PRegistryException:
        checks.append(name)
    else:
        raise AssertionError(f"Expected domain rejection: {name}")


farmer_service = services.G2PRegisterDomainServiceFarmer()
draft = {"farmer_id": "", "fayda_fan_id": None}
asyncio.run(farmer_service.validate_domain_attributes([draft]))
assert draft["farmer_id"] == "" and draft["fayda_fan_id"] is None
checks.append("native Farmer service accepts partial drafts")
normalized = {"farmer_id": " FR-000000000001 ", "fayda_fan_id": "0000 0000 0000 0001"}
asyncio.run(farmer_service.validate_domain_attributes([normalized]))
assert normalized["farmer_id"] == "FR-000000000001" and normalized["fayda_fan_id"] == "0000000000000001"
checks.append("native Farmer service normalizes identity without numeric coercion")
rejects("native Farmer service rejects Unicode digits", lambda: asyncio.run(farmer_service.validate_domain_attributes([{"farmer_id": "FR-" + "١" * 12}])))
projection = importlib.import_module("openg2p_registry_extensions.farmer_reference.projection")
farmer = models.G2PRegisterFarmer(internal_record_id="local-test-reference", farmer_id="FR-000000000001",
                                  fayda_fan_id="0000000000000002", first_name="Approved", middle_name=None,
                                  last_name="Farmer")
domain_class = models.G2PRegisterCropSown if domain == "cropsown" else models.G2PRegisterLivestock
domain_row = domain_class(internal_record_id="local-test-domain", farmer_uuid="local-test-reference",
                         farmer_id="FR-000000000001", fayda_fan_id="0000000000000001", farmer_name="Old Farmer")
if domain == "cropsown":
    domain_row.crop_year = "2026"
    domain_row.production_season = "domain-season"
assert projection._mirror(domain_row, farmer) == 1
assert domain_row.farmer_uuid == "local-test-reference" and domain_row.fayda_fan_id == "0000000000000002"
assert domain_row.farmer_name == "Approved Farmer"
assert domain_row.record_name == domain_row.get_record_name_fields()
assert domain_row.record_name == ("FR-000000000001" if domain == "cropsown" else "Approved Farmer")
if domain == "cropsown":
    assert domain_row.crop_year == "2026" and domain_row.production_season == "domain-season"
checks.append("approved identity mirror works with concrete domain ORM and naming services")


if domain == "cropsown":
    compute = importlib.import_module("openg2p_registry_extensions.register_domain.services.domain_compute_utils")
    row = {"qty_harvested": 10, "area_harvested": 2, "actual_yield": 8, "expected_yield": 10, "planned_area": 4, "actual_seed_qty": 20, "actual_fertilizer_qty": 50}
    compute.compute_production_results(row)
    assert [row[k] for k in ("yield_per_ha", "yield_performance_pct", "land_utilization_rate", "seed_productivity", "fertilizer_efficiency")] == [500, 80, 0.5, 50, 20]
    checks.append("production unit conversions and ratios")
    zero = {"qty_harvested": 0, "area_harvested": 0}
    compute.compute_production_results(zero)
    assert zero["yield_per_ha"] == zero["seed_productivity"] == 0
    checks.append("zero denominators")
    area = {"cluster_area_timad": 4}
    compute.compute_cluster_area(area)
    assert area["cluster_area_hectare"] == 1
    checks.append("timad to hectare")
    assert compute.is_date_in_season(date(2026, 1, 1), 11, 1, 2, 28)
    assert not compute.is_date_in_season(date(2026, 6, 1), 11, 1, 2, 28)
    checks.append("season across year boundary")
    service = services.G2PRegisterDomainServiceProduction()
    rejects("negative yield", lambda: service._validate_yields({"actual_yield": -1}))
    rejects("zero production area", lambda: service._validate_area_under_production({"area_under_production": 0}))
    geo_payload = {"geo_code_hierarchy_json": {"hierarchy": [{"level_mnemonic": "WOREDA", "level_value_id": "woreda-ET123", "level_value_mnemonic": "Test Woreda"}]}, "crop_year": "2026"}
    # An object with no execute/get methods detects a draft save attempting
    # database writes while preparing its own display fields.
    asyncio.run(services.G2PRegisterDomainServiceCropSown()._sync_address_names_on_record(geo_payload, session=object()))
    assert geo_payload["woreda"] == "woreda-ET123" and geo_payload["woreda_name"] == "Test Woreda" and geo_payload["crop_year"] == "2026"
    checks.append("canonical geography and no draft-to-live writes")
elif domain == "livestock":
    animal = services.G2PRegisterDomainServiceAnimal()
    row = {"quantity": "12"}
    animal._validate_quantity(row, True)
    assert row["quantity"] == 12
    checks.append("flock count normalization")
    rejects("missing flock count", lambda: animal._validate_quantity({}, True))
    rejects("zero flock count", lambda: animal._validate_quantity({"quantity": 0}, True))
    rejects("negative animal weight", lambda: animal._validate_weight({"weight": -1}))
    animal._validate_weight({"weight": 30})
    checks.append("positive animal weight")
    rejects("registration before birth", lambda: animal._validate_registration_not_before_birth({"date_of_birth": "2025-02-01", "registration_date": "2025-01-01"}))
print(json.dumps({"domain": domain, "runtime": mode, "model_columns": counts, "native_factory_resolution": "PASS", "portable_domain_checks": checks, "database_accessed": False}, indent=2))
