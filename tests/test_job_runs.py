"""Last run of each job: `core/jobruns.py` and `GET /jobs/last-runs` (INBOX 438).

The owner: "there should be timestamps and success status for when various
things were last ran like the search reindexing etc." One row per job kind,
written through one helper from every job's start and end. These tests pin
the helper's contract once, then that each job really records through it,
because a job that never calls the helper shows "Not run yet" for ever and
nothing else notices.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import select

from tessellate.ai import embeddings as embeddings_module
from tessellate.ai import model_manager
from tessellate.core import deps, jobruns, taskhistory
from tessellate.core.database import EmbeddingRecord, JobRun
from tests._app_js import frontend_text
from tests._pool_wait import pool_idle
from tests._repo_files import repo_files

ROOT = Path(__file__).resolve().parents[1]


def _fail(exc: Exception) -> None:
    """Raise from a call rather than inline: CodeQL reads an inline `raise`
    inside `pytest.raises` as making the asserts after it unreachable."""
    raise exc


def _runs(client) -> dict[str, dict]:
    body = client.get("/jobs/last-runs").json()
    return {row["kind"]: row for row in body["jobs"]}


# -- the helper ---------------------------------------------------------------


def test_every_kind_is_listed_even_before_it_has_run(client):
    runs = _runs(client)
    assert set(runs) >= set(jobruns.KINDS)
    never = runs["reindex"]
    assert never["ran"] is False and never["status"] == "never"
    assert never["label"] == "Search index rebuild"


def test_a_clean_block_records_ok_with_its_result_and_duration(client):
    with jobruns.job_run("reindex") as run:
        run.result = "412 notes indexed"
    row = _runs(client)["reindex"]
    assert row["ran"] and row["status"] == "ok"
    assert row["result"] == "412 notes indexed" and row["error"] == ""
    assert row["started_at"] and row["finished_at"]
    assert row["duration_ms"] is not None and row["duration_ms"] >= 0


def test_an_exception_is_recorded_as_a_failure_and_still_raised(client):
    with pytest.raises(RuntimeError, match="disk is full"):
        with jobruns.job_run("backup"):
            _fail(RuntimeError("disk is full"))
    row = _runs(client)["backup"]
    assert row["status"] == "failed"
    assert row["error"] == "disk is full" and row["result"] == ""


def test_a_stop_is_cancelled_not_failed(client):
    with jobruns.job_run("autonomous") as run:
        run.cancel("stopped after 3 of 9")
    row = _runs(client)["autonomous"]
    assert row["status"] == "cancelled" and row["result"] == "stopped after 3 of 9"
    assert row["error"] == ""


def test_the_row_says_running_while_the_block_is_open(client):
    with jobruns.job_run("import"):
        row = _runs(client)["import"]
        assert row["status"] == "running" and row["finished_at"] is None
    assert _runs(client)["import"]["status"] == "ok"


def test_one_row_per_kind_and_the_second_run_replaces_the_first(client, session):
    with jobruns.job_run("backup") as run:
        run.result = "first"
    with jobruns.job_run("backup") as run:
        run.result = "second"
    assert len(list(session.scalars(select(JobRun).where(JobRun.kind == "backup")))) == 1
    assert _runs(client)["backup"]["result"] == "second"


def test_a_skipped_run_puts_the_last_real_one_back(client):
    with jobruns.job_run("night-shift") as run:
        run.result = "read 4 notes, found 2 facts"
    with jobruns.job_run("night-shift") as run:
        run.skip()
    assert _runs(client)["night-shift"]["result"] == "read 4 notes, found 2 facts"
    with jobruns.job_run("resurface") as run:
        run.skip()
    assert _runs(client)["resurface"]["ran"] is False


def test_an_older_run_finishing_does_not_overwrite_a_newer_one_in_flight(client):
    older = jobruns.begin("import")
    with jobruns.job_run("import"):
        older.result = "old"
        older.finish()
        assert _runs(client)["import"]["status"] == "running"


def test_a_long_or_multiline_reason_is_kept_to_one_short_line(client):
    with pytest.raises(ValueError):
        with jobruns.job_run("backup"):
            _fail(ValueError("line one\nline two " + "x" * 900))
    error = _runs(client)["backup"]["error"]
    assert "\n" not in error and len(error) <= 300 and error.endswith("…")


def test_recording_with_no_app_is_a_quiet_no_op(monkeypatch):
    monkeypatch.setattr(jobruns, "_peek_db", lambda: None)
    with jobruns.job_run("backup") as run:
        run.result = "nowhere to write this"
    jobruns.note_finished("extra", "failed", "no database either")


def test_a_broken_database_never_breaks_the_job(client, monkeypatch):
    class Broken:
        def session(self):
            raise RuntimeError("database is locked")

    monkeypatch.setattr(jobruns, "_peek_db", lambda: Broken())
    ran = []
    with jobruns.job_run("backup"):
        ran.append(True)
    assert ran == [True]


def test_a_run_left_running_by_a_closed_app_is_marked_interrupted(client):
    jobruns.begin("reindex")  # the process dies here, never finishing
    assert jobruns.mark_interrupted() == 1
    row = _runs(client)["reindex"]
    assert row["status"] == "failed" and "closed" in row["error"]


# -- each job -----------------------------------------------------------------


class _Embedder:
    def __init__(self, boom: bool = False) -> None:
        self.boom = boom

    def backend_id(self) -> str:
        return "fake:test"

    def store_for_entry(self, session, entry) -> bool:  # noqa: ANN001
        if self.boom:
            raise RuntimeError("the embedding model went away")
        return True


def test_reindex_records_how_many_notes_it_indexed(client):
    for text in ("one", "two", "three"):
        client.post("/entries", json={"content": text})
    model_manager._run_reindex(deps.get_db(), _Embedder(), model_manager.Job(kind="reindex"))
    row = _runs(client)["reindex"]
    assert row["status"] == "ok" and row["result"] == "3 notes indexed"


def test_a_failed_reindex_shows_its_reason(client):
    client.post("/entries", json={"content": "one"})
    model_manager._run_reindex(
        deps.get_db(), _Embedder(boom=True), model_manager.Job(kind="reindex")
    )
    row = _runs(client)["reindex"]
    assert row["status"] == "failed"
    assert row["error"] == "The re-index stopped before it finished. The log has the reason."


def test_a_stopped_reindex_is_cancelled(client):
    client.post("/entries", json={"content": "one"})
    job = model_manager.Job(kind="reindex")
    job.cancel_requested = True
    model_manager._run_reindex(deps.get_db(), _Embedder(), job)
    assert _runs(client)["reindex"]["status"] == "cancelled"


def test_the_reindex_endpoint_records_a_run(ai_client):
    ai_client.post("/entries", json={"content": "a funny scarecrow joke"})
    assert ai_client.post("/models/reindex").status_code in (200, 202)
    import time

    deadline = time.time() + 5
    while time.time() < deadline and _runs(ai_client)["reindex"]["status"] != "ok":
        time.sleep(0.05)
    assert _runs(ai_client)["reindex"]["status"] == "ok"


def test_a_manual_backup_records_the_file_it_wrote(client):
    name = client.post("/backups").json()["name"]
    row = _runs(client)["backup"]
    assert row["status"] == "ok" and name in row["result"]


def test_the_startup_backup_is_a_run_only_when_one_is_taken(client):
    from tessellate.api import app as app_module

    app_module._backup_if_due()  # none exists yet: taken
    first = _runs(client)["backup"]
    assert first["status"] == "ok" and "daily backup" in first["result"]
    app_module._backup_if_due()  # one is fresh: nothing to record
    assert _runs(client)["backup"]["started_at"] == first["started_at"]


def test_a_failed_backup_shows_why(client, monkeypatch):
    from tessellate.core import backup

    def full(*_a, **_k):
        raise OSError(28, "No space left on device", "/home/someone/data/backups/memorymap.db")

    monkeypatch.setattr(backup, "backup_now", full)
    response = client.post("/backups")
    # Said in words for the toast, not the bare "Internal error" a 500 was.
    assert response.status_code == 507
    assert response.json()["detail"] == "Couldn't save the backup: No space left on device."
    row = _runs(client)["backup"]
    assert row["status"] == "failed"
    # A short worded reason: not the errno, and not the path of the person's
    # own folders.
    assert row["error"] == "No space left on device"


def test_the_duplicate_scan_records_its_count_on_the_first_page_only(client):
    client.post("/entries", json={"content": "the quick brown fox jumps over the lazy dog"})
    client.post("/entries", json={"content": "the quick brown fox jumps over the lazy dog again"})
    assert client.get("/duplicates").status_code == 200
    first = _runs(client)["duplicate-scan"]
    assert first["status"] == "ok" and "duplicate" in first["result"]
    client.get("/duplicates?offset=500")
    assert _runs(client)["duplicate-scan"]["started_at"] == first["started_at"]


def test_resurface_compute_records_a_run(client):
    client.post("/entries", json={"content": "something to score"})
    client.post("/resurface/compute")
    row = _runs(client)["resurface"]
    assert row["status"] == "ok" and row["result"].startswith("scored")


def test_the_night_shift_records_its_counts_and_a_paused_runner_records_nothing(
    ai_client, fake_ollama
):
    ai_client.post(
        "/entries",
        json={"content": "The batch size should stay at 32. Who owns the rollback plan?"},
    )
    reply = ai_client.post("/night/run", json={"budget": 2000}).json()
    row = _runs(ai_client)["night-shift"]
    assert row["status"] == "ok"
    assert row["result"].startswith(f"read {reply['scanned']} note")
    deps.get_config().set_preference("learn.night_shift.enabled", False)
    before = row["started_at"]
    assert ai_client.post("/night/run", json={}).json() == {"paused": True}
    assert _runs(ai_client)["night-shift"]["started_at"] == before


def test_a_markdown_upload_records_an_import(client):
    files = [("files", ("a.md", b"# hello\nsome words", "text/markdown"))]
    assert client.post("/import/markdown", files=files).status_code == 201
    row = _runs(client)["import"]
    assert row["status"] == "ok" and row["result"] == "imported 1 note"


def test_a_folder_import_records_an_import(client, tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "vault").mkdir(parents=True)
    (home / "vault" / "n.md").write_text("inside the vault", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    assert client.post("/import/directory", json={"path": str(home / "vault")}).status_code == 202
    pool_idle()
    assert _runs(client)["import"]["result"] == "imported 1 note from a folder"


def test_an_unreadable_document_records_a_failed_import(client, monkeypatch, caplog):
    from tessellate.api import routes_settings

    monkeypatch.setattr(routes_settings.importer, "markitdown_available", lambda: True)

    def boom(_path):
        raise ValueError("corrupt zip")

    monkeypatch.setattr(routes_settings.importer, "convert_to_markdown", boom)
    with caplog.at_level("WARNING", logger="tessellate.import"):
        response = client.post("/import/document", files={"file": ("deck.pptx", b"junk", "application/x")})
    assert response.status_code == 422
    row = _runs(client)["import"]
    #: Background jobs shows the row to a person: a plain sentence, with the
    #: file's name, and none of the converter's own words (final scan item 5).
    assert row["status"] == "failed" and "deck.pptx" in row["error"]
    assert "corrupt zip" not in row["error"] and "ValueError" not in row["error"]
    assert row["error"].startswith("Couldn't read deck.pptx.")
    #: The detail stays in the log, with its traceback.
    records = [r for r in caplog.records if r.name == "tessellate.import"]
    assert records and records[0].exc_info and "corrupt zip" in str(records[0].exc_info[1])


def test_a_job_that_cannot_be_resumed_shows_a_plain_reason_and_logs_the_detail(tmp_path, caplog):
    from tessellate.core import jobstore
    from tessellate.core.database import DatabaseManager, DurableJob

    db = DatabaseManager(tmp_path / "jobs.db")
    kind = next(iter(jobstore.HANDLERS))
    job_id = jobstore.record(kind, (1,), {}, db=db)
    assert job_id is not None
    with db.session() as session:
        session.query(DurableJob).filter(DurableJob.id == job_id).update({"payload": "{not json at all"})
        session.commit()
    with caplog.at_level("WARNING", logger="tessellate.jobstore"):
        counts = jobstore.resume(db=db, enqueue=lambda *call: None)
    jobstore.stop()
    assert counts["resumed"] == 0
    with db.session() as session:
        row = session.get(DurableJob, job_id)
        assert row.state == "failed"
        assert row.error == "Could not be resumed after the app restarted."
    records = [r for r in caplog.records if r.name == "tessellate.jobstore" and "resume job" in r.getMessage()]
    assert records and records[0].exc_info is not None


def test_link_reasons_records_a_run(client):
    assert client.post("/entries/links/backfill-reasons", json={"ai": False}).status_code == 200
    row = _runs(client)["link-reasons"]
    assert row["status"] == "ok" and row["result"].startswith("checked 0 links")


def test_re_evaluating_a_note_records_the_filing_run(ai_client, fake_ollama):
    note = ai_client.post("/entries", json={"content": "buy milk and eggs"}).json()
    assert ai_client.post(f"/entries/{note['id']}/reevaluate").status_code == 200
    row = _runs(ai_client)["filing"]
    assert row["status"] in ("ok", "failed")
    assert row["started_at"]


def test_re_evaluating_with_no_ai_records_why_it_could_not(client):
    note = client.post("/entries", json={"content": "buy milk and eggs"}).json()
    assert client.post(f"/entries/{note['id']}/reevaluate").status_code == 200
    row = _runs(client)["filing"]
    assert row["status"] == "failed" and row["error"]


def test_the_embeddings_backfill_records_what_it_filled(client, session, fake_embeddings):
    client.post("/entries", json={"content": "first note"})
    session.query(EmbeddingRecord).delete()
    session.commit()
    assert embeddings_module.backfill_missing(fake_embeddings, lambda: session) == 1
    row = _runs(client)["embeddings-backfill"]
    assert row["status"] == "ok" and row["result"] == "embedded 1 note that had no vector"


def test_the_embeddings_backfill_is_not_a_run_while_the_model_is_not_ready(client, session):
    from tests.fakes import FakeEmbeddingService

    embeddings_module.backfill_missing(FakeEmbeddingService(available=False), lambda: session)
    assert _runs(client)["embeddings-backfill"]["ran"] is False


def test_the_autonomous_pass_records_a_skip_honestly(client):
    from tessellate.ai import autonomous

    deps.get_config().set_preference("battery_efficient_mode", True)
    autonomous._run_optimization()
    row = _runs(client)["autonomous"]
    assert row["status"] == "ok" and row["result"].startswith("Skipped")


def test_a_failed_autonomous_pass_shows_the_reason(client, monkeypatch):
    from tessellate.ai import agent, autonomous

    def boom(**_kw):
        raise RuntimeError("the model refused to start")

    monkeypatch.setattr(agent, "run_agent", boom)
    config = deps.get_config()
    config.set_preference("auto_tag_enabled", True)
    autonomous._run_optimization()
    row = _runs(client)["autonomous"]
    assert row["status"] == "failed" and row["error"] == "the model refused to start"


@pytest.mark.parametrize(
    ("history_kind", "job_kind"),
    [("pull", "model-download"), ("extra", "extra"), ("searxng", "searxng"),
     ("embedding-model", "embedding-model"), ("vision_ocr", "ocr"), ("caption", "caption")],
)
def test_jobs_that_report_to_the_task_history_also_keep_a_last_run(client, history_kind, job_kind):
    taskhistory.record(history_kind, "Doing the thing", "failed", "the connection dropped")
    row = _runs(client)[job_kind]
    assert row["status"] == "failed" and row["error"] == "the connection dropped"
    taskhistory.record(history_kind, "Doing the thing", "completed", duration_ms=1500)
    row = _runs(client)[job_kind]
    assert row["status"] == "ok" and row["result"] == "Doing the thing"
    assert row["duration_ms"] is not None and row["duration_ms"] >= 1500


def test_the_last_run_survives_the_task_history_being_cleared(client):
    taskhistory.record("extra", "Installing x", "completed", "x installed")
    client.post("/tasks/history/clear")
    assert _runs(client)["extra"]["result"] == "x installed"


# -- the lints the DOM-less suite needs ---------------------------------------


def test_every_last_run_line_in_the_page_names_a_known_kind():

    html = (Path(__file__).resolve().parent.parent / "frontend" / "index.html").read_text(encoding="utf-8")
    lines = set(re.findall(r'data-job-line="([a-z-]+)"', html))
    assert lines, "the page has no last-run lines"
    assert lines <= set(jobruns.KINDS), lines - set(jobruns.KINDS)
    # The js builds the overview and the runtime lines from the same attribute.
    js = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "ai-tools.js").read_text(encoding="utf-8")
    assert set(re.findall(r'jobLineEl\("([a-z-]+)"\)', js)) <= set(jobruns.KINDS)


def test_every_kind_in_the_overview_is_written_by_some_job():
    """A kind nothing writes shows "Not run yet" for ever, which reads as a
    job that never works. Each must be opened by `job_run`/`begin` somewhere
    in `src`, or be a `taskhistory` bridge."""

    src = Path(__file__).resolve().parent.parent / "src" / "tessellate"
    text = "\n".join(p.read_text(encoding="utf-8") for p in repo_files(src, suffixes=(".py",), exclude_names=("jobruns.py",)))
    written = set(re.findall(r'(?:job_run|begin)\("([a-z-]+)"', text))
    written |= set(taskhistory.LAST_RUN_KINDS.values())
    assert set(jobruns.KINDS) <= written, set(jobruns.KINDS) - written


# -- live runs: progress, steps and a log while a job runs (INBOX 1006) -------


def _task_rows(client) -> list[dict]:
    return client.get("/tasks").json()["tasks"]


def test_a_running_job_run_is_listed_with_progress_and_log(client):
    with jobruns.job_run("embeddings-backfill") as run:
        run.step(3, 12, "Embedding notes")
        run.say("Embedded 3 of 12 notes.")
        rows = [r for r in _task_rows(client) if r["label"] == "Embeddings backfill"]
        assert len(rows) == 1
        row = rows[0]
        assert row["progress"] == pytest.approx(0.25)
        assert row["detail"] == "Embedding notes: 3 of 12"
        assert row["log"] == ["Embedded 3 of 12 notes."]
        assert row["started"] > 0
    assert not [r for r in _task_rows(client) if r["label"] == "Embeddings backfill"]


def test_a_failed_run_leaves_the_live_list(client):
    with pytest.raises(RuntimeError):
        with jobruns.job_run("resurface"):
            _fail(RuntimeError("boom"))
    assert not [r for r in _task_rows(client) if r["label"] == "Resurfacing"]


def test_the_log_keeps_the_last_fifty_lines_and_clips_each(client):
    with jobruns.job_run("maintenance") as run:
        for n in range(80):
            run.say(f"line {n}")
        run.say("x" * 900)
        live = next(r for r in jobruns.live() if r["kind"] == "maintenance")
        assert len(live["log"]) == 50
        assert live["log"][0] == "line 31" and len(live["log"][-1]) <= 300


def test_named_steps_show_done_running_and_waiting(client):
    with jobruns.job_run("backup") as run:
        run.plan(["Copy", "Verify", "Prune"])
        run.step(1, 3)
        steps = next(r for r in jobruns.live() if r["kind"] == "backup")["steps"]
        assert [s["outcome"] for s in steps] == ["completed", "running", "queued"]
        assert [s["label"] for s in steps] == ["Copy", "Verify", "Prune"]


def test_a_pass_run_through_the_pool_is_one_row_not_two(client, monkeypatch):
    import threading
    import time

    from tessellate.core import passes

    gate = threading.Event()

    def slow():
        with jobruns.job_run("resurface") as run:
            run.step(1, 2)
            assert gate.wait(10)

    passes.reset_for_tests()
    monkeypatch.setitem(passes.RUNNERS, "resurface", slow)
    try:
        started = client.post("/jobs/passes/resurface/run").json()["started"]
        assert started is True
        deadline = time.monotonic() + 10
        rows = []
        while time.monotonic() < deadline:
            rows = [r for r in _task_rows(client) if r["label"] == "Resurfacing"]
            if rows and rows[0]["progress"] is not None:
                break
            time.sleep(0.02)
        assert len(rows) == 1 and rows[0]["progress"] == pytest.approx(0.5)
        assert rows[0]["cancellable"] is False  # resurfacing has no step to stop at
    finally:
        gate.set()
        passes.reset_for_tests()


def test_a_backup_names_its_three_steps_and_checks_the_copy(client):
    from tessellate.core import backup

    config = deps.get_config()
    with jobruns.job_run("backup") as run:
        backup.backup_now(config.db_path, config.data_dir, 5, run)
        shot = run.snapshot()
    assert [s["label"] for s in shot["steps"]] == ["Copy the database", "Check the copy", "Remove old backups"]
    assert {s["outcome"] for s in shot["steps"]} == {"completed"}
    assert any("Checking the copy" in line for line in shot["log"])


def test_a_backup_that_cannot_be_read_back_fails_and_is_not_kept(tmp_path):
    from tessellate.core import backup

    junk = tmp_path / "memorymap-x.db"
    junk.write_bytes(b"this is not a database" * 50)
    with pytest.raises(OSError):
        backup.verify_copy(junk)


def test_housekeeping_marks_off_its_steps_and_says_what_it_is_doing(client, monkeypatch):
    from tessellate.core import passes

    seen = []
    monkeypatch.setattr(
        passes, "MAINTENANCE_STEPS",
        (lambda: seen.append(next(r for r in jobruns.live() if r["kind"] == "maintenance")), lambda: None),
    )
    passes._maintenance()
    first = seen[0]
    assert [s["outcome"] for s in first["steps"]] == ["running", "queued"]
    assert first["log"] == ["Clear expired notes from the bin."]


def test_the_night_pass_reports_notes_read_of_notes_to_read(client, session):
    from tessellate.ai import facts

    for text in ("I decided to use sqlite.", "Why does the build fail?", "We shipped the beta."):
        client.post("/entries", json={"content": text})
    with jobruns.job_run("night-shift") as run:
        outcome = facts.run(session, budget=5000, force=True)
        session.commit()
        shot = run.snapshot()
    assert outcome["scanned"] >= 3
    assert shot["progress"] is not None
    assert shot["log"][0].endswith("to read.") and any(line.startswith("Read ") for line in shot["log"])
    assert not any("Traceback" in line or "Error" in line for line in shot["log"])


# The jobs poll stops when signed out; a run's log lines carry its run id for the Logs button (owner 2026-10-11, OPEN ledger 1424).

def _fn(text: str, name: str) -> str:
    start = text.index(f"function {name}(")
    return text[start : text.index("\n}\n", start)]


def test_1424_the_jobs_poll_stops_when_signed_out():
    body = _fn(frontend_text("settings.js"), "refreshJobRuns")
    assert "if (!authToken()) {\n    clearTimeout(jobRunsTimer);\n    return;\n  }" in body
    assert "if (running && authToken()) jobRunsTimer = setTimeout(refreshJobRuns, 2000);" in body


def test_a_job_run_writes_its_lines_to_the_app_log_under_its_run_id(caplog):
    """The history row's Logs button filters on "[run-N]" (owner 2026-10-11)."""
    import logging


    with caplog.at_level(logging.INFO, logger="memorymap.jobruns"):
        with jobruns.job_run("reindex", origin="you") as run:
            run.say("Reading notes")
    lines = [r.getMessage() for r in caplog.records]
    assert any(m.startswith(f"[{run.id}] ") and "Reading notes" in m for m in lines), lines
    assert any(m.startswith(f"[{run.id}] ") and "finished" in m for m in lines), lines


def test_the_logs_button_filters_on_the_run_and_an_empty_log_is_the_empty_state():
    js = frontend_text("settings.js")
    assert "`[${item.run_id}]`" in frontend_text("settings-controls.js")
    shared = _fn(js, "renderLogSharedUI")
    assert "This job wrote no log lines" in shared and '"log-none"' in shared
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert re.search(r'id="logs-empty" class="empty-state hidden"', html)


def test_an_interrupted_run_keeps_when_it_started_and_claims_no_finish_time(client):
    """B66 (INBOX 904): "Last run 26 min ago, failed: The app closed before
    this finished" on an app that had not been running all day. The row was
    stamped finished at the moment the next start settled it, so the line read
    the start-up time as the run's time. The run's own start is the only time
    anyone knows; there is no finish."""
    from datetime import datetime, timedelta

    jobruns.begin("reindex")
    long_ago = datetime.utcnow() - timedelta(days=2)
    with deps.get_db().session() as session:
        session.get(JobRun, "reindex").started_at = long_ago
        session.commit()
    assert jobruns.mark_interrupted() == 1
    row = _runs(client)["reindex"]
    assert row["status"] == "failed"
    assert row["finished_at"] is None
    assert row["started_at"].startswith(long_ago.strftime("%Y-%m-%dT%H"))
