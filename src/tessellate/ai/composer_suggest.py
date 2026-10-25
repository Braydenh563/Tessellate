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


def _catalogue() -> list[tuple[Option, set[str], str]]:
    rows = []
    for intent, act in act_registry.ACTS.items():
        words = _tokens(f"{act.label} {act.verb} {_SYNONYMS.get(intent, '')}")
        rows.append((Option(intent, act.label, _ASK_FOR.get(intent, act.label.capitalize())), words, f"{act.label}. {act.help}"))
    return rows


def closest(question: str, embed=None, limit: int = 3) -> list[Option]:  # noqa: ANN001
    """The acts nearest `question`, best first. Shared words (synonyms
    included) always count; the embedder's cosine is added when `embed` works
    and silently left out when it does not."""
    asked = _tokens(question)
    rows = _catalogue()
    scores = [len(asked & words) / math.sqrt(max(len(words), 1)) for _, words, _ in rows]
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
    if _VAGUE.match(q):
        return "vague"
    m = _BARE.match(q)
    if m:
        kind = _VERB_KIND[m.group("verb").lower()]
        #: "make me a" and "add" alone are unfinished, not requests.
        return kind if (m.group("noun") or m.group("verb").lower() in ("open", "find", "search")) else ""
    return ""


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
_VAGUE_TEXT = (
    "I can do a few useful things without a model. What are you in the mood for? Pick one, or say what you have in mind.",
    "Cool how? Here are some things worth trying, or tell me what you are after.",
    "Happy to. Do you want to look something up, tidy something, or see what is coming up? A few ideas below.",
    "Can you say a little more? In the meantime, here are some things I do well.",
)


def reply(question: str, titles: list[str], *, seed: str = "") -> dict:
    """The clarifying question and its choices for an open-ended request:
    `{"text", "asks"}`. `titles` are the newest notes' names, newest first."""
    kind = open_ended(question)
    shown = [t for t in titles if t][:4]
    if kind in _WHICH:
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
    if kind in _DETAIL:
        return {"text": _DETAIL[kind], "asks": []}
    ideas = list(_TRY) + list(composer_replies.CALL_ASKS)
    ideas = list(dict.fromkeys(ideas))
    start = int(hashlib.sha1(f"ideas|{seed}|{question.lower()}".encode()).hexdigest(), 16) % len(ideas)
    asks = [ideas[(start + i * 2) % len(ideas)] for i in range(3)]
    if shown:
        asks.append(f"Open the note about {shown[int(hashlib.sha1(seed.encode()).hexdigest(), 16) % len(shown)]}")
    return {"text": _pick(list(_VAGUE_TEXT), question, seed), "asks": list(dict.fromkeys(asks))}


def unknown_action(question: str, titles: list[str], *, embed=None, seed: str = "") -> dict | None:  # noqa: ANN001
    """For a request in the imperative that no act understood: the closest
    acts as choices, never a notes search for its words. None for a question."""
    q = " ".join((question or "").split())
    if not q or _ASKING.match(q) or not _IMPERATIVE.match(q):
        return None
    options = closest(q, embed=embed)
    if not options:
        found = reply("do smth cool", titles, seed=seed)
        return {"text": "I am not sure how to do that one. " + found["text"], "asks": found["asks"]}
    labels = [o.label for o in options]
    names = labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " or " + labels[-1]
    return {"text": f"I am not sure I can do that exactly. The closest I can do is to {names}. Want one of those?", "asks": [o.ask for o in options]}
