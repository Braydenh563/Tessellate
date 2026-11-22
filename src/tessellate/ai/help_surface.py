"""A what-question that names a part of the app (L-chat-182), kept out of `help_chat` (line cap)."""
import re

#: "what is the graph tab", "what does the whiteboard do", "what's the bin for": a question about a part of the app, not
#: a how-to, so it is not the "how do I" frame (L-chat-182: it was answered "that's general knowledge").
_FILLER = {"the", "for", "and", "you", "can", "how", "what", "does", "this", "that", "with", "tell", "about", "work", "tabs", "page"}
_WHAT_FRAME = re.compile(r"^\s*(?:what(?:'s| is| are| does| do| can| could)|tell me about|explain)\s+(?:the\s+|a\s+|an\s+|my\s+)?", re.I)


def surface_word(question: str) -> str:
    """The word of a what-question that names the app's own part ("the graph tab" is Graph;
    "a sourdough starter" shares a keyword with Templates but not its name), or ""."""
    framed = _WHAT_FRAME.match(question)
    #: Lazy: help_chat builds its keyword tables on import (46 ms of the composer's cold import, tests/test_engine_budgets.py).
    from tessellate.ai import help_chat

    topics = help_chat._matching_topics(question) if framed else []
    if not topics:
        return ""
    named = {w[:5] for w in re.findall(r"[a-z]{3,}", f"{topics[0].get('id', '')} {help_chat.topic_title(topics[0])}".lower())}
    #: Only the first word after the frame names the part: "the zorblax code" is a thing in the notes, not Code files.
    words = re.findall(r"[a-z]{3,}", question[framed.end():].lower())
    first = next((w for w in words if w not in _FILLER), "")
    #: "the table number" asks a note for its number (composer_property), not the Table feature of the whiteboard.
    if first and words[words.index(first) + 1 : words.index(first) + 2] == ["number"]:
        return ""
    return first if first[:5] in named else ""


def asks_about_a_part(question: str, notes: list[dict]) -> bool:
    """The question names an app part and no note mentions it: it asks about the app, not the notes."""
    word = surface_word(question)
    return bool(word) and not any(word in f"{n.get('title') or ''} {n.get('content') or ''}".lower() for n in notes)
