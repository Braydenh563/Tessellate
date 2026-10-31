"""Words and small flows from the 2026-10-31 audit (AI12, AI19, HR9, HR10, HR11, HR17, HR19)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _text(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def test_ai12_the_guide_gives_one_instruction_per_switch_state(app_state):
    from tessellate.ai import help_chat
    from tessellate.core import deps

    for on, said, verb in ((True, "Web search is on now.", "Turn it off in"), (False, "Web search is off now.", "Turn it on in")):
        deps.get_config().set_preference("web_search_enabled", on)
        answer = help_chat.offline_answer("how do I turn on web search")["content"]
        assert said in answer
        assert verb in answer
        opposite = "Turn it on in" if on else "Turn it off in"
        assert opposite not in answer


def test_ai19_a_cancelled_rename_says_nothing_and_a_blank_one_cannot_be_saved():
    attach = _text("chat-attach.js")
    body = attach[attach.index("async function promptTitle"):attach.index("function chatWriteRecord")]
    assert "field.required = true" in body
    assert "toast(" not in body


def test_hr11_the_download_toast_has_no_stray_comma():
    assert "to your browser's downloads." in _text("skills.js")
    assert ", to your browser's downloads" not in _text("skills.js")


def test_hr9_a_stop_before_the_first_word_writes_what_happened_into_the_bubble():
    src = _text("chat-attach.js")
    assert "if (stopped && !answerRaw && !toolEvents.length)" in src
    assert "Stopped before an answer." in src


def test_hr10_the_task_chip_title_does_not_repeat_the_label():
    src = _text("status.js")
    assert "...backgroundTasks.slice(1).map" in src
    assert "backgroundTasks.map((t) => `${t.label}" not in src


def test_hr19_a_cancelled_download_says_so():
    src = _text("settings-models.js")
    body = src[src.index("async function modelCancel"):]
    assert "toast(`Stopped downloading ${model.name}.`)" in body.split("refreshModelStatus")[0]


@needs_node
def test_hr17_a_list_setting_names_the_act_not_the_count(tmp_path):
    src = _text("settings-data.js")
    start = src.index("//: A list setting says what was added")
    end = src.index("//: A `/preferences` PUT, diffed")
    script = tmp_path / "t.js"
    script.write_text(
        "const nounCount = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;\n"
        "function settingShown(v) { if (v === true) return 'on'; if (v === false) return 'off'; if (v == null) return 'default';"
        " if (Array.isArray(v)) return nounCount(v.length, 'item'); return String(v); }\n"
        + src[src.index("function settingName"):src.index("function settingChangeWords")]
        + src[start:end]
        + "const c = (key, old, nw) => ({ changes: [{ key, old, new: nw }], kind: 'prefs' });\n"
        "console.log(JSON.stringify([\n"
        " settingChangeWords(c('personas', [], [{ name: 'Coach', prompt: 'x' }])),\n"
        " settingChangeWords(c('personas', [{ name: 'Coach' }], [])),\n"
        " settingChangeWords(c('disabled_tools', [], ['restore_board_item'])),\n"
        " settingChangeWords(c('disabled_tools', ['restore_board_item'], [])),\n"
        " settingChangeWords(c('skills', null, [{ name: 'A' }, { name: 'B' }])),\n"
        " settingChangeWords(c('web_search_enabled', false, true)),\n"
        "]));\n",
        encoding="utf-8",
    )
    out = subprocess.run(["node", str(script)], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == [
        "Added Coach to personas",
        "Removed Coach from personas",
        "Turned off restore board item",
        "Turned on restore board item",
        "Skills: default to 2 items",
        "Web search enabled: off to on",
    ]


def test_ai3_a_faded_companion_is_not_a_tab_stop():
    dodge = _text("avatars.js")
    assert 'buddy.toggleAttribute("inert", over);' in dodge
    # A visit (the enlarged preview) takes the dodge off, so it takes the inert off too.
    assert 'buddy.removeAttribute("inert");' in _text("companion-menu.js")
    # The tab-away state hides it outright, which also leaves the tab order.
    css = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
    assert re.search(r"#nm-buddy\.nmb-away \{[^}]*visibility: hidden", css)


def test_ai16_a_parked_sidebar_sheet_is_out_of_the_tab_order():
    css = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    parked = re.search(r"#skills-sidebar > \* \{\s*visibility: hidden;", css)
    assert parked, "the parked sheet's children are visibility: hidden (INBOX 433)"
