"""WCAG 2.2 AA findings fixed from the axe-core and accessibility-tree scans
(INBOX 433, `scratchpad/ui-sweeps/axe.js`, `srtree.js`, `zoom.js`).

Each test pins one finding as it was measured in Chromium:

* No main landmark on five tabs, and a different one on the other three.
* Every resize grip (a focusable separator) lacked `aria-valuenow`.
* Two labels dimmed by opacity read under 4.5:1 in light.
* A list of rows that are buttons held no list items.
* The document editor and every note box had no accessible name.
"""

import re
from pathlib import Path

from tests._app_js import with_pieces
from tests._css_paths import css_text

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
CSS = FRONTEND / "css"


def _read(name: str) -> str:
    return (FRONTEND / ("js/" + name if name.endswith(".js") else name)).read_text(encoding="utf-8")


def _function(source: str, name: str) -> str:
    start = re.search(rf"^(?:async )?function {name}\(", source, re.M)
    assert start, f"{name} not found"
    rest = source[start.end():]
    return rest[: re.search(r"^}", rest, re.M).start()]


def test_one_main_landmark_wraps_the_tab_pages():
    html = _read("index.html")
    assert html.count("<main") == 1 and html.count("</main>") == 1
    main = html[html.index('<main id="app-main">'):html.index("</main>")]
    for tab in ("dashboard", "notes", "chat", "timeline", "graph", "documents", "reminders", "library"):
        assert f'id="tab-{tab}"' in main, tab
    css = (CSS / "08-consistency.css").read_text(encoding="utf-8")
    assert re.search(r"#app-main \{\s*display: contents;\s*\}", css)
    # No rule still names the inner element by its old tag.
    for path in CSS.glob("*.css"):
        assert not re.search(r"(\.layout ?> ?|split > |~ )main\b", path.read_text(encoding="utf-8")), path.name


def test_every_resize_grip_states_its_value():
    sheets = _read("sheets-selects.js")
    track = _function(sheets, "trackSeparatorValue")
    for attr in ("aria-valuemin", "aria-valuemax", "aria-valuenow", "aria-valuetext"):
        assert attr in track
    assert "ResizeObserver" in track
    assert "trackSeparatorValue(handle, aside, SIDEBAR_MIN, SIDEBAR_MAX)" in sheets
    assert "trackSeparatorValue(handle, panel, WEB_PANEL_MIN, WEB_PANEL_MAX)" in sheets
    assert "trackSeparatorValue(handle, $(\"doc-prose-panel\")" in _read("documents.js")
    # Every separator built anywhere goes through it. `js/`, not the root:
    # the root holds only the service worker, so this loop checked nothing
    # (found 2026-10-04).
    scripts = sorted((FRONTEND / "js").glob("*.js"))
    assert len(scripts) > 20
    for path in scripts:
        text = path.read_text(encoding="utf-8")
        if 'setAttribute("role", "separator")' in text and 'tabindex", "0"' in text:
            assert "trackSeparatorValue(" in text, path.name


def test_dimmed_labels_are_dimmed_by_colour_not_opacity():
    shell = (CSS / "00-tokens-shell.css").read_text(encoding="utf-8")
    count = shell[shell.index(".library-chip-count {"):]
    count = count[: count.index("}")]
    assert not re.search(r"^\s*opacity:", count, re.M) and "color: var(--muted);" in count
    forms = (CSS / "01-forms-settings.css").read_text(encoding="utf-8")
    toggle = forms[forms.index("#web-search-toggle:not(.active) {"):]
    toggle = toggle[: toggle.index("}")]
    assert not re.search(r"^\s*opacity:", toggle, re.M) and "color: var(--muted);" in toggle


def test_a_list_of_button_rows_is_a_group():
    dash = _read("dashboard.js")
    assert 'if (!ul.hasAttribute("role")) ul.setAttribute("role", "group");' in _function(dash, "dashActionRow")
    assert 'list.setAttribute("role", "group");' in dash
    assert 'id="ask-history-list" class="ask-history-list" role="group"' in _read("index.html")


def test_the_editors_have_names():
    docs = _read("documents.js")
    assert '"aria-label": "Document text"' in docs
    assert '"aria-label": noteSurfaceName(host)' in _function(docs, "noteSurfaceExtensions")
    name = _function(docs, "noteSurfaceName")
    assert 'split("\\n")[0]' in name
    html = _read("index.html")
    assert 'id="entry-content" data-autocorrect rows="3" class="autogrow" aria-label="New note"' in html
    for field in ("persona-prompt", "template-name", "template-description", "template-body"):
        tag = html[html.index(f'id="{field}"'):]
        assert "aria-label=" in tag[: tag.index(">")], field
    assert 'textarea.setAttribute("aria-label", "Note text")' in _read("note-edit-panels.js")


def test_find_anything_is_a_listbox_only_while_it_lists():
    find = _read("search.js")
    role = _function(find, "finderResultsRole")
    assert 'listing ? "listbox" : "group"' in role
    assert "finderResultsRole(results, false);" in _function(find, "finderRenderEmpty")
    assert "finderResultsRole(results, rows.length > 0);" in _function(find, "finderRender")
    assert 'id="finder-results" class="finder-results" role="group"' in _read("index.html")


def test_the_keyboard_lands_somewhere_after_every_note_step():
    # notekeys.js: F2 left the focus on <body>, Escape too, and a move by the
    # chooser too; a chooser opened on its X, so Enter closed it.
    notes = _read("notes-list.js")
    assert "else focusBodyAfterRender = id;" in _function(notes, "openNoteEditor")
    assert "focusNoteRow(back)" in _function(_read("note-edit-panels.js"), "closeNoteForm")
    row = _function(notes, "focusNoteRow")
    assert "active !== document.body" in row and "row.focus(" in row
    assert "if (!many) focusNoteRow(noteIds[0]);" in _read("categories-panel.js")
    sheet = _function(_read("phone-shell.js"), "openSheet")
    assert "'.sheet-row[aria-current=\"true\"]'" in sheet
    assert "ArrowDown: 1, ArrowUp: -1" in sheet


def test_focus_is_never_hidden_under_sticky_or_floating_furniture():
    # zoom.js at 400% (320x256) and 320 wide: Tab reached an off-screen
    # drawer, controls under the floating New note, and controls under the
    # sticky sub-tabs.
    misc = (CSS / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    closed = misc[misc.index("#skills-sidebar:not(.sidebar-sheet-open) {\n    overflow-y: hidden;") - 200:]
    assert "#sidebar:not(.sidebar-sheet-open)," in closed
    assert ".tab-page:has(> .dock-fab) .tab-main {\n    scroll-padding-bottom:" in misc
    side = (CSS / "05-sidebars-themes.css").read_text(encoding="utf-8")
    assert "#tab-notes .tab-main,\n#tab-library,\n#tab-library .tab-main {\n  scroll-padding-top:" in side
    resp = (CSS / "10-responsive.css").read_text(encoding="utf-8")
    short = resp[resp.index("@media (max-height: 420px) {"):]
    assert ".notes-subtabs,\n  .library-subtabs {\n    position: static;" in short
    assert 'const PHONE_FAB = "(max-width: 599.98px) and (min-height: 421px)";' in _read("phone-shell.js")


def test_single_key_shortcuts_can_be_turned_off():
    # WCAG 2.1.4: the "m" chord, "/" and "?" fired on a lone letter with no
    # way to turn them off.
    wiring = _read("settings-wiring.js")
    assert "const singleKeys = singleKeysOn();" in wiring
    assert "if (!typing && !overlayOpen && singleKeys && !boardOwns) {" in wiring
    assert 'singleKeys && e.key === "m" && !e.ctrlKey' in wiring
    assert 'prefs.get("singleKeys", null) !== "off"' in _function(wiring, "singleKeysOn")
    assert 'id="pref-single-keys"' in _read("index.html")


def test_a_select_opener_name_contains_the_words_on_its_face():
    """axe `label-content-name-mismatch` (2026-10-10, 22 findings per theme):
    every sort and model picker was named "Sort notes" while its face read
    "Newest first". Label in Name (2.5.3) wants the visible words inside the
    accessible name; the opener's aria-label is rewritten with the value."""
    selects = _read("sheets-selects.js")
    sync = selects[selects.index("const syncValue = () => {"):]
    sync = sync[: sync.index("opener.disabled = select.disabled;")]
    assert 'opener.setAttribute(' in sync and '`${label}: ${shown}`' in sync
    assert "select-opener-icon" in sync, "an icon-only opener shows no text and keeps the plain label"


# The 13 buttons that `index.html` ships with no text, `aria-label` or
# `title` (Brief 56, `scratchpad/ui-sweeps/hierarchy.js`): the plan counted
# them as unlabelled icon-only buttons from the markup alone. Observed in the
# running app, none of them is: JS paints each before it can be seen (the
# status bar's `paintStatusItem`, the Logs dock's `renderCopyLogsLabel`), and
# the live scan of 20 surfaces, 7 menus per surface and 19 dialogs found no
# visible control without a name. The set is pinned so a new empty button in
# the markup fails here, with the painter it has to have named in the message.
EMPTY_MARKUP_BUTTONS = {
    "status-notes", "status-reminders", "status-task", "status-activity",
    "status-command", "status-agent", "status-guide", "status-find",
    "status-back", "status-forward", "status-undo", "status-redo", "logs-copy",
    #: The utility clock chip (Brief 89): hidden until a timer or stopwatch
    #: runs, and `paintUtilityChip` (utility-tools.js) names it before it shows.
    "status-timer",
}


def _all_js() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted((FRONTEND / "js").glob("*.js")))


def _empty_markup_buttons() -> set[str]:
    from html.parser import HTMLParser

    found: set[str] = set()

    class Parser(HTMLParser):
        current = None

        def handle_starttag(self, tag, attrs):
            if tag == "button":
                self.current = {"attrs": dict(attrs), "text": ""}

        def handle_data(self, data):
            if self.current is not None:
                self.current["text"] += data

        def handle_endtag(self, tag):
            if tag != "button" or self.current is None:
                return
            attrs, text = self.current["attrs"], self.current["text"]
            self.current = None
            if not text.strip() and not attrs.get("aria-label") and not attrs.get("title"):
                found.add(attrs.get("id") or f"<button class={attrs.get('class')!r}>")

    Parser().feed(_read("index.html"))
    return found


def test_an_empty_markup_button_is_one_that_js_paints():
    found = _empty_markup_buttons()
    assert found == EMPTY_MARKUP_BUTTONS, (
        "a button in index.html has no text, aria-label or title: give it one, "
        f"or paint it from JS and add its id here. Difference: {sorted(found ^ EMPTY_MARKUP_BUTTONS)}"
    )
    js = _all_js()
    for button_id in EMPTY_MARKUP_BUTTONS:
        assert f'paintStatusItem("{button_id}"' in js or f'$("{button_id}")' in js, button_id
    # The status items are named by the text paintStatusItem writes into them.
    paint = _function(js, "paintStatusItem")
    assert "button.replaceChildren();" in paint and "text.textContent = label;" in paint


def test_buttons_js_builds_hidden_are_named_when_they_show():
    # hierarchy.js found these in the DOM with no name while `hidden`; each is
    # named in the pass that un-hides it.
    js = _all_js()
    map_js = _read("whiteboard-map.js")
    for marker in (
        'box.setAttribute("aria-label", task === "done" ? "Done" : "Not done");',
        'noteMark.setAttribute("aria-label", "Open the note behind this topic");',
        'link.setAttribute("aria-label", `Open the page this topic links to`);',
        'chevron.setAttribute("aria-label", chevron.title);',
        'badge.setAttribute("aria-label", label);',
    ):
        assert marker in map_js, marker
    ai = _read("ai-tools.js")
    assert "badge.hidden = !name;" in ai and "badge.textContent = missing" in ai
    assert "renderCopyLogsLabel" in js
def test_a_task_checkbox_in_a_note_card_is_named_by_its_task():
    """axe `label` (critical, 20 boxes, 2026-10-10): the disabled checkbox a
    "- [ ] task" line draws had no name. Done or To do, then the words."""
    cards = _read("notes-list.js")
    start = cards.index('box.type = "checkbox";')
    block = cards[start: start + 900]
    assert 'box.setAttribute("aria-label", `${box.checked ? "Done" : "To do"}: ' in block


def test_the_heatmap_scroller_is_a_tab_stop_with_a_ring():
    """axe `scrollable-region-focusable` (serious, 2026-10-10): `.heatmap`
    scrolls sideways and held nothing focusable."""
    dash = _function(_read("dashboard.js"), "renderHeatmapWidget")
    assert "grid.tabIndex = 0;" in dash
    assert 'grid.setAttribute("aria-label"' in dash
    # The ring is the base `:focus-visible` rule's, not a heatmap rule: a tab
    # stop gets it for free and the boot CSS has no bytes to spare.
    base = (CSS / "02-chat-graph.css").read_text(encoding="utf-8")
    assert re.search(r"^:focus-visible \{\s*outline: ", base, re.M)


def test_the_folded_tags_chip_keeps_a_24px_target():
    """axe `target-size` (serious, 2026-10-10): the "+N" chip was 23.6 by 24
    px at 390. WCAG 2.5.8 wants 24 on both sides."""
    css = (CSS / "08-consistency.css").read_text(encoding="utf-8")
    rule = re.search(r"\.note-meta > \.note-meta-more \{([^}]*)\}", css)
    assert rule, ".note-meta-more rule missing"
    assert "min-width: 24px;" in rule.group(1)  # the height is the chip's own 24
    assert 'chip("+0", "note-meta-more"' in _read("note-cards.js")


def test_an_icon_only_control_is_named_by_aria_label_not_title_alone():
    """a11yname.js (2026-10-10): 93 icon-only controls in the Notes list at
    1440 had a `title` and no `aria-label`; a title never shows on touch. The
    x buttons (`.unlink`) share one helper (note-cards.js: app.js is at its
    size ratchet), and a chip folded to its icon
    keeps its words as the name."""
    helper = _function(_read("note-cards.js"), "makeUnlinkAccessible")
    assert 'span.setAttribute("aria-label", span.title)' in helper
    cards = _read("note-cards.js")
    assert 'el.setAttribute("aria-label", el.title)' in cards[cards.index('el.classList.add("is-icon")'):][:400]


# Sweep findings: focus rings, list semantics, state said to a screen reader, names and groups (INBOX 800).


def _strip(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def test_a_solid_map_topic_keeps_its_progress_count_legible():
    # "3/7" drew in --muted (1.00:1) on the branch colour of a solid topic:
    # the `.wb-map-core` and `.wb-map-filled` rules named it, `.wb-map-solid`
    # (a bold main branch, any topic filled Solid) did not.
    css = _strip(css_text())
    rule = re.search(r"\.wb-map-node\.wb-map-solid:not\(\[data-shape=\"none\"\]\) :is\(([^)]*)\)\s*\{[^}]*color:\s*var\(--wb-core-ink\)", css)
    assert rule, "no ink rule for a solid topic's children"
    assert ".wb-map-progress" in rule.group(1)


def test_a_disabled_task_box_on_a_note_card_says_why():
    from _app_js import app_js_text

    js = app_js_text()
    at = js.index('item.className = "entry-task"')
    block = js[at : at + 1400]
    assert "box.disabled = true" in block
    assert 'box.title = "' in block


def test_the_chosen_chat_mode_keeps_a_visible_focus_ring_in_the_ink_palettes():
    # The ring was --on-accent (white) because a chosen segment was an accent
    # fill. In Utilitarian, Paper and Mono the chosen segment is an 11% ink
    # tint, so the white ring drew at 1.3:1 on it (focusring.js, 219 vs 255).
    css = _strip(css_text())
    rule = re.search(
        r':root:is\(\[data-palette="utilitarian"\], \[data-palette="paper"\], \[data-palette="mono"\]\) '
        r"\.chat-dock-controls \.seg > button:is\(\.active, \[aria-pressed=\"true\"\]\):focus-visible\s*\{([^}]*)\}",
        css,
    )
    assert rule and "outline-color: var(--ink)" in rule.group(1)


def test_a_dashboard_digest_line_is_a_list_item_holding_its_link():
    # axe `list` (serious): the Dashboard's "today" digest set role="link" on
    # each `li`, which stops it being a list item inside its `ul`.

    js = with_pieces("dashboard.js")
    at = js.index('li.className = line.kind === "quote"')
    block = js[at : at + 1400]
    assert 'li.setAttribute("role"' not in block
    assert 'link.setAttribute("role", "link")' in block
    assert "li.appendChild(link)" in block


def test_a_scrolling_page_and_widget_body_leave_room_for_a_focus_ring():
    # A Tab stop scrolled in flush with the bottom edge lost 3.8 to 4.1px of
    # its ring to the clip (focus-ring sweep): the scroller keeps --ring-room.
    css = _strip(css_text())
    rule = re.search(r"\.tab-page,\s*\.dash-body,\s*\.library-view-section\s*\{([^}]*)\}", css)
    assert rule and "scroll-padding-block: var(--ring-room)" in rule.group(1)


def test_a_plain_activity_row_beside_button_rows_is_not_a_stray_list_item():

    js = with_pieces("dashboard.js")
    at = js.index("Something that is gone (a note deleted for good")
    block = js[at : at + 900]
    assert 'li.setAttribute("role", "presentation")' in block


def _js(name: str) -> str:


    return with_pieces(name)


def test_a_reminders_priority_is_a_word_as_well_as_a_coloured_edge():
    js = _js("shell-reminders.js")
    assert '"High" : "Low"} priority' in js


def test_a_toggle_says_it_is_on_to_a_screen_reader_as_well_as_to_the_eye():
    assert "function setActiveChoice(" in _js("chat-attach.js")
    #: shell-reminders.js's own list and month toggle went with the one calendar (TIMELINE_PLAN decision 19).
    for name in ("wiring.js", "capture-ask.js", "skills.js"):
        assert "setActiveChoice(" in _js(name), name
    # The fill alone, set by hand on these, is the finding.
    assert 'classList.toggle("active", b === button)' not in _js("wiring.js")
    assert '$("select-btn").classList.add("active")' not in _js("skills.js")

    html = (Path(__file__).resolve().parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")
    for fragment in ('id="select-btn" class="ghost small" aria-pressed="false"', 'data-filter="open"'):
        assert fragment in html, fragment
    assert re.search(r'data-view="list" class="active icon-only"[^>]*aria-pressed="true"', html)
    assert re.search(r'aria-pressed="true" data-filter="open"', html)


def test_the_dashboards_hold_or_right_click_mark_menu_names_itself():
    assert 'holder.title = "Right-click or hold to change this mark"' in _js("dashboard.js")


def test_a_worded_menu_draws_its_groups_and_the_document_adder_declares_them():
    # menus.js: "Add this note to a document" was 7 rows with no groups because
    # `labelledMenu` ignored the `group` an item carries (kebabMenu honours it).
    sheets = _js("sheets-selects.js")
    at = sheets.index("function labelledMenu(")
    assert 'rule.className = "menu-sep"' in sheets[at : at + 2600]
    capture = _js("capture-ask.js")
    assert 'group: "Documents"' in capture and 'group: "New"' in capture


# Sweep 2026-10-17 (scratchpad/ui-sweeps/a11ysurfaces.js): the "/" menu in the
# chat box and the note boxes kept the focus in the textarea, but the listbox's
# `aria-activedescendant` sat on the list, which is never focused, so a screen
# reader heard nothing when the menu opened or the highlight moved.
def test_the_slash_menu_is_announced_through_the_box_that_has_the_focus():
    editor = _js("editor.js")
    assert "function editorLinkBox(" in editor
    opener = editor[editor.index("function editorOpenMenu(") :][:900]
    assert "editorLinkBox(textarea, true)" in opener
    closer = _function(editor, "editorCloseMenu")
    assert "editorLinkBox(textarea, false)" in closer
    active = _function(editor, "editorSetActive")
    assert 'editorMenuState.textarea?.el?.setAttribute("aria-activedescendant", row.id)' in active


# WCAG 2.5.8: the Appearance sliders (and every other range input) were
# 144x16, under the 24 px target floor; a range has no box of its own, so the
# floor is the checkbox's `--target-min` rule restated for it.
def test_a_range_input_keeps_the_target_floor():
    forms = (CSS / "01-forms-settings.css").read_text(encoding="utf-8")
    assert re.search(r'^input\[type="range"\] \{\s*min-height: var\(--target-min\);\s*\}', forms, re.M)


# Settings, Appearance at 390: the zoom row (minus, slider, plus, value, Reset)
# is 264 px wide with 44 px buttons, and the slider was squeezed to 24 px, a
# slider nobody can land a finger on (scratchpad/ui-sweeps/a11ysurfaces.js,
# measured 24x44). The row wraps and the slider keeps 8rem.
def test_the_zoom_slider_keeps_a_usable_width_on_a_phone():
    lazy = (CSS / "settings-controls-lazy.css").read_text(encoding="utf-8")
    assert re.search(r"\.setting-control:has\(> #zoom-slider\) \{\s*flex-wrap: wrap;", lazy)
    assert re.search(r"#zoom-slider \{\s*flex: 1 1 8rem;\s*min-width: 8rem;", lazy)


# A scroll asked for as "smooth" is not slowed by the system's reduced-motion
# setting; four did not ask (capture-ask, settings-wiring twice, wiring).
def test_no_scroll_is_smooth_without_asking_for_reduced_motion():
    bad = []
    for path in sorted((FRONTEND / "js").glob("*.js")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if 'behavior: "smooth"' in line:
                bad.append(f"{path.name}:{number}")
    assert not bad, f'use `behavior: reducedMotionWanted() ? "auto" : "smooth"`: {bad}'


# The calendar add sheet's Reminder and Event tabs named no panel: a screen
# reader said "tab 1 of 2" and nothing changed when the form beneath did
# (a11ysurfaces.js, addtabs probe: tabs 2, tabpanels 0, aria-controls null).
def test_the_calendar_add_tabs_control_a_panel_each():
    source = _js("timeline-cal-add.js")
    assert 'tab.setAttribute("aria-controls", `timeline-cal-add-panel-${kind}`)' in source
    assert 'holder.setAttribute("role", "tabpanel")' in source
    assert 'holder.setAttribute("aria-labelledby", tab.id)' in source


# The chat dock's Skills panel (a non-modal dialog): Escape closed it with the
# focus on a select inside it, which fell to the page (a11ysurfaces.js: "focus
# did not return to #chat-skills-btn").
def test_the_skills_panel_hands_the_focus_back_to_its_trigger():
    source = _js("skills.js")
    close = source[source.index("  const close = (refocus) => {") :][:420]
    assert "panel.contains(document.activeElement)" in close and "trigger.focus()" in close
    assert 'if (event.key === "Escape") close(true);' in source
    assert 'run.addEventListener("click", () => close(true));' in source
