"""One changed-row bar x for every row recipe, and the Help "Where" line kept
inside its topic's fold (INBOX 1610, 1612). Measured in a browser by the sweep
the commit names; this keeps the rules that make the numbers from drifting."""
from tests._help_text import help_more_text
from pathlib import Path
from tests._js_scope import unwrapped
from tests._css_paths import sheets

CSS = Path(__file__).resolve().parent.parent / "frontend" / "css"


def _rules(name: str, scope: str) -> list[str]:
    text = (CSS / name).read_text(encoding="utf-8")
    return [
        text[i : text.index("}", i)]
        for i in range(len(text))
        if text.startswith(f"{scope} .setting-modified::before", i)
        or text.startswith(f"{scope} :is(.check-row, .setting-check, .checkbox-label).setting-modified::before", i)
    ]


def test_the_changed_bar_sits_one_inset_from_the_text_edge_on_every_recipe():
    """Intent moved (INBOX 1696 c): two gutters from the text edge put the bar
    on the group's border ("right against the edge"); one token from the text
    edge now, inside the group. Measured (bars sweep, 1440 and 390): 77 rows,
    every bar 8px from its row's text edge; before 76 at 16px and one at 32."""
    shell = (CSS / "00-tokens-shell.css").read_text(encoding="utf-8")
    assert shell.count("--setting-bar-inset:") == 1
    for name, scope in (("01-forms-settings.css", "#settings-modal"), ("appearance-panel-lazy.css", "#appearance-panel")):
        rules = _rules(name, scope)
        assert len(rules) >= 1, (name, rules)
        assert "calc(-1 * var(--setting-bar-inset))" in rules[0]
        if name != "appearance-panel-lazy.css":
            continue
        assert "calc(var(--space-3) - var(--setting-bar-inset))" in rules[1]
    lazy = (CSS / "settings-controls-lazy.css").read_text(encoding="utf-8")
    assert "#settings-modal :is(.check-row, .setting-check, .checkbox-label).setting-modified::before {\n  inset-inline-start: calc(var(--space-3) - var(--setting-bar-inset))" in lazy
    for text in (lazy, (CSS / "appearance-panel-lazy.css").read_text(encoding="utf-8")):
        assert ".settings-group.setting-modified::before {\n  inset-inline-start: calc(1rem - var(--setting-bar-inset))" in text


def test_every_changed_bar_rule_offsets_by_the_one_token():
    """The lint (INBOX 1696 c): a rule anywhere that places a changed row's
    bar does it with `--setting-bar-inset` and the row's own padding, never a
    literal, so a new row recipe cannot put its bar on an x of its own."""
    import re

    bad = []
    for path in sorted(CSS.glob("*.css")):
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"(?:(?<=[{}])|\A)([^{}]*\.setting-modified::before)\s*\{([^}]*)\}", text):
            body = m.group(2)
            if "inset-inline-start" in body or re.search(r"(^|[^-])left\s*:", body):
                if "var(--setting-bar-inset)" not in body or re.search(r"(^|[^-])left\s*:", body):
                    bad.append((path.name, m.group(1).strip()[-80:]))
    assert not bad, bad
    #: The switch that leads a help head hangs like its neighbours, so its bar
    #: is on their x (it sat 9px further in).
    consistency = sheets("02-chat-graph.css", "06-timeline-dialogs.css", "07-whiteboard-misc.css")
    assert ".row.help-head > label:is(.check-row, .setting-check):first-child:has(> input[type=\"checkbox\"]) {\n  margin-inline-start: calc(-1 * var(--space-3) - 1px);" in consistency


def test_the_where_line_is_the_last_line_of_its_fold():
    text = sheets("02-chat-graph.css", "06-timeline-dialogs.css", "07-whiteboard-misc.css")
    i = text.index(".help-accordion > details > p.help-topic-links {")
    rule = text[i : text.index("}", i)]
    assert "margin: 0 0 0 var(--space-7)" in rule
    assert "border-top: 0" in rule
    assert "p.help-topic-links" not in (CSS / "04-chat-dock-appearance.css").read_text(encoding="utf-8")


def test_a_selection_bar_keeps_a_gap_to_its_list_and_takes_the_pane_heads_box():
    """INBOX 1605: the bar touched the first row (0px, now 8) and, in a Settings
    group, stuck over the pane head offset 17px and 34px narrower."""
    shell = (CSS / "00-tokens-shell.css").read_text(encoding="utf-8")
    i = shell.index(".library-contextbar {")
    assert "margin-block: var(--space-4) var(--space-3)" in shell[i : shell.index("}", i)]
    lazy = (CSS / "settings-controls-lazy.css").read_text(encoding="utf-8")
    assert "#settings-modal .settings-group > .selectbar {\n  margin-inline: calc(-1rem - 1px);" in lazy


def test_the_drag_grip_steps_off_a_cards_own_tick():
    js = (CSS.parent / "js" / "obj-drag.js").read_text(encoding="utf-8")
    assert 'next.querySelectorAll(\'input[type="checkbox"]\')' in js


def test_the_log_view_shows_what_a_filter_hid_and_loads_older_records_on_scroll():
    """INBOX 1608: the owner's Errors-only filter hid the rest and read as deleted."""
    root = CSS.parent
    settings = (root / "js" / "settings.js").read_text(encoding="utf-8")
    controls = unwrapped((root / "js" / "settings-controls.js").read_text(encoding="utf-8"))
    assert '"Show them", "Clear the filters"' in settings
    assert "hidden by the filters above, not deleted" in settings
    assert 'id="logs-refresh"' in (root / "index.html").read_text(encoding="utf-8")
    assert '$("logs-refresh").addEventListener("click"' in controls
    assert 'if (list.scrollTop < 80)' in controls


def test_the_desktop_companion_switch_is_in_appearance_beside_the_corner_companion():
    """INBOX 1611: the owner looked for it under Corner companion, not About."""
    html = (CSS.parent / "index.html").read_text(encoding="utf-8")
    appearance = html.split('id="settings-appearance"', 1)[1].split('id="settings-extras"', 1)[0]
    assert 'id="desktop-companion-row"' in appearance and 'id="desktop-companion-help"' in appearance
    about = html.split('id="settings-about"', 1)[1]
    assert 'id="desktop-companion-row"' not in about
    topics = help_more_text()
    assert "Settings, Appearance, Corner companion, Show the companion on the desktop" in topics
