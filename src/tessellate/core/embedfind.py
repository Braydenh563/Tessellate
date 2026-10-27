"""Embedding models already on this computer (INBOX 700, the owner's addendum).

The owner: "should there also be a way to detect and potentially use any other
cached models the user may have?? like for embedding models and such??". A
person who has used other local AI tools often has embedding models on disk
already, and downloading another is the slow, online part of switching.

**Where it looks, and only looks.** The Hugging Face cache (`HF_HUB_CACHE`,
`HF_HOME`, or `~/.cache/huggingface/hub`, read the way `embedmodels.cache_root`
reads it), the old sentence-transformers cache, Ollama's model list when
Ollama is running (its local API, which `list_models` already calls), and LM
Studio's models folder. A read-only walk of folders and a few small JSON
files: nothing is imported (no fastembed, no ONNX Runtime), nothing is
written, nothing leaves the machine.

**Use only for what the engine loads as it is.** A Hugging Face snapshot of
an embedding model (sentence-transformers' `modules.json` or a Pooling config)
with an ONNX export and its tokenizer is loaded from the cache, offline, by
fastembed. One with PyTorch weights only is listed with why not, and so is one
whose `config.json` names its own Python code (`auto_map`): Tessellate never
runs a repository's code. The old sentence-transformers cache and LM Studio's
GGUF files are listed with why they cannot be used, and what would.

A repo id here comes from a folder name on this disk, never from a request:
`POST /embedding-models/use` sends `found:<repo>` and the server scans again
and accepts it only if this scan lists it as usable.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("tessellate.embedfind")

#: Words in an Ollama model's name or family that mark an embedding model.
_OLLAMA_EMBED_WORDS = ("embed", "bge", "minilm", "e5", "gte", "arctic")
_OLLAMA_EMBED_FAMILIES = ("bert", "nomic-bert", "xlm-roberta")

#: How deep the LM Studio walk goes (publisher/model/file is three).
_LMSTUDIO_DEPTH = 4
#: A bound on files looked at, so a huge models folder cannot stall a poll.
_MAX_FILES = 5_000


def _sentence_transformers_home() -> Path:
    value = os.environ.get("SENTENCE_TRANSFORMERS_HOME")
    return Path(value) if value else Path.home() / ".cache" / "torch" / "sentence_transformers"


def _lmstudio_roots() -> list[Path]:
    value = os.environ.get("LMSTUDIO_HOME")
    if value:
        return [Path(value) / "models"]
    return [Path.home() / ".lmstudio" / "models", Path.home() / ".cache" / "lm-studio" / "models"]


def _snapshot(repo_dir: Path) -> Path | None:
    snapshots = repo_dir / "snapshots"
    try:
        found = sorted((p for p in snapshots.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime)
    except OSError:
        return None
    return found[-1] if found else None


def _has_weights(snap: Path) -> bool:
    try:
        return any(
            p.suffix in (".safetensors", ".bin", ".onnx") and p.name.startswith(("model", "pytorch_model"))
            for p in snap.rglob("*")
        )
    except OSError:
        return False


def _has_onnx(snap: Path) -> bool:
    """An ONNX export fastembed can run, with the tokenizer it reads."""
    has_model = (snap / "onnx" / "model.onnx").is_file() or (snap / "model.onnx").is_file()
    return has_model and (snap / "tokenizer.json").is_file()


def _is_embedding_model(snap: Path) -> bool:
    return any((snap / name).is_file() for name in ("modules.json", "config_sentence_transformers.json", "1_Pooling/config.json"))


def _why_not(snap: Path) -> str:
    """Why the built-in engine cannot load this snapshot, or "" when it can."""
    if not _has_weights(snap):
        return "Only part of it is here (no weights); a download that stopped half way."
    if _needs_own_code(snap):
        return "It needs Python code from its own repository to load, which Tessellate never runs."
    if not _has_onnx(snap):
        return "It has PyTorch weights only; the built-in engine runs ONNX exports. Pick it from the list above, or use it in Ollama."
    return ""


def _needs_own_code(snap: Path) -> bool:
    try:
        config = json.loads((snap / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(config, dict) and bool(config.get("auto_map"))


def _hub_rows() -> list[dict]:
    from tessellate.core import embedmodels

    rows = []
    root = embedmodels.cache_root()
    try:
        repos = sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("models--"))
    except OSError:
        return rows
    #: The catalogue's repos and the ONNX builds it fetches them from: the
    #: catalogue row already says whether those are downloaded.
    listed = set(embedmodels.EMBED_MODELS_BY_REPO) | {
        model.onnx.source for model in embedmodels.EMBED_MODELS if model.onnx is not None
    }
    for repo_dir in repos:
        repo = repo_dir.name[len("models--") :].replace("--", "/", 1)
        snap = _snapshot(repo_dir) if repo not in listed else None
        #: Not an embedding model as far as anything here can tell.
        if snap is None or not _is_embedding_model(snap):
            continue
        rows.append(_row(f"found:{repo}", embedmodels.BUILTIN_BACKEND, repo, repo, "Hugging Face cache", _why_not(snap)))
    return rows


def _legacy_rows() -> list[dict]:
    from tessellate.core import embedmodels

    rows = []
    root = _sentence_transformers_home()
    try:
        folders = sorted(p for p in root.iterdir() if p.is_dir())
    except OSError:
        return rows
    for folder in folders:
        if not (folder / "modules.json").is_file():
            continue
        name = folder.name.replace("_", "/", 1)
        rows.append(
            _row(
                f"found-legacy:{folder.name}", embedmodels.BUILTIN_BACKEND, "", name, "Old sentence-transformers cache",
                "In the cache older versions of sentence-transformers used, which Tessellate does not load from. "
                "Use the same model from the list above, or download it once.",
            )
        )
    return rows


def _lmstudio_rows() -> list[dict]:
    rows = []
    seen = 0
    for root in _lmstudio_roots():
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            depth = len(Path(dirpath).relative_to(root).parts)
            if depth >= _LMSTUDIO_DEPTH:
                dirnames[:] = []
            for filename in filenames:
                seen += 1
                if seen > _MAX_FILES:
                    return rows
                if not filename.lower().endswith(".gguf") or "embed" not in (dirpath + filename).lower():
                    continue
                rows.append(
                    _row(
                        f"found-lmstudio:{filename}", "gguf", "", filename, "LM Studio",
                        "A GGUF file: the built-in engine can't load GGUF. Pull the same model in Ollama "
                        "to use it here.",
                    )
                )
    return rows


def _ollama_rows(ollama) -> list[dict]:  # noqa: ANN001
    from tessellate.core import embedmodels

    if ollama is None:
        return []
    try:
        if not ollama.is_running():
            return []
        models = ollama.list_models() or []
    except Exception:  # noqa: BLE001  # Ollama down or odd is "nothing found", never an error
        return []
    rows = []
    for model in models:
        name = str(model.get("name", ""))
        base = name.removesuffix(":latest")
        if not name or base in embedmodels.OLLAMA_EMBED_MODELS_BY_NAME or name in embedmodels.OLLAMA_EMBED_MODELS_BY_NAME:
            continue
        families = (model.get("details") or {}).get("families") or []
        if not (any(word in base.lower() for word in _OLLAMA_EMBED_WORDS) or any(f in _OLLAMA_EMBED_FAMILIES for f in families)):
            continue
        rows.append(_row(f"found-ollama:{name}", "ollama", name, name, "Ollama", ""))
    return rows


def _row(row_id: str, backend: str, model: str, label: str, where: str, why: str) -> dict:
    return {
        "id": row_id,
        "backend": backend,
        "model": model,
        "label": label,
        "where": where,
        "usable": not why,
        "why_not": why,
    }


def found(ollama=None) -> list[dict]:  # noqa: ANN001
    """Every embedding model on this computer that the catalogue does not
    already list, usable ones first. Never raises."""
    rows: list[dict] = []
    for scan in (_hub_rows, _legacy_rows, _lmstudio_rows):
        try:
            rows.extend(scan())
        except Exception:  # noqa: BLE001  # one unreadable folder is not the list
            logger.debug("embedding model scan step failed", exc_info=True)
    rows.extend(_ollama_rows(ollama))
    return sorted(rows, key=lambda row: (not row["usable"], row["where"], row["label"].lower()))


def usable_repo(repo: str) -> bool:
    """Is `repo` a Hugging Face model on this disk the engine can load?"""
    return any(row["usable"] and row["model"] == repo for row in _hub_rows())


def resolve(choice_id: str, ollama=None) -> tuple[str, str] | None:  # noqa: ANN001
    """`(backend, model)` for a found row's id, rescanned; None otherwise."""
    if choice_id.startswith("found-ollama:"):
        rows = _ollama_rows(ollama)
    elif choice_id.startswith("found:"):
        rows = _hub_rows()
    else:
        return None
    row = next((row for row in rows if row["id"] == choice_id and row["usable"]), None)
    return (row["backend"], row["model"]) if row else None
