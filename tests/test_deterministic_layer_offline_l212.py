"""CHAT_PLAN decision 56 (L-chat-212): no network in the deterministic layer.
No module of the engine (composer, recogniser, reading, acts, realiser,
validators, utilities, filters) imports a network library, so a currency
or a unit is a dated table that says its date, never a lookup. Checked
over the import statements, top-level and inside functions."""

from __future__ import annotations

import ast
from pathlib import Path

AI = Path(__file__).resolve().parents[1] / "src" / "tessellate" / "ai"
NETWORK = {"httpx", "requests", "urllib3", "aiohttp", "socket", "http", "websockets", "websocket", "ftplib", "smtplib", "urllib.request"}
PREFIXES = (
    "composer", "recognise", "reading", "acts", "act_registry", "realise", "validate", "utilities", "filters", "find_it",
    "source_check", "when", "commands", "quantity", "guide_", "help_chat", "insights", "factgraph",
)


def _imports(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            found.add(node.module)
            found.update(f"{node.module}.{a.name}" for a in node.names)
    return found


def test_the_engine_imports_no_network_library():
    files = sorted(p for p in AI.glob("*.py") if p.name.startswith(PREFIXES))
    assert len(files) > 40, len(files)
    bad = {p.name: sorted(i for i in _imports(p) if i in NETWORK or i.split(".")[0] in NETWORK) for p in files}
    assert not {k: v for k, v in bad.items() if v}, bad
