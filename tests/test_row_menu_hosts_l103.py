"""L-world-class-103: a right-click, and a hold on touch, on every card and row
that has its own ⋯.

One delegated listener (navigation.js `ROW_MENU_HOSTS`) answers both, so the
work is the list: a row type that carries a `kebabMenu` and is missing from it
shows the browser's own menu. Measured at 1440 on a seeded notebook before the
change: the reminders rows, the skill cards, the Manage tags and categories
rows, the recordings, the sidebar's categories and the model cards were
unhosted (`scratchpad/ui-sweeps/rowmenus.js` drives all of them, mouse and
touch).
"""

from __future__ import annotations

import re

from tests._app_js import app_js_text

# Row type -> the selector it joins by, and where its rows are built.
NEW_HOSTS = {
    "#reminder-groups li": "shell-reminders.js",
    ".skill-card": "library.js",
    ".manage-cat-row": "tag-manager.js",
    ".recording-row": "meetings.js",
    "#category-list li[data-category]": "notes-list.js",
    ".model-card": "settings-models.js",
}


def _hosts() -> list[str]:
    text = app_js_text()
    start = text.index("const ROW_MENU_HOSTS")
    block = text[start : text.index('].join(", ");', start)]
    return re.findall(r'^\s*"([^"]+)",?\s*$', block, re.M)


def test_every_row_that_carries_its_own_menu_is_a_host():
    hosts = _hosts()
    for selector in NEW_HOSTS:
        assert selector in hosts, selector


def test_a_host_selector_still_names_something_that_is_built():
    """A renamed row class would drop out of the list silently (the browser's
    menu comes back); each selector's class or id must still be built in the
    frontend."""
    text = app_js_text()
    for selector in _hosts():
        for token in re.findall(r"[.#]([A-Za-z][\w-]*)", selector):
            assert token in text, f"{selector}: {token} is no longer built anywhere"


def test_the_host_rows_are_built_where_the_table_says():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "frontend" / "js"
    for selector, name in NEW_HOSTS.items():
        token = re.findall(r"[.#]([A-Za-z][\w-]*)", selector)[0]
        assert token in (root / name).read_text(encoding="utf-8") or token in app_js_text(), (selector, name)


def test_the_hold_is_500_ms_and_cancelled_by_a_move_past_8_px_not_by_jitter():
    text = app_js_text()
    assert "const LONG_PRESS_MS = 500;" in text
    assert "Math.hypot(move.clientX - clientX, move.clientY - clientY) <= 8) return;" in text, (
        "a bare pointermove cancelled every hold a finger's jitter touched"
    )


def test_the_hold_opens_its_menu_before_it_swallows_the_lift_off():
    """A note's menu is opened by clicking its own button; the swallow listens
    for clicks in the capture phase and would take that one."""
    text = app_js_text()
    body = text[text.index("const swallowed =") :][:1800]
    assert body.index("handler(event, {") < body.index("document.addEventListener(type, swallow, true)")


def test_one_listener_and_one_hold_answer_every_host():
    text = app_js_text()
    start = text.index("const ROW_MENU_HOSTS")
    block = text[start : text.index("function arrowNavTarget")]
    assert block.count('addEventListener("contextmenu"') == 1
    assert block.count("selector: ROW_MENU_HOSTS") == 1
