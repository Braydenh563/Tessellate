"""Optional extras and embedding-model routes: what can be installed, and the model search uses.

Split out of routes_settings.py (K24); mounted in app.py beside that module's router.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from tessellate.core import deps, embedmodels, extras
from tessellate.api.this_computer import this_computer_only

router = APIRouter(tags=["settings"])

# --- optional extras ---------------------------------------------------------


@router.get("/extras")
def list_extras() -> dict:
    """What can be installed, and what already is.

    The install itself reports through /tasks like every other background job,
    so this is only the catalogue and the current state.
    """
    state = extras.current()
    bulk = extras.bulk_status()
    return {
        "extras": extras.status(),
        "bundles": extras.bundles(),
        #: A bulk action is running between two of its packages too, when
        #: `state` is idle for a moment: the screen keeps polling through it.
        "running": state.running or bulk["running"],
        "installing": state.extra_id if state.running else "",
        #: The package the step, outcome and log are about once it has ended,
        #: so Settings can show them under that row (INBOX 1777).
        "last": state.extra_id,
        "step": state.step,
        "outcome": state.outcome,
        "log": list(state.log),
        "bulk": bulk,
    }


class ExtrasBulkBody(BaseModel):
    """A bulk action: ids from the allowlist, or one bundle's id. Never a
    package spec: `core/extras.start_bulk` refuses any id it does not hold."""

    action: str = Field(max_length=20)
    ids: list[str] = Field(default_factory=list, max_length=50)
    bundle: str = Field(default="", max_length=40)


@router.post("/extras/bulk", dependencies=[Depends(this_computer_only)])
def bulk_extras(body: ExtrasBulkBody) -> dict:
    """Install, remove or reinstall several extras, one after another, as one
    background job (INBOX 595). Each package reports its own outcome in
    `GET /extras`'s `bulk.items`; one failing does not stop the rest."""
    started, message = extras.start_bulk(body.action, body.ids, bundle=body.bundle)
    return {"started": started, "message": message}


@router.post("/extras/{extra_id}/install", dependencies=[Depends(this_computer_only)])
def install_extra(extra_id: str, reinstall: bool = False) -> dict:
    """Start installing one extra **from the allowlist**.

    The path names an entry in `core/extras.py`; the package spec handed to pip
    is never anything the client sent. That is the whole security property here
    - `pip install <a name from a request body>` is arbitrary code execution by
    design, and validating the string afterwards does not fix it.
    """
    started, message = extras.start(extra_id, reinstall=reinstall)
    return {"started": started, "message": message}


@router.post("/extras/{extra_id}/uninstall", dependencies=[Depends(this_computer_only)])
def uninstall_extra(extra_id: str) -> dict:
    """Remove one extra, by the same allowlist id the install uses."""
    started, message = extras.remove(extra_id)
    return {"started": started, "message": message}


# --- embedding models ---------------------------------------------------------


@router.get("/embedding-models")
def list_embedding_models() -> dict:
    """Which embedding models are on this machine, and what they cost.

    `can_download` is here rather than left for the client to infer: without
    `huggingface_hub` (which arrives with the semantic-search extra) every
    button on this screen would start something that cannot finish, and a
    disabled button with a reason beats a download that fails on an ImportError.
    """
    state = embedmodels.current()
    return {
        "models": embedmodels.status(),
        "cache": str(embedmodels.cache_root()),
        "can_download": embedmodels.can_download(),
        "running": state.running,
        "downloading": state.model_id if state.running else "",
        "step": state.step,
        "outcome": state.outcome,
        "log": list(state.log),
    }


class EmbeddingChoiceBody(BaseModel):
    #: A catalogue id (`core/embedmodels.catalogue`), never a repo or a path.
    id: str = Field(max_length=80)


def _legacy_search_files(backend: str, model: str) -> dict:
    """The old engine's files Settings offers to remove: only once the new
    build of the model search uses is in place (or search runs on Ollama), so
    nothing is taken away while it is still the way back to a working search."""
    if backend != "ollama" and not embedmodels.is_downloaded(model):
        return {"files": [], "engine": None}
    engine = extras.legacy_engine()
    if engine is not None:
        engine = {**engine, "size": embedmodels.size_in_words(engine["bytes"])}
    return {"files": embedmodels.legacy_files(), "engine": engine}


@router.get("/embedding-models/choices")
def embedding_model_choices() -> dict:
    """Settings, Models' list (INBOX 700): every model on offer with its
    facts, which one search uses now, and a switch in progress."""
    from tessellate.core import embedswitch

    manager = deps.get_model_manager()
    backend = manager.embedding_backend()
    model = manager.embedding_model() if backend == "ollama" else manager.embedding_st_model()
    from tessellate.core import embedfind

    choices = embedmodels.catalogue()
    #: Which Ollama rows are pulled already, for Install against Reinstall
    #: and Uninstall (the owner's second addendum). Ollama's local list only.
    try:
        from tessellate.api import routes_models

        pulled = routes_models._installed_names()
    except Exception:  # noqa: BLE001  # Ollama down: nothing is pulled as far as this screen knows
        pulled = set()
    for row in choices:
        if row["backend"] == "ollama":
            row["downloaded"] = row["model"] in pulled or f"{row['model']}:latest" in pulled
    return {
        "choices": choices,
        #: The previous engine's files (PyTorch weights, and in a packaged app
        #: the packages), offered for removal once nothing needs them.
        "legacy": _legacy_search_files(backend, model),
        #: Where the built-in models are kept, said in words under the list.
        "cache": str(embedmodels.cache_root()),
        #: Already on this computer, outside the catalogue (the owner's
        #: addendum): a read-only scan, offline.
        "found": embedfind.found(deps.get_ollama()),
        "current": {"backend": backend, "model": model},
        "switch": embedswitch.status(),
    }


@router.post("/embedding-models/use", dependencies=[Depends(this_computer_only)])
def use_embedding_model(body: EmbeddingChoiceBody) -> dict:
    """Switch search to one catalogue entry, in the background. An entry
    whose licence or loading rules forbid one press is refused here too,
    not only by its missing button."""
    from tessellate.core import embedswitch

    from tessellate.core import embedfind

    if body.id.startswith("found"):
        resolved = embedfind.resolve(body.id, deps.get_ollama())
    else:
        resolved = embedmodels.resolve_choice(body.id)
    if resolved is None:
        raise HTTPException(status_code=400, detail="That model can't be switched to from here.")
    started, message = embedswitch.start(*resolved)
    return {"started": started, "message": message}


class EmbeddingPullBody(BaseModel):
    name: str = Field(max_length=200)


@router.post("/embedding-models/pull", dependencies=[Depends(this_computer_only)])
def pull_embedding_model(body: EmbeddingPullBody) -> dict:
    """Pull a model by name (INBOX 700, the owner's second addendum).

    A Hugging Face repo is checked against the Hub's metadata, on this click
    and never before, and fetched only if the built-in engine can load it
    (`embedmodels.start_typed` says why not otherwise). An Ollama name goes
    to Ollama's own pull, a Background task with its bytes. Either way the
    model then appears under Found on this computer, with Use."""
    from tessellate.ai import model_cards, model_manager

    kind, name = embedmodels.parse_typed_name(body.name)
    if kind is None:
        return {"started": False, "message": name, "source": ""}
    if kind == "hf":
        started, message = embedmodels.start_typed(name)
        return {"started": started, "message": message, "source": "huggingface"}
    #: An Ollama name is checked by the rules of "Download another model".
    info = model_cards.inspect_model_name(name)
    if not info.get("valid"):
        return {"started": False, "message": info.get("error") or "That is not a model name.", "source": ""}
    name = info["name"]
    ollama = deps.get_ollama()
    try:
        running = ollama.is_running()
        installed = {str(m.get("name", "")) for m in (ollama.list_models() or [])} if running else set()
    except Exception:  # noqa: BLE001  # an Ollama that cannot answer is one that is not there
        running, installed = False, set()
    if not running:
        return {"started": False, "message": "Ollama isn't running. Start it and try again.", "source": "ollama"}
    if name in installed or f"{name}:latest" in installed:
        return {"started": False, "message": f"{name} is already in Ollama: it is under Found on this computer.", "source": "ollama"}
    if not model_manager.start_pull(ollama, name):
        return {"started": False, "message": f"{name} is already downloading.", "source": "ollama"}
    return {"started": True, "message": f"Pulling {name} into Ollama. Background tasks shows its progress.", "source": "ollama"}


@router.post("/embedding-models/{model_id}/download", dependencies=[Depends(this_computer_only)])
def download_embedding_model(model_id: str, reinstall: bool = False) -> dict:
    """Fetch one model **from the allowlist** in `core/embedmodels.py`.

    Same property as the extras installer: the repo id handed to the hub is
    never anything the client sent. A repo id from a request is a path that
    gets fetched and written to disk.

    A reinstall removes first, because that is the state the button exists for
    - a half-finished download leaves a directory that looks installed and
    loads as a corrupt model, and fetching over the top of it resumes the same
    broken snapshot.
    """
    if reinstall:
        started, message = embedmodels.reinstall(model_id)
    else:
        started, message = embedmodels.start(model_id)
    return {"started": started, "message": message}


@router.delete("/embedding-models/legacy/{item_id}", dependencies=[Depends(this_computer_only)])
def remove_legacy_search_files(item_id: str) -> dict:
    """Remove the previous engine's files: one catalogue model's PyTorch copy
    by its allowlist id, or "engine" for the packages in a packaged app's
    extras folder. Refused until the new model is in place."""
    manager = deps.get_model_manager()
    model = manager.embedding_st_model()
    if manager.embedding_backend() != "ollama" and not embedmodels.is_downloaded(model):
        return {"removed": False, "message": "Download the new search model first: the old files stay until it is here."}
    if item_id == "engine":
        started, message = extras.remove_legacy_engine()
        return {"removed": started, "message": message}
    removed, message = embedmodels.remove_legacy(item_id)
    return {"removed": removed, "message": message}


@router.delete("/embedding-models/{model_id}", dependencies=[Depends(this_computer_only)])
def remove_embedding_model(model_id: str) -> dict:
    """Delete one model from the cache, by the same allowlist id."""
    removed, message = embedmodels.remove(model_id)
    return {"removed": removed, "message": message}
