"""The companion's proactive remarks that need more than the recent notes
(CHAT_PLAN "Proactive", P1, P2, P5, P8, P9, P10; L-chat-54 and 57).

`composer_voice.remarks` says what the recent notes and the due reminders
hold. These say what the notebook has *noticed*: a plan left open a month, two
notes that disagree, a dated plan with no reminder, a new sentence that answers
an old question. Each is built on the voice's own machinery (`_Voice`: every
factual clause is a note's quoted sentence, a name, a reminder's words or a
measured value, so the grounding rows come with it) and its own closed
phrasebook below. Pure and deterministic: the route gathers the rows, this
reads them, and the same rows on the same day give the same remarks.

Each remark carries a `fact` (what it is about, not how it is worded) that the
page keeps so one fact is never said twice in a week, and a `ttl_days` for the
ones said once ever (a tension).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from tessellate.ai import composer_voice, reminder_suggest
from tessellate.ai.composer import NoteView, Sentence
from tessellate.ai.composer_voice import _Voice, lead

#: A plan fact still open this long is drift (P5).
DRIFT_DAYS = 30
#: A dated plan this near with no reminder is worth saying (P10).
UPCOMING_DAYS = 7
#: How far back "within the hour" reaches for an overdue reminder is no limit; ahead it is this.
DUE_AHEAD = timedelta(hours=1)
#: The days a said fact is not said again (P11); a tension is said once.
FACT_TTL_DAYS = 7
ONCE_TTL_DAYS = 3650

PHRASES: dict[str, str] = {
    "p_drift": "Still unticked since ",
    "p_drift_in": " in ",
    "p_tension": "Two of your notes pull apart. First ",
    "p_tension_then": ", then in ",
    "p_no_reminder": " No reminder is set.",
    "p_answered": "You asked ",
    "p_answered_by": ". The note ",
    "p_answered_in": " may answer it: ",
}


class _P(_Voice):
    """The voice with this module's phrasebook added."""

    def t(self, *names: str) -> _P:
        for name in names:
            text = PHRASES.get(name)
            if text is None:
                super().t(name)
            else:
                self.parts.append(("template", text))
        return self


def _fact(remark: dict, key: str, ttl: int = FACT_TTL_DAYS) -> dict:
    return {**remark, "fact": key, "ttl_days": ttl}


# --- P1: due within the hour, or overdue ---------------------------------------


def due_now(reminders: list[dict], now: datetime) -> list[dict]:
    """The open reminders due within the hour or already overdue, as
    `composer_voice.remarks` takes them. `now` is the person's clock (aware, or
    naive for their local time); a due time is read in that zone."""
    out = []
    here = now.replace(tzinfo=None)
    for r in reminders:
        if r.get("done"):
            continue
        at = r.get("due_time") or r.get("due_at")
        try:
            due = datetime.fromisoformat(str(at))
        except ValueError:
            continue
        if due.tzinfo is not None and now.tzinfo is not None:
            due = due.astimezone(now.tzinfo)
        if due.replace(tzinfo=None) <= here + DUE_AHEAD:
            out.append(r)
    return out


# --- P5: a plan fact open more than 30 days --------------------------------------


def drift(views: list[NoteView], today: date) -> list[dict]:
    """The oldest open checklist item of a note written over 30 days ago,
    said as unticked since then (nothing in the note ticked it)."""
    old = sorted(
        (w for w in views if w.written and (today - w.written).days > DRIFT_DAYS),
        key=lambda w: w.written,
    )
    for view in old:
        item = next((s for s in view.sentences if s.kind == "task" and not s.done), None)
        if item is None:
            continue
        v = _P({view.id: view}, today)
        v.t("p_drift").m(v.day(view.written)).t("p_drift_in").name(view).t("colon").quoted(composer_voice._clip(item))
        return [_fact(v.done("drift", note_id=view.id), f"drift:{view.id}")]
    return []


# --- P9: a new tension -------------------------------------------------------------


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z']+", text.lower()) if len(w) > 3}


def _closest(view: NoteView, other: NoteView) -> Sentence | None:
    """The sentence of `view` that shares the most words with `other`: the
    claim the two are about, not the note's opening line."""
    theirs = _tokens(str(other.note.get("content") or ""))
    best = max(view.sentences, key=lambda s: len(_tokens(s.text) & theirs), default=None)
    return composer_voice._clip(best) if best is not None else lead(view)


def tension(views: dict[int, NoteView], pairs: list[tuple[int, int, str]], today: date) -> list[dict]:
    """One remark for the first open tension whose notes are both readable:
    the earlier claim, then the newer note named with its claim. `pairs` is
    `(earlier_id, later_id, pair_key)`; the page says each only once."""
    for earlier_id, later_id, key in pairs:
        a, b = views.get(earlier_id), views.get(later_id)
        if a is None or b is None or not (a.sentences and b.sentences):
            continue
        first, second = _closest(a, b), _closest(b, a)
        if first is None or second is None:
            continue
        v = _P({a.id: a, b.id: b}, today)
        v.t("p_tension").quoted(first).t("p_tension_then").name(b).t("colon").quoted(second)
        return [_fact(v.done("tension", note_id=b.id), f"tension:{key}", ONCE_TTL_DAYS)]
    return []


# --- P10: a dated plan in the next 7 days with no reminder -------------------------


def upcoming(views: list[NoteView], reminders: list[dict], now: datetime) -> list[dict]:
    """A plan or event a note dates within the next 7 days, when no reminder
    is on that note: "Your trip note says: “We fly on the 14th”. No reminder is
    set." with the reminder it would make as `act`."""
    covered = {r.get("entry_id") for r in reminders if not r.get("done")}
    horizon = now + timedelta(days=UPCOMING_DAYS)
    found: list[tuple[datetime, NoteView, Sentence, dict]] = []
    for view in views:
        if view.id in covered:
            continue
        for s in view.sentences:
            if s.kind == "task" and s.done:
                continue
            read = reminder_suggest.suggest(s.text, now)
            due = read and read.get("due_at")
            if due is None or not (now <= due <= horizon):
                continue
            found.append((due, view, s, read))
            break
    if not found:
        return []
    due, view, s, read = min(found, key=lambda f: (f[0], f[1].id))
    v = _P({view.id: view}, now.date())
    v.t("says_a").name(view).t("says_a_end").quoted(composer_voice._clip(s)).t("p_no_reminder")
    remark = v.done("upcoming", note_id=view.id)
    remark["act"] = {"label": "Set a reminder", "text": read["text"], "due_at": due.isoformat(timespec="minutes"), "entry_id": view.id}
    return [_fact(remark, f"upcoming:{view.id}:{due.date().isoformat()}")]


# --- P8: a new sentence answers an open question -----------------------------------


def answered(view: NoteView, questions: list[dict], today: date) -> dict | None:
    """The first open question (`id`, `text`, `entry_id`) that a sentence of
    `view`, a note just saved, answers: they share at least three words and the
    sentence is not the question's own note. Said once with both quoted."""
    for q in questions:
        if q.get("entry_id") == view.id:
            continue
        asked = _tokens(str(q.get("text") or ""))
        best = max(view.sentences, key=lambda s: len(_tokens(s.text) & asked), default=None)
        if best is None or len(_tokens(best.text) & asked) < 3 or "?" in best.text:
            continue
        v = _P({view.id: view}, today)
        v.t("p_answered", "open_quote").m(str(q["text"]).strip()).t("close_quote", "p_answered_by").name(view)
        v.t("p_answered_in").quoted(composer_voice._clip(best))
        return _fact(v.done("answered", note_id=view.id, question_id=q.get("id")), f"answered:{q.get('id')}:{view.id}", ONCE_TTL_DAYS)
    return None
