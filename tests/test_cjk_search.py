"""A word of Japanese is found inside its line (notes audit 1031, N2)."""

import pytest

from tessellate.core import cjk


@pytest.mark.parametrize("text,count", [("", 0), ("two words", 2), ("ゴルフ", 3), ("考え 2 words", 4), ("한국어 단어", 2), ("ー", 0)])
def test_word_count_counts_ideographs_by_character(text, count):
    assert cjk.word_count(text) == count


def test_has_sees_unsegmented_scripts_only():
    assert cjk.has("harbor 計画") and cjk.has("ゴルフ") and cjk.has("골프를")
    assert not cjk.has("plain words") and not cjk.has("")


def _note(client, text, **extra):
    return client.post("/entries", json={"content": text, **extra}).json()["id"]


def _ids(client, q):
    hits = client.get("/search", params={"q": q, "hybrid": "false"}).json()["hits"]
    return [hit["id"] for hit in hits]


def test_a_word_inside_a_japanese_line_is_found(client):
    golf = _note(client, "週末のゴルフについての考え")
    other = _note(client, "harbor launch plan")
    for word in ("ゴルフ", "考え", "週末のゴルフ"):
        assert golf in _ids(client, word), word
    assert other not in _ids(client, "ゴルフ")


def test_a_mixed_query_needs_both_halves(client):
    both = _note(client, "harbor ゴルフ trip")
    only_jp = _note(client, "ゴルフ alone")
    found = _ids(client, "harbor ゴルフ")
    assert both in found and only_jp not in found


def test_a_filter_and_an_excluded_word_still_apply(client):
    kept = _note(client, "ゴルフの練習", tags=["sport"])
    dropped = _note(client, "ゴルフの雨", tags=["sport"])
    _note(client, "ゴルフの練習 elsewhere", tags=["other"])
    found = _ids(client, "ゴルフ tag:sport -雨")
    assert kept in found and dropped not in found and len(found) == 1


def test_keyword_search_finds_a_word_inside_a_japanese_line(client):
    from tessellate.core import deps
    from tessellate.search import search_manager

    golf = _note(client, "週末のゴルフについての考え")
    _note(client, "harbor launch plan")
    with deps.get_db().session() as session:
        found = [entry.id for entry in search_manager.keyword_search(session, "ゴルフ")]
    assert found == [golf]
