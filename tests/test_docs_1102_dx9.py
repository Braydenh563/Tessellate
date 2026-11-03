"""Documents audit 1102 DX9: the Word export keeps the document's structure.

Measured in Chromium by `scratchpad/ui-sweeps/docs42d.js` (the DX9 block) on a
document with a diagram, a formula, two tasks, a footnote cited twice and a
remote picture: before, `w:footnoteReference` 0, `w:drawing` 0, `m:oMath` 0,
"Back" and "Remote image not loaded" written, the diagram's source written,
no task boxes; after, 2, 1, 2, none of the texts, a PNG, and both boxes.
These are the static pins on the code that does it.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORD = (ROOT / "frontend/js/documents-word.js").read_text(encoding="utf-8")


def test_the_word_export_strips_the_shared_chrome_list():
    assert "querySelectorAll(`${DOC_EXPORT_STRIP}, button`)" in WORD
    docs = (ROOT / "frontend/js/documents.js").read_text(encoding="utf-8")
    strip = docs.split("const DOC_EXPORT_STRIP = ")[1].split(";")[0]
    for chrome in (".code-bar", ".entry-image-note", "a.md-fn-back"):
        assert chrome in strip


def test_a_task_box_is_written_as_its_glyph():
    assert 'tag === "input" && child.type === "checkbox"' in WORD
    assert "\\u2611 " in WORD and "\\u2610 " in WORD


def test_a_footnote_is_a_word_footnote_and_its_section_is_not_written_twice():
    assert "new D.FootnoteReferenceRun(id)" in WORD
    assert "footnotes: ctx.footnotes," in WORD
    assert 'el.classList.contains("md-footnotes")) continue' in WORD


def test_a_diagram_is_a_png_picture_and_falls_back_to_its_lines():
    assert "docWordBlob.diagram = async (source)" in WORD
    assert 'canvas.toBlob(resolve, "image/png")' in WORD
    assert 'tag === "pre" && ctx.diagrams?.has(el)' in WORD
    # The SVG's root tag is edited as text: a DOMParser would apply its style
    # attributes under the page's policy (27 CSP errors per export, measured).
    assert "DOMParser" not in WORD.split("docWordBlob.diagram")[1].split("docWordBlob.math")[0]


def test_a_formula_is_word_maths_with_its_symbols_as_the_fallback():
    block = WORD.split("docWordBlob.math = ")[1].split("async function docWordExport")[0]
    for part in ("MathFraction", "MathRadical", "MathSuperScript", "MathSubScript", "MathSubSuperScript", "MathSum", "MathIntegral", "new D.Math("):
        assert part in block
    assert 'el.classList.contains("md-math-block")' in WORD


def test_the_new_helpers_are_properties_not_new_globals():
    assert "\nfunction docWordMath" not in WORD and "\nfunction docWordDiagram" not in WORD
