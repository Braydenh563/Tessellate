"""The process ledger (INBOX 805): every AI, composer and background run, with
a plain title, who started it, timed lines, and its ending kept with them.

The owner: "all things that use the ai or composer and all background
processes need to be logged and shown in bg processes ... along with their
individual logs and process lines to show their process live and when they
are finished as well."
"""

from __future__ import annotations

import json

import pytest

from tests._clock import pin_clock
from tessellate.core import activity, jobruns, taskhistory
from tessellate.core import jobs as pool


@pytest.fixture(autouse=True)
def _clean():
    activity.clear()
    jobruns.clear_finished()
    taskhistory.clear()
    yield
    activity.clear()
    jobruns.clear_finished()
    taskhistory.clear()


def test_a_run_carries_its_title_origin_and_timed_lines():
    with jobruns.job_run("duplicate-scan", title="Looking for duplicates", origin="you", persist=False) as run:
        run.say("Read 40 notes.")
        live = next(r for r in jobruns.live() if r["id"] == run.id)
        assert live["title"] == "Looking for duplicates" and live["origin"] == "you"
        assert live["lines"][0]["text"] == "Read 40 notes." and live["lines"][0]["at"] > 0
        assert live["log"] == ["Read 40 notes."]
        run.result = "found 2 pairs"
    done = jobruns.finished()[0]
    assert done["run_id"] == run.id and done["outcome"] == "completed"
    assert done["detail"] == "found 2 pairs" and done["duration_ms"] >= 0
    assert [line["text"] for line in done["lines"]] == ["Read 40 notes."]


def test_a_failed_run_keeps_its_reason_and_lines():
    def export_that_fails():
        with jobruns.job_run("export", persist=False) as run:
            run.say("Wrote 3 notes.")
            raise RuntimeError("disk full")

    #: Raised inside a helper, so the reads after `pytest.raises` are not
    #: "unreachable" to CodeQL, which does not model the context manager.
    with pytest.raises(RuntimeError):
        export_that_fails()
    done = jobruns.finished()[0]
    assert done["outcome"] == "failed" and done["detail"] == "disk full"
    assert done["lines"][0]["text"] == "Wrote 3 notes."


def test_the_ring_and_the_lines_are_bounded():
    for n in range(jobruns.FINISHED_KEEP + 15):
        with jobruns.job_run("export", title=f"Export {n}", persist=False) as run:
            for i in range(jobruns.LOG_LINES + 5):
                run.say(f"line {i}")
    kept = jobruns.finished()
    assert len(kept) == jobruns.FINISHED_KEEP
    assert len(kept[0]["lines"]) == jobruns.LOG_LINES
    assert kept[0]["title"] == f"Export {jobruns.FINISHED_KEEP + 14}"


def test_repeated_small_runs_fold_into_one_row_with_a_count():
    for _ in range(5):
        with jobruns.job_run("embed-entry", title="Updating a note's search vector", persist=False):
            pass
    kept = jobruns.finished()
    assert len(kept) == 1 and kept[0]["count"] == 5


def test_a_run_seen_only_at_its_end_is_not_listed_twice():
    jobruns.note_finished("model-download", "completed", "pulled llama", 1000)
    assert jobruns.finished() == []


def test_started_by_names_who_started_runs_on_this_thread():
    with jobruns.started_by("start-up"), jobruns.job_run("maintenance", persist=False) as run:
        assert run.origin == "start-up"
    with jobruns.job_run("maintenance", persist=False) as run:
        assert run.origin == ""


def test_a_tracked_stream_is_a_run_with_narrated_lines():
    events = [
        {"type": "status", "stage": "searching"},
        {"type": "meta", "raw_results": [{}, {}], "search_mode": "hybrid", "answered_by": "qwen3:4b"},
        {"type": "tool", "tool": "search_notes", "ok": True, "arguments": {"query": "gaming mouse?\\", "limit": 0}},
        {"type": "tool", "tool": "ask_user", "ok": False, "error": "ask_user needs at least 2 different options"},
        {"type": "answer", "delta": "A gaming "},
        {"type": "answer", "delta": "mouse note."},
        {"type": "done"},
    ]
    lines = (json.dumps(e) + "\n" for e in events)
    out = list(activity.tracked_stream("generation", "Answering in Chat", lines, title="Agent: 'gaming mouse'"))
    assert len(out) == len(events)
    done = jobruns.finished()[0]
    assert done["title"] == "Agent: 'gaming mouse'" and done["origin"] == "you"
    said = [line["text"] for line in done["lines"]]
    assert said[0] == "Searching your notes."
    assert said[1] == "Found 2 notes (hybrid). Answering with qwen3:4b."
    assert said[2] == 'Called search_notes: query "gaming mouse?", limit 0.'
    assert said[3] == "ask_user did not run: ask_user needs at least 2 different options."
    assert said[4] == "Writing the answer."
    assert said[5] == "Done: 4 words, 2 tool calls (1 did not run)."
    assert done["detail"] == "4 words, 2 tool calls (1 did not run)"


def test_a_composed_answer_says_no_model_was_used():
    lines = [json.dumps({"type": "meta", "raw_results": [{}], "search_mode": "keyword", "composed": True})]
    list(activity.tracked_stream("generation", "Answering in Chat", iter(lines), title="Answering 'x'"))
    said = jobruns.finished()[0]["lines"][0]["text"]
    assert said == "Found 1 note (keyword). Composing the answer from your notes, no model."


def test_a_tracked_job_that_opens_its_own_run_is_not_doubled():
    with jobruns.job_run("import", title="Importing from Notion", persist=False), activity.track(
        "import", "Importing from Notion", ledger=False
    ):
        pass
    assert len(jobruns.finished()) == 1


def test_a_pool_job_is_a_run_and_a_pass_is_not_wrapped_twice():
    job = pool.Job(1, "file-entry", lambda: None, (), {}, "Shopping list")
    run = job.open_run()
    assert run is not None and run.title == "Filing a note: Shopping list" and run.listed
    run.finish()
    assert pool.Job(2, "pass", lambda: None, (), {}, "Backup").open_run() is None


def test_running_lists_a_chat_answer_with_its_lines(client):
    with activity.track("generation", "Answering in Chat", title="Answering 'what is a mouse'") as job:
        job.run.say("Searching your notes.")
        body = client.get("/tasks").json()
    row = next(t for t in body["tasks"] if t["label"] == "Answering 'what is a mouse'")
    assert row["watched"] is True and row["origin"] == "you"
    assert row["lines"][0]["text"] == "Searching your notes."
    history = client.get("/tasks").json()["history"]
    assert history[0]["label"] == "Answering 'what is a mouse'" and history[0]["lines"]


def test_history_holds_a_run_once_when_it_also_reports_to_taskhistory(client):
    with jobruns.job_run("reindex", title="Re-indexing your notes", persist=False) as run:
        run.say("Indexed 10 of 10.")
    taskhistory.record("reindex", "Search index rebuilt", "completed", "10 notes")
    history = client.get("/tasks").json()["history"]
    rows = [h for h in history if h["kind"] == "reindex"]
    assert len(rows) == 1 and rows[0]["lines"][0]["text"] == "Indexed 10 of 10."


def test_clearing_the_history_clears_the_ledger(client):
    with jobruns.job_run("export", persist=False):
        pass
    client.post("/tasks/history/clear")
    assert jobruns.finished() == []


def test_the_jobs_stream_carries_the_runs(client):
    with jobruns.job_run("export", title="Exporting the notebook", persist=False) as run:
        run.say("Wrote 3 notes.")
        text = client.get("/jobs/stream?seconds=0").text
    assert "event: runs" in text
    payload = json.loads(text.split("event: runs\ndata: ", 1)[1].split("\n", 1)[0])
    mine = next(r for r in payload["running"] if r["id"] == run.id)
    assert mine["lines"][0]["text"] == "Wrote 3 notes."


# --- Every model call, and every way a run ends (INBOX 805 second half, B77) --

from tessellate.ai.provider import Provider  # noqa: E402


class _Model(Provider):
    """A backend whose generation paths are the ledger's wrapped ones."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def chat(self, model, messages, mode=None):  # noqa: ANN001, ANN201
        if self.fail:
            raise RuntimeError("runner down")
        return {"message": {"content": "ok"}}

    def chat_stream(self, model, messages, mode=None):  # noqa: ANN001, ANN201
        yield from ("a", "b", "c")


def _wait_for(predicate, seconds: float = 5.0) -> None:
    import time

    end = time.monotonic() + seconds
    while time.monotonic() < end and not predicate():
        time.sleep(0.01)


def test_a_model_call_no_run_owns_is_a_run_of_its_own():
    _Model().chat("tiny", [])
    done = jobruns.finished()[0]
    assert done["kind"] == "ai-call" and done["outcome"] == "completed" and done["duration_ms"] >= 0
    assert [line["text"] for line in done["lines"]][0] == "Asked tiny."
    assert done["lines"][-1]["text"].startswith("tiny answered in ")
    assert jobruns.live() == []


def test_a_failed_model_call_ends_failed_not_running():
    with pytest.raises(RuntimeError):
        _Model(fail=True).chat("tiny", [])
    done = jobruns.finished()[0]
    assert done["outcome"] == "failed" and done["detail"] == "runner down"
    assert jobruns.live() == []


def test_a_model_call_inside_a_run_adds_its_lines_there():
    with jobruns.job_run("duplicate-scan", persist=False) as run:
        _Model().chat("tiny", [])
        texts = [line["text"] for line in run.lines()]
    assert texts[0] == "Asked tiny." and texts[1].startswith("tiny answered in ")
    assert [row["kind"] for row in jobruns.finished()] == ["duplicate-scan"]


def test_a_stream_the_reader_closes_ends_cancelled():
    stream = _Model().chat_stream("tiny", [])
    assert next(stream) == "a"
    assert [row["kind"] for row in jobruns.live()] == ["ai-call"]
    stream.close()
    done = jobruns.finished()[0]
    assert done["outcome"] == "cancelled" and jobruns.live() == []
    assert list(_Model().chat_stream("tiny", [])) == ["a", "b", "c"]
    assert jobruns.finished()[0]["outcome"] == "completed"


def test_a_model_call_is_named_for_the_request_that_made_it():
    def improve_writing():  # noqa: ANN202
        return None

    with jobruns.for_request({"type": "http", "path": "/entries/3/improve", "endpoint": improve_writing}):
        _Model().chat("tiny", [])
    assert jobruns.finished()[0]["title"] == "Improve writing"
    assert jobruns.finished()[0]["origin"] == "you"


@pytest.mark.parametrize("body", ["raises", "returns early", "cancelled"])
def test_a_filing_run_ends_on_every_way_out(body):
    """B77: "The agent run still says the note is filing but it is finished."
    A filing job whose body raises, returns early or is cancelled ends in the
    ledger, so nothing stays running."""

    class _Cancelled(BaseException):
        pass

    def work() -> None:
        _Model().chat("tiny", [])
        if body == "raises":
            raise ValueError("no category")
        if body == "cancelled":
            raise _Cancelled
        return

    lane = pool.Pool(widths={"model": 1}, kind_lanes={"file-entry": "model"})
    lane.enqueue("file-entry", work, name="Shopping list")
    _wait_for(lambda: bool(jobruns.finished()))
    lane.shutdown(1.0)
    assert jobruns.live() == []
    done = jobruns.finished()[0]
    assert done["title"] == "Filing a note: Shopping list"
    assert done["outcome"] == {"raises": "failed", "cancelled": "cancelled"}.get(body, "completed")
    #: The model call's lines are on the filing run, not a run of their own.
    assert [row["kind"] for row in jobruns.finished()] == ["file-entry"]
    assert done["lines"][0]["text"] == "Asked tiny."


def test_a_late_filing_answer_is_a_run_that_is_given_up_not_left_running():
    from tessellate.ai import janitor

    token = janitor._count_late("tiny", 15)
    row = janitor.activity_rows()[0]
    assert row["label"] == janitor.LATE_TITLE and "filed by meaning" in row["detail"]
    assert "Filing a note" not in row["label"]
    assert [r["kind"] for r in jobruns.live()] == ["filing-late"]
    janitor._give_up_stale_late(now=10**12)
    assert janitor.late_count() == 0 and janitor.activity_rows() == []
    assert jobruns.live() == [] and jobruns.finished()[0]["outcome"] == "cancelled"
    janitor._uncount_late(token, "late")  # the answer after the give-up: no second ending
    assert len(jobruns.finished()) == 1


def test_the_running_tab_lists_finished_runs_with_outcome_and_length(client):
    with jobruns.job_run("duplicate-scan", title="Looking for duplicates", origin="you", persist=False) as run:
        run.say("Read 40 notes.")
    finished = client.get("/activity").json()["finished"]
    row = next(r for r in finished if r["run_id"] == run.id)
    assert row["outcome"] == "completed" and row["duration_ms"] >= 0
    assert row["started"] <= row["finished"] and row["origin"] == "you started it"
    assert row["lines"][0]["text"] == "Read 40 notes."


# --- L669: one history for every run, with what started it and why ---------


def test_a_run_says_why_it_started_in_its_own_words_or_its_origins():
    with jobruns.job_run("export", title="Export", origin="you", why="You pressed Export", persist=False):
        pass
    with jobruns.job_run("resurface", title="Resurfacing", origin="schedule", persist=False):
        pass
    with jobruns.job_run("ocr", title="Reading", origin="event", why="A new image arrived", persist=False):
        pass
    by_title = {row["title"]: row for row in jobruns.finished()}
    assert by_title["Export"]["why"] == "You pressed Export"
    assert by_title["Resurfacing"]["why"] == jobruns.ORIGIN_WHY["schedule"]
    assert by_title["Reading"]["why"] == "A new image arrived"
    assert "event" in jobruns.ORIGINS


def test_started_by_carries_the_why_to_runs_opened_below():
    with jobruns.started_by("event", "A note was saved"):
        with jobruns.job_run("filing", title="Filing", persist=False):
            pass
    row = jobruns.finished()[0]
    assert row["origin"] == "event" and row["why"] == "A note was saved"
    assert jobruns.origin_now() == "" and jobruns.why_now() == ""


def test_history_lists_running_and_finished_runs_newest_first(client):
    with jobruns.job_run("export", title="First", origin="you", persist=False) as run:
        run.result = "wrote 3 notes"
    #: Fixed times, so the order never rides on the real clock.
    jobruns._finished[-1].update(started=1000.0, ended=1002.0)
    with jobruns.job_run("resurface", title="Second", origin="schedule", persist=False):
        rows = client.get("/activity/history").json()["runs"]
        assert rows[0]["title"] == "Second" and rows[0]["outcome"] == "running"
        assert rows[0]["finished"] is None
    rows = client.get("/activity/history").json()["runs"]
    assert [r["title"] for r in rows] == ["Second", "First"]
    first = rows[1]
    assert first["origin"] == jobruns.ORIGINS["you"] and first["result"] == "wrote 3 notes"
    assert first["outcome"] == "completed" and first["why"] and first["duration_ms"] >= 0
    assert first["label"] == "Notebook export" and first["started"] and first["finished"]


def test_history_is_not_cut_to_half_an_hour(client):
    with jobruns.job_run("export", title="Old", origin="you", persist=False):
        pass
    jobruns._finished[-1]["ended"] -= 3 * 3600
    assert client.get("/activity").json()["finished"] == []
    assert [r["title"] for r in client.get("/activity/history").json()["runs"]] == ["Old"]


# --- L-world-class-570: the history survives a restart ----------------------

from datetime import datetime, timedelta  # noqa: E402

from tessellate.core.database import JobRunLog  # noqa: E402
from tessellate.core.database_manager import DatabaseManager  # noqa: E402

_NOW = datetime(2026, 11, 21, 9, 0, 0)


@pytest.fixture
def stored(tmp_path, monkeypatch):
    """A database of its own as the app's, on a fixed clock the test can move."""
    db = DatabaseManager(tmp_path / "log.db")
    clock = {"now": _NOW}
    monkeypatch.setattr(jobruns, "_peek_db", lambda: db)
    pin_clock(monkeypatch, lambda: clock["now"])
    return db, clock


def _run(kind: str, title: str, **kw) -> None:
    with jobruns.job_run(kind, title=title, persist=False, **kw):
        pass


def test_the_history_survives_a_restart(stored):
    with jobruns.started_by("event", "A note was saved"):
        with jobruns.job_run("filing", title="Filing", persist=False) as run:
            run.say("Read the note.")
            run.result = "filed under Garden"
    jobruns._finished.clear()  # a restart: the ring is process memory
    assert jobruns.finished() == []
    [kept] = jobruns.history()
    assert kept["title"] == "Filing" and kept["origin"] == "event" and kept["why"] == "A note was saved"
    assert kept["detail"] == "filed under Garden" and kept["lines"][0]["text"] == "Read the note."


def test_history_route_reads_the_stored_runs(stored, client):
    _run("export", "Old export", origin="you")
    jobruns._finished.clear()
    rows = client.get("/activity/history").json()["runs"]
    assert [r["title"] for r in rows] == ["Old export"] and rows[0]["origin"] == jobruns.ORIGINS["you"]


def test_a_run_in_the_ring_and_the_table_is_listed_once(stored):
    _run("export", "Once", origin="you")
    assert [r["title"] for r in jobruns.history()] == ["Once"]


def test_old_rows_are_pruned_by_the_users_clock(stored):
    _db, clock = stored
    _run("export", "Ancient", origin="you")
    clock["now"] = _NOW + timedelta(days=jobruns.KEEP_DAYS, minutes=1)
    _run("resurface", "Fresh", origin="schedule")
    jobruns._finished.clear()
    assert [r["title"] for r in jobruns.history()] == ["Fresh"]


def test_rows_past_the_cap_are_pruned_newest_kept(stored, monkeypatch):
    db, _clock = stored
    monkeypatch.setattr(jobruns, "KEEP_ROWS", 3)
    for n in range(5):
        _run("export", f"Run {n}", origin="you")
        run_id = jobruns._finished[-1]["run_id"]
        #: Fixed order, never the real clock.
        with db.session() as session:
            session.get(JobRunLog, run_id).ended = 2000.0 + n
            session.commit()
    jobruns._finished.clear()
    assert [r["title"] for r in jobruns.history()] == ["Run 4", "Run 3", "Run 2"]


def test_clear_forgets_the_stored_history_too(stored):
    _run("export", "Gone", origin="you")
    jobruns.clear_finished()
    assert jobruns.history() == []


def test_a_scheduled_run_shows_its_origin_and_why(stored, client):
    with jobruns.started_by("schedule", "The autonomous pass is due every few hours."):
        with jobruns.job_run("night-shift", title="Night shift", persist=False):
            pass
    row = client.get("/activity/history").json()["runs"][0]
    assert row["origin"] == jobruns.ORIGINS["schedule"]
    assert row["why"] == "The autonomous pass is due every few hours."


def test_the_autonomous_scheduler_marks_its_pass_as_scheduled(monkeypatch):
    from tessellate.ai import autonomous

    seen: list[tuple[str, str]] = []
    monkeypatch.setattr(autonomous, "_run_optimization", lambda: seen.append((jobruns.origin_now(), jobruns.why_now())))
    monkeypatch.setattr(autonomous, "_vacuum", lambda: None)
    autonomous._working.set()
    autonomous.run_pass(scheduled=True)
    autonomous._working.set()
    autonomous.run_pass(scheduled=False)
    assert seen[0][0] == "schedule" and seen[0][1]
    assert seen[1][0] == "you" and seen[1][1]


def test_a_route_that_opens_a_run_says_who_started_it() -> None:
    # /resurface/compute opened its run with no origin, so its History row had no why (L-world-class-570 sweep).
    import re
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "src" / "tessellate" / "api"
    bare = [
        f"{p.name}:{n}"
        for p in sorted(src.glob("routes_*.py"))
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if re.search(r"jobruns\.job_run\(\"[^\"]+\"\)", line)
    ]
    assert not bare, bare
