"""Guard: every field name the metadata and the reporting views use is a column of the model.

A field name that does not match a column fails silently: the platform saves nothing for a widget bound to a
missing column, a search, filter or duplicate check on it finds nothing, and a reporting view breaks only when it is
refreshed in a cluster. This test reads the files statically, so it needs no database or platform image and runs on
every push in under a second. It is the base the other guard tests (test_search_text.py, test_child_register_keys.py)
read the model from.

The model's columns are read from source with ast, without importing it:
  * the livestock extension's mixins (register_domain/models/*.py), with the mixins they extend (G2PAdminArea)
  * the platform base classes the registers inherit from (CORE_COLUMNS below)
"""

import ast
import json
import re
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "livestock-extension/src/openg2p_registry_livestock_extension"
MODELS = EXT / "register_domain/models"
REGISTER_METADATA = EXT / "meta_data/register-metadata"

# The platform base classes' columns (openg2p_registry_core.models, g2p_register.py) at the pinned platform version.
# When scripts/bump-rp-version.sh moves the pin, compare these with the new version's core models and update
# CORE_VERSION.
CORE_VERSION = "1.2.2-rc.614"
CORE_COLUMNS = {
    "G2PRegister": {
        "internal_record_id", "functional_record_id", "link_internal_record_id", "link_foundational_id",
        "record_name", "record_image_document_id", "created_by", "created_at", "last_approved_at",
        "last_approved_by", "search_text", "record_status", "record_status_reason"},
    "G2PGeo": {
        "latitude", "longitude", "altitude", "plus_code", "address_line_1", "address_line_2", "postal_code",
        "country_code", "geo_lowest_level_value_id", "geo_code_hierarchy_json"},
}


@cache
def models():
    """{register mnemonic: columns} and {table name: register mnemonic}, read from the model source."""
    classes = {}
    for path in sorted(MODELS.glob("*.py")):
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.ClassDef):
                columns = {s.target.id for s in node.body if isinstance(s, ast.AnnAssign)
                           and isinstance(s.value, ast.Call) and getattr(s.value.func, "id", None) == "mapped_column"}
                table = next((s.value.value for s in node.body if isinstance(s, ast.Assign)
                              and getattr(s.targets[0], "id", None) == "__tablename__"), None)
                classes[node.name] = ([ast.unparse(b) for b in node.bases], columns, table)

    def resolve(name):
        if name in CORE_COLUMNS:
            return CORE_COLUMNS[name]
        bases, columns, _ = classes.get(name, ((), set(), None))
        return columns.union(*(resolve(b) for b in bases))

    registers, tables = {}, {}
    for name, (_, _, table) in classes.items():
        if name.startswith("G2PRegister") and not name.startswith("G2PRegisterHistory"):
            mnemonic = name.removeprefix("G2PRegister")
            registers[mnemonic] = resolve(name)
            tables[table] = mnemonic
    return registers, tables


def columns(mnemonic):
    return models()[0][mnemonic]


@cache
def definitions():
    """{register id: (mnemonic, master register id)} from g2p_register_definitions.sql."""
    sql = (REGISTER_METADATA / "g2p_register_definitions.sql").read_text()
    return {i: (m, None if master == "NULL" else master.strip("'"))
            for i, m, master in re.findall(r"\('([0-9a-f-]+)','([A-Za-z]+)','[^']*','[^']*',(NULL|'[0-9a-f-]+')", sql)}


def ui_schemas():
    """(file, schema) for every UI schema (a JSON string literal with widgets) in the seed SQL."""
    for path in sorted((EXT / "meta_data").rglob("*.sql")):
        for literal in re.findall(r"'(\{(?:[^']|'')*\})'", path.read_text()):
            if '"widget' in literal:
                yield path.relative_to(EXT).as_posix(), json.loads(literal.replace("''", "'"))


def widget_fields(node):
    """(register id, field) for every widget data path in a UI schema.

    A path is <register id>.<field>. A dialog table's path is <child register id>.records and its columns' paths
    are fields of that child register.
    """
    if isinstance(node, list):
        for item in node:
            yield from widget_fields(item)
    elif isinstance(node, dict):
        path = node.get("widget-data-path")
        if isinstance(path, str) and "." in path:
            register_id, field = path.split(".", 1)
            if field == "records" and "widget-data-columns" in node:
                for column in node["widget-data-columns"]:
                    yield register_id, column["widget-data-path"]
                return
            yield register_id, field
        for value in node.values():
            yield from widget_fields(value)


# Widget fields that are deliberately not columns. Each is handled in Python before the row is written.
VIRTUAL_FIELDS = {
    # The Farmer lookup's one Fayda ID box: field_rules.split_fayda_id stores it as fayda_fan_id or fayda_fin by
    # length, and fayda_id_view.py adds it back to the response.
    ("Livestock", "fayda_id"),
}


def test_core_columns_follow_the_platform_pin():
    pin = re.search(r"^ARG RP_VERSION=(\S+)$", (ROOT / "docker/staff-api/Dockerfile").read_text(), re.M)
    assert pin and pin.group(1) == CORE_VERSION, "Platform pin moved: re-check CORE_COLUMNS against its core models"


def test_model_source_yields_every_register():
    registers, tables = models()
    assert set(registers) == {mnemonic for mnemonic, _ in definitions().values()} == {
        "Farmer", "Livestock", "Animal", "HealthEvent", "Vaccination", "VitalEvent", "Breeding", "VaccineSchedule",
        "AuditLog", "Retagging"}
    assert {"g2p_register_livestocks", "g2p_register_animals", "g2p_register_breedings"} <= set(tables)
    assert {"region", "kebele_id", "latitude", "search_text"} <= columns("Livestock")
    assert {"ear_tag_id", "ai_technician_name", "link_internal_record_id"} <= columns("Breeding")


def test_widget_data_paths_are_columns():
    registers = definitions()
    fields = {(name, registers.get(register_id, (register_id,))[0], field)
              for name, schema in ui_schemas() for register_id, field in widget_fields(schema)}
    assert len(fields) > 150, "Too few widget data paths found; has the metadata moved?"
    assert any(field == "ai_technician_name" for _, mnemonic, field in fields if mnemonic == "Breeding")
    missing = sorted((name, mnemonic, field) for name, mnemonic, field in fields
                     if (mnemonic, field) not in VIRTUAL_FIELDS
                     and (mnemonic not in models()[0] or field not in columns(mnemonic)))
    assert not missing, missing


def test_register_schema_field_names_are_columns():
    """Deduplication, search result and filter fields (g2p_register_schemas) read the register's columns.

    g2p_register_schemas.sql inserts one row per register; the patches that rewrite a register's schemas name that
    one register in the statement.
    """
    registers = definitions()
    fields = set()
    for path in sorted((EXT / "meta_data").rglob("*.sql")):
        for statement in re.split(r";[ \t]*$", path.read_text(), flags=re.M):
            if "g2p_register_schemas" not in statement:
                continue
            rows = re.findall(r"\(\s*'([0-9a-f-]{36})',\s*('\[.*?\]',\s*'\[.*?\]',\s*'\[.*?\]')\s*\)", statement)
            if not rows:
                named = set(re.findall(r"'([0-9a-f-]{36})'", statement)) & set(registers)
                rows = [(named.pop(), statement)] if len(named) == 1 else []
            fields |= {(path.name, registers[register_id][0], field) for register_id, text in rows
                       for field in re.findall(r'"field_name":\s*"(\w+)"', text)}
    assert {name for name, _, _ in fields} >= {"g2p_register_schemas.sql", "patch_dedup_config.sql",
                                               "patch_animal_search_result_fields.sql"}
    assert len({mnemonic for _, mnemonic, _ in fields}) == len(registers)
    missing = sorted(f for f in fields if f[2] not in columns(f[1]))
    assert not missing, missing


def test_reporting_views_read_model_columns():
    """docker/db-seed/reporting_views.sql reads the register tables by alias (an.species); each must be a column."""
    tables = models()[1]
    sql = re.sub(r"--[^\n]*", " ", (ROOT / "docker/db-seed/reporting_views.sql").read_text())
    aliases = {alias: tables[table] for table, alias in re.findall(r"\b(?:FROM|JOIN)\s+(g2p_\w+)\s+(\w+)", sql, re.I)}
    assert set(aliases.values()) == {"Animal", "Livestock", "Farmer"}, aliases
    reads = {(aliases[alias], column) for alias, column in re.findall(r"\b(\w+)\.(\w+)\b", sql) if alias in aliases}
    assert len(reads) > 20
    missing = sorted((mnemonic, column) for mnemonic, column in reads if column not in columns(mnemonic))
    assert not missing, missing
