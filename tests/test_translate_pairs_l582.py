"""More translation pairs and a pair picker (L582).

The registry names every direction the app can ask for; the page is told only
the ones whose three files are in the installed folder, so the picker appears
when a second pair is there and never lists one that is not. Real pair models
are not downloaded here: the files are fake bytes in a fake folder.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tessellate.ai import translate
from tessellate.core import extras
from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def folder(tmp_path, monkeypatch):
    monkeypatch.setattr(translate, "_folder", lambda: tmp_path)
    return tmp_path


def _write(folder: Path, tag: str, files=("model", "lex", "vocab")):
    pair = next(p for p in translate.PAIRS if p["from"] + p["to"] == tag)
    for key in files:
        (folder / pair[key]).write_bytes(b"x")


def test_the_registry_has_more_than_one_direction_and_unique_files():
    assert len(translate.PAIRS) > 1
    assert translate.PAIRS[0]["from"] == "en" and translate.PAIRS[0]["to"] == "es"
    assert translate.PAIRS[0]["model"] == "model.enes.intgemm.alphas.bin"
    names = [p[k] for p in translate.PAIRS for k in ("model", "lex", "vocab")]
    assert len(names) == len(set(names))


def test_only_pairs_with_all_three_files_are_offered(folder):
    _write(folder, "enes")
    _write(folder, "enfr")
    _write(folder, "ende", files=("model", "lex"))
    offered = [(p["from"], p["to"]) for p in translate.installed_pairs()]
    assert offered == [("en", "es"), ("en", "fr")]
    assert translate.status()["pairs"] == translate.installed_pairs()


def test_not_installed_offers_no_pairs(monkeypatch):
    monkeypatch.setattr(translate, "_folder", lambda: None)
    assert translate.status()["pairs"] == []


def test_a_registry_file_is_served_by_name_and_nothing_else(folder, monkeypatch):
    _write(folder, "enfr")
    (folder / "installed.json").write_text("{}")
    monkeypatch.setattr(extras, "download_ready", lambda _id: folder)
    got = translate.served("vocab.enfr.spm")
    assert got is not None and got[0] == folder / "vocab.enfr.spm"
    assert translate.served("installed.json") is None
    assert translate.served("../installed.json") is None


def test_the_sheet_and_the_captions_read_the_saved_pair():
    js = frontend_text("translate.js")
    assert 'id = "translate-pair"' in js and "status.pairs.length > 1" in js
    assert 'prefs.set("translate-pair"' in js
    assert 'prefs.get("translate-pair")' in js
    assert 'prefs.get("translate-pair")' in frontend_text("captions.js")
