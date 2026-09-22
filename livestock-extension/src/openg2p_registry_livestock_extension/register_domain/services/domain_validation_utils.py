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


async def ear_tag_exists(ear_tag_id: str, application_reference: str | None = None) -> bool:
    """True if `ear_tag_id` names a real animal — already approved into the
    register, or drafted under an in-progress intake submission.

    With `application_reference` (the intake submission's reference, present on
    every row the platform has already saved) the check is SCOPED to that
    submission: the animal must be drafted in the same submission, or already
    approved from it. That is the Old System's rule (an event's animal is
    picked from the holding's own line_ids) and what keeps a typed ear tag
    from attaching an event to another farmer's animal. Without a reference
    (first save of a brand-new row) only global existence can be checked —
    the platform hands validate_domain_attributes this section's rows alone,
    with no submission context.
    """
    if is_blank(ear_tag_id):
        return False

    import importlib

    from openg2p_fastapi_common.context import dbengine
    from sqlalchemy import exists, select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    G2PRegisterAnimal, G2PIntakeFormAnimal = _animal_models()

    register_cond = G2PRegisterAnimal.ear_tag_id == ear_tag_id
    intake_cond = G2PIntakeFormAnimal.ear_tag_id == ear_tag_id
    if application_reference:
        # Intake rows carry the submission's reference directly. Register rows
        # do not, but they hang off the holding (link_internal_record_id), and
        # the holding keeps its internal_record_id from intake to register —
        # so "approved from this submission" = linked to this submission's
        # Livestock record.
        G2PIntakeFormLivestock = importlib.import_module(
            "openg2p_registry_extensions.register_domain.models"
        ).G2PIntakeFormLivestock
        holdings_of_submission = select(G2PIntakeFormLivestock.internal_record_id).where(
            G2PIntakeFormLivestock.application_reference == application_reference
        )
        register_cond = register_cond & G2PRegisterAnimal.link_internal_record_id.in_(holdings_of_submission)
        intake_cond = intake_cond & (G2PIntakeFormAnimal.application_reference == application_reference)

    session_maker = async_sessionmaker(dbengine.get(), expire_on_commit=False)
    async with session_maker() as session:
        in_register = (await session.execute(select(exists().where(register_cond)))).scalar()
        if in_register:
            return True
        in_intake = (await session.execute(select(exists().where(intake_cond)))).scalar()
        return bool(in_intake)

async def ear_tag_used_by_other_animal(
    ear_tag_id: str,
    species,
    breed,
    exclude_internal_record_ids: set[str] | None = None,
    exclude_application_references: set[str] | None = None,
) -> bool:
    """True if `ear_tag_id`, with this same species and breed, already
    belongs to a DIFFERENT animal — either already approved into the
    register, or drafted under some other in-progress intake submission.
    Mirrors the Old System's duplicate check ("same tag + same species +
    same breed already used"), which Gen2's Livestock Details section was
    missing entirely — see `_validate_no_duplicate_ear_tags` in
    G2PRegisterDomainServiceAnimal, the only caller.

    Scoped to the record being edited on BOTH tables:
    `exclude_internal_record_ids` should be every internal_record_id already
    present in the current save's own row list. This matters just as much
    for g2p_register_animals as for g2p_intake_form_animals — editing an
    already-approved animal's *other* fields (e.g. health_status) resubmits
    its unchanged ear_tag/species/breed, and without excluding its own
    internal_record_id that combination is always found "already registered"
    against itself, permanently blocking every edit to an approved animal
    that doesn't touch its ear tag. (Found via G2R-136 audit-log testing:
    editing Health Status on an already-approved animal raised
    "ear_tag_id ... is already registered to a different animal" even though
    nothing about the tag, species or breed had changed.)
    """
    if is_blank(ear_tag_id):
        return False

    from openg2p_fastapi_common.context import dbengine
    from sqlalchemy import and_, exists, select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    G2PRegisterAnimal, G2PIntakeFormAnimal = _animal_models()
    exclude_internal_record_ids = exclude_internal_record_ids or set()

    def _same_animal_key(model):
        conditions = [
            model.ear_tag_id == ear_tag_id,
            model.species == species,
            model.breed == breed,
        ]
        if exclude_internal_record_ids:
            conditions.append(model.internal_record_id.not_in(exclude_internal_record_ids))
        if exclude_application_references and hasattr(model, "application_reference"):
            # Rows of the submission being edited (intake table only — the
            # register table has no application_reference). The platform's
            # intake form resends already-saved dialog rows WITHOUT their
            # internal_record_id (edit_action ADD) when a draft is reopened,
            # so the id exclusion above cannot recognise them; every saved row
            # of a submission carries the same application_reference, which can.
            conditions.append(model.application_reference.not_in(exclude_application_references))
        return and_(*conditions)

    session_maker = async_sessionmaker(dbengine.get(), expire_on_commit=False)
    async with session_maker() as session:
        in_register = (
            await session.execute(select(exists().where(_same_animal_key(G2PRegisterAnimal))))
        ).scalar()
        if in_register:
            return True

        in_intake = (
            await session.execute(select(exists().where(_same_animal_key(G2PIntakeFormAnimal))))
        ).scalar()
        return bool(in_intake)

async def secondary_identifier_used_by_other_animal(
    secondary_identifier: str,
    species,
    breed,
    exclude_internal_record_ids: set[str] | None = None,
    exclude_application_references: set[str] | None = None,
) -> bool:
    """Same check as ear_tag_used_by_other_animal, for `secondary_identifier`
    — the leg band/wing tag/hive number an _EAR_TAG_EXEMPT_SPECIES animal
    (poultry, beehive; see G2PRegisterDomainServiceAnimal) identifies by
    instead of an ear tag. Kept as a separate function rather than a
    parameterized field name so each stays a straightforward, obviously
    correct mirror of the other — see that function's docstring for why the
    exclude_internal_record_ids scoping (and its ear-tag-only caveat) matter.
    """
    if is_blank(secondary_identifier):
        return False

    from openg2p_fastapi_common.context import dbengine
    from sqlalchemy import and_, exists, select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    G2PRegisterAnimal, G2PIntakeFormAnimal = _animal_models()
    exclude_internal_record_ids = exclude_internal_record_ids or set()

    def _same_animal_key(model):
        conditions = [
            model.secondary_identifier == secondary_identifier,
            model.species == species,
            model.breed == breed,
        ]
        if exclude_internal_record_ids:
            conditions.append(model.internal_record_id.not_in(exclude_internal_record_ids))
        if exclude_application_references and hasattr(model, "application_reference"):
            # Rows of the submission being edited (intake table only — the
            # register table has no application_reference). The platform's
            # intake form resends already-saved dialog rows WITHOUT their
            # internal_record_id (edit_action ADD) when a draft is reopened,
            # so the id exclusion above cannot recognise them; every saved row
            # of a submission carries the same application_reference, which can.
            conditions.append(model.application_reference.not_in(exclude_application_references))
        return and_(*conditions)

    session_maker = async_sessionmaker(dbengine.get(), expire_on_commit=False)
    async with session_maker() as session:
        in_register = (
            await session.execute(select(exists().where(_same_animal_key(G2PRegisterAnimal))))
        ).scalar()
        if in_register:
            return True

        in_intake = (
            await session.execute(select(exists().where(_same_animal_key(G2PIntakeFormAnimal))))
        ).scalar()
        return bool(in_intake)

def format_age(birth_date: date | None) -> str | None:
    """The Age display string for a date of birth ("2 years, 8 months"), the
    same way `g2p.livestock.registry.line._compute_age` did in the Odoo
    module. One implementation for the Animal row and for the event rows that
    copy the animal's age, so the two can never drift apart."""
    if birth_date is None:
        return None
    today = date.today()
    years = today.year - birth_date.year
    months = today.month - birth_date.month
    if today.day < birth_date.day:
        months -= 1
    if months < 0:
        years -= 1
        months += 12
    if years < 0:
        return None
    return f"{years} years, {months} months"


async def get_animal_species(ear_tag_id: str) -> str | None:
    """The species already recorded against ear_tag_id under Livestock
    Details, or None if the ear tag isn't known anywhere."""
    species, _ = await get_animal_species_and_birth_date(ear_tag_id)
    return species


async def get_animal_species_and_birth_date(ear_tag_id: str) -> tuple[str | None, date | None]:
    """The (species, date_of_birth) already recorded against ear_tag_id under
    Livestock Details, or (None, None) if the ear tag isn't known anywhere.
    Checks the approved register first (authoritative), then falls back to
    any in-progress intake draft.

    Same scoping caveat as ear_tag_exists: this is a global lookup by ear
    tag, not scoped to the farmer/record currently being edited.
    """
    if is_blank(ear_tag_id):
        return None, None

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
        for model in (G2PRegisterAnimal, G2PIntakeFormAnimal):
            row = (
                await session.execute(
                    select(model.species, model.date_of_birth)
                    .where(_has_species(model))
                    .order_by(model.created_at.desc())
                    .limit(1)
                )
            ).first()
            if row and row[0]:
                return row[0], parse_date(row[1])
        return None, None


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


async def get_species_config(species_value_id: str | None) -> tuple[bool, bool]:
    """(requires_ear_tag, is_flock_species) for a LIVESTOCK_SPECIES value —
    e.g. Poultry/Beehive vs. Cattle/Sheep/... — configurable per species from
    Configuration > Attributes > Species (an Edit Attribute Value's "Requires
    Ear Tag" / "Flock / Group Species" checkboxes), not a hardcoded species
    list in this codebase. Backed by G2PAttributeValueSpeciesConfig, a
    per-value side table (see core-patches/apply_patches.py Fix 4) the same
    way G2PAttributeValueSchedule already backs per-value vaccine scheduling
    — most species (and every non-species attribute value) never get a row
    there, which is why every field on it is nullable.

    Defaults to (True, False) — ear-tag-required, not a flock — whenever no
    row exists (species left blank, a species nobody has configured yet, or
    a brand-new species just added in Configuration). That default matches
    every species' actual behavior before this table existed, so an
    unconfigured species behaves exactly as before rather than silently
    losing its ear-tag requirement.
    """
    requires_ear_tag, is_flock_species = True, False
    if is_blank(species_value_id):
        return requires_ear_tag, is_flock_species

    from openg2p_fastapi_common.context import dbengine
    from openg2p_registry_core.models import G2PAttributeValueSpeciesConfig
    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_maker = async_sessionmaker(dbengine.get(), expire_on_commit=False)
    async with session_maker() as session:
        config = await session.get(G2PAttributeValueSpeciesConfig, species_value_id)
        if config is None:
            return requires_ear_tag, is_flock_species
        if config.requires_ear_tag is not None:
            requires_ear_tag = config.requires_ear_tag
        if config.is_flock_species is not None:
            is_flock_species = config.is_flock_species
        return requires_ear_tag, is_flock_species


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


# ─── Duplicate event checks (G2R-134) ────────────────────────────────────────
#
# The Old System refused to record the same event twice for one animal
# (`_check_duplicate_health_event` and friends in the Odoo module); Gen2 only
# had the ear-tag duplicate check above for the Animal section. The two
# helpers below give an event section the same two-layer check the Animal
# section already has: first within the rows of the current save, then
# against everything already in the register or drafted in any intake
# submission. What counts as "the same event" is decided by each section's
# own domain service, which passes the fields that must match. Used by the
# Health Event and Vaccination services here; the Vital Event (mortality /
# disease) and Breeding (21-day cycle) checks live in their own services
# with their own helpers.


def _event_models(register_mnemonic: str):
    """The (register, intake) model pair for an event section, e.g.
    "HealthEvent" -> (G2PRegisterHealthEvent, G2PIntakeFormHealthEvent).
    Imported through the "openg2p_registry_extensions" alias for the same
    reason _animal_models does: importing via "..models" would register a
    second copy of every table with SQLAlchemy.
    """
    import importlib

    models = importlib.import_module("openg2p_registry_extensions.register_domain.models")
    return (
        getattr(models, f"G2PRegister{register_mnemonic}"),
        getattr(models, f"G2PIntakeForm{register_mnemonic}"),
    )


def first_repeated_key(records: list[dict], key_of) -> tuple | None:
    """The first key that appears on more than one row of this save, or
    None. `key_of(record)` returns the tuple that identifies an event for
    duplicate purposes, or None to leave that row out (e.g. ear tag or date
    not filled in yet — required-field checks own those).
    """
    seen: set[tuple] = set()
    for record in records:
        key = key_of(record)
        if key is None:
            continue
        if key in seen:
            return key
        seen.add(key)
    return None


async def event_already_recorded(
    register_mnemonic: str,
    match: dict,
    exclude_internal_record_ids: set[str] | None = None,
    within_days: tuple | None = None,
    exclude_application_references: set[str] | None = None,
) -> bool:
    """True if an event with these same field values already exists for
    this section — approved into the register, or drafted under any intake
    submission.

    `match` maps column name -> value that must be equal (a None value
    matches IS NULL, so "no disease recorded" is a value in its own right,
    not a wildcard). `within_days=(column, date, days)` adds a date-window
    condition instead of an exact date, for rules like the Old System's
    "no second breeding event of the same type within 21 days".

    `exclude_internal_record_ids` must be every internal_record_id already
    present in the current save's own rows, for the same reason as in
    ear_tag_used_by_other_animal: editing an already-approved event
    resubmits its unchanged key fields, and without excluding its own row it
    would always be found "already recorded" against itself.

    `exclude_application_references` covers the case the id exclusion cannot:
    on a reopened draft the platform resends already-saved dialog rows
    WITHOUT their internal_record_id (edit_action ADD), so pass the
    submission's own application_reference(s) as well — every saved row of a
    submission carries it (intake table only; the register table has none).
    Same two-part exclusion as ear_tag_used_by_other_animal.
    """
    from datetime import timedelta

    from openg2p_fastapi_common.context import dbengine
    from sqlalchemy import and_, exists, select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    register_model, intake_model = _event_models(register_mnemonic)
    exclude_internal_record_ids = exclude_internal_record_ids or set()

    def _same_event(model):
        conditions = []
        for column, value in match.items():
            attribute = getattr(model, column)
            conditions.append(attribute.is_(None) if value is None else attribute == value)
        if within_days:
            column, on, days = within_days
            attribute = getattr(model, column)
            conditions.append(attribute.between(on - timedelta(days=days), on + timedelta(days=days)))
        if exclude_internal_record_ids:
            conditions.append(model.internal_record_id.not_in(exclude_internal_record_ids))
        if exclude_application_references and hasattr(model, "application_reference"):
            conditions.append(model.application_reference.not_in(exclude_application_references))
        return and_(*conditions)

    session_maker = async_sessionmaker(dbengine.get(), expire_on_commit=False)
    async with session_maker() as session:
        in_register = (
            await session.execute(select(exists().where(_same_event(register_model))))
        ).scalar()
        if in_register:
            return True

        in_intake = (
            await session.execute(select(exists().where(_same_event(intake_model))))
        ).scalar()
        return bool(in_intake)


def resolve_today_default(record: dict, field: str) -> None:
    """Replace the literal string "today" in a date field with today's date.

    The intake form gives some date widgets `"widget-data-default": "today"`
    (Animal registration_date, Vaccination vaccination_date). The platform's
    staff-ui resolves that token for what it displays, but if the user leaves
    the picker untouched the submitted value is the literal "today", which
    the database rejects ("invalid input for query argument ... 'today'") and
    the whole section save fails with UNEXPECTED_ERROR. Resolving it here on
    save keeps the default meaningful for the UI and for API clients alike.
    """
    value = record.get(field)
    if isinstance(value, str) and value.strip().lower() == "today":
        record[field] = date.today().isoformat()


async def attribute_value_parent(value_id) -> str | None:
    """parent_value_id of an attribute value (e.g. LIVESTOCK_BREED_BORAN ->
    LIVESTOCK_SPECIES_CATTLE, VACCINE_TYPE_ANTHRAX_CATTLE ->
    LIVESTOCK_SPECIES_CATTLE). None when the value is unknown or has no parent."""
    if is_blank(value_id):
        return None
    from openg2p_fastapi_common.context import dbengine
    from openg2p_registry_core.models.g2p_attributes import G2PAttributeValue
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_maker = async_sessionmaker(dbengine.get(), expire_on_commit=False)
    async with session_maker() as session:
        parent = (
            await session.execute(
                select(G2PAttributeValue.parent_value_id).where(
                    G2PAttributeValue.value_id == str(value_id).strip()
                )
            )
        ).scalar()
    return parent or None


async def validate_belongs_to_species(value_id, species, kind: str) -> None:
    """Reject a breed/vaccine whose catalogue parent is a DIFFERENT species
    than the one on the record. The dialogs show the full breed and vaccine
    lists on the official staff-ui (no species filter inside a pop-up), so
    this is what keeps a goat breed off a cattle record. A value without a
    parent in the catalogue is left alone."""
    if is_blank(value_id) or is_blank(species):
        return
    parent = await attribute_value_parent(value_id)
    if parent is None or parent == str(species).strip():
        return
    value_label = await humanize_attribute_value(value_id)
    parent_label = await humanize_attribute_value(parent)
    species_label = await humanize_attribute_value(species)
    validation_error(
        f"{kind} '{value_label}' belongs to species '{parent_label}', not '{species_label}'."
    )


def first_application_reference(records: list[dict]) -> str | None:
    """The submission reference shared by this save's already-saved rows, if
    any. Rows the platform has stored once carry `application_reference`
    (one per submission); brand-new rows don't. Used to scope ear-tag checks
    to the submission being edited."""
    for record in records:
        value = record.get("application_reference")
        if not is_blank(value):
            return str(value).strip()
    return None


def application_references_of(records: list[dict]) -> set[str]:
    return {
        str(record["application_reference"]).strip()
        for record in records
        if not is_blank(record.get("application_reference"))
    }


async def fill_species_and_age_from_animal(record: dict) -> None:
    """Copy the animal's species (when the row has none) and its current age
    onto an event row that names an ear tag.

    The event dialogs show Species and Age as read-only fields that the
    original ear-tag dropdown filled in from the selected Animal row; with
    the ear tag typed in as text on the official staff-ui nothing fills them,
    so species would fail the required-field check and age would stay blank
    in the section table and the register. Both values are derived from the
    animal, so filling them here is authoritative; validate_species_matches
    still rejects an explicit species mismatch. Age is always recomputed
    (it is a display value as of today, not independent input).
    """
    if is_blank(record.get("ear_tag_id")):
        return
    animal_species, birth_date = await get_animal_species_and_birth_date(str(record["ear_tag_id"]).strip())
    if animal_species and is_blank(record.get("species")):
        record["species"] = animal_species
    if birth_date is not None:
        record["age"] = format_age(birth_date)


async def get_animal_gender(ear_tag_id: str) -> str | None:
    """The gender already recorded against ear_tag_id under Livestock
    Details, or None if the ear tag isn't known anywhere or has no gender on
    file yet. Same lookup shape as get_animal_species_and_birth_date (register
    first, then any in-progress intake draft; same "same ear tag, different
    answer between calls" ordering guard) -- used by Breeding to reject
    logging a breeding event against a male animal (see
    G2PRegisterDomainServiceBreeding._validate_female_only).
    """
    if is_blank(ear_tag_id):
        return None

    from openg2p_fastapi_common.context import dbengine
    from sqlalchemy import and_, select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    G2PRegisterAnimal, G2PIntakeFormAnimal = _animal_models()

    def _has_gender(model):
        return and_(model.ear_tag_id == ear_tag_id, model.gender.is_not(None), model.gender != "")

    session_maker = async_sessionmaker(dbengine.get(), expire_on_commit=False)
    async with session_maker() as session:
        for model in (G2PRegisterAnimal, G2PIntakeFormAnimal):
            row = (
                await session.execute(
                    select(model.gender)
                    .where(_has_gender(model))
                    .order_by(model.created_at.desc())
                    .limit(1)
                )
            ).first()
            if row and row[0]:
                return row[0]
        return None


async def ensure_ear_tags_belong_to_submission(rows: list) -> None:
    """post_intake_upsert companion to ear_tag_exists(): the platform hands
    validate_domain_attributes a brand-new row with NO submission context, so
    that check can only be global there — a real ear tag from a *different*
    farmer's animals passes it. Right after the upsert the same rows are ORM
    objects carrying the submission's application_reference, so here the check
    can finally be scoped: every event row's animal must be drafted in, or
    already approved from, this very submission. Raising here returns 400 and
    rolls the section save back (the platform commits later)."""
    for row in rows:
        ear_tag_id = getattr(row, "ear_tag_id", None)
        reference = getattr(row, "application_reference", None)
        if is_blank(ear_tag_id) or is_blank(reference):
            continue
        if not await ear_tag_exists(str(ear_tag_id).strip(), application_reference=str(reference)):
            validation_error(
                f"Ear tag '{str(ear_tag_id).strip()}' is not an animal of this submission. "
                "Add the animal under Livestock Details first, or check the tag."
            )


def compose_farmer_name(first=None, middle=None, last=None) -> str | None:
    """The farmer's display name from the parts the form collects (First /
    Middle / Last Name), or None when all three are blank. farmer_name is the
    Farmer register's display name, a dedup field, and what the Livestock
    record mirrors, yet nothing composed it once the intake form stopped
    carrying a farmer_name field of its own."""
    parts = [str(p).strip() for p in (first, middle, last) if not is_blank(p)]
    return " ".join(parts) or None


async def sync_farmer_identity_to_livestock(session, application_reference, *, farmer=None, livestock_rows=None) -> int:
    """Mirror the farmer's identity (farmer_id, fayda_fan_id, farmer_name) from
    the submission's Farmer intake row onto its Livestock intake row(s),
    overwriting whatever they hold. Returns how many livestock rows changed.

    Overwrite, not fill-blank-only: on a reopened draft the operator may
    correct the Farmer ID / name in the Farmer section, and the Livestock row
    must follow or the engine scores the wrong farmer. That is safe because
    no section of the intake form edits these three fields on the Livestock
    row any more (the old "Farmer Details" section survives only on the
    register's view tab), and it matches the approval-time copy in
    G2PRegisterDomainServiceLivestock._sync_farmer_identity, which also
    overwrites unconditionally.

    Why: the deduplication engine scores only the main (Livestock) register —
    the Farmer section embedded in the Livestock intake form is never scored —
    and the Livestock dedup schema is farmer_id / fayda_fan_id / farmer_name /
    woreda. Until 2026-09-14 the intake form's "Farmer Details" section wrote
    those three fields onto the Livestock row; it was removed as redundant for
    the operator, after which the Livestock row carried only woreda at intake
    (score ~10 of a 55 threshold) and no duplicate was ever flagged until the
    identity was copied at approval. Doing that copy at intake restores the
    engine's input without bringing the section back.

    Called from post_intake_upsert of BOTH domain services, so the copy happens
    whichever section is saved first: the Farmer section (farmer row given,
    livestock rows looked up) or a Livestock-register section (livestock rows
    given, farmer row looked up). Runs inside the section-save transaction.
    """
    import importlib

    from sqlalchemy import select

    if is_blank(application_reference):
        return 0
    models = importlib.import_module("openg2p_registry_extensions.register_domain.models")
    Farmer, Livestock = models.G2PIntakeFormFarmer, models.G2PIntakeFormLivestock
    if farmer is None:
        farmer = (
            await session.execute(select(Farmer).where(Farmer.application_reference == application_reference))
        ).scalars().first()
    if farmer is None:
        return 0
    if livestock_rows is None:
        livestock_rows = (
            await session.execute(select(Livestock).where(Livestock.application_reference == application_reference))
        ).scalars().all()
    full_name = farmer.farmer_name
    if is_blank(full_name):
        full_name = compose_farmer_name(farmer.first_name, farmer.middle_name, farmer.last_name)
    changed = 0
    for row in livestock_rows:
        touched = False
        for field, value in (("farmer_id", farmer.farmer_id), ("fayda_fan_id", farmer.fayda_fan_id), ("farmer_name", full_name)):
            new = None if is_blank(value) else str(value).strip()
            current = getattr(row, field, None)
            current = None if is_blank(current) else str(current).strip()
            if current != new:
                setattr(row, field, new)
                touched = True
        changed += int(touched)
    if changed:
        await session.flush()
    return changed
