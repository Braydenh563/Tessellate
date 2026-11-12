"""Brief 40's leftovers: the trust page a QR code opens, the plain-http choice,
and the count of failed TLS handshakes.

The phone installs the authority once (`/lan/trust`, plain http, served only
while Settings has its window open); plain http for the app itself is the
person's choice, off by default; a handshake a phone refuses is counted so
"connection was lost" has a number beside it.
"""

from __future__ import annotations

import asyncio
import contextlib
import http.client
import socket
import ssl
import threading
import time

import pytest
import uvicorn

from tessellate.core import lancert, lanserve
from tests._app_js import app_js_text


async def _app(scope, receive, send):  # noqa: ANN001
    body = f"{scope['scheme']} {scope['path']}".encode()
    await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
    await send({"type": "http.response.body", "body": body})


class _Quiet(uvicorn.Server):
    def capture_signals(self):  # noqa: ANN202
        return contextlib.nullcontext()


@pytest.fixture()
def listener(tmp_path):
    """(start, data_dir): start(**serve_kwargs) -> port. One listener per test."""
    info = lancert.ensure(tmp_path, ["localhost", "127.0.0.1"])
    state: dict = {}

    def start(**kwargs) -> int:  # noqa: ANN003
        config = uvicorn.Config(
            _app, lifespan="off", log_level="warning",
            ssl_certfile=str(info.cert_path), ssl_keyfile=str(info.key_path),
        )
        config.load()
        server = _Quiet(config)
        sock = socket.create_server(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        thread = threading.Thread(target=lambda: asyncio.run(lanserve.serve(server, sock, **kwargs)), daemon=True)
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.02)
        state.update(server=server, thread=thread)
        return port

    yield start, tmp_path
    if "server" in state:
        state["server"].should_exit = True
        state["thread"].join(10)
    lanserve._stats["trust_until"] = 0.0  # noqa: SLF001


def _get(port, path, host=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.putrequest("GET", path, skip_host=True)
    conn.putheader("Host", host or f"127.0.0.1:{port}")
    conn.endheaders()
    response = conn.getresponse()
    body = response.read()
    conn.close()
    return response, body


def test_the_trust_page_and_the_certificate_answer_while_the_window_is_open(listener):
    start, data_dir = listener
    pem = lancert.authority_pem(data_dir)
    port = start(trust=lambda: (pem, "AA:BB"))
    lanserve.open_trust_page(60)
    page, body = _get(port, "/lan/trust")
    assert page.status == 200 and b"AA:BB" in body and b"/lan/trust/ca.crt" in body
    assert f"https://127.0.0.1:{port}/".encode() in body
    cert, blob = _get(port, "/lan/trust/ca.crt")
    assert cert.status == 200 and blob == pem
    assert cert.getheader("Content-Type") == "application/x-x509-ca-cert"


def test_the_trust_page_is_a_redirect_when_the_window_is_closed(listener):
    start, data_dir = listener
    port = start(trust=lambda: (lancert.authority_pem(data_dir), "AA"))
    response, _ = _get(port, "/lan/trust")
    assert response.status == 301


def test_the_trust_page_never_answers_a_host_that_is_not_this_computer(listener):
    start, data_dir = listener
    port = start(trust=lambda: (lancert.authority_pem(data_dir), "AA"))
    lanserve.open_trust_page(60)
    response, body = _get(port, "/lan/trust", host="evil.example")
    assert response.status == 400 and b"AA" not in body


def test_plain_http_is_the_redirect_unless_the_person_turned_it_on(listener):
    start, _ = listener
    off = start(plain_http=lambda: False)
    assert _get(off, "/notes")[0].status == 301


def test_plain_http_serves_the_app_when_it_is_on(listener):
    start, _ = listener
    port = start(plain_http=lambda: True)
    response, body = _get(port, "/notes")
    assert response.status == 200 and body == b"http /notes"


def test_a_handshake_a_client_refuses_is_counted(listener):
    start, _ = listener
    port = start()
    before = lanserve.handshake_failures()
    with pytest.raises(ssl.SSLError):
        conn = http.client.HTTPSConnection("127.0.0.1", port, context=ssl.create_default_context(), timeout=5)
        conn.request("GET", "/")
    deadline = time.monotonic() + 5
    while lanserve.handshake_failures() == before and time.monotonic() < deadline:
        time.sleep(0.05)
    assert lanserve.handshake_failures() == before + 1


def test_settings_draws_the_qr_the_count_and_the_plain_http_switch():
    js = app_js_text()
    assert "lan-trust-page" in js and "trust_url" in js
    assert "failed_handshakes" in js
    assert "account-lan-plain" in js and "plain_http" in js
