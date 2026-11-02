"""INBOX 598, 602 and 596's skeleton part: a surface on its way shows its own
shape, says what it is opening when it is slow, and the dashboard never
draws an empty frame on a return.

The lint DESIGN.md's recipe row names ("every lazy surface has a skeleton"):
a tab added to `TAB_MODULES` without an outline in `TAB_SKELETONS` fails
here, before anyone sees a blank page with a line across it. The frame
counts are `scratchpad/ui-sweeps/loading598.js`'s, at 4x CPU."""

from __future__ import annotations

import re
from tests._app_js import with_pieces
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


def _read(name: str) -> str:
    return with_pieces(name)


def _block(text: str, start: str) -> str:
    return text.split(start, 1)[1].split("\n}\n", 1)[0]


def test_every_lazy_surface_has_a_skeleton_and_a_name():
    modules = re.search(r"const TAB_MODULES = \{([^}]*)\}", _read("app.js")).group(1)
    tabs = re.findall(r"(\w+):", modules)
    assert tabs, "TAB_MODULES was not found in app.js"
    nav = _read("navigation.js")
    skeletons = nav.split("const TAB_SKELETONS = {", 1)[1].split("\n};\n", 1)[0]
    for tab in tabs:
        entry = re.search(rf"^  {tab}: \{{ name: \"([^\"]+)\", rows: \"[^\"]+\", build:", skeletons, re.M)
        assert entry, f"the lazy tab {tab!r} has no page-shaped outline in TAB_SKELETONS"


def test_a_slow_surface_names_itself_with_the_ring_by_400ms():
    nav = _read("navigation.js")
    late = int(re.search(r"const TAB_SKELETON_NAME_MS = (\d+);", nav).group(1))
    assert late <= 400
    body = _block(nav, "function tabPlaceholder(page, on) {")
    assert 'setLabel(status, `ph:spin Opening ${spec.name}…`)' in body
    assert 'setAttribute("role", "status")' in body


def test_the_placeholder_is_stretched_over_the_page_not_centred():
    # The "horizontal line in the middle": an absolutely placed child of the
    # centring flex page shrank to its content and sat in the middle.
    body = _block(_read("navigation.js"), "function tabPlaceholder(page, on) {")
    assert 'ph.style.alignSelf = "stretch"' in body
    assert 'ph.style.width = "auto"' in body


def test_dashboard_widgets_load_as_skeleton_rows_not_a_word():
    css = "".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "frontend" / "css").glob("*.css")))
    assert not re.search(r"\.dash-body:empty::after\s*\{[^}]*Loading", css)
    mount = _block(_read("dashboard.js"), "function mountWidgetBody(widget, body) {")
    assert "showSkeletons(body" in mount and "clearSkeletons(body)" in mount
    render = _read("dashboard.js").split("async function renderDashboard(", 1)[1].split("\n}\n", 1)[0]
    assert "dashFillingSkeleton(grid" in render


def test_a_return_to_the_dashboard_refreshes_in_place():
    nav = _read("navigation.js")
    assert 'renderDashboard({ refresh: true })' in nav
    dash = _read("dashboard.js")
    render = dash.split("async function renderDashboard(", 1)[1].split("\n}\n", 1)[0]
    assert "refreshDashWidgets(grid)" in render
    refresh = _block(dash, "function refreshDashWidgets(grid) {")
    # Drawn beside the old body, unseen, and swapped in only once it is done.
    assert 'visibility: "hidden"' in refresh and "old.replaceWith(next)" in refresh


#: Settings panes whose lists fill from a request (INBOX 596, "some skeleton
#: loaders are missing"): the render holds `.skeleton` rows until the answer
#: lands. `scratchpad/ui-sweeps/settings-skeletons.js` holds the API 800ms and
#: counts the lists left empty (8 panes before, none after).
SETTINGS_LISTS = (
    ("settings-packages.js", "async function renderExtras(", "extras-list"),
    ("skills.js", "async function renderSkillSettings(", "skill-list"),
    #: Moved to the lazy Settings bundle with an entry point (boot JS cap, 2026-10-31).
    ("settings-controls.js", "async function renderToolSettings(", "tool-list"),
    ("sheets-selects.js", "async function renderPersonas(", "persona-list"),
    ("settings-data.js", "async function renderBackups(", "backup-list"),
    ("settings-data.js", "async function renderPrivacyReceipt(", "privacy-switches"),
    ("settings-controls.js", "async function renderAccount(", "account-facts"),
)


def test_a_settings_list_that_fetches_shows_skeleton_rows_while_it_waits():
    for name, start, list_id in SETTINGS_LISTS:
        body = _block(_read(name), start)
        assert "showSkeletons(" in body, f"{start} draws {list_id} blank until its request answers"
        assert "clearSkeletons(" in body, f"{start} never takes its skeletons out on a failed request"
        shown = body.index("showSkeletons(")
        assert shown < body.index("await "), f"{start} shows its skeletons after the wait, not before it"
        assert "li" in body[shown : shown + 120] or "switchRows" in body[shown : shown + 120], start


def test_the_model_lists_wait_with_skeletons_only_while_the_status_is_unanswered():
    status = _read("status.js")
    assert 'showSkeletons($("models-skeleton"), 2);' in status
    assert 'list.removeAttribute("aria-busy");' in _read("settings-controls.js")  # the rows moved there, lazy
