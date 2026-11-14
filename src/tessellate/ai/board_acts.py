"""Acts on the whiteboard, mind maps, documents and skills the model's write tools already reach (L-chat-60).

One sentence is one card that waits for Confirm, over a tool the agent has: draw a shape, place a library
item, connect two cards, move, reword or take an item off the default whiteboard, add a node to a named mind
map or cross-link two of its nodes, draw a small tree of notes, write a document, save a skill, check what it
learned. The reader finds the sentence; the planner resolves the names against the notebook. Nothing here
writes except the three steps `run_step` owns, which are the Undo of a link, a node and a check (no tool the
model is offered does those). `commands.py` lends its card helpers (`_parity_helpers`).
"""

from __future__ import annotations

import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

INTENTS = frozenset({
    "board_shape", "board_library", "board_link", "board_move", "board_words", "board_remove", "map_node", "map_link",
    "make_diagram", "make_document", "make_skill", "check_learned",
})
def words() -> frozenset[str]:
    """The words of these acts' own phrases ("card", "node", "mind", "learned"): a real word one slip from one is read as it
    ("the Trips mid map", "connect the cad to"), as `parity_acts.words` does for its acts."""
    from tessellate.ai import act_registry

    return frozenset(w for a in act_registry.ACTS.values() if a.intent in INTENTS for w in re.findall(r"[a-z]{4,}", f"{a.verb} {a.label} {a.example}".lower()))


#: The steps `run_step` runs itself: the Undo of a link, a map node and a check of what it learned.
OWN_STEPS = frozenset({"drop_board_link", "drop_map_node", "undo_learned_check"})

_LEAD = r"^(?:(?:please|pls|can you|could you|would you)\s+)*"
_ON = r"(?:on|onto|in|into|to)\s+(?:the |my )?(?:white)?board"
_OFF = r"(?:off|from|out of)\s+(?:the |my )?(?:white)?board"
_KINDS = r"(?P<k>shape|sticky(?: note)?|text ?box|frame|card)"
_SHAPE_WORDS = {"rectangle": "rect", "box": "rect", "rect": "rect", "ellipse": "ellipse", "circle": "ellipse", "diamond": "diamond", "frame": "frame"}
_SHAPE = re.compile(
    rf"{_LEAD}(?:draw|add|put|make)\s+(?:me\s+)?(?:a |an |the )?(?P<s>rectangle|box|ellipse|circle|diamond|frame)"
    rf"(?:\s+(?:that says|saying|with|called|labelled|labeled|titled|named|reading)\s+(?P<t>.+?))?\s+{_ON}$", re.I)
_LIBRARY = re.compile(rf"{_LEAD}(?:put|place|add|drop)\s+(?:a |an |the )?(?P<q>.+?)\s+(?:shape |symbol |item |frame )?from the (?:shape )?library\s+{_ON}$", re.I)
_LINK = re.compile(rf"{_LEAD}(?:connect|link|join)\s+(?:the )?(?P<a>.+?)\s+card\s+(?:to|with|and)\s+(?:the )?(?P<b>.+?)\s+card(?:\s+on\s+(?:the |my )?(?:white)?board)?$", re.I)
_REMOVE = re.compile(rf"{_LEAD}(?:take|remove|delete|clear|get)\s+(?:the )?(?P<n>.+?)\s+{_KINDS}\s+{_OFF}$", re.I)
_MOVE = re.compile(rf"{_LEAD}move\s+(?:the )?(?P<n>.+?)\s+{_KINDS}\s+(?:on|in)\s+(?:the |my )?(?:white)?board\s+(?:to the |a bit |further |towards the )?(?P<d>left|right|up|down)$", re.I)
_WORDS = re.compile(rf"{_LEAD}(?:change|set|reword|rename)\s+(?:the )?(?P<n>.+?)\s+{_KINDS}\s+(?:on|in)\s+(?:the |my )?(?:white)?board\s+to\s+(?:say\s+)?(?P<t>.+)$", re.I)
_MAP = r"(?:the |my )?(?P<m>.+?)\s+mind ?map"
_NODE_UNDER = re.compile(rf"{_LEAD}add\s+(?:a |the )?(?:node|topic|branch)\s+(?:called |named )?(?P<t>.+?)\s+(?:under|below|beneath|to)\s+(?:the )?(?P<p>.+?)\s+(?:on|in)\s+{_MAP}$", re.I)
_NODE_ROOT = re.compile(rf"{_LEAD}add\s+(?:a |the )?(?:node|topic|branch)\s+(?:called |named )?(?P<t>.+?)\s+(?:on|in|to)\s+{_MAP}$", re.I)
_CROSS = re.compile(rf"{_LEAD}(?:cross-?link|link|connect)\s+(?:the )?(?P<a>.+?)\s+(?:to|with|and)\s+(?:the )?(?P<b>.+?)\s+(?:on|in)\s+{_MAP}$", re.I)
_DIAGRAM = re.compile(rf"{_LEAD}draw\s+(?:me\s+)?(?:a |the )?(?:diagram|tree)\s+of\s+(?P<r>.+?)\s+(?:with|showing|from|made of)\s+(?P<k>.+?)(?:\s+{_ON})?$", re.I)
_DOCUMENT = re.compile(
    rf"{_LEAD}(?:write|create|make|start|draft)\s+(?:me\s+)?(?:a |the )?(?:new )?(?:document|doc|report|essay|write-?up)\s+(?:called|named|titled|about|on)\s+(?P<t>[^:]+?)\s*:\s*(?P<b>.+)$", re.I)
_SKILL = re.compile(rf"{_LEAD}save\s+(?:a |the )?(?:new )?skill\s+(?:called|named)\s+(?P<n>.+?)\s+(?:that|which|to)\s+(?P<p>.+)$", re.I)
_CHECK = re.compile(rf"{_LEAD}(?:check|audit|re-?read)\s+what\s+(?:you|it|atlas)(?:['’]ve| have| has| had)?\s+learned$", re.I)
_STEP = 200
_SPLIT = re.compile(r"\s*(?:,|;|\band\b)\s*", re.I)


def _name(text: str) -> str:
    return " ".join(text.split()).strip(" .!?\"'“”‘’")


def _shaped(found: re.Match) -> dict:
    return {"shape": _SHAPE_WORDS[found.group("s").lower()], "text": _name(found.group("t") or "")}


def _titled(found: re.Match) -> dict:
    return {"title": _name(found.group("t")), "body": found.group("b").strip()}


def _tree(found: re.Match) -> dict | None:
    kids = [_name(k) for k in _SPLIT.split(found.group("k")) if _name(k)]
    return {"root": _name(found.group("r")), "children": kids} if kids else None


def _aimed(found: re.Match) -> dict:
    return {"name": _name(found.group("n")), "kind": _kind(found.group("k"))}


def _node(found: re.Match) -> dict:
    return {"text": _name(found.group("t")), "parent": _name(found.group("p")) if "p" in found.re.groupindex else "", "map": _name(found.group("m"))}


#: (pattern, intent, the fields it reads), tried in order.
_READERS = (
    (_CHECK, "check_learned", lambda f: {}),
    (_SKILL, "make_skill", lambda f: {"name": _name(f.group("n")), "prompt": _name(f.group("p"))}),
    (_DOCUMENT, "make_document", _titled),
    (_SHAPE, "board_shape", _shaped),
    (_LIBRARY, "board_library", lambda f: {"query": _name(f.group("q"))}),
    (_MOVE, "board_move", lambda f: {**_aimed(f), "direction": f.group("d").lower()}),
    (_WORDS, "board_words", lambda f: {**_aimed(f), "text": _name(f.group("t"))}),
    (_REMOVE, "board_remove", _aimed),
    (_LINK, "board_link", lambda f: {"a": _name(f.group("a")), "b": _name(f.group("b"))}),
    (_DIAGRAM, "make_diagram", _tree),
    (_NODE_UNDER, "map_node", _node),
    (_NODE_ROOT, "map_node", _node),
    (_CROSS, "map_link", lambda f: {"a": _name(f.group("a")), "b": _name(f.group("b")), "map": _name(f.group("m"))}),
)


def read(text: str) -> dict | None:
    """The act `text` is, or None."""
    for pattern, intent, fields in _READERS:
        if found := pattern.match(text):
            got = fields(found)
            return None if got is None else {"intent": intent, **got}
    return None


def _kind(word: str) -> str:
    word = word.lower()
    return "card" if word == "card" else "shape" if word == "shape" else "frame" if word == "frame" else "text"


# --- resolving names -------------------------------------------------------------------------------


def _pick(rows: list[tuple], wanted: str, what: str) -> tuple[tuple | None, str]:
    """The one row whose name is `wanted` (exact, then contained, case folded), else (None, the question or the refusal)."""
    low = wanted.casefold()
    near = [r for r in rows if r[0].casefold() == low] or [r for r in rows if low in r[0].casefold()]
    if len(near) == 1:
        return near[0], ""
    if not near:
        return None, f"I found no {what} called “{wanted}”."
    return None, "Which one: " + " or ".join(f"“{r[0]}”" for r in near[:3]) + "?"


def _board_items(session: Session, kinds: str) -> list[tuple]:
    """(words, tool kind, id) for the items on the default whiteboard of the kind said."""
    from tessellate.core.database import Entry, WhiteboardNode, WhiteboardObject, WhiteboardSketch

    rows: list[tuple] = []
    if kinds == "card":
        for node in session.scalars(select(WhiteboardNode).where(WhiteboardNode.board_id.is_(None))):
            entry = session.get(Entry, node.entry_id)
            if entry is not None and not entry.is_private:
                rows.append((_first_line(entry.content), "card", node.id))
        return rows
    if kinds == "shape":
        for sketch in session.scalars(select(WhiteboardSketch).where(WhiteboardSketch.board_id.is_(None))):
            data = _data(sketch)
            if not str(data.get("type", "")).startswith("link-") and data.get("label"):
                rows.append((str(data["label"]), "shape", sketch.id))
        return rows
    objects = session.scalars(select(WhiteboardObject).where(WhiteboardObject.board_id.is_(None), WhiteboardObject.kind.in_(("text", "frame"))))
    pairs = [(o, str(_data(o).get("content") or "")) for o in objects if (o.kind == "frame") == (kinds == "frame")]
    rows.extend((_first_line(words), "object", o.id) for o, words in pairs if words)
    return rows


def _data(row) -> dict:  # noqa: ANN001
    try:
        data = json.loads(row.data or "{}")
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _first_line(text: str) -> str:
    line = next((ln.strip() for ln in (text or "").splitlines() if ln.strip()), "")
    return line.lstrip("#").strip()[:80]


def _map_nodes(session: Session, title: str) -> tuple[int | None, list[tuple], str]:
    """The mind map called `title`: (its note id, [(words, node id)], "") or (None, [], why)."""
    from tessellate.core.database import Entry, WhiteboardObject

    maps = [(_first_line(e.content), e.id) for e in session.scalars(select(Entry).where(Entry.is_board.is_(True), Entry.deleted_at.is_(None), Entry.is_private.is_(False)))]
    found, why = _pick(maps, title, "mind map")
    if found is None:
        return None, [], why
    nodes = [(str(_data(o).get("content") or ""), o.id) for o in session.scalars(select(WhiteboardObject).where(WhiteboardObject.board_id == found[1]))]
    return found[1], [n for n in nodes if n[0]], ""


# --- plan ------------------------------------------------------------------------------------------


def _step(tool: str, **arguments) -> list[dict]:
    return [{"name": tool, "arguments": arguments}]


def _say(c: dict, label: str, steps: list[dict], items: list[str] | None = None) -> dict:
    return {"line": c["confirm"](label), "card": c["card"](label, steps, [], items or [])}


def _plan_library(session: Session, parsed: dict, c: dict) -> dict:
    from tessellate.ai import tools

    found = tools.execute_tool(session, "list_library", {"query": parsed["query"], "limit": 8}).get("items") or []
    #: Several sets hold a shape of one name (Decision is in three): the first is the one placed.
    pick, why = _pick(list({i["name"].casefold(): (i["name"], i["ref"]) for i in reversed(found)}.values())[::-1], parsed["query"], "library item")
    if pick is None:
        return {"line": why if found else f"I found nothing called “{parsed['query']}” in the library."}
    return _say(c, f"Put “{pick[0]}” from the library on the whiteboard", _step("place_library_item", ref=pick[1]))


def _plan_item(session: Session, parsed: dict, c: dict) -> dict:
    """Move, reword or take off one item of the default whiteboard."""
    from tessellate.ai.tools import board_edit

    rows = _board_items(session, parsed["kind"])
    pick, why = _pick(rows, parsed["name"], "item on the whiteboard")
    if pick is None:
        return {"line": why}
    kind, item_id = pick[1], pick[2]
    if parsed["intent"] == "board_remove":
        return _say(c, f"Take “{pick[0]}” off the whiteboard", _step("delete_board_item", kind=kind, item_id=item_id))
    if parsed["intent"] == "board_words":
        if kind == "card":
            return {"line": "A card shows its note, so change the note itself to change what it says."}
        return _say(c, f"Change “{pick[0]}” on the whiteboard to “{parsed['text']}”", _step("edit_board_item", kind=kind, item_id=item_id, text=parsed["text"]))
    row = board_edit._load(session, kind, item_id)
    x, y = board_edit._box(kind, row)
    dx, dy = {"left": (-_STEP, 0), "right": (_STEP, 0), "up": (0, -_STEP), "down": (0, _STEP)}[parsed["direction"]]
    return _say(c, f"Move “{pick[0]}” {parsed['direction']} on the whiteboard", _step("move_board_item", kind=kind, item_id=item_id, x=x + dx, y=y + dy))


def _plan_link(session: Session, parsed: dict, c: dict) -> dict:
    rows = _board_items(session, "card")
    first, why = _pick(rows, parsed["a"], "card on the whiteboard")
    if first is None:
        return {"line": why}
    second, why = _pick(rows, parsed["b"], "card on the whiteboard")
    if second is None:
        return {"line": why}
    if first[2] == second[2]:
        return {"line": "That is one card; a link joins two."}
    return _say(c, f"Connect “{first[0]}” to “{second[0]}” on the whiteboard", _step("add_whiteboard_link", from_card_id=first[2], to_card_id=second[2]))


def _plan_map(session: Session, parsed: dict, c: dict) -> dict:
    board_id, nodes, why = _map_nodes(session, parsed["map"])
    if board_id is None:
        return {"line": why}
    if parsed["intent"] == "map_link":
        first, why = _pick(nodes, parsed["a"], "node")
        second, why2 = _pick(nodes, parsed["b"], "node") if first else (None, why)
        if first is None or second is None:
            return {"line": why if first is None else why2}
        return _say(c, f"Link “{first[0]}” to “{second[0]}” on the “{parsed['map']}” mind map", _step("link_map_nodes", board_id=board_id, from_id=first[1], to_id=second[1]))
    args = {"board_id": board_id, "text": parsed["text"]}
    if parsed["parent"]:
        parent, why = _pick(nodes, parsed["parent"], "node")
        if parent is None:
            return {"line": why}
        args["parent_id"] = parent[1]
    return _say(c, f"Add “{parsed['text']}” to the “{parsed['map']}” mind map", _step("add_map_node", **args))


def _plan_diagram(parsed: dict, c: dict) -> dict:
    nodes = [{"ref": "r", "title": parsed["root"]}] + [{"ref": f"c{i}", "title": kid, "parent_ref": "r"} for i, kid in enumerate(parsed["children"][:12])]
    return _say(c, f"Draw “{parsed['root']}” with {len(nodes) - 1} notes under it on the whiteboard", _step("generate_diagram", nodes=nodes))


def plan(session: Session, parsed: dict, c: dict) -> dict:
    """The line and card for one of `INTENTS`. `c` is `commands`' lending (`commands._parity_helpers`)."""
    intent = parsed["intent"]
    if intent in ("board_move", "board_words", "board_remove"):
        return _plan_item(session, parsed, c)
    if intent == "board_shape":
        label = f"Draw a {parsed['shape'] if parsed['shape'] != 'rect' else 'rectangle'}{' saying “' + parsed['text'] + '”' if parsed['text'] else ''} on the whiteboard"
        return _say(c, label, _step("add_board_shape", shape=parsed["shape"], text=parsed["text"]))
    if intent == "board_library":
        return _plan_library(session, parsed, c)
    if intent == "board_link":
        return _plan_link(session, parsed, c)
    if intent in ("map_node", "map_link"):
        return _plan_map(session, parsed, c)
    if intent == "make_diagram":
        return _plan_diagram(parsed, c)
    if intent == "make_document":
        return _say(c, f"Save the document “{parsed['title']}”", _step("create_document", title=parsed["title"], content=parsed["body"]))
    if intent == "make_skill":
        return _say(c, f"Save the skill “{parsed['name']}”", _step("save_skill", name=parsed["name"], prompt=parsed["prompt"]))
    return _say(c, "Check what it has learned against your notes", _step("check_learned"))


# --- undo --------------------------------------------------------------------------------------------


def undo_for(name: str, args: dict, result: dict) -> dict | None:
    """The Undo of a step whose tool returns none: a link, a map node, a diagram."""
    if name in ("add_whiteboard_link", "link_map_nodes") and result.get("link_id") is not None:
        return {"tool": "drop_board_link", "arguments": {"id": result["link_id"]}}
    if name == "add_map_node" and result.get("node_id") is not None:
        return {"tool": "drop_map_node", "arguments": {"id": result["node_id"]}}
    if name == "check_learned" and result.get("run"):
        return {"tool": "undo_learned_check", "arguments": {"run": result["run"]}}
    if name == "generate_diagram":
        cards = result.get("cards") or []
        steps = [{"tool": "delete_board_item", "arguments": {"kind": "card", "item_id": row["card_id"]}} for row in cards]
        steps += [{"tool": "delete_note", "arguments": {"note_id": row["note_id"]}} for row in cards]
        return {"tool": "batch", "steps": steps}
    return None


def run_step(session: Session, name: str, args: dict) -> dict:
    """The steps this module owns (`OWN_STEPS`)."""
    from tessellate.core.database import WhiteboardObject, WhiteboardSketch

    if name == "undo_learned_check":
        from tessellate.ai import learned_audit_run

        return {"label": f"Put back {learned_audit_run.undo(session, str(args.get('run') or ''))} learned items"}
    model = WhiteboardSketch if name == "drop_board_link" else WhiteboardObject
    row = session.get(model, int(args.get("id") or 0))
    if row is None:
        return {"label": "It was already gone"}
    session.delete(row)
    session.commit()
    return {"label": "Took the link off the board" if name == "drop_board_link" else "Took the node off the map"}
