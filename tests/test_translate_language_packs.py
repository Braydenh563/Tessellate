"""The translator's other languages (L-world-class-41).

French, German, Italian and Portuguese are packages of their own beside the
engine's (which carries Spanish both ways), each with both directions, pinned
to the Mozilla release's files. A pair shows in the picker only when the
engine is installed and one folder holds its three files. The real files were
fetched and each direction translated a sentence in Chromium (the LEDGER row
names the run); these tests read the pins and fake the folders.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tessellate.ai import translate
from tessellate.core import extras


def _written(extra_id: str) -> set[str]:
    return {name for d in extras.EXTRAS_BY_ID[extra_id].downloads for _m, name in d.members}


def _files(pair: dict) -> set[str]:
    return {pair[key] for key in ("model", "lex", "vocab")}


def test_every_direction_is_carried_by_exactly_one_package():
    for pair in translate.PAIRS:
        owners = [i for i in (translate.EXTRA_ID, *translate.LANGUAGE_EXTRAS) if _files(pair) <= _written(i)]
        assert len(owners) == 1, (pair["from"], pair["to"], owners)
    assert len(translate.PAIRS) == 10


@pytest.mark.parametrize("extra_id", translate.LANGUAGE_EXTRAS)
def test_a_language_package_is_its_two_directions_and_nothing_else(extra_id):
    lang = extra_id.split("-")[1]
    extra = extras.EXTRAS_BY_ID[extra_id]
    assert extra.kind == "download" and extra.licence == "MPL-2.0"
    pairs = [p for p in translate.PAIRS if lang in (p["from"], p["to"])]
    assert {(p["from"], p["to"]) for p in pairs} == {("en", lang), (lang, "en")}
    assert _written(extra_id) == set().union(*map(_files, pairs))
    for download in extra.downloads:
        (_member, name), = download.members
        assert download.unpack == "gzip" and download.url.endswith(f"/exported/{name}.gz")
        tag = name.split(".")[-3] if name.startswith("lex.") else name.split(".")[1]
        assert f"/models/{tag[:2]}-{tag[2:]}/" in download.url
        assert len(download.sha256) == 64 and download.size > 100_000


@pytest.fixture()
def folders(tmp_path, monkeypatch):
    engine, french = tmp_path / "engine", tmp_path / "fr"
    engine.mkdir()
    french.mkdir()
    ready = {"translate-fr": french}
    monkeypatch.setattr(translate, "_folder", lambda: engine)
    monkeypatch.setattr(extras, "download_ready", lambda extra_id: ready.get(extra_id))
    return engine, french


def _write(folder: Path, tag: str) -> None:
    pair = next(p for p in translate.PAIRS if p["from"] + p["to"] == tag)
    for name in _files(pair):
        (folder / name).write_bytes(b"x")


def test_a_language_package_folder_adds_its_pairs(folders):
    engine, french = folders
    _write(engine, "enes")
    _write(french, "enfr")
    _write(french, "fren")
    offered = [(p["from"], p["to"]) for p in translate.installed_pairs()]
    assert offered == [("en", "es"), ("en", "fr"), ("fr", "en")]
    path, media = translate.served("vocab.fren.spm")
    assert path == french / "vocab.fren.spm" and media == "application/octet-stream"
    assert translate.served("model.ende.intgemm.alphas.bin") is None
    (french / "installed.json").write_text("{}")
    assert translate.served("installed.json") is None
    assert translate.served("../fr/vocab.fren.spm") is None


def test_a_language_package_without_the_engine_offers_nothing(folders, monkeypatch):
    _engine, french = folders
    _write(french, "enfr")
    monkeypatch.setattr(translate, "_folder", lambda: None)
    assert translate.installed_pairs() == []
    assert translate.served("vocab.enfr.spm") is None


def test_the_worker_keeps_one_pair_loaded():
    """Five models side by side aborted the engine in Chromium (2026-11-22) and
    every later call failed; switching pairs drops the others first."""
    worker = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "translate-worker.js").read_text(encoding="utf-8")
    body = worker[worker.index("async function translateModel") :]
    assert body.index("translateDropOthers(key)") < body.index("translateEngine.models.has(key)")
    drop = worker[worker.index("function translateDropOthers") : worker.index("async function translateModel")]
    assert "model.delete()" in drop and "models.delete(other)" in drop
