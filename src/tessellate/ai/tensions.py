"""Where the notebook disagrees with itself.

**This is the thing `LINK_TYPES` was built for and nobody ever built.** Its
own comment in `core/database.py` says so:

    `contradicts` is the one worth having built this for: a notebook that can
    show you where you disagreed with yourself is not something an embedding
    similarity score can ever produce, however well tuned.

That was true for a long time. `link_type` is writable only through
`POST /entries/{id}/links`, a person, by hand, choosing "Contradicts" from a
dropdown. So the notebook could *record* a disagreement it was told about, and
could never *find* one.

Everything else this app knows about connection answers "these are about the
same thing": embedding similarity, shared words, `[[wiki links]]`, threads.
None of them can tell agreement from disagreement, two notes that flatly
contradict each other are, to a vector, maximally similar. That gap is the
whole point of this module.

**Why this app can do it and a cloud notebook cannot.** Reading every
plausible pair of notes with a language model is an unbounded number of
tokens against a corpus that is entirely the user's private writing. Metered,
that is a bill nobody would pay to be told they changed their mind; sent to a
someone else's server, it is the most sensitive text a person owns. Here
inference is free and stays on the machine, so the notebook can afford to
actually read itself.

## What it looks for, and what it deliberately ignores

A *tension* is two notes that make claims which cannot both be right. Not two
notes on the same topic, not one adding nuance to another, not a plan that
changed because the facts changed.

Two rules keep this from becoming noise, and both matter more than the model
prompt does:

1. **Candidates come from pairs that are already about the same thing.**
   Contradiction is only possible between notes that share a subject, so this
   never scans all pairs, it takes the ones the existing similarity pass
   already produced. That bounds the work and removes the obvious false
   positives before a model is asked anything.
2. **Time is part of the finding, not decoration.** The interesting case is
   almost always a change of mind: written in March, contradicted in
   September. Two notes written the same afternoon that seem to disagree are
   usually one thought being refined. `MIN_GAP_DAYS` is what encodes that.

## Nothing is written without a person saying yes

Same policy as the auto-linker (`routes_entries_relations.link_suggestions`) and for a
stronger reason: telling someone they contradicted themselves when they did
not is worse than telling them nothing. This module only ever *proposes*.
Accepting a tension is what creates the `EntryLink` with
`link_type="contradicts"`, an existing column, so there is no migration
here and the graph, the traversal weighting and Trace all understand the
result the moment it exists.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from tessellate.ai import presets
from tessellate.ai import model_manager as model_manager_module
from tessellate.ai import ollama_client as ollama_client_module
from tessellate.core.database import Entry
from tessellate.entry.properties import strip as strip_properties

logger = logging.getLogger("tessellate.ai.tensions")

#: Two notes written within a few days of each other that appear to disagree
#: are usually one idea being worked out, not a change of position. A week is
#: long enough that the second note is a considered revisit rather than the
#: same sitting, and short enough that a fast-moving project still surfaces.
MIN_GAP_DAYS = 7

#: How much of each note the model is shown. Long enough to carry the claim,
#: short enough that a pair costs one small prompt, this runs over many
#: pairs, and the budget discipline in `ai/agent.py` applies here too.
EXCERPT_CHARS = 700

#: A hard ceiling on model calls per pass, so a large notebook cannot turn one
#: background pass into an hours-long job. The pass is resumable by nature:
#: pairs already judged are skipped by the caller.
MAX_PAIRS_PER_PASS = 40

#: The model must open with this token for a genuine disagreement. Asking for
#: a single leading word rather than JSON is deliberate, the small local
#: models this app targets are markedly better at "say YES or NO first" than
#: at emitting well-formed JSON, and `ai/extractor.py` already carries a
#: `_extract_json_object` helper written because they get that wrong.
_YES = "yes"
_NO = "no"

#: An "explanation" that only restates the verdict. Shown beside the two notes
#: it is accusing, one of these tells the reader nothing they could check, so
#: it is treated as no finding rather than displayed.
#:
#: A pattern rather than a phrase list, because the phrase list this started
#: as missed "basically they just conflict": the subject and the verb are the
#: fixed part and anything can sit between them. The same guard `ai/links.py`
#: needs for link reasons, for the same reason, a small model told to justify
#: itself will sometimes assert the conclusion instead.
VAGUE_EXPLANATION = re.compile(
    r"\b(?:they|these|the(?:\s+two)?\s+notes)\b[^.]{0,24}?"
    r"\b(?:disagree|contradict|conflict|inconsistent|different\s+things)\b",
    re.IGNORECASE,
)


@dataclass
class Tension:
    """One proposed disagreement, before anybody has agreed it is real."""

    earlier_id: int
    later_id: int
    #: One line, in the model's words, naming what the two notes disagree
    #: about. Shown to the person deciding, so it has to say something
    #: specific, and `_clean_explanation` rejects it when it does not.
    explanation: str
    earlier_excerpt: str
    later_excerpt: str
    earlier_at: str | None
    later_at: str | None
    gap_days: int


_SYSTEM = (
    "You compare two notes from one person's private notebook and decide "
    "whether they CONTRADICT each other.\n\n"
    "A contradiction means both notes make claims that cannot both be true, "
    "or state opposite positions, decisions or preferences about the same "
    "thing. The person has changed their mind, or written something "
    "inconsistent, and would want to know.\n\n"
    "These are NOT contradictions, and you must answer NO for them:\n"
    "- two notes about the same topic that simply say different things\n"
    "- one note adding detail, nuance or a later step to the other\n"
    "- a plan that changed because the circumstances changed, where both "
    "notes are true of their own moment\n"
    "- different opinions about different things\n"
    "- one note being vague and the other specific\n\n"
    "Answer NO unless you can name the specific claim each note makes and "
    "say why they cannot both hold. Most pairs are NOT contradictions; NO is "
    "the right answer far more often than YES.\n\n"
    "Reply on ONE line, starting with YES or NO. If YES, follow it with a "
    "dash and one short sentence naming what they disagree about, for "
    "example: 'YES - the first says the launch is in May, the second says "
    "it slipped to August'. If NO, reply with only the word NO."
)


def _excerpt(text: str) -> str:
    """A single-paragraph excerpt of a note, trimmed for the prompt."""
    flat = re.sub(r"\s+", " ", strip_properties(text or "")).strip()
    if len(flat) <= EXCERPT_CHARS:
        return flat
    return flat[:EXCERPT_CHARS].rsplit(" ", 1)[0] + "…"


def _clean_explanation(reply: str) -> str | None:
    """The sentence after YES, or None if the reply was NO or unusable.

    Strict on purpose. A model that answers "YES" with nothing after it has
    not made a case, and a tension with no stated reason is exactly the
    unfalsifiable accusation this feature must never produce, so an empty or
    too-short explanation is treated as a NO rather than shown with a blank
    line where the reasoning should be.
    """
    text = (reply or "").strip()
    if not text:
        return None
    head = text.lower()
    if head.startswith(_NO):
        return None
    if not head.startswith(_YES):
        # Neither word. The instruction was explicit, so a reply that ignores
        # it is not evidence of anything, treated as no finding.
        return None
    rest = text[len(_YES) :].lstrip()
    rest = rest.lstrip("-–, :,. ").strip()
    rest = rest.strip("\"'").strip()
    # "YES" alone, or a stub like "they disagree", says nothing a person can
    # check against the two notes shown beside it. Both shapes are rejected:
    # a length floor for the empty case, and a vague-phrase list for the
    # answer that restates the question instead of answering it.
    #
    # The same guard `ai/links.py` needs for link reasons, for the same
    # reason: a small model told to justify itself will sometimes assert the
    # conclusion instead. Its `VAGUE_PHRASES` covers "related"; these cover
    # the disagreement wording it does not.
    if len(rest) < 12:
        return None
    if VAGUE_EXPLANATION.search(rest):
        return None
    return rest


def _gap_days(earlier: datetime | None, later: datetime | None) -> int | None:
    if earlier is None or later is None:
        return None
    return abs((later - earlier).days)


def compare_pair(
    earlier: Entry,
    later: Entry,
    models: model_manager_module.ModelManager,
    ollama: ollama_client_module.OllamaClient,
) -> Tension | None:
    """Ask the model whether these two notes contradict each other.

    Returns None for "no contradiction", for an unusable reply, and for any
    model failure: a pass over many pairs must not be taken down by one bad
    round trip, and "we could not tell" and "they agree" lead to the same
    place here: nothing is shown.
    """
    earlier_text = _excerpt(earlier.content)
    later_text = _excerpt(later.content)
    if not earlier_text or not later_text:
        return None

    prompt = (
        f"Note A (written {_stamp(earlier.created_at)}):\n{earlier_text}\n\n"
        f"Note B (written later, {_stamp(later.created_at)}):\n{later_text}\n\n"
        "Do these contradict each other?"
    )
    try:
        reply = ollama.chat(
            models.utility_model(),
            [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": prompt},
            ],
            mode=presets.BACKGROUND_MODE,
        )
    except Exception:  # noqa: BLE001  # one pair failing must not end the pass
        logger.debug("tension check failed for %s/%s", earlier.id, later.id, exc_info=True)
        return None

    explanation = _clean_explanation((reply or {}).get("content", ""))
    if explanation is None:
        return None

    return Tension(
        earlier_id=earlier.id,
        later_id=later.id,
        explanation=explanation,
        earlier_excerpt=_excerpt(earlier.content)[:280],
        later_excerpt=_excerpt(later.content)[:280],
        earlier_at=_stamp(earlier.created_at),
        later_at=_stamp(later.created_at),
        gap_days=_gap_days(earlier.created_at, later.created_at) or 0,
    )


def _stamp(when: datetime | None) -> str | None:
    return when.date().isoformat() if when else None


def order_by_time(a: Entry, b: Entry) -> tuple[Entry, Entry] | None:
    """`(earlier, later)`, or None if the pair should not be considered.

    Filters here rather than in the caller because "which is earlier" and
    "is this pair worth a model call" are the same question: a pair with no
    timestamps has no story to tell about a change of mind, and a pair from
    the same few days is one thought being worked out (see `MIN_GAP_DAYS`).
    """
    if a.created_at is None or b.created_at is None:
        return None
    earlier, later = (a, b) if a.created_at <= b.created_at else (b, a)
    gap = _gap_days(earlier.created_at, later.created_at)
    if gap is None or gap < MIN_GAP_DAYS:
        return None
    return earlier, later


# --- the derived tensions table (WORLD_CLASS_PLAN B4) --------------------------
#
# A scan's findings used to live only in the response that carried them: the
# Tensions widget could say how many pairs had been accepted and nothing else,
# and finding them again meant asking the model again. The table below keeps
# them, but as a *view*: every row is rebuilt from the events and rows that
# are kept elsewhere, so a rebuild from nothing gives the same table (the B4
# gate), and nothing here is the only copy of anything.

#: The events this kernel writes, all `entity_type="tension"` so the audit
#: log's entity index serves "the newest tension event" without a scan, and
#: so none of them shows up in a note's own history as if it were an edit.
EVENT_TYPE = "tension"
FOUND = "tension_found"
ACCEPTED = "tension_accepted"
DISMISSED = "tension_dismissed"
#: Undo of an accept or a dismissal (INBOX 898): the pair is offered again.
REOPENED = "tension_reopened"

#: The order a pair's findings are ranked in when two sources found it: the
#: earliest finding wins, and on the same instant a scan (which a person ran)
#: before the night shift, before a bare link.
_SOURCE_RANK = {"scan": 0, "night": 1, "link": 2}


def pair_key(a: int, b: int) -> str:
    """`"low:high"`: one pair, one key, whichever side is named first. The
    same shape as `routes_entries_relations._tension_key` and the dismissed list."""
    low, high = sorted((int(a), int(b)))
    return f"{low}:{high}"


def record_event(session, action: str, earlier_id: int, later_id: int, **extra) -> None:  # noqa: ANN001, ANN003
    """One tension event, in the caller's transaction: found, accepted or
    dismissed. The payload names both notes; a finding adds its reason, its
    model and its confidence, which is everything a rebuild needs."""
    from tessellate.core import events

    payload = {"earlier_id": int(earlier_id), "later_id": int(later_id), "pair": pair_key(earlier_id, later_id)}
    payload.update(extra)
    actor = f"ai:{extra.get('model') or 'tensions'}"[:60] if action == FOUND else None
    events.record(session, action, EVENT_TYPE, int(later_id), detail=payload["pair"], payload=payload, actor=actor)


class _AllSpaces:
    """Every space's rows for the length of a rebuild. The table is one table
    for the notebook; a rebuild run from a request in one space must not
    quietly drop another space's links (`EntryLink` is space-scoped by the
    session's filter, `database._add_workspace_filter`)."""

    def __init__(self, session) -> None:  # noqa: ANN001
        self.session = session
        self.saved: tuple = (None, None)

    def __enter__(self):  # noqa: ANN204
        self.saved = (self.session.info.pop("workspace_id", None), self.session.info.pop("hidden_workspaces", None))
        return self

    def __exit__(self, *exc) -> None:  # noqa: ANN002
        workspace, hidden = self.saved
        if workspace is not None:
            self.session.info["workspace_id"] = workspace
        if hidden is not None:
            self.session.info["hidden_workspaces"] = hidden


def sources_version(session) -> tuple:  # noqa: ANN001
    """What the table was built from, in a few indexed aggregates: the newest
    tension event, the tension facts (and how many are tombstoned), and the
    `contradicts` links. Any change to a source moves it."""
    from sqlalchemy import func, select

    from tessellate.core import deps
    from tessellate.core.database import AuditLog, DerivedFact, EntryLink

    with _AllSpaces(session):
        return (
            str(deps.get_config().data_dir),
            session.scalar(select(func.max(AuditLog.id)).where(AuditLog.entity_type == EVENT_TYPE)),
            session.scalar(select(func.count(DerivedFact.id)).where(DerivedFact.kind == "tension")) or 0,
            session.scalar(select(func.max(DerivedFact.id)).where(DerivedFact.kind == "tension")),
            session.scalar(
                select(func.count(DerivedFact.id)).where(
                    DerivedFact.kind == "tension", DerivedFact.deleted_at.is_not(None)
                )
            )
            or 0,
            session.scalar(select(func.count(EntryLink.id)).where(EntryLink.link_type == "contradicts")) or 0,
            session.scalar(select(func.max(EntryLink.id)).where(EntryLink.link_type == "contradicts")),
        )


def _finding(key: str, earlier: int, later: int, **fields) -> dict:  # noqa: ANN003
    row = {"pair": key, "earlier_id": earlier, "later_id": later}
    row.update(fields)
    return row


@dataclass(slots=True)
class _Sources:
    """What `derive` has read so far: every finding by pair, and the verdicts
    that decide each pair's status. Filled by the three readers below, in the
    order of the three sources, and read once by `_rows`."""

    #: Notes' creation times, for telling which side of a pair came later.
    written: dict[int, Any]
    findings: dict[str, list[tuple]] = field(default_factory=dict)
    accepted_events: set[str] = field(default_factory=set)
    dismissed: set[str] = field(default_factory=set)
    linked: dict[str, Any] = field(default_factory=dict)

    def ordered(self, a: int, b: int) -> tuple[int, int]:
        """`(earlier, later)` by the notes' creation times; a note with no
        known time, or two written at the same instant, order by id."""
        at_a, at_b = self.written.get(a), self.written.get(b)
        if at_a is None or at_b is None or at_a == at_b:
            return (min(a, b), max(a, b))
        return (b, a) if at_b < at_a else (a, b)


def _read_events(session, found: _Sources) -> None:  # noqa: ANN001
    """1. The events, oldest first: a found pair is a finding; accepted,
    dismissed and reopened move the pair's verdict in the order they happened."""
    from sqlalchemy import select

    from tessellate.core.database import AuditLog

    for event in session.scalars(select(AuditLog).where(AuditLog.entity_type == EVENT_TYPE).order_by(AuditLog.id)):
        body = event.payload or {}
        try:
            a, b = int(body["earlier_id"]), int(body["later_id"])
        except (KeyError, TypeError, ValueError):
            continue
        key = pair_key(a, b)
        if event.action == FOUND:
            found.findings.setdefault(key, []).append((
                event.created_at, _SOURCE_RANK["scan"], event.id,
                _finding(
                    key, a, b, reason=str(body.get("reason") or ""), model=str(body.get("model") or "local"),
                    confidence=float(body.get("confidence") or 0.0), computed_at=event.created_at,
                    source="scan", source_id=None, event_id=event.id,
                ),
            ))
        elif event.action == ACCEPTED:
            found.accepted_events.add(key)
            found.dismissed.discard(key)
        elif event.action == DISMISSED:
            found.dismissed.add(key)
        elif event.action == REOPENED:
            found.accepted_events.discard(key)
            found.dismissed.discard(key)


def _night_fact_pair(fact) -> tuple[int, str] | None:  # noqa: ANN001
    """`(other note id, reason)` from a tension fact's payload, or None when
    the payload does not name another note (a bad row is skipped, not raised)."""
    import json

    try:
        body = json.loads(fact.payload or "{}") or {}
        return int(body["other_entry_id"]), str(body.get("reason") or "")
    except (KeyError, TypeError, ValueError):
        return None


def _read_night_facts(session, found: _Sources) -> None:  # noqa: ANN001
    """2. The night shift's tension facts (a tombstone is a dismissal)."""
    from sqlalchemy import select

    from tessellate.core.database import AuditLog, DerivedFact

    for fact in session.scalars(select(DerivedFact).where(DerivedFact.kind == "tension").order_by(DerivedFact.id)):
        named = _night_fact_pair(fact)
        if named is None or named[0] == fact.entry_id:
            continue
        other, reason = named
        key = pair_key(fact.entry_id, other)
        earlier, later = found.ordered(other, fact.entry_id)
        #: The version it read: the later note's newest event at the time.
        event_id = session.scalar(
            select(AuditLog.id)
            .where(
                AuditLog.entity_type == "entry",
                AuditLog.entity_id == later,
                AuditLog.created_at <= fact.computed_at,
            )
            .order_by(AuditLog.id.desc())
            .limit(1)
        )
        found.findings.setdefault(key, []).append((
            fact.computed_at, _SOURCE_RANK["night"], fact.id,
            _finding(
                key, earlier, later, reason=reason, model=fact.model or "local",
                confidence=float(fact.confidence or 0.0), computed_at=fact.computed_at,
                source="night", source_id=fact.id, event_id=event_id,
            ),
        ))
        if fact.deleted_at is not None:
            found.dismissed.add(key)


def _link_event_id(session, link) -> int | None:  # noqa: ANN001
    """The `linked` event that made this link, or None for a link with none."""
    from sqlalchemy import select

    from tessellate.core.database import AuditLog

    for event in session.scalars(
        select(AuditLog)
        .where(
            AuditLog.entity_type == "entry",
            AuditLog.entity_id == link.source_entry_id,
            AuditLog.action == "linked",
        )
        .order_by(AuditLog.id)
    ):
        if ((event.payload or {}).get("after") or {}).get("link_id") == link.id:
            return event.id
    return None


def comparable_notes(session, embeddings) -> tuple[dict, dict, set]:  # noqa: ANN001
    """The notes worth comparing by id, their vectors, and the pairs already linked as contradicting."""
    from sqlalchemy import select

    from tessellate.ai.embeddings import bytes_to_vector
    from tessellate.core.database import EmbeddingRecord, EntryLink
    from tessellate.entry import manager

    by_id = {e.id: e for e in manager.list_entries(session) if not e.is_private and not e.is_board}
    records = session.execute(
        select(EmbeddingRecord.entry_id, EmbeddingRecord.embedding).where(
            EmbeddingRecord.model_version == embeddings.backend_id()
        )
    ).all()
    vectors = {eid: bytes_to_vector(blob) for eid, blob in records if eid in by_id}
    already = {
        frozenset((link.source_entry_id, link.target_entry_id))
        for link in session.scalars(select(EntryLink).where(EntryLink.link_type == "contradicts"))
    }
    return by_id, vectors, already


def agent_row(tension: Tension) -> dict:
    """One tension as the agent's `find_contradictions` result reports it."""
    return {
        "earlier_note_id": tension.earlier_id,
        "later_note_id": tension.later_id,
        "what_they_disagree_about": tension.explanation,
        "earlier": tension.earlier_excerpt,
        "later": tension.later_excerpt,
        "written_apart_days": tension.gap_days,
    }


def _read_links(session, found: _Sources) -> None:  # noqa: ANN001
    """3. The links: a `contradicts` link is the accepted state, whoever made
    it. A link whose pair nothing else found becomes a finding of its own."""
    from sqlalchemy import select

    from tessellate.core.database import EntryLink

    for link in session.scalars(select(EntryLink).where(EntryLink.link_type == "contradicts").order_by(EntryLink.id)):
        found.linked.setdefault(pair_key(link.source_entry_id, link.target_entry_id), link)
    for key, link in found.linked.items():
        if key in found.findings:
            continue
        earlier, later = found.ordered(link.source_entry_id, link.target_entry_id)
        found.findings[key] = [(
            link.created_at, _SOURCE_RANK["link"], link.id,
            _finding(
                key, earlier, later, reason="", model="person", confidence=1.0,
                computed_at=link.created_at, source="link", source_id=link.id,
                event_id=_link_event_id(session, link),
            ),
        )]


def _status(key: str, found: _Sources) -> str:
    if key in found.linked:
        return "accepted"
    if key in found.dismissed or key in found.accepted_events:
        # Accepted once and the link since taken away is the person
        # changing their mind; it is not offered again either.
        return "dismissed"
    return "open"


def derive(session) -> list[dict]:  # noqa: ANN001
    """The table's rows, from the sources alone, in pair order. Reads and
    returns, so `rebuild` and the determinism test share it."""
    from sqlalchemy import select

    with _AllSpaces(session):
        found = _Sources(written=dict(session.execute(select(Entry.id, Entry.created_at)).all()))
        _read_events(session, found)
        _read_night_facts(session, found)
        _read_links(session, found)

    rows = []
    for key in sorted(found.findings, key=lambda k: tuple(int(x) for x in k.split(":"))):
        first = min(found.findings[key], key=lambda f: (f[0] is None, f[0] or datetime.min, f[1], f[2]))[3]
        rows.append({**first, "status": _status(key, found)})
    return rows


#: The sources version the table was last built from, per process. A note of
#: "is the table current", not a copy of the table: the table is in the
#: database.
_built: dict[str, bool] = {}


def rebuild(session) -> int:  # noqa: ANN001
    """Empty the table and fill it from the sources. Returns the row count."""
    from tessellate.core.database import DerivedTension

    rows = derive(session)
    session.query(DerivedTension).delete(synchronize_session=False)
    session.add_all(DerivedTension(**row) for row in rows)
    session.flush()
    _built.clear()
    _built[str(sources_version(session))] = True
    return len(rows)


def refresh(session) -> None:  # noqa: ANN001
    """Rebuild when a source moved since the last build, else nothing."""
    if not _built.get(str(sources_version(session))):
        rebuild(session)


def listing(session, *, status: str | None = "open", limit: int = 20) -> tuple[list, dict[str, int]]:  # noqa: ANN001
    """The rows a person can see (both notes live, not private, in this
    space), newest finding first, and the count per status."""
    from sqlalchemy import select
    from sqlalchemy.orm import aliased

    from tessellate.core.database import DerivedTension, Entry

    refresh(session)
    earlier, later = aliased(Entry), aliased(Entry)
    visible = (
        select(DerivedTension)
        .join(earlier, earlier.id == DerivedTension.earlier_id)
        .join(later, later.id == DerivedTension.later_id)
        .where(
            earlier.is_deleted.is_(False),
            earlier.is_private.is_(False),
            later.is_deleted.is_(False),
            later.is_private.is_(False),
        )
    )
    every = list(session.scalars(visible))
    counts = {"open": 0, "accepted": 0, "dismissed": 0}
    for row in every:
        counts[row.status] = counts.get(row.status, 0) + 1
    chosen = [row for row in every if status is None or row.status == status]
    chosen.sort(key=lambda r: (r.computed_at is not None, r.computed_at or datetime.min, r.id), reverse=True)
    return chosen[:limit], counts
