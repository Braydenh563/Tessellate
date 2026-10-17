"""What a question put to the Guide asks, read from its words before the tab
it was asked from (INBOX 904 B11 and B86; BACKLOG "Guide answers what can I do
in the chat").

The owner, 2026-10-17: "The guide should also consider that some queries may
not be related to the current page the user is on and needs to better detect
intent". Measured on the Graph tab with no model the same day: "How do I use
the app??" and "cna you help me" were answered with the Graph's topic, "what
is this page for" with the board library (the word "page"), "what should I
ask" with a paragraph on Ask and Chat, and "What can Atlas change in my
notebook?", the chip Chat's own empty page offers, with Agent mode.

Five readings, each from the words alone:

* `IDEAS`: what to ask ("what should I ask", "what can I do in the chat").
  Answered with four or five concrete asks for the surface the words name
  (else the tab, else Chat), as chips that fill that box, and one line on
  the box's own menu.
* `HELP`: a bare request for help ("can you help me", "help"). What the
  Guide does, and the tab's three starters (the greeting's chips).
* `ATLAS`: what Atlas can change. The note acts the registry holds
  (`act_registry.ACTS`), so the list is the one Chat runs.
* `APP`: how to use the app as a whole. The tabs overview and first steps,
  whatever tab is open.
* `PAGE`: what this page is for. The open tab's own topics, never a topic
  that merely says "page".
"""

from __future__ import annotations

import hashlib
import re

IDEAS = "ideas"
HELP = "help"
ATLAS = "atlas"
APP = "app"
PAGE = "page"

_IDEAS = re.compile(
    r"\bwhat (?:should|can|could|do|would) (?:i|we) (?:ask|say|type|try|write in)\b"
    r"|\bwhat (?:can|could|should) i do (?:in|with|on|from) (?:the |this )?(?:chat|ask|box)\b"
    r"|\bwhat (?:kinds?|sorts?|types?) of (?:questions|things) (?:can|should|could|do) (?:i|you)\b"
    r"|\b(?:give me|any|some) (?:ideas|examples|suggestions)\b"
    r"|\bexamples? of (?:questions|what to ask)\b|\bwhat to ask\b",
    re.I,
)
_HELP = re.compile(
    r"^(?:(?:can|could|would|will) you help(?: me)?(?: out)?|help(?: me)?(?: please| pls)?|please help(?: me)?"
    r"|i need (?:some )?help|i'?m (?:lost|stuck|confused|new here))\W*$",
    re.I,
)
_ATLAS = re.compile(
    r"\bwhat (?:can|could|will|does|is) (?:atlas|you|the assistant|the ai) (?:able to )?"
    r"(?:change|edit|modify|alter|touch|update|organise|organize|do to|do with|do in)\b",
    re.I,
)
_APP = re.compile(
    r"\bhow (?:do|can|should) (?:i|we|you) use (?:the|this) (?:app|program|thing|notebook)\b"
    r"|\bhow (?:does|do) (?:the|this) (?:app|program|notebook|tessellate) work\b|\bhow does tessellate work\b"
    r"|\bwhere (?:do|should) i (?:start|begin)\b|\bgetting started\b|\bget started\b"
    r"|\bwhat is (?:this|the) app(?: for)?\b|\bwhat does (?:this|the) app do\b",
    re.I,
)
_PAGE = re.compile(
    r"\bwhat(?:'s| is) (?:this|the) (?:page|tab|screen|view|panel|place)\b"
    r"|\bwhat (?:does|can) (?:this|the) (?:page|tab|screen|view|panel) do\b"
    r"|\bwhat am i (?:looking at|seeing)\b"
    r"|\b(?:explain|describe) (?:this|the) (?:page|tab|screen|view)\b"
    r"|\bhow (?:does|do) (?:this|the) (?:page|tab|screen|view) work\b"
    r"|\bwhat can i do (?:here|on this (?:page|tab|screen))\b",
    re.I,
)

#: The surface a question names, in the words people use for it.
_SURFACE = (
    ("notes", re.compile(r"\b(?:ask box|the ask|notes tab|ask your notebook|in ask)\b", re.I)),
    ("reminders", re.compile(r"\breminders?\b", re.I)),
    ("chat", re.compile(r"\b(?:chat|the box|agent)\b", re.I)),
)

#: Asks the app answers with no model, per surface: each one is run through
#: the route in `tests/test_guide_intent.py` and must not come back empty.
ASKS: dict[str, tuple[str, ...]] = {
    "chat": (
        "What did I write this week?",
        "What is due soon?",
        "Summarise my recent notes",
        "How many notes do I have?",
        "Remind me to call mum tomorrow at 6pm",
    ),
    "notes": (
        "What have I saved recently?",
        "What do my notes cover?",
        "What did I write last month?",
        "How many notes did I write this week?",
    ),
    "reminders": (
        "What is due this week?",
        "Remind me to water the plants every Sunday",
        "Remind me to call mum tomorrow at 6pm",
        "What did I write this week?",
    ),
}

#: Where the asks go, by name, for the lead.
_WHERE = {"chat": "Chat", "notes": "the Notes tab's Ask box", "reminders": "Chat"}

_IDEAS_LEADS = (
    "A few things to try in {where}:",
    "Some questions {where} answers well:",
    "Try one of these in {where}:",
    "Good first asks for {where}:",
    "Here are some things to ask in {where}:",
    "These work well in {where}:",
    "For a start, {where} takes any of these:",
    "A handful of asks that work in {where}:",
)

_IDEAS_TAILS = {
    "chat": "Typing / in the chat box opens its menu: attach a note or a file, web search, skills, commands such as /recent, and Agent or Ask mode.",
    "notes": "Ask answers from your notes' own words; Chat can also act on them.",
    "reminders": "Ask these in Chat; the Reminders tab's Magic add line takes the reminders too.",
}

_HELP_LINES = (
    "Yes. I'm the app's guide: ask me where a feature lives, what a setting does or how to do something here. Three to start with:",
    "Happy to. I answer questions about the app itself: where things are, what a setting does, how to do something. Some to start with:",
    "Of course. Ask me how to do something here, where a control lives or what a setting changes. Three to try:",
    "Sure. I know the app's own help: which tab does what, where each setting is, and the steps for most things. To start:",
    "I can. Tell me what you are trying to do, or where you are stuck, and I'll say where and how. Or pick one of these:",
    "That's what I'm for: how-tos, where a feature lives, what a setting means. Three questions people start with:",
    "Yes. Ask about any tab or setting, or say what you want to do and I'll give you the steps. For instance:",
    "Gladly. I answer from the app's own help, so ask how, where or what about anything in it. A few to begin:",
)

_ATLAS_LEADS = (
    "In Chat, Atlas changes your notebook when you ask it to. It can {acts}.",
    "Atlas can make these changes from Chat: {acts}.",
    "Ask in Chat and Atlas will {acts}.",
    "From Chat, Atlas can {acts}.",
    "These are the changes Atlas makes when asked in Chat: it can {acts}.",
    "Atlas acts on your notes from Chat: it can {acts}.",
    "Say what you want in Chat and Atlas can {acts}.",
    "Atlas's changes, all asked for in Chat: it can {acts}.",
)


def read(question: str) -> str | None:
    """The reading, or None for a question that names a feature itself."""
    text = " ".join((question or "").split()).strip()
    if not text:
        return None
    if _HELP.match(text.rstrip("?!. ")):
        return HELP
    if _ATLAS.search(text):
        return ATLAS
    if _IDEAS.search(text):
        return IDEAS
    if _APP.search(text):
        return APP
    if _PAGE.search(text):
        return PAGE
    return None


def surface(question: str, tab: str | None) -> str:
    """The surface whose asks a question about asking wants: named in the
    words, else the tab's own, else Chat."""
    for name, words in _SURFACE:
        if words.search(question or ""):
            return name
    return tab if tab in ASKS else "chat"


def _pick(options: tuple[str, ...], seed: str) -> str:
    digest = hashlib.sha256((seed or "").strip().lower().encode("utf-8")).digest()
    return options[digest[0] % len(options)]


#: Undoing acts ("take a tag off") are the same change the other way: the
#: list names the doing once.
_UNDOING = frozenset({"untag", "unpin", "unlink", "meeting"})


def _acts_said() -> str:
    """The note acts, as one list: the registry's labels, in its order."""
    from tessellate.ai import act_registry

    labels = [a.label for a in act_registry.ACTS.values() if a.writes and a.intent not in _UNDOING]
    return ", ".join(labels[:-1]) + " or " + labels[-1]


_COUNTS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")
_TAB_LINE = re.compile(r"\b([A-Z][a-z]+): ([^.]+)\.")


def _app_overview(by_id: dict[str, dict]) -> str:
    """How the app is laid out, a line a tab, from the tabs overview's own
    words, and how a new notebook starts (first steps)."""
    body = str(by_id.get("tabs-overview", {}).get("body") or "")
    tabs = _TAB_LINE.findall(body)
    if not tabs:
        return ""
    counted = _COUNTS[len(tabs)] if len(tabs) < len(_COUNTS) else str(len(tabs))
    lines = [f"Tessellate has {counted} tabs along the top:", "\n".join(f"- **{name}**: {what}." for name, what in tabs)]
    lines.append(
        "Settings (the gear, or Ctrl+,) holds the rest. A new notebook's Dashboard shows Start in three steps "
        "(your name, a first note, a first question), and Settings, Help starts the guided tour."
    )
    return "\n\n".join(lines)


def reply(question: str, tab: str | None, by_id: dict[str, dict]) -> dict | None:
    """The Guide's own answer for APP, IDEAS, HELP and ATLAS, in the shape
    `help_chat.offline_answer` returns; None for any other reading. `by_id`
    is the help's topics by id (passed in: this module sits below help_chat
    in the import graph)."""
    kind = read(question)
    if kind == APP:
        said = _app_overview(by_id)
        return {"content": said, "badges": [], "sources": ["Tabs overview", "First steps"]} if said else None
    if kind == IDEAS:
        where = surface(question, tab)
        asks = ASKS[where]
        lead = _pick(_IDEAS_LEADS, question).format(where=_WHERE[where])
        body = "\n".join(f"- {ask}" for ask in asks)
        return {
            "content": f"{lead}\n\n{body}\n\n{_IDEAS_TAILS[where]}",
            "badges": [],
            "sources": [],
            "asks": list(asks),
            "asks_to": "notes" if where == "notes" else "chat",
        }
    if kind == HELP:
        return {"content": _pick(_HELP_LINES, question), "badges": [], "sources": [], "greeting": True}
    if kind == ATLAS:
        from tessellate.ai import act_registry

        lead = _pick(_ATLAS_LEADS, question).format(acts=_acts_said())
        example = f"For example, “{act_registry.ACTS['tag'].example}” or “{act_registry.ACTS['reminder'].example}”."
        guard = (
            "Each change has Undo; reminders, new notes and pins happen at once, and tags, moves, renames, "
            "links, added lines and deletes wait for you to confirm them."
        )
        model = "With no model running the app does these itself from your words; a connected model adds writing and its other tools."
        return {
            "content": f"{lead} {example}\n\n{guard} {model}",
            "badges": [],
            "sources": ["Ask chat"],
            "asks": [act_registry.ACTS["tag"].example, act_registry.ACTS["reminder"].example],
            "asks_to": "chat",
        }
    return None


def topics(question: str, tab: str | None, by_id: dict[str, dict], tab_topics: dict[str, tuple]) -> list[dict] | None:
    """The topics an APP or PAGE question is about, whatever topic its words
    happen to share a keyword with; None for any other reading."""
    kind = read(question)
    if kind == APP:
        ids = ("tabs-overview", "first-steps")
    elif kind == PAGE:
        ids = tab_topics.get(tab or "", ()) or ("tabs-overview",)
    else:
        return None
    found = [by_id[i] for i in ids if i in by_id]
    return found or None
