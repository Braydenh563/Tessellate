"""The writing suggestions fit their own panel, and focus mode can open them
(INBOX 426 b).

The owner: "the suggestions panel doesnt adapt properly to the sidebar and
it also needs to be accessible in full screen mode". Measured in the 320px
right dock: the head was a `flex: none` row of five buttons, 415px wide, so
Dictionary and the close were cut off at the panel's edge and the panel
scrolled 222px sideways (109px at 360 wide); ten ellipsised finding halves
carried no title. In focus mode the only way in, the status bar's chip, is
one of the bands the mode hides. `scratchpad/ui-sweeps/doctoolbarfit.js`
measures the geometry; these lints hold the shapes.
"""

from __future__ import annotations

import re
from pathlib import Path
from tests._app_js import documents_text

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
CSS = sorted((FRONTEND / "css").glob("*.css"))


def _rules():
    for path in CSS:
        text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
        for match in re.finditer(r"(?:(?<=[{}])|\A)([^{}]+)\{([^{}]*)\}", text):
            yield path.name, match.group(1).strip(), match.group(2)


def _props(body: str) -> dict[str, str]:
    out = {}
    for decl in body.split(";"):
        if ":" in decl:
            key, value = decl.split(":", 1)
            out[key.strip()] = value.strip()
    return out


def test_focus_mode_opens_the_suggestions_as_a_side_panel() -> None:
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    tag = re.search(r"<div[^>]*id=\"doc-focus-bar\"[^>]*>", html)
    bar = html[tag.start(): html.index("\n    </div>", tag.start())]
    prose = re.search(r"<button[^>]*id=\"doc-focus-prose\"[^>]*>", bar)
    assert prose and 'aria-controls="doc-prose-panel"' in prose.group(0) and "aria-expanded=" in prose.group(0), (
        "focus mode has no way to open the suggestions"
    )
    side = [body for _, sel, body in _rules() if ".doc-focus" in sel and "#doc-prose-panel" in sel]
    assert any("position: fixed" in b for b in side), "the suggestions are not a side panel in focus mode"
    docs = documents_text()
    assert docs.count("docFocusSyncProse();") >= 3, "the floating dock's Suggestions does not follow the panel"


def test_the_suggestions_panel_fits_its_own_width() -> None:
    """Container queries on the panel, not the window: the same panel is a
    320px column on the right and a full-width band at the bottom."""
    rules = list(_rules())
    panel = [body for _, sel, body in rules if sel == ".doc-prose-panel"]
    assert any("container-type: inline-size" in b for b in panel), "the suggestions panel is not a size container"
    css = "\n".join(p.read_text(encoding="utf-8") for p in CSS)
    assert re.search(r"@container doc-prose\b", css), "no container query sizes the suggestions panel"
    # INBOX 552 (the owner: "ugly line wraps", the head's icons on a second
    # line): the head is one row at every width, and what gives way is the
    # name, never the buttons (which once ran off the panel) or the count.
    heads = [_props(body) for _, sel, body in rules if sel == ".doc-prose-head"]
    assert heads and all(h.get("flex-wrap") == "nowrap" for h in heads), "the suggestions head wraps"
    name = [_props(body) for _, sel, body in rules if sel == ".doc-prose-name"]
    assert name and name[0].get("min-width") == "0" and name[0].get("text-overflow") == "ellipsis", (
        "the head's name cannot give way, so the buttons would"
    )
    count = [_props(body) for _, sel, body in rules if sel == ".doc-prose-count"]
    assert count and count[0].get("flex") == "none", "the head's count can be cut"
    docs = documents_text()
    line = docs.split("function docFindingLine(", 1)[1].split("\n}\n", 1)[0]
    assert "words.title" in line and "why.title" in line, (
        "an ellipsised finding row does not carry its whole text in a title"
    )


def test_the_grip_width_lives_on_the_tab_page() -> None:
    """Focus mode's side panel and the page's padding beside it read the width
    the grip set; only a property on their common ancestor gives both one
    number (on the panel, the padding's `var()` computed to 0)."""
    docs = documents_text()
    assert '($("tab-documents") || panel).style.setProperty("--doc-prose-w"' in docs
    css = "".join(
        re.sub(r"/\*.*?\*/", "", p.read_text(encoding="utf-8"), flags=re.S)
        for p in sorted((ROOT / "frontend" / "css").glob("*.css"))
    )
    assert re.search(r"#tab-documents\s*\{\s*--doc-prose-w:", css)
    assert not re.search(r"\.doc-prose-panel\s*\{[^}]*--doc-prose-w:", css)
    assert re.search(r"--doc-focus-prose-w:\s*min\(var\(--doc-prose-w\)", css)


def test_a_narrow_panels_head_buttons_are_one_icon_group() -> None:
    """Image 92: worded, the head's buttons took two rows of their own in the
    right dock, the close alone on the second. Since INBOX 549 the head's
    tools are icon squares at every width (the Dictionary and the side in
    the ⋯); below 26rem Fix N's words are visually hidden too (never
    dropped: its title and label say the number), so the row stays one."""
    css = (ROOT / "frontend" / "css" / "05-sidebars-themes.css").read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    block = css[css.index("@container doc-prose (max-width: 26rem)"):]
    block = block[: block.index("\n}\n")]
    assert ".doc-prose-tools > .doc-prose-fix-all .ph-text" in block
    assert "clip-path: inset(50%)" in block
    assert "flex-basis: 100%" not in block
    docs = documents_text()
    head = docs.split("function docProseHeader(", 1)[1].split("\n}\n", 1)[0]
    assert "kebabMenu(" in head and "openDocDictionary()" in head and "toggleDocProseDock()" in head
