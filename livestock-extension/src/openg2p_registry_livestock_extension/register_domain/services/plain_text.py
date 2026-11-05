"""Words for a stored code, for text people read (record names, messages).

Codes such as CATTLE, UP_TO_DATE or VACCINE_TYPE_BLACKLEG are what the registry
stores; staff read "Cattle", "Up to date" and "Blackleg". Where Master Data can
be asked, its label is used; this module is the fallback for synchronous code
that cannot ask, and for a code Master Data does not know.
"""

_LIST_PREFIXES = ("VACCINE_TYPE_", "LIVESTOCK_DISEASE_", "BREED_")


def plain_code_text(text) -> str:
    """"CATTLE" -> "Cattle", "UP_TO_DATE" -> "Up to date",
    "VACCINE_TYPE_BLACKLEG" -> "Blackleg". Text that is already words
    ("Foot and mouth disease") is returned as it is."""
    text = str(text if text is not None else "").strip()
    if not text or ("_" not in text and not text.isupper()):
        return text
    for prefix in _LIST_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    words = text.replace("_", " ").strip().lower()
    return words[:1].upper() + words[1:]


# Record-name fields that hold a code. Everything else in a record name is an
# identifier or a name (ear tag, batch reference, source system, vaccine name)
# and is shown exactly as stored: "ET0000000123" must not become "Et0000000123".
CODE_FIELDS = frozenset({"event_type", "vaccine_type", "species", "action_type"})


def name_part(key: str, value) -> str:
    """One part of a record name: words for a code field, the stored text otherwise."""
    if key in CODE_FIELDS:
        return plain_code_text(value)
    return str(value if value is not None else "").strip()
