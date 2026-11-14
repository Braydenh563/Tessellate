"""The name the person gave, and when to say it (composer audit 2, G7 and "Name use").

One helper for every surface that may use `display_name` with no model:

- `asks` / `answer`: "what's my name", "do you know my name", "what do you
  call me", "who am I".
- `read_set` / `plan` / `run_step`: "call me Sam" is an act like any other, so it
  waits for Confirm or a typed yes (`ai/consent.py`), has Undo, and the model
  reaches it the same way (`propose_act` reads the same sentence).
- `dashboard_append`: the server decides whether a composed greeting takes the
  name, so the page does not add it to every one.
- `greet`: the name on the first hello of a chat, once.

The name is local data written by a local composer, so it is used with the
profile switch off; that switch promises what a model reads (`librarian.py`).
It is never guessed from a note, never in a fact answer, a list, a card or an
error, and cut at `CUT` characters as the dashboard cuts it.
"""

from __future__ import annotations

import re
from datetime import date

#: The dashboard cuts a name here (`GREETING_NAME_MAX` in dashboard.js).
CUT = 40

#: What a name is not: the words "call me ..." usually continues with.
_NOT_A_NAME = frozenset(
    "back later tomorrow today tonight now soon again maybe sometime anytime asap please when if at on in after before "
    "about whenever anything something nothing someone it that this them him her us you up out over monday tuesday "
    "wednesday thursday friday saturday sunday morning evening afternoon noon midnight home mum mom dad".split()
)
_WORD = re.compile(r"^[^\W\d_][\w'’.-]{0,29}$")
_SET = re.compile(
    r"^(?:(?:please|hey|ok|okay|so|well)[ ,]+)*(?:you (?:can|may|could) |just |from now on )*"
    r"(?:(?P<call>call me|i go by|i'm called|i am called|i'm known as)|(?P<is>my name is|my name's|change my name to|set my name to|my name should be))"
    #: The name runs to the end; its trailing stops and spaces are cut in code, not by a lazy group
    #: before `\s*[.!]*$`, which retries every split of a long blank run (CodeQL, polynomial regex).
    r"\s+(?P<name>\S.*)$",
    re.IGNORECASE,
)
_ASK = re.compile(
    r"^(?:(?:hey|hi|ok|okay|so|please|tell me)[ ,]+)*"
    r"(?:what(?:'s| is| was)? my name|what do you call me|what am i called|what'?s? you call me"
    r"|(?:do|can) you (?:know|remember|tell me) (?:my name|what my name is|what i'?m called)"
    r"|do you know who i am|who am i|what should you call me|who do you think i am)"
    r"(?: again| now| then| please)?\s*[?.!]*$",
    re.IGNORECASE,
)


def clean(raw: object) -> str:
    """A name, not markup: the settings route's rule, then the greeting's cut."""
    plain = " ".join(re.sub(r"[<>\x00-\x1f\x7f​-‏‪-‮⁦-⁩]", " ", str(raw or "")).split())
    return plain if len(plain) <= CUT else plain[: CUT - 1].rstrip() + "…"


def name_of(config) -> str:  # noqa: ANN001
    return clean(config.get_preference("display_name", "")) if config is not None else ""


def asks(text: str) -> str | None:
    """"who" for "who am I", "name" for the other name questions, else None."""
    found = _ASK.match(" ".join(str(text or "").split()))
    if not found:
        return None
    return "who" if re.search(r"who (?:am i|do you think)", found.group(0), re.I) else "name"


def answer(name: str) -> str:
    """The reply to a name question; a chip offers Settings when none is saved."""
    if name:
        return f"You're {name}, going by your profile."
    return "I don't know yet. Tell me, or add it in Settings, Profile."


def _match_set(plain: str):  # noqa: ANN202
    """`_SET` on the text, or on the text with a slip in the verb read as "call" ("cal me Sam")."""
    found = _SET.match(plain)
    if found or not re.search(r"\bme\b", plain, re.I):
        return found
    from tessellate.ai import question_noise

    fixed = question_noise.guided(plain, lambda t: bool(_SET.match(t)), frozenset({"call"}), real_to=None)
    return _SET.match(fixed) if fixed else None


def read_set(text: str) -> dict | None:
    """{"intent": "set_name", "name"} for "call me Sam" / "my name is Sam"; a
    time, a pronoun or a verb after "call me" ("call me later") is not a name."""
    found = _match_set(" ".join(str(text or "").split()))
    if not found:
        return None
    words = found.group("name").rstrip(" .!").strip(" ,").split()
    if not 1 <= len(words) <= 3 or not all(_WORD.match(w) for w in words):
        return None
    if found.group("call") and (len(words) > 2 or any(w.lower().strip(".") in _NOT_A_NAME for w in words)):
        return None
    if found.group("is") and words[0].lower() in {"not", "the", "a", "an", "what", "who", "is", "to"}:
        return None
    name = clean(" ".join(w[:1].upper() + w[1:] if w.islower() else w for w in words))
    return {"intent": "set_name", "name": name} if name else None


def plan(parsed: dict, card, confirm) -> dict:  # noqa: ANN001
    """The line and card that wait for Confirm; nothing is saved before."""
    from tessellate.core import deps

    name = parsed["name"]
    if name == name_of(deps.get_config()):
        return {"line": f"I already call you {name}."}
    label = f"Call you {name} from now on"
    return {"line": confirm(label), "card": card(label, [{"name": "set_display_name", "arguments": {"name": name}}])}


def run_step(config, args: dict) -> dict:  # noqa: ANN001
    """Save the name; the result carries the step that puts the old one back."""
    name = clean(args.get("name"))
    before = name_of(config)
    config.set_preference("display_name", name)
    label = f"Set your name to {name}" if name else "Cleared your name"
    return {"label": label, "undo": {"tool": "set_display_name", "arguments": {"name": before}}}


#: A hello that can take ", Name" before its first full stop.
_HELLO = re.compile(r"^(Good (?:morning|afternoon|evening)|Morning|Evening|Hello|Hi|Hey)(?=[.,])")


def greet(text: str, name: str, history: list[dict] | None) -> str:
    """The name on the first hello of a chat only ("Good morning, Alex."); a
    second hello, or any chat that has begun, is left as it is."""
    if not name or any(turn.get("answer") for turn in history or []):
        return text
    return _HELLO.sub(lambda m: f"{m.group(1)}, {name}", text, count=1)


#: The last composed dashboard greeting that took the name: its day and whether it did.
_LAST: dict = {"day": None, "named": False}


def dashboard_append(name: str, mark: str, today: date, slot: str) -> bool:
    """Whether a composed greeting takes the name: always for the first of the
    day, then about one in three, never on a question (it reads as a challenge:
    "Work on your mind lately, Alex?") and never twice running."""
    if not name:
        return True  # nothing to append: the page adds no name it does not have
    if mark == "?":
        return False
    first = _LAST["day"] != today
    named = first or (not _LAST["named"] and sum(map(ord, f"{today}|{slot}")) % 3 == 0)
    _LAST.update(day=today, named=named)
    return named
