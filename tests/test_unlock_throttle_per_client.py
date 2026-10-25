"""The unlock throttle is per client, with a global backstop (§12, S2).

One global list meant five wrong tries from anyone locked the owner out for
up to five minutes: harmless on localhost, where every request is the owner,
and a denial of service the day another device can reach the port. Now each
client address earns its own waits, and the old global list stays as a
second layer with a far larger allowance, so many addresses guessing at once
still slow down together.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from tessellate.api import routes_auth


@pytest.fixture()
def app(client):
    return client.app


def _from(app, address: str) -> TestClient:
    return TestClient(app, client=(address, 50000))


@pytest.fixture(autouse=True)
def _clear():
    routes_auth._active_tokens.clear()
    routes_auth._failed_unlocks.clear()
    routes_auth._failed_by_client.clear()
    yield
    routes_auth._active_tokens.clear()
    routes_auth._failed_unlocks.clear()
    routes_auth._failed_by_client.clear()


def _setup(app):
    assert _from(app, "127.0.0.1").post("/auth/setup", json={"password": "the owner"}).status_code == 200


def test_one_clients_wrong_guesses_do_not_lock_out_another(app):
    _setup(app)
    guesser = _from(app, "192.168.1.50")
    for _ in range(routes_auth._FAILURE_ALLOWANCE + 1):
        guesser.post("/auth/unlock", json={"password": "wrong guess"})
    # The same remedy as the test below, for the same reason: six misses earn
    # a two-second wait, and on a loaded CI runner (Python 3.11, 2026-10-06)
    # the bcrypt checks between them outlasted it, so the guesser's correct
    # password got a 200. More entries in the same bucket keep the test about
    # the property, not about how fast this machine hashes.
    routes_auth._failed_by_client["192.168.1.50"].extend([time.time()] * 5)
    assert guesser.post("/auth/unlock", json={"password": "the owner"}).status_code == 429
    owner = _from(app, "127.0.0.1")
    assert owner.post("/auth/unlock", json={"password": "the owner"}).status_code == 200


def test_the_guesser_is_still_throttled_after_the_owner_unlocks(app):
    _setup(app)
    guesser = _from(app, "192.168.1.50")
    for _ in range(routes_auth._FAILURE_ALLOWANCE + 1):
        guesser.post("/auth/unlock", json={"password": "wrong guess"})
    # Six real misses earn a two-second wait, and the owner's bcrypt unlock
    # between them took longer than that once on a loaded four-worker run, so
    # the wait expired and the test read the clock instead of the property.
    # A longer earned wait (the same list, more entries) keeps it about the
    # property: the owner's unlock leaves the guesser's own bucket alone.
    routes_auth._failed_by_client["192.168.1.50"].extend([time.time()] * 5)
    _from(app, "127.0.0.1").post("/auth/unlock", json={"password": "the owner"})
    assert guesser.post("/auth/unlock", json={"password": "wrong again"}).status_code == 429


def test_many_addresses_guessing_together_hit_the_global_ceiling(app, monkeypatch):
    """Per-address buckets are what a botnet has plenty of, which is the
    reason the old code gave for having one bucket. So the one bucket stays,
    as the backstop, with a larger allowance."""
    monkeypatch.setattr(routes_auth, "_GLOBAL_FAILURE_ALLOWANCE", 12)
    _setup(app)
    codes = []
    for n in range(20):
        codes.append(_from(app, f"10.0.0.{n}").post("/auth/unlock", json={"password": "wrong"}).status_code)
    assert 429 in codes
    assert all(code == 401 for code in codes[:12])


def test_the_client_table_stays_bounded(app, monkeypatch):
    monkeypatch.setattr(routes_auth, "_MAX_TRACKED_CLIENTS", 5)
    monkeypatch.setattr(routes_auth, "_GLOBAL_FAILURE_ALLOWANCE", 1000)
    _setup(app)
    for n in range(12):
        _from(app, f"10.0.1.{n}").post("/auth/unlock", json={"password": "wrong"})
    assert len(routes_auth._failed_by_client) <= 5


def test_addresses_in_one_ipv6_64_share_one_bucket(app):
    """lansec-1025: a device on the Wi-Fi picks any address in the network's
    /64 for itself (privacy addresses do exactly that), so keyed by the full
    address a guesser earned five free tries per address. An IPv6 client is
    keyed by its /64, and an IPv4 address in IPv6 clothing by the IPv4 one."""
    _setup(app)
    for n in range(routes_auth._FAILURE_ALLOWANCE + 1):
        _from(app, f"2001:db8:1:2::{n + 1:x}").post("/auth/unlock", json={"password": "wrong guess"})
    assert list(routes_auth._failed_by_client) == ["2001:db8:1:2::/64"]
    routes_auth._failed_by_client["2001:db8:1:2::/64"].extend([time.time()] * 5)
    fresh = _from(app, "2001:db8:1:2:aaaa:bbbb:cccc:dddd")
    assert fresh.post("/auth/unlock", json={"password": "the owner"}).status_code == 429
    # Another network's /64 is another client: not throttled (a new device
    # is then held for this computer's Allow, a 403 of its own).
    assert _from(app, "2001:db8:9:9::1").post("/auth/unlock", json={"password": "the owner"}).status_code != 429
    assert "2001:db8:9:9::/64" not in routes_auth._failed_by_client


def test_a_mapped_ipv4_client_is_its_ipv4_address():
    assert routes_auth._bucket("::ffff:192.168.1.50") == "192.168.1.50"
    assert routes_auth._bucket("192.168.1.50") == "192.168.1.50"
    assert routes_auth._bucket("fe80::1%eth0") == "fe80::/64"
    assert routes_auth._bucket("testclient") == "testclient"
