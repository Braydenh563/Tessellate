"""INBOX 726: four small UI bugs, pinned as text (the DOM is measured in
Chromium by the sweeps; this keeps the fixes from being edited away).

1. The graph's settings panel: the sections' side padding is one value on
   both sides, so the right gap (control to the scrollport's edge) equals the
   left gap (label to the panel's edge) with or without the scrollbar.
2. The companion hides while any full-screen surface is up, keyed on one flag
   on the root element and the companion's own container.
3. The Library's Boards / Maps filter row has its gap below it.
4. Settings: no rule above the autonomous pass's second switch.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import frontend_text
from tests import _js_scope

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "frontend" / "css"
JS = ROOT / "frontend" / "js"


def _css(name: str) -> str:
    return (CSS / name).read_text(encoding="utf-8")


def _rule(text: str, selector: str) -> str:
    """The body of the first rule whose selector list is exactly `selector`."""
    match = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", text)
    assert match, f"no rule for {selector}"
    return match.group(1)


def test_graph_options_sections_pad_both_sides_equally():
    body = _rule(_css("03-dashboard-widgets.css"), ".graph-options .dock-menu-section")
    pads = re.search(r"padding:\s*var\(--space-1\)\s+var\(--space-(\d)\)\s*;", body)
    assert pads, "the section's padding must be one block value and one shared side value"
    assert "scrollbar-gutter" not in _css("02-chat-graph.css").split(".graph-overlay .graph-options {")[-1][:900], (
        "`scrollbar-gutter: stable both-edges` clipped the selects' right borders (INBOX 726)"
    )


def test_boards_filter_gap_is_set_after_the_ring_room_rule():
    text = "\n".join(_css(n) for n in ("02-chat-graph.css", "05-sidebars-themes.css", "06-timeline-dialogs.css", "07-whiteboard-misc.css", "characters-lazy.css"))
    ring = text.index(":is(.launch-row, .library-filters, #chat-suggest) {")
    gap = text.index(":is(#library-boards-filter, #reminder-filter) {")
    assert gap > ring, "the gap must come after the `:is()` whose #chat-suggest id outranks a lone id"
    body = _rule(text, ":is(#library-boards-filter, #reminder-filter)")
    assert "margin-bottom: calc(var(--space-6) - var(--ring-room))" in body
    # The earlier lone-id rules never applied; they must not come back.
    assert not re.search(r"(?m)^#library-boards-filter\s*\{", _css("00-tokens-shell.css"))
    assert not re.search(r"(?m)^#reminder-filter\s*\{", _css("07-whiteboard-misc.css"))


def test_autonomous_pass_jobs_have_no_rule_above_the_second_switch():
    text = _css("library-lazy.css")
    # The later of its two rules is the one that wins (UI plan 13b, L459, moved the first here too).
    body = re.findall(r"(?m)^\.skills-worker-toggles\s*\{([^}]*)\}", text)[-1]
    assert "flex-direction: column" in body and "flex-wrap" not in body
    rule = _rule(text, ".skills-worker-toggles > .setting-check")
    assert "border-top-color: transparent" in rule


# --- 2. The companion hides while anything fills the window -------------------

#: The surfaces the flag knows, by name: each is a full-screen class (or a
#: modal that covers the window) watched in wiring.js. Adding one is a new
#: entry here and a new `watchFullscreenSurface(...)` there.
FULLSCREEN_SURFACES = {
    "graph": "graph-fullscreen",
    "whiteboard": "wb-fullscreen",
    "documents": "doc-focus",
    "ocr": "ocr-workspace",
}


def _js(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def test_companion_container_fades_on_the_root_flag():
    text = "\n".join(_css(n) for n in ("02-chat-graph.css", "05-sidebars-themes.css", "06-timeline-dialogs.css", "07-whiteboard-misc.css", "characters-lazy.css"))
    body = _rule(text, ":root[data-fullscreen] #nm-buddy-band")
    assert "opacity: 0" in body and "visibility: hidden" in body
    assert "pointer-events: none" in body
    # Its own fade, on the container, for whichever avatar it draws.
    assert "transition: opacity" in _rule(text, "#nm-buddy-band")
    # Keyed on the container and the flag, never on one avatar's classes.
    assert not re.search(r":root\[data-fullscreen[^\]]*\][^{]*(nm-atlas|atl-figure|nm-figure|\.name-mark)", text)


def test_every_full_screen_surface_is_watched():
    wiring = _js("wiring.js")
    for name, marker in FULLSCREEN_SURFACES.items():
        assert re.search(r'watchFullscreenSurface\("' + name + r'",[^\n]*' + re.escape(marker), wiring), name
    assert 'setFullscreenSurface("lightbox", true)' in _js("lightbox-view.js")
    assert 'setFullscreenSurface("lightbox", false)' in _js("lightbox-view.js")


def test_a_new_full_screen_class_must_be_watched():
    """Any `classList.toggle/add("...fullscreen...")` or the document focus
    class, anywhere in the scripts, is a surface that fills the window; the
    companion hides for it only if wiring.js watches that class."""
    wiring = _js("wiring.js")
    seen: dict[str, str] = {}
    pattern = r'classList\.(?:toggle|add)\(\s*"([\w-]*(?:fullscreen|doc-focus)[\w-]*)"'
    for path in sorted(JS.glob("*.js")):
        for match in re.finditer(pattern, path.read_text(encoding="utf-8")):
            seen.setdefault(match.group(1), path.name)
    # `graph-fullscreen-on` is the body class that hides the app chrome beside
    # the card's own `graph-fullscreen`, which is the one watched.
    seen.pop("graph-fullscreen-on", None)
    # Sub-modes of a watched surface (tools and sidebar inside focus mode).
    for sub in ("doc-focus-tools", "doc-focus-sidebar", "doc-focus-idle"):
        seen.pop(sub, None)
    unwatched = {cls: file for cls, file in seen.items() if f'"{cls}"' not in wiring}
    assert not unwatched, f"full-screen classes with no watchFullscreenSurface in wiring.js: {unwatched}"


def test_the_browsers_own_full_screen_is_only_asked_for_by_a_watched_surface():
    callers = [p.name for p in JS.glob("*.js") if "requestFullscreen(" in p.read_text(encoding="utf-8")]
    assert callers == ["documents.js"], f"a new requestFullscreen caller needs its own flag: {callers}"


def test_every_viewer_overlay_that_covers_the_window_sets_the_flag():
    # The lightbox is built and removed, so it says so itself rather than being watched.
    for path in JS.glob("*.js"):
        text = path.read_text(encoding="utf-8")
        if 'overlay.className = "lightbox"' in text:
            assert "setFullscreenSurface(" in text, path.name


# Owner findings: link-row hover underline and the snippets bar (INBOX 803).


def test_a_link_row_underlines_its_words_not_its_icon():
    # A button is inline-flex and a decoration on a flex container reaches the
    # icon, so the hover underline lives on the words' own span.
    questions = _css("questions-lazy.css")
    assert ".question-group-link:hover .ph-text" in questions
    hover = questions[questions.index(".question-group-link:hover,"):].split("}", 1)[0]
    assert "text-decoration" not in hover
    consistency = "\n".join(_css(n) for n in ("02-chat-graph.css", "05-sidebars-themes.css", "06-timeline-dialogs.css", "07-whiteboard-misc.css", "characters-lazy.css", "library-lazy.css"))
    assert ".library-read-open:hover .ph-text" in consistency
    #: The hover rule shares its block with the focus twin (the uisweep pass), so it ends in a comma.
    plain = consistency[consistency.index(".library-read-open:hover,"):].split("}", 1)[0]
    assert "text-decoration" not in plain
    # An always-underlined link that holds an icon is not a flex row.
    chat = _css("04-chat-dock-appearance.css")
    assert ":is(.linklike, .link-button):has(> .ph) {\n  display: inline-block;" in chat


def test_the_snippets_bar_is_one_height_and_its_label_one_line():
    # INBOX 803: field 32px, button 42.8px with "Save selection" on two lines.
    css = _css("library-lazy.css")
    block = css[css.index(".doc-code-side-bar > button {"):].split("}", 1)[0]
    assert "height: var(--control-h-lg)" in block and "white-space: nowrap" in block
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    # A short label, with the full action in the tooltip and the accessible name.
    start = html.index('<button id="doc-snippet-save"')
    button = html[start:html.index("</button>", start)]
    assert button.endswith("</i>Save")
    assert 'title="Save the selected code as a snippet"' in button
    assert 'aria-label="Save the selected code as a snippet"' in button
    # Every help surface that named the old label now names the button.
    assert "press Save to keep it" in html
    assert "press Save selection" not in _js_scope.unwrapped((ROOT / "frontend" / "js" / "documents-codekit.js").read_text(encoding="utf-8"))


# Small one-line fixes from the settings and UI system rows (OPEN ledger 1387 to 1490).

def _fn(text: str, name: str) -> str:
    start = text.index(f"function {name}(")
    return text[start : text.index("\n}\n", start)]


def test_1400_a_worded_small_button_is_named_by_its_words():
    body = _fn(frontend_text("app.js"), "smallButton")
    assert 'if (title && button.classList.contains("icon-only")) button.setAttribute("aria-label", title);' in body
    assert 'if (title) button.setAttribute("aria-label", title);' not in body


def test_1401_most_used_follows_a_write():
    body = _fn(frontend_text("notes-list.js"), "refreshEntries")
    assert 'if (typeof loadMostUsed === "function") loadMostUsed().catch(() => {});' in body


def test_1461_an_empty_notebook_is_offered_its_notes_from_elsewhere():
    body = _fn(frontend_text("onboarding.js"), "renderOnboardingActions")
    assert '"ph:file-arrow-up Bring in your notes"' in body
    assert 'closeOnboarding(false);\n        openSettingsModal("data", "import-md");' in body
