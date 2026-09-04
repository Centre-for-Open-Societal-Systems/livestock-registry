from datetime import date, datetime

from openg2p_registry_core.errors import G2PRegistryErrorCodes, G2PRegistryException


def validation_error(message: str) -> None:
    raise G2PRegistryException(
        code=G2PRegistryErrorCodes.REQUEST_VALIDATION_ERROR.value[1],
        message=message,
    )


def parse_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            pass
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
    return None


def as_int(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def as_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_bool(value) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    return bool(value)


def is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0
    return False


def require_field(record: dict, field: str, label: str | None = None) -> None:
    """Reject the save outright if field is missing/blank. Enforced here
    server-side rather than only via "widget-required" in the form's JSON,
    since a required-but-empty field is something the backend can always
    catch reliably — unlike display quirks in the table-cell widgets, which
    this project found are not something we can trust the frontend to get
    right without source access to fix them.
    """
    if is_blank(record.get(field)):
        validation_error(f"{label or field} is required")


def _animal_models():
    """Import the animal models the same way the platform itself resolves
    the domain extension: through the "openg2p_registry_extensions" alias
    that main.py points at this package's real module in sys.modules
    (Option C), not through this package's own real dotted name.

    Importing via "..models" instead loads a second, independent copy of
    every model under a different sys.modules key — same source file, but a
    distinct module object — and SQLAlchemy then refuses the second
    declarative Table registration ("... is already defined for this
    MetaData instance"). Importing here, not at module load: only needed by
    the two DB-touching functions below, and doing it lazily avoids forcing
    load order relative to app startup.
    """
    import importlib

    models = importlib.import_module("openg2p_registry_extensions.register_domain.models")
    return models.G2PRegisterAnimal, models.G2PIntakeFormAnimal


async def ear_tag_exists(ear_tag_id: str) -> bool:
    """True if ear_tag_id belongs to a real animal — already approved into the
    register, or drafted under some in-progress intake submission.

    This is a global existence check only, NOT scoped to the farmer/record
    being edited: validate_domain_attributes (the caller) is only handed this
    section's own rows by the platform, with no link back to which
    submission or register record they belong to. So a real ear tag typed
    from a *different* farmer's animals will still pass. It still catches
    typos and made-up tags, which is the bulk of the risk a free-text field
    carries.
    """
    if is_blank(ear_tag_id):
        return False

    from openg2p_fastapi_common.context import dbengine
    from sqlalchemy import exists, select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    G2PRegisterAnimal, G2PIntakeFormAnimal = _animal_models()

    session_maker = async_sessionmaker(dbengine.get(), expire_on_commit=False)
    async with session_maker() as session:
        in_register = (
            await session.execute(select(exists().where(G2PRegisterAnimal.ear_tag_id == ear_tag_id)))
        ).scalar()
        if in_register:
            return True
        in_intake = (
            await session.execute(select(exists().where(G2PIntakeFormAnimal.ear_tag_id == ear_tag_id)))
        ).scalar()
        return bool(in_intake)


async def ear_tag_used_by_other_animal(
    ear_tag_id: str,
    species,
    breed,
    exclude_internal_record_ids: set[str] | None = None,
) -> bool:
    """True if `ear_tag_id`, with this same species and breed, already
    belongs to a DIFFERENT animal — either already approved into the
    register, or drafted under some other in-progress intake submission.
    Mirrors the Old System's duplicate check ("same tag + same species +
    same breed already used"), which Gen2's Livestock Details section was
    missing entirely — see `_validate_no_duplicate_ear_tags` in
    G2PRegisterDomainServiceAnimal, the only caller.

    Unlike `ear_tag_exists` above, this one IS scoped to the record being
    edited: `exclude_internal_record_ids` should be every internal_record_id
    already present in the current save's own row list, so re-saving an
    animal you already registered — its ear tag is already sitting in
    g2p_intake_form_animals from the previous save — doesn't look like a
    duplicate of itself. g2p_register_animals needs no such exclusion:
    intake forms only ever create new submissions, so a row being drafted
    here can't already be sitting in the approved register under the same
    internal_record_id.
    """
    if is_blank(ear_tag_id):
        return False

    from openg2p_fastapi_common.context import dbengine
    from sqlalchemy import and_, exists, select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    G2PRegisterAnimal, G2PIntakeFormAnimal = _animal_models()
    exclude_internal_record_ids = exclude_internal_record_ids or set()

    def _same_animal_key(model):
        return and_(
            model.ear_tag_id == ear_tag_id,
            model.species == species,
            model.breed == breed,
        )

    session_maker = async_sessionmaker(dbengine.get(), expire_on_commit=False)
    async with session_maker() as session:
        in_register = (
            await session.execute(select(exists().where(_same_animal_key(G2PRegisterAnimal))))
        ).scalar()
        if in_register:
            return True

        matching_intake_ids = (
            await session.execute(
                select(G2PIntakeFormAnimal.internal_record_id).where(_same_animal_key(G2PIntakeFormAnimal))
            )
        ).scalars().all()
        return any(
            str(record_id) not in exclude_internal_record_ids for record_id in matching_intake_ids
        )


async def get_animal_species(ear_tag_id: str) -> str | None:
    """The species already recorded against ear_tag_id under Livestock
    Details, or None if the ear tag isn't known anywhere. Checks the
    approved register first (authoritative), then falls back to any
    in-progress intake draft.

    Same scoping caveat as ear_tag_exists: this is a global lookup by ear
    tag, not scoped to the farmer/record currently being edited.
    """
    if is_blank(ear_tag_id):
        return None

    from openg2p_fastapi_common.context import dbengine
    from sqlalchemy import and_, select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    G2PRegisterAnimal, G2PIntakeFormAnimal = _animal_models()

    def _has_species(model):
        # Excluded in the WHERE clause, not just checked after fetching: the
        # same ear tag can legitimately appear on more than one row (repeat
        # test submissions, a farmer's animal re-entered in a later intake),
        # and without this an unordered .limit(1) can just as easily land on
        # a row where species was never filled in, making the result
        # nondeterministic — same ear tag, different answer between calls.
        return and_(model.ear_tag_id == ear_tag_id, model.species.is_not(None), model.species != "")

    session_maker = async_sessionmaker(dbengine.get(), expire_on_commit=False)
    async with session_maker() as session:
        species = (
            await session.execute(
                select(G2PRegisterAnimal.species)
                .where(_has_species(G2PRegisterAnimal))
                .order_by(G2PRegisterAnimal.created_at.desc())
                .limit(1)
            )
        ).scalar()
        if species:
            return species
        species = (
            await session.execute(
                select(G2PIntakeFormAnimal.species)
                .where(_has_species(G2PIntakeFormAnimal))
                .order_by(G2PIntakeFormAnimal.created_at.desc())
                .limit(1)
            )
        ).scalar()
        return species


async def humanize_attribute_value(value_id: str | None) -> str:
    """The human-readable label for an attribute value id (e.g.
    "LIVESTOCK_SPECIES_SHEEP" -> "Sheep"), for building a validation message
    a user can actually act on. Falls back to the raw id if it isn't a known
    attribute value (or is blank) — validation error text should never go
    silent just because a lookup came up empty.
    """
    if is_blank(value_id):
        return str(value_id)

    from openg2p_fastapi_common.context import dbengine
    from openg2p_registry_core.models import G2PAttributeValue
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_maker = async_sessionmaker(dbengine.get(), expire_on_commit=False)
    async with session_maker() as session:
        display = (
            await session.execute(
                select(G2PAttributeValue.value_display).where(G2PAttributeValue.value_id == value_id)
            )
        ).scalar()
        return display or value_id


async def validate_species_matches(record: dict) -> None:
    """If both ear_tag_id and species are filled in on this record, species
    must match what's already recorded for that ear tag under Livestock
    Details. Either one left blank is skipped, not rejected — this only
    catches a genuine mismatch, not an incomplete row (other validators
    handle required-field checks).
    """
    ear_tag_id = record.get("ear_tag_id")
    species = record.get("species")
    if is_blank(ear_tag_id) or is_blank(species):
        return

    animal_species = await get_animal_species(str(ear_tag_id).strip())
    if animal_species is None:
        # Nothing recorded to compare against (e.g. species was never filled
        # in under Livestock Details for this animal) — ear_tag_exists
        # already rejects an ear tag that isn't real at all, so this is not
        # this check's job to also flag.
        return

    if str(species).strip() != animal_species:
        entered_label = await humanize_attribute_value(species)
        actual_label = await humanize_attribute_value(animal_species)
        validation_error(
            f"species '{entered_label}' does not match ear tag '{ear_tag_id}', "
            f"which is recorded as '{actual_label}' under Livestock Details. "
            "Select the matching species, or check you entered the correct ear tag."
        )
