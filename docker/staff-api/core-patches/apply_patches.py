"""Applies our fixes to the base image's installed openg2p_registry_core at
build time — NOT a wholesale file replacement, which is unsafe here: this
image's registry-platform lineage has drifted from our local checkout of that
repo in places unrelated to these fixes (e.g. it lacks G2PAttributeValueRole,
uses a different data-policy service name), so overwriting whole files can
delete code this base image actually needs and crash the app on import. Every
patch below finds an exact, small, known-good substring already proven to
match this image's real file content and swaps in the minimal fix — the same
technique validated by hand against the running container before this was
baked into the Dockerfile, now applied automatically on every build so it
survives rebuilds instead of being silently lost.

Run at Docker build time only (see docker/staff-api/Dockerfile).
"""

BASE = "/usr/local/lib/python3.12/site-packages/openg2p_registry_core"


def apply(path, old, new, label):
    with open(path) as f:
        content = f.read()
    n = content.count(old)
    assert n == 1, f"{label}: expected 1 match in {path}, found {n}"
    content = content.replace(old, new)
    with open(path, "w") as f:
        f.write(content)
    print(f"OK: {label}")


# ─── Fix 1: allow a hierarchical attribute value's parent to come from a
# DIFFERENT attribute (e.g. a Breed's parent is a Species value, not another
# Breed) — the original check wrongly required the same attribute_id.
apply(
    f"{BASE}/services/g2p_attribute_service.py",
    '''        parent = await session.get(G2PAttributeValue, parent_value_id)
        if not parent or parent.attribute_id != attribute_id:
            self._raise_validation_error(
                f"parent_value_id '{parent_value_id}' was not found for attribute '{attribute_id}'"
            )''',
    '''        parent = await session.get(G2PAttributeValue, parent_value_id)
        if not parent:
            self._raise_validation_error(
                f"parent_value_id '{parent_value_id}' was not found"
            )''',
    "validate_parent_value: allow cross-attribute parent",
)

# ─── Fix 2: optional per-value scheduling metadata (Interval/Active/Notes),
# e.g. how many days between doses for a Vaccine attribute value.
apply(
    f"{BASE}/models/g2p_attributes.py",
    '''    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)''',
    '''    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class G2PAttributeValueSchedule(BaseORMModel):
    __tablename__ = "g2p_attribute_value_schedules"

    value_id: Mapped[str] = mapped_column(String, primary_key=True)
    interval_days: Mapped[int] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=True)
    notes: Mapped[str] = mapped_column(String, nullable=True)''',
    "models/g2p_attributes.py: add G2PAttributeValueSchedule",
)

with open(f"{BASE}/models/__init__.py") as f:
    _models_init = f.read()
if "G2PAttributeValueRole" in _models_init:
    apply(
        f"{BASE}/models/__init__.py",
        "from .g2p_attributes import G2PAttribute, G2PAttributeValue, G2PAttributeValueRole",
        "from .g2p_attributes import G2PAttribute, G2PAttributeValue, G2PAttributeValueRole, G2PAttributeValueSchedule",
        "models/__init__.py: import (with Role)",
    )
else:
    apply(
        f"{BASE}/models/__init__.py",
        "from .g2p_attributes import G2PAttribute, G2PAttributeValue",
        "from .g2p_attributes import G2PAttribute, G2PAttributeValue, G2PAttributeValueSchedule",
        "models/__init__.py: import (without Role)",
    )

apply(
    f"{BASE}/schemas/register_payload.py",
    '''class AttributeValueData(BaseModel):
    value_id: str
    attribute_id: str
    value_code: str
    value_display: str
    parent_value_id: Optional[str] = None
    sort_order: int''',
    '''class AttributeValueData(BaseModel):
    value_id: str
    attribute_id: str
    value_code: str
    value_display: str
    parent_value_id: Optional[str] = None
    sort_order: int
    interval_days: Optional[int] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None''',
    "register_payload.py: AttributeValueData",
)
apply(
    f"{BASE}/schemas/register_payload.py",
    '''class CreateAttributeValueRequestPayload(BaseModel):
    attribute_id: str
    value_code: str
    value_display: str
    parent_value_id: Optional[str] = None
    sort_order: int = 0''',
    '''class CreateAttributeValueRequestPayload(BaseModel):
    attribute_id: str
    value_code: str
    value_display: str
    parent_value_id: Optional[str] = None
    sort_order: int = 0
    interval_days: Optional[int] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None''',
    "register_payload.py: CreateAttributeValueRequestPayload",
)
apply(
    f"{BASE}/schemas/register_payload.py",
    '''class UpdateAttributeValueRequestPayload(BaseModel):
    value_id: str
    value_code: Optional[str] = None
    value_display: Optional[str] = None
    parent_value_id: Optional[str] = None
    sort_order: Optional[int] = None''',
    '''class UpdateAttributeValueRequestPayload(BaseModel):
    value_id: str
    value_code: Optional[str] = None
    value_display: Optional[str] = None
    parent_value_id: Optional[str] = None
    sort_order: Optional[int] = None
    interval_days: Optional[int] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None''',
    "register_payload.py: UpdateAttributeValueRequestPayload",
)

apply(
    f"{BASE}/controller_services/attribute_controller_service.py",
    '''            attribute_value = await g2p_attribute_service.create_attribute_value(
                attribute_id=payload.attribute_id,
                value_code=payload.value_code,
                value_display=payload.value_display,
                parent_value_id=payload.parent_value_id,
                sort_order=payload.sort_order,
                session=session,
            )''',
    '''            attribute_value = await g2p_attribute_service.create_attribute_value(
                attribute_id=payload.attribute_id,
                value_code=payload.value_code,
                value_display=payload.value_display,
                parent_value_id=payload.parent_value_id,
                sort_order=payload.sort_order,
                interval_days=payload.interval_days,
                is_active=payload.is_active,
                notes=payload.notes,
                session=session,
            )''',
    "attribute_controller_service.py: create call",
)
apply(
    f"{BASE}/controller_services/attribute_controller_service.py",
    '''            attribute_value = await g2p_attribute_service.update_attribute_value(
                value_id=payload.value_id,
                value_code=payload.value_code,
                value_display=payload.value_display,
                parent_value_id=payload.parent_value_id,
                sort_order=payload.sort_order,
                session=session,
            )''',
    '''            attribute_value = await g2p_attribute_service.update_attribute_value(
                value_id=payload.value_id,
                value_code=payload.value_code,
                value_display=payload.value_display,
                parent_value_id=payload.parent_value_id,
                sort_order=payload.sort_order,
                interval_days=payload.interval_days,
                is_active=payload.is_active,
                notes=payload.notes,
                session=session,
            )''',
    "attribute_controller_service.py: update call",
)

with open(f"{BASE}/services/g2p_attribute_service.py") as f:
    _svc = f.read()
if "G2PAttributeValueRole" in _svc.split("\n")[11]:
    apply(
        f"{BASE}/services/g2p_attribute_service.py",
        "from ..models import G2PAttribute, G2PAttributeValue, G2PAttributeValueRole",
        "from ..models import G2PAttribute, G2PAttributeValue, G2PAttributeValueRole, G2PAttributeValueSchedule",
        "g2p_attribute_service.py: import (with Role)",
    )
else:
    apply(
        f"{BASE}/services/g2p_attribute_service.py",
        "from ..models import G2PAttribute, G2PAttributeValue",
        "from ..models import G2PAttribute, G2PAttributeValue, G2PAttributeValueSchedule",
        "g2p_attribute_service.py: import (without Role)",
    )

apply(
    f"{BASE}/services/g2p_attribute_service.py",
    '''            return [self._value_to_data(value) for value in result.scalars().all()], total''',
    '''            values = result.scalars().all()
            schedules = await self._get_schedules_by_value_ids(
                db_session, [v.value_id for v in values]
            )
            return [
                self._value_to_data(value, schedules.get(value.value_id))
                for value in values
            ], total''',
    "g2p_attribute_service.py: get_attribute_values return",
)

apply(
    f"{BASE}/services/g2p_attribute_service.py",
    '''    async def create_attribute_value(
        self,
        *,
        attribute_id: str,
        value_code: str,
        value_display: str,
        parent_value_id: Optional[str],
        sort_order: int,
        session: AsyncSession,
    ) -> AttributeValueData:''',
    '''    async def create_attribute_value(
        self,
        *,
        attribute_id: str,
        value_code: str,
        value_display: str,
        parent_value_id: Optional[str],
        sort_order: int,
        session: AsyncSession,
        interval_days: Optional[int] = None,
        is_active: Optional[bool] = None,
        notes: Optional[str] = None,
    ) -> AttributeValueData:''',
    "g2p_attribute_service.py: create_attribute_value signature",
)

apply(
    f"{BASE}/services/g2p_attribute_service.py",
    '''        session.add(value)
        await session.flush()
        await self._clear_attribute_cache()
        return self._value_to_data(value)

    async def update_attribute_value(
        self,
        *,
        value_id: str,
        value_code: Optional[str],
        value_display: Optional[str],
        parent_value_id: Optional[str],
        sort_order: Optional[int],
        session: AsyncSession,
    ) -> AttributeValueData:
        value = await session.get(G2PAttributeValue, value_id)
        if not value:
            self._raise_attribute_value_not_found(value_id)

        if all(field is None for field in (value_code, value_display, parent_value_id, sort_order)):
            self._raise_validation_error("At least one field must be provided to update")''',
    '''        session.add(value)

        schedule = await self._upsert_schedule(
            session,
            value_id=value.value_id,
            interval_days=interval_days,
            is_active=is_active,
            notes=notes,
        )

        await session.flush()
        await self._clear_attribute_cache()
        return self._value_to_data(value, schedule)

    async def update_attribute_value(
        self,
        *,
        value_id: str,
        value_code: Optional[str],
        value_display: Optional[str],
        parent_value_id: Optional[str],
        sort_order: Optional[int],
        session: AsyncSession,
        interval_days: Optional[int] = None,
        is_active: Optional[bool] = None,
        notes: Optional[str] = None,
    ) -> AttributeValueData:
        value = await session.get(G2PAttributeValue, value_id)
        if not value:
            self._raise_attribute_value_not_found(value_id)

        if all(
            field is None
            for field in (
                value_code, value_display, parent_value_id, sort_order,
                interval_days, is_active, notes,
            )
        ):
            self._raise_validation_error("At least one field must be provided to update")''',
    "g2p_attribute_service.py: create tail + update_attribute_value head",
)

apply(
    f"{BASE}/services/g2p_attribute_service.py",
    '''        session.add(value)
        await session.flush()
        await self._clear_attribute_cache()
        return self._value_to_data(value)

    async def delete_attribute_value(self, value_id: str, session: AsyncSession) -> str:
        value = await session.get(G2PAttributeValue, value_id)
        if not value:
            self._raise_attribute_value_not_found(value_id)

        if await self._child_value_count(session, value_id) > 0:
            raise G2PRegistryException(
                code=G2PRegistryErrorCodes.ATTRIBUTE_VALUE_HAS_CHILDREN.value[1],
                message=f"Cannot delete attribute value '{value_id}' while child values exist",
            )

        await session.delete(value)
        await session.flush()
        await self._clear_attribute_cache()
        return value_id''',
    '''        session.add(value)

        schedule = await self._upsert_schedule(
            session,
            value_id=value_id,
            interval_days=interval_days,
            is_active=is_active,
            notes=notes,
        )

        await session.flush()
        await self._clear_attribute_cache()
        return self._value_to_data(value, schedule)

    async def delete_attribute_value(self, value_id: str, session: AsyncSession) -> str:
        value = await session.get(G2PAttributeValue, value_id)
        if not value:
            self._raise_attribute_value_not_found(value_id)

        if await self._child_value_count(session, value_id) > 0:
            raise G2PRegistryException(
                code=G2PRegistryErrorCodes.ATTRIBUTE_VALUE_HAS_CHILDREN.value[1],
                message=f"Cannot delete attribute value '{value_id}' while child values exist",
            )

        schedule = await session.get(G2PAttributeValueSchedule, value_id)
        if schedule:
            await session.delete(schedule)

        await session.delete(value)
        await session.flush()
        await self._clear_attribute_cache()
        return value_id''',
    "g2p_attribute_service.py: update tail + delete_attribute_value",
)

apply(
    f"{BASE}/services/g2p_attribute_service.py",
    '''    def _value_to_data(self, value: G2PAttributeValue) -> AttributeValueData:
        return AttributeValueData(
            value_id=value.value_id,
            attribute_id=value.attribute_id,
            value_code=value.value_code,
            value_display=value.value_display,
            parent_value_id=value.parent_value_id,''',
    '''    async def _upsert_schedule(
        self,
        session: AsyncSession,
        *,
        value_id: str,
        interval_days: Optional[int],
        is_active: Optional[bool],
        notes: Optional[str],
    ) -> Optional["G2PAttributeValueSchedule"]:
        if interval_days is None and is_active is None and notes is None:
            return await session.get(G2PAttributeValueSchedule, value_id)

        schedule = await session.get(G2PAttributeValueSchedule, value_id)
        if not schedule:
            schedule = G2PAttributeValueSchedule(value_id=value_id)

        if interval_days is not None:
            schedule.interval_days = interval_days
        if is_active is not None:
            schedule.is_active = is_active
        if notes is not None:
            schedule.notes = notes

        session.add(schedule)
        return schedule

    async def _get_schedules_by_value_ids(self, session: AsyncSession, value_ids):
        if not value_ids:
            return {}
        query = select(G2PAttributeValueSchedule).where(
            G2PAttributeValueSchedule.value_id.in_(value_ids)
        )
        result = await session.execute(query)
        return {row.value_id: row for row in result.scalars().all()}

    def _value_to_data(self, value: G2PAttributeValue, schedule=None) -> AttributeValueData:
        return AttributeValueData(
            value_id=value.value_id,
            attribute_id=value.attribute_id,
            value_code=value.value_code,
            value_display=value.value_display,
            parent_value_id=value.parent_value_id,
            interval_days=schedule.interval_days if schedule else None,
            is_active=schedule.is_active if schedule else None,
            notes=schedule.notes if schedule else None,''',
    "g2p_attribute_service.py: _value_to_data + new helpers",
)

print("ALL PATCHES APPLIED")
