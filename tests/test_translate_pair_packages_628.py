"""L-world-class-628: each extra language is a package of its own.

Pinning all eight directions into the one `translate` extra (L-world-class-41)
bumped its version, so a person who had English to Spanish installed saw the
package as not installed and was asked for 209 MB again. The base package is
back to the engine and English to Spanish at its old version, so that install
still counts; every other language is its own small download beside it."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tessellate.ai import translate
from tessellate.core import extra_downloads, extras

ENGINE = {"bergamot-translator-worker.js", "bergamot-translator-worker.wasm", "LICENSE"}


def _files(extra) -> set[str]:
    return {file for download in extra.downloads for _member, file in download.members}


def _pair(tag: str) -> dict:
    return next(p for p in translate.PAIRS if p["from"] + "-" + p["to"] == tag)


def test_the_base_package_is_the_english_to_spanish_install_people_already_have():
    base = extras.EXTRAS_BY_ID[translate.EXTRA_ID]
    assert base.version == "0.4.9-enes-1"
    en_es = _pair("en-es")
    assert _files(base) == ENGINE | {en_es["model"], en_es["lex"], en_es["vocab"]}


def test_an_install_from_before_the_pairs_still_counts(tmp_path, monkeypatch):
    """The marker an English to Spanish install wrote names this version and
    these files: it reads as installed, so nothing downloads again."""
    monkeypatch.setattr(extra_downloads, "root_dir", lambda: tmp_path)
    base = extras.EXTRAS_BY_ID[translate.EXTRA_ID]
    folder = tmp_path / base.id
    folder.mkdir()
    names = sorted(_files(base))
    for name in names:
        (folder / name).write_bytes(b"x")
    (folder / extra_downloads.MARKER).write_text(json.dumps({"version": "0.4.9-enes-1", "files": names}))
    assert extra_downloads.is_installed(base)


def test_every_other_direction_is_pinned_in_exactly_one_language_package():
    owners: dict[str, list[str]] = {}
    for extra in extras.EXTRAS:
        if extra.id == translate.EXTRA_ID or extra.id.startswith("translate-"):
            for name in _files(extra):
                owners.setdefault(name, []).append(extra.id)
    for pair in translate.PAIRS:
        tag = pair["from"] + "-" + pair["to"]
        for key in ("model", "lex", "vocab"):
            assert owners.get(pair[key]) == [pair["extra"]], (tag, key)
    assert {p["extra"] for p in translate.PAIRS} - {translate.EXTRA_ID}, "no language package"
    for extra_id in {p["extra"] for p in translate.PAIRS} - {translate.EXTRA_ID}:
        extra = extras.EXTRAS_BY_ID[extra_id]
        assert extra.kind == "download" and not (_files(extra) & ENGINE)
        assert sum(d.size for d in extra.downloads) < 60_000_000


@pytest.fixture()
def installed(tmp_path, monkeypatch):
    """`extras.download_ready` answering from folders under tmp_path, one per
    extra id, for the ids passed to the returned function."""
    ready: set[str] = set()

    def ready_folder(extra_id):
        return tmp_path / extra_id if extra_id in ready else None

    monkeypatch.setattr(extras, "download_ready", ready_folder)

    def install(*tags: str) -> None:
        for tag in tags:
            pair = _pair(tag)
            folder = tmp_path / pair["extra"]
            folder.mkdir(exist_ok=True)
            for key in ("model", "lex", "vocab"):
                (folder / pair[key]).write_bytes(b"x")
            ready.add(pair["extra"])

    return install, ready, tmp_path


def test_a_language_package_adds_its_pairs_to_the_picker(installed):
    install, _ready, _root = installed
    install("en-es")
    assert [(p["from"], p["to"]) for p in translate.installed_pairs()] == [("en", "es")]
    install("en-fr", "fr-en")
    assert [(p["from"], p["to"]) for p in translate.installed_pairs()] == [("en", "es"), ("en", "fr"), ("fr", "en")]
    assert translate.status()["installed"] is True


def test_a_language_package_without_the_engine_offers_nothing(installed):
    install, _ready, _root = installed
    install("en-de", "de-en")
    assert translate.installed_pairs() == []
    assert translate.status()["installed"] is False


def test_each_file_is_served_from_its_own_package(installed):
    install, _ready, root = installed
    install("en-es", "en-fr")
    (root / "translate" / "bergamot-translator-worker.js").write_text("//")
    got = translate.served("vocab.enfr.spm")
    assert got is not None and got[0] == root / _pair("en-fr")["extra"] / "vocab.enfr.spm"
    assert translate.served("bergamot-translator-worker.js")[0] == root / "translate" / "bergamot-translator-worker.js"
    assert translate.served("vocab.ende.spm") is None
    assert translate.served("../translate/installed.json") is None


def test_the_language_packages_are_offered_together_and_not_forced_on_spanish():
    languages = extras.BUNDLES_BY_ID["languages"].extras
    assert not [e for e in languages if e.startswith("translate-")]
    more = extras.BUNDLES_BY_ID["translate-languages"].extras
    assert set(more) == {p["extra"] for p in translate.PAIRS}


def test_the_readme_and_the_guide_name_the_language_packages():
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "209 MB" not in readme
    from tessellate.ai import help_topics_more

    body = next(t for t in help_topics_more.MORE_TOPICS if t["id"] == "translate-offline")["body"]
    assert "209 MB" not in body and "More translation languages" in body
