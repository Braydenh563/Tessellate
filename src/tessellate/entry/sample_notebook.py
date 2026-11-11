"""The sample notebook (WORLD_CLASS_PLAN 25c, Brief 49).

A new notebook is offered a handful of example notes once, so the first
minutes show what the app does with notes (filed, tagged, linked, dated,
answered from) before a person has written enough of their own to see it.
Every note carries `SAMPLE_TAG`, which is how they are found to be taken away
again: to the bin, in one press, so the removal can itself be undone.

Written for the no-model case: each note names its category, so nothing
waits on filing, and the questions the welcome note suggests are answered
from the notes' own words.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.core.database import LIKE_ESCAPE, Category, Entry
from tessellate.entry import manager_categories
from tessellate.entry.manager import entry_tags

SAMPLE_TAG = "sample-notebook"
#: A literal pattern: the tag is a constant with no `%` or `_` of its own.
_SAMPLE_LIKE = '%"sample-notebook"%'

SAMPLE_NOTES: list[dict] = [
    {
        "category": "Getting started",
        "tags": ["welcome"],
        "content": (
            "About these sample notes\n\n"
            "These notes show what Tessellate does with yours. Ask \"where is the "
            "spare key?\" in Notes, Ask, and the answer comes from the notes, with "
            "no AI model needed. The Graph shows the two Juniper notes linked, and "
            "the Timeline has the boiler service on its date. When you are done, "
            "Remove the sample notes on the Dashboard moves them all to the bin."
        ),
    },
    {
        "category": "Home",
        "tags": ["home"],
        "content": "Spare key\n\nThe spare key is under the blue flowerpot by the back door.",
    },
    {
        "category": "Home",
        "tags": ["home", "bills"],
        "content": (
            "Boiler service\n\nBoiler service booked for 14 November at 9am. The "
            "engineer is Sam from Brightwarm; the reference is BW-2210."
        ),
    },
    {
        "category": "Work",
        "tags": ["work", "juniper"],
        "content": (
            "Project Juniper kickoff\n\nGoal: launch the new booking page by the end "
            "of March. Owner: Priya. Risks: the payments provider and the copy "
            "review. Next steps are in [[Juniper launch checklist]]."
        ),
    },
    {
        "category": "Work",
        "tags": ["work", "juniper"],
        "content": (
            "Juniper launch checklist\n\n"
            "- [x] Domain renewed\n"
            "- [ ] Payments sandbox tested\n"
            "- [ ] Copy reviewed by Lee"
        ),
    },
    {
        "category": "Reading",
        "tags": ["books", "psychology"],
        "content": (
            "Thinking, Fast and Slow\n\nSystem 1 is fast and intuitive, System 2 "
            "slow and deliberate. Most mistakes come from trusting System 1 with a "
            "question that needs System 2."
        ),
    },
    {
        "category": "Health",
        "tags": ["running"],
        "content": (
            "Running log\n\nRan 5 km in 29 minutes on Saturday. The knee felt fine; "
            "try intervals next week."
        ),
    },
    {
        "category": "Recipes",
        "tags": ["recipes", "dinner"],
        "content": (
            "Weeknight dal\n\nRed lentils, an onion, garlic, ginger, cumin, turmeric "
            "and a tin of tomatoes. Simmer for 25 minutes, then finish with lemon "
            "and coriander."
        ),
    },
]


def live_samples(session: Session) -> list[Entry]:
    """The sample notes still in the notebook (not binned)."""
    #: The LIKE narrows; `entry_tags` decides (a tag is JSON in a text column).
    query = select(Entry).where(Entry.is_deleted == False, Entry.tags.like(_SAMPLE_LIKE, escape=LIKE_ESCAPE))  # noqa: E712
    rows = session.scalars(query)
    return [entry for entry in rows if SAMPLE_TAG in entry_tags(entry)]


def category_ids(session: Session) -> set[int]:
    return set(session.scalars(select(Category.id)))


def drop_emptied_categories(session: Session, ids: list[int]) -> int:
    """The categories the sample made (`ids`, kept when it was added), deleted
    once no live note is in them: six empty rows left in the sidebar was the
    sample still there after Remove. A binned sample note in one goes to
    Uncategorised (`manager.delete_category`), restorable as ever."""
    dropped = 0
    for category_id in ids:
        if session.get(Category, category_id) is None:
            continue
        live = session.scalar(
            select(func.count(Entry.id)).where(Entry.category_id == category_id, Entry.is_deleted == False)  # noqa: E712
        )
        if not live:
            manager_categories.delete_category(session, category_id)
            dropped += 1
    return dropped
