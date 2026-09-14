"""HTTP endpoint for "upload a spreadsheet, system creates/updates matching
Animal records" — see animal_bulk_import_service.py for the actual parsing
and upsert logic; this file is only the thin HTTP wrapper around it.

A custom controller, not a core-patch: unlike the celery-beat scheduling
patches (which touch a base platform package with no domain-extension hook of
its own), openg2p_fastapi_common's BaseController + app_registry pattern is
already an extension point — instantiating and `.post_init()`-ing a
controller from OUR OWN app.py's Initializer works exactly the same way the
platform's own dozens of controllers register themselves (see
openg2p_registry_staff_api/app.py's Initializer.initialize() for the
identical pattern), so no core-patch is needed here at all.
"""

import logging
from datetime import datetime

from fastapi import File, Request, UploadFile
from openg2p_fastapi_common.context import dbengine
from openg2p_fastapi_common.controller import BaseController
from sqlalchemy.ext.asyncio import async_sessionmaker

from iam_core.user_auth.decorators import require_permissions

from ..services.animal_bulk_import_service import import_animals_from_csv

_logger = logging.getLogger("g2p-bulk-import")


def _envelope(payload: dict, error: str | None = None) -> dict:
    """The platform's standard G2PResponse envelope shape
    (response_header.response_status + response_body.response_payload) —
    staff-ui's proxyToBackend helper (app/api/_lib/backend-proxy.ts) reads
    exactly this shape from every backend response, so a plain dict return
    (without this wrapper) gets silently discarded there as "empty response".
    Hand-built here rather than via RequestResponseHelper's typed
    G2PResponse/G2PResponseBody models, which assume a typed G2PRequest body
    this file-upload endpoint doesn't have.
    """
    return {
        "response_header": {
            "request_id": "",
            "response_status": "ERROR" if error else "SUCCESS",
            "response_error_code": "BULK_IMPORT_ERROR" if error else "",
            "response_error_message": error or "",
            "response_timestamp": datetime.now().isoformat(),
        },
        "response_body": {"pagination_response": None, "response_payload": payload},
    }


class G2PAnimalBulkImportController(BaseController):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.router.tags += ["/livestock/animals"]
        self.router.prefix = "/livestock/animals"

        self.router.add_api_route(
            "/bulk-import",
            self.bulk_import,
            methods=["POST"],
        )

    # Empty permission set: any authenticated user can use this, same as
    # G2PDocumentController.upload_documents — the surrounding session/CSRF/
    # auth middleware (applied to the whole app, not per-route) still
    # requires a real logged-in session; this just adds no ADDITIONAL
    # permission check on top of that.
    @require_permissions({})
    async def bulk_import(self, request: Request, file: UploadFile = File(...)) -> dict:
        try:
            file_bytes = await file.read()
            actor = getattr(request.state.auth, "name", "Bulk Import") if hasattr(request.state, "auth") else "Bulk Import"

            session_maker = async_sessionmaker(dbengine.get(), expire_on_commit=False)
            async with session_maker() as session:
                result = await import_animals_from_csv(file_bytes, actor, session)
                await session.commit()
            return _envelope(result)
        except ValueError as error:
            # A malformed CSV (missing required columns etc.) — a well-formed
            # ERROR envelope, not a raw 500, for what is really a bad-input
            # problem.
            _logger.warning("Bulk animal import rejected: %s", error)
            return _envelope({}, error=str(error))
        except Exception as error:
            _logger.exception("Bulk animal import failed")
            return _envelope({}, error=str(error))
