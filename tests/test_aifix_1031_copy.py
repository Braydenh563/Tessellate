"""Words and small flows from the 2026-10-31 audit (AI12, AI19, HR9, HR10, HR11, HR17, HR19)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._app_js import with_pieces
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _text(name: str) -> str:
    return with_pieces(name)


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
    assert "if (t.stopped && !answerRaw && !toolEvents.length)" in src
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
    css = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    assert re.search(r"#nm-buddy\.nmb-away \{[^}]*visibility: hidden", css)


def test_ai16_a_parked_sidebar_sheet_is_out_of_the_tab_order():
    css = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    parked = re.search(r"#skills-sidebar > \* \{\s*visibility: hidden;", css)
    assert parked, "the parked sheet's children are visibility: hidden (INBOX 433)"


def test_ai17_an_arrow_key_moves_the_companion_and_the_guide_says_so():
    src = _text("avatars.js")
    assert "const NMB_NUDGE = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };" in src
    assert "const far = event.shiftKey ? 64 : 16;" in src
    from tessellate.ai import help_topics_more

    body = next(t["body"] for t in help_topics_more.MORE_TOPICS if t["id"] == "companion")
    assert "arrow key" in body and "16 pixels" in body and "Shift 64" in body


def test_ai10_requests_are_clipped_to_the_server_caps_before_they_go():
    from tessellate.api import routes_chat, routes_search

    chat = _text("chat.js")
    #: One shared question cap (audit 1031 AI9, tests/test_warm12_1101.py): the
    #: routes' numbers are `search/query.py`'s, and the page's is `CLIP_LIMITS.cap`.
    cap = int(re.search(r"\}\)\)\((\d+)\);", re.search(r"const CLIP_LIMITS = .*", chat).group(0)).group(1))
    answer = int(re.search(r"followAnswer: (\d+)", chat).group(1))
    assert cap == routes_search.WarmBody.model_fields["q"].metadata[0].max_length
    follow = routes_chat.FollowupBody.model_fields
    assert cap == follow["question"].metadata[0].max_length
    assert answer == follow["answer"].metadata[0].max_length
    assert 'clipFor("warm", q)' in _text("navigation.js")
    for name in ("chat-attach.js", "ask-compose.js"):
        assert 'clipFor("followQuestion", question)' in _text(name) and 'clipFor("followAnswer", answer)' in _text(name)
    # A one-word answer has no outline: the mind map item is not offered for it.
    assert 'trim().split(/\\s+/).length < 4 ? null : { label: "ph:tree-structure"' in chat


def test_hr12_an_import_the_server_refuses_says_why():
    src = _text("settings-controls.js")
    body = src[src.index("function pickJsonFile"):src.index("function textToSteps")]
    assert "await apply(data);" in body
    assert "apply(JSON.parse(" not in body
    assert 'toast(error?.message || "Couldn\'t import that file.", "info");' in body


def test_ai21_archiving_a_chat_from_its_row_repaints_the_list():
    """Measured gone from the sidebar 100 ms after Archive, open chat or not
    (audit 1031 saw the row stay): the handler repaints, and the server list
    leaves archived chats out."""
    js = _text("sheets-selects.js")
    handler = js[js.index('makeMenuItem("ph:archive Archive"'):]
    handler = handler[: handler.index("items.push(")]
    assert "chatArchiveUndo" in handler and "loadConversationList()" in handler


def test_ai5_the_dock_web_button_asks_before_its_first_turn_on():
    js = _text("wiring.js")
    toggle = js[js.index("async function toggleWebSearch("):]
    toggle = toggle[: toggle.index('$("web-search-toggle")')]
    asked = toggle.index("confirmDialog(")
    assert asked < toggle.index('"/preferences"'), "the question comes before the save"
    assert "never your notes" in toggle and "Don't ask again" in toggle
    assert "next && openFirst" in toggle, "only the dock's own button asks; the palette and the slash row do not"
    from tessellate.ai import help_chat

    body = next(t["body"] for t in help_chat.HELP_TOPICS if t["id"] == "websearch")
    assert "it asks first" in body


def test_ai14_escape_gives_the_keyboard_back():
    edit = _text("chat-edit.js")
    assert "cancel.addEventListener(\"click\", cancelEdit)" in edit and 'button[title="Edit this question"]' in edit
    wiring = _text("settings-wiring.js")
    assert '["ask-history-toggle", "ask-history-panel"]' in wiring and 'event.key !== "Escape"' in wiring
    attach = _text("chat-attach.js")
    assert attach.count('restoreFocusTo($("chat-input"))') >= 2


def test_hr20_confirms_queue_so_each_one_takes_focus():
    """Two confirms asked together show one at a time (HR20)."""
    from tests._app_js import app_js_text

    js = app_js_text()
    body = js[js.index("// One confirm at a time") : js.index("// `confirmDialog`'s missing sibling")]
    assert "confirmDialog.q = (confirmDialog.q || Promise.resolve()).then(show, show)" in body, (
        "each confirm waits for the one before, answered or not"
    )


def test_hr22_the_engine_detail_reads_on_the_hover_tone():
    """The muted detail on a hovered engine row was 3.8:1 light and 3.2:1 dark (HR22)."""
    css = (ROOT / "frontend" / "css" / "settings-controls-lazy.css").read_text(encoding="utf-8")
    rule = css[css.index(".provider-option:is(:hover, :has(:focus-visible)) .provider-detail") :][:120]
    assert "color: var(--text);" in rule, rule


def test_hr18_a_shut_model_group_builds_no_cards_until_it_opens():
    """Settings > Models built all 31 cards on open; a shut fold builds none (HR18)."""
    js = unwrapped((ROOT / "frontend" / "js" / "settings-models.js").read_text(encoding="utf-8"))
    fill = js[js.index("for (const group of groups) {\n    const grid") :][:300]
    assert "!grid.parentNode.open" in fill, fill
    toggle = js[js.index('section.addEventListener("toggle"') :][:260]
    assert "if (section.open && modelLastStatus) renderSuggested(modelLastStatus);" in toggle, toggle


def test_hr23_the_log_list_draws_the_newest_window_and_offers_the_rest():
    """500 records were 500 rows built on open (90 to 126 ms); the list draws the
    newest 200 and a row offers earlier ones, so follow mode still ends on the newest (HR23)."""
    js = (ROOT / "frontend" / "js" / "settings.js").read_text(encoding="utf-8")
    body = js[js.index("function renderLogList()") :][:1800]
    assert "LOG_WINDOW" in js and "visible.slice(-cap)" in body, body
    assert "earlier record" in body, "the rest is one press away"
    assert "list.dataset.window" in body, "no new top-level state (global-scope ratchet)"
