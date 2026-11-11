"""Sync over the LAN (WORLD_CLASS_PLAN B6, decisions 10 and 11).

The end-to-end test boots two real servers, each its own data folder, each
serving HTTPS with its own LAN certificate authority (`lancert`), and has
each pair with the other through `POST /sync/pair` (the other computer's
password, the LAN sign-in, the sync pass) and sync a note both ways. Both
listen on loopback, where a sign-in never waits for Allow; the held sign-in
and Remove in Other devices are covered in process below, with a network
client address, the way `tests/test_lan.py` drives a phone.
"""

from __future__ import annotations

import http.client
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tessellate.api import routes_auth
from tessellate.core import deps, lancert, lantrust, sync_state
from tessellate.entry import sync_link, sync_segments

ROOT = Path(__file__).resolve().parent.parent
PASSWORDS = {"a": "the first computer's password", "b": "the second computer's password"}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Server:
    """One notebook served over HTTPS with its own certificate, as the LAN port is."""

    def __init__(self, root: Path, name: str) -> None:
        self.name = name
        self.data = root / name
        self.data.mkdir()
        self.info = lancert.ensure(self.data, ["127.0.0.1"])
        self.authority = lancert.authority_pem(self.data).decode()
        self.port = _free_port()
        self.log = root / f"{name}.log"
        env = {
            **os.environ, "PYTHONPATH": str(ROOT / "src"), "TESSELLATE_DATA_DIR": str(self.data),
            "TESSELLATE_NO_AUTO_INSTALL": "1",
        }
        self.proc = subprocess.Popen(  # noqa: S603  # our own app, fixed argv
            [sys.executable, "-m", "uvicorn", "tessellate.api.app:create_app", "--factory",
             "--host", "127.0.0.1", "--port", str(self.port),
             "--ssl-certfile", str(self.info.cert_path), "--ssl-keyfile", str(self.info.key_path)],
            cwd=str(root), env=env, stdout=self.log.open("w"), stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
        )
        self.token = ""

    def wait(self) -> None:
        deadline = time.time() + 90
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise AssertionError(f"{self.name} exited: {self.log.read_text()[-2000:]}")
            try:
                if self.call("GET", "/health")[0] == 200:
                    return
            except OSError:
                time.sleep(0.3)
        raise AssertionError(f"{self.name} never answered")

    def call(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        import ssl

        context = ssl.create_default_context(cadata=self.authority)
        conn = http.client.HTTPSConnection("127.0.0.1", self.port, timeout=60, context=context)
        try:
            headers = {"X-Auth-Token": self.token} if self.token else {}
            payload = None
            if body is not None:
                payload, headers["Content-Type"] = json.dumps(body), "application/json"
            conn.request(method, path, body=payload, headers=headers)
            response = conn.getresponse()
            raw = response.read()
            return response.status, json.loads(raw) if raw else {}
        finally:
            conn.close()

    def stop(self) -> None:
        self.proc.terminate()
        try:
            self.proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=5)


@pytest.fixture()
def two_computers(tmp_path):
    servers = [Server(tmp_path, "a"), Server(tmp_path, "b")]
    try:
        for server in servers:
            server.wait()
            status, body = server.call("POST", "/auth/setup", {"password": PASSWORDS[server.name]})
            assert status == 200, body
            server.token = body["token"]
        yield servers
    finally:
        for server in servers:
            server.stop()


def _entries(server: Server) -> list[dict]:
    status, body = server.call("GET", "/entries?limit=50")
    assert status == 200, body
    return body


def _texts(server: Server) -> list[str]:
    return sorted(e["content"] for e in _entries(server))


def test_two_computers_pair_over_https_and_sync_a_note_both_ways(two_computers):
    a, b = two_computers
    # The first press only names the certificate to check (test_the_first_press_sends_no_password below).
    status, first = a.call("POST", "/sync/pair", {"address": f"127.0.0.1:{b.port}", "password": "not it"})
    b_print = lancert.read(b.data).authority_fingerprint
    assert status == 200 and first["error"] == sync_link.confirm_sentence(b_print) and first["paired"] is False
    # A wrong password, on the second press, is a plain sentence and leaves nothing paired.
    status, wrong = a.call("POST", "/sync/pair", {"address": f"127.0.0.1:{b.port}", "password": "not it"})
    assert status == 200 and wrong["error"] == sync_link.WRONG_PASSWORD and wrong["paired"] is False

    for here, there in ((a, b), (b, a)):
        if here is b:  # b has not checked a's certificate yet
            status, first = here.call("POST", "/sync/pair", {"address": f"127.0.0.1:{there.port}", "password": PASSWORDS[there.name]})
            assert first["error"] == sync_link.confirm_sentence(lancert.read(there.data).authority_fingerprint)
        status, paired = here.call("POST", "/sync/pair", {"address": f"127.0.0.1:{there.port}", "password": PASSWORDS[there.name]})
        assert status == 200 and paired["error"] == "" and paired["paired"] is True, paired
        assert paired["address"] == f"127.0.0.1:{there.port}"
        assert paired["fingerprint"] == lancert.read(there.data).authority_fingerprint
    stored = json.loads((a.data / sync_state.FILE_NAME).read_text())
    assert PASSWORDS["b"] not in json.dumps(stored)  # the pass is kept, never the password
    assert (a.data / sync_state.FILE_NAME).stat().st_mode & 0o077 == 0

    assert a.call("POST", "/entries", {"content": "Written on the first computer"})[0] in (200, 201)
    status, pulled = b.call("POST", "/sync/now")
    assert pulled["error"] == "" and pulled["applied"] == 1, pulled
    assert _texts(b) == ["Written on the first computer"]

    assert b.call("POST", "/entries", {"content": "Answered on the second computer"})[0] in (200, 201)
    status, pulled = a.call("POST", "/sync/now")
    assert pulled["error"] == "" and pulled["applied"] == 1, pulled
    assert _texts(a) == ["Answered on the second computer", "Written on the first computer"]

    # A private note opens on both (decision 12), and is stored sealed on each.
    status, made = a.call("POST", "/entries", {"content": "The safe code is 4412"})
    assert a.call("POST", f"/entries/{made['id']}/privacy", {"private": True})[0] == 200
    status, pulled = b.call("POST", "/sync/now")
    assert pulled["error"] == "" and pulled["applied"] == 1 and pulled["private_readable"] is True, pulled
    assert "The safe code is 4412" in _texts(b)
    copy = next(e for e in _entries(b) if e["content"] == "The safe code is 4412")
    assert copy["is_private"] is True
    assert b.call("PUT", f"/entries/{copy['id']}", {"content": "The safe code is now 9031"})[0] == 200
    status, pulled = a.call("POST", "/sync/now")
    assert pulled["error"] == "" and pulled["applied"] == 1, pulled
    assert "The safe code is now 9031" in _texts(a)
    for server in (a, b):
        raw = _raw_contents(server)
        assert not any("9031" in text or "4412" in text for text in raw), server.name
    status, pulled = b.call("POST", "/sync/now")
    assert pulled["applied"] == 0, pulled  # the same words under two keys are the same note

    # A document and an attached file come over the same pass (decision 13).
    assert a.call("POST", "/documents", {"title": "Boiler", "content": "Service in March"})[0] == 201
    note = next(e for e in _entries(a) if e["content"] == "Written on the first computer")
    assert _upload(a, note["id"], "receipt.png", b"\x89PNG not really") == 201
    status, pulled = b.call("POST", "/sync/now")
    assert pulled["error"] == "" and pulled["applied"] == 2, pulled
    status, docs = b.call("GET", "/documents")
    found = docs if isinstance(docs, list) else docs.get("documents") or docs.get("items")
    assert [d["title"] for d in found] == ["Boiler"], docs
    copy = next(e for e in _entries(b) if e["content"] == "Written on the first computer")
    status, shown = b.call("GET", f"/entries/{copy['id']}")
    [attached] = shown["attachments"]
    assert attached["filename"] == "receipt.png"
    assert _raw_file(b, attached["id"]) == b"\x89PNG not really"
    assert b.call("POST", "/sync/now")[1]["applied"] == 0

    # The pass reads the segment and nothing else.
    pass_b = json.loads((a.data / sync_state.FILE_NAME).read_text())["link"]["sync_pass"]
    for path in ("/entries", "/sync/status"):
        assert _with_pass(b, path, pass_b) == 401, path
    assert _with_pass(b, "/sync/segment?since=0&peer=abcdefabcdef", pass_b) == 200

    # A certificate other than the paired one is refused, in a plain sentence.
    stranger = a.data.parent / "stranger"
    stranger.mkdir()
    lancert.ensure(stranger, ["127.0.0.1"])
    before = _texts(a)
    sync_state.save_link(a.data, authority=lancert.authority_pem(stranger).decode())
    status, refused = a.call("POST", "/sync/now")
    assert refused["error"] == sync_link.CERT_CHANGED and _texts(a) == before


def _raw_contents(server: Server) -> list[str]:
    import sqlite3

    with sqlite3.connect(server.data / "tessellate.db") as db:
        return [row[0] for row in db.execute("SELECT content FROM entries")]


def _https(server: Server):  # noqa: ANN202
    import ssl

    return http.client.HTTPSConnection(
        "127.0.0.1", server.port, timeout=30, context=ssl.create_default_context(cadata=server.authority)
    )


def _upload(server: Server, entry_id: int, name: str, data: bytes) -> int:
    boundary = "tessellate-sync-test"
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
            f"Content-Type: image/png\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
    conn = _https(server)
    try:
        conn.request("POST", f"/entries/{entry_id}/files", body=body, headers={
            "X-Auth-Token": server.token, "Content-Type": f"multipart/form-data; boundary={boundary}"})
        response = conn.getresponse()
        response.read()
        return response.status
    finally:
        conn.close()


def _raw_file(server: Server, attachment_id: int) -> bytes:
    import sqlite3

    with sqlite3.connect(server.data / "tessellate.db") as db:
        [(stored,)] = db.execute("SELECT stored_name FROM attachments WHERE id = ?", (attachment_id,)).fetchall()
    return (server.data / "uploads" / stored).read_bytes()


def _with_pass(server: Server, path: str, sync_pass: str) -> int:
    import ssl

    conn = http.client.HTTPSConnection(
        "127.0.0.1", server.port, timeout=30, context=ssl.create_default_context(cadata=server.authority)
    )
    try:
        conn.request("GET", path, headers={"X-Sync-Pass": sync_pass})
        response = conn.getresponse()
        response.read()
        return response.status
    finally:
        conn.close()


@pytest.mark.parametrize(("typed", "expected"), [
    ("192.168.1.20:8443", ("192.168.1.20", 8443)),
    ("https://192.168.1.20:8443/", ("192.168.1.20", 8443)),
    ("[fd00::5]:8443", ("fd00::5", 8443)),
])
def test_an_address_is_read_as_settings_shows_it(typed, expected):
    assert sync_link.parse_address(typed) == expected


@pytest.mark.parametrize("typed", ["", "192.168.1.20", "http://x:80/path", "a@b:80", "host:99999"])
def test_an_address_that_is_not_one_is_a_plain_sentence(typed):
    with pytest.raises(sync_link.PairError, match="Type the other computer's address"):
        sync_link.parse_address(typed)


# --- in process: the held sign-in and Remove ----------------------------------

PASSWORD = "the owner's password"
COOKIE = "paired-notebook-device-0001"


@pytest.fixture()
def notebook(client):
    routes_auth._active_tokens.clear()
    routes_auth._device_tokens.clear()
    routes_auth._network_tokens.clear()
    routes_auth._clear_unlock_failures()
    lantrust.reset_for_tests()
    local = TestClient(client.app, base_url="http://127.0.0.1:8795", client=("127.0.0.1", 50000))
    local.headers["X-Auth-Token"] = local.post("/auth/setup", json={"password": PASSWORD}).json()["token"]
    yield local
    lantrust.reset_for_tests()
    routes_auth._active_tokens.clear()
    routes_auth._device_tokens.clear()
    routes_auth._network_tokens.clear()


def _other_computer(client) -> TestClient:
    return TestClient(client.app, base_url="https://192.168.0.50:8443", client=("192.168.0.50", 50001),
                      cookies={lantrust.DEVICE_COOKIE: COOKIE})


def test_the_other_computer_waits_for_allow_and_remove_ends_its_pass(notebook, monkeypatch):
    data_dir = deps.get_config().data_dir
    monkeypatch.setattr(routes_auth, "DEVICE_WAIT_SECONDS", 0.05)
    other = _other_computer(notebook)
    held = other.post("/auth/unlock", json={"password": PASSWORD})
    assert held.status_code == 403 and held.json()["device_pending"] is True
    device = lantrust.device_hash(COOKIE)
    allowed = notebook.post(f"/auth/lan-devices/{device}/allow")
    assert allowed.status_code == 200

    signed_in = other.post("/auth/unlock", json={"password": PASSWORD}).json()["token"]
    issued = other.post("/sync/pass", json={"peer": "abcdefabcdef"}, headers={"X-Auth-Token": signed_in}).json()
    assert issued["device"] == sync_state.device_id(data_dir)
    assert [d["id"] for d in lantrust.devices(data_dir)] == [device]

    segment = other.get("/sync/segment", params={"since": 0, "peer": "abcdefabcdef"}, headers={"X-Sync-Pass": issued["pass"]})
    assert segment.status_code == 200 and segment.json()["device"] == issued["device"]
    forged = other.get("/sync/segment", params={"peer": "x"}, headers={"X-Sync-Pass": "a forged pass"})
    assert forged.status_code == 401

    forgotten = notebook.delete(f"/auth/lan-devices/{device}")
    assert forgotten.status_code == 200
    gone = other.get("/sync/segment", params={"since": 0, "peer": "abcdefabcdef"}, headers={"X-Sync-Pass": issued["pass"]})
    assert gone.status_code == 401


def test_a_device_never_allowed_gets_no_pass_even_with_a_session(notebook):
    token = "a session from before asking was on"
    routes_auth._active_tokens[token] = [time.time(), time.time()]
    refused = _other_computer(notebook).post("/sync/pass", json={"peer": "abcdefabcdef"}, headers={"X-Auth-Token": token})
    assert refused.status_code == 403 and "Allow this computer" in refused.json()["detail"]


def test_with_asking_off_the_paired_computer_is_still_listed_so_remove_works(notebook):
    data_dir = deps.get_config().data_dir
    lantrust.set_flag(data_dir, "ask_new_devices", False)
    other = _other_computer(notebook)
    signed_in = other.post("/auth/unlock", json={"password": PASSWORD}).json()["token"]
    issued = other.post("/sync/pass", json={"peer": "abcdefabcdef"}, headers={"X-Auth-Token": signed_in})
    assert issued.status_code == 200
    [listed] = lantrust.devices(data_dir)
    assert listed["id"] == lantrust.device_hash(COOKIE) and listed["name"].startswith("Paired notebook")


def test_pairing_is_for_this_computer_only(notebook):
    other = _other_computer(notebook)
    lantrust.set_flag(deps.get_config().data_dir, "ask_new_devices", False)
    other.headers["X-Auth-Token"] = other.post("/auth/unlock", json={"password": PASSWORD}).json()["token"]
    paired = other.post("/sync/pair", json={"address": "192.168.0.9:8443", "password": "x"})
    unpaired = other.delete("/sync/pair")
    assert paired.status_code == 403 and unpaired.status_code == 403


def test_the_first_press_sends_no_password_and_the_second_uses_the_checked_certificate(tmp_path, monkeypatch):
    """Trust on first use, made a choice: someone else on the network could answer the first call, so the
    certificate it gives is shown, kept and checked by the person before any password leaves this computer."""
    there = tmp_path / "there"
    there.mkdir()
    lancert.ensure(there, ["127.0.0.1"])
    authority = lancert.authority_pem(there).decode()
    fetched, signed = [], []
    monkeypatch.setattr(sync_link, "_authority", lambda host, port: fetched.append(host) or authority)

    def sign_in(wire, password, cookie):
        signed.append((wire.host, password))
        raise sync_link.PairError(sync_link.WRONG_PASSWORD)

    monkeypatch.setattr(sync_link, "_sign_in", sign_in)
    here = tmp_path / "here"
    here.mkdir()
    with pytest.raises(sync_link.PairError):
        sync_link.pair(here, "192.168.1.20:8443", "the password")
    assert fetched == ["192.168.1.20"] and signed == []
    assert sync_link.last_problem() == sync_link.confirm_sentence(sync_link.fingerprint(authority))
    with pytest.raises(sync_link.PairError):
        sync_link.pair(here, "192.168.1.20:8443", "the password")
    assert fetched == ["192.168.1.20"] and signed == [("192.168.1.20", "the password")]  # the kept certificate
    with pytest.raises(sync_link.PairError):
        sync_link.pair(here, "192.168.1.21:8443", "the password")  # a new address is a new first press
    assert fetched == ["192.168.1.20", "192.168.1.21"] and len(signed) == 1


def test_a_first_press_at_another_address_leaves_the_working_pairing_alone(tmp_path, monkeypatch):
    """A stranger answering a mistyped address, or a press never repeated, must not undo a pairing that syncs."""
    pems = []
    for name in ("there", "stranger"):
        (tmp_path / name).mkdir()
        lancert.ensure(tmp_path / name, ["127.0.0.1"])
        pems.append(lancert.authority_pem(tmp_path / name).decode())
    here = tmp_path / "here"
    here.mkdir()
    sync_state.save_link(here, host="192.168.1.20", port=8443, cookie="c", authority=pems[0], fingerprint="fp",
                         peer="abc123def456", sync_pass="the pass")
    monkeypatch.setattr(sync_link, "_authority", lambda host, port: pems[1])
    with pytest.raises(sync_link.PairError):
        sync_link.pair(here, "192.168.1.99:8443", "the password")
    kept = sync_state.link(here)
    assert (kept["host"], kept["peer"], kept["sync_pass"], kept["authority"]) == (
        "192.168.1.20", "abc123def456", "the pass", pems[0])
    assert sync_link.load(here) is not None


def test_pairing_with_a_computer_that_has_this_ones_sync_id_is_refused(tmp_path, monkeypatch):
    """PR 216 review: a data folder copied to a second computer answers with this computer's own device id."""
    there = tmp_path / "there"
    there.mkdir()
    lancert.ensure(there, ["127.0.0.1"])
    authority = lancert.authority_pem(there).decode()
    here = tmp_path / "here"
    here.mkdir()
    me = sync_state.device_id(here)
    monkeypatch.setattr(sync_link, "_authority", lambda host, port: authority)
    monkeypatch.setattr(sync_link, "_sign_in", lambda wire, password, cookie: "token")
    answer = json.dumps({"pass": "p", "device": me}).encode()
    monkeypatch.setattr(sync_link._Wire, "call", lambda self, method, path, **kw: (200, answer))  # noqa: SLF001
    with pytest.raises(sync_link.PairError):
        sync_link.pair(here, "192.168.1.20:8443", "the password")  # the certificate to check first
    with pytest.raises(sync_link.PairError):
        sync_link.pair(here, "192.168.1.20:8443", "the password")
    assert sync_link.last_problem() == sync_segments.SAME_ID
    assert sync_link.load(here) is None


def test_a_pull_from_a_link_named_as_this_computer_applies_nothing(tmp_path):
    from tessellate.entry import sync_pull

    here = tmp_path / "here"
    here.mkdir()
    me = sync_state.device_id(here)

    class Twin:
        name = me

        def fetch(self, since, peer):  # noqa: ANN001, ANN202
            raise AssertionError("never asked")

    done = sync_pull.pull_from(None, here, Twin(), "network")
    assert done["error"] == sync_segments.SAME_ID
