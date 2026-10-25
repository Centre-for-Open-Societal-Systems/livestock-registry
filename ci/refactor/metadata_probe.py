"""Native model/metadata rehearsal in an explicitly disposable PostgreSQL.

Not an installer or a migration runner. It never calls native seeding/network
hooks, alters environment data, or changes the promotion preflight.
"""
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys

from sqlalchemy import create_engine, text
from new_dev_metadata import sanitize

repo, domain, mode = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
sys.path.insert(0, str(repo / f"{domain}-extension/src"))
module = f"openg2p_registry_{domain}_extension"
os.environ["REGISTRY_EXTENSION_MODULE"] = module
sys.modules["openg2p_registry_extensions"] = importlib.import_module(module)
importlib.import_module("openg2p_registry_staff_api.config").Settings.get_config()
app = importlib.import_module("openg2p_registry_extensions.app")
app.Initializer()
models = importlib.import_module("openg2p_registry_extensions.register_domain.models")
from openg2p_fastapi_common.models import BaseORMModel

hostname = f"coss-refactor-metadata-{domain}-db"
engine = create_engine(f"postgresql+psycopg2://postgres@{hostname}/refactor_metadata")
with engine.begin() as connection:
    connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
BaseORMModel.metadata.create_all(engine)
if mode == "ddl":
    print(json.dumps({"registry":domain,"ddl":"PASS"}))
    engine.dispose()
    raise SystemExit(0)

output = {"registry":domain,"native_platform":"1.2.2-rc.557","disposable_only":True,"models":{},"sql":[],"seed_errors":[]}
for name in app.MODEL_NAMES:
    model = getattr(models,name)
    output["models"][name] = {"table":model.__tablename__,"columns":{
        column.key:{"type":str(column.type),"nullable":column.nullable,"primary_key":column.primary_key}
        for column in model.__table__.columns}}

package = repo / f"{domain}-extension/src/{module}"
files = sorted((package / "meta_data").rglob("*.sql"))
output["sql"] = [{"path":path.relative_to(repo).as_posix(),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()} for path in files]
tables = {}
allowed = {"g2p_register_definitions","g2p_register_schemas","g2p_register_sections","g2p_register_ui_tabs",
    "g2p_register_ui_tab_sections","g2p_intake_form_definitions","g2p_intake_form_ui_tabs",
    "g2p_intake_form_ui_tab_sections","registry_languages","registry_themes","registry_theme_values",
    "g2p_attributes","g2p_attribute_values","data_models","g2p_data_models",
    "incoming_model_key_paths","incoming_model_register_semantic_patterns","incoming_model_semantic_patterns",
    "incoming_templates","g2p_registry_documents"}
for table in BaseORMModel.metadata.sorted_tables:
    if table.name not in allowed:
        continue
    with engine.connect() as connection:
        rows = [dict(row) for row in connection.execute(table.select()).mappings()]
    rows.sort(key=lambda row:json.dumps(row,sort_keys=True,default=str))
    tables[table.name] = rows
output["metadata"] = tables
destination = repo / f"docs/refactor/new-dev/target-pass-{mode}.json"
destination.parent.mkdir(parents=True,exist_ok=True)
destination.write_text(json.dumps(sanitize(output),indent=2,ensure_ascii=False,default=str)+"\n",encoding="utf-8",newline="\n")
print(json.dumps({"registry":domain,"models":len(output["models"]),"sql_files":len(files),
    "tables":{name:len(rows) for name,rows in tables.items()}}))
engine.dispose()
