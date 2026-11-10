"""Comparing, counting and sums over what was just shown (fable-composer-1110 F6).

"Which is higher", "by how much", "total", "which comes first", "how many days between
them", "times 12": each leans on the figures of the answer before it. They are read from
the notes that answer used (the frame's ids, rechecked here, so a deleted or private note
is never reached) and from the days the last few frames named, then computed and said with
both values. Nothing here acts or writes; a turn that is no such ask, or has nothing to
compute from, returns None and the ordinary readers answer.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import composer_frame
from tessellate.core.database import Entry

FRAME_TURNS = 4
_MONTHS = "january february march april may june july august september october november december".split()

_LEAD = r"^(?:(?:and|so|ok|okay|then|now) )*(?:(?:what|how much)(?:'s| is)? )?"
_HIGH = r"higher|highest|bigger|biggest|larger|largest|greater|greatest|more|most|costlier|dearer|longer|longest|faster|fastest|quicker|quickest"
_LOW = r"lower|lowest|smaller|smallest|less|least|fewer|fewest|cheaper|cheapest|shorter|shortest|slower|slowest"
_WHICH = re.compile(rf"^(?:(?:and|so|ok) )*(?:which|what)(?: one| is| was| are| were| of them| of the two)*(?: the)? (?P<w>{_HIGH}|{_LOW})\b")
_DIFF = re.compile(r"\b(?:by how much|the difference|how much (?:more|less|higher|lower|cheaper|longer|faster))\b")
_TOTAL = re.compile(r"\b(?:total|sum|altogether|in all|in total)\b(?: (?:for|of|in) (?:the )?(?P<what>[a-z]+))?")
_NIGHTS = re.compile(r"\bhow many (?P<unit>nights|days)\b.*\b(?:total|altogether|in all|together)\b")
_FIRST = re.compile(r"\bwhich (?:one )?(?:comes|is|was|are|come) (?:first|next|sooner|earlier)\b|\bwhat comes first\b")
_BETWEEN = re.compile(r"\bhow (?:many days|long) (?:are there |is it )?between (?:them|the two|those|these)\b")
_UNTIL = re.compile(r"\bhow (?:many days|long) (?:until|till|to) (?:then|that|it)\b")
_BIRTHDAY = re.compile(r"\bwhose birthday is (?:first|next|soonest|coming up|closest)\b")
_SPENT = re.compile(r"\bhow much (?:did i|have i|do i) (?:spend|spent|pay|paid) on (?:the )?(?P<what>[a-z ]{3,24}?)\??$")
_ABOUT = re.compile(r"^(?:and )?how many (?:notes )?(?:about|mention\w*|on|with) (?:the )?(?P<what>[\w'-]{3,24})\??$")
_CHAIN = re.compile(
    r"^(?:(?:and|now|then|ok|so) )*(?:what(?:'s| is) )?(?:that |it )?(?:(?P<op>times|x|multiplied by|minus|less|take away|subtract|plus|add|divided by|over|"
    r"split(?: that)?(?: between| by| into| among)?|share(?: that)?(?: between| by)?) (?P<n>[\d,.]+)(?: ways)?|(?P<half>half of that|halve that|double that|twice that|a third of that|a quarter of that))\??$"
)
_CALC_LINE = re.compile(r"^[\d$£€(.][^A-Za-z]*?(?: of [\d,.]+)?[^A-Za-z]* is (?P<v>-?[$£€]?[\d,]*\.?\d+)\.?$")
_LINE = re.compile(r"^\s*[-*]?\s*(?P<label>[A-Za-z][A-Za-z &']*?)\s*[:\-]?\s*[$£€]?(?P<n>\d[\d,]*(?:\.\d+)?)\s*$")
_RUN = re.compile(r"(?P<day>\d{1,2} [A-Z][a-z]+):\s*(?P<dist>[\d.]+ ?[a-z]{1,5}) in (?P<t>\d{1,2}:\d{2})")
_STAY = re.compile(r"\b(?P<place>[A-Z][a-z]+) for (?P<n>\d+)(?: nights?)?")
_BIRTH = re.compile(r"birthday is (?P<d>\d{1,2}) (?P<m>[A-Z][a-z]+)")
_BUDGETISH = re.compile(r"budget|cost|spend|expens|bill", re.I)
_WORDS = "zero one two three four five six seven eight nine ten eleven twelve".split()


def _num(value: float) -> str:
    return f"{value:,.0f}" if float(value).is_integer() else f"{value:,.4f}".rstrip("0").rstrip(".")


def _count(n: int) -> str:
    return _WORDS[n].capitalize() if n < len(_WORDS) else str(n)


def _day(d: date, today: date) -> str:
    return f"{d.day} {d:%B}" + ("" if d.year == today.year else f" {d.year}")


def _ahead(d: date, today: date) -> str:
    gap = (d - today).days
    return f"{gap} day{'s' if abs(gap) != 1 else ''} {'away' if gap >= 0 else 'ago'}"


# --- a calculator that keeps its last result -------------------------------------------


def _last_result(history: list[dict]) -> float | None:
    lead = str((history[-1] if history else {}).get("answer") or "").strip().split("\n", 1)[0]
    found = _CALC_LINE.match(lead)
    return float(re.sub(r"[^\d.\-]", "", found.group("v"))) if found else None


def _chained(question: str, history: list[dict]) -> str | None:
    """"times 12" after "650 plus 140": the last result carried on (a half, a double, a split)."""
    found = _CHAIN.match(question)
    last = _last_result(history) if found else None
    if last is None:
        return None
    half = found.group("half")
    if half:
        word, factor = {"half": ("Half", 0.5), "halve": ("Half", 0.5), "double": ("Double", 2), "twice": ("Double", 2)}.get(half.split()[0], ("A third", 1 / 3) if "third" in half else ("A quarter", 0.25))
        return f"{word} of {_num(last)} is {_num(last * factor)}."
    try:
        n = float(found.group("n").replace(",", ""))
    except ValueError:
        return None
    op = found.group("op")
    if op in ("times", "x", "multiplied by"):
        return f"{_num(last)} × {_num(n)} is {_num(last * n)}."
    if op in ("plus", "add"):
        return f"{_num(last)} + {_num(n)} is {_num(last + n)}."
    if op in ("minus", "less", "take away", "subtract"):
        return f"{_num(last)} − {_num(n)} is {_num(last - n)}."
    if not n:
        return "That would divide by zero."
    if op.startswith(("split", "share")):
        return f"{_num(last)} split between {_num(n)} is {_num(last / n)} each."
    return f"{_num(last)} ÷ {_num(n)} is {_num(last / n)}."


# --- the notes the last answer used --------------------------------------------------------


def _frames(history: list[dict]) -> list[dict]:
    return [t["frame"] for t in (history or [])[-FRAME_TURNS:] if isinstance(t, dict) and t.get("frame")]


def _notes(session: Session, ids: list[int]) -> list[Entry]:
    """The frame's notes, read again: deleted and private notes are never reached through client ids."""
    rows = session.scalars(select(Entry).where(Entry.id.in_(ids), Entry.is_deleted == False, Entry.is_private == False)).all()  # noqa: E712
    order = {i: n for n, i in enumerate(ids)}
    return sorted(rows, key=lambda e: order[e.id])


def _all_notes(session: Session) -> list[Entry]:
    return list(session.scalars(select(Entry).where(Entry.is_deleted == False, Entry.is_private == False).order_by(Entry.created_at.desc())).all())  # noqa: E712


def _name_of(entry: Entry) -> str:
    return composer_frame.note_title(entry.content) or "Untitled"


def _amounts(entry: Entry) -> dict[str, tuple[str, float]]:
    """"Rent 650. Groceries 140." in a note titled budget, costs or spending: label -> (label, amount)."""
    if not _BUDGETISH.search(_name_of(entry)):
        return {}
    body = (entry.content or "").split("\n", 1)[-1]
    out: dict[str, tuple[str, float]] = {}
    for chunk in re.split(r"[.;\n]", body):
        found = _LINE.match(chunk)
        if found:
            label = found.group("label").strip()
            out.setdefault(label.lower(), (label, float(found.group("n").replace(",", ""))))
    return out if len(out) >= 2 else {}


def _word(entry: Entry, word: str) -> bool:
    return bool(word) and word.lower() in (entry.content or "").lower()


# --- budgets: compare, difference, total, spend ----------------------------------------------


def _total_of(amounts: dict) -> float:
    return sum(v for _l, v in amounts.values())


def _budget_compare(budgets: list[tuple[Entry, dict]], dirn: str | None) -> str:
    older, newer = sorted(budgets, key=lambda b: b[0].created_at)[:2]
    (eo, ao), (en, an) = older, newer
    to, tn = _total_of(ao), _total_of(an)
    high = dirn is None or re.fullmatch(_HIGH, dirn) is not None
    first, second = (eo, en) if (to >= tn) == high else (en, eo)
    f_total, s_total = (to, tn) if first is eo else (tn, to)
    word = "higher" if high else "lower"
    lead = f"{_name_of(first)} is {word} overall, {_num(f_total)} against {_num(s_total)} for {_name_of(second)}." if to != tn else f"Both come to {_num(to)}."
    moves = []
    for key, (label, then) in ao.items():
        if key in an and an[key][1] != then:
            now = an[key][1]
            moves.append(f"{label.lower()} {'rose' if now > then else 'fell'} from {_num(then)} to {_num(now)}")
    return f"{lead} From {_name_of(eo)} to {_name_of(en)}, {'; '.join(moves)}." if moves else lead


def _budget_total(entry: Entry, amounts: dict) -> str:
    parts = ", ".join(f"{label.lower()} {_num(v)}" for label, v in amounts.values())
    return f"{_name_of(entry)} comes to {_num(_total_of(amounts))}: {parts}."


def _budget_answer(question: str, budgets: list[tuple[Entry, dict]]) -> str | None:
    which, diff = _WHICH.match(question), _DIFF.search(question)
    if (which or diff) and len(budgets) >= 2:
        totals = sorted(_total_of(a) for _e, a in budgets[:2])
        if diff and not which:
            return f"By {_num(totals[1] - totals[0])}, {_num(totals[1])} against {_num(totals[0])}."
        return _budget_compare(budgets, which.group("w") if which else None)
    if _TOTAL.search(question) and budgets:
        return " ".join(_budget_total(e, a) for e, a in budgets[:2])
    return None


def _budgets(entries: list[Entry]) -> list[tuple[Entry, dict]]:
    return [(e, a) for e in entries if (a := _amounts(e))]


def _spent(session: Session, what: str) -> str | None:
    """"How much did I spend on groceries": the label in every budget note that has it."""
    stem = what.strip().rstrip("s")[:6]
    rows = [(e, a[key][1]) for e, a in _budgets(_all_notes(session)) for key in a if key.startswith(stem)]
    if not rows:
        return None
    label = next(a[k][0] for _e, a in _budgets(_all_notes(session)) for k in a if k.startswith(stem))
    parts = ", ".join(f"{_num(v)} in {_name_of(e)}" for e, v in rows)
    return f"{label}: {parts}" + (f"; {_num(sum(v for _e, v in rows))} together." if len(rows) > 1 else ".")


def _total_for(session: Session, what: str) -> str | None:
    """"Total for november": the budget notes that name the word."""
    found = [(e, a) for e, a in _budgets(_all_notes(session)) if _word(e, what)]
    return " ".join(_budget_total(e, a) for e, a in found[:2]) or None


# --- runs and stays ----------------------------------------------------------------------------


def _seconds(clock: str) -> int:
    m, s = clock.split(":")
    return int(m) * 60 + int(s)


def _runs_answer(question: str, entries: list[Entry]) -> str | None:
    which, diff = _WHICH.match(question), _DIFF.search(question)
    if not (which or diff):
        return None
    runs = sorted({(m.group("day"), m.group("dist"), m.group("t")) for e in entries for m in _RUN.finditer(e.content or "")}, key=lambda r: _seconds(r[2]))
    runs = [r for r in runs if r[1] == runs[0][1]] if runs else []
    if len(runs) < 2:
        return None
    (day_a, dist, t_a), (day_b, _dist, t_b) = runs[0], runs[-1]
    gap = _seconds(t_b) - _seconds(t_a)
    if which and which.group("w") in ("slower", "slowest"):
        return f"{day_b} was slower: {dist} in {t_b}, against {t_a} on {day_a}."
    return f"{day_a} was faster: {dist} in {t_a}, against {t_b} on {day_b}, {gap} seconds quicker."


def _stays_answer(question: str, entries: list[Entry]) -> str | None:
    stays: list[tuple[str, int]] = []
    for entry in entries:
        for sentence in re.split(r"(?<=[.!?])\s+", entry.content or ""):
            if "night" in sentence:
                stays += [(m.group("place"), int(m.group("n"))) for m in _STAY.finditer(sentence)]
    if len(stays) < 2:
        return None
    parts = ", ".join(f"{p} {n}" for p, n in stays)
    if _NIGHTS.search(question) or _TOTAL.search(question):
        return f"{sum(n for _p, n in stays)} nights in all: {parts}."
    which = _WHICH.match(question)
    if which:
        pick = max(stays, key=lambda s: s[1]) if re.fullmatch(_HIGH, which.group("w")) else min(stays, key=lambda s: s[1])
        return f"{pick[0]} is the {'longest' if pick is max(stays, key=lambda s: s[1]) else 'shortest'} stay, {pick[1]} nights ({parts})."
    return None


# --- days named by the last answers --------------------------------------------------------------


def _events(session: Session, history: list[dict]) -> list[tuple[str, date]]:
    """(name, day) for the day each recent answer led with, oldest first, one per day."""
    seen: dict[date, str] = {}
    for frame in _frames(history):
        if not frame.get("dates") or not frame.get("note_ids"):
            continue
        found = _notes(session, frame["note_ids"][:1])
        if found:
            seen[datetime.strptime(frame["dates"][0], "%Y-%m-%d").date()] = _name_of(found[0])
    return [(name, d) for d, name in seen.items()]


def _dates_answer(question: str, events: list[tuple[str, date]], today: date) -> str | None:
    ordered = sorted(events, key=lambda e: e[1])
    if _UNTIL.search(question) and events:
        name, d = events[-1]
        return f"{name} is {_ahead(d, today)}, on {_day(d, today)}."
    if len(ordered) < 2 or not (_FIRST.search(question) or _BETWEEN.search(question) or _WHICH.match(question)):
        return None
    if _BETWEEN.search(question):
        gaps = [f"{b[1].toordinal() - a[1].toordinal()} days from {a[0]} to {b[0]}" for a, b in zip(ordered, ordered[1:])]
        return "; ".join(gaps)[:1].upper() + "; ".join(gaps)[1:] + "."
    first, rest = ordered[0], ordered[1:]
    tail = " and ".join(f"{n} on {_day(d, today)}" for n, d in rest)
    return f"{first[0]} comes first, on {_day(first[1], today)}, {_ahead(first[1], today)}. Then {tail}."


def _birthdays(session: Session, today: date) -> str | None:
    found = []
    for entry in _all_notes(session):
        m = _BIRTH.search(entry.content or "")
        if not m or m.group("m").lower() not in _MONTHS:
            continue
        month, day = _MONTHS.index(m.group("m").lower()) + 1, int(m.group("d"))
        nxt = date(today.year, month, day)
        found.append((_name_of(entry), nxt if nxt >= today else date(today.year + 1, month, day)))
    found.sort(key=lambda f: f[1])
    if len(found) < 2:
        return None
    (n1, d1), (n2, d2) = found[0], found[1]
    return f"{n1}'s is first, on {_day(d1, today)}, {_ahead(d1, today)}. {n2}'s follows on {_day(d2, today)}."


def _tagged(entry: Entry, tag: str) -> bool:
    return tag.lower() in {str(t).lower() for t in json.loads(entry.tags or "[]")}


def _how_many_about(session: Session, what: str, history: list[dict]) -> str | None:
    """"How many about harbor" right after a count: the notes tagged with it and the notes that say it."""
    if not history or not re.search(r"\bhow many\b", str(history[-1].get("question") or "").lower()):
        return None
    notes = _all_notes(session)
    tagged, said = sum(_tagged(e, what) for e in notes), sum(_word(e, what) for e in notes)
    if not said:
        return None
    plural = "s" if said != 1 else ""
    if tagged and tagged != said:
        return f"{_count(tagged)} note{'s' if tagged != 1 else ''} tagged {what}, and {_count(said).lower()} that mention it."
    return f"{_count(said)} note{plural} mention{'' if plural else 's'} {what}."


# --- the entry --------------------------------------------------------------------------------------


def _from_notes(session: Session, question: str, history: list[dict]) -> str | None:
    frames = _frames(history)
    entries = _notes(session, list(dict.fromkeys(i for f in reversed(frames) for i in f["note_ids"]))[:6]) if frames else []
    last = _notes(session, frames[-1]["note_ids"]) if frames else []
    return (_budget_answer(question, _budgets(last)) if last else None) or _runs_answer(question, last) or _stays_answer(question, entries or last)


def _cold(session: Session, question: str, history: list[dict], today: date) -> str | None:
    """Asks that need no answer before them: a birthday order, a count, a spend, a total for a named month."""
    if _BIRTHDAY.search(question):
        return _birthdays(session, today)
    if (about := _ABOUT.match(question)) and (said := _how_many_about(session, about.group("what"), history)):
        return said
    if spent := _SPENT.search(question):
        return _spent(session, spent.group("what"))
    total = _TOTAL.search(question)
    #: Only a month names a budget here ("total for november"); "total of the budget" is the money reader's.
    named = total.group("what") if total and total.group("what") in _MONTHS else None
    return _total_for(session, named) if named else None


def answer(session: Session, typed: str, history: list[dict] | None, today: date) -> str | None:
    """What this turn computes from the figures the answers before it showed, or None."""
    question = " ".join(str(typed or "").lower().replace("?", " ").replace("’", "'").split())
    history = list(history or [])
    if not question:
        return None
    if (chained := _chained(question, history)) is not None:
        return chained
    if said := _cold(session, question, history, today):
        return said
    if not history:
        return None
    return _dates_answer(question, _events(session, history), today) or _from_notes(session, question, history)
