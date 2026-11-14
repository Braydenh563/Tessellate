"""What to say when a request is open-ended or is an action the app does not know.

The 22-10 bug doc: "do smth cool" got "I couldn't find anything on cool" (a
notes search), and "open a note" searched the notes for the word "a". With no
model the app asks what was meant and offers choices that run when pressed.

- `open_ended`: "do smth cool", "surprise me" (vague) and a bare action with no
  object ("open a note") are told apart from a question about the notes.
- `reply`: the clarifying question and the choices, as text and `asks` (the
  chips under an answer; each one is a complete request that works as typed).
- `closest` / `unknown_action`: an imperative nothing understood ("get rid of
  old stuff") is matched to the acts the registry holds, by shared words
  (with synonyms) and, when the embedder runs, by cosine on their labels. With
  no embedder it is the words alone: the same ranking minus one term.

Every sentence here is the app's own wording about what it can do; nothing is
said about the notes except their names, which are the notes' own.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from dataclasses import dataclass

from tessellate.ai import act_registry, composer_replies

log = logging.getLogger(__name__)

_FILLER = r"(?:please |pls |can you |could you |would you |go ahead and )*"
_VAGUE = re.compile(
    rf"^{_FILLER}(?:"
    r"(?:do|show|give|tell|make|find|try|play|pick|get) (?:me )?(?:smth|something|somethin|sumthing|anything|stuff|a thing|one thing)(?: (?:cool|fun|nice|interesting|useful|good|awesome|neat|special|different|random|amazing|impressive))?(?: for me| now| please)?"
    r"|(?:surprise|impress|amaze|entertain) me"
    r"|(?:i'?m|im|i am) (?:so )?(?:bored|stuck|lost|unsure)"
    r"|(?:what|anything) (?:else )?(?:cool|fun|interesting)(?: can you do)?"
    r"|show off|do your thing|wow me"
    r")[?.! ]*$",
    re.I,
)
_VERB_KIND = {
    "open": "open", "find": "find", "search": "find", "show": "find", "delete": "delete", "remove": "delete", "pin": "pin",
    "unpin": "unpin", "summarise": "summarise", "summarize": "summarise", "tag": "tag", "rename": "rename", "link": "link",
    "remind": "reminder", "move": "move", "create": "new", "make": "new", "add": "new", "write": "new", "start": "new", "new": "new",
}
_BARE = re.compile(
    rf"^{_FILLER}(?P<verb>{'|'.join(_VERB_KIND)})(?: me)?(?: (?:a|an|any|some|one|the|my))?(?: (?P<noun>note|notes|reminder|reminders|thing|file|one))?[?.! ]*$",
    re.I,
)
_IMPERATIVE = re.compile(
    rf"^{_FILLER}(?:get|make|give|put|set|play|read|write|send|turn|run|clean|sort|organi[sz]e|tidy|fix|do|show|help me|let me|take|bring|throw|stick|get rid of|use|try|go|build|draw|plan|schedule|book|email|call|print|share|export|import|copy|merge|split|archive|clear|reset)\b",
    re.I,
)
#: "Give me the short version" with no answer before it to shorten.
_FORM = re.compile(
    rf"^{_FILLER}(?:give|show|tell|get) me (?:it |that )?(?:in )?(?:the |a )?(?:short|long|brief|quick|full|detailed|simple|plain|shorter|longer|simpler)(?: version| answer| summary| form| way| one)?[?.! ]*$", re.I
)
_NO_FORM = (
    "There is no answer yet to give in a shorter form. Ask me something first, then say “shorter” and I will cut it down.",
    "Nothing to shorten so far. Ask a question about your notes, and I can give you the short version of the answer.",
)
_ASKING = re.compile(r"^(?:what|when|where|who|whom|whose|which|why|how|is|are|was|were|do i|did i|does|have i|has|can i)\b", re.I)

#: Words each act is also said with, so "get rid of" finds delete without the
#: registry's label carrying every synonym.
_SYNONYMS: dict[str, str] = {
    "reminder": "remind reminder alarm nudge alert notify remember later tomorrow tonight",
    "tag": "tag label categorise categorize hashtag",
    "untag": "untag unlabel strip",
    "move": "move file put category folder relocate sort",
    "new_note": "write jot capture save create new note idea",
    "meeting": "meeting minutes record agenda call",
    "pin": "pin stick top favourite favorite keep star",
    "unpin": "unpin unstick unstar",
    "link": "link connect relate join",
    "unlink": "unlink disconnect separate",
    "rename": "rename retitle title name call",
    "append": "add append put extra line",
    "delete": "delete remove trash bin erase discard drop rid clear",
    "find": "find search look locate where lookup",
    "open": "open show go view read display",
    "navigate": "settings graph timeline go page screen open",
    "summarise": "summarise summarize recap gist overview tldr digest",
}

#: Complete requests, one per act, that work as typed (a chip runs them).
_ASK_FOR = {
    "reminder": "Set a reminder", "tag": "Tag a note", "untag": "Take a tag off", "move": "Move a note", "new_note": "Make a new note",
    "meeting": "Start a meeting", "pin": "Pin a note", "unpin": "Unpin a note", "link": "Link two notes", "unlink": "Unlink two notes",
    "rename": "Rename a note", "append": "Add a line to a note", "delete": "Delete a note", "find": "Find a note", "open": "Open a note",
    "navigate": "Open settings", "summarise": "Summarise my newest notes",
}
#: Things worth trying, for a request with no direction. Runs with no model.
_TRY = (
    "What did I write this week?", "Show my open tasks", "What's on today?", "Which notes are not linked to anything?",
    "Summarise my newest notes", "What can you do?", "Show my reminders", "What have I saved recently?",
)


@dataclass(frozen=True)
class Option:
    intent: str
    label: str
    ask: str
    score: float = 0.0


def _stem(word: str) -> str:
    for tail in ("ing", "ed", "es", "s"):
        if len(word) > len(tail) + 2 and word.endswith(tail):
            return word[: -len(tail)]
    return word


def _tokens(text: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-z]+", (text or "").lower()) if len(w) > 2 and w not in _STOP}


_STOP = frozenset("the and for with from that this you can could would please about into onto have has not are was were your note notes".split())


#: Acts said as a whole sentence about a kind of thing (a category, a tag, a note's text, a list, a skill): offered
#: by name they would outscore "delete a note" on a bare "delete" (`parity_acts`).
_SENTENCE_ONLY = frozenset({"delete_category", "merge_categories", "delete_tag", "edit_text", "to_reminders", "run_skill"})


def _catalogue() -> list[tuple[Option, set[str], str]]:
    rows = []
    for intent, act in act_registry.ACTS.items():
        if intent in _SENTENCE_ONLY:
            continue
        words = _tokens(f"{act.label} {act.verb} {_SYNONYMS.get(intent, '')}")
        rows.append((Option(intent, act.label, _ASK_FOR.get(intent, act.label.capitalize())), words, f"{act.label}. {act.help}"))
    return rows


def closest(question: str, embed=None, limit: int = 3) -> list[Option]:  # noqa: ANN001
    """The acts nearest `question`, best first. Shared words (synonyms
    included) always count; the embedder's cosine is added when `embed` works
    and silently left out when it does not."""
    asked = _tokens(question)
    rows = _catalogue()
    #: A narrower act ("delete_document") shares its verb with the broad one
    #: ("delete"); without its own noun asked it is not the closer act, however
    #: short its word list ("delete the boiler note" is a note's delete).
    broad = {act.intent: words for act, words, _ in rows}
    scores = [
        0.0 if (parent := broad.get(act.intent.split("_")[0])) is not None and act.intent != act.intent.split("_")[0] and not (asked & words) - parent
        else len(asked & words) / math.sqrt(max(len(words), 1))
        for act, words, _ in rows
    ]
    if embed is not None:
        try:
            vectors = embed([question] + [text for _, _, text in rows])
            query, rest = vectors[0], vectors[1:]
            for i, vec in enumerate(rest):
                scores[i] += max(0.0, _cosine(query, vec))
        except Exception:  # noqa: BLE001  # no backend is a state: words alone
            log.debug("closest: no embedder, scoring by words alone", exc_info=True)
    ranked = sorted(zip(scores, range(len(rows))), key=lambda p: (-p[0], p[1]))
    return [Option(rows[i][0].intent, rows[i][0].label, rows[i][0].ask, round(s, 3)) for s, i in ranked[:limit] if s > 0]


def _cosine(a, b) -> float:  # noqa: ANN001
    if a is None or b is None:
        return 0.0
    dot = sum(float(x) * float(y) for x, y in zip(a, b))
    na = math.sqrt(sum(float(x) ** 2 for x in a))
    nb = math.sqrt(sum(float(y) ** 2 for y in b))
    return dot / (na * nb) if na and nb else 0.0


def open_ended(question: str) -> str:
    """"vague" for a request with no direction, the act's name ("open",
    "find", "delete", "pin", ...) for a bare action with no object, else ""."""
    q = " ".join((question or "").split())
    #: "can you do anything fun" asks what Atlas can do; it is answered, not
    #: met with "Cool how?" (INBOX 1561).
    from tessellate.ai import capability

    if _VAGUE.match(q):
        return "" if capability.asks(q) else "vague"
    m = _BARE.match(q)
    return _bare_kind(m) if m else ""


def _bare_kind(m: re.Match) -> str:
    """The act a bare verb (with or without its noun) starts, or "" when the
    words are a request already (`open_ended`)."""
    verb, noun = m.group("verb").lower(), (m.group("noun") or "").lower()
    kind = _VERB_KIND[verb]
    #: "show my reminders" names its object: the Reminders, read or
    #: opened, never "What should I look for?" (audit 1028 E28).
    if kind in ("find", "open") and noun.startswith("reminder"):
        return ""
    #: "make me a reminder" starts a reminder, not a note (INBOX 1668).
    if kind == "new" and noun.startswith("reminder"):
        return "reminder"
    #: "new notes" is the newest notes, not the start of making one
    #: (INBOX 1532); only the singular "new note" is unfinished.
    if verb == "new" and noun == "notes":
        return ""
    #: "make me a" and "add" alone are unfinished, not requests.
    return kind if (noun or verb in ("open", "find", "search")) else ""


# --- the answer to "Which note?" (INBOX 1570) -----------------------------------------------
#
# "Pin a note" -> "Which note do you want pinned?" -> "erm, the interesting bean one": the
# reply is that question's answer, read before anything routes it.

#: Said while thinking or softening, never part of a note's name.
#: One filler word and its trailing commas and stops; `_unfilled` steps them off the front
#: one at a time. A repeated group with a trailing `$` was polynomial on runs of blanks
#: (CodeQL 1997), so the front and the tail are walked, not matched whole.
_SLOT_FILLER = re.compile(r"(?:erm+|er+|um+|uh+|hmm+|like|so|well|ok|okay|yeah|yes|yep|oh|ah|just|maybe|i guess|i mean|please|pls)\b[ ,.]*", re.I)
_SLOT_TAIL_WORDS = ("thank you", "please", "thanks", "pls", "then")


def _unfilled(said: str) -> str:
    at = 0
    while (found := _SLOT_FILLER.match(said, at)) and found.end() > at:
        at = found.end()
    said = said[at:].rstrip(" .!")
    while True:
        low = said.lower()
        word = next((w for w in _SLOT_TAIL_WORDS if low.endswith(w) and len(said) > len(w) and said[-len(w) - 1] in " ,."), "")
        if not word:
            return said
        said = said[: -len(word)].rstrip(" ,.")
#: "the one about X", "the one called X": the note is named after "one".
_ONE_ABOUT = re.compile(r"^(?:(?:the|that|this|my) )?one (?:about|on|for|called|named|titled|with|that mentions?|mentioning) (?:the |my )?(?P<name>.+)$", re.I)
#: "the X one", "that X note", "my X one": the note is the words between.
_THE_ONE = re.compile(r"^(?:(?:the|that|this|my) )?(?P<name>.+?)(?: one| note| entry)?$", re.I)
_SLOT_KINDS = ("open", "find", "delete", "pin", "unpin", "summarise")
_BLANK_WORDS = frozenset("one ones note notes it this that them these those thing stuff".split())


def reference(text: str) -> str:
    """The note a reply points at ("erm, the interesting bean one" is "interesting
    bean"), or "" when it names nothing: only filler, "it", "that one"."""
    said = _unfilled(" ".join((text or "").split())).strip(" \"'“”")
    found = _ONE_ABOUT.match(said)
    name = found.group("name") if found else (_THE_ONE.match(said).group("name") if _THE_ONE.match(said) else said)
    name = name.strip(" \"'“”,.")
    words = re.findall(r"[\w'’-]+", name.lower())
    return "" if not words or all(w in _BLANK_WORDS for w in words) else name


def pending_kind(history: list[dict]) -> str:
    """The act the last answer was asking "which note?" for, else "": the last turn's
    question was an act with no note, and its answer is the clarifying one (`reply`)."""
    if not history:
        return ""
    last = history[-1]
    kind = open_ended(str(last.get("question") or ""))
    answer = " ".join(str(last.get("answer") or "").split())
    return kind if kind in _SLOT_KINDS and answer in {" ".join(t.split()) for t in _WHICH[kind]} else ""


def fill_slot(question: str, history: list[dict], notes: list[tuple[int, str]]) -> str | None:
    """The act `question` completes, said whole ("Pin note 12"), when it answers the
    note Atlas just asked for: the reply fills the act's slot before any routing.
    `notes` are `(id, title)` pairs. None when the reply is its own request."""
    kind = pending_kind(history)
    if not kind or open_ended(question) or "?" in question:
        return None
    name = reference(question)
    if not name or len(name.split()) > 8:
        return None
    #: A reply that is itself a command ("delete the boiler note") is routed as one.
    if re.match(rf"^(?:{'|'.join(_VERB_KIND)})\b", name, re.I) and len(name.split()) > 2:
        return None
    key = " ".join(name.lower().split())
    exact = [i for i, title in notes if " ".join(title.lower().split()) == key]
    verb = _VERB_FOR[kind]
    #: "Summarise note 12" reads as a topic, so it names the title instead.
    if len(exact) == 1 and kind != "summarise":
        return f"{verb} note {exact[0]}"
    if len(exact) == 1:
        return f"{verb} the note about {next(t for i, t in notes if i == exact[0])}"
    return f"{verb} the note about {name}"


def _pick(options: list, question: str, seed: str):  # noqa: ANN001, ANN202
    digest = hashlib.sha1(f"{question.strip().lower()}|{seed}".encode()).digest()
    return options[digest[0] % len(options)]


_WHICH = {
    "open": ("Which note should I open? Your newest are below, or tell me what it is about.",
             "Happy to open one. Which note do you mean? Pick a recent one, or name it."),
    "find": ("What should I look for? Name a word or a topic, or pick a recent note.",
             "Which note are you after? Give me a word from it, or pick one below."),
    "delete": ("Which note should I delete? It goes to the bin, so Undo brings it back.",
               "Which note do you want gone? It waits for your Confirm, and the bin keeps it."),
    "pin": ("Which note should I pin to the top?", "Which note do you want pinned?"),
    "unpin": ("Which note should I unpin?", "Which pinned note do you want to let go?"),
    "summarise": ("Which note should I summarise? Or say a topic, like “my gym notes”.",
                  "What should I sum up? Pick a note, or name a topic."),
}
_VERB_FOR = {"open": "Open", "find": "Find", "delete": "Delete", "pin": "Pin", "unpin": "Unpin", "summarise": "Summarise"}
_DETAIL = {
    "tag": "Which note, and which tags? For example: “tag the knife note with kitchen”.",
    "rename": "Which note, and what should it be called? For example: “rename the gym note to Strength plan”.",
    "move": "Which note, and which category? For example: “move the sourdough note to Cooking”.",
    "link": "Which two notes? For example: “link the gym note to the running note”.",
    "reminder": "What should I remind you about, and when? For example: “remind me to call mum on Friday at 9”.",
    "new": "What should the note say? Start with “note:” and the words, for example “note: buy milk and eggs”.",
}
#: A bare "new note" offers both readings: making one, or the newest ones (INBOX 1532).
_DETAIL_ASKS = {"new": ("Show my newest notes",)}
_FEELS = re.compile(r"\b(?:bored|stuck|lost|unsure)\b", re.I)
_FEELING_TEXT = (
    "Bored, then. Here are a few things worth trying, or tell me what you are after.",
    "Let us fix that. A few ideas below, or say what you feel like.",
    "Slow day? Here are some things to try, or tell me what you are in the mood for.",
    "I can help with that. Pick something below, or say what you have in mind.",
)
_VAGUE_TEXT = (
    "I can do a few useful things without a model. What are you in the mood for? Pick one, or say what you have in mind.",
    "Cool how? Here are some things worth trying, or tell me what you are after.",
    "Happy to. Do you want to look something up, tidy something, or see what is coming up? A few ideas below.",
    "Can you say a little more? In the meantime, here are some things I do well.",
)


def _which_reply(kind: str, question: str, shown: list[str], seed: str) -> dict:
    """The question for a request that names its verb but not which note ("open it")."""
    if not shown and kind in ("open", "delete", "pin", "unpin", "summarise"):
        return {"text": "You have no notes yet, so there is nothing to " + kind + ". Make one with “note:” and your words, or ask me what I can do.",
                "asks": ["Make a new note", "What can you do?"]}
    text = _pick(list(_WHICH[kind]), question, seed)
    if kind == "find":
        return {"text": text, "asks": [f"Open the note about {t}" for t in shown] or ["What have I saved recently?"]}
    verb = _VERB_FOR[kind]
    if kind == "summarise":
        return {"text": text, "asks": ["Summarise my newest notes"] + [f"Summarise the note about {t}" for t in shown[:3]]}
    return {"text": text, "asks": [f"{verb} the note about {t}" for t in shown]}


def reply(question: str, titles: list[str], *, seed: str = "") -> dict:
    """The clarifying question and its choices for an open-ended request:
    `{"text", "asks"}`. `titles` are the newest notes' names, newest first."""
    kind = open_ended(question)
    shown = [t for t in titles if t][:4]
    if kind in _WHICH:
        return _which_reply(kind, question, shown, seed)
    if kind in _DETAIL:
        #: A bare "new note" offers both readings: making one, or the newest ones.
        return {"text": _DETAIL[kind], "asks": list(_DETAIL_ASKS.get(kind, ()))}
    ideas = list(_TRY) + list(composer_replies.CALL_ASKS)
    ideas = list(dict.fromkeys(ideas))
    start = int(hashlib.sha1(f"ideas|{seed}|{question.lower()}".encode()).hexdigest(), 16) % len(ideas)
    asks = [ideas[(start + i * 2) % len(ideas)] for i in range(3)]
    if shown:
        asks.append(f"Open the note about {shown[int(hashlib.sha1(seed.encode()).hexdigest(), 16) % len(shown)]}")
    #: A feeling is answered as one first ("I'm bored" is not "Cool how?", INBOX 1749).
    feeling = _FEELING_TEXT if _FEELS.search(question or "") else _VAGUE_TEXT
    return {"text": _pick(list(feeling), question, seed), "asks": list(dict.fromkeys(asks))}


#: The doing words of a request, which every help sentence shares; the
#: thing asked for has to be in the help line itself.
_ASK_VERBS = frozenset("set start make run open do give put add create begin use".split())


def _app_tool(request: str) -> str | None:
    """A request for one of the app's own tools that chat cannot run ("set
    a timer"): how to run it, from the Guide's topic (INBOX 1357, class B,
    where it got "The closest I can do is to set a reminder"). None unless
    the thing asked for is named in the help line."""
    from tessellate.ai import composer, help_chat

    found = composer.help_line(request, help_chat.topics_for(request))
    if found is None:
        return None
    things = [w for w in re.findall(r"[a-z]{4,}", request.lower()) if w not in _ASK_VERBS]
    if not things or not all(re.search(rf"\b{w}", found[0], re.I) for w in things):
        return None
    return f"I cannot run that from chat, but you can: {found[0]}"


#: "make it simpler", "shorten that", "rephrase this": a rewrite of the words just said, which only a model
#: can do (L45); said as that, never offered as a new note or a category.
_REWRITE = re.compile(
    r"^(?:please |can you |could you )*(?:(?:make|keep)\s+(?:it|this|that|the (?:note|text|draft|answer|reply))\s+(?:a (?:bit|little) |much |way )?"
    r"(?:simpler|shorter|longer|clearer|plainer|easier|friendlier|funnier|more \w+|less \w+|formal|casual|better)"
    r"|(?:simplify|shorten|lengthen|rephrase|reword|rewrite|paraphrase|polish|improve)\s+(?:it|this|that)\b)",
    re.I,
)
_REWRITE_NEEDS_MODEL = "Rewording needs a model. Connect one in Settings, then ask again. Your words are untouched."


def unknown_action(question: str, titles: list[str], *, embed=None, seed: str = "") -> dict | None:  # noqa: ANN001
    """For a request in the imperative that no act understood: the closest
    acts as choices, never a notes search for its words. None for a question."""
    q = " ".join((question or "").split())
    if q and _REWRITE.match(q) and not _ASKING.match(q):
        return {"text": _REWRITE_NEEDS_MODEL, "asks": []}
    if not q or _ASKING.match(q) or not _IMPERATIVE.match(q):
        return None
    if _FORM.match(q):
        return {"text": _pick(list(_NO_FORM), q, seed), "asks": []}
    tool = _app_tool(q)
    if tool:
        return {"text": tool, "asks": []}
    options = closest(q, embed=embed)
    if not options:
        found = reply("do smth cool", titles, seed=seed)
        return {"text": "I am not sure how to do that one. " + found["text"], "asks": found["asks"]}
    labels = [o.label for o in options]
    names = labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " or " + labels[-1]
    return {"text": f"I am not sure I can do that exactly. The closest I can do is to {names}. Want one of those?", "asks": [o.ask for o in options]}
