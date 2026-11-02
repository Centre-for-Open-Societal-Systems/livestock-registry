"""Animal sex codes: the Master Data LIVESTOCK_SEX list (ETH-OAN pack, from the
National Livestock Data Standard for Ethiopia) plus SEX_MIXED for a flock or
hive row, which stands for a group rather than one sexed animal.

The registry stored MALE / FEMALE / MIXED before it read the list. Those codes
still arrive from ODK forms published earlier, Excel files filled from the old
template and drafts saved before the switch, so every path that reads a sex
turns them into the list's codes (sex_code) instead of refusing them.

Kept free of model imports for the reason given at _ANIMAL_SEX_VALUES in
g2p_register_domain_service_animal.py.
"""

SEX_MALE = "SEX_MALE"
SEX_FEMALE = "SEX_FEMALE"
SEX_MALE_NEUTER = "SEX_MALE_NEUTER"
SEX_FEMALE_NEUTER = "SEX_FEMALE_NEUTER"
SEX_MIXED = "SEX_MIXED"

ANIMAL_SEX_VALUES = frozenset({SEX_MALE, SEX_FEMALE, SEX_MALE_NEUTER, SEX_FEMALE_NEUTER, SEX_MIXED})
# A newborn is not neutered.
OFFSPRING_SEX_VALUES = frozenset({SEX_MALE, SEX_FEMALE, SEX_MIXED})

LEGACY_SEX_CODES = {"MALE": SEX_MALE, "FEMALE": SEX_FEMALE, "MIXED": SEX_MIXED}

SEX_LABELS = {
    SEX_MALE: "male",
    SEX_FEMALE: "female",
    SEX_MALE_NEUTER: "castrated male",
    SEX_FEMALE_NEUTER: "female neuter",
    SEX_MIXED: "mixed / not applicable",
}


def sex_code(value):
    """The LIVESTOCK_SEX code of a stored or submitted sex; blank stays None,
    an unknown value comes back upper-cased for the caller to refuse."""
    text = str(value or "").strip().upper()
    if not text:
        return None
    return LEGACY_SEX_CODES.get(text, text)


def normalize_sex(record: dict, field: str) -> None:
    """Rewrite record[field] to its LIVESTOCK_SEX code, in place."""
    if str(record.get(field) or "").strip():
        record[field] = sex_code(record[field])


def sex_label(value) -> str:
    code = sex_code(value)
    return SEX_LABELS.get(code, str(value or "").lower())
