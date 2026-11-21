"""LAN mode on and off while the app runs, with no restart (INBOX 900).

The owner, 2026-10-11: "the outgoing lan connection should have a hotkey,
and should also be easily accessible", and its state "should change if the
user loses wifi or mobile data connection and or moves to an untrusted
network". The switch used to take effect at the next launch: the HTTPS
listener was built once in `__main__` beside the loopback one. Now the
launcher always runs `supervise` beside the loopback server, and it starts
or stops one `Listener` whenever the switch and the password say so:

- **On** builds what `__main__` used to build at launch: the certificate
  (core/lancert.py), the network gate (core/lantrust.py), the socket on
  `netbind.lan_port` (or the next free one), and a second uvicorn server fed
  by core/lanserve.py's accept loop.
- **Off** drops every connection another device holds, closes the socket and
  stops that server; this computer's own `http://127.0.0.1` never moves.

The routes (`/auth/lan-access`) change the preference and call `wake`, then
`wait_pass`, so the answer they send already says what is true. Without a
supervisor (tests, a container's `TESSELLATE_BIND`) nothing listens for the
wake and the old "restart to apply" answer stands.

Also here, because it needs the switch, the trust file and a clock:
**unused for `lantrust.UNUSED_DAYS` days, LAN mode switches itself off**
(secscan-1011's decision), leaving a notice for this computer.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
import time

log = logging.getLogger(__name__)

#: How often the supervisor looks again without being woken: a preference
#: changed some other way (an import, a reset that removed the password).
CHECK_SECONDS = 2.0
#: How often the unused clock is read.
UNUSED_CHECK_SECONDS = 600.0
#: How long a route waits for the supervisor to act on its change.
APPLY_SECONDS = 10.0
#: A listener that could not start is tried again after this long.
RETRY_SECONDS = 30.0
#: How long a stopping listener may take to close its connections.
STOP_SECONDS = 2.0

_lock = threading.Condition()
#: `ticket` counts wakes; `done` is the last ticket a finished pass had read.
_state: dict = {"attached": False, "running": False, "ticket": 0, "done": 0, "error": ""}
_wake: dict = {"loop": None, "event": None}


def attached() -> bool:
    """A supervisor is running in this process: the switch applies live."""
    return bool(_state["attached"])


def running() -> bool:
    return bool(_state["running"])


def last_error() -> str:
    return str(_state["error"] or "")


def wake() -> int:
    """Ask the supervisor to look now; returns the ticket `wait_pass` takes."""
    with _lock:
        _state["ticket"] += 1
        ticket = _state["ticket"]
    loop, event = _wake["loop"], _wake["event"]
    if loop is not None and event is not None:
        with contextlib.suppress(RuntimeError):  # the loop has closed
            loop.call_soon_threadsafe(event.set)
    return ticket


def wait_pass(ticket: int, timeout: float = APPLY_SECONDS) -> bool:
    """Wait until a supervisor pass that began after `wake` gave `ticket`
    has finished, so the change it asked for is in effect (or failed)."""
    deadline = time.monotonic() + timeout
    with _lock:
        while _state["attached"] and _state["done"] < ticket:
            left = deadline - time.monotonic()
            if left <= 0:
                return False
            _lock.wait(left)
    return True


def _set(**changes) -> None:  # noqa: ANN003
    with _lock:
        _state.update(changes)
        _lock.notify_all()


class Listener:
    """One LAN listener, built on `start` and gone after `stop`."""

    def __init__(self, uvicorn, app, config, *, local_port: int, announce=print) -> None:  # noqa: ANN001
        self.uvicorn = uvicorn
        self.app = app
        self.config = config
        self.local_port = local_port
        self.announce = announce
        self.server = None
        self.task: asyncio.Future | None = None
        self.failed_at = 0.0
        self.fingerprint = ""

    @property
    def active(self) -> bool:
        return self.task is not None

    def _reissue(self) -> None:
        """INBOX 892: joining a hotspot (or any new address) mid-run needs a
        certificate naming the new address, or the phone reports "wrong
        name" (Safari: "connection lost"). `ensure` keeps the authority the
        phone already trusts while it can vouch for the address (every
        private range), so only the server certificate is new."""
        from tessellate.core import lancert

        info = lancert.ensure(self.config.data_dir)
        if info.fingerprint != self.fingerprint and lancert.reload(info):
            log.info("Other devices: a certificate naming this computer's new address is in use.")
        self.fingerprint = info.fingerprint

    async def start(self) -> bool:
        """Open LAN mode. False (and stays local) when no port can be had."""
        import socket as socket_module

        from tessellate.core import lancert, lanserve, lantrust, netbind

        loop = asyncio.get_running_loop()
        data_dir = self.config.data_dir
        lan_port = netbind.lan_port(self.local_port)

        def prepare():  # noqa: ANN202
            #: INBOX 867: only on a network the person allowed. Elsewhere the
            #: port is not bound until "Allow on this network"; the accept
            #: loop opens and closes it as that changes.
            return lancert.ensure(data_dir), lantrust.refresh(data_dir, fresh=True)

        info, trust = await loop.run_in_executor(None, prepare)
        self.fingerprint = info.fingerprint
        requested = netbind.bind_host(self.config, has_password=True)

        def make_socket(port: int):  # noqa: ANN202
            #: LAN mode over IPv6 (WORLD_CLASS_PLAN §12, row 2): "::" is one
            #: dual-stack socket made here, since uvicorn's own bind of "::"
            #: is IPv6 only on Windows. If it cannot be made, IPv4 as before.
            made = netbind.listening_socket(requested, port)
            return made or socket_module.create_server(
                (netbind.ALL_INTERFACES if requested == netbind.ALL_INTERFACES_V6 else requested, port)
            )

        sock = None
        bind = requested
        if trust["open"]:
            #: A second notebook on this computer already holds 8443: take the
            #: next free port rather than staying local.
            first_error: OSError | None = None
            for candidate in netbind.lan_port_candidates(lan_port):
                try:
                    sock = make_socket(candidate)
                except OSError as exc:
                    first_error = first_error or exc
                    continue
                lan_port = candidate
                break
            if sock is None:
                log.warning(
                    "Other devices can't reach this notebook: port %s and the next %s are taken (%s). "
                    "Listening on this computer only.", lan_port, netbind.LAN_PORT_TRIES - 1, first_error,
                )
                self.failed_at = time.monotonic()
                _set(error="port_taken")
                return False
            if requested == netbind.ALL_INTERFACES_V6 and sock.family != socket_module.AF_INET6:
                bind = netbind.ALL_INTERFACES
        netbind.set_current(bind)
        netbind.set_lan_port(lan_port)
        # Printed, not only logged: the terminal is where the person starting
        # the app looks, and the fingerprint is what they compare on the phone.
        if sock is None:
            label = (trust.get("network") or {}).get("label") or "this network"
            self.announce(
                f"Other devices are not let in on {label} yet ({trust['reason'].replace('_', ' ')}). "
                "To allow them, open Settings, Account & security, Other devices, and choose Allow on this network.\n"
                f"The certificate's fingerprint, to compare on the other device: {info.fingerprint}",
                flush=True,
            )
        else:
            shown = netbind.order_addresses(
                netbind.lan_addresses(include_v6=sock.family == socket_module.AF_INET6), lantrust.current_network()
            )
            addresses = ", ".join(f"https://{netbind.url_host(a)}:{lan_port}" for a in shown) or bind
            self.announce(
                f"Other devices on this network can open this notebook (with the password, over HTTPS): {addresses}\n"
                f"The certificate's fingerprint, to compare on the other device: {info.fingerprint}",
                flush=True,
            )

        class _NoSignals(self.uvicorn.Server):
            """The LAN server leaves Ctrl+C and SIGTERM to the loopback one,
            whose exit ends the supervisor and so this server too."""

            def capture_signals(self):  # noqa: ANN202
                return contextlib.nullcontext()

        lan_config = self.uvicorn.Config(
            self.app,
            host=bind,
            port=lan_port,
            log_level="info",
            lifespan="off",  # the app starts and stops once, with the loopback server
            ssl_certfile=str(info.cert_path),
            ssl_keyfile=str(info.key_path),
            #: Switching off must not wait on a phone's open stream.
            timeout_graceful_shutdown=STOP_SECONDS,
        )
        lan_config.load()
        # "Regenerate certificate" in Settings reaches this context (lancert.reload).
        lancert.set_live_context(lan_config.ssl)
        self.server = _NoSignals(lan_config)
        port = lan_port
        self.task = asyncio.ensure_future(
            lanserve.serve(
                self.server, sock, port=port, gate=lantrust.is_open,
                refresh=lambda: lantrust.refresh(data_dir), reopen=lambda: make_socket(port),
                on_addresses=self._reissue,
            )
        )
        self.failed_at = 0.0
        _set(running=True, error="")
        lantrust.touch_version()
        log.info("Other devices: LAN mode is on (port %s).", lan_port)
        return True

    async def stop(self) -> None:
        """Close LAN mode: every open connection from another device, the
        socket, and the server behind them."""
        from tessellate.core import lancert, lanserve, lantrust, netbind

        if self.task is None:
            return
        server, task = self.server, self.task
        dropped = lanserve.drop_connections(server)
        server.should_exit = True
        try:
            await asyncio.wait_for(asyncio.shield(task), STOP_SECONDS * 3)
        except asyncio.TimeoutError:
            task.cancel()
            #: Wait for the cancelled task to finish; `wait` does not re-raise what it ended with.
            await asyncio.wait([task])
        except Exception:  # noqa: BLE001  # a listener that had failed is stopped all the same
            log.debug("the LAN listener ended with an error", exc_info=True)
        self.server = self.task = None
        lancert.set_live_context(None)
        netbind.set_lan_port(None)
        netbind.set_current(netbind.LOOPBACK)
        _set(running=False)
        lantrust.touch_version()
        log.info("Other devices: LAN mode is off (%s open connection(s) closed).", dropped)


def switch_off_if_unused(config, now: float | None = None) -> bool:  # noqa: ANN001
    """Turn LAN mode off when no device has connected for UNUSED_DAYS days.
    A switch with no start time (turned on before this was kept) starts the
    clock now rather than closing at once."""
    from tessellate.core import lantrust, netbind

    if not netbind.lan_enabled(config):
        return False
    data_dir = config.data_dir
    lantrust.persist_use(data_dir)
    state = lantrust.load(data_dir)
    since = lantrust.unused_since(state)
    if not since:
        lantrust.mark_turned_on(data_dir)
        return False
    if (now if now is not None else time.time()) - since < lantrust.UNUSED_DAYS * 86400:
        return False
    config.set_preference(netbind.LAN_PREF, False)
    lantrust.mark_switched_off(data_dir)
    log.warning(
        "Other devices: no device has opened this notebook for %s days, so LAN mode switched itself off.",
        lantrust.UNUSED_DAYS,
    )
    return True


async def supervise(listener: Listener, *, wanted, should_exit) -> None:  # noqa: ANN001
    """Run beside the loopback server until `should_exit()`: start or stop
    `listener` as `wanted()` (the switch is on and a password exists) says,
    at once on `wake`, else every CHECK_SECONDS."""
    loop = asyncio.get_running_loop()
    event = asyncio.Event()
    _wake.update(loop=loop, event=event)
    _set(attached=True)
    clock = {"unused": -UNUSED_CHECK_SECONDS}

    def look() -> bool:
        """Off the loop: the unused clock now and then, then the switch."""
        if time.monotonic() - clock["unused"] >= UNUSED_CHECK_SECONDS:
            clock["unused"] = time.monotonic()
            with contextlib.suppress(Exception):
                switch_off_if_unused(listener.config)
        try:
            return bool(wanted())
        except Exception:  # noqa: BLE001  # an unreadable answer is "no"
            return False

    try:
        while not should_exit():
            woken = event.is_set()
            event.clear()
            with _lock:
                taking = _state["ticket"]
            want = await loop.run_in_executor(None, look)
            if listener.active and listener.task.done():
                log.warning("Other devices: the LAN listener stopped on its own; starting it again.")
                await listener.stop()
            if want and not listener.active:
                if woken or not listener.failed_at or time.monotonic() - listener.failed_at >= RETRY_SECONDS:
                    try:
                        await listener.start()
                    except Exception:  # noqa: BLE001  # the app keeps running on this computer
                        log.warning("Other devices: LAN mode could not start", exc_info=True)
                        listener.failed_at = time.monotonic()
                        _set(error="failed")
            elif not want and listener.active:
                await listener.stop()
            with _lock:
                _state["done"] = max(_state["done"], taking)
                _lock.notify_all()
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(event.wait(), CHECK_SECONDS)
    finally:
        _wake.update(loop=None, event=None)
        await listener.stop()
        _set(attached=False)
