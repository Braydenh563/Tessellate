"""The tag-reasons cache holds a whole 5,000-note page (L-world-class-161).

`GET /entries?limit=5000` reads the same notes in the same order on every load.
An LRU of 1,024 rows evicts each row before the next load reaches it, so the
second load re-ran `tagging.clean` (about 0.4 ms a note) for every note: 2.1 s
warm at 5,000. Counted, not timed: a miss is a call of `_reasons_for`."""

from __future__ import annotations

from tessellate.api import routes_entries


def test_a_full_page_read_twice_computes_each_note_once(monkeypatch):
    calls = {"n": 0}

    def counted(content: str, tags: tuple[str, ...]):
        calls["n"] += 1
        return tuple((tag, f"in {content}") for tag in tags)

    monkeypatch.setattr(routes_entries, "_reasons_for", counted)
    routes_entries._cached_reasons.cache_clear()
    page = routes_entries.ENTRIES_PAGE_SIZE_MAX
    for _load in range(2):
        for i in range(page):
            assert routes_entries._tag_reasons(f"Note {i} on running", ["running"]) == {"running": f"in Note {i} on running"}
    assert calls["n"] == page
    info = routes_entries._cached_reasons.cache_info()
    assert (info.hits, info.misses) == (page, page)


def test_the_cache_is_bigger_than_a_page_and_light_per_row():
    assert routes_entries.REASONS_CACHE_ROWS > routes_entries.ENTRIES_PAGE_SIZE_MAX
    routes_entries._cached_reasons.cache_clear()
    routes_entries._cached_reasons("x" * 19_000, ("a",))
    (key,) = routes_entries._cached_reasons._rows
    assert len(key[0]) == 16  # a digest, not the 19,000-character text


def test_the_oldest_row_goes_first_when_full(monkeypatch):
    monkeypatch.setattr(routes_entries, "_reasons_for", lambda content, tags: ())
    cache = routes_entries._ReasonsCache(2)
    for text in ("a", "b", "a", "c"):
        cache(text, ("t",))
    assert cache.cache_info().currsize == 2
    cache("a", ("t",))
    assert cache.cache_info().hits == 2  # "a" was touched, so "b" went
