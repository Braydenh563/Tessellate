"""The notes a question is answered from: retrieval widened by the person's
glossary, synonyms, neighbours and the open note, records and time windows,
each note's content, and the matched rows the answer shows.

Moved whole from `routes_chat.py` (audit AR3, gods-1101): the code is
unchanged, and `routes_chat` re-exports every name here that anything
reads, so `routes_chat._frame_matches` still works. Imports run one way, down the
layer list in `routes_chat.py`'s docstring, never back to `routes_chat`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from tessellate.ai import composer, composer_frame, composer_intent, composer_lists, composer_money, composer_slots, composer_sum, composer_versus, glossary, librarian, neighbours, question_noise
from tessellate.ai import composer_ask, composer_property, composer_tables
from tessellate.api.chat_attach import _MEDIA_REF, _attached_boards, _attachment_readings, _media_readings, _mostly_pictures, _named_sources, _picture_alts, _picture_sizes
from tessellate.core import deps
from tessellate.core.database import Category, Entry, like_escape, LIKE_ESCAPE, MediaUpload
from tessellate.repo import content as content_repo
from tessellate.repo import documents as documents_repo
from tessellate.repo import relations as relations_repo
from tessellate.repo import tags as tags_repo
from tessellate.entry import manager
from tessellate.entry import manager_text
from tessellate.search import engine, search_manager


#: A topic asked about as a whole reads this many notes (INBOX 787): "games
#: notes" answered from the five a similarity search ranked counted five, and
#: the overview says how many there are.
OVERVIEW_LIMIT = 24

#: How far the count of a topic's notes looks past the pool (never read, only counted).
POOL_COUNT_LIMIT = 500


#: Notes found by what their pictures show or say, beside retrieval.
PICTURE_MATCHES = 3


#: The person's abbreviations, learned once per state of the notebook (the
#: count and the newest edit), not once per question.
_GLOSSARY: dict[str, object] = {"key": None, "terms": {}}


def _glossary(session: Session) -> dict[str, str]:
    """`ai/glossary.learn` over every note (CHAT_PLAN B7): "CC" is Cloud
    Computing because the notes say so, or name it in full beside it."""
    live = Entry.is_deleted == False  # noqa: E712
    key = session.execute(select(func.count(Entry.id), func.max(Entry.updated_at)).where(live)).one()
    if _GLOSSARY["key"] != tuple(key):
        texts = session.execute(select(Entry.content).where(live)).scalars()
        _GLOSSARY.update(key=tuple(key), terms=glossary.learn(texts))
    return _GLOSSARY["terms"]  # type: ignore[return-value]


def _widened(session: Session, question: str, entries: list, scope: str = "") -> list:
    """The retrieved notes, plus the notes whose pictures match the question
    (keyword search reads a note's words, not its pictures' readings: "what
    did I note about binary search trees" missed the lecture slide), plus,
    for a topic asked about as a whole, its notes by keyword and by tag."""
    from tessellate.ai import composer_overview

    extra = _picture_notes(session, composer.subject_terms(question))
    subject = composer_overview.topic(question)
    if subject:
        #: The notes filed under the subject (its category, its tag) come first:
        #: a keyword rank by how often a word repeats put a note that says
        #: "reading" nine times above the Books note (audit 1031 C4).
        filed = _filed_under(session, composer.subject_terms(subject), POOL_COUNT_LIMIT)
        said = filed + search_manager.keyword_search(session, subject, limit=POOL_COUNT_LIMIT)
        extra += said if len({e.id for e in said}) >= 2 else said + _by_synonym(session, subject)
    seen = {entry.id for entry in entries}
    out = list(entries)
    for entry in extra:
        #: A question scoped to a category ("my notes in Health") keeps its
        #: answer there: "notes in Health" reads as a topic too, and its word
        #: "notes" matched an Ideas note.
        if scope and manager.category_name_for(session, entry) != scope:
            continue
        if entry.id not in seen and not entry.is_deleted and not entry.is_private:
            seen.add(entry.id)
            out.append(entry)
    kept = out[: max(len(entries), OVERVIEW_LIMIT)]
    #: The pool stays at OVERVIEW_LIMIT, but the lead counts the notes there are.
    if subject and kept and len(out) > len(kept):
        kept[0]._overview_pool = (len(out), len(kept))  # noqa: SLF001  # read by `_chat_payload`
    return kept


#: Notes read for "the topic whole" come from the first of the retrieved
#: ones that rank at the top, never from every graph neighbour.
NEIGHBOUR_SEEDS = 3


#: Past this many retrieved notes the topic is already read whole.
NEIGHBOUR_ROOM = 6


def _with_neighbours(session: Session, question: str, entries: list, scope: str = "") -> list:
    """The retrieved notes plus, for a question about a topic as a whole, the
    notes sharing a rare tag with the best of them (`ai/neighbours.py`: the
    keyword search wants every word, so "how's the gym going?" never read the
    second gym note)."""
    if neighbours.asks_left(question) and not scope:
        return _with_open(session, question, entries)
    if not entries or scope or len(entries) > NEIGHBOUR_ROOM or not neighbours.reads_whole(question):
        return entries
    rows = tags_repo.tagged(session, limit=2000)
    chosen = neighbours.pick([e.id for e in entries[:NEIGHBOUR_SEEDS]], rows)
    have = {e.id for e in entries}
    extra = [session.get(Entry, i) for i in chosen if i not in have]
    return entries + [e for e in extra if e is not None]


def _with_open(session: Session, question: str, entries: list) -> list:
    """For "what do I need to buy" and "what's left", the notes that hold
    something unfinished: an unticked box, "still to" or "need to", and, for
    buying, the shopping notes by tag or category. Search by the words of the
    question ("buy") finds none of them."""
    clauses = [Entry.content.like("%- [ ]%"), Entry.content.like("%still to %"), Entry.content.like("%need to %")]
    if re.search(r"\b(buy|shop|get)\b", question, re.I):
        shops = ("grocer", "shopping", "shop list")
        clauses += tags_repo.mentioning(list(shops))
        named = select(Category.id).where(or_(*(func.lower(Category.name).like(f"%{like_escape(w)}%", escape=LIKE_ESCAPE) for w in shops)))
        clauses.append(Entry.category_id.in_(named))
    found = session.scalars(
        select(Entry)
        .where(Entry.is_deleted == False, Entry.is_private == False, Entry.is_board == False, or_(*clauses))  # noqa: E712
        .order_by(Entry.created_at.desc())
        .limit(NEIGHBOUR_ROOM)
    )
    have = {e.id for e in entries}
    return entries + [e for e in found if e.id not in have]


def _by_synonym(session: Session, subject: str) -> list:
    """The notes that name a topic by another word ("uni" for "university"):
    read only when the topic's own word finds fewer than two, which is no
    overview (`composer_overview.members`)."""
    found: list = []
    for word in composer.subject_terms(subject)[:3]:
        for other in sorted(a for a in composer_ask._alternatives(composer._stem(word)) if len(a) >= 3 and a.isalpha()):  # noqa: SLF001
            found += search_manager.keyword_search(session, other, limit=OVERVIEW_LIMIT) + _filed_under(session, [other])
    return found


def _filed_under(session: Session, terms: list[str], limit: int = OVERVIEW_LIMIT) -> list:
    """Notes tagged with, or filed in a category named for, a word of the
    topic ("games" finds the notes tagged games that never say the word)."""
    words = [t.lower() for t in terms if len(t) >= 3][:3]
    if not words:
        return []
    clauses = tags_repo.mentioning(words, whole_start=True)
    #: A word at the start of the name or after a space in it ("study" is in "Courses & study").
    said = [like_escape(w.rstrip("s")) for w in words]
    named = select(Category.id).where(or_(*(func.lower(Category.name).like(pattern, escape=LIKE_ESCAPE) for w in said for pattern in (f"{w}%", f"% {w}%"))))
    clauses.append(Entry.category_id.in_(named))
    query = (
        select(Entry)
        .where(Entry.is_deleted == False, Entry.is_private == False, or_(*clauses))  # noqa: E712
        .order_by(Entry.created_at.desc())
        .limit(limit)
    )
    return list(session.scalars(query))


def _picture_notes(session: Session, terms: list[str]) -> list:
    """Notes holding a picture whose caption or read text has every word of
    the question's subject, at most `PICTURE_MATCHES`."""
    words = [t.lower() for t in terms if len(t) >= 3][:4]
    if not words:
        return []
    said = func.lower(func.coalesce(MediaUpload.caption, "") + " " + func.coalesce(MediaUpload.vision_ocr_text, "") + " " + func.coalesce(MediaUpload.ocr_text, ""))
    names = list(session.scalars(
        select(MediaUpload.filename).where(*(said.like(f"%{like_escape(w)}%", escape=LIKE_ESCAPE) for w in words)).limit(PICTURE_MATCHES)
    ))
    if not names:
        return []
    holding = or_(*(Entry.content.like(f"%{like_escape(name)}%", escape=LIKE_ESCAPE) for name in names))
    return list(session.scalars(select(Entry).where(Entry.is_deleted == False, holding).limit(PICTURE_MATCHES)))  # noqa: E712


@dataclass
class _Found:
    """What `_prepare` learns about one question, filled in stage by stage."""

    detected: str
    stats: object = None
    entries: list = field(default_factory=list)
    mode: str = "none"
    meaning_loading: bool = False
    meaning_off: bool = False
    #: Notes that mention the one day asked about (E6).
    mentioned: set = field(default_factory=set)
    #: Ids that are here because they are *connected* to a match rather than
    #: because they matched. The user asked about one thing and is shown notes
    #: about another; without saying why, the panel looks like the search
    #: misfired, and the model, told nothing, would report them as results.
    connected_ids: set = field(default_factory=set)
    match_info: dict = field(default_factory=dict)
    when_phrase: str = ""
    #: As of a date: per note, the revision its text came from.
    as_of_then: dict = field(default_factory=dict)
    #: The days a time recall asked about, so the documents made then are read beside the notes.
    window: tuple | None = None


@dataclass
class _NoteCtx:
    """What turning an entry into a prompt row needs besides the entry."""

    session: Session
    found: _Found
    attached_ids: set
    zone: object
    today: object
    time_words: dict
    files_on: dict
    as_of: "date | None"
    #: Category names for every entry in one query, not one per note.
    category_names: dict = field(default_factory=dict)


def _in_window(found: _Found, session: Session, asked, question: str) -> None:  # noqa: ANN001
    """The window's own notes are the pool: a time recall, or a question whose
    only words are its window and the question's verb."""
    archived = question_noise.asks_archived(question)
    if asked.kind == "recall":
        found.entries = search_manager.entries_between(session, asked.window[0], asked.window[1], archived=archived)
    else:
        #: "How much did I save in October": the question's own verb is no
        #: term, so nothing was searched; the window's notes are the pool the
        #: readers ask (audit 1031 C3).
        stems = composer_intent.window_verb_stems(question, asked.window_phrase)
        window = search_manager.entries_between(session, asked.window[0], asked.window[1], limit=1000 if stems else 40, archived=archived)
        found.entries = [e for e in window if composer_intent.holds_any(stems, e.content or "")][:40] if stems else window
    found.mode, found.connected_ids, found.match_info, found.when_phrase = "window", set(), {}, asked.window_phrase
    found.window = asked.window


def _keep_window(found: _Found, asked) -> None:  # noqa: ANN001
    """**A subject inside a window keeps the window** (1324): "what did I
    write about sourdough last week" was answered with sourdough notes from
    six weeks, under a header that said "last week". The notes inside the
    window are the answer when there are any."""
    inside = [
        e for e in found.entries
        if e.id in found.mentioned or (e.created_at and asked.window[0] <= e.created_at.date() <= asked.window[1])
    ]
    if inside:
        found.entries = inside
        found.when_phrase = found.when_phrase or asked.window_phrase


def _with_each_side(session: Session, question: str, entries: list, locale: str | None) -> list:  # noqa: ANN001
    """A comparison needs both things in hand: a search for "Lisbon vs Porto"
    can fill its few slots with one side, so each side is searched on its own
    and the best of each is added."""
    sides = composer.compare_sides(question) or _lower_pair(session, question, entries, locale)
    if not sides:
        return entries
    merged = list(entries)
    seen = {e.id for e in merged}
    for side in sides:
        #: A side named by a title is that note, first (audit 1031 C50): at 207
        #: notes the five likest "dentist" were filler that said the word.
        titled = _titled_entry(session, side)
        if titled is not None:
            merged = [titled, *(e for e in merged if e.id != titled.id)]
            seen.add(titled.id)
        for entry in search_manager.retrieve_detailed(session, side, deps.get_embeddings(), limit=3, locale=locale).entries:
            if entry.id not in seen:
                seen.add(entry.id)
                merged.append(entry)
    return merged


def _lower_pair(session: Session, question: str, entries: list, locale: str | None) -> tuple[str, ...] | None:  # noqa: ANN001
    """"tom and sara" typed in lower case is two names when the notes hold both words: each word is
    looked up on its own (the pool of the pair may hold only one), then the pair is read with those
    notes' words (W7 B5, composer-r6 L23)."""
    pair = composer_tables.LOWER_PAIR.match(question.strip())
    if not pair:
        return None
    pooled = list(entries)
    for word in (pair.group("a"), pair.group("b")):
        pooled += search_manager.retrieve_detailed(session, word, deps.get_embeddings(), limit=3, locale=locale).entries
    notes = [{"content": e.content or ""} for e in pooled]
    words, texts = composer_ask.NOTE_WORDS.set(composer._note_words(notes)), composer_ask.NOTE_TEXTS.set(tuple(n["content"] for n in notes))  # noqa: SLF001
    try:
        return composer.compare_sides(question)
    finally:
        composer_ask.NOTE_TEXTS.reset(texts)
        composer_ask.NOTE_WORDS.reset(words)


def _titled_entry(session: Session, side: str):  # noqa: ANN202
    """The note whose title is `side` ("the dentist", "Lisbon trip"), or None."""
    core = re.sub(r"^(?:the|my|our)\s+|\s+notes?$", "", " ".join(side.lower().split()), flags=re.I).strip()
    if len(core) < 3:
        return None
    rows = session.scalars(
        select(Entry).where(
            Entry.content.ilike(f"#%{like_escape(core)}%", escape=LIKE_ESCAPE), Entry.is_deleted.is_(False), Entry.deleted_at.is_(None), Entry.is_private.is_(False),
        ).limit(20)
    ).all()
    return next((e for e in rows if re.sub(r"^(?:the|a|an)\s+", "", composer_frame.note_title(e.content).lower().strip()) == core), None)


def _with_records(session: Session, question: str, entries: list, locale: str | None) -> list:  # noqa: ANN001
    """An open checklist item may be done in a later note ("Renewed my library
    membership today" beside "[ ] Renew library membership"): a question
    about the checklist's state also fetches the notes that name its open
    items, so the answer reads one state for the item (second eye F3). So
    does any answer that may show the checklist: an overview's boxes said
    "none done" beside a note that records one (F15)."""
    doings = [d for e in entries for d in composer_slots.open_doings(e.content or "")][:6]
    if not doings:
        return entries
    merged, seen = list(entries), {e.id for e in entries}
    for doing in doings:
        for entry in search_manager.retrieve_detailed(session, doing, deps.get_embeddings(), limit=2, locale=locale).entries:
            if entry.id not in seen:
                seen.add(entry.id)
                merged.append(entry)
    return merged


def _or_empty_notebook(session: Session, line: str) -> str:
    """"I couldn't find any saved notes matching that question" reads as if notes exist: with no note and no
    document at all the answer says so, and how to begin (round 3, R3-30); a notebook of documents keeps the
    plain miss, which the related items follow. A private note is a note: it is counted (and only counted),
    and a line that says more than the plain miss (a day with nothing in it, with where the
    notes run) is kept."""
    if line != librarian.NO_RESULTS_MESSAGE:
        return line
    if content_repo.anything_kept(session):
        return line
    return "You have no notes yet. Write one, or type note: and what you want to keep."


def _slips_put_right(question: str) -> str:
    """The question searched with its slips put right ("wat do i know abuot tokio"), which the search would
    otherwise match on "wat" and "abuot" (round 3, R3-17)."""
    return question_noise.slips_only(question)


def _with_holders(session: Session, question: str, entries: list, locale: str | None) -> list:  # noqa: ANN001
    """"The number for the dentist" is searched on the word "number" too, which
    fills the five places with other notes that say number: the person's notes are fetched as well, on the name alone, so a
    denial is made over everything the notebook says of them (round 3, R3-2)."""
    whose = composer_property.subject(question) if composer_property.asked(question) == "phone" else ""
    if not whose:
        return entries
    have = {e.id for e in entries}
    found = search_manager.retrieve_detailed(session, whose, deps.get_embeddings(), limit=6, locale=locale).entries
    return entries + [e for e in found if e.id not in have]


def _records_beside(session: Session, question: str, attached: list, locale: str | None) -> list:  # noqa: ANN001
    """A closed set of one named note ("what is in my admin bits note") still
    reads a box a later note records as done: the notes that name its open
    items ride beside it, never in its place (second eye F15)."""
    have = {e.id for e in attached}
    return [e for e in _with_records(session, question, list(attached), locale) if e.id not in have]


_CHECKBOX = re.compile(r"^\s*[-*]\s*\[[ xX]\]", re.M)


def _whole_pool(session: Session, question: str, found: _Found) -> None:
    """"How much have I spent", "my biggest expense", "what's unpacked": the
    answer is over every note that records the thing (spending, an amount, a
    checklist), which the five likest never were ("spent" does not match
    "Spending October"; 2026-10-30 sweep). None at all keeps the ordinary
    retrieval, so the answer can say no note holds it."""
    mode = "money"
    if composer_money.asks(question) or composer_sum.asks_most(question):
        holds = lambda text: composer_money.records_amounts(text) or composer_sum.holds_amount(question, text)  # noqa: E731
    elif composer_slots.asks_state(question):
        holds, mode = (lambda text: bool(_CHECKBOX.search(text))), "checklist"  # noqa: E731
    else:
        return
    if recorded := _scan_notes(session, holds):
        found.entries = recorded
        found.mode, found.connected_ids, found.match_info = mode, set(), {}


def _scan_notes(session: Session, holds) -> list:  # noqa: ANN001
    """The newest notes `holds` is true of, page by page and stopping at the
    scan's hit cap, never at the first page (a notebook past 400 notes
    answered "no amounts"; second eye F1)."""
    found: list = []
    offset = 0
    while len(found) < composer_money.SCAN_HITS:
        page = manager.list_entries(session, limit=composer_money.SCAN_PAGE, offset=offset)
        found += [e for e in page if holds(e.content or "")]
        if len(page) < composer_money.SCAN_PAGE:
            break
        offset += composer_money.SCAN_PAGE
    return found[: composer_money.SCAN_HITS]


def _composer_reads(question: str) -> bool:
    """Whether a counted-notes request is one the composer answers whole
    (a ranking, an order, a count at one end of it) and so reads its own pool."""
    return composer_versus.asks(question) or bool(composer_lists.list_order(question) or composer_lists.counted_order(question))


#: Text this app read out of a picture or an attached file and put under a
#: note (`_media_readings`, `_attachment_readings`) is not the person's words:
#: a note carrying it taints the turn like a clipped page (audit 1028 E4).
_READ_TEXT_MARKERS = ('text in it: "', "[Files attached to this note, as this app read them:")


def _holds_read_text(content: str) -> bool:
    return any(marker in content for marker in _READ_TEXT_MARKERS)


def _note_content(ctx: _NoteCtx, entry) -> str:  # noqa: ANN001
    session, found = ctx.session, ctx.found
    content = found.as_of_then[entry.id].text if entry.id in found.as_of_then else manager_text.readable_content(entry)
    if entry.id in ctx.attached_ids:
        # Only for notes the user picked by hand. A retrieved note is a
        # candidate; an attached one is the subject of the question, and that is
        # worth the extra characters: doing this for all ten search hits would
        # spend the notes budget on pictures nobody asked about.
        return f"{content}{_media_readings(session, content)}{_attachment_readings(session, entry.id)}"
    if _mostly_pictures(content):
        return f"{content}{_media_readings(session, content)}"
    if _MEDIA_REF.search(content or ""):
        #: **A picture's caption is the note's content** (CHAT_PLAN decision
        #: 37; the owner: "Note captions arent counted as note content"): every
        #: retrieved note with a picture brings what its pictures show, one line
        #: each, so an answer can quote the caption. The text read in them stays
        #: for a note that is mostly pictures or was picked by hand: it can run
        #: to pages.
        return f"{content}{_media_readings(session, content, captions_only=True)}"
    return content


def _document_row(document, session: Session | None = None) -> dict:  # noqa: ANN001
    # The same shape `_context_note` builds, by hand rather than through it: a
    # Document has no category/tags and its id lives in a different table than
    # Entry's, so folding it through the Entry-shaped helper would be the wrong
    # abstraction, not a shortcut. `connected`/`match_info` are never true for a
    # hand-picked document, same as an attached note.
    return {
        "id": document.id,
        "content": f"{document.title}\n\n{document.content}",
        "created_at": document.created_at.isoformat() if document.created_at else None,
        "category": "Document",
        "kind": "document",
        #: An imported document's text is somebody else's (audit 1028 E4).
        "from_outside": bool(session is not None and manager.document_came_from_outside(session, document.id)),
        "attached": True,
        "connected": False,
        "match_info": None,
    }


def _stats_out(stats) -> dict | None:  # noqa: ANN001
    #: The computed answer, when this was a question about the notebook's shape
    #: rather than its contents. `text` is already a complete answer, which is
    #: what makes these work with the model stopped.
    if stats is None:
        return None
    return {"kind": stats.kind, "text": stats.text, "facts": stats.facts, "offer": stats.offer}


def _raw_results(session: Session, found: _Found) -> list:
    from tessellate.api.routes_entries import _to_out_bulk  # avoids a route-module cycle

    rows = []
    #: In a fixed number of queries: one `_to_out` per note was five queries
    #: each, 120 for a 24-note answer (2026-11-02).
    for entry, out in zip(found.entries, _to_out_bulk(session, list(found.entries)), strict=True):
        if entry.id in found.as_of_then:
            out = out.model_copy(update={"content": found.as_of_then[entry.id].text})
        rows.append(out)
    return rows


def _chat_payload(session: Session, found: _Found, notes: list[dict], config, as_of) -> dict:  # noqa: ANN001
    #: The cut pool's size travels with the notes to wherever the answer is composed.
    pool = next((p for p in (getattr(e, "_overview_pool", None) for e in found.entries) if p), None)
    if pool and notes:
        notes[0]["overview_pool"] = list(pool)
    return {
        "notes": notes,
        "intent": found.detected,
        "stats": _stats_out(found.stats),
        #: The search model was still loading, so this one read words only
        #: (`search_manager.query_vector`): said in Why, and when nothing
        #: matched, said with the answer.
        "meaning_loading": found.meaning_loading,
        "meaning_off": found.meaning_off,
        "raw_results": _raw_results(session, found),
        #: The day asked about and, per note, the revision its text came from
        #: (None for a note that read the same then as now).
        "as_of": as_of.isoformat() if as_of is not None else None,
        "as_of_revisions": {str(i): then.revision_id for i, then in found.as_of_then.items()},
        #: Words for each retrieved note's pictures, for the thumbnails an
        #: answer draws beside a citation (INBOX 502, `_picture_alts`).
        "picture_alts": _picture_alts(session, found.entries),
        "picture_sizes": _picture_sizes(found.entries),
        "search_mode": found.mode,
        # Sent beside the results rather than as a field on EntryOut: it is a
        # fact about this search, not about the note, and every other route that
        # returns an entry would otherwise carry a field that is always false.
        "connected_ids": sorted(found.connected_ids),
        # str() keys: JSON object keys are always strings and Pydantic's
        # dict[str, dict] won't silently coerce an int key.
        "match_info": {str(k): v for k, v in found.match_info.items()},
        "when_phrase": found.when_phrase,
        "style": config.get_preference("communication_style", "friendly"),
        # The name and the capped "About me", or nothing while the profile
        # switch is off: `librarian.profile_from_config` decides.
        "profile": librarian.profile_from_config(config),
    }


def _frame_matches(session: Session, question: str, notes: list[dict], match_info: dict, mode: str) -> None:
    """Why each Matching records card is there, in words, and which shown
    notes the person linked (INBOX 1310, the owner: "it has no frame of
    reference for how related each shown matching record is or why it was
    shown and how the shown notes link"). Each note gets `linked_to`, the
    shown notes it is linked to; each entry's `match_info` gets `why`, made
    for a note that came by date or recency too. Facts either way: the model
    reads them as context, the composer says them (decision 75)."""
    ids = [n["id"] for n in notes]
    if not ids:
        return
    linked: dict[int, list[int]] = {i: [] for i in ids}
    rows = relations_repo.among(session, ids)
    reasons: dict[int, dict[int, str]] = {i: {} for i in ids}
    for a, b, reason in rows:
        #: Once each: two notes linked both ways are one link to the reader.
        if b not in linked[a]:
            linked[a].append(b)
        if a not in linked[b]:
            linked[b].append(a)
        if reason:
            reasons[a].setdefault(b, reason)
            reasons[b].setdefault(a, reason)
    for note in notes:
        note["linked_to"] = linked[note["id"]]
        #: What the person wrote of each link, for "why did I link these" (audit 1031 C49).
        note["link_reasons"] = reasons[note["id"]]
    for key, reason in composer_frame.reasons(question, notes, mode).items():
        match_info.setdefault(int(key), {})["why"] = reason
    for note in notes:
        note["match_info"] = match_info.get(note["id"])


def _named_rows(session: Session, question: str) -> list[dict]:
    """A document, board or map the question names by title, read first as
    itself (not as an attachment the person picked)."""
    named_docs, named_boards = _named_sources(session, question)
    #: Said by its title and words, as a note is (`_board_rows`).
    boards = _board_rows(_attached_boards(session, named_boards))
    named = [_document_row(d, session) for d in named_docs] + boards
    for row in named:
        row["attached"] = False
        row["named"] = True
    return named


#: How many boards, maps and documents a question's words may bring in.
MATCHED_SOURCES = 3


def _holds_every(text: str, terms: list[str]) -> bool:
    """Every term is a word (or the start of one) in `text`."""
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return all(any(w.startswith(t.lower()) for w in words) for t in terms)


def _board_rows(boards: list[dict], terms: list[str] | None = None) -> list[dict]:
    """Attached-board rows said as notes are: the title and its words, without
    the "Mind map: X (4 nodes)" head that is for a model. With `terms`, only
    those holding every term."""
    kept = []
    for row in boards:
        head, _, outline = row["content"].partition("\n\n")
        title = head.split(": ", 1)[-1].splitlines()[0]
        if terms is not None and not _holds_every(f"{title} {outline}", terms):
            continue
        row["content"] = f"# {title}\n\n{outline}"
        kept.append(row)
    return kept


def _holding(session: Session, hits: list, terms: list[str], skip: set[tuple[str, int]]) -> tuple[list, list[int]]:
    """The documents and board ids among search `hits` not yet in, a document
    kept only where its text holds every term."""
    docs, boards = [], []
    for hit in hits:
        if ("document" if hit.kind == "document" else "board", hit.ref_id) in skip:
            continue
        doc = documents_repo.find(session, hit.ref_id) if hit.kind == "document" else None
        if doc is not None and doc.deleted_at is None and _holds_every(f"{doc.title} {doc.content}", terms):
            docs.append(doc)
        elif hit.kind != "document":
            boards.append(hit.ref_id)
    return docs, boards


def _matched_rows(session: Session, question: str, skip: set[tuple[str, int]]) -> list[dict]:
    """Boards, maps and documents whose own words hold the question's words
    (composer work list 1: "tell me about IaaS" found nothing when IaaS was a
    node on a map, because the note search reads notes). Found by the one
    search index, then kept only where every term is really in the text, so a
    partial match does not bring a source in. Read as the named ones are, so
    the answer says the kind ("on your Cloud map"). `skip` holds
    (document or board, id) pairs already in."""
    terms = [t for t in search_manager._meaningful_terms(question or "") if t not in composer_ask._ASKING_WORDS]  # noqa: SLF001
    if not terms or len(question or "") > 300:
        return []
    hits = engine.search(session, " ".join(terms), kinds=["board", "map", "document"], limit=8, hybrid=False)
    docs, boards = _holding(session, hits, terms, skip)
    rows = [_document_row(d, session) for d in docs] + _board_rows(_attached_boards(session, boards), terms)
    for row in rows:
        row["attached"] = False
        row["named"] = True
    return rows[:MATCHED_SOURCES]


#: How many documents of a window are read beside its notes.
WINDOW_DOCUMENTS = 8


def _window_documents(session: Session, found: "_Found") -> list[dict]:
    """The documents made in the days a time recall asked about, as rows beside
    its notes: "what did I write on 3 November" counts a diagram made that day
    too (INBOX 1739). Read by the composer and the model alike (decision 75)."""
    if found.mode != "window" or not found.window:
        return []
    rows = [_document_row(d, session) for d in documents_repo.made_between(session, found.window[0], found.window[1], WINDOW_DOCUMENTS)]
    for row in rows:
        row["attached"] = False
    return rows


def _with_sources(session: Session, question: str, notes: list[dict], mode: str) -> list[dict]:
    """The notes with the boards, maps and documents the question names or
    whose words hold it. Where the note search found nothing by its words, a
    source that holds them leads; where it did, the notes lead and it follows."""
    named = _named_rows(session, question)
    taken = {("document" if r["kind"] == "document" else "board", r["id"]) for r in named}
    matched = _matched_rows(session, question, taken)
    return named + (matched + notes if mode in ("recent", "none") else notes + matched)
