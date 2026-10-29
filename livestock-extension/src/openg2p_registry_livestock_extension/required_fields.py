"""Required fields of the Livestock forms, read from the section metadata.

`widget-required` in a section's UI schema is the one place the rule lives:
the staff UI marks the field, and the save and submit checks
(required_intake.py) read the same flag, on every channel (web, ODK, partner).
Making a field optional is a metadata change, not a code change.

The rules follow the staff UI (ui-widgets `evaluateWidgetConditions`):

- rules run in order and the last show/hide wins; a field hidden by a rule is
  not required;
- a `require` rule makes a field required while its condition matches;
- a list (table) section needs at least one row only when the table widget
  itself is `widget-required`; each row must carry its required columns.

The Farmer lookup section (Farmer ID and one Fayda ID) keeps its own
validation (field_rules.py and the finalize check in farmer_reference/native.py),
so the identity fields are left to it, and the Farmer reference status is
never asked of anyone.

This module has no database or framework imports, so it can be tested alone.
"""

MESSAGES = {
    "required_fill_in": "{section}: fill in {fields}",
    "required_fill_in_row": "{section}, row {row}: fill in {fields}",
    "required_add_row": "{section}: add at least one row",
}

# Widgets whose value is not a field of the section's record, or that other
# checks own: a table is its own register, a lookup picks a parent record,
# display and group widgets hold no input, files are attached, not typed.
SKIPPED = {"table", "dialog-table", "register-lookup", "parent-lookup", "display", "header-section", "file"}
TABLES = ("table", "dialog-table")

# Fields the Farmer lookup section validates itself, plus values the registry
# fills in: never required here.
OWN_VALIDATION = frozenset(
    {"farmer_id", "fayda_id", "fayda_fin", "fayda_fan_id", "farmer_reference_status", "identity_verification"}
)


def humanize(key) -> str:
    """A readable name for a key nobody translated: no underscores or hyphens."""
    text = " ".join(str(key or "").replace("_", " ").replace("-", " ").split())
    return text[:1].upper() + text[1:]


def blank(value) -> bool:
    """Nothing entered. Zero and false are answers."""
    return (
        value is None
        or value == ""
        or (isinstance(value, str) and not value.strip())
        or (isinstance(value, list | dict) and not value)
    )


def value_at(values: dict, path):
    """`path` is "<register id>.<field>[.<key>...]" or a bare field name;
    `values` maps register ids (or field names) to values."""
    if not isinstance(path, str):
        return None
    current = values
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _boolean_like(value) -> bool:
    if value is True or value == 1:
        return True
    if value is False or value == 0:
        return False
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "1")
    return bool(value)


def condition_matches(condition: dict, values: dict) -> bool:
    """ui-widgets `evaluateCondition`, operator for operator."""
    field = value_at(values, condition.get("field"))
    operator, expected = condition.get("operator"), condition.get("value")
    if operator == "equals":
        if isinstance(expected, bool):
            return isinstance(field, bool) and field == expected
        if isinstance(field, bool):
            return field == _boolean_like(expected)
        return field == expected
    if operator == "notEquals":
        return field != expected
    if operator == "notEmpty":
        return field is not None and field != ""
    if operator in ("empty", "isEmpty"):
        return field is None or field == ""
    if operator in ("greaterThan", "lessThan"):
        try:
            left, right = float(field), float(expected)
        except (TypeError, ValueError):
            return False
        return left > right if operator == "greaterThan" else left < right
    if operator in ("contains", "notContains"):
        if isinstance(field, str) and isinstance(expected, str) or isinstance(field, list):
            found = expected in field
        else:
            found = False
        return found if operator == "contains" else not found
    return False


def _rules(options) -> list[dict]:
    if not isinstance(options, dict):
        return []
    actions = options.get("actions")
    if isinstance(actions, list) and actions:
        return [a for a in actions if isinstance(a, dict) and a.get("action")]
    if options.get("action") and options.get("condition"):
        return [{"action": options["action"], "condition": options["condition"]}]
    return []


def widget_state(widget: dict, values: dict) -> tuple[bool, bool]:
    """(visible, required), as ui-widgets `evaluateWidgetConditions`."""
    base = widget.get("widget-required") is True
    visible, required = True, base
    for rule in _rules(widget.get("widget-data-options")):
        condition = rule.get("condition")
        if not isinstance(condition, dict):
            continue
        match = condition_matches(condition, values)
        if rule["action"] == "show":
            visible = match
        elif rule["action"] == "hide":
            visible = not match
        elif rule["action"] == "require":
            required = base or match
    return visible, required


def widgets_of(node):
    """Every input widget of a section schema, in document order."""
    if isinstance(node, dict):
        if "widget" in node and "widget-id" in node:
            yield node
        for value in node.values():
            yield from widgets_of(value)
    elif isinstance(node, list):
        for item in node:
            yield from widgets_of(item)


class Words:
    """Section titles and field labels as the form shows them. `messages`
    maps a translation key to its text; a label nobody translated is shown as
    written, or made readable."""

    def __init__(self, messages: dict | None = None):
        self.messages = messages if isinstance(messages, dict) else {}

    def _translated(self, key):
        found = self.messages.get(key) if isinstance(key, str) and key else None
        return found if isinstance(found, str) and found else None

    def title(self, schema: dict) -> str:
        key = (schema or {}).get("section-title")
        return self._translated(key) or humanize(key) or "Section"

    def label(self, widget: dict, field: str) -> str:
        for candidate in (widget.get("widget-label"), field):
            found = self._translated(candidate)
            if found:
                return found
        return humanize(widget.get("widget-label") or field)

    def text(self, key: str, **params) -> str:
        template = self._translated(key) or MESSAGES[key]
        try:
            return template.format(**params)
        except (KeyError, IndexError, ValueError):
            return MESSAGES[key].format(**params)


def value_path(widget: dict):
    path = widget.get("widget-data-path")
    if isinstance(path, dict):
        path = path.get("value")
    return path if isinstance(path, str) else None


def field_of(widget: dict):
    """The record field a widget writes: the last part of its data path, or
    the column key of a table column."""
    if widget.get("column-key"):
        return str(widget["column-key"])
    path = value_path(widget)
    return path.split(".")[-1] if path else None


def table_of(schema: dict):
    """The table widget of a list section."""
    stack = [schema]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if node.get("widget") in TABLES and "widget-data-columns" in node:
                return node
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return None


def missing_in_record(widgets, record: dict, values: dict, words: Words) -> list[str]:
    """Labels of the required, visible fields the record leaves empty.

    `values` is what conditions are evaluated against: register id -> record
    for a single-record section, the row itself for a table row.
    """
    fill: list[str] = []
    for widget in widgets:
        if widget.get("widget") in SKIPPED or widget.get("widget-readonly"):
            continue
        field = field_of(widget)
        if not field or field in OWN_VALIDATION:
            continue
        visible, required = widget_state(widget, values)
        if not (visible and required):
            continue
        label = words.label(widget, field)
        if blank(record.get(field)) and label not in fill:
            fill.append(label)
    return fill


def section_problems(
    schema: dict,
    is_list: bool,
    records: list[dict],
    values: dict,
    messages: dict | None = None,
) -> list[str]:
    """One sentence per thing a section still needs, in the section's words.

    `records` are the section's records as they will be stored (the surviving
    rows); `values` maps register ids to records, for conditions that look at
    another section of the same form.
    """
    words = Words(messages)
    title = words.title(schema)
    if is_list:
        table = table_of(schema)
        if table is None:
            return []
        if table.get("widget-required") is True and not records:
            return [words.text("required_add_row", section=title)]
        columns = [c for c in table.get("widget-data-columns") or [] if isinstance(c, dict)]
        problems = []
        for number, row in enumerate(records, start=1):
            fill = missing_in_record(columns, row, {**values, **row}, words)
            if fill:
                problems.append(words.text("required_fill_in_row", section=title, row=number, fields=", ".join(fill)))
        return problems
    record = records[0] if records else {}
    # A condition names its field as "<register id>.<field>" or by the bare field name.
    fill = missing_in_record(widgets_of(schema), record, {**record, **values}, words)
    return [words.text("required_fill_in", section=title, fields=", ".join(fill))] if fill else []
