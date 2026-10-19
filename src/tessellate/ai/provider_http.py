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

from urllib.parse import urljoin, urlsplit

import requests
from requests import ConnectTimeout, HTTPError, ReadTimeout, RequestException, Response
from requests import ConnectionError as RefusedError

__all__ = [
    "ConnectTimeout", "HTTPError", "OffHostRedirect", "ReadTimeout", "RefusedError", "RequestException", "Response",
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


def get(url: str, **kwargs) -> Response:  # noqa: ANN003
    return requests.request("GET", url, **_guarded(kwargs))


def post(url: str, **kwargs) -> Response:  # noqa: ANN003
    return requests.request("POST", url, **_guarded(kwargs))


def delete(url: str, **kwargs) -> Response:  # noqa: ANN003
    return requests.request("DELETE", url, **_guarded(kwargs))
