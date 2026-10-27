"""Every way the backend can reach the network, pinned, and none of them on by default.

The owner, 2026-10-05: "make sure it is fully local and doesn't use any
external libraries that aren't vendored". `tests/test_offline_promise.py`
pins the two opt-in switches and the copy that describes them; this pins the
code underneath: every module that can open an outbound connection, what it
talks to, and what has to happen first. A module that gains a network
library and is not in `INVENTORY` fails here until somebody has written down
where it goes and who asked for it.

The rule each row is held to: a request goes either to the person's own
configured model server (on this computer unless they typed another
address), or to a URL the person asked for, with a click or a switch that is
off out of the box. Nothing phones home by default, and the second test
proves that on a booted app rather than by reading.
"""

from __future__ import annotations

import ast
import ipaddress
import socket
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from tests._repo_files import repo_files

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "tessellate"

#: The libraries that open connections. `socket.create_connection` is listed
#: as the call, since `socket` itself is everywhere.
NETWORK_MODULES = frozenset({
    "requests", "httpx", "urllib.request", "http.client", "aiohttp",
    "huggingface_hub", "ftplib", "smtplib", "fsspec", "urllib3", "websockets",
})

#: file -> (where it connects, what has to happen first). Kept short and
#: true; the module docstrings say the rest.
INVENTORY = {
    "__main__.py": ("this computer only (the launcher's own health checks, no proxy)", "always; loopback"),
    "core/instance_lock.py": ("this computer only (the running instance)", "a second launch; loopback"),
    "core/netbind.py": ("nothing outbound: the listening socket for LAN mode", "the password-gated switch"),
    "api/routes_bench.py": (
        "this server itself over 127.0.0.1, its own port (never the Host header)",
        "GET /models/bench/budgets?live=true, the interaction budgets timed on the person's notebook",
    ),
    "ai/captions.py": (
        "the whisper.cpp captions helper at TESSELLATE_CAPTIONS_URL, refused unless it is this computer (loopback)",
        "Live captions started from the palette, and a status probe while the captions dock is open",
    ),
    "ai/provider_http.py": (
        "the person's model server: Ollama at localhost:11434 or an OpenAI-compatible one at localhost:1234 unless they typed another address",
        "a chat, an embedding, a model list",
    ),
    "api/routes_update.py": ("api.github.com and the release download", "update_check_enabled (off until the ask-once question is answered yes) or a Check for updates / Install click"),
    "core/embedmodels.py": (
        "huggingface.co (an allowlisted model, or the metadata and files of a repo typed into Pull a model by name)",
        "an Install, Reinstall or Pull click in Settings, or a yes to the one-time question about search by meaning",
    ),
    "core/extra_downloads.py": ("the pinned URL of an allowlisted extra, sha256 checked", "an Install click in Settings, Extras"),
    "core/privacy_http.py": ("whatever its caller names; records each destination on the privacy receipt", "its callers' triggers"),
    "core/webclip.py": ("the page the person clipped, or the agent's read_url", "web_search_enabled (off by default)"),
    "search/websearch.py": ("the search engine the person chose", "web_search_enabled (off by default)"),
    "search/searxng_install.py": ("github.com (SearXNG's source) and pypi.org", "an Install click for local SearXNG"),
}


def _network_files() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for path in repo_files(SRC, suffixes=(".py",)):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names: set[str] = set()
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                modules = [node.module]
            for module in modules:
                if module in NETWORK_MODULES or module.split(".", 1)[0] in NETWORK_MODULES:
                    names.add(module)
            if (
                isinstance(node, ast.Attribute)
                and node.attr in ("create_connection", "create_server")
                and isinstance(node.value, ast.Name)
                and node.value.id == "socket"
            ):
                names.add(f"socket.{node.attr}")
        if names:
            found[path.relative_to(SRC).as_posix()] = names
    return found


def test_every_module_that_can_reach_the_network_is_accounted_for():
    found = _network_files()
    unlisted = sorted(set(found) - set(INVENTORY))
    assert not unlisted, (
        f"{unlisted} can open a network connection and is not in INVENTORY: "
        "add it with where it connects and what has to happen first"
    )
    stale = sorted(set(INVENTORY) - set(found))
    assert not stale, f"{stale} no longer reach the network: take them out of INVENTORY"


def test_the_defaults_are_local_and_off(app_state):
    from tessellate.ai import ollama_client, openai_client
    # "Ask once" (the owner, 2026-10-05): `auto_update_enabled`, which the
    # launchers' own pull obeys, is off for every install, a source checkout
    # included, until the one-time question is answered (`update_choice_made`).
    for key in ("web_search_enabled", "update_check_enabled", "auto_update_enabled", "update_choice_made"):
        assert app_state.get_preference(key, None) is False, key
    assert app_state.get_preference("llm_provider", None) == "ollama"
    assert app_state.get_preference("llm_base_url", None) == ""
    import inspect

    assert inspect.signature(ollama_client.OllamaClient.__init__).parameters["base_url"].default.startswith("http://localhost:")
    assert inspect.signature(openai_client.OpenAICompatClient.__init__).parameters["base_url"].default.startswith("http://localhost:")


def _is_local(host: str) -> bool:
    host = (host or "").strip("[]").lower()
    if host in ("localhost", "testserver", ""):
        return True
    try:
        return ipaddress.ip_address(host.split("%", 1)[0]).is_loopback
    except ValueError:
        return False


def test_a_booted_app_reaches_nothing_beyond_this_computer(app_state, monkeypatch):
    """A fresh notebook, started and used: every connection attempt and every
    name lookup is recorded, and none may leave loopback."""
    #: The search model no longer downloads on a note's first save: it waits
    #: for a yes (the owner, 2026-10-27), so this needs no environment switch
    #: and a machine without the model stays on keywords. Before, it passed
    #: where the model was cached and reached huggingface.co where it was not
    #: (CI, 2026-10-26) unless the variable was set.
    monkeypatch.delenv("TESSELLATE_NO_AUTO_INSTALL", raising=False)
    attempts: list[str] = []
    real_connect = socket.socket.connect
    real_getaddrinfo = socket.getaddrinfo

    def connect(self, address):
        if isinstance(address, tuple):
            attempts.append(str(address[0]))
        return real_connect(self, address)

    def getaddrinfo(host, *args, **kwargs):
        attempts.append(str(host))
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)

    from tessellate.api.app import create_app

    with TestClient(create_app()) as client:
        token = client.post("/auth/setup", json={"password": "a long password"}).json()["token"]
        headers = {"X-Auth-Token": token}
        client.post("/entries", json={"content": "a note about bread"}, headers=headers)
        for path in ("/health", "/auth/status", "/entries?limit=5", "/preferences", "/privacy/receipt", "/search?q=bread"):
            client.get(path, headers=headers)
    outside = sorted({host for host in attempts if not _is_local(host)})
    assert outside == [], f"reached beyond this computer with nothing switched on: {outside}"


@pytest.mark.parametrize("name", sorted(INVENTORY))
def test_each_row_says_where_and_when(name):
    where, when = INVENTORY[name]
    assert where.strip() and when.strip()
