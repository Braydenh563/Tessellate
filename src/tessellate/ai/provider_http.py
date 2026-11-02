"""`requests`, for the model backends, with redirects held to the address asked.

WORLD_CLASS_PLAN §12, S6. The model backend's address is one the person set,
and it is on this machine or this network by design (`local_only_ai`,
`security.check_backend_url`), so the address itself is not the risk. A
redirect is. `requests` follows one to anywhere unless told otherwise, so a
server at the configured address, or anything able to answer as it, could send
the app's next request on to another host: prompts carrying notes to a
different machine on the LAN, or a probe to the cloud metadata address the
backend check refuses when it is typed in directly.

So the two provider clients import this module in place of `requests`
(`from tessellate.ai import provider_http as requests`), and every call they
make carries one response hook: a redirect whose target is not the same
scheme, host and port as the response that sent it is refused with a reason,
before `requests` follows it. A redirect on the same address (a moved path, a
trailing slash) is still followed, because local servers do send those.

A module rather than a keyword at each of the fifteen call sites, for two
reasons. The call sites stay as they read. And the tests' fakes, which patch
`openai_client.requests.post` with fixed signatures, patch this module's
`post` exactly as they patched the real one, and see the same arguments.
"""

from __future__ import annotations

import socket
import threading
from urllib.parse import urljoin, urlsplit

import requests
from requests import ConnectTimeout, HTTPError, ReadTimeout, RequestException, Response
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from requests import ConnectionError as RefusedError

__all__ = [
    "Cancelled", "ConnectTimeout", "HTTPError", "OffHostRedirect", "ReadTimeout", "RefusedError", "RequestException", "Response",
    "delete", "get", "post",
]

_DEFAULT_PORTS = {"http": 80, "https": 443}


class OffHostRedirect(RequestException):
    """A model server tried to send a request somewhere else. Caught wherever
    `requests.RequestException` already is, so it reads as a failed call."""


def _address(url: str) -> tuple[str, str, int | None]:
    parts = urlsplit(url)
    scheme = (parts.scheme or "").lower()
    try:
        port = parts.port or _DEFAULT_PORTS.get(scheme)
    except ValueError:
        port = None
    return scheme, (parts.hostname or "").lower(), port


def refuse_off_host_redirect(response: Response, *args, **kwargs) -> Response:  # noqa: ANN002, ANN003
    """The response hook: runs on every response, the redirects included,
    before `requests` decides whether to follow one."""
    if not response.is_redirect:
        return response
    target = urljoin(response.url, response.headers.get("location", ""))
    if _address(target) != _address(response.url):
        _scheme, here, _port = _address(response.url)
        response.close()
        raise OffHostRedirect(
            f"The model server at {here} answered with a redirect to another "
            "address, which is not followed. Point the app at the address it "
            "redirects to, if that is the right server.",
            response=response,
        )
    return response


def _guarded(kwargs: dict) -> dict:
    hooks = dict(kwargs.get("hooks") or {})
    existing = hooks.get("response") or []
    if callable(existing):
        existing = [existing]
    hooks["response"] = [refuse_off_host_redirect, *existing]
    return {**kwargs, "hooks": hooks}


class Cancelled(RequestException):
    """The call was stopped (Stop, a closed tab) or ran out of its deadline.
    Caught wherever `RequestException` already is, so it reads as a failed
    call and each caller's own fallback runs."""


class _Cut:
    """The sockets one call has open, so a stop can shut them at once. A call
    blocked waiting for the model's first byte has no response object to
    close yet; the socket is the only handle on it."""

    def __init__(self) -> None:
        self.cancelled = False
        self._socks: list = []
        self._lock = threading.Lock()

    def add(self, sock) -> None:  # noqa: ANN001
        with self._lock:
            self._socks.append(sock)
            cancelled = self.cancelled
        if cancelled:
            self._shut(sock)

    def cut(self) -> None:
        with self._lock:
            self.cancelled = True
            socks = list(self._socks)
        for sock in socks:
            self._shut(sock)

    @staticmethod
    def _shut(sock) -> None:  # noqa: ANN001
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass  # already closed by the other side: nothing left to cut


_tls = threading.local()


def _note_socket(connection) -> None:  # noqa: ANN001
    cut = getattr(_tls, "cut", None)
    if cut is not None and connection.sock is not None:
        cut.add(connection.sock)


class _Conn(HTTPConnection):
    def connect(self) -> None:
        super().connect()
        _note_socket(self)


class _SecureConn(HTTPSConnection):
    def connect(self) -> None:
        super().connect()
        _note_socket(self)


class _Pool(HTTPConnectionPool):
    ConnectionCls = _Conn


class _SecurePool(HTTPSConnectionPool):
    ConnectionCls = _SecureConn


_POOLS = {"http": _Pool, "https": _SecurePool}


class _Adapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = _POOLS

    def proxy_manager_for(self, proxy, **kwargs):  # noqa: ANN001, ANN003, ANN202
        manager = super().proxy_manager_for(proxy, **kwargs)
        manager.pool_classes_by_scheme = _POOLS
        return manager


def _stop_events() -> list:
    from tessellate.core import activity, deadline

    return [event for event in (activity.current_stop_event(), deadline.current()) if event is not None]


def _send(method: str, url: str, kwargs: dict) -> Response:
    kwargs = _guarded(kwargs)
    events = _stop_events()
    if not events:
        return requests.request(method, url, **kwargs)
    cut = _Cut()
    _tls.cut = cut
    removers = [event.add_hook(cut.cut) for event in events]
    try:
        if cut.cancelled:
            raise Cancelled("The model call was stopped before it started.")
        with requests.Session() as session:
            adapter = _Adapter()
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            response = session.request(method, url, **kwargs)
        # A streamed body is still being read: its hook stays until the flag
        # fires or the run ends, so a deadline can cut a stream too.
        if not kwargs.get("stream"):
            for remove in removers:
                remove()
        return response
    except RequestException as exc:
        for remove in removers:
            remove()
        if cut.cancelled and not isinstance(exc, Cancelled):
            raise Cancelled("The model call was stopped.") from exc
        raise
    finally:
        _tls.cut = None


def get(url: str, **kwargs) -> Response:  # noqa: ANN003
    return _send("GET", url, kwargs)


def post(url: str, **kwargs) -> Response:  # noqa: ANN003
    return _send("POST", url, kwargs)


def delete(url: str, **kwargs) -> Response:  # noqa: ANN003
    return _send("DELETE", url, kwargs)
