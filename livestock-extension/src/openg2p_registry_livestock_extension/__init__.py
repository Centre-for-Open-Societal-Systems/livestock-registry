__version__ = "1.0.0"
__variant__ = "livestock"

import os
import sys

# Alias so the core platform can import from openg2p_registry_extensions
# (the generic name) while the actual package is openg2p_registry_livestock_extension.
try:
    import openg2p_registry_livestock_extension
    sys.modules["openg2p_registry_extensions"] = openg2p_registry_livestock_extension
    import openg2p_registry_livestock_extension.config
    sys.modules["openg2p_registry_extensions.config"] = openg2p_registry_livestock_extension.config
    import openg2p_registry_livestock_extension.register_domain
    sys.modules["openg2p_registry_extensions.register_domain"] = openg2p_registry_livestock_extension.register_domain
    if hasattr(openg2p_registry_livestock_extension, "app"):
        sys.modules["openg2p_registry_extensions.app"] = openg2p_registry_livestock_extension.app
except Exception:
    pass

# Bridge staff-api / platform settings to iam_core common_ settings
_redis_url = os.environ.get("REGISTRY_STAFF_PORTAL_API_AUTH_REDIS_URL") or os.environ.get("COMMON_AUTH_REDIS_URL")
if _redis_url:
    os.environ["COMMON_AUTH_REDIS_URL"] = _redis_url

_auth_provider_url = os.environ.get("REGISTRY_STAFF_PORTAL_API_AUTH_PROVIDER_API_URL") or os.environ.get("COMMON_AUTH_PROVIDER_API_URL")
if _auth_provider_url:
    os.environ["COMMON_AUTH_PROVIDER_API_URL"] = _auth_provider_url

_client_id = os.environ.get("REGISTRY_STAFF_PORTAL_API_KEYCLOAK_CLIENT_ID") or os.environ.get("COMMON_KEYCLOAK_CLIENT_ID")
if _client_id:
    os.environ["COMMON_KEYCLOAK_CLIENT_ID"] = _client_id

try:
    from iam_core.user_auth.config import Settings as IamSettings
    _iam_cfg = IamSettings.get_config(strict=False)
    if _redis_url:
        _iam_cfg.auth_redis_url = _redis_url
    if _auth_provider_url:
        _iam_cfg.auth_provider_api_url = _auth_provider_url
    if _client_id:
        _iam_cfg.keycloak_client_id = _client_id
except Exception:
    pass

# Bridge database settings to openg2p_fastapi_common and openg2p_registry_core
_db_host = (
    os.environ.get("REGISTRY_STAFF_PORTAL_API_DB_HOSTNAME")
    or os.environ.get("REGISTRY_PARTNER_API_DB_HOSTNAME")
    or os.environ.get("REGISTRY_CELERY_WORKERS_DB_HOSTNAME")
    or os.environ.get("REGISTRY_CELERY_BEAT_DB_HOSTNAME")
    or os.environ.get("COMMON_DB_HOSTNAME")
    or "postgres"
)
_db_port = int(
    os.environ.get("REGISTRY_STAFF_PORTAL_API_DB_PORT")
    or os.environ.get("REGISTRY_PARTNER_API_DB_PORT")
    or os.environ.get("REGISTRY_CELERY_WORKERS_DB_PORT")
    or os.environ.get("REGISTRY_CELERY_BEAT_DB_PORT")
    or os.environ.get("COMMON_DB_PORT")
    or 5432
)
_db_name = (
    os.environ.get("REGISTRY_STAFF_PORTAL_API_DB_DBNAME")
    or os.environ.get("REGISTRY_PARTNER_API_DB_DBNAME")
    or os.environ.get("REGISTRY_CELERY_WORKERS_DB_DBNAME")
    or os.environ.get("REGISTRY_CELERY_BEAT_DB_DBNAME")
    or os.environ.get("REGISTRY_DB")
    or "livestock"
)
_db_user = (
    os.environ.get("REGISTRY_STAFF_PORTAL_API_DB_USERNAME")
    or os.environ.get("REGISTRY_PARTNER_API_DB_USERNAME")
    or os.environ.get("REGISTRY_CELERY_WORKERS_DB_USERNAME")
    or os.environ.get("REGISTRY_CELERY_BEAT_DB_USERNAME")
    or os.environ.get("REGISTRY_DB_USER")
    or "livestock_user"
)
_db_pass = (
    os.environ.get("REGISTRY_STAFF_PORTAL_API_DB_PASSWORD")
    or os.environ.get("REGISTRY_PARTNER_API_DB_PASSWORD")
    or os.environ.get("REGISTRY_CELERY_WORKERS_DB_PASSWORD")
    or os.environ.get("REGISTRY_CELERY_BEAT_DB_PASSWORD")
    or os.environ.get("REGISTRY_DB_PASSWORD")
    or "livestock_pass"
)

os.environ["COMMON_DB_HOSTNAME"] = _db_host
os.environ["COMMON_DB_PORT"] = str(_db_port)
os.environ["COMMON_DB_DBNAME"] = _db_name
os.environ["COMMON_DB_USERNAME"] = _db_user
os.environ["COMMON_DB_PASSWORD"] = _db_pass
_db_datasource = f"postgresql+asyncpg://{_db_user}:{_db_pass}@{_db_host}:{_db_port}/{_db_name}"
os.environ["COMMON_DB_DATASOURCE"] = _db_datasource

try:
    import openg2p_fastapi_common.app as fc_app
    if hasattr(fc_app, "_config"):
        fc_app._config.db_hostname = _db_host
        fc_app._config.db_port = _db_port
        fc_app._config.db_dbname = _db_name
        fc_app._config.db_username = _db_user
        fc_app._config.db_password = _db_pass
        fc_app._config.db_datasource = _db_datasource

    from openg2p_fastapi_common.context import dbengine
    from sqlalchemy.ext.asyncio import create_async_engine

    _registry_engine = None

    def _get_registry_engine():
        global _registry_engine
        if _registry_engine is None:
            _registry_engine = create_async_engine(
                _db_datasource,
                pool_pre_ping=True,
                pool_recycle=1800,
            )
        return _registry_engine

    _orig_dbengine_get = dbengine.get
    _orig_dbengine_set = dbengine.set

    def _safe_dbengine_get():
        val = _orig_dbengine_get()
        if val is None or getattr(getattr(val, "url", None), "host", None) in ("localhost", "127.0.0.1", None):
            val = _get_registry_engine()
            _orig_dbengine_set(val)
        return val

    def _safe_dbengine_set(value):
        if value is not None and getattr(getattr(value, "url", None), "host", None) in ("localhost", "127.0.0.1", None):
            value = _get_registry_engine()
        _orig_dbengine_set(value)

    dbengine.get = _safe_dbengine_get
    dbengine.set = _safe_dbengine_set
    dbengine.set(_get_registry_engine())

    from openg2p_fastapi_common.app import Initializer as BaseInitializer
    def _patched_init_db(self):
        dbengine.set(_get_registry_engine())
    BaseInitializer.init_db = _patched_init_db
except Exception:
    pass

try:
    import openg2p_registry_core.engine as core_engine
    from sqlalchemy.ext.asyncio import create_async_engine

    _md_host = (
        os.environ.get("REGISTRY_STAFF_PORTAL_API_MASTER_DATA_DB_HOSTNAME")
        or os.environ.get("REGISTRY_PARTNER_API_MASTER_DATA_DB_HOSTNAME")
        or "postgres"
    )
    _md_port = (
        os.environ.get("REGISTRY_STAFF_PORTAL_API_MASTER_DATA_DB_PORT")
        or os.environ.get("REGISTRY_PARTNER_API_MASTER_DATA_DB_PORT")
        or "5432"
    )
    _md_name = (
        os.environ.get("REGISTRY_STAFF_PORTAL_API_MASTER_DATA_DB_DBNAME")
        or os.environ.get("REGISTRY_PARTNER_API_MASTER_DATA_DB_DBNAME")
        or os.environ.get("MASTER_DATA_DB")
        or "master_data"
    )
    _md_user = (
        os.environ.get("REGISTRY_STAFF_PORTAL_API_MASTER_DATA_DB_USERNAME")
        or os.environ.get("REGISTRY_PARTNER_API_MASTER_DATA_DB_USERNAME")
        or os.environ.get("MASTER_DATA_DB_USER")
        or "master_data_user"
    )
    _md_pass = (
        os.environ.get("REGISTRY_STAFF_PORTAL_API_MASTER_DATA_DB_PASSWORD")
        or os.environ.get("REGISTRY_PARTNER_API_MASTER_DATA_DB_PASSWORD")
        or os.environ.get("MASTER_DATA_DB_PASSWORD")
        or "master_data_pass"
    )
    _md_datasource = f"postgresql+asyncpg://{_md_user}:{_md_pass}@{_md_host}:{_md_port}/{_md_name}"

    _md_engine = create_async_engine(_md_datasource, pool_pre_ping=True, pool_recycle=1800)
    if core_engine._engines is None:
        core_engine._engines = {}
    core_engine._engines["db_engine_master_data"] = _md_engine

    _orig_get_engine = getattr(core_engine, "get_engine", None)
    if _orig_get_engine:
        def _safe_get_engine(name="db_engine_master_data"):
            if name == "db_engine_master_data":
                return _md_engine
            res = _orig_get_engine(name)
            if res is None or getattr(getattr(res, "url", None), "host", None) in ("localhost", "127.0.0.1", None):
                res = _get_registry_engine()
            return res
        core_engine.get_engine = _safe_get_engine
except Exception:
    pass

# Ensure JSONResponse safely serializes datetime objects without failing
try:
    import json
    import starlette.responses
    from fastapi.encoders import jsonable_encoder

    _orig_json_render = starlette.responses.JSONResponse.render

    def _safe_json_render(self, content):
        try:
            return _orig_json_render(self, content)
        except TypeError:
            return json.dumps(
                jsonable_encoder(content),
                ensure_ascii=False,
                allow_nan=False,
                indent=None,
                separators=(",", ":"),
            ).encode("utf-8")

    starlette.responses.JSONResponse.render = _safe_json_render
except Exception:
    pass

# Register G2PAttributeValueSpeciesConfig model
try:
    from openg2p_fastapi_common.models import BaseORMModel
    from sqlalchemy import Column, String, Boolean
    import openg2p_registry_core.models as core_models

    class G2PAttributeValueSpeciesConfig(BaseORMModel):
        __tablename__ = "g2p_attribute_value_species_configs"
        __table_args__ = {"extend_existing": True}
        value_id = Column(String, primary_key=True)
        requires_ear_tag = Column(Boolean, nullable=True)
        is_flock_species = Column(Boolean, nullable=True)

    core_models.G2PAttributeValueSpeciesConfig = G2PAttributeValueSpeciesConfig
except Exception:
    pass

# Bridge MinIO configuration for openg2p_registry_core
_minio_endpoint = (
    os.environ.get("REGISTRY_CELERY_WORKERS_MINIO_ENDPOINT")
    or os.environ.get("REGISTRY_PARTNER_API_MINIO_ENDPOINT")
    or os.environ.get("REGISTRY_STAFF_PORTAL_API_MINIO_ENDPOINT")
    or os.environ.get("REGISTRY_CORE_MINIO_ENDPOINT")
    or "minio:9000"
)
_minio_user = (
    os.environ.get("REGISTRY_CELERY_WORKERS_MINIO_ACCESS_KEY")
    or os.environ.get("REGISTRY_PARTNER_API_MINIO_ACCESS_KEY")
    or os.environ.get("REGISTRY_STAFF_PORTAL_API_MINIO_ACCESS_KEY")
    or os.environ.get("MINIO_ROOT_USER")
    or "admin"
)
_minio_pass = (
    os.environ.get("REGISTRY_CELERY_WORKERS_MINIO_SECRET_KEY")
    or os.environ.get("REGISTRY_PARTNER_API_MINIO_SECRET_KEY")
    or os.environ.get("REGISTRY_STAFF_PORTAL_API_MINIO_SECRET_KEY")
    or os.environ.get("MINIO_ROOT_PASSWORD")
    or "secret"
)
os.environ["REGISTRY_CORE_MINIO_ENDPOINT"] = _minio_endpoint
os.environ["REGISTRY_CORE_MINIO_ACCESS_KEY"] = _minio_user
os.environ["REGISTRY_CORE_MINIO_SECRET_KEY"] = _minio_pass
os.environ["REGISTRY_CORE_MINIO_SECURE"] = "false"

try:
    from openg2p_registry_core.helpers.document import document_factory
    from openg2p_registry_core.helpers.document.minio_client import MinioClient
    from openg2p_registry_core.helpers.document.document_handlers import DocumentHandler
    from openg2p_fastapi_common.component import component_registry

    def _make_minio_client():
        return MinioClient(
            endpoint=_minio_endpoint,
            access_key=_minio_user,
            secret_key=_minio_pass,
            secure=False,
        )

    document_factory._create_document_handler = _make_minio_client
    DocumentHandler.set_component(_make_minio_client())

    cr = component_registry.get()
    if cr:
        for i, c in enumerate(cr):
            if isinstance(c, DocumentHandler):
                cr[i] = _make_minio_client()
                break
except Exception:
    pass

try:
    from . import odk_ingest_hooks  # noqa: F401
except Exception as e:
    import traceback
    print(f"FAILED TO IMPORT odk_ingest_hooks: {e}", flush=True)
    traceback.print_exc()


