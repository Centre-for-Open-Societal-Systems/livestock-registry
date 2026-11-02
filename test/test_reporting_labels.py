"""Reporting labels come from the Master Data API, never from a registry table it no longer has."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("lr_reporting_labels", ROOT / "docker/db-seed/reporting-label-sync.py")
labels = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(labels)


def values(*rows):
    return [dict(zip(("value_id", "value_code", "display", "status"), row)) for row in rows]


def test_active_values_are_labelled_by_code_and_by_id():
    rows = values(("CATTLE", "CATTLE", "Cattle", "ACTIVE"),
                  ("LIVESTOCK_SPECIES_GOATS", "GOATS", "Goats", "ACTIVE"),
                  ("OLD", "OLD", "Retired", "INACTIVE"),
                  ("BLANK", "BLANK", " ", "ACTIVE"))
    assert labels.labels_of(rows) == [("CATTLE", "Cattle"), ("GOATS", "Goats"), ("LIVESTOCK_SPECIES_GOATS", "Goats")]


def test_unconfigured_master_data_skips_without_touching_the_table(monkeypatch, capsys):
    for name in ("MDS_API_URL", "MDS_TOKEN_URL", "MDS_CLIENT_ID", "MDS_CLIENT_SECRET"):
        monkeypatch.delenv(name, raising=False)
    with patch.object(labels, "store") as store:
        assert labels.main() == 0
    store.assert_not_called()
    assert "not configured" in capsys.readouterr().err


class Answers:
    """The token endpoint, then one catalogue page per list."""

    def __init__(self, pages):
        self.pages = list(pages)

    def __call__(self, url, body, *, token=None, form=False):
        if form:
            return {"access_token": "token"}
        page = self.pages.pop(0)
        if page is None:
            return {"response_header": {"response_status": "ERROR"}}
        return {"response_header": {"response_status": "SUCCESS"},
                "response_body": {"response_payload": {"values": page}}}


def test_both_lists_are_read_from_the_catalogue():
    species = values(("CATTLE", "CATTLE", "Cattle", "ACTIVE"))
    breeds = values(("BREED_LOCAL", "BREED_LOCAL", "Local", "ACTIVE"))
    with patch.object(labels, "post", Answers([species, breeds])):
        found = labels.fetch_labels("http://mds", "http://kc/token", "client", "secret")
    assert found == {"LIVESTOCK_SPECIES": [("CATTLE", "Cattle")], "LIVESTOCK_BREED": [("BREED_LOCAL", "Local")]}


@pytest.mark.parametrize("pages", [[None], [[]], [values(("CATTLE", "CATTLE", "Cattle", "ACTIVE")), []]])
def test_a_refusal_or_an_empty_list_keeps_the_previous_labels(pages):
    with patch.object(labels, "post", Answers(pages)), patch.object(labels, "store") as store, \
            pytest.raises(labels.LabelsUnavailable):
        labels.fetch_labels("http://mds", "http://kc/token", "client", "secret")
    store.assert_not_called()


def test_the_views_join_the_label_table_not_the_old_attribute_table():
    sql = (ROOT / "docker/db-seed/reporting_views.sql").read_text(encoding="utf-8")
    assert "g2p_attribute_values" not in sql
    assert "CREATE TABLE IF NOT EXISTS lr_rpt_label" in sql
    assert "sp.list_code = 'LIVESTOCK_SPECIES'" in sql and "br.list_code = 'LIVESTOCK_BREED'" in sql
    # The dashboard API reads these two columns.
    assert "AS species_name" in sql and "AS breed_name" in sql


def test_db_seed_image_carries_the_label_sync():
    dockerfile = (ROOT / "docker/db-seed/Dockerfile").read_text(encoding="utf-8")
    assert "COPY --chmod=755 docker/db-seed/reporting-label-sync.py /seed/reporting-label-sync.py" in dockerfile
