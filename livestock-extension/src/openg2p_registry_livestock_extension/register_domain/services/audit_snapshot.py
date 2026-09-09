"""Writes an immutable before/after snapshot to g2p_register_audit_logs on every
change-request approval (create/update/delete) — G2R-136's "Audit Logging"
requirement, mirroring g2p.livestock.audit.log. See G2PAuditLog's own docstring
for why this sits alongside, not instead of, the platform's register_history
tables: history versions the record, this records the actor and the diff.

Hooked in via pre_approve() — BEFORE approve_register()/approve_table() mutate
the register row — so "before" values come straight off the still-untouched row
in this same session, no history-table digging required. Self-contained inside
the livestock extension; no platform (openg2p-registry-core) changes needed.

Known limitation: user_role / ip_address / session_id are left blank. Neither
pre_approve() nor anything above it in the approval call chain carries the
acting user's HTTP request context down to this layer today — only
created_by / approved_by on the change request itself reach here. Populating
those three would mean threading request context from the controller down
through G2PRegisterChangeRequestService, which is a platform-level change
outside this extension's reach.
"""

import importlib
import json
import logging
from datetime import datetime

from openg2p_registry_core.models import (
    ChangeActionEnum,
    G2PRegisterChangeRequest,
    G2PRegisterChangeRequestPayload,
    G2PRegisterDefinition,
)
from sqlalchemy import select

_logger = logging.getLogger("g2p-audit-snapshot")

# Envelope/bookkeeping columns every register row carries — not something a
# user "changed", so never surfaced as a diffed field.
_ENVELOPE_FIELDS = {
    "internal_record_id", "functional_record_id", "link_internal_record_id",
    "link_foundational_id", "record_name", "record_image_document_id",
    "created_by", "created_at", "last_approved_at", "last_approved_by",
    "search_text", "record_status", "record_status_reason", "edit_action",
}

_ACTION_MAP = {
    ChangeActionEnum.ADD.value: "CREATE",
    ChangeActionEnum.UPDATE.value: "UPDATE",
    ChangeActionEnum.DELETE.value: "DELETE",
}


def _models_module():
    # Same "resolve through the extensions alias" reasoning as
    # domain_validation_utils._animal_models(): importing via a relative
    # "..models" here would load a second, independent copy of every model
    # class under a different sys.modules key and SQLAlchemy would refuse the
    # duplicate declarative Table registration.
    return importlib.import_module("openg2p_registry_extensions.register_domain.models")


async def _get_register_definition(section_register_id: str, session) -> G2PRegisterDefinition | None:
    return (
        await session.execute(
            select(G2PRegisterDefinition).where(
                G2PRegisterDefinition.register_id == section_register_id
            )
        )
    ).scalar()


async def _get_change_payload_rows(change_request_id: str, session) -> list[dict]:
    payload = (
        await session.execute(
            select(G2PRegisterChangeRequestPayload).where(
                G2PRegisterChangeRequestPayload.change_request_id == change_request_id
            )
        )
    ).scalar()
    if not payload or not payload.change_payload:
        return []
    return payload.change_payload


def _diff_fields(before: dict | None, after: dict, valid_columns: set[str]) -> dict:
    """Field-level diff, comparing as strings so e.g. a date object already on
    the row vs. an ISO date string just submitted from the form don't register
    as a false change.

    Restricted to `valid_columns` (the register table's own mapped columns) —
    a change_payload row can carry other widget-level bookkeeping alongside
    the real fields (completion-score inputs, a documents map, an image
    storage id staged for upload...) that never lands on the register row
    itself. Diffing those against a register row that never has them would
    show every one of them as a "before: null" change on every single save,
    which is noise, not something a user actually changed.
    """
    diff = {}
    for key, new_value in after.items():
        if key in _ENVELOPE_FIELDS or key not in valid_columns:
            continue
        old_value = (before or {}).get(key)
        old_s = None if old_value is None else str(old_value)
        new_s = None if new_value is None else str(new_value)
        if old_s != new_s:
            diff[key] = {"before": old_value, "after": new_value}
    return diff


async def write_audit_snapshot(change_request: G2PRegisterChangeRequest, session) -> None:
    register_definition = await _get_register_definition(change_request.section_register_id, session)
    if register_definition is None or register_definition.register_mnemonic == "AuditLog":
        return  # unknown section, or the audit log entity auditing itself — skip

    models = _models_module()
    register_class = getattr(models, f"G2PRegister{register_definition.register_mnemonic}", None)
    audit_log_class = getattr(models, "G2PRegisterAuditLog", None)
    if register_class is None or audit_log_class is None:
        _logger.warning(
            "Could not resolve register/audit-log class for mnemonic %s — skipping audit snapshot",
            register_definition.register_mnemonic,
        )
        return

    rows = await _get_change_payload_rows(change_request.change_request_id, session)
    if not rows:
        return

    valid_columns = set(register_class.__table__.columns.keys())
    actor = change_request.approved_by or change_request.created_by or "system"
    now = datetime.now()

    for row in rows:
        edit_action = row.get("edit_action", ChangeActionEnum.UPDATE.value)
        action_type = _ACTION_MAP.get(edit_action)
        if action_type is None:
            continue  # NO_CHANGE, or an action this snapshot doesn't cover

        record_id = row.get("internal_record_id") or change_request.internal_record_id
        existing = None
        if record_id:
            existing = (
                await session.execute(
                    select(register_class).where(register_class.internal_record_id == record_id)
                )
            ).scalar()
        before_dict = existing.to_dict() if existing else None

        if action_type == "DELETE":
            changes = {
                key: {"before": value, "after": None}
                for key, value in (before_dict or {}).items()
                if key not in _ENVELOPE_FIELDS and key in valid_columns and value is not None
            }
        else:
            changes = _diff_fields(before_dict, row, valid_columns)

        if not changes and action_type != "CREATE":
            continue  # nothing on this row actually changed

        session.add(
            audit_log_class(
                link_internal_record_id=change_request.internal_record_id,
                res_model=register_definition.register_mnemonic,
                action_type=action_type,
                user_name=actor,
                changes=json.dumps(
                    {
                        "internal_record_id": record_id,
                        "change_request_id": change_request.change_request_id,
                        "fields": changes,
                    },
                    default=str,
                ),
                event_timestamp=now,
                created_by=actor,
                created_at=now,
                last_approved_at=now,
                last_approved_by=actor,
            )
        )


class AuditSnapshotMixin:
    """Mix in alongside G2PRegisterDomainService on every entity's domain
    service EXCEPT AuditLog's own (that would have it audit itself). Order
    matters: put this mixin FIRST in the base list so its pre_approve wins the
    MRO and its super() call chains into G2PRegisterDomainService.pre_approve.
    """

    async def pre_approve(self, change_request, session):
        await write_audit_snapshot(change_request, session)
        await super().pre_approve(change_request, session)
