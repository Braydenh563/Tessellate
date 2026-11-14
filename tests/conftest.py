"""Shared test fixtures.

Every test gets a throwaway data directory so nothing ever touches a
real database, and singletons are rebuilt between tests.
"""

from __future__ import annotations

import os
import re
import importlib
from contextvars import Context, ContextVar
import shutil
import sys
from pathlib import Path
from datetime import date

import pytest
from fastapi.testclient import TestClient

from tessellate.ai import model_manager, spelling
from tessellate.core import deps, extras, jobs, taskhistory, vault

#: Loaded for what they register (the typed reader, the help topics), which a
#: test that classifies a question without the chat route would otherwise miss.
for _loaded in ("tessellate.ai.commands", "tessellate.ai.help_chat"):
    importlib.import_module(_loaded)


# --- one dependant per route endpoint, however many apps the tests build -------
#
# FastAPI (0.16x) builds an included router's route state on the first request
# an app routes through it, and every test that makes a `client` builds a new
# app: the first request then spent about 1.2 s in `get_dependant` and
# pydantic's TypeAdapters for 633 routes (cProfile, CI time 1102), the same
# work for the same module-level endpoints in every test. A dependant depends
# only on the path, the endpoint and its dependencies, not on the app (the
# overrides are read from the app per request), so one per process is kept.
# Endpoints defined inside `create_app` (`<locals>`) are new per app and are
# not kept, or the cache would pin every dead app the way the callable caches
# below did.


def _share_route_dependants() -> None:
    import fastapi.routing as fastapi_routing

    build = getattr(fastapi_routing, "_build_dependant_with_parameterless_dependencies", None)
    if build is None or getattr(build, "_shared", False):
        return  # another FastAPI: nothing to share, the tests run as they are
    kept: dict = {}

    def per_app(callable_) -> bool:
        return "<locals>" in getattr(callable_, "__qualname__", "<locals>")

    def shared(*, path, call, dependencies):
        if per_app(call) or any(per_app(d.dependency) for d in dependencies):
            return build(path=path, call=call, dependencies=dependencies)
        try:
            key = (path, call, tuple(dependencies))
            found = kept.get(key)
        except TypeError:  # an unhashable dependency: build it as FastAPI would
            return build(path=path, call=call, dependencies=dependencies)
        if found is None:
            found = kept[key] = build(path=path, call=call, dependencies=dependencies)
        return found

    shared._shared = True
    fastapi_routing._build_dependant_with_parameterless_dependencies = shared

    # The response model's field, the other per-route TypeAdapter: only the
    # plain (name, type, mode) form the route state uses is kept.
    make_field = getattr(fastapi_routing, "create_model_field", None)
    if make_field is None:
        return
    fields: dict = {}

    def shared_field(name, type_=None, *args, mode="validation", **kwargs):
        if args or kwargs or per_app(type_):
            return make_field(name, type_, *args, mode=mode, **kwargs)
        try:
            key = (name, type_, mode)
            found = fields.get(key)
        except TypeError:
            return make_field(name, type_, mode=mode)
        if found is None:
            found = fields[key] = make_field(name, type_, mode=mode)
        return found

    fastapi_routing.create_model_field = shared_field


_share_route_dependants()


# --- one simulated overlay hour per session, however many xdist workers ----------
#
# The overlay tests read the same seeded hours (2 to 20 s each) from several files, and every `-n auto` worker used
# to simulate its own copy (the CI profile of 1109: up to four runs of one hour). The controller makes one folder, the
# workers inherit the variable, and `tests/overlay_sim_1670.disk_memo` computes each hour once and shares it.

def pytest_addoption(parser):
    parser.addoption("--shard", default=None, help="i/n: run only the test files of leg i of n (tests/_shard.py), for parallel CI legs")


def pytest_collection_modifyitems(config, items):
    spec = config.getoption("--shard")
    if spec:
        from tests import _shard

        kept, dropped = _shard.split(items, spec)
        config.hook.pytest_deselected(items=dropped)
        items[:] = kept


def pytest_configure(config):
    if os.environ.get("TESSELLATE_SIM_CACHE") or os.environ.get("PYTEST_XDIST_WORKER"):
        return
    import tempfile

    os.environ["TESSELLATE_SIM_CACHE"] = tempfile.mkdtemp(prefix="tessellate-sim-")
    config._tessellate_sim_cache = os.environ["TESSELLATE_SIM_CACHE"]


def pytest_unconfigure(config):
    folder = getattr(config, "_tessellate_sim_cache", None)
    if folder:
        shutil.rmtree(folder, ignore_errors=True)
        os.environ.pop("TESSELLATE_SIM_CACHE", None)


# --- one copy of each source file, however many test modules read it ----------
#
# About 145 test modules read a frontend file into a module-level constant
# (`SRC = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(...)`: 36 of
# them index.html, 24 whiteboard.js, and so on). Every call decoded a fresh
# copy, and the module keeps it for the whole session, so collection alone held
# 180 MB of identical strings in every pytest-xdist worker (measured with
# tracemalloc: 181 MB under `codecs`, of 437 MB traced; about 650 MB RSS before
# the first test ran). Strings are immutable, so handing every caller the same
# object is invisible to the tests and drops that to the 11 MB the files
# really are. Keyed by size and mtime so a test that writes one of these files
# still reads what it wrote. The repo-scanning tests (`tests/_repo_files.py`)
# read every `src/` and `tests/` file and some of `docs/` between them, so those
# trees share the same cache; `errors` is part of the key because a scanner
# that reads with `errors="replace"` gets different text from one that does not.

_REPO = Path(__file__).resolve().parents[1]
_INDEX_HTML = _REPO / "frontend" / "index.html"
_SURFACE_SCRIPT = re.compile(r'<script type="text/x-surface"([^>]*)>(.*?)</script>', re.S)
_SHARED_PREFIXES = tuple(str(_REPO / d) + os.sep for d in ("frontend", "src", "docs", "tests"))
_real_read_text = Path.read_text
_shared_texts: dict[tuple, str] = {}


def _read_text_once(self, encoding=None, errors=None):
    try:
        if str(self.resolve()).startswith(_SHARED_PREFIXES):
            st = self.stat()
            key = (str(self), encoding, errors, st.st_mtime_ns, st.st_size)
            text = _shared_texts.get(key)
            if text is None:
                text = _real_read_text(self, encoding, errors)
                if self.resolve() == _INDEX_HTML:
                    # The page keeps each surface's markup as raw text in a
                    # `<script type="text/x-surface">` so the parser makes no
                    # nodes for it at boot (settings-body.js). The lints that
                    # read it for ids, classes and structure see the markup
                    # where it always was, a `<template data-surface>`, so
                    # none of them loses a surface; the raw form is held by
                    # tests/test_surface_scripts.py, which reads the file.
                    text = _SURFACE_SCRIPT.sub(r"<template\1>\2</template>", text)
                _shared_texts[key] = text
            return text
    except OSError:
        pass  # let the real call raise the error the test expects
    return _real_read_text(self, encoding, errors)


Path.read_text = _read_text_once


@pytest.fixture(scope="session")
def repo_tree():
    """`repo_files` from `tests/_repo_files.py`: the checkout walked once per
    process, filtered per call. A scanner that builds its file list at import
    (for `parametrize`) imports the function; one that scans inside a test can
    take this fixture instead."""
    from tests._repo_files import repo_files

    return repo_files


@pytest.fixture(autouse=True)
def _own_run_folder(tmp_path, monkeypatch):
    """A test that starts a server claim writes a running-copies record
    (core/run_records.py); it goes to the test's folder, never the
    developer's own per-user one."""
    monkeypatch.setenv("TESSELLATE_RUN_DIR", str(tmp_path / "_run"))


#: The suite's fixed day (a Saturday, the same day `_frozen_clock.FIXED_NOW` uses).
SUITE_DAY = date(2026, 8, 1)


@pytest.fixture(autouse=True)
def _fixed_day(monkeypatch):
    """No test reads the real calendar through `clock.today()` (CLAUDE.md
    section 8: tests use a fixed clock). The chat reply seed carries the day,
    so composer wording flipped between runs (1693 a, 8 failures on 2026-11-07).
    A test that sets its own day with `monkeypatch.setattr(clock, "today", ...)`
    runs after this fixture and wins."""
    from tessellate.core import clock

    monkeypatch.setattr(clock, "today", lambda: SUITE_DAY)


@pytest.fixture(autouse=True)
def _forget_the_reported_locale():
    """A request's locale is kept in memory for readers that take none (`recognise.note_locale`); a test that
    posted "en-US" must not make the next test's "3/4" month first."""
    yield
    from tessellate.ai import recognise

    recognise._HEMISPHERE["reported"] = None  # noqa: SLF001


@pytest.fixture(autouse=True)
def _no_repo_data_folder():
    """A test that builds the app's config without `app_state` falls back to
    `./data`, which is the repo's own folder when pytest runs from the root
    (four `test_mcp_server` tests did, seen as an untracked `data/` after CI).
    It clears the folder, and in a serial run fails the test that made it. Under
    xdist the workers share the folder, so a leak in one would fail whichever
    test in another worker was running beside it: there it only cleans up, and
    `pytest -p no:xdist <file>` names the offender."""
    folder = Path(__file__).resolve().parents[1] / "data"
    existed = folder.exists()
    yield
    if not existed and folder.exists():
        shutil.rmtree(folder, ignore_errors=True)
        if not os.environ.get("PYTEST_XDIST_WORKER"):
            pytest.fail("this test wrote the repo's data/ folder: use the app_state fixture (or TESSELLATE_DATA_DIR)")


@pytest.fixture()
def app_state(tmp_path, monkeypatch):
    """Fresh singletons pointed at a temp dir. Yields the ConfigManager."""
    # Make sure a developer's real .env can't leak into tests.
    monkeypatch.setenv("TESSELLATE_DATA_DIR", str(tmp_path / "data"))
    deps.reset_app_state()
    model_manager.reset_jobs()
    # The vault's key is module-level too: a test that unlocked it left the
    # next test in the same process reading private notes with a stale key
    # ("couldn't be decrypted" where "unlock to read it" was asserted), which
    # only showed once the suite ran in parallel and the order changed.
    vault.close()
    # Process-global like the log buffer, so it leaks between tests exactly the
    # way the job registry does, and a test asserting "no jobs have finished"
    # would otherwise pass or fail on what ran before it.
    taskhistory.clear()
    # The app's start enqueues the speller's one-per-process warm-up on the job
    # pool; whichever test first started an app saw it in `/tasks` ("Warm: warm
    # the spelling lists"), so test_tasks passed or failed on the order a worker
    # ran its files in. No test wants the job, and the lists load on first use.
    spelling._WARMED["started"] = True
    # The extras installer's one-at-a-time record is process-global too: an
    # install a test queued and the pool then dropped (or a removal still
    # running at teardown) stayed "running" for the next test, which saw
    # "Installing ... (needle)" in `/tasks`.
    extras.reset_for_tests()
    deps.init_app_state(data_dir=tmp_path / "data")
    # A sign-in from a new device on the network is held up to 45 s for this
    # computer's Allow. No test answers it unless it means to, so each one
    # that reached the hold sat out the whole wait (47 s for the IPv6 throttle
    # test, CI time 1102). A test about the wait sets its own.
    from tessellate.api import routes_auth

    monkeypatch.setattr(routes_auth, "DEVICE_WAIT_SECONDS", 0.3)
    yield deps.get_config()
    # A worker the test started (the embedding warm-up after a capture, a
    # caption job after an attach) would otherwise rebuild the app state from
    # the repo's `data/` once it is reset.
    jobs.shutdown(2.0)
    jobs.join_threads()
    extras.reset_for_tests()
    vault.close()
    deps.reset_app_state()
    model_manager.reset_jobs()
    taskhistory.clear()


@pytest.fixture()
def session(app_state):
    s = deps.get_db().session()
    yield s
    s.close()


@pytest.fixture()
def client(app_state):
    """TestClient with ALL AI unavailable, proves capture and keyword
    search work with zero AI, and keeps results identical whether or not
    the developer happens to have Ollama running."""
    from tessellate.api.app import create_app
    from tests.fakes import FakeEmbeddingService, FakeOllama

    deps.override_ai(
        ollama=FakeOllama(running=False),
        embeddings=FakeEmbeddingService(available=False),
    )
    return TestClient(create_app())


@pytest.fixture()
def fake_ollama(app_state):
    from tests.fakes import FakeOllama

    fake = FakeOllama(running=True)
    deps.override_ai(ollama=fake)
    return fake


@pytest.fixture()
def fake_embeddings(app_state):
    from tests.fakes import FakeEmbeddingService

    fake = FakeEmbeddingService(available=True)
    deps.override_ai(embeddings=fake)
    return fake


@pytest.fixture()
def ai_client(app_state, fake_ollama, fake_embeddings):
    """TestClient with working (fake) AI: full Phase 2 behaviour."""
    from tessellate.api.app import create_app

    return TestClient(create_app())


# --- a fake OpenAI-compatible transport (§6) ---------------------------------
#
# The fixtures live here so pytest finds them by name; `FakeResponse` and `sse`
# are ordinary helpers and live in `fakes_http.py`, because importing a *test*
# module to get them re-binds everything else that import carries, which is
# how `client` from `test_providers` came to shadow the `client` fixture above
# and silently decide which HTTP client three files' tests were handed.


@pytest.fixture
def capture_post(monkeypatch):
    """Swap `requests.post` inside the OpenAI client and record the payloads."""
    from tests.fakes_http import FakeResponse

    sent: list[dict] = []
    queued: list = []

    def fake_post(url, json=None, headers=None, stream=False, timeout=None):
        sent.append({"url": url, "json": json})
        return queued.pop(0) if queued else FakeResponse(payload={})

    monkeypatch.setattr("tessellate.ai.openai_client.requests.post", fake_post)
    return type("Capture", (), {"sent": sent, "queue": queued})()


@pytest.fixture
def openai_client(tmp_path, monkeypatch):
    """An `OpenAICompatClient` that can never reach the network. Its requests
    log a job run, so the data dir is a scratch one, never the repo's."""
    from tessellate.ai.openai_client import OpenAICompatClient

    monkeypatch.setenv("TESSELLATE_DATA_DIR", str(tmp_path))

    c = OpenAICompatClient(base_url="http://localhost:1234/v1")
    c._catalog = []
    c._context_lengths = {"m": 8192}
    return c


# --- no test may run pip ------------------------------------------------------
#
# The suite once installed torch. `EmbeddingService` auto-installs the
# "semantic" extra when the sentence-transformers backend is selected and the
# import fails, and one test reached that path with a real thread: the full
# run then carried a live `pip install sentence-transformers` for twenty
# minutes, `/debug/health` reported it as a running job (which failed
# test_debug_health), and the sandbox venv grew by 700 MB of packages
# CLAUDE.md says never to install. Every test that means to exercise the
# installer already fakes `extras.subprocess.Popen` itself (a monkeypatch
# inside the test overrides this one); everything else gets a Popen that
# refuses, so an accidental install is a loud failure instead of a silent
# download.


@pytest.fixture(autouse=True)
def _no_test_runs_pip(monkeypatch):
    from tessellate.core import extras

    # `extras.subprocess` is the one shared `subprocess` module, so a blanket
    # refusal broke every other Popen in the process: `platform.platform()`
    # runs `file` through it, and the support bundle test failed in isolation
    # while passing in the full run only because an earlier test had filled
    # platform's cache. Refuse pip; let everything else through.
    real_popen = extras.subprocess.Popen

    def guard(args, *rest, **kwargs):
        argv = args if isinstance(args, (list, tuple)) else [args]
        #: The command `pip`, not any text holding the letters: a temp file's
        #: random name ("tmpq7pipx2.js") failed a test on CI that way, 2026-10-12.
        if any(os.path.basename(str(part)).lower() in ("pip", "pip3", "pip.exe", "pip3.exe") for part in argv):
            raise RuntimeError(
                "a test reached the real installer; fake extras.subprocess.Popen "
                "or extras.start in the test (see conftest._no_test_runs_pip)"
            )
        return real_popen(args, *rest, **kwargs)

    monkeypatch.setattr(extras.subprocess, "Popen", guard)
    yield


# --- Brief 13: the harness fixtures (tests/test_harness_verifier_spec.py) -----
#
# Both are `FakeOllama` with a script, and both stand in for a *reported* small
# model behaviour rather than for a model in general:
#
# - `fake_model_with_paged_list` fetches one page and stops, which is the
#   behaviour CHAT_PLAN decision 10 is about. The run's paging nudge is what
#   gets it to page two, and the point of the spec is that the app does the
#   nudging rather than hoping.
# - `fake_model_that_loops` calls the same tool for ever, which is the shape
#   the run budget exists to bound.
#
# Neither says anything about what a real small model does with either prompt:
# every provider test here runs against a fake transport (CLAUDE.md section 4).


@pytest.fixture()
def fake_model_with_paged_list(app_state, fake_embeddings):
    """Pages `list_notes` twenty at a time, one page per turn, then reads one
    note and answers."""
    from tests.fakes import FakeOllama

    fake = FakeOllama(running=True)
    script: list[list[dict]] = []
    for page in range(4):
        script.append(
            [{"name": "list_notes", "arguments": {"offset": page * 20, "limit": 20}}]
        )
        script.append([])  # the round that answers, ending the turn
    script.append([{"name": "get_note", "arguments": {"note_id": 1}}])
    script.append([])
    fake.tool_script = script
    deps.override_ai(ollama=fake)
    return fake


@pytest.fixture()
def fake_model_that_loops(app_state, fake_embeddings):
    """Calls one tool for ever, and reports a thousand tokens a round.

    The token figures are the fixture's own, not a measurement: they are
    chosen so the budget in the spec (2,000 tokens) is reached in two rounds
    and the test is about the enforcement rather than about arithmetic.
    """
    from tests.fakes import FakeOllama

    fake = FakeOllama(running=True)
    fake.tool_script = [
        [{"name": "notebook_overview", "arguments": {}}] for _ in range(40)
    ]
    fake.stats = {**fake.stats, "prompt_tokens": 600, "output_tokens": 400}
    deps.override_ai(ollama=fake)
    return fake


@pytest.fixture(autouse=True)
def _forget_the_docker_probe():
    """`docker_available()` remembers its last answer for fifteen seconds, and
    a whole test session runs well inside fifteen seconds.

    Without this, one test that fakes a stopped daemon leaves "no" behind for
    every test after it that asks the real function, and which tests those are
    depends on the order they ran in. Cleared on both sides so a test is
    neither poisoned by its predecessor nor the thing that poisons its
    successor."""
    from tessellate.search import searxng_docker

    searxng_docker.forget_docker_daemon_state()
    yield
    searxng_docker.forget_docker_daemon_state()


@pytest.fixture(autouse=True)
def _no_real_keyring():
    """Secret settings (core/secrets_store.py) use the OS keyring when one is
    present; a developer's machine must never have a test write into theirs.
    Every test starts on a store with no keyring, so the owner-only file in the
    test's own data dir is used; a test that wants a keyring sets a fake."""
    from tessellate.core import pinstore

    pinstore.set_store(pinstore.Store())
    yield
    pinstore.set_store(None)


@pytest.fixture(autouse=True)
def _forget_the_ocr_probe():
    """`/models/status` remembers the OCR reader question for thirty seconds
    (routes_models.ocr_probe); a test that fakes a reader must not leave its
    answer to the next one. Read from `sys.modules`, as the fixture below."""
    def forget():
        module = sys.modules.get("tessellate.api.routes_models")
        if module is not None:
            module.forget_ocr_probe()

    forget()
    yield
    forget()


@pytest.fixture(autouse=True)
def _forget_ollama_down():
    """The refused-connection memory is module level; a test that refused one
    must not make the next test's Ollama look off. Read from `sys.modules`,
    not imported: importing it here reaches the config before a test's
    `app_state` does, and the default config writes the repo's `data/`."""
    def forget():
        module = sys.modules.get("tessellate.ai.ollama_client")
        if module is not None:
            module._down_until.clear()

    forget()
    yield
    forget()


@pytest.fixture(autouse=True)
def _forget_asked_image_readers():
    """`media_process._ASKED` is per run; a test's upload ids and hashed file
    names repeat in the next test's notebook (INBOX 1465)."""
    module = sys.modules.get("tessellate.core.media_process")
    if module is not None:
        module._ASKED.clear()
    yield
    if module is not None:
        module._ASKED.clear()


@pytest.fixture(autouse=True)
def _forget_span_reviews():
    """`routes_timeline` keeps a span's model review per process; a test's
    note ids repeat in the next test's notebook."""
    module = sys.modules.get("tessellate.api.routes_timeline")
    if module is not None:
        module._SPAN_SAID.clear()
        module._SPAN_FLIGHTS.clear()
    yield
    if module is not None:
        module._SPAN_SAID.clear()
        module._SPAN_FLIGHTS.clear()


@pytest.fixture(autouse=True)
def _reset_the_librarian():
    """The librarian's Quit flag and hold are module level (one scheduler per
    process), so a test that pressed Quit left them set for every test after
    it in the same process, in whatever order that run happened to have.
    Cleared on both sides, like `_forget_the_docker_probe` above. See
    tests/test_autonomous_state_isolation.py."""
    from tessellate.ai import autonomous

    autonomous.reset_state()
    yield
    autonomous.reset_state()


@pytest.fixture(autouse=True)
def _release_fastapi_callable_caches():
    """Stop FastAPI's process-wide callable caches from pinning every test app.

    `fastapi.dependencies.models` keeps three `lru_cache`s (generator, async
    generator and coroutine classification, 4,096 entries each) keyed by the
    *identity* of each endpoint and dependency callable. `create_app()` defines
    its system routes (`/health`, `/openapi.json`, `/changelog`...) as closures
    over the `app` being built, so one cache entry holds that closure, the
    closure holds the `FastAPI` instance, and the instance holds every router,
    route context, pydantic field and the first request's lazily built
    `_EffectiveRouteContext` objects: about 8 MB per app. The caches only
    evict at 4,096 entries, so a test process kept a few hundred dead apps and
    every pytest-xdist worker climbed to 2 to 2.7 GB by the end of the suite
    (four of them filled a 16 GB CI runner, which then shut down mid-run).
    Measured with a per-test RSS plugin: 7 to 9 MB per test that builds an app,
    perfectly linear, and `gc.get_referrers` on a dead app ends at
    `_is_*_callable_cached`.

    The app itself does not leak: a real process builds one. Clearing between
    tests is the whole fix, and it is a clear, not a patch, so what a test
    sees is unchanged (the caches only memoise a classification that is cheap
    to recompute). Found by `cache_clear` rather than by name so a FastAPI
    release that renames or adds one of them is still covered."""
    yield
    import sys

    models = sys.modules.get("fastapi.dependencies.models")
    if models is not None:
        for value in vars(models).values():
            clear = getattr(value, "cache_clear", None)
            if callable(clear):
                clear()


@pytest.fixture(autouse=True)
def _fresh_digest_context():
    """The digest keeps its per-answer state in context variables. The public
    entries run in a copy of the caller's context, but a helper called directly
    (`_pattern` reaches `_next_gap`, which appends to the gap leads) writes to
    the test's own context, and pytest runs every test of a worker in one. A
    test then read the leads an earlier one had used, so "a day ago" came out
    as another wording, depending on which tests shared the worker. Reset every
    one to its default per test."""
    from tessellate.ai import composer_digest, composer_digest_sentences

    # The variables live in the layer module they were moved to (K24); each is reset where it is defined.
    for module in (composer_digest, composer_digest_sentences):
        for var in vars(module).values():
            if isinstance(var, ContextVar):
                try:
                    var.set(Context().run(var.get))  # a fresh context answers with the variable's own default
                except LookupError:
                    # A variable with no default has nothing an earlier test could
                    # have left behind, so there is nothing to reset.
                    continue
