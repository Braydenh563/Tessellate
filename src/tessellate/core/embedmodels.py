"""The embedding models on this machine, and getting rid of the ones you don't want.

Asked for directly, alongside a question worth answering here because the
answer is the reason this file is small:

> *"the embedding model doesn't redownload every time I load up the app
> right?"*

**No.** The built-in engine is fastembed (ONNX Runtime), and the model is a
snapshot in the HuggingFace hub cache, a directory on disk: fetched once, by
`fetch` below, and from then on loaded from that folder with no network at
all (`ai/embeddings.py` hands fastembed the snapshot's path). Nothing asks the
hub whether a cached model is current; Reinstall is the one way back online.

What there was no way to do was *see* that, or undo it. A model is the largest
thing this app ever puts on a disk and it arrived invisibly, with no size, no
list and no way to remove it short of knowing where HuggingFace keeps its
cache. Hence: a list, a size, and install / reinstall / remove.

**The security property is `extras.py`'s, and for the same reason.** A repo id
from an HTTP request is a path fetched and written to disk, so the request
names an entry in the allowlist below and the repo id is never anything the
client sent. Removal deletes a directory, which is *why* the id may not be
client text, because a path from a request is a path traversal waiting to
happen. Every deletion is checked to be inside the cache root as well.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import re
import shutil
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from tessellate.core import egress

logger = logging.getLogger("tessellate.embedmodels")

#: The built-in engine's name, stored as the `embedding_backend` preference
#: and in front of every vector's `model_version` (`ai/embeddings.py`).
BUILTIN_BACKEND = "fastembed"
#: What the preference said before fastembed replaced sentence-transformers
#: (2026-10-27). The same models in the same space, so a saved setting reads as
#: the new engine; migration f1b3c5d7e9a2 renames the stored vectors of the two
#: models whose engines were measured equal (its docstring has the numbers) and
#: the backfill embeds the notes of any other model again.
LEGACY_BACKENDS = frozenset({"sentence-transformers"})
#: The models whose vectors from the old engine are kept (renamed, never
#: embedded again): measured equal to fastembed's. Mirrors the migration's
#: list (`tests/test_fastembed_vector_ids.py` holds the two together).
VECTORS_KEPT = ("BAAI/bge-small-en-v1.5", "intfloat/multilingual-e5-small")


def backend_name(value: object) -> str:
    """The engine a saved `embedding_backend` means: "ollama", or the
    built-in one for anything else (an old "sentence-transformers" included),
    which is what every `!= "ollama"` check already read it as."""
    return "ollama" if value == "ollama" else BUILTIN_BACKEND


@dataclass(frozen=True)
class OnnxBuild:
    """Where a model's ONNX files are and how fastembed reads them.

    `source` is the Hub repo the files come from (fastembed's own export,
    `Qdrant/...`, for most of the catalogue); `model_file` and `extra_files`
    are what a snapshot must hold besides its tokenizer and config. `pooling`
    is empty for a model fastembed knows by name, else how the loader
    registers it ("CLS", "MEAN"), with `dim` its width."""

    source: str
    model_file: str = "onnx/model.onnx"
    extra_files: tuple[str, ...] = ()
    pooling: str = ""
    dim: int = 0


#: The small files every snapshot is fetched with: fastembed reads the
#: tokenizer from these, and a Pooling config says how a typed model pools.
CONFIG_FILES = ("config.json", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "1_Pooling/config.json")


@dataclass(frozen=True)
class EmbedModel:
    """One embedding model, and the honest description of the trade."""

    #: Stable id used by the API. Never a repo id from the client.
    id: str
    #: The HuggingFace repo. Only ever read from this file.
    repo: str
    label: str
    #: What choosing it buys, in the user's terms.
    about: str
    #: Rough download size, so nobody starts one by accident on a phone tether.
    size: str
    #: True for the one the app loads unless told otherwise.
    default: bool = False
    #: INBOX 700's facts, shown on the row: parameters, languages, how much
    #: text one vector reads, and the licence as its repository states it
    #: (each read from the Hub's own metadata, 2026-10-06).
    params: str = ""
    languages: str = "English"
    context: str = "512 tokens"
    licence: str = ""
    #: One line: who should pick it.
    best_for: str = ""
    #: Whether the app may fetch and switch to it in one press. Only for a
    #: licence that allows it (Apache-2.0, MIT) **and** a model that loads
    #: without running code from its repository; anything else links to
    #: `terms_url` and says why.
    one_press: bool = True
    terms_url: str = ""
    why_not: str = ""
    #: Put in front of every text this model embeds. The E5 family and
    #: nomic were trained with one; without it their matches are measurably
    #: worse. One prefix for notes and questions alike: the app embeds both
    #: through one call, and the symmetric form is the one E5's card names
    #: for similarity between texts of the same kind.
    prefix: str = ""
    #: The ONNX build fastembed runs (`build_for`); None for a typed repo,
    #: whose files are read from its own snapshot.
    onnx: OnnxBuild | None = None


#: The allowlist, and the catalogue Settings, Models offers (INBOX 700, the
#: owner: "add more embedding model options ... research the best ones
#: available today"). Each entry answers a different question: the sane
#: default, very little disk, long notes, many languages, the best matches a
#: laptop can run. Ordered small to large so the list reads as a trade.
EMBED_MODELS: tuple[EmbedModel, ...] = (
    EmbedModel(
        id="minilm",
        repo="sentence-transformers/all-MiniLM-L6-v2",
        label="MiniLM L6 (English)",
        about="Smaller and quicker, and a little blunter about what counts as "
        "similar. The one to keep on a machine that is short of disk.",
        size="~90 MB",
        params="22M",
        context="256 tokens",
        licence="Apache-2.0",
        best_for="An old or small machine: the fastest here, a little less precise.",
        onnx=OnnxBuild("Qdrant/all-MiniLM-L6-v2-onnx", "model.onnx"),
    ),
    EmbedModel(
        id="bge-small",
        repo="BAAI/bge-small-en-v1.5",
        label="BGE Small (English)",
        about="The default. Fast enough to embed a note as you save it, and "
        "good enough that searching by meaning beats searching by keyword.",
        size="~67 MB",
        default=True,
        params="33M",
        licence="MIT",
        best_for="Most notebooks in English: quick on any laptop, good matches.",
        onnx=OnnxBuild("Qdrant/bge-small-en-v1.5-onnx-Q", "model_optimized.onnx"),
    ),
    EmbedModel(
        id="me5-small",
        repo="intfloat/multilingual-e5-small",
        label="Multilingual E5 Small",
        about="About a hundred languages in a small model, so notes in "
        "several languages find each other.",
        size="~470 MB",
        params="118M",
        languages="About 100 languages",
        licence="MIT",
        best_for="Notes in more than one language on an ordinary laptop.",
        prefix="query: ",
        onnx=OnnxBuild("intfloat/multilingual-e5-small", pooling="MEAN", dim=384),
    ),
    EmbedModel(
        id="bge-base",
        repo="BAAI/bge-base-en-v1.5",
        label="BGE Base (English)",
        about="Noticeably better matches on long notes, at roughly three times "
        "the size and about twice the time to embed one.",
        size="~220 MB",
        params="110M",
        licence="MIT",
        best_for="English notes when better matches are worth a slower save.",
        onnx=OnnxBuild("Qdrant/bge-base-en-v1.5-onnx-Q", "model_optimized.onnx"),
    ),
    EmbedModel(
        id="nomic-v1.5",
        repo="nomic-ai/nomic-embed-text-v1.5",
        label="Nomic Embed Text v1.5 (English)",
        about="Reads up to 8,000 tokens at once, so a long note is one vector "
        "of the whole rather than of its start.",
        size="~550 MB",
        params="137M",
        context="8,192 tokens",
        licence="Apache-2.0",
        best_for="Long notes and documents in English.",
        one_press=False,
        terms_url="https://huggingface.co/nomic-ai/nomic-embed-text-v1.5",
        why_not="Not offered built in yet. The same model is nomic-embed-text in Ollama.",
        prefix="search_query: ",
        onnx=OnnxBuild("nomic-ai/nomic-embed-text-v1.5"),
    ),
    EmbedModel(
        id="qwen3-0.6b",
        repo="Qwen/Qwen3-Embedding-0.6B",
        label="Qwen3 Embedding 0.6B",
        about="The best matches here on the public benchmarks, in over a "
        "hundred languages, at the cost of memory and a slower save.",
        size="~2.4 GB",
        params="596M",
        languages="Over 100 languages",
        context="32,768 tokens",
        licence="Apache-2.0",
        best_for="The best matches, with 8 GB of memory or more to spare.",
        onnx=OnnxBuild("Qdrant/Qwen3-Embedding-0.6B-onnx", extra_files=("onnx/model.onnx_data",)),
    ),
    EmbedModel(
        id="bge-m3",
        repo="BAAI/bge-m3",
        label="BGE M3 (multilingual)",
        about="A large multilingual model that reads long notes whole.",
        size="~2.3 GB",
        params="568M",
        languages="Over 100 languages",
        context="8,192 tokens",
        licence="MIT",
        best_for="Long notes in many languages on a well-equipped machine.",
        onnx=OnnxBuild(
            "BAAI/bge-m3", extra_files=("onnx/model.onnx_data", "onnx/Constant_7_attr__value"), pooling="CLS", dim=1024
        ),
    ),
    EmbedModel(
        id="embeddinggemma",
        repo="google/embeddinggemma-300m",
        label="EmbeddingGemma 300M",
        about="Google's small multilingual model, strong for its size.",
        size="~1.2 GB",
        params="303M",
        languages="Over 100 languages",
        context="2,048 tokens",
        licence="Gemma terms",
        best_for="Multilingual notes, once you have accepted Google's terms.",
        one_press=False,
        terms_url="https://ai.google.dev/gemma/terms",
        why_not="Under Google's Gemma terms rather than an open licence, and "
        "gated on the Hub: read and accept them first, then it is "
        "embeddinggemma in Ollama.",
        onnx=OnnxBuild("onnx-community/embeddinggemma-300m-ONNX", extra_files=("onnx/model.onnx_data",)),
    ),
)

EMBED_MODELS_BY_ID = {model.id: model for model in EMBED_MODELS}
EMBED_MODELS_BY_REPO = {model.repo: model for model in EMBED_MODELS}
DEFAULT_REPO = next(model.repo for model in EMBED_MODELS if model.default)


@dataclass(frozen=True)
class OllamaEmbedModel:
    """An embedding model Ollama serves, by its Ollama name."""

    name: str
    label: str
    size: str
    languages: str
    context: str
    licence: str
    best_for: str
    one_press: bool = True
    terms_url: str = ""
    why_not: str = ""


#: Through Ollama: the model lives in Ollama, so Tessellate stays near 100 MB
#: of memory. Licences are the upstream repositories' (read on the Hub,
#: 2026-10-06); sizes are Ollama's library pages'.
OLLAMA_EMBED_MODELS: tuple[OllamaEmbedModel, ...] = (
    OllamaEmbedModel(
        "granite-embedding", "Granite Embedding 30M", "~63 MB", "English", "512 tokens",
        "Apache-2.0", "The smallest here: a quick English index with Ollama.",
    ),
    OllamaEmbedModel(
        "nomic-embed-text", "Nomic Embed Text", "~274 MB", "English", "8,192 tokens",
        "Apache-2.0", "Long English notes, and the usual Ollama choice.",
    ),
    OllamaEmbedModel(
        "qwen3-embedding:0.6b", "Qwen3 Embedding 0.6B", "~639 MB", "Over 100 languages",
        "32,768 tokens", "Apache-2.0", "The best matches through Ollama on a laptop.",
    ),
    OllamaEmbedModel(
        "mxbai-embed-large", "mxbai Embed Large", "~670 MB", "English", "512 tokens",
        "Apache-2.0", "Precise English matches on short notes.",
    ),
    OllamaEmbedModel(
        "bge-m3", "BGE M3", "~1.2 GB", "Over 100 languages", "8,192 tokens",
        "MIT", "Long notes in many languages.",
    ),
    OllamaEmbedModel(
        "snowflake-arctic-embed2", "Snowflake Arctic Embed 2", "~1.2 GB", "About 75 languages",
        "8,192 tokens", "Apache-2.0", "Multilingual search with long context.",
    ),
    OllamaEmbedModel(
        "embeddinggemma", "EmbeddingGemma", "~622 MB", "Over 100 languages", "2,048 tokens",
        "Gemma terms", "Multilingual notes, once you have accepted Google's terms.",
        one_press=False,
        terms_url="https://ai.google.dev/gemma/terms",
        why_not="Under Google's Gemma terms rather than an open licence: read "
        "them, then pull it in Ollama yourself and pick it below.",
    ),
)

OLLAMA_EMBED_MODELS_BY_NAME = {model.name: model for model in OLLAMA_EMBED_MODELS}


def prefix_for(repo: str) -> str:
    """The text a built-in model wants in front of everything it embeds."""
    model = EMBED_MODELS_BY_REPO.get(repo)
    return model.prefix if model else ""


def catalogue() -> list[dict]:
    """Every choice Settings, Models offers, built-in and Ollama, as rows.

    `id` is what `POST /embedding-models/use` takes: an allowlist id for a
    built-in model, `ollama:<name>` for an Ollama one; never a repo id."""
    rows = []
    for model in EMBED_MODELS:
        health = cache_health(model.repo)
        rows.append(
            {
                "id": model.id,
                "backend": BUILTIN_BACKEND,
                "model": model.repo,
                "label": model.label,
                "size": model.size,
                "params": model.params,
                "languages": model.languages,
                "context": model.context,
                "licence": model.licence,
                "best_for": model.best_for,
                "one_press": model.one_press,
                "terms_url": model.terms_url,
                "why_not": model.why_not,
                "default": model.default,
                "downloaded": health["state"] == "complete",
                "files_missing": health["state"] == "incomplete",
                "missing": health["missing"],
                "state": snapshot_state(model.repo),
                "on_disk": disk_size_of(model.repo),
            }
        )
    rows.extend(
        {
            "id": f"ollama:{model.name}",
            "backend": "ollama",
            "model": model.name,
            "label": model.label,
            "size": model.size,
            "params": "",
            "languages": model.languages,
            "context": model.context,
            "licence": model.licence,
            "best_for": model.best_for,
            "one_press": model.one_press,
            "terms_url": model.terms_url,
            "why_not": model.why_not,
            "default": False,
            "downloaded": False,
            "files_missing": False,
            "missing": [],
            "state": "absent",
            "on_disk": "",
        }
        for model in OLLAMA_EMBED_MODELS
    )
    return rows


def resolve_choice(choice_id: str) -> tuple[str, str] | None:
    """`(backend, model)` for a catalogue id, or None for anything else,
    including an entry whose licence or loading rules forbid one press."""
    if choice_id.startswith("ollama:"):
        entry = OLLAMA_EMBED_MODELS_BY_NAME.get(choice_id.removeprefix("ollama:"))
        return ("ollama", entry.name) if entry and entry.one_press else None
    model = EMBED_MODELS_BY_ID.get(choice_id)
    return (BUILTIN_BACKEND, model.repo) if model and model.one_press else None


@dataclass
class DownloadState:
    """What one download is doing, for `/tasks` and the panel."""

    running: bool = False
    model_id: str = ""
    step: str = ""
    log: list[str] = field(default_factory=list)
    started: float = 0.0
    #: The model's name for the Background tasks row: a catalogue label, or
    #: the repo a person typed into Pull a model by name (INBOX 700).
    label: str = ""
    outcome: str = ""  # "" while running, then completed | failed
    #: Someone pressed Quit. Checked between download attempts, see
    #: `cancel()` for why that is the only place it can be checked.
    cancel_requested: bool = False
    #: The app began this one itself because the files on disk were
    #: incomplete (`repair`), so the row says "Repairing", not "Downloading".
    repair: bool = False


_state = DownloadState()
_lock = threading.Lock()

MAX_LOG_LINES = 60


def cache_root() -> Path:
    """Where HuggingFace keeps downloaded models on this machine.

    Read from the environment exactly as `huggingface_hub` reads it, rather
    than imported from it: this has to answer "how much disk is this using"
    on an install where `fastembed` was never installed, which is the install
    where the question matters most.
    """
    for name in ("HF_HUB_CACHE", "HUGGINGFACE_HUB_CACHE"):
        value = os.environ.get(name)
        if value:
            return Path(value)
    home = os.environ.get("HF_HOME")
    if home:
        return Path(home) / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"


def _folder_for(source: str) -> Path:
    """The cache directory for one Hub repo. `org/name` becomes
    `models--org--name`: HuggingFace's own scheme, and the reason this is a
    function rather than a string in the dataclass: it is their layout, not
    ours, and if it ever changes there is one place to say so."""
    return cache_root() / ("models--" + source.replace("/", "--"))


def _snapshots(source: str) -> list[Path]:
    snapshots = _folder_for(source) / "snapshots"
    try:
        return sorted(path for path in snapshots.iterdir() if path.is_dir())
    except OSError:
        return []


def _typed_build(repo: str) -> OnnxBuild:
    """A repo outside the catalogue, read from what its snapshot holds: the
    ONNX file at `onnx/model.onnx` (the usual export) or the repo's root, and
    the external weights beside it when the export split them out."""
    found = [snap for snap in _snapshots(repo) if (snap / "onnx" / "model.onnx").is_file() or (snap / "model.onnx").is_file()]
    model_file = "model.onnx" if found and not (found[0] / "onnx" / "model.onnx").is_file() else "onnx/model.onnx"
    split = any((snap / f"{model_file}_data").is_file() for snap in found)
    return OnnxBuild(repo, model_file, (f"{model_file}_data",) if split else ())


def build_for(repo: str) -> OnnxBuild:
    """The ONNX build a built-in model runs from: the catalogue's, or a typed
    repo's own files."""
    entry = EMBED_MODELS_BY_REPO.get(repo)
    if entry is not None and entry.onnx is not None:
        return entry.onnx
    return _typed_build(repo)


def model_folder(repo: str) -> Path:
    """The cache folder `repo`'s files live in (its ONNX source's)."""
    return _folder_for(build_for(repo).source)


def _model_dir(model: EmbedModel) -> Path:
    return _folder_for((model.onnx or build_for(model.repo)).source)


def snapshot_state(repo: str) -> str:
    """"ready" when a snapshot holds the model's ONNX file and its config,
    "partial" when the cache folder exists without them (the folder an
    interrupted first request leaves, or weights cut off before the config),
    "absent" when there is no folder at all.

    Both files, because the load runs offline once the folder is there: weights
    alone fail with `EmbeddingCacheBroken` and the person is told to reinstall
    (INBOX 1288)."""
    build = build_for(repo)
    if not _folder_for(build.source).is_dir():
        return "absent"
    for snapshot in _snapshots(build.source):
        if _file_size(snapshot / build.model_file) and (snapshot / "config.json").is_file():
            return "ready"
    return "partial"


def is_downloaded(repo: str) -> bool:
    """Whether `repo` is complete in the cache: a snapshot holding a model
    file and its config, not merely the folder an interrupted first request
    left behind."""
    return snapshot_state(repo) == "ready"


def disk_size_of(repo: str) -> str:
    """What the model's cache folder takes on disk, in words, or "" for none."""
    folder = model_folder(repo)
    return _human_size(_dir_size(folder)) if folder.is_dir() else ""


#: What the old engine (sentence-transformers) kept in the cache: PyTorch
#: weights, which fastembed never reads. The ONNX build is a different file in
#: a different folder (or, for E5 and BGE M3, beside these in the same one).
_TORCH_WEIGHTS = ("model.safetensors", "pytorch_model.bin")
#: What the engine's own download adds to a model's: fastembed 0.9.1 and the
#: wheels it needs on Linux, measured 2026-10-27 (57 MB, rounded up).
_ENGINE_BYTES = 60 * 1024**2


def _torch_files(model: EmbedModel) -> list[Path]:
    """The old engine's weight files for one catalogue model, as they sit in
    its repo's snapshots (links into the blob store)."""
    found = []
    for snapshot in _snapshots(model.repo):
        found.extend(snapshot / name for name in _TORCH_WEIGHTS if _file_size(snapshot / name))
    return found


def _round_download(size: int) -> str:
    """`about 130 MB`, rounded to ten, or `about 2.4 GB` for a large one."""
    megabytes = round(size / 1024**2 / 10) * 10
    return f"about {megabytes} MB" if megabytes < 1000 else f"about {size / 1024**3:.1f} GB"


def engine_moved(repo: str) -> dict | None:
    """Whether this computer holds the old engine's copy of `repo` but not the
    new engine's, and what the person is told then (the owner's decision,
    2026-10-27: keep the ask, since nothing downloads without a yes, and say
    the engine moved).

    `vectors` is "kept" for a model whose notes were renamed by migration
    f1b3c5d7e9a2 (`VECTORS_KEPT`) and "again" for one whose notes the
    backfill embeds again; `download` is the one-time size in words, the
    engine plus the model's ONNX build. None when the new build is here, when
    there is no old copy, or for a model outside the catalogue."""
    entry = EMBED_MODELS_BY_REPO.get(repo)
    if entry is None or entry.onnx is None or is_downloaded(repo) or not _torch_files(entry):
        return None
    return {
        "vectors": "kept" if repo in VECTORS_KEPT else "again",
        "download": _round_download(_ENGINE_BYTES + _declared_bytes(entry.size)),
    }


def _shares_onnx_folder(model: EmbedModel) -> bool:
    """Whether the old copy's folder is also a folder the new engine reads
    (E5, BGE M3 and Gemma's ONNX sources are their own repos), so only the
    weight files may go."""
    folder = _folder_for(model.repo)
    return any(_folder_for(other.onnx.source) == folder for other in EMBED_MODELS if other.onnx is not None)


def legacy_files() -> list[dict]:
    """The old engine's model files still on disk, one row per catalogue model
    (`id`, `label`, the `folder` name, `bytes` and `size`): what Settings,
    Search and index offers to remove once the new build is in place."""
    rows = []
    for model in EMBED_MODELS:
        files = _torch_files(model)
        if not files:
            continue
        folder = _folder_for(model.repo)
        if _shares_onnx_folder(model):
            size = sum({path.resolve(): _file_size(path) for path in files}.values())
        else:
            size = _dir_size(folder)
        rows.append({"id": model.id, "label": model.label, "folder": folder.name, "bytes": size, "size": _human_size(size)})
    return rows


def remove_legacy(model_id: str) -> tuple[bool, str]:
    """Delete one catalogue model's old engine files, by allowlist id: the
    whole old folder, or only the weights when the new engine reads the same
    folder. Inside the cache root or nothing."""
    model = EMBED_MODELS_BY_ID.get(model_id)
    if model is None or model.onnx is None:
        return False, "No such embedding model."
    files = _torch_files(model)
    if not files:
        return False, "Those files are not on this computer."
    if _state.running:
        return False, "A model is downloading right now. Try again when it has finished."
    root = cache_root().resolve()
    folder = _folder_for(model.repo)
    try:
        if not folder.resolve().is_relative_to(root):
            return False, "Refusing to delete outside the model cache."
        if _shares_onnx_folder(model):
            _unlink_weights(files, root)
        else:
            shutil.rmtree(folder)
    except OSError:
        logger.warning("couldn't remove the old files of %s", model.id, exc_info=True)
        return False, "Couldn't remove them: see Settings, Logs for why."
    return True, f"The old files for {model.label} are removed."


def _unlink_weights(files: list[Path], root: Path) -> None:
    """Remove weight links and the blobs behind them, a blob only when no other
    link in the cache still points at it."""
    targets = {path.resolve() for path in files}
    for path in files:
        path.unlink()
    still_linked = {
        link.resolve() for link in root.glob("models--*/snapshots/*/**/*") if link.is_symlink()
    }
    for target in targets - still_linked:
        if target.is_relative_to(root) and target.is_file():
            target.unlink()


#: A weights file smaller than this share of the catalogue's stated size is
#: truncated. Generous on purpose (the stated size is approximate), so only a
#: file that is plainly short is refused.
_WEIGHTS_FLOOR_SHARE = 0.3


def _declared_bytes(size: str) -> int:
    """`~130 MB` or `~1.2 GB` as bytes, 0 when it says nothing."""
    found = re.search(r"([\d.]+)\s*(KB|MB|GB)", size or "", re.IGNORECASE)
    if not found:
        return 0
    unit = {"kb": 1024, "mb": 1024**2, "gb": 1024**3}[found.group(2).lower()]
    return int(float(found.group(1)) * unit)


def _file_size(path: Path) -> int:
    """The size of what a link in the snapshot points at; 0 for a missing
    file or a link whose blob is gone (the broken state an interrupted or
    cleaned cache leaves)."""
    try:
        return path.stat().st_size if path.is_file() else 0
    except OSError:
        return 0


def _weights_floor(repo: str) -> int:
    """The fewest bytes `repo`'s weights may hold. A model outside the
    catalogue (typed by name) has no stated size, so only "non-empty" can be
    asked of it."""
    entry = EMBED_MODELS_BY_REPO.get(repo)
    return max(int(_declared_bytes(entry.size) * _WEIGHTS_FLOOR_SHARE) if entry else 0, 1)


def _snapshot_missing(snapshot: Path, build: OnnxBuild, floor: int) -> list[str]:
    """What this one snapshot lacks to load: empty when it is whole. fastembed
    reads `config.json`, `tokenizer.json` and the ONNX file (with its external
    weights, when the export split them out)."""
    missing = [name for name in ("config.json", "tokenizer.json") if _file_size(snapshot / name) == 0]
    missing.extend(name for name in build.extra_files if _file_size(snapshot / name) == 0)
    weights = sum(_file_size(snapshot / name) for name in (build.model_file, *build.extra_files))
    if _file_size(snapshot / build.model_file) == 0:
        missing.append("model weights")
    elif weights < floor:
        missing.append("model weights (cut short)")
    return missing


def cache_health(repo: str) -> dict:
    """Whether `repo`'s cache can load: `absent` (no folder), `complete`, or
    `incomplete` with `missing` naming what is not there (101c).

    The owner (2026-10-07): an empty or partial model folder was treated as
    present and failed with `EmbeddingCacheBroken`. A folder is not a model:
    it needs `config.json`, a tokenizer, and an ONNX file (and any external
    weights) of a believable size. A file whose link points at nothing counts
    as missing, and so does any `.incomplete` blob the hub leaves while a
    download is still running."""
    build = build_for(repo)
    root = _folder_for(build.source)
    if not root.is_dir():
        return {"state": "absent", "missing": []}
    try:
        unfinished = any(root.joinpath("blobs").glob("*.incomplete"))
    except OSError:
        unfinished = False
    best: list[str] | None = None
    for snapshot in _snapshots(build.source):
        gaps = _snapshot_missing(snapshot, build, _weights_floor(repo))
        if not gaps and not unfinished:
            return {"state": "complete", "missing": []}
        if best is None or len(gaps) < len(best):
            best = gaps
    missing = best if best is not None else ["model weights"]
    if unfinished:
        missing = [*missing, "an unfinished download"]
    return {"state": "incomplete", "missing": missing}


def snapshot_path(repo: str) -> Path | None:
    """The whole snapshot fastembed loads `repo` from, or None: the folder the
    loader hands over, so a load never touches the network."""
    build = build_for(repo)
    if cache_health(repo)["state"] != "complete":
        return None
    floor = _weights_floor(repo)
    return next((snap for snap in _snapshots(build.source) if not _snapshot_missing(snap, build, floor)), None)


def _read_json(path: Path) -> dict:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def pooling_of(snapshot: Path) -> str:
    """How a typed model pools, from its sentence-transformers Pooling config:
    "CLS", "LAST_TOKEN" or "MEAN" (the usual, and the default)."""
    pooling = _read_json(snapshot / "1_Pooling" / "config.json")
    if pooling.get("pooling_mode_cls_token"):
        return "CLS"
    if pooling.get("pooling_mode_lasttoken"):
        return "LAST_TOKEN"
    return "MEAN"


def width_of(snapshot: Path) -> int:
    """A typed model's vector width, from its configs; 0 when neither says."""
    for value in (
        _read_json(snapshot / "1_Pooling" / "config.json").get("word_embedding_dimension"),
        _read_json(snapshot / "config.json").get("hidden_size"),
    ):
        if isinstance(value, int) and value > 0:
            return value
    return 0


def fetch(repo: str, build: OnnxBuild | None = None) -> None:
    """Download `repo`'s ONNX build into the cache: only the files fastembed
    reads, never the repo's other formats (a sentence-transformers repo also
    holds PyTorch and safetensors weights, several times the size). The one
    way a built-in model reaches this computer, so every fetch is said in the
    privacy panel. `build` is a typed repo's, read from the Hub's file list
    before anything is on disk."""
    from huggingface_hub import snapshot_download

    build = build or build_for(repo)
    with egress.purpose(f"Downloading the embedding model {repo}"):
        snapshot_download(
            repo_id=build.source,
            allow_patterns=[build.model_file, *build.extra_files, *CONFIG_FILES],
            cache_dir=str(cache_root()),
        )


def _dir_size(path: Path) -> int:
    """What a model's cache folder holds on disk, each file counted once.

    The hub cache is *made* of links: `snapshots/` points into `blobs/`, and a
    newer `huggingface_hub` keeps the weights in a shared `<cache>/blobs/` store
    that the model's own folder links to. Counting what a link points at, once
    per target, gives the real size both ways: a walk that followed every link
    reported double, and one that skipped them reported a 127 MB model as
    1 MB."""
    total = 0
    seen: set[Path] = set()
    for entry in path.rglob("*"):
        try:
            target = entry.resolve()
            if target in seen or not target.is_file():
                continue
            seen.add(target)
            total += target.stat().st_size
        except OSError:
            # A file removed underneath the walk costs its bytes, not the total.
            continue
    return total


def _human_size(size: int) -> str:
    if size < 1024 * 1024:
        return f"{size / 1024:.0f} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.0f} MB"
    return f"{size / (1024 * 1024 * 1024):.1f} GB"


def size_in_words(size: int) -> str:
    """A byte count as the screens say it (`128 MB`)."""
    return _human_size(size)


def can_download() -> bool:
    """Whether anything here can actually fetch a model.

    `huggingface_hub` arrives with `fastembed`, so on a notebook
    that never installed the semantic-search extra the answer is no, and
    saying so is much better than a download that fails with an ImportError
    the user has no way to read.
    """
    return importlib.util.find_spec("huggingface_hub") is not None


def status() -> list[dict]:
    """Every model, with whether it is on disk and what it is costing."""
    rows = []
    for model in EMBED_MODELS:
        path = _model_dir(model)
        health = cache_health(model.repo)
        #: Installed means it can load; a folder with some files in it is
        #: "files missing", with Reinstall, not a model (101c).
        installed = health["state"] == "complete"
        rows.append(
            {
                "id": model.id,
                "repo": model.repo,
                "label": model.label,
                "about": model.about,
                "size": model.size,
                "default": model.default,
                "one_press": model.one_press,
                "terms_url": model.terms_url,
                "why_not": model.why_not,
                "installed": installed,
                "files_missing": health["state"] == "incomplete",
                "missing": health["missing"],
                "on_disk": _human_size(_dir_size(path)) if path.is_dir() else "",
                "state": snapshot_state(model.repo),
                "downloading": _state.running and _state.model_id == model.id,
            }
        )
    return rows


def current() -> DownloadState:
    return _state


def cancel() -> tuple[bool, str]:
    """Ask the running download to stop. Returns (asked, message).

    **Between attempts, not mid-file, and the message says so.**
    `snapshot_download` is one blocking call inside huggingface_hub with no
    cancellation token and no way to interrupt it short of killing the
    process, so what this can honestly promise is: no further retry, and no
    "completed" for a download nobody wants any more. A part-downloaded model
    is not wasted: the cache is resumable, which is why the wording says the
    bytes are kept rather than implying they were thrown away.

    Claiming more than that would be the worse outcome: a Quit button that
    reports success while a 400 MB download carries on is how a user learns
    not to trust the panel.
    """
    if not _state.running:
        return False, "Nothing is downloading."
    _state.cancel_requested = True
    _state.step = "Stopping after the current file…"
    return True, "It will stop after the file it is on, what's downloaded is kept."


def _log(line: str) -> None:
    _state.log.append(line)
    del _state.log[:-MAX_LOG_LINES]
    _state.step = line[:120]


#: How many times a dropped connection is retried before giving up.
#:
#: Reported from a real download: *"[WinError 10054] An existing connection was
#: forcibly closed by the remote host."* That is not a broken install or a
#: wrong repo: it is one TCP connection dying part-way through several
#: hundred megabytes, which on a domestic line is ordinary. `snapshot_download`
#: resumes from what is already in the cache, so a retry costs the bytes since
#: the last completed file rather than starting again.
DOWNLOAD_ATTEMPTS = 3

#: What a dropped connection looks like, in the words the user will see. The
#: raw exception names a Windows error code and then tells them to "check your
#: internet connection and try again", which is advice, not an explanation,
#: and it is the *second* half of a two-part message whose first half was a
#: socket error. Worth replacing, because the two failures behind it need
#: opposite responses: a drop is worth retrying, and a genuinely offline
#: machine is not.
_CONNECTION_WORDS = (
    "connection",
    "connect",
    "timed out",
    "timeout",
    "temporarily",
    "network",
    "10054",
)


def _looks_like_a_dropped_connection(exc: Exception) -> bool:
    return any(word in str(exc).lower() for word in _CONNECTION_WORDS)


def _run_download(model: EmbedModel) -> None:
    try:
        last: Exception | None = None
        for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
            if _state.cancel_requested:
                _state.outcome = "cancelled"
                _state.step = "Stopped before it finished. What downloaded is kept."
                return
            try:
                _log(
                    f"Fetching {model.repo}…"
                    if attempt == 1
                    else f"Connection dropped: resuming ({attempt} of {DOWNLOAD_ATTEMPTS})…"
                )
                fetch(model.repo, model.onnx)
                if _state.cancel_requested:
                    _state.outcome = "cancelled"
                    _state.step = "Stopped just as it finished, the files are on disk."
                    return
                #: Verified, not assumed (INBOX 700, "Reinstall re-downloads
                #: and verifies"): the weights must be in the snapshot.
                arrived = cache_health(model.repo)
                if arrived["state"] != "complete":
                    _state.outcome = "failed"
                    gaps = ", ".join(arrived["missing"][:3]) or "its files"
                    _state.step = f"{model.label} arrived without {gaps}. Reinstall fetches it again."
                    return
                _state.outcome = "completed"
                _state.step = (
                    f"{model.label} is on this machine. Pick it under Embedding "
                    "models in Settings, Search and index to search with it."
                )
                return
            except Exception as exc:  # noqa: BLE001  # retry decides, not the type
                last = exc
                if not _looks_like_a_dropped_connection(exc):
                    raise
        _state.outcome = "failed"
        _state.step = (
            f"Couldn't finish downloading {model.label}: the connection kept "
            f"dropping after {DOWNLOAD_ATTEMPTS} attempts. What is already "
            "downloaded is kept, so pressing Download again resumes rather "
            f"than starting over. ({last})"
        )
    except Exception as exc:  # noqa: BLE001  # any other failure is one report
        _state.outcome = "failed"
        _state.step = f"Couldn't download {model.label}: {exc}"
    finally:
        _state.running = False
        # The other half of "for /tasks and the panel" (this dataclass's own
        # docstring): a job that fails must not just vanish from the running
        # list, the way a re-index dying halfway used to.
        from tessellate.core import taskhistory

        taskhistory.record(
            "embedding-model",
            repair_title(model.label) if _state.repair else f"Downloading {model.label}",
            _state.outcome,
            _state.step,
            name=model.id,
            duration_ms=(time.time() - _state.started) * 1000 if _state.started else None,
        )
        if _state.outcome == "completed":
            for hook in list(_finished_hooks):  # noqa: PERF101  # a hook may unregister itself
                try:
                    hook(model.repo)
                except Exception:  # noqa: BLE001  # a listener must not undo a finished download
                    logger.warning("a download-finished listener failed", exc_info=True)


#: Called with the repo once a download (or a repair) lands whole. The
#: embedding service listens, so a model mended in the background loads
#: without waiting out its retry interval (101c).
_finished_hooks: list[Callable[[str], None]] = []


def on_download_finished(hook: Callable[[str], None]) -> None:
    if hook not in _finished_hooks:
        _finished_hooks.append(hook)


def reinstall(model_id: str) -> tuple[bool, str]:
    """Delete what is on disk, then fetch it again: the Reinstall button.

    An incomplete folder is cleared even when it is the model search uses
    (`remove` would refuse): nothing can be searched with it, and fetching
    over the top resumes the same short files. A whole model that is in use
    keeps `remove`'s refusal and is fetched over, as before."""
    model = EMBED_MODELS_BY_ID.get(model_id)
    if model is not None and cache_health(model.repo)["state"] == "incomplete" and not (
        _state.running and _state.model_id == model.id
    ):
        _clear_directory(model)
    else:
        remove(model_id)
    return start(model_id)


def start(model_id: str) -> tuple[bool, str]:
    """Begin a download. Returns (started, message). Never raises on a bad id."""
    model = EMBED_MODELS_BY_ID.get(model_id)
    if model is None:
        return False, "No such embedding model."
    if not model.one_press:
        return False, model.why_not
    if not can_download():
        return False, (
            "Downloading a model needs the huggingface_hub library, which "
            "arrives with “Search by meaning” in Settings, Packages. Install "
            "that first."
        )
    return _begin_download(model)


def _begin_download(model: EmbedModel, repair: bool = False) -> tuple[bool, str]:
    with _lock:
        if _state.running:
            return False, "Another model is already downloading."
        _state.repair = repair
        _state.running = True
        _state.model_id = model.id
        _state.label = model.label
        _state.outcome = ""
        _state.step = "starting…"
        _state.log = []
        _state.started = time.time()
        _state.cancel_requested = False
    _spawn_download(model)
    return True, f"{repair_title(model.label) if repair else 'Downloading ' + model.label}."


def _spawn_download(model: EmbedModel) -> None:
    threading.Thread(target=_run_download, args=(model,), daemon=True).start()


def repair_title(label: str) -> str:
    """What a self-repair is called in Background tasks and the history: the
    owner's words (2026-10-07, "Fixing search by meaning...") and the model."""
    return f"Fixing search by meaning ({label})"


def repair(repo: str) -> tuple[bool, str]:
    """Mend a cache whose files are incomplete, as a visible task (101c): the
    broken folder is cleared and the model fetched again, so "Repairing ..."
    shows in Background tasks with Quit instead of a silent fetch inside the
    loader. A cache that is whole, or absent, is left alone: a first download
    is the loader's, and a good model is never deleted.

    It may clear the model search uses, which `remove` refuses: that model
    cannot be used while its files are short, so there is nothing to protect."""
    if cache_health(repo)["state"] != "incomplete":
        return False, "Its files are not incomplete."
    if not can_download():
        return False, "Repairing needs the huggingface_hub library, which arrives with Search by meaning in Settings, Packages."
    model = EMBED_MODELS_BY_REPO.get(repo) or EmbedModel(id="typed", repo=repo, label=repo, about="", size="")
    if _state.running:
        return False, "Another model is already downloading."
    cleared, message = _clear_directory(model)
    if not cleared:
        return False, message
    return _begin_download(model, repair=True)


# -- Pull a model by name (INBOX 700, the owner's second addendum) -------------

#: A Hugging Face repo id: owner/name, each part starting with a letter or
#: digit, so no `..` and no path can be spelled with it.
_HF_REPO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}/[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")

#: Licences a typed repo may have and still be fetched in one press: the
#: open ones, the rule the catalogue keeps (Apache-2.0, MIT and their kin).
OPEN_LICENCES = frozenset({"apache-2.0", "mit", "bsd-2-clause", "bsd-3-clause", "cc-by-4.0", "cc-by-sa-4.0", "cc0-1.0"})

#: What marks a repo as an embedding model: sentence-transformers' own
#: files, or the Hub's task tags for one.
_ST_FILES = ("modules.json", "config_sentence_transformers.json")
_EMBEDDING_TAGS = frozenset({"sentence-similarity", "feature-extraction", "sentence-transformers"})
#: Where an ONNX export keeps its model, in the order the loader prefers.
_ONNX_FILES = ("onnx/model.onnx", "model.onnx")


def parse_typed_name(text: str) -> tuple[str | None, str]:
    """("hf", repo), ("ollama", name) or (None, why) for a typed name.

    owner/name with no tag is a Hugging Face repo; anything with a tag, or
    no owner, is an Ollama name, which the route checks by the same rules as
    Settings, Models' "Download another model" (`model_cards.inspect_model_name`;
    this module may not import `ai.model_cards`, which would close a cycle
    through the model manager)."""
    text = (text or "").strip()
    if not text or ".." in text or any(ch.isspace() for ch in text):
        return None, "Type a Hugging Face repo (owner/name) or an Ollama name (name:tag)."
    if ":" not in text and _HF_REPO.match(text):
        return "hf", text
    return "ollama", text


def hub_metadata(repo: str) -> dict | None:
    """The Hub's own record of `repo` (files, tags, licence), or None when
    there is no such model. Called only on a Pull click: the one network
    request on this screen besides a download, and said so beside the box.

    Asked through `huggingface_hub` (already required before a pull, see
    `can_download`), whose `model_info` takes the repo id as an id, not as a
    piece of a URL this code builds, and which always talks to the Hub's own
    endpoint. The id is still checked against `_HF_REPO` first."""
    if not _HF_REPO.match(repo or ""):
        return None
    from huggingface_hub import HfApi
    from huggingface_hub.utils import GatedRepoError, RepositoryNotFoundError

    try:
        info = HfApi().model_info(repo, timeout=15)
    except GatedRepoError:
        return {"siblings": [], "tags": [], "cardData": {}, "gated": True}
    except RepositoryNotFoundError:
        return None
    card = getattr(info, "card_data", None)
    licence = getattr(card, "license", None) if card is not None else None
    return {
        "siblings": [{"rfilename": sibling.rfilename} for sibling in (info.siblings or [])],
        "tags": list(info.tags or []),
        "cardData": {"license": licence} if licence else {},
        "gated": bool(info.gated),
    }


def _format_refusal(names: set[str], tags: set[str]) -> str:
    """Why the engine cannot read this repo's files, or "": it runs an ONNX
    export with its tokenizer, of a repo that is an embedding model."""
    runnable = any(name in names for name in _ONNX_FILES) and "tokenizer.json" in names
    if not runnable and any(name.lower().endswith(".gguf") for name in names):
        return "It holds GGUF files, which the built-in engine can't load. Pull it in Ollama instead."
    if not any(name in names for name in _ST_FILES) and not _EMBEDDING_TAGS & tags:
        return "It isn't an embedding model the built-in engine knows how to read."
    if not runnable:
        return "It has no ONNX export with a tokenizer, which is what the built-in engine runs. Use it in Ollama instead."
    return ""


def hub_refusal(meta: dict) -> str:
    """Why the built-in engine cannot use this repo, or "" when it can."""
    names = {str(item.get("rfilename", "")) for item in meta.get("siblings") or []}
    tags = {str(tag) for tag in meta.get("tags") or []}
    why = _format_refusal(names, tags)
    if why:
        return why
    if "custom_code" in tags:
        return "It needs Python code from its own repository to load, which Tessellate never runs."
    if meta.get("gated"):
        return "It is gated behind terms on Hugging Face: read and accept them there first."
    licence = str((meta.get("cardData") or {}).get("license") or "")
    if not licence:
        licence = next((tag.split(":", 1)[1] for tag in tags if tag.startswith("license:")), "")
    if not licence:
        return "It states no licence, so it is not fetched in one press."
    if licence.lower() not in OPEN_LICENCES:
        return f"Its licence is {licence}, not an open one Tessellate fetches in one press: read its terms on Hugging Face."
    return ""


def start_typed(repo: str) -> tuple[bool, str]:
    """Check `repo` on the Hub and, if the engine can use it, download it as
    a Background task. The repo id was matched by `_HF_REPO` and is then
    confirmed by the Hub itself before anything is written."""
    if not _HF_REPO.match(repo or ""):
        return False, "Type a Hugging Face repo as owner/name."
    if repo in EMBED_MODELS_BY_REPO:
        entry = EMBED_MODELS_BY_REPO[repo]
        return start(entry.id) if entry.one_press else (False, entry.why_not)
    if not can_download():
        return False, (
            "Downloading a model needs the huggingface_hub library, which "
            "arrives with “Search by meaning” in Settings, Packages. Install "
            "that first."
        )
    try:
        meta = hub_metadata(repo)
    except Exception:  # noqa: BLE001  # offline, refused or odd: one sentence
        logger.info("couldn't reach Hugging Face to check a typed model name", exc_info=True)
        return False, "Couldn't reach Hugging Face to check that name. Check the connection and try again."
    if meta is None:
        return False, f"No model called {repo} on Hugging Face."
    why = hub_refusal(meta)
    if why:
        return False, why
    return _begin_download(EmbedModel(id="typed", repo=repo, label=repo, about="", size="", onnx=_build_from_hub(repo, meta)))


def _build_from_hub(repo: str, meta: dict) -> OnnxBuild:
    """A typed repo's ONNX build from the Hub's file list: which export file,
    and its external weights when it has them."""
    names = {str(item.get("rfilename", "")) for item in meta.get("siblings") or []}
    model_file = next(name for name in _ONNX_FILES if name in names)
    return OnnxBuild(repo, model_file, (f"{model_file}_data",) if f"{model_file}_data" in names else ())


def remove(model_id: str) -> tuple[bool, str]:
    """Delete one model from the cache.

    No undo and none implied, it is a re-download, which is why the wording
    says so rather than warning about loss. What it must never be is a way to
    delete something else: the id is an allowlist key, and the path is checked
    to be under the cache root before anything is removed. Both, because the
    first is the rule and the second is what catches the day somebody adds an
    entry with a repo id containing `..`.
    """
    model = EMBED_MODELS_BY_ID.get(model_id)
    if model is None:
        return False, "No such embedding model."
    if _state.running and _state.model_id == model.id:
        return False, "That model is downloading right now."
    #: Never the one search uses (INBOX 700): switch first, then remove.
    if _in_use(model.repo):
        return False, f"{model.label} is in use for search: switch to another model first, then remove it."
    cleared, message = _clear_directory(model)
    if not cleared:
        return False, message
    return True, f"{model.label} removed. Downloading it again is one click."


def _clear_directory(model: EmbedModel) -> tuple[bool, str]:
    """Delete one model's cache folder, after checking it is inside the cache
    root. The shared end of `remove` (a person's choice) and `repair`."""
    path = _model_dir(model)
    root = cache_root()
    try:
        resolved = path.resolve()
        if not resolved.is_relative_to(root.resolve()):
            return False, "Refusing to delete outside the model cache."
    except OSError:
        # The exception text carries the full filesystem path (and on some
        # platforms more besides), and this string is returned straight to the
        # browser by `DELETE /embedding-models/{id}`. Flagged by CodeQL as
        # `py/stack-trace-exposure`. Logged in full where only the owner of the
        # machine can read it; the caller gets the fact, not the internals.
        logger.warning("couldn't resolve the cache path for %s", model.id, exc_info=True)
        return False, "Couldn't check where that model is stored."
    if not path.is_dir():
        return False, f"{model.label} isn't on this machine."
    try:
        shutil.rmtree(path)
    except OSError:
        logger.warning("couldn't remove %s from the cache", model.id, exc_info=True)
        return False, (
            f"Couldn't remove {model.label}: see Settings → Logs for why. "
            "It may be in use by a running model."
        )
    return True, ""




#: "Is this repo the model search uses right now?", set by `core/deps.py`
#: (`set_in_use_check`), which owns the model manager. A hook rather than an
#: import: `deps` builds the embedding service, which reaches this module, and
#: importing `deps` here closed the cycles
#: `ai.embeddings -> core.embedmodels -> core.deps -> ai.embeddings` and
#: `ai.model_manager -> core.embedmodels -> core.deps -> ai.model_manager`
#: (`tests/test_no_import_cycles.py`). The default, no app (a script), is
#: that nothing is in use.
_in_use_check: Callable[[str], bool] = lambda repo: False  # noqa: E731


def set_in_use_check(check: Callable[[str], bool]) -> None:
    global _in_use_check
    _in_use_check = check


def _in_use(repo: str) -> bool:
    try:
        return bool(_in_use_check(repo))
    except Exception:  # noqa: BLE001  # no app (a script): nothing is in use
        return False


def reset_for_tests() -> None:
    """Process-global state, like the extras installer, tests have to clear it
    or one test's download leaks into the next one's assertions."""
    global _state
    _state = DownloadState()
