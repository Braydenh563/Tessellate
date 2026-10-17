"""A question about Atlas is answered about Atlas (CHAT_PLAN decision 65).

INBOX 810, the owner: "I asked if it could web search and then searched the
web for the word "web" and then didnt even output the results". "Can you
search the web?" is a question about the assistant, not a search: it is
answered here, from what the app can do and the switch that turns each on,
and it never reaches retrieval, the web or a tool.

A request is not a capability question: "can you search the web for
gaming mice" names what to do, and "can you remind me to call mum" is an
act. `asks` reads the difference by what follows the verb: a request
carries its object ("for ...", "my ...", "to <verb> ..."); a capability
question stops at the thing ("the web", "maths", "reminders").
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_LEAD = re.compile(
    r"^(?:hey |so |ok |okay )?(?:atlas,? )?"
    r"(?:can|could|will|would|do|does) (?:you|u|atlas|it|the app|this app)(?: (?:actually|even|also|ever|still))?"
    r"(?: be able to)? (?P<rest>\S.*)$"
    r"|^(?:are|r) (?:you|u) (?:able|allowed|capable of|good at) (?:to )?(?P<rest2>.+)$"
    r"|^is (?:it|there a way) (?:possible )?(?:to |for (?:you|me) to )?(?P<rest3>.+)$"
    r"|^(?:do you (?:know how to|have|support)|have you got) (?P<rest4>.+)$",
    re.I,
)
_OVERVIEW = re.compile(
    r"^(?:what|which things?) (?:can|could|do) (?:you|u|atlas|i) (?:do|help (?:me )?with)(?: (?:here|for me|in (?:this|the) app|on (?:this|the) app|with (?:you|this|it)))?$"
    r"|^what (?:are|r) (?:you|u) (?:able to do|capable of|good at|for)$"
    r"|^what (?:are )?(?:your|atlas'?s?) (?:abilities|capabilities|features|skills|powers|tools)$"
    r"|^(?:what can i (?:ask|say|do)(?: (?:you|here|in (?:this|the) app|on (?:this|the) app))?)$"
    r"|^how can you help(?: me)?$|^what do you do$",
    re.I,
)
#: What turns a capability question into a request: an object of its own.
_REQUEST = re.compile(
    r"\b(?:for|about|abt|regarding|mentioned|wrote|written|called|named|that says|me to|this note|these|those)\b|\bthe (?:\w+ )?note\b"
    r"|\bmy (?!notes?\b|history\b|files?\b|reminders\b|stuff\b|things\b)|\"|“",
    re.I,
)


@dataclass(frozen=True)
class Capability:
    key: str
    words: re.Pattern
    can: str
    how: str
    #: The preference that turns it on, and where it lives; None is always on.
    switch: str | None = None
    where: str = ""
    #: Needs a model running (translation, writing a draft).
    model: bool = False


CAPABILITIES: tuple[Capability, ...] = (
    #: "do you send my notes anywhere" was answered "Yes. Say make a note"
    #: (item 8 of the composer brief, 2026-10-11): privacy first.
    Capability("privacy", re.compile(
        r"\b(send|sends|sending|share|sharing|upload\w*|sell|leak\w*|cloud|servers?|track\w*|spy\w*|private|privacy|"
        r"(?:go|goes|leave|leaves|sent) (?:anywhere|to the internet|this (?:computer|device|laptop|pc))|safe|secure|stored|kept)\b", re.I),
        "No.", "Your notes stay on this computer, and nothing is sent anywhere on its own. Web search sends only the words "
        "you search for, and only when it is on; a model you connect gets the notes a question needs, so one running on "
        "this computer keeps everything here."),
    Capability("access", re.compile(r"\b(see|read|access|look at|view|know)\b(?: \w+){0,2} (?:notes?|stuff|files|data)\b", re.I),
               "Yes, here on this computer.", "I read your notes to answer you, and they never leave it."),
    Capability("web", re.compile(r"\b(web|internet|online|google|browse|websites?|pages?|look (?:it )?up)\b", re.I),
               "Yes, when web search is on.",
               "Ask \"search the web for ...\" and I answer from the pages I read, with their links under the answer.",
               switch="web_search_enabled", where="Settings, Web search"),
    Capability("reminders", re.compile(r"\b(remind(?:ers?)?|alarms?|alerts?|nudge)\b", re.I),
               "Yes.", "Say \"remind me to call Sam on Friday\" and I set it, with Undo."),
    Capability("maths", re.compile(r"\b(maths?|sums?|calculat\w*|add (?:up|numbers)|arithmetic|percent\w*|multiply|divide)\b", re.I),
               "Yes, with no model.", "Type the sum, \"15% of 80\" or \"12 * 7\", and I work it out."),
    Capability("time", re.compile(r"\b(time ?zones?|the time|clocks?|what time)\b", re.I),
               "Yes, with no model.", "Ask \"what's the time in Perth\" or \"9am London in Tokyo\"."),
    Capability("dates", re.compile(r"\b(dates?|days until|how long until|calendar|countdown)\b", re.I),
               "Yes, with no model.", "Ask \"days until 25 December\" or \"what day is 3 March\"."),
    Capability("stats", re.compile(r"\b(stat(?:istic)?s|averages?|mean|median|count(?:s|ing)?)\b", re.I),
               "Yes, with no model.", "Ask \"average of 3, 8, 10\", or \"notebook stats\" for your notes in numbers."),
    Capability("convert", re.compile(r"\b(convert\w*|units?|currenc\w*|exchange rates?)\b", re.I),
               "Yes, with no model.", "Ask \"5 miles in km\" or \"20 USD in AUD\"."),
    Capability("notes", re.compile(r"\b(notes?|write (?:things )?down|save (?:things|stuff)|capture|remember (?:things|stuff))\b", re.I),
               "Yes.", "Say \"make a note: ...\" and I save it; ask \"what have I saved about uni?\" and I answer from your notes."),
    Capability("search", re.compile(r"\b(search|find|look through)\b", re.I),
               "Yes, your notes always.", "Ask \"what is there about the gaming mouse?\" and I answer from the notes that match."),
    Capability("organise", re.compile(r"\b(tags?|tagging|file|filing|organi[sz]\w*|categor\w*|sort)\b", re.I),
               "Yes.", "New notes are filed for you; say \"tag the gym note strength\" or open Tidy for the rest."),
    Capability("translate", re.compile(r"\b(translat\w*|languages?|french|spanish|german)\b", re.I),
               "Only with a model running.", "Connect a model in Settings, Models, then ask \"translate this into French\".", model=True),
    Capability("write", re.compile(r"\b(write (?:an? |me )?(?:essay|email|story|poem|draft)|draft\w*|essays?|emails?)\b", re.I),
               "Only with a model running.", "Connect a model in Settings, Models; with none I answer from your notes.", model=True),
    Capability("pictures", re.compile(r"\b(pictures?|images?|photos?|screenshots?|ocr|scan\w*)\b", re.I),
               "Yes.", "Attach a picture to a note and I read the words in it, so search finds them."),
    Capability("voice", re.compile(r"\b(voice|speak|talk|read (?:it )?(?:aloud|out)|dictat\w*|microphone|listen)\b", re.I),
               "Yes.", "Press the microphone to dictate, or the speaker under an answer to hear it."),
    Capability("history", re.compile(r"\b(history|records?|what i searched|log)\b", re.I),
               "Yes.", "Ask \"what did I search yesterday\", \"what ran overnight\" or \"when did I last back up\"; History beside the Ask box keeps every answer."),
)

#: The overview is composed, not stored (owner, 2026-10-17: "this should be
#: composed and not a set response, with variations, longer or shorter based
#: on response style and user request"). An opening that says who is speaking,
#: the groups the request and its length call for, what a model adds, and one
#: thing to try; each part has several phrasings and `phrasing.choose` picks
#: the one unlike the last replies.
_SHORT = re.compile(r"\b(?:briefly|brief|quick(?:ly)?|short(?:ly)?|tl;?dr|in a word|one line|summary|nutshell)\b", re.I)
_LONG = re.compile(
    r"\b(?:everything|all (?:of )?(?:it|your|the)|in detail|detailed|full|complete|list|every|properly|fully|explain)\b", re.I
)

_OPENING = {
    "natural": (
        "I'm Atlas's assistant. I work without a model: I answer from your notes, do sums, times and dates, and act on the app for you.",
        "I'm the assistant that comes with Tessellate and works for Atlas. On my own I read your notes, work things out and do small jobs.",
        "Atlas's assistant here. Without a model I can still answer from your notes, do the maths and dates, and run the app for you.",
        "I'm Atlas's assistant, the part that answers when no model is connected: your notes, quick sums and dates, and jobs in the app.",
    ),
    "professional": (
        "I am Atlas's assistant. Without a model I answer from your notes, calculate times and dates, and carry out tasks in the app.",
        "I am the assistant that serves Atlas. On my own I search your notes, perform calculations and act on the app on request.",
        "This is Atlas's assistant. It answers from your notes, works out sums and dates, and performs small tasks in the app.",
    ),
}
_GROUPS = (
    ("Ask", (
        "what you saved about a topic, what you did on a day, how a habit is going.",
        "when something is, who said what, what you decided and what is still open.",
        "anything you wrote down: a date, a list, how a project is going.",
    )),
    ("Work things out", (
        "maths, time zones, days until a date, averages.",
        "sums, conversions, how long until a date, a quick average.",
        "dates and numbers, such as days until an event or a total.",
    )),
    ("Act", (
        "make a note, set a reminder, file or tag notes, open any page.",
        "add a note, set a reminder, tag, pin or move notes, jump to any page.",
        "create and organise notes, set reminders and open any part of the app.",
    )),
    ("Look around", (
        "the graph, the timeline, boards, mind maps and documents are all open to me.",
        "I can open the graph, the timeline, your boards, maps and documents.",
        "the graph, timeline, boards, maps and documents are one request away.",
    )),
    ("Private", (
        "everything stays on this computer; nothing leaves unless you turn web search on.",
        "your notes never leave this computer unless you switch web search on.",
    )),
    ("Remember", (
        "your reminders, your habits and what changed since last week.",
        "reminders, habits, and what you wrote this week compared with last.",
    )),
)
_SHORT_LINE = (
    "I answer from your notes, do sums and dates, and act on the app.",
    "Notes, quick maths and dates, and jobs in the app: that is what I do.",
    "In short: I search your notes, work things out and run the app for you.",
)
_MODEL = {
    False: (
        "To talk to Atlas itself, connect a model in Settings, Models. It adds writing and translating.",
        "Atlas is the model you connect: add one in Settings, Models and it can write, translate and use tools.",
        "Connect a model in Settings, Models to talk to Atlas, which adds writing and translating.",
    ),
    True: (
        "Atlas, the model you connected, can also write and translate.",
        "A model is connected, so Atlas can write and translate as well.",
        "With your model running, Atlas can also write drafts and translate.",
    ),
}
_TRY = (
    "Try \"what have I saved about uni?\"",
    "Try \"what did I do last week?\"",
    "Try \"remind me to call the dentist on Friday\".",
    "Try \"how many days until my birthday?\"",
    "Say \"what's on today?\" to start.",
)


def overview(
    question: str = "", *, model_running: bool = False, voice: str = "natural", recent=(), seed: str = ""  # noqa: ANN001
) -> str:
    """The composed rundown of what the assistant can do: shorter for "briefly",
    longer for "everything", the same words never twice in a row."""
    from tessellate.ai import phrasing

    pick = lambda key, options: phrasing.choose(options, f"capability:{key}", recent, seed)  # noqa: E731
    professional = voice == "professional"
    model = pick("model", _MODEL[model_running])
    asked = question or ""
    if _SHORT.search(asked):
        return " ".join([pick("short", _SHORT_LINE), model])
    count = 6 if _LONG.search(asked) else 3
    lines = [pick("open", _OPENING["professional" if professional else "natural"])]
    for label, options in _GROUPS[:count]:
        lines.append(f"**{label}:** {pick(label, options)}")
    lines.append(model)
    lines.append(pick("try", _TRY))
    return "\n\n".join(lines)


#: Said after or before a rundown request: it sets the length (`overview`)
#: and does not change what is asked. Stripped with `endswith`, not a regex:
#: an end-anchored run is polynomial on a long input (CodeQL).
_TAILS = ("briefly", "in short", "in brief", "quickly", "please", "pls", "in detail", "in full", "thanks")
_RUNDOWN = re.compile(
    r"^(?:please |pls )?(?:tell me|show me|list|give me|explain|describe)(?: me)? (?:everything|all|a list of everything|what)"
    r"(?: that)?(?: you (?:can|could|are able to) do| you do)$",
    re.I,
)


def _clean(question: str) -> str:
    text = " ".join((question or "").split())
    #: str.strip, not a regex: an end-anchored character run is polynomial
    #: on a long run of the same mark (CodeQL).
    text = text.lstrip("\\/'\"` ").rstrip("\\/'\"`?.! ")
    low, trimmed = text.lower(), False
    while True:
        tail = next((t for t in _TAILS if low.endswith(" " + t) or low.endswith("," + t)), None)
        if tail is None:
            break
        low, trimmed = low[: -len(tail)].rstrip(" ,"), True
    if _RUNDOWN.match(low):
        return "what can you do"
    return low if trimmed and _OVERVIEW.match(low) else text


#: "do my notes go online", "is my data private", "where are my notes
#: stored": a question about where the notes go, answered by "privacy".
_PRIVACY = re.compile(
    r"^(?:do|does|will|would|are|is|can|could) (?:my|your|the|all my) (?:notes?|data|stuff|files|information|info|entries)\b.*"
    r"\b(?:go|leave|sent|send|online|cloud|private|safe|secure|shared|uploaded|stored|seen)\b"
    r"|^(?:is|are) (?:this|it|the app|this app|atlas|memorymap) (?:private|safe|secure|online|offline|local)\b"
    r"|^where (?:are|is|do|does) (?:my|the) (?:notes?|data|stuff|files) (?:stored|kept|go|saved|live)\b",
    re.I,
)


def asks(question: str) -> bool:
    """Whether `question` asks what Atlas can do rather than asking it to."""
    text = _clean(question)
    if _OVERVIEW.match(text) or _PRIVACY.match(text):
        return True
    m = _LEAD.match(text)
    if not m:
        return False
    rest = next(g for g in (m.group("rest"), m.group("rest2"), m.group("rest3"), m.group("rest4")) if g)
    if _REQUEST.search(rest) or len(rest.split()) > 6:
        return False
    return any(c.words.search(rest) for c in CAPABILITIES) or bool(re.match(r"^(?:help|do (?:things|stuff|anything))\b", rest, re.I))


def _private(c, text: str) -> str:  # noqa: ANN001  # a capability row
    """"is my data private" is a yes; "do you send my notes" a no; "where are
    my notes stored" neither (the answer says where)."""
    if re.match(r"^where\b", text, re.I):
        return c.how
    sending = re.search(r"\b(send|sends|sent|sending|share|sharing|upload\w*|sell|leak\w*|cloud|servers?|track\w*|spy\w*|online|go|goes|leave|leaves)\b", text, re.I)
    return f"{'No.' if sending else 'Yes.'} {c.how}"


def privacy_line(question: str) -> str | None:
    """The yes or no a privacy question gets ("is my data sent anywhere": No,
    and where it stays), or None for any other question: the Guide leads
    with it rather than with the Privacy topic's first sentence."""
    text = _clean(question)
    return answer(question) if _PRIVACY.match(text) else None


def answer(
    question: str, *, prefs: dict | None = None, model_running: bool = False, voice: str = "natural", recent=(), seed: str = ""  # noqa: ANN001
) -> str:
    """The capability line for `question`: whether, how, and the switch.
    `prefs` are the saved preferences (the switches' state)."""
    prefs = prefs or {}
    text = _clean(question)
    found = [c for c in CAPABILITIES if c.words.search(text)] if not _OVERVIEW.match(text) else []
    if _PRIVACY.match(text):
        found = [c for c in CAPABILITIES if c.key == "privacy"]
    if not found:
        return overview(question, model_running=model_running, voice=voice, recent=recent, seed=seed)
    c = found[0]
    if c.key == "privacy":
        return _private(c, text)
    lines = []
    if c.model and model_running:
        lines.append("Yes, with the model you have connected.")
    else:
        lines.append(c.can)
    lines.append(c.how)
    if c.switch:
        on = bool(prefs.get(c.switch, False))
        lines.append(f"It is {'on' if on else 'off'} now, in {c.where}.")
    return " ".join(lines)
