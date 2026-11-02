"""The two suggestion rows: the questions asked before ("Ask again") and the
starter suggestions, kept from repeating each other.

Moved whole from `routes_chat.py` (audit AR3, gods-1101): the code is
unchanged, and `routes_chat` re-exports every name here that anything
reads, so `routes_chat.STARTER_SUGGESTIONS` still works. Imports run one way, down the
layer list in `routes_chat.py`'s docstring, never back to `routes_chat`.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.api.chat_request import ChatRequest
from tessellate.core.database import AuditLog


#: **Asking and requesting are logged apart, and this is why.** Reported
#: directly: "tasks that I have put in the agent show in the 'ask' again
#: section, the things that I will ask the agent are different to what I would
#: ask if searching in my notebook."
#:
#: Every turn through this module used to write one `queried`/`chat` audit row,
#: so "Ask again", which reads that log, offered back "tag everything about
#: the trip" and "delete the draft" as though they were questions about the
#: notebook. They are instructions, they have already been carried out, and
#: running one a second time from a chip is at best pointless and at worst a
#: repeat of an action the user did not mean to repeat.
#:
#: The rule the user gave, in their words: "if I was in the chat and using the
#: 'ask' mode, then those queries should count, but only those, and my previous
#: requests in the 'ask' subtab in notes should be registered." So the two
#: reading surfaces: the Notes tab's Ask box (`notes_only`) and the Chat tab
#: in Ask mode (tools off): write `chat`; Request mode and the Ctrl+Shift+A
#: palette, both of which act, write `agent`. Both stay in the audit log, which
#: is a record of what happened and should not lose the requests; only the
#: chip row narrows.
ASK_SURFACE = "chat"


AGENT_SURFACE = "agent"


def _feature_for(body: "ChatRequest") -> str:
    """Which feature row a turn runs under: the Ask box or the Chat tab.

    Both post here. `notes_only` is set by the Notes tab's Ask box and never
    by the Chat tab (see the field), so it is the one fact that already tells
    the two apart without a second flag to keep in step.
    """
    return "ask" if body.notes_only else "chat"


def _recent_questions(session: Session, limit: int = 5) -> list[str]:
    """The last `limit` distinct questions asked at the Ask box, newest first.
    Read straight from the audit log, no extra bookkeeping.

    Scoped to `ASK_SURFACE`, so an instruction given to the agent is never
    offered back as something to ask again.

    **Clearable, without editing the log** (the owner, 2026-10-10: "There's
    no way to clear your ask history"; "no way to ... delete individual
    records??"). The log is a history, so nothing is deleted from it: Clear
    history writes a `cleared` row, and walking back stops there; forgetting
    one chip writes a `forgot` row naming it, which hides the earlier askings
    of that question and not a later one."""
    rows = session.scalars(
        select(AuditLog)
        .where(
            AuditLog.action.in_(("queried", "forgot", "cleared", "remembered")),
            AuditLog.entity_type == ASK_SURFACE,
        )
        .order_by(AuditLog.id.desc())
        .limit(100)
    )
    questions: list[str] = []
    forgotten: set[str] = set()
    #: A `remembered` row is Undo of a `forgot` or `cleared` one (INBOX 898):
    #: it names that row's id, and walking back, the row it names no longer counts.
    lifted: set[str] = set()
    for row in rows:
        if row.action == "remembered":
            lifted.add(row.detail or "")
            continue
        if str(row.id) in lifted:
            continue
        if row.action == "cleared":
            break
        if row.action == "forgot":
            forgotten.add(row.detail or "")
        elif row.detail and row.detail not in questions and row.detail not in forgotten:
            questions.append(row.detail)
        if len(questions) == limit:
            break
    return questions


def _asked_key(question: str) -> str:
    """One spelling of a question, for comparing the two suggestion rows.

    Only case and surrounding space: a chip is clicked verbatim, so a repeat
    is character-for-character the same string, and anything cleverer here
    (dropping the question mark, stemming) would start deciding that two
    *different* questions are the same one."""
    return " ".join(question.split()).casefold()


#: **The two suggestion rows do not show each other's chips.** Reported (INBOX
#: 120, the owner): "the try asking and ask again suggestions are nearly
#: identical", with "Try asking:" above "Ask again:" and two of the five chips
#: below repeating the row above word for word. The rows answer different
#: questions, what you could ask and what you already asked, so neither should
#: be showing the other's answer.
#:
#: The rule, decided with the report: the history row wins a duplicate, because
#: it is a fact about this notebook rather than something generated, and the
#: generated row fills the gap with its next candidate. Which is why this is
#: settled here, on the server that builds both rows, rather than in the two
#: independent `loadSuggestions`/`loadRecentQuestions` calls in the client,
#: where it would depend on which request came back first.
SUGGESTIONS_SHOWN = 4


def _fill(candidates: list[str], asked: set[str]) -> list[str]:
    """The first `SUGGESTIONS_SHOWN` candidates that are neither a repeat of
    each other nor already offered by "Ask again"."""
    picks: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = _asked_key(candidate)
        if key in seen or key in asked:
            continue
        seen.add(key)
        picks.append(candidate)
        if len(picks) == SUGGESTIONS_SHOWN:
            break
    return picks


# Shown when the chat is empty, to teach the feature (Round 1).
STARTER_SUGGESTIONS = [
    "What have I saved recently?",
    "Summarise my notes.",
    "What are my most common topics?",
]


def _about(name: str) -> str:
    """A category name as the object of "What have I saved about ...?".

    Lower-cased word by word as a noun in running text ("Travel plans" to
    "travel plans"), but a word with capitals inside it is a name and keeps
    them ("iPhone"), as does the app's own name, and a category already named
    "About X" gives "X": the seeded notebook's "About Tessellate" came out as
    "What have I saved about about ..." (the devibe pass, a 1440 still of the
    empty chat).
    """
    words = name.split()
    if len(words) > 1 and words[0].lower() == "about":
        words = words[1:]
    return " ".join(
        w if w in _NAMES or any(c.isupper() for c in w[1:]) else w.lower() for w in words
    )


#: Proper nouns `_about` keeps capitalised although they have no inner capital.
_NAMES = frozenset({"Tessellate"})
