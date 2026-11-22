"""The embedding weights are pinned (L-world-class-320, SECURITY.md T23).

A download used to take whatever a Hub repo's `main` held that day, and
trusted it once its files were a believable size. Each catalogue build now
names the commit it is fetched at and the sha256 of every weight file (the
Hub's LFS oid, read 2026-11-21); a download whose weights differ is refused,
its file removed, and the row says so in one sentence."""

from __future__ import annotations

import re
import sys
import types

import pytest

from tessellate.core import embedmodels
from tests import _fake_fastembed as fake

BGE = fake.BGE


@pytest.fixture(autouse=True)
def _clean(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hub"))
    embedmodels.reset_for_tests()
    yield
    embedmodels.reset_for_tests()


def _hub(monkeypatch, tmp_path, asked: dict | None = None, *, tamper: bool = False) -> None:
    """A Hub that writes bge's build at the revision it is asked for."""

    def _download(**kwargs):
        if asked is not None:
            asked.update(kwargs)
        root = fake.snapshot(tmp_path / "hub", BGE, rev=kwargs.get("revision") or "main-head")
        if tamper:
            weights = root / "snapshots" / kwargs["revision"] / embedmodels.build_for(BGE).model_file
            with weights.resolve().open("r+b") as handle:
                handle.write(b"swapped")
        return str(root)

    monkeypatch.setitem(sys.modules, "huggingface_hub", types.SimpleNamespace(snapshot_download=_download))


def test_every_catalogue_build_names_a_commit_and_its_weights_hashes():
    for model in embedmodels.EMBED_MODELS:
        build = model.onnx
        assert re.fullmatch(r"[0-9a-f]{40}", build.revision), model.id
        pinned = dict(build.sha256)
        assert set(pinned) == {build.model_file, *build.extra_files}, model.id
        assert all(re.fullmatch(r"[0-9a-f]{64}", value) for value in pinned.values()), model.id


def test_the_fetch_asks_for_the_pinned_commit(monkeypatch, tmp_path):
    asked: dict = {}
    _hub(monkeypatch, tmp_path, asked)
    embedmodels.fetch(BGE)
    assert asked["revision"] == embedmodels.build_for(BGE).revision


def test_weights_that_match_the_pin_complete(monkeypatch, tmp_path):
    _hub(monkeypatch, tmp_path)
    embedmodels._run_download(fake.pinned_to_fake(embedmodels.EMBED_MODELS_BY_ID["bge-small"]))
    assert embedmodels.current().outcome == "completed", embedmodels.current().step


def test_weights_that_differ_are_refused_and_removed(monkeypatch, tmp_path):
    _hub(monkeypatch, tmp_path, tamper=True)
    model = fake.pinned_to_fake(embedmodels.EMBED_MODELS_BY_ID["bge-small"])
    embedmodels._run_download(model)
    state = embedmodels.current()
    assert state.outcome == "failed"
    assert state.step == (
        "BGE Small (English) arrived with weights that differ from the ones this app was checked with, "
        "so they were removed. Download again, or report it if it keeps happening."
    )
    weights = tmp_path / "hub" / "models--Qdrant--bge-small-en-v1.5-onnx-Q" / "snapshots" / model.onnx.revision
    assert not (weights / model.onnx.model_file).exists()
    assert embedmodels.cache_health(BGE)["state"] == "incomplete"


def test_the_loader_prefers_the_pinned_snapshot(tmp_path):
    """An older snapshot fetched from `main` before the pin stays usable, but
    the verified one is what loads once it is there."""
    build = embedmodels.build_for(BGE)
    fake.snapshot(tmp_path / "hub", BGE, rev="0000-older")
    fake.snapshot(tmp_path / "hub", BGE, rev=build.revision)
    assert embedmodels.snapshot_path(BGE).name == build.revision
