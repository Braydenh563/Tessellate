"""Pinned optional pip extras and embedding weights (SECURITY.md T23, L-world-class-320).

A pip extra goes to pip with a version range, never a bare name; an embedding
weights file is hashed after the fetch and refused when it is not the pinned
one, the way a download extra is. Fake transports only: no pip, no Hub.
"""

from __future__ import annotations

import hashlib
import re
import sys
import types

import pytest

from tessellate.core import embedmodels, extras

_BOUND = re.compile(r"(==[\w.]+$|>=[\w.]+,<[\w.]+$)")


@pytest.fixture(autouse=True)
def _clean(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hub"))
    extras.reset_for_tests()
    embedmodels.reset_for_tests()
    yield
    extras.reset_for_tests()
    embedmodels.reset_for_tests()


def _pip_extras():
    return [extra for extra in extras.EXTRAS if extra.kind == "pip"]


def test_every_pip_extra_is_bounded():
    assert _pip_extras()
    for extra in _pip_extras():
        for spec in extras.pip_requirements(extra):
            assert _BOUND.search(spec), f"{extra.id}: {spec} has no version bound"


def test_the_bound_table_has_no_stale_name():
    names = {extras._canonical(extras._requirement_name(p)) for e in _pip_extras() for p in e.packages}
    assert set(extras.PIP_BOUNDS) <= names


def test_the_install_command_hands_pip_the_bounded_names(monkeypatch):
    seen = {}

    class _Capture:
        def __init__(self, command, **kwargs):
            seen["command"] = command
            self.stdout = []

        def wait(self, timeout=None):
            return 0

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def poll(self):
            return 0

    monkeypatch.setattr(extras.subprocess, "Popen", _Capture)
    monkeypatch.setattr(extras.subprocess, "run", lambda *a, **k: types.SimpleNamespace(returncode=0, stdout="", stderr=""))
    for extra in _pip_extras():
        extras._run_install(extra)
        for spec in extras.pip_requirements(extra):
            assert spec in seen["command"], extra.id
        assert not any(arg in extra.packages and not _BOUND.search(arg) for arg in seen["command"]), extra.id
        extras.reset_for_tests()
    documents = extras.pip_requirements(extras.EXTRAS_BY_ID["documents"])
    assert documents == ["markitdown[pdf,docx,pptx]>=0.1.9,<0.2"]


def test_every_catalogue_weights_file_has_a_pinned_digest():
    for model in embedmodels.EMBED_MODELS:
        build = model.onnx
        assert build is not None
        assert re.fullmatch(r"[0-9a-f]{40}", build.revision), model.id
        pinned = dict(build.digests)
        assert build.model_file in pinned, model.id
        for name, digest in pinned.items():
            assert re.fullmatch(r"[0-9a-f]{64}", digest), f"{model.id} {name}"


def _fake_hub(monkeypatch, tmp_path, build, content: bytes):
    """A `snapshot_download` that writes one weights file as a blob plus link."""
    calls = {}

    def _download(repo_id, allow_patterns=(), cache_dir=None, revision=None, **_):
        calls["revision"] = revision
        root = tmp_path / "hub" / f"models--{repo_id.replace('/', '--')}"
        snap = root / "snapshots" / (revision or "main")
        (snap / build.model_file).parent.mkdir(parents=True, exist_ok=True)
        (root / "blobs").mkdir(parents=True, exist_ok=True)
        blob = root / "blobs" / "abc"
        blob.write_bytes(content)
        (snap / build.model_file).symlink_to(blob)

    hub = types.ModuleType("huggingface_hub")
    hub.snapshot_download = _download
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    return calls


def _build(content: bytes) -> embedmodels.OnnxBuild:
    return embedmodels.OnnxBuild(
        "acme/model-onnx",
        "model.onnx",
        revision="a" * 40,
        digests=(("model.onnx", hashlib.sha256(content).hexdigest()),),
    )


def test_a_weights_digest_mismatch_is_refused_and_nothing_is_kept(monkeypatch, tmp_path):
    build = _build(b"the pinned bytes")
    calls = _fake_hub(monkeypatch, tmp_path, build, b"tampered bytes")
    with pytest.raises(embedmodels.WeightsDigestMismatch, match="model.onnx"):
        embedmodels.fetch("acme/model", build)
    assert calls["revision"] == "a" * 40
    root = tmp_path / "hub" / "models--acme--model-onnx"
    assert not (root / "snapshots" / ("a" * 40) / "model.onnx").exists()
    assert list((root / "blobs").iterdir()) == []


def test_matching_weights_are_kept(monkeypatch, tmp_path):
    build = _build(b"the pinned bytes")
    _fake_hub(monkeypatch, tmp_path, build, b"the pinned bytes")
    embedmodels.fetch("acme/model", build)
    assert (tmp_path / "hub" / "models--acme--model-onnx" / "snapshots" / ("a" * 40) / "model.onnx").is_file()


def test_a_mismatch_fails_the_download_task_with_a_reason(monkeypatch, tmp_path):
    model = embedmodels.EMBED_MODELS_BY_ID["minilm"]
    build = _build(b"the pinned bytes")
    _fake_hub(monkeypatch, tmp_path, build, b"tampered bytes")
    monkeypatch.setattr(embedmodels, "build_for", lambda repo: build)
    monkeypatch.setattr(embedmodels, "fetch", lambda repo, onnx=None, _f=embedmodels.fetch: _f(repo, build))
    embedmodels._run_download(model)
    state = embedmodels.current()
    assert state.outcome == "failed"
    assert "checksum" in state.step
