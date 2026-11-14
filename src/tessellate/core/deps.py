"""The single source of truth for shared app state (build plan §4).

Exactly one ConfigManager and one DatabaseManager exist per process.
Routers must import `get_session` / `get_config` from here and must
NEVER build their own DatabaseManager.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TypeVar

from fastapi import HTTPException, Request
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from tessellate.ai.embeddings import EmbeddingService
from tessellate.ai.model_manager import ModelManager
from tessellate.ai.ollama_client import OllamaClient
from tessellate.ai.openai_client import OpenAICompatClient
from tessellate.ai.provider import Provider
from tessellate.core import embedmodels, jobruns, spacelock
from tessellate.core.config import ConfigManager
from tessellate.core import board_thumbs
from tessellate.core.database import Entry
from tessellate.core.database_manager import DatabaseManager

_ModelT = TypeVar("_ModelT")

_config: ConfigManager | None = None
_db: DatabaseManager | None = None
_ollama: Provider | None = None
_model_manager: ModelManager | None = None
_embeddings: EmbeddingService | None = None


class MultipleWorkersError(RuntimeError):
    """Raised when the app is started with more than one worker process."""


def _requested_worker_count() -> int | None:
    """How many workers the launcher was asked for, if it said.

    Everything in this module is one-per-process, and so are the in-memory log
    buffer, the auth tokens and the handle on the SearXNG subprocess. That is
    correct and simple for one process, and quietly wrong for two: the log
    console would show a fraction of what happened, an unlock would work only
    on whichever worker answered next, and two workers would each believe they
    owned the SearXNG they started.

    None of that fails loudly. It presents as flakiness, which is the reason
    to refuse rather than warn.

    Read from the command line and from WEB_CONCURRENCY, which is the
    environment variable uvicorn and gunicorn both honour, between them those
    are the ways someone actually turns this up.
    """
    argv = sys.argv[1:]
    for index, argument in enumerate(argv):
        value = None
        if argument in ("--workers", "-w") and index + 1 < len(argv):
            value = argv[index + 1]
        elif argument.startswith("--workers="):
            value = argument.split("=", 1)[1]
        if value is not None:
            try:
                return int(value)
            except ValueError:
                return None
    concurrency = os.environ.get("WEB_CONCURRENCY")
    if concurrency:
        try:
            return int(concurrency)
        except ValueError:
            return None
    return None


def refuse_multiple_workers() -> None:
    """Stop a multi-worker start, with the reason and the way out.

    Deliberately an exception rather than a log line. A warning at startup is
    read by nobody and the failure it precedes looks like a bug in the app.
    """
    workers = _requested_worker_count()
    if workers is None or workers <= 1:
        return
    raise MultipleWorkersError(
        f"Tessellate cannot run with {workers} workers: it is a single-user "
        "app, and its configuration, database handle, log buffer, unlock "
        "sessions and SearXNG subprocess are one-per-process. With more than "
        "one worker each of those silently becomes per-worker: logs would show "
        "a fraction of what happened, unlocking would work only sometimes, and "
        "two workers would each think they own the SearXNG they started.\n\n"
        "Start it with one worker (`python -m tessellate`). If you are trying "
        "to make it faster, more workers is not the lever, the slow paths are "
        "Ollama and embedding, and both are already off the request thread."
    )


#: Where each dialect listens when the user hasn't said. LM Studio's port is
#: the OpenAI default because it is the backend that was actually asked for,
#: and it is the one of the four whose port is fixed rather than chosen at
#: launch (llama.cpp and vLLM are whatever you passed `--port`).
DEFAULT_BASE_URLS = {
    "ollama": "http://localhost:11434",
    "openai": "http://localhost:1234/v1",
}


def build_llm_client(config: ConfigManager) -> Provider:
    """The chat backend the user has chosen (§6).

    Two dialects, not four products: `openai` covers LM Studio, llama.cpp, Jan
    and vLLM alike, because the only thing that differs between them is the
    base URL. Everything downstream, the agent, the librarian, the janitor , 
    is written against `Provider` and never asks which one it got.

    An unrecognised provider name falls back to Ollama rather than raising. The
    preferences file is a JSON file the user is invited to edit by hand, and a
    typo in it should cost the setting, not the app.
    """
    provider = str(config.get_preference("llm_provider", "ollama") or "ollama").lower()
    base_url = str(config.get_preference("llm_base_url", "") or "").strip()

    # The lock is enforced here as well as at the endpoint, and that is not
    # belt-and-braces for its own sake: `preferences.json` is a plain file the
    # user is invited to edit by hand, and it is what a restored backup or a
    # copied config brings with it. Checking only on the way in would mean a
    # remote address that never passed through the endpoint is used anyway, 
    # silently, and on every turn.
    #
    # Falling back to the provider's local default rather than refusing to
    # start: the app must open so the setting can be fixed from inside it.
    if base_url and config.get_preference("local_only_ai", True):
        from tessellate.core import security

        allowed, reason, _ = security.check_backend_url(base_url, local_only=True)
        if not allowed:
            logging.getLogger("tessellate.config").warning(
                "refusing the saved AI backend %r and using the local default "
                "instead: %s",
                base_url,
                reason,
            )
            base_url = ""

    if provider == "openai":
        return OpenAICompatClient(
            base_url=base_url or DEFAULT_BASE_URLS["openai"],
            api_key=str(config.get_preference("llm_api_key", "") or ""),
        )
    # `config.ollama_url` carries the OLLAMA_URL environment variable, which
    # predates this setting: so it stays the default for the Ollama path
    # rather than being overwritten by an empty preference.
    return OllamaClient(base_url=base_url or config.ollama_url)


#: One builder at a time. The singletons are built lazily by whichever
#: caller asks first, and a background thread (the embedding warm-up, a job
#: on the pool) can ask at the same moment as a request or a test fixture:
#: two `DatabaseManager`s on one file then both run `create_all`, and the
#: loser fails with "table spaces already exists" (seen on CI once the suite
#: ran in parallel and a leftover thread from one test met the next test's
#: fixture). Re-entrant, because building one singleton can ask for another.
_state_lock = threading.RLock()


def init_app_state(data_dir: str | Path | None = None) -> None:
    """Build the singletons once, under `_state_lock` (see its comment)."""
    with _state_lock:
        _init_app_state(data_dir)


def _init_app_state(data_dir: str | Path | None = None) -> None:
    """Build the singletons once. Safe to call twice (later calls no-op),
    so tests can initialise with a temp dir before the app starts."""
    global _config, _db, _ollama, _model_manager, _embeddings
    if _config is None:
        _config = ConfigManager(data_dir=data_dir)
    if _db is None:
        from tessellate.core import selfcheck

        selfcheck.observe_start(Path(_config.db_path))
        try:
            _db = DatabaseManager(_config.db_path)
        except DatabaseError as exc:
            # The check tells damage apart from a locked or busy file, which
            # keeps its own error (WORLD_CLASS 25e).
            from tessellate.core import backup, startup_status

            if backup.check_at_boot(_config.db_path)["ok"]:
                raise
            # With a backup that holds notes, the damaged file is kept aside
            # and the lock screen offers the backup (INBOX 1573); without
            # one the app stops, naming the way back, as before.
            if selfcheck.restore_offer(Path(_config.db_path), Path(_config.data_dir), has_user=False):
                selfcheck.set_aside_damaged_database(Path(_config.db_path))
                selfcheck.forget_offer()
                backup.forget_boot_check(_config.db_path)
                _db = DatabaseManager(_config.db_path)
            else:
                words = backup.damaged_notebook_words(Path(_config.db_path), Path(_config.data_dir))
                startup_status.set_phase(words)
                logging.getLogger("tessellate.startup").error("%s", words)
                raise backup.DamagedNotebookError(words) from exc
    if _ollama is None:
        _ollama = build_llm_client(_config)
    # `ai/provider.py` reads the user's sampling overrides through a getter
    # rather than importing this module: it is the bottom of the AI stack and
    # this is the wiring that builds on it, so the import would be a cycle
    # (CodeQL flagged it) as well as the wrong direction. Registered here,
    # where the config it reads is known to exist.
    #
    # Even a submodule-direct, function-scoped import of it was still flagged
    # as beginning a cycle (CodeQL's cyclic-import query counts a function
    # body's imports too, not just module-level ones), so this is imported
    # by name through `importlib` instead of a `from`/`import` statement,
    # which is the same runtime lookup with nothing for the static check to
    # see as an edge.
    import importlib

    importlib.import_module("tessellate.ai.provider").set_sampling_overrides_getter(
        lambda: _config.get_preference("sampling_overrides", {})
    )
    if _model_manager is None:
        _model_manager = ModelManager(_config)
    if _embeddings is None:
        _embeddings = EmbeddingService(_model_manager, _ollama)


def reload_db() -> None:
    """Close every connection and reopen the database file, needed
    after a backup restore replaces the file underneath us."""
    global _db
    assert _config is not None
    if _db is not None:
        _db.engine.dispose()
    _db = DatabaseManager(_config.db_path)


#: Caches that have to be emptied when the singletons are thrown away.
#:
#: Anything holding values derived from *this* notebook registers here. The
#: graph's PageRank and similarity caches were the first, and they were
#: originally cleared by importing `api.routes_graph` from inside
#: `reset_app_state`, which works, and inverts the layering: `core/` is the
#: bottom of this app and must not know the API layer exists. CodeQL called it
#: what it was, a cycle.
#:
#: A registry turns it the right way up. The cache tells the container it
#: exists; the container never goes looking.
_cache_resets: list = []


def register_cache_reset(drop) -> None:  # noqa: ANN001  # any zero-arg callable
    """Have `drop()` called whenever the app's singletons are reset."""
    if drop not in _cache_resets:
        _cache_resets.append(drop)


def reset_app_state() -> None:
    """Throw the singletons away, used between tests, never in the app."""
    with _state_lock:
        _reset_app_state()


def _reset_app_state() -> None:
    global _config, _db, _ollama, _model_manager, _embeddings
    if _db is not None:
        _db.engine.dispose()
    from tessellate.core import selfcheck

    selfcheck.reset_for_tests()
    for drop in _cache_resets:
        drop()
    _config = None
    _db = None
    _ollama = None
    _model_manager = None
    _embeddings = None


def reload_llm_client() -> None:
    """Rebuild the chat backend after the provider or its URL changed.

    Settings, Models can switch between Ollama and an OpenAI-compatible
    server, and the whole point of doing it there is not having to restart the
    app. The embedding service holds the same client, so it is rebuilt too, 
    otherwise switching backend would leave embeddings still talking to the old
    one, which presents as semantic search quietly using a server the user
    thinks they turned off.
    """
    global _ollama, _embeddings
    assert _config is not None
    _ollama = build_llm_client(_config)
    # **Re-pointed, not rebuilt.** A new `EmbeddingService` starts with no
    # model loaded, and the built-in fastembed model never uses
    # the chat client at all: measured (audit 2026-10-05, ARCH-06), after a
    # switch and back `embedding_ready` stayed false and search ran keyword
    # only for as long as nobody saved, then the next save paid the 5 s cold
    # load. The service keeps its loaded model and talks to the new client.
    if _embeddings is None:
        _embeddings = EmbeddingService(get_model_manager(), _ollama)
    else:
        _embeddings.use_client(_ollama)


def override_ai(
    ollama: Provider | None = None,
    embeddings: EmbeddingService | None = None,
) -> None:
    """Swap in fakes: tests only. Real code never calls this."""
    global _ollama, _embeddings
    if ollama is not None:
        _ollama = ollama
    if embeddings is not None:
        _embeddings = embeddings


def get_config() -> ConfigManager:
    init_app_state()
    assert _config is not None
    return _config


spacelock.config_source = get_config
board_thumbs.data_dir_source = lambda: get_config().data_dir


def get_db() -> DatabaseManager:
    init_app_state()
    assert _db is not None
    return _db


def peek_db() -> DatabaseManager | None:
    """The database if the app has one, without creating it.

    `get_db` initialises the app state on first use, which is right for a
    request and wrong for bookkeeping: a job record written from a helper
    that a test (or a script) runs without an app must not conjure a data
    directory to put its note in.
    """
    return _db


def peek_config() -> ConfigManager | None:
    """The settings if the app has them, without creating them (`peek_db`'s
    reason: a helper run outside the app must not conjure a data folder)."""
    return _config


#: The job records (`core/jobruns.py`) find the database through this.
jobruns.set_database_source(peek_db)


def get_ollama() -> Provider:
    """The chat backend, whichever dialect it speaks.

    Still named for Ollama because every call site is, and renaming it would
    be a large diff that changes no behaviour. What it returns is a `Provider`.
    """
    init_app_state()
    assert _ollama is not None
    return _ollama


def get_model_manager() -> ModelManager:
    init_app_state()
    assert _model_manager is not None
    return _model_manager


def get_embeddings() -> EmbeddingService:
    init_app_state()
    assert _embeddings is not None
    return _embeddings


def _embedding_model_in_use(repo: str) -> bool:
    """Whether `repo` is the built-in model search reads with right now. Handed
    to `core/embedmodels.py` (it may not import this module: a cycle), which
    refuses to remove that model."""
    manager = get_model_manager()
    return manager.embedding_backend() != "ollama" and manager.embedding_st_model() == repo


embedmodels.set_in_use_check(_embedding_model_in_use)


#: The ids of the spaces that exist, so a request header is checked without a
#: query per request. Refreshed on a miss (a space made a moment ago is found),
#: after 5 s (a space deleted elsewhere stops being accepted), and whenever a
#: `Space` row is inserted or deleted through this process.
_SPACE_IDS_TTL = 5.0
#: One slot, `(when, ids)` or None; a list so no function rebinds a global.
_space_ids: list[tuple[float, frozenset[str]] | None] = [None]


def forget_space_ids() -> None:
    _space_ids[0] = None


def _on_space_row_change(*_args: object) -> None:
    forget_space_ids()


def _watch_spaces() -> None:
    from sqlalchemy import event

    from tessellate.core.database import Space

    for name in ("after_insert", "after_delete"):
        event.listen(Space, name, _on_space_row_change)


_watch_spaces()
register_cache_reset(forget_space_ids)


def _space_known(session: Session, workspace_id: str) -> bool:
    from tessellate.core.database import Space

    now = time.monotonic()
    cached = _space_ids[0]
    if cached and now - cached[0] < _SPACE_IDS_TTL and workspace_id in cached[1]:
        return True
    ids = frozenset(row[0] for row in session.query(Space.id).all())
    _space_ids[0] = (now, ids)
    return workspace_id in ids


#: Paths that act on the private spaces themselves, or on the sign-in, and
#: so must reach a locked one: unlocking it is a POST that names it.
_UNSEALED_PATHS = ("/auth/", "/spaces", "/private-spaces/")
#: The chat and the model's other readers: a private space is out of them
#: unless the chat is opened inside it (INBOX 1727).
_AI_PATHS = ("/chat", "/insights", "/questions", "/help/", "/night", "/editor")


def _still_sealed(session: Session, request: Request, workspace_id: str | None, private: list[str]) -> list[str]:
    """Which private spaces stay out of this request's reads."""
    from tessellate.core import private_turn

    # Idle is the person's, not the app's polls: only their own activity
    # (`/private-spaces/touch`) keeps the private spaces open.
    if not spacelock.opened(request.headers.get("X-Auth-Token")):
        return private
    path = request.url.path
    if path.startswith(_AI_PATHS):
        # The AI reads a private space only from a chat opened inside it,
        # and that turn keeps nothing (`private_turn.route`).
        if workspace_id in private:
            session.info[private_turn.IN_PRIVATE_SPACE] = True
        return [space for space in private if space != workspace_id]
    # An export leaves them out unless they are open and the person said so.
    if path.startswith("/export") and request.query_params.get("include_private_spaces") != "1":
        return private
    return []


def _seal_private_spaces(session: Session, request: Request, workspace_id: str | None) -> None:
    """INBOX 1727: a private space's rows are out of every read of this
    request until its session opened them (`core/spacelock.py`) with the
    vault key loaded. `database._add_workspace_filter` reads the ids; a write
    that names a locked private space is refused here, before it can land a
    row nothing could seal."""
    from tessellate.core.database import PRIVATE_SPACES, Space

    private = [row[0] for row in session.query(Space.id).filter(Space.is_private.is_(True)).all()]
    # Read once per request: the sealing hook and the reminders' notice reuse it.
    session.info[PRIVATE_SPACES] = private
    if not private:
        return
    private = _still_sealed(session, request, workspace_id, private)
    if not private:
        return
    session.info["sealed_workspaces"] = private
    if (
        workspace_id in private
        and request.method not in ("GET", "HEAD", "OPTIONS")
        and not request.url.path.startswith(_UNSEALED_PATHS)
    ):
        session.close()
        raise HTTPException(
            status_code=423,
            detail={"detail": "This private space is locked. Unlock it first.", "code": "private_space_locked", "hint": None},
        )


def _refuse_unknown_space(workspace_id: str) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={
            "detail": "That space does not exist. Pick one from the space menu.",
            "code": "unknown_space",
            "hint": None,
        },
    )


class _RequestGate:
    """Counts the requests holding a session, so a restore can wait for them.

    Restore replaces the database file and disposes the engine; a request still
    mid-transaction on it failed on the disposed pool or wrote to the old file
    (audit 1031 BK5; the job runner is held separately, 1028 K19). A restore
    pauses the gate (`drained`): new requests wait at `request`, and it waits
    for the ones in flight, not counting its own (the unlock gate gives every
    request a session). Keyed by the request's scope, which all of one
    request's dependencies share, so a request already inside is never held
    back by a restore that is waiting for it.
    """

    def __init__(self) -> None:
        self.cond = threading.Condition()
        self.active: dict[int, int] = {}
        self.pausers = 0

    @staticmethod
    def key(request: Request | None) -> int:
        return id(request.scope) if request is not None else 0

    @contextmanager
    def request(self, request: Request | None, wait: float = 60.0) -> Iterator[None]:
        key = self.key(request)
        with self.cond:
            if key not in self.active and not self.cond.wait_for(lambda: not self.pausers, timeout=wait):
                raise HTTPException(
                    status_code=503,
                    detail={"detail": "Tessellate is restoring a backup. Try again in a moment.", "code": "restoring", "hint": None},
                    headers={"Retry-After": "2"},
                )
            self.active[key] = self.active.get(key, 0) + 1
        try:
            yield
        finally:
            with self.cond:
                self.active[key] -= 1
                if not self.active[key]:
                    del self.active[key]
                self.cond.notify_all()

    @contextmanager
    def drained(self, deadline: float, own: Request | None = None) -> Iterator[bool]:
        mine = self.key(own) if own is not None else None
        with self.cond:
            self.pausers += 1
            idle = self.cond.wait_for(lambda: all(k == mine for k in self.active), timeout=deadline)
        try:
            yield idle
        finally:
            with self.cond:
                self.pausers -= 1
                self.cond.notify_all()


_gate = _RequestGate()
drained = _gate.drained


def requests_in_flight() -> int:
    return sum(_gate.active.values())


def get_session(request: Request = None) -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed, counted
    while it is held (`_RequestGate`)."""
    yield from _counted_session(request)


def _counted_session(request: Request | None, *, seal: bool = True) -> Iterator[Session]:
    with _gate.request(request):
        yield from _open_session(request, seal=seal)


@contextmanager
def brief_session(request: Request | None = None) -> Iterator[Session]:
    """`get_session` for a check that reads and lets go before the handler
    runs, so a long poll behind it is not counted as in flight. It reads the
    sign-in only, so it skips the private spaces' read (`_seal_private_spaces`)."""
    held = _counted_session(request, seal=False)
    try:
        yield next(held)
    finally:
        held.close()


def _open_session(request: Request | None, *, seal: bool = True) -> Iterator[Session]:
    """One session per request, always closed.

    The `X-Workspace-ID` header scopes every query, so it must name a space
    (or be `all`): an id that is none of those is 422, not a filter that
    matches nothing (audit 1031 BK3). The auth routes run before a space means
    anything and ignore it, so a stale id can never lock the person out."""
    session = get_db().session()
    if request is not None:
        workspace_id = request.headers.get("X-Workspace-ID")
        if workspace_id and not request.url.path.startswith("/auth/"):
            if workspace_id != "all" and not _space_known(session, workspace_id):
                session.close()
                raise _refuse_unknown_space(workspace_id)
            session.info["workspace_id"] = workspace_id
            # Resolved here, once, because the statement-level filter in
            # database.py runs for every query and must not issue one of its
            # own (it would re-enter that same event). Only "all" needs it.
            if workspace_id == "all":
                from tessellate.core.database import Space

                session.info["hidden_workspaces"] = [
                    row[0]
                    for row in session.query(Space.id)
                    .filter(Space.hidden_from_all.is_(True))
                    .all()
                ]
        if seal:
            _seal_private_spaces(session, request, workspace_id)
    try:
        yield session
    finally:
        session.close()


def get_or_404(
    session: Session, model: type[_ModelT], obj_id: object, detail: str
) -> _ModelT:
    """Fetch a row by primary key, or raise the 404 the route wants.

    Every route file had its own copy of `row = session.get(Model, id); if
    row is None: raise HTTPException(404, "...")`, ~39 of them across 12
    files, found by grep, all the same three lines with a different model
    and message. This is the plain "look up by id, 404 if missing" shape
    only; a lookup that also checks something else about the row (soft
    delete, ownership, an index bound) stays inline at its call site rather
    than being bent to fit here, because bending it would either change what
    it checks or make the helper lie about what it does.

    `detail` is required rather than derived from `model.__name__`, because
    the existing messages are user-facing text ("No such preference",
    "Attachment not found", "No note with id 5") that this refactor is not
    meant to alter: passing it explicitly is what keeps that text byte-for-
    byte the same as before.
    """
    obj = session.get(model, obj_id)
    if obj is None:
        raise HTTPException(status_code=404, detail=detail)
    return obj


def store_quietly(session: Session, entry: Entry) -> bool:
    """Best-effort embedding refresh for a note that was just written.

    Every caller wants the same two things: never fail the user's save because
    the embedding backend is unhappy, and never lose the reason it was unhappy.
    The bare ``except Exception: pass`` this replaces delivered only the first, 
    so a backend that had stopped working produced notes that quietly dropped
    out of semantic search with nothing anywhere to say why.

    It lives here, and not in `ai/embeddings.py` where it reads like it
    belongs, for one reason: it needs the shared `EmbeddingService`, and this
    module is the only thing allowed to hand that out. From inside `embeddings`
    it could only be reached by importing this module back, a real cycle,
    which a function-local import defers rather than removes.

    Returns True if a vector was stored.
    """
    try:
        return get_embeddings().store_for_entry(session, entry)
    except Exception:  # noqa: BLE001  # the whole point is that nothing escapes
        logging.getLogger("tessellate.embeddings").warning(
            "couldn't embed entry %s; it stays keyword-searchable only",
            getattr(entry, "id", "?"),
            exc_info=True,
        )
        return False

def store_quietly_many(session: Session, entries: list[Entry]) -> int:
    """`store_quietly` for a batch: one encode and one commit for the lot.

    A bulk import used to call `store_quietly` per note, and that commits, so
    5,000 notes paid 5,000 fsyncs (L508). Returns how many vectors were stored.
    """
    try:
        return get_embeddings().store_for_entries(session, entries)
    except Exception:  # noqa: BLE001  # nothing here may fail the import
        logging.getLogger("tessellate.embeddings").warning(
            "couldn't embed a batch of %s entries; they stay keyword-searchable only",
            len(entries),
            exc_info=True,
        )
        return 0


#: How many notes have to arrive or vanish at once before the app says the
#: search index is worth rebuilding. Twenty is roughly "an import or a restore
#: happened", not "you had a productive afternoon", a suggestion that fires
#: on ordinary use is a suggestion people learn to ignore.
INDEX_STALE_SUGGEST_AT = 20


def mark_index_stale(count: int) -> None:
    """Record that `count` notes changed outside the one-note-at-a-time path.

    Asked for directly: *"suggest rebuilding the search index upon large
    changes."* A note saved through the app embeds itself as it goes
    (`store_quietly` above); a note that arrives by bulk import or comes back
    from a backup restore does not always, and nothing anywhere said so, the
    only symptom was semantic search quietly missing things it should have
    found.

    A counter rather than a boolean, because "3 notes" and "1,400 notes" are
    different situations and only one of them is worth interrupting anybody
    for. Kept in preferences (not the database) so a restore cannot roll the
    fact of the restore back over itself.
    """
    if count <= 0:
        return
    config = get_config()
    current = int(config.get_preference("index_stale_notes", 0) or 0)
    config.set_preference("index_stale_notes", current + count)


def clear_index_stale() -> None:
    """Called when a rebuild starts: the backlog it was counting is gone."""
    get_config().set_preference("index_stale_notes", 0)


def index_stale_notes() -> int:
    return int(get_config().get_preference("index_stale_notes", 0) or 0)


#: Handed to the model manager so its durable jobs can find the running app's
#: own objects without importing this module (an import cycle).
#: Not named `_model_manager`: that is the running manager above, and the
#: module under its name made every chat and /models/status a 500.
from tessellate.ai import model_manager as _manager_module  # noqa: E402

_manager_module.APP_GETTERS.update(db=get_db, embeddings=get_embeddings, ollama=get_ollama)

from tessellate.ai import voice as _voice  # noqa: E402

_voice.CONFIG_PEEK = peek_config
