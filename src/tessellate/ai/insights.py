"""Patterns in the notes, measured, with a fixed hedge (CHAT_PLAN Phase 6,
decision 32): never a claim about the person, always a count over their own
notes, said with one tested phrase that fires only on its rule.

"You have written about golf 4 times since 5 September, three of them after
work; that may be a hobby forming." Every slot of every template is a count,
a date or the person's own words (`composer_tables.INSIGHT_TEMPLATES`; a lint
in `tests/test_insights.py` holds it), so the sentence is re-derived from the
notes by running the rule again, which is what the eval does.

The rules, each a function over the notes and their facts (`factgraph`):

- recurrence: a subject in at least 3 notes across at least 3 weeks;
- streak: a subject written about in at least 3 consecutive weeks;
- drift: a plan at least 30 days old with no later note on it;
- contrast: a preference, then a later one the other way about the same thing;
- load: a week with at least twice the median count of notes (and 4 or more);
- time of day: at least 3 of a subject's notes say "after work", "in the
  evening" or "before work", "in the morning".

Insights close a broad answer and make the Patterns line (Tidy and the
dashboard, `routes_insights`); they are never filed as facts on their own.

Confirm and Not right (decision 60). Every insight line carries both.
Confirm writes a fact the person vouched for (a `derived_facts` row of kind
"confirmed", model "you"), said from then on as their own word, never
re-hedged: "Golf is a hobby of yours, as you told me on 10 October." Not
right records a "dismiss_insight" correction; that insight and its
near-variants (the same rule about the same subject, whatever the count or
the dates) are not shown again. `key` is what makes two lines variants.

Done (INBOX 1412). A plan line also carries a third verdict: the plan is
finished. It removes the confirmed fact (soft delete) and records a
"dismiss_insight" of reason "done", so the plan and its variants never show
again, said once as "Marked done". A later note sharing the plan's words
(the rule `drift` already uses) retires a confirmed drift fact the same way
(`retire_followed`), so "still open" is not said after the owner wrote it was done.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from statistics import median

from tessellate.ai import composer_tables, recognise

#: The thresholds each rule fires on (decision 32): below them, silence.
MIN_NOTES = 3
MIN_WEEKS = 3
DRIFT_DAYS = 30
LOAD_FACTOR = 2.0
LOAD_MIN = 4
TIME_OF_DAY_MIN = 3

_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
#: Words that say a subject is something done for its own sake: a session, a
#: round, practice, a game. With one of them, a recurring subject "may be a
#: hobby forming"; without, it "keeps coming up".
_LEISURE = re.compile(r"\b(?:after work|weekend|session|round|practi[cs]e|played|game|class|lesson|hobby|for fun|drills?)\b", re.I)
#: Study and paid work are duties, never "a hobby forming", whatever their
#: "class" or "session" (INBOX 1461: uni notes were called a hobby). Not
#: "course": a golf course is free time.
_DUTY = re.compile(r"\b(?:uni|university|lectures?|exams?|assignments?|semester|coursework|stud(?:y|ies|ying)|subjects?|tutorials?|homework|"
                   r"essays?|degree|school|college|shifts?|deadlines?|clients?|meetings?)\b", re.I)


@dataclass
class Insight:
    """One measured line: its rule, its sentence, and the notes it rests on."""

    rule: str
    text: str
    note_ids: list[int] = field(default_factory=list)
    #: The slot values, typed (count, date, quoted), for the lint and the eval.
    slots: dict = field(default_factory=dict)


def _day(day: date, today: date) -> str:
    if day.year == today.year:
        return f"{day.day} {_MONTHS[day.month - 1]}"
    return f"{day.day} {_MONTHS[day.month - 1]} {day.year}"


def _count_word(n: int) -> str:
    words = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve")
    return words[n] if 0 <= n < len(words) else str(n)


def _capital(subject: object) -> str:
    said = str(subject)
    return said[:1].upper() + said[1:]


def _written(note: dict) -> date | None:
    raw = str(note.get("created_at") or "")
    try:
        return date.fromisoformat(raw[:10]) if re.match(r"\d{4}-\d{2}-\d{2}", raw) else None
    except ValueError:
        return None


def _holds(note: dict, subject: str) -> bool:
    words = subject.lower().split()
    text = (str(note.get("content") or "") + " " + " ".join(str(t) for t in note.get("tags") or [])).lower()
    return all(re.search(rf"\b{re.escape(w)}", text) for w in words)


def _week(day: date) -> tuple[int, int]:
    iso = day.isocalendar()
    return iso[0], iso[1]


#: "want to see Kyoto and Nara" is a verb phrase; "no later note picks up want to see ..." reads broken (audit 1030 Z7).
_PLAN_LEAD = re.compile(r"^(?:(?:i|we)(?:'m|'re| am| are)?\s+)?(?:(?:want|wants|wanted|plan|plans|planned|planning|hope|hopes|hoped|hoping|intend|intends|need|needs|needed|have|has)\s+to|(?:should|must)|(?:am |are |is )?going to)\s+(?=\S)", re.I)


def _plan_phrase(plan: str, shown: str) -> str:
    """The plan as a noun phrase ("your plan to see Kyoto and Nara"); anything else, or words quoted as
    typed, keeps its words after "this plan:"."""
    lead = _PLAN_LEAD.match(plan)
    return f"your plan to {plan[lead.end():]}" if lead and shown == plan else f"this plan: {shown}"


def _shown(rule: str, slots: dict) -> dict:
    """The slots as the sentence says them: a recurrence's subject with its capital and its count in
    words (G12), the slot values themselves staying typed for the lint and Confirm."""
    if rule != "recurrence":
        from tessellate.ai import composer_story

        shown = {k: composer_story.quoted_if_slang(v) if composer_tables.INSIGHT_SLOTS.get(k) == "span" else v for k, v in slots.items()}
        return {**shown, "plan": _plan_phrase(str(slots["plan"]), str(shown["plan"]))} if rule == "drift" else shown
    return {**slots, "subject": _capital(slots["subject"]), "count": _count_word(int(slots["count"]))}


def _fill(rule: str, slots: dict) -> str:
    return composer_tables.INSIGHT_TEMPLATES[rule].format(**_shown(rule, slots))


def shown(rule: str, slots: dict) -> dict:
    """`_shown` for the eval, which fills the template from a row's own numbers."""
    return _shown(rule, slots)


def listed(found: list["Insight"]) -> list[str]:
    """The sentences of a list of insights, each recurrence's hedge said once: the same "that keeps
    coming up" three times in a row reads as a stamp (G12)."""
    said: set[str] = set()
    lines = []
    for item in found:
        hedge = str(item.slots.get("hedge") or "")
        tail = f"; {hedge}."
        if item.rule == "recurrence" and hedge in said and item.text.endswith(tail):
            lines.append(f"{item.text[: -len(tail)]}.")
            continue
        if item.rule == "recurrence":
            said.add(hedge)
        lines.append(item.text)
    return lines


def _leisure(notes: list[dict]) -> bool:
    """Whether the notes read as free time: a class or a session, and no
    study or paid work (INBOX 1461)."""
    texts = [f"{n.get('content') or ''} {n.get('category') or ''}" for n in notes]
    return any(_LEISURE.search(t) for t in texts) and not any(_DUTY.search(t) for t in texts)


def recurrence(subject: str, notes: list[dict], today: date) -> Insight | None:
    """`subject` in at least `MIN_NOTES` notes across at least `MIN_WEEKS`
    weeks: how many, since when, how many of them after work, and a hedge."""
    dated = sorted(((d, n) for n in notes if _holds(n, subject) and (d := _written(n))), key=lambda pair: pair[0])
    if len(dated) < MIN_NOTES or len({_week(d) for d, _ in dated}) < MIN_WEEKS:
        return None
    after = sum(1 for _d, n in dated if recognise.part_of_day(str(n.get("content") or "")) == "evening")
    leisure = _leisure([n for _d, n in dated])
    slots = {
        "subject": subject,
        "count": len(dated),
        "since": _day(dated[0][0], today),
        "after": f", {_count_word(after)} of them after work" if after >= TIME_OF_DAY_MIN else "",
        "hedge": composer_tables.INSIGHT_HEDGES["hobby" if leisure else "recurs"],
    }
    return Insight("recurrence", _fill("recurrence", slots), [n["id"] for _d, n in dated], slots)


def streak(subject: str, notes: list[dict], today: date) -> Insight | None:
    """`subject` written about in at least `MIN_WEEKS` consecutive weeks,
    ending this week or last."""
    weeks = sorted({_week(d) for n in notes if _holds(n, subject) and (d := _written(n))})
    if not weeks:
        return None
    run = 1
    last = weeks[-1]
    for earlier, later in zip(reversed(weeks[:-1]), reversed(weeks[1:])):
        gap = (date.fromisocalendar(later[0], later[1], 1) - date.fromisocalendar(earlier[0], earlier[1], 1)).days
        if gap != 7:
            break
        run += 1
    this_week = _week(today)
    last_week = _week(today - timedelta(days=7))
    if run < MIN_WEEKS or last not in (this_week, last_week):
        return None
    slots = {"subject": subject, "weeks": run}
    ids = [n["id"] for n in notes if _holds(n, subject) and _written(n)]
    return Insight("streak", _fill("streak", slots), ids, slots)


#: The subject just before a plan's words: a pronoun for someone else, or a
#: name ("Daniel wants to ...").
_OTHERS_PLAN = re.compile(r"(?:\b(?:[Hh]e|[Ss]he|[Tt]hey|[Ww]e)|\b(?!I\b)[A-Z][a-z]+)\s+$")


def _own_plan(note: dict, fact) -> bool:  # noqa: ANN001
    """A plan the writer stated. "He wants to try the crag" is another
    person's, said as the writer's ("this plan: wants to try ...", INBOX 1301 D5)."""
    if fact.kind != "plan" or fact.mode != "asserted":
        return False
    return not _OTHERS_PLAN.search(str(note.get("content") or "")[: fact.start])


def _followed_up(notes: list[dict], note: dict, written: date, words: list[str]) -> bool:
    """Whether a later note mentions at least half of the plan's words."""
    need = (len(words) + 1) // 2
    for other in notes:
        if other is note or not (day := _written(other)) or day <= written:
            continue
        content = str(other.get("content") or "").lower()
        if sum(1 for w in words if re.search(rf"\b{w}", content)) >= need:
            return True
    return False


def drift(notes: list[dict], today: date) -> list[Insight]:
    """Plans at least `DRIFT_DAYS` old that no later note follows up: the
    plan's own words, quoted, and the day it was written."""
    from tessellate.ai import factgraph

    out: list[Insight] = []
    for note in notes:
        written = _written(note)
        if written is None or (today - written).days < DRIFT_DAYS:
            continue
        for fact in factgraph.facts(note):
            if not _own_plan(note, fact):
                continue
            words = [w for w in re.findall(r"[a-z]{4,}", fact.attrs.get("object", "").lower()) if w not in _PLAIN]
            if not words:
                continue
            if _followed_up(notes, note, written, words):
                continue
            slots = {"plan": fact.text, "since": _day(written, today)}
            out.append(Insight("drift", _fill("drift", slots), [note["id"]], slots))
    return out


def contrast(notes: list[dict], today: date) -> list[Insight]:
    """A preference, then a later note the other way about the same object."""
    from tessellate.ai import factgraph

    said = []
    for note in notes:
        written = _written(note)
        if written is None:
            continue
        said.extend((written, note, fact) for fact in factgraph.facts(note)
                    if fact.kind == "preference" and fact.attrs.get("object"))
    said.sort(key=lambda row: row[0])
    out: list[Insight] = []
    for i, (first_day, first_note, first) in enumerate(said):
        target = set(re.findall(r"[a-z]{4,}", first.attrs["object"].lower())) - _PLAIN
        for later_day, later_note, later in said[i + 1:]:
            if later_day <= first_day or later.attrs.get("polarity") == first.attrs.get("polarity"):
                continue
            if target & set(re.findall(r"[a-z]{4,}", later.attrs["object"].lower())):
                slots = {"first": _day(first_day, today), "before": first.text, "last": _day(later_day, today), "after_said": later.text}
                out.append(Insight("contrast", _fill("contrast", slots), [first_note["id"], later_note["id"]], slots))
                break
    return out


def load(notes: list[dict], today: date) -> Insight | None:
    """The busiest week, when it had at least twice the median week's notes."""
    weeks = Counter(_week(d) for n in notes if (d := _written(n)))
    if len(weeks) < 3:
        return None
    (year, week), most = weeks.most_common(1)[0]
    usual = median(weeks.values())
    if most < LOAD_MIN or most < LOAD_FACTOR * usual:
        return None
    monday = date.fromisocalendar(year, week, 1)
    slots = {"week": _day(monday, today), "count": most, "usual": int(usual) if float(usual).is_integer() else round(usual, 1)}
    ids = [n["id"] for n in notes if (d := _written(n)) and _week(d) == (year, week)]
    return Insight("load", _fill("load", slots), ids, slots)


_PLAIN = frozenset(
    """that this with have from your will they them what when then than there their about would could should into
    week weeks times time days month months year years three four five every each next again""".split()
)


#: A question that asks after regularity ("any patterns in my running notes",
#: "how often do I write about chess") is answered by the streak when one holds.
REGULAR = re.compile(r"\b(?:patterns?|habits?|trends?|streaks?|regular(?:ly)?|how often|every week|weekly)\b", re.I)


def for_subject(subject: str, notes: list[dict], today: date, question: str = "") -> list[Insight]:
    """The insights a broad answer about `subject` may close with, best first:
    a recurrence, else a streak; a streak first when `question` asks after
    regularity (`REGULAR`)."""
    run = streak(subject, notes, today)
    if run and REGULAR.search(question or ""):
        return [run]
    found = recurrence(subject, notes, today)
    if found:
        return [found]
    return [run] if run else []


#: The short form of each rule for the dashboard's line ("golf came up 4 times since
#: 5 September"), from the same slots: a count, a date, a subject.
def short(insight: Insight) -> str:
    slots = insight.slots
    if insight.rule == "recurrence":
        #: The subject with its capital and the count in words (G12).
        return f"{_capital(slots['subject'])} came up {_count_word(int(slots['count']))} times since {slots['since']}"
    if insight.rule == "streak":
        return f"{_capital(slots['subject'])} every week for {_count_word(int(slots['weeks']))} weeks"
    if insight.rule == "drift":
        return f"a plan from {slots['since']} still open"
    if insight.rule == "contrast":
        return f"a change of mind since {slots['first']}"
    return f"a busy week from {slots['week']}"


def after_lead(insight: Insight) -> str:
    """A recurrence said after a lead that gave its count and dates ("At least
    four of your notes mention golf, from 5 to 30 September"): only what the
    lead did not say (CHAT_PLAN decision 52, one fact once). "Three of them
    after work; that may be a hobby forming."; "" when there is nothing new, since "That keeps coming up."
    only said the count again (fable-composer-1110 F7.3)."""
    hedge = str(insight.slots.get("hedge") or "")
    after = str(insight.slots.get("after") or "").lstrip(", ")
    if after:
        return f"{after[:1].upper()}{after[1:]}; {hedge}."
    return "" if hedge == composer_tables.INSIGHT_HEDGES["recurs"] else f"{hedge[:1].upper()}{hedge[1:]}."


#: How many of the newest notes the Patterns line reads: the patterns worth a
#: line are recent ones, and a notebook of thousands is read in a moment.
NOTEBOOK_NOTES = 300


def from_session(session, today: date, limit: int = 3) -> list[Insight]:  # noqa: ANN001
    """The Patterns line over the notebook's newest notes (Tidy, the
    dashboard; `routes_insights.patterns`). Private and binned notes are
    never read."""
    from sqlalchemy import select

    from tessellate.core.database import Entry
    from tessellate.entry import manager

    rows = session.scalars(
        select(Entry)
        .where(Entry.is_deleted == False, Entry.is_private == False)  # noqa: E712
        .order_by(Entry.created_at.desc())
        .limit(NOTEBOOK_NOTES)
    ).all()
    notes = [
        {"id": e.id, "content": e.content or "", "created_at": e.created_at.date().isoformat() if e.created_at else "", "tags": manager.entry_tags(e)}
        for e in rows
    ]
    retire_followed(session, notes, today)
    known = memory(session)
    return [i for i in notebook(notes, today, limit + len(known.dismissed)) if key(i) not in known.dismissed][:limit]


# --- Confirm and Not right (decision 60) ---------------------------------------------------


def _stems(text: str) -> str:
    words = re.findall(r"[a-z0-9]+", str(text or "").lower())
    return " ".join(sorted({w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words}))


def key(insight: Insight) -> str:
    """What makes two insight lines one insight: the rule and what it is
    about, never the count or the dates, so "golf, 4 times" and "golf, 5
    times" are near-variants and a dismissal of one is a dismissal of both."""
    slots = insight.slots
    about = {"recurrence": "subject", "streak": "subject", "drift": "plan", "contrast": "before"}.get(insight.rule)
    if about:
        return f"{insight.rule}:{_stems(slots.get(about, ''))}"
    return f"{insight.rule}:{slots.get('week', '')}"


def _said(insight: Insight) -> str:
    """The insight as a statement, without its hedge: what Confirm vouches for."""
    slots = insight.slots
    subject = str(slots.get("subject") or "")
    named = subject[:1].upper() + subject[1:]
    if insight.rule == "recurrence":
        hobby = slots.get("hedge") == composer_tables.INSIGHT_HEDGES["hobby"]
        return f"{named} is {'a hobby' if hobby else 'a regular subject'} of yours"
    if insight.rule == "streak":
        return f"You write about {subject} every week"
    if insight.rule == "drift":
        return f"This plan is still open: {slots.get('plan', '')}"
    if insight.rule == "contrast":
        return f"You changed your mind: {slots.get('after_said', '')}"
    return f"The week of {slots.get('week', '')} was a busy week"


def confirmed_line(said: str, on: date) -> str:
    """The person's own word, with its source, as a person says it (INBOX
    1483, the owner: "(confirmed by you, 11 October)" read as a record):
    "Golf is a hobby of yours, as you told me on 10 October."."""
    return f"{said.rstrip('.')}, as you told me on {on.day} {_MONTHS[on.month - 1]}."


#: A line confirmed before INBOX 1483, stored as it was said then.
_OLD_CONFIRMED = re.compile(r"^(?P<said>.*?) \(confirmed by you, (?P<on>\d{1,2} [A-Z][a-z]+)\)\.$")


def _said_now(line: str) -> str:
    """A stored confirmed line in today's words: "X (confirmed by you, 10
    October)." is "X, as you told me on 10 October."."""
    old = _OLD_CONFIRMED.match(line or "")
    return f"{old['said']}, as you told me on {old['on']}." if old else line


@dataclass
class Memory:
    """What the person said about insights: the keys they dismissed, and the
    ones they confirmed with the line each is now said as."""

    dismissed: frozenset = frozenset()
    confirmed: dict = field(default_factory=dict)

    def subjects(self) -> dict[str, str]:
        """Confirmed subjects (as `key` writes them) and their lines."""
        return {k.split(":", 1)[1]: v["line"] for k, v in self.confirmed.items() if k.split(":", 1)[0] in ("recurrence", "streak")}


CONFIRMED_KIND = "confirmed"


def memory(session) -> Memory:  # noqa: ANN001
    """The confirmations (`derived_facts`, kind "confirmed", not deleted) and
    the dismissals (`learning`, "dismiss_insight") of this notebook."""
    from tessellate.ai import learning

    dismissed = {str(c.subject.get("key") or "") for c in learning.corrections(session, "dismiss_insight")}
    confirmed: dict[str, dict] = {}
    for row in shown_confirmed(session):
        payload = _payload(row)
        if payload.get("key"):
            info = {"line": _said_now(row.text), "id": row.id, "measured": payload.get("measured", ""), "note_ids": payload.get("note_ids") or [],
                    "subject": payload.get("subject", "")}
            #: A subject the person renamed (B9) answers under its new word
            #: too; newest first, so the newest row holds a shared key.
            for the_key in _keys(payload):
                confirmed.setdefault(the_key, info)
    return Memory(frozenset(dismissed - set(confirmed)), confirmed)


def _keys(payload: dict) -> list[str]:
    """Every key a confirmed fact answers under: its own and the subject it was renamed to."""
    return [k for k in (payload.get("key"), *payload.get("aliases", [])) if k]


def _confirmed_rows(session, *, removed: bool = False, fact_id: int | None = None) -> list:  # noqa: ANN001
    """Confirmed facts (or removed ones) the person can open, newest first:
    at least one note the pattern rests on is not binned, not private and in
    this space (the workspace filter rides on `Entry`). Any one, not the
    newest (`entry_id`): binning one golf note of four keeps its
    confirmation (review of B9). All of them hidden
    takes the pattern with them (`facts._visible`'s rule)."""
    from sqlalchemy import select

    from tessellate.core.database import DerivedFact, Entry

    gone = DerivedFact.deleted_at.is_not(None) if removed else DerivedFact.deleted_at.is_(None)
    query = select(DerivedFact).where(DerivedFact.kind == CONFIRMED_KIND, gone)
    if fact_id is not None:
        query = query.where(DerivedFact.id == fact_id)
    rows = list(session.scalars(query.order_by(DerivedFact.computed_at.desc(), DerivedFact.id.desc())))
    rests_on = {row.id: {int(i) for i in _payload(row).get("note_ids") or []} | {row.entry_id} for row in rows}
    wanted = set().union(*rests_on.values()) if rows else set()
    can_open = set(session.scalars(select(Entry.id).where(Entry.id.in_(wanted), Entry.is_deleted.is_(False), Entry.is_private.is_(False)))) if wanted else set()
    return [row for row in rows if rests_on[row.id] & can_open]


def _from_payload(body: dict) -> Insight:
    return Insight(str(body.get("rule") or ""), str(body.get("text") or ""), [int(i) for i in body.get("note_ids") or []], dict(body.get("slots") or {}))


def confirm(session, body: dict, today: date) -> dict:  # noqa: ANN001
    """Confirm: the insight becomes a fact the person vouched for, with the
    measurement it came from, on the newest note it rests on."""
    import json

    from tessellate.ai import learning
    from tessellate.core.database import DerivedFact

    insight = _from_payload(body)
    if not insight.note_ids or not insight.rule:
        raise ValueError("That insight names no notes, so there is nothing to confirm.")
    the_key = key(insight)
    #: A second Confirm on a pattern already confirmed is that fact, not a
    #: copy of it (two identical rows in What it learned, the review of B9).
    known = memory(session).confirmed.get(the_key)
    if known:
        return {"id": known["id"], "key": the_key, "line": known["line"]}
    line = confirmed_line(_said(insight), today)
    #: Not an edit: the sentence is the person's own from the start, so Reset
    #: (offered only once they edit it in Settings) puts this sentence back,
    #: never the measurement, which the payload keeps.
    row = DerivedFact(
        entry_id=max(insight.note_ids), kind=CONFIRMED_KIND, text=line, model="you", confidence=1.0,
        payload=json.dumps({"key": the_key, "rule": insight.rule, "measured": insight.text, "note_ids": insight.note_ids,
                            "source": f"confirmed by you, {today.isoformat()}"}),
    )
    session.add(row)
    learning.record(session, kind="confirm_insight", subject={"key": the_key, "entry_id": max(insight.note_ids)}, to_value=line, excerpt=insight.text)
    session.flush()
    return {"id": row.id, "key": the_key, "line": line}


def dismiss(session, body: dict) -> dict:  # noqa: ANN001
    """Not right: this insight and its near-variants are not shown again."""
    from tessellate.ai import learning

    insight = _from_payload(body)
    if not insight.rule:
        raise ValueError("That is not an insight the notes measured.")
    the_key = key(insight)
    learning.record(session, kind="dismiss_insight", subject={"key": the_key}, from_value=insight.text, excerpt=insight.text)
    return {"key": the_key}


def _retire(session, keys: set[str]) -> int:  # noqa: ANN001
    """Soft-delete the confirmed facts under these keys; how many went."""
    import json

    from sqlalchemy import select

    from tessellate.core.database import DerivedFact, utcnow

    gone = 0
    for row in session.scalars(select(DerivedFact).where(DerivedFact.kind == CONFIRMED_KIND, DerivedFact.deleted_at.is_(None))):
        try:
            the_key = json.loads(row.payload or "{}").get("key")
        except ValueError:
            continue
        if the_key in keys:
            row.deleted_at = utcnow()
            gone += 1
    return gone


def done(session, body: dict) -> dict:  # noqa: ANN001
    """Done: the plan is finished. The confirmed fact (if any) is removed and
    the plan, with its variants, is never shown again."""
    from tessellate.ai import learning

    insight = _from_payload(body)
    if insight.rule != "drift":
        raise ValueError("Only a plan can be marked done.")
    the_key = key(insight)
    _retire(session, {the_key})
    learning.record(session, kind="dismiss_insight", subject={"key": the_key, "reason": "done"}, from_value=insight.text, excerpt=insight.text)
    session.flush()
    return {"key": the_key, "said": "Marked done"}


def retire_followed(session, notes: list[dict], today: date) -> int:  # noqa: ANN001
    """A confirmed "still open" plan that a later note now follows up (the
    words `drift` matches on) is no longer said: its fact is removed. Needs
    the plan's own note among `notes`, so a limited window never retires it."""
    known = memory(session)
    open_keys = {key(i) for i in drift(notes, today)}
    ids = {n["id"] for n in notes}
    stale = set()
    for the_key, info in known.confirmed.items():
        if not the_key.startswith("drift:") or the_key in open_keys:
            continue
        if info.get("note_ids") and all(i in ids for i in info["note_ids"]):
            stale.add(the_key)
    return _retire(session, stale) if stale else 0


def as_row(insight: Insight, known: Memory | None = None) -> dict:
    """An insight for a page: its line, its key, and whether it is confirmed
    (then its line is the confirmed one, and its menu is Edit, Remove and
    Not right on `confirmed_id`, B9)."""
    the_key = key(insight)
    confirmed = known.confirmed.get(the_key) if known else None
    return {
        "rule": insight.rule, "key": the_key, "text": confirmed["line"] if confirmed else insight.text,
        "short": short(insight), "note_ids": insight.note_ids, "slots": insight.slots, "confirmed": bool(confirmed),
        "confirmed_id": confirmed["id"] if confirmed else None, "confirmed_subject": confirmed.get("subject", "") if confirmed else "",
    }


# --- Managing what was confirmed (CHAT_PLAN B9) -------------------------------------------

#: A confirmed line's tail, as `confirmed_line` writes it.
_TOLD = re.compile(r"^(?P<said>.*), as you told me on (?P<on>\d{1,2} [A-Z][a-z]+)\.$", re.S)
#: The rules whose key is a subject the person may rename.
SUBJECT_RULES = ("recurrence", "streak")
#: That tail typed into Edit (any case, after a comma or a stop): the day is
#: the one it was first confirmed, said once.
_TOLD_TYPED = re.compile(r"[\s,.;]*as you told me on \d{1,2} [A-Za-z]+[\s.]*$", re.I)


def _payload(row) -> dict:  # noqa: ANN001
    import json

    try:
        return json.loads(row.payload or "{}") or {}
    except ValueError:
        return {}


def shown_confirmed(session, fact_id: int | None = None) -> list:  # noqa: ANN001
    """The confirmed facts the person can open, newest first (or the one)."""
    return _confirmed_rows(session, fact_id=fact_id)


def removed_confirmed(session, fact_id: int):  # noqa: ANN001, ANN201
    """A removed confirmed fact on a note the person can still open: Undo's way back."""
    found = _confirmed_rows(session, removed=True, fact_id=fact_id)
    return found[0] if found else None


def restore_confirmed(session, row) -> list[int]:  # noqa: ANN001
    """Undo of Remove or Not right: the fact is back. A row confirmed again
    in between under the same key goes (soft delete), so the pattern is
    listed once and keeps the wording it had; their ids are returned."""
    from tessellate.core.database import utcnow

    keys = set(_keys(_payload(row)))
    newer = [other for other in shown_confirmed(session) if keys & set(_keys(_payload(other)))]
    for other in newer:
        other.deleted_at = utcnow()
    row.deleted_at = None
    session.flush()
    return [other.id for other in newer]


def confirmed_json(session, row) -> dict:  # noqa: ANN001
    """One confirmed pattern for What it remembers: its sentence, the day it
    was confirmed, its subject and the notes behind it (only those the
    person can open: private, binned and other spaces' notes are left out)."""
    payload = _payload(row)
    line = _said_now(row.text)
    told = _TOLD.match(line)
    rule = str(payload.get("rule") or str(payload.get("key") or ":").split(":", 1)[0])
    named = str(payload.get("key", "")).split(":", 1)[-1] if rule in SUBJECT_RULES else ""
    return {
        "id": row.id, "line": line, "sentence": told["said"] if told else line.rstrip("."), "confirmed_on": _confirmed_on(row, payload),
        "rule": rule, "key": payload.get("key", ""), "subject": payload.get("subject") or named, "measured": payload.get("measured", ""),
        "notes": _notes_behind(session, payload.get("note_ids") or []),
    }


def _confirmed_on(row, payload: dict) -> str:  # noqa: ANN001
    """The day it was confirmed, as Confirm stored it ("confirmed by you, 2026-10-06")."""
    source = str(payload.get("source") or "")
    if source.startswith("confirmed by you, "):
        return source.rsplit(", ", 1)[-1]
    return row.computed_at.date().isoformat() if row.computed_at else ""


def _notes_behind(session, ids: list) -> list[dict]:  # noqa: ANN001
    """The notes a pattern rests on, oldest first, by title; only the ones the
    person can open (the workspace filter rides on `Entry`)."""
    from sqlalchemy import select

    from tessellate.core.database import Entry
    from tessellate.entry import link_wording

    ids = [int(i) for i in ids][:200]
    if not ids:
        return []
    notes = session.scalars(select(Entry).where(Entry.id.in_(ids), Entry.is_deleted.is_(False), Entry.is_private.is_(False)).order_by(Entry.created_at))
    return [{"id": e.id, "title": link_wording.title(e.content or "", limit=48) or "Untitled note"} for e in notes]


def edit_confirmed(session, row, sentence: str | None = None, subject: str | None = None) -> None:  # noqa: ANN001
    """Edit: the person's own wording (said as it is, with the day it was
    first confirmed) or what it is about. A new subject replaces the one
    before (review of B9: three renames left all three answering while
    Settings named one); the tag it was found under keeps answering, since
    its Patterns line is measured under that key. Their word:
    `edited_by_user` stays set, so no run rewrites it."""
    import json

    payload = _payload(row)
    sentence = _TOLD_TYPED.sub("", " ".join(str(sentence or "").split())).rstrip(" .,")
    subject = " ".join(str(subject or "").split())
    if not sentence and not subject:
        raise ValueError("Say what it should say, or what it is about.")
    if subject:
        rule = str(payload.get("rule") or "")
        if rule not in SUBJECT_RULES:
            raise ValueError("Only a pattern about a subject can be given another one.")
        alias = f"{rule}:{_stems(subject)}"
        payload["subject"] = subject
        payload["aliases"] = [alias] if alias != payload.get("key") else []
        row.payload = json.dumps(payload)
    if sentence:
        told = _TOLD.match(_said_now(row.text))
        row.text = f"{sentence}, as you told me on {told['on']}." if told else f"{sentence}."
    row.edited_by_user = True
    session.flush()


def dismiss_confirmed(session, row) -> list[int]:  # noqa: ANN001
    """Not right on a confirmed pattern: the fact goes (soft delete) and the
    pattern, with its near-variants, is not shown again. The corrections'
    ids are the Undo's way back (`DELETE /learned/corrections/{id}`)."""
    from tessellate.ai import learning
    from tessellate.core.database import utcnow

    payload = _payload(row)
    row.deleted_at = utcnow()
    ids = [learning.record(session, kind="dismiss_insight", subject={"key": k}, from_value=row.text, excerpt=row.text).id for k in _keys(payload)]
    session.flush()
    return ids


def notebook(notes: list[dict], today: date, limit: int = 3) -> list[Insight]:
    """The Patterns line over a notebook: recurring tags, plans gone quiet,
    minds changed and a busy week, each its own rule, at most `limit`."""
    tags = Counter(str(t).lower() for n in notes for t in set(n.get("tags") or []))
    out: list[Insight] = []
    for tag, _count in tags.most_common(6):
        found = recurrence(tag, [n for n in notes if tag in {str(t).lower() for t in n.get("tags") or []}], today)
        if found:
            out.append(found)
    out += drift(notes, today)[:2]
    out += contrast(notes, today)[:1]
    busy = load(notes, today)
    if busy:
        out.append(busy)
    return out[:limit]
