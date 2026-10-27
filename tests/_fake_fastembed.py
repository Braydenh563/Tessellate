"""A stand-in for fastembed and its model cache, for the embedding tests.

No test downloads a model or imports ONNX Runtime: `install` puts a fake
`fastembed` in `sys.modules` whose `TextEmbedding` records every load and
returns unit vectors, and `snapshot` lays out an ONNX build in the hub
cache the way `huggingface_hub` writes one (blobs behind symlinks, weights
sparse so a 66 MB file costs nothing).
"""

from __future__ import annotations

import math
import sys
import types
from enum import Enum
from pathlib import Path

import numpy as np

from tessellate.core import embedmodels

BGE = "BAAI/bge-small-en-v1.5"
#: Over the catalogue's floor for every small model (a share of "~67 MB").
WEIGHT_BYTES = 120 * 1024 * 1024


class PoolingType(str, Enum):
    CLS = "CLS"
    MEAN = "MEAN"
    LAST_TOKEN = "LAST_TOKEN"
    DISABLED = "DISABLED"


class ModelSource:
    def __init__(self, hf=None, url=None):  # noqa: ANN001
        self.hf = hf
        self.url = url


class FakeTextEmbedding:
    """Records each load's arguments in `loads`; a load raises while
    `local_works` is false (files on disk that will not open)."""

    loads: list[dict] = []
    custom: list[dict] = []
    embeds: list[list[str]] = []
    local_works = True
    dim = 384

    def __init__(self, model_name, cache_dir=None, threads=None, local_files_only=False, specific_model_path=None, **kwargs):  # noqa: ANN001
        type(self).loads.append(
            {"model_name": model_name, "threads": threads, "local_files_only": local_files_only, "path": specific_model_path}
        )
        if not type(self).local_works:
            raise OSError("cache incomplete")
        self.model_name = model_name

    def embed(self, documents, batch_size=256, parallel=None, **kwargs):  # noqa: ANN001, ANN201
        texts = list(documents)
        type(self).embeds.append(texts)
        for _ in texts:
            yield np.full(type(self).dim, 1 / math.sqrt(type(self).dim), dtype="float32")

    @classmethod
    def add_custom_model(cls, **kwargs) -> None:  # noqa: ANN003
        if any(entry["model"] == kwargs["model"] for entry in cls.custom):
            raise ValueError(f"Model {kwargs['model']} is already registered")
        cls.custom.append(kwargs)


def install(monkeypatch) -> type[FakeTextEmbedding]:  # noqa: ANN001
    """A fake `fastembed` package for the length of one test."""
    package = types.ModuleType("fastembed")
    package.TextEmbedding = FakeTextEmbedding
    common = types.ModuleType("fastembed.common")
    description = types.ModuleType("fastembed.common.model_description")
    description.PoolingType = PoolingType
    description.ModelSource = ModelSource
    package.common = common
    common.model_description = description
    monkeypatch.setitem(sys.modules, "fastembed", package)
    monkeypatch.setitem(sys.modules, "fastembed.common", common)
    monkeypatch.setitem(sys.modules, "fastembed.common.model_description", description)
    from tessellate.ai import embeddings

    monkeypatch.setattr(embeddings, "_registered", set())
    FakeTextEmbedding.loads = []
    FakeTextEmbedding.custom = []
    FakeTextEmbedding.embeds = []
    FakeTextEmbedding.local_works = True
    return FakeTextEmbedding


def snapshot(hub: Path, repo: str = BGE, *, weights: int | None = WEIGHT_BYTES, skip: tuple[str, ...] = (), rev: str = "abc123") -> Path:
    """`repo`'s ONNX build in the cache at `hub`; returns its folder
    (`models--org--name`). `skip` leaves files out by name ("model weights"
    for the ONNX file)."""
    build = embedmodels.build_for(repo)
    root = hub / ("models--" + build.source.replace("/", "--"))
    snap = root / "snapshots" / rev
    blobs = root / "blobs"
    snap.mkdir(parents=True, exist_ok=True)
    blobs.mkdir(parents=True, exist_ok=True)
    texts = {
        "config.json": '{"hidden_size": 384}',
        "tokenizer.json": "{}",
        "tokenizer_config.json": "{}",
        "special_tokens_map.json": "{}",
    }
    for name, text in texts.items():
        if name not in skip:
            _link(snap, blobs, name, text.encode())
    for name in build.extra_files:
        if name not in skip:
            _link(snap, blobs, name, b"x" * 16)
    if weights is not None and "model weights" not in skip:
        blob = blobs / "weights-blob"
        with blob.open("wb") as handle:
            handle.truncate(weights)
        target = snap / build.model_file
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(blob)
    return root


def _link(snap: Path, blobs: Path, name: str, data: bytes) -> None:
    blob = blobs / (name.replace("/", "_") + "-blob")
    blob.write_bytes(data)
    (snap / name).parent.mkdir(parents=True, exist_ok=True)
    (snap / name).symlink_to(blob)


def fake_fetch(monkeypatch, hub: Path, *, works: bool = True) -> list[str]:  # noqa: ANN001
    """`embedmodels.fetch` as a download that lands a whole snapshot (and
    mends files that would not open), or fails like no network. Returns the
    list of repos fetched."""
    fetched: list[str] = []

    def fetch(repo, build=None):  # noqa: ANN001, ANN202
        fetched.append(repo)
        if not works:
            raise OSError("no network")
        snapshot(hub, repo, rev="fetched")
        FakeTextEmbedding.local_works = True

    monkeypatch.setattr(embedmodels, "fetch", fetch)
    return fetched
