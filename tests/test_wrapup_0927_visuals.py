"""The small visual carry-overs in wrapup-0927.md (10c, 10, 8), measured in Chromium.

Each test pins the shape of the fix; the numbers are in the ledger entry.

* 10c(1): an escaped select list is at least its trigger's width. Before,
  ten of thirteen were narrower (Library "Items per page" 131.5px under a
  215.6px trigger); after, every list measured is its trigger's width or
  wider.
* 10c(2): a chip's leading icon sat 1.5px above the chip's centre (a flex
  child ignores `vertical-align`); nudged 0.1em down.
* 10c(3): the Web panel's "..." waited for the engine status call.
* 10(d): a note card's meta row sat 6.4px under its text, 8px under "Show more".
* 8(b): today's count floated mid-head beside "Start today's note".
* 8(c): the reminder steppers sat apart from the readout they move.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"


def _read(name: str) -> str:
    return (FRONTEND / ("js/" + name if name.endswith(".js") else name)).read_text(encoding="utf-8")


def test_an_escaped_select_list_is_floored_at_its_trigger_width():
    menus = _read("menus.js")
    place = menus[menus.index("function wireEscapedActionMenu") :]
    floor = place.index('menu.classList.contains("select-menu")')
    # Written before the menu is measured, so the placement uses the floored width.
    assert floor < place.index("const box = menu.getBoundingClientRect();")
    assert "menu.style.minWidth = `${Math.min(anchor.width, innerWidth" in place


def test_a_chip_leading_icon_is_dropped_onto_its_words():
    """10c(2): icon ink centre minus the words' ink centre, Ask again chips:
    -1.84, -2.00, -0.84px before; -0.50, -0.66, +0.50 after (dark within 0.67).
    INBOX 592 replaced every per-family drop with the label recipe: the
    chip's icon moves by the live font's own gap (`--ph-cap-dy`)."""
    css = _read("css/07-whiteboard-misc.css")
    assert "translate: 0 calc(var(--ph-cap-dy) * 1em / 1.15 - var(--ph-ink-dy));" in css


def test_the_web_panel_draws_its_menu_before_the_status_call():
    """10c(3): the "..." was built only after /websearch/searxng/status
    answered (44 to 108ms here, seconds while Docker answers); now it is
    built in the same task that opens the panel (visible in 5ms)."""
    chat = _read("chat.js")
    body = chat[chat.index("function toggleWebPanel") :]
    body = body[: body.index("\n}\n")]
    assert body.index("renderWebPanelMenu(webEngineInfo);") < body.index("refreshWebSearxngStrip();")


def test_a_note_card_keeps_one_gap_above_its_metadata_row():
    """10(d): card view, box gap above the meta row: 6.4px under the text,
    8 under "Show more", 6.4 under a file row before; 8 (`--space-3`) under
    each after. The rows view is untouched (its meta sits beside the text)."""
    css = _read("css/07-whiteboard-misc.css")
    assert "#entry-list:not(.is-rows) > li > .entry-meta {\n  margin-top: var(--space-3);\n}" in css


def test_today_keeps_its_count_in_the_column_of_counts():
    """8(b): with rows today, the count floated 729px short of the head's end
    (two auto margins split the space); after, it ends where every other
    day's count does (0px), with "Start today's note" just before it."""
    css = _read("css/07-whiteboard-misc.css")
    assert (
        ".timeline-bucket-head:has(> .timeline-today-action) > .timeline-bucket-count {\n"
        "  order: 1;\n  margin-left: 0;\n}"
    ) in css


def test_the_reminder_steppers_follow_quick_set_and_lead_the_readout():
    """8(c): at 1440 the steppers sat at the row's end, 725px past the readout
    text, and moved 101.5px left when Reset appeared; after, they follow
    Quick set by 8px at one place whatever the readout says, and the readout
    follows them by 8px."""
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    row = html[html.index('id="reminder-due-row"') :]
    row = row[: row.index('<p class="muted reminder-hint">')]
    assert row.index('id="reminder-presets-menu"') < row.index('class="stepper-pair"') < row.index('id="reminder-due-readout"')
    pair = _read("css/01-forms-settings.css")
    pair = pair[pair.index(".stepper-pair {") :]
    assert "margin-inline-start: auto" not in pair[: pair.index("}")]
    widgets = _read("css/03-dashboard-widgets.css")
    readout = widgets[widgets.index("#reminder-due-readout {") :]
    assert "min-width" not in readout[: readout.index("}")]
