"""The app's own records, asked about in words (CHAT_PLAN A3).

"What did I search yesterday", "what ran overnight" and "when did I last
back up" are questions about what the app did, not about the notes: the
answers are already written down (the Ask box's turns, the job records and
the in-memory task history, the backup folder), so they are read here, with
their times, and never sent to search or a model. A model, when one runs,
is handed the answer as ground truth like any counted answer
(`routes_chat._prepare`'s `stats`, decision 75).

Times are said on the person's clock: "09:14 today", "22:40 yesterday",
"14:02 on 9 October". Nothing here writes.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import notebook_stats
from tessellate.ai.composer import _MONTHS
from tessellate.ai.composer_answer import _NUMBER_WORDS
from tessellate.ai.recognise import recognise, window

_I = r"(?:i|we)"
_SEARCHES = re.compile(
    rf"\b(?:(?:what|which (?:things|questions))\s+(?:did|have|had)|what'?d)\s+{_I}\s+(?:last\s+)?"
    r"(?:search(?:ed)?|look(?:ed)? up|ask(?:ed)?(?: you| atlas)?|google(?:d)?)\b"
    r"|\bmy (?:last |latest |recent )?(?:searches|search history|questions|ask history)\b"
    r"|\b(?:last|latest) (?:thing )?(?:search|question) (?:i|we) (?:made|asked|did)\b"
    r"|\bwhat was my (?:last|latest) (?:search|question)\b",
    re.I,
)
_RAN = re.compile(
    r"\bwhat (?:has |have )?(?:ran|run|happened in the background|jobs? ran|tasks? ran|background (?:tasks?|jobs?) ran)\b"
    r"|\b(?:did|has|have) (?:anything|any (?:jobs?|tasks?)|something) (?:run|ran|fail(?:ed)?|break|broken)\b"
    r"|\bwhat (?:jobs?|tasks?|background (?:tasks?|jobs?)) (?:ran|run|have run|finished|failed)\b"
    r"|\bdid (?:the )?(?:night shift|nightly pass|re-?index|index rebuild) (?:run|finish|work)\b",
    re.I,
)
_BACKUP = re.compile(
    r"\bwhen (?:did|was|were) (?:i|we|it|you|the app)?\s*(?:last )?back(?:ed)? ?up\b"
    r"|\bwhen was (?:my|the) (?:last|latest|most recent) back ?up\b"
    r"|\b(?:have|has|did) (?:i|we|it|you|the app|my (?:notes|notebook))\s+(?:been )?(?:backed|back) ?up\b"
    r"|\b(?:is|are) my (?:notes|notebook|data) backed ?up\b"
    r"|\bdid (?:the|my) (?:last )?back ?up (?:run|work|finish|fail)\b"
    r"|\b(?:do|have) (?:i|we) (?:have|got) (?:a |any )?back ?ups?\b",
    re.I,
)
#: Asking how to, or asking for one, is help or an act, not a record.
_NOT = re.compile(r"\bhow (?:do|can|would|should) (?:i|we|you)\b|^\s*(?:please\s+)?(?:back ?up|search|look up)\b", re.I)
_OVERNIGHT = re.compile(r"\b(?:overnight|last night|while i (?:was )?slept|while i was asleep|over ?night)\b", re.I)

#: How many rows an answer lists before saying how many more.
LIST_AT_MOST = 8


def asks(question: str) -> str | None:
    """"searches", "ran" or "backup" for a question about the app's own
    records, else None."""
    text = " ".join((question or "").split())
    if not text or _NOT.search(text):
        return None
    if _BACKUP.search(text):
        return "backup"
    if _RAN.search(text):
        return "ran"
    if _SEARCHES.search(text):
        return "searches"
    return None


# --- saying a time ------------------------------------------------------------


def _local(at: datetime | str | None, zone) -> datetime | None:  # noqa: ANN001
    """A stored instant (naive UTC, or ISO text) on the person's clock."""
    if at is None:
        return None
    if isinstance(at, str):
        try:
            at = datetime.fromisoformat(at)
        except ValueError:
            return None
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    return at.astimezone(zone)


def _day_words(day: date, today: date) -> str:
    if day == today:
        return "today"
    if day == today - timedelta(days=1):
        return "yesterday"
    month = _MONTHS[day.month - 1]
    return f"on {day.day} {month}" if day.year == today.year else f"on {day.day} {month} {day.year}"


def _at(when: datetime, today: date) -> str:
    """"09:14 today", "14:02 on 9 October"."""
    return f"{when:%H:%M} {_day_words(when.date(), today)}"


def _ago(when: datetime, now: datetime) -> str:
    seconds = max(0, (now - when).total_seconds())
    if seconds < 90:
        return "just now"
    for size, unit in ((86400, "day"), (3600, "hour"), (60, "minute")):
        if seconds >= size:
            n = int(seconds // size)
            return f"{_count(n)} {unit}{'' if n == 1 else 's'} ago"
    return "just now"


def _count(n: int) -> str:
    return _NUMBER_WORDS[n] if 0 <= n < len(_NUMBER_WORDS) else str(n)


def _span_of(question: str, now: datetime) -> tuple[datetime, datetime, str] | None:
    """(start, end, words) the question names, on the person's clock.
    "Overnight" and "last night" are 18:00 yesterday to 09:00 today (or now,
    when that is earlier); any other day or span is `recognise.window`'s,
    the one reader every date question goes through."""
    if _OVERNIGHT.search(question):
        today = now.date()
        start = datetime.combine(today - timedelta(days=1), time(18), now.tzinfo)
        end = min(datetime.combine(today, time(9), now.tzinfo), now)
        return start, end, "overnight"
    part = re.search(r"\bthis (morning|afternoon|evening)\b", question, re.I)
    if part:
        #: A part of today, by the hours `when.py` gives the parts of a day.
        hours = {"morning": (0, 12), "afternoon": (12, 18), "evening": (18, 24)}[part.group(1).lower()]
        start = datetime.combine(now.date(), time(hours[0]), now.tzinfo)
        end = min(start + timedelta(hours=hours[1] - hours[0]), now)
        return start, end, part.group(0).lower()
    phrase = _time_phrase(question, now)
    if not phrase:
        return None
    span = window(phrase, now)
    if span is None:
        return None
    if phrase.startswith(("today", "yesterday", "this ", "last ")):
        return span[0], span[1], phrase
    #: A weekday or "3 days ago" is said as the day it meant.
    day = span[0].date()
    return span[0], span[1], f"on {day:%A} {day.day} {_MONTHS[day.month - 1]}"


def _time_phrase(question: str, now: datetime) -> str | None:
    """The first day or span the recogniser reads in `question`, lowered
    ("yesterday", "last week", "on monday", "3 days ago"); a bare length
    followed by "ago" ("2 hours ago") is the time that long back."""
    for found in recognise(question, now=now, tense="past"):
        if found.rank:
            continue
        if found.kind in ("date", "range"):
            return found.text.lower()
        if found.kind == "duration" and question[found.end:].lstrip().lower().startswith("ago"):
            return f"{found.text.lower()} ago"
    return None


def _offered(text: str, facts: list[dict] | None, offer: dict) -> notebook_stats.StatAnswer:
    """The answer with its offer as its own last line: the line the Ask box
    turns into the offer's link (`digestOffer`)."""
    return notebook_stats.StatAnswer("records", f"{text}\n\n{offer['label']}", facts or [], offer=offer)


def _opening(words: str, sentence: str) -> str:
    """"Yesterday, you asked ..." with the span's words first."""
    return f"{words[0].upper()}{words[1:]}, {sentence}"


# --- searches -----------------------------------------------------------------


def _turns(session: Session) -> list[tuple[datetime, str]]:
    from tessellate.core.database import AskTurn

    rows = session.execute(select(AskTurn.created_at, AskTurn.question).order_by(AskTurn.created_at.desc()).limit(500))
    return [(at, " ".join((q or "").split())) for at, q in rows]


def _question_said(text: str) -> str:
    text = text.strip()
    return text[:1].upper() + text[1:] if text else text


def _searches(question: str, turns: list[tuple[datetime, str]], now: datetime) -> notebook_stats.StatAnswer:
    zone, today = now.tzinfo, now.date()
    asked = [(_local(at, zone), q) for at, q in turns if q]
    asked = [(at, q) for at, q in asked if at is not None]
    offer = {"kind": "open", "label": "Open History to read their answers?", "surface": "ask-history"}
    span = _span_of(question, now)
    if not asked:
        return notebook_stats.StatAnswer("records", "You have not asked anything in Ask yet, so there is nothing in History.")
    if span is None:
        return _searches_unspanned(question, asked, today, offer)
    start, end, words = span
    inside = [(at, q) for at, q in asked if start <= at <= end]
    if not inside:
        return _asked_nothing(asked, start, words, today)
    grouped = _grouped_questions(inside)
    rows = list(grouped.values())[:LIST_AT_MOST]
    rows.reverse()  # oldest first, so the day reads in order
    one_day = rows[0][0].date() == rows[-1][0].date()
    label = (lambda at: f"{at:%H:%M}") if one_day else (lambda at: _at(at, today))
    lines = [
        f"**{label(at)}:** {_question_said(q)}" + (f" ({_count(times)} times)" if times > 1 else "")
        for at, q, times in rows
    ]
    head = _opening(words, f"you asked {_asked_count_words(len(inside), len(grouped))}:")
    return _offered("\n\n".join([head, *lines]), [{"label": label(at), "text": q, "times": times} for at, q, times in rows], offer)


def _asked_nothing(asked: list, start: datetime, words: str, today) -> notebook_stats.StatAnswer:  # noqa: ANN001
    """Nothing asked in the span: name the question before it."""
    before = next(((at, q) for at, q in asked if at < start), None)
    text = f"You asked nothing in Ask {words}."
    if before:
        text += f" The question before that was \"{_question_said(before[1])}\", at {_at(before[0], today)}."
    return notebook_stats.StatAnswer("records", text)


def _searches_unspanned(question: str, asked: list, today, offer: dict) -> notebook_stats.StatAnswer:
    """"What did I last ask" with no span: the latest question, or the last five."""
    if re.search(r"\blast|latest\b", question, re.I) and not re.search(r"\bsearches|questions\b", question, re.I):
        at, q = asked[0]
        return _offered(
            f"Your last question in Ask was \"{_question_said(q)}\", at {_at(at, today)}.",
            [{"label": f"{at:%H:%M}", "text": q}], offer | {"label": "Open History?"},
        )
    shown = asked[:5]
    lines = [f"**{_at(at, today)}:** {_question_said(q)}" for at, q in shown]
    head = f"Your last {_count(len(shown))} questions in Ask, newest first:" if len(shown) > 1 else "Your one question in Ask so far:"
    return _offered("\n\n".join([head, *lines]), [{"label": f"{at:%H:%M}", "text": q} for at, q in shown], offer)


def _grouped_questions(inside: list) -> dict[str, list]:
    """One row per question, at the last time it was asked: a question
    asked again is said once with how many times."""
    grouped: dict[str, list] = {}
    for at, q in inside:  # newest first
        key = q.lower().rstrip("?.! ")
        if key in grouped:
            grouped[key][2] += 1
        else:
            grouped[key] = [at, q, 1]
    return grouped


def _asked_count_words(total: int, distinct: int) -> str:
    """"one thing in Ask", "three different questions in Ask, five times in all", and the latest-N tail."""
    if total == distinct:
        said = ("one thing" if total == 1 else f"{_count(total)} things") + " in Ask"
    elif distinct == 1:
        said = f"one question in Ask, {_count(total)} times"
    else:
        said = f"{_count(distinct)} different questions in Ask, {_count(total)} times in all"
    latest = f"; the latest {_count(LIST_AT_MOST)}" if distinct > LIST_AT_MOST else ""
    return f"{said}{latest}"


# --- what ran -----------------------------------------------------------------

_STATUS = {"ok": "done", "completed": "done", "failed": "failed", "cancelled": "stopped", "running": "still running", "interrupted": "stopped"}


def _ran_rows(runs: list[dict], finished: list[dict], zone) -> list[dict]:  # noqa: ANN001
    """One row per job ending: the job records' last run of each kind and
    the task history's endings, the same ending counted once."""
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for item in finished:
        at = _local(item.get("at"), zone)
        if at is None:
            continue
        label = item.get("label") or item.get("kind") or "A task"
        rows.append({"at": at, "label": label, "status": _STATUS.get(item.get("outcome", ""), "done"), "detail": item.get("detail") or ""})
        seen.add((label.lower(), f"{at:%Y%m%d%H%M}"))
    for run in runs:
        if not run.get("ran"):
            continue
        at = _local(run.get("finished_at") or run.get("started_at"), zone)
        if at is None:
            continue
        label = run.get("label") or run.get("kind") or "A task"
        if (label.lower(), f"{at:%Y%m%d%H%M}") in seen:
            continue
        status = _STATUS.get(run.get("status", ""), run.get("status", ""))
        rows.append({"at": at, "label": label, "status": status, "detail": run.get("error") or run.get("result") or ""})
    rows.sort(key=lambda r: r["at"])
    return rows


def _row_line(row: dict, label: str) -> str:
    detail = row["detail"].strip().rstrip(".")
    said = f"{row['label']}, {row['status']}"
    if detail and detail.lower() != row["label"].lower():
        #: "Derived 14 facts" follows a colon in lower case; "SearXNG ..." keeps its capitals.
        said += f": {detail[:1].lower() + detail[1:] if detail[1:2].islower() else detail}"
    return f"**{label}:** {said}."


def _ran_nothing(rows: list[dict], start: datetime, words: str, today) -> str:  # noqa: ANN001
    """Nothing ran in the span: say what ran last, or that nothing has."""
    text = f"Nothing ran {words}."
    earlier = [r for r in rows if r["at"] < start]
    if earlier:
        last = earlier[-1]
        text += f" The last thing that ran was {'the ' + last['label'].lower() if last['label'][1:].islower() else last['label']}, at {_at(last['at'], today)} ({last['status']})."
    elif not rows:
        text += " Nothing has run since the app started, by its records."
    return text


def _ran_head(inside: list[dict], end: datetime, words: str) -> str:
    """"Three things ran, all done." for the rows inside the span."""
    failed = sum(1 for r in inside if r["status"] == "failed")
    things = "one thing" if len(inside) == 1 else f"{_count(len(inside))} things"
    how = "and it failed" if failed and len(inside) == 1 else (f"and {_count(failed)} failed" if failed else ("all done" if len(inside) > 1 else ""))
    if words == "overnight":
        head = f"Overnight, from 18:00 yesterday to {end:%H:%M} today, {things} ran"
    else:
        head = _opening(words, f"{things} ran")
    return head + (f", {how}." if how else ".")


def _ran(question: str, runs: list[dict], finished: list[dict], now: datetime) -> notebook_stats.StatAnswer:
    zone, today = now.tzinfo, now.date()
    rows = _ran_rows(runs, finished, zone)
    span = _span_of(question, now) or (now - timedelta(days=1), now, "in the last day")
    start, end, words = span
    inside = [r for r in rows if start <= r["at"] <= end]
    offer = {"kind": "open", "label": "Open Background tasks?", "surface": "settings:tasks"}
    if not inside:
        return _offered(_ran_nothing(rows, start, words, today), None, offer)
    one_day = inside[0]["at"].date() == inside[-1]["at"].date()
    lines = [_row_line(r, f"{r['at']:%H:%M}" if one_day else _at(r["at"], today)) for r in inside[:LIST_AT_MOST]]
    if len(inside) > LIST_AT_MOST:
        lines.append(f"And {_count(len(inside) - LIST_AT_MOST)} more.")
    head = _ran_head(inside, end, words)
    return _offered(
        "\n\n".join([head, *lines]),
        [{"label": f"{r['at']:%H:%M}", "text": r["label"], "status": r["status"]} for r in inside], offer,
    )


# --- backups ------------------------------------------------------------------


def _backup(backups: list[dict], runs: list[dict], now: datetime) -> notebook_stats.StatAnswer:
    zone, today = now.tzinfo, now.date()
    offer = {"kind": "open", "label": "Open Backups in Settings?", "surface": "settings:data"}
    run = next((r for r in runs if r.get("kind") == "backup" and r.get("ran")), None)
    newest = _local(backups[0]["created_at"], zone) if backups else None
    failed_at = _local(run.get("finished_at") or run.get("started_at"), zone) if run and run.get("status") == "failed" else None
    if newest is None:
        text = "There is no backup yet."
        if failed_at is not None:
            text += f" The last try, at {_at(failed_at, today)}, failed: {run.get('error') or 'no reason was recorded'}."
        return _offered(text, None, offer)
    kept = len(backups)
    text = f"Your last backup was at {_at(newest, today)}, {_ago(newest, now)}."
    text += f" {'One backup is' if kept == 1 else f'{_count(kept).capitalize()} backups are'} kept."
    if failed_at is not None and failed_at > newest:
        reason = (run.get("error") or "no reason was recorded").rstrip(".")
        text += f"\n\nThe try after it, at {_at(failed_at, today)}, failed: {reason}."
    return _offered(text, [{"label": "last backup", "text": newest.isoformat()}], offer)


# --- the answer ---------------------------------------------------------------


def answer(
    question: str,
    session: Session | None,
    *,
    now: datetime,
    data_dir: Path | None = None,
    turns: list[tuple[datetime, str]] | None = None,
    runs: list[dict] | None = None,
    finished: list[dict] | None = None,
    backups: list[dict] | None = None,
) -> notebook_stats.StatAnswer | None:
    """The records' answer to `question`, or None when it is not about
    them. `now` is the person's clock (tz-aware). The keyword arguments
    after it stand in for the records in tests; left out, each is read."""
    kind = asks(question)
    if kind is None:
        return None
    if kind == "searches":
        return _searches(question, turns if turns is not None else _turns(session), now)
    if runs is None:
        from tessellate.core import jobruns

        runs = jobruns.last_runs()
    if kind == "ran":
        if finished is None:
            from tessellate.core import taskhistory

            finished = taskhistory.recent()
        return _ran(question, runs, finished, now)
    if backups is None:
        from tessellate.core import backup

        backups = backup.list_backups(data_dir) if data_dir is not None else []
    return _backup(backups, runs, now)
