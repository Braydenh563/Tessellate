"""The Model Manager endpoints, fully offline via fakes."""

from __future__ import annotations

import time
from pathlib import Path

from sqlalchemy import select

from tessellate.ai.embeddings import EmbeddingService
from tessellate.core import deps
from tessellate.core.database import EmbeddingRecord
from tests.fakes import FakeOllama


def _wait_for(client, check, timeout: float = 5.0) -> dict:
    """Poll /models/status until `check(status)` is true (background jobs)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get("/models/status").json()
        if check(body):
            return body
        time.sleep(0.05)
    raise AssertionError("timed out waiting for background job")


def test_status_with_all_ai_down(client):
    body = client.get("/models/status").json()
    assert body["ollama_running"] is False
    assert body["installed_models"] == []
    assert body["chat_model"] == "llama3.2"
    assert body["chat_model_installed"] is None  # unknown while Ollama is off
    assert body["embedding_backend"] == "fastembed"
    assert body["embedding_ready"] is False
    assert body["pulls"] == {}


def test_suggested_catalog(client):
    body = client.get("/models/suggested").json()
    assert "llama3.2" in [m["name"] for m in body["text"]]
    assert "nomic-embed-text" in [m["name"] for m in body["embedding"]]


# --- the status pill: warming vs failed -----------------------------------------


def test_status_reports_embedding_error(client):
    body = client.get("/models/status").json()
    assert "embedding_warming" in body
    assert "embedding_error" in body


def test_embedding_failure_is_recorded_not_swallowed(app_state, monkeypatch):
    # Force the model load to fail deterministically. An offline machine
    # fails because the model isn't cached, but a networked CI runner would
    # download the real model and succeed, which isn't what this test is
    # about. We're checking that a genuine failure is RECORDED (last_error)
    # and not swallowed into a forever "warming up…" state (user-reported bug).
    service = EmbeddingService(deps.get_model_manager(), FakeOllama(running=False))

    def boom():
        raise RuntimeError("no embedding model available (forced for test)")

    monkeypatch.setattr(service, "_load_builtin_model", boom)
    assert service.embed_text("hello") is None
    assert service.last_error is not None
    assert service.is_ready() is False


def test_set_chat_model_requires_installed(ai_client):
    denied = ai_client.post("/models/chat-model", json={"name": "qwen2.5:3b"})
    assert denied.status_code == 400

    ok = ai_client.post("/models/chat-model", json={"name": "llama3.2"})
    assert ok.status_code == 200
    assert deps.get_config().get_preference("chat_model") == "llama3.2"


def test_set_chat_model_needs_ollama(client):
    assert client.post("/models/chat-model", json={"name": "llama3.2"}).status_code == 409


def test_pull_streams_progress_to_status(ai_client, fake_ollama):
    assert ai_client.post("/models/pull", json={"name": "nomic-embed-text"}).status_code == 200

    body = _wait_for(
        ai_client, lambda b: b["pulls"].get("nomic-embed-text", {}).get("status") == "success"
    )
    job = body["pulls"]["nomic-embed-text"]
    assert job["total"] == 1_000 and job["done"] == 1_000
    # The fake now reports it installed, like real Ollama would.
    assert any(m["name"] == "nomic-embed-text" for m in body["installed_models"])


def test_switch_embedding_backend_reindexes_everything(ai_client, fake_embeddings):
    ai_client.post("/entries", json={"content": "a funny scarecrow joke"})
    ai_client.post("/entries", json={"content": "buy milk and eggs"})

    response = ai_client.post(
        "/models/embedding-backend",
        json={"backend": "ollama", "model": "nomic-embed-text"},
    )
    assert response.status_code == 200

    # Through the model switch since INBOX 700 (`core/embedswitch.py`): the
    # new set is staged beside the old and swapped in, then the setting saved.
    from tessellate.core import embedswitch

    deadline = time.monotonic() + 10
    while embedswitch.status()["running"] and time.monotonic() < deadline:
        time.sleep(0.05)
    assert embedswitch.status()["outcome"] == "completed", embedswitch.status()

    config = deps.get_config()
    assert config.get_preference("embedding_backend") == "ollama"
    assert config.get_preference("embedding_model") == "nomic-embed-text"

    # Every entry got a fresh vector from the (fake) active backend.
    session = deps.get_db().session()
    try:
        records = list(session.scalars(select(EmbeddingRecord)))
        assert len(records) == 2
        assert {r.model_version for r in records} == {"fake:keywords-v1"}
    finally:
        session.close()


def test_embedding_switch_requires_model_for_ollama(ai_client):
    response = ai_client.post("/models/embedding-backend", json={"backend": "ollama"})
    assert response.status_code == 400


# --- the utility model (separate from the chat model, for cheap background jobs) --


def _save(client, content, **extra):
    response = client.post("/entries", json={"content": content, **extra})
    assert response.status_code == 201
    return response.json()


def test_utility_model_defaults_to_chat_model(app_state):
    manager = deps.get_model_manager()
    assert manager.utility_model() == manager.chat_model()
    manager.set_utility_model("phi3.5")
    assert manager.utility_model() == "phi3.5"
    manager.set_utility_model("")  # back to "same as chat"
    assert manager.utility_model() == manager.chat_model()


def test_status_reports_utility_model(client):
    body = client.get("/models/status").json()
    assert "utility_model" in body
    assert body["utility_model"] == ""  # unset by default


def test_set_utility_model_offline_still_saves(client):
    # Ollama unavailable in this fixture, an empty name always applies.
    assert client.post("/models/utility-model", json={"name": ""}).status_code == 200


def test_digest_uses_utility_model(ai_client, fake_ollama):
    deps.get_model_manager().set_utility_model("phi3.5")
    _save(ai_client, "a funny scarecrow joke")
    ai_client.post("/insights/digest")
    # The last chat call went to the utility model, not the chat model.
    assert fake_ollama.chat_models[-1] == "phi3.5"


# --- vision model (auto-detect or explicit) ---------------------------------


def test_vision_model_defaults_to_auto(app_state):
    manager = deps.get_model_manager()
    assert manager.vision_model() == ""


def test_resolve_vision_model_explicit_choice_wins(app_state, fake_ollama):
    manager = deps.get_model_manager()
    manager.set_vision_model("llama3.2-vision")
    # Wins even though nothing installed declares "vision", the same trust
    # chat_model() already extends an unverified explicit choice.
    assert manager.resolve_vision_model(fake_ollama) == "llama3.2-vision"


def test_resolve_vision_model_auto_detects_from_capabilities(app_state, fake_ollama):
    manager = deps.get_model_manager()
    fake_ollama.capabilities_declared = ["vision", "tools"]
    assert manager.resolve_vision_model(fake_ollama) == fake_ollama.installed[0]["name"]


def test_resolve_vision_model_is_none_when_nothing_declares_it(app_state, fake_ollama):
    manager = deps.get_model_manager()
    fake_ollama.capabilities_declared = ["tools"]  # no vision
    assert manager.resolve_vision_model(fake_ollama) is None


def test_status_reports_vision_model(client):
    body = client.get("/models/status").json()
    assert body["vision_model"] == ""
    assert body["vision_model_resolved"] is None  # Ollama not running (client fixture)


def test_set_vision_model_offline_still_saves(client):
    assert client.post("/models/vision-model", json={"name": ""}).status_code == 200


def test_set_vision_model_rejects_a_name_not_installed(ai_client):
    response = ai_client.post("/models/vision-model", json={"name": "not-a-real-model"})
    assert response.status_code == 400


def test_set_vision_model_persists(ai_client):
    ai_client.post("/models/vision-model", json={"name": "llama3.2"})
    assert deps.get_model_manager().vision_model() == "llama3.2"
    body = ai_client.get("/models/status").json()
    assert body["vision_model"] == "llama3.2"


# --- rebuilding the search index on demand ---------------------------------------
#
# Until this endpoint existed the *only* way to re-embed a notebook was to
# switch embedding backend and switch back: `set_embedding_backend` starts a
# re-index because it has to (vectors from two models cannot be compared), and
# that side effect was the whole mechanism.
#
# A stale index is not always the user's doing, though. `embedding_text`, what
# a vector is actually built from, has changed in this app to include a note's
# category, tags and attachment text, so vectors written before that encode
# less than the same note would today. Reported directly: "I have a whole
# category called hobbies but basically none came up in the semantic search."


def test_a_rebuild_can_be_asked_for_directly(ai_client, fake_embeddings):
    ai_client.post("/entries", json={"content": "seraphine and warwick", "category": "Hobbies"})
    ai_client.post("/entries", json={"content": "buy milk and eggs"})

    response = ai_client.post("/models/reindex")
    assert response.status_code == 200
    assert response.json()["reindex_started"] is True

    _wait_for(ai_client, lambda b: (b["reindex"] or {}).get("status") == "success")

    session = deps.get_db().session()
    try:
        records = list(session.scalars(select(EmbeddingRecord)))
        assert len(records) == 2
        assert {r.model_version for r in records} == {"fake:keywords-v1"}
    finally:
        session.close()


def test_a_rebuild_also_rebuilds_the_keyword_index(ai_client, fake_embeddings):
    """The keyword index (`search_index`) was built once, at the startup that
    created its table, and never again: after a restore, an import or a bug
    there was no way to ask for it. "Rebuild search index" now rebuilds both
    halves of search, in the job it already ran, and `/search/stats` says
    when and with how many rows."""
    from sqlalchemy import text as sa_text

    ai_client.post("/entries", json={"content": "the lighthouse keeper's log"})
    session = deps.get_db().session()
    try:
        # A drifted index: one row taken out behind the flush hook's back,
        # and one row for a note that does not exist.
        session.execute(sa_text("DELETE FROM search_index WHERE kind = 'note'"))
        from tessellate.search import index

        ghost = index._rowid(index.source_for("notes"), 999999)
        session.execute(
            sa_text(
                "INSERT INTO search_index(rowid, title, body, tags, kind, ref_id, source, "
                "space, flags, written) VALUES (:rowid, 'ghost', 'ghost', '', 'note', 999999, "
                "'notes', 'default', '', '')"
            ),
            {"rowid": ghost},
        )
        session.commit()
    finally:
        session.close()
    assert ai_client.post("/models/reindex").status_code == 200
    _wait_for(ai_client, lambda b: (b["reindex"] or {}).get("status") == "success")
    stats = ai_client.get("/search/stats").json()
    assert stats["index"]["note"] == 1
    assert stats["last_rebuild"]["rows"]["note"] == 1
    assert stats["last_rebuild"]["at"]


def test_a_rebuild_does_not_change_which_backend_is_in_use(ai_client, fake_embeddings):
    """It re-embeds with the *current* backend. A rebuild that quietly moved
    the user to a different one would be a settings change wearing a
    maintenance button's clothes."""
    config = deps.get_config()
    before = (
        config.get_preference("embedding_backend"),
        config.get_preference("embedding_model"),
    )
    ai_client.post("/entries", json={"content": "something to embed"})
    assert ai_client.post("/models/reindex").status_code == 200
    _wait_for(ai_client, lambda b: (b["reindex"] or {}).get("status") == "success")
    assert (
        config.get_preference("embedding_backend"),
        config.get_preference("embedding_model"),
    ) == before


def test_a_second_rebuild_while_one_runs_is_refused(ai_client, fake_embeddings, monkeypatch):
    """409, not a second thread racing the first over the same rows."""
    monkeypatch.setattr(
        "tessellate.api.routes_models.jobs.reindex_status",
        lambda: {"status": "running", "done": 1, "total": 9},
    )
    response = ai_client.post("/models/reindex")
    assert response.status_code == 409
    assert "already running" in response.json()["detail"]


def test_status_names_the_model_an_openai_server_actually_runs(client, monkeypatch):
    """Owner, packaged app: the chat header said llama3.2, not installed,
    while the server's own loaded model answered. On an OpenAI-dialect
    server the loaded model is what runs; report it."""
    from tessellate.core import deps

    config = deps.get_config()
    config.set_preference("llm_provider", "openai")
    ollama = deps.get_ollama()
    monkeypatch.setattr(ollama, "list_models", lambda: [{"name": "qwen3.5-4b-q4.gguf", "size": 1}])
    body = client.get("/models/status").json()
    assert body["chat_model_installed"] is False
    assert body["chat_model_effective"] == "qwen3.5-4b-q4.gguf"


# --- INBOX 277: what the utility role resolves to, and why ------------------
#
# A role can say one model and run another: the utility preference ships
# empty, and smart model routing off sends every background job to the chat
# model whatever the preference says. Settings used to show only the stored
# name, so a person who picked a small model and then turned routing off was
# told something untrue about their own notebook. The status poll now reports
# the resolved name and the reason, from the one function that decides it.


def test_status_reports_the_utility_model_it_resolves_to(client):
    body = client.get("/models/status").json()
    assert body["utility_model_resolved"] == body["chat_model"]
    assert body["utility_model_reason"] == "unset"


def test_status_says_a_chosen_utility_model_is_the_one_in_use(client):
    deps.get_model_manager().set_utility_model("phi3.5")
    body = client.get("/models/status").json()
    assert body["utility_model"] == "phi3.5"
    assert body["utility_model_resolved"] == "phi3.5"
    assert body["utility_model_reason"] == "chosen"


def test_status_says_routing_off_sends_background_jobs_to_chat(client):
    manager = deps.get_model_manager()
    manager.set_utility_model("phi3.5")
    manager._config.set_preference("smart_model_routing_enabled", False)
    body = client.get("/models/status").json()
    # The stored choice is still reported (the picker shows it), and the
    # resolved name says what actually runs.
    assert body["utility_model"] == "phi3.5"
    assert body["utility_model_resolved"] == body["chat_model"]
    assert body["utility_model_reason"] == "routing_off"


def test_resolution_agrees_with_the_getter_in_every_case(app_state):
    manager = deps.get_model_manager()
    for chosen in ("", "phi3.5"):
        for routing in (True, False):
            manager.set_utility_model(chosen)
            manager._config.set_preference("smart_model_routing_enabled", routing)
            model, _reason = manager.utility_resolution()
            assert model == manager.utility_model()


def test_status_never_waits_on_a_capability_probe(client, monkeypatch):
    """The owner's log: `GET /models/status: signal timed out` twice in the
    first minute after a start. The poll resolved the vision model by asking
    each installed model its capabilities in turn, up to 5s a model, inside
    an 8s browser budget. It now answers from the cache and asks in the
    background, so a slow `/api/show` costs the poll nothing and the next
    poll has the answer."""
    import threading
    import time

    from tessellate.ai.ollama_client import OllamaClient
    from tessellate.core import deps

    ollama = OllamaClient("http://127.0.0.1:9")
    monkeypatch.setattr(deps, "get_ollama", lambda: ollama)
    installed = [{"name": f"model-{i}", "size": 1} for i in range(4)]
    monkeypatch.setattr(ollama, "list_models", lambda: installed)
    asked = threading.Event()
    release = threading.Event()

    def slow_show(model):
        asked.set()
        # Blocks until the test lets it go (or a minute passes): a status
        # call that waited on this probe would take the whole minute.
        release.wait(60)
        ollama._shown[model] = {"capabilities": ["vision"] if model == "model-2" else ["completion"]}
        return ollama._shown[model]

    monkeypatch.setattr(ollama, "show", slow_show)
    started = time.monotonic()
    body = client.get("/models/status").json()
    # The probe is still blocked here (released below), so any answer well
    # inside its minute proves the poll did not wait on it. The margin is wide
    # on purpose: CI once took 4.6s for this call under load (2026-09-26)
    # against a 4s limit set beside a 5s probe, which measured the runner.
    assert time.monotonic() - started < 30
    assert not release.is_set()
    assert body["ollama_running"] is True
    assert body["vision_model_resolved"] is None  # unknown yet, not waited for
    assert asked.wait(5)
    release.set()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and len(ollama._shown) < 4:
        time.sleep(0.05)
    assert client.get("/models/status").json()["vision_model_resolved"] == "model-2"


def test_warm_filing_is_served_where_the_page_asks_for_it(client):
    # The page posts to /models/warm-filing once it is unlocked (app.js). The
    # router already carries the /models prefix; a path repeating it served
    # the route at /models/models/warm-filing, and every tab's load logged a
    # 405 that failed the E2E smoke suite.
    assert client.post("/models/warm-filing").json() == {"status": "ok"}


def test_a_launch_with_no_waiting_notes_queues_no_filing_row(client, monkeypatch):
    # Every page load queued the stand-in retry as a "Filing a note" job even
    # on an empty notebook, so the bell and Activity said a note was being
    # filed when there was none (scan 2026-10-11).
    from tessellate.core import jobs

    queued: list[str] = []
    monkeypatch.setattr(jobs, "enqueue", lambda kind, *a, **k: queued.append(kind))
    monkeypatch.setattr(deps.get_ollama().__class__, "is_running", lambda self: True, raising=False)
    client.post("/models/warm-filing")
    assert queued == ["warm-filing"]


def test_a_launch_with_no_model_running_does_not_queue_a_warm_up_row(client, monkeypatch):
    # "Warming up the filing model" showed in the bell and Activity on every
    # launch of a notebook with no model, for a job that returned at once.
    from tessellate.core import jobs

    queued: list[str] = []
    monkeypatch.setattr(jobs, "enqueue", lambda kind, *a, **k: queued.append(kind))
    monkeypatch.setattr(deps.get_ollama().__class__, "is_running", lambda self: False, raising=False)
    client.post("/models/warm-filing")
    assert queued == []


def test_a_launch_with_a_stand_in_note_retries_its_filing(client, monkeypatch):
    from tessellate.core import jobs

    queued: list[str] = []
    monkeypatch.setattr(jobs, "enqueue", lambda kind, *a, **k: queued.append(kind))
    from tessellate.api import routes_entries

    monkeypatch.setattr(routes_entries, "stand_ins_waiting", lambda: 2)
    monkeypatch.setattr(deps.get_ollama().__class__, "is_running", lambda self: True, raising=False)
    client.post("/models/warm-filing")
    assert queued == ["warm-filing", "file-entry"]


def test_status_serves_the_last_answer_while_the_runner_is_slow(client, monkeypatch):
    """`GET /models/status: signal timed out` again, with the capability probe
    already off the request path: what is left is the poll waiting on the
    runner's own model list (up to 5s on Ollama, two 5s tries on an
    OpenAI-dialect server, against the browser's 8s). A runner busy loading a
    model answers late, and that is the runner's state, not the poll's to wait
    for: with an answer already known, the poll gives the refresh a short
    budget, then serves what it last knew and lets the refresh finish."""
    import threading
    import time

    from tessellate.ai.ollama_client import OllamaClient
    from tessellate.api import routes_models
    from tessellate.core import deps

    ollama = OllamaClient("http://127.0.0.1:9")
    monkeypatch.setattr(deps, "get_ollama", lambda: ollama)
    monkeypatch.setattr(routes_models, "INSTALLED_REFRESH_BUDGET", 0.3)
    release = threading.Event()
    calls: list[int] = []
    answers = [{"name": "model-a", "size": 1}]

    def list_models():
        calls.append(1)
        if len(calls) > 1:
            release.wait(30)
        return list(answers)

    monkeypatch.setattr(ollama, "list_models", list_models)
    first = client.get("/models/status").json()
    assert [m["name"] for m in first["installed_models"]] == ["model-a"]  # nothing known yet: it waits
    answers[:] = [{"name": "model-b", "size": 1}]
    started = time.monotonic()
    slow = client.get("/models/status").json()
    assert time.monotonic() - started < 5  # the refresh is blocked for 30s
    assert not release.is_set()
    assert slow["ollama_running"] is True
    assert [m["name"] for m in slow["installed_models"]] == ["model-a"]  # what it last knew
    # A third poll while the refresh is still out does not start another.
    client.get("/models/status")
    assert len(calls) == 2
    release.set()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        body = client.get("/models/status").json()
        if [m["name"] for m in body["installed_models"]] == ["model-b"]:
            break
        time.sleep(0.05)
    else:
        raise AssertionError("the refresh never landed")


def test_status_reports_a_runner_that_goes_away_when_it_answers(client, monkeypatch):
    """The budget only ever hides lateness: a runner that refuses the
    connection is reported as down on that same poll."""
    from tessellate.ai.ollama_client import OllamaClient, OllamaError
    from tessellate.core import deps

    ollama = OllamaClient("http://127.0.0.1:9")
    monkeypatch.setattr(deps, "get_ollama", lambda: ollama)
    state = {"up": True}

    def list_models():
        if not state["up"]:
            raise OllamaError("refused")
        return [{"name": "model-a", "size": 1}]

    monkeypatch.setattr(ollama, "list_models", list_models)
    assert client.get("/models/status").json()["ollama_running"] is True
    state["up"] = False
    body = client.get("/models/status").json()
    assert body["ollama_running"] is False and body["installed_models"] == []


def test_a_start_up_choice_is_said_with_its_reason_until_one_is_picked(client, monkeypatch):
    """The owner, 2026-10-07: a fresh install with models present said Atlas
    "was running llama3.2, which is not installed any more". Never chosen
    reads as never chosen; a start-up choice carries its why until a model
    is picked by hand."""
    from tessellate.api import app as app_module
    from tessellate.core import deps

    ollama = deps.get_ollama()
    monkeypatch.setattr(ollama, "is_running", lambda: True)
    monkeypatch.setattr(ollama, "list_models", lambda: [{"name": "granite4.1:3b", "size": 2 * 1024**3}])
    #: A fresh install: nothing stored, so the default name stands in.
    deps.get_config()._preferences.pop("chat_model", None)
    body = client.get("/models/status").json()
    assert body["chat_model_chosen"] is False and body["chat_model_chosen_why"] == ""
    app_module._choose_chat_model_if_missing()
    body = client.get("/models/status").json()
    assert body["chat_model"] == "granite4.1:3b" and body["chat_model_chosen"] is True
    assert "llama3.2 is not installed" in body["chat_model_chosen_why"]
    assert client.post("/models/chat-model", json={"name": "granite4.1:3b"}).status_code == 200
    assert client.get("/models/status").json()["chat_model_chosen_why"] == ""
    js = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "status.js").read_text(encoding="utf-8")
    assert "sayChatModelChosen(modelStatus);" in js and '"Change"' in js.split("function sayChatModelChosen", 1)[1][:900]


def test_suggested_shares_the_status_polls_model_list(client, monkeypatch):
    """INBOX 1415: `/models/suggested` took 4.1s in the owner's lag log. It
    asked the runner for its model list inline, unbudgeted, while the status
    poll already keeps that answer: with one known, the shortlist serves it
    and leaves the refresh to finish on its own thread."""
    import threading
    import time

    from tessellate.ai.ollama_client import OllamaClient
    from tessellate.api import routes_models
    from tessellate.core import deps

    ollama = OllamaClient("http://127.0.0.1:9")
    monkeypatch.setattr(deps, "get_ollama", lambda: ollama)
    monkeypatch.setattr(routes_models, "INSTALLED_REFRESH_BUDGET", 0.3)
    monkeypatch.setattr(routes_models, "_loaded_names", set)
    release = threading.Event()
    calls: list[int] = []
    name = next(iter(routes_models.SUGGESTED_MODELS.values()))[0]["name"]

    def list_models():
        calls.append(1)
        if len(calls) > 1:
            release.wait(30)
        return [{"name": name, "size": 3 * 1024**3}]

    monkeypatch.setattr(ollama, "list_models", list_models)
    client.get("/models/suggested")  # nothing known yet: it waits, as the poll does
    started = time.monotonic()
    body = client.get("/models/suggested").json()
    assert time.monotonic() - started < 5  # the refresh is blocked for 30s
    release.set()
    entry = next(m for models in body.values() for m in models if m["name"] == name)
    assert entry["size_source"] == "measured"
