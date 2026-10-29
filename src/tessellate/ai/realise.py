"""Saying a note's sentence back to the person who wrote it (CHAT_PLAN Phase 6,
decision 33): grammar rules with a table of pairs each, no model.

- `shift_person`: the writer's "I", "my", "me" said as "you", "your",
  with the verb agreeing ("I am" is "you are", "I was" is "you were", "am I"
  is "are you", "I've" is "you have"); "Sam and I" is "you and Sam"; "we",
  "us" and "our" stay (the person was one of several). Never inside someone
  else's words: text in quotation marks, or after "Sam said:", is theirs.
- `past_plan`: a plan whose day has gone by, said in the past ("you plan to
  go" is "you planned to go"), the note's own words one tap away.
- `relative_day`: a day said against today ("yesterday", "on Friday", "last
  week", "two weeks ago", "on 3 March", "on 3 March 2025").
- `count_noun`, `join_items`, `after_comma`, `cut_title`: number agreement,
  a list said as one sentence, the case after a joining comma, a title cut
  at a word.

- `protected`, `opener`, `wording`, `variety`: the variety floor (decision
  51). A composed answer is parts; the protected ones (a quote, a title, a
  measured value, the asked words, a Help sentence) never vary, the rest
  (openers and joins) vary by chat and turn. `VARIETY_FLOOR` of
  `VARIETY_TURNS` turns of one question open differently, measured on every
  build by `tests/test_realise.py` in both voices and the help register.

Each rule is a table of input and output pairs in `tests/test_realise.py`;
a rule that would change what a sentence means has a pair that shows it
does not. The composer marks every sentence it shifted, and the grounding
row keeps the note's own words (`original`), so a shifted sentence is still
checked against the note it came from.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from tessellate.search.snippet import clip_words

_NUMBERS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve")
_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

# --- the app's own voice (decision 55) ----------------------------------------------

#: What the app says itself, one register (Brief 68 row 9): a failure is
#: "Couldn't {what}.", or with its reason "Couldn't {what}: {why}". The
#: browser's twin is `VOICE` in status.js, held equal by
#: tests/test_voice_tables.py.
VOICE = {
    "failed": "Couldn't {what}.",
    "failed_why": "Couldn't {what}: {why}",
}


def say(key: str, **slots: str) -> str:
    why = str(slots.get("why") or "").strip()
    shape = VOICE["failed_why" if key == "failed" and why else key]
    return shape.format(**{**slots, "why": why})


# --- person ---------------------------------------------------------------------

#: Whole-phrase rewrites first (verb agreement), then single words. Lowercase
#: keys; the replacement takes the case of the word it replaces, except that
#: "I" (always a capital) gives a lowercase "you": sentence case is the
#: caller's, which knows whether the sentence starts there.
_PHRASES = (
    (r"\bI am\b", "you are"),
    (r"\bI'm\b", "you're"),
    (r"\bI was\b", "you were"),
    (r"\bI wasn't\b", "you weren't"),
    (r"\bI was not\b", "you were not"),
    (r"\bI've\b", "you have"),
    (r"\bI'll\b", "you will"),
    (r"\bI'd\b", "you'd"),
    (r"\bam I\b", "are you"),
    (r"\bwas I\b", "were you"),
    (r"\bAm I\b", "Are you"),
    (r"\bWas I\b", "Were you"),
)
_PHRASE_RES = tuple((re.compile(p), r) for p, r in _PHRASES)
#: "Sam and I", "Sam and me": the person first, as people say it of others.
_AND_I = re.compile(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)?) and (?:I|me)\b")
#: A sentence's opening word is not a person: "Then Sam and I" is Sam.
_NOT_A_NAME = frozenset(
    "Then And But So When After Before Yesterday Today Tomorrow Later Also Now Once Last This Next Finally".split()
)
_WORDS = {"i": "you", "me": "you", "my": "your", "mine": "yours", "myself": "yourself"}
_WORD_RE = re.compile(r"\b(I|me|my|mine|myself|Me|My|Mine|Myself|MY)\b")
#: Where someone else's words start: a quotation mark, or "said:"-like.
_THEIRS = re.compile(r"[\"“][^\"“”]*[\"”]|\b(?:said|says|wrote|writes|told me|asked|replied)\s*:.*$", re.S)


def _case_like(word: str, said: str) -> str:
    if word == "I":
        return said
    if word.isupper() and len(word) > 1:
        return said.upper()
    if word[:1].isupper():
        return said[:1].upper() + said[1:]
    return said


#: Where a first-person word is not the writer: an idiom ("let me know",
#: "oh my", "my bad") or a numeral ("Part I", "World War I", "I/O"). Said as
#: written; each has a pair in the tests.
_KEEP = re.compile(
    r"(?i:\b(?:let|excuse|trust|believe|pardon|beats)\s+me\b|\boh my\b|\bmy (?:god|goodness|gosh|bad)\b)"
    r"|\b(?:Part|Chapter|Book|War|Phase|Season|Volume|Act|Henry|Elizabeth|Charles|George|Louis|Type|Level|Grade|Class)\s+I\b"
    r"|\bI/O\b|\bI-\d",
)


#: "I live in Perth and I work at the cafe": a place after a preposition,
#: then a new clause, is not a person beside the writer (found 2026-10-11:
#: it read "you live in you and Perth work").
_PLACE_BEFORE = re.compile(r"\b(?:in|at|to|from|near|for|on|of|by|into|around|across|outside|inside|visit|visited)\s+$", re.I)


def _with_you(match: re.Match) -> str:
    before = match.string[: match.start()]
    after = match.string[match.end():]
    if _PLACE_BEFORE.search(before) and re.match(r"\s+[a-z]", after) and match.group(0).endswith(" I"):
        return match.group(0)
    words = match.group(1).split()
    if words[0] in _NOT_A_NAME:
        if len(words) == 1:
            return match.group(0)
        return f"{words[0]} you and {words[1]}"
    return f"you and {match.group(1)}"


def _shift_words(text: str) -> str:
    text = _AND_I.sub(_with_you, text)
    for pattern, said in _PHRASE_RES:
        text = pattern.sub(said, text)
    return _WORD_RE.sub(lambda m: _case_like(m.group(1), _WORDS[m.group(1).lower()]), text)


def _shift_part(text: str) -> str:
    out = []
    cursor = 0
    for match in _KEEP.finditer(text):
        out.append(_shift_words(text[cursor:match.start()]))
        out.append(match.group(0))
        cursor = match.end()
    out.append(_shift_words(text[cursor:]))
    return "".join(out)


def shift_person(text: str, quoted: bool = False) -> str:
    """`text` with the writer's first person said as the reader's second.
    `quoted`: the whole text is someone else's words, so nothing changes."""
    if quoted or not text:
        return text
    out = []
    cursor = 0
    for match in _THEIRS.finditer(text):
        out.append(_shift_part(text[cursor:match.start()]))
        out.append(match.group(0))
        cursor = match.end()
    out.append(_shift_part(text[cursor:]))
    return "".join(out)


def first_person(text: str) -> bool:
    """Whether `shift_person` would change anything in `text`."""
    return shift_person(text) != text


# --- tense ------------------------------------------------------------------------

_PLAN_PAST = (
    (re.compile(r"\byou plan to\b"), "you planned to"),
    (re.compile(r"\byou are planning to\b"), "you were planning to"),
    (re.compile(r"\byou're planning to\b"), "you were planning to"),
    (re.compile(r"\byou are going to\b"), "you were going to"),
    (re.compile(r"\byou're going to\b"), "you were going to"),
    (re.compile(r"\byou are going\b"), "you were going"),
    (re.compile(r"\byou're going\b"), "you were going"),
    (re.compile(r"\byou will\b"), "you were going to"),
    (re.compile(r"\byou want to\b"), "you wanted to"),
    (re.compile(r"\byou need to\b"), "you needed to"),
    (re.compile(r"\byou intend to\b"), "you intended to"),
)


def past_plan(text: str, due: date | None, today: date) -> str:
    """A plan said in the second person, moved into the past when its day has
    gone by ("you plan to go on Friday", Friday past: "you planned to go on
    Friday"). Unchanged when the day is to come or not known."""
    if due is None or due >= today:
        return text
    for pattern, said in _PLAN_PAST:
        text = pattern.sub(said, text)
    return text


# --- days and counts ------------------------------------------------------------------


def count_word(n: int) -> str:
    return _NUMBERS[n] if 0 <= n < len(_NUMBERS) else str(n)


def relative_day(day: date, today: date) -> str:
    """`day` said against `today`, the way a person would: the exact date is
    the citation's to give."""
    delta = (today - day).days
    if delta == 0:
        return "today"
    if delta == 1:
        return "yesterday"
    if delta == -1:
        return "tomorrow"
    if 2 <= delta <= 6:
        return f"on {_WEEKDAYS[day.weekday()]}"
    if -6 <= delta <= -2:
        return f"on {_WEEKDAYS[day.weekday()]}"
    if 7 <= delta <= 13:
        return "last week"
    if -13 <= delta <= -7:
        return "next week"
    if 14 <= delta <= 34:
        return f"{count_word(delta // 7)} weeks ago"
    if day.year == today.year:
        return f"on {day.day} {_MONTHS[day.month - 1]}"
    return f"on {day.day} {_MONTHS[day.month - 1]} {day.year}"


_IRREGULAR_PLURALS = {"day": "days", "week": "weeks", "person": "people", "child": "children", "entry": "entries", "copy": "copies"}


def count_noun(n: int, noun: str, *, article: bool = False) -> str:
    """"one note", "two notes"; with `article`, "a day", "three days"."""
    if n == 1:
        if article:
            return f"{'an' if noun[:1].lower() in 'aeiou' else 'a'} {noun}"
        return f"one {noun}"
    plural = _IRREGULAR_PLURALS.get(noun) or (noun[:-1] + "ies" if noun.endswith("y") and noun[-2:-1] not in "aeiou" else noun + "s")
    return f"{count_word(n)} {plural}"


def join_items(items: list[str]) -> str:
    """A list said as one sentence: "A, B and C". The Oxford comma only when
    an item itself holds "and", so "bread, salt, and fish and chips" cannot be
    read as four things."""
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    oxford = "," if any(" and " in i for i in items) else ""
    return f"{', '.join(items[:-1])}{oxford} and {items[-1]}"


#: First words that are never a name, so lowered after a joining comma.
_COMMON = frozenset(
    """a an the it its this that these those there they their them we our you your he she his her
    one two three four five six seven eight nine ten every each some most all no not after before when
    if then in on at for to with from by of only just still maybe once both next last first until since
    what which who how why where""".split()
)


def after_comma(text: str) -> str:
    """The sentence's first letter as it reads after "Separately, ": lowered
    when its first word is a common word, kept when it may be a name or is
    "I"."""
    first = re.match(r"[A-Za-z']+", text or "")
    if not first or first.group(0).lower() not in _COMMON or first.group(0)[1:] != first.group(0)[1:].lower():
        return text
    return text[0].lower() + text[1:]


#: Words a clipped name never ends on: "Dentist appointment on 4 November at…"
#: says nothing, "Dentist appointment on 4 November…" does.
_DANGLING = frozenset("a an the and or but nor of to in on at for with by from as is are was were my your our their its this that if so then".split())


def cut_title(title: str, limit: int) -> str:
    """The one clip for a name or a line said back (audit 1029 C9): at most
    `limit` characters, cut at a word with an ellipsis, never through a word
    and never after a word that cannot end a phrase. Text that fits is
    returned whole, spaces folded."""
    flat = " ".join((title or "").split())
    clipped = clip_words(flat, limit)
    if clipped == flat:
        return flat
    return " ".join(drop_dangling(clipped.removesuffix("…").split(" "))).rstrip(" ,;:-") + "…"


def drop_dangling(words: list[str]) -> list[str]:
    """`words` without the function words a cut would leave at its end."""
    words = list(words)
    while len(words) > 1 and words[-1].lower().strip(",;:") in _DANGLING:
        words.pop()
    return words


_STOP_AFTER_STOP = re.compile(r"([?!])\.(?!\.)")
_COMMA_AFTER_STOP = re.compile(r"([?!]),(\s+)(\w)")


def mend_stops(text: str) -> str:
    """`text` without the stop a frame adds after a quote that ends a
    question or an exclamation: "theme?." is "theme?", and "next?, from your
    note" is "next? From your note" (audit 1029 C13)."""
    text = _STOP_AFTER_STOP.sub(r"\1", text)
    return _COMMA_AFTER_STOP.sub(lambda m: f"{m.group(1)}{m.group(2)}{m.group(3).upper()}", text)


# --- the variety floor (decision 51) ------------------------------------------------

#: Parts that carry a fact or the person's words: fixed whatever the turn.
PROTECTED = frozenset({"address", "confirmed", "quote", "title", "filed", "picture", "measure", "asked", "help", "web", "reminder", "term"})
#: Twenty turns of one question in one chat open at least eight ways: the
#: plan's floor was three (2026-10-10; measured 1 before the mention lead had
#: variants), raised to decision 58's target of eight by Brief 84 (measured
#: 8 natural, 8 professional, 9 help), so it is a ratchet now.
VARIETY_FLOOR = 8
VARIETY_TURNS = 20


def protected(parts: list) -> tuple:
    """The answer's protected spans, in order: what must not change between
    turns. A quote's first letter lowered after a joiner is the same fact."""
    return tuple((p[0], p[1][:1].lower() + p[1][1:]) for p in parts if p[0] in PROTECTED and p[1])


def opener(parts: list) -> str:
    """How an answer starts: its first worded template phrase, or the kind of
    the protected span it starts with ("(quote)")."""
    for part in parts:
        if part[0] != "template":
            return f"({part[0]})"
        if re.search(r"[A-Za-z]", part[1]):
            return part[1]
    return ""


def wording(parts: list) -> str:
    """The answer with every protected span said as its kind: what the
    realiser chose, apart from what the notes said."""
    return "".join(p[1] if p[0] not in PROTECTED else f"<{p[0]}>" for p in parts)


def variety(results: list[dict]) -> dict:
    """Over one question's answers in one chat: how many ways they open, how
    many wordings they take, and how many protected-span sets (one, always)."""
    return {
        "openers": len({opener(r["parts"]) for r in results}),
        "wordings": len({wording(r["parts"]) for r in results}),
        "facts": len({protected(r["parts"]) for r in results}),
    }


# --- output forms (CHAT_PLAN decision 59, step 2; Brief 84) ---------------------------------
#
# The shape comes from the data, never from the question: a count per name
# is a chart (a bar of counts), two or more columns of equal rows a table,
# one object a card, plain items a list. Each is drawn through the chat's
# existing answer blocks: the Markdown renderer's table (`.md-table`), list
# and callout (`> [!note]`, the card), and the Ask box's chart recipe
# (`drawAskChart`, ask-chart.js) for the bar of counts. No new markup.

FORMS = ("chart", "table", "card", "list")


def form_of(data: object) -> str | None:
    """The form `data` asks for, or None for data that is a sentence."""
    if isinstance(data, dict):
        return "card" if data else None
    if not isinstance(data, list) or not data:
        return None
    if all(isinstance(row, str) for row in data):
        return "list"
    if not all(isinstance(row, dict) and row for row in data):
        return None
    return _rows_form(data)


def _rows_form(rows: list[dict]) -> str:
    """Equal rows: one is a card, a name and a count each a chart, two or
    more columns a table; unequal rows a list."""
    columns = {tuple(row) for row in rows}
    if len(columns) != 1:
        return "list"
    keys = next(iter(columns))
    if len(rows) == 1:
        return "card"
    first = rows[0]
    counted = len(keys) == 2 and isinstance(first[keys[0]], str) and type(first[keys[1]]) is int
    return "chart" if counted else "table" if len(keys) >= 2 else "list"


def _cell(value: object) -> str:
    text = "" if value is None else ("yes" if value is True else "no" if value is False else str(value))
    return " ".join(text.replace("|", "/").split())


def table(rows: list[dict], headers: dict[str, str] | None = None) -> str:
    """A GFM pipe table (the renderer's `.md-table`), columns in row order."""
    keys = list(rows[0])
    names = [(headers or {}).get(k) or k.replace("_", " ").capitalize() for k in keys]
    lines = ["| " + " | ".join(names) + " |", "| " + " | ".join("---" for _ in keys) + " |"]
    lines += ["| " + " | ".join(_cell(row.get(k)) for k in keys) + " |" for row in rows]
    return "\n".join(lines)


def bullets(items: list[str]) -> str:
    return "\n".join(f"- {_cell(item)}" for item in items)


def card(title: str, fields: dict) -> str:
    """One object as a callout with a line per field (the renderer's card)."""
    lines = [f"> [!note] {_cell(title)}"]
    lines += [f"> - {_cell(k)}: {_cell(v)}" for k, v in fields.items() if v not in (None, "", [])]
    return "\n".join(lines)


def chart(title: str, by: str, rows: list[dict]) -> dict:
    """A bar of counts in the shape `drawAskChart` takes (ask-chart.js)."""
    keys = list(rows[0])
    bars = [{"label": str(r[keys[0]]), "value": int(r[keys[1]])} for r in rows]
    return {"title": title, "kind": "bar", "by": by, "rows": bars, "total": sum(b["value"] for b in bars)}


def render(data: object, *, title: str = "", by: str = "tag", headers: dict[str, str] | None = None) -> dict:
    """`data` in its form: {"form", "text" (Markdown, "" for a chart), "chart"}."""
    form = form_of(data)
    if form == "chart":
        return {"form": form, "text": "", "chart": chart(title, by, data)}  # type: ignore[arg-type]
    if form == "table":
        return {"form": form, "text": table(data, headers), "chart": None}  # type: ignore[arg-type]
    if form == "card":
        fields = data if isinstance(data, dict) else data[0]  # type: ignore[index]
        return {"form": form, "text": card(title, fields), "chart": None}
    if form == "list":
        items = [r if isinstance(r, str) else " ".join(_cell(v) for v in r.values()) for r in data]  # type: ignore[union-attr]
        return {"form": form, "text": bullets(items), "chart": None}
    return {"form": None, "text": "", "chart": None}


def _named(rows: list[dict]) -> list[dict]:
    return [{"name": str(r.get("name") or ""), "notes": int(r.get("notes") or 0)} for r in rows]


def _when(raw: object, today: date) -> str:
    try:
        moment = datetime.fromisoformat(str(raw))
    except ValueError:
        return ""
    clock = f"{moment.hour % 12 or 12}{f':{moment.minute:02d}' if moment.minute else ''}{'am' if moment.hour < 12 else 'pm'}"
    return f"{relative_day(moment.date(), today).removeprefix('on ')} at {clock}"


_EMPTY = {"form": None, "text": "", "chart": None}


#: Named in the lead up to this many; past it, the most used and a count.
_NAMED_IN_LEAD = 6


def named_lead(rows: list[dict], noun: str, name: str = "name", notes: str = "notes") -> str:
    """"You have three categories: Uni (3), Hobbies (2) and Personal (2)."
    Every one named when they are few (INBOX 1357, class I: "list my
    categories" named only the biggest); past `_NAMED_IN_LEAD`, the most used."""
    mark = "#" if noun == "tag" else ""
    said = [f"{mark}{r.get(name)} ({r.get(notes)})" for r in rows]
    if len(rows) <= _NAMED_IN_LEAD:
        return f"You have {count_noun(len(rows), noun)}: {join_items(said)}."
    return f"You have {count_noun(len(rows), noun)}; the most used are {join_items(said[:3])}."


def _say_named(tool: str, result: dict, today: date) -> tuple[str, dict]:
    key, noun = ("tags", "tag") if tool == "list_tags" else ("categories", "category")
    rows = _named(result.get(key) or [])
    if not rows:
        return f"You have no {key} yet.", _EMPTY
    lead = named_lead(rows, noun)
    return lead, render(rows, title=f"Notes per {noun}", by=noun) if len(rows) > 1 else _EMPTY


def _say_count(tool: str, result: dict, today: date) -> tuple[str, dict]:
    per = [{"name": k, "notes": int(v)} for k, v in (result.get("by_category") or {}).items()]
    #: A scoped count ("tagged harbor") is `count`; the whole notebook's is
    #: `total`. Reading only `total` said "You have no notes." to the first.
    lead = f"You have {count_noun(int(result.get('total') or result.get('count') or 0), 'note')}."
    return lead, render(per, title="Notes per category", by="category") if len(per) > 1 else _EMPTY


def _first_five(rows: list[dict]) -> str:
    return join_items([r["name"] for r in rows[:5]]) + (f" and {len(rows) - 5} more" if len(rows) > 5 else "")


def _say_overview(tool: str, result: dict, today: date) -> tuple[str, dict]:
    cats, tags = _named(result.get("categories") or []), _named(result.get("tags") or [])
    fields = {"Notes": int(result.get("total_notes") or 0), "Categories": _first_five(cats), "Tags": _first_five(tags)}
    return "Your notebook at a glance.", render(fields, title="Your notebook")


def _say_structure(tool: str, result: dict, today: date) -> tuple[str, dict]:
    fields = {"Notes": result.get("notes"), "Connected": result.get("connected"),
              "Clusters": result.get("cluster_count"), "Not linked to anything": result.get("orphan_count")}
    return "How your notes connect.", render(fields, title="Your notebook's shape")


def _say_reminders(tool: str, result: dict, today: date) -> tuple[str, dict]:
    rows = [{"Reminder": r.get("text"), "When": _when(r.get("due_at"), today)} for r in result.get("reminders") or [] if not r.get("done")]
    if not rows:
        return "You have no reminders waiting.", _EMPTY
    shaped = render(rows) if len(rows) > 1 else render(rows, title=str(rows[0]["Reminder"]))
    return f"You have {count_noun(len(rows), 'reminder')} waiting.", shaped


_LISTED = {"list_documents": ("documents", "document"), "list_notes": ("notes", "note"), "list_skills": ("skills", "skill")}


def _say_listed(tool: str, result: dict, today: date) -> tuple[str, dict]:
    key, noun = _LISTED[tool]
    found = result.get(key) or []
    if not found:
        return f"You have no {key} yet.", _EMPTY
    if tool == "list_skills":
        rows = [{"Skill": s.get("name"), "When to use it": cut_title(str(s.get("when_to_use") or ""), 80)} for s in found[:12]]
        shaped = render(rows) if len(rows) > 1 else _EMPTY
    else:
        shaped = render([cut_title(str(d.get("title") or d.get("content") or "").split("\n")[0], 60) for d in found[:10]])
    total = int(result.get("total_matching") or result.get("total") or len(found))
    if total > 10:
        return f"The newest {count_word(min(len(found), 10))} of your {total} {key}.", shaped
    return f"You have {count_noun(total, noun)}" + (", newest first." if tool != "list_skills" else "."), shaped


def _title_and_line(content: str) -> tuple[str, str]:
    """A note's title (its first line, heading marks off) and its first line
    of body, for a one-line row."""
    lines = [ln.strip() for ln in str(content or "").splitlines() if ln.strip()]
    if not lines:
        return "Untitled", ""
    title = lines[0].lstrip("#").strip() or "Untitled"
    return cut_title(title, 60), cut_title(lines[1].lstrip("#-*> ").strip(), 100) if len(lines) > 1 else ""


def _say_found(tool: str, result: dict, today: date) -> tuple[str, dict]:
    """search_notes (INBOX 801: "it doesnt output tool results with the
    composer"): the titles found, one line each, in the order found."""
    notes = [n for n in result.get("notes") or [] if isinstance(n, dict) and not n.get("why")]
    asked = re.search(r"“(.+)”", str(result.get("label") or ""))
    about = f" about “{asked.group(1)}”" if asked else ""
    if not notes:
        return f"I found no notes{about}.", _EMPTY
    rows = []
    for note in notes[:5]:
        title, line = _title_and_line(note.get("content"))
        rows.append(f"- **{title}**" + (f": {line}" if line else ""))
    more = f" The first five of {int(result.get('found') or len(notes))}." if len(notes) > 5 else ""
    return f"I found {count_noun(len(notes), 'note')}{about}.{more}", {"form": "list", "text": "\n".join(rows), "chart": None}


def _say_time(tool: str, result: dict, today: date) -> tuple[str, dict]:
    where = f" in {result['place']}" if result.get("place") else ""
    return f"It is {result.get('human') or 'unknown'}{where}.", _EMPTY


def _say_worked(tool: str, result: dict, today: date) -> tuple[str, dict]:
    answer = str(result.get("answer") or "").strip()
    read = str(result.get("read_as") or "").strip()
    return (answer + (f"\nRead as {read}." if read and read not in answer else "")), _EMPTY


_SAYERS = {
    "list_tags": _say_named, "list_categories": _say_named, "count_notes": _say_count,
    "notebook_overview": _say_overview, "notebook_structure": _say_structure, "list_reminders": _say_reminders,
    "list_documents": _say_listed, "list_notes": _say_listed, "list_skills": _say_listed,
    "search_notes": _say_found, "get_current_time": _say_time, "calculate": _say_worked,
}


def tool_answer(tool: str, result: dict, today: date) -> dict | None:
    """A read tool's result said in one line and drawn in its form (decision
    59, steps 1 and 2): {"text", "form", "chart"}; None for a tool this does
    not say, or a result that is an error."""
    sayer = _SAYERS.get(tool)
    if sayer is None or not isinstance(result, dict) or result.get("error"):
        return None
    lead, shaped = sayer(tool, result, today)
    text = lead if not shaped["text"] else f"{lead}\n\n{shaped['text']}"
    return {"text": text, "form": shaped["form"], "chart": shaped["chart"]}
