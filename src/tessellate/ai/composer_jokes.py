"""Jokes, quotes and poems asked for (L-chat-19; the owner, 2026-10-10: "it got
jokes from another note but not the separate one from the top of the matching
records"). "One of my jokes" is the top matching record's; "the chicken joke"
is the one that says chicken; "what are my jokes" is all of them, each quoted
as written, never run into the next.
"""

from __future__ import annotations

import re

from tessellate.ai import composer, realise
from tessellate.ai.composer_digest_sentences import _PREFIX, CONTEXT_TAGS, Fact

CONTEXT_STEMS = frozenset(composer._stem(t) for t in CONTEXT_TAGS)  # noqa: SLF001
_ALL = re.compile(r"^\W*(?:what|which)\s+(?:are|were)\s+(?:all\s+)?(?:my|the)\s+(?:\w+\s+)?(?:jokes|quotes|poems)\b|\b(?:list|show me)\s+(?:all\s+)?(?:of\s+)?my\s+(?:jokes|quotes|poems)\b", re.I)
_ONE_OF = re.compile(r"\b(?:one|a|an|any|some)\s+(?:of\s+)?(?:my\s+)?(?:\w+\s+)?(?:jokes?|quotes?|poems?)\b", re.I)
#: "Why don't skeletons fight? They don't have the guts": a sentence ends inside the item.
_SENTENCES_INSIDE = re.compile(r"[?.!] +[A-Z]")


def wants_all(question: str) -> bool:
    """"What are my jokes" asks for all of them; "one of my jokes" is one."""
    return bool(_ALL.search(question)) and not _ONE_OF.search(question)


def only_context(words: list[str]) -> bool:
    """Every word is a kind of piece ("jokes"): every joke note is as much about
    jokes as any other, so the search's order stands."""
    return not words or {composer._stem(t) for t in words} <= CONTEXT_STEMS  # noqa: SLF001


def pick(facts: list, stems: set[str]):  # noqa: ANN201
    """The piece asked for, or None when the question names no kind of piece."""
    named = stems - CONTEXT_STEMS
    if not facts or not stems or named == stems:
        return None
    if not named:
        return facts[0]
    held = [f for f in facts if all(composer._holds(st, set(f.sentence.words) | f.view.title_words) for st in named)]  # noqa: SLF001
    return held[0] if held else None


def whole_sentences(bodies: list[str]) -> bool:
    """Each item is whole sentences, a joke's question and its answer."""
    return all(_SENTENCES_INSIDE.search(b) for b in bodies)


def quoted_listed(bodies: list[str], limit: int) -> str:
    """The items quoted as written, the first `limit` (all of them when one more), then "two more"."""
    shown = bodies[:limit + 1] if len(bodies) == limit + 1 else bodies[:limit]
    items = [f"“{b.rstrip().rstrip('.')}”" for b in shown]
    if len(bodies) > len(shown):
        items.append(f"{realise.count_word(len(bodies) - len(shown))} more")
    return realise.join_items(items)


def context_note(view: composer.NoteView) -> bool:
    tags = {str(t).lower().strip("#") for t in (view.note.get("tags") or [])}
    return bool(tags & CONTEXT_TAGS)


def context_facts(view: composer.NoteView) -> list[Fact]:
    """A joke or a quote is one piece (decision 67): its question and its
    punchline are never two facts. A list of them ("Jokes I like" with a joke a bullet) is one piece a
    bullet: run together, one joke's punchline ran into the next one's question."""
    if len(view.sentences) > 1 and all(s.kind == "item" for s in view.sentences):
        return [Fact(view, s, "Joke", s.text.strip().rstrip("."), "") for s in view.sentences]
    whole = " ".join(s.text.strip() for s in view.sentences)
    head = _PREFIX.match(whole)
    label = head.group(1).strip() if head else "Joke"
    body = head.group(2) if head else whole
    return [Fact(view, view.sentences[0], label, body.strip().rstrip("."), "")] if view.sentences else []


def kept(views) -> list[str]:  # noqa: ANN001
    """A joke's own words, kept as written by the grammar pass; said without its "Joke:" label, so the words alone too."""
    out = []
    for v in views:
        for s in v.sentences if context_note(v) else ():
            text = s.text.strip().rstrip(".!")
            head = _PREFIX.match(text)
            out += [text, head.group(2)] if head else [text]
    return out
