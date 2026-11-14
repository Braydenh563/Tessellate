"""The 1103 unslop audit's twelve findings, held at source level.

Each test names the finding (docs/roadmap/agent-remaining/unslop-1103.md) and
the one fact in the stylesheet or markup that, if it drifts back, reproduces
it. The measured numbers live in the commit bodies.
"""

import re
from pathlib import Path

from tests._js_scope import unwrapped
from tests._css_paths import FORMER_10, sheets

ROOT = Path(__file__).resolve().parent.parent
CSS_DIR = ROOT / "frontend" / "css"


def _css(name: str) -> str:
    text = (CSS_DIR / name).read_text(encoding="utf-8")
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _rules(css: str):
    for match in re.finditer(r"(?:(?<=[{}])|\A)([^{}]+)\{([^{}]*)\}", css):
        yield " ".join(match.group(1).split()), match.group(2)


def _body(css: str, selector: str) -> str:
    return "\n".join(b for s, b in _rules(css) if selector in [x.strip() for x in s.split(",")])


def test_1_reminder_time_is_its_own_phone_line():
    """Beside the words the time took 185px of 301 and left 48px for the text."""
    css = "\n".join(_css(n) for n in ("01-forms-settings.css", "03-dashboard-widgets.css", "04-chat-dock-appearance.css", "05-sidebars-themes.css", "06-timeline-dialogs.css", "07-whiteboard-misc.css"))
    grid = _body(css, "#reminder-groups .entry-list li > .entry-meta")
    assert '"tick text"' in grid and '"tick when"' in grid and '"acts acts"' in grid


def test_2_skills_dock_builds_a_menu_to_fold_into():
    """Without a `.dock-more` the dock cannot fold: the title sat under the select.

    The menu is made by `foldDockArrange` when the dock first folds, not shipped
    in the page (the boot element cap, tests/test_boot_diet3.py)."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'data-dock-name="library-skills" data-dock-more="skills-more-menu"' in html
    assert 'id="skills-more-menu"' not in html
    js = (ROOT / "frontend" / "js" / "phone-shell.js").read_text(encoding="utf-8")
    start = js.index("function foldDockArrange(")
    assert "doc-dock-menu dock-menu dock-more" in js[start : js.index("\n}\n", start)]
    assert "ensureDockMore" not in js, "a named helper is one more global (test_global_scope_ratchet)"
    assert ".dock-more:has(> .dock-menu-list:empty)" in "\n".join(_css(n) for n in ("01-forms-settings.css", "03-dashboard-widgets.css", "04-chat-dock-appearance.css", "05-sidebars-themes.css", "06-timeline-dialogs.css", "07-whiteboard-misc.css"))


def test_3_dashboard_spans_are_pixel_rows_with_the_card_gap_in_the_span():
    """An 8px unit and a 16px row gap rounded every card up in 24px steps."""
    grid = _body(_css("01-forms-settings.css"), "#dash-grid")
    assert "grid-auto-rows: 1px" in grid and "gap: 0 var(--space-6)" in grid
    js = (ROOT / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")
    start = js.index("function sizeDashWidgetSpan(")
    body = js[start : js.index("\n}\n", start)]
    assert "cardGap" in body and "rowGap" in body


def test_4_dashboard_find_label_drops_its_scope_on_a_phone():
    """93px of text room cut "Search your notes, ..." to "Search your..."."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert '<span class="dash-find-scope"> your notes, documents, files and the app</span>' in html
    assert "display: none" in _body(re.sub(r"/\*.*?\*/", "", sheets(*FORMER_10), flags=re.S), ".dash-find-scope")


def test_5_map_toolbar_selects_take_the_quiet_inset_not_radius_inner():
    """`--radius-inner` is 0 at the default corner: square, ink-edged selects."""
    body = _body(_css("07-whiteboard-misc.css"), ".wb-rail .select-shell > .select-opener")
    assert "radius-inner" not in body
    assert "border-radius: var(--radius-md)" in body and "var(--field-inset)" in body
    assert "border: 1px solid transparent" in body


def test_6_dock_search_is_the_docks_control_height():
    """The search was 32 (`--control-h-lg`) in a bar of 28s; DESIGN says 28."""
    body = _body("\n".join(_css(n) for n in ("01-forms-settings.css", "03-dashboard-widgets.css", "04-chat-dock-appearance.css", "05-sidebars-themes.css", "06-timeline-dialogs.css", "07-whiteboard-misc.css")), ".dock .dock-search")
    assert "height: max(var(--control-h), var(--target-min))" in body
    design = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    assert "(32px, 44 under touch; refresh" not in design


def test_7_chat_sidebar_search_is_the_quiet_inset():
    """It was the one search field drawn as a form field (ink edge, white fill)."""
    body = _body(_css("02-chat-graph.css"), ".search-field.chat-sidebar-search")
    assert "border-color: transparent" in body and "background: var(--field-inset)" in body
    inner = _body(_css("02-chat-graph.css"), ".search-field.chat-sidebar-search > .search-field-input")
    assert "font-size: var(--text-md)" in inner


def test_8_library_sections_grow_into_their_ring_room():
    """Padding with a negative margin nets zero only if the box widens."""
    css = _css("07-whiteboard-misc.css")
    body = _body(css, ".tab-page > .library-view-section")
    assert "width: calc(100% + 2 * var(--ring-room))" in body
    assert "max-width: calc(var(--content-max) + 2 * var(--ring-room))" in body


def test_9_settings_peek_is_beside_the_title_not_among_the_utilities():
    """Peek shown only on Appearance moved the utilities 91px between sections."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    head = html[html.index('<h2 class="dialog-head-title"><i class="ph ph-gear'):]
    head = head[: head.index('id="settings-close"')]
    assert head.index('id="settings-peek"') < head.index('id="settings-profile-btn"')
    assert "margin-inline-end: auto" in _body("\n".join(_css(n) for n in ("01-forms-settings.css", "03-dashboard-widgets.css", "04-chat-dock-appearance.css", "05-sidebars-themes.css", "06-timeline-dialogs.css", "07-whiteboard-misc.css")), ".dialog-head > #settings-peek")


def test_10_settings_rail_head_wraps_instead_of_clipping_its_toggle():
    css = _css("06-timeline-dialogs.css")
    assert "flex-wrap: wrap" in _body(css, ".settings-nav-groups-head")
    assert "white-space: nowrap" in _body(css, ".settings-nav-groups-head > *")
    link = _body(css, ".settings-nav-groups-head .linklike")
    assert "overflow: visible" in link and "text-overflow: clip" in link


def test_11_dashboard_has_one_filled_button_and_no_tinted_edge_at_rest():
    tinted = _body(_css("03-dashboard-widgets.css"), ".quick-link-tinted")
    assert "border-color" not in tinted
    js = (ROOT / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")
    assert js.count("Generate this week's digest") == 2
    assert 'smallButton("ph:sparkle Generate this week\'s digest", "", runGeneration)' in js
    assert 'runGeneration, false' not in js


def test_12_reminder_when_row_takes_the_fields_height_and_corner():
    css = "\n".join(_css(n) for n in ("01-forms-settings.css", "03-dashboard-widgets.css", "04-chat-dock-appearance.css", "05-sidebars-themes.css", "06-timeline-dialogs.css", "07-whiteboard-misc.css"))
    assert "--button-min-h: var(--control-h-body)" in _body(css, "#reminder-due-row")
    for selector in ("#reminder-due-row > details > summary", "#reminder-due-row .stepper"):
        assert "border-radius: var(--radius-md)" in _body(css, selector)
        assert "radius-pill" not in _body(css, selector)
    assert "border-radius: var(--radius-in-md)" in _body(css, "#reminder-due-row .stepper-btn")


def _js(name: str) -> str:
    return unwrapped((ROOT / "frontend" / "js" / name).read_text(encoding="utf-8"))


def test_13_reminder_facts_are_one_line_of_equal_chips():
    """Three stacked rows (107px) for a priority, a repeat and a note; the chips 21 and 24."""
    js = _js("shell-reminders.js")
    start = js.index('row.className = "entry-meta"')
    body = js[start : js.index("async function openCalendarPage(", start)]
    assert body.count('className = "entry-links"') == 1, "the repeat, alert and note chips share one line"
    assert 'chip(`ph:flag ${reminder.priority === "high"' not in body, "the edge already says high"
    assert '"High priority. "' in body, "the words stay for a screen reader"
    assert "min-height: 1.5rem" in _body(_css("01-forms-settings.css"), "#reminder-groups .entry-links > .chip")


def test_boot_win_the_m_guide_panel_is_a_lazy_sheet():
    """The integration branch was 95 bytes over the boot CSS cap; the guide draws only after a first m."""
    lazy = _css("chord-guide-lazy.css")
    assert ".chord-guide-panel .chord-guide-row" in lazy and ".chord-guide {" in lazy
    for boot in ("00-tokens-shell.css", "01-forms-settings.css", "02-chat-graph.css", "03-dashboard-widgets.css",
                 "04-chat-dock-appearance.css", "05-sidebars-themes.css", "06-timeline-dialogs.css", "10-responsive.css"):
        assert "chord-guide-panel" not in _css(boot) or boot == "07-whiteboard-misc.css"
    assert 'lazyScript("/css/chord-guide-lazy.css")' in _js("chord-guide.js")


def test_14_the_two_composers_have_no_drag_grip():
    """The native grip was drawn over the chat box's corner and the Dashboard's."""
    chat = _body(_css("04-chat-dock-appearance.css"), ".chat-dock .chat-composer #chat-input")
    assert "resize" not in chat, "textarea.autogrow already says resize: none"
    assert "resize: none" in _body(_css("05-sidebars-themes.css"), "textarea.autogrow")
    # INBOX 1592: the Dashboard's Quick capture is the capture card's bar now, so the grip rule is the card body's.
    js = _js("dashboard.js")
    start = js.index("async function renderQuickCaptureWidget(")
    assert "textarea" not in js[start : js.index("\n}\n", start)]
    assert "resize: none" in _body(_css("capture-card-lazy.css"), ".capture-card-body")


def test_15_a_dock_title_is_a_count_not_the_tab_name_again():
    """The sub-tab says Documents; the dock under it said Documents too (50px, 16px / 600, twice)."""
    assert "nounCount.dock = function (" in _js("library.js"), "a property, not one more global; not in the boot scripts (test_static_compression)"
    calls = {
        "library.js": ('nounCount.dock("library-docs"', 'nounCount.dock("library-media"', 'nounCount.dock("library-links"', 'nounCount.dock("library-skills"', 'nounCount.dock("library",'),
        "boards-gallery.js": ('nounCount.dock("library-boards"',),
        "meetings.js": ('nounCount.dock?.("library-recordings"',),
    }
    for name, needles in calls.items():
        for needle in needles:
            assert needle in _js(name), f"{name} no longer writes {needle}"
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    # The Timeline and the Graph have a count chip beside the title already: the title stays for a screen reader only.
    assert '<h2 class="visually-hidden">Timeline</h2>' in html and '<h2 class="visually-hidden">Graph</h2>' in html


def test_boot_win_the_inline_action_form_lives_with_its_one_caller():
    """The boot scripts' gzip total was 37 bytes under its cap; the form draws only from a lazy note card."""
    assert "function renderInlineAction(" not in _js("lightbox.js")
    assert "function renderInlineAction(" in _js("entry-card.js")


def test_16_first_steps_names_what_it_opens_not_a_generic_get_started():
    """The dock button said "Get started" and its card said "Get started, 0 of 3 done"."""
    first = _js("first-run.js")
    assert 'word.textContent = "First steps"' in first
    assert 'title.textContent = "Three steps to a working notebook"' in first
    assert '"Get started"' not in first, "no visible word left over from the old name"
    assert "Show first steps" in _js("dashboard.js") and "Show first steps" in _js("app-features.js")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "Show first steps</button>" in html and "Show Get started" not in html
    from tessellate.ai.help_topics_more import MORE_TOPICS

    topic = next(t for t in MORE_TOPICS if t["id"] == "first-steps")
    assert "Hide first steps" in topic["body"] and "Hide Get started" not in topic["body"]
    # The longer title takes two lines beside the buttons on a phone; the count joins the bar below it.
    phone = _css("first-run-lazy.css")
    phone = phone[phone.index("max-width: 599.98px") :]
    assert "grid-area: title" in phone and "grid-area: count" in phone and "grid-area: bar" in phone




def test_17_the_empty_chat_sidebar_is_the_empty_state_recipe():
    """A bare 13.6px grey line in a 40px strip, where every other empty list has icon, title, sentence, action."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert '<div id="conv-empty" class="empty-state hidden"></div>' in html, "one element in the page: the rest is drawn on demand"
    js = _js("sheets-selects.js")
    start = js.index("async function loadConversationList(")
    body = js[start : js.index("\n}\n", start)]
    for part in ('icon.className = "empty-icon"', 'setLabel(icon, "ph:chats")', 'title.className = "empty-title"', 'start.dataset.emptyAction = "new-chat"', '"ph:plus New chat"'):
        assert part in body, part
    assert 'action === "new-chat"' in _js("navigation.js")


def test_18_an_empty_state_does_not_repeat_the_dock_button_above_it():
    """Library Create, Images Upload, Boards New, Bookmarks Add and Reminders Add each showed twice."""
    lib = _js("library.js")
    assert 'dockCreate?.classList.toggle("hidden", offerCreate && Boolean(dockCreate))' in lib
    assert '$("library-images-upload")?.classList.toggle("hidden", !ofKind.length)' in lib
    assert '$("bookmark-add")?.classList.toggle("hidden", !bookmarksCache.length)' in lib
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    reminders = html[html.index('<div id="reminders-empty"') :].split("</div>", 1)[0]
    assert "<button" not in reminders and "Add one above" in reminders
    boards = html[html.index('<div id="library-boards-empty"') :].split("</div>", 1)[0]
    assert 'data-empty-action="new-board"' not in boards and 'id="library-boards-new-map"' in boards


def test_19_an_empty_graph_paints_no_legend_and_no_zoom_but_a_filtered_one_keeps_both():
    """201x29 "Bigger dot, more links" and a 42x150 zoom strip over "Nothing to map yet"."""
    js = _js("graph-canvas.js")
    start = js.index("function gcShowEmpty(")
    body = js[start : js.index("\n}\n", start)]
    assert 'classList.toggle("graph-bare", Boolean(show && !filtered))' in body
    css = _css("graph-lazy.css")
    assert "display: none" in _body(css, ".graph-bare .graph-legend-row") and "display: none" in _body(css, ".graph-bare .graph-zoom")


def test_20_an_empty_notebooks_dashboard_keeps_the_one_widget_that_needs_no_notes():
    """349px of nothing between the steps and the status bar; Quick capture needs no data."""
    js = _js("dashboard.js")
    start = js.index("async function renderDashboard(")
    body = js[start : js.index("\n}\n", start)]
    assert "const bare = entriesEverLoaded && !allEntries.length && !dashEditMode;" in body
    assert 'if (bare && name !== "capture") continue;' in body
    assert "window.dashSettled = Promise.resolve();" not in body, "the early return that left the grid empty is gone"


def test_23_the_timeline_date_drops_this_years_year_and_the_column_follows():
    """390: 11 of 94 titles ended in an ellipsis, with 128px of Date column spent on "Dec 14, 2026"."""
    js = _js("timeline.js")
    assert "TIMELINE_ROW_FULL_DATE.thisYear = new Intl.DateTimeFormat(undefined, { day: \"numeric\", month: \"short\" })" in js
    start = js.index("function timelineTableRow(")
    body = js[start : js.index("\n}\n", start)]
    assert "TIMELINE_ROW_FULL_DATE.thisYear : TIMELINE_ROW_FULL_DATE).format(row.when)" in body
    assert "TIMELINE_ROW_FULL_DATE.format(row.when)}. Written" in body, "the hover keeps the whole date"
    assert 'classList.toggle("timeline-this-year"' in js
    css = _css("06-timeline-dialogs.css")
    assert "width: 5rem" in _body(css, ".timeline-table.timeline-this-year th:nth-child(2)")
    assert "width: 6.5rem" in _body(css, ".timeline-table th:nth-child(2)")


def test_25_failure_copy_has_one_contraction_and_names_its_object():
    """"Could not" 30 times beside "Couldn't" 226; seven toasts said "that" and one said "Failed to"."""
    said = []
    for path in sorted((ROOT / "frontend" / "js").glob("*.js")):
        for number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
            if re.search(r"[\"`]Could not |Failed to remove|Couldn't (?:undo|save) that(?:\.|\s*\"|\s*`|,)", line) and not line.lstrip().startswith("//"):
                said.append(f"{path.name}:{number}: {line.strip()[:110]}")
    assert not said, said
    css = _css("02-chat-graph.css")
    assert "font-size: 2.6rem" in _body(css, ".ph.empty-icon"), "an `i.ph.empty-icon` lost to `.ph` and drew at 16.9px"


def test_22_a_task_box_on_a_note_card_hands_the_tap_to_the_card():
    """18x18 and no click event at all (a disabled box swallows it); switches and the star chip are not targets."""
    css = _css("01-forms-settings.css")
    body = _body(css, '#entry-list .entry-content .entry-task > input[type="checkbox"]:disabled')
    assert "pointer-events: none" in body
    js = _js("notes-list.js")
    assert 'item.title = "Open the note to tick this off";' in js and "box.title" not in js


def test_21_the_micro_gaps_sit_on_the_scale_not_between_its_steps():
    """602 off-scale readings (gap 0.8, 1.6, 2.4px; padding-block 2.4px) across six tabs and two panes, 118 left."""
    expect = {
        "01-forms-settings.css": {".modal-nav": "gap: var(--space-1)", ".modal-nav>div": "gap: var(--space-1)",
                                  ".entry-actions button": "padding: var(--space-1) var(--space-3)"},
        "03-dashboard-widgets.css": {".seg": "gap: var(--space-1)", ".segmented-control": "gap: var(--space-1)"},
        "04-chat-dock-appearance.css": {".setting-label": "gap: var(--space-1)", ".setting-check>span": "gap: var(--space-1)",
                                        ".category-actions": "gap: var(--space-1)"},
        "05-sidebars-themes.css": {".conv-title": "gap: var(--space-1)"},
        "07-whiteboard-misc.css": {".dash-list-text": "gap: 0"},
    }
    for name, rules in expect.items():
        css = _css(name)
        for selector, declaration in rules.items():
            assert declaration in _body(css, selector), f"{name}: {selector} should have {declaration}"
