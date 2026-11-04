"""An equation structure whose boxes are all empty can be deleted (INBOX 1664, the owner: "I cant delete these in
the equations").

MathLive removes an empty box and the box-restoring rules put it back, so a fresh big operator, integral or script
never went. Word's rule: the first delete in an empty box (or next to the structure) selects the whole structure,
the second removes it; a structure with something typed in keeps its boxes. The pure part, whether a structure's
boxes are all empty, is run in node over every palette template; the key handling is measured in the browser (the
CHANGELOG line has the numbers).
"""

from __future__ import annotations

from pathlib import Path

from tests.test_calc_panel_1102 import EDITOR, FIELD, _failed, _node, _region

EDITOR_CORE = _region(EDITOR, "// MATH-EDITOR-CORE-BEGIN", "// MATH-EDITOR-CORE-END")
FIELD_CORE = _region(FIELD, "// MATH-FIELD-CORE-BEGIN", "// MATH-FIELD-CORE-END")


def test_every_palette_template_with_empty_boxes_is_hollow_and_one_with_a_letter_is_not(tmp_path: Path) -> None:
    driver = r"""
const BOX = "\\placeholder{}";
const skeletons = MATH_EDITOR_TEMPLATES.flatMap(([, , items]) => items.map((i) => i[1]));
let n = 0;
const empty = [], typed = [], plain = [];
for (const [, , items] of MATH_EDITOR_TEMPLATES) {
  for (const [name, template] of items) {
    if (!/#[@?]/.test(template)) continue;
    n += 1;
    const boxes = template.replace(/#[@?]/g, BOX);
    if (!mathFieldHollow(boxes, skeletons)) empty.push(name);
    // the same structure with MathLive's other spellings (no spaces, a bare trailing box)
    if (!mathFieldHollow(boxes.replace(/ /g, ""), skeletons)) plain.push(name);
    // a letter in the first box is content
    if (mathFieldHollow(template.replace(/#[@?]/, "x").replace(/#[@?]/g, BOX), skeletons)) typed.push(name);
  }
}
check("every template was walked", n > 90, n);
check("each is hollow with its boxes empty", empty.length === 0, empty.join(", "));
check("and without its spaces", plain.length === 0, plain.join(", "));
check("none is hollow once a letter is typed", typed.length === 0, typed.join(", "));
check("a frame without a template", mathFieldHollow("\\frac{\\placeholder{}}{\\placeholder{}}") && mathFieldHollow("\\sqrt[\\placeholder{}]{\\placeholder{}}"));
check("a frame with content", !mathFieldHollow("\\frac{1}{\\placeholder{}}") && !mathFieldHollow("\\frac{\\placeholder{}}{\\placeholder{}}+2"));
check("a box beside a structure needs a template", !mathFieldHollow("\\frac{\\placeholder{}}{\\placeholder{}}\\placeholder{}", skeletons, true));
check("no box is not hollow", !mathFieldHollow("") && !mathFieldHollow("\\frac{1}{2}"));
"""
    results = _node(FIELD_CORE + "\n" + EDITOR_CORE, driver, tmp_path)
    assert not _failed(results), _failed(results)


def test_the_pane_selects_a_hollow_structure_before_the_delete_takes_it() -> None:
    assert "hollowRange(" in FIELD
    pane = FIELD[FIELD.index('field.addEventListener("beforeinput"') :]
    assert pane.index("hollowRange(") < pane.index("mathFieldSlots(settled, pre")
    assert "event.preventDefault()" in pane[: pane.index("mathFieldSlots(settled, pre")]
