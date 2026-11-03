"""Every formatting tool can be reached, at every width and in focus mode
(INBOX 426 a and b).

The owner: "in the documents full screen mode, I cant access the formatting
toolbar or any of the other key tools or controls", with a screenshot of the
strip in its one-row mode at about 1000px: a horizontal scrollbar under the
buttons, and the strip's own pinned cluster (the layout, line-number and
collapse buttons, `position: sticky` on an opaque ground) drawn on top of
Insert, so Insert was cut in half and nothing past it could be seen. Focus
mode, for its part, hid the strip, the dock and the status bar outright and
offered no way back to any of them but leaving the mode.

And "the suggestions panel doesnt adapt properly to the sidebar and it also
needs to be accessible in full screen mode": in the right-docked 320px column
the panel's head was a `flex: none` row of five buttons, so the head ran
past the panel, the Dictionary button was cut off and the panel scrolled
sideways; in focus mode the only way to open it (the status bar's chip) was
hidden.

These lints hold the shapes that fix both. The geometry itself (every
button's rect inside the strip's and no two overlapping, at 360, 768, 1024,
1280 and 1600) is measured by `scratchpad/ui-sweeps/doctoolbarfit.js`, which
the suite cannot run.
"""

from __future__ import annotations

import re
from pathlib import Path

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


def test_no_formatting_strip_scrolls_sideways() -> None:
    """One row means one row with a More, never a scroller: a scrolling strip
    hides the tools past its edge and needs a scrollbar to say so."""
    for name, selector, body in _rules():
        if "doc-toolbar" not in selector and "note-toolbar" not in selector:
            continue
        props = _props(body)
        for key in ("overflow-x", "overflow"):
            value = props.get(key, "")
            assert "auto" not in value and "scroll" not in value, (
                f"{name}: {selector} makes a formatting strip scroll ({key}: {value})"
            )
        if "::-webkit-scrollbar" in selector:
            raise AssertionError(f"{name}: {selector} styles a strip scrollbar that must not exist")


def test_the_strips_own_cluster_never_sits_on_the_tools() -> None:
    """The layout, line-number and collapse buttons are a flex item at the end
    of the strip, not a sticky patch over whatever scrolls under it."""
    for name, selector, body in _rules():
        if "doc-toolbar-tools" in selector:
            props = _props(body)
            assert props.get("position", "static") not in {"sticky", "absolute", "fixed"}, (
                f"{name}: {selector} floats the strip's cluster over its tools"
            )


def test_one_row_mode_folds_what_does_not_fit_behind_more() -> None:
    docs = (FRONTEND / "js" / "documents.js").read_text(encoding="utf-8")
    assert "function fitDocToolbarRow(" in docs, "the one-row strip no longer measures what fits"
    mount = docs.split("function mountDocToolbarControlsFor(", 1)[1].split("\nfunction ", 1)[0]
    assert "watchDocToolbarWidth(bar)" in mount and "new ResizeObserver" in docs, (
        "the one-row strip is not refitted when its width changes"
    )
    assert "doc-toolbar-more" in mount and "aria-expanded" in docs.split("function syncDocToolbarMore(", 1)[1][:1500], (
        "the strip's More is gone or does not say whether it is open"
    )
    hidden = [body for _, sel, body in _rules() if re.search(r"\.doc-toolbar-over\b", sel) and ":not(.is-more-open)" in sel]
    assert any("display: none" in b for b in hidden), "a tool that does not fit is not folded away"
    shown = [sel for _, sel, _ in _rules() if "is-more-open" in sel]
    assert shown, "More does not bring the folded tools back"


def test_focus_mode_keeps_a_way_to_the_tools() -> None:
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    tag = re.search(r"<div[^>]*id=\"doc-focus-bar\"[^>]*>", html)
    bar = html[tag.start(): html.index("\n    </div>", tag.start())]
    tools = re.search(r"<button[^>]*id=\"doc-focus-tools\"[^>]*>", bar)
    assert tools and "aria-pressed=" in tools.group(0), "focus mode has no way to show the tools"
    shows = [sel for _, sel, body in _rules() if "doc-focus-tools" in sel and "display" in body]
    assert any("#doc-toolbar" in s for s in shows) and any(".doc-dock" in s for s in shows), (
        "the focus mode's Tools does not bring back the dock and the formatting strip"
    )


def test_a_strip_is_refitted_when_its_contents_change() -> None:
    """A control shown or hidden at a constant width moves the end of the row
    without resizing the strip; the width observer alone missed it, so the
    strip also watches its children, and refits only when what it lays out
    changed (the bold button's `active` class is not a reason)."""
    docs = (FRONTEND / "js" / "documents.js").read_text(encoding="utf-8")
    watch = docs[docs.index("function watchDocToolbarWidth"):]
    watch = watch[: watch.index("\nfunction fitDocToolbars")]
    assert "watchDocToolbarContents(bar)" in watch
    assert "new MutationObserver(" in watch
    assert "docToolbarLayoutSignature(bar)" in watch
    assert "if (next === sig) return;" in watch


def test_a_narrow_strip_folds_its_layout_toggle_first() -> None:
    """At 360 the strip's own group took 176 of a 300px row. Under 600px the
    layout toggle goes behind More, but only when something is folded
    anyway, so a strip whose tools all fit keeps it in reach."""
    docs = (FRONTEND / "js" / "documents.js").read_text(encoding="utf-8")
    fit = docs[docs.index("function fitDocToolbarRow"):]
    fit = fit[: fit.index("\nfunction syncDocToolbarMore")]
    folded = fit.index('bar.classList.add("is-layout-folded")')
    assert fit.index("if (!fits()) {") < folded, "the toggle folds only when More is needed"
    assert "box.width < 600" in fit
    hides = [
        selector
        for _name, selector, body in _rules()
        if ".is-layout-folded" in selector and _props(body).get("display") == "none"
    ]
    assert hides and all(":not(.is-more-open)" in s for s in hides), hides


def test_the_document_strips_group_never_takes_a_row_alone() -> None:
    """Round 4, A3: expanded at 1024 the strip's own three buttons sat alone
    on a third row (`stripwrap.js`). The document strip leaves layout and
    collapse to its ⋯ menu then, and puts line numbers at the first row's
    end when there is room; the group is back at the end before every fit."""
    docs = (FRONTEND / "js" / "documents.js").read_text(encoding="utf-8")
    body = docs[docs.index("function trimDocToolbarGroup"):]
    body = body[: body.index("\n}\n")]
    assert 'bar.id !== "doc-toolbar"' in body, "only the strip whose menu holds the other two"
    assert "bar.appendChild(tools)" in body
    assert 'bar.classList.add("is-group-trimmed")' in body
    fit = docs[docs.index("function fitDocToolbarRow"):]
    fit = fit[: fit.index("\n}\n")]
    assert "trimDocToolbarGroup(bar" in fit
    css = "".join(p.read_text(encoding="utf-8") for p in CSS)
    assert ".doc-toolbar.is-group-trimmed > .doc-toolbar-tools > :is(.doc-toolbar-layout, .doc-toolbar-collapse)" in css
