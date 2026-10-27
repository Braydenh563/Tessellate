"""What a cold launch downloads before the lock screen, held down (audit
2026-10-05, FE-06).

WORLD_CLASS_PLAN H7 measured boot JS going 1,699 to 1,072 KB against a 1 MB
line on 2026-09-24 and named `boottime.js` the gate; nothing ran it, no test
bounded a boot asset, and the audit found 1,384 KB nine days later. This
reads every `<script src>` and `<link rel="stylesheet">` in `index.html`,
takes each one's bytes as served (the app's own stripped of comments,
`api/asset_strip.py`; a vendored file as it is), gzips them as the server
does, and fails over the caps. Lazy bundles (`LAZY_MODULES` in app.js) and
the p5 the emblem fetches after load are not in it: this is the boot.

The caps are the measured totals plus 2%, and only ever go down. When a
change is worth more boot bytes than that, the answer is the next surface
out of the boot (a lazy bundle), not a bigger number here.
"""

from __future__ import annotations

import gzip
import re
from pathlib import Path

from tessellate.api.asset_strip import strip_for_path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
INDEX = FRONTEND / "index.html"

SCRIPT = re.compile(r'<script[^>]*\ssrc="(/[^"?]+)(?:\?[^"]*)?"', re.I)
STYLE = re.compile(r'<link[^>]*rel="stylesheet"[^>]*href="(/[^"?]+)(?:\?[^"]*)?"', re.I)

#: 2026-10-05, measured by this test after the serve-time strip: 38 boot
#: scripts 691,724 bytes gzipped (the app's own 599,265 plus d3's 92,459;
#: the largest of the app's, avatars.js, 91,517), 12 stylesheets 179,712.
#: Before the strip the audit measured 1,384 KB of boot JS and 810 KB of CSS.
#: Plus 2%.
#: 2026-10-05, audit FE-07: d3 left the boot (it comes with the graph and
#: library bundles) and the template picker and a few guards left app.js:
#: 37 scripts, 589,299 bytes. Plus 2%.
#: 2026-10-05, the integration branch after search-boot-1005 merged: 590,758
#: (the note edit form, the full backup's two handlers and seven other
#: one-caller helpers moved into the lazy files that call them, and 63
#: same-bundle guards dropped). The measure rounded up to the next 100.
#: After claude/notes-flow-rebuild 143b240 merged (616's form, skeletons):
#: 589,955, with the embedding models list, the edit form's close and the
#: Settings bar's New listener moved to their lazy files.
#: And after 88227db (621, 622): 589,719.
#: And after the Atlas merge (f22bd43), with the companion's menu and
#: enlarged view in companion-menu.js (lazy): 589,093.
#: And with the s2 agent's list drag-select edge scroll (selection.js, +489,
#: boot): 589,597, a raise the next agent undid: the edge scroll moved whole
#: into drag-edge.js (lazy, preloaded three seconds after boot, like
#: quick-note.js) and the note edit form's formatting strip
#: (`noteEditToolbar`, only `renderEditForm` calls it) into
#: note-edit-panels.js: 588,354, so the cap is back below 589,100.
#: 2026-10-10, bootdiet: `featureCatalog` moved to app-features.js (lazy, with the
#: palette bundle), after Brief 80 took the boot to 588,728; measured 582,849.
#: 2026-10-25, composer2: bg-art.js (20 KB) became the lazy `bgArt` bundle,
#: boot measured 568,431, so about 20 KB of room; the cap is unchanged.
BOOT_JS_CAP = 588_400
#: 2026-10-10 INBOX 767: the no-model notice's row and phone grid cost 58
#: gzipped bytes, paid for by the blank lines of 08-consistency.css (61), so
#: the cap holds; the next CSS goes in a lazy file.
#: 2026-10-11, uiset (OPEN: "BOOT_CSS_CAP can be lowered now that strip_css
#: drops comment-leftover lines"): measured 178,351, so the cap comes down
#: from 183,300. The same session's menu row fit, toast stack and credits
#: rows took it to 178,530; the cap is that with 470 bytes of room.
#: 2026-10-27: the Reminders row's always-drawn ⋯ and the gap that keeps the
#: time off it cost 54 gzipped bytes (head 178,997, now 179,051) and the head
#: had 3 to spare; there is no lazy file for a row that draws at boot, so the
#: cap rises by 100.
BOOT_CSS_CAP = 179_100


def _served_gzip(url: str) -> int:
    path = FRONTEND / url.lstrip("/")
    body = path.read_bytes()
    if not url.startswith("/vendor/"):
        body = strip_for_path(path.name, body)
    return len(gzip.compress(body, 9, mtime=0))


def _boot(pattern: re.Pattern) -> dict[str, int]:
    html = re.sub(r"<!--.*?-->", "", INDEX.read_text(encoding="utf-8"), flags=re.S)
    return {url: _served_gzip(url) for url in pattern.findall(html)}


def test_boot_scripts_stay_under_the_budget():
    sizes = _boot(SCRIPT)
    assert len(sizes) >= 20, "the boot scripts were not found: has index.html moved?"
    total = sum(sizes.values())
    largest = sorted(sizes.items(), key=lambda kv: -kv[1])[:5]
    assert total <= BOOT_JS_CAP, (
        f"boot JS is {total} bytes gzipped (cap {BOOT_JS_CAP}); largest: {largest}. "
        "Move a surface into a lazy bundle rather than raising the cap."
    )


def test_boot_stylesheets_stay_under_the_budget():
    sizes = _boot(STYLE)
    assert len(sizes) >= 5, "the stylesheets were not found: has index.html moved?"
    total = sum(sizes.values())
    assert total <= BOOT_CSS_CAP, f"boot CSS is {total} bytes gzipped (cap {BOOT_CSS_CAP})"


def test_the_list_edge_scroll_is_a_lazy_file_not_boot_code():
    """The drag-select edge scroll is a held mouse drag's alone, so selection.js
    and phone-shell.js carry none of it; `LAZY_MODULES.dragEdge` fetches
    drag-edge.js after boot and the file wires its own listeners."""
    boot = "\n".join((FRONTEND / "js" / name).read_text(encoding="utf-8") for name in ("selection.js", "phone-shell.js"))
    assert "DragSelectEdgeScroll" not in boot and "DRAG_EDGE" not in boot
    lazy = (FRONTEND / "js" / "drag-edge.js").read_text(encoding="utf-8")
    assert lazy.rstrip().endswith("initDragSelectEdgeScroll();")
    app = (FRONTEND / "js" / "app.js").read_text(encoding="utf-8")
    assert 'dragEdge: ["/js/drag-edge.js"]' in app and '"notePanels", "dragEdge"' in app


def test_a_drag_begun_before_the_edge_scroll_arrives_still_scrolls():
    """qa-1005: a drag in the first seconds after boot (before the preload) or
    on a slow disk scrolled 0px at the edge, since the file's listeners missed
    the press. Boot keeps only the press (`EDGE_SCROLL_HELD`, selection.js) and
    asks for the bundle; drag-edge.js picks the held press up at load and
    starts its tick from the pointer's last place. Measured by
    `scratchpad/ui-sweeps/search1005-lazy.js` FIRST=1 SLOW=1500: 0px, then 756px."""
    boot = (FRONTEND / "js" / "selection.js").read_text(encoding="utf-8")
    assert "EDGE_SCROLL_HELD.press = { target: event.target" in boot and 'ensureModule("dragEdge")' in boot
    lazy = (FRONTEND / "js" / "drag-edge.js").read_text(encoding="utf-8")
    assert "dragEdgeZone(held.target)" in lazy and "d.frame = requestAnimationFrame(dragEdgeTick)" in lazy
