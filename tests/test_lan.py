"""LAN mode (Allow other devices on this network): the switch, trust, certificate, serving and the Settings controls."""

from __future__ import annotations

import asyncio
import contextlib
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import ssl
import stat
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

from cryptography import x509
import datetime as dt
from fastapi.testclient import TestClient
import pytest
import uvicorn

from tessellate.api import routes_auth
from tessellate.api.this_computer import REFUSAL
from tessellate.core import egress, lancert, lanlive, lanserve, lantrust, netbind, netid, origin, vault
from tests._app_js import app_js_text


# The Windows firewall line: Settings, Other devices shows the one-line netsh command when the switch is on, for the private profile only.


def test_the_hint_is_one_netsh_line_for_the_private_profile_only():
    hint = netbind.firewall_hint(8443, platform="win32")
    command = hint["command"]
    assert command.startswith("netsh advfirewall firewall add rule ")
    assert "dir=in" in command and "action=allow" in command
    assert "protocol=TCP" in command and "localport=8443" in command
    assert "profile=private" in command and "profile=any" not in command and "public" not in command
    assert "\n" not in command
    assert hint["rule"] in command
    assert hint["remove"] == f'netsh advfirewall firewall delete rule name="{hint["rule"]}"'


def test_there_is_no_hint_off_windows_or_without_a_port():
    assert netbind.firewall_hint(8443, platform="linux") is None
    assert netbind.firewall_hint(8443, platform="darwin") is None
    assert netbind.firewall_hint(None, platform="win32") is None
    assert netbind.firewall_hint(0, platform="win32") is None


def test_describe_carries_the_hint_only_where_it_applies(app_state, monkeypatch):
    monkeypatch.setattr(netbind.sys, "platform", "linux")
    assert netbind.describe(app_state, 8000)["firewall"] is None
    monkeypatch.setattr(netbind.sys, "platform", "win32")
    off = netbind.describe(app_state, 8000)
    assert off["firewall"] is None  # the switch is off: nothing to open
    app_state.set_preference(netbind.LAN_PREF, True)
    on = netbind.describe(app_state, 8000)
    assert str(netbind.lan_port(8000)) in on["firewall"]["command"]


def test_settings_draws_the_line_with_a_copy_button():
    root = Path(__file__).resolve().parents[1]
    html = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    js = (root / "frontend" / "js" / "settings-controls.js").read_text(encoding="utf-8")
    assert 'id="account-lan-firewall"' in html
    assert "state.firewall" in js and "account-lan-firewall" in js


# LAN mode from the status bar, live: applies while the app runs, networks and certificate follow the address, 14 days unused switches it off, a phone never installs software.


PASSWORD = "the owner's password"
HOME = netid.Network("192.168.0.1", "aa:bb:cc:dd:ee:01", "192.168.0.0/24")
CAFE = netid.Network("192.168.0.1", "11:22:33:44:55:66", "192.168.0.0/24")


def _state(**over):
    state = lantrust.load(Path("/nonexistent-lanbar"))  # the closed defaults
    state.update(over)
    return state


# --- which networks open: untrusted and no network --------------------------------


def test_a_network_marked_untrusted_stays_closed_even_with_any_network():
    blocked = _state(any_network=True, untrusted=[{"key": CAFE.key, "blocked": True}])
    assert lantrust.evaluate(blocked, CAFE) == (False, "untrusted_network")
    assert lantrust.evaluate(blocked, HOME) == (True, "any_network")
    # Only listed, never marked: "Allow on any network" still opens it.
    seen = _state(any_network=True, untrusted=[{"key": CAFE.key, "blocked": False}])
    assert lantrust.evaluate(seen, CAFE) == (True, "any_network")


def test_no_network_at_all_is_its_own_closed_state():
    loose = _state(any_network=True)
    assert lantrust.evaluate(loose, None, online=False) == (False, "no_network")
    assert lantrust.evaluate(loose, None, online=True) == (True, "any_network")


def test_a_network_the_port_stayed_closed_on_is_listed_to_trust_later(tmp_path):
    lantrust.reset_for_tests()
    lantrust.save(tmp_path, _state(networks=[{"key": HOME.key, "label": "home"}]))
    assert lantrust.refresh(tmp_path, CAFE)["reason"] == "new_network"
    assert [n["key"] for n in lantrust.load(tmp_path)["untrusted"]] == [CAFE.key]
    # Trust it from the list, then stop trusting it: marked, and closed.
    assert lantrust.trust_network(tmp_path, CAFE.key)
    assert lantrust.refresh(tmp_path, CAFE)["open"] is True
    assert lantrust.load(tmp_path)["untrusted"] == []
    assert lantrust.untrust_network(tmp_path, CAFE.key)
    assert lantrust.is_open() is False and lantrust.status()["reason"] == "untrusted_network"
    state = lantrust.load(tmp_path)
    assert [n["key"] for n in state["networks"]] == [HOME.key]
    assert [(n["key"], n["blocked"]) for n in state["untrusted"]] == [(CAFE.key, True)]
    # Forget takes it off both lists: new again next time (from home here,
    # since forgetting the network the computer is on lists it again as seen).
    lantrust.refresh(tmp_path, HOME)
    assert lantrust.forget_network(tmp_path, CAFE.key)
    assert lantrust.load(tmp_path)["untrusted"] == []
    assert not lantrust.untrust_network(tmp_path, "nothing-like-it")
    lantrust.reset_for_tests()


def test_turning_the_switch_on_does_not_trust_a_network_marked_untrusted(tmp_path, monkeypatch):
    lantrust.reset_for_tests()
    monkeypatch.setattr(netid, "read", lambda: CAFE)
    lantrust.save(tmp_path, _state(untrusted=[{"key": CAFE.key, "blocked": True}]))
    assert lantrust.remember_current(tmp_path)["reason"] == "untrusted_network"
    assert lantrust.load(tmp_path)["networks"] == []
    lantrust.reset_for_tests()


# --- 14 days unused ------------------------------------------------------------------


class _Config:
    def __init__(self, data_dir, on=True):
        self.data_dir = data_dir
        self.prefs = {netbind.LAN_PREF: on}

    def get_preference(self, key, default=None):
        return self.prefs.get(key, default)

    def set_preference(self, key, value):
        self.prefs[key] = value


def test_lan_mode_switches_itself_off_after_fourteen_days_unused(tmp_path):
    lantrust.reset_for_tests()
    config = _Config(tmp_path)
    # Turned on before the clock was kept: the clock starts now.
    assert lanlive.switch_off_if_unused(config) is False
    started = lantrust.load(tmp_path)["turned_on"]
    assert started > 0
    day = 86400
    assert lanlive.switch_off_if_unused(config, now=started + 13 * day) is False
    # A device connected on day 10: fourteen days count from then.
    lantrust.note_used()
    lantrust._used["at"] = started + 10 * day
    assert lanlive.switch_off_if_unused(config, now=started + 20 * day) is False
    assert lanlive.switch_off_if_unused(config, now=started + 25 * day) is True
    assert config.prefs[netbind.LAN_PREF] is False
    assert lantrust.load(tmp_path)["switched_off"]
    # Off already: nothing more to do, and turning on spends the notice.
    assert lanlive.switch_off_if_unused(config, now=started + 99 * day) is False
    lantrust.mark_turned_on(tmp_path)
    assert lantrust.load(tmp_path)["switched_off"] == ""
    lantrust.reset_for_tests()


# --- the receipt sees a phone connecting (INBOX 894) --------------------------------


def test_an_incoming_connection_is_a_local_network_row_with_the_address_only():
    egress.reset()
    before = egress.totals()["local_network"]
    egress.record_incoming("192.168.0.50")
    egress.record_incoming("::ffff:192.168.0.50")  # a dual-stack socket's form of the same phone
    # A phone's own global IPv6 address in this network's /64 is still local.
    egress.record_incoming("2001:db8::50")
    rows = [r for r in egress.destinations() if r["kind"] == "incoming"]
    assert {(r["host"], r["count"], r["scope"], r["port"]) for r in rows} == {
        ("192.168.0.50", 2, "local_network", None),
        ("2001:db8::50", 1, "local_network", None),
    }
    assert all(r["feature"] == "Other devices" and r["purposes"] == [egress.INCOMING_PURPOSE] for r in rows)
    assert egress.totals()["local_network"] == before + 3
    assert egress.verdict(egress.totals()) == "local_network"
    egress.reset()


def test_the_receipt_says_came_in_for_an_incoming_row():
    js = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "settings-data.js").read_text(encoding="utf-8")
    assert 'row.kind === "incoming"' in js and "Came in from" in js


# --- the address set changes: a certificate naming it (INBOX 892) -------------------


def test_a_new_address_gets_a_certificate_that_names_it(tmp_path, monkeypatch):
    first = lancert.ensure(tmp_path, ["192.168.0.5"])
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(first.cert_path), str(first.key_path))
    lancert.set_live_context(context)
    try:
        listener = lanlive.Listener(None, None, SimpleNamespace(data_dir=tmp_path), local_port=8000)
        listener.fingerprint = first.fingerprint
        # The computer joined a phone's hotspot: a new address, same authority.
        monkeypatch.setattr(lancert, "default_names", lambda addresses=None: ["172.20.10.2"])
        listener._reissue()
        now = lancert.read(tmp_path)
        assert "172.20.10.2" in now.names and now.fingerprint == listener.fingerprint != first.fingerprint
        assert now.authority_fingerprint == first.authority_fingerprint  # the phone is not asked again
        # The same addresses again: nothing is made.
        listener._reissue()
        assert lancert.read(tmp_path).fingerprint == now.fingerprint
    finally:
        lancert.set_live_context(None)


def test_turning_away_a_network_drops_the_connections_already_open():
    closed = []
    conns = [SimpleNamespace(transport=SimpleNamespace(close=lambda n=n: closed.append(n))) for n in range(3)]
    server = SimpleNamespace(server_state=SimpleNamespace(connections=conns))
    assert lanserve.drop_connections(server) == 3 and sorted(closed) == [0, 1, 2]
    assert lanserve.drop_connections(SimpleNamespace()) == 0


# --- a phone never installs software here (secscan-1011's decision) ---------------


def test_a_phones_request_waits_for_this_computer_before_the_semantic_install(monkeypatch):
    from tessellate.ai import embeddings
    from tessellate.core import extras, jobs

    origin.reset_for_tests()
    monkeypatch.delenv("TESSELLATE_NO_AUTO_INSTALL", raising=False)
    started = []
    monkeypatch.setattr(extras, "start", lambda name, auto=False: (started.append(name), (False, "test"))[1])
    monkeypatch.setattr(jobs, "enqueue", lambda kind, func, *a, **k: func())
    service = object.__new__(embeddings.EmbeddingService)
    service._auto_install_attempted = False
    service._models = SimpleNamespace(_config=SimpleNamespace(get_preference=lambda key, default=None: True))
    missing = ModuleNotFoundError("No module named 'sentence_transformers'")
    with origin.acting_for(True):
        service._maybe_auto_install_missing_package(missing)
    assert started == [] and origin.has_deferred() and service._auto_install_attempted is False
    assert origin.run_deferred(jobs.enqueue) == 1
    assert started == ["semantic"] and not origin.has_deferred()
    origin.reset_for_tests()


def test_a_job_queued_for_a_phone_runs_as_the_phone():
    from tessellate.core import jobs

    with origin.acting_for(True):
        job = jobs._Job(1, "embed", print, (), {}, "x")
    assert job.another_device is True
    assert jobs._Job(2, "embed", print, (), {}, "y").another_device is False


# --- the routes ------------------------------------------------------------------------


@pytest.fixture()
def lan_app(client, monkeypatch):
    routes_auth._active_tokens.clear()
    routes_auth._media_tickets.clear()
    routes_auth._clear_unlock_failures()
    routes_auth._device_tokens.clear()
    routes_auth._network_tokens.clear()
    vault.close()
    lantrust.reset_for_tests()
    origin.reset_for_tests()
    monkeypatch.setattr(netid, "read", lambda: HOME)
    here = _here(client)
    here.headers["X-Auth-Token"] = here.post("/auth/setup", json={"password": PASSWORD}).json()["token"]
    yield client
    lantrust.reset_for_tests()
    origin.reset_for_tests()
    netbind.set_current(netbind.LOOPBACK)
    routes_auth._active_tokens.clear()
    routes_auth._device_tokens.clear()
    routes_auth._network_tokens.clear()
    vault.close()


def _here(client) -> TestClient:
    token = next(iter(routes_auth._active_tokens), None)
    return TestClient(
        client.app, base_url="http://127.0.0.1:8795", client=("127.0.0.1", 50000),
        headers={"X-Auth-Token": token} if token else {},
    )


def _phone(client) -> TestClient:
    from tessellate.core import deps

    lantrust.set_flag(deps.get_config().data_dir, "ask_new_devices", False)
    phone = TestClient(client.app, base_url="https://192.168.0.50:8443", client=("192.168.0.50", 50001))
    phone.headers["X-Auth-Token"] = phone.post("/auth/unlock", json={"password": PASSWORD}).json()["token"]
    return phone


def test_trust_and_untrust_from_the_list_are_this_computers(lan_app):
    from tessellate.core import deps

    data_dir = deps.get_config().data_dir
    lantrust.refresh(data_dir, CAFE)  # seen, closed: listed as untrusted
    here, phone = _here(lan_app), _phone(lan_app)
    state = here.get("/auth/lan-access").json()
    assert [(n["key"], n["blocked"]) for n in state["untrusted"]] == [(CAFE.key, False)]
    assert state["unused_days"] == lantrust.UNUSED_DAYS and state["live"] is False
    for path in (f"/auth/lan-networks/{CAFE.key}/trust", f"/auth/lan-networks/{CAFE.key}/untrust", "/auth/lan-notice/dismiss"):
        refused = phone.post(path, json={"current_password": PASSWORD})
        assert refused.status_code == 403 and refused.json()["detail"] == REFUSAL, path
    assert here.post(f"/auth/lan-networks/{CAFE.key}/trust", json={}).status_code == 401
    state = here.post(f"/auth/lan-networks/{CAFE.key}/trust", json={"current_password": PASSWORD}).json()
    assert [n["key"] for n in state["networks"]] == [CAFE.key] and state["untrusted"] == []
    state = here.post(f"/auth/lan-networks/{CAFE.key}/untrust").json()
    assert state["networks"] == [] and state["untrusted"][0]["blocked"] is True
    assert here.post("/auth/lan-networks/nothing/untrust").status_code == 404
    refused = phone.delete(f"/auth/lan-networks/{CAFE.key}")
    assert refused.status_code == 403 and refused.json()["detail"] == REFUSAL
    removed = here.delete(f"/auth/lan-networks/{CAFE.key}")
    assert removed.status_code == 200


def test_switching_off_signs_every_other_device_out(lan_app):
    here, phone = _here(lan_app), _phone(lan_app)
    assert phone.get("/auth/lan-access").status_code == 200
    state = here.post("/auth/lan-access", json={"enabled": False}).json()
    assert state["allow_lan"] is False
    assert phone.get("/auth/lan-access").status_code == 401
    assert here.get("/auth/lan-access").status_code == 200


def test_the_watch_tells_the_status_bar_the_switch_and_the_notice(lan_app):
    from tessellate.core import deps

    here = _here(lan_app)
    lantrust.mark_switched_off(deps.get_config().data_dir)
    watch = here.get("/auth/lan-watch?since=-1").json()
    assert watch["allow_lan"] is False and watch["switched_off"] and watch["live"] is False
    # Off: the icon's words need no network, no reason and no listener error.
    assert watch["serving"] is False and watch["network"] == "" and watch["reason"] == "" and watch["error"] == ""
    assert here.post("/auth/lan-notice/dismiss").json()["switched_off"] == ""


def test_a_change_from_this_computer_starts_what_waited_and_a_phones_does_not(lan_app, monkeypatch):
    from tessellate.core import jobs

    ran = []
    monkeypatch.setattr(jobs, "enqueue", lambda kind, func, *a, **k: func())
    origin.defer("test", lambda: ran.append(origin.from_another_device()))
    phone = _phone(lan_app)
    phone.post("/auth/lan-options", json={"name": "ask_new_devices", "enabled": True})
    assert ran == [] and origin.has_deferred()
    _here(lan_app).post("/auth/lan-options", json={"name": "ask_new_devices", "enabled": True})
    assert ran == [False] and not origin.has_deferred()


# --- end to end: on and off with no restart (INBOX 900) -----------------------------


@pytest.fixture()
def network_address():
    address = _network_address()
    if address is None:
        pytest.skip("this machine has no network address to reach the app on")
    return address


def _wait_listening(address: str, port: int, cafile, *, up: bool, seconds: float = 10.0) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            _Http(address, port, cafile=cafile).call("GET", "/health")
            if up:
                return True
        except OSError:
            if not up:
                return True
        time.sleep(0.2)
    return False


def test_turning_lan_mode_on_and_off_applies_without_a_restart(tmp_path, network_address):
    proc, port, _log = _start(tmp_path, {"web_search_enabled": False})
    try:
        here = _Http("127.0.0.1", port)
        cert = tmp_path / "data" / "lan-tls" / "cert.pem"
        lan_port = _lan_port(port)
        status, body, _ = here.call("POST", "/auth/setup", {"password": PASSWORD})
        owner = {"X-Auth-Token": body["token"]}
        with pytest.raises(OSError):
            _Http(network_address, lan_port).call("GET", "/health")

        # On: the answer already says other devices can open it.
        status, state, _ = here.call("POST", "/auth/lan-access", {"enabled": True, "current_password": PASSWORD}, owner)
        assert status == 200 and state["live"] is True
        if state["held"] == "unknown_network":
            pytest.skip("this machine's network cannot be told apart (no router hardware address)")
        assert state["restart_required"] is False and state["other_devices"] is True, state
        lan = _Http(network_address, lan_port, cafile=cert)
        assert lan.call("GET", "/health")[0] == 200

        # A phone signs in and holds a keep-alive connection open.
        here.call("POST", "/auth/lan-options", {"name": "ask_new_devices", "enabled": False, "current_password": PASSWORD}, owner)
        status, body, _ = lan.call("POST", "/auth/unlock", {"password": PASSWORD})
        phone = {"X-Auth-Token": body["token"]}
        kept = http.client.HTTPSConnection(
            network_address, lan_port, timeout=10, context=ssl.create_default_context(cafile=str(cert))
        )
        kept.request("GET", "/health", headers={"Host": f"{network_address}:{lan_port}"})
        assert kept.getresponse().status == 200

        # The receipt shows the phone connecting, by address only.
        status, receipt, _ = here.call("GET", "/privacy/receipt", headers=owner)
        incoming = [r for r in receipt["destinations"] if r["kind"] == "incoming"]
        assert [r["host"] for r in incoming] == [network_address] and incoming[0]["scope"] == "local_network"

        # Off: the port refuses, the open connection is gone, the phone is out.
        status, state, _ = here.call("POST", "/auth/lan-access", {"enabled": False}, owner)
        assert status == 200 and state["restart_required"] is False and state["other_devices"] is False
        assert _wait_listening(network_address, lan_port, cert, up=False, seconds=3)
        with pytest.raises((OSError, http.client.HTTPException)):
            kept.request("GET", "/health", headers={"Host": f"{network_address}:{lan_port}"})
            kept.getresponse().read()
        kept.close()
        assert here.call("GET", "/auth/lan-access", headers=phone)[0] == 401
        assert here.call("GET", "/health")[0] == 200  # this computer never moved

        # On again, still no restart.
        status, state, _ = here.call("POST", "/auth/lan-access", {"enabled": True, "current_password": PASSWORD}, owner)
        assert state["other_devices"] is True
        assert _wait_listening(network_address, lan_port, cert, up=True, seconds=5)
    finally:
        _stop(proc)


# ---- the status bar's Other devices icon and panel (INBOX 896) ------------

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def _js(name: str) -> str:
    return (FRONTEND / "js" / name).read_text(encoding="utf-8")


def test_the_icon_is_a_tools_doorway_hidden_until_this_computer_answers():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    footer = html.split('<footer', 1)[1].split("</footer>", 1)[0]
    tools = footer.split('data-status-zone="tools"', 1)[1].split('data-status-zone="control"', 1)[0]
    button = re.search(r'<button id="status-lan"[^>]*>', tools)
    assert button, "the Other devices icon left the tools zone"
    for attr in ('class="status-item icon-only hidden"', 'data-status-slot="lan"', 'data-this-computer="hide"', 'aria-label="Other devices"'):
        assert attr in button.group(0), attr
    # The panel lives outside the footer: its backdrop-filter would contain it.
    assert 'id="lan-popover"' not in footer and 'id="lan-popover"' in html


def test_the_watch_paints_the_icon_and_keeps_going_while_lan_mode_is_off():
    watch = _js("lan-watch.js")
    once = watch.split("async function lanWatchOnce(", 1)[1].split("\n}\n", 1)[0]
    assert 'error?.status === 403) return "stop"' in once
    assert 'if (!state.serving) return "stop"' not in once
    assert "lanPaintIcon(lanLookFromWatch(state))" in once
    assert "lanNoticeSwitchedOff(state.switched_off)" in once
    # The recipes: the help popover on a desktop, the sheet without a box.
    assert "wireHelpPopover(button, panel)" in watch and "openSheet({" in watch
    assert "stopImmediatePropagation()" in watch and "getBoundingClientRect().width" in watch
    # One switch and one set of network rows, shared with Settings.
    assert "lanSwitch(!state.allow_lan)" in watch and "lanNetworkRows(state, paint)" in watch
    assert 'shortcutTitle(`Other devices. ${look.words}`, "lanPanel")' in watch


def test_the_icon_is_reachable_by_key_palette_slot_and_phone_row():
    wiring = _js("settings-wiring.js")
    assert 'lanPanel: { keys: "Alt+L"' in wiring and "lanPanel: () => openLanPanel()," in wiring
    assert 'chord: "lanPanel", act: () => openLanPanel()' in _js("settings-panes.js")
    assert 'key: "lan",' in _js("settings-controls.js").split("const STATUS_SLOTS", 1)[1].split("];", 1)[0]
    assert '{ id: "status-lan", label: "ph:wifi-high Other devices" }' in _js("phone-shell.js")
    assert "function openLanPanel()" in _js("status.js")


def test_settings_lists_untrusted_networks_with_trust_and_forget():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert 'id="account-lan-untrusted"' in html and "Untrusted networks" in html
    controls = _js("settings-controls.js")
    rows = controls.split("function lanNetworkRows(", 1)[1].split("\n}\n", 1)[0]
    for route in ('path(network, "untrust")', "lanTrustNetwork(network, paint)", 'method: "DELETE"'):
        assert route in rows, route
    assert "/trust`" in controls.split("async function lanTrustNetwork(", 1)[1].split("\n}\n", 1)[0]


# LAN mode end to end against the real launcher on 0.0.0.0 (a client that is not loopback), plus the password, new-device and DNS-rebinding refusals. The _clean reset is applied to these tests only.


ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def _clean():
    routes_auth._active_tokens.clear()
    routes_auth._media_tickets.clear()
    routes_auth._clear_unlock_failures()
    vault.close()
    netbind.set_current(netbind.LOOPBACK)
    yield
    netbind.set_current(netbind.LOOPBACK)
    routes_auth._active_tokens.clear()
    routes_auth._media_tickets.clear()
    routes_auth._clear_unlock_failures()
    vault.close()


def _local(client) -> TestClient:
    return TestClient(client.app, base_url="http://127.0.0.1:8795", client=("127.0.0.1", 50000))


def _setup(client) -> dict:
    token = _local(client).post("/auth/setup", json={"password": PASSWORD}).json()["token"]
    return {"X-Auth-Token": token}


# --- the switch ----------------------------------------------------------------


@pytest.mark.usefixtures("_clean")
def test_it_is_off_by_default_and_binds_loopback(app_state):
    assert netbind.lan_enabled(app_state) is False
    assert netbind.bind_host(app_state, has_password=True) == "127.0.0.1"


@pytest.mark.usefixtures("_clean")
def test_only_a_literal_true_turns_it_on(app_state):
    """A hand-edited preferences file must not open the notebook by accident."""
    for value in ("yes", 1, "true", [True]):
        app_state.set_preference(netbind.LAN_PREF, value)
        assert netbind.bind_host(app_state, has_password=True) == "127.0.0.1", value
    app_state.set_preference(netbind.LAN_PREF, True)
    # Every interface: IPv4 and IPv6 on one socket where the machine has
    # both, IPv4 alone where it has no IPv6 (this sandbox).
    assert netbind.bind_host(app_state, has_password=True) == ("::" if netbind.dual_stack() else "0.0.0.0")


# --- IPv6 (WORLD_CLASS_PLAN §12, row 2) -------------------------------------------


@pytest.mark.usefixtures("_clean")
def test_without_dual_stack_lan_mode_binds_ipv4(app_state, monkeypatch):
    app_state.set_preference(netbind.LAN_PREF, True)
    monkeypatch.setattr(netbind, "dual_stack", lambda: False)
    assert netbind.bind_host(app_state, has_password=True) == "0.0.0.0"
    monkeypatch.setattr(netbind, "dual_stack", lambda: True)
    assert netbind.bind_host(app_state, has_password=True) == "::"
    assert netbind.is_loopback_bind("::") is False


@pytest.mark.usefixtures("_clean")
def test_only_the_dual_stack_host_gets_a_socket_of_its_own():
    assert netbind.listening_socket("127.0.0.1", 0) is None
    assert netbind.listening_socket("0.0.0.0", 0) is None


@pytest.mark.usefixtures("_clean")
def test_an_ipv4_client_on_the_dual_stack_socket_is_still_this_computer():
    """On the dual-stack socket IPv4 arrives as `::ffff:a.b.c.d`, and Python
    does not call `::ffff:127.0.0.1` loopback: the guard reads the IPv4 inside."""
    assert netbind.arrived_on_loopback(("::ffff:127.0.0.1", 8000)) is True
    assert netbind.arrived_on_loopback(("::1", 8000)) is True
    assert netbind.arrived_on_loopback(("[::1]", 8000)) is True
    assert netbind.arrived_on_loopback(("::ffff:192.168.1.5", 8000)) is False
    assert netbind.arrived_on_loopback(("2001:db8::5", 8000)) is False
    assert netbind.arrived_on_loopback(("fd12:3456::7", 8000)) is False


@pytest.mark.usefixtures("_clean")
def test_ipv6_addresses_are_listed_bracketed_and_never_link_local(monkeypatch, app_state):
    def fake_getaddrinfo(host, port, family=0, *args, **kwargs):
        if family == socket.AF_INET6:
            return [
                (family, 1, 6, "", ("fe80::1%eth0", 0, 0, 2)),
                (family, 1, 6, "", ("::1", 0, 0, 0)),
                (family, 1, 6, "", ("2001:db8::5", 0, 0, 0)),
                (family, 1, 6, "", ("fd12:3456::7", 0, 0, 0)),
                (family, 1, 6, "", ("::ffff:192.168.1.9", 0, 0, 0)),
            ]
        return [(socket.AF_INET, 1, 6, "", ("192.168.1.9", 0))]

    monkeypatch.setattr(netbind.socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(netbind.sys, "platform", "test")
    assert netbind.lan_addresses(include_v6=True) == ["192.168.1.9", "2001:db8::5", "fd12:3456::7"]
    assert netbind.lan_addresses(include_v6=False) == ["192.168.1.9"]
    assert netbind.url_host("2001:db8::5") == "[2001:db8::5]"
    assert netbind.url_host("192.168.1.9") == "192.168.1.9"
    monkeypatch.setattr(netbind, "lan_addresses", lambda include_v6=None: ["192.168.1.9", "2001:db8::5"])
    app_state.set_preference(netbind.LAN_PREF, True)
    netbind.set_current("::")
    # LAN mode is HTTPS on its own port (8443 beside 8000; core/lancert.py).
    assert netbind.describe(app_state, 8000)["addresses"] == [
        "https://192.168.1.9:8443",
        "https://[2001:db8::5]:8443",
    ]


@pytest.mark.usefixtures("_clean")
def test_a_bracketed_ipv6_host_header_names_this_computer():
    assert netbind.host_allowed("[::1]:8000")
    assert netbind.host_allowed("[2001:db8::5]:8000")
    assert not netbind.host_allowed("evil.example:8000")


@pytest.mark.usefixtures("_clean")
def test_a_localhost_name_is_this_computer_only_on_loopback(monkeypatch):
    """`tessellate.localhost` is the friendly name `TESSELLATE_LOCAL_NAME`
    gives (no DNS, no admin rights). Only that one name, and only on a
    request that arrived on loopback (lansec-1025): a browser that sends a
    `*.localhost` lookup to the network's DNS (a hostile cafe resolver) could
    otherwise point `evil.localhost` at this computer's LAN address and
    rebind, so off loopback, or under any other name, it is a 421."""
    from tessellate.core import security

    monkeypatch.setattr(security, "_notebook_has_password", lambda: True)
    monkeypatch.delenv("TESSELLATE_LOCAL_NAME", raising=False)
    assert not netbind.host_allowed("tessellate.localhost:8000", on_loopback=True)
    monkeypatch.setenv("TESSELLATE_LOCAL_NAME", "Tessellate")
    assert netbind.local_name() == "tessellate.localhost"
    assert netbind.host_allowed("tessellate.localhost:8000", on_loopback=True)
    assert not netbind.host_allowed("tessellate.localhost:8000")
    assert not netbind.host_allowed("evil.localhost:8000", on_loopback=True)
    assert not netbind.host_allowed("notes.tessellate.localhost", on_loopback=True)
    assert not netbind.host_allowed("localhost.evil.example:8000", on_loopback=True)
    assert not netbind.host_allowed("evillocalhost:8000", on_loopback=True)
    assert _through_host_check(("127.0.0.1", 8000), "tessellate.localhost:8000") == (None, True)
    assert _through_host_check(("::ffff:127.0.0.1", 8443), "tessellate.localhost:8443") == (None, True)
    assert _through_host_check(("192.168.1.9", 8443), "tessellate.localhost:8443") == (421, False)
    assert _through_host_check(("127.0.0.1", 8000), "evil.localhost:8000") == (421, False)
    # The LAN port's plain-http redirect never sends a phone to a .localhost name.
    from tessellate.core import lanserve

    head = b"GET / HTTP/1.1\r\nHost: tessellate.localhost:8443\r\n\r\n"
    assert lanserve.redirect_response(head, 8443).startswith(b"HTTP/1.1 400")


@pytest.mark.usefixtures("_clean")
def test_the_local_name_counts_as_this_computer(client, app_state, monkeypatch):
    """Sign-in off, the friendly name gets its password-free session as
    127.0.0.1 does; any other `*.localhost` name does not."""
    from starlette.requests import Request

    monkeypatch.setenv("TESSELLATE_LOCAL_NAME", "tessellate")

    def request(host: str) -> Request:
        return Request({"type": "http", "method": "GET", "path": "/", "headers": [(b"host", host.encode())],
                        "client": ("127.0.0.1", 5000), "server": ("127.0.0.1", 8000), "scheme": "http"})

    assert routes_auth._from_this_computer(request("tessellate.localhost:8000"))
    assert not routes_auth._from_this_computer(request("evil.localhost:8000"))


@pytest.mark.usefixtures("_clean")
def test_turning_it_on_needs_the_current_password(client, app_state):
    headers = _setup(client)
    local = _local(client)
    missing = local.post("/auth/lan-access", json={"enabled": True}, headers=headers)
    assert missing.status_code == 401
    wrong = local.post(
        "/auth/lan-access", json={"enabled": True, "current_password": "not it"}, headers=headers
    )
    assert wrong.status_code == 401
    assert netbind.lan_enabled(app_state) is False
    right = local.post(
        "/auth/lan-access", json={"enabled": True, "current_password": PASSWORD}, headers=headers
    )
    assert right.status_code == 200, right.text
    body = right.json()
    assert body["allow_lan"] is True
    assert body["restart_required"] is True  # this launch still listens on loopback
    assert netbind.lan_enabled(app_state) is True
    rows = local.get("/audit?entity_type=user&limit=20", headers=headers).json()
    assert any("other devices" in (row.get("detail") or "") for row in rows)


@pytest.mark.usefixtures("_clean")
def test_wrong_passwords_for_the_switch_are_throttled_like_an_unlock(client):
    headers = _setup(client)
    local = _local(client)
    for _ in range(routes_auth._FAILURE_ALLOWANCE + 1):
        local.post("/auth/lan-access", json={"enabled": True, "current_password": "a guess"}, headers=headers)
    again = local.post(
        "/auth/lan-access", json={"enabled": True, "current_password": PASSWORD}, headers=headers
    )
    assert again.status_code == 429


@pytest.mark.usefixtures("_clean")
def test_turning_it_off_needs_nothing(client, app_state):
    headers = _setup(client)
    app_state.set_preference(netbind.LAN_PREF, True)
    off = _local(client).post("/auth/lan-access", json={"enabled": False}, headers=headers)
    assert off.status_code == 200
    assert netbind.lan_enabled(app_state) is False


@pytest.mark.usefixtures("_clean")
def test_put_preferences_cannot_turn_it_on(client, app_state):
    headers = _setup(client)
    _local(client).put("/preferences", json={netbind.LAN_PREF: True}, headers=headers)
    assert netbind.lan_enabled(app_state) is False


@pytest.mark.usefixtures("_clean")
def test_the_state_is_readable_for_settings(client, app_state):
    headers = _setup(client)
    body = _local(client).get("/auth/lan-access", headers=headers).json()
    assert body == {**body, "allow_lan": False, "other_devices": False, "restart_required": False}


# --- the rebinding guard ---------------------------------------------------------


@pytest.mark.usefixtures("_clean")
def test_host_names_that_are_this_computer():
    assert netbind.host_allowed("127.0.0.1:8000")
    assert netbind.host_allowed("localhost:8000")
    assert netbind.host_allowed("[::1]:8000")
    assert netbind.host_allowed("192.168.1.20:8000")
    assert netbind.host_allowed(f"{socket.gethostname()}:8000")
    assert netbind.host_allowed(None)
    assert not netbind.host_allowed("evil.example:8000")
    assert not netbind.host_allowed("evil.example")


@pytest.mark.usefixtures("_clean")
def test_the_guard_judges_every_real_socket(client):
    """The in-process test client (its scope names `testserver`, never a
    number) is not judged; a request on a numbered address is, loopback
    included (SEC-05)."""
    _setup(client)
    assert client.get("/health", headers={"Host": "evil.example"}).status_code == 200
    assert _local(client).get("/health", headers={"Host": "evil.example"}).status_code == 421
    netbind.set_current("0.0.0.0")
    refused = client.get("/health", headers={"Host": "evil.example"})
    assert refused.status_code == 421
    assert client.get("/health", headers={"Host": "192.168.1.20:8000"}).status_code == 200


def _through_host_check(server: tuple, host: str | None) -> tuple[int | None, bool]:
    """Run one request through HostCheckMiddleware with a made-up ASGI
    scope: the (address, port) the request arrived at, and its Host. Returns
    (the status the middleware answered with, or None; whether the app ran)."""

    from tessellate.core import security

    ran = []

    async def app(scope, receive, send):
        ran.append(scope["path"])

    headers = [] if host is None else [(b"host", host.encode())]
    scope = {"type": "http", "method": "GET", "path": "/health", "headers": headers, "server": server}
    sent = []

    async def send(message):
        sent.append(message)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    asyncio.run(security.HostCheckMiddleware(app)(scope, receive, send))
    status = next((m["status"] for m in sent if m["type"] == "http.response.start"), None)
    return status, bool(ran)


@pytest.mark.usefixtures("_clean")
def test_the_guard_keys_on_the_address_the_request_arrived_at(monkeypatch):
    """`set_current` is the launcher's word (review, 2026-09-26): a server
    started any other way on 0.0.0.0 (`uvicorn --host 0.0.0.0`, the sweeps'
    serve.sh, a container) never called it, so the guard stayed off while
    the socket was open to the network. The ASGI scope carries the address
    the request arrived at (`server`), which is the fact itself: a request
    that came in on a network address gets the check whatever the launcher
    said, and one that came in on loopback never does. Off loopback a
    request with no Host at all is refused too: HTTP/1.1 requires one, so
    nothing legitimate on the network omits it."""
    from tessellate.core import security

    monkeypatch.setattr(security, "_notebook_has_password", lambda: True)
    netbind.set_current(netbind.LOOPBACK)
    lan = ("192.168.1.9", 8000)
    assert _through_host_check(lan, "evil.example") == (421, False)
    assert _through_host_check(lan, "192.168.1.9:8000") == (None, True)
    assert _through_host_check(lan, "[fe80::1%eth0]:8000") == (None, True)
    assert _through_host_check(lan, "LOCALHOST:8000") == (None, True)
    assert _through_host_check(lan, "evil.example.:8000") == (421, False)
    assert _through_host_check(lan, None) == (421, False)
    # On loopback too since SEC-05 (audit 2026-10-05): a rebinding page
    # arrives on 127.0.0.1 naming its own domain. A local tool that sends no
    # Host at all is still served.
    assert _through_host_check(("127.0.0.1", 8000), "evil.example") == (421, False)
    assert _through_host_check(("::1", 8000), "evil.example") == (421, False)
    assert _through_host_check(("127.0.0.1", 8000), "localhost:8000") == (None, True)
    assert _through_host_check(("127.0.0.1", 8000), None) == (None, True)
    # The test client's own scope names the server rather than numbering it.
    assert _through_host_check(("testserver", 80), "evil.example") == (None, True)


# --- end to end: the real launcher on 0.0.0.0 --------------------------------------


def _network_address() -> str | None:
    for address in netbind.lan_addresses():
        try:
            with socket.create_connection((address, 9), timeout=0.2):
                pass
        except ConnectionRefusedError:
            return address  # reachable and ours: a refusal is the kernel answering
        except OSError:
            continue
        return address
    return None


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start(tmp_path: Path, preferences: dict) -> tuple[subprocess.Popen, int, Path]:
    """The real launcher. The HTTPS port other devices use is `port + 1000`,
    pinned through `TESSELLATE_LAN_PORT` (see `_lan_port`)."""
    data = tmp_path / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "preferences.json").write_text(json.dumps(preferences))
    port = _free_port()
    log = tmp_path / "server.log"
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "TESSELLATE_DATA_DIR": str(data),
        "TESSELLATE_PORT": str(port),
        "TESSELLATE_LAN_PORT": str(_lan_port(port)),
    }
    proc = subprocess.Popen(  # noqa: S603  # our own launcher, fixed argv
        [sys.executable, "-m", "tessellate"],
        cwd=str(tmp_path),
        env=env,
        stdout=log.open("w"),
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
    )
    deadline = time.time() + 90
    while time.time() < deadline:
        if proc.poll() is not None:
            raise AssertionError(f"the server exited: {log.read_text()[-2000:]}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.3)
    else:
        proc.kill()
        raise AssertionError("the server never listened")
    return proc, port, log


def _stop(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _lan_port(port: int) -> int:
    """`_free_port` hands out ports below 61000 on Linux, so this fits."""
    return port + 1000 if port + 1000 < 65536 else port - 1000


class _Http:
    """http.client, never a proxy: the point is which socket the server sees.

    With `cafile`, HTTPS verified against the notebook's own certificate and
    nothing else: the address has to be in its names (the SAN), or the
    handshake fails, which is the test of the names."""

    def __init__(self, address: str, port: int, cafile: Path | None = None) -> None:
        self.address, self.port, self.cafile = address, port, cafile

    def _connection(self):
        if self.cafile is None:
            return http.client.HTTPConnection(self.address, self.port, timeout=30)
        context = ssl.create_default_context(cafile=str(self.cafile))
        return http.client.HTTPSConnection(self.address, self.port, timeout=30, context=context)

    def call(self, method: str, path: str, body=None, headers=None, host=None):
        conn = self._connection()
        try:
            sent = {"Host": host or f"{self.address}:{self.port}", **(headers or {})}
            payload = None
            if body is not None:
                payload = json.dumps(body)
                sent["Content-Type"] = "application/json"
            conn.request(method, path, body=payload, headers=sent)
            response = conn.getresponse()
            raw = response.read()
            try:
                data = json.loads(raw) if raw else None
            except ValueError:
                data = None
            return response.status, data, response.getheaders()
        finally:
            conn.close()


@pytest.mark.usefixtures("_clean")
def test_lan_mode_end_to_end(tmp_path, network_address):
    # SEC-01: with the switch on but no password yet, the launcher listens
    # on this computer only; the password is set here, then it restarts.
    prefs = {netbind.LAN_PREF: True, "web_search_enabled": True}
    proc, port, log = _start(tmp_path, prefs)
    try:
        with pytest.raises(OSError):
            _Http(network_address, port).call("GET", "/auth/status")
        status, _, _ = _Http("127.0.0.1", port).call("POST", "/auth/setup", {"password": PASSWORD})
        assert status == 200
    finally:
        _stop(proc)
    proc, port, log = _start(tmp_path, prefs)
    try:
        cert = tmp_path / "data" / "lan-tls" / "cert.pem"
        lan = _Http(network_address, _lan_port(port), cafile=cert)
        here = _Http("127.0.0.1", port)

        # INBOX 867: the switch was never turned on in this network (it was
        # written to the file), so the LAN port is not even bound until this
        # computer says "Allow on this network", with the password.
        with pytest.raises(OSError):
            _Http(network_address, _lan_port(port)).call("GET", "/health")
        status, body, _ = here.call("POST", "/auth/unlock", {"password": PASSWORD})
        owner = {"X-Auth-Token": body["token"]}
        status, state, _ = here.call("GET", "/auth/lan-access", headers=owner)
        if state["held"] == "unknown_network":
            pytest.skip("this machine's network cannot be told apart (no router hardware address)")
        assert state["held"] == "new_network" and state["other_devices"] is False
        assert here.call("POST", "/auth/lan-networks/allow", {"current_password": "a guess"}, owner)[0] == 401
        status, state, _ = here.call("POST", "/auth/lan-networks/allow", {"current_password": PASSWORD}, owner)
        assert status == 200 and state["held"] is None and len(state["networks"]) == 1
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                _Http(network_address, _lan_port(port)).call("GET", "/health")
                break
            except OSError:
                time.sleep(0.2)

        # The network gets HTTPS only (the owner, 2026-10-05; SEC-08): the
        # plain http port answers on this computer alone, and the HTTPS one
        # answers a plain request only with a redirect to itself over https
        # (INBOX 866: a phone given the address without https:// got nothing).
        with pytest.raises(OSError):
            _Http(network_address, port).call("GET", "/health")
        status, data, headers = _Http(network_address, _lan_port(port)).call("GET", "/health")
        assert status == 301 and data is None
        assert dict(headers)["Location"] == f"https://{network_address}:{_lan_port(port)}/health"

        # It listens on the network address, and says so on the receipt.
        status, body, _ = lan.call("GET", "/auth/status")
        assert status == 200 and body["setup_required"] is False
        status, receipt, _ = here.call("GET", "/privacy/receipt", headers=owner)
        assert receipt["listening"]["other_devices"] is True
        assert f"https://{network_address}:{_lan_port(port)}" in receipt["listening"]["addresses"]
        status, state, _ = here.call("GET", "/auth/lan-access", headers=owner)
        assert state["certificate"]["fingerprint"] in log.read_text()

        # A device on the network is never let in without the password, even
        # with sign-in off for this computer.
        status, _, _ = here.call(
            "POST", "/auth/password-on-open", {"enabled": False, "current_password": PASSWORD}, owner
        )
        assert status == 200
        status, body, _ = lan.call("GET", "/auth/status")
        assert body["auto_session"] is False
        assert lan.call("POST", "/auth/auto-session")[0] == 403
        assert here.call("POST", "/auth/auto-session")[0] == 200
        assert lan.call("GET", "/entries")[0] == 401

        # INBOX 867: a new device waits until this computer allows it. The
        # phone's sign-in is held open; the computer's window hears of it at
        # once (/auth/lan-watch) and Allow lets the same sign-in through.

        result = {}
        asking = threading.Thread(
            target=lambda: result.update(r=lan.call("POST", "/auth/unlock", {"password": PASSWORD}))
        )
        asking.start()
        status, watch, _ = here.call("GET", "/auth/lan-watch?since=-1", headers=owner)
        deadline = time.time() + 10
        while not watch["pending"] and time.time() < deadline:
            status, watch, _ = here.call("GET", f"/auth/lan-watch?since={watch['version']}", headers=owner)
        assert watch["pending"] and watch["pending"][0]["address"] == network_address
        assert lan.call("GET", "/auth/lan-watch", headers={"X-Auth-Token": owner["X-Auth-Token"]})[0] == 403
        assert here.call("POST", f"/auth/lan-devices/{watch['pending'][0]['id']}/allow", {}, owner)[0] == 200
        asking.join(30)

        # The media cookie, not the session token, opens pictures; over
        # HTTPS it is Secure, as well as HttpOnly and SameSite=Strict.
        status, body, headers = result["r"]
        assert status == 200
        phone = body["token"]
        cookies = [value for name, value in headers if name.lower() == "set-cookie"]
        assert cookies and all("httponly" in c.lower() and "samesite=strict" in c.lower() for c in cookies)
        assert all("; secure" in c.lower() for c in cookies)
        ticket = cookies[0].split(";", 1)[0]
        assert lan.call("GET", f"/media/nothing.png?token={phone}")[0] == 401
        assert lan.call("GET", "/media/nothing.png", headers={"Cookie": ticket})[0] == 404

        # Importing a folder of this computer's files is this computer's own
        # act (this_computer_only): a phone is refused outright, and from here
        # the import is still confined to home and the data folder.
        status, _, _ = lan.call(
            "POST", "/import/directory", {"path": "/etc"}, {"X-Auth-Token": phone}
        )
        assert status == 403
        assert here.call("POST", "/import/directory", {"path": "/etc"}, owner)[0] == 400
        # The phone is not the desktop app, whatever this computer is.
        assert lan.call("GET", "/health")[1]["this_computer"] is False
        assert "max-age" in dict(lan.call("GET", "/health")[2]).get("strict-transport-security", "")

        # The web reader refuses this machine and the local network, and the
        # receipt shows nothing was connected to: what it counts on the local
        # network is the phone coming in (INBOX 894), never a reach out.
        for url in (f"http://127.0.0.1:{port}/", "http://10.0.0.1/"):
            status, body, _ = lan.call(
                "GET", f"/websearch/read?url={url}", headers={"X-Auth-Token": phone}
            )
            assert status == 502, (url, status, body)
        status, receipt, _ = lan.call("GET", "/privacy/receipt", headers={"X-Auth-Token": phone})
        outgoing = [d for d in receipt["destinations"] if d["scope"] == "local_network" and d["kind"] != "incoming"]
        assert outgoing == []
        incoming = sum(d["count"] for d in receipt["destinations"] if d["kind"] == "incoming")
        assert receipt["totals"]["local_network"] == incoming > 0
        assert not [d for d in receipt["destinations"] if d["host"] == "10.0.0.1"]

        # DNS rebinding: a name that is not this computer is refused.
        assert lan.call("GET", "/health", host=f"evil.example:{_lan_port(port)}")[0] == 421
        assert lan.call("GET", "/health")[0] == 200

        # Wrong guesses from the network do not lock out this computer.
        for _ in range(routes_auth._FAILURE_ALLOWANCE + 1):
            lan.call("POST", "/auth/unlock", {"password": "a guess"})
        assert lan.call("POST", "/auth/unlock", {"password": PASSWORD})[0] == 429
        assert here.call("POST", "/auth/unlock", {"password": PASSWORD})[0] == 200
    finally:
        _stop(proc)
    text = log.read_text()
    assert "token=" not in text.replace("token=[redacted]", ""), text[-2000:]
    assert "token=[redacted]" in text  # the ?token= request above was logged, scrubbed
    assert f"{network_address}" in text or "0.0.0.0" in text


@pytest.mark.usefixtures("_clean")
def test_without_the_switch_the_network_cannot_connect(tmp_path, network_address):
    proc, port, _log = _start(tmp_path, {})
    try:
        assert _Http("127.0.0.1", port).call("GET", "/health")[0] == 200
        with pytest.raises(OSError):
            _Http(network_address, port).call("GET", "/health")
    finally:
        _stop(proc)


@pytest.mark.usefixtures("_clean")
@pytest.mark.skipif(not netbind.dual_stack(), reason="this machine has no dual-stack IPv6 (the sandbox has no IPv6 at all)")
def test_lan_mode_answers_on_ipv6_and_ipv4_from_one_server(tmp_path):
    """The plan's own test: the real launcher with LAN mode on, reached once
    over `[::1]` and once over IPv4, the same server both times."""
    # No password yet means loopback only (SEC-01): set one, then restart.
    proc, port, log = _start(tmp_path, {netbind.LAN_PREF: True})
    try:
        assert _Http("127.0.0.1", port).call("POST", "/auth/setup", {"password": PASSWORD})[0] == 200
    finally:
        _stop(proc)
    #: The port opens only on a network the person allowed (core/lantrust.py):
    #: this test is about the sockets, so every network is allowed here.
    (tmp_path / "data" / lantrust.FILE_NAME).write_text(json.dumps({"any_network": True, "ask_new_devices": False}))
    proc, port, log = _start(tmp_path, {netbind.LAN_PREF: True})
    try:
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                socket.create_connection(("::1", _lan_port(port)), timeout=0.5).close()
                break
            except OSError:
                time.sleep(0.3)
        # The dual-stack socket is the HTTPS one (loopback http is 127.0.0.1).
        cert = tmp_path / "data" / "lan-tls" / "cert.pem"
        here_v6 = _Http("::1", _lan_port(port), cafile=cert)
        here_v4 = _Http("127.0.0.1", _lan_port(port), cafile=cert)
        status, body, _ = here_v6.call("GET", "/auth/status", host=f"[::1]:{_lan_port(port)}")
        assert status == 200 and body["setup_required"] is False
        status, body, _ = here_v4.call("POST", "/auth/unlock", {"password": PASSWORD})
        assert status == 200
        owner = {"X-Auth-Token": body["token"]}
        # Both arrive on loopback: [::1] is, and 127.0.0.1 arrives as
        # ::ffff:127.0.0.1, which the guard reads as loopback too.
        assert here_v6.call("POST", "/auth/auto-session", host=f"[::1]:{_lan_port(port)}")[0] in (200, 403)
        status, receipt, _ = here_v6.call(
            "GET", "/privacy/receipt", headers=owner, host=f"[::1]:{_lan_port(port)}"
        )
        assert status == 200
        assert receipt["listening"]["other_devices"] is True
        assert receipt["listening"]["host"] == "::"
    finally:
        _stop(proc)
    assert "token=" not in log.read_text().replace("token=[redacted]", "")


# --- SEC-01: a reset never leaves an open notebook on the network --------------------


def _lan(client) -> TestClient:
    """A request that arrived on a network address, as a phone's would: the
    ASGI scope's `server` is taken from the base URL."""
    return TestClient(client.app, base_url="http://192.168.1.9:8795", client=("192.168.1.50", 50000))


@pytest.mark.usefixtures("_clean")
def test_no_password_means_loopback_whatever_the_switch_says(app_state):
    """SEC-01 (audit 2026-10-05): `--reset-password` deletes the user row and
    the next launch bound 0.0.0.0 with nothing to ask for."""
    app_state.set_preference(netbind.LAN_PREF, True)
    assert netbind.bind_host(app_state, has_password=False) == "127.0.0.1"
    assert netbind.bind_host(app_state, has_password=True) != "127.0.0.1"


@pytest.mark.usefixtures("_clean")
def test_reset_password_turns_lan_mode_off(app_state, monkeypatch, capsys):
    from tessellate import __main__ as launcher
    from tessellate.core import deps
    from tessellate.core.database import User

    with deps.get_db().session() as session:
        session.add(User(username="owner", password_hash="x"))
        session.commit()
    app_state.set_preference(netbind.LAN_PREF, True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "RESET")
    assert launcher._reset_password() == 0
    assert netbind.lan_enabled(app_state) is False
    assert "other devices" in capsys.readouterr().out.lower()


@pytest.mark.usefixtures("_clean")
def test_without_a_password_the_network_gets_nothing(client):
    """Even on a server bound to the network some other way (uvicorn
    --host 0.0.0.0, a container), a request that arrives off loopback before
    a password exists is refused: no notes, no status, no claiming the
    notebook with /auth/setup."""
    lan = _lan(client)
    for method, path, body in (
        ("GET", "/entries?limit=5", None),
        ("GET", "/auth/status", None),
        ("POST", "/auth/setup", {"password": PASSWORD}),
        ("GET", "/health", None),
        ("GET", "/", None),
    ):
        response = lan.request(method, path, json=body)
        assert response.status_code == 403, (path, response.status_code)
    # This computer is still served, and once a password exists the network
    # gets the ordinary lock screen.
    assert _local(client).get("/auth/status").json()["setup_required"] is True
    _setup(client)
    assert lan.get("/auth/status").status_code == 200
    assert lan.get("/entries?limit=5").status_code == 401



@pytest.mark.usefixtures("_clean")
def test_a_second_notebook_on_this_computer_takes_the_next_lan_port(monkeypatch):
    """The owner, 2026-10-11: "what if multiple people are running memory map
    and want to connect over the same lan connection??" Two accounts on one
    computer: the second used to go local-only when 8443 was held."""

    monkeypatch.delenv("TESSELLATE_LAN_PORT", raising=False)
    assert netbind.lan_port_candidates(8443)[:3] == [8443, 8444, 8445]
    assert len(netbind.lan_port_candidates(8443)) == netbind.LAN_PORT_TRIES
    monkeypatch.setenv("TESSELLATE_LAN_PORT", "9000")
    assert netbind.lan_port_candidates(9000) == [9000]


# One row per network in the trusted lists: a less complete reading of the same router is the same network.


FULL = netid.Network("192.168.0.1", "aa:bb:cc:dd:ee:01", "192.168.0.0/24", category="private", name="Telstra140043")
BARE = netid.Network("192.168.0.1", "aa:bb:cc:dd:ee:01")
OTHER_ROUTER = netid.Network("192.168.0.1", "11:22:33:44:55:66", "192.168.0.0/24")


def _row_state(**over):
    state = lantrust.load(Path("/nonexistent-phone-lanfix"))
    state.update(over)
    return state


def test_a_less_complete_reading_of_the_same_router_is_the_same_network():
    assert FULL.key != BARE.key and FULL.router == BARE.router
    assert OTHER_ROUTER.router != FULL.router
    trusted = _row_state(networks=[lantrust._entry(FULL)])
    assert lantrust.evaluate(trusted, BARE) == (True, "allowed")
    # Another router at the same address is still another network.
    assert lantrust.evaluate(trusted, OTHER_ROUTER) == (False, "new_network")
    blocked = _row_state(any_network=True, untrusted=[{**lantrust._entry(BARE), "blocked": True}])
    assert lantrust.evaluate(blocked, FULL) == (False, "untrusted_network")


def test_trusting_twice_through_both_readings_keeps_one_record(tmp_path):
    lantrust.reset_for_tests()
    state = lantrust.load(tmp_path)
    lantrust._remember(state, BARE)
    lantrust._remember(state, FULL)
    lantrust._remember(state, BARE)
    assert [(n["key"], n["label"], n["subnet"]) for n in state["networks"]] == [
        (FULL.key, "Telstra140043", "192.168.0.0/24")
    ]
    lantrust.reset_for_tests()


def test_old_duplicates_show_as_one_row_named_by_the_wifi_name():
    old = [
        {"key": BARE.key, "label": "the network with router 192.168.0.1", "gateway": "192.168.0.1", "subnet": "", "added": "2026-10-12 01:15"},
        {"key": FULL.key, "label": "Telstra140043", "gateway": "192.168.0.1", "subnet": "192.168.0.0/24", "added": "2026-10-12 01:15"},
    ]
    rows = lantrust.listed(old)
    assert len(rows) == 1
    row = rows[0]
    assert row["label"] == "Telstra140043" and row["subnet"] == "192.168.0.0/24"
    assert sorted(row["keys"]) == sorted([BARE.key, FULL.key]) and row["key"] == FULL.key
    # The key the computer is on now is the row's key, so "(this network)" finds it.
    assert lantrust.listed(old, here=BARE.key)[0]["key"] == BARE.key
    # Two routers with their subnets read are two rows.
    two = [lantrust._entry(FULL), lantrust._entry(OTHER_ROUTER)]
    assert len(lantrust.listed(two)) == 2


def test_stop_trusting_and_forget_take_every_record_of_the_network(tmp_path):
    lantrust.reset_for_tests()
    old = [
        {"key": BARE.key, "label": "the network with router 192.168.0.1", "gateway": "192.168.0.1", "subnet": "", "added": "x"},
        {"key": FULL.key, "label": "Telstra140043", "gateway": "192.168.0.1", "subnet": "192.168.0.0/24", "added": "x"},
    ]
    lantrust.save(tmp_path, _row_state(networks=old))
    assert lantrust.untrust_network(tmp_path, FULL.key)
    state = lantrust.load(tmp_path)
    assert state["networks"] == []
    assert sorted(n["key"] for n in state["untrusted"]) == sorted([BARE.key, FULL.key])
    assert all(n["blocked"] for n in state["untrusted"])
    assert len(lantrust.listed(state["untrusted"])) == 1
    assert lantrust.forget_network(tmp_path, BARE.key)
    assert lantrust.load(tmp_path)["untrusted"] == []
    lantrust.reset_for_tests()


def test_trust_takes_only_records_known_to_be_the_same_router(tmp_path):
    lantrust.reset_for_tests()
    legacy = {"key": BARE.key, "label": "the network with router 192.168.0.1", "gateway": "192.168.0.1", "subnet": "", "added": "x", "blocked": False}
    full = {**lantrust._entry(FULL), "blocked": False}
    lantrust.save(tmp_path, _row_state(untrusted=[legacy, full]))
    assert lantrust.trust_network(tmp_path, FULL.key)
    state = lantrust.load(tmp_path)
    # The legacy record has no router to compare: it is not trusted with it.
    assert [n["key"] for n in state["networks"]] == [FULL.key]
    assert [n["key"] for n in state["untrusted"]] == [BARE.key]
    lantrust.reset_for_tests()


def test_the_panel_lists_one_row_and_a_phone_still_cannot_touch_it(lan_app):  # noqa: F811
    from tessellate.core import deps

    data_dir = deps.get_config().data_dir
    here, phone = _here(lan_app), _phone(lan_app)
    old = [
        {"key": BARE.key, "label": "the network with router 192.168.0.1", "gateway": "192.168.0.1", "subnet": "", "added": "2026-10-12 01:15"},
        {"key": FULL.key, "label": "Telstra140043", "gateway": "192.168.0.1", "subnet": "192.168.0.0/24", "added": "2026-10-12 01:15"},
    ]
    lantrust.save(data_dir, {**lantrust.load(data_dir), "networks": old})
    state = here.get("/auth/lan-access").json()
    assert [(n["label"], n["subnet"]) for n in state["networks"]] == [("Telstra140043", "192.168.0.0/24")]
    for method, path in (("post", f"/auth/lan-networks/{FULL.key}/untrust"), ("delete", f"/auth/lan-networks/{FULL.key}"),
                         ("post", f"/auth/lan-networks/{BARE.key}/untrust"), ("delete", f"/auth/lan-networks/{BARE.key}")):
        refused = getattr(phone, method)(path)
        assert refused.status_code == 403 and refused.json()["detail"] == REFUSAL, path
    assert len(lantrust.load(data_dir)["networks"]) == 2
    state = here.post(f"/auth/lan-networks/{FULL.key}/untrust").json()
    assert state["networks"] == [] and len(state["untrusted"]) == 1
    gone = here.delete(f"/auth/lan-networks/{FULL.key}")
    assert gone.json()["untrusted"] == []
    _ = PASSWORD


def test_the_rows_keep_their_actions_on_screen_and_start_with_a_capital():
    root = Path(__file__).resolve().parents[1]
    js = (root / "frontend/js/settings-controls.js").read_text(encoding="utf-8")
    body = js[js.index("function lanListRow("):js.index("function lanEmptyRow(")]
    assert "lan-network-row" in body
    rows = js[js.index("function lanNetworkRows("):js.index("async function lanTrustNetwork(")]
    assert "toUpperCase()" in rows
    css = (root / "frontend/css/lan-lazy.css").read_text(encoding="utf-8")
    assert ".entry-list li.lan-network-row .entry-actions" in css


# The LAN switch offers a Restart action instead of only telling you to.


def _function(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    return source[start : source.index("\n}\n", start)]


def test_restart_memory_map_is_defined_once():
    app = app_js_text()
    assert app.count("async function restartMemoryMap(") == 1
    body = _function(app, "restartMemoryMap")
    assert '"/system/restart"' in body
    assert "confirmDialog(" in body


def test_the_about_button_reuses_it_rather_than_a_second_copy():
    app = app_js_text()
    assert '$("about-restart")?.addEventListener("click", () => restartMemoryMap());' in app
    # The old inline copy of the same "ask, restart, or say why not" logic
    # must actually be gone, not just duplicated alongside the shared one.
    assert app.count('apiJson("/system/restart"') == 1


def test_disabling_lan_offers_restart_when_the_bind_has_not_dropped_yet():
    app = app_js_text()
    handler_start = app.index('$("account-allow-lan")?.addEventListener("change"')
    handler = app[handler_start : handler_start + 2200]
    assert "off.restart_required" in handler
    assert 'toastAction("Restart to close the app to other devices now."' in handler
    assert "restartMemoryMap({ confirm: false })" in handler


def test_enabling_lan_offers_restart_when_one_is_needed():
    app = app_js_text()
    handler_start = app.index('$("account-allow-lan")?.addEventListener("change"')
    handler = app[handler_start : handler_start + 2200]
    assert "reply.restart_required" in handler
    assert 'toastAction("Other devices can open the app after a restart."' in handler


def test_toast_action_is_the_recipe_used_not_a_bespoke_banner():
    """DESIGN.md's recipe index: "a brief confirmation... with one action,
    toastAction(text, label, fn)". No new banner element for this."""
    app = app_js_text()
    handler_start = app.index('$("account-allow-lan")?.addEventListener("change"')
    handler = app[handler_start : handler_start + 2200]
    assert handler.count("toastAction(") == 2


# The LAN port answers plain http with a redirect, and TLS with the app (real sockets, certificate checked by OpenSSL).


async def _app(scope, receive, send):  # noqa: ANN001
    assert scope["type"] == "http"
    body = f"{scope['scheme']} {scope['path']}".encode()
    await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
    await send({"type": "http.response.body", "body": body})


class _Quiet(uvicorn.Server):
    def capture_signals(self):  # noqa: ANN202
        return contextlib.nullcontext()


@pytest.fixture()
def lan(tmp_path):
    info = lancert.ensure(tmp_path, ["localhost", "127.0.0.1"])
    config = uvicorn.Config(
        _app, lifespan="off", log_level="warning",
        ssl_certfile=str(info.cert_path), ssl_keyfile=str(info.key_path),
    )
    config.load()
    server = _Quiet(config)
    sock = socket.create_server(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    thread = threading.Thread(target=lambda: asyncio.run(lanserve.serve(server, sock)), daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    yield port, tmp_path
    server.should_exit = True
    thread.join(10)
    assert not thread.is_alive(), "the LAN listener did not stop"


def _plain(port, host):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.putrequest("GET", "/notes?x=1", skip_host=True)
    conn.putheader("Host", host)
    conn.endheaders()
    response = conn.getresponse()
    conn.close()
    return response


def test_https_reaches_the_app_with_a_certificate_the_authority_vouches_for(lan):
    port, data_dir = lan
    context = ssl.create_default_context(cadata=lancert.authority_pem(data_dir).decode())
    conn = http.client.HTTPSConnection("127.0.0.1", port, context=context, timeout=5)
    conn.request("GET", "/hello")
    response = conn.getresponse()
    assert response.status == 200 and response.read() == b"https /hello"
    conn.close()


def test_silent_connections_do_not_hold_up_the_page(lan):
    """Safari opens connections ahead of need and sends nothing on them
    (the owner, 2026-10-11: "it still hasnt loaded"). Twenty of them must
    not make a real request wait."""
    port, data_dir = lan
    silent = [socket.create_connection(("127.0.0.1", port)) for _ in range(20)]
    try:
        time.sleep(0.2)
        context = ssl.create_default_context(cadata=lancert.authority_pem(data_dir).decode())
        started = time.monotonic()
        conn = http.client.HTTPSConnection("127.0.0.1", port, context=context, timeout=5)
        conn.request("GET", "/hello")
        assert conn.getresponse().status == 200
        conn.close()
        assert time.monotonic() - started < 2
    finally:
        for s in silent:
            s.close()


def test_plain_http_is_sent_to_https_on_the_same_address(lan):
    port, _ = lan
    response = _plain(port, f"127.0.0.1:{port}")
    assert response.status == 301
    assert response.getheader("Location") == f"https://127.0.0.1:{port}/notes?x=1"


def test_a_host_that_is_not_this_computer_is_not_redirected(lan):
    """Never an open redirect: a rebinding page's Host gets a 400."""
    port, _ = lan
    response = _plain(port, "evil.example")
    assert response.status == 400 and response.getheader("Location") is None


def test_a_redirect_never_leaves_this_computer():
    assert b"Location: https://127.0.0.1:8443/\r\n" in lanserve.redirect_response(
        b"GET //evil.example/x HTTP/1.1\r\nHost: 127.0.0.1:8443\r\n\r\n", 8443
    )
    assert b"Location: https://[::1]:8443/a\r\n" in lanserve.redirect_response(
        b"GET /a HTTP/1.1\r\nHost: [::1]:8443\r\n\r\n", 8443
    )
    assert b"301" not in lanserve.redirect_response(b"GET / HTTP/1.1\r\nHost: a\r\nb.example\r\n\r\n", 8443)


# --- INBOX 867: clients from private addresses only ----------------------------


@pytest.mark.parametrize(
    "address",
    [
        "192.168.1.50", "10.0.0.7", "172.16.4.2", "172.31.255.1", "100.64.0.9", "169.254.10.1",
        "127.0.0.1", "::1", "fd12:3456::1", "fe80::1", "::ffff:192.168.1.50", "fe80::1%eth0",
    ],
)
def test_a_client_on_this_network_is_let_through(address):
    assert lanserve.client_allowed(address)


@pytest.mark.parametrize(
    "address",
    ["8.8.8.8", "172.32.0.1", "100.128.0.1", "2001:4860::8888", "::ffff:8.8.8.8", "", "garbage", None],
)
def test_a_client_from_a_public_address_is_refused(address):
    """A forwarded port, or a network that hands out public addresses: the
    notebook is for the devices beside it. An address that cannot be read is
    refused too, never let through."""
    assert not lanserve.client_allowed(address)


def test_a_global_ipv6_client_is_let_in_only_from_this_networks_prefix():
    """The owner's machine has global 2001:8003:... addresses; an iPhone on
    the same Wi-Fi connects from the same /64. Another /64 is the internet."""
    ours = lanserve.own_v6_prefixes(["192.168.0.107", "2001:8003:1:2:aaaa::3ef2", "fe80::1", "[2001:8003:1:2::87db]"])
    assert len(ours) == 1
    assert lanserve.client_allowed("2001:8003:1:2:1234:5678:9abc:def0", ours)
    assert not lanserve.client_allowed("2001:8003:1:3::1", ours)
    assert not lanserve.client_allowed("2001:4860::8888", ours)
    assert not lanserve.client_allowed("2001:8003:1:2::5", frozenset())


def test_this_computers_own_address_is_let_in_whatever_its_range(monkeypatch):
    monkeypatch.setattr(lanserve.netbind, "lan_addresses", lambda include_v6=None: ["192.0.2.2"])
    lanserve.refresh_own_prefixes()
    try:
        assert lanserve.client_allowed("192.0.2.2")
        assert not lanserve.client_allowed("192.0.2.3")
    finally:
        monkeypatch.undo()
        lanserve.refresh_own_prefixes()


def test_a_refused_client_is_closed_before_any_handshake(lan, monkeypatch):
    """On a real socket: the connection is closed before TLS starts, so the
    client learns nothing, not even the certificate."""
    port, data_dir = lan
    monkeypatch.setattr(lanserve, "client_allowed", lambda address: False)
    context = ssl.create_default_context(cadata=lancert.authority_pem(data_dir).decode())
    with pytest.raises((ssl.SSLError, ConnectionError, OSError)):
        conn = http.client.HTTPSConnection("127.0.0.1", port, context=context, timeout=5)
        conn.request("GET", "/hello")
        conn.getresponse()
    with socket.create_connection(("127.0.0.1", port), timeout=5) as raw:
        # Closed unread: an empty read, or a reset when the request beat the close.
        try:
            raw.sendall(b"GET / HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
            assert raw.recv(100) == b""
        except ConnectionError:
            pass  # a reset: the request beat the close, which is the same refusal


def test_the_gate_closes_and_reopens_the_port(tmp_path):
    """INBOX 867: on a network nobody allowed, the LAN port is not bound at
    all; "Allow on this network" binds it within a second, and a move to
    another network closes it again. Real sockets throughout."""
    info = lancert.ensure(tmp_path, ["localhost", "127.0.0.1"])
    config = uvicorn.Config(
        _app, lifespan="off", log_level="warning",
        ssl_certfile=str(info.cert_path), ssl_keyfile=str(info.key_path),
    )
    config.load()
    server = _Quiet(config)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    allowed = {"open": False}
    thread = threading.Thread(
        target=lambda: asyncio.run(
            lanserve.serve(
                server, None, port=port, gate=lambda: allowed["open"],
                reopen=lambda: socket.create_server(("127.0.0.1", port)),
            )
        ),
        daemon=True,
    )
    thread.start()

    def answers() -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            return False

    def settles(want: bool) -> bool:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if answers() == want:
                return True
            time.sleep(0.1)
        return False

    try:
        time.sleep(1.0)
        assert not answers()
        allowed["open"] = True
        assert settles(True)
        allowed["open"] = False
        assert settles(False)
    finally:
        server.should_exit = True
        thread.join(10)
    assert not thread.is_alive()


# LAN mode over HTTPS with a certificate made on this computer (the end-to-end test against the real launcher is the mode block above). The _no_live_listener reset is applied to these tests only.


NAMES = ["localhost", "127.0.0.1", "::1", "studio", "studio.local", "192.168.1.9", "2001:db8::5"]


def _cert(info):
    return x509.load_pem_x509_certificate(info.cert_path.read_bytes())


@pytest.mark.usefixtures("_no_live_listener")
def test_made_once_and_reused(tmp_path):
    first = lancert.ensure(tmp_path, NAMES)
    key_bytes = first.key_path.read_bytes()
    second = lancert.ensure(tmp_path, NAMES)
    assert second.fingerprint == first.fingerprint
    assert second.key_path.read_bytes() == key_bytes


@pytest.mark.usefixtures("_no_live_listener")
def test_names_this_computer_and_its_lan_addresses(tmp_path):
    info = lancert.ensure(tmp_path, NAMES)
    san = _cert(info).extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    dns = set(san.get_values_for_type(x509.DNSName))
    ips = {str(ip) for ip in san.get_values_for_type(x509.IPAddress)}
    assert {"localhost", "studio", "studio.local"} <= dns
    assert {"127.0.0.1", "::1", "192.168.1.9", "2001:db8::5"} <= ips
    # Addresses go in as IP entries, never as names a browser would not match.
    assert not any(_is_ip(name) for name in dns)


def _is_ip(text):
    try:
        ipaddress.ip_address(text)
    except ValueError:
        return False
    return True


@pytest.mark.usefixtures("_no_live_listener")
def test_the_default_names_are_the_host_name_and_the_listed_addresses(monkeypatch):
    monkeypatch.setattr(lancert.socket, "gethostname", lambda: "Studio.lan")
    monkeypatch.setattr(netbind, "lan_addresses", lambda include_v6=None: ["10.0.0.7", "fd00::7"])
    names = lancert.default_names()
    for expected in ("studio.lan", "studio", "studio.local", "10.0.0.7", "fd00::7", "localhost"):
        assert expected in names


@pytest.mark.usefixtures("_no_live_listener")
@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
def test_the_key_and_certificate_are_private(tmp_path):
    info = lancert.ensure(tmp_path, NAMES)
    for path in (info.cert_path, info.key_path):
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600, path
    assert stat.S_IMODE(os.stat(info.key_path.parent).st_mode) == 0o700


@pytest.mark.usefixtures("_no_live_listener")
def test_a_server_certificate_a_phone_accepts(tmp_path):
    cert = _cert(lancert.ensure(tmp_path, NAMES))
    eku = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    assert x509.oid.ExtendedKeyUsageOID.SERVER_AUTH in eku
    assert cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca is False
    life = cert.not_valid_after_utc - cert.not_valid_before_utc
    assert life <= dt.timedelta(days=826)


@pytest.mark.usefixtures("_no_live_listener")
def test_regenerate_makes_a_new_one(tmp_path):
    first = lancert.ensure(tmp_path, NAMES)
    second = lancert.generate(tmp_path, NAMES)
    assert second.fingerprint != first.fingerprint
    assert lancert.ensure(tmp_path, NAMES).fingerprint == second.fingerprint


@pytest.mark.usefixtures("_no_live_listener")
def test_an_unreadable_one_is_replaced(tmp_path):
    info = lancert.ensure(tmp_path, NAMES)
    info.cert_path.write_text("not a certificate")
    assert lancert.ensure(tmp_path, NAMES).fingerprint != info.fingerprint


@pytest.mark.usefixtures("_no_live_listener")
def test_one_close_to_expiring_is_replaced(tmp_path, monkeypatch):
    info = lancert.ensure(tmp_path, NAMES)
    later = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=lancert.VALID_DAYS - 10)
    monkeypatch.setattr(lancert, "_now", lambda: later)
    assert lancert.ensure(tmp_path, NAMES).fingerprint != info.fingerprint


@pytest.mark.usefixtures("_no_live_listener")
def test_the_fingerprint_is_sha256_in_pairs(tmp_path):
    info = lancert.ensure(tmp_path, NAMES)
    parts = info.fingerprint.split(":")
    assert len(parts) == 32 and all(len(p) == 2 for p in parts)
    assert info.public().keys() == {"fingerprint", "authority_fingerprint", "expires", "names"}


# --- The authority a phone trusts (INBOX 866) -------------------------------------


def _authority(tmp_path):
    return x509.load_pem_x509_certificate(lancert.authority_pem(tmp_path))


@pytest.mark.usefixtures("_no_live_listener")
def test_the_server_certificate_is_signed_by_an_authority_a_phone_can_install(tmp_path):
    """iOS lists only authorities under Certificate Trust Settings, Android
    installs only those as a CA certificate, and Firefox refuses an authority
    used as a server certificate: so two certificates, not one."""
    info = lancert.ensure(tmp_path, NAMES)
    ca = _authority(tmp_path)
    basic = ca.extensions.get_extension_for_class(x509.BasicConstraints).value
    assert basic.ca is True and basic.path_length == 0
    assert ca.extensions.get_extension_for_class(x509.KeyUsage).value.key_cert_sign
    leaf = _cert(info)
    assert leaf.issuer == ca.subject != leaf.subject
    leaf.verify_directly_issued_by(ca)
    assert info.authority_fingerprint == lancert._fingerprint(ca) != info.fingerprint
    # The chain the server sends: the server certificate, then the authority.
    chain = x509.load_pem_x509_certificates(info.cert_path.read_bytes())
    assert [c.subject for c in chain] == [leaf.subject, ca.subject]


@pytest.mark.usefixtures("_no_live_listener")
def test_the_authority_vouches_only_for_this_network(tmp_path):
    """A stolen authority key must not let anyone pose as a bank to a phone
    that trusted it: its name constraints keep it to private addresses,
    `.local` and this computer's own names."""
    lancert.ensure(tmp_path, NAMES)
    ca = _authority(tmp_path)
    ext = ca.extensions.get_extension_for_class(x509.NameConstraints)
    assert ext.critical
    assert lancert._covers(ca, ["192.168.7.20", "10.1.2.3", "studio", "notes.local", "fd00::9"])
    assert not lancert._covers(ca, ["bank.example"])
    assert not lancert._covers(ca, ["8.8.8.8"])
    for path in lancert.authority_paths(tmp_path):
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600, path


@pytest.mark.usefixtures("_no_live_listener")
def test_a_reused_authority_key_is_made_private_again(tmp_path):
    """lansec-1025: `ensure` re-tightened the server key on every start but
    not the authority's key or the folder, so a copy loosened by a restore,
    a sync tool or an older build stayed readable while it was reused."""
    lancert.ensure(tmp_path, NAMES)
    folder = lancert.paths(tmp_path)[0].parent
    _ca, ca_key = lancert.authority_paths(tmp_path)
    os.chmod(ca_key, 0o640)
    os.chmod(folder, 0o750)
    lancert.ensure(tmp_path, NAMES)
    assert stat.S_IMODE(os.stat(ca_key).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(folder).st_mode) == 0o700


@pytest.mark.usefixtures("_no_live_listener")
def test_a_new_private_address_keeps_the_authority_the_phone_trusts(tmp_path):
    first = lancert.ensure(tmp_path, ["localhost", "192.168.1.9"])
    second = lancert.ensure(tmp_path, ["localhost", "192.168.1.9", "192.168.1.77"])
    assert second.fingerprint != first.fingerprint
    assert second.authority_fingerprint == first.authority_fingerprint


@pytest.mark.usefixtures("_no_live_listener")
def test_a_public_address_gets_an_authority_that_covers_it(tmp_path):
    first = lancert.ensure(tmp_path, ["localhost", "192.168.1.9"])
    second = lancert.ensure(tmp_path, ["localhost", "192.168.1.9", "203.0.113.5"])
    assert second.authority_fingerprint != first.authority_fingerprint
    assert lancert._covers(_authority(tmp_path), ["203.0.113.5"])
    assert not lancert._covers(_authority(tmp_path), ["203.0.113.6"])


@pytest.mark.usefixtures("_no_live_listener")
def test_a_global_ipv6_address_is_covered_by_its_64(tmp_path):
    """Windows rotates a privacy IPv6 address inside the same /64 daily; a
    /128 would make a new authority (and a phone reinstall) every day."""
    lancert.ensure(tmp_path, ["localhost", "2001:db8:6355:b600::17"])
    assert lancert._covers(_authority(tmp_path), ["2001:db8:6355:b600:abcd::9"])
    assert not lancert._covers(_authority(tmp_path), ["2001:db8:6355:b601::9"])


@pytest.mark.usefixtures("_no_live_listener")
def test_a_self_signed_certificate_from_before_is_replaced_by_the_pair(tmp_path):
    info = lancert.ensure(tmp_path, NAMES)
    for path in lancert.authority_paths(tmp_path):
        path.unlink()
    again = lancert.ensure(tmp_path, NAMES)
    assert again.fingerprint != info.fingerprint and again.authority_fingerprint


@pytest.mark.usefixtures("_no_live_listener")
def test_regenerate_makes_a_new_authority_too(tmp_path):
    first = lancert.ensure(tmp_path, NAMES)
    assert lancert.generate(tmp_path, NAMES).authority_fingerprint != first.authority_fingerprint


# --- The routes Settings uses ----------------------------------------------------


@pytest.fixture()
def owner(client):
    token = client.post("/auth/setup", json={"password": PASSWORD}).json()["token"]
    return {"X-Auth-Token": token}


@pytest.fixture()
def _no_live_listener():
    netbind.set_lan_port(None)
    lancert.set_live_context(None)
    yield
    netbind.set_lan_port(None)
    lancert.set_live_context(None)


@pytest.mark.usefixtures("_no_live_listener")
def test_settings_shows_the_fingerprint_once_lan_mode_is_on(client, app_state, owner):
    body = client.get("/auth/lan-access", headers=owner).json()
    assert body["certificate"] is None
    lancert.ensure(app_state.data_dir, NAMES)
    body = client.get("/auth/lan-access", headers=owner).json()
    assert body["certificate"]["fingerprint"] == lancert.read(app_state.data_dir).fingerprint


@pytest.mark.usefixtures("_no_live_listener")
def test_turning_it_on_makes_the_certificate(client, app_state, owner):
    reply = client.post(
        "/auth/lan-access", json={"enabled": True, "current_password": PASSWORD}, headers=owner
    )
    assert reply.status_code == 200, reply.text
    assert reply.json()["certificate"]["fingerprint"]
    assert lancert.read(app_state.data_dir) is not None


@pytest.mark.usefixtures("_no_live_listener")
def test_regenerate_from_settings(client, app_state, owner):
    first = lancert.ensure(app_state.data_dir, NAMES)
    assert client.post("/auth/lan-certificate").status_code == 401
    reply = client.post("/auth/lan-certificate", headers=owner)
    assert reply.status_code == 200, reply.text
    assert reply.json()["certificate"]["fingerprint"] != first.fingerprint


@pytest.mark.usefixtures("_no_live_listener")
def test_the_addresses_are_https_on_the_lan_port(app_state, monkeypatch):
    monkeypatch.setattr(netbind, "lan_addresses", lambda include_v6=None: ["192.168.1.9"])
    app_state.set_preference(netbind.LAN_PREF, True)
    described = netbind.describe(app_state, 8000)
    assert described["addresses"] == [f"https://192.168.1.9:{netbind.lan_port(8000)}"]
    assert netbind.lan_port(8000) == 8443


@pytest.mark.usefixtures("_no_live_listener")
def test_regenerate_reaches_the_running_listener(tmp_path):
    """The live TLS context takes the new certificate: no restart needed."""

    first = lancert.ensure(tmp_path, NAMES)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(first.cert_path), str(first.key_path))
    lancert.set_live_context(context)
    calls = []
    real = context.load_cert_chain

    class _Spy:
        def load_cert_chain(self, cert, key):
            calls.append(cert)
            return real(cert, key)

    lancert.set_live_context(_Spy())
    assert lancert.reload(lancert.generate(tmp_path, NAMES)) is True
    assert calls == [str(first.cert_path)]


@pytest.mark.usefixtures("_no_live_listener")
def test_new_address_makes_a_new_certificate(tmp_path, caplog):
    """After a DHCP change the phone must not meet a certificate without the address."""
    first = lancert.ensure(tmp_path, ["localhost", "192.168.1.9"])
    with caplog.at_level("INFO", logger="tessellate.core.lancert"):
        second = lancert.ensure(tmp_path, ["localhost", "192.168.1.9", "192.168.1.77"])
    assert second.fingerprint != first.fingerprint
    assert "192.168.1.77" in second.names
    assert any("made again" in r.message for r in caplog.records)
    # Same list again: reused, no churn.
    assert lancert.ensure(tmp_path, ["localhost", "192.168.1.77"]).fingerprint == second.fingerprint


@pytest.mark.usefixtures("_no_live_listener")
def test_certificate_download_is_the_authority_only(client, app_state):
    info = lancert.ensure(app_state.data_dir, NAMES)
    r = client.get("/auth/lan-certificate.pem")
    assert r.status_code == 200
    assert b"PRIVATE KEY" not in r.content and r.content.count(b"BEGIN CERTIFICATE") == 1
    assert lancert._fingerprint(x509.load_pem_x509_certificate(r.content)) == info.authority_fingerprint
    assert "attachment" in r.headers["content-disposition"]


@pytest.mark.usefixtures("_no_live_listener")
def test_certificate_download_works_by_plain_navigation(client, app_state, owner):
    """The phone installs it by opening the link (iOS installs a profile only
    from a navigation, never from a script's download), and a navigation
    carries no X-Auth-Token: so no unlock is asked. The authority's
    certificate is public; every TLS handshake already sends it."""
    lancert.ensure(app_state.data_dir, NAMES)
    assert client.get("/entries").status_code == 401  # locked: the header is what unlocks
    r = client.get("/auth/lan-certificate.pem")
    assert r.status_code == 200 and b"BEGIN CERTIFICATE" in r.content


# LAN mode safe on any network: which network, which devices (core/netid.py reads, core/lantrust.py decides, every failure reads as closed).


ROUTE = (
    "Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT\n"
    "wlan0\t00000000\t0100A8C0\t0003\t0\t0\t600\t00000000\t0\t0\t0\n"
    "eth9\t00000000\t0101A8C0\t0003\t0\t0\t900\t00000000\t0\t0\t0\n"
    "wlan0\t0000A8C0\t00000000\t0001\t0\t0\t600\t00FFFFFF\t0\t0\t0\n"
)
ARP = (
    "IP address       HW type     Flags       HW address            Mask     Device\n"
    "192.168.0.1      0x1         0x2         AA:BB:cc:dd:ee:01     *        wlan0\n"
)
PUBLIC = netid.Network("10.0.0.1", "aa:aa:aa:aa:aa:aa", "10.0.0.0/24", category="public", name="Airport")


# --- reading the network -------------------------------------------------------


def test_linux_reads_the_default_route_and_the_routers_hardware_address(tmp_path):
    (tmp_path / "route").write_text(ROUTE)
    (tmp_path / "arp").write_text(ARP)
    found = netid.read_linux(tmp_path)
    assert (found.gateway, found.gateway_mac, found.subnet) == ("192.168.0.1", "aa:bb:cc:dd:ee:01", "192.168.0.0/24")


def test_linux_without_the_routers_hardware_address_is_an_unknown_network(tmp_path):
    (tmp_path / "route").write_text(ROUTE)
    (tmp_path / "arp").write_text(ARP.splitlines()[0] + "\n192.168.0.1 0x1 0x0 00:00:00:00:00:00 * wlan0\n")
    assert netid.read_linux(tmp_path) is None
    assert netid.read_linux(tmp_path / "missing") is None


def test_the_same_router_address_on_another_router_is_another_network():
    assert HOME.key != CAFE.key
    assert HOME.key == netid.Network("192.168.0.1", "aa:bb:cc:dd:ee:01", "192.168.0.0/24").key


def test_macos_and_windows_outputs_parse():
    assert netid.parse_route_get("   route to: default\n    gateway: 192.168.1.1\n  interface: en0\n") == (
        "192.168.1.1", "en0",
    )
    assert netid.normal_mac("? (192.168.1.1) at a:b:c:d:e:f on en0 ifscope [ethernet]") == "0a:0b:0c:0d:0e:0f"
    assert netid.normal_mac("  192.168.1.1   aa-bb-cc-dd-ee-ff   dynamic") == "aa:bb:cc:dd:ee:ff"
    found = netid.parse_windows_json(
        '{"gateway":"192.168.0.1","address":"192.168.0.107","prefix":24,"category":"Public",'
        '"name":"Cafe WiFi","mac":"AA-BB-CC-DD-EE-01","virtual":["192.168.56.1"]}'
    )
    assert found.category == "public" and found.name == "Cafe WiFi" and found.subnet == "192.168.0.0/24"
    assert found.virtual == ("192.168.56.1",) and found.address == "192.168.0.107"
    assert netid.parse_windows_json("") is None and netid.parse_windows_json('{"gateway":"x"}') is None
    route = "  0.0.0.0          0.0.0.0      192.168.0.1    192.168.0.107     35\n"
    assert netid.parse_route_print(route) == "192.168.0.1"


def test_a_command_that_fails_reads_as_unknown(monkeypatch):
    monkeypatch.setattr(netid, "_run", lambda argv, timeout=0: "")
    assert netid.read_macos() is None
    assert netid.read_windows() is None


# --- which networks open -------------------------------------------------------


def _trust_state(**over):
    state = {
        "networks": [], "devices": [], "any_network": False, "ask_new_devices": True,
        "untrusted": [], "turned_on": 0.0, "last_used": 0.0, "switched_off": "",
    }
    state.update(over)
    return state


def test_only_an_allowed_network_opens():
    allowed = _trust_state(networks=[{"key": HOME.key}])
    assert lantrust.evaluate(allowed, HOME) == (True, "allowed")
    assert lantrust.evaluate(allowed, CAFE) == (False, "new_network")
    assert lantrust.evaluate(allowed, None) == (False, "unknown_network")


def test_any_network_opens_everywhere_but_a_public_one():
    loose = _trust_state(any_network=True)
    assert lantrust.evaluate(loose, CAFE) == (True, "any_network")
    assert lantrust.evaluate(loose, None) == (True, "any_network")
    assert lantrust.evaluate(loose, PUBLIC) == (False, "public_network")
    assert lantrust.evaluate(_trust_state(networks=[{"key": PUBLIC.key}]), PUBLIC) == (True, "allowed")


def test_a_damaged_file_gives_the_closed_defaults(tmp_path):
    (tmp_path / lantrust.FILE_NAME).write_text('{"any_network": "yes", "ask_new_devices": 0, "networks": 5}')
    state = lantrust.load(tmp_path)
    assert state == _trust_state()
    (tmp_path / lantrust.FILE_NAME).write_text("not json")
    assert lantrust.load(tmp_path) == _trust_state()


def test_turning_on_remembers_this_network_but_never_a_public_one(tmp_path, monkeypatch):
    lantrust.reset_for_tests()
    monkeypatch.setattr(netid, "read", lambda: HOME)
    assert lantrust.remember_current(tmp_path)["open"] is True
    assert lantrust.refresh(tmp_path, CAFE)["reason"] == "new_network"
    assert lantrust.is_open() is False
    monkeypatch.setattr(netid, "read", lambda: PUBLIC)
    assert lantrust.remember_current(tmp_path)["reason"] == "public_network"
    assert lantrust.allow_current(tmp_path)["open"] is True  # asked, and allowed


def test_allow_on_an_unknown_network_lasts_until_the_router_is_read(tmp_path, monkeypatch):
    lantrust.reset_for_tests()
    monkeypatch.setattr(netid, "read", lambda: None)
    assert lantrust.refresh(tmp_path)["reason"] == "unknown_network"
    assert lantrust.allow_current(tmp_path)["reason"] == "allowed_this_run"
    # The router answers: it is remembered as the network that was allowed.
    assert lantrust.refresh(tmp_path, HOME)["reason"] == "allowed"
    assert [n["key"] for n in lantrust.load(tmp_path)["networks"]] == [HOME.key]
    lantrust.reset_for_tests()
    assert lantrust.refresh(tmp_path, None)["open"] is False


def test_the_file_is_private(tmp_path):
    lantrust.save(tmp_path, _trust_state())
    assert (tmp_path / lantrust.FILE_NAME).stat().st_mode & 0o077 == 0


# --- devices ---------------------------------------------------------------------


def test_a_held_device_is_allowed_once_and_remembered_as_a_hash(tmp_path):
    lantrust.reset_for_tests()
    held = lantrust.hold("raw-cookie", "iPhone, Safari", "192.168.0.50")
    assert [p["id"] for p in lantrust.pending()] == [held["id"]]
    assert not lantrust.device_known(tmp_path, "raw-cookie")
    assert lantrust.decide(tmp_path, held["id"], True)
    assert lantrust.wait_decision("raw-cookie", 0.1) == "allowed"
    assert not lantrust.decide(tmp_path, held["id"], True)  # answered already
    assert lantrust.device_known(tmp_path, "raw-cookie")
    assert "raw-cookie" not in (tmp_path / lantrust.FILE_NAME).read_text()
    assert lantrust.forget_device(tmp_path, held["id"])
    assert not lantrust.device_known(tmp_path, "raw-cookie")


def test_a_denied_device_is_not_remembered_and_can_ask_again(tmp_path):
    lantrust.reset_for_tests()
    held = lantrust.hold("other", "A device", "192.168.0.51")
    lantrust.decide(tmp_path, held["id"], False)
    assert lantrust.wait_decision("other", 0.1) == "denied"
    assert not lantrust.device_known(tmp_path, "other")
    lantrust.settle("other")  # the device was told
    lantrust.hold("other", "A device", "192.168.0.51")
    assert len(lantrust.pending()) == 1


def test_a_device_that_keeps_asking_cannot_fill_the_screen():
    lantrust.reset_for_tests()
    for n in range(lantrust.MAX_PENDING + 5):
        lantrust.hold(f"d{n}", "A device", "192.168.0.9")
    assert len(lantrust.pending()) == lantrust.MAX_PENDING


def test_device_names_say_what_is_asking():
    iphone = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1"
    assert lantrust.device_name(iphone) == "iPhone, Safari"
    assert lantrust.device_name(None) == "A device"


# --- the routes --------------------------------------------------------------------




@pytest.fixture()
def trust_lan_app(client, monkeypatch):
    routes_auth._active_tokens.clear()
    routes_auth._media_tickets.clear()
    routes_auth._clear_unlock_failures()
    routes_auth._device_tokens.clear()
    vault.close()
    lantrust.reset_for_tests()
    monkeypatch.setattr(netid, "read", lambda: HOME)
    monkeypatch.setattr(routes_auth, "DEVICE_WAIT_SECONDS", 0.3)
    here = TestClient(client.app, base_url="http://127.0.0.1:8795", client=("127.0.0.1", 50000))
    token = here.post("/auth/setup", json={"password": PASSWORD}).json()["token"]
    here.headers["X-Auth-Token"] = token
    yield client
    lantrust.reset_for_tests()
    netbind.set_current(netbind.LOOPBACK)
    routes_auth._active_tokens.clear()
    routes_auth._device_tokens.clear()
    vault.close()


def _trust_here(client) -> TestClient:
    token = next(iter(routes_auth._active_tokens))
    return TestClient(
        client.app, base_url="http://127.0.0.1:8795", client=("127.0.0.1", 50000), headers={"X-Auth-Token": token}
    )


def _trust_phone(client) -> TestClient:
    """A phone on the network: https on the LAN port, so its Secure cookie is kept."""
    return TestClient(
        client.app, base_url="https://192.168.0.50:8443", client=("192.168.0.50", 50001),
        headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari/604.1"},
    )


def test_a_new_device_waits_and_this_computer_allows_it(trust_lan_app):
    here, phone = _trust_here(trust_lan_app), _trust_phone(trust_lan_app)
    refused = phone.post("/auth/unlock", json={"password": PASSWORD})
    assert refused.status_code == 403 and refused.json()["device_pending"] is True
    assert "allow it first" in refused.json()["detail"]
    cookie = refused.cookies.get(lantrust.DEVICE_COOKIE)
    assert cookie and "secure" in refused.headers["set-cookie"].lower()
    assert "httponly" in refused.headers["set-cookie"].lower()
    assert "samesite=strict" in refused.headers["set-cookie"].lower()
    waiting = here.get("/auth/lan-watch?since=-1").json()["pending"]
    assert [p["name"] for p in waiting] == ["iPhone, Safari"]
    # Only this computer sees who is waiting, and only it can answer.
    assert phone.get("/auth/lan-watch").status_code in (401, 403)
    # The phone asks again and waits; Allow on this computer lets it in.
    result = {}
    asking = threading.Thread(
        target=lambda: result.update(r=phone.post("/auth/unlock", json={"password": PASSWORD}))
    )
    routes_auth.DEVICE_WAIT_SECONDS = 5.0
    asking.start()
    deadline = __import__("time").monotonic() + 3
    while not lantrust.pending() and __import__("time").monotonic() < deadline:
        __import__("time").sleep(0.05)
    assert here.post(f"/auth/lan-devices/{waiting[0]['id']}/allow").status_code == 200
    asking.join(10)
    assert result["r"].status_code == 200 and result["r"].json()["token"]
    # Remembered: the next sign-in goes straight through.
    assert phone.post("/auth/unlock", json={"password": PASSWORD}).status_code == 200
    state = here.get("/auth/lan-access").json()
    assert [d["name"] for d in state["devices"]] == ["iPhone, Safari"]


def test_removing_a_device_signs_it_out_and_it_asks_again(trust_lan_app):
    here, phone = _trust_here(trust_lan_app), _trust_phone(trust_lan_app)
    phone.post("/auth/unlock", json={"password": PASSWORD})
    held = lantrust.pending()[0]
    here.post(f"/auth/lan-devices/{held['id']}/allow")
    token = phone.post("/auth/unlock", json={"password": PASSWORD}).json()["token"]
    assert phone.get("/auth/lan-access", headers={"X-Auth-Token": token}).status_code == 200
    removed = here.delete(f"/auth/lan-devices/{held['id']}")
    assert removed.status_code == 200
    assert phone.get("/auth/lan-access", headers={"X-Auth-Token": token}).status_code == 401
    assert phone.post("/auth/unlock", json={"password": PASSWORD}).status_code == 403


def test_deny_says_so_and_a_wrong_password_never_reaches_the_screen(trust_lan_app):
    here, phone = _trust_here(trust_lan_app), _trust_phone(trust_lan_app)
    assert phone.post("/auth/unlock", json={"password": "a guess"}).status_code == 401
    assert lantrust.pending() == []
    phone.post("/auth/unlock", json={"password": PASSWORD})
    held = lantrust.pending()[0]
    assert phone.post(f"/auth/lan-devices/{held['id']}/deny").status_code in (401, 403)
    assert here.post(f"/auth/lan-devices/{held['id']}/deny").status_code == 200
    refused = phone.post("/auth/unlock", json={"password": PASSWORD})
    assert refused.status_code == 403 and "said no" in refused.json()["detail"]
    # Told once; it may ask again, and waits like any new device.
    again = phone.post("/auth/unlock", json={"password": PASSWORD})
    assert again.status_code == 403 and again.json()["device_pending"] is True


def test_loopback_never_waits(trust_lan_app):
    assert TestClient(trust_lan_app.app, base_url="http://127.0.0.1:8795", client=("127.0.0.1", 50002)).post(
        "/auth/unlock", json={"password": PASSWORD}
    ).status_code == 200


def test_turning_off_asking_needs_the_password_and_on_does_not(trust_lan_app):
    here, phone = _trust_here(trust_lan_app), _trust_phone(trust_lan_app)
    body = {"name": "ask_new_devices", "enabled": False}
    assert here.post("/auth/lan-options", json=body).status_code == 401
    assert here.post("/auth/lan-options", json={**body, "current_password": PASSWORD}).json()["ask_new_devices"] is False
    assert phone.post("/auth/unlock", json={"password": PASSWORD}).status_code == 200
    assert here.post("/auth/lan-options", json={"name": "ask_new_devices", "enabled": True}).status_code == 200
    assert lantrust.load(lantrust_dir(trust_lan_app))["ask_new_devices"] is True


def lantrust_dir(client):
    from tessellate.core import deps

    return deps.get_config().data_dir


def test_any_network_and_allow_here_need_the_password(trust_lan_app):
    here = _trust_here(trust_lan_app)
    assert here.post("/auth/lan-options", json={"name": "any_network", "enabled": True}).status_code == 401
    assert here.post("/auth/lan-networks/allow", json={}).status_code == 401
    state = here.post("/auth/lan-networks/allow", json={"current_password": PASSWORD}).json()
    assert [n["key"] for n in state["networks"]] == [HOME.key]
    forgotten = here.delete(f"/auth/lan-networks/{HOME.key}")
    assert forgotten.json()["networks"] == []
    assert here.post(
        "/auth/lan-options", json={"name": "any_network", "enabled": True, "current_password": PASSWORD}
    ).json()["any_network"] is True
    assert here.post("/auth/lan-options", json={"name": "bogus", "enabled": True}).status_code == 422


def test_turning_the_switch_on_remembers_this_network(trust_lan_app):
    here = _trust_here(trust_lan_app)
    state = here.post("/auth/lan-access", json={"enabled": True, "current_password": PASSWORD}).json()
    assert [n["key"] for n in state["networks"]] == [HOME.key]


def test_preferences_cannot_reach_the_trust_file(trust_lan_app):
    here = _trust_here(trust_lan_app)
    here.put("/preferences", json={"any_network": True, "ask_new_devices": False, "networks": [{"key": "x"}]})
    assert lantrust.load(lantrust_dir(trust_lan_app)) == _trust_state()


def test_settings_says_when_the_network_is_held(trust_lan_app):
    """The launcher bound the network but this network is not allowed."""
    here = _trust_here(trust_lan_app)
    netbind.set_current(netbind.ALL_INTERFACES)
    lantrust.refresh(lantrust_dir(trust_lan_app), CAFE)
    state = here.get("/auth/lan-access").json()
    assert state["held"] == "new_network" and state["other_devices"] is False
    watch = here.get("/auth/lan-watch?since=-1").json()
    assert watch["serving"] is True and watch["held"]["reason"] == "new_network"


def test_addresses_put_the_phones_network_first_and_drop_virtual_adapters():
    network = netid.Network("192.168.0.1", "aa:bb:cc:dd:ee:01", "192.168.0.0/24", address="192.168.0.107",
                            virtual=("192.168.56.1",))
    shown = netbind.order_addresses(
        ["192.168.56.1", "2001:8003::3ef2", "192.168.0.107", "10.8.0.2", "2001:8003::87db"], network
    )
    assert shown == ["192.168.0.107", "10.8.0.2", "2001:8003::3ef2", "2001:8003::87db"]
    assert netbind.order_addresses(["172.17.0.2"], netid.Network("a", "b", virtual=("172.17.0.2",), address="172.17.0.2")) == ["172.17.0.2"]


# --- the looser direction is this computer's (secscan-1011) -------------------


def _signed_in_phone(client) -> TestClient:
    from tessellate.core import deps

    lantrust.set_flag(deps.get_config().data_dir, "ask_new_devices", False)
    phone = _trust_phone(client)
    phone.headers["X-Auth-Token"] = phone.post("/auth/unlock", json={"password": PASSWORD}).json()["token"]
    return phone


def test_a_phone_cannot_loosen_the_lan_options(trust_lan_app):
    """A phone with the password used to turn "Allow on any network" on and
    "Ask before a new device signs in" off; the safer direction stays open."""

    phone = _signed_in_phone(trust_lan_app)
    for body in (
        {"name": "any_network", "enabled": True, "current_password": PASSWORD},
        {"name": "ask_new_devices", "enabled": False, "current_password": PASSWORD},
    ):
        refused = phone.post("/auth/lan-options", json=body)
        assert refused.status_code == 403 and refused.json()["detail"] == REFUSAL
    assert lantrust.load(lantrust_dir(trust_lan_app))["any_network"] is False
    assert phone.post("/auth/lan-options", json={"name": "ask_new_devices", "enabled": True}).status_code == 200
    assert phone.post("/auth/lan-options", json={"name": "any_network", "enabled": False}).status_code == 200


def test_a_phone_cannot_allow_the_network_it_is_on(trust_lan_app):

    phone = _signed_in_phone(trust_lan_app)
    refused = phone.post("/auth/lan-networks/allow", json={"current_password": PASSWORD})
    assert refused.status_code == 403 and refused.json()["detail"] == REFUSAL
    assert lantrust.load(lantrust_dir(trust_lan_app))["networks"] == []
    assert _trust_here(trust_lan_app).post("/auth/lan-networks/allow", json={"current_password": PASSWORD}).status_code == 200


def test_local_name_opens_a_localhost_name(monkeypatch):
    from tessellate import __main__ as entry

    monkeypatch.delenv("TESSELLATE_LOCAL_NAME", raising=False)
    assert entry.page_host() == "127.0.0.1"
    monkeypatch.setenv("TESSELLATE_LOCAL_NAME", "Tessellate")
    assert entry.page_host() == "tessellate.localhost"
    monkeypatch.setenv("TESSELLATE_LOCAL_NAME", "evil.example/x")
    assert entry.page_host() == "127.0.0.1"
