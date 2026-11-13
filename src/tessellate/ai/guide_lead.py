"""Which sentence leads the Guide's answer, and what is not the Guide's to
answer (composer audit 2, G5).

With no model the Guide answers from the app's own help text. Its pick was
the sentence sharing the most words with the question, which led "what is
Tidy" with the layout picker and "how do I scan a page" with a pinch to zoom.
The rules here run first and are few:

- "what is X" leads with the topic titled X, or the sentence whose subject is
  X; a topic that merely shares a word with X does not answer it;
- a few how-tos open with their topic's first sentence ("scan a page");
- "turn off X" leads with the sentence that names Off, not the steps that
  turn it on;
- yes or no questions about the app (needs a model, costs, Android) get Yes
  or No, in words taken from the help;
- a question about the person's own notes is handed to Chat with a chip.

Nothing here acts: a hand-over is a sentence and a chip, and the chip only
asks the question in Chat."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from tessellate.ai.review_words import kind as review_kind

#: The miss line says nothing about a model: the model is not why there is no help.
MISS = "I don't have help on that. Try a tab or feature name, or browse Settings, Help."
NOTEBOOK = "That is one for your notebook, not the help: Chat answers it from your notes."

_ARTICLES = frozenset({"a", "an", "the", "my", "your", "our", "this", "that"})
_ASK = re.compile(
    r"^\W*(?:what(?:'s| is| are| was)|what (?:does|do)|tell me about|explain)\s+(?P<x>[\w' -]{2,40}?)"
    r"(?:\s+(?:do|does|mean|show|work|for|is for|are for))?\W*$",
    re.I,
)
#: What a sentence's subject is followed by.
_VERBS = frozenset(
    "is are shows lists opens lays lets keeps makes sets takes holds draws gives starts needs reads files checks turns runs"
    " lives sits switches asks answers".split()
)
_WORDS = re.compile(r"[a-z0-9']+")
#: "what is tessellate" and friends are the app's overview, not a topic called that.
_ABOUT_APP = frozenset({"tessellate", "atlas", "memorymap", "app", "this", "it", "everything", "new", "up", "going on"})


@dataclass
class Led:
    """The topics in order and the sentence that leads; `steps` False keeps
    the steps off (they turn a thing on, the question turned it off)."""

    topics: list[dict]
    lead: str = ""
    steps: bool = True
    miss: bool = False
    extra: dict = field(default_factory=dict)


def own_topic(topics: list[dict], lead: str, sentences) -> dict:  # noqa: ANN001
    """The topic the lead sentence is in, not the best-ranked one: its second
    sentence is that topic's own (G14 g: the export answer's was about duplicates)."""
    return next((t for t in topics if lead and lead in sentences(t["body"])), topics[0])


def _stem(word: str) -> str:
    word = word.strip("'").lower()
    for tail in ("ies", "es", "s"):
        if len(word) > 3 and word.endswith(tail):
            return word[: -len(tail)] + ("y" if tail == "ies" else "")
    return word


def _stems(text: str) -> list[str]:
    return [_stem(w) for w in _WORDS.findall(text.lower()) if w not in _ARTICLES]


def _first_clause(sentence: str, limit: int = 40) -> str:
    """A long first sentence cut at its first `;` so the lead is a line."""
    if len(sentence.split()) <= limit or ";" not in sentence:
        return sentence
    head = sentence.split(";", 1)[0].rstrip(",: ")
    return head + "." if len(head.split()) >= 5 else sentence


def subject_of(question: str) -> str:
    """"Tidy" for "what is Tidy"; "" for a question that is not "what is X"."""
    found = _ASK.match(question or "")
    if not found:
        return ""
    words = [w for w in _WORDS.findall(found.group("x").lower()) if w not in {"a", "an", "the"}]
    if not words or words[0] in {"my", "your", "our", "i", "you", "we", "this", "that", "it", "there"}:
        return ""
    return " ".join(words)


def _sentences(topic: dict) -> list[str]:
    return help_sentences(str(topic.get("body") or ""))


def _titled(subject: str, topics: list[dict], title_of) -> dict | None:  # noqa: ANN001
    wanted = _stems(subject)
    return next((t for t in topics if _stems(title_of(t).split(":")[0]) == wanted), None)


def _subject_sentence(subject: str, topics: list[dict]) -> tuple[dict, str] | None:
    """The sentence in which `subject` is what is being said about: it opens
    the sentence (within three words) or starts a clause ("where On this day
    shows ...") and a verb follows it."""
    phrase = re.compile(r"\b" + r"\s+".join(re.escape(w) for w in subject.split()) + r"\b\s+(?P<verb>[a-z]+)", re.I)
    for topic in topics:
        for sentence in _sentences(topic):
            for found in phrase.finditer(sentence):
                if found.group("verb").lower() not in _VERBS:
                    continue
                before = sentence[: found.start()].split()
                if len(before) <= 3:
                    return topic, _first_clause(sentence)
                clause = sentence[found.start():].split(";", 1)[0].rstrip()
                return topic, clause[:1].upper() + clause[1:]
    return None


def _has_phrase(subject: str, topics: list[dict]) -> bool:
    """Whether the subject names the topic by its keywords: "what is quick
    capture" is answered by the topic that lists "quick capture"."""
    wanted = set(_stems(subject))
    for topic in topics:
        for key in topic.get("keywords", ()):
            if wanted and wanted <= set(_stems(str(key))):
                return True
    return False


_OPENINGS = (
    (re.compile(r"\bscan(?:ning)?\b", re.I), "ocr-workspace"),
    (re.compile(r"\b(?:make|create|add|start|write|use)\b.{0,20}\b(?:check ?lists?|to-?do lists?|task lists?)\b", re.I), "tasks"),
    (re.compile(r"\bnothing (?:happens|works|responds)\b|\b(?:doesn'?t|does not|won'?t) (?:work|respond)\b", re.I), "troubleshooting"),
)
_OFF = re.compile(r"\b(?:turn|switch|shut|get rid of|disable|hide|stop)\b.{0,10}\boff\b|\b(?:turn off|switch off|disable|hide|get rid of)\b", re.I)
_OFF_SENTENCE = re.compile(r"\bOff\b|\bturn(?:ed)? off\b")


def _fronted(topic: dict, topics: list[dict]) -> list[dict]:
    return [topic, *(t for t in topics if t is not topic)]


def _opening_lead(question: str, topics: list[dict], by_id: dict[str, dict]) -> Led | None:
    """A how-to that opens with its topic's first sentence, or a "turn off"
    that leads with the sentence naming Off (the steps turn it on)."""
    for pattern, topic_id in _OPENINGS:
        if pattern.search(question) and topic_id in by_id:
            first = _sentences(by_id[topic_id])
            return Led(_fronted(by_id[topic_id], topics), first[0] if first else "")
    if _OFF.search(question):
        for topic in topics:
            line = next((s for s in _sentences(topic) if _OFF_SENTENCE.search(s)), "")
            if line:
                return Led(_fronted(topic, topics), line, steps=False)
    return None


def _subject_lead(subject: str, topics: list[dict], by_id: dict[str, dict], title_of) -> Led | None:  # noqa: ANN001
    """"what is X": the topic titled X, else the sentence about X, else a
    miss when the ranked topics do not name X at all."""
    everything = list(by_id.values())
    topic = _titled(subject, everything, title_of)
    if topic is not None:
        first = _sentences(topic)
        return Led(_fronted(topic, topics), _first_clause(first[0]) if first else "")
    found = _subject_sentence(subject, everything)
    if found is not None:
        return Led(_fronted(found[0], topics), found[1])
    named = _has_phrase(subject, topics[:2]) or set(_stems(subject)) <= set(_stems(title_of(topics[0])))
    #: "the document views": every word is the top topic's own (title or body), so it is about it.
    named = named or set(_stems(subject)) <= set(_stems(title_of(topics[0]) + " " + str(topics[0].get("body") or "")))
    return None if named else Led(topics, miss=True)


def lead_for(question: str, tab: str | None, topics: list[dict], by_id: dict[str, dict], title_of) -> Led | None:  # noqa: ANN001
    """The lead the rules above choose for `question` over the matched
    `topics`, or None to leave the ranked pick alone."""
    from tessellate.ai import guide_intent

    if guide_intent.read(question) == guide_intent.PAGE:
        first = _sentences(topics[0])
        return Led(topics, _first_clause(first[0])) if first else None
    opened = _opening_lead(question, topics, by_id)
    if opened is not None:
        return opened
    subject = subject_of(question)
    return None if not subject or subject in _ABOUT_APP else _subject_lead(subject, topics, by_id, title_of)


# --- what is not the help's to answer --------------------------------------

_MINE = (
    re.compile(r"^\W*(?:when|what time) (?:is|are|was|were) (?:my|the|our) \w", re.I),
    re.compile(r"\bhow many (?:notes|reminders|tasks|documents|tags|words|boards|maps|spaces)\b.{0,12}\b(?:do )?(?:i|we) (?:have|got|wrote|made)\b", re.I),
    re.compile(r"^\W*(?:what|which) (?:did|have|do) (?:i|we) (?:write|wrote|make|made|do|done|add|save|plan)\b", re.I),
    re.compile(r"^\W*what(?:'s| is| are) (?:on )?my (?:notes?|reminders?|tasks?|to[- ]?do list|list|agenda|schedule|day|week|calendar)\b", re.I),
    re.compile(r"^\W*(?:show|list|give|see|open)\b.{0,8}\bmy (?:notes?|reminders?|tasks?|to[- ]?do list|agenda|schedule)\b", re.I),
    re.compile(r"^\W*what (?:tasks|reminders|notes|meetings|appointments) do (?:i|we) have\b", re.I),
    re.compile(r"^\W*do (?:i|we) have (?:any |a |an )?(?:reminders?|notes?|tasks?|appointments?|meetings?|deadlines?|exams?)\b", re.I),
)


def hands_over(question: str) -> dict | None:
    """A question about the person's own notes or reminders: one sentence and
    a chip that asks it in Chat. The chip only asks; nothing is done here."""
    text = " ".join((question or "").split())
    if not text:
        return None
    if review_kind(text) or any(rx.search(text) for rx in _MINE):
        #: The chip is the question as a button says it: a capital first (L-chat-35).
        return {"content": NOTEBOOK, "badges": [], "sources": [], "asks": [text[:1].upper() + text[1:]], "asks_to": "chat"}
    return None


_NEEDS_MODEL = re.compile(
    r"\b(?:do|does|will|would|must|should)\b.{0,15}\b(?:i|it|atlas|this|the app|tessellate)\b.{0,15}\b(?:need|require|have to have|want)s?\b.{0,10}"
    r"\b(?:a |an |the )?(?:model|ai|llm|ollama)\b|\b(?:need|require)s? (?:a |an )?(?:model|ai|llm)\b.{0,12}\??$|\bwork(?:s)? without (?:a |an )?(?:model|ai)\b",
    re.I,
)
_COST = re.compile(
    r"\bhow much\b.{0,25}\b(?:cost|is it|does it|to buy)\b|\b(?:is|does)\b.{0,12}\b(?:it|this|tessellate|the app)\b.{0,12}\b(?:free|cost|charge)\b"
    r"|\b(?:price|pricing|subscription|free of charge)\b|\bcosts?\b",
    re.I,
)
_SIZE = re.compile(r"\b(?:space|room|disk|storage|memory|ram|megabytes?|gigabytes?|mb|gb)\b", re.I)
_PLATFORM = re.compile(r"\b(?P<p>android|ios|iphone|ipad)\b", re.I)
_APP_FOR = re.compile(r"\b(?:app|apps|available|download|install|version)\b", re.I)


def yes_no(question: str) -> tuple[str, list[str]] | None:
    """The answer to a yes or no question about the app, and the topic ids it
    comes from; the words are the help text's own."""
    text = " ".join((question or "").split())
    if _NEEDS_MODEL.search(text):
        return "No. Everything except Chat, drafting and skills works without one, and Notes, Ask answers from your notes.", ["models", "troubleshooting"]
    #: "how much space does it use" asks about the disk, not the price (L-chat-38).
    if _COST.search(text) and not _SIZE.search(text):
        return (
            "There is nothing to buy in the app: Tessellate is AGPL-3.0 open source (Settings, Help, Credits). "
            "A hosted model you connect is billed by its own provider.",
            ["credits", "models"],
        )
    platform = _PLATFORM.search(text)
    if platform and _APP_FOR.search(text) and not re.search(r"\bhow do i\b", text, re.I):
        name = "Android" if platform.group("p").lower() == "android" else "iPhone or iPad"
        return (
            f"There is no separate {name} app. Open the notebook in your phone's browser over your own network "
            "(Settings, Account & security, Other devices); where the browser offers Install as an app, it gets its own icon.",
            ["phone", "install-app"],
        )
    return None


_PRONOUN = re.compile(r"\b(?:they|them|it|those|that|these|there|their|its)\b", re.I)


def follow_topics(question: str, history: list[dict] | None, topics_for) -> list[dict]:  # noqa: ANN001
    """The topics of the last question that named one, for a short follow-on
    that names nothing ("where do they show up")."""
    if not history or len(question.split()) > 9 or not _PRONOUN.search(question):
        return []
    for turn in reversed(history):
        if turn.get("role") == "user":
            found = topics_for(str(turn.get("content") or ""))
            if found:
                return found
    return []


#: A full stop that ends no sentence: "(e.g. Summarise)", "etc. and", "vs.".
_ABBREVIATION = re.compile(r"\b(?:e\.g|i\.e|etc|vs|approx|incl|cf)\.$", re.I)


def help_sentences(body: str) -> list[str]:
    """The sentences of a help topic of five words or more. A sentence ends
    at a stop before a capital, a quote or a bracket, or at the end: "0.5x",
    ".ics", "a category's ... menu" and "e.g. Summarise" end nothing (the
    Guide's gold: "Skills are one-click requests shown above the chat box
    (e." was a lead)."""
    out, start = [], 0
    for m in re.finditer(r"[.!?](?=\s+(?:/[a-z]|[\"“(\[*]?[A-Z0-9])|\s*$)", body):
        chunk = body[start:m.end()]
        if _ABBREVIATION.search(chunk) or chunk.endswith(".."):
            continue
        out.append(chunk.strip())
        start = m.end()
    #: Five words at least: "Notes keys and controls." is a topic's title.
    return [line for line in out if len(line.split()) >= 5]


def _help_sentences(body: str) -> list[str]:
    return help_sentences(body)


#: A topic that is about a switch, and the switch: its preference, its
#: default and its name. The Guide says which way it is set now ("how do I
#: turn on web search" when it is on is answered "Web search is on now").
_SWITCHES: dict[str, tuple[str, bool, str]] = {
    "websearch": ("web_search_enabled", False, "Web search"),
    "autonomous": ("autonomous_tasks_enabled", False, "Background AI"),
}


def state_line(topic_id: str, preference) -> str:  # noqa: ANN001
    """"Web search is off now.": the switch a topic is about, as it is set."""
    switch = _SWITCHES.get(topic_id)
    if switch is None:
        return ""
    key, default, name = switch
    return f"{name} is {'on' if preference(key, default) else 'off'} now."


def related_titles(topics: list[dict], shown: str, title_of) -> list[str]:  # noqa: ANN001
    """The other topics' titles, none the topic just given nor one already
    said in the answer (G5 h: "Related: Set a reminder" under that answer)."""
    first, said = title_of(topics[0]), shown.lower()
    return [t for t in (title_of(topic) for topic in topics[1:]) if t != first and t.lower() not in said]
