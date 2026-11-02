"""An outbreak alert suppresses only repeats of its own outbreak: a later
cluster in the same woreda alerts again, however small, once the earlier
alert has left the window."""

from datetime import date, datetime

import pytest

pytest.importorskip("openg2p_registry_core")

from openg2p_registry_livestock_extension.register_domain.services import outbreak_alert_service as alerts


class Engine:
    """Answers the alert lookup with one stored row (case_count, alerted_at), or none."""

    def __init__(self, row):
        self.row = row

    def connect(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, statement, params):
        assert params == {"d": "LIVESTOCK_DISEASE_ANTHRAX", "w": "ET040706"}
        return self

    def first(self):
        return self.row


WINDOW_START = date(2026, 6, 1)


def already(row, cases):
    return alerts._already_alerted(Engine(row), "LIVESTOCK_DISEASE_ANTHRAX", "ET040706", cases, WINDOW_START)


def test_no_earlier_alert_alerts():
    assert already(None, 3) is False


def test_a_large_old_outbreak_does_not_suppress_a_new_small_one():
    # 10 cases alerted in January; a 3-case cluster in June is a new outbreak.
    assert already((10, datetime(2026, 1, 15, 9, 0)), 3) is False


def test_the_same_outbreak_inside_the_window_is_not_repeated():
    assert already((5, datetime(2026, 6, 5, 9, 0)), 3) is True
    assert already((5, datetime(2026, 6, 5, 9, 0)), 5) is True


def test_the_same_outbreak_growing_inside_the_window_alerts_again():
    assert already((3, datetime(2026, 6, 5, 9, 0)), 6) is False


def test_an_alert_without_a_time_does_not_suppress():
    assert already((10, None), 3) is False
