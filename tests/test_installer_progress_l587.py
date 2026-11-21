"""Installer progress for optional package downloads, and the filing model's
warm-up when its download ends (LEDGER L587; Windows splash part in BACKLOG).

A pinned download knows its bytes, so its bar is a real fraction that runs 0
to 1 over every file of the install (`extra_downloads._fetch`, `InstallState`)
and reaches `/extras` and `/tasks`; pip knows nothing, so its bar stays the
moving one. Every download here is a fake stream; no test reaches the network.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from tessellate.ai import model_manager
from tessellate.core import extra_downloads, extras

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"


@pytest.fixture(autouse=True)
def _clean_extras():
    extras.reset_for_tests()
    yield
    extras.reset_for_tests()


class _Stream:
    """A body handed out in fixed pieces, like a socket."""

    def __init__(self, payload: bytes, piece: int) -> None:
        self.payload, self.piece, self.at = payload, piece, 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, _n):
        chunk = self.payload[self.at : self.at + self.piece]
        self.at += self.piece
        return chunk


def _download(payload: bytes) -> extra_downloads.Download:
    return extra_downloads.Download(
        url="https://example.invalid/core.bin",
        sha256=hashlib.sha256(payload).hexdigest(),
        size=len(payload),
        unpack="file",
        members=(("", "core.bin"),),
    )


def test_a_download_reports_the_fraction_it_has_fetched(monkeypatch, tmp_path):
    payload = b"x" * 1000
    seen: list[float] = []
    state = extras.InstallState()

    class _Watch(_Stream):
        def read(self, n):
            if self.at:
                seen.append(state.fraction)
            return super().read(n)

    clock = iter(range(1000, 100000, 1))  # every chunk is more than 0.25 s after the last
    monkeypatch.setattr(extra_downloads.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(extra_downloads, "_open_url", lambda url: _Watch(payload, 250))
    extra_downloads._fetch(_download(payload), tmp_path / "part", state, "Core")
    assert seen[:3] == [0.25, 0.5, 0.75]
    assert 0 <= min(seen) and max(seen) <= 1
    assert state.step.startswith("Downloading Core:")


def test_the_fraction_runs_over_every_file_not_back_to_zero(monkeypatch, tmp_path):
    payload = b"y" * 400
    state = extras.InstallState()
    clock = iter(range(1000, 100000, 1))
    monkeypatch.setattr(extra_downloads.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(extra_downloads, "_open_url", lambda url: _Stream(payload, 200))
    extra_downloads._fetch(_download(payload), tmp_path / "second", state, "Core (2 of 2)", (1, 2))
    assert state.fraction == pytest.approx(1.0)
    extra_downloads._fetch(_download(payload), tmp_path / "first", state, "Core (1 of 2)", (0, 2))
    assert state.fraction == pytest.approx(0.5)


def test_claiming_an_install_clears_the_last_fraction():
    extras._state.fraction = 0.9
    with extras._lock:
        extras._claim(extras.EXTRAS[0], "starting")
    assert extras._state.fraction is None


def test_extras_and_tasks_carry_the_fraction(client):
    extras._state.running = True
    extras._state.extra_id = "pyodide"
    extras._state.step = "Downloading Pyodide: 1.0 of 4.0 MB"
    extras._state.fraction = 0.25
    body = client.get("/extras").json()
    assert body["fraction"] == 0.25
    assert next(e for e in body["extras"] if e["id"] == "pyodide")["fraction"] == 0.25
    assert next(e for e in body["extras"] if e["id"] != "pyodide")["fraction"] is None
    rows = [r for r in client.get("/tasks").json()["tasks"] if r["kind"] == "extra"]
    assert rows and rows[0]["progress"] == 0.25
    extras._state.running = False
    assert client.get("/extras").json()["fraction"] is None


def test_a_bulk_row_adds_the_package_in_hands_fraction():
    from tessellate.api import routes_tasks

    pip = extras.InstallState(running=True, fraction=0.5)
    assert routes_tasks._bulk_progress({"total": 4, "done": 1}, pip) == pytest.approx(0.375)
    assert routes_tasks._bulk_progress({"total": 0, "done": 0}, pip) is None
    assert routes_tasks._bulk_progress({"total": 2, "done": 1}, extras.InstallState(running=True)) == 0.5


def test_the_rows_and_the_notice_draw_the_fraction():
    rows = (JS / "settings-packages.js").read_text(encoding="utf-8")
    assert "const { step, fraction, ...rest } = extra;" in rows, "a changing fraction must not redraw the row"
    assert re.search(r"packagesSetBar\(kept\.querySelector\(\"\.extras-install-progress-bar\"\), extra\.fraction\)", rows)
    assert "packagesSetBar(bar, extra.fraction);" in rows
    notice = (JS / "extra-notice.js").read_text(encoding="utf-8")
    assert "Installing, ${Math.round(body.fraction * 100)}%" in notice
    assert "extraNoticeWaitIdle((body)" in notice
    assert "the install carries on and Activity shows it" in notice


# --- the filing model is warmed when its download ends ------------------------


def test_the_same_model_under_its_bare_and_latest_names():
    assert model_manager.same_model_name("llama3.2", "llama3.2:latest")
    assert model_manager.same_model_name("llama3.2:latest", "llama3.2")
    assert not model_manager.same_model_name("llama3.2", "qwen3:4b")
    assert not model_manager.same_model_name("", "")


class _Ollama:
    def pull(self, name):
        yield {"status": "pulling", "total": 100, "completed": 50}
        yield {"status": "success", "total": 100, "completed": 100}


def test_a_finished_pull_calls_the_after_pull_hooks(monkeypatch):
    called: list[str] = []
    monkeypatch.setattr(model_manager, "AFTER_PULL", [called.append, lambda n: 1 / 0])
    monkeypatch.setattr(model_manager, "_check_room", lambda client, wanted: None)
    job = model_manager.Job(kind="pull", name="llama3.2")
    model_manager._run_pull(_Ollama(), "llama3.2", job)
    assert called == ["llama3.2"]
    assert job.status == "success", "a failing hook must not turn a finished download into an error"


def test_a_pull_of_the_filing_model_queues_the_warm_up_and_another_does_not(monkeypatch, app_state):
    from tessellate.api import routes_models
    from tessellate.core import deps

    queued: list[tuple] = []
    monkeypatch.setattr(routes_models.bgpool, "enqueue", lambda *a, **k: queued.append((a[0], k)) or True)
    manager = deps.get_model_manager()
    monkeypatch.setattr(manager, "utility_model", lambda: "llama3.2")
    routes_models._warm_after_pull("llama3.2:latest")
    routes_models._warm_after_pull("qwen3:4b")
    assert queued == [("warm-filing", {"dedupe_key": "warm-filing"})]
    assert routes_models._warm_after_pull in model_manager.AFTER_PULL
