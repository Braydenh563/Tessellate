"""A deferred note always settles, even when the app closed mid-filing.

Owner, 0.3.31: "even if the filing already happened it still looks like it is
endlessly filing". The filing job lives in this process's queue, so a note
saved just before the app closed came back "pending" with nothing behind it.
`GET /entries/{id}/filing` now re-queues such a note, and a job for a note
that has already settled does nothing.
"""

import time

import pytest

from tessellate.api import routes_entries
from tessellate.core import jobs
from tessellate.core.database import Entry


def _wait_settled(client, entry_id, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = client.get(f"/entries/{entry_id}/filing").json()["filing_state"]
        if state != "pending":
            return state
        time.sleep(0.05)
    return "pending"


def test_a_deferred_note_settles(client):
    created = client.post("/entries", json={"content": "buy milk and eggs", "defer_filing": True}).json()
    assert created["filing_state"] == "pending"
    assert _wait_settled(client, created["id"]) != "pending"


def test_a_note_orphaned_by_a_closed_app_is_filed_when_asked(client, session, monkeypatch):
    # The first job is dropped, as a closed app drops it.
    monkeypatch.setattr(routes_entries, "_queue_filing", lambda entry: None)
    created = client.post("/entries", json={"content": "call the dentist", "defer_filing": True}).json()
    monkeypatch.undo()
    entry = session.get(Entry, created["id"])
    session.refresh(entry)
    assert entry.filing_state == "pending"
    assert _wait_settled(client, created["id"]) != "pending"


def test_a_settled_note_is_not_filed_again(client, session, monkeypatch):
    created = client.post("/entries", json={"content": "a settled note", "defer_filing": True}).json()
    assert _wait_settled(client, created["id"]) != "pending"
    calls = []
    monkeypatch.setattr(routes_entries, "_file_entry_now", lambda *a, **k: calls.append(a))
    routes_entries._file_entry_in_background(created["id"], "default")
    assert calls == []


def test_filing_jobs_are_deduplicated_per_note(monkeypatch):
    keys = []
    monkeypatch.setattr(jobs, "enqueue", lambda *a, **k: keys.append(k.get("dedupe_key")))

    class _E:
        id = 7
        workspace_id = "default"

    routes_entries._queue_filing(_E())
    assert keys == [("file-entry", 7)]


def test_a_slow_model_does_not_hold_filing_past_the_deadline(monkeypatch):
    from tessellate.ai import janitor

    class _Slow:
        def chat(self, model, messages, mode=None):
            time.sleep(5)
            return {"content": '{"category": "Late"}'}

    started = time.time()
    with pytest.raises(TimeoutError):
        janitor._chat_within_deadline(_Slow(), "m", [], deadline=0.3)
    assert time.time() - started < 2


def test_filing_asks_the_model_in_quick_mode():
    from tessellate.ai import janitor

    seen = {}

    class _Fake:
        def chat(self, model, messages, mode=None):
            seen["mode"] = mode
            return {"content": "{}"}

    janitor._chat_within_deadline(_Fake(), "m", [])
    assert seen["mode"] == "quick"


def _category_of(client, entry_id):
    return client.get(f"/entries/{entry_id}/filing").json()["category"]


def test_the_models_late_answer_replaces_the_stand_in(client):
    created = client.post("/entries", json={"content": "late one", "category": "Stand in"}).json()
    client.put(f"/entries/{created['id']}", json={"content": "late one"})
    late = routes_entries._LateFiling(created["id"], "default")
    # user_filed is set for a chosen category, so clear it: the stand-in is the AI's.
    from tessellate.core import deps

    with deps.get_db().session() as s:
        row = s.get(Entry, created["id"])
        row.user_filed = False
        row.filing_state = "standin"  # as a note whose model missed the wait
        s.commit()
    assert late.stand_in("Stand in", 40, "semantic-match") == ("Stand in", 40, "semantic-match")
    late.arrived("Recipes", 90)
    assert _category_of(client, created["id"]) == "Recipes"


def test_a_note_moved_by_hand_keeps_its_place(client):
    created = client.post("/entries", json={"content": "moved one", "category": "Mine"}).json()
    from tessellate.core import deps

    with deps.get_db().session() as s:
        s.get(Entry, created["id"]).user_filed = False
        s.commit()
    late = routes_entries._LateFiling(created["id"], "default")
    late.stand_in("Something else", 40, "semantic-match")
    late.arrived("Recipes", 90)
    assert _category_of(client, created["id"]) == "Mine"


def test_an_answer_before_the_stand_in_is_used_instead(app_state):
    late = routes_entries._LateFiling(1, "default")
    late.arrived("Recipes", 90)
    assert late.stand_in("Stand in", 40, "semantic-match") == ("Recipes", 90, "llm")


def test_a_late_reply_reaches_the_callback():
    import threading

    from tessellate.ai import janitor

    got = threading.Event()

    class _Slow:
        def chat(self, model, messages, mode=None):
            time.sleep(0.5)
            return {"content": '{"category": "Late", "confidence": 70}'}

    seen = []
    with pytest.raises(TimeoutError):
        janitor._chat_within_deadline(
            _Slow(), "m", [], deadline=0.1,
            on_late=lambda reply: (seen.append(reply), got.set()),
        )
    assert got.wait(3) and "Late" in seen[0]["content"]


def test_the_wait_is_a_clamped_preference(monkeypatch):
    from tessellate.ai import janitor
    from tessellate.core import deps

    class _Cfg:
        def __init__(self, v):
            self.v = v

        def get_preference(self, key, default=None):
            return self.v if key == "filing_wait_seconds" else default

    for value, expected in ((None, 15.0), (30, 30.0), (1, 5.0), (500, 60.0)):
        monkeypatch.setattr(deps, "get_config", lambda v=value: _Cfg(v))
        assert janitor.filing_deadline() == expected


def _pending_note(client, monkeypatch, content):
    monkeypatch.setattr(routes_entries, "_queue_filing", lambda entry: None)
    created = client.post("/entries", json={"content": content, "defer_filing": True}).json()
    monkeypatch.undo()
    return created


def test_stopping_leaves_a_note_where_it_is_and_no_late_answer_moves_it(client, session, monkeypatch):
    # Queue nothing, so the note stays pending until it is stopped.
    monkeypatch.setattr(routes_entries, "_queue_filing", lambda entry: None)
    created = client.post("/entries", json={"content": "stop me", "defer_filing": True}).json()
    stopped = client.post(f"/entries/{created['id']}/filing/stop", json={"action": "keep"}).json()
    assert stopped["stopped"] is True
    status = client.get(f"/entries/{created['id']}/filing").json()
    assert status["filing_state"] == "stopped"
    late = routes_entries._LateFiling(created["id"], "default")
    late.stand_in(status["category"], 0, "none")
    late.arrived("Somewhere else", 90)
    assert _category_of(client, created["id"]) == status["category"]


def test_stop_rejects_an_unknown_action(client):
    created = client.post("/entries", json={"content": "x", "category": "A"}).json()
    assert client.post(f"/entries/{created['id']}/filing/stop", json={"action": "nope"}).status_code == 422


def test_the_background_tasks_stop_files_every_pending_note(client, monkeypatch):
    from tessellate.core import bgtasks

    monkeypatch.setattr(routes_entries, "_queue_filing", lambda entry: None)
    ids = [
        client.post("/entries", json={"content": f"note {i}", "defer_filing": True}).json()["id"]
        for i in range(2)
    ]
    answer = client.post("/tasks/cancel", json={"kind": "job-file-entry"}).json()
    assert answer["stopped"], answer
    assert "job-file-entry" not in bgtasks.CANCELLERS  # never stopped at shutdown
    for entry_id in ids:
        assert client.get(f"/entries/{entry_id}/filing").json()["filing_state"] == "stopped"


def test_a_filing_says_who_decided_in_the_notes_history(client, monkeypatch):
    from tessellate.ai import janitor

    monkeypatch.setattr(janitor, "categorise", lambda *a, **k: ("Recipes", 88, "llm"))
    created = client.post("/entries", json={"content": "pasta bake", "defer_filing": True}).json()
    assert _wait_settled(client, created["id"]) != "pending"
    filed = [i for i in client.get(f"/entries/{created['id']}/history").json()["items"] if i["action"] == "filed"]
    assert filed and "by " in filed[0]["detail"] and "88% sure" in filed[0]["detail"]


def test_a_stopped_note_stays_open_to_re_evaluation(client, monkeypatch):
    monkeypatch.setattr(routes_entries, "_queue_filing", lambda entry: None)
    created = client.post("/entries", json={"content": "not now", "defer_filing": True}).json()
    client.post(f"/entries/{created['id']}/filing/stop", json={"action": "keep"})
    from tessellate.core import deps

    with deps.get_db().session() as s:
        assert s.get(Entry, created["id"]).user_filed is False


def test_a_cold_embedding_model_does_not_hold_the_stand_in(monkeypatch, app_state):
    from tessellate.ai import janitor

    class _Late:
        def waiting(self):
            self.w = True

        def arrived(self, *a):
            pass

    class _Emb:
        def is_ready(self):
            return False

    monkeypatch.setattr(janitor, "_ask_llm", lambda *a, **k: (janitor.UNCATEGORISED, 0, "timeout"))
    monkeypatch.setattr(janitor, "_semantic_category", lambda *a, **k: (_ for _ in ()).throw(AssertionError("loaded")))
    result = janitor.categorise(None, "x", _Emb(), None, None, on_late_llm=_Late())
    assert result == (janitor.UNCATEGORISED, 0, "none")


def test_an_ai_change_names_its_model():
    from tessellate.ai import tools

    assert tools._ai_actor("add_tags", "granite4.1:3b") == "ai:add_tags@granite4.1:3b"
    assert tools._ai_actor("add_tags", None) == "ai:add_tags"
    assert len(tools._ai_actor("x", "m" * 100)) == 60


def test_a_new_notebook_files_its_first_note_without_loading_the_embedding_model(session):
    """Nothing filed by meaning means nothing to compare against, so the note
    is never embedded on the way to Uncategorised: that embed was the model's
    cold load on a first launch (E2E first-run, 2026-10-06)."""
    from tessellate.ai import janitor

    class _ColdEmb:
        def embed_text(self, text):
            raise AssertionError("embedded with nothing to compare against")

        def backend_id(self):
            raise AssertionError("read the matrix with nothing filed")

    emb = _ColdEmb()
    assert janitor._semantic_category(session, "the spare key is under the blue pot", emb) is None
    assert janitor._best_centroid_match(session, "the spare key", emb) is None
    assert janitor._knn_match(session, "the spare key", emb) is None


def test_a_model_that_stalled_is_not_waited_for_again_note_after_note():
    """INBOX 1312: twenty notes against a model that never answers each waited
    its own 15 s in turn (about 300 s). After one miss the next ones file by
    meaning at once."""
    from tessellate.ai import janitor

    calls = []

    class _Hung:
        def chat(self, model, messages, mode=None):
            calls.append(1)
            time.sleep(1.5)
            return {"content": "{}"}

    hung = _Hung()
    with pytest.raises(TimeoutError):
        janitor._chat_within_deadline(hung, "m", [], deadline=0.1)
    started = time.time()
    for _ in range(5):
        with pytest.raises(janitor.ModelStalled):
            janitor._chat_within_deadline(hung, "m", [], deadline=0.1)
    assert time.time() - started < 0.5 and len(calls) == 1
    #: A caller that chose to wait for the model (Tidy, the warm-up) still does.
    assert issubclass(janitor.ModelStalled, TimeoutError)


def test_a_late_answer_shows_the_model_is_alive_and_ends_the_skipping():
    from tessellate.ai import janitor

    class _Slowish:
        def chat(self, model, messages, mode=None):
            time.sleep(0.3)
            return {"content": "{}"}

    model = _Slowish()
    with pytest.raises(TimeoutError):
        janitor._chat_within_deadline(model, "m", [], deadline=0.05)
    with pytest.raises(janitor.ModelStalled):
        janitor._chat_within_deadline(model, "m", [], deadline=0.05)
    time.sleep(0.6)  # the first call's answer has arrived
    assert janitor._chat_within_deadline(model, "m", [], deadline=2) == {"content": "{}"}


def test_a_caller_that_waits_for_the_model_is_never_skipped():
    from tessellate.ai import janitor

    class _Once:
        n = 0

        def chat(self, model, messages, mode=None):
            _Once.n += 1
            if _Once.n == 1:
                time.sleep(0.4)
            return {"content": "{}"}

    model = _Once()
    with pytest.raises(TimeoutError):
        janitor._chat_within_deadline(model, "m", [], deadline=0.05)
    assert janitor._chat_within_deadline(model, "m", [], deadline=janitor.BLOCKING_MODEL_DEADLINE_SECONDS) == {"content": "{}"}


def test_only_a_few_inline_notes_wait_on_the_model_at_once(monkeypatch):
    """INBOX 1313: twenty inline creates against a model that never answers
    each held a database connection through its wait and filled the pool."""
    import threading

    from tessellate.ai import janitor

    monkeypatch.setattr(janitor, "_model_slots", threading.BoundedSemaphore(2))
    asked = []
    release = threading.Event()

    class _Hung:
        def chat(self, model, messages, mode=None):
            asked.append(1)
            release.wait(5)
            return {"content": "{}"}

    results = []

    def one():
        try:
            janitor._chat_within_deadline(_Hung(), "m", [], deadline=1.0)
        except janitor.ModelStalled:
            results.append("skipped")
        except TimeoutError:
            results.append("waited")

    threads = [threading.Thread(target=one) for _ in range(6)]
    for t in threads:
        t.start()
    time.sleep(0.4)
    assert results.count("skipped") == 4 and len(asked) == 2
    release.set()
    for t in threads:
        t.join(5)


def test_a_client_that_cannot_be_weakly_referenced_is_simply_never_skipped():
    from tessellate.ai import janitor

    class _Slotted:
        __slots__ = ()

        def chat(self, model, messages, mode=None):
            return {"content": "{}"}

    assert janitor._chat_within_deadline(_Slotted(), "m", [], deadline=1.0) == {"content": "{}"}


def test_a_note_filed_inline_waits_for_the_model_no_longer_than_the_wait(client, monkeypatch):
    """INBOX 1313: an inline create (MCP, a script, an importer, the agent) held
    its database connection for the model's whole answer, three minutes by
    default; it now has the same bounded wait as the background pass."""
    seen = []
    real = routes_entries._file_entry_now

    def spy(session, content, on_late_llm=None, model_deadline=None):
        seen.append(model_deadline)
        return real(session, content, on_late_llm=on_late_llm, model_deadline=model_deadline)

    monkeypatch.setattr(routes_entries, "_file_entry_now", spy)
    made = client.post("/entries", json={"content": "an inline note, no defer_filing"})
    assert made.status_code == 201
    from tessellate.ai import janitor

    assert seen == [janitor.filing_deadline()]
    assert janitor.filing_deadline() < janitor.BLOCKING_MODEL_DEADLINE_SECONDS
