"""Where your data went says what each connection was for (INBOX 807).

The owner: "it isnt really clear exactly what these were for". The code
that reaches out names its purpose; each destination keeps the newest few.
"""

from __future__ import annotations

import threading

import pytest

from tessellate.core import egress


@pytest.fixture(autouse=True)
def _clean():
    egress.configure(None)
    egress.reset()
    yield
    egress.reset()


def _row(host):
    return next(r for r in egress.destinations() if r["host"] == host)


def test_a_connection_inside_a_purpose_records_it():
    with egress.purpose("Downloading the English OCR data"):
        egress._record("lookup", "github.com", 443)
    assert _row("github.com")["purposes"] == ["Downloading the English OCR data"]


def test_purposes_are_distinct_newest_first_and_capped():
    for n in range(egress.MAX_PURPOSES + 3):
        with egress.purpose(f"Web search for 'mouse {n}'"):
            egress._record("lookup", "duckduckgo.com", 443)
    with egress.purpose("Web search for 'mouse 2'"):
        egress._record("lookup", "duckduckgo.com", 443)
    kept = _row("duckduckgo.com")["purposes"]
    assert len(kept) == egress.MAX_PURPOSES and kept[0] == "Web search for 'mouse 2'"
    assert len(set(kept)) == len(kept)


def test_a_connection_with_no_purpose_records_none():
    egress._record("lookup", "example.org", 443)
    assert _row("example.org")["purposes"] == []


def test_a_library_worker_thread_inherits_the_open_purpose():
    with egress.purpose("Downloading the embedding model BAAI/bge-small-en-v1.5"):
        worker = threading.Thread(target=egress._record, args=("lookup", "huggingface.co", 443))
        worker.start()
        worker.join()
    assert _row("huggingface.co")["purposes"] == ["Downloading the embedding model BAAI/bge-small-en-v1.5"]


def test_labelled_names_the_call_from_its_arguments():
    @egress.labelled(lambda query, **_: f"Web search for '{egress.short(query)}'")
    def search(query, limit=5):
        egress._record("lookup", "search.example", 443)

    search("gaming mouse", limit=3)
    assert _row("search.example")["purposes"] == ["Web search for 'gaming mouse'"]


def test_a_label_that_raises_never_stops_the_call():
    @egress.labelled(lambda: 1 / 0)
    def fetch():
        return "ok"

    assert fetch() == "ok"


def test_the_ledger_on_disk_keeps_purposes_across_flushes(tmp_path):
    path = tmp_path / egress.LEDGER_NAME
    with egress.purpose("Checking GitHub for a new version"):
        egress._record("lookup", "api.github.com", 443)
    egress.flush(path)
    with egress.purpose("Listing the versions on GitHub"):
        egress._record("lookup", "api.github.com", 443)
    ledger = egress.flush(path)
    row = next(r for r in ledger["destinations"] if r["host"] == "api.github.com")
    assert row["purposes"] == ["Listing the versions on GitHub", "Checking GitHub for a new version"]


def test_the_outbound_call_sites_name_their_purpose():
    from tessellate.api import routes_update
    from tessellate.core import webclip
    from tessellate.search import searxng_install, websearch

    for func in (
        websearch.search_web,
        #: The label moved with the request itself, out of fetch_readable into
        #: the helper it calls (audit 1030 A2 split fetch_readable).
        websearch._fetch_page,
        webclip.fetch_page,
        routes_update._download,
        routes_update.check_for_update,
        routes_update.list_releases,
        routes_update.apply_update,
        searxng_install._download,
    ):
        assert func.__wrapped__, func



def test_the_address_guard_names_the_feature_it_checked_for():
    """`security` resolves before every fetch; the row names the feature."""
    seen = []

    def record():  # where `_record` sits, so `_caller` skips the same frames
        seen.append(egress._caller())

    guard = {"__name__": "tessellate.core.security", "record": record}
    exec("def check():\n    return record()", guard)
    feature = {"__name__": "tessellate.core.webclip", "check": guard["check"]}
    exec("def fetch():\n    return check()", feature)
    feature["fetch"]()
    guard["check"]()
    assert seen == ["tessellate.core.webclip", "tessellate.core.security"]
