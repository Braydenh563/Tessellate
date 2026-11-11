"""INBOX 1776: the packages list must not be rebuilt on every install poll.

Measured before the fix (Playwright, the OCR row installed, an install faked
over 15 s): every 1.5 s tick rebuilt all rows, the OCR language picker
re-fetched its content, and the scroll height flipped 4823 <-> 4829 twenty
times. After: zero changes.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "frontend/js/settings-packages.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend/css/00-tokens-shell.css").read_text(encoding="utf-8")


def _body(name: str) -> str:
    start = JS.index(f"function {name}(")
    return JS[start : JS.index("\n  }\n", start)]


def test_poll_paints_rows_in_place():
    render = JS[JS.index("async function renderExtras") : JS.index("// --- dictation model sizes")]
    assert "packagesPaintRows(list, body)" in render
    assert "list.replaceChildren(...body.extras.map" not in render


def test_unchanged_rows_are_kept_and_the_step_swapped():
    paint = _body("packagesPaintRows")
    assert "kept._packagesKey === key" in paint
    assert ".extras-install-progress-text" in paint and "textContent" in paint
    assert "innerHTML" not in paint
    # The step text is not part of a row's identity, or every tick rebuilds it.
    assert "const { step, ...rest } = extra;" in _body("packagesRowKey")


def test_progress_numbers_do_not_shift_the_line():
    rule = CSS[CSS.index(".extras-install-progress-text {") :]
    rule = rule[: rule.index("}")]
    assert "font-variant-numeric: tabular-nums" in rule
