"""The Calculator and equations panel, redesigned (INBOX 1584, the owner, 2026-11-03: "poor design and needs to
be fixed and redesigned"): one head row, History as a disclosure row, the palette's strip on a band of its
own, and a box that comes back when what was typed into it is deleted.

The browser numbers (head rows, content showing through the band, boxes after deleting) are in the CHANGELOG
line; these tests hold what a file can say, and run the box rules in node over every structure the palette inserts.
"""

from __future__ import annotations

from pathlib import Path

from tests.test_calc_panel_1102 import EDITOR, EDITOR_CSS, FIELD, KIT, KIT_CSS, _failed, _node, _region, _rule

ROOT = Path(__file__).resolve().parents[1]

FIELD_CORE = _region(FIELD, "// MATH-FIELD-CORE-BEGIN", "// MATH-FIELD-CORE-END")
EDITOR_CORE = _region(EDITOR, "// MATH-EDITOR-CORE-BEGIN", "// MATH-EDITOR-CORE-END")


# --- (d) a box comes back -----------------------------------------------------------------


def test_every_box_the_palette_inserts_comes_back_when_what_was_typed_is_deleted(tmp_path: Path) -> None:
    """For each template with a box: fill each box in turn with a letter, delete the letter, and the box is there.

    MathLive's own TeX is simulated at its two quirks: a box a character replaced is the character, and a
    deleted character leaves nothing (an empty `{}` where there were braces), which is what the editor sees."""
    driver = r"""
const BOX = "\\placeholder{}";
const settle = (state, next, collapsed) => {
  const got = mathFieldSlots(state.tex, next, state.slots, { collapsed });
  const boxed = mathFieldBoxes(got.tex, true);
  return { tex: boxed, slots: mathFieldSlots(boxed, boxed, mathFieldSlots(got.tex, boxed, got.slots, { restore: false }).slots, { restore: false }).slots };
};
const nth = (tex, n) => { let at = -1; for (let k = 0; k <= n; k += 1) at = tex.indexOf(BOX, at + 1); return at; };
let structures = 0;
const bad = [];
for (const [, , items] of MATH_EDITOR_TEMPLATES) {
  for (const [name, template] of items) {
    if (!/#[@?]/.test(template)) continue;
    structures += 1;
    const start = template.replace(/#[@?]/g, BOX);
    const total = start.split(BOX).length - 1;
    for (let i = 0; i < total; i += 1) {
      let state = { tex: start, slots: [] };
      const at = nth(state.tex, i);
      // a letter replaces the box ...
      state = settle(state, state.tex.slice(0, at) + "x" + state.tex.slice(at + BOX.length), true);
      // ... and deleting it leaves nothing in its place, as MathLive writes it
      state = settle(state, state.tex.slice(0, at) + state.tex.slice(at + 1), true);
      if (state.tex !== start) {
        bad.push(name + ", box " + (i + 1) + " of " + total + ": " + state.tex);
        break;
      }
    }
  }
}
check("every structure was walked", structures > 90, structures);
check("each box came back, the TeX as inserted", bad.length === 0, bad.join(" | "));
"""
    results = _node(FIELD_CORE + "\n" + EDITOR_CORE, driver, tmp_path)
    assert not _failed(results), _failed(results)


def test_boxes_come_back_in_the_shapes_the_owner_met(tmp_path: Path) -> None:
    """The TeX pairs MathLive gives, from the running editor (INBOX 1584 d)."""
    driver = r"""
const BOX = "\\placeholder{}";
// fill the box at `at` with `typed`, then delete it; the box must stand again
const walk = (before, at, typed, after, collapsed = true) => {
  const filled = before.slice(0, at) + typed + before.slice(at + BOX.length);
  const one = mathFieldSlots(before, filled, [], { collapsed });
  const two = mathFieldSlots(filled, after, one.slots, { collapsed });
  return two;
};
let m = "\\begin{pmatrix}" + BOX + " & " + BOX + "\\\\ " + BOX + " & " + BOX + "\\end{pmatrix}";
let r = walk(m, m.indexOf(BOX), "x", m.replace(BOX, ""));
check("a matrix cell", r.tex === m, r.tex);
let body = "\\int_{" + BOX + "}^{" + BOX + "}" + BOX;
r = walk(body, body.lastIndexOf(BOX), "f", body.slice(0, body.lastIndexOf(BOX)));
check("an integral's body, at the end", r.tex === body, r.tex);
let lim = "\\lim_{" + BOX + "\\to\\infty}" + BOX;
r = walk(lim, lim.indexOf(BOX), "x", lim.replace(BOX, ""));
check("a limit beside other text", r.tex === lim, r.tex);
let paren = "\\left(" + BOX + "\\right)";
r = walk(paren, paren.indexOf(BOX), "x", "\\left(\\right)");
check("a bracket pair", r.tex === paren, r.tex);
let der = "\\frac{d" + BOX + "}{d" + BOX + "}";
r = walk(der, der.indexOf(BOX), "y", "\\frac{d}{d" + BOX + "}");
check("a derivative keeps its d and gets its box", r.tex === der, r.tex);
let root = "\\sqrt[" + BOX + "]{" + BOX + "}";
r = walk(root, root.indexOf(BOX), "n", "\\sqrt{" + BOX + "}");
check("a root's index, which MathLive leaves out of the TeX when empty", r.tex === root, r.tex);
let log = "\\log_{" + BOX + "}\\left(" + BOX + "\\right)";
r = walk(log, log.indexOf(BOX), "b", "\\left(" + BOX + "\\right)");
check("a logarithm's base, which takes the logarithm with it", r.tex === log, r.tex);
let text = "\\text{" + BOX + "}";
const typed = mathFieldSlots(text, "ab", [], {});
const gone = mathFieldSlots("ab", "", typed.slots, { collapsed: true });
check("text, whose letters are left bare when typed", gone.tex === text, gone.tex);
check("the box is selected where it stands", gone.at === text.indexOf(BOX), gone.at);
"""
    results = _node(FIELD_CORE, driver, tmp_path)
    assert not _failed(results), _failed(results)


def test_a_box_is_only_put_back_where_the_person_emptied_it(tmp_path: Path) -> None:
    driver = r"""
const BOX = "\\placeholder{}";
const frac = "\\frac{" + BOX + "}{" + BOX + "}";
const typed = mathFieldSlots(frac, "\\frac{12}{" + BOX + "}", [], {});
check("two characters are one slot", JSON.stringify(typed.slots) === JSON.stringify([[6, 8, "", ""]]), JSON.stringify(typed.slots));
const one = mathFieldSlots("\\frac{12}{" + BOX + "}", "\\frac{1}{" + BOX + "}", typed.slots, {});
check("one of two characters deleted is no box", one.tex === "\\frac{1}{" + BOX + "}" && one.at === -1, one.tex);
const both = mathFieldSlots("\\frac{12}{" + BOX + "}", frac.replace(BOX, ""), typed.slots, {});
check("both deleted at once is a box", both.tex === frac && both.at === 6, both.tex + " " + both.at);
const whole = mathFieldSlots("\\frac{12}{" + BOX + "}", "", typed.slots, { collapsed: false });
check("a structure deleted whole stays deleted", whole.tex === "" && whole.slots.length === 0, whole.tex);
const typedAfter = mathFieldSlots(frac, "\\frac{" + BOX + "}{3}", [], {});
const moved = mathFieldSlots("\\frac{" + BOX + "}{3}", "a\\frac{" + BOX + "}{3}", typedAfter.slots, {});
check("a slot moves with an edit before it", JSON.stringify(moved.slots) === JSON.stringify([[23, 24, "", ""]]), JSON.stringify(moved.slots));
const grown = mathFieldSlots("\\frac{1}{" + BOX + "}", "\\frac{12}{" + BOX + "}", mathFieldSlots(frac, "\\frac{1}{" + BOX + "}", [], {}).slots, {});
check("typing at the end of a slot grows it", JSON.stringify(grown.slots) === JSON.stringify([[6, 8, "", ""]]), JSON.stringify(grown.slots));
const rest = mathFieldSlots("\\frac{12}{" + BOX + "}", "\\frac{12}{3}", typed.slots, {});
check("the other box filled leaves the first slot alone", JSON.stringify(rest.slots.slice(0, 1)) === JSON.stringify([[6, 8, "", ""]]), JSON.stringify(rest.slots));
check("a structure typed in is not a slot", mathFieldSlots(BOX, "\\frac{" + BOX + "}{" + BOX + "}", [], {}).slots.length === 0, "");
check("nothing changed is the same answer", mathFieldSlots("a", "a", [[0, 1, "", ""]], {}).at === -1, "");
"""
    results = _node(FIELD_CORE, driver, tmp_path)
    assert not _failed(results), _failed(results)


def test_a_base_whose_script_was_deleted_is_plain_text(tmp_path: Path) -> None:
    """INBOX 1623, the owner: deleting the superscript left the base "as a regular number, which
    is fine but if i delete that number it appears with the empty box". The base's slot goes
    with its script; while the script stands, the base still comes back as a box (1584 d)."""
    driver = r"""
const BOX = "\\placeholder{}";
for (const [name, mark] of [["superscript", "^"], ["subscript", "_"]]) {
  const tpl = BOX + mark + "{" + BOX + "}";
  const base = mathFieldSlots(tpl, "2" + mark + "{" + BOX + "}", [], {});
  check(name + ": the typed base is a slot", base.slots.length === 1, JSON.stringify(base.slots));
  const bare = mathFieldSlots("2" + mark + "{" + BOX + "}", "2", base.slots, {});
  check(name + ": its script deleted lets the slot go", bare.slots.length === 0, JSON.stringify(bare.slots));
  const gone = mathFieldSlots("2", "", bare.slots, {});
  check(name + ": then the number deletes to nothing", gone.tex === "" && gone.at === -1, gone.tex);
  const held = mathFieldSlots("2" + mark + "{3}", BOX.slice(0, 0) + mark + "{3}", base.slots, {});
  check(name + ": with the script standing, the base is a box again", held.tex === BOX + mark + "{3}", held.tex);
}
"""
    results = _node(FIELD_CORE, driver, tmp_path)
    assert not _failed(results), _failed(results)


def test_the_pane_runs_the_slot_rules_on_every_edit_and_starts_over_on_a_write() -> None:
    pane = FIELD.split("function mathFieldPane", 1)[1].split("\n}\n", 1)[0]
    assert "mathFieldSlots(settled, latex, slots" in pane
    assert "mathFieldBoxes(got.tex, true)" in pane and pane.index("mathFieldBoxes(got.tex, true)") < pane.index("onChange()")
    assert pane.count("write(") >= 3 and "slots = [];" in pane, "a write from outside must forget the old slots"
    assert "beforeinput" in pane and "selectBox(" in pane


def test_a_structure_has_a_walk_in_the_real_editor() -> None:
    spec = (ROOT / "tests-e2e" / "specs" / "calc-boxes-1584.spec.js").read_text(encoding="utf-8")
    assert "mathEditorGroups()" in spec and "moveToNextPlaceholder" not in spec
    assert 'press("Backspace")' in spec and "\\u25a2" in spec


# --- (a) the head ---------------------------------------------------------------------------


def test_the_head_is_one_row_with_the_angle_unit_only_in_scientific() -> None:
    assert "calc-sumline" not in KIT and "calc-mode-bar" not in KIT, "the two rows are back"
    assert 'head.className = "calc-head"' in KIT
    assert "head.append(kind.seg, angle.seg, memory)" in KIT
    assert 'angle.seg.classList.toggle("hidden", !on)' in KIT
    body = _rule(KIT_CSS, ".calc-head")
    assert "display: flex" in body and "flex-wrap" not in body, "one row, never wrapping"


def test_the_angle_unit_shows_a_short_form_and_keeps_its_name() -> None:
    # The first draft swapped the words under 26rem; the breakpoint set only shrinks (test_breakpoints), so the short form is
    # the one form on every width: Deg and Rad, the full words as the button's name and title.
    assert '["deg", "Degrees", "Deg"]' in KIT and '["rad", "Radians", "Rad"]' in KIT
    assert 'b.setAttribute("aria-label", words)' in KIT and "b.title = words" in KIT, "the short form must not rename the button"
    assert "calc-seg-short" not in KIT_CSS and "26rem" not in KIT_CSS


def test_a_ring_is_for_the_keyboard() -> None:
    """INBOX 1622: the strip's own `:focus-visible` is the only ring, so the `is-pointer` workaround of the old `.seg` is gone."""
    seg = KIT.split("seg(label, choices, value, onChange)", 1)[1].split("\n  },\n", 1)[0]
    assert '"pointerdown"' not in seg and "is-pointer" not in seg and "is-pointer" not in KIT_CSS
    assert '"keydown"' in seg


# --- (b) History ----------------------------------------------------------------------------


def test_history_is_the_disclosure_row_with_a_muted_badge_and_a_quiet_clear() -> None:
    history = KIT.split("function replyCalcHistory", 1)[1].split("\nfunction ", 1)[0]
    assert '"ghost small disclosure-row calc-log-toggle"' in history
    assert 'caret.className = "ph ph-caret-down contents-caret"' in history
    assert "toggle.append(caret," in history and "bar.append(toggle, clear)" in history
    assert 'clear.classList.add("quiet")' in history
    badge = _rule(KIT_CSS, ".calc-log-toggle .calc-log-count")
    assert "var(--muted)" in badge and "var(--chip-bg)" in badge and "var(--radius-pill)" in badge
    toggle = _rule(KIT_CSS, "button.ghost.disclosure-row.calc-log-toggle")
    assert "background" not in toggle, "a filled ground belongs to the hover only (the recipe's veil)"


# --- (c) the strip ---------------------------------------------------------------------------


def test_the_strip_sits_on_a_band_of_its_own() -> None:
    mount = EDITOR.split("function mathEditorMount", 1)[1]
    assert 'band.className = "math-editor-band"' in mount and "band.append(jump)" in mount
    assert "search, band, list)" in mount, "the band, not the bare strip, is in the pane"
    band = _rule(EDITOR_CSS, ".math-editor-band")
    assert "position: sticky" in band and "background: var(--modal-bg-opaque)" in band
    strip = _rule(EDITOR_CSS, ".math-editor-jump")
    assert "position: sticky" not in strip and "background" not in strip, "the fade is into the band's colour: the strip holds none of its own"
    assert "overflow-x: auto" in strip and "scrollbar-width: thin" in strip
