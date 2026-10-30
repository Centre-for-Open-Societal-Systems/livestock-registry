"""Re-driving deliveries that failed for want of a signing key (no database needed)."""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from openg2p_registry_connector_extension import registry_signature, requeue  # noqa: E402

MARKER = requeue.MARKER + " (auth_secret_json.registry_signature)"
ENV_NAMES = ("CONNECTOR_SIGNING_KEY_PEM", "CONNECTOR_SIGNING_KID", "CONNECTOR_REGISTRY_SIGNATURE_KEY_PEM",
             "CONNECTOR_REGISTRY_SIGNATURE_KEY_ID")
NONE_YET = {"candidates": 0, "replayed": 0, "failed": 0, "skipped": 0}


class Col:
    """Stand-in for a mapped column: its operators return tagged clauses the fake session reads."""

    def __init__(self, name=""):
        self.name = name

    def like(self, pattern):
        return ("like", pattern)

    def in_(self, values):
        return ("in", list(values))

    def __eq__(self, other):
        return ("eq", other)

    __hash__ = object.__hash__

    def __lt__(self, other):
        return ("lt", other)


class Entry:
    dl_id = Col("dl_id")
    error = Col("error")
    attempt_count = Col("attempt_count")
    created_at = Col("created_at")
    connector_id = Col("connector_id")

    def __init__(self, dl_id, error=MARKER, attempts=1, connector_id="c1"):
        self.dl_id, self.error, self.attempt_count = dl_id, error, attempts
        self.connector_id, self.source_event_id, self.payload = connector_id, "evt-" + dl_id, {"k": dl_id}


class Connector:
    def __init__(self, active=True, secrets=None):
        self.is_active, self._secrets = active, secrets

    def get_auth_secrets(self):
        return self._secrets or {}


class Query:
    def __init__(self, target):
        self.target, self.clauses, self.n, self.locked, self.is_distinct = target, [], None, False, False

    def where(self, *clauses):
        self.clauses += clauses
        return self

    def order_by(self, *_):
        return self

    def limit(self, n):
        self.n = n
        return self

    def distinct(self):
        self.is_distinct = True
        return self

    def with_for_update(self, skip_locked=False):
        self.locked = skip_locked
        return self


class Result:
    def __init__(self, items):
        self.items = items

    def scalars(self):
        return SimpleNamespace(all=lambda: self.items)

    def scalar_one_or_none(self):
        return self.items[0] if self.items else None


class Store:
    """Entries by id; each call gives a session over the same data."""

    def __init__(self, entries, connectors):
        self.entries = {e.dl_id: e for e in entries}
        self.connectors, self.deleted, self.rollbacks = connectors, [], 0
        self.locked_by_other, self.lock_requests = set(), 0

    def __call__(self):
        return Session(self)


class Session:
    def __init__(self, store):
        self.store = store

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, query):
        clauses = {c[0]: c[1] for c in query.clauses if isinstance(c, tuple)}
        rows = [e for e in self.store.entries.values()
                if ("like" not in clauses or (e.error.startswith(clauses["like"].rstrip("%"))
                                              and e.attempt_count < requeue.MAX_ATTEMPTS))
                and ("in" not in clauses or e.connector_id in clauses["in"])
                and ("eq" not in clauses or e.dl_id == clauses["eq"])]
        if query.locked:
            self.store.lock_requests += 1
            rows = [e for e in rows if e.dl_id not in self.store.locked_by_other]
        if query.target is Entry:
            return Result(rows[:1])
        values = [getattr(e, query.target.name) for e in rows]
        if query.is_distinct:
            values = list(dict.fromkeys(values))
        return Result(values[:query.n])

    async def get(self, model, key):
        return self.store.entries.get(key) if model is Entry else self.store.connectors.get(key)

    async def delete(self, entry):
        self.store.deleted.append(entry.dl_id)
        del self.store.entries[entry.dl_id]

    async def commit(self):
        pass

    async def rollback(self):
        self.store.rollbacks += 1


class Service:
    def __init__(self, outcomes):
        self.outcomes, self.calls = outcomes, []

    async def process_record(self, connector, source_event_id, raw_data, session):
        self.calls.append((source_event_id, raw_data))
        status, error = self.outcomes[source_event_id]
        return SimpleNamespace(status=SimpleNamespace(value=status), last_error=error)


def run(store, service):
    return asyncio.run(requeue.redrive(store, service, entry_model=Entry, connector_model=Connector, select=Query))


@pytest.fixture(autouse=True)
def no_env_key(monkeypatch):
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("CONNECTOR_SIGNING_KEY_PEM", "pem")
    monkeypatch.setenv("CONNECTOR_SIGNING_KID", "kid")


def test_nothing_is_replayed_while_no_key_exists():
    store = Store([Entry("a")], {"c1": Connector()})
    service = Service({"evt-a": ("SUCCESS", None)})
    assert run(store, service) == NONE_YET
    assert service.calls == [] and not store.deleted


def test_success_deletes_the_entry_and_replays_the_stored_body(key):
    store = Store([Entry("a")], {"c1": Connector()})
    service = Service({"evt-a": ("SUCCESS", None)})
    stats = run(store, service)
    assert stats["replayed"] == 1 and store.deleted == ["a"]
    assert service.calls == [("evt-a", {"k": "a"})]
    assert store.lock_requests == 1  # the entry was read FOR UPDATE SKIP LOCKED


def test_stored_secret_key_also_enables_the_replay():
    secrets = {"registry_signature": {"key_pem": "pem", "key_id": "kid"}}
    store = Store([Entry("a")], {"c1": Connector(secrets=secrets)})
    assert run(store, Service({"evt-a": ("SUCCESS", None)}))["replayed"] == 1


def test_only_the_signature_failures_are_selected(key):
    store = Store([Entry("a"), Entry("b", error="Validation failed: x"), Entry("c", attempts=requeue.MAX_ATTEMPTS)],
                  {"c1": Connector()})
    service = Service({"evt-a": ("SUCCESS", None)})
    assert run(store, service)["candidates"] == 1
    assert [c[0] for c in service.calls] == ["evt-a"]


def test_a_failed_replay_is_rolled_back_and_leaves_the_selection(key):
    store = Store([Entry("a")], {"c1": Connector()})
    service = Service({"evt-a": ("FAILED", "Registry rejected the signature")})
    stats = run(store, service)
    entry = store.entries["a"]
    assert stats["failed"] == 1 and store.rollbacks == 1 and not store.deleted
    assert entry.attempt_count == 2 and entry.error == "Registry rejected the signature"
    assert run(store, service)["candidates"] == 0  # no endless loop


def test_inactive_or_missing_connector_is_never_selected(key):
    store = Store([Entry("a"), Entry("b", connector_id="gone")], {"c1": Connector(active=False)})
    service = Service({})
    assert run(store, service) == NONE_YET
    assert not store.deleted and service.calls == []


def test_an_exception_in_one_entry_is_counted_and_does_not_stop_the_batch(key):
    store = Store([Entry("a"), Entry("b")], {"c1": Connector()})
    service = Service({"evt-b": ("SUCCESS", None)})  # evt-a is missing: KeyError
    stats = run(store, service)
    assert stats["failed"] == 1 and stats["replayed"] == 1 and store.deleted == ["b"]
    # the entry that raised leaves the selection instead of being retried every tick
    a = store.entries["a"]
    assert a.attempt_count == 2 and a.error.startswith("Re-drive raised KeyError")
    assert run(store, service)["candidates"] == 0


def test_entries_that_cannot_be_replayed_do_not_block_the_batch(key, monkeypatch):
    monkeypatch.setattr(requeue, "BATCH", 2)
    stuck = [Entry(f"s{i}", connector_id="idle") for i in range(5)]
    store = Store(stuck + [Entry("a"), Entry("b")], {"c1": Connector(), "idle": Connector(active=False)})
    service = Service({"evt-a": ("SUCCESS", None), "evt-b": ("SUCCESS", None)})
    stats = run(store, service)
    assert stats["replayed"] == 2 and sorted(store.deleted) == ["a", "b"]


def test_an_entry_locked_by_another_tick_is_left_alone(key):
    store = Store([Entry("a"), Entry("b")], {"c1": Connector()})
    store.locked_by_other.add("a")
    service = Service({"evt-a": ("SUCCESS", None), "evt-b": ("SUCCESS", None)})
    stats = run(store, service)
    assert stats["skipped"] == 1 and stats["replayed"] == 1 and store.deleted == ["b"]


def test_a_missing_dead_letter_table_gives_empty_stats_and_one_warning(caplog):
    from sqlalchemy.exc import OperationalError

    class Broken:
        def __call__(self):
            return self

        async def __aenter__(self):
            raise OperationalError("select", {}, Exception("no such table"))

        async def __aexit__(self, *exc):
            return False

    with caplog.at_level("WARNING", logger="connector.extension.requeue"):
        stats = asyncio.run(requeue.redrive(Broken(), Service({})))
    assert stats == NONE_YET
    assert len([r for r in caplog.records if "not readable" in r.getMessage()]) == 1


def test_worker_hook_registers_the_task_and_beat_entry_once():
    from celery import Celery

    from openg2p_registry_connector_extension import worker_hook

    app = Celery("t")
    app.conf.beat_schedule = {"poll-all-connectors": {"task": "connector.poll_all", "schedule": 60}}
    module = SimpleNamespace(celery_app=app)
    worker_hook.install(module)
    worker_hook.install(module)
    assert requeue.TASK_NAME in app.tasks
    assert app.conf.beat_schedule["oan-redrive-unsigned"] == {
        "task": requeue.TASK_NAME, "schedule": requeue.INTERVAL_SECONDS}
    assert "poll-all-connectors" in app.conf.beat_schedule
    assert app.tasks[requeue.TASK_NAME].time_limit == requeue.TIME_LIMIT_SECONDS < requeue.INTERVAL_SECONDS


def test_a_failing_hook_does_not_break_the_import_of_the_module(caplog):
    from openg2p_registry_connector_extension import startup

    def boom(_module):
        raise RuntimeError("hook bug")

    module = SimpleNamespace(__name__="m")
    with caplog.at_level("ERROR", logger="connector.extension.startup"):
        startup._Loader(SimpleNamespace(exec_module=lambda m: None), boom).exec_module(module)
    assert "hook bug" in caplog.text


def test_marker_matches_the_error_the_signer_raises():
    with pytest.raises(ValueError) as exc:
        registry_signature.signing_key(Connector())
    assert str(exc.value).startswith(requeue.MARKER)
