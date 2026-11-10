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
    monkeypatch.setitem(launcher._LOCALHOST_VERDICT, 8795, True)  # no real server to probe
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


# --- every opener uses the window host; localhost falls back to the bind address ---


def _loopback(monkeypatch, addrs, probe_ok=True):
    import socket

    launcher._LOCALHOST_VERDICT.clear()
    monkeypatch.delenv("TESSELLATE_LOCAL_NAME", raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", (a_, 0)) for a_ in addrs])

    import http.client

    class _Conn:
        def __init__(self, *a, **k):
            pass

        def request(self, *a, **k):
            if not probe_ok:
                raise OSError("refused")

        def getresponse(self):
            return type("R", (), {"status": 200})()

        def close(self):
            pass

    monkeypatch.setattr(http.client, "HTTPConnection", _Conn)


def test_window_host_is_localhost_when_it_is_loopback_and_answers(monkeypatch):
    _loopback(monkeypatch, ["127.0.0.1", "::1"])
    assert launcher.window_host(8796) == "localhost"


def test_fallback_when_localhost_resolves_off_loopback(monkeypatch):
    _loopback(monkeypatch, ["10.1.2.3"])
    assert launcher.window_host(8797) == "127.0.0.1"
    assert launcher._window_url(8797) == "http://127.0.0.1:8797"


def test_fallback_when_the_probe_fails(monkeypatch):
    _loopback(monkeypatch, ["127.0.0.1"], probe_ok=False)
    assert launcher.window_host(8798) == "127.0.0.1"


def test_every_opener_uses_the_window_host(monkeypatch):
    src = (ROOT / "src" / "tessellate" / "__main__.py").read_text(encoding="utf-8")
    assert "page_host" not in src
    _loopback(monkeypatch, ["127.0.0.1"])
    opened = []
    import webbrowser

    monkeypatch.setattr(webbrowser, "open", lambda u, **k: opened.append(u))
    monkeypatch.setattr(launcher, "_existing_instance", lambda: ("live", type("R", (), {"port": 8799})()))
    assert launcher._capture() == 0
    assert opened == ["http://localhost:8799/capture.html"]


def test_an_empty_second_put_keeps_the_held_set(client, _clock):
    """Review 5850946759: the bridge opened twice (a reload) sent an empty put that wiped the first."""
    local = _local(client)
    local.post("/origin-handoff/put", json={"items": {"theme": "dark"}})
    kept = local.post("/origin-handoff/put", json={"items": {}})
    assert kept.json() == {"ok": True, "count": 0, "kept": 1}
    assert local.post("/origin-handoff/take").json() == {"items": {"theme": "dark"}}
    # Once the held set is past its window, an empty put replaces it as before.
    local.post("/origin-handoff/put", json={"items": {"zoom": "110"}})
    _clock["t"] += 10_000
    local.post("/origin-handoff/put", json={"items": {}})
    _clock["t"] += 1
    assert local.post("/origin-handoff/take").json() == {"items": {}}
