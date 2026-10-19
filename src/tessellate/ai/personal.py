"""Personal and random questions, answered with no model.

The owner, 2026-10-11: "Can the composer answer personal questions or any
other random questions??". Three kinds:

- **About the person**, from what their notes say of them in the first
  person: where they live, their work, birthday and age, favourites, the
  people and pets they name ("my sister Jess"), what they are learning, and
  all of it at once for "what do you know about me". Each answer is the
  fact said back with the day of its note and one source mark; a fact the
  notes do not hold is said plainly, with what they do hold beside it.
- **About the assistant** ("do you have feelings", "who made you", "what's
  your favourite colour"): a short, true line in its own voice.
- **General knowledge** ("what's the capital of France") with nothing in the
  notes and no web search: said honestly, never invented.

Every sentence is a note's own fact or the app's joining words (CHAT_PLAN
decision 33). The gold is `fixtures/composer/personal_1011.json`.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime

from tessellate.ai import realise

_REL = (
    r"sister|brother|mum|mom|mother|dad|father|partner|wife|husband|boyfriend|girlfriend|son|daughter|"
    r"best friend|friend|boss|flatmate|roommate|housemate|cousin|aunt|uncle|nan|nana|grandma|grandpa|"
    r"dog|cat|puppy|kitten|pet|bird|rabbit|fish"
)
_PETS = frozenset("dog cat puppy kitten pet bird rabbit fish".split())
_STOP = r"(?=\s+(?:and|but|so|because)\b|[,.;!?]|$)"


@dataclass
class Fact:
    """One thing a note says of the person: the line said back, the note,
    the sentence it came from."""

    key: str
    said: str
    value: str
    note: dict
    source: str


#: What a note says of its writer, each as (key, pattern, how it is said).
_READERS: tuple[tuple[str, re.Pattern, Callable[[re.Match], tuple[str, str]]], ...] = (
    ("live", re.compile(r"\bI (?:live|am living|'m living|moved) (?:in|to) ([A-Z][\w'-]*(?:,? [A-Z][\w'-]*)*)"),
     lambda m: (f"you live in {m.group(1)}", m.group(1))),
    ("work", re.compile(r"\bI work ((?:part[- ]time |full[- ]time |casually )?(?:as|at|for|in) [^,.;!?]+?)" + _STOP, re.I),
     lambda m: (f"you work {m.group(1)}", m.group(1))),
    ("work", re.compile(r"\bmy job is ([^,.;!?]+?)" + _STOP, re.I), lambda m: (f"your job is {m.group(1)}", m.group(1))),
    ("birthday", re.compile(r"\bmy (?:birthday|bday) is (?:on )?([^,.;!?]+?)" + _STOP, re.I),
     lambda m: (f"your birthday is {m.group(1)}", m.group(1))),
    ("born", re.compile(r"\bI was born (?:on |in )?([^,.;!?]+?)" + _STOP, re.I), lambda m: (f"you were born {m.group(1)}", m.group(1))),
    ("favourite", re.compile(r"\b(?:my )?fav(?:ou?rite)? ([a-z]+(?: [a-z]+)?) (?:is|are) ([^,.;!?]+?)" + _STOP, re.I),
     lambda m: (f"your favourite {m.group(1).lower()} is {m.group(2)}", f"{m.group(1).lower()}={m.group(2)}")),
    ("person", re.compile(r"\b(?i:my) (" + _REL + r")(?:,| is called| called| named)? ([A-Z][a-z]+)\b"),
     lambda m: (f"your {m.group(1)} is {m.group(2)}", f"{m.group(1)}={m.group(2)}")),
    ("person", re.compile(r"\b([A-Z][a-z]+),? my (" + _REL + r")\b"),
     lambda m: (f"your {m.group(2)} is {m.group(1)}", f"{m.group(2)}={m.group(1)}")),
    ("learning", re.compile(r"\b(?:I'm|I am|started|been|now|currently) learning ([A-Za-z]+(?: [a-z]+)?)(?= on| at| with|" + _STOP[3:], re.I),
     lambda m: (f"you're learning {m.group(1)}", m.group(1))),
)


def notes_of(session) -> list[dict]:  # noqa: ANN001  # a SQLAlchemy session
    """The newest notes, as the composer reads them, for what they say of
    the person ("I live in Perth"): a fact is in whichever note it is in."""
    from tessellate.entry import manager

    return [
        {"id": e.id, "content": e.content or "", "created_at": e.created_at, "category": "", "tags": []}
        for e in manager.list_entries(session, limit=400)
    ]


def birthday(notes: Iterable[dict], now: datetime) -> str | None:
    """The birthday the notes give ("my birthday is 3 December"), as the ISO
    day `reading` takes for "on my birthday" (OPEN-ledger row 459); a month
    or a year alone is no day, so None."""
    from tessellate.ai import recognise

    for fact in facts(notes):
        if fact.key in ("birthday", "born") and re.search(r"\b\d{1,2}(?:st|nd|rd|th)?\b", fact.value):
            day = recognise.resolve(fact.value, now)
            if day is not None:
                return f"2000-{day.month:02d}-{day.day:02d}"
    return None


def facts(notes: Iterable[dict]) -> list[Fact]:
    """Every first-person fact the notes hold, newest note first, one per
    key and value."""
    out: list[Fact] = []
    seen: set[tuple[str, str]] = set()
    for note in notes:
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", str(note.get("content") or "")):
            out.extend(_read(sentence.strip(), note, seen))
    return out


def _read(sentence: str, note: dict, seen: set) -> list[Fact]:
    found = []
    for key, pattern, say in _READERS:
        for m in pattern.finditer(sentence):
            said, value = say(m)
            if (key, value.lower()) in seen or (key == "person" and m.group(0)[:1].isupper() and m.group(1) in _NOT_NAMES):
                continue
            seen.add((key, value.lower()))
            found.append(Fact(key, said.strip(), value.strip(), note, sentence))
    return found


#: Words that open a sentence and are not a person ("Today, my sister").
_NOT_NAMES = frozenset("Then And But So When Today Yesterday Tomorrow Also Now Visited Called Texted Met".split())

# --- what is asked -----------------------------------------------------------

_ASKS: tuple[tuple[str, re.Pattern], ...] = (
    ("live", re.compile(r"^(?:where do i live|where(?:'s| is) (?:my )?home|what (?:city|town|country) do i live in|where am i from)\b")),
    ("work", re.compile(r"^(?:what do i do(?: for (?:work|a living|a job|money))?|where do i work|what(?:'s| is) my (?:job|work)|what is my occupation)\s*$")),
    ("birthday", re.compile(r"^(?:when(?:'s| is) my (?:birthday|bday)|when was i born|what(?:'s| is) my (?:birthday|birth date|date of birth))\b")),
    ("age", re.compile(r"^(?:how old am i|what(?:'s| is) my age|how old will i be)\b")),
    ("favourite", re.compile(r"^(?:what(?:'s| is| are) my|do i have a) fav(?:ou?rite)? ([a-z]+(?: [a-z]+)?)\s*$")),
    ("person", re.compile(r"^(?:what(?:'s| is) my (" + _REL + r")(?:'s|s)? name|who(?:'s| is) my (" + _REL + r")|"
                          r"what(?:'s| is) my (" + _REL + r") called|what do i call my (" + _REL + r"))\b")),
    ("pets", re.compile(r"^(?:do i have (?:a |any )?(?:pets?|dogs?|cats?)|what pets do i have)\b")),
    ("learning", re.compile(r"^what (?:\w+ )?am i (?:learning|studying)\b")),
    ("profile", re.compile(r"^(?:what do you know about me|do you (?:remember|know) me|tell me about (?:me|myself)|who am i|"
                           r"what have i told you about (?:me|myself))\b")),
    ("advice", re.compile(r"^(?:what|which) should i (eat|watch|listen to|read|cook)\b")),
)

#: "What should I eat?": the favourite that speaks to it.
_ADVICE = {"eat": "food", "cook": "food", "watch": "film", "listen to": "band", "read": "book"}


def _clean(question: str) -> str:
    from tessellate.ai import question_noise

    #: "wat do u know abt me" read as typed would be no question at all.
    q = question_noise.repair(question_noise.tidy(question or ""))
    q = re.sub(r"[?!.]+$", "", q.strip().lower())
    q = re.sub(r"\b(?:ur|youre)\b", "your", q)
    q = re.sub(r"\bfav\b", "favourite", re.sub(r"\bfavorite\b", "favourite", q))
    return re.sub(r"\s+", " ", re.sub(r"^(?:so|ok|okay|hey|um|and|but)[, ]+", "", q)).replace("whats", "what's")


def asked(question: str) -> tuple[str, str] | None:
    """(kind, what) when the question asks the notes about the person."""
    q = _clean(question)
    for kind, pattern in _ASKS:
        m = pattern.match(q)
        if m:
            return kind, next((g for g in m.groups() if g), "") if m.groups() else ""
    return None


def answer(question: str, notes: Callable[[], list[dict]] | list[dict], today: date | None = None) -> dict | None:
    """The answer, as the composer's dict (text, grounding rows), or None
    when the question is not about the person. `notes` may be a loader, so
    the notebook is read only for a question that needs it."""
    kind = asked(question)
    if kind is None:
        return None
    held = facts(notes() if callable(notes) else notes)
    today = today or date.today()
    said = _SAY[kind[0]](kind[1], held, today)
    return _result(*said) if said else None


# --- saying it -------------------------------------------------------------------


def _day(fact: Fact, today: date) -> str:
    written = _written(fact.note)
    if written is None:
        return ""
    from tessellate.ai import composer_digest

    return composer_digest._day(written, today)


def _written(note: dict) -> date | None:
    raw = note.get("created_at")
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    try:
        return datetime.fromisoformat(str(raw).replace(" ", "T")[:19]).date()
    except ValueError:
        return None


def _line(fact: Fact, today: date) -> str:
    day = _day(fact, today)
    text = fact.said[0].upper() + fact.said[1:]
    return f"{text}, going by your note of {day}." if day else f"{text}."


def _row(fact: Fact, line: str) -> dict:
    content = str(fact.note.get("content") or "")
    start = content.find(fact.source)
    row = {"sentence": line, "note_id": fact.note.get("id"), "source": fact.source, "score": 1.0, "digest": True,
           "label": content.strip().splitlines()[0].lstrip("# ")[:60] if content.strip() else ""}
    if start >= 0:
        row.update(start=start, end=start + len(fact.source))
    return row


def _one(key: str, missing: str) -> Callable[[str, list[Fact], date], tuple]:
    def say(_what: str, held: list[Fact], today: date) -> tuple:
        found = [f for f in held if f.key == key]
        if not found:
            return [missing], []
        line = _line(found[0], today)
        return [line], [_row(found[0], line)]

    return say


def _age(_what: str, held: list[Fact], today: date) -> tuple:
    born = next((f for f in held if f.key == "born" and re.search(r"\b(19|20)\d\d\b", f.value)), None)
    if born:
        year = int(re.search(r"\b((?:19|20)\d\d)\b", born.value).group(1))
        line = f"You're about {today.year - year}: you were born in {year}, going by your note of {_day(born, today)}."
        return [line], [_row(born, line)]
    birthday = next((f for f in held if f.key == "birthday"), None)
    if birthday:
        line = f"Your notes give your birthday, {birthday.value}, but not the year you were born, so I can't work out your age."
        return [line], [_row(birthday, line)]
    return ["Your notes don't say how old you are or when you were born."], []


def _favourite(what: str, held: list[Fact], today: date) -> tuple:
    what = what.lower().rstrip("s") if what.lower() not in ("glass", "bus") else what.lower()
    favs = [f for f in held if f.key == "favourite"]
    hit = next((f for f in favs if f.value.split("=")[0].rstrip("s") in (what, f"{what}s")), None)
    if hit:
        value = hit.value.split("=", 1)[1]
        line = f"{value[0].upper() + value[1:]}, going by your note of {_day(hit, today)}."
        return [line], [_row(hit, line)]
    if not favs:
        return [f"Your notes don't name a favourite {what}."], []
    others = realise.join_items([f"{f.value.split('=')[0]} ({f.value.split('=', 1)[1]})" for f in favs[:3]])
    return [f"Your notes don't name a favourite {what}. They do name your favourite {others}."], []


def _person(what: str, held: list[Fact], today: date) -> tuple:
    hit = next((f for f in held if f.key == "person" and f.value.lower().startswith(what.lower() + "=")), None)
    if not hit:
        return [f"Your notes don't name your {what}."], []
    name = hit.value.split("=", 1)[1]
    line = f"Your {what} is {name}, going by your note of {_day(hit, today)}."
    return [line], [_row(hit, line)]


def _pets(_what: str, held: list[Fact], today: date) -> tuple:
    pets = [f for f in held if f.key == "person" and f.value.split("=")[0] in _PETS]
    if not pets:
        return ["Your notes don't mention a pet."], []
    lines = [f"Yes: {realise.join_items([f'{p.value.split(chr(61))[1]}, your {p.value.split(chr(61))[0]}' for p in pets])}, going by your notes."]
    return lines, [_row(p, lines[0]) for p in pets]


def _learning(_what: str, held: list[Fact], today: date) -> tuple:
    found = [f for f in held if f.key == "learning"]
    if not found:
        return ["Your notes don't say you're learning anything yet."], []
    line = f"{realise.join_items([f.value for f in found])}, going by your note{'s' if len(found) > 1 else ''} of {_day(found[0], today)}."
    return [line[0].upper() + line[1:]], [_row(f, line[0].upper() + line[1:]) for f in found]


_ORDER = ("live", "work", "birthday", "born", "person", "learning", "favourite")


def _profile(_what: str, held: list[Fact], today: date) -> tuple:
    if not held:
        return ["Only what your notes say, and none of them says anything about you yet. Write a note about yourself and I'll know it."], []
    shown = sorted(held, key=lambda f: _ORDER.index(f.key))[:8]
    lines = [f"From your notes, {realise.count_noun(len(shown), 'thing')} about you:"]
    rows = []
    for f in shown:
        item = f"- {f.said[0].upper() + f.said[1:]}."
        lines.append(item)
        rows.append(_row(f, item[2:]))
    return ["\n".join(lines)], rows


def _advice(what: str, held: list[Fact], today: date) -> tuple:
    topic = _ADVICE.get(what, "")
    hit = next((f for f in held if f.key == "favourite" and f.value.split("=")[0].rstrip("s") == topic), None)
    if not hit:
        return ["That's your call: I only know what your notes say, and none of them points either way."], []
    value = hit.value.split("=", 1)[1]
    line = f"Your call, but your favourite {topic} is {value}, going by your note of {_day(hit, today)}."
    return [line], [_row(hit, line)]


_SAY: dict[str, Callable[[str, list[Fact], date], tuple]] = {
    "live": _one("live", "Your notes don't say where you live yet. Write it in a note and I'll know it next time."),
    "work": _one("work", "Your notes don't say what you do for work."),
    "birthday": lambda what, held, today: _one("birthday", "")(what, held, today) if any(f.key == "birthday" for f in held)
    else _one("born", "Your notes don't say when your birthday is.")(what, held, today),
    "age": _age,
    "favourite": _favourite,
    "person": _person,
    "pets": _pets,
    "learning": _learning,
    "profile": _profile,
    "advice": _advice,
}


def _result(lines: list[str], rows: list[dict]) -> dict:
    n = len(rows)
    return {
        "text": "\n\n".join(lines),
        "grounding": rows,
        "next": [],
        "shape": "personal",
        "digest": True,
        "support": {"supported": n, "sentences": n, "unsupported": [], "digest": True},
    }


# --- about the assistant, and the world -------------------------------------------

_SELF: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"\b(feelings?|feel things|emotions?|conscious|alive|sentient)\b"),
     "No. I'm a program on this computer that reads your notes; I don't feel things, though I can tell you what you wrote on a hard day."),
    (re.compile(r"\b(?:who|what company|which company) (?:made|built|created|wrote|programmed) you\b|\bwho(?:'s| is) your (?:maker|creator|developer)\b"),
     "I'm Atlas, the part of Tessellate that answers from your notes. Tessellate runs on this computer, and no one else sees what you ask."),
    (re.compile(r"\bhow old are you\b|\bwhen were you (?:made|born)\b"),
     "Old enough to read your notes, young enough to have no birthday. I'm Atlas, and I live on this computer."),
    (re.compile(r"\bare you (?:a )?(?:real|human|person|robot|bot|ai)\b|\bare you real\b"),
     "I'm a program, not a person: Atlas, reading your notes on this computer."),
    (re.compile(r"\bwhat(?:'s| is) your fav(?:ou?rite)? (\w+)"),
     "I don't have one; I'm a program. I'm happiest when a question finds the right note."),
    (re.compile(r"\b(?:keep|tell anyone|share) (?:a |my )?secrets?\b|\bcan i tell you (?:a )?secret\b"),
     "Yes. What you write stays on this computer, and nothing is sent anywhere on its own."),
    (re.compile(r"\bdo you (?:sleep|eat|dream|get tired)\b"),
     "No. I'm a program, here whenever you open the app."),
)


#: "am I a good person": not a thing a notebook can say, and not guessed.
_JUDGE = re.compile(r"^am i (?:a |an )?(?:good|bad|smart|clever|stupid|dumb|ugly|pretty|attractive|normal|weird|boring|nice|kind|lazy|failure|loser)\b")


def about_me(question: str) -> str | None:
    """A question about the assistant itself, answered in its own voice;
    or one asking it to judge the person, which it does not."""
    q = _clean(question)
    if _JUDGE.match(q):
        return ("That's not something I can judge from a notebook, and I won't guess. "
                "I can find what you wrote about a day, a person or a plan, if that helps.")
    if not re.search(r"\byou(?:r|rself)?\b", q):
        return None
    return next((said for pattern, said in _SELF if pattern.search(q)), None)


_GENERAL = re.compile(r"^(?:what|who|where|when|why|how|which)(?:'s| is| are| was| were| did| does| do| many| much| far| long| big)?\b")
_PERSONAL = re.compile(r"\b(?:i|i'm|im|i've|me|my|mine|myself|we|our|us)\b")
#: "Who is Sam": a bare name is someone the notes may name, not the world's
#: (the engine probe's P1 says "I found nothing about “Sam”").
_WHO_NAME = re.compile(r"^who(?:'s| is| was) (?!the |a |an )\w+(?: \w+)?[?.]*$")


def general(question: str) -> bool:
    """A question about the world, not the person or their notes ("what's
    the capital of France"): with nothing found it is said as such."""
    q = _clean(question)
    if _WHO_NAME.match(q):
        return False
    return bool(_GENERAL.match(q)) and not _PERSONAL.search(q) and not re.search(r"\b(?:you|your|note|notes)\b", q)


_OWN_NOTES = re.compile(
    r"\b(?:my|our|your)\s+(?:\w+\s+){0,2}(?:notes?|notebook|entries|entry)\b|\b(?:notes?|entry) (?:i|we) (?:ever )?(?:wrote|made|took|saved)\b"
    r"|\bi (?:ever )?(?:wrote|made|saved)\b|\bin (?:my|the) notes\b"
)


def about_own_notes(question: str) -> bool:
    """A question about the person's own notes ("the first note I ever
    wrote"): the web has nothing on it, so it is never sent there (INBOX 1345 b)."""
    return bool(_OWN_NOTES.search(_clean(question)))


def general_reply(web_on: bool) -> str:
    if web_on:
        return "That's general knowledge rather than something in your notes, and the web search found nothing to go on."
    return ("That's general knowledge, and with no model running I only know what your notes say, and none of them covers it. "
            "Turn on web search in [Settings](#/settings/websearch) to look it up.")
