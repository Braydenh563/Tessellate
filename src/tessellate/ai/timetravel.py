"""Time travel over meaning (WORLD_CLASS_PLAN I5, H8, row 23).

"What did I think about X in March?" answered from the notebook as it stood
then, and a note's claims then set against its claims now.

**What the past is made of.** `entry_revisions`: `record_revision` saves a
note's text *before* each change, stamped when the change was made. So the
text a note had at an instant `T` is the content of the first revision
stamped after `T`, or, when nothing was revised after `T`, the note as it is
now. A note created after `T` did not exist then. Three limits, said rather
than hidden:

* a note keeps its newest `manager.MAX_REVISIONS` revisions; when all of
  them are kept and `T` is older than the oldest, older edits may have been
  pruned, so the version is marked `exact=False`;
* a private note's revisions are ciphertext and a binned note is not
  searched today either, so neither is read here;
* edits coalesced into one revision (a burst of typing) are one step.

**No model, no new table** (the spec's "Data: no new table"): the claims of
then-and-now are the note's sentences (`grounding.split_sentences`), paired
by shared distinctive words; a model's judgement over the pairs is the
spec's optional second half, which this module leaves out. Retrieval as of a date takes
its candidates from the engine (today's notes) and from revisions whose
text matches the question, then ranks the then-texts by the same words.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from tessellate.core.database import Entry, EntryRevision, like_escape, LIKE_ESCAPE
from tessellate.entry import manager


@dataclass(frozen=True)
class Then:
    """One note's text at an instant."""

    entry: Entry
    text: str
    #: The revision the text came from, or None for the note's text now.
    revision_id: int | None
    #: False when older edits may have been pruned (see the module docstring).
    exact: bool = True


def _aware(when: datetime | None) -> datetime | None:
    if when is None:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _revisions(session: Session, entry_ids: list[int]) -> dict[int, list[EntryRevision]]:
    """Every kept revision of these notes, oldest first, in one query."""
    out: dict[int, list[EntryRevision]] = {}
    if not entry_ids:
        return out
    rows = session.scalars(
        select(EntryRevision)
        .where(EntryRevision.entry_id.in_(entry_ids))
        .order_by(EntryRevision.entry_id, EntryRevision.created_at, EntryRevision.id)
    )
    for row in rows:
        out.setdefault(row.entry_id, []).append(row)
    return out


def _then(entry: Entry, revisions: list[EntryRevision], when: datetime) -> Then | None:
    if entry.is_private or entry.is_deleted:
        return None
    created = _aware(entry.created_at)
    if created is not None and created > when:
        return None
    for index, revision in enumerate(revisions):
        if _aware(revision.created_at) > when:
            pruned = len(revisions) >= manager.MAX_REVISIONS and index == 0
            return Then(entry, revision.content or "", revision.id, exact=not pruned)
    return Then(entry, entry.content or "", None)


def text_as_of(session: Session, entry: Entry, when: datetime) -> Then | None:
    """`entry`'s text at `when`, or None when it did not exist then (or is
    private or binned, which time travel does not read)."""
    when = _aware(when)
    return _then(entry, _revisions(session, [entry.id]).get(entry.id, []), when)


def _terms(text: str) -> list[str]:
    from tessellate.search.search_manager import _meaningful_terms

    return _meaningful_terms(text)


def revision_candidates(session: Session, question: str, limit: int = 50) -> list[Entry]:
    """Notes whose *past* text matches the question: a note that said "batch
    size 32" in March and something else now is still the note to read as of
    March. Three of the question's words, any of them, in any kept revision."""
    terms = [t for t in _terms(question) if len(t) > 2][:3]
    if not terms:
        return []
    matches = [EntryRevision.content.ilike(f"%{like_escape(t)}%", escape=LIKE_ESCAPE) for t in terms]
    ids = list(
        session.scalars(
            select(EntryRevision.entry_id).where(or_(*matches)).group_by(EntryRevision.entry_id).limit(limit)
        )
    )
    if not ids:
        return []
    return list(session.scalars(select(Entry).where(Entry.id.in_(ids))))


def rewind(session: Session, question: str, when: datetime, candidates: list[Entry], limit: int = 5) -> list[Then]:
    """The notes to answer `question` from, as they stood at `when`: each
    candidate's text then, ranked by how many of the question's words it
    holds (the engine's order breaks ties), those that did not exist dropped.
    When no then-text shares a word, the engine's own order stands."""
    when = _aware(when)
    seen: set[int] = set()
    unique = [e for e in candidates if not (e.id in seen or seen.add(e.id))]
    history = _revisions(session, [e.id for e in unique])
    terms = set(_terms(question))
    scored: list[tuple[int, int, Then]] = []
    for rank, entry in enumerate(unique):
        then = _then(entry, history.get(entry.id, []), when)
        if then is None:
            continue
        hits = len(terms & set(_terms(then.text))) if terms else 0
        scored.append((-hits, rank, then))
    scored.sort(key=lambda row: (row[0], row[1]))
    if terms and any(row[0] < 0 for row in scored):
        scored = [row for row in scored if row[0] < 0]
    return [row[2] for row in scored[:limit]]


def end_of_day(day, zone) -> datetime:  # noqa: ANN001
    """"As of 3 March" is the notebook at the end of 3 March, in the user's
    own time zone: what they had written by the time that day was over."""
    from datetime import time as clock

    return datetime.combine(day, clock(23, 59, 59), zone or timezone.utc)


_SAID = re.compile(r"\bwhat\s+(?:did|does|do|was|were)\s+(?:my|the|our|that|this)\s+[\w' -]{2,40}?\s+(?:say|said|read|state|stated|look(?:ed)? like|contain|include)\b", re.I)


def as_of_in(question: str, now: datetime) -> date | None:
    """The day a "what did my plan say last month" question asks the notebook as of: the last day of the
    past window it names (`recognise`). None for a question that is not about what a note's text said
    ("what did I write last month" asks for notes by their dates) or a window that is not past."""
    from tessellate.ai import recognise

    if not _SAID.search(question or ""):
        return None
    today = now.date()
    for found in recognise.recognise(question, now=now, tense="past"):
        if found.rank or found.kind not in ("date", "range"):
            continue
        last = found.value[1] if found.kind == "range" else found.value
        if isinstance(last, date) and last < today:
            return last
    return None


def day_words(day) -> str:  # noqa: ANN001
    """"1 January 2025": the day number by hand, not `%-d`, which is glibc's
    and raises on Windows (agent.py says so where it bit)."""
    return f"{day.day} {day:%B %Y}"


# --- then and now -----------------------------------------------------------------

#: How much of a sentence's distinctive words two sentences must share to be
#: one claim revised rather than one dropped and one new (Jaccard over the
#: search terms). Measured on the spec's fixture: "The batch size should stay
#: at 32" against "The batch size is 64 after the memory fix" share 2 of 9
#: (0.22); the unrelated pair in the same note shares none (0.0).
REVISED_AT = 0.2
#: Fewer words than this is a fragment ("Done."), not a claim.
MIN_CLAIM_WORDS = 3


def claims(text: str) -> list[str]:
    from tessellate.ai.grounding import split_sentences

    return [s for s in split_sentences(text or "") if len(s.split()) >= MIN_CLAIM_WORDS]


def _overlap(a: str, b: str) -> float:
    left, right = set(_terms(a)), set(_terms(b))
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def then_and_now(then_text: str, now_text: str) -> dict:
    """The claims of `then_text` against those of `now_text`.

    `changed` lists one row per difference, by index into `then` and `now`:
    `revised` (a then-claim whose closest now-claim shares enough words and
    is not the same sentence), `dropped` (a then-claim with no partner) and
    `new` (a now-claim nothing then became). A claim said the same way in
    both is not a change and is not listed."""
    then, now = claims(then_text), claims(now_text)
    changed: list[dict] = []
    used: set[int] = set()
    for i, sentence in enumerate(then):
        if sentence in now:
            used.add(now.index(sentence))
            continue
        best, score = None, 0.0
        for j, other in enumerate(now):
            if j in used or other in then:
                continue
            value = _overlap(sentence, other)
            if value > score:
                best, score = j, value
        if best is not None and score >= REVISED_AT:
            used.add(best)
            changed.append({"kind": "revised", "then": i, "now": best})
        else:
            changed.append({"kind": "dropped", "then": i, "now": None})
    for j, sentence in enumerate(now):
        if j not in used and sentence not in then:
            changed.append({"kind": "new", "then": None, "now": j})
    return {"then": then, "now": now, "changed": changed}
