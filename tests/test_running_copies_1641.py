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
from tessellate.core import run_records
from tessellate.core import running_copies as rc

NOW = 1_000_000.0


@pytest.fixture()
def run_dir(tmp_path, monkeypatch):
    folder = tmp_path / "run"
    monkeypatch.setenv("TESSELLATE_RUN_DIR", str(folder))
    return folder


def _record(run_dir, pid, port, *, started=NOW - 500, data_dir="/d", token="t" * 12):
    run_records.register(run_records.Record(pid=pid, port=port, token=token, started=started, data_dir=data_dir))


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
        started_fn=lambda pid: None,
    )
    assert [c.pid for c in copies] == [333]
    assert sorted(p.name for p in run_dir.glob("*.json")) == ["333.json"]


def test_a_copy_still_booting_is_kept_and_this_copy_is_marked(run_dir):
    _record(run_dir, 555, 8806, started=NOW - 5)
    _record(run_dir, 556, 8807)
    copies = rc.list_copies(
        own_pid=556, now=NOW, answers_fn=lambda port: port == 8807, alive_fn=lambda pid: True,
        started_fn=lambda pid: None,
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
        identity_fn=lambda port: "", alive_fn=lambda pid: True, started_fn=lambda pid: None, now=NOW,
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
    live = {"identity_fn": lambda port: "", "alive_fn": lambda pid: True, "started_fn": lambda pid: None, "now": NOW}
    assert rc.shutdown(1010, own_pid=1, ask_fn=lambda *a: False, **live) == "failed"
    assert not hasattr(rc, "terminate") and not hasattr(rc, "verify_is_this_app")


def test_a_damaged_record_reads_as_none(run_dir):
    # Review of 1641: `int(1e999)` raised OverflowError and broke the listing.
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "77.json").write_text('{"pid": 77, "port": 1e999, "token": "t", "started": 1}', encoding="utf-8")
    assert run_records.read(run_dir / "77.json") is None


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


# --- Only copies that really run are listed (the owner, 2026-11-11: about 25 dead
# "other copies" on port 8000, and Shut down on one answered 502) ---------------

OLD = NOW - 500


def _serving(by_port):
    """`identity_fn`: the instance id each port serves, "" for an older build
    that answers without one, None for a port nobody answers on."""
    return lambda port: by_port.get(port)


def _list(run_dir, *, serving, alive=(), began=None, own_pid=1):
    return rc.list_copies(
        own_pid=own_pid,
        now=NOW,
        identity_fn=_serving(serving),
        alive_fn=lambda pid: pid in alive,
        started_fn=lambda pid: (began or {}).get(pid),
    )


def test_dead_entries_on_the_port_the_current_copy_holds_are_pruned(run_dir):
    for pid in range(100, 125):
        _record(run_dir, pid, 8000, started=NOW - 86_400 - pid, token=f"dead-token-{pid}")
    _record(run_dir, 999, 8000, started=OLD, token="the-live-token")
    copies = _list(run_dir, serving={8000: il.instance_id("the-live-token")}, alive={999} | set(range(100, 125)), began={999: OLD - 2})
    assert [c.pid for c in copies] == [999]
    assert [f.name for f in run_dir.glob("*.json")] == ["999.json"]


def test_a_reused_pid_is_not_a_running_copy(run_dir):
    # Windows hands a dead copy's pid to another program: alive, but it began after the record was written.
    _record(run_dir, 4000, 8001, started=OLD)
    copies = _list(run_dir, serving={}, alive={4000}, began={4000: NOW - 10})
    assert copies == [] and list(run_dir.glob("*.json")) == []


def test_a_live_process_that_began_when_the_record_says_stays_even_if_it_is_silent(run_dir):
    _record(run_dir, 4001, 8002, started=OLD)
    copies = _list(run_dir, serving={}, alive={4001}, began={4001: OLD - 3})
    assert [c.pid for c in copies] == [4001]


def test_a_port_held_by_a_different_instance_makes_the_record_stale(run_dir):
    _record(run_dir, 4002, 8003, started=OLD, token="mine-was-this")
    copies = _list(run_dir, serving={8003: il.instance_id("someone-else")}, alive={4002}, began={4002: OLD - 1})
    assert copies == []


def test_an_older_build_with_no_instance_id_is_kept_only_while_its_process_matches(run_dir):
    _record(run_dir, 4003, 8004, started=OLD)
    _record(run_dir, 4004, 8004, started=OLD - 9_000)
    copies = _list(run_dir, serving={8004: ""}, alive={4003, 4004}, began={4003: OLD - 1, 4004: NOW - 5})
    assert [c.pid for c in copies] == [4003]


def test_two_older_records_on_one_port_keep_only_the_newest(run_dir):
    _record(run_dir, 4005, 8005, started=OLD - 100)
    _record(run_dir, 4006, 8005, started=OLD)
    copies = _list(run_dir, serving={8005: ""}, alive={4005, 4006}, began={4005: OLD - 101, 4006: OLD - 1})
    assert [c.pid for c in copies] == [4006]


def test_this_copy_is_always_listed(run_dir):
    _record(run_dir, 4007, 8006, started=OLD)
    copies = _list(run_dir, serving={}, alive=(), own_pid=4007)
    assert [c.pid for c in copies] == [4007] and copies[0].this_copy


def test_shut_down_on_a_dead_entry_removes_it_and_is_not_an_error(run_dir):
    _record(run_dir, 4008, 8000, started=OLD, token="dead")
    asked = []
    result = rc.shutdown(
        4008, own_pid=1, ask_fn=lambda *a: asked.append(a) or True,
        identity_fn=_serving({8000: il.instance_id("the-holder")}), alive_fn=lambda pid: True,
        started_fn=lambda pid: NOW - 5, now=NOW,
    )
    assert result == "gone" and asked == [] and list(run_dir.glob("*.json")) == []


def test_a_live_copy_that_does_not_answer_keeps_the_honest_failure(run_dir):
    _record(run_dir, 4009, 8007, started=OLD, token="hung")
    result = rc.shutdown(
        4009, own_pid=1, ask_fn=lambda *a: False,
        identity_fn=_serving({}), alive_fn=lambda pid: True, started_fn=lambda pid: OLD - 1, now=NOW,
    )
    assert result == "failed" and [f.name for f in run_dir.glob("*.json")] == ["4009.json"]


def test_a_start_up_prunes_the_dead_records(run_dir, tmp_path, monkeypatch):
    _record(run_dir, 4010, 8008, started=OLD)
    monkeypatch.setattr(il, "served_instance", lambda *a, **k: None)
    monkeypatch.setattr(il, "pid_alive", lambda pid: pid == os.getpid())
    il.claim(tmp_path / "data", 8009)
    try:
        rc.prune_now()
        assert [f.name for f in run_dir.glob("*.json")] == [f"{os.getpid()}.json"]
    finally:
        il.release()


def test_health_names_the_instance_without_the_token(client, tmp_path):
    info = il.claim(tmp_path / "data", 8015)
    try:
        body = client.get("/health").json()
        assert body["instance"] == il.instance_id(info.token)
        assert info.token not in json.dumps(body)
    finally:
        il.release()


def test_the_shutdown_route_says_a_stopped_copy_is_removed_not_a_502(client, run_dir, monkeypatch):
    monkeypatch.setattr(rc, "shutdown", lambda pid: "gone")
    r = client.post("/running-copies/4011/shutdown")
    assert r.status_code == 200
    assert r.json() == {"stopping": False, "removed": True, "message": "That copy had already stopped; removed it from the list."}
