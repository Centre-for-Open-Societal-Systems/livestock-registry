"""Show the saved Fayda ID in the Farmer lookup section, and keep it on re-save.

The Farmer lookup section has one box, `fayda_id`, but the intake tables store
the value in two columns: fayda_fin (12 digits) or fayda_fan_id (16 digits).
Saving splits the typed value into those columns (field_rules.split_fayda_id).
The platform builds the records it returns from the table columns only, so a
saved intake opened again had an empty box although the value was stored.

This mixin closes both directions on the intake service without touching the
platform:

- read: every section record that carries fayda_fin or fayda_fan_id also
  carries `fayda_id` (the FIN, else the FAN). It is added to the response
  only; the rows, the stored-row serializer and the approval path never see it.
- save: a blank `fayda_id` posted for a record that already has a stored FIN
  or FAN (in the database, or still carried by the posted record itself) is an
  unchanged box, not a clearing. The blank key is dropped so the stored value
  stays and the "Fayda ID required" check is not raised for it. A record with
  nothing stored keeps the blank value and is refused as before, and a typed
  value, different or not, is split and stored as before.

Put it first in the intake service's bases.
"""

_STORED = ("fayda_fin", "fayda_fan_id")


def _blank(value):
    return value is None or (isinstance(value, str) and not value.strip())


def stored_fayda_id(record):
    """The saved Fayda ID of a record: the FIN, else the FAN, else None."""
    for field in _STORED:
        value = record.get(field)
        if not _blank(value):
            return value.strip() if isinstance(value, str) else value
    return None


def add_fayda_id(items):
    """Add `fayda_id` to the records of section payload items that store a FIN or FAN."""
    for item in items or []:
        for record in item.records:
            if isinstance(record, dict) and any(field in record for field in _STORED):
                record["fayda_id"] = stored_fayda_id(record)
    return items


class FaydaIdMixin:
    async def _build_section_payloads(self, submission, session):
        return add_fayda_id(await super()._build_section_payloads(submission, session))

    async def get_tab_records(self, submission_id, tab_id, data_policies=None):
        return add_fayda_id(await super().get_tab_records(submission_id, tab_id, data_policies))

    async def save_intake_form_submission_with_session(
        self, submission_id, section_id, section_payload, section_register_id,
        form_id, register_id, created_by, session, documents=None,
    ):
        await self._keep_stored_fayda_id(submission_id, section_payload, section_register_id, session)
        return await super().save_intake_form_submission_with_session(
            submission_id, section_id, section_payload, section_register_id,
            form_id, register_id, created_by, session, documents=documents)

    async def _keep_stored_fayda_id(self, submission_id, section_payload, section_register_id, session):
        blanks = [
            (record, key)
            for record in section_payload or []
            if isinstance(record, dict) and record.get("edit_action") != "DELETE"
            for key in record
            if isinstance(key, str) and key.rsplit(".", 1)[-1] == "fayda_id" and _blank(record[key])
        ]
        if not blanks:
            return
        stored = None
        for record, key in blanks:
            prefix = key[: -len("fayda_id")]
            if stored_fayda_id({field: record.get(prefix + field) for field in _STORED}):
                record.pop(key)
                continue
            if stored is None:
                stored = await self._stored_fayda_ids(submission_id, section_register_id, session)
            known = stored.get(str(record.get("internal_record_id") or ""))
            if known is None and len(stored) == 1 and not record.get("internal_record_id"):
                known = next(iter(stored.values()))
            if known:
                record.pop(key)

    async def _stored_fayda_ids(self, submission_id, section_register_id, session):
        """Record id -> saved Fayda ID of the rows the submission stores for a register."""
        if not submission_id:
            return {}
        try:
            intake_class = await self._resolve_intake_form_class(section_register_id, session)
            if not all(hasattr(intake_class, field) for field in _STORED):
                return {}
            rows = await self._get_intake_rows(intake_class, str(submission_id), session)
        except Exception:  # noqa: BLE001 - an unknown submission is the platform's to report
            return {}
        return {
            str(record_id): stored_fayda_id({field: getattr(row, field) for field in _STORED})
            for record_id, row in rows.items()
        }
