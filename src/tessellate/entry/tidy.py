"""Tidy: the notebook's housekeeping as rules a person can read (INBOX 691).

The owner: "a way to better sort through links and tags without the ai ...
manual or automated ways to manage notes and other things systematically
and programmatically nearly up to par with the ai but as an option if the ai
isnt available or as an alternative". The AI's housekeeping (the autonomous
pass's auto tag, link and dedupe) needs a model and is off by default; what
existed without one was scattered (the tag manager's look-alikes, Find
duplicates in Settings, `is:review` typed into the filter) and nothing at all
for weak links, tags another actor added, short notes or reminders long past.

Each review here is **a rule, a list and one undo**:

- `rows(session, key, level)` is the rule: what it finds, each row with a
  one-line why (`detail`) and what applying would do (`change`). Every rule is
  deterministic and needs no model; the same notebook gives the same rows.
- `apply(session, key, ids, level)` acts on the rows the person ticked,
  recomputed here rather than trusted from the client: a row that no longer
  matches (somebody edited the note meanwhile) is skipped, not forced.
- Every apply writes one `tidied` row in the activity log (entity `tidy`, no
  entity id, so the compactor leaves its payload alone) holding exactly what
  is needed to put the batch back; `undo(session, undo_id)` does that once
  (twice is a no-op) and never overwrites something changed since.

**Automatic** (decision 3): a rule that is safe to run unattended may be
switched on (`tidy_auto`, off by default); `run_automatic` runs after a note
is filed, as `system:tidy`, and its runs are in the same history with the
same Undo. Merging and binning notes are never automatic: a person decides
those, whatever a switch says.

The link reason pass (`respecify_all`) is also a durable job (`jobstore`
kind `tidy-link-reasons`), in chunks, stopped between chunks by
`request_stop` (the Tasks panel's Quit, `core/bgtasks`).
"""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, or_, select

from tessellate.core import events
from tessellate.core.database import AuditLog, Entry, EntryLink, Reminder, utcnow
from tessellate.entry import link_facts, link_wording, manager

logger = logging.getLogger("tessellate.tidy")

ACTOR = "system:tidy"
PREF_AUTO = "tidy_auto"
#: Rows a person dismissed for good, `{review key: [row ids]}` (INBOX 783).
PREF_DISMISSED = "tidy_dismissed"
#: Dismissed rows kept per review: a long-lived notebook never grows the file.
MAX_DISMISSED = 2000
LOG_ACTION = "tidied"
LOG_ENTITY = "tidy"
#: The actors whose writes are a person's own (`events.ACTOR_USER*`).
PERSON = ("user", "user+ai")

#: A reminder this long past its day, never done and not repeating, is stale.
STALE_DAYS = 14
#: A note this short, in characters or in words, is "empty or very short".
SHORT_CHARS = 12
SHORT_WORDS = 2
#: The auto-tag review's bars: a tag that fits less than this is listed.
FIT_LEVELS = {"low": 0.25, "medium": 0.5, "high": 0.75}
#: The weak-link review's bars: which strengths are listed.
STRENGTH_LEVELS = {"weak": ("weak",), "some": ("weak", "some"), "strong": ("weak", "some", "strong")}
#: Rows one review lists at most; the count still says how many there are.
MAX_ROWS = 300


@dataclass(frozen=True)
class Review:
    key: str
    label: str
    about: str
    #: Safe to run unattended after filing (decision 3).
    can_auto: bool
    #: Ticked when listed: a change that only adds or renames, or is undone
    #: by a tick. Rows that remove or bin start unticked.
    ticked: bool
    levels: tuple[str, ...] = ()
    level: str = ""
    #: One short line for the overview row: what the review looks for. `about`
    #: says it again at greater length and names what Apply will change.
    finds: str = ""


REVIEWS: dict[str, Review] = {
    r.key: r
    for r in (
        Review(
            "link-reasons", "Links to explain",
            "These links only say “similar in meaning”. Add reasons gives each one what its two notes share: a tag, a name or a week.",
            True, True, finds="Links that only say “similar in meaning”.",
        ),
        Review(
            "weak-links", "Weak automatic links",
            "Links made from likeness alone, with nothing else in common and a weak score. Remove links takes the ticked ones out; the notes stay.",
            True, False, tuple(STRENGTH_LEVELS), "weak", finds="Links made from likeness alone.",
        ),
        Review(
            "auto-tags", "Tags Atlas added",
            "Tags written by Atlas or a background pass, never changed by you, that fit their note poorly. Remove tags takes the ticked ones off their notes.",
            True, False, tuple(FIT_LEVELS), "medium", finds="Tags Atlas wrote that fit their note poorly.",
        ),
        Review(
            "rare-tags", "Tags used once",
            "Tags on one note only: a typo, or a label nothing else shares. Remove tags takes the ticked ones off their note.",
            False, False, finds="Tags on a single note.",
        ),
        Review(
            "lookalike-tags", "Tags that look alike",
            "Tag names that differ only in case, spacing, hyphens or a plural. Merge tags turns each set into one tag on every note that had any of them.",
            True, True, finds="Tag names that differ only in spelling.",
        ),
        Review(
            "uncategorised", "Notes without a category",
            "Notes in Uncategorised, with the category their words point to when there is a clear one. Move notes files each ticked note there.",
            True, True, finds="Notes still in Uncategorised.",
        ),
        Review(
            "duplicates", "Near-duplicate notes",
            "Notes that say much the same thing, compared word by word. Merge notes keeps the first of each set, adds the others' words and tags to it, and moves the others to the bin.",
            False, False, finds="Notes that say much the same thing.",
        ),
        Review(
            "similar-categories", "Categories that overlap",
            "Two categories about the same topics, in their words and in meaning. Merge categories moves the smaller one's notes into the larger and remembers it as your name for those topics; Undo puts them back.",
            False, False, finds="Categories that hold the same kind of note.",
        ),
        Review(
            "category-names", "Category names",
            "A category whose notes are mostly about one topic it is not named for. Rename gives it the topic list's name for them; Undo puts the old name back.",
            False, False, finds="Categories whose name hides what they hold.",
        ),
        Review(
            "short-notes", "Empty or very short notes",
            "Notes of a word or two, with no links, files or pin. Move to bin sends each ticked note to the recycle bin, where it can be restored.",
            False, False, finds="Notes of a word or two with nothing attached.",
        ),
        Review(
            "stale-reminders", "Reminders long past",
            f"Reminders more than {STALE_DAYS} days past their day, never done and not repeating. Mark done ticks off each ticked reminder.",
            True, True, finds="Reminders weeks past their day and never done.",
        ),
    )
}


# --- pure rules ---------------------------------------------------------------


def lookalike_key(name: str) -> str:
    """The tag manager's look-alike key (`manageLookAlikeKey`, tag-manager.js):
    case, spaces, hyphens, underscores and dots set aside, a plural made
    singular. Kept identical so the two surfaces agree on what looks alike."""
    key = re.sub(r"[\s_\-.]+", "", str(name).lower())
    if len(key) > 3 and key.endswith("ies"):
        key = key[:-3] + "y"
    elif len(key) > 3 and key.endswith("s") and not key.endswith("ss"):
        key = key[:-1]
    return key


def lookalike_groups(counts: dict[str, int]) -> list[list[str]]:
    """Groups of tag names that look like one, busiest first in each."""
    groups: dict[str, list[str]] = {}
    for name in counts:
        key = lookalike_key(name)
        if key:
            groups.setdefault(key, []).append(name)
    out = [sorted(g, key=lambda n: (-counts[n], n)) for g in groups.values() if len(g) > 1]
    return sorted(out, key=lambda g: g[0].casefold())


_MARKS = re.compile(r"[#>*_`~\-\[\]()|!:]+")


def is_short(text: str) -> bool:
    """A word or two and nothing else. A picture or a link is not short."""
    raw = text or ""
    if re.search(r"!\[[^\]]*\]\(|\]\(|https?://|\[\[", raw):
        return False
    plain = " ".join(_MARKS.sub(" ", raw).split())
    return len(plain) < SHORT_CHARS or len(plain.split()) <= SHORT_WORDS


def tag_fit(tag: str, words: set[str], peers_with: int, peers: int) -> float:
    """How well a tag fits its note, 0..1, from the notebook alone: 1 when the
    note's own words say it, otherwise the share of the other notes in its
    category that carry it."""
    tag_words = link_wording.tokens(tag.replace("-", " ").replace("_", " ").replace("/", " "))
    if tag_words and all(w in words for w in tag_words):
        return 1.0
    return round(peers_with / peers, 2) if peers else 0.0


# --- helpers -----------------------------------------------------------------


def _tags(entry: Entry) -> list[str]:
    return manager.entry_tags(entry)


def _title(entry: Entry | None) -> str:
    if entry is None:
        return "a note"
    return link_wording.title(entry.content or "", limit=48) or "Untitled note"


def _live_entries(session):  # noqa: ANN001, ANN202
    return session.scalars(
        select(Entry).where(
            Entry.is_deleted == False,  # noqa: E712
            Entry.is_private == False,  # noqa: E712
            Entry.is_board == False,  # noqa: E712
            Entry.is_draft == False,  # noqa: E712
        )
    ).all()


def _percent(x: float) -> str:
    return f"{round(x * 100)}%"


def _row(id_: str, title: str, detail: str, change: str, entry_ids: list[int], selectable: bool = True) -> dict:
    return {"id": id_, "title": title, "detail": detail, "change": change, "entry_ids": entry_ids, "selectable": selectable}


def _generic_links(session) -> list[tuple[EntryLink, Entry, Entry]]:  # noqa: ANN001
    """Deduced links (a score, not a person's words) still reading the
    generic reason, with both ends live and not private."""
    links = session.scalars(select(EntryLink).where(EntryLink.reason_confidence.is_not(None))).all()
    links = [lk for lk in links if link_wording.is_generic(lk.reason)]
    ids = {i for lk in links for i in (lk.source_entry_id, lk.target_entry_id)}
    ends = {
        e.id: e
        for e in session.scalars(select(Entry).where(Entry.id.in_(ids), Entry.is_deleted == False))  # noqa: E712
        if not e.is_private
    }
    return [(lk, ends[lk.source_entry_id], ends[lk.target_entry_id]) for lk in links if lk.source_entry_id in ends and lk.target_entry_id in ends]


def _strength_detail(score: float | None) -> str:
    word = link_wording.strength_word(score) or "unknown"
    return f"Similar in meaning, {word} likeness ({_percent(score or 0)})"


# --- the rules, one per review --------------------------------------------------


def _rows_link_reasons(session, _level: str) -> list[dict]:  # noqa: ANN001
    found = _generic_links(session)
    if not found:
        return []
    facts = link_facts.notes(session, sorted({i for lk, _a, _b in found for i in (lk.source_entry_id, lk.target_entry_id)}))
    counts = link_facts.counts(session)
    rows = []
    for link, a, b in found:
        if a.id not in facts or b.id not in facts:
            continue
        reason = link_wording.specific_reason(facts[a.id], facts[b.id], counts)
        if reason:
            rows.append(_row(f"link:{link.id}", f"{_title(a)} and {_title(b)}", _strength_detail(link.reason_confidence), reason, [a.id, b.id]))
    return rows


def _rows_weak_links(session, level: str) -> list[dict]:  # noqa: ANN001
    allowed = STRENGTH_LEVELS.get(level, STRENGTH_LEVELS["weak"])
    rows = []
    for link, a, b in _generic_links(session):
        if link_wording.strength_word(link.reason_confidence) in allowed:
            rows.append(_row(f"link:{link.id}", f"{_title(a)} and {_title(b)}", _strength_detail(link.reason_confidence), "Unlink", [a.id, b.id]))
    rows.sort(key=lambda r: r["detail"])
    return rows


def _auto_added(session) -> dict[int, dict[str, str]]:  # noqa: ANN001
    """{entry id: {tag casefold: actor}} for tags another actor put on a note
    whose tags no person has changed since."""
    added: dict[int, dict[str, tuple[str, int]]] = {}
    rows = session.execute(
        select(AuditLog.id, AuditLog.entity_id, AuditLog.actor, AuditLog.payload, AuditLog.action).where(
            AuditLog.entity_type == "entry",
            AuditLog.action.in_(("created", "edited")),
            AuditLog.entity_id.is_not(None),
        ).order_by(AuditLog.id)
    ).all()
    for row_id, entry_id, actor, payload, _action in rows:
        payload = payload if isinstance(payload, dict) else {}
        after = payload.get("after") if isinstance(payload.get("after"), dict) else {}
        if "tags" not in after:
            continue
        before = payload.get("before") if isinstance(payload.get("before"), dict) else {}
        if actor == ACTOR:
            continue  # Tidy's own removal or undo says nothing about who chose a tag
        if (actor or "user") in PERSON:
            # The person changed this note's tags: everything earlier is theirs now.
            added.pop(entry_id, None)
            continue
        new = {str(t).casefold() for t in (after.get("tags") or [])} - {str(t).casefold() for t in (before.get("tags") or [])}
        mine = added.setdefault(entry_id, {})
        for tag in new:
            mine[tag] = (actor, row_id)
    return {eid: {tag: who for tag, (who, _id) in tags.items()} for eid, tags in added.items() if tags}


def _actor_words(actor: str) -> str:
    if actor.startswith("ai:"):
        return "Atlas"
    if actor.startswith("system:"):
        return "a background pass"
    if actor.startswith("agent:"):
        return "a connected assistant"
    return actor


def _rows_auto_tags(session, level: str) -> list[dict]:  # noqa: ANN001
    bar = FIT_LEVELS.get(level, FIT_LEVELS["medium"])
    added = _auto_added(session)
    if not added:
        return []
    entries = {e.id: e for e in _live_entries(session)}
    by_category: dict[int | None, list[Entry]] = {}
    for e in entries.values():
        by_category.setdefault(e.category_id, []).append(e)
    names = manager.bulk_category_names(session, list(entries.values()))
    rows = []
    for entry_id, tags in sorted(added.items()):
        entry = entries.get(entry_id)
        if entry is None:
            continue
        words = set(link_wording.tokens(entry.content or ""))
        peers = [p for p in by_category.get(entry.category_id, []) if p.id != entry.id]
        for tag in _tags(entry):
            actor = tags.get(tag.casefold())
            if actor is None:
                continue
            peers_with = sum(1 for p in peers if tag.casefold() in {t.casefold() for t in _tags(p)})
            fit = tag_fit(tag, words, peers_with, len(peers))
            if fit >= bar:
                continue
            category = names.get(entry.category_id, manager.UNCATEGORISED)
            detail = f"Added by {_actor_words(actor)} to “{_title(entry)}”; not in its words, on {peers_with} of {len(peers)} other {category} notes"
            rows.append(_row(f"tag:{entry.id}:{tag}", f"#{tag}", detail, f"Remove #{tag} from this note", [entry.id]))
    return rows


def _tag_counts(session) -> tuple[dict[str, int], dict[str, list[Entry]]]:  # noqa: ANN001
    counts: dict[str, int] = {}
    holders: dict[str, list[Entry]] = {}
    for entry in _live_entries(session):
        for tag in _tags(entry):
            counts[tag] = counts.get(tag, 0) + 1
            holders.setdefault(tag, []).append(entry)
    return counts, holders


def _rows_rare_tags(session, _level: str) -> list[dict]:  # noqa: ANN001
    counts, holders = _tag_counts(session)
    rows = [
        _row(f"tag:{holders[t][0].id}:{t}", f"#{t}", f"Only on “{_title(holders[t][0])}”", "Remove the tag", [holders[t][0].id])
        for t, n in counts.items()
        if n == 1
    ]
    return sorted(rows, key=lambda r: r["title"].casefold())


def _rows_lookalike_tags(session, _level: str) -> list[dict]:  # noqa: ANN001
    counts, _holders = _tag_counts(session)
    rows = []
    for group in lookalike_groups(counts):
        keeper, others = group[0], group[1:]
        notes = sum(counts[n] for n in group)
        rows.append(_row(
            f"tags:{lookalike_key(keeper)}",
            ", ".join(f"#{n}" for n in group),
            f"{notes} notes between them; the same name once case, spacing and plurals are set aside",
            f"Merge {', '.join('#' + n for n in others)} into #{keeper}",
            [],
        ))
    return rows


def _rows_uncategorised(session, _level: str) -> list[dict]:  # noqa: ANN001
    from tessellate.ai import lexical_filing

    entries = [e for e in _live_entries(session)]
    names = manager.bulk_category_names(session, entries)
    rows = []
    for entry in entries:
        if names.get(entry.category_id, manager.UNCATEGORISED) != manager.UNCATEGORISED:
            continue
        decision = lexical_filing.decide(session, entry.content or "", exclude_entry_id=entry.id)
        best = decision.filed or (decision.ranked[0] if decision.held and decision.ranked else None)
        if best is not None and best.name != manager.UNCATEGORISED:
            row = _row(f"note:{entry.id}", _title(entry), best.why, f"Move to {best.name}", [entry.id])
            if decision.held:
                #: A sensitive note (WORLD_CLASS 23, decision 6): listed for the
                #: person, unticked, and never moved by the automatic run.
                row["detail"] = f"Waits for you: it reads as {decision.sensitive}. {best.why}"
                row["sensitive"] = True
            rows.append(row)
        else:
            rows.append(_row(f"note:{entry.id}", _title(entry), "No clear match in your other notes", "File it by hand", [entry.id], selectable=False))
    return rows


#: WORLD_CLASS 23, decision 4: two categories are offered as one when their
#: topic profiles overlap this much and their notes sit this close in meaning
#: (cosine distance of the two categories' mean vectors). With no search model
#: there is no meaning to measure, so the topics alone must overlap
#: `MERGE_TOPIC_OVERLAP_ALONE`, and the row says so.
MERGE_TOPIC_OVERLAP = 0.6
MERGE_CENTROID_DISTANCE = 0.15
MERGE_TOPIC_OVERLAP_ALONE = 0.8
#: A rename is offered when one topic holds this share of what a category's
#: notes name, over at least `RENAME_MIN_NOTES` notes.
RENAME_SHARE = 0.6
RENAME_MIN_NOTES = 3


def _category_ids(session) -> dict[str, int]:  # noqa: ANN001
    from tessellate.core.database import Category

    return {name: id_ for id_, name in session.execute(select(Category.id, Category.name)).all()}


def _meaning_centroids(session) -> dict | None:  # noqa: ANN001
    """Each category's mean note vector, unit length, from the search
    model's matrix; None when the model is not loaded (decision 4's second
    measure is then unavailable, never guessed)."""
    from tessellate.ai import janitor
    from tessellate.core import deps

    try:
        embeddings = deps.get_embeddings()
        if not embeddings.is_ready():
            return None
        labelled = janitor._labelled_vectors(session, embeddings)
    except Exception:  # noqa: BLE001 - no model is a state; the review falls back to topics
        logger.info("no search model for the overlap review; comparing topics alone", exc_info=True)
        return None
    if labelled is None or not labelled.names:
        return None
    import numpy as np

    centroids = {}
    for name in set(labelled.names):
        rows = labelled.rows[[i for i, n in enumerate(labelled.names) if n == name and not labelled.private[i]]]
        if rows.shape[0]:
            mean = rows.mean(axis=0)
            norm = float(np.linalg.norm(mean))
            if norm:
                centroids[name] = mean / norm
    return centroids


def _top_topics(profile: dict[str, float], other: dict[str, float] | None = None, n: int = 2) -> list[str]:
    keys = [t for t in profile if other is None or t in other]
    return sorted(keys, key=lambda t: -(profile[t] * (other or {}).get(t, 1.0)))[:n]


def _rows_similar_categories(session, _level: str) -> list[dict]:  # noqa: ANN001
    """One row per group of categories that overlap: pairs that clear both
    measures join into a group (Gym, Fitness and Misc together, not three
    rows that undo one another), kept under its largest category."""
    from tessellate.ai import lexical_filing

    profiles = lexical_filing.category_profiles(session)
    ids = _category_ids(session)
    centroids = _meaning_centroids(session)
    names = sorted(profiles, key=str.casefold)
    group: dict[str, str] = {name: name for name in names}

    def root(name: str) -> str:
        while group[name] != name:
            name = group[name]
        return name

    measures: dict[frozenset, tuple[float, float | None]] = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            overlap = lexical_filing.topic_overlap(profiles[a][1], profiles[b][1])
            if overlap < MERGE_TOPIC_OVERLAP:
                continue
            distance = None
            if centroids is not None and a in centroids and b in centroids:
                distance = 1.0 - float(centroids[a] @ centroids[b])
                if distance > MERGE_CENTROID_DISTANCE:
                    continue
            elif overlap < MERGE_TOPIC_OVERLAP_ALONE:
                continue
            measures[frozenset((a, b))] = (overlap, distance)
            group[root(a)] = root(b)
    members: dict[str, list[str]] = {}
    for name in names:
        members.setdefault(root(name), []).append(name)
    rows = []
    for together in members.values():
        if len(together) < 2:
            continue
        keep, *folds = sorted(together, key=lambda n: (-profiles[n][0], n.casefold()))
        pairs = [m for pair, m in measures.items() if pair <= set(together)]
        overlap = min(m[0] for m in pairs)
        distances = [m[1] for m in pairs if m[1] is not None]
        measure = (
            f"topics overlap {overlap:.2f}, {max(distances):.2f} apart in meaning"
            if distances and len(distances) == len(pairs)
            else f"topics overlap {overlap:.2f} (by topics alone: the search model is off)"
        )
        shared = ", ".join(_top_topics(profiles[keep][1], profiles[folds[0]][1]))
        folded = " and ".join(folds)
        counts = ", ".join(str(profiles[n][0]) for n in (keep, *folds))
        rows.append(_row(
            f"merge:{'-'.join(str(ids[n]) for n in folds)}:{ids[keep]}",
            f"Merge {folded} into {keep}?",
            f"{counts} notes, all about {shared}; {measure}",
            f"Merge {folded} into {keep}",
            [],
        ))
    return rows


def _rows_category_names(session, _level: str) -> list[dict]:  # noqa: ANN001
    from tessellate.ai import lexical_filing, taxonomy

    profiles = lexical_filing.category_profiles(session)
    ids = _category_ids(session)
    taken = {name.casefold() for name in ids}
    rows = []
    for name in sorted(profiles, key=str.casefold):
        count, _profile, own = profiles[name]
        total = sum(own.values())
        if count < RENAME_MIN_NOTES or not total:
            continue
        topic = max(own, key=own.__getitem__)
        share = own[topic] / total
        if share < RENAME_SHARE or topic in taxonomy.name_topics(name) or topic.casefold() in taken:
            continue
        rows.append(_row(
            f"rename:{ids[name]}",
            f"Rename {name} to {topic}?",
            f"{round(share * 100)}% of what its {count} notes are about is {topic}",
            f"Rename to {topic}",
            [],
        ))
    return rows


def _count_uncategorised(session) -> int:  # noqa: ANN001
    """How many rows `_rows_uncategorised` would list, without building them.

    Every uncategorised note becomes a row (one that points at a category or
    "no clear match"), so the badge's count is the number of such notes. Making
    the rows matches each note's words against every other note, 2.3 ms apiece:
    11.5 s of the 23 s `GET /tidy` took at 5,000 notes (audit 2026-10-10), paid
    on every redraw of the notes list just to print a number."""
    entries = _live_entries(session)
    names = manager.bulk_category_names(session, entries)
    return sum(1 for e in entries if names.get(e.category_id, manager.UNCATEGORISED) == manager.UNCATEGORISED)


def _rows_duplicates(session, _level: str) -> list[dict]:  # noqa: ANN001
    from tessellate.entry import duplicates

    rows = []
    for group in duplicates.find_duplicates(session):
        ids = [m["id"] for m in group["entries"]]
        others = len(ids) - 1
        titles = [link_wording.title(m["content"] or "", limit=40) or "Untitled note" for m in group["entries"]]
        rows.append(_row(
            "dupe:" + "-".join(str(i) for i in ids),
            " and ".join(titles[:2]) + (f" and {len(titles) - 2} more" if len(titles) > 2 else ""),
            f"{_percent(group['similarity'])} of their words in common",
            f"Merge into one note; the other{'s go' if others > 1 else ' goes'} to the bin",
            ids,
        ))
    return rows


def _rows_short_notes(session, _level: str) -> list[dict]:  # noqa: ANN001
    entries = [e for e in _live_entries(session) if not e.pinned and is_short(e.content or "")]
    if not entries:
        return []
    ids = [e.id for e in entries]
    linked = {
        i for pair in session.execute(
            select(EntryLink.source_entry_id, EntryLink.target_entry_id).where(
                or_(EntryLink.source_entry_id.in_(ids), EntryLink.target_entry_id.in_(ids))
            )
        ) for i in pair
    }
    threaded = set(session.scalars(select(Entry.parent_id).where(Entry.parent_id.in_(ids))))
    files = manager.documents_for_entries_bulk(session, ids)
    rows = []
    for entry in entries:
        if entry.id in linked or entry.id in threaded or entry.parent_id or files.get(entry.id):
            continue
        shown = " ".join((entry.content or "").split())
        rows.append(_row(f"note:{entry.id}", shown or "Empty note", f"{len(shown)} characters, no links or files", "Move to the bin", [entry.id]))
    return rows


def _rows_stale_reminders(session, _level: str) -> list[dict]:  # noqa: ANN001
    cutoff = utcnow() - timedelta(days=STALE_DAYS)
    found = session.scalars(
        select(Reminder).where(
            Reminder.done == False,  # noqa: E712
            Reminder.deleted_at.is_(None),
            Reminder.recurring == "none",
            Reminder.due_at < cutoff,
        ).order_by(Reminder.due_at)
    ).all()
    now = utcnow()
    rows = []
    for reminder in found:
        due = reminder.due_at if reminder.due_at.tzinfo else reminder.due_at.replace(tzinfo=now.tzinfo)
        days = (now - due).days
        ago = f"{days // 7} weeks" if days >= 14 else f"{days} days"
        rows.append(_row(f"reminder:{reminder.id}", reminder.text, f"Due {ago} ago, never done", "Mark done", [reminder.entry_id] if reminder.entry_id else []))
    return rows


_RULES = {
    "link-reasons": _rows_link_reasons,
    "weak-links": _rows_weak_links,
    "auto-tags": _rows_auto_tags,
    "rare-tags": _rows_rare_tags,
    "lookalike-tags": _rows_lookalike_tags,
    "uncategorised": _rows_uncategorised,
    "duplicates": _rows_duplicates,
    "similar-categories": _rows_similar_categories,
    "category-names": _rows_category_names,
    "short-notes": _rows_short_notes,
    "stale-reminders": _rows_stale_reminders,
}


#: The duplicates count last taken, with the notebook's state when it was
#: taken. The scan is the one review whose cost grows with the square of the
#: notebook (4.7 to 5.8 s at 5,000 notes even after ARCH-11), and the badge
#: asks again on every redraw of the notes list. A different count of live
#: notes, a newer edit or a new id is a different notebook; the same
#: signature is the same answer.
_duplicates_seen: dict = {}


def _count_duplicates(session) -> int:  # noqa: ANN001
    #: The database's own address leads the signature: two notebooks (a test's
    #: throwaway one, a space switch) must never share an answer.
    signature = (str(session.get_bind().url), *session.execute(
        select(func.count(Entry.id), func.max(Entry.updated_at), func.max(Entry.id)).where(
            Entry.is_deleted == False,  # noqa: E712
            Entry.is_private == False,  # noqa: E712
        )
    ).one())
    if _duplicates_seen.get("signature") == signature:
        return _duplicates_seen["count"]
    count = len(_rows_duplicates(session, ""))
    _duplicates_seen.update(signature=signature, count=count)
    return count


#: Reviews whose count is cheaper to take than their rows are to build.
_COUNTERS = {"uncategorised": _count_uncategorised, "duplicates": _count_duplicates}


def rows(session, key: str, level: str | None = None) -> list[dict]:  # noqa: ANN001
    """What review `key` finds now, each row ticked or not by the review's
    default. Raises KeyError for an unknown review."""
    from tessellate.core import deps

    review = REVIEWS[key]
    gone = dismissed_ids(deps.get_config(), key)
    found = [row for row in _RULES[key](session, level or review.level) if row["id"] not in gone]
    for row in found:
        row["ticked"] = review.ticked and row["selectable"] and not row.get("sensitive")
    return found


def dismissed_ids(config, key: str) -> set[str]:  # noqa: ANN001
    """The row ids of review `key` a person dismissed for good."""
    stored = config.get_preference(PREF_DISMISSED, {}) or {}
    return set(stored.get(key) or ())


def dismiss(session, config, key: str, ids: list[str]) -> int:  # noqa: ANN001
    """Dismiss rows review `key` finds now, so they are not listed, counted or
    applied again (INBOX 783). Ids it does not find are ignored. Returns how
    many are dismissed in all."""
    wanted = set(ids)
    found = {row["id"] for row in rows(session, key) if row["id"] in wanted}
    stored = dict(config.get_preference(PREF_DISMISSED, {}) or {})
    kept = list(stored.get(key) or [])
    kept.extend(i for i in sorted(found) if i not in kept)
    stored[key] = kept[-MAX_DISMISSED:]
    config.set_preference(PREF_DISMISSED, stored)
    return len(stored[key])


def undismiss(config, key: str, ids: list[str]) -> int:  # noqa: ANN001
    """Bring dismissed rows back. Returns how many stay dismissed."""
    stored = dict(config.get_preference(PREF_DISMISSED, {}) or {})
    drop = set(ids)
    stored[key] = [i for i in stored.get(key) or [] if i not in drop]
    config.set_preference(PREF_DISMISSED, stored)
    return len(stored[key])


# --- applying, and putting back ---------------------------------------------------


def _id_number(row_id: str) -> int:
    return int(row_id.split(":")[1])


def _apply_link_reasons(session, chosen: list[dict]) -> tuple[int, dict]:  # noqa: ANN001
    undo = []
    for row in chosen:
        link = session.get(EntryLink, _id_number(row["id"]))
        if link is None or not link_wording.is_generic(link.reason):
            continue
        undo.append({"id": link.id, "reason": link.reason, "now": row["change"]})
        link.reason = row["change"]
    return len(undo), {"links": undo}


def _apply_unlink(session, chosen: list[dict]) -> tuple[int, dict]:  # noqa: ANN001
    undo = []
    for row in chosen:
        link = session.get(EntryLink, _id_number(row["id"]))
        if link is None:
            continue
        undo.append({
            "source": link.source_entry_id, "target": link.target_entry_id, "reason": link.reason,
            "reason_confidence": link.reason_confidence, "link_type": link.link_type, "origin": link.origin,
        })
        manager.log_action(session, "unlinked", "entry", link.source_entry_id, f"-> entry {link.target_entry_id}")
        session.delete(link)
    return len(undo), {"unlinked": undo}


def _apply_remove_tags(session, chosen: list[dict]) -> tuple[int, dict]:  # noqa: ANN001
    by_entry: dict[int, set[str]] = {}
    for row in chosen:
        _kind, entry_id, tag = row["id"].split(":", 2)
        by_entry.setdefault(int(entry_id), set()).add(tag.casefold())
    entries = list(session.scalars(select(Entry).where(Entry.id.in_(list(by_entry)))))
    before = manager._retag(session, entries, lambda e, tags: [t for t in tags if t.casefold() not in by_entry[e.id]])
    return sum(len(by_entry[i]) for i in before), {"tags": {str(k): v for k, v in before.items()}}


def _apply_merge_tags(session, chosen: list[dict]) -> tuple[int, dict]:  # noqa: ANN001
    counts, _holders = _tag_counts(session)
    groups = {f"tags:{lookalike_key(g[0])}": g for g in lookalike_groups(counts)}
    before: dict[int, list[str]] = {}
    merged = 0
    for row in chosen:
        group = groups.get(row["id"])
        if not group:
            continue
        for entry_id, tags in manager.rename_tags(session, group[1:], group[0]).items():
            before.setdefault(entry_id, tags)
        merged += 1
    return merged, {"tags": {str(k): v for k, v in before.items()}}


def _apply_move(session, chosen: list[dict]) -> tuple[int, dict]:  # noqa: ANN001
    undo = []
    for row in chosen:
        entry = session.get(Entry, _id_number(row["id"]))
        if entry is None or not row["change"].startswith("Move to "):
            continue
        undo.append({"id": entry.id, "category": manager.category_name_for(session, entry), "user_filed": bool(entry.user_filed)})
        manager.update_entry(session, entry, category_name=row["change"][len("Move to "):])
    return len(undo), {"moved": undo}


def _apply_merge_notes(session, chosen: list[dict]) -> tuple[int, dict]:  # noqa: ANN001
    undo = []
    for row in chosen:
        ids = [int(i) for i in row["id"].split(":", 1)[1].split("-")]
        entries = [session.get(Entry, i) for i in ids]
        if any(e is None or e.is_deleted or e.is_private for e in entries):
            continue
        keeper = entries[0]
        tags: list[str] = []
        for entry in entries:
            for tag in _tags(entry):
                if tag not in tags:
                    tags.append(tag)
        undo.append({"keeper": keeper.id, "content": keeper.content, "tags": _tags(keeper), "binned": ids[1:]})
        manager.record_revision(session, keeper)
        merged = "\n\n---\n\n".join((e.content or "").strip() for e in entries)
        #: The text of the longest note when one already holds all the others'
        #: words (the usual near-duplicate: one note and its longer retelling).
        longest = max(entries, key=lambda e: len(e.content or ""))
        if all(set((e.content or "").split()) <= set((longest.content or "").split()) for e in entries):
            merged = longest.content
        manager.update_entry(session, keeper, content=merged, tags=tags)
        for entry in entries[1:]:
            manager.soft_delete_entry(session, entry)
    return len(undo), {"merged": undo}


def _apply_merge_categories(session, chosen: list[dict]) -> tuple[int, dict]:  # noqa: ANN001
    """Fold each ticked category into the other, and write the folded name's
    topics as the person's alias for the kept one (decision 7), so the next
    note about them files there. Undo moves the notes back (the category is
    made again by name) and takes the aliases away."""
    from tessellate.ai import learning, taxonomy
    from tessellate.core.database import Category

    moved, aliases = [], []
    merged = 0
    for row in chosen:
        _kind, fold_ids, keep_id = row["id"].split(":")
        keep = session.get(Category, int(keep_id))
        if keep is None:
            continue
        for fold_id in fold_ids.split("-"):
            fold = session.get(Category, int(fold_id))
            if fold is None:
                continue
            held = session.scalars(select(Entry).where(Entry.category_id == fold.id, Entry.is_deleted == False))  # noqa: E712
            moved.extend({"id": entry.id, "category": fold.name, "user_filed": bool(entry.user_filed)} for entry in held)
            for topic in taxonomy.name_topics(fold.name):
                correction = learning.record(session, kind="alias", subject={"topic": topic}, from_value=fold.name, to_value=keep.name)
                aliases.append(correction.id)
            manager.rename_category(session, fold.id, keep.name)
        merged += 1
    return merged, {"moved": moved, "aliases": aliases}


def _apply_rename_categories(session, chosen: list[dict]) -> tuple[int, dict]:  # noqa: ANN001
    from tessellate.core.database import Category

    renamed = []
    for row in chosen:
        category = session.get(Category, _id_number(row["id"]))
        if category is None or not row["change"].startswith("Rename to "):
            continue
        new = row["change"][len("Rename to "):]
        entries = [e.id for e in session.scalars(select(Entry).where(Entry.category_id == category.id))]
        renamed.append({"id": category.id, "from": category.name, "to": new, "entries": entries})
        manager.rename_category(session, category.id, new)
    return len(renamed), {"renamed": renamed}


def _apply_bin(session, chosen: list[dict]) -> tuple[int, dict]:  # noqa: ANN001
    binned = []
    for row in chosen:
        entry = session.get(Entry, _id_number(row["id"]))
        if entry is None or entry.is_deleted:
            continue
        manager.soft_delete_entry(session, entry)
        binned.append(entry.id)
    return len(binned), {"binned": binned}


def _apply_done(session, chosen: list[dict]) -> tuple[int, dict]:  # noqa: ANN001
    done = []
    for row in chosen:
        reminder = session.get(Reminder, _id_number(row["id"]))
        if reminder is None or reminder.done:
            continue
        reminder.done = True
        manager.log_action(session, "completed", "reminder", reminder.id, reminder.text[:80])
        done.append(reminder.id)
    return len(done), {"done": done}


_APPLY = {
    "link-reasons": _apply_link_reasons,
    "weak-links": _apply_unlink,
    "auto-tags": _apply_remove_tags,
    "rare-tags": _apply_remove_tags,
    "lookalike-tags": _apply_merge_tags,
    "uncategorised": _apply_move,
    "duplicates": _apply_merge_notes,
    "similar-categories": _apply_merge_categories,
    "category-names": _apply_rename_categories,
    "short-notes": _apply_bin,
    "stale-reminders": _apply_done,
}

_DONE_WORDS = {
    "link-reasons": "Added reasons to {n} link{s}",
    "weak-links": "Removed {n} weak link{s}",
    "auto-tags": "Removed {n} tag{s} Atlas added",
    "rare-tags": "Removed {n} tag{s} used once",
    "lookalike-tags": "Merged {n} set{s} of look-alike tags",
    "uncategorised": "Moved {n} note{s} to a category",
    "duplicates": "Merged {n} set{s} of duplicates",
    "similar-categories": "Merged {n} group{s} of categories",
    "category-names": "Renamed {n} categor{ies}",
    "short-notes": "Moved {n} short note{s} to the bin",
    "stale-reminders": "Marked {n} old reminder{s} done",
}


def _log(session, key: str, applied: int, undo: dict) -> AuditLog | None:  # noqa: ANN001
    message = _DONE_WORDS[key].format(n=applied, s="" if applied == 1 else "s", ies="y" if applied == 1 else "ies")
    return manager.log_action(
        session, LOG_ACTION, LOG_ENTITY, None, message,
        payload={"review": key, "count": applied, "undo": undo, "undone": False},
    )


def _touched_entry_ids(session, undo: dict) -> list[int]:  # noqa: ANN001
    """The notes a run (or its undo) changed, read off the undo payload, so
    the app patches those rows (`refreshEntries(ids)`) and does not read the
    whole notebook again (tests/test_refresh_entries.py). Reminders are not
    notes and are not here."""
    found: set[int] = set()
    for item in undo.get("links", []):
        link = session.get(EntryLink, item["id"])
        if link is not None:
            found.update((link.source_entry_id, link.target_entry_id))
    for item in undo.get("unlinked", []):
        found.update((int(item["source"]), int(item["target"])))
    found.update(int(key) for key in (undo.get("tags") or {}))
    found.update(int(item["id"]) for item in undo.get("moved", []))
    for item in undo.get("merged", []):
        found.add(int(item["keeper"]))
        found.update(int(entry_id) for entry_id in item["binned"])
    found.update(int(entry_id) for entry_id in undo.get("binned", []))
    for item in undo.get("renamed", []):
        found.update(int(entry_id) for entry_id in item["entries"])
    return sorted(found)


def apply(session, key: str, ids: list[str], level: str | None = None) -> dict:  # noqa: ANN001
    """Act on the ticked rows `review` still finds. One transaction, one log
    row, one undo id. Raises KeyError for an unknown review."""
    wanted = set(ids)
    chosen = [r for r in rows(session, key, level) if r["id"] in wanted and r["selectable"]]
    if not chosen:
        return {"applied": 0, "undo_id": None, "message": "Nothing to change."}
    #: The notes' own events are Tidy's (`ACTOR`), whoever asked: so a tag
    #: Tidy took off and an Undo put back is still the one Atlas added, never
    #: mistaken for the person's (`_auto_added` skips Tidy's writes). The
    #: run's own log row below keeps the asker, which is what History shows.
    with events.acting_as(ACTOR):
        applied, undo = _APPLY[key](session, chosen)
    if not applied:
        session.rollback()
        return {"applied": 0, "undo_id": None, "message": "Nothing to change."}
    row = _log(session, key, applied, undo)
    session.commit()
    link_facts.forget()
    return {
        "applied": applied,
        "undo_id": row.id if row is not None else None,
        "message": row.detail if row is not None else "",
        "entry_ids": _touched_entry_ids(session, undo),
    }


def _undo_links(session, undo: dict) -> int:  # noqa: ANN001
    restored = 0
    for item in undo.get("links", []):
        link = session.get(EntryLink, item["id"])
        if link is not None and link.reason == item["now"]:
            link.reason = item["reason"]
            restored += 1
    return restored


def _undo_unlinked(session, undo: dict) -> int:  # noqa: ANN001
    restored = 0
    for item in undo.get("unlinked", []):
        source, target = session.get(Entry, item["source"]), session.get(Entry, item["target"])
        if source is None or target is None:
            continue
        made = manager.create_link(
            session, source, target, reason=item["reason"], link_type=item["link_type"],
            origin=item["origin"], reason_confidence=item["reason_confidence"],
        )
        restored += made is not None
    return restored


def _undo_tags(session, undo: dict) -> int:  # noqa: ANN001
    if not undo.get("tags"):
        return 0
    return len(manager.undo_tag_edit(session, {int(k): v for k, v in undo["tags"].items()}))


def _undo_moved(session, undo: dict) -> int:  # noqa: ANN001
    restored = 0
    for item in undo.get("moved", []):
        entry = session.get(Entry, item["id"])
        if entry is None:
            continue
        manager.update_entry(session, entry, category_name=item["category"])
        entry.user_filed = item["user_filed"]
        restored += 1
    return restored


def _restore_binned(session, entry_id: int) -> bool:  # noqa: ANN001
    """Bring one binned note back; False when it is gone or was never binned."""
    entry = session.get(Entry, entry_id)
    if entry is not None and entry.is_deleted:
        manager.restore_entry(session, entry)
        return True
    return False


def _undo_merged(session, undo: dict) -> int:  # noqa: ANN001
    restored = 0
    for item in undo.get("merged", []):
        keeper = session.get(Entry, item["keeper"])
        if keeper is not None:
            manager.update_entry(session, keeper, content=item["content"], tags=item["tags"])
        for entry_id in item["binned"]:
            _restore_binned(session, entry_id)
        restored += 1
    return restored


def _undo_binned(session, undo: dict) -> int:  # noqa: ANN001
    return sum(_restore_binned(session, entry_id) for entry_id in undo.get("binned", []))


def _undo_renamed(session, undo: dict) -> int:  # noqa: ANN001
    from tessellate.core.database import Category

    restored = 0
    for item in undo.get("renamed", []):
        category = session.get(Category, item["id"])
        if category is not None and category.name == item["to"]:
            manager.rename_category(session, category.id, item["from"])
            restored += 1
    return restored


def _undo_aliases(session, undo: dict) -> int:  # noqa: ANN001
    """Forget the corrections a tidy run taught; they do not count as restored notes."""
    for alias_id in undo.get("aliases", []):
        row = session.get(AuditLog, alias_id)
        if row is not None and row.action == "correction":
            session.delete(row)
    return 0


def _undo_done(session, undo: dict) -> int:  # noqa: ANN001
    restored = 0
    for reminder_id in undo.get("done", []):
        reminder = session.get(Reminder, reminder_id)
        if reminder is not None and reminder.done:
            reminder.done = False
            restored += 1
    return restored


#: The parts of a tidy run's undo record, put back in this order.
_UNDO_STEPS = (
    _undo_links, _undo_unlinked, _undo_tags, _undo_moved, _undo_merged,
    _undo_binned, _undo_renamed, _undo_aliases, _undo_done,
)


def _undo_payload(session, undo: dict) -> int:  # noqa: ANN001
    return sum(step(session, undo) for step in _UNDO_STEPS)


def undo(session, undo_id: int) -> dict:  # noqa: ANN001
    """Put one tidy run back. A second call restores nothing. Raises
    LookupError when `undo_id` is not a tidy run."""
    row = session.get(AuditLog, undo_id)
    if row is None or row.action != LOG_ACTION or row.entity_type != LOG_ENTITY or not isinstance(row.payload, dict):
        raise LookupError("No tidy run with that number.")
    if row.payload.get("undone"):
        return {"restored": 0, "message": "Already undone."}
    stored = row.payload.get("undo") or {}
    touched = _touched_entry_ids(session, stored)
    with events.acting_as(ACTOR):
        restored = _undo_payload(session, stored)
    row.payload = {**row.payload, "undone": True}
    manager.log_action(session, "restored", LOG_ENTITY, None, f"Undid: {row.detail}", payload={"undid": [row.id]})
    session.commit()
    link_facts.forget()
    return {"restored": restored, "message": f"Undid: {row.detail}", "entry_ids": touched}


def history(session, limit: int = 20) -> list[dict]:  # noqa: ANN001
    """The latest tidy runs, newest first, each with its undo id."""
    found = session.scalars(
        select(AuditLog)
        .where(AuditLog.action == LOG_ACTION, AuditLog.entity_type == LOG_ENTITY)
        .order_by(AuditLog.id.desc())
        .limit(limit)
    ).all()
    return [
        {
            "undo_id": row.id,
            "review": (row.payload or {}).get("review"),
            "message": row.detail,
            "count": (row.payload or {}).get("count", 0),
            "automatic": row.actor == ACTOR,
            "undone": bool((row.payload or {}).get("undone")),
            "at": row.created_at.isoformat(),
        }
        for row in found
    ]


# --- the summary, and automation -------------------------------------------------


def auto_settings(config) -> dict[str, bool]:  # noqa: ANN001
    stored = config.get_preference(PREF_AUTO, {}) or {}
    return {key: bool(stored.get(key)) and review.can_auto for key, review in REVIEWS.items()}


def set_auto(config, key: str, on: bool) -> dict[str, bool]:  # noqa: ANN001
    """Switch one review's automatic run. ValueError for a review that only a
    person may apply."""
    review = REVIEWS[key]
    if on and not review.can_auto:
        raise ValueError(f"{review.label} always asks first.")
    stored = dict(config.get_preference(PREF_AUTO, {}) or {})
    stored[key] = bool(on)
    config.set_preference(PREF_AUTO, stored)
    return auto_settings(config)


def summary(session, config) -> dict:  # noqa: ANN001
    """Every review with how many rows it finds now, and the total."""
    autos = auto_settings(config)
    out = []
    for key, review in REVIEWS.items():
        try:
            counter = _COUNTERS.get(key) if not dismissed_ids(config, key) else None
            count = counter(session) if counter else len(rows(session, key))
        except Exception:  # noqa: BLE001  # one rule failing never hides the others
            logger.warning("tidy review %s failed", key, exc_info=True)
            count = 0
        out.append({
            "key": key, "label": review.label, "about": review.about, "finds": review.finds, "count": count,
            "auto": autos[key], "can_auto": review.can_auto, "levels": list(review.levels), "level": review.level,
        })
    return {"reviews": out, "total": sum(r["count"] for r in out)}


#: Seconds between automatic runs: filing a folder of notes runs it once.
AUTO_EVERY = 30.0
#: When the automatic pass last ran (monotonic seconds), held in a dict so
#: no function rebinds a module global.
_auto_clock = {"last": 0.0}
_auto_lock = threading.Lock()


def run_automatic(session, force: bool = False) -> dict[str, int]:  # noqa: ANN001
    """Apply every review switched on, as `system:tidy`. Returns what each
    applied. Called after a note is filed; never raises."""
    from tessellate.core import deps

    with _auto_lock:
        if not force and time.monotonic() - _auto_clock["last"] < AUTO_EVERY:
            return {}
        _auto_clock["last"] = time.monotonic()
    done: dict[str, int] = {}
    try:
        autos = auto_settings(deps.get_config())
        with events.acting_as(ACTOR):
            for key, on in autos.items():
                if not on:
                    continue
                found = [r["id"] for r in rows(session, key) if r["selectable"] and not r.get("sensitive")]
                if found:
                    result = apply(session, key, found)
                    if result["applied"]:
                        done[key] = result["applied"]
    except Exception:  # noqa: BLE001  # housekeeping never fails the filing it follows
        logger.warning("automatic tidy failed", exc_info=True)
        session.rollback()
    return done


# --- the link reason pass as a durable job ---------------------------------------

_stop = threading.Event()
_running = threading.Event()


def request_stop() -> bool:
    """Ask the running pass to stop at its next chunk (`bgtasks`). Also
    stops a pass that has not started yet."""
    _stop.set()
    return _running.is_set()


def is_running() -> bool:
    return _running.is_set()


def respecify_all(workspace_id: str = "default", chunk: int = 200) -> dict:
    """Name every generic link reason the notes can name, in chunks, one
    undoable run. Idempotent (a named link no longer matches), so a resumed
    job repeats nothing. Returns {"named", "stopped", "undo_id"}."""
    from tessellate.core import deps
    from tessellate.core.deps import impersonate_workspace

    from tessellate.core import jobruns

    _running.set()
    named: list[dict] = []
    stopped = False
    undo_id = None
    try:
        with jobruns.job_run("tidy") as run, deps.get_db().session() as session, impersonate_workspace(session, workspace_id):
            found = _rows_link_reasons(session, "")
            run.step(0, len(found), "Naming link reasons")
            run.say(f"{len(found)} link{'' if len(found) == 1 else 's'} with a generic reason to look at.")
            for start in range(0, len(found), max(1, chunk)):
                if _stop.is_set():
                    stopped = True
                    run.say("Stopped between batches. What was named is kept.")
                    break
                applied, undo_part = _apply_link_reasons(session, found[start : start + chunk])
                named.extend(undo_part["links"])
                session.commit()
                run.step(min(start + chunk, len(found)), len(found))
                run.say(f"Looked at {min(start + chunk, len(found))} of {len(found)} links, {len(named)} named so far.")
            if named:
                #: Asked for by a person (Name all in the background), so the
                #: run is theirs in Recent runs, not "automatically".
                row = _log(session, "link-reasons", len(named), {"links": named})
                session.commit()
                undo_id = row.id if row is not None else None
            run.result = f"named {len(named)} link reasons" + (" (stopped)" if stopped else "")
    finally:
        _stop.clear()
        _running.clear()
        link_facts.forget()
    return {"named": len(named), "stopped": stopped, "undo_id": undo_id}
