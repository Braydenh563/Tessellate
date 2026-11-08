"""The desk menu stays open after a choice that changes a setting (INBOX 1696): Activity, Stay here or Roam, Roam
over windows and the three sizes redraw the menu with the new tick and keep the focus on the row chosen. Before,
every row closed the menu (`leave`), so stepping Activity from Calm to Lively took two right-clicks and the tick
was never seen. A request that moves the figure (wave, come, go somewhere else, nap) or opens something still closes it."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "frontend" / "js" / "desk-companion.js").read_text(encoding="utf-8")
MENU = JS.split("async function openMenu(kind)")[1].split("\n  }\n")[0]


def test_the_setting_rows_keep_the_menu_open() -> None:
    for call in ('ask("set_stay", false)', 'ask("set_stay", true)', 'ask("set_roam", !motion.roam)', 'ask("set_lively"', 'ask("set_figure_size", name)'):
        at = MENU.index(call)
        line = MENU[MENU.rindex("\n", 0, at) : MENU.index("\n", at)]
        assert "keepOpen(() => " + call in line and "leave(() => " + call not in line, call


def test_keep_open_redraws_the_context_menu_after_the_answer_and_never_hides_the_panel() -> None:
    body = JS.split("async function keepOpen(action, row)")[1].split("\n  }\n")[0]
    assert body.index("await action()") < body.index("refocus = row;") < body.index('await openMenu("context")')
    assert "hide_panel" not in body and 'show("rest")' not in body


def test_the_redrawn_menu_puts_the_focus_back_on_the_row_chosen() -> None:
    assert 'let refocus = "";' in JS and "const again = refocus;" in MENU
    assert "row.textContent.startsWith(again)" in MENU and "|| live[0])?.focus()" in MENU


def test_requests_that_move_the_figure_or_open_something_still_close_it() -> None:
    assert 'leave(() => ask("figure_do", name))' in JS
    for call in ('ask("snooze")', 'ask("hide_companion")', 'ask("open_app", "settings")', 'ask("let_it_walk")'):
        assert "leave(() => " + call in JS, call


def test_the_guide_topic_says_a_setting_keeps_the_menu_open() -> None:
    text = (ROOT / "src" / "tessellate" / "ai" / "help_topics_more.py").read_text(encoding="utf-8")
    assert "settings keep it open" in text


def test_the_settings_popover_says_it_too() -> None:
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "a setting keeps the menu open with its new tick" in " ".join(html.split())
