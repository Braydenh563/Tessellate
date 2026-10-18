"""One disclosure marker (INBOX 464 (14), DESIGN.md "A disclosure marker").

Settings folds, the help accordion and task logs drew a 5x6px triangle built
from borders in `--muted` (08-consistency.css), crossed with a 2px rotated
border chevron from 07-whiteboard-misc.css; the Library's Contents, notes and
outlines drew the 16px Phosphor caret. Every fold now draws the caret.
"""
import re
from pathlib import Path

CSS_DIR = Path(__file__).resolve().parents[1] / "frontend" / "css"
CSS = {p.name: p.read_text(encoding="utf-8") for p in CSS_DIR.glob("*.css")}
FAMILIES = (
    ".help-accordion details > summary",
    ".settings-section summary",
    ".settings-group > summary",
    ".settings-fold > summary",
    ".advanced-css > summary",
    ".task-log > summary",
    ".chat-sources > .chat-sources-summary",
)


def _marker_rule():
    text = CSS["08-consistency.css"]
    for m in re.finditer(r"([^{}]*)\{([^}]*)\}", text):
        if "::before" in m.group(1) and all(f in m.group(1) for f in FAMILIES):
            return m.group(2)
    return None


def test_every_fold_family_draws_the_phosphor_caret():
    body = _marker_rule()
    assert body, "the shared disclosure marker rule is missing a family"
    assert 'content: "\\e136"' in body
    assert "font-family: Phosphor" in body
    assert "rotate(-90deg)" in body
    assert "border: 0" in body


def test_no_fold_draws_a_chevron_from_borders():
    for name, text in CSS.items():
        for m in re.finditer(r"([^{}]*)\{([^}]*)\}", text):
            sel, body = m.group(1), m.group(2)
            if "summary" not in sel or "::before" not in sel:
                continue
            if not any(f in sel for f in FAMILIES + (".about-whats-new", ".help-accordion > summary")):
                continue
            assert not re.search(r"border-(left|right|bottom):\s*[\d.]+(px|rem) solid currentColor", body), (
                f"{name}: a border-drawn marker on a fold: {sel.strip()[:80]}"
            )


def test_the_library_caret_is_the_same_glyph():
    js = (CSS_DIR.parent / "js" / "library.js").read_text(encoding="utf-8")
    assert 'ph ph-caret-down contents-caret' in js


def test_every_open_caret_outranks_its_closed_twin():
    """An open fold's caret turns down (INBOX 477). The closed rule's
    `:not(.icon-only):not(.icon-button)` chain is three classes of
    specificity; an open selector without it lost to it, and every one of
    109 folds kept its caret turned while open. So each closed selector's
    `:not()` chain appears again in an open selector for the same family."""
    css = CSS["08-consistency.css"]
    start = css.index("The chevron the native marker was hiding: **one")
    block = css[start : start + 6000]
    closed_head = block[block.index("*/") : block.index("{")]
    open_start = block.index("[open]")
    open_head = block[block.rfind("}", 0, open_start) : block.index("{", open_start)]
    closed = [s.strip() for s in closed_head.split(",") if ":not(" in s]
    assert closed, "found no closed selectors to check"
    for selector in closed:
        chain = selector[selector.index(":not(") : selector.index("::before")]
        assert chain in open_head, f"no open twin carries {chain!r} for {selector!r}"


def test_the_sources_fold_shows_its_state_and_starts_shut():
    # INBOX 1300 C29, the owner: "hard to tell from the ui of the sources box
    # and dropdown list of sources below if the sources are actually part of
    # that button's dropdown and if the button is open or not". The caret
    # turns upright open (`sources1300.js`: -90deg shut, none open, on the
    # popup's panel and the Chat card panel alike), the list hangs from a
    # rail under it, and no surface opens it for you.
    assert ".chat-sources[open] > .chat-sources-summary::before" in CSS["08-consistency.css"]
    body = re.search(r"\.chat-sources-body \{([^}]*)\}", CSS["02-chat-graph.css"]).group(1)
    assert "border-left: 1px solid var(--border)" in body
    js = (CSS_DIR.parent / "js" / "chat-agent.js").read_text(encoding="utf-8")
    panel = js[js.index("function chatSourcesPanel(") :]
    panel = panel[: panel.index("\n}\n")]
    assert "details.open" not in panel
