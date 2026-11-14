"""An ask in the diagram builder for the mind map, timeline and sequence kinds (L-documents-27), a lazy sibling of
`diagram_ask` (the flowchart's) so the flowchart's ask pays nothing for it.

The builder sends the kind's blocks as a flat list: `{uid, type, text, parent, id, from, to}` (a mind map's root `r` and
branches `b`; a timeline's section `s`, period `p` and event `e`; a sequence's participant `a` with its `id`, and message
`m` from one participant id to another). A Gantt chart, pie chart, state, class and ER diagram join the same list
(L-documents-86): a Gantt section `s`, task `t` (its timing in `value`) and title `p`; a pie slice `s` (its number in `value`)
and title `p`; a state `s`, group `c` and transition `x`; a class `c`, member `m` and relation `r`; an ER entity `e`,
attribute `a` and relationship `r`. A relation's ends are resolved to block uids (a state's `[*]` stays itself), so the
builder looks nothing up by name. An ask comes back as short ops on that list, by rule with no model or written by
the model, and **untrusted by construction**: `checked` plays every op on a copy and keeps only those that apply, with
blocks resolved to uids so the builder needs no name matching. Five verbs: `add` (with a `type`), `rename`, `move`,
`set` (a slice's number, a task's timing) and `delete` (a block takes what is under it; a participant takes its messages;
a state, class or entity takes the relations that end in it).
"""

from __future__ import annotations

import copy
import re

from tessellate.ai.diagram_ask import ASK_CHARS, DESCRIBED_CHARS, MAX_BLOCKS, MAX_OPS, TEXT_CHARS, _clean, _CLAUSES, _LEAD, _one_spaced, fold, read_reply

__all__ = ["ASK_CHARS", "MAX_BLOCKS", "MAX_OPS", "TEXT_CHARS", "DESCRIBED_CHARS", "KINDS", "by_rule", "checked", "described", "prompt", "with_model"]

KINDS = ("mindmap", "timeline", "sequence", "gantt", "pie", "state", "class", "er")
#: What each kind can add, and where a new block may hang (the parent's type; "" is the top).
_ADD = {
    "mindmap": {"b": ("r", "b")},
    "timeline": {"s": ("",), "p": ("s", ""), "e": ("p",)},
    "sequence": {"a": ("",), "m": ("",)},
    "gantt": {"s": ("",), "t": ("s", ""), "p": ("",)},
    "pie": {"s": ("",), "p": ("",)},
    "state": {"s": ("c", ""), "x": ("c", "")},
    "class": {"c": ("",), "m": ("c",), "r": ("",)},
    "er": {"e": ("",), "a": ("e",), "r": ("",)},
}
_MOVE = {"mindmap": {"b": ("r", "b")}, "timeline": {"p": ("s", ""), "e": ("p",)}, "sequence": {}, "gantt": {"t": ("s", "")}, "pie": {}, "state": {"s": ("c", ""), "x": ("c", "")}, "class": {}, "er": {}}
#: The five chart kinds, what they call a relation, the blocks a relation may join, what a plain add makes, and what `set` changes.
_CHARTS = ("gantt", "pie", "state", "class", "er")
_REL = {"state": "x", "class": "r", "er": "r"}
_ENDS = {"state": ("s", "c"), "class": ("c",), "er": ("e",)}
_PLAIN = {"gantt": "t", "pie": "s", "state": "s", "class": "c", "er": "e"}
_SET = {"gantt": "t", "pie": "s"}
_START = ("start", "end", "finish", "[*]")
NOT_READ = "That did not read as a change. Try “add Rent under Budget” or “rename Hiring to Recruiting”."

_PROMPTS = {
    "mindmap": "a mind map. Blocks: r root, b branch. Ops: {\"op\":\"add\",\"type\":\"b\",\"text\",\"parent\"}; {\"op\":\"move\",\"target\",\"parent\"}",
    "timeline": "a timeline. Blocks: s section, p period (its date or span is the text), e event. Ops: {\"op\":\"add\",\"type\":\"s|p|e\",\"text\",\"parent\"} (a period's parent is a section or empty, an event's is a period); {\"op\":\"move\",\"target\",\"parent\"}",
    "gantt": "a Gantt chart. Blocks: s section, t task (its timing is value, as in 3d or after a1, 5d), p title. Ops: {\"op\":\"add\",\"type\":\"s|t|p\",\"text\",\"parent\",\"value\"} (a task's parent is a section or empty); {\"op\":\"set\",\"target\",\"value\"}; {\"op\":\"move\",\"target\",\"parent\"}",
    "pie": "a pie chart. Blocks: s slice (its number is value), p title. Ops: {\"op\":\"add\",\"type\":\"s|p\",\"text\",\"value\"}; {\"op\":\"set\",\"target\",\"value\"}",
    "state": "a state diagram. Blocks: s state, c group, x transition (its words are the label). Ops: {\"op\":\"add\",\"type\":\"s\",\"text\",\"parent\"} (parent a group or empty); {\"op\":\"add\",\"type\":\"x\",\"text\",\"from\",\"to\"} (states by uid or words, or [*] for the start or end); {\"op\":\"move\",\"target\",\"parent\"}",
    "class": "a class diagram. Blocks: c class, m member, r relation. Ops: {\"op\":\"add\",\"type\":\"c\",\"text\"}; {\"op\":\"add\",\"type\":\"m\",\"text\",\"parent\"} (a class); {\"op\":\"add\",\"type\":\"r\",\"text\",\"from\",\"to\"} (classes)",
    "er": "an ER diagram. Blocks: e entity, a attribute, r relationship. Ops: {\"op\":\"add\",\"type\":\"e\",\"text\"}; {\"op\":\"add\",\"type\":\"a\",\"text\",\"parent\"} (an entity); {\"op\":\"add\",\"type\":\"r\",\"text\",\"from\",\"to\"} (entities)",
    "sequence": "a sequence diagram. Blocks: a participant (use its id), m message. Ops: {\"op\":\"add\",\"type\":\"a\",\"text\"}; {\"op\":\"add\",\"type\":\"m\",\"text\",\"from\",\"to\"} (participant ids)",
}


#: A bare key in the shorthand above (`,"text","parent"}`): the 1.5B model copied it as written, which is not JSON, and the
#: whole reply was dropped (L-documents-100, class and ER). Each is written out as a key with an empty value.
_BARE_KEY = re.compile(r'(?<=[{,])"(\w+)"(?=[,}])')


def prompt(kind: str) -> str:
    text = f"You edit {_PROMPTS[kind]}; {{\"op\":\"rename\",\"target\",\"text\"}}; {{\"op\":\"delete\",\"target\"}}. Reply with JSON only: {{\"ops\": [...]}}, at most 12 ops, only what was asked. Name blocks by uid or by their words as listed."
    return _BARE_KEY.sub(lambda m: f'"{m.group(1)}":""', text)


class _Sim:
    def __init__(self, model: dict):
        model = copy.deepcopy(model or {})
        self.nodes = [n for n in model.get("nodes") or [] if isinstance(n, dict) and n.get("uid")]
        self.made = 0

    def find(self, ref, types=None, by_id: bool = False):
        """The one block `ref` names (its uid, or its words folded), or None when it names none or several."""
        ref = str(ref or "").strip()
        pool = [n for n in self.nodes if not types or n.get("type") in types]
        for match in (lambda n: n["uid"] == ref, lambda n: by_id and n.get("id") == ref, lambda n: bool(fold(ref)) and fold(n.get("text")) == fold(ref)):
            hit = [n for n in pool if match(n)]
            if hit:
                return hit[0] if len(hit) == 1 else None
        return None

    def under(self, node: dict) -> list[dict]:
        out, todo = [], [node["uid"]]
        while todo:
            at = todo.pop()
            for n in self.nodes:
                if n.get("parent") == at and n not in out:
                    out.append(n)
                    todo.append(n["uid"])
        return out


def _parent_uid(sim: _Sim, ref, kinds: tuple):
    """The parent block's uid, "" for the top, or None when it cannot hold the block."""
    if not str(ref or "").strip():
        root = next((n for n in sim.nodes if n.get("type") == "r"), None)
        return root["uid"] if root else ("" if "" in kinds else None)
    found = sim.find(ref, tuple(k for k in kinds if k))
    return found["uid"] if found else None


def _type_of(kind: str, op: dict, parent) -> str:
    """The block type an add makes: the one asked for when this kind has it, else the one its parent implies."""
    if op.get("type") in _ADD[kind]:
        return op["type"]
    if kind == "timeline":
        return {"s": "p", "p": "e"}.get(parent["type"] if parent else "", "s")
    if kind in _CHARTS:
        return _REL[kind] if kind in _REL and op.get("from") else _PLAIN[kind]
    return {"mindmap": "b", "sequence": "m" if op.get("from") else "a"}[kind]


def _add_sequence(sim: _Sim, op: dict, kind_type: str, text: str, out: dict, new: dict) -> bool:
    if kind_type == "a":
        if any(fold(n.get("text")) == fold(text) for n in sim.nodes if n.get("type") == "a"):
            return False
        new["id"] = re.sub(r"\W+", "_", text)[:30] or "P"
        return True
    who = [sim.find(op.get(k), ("a",), by_id=True) for k in ("from", "to")]
    if not all(who):
        return False
    out |= {"from": who[0]["id"], "to": who[1]["id"]}
    new |= {"from": who[0]["id"], "to": who[1]["id"]}
    return True


def _value(kind: str, raw) -> str | None:  # noqa: ANN001
    """A slice's number (above zero) or a task's timing, as written; None when it is neither."""
    text = _clean(raw, 40)
    if kind == "pie":
        return text if re.fullmatch(r"\d+(?:\.\d+)?", text) and float(text) > 0 else None
    return text or None


def _end(kind: str, sim: _Sim, ref) -> str | None:  # noqa: ANN001
    """A relation's end as a uid (a state's start or end mark stays `[*]`), or None when it names no block."""
    if kind == "state" and str(ref or "").strip().lower() in _START:
        return "[*]"
    found = sim.find(ref, _ENDS[kind], by_id=True)
    return found["uid"] if found else None


def _add_relation(kind: str, sim: _Sim, op: dict, out: dict, new: dict) -> bool:
    ends = [_end(kind, sim, op.get(k)) for k in ("from", "to")]
    if None in ends:
        return False
    out |= {"from": ends[0], "to": ends[1]}
    new |= {"from": ends[0], "to": ends[1]}
    return True


def _add_value(kind: str, op: dict, out: dict, new: dict) -> bool:
    value = _value(kind, op.get("value") if op.get("value") not in (None, "") else ("10" if kind == "pie" else "3d"))
    if value is None:
        return False
    out["value"] = new["value"] = value
    return True


def _chart_parent(kind: str, sim: _Sim, op: dict, kind_type: str, out: dict, new: dict) -> bool:
    asked = str(op.get("parent") or "").strip()
    parents = _ADD[kind][kind_type]
    found = sim.find(asked, tuple(k for k in parents if k)) if asked else None
    if (asked and not found) or (not asked and "" not in parents):
        return False
    if found:
        out["parent"] = new["parent"] = found["uid"]
    return True


def _chart_name(kind: str, sim: _Sim, kind_type: str, text: str, new: dict) -> bool:
    """A state, class or entity is named once; its id is what a relation will carry."""
    if any(fold(n.get("text")) == fold(text) for n in sim.nodes if n.get("type") == kind_type):
        return False
    new["id"] = re.sub(r"\W+", "_", text)[:30] if kind == "state" else text
    return True


def _add_chart(kind: str, sim: _Sim, op: dict, kind_type: str, text: str, out: dict, new: dict) -> bool:
    if not _chart_parent(kind, sim, op, kind_type, out, new):
        return False
    if kind_type == _REL.get(kind):
        return _add_relation(kind, sim, op, out, new)
    if kind_type in _ENDS.get(kind, ()) and not _chart_name(kind, sim, kind_type, text, new):
        return False
    return _add_value(kind, op, out, new) if (kind, kind_type) in (("pie", "s"), ("gantt", "t")) else True


def _place(kind: str, sim: _Sim, op: dict, kind_type: str, text: str, out: dict, new: dict) -> bool:
    """Whether the new block fits where the kind keeps it; `out` and `new` take its parent, ends and value."""
    if kind in _CHARTS:
        return kind_type in _ADD[kind] and _add_chart(kind, sim, op, kind_type, text, out, new)
    if kind == "sequence":
        return _add_sequence(sim, op, kind_type, text, out, new)
    asked = str(op.get("parent") or "").strip()
    up = _parent_uid(sim, asked, _ADD[kind][kind_type]) if (asked or kind_type != "s") else ""
    if up is None or (kind_type == "s" and asked):
        return False
    out["parent"] = new["parent"] = up
    return True


def _add(kind: str, sim: _Sim, op: dict) -> dict | None:
    text = _clean(op.get("text"), TEXT_CHARS)
    asked = str(op.get("parent") or "").strip()
    parent = sim.find(asked) if asked else None
    kind_type = _type_of(kind, op, parent)
    if (not text and kind_type != _REL.get(kind)) or len(sim.nodes) >= MAX_BLOCKS:
        return None
    out: dict = {"op": "add", "type": kind_type, "text": text}
    new = {"uid": f"n{sim.made + 1}", "type": kind_type, "text": text}
    if not _place(kind, sim, op, kind_type, text, out, new):
        return None
    sim.made += 1
    sim.nodes.append(new)
    return out


def _rename(kind: str, sim: _Sim, op: dict) -> dict | None:
    target, text = sim.find(op.get("target")), _clean(op.get("text"), TEXT_CHARS)
    if not target or not text or fold(text) == fold(target.get("text")):
        return None
    target["text"] = text
    return {"op": "rename", "target": target["uid"], "text": text}


def _move(kind: str, sim: _Sim, op: dict) -> dict | None:
    target = sim.find(op.get("target"))
    rule = _MOVE[kind].get(target.get("type")) if target else None
    if not rule:
        return None
    up = _parent_uid(sim, op.get("parent"), rule) if (str(op.get("parent") or "").strip() or "" not in rule) else ""
    if up is None or up == target.get("parent") or up == target["uid"] or any(n["uid"] == up for n in sim.under(target)):
        return None
    target["parent"] = up
    return {"op": "move", "target": target["uid"], "parent": up}


def _set(kind: str, sim: _Sim, op: dict) -> dict | None:
    target = sim.find(op.get("target"), (_SET[kind],)) if kind in _SET else None
    value = _value(kind, op.get("value")) if target else None
    if not target or value is None or value == target.get("value"):
        return None
    target["value"] = value
    return {"op": "set", "target": target["uid"], "value": value}


def _joined(kind: str, sim: _Sim, gone: list) -> list:
    """What goes with the target: the relations that end in a state, class or entity (their ends are uids)."""
    if kind not in _ENDS:
        return []
    ids = {n["uid"] for n in gone if n.get("type") in _ENDS[kind]} | {n.get("id") for n in gone if n.get("type") in _ENDS[kind]}
    return [n for n in sim.nodes if n.get("type") == _REL[kind] and (n.get("from") in ids or n.get("to") in ids) and n not in gone]


def _delete(kind: str, sim: _Sim, op: dict) -> dict | None:
    target = sim.find(op.get("target"))
    if not target or (target.get("type") == "r" and kind not in _CHARTS):
        return None
    gone = [target, *sim.under(target)]
    if kind == "sequence" and target.get("type") == "a":
        gone += [n for n in sim.nodes if n.get("type") == "m" and target.get("id") in (n.get("from"), n.get("to"))]
    gone += _joined(kind, sim, gone)
    sim.nodes = [n for n in sim.nodes if n not in gone]
    return {"op": "delete", "target": target["uid"]}


_VERBS = {"add": _add, "rename": _rename, "move": _move, "set": _set, "delete": _delete}


def checked(kind: str, ops, model: dict) -> tuple[list[dict], int]:
    """The ops that apply, in order, as normalised ops, and how many were not kept."""
    if kind not in KINDS:
        return [], len(ops) if isinstance(ops, list) else 0
    sim, kept, dropped = _Sim(model), [], 0
    for op in ops if isinstance(ops, list) else []:
        verb = _VERBS.get(op.get("op")) if isinstance(op, dict) else None
        done = verb(kind, sim, op) if verb and len(kept) < MAX_OPS else None
        if done:
            kept.append(done)
        else:
            dropped += 1
    return kept, dropped


# --- by rule ---------------------------------------------------------------------------------------

_R = re.IGNORECASE
_UNDER = r"(?:under|to|into|in|below|on)"
_SET_RULE = (re.compile(r"^set\s+(.+?)\s+to\s+(.+)$", _R), lambda h: {"op": "set", "target": h[1], "value": h[2]})


def _relation(word: str, kind_type: str, kind: str) -> tuple:
    """`add a transition from A to B called words`: the rule for a relation block, its ends and optional words."""
    pattern = re.compile(rf"^add\s+(?:an?\s+)?{word}\s+(?:from\s+)?(.+?)\s+to\s+(.+?)(?:\s+(?:called|labelled|labeled|named|saying|:)\s+(.+))?$", _R)
    return pattern, lambda h: {"op": "add", "type": kind_type, "text": h[3] or "", "from": h[1], "to": h[2]}


_RULES = {
    "mindmap": (
        (re.compile(rf"^add\s+(?:a\s+)?(?:branch\s+)?(.+?)\s+{_UNDER}\s+(.+)$", _R), lambda h: {"op": "add", "type": "b", "text": h[1], "parent": h[2]}),
        (re.compile(r"^add\s+(?:a\s+)?(?:branch\s+)?(.+)$", _R), lambda h: {"op": "add", "type": "b", "text": h[1], "parent": ""}),
    ),
    "timeline": (
        (re.compile(r"^add\s+(?:a\s+)?section\s+(.+)$", _R), lambda h: {"op": "add", "type": "s", "text": h[1], "parent": ""}),
        (re.compile(rf"^add\s+(?:a\s+)?period\s+(.+?)\s+{_UNDER}\s+(.+)$", _R), lambda h: {"op": "add", "type": "p", "text": h[1], "parent": h[2]}),
        (re.compile(r"^add\s+(?:a\s+)?period\s+(.+)$", _R), lambda h: {"op": "add", "type": "p", "text": h[1], "parent": ""}),
        (re.compile(rf"^add\s+(?:an\s+)?event\s+(.+?)\s+{_UNDER}\s+(.+)$", _R), lambda h: {"op": "add", "type": "e", "text": h[1], "parent": h[2]}),
    ),
    "gantt": (
        (re.compile(r"^add\s+(?:a\s+)?section\s+(.+)$", _R), lambda h: {"op": "add", "type": "s", "text": h[1]}),
        (re.compile(rf"^add\s+(?:a\s+)?task\s+(.+?)\s+{_UNDER}\s+(.+)$", _R), lambda h: {"op": "add", "type": "t", "text": h[1], "parent": h[2]}),
        (re.compile(r"^add\s+(?:a\s+)?task\s+(.+)$", _R), lambda h: {"op": "add", "type": "t", "text": h[1]}),
        (re.compile(r"^add\s+(?:a\s+)?title\s+(.+)$", _R), lambda h: {"op": "add", "type": "p", "text": h[1]}),
        _SET_RULE,
    ),
    "pie": (
        (re.compile(r"^add\s+(?:a\s+)?(?:slice\s+)?(.+?)\s+(?:(?:at|of|with|=|:)\s*|)(\d+(?:\.\d+)?)$", _R), lambda h: {"op": "add", "type": "s", "text": h[1], "value": h[2]}),
        (re.compile(r"^add\s+(?:a\s+)?slice\s+(.+)$", _R), lambda h: {"op": "add", "type": "s", "text": h[1]}),
        (re.compile(r"^add\s+(?:a\s+)?title\s+(.+)$", _R), lambda h: {"op": "add", "type": "p", "text": h[1]}),
        _SET_RULE,
    ),
    "state": (
        (re.compile(rf"^add\s+(?:a\s+)?state\s+(.+?)\s+{_UNDER}\s+(.+)$", _R), lambda h: {"op": "add", "type": "s", "text": h[1], "parent": h[2]}),
        (re.compile(r"^add\s+(?:a\s+)?state\s+(.+)$", _R), lambda h: {"op": "add", "type": "s", "text": h[1]}),
        _relation("transition", "x", "state"),
    ),
    "class": (
        (re.compile(r"^add\s+(?:a\s+)?class\s+(.+)$", _R), lambda h: {"op": "add", "type": "c", "text": h[1]}),
        (re.compile(rf"^add\s+(?:a\s+)?(?:member|field|method)\s+(.+?)\s+{_UNDER}\s+(.+)$", _R), lambda h: {"op": "add", "type": "m", "text": h[1], "parent": h[2]}),
        _relation("relation", "r", "class"),
    ),
    "er": (
        (re.compile(r"^add\s+(?:an?\s+)?entity\s+(.+)$", _R), lambda h: {"op": "add", "type": "e", "text": h[1]}),
        (re.compile(rf"^add\s+(?:an?\s+)?attribute\s+(.+?)\s+{_UNDER}\s+(.+)$", _R), lambda h: {"op": "add", "type": "a", "text": h[1], "parent": h[2]}),
        _relation("relationship", "r", "er"),
    ),
    "sequence": (
        (re.compile(r"^add\s+(?:a\s+)?(?:participant|actor)\s+(.+)$", _R), lambda h: {"op": "add", "type": "a", "text": h[1]}),
        (re.compile(r"^add\s+(?:a\s+)?message\s+(.+?)\s+from\s+(.+?)\s+to\s+(.+)$", _R), lambda h: {"op": "add", "type": "m", "text": h[1], "from": h[2], "to": h[3]}),
    ),
}
_COMMON = (
    (re.compile(r"^rename\s+(.+?)\s+to\s+(.+)$", _R), lambda h: {"op": "rename", "target": h[1], "text": h[2]}),
    (re.compile(rf"^move\s+(.+?)\s+{_UNDER}\s+(.+)$", _R), lambda h: {"op": "move", "target": h[1], "parent": h[2]}),
    (re.compile(r"^(?:delete|remove)\s+(.+)$", _R), lambda h: {"op": "delete", "target": h[1]}),
)


def by_rule(kind: str, ask: str, model: dict) -> dict:
    """The ask read by rule, clause by clause, each checked against the blocks as the earlier ones left them."""
    sim, kept, dropped, unread = _Sim(model), [], 0, 0
    rules = _COMMON + _RULES.get(kind, ())
    for clause in [c for c in _CLAUSES.split(_one_spaced(str(ask or "")[:ASK_CHARS])) if c.strip()]:
        clause = _LEAD.sub("", clause.strip()).rstrip(".")
        hit = next(((m, make) for pattern, make in rules if (m := pattern.match(clause))), None)
        if not hit or kind not in KINDS:
            unread += 1
            continue
        op = hit[1](hit[0])
        done = _VERBS[op["op"]](kind, sim, op) if len(kept) < MAX_OPS else None
        if done:
            kept.append(done)
        else:
            dropped += 1
    said = "" if kept else (NOT_READ if unread and not dropped else "No block in the diagram fits that." if dropped else NOT_READ)
    return {"ops": kept, "said": said, "by": "rule", "dropped": dropped}


# --- with the model --------------------------------------------------------------------------------


def described(model: dict) -> str:
    """The blocks as the model reads them: `u4: Salaries (b) in u2`, `u3: Hello (m) Alice -> Bob`."""
    out, size = [], 0
    for n in _Sim(model).nodes[:MAX_BLOCKS]:
        line = f"{n['uid']}: {_clean(n.get('text'), 60)} ({n.get('type')})"
        if n.get("type") == "m":
            line += f" {_clean(n.get('from'), 30)} -> {_clean(n.get('to'), 30)}"
        elif n.get("type") == "a":
            line += f" id {_clean(n.get('id'), 30)}"
        if n.get("parent"):
            line += f" in {n['parent']}"
        if size + len(line) + 1 > DESCRIBED_CHARS:
            break
        out.append(line)
        size += len(line) + 1
    return "\n".join(out)


def with_model(kind: str, ask: str, model: dict, model_name: str, provider) -> dict:  # noqa: ANN001
    """The ask written as ops by the model, checked; the rule's answer when nothing it wrote applies."""
    from tessellate.ai.ollama_client import OllamaError

    try:
        reply = provider.chat(model_name, [
            {"role": "system", "content": prompt(kind)},
            {"role": "user", "content": f"Blocks:\n{described(model)}\n\nAsk: {str(ask)[:ASK_CHARS]}"},
        ])
    except OllamaError:
        reply = {}
    kept, dropped = checked(kind, read_reply((reply or {}).get("content") or ""), model)
    if kept:
        return {"ops": kept, "said": "", "by": "model", "dropped": dropped}
    ruled = by_rule(kind, ask, model)
    return {**ruled, "said": ("The model's answer could not be used, so this is by rule. " + ruled["said"]).strip()}
