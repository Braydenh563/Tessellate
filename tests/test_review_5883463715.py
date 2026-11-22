"""The owner's automated review 5883463715 on PR 227: five findings, one test each."""

from __future__ import annotations

import inspect

from tessellate.core import lantrust


def test_the_plain_http_flag_is_read_from_disk_once_until_it_changes(tmp_path, monkeypatch):
    """Finding 2: the LAN port asks "plain http?" per connection; that is a cached flag, not a file read."""
    lantrust.set_flag(tmp_path, "plain_http", True)
    reads = []
    real = lantrust.load
    monkeypatch.setattr(lantrust, "load", lambda d: reads.append(d) or real(d))
    assert lantrust.plain_http_on(tmp_path) is True
    assert lantrust.plain_http_on(tmp_path) is True
    assert len(reads) <= 1
    monkeypatch.setattr(lantrust, "load", real)
    lantrust.set_flag(tmp_path, "plain_http", False)
    assert lantrust.plain_http_on(tmp_path) is False


def test_the_lan_listener_asks_the_cached_flag():
    from tessellate.core import lanlive

    source = inspect.getsource(lanlive)
    assert "lantrust.plain_http_on(data_dir)" in source
    assert 'lantrust.load(data_dir)["plain_http"]' not in source


def test_a_plain_http_device_cookie_is_not_marked_secure():
    """Finding 1: a Secure cookie on plain http is dropped, so the phone was asked about every sign-in."""
    from starlette.responses import Response

    from tessellate.api import routes_auth

    response = Response()
    routes_auth._set_device_cookie(response, "a" * 32, secure=False)
    header = response.headers["set-cookie"]
    assert "Secure" not in header and "HttpOnly" in header
    response = Response()
    routes_auth._set_device_cookie(response, "a" * 32, secure=True)
    assert "Secure" in response.headers["set-cookie"]


def test_eviction_keeps_running_and_locked_slots_and_the_one_asked_for(monkeypatch):
    """Finding 3: a full table dropped the oldest slot even while its turn ran, so a retry ran twice."""
    from tessellate.ai import turn_once

    turn_once.reset_for_tests()
    monkeypatch.setattr(turn_once, "MAX_SLOTS", 3)
    running = turn_once.slot("t-running", "dev-a")
    assert turn_once.begin_stream(running)
    locked = turn_once.slot("t-locked", "dev-a")
    locked.lock.acquire()
    try:
        for n in range(6):
            turn_once.slot(f"t-{n}", "dev-a")
        assert turn_once.slot("t-running", "dev-a") is running
        assert turn_once.slot("t-locked", "dev-a") is locked
    finally:
        locked.lock.release()
        turn_once.reset_for_tests()


def test_slots_are_kept_apart_per_caller():
    from tessellate.ai import turn_once

    turn_once.reset_for_tests()
    assert turn_once.slot("t-1", "dev-a") is not turn_once.slot("t-1", "dev-b")
    assert turn_once.slot("t-1", "dev-a") is turn_once.slot("t-1", "dev-a")
    turn_once.reset_for_tests()


def test_a_stream_cut_off_partway_is_not_run_again():
    """Finding 4: a stream dropped after some lines left the id free, so a retry repeated its writes."""
    import asyncio

    from tessellate.ai import turn_once
    from tessellate.api import once_routes

    turn_once.reset_for_tests()
    held = turn_once.slot("t-cut", "dev-a")
    assert turn_once.begin_stream(held)

    async def lines():
        yield "one\n"
        yield "two\n"

    async def read_one():
        gen = once_routes._remember(held, lines())
        await gen.__anext__()
        await gen.aclose()

    asyncio.run(read_one())
    assert held.partial and held.value is None
    assert not turn_once.begin_stream(held)
    turn_once.reset_for_tests()


def test_a_notes_file_text_is_capped_in_its_search_row(session):
    """Finding 5: a scanned book's OCR made every save of its note re-index all of it."""
    from tessellate.core.database import Attachment
    from tessellate.entry import manager
    from tessellate.search import index

    entry = manager.create_entry(session, "Scanned book", category_name=manager.UNCATEGORISED)
    session.commit()
    session.add(Attachment(entry_id=entry.id, filename="b.pdf", stored_name="cap1", size=1, ocr_text="word " * 20_000))
    session.commit()
    assert len(index._file_words(session.get(type(entry), entry.id))) == index.FILE_WORDS_CAP  # noqa: SLF001
