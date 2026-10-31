"""A message the composer cannot place is not a web search (INBOX 1490).

The owner, 2026-10-31: "ur mum" and "japanese", sent with Web search on and no
model, answered "I tried to search the web, but the search service at
127.0.0.1 is not answering ... docker run ...". "All results with the composer
that it doesn't understand tend to be met with the web search."

The web is for what the person asked of it, so it is chosen by evidence
(`worthy`): the words "search the web", or a question about the world with a
shape ("what is the capital of France", "weather in Brisbane", "how to
descale a kettle"). Everything else with no note to answer it (banter, slang,
a bare word, an emoji, a name) is `unplaced`: it gets a short question back
with two chips, never a search, so the class is closed by what a search needs
rather than by a list of what is not one.
"""

from __future__ import annotations

import re

from tessellate.ai import realise, toolwords

#: A note, a notebook, "my ...": the person is asking about their own record,
#: whose home is the notes (the web is a chip, never the first stop).
_NOTES = re.compile(r"\b(?:notes?|notebook|entr(?:y|ies)|journal|diary)\b|\bmy\b", re.I)
#: A thing the notebook holds, said without "note" or "my": "open checklist
#: items", "overdue tasks", "what's due", "any reminders". The app's own
#: readers answer these (an empty answer included), so they are never asked
#: back. Kept out of `lookup`, so "list of countries in europe" stays a lookup.
_NOTEBOOK_THINGS = re.compile(
    r"\b(?:check-?lists?|to-?dos?|todos?|reminders?|tasks?|overdue|deadlines?|appointments?|items?|lists?|"
    r"due (?:today|tomorrow|soon|this|next|on|by|date)|(?:what's|whats|whos|what is) due)\b",
    re.I,
)
#: The person speaking of themselves ("how long since I called dad", "what did
#: I buy for Mum"): their own record, whose home is the notes, never banter.
_FIRST_PERSON = re.compile(r"\b(?:i|i'm|im|i've|ive|i'd|i'll|we|our|mine|myself)\b")
#: An instruction aimed at the app or at what is on screen ("summarise this",
#: "open it", "undo", "try again"): the app's own readers answer or say why not.
_INSTRUCTION = re.compile(
    r"^(?:(?:please|pls|can you|could you|just|ok|okay|now|and|then) )*(?:summari[sz]e|open|delete|remove|rewrite|translate|pin|unpin|read|shorten|"
    r"lengthen|expand|explain|tag|untag|rename|copy|share|export|print|save|add|check|fix|improve|proofread|continue|finish|redo|undo|retry|again|"
    r"do it again|try again|go on|carry on|edit|move|merge|split|archive|restore|show|list|find|search|set|remind|create|make|write|draft)\b"
)
#: The question words and auxiliaries a question opens with.
_ASK_OPEN = re.compile(
    r"^(?:what|whats|what's|who|whos|who's|where|wheres|where's|when|why|how|which|whose|"
    r"is|are|was|were|do|does|did|can|could|will|would|should|has|have|had)\b"
)
#: A thing to look up, said as an order.
_LOOKUP_VERB = re.compile(
    r"^(?:tell me about|tell me|explain|define|describe|compare|translate|convert|look up|google|find out|learn about|give me (?:the )?(?:definition|meaning|history|summary) of)\b"
)
#: Topics the web answers, with one more word naming the place or the thing.
_TOPIC = re.compile(
    r"\b(?:weather|forecast|news|score|scores|price|prices|stock|stocks|recipe|recipes|lyrics|translation|definition|meaning|population|capital|"
    r"exchange rate|timezone|time zone|directions|opening hours|release date|net worth|height|age|biography|history|symptoms|ingredients|calories)\b"
)
#: "capital of France", "price of bitcoin": a noun asked about by its owner.
_OF = re.compile(r"^(?:the )?[a-z' -]{3,30}? (?:of|in|for|at|near) [a-z0-9' -]{2,40}$")
#: Said to the app, not about the world: "are you stupid", "do you like me",
#: "what do you think", "ur mum".
_TO_THE_APP = re.compile(
    r"^(?:are|do|did|can|could|will|would|have|has|is) (?:you|u|ya|ur|your|yourself)\b"
    r"|\bwhat (?:do|did|are|were|would) (?:you|u)\b(?! (?:call|use|need|say|put|do (?:with|when|if)))"
    r"|\b(?:ur|your|yer|ya|yo|u r|youre|you're|shut up|stfu|mum|mom|mama|mother|dad|stupid|dumb|idiot|loser|sucks?|fat|ugly)\b"
)
#: The second word that makes "what's X" a small-talk opener, not a topic.
_SMALL = frozenset("up good new that this it next wrong going happening popping cracking poppin sup the a an about now then".split())
_SHORT_OPEN = re.compile(r"^(?:what's|whats|who's|whos|define) (?P<rest>[a-z0-9'-]{2,40})$")


def clean(message: str) -> str:
    """Lowercase words and nothing else: no emoji, no stray punctuation."""
    return " ".join(re.sub(r"[^\w' ]+", " ", (message or "").lower().replace("’", "'")).split())


def names_notes(message: str) -> bool:
    """The person says notes, a notebook or "my": their own record is the subject."""
    return bool(_NOTES.search(message or ""))


_NOTE_WORD = re.compile(r"\b(?:notes?|notebook|entr(?:y|ies)|journal|diary)\b", re.I)


def says_notes(message: str) -> bool:
    """The message says "note", "notes" or the notebook, not only "my"."""
    return bool(_NOTE_WORD.search(message or ""))


def names_notebook_things(message: str) -> bool:
    """The person asks about a thing the notebook holds (checklists, to-dos,
    reminders, tasks, what is due, lists)."""
    return bool(_NOTEBOOK_THINGS.search((message or "").replace("’", "'")))


def lookup(message: str) -> bool:
    """A question about the world, with the shape of one."""
    q = clean(message)
    words = q.split()
    if not words or _TO_THE_APP.search(q) or names_notes(message):
        return False
    short = _SHORT_OPEN.match(q)
    if short:
        return short.group("rest") not in _SMALL
    if len(words) == 2 and _LOOKUP_VERB.match(q):
        return True
    if len(words) < 3:
        return bool(_TOPIC.search(q)) and len(words) == 2
    return bool(_ASK_OPEN.match(q) or _LOOKUP_VERB.match(q) or _TOPIC.search(q) or _OF.match(q) or q.startswith("how to "))


def worthy(message: str) -> bool:
    """Whether the web may be searched for this message: it was asked for, or
    the message is a lookup."""
    return toolwords.asks_web(message) or lookup(message)


def about_the_person(message: str) -> bool:
    """The message is about the person's own record or is an instruction: it
    names a notebook thing, says "I" or "we", or opens with an app verb."""
    q = clean(message)
    return names_notebook_things(message) or bool(_FIRST_PERSON.search(q) or _INSTRUCTION.match(q))


def unplaced(message: str) -> bool:
    """A message no reader placed and that asks nothing of the web: banter,
    slang, a bare word, an emoji. With no note to answer it, it is asked about."""
    return bool((message or "").strip()) and not worthy(message) and not names_notes(message) and not about_the_person(message)


def bare_word(message: str) -> str:
    """The one word (or short name) a message is, else "": what to offer notes on."""
    q = clean(message)
    return q if q and len(q.split()) <= 2 and not _TO_THE_APP.search(q) and re.search(r"[^\W\d_]{3}", q) else ""


#: The question back. `{what}` is the message in the person's words.
CLARIFY: dict[str, tuple[str, ...]] = {
    "natural": (
        "Not sure what you mean by “{what}”. Do you want your notes on it, or the web?",
        "I did not catch what “{what}” was after. Your notes on it, or the web?",
        "“{what}” has me stumped. Should I look in your notes, or the web?",
    ),
    "professional": (
        "I could not tell what “{what}” was asking for. Would you like your notes on it, or the web?",
        "The request “{what}” was unclear. Should I search your notes or the web?",
    ),
}
CLARIFY_NOTES_ONLY: dict[str, tuple[str, ...]] = {
    "natural": (
        "Not sure what you mean by “{what}”. Do you want your notes on it, or something else?",
        "I did not catch what “{what}” was after. Should I look in your notes?",
    ),
    "professional": ("I could not tell what “{what}” was asking for. Would you like your notes on it?",),
}


def clarify(message: str, *, web_on: bool, voice: str = "natural", seed: str = "") -> str:
    """The short question for a message that nothing placed."""
    from tessellate.ai.composer_social import _pick, _voice

    pool = (CLARIFY if web_on else CLARIFY_NOTES_ONLY)[_voice(voice)]
    return _pick(pool, f"unplaced|{seed}|{message}").format(what=realise.cut_title(" ".join(message.split()), 40))


def chips(message: str, *, web_on: bool) -> list[str]:
    """Two chips: the notes on it, then the web (when it is on) or what the app can do."""
    what = realise.cut_title(" ".join(message.split()), 40)
    return [f"Search my notes for {what}", f"Search the web for {what}" if web_on else "What can you do?"]
