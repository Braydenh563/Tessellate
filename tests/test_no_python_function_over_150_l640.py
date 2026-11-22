"""LEDGER L640 (K25): no function in src/ runs over 150 lines. The ten long
functions were split in K24/K25 (HISTORY, 2026-11-11); this keeps it so."""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
BAR = 150


def test_no_function_in_src_is_over_the_bar():
    long = []
    for path in SRC.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                length = node.end_lineno - node.lineno + 1
                if length > BAR:
                    long.append(f"{path.relative_to(SRC)}:{node.lineno} {node.name} {length}")
    assert not long, long
