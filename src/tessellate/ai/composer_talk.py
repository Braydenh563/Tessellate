"""The composer holds a conversation (INBOX 1729).

Three things the no-model answer writer did one turn at a time:

- **Next chips on every answer.** An answer that ends with none (an empty day,
  a slash list, the statistics overview) gets the acts its subject offers
  (`Closing`).
- **A follow-on reads the turn before.** "Any other diagrams?" after a chart
  draws one it has not drawn; "what are those tags?" after the overview lists
  the tags (`reply`). The turn before is read from its question and answer
  text (`previous`), the only state a request carries.
- **The stumped line is the last resort**, and its chips are the previous
  subject's acts (`acts_for`).

Every number comes from the notebook's own counts (`slash_more`,
`notebook_stats`); no model writes a word of it.
"""

from __future__ import annotations

import calendar
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.ai import consent, consent_store, composer_chips, composer_remark, follow_items, intent, realise, slash, slash_more
from tessellate.ai import recognise_questions

#: The charts the app can already draw from the notes, in the order offered.
CHARTS = ("time", "tag", "category", "weekday")
_CHART_WORDS = {"time": "per week", "tag": "per tag", "category": "per category", "weekday": "per weekday"}
SHOWN_TAGS = 40

_OTHER = r"other|another|more|different|else|additional|further|new"
_CHART_NOUN = r"diagrams?|charts?|graphs?|plots?|visuali[sz]ations?"
_OTHER_CHART = re.compile(rf"\b(?:{_OTHER})\b.*\b(?:{_CHART_NOUN})\b|\b(?:{_CHART_NOUN})\b.*\b(?:{_OTHER})\b", re.I)
_BARE_OTHER = re.compile(rf"^(?:and |ok |okay |so )?(?:(?:show|give|draw) me |any |do you have |got )?(?:an?|the|any)? ?(?:{_OTHER}) ?(?:one|ones)?\W*$", re.I)
_CHART_ASK = re.compile(r"^(?:(?:show|draw|chart|graph|plot|give|see)\b.*?)\b(?:notes?|writing) (?:per|by|each) (?P<by>week ?day|day of the week|week|month|tag|category)\b", re.I)
#: The ask said whole, for a turn a model may answer: anything after the period word ("by tag recipes",
#: "per week about the garden") is a filter or a summary the chart does not do (review of PR 216).
_CHART_ASK_WHOLE = re.compile(
    rf"^(?:show|draw|chart|graph|plot|give|see)\b(?: me| us)?(?: an?| the| all)?(?: my| our| the)?(?: (?:{_CHART_NOUN}) of)?(?: my| our| the| all)? ?(?:notes?|writing) (?:per|by|each) "
    r"(?P<by>week ?day|day of the week|week|month|tag|category)(?:[\s,]*(?:please|thanks|thank you|for me))?$", re.I)
_BY_WORD = {"week": "time", "tag": "tag", "category": "category", "weekday": "weekday"}
_PART = re.compile(r"\b(?P<part>tags?|categor(?:y|ies)|documents?|docs|month)\b", re.I)
_REFERS = re.compile(r"\b(?:those|these|that|the|which|what|list|show|name|its|their)\b", re.I)


@dataclass
class Prev:
    """What the turn before showed: its kind, the charts it drew, the days it
    was about and whether they held nothing."""

    kind: str = ""
    shown: set = field(default_factory=set)
    window: tuple[date, date] | None = None
    empty: bool = False


def _n(n: int, word: str) -> str:
    """"10 tags": the figure as the overview writes it."""
    return f"{n} {word}{'' if n == 1 else 's'}"


def _clean(text: str) -> str:
    return " ".join(str(text or "").replace("’", "'").split())


def _window(question: str, today: date) -> tuple[date, date] | None:
    typed = slash.parse(question)
    if typed:
        got = slash._window(typed[0] if typed[0] in ("today", "yesterday") else typed[1], today) if typed[0] in ("today", "yesterday", "made") else None  # noqa: SLF001
        return (got[0], got[1]) if got else None
    got = recognise_questions.question_day(question, today)
    return (got[0], got[1]) if got else None


#: What an answer's own words say it was: (pattern, kind, charts it drew). A chart
#: of None is the one its words name.
_BY_ANSWER = (
    (re.compile(r"Open Statistics for the full picture"), "overview", set()),
    (re.compile(r"Here are your notes per (week|tag|category|weekday)\b"), "chart", None),
    (re.compile(r"Your (?:\w+ )?distinct tags?, most used first|Your most-used tags"), "tags", {"tag"}),
    (re.compile(r"Your notes sit in |The categories with the most notes"), "categories", {"category"}),
    (re.compile(r"Your \d+ documents?, newest first|You have no documents"), "documents", set()),
    (re.compile(r"^.{0,40} was your busiest month, with "), "month", set()),
)


def _kind_of_answer(answer: str) -> Prev | None:
    for pattern, kind, drew in _BY_ANSWER:
        found = pattern.search(answer)
        if found:
            return Prev(kind, {_BY_WORD[found.group(1)]} if drew is None else set(drew))
    return None


def previous(question: str, answer: str, today: date) -> Prev:
    """The kind of an answer, read from its words and the question that got it."""
    said = _kind_of_answer(answer)
    typed = slash.parse(question)
    name = typed[0] if typed else ""
    if said is None and name in ("tags", "categories"):
        said = Prev(name, {"tag" if name == "tags" else "category"})
    if said is not None:
        return said
    listed = "](#/notes/" in answer
    window = _window(question, today)
    if window and (name in ("today", "yesterday", "made") or not listed):
        return Prev("window", {"time"}, window, not listed)
    return Prev("notes") if listed else Prev()


# --- the charts ---------------------------------------------------------------


def _bar(title: str, by: str, rows: list[dict]) -> dict | None:
    return {"type": "chart", "chart": realise.chart(title, by, rows)} if rows and realise.form_of(rows) == "chart" else None


def _weekdays(session: Session) -> list[dict]:
    entry, visible = slash_more._notes()  # noqa: SLF001
    days = Counter(made.weekday() for made in session.scalars(select(entry.created_at).where(*visible)) if made)
    return [{"name": calendar.day_name[i], "notes": days.get(i, 0)} for i in range(7)] if days else []


def drawing(session: Session, kind: str, today: date) -> dict | None:
    """The event that draws chart `kind` over every note, None when the
    notebook is too small to draw it."""
    if kind == "time":
        return slash_more.empty_timeline(session, today)
    if kind == "tag":
        return _bar("Notes per tag", "tag", [{"name": t, "notes": n} for t, n in slash_more.tag_counts(session).most_common(15)])
    if kind == "category":
        return _bar("Notes per category", "category", [{"name": str(c), "notes": int(n)} for c, n in slash_more.category_counts(session)[0][:15]])
    return _bar("Notes per weekday", "weekday", _weekdays(session)) if kind == "weekday" else None


def _chart_chip(kind: str) -> str:
    return f"Show notes {_CHART_WORDS[kind]}"


def _chart_reply(session: Session, kind: str, today: date, lead: str, others: list[str]) -> list[dict]:
    drawn = drawing(session, kind, today)
    tail = f" I can also draw notes {_join([_CHART_WORDS[k] for k in others])}." if others else ""
    events: list[dict] = [{"type": "answer", "delta": f"{lead}{tail}"}]
    if drawn:
        events.append(drawn)
    asks = [*map(_chart_chip, others[:3]), "Notebook statistics"] if others else ["Notebook statistics", "What did I write this week?"]
    return [*events, {"type": "offer", "offer": {"kind": "ask", "label": "", "asks": asks[:4]}}]


def _join(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " or " + parts[-1]


def _other_chart(session: Session, question: str, prev: Prev, today: date) -> list[dict] | None:
    """"Any other diagrams you can show me?": the charts the notebook can draw
    that the turn before did not."""
    asked = _OTHER_CHART.search(question) and (prev.shown or len(question.split()) <= 9)
    if not (asked or (prev.shown and _BARE_OTHER.match(question))):
        return None
    left = [k for k in CHARTS if k not in prev.shown and drawing(session, k, today)]
    if not left:
        return [{"type": "answer", "delta": "That is every chart I can draw from your notes. Statistics holds the rest of the numbers."}]
    first, rest = left[0], left[1:]
    return _chart_reply(session, first, today, f"Here are your notes {_CHART_WORDS[first]}.", rest)


def _chart_by(session: Session, question: str, prev: Prev, today: date, *, whole: bool = False) -> list[dict] | None:
    """"Show notes per tag", the chip an offered chart is."""
    got = (_CHART_ASK_WHOLE if whole else _CHART_ASK).search(question)
    if not got:
        return None
    word = got.group("by").lower().replace(" ", "")
    kind = "weekday" if word.startswith("week") and word != "week" or word == "dayoftheweek" else "time" if word in ("week", "month") else word
    if kind not in CHARTS or not drawing(session, kind, today):
        return None
    left = [k for k in CHARTS if k != kind and k not in prev.shown]
    return _chart_reply(session, kind, today, f"Here are your notes {_CHART_WORDS[kind]}.", left)


# --- parts of an answer -------------------------------------------------------


def _tag_list(session: Session, today: date) -> list[dict] | None:
    counts = slash_more.tag_counts(session)
    if not counts:
        return [{"type": "answer", "delta": "None of your notes carry a tag yet."}]
    top = counts.most_common(SHOWN_TAGS)
    lines = "\n".join(f"- {tag} ({n})" for tag, n in top)
    more = f"\n\n{realise.count_word(len(counts) - len(top)).capitalize()} more are in Notes." if len(counts) > len(top) else ""
    events: list[dict] = [{"type": "answer", "delta": f"Your {_n(len(counts), 'distinct tag')}, most used first:\n\n{lines}{more}"}]
    drawn = drawing(session, "tag", today)
    return events + ([drawn] if drawn else [])


def _category_list(session: Session, today: date) -> list[dict] | None:
    rows, unfiled = slash_more.category_counts(session)
    if not rows:
        return [{"type": "answer", "delta": "None of your notes are filed in a category yet."}]
    lines = "\n".join(f"- {name} ({n})" for name, n in rows)
    left = f"\n\n{realise.count_noun(unfiled, 'note').capitalize()} {'is' if unfiled == 1 else 'are'} filed nowhere." if unfiled else ""
    return [{"type": "answer", "delta": f"Your notes sit in {len(rows)} {'category' if len(rows) == 1 else 'categories'}:\n\n{lines}{left}"}]


def _document_list(session: Session, today: date) -> list[dict] | None:
    from tessellate.core.database import Document

    titles = [str(d.title) for d in session.scalars(select(Document).order_by(Document.updated_at.desc()).limit(SHOWN_TAGS))]
    if not titles:
        return [{"type": "answer", "delta": "You have no documents yet."}]
    return [{"type": "answer", "delta": f"Your {_n(len(titles), 'document')}, newest first:\n\n" + "\n".join(f"- {t}" for t in titles)}]


def _busiest_month(session: Session) -> tuple[int, int, int] | None:
    entry, visible = slash_more._notes()  # noqa: SLF001
    months = Counter((made.year, made.month) for made in session.scalars(select(entry.created_at).where(*visible)) if made)
    if len(months) < 2:
        return None
    (year, month), n = months.most_common(1)[0]
    return year, month, n


def _month_list(session: Session, today: date) -> list[dict] | None:
    found = _busiest_month(session)
    if found is None:
        return None
    year, month, n = found
    entry, visible = slash_more._notes()  # noqa: SLF001
    start = datetime(year, month, 1)
    end = datetime(year + (month == 12), month % 12 + 1, 1)
    rows = list(session.scalars(select(entry).where(*visible, entry.created_at >= start, entry.created_at < end).order_by(entry.created_at.desc(), entry.id.desc())))
    lead = f"{start:%B %Y} was your busiest month, with {_n(n, 'note')}:"
    return [{"type": "answer", "delta": f"{lead}\n\n{slash_more._rows(session, rows)}{slash_more._more(len(rows))}"}]  # noqa: SLF001


_PARTS = {"tag": _tag_list, "categor": _category_list, "doc": _document_list, "month": _month_list}


def _part_of(session: Session, question: str, prev: Prev, today: date) -> list[dict] | None:
    """"What are those distinct tags": the part of the overview the question names, listed."""
    got = _PART.search(question)
    if not got or prev.kind not in _PARTED or not _REFERS.search(question):
        return None
    word = got.group("part").lower()
    key = next(k for k in _PARTS if word.startswith(k))
    if prev.kind == "tags" and key == "tag" or prev.kind == "categories" and key == "categor" or prev.kind == "month" and key == "month":
        return None
    return _PARTS[key](session, today)


_PARTED = ("overview", "tags", "categories", "documents", "month")
_READERS = (_other_chart, _chart_by, _part_of)


def _previous_turn(turn: dict, today: date) -> Prev:
    """One turn's kind. A dated question answered from a note ("the first one", whose frame names
    the note it read) showed that note, not a chart of the days (fable-composer-1110 F1)."""
    said = previous(str(turn.get("question") or ""), str(turn.get("answer") or ""), today)
    frame = turn.get("frame") if isinstance(turn.get("frame"), dict) else {}
    return Prev("notes") if said.kind == "window" and not said.empty and frame.get("note_ids") else said


def from_history(history: list[dict], today: date) -> Prev:
    """The turn before, with every chart the last few turns drew."""
    turns = [_previous_turn(t, today) for t in (history or [])[-6:]]
    if not turns:
        return Prev()
    last = turns[-1]
    last.shown = set().union(*(t.shown for t in turns))
    return last


def reply(session: Session, question: str, history: list[dict], today: date) -> list[dict] | None:
    """The events for a question that reads against the turn before it (or names a chart), else None."""
    said = _clean(question).rstrip("?!. ")
    if not said:
        return None
    if asks := follow_items.read(question, history, datetime.combine(today, time(9)))[1]:
        return [{"type": "answer", "delta": asks}]
    prev = from_history(history, today)
    for read in _READERS:
        events = read(session, said, prev, today)
        if events is not None:
            return events
    return None


def chart_ask(session: Session, question: str, history: list[dict], today: date) -> list[dict] | None:
    """"Show notes per week": the chart, with a model up too (CHAT_PLAN decision
    75). A model handed the ask called the notes list with the category "week"
    and said there were none (the owner, 2026-11-12)."""
    said = _clean(question).rstrip("?!. ")
    drawn = _chart_by(session, said, from_history(history, today), today, whole=True) if said else None
    return drawn if drawn is not None else _graph_pasted(question, history)


def _graph_pasted(question: str, history: list[dict]) -> list[dict] | None:
    """"Chart this: Mon 3, Tue 5": the values given (or the answer before) as
    the chart maker's fence, with a model up too (L158, INBOX 1847)."""
    from tessellate.ai import composer_graph

    previous = str((history or [{}])[-1].get("answer") or "") if history else ""
    made = composer_graph.pasted(question or "", previous=previous)
    return [{"type": "answer", "delta": made["text"]}] if made else None


# --- an offer taken up (B23) ----------------------------------------------------

def is_yes(question: str) -> bool:
    """A bare yes in any of its forms (yeah, yep, sure, ok, go ahead, please do), the reader typed consent uses."""
    return consent.says(_clean(question).strip()) == "yes"


#: The offers an answer ends with that a sentence can carry out: a reminder, said as the prose asks it or as its button does.
_REMIND_OFFER = re.compile(
    r"^(?:shall i remind you|remind you|set a reminder|want a nudge|should i remind you|want me to remind you)(?: (?P<every>(?:each|every) \w+))? to (?P<action>.+?)\??$", re.I
)


def accepted_offer(question: str, history: list[dict] | None, now: datetime | None = None) -> str | None:
    """The sentence a bare "yes" stands for when the answer before it ended with an offer
    the composer can carry out ("Shall I remind you to call the plumber?" is "remind me to
    call the plumber"), else None. An offer with no act behind it is not guessed at.
    An instruction after a list or an act ("remove milk", "make it 6") is the act on
    what that answer showed (`follow_items`)."""
    if history and (said := follow_items.read(question, history, now)[0]):
        return said
    if not history or not is_yes(question):
        return None
    lines = [ln.strip(" *_") for ln in str(history[-1].get("answer") or "").splitlines() if ln.strip()]
    found = _REMIND_OFFER.match(lines[-1]) if lines else None
    if not found:
        return _note_offer_sentence(lines)
    action = re.sub(r"\byour\b", "my", found.group("action").strip().rstrip("?."), flags=re.I) if found.group("every") else found.group("action").strip().rstrip("?.")
    return f"remind me to {action}" + (f" {found.group('every').replace('each', 'every')}" if found.group("every") else "")


def held_offer(question: str, history: list[dict] | None) -> str | None:
    """The text of the note a bare "yes" makes when the answer before it ended with an offer the server
    holds (Gather them into one note, Track your lifts in a table): their words are the notes', which the turn
    sent back no longer has. The id is spent by the yes; it is taken only while the offer is still the answer's
    last line, so a yes to another question reaches nothing."""
    last = (history or [{}])[-1] if history else {}
    key = str(last.get("offer_id") or "")
    if not key or not is_yes(question):
        return None
    held = (consent_store.peek(key) or {}).get("offer")
    lines = [ln.strip(" *_") for ln in str(last.get("answer") or "").splitlines() if ln.strip()]
    if not held or not lines or lines[-1] != str(held.get("line") or "").strip(" *_"):
        return None
    consent_store.take(key)
    return str(held["text"])


#: The offers that save a note, said as the button's label says them (`composer_digest.PHRASES`).
_CHECKLIST_OFFER = re.compile(r"^save it as a checklist note\??$", re.I)
_PICK_OFFER = re.compile(r"^note the (?P<side>.+?) as your pick\??$", re.I)
_LIST_OFFER = re.compile(r"^start a list of (?P<what>.+?) to (?P<verb>[\w ]+?) next\??$", re.I)
_OPENING_COUNT = re.compile(r"^(?:\w+) (?P<what>.+?), from ", re.I)


def _note_offer_sentence(lines: list[str]) -> str | None:
    """The sentence for a note offer taken up (B23): "Save it as a checklist note?" is the
    list lines above it, "Note the first as your pick?" the pick, "Start a list of films to
    watch next?" an empty list. Rebuilt from the answer's own text, since a turn sent back
    holds no more; the yes is the consent, as for a reminder. Gathering and a table carry
    notes' words the text no longer holds, so they stay the button's."""
    last = lines[-1] if lines else ""
    if _CHECKLIST_OFFER.match(last):
        items = [m.group(1).strip() for ln in lines if (m := re.match(r"^-\s*\[ \]\s+(.+)$", ln))]
        if not items:
            return None
        what = _OPENING_COUNT.match(lines[0])
        title = (what.group("what") if what else "").strip()
        called = f" called {title[:1].upper() + title[1:]}" if title and not re.search(r"\b(?:of|for|with|containing|including)\b", title, re.I) else ""
        quoted = ", ".join(f'"{i}"' if re.search(r"\band\b|[,;&]", i) else i for i in items)
        return f"make a checklist note{called} of {quoted}"
    if pick := _PICK_OFFER.match(last):
        return f"make a note: My pick: the {pick.group('side').strip()}"
    if start := _LIST_OFFER.match(last):
        return f"make a checklist for {start.group('what')} to {start.group('verb')} next"
    return None


def cited_question(question: str, history: list[dict] | None, now: datetime) -> str | None:
    """"Open it", "tell me more about the starter" (audit 1029 C44): the question with its referent
    named, the leading note the last answer cited, so it is never searched by its own words."""
    from tessellate.ai import reading

    turns = [{"text": str(t.get("question") or ""), "objects": t.get("objects") or []} for t in (history or [])[-reading.FOLLOW_TURNS:]]
    if not history:
        return None
    from tessellate.ai import composer_dialogue

    if composer_dialogue.other_in_frames(question, history):
        return None  # the frames bind "and the other" to the next note of the list the pick came from
    #: "and the other one?" is the question before about the other note it cited (B21), which `cited_follow` leaves to acts.
    other = reading.follow(question, turns, now)
    return reading.cited_follow(question, turns, now) or (other[0] if other and other[1] == "other" else None)


# --- what to offer next ---------------------------------------------------------


def _day(d: date, today: date) -> str:
    return f"{d.day} {d:%B}" if d.year == today.year else f"{d.day} {d:%B %Y}"


def _nearest_day(session: Session, window: tuple[date, date]) -> date | None:
    entry, visible = slash_more._notes()  # noqa: SLF001
    before = session.scalar(select(func.max(entry.created_at)).where(*visible, entry.created_at < datetime.combine(window[0], time.min)))
    after = session.scalar(select(func.min(entry.created_at)).where(*visible, entry.created_at >= datetime.combine(window[1] + timedelta(days=1), time.min)))
    near = [d.date() for d in (before, after) if d]
    return min(near, key=lambda d: abs((d - window[0]).days)) if near else None


def _busiest_week(session: Session) -> tuple[date, date] | None:
    entry, visible = slash_more._notes()  # noqa: SLF001
    weeks = Counter((made.date() - timedelta(days=made.weekday())) for made in session.scalars(select(entry.created_at).where(*visible)) if made)
    if not weeks:
        return None
    start = weeks.most_common(1)[0][0]
    return start, start + timedelta(days=6)


def _empty_day_acts(session: Session, prev: Prev, today: date) -> list[str]:
    acts: list[str] = []
    near = _nearest_day(session, prev.window) if prev.window else None
    if near:
        acts.append(f"What did I write on {_day(near, today)}?")
    acts.append("What did I write this week?")
    week = _busiest_week(session)
    if week:
        acts.append(f"What did I write from {_day(week[0], today)} to {_day(week[1], today)}?")
    return acts


def acts_for(session: Session, prev: Prev, today: date, *, generic: bool = True) -> list[str]:
    """What can be done with the subject of an answer: the chips under it."""
    others = [k for k in CHARTS if k not in prev.shown and drawing(session, k, today)]
    if prev.kind == "window" and prev.empty:
        return _empty_day_acts(session, prev, today)
    if prev.kind in ("documents", "month"):
        return ["Notebook statistics", "List my categories", "Which tags do I use most?", *map(_chart_chip, others[:1])]
    if prev.kind == "overview":
        return ["Which tags do I use most?", "List my categories", "What documents do I have?", "Which was my busiest month?"]
    if prev.kind == "tags":
        return ["List my categories", *map(_chart_chip, others[:2])]
    if prev.kind == "categories":
        return ["Which tags do I use most?", *map(_chart_chip, others[:2])]
    if prev.kind in ("window", "notes", "chart"):
        return [*map(_chart_chip, others[:2]), "What did I write this week?"]
    #: The generic trio is for a first turn or a stumped one, never while an answer has a subject (F5).
    return ["What did I write this week?", "Notebook statistics", "What can you do?"] if generic else []


def _offers_chips(event: dict) -> bool:
    """Whether the event is an offer or carries Next chips (the turn has its own)."""
    return event.get("type") == "offer" or event.get("type") == "grounding" and bool(event.get("next"))


class Closing:
    """Watches a composed turn's events and, when it ends with no Next chips,
    adds the subject's own (INBOX 1729 a). A turn whose only offer is an
    "open" button carries the chips inside it (`also`), since the page keeps
    one offer a turn. `active=False` makes every call a no-op."""

    def __init__(self, session: Session, question: str, today: date, active: bool = True, history: list[dict] | None = None) -> None:
        self.session, self.question, self.today, self.active = session, question, today, active
        self.history = history
        self.chipped = not active
        self.shown: set = set()
        #: A frame was sent: the answer has a subject, so the generic trio is not its chips (F5).
        self.framed = False
        self.asked = False
        #: Chips came with the turn (a model's, an offer), whether or not this closing is active.
        self.offered = False

    def _note(self, event: dict) -> None:
        kind = event.get("type")
        self.offered = self.offered or _offers_chips(event)
        self.framed = self.framed or kind == "frame"
        self.asked = self.asked or kind == "offer" and (event.get("offer") or {}).get("kind") == "ask"
        if kind == "grounding" and event.get("next") or kind == "offer" and (event.get("offer") or {}).get("kind") == "ask":
            self.chipped = True
        if kind == "panel" and event.get("panel") == "timeline":
            self.shown.add("time")
        if kind == "chart":
            self.shown.add((event.get("chart") or {}).get("by"))

    def see(self, event: dict, answer: str) -> dict:
        """The event, with the chips inside it when it is the only offer."""
        self._note(event)
        offer = event.get("offer") if event.get("type") == "offer" else None
        asks = self.asks(answer) if offer and offer.get("kind") != "ask" and not self.chipped else []
        if not asks:
            return event
        self.chipped = True
        return {**event, "offer": {**offer, "also": [*(offer.get("also") or []), {"kind": "ask", "label": "", "asks": asks}]}}

    def asks(self, answer: str) -> list[str]:
        prev = previous(self.question, answer, self.today)
        prev.shown |= self.shown
        return acts_for(self.session, prev, self.today, generic=not self.framed)[:4]

    def finish(self, answer: str) -> list[dict]:
        """The offer to add after the last event, when there is an answer and no chips. A reminder
        asked "when?" offers the times its sentence lists (F5)."""
        if not self.asked and composer_chips.asks_time(answer):
            return [{"type": "offer", "offer": {"kind": "ask", "label": "", "asks": composer_chips.TIME_CHIPS}}]
        #: A social turn ("heyy", "its been hot") has no subject: no statistics chips under it (INBOX 1749).
        social = social_turn(self.question, self.history)
        asks = [] if self.chipped or not answer.strip() or social else self.asks(answer)
        if not asks and not self.offered and answer.strip() and not self.framed and social:
            #: "thanks" has no subject of its own: it offers the last answer's chips (F5).
            asks = composer_chips.resume_chips(self.session, self.history, self.today.isoformat(), self.question)
            #: A hello or thanks with nothing before it has no answer to resume: the starters (L48).
            asks = asks or self._starters()
        return [{"type": "offer", "offer": {"kind": "ask", "label": "", "asks": asks}}] if asks else []

    def _starters(self) -> list[str]:
        """Where to begin, under a bare hello or thanks that follows no answer."""
        from tessellate.ai import question_noise  # lazy: see `social_turn`

        #: Nothing before it offers none (F5, R3: small talk opening a chat stays chip-free), and the starters are
        #: not the generic trio, which a "thanks" never repeats (`composer_chips.GENERIC`).
        if not self.history or question_noise.social_kind(self.question) not in ("greeting", "morning", "thanks"):
            return []
        asked = [self.question, *(str(t.get("question") or "") for t in self.history or [] if isinstance(t, dict))]
        return [c for c in composer_chips.STARTERS if not composer_chips.spent(c, asked)]

    def apply(self, events: list[dict]) -> list[dict]:
        """A whole turn's events with the chips in."""
        text = "".join(str(e.get("delta") or "") for e in events if e.get("type") == "answer")
        out = [self.see(e, text) for e in events]
        return out + self.finish(text)


def stumped_asks(session: Session, history: list[dict], today: date) -> list[str]:
    """The previous subject's acts for the stumped line's chips (INBOX 1729 c); empty with no turn before."""
    prev = from_history(history, today)
    return acts_for(session, prev, today) if history else []

def social_turn(question: str, history: list[dict] | None = None) -> bool:
    """Whether the turn is conversation, not a question about the notes: small
    talk, a remark, a feeling, thanks or a question about Atlas. Such a turn
    has no subject, so no statistics chips sit under it (INBOX 1749). Here, not in `composer_remark`,
    because `intent` asks `composer_remark` whether a turn is a remark: asking `intent` from there was an import
    cycle (code scanning 2175, 2176)."""
    from tessellate.ai import composer_chat, personal, question_noise  # lazy: the composer loads these on first use

    return (
        intent.classify(question) == intent.SMALLTALK
        or composer_remark.is_remark(question)
        or question_noise.social_kind(question) is not None
        or composer_chat.reply(question, history or [], "") is not None
        or bool(personal.about_me(question))
    )
