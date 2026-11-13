"""Source text: a review switched on runs after a note is filed (INBOX 691, L392).

Measured in the browser (2026-11-12, port 8790): with "Tags that look alike"
switched on, three saves tagged garden-plot, Garden plot and Garden plots
filed ("done" in about 0.5s) and the review still found its set afterwards,
with no run in Tidy's history. Every earlier test called `run_automatic`
itself with `force=True`; this one goes through the save.
"""

from __future__ import annotations

from tessellate.core import deps
from tessellate.entry import tidy


def test_a_save_runs_the_switched_on_review(client, session):
    tidy.set_auto(deps.get_config(), "lookalike-tags", True)
    tidy._auto_clock["last"] = 0.0
    client.post("/entries", json={"content": "Watered the tomatoes.", "tags": ["garden-plot"]})
    tidy._auto_clock["last"] = 0.0
    client.post("/entries", json={"content": "Planted beans by the fence.", "tags": ["Garden plot"]})
    reviews = {r["key"]: r for r in client.get("/tidy").json()["reviews"]}
    assert reviews["lookalike-tags"]["count"] == 0
    runs = client.get("/tidy/history").json()["runs"]
    assert runs and runs[0]["automatic"] is True
