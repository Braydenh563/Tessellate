"""The LAN accept loop never drops a connection it has accepted (L-world-class-240).

`_accept` waited for `loop.sock_accept` under a 0.5 s `wait_for`. When the
timeout landed in the same loop turn as the accept, the accepted socket was
dropped unread and closed: the client saw a reset in its TLS handshake and the
server logged nothing (CI on 3c57303c, test_lan_mode_end_to_end, the server
log tail showing no line for the lost connection). The non-blocking socket is
now asked directly, so no accept is pending when a tick ends and none can be
cancelled; an untaken connection waits in the kernel's backlog."""

import asyncio
from pathlib import Path
import socket

from tessellate.core import lanserve


def _listener() -> socket.socket:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(8)
    sock.setblocking(False)
    return sock


def test_a_tick_without_a_connection_leaves_nothing_pending():
    async def run():
        loop = asyncio.get_running_loop()
        sock = _listener()
        try:
            before = len(asyncio.all_tasks())
            assert await lanserve._accept(loop, sock) is None
            assert len(asyncio.all_tasks()) == before
        finally:
            sock.close()

    asyncio.run(run())


def test_a_connection_that_arrives_between_ticks_is_returned_on_the_next():
    async def run():
        loop = asyncio.get_running_loop()
        sock = _listener()
        client = socket.socket()
        try:
            assert await lanserve._accept(loop, sock) is None
            client.connect(sock.getsockname())
            got = await lanserve._accept(loop, sock)
            assert got is not None
            conn, addr = got
            assert addr[0] == "127.0.0.1"
            assert conn.getblocking() is False
            conn.close()
        finally:
            client.close()
            sock.close()

    asyncio.run(run())


def test_the_accept_has_no_timeout_to_cancel_and_no_task():
    source = Path(lanserve.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def _accept") :]
    body = body[: body.index("\nasync def ")]
    assert "wait_for(" not in body
    assert "ensure_future(" not in body
    assert "create_task(" not in body
