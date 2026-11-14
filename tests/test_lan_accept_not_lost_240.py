"""The LAN accept loop never drops a connection it has accepted (L-world-class-240).

`_accept` waited for `loop.sock_accept` under a 0.5 s `wait_for`. When the
timeout landed in the same loop turn as the accept, the accepted socket was
dropped unread and closed: the client saw a reset in its TLS handshake and the
server logged nothing (CI on 3c57303c, test_lan_mode_end_to_end, the server
log tail showing no line for the lost connection). One accept now stays
pending across the ticks; a tick only stops waiting, never cancels it."""

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


def test_a_tick_without_a_connection_keeps_the_accept_pending():
    async def run():
        loop = asyncio.get_running_loop()
        sock = _listener()
        held = {}
        try:
            assert await lanserve._accept(loop, sock, held) is None
            task = held["task"]
            assert not task.cancelled() and not task.done()
            assert await lanserve._accept(loop, sock, held) is None
            assert held["task"] is task
        finally:
            lanserve._drop_accept(held)
            sock.close()

    asyncio.run(run())


def test_a_connection_that_arrives_at_the_tick_is_returned_on_the_next():
    async def run():
        loop = asyncio.get_running_loop()
        sock = _listener()
        held = {}
        client = socket.socket()
        try:
            assert await lanserve._accept(loop, sock, held) is None
            client.connect(sock.getsockname())
            got = None
            for _ in range(20):
                got = await lanserve._accept(loop, sock, held)
                if got:
                    break
            assert got is not None
            conn, addr = got
            assert addr[0] == "127.0.0.1"
            conn.close()
            assert "task" not in held
        finally:
            client.close()
            lanserve._drop_accept(held)
            sock.close()

    asyncio.run(run())


def test_the_accept_is_never_cancelled_by_a_timeout():
    source = Path(lanserve.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def _accept") :]
    body = body[: body.index("\nasync def ")]
    assert "wait_for(" not in body
