"""The phone's sidebar openers are mounted into docks that live in lazy surfaces.

`mountPhoneSidebarOpeners` looks each dock up when it runs. Notes, Chat,
Documents and the Library are built on first use (`surfaceBuild`), so a mount
that ran once at load found no Notes or Chat dock and never came back: below
600px there was no rail and no opener, and the sidebar could not be opened.
Each surface that holds a sidebar dock has to mount again when it is built.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _surface_of(element_id: str) -> str:
    """The `data-surface` template that holds `id="element_id"` in index.html.

    By position, not by matching the template's end tag: a surface can nest
    another script template (the Library holds the board)."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    starts = [(m.start(), m.group(1)) for m in re.finditer(r'<(?:script type="text/x-surface"|template) data-surface="([^"]+)"', html)]
    for hit in re.finditer(rf'<aside[^>]*\bid="{re.escape(element_id)}"', html):
        before = [name for pos, name in starts if pos < hit.start()]
        if before:
            return before[-1]
    raise AssertionError(f"#{element_id} is not inside a lazy surface")


def test_each_sidebar_dock_remounts_its_opener_when_its_surface_is_built():
    src = (ROOT / "frontend" / "js" / "phone-shell.js").read_text(encoding="utf-8")
    rows = re.search(r"const PHONE_SIDEBAR_OPENERS = \[(.*?)\n\];", src, re.S).group(1)
    for aside in re.findall(r'aside: "([^"]+)"', rows):
        surface = _surface_of(aside)
        assert re.search(rf'onSurface\("{surface}",\s*mountPhoneSidebarOpeners\)', src), (
            f"the {aside} opener is never mounted once the {surface} surface is built"
        )


def test_each_sidebar_is_wired_for_resize_and_its_toggle_when_its_surface_is_built():
    """`initResizableSidebars` makes the rail toggle (the sheet's own closer) on
    each sidebar; a surface left out of its list never got one, so the phone
    opener pressed nothing."""
    src = (ROOT / "frontend" / "js" / "sheets-selects.js").read_text(encoding="utf-8")
    listed = set(re.findall(r'"([a-zA-Z]+)"', re.search(r"for \(const name of \[([^\]]*)\]\) onSurface\(name, wire\)", src).group(1)))
    ids = re.search(r"const SIDEBAR_IDS = \[([^\]]*)\]", src).group(1)
    for aside in re.findall(r'"([^"]+)"', ids):
        surface = _surface_of(aside)
        assert surface in listed, f"#{aside} (surface {surface}) is never wired once it is built"
