"""Source text: this test reads test files and gate.sh as text, because the rule it keeps is about their words (a docstring), not behaviour. A new test that reads source text says, in its docstring, why.

A test that greps a file proves a string exists, not that the app works.
Some must (lints over CSS, CSP, load order, packaging text), so the rule is
"say why": a source-text test file not in `tests/source_text_baseline.txt`
opens its module docstring with "Source text:" and gives the reason
behaviour cannot be asserted (L-general-9). Never add to the baseline to
dodge this; the baseline is the files that existed on 2026-11-12.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import source_text_tests  # noqa: E402


def test_new_source_text_tests_say_why():
    baseline = set(source_text_tests.BASELINE.read_text(encoding="utf-8").split())
    missing = []
    for name in source_text_tests.source_text_files():
        if name in baseline:
            continue
        doc = ast.get_docstring(ast.parse((source_text_tests.TESTS / name).read_text(encoding="utf-8"))) or ""
        if not doc.startswith("Source text:") or len(doc) < 40:
            missing.append(name)
    assert not missing, f'start the module docstring with "Source text: <why behaviour cannot be asserted>": {missing}'


def test_the_gate_prints_the_count():
    assert "source_text_tests.py" in (ROOT / "scripts" / "gate.sh").read_text(encoding="utf-8")
    assert source_text_tests.source_text_files()
