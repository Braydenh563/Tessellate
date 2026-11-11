"""The Calculator and equations panel, five owner rows (INBOX 1537 to 1541, 2026-11-02).

Measured in the browser (a Playwright sweep of the panel at 1440x900 and 1280x720;
the numbers are in the CHANGELOG lines); these tests hold what a file can say: the sizes the CSS asks for, the one place a slot's
empty state is decided, the glide's class, the palette's quick access, and the
history's rules (pure, run in node). Everything here is written before the
code it covers.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests import _js_scope

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = ROOT / "frontend" / "css"
KIT = _js_scope.unwrapped((JS / "reply-kit.js").read_text(encoding="utf-8"))
EDITOR = (JS / "math-editor.js").read_text(encoding="utf-8")
FIELD = (JS / "math-field.js").read_text(encoding="utf-8")
KIT_CSS = (CSS / "reply-kit-lazy.css").read_text(encoding="utf-8")
EDITOR_CSS = (CSS / "math-editor-lazy.css").read_text(encoding="utf-8")


def _region(text: str, begin: str, end: str) -> str:
    start, stop = text.find(begin), text.find(end)
    assert start != -1 and stop > start, f"{begin} / {end} markers are missing"
    return text[start + len(begin) : stop]


def _rule(css: str, selector: str) -> str:
    match = re.search(r"(?:^|[}/])\s*" + re.escape(selector) + r"\s*\{([^{}]*)\}", css)
    assert match, f"{selector} has no rule"
    return match.group(1)


def _node(source: str, driver: str, tmp_path: Path) -> list[dict]:
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = tmp_path / "run.js"
    script.write_text(
        source + "\nconst results = [];\nconst check = (name, ok, detail) => results.push({ name, ok: !!ok, detail: detail == null ? null : String(detail) });\n" + driver + "\nprocess.stdout.write(JSON.stringify(results));\n",
        encoding="utf-8",
    )
    run = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60, check=False)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def _failed(results: list[dict]) -> str:
    return "\n".join(f"{c['name']}: {c['detail']}" for c in results if not c["ok"])


# --- 1537: tall enough that Sum and Units need no scroll -------------------------------


def test_the_panel_opens_tall_enough_for_the_keypad() -> None:
    """Sum's pane needs 325px and the card's head, tab strip and action row 219px
    (measured at 1280x720, where the card was 475px and the pane scrolled), so
    the card must be 544px or more at 720 and still 544px at 900 and above."""
    body = _rule(KIT_CSS, ".sheet-card.calc-card")
    match = re.search(r"max-height:\s*min\((\d+)dvh,\s*(\d+(?:\.\d+)?)rem\)", body)
    assert match, body
    share, cap = int(match.group(1)), float(match.group(2))
    assert "height: auto" in body, "INBOX 1622: the card fits its content"
    assert share / 100 * 720 >= 560, f"{share}dvh is {share * 7.2:.0f}px at 720, the Sum pane scrolls"
    assert cap * 16 >= 688, "the cap leaves Standard (688px) scrolling in a tall window"
    assert share <= 96, "the foot must not run under the screen's edge"


# --- 1538: an emptied box shows its box again ------------------------------------------


def test_an_emptied_slot_is_a_box_again(tmp_path: Path) -> None:
    """MathLive writes `\\frac{}{...}` for a slot typed in and deleted; the field's
    own empty-box rule (`mathFieldBoxes`) only ran when TeX was set, not after an edit; one function does both."""
    core = _region(FIELD, "// MATH-FIELD-CORE-BEGIN", "// MATH-FIELD-CORE-END")
    driver = r"""
const refill = (t) => mathFieldBoxes(t);
check("typed then deleted", refill("\\frac{}{\\placeholder{}}") === "\\frac{\\placeholder{}}{\\placeholder{}}", refill("\\frac{}{\\placeholder{}}"));
check("every slot kind", refill("x^{}") === "x^{\\placeholder{}}" && refill("x_{}") === "x_{\\placeholder{}}" && refill("\\sqrt{}") === "\\sqrt{\\placeholder{}}", [refill("x^{}"), refill("x_{}"), refill("\\sqrt{}")].join(" "));
check("a box already drawn is left alone", refill("\\frac{\\placeholder{}}{2}") === "\\frac{\\placeholder{}}{2}", refill("\\frac{\\placeholder{}}{2}"));
check("a filled slot is left alone", refill("\\frac{1}{2}") === "\\frac{1}{2}", refill("\\frac{1}{2}"));
check("a braced brace is not a slot", refill("\\left\\{x\\right\\}") === "\\left\\{x\\right\\}", refill("\\left\\{x\\right\\}"));
check("spaces inside are still empty", refill("\\frac{ }{2}") === "\\frac{\\placeholder{}}{2}", refill("\\frac{ }{2}"));
check("a script whose base was deleted", mathFieldBoxes("^{\\placeholder{}}", true) === "\\placeholder{}^{\\placeholder{}}" && mathFieldBoxes("\\frac{_{2}}{3}", true) === "\\frac{\\placeholder{}_{2}}{3}", mathFieldBoxes("^{\\placeholder{}}", true));
check("a base is only asked for after an edit", mathFieldBoxes("^{2}") === "^{2}", "");
check("nothing to do is the same string", refill("a+b") === "a+b", "");
"""
    assert not _failed(_node(core, driver, tmp_path)), _failed(_node(core, driver, tmp_path))


def test_the_field_refills_after_every_edit() -> None:
    pane = FIELD.split("function mathFieldPane", 1)[1].split("\n}\n", 1)[0]
    # 1584: the TeX is first run through the slot rules (got.tex), so the call names that, not the raw latex.
    assert "mathFieldBoxes(got.tex, true)" in pane, "the pane's input handler never restores an emptied box"
    assert pane.index("mathFieldBoxes(got.tex, true)") < pane.index("onChange()"), "the change is announced before the box is back"


# --- 1540: the Inline and Display pill glides ------------------------------------------


def test_the_inline_display_pill_has_the_chosen_class_the_glide_reads() -> None:
    """`glideStrip` places the indicator on `:scope > .active` or `aria-selected`;
    `aria-pressed` alone left it without one (shell-reminders.js GLIDE_CHOSEN)."""
    modes = EDITOR.split("function mathEditorModes", 1)[1].split("\n}\n", 1)[0]
    assert 'classList.toggle("active"' in modes, "the chosen tab never gets .active"
    assert 'className = "tabs-line popup-kinds math-editor-mode"' in modes


def test_every_segmented_control_the_panel_builds_marks_its_chosen_option() -> None:
    """Any `.seg` the panel's files build in script must toggle `.active` with `aria-pressed`."""
    for name, text in (("reply-kit.js", KIT), ("math-editor.js", EDITOR), ("math-field.js", FIELD)):
        for built in re.finditer(r'className = "[^"]*\bseg\b[^"]*"', text):
            tail = text[built.start() : built.start() + 2500]
            assert 'classList.toggle("active"' in tail, f"{name}: a .seg is built without the glide's chosen class"


# --- 1539: quicker than scrolling ------------------------------------------------------


def test_the_palette_has_a_jump_row_recent_and_favourites() -> None:
    mount = EDITOR.split("function mathEditorMount", 1)[1]
    assert "math-editor-jump" in mount, "no row of groups to jump to"
    assert "scrollIntoView" in mount and "aria-current" in mount, "a jump must scroll and mark the group in view"
    palette = EDITOR.split("function mathEditorPalette", 1)[1].split("\n}\n", 1)[0]
    assert '"Favourites"' in palette and '"Recent"' in palette
    assert "math-editor-recent" in EDITOR and "math-editor-fav" in EDITOR
    assert "prefs.json(" in EDITOR and "prefs.setJSON(" in EDITOR, "recent and favourites go through the prefs store"


def test_the_jump_row_stays_in_reach_while_the_palette_scrolls() -> None:
    # 1584: the strip scrolls sideways on its own; the sticky part moved to the band around it, which also owns the
    # opaque ground and the divider, so the fade and the scrollbar can no longer cross the tiles under it.
    band = _rule(EDITOR_CSS, ".math-editor-band")
    assert "position: sticky" in band and "var(--modal-bg-opaque)" in band
    assert "overflow-x: auto" in _rule(EDITOR_CSS, ".math-editor-jump")


# --- 1541: history for sums, conversions and equations ---------------------------------


def test_the_history_rules(tmp_path: Path) -> None:
    core = _region(KIT, "// CALC-TEX-BEGIN", "// CALC-TEX-END")
    driver = r"""
const log = calcTex.log;
let list = [];
list = log.add(list, { key: "1+1", input: "1+1", answer: "2" });
list = log.add(list, { key: "2+2", input: "2+2", answer: "4" });
check("newest first", list.map((r) => r.key).join() === "2+2,1+1", list.map((r) => r.key).join());
list = log.add(list, { key: "1+1", input: "1+1", answer: "2" });
check("a repeat moves up, once", list.map((r) => r.key).join() === "1+1,2+2", list.map((r) => r.key).join());
list = log.add(list, { key: "3+3", input: "3+3", answer: "6" }, "2+2");
check("an edit replaces the row where it was", list.map((r) => r.key).join() === "1+1,3+3", list.map((r) => r.key).join());
check("an edit of a row that is gone adds", log.add([], { key: "a" }, "zzz").length === 1, "");
let many = [];
for (let i = 0; i < 40; i++) many = log.add(many, { key: String(i) });
check("capped", many.length === log.max && many[0].key === "39", many.length);
check("remove", log.remove(list, "1+1").map((r) => r.key).join() === "3+3", "");
check("clean drops what is not a row", log.clean([{ key: "a" }, null, 5, { nokey: 1 }, { key: 3 }, { key: "b", input: "x" }]).map((r) => r.key).join() === "a,b", "");
check("clean takes only an array", log.clean({}).length === 0 && log.clean(null).length === 0, "");
"""
    assert not _failed(_node(core, driver, tmp_path)), _failed(_node(core, driver, tmp_path))


def test_each_tab_keeps_a_history_in_the_prefs_store() -> None:
    assert 'prefs.json("calc-history"' in KIT and 'prefs.setJSON("calc-history"' in KIT
    for tab in ("work", "convert", "equation"):
        assert f'replyCalcHistory("{tab}"' in KIT, f"the {tab} tab has no history"
    assert "history: []" not in KIT, "the in-memory list is replaced, not layered"


def test_every_answer_has_a_copy_button_and_a_row_has_its_three_actions() -> None:
    result = KIT.split("function replyCalcResult", 1)[1].split("\n}\n", 1)[0]
    assert "calc-copy" in result and "navigator.clipboard" in result
    history = KIT.split("function replyCalcHistory", 1)[1].split("\nfunction ", 1)[0]
    for needle in ("calc-again", "Copy this answer", "Edit this one", "Remove from the history", "Clear the history", "Undo"):
        assert needle in history, f"the history is missing {needle}"
    #: A click puts the row back in the fields; Edit does too and the next keep replaces it.
    assert "restore(" in history and "replacing" in history


def test_units_keeps_nothing_for_the_conversion_it_opens_with() -> None:
    pane = KIT.split("function replyCalcConvertPane", 1)[1]
    assert "let touched = false;" in pane and "if (last && touched)" in pane


def test_the_equation_tab_can_load_a_row_back_into_the_field() -> None:
    mount = EDITOR.split("function mathEditorMount", 1)[1]
    assert "load:" in mount and "entry:" in mount


def test_the_history_is_drawn_from_the_recipe_tokens() -> None:
    for selector in (".calc-log", ".calc-log-bar", ".calc-history"):
        assert re.search(re.escape(selector) + r"\s*\{", KIT_CSS), f"{selector} has no rule"
    flat = KIT_CSS.split(".calc-log", 1)[1]
    assert not re.search(r"#[0-9a-fA-F]{3,6}\b|\d+px\b", flat.split(".calc-convert-row")[0]), "a literal colour or pixel size"
