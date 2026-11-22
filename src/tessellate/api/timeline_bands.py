"""The timeline's lanes: how a page of placed notes is grouped into bands."""

from __future__ import annotations

from collections import defaultdict


#: A row's title is the first line of this, and the row's own CSS ellipsis is
#: what should cut it, at the row's edge. At 120 the cut came first: at 1440 a
#: 1248px title ended "...borrows as loans. #learn…" at x=896, with 430px of
#: empty row before the time (INBOX 464). 240 fills the widest row; the grid
#: and the band cards clamp their own lines.
PREVIEW_CHARS = 240


# One band per category or tag, plus "everything else", a chart with forty
# lanes is not a chart. The cut-off is by note count, so the bands are the
# ones the user actually writes in.
MAX_BANDS = 8
OTHER_BAND = "Everything else"


def _clip(text: str, limit: int = PREVIEW_CHARS) -> str:
    """A preview that says it's a preview. A bare `text[:limit]` slice: 
    what this used to be, cuts a note off mid-word with nothing to say so,
    which is the "no ellipsis" the grid view was reported for: the card
    genuinely had less text than the note, and nothing on screen said that.
    """
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _bands(notes: list[dict], group: str) -> list[dict]:
    """The lanes, biggest first, with a lane for the long tail."""
    if group == "none":
        return [{"name": "All notes", "count": len(notes), "ids": [n["id"] for n in notes]}]
    if group == "thread":
        return _thread_bands(notes)

    members: dict[str, list[int]] = defaultdict(list)
    for note in notes:
        if group == "category":
            members[note["category"]].append(note["id"])
        else:
            for tag in note["tags"] or ["untagged"]:
                members[tag].append(note["id"])

    ranked = sorted(members.items(), key=lambda pair: (-len(pair[1]), pair[0]))
    bands = [
        {"name": name, "count": len(ids), "ids": ids} for name, ids in ranked[:MAX_BANDS]
    ]
    tail = ranked[MAX_BANDS:]
    if tail:
        ids = sorted({note_id for _, group_ids in tail for note_id in group_ids})
        bands.append({"name": OTHER_BAND, "count": len(ids), "ids": ids})
    return bands


THREAD_BAND = "Single notes & smaller threads"


def _thread_bands(notes: list[dict]) -> list[dict]:
    """One lane per thread, a root note and everything that continues it
    (`Entry.parent_id`), the one grouping a grid genuinely cannot show at
    all: a conversation with itself, spread across days or months (§87.6: 
    IDEAS.md's "branching line with offshoots", joined with the thread
    structure `parent_id` already stores). A parent outside the currently
    loaded window (out of the date range, private, or deleted) makes its
    child a root of its own rather than a second query reaching further
    back: the same honest simplification the `days` filter already asks
    the rest of this view to accept.

    A note with no children is not a thread, so it does not get its own
    lane: every such note, plus any real thread beyond the lane cap,
    folds into one shared band, the same shape category/tag grouping
    already uses for its own long tail.
    """
    by_id = {note["id"]: note for note in notes}

    def root_of(note: dict) -> dict:
        seen = {note["id"]}
        current = note
        # A parent chain is at most as deep as the notebook has notes; this
        # caps the walk defensively rather than trusting that shape holds.
        for _ in range(200):
            parent = by_id.get(current.get("parent_id"))
            if parent is None or parent["id"] in seen:
                return current
            seen.add(parent["id"])
            current = parent
        return current

    members: dict[int, list[int]] = defaultdict(list)
    roots: dict[int, dict] = {}
    for note in notes:
        root = root_of(note)
        members[root["id"]].append(note["id"])
        roots[root["id"]] = root

    threads = sorted(
        (item for item in members.items() if len(item[1]) > 1),
        key=lambda pair: (-len(pair[1]), pair[0]),
    )
    bands = [
        {"name": _clip(roots[root_id]["preview"], 40) or f"Note #{root_id}", "count": len(ids), "ids": ids}
        for root_id, ids in threads[:MAX_BANDS]
    ]
    solo_ids = {i for root_id, ids in members.items() if len(ids) == 1 for i in ids}
    overflow_ids = {i for _, ids in threads[MAX_BANDS:] for i in ids}
    other = solo_ids | overflow_ids
    if other:
        bands.append({"name": THREAD_BAND, "count": len(other), "ids": sorted(other)})
    return bands
