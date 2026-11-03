"""DX29 (audit 1102): a hover gutter handle that drags a Live block.

Static checks only; the drag itself is measured in the running app (the
numbers are in docs/roadmap/agent-remaining/a29l-1102.md).
"""

import re

from tests._app_js import documents_text


def _plugin() -> str:
    text = documents_text()
    start = text.index("docLiveExtensions.dragHandle = ")
    end = text.index("\n};\n", start)
    return text[start:end]


def test_handle_is_a_live_extension() -> None:
    text = documents_text()
    assert "docLiveExtensions.dragHandle = " in text
    live = text[text.index("function docLiveExtensions(CM)"):]
    assert "docLiveExtensions.dragHandle(CM)" in live.split("}", 1)[0]


def test_handle_is_a_decorative_grip_naming_the_keyboard_path() -> None:
    plugin = _plugin()
    assert "ph-dots-six-vertical" in plugin
    assert 'setAttribute("aria-hidden", "true")' in plugin
    assert "Alt+Up" in plugin and "Alt+Down" in plugin


def test_handle_reuses_the_keyboard_move() -> None:
    plugin = _plugin()
    assert "docBlockMoveEdit(" in plugin


def test_handle_skips_code_documents_and_coarse_pointers() -> None:
    plugin = _plugin()
    assert "docFileType().previewable" in plugin
    assert '(hover: none)' in plugin


def test_drop_is_one_transaction() -> None:
    plugin = _plugin()
    assert len(re.findall(r"\.dispatch\(", plugin)) == 1
    assert 'userEvent: "move.line"' in plugin


def test_move_edit_reports_the_unit_and_the_neighbour() -> None:
    text = documents_text()
    body = text[text.index("function docBlockMoveEdit("):text.index("function docBlockMoveRun(")]
    assert "hopFrom" in body and "hopTo" in body and "unit:" in body


def test_stale_comments_are_updated() -> None:
    text = documents_text()
    assert "A drag handle was left out" not in text
    assert "What is lost, said plainly" not in text
