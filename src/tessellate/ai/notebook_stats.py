"""Questions about the *shape* of the notebook, answered from SQL.

Asked for directly: *"enhance the semantic search so it can pick up stuff like
if I ask 'what are my most common tags', or maybe 'categories with the most
notes'."*

**Retrieval cannot answer these, and that is not a tuning problem.** Semantic
search finds the notes most *like* a question. "What are my most common tags"
is not like any note, it is a question about the collection, and the honest
answer is a count, not a passage. Before this, such a question went through
retrieval, came back with five arbitrary notes, and the model was told to
answer using only those: so it either declined or invented a ranking from a
five-note sample. Both are worse than saying nothing.

So these are answered by counting, which is what a database is for. Three
properties fall out of that and they are the point:

- **It is exact.** "You have 47 notes" is a fact, not a model's impression.
- **It is instant.** No inference, so it works with the model stopped.
- **It cannot hallucinate.** The numbers come from rows.

The model still gets to *phrase* the answer when it is running (see
`routes_chat`), but the facts are computed here and passed to it, so what it
can do is write a sentence around numbers it did not choose.

Deliberately a heuristic matcher rather than a model call, for exactly the
reason `intent.py` gives about its own classifier: it runs on every message, so
it has to be instant and predictable, and anything it is not sure about falls
through to ordinary retrieval, the worst case is the behaviour that was there
before.
"""

from __future__ import annotations

import difflib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from sqlalchemy import and_, case, exists, func, or_, select
from sqlalchemy.orm import Session, aliased

from tessellate.core.database import Category, Document, Entry, EntryLink, EntryRevision, Reminder, utcnow

#: How many rows a "top N" answer lists. Ten is a glance; fifty is a report
#: nobody reads in a chat bubble, and the follow-up question ("show me all of
#: them") has the Library for an answer.
TOP_N = 10


@dataclass
class StatAnswer:
    """One computed answer, ready to be spoken or rendered.

    `text` is a complete answer on its own, that is what makes this work with
    the model stopped. `facts` is the same information as rows, so a caller can
    render a list or hand the model something to phrase without re-parsing
    prose.
    """

    kind: str
    text: str
    facts: list[dict] = field(default_factory=list)
    #: One acting offer under the answer ({"kind": "open", "label", "surface"}).
    offer: dict | None = None


def _visible(query):
    """Live notes only: binned and private notes are nobody's statistics.

    Private notes are excluded for the reason the rest of the app excludes
    them: a count that changes when a note is made private is a count that
    leaks what is in it.
    """
    #: `is_board` too: a mind map is an `Entry` whose text is its title, and
    #: "how many notes do I have" counted it (the Notes list does not).
    return query.where(
        Entry.deleted_at.is_(None), Entry.is_private.is_(False), Entry.is_board.is_(False)
    )


def _tags_of(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw or "[]")
    except (ValueError, TypeError):
        return []
    return [str(tag).strip() for tag in parsed if str(tag).strip()] if isinstance(parsed, list) else []


def _plural(n: int, word: str) -> str:
    #: "10 categorys" was said in the overview (INBOX 801's NOTEBOOK STATS).
    if n == 1:
        return f"{n} {word}"
    return f"{n} {word[:-1]}ies" if word.endswith("y") and word[-2:-1] not in "aeiou" else f"{n} {word}s"


# --- the questions -----------------------------------------------------------
#
# Each pattern is anchored on the *thing being asked about* rather than on a
# whole sentence shape, because people phrase these a dozen ways ("my most
# common tags", "which tags do I use most", "top tags") and a sentence-shaped
# regex catches one of them.

_TAG_WORDS = r"tags?"
_CATEGORY_WORDS = r"categor(?:y|ies)|folders?|spaces?"
_MOST = r"most|top|common|commonest|frequent|popular|biggest|largest|main"
_COUNT = r"how many|how much|number of|count of|total"


#: **Every word the matchers below actually look for.**
#:
#: Reported: *"the stats semantic search needs to be improved and also it
#: doesnt account for spelling mistakes."* It did not, and could not: every
#: matcher is a regex over literal words, so "catagories", "docuemnts" and
#: "orphens" matched nothing at all and the question fell through to ordinary
#: retrieval: which, as this module's own docstring explains, is exactly the
#: case retrieval answers badly. A typo therefore produced the *worst*
#: available answer rather than a slightly worse one.
#:
#: Written out rather than scraped from the patterns above. Scraping a regex
#: for its literals means parsing regex syntax, and the list would silently
#: lose a word the day someone writes one inside a group this parser does not
#: understand: the "a policy silently refusing the work" shape. A test asserts
#: the two stay in step instead.
_VOCABULARY = (
    "tag tags category categories folder folders space spaces "
    "most top common commonest frequent popular biggest largest main "
    "many much number count total "
    "note notes notebook document documents "
    "untagged tagged missing without "
    "linked links link connected connect unlinked orphan orphans orphaned "
    "busiest active time date day week weeks month months year recent "
    "longest shortest biggest words written writing wordcount "
    "stale forgotten untouched abandoned "
    "together alongside pairs pair "
    "statistics stats"
).split()

#: Words shorter than this are left alone. "tp" is not a typo for "top" in any
#: useful sense: it is as close to "to", "up" and "tag", and correcting it
#: guesses at the user's meaning rather than fixing their spelling.
_SPELLING_MIN_LENGTH = 4

#: How alike a word has to be before it is treated as a misspelling.
#: `difflib`'s ratio, so 0.8 is roughly "one edit in five characters", 
#: "catagories"/"categories" and "docuemnts"/"documents" pass, while "notepad"
#: and "notebook" (0.67) do not, which is the pair that matters: correcting a
#: real word into a different real word is worse than not correcting it.
_SPELLING_CUTOFF = 0.8


def _transposition_of(word: str, known: set[str]) -> str | None:
    """The vocabulary word this is one swapped pair of letters away from.

    Handled separately because `difflib` underrates exactly this typo, which is
    the most common one there is: "tgas"/"tags" scores 0.750 and "notse"/
    "notes" 0.800, both at or under the cutoff, while "task"/"tags", which
    must *not* be corrected ("how many tasks do I have" is a different
    question), also scores 0.750. So the cutoff cannot be lowered to catch
    transpositions without also catching that, and this closes the gap exactly
    rather than approximately.
    """
    for i in range(len(word) - 1):
        swapped = word[:i] + word[i + 1] + word[i] + word[i + 2:]
        if swapped in known:
            return swapped
    return None


def _despell(text: str) -> str:
    """The message with near-misses of the vocabulary corrected.

    Runs on every message this module sees, which is why it is `difflib` over a
    fixed 60-word list rather than a spell-checker: it is bounded, it needs
    nothing installed, and a word that is already in the vocabulary is returned
    untouched without any comparison at all.

    Only the *matcher's* copy of the message is corrected, the user's question
    is never rewritten anywhere they can see it, so a wrong correction costs at
    most a fallthrough to retrieval, which is what would have happened anyway.
    """
    known = set(_VOCABULARY)

    def fix(match: re.Match) -> str:
        word = match.group(0)
        if len(word) < _SPELLING_MIN_LENGTH or word in known:
            return word
        swap = _transposition_of(word, known)
        if swap:
            return swap
        close = difflib.get_close_matches(word, _VOCABULARY, n=1, cutoff=_SPELLING_CUTOFF)
        return close[0] if close else word

    # `\w+` rather than splitting on spaces: "categories," and "tags?" have to
    # be corrected without their punctuation travelling into the comparison.
    return re.sub(r"[a-z]+", fix, text)


def _asks(text: str, *patterns: str) -> bool:
    return all(re.search(pattern, text) for pattern in patterns)


def looks_like_a_question_about_the_notebook(message: str) -> bool:
    """Cheap pre-filter: is this worth running the matchers over at all?"""
    text = _despell((message or "").lower())
    return bool(
        re.search(_TAG_WORDS, text)
        or re.search(_CATEGORY_WORDS, text)
        or re.search(r"\bnotes?\b|\bdocuments?\b|notebook", text)
        #: The topics added alongside the spelling pass. Without these the
        #: pre-filter rejected "how many words have I written" before any
        #: matcher saw it: a question the module now answers exactly, refused
        #: by the gate in front of it. That is this repo's "a policy silently
        #: refusing the work" shape, and it was caught by the test for the new
        #: matcher rather than by reading the code.
        or re.search(r"\bwords?\b|word ?count|writ(?:ten|ing)|\bwr(?:ite|ote)\b", text)
        or re.search(r"stale|forgotten|untouched|abandoned", text)
        or re.search(r"\bstat(?:istic)?s\b", text)
    )


def answer(message: str, session: Session) -> StatAnswer | None:
    """The computed answer to this question, or None to fall through to search."""
    #: Spelling is fixed once, here, and every matcher below sees the corrected
    #: text: including `_recent_count`, which reads the string itself.
    text = _despell((message or "").strip().lower())
    if not text or not looks_like_a_question_about_the_notebook(text):
        return None

    if _asks(text, _TAG_WORDS, _MOST):
        return _top_tags(session)
    if _asks(text, _CATEGORY_WORDS, _MOST):
        return _top_categories(session)
    if _asks(text, r"untagged|no tags|without (?:a )?tags?|missing tags?"):
        return _untagged(session)
    if _asks(text, _COUNT, _TAG_WORDS):
        return _tag_count(session)
    if _asks(text, _COUNT, _CATEGORY_WORDS):
        return _category_count(session)
    #: "How many notes are about Harbor" counts the notes on a subject, which
    #: retrieval finds and the composer counts ("At least four of your notes
    #: mention Harbor"); answering it "You have 77 notes" dropped the subject
    #: (engine probe P5).
    #: A count over a window ("how many notes did I write this week") is the
    #: window's count, never the notebook's total: the window is read by
    #: `ai/recognise.py` (CHAT_PLAN decision 46), so "in March" and "since
    #: Friday" count too.
    window = _window(text) if re.search(_COUNT, text) else None
    if window is not None and not _SUBJECT_AFTER.search(text):
        return _recent_count(session, window)
    if _asks(text, _COUNT, r"\bnotes?\b") and not _SUBJECT_AFTER.search(text):
        return _note_count(session)
    if _asks(text, _COUNT, r"\bdocuments?\b"):
        return _document_count(session)
    if _asks(text, r"\bmost linked|linked (?:to )?the most|best connected|most connect"):
        return _most_linked(session)
    if _asks(text, r"orphan|unlinked|not linked|no links"):
        return _orphans(session)
    if _asks(text, r"when do i|busiest|most active|what time|which day"):
        return _busiest(session)
    #: --- added with the spelling pass, because "improve" was the other half
    #: of the same request. Each one is a question people ask about a notebook
    #: that retrieval answers badly for the same reason the rest do: it is a
    #: question about the collection, not about any note in it.
    if _asks(text, r"\b(?:write|wrote|written|writing)\b", r"\bmost\b", r"\babout\b"):
        return _top_subjects(session)
    if _asks(text, r"\bwords?\b|word count|wordcount", r"\bhow many|\btotal|\bwritten|\bcount"):
        return _word_count(session)
    if _asks(text, r"longest|biggest|largest", r"\bnotes?\b"):
        return _longest_notes(session)
    if _asks(text, r"stale|forgotten|untouched|abandoned|haven.?t (?:looked|touched|opened|read)"):
        return _stale_notes(session)
    if _asks(text, _TAG_WORDS, r"together|alongside|\bpairs?\b|combination|co-?occur"):
        return _tag_pairs(session)
    return _whole_notebook(text, session)


def _whole_notebook(text: str, session: Session) -> StatAnswer | None:
    """Questions about the notebook as a whole. "What do my notes cover so far",
    "what's in my notebook", "an overview of my notes": never a search for the
    word "cover" (owner, 2026-10-17). "Stats" and "statistics" only for the
    figures: "summary" and "overview" of a subject ask for the notes' content
    ("a summary of the trip"), which the composer answers."""
    if _COVERAGE.match(text.rstrip("?!. ")):
        return _coverage(session)
    if _asks(text, r"\bstat(?:istic)?s\b"):
        return _general_stats(session)
    return None


#: A count of notes narrowed to a subject: "notes about X", "notes that
#: mention X", "notes tagged X", "notes on X".
_SUBJECT_AFTER = re.compile(r"\bnotes?\b.*\b(?:about|mention(?:s|ing)?|tagged|on)\s+\S")

#: Words that say nothing about what a note is about, left out of the most
#: written-about words: function words and the ones every note shares.
_PLAIN = frozenset(
    """the a an and or but of to in on at for with from by is are was were be been it its
    this that these those i me my we our you your he she they them his her their not no
    do did does done have has had will would can could should so if then than as up out
    just also very more most some any all one two three get got go went make made need
    about into over after before when what which who how there here note notes today""".split()
)


def _top_subjects(session: Session) -> StatAnswer:
    """What the notebook is most about, by what it is filed under first (its
    tags, then its categories) and, with neither, by the words the most notes
    use (engine probe P7: "what did I write most about" listed the newest
    notes). Every figure is a count of notes."""
    rows = session.execute(_visible(select(Entry.tags, Entry.content))).all()
    if not rows:
        return StatAnswer("subjects", "There are no notes to read yet.")
    tags = Counter(tag for raw, _content in rows for tag in set(_tags_of(raw)))
    if len(tags) >= 2:
        top = tags.most_common(5)
        listed = ", ".join(f"{tag} ({_plural(n, 'note')})" for tag, n in top)
        return StatAnswer("subjects", f"By your tags, you write most about {listed}.", [{"label": t, "count": n} for t, n in top])
    words: Counter[str] = Counter()
    for _raw, content in rows:
        words.update({w for w in re.findall(r"[a-z][a-z'-]{2,}", str(content or "").lower()) if w not in _PLAIN})
    top = [(w, n) for w, n in words.most_common(5) if n >= 2]
    if not top:
        return StatAnswer("subjects", f"No word comes up in more than one of your {_plural(len(rows), 'note')} yet.")
    listed = ", ".join(f"“{w}” ({_plural(n, 'note')})" for w, n in top)
    return StatAnswer("subjects", f"The words the most notes use are {listed}.", [{"label": w, "count": n} for w, n in top])


def _top_tags(session: Session) -> StatAnswer:
    rows = session.scalars(_visible(select(Entry.tags))).all()
    counts = Counter(tag for raw in rows for tag in _tags_of(raw))
    if not counts:
        return StatAnswer("tags", "You have not tagged any notes yet.")
    top = counts.most_common(TOP_N)
    listed = ", ".join(f"{tag} ({n})" for tag, n in top)
    return StatAnswer(
        "tags",
        f"Your most-used tags are {listed}. "
        f"That is across {_plural(len(counts), 'distinct tag')}.",
        [{"label": tag, "count": n} for tag, n in top],
    )


def _top_categories(session: Session) -> StatAnswer:
    rows = session.execute(
        _visible(
            select(Category.name, func.count(Entry.id))
            .join(Category, Category.id == Entry.category_id)
            .group_by(Category.name)
        ).order_by(func.count(Entry.id).desc()).limit(TOP_N)
    ).all()
    if not rows:
        return StatAnswer("categories", "None of your notes are filed in a category yet.")
    listed = ", ".join(f"{name} ({n})" for name, n in rows)
    return StatAnswer(
        "categories",
        f"The categories with the most notes are {listed}.",
        [{"label": name, "count": n} for name, n in rows],
    )


def _untagged(session: Session) -> StatAnswer:
    rows = session.scalars(_visible(select(Entry.tags))).all()
    without = sum(1 for raw in rows if not _tags_of(raw))
    return StatAnswer(
        "untagged",
        f"{_plural(without, 'note')} out of {len(rows)} have no tags."
        + (" Filing those would make them much easier to find." if without else ""),
        [{"label": "untagged", "count": without}, {"label": "total", "count": len(rows)}],
    )


def _tag_count(session: Session) -> StatAnswer:
    rows = session.scalars(_visible(select(Entry.tags))).all()
    distinct = {tag for raw in rows for tag in _tags_of(raw)}
    return StatAnswer(
        "tag-count",
        f"You are using {_plural(len(distinct), 'distinct tag')}.",
        [{"label": "tags", "count": len(distinct)}],
    )


def _category_count(session: Session) -> StatAnswer:
    total = session.scalar(select(func.count(Category.id))) or 0
    return StatAnswer(
        "category-count",
        f"You have {_plural(total, 'category')}.".replace("categorys", "categories"),
        [{"label": "categories", "count": total}],
    )


def _note_count(session: Session) -> StatAnswer:
    total = session.scalar(_visible(select(func.count(Entry.id)))) or 0
    return StatAnswer(
        "note-count",
        f"You have {_plural(total, 'note')}.",
        [{"label": "notes", "count": total}],
    )


def _document_count(session: Session) -> StatAnswer:
    total = session.scalar(select(func.count(Document.id))) or 0
    return StatAnswer(
        "document-count",
        f"You have {_plural(total, 'document')}.",
        [{"label": "documents", "count": total}],
    )


def _most_linked(session: Session) -> StatAnswer:
    """The notes at the centre of the graph.

    Counts both directions: a note everything points *at* is as central as one
    that points at everything, and a "best connected" answer that counted only
    outgoing links would rank the note you happened to write last.
    """
    counts: Counter[int] = Counter()
    for source, target in session.execute(select(EntryLink.source_entry_id, EntryLink.target_entry_id)).all():
        counts[source] += 1
        counts[target] += 1
    if not counts:
        return StatAnswer("linked", "None of your notes are linked to each other yet.")
    top_ids = [entry_id for entry_id, _ in counts.most_common(TOP_N)]
    rows = session.scalars(_visible(select(Entry).where(Entry.id.in_(top_ids)))).all()
    by_id = {row.id: row for row in rows}
    facts = []
    for entry_id in top_ids:
        row = by_id.get(entry_id)
        if row is None:
            continue  # binned or private since the link was made
        facts.append(
            {
                "label": (row.content or "").strip().split("\n")[0][:60],
                "count": counts[entry_id],
                "id": row.id,
            }
        )
    if not facts:
        return StatAnswer("linked", "None of your visible notes are linked to each other yet.")
    listed = "; ".join(f"“{fact['label']}” ({fact['count']} links)" for fact in facts[:5])
    return StatAnswer("linked", f"Your most connected notes are {listed}.", facts)


def _orphans(session: Session) -> StatAnswer:
    linked: set[int] = set()
    for source, target in session.execute(select(EntryLink.source_entry_id, EntryLink.target_entry_id)).all():
        linked.add(source)
        linked.add(target)
    ids = session.scalars(_visible(select(Entry.id))).all()
    alone = [entry_id for entry_id in ids if entry_id not in linked]
    return StatAnswer(
        "orphans",
        f"{_plural(len(alone), 'note')} out of {len(ids)} are not linked to anything else.",
        [{"label": "unlinked", "count": len(alone)}, {"label": "total", "count": len(ids)}],
    )


#: Written out rather than computed from the locale: this string is spoken back
#: to the user, and `%A` would follow the *server's* locale rather than theirs.
_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _busiest(session: Session) -> StatAnswer:
    rows = session.scalars(_visible(select(Entry.created_at))).all()
    if not rows:
        return StatAnswer("busiest", "There are no notes to look at yet.")
    days = Counter(_WEEKDAYS[value.weekday()] for value in rows if value)
    hours = Counter(value.hour for value in rows if value)
    day, day_n = days.most_common(1)[0]
    hour, _ = hours.most_common(1)[0]
    window = f"{hour:02d}:00–{(hour + 1) % 24:02d}:00"
    return StatAnswer(
        "busiest",
        f"You write most on {day}s ({_plural(day_n, 'note')}), and most often around {window}.",
        [{"label": name, "count": n} for name, n in days.most_common()],
    )


def _window(text: str) -> tuple[datetime, datetime, str] | None:
    """(start, end, words) of the first day or span of days the question
    names, on the UTC calendar the notes are stamped with; None for none."""
    from tessellate.ai import recognise

    now = utcnow()
    for found in recognise.recognise(text, now=now, tense="past"):
        if found.rank or found.kind not in ("date", "range"):
            continue
        first, last, grain = found.value if found.kind == "range" else (found.value, found.value, "day")
        if not isinstance(first, date):
            continue
        words = found.text.strip()
        if grain == "month" and words.lower().startswith(("in ", "during ")):
            words = first.strftime("in %B %Y")
        elif not words.lower().startswith(("in ", "since ", "on ", "this ", "last ", "today", "yesterday")):
            words = ("in the " if words.lower().startswith(("past ", "previous ")) else "on ") + words
        start = datetime.combine(first, time(0), now.tzinfo)
        end = min(datetime.combine(last, time(23, 59, 59), now.tzinfo), now)
        return (start, end, words) if start < end else None
    return None


def _recent_count(session: Session, window: tuple[datetime, datetime, str]) -> StatAnswer:
    start, end, words = window
    total = (
        session.scalar(
            _visible(select(func.count(Entry.id)).where(Entry.created_at >= start, Entry.created_at <= end))
        )
        or 0
    )
    return StatAnswer(
        "recent-count",
        f"You have written {_plural(total, 'note')} {words}.",
        [{"label": words, "count": total}],
    )


#: A note shorter than this is a fragment, a link, a phone number, a one-word
#: reminder: and listing the "longest" notes is only interesting against
#: things somebody actually wrote. Not a filter on the count, only on the list.
_LONGEST_MIN_CHARS = 40

#: How long a note has to go untouched to count as stale. Ninety days is one
#: quarter: long enough that a note you simply have not needed this month is
#: not on the list, short enough to still be actionable.
_STALE_DAYS = 90


def _word_count(session: Session) -> StatAnswer:
    """How much you have actually written.

    Counted in Python rather than in SQL because SQLite has no word-count
    function and the alternatives, `length(x) - length(replace(x, ' ', ''))`
    - count *spaces*, so they are off by one on every note and badly wrong on
    any note with double spacing or a list. A notebook is thousands of rows,
    not millions; this is a millisecond.
    """
    rows = session.scalars(_visible(select(Entry.content))).all()
    words = sum(len(str(row or "").split()) for row in rows)
    if not rows:
        return StatAnswer("word-count", "There are no notes to count yet.")
    average = round(words / len(rows))
    return StatAnswer(
        "word-count",
        f"You have written about {words:,} words across {_plural(len(rows), 'note')}, "
        f"roughly {average} words a note.",
        [{"label": "words", "count": words}, {"label": "notes", "count": len(rows)}],
    )


def _longest_notes(session: Session) -> StatAnswer:
    """The notes with the most in them.

    Useful for the reason nobody expects: the longest notes are usually the
    ones that should have been split, and this is the only view in the app that
    surfaces them. Ordered by character count in SQL so the whole notebook does
    not have to come back to rank ten rows.
    """
    rows = session.execute(
        _visible(select(Entry.id, Entry.content))
        .where(func.length(Entry.content) >= _LONGEST_MIN_CHARS)
        .order_by(func.length(Entry.content).desc())
        .limit(TOP_N)
    ).all()
    if not rows:
        return StatAnswer("longest-notes", "There are no notes long enough to rank yet.")
    facts = [
        {
            "label": " ".join(str(content or "").split())[:60],
            "count": len(str(content or "").split()),
            "id": note_id,
        }
        for note_id, content in rows
    ]
    lead = facts[0]
    return StatAnswer(
        "longest-notes",
        f"Your longest note is about {lead['count']} words: “{lead['label']}”. "
        f"The top {len(facts)} are listed below.",
        facts,
    )


def _stale_notes(session: Session) -> StatAnswer:
    """What you have not touched in a season.

    `updated_at` rather than `created_at`: a note written a year ago and edited
    last week is not forgotten, and the question being asked is about attention,
    not age.
    """
    since = utcnow() - timedelta(days=_STALE_DAYS)
    rows = session.execute(
        _visible(select(Entry.id, Entry.content, Entry.updated_at))
        .where(Entry.updated_at < since)
        .order_by(Entry.updated_at.asc())
        .limit(TOP_N)
    ).all()
    total = (
        session.scalar(_visible(select(func.count(Entry.id)).where(Entry.updated_at < since)))
        or 0
    )
    if not total:
        return StatAnswer(
            "stale-notes",
            f"Nothing has gone untouched for {_STALE_DAYS} days: every note has been "
            "opened or edited more recently than that.",
        )
    facts = [
        {
            "label": " ".join(str(content or "").split())[:60],
            "id": note_id,
            "when": touched.isoformat() if touched else "",
        }
        for note_id, content, touched in rows
    ]
    return StatAnswer(
        "stale-notes",
        f"{_plural(total, 'note')} {'has' if total == 1 else 'have'} gone more than "
        f"{_STALE_DAYS} days without an edit. The {len(facts)} oldest are listed below.",
        facts,
    )


def _tag_pairs(session: Session) -> StatAnswer:
    """Which tags keep turning up together.

    The one question in this module that is genuinely about *structure* rather
    than about counting one column: a pair of tags that co-occur constantly is
    either one idea filed under two names, or a real seam in the notebook. Both
    are worth seeing, and neither is visible from a list of tag counts.

    Pairs are ordered within themselves so `(a, b)` and `(b, a)` are one pair: 
    without that, every co-occurrence would be counted twice and the ranking
    would still be right but the numbers would all be doubled, which is the
    kind of wrong that nobody notices.
    """
    rows = session.scalars(_visible(select(Entry.tags))).all()
    pairs: Counter[tuple[str, str]] = Counter()
    for raw in rows:
        tags = sorted(set(_tags_of(raw)))
        for i, first in enumerate(tags):
            for second in tags[i + 1:]:
                pairs[(first, second)] += 1
    #: A pair seen once is a coincidence, not a pattern.
    common = [(pair, n) for pair, n in pairs.most_common(TOP_N) if n > 1]
    if not common:
        return StatAnswer(
            "tag-pairs",
            "No two tags turn up together often enough to be worth calling a pattern yet.",
        )
    (top_a, top_b), top_n = common[0]
    return StatAnswer(
        "tag-pairs",
        f"#{top_a} and #{top_b} appear together most often, on {_plural(top_n, 'note')}. "
        f"The top {len(common)} pairings are listed below.",
        [{"label": f"#{a} + #{b}", "count": n} for (a, b), n in common],
    )


_SOFAR = r"(?: (?:so far|overall|in total|all together|at the moment|right now|lately|these days))?"
#: Anchored whole-message patterns: "what do my notes say about golf" has a
#: subject and is a search.
_COVERAGE = re.compile(
    rf"^(?:what|which)(?: things| topics| subjects| areas)? (?:do|does|are) (?:my |the )?(?:notes?|notebook|entries) (?:cover|contain|hold|include|have in them){_SOFAR}$"
    rf"|^what(?:'s| is| are) (?:in|inside) (?:my |the )?(?:notes?|notebook){_SOFAR}$"
    rf"|^what (?:have i|did i|do i) (?:been )?(?:writing|written|write|wrote|noting|noted|saving|saved|note|save)(?: (?:about|on))?{_SOFAR}$"
    rf"|^what (?:topics|subjects|themes|things|areas) (?:do i|have i|did i) (?:write|writing|written|wrote|note|noted|cover|covered|keep notes)(?: (?:about|on))?{_SOFAR}$"
    rf"|^(?:give me |show me |can i get |i want )?(?:an? )?(?:overview|summary|rundown|run down|breakdown|tour) of (?:my |the )?(?:notes|notebook|everything){_SOFAR}$"
)


def _common_words(session: Session) -> list[tuple[str, int]]:
    """The words the most notes use, for a notebook with nothing filed or tagged."""
    counted: Counter[str] = Counter()
    for content in session.scalars(_visible(select(Entry.content))).all():
        counted.update({w for w in re.findall(r"[a-z][a-z'-]{2,}", str(content or "").lower()) if w not in _PLAIN})
    return [(w, n) for w, n in counted.most_common(6) if n >= 2]


def _coverage_parts(session: Session) -> tuple[list, list, list]:
    """(areas, tags, words) the notebook is made of: the categories with notes,
    the tags that come up most and, only when neither exists, the common words."""
    areas = session.execute(
        _visible(select(Category.name, func.count(Entry.id)).join(Category, Category.id == Entry.category_id).group_by(Category.name))
        .order_by(func.count(Entry.id).desc())
    ).all()
    areas = [(name, n) for name, n in areas if name and name != "Uncategorised"][:6]
    tags = Counter(tag for raw in session.scalars(_visible(select(Entry.tags))).all() for tag in set(_tags_of(raw)))
    top_tags = tags.most_common(6)
    return areas, top_tags, ([] if areas or top_tags else _common_words(session))


def _coverage(session: Session) -> StatAnswer:
    """What the notebook holds, in a few sentences: how many notes over what
    span, the areas they are filed in and the tags that come up most."""
    note_total = session.scalar(_visible(select(func.count(Entry.id)))) or 0
    if not note_total:
        return StatAnswer("coverage", "There are no notes to read yet.")
    made = sorted(value for value in session.scalars(_visible(select(Entry.created_at))).all() if value)
    areas, top_tags, words = _coverage_parts(session)
    sentences = [f"You have {_plural(note_total, 'note')}{_span_words(made)}."]
    if words:
        sentences.append("The words that come up most are " + ", ".join(f"\u201c{w}\u201d ({n})" for w, n in words) + ".")
    if areas:
        sentences.append("They are filed under " + ", ".join(f"{name} ({n})" for name, n in areas) + ".")
    if top_tags:
        sentences.append("The tags that come up most are " + ", ".join(f"{tag} ({n})" for tag, n in top_tags) + ".")
    offer = {"kind": "open", "label": "Open Statistics for the full picture?", "surface": "statistics"}
    return StatAnswer(
        "coverage",
        "\n\n".join([" ".join(sentences), offer["label"]]),
        [{"label": name, "count": n} for name, n in areas]
        + [{"label": f"#{tag}", "count": n} for tag, n in top_tags]
        + [{"label": w, "count": n} for w, n in words],
        offer,
    )


def _general_stats(session: Session) -> StatAnswer:
    """"Notebook stats" (INBOX 801, decision 70's gold Q3): the count and
    span in one opening sentence, the most filed category and the busiest
    month under bold labels, the rest in one line, and Statistics offered."""
    note_total = session.scalar(_visible(select(func.count(Entry.id)))) or 0
    cat_total = session.scalar(_visible(select(func.count(func.distinct(Entry.category_id))))) or 0
    #: Documents are not entries, so not filtered as entries are (the same
    #: count `_document_count` gives).
    doc_total = session.scalar(select(func.count(Document.id))) or 0
    rows = session.scalars(_visible(select(Entry.tags))).all()
    distinct_tags = len({tag for raw in rows for tag in _tags_of(raw)})
    made = sorted(value for value in session.scalars(_visible(select(Entry.created_at))).all() if value)
    top = session.execute(
        _visible(select(Category.name, func.count(Entry.id)).join(Category, Category.id == Entry.category_id).group_by(Category.name))
        .order_by(func.count(Entry.id).desc()).limit(1)
    ).first()
    in_cats = f" in {_plural(cat_total, 'category')}" if cat_total else ""
    lines = [f"You have {_plural(note_total, 'note')}{in_cats}{_span_words(made)}."]
    labelled = []
    if top:
        labelled.append(f"**Most filed:** {top[0]}, with {top[1]}.")
    months = Counter((value.year, value.month) for value in made)
    if len(months) > 1:
        (year, month), n = months.most_common(1)[0]
        labelled.append(f"**Busiest month:** {_MONTHS[month - 1]}{'' if year == made[-1].year else f' {year}'}, with {_plural(n, 'note')}.")
    labelled.append(f"**Also:** {_plural(doc_total, 'document')} and {_plural(distinct_tags, 'distinct tag')}.")
    offer = {"kind": "open", "label": "Open Statistics for the full picture?", "surface": "statistics"}
    return StatAnswer(
        "overview",
        #: One paragraph per labelled line: the Ask box's markdown joins a
        #: single newline into one run-on paragraph (measured, records.js).
        "\n\n".join([lines[0], *labelled, offer["label"]]),
        [
            {"label": "notes", "count": note_total},
            {"label": "documents", "count": doc_total},
            {"label": "categories", "count": cat_total},
            {"label": "tags", "count": distinct_tags},
        ],
        offer,
    )


_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")


def _span_words(made: list[datetime]) -> str:
    """", 17 July to 9 October"; the year said when the span crosses one."""
    if not made:
        return ""
    first, last = made[0], made[-1]
    if first.date() == last.date():
        return f", all from {first.day} {_MONTHS[first.month - 1]}"
    year = first.year != last.year
    said = [f"{d.day} {_MONTHS[d.month - 1]}{f' {d.year}' if year else ''}" for d in (first, last)]
    return f", {said[0]} to {said[1]}"


# --- the Statistics page (UI_MODERNISATION statistics rows 1 and 2) ----------
#
# The page asks once (`GET /statistics`) and draws what comes back: every
# figure on it is a count made here, from rows, with no model. Bounded: twelve
# months of growth, two weeks of review, the usage ledger's top rows.

GROWTH_MONTHS = 12
USAGE_ROWS = 200


def _words(text: str | None) -> int:
    return len(str(text or "").split())


def _month_keys(now: datetime, months: int = GROWTH_MONTHS) -> list[str]:
    year, month = now.year, now.month
    keys = []
    for _ in range(months):
        keys.append(f"{year:04d}-{month:02d}")
        year, month = (year, month - 1) if month > 1 else (year - 1, 12)
    return keys[::-1]


def _notebook_block(session: Session, now: datetime) -> dict:
    """Notes, words, tags and growth from one pass over the live notes; the
    other counts are one aggregate query each."""
    zone = now.tzinfo
    rows = session.execute(_visible(select(Entry.content, Entry.tags, Entry.created_at))).all()
    keys = _month_keys(now)
    growth = dict.fromkeys(keys, 0)
    tags: set[str] = set()
    words = 0
    for content, raw, created in rows:
        words += _words(content)
        tags.update(_tags_of(raw))
        if created is not None:
            key = (created.astimezone(zone) if created.tzinfo else created).strftime("%Y-%m")
            if key in growth:
                growth[key] += 1
    #: A link counts only between two counted notes: a link to a binned or
    #: private one would say that hidden note is joined to something.
    near, far = aliased(Entry), aliased(Entry)
    visible_link = (
        select(EntryLink.id)
        .join(near, near.id == EntryLink.source_entry_id)
        .join(far, far.id == EntryLink.target_entry_id)
    )
    for end in (near, far):
        visible_link = visible_link.where(
            end.deleted_at.is_(None), end.is_private.is_(False), end.is_board.is_(False)
        )
    linked = or_(
        exists().where(EntryLink.source_entry_id == Entry.id, EntryLink.id.in_(visible_link)),
        exists().where(EntryLink.target_entry_id == Entry.id, EntryLink.id.in_(visible_link)),
    )
    return {
        "notes": len(rows),
        "words": words,
        "tags": len(tags),
        "categories": session.scalar(select(func.count(Category.id))) or 0,
        "documents": session.scalar(select(func.count(Document.id))) or 0,
        "links": session.scalar(select(func.count()).select_from(visible_link.subquery())) or 0,
        "orphans": session.scalar(_visible(select(func.count(Entry.id)).where(~linked))) or 0,
        "growth": [{"label": key, "value": growth[key]} for key in keys],
    }


def _reminder_block(session: Session, now: datetime) -> dict:
    """Made, done, late and open, in one aggregate query (binned reminders
    are out of every select, `_hide_binned`)."""
    moment = now.astimezone(utcnow().tzinfo)
    open_ = Reminder.done.is_(False)
    made, done, late = session.execute(
        select(
            func.count(Reminder.id),
            func.coalesce(func.sum(case((Reminder.done.is_(True), 1), else_=0)), 0),
            func.coalesce(func.sum(case((and_(open_, Reminder.due_at < moment), 1), else_=0)), 0),
        )
    ).one()
    return {"made": made, "done": int(done), "late": int(late), "open": made - int(done)}


def week_start(now: datetime, first_day: int = 0) -> datetime:
    """00:00 of the first day of `now`'s week, on `now`'s own clock.
    `first_day` is Python's weekday number: 0 Monday, 5 Saturday, 6 Sunday."""
    day = now.date() - timedelta(days=(now.weekday() - first_day) % 7)
    return datetime.combine(day, time(0), now.tzinfo)


def _words_added_by_edits(session: Session, a: datetime, b: datetime) -> int:
    """Words added to notes made before `a` by edits made in `[a, b)` (ledger 1525).

    No per-edit delta is stored, but `EntryRevision` keeps each text an edit
    replaced, so an edit's gain is the words of what came after it (the next
    revision, or the note as it stands) less the words of what it replaced.
    Only gains count: a trim is not "words written". A revision the app folded
    into a recent one (rapid saves) is one edit here, so this is a floor.
    """
    ids = [
        row[0]
        for row in session.execute(
            _visible(select(Entry.id))
            .join(EntryRevision, EntryRevision.entry_id == Entry.id)
            .where(Entry.created_at < a, EntryRevision.created_at >= a, EntryRevision.created_at < b)
            .distinct()
        )
    ]
    if not ids:
        return 0
    current = dict(session.execute(select(Entry.id, Entry.content).where(Entry.id.in_(ids))).all())
    chain: dict[int, list[tuple[datetime, str]]] = {}
    for entry_id, made, content in session.execute(
        select(EntryRevision.entry_id, EntryRevision.created_at, EntryRevision.content)
        .where(EntryRevision.entry_id.in_(ids))
        .order_by(EntryRevision.entry_id, EntryRevision.id)
    ):
        chain.setdefault(entry_id, []).append((made, content))
    added = 0
    for entry_id, revisions in chain.items():
        for index, (made, before) in enumerate(revisions):
            if not (a <= made < b):
                continue
            after = revisions[index + 1][1] if index + 1 < len(revisions) else current.get(entry_id)
            added += max(0, _words(after) - _words(before))
    return added


def _week_counts(session: Session, start: datetime, end: datetime) -> dict:
    a, b = start.astimezone(utcnow().tzinfo), end.astimezone(utcnow().tzinfo)
    texts = session.scalars(
        _visible(select(Entry.content)).where(Entry.created_at >= a, Entry.created_at < b)
    ).all()
    done = session.scalar(
        select(func.count(Reminder.id)).where(Reminder.done_at >= a, Reminder.done_at < b)
    ) or 0
    return {
        "start": start.date().isoformat(),
        "end": (end - timedelta(seconds=1)).date().isoformat(),
        "notes": len(texts),
        "words": sum(_words(text) for text in texts),
        "edited_words": _words_added_by_edits(session, a, b),
        "reminders_done": done,
    }


def week_review(session: Session, now: datetime, first_day: int = 0) -> dict:
    """This week so far against the whole of last week (Screen Time's shape):
    notes made, words written in them, reminders ticked off. "Done" is when
    the tick was made (`Reminder.done_at`); one ticked before that column
    existed has no week, so it is in neither."""
    this = week_start(now, first_day)
    last = this - timedelta(days=7)
    return {
        "this": _week_counts(session, this, now + timedelta(seconds=1)),
        "last": _week_counts(session, last, this),
    }


def page(session: Session, now: datetime, usage_summary: dict, first_day: int = 0) -> dict:
    """Everything the Statistics page draws, in one answer."""
    features = list(usage_summary.get("features") or [])[:USAGE_ROWS]
    return {
        "as_of": now.isoformat(),
        "notebook": _notebook_block(session, now),
        "reminders": _reminder_block(session, now),
        "week": week_review(session, now, first_day),
        "usage": {
            "features": features,
            "unused_days": usage_summary.get("unused_days"),
            "uses": sum(int(f.get("count") or 0) for f in features),
        },
    }
