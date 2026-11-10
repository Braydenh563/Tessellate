"""Reads the agent has a tool for, said with no model (CHAT_PLAN decision 75,
"everything the composer can do, the ai should be able to do, and vice versa";
composer audit 2, "What the model-on path can do that the composer cannot").

Each reader takes a sentence and the session and returns the answer's text, or
None. They only read: a change is an act with its card (`ai/commands.py`). With
a model up the same text is handed over as facts (`api/chat_extra.facts_events`),
so both paths say the same thing.

- the bin ("what's in my bin", `manager.list_deleted_entries`);
- earlier chats ("what did we talk about last time", the `search_chat_history` tool);
- how two notes are related ("how are japan trip and kyoto ideas related", `path_between`);
- where the notebook is exported (no tool: a hand-off to Settings).

Two more are said only when no model runs (`answer(..., model=False)`), because
a model has the tool and the composer cannot do what it does: finding notes
that disagree (`find_contradictions`) and writing a document (`create_document`).
Each says so and where to turn a model on, in the tool's own words.
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from tessellate.repo import relations as relations_repo

_LEAD = r"^(?:(?:please|pls|hey|ok|okay|so|and|then|can you|could you)\s+)*"
_BIN = re.compile(
    _LEAD + r"(?:(?:what(?:'s|’s| is)|what do i have)(?: in)?|show(?: me)?(?: what(?:'s|’s| is) in)?|list|open|see|check)\s+"
    r"(?:(?:in )?(?:my|the) )?(?:bin|trash|recycle bin|rubbish bin|deleted notes)\W*$"
    r"|" + _LEAD + r"what (?:have i|did i) (?:deleted?|binned|thrown away)(?: recently| lately)?\W*$",
    re.I,
)
_HISTORY = re.compile(
    _LEAD + r"(?:what|where) (?:did|were|have) (?:we|you and i)\s+(?:talk(?:ed)?|chat(?:ted)?|discuss(?:ed)?|decide|decided|speak|spoke|say|said"
    #: "what did we cover in lecture 5" is the study summary's; only "...cover last time" is a past chat.
    r"|cover(?:ed)?(?=.*\b(?:last time|earlier|before|previously|the other day|recently|lately|this morning|last night)\b))\b(?P<rest>.*)$"
    r"|" + _LEAD + r"(?:search|find|look)(?: through| in| at)? (?:my |our |the )?(?:old |past |earlier |previous )?(?:chats?|conversations?)(?: history)?(?: for| about| on)?(?P<rest2>.*)$",
    re.I,
)
#: When, not what ("last time"): left out of the topic. A day or a span is `recognise.without_windows`'s.
_WHEN = re.compile(r"\b(?:last time|the last time|earlier|before|previously|the other day|recently|lately|this morning|last night)\b", re.I)
_RELATED = re.compile(
    _LEAD + r"how (?:are|is|do|does) (?:the |my )?(?P<a>.+?) (?:and|with|to) (?:the |my )?(?P<b>.+?) (?:related|connected|linked|relate|connect|link)\W*$"
    r"|" + _LEAD + r"(?:what|how) (?:links|connects|joins|relates) (?:the |my )?(?P<a2>.+?) (?:and|to|with) (?:the |my )?(?P<b2>.+?)\W*$",
    re.I,
)
_CONTRADICTION = re.compile(
    _LEAD + r"(?:(?:are there|is there|do i have|have i got|find|show|check|look for|any)\s+)*(?:any\s+)?(?:contradictions?|conflicts?|inconsistenc(?:y|ies))(?: in my notes)?\W*$"
    r"|" + _LEAD + r"(?:do|does|are|is) (?:any of )?(?:my|the) notes (?:contradict|disagree|conflict)(?: with each other| with one another)?\W*$",
    re.I,
)
_DOCUMENT = re.compile(
    _LEAD + r"(?:make|create|write|draft|start|put together)(?: me)? (?:a |an )(?:new )?(?:long )?(?:document|doc|report|essay|write-up|writeup)\b.*$",
    re.I,
)
_EXPORT = re.compile(
    _LEAD + r"(?:export|back ?up|download|save)\s+(?:all |everything in )?(?:of )?(?:my |the )?(?:whole )?(?:notes|notebook|everything|data|library)(?: as (?:json|csv|markdown|a (?:file|folder|zip)))?\W*$"
    r"|" + _LEAD + r"how (?:do|can) i (?:export|back ?up|download) (?:my |the )?(?:notes|notebook|data|everything)\W*$",
    re.I,
)


def _bin(session: Session) -> str:
    from tessellate.ai.composer_frame import note_title
    from tessellate.entry import manager

    total = manager.count_deleted_entries(session)
    if not total:
        return "The bin is empty."
    names = [f"- {note_title(row.content, size=48)}" for row in manager.list_deleted_entries(session, limit=6) if not row.is_private]
    head = "One note is in the bin." if total == 1 else f"{total} notes are in the bin."
    tail = "\n\nSay “restore the last deleted note” to bring the newest back, or “restore the” and a name for another." if names else ""
    return head + ("\n\n" + "\n".join(names) if names else "") + tail


def _topic(rest: str) -> str:
    """The words a past chat is searched for: what is left of the sentence once the time words are taken off."""
    from tessellate.ai import recognise

    query = _WHEN.sub(" ", recognise.without_windows(rest or ""))
    query = re.sub(r"^\W*(?:about|on|regarding|for)\b", " ", query.strip(), flags=re.I)
    return " ".join(re.sub(r"[?!.,]+", " ", query).split())


def _chat_row(chat: dict) -> str:
    asked = next((e["text"] for e in chat.get("excerpts") or [] if e.get("role") == "user"), "").strip()
    head = f"- **{chat.get('title') or 'Untitled chat'}** ({str(chat.get('updated_at') or '')[:10]})"
    return f"{head}: you asked “{asked[:90]}”" if asked else head


def _history(session: Session, rest: str) -> str:
    from tessellate.ai import tools as agent_tools

    query = _topic(rest)
    result = agent_tools.execute_tool(session, "search_chat_history", {"query": query, "limit": 3})
    found = [c for c in result.get("conversations") or [] if isinstance(c, dict)]
    if not found:
        return f"I found no earlier chat about “{query}”." if query else "You have no earlier chats yet."
    if not query:
        lead = "Your latest chats:"
    else:
        lead = f"One earlier chat mentions “{query}”." if len(found) == 1 else f"{len(found)} earlier chats mention “{query}”."
    return lead + "\n\n" + "\n".join(_chat_row(chat) for chat in found)


def _first_note(session: Session, words: str) -> int | None:
    """The id of the note a few words name, the way a model finds one: the search tool's first hit."""
    from tessellate.ai import tools as agent_tools

    hits = agent_tools.execute_tool(session, "search_notes", {"query": words, "limit": 1}).get("notes") or []
    return hits[0].get("id") if hits and isinstance(hits[0], dict) else None


def _related(session: Session, first: str, second: str) -> str | None:
    """The chain between two notes, said as the tool's answer is (`tool_say`); None when a name finds no note."""
    from tessellate.ai import tool_say
    from tessellate.ai import tools as agent_tools

    a, b = _first_note(session, first), _first_note(session, second)
    if a is None or b is None or a == b:
        return None
    #: A link the person gave a reason is said with it by the composer (audit 1031 C49), not as a bare chain.
    if any(reason for _, _, reason in relations_repo.among(session, [a, b])):
        return None
    args = {"note_id": a, "other_note_id": b}
    return tool_say.say("path_between", agent_tools.execute_tool(session, "path_between", args), args)["text"]


def _contradictions(session: Session) -> str:
    from tessellate.ai import tool_say
    from tessellate.ai import tools as agent_tools

    return tool_say.say("find_contradictions", agent_tools.execute_tool(session, "find_contradictions", {}))["text"]


_DOCUMENT_LINE = (
    "Writing a document needs a model, and none is running. Turn one on in Settings, [Models](#/settings/models), "
    "or start a blank one yourself in [Documents](#/docs)."
)
_EXPORT_LINE = (
    "Exporting is done in Settings, Import & export: JSON, CSV, Markdown, or the whole notebook as a folder, "
    "and a full backup you can seal with a password. [Open Import & export](#/settings/data)"
)


def _history_of(session: Session, found: re.Match) -> str:
    return _history(session, found.group("rest") or found.group("rest2") or "")


def _related_of(session: Session, found: re.Match) -> str | None:
    return _related(session, found.group("a") or found.group("a2"), found.group("b") or found.group("b2"))


#: (pattern, reader, only when no model runs), in the order they are tried.
_READERS = (
    (_CONTRADICTION, lambda session, _found: _contradictions(session), True),
    (_DOCUMENT, lambda _session, _found: _DOCUMENT_LINE, True),
    (_BIN, lambda session, _found: _bin(session), False),
    (_HISTORY, _history_of, False),
    (_RELATED, _related_of, False),
    (_EXPORT, lambda _session, _found: _EXPORT_LINE, False),
)


def answer(session: Session, question: str, *, model: bool = False) -> str | None:
    """The text for a sentence one of these readers owns, else None. `model`: a
    model is up, which has the tools the readers marked so stand in for."""
    text = " ".join((question or "").split())
    if not text or len(text) > 160:
        return None
    for pattern, reader, bare in _READERS:
        if (found := pattern.match(text)) and not (bare and model):
            return reader(session, found)
    return None
