"""Summarise a meeting note into decisions and action items, every line cited
(INBOX 644, decision 3).

The recorder's old pass (§25, a block of bullets) returned bullets nobody can check: a small model that invents "Sam will send the deck"
writes it in the same voice as one that read it. This pass asks for each line
together with the exact words of the note it came from, and **keeps a line
only when those words are really in the note** (the Ask citation rule: a
claim with no source in the notebook is not shown as if it had one). What was
dropped is counted, so the sheet can say "2 lines had no source and were left
out" rather than pretending the model found less.

The reply format is one line per item, pipe separated, because it is the
shape a 3B model keeps most reliably and a malformed line degrades into one
dropped item rather than a parse error for the whole reply.
"""

from __future__ import annotations

import re

#: The longest stretch of the note sent: a meeting of an hour transcribed is
#: about 9,000 words, and a small model's context has to hold the
#: instructions beside it.
MAX_SOURCE_CHARS = 24_000
#: A quote shorter than this proves nothing: "the" is in every note.
MIN_QUOTE_CHARS = 8
MAX_LINES = 30

SYSTEM = (
    "You read meeting notes and list only the decisions made and the action "
    "items agreed. Reply with one item per line and nothing else, in exactly "
    "one of these two shapes:\n"
    "DECISION | <the decision, one short sentence> | <exact words copied from the notes>\n"
    "ACTION | <the task, one short sentence> | <owner's first name, or blank> | <exact words copied from the notes>\n"
    "The last field must be copied word for word from the notes, so it can be "
    "found in them. If there are no decisions and no action items, reply with "
    "exactly: NONE"
)

_SPACE = re.compile(r"\s+")
_EDGE = re.compile(r"^[\s\"'“”‘’.,;:]+|[\s\"'“”‘’.,;:]+$")


def _norm(text: str) -> str:
    return _SPACE.sub(" ", _EDGE.sub("", str(text or ""))).strip().lower()


def _found(quote: str, source_norm: str) -> bool:
    q = _norm(quote)
    return len(q) >= MIN_QUOTE_CHARS and q in source_norm


def _one_line(text: str, limit: int = 240) -> str:
    return " ".join(str(text or "").replace("“", '"').replace("”", '"').split())[:limit]


def parse_reply(reply: str, source: str) -> dict:
    """`{"decisions": [...], "actions": [...], "dropped": n}` from the model's
    lines, each kept item carrying the `quote` it was found by. Pure, so the
    rule that matters (no source, no line) is tested without a model."""
    source_norm = _norm(source)
    decisions: list[dict] = []
    actions: list[dict] = []
    dropped = 0
    seen: set[str] = set()
    for raw in str(reply or "").splitlines()[: MAX_LINES * 2]:
        line = raw.strip().lstrip("-*• ").strip()
        if not line or line.upper() == "NONE":
            continue
        parts = [part.strip() for part in line.split("|")]
        kind = parts[0].upper().rstrip(":") if parts else ""
        if kind == "DECISION" and len(parts) >= 3:
            text, quote, owner = parts[1], "|".join(parts[2:]), ""
        elif kind == "ACTION" and len(parts) >= 4:
            text, owner, quote = parts[1], parts[2], "|".join(parts[3:])
        else:
            dropped += 1
            continue
        text = _one_line(text)
        quote = _one_line(_EDGE.sub("", quote), 300)
        if not text or not _found(quote, source_norm):
            dropped += 1
            continue
        key = f"{kind}:{_norm(text)}"
        if key in seen:
            continue
        seen.add(key)
        owner_word = re.sub(r"[^\w.'-]", "", (owner or "").split(" ")[0]) if owner and owner.lower() not in {"blank", "none", "-", "n/a"} else ""
        item = {"text": text, "quote": quote}
        if kind == "DECISION":
            decisions.append(item)
        else:
            item["owner"] = owner_word or None
            actions.append(item)
    return {"decisions": decisions[:MAX_LINES], "actions": actions[:MAX_LINES], "dropped": dropped}


def _cite(item: dict) -> str:
    """`, from “...”`, or nothing when the line is the quote itself: a
    sentence copied from the notes (the rules pass, `entry/meetings.find_items`)
    is its own source, and its "by Friday" is then the reminder's day."""
    if item.get("verbatim"):
        return ""
    return f", from “{item['quote']}”"


def as_lines(result: dict) -> dict[str, list[str]]:
    """The markdown each kept item becomes in the note, its source after it:
    `- Launch in November, from “launch moves to November”`. The quote is the
    citation a reader checks against the Notes section above it."""
    decisions = [f"- {d['text']}{_cite(d)}" for d in result.get("decisions", [])]
    actions = []
    for a in result.get("actions", []):
        owner = f" @{a['owner']}" if a.get("owner") and f"@{a['owner']}".lower() not in a["text"].lower() else ""
        actions.append(f"- [ ] {a['text']}{owner}{_cite(a)}")
    return {"decisions": decisions, "actions": actions}


def _same_source(a: dict, b: dict) -> bool:
    qa, qb = _norm(a["quote"]), _norm(b["quote"])
    return bool(qa and qb) and (qa in qb or qb in qa)


def merge(rules: dict, model: dict) -> dict:
    """The rules' list with the model's words on top (28.5 row 2): an item
    both found from the same sentence keeps the model's sentence and the
    rules' owner and day; what only one found is kept as it is. The model
    rewrites the list; it never shortens it."""
    out: dict = {"dropped": model.get("dropped", 0)}
    for kind in ("decisions", "actions"):
        written = list(model.get(kind, []))
        kept = []
        for item in rules.get(kind, []):
            twin = next((m for m in written if _same_source(item, m)), None)
            if twin is None:
                kept.append(item)
                continue
            written.remove(twin)
            kept.append({**item, **{k: v for k, v in twin.items() if v}, "verbatim": False})
        out[kind] = (kept + written)[:MAX_LINES]
    return out


def summarise(source: str, model_manager, ollama) -> dict:  # noqa: ANN001
    """One utility-model call; raises whatever the client raises when the
    model is unavailable, and the route says so."""
    text = str(source or "")[:MAX_SOURCE_CHARS]
    reply = ollama.chat(
        model_manager.utility_model(),
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}],
    )
    return parse_reply(reply.get("content", ""), text)
