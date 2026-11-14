"""The nth item of a list note, and how many items it holds (round 2 E8).

"What is the third item in the Tokyo packing list" and "how many items are in
Packing for Tokyo" used to read as a search for the words "third" and "items",
and answered with the whole list, or with one unrelated sentence. A numbered,
bulleted or ticked list is a sequence, so its position and its length are a
fact the notes hold, said exactly.
"""

from __future__ import annotations

import re

from tessellate.ai import realise
from tessellate.ai.composer_ask import _stem

_ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "last": -1,
}
_THING = r"(?:item|thing|entry|line|task|bullet|step|row)"
_PLACE = r"\s+(?:in|on|of|from)\s+(?:my\s+|the\s+|our\s+)?(?P<note>.+?)"
_ORD = rf"(?P<nth>{'|'.join(_ORDINALS)}|\d{{1,2}}(?:st|nd|rd|th))\s+{_THING}"
#: "What is the third item in X", or the short forms people type ("third item in
#: the Tokyo packing list", "show me the last item in my to-do"). A short form
#: must name the list: "first thing in the morning" is not an ask for one.
_NTH = re.compile(rf"^(?:what|which)(?:'s|\s+is|\s+was)?\s+(?:the\s+)?{_ORD}(?:{_PLACE})?$", re.I)
_NTH_SHORT = re.compile(rf"^(?:(?:show|tell|give|read)\s+me\s+)?(?:the\s+)?{_ORD}{_PLACE}$", re.I)
_COUNT = re.compile(rf"^how\s+many\s+(?P<thing>{_THING}s?)\s+(?:are\s+|do\s+i\s+have\s+)?(?:there\s+)?(?:in|on|of)\s+(?:my\s+|the\s+|our\s+)?(?P<note>.+?)$", re.I)
_NOT_NAMING = frozenset({"list", "note", "checklist", "lists", "notes", "for", "the", "of", "my", "and", "to", "a", "an", "in", "on"})


def _nth_of(word: str) -> int:
    word = word.lower()
    return _ORDINALS.get(word) or int(re.sub(r"\D", "", word))


def _view_for(note: str, views: list):  # noqa: ANN001, ANN202
    """The list note the words name (every word in its title), else the only
    note that has list items at all."""
    withs = [v for v in views if any(s.kind in ("item", "task") for s in v.sentences)]
    stems = {_stem(w) for w in re.findall(r"[a-z0-9]+", note.lower()) if w not in _NOT_NAMING}
    if stems:
        named = [v for v in withs if stems <= v.title_words]
        return min(named, key=lambda v: (len(v.title_words), v.rank)) if named else None
    return withs[0] if len(withs) == 1 else None


def _items(view) -> list:  # noqa: ANN001
    return [s for s in view.sentences if s.kind in ("item", "task")]


def _label(sentence) -> str:  # noqa: ANN001
    if sentence.kind == "task":
        return f"{sentence.text.strip()} ({'done' if sentence.done else 'not done'})"
    return sentence.text.strip()


def _asked(asked: str):  # noqa: ANN202
    """`(position, note words, ordinal word)` for an nth ask, position 0 for a
    count, or None."""
    q = " ".join(str(asked or "").split()).rstrip("?.! ")
    if m := _NTH.match(q) or _NTH_SHORT.match(q):
        return _nth_of(m.group("nth")), m.group("note") or "", m.group("nth").lower()
    if m := _COUNT.match(q):
        return 0, m.group("note"), ""
    return None


def answer(out, asked: str, views: list) -> bool:  # noqa: ANN001
    """Say the position or the count, or False when `asked` is neither."""
    from tessellate.ai import composer_lists

    got = _asked(asked)
    view = _view_for(got[1], views) if got else None
    items = _items(view) if view is not None else []
    if not items:
        return False
    which, _note, ordinal = got
    title = composer_lists._title(view)  # noqa: SLF001
    plural = "s" if len(items) != 1 else ""
    if which == 0:
        done = sum(1 for s in items if s.kind == "task" and s.done)
        tail = f", {realise.count_word(done)} of them done" if done and items[0].kind == "task" else ""
        line, cited = f"{title} has {realise.count_word(len(items))} item{plural}{tail}.", items[0]
    elif (at := len(items) if which < 0 else which) > len(items):
        line, cited = f"{title} has only {realise.count_word(len(items))} item{plural}.", items[-1]
    else:
        cited = items[at - 1]
        line = f"The {'last' if which < 0 else ordinal} item is {_label(cited)}."
    out.lines.append(line)
    composer_lists._cite(out, view, cited, line)  # noqa: SLF001
    return True
