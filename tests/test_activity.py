"""The Activity panel's backend (WORLD_CLASS_PLAN 28.1 rule 5, decision 70):
one list of what is running, one Stop, and "Stop the model"."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tessellate.ai import model_manager
from tessellate.core import activity, jobruns
from tests._repo_files import repo_files

SRC = Path(__file__).resolve().parents[1] / "src" / "tessellate"


@pytest.fixture(autouse=True)
def _clean():
    activity.clear()
    model_manager.reset_jobs()
    yield
    activity.clear()
    model_manager.reset_jobs()


def test_a_tracked_job_is_listed_and_stop_reaches_it():
    with activity.track("generation", "Answering in Chat") as job:
        rows = activity.snapshot()
        assert [r["kind"] for r in rows] == ["generation"]
        assert rows[0]["stoppable"] is True
        stopped, _ = activity.stop(job.id)
        assert stopped and job.stopped
    assert activity.snapshot() == []


def test_a_job_that_cannot_stop_says_so():
    with activity.track("ocr", "Reading", stoppable=False) as job:
        stopped, detail = activity.stop(job.id)
    assert not stopped and "finish" in detail


def test_a_tracked_stream_ends_on_stop_and_closes_its_source():
    closed = []

    def source():
        try:
            for i in range(1000):
                yield f"line {i}\n"
        finally:
            closed.append(True)

    out = []
    for line in activity.tracked_stream("generation", "Drafting", source()):
        out.append(line)
        if len(out) == 3:
            activity.stop(activity.snapshot()[0]["id"])
    assert len(out) == 3 and closed == [True]
    assert activity.snapshot() == []


def test_activity_lists_a_reindex_a_booked_run_and_a_generation(client, monkeypatch):
    monkeypatch.setattr(
        model_manager,
        "reindex_status",
        lambda: {"kind": "reindex", "name": "", "total": 40, "done": 10, "status": "running"},
    )
    run = jobruns.begin("import")
    job = activity.start("generation", "Answering in Chat", stoppable=True)
    try:
        body = client.get("/activity").json()
    finally:
        run.finish()
        activity.finish(job)
    ids = {row["id"]: row for row in body["jobs"]}
    assert ids["task:reindex:"]["progress"] == 0.25 and ids["task:reindex:"]["stoppable"]
    assert ids["run:import"]["label"]
    assert ids[job.id]["kind"] == "generation"
    assert set(body["model"]) == {"model", "loaded", "stoppable"}


def test_stop_by_id_reaches_the_reindex_canceller(client, monkeypatch):
    asked = []
    monkeypatch.setattr(model_manager, "cancel_reindex", lambda: asked.append(1) or True)
    body = client.post("/activity/task:reindex:/stop").json()
    assert body["stopped"] and asked == [1]


def test_stop_by_id_reaches_a_generation(client):
    job = activity.start("generation", "Answering in Chat", stoppable=True)
    try:
        body = client.post(f"/activity/{job.id}/stop").json()
    finally:
        activity.finish(job)
    assert body["stopped"] and job.stopped


def test_a_finished_job_is_an_answer_not_an_error(client):
    gone = client.post("/activity/job-999/stop").json()
    empty = client.post("/activity/task::/stop").json()
    assert gone["stopped"] is False and empty["stopped"] is False


def test_stop_the_model_asks_ollama_to_unload_it(monkeypatch):
    from tessellate.ai import ollama_client

    sent = {}

    class Response:
        def raise_for_status(self):
            return None

    def post(url, json=None, timeout=None):  # noqa: A002
        sent["url"], sent["json"] = url, json
        return Response()

    monkeypatch.setattr(ollama_client.requests, "post", post)
    acted, detail = ollama_client.OllamaClient("http://127.0.0.1:11434").unload("llama3")
    assert acted and sent["json"] == {"model": "llama3", "keep_alive": 0}
    assert sent["url"].endswith("/api/generate") and "llama3" in detail


def test_stop_the_model_stops_every_generation_first(client):
    job = activity.start("generation", "Answering in Chat", stoppable=True)
    try:
        body = client.post("/activity/model/stop").json()
    finally:
        activity.finish(job)
    assert job.stopped and body["detail"]


#: Every `threading.Thread(` in the app, and how its work reaches Activity.
#: A new long-running thread fails here until it registers (rule 5's lint):
#: either in `routes_tasks.collect()` under a kind, or through
#: `core/activity.py` or `jobruns.job_run`. Infrastructure that is not a job
#: (the server, the tray icon, a heartbeat) says so.
THREAD_SITES = {
    "ai/embeddings.py": "collect: embeddings, embedding-model",
    "ai/janitor.py": "collect: filing kinds",
    "ai/autonomous.py": "collect: autonomous",
    "search/searxng_manager.py": "infrastructure: the SearXNG output pump",
    "search/searxng_install.py": "collect: searxng",
    "api/routes_update.py": "collect: app-update",
    "api/app.py": "jobruns: backup",
    "__main__.py": "infrastructure: the server and the tray icon",
    "core/jobs.py": "collect: job- kinds (the pool) and its heartbeat",
    "core/embedmodels.py": "collect: embedding-model",
    "core/security.py": "infrastructure: a DNS probe of two seconds",
    "core/lanserve.py": "infrastructure: the one select thread that waits for a LAN connection first byte",
    "ai/backend_hint.py": "infrastructure: one status probe of a backend, waited for at most 0.15 s by a decorating route",
    "core/background.py": "the registry: running() lists, stop_all() at quit; callers reach Activity (transcription: activity.start, warm-up: collect embeddings)",
}


def test_every_thread_site_is_registered_with_activity():
    found = set()
    for path in repo_files(SRC, suffixes=(".py",)):
        text = path.read_text(encoding="utf-8")
        if re.search(r"threading\.Thread\(", re.sub(r"(?m)^\s*#.*$|`[^`]*`", "", text)):
            found.add(path.relative_to(SRC).as_posix())
    unregistered = sorted(found - set(THREAD_SITES))
    assert not unregistered, (
        f"{unregistered} start a thread nothing lists: register it in routes_tasks.collect(), "
        "core/activity.track or jobruns.job_run, then name it in THREAD_SITES"
    )
    assert not set(THREAD_SITES) - found, "a listed thread site is gone: drop its row"
