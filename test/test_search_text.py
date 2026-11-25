"""Guard: search_text is built from real columns.

The register list and the DCI search match search_text (ILIKE), so a record is only findable by what its search_text
holds. Core fills it on save from each register's domain service (construct_search_text, reached through the
model's get_search_text_fields with the record's to_dict()). A field name that is not a column reads as None, and
the record silently stops being findable by it.
"""

import ast
import re

from test_metadata_consistency import EXT, ROOT, columns, models

SERVICES = EXT / "register_domain/services"


def search_text_reads():
    """{register mnemonic: field names its construct_search_text reads}."""
    reads = {}
    for path in sorted(SERVICES.glob("g2p_register_domain_service_*.py")):
        tree = ast.parse(path.read_text())
        # A service may read a module-level list by name.
        lists = {node.targets[0].id: {e.value for e in node.value.elts if isinstance(e, ast.Constant)}
                 for node in tree.body if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                 and isinstance(node.value, (ast.List, ast.Tuple))}
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            mnemonic = node.name.removeprefix("G2PRegisterDomainService")
            for function in node.body:
                if isinstance(function, ast.FunctionDef) and function.name == "construct_search_text":
                    fields = set()
                    for n in ast.walk(function):
                        if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "get" and n.args \
                                and isinstance(n.args[0], ast.Constant):
                            fields.add(n.args[0].value)
                        elif isinstance(n, (ast.List, ast.Tuple)):
                            fields |= {e.value for e in n.elts
                                       if isinstance(e, ast.Constant) and isinstance(e.value, str)}
                        elif isinstance(n, ast.Name) and n.id in lists:
                            fields |= lists[n.id]
                    reads[mnemonic] = fields
    return reads


def test_search_text_reads_model_columns():
    reads = search_text_reads()
    registers = set(models()[0])
    assert registers <= set(reads), registers - set(reads)
    assert {"functional_record_id", "farmer_id", "fayda_fan_id"} <= reads["Livestock"]
    assert {"ear_tag_id", "ai_technician_name"} <= reads["Breeding"]
    missing = {mnemonic: sorted(fields - columns(mnemonic)) for mnemonic, fields in reads.items()
               if mnemonic in registers and fields - columns(mnemonic)}
    assert not missing, missing


def test_raw_register_inserts_write_search_text():
    """Raw SQL does not fire the ORM listeners that fill search_text, so a row inserted that way must write it.

    test/sanity/sanity/data_seed.py does; any later loader must too. A Python file builds its column list apart from
    the INSERT, so the check is that the file names search_text.
    """
    tables = "|".join(sorted(models()[1]))
    insert = re.compile(rf"INSERT\s+INTO\s+(?:\"?public\"?\.)?\"?(?:{tables})\b", re.I)
    writers = []
    skip = {".git", "node_modules", ".venv", "venv", "__pycache__"}
    for path in sorted(p for p in ROOT.rglob("*") if p.suffix in (".py", ".sql", ".sh") and not skip & set(p.parts)
                       and p.parent != ROOT / "test"):
        text = path.read_text(errors="ignore")
        if insert.search(text):
            writers.append((path.relative_to(ROOT).as_posix(), "search_text" in text))
    assert ("test/sanity/sanity/data_seed.py", True) in writers
    assert all(names for _, names in writers), [name for name, names in writers if not names]
