"""What a scroll in Settings, Help costs, pinned where the browser cannot be.

The owner: Settings, Help is laggy to scroll. Traced headless at 1440x900,
40 wheel steps of 100px on Help (scratch sweep, untracked): about 5.5-7ms of
script per step. A first trace blamed the Dashboard's constellation (a p5
sketch) drawing behind a first-run question that had caught the wheel, so that
trace scrolled nothing. With the question answered first, the 40 steps
scroll 4000px and the cost is the scroll's own listeners: the "On this
page" marker 65-83ms a run (settings-find.js), the back/forward history's
listener 12-28ms (navigation.js), `closeActionMenusOnScroll` 19-26ms
(menus.js).

Two facts set what is worth changing in those listeners:

- A scroll event is already dispatched at most once per frame per scroller
  (the HTML "run the scroll steps" happen in the rendering update), so a
  rAF wrapper around a scroll handler only moves its work, it does not
  thin it.
- A scroll event is not cancelable, so `passive` changes nothing for it.

What does cost is a handler that walks computed styles on every event:
`settingsScroller` (settings.js) asked `getComputedStyle` of every ancestor
of the pane, once per scroll event from the back/forward history
(navigation.js) and once per frame from the "On this page" marker
(settings-find.js). A computed-style read straight after the scroll's own
`data-scrolling` invalidation is a forced style recalculation: traced at
5.9ms in navigation.js and 4.1ms in settings-find.js in one run.
"""

import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _body(name: str, head: str) -> str:
    src = (JS / name).read_text(encoding="utf-8")
    start = src.index(head)
    end = src.index("\n}\n", start)
    return src[start:end]


def test_the_settings_scroller_is_found_once_per_pane_and_width():
    body = _body("settings.js", "function settingsScroller(name) {")
    # A remembered answer, checked cheaply (still an ancestor, same width),
    # before any computed-style walk.
    hit = body.index("_scroller")
    walk = body.index("getComputedStyle")
    assert hit < walk
    assert "innerWidth" in body
    assert re.search(r"_scroller\??\.contains\(box\)", body)


def test_the_sidebar_scroller_the_marker_follows_is_found_once():
    body = _body("settings-find.js", "function settingsNavFollow(link) {")
    assert "settingsNavFollow.box?.contains(link)" in body
    assert body.index("settingsNavFollow.box?.contains(link)") < body.index("nearestScrollParent(link)")


def test_the_marker_finds_the_jump_list_by_id_each_frame():
    body = _body("settings-find.js", "function settingsIndexMark(name) {")
    assert 'document.getElementById("settings-jump")' in body
    assert 'querySelector(".settings-jump")' not in body


def test_the_marker_follows_the_sidebar_before_it_moves_the_mark():
    """Measure, then write: `settingsNavFollow` reads two rects, and after
    the `aria-current` write those reads were a forced second style and
    layout pass in the frame."""
    body = _body("settings-find.js", "function settingsIndexMark(name) {")
    assert body.index("settingsNavFollow(link)") < body.index('link.setAttribute("aria-current", "location")')
    # The heads are in page order: the look stops at the first one below.
    assert "break;" in body


def test_open_toolbar_menus_are_kept_by_their_toggle_not_looked_for():
    """`replaceOpenToolbarMenus` walked a live collection of every toolbar
    menu on each scroll event of any element; on Notes the list changes
    every frame (cards filling as they come into view), so the collection
    was rebuilt each time: 47ms self of a 40-step scroll (CPU profile)."""
    src = (JS / "sheets-selects.js").read_text(encoding="utf-8")
    body = _body("sheets-selects.js", "function replaceOpenToolbarMenus() {")
    assert "OPEN_TOOLBAR_MENUS" in body
    assert "TOOLBAR_MENUS = document.getElementsByClassName" not in src
    assert "OPEN_TOOLBAR_MENUS.add(details)" in src
    assert "OPEN_TOOLBAR_MENUS.delete(details)" in src


def test_the_feature_model_rows_are_rebuilt_only_when_they_change():
    """While Settings is open the status poll answers every three seconds,
    and every answer rebuilt each feature-model row and its enhanced select
    (recorded during a 40-step scroll of Help: 20 row replacements and 34
    menu rebuilds), changing the page under whatever was being scrolled.
    The drawing also left the boot scripts for the lazy Settings file
    (eager gzip total 320,584 to 320,045)."""
    rows = _body("settings-controls.js", "function renderFeatureModelRows(status) {")
    assert "list.dataset.sig === sig" in rows
    assert rows.index("list.dataset.sig === sig") < rows.index("list.replaceChildren()")
    eager = _body("ai-tools.js", "function renderFeatureModels(status) {")
    assert "replaceChildren" not in eager
    assert "renderFeatureModelRows(status)" in eager
    # A refused change redraws, so its select does not keep the choice.
    apply = _body("ai-tools.js", "async function applyFeatureModel(key, name) {")
    assert 'dataset.sig = ""' in apply


def test_the_constellation_rests_while_idle_and_resumes_where_it_stopped():
    """Idle work, not scroll work, found in the same pass (step 3): traced
    with nobody at the window, the Dashboard's constellation ran 600 p5
    frames and 204ms of script every ten seconds, forever. It now rests
    after the background art's two idle minutes and goes on at the next
    input (measured: 60 frames in 2 s, 0 while resting, 60 after a pointer
    move), with its drift clock moved on by the rest so nothing jumps."""
    src = (JS / "dashboard.js").read_text(encoding="utf-8")
    draw = src[src.index("p.draw = () => {"):]
    draw = draw[: draw.index("scene(reduceMotion")]
    assert "bgArtLastInput > BG_ART_IDLE_MS" in draw
    assert "p.noLoop()" in draw and "p.loop()" in draw
    assert "!reduceMotion" in draw, "a still sketch must not be woken into motion"
    assert "artEpoch += performance.now() - rested" in draw
    assert "let artEpoch" in src
