"""The desk reads the companion catalogue (atlascat-1108, Batch A): one loader, one table for both sides."""

from __future__ import annotations

from tessellate.core.overlay import catalogue


def test_the_loader_returns_every_entry() -> None:
    assert len(catalogue.entries()) == 307
    assert catalogue.load()["moods"]


def test_a_missing_file_is_an_empty_table_not_a_crash(monkeypatch, tmp_path) -> None:
    catalogue.load.cache_clear()
    monkeypatch.setattr(catalogue, "path", lambda: tmp_path / "none.json")
    try:
        assert catalogue.load() == {} and catalogue.entries() == [] and catalogue.by_desk_name() == {}
        (tmp_path / "bad.json").write_text("[1,", encoding="utf-8")
        catalogue.load.cache_clear()
        monkeypatch.setattr(catalogue, "path", lambda: tmp_path / "bad.json")
        assert catalogue.load() == {}
    finally:
        catalogue.load.cache_clear()
