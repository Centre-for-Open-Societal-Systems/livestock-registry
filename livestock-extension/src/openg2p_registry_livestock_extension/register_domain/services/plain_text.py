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
