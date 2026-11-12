"""The LAN port's accept loop: TLS for the app, a redirect for plain http.

INBOX 866, "the connection ... issues when trying to access it on phone over
lan". A phone that is given `192.168.1.5:8443` without `https://` (typed, or
read off the terminal) asks over plain http, which every phone browser does
for an address, and a TLS-only socket answered that with nothing: Safari's
"the server unexpectedly dropped the connection", Chrome's ERR_EMPTY_RESPONSE.
So the first byte decides. 0x16 opens a TLS handshake, and the connection goes
to uvicorn's own HTTP protocol over TLS, exactly as uvicorn would have made it;
anything else gets a `301` to the same address over https, and only for a Host
that names this computer (`netbind.host_allowed`), so the redirect can never
send anyone elsewhere.

Two things answer a plain-http first byte instead of the redirect (Brief 40,
fix shape 2 and 3). `/lan/trust` and `/lan/trust/ca.crt`: the one-page guide
and the public authority certificate a phone installs, served only while
Settings has the trust window open (`open_trust_page`), which is what the QR
code in Settings points at. And, when the person turned "plain http" on, the
app itself: the connection goes to uvicorn's protocol without TLS, off by
default, the password warning beside the switch. A failed TLS handshake
(a phone refusing the certificate, a scanner) is counted for Settings.

uvicorn is given no socket of its own (`serve(sockets=[])`): it still runs
its loop, keeps the connections this loop hands it in `server_state`, and
closes them at shutdown, so Ctrl+C ends both listeners as before.

INBOX 867 ("what if memory map is open to lan on a public network"): a
client whose address is not private, shared or link-local is closed before
its first byte is read (`client_allowed`): a forwarded port or a network
that hands out public addresses never reaches the lock screen.
"""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import logging
import re
import select
import socket
import ssl
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from tessellate.core import netbind

log = logging.getLogger(__name__)

TLS_HANDSHAKE = 0x16
#: How long a new connection may stay silent before it is dropped.
FIRST_BYTE_SECONDS = 10.0
HEAD_LIMIT = 8192
#: Plain-http answers run on threads, because the Windows event loop
#: (Proactor) has no `add_reader`; their request head is already in hand.
_PEEKERS = ThreadPoolExecutor(max_workers=4, thread_name_prefix="lan-http")
_SAFE_PATH = re.compile(r"^/[\x21-\x7e]*$")
#: How long Settings' "Phone setup QR code" keeps the trust page answering.
TRUST_WINDOW_SECONDS = 900.0
TRUST_PATH = "/lan/trust"
#: Failed TLS handshakes since start (a phone refusing the certificate is the
#: usual one): the number beside "connection was lost" in Settings.
_stats = {"trust_until": 0.0, "handshake_failures": 0}
#: The addresses a device beside this computer has: private (RFC 1918 and
#: IPv6 unique-local), carrier-grade shared space (a phone hotspot, some
#: mesh VPNs), link-local, and this computer itself. Listed rather than
#: `is_private`, whose meaning has moved between Python versions.
_NEARBY = tuple(
    ipaddress.ip_network(n)
    for n in (
        "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10", "169.254.0.0/16",
        "127.0.0.0/8", "::1/128", "fc00::/7", "fe80::/10",
    )
)


#: The /64 of each of this computer's global IPv6 addresses. An iPhone on the
#: same Wi-Fi often connects from its own global IPv6 address, which is not
#: private, but shares the /64 the router hands this whole network (the owner's
#: Windows machine, 2026-10-11: two 2001:8003:... addresses, one temporary).
_own_v6_prefixes: frozenset = frozenset()
#: How often the prefixes (and the network gate) are read again: temporary
#: IPv6 addresses rotate, and a laptop changes networks without restarting.
REFRESH_SECONDS = 30.0
#: How often this computer's own address set is compared with the last one
#: (INBOX 892 and 896): a list read locally, cheap enough to run often, so
#: losing Wi-Fi or joining a hotspot closes or re-certifies the port in
#: seconds rather than at the next full read of the network.
ADDRESS_SECONDS = 5.0


def open_trust_page(seconds: float = TRUST_WINDOW_SECONDS) -> float:
    """Let the plain-http trust page answer for `seconds` (the QR code's window).
    Returns the seconds it will stay open."""
    _stats["trust_until"] = time.monotonic() + seconds
    return seconds


def trust_page_open() -> bool:
    return time.monotonic() < _stats["trust_until"]


def handshake_failures() -> int:
    return _stats["handshake_failures"]


def _text_response(status: bytes, kind: bytes, body: bytes, extra: bytes = b"") -> bytes:
    return (
        b"HTTP/1.1 " + status + b"\r\nContent-Type: " + kind + b"\r\nCache-Control: no-store\r\n"
        + extra + b"Connection: close\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body
    )


def _trust_page(fingerprint: str, https_url: str) -> bytes:
    steps = (
        "<li>iPhone or iPad: tap <b>Download the certificate</b>, allow it, then Settings, Profile Downloaded, "
        "Install. After that, Settings, General, About, Certificate Trust Settings, and switch it on.</li>"
        "<li>Android: tap <b>Download the certificate</b>, then in the phone's own settings app: Security, Install a certificate, "
        "CA certificate.</li><li>Brave on iPhone uses the same system trust as Safari.</li>"
    )
    html = (
        '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Trust this notebook</title><style>body{font:17px/1.5 system-ui;max-width:34rem;margin:2rem auto;padding:0 1rem}</style><body>"
        "<h1>Trust this notebook on your phone</h1>"
        "<p>Install the certificate once and this address stops warning you.</p>"
        '<p><a href="/lan/trust/ca.crt"><b>Download the certificate</b></a></p>'
        f"<p>After installing, check the fingerprint reads <code>{fingerprint}</code>.</p><ol>{steps}</ol>"
        f'<p>Then open <a href="{https_url}">{https_url}</a>.</p>'
    )
    return _text_response(b"200 OK", b"text/html; charset=utf-8", html.encode("utf-8"))


def _trust_request(head: bytes) -> tuple[str, str] | None:
    """(path, host) of a GET for the trust page from a Host that names this
    computer, else None."""
    lines = head.decode("latin-1", "replace").split("\r\n")
    parts = lines[0].split(" ")
    if len(parts) != 3 or parts[0] != "GET" or parts[1] not in (TRUST_PATH, TRUST_PATH + "/ca.crt"):
        return None
    host = next((v.strip() for n, _, v in (ln.partition(":") for ln in lines[1:]) if n.strip().lower() == "host"), "")
    if not host or not netbind.host_allowed(host) or not re.fullmatch(r"[A-Za-z0-9.\-:\[\]%]+", host):
        return None
    return parts[1], host


def trust_response(head: bytes, port: int, trust) -> bytes | None:  # noqa: ANN001
    """The guide or the certificate for a plain-http request to `/lan/trust`,
    or None when this is not that request (the redirect answers). `trust` is
    `() -> (authority_pem, fingerprint) | None`; None, or a closed window,
    is not an answer either. Only a Host naming this computer, as the redirect."""
    request = _trust_request(head) if trust is not None and trust_page_open() else None
    material = trust() if request else None
    if material is None:
        return None
    path, host = request
    pem, fingerprint = material
    if path.endswith("/ca.crt"):
        return _text_response(
            b"200 OK", b"application/x-x509-ca-cert", pem,
            b'Content-Disposition: attachment; filename="tessellate-lan.crt"\r\n',
        )
    name = host.split("]", 1)[0] + "]" if host.startswith("[") else (host.rsplit(":", 1)[0] if host.count(":") == 1 else host)
    return _trust_page(fingerprint, f"https://{name}:{port}/")


def drop_connections(server) -> int:  # noqa: ANN001  # a uvicorn.Server
    """Close every connection another device holds open on the LAN port.
    Closing the listening socket stops new ones; a phone's keep-alive
    connection would otherwise go on answering on a network that was just
    turned away (INBOX 896) or after LAN mode was switched off (INBOX 900)."""
    dropped = 0
    state = getattr(server, "server_state", None)
    for connection in list(state.connections if state is not None else ()):
        transport = getattr(connection, "transport", None)
        if transport is None:
            continue
        with contextlib.suppress(Exception):
            transport.close()
            dropped += 1
    return dropped


def _record_incoming(address: str) -> None:
    """INBOX 894: a device on this network opening the app is on the privacy
    receipt, as an incoming row in the local-network total. The audit hook
    sees only what this process opens, never what it accepts, so the accept
    loop says so itself: the device's address, never what it asked for."""
    from tessellate.core import egress, lantrust

    with contextlib.suppress(Exception):
        egress.record_incoming(address)
    with contextlib.suppress(Exception):
        lantrust.note_used()


def own_v6_prefixes(addresses: list[str]) -> frozenset:
    """The /64s of the global IPv6 addresses in `addresses`."""
    found = set()
    for text in addresses:
        try:
            ip = ipaddress.ip_address(text.strip("[]").split("%", 1)[0])
        except ValueError:
            continue
        if ip.version == 6 and ip.is_global:
            found.add(ipaddress.ip_network(f"{ip}/64", strict=False))
    return frozenset(found)


#: This computer's own addresses: a connection from one of them is from this
#: computer, whatever range the network numbers it in.
_own_addresses: frozenset = frozenset()


def refresh_own_prefixes() -> None:
    global _own_v6_prefixes, _own_addresses
    try:
        mine = netbind.lan_addresses(include_v6=True)
    except OSError:
        mine = []
    _own_v6_prefixes = own_v6_prefixes(mine)
    _own_addresses = frozenset(mine)


def _addresses_now() -> list[str]:
    try:
        return netbind.lan_addresses(include_v6=True)
    except OSError:
        return []


def client_allowed(address: str | None, prefixes: frozenset | None = None) -> bool:
    """Is this client address one on this network? Unreadable means no."""
    if not isinstance(address, str):
        return False
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    ip = getattr(ip, "ipv4_mapped", None) or ip
    if any(ip.version == net.version and ip in net for net in _NEARBY) or str(ip) in _own_addresses:
        return True
    shared = _own_v6_prefixes if prefixes is None else prefixes
    return ip.version == 6 and any(ip in net for net in shared)


class _FirstByteWatcher:
    """One thread that waits for every new connection's first byte with
    `select`, which works on every platform's sockets.

    The owner, 2026-10-11, Safari on an iPhone: "its taking a very long
    time". Safari opens connections ahead of need and sends nothing on
    them; a thread per peek held one of eight workers for up to ten seconds
    each, so the page's real requests queued behind silent sockets. One
    watcher holds any number of silent sockets at no cost."""

    TICK = 0.05
    #: Windows' select takes at most 512 sockets; the rest wait a tick.
    BATCH = 500

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._waiting: dict[socket.socket, tuple[asyncio.AbstractEventLoop, asyncio.Future, float]] = {}
        self._thread: threading.Thread | None = None

    def wait(self, conn: socket.socket, timeout: float = FIRST_BYTE_SECONDS) -> asyncio.Future:
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        conn.setblocking(False)
        with self._lock:
            self._waiting[conn] = (loop, future, time.monotonic() + timeout)
            if self._thread is None:
                from tessellate.core import jobs

                self._thread = jobs.thread("lan-first-byte", self._run)
        return future

    @staticmethod
    def _settle(loop, future, value) -> None:  # noqa: ANN001
        def done() -> None:
            if future.done():
                return
            if isinstance(value, BaseException):
                future.set_exception(value)
            else:
                future.set_result(value)

        with contextlib.suppress(RuntimeError):  # the loop has closed
            loop.call_soon_threadsafe(done)

    def _run(self) -> None:
        while True:
            with self._lock:
                if not self._waiting:
                    self._thread = None
                    return
                socks = list(self._waiting)
            batch = socks[: self.BATCH]
            try:
                ready, _, broken = select.select(batch, [], batch, self.TICK)
            except (OSError, ValueError):  # a socket closed under us
                ready, broken = [], [s for s in batch if s.fileno() < 0]
            now = time.monotonic()
            for sock in socks:
                with self._lock:
                    entry = self._waiting.get(sock)
                if entry is None:
                    continue
                loop, future, deadline = entry
                value: bytes | OSError
                if sock in ready or sock in broken:
                    try:
                        value = sock.recv(1, socket.MSG_PEEK)
                    except BlockingIOError:
                        continue
                    except OSError as exc:
                        value = exc
                elif now >= deadline or future.cancelled():
                    value = b""
                else:
                    continue
                with self._lock:
                    self._waiting.pop(sock, None)
                self._settle(loop, future, value)


_WATCHER = _FirstByteWatcher()


def redirect_response(head: bytes, port: int) -> bytes:
    """The answer to a plain-http request head: a 301 to https, or a 400."""
    text = head.decode("latin-1", "replace")
    lines = text.split("\r\n")
    parts = lines[0].split(" ")
    path = parts[1] if len(parts) == 3 and parts[2].startswith("HTTP/") else "/"
    if not _SAFE_PATH.match(path) or path.startswith("//"):
        path = "/"
    host = ""
    for line in lines[1:]:
        name, _, value = line.partition(":")
        if name.strip().lower() == "host":
            host = value.strip()
            break
    if not host or not netbind.host_allowed(host) or not re.fullmatch(r"[A-Za-z0-9.\-:\[\]%]+", host):
        body = b"Open this address with https:// in front.\n"
        return (
            b"HTTP/1.1 400 Bad Request\r\nContent-Type: text/plain; charset=utf-8\r\n"
            b"Connection: close\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body
        )
    if host.startswith("["):
        name = host.split("]", 1)[0] + "]"
    else:
        name = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
    location = f"https://{name}:{port}{path}"
    return (
        b"HTTP/1.1 301 Moved Permanently\r\nLocation: " + location.encode("ascii") + b"\r\n"
        b"Content-Length: 0\r\nConnection: close\r\n\r\n"
    )


def _answer_plain_http(conn: socket.socket, port: int, trust=None) -> None:  # noqa: ANN001
    conn.settimeout(FIRST_BYTE_SECONDS)
    head = b""
    with contextlib.suppress(OSError):
        while b"\r\n\r\n" not in head and len(head) < HEAD_LIMIT:
            chunk = conn.recv(1024)
            if not chunk:
                break
            head += chunk
        conn.sendall(trust_response(head, port, trust) or redirect_response(head, port))
    with contextlib.suppress(OSError):
        conn.shutdown(socket.SHUT_RDWR)
    conn.close()


async def _route(  # noqa: ANN001, PLR0913
    conn: socket.socket, make_protocol, context: ssl.SSLContext, port: int, plain_http=None, trust=None,
) -> None:
    loop = asyncio.get_running_loop()
    try:
        first = await _WATCHER.wait(conn)
    except OSError:
        conn.close()
        return
    if not first:
        conn.close()
        return
    if first[0] != TLS_HANDSHAKE:
        if plain_http is not None and plain_http():
            #: The person's choice, off by default: the app over plain http, the
            #: first byte still unread (it was only peeked).
            await loop.connect_accepted_socket(make_protocol, conn)
            return
        await loop.run_in_executor(_PEEKERS, _answer_plain_http, conn, port, trust)
        return
    try:
        await loop.connect_accepted_socket(make_protocol, conn, ssl=context)
    except (OSError, ssl.SSLError, asyncio.TimeoutError, ConnectionError):
        # A failed handshake: a phone refusing the certificate, a scanner.
        # asyncio has closed the transport; the socket may still be open.
        _stats["handshake_failures"] += 1
        conn.close()


async def _port_step(sock, gate, reopen, port, server):  # noqa: ANN001
    """Close the port when the gate shuts, bind it again when it opens.
    Returns (sock, verdict): "go" to accept, "continue" to try again, "break" to stop."""
    if gate is not None and not gate():
        if sock is not None:
            log.info("Other devices: this network is not allowed; the LAN port is closed.")
            sock.close()
            sock = None
            dropped = drop_connections(server)
            if dropped:
                log.info("Other devices: %s open connection(s) closed with it.", dropped)
        await asyncio.sleep(0.5)
        return sock, "continue"
    if sock is None:
        if reopen is None:
            return sock, "break"
        try:
            sock = reopen()
            sock.setblocking(False)
            log.info("Other devices: the LAN port is open on this network.")
        except OSError as exc:
            log.warning("Other devices can't reach this notebook: port %s is taken (%s).", port, exc)
            await asyncio.sleep(REFRESH_SECONDS / 3)
            return None, "continue"
    return sock, "go"


async def _accept(loop, sock):  # noqa: ANN001
    """The next allowed connection as (conn, addr), or None to look again."""
    try:
        conn, addr = await asyncio.wait_for(loop.sock_accept(sock), 0.5)
    except asyncio.TimeoutError:
        return None
    except OSError as exc:
        log.debug("LAN accept failed: %s", exc)
        await asyncio.sleep(0.1)
        return None
    if not client_allowed(addr[0] if addr else None):
        log.info("Refused a connection from %s: not an address on this network.", addr[0] if addr else "?")
        with contextlib.suppress(OSError):
            conn.close()
        return None
    return conn, addr


async def serve(  # noqa: PLR0913
    server,  # noqa: ANN001  # a uvicorn.Server with ssl set
    sock: socket.socket | None,
    *,
    port: int | None = None,
    gate=None,  # noqa: ANN001  # () -> bool: may the port be open now?
    refresh=None,  # noqa: ANN001  # () -> None: read the network again
    reopen=None,  # noqa: ANN001  # () -> socket: bind the port again
    on_addresses=None,  # noqa: ANN001  # () -> None: this computer's addresses changed
    plain_http=None,  # noqa: ANN001  # () -> bool: serve the app over plain http too?
    trust=None,  # noqa: ANN001  # () -> (authority pem, fingerprint) | None, for /lan/trust
) -> None:
    """Run `server` (TLS configured, `config.load()`ed) on `sock`, sniffing
    each connection's first byte. Returns once the server has exited.

    With `gate` (INBOX 867), the port is open only while the gate says so:
    the socket is closed when it shuts (the computer moved to a network
    nobody allowed) and bound again with `reopen` when it opens, read every
    `REFRESH_SECONDS` with `refresh` and at once after "Allow on this
    network". `sock` may then start as None.

    The address set is compared every `ADDRESS_SECONDS`; a change reads the
    network at once and calls `on_addresses` (INBOX 892: a certificate that
    names the new address). When the gate shuts, the connections already
    open are dropped as well as the port (INBOX 896)."""
    config = server.config
    context = config.ssl
    port = sock.getsockname()[1] if sock is not None else port
    running = asyncio.ensure_future(server.serve(sockets=[]))
    while not server.started and not running.done():
        await asyncio.sleep(0.02)

    def make_protocol() -> asyncio.Protocol:
        return config.http_protocol_class(
            config=config, server_state=server.server_state, app_state=server.lifespan.state
        )

    loop = asyncio.get_running_loop()
    if sock is not None:
        sock.setblocking(False)
    pending: set[asyncio.Task] = set()
    watch = {"refreshed": -REFRESH_SECONDS, "addresses": None}

    def look_again() -> None:
        """Off the loop: the address set, and the network when it changed or
        REFRESH_SECONDS have passed (both read this computer only)."""
        now = frozenset(_addresses_now())
        changed = watch["addresses"] is not None and now != watch["addresses"]
        watch["addresses"] = now
        if not changed and time.monotonic() - watch["refreshed"] < REFRESH_SECONDS:
            return
        watch["refreshed"] = time.monotonic()
        refresh_own_prefixes()
        if refresh is not None:
            with contextlib.suppress(Exception):
                refresh()
        if changed and on_addresses is not None:
            log.info("Other devices: this computer's addresses changed.")
            with contextlib.suppress(Exception):
                on_addresses()

    looked = -ADDRESS_SECONDS
    try:
        while not running.done() and not server.should_exit:
            if loop.time() - looked >= ADDRESS_SECONDS:
                looked = loop.time()
                await loop.run_in_executor(None, look_again)
            sock, verdict = await _port_step(sock, gate, reopen, port, server)
            if verdict == "break":
                break
            if verdict == "continue":
                continue
            accepted = await _accept(loop, sock)
            if accepted is None:
                continue
            conn, addr = accepted
            _record_incoming(addr[0])
            task = asyncio.ensure_future(_route(conn, make_protocol, context, port, plain_http, trust))
            pending.add(task)
            task.add_done_callback(pending.discard)
    finally:
        if sock is not None:
            sock.close()
        server.should_exit = True
        for task in list(pending):
            task.cancel()
        await asyncio.gather(running, *pending, return_exceptions=True)
