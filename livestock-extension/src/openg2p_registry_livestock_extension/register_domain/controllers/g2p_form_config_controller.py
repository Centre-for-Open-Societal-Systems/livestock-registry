"""Read-only endpoint the staff portal's livestock dialog overlay reads its
per-value configuration from.

Until registry-platform 1.1 the overlay took this from the attribute values
themselves: the livestock patches added ``requires_ear_tag`` /
``is_flock_species`` to a species value and ``interval_days`` to a vaccine
value. 1.2 reads the code lists from Master Data through the legacy
attributes API, which returns a value's code, label, parent and order only, so
the two livestock-specific facts come from here instead:

- species config, the LIVESTOCK_SPECIES value attributes in Master Data
  (requires_ear_tag / is_flock_species, set by the country pack)
- vaccine intervals, the approved Vaccine Schedule register (the same rows the
  server uses to fill next_due_date on save), else the VACCINE_TYPE value's
  interval_days attribute in Master Data

The portal reaches it through its own /api/attributes/values route
(docker/staff-ui/assets/patch-form-config-route.js adds the switch
``?livestock=form-config``), which POSTs a Master Data style envelope and
returns ``response_body.response_payload.attribute_values``. So the answer is
the platform envelope around Master Data style attribute values, one pseudo
value per fact:

    {"response_header": {"response_status": "SUCCESS", ...},
     "response_body": {"response_payload": {"attribute_values": [
        {"attribute_id": "LIVESTOCK_SPECIES_CONFIG", "value_id": "<species value id>",
         "requires_ear_tag": bool|null, "is_flock_species": bool|null},
        {"attribute_id": "VACCINE_INTERVAL_DAYS", "value_id": "<vaccine value id>",
         "interval_days": int}
    ]}}}

Same custom-controller pattern as G2PAnimalBulkImportController. Requires a
staff session (``@require_permissions({})``) and nothing more: the data is
configuration every staff user already sees in the form.
"""

import logging
from datetime import datetime, timezone

from fastapi import Request
from iam_core.user_auth.decorators import require_permissions
from openg2p_fastapi_common.context import dbengine
from openg2p_fastapi_common.controller import BaseController
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from ... import master_data_lists
from ..models.vaccine_schedule import G2PRegisterVaccineSchedule

_logger = logging.getLogger("g2p-livestock-form-config")


def _norm(value) -> str:
    return str(value or "").strip().upper()


class G2PLivestockFormConfigController(BaseController):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.router.tags += ["/livestock/form-config"]
        self.router.add_api_route("/livestock/form-config", self.form_config, methods=["GET", "POST"])

    @require_permissions({})
    async def form_config(self, request: Request) -> dict:
        species: dict[str, dict] = {}
        intervals: dict[str, int] = {}
        for value_id, value in (await master_data_lists.get_list("LIVESTOCK_SPECIES") or {}).items():
            attributes = value.get("attributes") or {}
            species[value_id] = {
                "requires_ear_tag": attributes.get("requires_ear_tag"),
                "is_flock_species": attributes.get("is_flock_species"),
            }

        session_maker = async_sessionmaker(dbengine.get(), expire_on_commit=False)
        async with session_maker() as session:
            schedules = (
                await session.execute(
                    select(
                        G2PRegisterVaccineSchedule.vaccine_name,
                        G2PRegisterVaccineSchedule.species,
                        G2PRegisterVaccineSchedule.interval_days,
                    ).where(G2PRegisterVaccineSchedule.is_active.is_not(False))
                )
            ).all()

        # The schedule register is keyed by bare codes (vaccine_name
        # "ANTHRAX_CATTLE", species "CATTLE") while the form saves value ids
        # (VACCINE_TYPE_ANTHRAX_CATTLE); the dialog looks the interval up by
        # value id, so both spellings are offered. Mirrors
        # G2PRegisterDomainServiceVaccination._populate_next_due_date.
        for name, _schedule_species, days in schedules:
            if days is None or not name:
                continue
            key = _norm(name)
            for candidate in (key, key.replace("VACCINE_TYPE_", "", 1), f"VACCINE_TYPE_{key.replace('VACCINE_TYPE_', '', 1)}"):
                intervals.setdefault(candidate, int(days))
        for value_id, value in (await master_data_lists.get_list("VACCINE_TYPE") or {}).items():
            days = (value.get("attributes") or {}).get("interval_days")
            if isinstance(days, int) and not isinstance(days, bool) and days > 0:
                intervals.setdefault(value_id, days)

        rows: list[dict] = [
            {"attribute_id": "LIVESTOCK_SPECIES_CONFIG", "value_id": value_id, **cfg}
            for value_id, cfg in sorted(species.items())
        ]
        rows += [
            {"attribute_id": "VACCINE_INTERVAL_DAYS", "value_id": value_id, "interval_days": days}
            for value_id, days in sorted(intervals.items())
        ]
        # The platform envelope the portal proxy expects: it rejects an ERROR
        # header and hands response_body to the route's response transform.
        return {
            "response_header": {
                "request_id": "",
                "response_status": "SUCCESS",
                "response_error_code": "",
                "response_error_message": "",
                "response_timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "response_body": {
                "pagination_response": None,
                "response_payload": {"attribute_values": rows},
            },
        }
