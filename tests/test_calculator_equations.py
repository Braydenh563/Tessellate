"""One maths tool: the Calculator and the equation editor are one dialog (INBOX 1527).

The owner, 2026-11-01: "I think the equations and calculator should be
integrated together". The Calculator sheet has three tabs (Work out, Convert
units, Equation); the Equation tab hosts the editor math-editor.js builds
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

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
KIT = (JS / "reply-kit.js").read_text(encoding="utf-8")
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
    source = _region(KIT, "// CALC-TEX-BEGIN", "// CALC-TEX-END")
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
    assert '["work", "Work out"], ["convert", "Convert units"], ["equation", "Equation"]' in KIT
    assert 'label: "Calculator and equations"' in KIT
    #: The Equation tab hosts the editor, built on first use, and a result
    #: offers Insert and Insert as equation only when there is a box.
    assert "mathEditorMount(" in KIT and 'ensureModule("mathEditor")' in KIT
    assert "Insert as equation" in KIT
    assert "if (target) {" in KIT.split("function replyCalcWorkPane", 1)[1].split("function replyCalcKeypad", 1)[0]
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
