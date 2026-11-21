"""A map out: the outline, markdown, text, OPML, FreeMind and XMind writers and the export route.

Moved whole from `routes_whiteboard.py` (audit AR3, gods-2): the code is unchanged, and
`routes_whiteboard` re-exports every name here that anything reads. Imports run one way,
down the layer list in `routes_whiteboard.py`'s docstring, never back to `routes_whiteboard`.
"""

from __future__ import annotations

import json
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from tessellate.entry.manager_text import extract_title
from tessellate.core.deps import get_session
from tessellate.api.wb_model import MAP_TOPIC_KIND
from tessellate.api.wb_tree import MAX_MAP_DEPTH, _build_tree, _cross_links, _map_objects
from tessellate.api.wb_board import _board_entry, _board_numbered, _board_settings, _board_theme, _themed_style, _without_pins

router = APIRouter()


# --- export and import: text formats, so a map is not a lock-in -------------
#
# MINDMAP_PLAN.md §5 items 16-17. PNG/SVG/PDF come from the canvas and are the
# frontend's; Markdown and OPML are text, cost nothing, and are what every
# other mindmapper reads: which is the difference between a map you can take
# with you and a map you can only look at here.


def _outline_rows(roots: list[dict]) -> list[tuple[int, dict]]:
    """The tree flattened to `(depth, node)` in reading order. Iterative for
    the same reason every other walk in this file is.

    **And guarded by a seen set, which is a different reason.** Iterative made
    this safe against a deep map and did nothing at all about a *ring*.
    `_build_tree` deliberately re-roots the lowest id of an unreachable ring
    so its rows are not silently dropped, which means a ring arrives here as a
    root whose descendants lead back to it: a to b to a, forever, appending a
    row each time. That is not a crash, it is a Markdown export that never
    returns and grows until the process dies, which is worse than a 500.

    The depth is clamped rather than the walk cut short: an outline is a
    picture of the whole map, and dropping a subtree past some depth loses
    rows a person typed. `MAX_MAP_DEPTH` is the figure every other walk in
    this file stops at.
    """
    rows: list[tuple[int, dict]] = []
    seen: set[int] = set()
    stack = [(0, node) for node in reversed(roots)]
    while stack:
        depth, node = stack.pop()
        if node["id"] in seen:
            continue
        seen.add(node["id"])
        rows.append((min(depth, MAX_MAP_DEPTH), node))
        stack.extend(
            (depth + 1, child)
            for child in reversed(node["children"])
        )
    return rows


def _export_tree(root_element, roots: list[dict], build) -> None:
    """Build one element per node, under the element its parent built.

    **The two XML exports used to recurse, and they were the only walks in
    this file that did.** Every other one is iterative with a seen set, and
    `_is_descendant`'s comment says why: a walk of a tree that is not one is a
    stack overflow rather than a refusal. These two had the same exposure from
    two directions. Nothing caps how deep a map built by hand can go
    (`MAX_IMPORT_DEPTH` caps an import; the Tab key is not an import), so a
    branch deeper than Python's own recursion headroom exported as a
    `RecursionError`, which reaches the person downloading it as a 500. And
    `_build_tree` re-roots the lowest id of an unreachable ring rather than
    dropping its rows, so a ring arrives here as a root whose descendants lead
    back to it, and a recursive walk of that never returns at all.

    `build(parent_element, node)` returns the element it made, so the walk
    holds no state of its own between calls: two exports running at once share
    nothing, which a module-level map of node id to element would not have
    given.

    Nesting is clamped at `MAX_MAP_DEPTH` rather than cut: a node past the cap
    is written as a sibling at the cap instead of being dropped, so the file
    still holds every topic a person typed. Two hundred levels is also about
    where a serialiser's own recursion becomes the next question, and
    `ElementTree.tostring` is recursive in CPython.
    """
    seen: set[int] = set()
    stack = [(root_element, 0, node) for node in reversed(roots)]
    while stack:
        parent_element, depth, node = stack.pop()
        if node["id"] in seen:
            continue
        seen.add(node["id"])
        element = build(parent_element, node)
        below = element if depth < MAX_MAP_DEPTH else parent_element
        stack.extend(
            (below, depth + 1, child)
            for child in reversed(node["children"])
        )


def _outline_numbers(roots: list[dict]) -> dict:
    """Every topic's place in the outline, `{node_id: "1.2"}` (MINDMAP_PLAN.md
    decision 17).

    A root is the map's subject and has no number; its children are 1, 2, 3
    and theirs 1.1, 1.2, each root counting from 1 again. No trailing dot:
    `- 2. Write` is an ordered list inside a bullet to every Markdown reader,
    which would draw the number twice. Sibling order is the tree's, which is
    `_sibling_key`'s and so the canvas's (`wbMapNumbers`). Iterative and
    seen-guarded, the rule every walk in this file keeps.
    """
    numbers: dict = {}
    seen: set = set()
    stack: list[tuple[str, dict]] = [("", root) for root in reversed(roots)]
    while stack:
        prefix, node = stack.pop()
        if node["id"] in seen:
            continue
        seen.add(node["id"])
        children = node.get("children") or []
        for position in range(len(children), 0, -1):
            child = children[position - 1]
            number = f"{prefix}.{position}" if prefix else str(position)
            numbers.setdefault(child["id"], number)
            stack.append((number, child))
    return numbers


#: A number at the start of an imported line, `1.2 Text`: what a numbered
#: map's Markdown export writes, and read back only when every topic's number
#: is its own place (`_strip_outline_numbers`).
_OUTLINE_NUMBER = re.compile(r"^(\d+(?:\.\d+)*)\s+(?=\S)")


def _strip_outline_numbers(roots: list[dict]) -> bool:
    """Take the numbers off an imported outline whose every topic starts with
    its own place in it, and say whether it did (decision 17).

    All or nothing, and only when they match: a topic called "2024 plan" in
    the first place is a name, not a number, and neither is a list numbered
    by hand in some other scheme. A file this app wrote matches by
    construction, so the map comes back numbered rather than with "1.1"
    typed into every topic, and exporting it again does not number it twice.
    """
    expected: list[tuple[dict, str]] = []
    stack: list[tuple[str, dict]] = [("", root) for root in roots]
    while stack:
        prefix, node = stack.pop()
        for position, child in enumerate(node.get("children") or [], start=1):
            number = f"{prefix}.{position}" if prefix else str(position)
            expected.append((child, number))
            stack.append((number, child))
    if not expected:
        return False
    for node, number in expected:
        found = _OUTLINE_NUMBER.match(node.get("text") or "")
        if not found or found.group(1) != number:
            return False
    for node, _ in expected:
        node["text"] = node["text"][_OUTLINE_NUMBER.match(node["text"]).end():]
    return True


def _export_markdown(title: str, roots: list[dict], numbered: bool = False) -> str:
    """`# Title`, then a two-space-per-level bullet outline.

    A reference node carries what it points at on the same line, `- Sources
    (note 12)`, because an outline of bare titles is a picture of the map
    rather than a working document: the ids are what let it be read back, or
    followed by hand.

    **Everything a node wears is deliberately dropped here**, and that is the
    one export where dropping it is right: this format's whole promise is
    that the file is an outline anybody can paste into anything. The two XML
    exports carry the style (`MAP_STYLE_FIELDS`), and a bold marker or an
    icon name smuggled into a bullet would come back in on the Markdown
    import as part of somebody's topic text.
    """
    lines = [f"# {title}"]
    rows = _outline_rows(roots)
    if rows:
        lines.append("")
    #: A numbered map's numbers (decision 17) are written into the line,
    #: after a task's box (which has to follow the marker to be one) and
    #: before the text, because a number is the one part of a map's look an
    #: outline pasted anywhere still means something by.
    numbers = _outline_numbers(roots) if numbered else {}
    for depth, node in rows:
        text = node["text"] or "(untitled)"
        suffix = ""
        if node["kind"] != MAP_TOPIC_KIND and node["ref_id"] is not None:
            suffix = f" ({node['kind']} {node['ref_id']})"
        box = _MARKDOWN_TASK_BOX.get((node.get("style") or {}).get("task"), "")
        number = numbers.get(node["id"])
        number = f"{number} " if number else ""
        lines.append(f"{'  ' * depth}- {box}{number}{text}{suffix}")
        note = (node.get("style") or {}).get("note")
        if note:
            lines.extend(_markdown_note_lines(note, depth))
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n"


def _export_text(roots: list[dict]) -> str:
    """The plain-text outline (§12.2 item 10): one topic per line, a tab per
    level, nothing else. No title line, because a plain outline has no word
    for one and a first line would come back as a topic: the file's name is
    the map's, and the import is sent it. No bullets, numbers, boxes or
    notes: this is the format for pasting into something that knows nothing
    about lists, and `_outline_from_paste` reads it back."""
    lines = [f"{chr(9) * depth}{node['text'] or '(untitled)'}" for depth, node in _outline_rows(roots)]
    return "\n".join(lines) + "\n"


#: **A note is an indented paragraph under its bullet** (MINDMAP_PLAN.md
#: decision 18): a blank line, the note at the bullet's content column, a
#: blank line. Every Markdown reader draws that as a paragraph inside the
#: list item, which is what a note behind a topic is, and
#: `_parse_markdown_outline` reads it back. A note line that would read as a
#: bullet or a heading is escaped with a backslash, which a reader draws as
#: the character and the import takes off again.
_MARKDOWN_NOTE_ESCAPE = re.compile(r"^([\\\-*+#])")


def _markdown_note_lines(note: str, depth: int) -> list[str]:
    pad = "  " * depth + "  "
    out = [""]
    for line in str(note).strip().splitlines():
        line = line.rstrip()
        out.append(pad + _MARKDOWN_NOTE_ESCAPE.sub(r"\\\1", line) if line else "")
    out.append("")
    return out


#: **A task is the one thing a node carries that Markdown has a word for**
#: (MINDMAP_PLAN.md decision 15): `- [ ]` and `- [x]` are the task-list items
#: every Markdown reader in common use draws as a checkbox, so writing them
#: keeps this file's promise (paste it anywhere) rather than breaking it the
#: way a bold marker or an icon name would, and `_parse_markdown_outline`
#: reads them back.
_MARKDOWN_TASK_BOX = {"open": "[ ] ", "done": "[x] "}


#: How this map's three line shapes are spelled in FreeMind's own `<edge
#: STYLE>` vocabulary, and back. FreeMind's list is `linear`, `bezier`,
#: `sharp_linear`, `sharp_bezier`, `horizontal` and `hide_edge`: `bezier` is
#: a curve, `linear` is a straight segment, and `horizontal` is the
#: right-angled run this map calls an elbow. Writing the native spelling
#: rather than a private attribute is what makes a map exported here open in
#: FreeMind, Freeplane and Coggle *looking* the way it did.
_FREEMIND_EDGE_STYLE = {"curve": "bezier", "elbow": "horizontal", "straight": "linear"}
#: And the ones with no native home, written as private attributes on the
#: node, the same device `_kind` and `_ref` already use here: an unknown
#: attribute is ignored by every other reader and survives a round trip
#: through this one. Per field, why it is here rather than in the format:
#:
#: - `icon`: FreeMind's `<icon BUILTIN>` is a closed enumeration of its own
#:   icon names, and this app's are Phosphor names. Writing a Phosphor name
#:   into BUILTIN would claim an icon FreeMind does not have, which renders
#:   as a gap there and does not come back as itself here.
#: - `edge_label`: FreeMind has no label on an edge at all. Freeplane grew
#:   one much later, in its own namespace, which FreeMind then refuses.
#: - `edge_dashed`: `<edge>` has STYLE, COLOR and WIDTH, and no dash.
#: - `align`: FreeMind aligns a node by which side of the root it sits on,
#:   not by a text alignment, so there is nothing to write it into.
#: - `edge_bend`/`edge_slide`: `<edge>` has no waypoint of any kind. Freeplane
#:   grew one much later as a `<edge>` child in its own namespace, spelled in
#:   absolute coordinates, which is the one spelling these two deliberately are
#:   not (see the fields' own comment): writing it would claim a shape in units
#:   the file cannot honour and would not come back as itself.
#: - `image`: FreeMind's own way to put a picture in a node is a
#:   `<richcontent>` body of HTML with an `<img>` in it, and the src this app
#:   has to write is `/media/...`, which resolves to a picture only on the
#:   install that holds the file. So the honest export is the url as a private
#:   attribute: this reader puts the picture back, and another reader is shown
#:   a topic with no broken image in it rather than one with.
_FREEMIND_PRIVATE = {
    #: `_shape` as well as the native `STYLE` below, not instead of it:
    #: FreeMind's node style is `bubble` or `fork` and has no third value, so
    #: STYLE alone cannot tell a pill from a box on the way back in. STYLE is
    #: what makes the file look right where it is opened; `_shape` is what
    #: makes it come back as itself.
    "shape": "_shape",
    "core": "_core",
    "spine": "_spine",
    "fill": "_fill",
    "effect": "_effect",
    "icon": "_icon",
    "edge_label": "_edge_label",
    "edge_dashed": "_edge_dashed",
    "edge_width": "_edge_width",
    "edge_arrow": "_edge_arrow",
    "edge_bend": "_edge_bend",
    "edge_slide": "_edge_slide",
    "edge_from": "_edge_from",
    "edge_to": "_edge_to",
    "image": "_image",
    "align": "_align",
    #: A task (decision 15): FreeMind's built-in icons have a tick but no
    #: empty box, so an open task has no native spelling; private, like the
    #: rest of this list.
    "task": "_task",
    #: A note (decision 18). FreeMind's own is `<richcontent TYPE="NOTE">`,
    #: whose body is HTML, which this file neither writes nor reads (see
    #: `_parse_freemind`); the attribute keeps the text plain both ways.
    "note": "_note",
    #: Decisions 19 and 20: FreeMind's own `<cloud>` is one shape with no
    #: label, and it has no summary at all, so both ride as private ones.
    **{f: f"_{f}" for f in ("boundary", "boundary_label", "summary", "summary_span", "branch_layout", "callout", "labels", "stamps")},
    #: Markers (decision 34): neither format has a place for them that the
    #: other reads, so all four ride as private attributes.
    **{f: f"_{f}" for f in ("priority", "progress", "flag", "markers", "due", "due_time", "start")},
}
#: OPML 2.0 defines `text`, `type`, `url`, `isComment`, `isBreakpoint`,
#: `created` and `category` and nothing else, so `url` is the only native
#: home any of these have and the rest ride as private attributes. Reading a
#: map's look back out of an OPML file is then exact, and an OPML reader that
#: knows none of them still sees the outline it came for.
_OPML_PRIVATE = {
    "shape": "_shape",
    "core": "_core",
    "spine": "_spine",
    "fill": "_fill",
    "effect": "_effect",
    "bold": "_bold",
    "italic": "_italic",
    "font_size": "_font_size",
    "align": "_align",
    "icon": "_icon",
    "edge_label": "_edge_label",
    "edge_style": "_edge_style",
    "edge_dashed": "_edge_dashed",
    "edge_width": "_edge_width",
    "edge_arrow": "_edge_arrow",
    "edge_bend": "_edge_bend",
    "edge_slide": "_edge_slide",
    "edge_from": "_edge_from",
    "edge_to": "_edge_to",
    "image": "_image",
    "task": "_task",
    #: `_note` is the spelling OmniOutliner and Workflowy already write, so
    #: this one reaches another outliner as a note rather than being dropped.
    "note": "_note",
    **{f: f"_{f}" for f in ("boundary", "boundary_label", "summary", "summary_span", "branch_layout", "callout", "labels", "stamps")},
    #: Markers (decision 34): neither format has a place for them that the
    #: other reads, so all four ride as private attributes.
    **{f: f"_{f}" for f in ("priority", "progress", "flag", "markers", "due", "due_time", "start")},
}


def _xml_attribute(value) -> str:
    """A style value as an XML attribute. `True` is written as the string
    every XML format in this area uses, and the bool that comes back through
    `_clean_import_style` is Pydantic's own lax parse of it."""
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (list, tuple)):
        return ",".join(str(part) for part in value)
    if isinstance(value, dict):
        return ",".join(f"{key}:{count}" for key, count in value.items())
    return str(value)


def _export_opml(
    title: str, roots: list[dict], cross_links: list[dict] | None = None, numbered: bool = False
) -> str:
    """OPML 2.0: the interchange format every mindmapper reads.

    Built with ElementTree rather than by formatting strings, so that a topic
    containing `&`, `<` or a quote is escaped by something that knows the
    rules: which hand-written XML reliably gets wrong on the first
    apostrophe.
    """
    import xml.etree.ElementTree as ET

    opml = ET.Element("opml", {"version": "2.0"})
    head = ET.SubElement(opml, "head")
    ET.SubElement(head, "title").text = title
    body = ET.SubElement(opml, "body")
    links_from: dict = {}
    labels_from: dict = {}
    for link in cross_links or []:
        links_from.setdefault(link.get("from_id"), []).append(link.get("to_id"))
        labels_from.setdefault(link.get("from_id"), []).append(str(link.get("label") or ""))
    #: A numbered map (decision 17): `_number` on each outline, private like
    #: `_kind` and `_task`, so another reader keeps clean text and this one
    #: reads the map back numbered.
    numbers = _outline_numbers(roots) if numbered else {}

    def build(parent_element, node: dict):
        attrs = {"text": node["text"] or "(untitled)"}
        if node["id"] in numbers:
            attrs["_number"] = numbers[node["id"]]
        if node["kind"] != MAP_TOPIC_KIND:
            # `_kind`/`_ref`, not `type`/`ref`: OPML's own `type` attribute
            # already means something else (how a reader should treat the
            # outline), and quietly redefining it would make this file wrong
            # for every other tool that opens it. An unknown attribute is
            # ignored by other readers and survives a round trip through
            # this one.
            attrs["_kind"] = node["kind"]
            if node["ref_id"] is not None:
                attrs["_ref"] = str(node["ref_id"])
        style = node.get("style") or {}
        if style.get("link"):
            # `url` is OPML 2.0's own attribute for where an outline points,
            # and it is the one thing on this list another reader will do
            # something useful with. `type="link"` is deliberately *not* set
            # alongside it: that would say the outline *is* a link rather
            # than a topic that has one, and a reader honouring it would drop
            # the children hanging underneath.
            attrs["url"] = style["link"]
        for field, attribute in _OPML_PRIVATE.items():
            if field in style:
                attrs[attribute] = _xml_attribute(style[field])
        if node.get("color"):
            attrs["_color"] = str(node["color"])
        #: **A cross-link, in the only place an outline has for one**
        #: (MINDMAP_PLAN.md §13d). OPML is strictly a tree: there is no
        #: element for an edge that is not containment, and inventing one
        #: would make the file wrong for every other reader. So the same
        #: bargain `_kind` and `_ref` already struck: a private attribute,
        #: ignored by everything else, read back by this file. `_id` on every
        #: outline and `_links` on the one the link starts at, space
        #: separated because an outline may start several.
        attrs["_id"] = _export_node_id(node["id"])
        outgoing = links_from.get(node["id"])
        if outgoing:
            attrs["_links"] = " ".join(_export_node_id(end) for end in outgoing)
            #: The labels, in the same order, only when one is set (gap 12:
            #: a labelled link between two roots came home unlabelled).
            if any(labels_from[node["id"]]):
                attrs["_link_labels"] = json.dumps(labels_from[node["id"]], ensure_ascii=False)
        return ET.SubElement(parent_element, "outline", attrs)

    _export_tree(body, roots, build)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + ET.tostring(opml, encoding="unicode")
        + "\n"
    )


#: **A cross-link's id in the two XML exports** (MINDMAP_PLAN.md §13d).
#: FreeMind's own ids are the string `ID_` and a number, and its
#: `<arrowlink DESTINATION>` points at one; the OPML export uses the same
#: spelling in a private `_id` so that one reader in this file understands
#: both. Derived from the object id rather than counted, so the same map
#: exports to the same file twice and a diff of two exports is the changes.
def _export_node_id(node_id: object) -> str:
    return f"ID_{node_id}"


def _freemind_attributes(node: dict, style: dict) -> dict:
    """The attributes of one FreeMind `<node>`: its text, kind and reference,
    link, this app's private style fields and the box shape."""
    attrs = {"TEXT": node["text"] or "(untitled)"}
    if node["kind"] != MAP_TOPIC_KIND:
        attrs["_kind"] = node["kind"]
        if node["ref_id"] is not None:
            attrs["_ref"] = str(node["ref_id"])
    if style.get("link"):
        attrs["LINK"] = style["link"]
    for field, attribute in _FREEMIND_PRIVATE.items():
        if field in style:
            attrs[attribute] = _xml_attribute(style[field])
    if style.get("shape"):
        # FreeMind's own two: `fork` is a label on the line with no box
        # around it, which is exactly this map's "plain", and `bubble` is
        # the boxed node every other shape here is a variety of.
        attrs["STYLE"] = "fork" if style["shape"] == "none" else "bubble"
    return attrs


def _freemind_font(style: dict) -> dict:
    """A node's `<font>` attributes. NAME is left off rather than filled with
    "SansSerif": this app sets no font family, and writing one would be a
    claim about the map that nobody here made."""
    font = {}
    if style.get("bold"):
        font["BOLD"] = "true"
    if style.get("italic"):
        font["ITALIC"] = "true"
    if style.get("font_size"):
        font["SIZE"] = str(int(style["font_size"]))
    return font


def _freemind_edge(node: dict, style: dict) -> dict:
    """A node's `<edge>` attributes: line style, width and the node colour."""
    edge = {}
    if style.get("edge_style") in _FREEMIND_EDGE_STYLE:
        edge["STYLE"] = _FREEMIND_EDGE_STYLE[style["edge_style"]]
    #: FreeMind's own `<edge WIDTH>`, alongside the private `_edge_width`
    #: that carries the step back: WIDTH is a number of pixels or the word
    #: `thin`, which is a lossy home for a three-step scale, so it is
    #: written for the reader that opens the file and read back from the
    #: private attribute. Same bargain as `STYLE` and `_shape` above.
    if style.get("edge_width") == "thin":
        edge["WIDTH"] = "thin"
    elif style.get("edge_width") == "thick":
        edge["WIDTH"] = "4"
    if node.get("color"):
        # A map's node colour paints the spine down the node's leading
        # edge and the line coming into it (§12.0, "a node carries its
        # colour on its own card"), which is `<edge COLOR>` here rather
        # than `<node COLOR>`: FreeMind's node colour is its *text*
        # colour, and writing it there would recolour the words.
        edge["COLOR"] = str(node["color"])
    return edge


def _export_freemind(title: str, roots: list[dict], cross_links: list[dict] | None = None) -> str:
    """FreeMind `.mm`: the other format every mindmapper reads, and the one
    Coggle, Freeplane, XMind and MindMeister all import (§4's list).

    **A `.mm` file has exactly one root.** A map here may have several, which
    is a real shape (two unrelated trunks on one board), so a multi-root map is
    exported under one node named after the map (marked `_wrapper`, so this
    app's import takes it off again) rather than as several documents or as a
    file only this app can read back. A single-root map is written as itself,
    so the common case round-trips unchanged; its name rides on `<map
    _title>` when it differs from the central topic.

    `_kind`/`_ref` ride along for the same reason they do in the OPML export:
    FreeMind ignores attributes it does not know, and they are what lets a
    reference node come back as a reference node rather than as a topic.
    """
    import xml.etree.ElementTree as ET

    document = ET.Element("map", {"version": "1.0.1"})
    elements: dict = {}

    def build(parent_element, node: dict):
        style = node.get("style") or {}
        attrs = _freemind_attributes(node, style)
        attrs["ID"] = _export_node_id(node["id"])
        element = ET.SubElement(parent_element, "node", attrs)
        elements[node["id"]] = element
        # `<font>` and `<edge>` are FreeMind's own children of a node, and
        # they are written only when something was actually chosen: an empty
        # `<font/>` on every node would triple the size of a plain map's file
        # and say nothing.
        font = _freemind_font(style)
        if font:
            ET.SubElement(element, "font", font)
        edge = _freemind_edge(node, style)
        if edge:
            ET.SubElement(element, "edge", edge)
        return element

    under = document
    if len(roots) != 1:
        #: `_wrapper` marks the trunk this export invented, so the import
        #: (`_parse_freemind`) takes it back off and the map's own roots come
        #: back as roots. FreeMind ignores the attribute and draws the trunk.
        under = ET.SubElement(document, "node", {"TEXT": title, "_wrapper": "map"})
    elif title and title != (roots[0].get("text") or ""):
        #: A one-root map whose name differs from its central topic keeps its
        #: name in a private attribute on `<map>` (audit FEAT-01): the root
        #: node is the central topic now, so it can no longer carry the name.
        document.set("_title", title)
    _export_tree(under, roots, build)
    #: **The cross-links, in FreeMind's own element** (MINDMAP_PLAN.md §13d).
    #: `<arrowlink>` is a child of the node the link starts at and names the
    #: node it ends at, which is exactly the shape a link sketch already has,
    #: so this is a spelling change rather than a model change. Written after
    #: the tree because a link can point backwards as easily as forwards and
    #: the element it points at has to exist; skipped when either end is not
    #: on this map, which `_cross_links` already guarantees but a file this
    #: function is handed twice should not depend on.
    for link in cross_links or []:
        source = elements.get(link.get("from_id"))
        if source is None or link.get("to_id") not in elements:
            continue
        arrow = {"DESTINATION": _export_node_id(link["to_id"]), "ENDARROW": "Default"}
        if link.get("label"):
            arrow["MIDDLE_LABEL"] = _xml_attribute(link["label"])
        ET.SubElement(source, "arrowlink", arrow)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + ET.tostring(document, encoding="unicode")
        + "\n"
    )


#: **XMind's structures** (canvasdepth2, MINDMAP_PLAN "canvasdepth, ranked"
#: row 4): a layout here and the `structureClass` XMind writes for it, both
#: ways. The logic chart and the sideways tree are one structure in XMind.
XMIND_STRUCTURES = {
    "tree-right": "org.xmind.ui.logic.right",
    "logic-right": "org.xmind.ui.logic.right",
    "tree-left": "org.xmind.ui.logic.left",
    "tree-both": "org.xmind.ui.map.unbalanced",
    "tree-down": "org.xmind.ui.org-chart.down",
    "tree-table": "org.xmind.ui.treetable",
    "timeline": "org.xmind.ui.timeline.horizontal",
    "fishbone": "org.xmind.ui.fishbone.rightHeaded",
    "radial": "org.xmind.ui.map.clockwise",
}
XMIND_LAYOUTS = {cls: layout for layout, cls in reversed(list(XMIND_STRUCTURES.items()))}


def _xmind_topic(node: dict, ids: dict) -> dict:
    """One topic as XMind Zen's `content.json` writes it: its title, notes,
    link, labels, callout, priority and task markers and its branch's
    structure; what XMind has no place for is left out."""
    style = node.get("style") or {}
    topic: dict = {"id": ids.setdefault(node["id"], f"mm{node['id']}"), "class": "topic", "title": node["text"] or ""}
    if style.get("note"):
        topic["notes"] = {"plain": {"content": style["note"]}}
    if style.get("link"):
        topic["href"] = style["link"]
    if style.get("labels"):
        topic["labels"] = list(style["labels"])
    markers = [{"markerId": f"priority-{style['priority']}"}] if style.get("priority") else []
    if style.get("task"):
        markers.append({"markerId": "task-done" if style["task"] == "done" else "task-start"})
    if markers:
        topic["markers"] = markers
    if style.get("branch_layout") in XMIND_STRUCTURES:
        topic["structureClass"] = XMIND_STRUCTURES[style["branch_layout"]]
    children: dict = {}
    if node.get("children"):
        children["attached"] = [_xmind_topic(child, ids) for child in node["children"]]
    if style.get("callout"):
        children["callout"] = [{"id": f"{topic['id']}c", "class": "topic", "title": style["callout"]}]
    if children:
        topic["children"] = children
    return topic


def _export_xmind(title: str, roots: list[dict], cross_links: list[dict], layout: str) -> bytes:
    """An XMind (Zen and later) `.xmind`: a zip holding `content.json`, one
    sheet whose root is the map's one centre (several trunks go under one
    named after the map, as the FreeMind export does), its layout as the
    root's structure, and the cross-links as relationships."""
    import io
    import zipfile

    ids: dict = {}
    if len(roots) == 1:
        root = _xmind_topic(roots[0], ids)
    else:
        root = {"id": "mmroot", "class": "topic", "title": title,
                "children": {"attached": [_xmind_topic(node, ids) for node in roots]}}
    root["structureClass"] = XMIND_STRUCTURES.get(layout, "org.xmind.ui.map.unbalanced")
    sheet = {"id": "mmsheet", "class": "sheet", "title": title, "rootTopic": root}
    relationships = [
        {"id": f"mmrel{i}", "end1Id": ids[link["from_id"]], "end2Id": ids[link["to_id"]], "title": link["label"]}
        for i, link in enumerate(cross_links)
        if link["from_id"] in ids and link["to_id"] in ids
    ]
    if relationships:
        sheet["relationships"] = relationships
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("content.json", json.dumps([sheet], ensure_ascii=False))
        archive.writestr("metadata.json", json.dumps({"creator": {"name": "Tessellate"}}))
        archive.writestr("manifest.json", json.dumps({"file-entries": {"content.json": {}, "metadata.json": {}}}))
    return out.getvalue()


#: What each export format is called on the way out: the media type a browser
#: should treat it as, and the extension the file has to have. A `.md` file
#: holding OPML is a file nothing will open.
EXPORT_FORMATS = {
    "markdown": ("text/markdown; charset=utf-8", "md"),
    "opml": ("text/x-opml; charset=utf-8", "opml"),
    "freemind": ("application/x-freemind; charset=utf-8", "mm"),
    "text": ("text/plain; charset=utf-8", "txt"),
    #: A zip, so no charset.
    "xmind": ("application/vnd.xmind.workbook", "xmind"),
}


@router.get("/boards/{board_id}/export")
def export_board(board_id: int, format: str = "markdown", db: Session = Depends(get_session)):
    """A map as an indented Markdown outline, or as OPML.

    Returned as a text response with a filename rather than as JSON: what a
    caller wants from this is a file, and a JSON envelope means every client
    writes the same unwrapping code before it can save one.
    """
    from fastapi.responses import Response

    if format not in EXPORT_FORMATS:
        raise HTTPException(
            status_code=422,
            detail="Pick one of these export formats: "
            + ", ".join(sorted(EXPORT_FORMATS))
            + ".",
        )
    entry = _board_entry(db, board_id)
    title = extract_title(entry.content) or entry.content.strip()[:40] or f"Note {board_id}"
    roots = _build_tree(db, _map_objects(db, board_id))
    #: **An export of a themed map looks like the map** (MINDMAP_PLAN.md
    #: §13e). A theme is resolved at paint time rather than written onto each
    #: node, which is what keeps it safe to change; but none of the three
    #: formats has a place to put a map-level look, so a file written from
    #: the stored styles alone would come out plainer than the map it was
    #: taken from. Resolved here and nowhere else: `/tree` deliberately keeps
    #: reporting what each node actually carries, because that is what the
    #: strip has to show as set or unset.
    #: Every map now, not only a themed one, because a pin is written as the
    #: absence it means on any map (`_without_pins`). Seen-guarded: a ring
    #: in `parent_id` stays a ring in `children` here, and an unguarded walk
    #: of it never ends (`test_a_ring_in_the_tree_does_not_hang_an_export`).
    theme = _board_theme(entry)
    stack = list(roots)
    styled: set[int] = set()
    while stack:
        node = stack.pop()
        if id(node) in styled:
            continue
        styled.add(id(node))
        node["style"] = _without_pins(_themed_style(node.get("style") or {}, theme))
        stack.extend(node.get("children") or [])
    media, suffix = EXPORT_FORMATS[format]
    #: **Markdown carries no cross-links, deliberately** (MINDMAP_PLAN.md
    #: §13d's decision). This format's whole promise is in `_export_markdown`'s
    #: own docstring, that the file is an outline anybody can paste into
    #: anything, and everything a node wears is already dropped here for that
    #: reason. A "Cross-links" section after the outline would also be read
    #: straight back in by `_parse_markdown_outline`, which reads indentation
    #: and nothing else, so one map's two links would come back as two topics.
    numbered = _board_numbered(entry)
    if format == "markdown":
        text = _export_markdown(title, roots, numbered)
    elif format == "text":
        text = _export_text(roots)
    elif format in ("opml", "xmind"):
        links = _cross_links(db, board_id, {node["id"] for _, node in _outline_rows(roots)})
        writers = {
            "opml": lambda: _export_opml(title, roots, links, numbered),
            "xmind": lambda: _export_xmind(title, roots, links, _board_settings(entry)[1]),
        }
        text = writers[format]()
    else:
        #: Read only for the two formats that can carry them, so a Markdown
        #: export does not pay for a scan of every sketch on the board to find
        #: something it is going to drop.
        links = _cross_links(db, board_id, {node["id"] for _, node in _outline_rows(roots)})
        text = _export_freemind(title, roots, links)
    # The filename is built from the board's id, never from its title: a
    # title is free text, and a Content-Disposition header is exactly where
    # free text becomes a header-injection question nobody wants to answer
    # twice.
    return Response(
        content=text,
        media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="board-{int(board_id)}.{suffix}"'
        },
    )
