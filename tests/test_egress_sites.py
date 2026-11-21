"""Every outbound call site names what it is for (trust contract rule, L659).

`test_egress_call_sites.py` looks at files, so one named call hid a second
unnamed one beside it. This looks at call sites: each function that opens a
connection (requests, urllib, http.client, httpx, sockets, the model hub) is
either inside `egress.labelled` / `with egress.purpose(...)`, so the receipt
says what it was for, or it is in `SITES` below with the reason it needs no
label (loopback, or its caller names the purpose). A new site that is on
neither side fails; a line whose site is gone or became labelled fails too.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests._repo_files import repo_files

SRC = Path(__file__).resolve().parents[1] / "src" / "tessellate"

_MODULE_CALLS = {
    "requests": {"get", "post", "put", "delete", "head", "request", "Session"},
    "urllib.request": {"urlopen"},
    "socket": {"create_connection"},
    "http.client": {"HTTPConnection", "HTTPSConnection"},
    "httpx": {"get", "post", "put", "delete", "head", "request", "Client", "AsyncClient", "stream"},
}
_BARE_CALLS = {"urlopen", "hf_hub_download", "snapshot_download", "create_connection"}
#: `from tessellate.ai import provider_http as requests` is still the requests API.

#: file::function -> why it needs no label of its own. Loopback means it only
#: ever talks to this computer; "caller" means a caller inside a purpose block
#: or a labelled function. Never add a line for new code that can be labelled.
SITES: dict[str, str] = {
    "__main__.py::_localhost_works": "loopback: the launcher checks its own port",
    "__main__.py::_port_holder": "loopback: asks whoever holds this computer's port",
    "__main__.py::_wait_for_server": "loopback: waits for this app's own port",
    "__main__.py::_wait_for_server_with_progress": "loopback: waits for this app's own port",
    "ai/captions.py::_http": "loopback: the captions helper, refused unless it is this computer",
    "api/routes_bench.py::loopback": "loopback: this server's own port, timing its own routes",
    "api/routes_update.py::_open": "caller: _download and _fetch_signature are labelled",
    "api/routes_update.py::_fetch_release_answer": "caller: the labelled release check and version list",
    "core/extra_downloads.py::_open_url": "caller: _fetch runs inside egress.purpose in the installer",
    "core/webclip.py::_new_session": "session factory: its two callers are labelled",
    "search/websearch.py::_private_session": "session factory: web search and the reader are labelled",
}


def _dotted(node: ast.AST) -> str:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _is_named(node: ast.AST) -> bool:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for deco in node.decorator_list:
            target = deco.func if isinstance(deco, ast.Call) else deco
            if _dotted(target).endswith(("egress.labelled", "egress.purpose")):
                return True
    if isinstance(node, ast.With):
        return any(
            isinstance(item.context_expr, ast.Call) and _dotted(item.context_expr.func).endswith("egress.purpose")
            for item in node.items
        )
    return False


def _is_outbound(call: ast.Call) -> bool:
    name = _dotted(call.func)
    if name in _BARE_CALLS:
        return True
    head, _, tail = name.rpartition(".")
    return tail in _MODULE_CALLS.get(head, ())


def _sites() -> dict[str, tuple[bool, int]]:
    """file::qualified function -> (named, first line)."""
    found: dict[str, tuple[bool, int]] = {}

    def visit(node: ast.AST, rel: str, scope: list[str], named: bool) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            scope = [*scope, node.name]
        named = named or _is_named(node)
        if isinstance(node, ast.Call) and _is_outbound(node):
            key = f"{rel}::{'.'.join(scope) or '<module>'}"
            old = found.get(key)
            found[key] = (named and (old is None or old[0]), old[1] if old else node.lineno)
        for child in ast.iter_child_nodes(node):
            visit(child, rel, scope, named)

    for path in repo_files(SRC, suffixes=(".py",)):
        text = path.read_text(encoding="utf-8")
        if "provider_http as requests" in text:
            continue  # its `requests` is provider_http, whose one send is labelled
        visit(ast.parse(text), path.relative_to(SRC).as_posix(), [], False)
    return found


def test_every_outbound_call_site_names_its_purpose_or_says_why_not():
    bad = sorted(f"{k} (line {line})" for k, (named, line) in _sites().items() if not named and k not in SITES)
    assert not bad, (
        "outbound call with no egress.labelled / egress.purpose; label it, or list it in SITES with the reason: "
        f"{bad}"
    )


def test_the_sites_list_has_no_stale_lines():
    sites = _sites()
    stale = sorted(k for k in SITES if k not in sites or sites[k][0])
    assert not stale, f"remove from SITES (gone, or labelled now): {stale}"
    assert all(SITES.values()), "every SITES line says why"
