"""Source text: a review switched on runs after a note is filed (INBOX 691, L392).

Measured in the browser (2026-11-12, port 8790): with "Tags that look alike"
switched on, three saves tagged garden-plot, Garden plot and Garden plots
filed ("done" in about 0.5s) and the review still found its set afterwards,
with no run in Tidy's history. Every earlier test called `run_automatic`
itself with `force=True`; this one goes through the save.
"""

from __future__ import annotations

import threading

from tessellate.core import deps, jobs
from tessellate.entry import tidy


def test_a_save_runs_the_switched_on_review(client, session):
    tidy.set_auto(deps.get_config(), "lookalike-tags", True)
    tidy._auto_clock["last"] = 0.0
    client.post("/entries", json={"content": "Watered the tomatoes.", "tags": ["garden-plot"]})
    jobs.join_threads()
    tidy._auto_clock["last"] = 0.0
    client.post("/entries", json={"content": "Planted beans by the fence.", "tags": ["Garden plot"]})
    jobs.join_threads()
    reviews = {r["key"]: r for r in client.get("/tidy").json()["reviews"]}
    assert reviews["lookalike-tags"]["count"] == 0
    runs = client.get("/tidy/history").json()["runs"]
    assert runs and runs[0]["automatic"] is True


def test_the_review_runs_off_the_request_in_its_own_session(client, monkeypatch):
    """Source text: review 5899359161 (1): `_finish_new_entry` ran Tidy inline
    on the request's session, so a failing review rolled back that session and
    the save waited on every switched-on review."""
    seen = []

    def boom(session, force=False):  # noqa: ANN001, ARG001
        seen.append((threading.current_thread().name, session))
        session.rollback()
        raise RuntimeError("tidy fell over")

    monkeypatch.setattr(tidy, "run_automatic", boom)
    made = client.post("/entries", json={"content": "Pruned the roses.", "tags": ["garden"]})
    jobs.join_threads()
    assert made.status_code in (200, 201)
    assert seen and seen[0][0] == "tidy"
    entry = client.get(f"/entries/{made.json()['id']}").json()
    assert entry["content"] == "Pruned the roses." and "garden" in entry["tags"]
