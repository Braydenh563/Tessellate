"""An ask in the diagram builder, as operations on its model (dgai-1110; the format is
docs/roadmap/agent-remaining/dgai-1110.md F1 to F5).

The owner, 2026-11-10: "the ai should be able to help you make it and make changes and suggest edits". "add a refund
step after In stock? No" or "rename Warehouse to Fulfilment" comes back as a short list of operations on the D1 model
(add, rename, join, nest, delete), the same verbs whether a rule read the words (no model) or the model wrote them, so
the builder previews, applies and names a version the same way for both.

**Untrusted by construction.** A model's reply is read as JSON and nothing else; `checked` plays every op on a copy of
the model and keeps only those that apply (a known verb, names that resolve, words cut, the block limit, at most
`MAX_OPS`). The builder applies what comes back through its own model functions, which refuse again.
"""

from __future__ import annotations

import copy
import json
import re

MAX_OPS = 12
#: The pane's own limits (diagram-ops.js `DGB_MAX` and `dgbRelabel`).
MAX_BLOCKS = 120
TEXT_CHARS = 120
LABEL_CHARS = 40
ASK_CHARS = 300
SHAPES = ("rect", "round", "stadium", "circle", "diamond", "hexagon", "cylinder", "parallelogram")
#: What the model is shown of the diagram: enough for a small window.
DESCRIBED_BLOCKS = 60
DESCRIBED_CHARS = 4000

ASK_PROMPT = (
    "You edit a flowchart. Reply with JSON only: {\"ops\": [...]}, at most 12 ops, only what was asked. Ops: "
    "{\"op\":\"add\",\"text\",\"shape\",\"after\",\"label\",\"group\"} (after: the block it follows; label: the "
    "arrow's words); {\"op\":\"rename\",\"target\",\"text\"} or {\"op\":\"rename\",\"from\",\"to\",\"text\"} for an "
    "arrow; {\"op\":\"join\",\"from\",\"to\",\"label\"}; {\"op\":\"nest\",\"target\",\"group\"} (\"\" lifts it out); "
    "{\"op\":\"delete\",\"target\"} or {\"op\":\"delete\",\"from\",\"to\"}. Name blocks by their words as listed. "
    "Shapes: rect, round, stadium, circle, diamond, hexagon, cylinder, parallelogram, group."
)


def fold(text: str) -> str:
    """A name as compared: case, spaces and punctuation folded ("In stock?" is "in stock")."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).split())


def _clean(text, limit: int) -> str:
    return " ".join(str(text or "").split())[:limit].strip() if isinstance(text, (str, int, float)) else ""


class _Sim:
    """The model as plain lists, to play ops on. A block added here is `new` and is named by its words."""

    def __init__(self, model: dict):
        model = copy.deepcopy(model or {})
        self.nodes = [n for n in model.get("nodes") or [] if isinstance(n, dict) and n.get("id")]
        self.groups = [g for g in model.get("subgraphs") or [] if isinstance(g, dict) and g.get("id")]
        self.edges = [e for e in model.get("edges") or [] if isinstance(e, dict)]
        self.made = 0

    def _words(self, item: dict) -> str:
        return item.get("text") if "text" in item else item.get("title", "")

    def find(self, ref, *, groups: bool = True, nodes: bool = True) -> dict | None:
        """The one block `ref` names: its id first, then its words folded; None for none or two."""
        ref = _clean(ref, TEXT_CHARS)
        if not ref:
            return None
        pool = (self.nodes if nodes else []) + (self.groups if groups else [])
        for item in pool:
            if not item.get("new") and item["id"] == ref:
                return item
        hits = [item for item in pool if fold(self._words(item)) == fold(ref)]
        return hits[0] if len(hits) == 1 and fold(ref) else None

    def name(self, item: dict) -> str:
        """How an op names a block: its id, or the words of one this batch added (the builder gives its id)."""
        return self._words(item) if item.get("new") else item["id"]

    def is_group(self, item: dict) -> bool:
        return any(item is g for g in self.groups)

    def inside(self, gid: str, group: dict) -> bool:
        at, hops = gid, 0
        while at and hops < 200:
            if at == group["id"]:
                return True
            at = next((g.get("parent") for g in self.groups if g["id"] == at), None)
            hops += 1
        return False

    def edge(self, a: dict, b: dict) -> dict | None:
        return next((e for e in self.edges if e.get("from") == a["id"] and e.get("to") == b["id"]), None)

    def fresh(self) -> str:
        self.made += 1
        return f"+{self.made}"


_MISSING = object()


def _optional(sim: _Sim, ref, **only):
    """None when no name was given, else the block it names, or `_MISSING` when nothing answers it."""
    if not ref:
        return None
    return sim.find(ref, **only) or _MISSING


def _add_group(sim: _Sim, op: dict, text: str) -> dict | None:
    parent = _optional(sim, op.get("group"), nodes=False)
    if parent is _MISSING:
        return None
    sim.groups.append({"id": sim.fresh(), "title": text, "parent": parent["id"] if parent else None, "new": True})
    return {"op": "add", "text": text, "shape": "group", "after": "", "label": "", "group": sim.name(parent) if parent else ""}


def _add(sim: _Sim, op: dict) -> dict | None:
    text = _clean(op.get("text"), TEXT_CHARS)
    shape = op.get("shape") if op.get("shape") in SHAPES + ("group",) else "rect"
    if not text or shape == "group":
        return _add_group(sim, op, text) if text else None
    after, group = _optional(sim, op.get("after")), _optional(sim, op.get("group"), nodes=False)
    if len(sim.nodes) >= MAX_BLOCKS or _MISSING in (after, group):
        return None
    if not op.get("group") and after and not sim.is_group(after):
        #: A step after another goes in its group.
        group = next((g for g in sim.groups if g["id"] == after.get("group")), None)
    return _placed(sim, {"text": text, "shape": shape}, after, group, _clean(op.get("label"), LABEL_CHARS))


def _placed(sim: _Sim, made: dict, after, group, label: str) -> dict:
    """A new block in `group`, joined from `after` with `label` when there is one."""
    label = label if after else ""
    node = {"id": sim.fresh(), **made, "group": group["id"] if group else None, "new": True}
    sim.nodes.append(node)
    if after:
        sim.edges.append({"from": after["id"], "to": node["id"], "label": label})
    return {"op": "add", **made, "after": sim.name(after) if after else "", "label": label, "group": sim.name(group) if group else ""}


def _rename(sim: _Sim, op: dict) -> dict | None:
    if "from" in op or "to" in op:
        a, b = sim.find(op.get("from")), sim.find(op.get("to"))
        arrow = a and b and sim.edge(a, b)
        if not arrow:
            return None
        arrow["label"] = _clean(op.get("text"), LABEL_CHARS)
        return {"op": "rename", "from": sim.name(a), "to": sim.name(b), "text": arrow["label"]}
    item, text = sim.find(op.get("target")), _clean(op.get("text"), TEXT_CHARS)
    if not item or not text:
        return None
    out = {"op": "rename", "target": sim.name(item), "text": text}
    item["title" if sim.is_group(item) else "text"] = text
    return out


def _join(sim: _Sim, op: dict) -> dict | None:
    a, b = sim.find(op.get("from")), sim.find(op.get("to"))
    label = _clean(op.get("label"), LABEL_CHARS)
    if not a or not b or a is b or any(e.get("from") == a["id"] and e.get("to") == b["id"] and (e.get("label") or "") == label for e in sim.edges):
        return None
    sim.edges.append({"from": a["id"], "to": b["id"], "label": label})
    return {"op": "join", "from": sim.name(a), "to": sim.name(b), "label": label}


def _nest(sim: _Sim, op: dict) -> dict | None:
    item = sim.find(op.get("target"))
    group = sim.find(op.get("group"), nodes=False) if op.get("group") else None
    if not item or (op.get("group") and not group):
        return None
    if group and (item is group or (sim.is_group(item) and sim.inside(group["id"], item))):
        return None
    item["parent" if sim.is_group(item) else "group"] = group["id"] if group else None
    return {"op": "nest", "target": sim.name(item), "group": sim.name(group) if group else ""}


def _delete_arrow(sim: _Sim, op: dict) -> dict | None:
    a, b = sim.find(op.get("from")), sim.find(op.get("to"))
    arrow = a and b and sim.edge(a, b)
    if not arrow:
        return None
    sim.edges.remove(arrow)
    return {"op": "delete", "from": sim.name(a), "to": sim.name(b)}


def _delete(sim: _Sim, op: dict) -> dict | None:
    if "from" in op or "to" in op:
        return _delete_arrow(sim, op)
    item = sim.find(op.get("target"))
    if not item:
        return None
    out = {"op": "delete", "target": sim.name(item)}
    sim.edges = [e for e in sim.edges if item["id"] not in (e.get("from"), e.get("to"))]
    if not sim.is_group(item):
        sim.nodes = [n for n in sim.nodes if n is not item]
        return out
    #: A group lifts what it holds to its own parent.
    for n in sim.nodes:
        n["group"] = item.get("parent") if n.get("group") == item["id"] else n.get("group")
    for g in sim.groups:
        g["parent"] = item.get("parent") if g.get("parent") == item["id"] else g.get("parent")
    sim.groups = [g for g in sim.groups if g is not item]
    return out


_VERBS = {"add": _add, "rename": _rename, "join": _join, "nest": _nest, "delete": _delete}


def checked(ops, model: dict) -> tuple[list[dict], int]:
    """The ops that apply, in order, each played on a copy of `model`, and how many were dropped."""
    ops = ops if isinstance(ops, list) else []
    sim, kept = _Sim(model), []
    for op in ops[:MAX_OPS]:
        verb = _VERBS.get(op.get("op")) if isinstance(op, dict) else None
        done = verb(sim, op) if verb else None
        if done:
            kept.append(done)
    return kept, len(ops) - len(kept)


# --- by rule ---------------------------------------------------------------------------------------

# Matched on text whose whitespace runs are already one space (_one_spaced), so no two
# quantifiers share a run of spaces (CodeQL 2129: a tab run backtracked).
_CLAUSES = re.compile(r" ?(?:;|\. |,? and then |, ?then ) ?", re.I)


def _one_spaced(text: str) -> str:
    return re.sub(r"[^\S\n]+", " ", text).replace("\n", ";")
_LEAD = re.compile(r"^(?:then|and|also|please|can you|could you)\s+", re.I)
_BLOCK_WORD = re.compile(r"\s+(?:step|box|block|node)$", re.I)


def _text_of(words: str) -> tuple[str, str]:
    """A new block's words and shape: "a refund step" is Refund, a box; a question is a decision."""
    words = re.sub(r"^(?:a|an|the|new)\s+", "", words.strip(), flags=re.I)
    shape = "rect"
    hit = re.match(r"^(?:decision|question)\s+(?:called\s+|named\s+)?(.+)$", words, re.I)
    if hit:
        words, shape = hit.group(1), "diamond"
    words = _BLOCK_WORD.sub("", re.sub(r"^(?:called|named)\s+", "", words, flags=re.I)).strip(" .,")
    if words.endswith("?"):
        shape = "diamond"
    elif fold(words) in ("start", "end", "done", "finish", "stop", "begin"):
        shape = "stadium"
    return (words[:1].upper() + words[1:]), shape


def _split_two(text: str, sep: str, sim: _Sim):
    """`Y <sep> Z` where both name a block, trying each place the separator stands."""
    parts = re.split(rf"\s+{sep}\s+", text, flags=re.I)
    for i in range(1, len(parts)):
        left, right = " ".join(parts[:i]), " ".join(parts[i:])
        if sim.find(left) and sim.find(right):
            return left, right
    return None


def _named_then_rest(text: str, sim: _Sim):
    """The longest run of words at the start that names a block, and the words after it."""
    words = text.split()
    for k in range(len(words), 0, -1):
        if sim.find(" ".join(words[:k])):
            return " ".join(words[:k]), " ".join(words[k:]).strip(" :,-")
    return None


def _rule_rename(hit, sim: _Sim):
    parts = re.split(r"\s+(?:to|as)\s+", hit.group(1), flags=re.I)
    if len(parts) < 2:
        return None
    #: The longest run of words before a "to" that names a block ("rename Ready to go to Go" is Ready to go).
    cut = next((i for i in range(len(parts) - 1, 0, -1) if sim.find(" to ".join(parts[:i]))), 1)
    return [{"op": "rename", "target": " to ".join(parts[:cut]), "text": " to ".join(parts[cut:])}]


def _rule_join(hit, sim: _Sim):
    body, label = hit.group(1), ""
    tail = re.search(r"\s+(?:with|labell?ed|saying)\s+(.+)$", body, re.I)
    if tail and _split_two(body[: tail.start()], "to", sim):
        body, label = body[: tail.start()], tail.group(1)
    two = _split_two(body, "to", sim) or _split_two(body, "and", sim)
    return [{"op": "join", "from": two[0], "to": two[1], "label": label}] if two else None


def _rule_unjoin(hit, sim: _Sim):
    two = _split_two(hit.group(1), "to", sim)
    return [{"op": "delete", "from": two[0], "to": two[1]}] if two else None


def _rule_between(hit, sim: _Sim):
    two = _split_two(hit.group(2), "and", sim)
    if not two:
        return None
    text, shape = _text_of(hit.group(1))
    arrow = sim.edge(sim.find(two[0]), sim.find(two[1]))
    ops = [{"op": "add", "text": text, "shape": shape, "after": two[0], "label": arrow.get("label", "") if arrow else ""}, {"op": "join", "from": text, "to": two[1], "label": ""}]
    return ops + ([{"op": "delete", "from": two[0], "to": two[1]}] if arrow else [])


def _rule_add(hit, sim: _Sim):
    rest = hit.group(1)
    parts = re.split(r"\s+after\s+", rest, flags=re.I)
    for i in range(len(parts) - 1, 0, -1):
        found = _named_then_rest(" ".join(parts[i:]), sim)
        if found:
            text, shape = _text_of(" after ".join(parts[:i]))
            return [{"op": "add", "text": text, "shape": shape, "after": found[0], "label": found[1]}]
    text, shape = _text_of(rest)
    return [{"op": "add", "text": text, "shape": shape}]


_ADD = r"^(?:add|insert|create|put in)\s+"
#: The rule's grammar, tried in order: a pattern, and what it makes of the words it caught.
_RULES = (
    (r"^(?:rename|call|change)\s+(?:the\s+)?(.+)$", _rule_rename),
    (r"^(?:join|connect|link)\s+(.+)$", _rule_join),
    (r"^(?:take|move|lift)\s+(.+?)\s+out of\s+(?:its|the)\s+group$", lambda hit, sim: [{"op": "nest", "target": hit.group(1), "group": ""}]),
    (r"^(?:put|move|nest)\s+(.+?)\s+(?:into|inside|in|under)\s+(?:the\s+)?(?:group\s+)?(.+?)(?:\s+group)?$", lambda hit, sim: [{"op": "nest", "target": hit.group(1), "group": hit.group(2)}]),
    (r"^(?:delete|remove)\s+the\s+(?:arrow|join|link|connection|line)\s+from\s+(.+)$", _rule_unjoin),
    (r"^(?:delete|remove)\s+(?:the\s+)?(?:block\s+|step\s+|group\s+)?(.+)$", lambda hit, sim: [{"op": "delete", "target": hit.group(1)}]),
    (_ADD + r"(?:a\s+|an\s+|the\s+)?group\s+(?:called\s+|named\s+)?(.+)$", lambda hit, sim: [{"op": "add", "text": hit.group(1), "shape": "group"}]),
    (_ADD + r"(.+?)\s+between\s+(.+)$", _rule_between),
    (_ADD + r"(.+)$", _rule_add),
)


def _clause_ops(clause: str, sim: _Sim) -> list[dict] | None:
    c = _LEAD.sub("", clause.strip().rstrip("."))
    for pattern, make in _RULES:
        if hit := re.match(pattern, c, re.I):
            return make(hit, sim)
    return None


NOT_READ = "That did not read as a change. Try “add Refund after In stock? No” or “rename Warehouse to Fulfilment”."


def by_rule(ask: str, model: dict) -> dict:
    """The ask read by rule, clause by clause, each checked against the model as the earlier ones left it."""
    sim, kept, dropped, unread = _Sim(model), [], 0, 0
    for clause in [c for c in _CLAUSES.split(_one_spaced(str(ask or "")[:ASK_CHARS])) if c.strip()]:
        ops = _clause_ops(clause, sim)
        if not ops:
            unread += 1
            continue
        for op in ops:
            done = _VERBS[op["op"]](sim, op) if len(kept) < MAX_OPS else None
            if done:
                kept.append(done)
            else:
                dropped += 1
    said = "" if kept else (NOT_READ if unread and not dropped else "No block in the diagram has those words." if dropped else NOT_READ)
    return {"ops": kept, "said": said, "by": "rule", "dropped": dropped}


# --- with the model --------------------------------------------------------------------------------


def described(model: dict) -> str:
    """The diagram as the model reads it: `B: In stock? [diamond] in Warehouse`, then `B -> C: Yes`."""
    sim = _Sim(model)
    titles = {g["id"]: _clean(g.get("title"), 60) for g in sim.groups}
    lines = [f"{n['id']}: {_clean(n.get('text'), 60)} [{n.get('shape') or 'rect'}]" + (f" in {titles[n['group']]}" if n.get("group") in titles else "") for n in sim.nodes[:DESCRIBED_BLOCKS]]
    lines += [f"group {g['id']}: {titles[g['id']]}" for g in sim.groups[:20]]
    lines += [f"{e.get('from')} -> {e.get('to')}" + (f": {_clean(e.get('label'), LABEL_CHARS)}" if e.get("label") else "") for e in sim.edges[:2 * DESCRIBED_BLOCKS]]
    out, size = [], 0
    for line in lines:
        if size + len(line) + 1 > DESCRIBED_CHARS:
            break
        out.append(line)
        size += len(line) + 1
    return "\n".join(out)


def read_reply(reply: str) -> list:
    """The ops in a model's reply: the first JSON object or list in it, read and never run; [] for none."""
    text = str(reply or "")
    for at, ch in enumerate(text):
        if ch not in "{[":
            continue
        try:
            value, _ = json.JSONDecoder().raw_decode(text, at)
        except ValueError:
            continue
        #: A small model sometimes answers with the one op itself, not wrapped in a list (L-documents-100, ER).
        ops = [value] if isinstance(value, dict) and "op" in value and "ops" not in value else value.get("ops") if isinstance(value, dict) else value
        return ops if isinstance(ops, list) else []
    return []


def with_model(ask: str, model: dict, model_name: str, provider) -> dict:  # noqa: ANN001
    """The ask written as ops by the model, checked; the rule's answer when nothing it wrote applies."""
    from tessellate.ai.ollama_client import OllamaError

    try:
        reply = provider.chat(model_name, [
            {"role": "system", "content": ASK_PROMPT},
            {"role": "user", "content": f"Diagram:\n{described(model)}\n\nAsk: {str(ask)[:ASK_CHARS]}"},
        ])
    except OllamaError:
        reply = {}
    kept, dropped = checked(read_reply((reply or {}).get("content") or ""), model)
    if kept:
        return {"ops": kept, "said": "", "by": "model", "dropped": dropped}
    ruled = by_rule(ask, model)
    return {**ruled, "said": ("The model's answer could not be used, so this is by rule. " + ruled["said"]).strip()}
