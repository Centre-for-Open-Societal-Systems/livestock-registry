"""Guard: the DCI search response reads the child registers under the keys the platform attaches them by.

The platform loads a record's register tree and attaches each child register's rows as a list under the snake_case
of the child's register mnemonic (openg2p_registry_core search/hierarchy.py, snake_case; and
G2PRegisterHierarchicalService._to_snake_case): a holding's animals arrive under `animal`, its breeding events under
`breeding`, its health events under `health_event`. A template that reads any other key gets an empty list, and the
DCI response carries no animals or events, without an error.

templates/openg2p_livestock_to_dci.json.j2 is rendered here with a holding built the way the platform builds it, from
the register definitions (master_register_id) and the model columns, every column set.
"""

import json
import re

from jinja2 import Environment

from test_metadata_consistency import EXT, columns, definitions

TEMPLATE = EXT / "templates/openg2p_livestock_to_dci.json.j2"


def snake_case(name):
    """The platform's snake_case (openg2p_registry_core search/hierarchy.py)."""
    spaced = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", spaced).lower()


def children(mnemonic):
    """The mnemonics of the registers whose master register is this one."""
    registers = definitions()
    parent = next(i for i, (m, _) in registers.items() if m == mnemonic)
    return sorted(m for m, master in registers.values() if master == parent)


def row(mnemonic):
    """A record of the register with every column set. 1 renders in every field: a code, a date, a count, a flag."""
    return dict.fromkeys(columns(mnemonic), 1)


# Lists the template reads that the platform never attaches. Remove an entry once its gap is closed.
KNOWN_UNATTACHED = {
    # Farmer is a register of its own (no master register), not a child of Livestock, so the hierarchy never
    # attaches it and farmer_info's phone number, surname, sex and birth date are always empty; the given name
    # falls back to the holding's farmer_name.
    "farmer",
}


def test_child_registers_are_read_under_their_snake_case_mnemonic():
    template = TEMPLATE.read_text(encoding="utf-8")
    keys = set(re.findall(r"holding\.get\('(\w+)'\) or \[\]", template))
    child_keys = {snake_case(m) for m in children("Livestock")}
    assert {"animal", "breeding"} <= keys
    assert keys - child_keys == KNOWN_UNATTACHED, {"not attached": sorted(keys - child_keys - KNOWN_UNATTACHED),
                                                   "fixed, remove from KNOWN_UNATTACHED": sorted(
                                                       KNOWN_UNATTACHED - (keys - child_keys))}

    holding = row("Livestock") | {snake_case(m): [row(m)] for m in children("Livestock")}
    response = json.loads(Environment().from_string(template).render(expanded=holding))
    for section in ("animal_details", "breeding_details", "health_event_details", "vaccination_details",
                    "vital_event_details"):
        assert len(response[section]) == 1, section
        empty = sorted(field for field, value in response[section][0].items() if value in ("", 0, False, None))
        assert not empty, (section, empty)
