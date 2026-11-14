"""What changed between two versions of a board, in words (L-whiteboard-11).

`diff` compares two replayed states (`routes_board_history._states_at`) and
`summary` writes the composer's own sentences from it, so a board with no
local model still gets an answer. `rewrite` is the model's pass over that
text only: it sees the sentences, never the board, and a private note's title
is never in them (`_labels` leaves a private card unnamed).
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from tessellate.entry.manager_text import extract_title
from tessellate.repo import whiteboard as whiteboard_repo

#: noun, plural, by the kind of item; an object kind not listed is a shape.
_NOUNS = {
    "node": ("card", "cards"),
    "sketch": ("drawing", "drawings"),
    "frame": ("frame", "frames"),
    "text": ("text box", "text boxes"),
    "sticky": ("sticky", "stickies"),
    "topic": ("topic", "topics"),
}
_SHAPE = ("shape", "shapes")
_NAMES_SHOWN = 3
#: How long the model has to word the summary before the composer's text is sent.
NARRATE_SECONDS = 20.0


def _object(state: dict) -> tuple[str, dict]:
    try:
        data = json.loads(state.get("data") or "{}")
    except (TypeError, ValueError):
        data = {}
    return str(state.get("kind") or ""), data if isinstance(data, dict) else {}


def _words(data: dict) -> str:
    for field in ("content", "text"):
        value = data.get(field)
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())[:60]
    return ""


def _labels(db: Session, states: dict[str, dict]) -> dict[str, tuple[str, str]]:
    """Each item's (kind key, name or ''). A private card has no name."""
    wanted = [s.get("entry_id") for k, s in states.items() if k.startswith("node:") and s.get("entry_id")]
    entries = {e.id: e for e in whiteboard_repo.entries(db, wanted)}
    out: dict[str, tuple[str, str]] = {}
    for key, state in states.items():
        kind = key.split(":")[0]
        if kind == "node":
            entry = entries.get(state.get("entry_id"))
            name = "" if entry is None or entry.is_private else extract_title(entry.content or "")
            out[key] = ("node", name or "")
        elif kind == "sketch":
            out[key] = ("sketch", "")
        else:
            okind, data = _object(state)
            out[key] = (okind if okind in _NOUNS else "shape", _words(data))
    return out


def diff(db: Session, older: dict[str, dict], newer: dict[str, dict]) -> dict:
    """Added, removed, moved and retitled items, each as (kind key, name)."""
    labels = _labels(db, {**older, **newer})
    out: dict[str, list] = {"added": [], "removed": [], "moved": [], "retitled": []}
    for key in sorted(newer.keys() - older.keys()):
        out["added"].append(labels[key])
    for key in sorted(older.keys() - newer.keys()):
        out["removed"].append(labels[key])
    for key in sorted(older.keys() & newer.keys()):
        before, after = older[key], newer[key]
        if (before.get("x"), before.get("y")) != (after.get("x"), after.get("y")):
            out["moved"].append(labels[key])
        if key.startswith("object:"):
            was, now = _words(_object(before)[1]), _words(_object(after)[1])
            if was != now and now:
                out["retitled"].append((labels[key][0], was, now))
    return out


def _list(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def _phrase(verb: str, items: list[tuple[str, str]]) -> list[str]:
    """One sentence per kind of item: 'Added 3 cards: A, B and C.'"""
    by_kind: dict[str, list[str]] = {}
    for kind, name in items:
        by_kind.setdefault(kind, []).append(name)
    sentences = []
    for kind, names in by_kind.items():
        one, many = _NOUNS.get(kind, _SHAPE)
        named = [n for n in names if n]
        if len(names) == 1:
            sentences.append(f"{verb} the {one} {named[0]}." if named else f"{verb} a {one}.")
            continue
        text = f"{verb} {len(names)} {many}"
        if named:
            shown = named[:_NAMES_SHOWN]
            rest = len(names) - len(shown)
            text += ": " + _list(shown + ([f"{rest} more"] if rest else []))
        sentences.append(text + ".")
    return sentences


NOTHING = "Nothing changed between these two versions."


def summary(changes: dict) -> str:
    """The composer's account of a diff, in plain sentences."""
    parts = _phrase("Added", changes["added"]) + _phrase("Moved", changes["moved"])
    for kind, was, now in changes["retitled"][:_NAMES_SHOWN]:
        one = _NOUNS.get(kind, _SHAPE)[0]
        parts.append(f"Changed the {one} {was} to {now}." if was else f"Wrote {now} on a {one}.")
    parts += _phrase("Removed", changes["removed"])
    return " ".join(parts) or NOTHING


def rewrite(text: str, model_manager, ollama) -> str:  # noqa: ANN001
    """The local model's wording of `summary`'s sentences; raises OllamaError."""
    system = (
        "You tell someone what changed on their whiteboard between two versions. "
        "Rewrite the facts you are given as one or two short, plain sentences. "
        "Add nothing that is not in them, change no name or number, no exclamation marks."
    )
    reply = ollama.chat(model_manager.utility_model(), [{"role": "system", "content": system}, {"role": "user", "content": text}])
    return reply["content"].strip()[:600]
