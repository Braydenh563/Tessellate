"""The boot and the ways between views stay smooth (INBOX 577, 580).

The owner: "when loading into the app, the companion or atlas's head goes
large then small then large again then settles on the normal size. also
loading up the app is very laggy or visually slow. it is visually not clean
and glitchy even though it may not be", and "opening pages and between ui
views like tabs, pages, popups, features like the graph etc need to be more
smooth in transitions and cheap to hide the ugly loading glitches".

What each cause was, measured by `scratchpad/ui-sweeps/smooth1005-boot.js`
and `smooth1005-tabs.js`, and the rule that keeps it fixed:

- The head: the hello nod's keyframes replaced the head's resting transform
  and dropped its 0.76 scale (0.74 at rest, 0.96 for 0.9s), and every
  entrance squashed or grew the figure as it came in.
- The splash cut instead of fading (`.hidden` is `display: none
  !important`) and was never removed; the shell then built itself in view.
- The status bar was laid out under the header and thrown to the foot.
- Every tab switch started its page at opacity 0: three or four blank frames.
- Every popup opened between two frames.

Like the other frontend lints this cannot see the DOM: the two sweeps are
what run against a browser (GATE=1 on each).
"""

from __future__ import annotations

import re

from tests._app_js import app_js_text
from tests._css_paths import CSS_DIR

ROOT = CSS_DIR.parents[1]
JS = app_js_text()
AVATARS = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
CSS = {p.name: p.read_text(encoding="utf-8") for p in sorted(CSS_DIR.glob("*.css"))}
ALL_CSS = "\n".join(CSS.values())


def _fn(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    return source[start : source.index("\n}\n", start)]


def _keyframes(name: str) -> str:
    start = ALL_CSS.index(f"@keyframes {name} {{")
    depth, i = 0, ALL_CSS.index("{", start)
    while True:
        depth += {"{": 1, "}": -1}.get(ALL_CSS[i], 0)
        i += 1
        if depth == 0:
            return ALL_CSS[start:i]


def test_the_companion_comes_in_at_its_own_size():
    enter = _fn(AVATARS, "nameMarkBuddyEnter")
    assert "nameMarkBuddySquash" not in enter, "an entrance squashes the figure as it arrives"
    assert not re.search(r"scale:\s*\"", enter), "an entrance animates the character's scale"


def test_the_nod_keeps_the_head_at_its_resting_size():
    # A keyframe `transform` on `.atl-head` replaces the resting one (and its
    # 0.76 scale); the nod moves the individual `translate` and `rotate`,
    # which compose with it.
    frames = re.findall(r"\{([^{}]*)\}", _keyframes("atl-nod"))
    assert frames
    for frame in frames:
        assert not re.search(r"(?<![-\w])transform\s*:", frame), frame
        assert "rotate:" in frame and "translate:" in frame, frame


def test_the_companion_waits_for_the_curtain():
    arrive = _fn(AVATARS, "nameMarkBuddyArrive")
    assert arrive.index("nameMarkBuddyCurtained()") < arrive.index("nameMarkBuddySettle(")
    curtained = _fn(AVATARS, "nameMarkBuddyCurtained")
    for what in ('"boot-splash"', '"shell-curtain"', '"lock-overlay"'):
        assert what in curtained


def test_the_splash_fades_and_leaves():
    hide = _fn(JS, "hideBootSplash")
    assert 'classList.add("hidden")' not in hide, "`.hidden` is display: none !important: the fade never runs"
    assert "boot-splash-leaving" in hide and "splash.remove()" in hide and "setTimeout(" in hide
    assert ".boot-splash.boot-splash-leaving {" in CSS["00-tokens-shell.css"]


def test_one_curtain_lifts_over_a_drawn_first_tab():
    start = _fn(JS, "startApp")
    assert "return Promise.all([looksReady, tabReady]);" in start
    curtain = _fn(JS, "curtainShell")
    assert "SHELL_CURTAIN_MAX_MS" in curtain and "hideBootSplash();" in curtain and "liftLockScreen();" in curtain
    # Every way the app starts lifts it: the stored token, sign-in off, a password.
    for name in ("initAuth", "enterWithoutPassword", "submitLockForm"):
        assert "curtainShell(opening);" in _fn(JS, name), name
    assert "#lock-overlay.lock-leaving {" in CSS["08-consistency.css"]


def test_the_status_bar_is_at_the_foot_before_any_page():
    rule = CSS["00-tokens-shell.css"]
    body = rule[rule.index("#status-bar {") : rule.index("}", rule.index("#status-bar {"))]
    assert "margin-top: auto;" in body


def test_the_dashboard_banner_keeps_its_lines_before_its_words():
    assert ":is(.dash-greeting, .dash-submessage, .dash-clock-time, .dash-clock-date):empty::before {" in CSS["01-forms-settings.css"]
    assert ".dash-submessage:empty {\n  display: none;" not in CSS["01-forms-settings.css"]


def test_a_page_never_arrives_from_nothing():
    css = CSS["08-consistency.css"]
    block = css[css.index("/* --- motion: a page arrives") :]
    block = block[: block.index("/* --- ", 10)]
    # INBOX 1462: opacity plus a one-step rise, both compositor-only, on one token.
    assert "transition: opacity var(--ui-base) var(--ease-out), translate var(--ui-base) var(--ease-out);" in block
    start = re.search(
        r"@starting-style\s*\{\s*\.tab-page:not\(\.hidden\)\s*\{\s*opacity:\s*([\d.]+);\s*translate:\s*0 var\(--space-([12])\);", block
    )
    assert start and float(start.group(1)) >= 0.3, "a page fading in from 0 shows the bare window for its first frames"
    assert start.group(2) == "1", "the rise is one step (4px): a page that travels further is confronting"
    assert "will-change" not in block


def test_the_small_popups_and_the_hover_card_arrive_on_the_menu_recipe():
    """INBOX 1462: the selection popup, the spelling menu and the OCR region popover
    join the shared fade and grow (no per-surface rule); the graph's hover card
    fades by opacity alone, since its own `transform` places it."""
    resp = (ROOT / "frontend" / "css" / "10-responsive.css").read_text(encoding="utf-8")
    at = resp.index(".action-menu:not(.hidden),\n.dock-menu[open]")
    head = resp[at : resp.index("{", at)]
    for sel in (".selection-popup", ".doc-suggest-menu", ".ocr-region-popover"):
        assert sel in head, sel
    graph = (ROOT / "frontend" / "css" / "graph-lazy.css").read_text(encoding="utf-8")
    rule = graph[graph.index(".graph-hovercard:not([hidden]) {") :]
    rule = rule[: rule.index("}")]
    assert "animation: ui-fade var(--ui-fast) var(--ease-out);" in rule and "transform" not in rule


def test_every_popup_has_one_way_in():
    css = CSS["08-consistency.css"]
    block = css[css.index("/* --- motion: a popup arrives") :]
    block = block[: block.index("/* --- ", 10)]
    which = ":where(.modal-overlay, .lock-overlay:not(#lock-overlay), #palette-overlay):not(.hidden) {"
    assert block.count(which) == 1, "one rule for every overlay"
    flat = " ".join(block.split())
    assert "@starting-style { opacity: 0; & > * { translate: 0 var(--space-2); scale: 0.985; }" in flat
    assert "var(--ui-base)" in block and "var(--ui-slow)" in block and "var(--ui-exit)" in block


def test_a_heavy_tab_shows_its_shape_while_its_code_loads():
    nav = (ROOT / "frontend" / "js" / "navigation.js").read_text(encoding="utf-8")
    switch = nav[nav.index("async function switchTab(") : nav.index("\n}\n", nav.index("async function switchTab("))]
    assert "tabPlaceholder(lazyPage, true);" in switch
    # Given back on the draw, on a timer, and on a failed load.
    assert switch.count("tabPlaceholder(lazyPage, false)") == 2
    assert "drawing = renderGraph();" in switch and "drawing = loadLibrary();" in switch
    css = CSS["08-consistency.css"]
    assert ".tab-page.tab-loading > :not(.tab-placeholder) {" in css
    assert ".tab-page > .tab-placeholder.tab-placeholder-leaving {" in css


def test_late_parts_do_not_push_the_page():
    library = (ROOT / "frontend" / "js" / "library.js").read_text(encoding="utf-8")
    gallery = _fn(library, "renderLibraryImagesGallery")
    assert gallery.index('if (grid.querySelector(":scope > .skeleton")) empty?.classList.add("hidden");') < gallery.index('"/media"')
    assert 'chat-empty-waiting' in _fn(JS, "renderChatEmptyState") and "chat-empty-waiting" in _fn(JS, "loadChatSuggestions")
    assert ".timeline-days:empty {" in CSS["06-timeline-dialogs.css"]
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert '<p id="ollama-status" class="status is-checking">Checking the models…</p>' in html


def test_the_companion_holds_still_while_a_view_arrives():
    nav = (ROOT / "frontend" / "js" / "navigation.js").read_text(encoding="utf-8")
    switch = nav[nav.index("async function switchTab(") :]
    assert switch.index("window.uiSettlingUntil = performance.now() + 400;") < switch.index("revealTab(name);")
    settings = (ROOT / "frontend" / "js" / "settings.js").read_text(encoding="utf-8")
    assert "window.uiSettlingUntil = performance.now() + 400;" in _fn(settings, "openSettingsModal")
    assert "now < (window.uiSettlingUntil || 0)" in _fn(AVATARS, "nameMarkBuddyTempo")


def test_the_companion_never_sits_on_the_air():
    # INBOX 582: a perch is asked of the page under it, not remembered.
    supported = _fn(AVATARS, "nameMarkBuddySupported")
    assert "document.elementsFromPoint(" in supported and "<= 2" in supported
    assert "el.closest(NMB_CANVAS)" in supported, "what is drawn on a canvas is never a perch"
    check = _fn(AVATARS, "nameMarkBuddyCheck")
    assert check.index("!nameMarkBuddySupported()") < check.index("nameMarkBuddyObstacles(tab)")
    assert "placeNameMarkBuddy(buddy, false, [nmb.x, nmb.y]);" in check
    assert "if (!nameMarkBuddySupported()) return false;" in _fn(AVATARS, "nameMarkBuddyStillGood")
    # Asked again after a pan or zoom on a canvas, a release, and while it rests.
    assert 'document.addEventListener("wheel", nameMarkBuddySupportSoon' in AVATARS
    assert 'document.addEventListener("pointerup", nameMarkBuddySupportSoon' in AVATARS


def test_every_animation_on_atlas_head_keeps_its_scale():
    # The general form of the nod's fix: any keyframes run on `.atl-head`
    # replace its resting transform, so every frame restates the scale.
    names = set(re.findall(r"\.atl-head\s*\{\s*animation:\s*([a-z][\w-]*)", ALL_CSS))
    assert names, "no animation on Atlas's head found: the lint would pass on nothing"
    for name in names:
        for frame in re.findall(r"\{([^{}]*)\}", _keyframes(name)):
            if "transform" in frame:
                assert "var(--atl-head-k)" in frame, f"@keyframes {name} drops the head's scale: {frame.strip()}"


def test_design_names_the_recipe_and_its_lints():
    design = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    row = next(line for line in design.splitlines() if line.startswith("| Motion (a selection that moves"))
    for needle in ("from 0.4", "tabPlaceholder", "curtainShell", "tests/test_smooth_boot.py", "smooth1005-boot.js", "smooth1005-tabs.js"):
        assert needle in row, needle
    assert "nameMarkBuddySupported" in design and "smooth1005-perch.js" in design


def test_the_dashboard_shows_its_widgets_once_they_have_drawn():
    dash = (ROOT / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")
    render = dash[dash.index("async function renderDashboard(") :]
    render = render[: render.index("\n}\n")]
    assert 'grid.classList.add("dash-filling");' in render
    assert "drawing.push(mountWidgetBody(widget, body));" in render
    assert "window.dashSettled = Promise.race([Promise.allSettled(drawing)" in render
    assert 'grid.classList.remove("dash-filling")' in render
    assert "return drawn;" in _fn(dash, "mountWidgetBody")
    assert "#dash-grid.dash-filling {" in CSS["08-consistency.css"]
    assert ".then(() => window.dashSettled).then(lift, lift);" in _fn(JS, "curtainShell")
