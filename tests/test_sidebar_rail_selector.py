"""The rail clearance names the elements it is for (wbp2).

`.sidebar-panel ~ *` matched every element, so each restyled node anywhere
(a mind map's two hundred topics are siblings in one layer) walked its
preceding siblings looking for a sidebar. The rule is for the content column
that follows a sidebar and nothing else, so the subject is a short list of
classes, wrapped in `:where()` so the specificity stays exactly what the
universal rule's was and no other rule's cascade moves.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

from tests._css_paths import CSS_DIR, FRONTEND_DIR

RAIL = re.compile(r"\.sidebar-panel\s*~\s*(:where\(([^)]*)\)|[^\s{,]+)\s*\{")
#: The file and the number of scoped rail rules it holds: one was in
#: 10-responsive.css until UI plan 13b moved it beside 07's.
FILES = {"07-whiteboard-misc.css": 2}


def _css(name: str) -> str:
    return (CSS_DIR / name).read_text(encoding="utf-8")


def test_no_rule_uses_the_universal_sibling_after_a_sidebar() -> None:
    for path in sorted(CSS_DIR.glob("*.css")):
        text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
        assert not re.search(r"\.sidebar-panel\s*~\s*\*", text), f"{path.name}: a universal sibling rule"


def _listed_classes() -> set[str]:
    listed: set[str] = set()
    for name in FILES:
        text = re.sub(r"/\*.*?\*/", "", _css(name), flags=re.DOTALL)
        found = [m for m in RAIL.finditer(text) if m.group(2) is not None]
        assert len(found) >= FILES[name], f"{name} lost a scoped rail rule"
        for match in found:
            listed |= {c.strip().lstrip(".") for c in match.group(2).split(",")}
    return listed


class _Siblings(HTMLParser):
    """For each element with `.sidebar-panel`, the classes of its later siblings."""

    VOID = {"meta", "link", "br", "hr", "img", "input", "source", "path", "circle", "rect", "line"}

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[list[tuple[str, set[str]]]] = [[]]
        self.later: list[tuple[str, set[str]]] = []

    def handle_starttag(self, tag, attrs):
        classes = set((dict(attrs).get("class") or "").split())
        self.stack[-1].append((tag, classes))
        if tag not in self.VOID:
            self.stack.append([])

    def handle_endtag(self, tag):
        if tag in self.VOID or len(self.stack) < 2:
            return
        kids = self.stack.pop()
        seen = False
        for kid_tag, kid_classes in kids:
            if seen:
                self.later.append((kid_tag, kid_classes))
            if "sidebar-panel" in kid_classes:
                seen = True


def test_every_sibling_after_a_sidebar_in_the_page_is_named_by_the_rule() -> None:
    """The universal rule reached whatever followed a sidebar; the list reaches
    the three things that do today. A fourth, added to index.html, fails here
    until it is named, which is the cost of not matching everything."""
    parser = _Siblings()
    parser.feed((FRONTEND_DIR / "index.html").read_text(encoding="utf-8"))
    listed = _listed_classes()
    assert parser.later, "the page has no element after a sidebar; the parse is wrong"
    missing = [(tag, sorted(c)) for tag, c in parser.later if not (c & listed)]
    assert not missing, f"siblings after a .sidebar-panel that the rail rule does not name: {missing}"


def test_the_scoped_rule_is_where_so_its_specificity_is_unchanged() -> None:
    for name in FILES:
        text = re.sub(r"/\*.*?\*/", "", _css(name), flags=re.DOTALL)
        assert text.count(".sidebar-panel ~ :where(") >= FILES[name], f"{name}: the subject must sit in :where()"
