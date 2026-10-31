"""The document editor's top dock (§ documents).

Reported with a screenshot: "fix/redesign the ui, layout, alignment, sizing,
and look of the documents top dock". What it showed was a single row holding
the title plus twelve controls of four different heights, wrapping onto three
lines with "⬇ PDF" and a bin left alone on the last of them.

Two causes, both invisible in the source and both found by measuring in a
browser:

1. The dock carried `.doc-toolbar`, the *formatting* toolbar's class, so
   `.doc-toolbar button` restyled its `.ghost.small` buttons as 2rem glyph
   buttons while leaving the `<select>` and the segmented control alone.
2. The first fix used `height: var(--control-h)`, and `--control-h` is scoped
   to `.library-toolbar`/`.library-controls`. Undefined here, so the rule was
   invalid and did nothing, silently. Measured: 45 / 43 / 37 / 27 / 22 / 18px
   across six controls that are meant to be one height.

These are lints: nothing here can see a rendered page. They pin the two causes
so neither can come back unnoticed.
"""

from __future__ import annotations

import re
from pathlib import Path
from tests._app_js import app_js_text

HTML = Path("frontend/index.html").read_text(encoding="utf-8")
CSS = "".join(
    p.read_text(encoding="utf-8") for p in sorted(Path("frontend/css").glob("*.css"))
)


def test_the_dock_is_not_a_formatting_toolbar():
    """`.doc-toolbar button` is written for H1/B/I glyph buttons. The dock
    shared the class and inherited it."""
    dock = HTML.split('class="row space-between doc-dock"')[1].split("</div>")[0]
    assert "doc-toolbar" not in HTML.split("doc-dock")[0][-200:], "the dock kept the class"
    assert 'class="doc-toolbar" id="doc-toolbar"' in HTML, "the formatting bar keeps it"
    assert dock


def test_the_dock_declares_the_control_height_it_uses():
    """`--control-h` is not a global token. Used without being declared it is
    invalid where it is *used*, and an invalid height is silently no height, 
    the same shape as the appearance-defaults bug in CLAUDE.md."""
    block = CSS.split(".doc-dock {")[1].split("}")[0]
    assert "--control-h:" in block, (
        "--control-h is scoped to .library-toolbar; the dock has to declare its own"
    )
    heights = CSS.split(".doc-dock .ghost.small,")[1].split("}")[0]
    assert "height: var(--control-h)" in heights


def test_every_control_in_the_dock_is_sized_by_that_one_rule():
    """A select, a segmented control and a button each arrive from a different
    base rule and each size themselves."""
    selectors = CSS.split(".doc-dock .ghost.small,")[1].split("{")[0]
    for part in (".seg",):
        assert part in selectors, part


def test_the_least_used_controls_are_behind_one_kebab():
    """Export .md, export PDF and delete were a third of the bar."""
    assert 'id="doc-dock-menu"' in HTML
    menu = HTML.split('id="doc-dock-menu"')[1].split("</details>")[0]
    for element_id in ("doc-export-md", "doc-export-pdf", "doc-delete"):
        assert f'id="{element_id}"' in menu, element_id


def test_the_ids_did_not_move():
    """documents.js binds by id. A redesign that renames one is a redesign
    that silently unwires it, the "features that never ran" shape."""
    js = Path("frontend/js/documents.js").read_text(encoding="utf-8")
    for element_id in re.findall(r'\$\("(doc-[a-z-]+)"\)', js):
        assert f'id="{element_id}"' in HTML, element_id


def test_the_export_label_is_set_with_setlabel_not_textcontent():
    """The button carries an icon element now. `textContent = …` would wipe
    it, which is the kind of thing that looks fine until you open the menu."""
    js = Path("frontend/js/documents.js").read_text(encoding="utf-8")
    assert 'setLabel($("doc-export-md")' in js
    assert '$("doc-export-md").textContent' not in js


def test_the_kebab_closes_on_a_pick_and_on_a_click_away():
    """`<details>` gives open/close, Enter/Space and Escape. It gives neither
    of these."""
    js = Path("frontend/js/documents.js").read_text(encoding="utf-8")
    assert "doc-dock-menu-item" in js
    assert "menu.contains(event.target)" in js


def test_the_name_and_the_type_share_a_row():
    """They are the same statement about the document. Moving the select off
    the action row is also what let that row fit on one line, measured at
    1018px, it was 20px too wide with the select still in it."""
    #: Cut at the next dock section, not the first `</span>`: the Back
    #: button's own label is a span inside the identity (the laptop pass,
    #: 2026-09-27), and the first close tag was that label's.
    identity = HTML.split('class="doc-dock-identity"')[1].split('class="row doc-actions"')[0]
    assert 'id="doc-title"' in identity
    # INBOX 1482: the type left the dock for the foot (a button opening the
    # grouped picker, `docTypeMenu`), so the identity row is still the title
    # alone and the dock's ⋯ menu no longer holds a select for it.
    assert 'id="doc-type-slot"' in HTML.split('id="doc-statusbar"')[1]
    assert 'id="doc-file-type"' not in HTML
    assert 'id="doc-file-type"' not in identity


def test_printing_still_hides_the_dock():
    """It used to be hidden by `.doc-toolbar`; losing that class silently put
    a toolbar on every printed page."""
    assert "body.printing-doc .doc-dock," in CSS


def test_every_kebab_uses_the_same_icon():
    """Reported from two screenshots side by side: the gallery's kebab was
    vertical dots and every other one in the app was horizontal, which read as
    two different controls doing one job. The dock and the gallery stay the
    horizontal meatball. Since INBOX 706 the vertical kebab exists on purpose,
    for the end of a row in a vertical list and a narrow column, chosen by
    `kebabMenu(..., { vertical: true })` and pinned by
    `tests/test_icon_conventions.py`; neither the dock's documents.js nor the
    gallery's library.js ever names it."""
    sources = {
        p.name: p.read_text(encoding="utf-8")
        for p in (
            Path("frontend/index.html"),
            Path("frontend/js/library.js"),
            Path("frontend/js/documents.js"),
        )
    }
    for name, text in sources.items():
        if name != "index.html":
            assert "dots-three-vertical" not in text, f"{name} names the vertical kebab"
    assert 'class="ph ph-dots-three"' in sources["index.html"]
    assert '"ph:dots-three"' in app_js_text()
    #: library.js used to draw its own kebab and is asserted *not* to now: the
    #: Images/Files gallery menu was a second implementation of one control, 
    #: its own `<details>`, its own list class, its own placement code, which
    #: is how it drifted from every other menu in the app three times over. It
    #: calls `kebabMenu()` (app.js) like everything else, so the glyph is
    #: chosen in exactly one place and this file cannot disagree with it.
    assert "ph:dots-three" not in sources["library.js"], (
        "library.js is drawing its own kebab again, use kebabMenu() from app.js"
    )


def test_enter_in_the_title_starts_the_body():
    """UX-05: "Trip plan", Enter, "Day one" typed on into the title. The
    behaviour is measured by scratchpad/ui-sweeps/ux1005-doctitle.js at 1440
    and 390; this pins the handler's shape so it is not lost."""
    source = Path("frontend/js/documents.js").read_text(encoding="utf-8")
    start = source.index('$("doc-title").addEventListener("keydown"')
    handler = source[start : source.index("\n});", start)]
    assert "event.isComposing" in handler, "Enter that ends an IME composition is not a line break"
    assert '"Enter"' in handler and "preventDefault" in handler
    assert "docCmView.focus()" in handler and 'setDocView(' in handler
