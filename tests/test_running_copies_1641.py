"""INBOX 1641: Settings lists the other copies of Tessellate running on this
computer and shuts one down. Records live in a per-user folder
(core/running_copies.py); the shutdown asks the other copy over its own
loopback route with the token only that user can read."""

import json
import os
import stat
import sys

import pytest

from tessellate.core import instance_lock as il
from tessellate.core import running_copies as rc

NOW = 1_000_000.0


@pytest.fixture()
def run_dir(tmp_path, monkeypatch):
    folder = tmp_path / "run"
    monkeypatch.setenv("TESSELLATE_RUN_DIR", str(folder))
    return folder


def _record(run_dir, pid, port, *, started=NOW - 500, data_dir="/d", token="t" * 12):
    rc.register(rc.Record(pid=pid, port=port, token=token, started=started, data_dir=data_dir))


def test_a_claim_registers_and_a_release_removes_the_record(run_dir, tmp_path):
    info = il.claim(tmp_path / "data", 8801)
    try:
        files = list(run_dir.glob("*.json"))
        assert [f.name for f in files] == [f"{os.getpid()}.json"]
        body = json.loads(files[0].read_text())
        assert body["port"] == 8801 and body["token"] == info.token
        assert body["data_dir"] == str(tmp_path / "data")
    finally:
        il.release()
    assert list(run_dir.glob("*.json")) == []


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
def test_the_record_and_its_folder_are_private_to_this_user(run_dir):
    _record(run_dir, 4242, 8802)
    assert stat.S_IMODE(run_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE((run_dir / "4242.json").stat().st_mode) == 0o600


def test_a_stale_record_is_pruned_when_listed(run_dir):
    _record(run_dir, 111, 8803)  # pid gone
    _record(run_dir, 222, 8804)  # pid alive, port silent, past the boot grace
    _record(run_dir, 333, 8805)  # live
    copies = rc.list_copies(
        own_pid=1, now=NOW,
        answers_fn=lambda port: port == 8805,
        alive_fn=lambda pid: pid in (222, 333),
    )
    assert [c.pid for c in copies] == [333]
    assert sorted(p.name for p in run_dir.glob("*.json")) == ["333.json"]


def test_a_copy_still_booting_is_kept_and_this_copy_is_marked(run_dir):
    _record(run_dir, 555, 8806, started=NOW - 5)
    _record(run_dir, 556, 8807)
    copies = rc.list_copies(
        own_pid=556, now=NOW, answers_fn=lambda port: port == 8807, alive_fn=lambda pid: True
    )
    by_pid = {c.pid: c for c in copies}
    assert set(by_pid) == {555, 556} and by_pid[556].this_copy and not by_pid[555].this_copy


def test_the_public_view_never_carries_the_token(run_dir):
    _record(run_dir, 777, 8808, token="secret-token-value")
    copies = rc.list_copies(own_pid=1, now=NOW, answers_fn=lambda p: True, alive_fn=lambda p: True)
    assert "secret-token-value" not in json.dumps([c.public() for c in copies])


def test_shutdown_asks_the_other_copy_with_its_token(run_dir):
    _record(run_dir, 888, 8809, token="tok-888")
    asked = []
    result = rc.shutdown(
        888, own_pid=1,
        ask_fn=lambda port, token: asked.append((port, token)) or True,
    )
    assert result == "stopping" and asked == [(8809, "tok-888")]


def test_shutdown_refuses_this_copy_and_unknown_pids(run_dir):
    _record(run_dir, 999, 8810)
    assert rc.shutdown(999, own_pid=999, ask_fn=lambda *a: True) == "this-copy"
    assert rc.shutdown(12345, own_pid=1, ask_fn=lambda *a: True) == "unknown"


def test_a_copy_that_does_not_agree_to_stop_is_never_killed(run_dir):
    # Review of 1641: a recorded pid can be reused by another program while a
    # different copy answers on the port, so Shut down only ever asks.
    _record(run_dir, 1010, 8811)
    assert rc.shutdown(1010, own_pid=1, ask_fn=lambda *a: False) == "failed"
    assert not hasattr(rc, "terminate") and not hasattr(rc, "verify_is_this_app")


def test_a_damaged_record_reads_as_none(run_dir):
    # Review of 1641: `int(1e999)` raised OverflowError and broke the listing.
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "77.json").write_text('{"pid": 77, "port": 1e999, "token": "t", "started": 1}', encoding="utf-8")
    assert rc._read(run_dir / "77.json") is None


def test_a_record_is_ignored_when_junk(run_dir):
    run_dir.mkdir(parents=True)
    (run_dir / "5.json").write_text("{nope")
    (run_dir / "6.json").write_text(json.dumps({"pid": 6, "port": 99999, "token": "x", "started": 1}))
    assert rc.list_copies(own_pid=1, now=NOW, answers_fn=lambda p: True, alive_fn=lambda p: True) == []


def test_the_shutdown_route_needs_the_instance_token(client):
    from tessellate.core import instance_lock

    instance_lock.claim(os.environ["TESSELLATE_DATA_DIR"], 8812)
    try:
        bare = client.post("/instance/shutdown")
        wrong = client.post("/instance/shutdown", headers={"X-Instance-Token": "wrong"})
        assert bare.status_code == 403 and wrong.status_code == 403
    finally:
        instance_lock.release()


def test_the_shutdown_route_stops_with_the_right_token(client, monkeypatch):
    from tessellate.api import routes_tasks
    from tessellate.core import instance_lock

    stopped = []
    monkeypatch.setattr(routes_tasks, "stop_process_soon", lambda: stopped.append(1))
    info = instance_lock.claim(os.environ["TESSELLATE_DATA_DIR"], 8813)
    try:
        r = client.post("/instance/shutdown", headers={"X-Instance-Token": info.token})
        assert r.status_code == 200 and r.json() == {"stopping": True}
        assert stopped == [1]
        # A browser page cannot send the header cross-origin without a preflight
        # this app never answers; and a page-held token does not exist.
    finally:
        instance_lock.release()


def test_settings_routes_list_and_refuse_other_devices(client, run_dir, monkeypatch):
    monkeypatch.setattr(il, "answers", lambda *a, **k: True)
    _record(run_dir, os.getpid(), 8814, started=NOW)
    body = client.get("/running-copies").json()
    assert body["copies"] and all("token" not in c for c in body["copies"])
    unknown = client.post("/running-copies/424242/shutdown")
    own = client.post(f"/running-copies/{os.getpid()}/shutdown")
    assert unknown.status_code == 404 and own.status_code == 409


def test_the_settings_row_and_its_help_exist():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    html = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="running-copies-list"' in html and 'data-help-for="running-copies-help"' in html
    assert chr(0x2014) not in html[html.index('id="running-copies-group"'):][:3000]
