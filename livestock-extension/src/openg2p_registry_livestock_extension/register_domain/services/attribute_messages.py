"""Words around the platform's code-list validator; its rules stay in core.

When a request carries a code that is not on its Master Data list (a stale
form value, ODK or file import), core says
"record 0: species='DOG' is not a value of LIVESTOCK_SPECIES (permitted: ...)".
That names a record number, a database field, a list id and codes. It is
reworded here to "Species: choose a species from the list (Cattle, Goats, ...)."
with the labels Master Data shows, for every coded field.
"""

import re

MAX_LISTED = 10
DEFAULT_TEXT = "{label}: choose {noun} from the list ({choices})."

# field -> (label as the form shows it, noun for "choose a ...")
FIELDS = {
    "species": ("Species", "a species"),
    "breed": ("Breed", "a breed"),
    "gender": ("Sex", "one"),
    "health_status": ("Health status", "one"),
    "vaccination_status": ("Vaccination status", "one"),
    "vaccine_type": ("Vaccine", "a vaccine"),
    "disease": ("Disease", "a disease"),
}

_PROBLEM = re.compile(
    r"""record \d+: (\w+)=('(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*") is not a value of (\S+) \(permitted: ([^)]*)\)"""
)


def _readable(code: str) -> str:
    from .plain_text import plain_code_text

    return plain_code_text(code)


def field_label(field: str) -> tuple[str, str]:
    label, noun = FIELDS.get(field, (None, None))
    if label:
        return label, noun
    text = field.replace("_", " ").strip()
    return text[:1].upper() + text[1:], "one"


def problems_in(message: str) -> list[re.Match]:
    return list(_PROBLEM.finditer(message or ""))


def choices_text(permitted: list[str], shown: dict[str, str]) -> str:
    """The labels of the permitted codes, in the list's own order when `shown`
    is ordered, else as given."""
    codes = [c for c in shown if c in permitted] or permitted
    names = [shown.get(code) or _readable(code) for code in codes]
    text = ", ".join(names[:MAX_LISTED])
    if len(names) > MAX_LISTED:
        text += f" and {len(names) - MAX_LISTED} more"
    return text


def reword(message: str, lists: dict[str, dict[str, str]], messages: dict | None = None) -> str:
    """`message` with each code-list problem in plain words. `lists` maps a
    Master Data list id to {code: label} in display order. Text that is not a
    code-list problem is kept as it is."""
    template = (messages or {}).get("livestock_code_choice")
    template = template if isinstance(template, str) and template else DEFAULT_TEXT
    out, end = [], 0
    for match in problems_in(message):
        field, _value, attribute, permitted = match.groups()
        out.append(message[end:match.start()])
        label, noun = field_label(field)
        codes = [c.strip() for c in permitted.split(",") if c.strip()]
        try:
            out.append(template.format(label=label, noun=noun, choices=choices_text(codes, lists.get(attribute, {}))))
        except (IndexError, KeyError, ValueError):
            out.append(DEFAULT_TEXT.format(label=label, noun=noun, choices=choices_text(codes, lists.get(attribute, {}))))
        end = match.end()
    out.append(message[end:])
    return " ".join(part for part in (p.strip(" ;") for p in out) if part)


async def _lists_for(message: str) -> dict[str, dict[str, str]]:
    from ... import master_data_lists

    lists = {}
    for match in problems_in(message):
        attribute = match.group(3)
        if attribute in lists:
            continue
        rows = await master_data_lists.get_values(attribute)
        lists[attribute] = {
            str(r.get("value_id") or r.get("value_code")): str(r.get("value_display") or "")
            for r in rows
            if r.get("value_display")
        }
    return lists


def install_attribute_messages():
    from openg2p_fastapi_common.context import component_registry
    from openg2p_registry_core.errors import G2PRegistryErrorCodes, G2PRegistryException
    from openg2p_registry_core.services.g2p_attribute_value_validator import (
        G2PAttributeValueValidator,
    )

    class AttributeValueValidator(G2PAttributeValueValidator):
        async def validate_records(self, records, *, field_map=None):
            try:
                return await super().validate_records(records, field_map=field_map)
            except G2PRegistryException as error:
                if error.code != G2PRegistryErrorCodes.REQUEST_VALIDATION_ERROR.value[1]:
                    raise
                text = error.message or ""
                if not problems_in(text):
                    raise
                from .field_rules import _translations

                reworded = reword(text, await _lists_for(text), await _translations())
                raise G2PRegistryException(code=error.code, message=reworded) from error

    core = G2PAttributeValueValidator.get_component()
    if core is not None and getattr(core, "livestock_messages", False):
        return core
    service = AttributeValueValidator()
    service.livestock_messages = True
    component_registry.remove(service)
    first = next(
        (i for i, c in enumerate(component_registry) if isinstance(c, G2PAttributeValueValidator)),
        len(component_registry),
    )
    component_registry.insert(first, service)
    return service
