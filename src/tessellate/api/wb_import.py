"""A map in: the FreeMind, OPML, XMind and markdown readers and the placing of what they read.

Moved whole from `routes_whiteboard.py` (audit AR3, gods-2): the code is unchanged, and
`routes_whiteboard` re-exports every name here that anything reads. Imports run one way,
down the layer list in `routes_whiteboard.py`'s docstring, never back to `routes_whiteboard`.
"""

from __future__ import annotations

import json
import logging
import re

from pydantic import BaseModel, Field, ValidationError, field_validator
from fastapi import HTTPException
from sqlalchemy.orm import Session
from tessellate.core.database import WhiteboardObject, WhiteboardSketch
from tessellate.api.wb_tree import MAP_COL, MAP_ROW, MAX_IMPORT_CHARS, MAX_IMPORT_DEPTH, MAX_IMPORT_NODES
from tessellate.api.wb_model import MAP_TOPIC_KIND, MAX_OBJECT_TEXT_CHARS, MAX_TOPIC_NOTE_CHARS, WhiteboardObjectData
from tessellate.api.wb_export import XMIND_LAYOUTS, _FREEMIND_EDGE_STYLE, _FREEMIND_PRIVATE, _OPML_PRIVATE

#: The export's tables read backwards: FreeMind's edge STYLE to this map's line
#: shape, and a Markdown task box to its state.
_FREEMIND_EDGE_STYLE_BACK = {value: key for key, value in _FREEMIND_EDGE_STYLE.items()}
_MARKDOWN_TASK_ITEM = re.compile(r"^\[([ xX])\]\s+")

class MapImport(BaseModel):
    format: str
    content: str = Field(max_length=MAX_IMPORT_CHARS)
    #: What to call the new map. Omitted means "whatever the document calls
    #: itself", an OPML `<head><title>`, or a Markdown `#` heading.
    name: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("format")
    @classmethod
    def _known_format(cls, value: str) -> str:
        if value not in IMPORT_FORMATS:
            raise ValueError(
                f"Unknown import format {value!r}: expected one of "
                + ", ".join(sorted(IMPORT_FORMATS))
            )
        return value


#: The formats `import_board` reads. Markdown and OPML both round-trip with
#: the exports above; FreeMind `.mm` is the format Coggle, Freeplane, XMind and
#: MindMeister all write, which is what section 4's list meant by "an existing
#: map can come in".
IMPORT_FORMATS = ("markdown", "opml", "freemind", "xmind", "text")


def _parse_xml_document(content: str, label: str):
    """The XML door, for both formats that come through it.

    **A document type declaration is refused outright**, before the parser
    ever sees the string. `xml.etree` does not resolve *external* entities,
    but it does expand internal ones, which is the billion-laughs shape: a
    dozen nested entity definitions turn a 1KB file into gigabytes of memory
    inside the parse call, where no size cap on the way in can see it coming.
    Nothing else in this app parses XML from anywhere, and no real OPML or
    FreeMind file needs a DTD: so the door refuses one, which is a check that
    stays correct even if the parser behind it is swapped later.

    The parser behind it is `defusedxml`, not the stdlib: the string check
    above is belt, this is braces. defusedxml refuses entity declarations at
    the parser level, and it is also the only shape CodeQL's `py/xml-bomb`
    query accepts as safe, the stdlib call was flagged as a high-severity
    alert on this PR even with the guard in front of it.

    One function rather than one per format because a second copy of a
    security check is a second copy that can drift: the FreeMind import
    arrived after the OPML one and is exactly where the DOCTYPE guard would
    otherwise have been quietly left out.
    """
    try:
        from defusedxml import ElementTree as ET
        from defusedxml.common import DefusedXmlException
    except ImportError as exc:  # a hand-rolled install that skipped requirements.txt
        raise HTTPException(
            status_code=503,
            detail=(
                f"{label} import needs a safe XML reader (the defusedxml package), "
                "which is missing from this install. Install it, then restart Tessellate."
            ),
        ) from exc

    lowered = content.lower()
    if "<!doctype" in lowered or "<!entity" in lowered:
        raise HTTPException(
            status_code=422,
            detail=(
                f"That {label} file declares a document type, which is not allowed. "
                "Remove that line and try again."
            ),
        )
    try:
        return ET.fromstring(content)
    except (ET.ParseError, DefusedXmlException) as exc:
        # The parser's own text names a line and column of the file, which is
        # for the log; the person needs to know the file is the problem.
        logging.getLogger("tessellate.whiteboard").warning("couldn't parse a %s file", label, exc_info=True)
        raise HTTPException(
            status_code=422,
            detail=f"That isn't valid {label}. Check that the file is complete and try again.",
        ) from exc


#: A colour arriving from a file is held to a hex literal, which is stricter
#: than the object PUT path (`max_length=20`, any string) on purpose. This
#: value is written into a CSS custom property on the node, and the door a
#: *file somebody was sent* comes through is not the door to widen: every
#: colour this app itself writes is a `<input type="color">` value, so the
#: rule costs nothing real and refuses everything else.
_IMPORT_COLOUR = re.compile(r"^#[0-9a-fA-F]{3,8}$")


def _clean_import_style(raw: dict) -> dict:
    """The style attributes read off an imported node, validated one at a
    time, with anything that does not pass simply left out.

    **Validated by `WhiteboardObjectData` itself, field by field.** These
    values come off an XML attribute in a file from somewhere else, and they
    are written straight into `data`, which is the same blob the object PUT
    endpoint validates: so the rules that endpoint enforces (a Phosphor icon
    name and nothing else, an http/https/mailto link and nothing else, a font
    size in range, one of three line shapes) have to hold here too, and a
    second hand-written copy of them is a second copy that drifts. One field
    per `model_validate` call rather than the whole dict at once, because a
    file with one bad attribute should lose that attribute, not every
    attribute it had.
    """
    clean: dict = {}
    for field, value in raw.items():
        if value is None or value == "":
            continue
        if field == "color":
            text = str(value).strip()
            if _IMPORT_COLOUR.match(text):
                clean[field] = text
            continue
        try:
            checked = WhiteboardObjectData.model_validate({field: value})
        except ValidationError:
            continue
        settled = getattr(checked, field, None)
        if settled is not None and settled is not False:
            clean[field] = settled
    return clean


def _freemind_style(element) -> dict:
    """What a `<node>` wears, read back out of the shape `_export_freemind`
    writes: FreeMind's own `LINK`, `<font>` and `<edge>`, and the private
    attributes for the four things FreeMind has nowhere to put."""
    raw: dict = {"link": element.get("LINK")}
    for field, attribute in _FREEMIND_PRIVATE.items():
        raw[field] = element.get(attribute)
    if not raw.get("shape") and element.get("STYLE") == "fork":
        # A `.mm` from somewhere else has no `_shape`, and `fork` is the one
        # of FreeMind's two styles that means something here. `bubble` is left
        # alone: it is the boxed node, which is this map's own default, and
        # reading it as a shape would put a field on every imported node.
        raw["shape"] = "none"
    font = element.find("font")
    if font is not None:
        raw["bold"] = font.get("BOLD")
        raw["italic"] = font.get("ITALIC")
        raw["font_size"] = font.get("SIZE")
    edge = element.find("edge")
    if edge is not None:
        raw["edge_style"] = _FREEMIND_EDGE_STYLE_BACK.get(edge.get("STYLE") or "")
        raw["color"] = edge.get("COLOR")
    return _clean_import_style(raw)


def _opml_style(element) -> dict:
    """The same, for an `<outline>`: OPML's `url`, and the private attributes
    for everything OPML 2.0 has no word for."""
    raw: dict = {"link": element.get("url"), "color": element.get("_color")}
    for field, attribute in _OPML_PRIVATE.items():
        raw[field] = element.get(attribute)
    return _clean_import_style(raw)


#: The cross-links starting at one imported element, as the ids the file
#: itself used (MINDMAP_PLAN.md §13d). Bounded, because this is a file
#: somebody handed us: a node with ten thousand arrowlinks is either a
#: generated file nobody meant to import or an attempt to make the import
#: write ten thousand rows per node.
MAX_IMPORT_LINKS_PER_NODE = 64


def _import_link_targets(element, tag: str, attribute: str) -> list[str]:
    return [target for target, _label in _import_links(element, tag, attribute)]


def _import_links(element, tag: str, attribute: str) -> list[tuple[str, str]]:
    """`(target, label)` per link; FreeMind's label is `MIDDLE_LABEL`."""
    out: list[tuple[str, str]] = []
    for link in element.findall(tag):
        target = (link.get(attribute) or "").strip()
        if target:
            out.append((target, (link.get("MIDDLE_LABEL") or "").strip()[:MAX_OBJECT_TEXT_CHARS]))
        if len(out) >= MAX_IMPORT_LINKS_PER_NODE:
            break
    return out


def _opml_link_labels(raw: str | None, count: int) -> list[str]:
    """`_link_labels` is JSON this app wrote; anything else in the attribute
    (a file somebody edited) is no labels rather than an error."""
    try:
        labels = json.loads(raw or "[]")
    except ValueError:
        return []
    if not isinstance(labels, list):
        return []
    return [str(x).strip()[:MAX_OBJECT_TEXT_CHARS] for x in labels[:count]]


def _parse_freemind(content: str) -> tuple[str, list[dict]]:
    """FreeMind `.mm` in, `(title, nested {text, children})` out.

    The format is one `<node TEXT="...">` inside another, and the document's
    single root node is the map's central topic, the shape Freeplane, XMind
    and Coggle export; its text also names the map unless `<map _title>`
    does. The one exception is the trunk `_export_freemind` writes over a
    multi-root map, marked `_wrapper`, which is taken back off. A file with
    several top-level nodes (not legal FreeMind, but files are files) keeps
    all of them and takes no title from them.

    Text can also live in a `<richcontent>` element rather than in `TEXT`.
    That body is HTML, and rendering someone else's HTML into a node is not a
    thing this import is going to do: such a node comes in unlabelled rather
    than with its markup as its label.
    """
    root = _parse_xml_document(content, "FreeMind")
    counted = [0]

    def walk(element, depth: int) -> list[dict]:
        out: list[dict] = []
        if depth >= MAX_IMPORT_DEPTH:
            return out
        for child in element.findall("node"):
            counted[0] += 1
            if counted[0] > MAX_IMPORT_NODES:
                raise HTTPException(
                    status_code=422,
                    detail=f"That outline has more than {MAX_IMPORT_NODES} nodes: split it up first.",
                )
            text = (child.get("TEXT") or child.get("text") or "").strip()
            out.append(
                {
                    "text": text[:MAX_OBJECT_TEXT_CHARS],
                    "style": _freemind_style(child),
                    #: The file's own id and the arrowlinks that start here
                    #: (MINDMAP_PLAN.md §13d). Carried as written rather than
                    #: resolved, because nothing has an object id yet: the
                    #: import resolves them once every node has been placed.
                    "ref": (child.get("ID") or "").strip(),
                    "links": _import_link_targets(child, "arrowlink", "DESTINATION"),
                    "link_labels": [label for _t, label in _import_links(child, "arrowlink", "DESTINATION")],
                    "children": walk(child, depth + 1),
                }
            )
        return out

    tops = root.findall("node")
    named = (root.get("_title") or "").strip()
    if len(tops) == 1 and tops[0].get("_wrapper") == "map":
        # The trunk `_export_freemind` invented for a multi-root map: its text
        # is the map's name and its children are the map's own roots.
        title = (tops[0].get("TEXT") or "").strip()
        return named or title, walk(tops[0], 0)
    if len(tops) == 1:
        # The one legal shape, and **the single root is the central topic**
        # (audit FEAT-01, 2026-10-05; this reversed the older reading, which
        # took it as the map's name and dropped it, so every `.mm` from
        # Freeplane or XMind arrived as loose trunks). The map is named after
        # it unless the file names itself.
        title = (tops[0].get("TEXT") or "").strip()
        return named or title, walk(root, 0)
    return named, walk(root, 0)


def _parse_opml(content: str) -> tuple[str, list[dict]]:
    """OPML in, `(title, nested {text, children})` out.

    **A document type declaration is refused outright**, before the parser
    ever sees the string. `xml.etree` does not resolve *external* entities,
    but it does expand internal ones, which is the billion-laughs shape: a
    dozen nested entity definitions turn a 1KB file into gigabytes of memory
    inside the parse call, where no size cap on the way in can see it coming.
    Both guards live in `_parse_xml_document`, which is the one XML door in
    this app: see it for the billion-laughs reasoning and for why the parser
    is defusedxml rather than the stdlib.
    """
    root = _parse_xml_document(content, "OPML")

    title = ""
    head_title = root.find("./head/title")
    if head_title is not None and head_title.text:
        title = head_title.text.strip()

    body = root.find("./body")
    if body is None:
        # Some exporters leave out <body> and hang the outlines off the root.
        body = root

    counted = [0]

    def walk(element, depth: int) -> list[dict]:
        out: list[dict] = []
        if depth >= MAX_IMPORT_DEPTH:
            return out
        for child in element.findall("outline"):
            counted[0] += 1
            if counted[0] > MAX_IMPORT_NODES:
                raise HTTPException(
                    status_code=422,
                    detail=f"That outline has more than {MAX_IMPORT_NODES} nodes: split it up first.",
                )
            text = (child.get("text") or child.get("title") or "").strip()
            out.append(
                {
                    "text": text[:MAX_OBJECT_TEXT_CHARS],
                    "style": _opml_style(child),
                    "ref": (child.get("_id") or "").strip(),
                    "links": (child.get("_links") or "").split(),
                    "link_labels": _opml_link_labels(child.get("_link_labels"), len((child.get("_links") or "").split())),
                    "numbered": bool((child.get("_number") or "").strip()),
                    "children": walk(child, depth + 1),
                }
            )
        return out

    return title, walk(body, 0)


#: An XMind file's map, uncompressed, at most: a map of MAX_IMPORT_NODES
#: topics is well under this, and a zip that says it unpacks to more is a
#: zip bomb, not a mind map.
MAX_XMIND_JSON_BYTES = 8_000_000


def _xmind_style(topic: dict) -> dict:
    """What an XMind topic carries that a topic here can hold: its plain
    notes, link, labels, first callout, priority and task markers and its
    branch's structure (canvasdepth2). Validated by `_clean_import_style`."""
    labels = topic.get("labels")
    callouts = (topic.get("children") or {}).get("callout")
    first = callouts[0] if isinstance(callouts, list) and callouts else {}
    return {
        "note": ((topic.get("notes") or {}).get("plain") or {}).get("content"),
        #: `_clean_import_style` holds the link to http, https and mailto.
        "link": topic.get("href"),
        "labels": [str(label)[:30].replace(",", " ") for label in labels[:8]] if isinstance(labels, list) else None,
        "callout": str(first.get("title") or "")[:200] if isinstance(first, dict) else None,
        **_xmind_marks(topic.get("markers")),
        "branch_layout": XMIND_LAYOUTS.get(str(topic.get("structureClass") or "")),
    }


def _xmind_marks(markers) -> dict:
    """XMind's `priority-N` and `task-*` markers as a priority and a task."""
    marks = [str(m.get("markerId") or "") for m in markers or [] if isinstance(m, dict)]
    priority = next((int(m[9:]) for m in marks if re.fullmatch(r"priority-[1-5]", m)), None)
    task = None
    if any(m.startswith("task-") for m in marks):
        task = "done" if "task-done" in marks else "open"
    return {"priority": priority, "task": task}


def _parse_xmind(content: str) -> tuple[str, list[dict]]:
    """An XMind (Zen and later) `.xmind` in, `(title, [the central topic])` out.

    The file is a zip; the client sends it base64 encoded. Its map is
    `content.json`: a list of sheets, each with a `rootTopic` whose children
    are `children.attached`. The first sheet comes in, its central topic as
    the map's root (and its name), the rest under it as they were in XMind.
    A topic's plain notes come in as
    its note. XMind 8's older `content.xml` is refused with a sentence saying
    how to get the newer file, rather than guessed at.
    """
    import base64
    import binascii
    import io
    import zipfile

    try:
        raw = base64.b64decode(content, validate=True)
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except (binascii.Error, ValueError, zipfile.BadZipFile) as err:
        raise HTTPException(status_code=422, detail="That is not an XMind file (it should be a .xmind archive).") from err
    names = set(archive.namelist())
    if "content.json" not in names:
        detail = (
            "That XMind file is in the older XMind 8 format. Open it in XMind and save it again, then import it."
            if "content.xml" in names
            else "That XMind file has no map in it."
        )
        raise HTTPException(status_code=422, detail=detail)
    info = archive.getinfo("content.json")
    if info.file_size > MAX_XMIND_JSON_BYTES:
        raise HTTPException(status_code=422, detail="That XMind map is too large to import: split it up first.")
    try:
        sheets = json.loads(archive.read("content.json").decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as err:
        raise HTTPException(status_code=422, detail="That XMind file's map could not be read.") from err
    sheet = sheets[0] if isinstance(sheets, list) and sheets else {}
    root = sheet.get("rootTopic") if isinstance(sheet, dict) else None
    if not isinstance(root, dict):
        raise HTTPException(status_code=422, detail="That XMind file has no map in it.")
    counted = [0]

    def walk(topic: dict, depth: int) -> list[dict]:
        out: list[dict] = []
        if depth >= MAX_IMPORT_DEPTH:
            return out
        children = (topic.get("children") or {}).get("attached") or []
        for child in children:
            if not isinstance(child, dict):
                continue
            counted[0] += 1
            if counted[0] > MAX_IMPORT_NODES:
                raise HTTPException(
                    status_code=422,
                    detail=f"That outline has more than {MAX_IMPORT_NODES} nodes: split it up first.",
                )
            out.append(
                {
                    "text": str(child.get("title") or "").strip()[:MAX_OBJECT_TEXT_CHARS],
                    "style": _clean_import_style(_xmind_style(child)),
                    "ref": str(child.get("id") or ""),
                    "links": [],
                    "children": walk(child, depth + 1),
                }
            )
        return out

    #: **The central topic stays a topic** (the features audit, FEAT-01: a
    #: FreeMind file lost its centre this way, and an XMind map without its
    #: central idea is N loose trunks). It also names the map.
    title = str(root.get("title") or sheet.get("title") or "").strip()
    centre = {
        "text": title[:MAX_OBJECT_TEXT_CHARS],
        "style": _clean_import_style({**_xmind_style(root), "branch_layout": None}),
        "ref": str(root.get("id") or ""),
        "links": [],
        "children": walk(root, 1),
    }
    return title, [centre]


def _outline_note_line(stack: list, line: str, stripped: str, blank: bool) -> None:
    """Text indented under a bullet is that topic's note: add it to the owner's `note_lines`."""
    prefix = line[: len(line) - len(stripped)]
    if stack and len(prefix) + prefix.count("\t") > stack[-1][0]:
        lines = stack[-1][1].setdefault("note_lines", [])
        if lines and blank:
            lines.append("")
        lead = len(line) - len(line.lstrip(" "))
        text = line[min(lead, stack[-1][0] + 2):].lstrip("\t")
        lines.append(_MARKDOWN_NOTE_UNESCAPE.sub(r"\1", text))


def _outline_attach(stack: list, roots: list, node: dict, indent: int) -> list:
    """Hang `node` under the nearest shallower bullet (or make it a root) and return the new path stack."""
    while stack and stack[-1][0] >= indent:
        stack.pop()
    if stack and len(stack) < MAX_IMPORT_DEPTH:
        stack[-1][1]["children"].append(node)
    else:
        roots.append(node)
        stack = []
    stack.append((indent, node))
    return stack


def _outline_node(text: str) -> dict:
    """One outline bullet as a node; a `[ ]` or `[x]` prefix makes it a task."""
    node: dict = {"text": text[:MAX_OBJECT_TEXT_CHARS], "children": []}
    task = _MARKDOWN_TASK_ITEM.match(text)
    if task and text[task.end():].strip():
        node["text"] = text[task.end():][:MAX_OBJECT_TEXT_CHARS]
        node["style"] = {"task": "open" if task.group(1) == " " else "done"}
    return node


def _parse_markdown_outline(content: str) -> tuple[str, list[dict]]:
    """An indented `- bullet` outline in, `(title, nested nodes)` out.

    Indentation decides depth, and a jump of more than one level is treated
    as one level: a hand-written outline that indents four spaces in one
    place and two in another is a normal thing to be handed, and refusing it
    would make the import useless for exactly the files people have.
    """
    title = ""
    roots: list[dict] = []
    #: (indent, node) down the path from the current root to the last node
    #: seen: the standard outline-parsing stack.
    stack: list[tuple[int, dict]] = []
    counted = 0
    #: A blank line since the last note line, so a note's paragraphs come
    #: back as paragraphs (decision 18).
    blank = False
    for raw in content.splitlines():
        line = raw.rstrip()
        stripped = line.lstrip()
        if not stripped:
            blank = True
            continue
        if stripped.startswith("#"):
            if not title:
                title = stripped.lstrip("#").strip()
            continue
        if stripped[0] not in "-*+":
            #: **Text indented under a bullet is that topic's note**
            #: (decision 18): what `_export_markdown` writes, and what a
            #: paragraph under a hand-written bullet means. Anything else
            #: that is not a bullet is not part of the outline, as before.
            _outline_note_line(stack, line, stripped, blank)
            blank = False
            continue
        blank = False
        text = stripped[1:].strip()
        if not text:
            continue
        counted += 1
        if counted > MAX_IMPORT_NODES:
            raise HTTPException(
                status_code=422,
                detail=f"That outline has more than {MAX_IMPORT_NODES} nodes: split it up first.",
            )
        # A tab counts as one level however wide it is drawn, so a file
        # indented with tabs nests the same way one indented with spaces does.
        prefix = line[: len(line) - len(stripped)]
        indent = len(prefix) + prefix.count("\t")
        node = _outline_node(text)
        stack = _outline_attach(stack, roots, node, indent)
    for node in _flatten_parsed(roots):
        lines = node.pop("note_lines", None)
        note = "\n".join(lines or []).strip()
        if note:
            node["style"] = {**(node.get("style") or {}), "note": note[:MAX_TOPIC_NOTE_CHARS]}
    return title, roots


#: The backslash `_markdown_note_lines` put in front of a note line that
#: would have read as a bullet or a heading, taken off again.
_MARKDOWN_NOTE_UNESCAPE = re.compile(r"^\\([\\\-*+#])")


def _place_map_nodes(
    db: Session,
    board_id: int,
    parsed: list[dict],
    reference_for=None,
    under: WhiteboardObject | None = None,
) -> list[WhiteboardObject]:
    """Write a parsed outline onto a board as map nodes, returning them.

    Returns the objects rather than a count because both callers have to
    record one `whiteboard_object`/`created` event each: a map whose nodes
    have no events of their own replays to an empty board (Brief 7, open
    item 4, `archive/agent-remaining/brief7-event-log.md`).

    One walk for both doors onto a map made from text: an import, and the
    AI proposal the user accepted. They differ in exactly one thing, whether
    a line stands for a note the user already has, and that is what
    `reference_for` answers: given a node's text it returns `(kind, ref_id)`
    or None. An import passes nothing, because guessing that a line reading
    "Chapter three" means a particular note in *this* notebook is the kind of
    helpfulness whose mistakes are invisible until much later; the proposal
    passes a lookup over the notes the user themselves chose, which is not a
    guess.

    A single running row counter is shared by the whole walk, so the map lands
    as a readable ladder rather than with every branch stacked on top of the
    last one at y=0.
    """
    created: list[WhiteboardObject] = []
    row = [0]

    def place(nodes: list[dict], parent: WhiteboardObject | None, depth: int) -> None:
        for node in nodes:
            #: A node built from a note already says which (the map made
            #: from the graph's notes, `routes_map_from_notes`), and that is
            #: not a guess from its text.
            if node.get("note"):
                reference = ("note", node["note"])
            else:
                reference = reference_for(node["text"]) if reference_for else None
            kind, ref_id = reference if reference else (MAP_TOPIC_KIND, None)
            data: dict = {"content": node["text"]}
            if ref_id is not None:
                data["ref_id"] = ref_id
            # Whatever the file said the node looks like, already validated
            # by `_clean_import_style`. A Markdown outline and an AI proposal
            # carry no style at all, which is why this is a `get`.
            data.update(node.get("style") or {})
            #: Under an existing topic (a pasted outline), the ladder starts
            #: beside it; the client's tidy lays it out properly after.
            ox = float(under.x) + MAP_COL if under is not None else 0.0
            oy = float(under.y) if under is not None else 0.0
            obj = WhiteboardObject(
                board_id=board_id,
                kind=kind,
                data=json.dumps(data),
                x=ox + float(depth) * MAP_COL,
                y=oy + float(row[0]) * MAP_ROW,
                z=1,
                parent_id=parent.id if parent is not None else None,
            )
            row[0] += 1
            db.add(obj)
            db.flush()  # its children need its id
            created.append(obj)
            place(node["children"], obj, depth + 1)

    place(parsed, under, 0)
    return created


def _restore_import_links(
    db: Session, board_id: int, parsed: list[dict], created: list[WhiteboardObject]
) -> int:
    """The imported file's cross-links, as the link sketches a map draws.

    **The ids in the file are the file's, not this database's**, so this runs
    after every node has been placed and has one: `parsed` is walked in the
    same pre-order `_place_map_nodes` places in, which pairs each parsed node
    with the object made from it, and that pairing is the whole translation.
    Walked here rather than threaded through `_place_map_nodes` because the
    other caller of that function (the AI proposal) has no file and no ids,
    and giving it a parameter it can only pass None to is a parameter every
    later reader has to rule out.

    A link whose far end is not in this file is dropped rather than left
    dangling: half a link is a row the canvas draws as a line to nowhere, and
    `_forget_links_to` exists precisely to stop those accumulating.
    """
    by_file_id: dict[str, WhiteboardObject] = {}
    flat: list[dict] = []

    def walk(nodes: list[dict]) -> None:
        for node in nodes:
            flat.append(node)
            walk(node.get("children") or [])

    walk(parsed)
    if len(flat) != len(created):
        # The two walks disagreed, which they cannot unless `_place_map_nodes`
        # changed shape. Nothing is written rather than something wrong: an
        # import that quietly links the wrong pair of topics is worse than one
        # that drops the links.
        return 0
    for node, obj in zip(flat, created):
        ref = str(node.get("ref") or "")
        if ref:
            by_file_id[ref] = obj
    made = 0
    for node, obj in zip(flat, created):
        labels = node.get("link_labels") or []
        for at, target in enumerate(node.get("links") or []):
            far = by_file_id.get(str(target))
            if far is None or far.id == obj.id:
                continue
            link_data = {
                "type": "link-straight",
                "sourceId": obj.id,
                "sourceKind": "object",
                "targetId": far.id,
                "targetKind": "object",
            }
            if at < len(labels) and labels[at]:
                link_data["label"] = labels[at]
            db.add(
                WhiteboardSketch(
                    board_id=board_id,
                    data=json.dumps(link_data),
                    x=0.0,
                    y=0.0,
                    z=1,
                )
            )
            made += 1
    if made:
        db.flush()
    return made


def _flatten_parsed(parsed: list[dict]) -> list[dict]:
    """Every node of a parsed outline, iteratively."""
    out: list[dict] = []
    stack = list(parsed)
    while stack:
        node = stack.pop()
        out.append(node)
        stack.extend(node.get("children") or [])
    return out
