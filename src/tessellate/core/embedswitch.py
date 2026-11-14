"""Changing the embedding model without losing search while it happens.

INBOX 700, the owner: "can you also add more embedding model options as
alternatives in the models??". The choices are `core/embedmodels.py`'s
catalogue; this is what choosing one does.

**The old way cost search for the length of a re-index.** Vectors from two
models are not comparable, so a switch saved the new setting at once and then
re-embedded every note, deleting each old vector as it went: from the first
second, every search embedded its question with the new model and found only
the notes the pass had reached, then keyword results for the rest.

**Now the new set is built beside the old one and swapped in whole.**

1. *Prepare.* The target model is made ready: an Ollama model not yet pulled
   is pulled (bytes done of bytes total), a built-in one is loaded (its first
   load downloads it).
2. *Stage.* Every note that has a vector today is embedded with the target
   into `embeddings_staged` (`database.StagedEmbedding`), in batches, with
   progress. The saved settings are untouched, so every search and every save
   in the meantime uses the old model and the old vectors.
3. *Swap.* One transaction replaces every note vector with its staged one and
   only then are the settings saved. A note written or edited after its
   staged vector was made, or with none, is embedded again afterwards with
   the model now in use, and long notes get their paragraph vectors back.

**Durable** (`core/jobstore.py`): the job is a named handler with plain-data
arguments, so a quit or a crash part-way resumes at the next launch; staged
rows already made for the same target are kept, so it picks up where it
stopped. **Stop** (`jobs.cancel_kind`, the Background tasks row) ends it
between batches, drops the staged rows and leaves the old model in use: the
one outcome a stop can never have is a notebook on two models.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

logger = logging.getLogger("tessellate.embedswitch")

#: Notes embedded per batch; a stop is honoured between batches.
BATCH = 16


@dataclass
class SwitchState:
    """What the switch is doing, for `/tasks`, the Models list and Stop."""

    running: bool = False
    backend: str = ""
    model: str = ""
    label: str = ""
    #: prepare | stage | swap | paragraphs
    phase: str = ""
    done: int = 0
    total: int = 0
    started: float = 0.0
    #: "" while running, then completed | failed | cancelled
    outcome: str = ""
    message: str = ""
    cancel_requested: bool = False


_state = SwitchState()
_lock = threading.Lock()


def status() -> dict:
    """The switch as a plain dict (the Models list polls this)."""
    return {
        "running": _state.running,
        "backend": _state.backend,
        "model": _state.model,
        "label": _state.label,
        "phase": _state.phase,
        "done": _state.done,
        "total": _state.total,
        "started": _state.started or None,
        "outcome": _state.outcome,
        "message": _state.message,
    }


def label_for(backend: str, model: str) -> str:
    """A person's name for a model: the catalogue's label, else its name."""
    from tessellate.core import embedmodels

    if backend == "ollama":
        entry = embedmodels.OLLAMA_EMBED_MODELS_BY_NAME.get(model)
        return entry.label if entry else model
    entry = embedmodels.EMBED_MODELS_BY_REPO.get(model)
    return entry.label if entry else model


def task_row() -> dict | None:
    """The Background tasks row, less its kind (`routes_tasks` names it),
    or None when no switch runs."""
    if not _state.running:
        return None
    detail = {
        "prepare": "Getting the model ready. The first time it is downloaded.",
        "stage": f"{_state.done:,} of {_state.total:,} notes. Search uses the old model until this finishes.",
        "swap": "Swapping the new vectors in.",
        "paragraphs": f"Paragraph vectors for long notes: {_state.done:,} of {_state.total:,}.",
    }.get(_state.phase, "Starting…")
    fraction = None
    if _state.phase in ("stage", "paragraphs", "prepare") and _state.total:
        fraction = max(0.0, min(1.0, _state.done / _state.total))
    return {
        "name": _state.model,
        "label": f"Switching search to {_state.label}",
        "detail": detail,
        "progress": fraction,
        "log": [],
        "started": _state.started or None,
    }


def start(backend: str, model: str) -> tuple[bool, str]:
    """Queue a switch to `backend`/`model`. Returns (started, message).

    The caller has already resolved the pair from the catalogue or checked
    the Ollama name; this only refuses a second switch and a no-op."""
    from tessellate.core import deps
    from tessellate.core import jobs as pool

    manager = deps.get_model_manager()
    current = (
        manager.embedding_backend(),
        manager.embedding_model() if manager.embedding_backend() == "ollama" else manager.embedding_st_model(),
    )
    if current == (backend, model):
        return False, f"Search already uses {label_for(backend, model)}."
    with _lock:
        if _state.running:
            return False, "A model switch is already running."
        _begin(backend, model)
    job = pool.enqueue("embed-switch", run, backend, model, name=_state.label, dedupe_key="embed-switch")
    if not job:
        with _lock:
            _state.running = False
            _state.outcome = "failed"
            _state.message = "Tessellate is shutting down, so nothing was started."
        return False, _state.message
    return True, f"Switching search to {_state.label}. Search keeps working on the old model until it finishes."


def _begin(backend: str, model: str) -> None:
    _state.running = True
    _state.backend = backend
    _state.model = model
    _state.label = label_for(backend, model)
    _state.phase = "prepare"
    _state.done = 0
    _state.total = 0
    _state.started = time.time()
    _state.outcome = ""
    _state.message = ""
    _state.cancel_requested = False


def cancel(_name: str = "") -> tuple[bool, str]:
    """Stop at the next batch; the old model stays in use."""
    if not _state.running:
        return False, "No model switch is running."
    _state.cancel_requested = True
    return True, "Stopping the switch. Search stays on the model it uses now."


class _Stopped(Exception):
    pass


def run(backend: str, model: str) -> None:
    """The pool job (and the durable handler, `jobstore.HANDLERS`)."""
    from tessellate.core import deps, jobruns, taskhistory

    with _lock:
        if not _state.running or (_state.backend, _state.model) != (backend, model):
            # A resumed row: this process never saw it start.
            _begin(backend, model)
    live = deps.get_embeddings()
    db = deps.get_db()
    target = live.pinned(backend, model)
    target_id = target.backend_id()
    started = time.monotonic()
    title = f"Switching search to {_state.label}"
    try:
        with jobruns.job_run("embed-switch", db=db) as job_run:
            try:
                _prepare(target, backend, model)
                _stage(db, target, target_id)
                _swap(db, live, target, target_id, backend, model)
            except _Stopped:
                _drop_staged(db)
                job_run.cancel("stopped; search stayed on the old model")
                _end("cancelled", "Stopped. Search stayed on the model it was using.")
                taskhistory.record("embed-switch", title, "cancelled", _state.message,
                                   duration_ms=(time.monotonic() - started) * 1000)
                return
            job_run.result = f"{_state.total} notes on {_state.label}"
    except Exception as exc:  # noqa: BLE001  # a failed switch reports; the old model stays
        logger.warning("embedding model switch failed", exc_info=True)
        _drop_staged(db)
        _end("failed", "Couldn't switch: the model didn't load. Search stayed on the model it was using. The log has the details.")
        taskhistory.record("embed-switch", title, "failed", type(exc).__name__,
                           duration_ms=(time.monotonic() - started) * 1000)
        return
    _end("completed", f"Search now uses {_state.label}.")
    taskhistory.record("embed-switch", f"Search now uses {_state.label}", "completed",
                       duration_ms=(time.monotonic() - started) * 1000)


def _end(outcome: str, message: str) -> None:
    with _lock:
        _state.running = False
        _state.outcome = outcome
        _state.message = message
        _state.phase = ""


def _check_stop() -> None:
    if _state.cancel_requested:
        raise _Stopped


def _prepare(target, backend: str, model: str) -> None:  # noqa: ANN001
    """Make the target answer before a single note is staged with it."""
    _state.phase = "prepare"
    if backend == "ollama":
        from tessellate.core import deps

        client = deps.get_ollama()
        names = {str(m.get("name", "")) for m in (client.list_models() or [])}
        if model not in names and f"{model}:latest" not in names:
            for update in client.pull(model):
                _check_stop()
                if update.get("error"):
                    raise RuntimeError(update["error"])
                if update.get("total"):
                    _state.total = int(update["total"])
                    _state.done = int(update.get("completed", _state.done))
    if target.embed_text("Tessellate") is None:
        raise RuntimeError(target.last_error or f"{_state.label} did not answer")


def _stage(db, target, target_id: str) -> None:  # noqa: ANN001
    from sqlalchemy import delete, select

    from tessellate.ai.embeddings import embedding_text, vector_to_bytes
    from tessellate.core.database import EmbeddingRecord, Entry, StagedEmbedding

    session = db.session()
    try:
        # Another target's leftovers (a stopped switch the process died in).
        session.execute(delete(StagedEmbedding).where(StagedEmbedding.model_version != target_id))
        session.commit()
        have = set(session.scalars(select(StagedEmbedding.entry_id)))
        ids = list(
            session.scalars(
                select(Entry.id)
                .join(EmbeddingRecord, EmbeddingRecord.entry_id == Entry.id)
                .where(Entry.is_deleted == False, Entry.is_private == False)  # noqa: E712
                .order_by(Entry.id)
            )
        )
        _state.phase = "stage"
        _state.total = len(ids)
        _state.done = sum(1 for entry_id in ids if entry_id in have)
        missing = [entry_id for entry_id in ids if entry_id not in have]
        for start in range(0, len(missing), BATCH):
            _check_stop()
            entries = list(session.scalars(select(Entry).where(Entry.id.in_(missing[start : start + BATCH]))))
            vectors = target.embed_many([embedding_text(session, entry) for entry in entries])
            for entry, vector in zip(entries, vectors):
                if vector is None:
                    raise RuntimeError(target.last_error or "the new model could not embed a note")
                session.add(
                    StagedEmbedding(
                        entry_id=entry.id,
                        embedding=vector_to_bytes(vector),
                        dim=int(vector.shape[0]),
                        model_version=target_id,
                    )
                )
            session.commit()
            _state.done += len(entries)
    finally:
        session.close()


def _swap(db, live, target, target_id: str, backend: str, model: str) -> None:  # noqa: ANN001
    from sqlalchemy import delete, insert, select

    from tessellate.ai.embeddings import paragraph_chunks
    from tessellate.core import deps
    from tessellate.core.database import EmbeddingRecord, Entry, StagedEmbedding
    from tessellate.entry.manager import log_action

    _check_stop()
    _state.phase = "swap"
    session = db.session()
    try:
        staged = {
            row.entry_id: row
            for row in session.scalars(select(StagedEmbedding).where(StagedEmbedding.model_version == target_id))
        }
        live_ids = set(
            session.scalars(
                select(Entry.id).where(Entry.is_deleted == False, Entry.is_private == False)  # noqa: E712
            )
        )
        # One transaction: every note on the new model, or none of them.
        session.execute(delete(EmbeddingRecord))
        rows = [
            {
                "entry_id": entry_id,
                "embedding": row.embedding,
                "dim": row.dim,
                "model_version": target_id,
            }
            for entry_id, row in staged.items()
            if entry_id in live_ids
        ]
        if rows:
            session.execute(insert(EmbeddingRecord), rows)
        session.execute(delete(StagedEmbedding))
        deps.get_model_manager().set_embedding_backend(backend, model)
        log_action(session, "edited", "preferences", detail=f"embedding model -> {target_id}")
        session.commit()
        live.adopt(target)

        # Written or edited since its staged vector was made, or never staged.
        later = live_ids - set(staged)
        for entry_id, row in staged.items():
            entry = session.get(Entry, entry_id)
            if entry is not None and entry.updated_at and row.created_at and _naive(entry.updated_at) > _naive(row.created_at):
                later.add(entry_id)
        long_notes = [
            entry
            for entry in session.scalars(select(Entry).where(Entry.id.in_(live_ids)))
            if entry.id not in later and len(paragraph_chunks(entry.content or "")) >= 2
        ]
        _state.phase = "paragraphs"
        _state.total = len(later) + len(long_notes)
        _state.done = 0
        redo = list(session.scalars(select(Entry).where(Entry.id.in_(later))))
        for start in range(0, len(redo), BATCH):
            live.store_for_entries(session, redo[start : start + BATCH])
            _state.done += len(redo[start : start + BATCH])
        records = {r.entry_id: r for r in session.scalars(select(EmbeddingRecord))}
        for entry in long_notes:
            record = records.get(entry.id)
            if record is not None:
                try:
                    live._store_chunks(session, entry, record)
                    session.commit()
                except Exception:  # noqa: BLE001  # paragraphs refine search; the swap is done
                    session.rollback()
                    logger.warning("couldn't store paragraph vectors for entry %s", entry.id, exc_info=True)
            _state.done += 1
    finally:
        session.close()


def _naive(value):  # noqa: ANN001, ANN202
    return value.replace(tzinfo=None) if getattr(value, "tzinfo", None) else value


def _drop_staged(db) -> None:  # noqa: ANN001
    from sqlalchemy import delete

    from tessellate.core.database import StagedEmbedding

    try:
        session = db.session()
        try:
            session.execute(delete(StagedEmbedding))
            session.commit()
        finally:
            session.close()
    except Exception:  # noqa: BLE001  # leftovers are dropped by the next switch
        logger.warning("couldn't drop staged vectors", exc_info=True)


def reset_for_tests() -> None:
    global _state
    _state = SwitchState()
