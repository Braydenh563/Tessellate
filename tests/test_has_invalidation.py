"""A `:has()` must not sit before a rightmost compound that has no class or
id in it (audit FEAT-02, 2026-10-05).

Traced on a 301-topic map: with `.doc-layout:has(> #doc-sidebar.hidden) >
:not(#doc-sidebar)` in the stylesheet, appending one element anywhere inside
the board, or turning a topic's text editable, restyled 3,731 elements, every
element on the page, 55 to 80ms each time. Chrome cannot key the
invalidation for a `:has()` in a non-subject position when what follows it
names no class or id, so it restyles everything. Three such rules
(`.entry-list.is-rows li:not(:has(textarea)) > *:not(...)`, the one above,
and `#capture > .row:has(> h2) button`) took one Tab on a map from about
20ms of style work to about 180ms; rewritten, the insertion costs 20ms.

A ratchet, because a few weaker cases remain (a type selector after the
`:has()`, measured at 10 to 20ms each) and are listed here to be cut down,
never added to.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = sorted((ROOT / "frontend" / "css").glob("*.css"))

#: Selectors with a `:has()` before a rightmost compound that names no class
#: or id. Only ever lowered.
CEILING = 9


def _split_top(text: str, sep: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in text:
        depth += ch == "("
        depth -= ch == ")"
        if ch == sep and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return out


def _rightmost(selector: str) -> str:
    depth, last = 0, 0
    for i, ch in enumerate(selector):
        depth += ch == "("
        depth -= ch == ")"
        if depth == 0 and ch in " >~+":
            last = i + 1
    return selector[last:].strip()


def _outside_parens(compound: str) -> str:
    out, depth = "", 0
    for ch in compound:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0:
            out += ch
    return out


def offenders() -> list[str]:
    found = []
    for path in CSS:
        text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
        for prelude in re.findall(r"([^{}]+)\{", text):
            if ":has(" not in prelude or prelude.strip().startswith("@"):
                continue
            for selector in _split_top(prelude, ","):
                selector = " ".join(selector.split())
                if ":has(" not in selector:
                    continue
                last = _rightmost(selector)
                if ":has(" in last:
                    continue
                keyed = _outside_parens(re.sub(r"::?[\w-]+", "", last))
                if "." in keyed or "#" in keyed:
                    continue
                found.append(f"{path.name}: {selector}")
    return found


def test_the_three_measured_rules_stay_rewritten():
    joined = "\n".join(offenders())
    assert "> :not(#doc-sidebar)" not in joined
    assert "li:not(:has(textarea)) > *:not(.entry-title)" not in joined
    assert ".row:has(> h2) button" not in joined


def test_no_new_unkeyed_rule_after_a_has():
    found = offenders()
    assert len(found) <= CEILING, "\n".join(found)


#: Classes so common that a `:has()` keyed on one of them is keyed on nothing:
#: `.doc-ai-card > #doc-ai-verb label:has(input:checked) > .ph` restyled every
#: icon on the page, 4,700 on one Tab on a 301-topic map (FEAT-02's 100ms gate,
#: `scratchpad/ui-sweeps/mmd2-1005-maptrace.js` with WHY=1).
UBIQUITOUS = {"ph", "ph-lead", "ghost", "small", "icon-only", "card", "hidden", "muted"}


def test_no_has_is_keyed_only_on_a_class_everything_wears():
    found = []
    for path in CSS:
        text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
        for prelude in re.findall(r"([^{}]+)\{", text):
            if ":has(" not in prelude or prelude.strip().startswith("@"):
                continue
            for selector in _split_top(prelude, ","):
                selector = " ".join(selector.split())
                last = _rightmost(selector)
                if ":has(" not in selector or ":has(" in last:
                    continue
                keyed = _outside_parens(re.sub(r"::?[\w-]+", "", last))
                classes = set(re.findall(r"\.([\w-]+)", keyed))
                if classes and classes <= UBIQUITOUS and "#" not in keyed:
                    found.append(f"{path.name}: {selector}")
    assert not found, "\n".join(found)


def test_no_has_looks_for_a_contenteditable_attribute():
    """OPEN 813: `#entry-list > li:not(:has(textarea, details[open],
    [contenteditable="true"]))` made turning a map topic's text editable
    restyle the board twice over: an attribute named inside a `:has()` is
    checked against every `contenteditable` write on the page, and the board's
    topic editor writes one on every add. Measured at 390px on a 20-topic map,
    the write plus the focus cost 22ms of style work with it and 12ms without
    (the note editor's CodeMirror root is `.cm-editor`, which says the same
    thing by class)."""
    found = []
    for path in CSS:
        text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
        for prelude in re.findall(r"([^{}]+)\{", text):
            for has in re.findall(r":has\(([^()]*(?:\([^()]*\)[^()]*)*)\)", prelude):
                if "contenteditable" in has:
                    found.append(f"{path.name}: {' '.join(prelude.split())}")
    assert not found, "\n".join(found)


def test_a_tab_anchored_has_names_its_child_not_a_search_of_the_tab():
    """OPEN 813: `.tab-page:has(#library-view-whiteboard:not(.hidden))` and
    its three siblings searched the whole tab for the id on every restyle of
    the dock button they hide. The Library tab holds the open board's two
    thousand elements, so the three of them cost 38ms (selector stats, one
    add at 390px on 200 topics). A `:has(> child)` looks at the tab's own
    children and nothing else. A rule for one tab names it (`:where(#tab-notes)`)
    so the search stays inside a tab that is small."""
    found = []
    for path in CSS:
        text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
        for prelude in re.findall(r"([^{}]+)\{", text):
            for selector in _split_top(prelude, ","):
                selector = " ".join(selector.split())
                if re.search(r"(?:\.tab-page|#tab-library):has\((?!>)", selector):
                    found.append(f"{path.name}: {selector}")
    assert not found, "\n".join(found)


def test_a_line_shows_its_ends_by_a_class_on_its_own_group():
    """OPEN 813: `.wb-map-edge-group:has(.wb-map-edge-handle.is-shown)` and a
    `:has(:focus-visible)` on the same group were re-matched for every line on
    the board by every class write, 8ms of 15 in the add's focus flush at 200
    topics. The group carries `is-shown` beside its handle instead."""
    lazy = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    assert ".wb-map-edge-group.is-shown .wb-map-edge-end" in lazy
    assert ":has(.wb-map-edge-handle" not in lazy
    misc = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    assert ".wb-map-edge-group:is(:focus-visible, :has(:focus-visible))" not in misc
    js = (ROOT / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")
    assert 'handle.parentNode.classList.toggle("is-shown", on)' in js
