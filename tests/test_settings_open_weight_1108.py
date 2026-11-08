"""Settings' first open stays light (perf audit 1108 P4, P12), pinned in the source.

Measured at 4x CPU on 500 notes: 921 listeners and +2,721 nodes on the first open, +47 listeners on every
reopen. The browser numbers are in CHANGELOG; these hold the shape that produced the drop.
"""

from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"


def _src(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def test_help_triggers_share_one_capture_listener():
    menus = _src("menus.js")
    wire = menus[menus.index("function wireHelpPopover(") : menus.index("wireHelpPopover.triggers = ")]
    assert 'trigger.addEventListener("click"' not in wire
    assert "wireHelpPopover.triggers.set(trigger, entry)" in wire
    assert "}, true);" in menus[: menus.index("function wireHelpPopover(")]
    # the panel's own stop waits for its first open
    assert "panel._helpStop" in wire


def test_selects_in_unshown_settings_panes_wait_for_the_pane():
    selects = _src("sheets-selects.js")
    assert 'select.closest("#settings-modal .settings-section.hidden")' in selects
    show = _src("settings.js")
    show = show[show.index("function showSettingsSection(") :]
    assert "enhanceAllSelects($(`settings-${name}`))" in show[:4000]


def test_guide_topics_draw_their_text_when_opened_or_matched():
    find = _src("settings-find.js")
    row = find[find.index("function helpTopicRow(") : find.index("// --- search (INBOX 520)")]
    assert "helpTopicPaint(" not in row
    assert "if (searching || details._painted) helpTopicPaint(details, rx)" in find


def test_reopen_redraws_nothing_it_already_has():
    assert "drawn.length === STATUS_SLOTS.length" in _src("settings-controls.js")
    assert "const reuse = host.dataset.knobs === names" in _src("settings-health.js")
    close = _src("settings.js")
    close = close[close.index("function closeSettingsModal(") :][:900]
    assert "if (search?.value)" in close
