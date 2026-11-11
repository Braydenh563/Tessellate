"""Shapes CodeQL flags on every push, held here so the gate sees them first.

An `assert client.post(...).status_code == 200` puts the request inside the
assert: run with `python -O`, the request never happens and the test still
passes. CodeQL reports it as "an assert statement has a side-effect" on each
new one, and the agents writing tests reached for the shape often enough that
2026-10-05 alone brought seventeen. The rule is a ratchet: the count only goes
down. New tests make the request first and assert on its response.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

TESTS = Path(__file__).resolve().parent

#: The request inside the assert, on the client fixtures the suite uses.
SIDE_EFFECT_ASSERT = re.compile(r"^\s*assert (?:ai_)?client\.(?:delete|post|put|patch)\(", re.M)

#: The count on 2026-10-05, after the new ones were rewritten. Lower it when
#: you rewrite more; never raise it.
SIDE_EFFECT_ASSERTS_CAP = 226


def test_no_new_request_inside_an_assert():
    found = {
        path.name: len(SIDE_EFFECT_ASSERT.findall(path.read_text(encoding="utf-8")))
        for path in sorted(TESTS.glob("test_*.py"))
    }
    total = sum(found.values())
    assert total <= SIDE_EFFECT_ASSERTS_CAP, (
        f"{total} asserts make a request inside the assert (cap {SIDE_EFFECT_ASSERTS_CAP}): "
        "assign the response first, then assert on it. Files: "
        + ", ".join(f"{name} {n}" for name, n in found.items() if n)
    )


def test_the_shape_is_matched():
    # A pattern that silently matched nothing would pass forever.
    assert SIDE_EFFECT_ASSERT.search('    assert client.post("/x").status_code == 200\n')
    assert not SIDE_EFFECT_ASSERT.search('    response = client.post("/x")\n')


#: The names CodeQL's sensitive-data heuristics read as a secret, a password,
#: a certificate or an account (its HeuristicNames, abridged). The heuristic is
#: name-based and key-blind: an attribute or method named like this on the
#: settings path made every `get_preference` result "sensitive", so the
#: timezone, model and backend-address log lines that read one were 15
#: clear-text-logging alerts (PR 216).
SENSITIVE_NAME = re.compile(r"secret|token|pass(?:wd|word|code|phrase)|cert|acc(?:ou)?nt|private", re.I)


def _config_manager_names() -> set[str]:
    source = (TESTS.parent / "src" / "tessellate" / "core" / "config.py").read_text(encoding="utf-8")
    cls = next(
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ClassDef) and node.name == "ConfigManager"
    )
    names = {node.name for node in ast.walk(cls) if isinstance(node, ast.FunctionDef)}
    names |= {
        node.attr
        for node in ast.walk(cls)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self"
    }
    return names


def test_settings_path_has_no_secret_looking_names():
    # `get_preference` serves every setting, the two secret ones included;
    # what it reads from must not be named like a secret, or every caller's
    # log line is reported as logging one.
    flagged = sorted(name for name in _config_manager_names() if SENSITIVE_NAME.search(name))
    assert not flagged, f"ConfigManager names CodeQL reads as secrets: {flagged}"


def test_the_sensitive_name_shape_is_matched():
    assert SENSITIVE_NAME.search("_secrets") and SENSITIVE_NAME.search("_keep_secrets")
    assert not SENSITIVE_NAME.search("_kept_apart") and not SENSITIVE_NAME.search("get_preference")
