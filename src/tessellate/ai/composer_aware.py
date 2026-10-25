"""The composer knows where you are (the owner, 2026-10-25): "Make composer
aware of your screen, recent actions and more ... 'I can see you have been
talking about this or doing this, here's how you might do that'".

The client sends a small, local context with a Guide, Chat or Ask request: the
tab on screen, the document open, the labels of the last three things done
(the undo stack's, "Moved a note to the bin"), and the server adds the recent
chat topic from the turns it already holds. This module turns that into three
things, all the app's own wording around values it was handed:

- `opening`: a short line that says what the app can see, for a greeting;
- `closing`: a "pick up where you left off" next step after an answer;
- `model_context`: the same facts as a labelled block for a model, which
  leads while one runs (CHAT_PLAN decision 75).

**Privacy.** Nothing leaves the machine, and a note is named only when the
server can read it as a plain note: a private, binned or board note never
is (`note_title`), and an action label that quotes a name is dropped. Which
wording is chosen comes from the seed (the chat's, the day and the Ask again
count), so a replayed answer says the same and a new one does not.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

#: What the client calls each tab, in the words a person uses for it.
TAB_NAMES: dict[str, str] = {
    "dashboard": "Home",
    "notes": "Notes",
    "ask": "Ask",
    "chat": "Chat",
    "graph": "the Graph",
    "library": "the Library",
    "documents": "Documents",
    "timeline": "the Timeline",
    "reminders": "Reminders",
    "settings": "Settings",
}

#: A question to ask next for where you are: the how-to the Guide answers.
TAB_HOWTO: dict[str, str] = {
    "dashboard": "how do I arrange my home page",
    "notes": "how do I tag a note",
    "ask": "how do I ask about one note",
    "chat": "how do I attach a note to a chat",
    "graph": "how do I link two notes",
    "library": "how do I add a file",
    "documents": "how do I find text in a document",
    "timeline": "how do I jump to a date",
    "reminders": "how do I add a reminder",
}

MAX_ACTIONS = 3
MAX_LABEL = 60
_QUOTES = re.compile(r"[\"'“”‘’`]")


@dataclass(frozen=True)
class Awareness:
    tab: str = ""  # a name from TAB_NAMES, or ""
    open_title: str = ""  # a plain note's or a document's title, never a private one's
    actions: tuple[str, ...] = ()  # newest first, at most MAX_ACTIONS
    topic: str = ""  # what the last chat turns were about
    key: str = field(default="", compare=False)

    @property
    def known(self) -> bool:
        return bool(self.tab or self.open_title or self.actions or self.topic)


def clean_actions(labels: object) -> tuple[str, ...]:
    """The last three action labels, newest first. A label that carries a quote
    (it would be naming something) or is long is dropped, never trimmed."""
    if not isinstance(labels, (list, tuple)):
        return ()
    out: list[str] = []
    for label in reversed(labels):
        text = " ".join(str(label or "").split())
        if not text or len(text) > MAX_LABEL or _QUOTES.search(text):
            continue
        out.append(text)
        if len(out) == MAX_ACTIONS:
            break
    return tuple(out)


def tab_name(tab: object) -> str:
    return TAB_NAMES.get(str(tab or "").strip().lower(), "")


def build(*, tab: object = None, open_title: str = "", actions: object = None, topic: str = "") -> Awareness:
    """Awareness from what the request carried; every part is optional."""
    title = " ".join(str(open_title or "").split())[:60]
    return Awareness(tab=tab_name(tab), open_title=title, actions=clean_actions(actions), topic=" ".join(str(topic or "").split())[:40])


def _pick(options: tuple[str, ...], seed: str, salt: str) -> str:
    digest = hashlib.sha256(f"{seed}:{salt}".encode()).digest()
    return options[digest[0] % len(options)]


def _lower(action: str) -> str:
    return action[:1].lower() + action[1:]


def _where(aw: Awareness) -> str:
    if aw.open_title and aw.tab:
        return f"you're in {aw.tab} with “{aw.open_title}” open"
    if aw.open_title:
        return f"“{aw.open_title}” is open"
    if aw.tab:
        return f"you're in {aw.tab}"
    return ""


_OPENINGS = (
    "I can see {where}.",
    "Looks like {where}.",
    "From here, {where}.",
    "I can tell {where}.",
)
_ACTION_OPENINGS = (
    "I can see you {did} a moment ago.",
    "You {did} just now, I noticed.",
    "I saw you {did} a moment ago.",
)


def opening(aw: Awareness, seed: str) -> str:
    """One short line of what the app can see, or "" when it sees nothing."""
    where = _where(aw)
    if where:
        return _pick(_OPENINGS, seed, "open").format(where=where)
    if aw.actions:
        return _pick(_ACTION_OPENINGS, seed, "act").format(did=_lower(aw.actions[0]))
    return ""


_PICK_UP = (
    "Last you {did}. Want to pick up from there?",
    "You were part-way through something: you {did}. I can carry on from there with you.",
    "Since you {did} a moment ago, I can help with what comes next.",
    "Pick up where you left off? You {did} last.",
)
_PICK_UP_OPEN = (
    "Shall we carry on with “{title}”? I can summarise it or list what is left in it.",
    "You have “{title}” open. Ask me what is left on it, or what it links to.",
    "Want to pick up “{title}” where you left it? I can go through it with you.",
)
_TOPIC = (
    "You were talking about {topic}; ask me for the notes on it if you want to go on.",
    "We were on {topic}. I can pull the notes on it up again.",
)
_HOWTO = (
    "If it helps, ask me “{howto}” and I will show you.",
    "A good next question here: “{howto}”.",
    "To get going, ask me “{howto}”.",
)


def closing(aw: Awareness, seed: str, avoid: tuple[str, ...] | list[str] = ()) -> str:
    """The "here's how you might do that" step: what you were doing, then one
    thing to ask. "" when the app sees nothing to build on, or when every
    wording has been said in the last replies (`avoid`)."""
    if not aw.known:
        return ""
    said = "\n".join(avoid)
    tab_key = next((k for k, v in TAB_NAMES.items() if v == aw.tab), "")
    howto = TAB_HOWTO.get(tab_key, "")
    for step in range(4):
        lines: list[str] = []
        salted = f"{seed}:{step}"
        if aw.open_title:
            lines.append(_pick(_PICK_UP_OPEN, salted, "title").format(title=aw.open_title))
        elif aw.actions:
            lines.append(_pick(_PICK_UP, salted, "pick").format(did=_lower(aw.actions[0])))
        elif aw.topic:
            lines.append(_pick(_TOPIC, salted, "topic").format(topic=aw.topic))
        if howto and not aw.open_title:
            lines.append(_pick(_HOWTO, salted, "howto").format(howto=howto))
        line = " ".join(lines)
        if line and line not in said:
            return line
    return ""


def model_context(aw: Awareness) -> str:
    """The same facts as a labelled block for a model. Facts only: the model
    decides whether any of it matters to the question."""
    if not aw.known:
        return ""
    parts = []
    if aw.tab:
        parts.append(f"on {aw.tab}")
    if aw.open_title:
        parts.append(f"open: {aw.open_title}")
    if aw.actions:
        parts.append("last actions: " + "; ".join(aw.actions))
    if aw.topic:
        parts.append(f"recent chat topic: {aw.topic}")
    return "[On screen now, from this device only, may be stale: " + ", ".join(parts) + "]"
