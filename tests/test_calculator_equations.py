"""One maths tool: the Calculator and the equation editor are one dialog (INBOX 1527).

The owner, 2026-11-01: "I think the equations and calculator should be
integrated together". The Calculator sheet has three tabs (Sum, Units,
Equation); the Equation tab hosts the editor math-editor.js builds
(`mathEditorMount`), Alt+= opens the sheet on that tab over the box it was
pressed in, /calc opens it on Work out, a result offers Insert and Insert as
equation, and an equation made of numbers shows its value through the same
evaluator as Work out. The pure TeX converters run in node; the wiring is read
from the files.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests import _js_scope
from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
KIT = _js_scope.unwrapped((JS / "reply-kit.js").read_text(encoding="utf-8"))
EDITOR = (JS / "math-editor.js").read_text(encoding="utf-8")
PANES = (JS / "settings-panes.js").read_text(encoding="utf-8")


def _region(text: str, begin: str, end: str) -> str:
    start, stop = text.find(begin), text.find(end)
    assert start != -1 and stop > start, f"{begin} / {end} markers are missing"
    return text[start + len(begin) : stop]


DRIVER = r"""
const out = [];
const same = (name, got, want) => out.push({ name, ok: got === want, detail: `${JSON.stringify(got)} != ${JSON.stringify(want)}` });
const value = (sum) => (sum === null ? null : Function(`"use strict"; return (${sum.replace(/\^/g, "**")});`)());

same("frac and plus", value(calcTex.toSum("\\frac{1}{2}+3")), 3.5);
same("times and groups", value(calcTex.toSum("12\\times(3+4)")), 84);
same("power", value(calcTex.toSum("2^{3}")), 8);
same("left and right", value(calcTex.toSum("\\left(1+2\\right)\\cdot4")), 12);
same("nested frac", value(calcTex.toSum("\\frac{\\frac{1}{2}}{2}+1")), 1.25);
same("div", value(calcTex.toSum("8\\div2")), 4);
same("a letter is not a number", calcTex.toSum("x+1"), null);
same("a root is not read", calcTex.toSum("\\sqrt{4}+1"), null);
same("a bare number has nothing to work out", calcTex.toSum("5"), null);
same("a symbol is not a number", calcTex.toSum("\\alpha+2"), null);
same("empty", calcTex.toSum("  "), null);

//: INBOX 1579: a sum still being typed is not an error.
same("pending: a trailing plus", calcTex.pending("55*9+"), true);
same("pending: a trailing times sign", calcTex.pending("55 ×"), true);
same("pending: an open bracket", calcTex.pending("12*(3+4"), true);
same("pending: a joining word", calcTex.pending("5 km to"), true);
same("pending: a power sign", calcTex.pending("2^"), true);
same("done: a finished sum", calcTex.pending("55*9+1"), false);
same("done: balanced", calcTex.pending("12*(3+4)"), false);
same("done: a percent", calcTex.pending("20%"), false);
same("done: empty", calcTex.pending("   "), false);
same("done: a question", calcTex.pending("15% of 80"), false);

//: INBOX 1579: the sum typeset as typed, whatever is typed, and never a formula the renderer has to guess at.
same("live: times and a group", calcTex.live("12*(3+4)"), "12 \\times (3+4)");
same("live: divide", calcTex.live("12 / 4"), "12 \\div 4");
same("live: a raised power", calcTex.live("2^10"), "2^{10}");
same("live: a power with a bracket", calcTex.live("2^(1+2)"), "2^{1+2}");
same("live: a root", calcTex.live("sqrt(16)"), "\\sqrt{16}");
same("live: pi", calcTex.live("2pi"), "2\\pi");
same("live: a function is upright", calcTex.live("sin(30)"), "\\sin (30)");
same("live: a minus is the minus sign", calcTex.live("10 - 3"), "10\u22123");
same("live: words are text", calcTex.live("5 km to miles"), "5\\;\\text{km to miles}");
same("live: a long word is not a function", calcTex.live("tangent"), "\\text{tangent}");
same("live: nothing", calcTex.live("  "), "");
//: INBOX 1579: the scientific reader. `sci(text)` is the figure as shown, "ERR" for a sum it will not work out, "WORDS" for text that is not a sum.
const sci = (text, angle = "deg") => {
  try {
    return calcTex.sci.format(calcTex.sci.evaluate(text, { angle }).value);
  } catch (error) {
    return error.notMath ? "WORDS" : `ERR ${error.message}`;
  }
};
same("sci: sine in degrees", sci("sin(30)"), "0.5");
same("sci: cosine of 90 is zero, not float dust", sci("cos(90)"), "0");
same("sci: tangent of 45", sci("tan(45)"), "1");
same("sci: tangent of 90 is undefined", sci("tan(90)"), "ERR tan is undefined there.");
same("sci: sine in radians", sci("sin(pi/2)", "rad"), "1");
same("sci: inverse sine answers in degrees", sci("asin(1)"), "90");
same("sci: inverse sine answers in radians", sci("asin(1)", "rad"), "1.57079632679");
same("sci: pi with a number against it", sci("2pi"), "6.28318530718");
same("sci: e to a power", sci("e^2"), "7.38905609893");
same("sci: natural log of e", sci("ln(e)"), "1");
same("sci: log is base ten", sci("log(1000)"), "3");
same("sci: a root and a factorial", sci("sqrt(16)+5!"), "124");
same("sci: a root sign", sci("\u221a16"), "4");
same("sci: zero factorial", sci("0!"), "1");
same("sci: a factorial of a fraction", sci("3.5!"), "ERR A factorial needs a whole number from 0 to 170.");
same("sci: powers are right to left", sci("2^3^2"), "512");
same("sci: a minus binds looser than a power", sci("-2^2"), "-4");
same("sci: a percent", sci("200*10%"), "20");
same("sci: a remainder", sci("10 % 3"), "1");
same("sci: a group beside a group", sci("(1+2)(3+4)"), "21");
same("sci: float dust is trimmed", sci("0.1+0.2"), "0.3");
same("sci: divide by zero", sci("1/0"), "ERR Cannot divide by zero.");
same("sci: a negative root", sci("sqrt(-1)"), "ERR There is no real square root of a negative number.");
same("sci: a log of zero", sci("ln(0)"), "ERR A logarithm needs a number above 0.");
same("sci: an open bracket", sci("(1+2"), "ERR A bracket is not closed.");
same("sci: two numbers side by side", sci("2 3"), "ERR Put a sign between the numbers.");
same("sci: a conversion is the app's, not this reader's", sci("5 km to miles"), "WORDS");
same("sci: a percentage of is the app's", sci("15% of 80"), "WORDS");
same("sci: a thousands comma", sci("1,000+1"), "1,001");
same("sci: a word that starts like a function is not one", sci("tangent"), "WORDS");
same("pending: a function name waiting for its bracket", calcTex.pending("sin"), true);
same("pending: a root sign waiting", calcTex.pending("\u221a"), true);
same("done: a name inside a word is not pending", calcTex.pending("5 singles"), false);
for (const typed of ["55*9+", "2^", "sqrt", "(1+2", "1+2)", "15% of 80", "5!", "e^2", "log10(100)", "asin(0.5)", "\u221a16", "20\u00b0", "1,000+1", "a & b", "$5", "x_{1}"]) {
  let problem = "none";
  try {
    problem = docMathTree(calcTex.live(typed)).problem || "none";
  } catch (error) {
    problem = `threw ${error.message}`;
  }
  same(`live reads ${typed}`, problem, "none");
}

same("times", calcTex.toTex("12 * (3 + 4)", "84"), "12 \\times (3 + 4) = 84");
same("fraction", calcTex.toTex("12/4", "3"), "\\frac{12}{4} = 3");
same("power", calcTex.toTex("2^3", "8"), "2^{3} = 8");
same("words stay words", calcTex.toTex("15% of 80", "12"), "\\text{15\\% of 80} = 12");
same("units stay words", calcTex.toTex("5 km to miles", "3.11 miles"), "\\text{5 km to miles} = \\text{3.11 miles}");
process.stdout.write(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def converters(tmp_path_factory) -> list[dict]:
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    source = _region((JS / "documents-math.js").read_text(encoding="utf-8"), "// DOC-MATH-BEGIN", "// DOC-MATH-END")
    source += _region(KIT, "// CALC-TEX-BEGIN", "// CALC-TEX-END")
    script = tmp_path_factory.mktemp("calctex") / "run.js"
    script.write_text(source + DRIVER, encoding="utf-8")
    run = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60, check=False)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def test_the_tex_converters_read_and_write_sums(converters: list[dict]) -> None:
    failed = [c for c in converters if not c["ok"]]
    assert not failed, "\n".join(f"{c['name']}: {c['detail']}" for c in failed)


def test_the_calculator_has_three_tabs_and_takes_a_target() -> None:
    assert 'function openCalculator(input = "", mode = "work", { target = null } = {})' in KIT
    assert '["work", "Sum"], ["convert", "Units"], ["equation", "Equation"]' in KIT
    assert 'label: "Calculator and equations"' in KIT
    #: The Equation tab hosts the editor, built on first use, and a result
    #: offers Insert and Insert as equation only when there is a box.
    assert "mathEditorMount(" in KIT and 'ensureModule("mathEditor")' in KIT
    assert "Insert as equation" in KIT
    assert "function replyCalcActions(target" in KIT and "calc-where" in KIT
    assert "mathEditorWrite(target," in KIT and "plain: !equation" in KIT
    #: The value of a numeric equation is the Work out evaluator's.
    assert "replyCalcWork(" in KIT.split("function replyCalcEquation", 1)[1]


def test_an_open_dialog_is_reused_or_replaced_for_a_new_target() -> None:
    opener = KIT.split("function openCalculator", 1)[1].split("function replyCalcBuild", 1)[0]
    assert "replyCalc.tabs.findIndex" in opener and "existing && target" in opener
    assert re.search(r"existing\.querySelector\(['\"]\.sheet-close['\"]\)", opener), "a new target needs a new dialog"


def test_the_editor_is_hosted_not_forked() -> None:
    assert "function mathEditorMount({" in EDITOR
    assert "function mathEditorWrite(target, tex, {" in EDITOR and "plain = false" in EDITOR
    #: Every caller of openMathEditor (Alt+=, the "/" rows, the Insert menu)
    #: lands in the one dialog; the floating popover is gone.
    body = EDITOR.split("function openMathEditor", 1)[1]
    assert 'ensureModule("replyKit")' in body and 'openCalculator("", "equation"' in body
    assert "mathEditorPlace" not in EDITOR and "math-editor-centred" not in EDITOR
    assert '"help-popover math-editor"' not in EDITOR
    css = (ROOT / "frontend" / "css" / "math-editor-lazy.css").read_text(encoding="utf-8")
    assert ".math-editor.help-popover" not in css and "math-editor-centred" not in css


def test_one_registry_row_carries_both_shortcuts() -> None:
    tools = PANES.split("const POPUP_TOOLS = [", 1)[1].split("\n];", 1)[0]
    assert 'id: "equation"' not in tools, "the separate Equation row is replaced, not layered"
    row = next(block for block in tools.split("\n  },") if 'id: "calculator"' in block)
    assert 'name: "Calculator and equations"' in row
    assert 'keys: "Alt+= or /calc"' in row
    assert 'guide: "calculator"' in row and "popupToolMaths({ target: t || null })" in row
    #: Nothing else in the registry claims Alt+=.
    assert tools.count('keys: "Alt+=') == 1


def test_the_shortcut_list_draws_each_chord_of_a_row() -> None:
    features = (JS / "app-features.js").read_text(encoding="utf-8")
    assert 'tool.keys.split(" or ")' in features
    assert "function popupToolEquation" not in features and "function popupToolMaths" in features


def test_the_guide_says_it_is_one_tool() -> None:
    from tessellate.ai import help_topics_more as more

    topics = {t["id"]: t["body"] for t in more.MORE_TOPICS}
    calc = topics["calculator"]
    assert "Equation tab" in calc and "Alt+=" in calc and "Insert as equation" in calc
    assert more.TOPIC_META["calculator"]["title"] == "Calculator and equations"
    equation = topics["equation-editor"]
    assert "Calculator" in equation and "Equation tab" in equation
    assert "Ctrl+K, Equation opens" not in equation


def test_a_slash_row_hands_the_calculator_the_box_it_was_typed_in():
    """The UX audit of d231b19: "/calc" in a note, after the palette was last opened over the
    Ask box, inserted the result into the hidden Ask box (`paletteCaught` was stale)."""
    from pathlib import Path

    js = Path(__file__).resolve().parents[1] / "frontend" / "js"
    editor = (js / "editor.js").read_text(encoding="utf-8")
    assert 'run: (t) => tool.open(t) });' in editor
    panes = (js / "settings-panes.js").read_text(encoding="utf-8")
    assert "open: (t) => ensureModule(\"appPalette\").then(() => popupToolMaths({ target: t || null }))," in panes


def test_no_live_field_shows_an_error_while_it_is_being_typed() -> None:
    """INBOX 1579: "55*9+" showed "That is not a sum". An unfinished sum clears the preview, any other error waits about 800 ms, and a pattern field holds its error the same way."""
    work = KIT.split("function replyCalcWorkPane", 1)[1].split("function replyCalcEquation", 1)[0]
    assert "calcTex.pending(box.value)" in work and "out._late" in work and "That sum is not finished" in work
    replace = (JS / "documents-replace.js").read_text(encoding="utf-8")
    assert "docReplace.late = setTimeout" in replace
    board = frontend_text("whiteboard.js")
    assert "wbBoardSearch.late = setTimeout" in board


def test_the_scientific_mode_is_a_seg_with_its_own_keys_and_no_eval() -> None:
    """INBOX 1579: Standard or Scientific is a `.seg` on the recipe, keyboard reachable, and the reader never hands text to `eval`."""
    region = _region(KIT, "// CALC-TEX-BEGIN", "// CALC-TEX-END")
    assert "eval(" not in region and "new Function" not in region and "Function(" not in region
    work = KIT.split("function replyCalcWorkPane", 1)[1].split("function replyCalcEquation", 1)[0]
    assert 'replyCalc.seg("Calculator kind"' in work and 'replyCalc.seg("Angle unit"' in work
    assert "replyCalcKeypad(box, equals, { keys: replyCalc.sciKeys" in work
    seg = KIT.split("  seg(label, choices, value, onChange) {", 1)[1].split("\n  },", 1)[0]
    assert '"tabs-line popup-kinds calc-seg"' in seg and "aria-selected" in seg and 'classList.toggle("active"' in seg
    #: One Tab stop per keypad and the arrows walk it: the same function builds both.
    assert KIT.count("function replyCalcKeypad(") == 1
    from tessellate.ai import help_topics_more

    topic = next(t for t in help_topics_more.MORE_TOPICS if t["id"] == "calculator")
    assert "Scientific" in topic["body"] and "Radians" in topic["body"] and "memory" in topic["body"]
    assert "Scientific adds" in KIT
