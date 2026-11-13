"""The Guide's answers to general and advice questions, with no model (L-chat-34).

The owner, 2026-11-13: "the guide should be able to respond like a chatbot
with the composer when an ai model isnt there so if I ask general questions or
advice then it can provide". A how-to question finds its help topic; "what
should I use chat for?" or "should I use categories or tags?" asks for a
recommendation, which no topic leads with, so it used to get a topic's first
line (Ask's controls) or "I don't have help on that".

Each entry answers first, in the app's voice, then names the help topics it
stands on: the reply's badges open them and its sources list them, and the
reply is composed, so its byline says it is the app's own help. Every claim
in an answer is a fact one of its topics states (`tests/test_guide_advice_l34.py`
checks the topics exist and pins each answer's first sentence). With a model
running the model answers (CHAT_PLAN decision 75): this is only read by the
offline path, through `guide_intent.reply`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Asking for a recommendation rather than a place or a step: "should I",
#: "best way", "tips", "advice", "good for", "how can I ... better".
_CUE = (
    r"\b(?:should i|shall i|best way|good way|right way|quickest way|fastest way|easiest way|tips?|advice|"
    r"recommend\w*|good for|better|difference between|or a\b|or tags|or categories|why use|separate|"
    r"stay on top|keep on top|keep track)\b"
)
_ADVICE = re.compile(_CUE, re.I)


@dataclass(frozen=True)
class Advice:
    id: str
    about: re.Pattern
    answer: str
    topics: tuple[str, ...]
    asks: tuple[str, ...] = ()
    #: An entry whose words alone ask for advice ("what is chat good for").
    plain: bool = False


def _rx(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.I)


#: In the order they are tried: the narrower subjects first.
ADVICE: tuple[Advice, ...] = (
    Advice(
        "chat-vs-ask",
        _rx(r"\bdifference between (?:the )?(?:chat|ask)\b.*\b(?:chat|ask)\b|\b(?:chat|ask) (?:or|vs\.?|versus) (?:chat|ask)\b"),
        "Both answer from your saved notes, with the notes beside the answer. Ask (the Notes tab's “Ask "
        "your notebook” box) is for a quick question while you are in your notes; Chat keeps a "
        "conversation and also does things, such as setting a reminder or tagging a note, with Undo.",
        ("ask-chat", "chat-acts"),
        plain=True,
    ),
    Advice(
        "chat-for",
        _rx(r"\b(?:use|using) (?:the )?chat (?:tab )?for\b|\bchat (?:tab )?(?:good|useful|for)\b|\bwhat (?:is|does) (?:the )?chat (?:tab )?(?:for|do)\b"),
        "Use Chat to ask about your own notes and to get small jobs done: “what did I write about the "
        "boiler?”, “remind me to call mum on Friday at 9” or “tag the knife note with "
        "kitchen”. It answers from your saved notes, with the notes beside the answer, and it works with "
        "no model; a connected model adds writing.",
        ("ask-chat", "tasks"),
        ("What did I write this week?", "What is due soon?"),
        plain=True,
    ),
    Advice(
        "organise",
        _rx(r"\b(?:organi[sz]e|organi[sz]ing|sort|structure|file)\b.*\bnotes?\b|\bcategor(?:y|ies)\b|\btags?\b|\bspaces?\b"),
        "Let filing do the first pass: Atlas files each note into a category and suggests tags, and you can "
        "change either from the note's own row. Use the category for what a note is (one each) and tags for "
        "what it touches (as many as you like, typed as #word as you write); a space keeps a whole area of "
        "life apart.",
        ("tags-categories", "spaces"),
    ),
    Advice(
        "tasks",
        _rx(r"\b(?:tasks?|to-?dos?|todo list|things to do|on top of|keep track|deadlines?|reminders?)\b"),
        "Put anything with a time in a reminder and anything without one on a checklist line (- [ ]) in a "
        "note; Chat handles both from one sentence. The Reminders tab groups them into Overdue, Today, "
        "Upcoming and Done, so one look there shows what needs doing.",
        ("tasks", "reminders"),
        ("What is due soon?", "What are my open tasks?"),
    ),
    Advice(
        "plan-week",
        _rx(r"\bplan(?:ning)? (?:my |the )?(?:week|day|month)\b|\b(?:week|day) ahead\b"),
        "Ask Chat “what is due this week?”, then open the Timeline: its feed shows the week ahead "
        "above today, and an empty day has an Add for a reminder or an event.",
        ("timeline", "reminders"),
        ("What is due this week?",),
    ),
    Advice(
        "backup",
        _rx(r"\bback(?:ing)? ?ups?\b|\bback (?:it |things |my notes )?up\b"),
        "The app makes a daily backup for you in its data folder, and Settings, Import & export shows where "
        "that folder is and saves a full backup to a file (sealed with a password if you like). Keep one of "
        "those files on another drive now and then: a backup on the same disk does not outlive the disk.",
        ("storage",),
    ),
    Advice(
        "write-notes",
        _rx(r"\b(?:write|writing|take|taking|make|making) (?:better|good|great|useful) notes?\b|\bnotes? (?:better|well)\b"),
        "Keep one subject per note and say it in the first line, so filing, search and Chat have one clear "
        "thing to find. Link related notes by typing [[ and a title, and pick a template in Capture for notes "
        "you write often.",
        ("capture", "links", "templates"),
    ),
    Advice(
        "remember",
        _rx(r"\b(?:remember|memori[sz]e|revise|revision|study|studying|learn)\b"),
        "Turn your notes into practice: in Chat, say “quiz me on lecture 5” or “make "
        "flashcards from this note”. Both work with no model, built from the note's definitions, bold "
        "terms and lists.",
        ("studyhelp",),
        ("Quiz me on my newest note",),
    ),
    Advice(
        "map-or-board",
        _rx(r"\bmind ?maps?\b|\b(?:white)?boards?\b"),
        "A mind map suits one idea broken into branches; a board suits sketches and note cards laid out "
        "freely. Both live in the Library, under Boards & maps, and a note's menu can make a mind map from "
        "its headings.",
        ("mind-maps", "whiteboard"),
    ),
    Advice(
        "journal",
        _rx(r"\b(?:journal\w*|diary|daily notes?|daily log)\b"),
        "Write one note a day, from a template of your own if you like a fixed outline, and the Timeline "
        "groups them by day. The Dashboard keeps your streak, and Chat can answer “what did I write "
        "last week?” from them.",
        ("templates", "timeline", "dashboard"),
        ("What did I write last week?",),
    ),
    Advice(
        "find",
        _rx(r"\b(?:find(?:ing)?|search(?:ing)?|look(?:ing)? up)\b"),
        "Use Find anything (Ctrl+P): it looks through every kind at once, by your words and by meaning, and "
        "tag:work or cat:work narrows it.",
        ("search",),
    ),
    Advice(
        "meetings",
        _rx(r"\bmeetings?\b"),
        "Start it with New meeting: it opens a note with Agenda, Notes, Decisions and Action items, and Start "
        "and open recorder writes what is said into its Notes.",
        ("meetings",),
    ),
    Advice(
        "graph",
        _rx(r"\b(?:the )?graph\b"),
        "The Graph shows how your notes connect: the links you made between them, plus optional similarity "
        "lines, with a legend that turns categories on and off.",
        ("graph", "links"),
    ),
    Advice(
        "jot",
        _rx(r"\b(?:jot|capture|note (?:something|it|an idea) down|ideas? down|write (?:something|it) down)\b"),
        "Use Quick note (Alt+N): a small box over whatever tab you are on, and Ctrl+Enter saves and files "
        "the note while you stay where you were.",
        ("quick-note", "capture"),
    ),
)


def match(question: str) -> Advice | None:
    """The entry an advice question asks for; None for a how-to or anything else."""
    q = " ".join((question or "").split())
    advising = bool(_ADVICE.search(q))
    for advice in ADVICE:
        if (advising or advice.plain) and advice.about.search(q):
            return advice
    return None


def reply(question: str, by_id: dict[str, dict]) -> dict | None:
    """The Guide's reply for an advice question, in `offline_answer`'s shape."""
    advice = match(question)
    if advice is None:
        return None
    topics = [by_id[i] for i in advice.topics if i in by_id]
    badges: list[dict] = []
    for topic in topics:
        if topic["badge"] not in badges:
            badges.append(topic["badge"])
    out = {
        "content": advice.answer,
        "badges": badges,
        "sources": [t["id"].replace("-", " ").capitalize() for t in topics],
    }
    return {**out, "asks": list(advice.asks), "asks_to": "chat"} if advice.asks else out
