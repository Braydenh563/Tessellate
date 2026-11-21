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

**No new table** (the spec's "Data: no new table"): the claims of
then-and-now are the note's sentences (`grounding.split_sentences`), paired
by shared distinctive words; with a model on, the model judges each pair
(same, changed, contradicts, unrelated: `model_judge`), and with none, or an
unusable reply, the word rule stands as it always did. Retrieval as of a date takes
its candidates from the engine (today's notes), from revisions whose text
matches the question and from the notes edited since that day, then ranks
the then-texts by the same words and by meaning: each past version's own
vector, made on demand and kept in memory by revision id (`past_vectors`,
at most `EMBED_PER_QUERY` new ones per question).
"""

from __future__ import annotations

import re
import threading
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from tessellate.core.database import EmbeddingRecord, Entry, EntryRevision, like_escape, LIKE_ESCAPE
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


def changed_since(session: Session, when: datetime, limit: int = 200) -> list[Entry]:
    """Notes edited after `when`: the ones whose text then is not their text
    now, so the engine's vectors (of today's text) cannot find them by what
    they said then. The most recently edited first, at most `limit`."""
    rows = session.execute(
        select(EntryRevision.entry_id, func.max(EntryRevision.created_at).label("last"))
        .where(EntryRevision.created_at > _aware(when).astimezone(timezone.utc).replace(tzinfo=None))
        .group_by(EntryRevision.entry_id)
        .order_by(func.max(EntryRevision.created_at).desc())
        .limit(limit)
    )
    ids = [row.entry_id for row in rows]
    if not ids:
        return []
    found = {e.id: e for e in session.scalars(select(Entry).where(Entry.id.in_(ids)))}
    return [found[i] for i in ids if i in found]


# --- meaning over past texts ------------------------------------------------------

#: New past texts embedded per question at most. A revision's vector is made
#: on demand and kept by revision id, so the first question as of a day over
#: a long history pays for this many and the next ones only for what is new;
#: a then-text not embedded yet is ranked by its words alone.
EMBED_PER_QUERY = 48
#: Past-text vectors kept in memory, by embedding backend and revision.
PAST_VECTORS_MAX = 4000
#: How much of a past text is embedded (a note's opening carries its subject).
PAST_TEXT_CHARS = 2000
_past_vectors: OrderedDict = OrderedDict()
_past_lock = threading.Lock()


def forget_past_vectors() -> None:
    """Empty the past-text vector cache (an embedding switch, a test)."""
    with _past_lock:
        _past_vectors.clear()


def _unit(vector) -> np.ndarray | None:  # noqa: ANN001
    if vector is None:
        return None
    array = np.asarray(vector, dtype="float32")
    norm = float(np.linalg.norm(array))
    return array / norm if norm else None


def _now_vectors(session: Session, entry_ids: list[int], backend: str) -> dict[int, np.ndarray]:
    """The stored vectors of notes whose then-text is their text now."""
    if not entry_ids:
        return {}
    rows = session.execute(
        select(EmbeddingRecord.entry_id, EmbeddingRecord.embedding).where(
            EmbeddingRecord.entry_id.in_(entry_ids), EmbeddingRecord.model_version == backend
        )
    )
    return {entry_id: np.frombuffer(blob, dtype="float32") for entry_id, blob in rows}


def past_vectors(session: Session, thens: list[Then], embeddings) -> dict[int, np.ndarray]:  # noqa: ANN001
    """A vector per then-text, by note: today's stored one for a note
    unchanged since, a cached or newly made one by revision id for a past
    version, at most `EMBED_PER_QUERY` made per call."""
    backend = embeddings.backend_id()
    out = _now_vectors(session, [t.entry.id for t in thens if t.revision_id is None], backend)
    missing: list[tuple[tuple, Then]] = []
    with _past_lock:
        for then in thens:
            if then.entry.id in out:
                continue
            key = (backend, then.revision_id) if then.revision_id is not None else (backend, "text", then.text)
            if key in _past_vectors:
                _past_vectors.move_to_end(key)
                out[then.entry.id] = _past_vectors[key]
            elif len(missing) < EMBED_PER_QUERY:
                missing.append((key, then))
    if not missing:
        return out
    made = embeddings.embed_many([then.text[:PAST_TEXT_CHARS] for _, then in missing])
    with _past_lock:
        for (key, then), vector in zip(missing, made):
            if vector is None:
                continue
            out[then.entry.id] = _past_vectors[key] = np.asarray(vector, dtype="float32")
        while len(_past_vectors) > PAST_VECTORS_MAX:
            _past_vectors.popitem(last=False)
    return out


def _meaning_floor(values: list[float]) -> float:
    """The cosine a then-text must reach to count as about the question: the
    search's own two floors (`search_manager.semantic_search`), the absolute
    one and, over five or more, the question's own mean plus a margin, since
    an anisotropic model scores unrelated texts at 0.4 to 0.6."""
    from tessellate.search import search_manager

    least, margin = search_manager.configured_thresholds()
    if len(values) < search_manager.RELATIVE_MIN_CANDIDATES:
        return least
    return max(least, float(np.mean(values) + margin * np.std(values)))


def _meaning(session: Session, question: str, thens: list[Then], embeddings) -> dict[int, float]:  # noqa: ANN001
    """Each then-text's cosine with the question, by note, kept only when it
    clears `_meaning_floor`; empty when the embedding model is not ready (the
    words alone rank then)."""
    if embeddings is None or not thens or not embeddings.is_ready():
        return {}
    from tessellate.search import search_manager

    asked = _unit(search_manager.query_vector(embeddings, question))
    if asked is None:
        return {}
    out = {}
    for entry_id, vector in past_vectors(session, thens, embeddings).items():
        unit = _unit(vector)
        if unit is not None and unit.shape == asked.shape:
            out[entry_id] = float(unit @ asked)
    floor = _meaning_floor(list(out.values()))
    return {entry_id: value for entry_id, value in out.items() if value >= floor}


def rewind(session: Session, question: str, when: datetime, candidates: list[Entry], limit: int = 5, embeddings=None) -> list[Then]:  # noqa: ANN001
    """The notes to answer `question` from, as they stood at `when`: each
    candidate's text then, ranked by the share of the question's words it
    holds plus, with `embeddings`, its meaning's closeness to the question
    (the then-text's own vector, `past_vectors`), the engine's order breaking
    ties; those that did not exist are dropped. When a then-text shares a
    word or clears the meaning floor, those that do neither are dropped;
    when none does, the engine's own order stands."""
    when = _aware(when)
    seen: set[int] = set()
    unique = [e for e in candidates if not (e.id in seen or seen.add(e.id))]
    history = _revisions(session, [e.id for e in unique])
    thens = [then for e in unique if (then := _then(e, history.get(e.id, []), when)) is not None]
    meaning = _meaning(session, question, thens, embeddings)
    terms = set(_terms(question))
    scored: list[tuple[float, int, Then]] = []
    for rank, then in enumerate(thens):
        hits = len(terms & set(_terms(then.text))) / len(terms) if terms else 0.0
        scored.append((-(hits + meaning.get(then.entry.id, 0.0)), rank, then))
    scored.sort(key=lambda row: (row[0], row[1]))
    if any(row[0] < 0 for row in scored):
        scored = [row for row in scored if row[0] < 0]
    return [row[2] for row in scored[:limit]]


def rewind_question(session: Session, question: str, when: datetime, locale: str | None, embeddings, limit: int = 5) -> list[Then]:  # noqa: ANN001
    """Ask as of a day (`routes_chat._rewind_as_of`): the candidates are the
    engine's matches today, the notes whose past text holds the question's
    words, and the notes edited since that day (today's vectors cannot find
    a note by what it said then; its past version's own vector can), all
    ranked by `rewind`."""
    from tessellate.search import search_manager

    hit = search_manager.retrieve_detailed(session, question, embeddings, limit=20, locale=locale)
    candidates = hit.entries + revision_candidates(session, question) + changed_since(session, when)
    return rewind(session, question, when, candidates, limit=limit, embeddings=embeddings)


def end_of_day(day, zone) -> datetime:  # noqa: ANN001
    """"As of 3 March" is the notebook at the end of 3 March, in the user's
    own time zone: what they had written by the time that day was over."""
    from datetime import time as clock

    return datetime.combine(day, clock(23, 59, 59), zone or timezone.utc)


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


#: With a model judging, any shared distinctive word makes a pair worth
#: asking about: the model, not the word count, says whether it is one claim.
JUDGE_CANDIDATE_AT = 0.0
#: One call per comparison, so a long note asks about its first pairs only.
JUDGE_PAIRS_MAX = 12
#: A claim longer than this is clipped in the prompt (a sentence, not a page).
JUDGE_CLAIM_CHARS = 300
#: The judge's fixed text is resent on every comparison: kept small.
JUDGE_PROMPT_CHARS = 420
JUDGE_PROMPT = (
    "Each numbered pair is one note's claim THEN and a claim it makes NOW. "
    "Judge each pair with one word: same (the same claim, reworded), changed "
    "(the claim was revised), contradicts (now says the opposite), or unrelated "
    '(different subjects). Reply with JSON only, like {"1": "changed", "2": "same"}.'
)
JUDGEMENTS = ("same", "changed", "contradicts", "unrelated")


def parse_judgement(reply: str, count: int) -> list[str | None] | None:
    """The model's verdict per pair, by number, or None when the reply is not
    a JSON object at all. A word outside `JUDGEMENTS` is None for that pair,
    which keeps the word rule for it."""
    from tessellate.ai.provider import loads_lenient

    try:
        data = loads_lenient(reply or "")
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or not data:
        return None
    out: list[str | None] = []
    for k in range(1, count + 1):
        word = str(data.get(str(k), "")).strip().lower()
        out.append(word if word in JUDGEMENTS else None)
    return out


def model_judge(ollama, model_manager):  # noqa: ANN001, ANN201
    """A judge over claim pairs through the running provider, and its model's
    name; (None, None) when no model is on or a question is in flight (the
    answer the person waits on goes first, as follow-ups yield to it)."""
    from tessellate.ai.ollama_client import OllamaError
    from tessellate.core import model_gate

    if ollama is None or not ollama.is_running() or model_gate.busy():
        return None, None
    model = model_manager.utility_model()

    def judge(pairs: list[tuple[str, str]]) -> list[str | None] | None:
        lines = [f"{k}. THEN: {a}\n   NOW: {b}" for k, (a, b) in enumerate(pairs, start=1)]
        try:
            reply = ollama.chat(
                model,
                [{"role": "system", "content": JUDGE_PROMPT}, {"role": "user", "content": "\n".join(lines)}],
                mode="quick",
            )
        except OllamaError:
            return None
        return parse_judgement(reply.get("content") or "", len(pairs))

    return judge, model


def _pairs(then: list[str], now: list[str], floor: float, strict: bool) -> tuple[list[tuple[int, int, float]], set[int], set[int]]:
    """Each then-claim's closest unused now-claim, as (then, now, overlap),
    for the pairs at `floor` or over (over it when not `strict`); the
    now-claims taken; and the then-claims said word for word in both."""
    pairs: list[tuple[int, int, float]] = []
    used: set[int] = set()
    same_then: set[int] = set()
    for i, sentence in enumerate(then):
        if sentence in now:
            used.add(now.index(sentence))
            same_then.add(i)
            continue
        best, score = None, 0.0
        for j, other in enumerate(now):
            if j in used or other in then:
                continue
            value = _overlap(sentence, other)
            if value > score:
                best, score = j, value
        if best is not None and (score >= floor if strict else score > floor):
            used.add(best)
            pairs.append((i, best, score))
    return pairs, used, same_then


def _verdicts(then: list[str], now: list[str], pairs: list, judge) -> list[str | None] | None:  # noqa: ANN001
    asked = pairs[:JUDGE_PAIRS_MAX]
    if not judge or not asked:
        return None
    return judge([(then[i][:JUDGE_CLAIM_CHARS], now[j][:JUDGE_CLAIM_CHARS]) for i, j, _ in asked])


def then_and_now(then_text: str, now_text: str, judge=None, judged_by: str | None = None) -> dict:  # noqa: ANN001
    """The claims of `then_text` against those of `now_text`.

    `changed` lists one row per difference, by index into `then` and `now`:
    `revised` (a then-claim whose closest now-claim is that claim changed),
    `dropped` (a then-claim with no partner) and `new` (a now-claim nothing
    then became). A claim said the same way in both is not a change and is
    not listed.

    With `judge` (a model, `model_judge`), the pairs sharing any word go to
    it: `same` is no change, `changed` or `contradicts` is revised and says
    which (`judgement`), `unrelated` is one dropped and one new. A pair it
    gave no usable word for, and every pair when its reply is unusable, keeps
    the word rule (`REVISED_AT`), so no model and a failed model read alike."""
    then, now = claims(then_text), claims(now_text)
    floor, strict = (JUDGE_CANDIDATE_AT, False) if judge else (REVISED_AT, True)
    pairs, used, same_then = _pairs(then, now, floor, strict)
    verdicts = _verdicts(then, now, pairs, judge)
    paired = _settle(pairs, verdicts, used)
    changed = _changes(then, now, paired, same_then, used)
    judged = judged_by if verdicts and any(v is not None for v in verdicts) else None
    return {"then": then, "now": now, "changed": changed, "judged_by": judged}


def _settle(pairs: list, verdicts: list | None, used: set[int]) -> dict[int, tuple[int, str | None]]:
    """Each kept pair's now-claim and verdict, by then-claim; a pair judged
    unrelated, or under the word rule's bar with no verdict, frees its
    now-claim to be new."""
    paired: dict[int, tuple[int, str | None]] = {}
    for k, (i, j, score) in enumerate(pairs):
        verdict = verdicts[k] if verdicts and k < len(verdicts) else None
        if verdict == "unrelated" or (verdict is None and score < REVISED_AT):
            used.discard(j)
        else:
            paired[i] = (j, verdict)
    return paired


def _changes(then: list[str], now: list[str], paired: dict, same_then: set[int], used: set[int]) -> list[dict]:
    changed: list[dict] = []
    for i in range(len(then)):
        if i in same_then:
            continue
        j, verdict = paired.get(i, (None, None))
        if j is None:
            changed.append({"kind": "dropped", "then": i, "now": None})
        elif verdict != "same":
            changed.append({"kind": "revised", "then": i, "now": j} | ({"judgement": verdict} if verdict else {}))
    for j, sentence in enumerate(now):
        if j not in used and sentence not in then:
            changed.append({"kind": "new", "then": None, "now": j})
    return changed


def stored_claims(session: Session, entry_ids: list[int]) -> dict[tuple[int, str], object]:
    """The night shift's claim rows for these notes, by note and sentence as
    compared (`verdicts.norm`): how a sentence read from a note finds the row
    that says which model made it a claim, and when (the claims route and an
    entity page's claims, B4)."""
    from tessellate.ai import verdicts
    from tessellate.core.database import DerivedFact

    if not entry_ids:
        return {}
    rows = session.scalars(select(DerivedFact).where(DerivedFact.entry_id.in_(entry_ids), DerivedFact.kind == "claim"))
    return {(row.entry_id, verdicts.norm(row.text)): row for row in rows}


def claim_span(content: str, sentence: str, start: int = 0) -> tuple[int, int] | None:
    """Where a claim stands in its note: `claims` collapses spacing, so the
    words are found with any run of space between them."""
    words = sentence.split()
    if not words:
        return None
    match = re.compile(r"\s+".join(map(re.escape, words))).search(content, start)
    return match.span() if match else None


#: How many dated changes an entity page lists: the newest say what is true now.
CHANGES_MAX = 30


def _version_changes(entry: Entry, before: str, after: str, at: datetime, keep) -> list[dict]:  # noqa: ANN001
    diff = then_and_now(before, after)
    rows = []
    for change in diff["changed"]:
        then = diff["then"][change["then"]] if change["then"] is not None else None
        now = diff["now"][change["now"]] if change["now"] is not None else None
        if keep(then or "") or keep(now or ""):
            rows.append({"kind": change["kind"], "entry_id": entry.id, "then": then, "now": now, "at": at.isoformat()})
    return rows


def changes_over_time(session: Session, entries: list[Entry], keep, clean=lambda text: text) -> list[dict]:  # noqa: ANN001
    """What changed in these notes' claims, version by version (B4, "what
    changed about X"): `then_and_now` over each pair of kept versions, oldest
    first, each change dated by the edit that made it and kept when `keep`
    says either side is about the thing. Newest first. `clean` takes out of
    each version what is not prose (an entity page's task lines), before the
    pairing, so a task is not read as a claim revised. A private or binned
    note's history is not read, as time travel never reads it."""
    readable = [e for e in entries if not e.is_private and not e.is_deleted]
    history = _revisions(session, [e.id for e in readable])
    rows: list[dict] = []
    for entry in readable:
        revisions = history.get(entry.id, [])
        versions = [clean(r.content or "") for r in revisions] + [clean(entry.content or "")]
        for index, revision in enumerate(revisions):
            rows += _version_changes(entry, versions[index], versions[index + 1], revision.created_at, keep)
    rows.sort(key=lambda r: r["at"], reverse=True)
    return rows[:CHANGES_MAX]
