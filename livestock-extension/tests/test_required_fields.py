"""Required fields read from the section metadata (pure helpers, no database)."""

import importlib
import os

PACKAGE = os.environ.get("REGISTRY_EXTENSION_MODULE", "openg2p_registry_livestock_extension")
rf = importlib.import_module(PACKAGE + ".required_fields")

REGISTER = "997676d3-7008-59f9-b23e-613ad79bbb08"


def widget(field, label, *, required=False, kind="text", actions=None, path=True):
    node = {"widget": kind, "widget-id": field, "widget-label": label, "widget-required": required}
    if path:
        node["widget-data-path"] = f"{REGISTER}.{field}"
    if actions:
        node["widget-data-options"] = {"actions": actions}
    return node


def column(field, label, *, required=False, kind="text", actions=None):
    node = {"widget": kind, "column-key": field, "widget-label": label, "widget-required": required}
    if actions:
        node["widget-data-options"] = {"actions": actions}
    return node


def single(title, *widgets):
    return {"section-title": title, "panels": [{"widgets": list(widgets)}]}


def table(title, *columns, required=False):
    return {
        "section-title": title,
        "panels": [{"widgets": [{
            "widget": "dialog-table", "widget-id": "rows", "widget-label": title,
            "widget-required": required, "widget-data-columns": list(columns),
        }]}],
    }


LOCATION = single(
    "Livestock Location",
    widget("kebele", "Kebele", required=True),
    widget("landmark", "Landmark"),
)

SHOW_WHEN_OTHER = [{"action": "show", "condition": {"field": "water_source", "operator": "equals", "value": "OTHER"}}]
REQUIRE_WHEN_OTHER = [{"action": "require", "condition": {"field": "water_source", "operator": "equals", "value": "OTHER"}}]


def test_complete_section_has_no_problems():
    assert rf.section_problems(LOCATION, False, [{"kebele": "Kebele 01"}], {REGISTER: {"kebele": "Kebele 01"}}) == []


def test_empty_required_section_names_the_fields():
    problems = rf.section_problems(LOCATION, False, [{}], {REGISTER: {}})
    assert problems == ["Livestock Location: fill in Kebele"]


def test_blank_text_counts_as_empty_but_zero_and_false_do_not():
    schema = single(
        "Herd", widget("name", "Herd Name", required=True), widget("head_count", "Head Count", required=True, kind="number"),
        widget("vaccinated", "Vaccinated", required=True, kind="radio"),
    )
    record = {"name": "   ", "head_count": 0, "vaccinated": False}
    assert rf.section_problems(schema, False, [record], {REGISTER: record}) == ["Herd: fill in Herd Name"]


def test_a_missing_section_record_is_incomplete():
    assert rf.section_problems(LOCATION, False, [], {}) == ["Livestock Location: fill in Kebele"]


def test_hidden_field_is_not_required():
    schema = single(
        "Water",
        widget("water_source", "Water Source", required=True, kind="select"),
        widget("water_other", "Other Water Source", required=True, actions=SHOW_WHEN_OTHER),
    )
    hidden = {"water_source": "RIVER"}
    assert rf.section_problems(schema, False, [hidden], {REGISTER: hidden}) == []
    shown = {"water_source": "OTHER"}
    assert rf.section_problems(schema, False, [shown], {REGISTER: shown}) == ["Water: fill in Other Water Source"]


def test_require_rule_makes_a_field_required_while_it_matches():
    schema = single(
        "Water",
        widget("water_source", "Water Source", kind="select"),
        widget("water_other", "Other Water Source", actions=REQUIRE_WHEN_OTHER),
    )
    other = {"water_source": "OTHER"}
    assert rf.section_problems(schema, False, [other], {REGISTER: other}) == ["Water: fill in Other Water Source"]
    other["water_other"] = "Borehole"
    assert rf.section_problems(schema, False, [other], {REGISTER: other}) == []
    river = {"water_source": "RIVER"}
    assert rf.section_problems(schema, False, [river], {REGISTER: river}) == []


def test_the_last_show_or_hide_rule_wins_like_the_staff_ui():
    state = rf.widget_state(
        widget("x", "X", required=True, actions=[
            {"action": "hide", "condition": {"field": "a", "operator": "equals", "value": 1}},
            {"action": "show", "condition": {"field": "a", "operator": "equals", "value": 1}},
        ]),
        {"a": 1},
    )
    assert state == (True, True)


def test_farmer_lookup_fields_keep_their_own_validation():
    schema = single(
        "Farmer lookup",
        widget("farmer_id", "Farmer ID", required=True),
        widget("fayda_id", "Fayda ID (FAN or FIN)", required=True),
        widget("farmer_reference_status", "Farmer reference status", required=True),
    )
    assert rf.section_problems(schema, False, [{}], {REGISTER: {}}) == []


def test_readonly_and_display_widgets_are_not_asked_for():
    readonly = widget("age", "Age", required=True)
    readonly["widget-readonly"] = True
    schema = single("Herd", readonly, widget("note", "Note", required=True, kind="display"))
    assert rf.section_problems(schema, False, [{}], {REGISTER: {}}) == []


def test_a_list_section_needs_a_row_only_when_the_table_is_required():
    columns = [column("species", "Species", required=True)]
    assert rf.section_problems(table("Livestock Details", *columns), True, [], {}) == []
    assert rf.section_problems(table("Livestock Details", *columns, required=True), True, [], {}) == [
        "Livestock Details: add at least one row"]


def test_each_row_is_checked_for_its_required_columns():
    schema = table(
        "Livestock Details",
        column("species", "Species", required=True, kind="select"),
        column("breed", "Breed", required=True, kind="select"),
        column("weight", "Weight (kg)", kind="number"),
    )
    rows = [{"species": "CATTLE", "breed": "BORAN"}, {"species": "CATTLE", "breed": ""}, {"weight": 3}]
    assert rf.section_problems(schema, True, rows, {}) == [
        "Livestock Details, row 2: fill in Breed",
        "Livestock Details, row 3: fill in Species, Breed",
    ]


def test_column_rules_use_the_row_and_hidden_columns_are_skipped():
    schema = table(
        "Vital Event Details",
        column("event_type", "Event Type", required=True, kind="select"),
        column("disease_type", "Disease Type", kind="select", actions=[
            {"action": "show", "condition": {"field": "event_type", "operator": "equals", "value": "DISEASE"}},
            {"action": "require", "condition": {"field": "event_type", "operator": "equals", "value": "DISEASE"}},
        ]),
    )
    assert rf.section_problems(schema, True, [{"event_type": "BIRTH"}], {}) == []
    assert rf.section_problems(schema, True, [{"event_type": "DISEASE"}], {}) == [
        "Vital Event Details, row 1: fill in Disease Type"]


def test_a_list_section_without_a_table_widget_has_nothing_to_check():
    assert rf.section_problems({"section-title": "Empty", "panels": []}, True, [{}], {}) == []


def test_a_label_nobody_translated_is_made_readable_and_translations_win():
    schema = single("livestock_location", {"widget": "text", "widget-id": "kebele_name", "widget-required": True,
                                          "widget-data-path": REGISTER + ".kebele_name"})
    assert rf.section_problems(schema, False, [{}], {}) == ["Livestock location: fill in Kebele name"]
    translated = {"livestock_location": "Where the herd is kept", "kebele_name": "Kebele"}
    assert rf.section_problems(schema, False, [{}], {}, translated) == ["Where the herd is kept: fill in Kebele"]


def test_messages_never_show_underscores_or_hyphens_from_keys():
    schema = single("herd-details_page", {"widget": "text", "widget-id": "x", "widget-required": True,
                                          "widget-data-path": REGISTER + ".head_count_total"})
    (text,) = rf.section_problems(schema, False, [{}], {})
    assert "_" not in text and "-" not in text
