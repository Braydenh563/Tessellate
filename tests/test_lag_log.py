"""The lag log (core/lagwatch.py, api/routes_lag.py, frontend/js/lag-watch.js).

The owner, 2026-10-26: a lag spike is logged with its cause and time, kept on
disk so it can be handed over after a restart.
"""

from __future__ import annotations

import json
from pathlib import Path

from tessellate.core import lagwatch

ROOT = Path(__file__).resolve().parents[1]


def test_reports_are_kept_on_disk_and_read_back(client, app_state):
    event = {"kind": "frame", "ms": 812.4, "view": "documents", "cause": "documents.js docRender", "at": "2026-10-26T05:00:00Z"}
    posted = client.post("/logs/lag", json={"events": [event]})
    assert posted.status_code == 201
    path = lagwatch.log_path(Path(app_state.data_dir) / "logs")
    assert json.loads(path.read_text().splitlines()[0])["cause"] == "documents.js docRender"
    kept = client.get("/logs/lag").json()
    assert kept[-1]["ms"] == 812.4
    cleared = client.delete("/logs/lag").json()
    assert cleared == {"cleared": True}
    after = client.get("/logs/lag").json()
    assert after == []


def test_a_report_is_one_line_and_bounded(tmp_path):
    lagwatch.append(tmp_path, [{"cause": "a\nforged line" + "x" * 2000, "k" * 99: 1}])
    lines = lagwatch.log_path(tmp_path).read_text().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert "\n" not in row["cause"] and len(row["cause"]) <= 400
    assert all(len(key) <= 40 for key in row)


def test_the_file_rolls_rather_than_grows(tmp_path, monkeypatch):
    monkeypatch.setattr(lagwatch, "MAX_BYTES", 300)
    for _ in range(10):
        lagwatch.append(tmp_path, [{"cause": "y" * 80}])
    assert lagwatch.log_path(tmp_path).stat().st_size <= 300
    assert (tmp_path / "lag.log.1").exists()


def test_a_batch_is_capped(client):
    too_many = client.post("/logs/lag", json={"events": [{}] * 21})
    assert too_many.status_code == 422


def test_the_watcher_is_lazy_and_preloaded():
    app = (ROOT / "frontend/js/app.js").read_text()
    assert '"dragEdge"' in app.split("forEach(ensureModule), 3000")[0].rsplit("setTimeout", 1)[-1]
    assert 'lazyScript("/js/lag-watch.js")' in (ROOT / "frontend/js/drag-edge.js").read_text()
    index = (ROOT / "frontend/index.html").read_text()
    assert "lag-watch.js" not in index
