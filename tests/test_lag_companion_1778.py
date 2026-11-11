"""The companion's two avoidable restyle costs (INBOX 1778 d).

A browser cannot run in pytest, so these are static. Measured on the running app at 4x CPU, 200 notes, Atlas
companion on (790 elements under `#nm-buddy`, 21 Atlas marks on the page):

- `setAtlasMood` wrote `--atl-ease` on every mark, a custom property nothing reads. An unregistered custom
  property restyles the whole subtree, so each mood change cost a median 23.6 ms (spikes of 199 and 537 ms) of
  forced style in the first read after it; with only the class toggle, a median 2.7 ms.
- `#nm-buddy:has(.atl-figure...)` made every child insert or remove anywhere under the companion re-match its
  subtree: 20 ms for one span under `#nm-buddy`, 22 to 44 ms under the face button; 0.0 and 0.4 ms once the
  figure's look rides `data-atlas-figure` on the companion, set where the figure is mounted.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = ROOT / "frontend" / "css"


def _strip_css(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _fn(js: str, head: str) -> str:
    start = js.index(head)
    return js[start : js.index("\n}\n", start)]


def test_the_mood_ease_is_a_class_and_writes_no_custom_property() -> None:
    js = (JS / "atlas.js").read_text(encoding="utf-8")
    fn = _fn(js, "function setAtlasMood(")
    assert 'svg.classList.toggle("atl-easing", !!easeMs)' in fn
    assert "--atl-ease" not in fn
    assert "setProperty" not in fn, "a style write on every Atlas mark restyles each mark's subtree"


def test_no_script_writes_an_atlas_ease_property_nothing_reads() -> None:
    css = "".join(_strip_css(p.read_text(encoding="utf-8")) for p in CSS.glob("*.css"))
    assert "var(--atl-ease" not in css
    for path in JS.glob("*.js"):
        code = re.sub(r"^\s*//.*$", "", path.read_text(encoding="utf-8"), flags=re.M)
        assert 'setProperty("--atl-ease"' not in code, path.name


def test_the_companion_css_has_no_has_selector() -> None:
    css = _strip_css((CSS / "08-consistency.css").read_text(encoding="utf-8"))
    bad = [line.strip()[:120] for line in css.splitlines() if "nm-buddy" in line and ":has(" in line]
    bad += [line.strip()[:120] for line in css.splitlines() if re.search(r"&(?:\[[^\]]*\])?(?::not\()?:has\(\.atl-figure", line)]
    assert not bad, f"a :has() on the companion re-matches its 790 elements on every insert or remove: {bad}"


def test_the_companion_css_reads_the_marker_attribute() -> None:
    css = _strip_css((CSS / "08-consistency.css").read_text(encoding="utf-8"))
    assert '#nm-buddy[data-atlas-figure]:is([data-pose="lie"], [data-pose="lie-2"], [data-pose="curl"])::before' in css
    assert "#nm-buddy[data-atlas-figure] .nms { opacity: 0; }" in css
    assert '&[data-atlas-figure="masculine"].nmb-walking .nm-buddy-char' in css
    assert ":not([data-atlas-figure]).nmb-walking:not([data-travel]) .nmb-arm-l" in css


def test_the_marker_is_set_and_cleared_where_the_figure_is_mounted() -> None:
    js = (JS / "avatars.js").read_text(encoding="utf-8")
    start = js.index("char.prepend(characterFor(seed).figure());")
    block = js[start : start + 700]
    assert 'char.querySelector(".atl-figure-box")?.dataset.atlasLook' in block
    assert "buddy.dataset.atlasFigure = figureLook" in block
    assert "delete buddy.dataset.atlasFigure" in block
    # One mount point: a second place that swaps the companion's figure would need the marker too.
    assert js.count("char.prepend(characterFor(seed).figure())") == 1
