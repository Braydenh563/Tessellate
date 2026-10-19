"""Shared test fixtures.

Every test gets a throwaway data directory so nothing ever touches a
real database, and singletons are rebuilt between tests.
"""

from __future__ import annotations

import os
import importlib
import shutil
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tessellate.ai import model_manager, spelling
from tessellate.core import background, deps, extras, jobs, taskhistory, vault

#: Loaded for what they register (the typed reader, the help topics), which a
#: test that classifies a question without the chat route would otherwise miss.
for _loaded in ("tessellate.ai.commands", "tessellate.ai.help_chat"):
    importlib.import_module(_loaded)


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
                text = _shared_texts[key] = _real_read_text(self, encoding, errors)
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
    yield deps.get_config()
    # A worker the test started (the embedding warm-up after a capture, a
    # caption job after an attach) would otherwise rebuild the app state from
    # the repo's `data/` once it is reset.
    jobs.shutdown(2.0)
    background.join_all()
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
    from fakes_http import FakeResponse

    sent: list[dict] = []
    queued: list = []

    def fake_post(url, json=None, headers=None, stream=False, timeout=None):
        sent.append({"url": url, "json": json})
        return queued.pop(0) if queued else FakeResponse(payload={})

    monkeypatch.setattr("tessellate.ai.openai_client.requests.post", fake_post)
    return type("Capture", (), {"sent": sent, "queue": queued})()


@pytest.fixture
def openai_client():
    """An `OpenAICompatClient` that can never reach the network."""
    from tessellate.ai.openai_client import OpenAICompatClient

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
