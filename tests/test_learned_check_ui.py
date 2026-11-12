"""Decision 68's panel half: the bar's button, the box, the undo and the flag marks.

Source-level, like the other Settings panel tests: the behaviour itself was
driven in the app (CHANGELOG, audit68-1101)."""

from __future__ import annotations

import re
from pathlib import Path
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
CONTROLS = unwrapped((ROOT / "frontend" / "js" / "settings-controls.js").read_text(encoding="utf-8"))
BOOT = (ROOT / "frontend" / "js" / "settings.js").read_text(encoding="utf-8")


def _section(html: str, ident: str) -> str:
    start = html.index(f'id="{ident}"')
    return html[start : start + 1500]


def test_the_button_is_on_the_learned_bar_and_the_box_has_its_undo():
    dock = HTML[HTML.index('data-dock-name="settings-learned"') :][:1200]
    assert 'id="learned-check"' in dock and "Check what it learned" in dock
    assert 'id="learned-check-undo"' in _section(HTML, "learned-check-result")
    assert 'data-job-line="learned-audit"' in HTML  # the run's lines, INBOX 805's ledger


def test_all_of_it_is_in_the_lazy_settings_file_not_the_boot_files():
    for name in ("learnedCheckRun", "learnedCheckPutBack", "learnedCheckMark", "learnedCheckShow"):
        assert f"function {name}(" in CONTROLS or f"async function {name}(" in CONTROLS
        assert name not in BOOT
    assert "/learned/audit/run" not in BOOT


def test_a_check_leaves_an_undo_step_with_a_redo_and_the_boxs_undo_leaves_one_too():
    run = CONTROLS[CONTROLS.index("async function learnedCheckRun()") : CONTROLS.index("async function learnedCheckPutBack()")]
    assert "pushRoutePairUndo(" in run and '"/learned/audit/undo"' in run and '"/learned/audit/redo"' in run
    back = CONTROLS[CONTROLS.index("async function learnedCheckPutBack()") :]
    assert back.index("/learned/audit/undo") < back.index("pushUndo(") < back.index("/learned/audit/redo")


def test_the_flag_mark_is_added_once_per_row_and_follows_every_redraw():
    mark = CONTROLS[CONTROLS.index("function learnedCheckMark()") : CONTROLS.index("async function learnedCheckRefresh(")]
    assert 'querySelector(".learned-flag")' in mark and "factId" in mark
    assert "renderLearnedList = async function" in CONTROLS and "await learnedListDrawn()" in CONTROLS
    assert "MutationObserver" not in CONTROLS[CONTROLS.index("// ---- Check what it learned") :].replace("A wrapper and not a MutationObserver", "")


def test_the_copy_is_house_style():
    block = CONTROLS[CONTROLS.index("// ---- Check what it learned") :]
    strings = re.findall(r'`([^`]*)`|"([^"\n]{12,})"', block)
    for first, second in strings:
        text = first or second
        assert chr(0x2014) not in text and "!" not in text and "Oops" not in text, text
