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


# The same rebuild-every-poll on the other progress surfaces (INBOX 1776).
# Measured with a fake transport over 15 s, Playwright, scrollHeight and
# scrollTop sampled every 250 ms:
#   Packages spell-fr / ocr rows: scrollHeight 4823, 0 rows replaced (above).
#   Model cards (/models/status pulls): scrollHeight 3531, 0 cards replaced
#     (modelCardFor keeps a card by signature, the bar updated in place).
#   OCR engine line (workspace host): 16 of 16 ticks replaced the bar before,
#     0 after; host height 44px throughout.
#   Embedding switch rows: scrollHeight 3256 throughout, 15 of 15 rows replaced
#     per tick before, 0 after.
OCR_JS = (ROOT / "frontend/js/ocr-engine.js").read_text(encoding="utf-8")
EMBED_JS = (ROOT / "frontend/js/embed-choices.js").read_text(encoding="utf-8")


def test_ocr_engine_install_line_is_kept_between_ticks():
    paint = OCR_JS[OCR_JS.index("function ocrEnginePaint(host)") : OCR_JS.index("function ocrEnginePaintFailure")]
    fast = paint.index("host._ocrInstalling === installingNow")
    assert fast < paint.index("host.replaceChildren()")
    assert "keptDetail.textContent" in paint
    assert "host._ocrInstalling = ocrEngineInstall.extra" in paint


def test_embed_rows_painted_in_place_while_a_switch_runs():
    render = EMBED_JS[EMBED_JS.index("async function renderEmbedChoices") : EMBED_JS.index("function embedRowKey")]
    assert "embedPaintRows(list, body, now)" in render
    assert "list.replaceChildren(...body.choices" not in render
    # The switch's progress is not part of a row's identity, or every tick rebuilds it.
    key = EMBED_JS[EMBED_JS.index("function embedRowKey") : EMBED_JS.index("function embedPaintRows")]
    assert "const { done, started, ...rest } = body.switch" in key
    paint = EMBED_JS[EMBED_JS.index("function embedPaintRows") : EMBED_JS.index("function embedPaintProgress")]
    assert "kept._embedKey === key" in paint and "embedPaintProgress(" in paint
