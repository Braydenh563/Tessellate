"""Other tools' diagrams in, as the board's own graph: GraphML, Miro, PlantUML and EMF (L-whiteboard-41, 45).

Every reader here is a pure function from text (or bytes) to a plain dict, so the tests run them with no
server and the board places the result with the placer the Mermaid import already has. Nothing is rendered
and nothing is fetched: a PlantUML file is *parsed*, not drawn by a PlantUML server or a Java process.

A result is `{"kind": "graph", "graph": {...}}` (the shape `diagramModel.parse` returns for a Mermaid
flowchart, so one placer draws all of them), `{"kind": "sequence", "sequence": {...}}` (the shape the
Mermaid sequence reader returns), or `{"kind": "emf", ...}` (see `inspect_emf`).

**Hostile input.** A size cap is checked before a byte is parsed (`MAX_CONVERT_CHARS`, `MAX_EMF_BYTES`), and
XML goes through `wb_import._parse_xml_document`, the one door that refuses a document type declaration
(the billion-laughs shape) and parses with `defusedxml`. A file with more nodes than `MAX_NODES` is refused,
not trimmed, so a half diagram is never passed off as the whole.
"""

from __future__ import annotations

import base64
import json
import re
import struct
from html import unescape

from fastapi import HTTPException

from tessellate.api.wb_import import _parse_xml_document

#: Text a reader will look at. A real diagram is a few KB; this is generous and still small enough that a
#: parse cannot hold the server.
MAX_CONVERT_CHARS = 2_000_000
#: An EMF is read for its header only; the whole file is still capped.
MAX_EMF_BYTES = 8_000_000
MAX_NODES = 2_000
MAX_EDGES = 6_000

FORMATS = ("auto", "graphml", "miro", "plantuml", "emf")


def _refuse(code: int, detail: str):
    raise HTTPException(status_code=code, detail=detail)


def _cap(text: str, label: str) -> None:
    if len(text) > MAX_CONVERT_CHARS:
        _refuse(
            413,
            f"That {label} file is larger than {MAX_CONVERT_CHARS // 1_000_000} MB, which is more than a diagram needs.",
        )


def _check_counts(nodes: list, edges: list, label: str) -> None:
    if len(nodes) > MAX_NODES or len(edges) > MAX_EDGES:
        _refuse(
            413,
            f"That {label} diagram has more than {MAX_NODES} shapes or {MAX_EDGES} connectors, so it was not brought in.",
        )


def _graph(nodes: list, edges: list, **extra) -> dict:
    out = {"dir": "TD", "nodes": nodes, "edges": edges, "subgraphs": [], "skipped": 0}
    out.update(extra)
    return out


def _local(tag: str) -> str:
    """An XML tag without its namespace."""
    return tag.rsplit("}", 1)[-1]


# --- GraphML --------------------------------------------------------------------------------------------------


_GML_SHAPES = {"diamond": "diamond", "ellipse": "circle", "roundrectangle": "rounded"}


def _gml_keys(root) -> dict[str, str]:
    return {
        k.get("id"): (k.get("attr.name") or k.get("yfiles.type") or "").lower()
        for k in root.iter()
        if _local(k.tag) == "key" and k.get("id")
    }


def _gml_inner(out: dict, inner) -> None:
    """One yEd element inside a data block: its label, geometry or shape."""
    tag = _local(inner.tag)
    if tag in ("NodeLabel", "EdgeLabel") and out["label"] is None and (inner.text or "").strip():
        out["label"] = " ".join(inner.text.split())
    elif tag == "Geometry" and inner.get("width"):
        out["geometry"] = inner
    elif tag == "Shape" and inner.get("type"):
        out["shape"] = inner.get("type")


def _gml_data(element, keys: dict[str, str]) -> dict:
    out: dict = {"label": None, "geometry": None, "shape": None}
    for datum in element:
        if _local(datum.tag) != "data":
            continue
        if (
            keys.get(datum.get("key"), "") in ("label", "name", "description")
            and out["label"] is None
            and (datum.text or "").strip()
        ):
            out["label"] = datum.text.strip()
        for inner in datum.iter():
            _gml_inner(out, inner)
    return out


def _gml_box(geo, node: dict) -> None:
    try:
        node.update(
            w=max(20.0, float(geo.get("width"))),
            h=max(20.0, float(geo.get("height"))),
            x=float(geo.get("x", 0)),
            y=float(geo.get("y", 0)),
        )
    except (TypeError, ValueError):
        #: A box with no size, or a size that is not a number, keeps the default box the caller gave it.
        return


class _GraphML:
    def __init__(self, keys: dict[str, str]) -> None:
        self.keys = keys
        self.nodes: list[dict] = []
        self.edges: list[dict] = []
        self.frames: list[dict] = []
        self.skipped = 0

    def node(self, child, parent: str | None) -> None:
        ident = child.get("id") or f"n{len(self.nodes) + 1}"
        data = _gml_data(child, self.keys)
        node = {
            "id": ident,
            "text": data["label"] or ident,
            "shape": _GML_SHAPES.get((data["shape"] or "").lower(), "rect"),
            "group": parent,
        }
        if data["geometry"] is not None:
            _gml_box(data["geometry"], node)
        nested = next((c for c in child if _local(c.tag) == "graph"), None)
        if nested is not None:
            self.frames.append({"id": ident, "title": node["text"], "parent": parent})
            self.walk(nested, ident)
        else:
            self.nodes.append(node)
        if len(self.nodes) > MAX_NODES:
            _check_counts(self.nodes, self.edges, "GraphML")

    def edge(self, child) -> None:
        src, dst = child.get("source"), child.get("target")
        if not src or not dst:
            self.skipped += 1
            return
        label = _gml_data(child, self.keys)["label"] or ""
        self.edges.append(
            {
                "from": src,
                "to": dst,
                "label": label,
                "arrow": child.get("directed") != "false",
                "dashed": False,
            }
        )
        if len(self.edges) > MAX_EDGES:
            _check_counts(self.nodes, self.edges, "GraphML")

    def walk(self, graph, parent: str | None) -> None:
        for child in graph:
            tag = _local(child.tag)
            if tag == "node":
                self.node(child, parent)
            elif tag == "edge":
                self.edge(child)
            elif tag == "graph":
                self.walk(child, parent)
            elif tag in ("hyperedge", "port"):
                self.skipped += 1


def parse_graphml(text: str) -> dict:
    """GraphML nodes, edges and labels (also yEd's: `y:NodeLabel`, `y:EdgeLabel`, `y:Geometry`, `y:Shape`).

    A label is the node's `label`/`name` data key, else a yEd `NodeLabel`, else its id. `<graph>` inside a
    `<node>` (a nested graph) becomes a frame around its nodes. A hyperedge, a port and everything else is
    left out and counted in `skipped`.
    """
    _cap(text, "GraphML")
    root = _parse_xml_document(text, "GraphML")
    if _local(root.tag) != "graphml":
        _refuse(422, "That isn't GraphML: the file has no graphml element.")
    state = _GraphML(_gml_keys(root))
    for top in root:
        if _local(top.tag) == "graph":
            state.walk(top, None)
            if top.get("edgedefault") == "undirected":
                for e in state.edges:
                    e["arrow"] = False
    known = {n["id"] for n in state.nodes} | {f["id"] for f in state.frames}
    kept = [e for e in state.edges if e["from"] in known and e["to"] in known]
    skipped = state.skipped + len(state.edges) - len(kept)
    _check_counts(state.nodes, kept, "GraphML")
    if not state.nodes:
        _refuse(422, "No nodes found in that GraphML file.")
    return {
        "kind": "graph",
        "graph": _graph(
            state.nodes,
            kept,
            subgraphs=state.frames,
            skipped=skipped,
            positioned=_positioned(state.nodes) and not state.frames,
        ),
    }


def _positioned(nodes: list[dict]) -> bool:
    """Every shape came with a place, so the file's own layout is kept rather than a new one made."""
    return bool(nodes) and all("x" in n and "y" in n for n in nodes)


# --- Miro -----------------------------------------------------------------------------------------------------

_TAGS = re.compile(r"<[^>]*>")
_MIRO_SHAPES = {
    "rectangle": "rect",
    "round_rectangle": "rounded",
    "circle": "circle",
    "rhombus": "diamond",
    "ellipse": "circle",
    "flow_chart_decision": "diamond",
}
_MIRO_BOXES = {"shape", "sticky_note", "text", "card", "app_card"}


def _plain(html: str | None) -> str:
    """Miro keeps item text as HTML (`<p>one</p><p>two</p>`); the board keeps lines."""
    if not html:
        return ""
    spaced = re.sub(r"</p>|<br\s*/?>|</li>", "\n", str(html), flags=re.I)
    return "\n".join(
        line.strip() for line in unescape(_TAGS.sub("", spaced)).splitlines() if line.strip()
    )


def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _miro_box(
    item: dict, ident: str, kind: str, data: dict, geom: tuple[float, float, float, float]
) -> dict:
    x, y, w, h = geom
    style = _dict(item.get("style"))
    fill = style.get("fillColor") or style.get("backgroundColor")
    node = {
        "id": ident,
        "text": _plain(data.get("content")) or str(data.get("title") or ""),
        "shape": _MIRO_SHAPES.get(str(data.get("shape")), "rect"),
        "group": None,
        "x": x,
        "y": y,
        "w": max(20.0, w),
        "h": max(20.0, h),
    }
    if isinstance(fill, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", fill):
        node["fill"] = fill
    if kind == "sticky_note":
        node["sticky"] = True
    return node


def _miro_geometry(item: dict) -> tuple[float, float, float, float] | None:
    pos, geo = _dict(item.get("position")), _dict(item.get("geometry"))
    try:
        return (
            float(pos.get("x", 0)),
            float(pos.get("y", 0)),
            float(geo.get("width") or 160),
            float(geo.get("height") or 70),
        )
    except (TypeError, ValueError):
        return None


def _miro_edge(link: dict, ends: set[str]) -> dict | None:
    start, end = (link.get("startItem") or {}).get("id"), (link.get("endItem") or {}).get("id")
    start, end = (
        (str(start) if start is not None else None),
        (str(end) if end is not None else None),
    )
    if start not in ends or end not in ends:
        return None
    caps = link.get("captions") if isinstance(link.get("captions"), list) else []
    label = _plain(caps[0].get("content")) if caps and isinstance(caps[0], dict) else ""
    style = link.get("style") or {}
    return {
        "from": start,
        "to": end,
        "label": label,
        "arrow": (style.get("endStrokeCap") or "none") != "none",
        "dashed": style.get("strokeStyle") == "dashed",
    }


def _miro_group(nodes: list[dict], frames: list[dict]) -> None:
    """A shape inside a Miro frame belongs to it when its centre lies in the frame's box."""
    for node in nodes:
        for frame in frames:
            if (
                frame["x"] <= node["x"] <= frame["x"] + frame["w"]
                and frame["y"] <= node["y"] <= frame["y"] + frame["h"]
            ):
                node["group"] = frame["id"]


def _miro_items(text: str) -> list[dict]:
    try:
        doc = json.loads(text)
    except ValueError:
        _refuse(
            422,
            "That isn't Miro JSON. Export the board's items with the Miro REST API (get items on board) and try again.",
        )
    items = doc.get("data") if isinstance(doc, dict) else doc
    if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        _refuse(422, "That isn't Miro JSON: expected a list of items under data.")
    return items


def _miro_sort(item: dict, nodes: list[dict], frames: list[dict], links: list[dict]) -> bool:
    """File one item as a shape, a frame or a connector; False when it is none of those or has no usable place."""
    kind = item.get("type")
    geom = _miro_geometry(item)
    if geom is None or not (kind in _MIRO_BOXES or kind in ("frame", "connector")):
        return False
    ident = str(item.get("id") or f"i{len(nodes) + len(frames) + 1}")
    data = _dict(item.get("data"))
    x, y, w, h = geom
    if kind == "frame":
        frames.append(
            {
                "id": ident,
                "title": str(data.get("title") or "Frame"),
                "x": x - w / 2,
                "y": y - h / 2,
                "w": w,
                "h": h,
            }
        )
    elif kind == "connector":
        links.append(item)
    else:
        nodes.append(_miro_box(item, ident, kind, data, geom))
    return True


def parse_miro(text: str) -> dict:
    """Miro's REST API v2 items as JSON: `{"data": [item, ...]}` (what "Get items on board" returns and what
    a backup script saves) or a bare list of the same items.

    That is the one Miro shape with a public, versioned definition (developers.miro.com, REST API v2: an item
    has `id`, `type`, `data`, `style`, `position {x, y}`, `geometry {width, height}`, `parent {id}`, and a
    connector `startItem {id}`, `endItem {id}`, `captions [{content}]`). Miro's own board export is a
    proprietary `.rtb` archive and its CSV export carries sticky notes' text with no positions, so neither
    is read here (decision recorded on L-whiteboard-45). Shapes, stickies, text, cards and frames come
    in with their places; connectors rejoin them; anything else (images, embeds, mind map nodes) is counted.
    """
    _cap(text, "Miro")
    nodes: list[dict] = []
    frames: list[dict] = []
    links: list[dict] = []
    skipped = 0
    for item in _miro_items(text):
        skipped += not _miro_sort(item, nodes, frames, links)
    _check_counts(nodes + frames, links, "Miro")
    ends = {n["id"] for n in nodes} | {f["id"] for f in frames}
    edges = [e for e in (_miro_edge(link, ends) for link in links) if e]
    skipped += len(links) - len(edges)
    _miro_group(nodes, frames)
    _check_counts(nodes, edges, "Miro")
    if not nodes and not frames:
        _refuse(422, "No shapes, sticky notes or frames found in that Miro file.")
    return {
        "kind": "graph",
        "graph": _graph(
            nodes,
            edges,
            subgraphs=[],
            frames=frames,
            skipped=skipped,
            positioned=True,
            centred=True,
        ),
    }


# --- PlantUML -------------------------------------------------------------------------------------------------

_PU_SKIP_BLOCK = re.compile(
    r"^(skinparam|!|hide|show|title|header|footer|legend|left to right|top to bottom|scale|autonumber|center|caption)\b",
    re.I,
)
_PU_REL = re.compile(
    r"""^("[^"]+"|[\w.$:-]+)\s*(?:"([^"]*)")?\s*
        (<\|?|\*|o|\#|\+|\^|x|\}|\|)?
        (-+|\.+|=+)(?:\[[^\]]*\])?(?:[a-z]+(?:\[[^\]]*\])?)?(?:-+|\.+)?
        (\|?>|\*|o|\#|\+|\^|x|\{|\|)?\s*
        (?:"([^"]*)")?\s*("[^"]+"|[\w.$:-]+)\s*(?::\s*(.*))?$""",
    re.X,
)
_PU_CAPS = {
    "<|": "triangle",
    "|>": "triangle",
    "*": "diamond-filled",
    "o": "diamond",
    "<": "arrow",
    ">": "arrow",
    "#": "arrow",
    "+": "arrow",
    "^": "triangle",
    "x": "cross",
}


def _name(raw: str) -> str:
    return raw.strip().strip('"')


def _drop_block_comments(text: str) -> str:
    """PlantUML's `/' ... '/` comments out, in one pass (CodeQL 2306: a lazy regex rescans from every `/'`).

    An unclosed `/'` is left as written, as the regex it replaces left it."""
    out: list[str] = []
    at = 0
    while True:
        start = text.find("/'", at)
        if start < 0:
            out.append(text[at:])
            return "".join(out)
        out.append(text[at:start])
        end = text.find("'/", start + 2)
        if end < 0:
            out.append(text[start:])
            return "".join(out)
        at = end + 2


def _pu_lines(text: str) -> list[str]:
    """The lines between `@startuml` and `@enduml`, comments (`'` and `/' ... '/`) out, a trailing `\\` joined."""
    body = _drop_block_comments(text)
    out: list[str] = []
    started = "@start" not in body.lower()
    for raw in body.splitlines():
        line = raw.strip()
        if line.lower().startswith("@start"):
            started = True
            continue
        if line.lower().startswith("@end"):
            break
        if not started or not line or line.startswith("'"):
            continue
        out.append(line)
    return out


def plantuml_kind(lines: list[str]) -> str:
    """class, elements, activity, sequence, or `""` when it is a diagram this reader has no subset for."""
    joined = "\n".join(lines)
    if re.search(
        r"^(abstract\s+class|class|interface|enum|annotation)\s", joined, re.M
    ) or re.search(r"<\|--|--\|>|\.\.\|>|<\|\.\.|\*--|--\*|o--|--o", joined):
        return "class"
    if re.search(
        r"^(rectangle|diamond|circle|node|card|component|usecase|artifact|storage|cloud|database|folder|frame|package|agent|queue|interface)\s+\"",
        joined,
        re.M,
    ) and re.search(r"^[\w$]+\s+(?:--|\.\.)>?\s+[\w$]+", joined, re.M):
        return "elements"
    if re.search(r"^start\s*$", joined, re.M | re.I) or re.search(r"^:.*;\s*$", joined, re.M):
        return "activity"
    if re.search(
        r"^(participant|actor|boundary|control|entity|database|collections|queue)\s",
        joined,
        re.M | re.I,
    ) or re.search(r"^\S+\s*(<?-{1,2}>>?|<?\\\\?-{1,2}|<?-{1,2}\\\\?)\s*\S+\s*:", joined, re.M):
        return "sequence"
    return ""


_PU_CLASS_DECL = re.compile(
    r'^(?:abstract\s+class|abstract|class|interface|enum|annotation|entity)\s+("[^"]+"|[\w.$-]+)(?:\s+as\s+([\w.$-]+))?(?:\s*<<[^>]*>>)?(?:\s+(?:extends|implements)\s+[\w.$,\s-]+)?\s*(\{)?\s*(\})?$'
)
_PU_MEMBER = re.compile(r"^([\w.$-]+)\s*:\s*(.+)$")


class _ClassDiagram:
    def __init__(self) -> None:
        self.nodes: dict[str, dict] = {}
        self.edges: list[dict] = []
        self.members: dict[str, list[str]] = {}
        self.skipped = 0
        self.inside: str | None = None

    def node(self, raw: str, text: str | None = None) -> str:
        ident = _name(raw)
        if ident not in self.nodes:
            self.nodes[ident] = {"id": ident, "text": text or ident, "shape": "rect", "group": None}
            self.members[ident] = []
        return ident

    def in_body(self, line: str) -> None:
        if line == "}":
            self.inside = None
        elif not line.startswith(("--", "..", "==")):
            self.members[self.inside].append(line)

    def declare(self, decl: re.Match) -> None:
        name = _name(decl.group(1))
        ident = self.node(decl.group(2) or name, name)
        if decl.group(2):
            self.nodes[ident]["text"] = name
        if decl.group(3) and not decl.group(4):
            self.inside = ident

    def relate(self, rel: re.Match) -> None:
        start_mark, arrow, end_mark = rel.group(3), rel.group(4), rel.group(5)
        a, b = self.node(rel.group(1)), self.node(rel.group(7))
        label = next(
            (t.strip() for t in (rel.group(8), rel.group(2), rel.group(6)) if t and t.strip()), ""
        )
        start_cap, end_cap = _PU_CAPS.get(start_mark or ""), _PU_CAPS.get(end_mark or "")
        self.edges.append(
            {
                "from": a,
                "to": b,
                "label": label,
                "arrow": bool(end_cap),
                "startCap": start_cap,
                "endCap": end_cap,
                "dashed": arrow[0] == ".",
            }
        )

    def line(self, line: str) -> None:
        if self.inside is not None:
            self.in_body(line)
            return
        decl = _PU_CLASS_DECL.match(line)
        if decl:
            self.declare(decl)
            return
        if (
            _PU_SKIP_BLOCK.match(line)
            or line in ("{", "}")
            or line.startswith(("package", "namespace", "note", "end note"))
        ):
            self.skipped += line.startswith(
                ("package", "namespace", "note")
            ) and line.rstrip().endswith("{")
            return
        rel = _PU_REL.match(line)
        if rel:
            self.relate(rel)
            return
        member = _PU_MEMBER.match(line)
        if member:
            self.members[self.node(member.group(1))].append(member.group(2).strip())
        else:
            self.skipped += 1


def _pu_class(lines: list[str]) -> dict:
    state = _ClassDiagram()
    for line in lines:
        state.line(line)
    for ident, rows in state.members.items():
        if rows:
            state.nodes[ident]["text"] = "\n".join([state.nodes[ident]["text"], *rows])
        state.nodes[ident]["h"] = 50 + 20 * len(rows)
    node_list = list(state.nodes.values())
    _check_counts(node_list, state.edges, "PlantUML")
    return {"kind": "graph", "graph": _graph(node_list, state.edges, skipped=state.skipped)}


def _pu_elements(lines: list[str]) -> dict:
    """What the board's own PlantUML writer says (and what a component or deployment diagram says in the same
    plain way): named elements with an alias, `package "Title" { ... }` round some of them, and `a --> b : label`
    (`--` no arrow, `..>` dashed)."""
    nodes: dict[str, dict] = {}
    frames: list[dict] = []
    edges: list[dict] = []
    skipped = 0
    stack: list[str] = []
    shapes = {"diamond": "diamond", "circle": "circle", "usecase": "circle"}
    for line in lines:
        pack = re.match(
            r'^(?:package|frame|folder|cloud|node|rectangle)\s+"([^"]*)"(?:\s+as\s+([\w$]+))?\s*\{$',
            line,
        )
        if pack:
            ident = pack.group(2) or f"g{len(frames) + 1}"
            frames.append(
                {"id": ident, "title": pack.group(1), "parent": stack[-1] if stack else None}
            )
            stack.append(ident)
            continue
        if line == "}":
            if stack:
                stack.pop()
            continue
        decl = re.match(
            r'^(rectangle|diamond|circle|node|card|component|usecase|artifact|storage|cloud|database|folder|agent|queue|interface|actor)\s+"([^"]*)"(?:\s+as\s+([\w$]+))?\s*$',
            line,
        )
        if decl:
            ident = decl.group(3) or decl.group(2)
            nodes[ident] = {
                "id": ident,
                "text": decl.group(2),
                "shape": shapes.get(decl.group(1), "rect"),
                "group": stack[-1] if stack else None,
            }
            continue
        rel = re.match(r"^([\w$]+)\s+(--|\.\.|-->|\.\.>|->|\.>)\s+([\w$]+)\s*(?::\s*(.*))?$", line)
        if rel:
            for end in (rel.group(1), rel.group(3)):
                nodes.setdefault(end, {"id": end, "text": end, "shape": "rect", "group": None})
            edges.append(
                {
                    "from": rel.group(1),
                    "to": rel.group(3),
                    "label": (rel.group(4) or "").strip(),
                    "arrow": rel.group(2).endswith(">"),
                    "dashed": rel.group(2).startswith("."),
                }
            )
            continue
        if not _PU_SKIP_BLOCK.match(line):
            skipped += 1
    node_list = list(nodes.values())
    _check_counts(node_list, edges, "PlantUML")
    return {"kind": "graph", "graph": _graph(node_list, edges, subgraphs=frames, skipped=skipped)}


_PU_MSG = re.compile(
    r'^("[^"]+"|[\w.$-]+)\s*(<?-{1,2}>>?|<?-{1,2}\\\\?|<?\\\\?-{1,2}|-{1,2}x|-{1,2}\)|<-{1,2}|-{1,2}>|\.{2}>)\s*("[^"]+"|[\w.$-]+)\s*(?::\s*(.*))?$'
)
_PU_PART = re.compile(
    r'^(participant|actor|boundary|control|entity|database|collections|queue)\s+("[^"]+"|[\w.$-]+)(?:\s+as\s+("[^"]+"|[\w.$-]+))?',
    re.I,
)
_PU_NOTE = re.compile(
    r"^note\s+(over|left of|right of|left|right)\s+([\w.$-]+(?:\s*,\s*[\w.$-]+)?)\s*:\s*(.*)$", re.I
)
_PU_BLOCK = re.compile(r"^(alt|opt|loop|par|critical|break|group)\b\s*(.*)$", re.I)
_PU_SEQ_QUIET = re.compile(r"^(end|else|activate|deactivate|return|autonumber|\|\|\|)\b", re.I)


class _Sequence:
    def __init__(self) -> None:
        self.parts: dict[str, dict] = {}
        self.steps: list[dict] = []
        self.skipped = 0

    def who(self, raw: str, text: str | None = None, actor: bool = False) -> str:
        ident = _name(raw)
        part = self.parts.setdefault(ident, {"id": ident, "text": ident, "actor": False})
        if text:
            part["text"] = text
        part["actor"] = part["actor"] or actor
        return ident

    def declare(self, decl: re.Match) -> None:
        kind, first, alias = decl.group(1).lower(), decl.group(2), decl.group(3)
        actor = kind == "actor"
        if alias and not first.startswith('"'):
            self.who(first, _name(alias), actor)
        elif alias:
            self.who(alias, _name(first), actor)
        else:
            self.who(first, None, actor)

    def message(self, found: re.Match) -> None:
        a, arrow, b = self.who(found.group(1)), found.group(2), self.who(found.group(3))
        if arrow.startswith("<"):
            a, b = b, a
        self.steps.append(
            {
                "kind": "message",
                "from": a,
                "to": b,
                "text": (found.group(4) or "").strip(),
                "dashed": "--" in arrow,
            }
        )

    def note(self, note: re.Match) -> None:
        side = {"left": "left of", "right": "right of"}.get(
            note.group(1).lower(), note.group(1).lower()
        )
        self.steps.append(
            {
                "kind": "note",
                "side": side,
                "over": [self.who(n.strip()) for n in note.group(2).split(",")],
                "text": note.group(3).strip(),
            }
        )

    def line(self, line: str) -> None:
        for pattern, handler in (
            (_PU_PART, self.declare),
            (_PU_MSG, self.message),
            (_PU_NOTE, self.note),
        ):
            found = pattern.match(line)
            if found:
                handler(found)
                return
        block = _PU_BLOCK.match(line)
        if block:
            self.steps.append(
                {"kind": "block", "text": f"{block.group(1).lower()} {block.group(2)}".strip()}
            )
        elif not (_PU_SEQ_QUIET.match(line) or _PU_SKIP_BLOCK.match(line)):
            self.skipped += 1


def _pu_sequence(lines: list[str]) -> dict:
    state = _Sequence()
    for line in lines:
        state.line(line)
    if len(state.parts) > MAX_NODES or len(state.steps) > MAX_EDGES:
        _check_counts(list(state.parts), state.steps, "PlantUML")
    return {
        "kind": "sequence",
        "sequence": {
            "participants": list(state.parts.values()),
            "steps": state.steps,
            "skipped": state.skipped,
        },
    }


class _Activity:
    """The activity reader's state and one method per statement; `_ACT_ROUTES` says which line goes to which."""

    def __init__(self) -> None:
        self.nodes: list[dict] = []
        self.edges: list[dict] = []
        self.skipped = 0
        #: Open ends waiting for the next node: (from id, edge label).
        self.tails: list[tuple[str, str]] = []
        self.stack: list[dict] = []

    def add(self, text: str, shape: str = "rect") -> str:
        ident = f"a{len(self.nodes) + 1}"
        self.nodes.append({"id": ident, "text": text, "shape": shape, "group": None})
        return ident

    def link(self, src: str, dst: str, label: str) -> None:
        self.edges.append({"from": src, "to": dst, "label": label, "arrow": True, "dashed": False})

    def join(self, to: str) -> None:
        for src, label in self.tails:
            self.link(src, to, label)
        self.tails.clear()

    def top(self, kind: str) -> dict | None:
        return self.stack[-1] if self.stack and self.stack[-1]["kind"] == kind else None

    def miss(self, *_args) -> None:
        self.skipped += 1

    def start(self, *_args) -> None:
        self.tails.append((self.add("Start", "start"), ""))

    def stop(self, line: str, low: str) -> None:
        if low in ("stop", "end"):
            self.join(self.add("End", "end"))
        else:
            self.tails.clear()

    def action(self, line: str, low: str) -> None:
        if not line.endswith(";"):
            self.skipped += 1
        self.join(
            self.add(line[1:].rstrip(";").strip() if line.endswith(";") else line[1:].strip())
        )
        self.tails.append((self.nodes[-1]["id"], ""))

    def cond(self, line: str, low: str) -> None:
        m = re.match(
            r"^(?:else\s*if|elseif|if)\s*\((.*?)\)\s*(?:then\s*(?:\((.*?)\))?)?", line, re.I
        )
        question = m.group(1) if m else line
        then_label = (m.group(2) or "").strip() if m else ""
        if low.startswith("if"):
            dec = self.add(question, "diamond")
            self.join(dec)
            self.stack.append({"kind": "if", "dec": dec, "ends": [], "label": then_label})
            self.tails.append((dec, then_label))
            return
        top = self.top("if")
        if top is None:
            self.skipped += 1
            return
        top["ends"].extend(self.tails)
        self.tails.clear()
        dec = self.add(question, "diamond")
        self.link(top["dec"], dec, top.get("else_label", "no"))
        top["dec"] = dec
        self.tails.append((dec, then_label))

    def otherwise(self, line: str, low: str) -> None:
        top = self.top("if")
        if top is None:
            self.skipped += 1
            return
        top["ends"].extend(self.tails)
        self.tails.clear()
        m = re.match(r"^else\s*(?:\((.*?)\))?", line, re.I)
        self.tails.append((top["dec"], (m.group(1) or "").strip() if m and m.group(1) else "no"))
        top["else_taken"] = True

    def endif(self, line: str, low: str) -> None:
        if self.top("if") is None:
            self.skipped += 1
            return
        top = self.stack.pop()
        if not top.get("else_taken"):
            self.tails.append((top["dec"], "no"))
        self.tails.extend(top["ends"])

    def loop(self, line: str, low: str) -> None:
        m = re.match(r"^while\s*\((.*?)\)\s*(?:is\s*\((.*?)\))?", line, re.I)
        dec = self.add(m.group(1) if m else line, "diamond")
        self.join(dec)
        self.stack.append({"kind": "while", "dec": dec, "exit": "no"})
        self.tails.append((dec, (m.group(2) or "").strip() if m and m.group(2) else "yes"))

    def endloop(self, line: str, low: str) -> None:
        if self.top("while") is None:
            self.skipped += 1
            return
        top = self.stack.pop()
        for src, label in self.tails:
            self.link(src, top["dec"], label)
        m = re.match(r"^endwhile\s*(?:\((.*?)\))?", line, re.I)
        self.tails[:] = [(top["dec"], (m.group(1) or "").strip() if m and m.group(1) else "no")]

    def repeat(self, *_args) -> None:
        anchor = self.add("Repeat", "rounded")
        self.join(anchor)
        self.stack.append({"kind": "repeat", "anchor": anchor})
        self.tails.append((anchor, ""))

    def repeat_while(self, line: str, low: str) -> None:
        if self.top("repeat") is None:
            self.skipped += 1
            return
        top = self.stack.pop()
        m = re.match(r"^repeat\s+while\s*\((.*?)\)", line, re.I)
        dec = self.add(m.group(1) if m else "again?", "diamond")
        self.join(dec)
        self.link(dec, top["anchor"], "yes")
        self.tails.append((dec, "no"))

    def ignore(self, *_args) -> None:
        return None


#: Where a line goes, first match wins (`else if` before `else`, `repeat while` before nothing else: `repeat` is exact).
_ACT_ROUTES = (
    (lambda line, low: low == "start", _Activity.start),
    (lambda line, low: low in ("stop", "end", "kill", "detach"), _Activity.stop),
    (lambda line, low: line.startswith(":"), _Activity.action),
    (
        lambda line, low: bool(re.match(r"^(if|elseif)\s*\(", low)) or low.startswith("else if"),
        _Activity.cond,
    ),
    (lambda line, low: low.startswith("else"), _Activity.otherwise),
    (lambda line, low: low == "endif", _Activity.endif),
    (lambda line, low: low.startswith("while"), _Activity.loop),
    (lambda line, low: low.startswith("endwhile"), _Activity.endloop),
    (lambda line, low: low == "repeat", _Activity.repeat),
    (lambda line, low: low.startswith("repeat while"), _Activity.repeat_while),
    (
        lambda line, low: (
            bool(_PU_SKIP_BLOCK.match(line))
            or low.startswith(("partition", "|", "}", "note", "end note", "legend"))
        ),
        _Activity.ignore,
    ),
)


def _pu_activity(lines: list[str]) -> dict:
    """The new activity syntax: `start`, `:action;`, `if (c) then (yes) ... else (no) ... endif`,
    `while (c) is (yes) ... endwhile`, `repeat ... repeat while (c)`, `stop`, `end`. A fork, a swimlane and a
    note are left out and counted."""
    state = _Activity()
    for line in lines:
        low = line.lower()
        handler = next((h for test, h in _ACT_ROUTES if test(line, low)), _Activity.miss)
        handler(state, line, low)
    _check_counts(state.nodes, state.edges, "PlantUML")
    return {"kind": "graph", "graph": _graph(state.nodes, state.edges, skipped=state.skipped)}


def parse_plantuml(text: str) -> dict:
    """A PlantUML class, sequence or activity (new syntax) diagram as board shapes and connectors."""
    _cap(text, "PlantUML")
    lines = _pu_lines(text)
    kind = plantuml_kind(lines)
    if not kind:
        _refuse(
            422,
            "That PlantUML is not a class, sequence or activity diagram, or a plain diagram of named boxes, the kinds read here.",
        )
    result = {
        "class": _pu_class,
        "elements": _pu_elements,
        "sequence": _pu_sequence,
        "activity": _pu_activity,
    }[kind](lines)
    if result["kind"] == "graph" and not result["graph"]["nodes"]:
        _refuse(422, "No shapes found in that PlantUML diagram.")
    if result["kind"] == "sequence" and not result["sequence"]["participants"]:
        _refuse(422, "No participants found in that PlantUML sequence diagram.")
    result["diagram"] = kind
    return result


# --- EMF ------------------------------------------------------------------------------------------------------


def inspect_emf(data: bytes) -> dict:
    """An EMF is checked and measured, not drawn.

    **Why not converted:** a browser has no EMF decoder; the readers that draw one (Inkscape, LibreOffice,
    Pillow on Windows through GDI) are native or Windows-only, and no pure-Python EMF renderer exists under an
    MIT or AGPL-compatible licence (`pyemf` is GPL-2 and writes EMF, it does not draw one). So the board
    keeps what it can say truthfully: the file is a real EMF of this size, and how to get a picture of it.
    """
    if len(data) > MAX_EMF_BYTES:
        _refuse(413, f"That EMF file is larger than {MAX_EMF_BYTES // 1_000_000} MB.")
    if len(data) < 88:
        _refuse(422, "That isn't an EMF file: it is too short to have a header.")
    rec_type, rec_size = struct.unpack_from("<II", data, 0)
    signature = struct.unpack_from("<I", data, 40)[0]
    if rec_type != 1 or signature != 0x464D4520 or rec_size < 88 or rec_size > len(data):
        _refuse(422, "That isn't an EMF file: its header is not an EMF header.")
    left, top, right, bottom = struct.unpack_from("<iiii", data, 8)
    width, height = max(1, right - left + 1), max(1, bottom - top + 1)
    return {
        "kind": "emf",
        "width": min(width, 20_000),
        "height": min(height, 20_000),
        "bytes": len(data),
        "message": "A browser cannot draw an EMF, so it was not placed as a picture. Open it in Inkscape or LibreOffice, save it as SVG or PNG, then insert that.",
    }


# --- The door -------------------------------------------------------------------------------------------------


def detect(text: str) -> str:
    """Which reader a pasted or chosen text is for."""
    head = text.lstrip()[:4096].lower()
    if "<graphml" in head or ("<?xml" in head and "graphml" in text[:20000].lower()):
        return "graphml"
    if head.startswith(("{", "[")):
        return "miro"
    if "@startuml" in head or plantuml_kind(_pu_lines(text[:200_000])):
        return "plantuml"
    return ""


def convert(fmt: str, content: str | None, data_b64: str | None) -> dict:
    if fmt == "emf" or (fmt == "auto" and data_b64):
        try:
            raw = base64.b64decode(data_b64 or "", validate=True)
        except ValueError:
            _refuse(422, "That EMF file did not arrive intact.")
        return inspect_emf(raw)
    text = content or ""
    if fmt == "auto":
        fmt = detect(text)
        if not fmt:
            _refuse(422, "That is not GraphML, Miro JSON or PlantUML.")
    readers = {"graphml": parse_graphml, "miro": parse_miro, "plantuml": parse_plantuml}
    return readers[fmt](text)
