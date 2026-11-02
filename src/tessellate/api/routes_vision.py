"""The original vision's open rows (WORLD_CLASS_PLAN section 17, section 8 row 11).

The owner's first notes, read against the app on 2026-09-09, left seven rows
open; the calendar was built 2026-09-26. These are the rest that need the
server:

- **The review queue.** Filings Atlas was unsure of (under 60%) and notes
  left Uncategorised, none of which a person has settled, as one list the
  Notes filter `is:review` and the dashboard count read; Accept settles one.
- **Most opened this month.** `access_count` is all time, so "this month"
  needed a log: `EntryOpen`, a row per note per day, counted on every open.
- **Tidy proposals.** Categories whose names are near (or whose names mean
  the same, when the search engine can embed them) proposed as merges, and
  categories empty for thirty days proposed for removal. Nothing moves until a
  person presses Merge or Remove (the categories' own routes); "Not these"
  is remembered, and a category the person renamed is never merged away.
- **Charts from questions.** A counting or trend question ("how many notes
  per category this month") answered with the counts it asks for, from the
  records and with no model, for the Ask box to draw.

The principle the first notes state: the AI is a servant, not a gatekeeper;
each of these proposes or counts, and a person decides.
"""

from __future__ import annotations

import difflib
import re
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from tessellate.core import deps
from tessellate.core.database import AuditLog, Category, Entry, EntryOpen, utcnow
from tessellate.core.deps import get_session
from tessellate.entry import manager

router = APIRouter(tags=["vision"])

#: Under this, a filing Atlas made is one to check (section 17 row 1).
#: The card's chip and the dashboard's count use the same number
#: (`manager.REVIEW_CONFIDENCE`, the plan's recorded decision).
REVIEW_BELOW = manager.REVIEW_CONFIDENCE
#: How long a category must have been empty to be offered for removal.
EMPTY_DAYS = 30
#: How alike two category names must read to be offered as one.
NAME_RATIO = 0.84
#: The pairs a person said no to, as "a|b" in lower case, sorted.
TIDY_DISMISSED_PREF = "category_tidy_dismissed"


def _live_notes():
    return (
        Entry.is_deleted == False,  # noqa: E712
        Entry.is_draft == False,  # noqa: E712
        Entry.is_board == False,  # noqa: E712
        Entry.archived_at.is_(None),
    )


# --- the review queue ---------------------------------------------------------------


def review_filter():
    """A note waits for review when nobody has settled its filing and either
    Atlas was unsure or it is in Uncategorised. A note still being filed is
    not in it yet."""
    return and_(
        *_live_notes(),
        Entry.user_filed == False,  # noqa: E712
        or_(Entry.filing_state.is_(None), Entry.filing_state != "pending"),
        or_(
            Entry.category_id.is_(None),
            Category.name == manager.UNCATEGORISED,
            and_(Entry.ai_confidence > 0, Entry.ai_confidence < REVIEW_BELOW),
        ),
    )


@router.get("/review-queue")
def review_queue(
    limit: int = Query(default=500, ge=1, le=2000), session: Session = Depends(get_session)
) -> dict:
    """The notes to check, newest first, and how many there are."""
    base = select(Entry.id).outerjoin(Category, Category.id == Entry.category_id).where(review_filter())
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    ids = list(session.scalars(base.order_by(Entry.created_at.desc(), Entry.id.desc()).limit(limit)))
    return {"count": int(total), "ids": ids, "below": REVIEW_BELOW}


@router.post("/review-queue/{entry_id}/accept")
def accept_filing(entry_id: int, session: Session = Depends(get_session)) -> dict:
    """Keep the category it is in: the filing becomes the person's, so the
    queue lets it go and a re-evaluation leaves it where it is."""
    entry = session.get(Entry, entry_id)
    if entry is None or entry.is_deleted:
        raise HTTPException(status_code=404, detail="That note could not be found.")
    entry.user_filed = True
    manager.log_action(
        session, "edited", "entry", entry.id, f"filing accepted: {manager.category_name_for(session, entry)}"
    )
    session.commit()
    return {"id": entry.id, "category": manager.category_name_for(session, entry), "user_filed": True}


# --- most opened this month -----------------------------------------------------------


@router.get("/most-opened")
def most_opened(
    days: int = Query(default=30, ge=1, le=366),
    limit: int = Query(default=10, ge=1, le=50),
    session: Session = Depends(get_session),
) -> list[dict]:
    """The notes opened most in the last `days` days, with how often."""
    from tessellate.api.routes_entries import _to_out_bulk

    since = (utcnow().date() - timedelta(days=days - 1)).isoformat()
    opened = func.sum(EntryOpen.count).label("opened")
    rows = session.execute(
        select(EntryOpen.entry_id, opened)
        .join(Entry, Entry.id == EntryOpen.entry_id)
        .where(EntryOpen.day >= since, *_live_notes())
        .group_by(EntryOpen.entry_id)
        .order_by(opened.desc(), EntryOpen.entry_id.desc())
        .limit(limit)
    ).all()
    counts = {entry_id: int(n) for entry_id, n in rows}
    entries = {e.id: e for e in session.scalars(select(Entry).where(Entry.id.in_(list(counts))))}
    ordered = [entries[i] for i in counts if i in entries]
    out = []
    for item in _to_out_bulk(session, ordered):
        data = item.model_dump(mode="json")
        data["opened"] = counts.get(item.id, 0)
        out.append(data)
    return out


# --- tidy proposals ---------------------------------------------------------------------


def _norm(name: str) -> str:
    text = re.sub(r"[^a-z0-9 ]+", " ", name.lower())
    words = [w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in text.split()]
    return " ".join(words)


def _pair_key(a: str, b: str) -> str:
    return "|".join(sorted((a.strip().lower(), b.strip().lower())))


def _renamed_by_person(session: Session) -> set[int]:
    """Categories a person renamed: their name is a choice, never merged away."""
    rows = session.scalars(
        select(AuditLog.entity_id).where(
            AuditLog.entity_type == "category",
            AuditLog.action == "edited",
            AuditLog.actor == "user",
            AuditLog.detail.like("%→%"),
        )
    )
    return {int(i) for i in rows if i is not None}


def _meaning_alike(names: list[str]) -> dict[tuple[int, int], float]:
    """Cosine of each pair of names, when the search engine can embed them."""
    if len(names) < 2 or len(names) > 300:
        return {}
    try:
        embeddings = deps.get_embeddings()
        if not embeddings.is_ready():
            return {}
        vectors = embeddings.embed_many(names)
    except Exception:  # noqa: BLE001 - names alone still propose
        return {}
    #: Here, not at the top: importing the app must not load numpy before a
    #: request needs it (tests/test_lazy_heavy_imports.py).
    import numpy as np

    out: dict[tuple[int, int], float] = {}
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = vectors[i], vectors[j]
            if a is None or b is None:
                continue
            na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
            if na and nb:
                out[(i, j)] = float(np.dot(a, b)) / (na * nb)
    return out


@router.get("/tidy-proposals")
def tidy_proposals(session: Session = Depends(get_session)) -> dict:
    """Merges and removals the librarian proposes; nothing is changed here."""
    categories = list(session.scalars(select(Category).order_by(Category.id)))
    counts = dict(
        session.execute(
            select(Entry.category_id, func.count(Entry.id))
            .where(Entry.is_deleted == False)  # noqa: E712
            .group_by(Entry.category_id)
        ).all()
    )
    dismissed = set(deps.get_config().get_preference(TIDY_DISMISSED_PREF, []) or [])
    renamed = _renamed_by_person(session)
    usable = [c for c in categories if c.name != manager.UNCATEGORISED]
    meaning = _meaning_alike([c.name for c in usable])
    merges = []
    for i, a in enumerate(usable):
        for j in range(i + 1, len(usable)):
            b = usable[j]
            if (a.workspace_id or "default") != (b.workspace_id or "default"):
                continue
            if _pair_key(a.name, b.name) in dismissed:
                continue
            ratio = difflib.SequenceMatcher(None, _norm(a.name), _norm(b.name)).ratio()
            close = meaning.get((i, j), 0.0)
            if ratio < NAME_RATIO and close < 0.92:
                continue
            keep, merge = (a, b) if counts.get(a.id, 0) >= counts.get(b.id, 0) else (b, a)
            if merge.id in renamed:
                if keep.id in renamed:
                    continue
                keep, merge = merge, keep
            why = f"names alike ({round(ratio * 100)}%)" if ratio >= NAME_RATIO else f"names mean the same ({round(close * 100)}%)"
            merges.append(
                {
                    "keep": {"id": keep.id, "name": keep.name, "notes": counts.get(keep.id, 0)},
                    "merge": {"id": merge.id, "name": merge.name, "notes": counts.get(merge.id, 0)},
                    "why": why,
                }
            )
    cutoff = utcnow() - timedelta(days=EMPTY_DAYS)
    empty = [
        {"id": c.id, "name": c.name, "created_at": c.created_at.isoformat()}
        for c in usable
        if not counts.get(c.id) and c.created_at is not None and c.created_at < cutoff
    ]
    return {"merges": merges, "empty": empty, "empty_days": EMPTY_DAYS}


class DismissBody(BaseModel):
    a: str = Field(min_length=1, max_length=120)
    b: str = Field(min_length=1, max_length=120)


@router.post("/tidy-proposals/dismiss")
def dismiss_tidy(body: DismissBody) -> dict:
    """"Not these": the pair is never proposed again."""
    config = deps.get_config()
    dismissed = list(config.get_preference(TIDY_DISMISSED_PREF, []) or [])
    key = _pair_key(body.a, body.b)
    if key not in dismissed:
        dismissed.append(key)
        config.set_preference(TIDY_DISMISSED_PREF, dismissed[-500:])
    return {"dismissed": key}


@router.post("/tidy-proposals/undismiss")
def undismiss_tidy(body: DismissBody) -> dict:
    """Undo of "Not these" (INBOX 898): the pair may be proposed again."""
    config = deps.get_config()
    key = _pair_key(body.a, body.b)
    dismissed = [k for k in (config.get_preference(TIDY_DISMISSED_PREF, []) or []) if k != key]
    config.set_preference(TIDY_DISMISSED_PREF, dismissed)
    return {"undismissed": key}


# --- charts from questions -------------------------------------------------------------

_COUNTING = re.compile(r"\b(how many|number of|count|trend|chart|graph|plot|over time|per|each)\b")
_ABOUT_NOTES = re.compile(r"\b(notes?|entries|wrote|written|write|captured|saved)\b")


def _period(text: str, today: date) -> tuple[date | None, date | None, str]:
    """(since, until exclusive, words) for the period a question names, read
    by `ai/recognise.py` in the past tense (CHAT_PLAN decision 46): "this
    week", "last month", "in March", "in 2026", "the last 30 days", "since
    Friday", "yesterday". The end is never after today."""
    from tessellate.ai import recognise

    for found in recognise.recognise(text, now=datetime.combine(today, datetime.min.time()), tense="past"):
        if found.rank or found.kind not in ("date", "range"):
            continue
        first, last, grain = found.value if found.kind == "range" else (found.value, found.value, "day")
        if not isinstance(first, date):
            continue  # a stretch of hours: no period of days
        words = found.text.strip().lower()
        if grain == "month" and first.day == 1 and words.startswith(("in ", "during ")):
            words = first.strftime("%B %Y")
        elif grain == "year" and words.startswith(("in ", "during ")):
            words = str(first.year)
        return first, min(last, today) + timedelta(days=1), words
    return None, None, "all time"


def parse_chart_question(question: str, today: date | None = None) -> dict | None:
    """What a counting or trend question asks for, or None when it is not one."""
    text = " ".join(question.lower().split())
    if not _COUNTING.search(text) or not _ABOUT_NOTES.search(text):
        return None
    today = today or datetime.now(timezone.utc).date()
    since, until, words = _period(text, today)
    if re.search(r"\bcategor", text):
        by = "category"
    elif re.search(r"\btags?\b", text):
        by = "tag"
    elif re.search(r"\b(per|each|by) day\b|\bdaily\b|\ba day\b", text):
        by = "day"
    elif re.search(r"\b(per|each|by) week\b|\bweekly\b|\ba week\b", text):
        by = "week"
    elif re.search(r"\b(per|each|by) year\b|\byearly\b", text):
        by = "year"
    elif re.search(r"\b(per|each|by) month\b|\bmonthly\b|\ba month\b", text):
        by = "month"
    elif not re.search(r"\b(how many|number of|count|trend|chart|graph|plot|over time)\b", text):
        return None
    else:
        span = (until - since).days if since and until else None
        by = "day" if span is not None and span <= 31 else "month"
    return {"by": by, "since": since, "until": until, "period": words}


def _bucket(moment: datetime, by: str) -> str:
    day = moment.date()
    if by == "day":
        return day.isoformat()
    if by == "week":
        return (day - timedelta(days=day.weekday())).isoformat()
    if by == "year":
        return str(day.year)
    return f"{day.year:04d}-{day.month:02d}"


def _buckets(since: date, until: date, by: str) -> list[str]:
    out: list[str] = []
    day = since
    while day < until and len(out) < 400:
        key = _bucket(datetime(day.year, day.month, day.day), by)
        if not out or out[-1] != key:
            out.append(key)
        day += timedelta(days=1)
    return out


def count_notes(session: Session, by: str, since: date | None, until: date | None) -> list[dict]:
    """Live notes counted by category, tag or time, in a period."""
    filters = list(_live_notes())
    if since:
        filters.append(Entry.created_at >= datetime(since.year, since.month, since.day, tzinfo=timezone.utc))
    if until:
        filters.append(Entry.created_at < datetime(until.year, until.month, until.day, tzinfo=timezone.utc))
    entries = list(session.scalars(select(Entry).where(*filters)))
    counts: dict[str, int] = {}
    if by == "category":
        names = manager.bulk_category_names(session, entries)
        for entry in entries:
            name = names.get(entry.category_id, manager.UNCATEGORISED)
            counts[name] = counts.get(name, 0) + 1
        rows = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))
        return [{"label": k, "value": v} for k, v in rows[:20]]
    if by == "tag":
        for entry in entries:
            for tag in manager.entry_tags(entry):
                counts[tag] = counts.get(tag, 0) + 1
        rows = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))
        return [{"label": k, "value": v} for k, v in rows[:20]]
    for entry in entries:
        key = _bucket(entry.created_at, by)
        counts[key] = counts.get(key, 0) + 1
    if since and until:
        keys = _buckets(since, until, by)
    else:
        keys = sorted(counts)
        if keys and by in ("month", "day", "week"):
            first = date.fromisoformat(keys[0] + ("-01" if by == "month" else ""))
            keys = _buckets(first, utcnow().date() + timedelta(days=1), by)
    return [{"label": k, "value": counts.get(k, 0)} for k in keys]


class ChartQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=500)


_BY_WORDS = {"category": "per category", "tag": "per tag", "day": "per day", "week": "per week", "month": "per month", "year": "per year"}


def question_chart(session: Session, question: str) -> dict | None:
    """The chart a counting or trend question asks for, or None: no model, the
    words choose the grouping and the period and the records give the counts."""
    asked = parse_chart_question(question)
    if asked is None:
        return None
    rows = count_notes(session, asked["by"], asked["since"], asked["until"])
    total = sum(r["value"] for r in rows) if asked["by"] not in ("tag",) else None
    return {
        "title": f"Notes {_BY_WORDS[asked['by']]}, {asked['period']}",
        "by": asked["by"],
        "kind": "bar" if asked["by"] in ("category", "tag") else "line",
        "period": asked["period"],
        "rows": rows,
        "total": total,
    }


@router.post("/charts/question")
def chart_for_question(body: ChartQuestion, session: Session = Depends(get_session)) -> dict:
    """A chart's numbers for a counting or trend question, or `chart: null`.
    The chart is the same with the model off."""
    return {"chart": question_chart(session, body.question)}
