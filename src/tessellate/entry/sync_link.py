"""The LAN transport for sync (WORLD_CLASS_PLAN B6, decisions 10 and 11).

Pairing signs this computer in to the other one exactly as a phone does on
the LAN port: `POST /auth/unlock` with the other computer's password and a
device cookie this computer made, so the other computer's "Ask before a new
device signs in" holds it until someone there presses Allow, and it is then
listed in that computer's Other devices. With the sign-in it asks
`POST /sync/pass` for a pass that reads `GET /sync/segment` and nothing
else; the pass is what is kept (decision 11), never the password, and
Remove in the other computer's Other devices ends it.

TLS as the LAN mode does it: the first contact fetches the other computer's
own certificate authority (`/auth/lan-certificate.pem`, the file a phone
installs), and every connection after that, the sign-in included, is
verified against that authority and nothing else, with the address checked
against the certificate's names. The authority's fingerprint is shown in
both computers' Settings so the person can compare them.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import platform
import secrets
import ssl
from pathlib import Path
from urllib.parse import urlencode

from tessellate.core import sync_state
from tessellate.entry import sync_keys
from tessellate.entry.sync_segments import SegmentError

WRONG_PASSWORD = "That password is wrong for the other computer."
WAITING = "Choose Allow on the other computer, then press Pair again."
DENIED = "The other computer said no to this one."
NOT_SYNCING = "The other computer did not offer sync; update Tessellate there first."
BAD_ADDRESS = "Type the other computer's address as Settings there shows it, like 192.168.1.20:8443."
UNREACHABLE = "The other computer did not answer at that address. Check that other devices are on there."
NOT_ALLOWED = "The other computer no longer allows this one; pair again."
CERT_CHANGED = "The other computer's certificate is not the one paired; nothing was applied. Pair again if it was renewed."
TIMEOUT = 30.0


class PairError(ValueError):
    """Pairing stopped; the message is the sentence Settings shows."""


def parse_address(text: str) -> tuple[str, int]:
    """'192.168.1.20:8443' or 'https://192.168.1.20:8443/' to (host, port)."""
    raw = (text or "").strip().removeprefix("https://").rstrip("/")
    host, _, port = raw.rpartition(":")
    host = host.strip("[]")
    if not host or not port.isdigit() or not 0 < int(port) < 65536 or any(c in host for c in "/@?# "):
        raise PairError(BAD_ADDRESS)
    return host, int(port)


def fingerprint(pem: str) -> str:
    """The authority's SHA-256 fingerprint as `lancert` prints it (AB:CD:...)."""
    der = ssl.PEM_cert_to_DER_cert(pem)
    digest = hashlib.sha256(der).hexdigest().upper()
    return ":".join(digest[i : i + 2] for i in range(0, len(digest), 2))


class _Wire:
    """One HTTPS exchange with the other computer, never through a proxy."""

    def __init__(self, host: str, port: int, authority: str | None) -> None:
        self.host, self.port = host, port
        if authority is None:  # first contact only: fetch the authority, trust nothing yet
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        else:
            context = ssl.create_default_context(cadata=authority)
        self.context = context

    def call(self, method: str, path: str, *, body: dict | None = None, headers: dict | None = None) -> tuple[int, bytes]:
        conn = http.client.HTTPSConnection(self.host, self.port, timeout=TIMEOUT, context=self.context)
        try:
            sent = {"Accept": "application/json", "User-Agent": f"Tessellate sync ({platform.system()})", **(headers or {})}
            payload = None
            if body is not None:
                payload = json.dumps(body)
                sent["Content-Type"] = "application/json"
            conn.request(method, path, body=payload, headers=sent)
            response = conn.getresponse()
            return response.status, response.read()
        finally:
            conn.close()


def _json(raw: bytes) -> dict:
    try:
        found = json.loads(raw or b"{}")
    except ValueError:
        return {}
    return found if isinstance(found, dict) else {}


def _authority(host: str, port: int) -> str:
    try:
        status, raw = _Wire(host, port, None).call("GET", "/auth/lan-certificate.pem")
    except OSError as exc:
        raise PairError(UNREACHABLE) from exc
    text = raw.decode("ascii", "replace")
    if status != 200 or "BEGIN CERTIFICATE" not in text:
        raise PairError(UNREACHABLE)
    return text


def _sign_in(wire: _Wire, password: str, cookie: str) -> str:
    status, raw = wire.call("POST", "/auth/unlock", body={"password": password}, headers={"Cookie": f"mm_device={cookie}"})
    answer = _json(raw)
    if status == 200 and answer.get("token"):
        return answer["token"]
    if status == 403:
        raise PairError(WAITING if answer.get("device_pending") else DENIED)
    raise PairError(WRONG_PASSWORD if status == 401 else UNREACHABLE)


def pair(data_dir: Path, address: str, password: str) -> dict:
    """Sign in to the other computer and keep a sync pass; the stored link."""
    host, port = parse_address(address)
    before = sync_state.link(data_dir)
    same_place = before.get("host") == host and before.get("port") == port
    cookie = before.get("cookie") if same_place and before.get("cookie") else secrets.token_urlsafe(32)
    authority = before["authority"] if same_place and before.get("authority") else _authority(host, port)
    # The cookie and authority are kept before the sign-in, so a press after Allow
    # is the same device to the other computer and checks the same certificate.
    # A new address starts a new pairing; a wrong password for the same one keeps the old pass.
    fresh = {} if same_place else {"peer": "", "sync_pass": ""}
    sync_state.save_link(data_dir, host=host, port=port, cookie=cookie, authority=authority,
                         fingerprint=fingerprint(authority), **fresh)
    wire = _Wire(host, port, authority)
    try:
        token = _sign_in(wire, password, cookie)
        status, raw = wire.call("POST", "/sync/pass", body={"peer": sync_state.device_id(data_dir)},
                                headers={"X-Auth-Token": token, "Cookie": f"mm_device={cookie}"})
    except ssl.SSLCertVerificationError as exc:
        raise PairError(CERT_CHANGED) from exc
    except OSError as exc:
        raise PairError(UNREACHABLE) from exc
    answer = _json(raw)
    if status != 200 or not answer.get("pass") or not answer.get("device"):
        raise PairError(answer.get("detail") if status == 403 and answer.get("detail") else NOT_SYNCING)
    return sync_state.save_link(data_dir, peer=answer["device"], sync_pass=answer["pass"],
                                peer_key=sync_keys.wrap_peer_key(answer.get("key")))


class LanLink:
    """The transport `sync_pull` uses (decision 9): `name` and `fetch`."""

    def __init__(self, stored: dict) -> None:
        self.name = stored["peer"]
        self._wire = _Wire(stored["host"], stored["port"], stored["authority"])
        self._pass = stored["sync_pass"]

    def fetch(self, since: int, me: str) -> dict:
        query = urlencode({"since": since, "peer": me})
        try:
            status, raw = self._wire.call("GET", f"/sync/segment?{query}", headers={"X-Sync-Pass": self._pass})
        except ssl.SSLCertVerificationError as exc:
            raise SegmentError(CERT_CHANGED) from exc
        if status == 401:
            raise SegmentError(NOT_ALLOWED)
        if status != 200:
            raise ConnectionError(f"the other computer answered {status}")
        return _json(raw)


def load(data_dir: Path) -> LanLink | None:
    """The paired computer's transport, or None when pairing never finished."""
    stored = sync_state.link(data_dir)
    if not stored.get("peer") or not stored.get("sync_pass"):
        return None
    return LanLink(stored)
