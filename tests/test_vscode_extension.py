"""The VS Code extension (editors/vscode) calls Tessellate's own routes: a
rename here must fail CI rather than break the extension silently."""

from __future__ import annotations

import json
import re
import subprocess
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
EXT = ROOT / "editors" / "vscode"


def _routes(client) -> dict[str, set[str]]:
    paths = client.get("/openapi.json").json()["paths"]
    return {path: {method.upper() for method in methods} for path, methods in paths.items()}


def _client_routes() -> dict[str, str]:
    block = re.search(r"const ROUTES = \{(.*?)\};", (EXT / "lib/client.js").read_text(), re.S).group(1)
    return dict(re.findall(r'(\w+): "(/[^"]*)"', block))


def test_every_route_the_client_calls_exists(client) -> None:
    routes = _routes(client)
    wanted = {
        "status": "GET",
        "unlock": "POST",
        "entries": "POST",
        "search": "GET",
    }
    assert set(_client_routes()) == set(wanted)
    for name, path in _client_routes().items():
        assert wanted[name] in routes.get(path, set()), f"{wanted[name]} {path} is gone from the app"
    assert "GET" in routes["/entries/{entry_id}"]


def test_package_is_agpl_and_local_only() -> None:
    package = json.loads((EXT / "package.json").read_text())
    assert package["license"].startswith("AGPL-3.0")
    assert package["main"] == "./extension.js"
    declared = {c["command"] for c in package["contributes"]["commands"]}
    used = set(re.findall(r'registerCommand\(name|command\("(tessellate\.\w+)"', (EXT / "extension.js").read_text()))
    assert declared == used - {""}
    source = (EXT / "extension.js").read_text() + (EXT / "lib/client.js").read_text()
    assert not re.search(r"https?://(?!127\.0\.0\.1)[\w.-]", source), "the extension may only talk to this computer"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_client_node_tests_pass() -> None:
    done = subprocess.run(["node", "--test", "test/client.test.js"], cwd=EXT, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout[-1500:]
