"""L-world-class-240: a router whose ARP entry is being re-resolved reads as
no network for a moment (`/proc/net/arp` flags 0x0). The gate took that for
an unknown network, closed the LAN port and dropped every open connection
(CI: an SSL EOF on a phone's second request). This computer still holding the
address it had on the allowed network means it is the same network: the gate
keeps the last reading. A changed address still closes it."""
from __future__ import annotations

import pytest

from tessellate.core import lantrust, netid

NET = netid.Network("192.168.1.1", "aa:bb:cc:dd:ee:ff", "192.168.1.0/24", address="192.168.1.20")


@pytest.fixture
def allowed(tmp_path, monkeypatch):
    monkeypatch.setattr(lantrust, "_gate", dict(lantrust._gate))
    monkeypatch.setattr(lantrust, "_run", dict(lantrust._run))
    lantrust.refresh(tmp_path, NET, online=True)
    state = lantrust.load(tmp_path)
    lantrust._remember(state, NET)
    lantrust.save(tmp_path, state)
    lantrust.refresh(tmp_path, NET, online=True)
    assert lantrust.is_open()
    monkeypatch.setattr(netid, "read", lambda: None)
    return tmp_path


def test_a_router_mid_arp_keeps_the_gate_open_while_the_address_is_the_same(allowed, monkeypatch):
    monkeypatch.setattr(lantrust, "addresses_probe", lambda: ["192.168.1.20", "fe80::1"])
    lantrust.refresh(allowed)
    assert lantrust.is_open()
    assert lantrust.current_network() == NET


def test_a_changed_address_with_no_reading_closes_it(allowed, monkeypatch):
    monkeypatch.setattr(lantrust, "addresses_probe", lambda: ["10.0.0.7"])
    lantrust.refresh(allowed)
    assert not lantrust.is_open()


def test_an_explicit_no_network_is_not_held(allowed, monkeypatch):
    monkeypatch.setattr(lantrust, "addresses_probe", lambda: ["192.168.1.20"])
    lantrust.refresh(allowed, None, online=True)
    assert not lantrust.is_open()
