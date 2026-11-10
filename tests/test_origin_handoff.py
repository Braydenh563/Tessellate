"""The desktop window opens localhost, and the old 127.0.0.1 origin's saved
settings cross once (owner, HANDOVER "Hello origin", 2026-11-10).

Real WebView2 / Windows is unverified here; the bridge page's logic is read
from its source and the server side is exercised for real.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tessellate import __main__ as launcher
from tessellate.api import routes_origin_handoff as handoff

ROOT = Path(__file__).resolve().parents[1]
LOCAL = "http://127.0.0.1:8795"


@pytest.fixture(autouse=True)
def _clock(monkeypatch):
    now = {"t": 1000.0}
    monkeypatch.setattr(handoff, "_now", lambda: now["t"])
    handoff._held.clear()
    yield now
    handoff._held.clear()


def _local(client):
    return TestClient(client.app, base_url=LOCAL, client=("127.0.0.1", 50000))


# --- the window ---------------------------------------------------------------


def test_window_host_is_localhost_and_bind_stays_loopback(monkeypatch):
    monkeypatch.delenv("TESSELLATE_LOCAL_NAME", raising=False)
    assert launcher.window_host() == "localhost"
    assert launcher.HOST == "127.0.0.1"
    src = (ROOT / "src" / "tessellate" / "__main__.py").read_text(encoding="utf-8")
    assert not re.search(r'host\s*=\s*["\']0\.0\.0\.0', src)


def test_first_open_goes_through_the_bridge_then_straight_to_localhost(monkeypatch, tmp_path):
    monkeypatch.setenv("TESSELLATE_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("TESSELLATE_LOCAL_NAME", raising=False)
    assert launcher._window_url(8795) == "http://127.0.0.1:8795/origin-bridge.html?to=localhost"
    assert launcher._window_url(8795) == "http://localhost:8795"
    assert launcher._window_url(8795) == "http://localhost:8795"


# --- the server side ----------------------------------------------------------


def test_put_then_take_once(client):
    local = _local(client)
    assert local.post("/origin-handoff/put", json={"items": {"theme": "dark", "zoom": "110"}}).json()["count"] == 2
    assert local.post("/origin-handoff/take", headers={"Host": "localhost:8795"}).json() == {
        "items": {"theme": "dark", "zoom": "110"}
    }
    assert local.post("/origin-handoff/take").json() == {"items": {}}


def test_the_token_is_never_carried(client):
    local = _local(client)
    local.post("/origin-handoff/put", json={"items": {"token": "secret", "theme": "dark"}})
    assert local.post("/origin-handoff/take").json() == {"items": {"theme": "dark"}}


def test_it_expires(client, _clock):
    local = _local(client)
    local.post("/origin-handoff/put", json={"items": {"a": "b"}})
    _clock["t"] += handoff.TTL_SECONDS + 1
    assert local.post("/origin-handoff/take").json() == {"items": {}}


def test_it_is_bounded(client):
    local = _local(client)
    assert local.post("/origin-handoff/put", json={"items": {"k": "x" * (handoff.MAX_VALUE_CHARS + 1)}}).status_code == 413
    assert local.post("/origin-handoff/put", json={"items": {"k" * 200: "v"}}).status_code == 413
    many = {f"k{i}": "v" for i in range(handoff.MAX_KEYS + 1)}
    assert local.post("/origin-handoff/put", json={"items": many}).status_code == 413
    big = {f"k{i}": "x" * 200_000 for i in range(6)}
    assert local.post("/origin-handoff/put", json={"items": big}).status_code == 413


def test_other_devices_and_tunnels_are_refused(client):
    lan = TestClient(client.app, base_url="http://192.168.1.10:8795", client=("192.168.1.20", 50000))
    tunnel = TestClient(client.app, base_url=LOCAL, client=("127.0.0.1", 50000), headers={"X-Forwarded-For": "8.8.8.8"})
    for other in (lan, tunnel):
        assert other.post("/origin-handoff/put", json={"items": {"a": "b"}}).status_code == 403
        assert other.post("/origin-handoff/take").status_code == 403
    assert handoff._held == {}


def test_a_stranger_cannot_take_what_this_computer_put(client):
    _local(client).post("/origin-handoff/put", json={"items": {"a": "b"}})
    lan = TestClient(client.app, base_url="http://192.168.1.10:8795", client=("192.168.1.20", 50000))
    assert lan.post("/origin-handoff/take").status_code == 403
    assert _local(client).post("/origin-handoff/take").json() == {"items": {"a": "b"}}


# --- the page -----------------------------------------------------------------


def test_the_bridge_pulls_once_and_never_overwrites():
    js = (ROOT / "frontend" / "js" / "origin-bridge.js").read_text(encoding="utf-8")
    assert js.count("/origin-handoff/take") == 1
    assert 'localStorage.getItem(MARK)' in js and 'localStorage.setItem(MARK, "1")' in js
    assert "localStorage.getItem(key) === null" in js  # an existing value on the new origin wins
    assert r"(localhost|[a-z0-9-]{1,63}\.localhost)" in js  # the redirect target is loopback only


def test_the_bridge_page_is_served_and_not_part_of_the_boot_page(client):
    page = client.get("/origin-bridge.html")
    assert page.status_code == 200 and "/js/origin-bridge.js" in page.text
    assert "origin-bridge" not in (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
