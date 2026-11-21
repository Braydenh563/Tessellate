"""A recall by time ("what did I write last week") and the overview of a
topic: its notes grouped by theme, said as a lead and bullets.

Moved whole from `composer.py` (audit AR3, gods-1101): the code is unchanged,
and `composer` re-exports every name here that anything reads, so
`composer._recall` still works. Imports run one way, down
the layer list in `composer.py`'s docstring, never back to `composer`.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date

from tessellate.ai import composer_frame, composer_tables
from tessellate.ai.composer_answer import _Answer
from tessellate.ai.composer_ask import _MONTHS, _holds, _overview, _stem, _words, asks_time, compare_sides, rephrase, subject_terms
from tessellate.ai.composer_body import _overview_line
from tessellate.ai.composer_dialogue import Dialogue, NEXT_MAX_CHARS
from tessellate.ai.composer_empty import _as_typed, window_said
from tessellate.ai.composer_help import _in_window, _result
from tessellate.ai.composer_intent import AROUND_DAYS, Plan, plan
from tessellate.ai.composer_phrases import PHRASES
from tessellate.ai.composer_read import NoteView, Sentence, _ITEM, _distinct_ids, _heading_text, _title, _unit, read_note
from tessellate.core.lazyre import lazy_compile


#: A recall by time lists at most this many notes; the count says how many.
RECALL_NOTES = 8


#: A question about the act of writing: only the day a note was made answers it.
_WROTE_VERB = lazy_compile(r"\b(?:wrote|write|written|made|created|added|saved|captured|jotted|typed)\b", re.I)


#: A question that asks for everything on a subject rather than one fact:
#: answered by how many notes mention it, then the sentence most of them lean
#: towards (`centrality`), then one sentence from each other note.
_BROAD = lazy_compile(
    r"^\s*(?:what (?:do|did|have) (?:i|we|my notes|you) (?:know|say|said|written|write|wrote|got|have)\b"
    r"|what(?:'s| is) in my notes\b|tell me (?:about|everything)\b|everything (?:about|on)\b"
    r"|summari[sz]e\b|give me an overview\b|(?:an )?overview of\b"
    r"|(?:is there )?anything (?:about|on)\b|do i have (?:any )?(?:notes? )?(?:about|on)\b"
    r"|have i (?:written|got|noted) (?:anything |down )?(?:about|on)\b|what(?: is|'s)? the deal with\b"
    r"|what do (?:i|you) have on\b|how many (?:of my )?notes\b|catch me up on\b|fill me in on\b|bring me up to speed on\b)",
    re.I,
)


_WINDOW_NOUN = lazy_compile(r"\b(weekend|week|month|year|fortnight)\b", re.I)


def window_as_topic(p: Plan, views: list[NoteView]) -> bool:
    """Whether the window's noun is a note's title word ("plans for the weekend"
    with a note called "Weekend plans", R3-20). The title is then the subject:
    the window is dropped and the noun searched as a word, so no note written
    in the window is not "nothing". Ahead, not behind ("last week" with a
    "Weekly review" is a recall), and the word itself, not its stem."""
    noun = _WINDOW_NOUN.search(p.window_phrase or "")
    if not (noun and p.window and p.terms and p.kind != "recall") or re.match(r"(?:the )?last\b", p.window_phrase, re.I):
        return False
    word = re.compile(rf"\b{noun.group(1)}\b", re.I)
    if not any(v.titled and word.search(v.title or "") for v in views) or any(_in_window(v, p.window) for v in views):
        return False
    p.window, p.terms = None, list(dict.fromkeys([*p.terms, noun.group(1).lower()]))
    return True


#: Said for an "around <day>" window, where `said` would name the whole span.
def _near_said(out: _Answer, p: Plan) -> str:
    return f"within {_count_days(AROUND_DAYS)} days of {out.day(p.around)}"


def _count_days(n: int) -> str:
    return {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}.get(n, str(n))


def _recall_lead(out: _Answer, p: Plan, inside: list[NoteView], said: str, wrote: bool) -> None:
    """The count line. Notes that say the day were not all written on it: they
    are "dated", never "you wrote" (R3-8). The documents made in the window are
    counted beside the notes, named as documents (INBOX 1739)."""
    notes = [v for v in inside if v.kind != "document"]
    docs = [v for v in inside if v.kind == "document"]
    dated = not wrote and any(not (p.window[0] <= v.written <= p.window[1]) for v in notes if v.written)
    if dated and notes:
        out.m(out.count(len(notes)).capitalize()).t("recall_dated_note" if len(notes) == 1 else "recall_dated_notes").asked(said)
    else:
        _recall_count(out, notes, docs, said)
    out.t(("recall_near_b" if p.around else "recall_b") if len(inside) > 1 else "end_colon")


def _recall_count(out: _Answer, notes: list[NoteView], docs: list[NoteView], said: str) -> None:
    """"You wrote two notes and made one document on <day>": notes and documents, each named as what it is."""
    if docs and notes:
        out.t("recall_a").m(out.count(len(notes))).t("recall_note_and" if len(notes) == 1 else "recall_notes_and")
        out.m(out.count(len(docs))).t("recall_doc" if len(docs) == 1 else "recall_docs").asked(said)
    elif docs:
        out.t("recall_made").m(out.count(len(docs))).t("recall_doc" if len(docs) == 1 else "recall_docs").asked(said)
    else:
        out.t("recall_a").m(out.count(len(notes))).t("recall_note" if len(notes) == 1 else "recall_notes").asked(said)


def _recall_name(out: _Answer, view: NoteView) -> None:
    """A note's name and day: its title, or its own first words (R3-15). A
    note the timeline files under another day says both (INBOX 1739)."""
    if view.titled:
        out.name(view).dated_both(view)
    else:
        out.term(composer_frame.name_of(view.note), view).dated_both(view)


#: A short note about oneself is quoted as written, not retold (INBOX 1739).
QUOTE_WHOLE_CHARS = 240
_TRIVIA = lazy_compile(r"^\s*(?:who|where|which|how (?:tall|far|big|old|long|fast|deep))", re.I)
_NOTE_WORD = lazy_compile(r"\b(?:notes?|wrote|written|saved|entry|entries|reminders?|diary|journal)\b", re.I)


def trivia(question: str) -> bool:
    """A general-knowledge question that carries a year ("who won the cup in 1966"):
    it asks about the world, so a window no note falls in is not the answer."""
    return bool(_TRIVIA.match(question) and re.search(r"\b(?:1\d|20)\d\d\b", question)) and not _PERSONAL.search(question) and not _NOTE_WORD.search(question)


_PERSONAL = lazy_compile(r"\b(?:i|i'm|i've|i'd|i'll|my|me|mine|myself|we|our)\b", re.I)


def _own_words(view: NoteView) -> list[Sentence]:
    """The body of a short first-person note, sentence by sentence and without
    its title, or [] for any other note (a long one, a list, a document)."""
    if view.kind != "note" or not view.written:
        return []
    content = str(view.note.get("content") or "")
    start = _title(content)[1] if view.titled else 0
    units = [s for s in view.sentences if s.start >= start]
    said = " ".join(s.text for s in units)
    if not units or any(s.kind != "prose" for s in units) or len(said) > QUOTE_WHOLE_CHARS or not _PERSONAL.search(said):
        return []
    return units


def _recall_quoted(out: _Answer, view: NoteView, units: list[Sentence]) -> None:
    """"Title (3 November): “its words”": the title once, the words as written.
    A note with no title is its words, so its day stands in the title's place."""
    if view.titled:
        out.name(view).dated_both(view)
    else:
        about = out.placed_day(view)
        out.written_about(view, about, top=True) if about else out.m(out.day(view.written))
    out.t("colon", "open_quote")
    before, out.verbatim = out.verbatim, True
    for i, unit in enumerate(units):
        out.t("space") if i else None
        out.q(unit, [])
    out.verbatim = before
    out.t("close_quote")


def _nearest_first(out: _Answer, p: Plan, inside: list[NoteView]) -> tuple[list[NoteView], str]:
    """The days either side, the nearest first; "what else" leaves the day itself, which the turn before gave."""
    kept = [v for v in inside if not (p.others and v.written == p.around)]
    kept.sort(key=lambda v: (abs((v.written - p.around).days), -v.rank, v.id))
    return kept, _near_said(out, p)


def _recall(out: _Answer, p: Plan, views: list[NoteView], question: str) -> None:
    """Recall by time (decision 31's schema): the notes in the window, newest
    first, grouped by day, under the count; "nothing from then" when none."""
    wrote = bool(_WROTE_VERB.search(question or ""))
    #: A board or a mind map is made, not written: it is no "note" in the count.
    inside = sorted(
        (v for v in views if _in_window(v, p.window, mentions=not wrote) and str(v.note.get("kind") or "note") not in ("board", "map")),
        key=lambda v: (v.written, -v.rank), reverse=True,
    )
    said = window_said(_as_typed(p.window_phrase, question), p.window)
    if p.around:
        inside, said = _nearest_first(out, p, inside)
    if not inside:
        out.t("recall_none").asked(said).t("stop")
        return
    _recall_lead(out, p, inside, said, wrote)
    for view in inside[:RECALL_NOTES]:
        out.t("line", "bullet")
        _recall_row(out, view)
    if len(inside) > RECALL_NOTES:
        out.t("para", "recall_more_a").m(out.count(len(inside) - RECALL_NOTES)).t("recall_more_b")


def _recall_row(out: _Answer, view: NoteView) -> None:
    """One bullet: a document by name, a short personal note quoted, any other by name and its best line."""
    if view.kind == "document":
        out.t("doc_lead").name(view).dated_both(view).t("stop")
        return
    own = _own_words(view)
    if own:
        _recall_quoted(out, view, own)
        return
    _recall_name(out, view)
    #: A picture's note as what it shows and its words; a note's
    #: heading with the sentence after it (INBOX 787).
    units = _overview().best_line(view.sentences, set()) or _label_line(view)
    if not units or _restates_name(view, units):
        out.t("stop")
        return
    out.t("colon")
    _overview_line(out, units, set())


def _restates_name(view: NoteView, units: list[Sentence]) -> bool:
    """A line that is only the note's name again (“milk” (27 October): Milk.): the name already says it (E18)."""
    plain = lambda text: re.sub(r"[\W_]+", " ", text).strip().lower()  # noqa: E731
    return plain(" ".join(u.text for u in units)) == plain(composer_frame.name_of(view.note))


def _label_line(view: NoteView) -> list[Sentence]:
    """The first line under the heading of a note with no quotable sentence
    (its body is a label such as "Blockers: none."): listing by date needs a
    day and a name, not a claim, so the line stands in for the sentence."""
    content = str(view.note.get("content") or "")
    offset = 0
    for line in content.splitlines(keepends=True):
        start, offset = offset, offset + len(line)
        if not line.strip() or _heading_text(line) is not None or line.strip().startswith(("```", "![", "|")):
            continue
        item = _ITEM.match(line)
        unit = _unit(view, content, start + (item.end() if item else 0), start + len(line.rstrip("\r\n")), "item", None)
        return [unit] if unit else []
    return []


# --- the overview of a topic (INBOX 787) ------------------------------------------

#: At most this many notes in an overview, and this many under one thread:
#: past these it is the records list again, which is beside the answer.
OVERVIEW_NOTES = 8


OVERVIEW_PER_THEME = 4


#: The subject is a name ("Jake"): the lead says where it comes up, and
#: its notes are not grouped (each is about them already).
_PERSON = lazy_compile(r"^[A-Z][\w'-]+$")


def _with_matched(found: list[NoteView], views: list[NoteView]) -> tuple[list[NoteView], int]:
    """K30: the records the search matched count too (by meaning, not only by
    the category); with any, the count filed under it, for the lead (else 0)."""
    matched = [v for v in views if v not in found and v.note.get("match_info")]
    if not matched:
        return found, 0
    return sorted([*found, *matched], key=lambda v: v.rank), len(found)


def _overview_answer(
    question: str, notes: list[dict], *, today: date, voice: str, said: str, prefer: str, dialogue: Dialogue | None = None,
) -> dict | None:
    """A topic asked about as a whole ("games notes", "what did I write about
    uni", "who is Jake"), answered as a person would: how many notes and
    over which days, the thread most share, the notes grouped by it with a
    day and one short line each, the name that links them, and what to ask
    next. None when the question is not one, or fewer than two notes are
    about it (the question's own shape answers those)."""
    subject = _overview_subject(question, today) if not (said or prefer) else None
    if not subject:
        return None
    views = [v for v in (read_note(n, i) for i, n in enumerate(_distinct_ids(notes or []))) if v]
    stems = _subject_stems(subject)
    head = next((_stem(t) for t in subject_terms(subject)), "")
    found = _overview().members(stems, views, _holds, head)
    if len(found) < 2 or not _overview_over_broad(question, stems, views):
        return None
    found, filed = _with_matched(found, views)
    out = _Answer({v.id: v for v in views}, today)
    out.voice, out.question, out.subject = composer_tables.voice_of(voice), question, stems
    #: No joining words twice in a conversation (decision 25).
    out.used = set(dialogue.used) if dialogue is not None else set()
    #: A name from a body is no heading for notes that were filed under the
    #: topic or matched it by meaning ("Atlas" under "courses & study", audit
    #: 1031 C39): the filing is the grouping, the notes follow in one list.
    themes = [] if _PERSON.match(subject) or filed else _overview().themes(found, stems, _stem, views)
    _overview_lead(out, question, subject, found, themes, filed)
    shown = _overview_groups(out, found, themes, stems)
    _overview_links(out, found, themes, stems, views)
    _overview_rest(out, _overview().pooled(len(found)) - shown)
    result = _result(out.parts, "overview", out.rows, _overview_next(question, subject, found, themes))
    result["broad"] = True
    return result


def _overview_rest(out: _Answer, left: int) -> None:
    """What the groups did not show: one more, or a count of more."""
    if left == 1:
        out.t("para", "ov_one_more")
    elif left > 1:
        out.t("para", "ov_more_a").m(out.count(left)).t("ov_more_b")


def _month(out: _Answer, when: date) -> str:
    """"July", or "July 2025" outside this year: a span's ends, by month, so
    the days the lines below give are not said twice (decision 52)."""
    name = _MONTHS[when.month - 1]
    return name if when.year == out.today.year else f"{name} {when.year}"


def _overview_subject(question: str, today: date) -> str | None:
    """The topic a question asks about as a whole, when nothing else in it
    (a time, a tag, a sum, a recall, an insight) answers it first: "any
    patterns in my golf notes" has the "<topic> notes" frame, but it asks for
    the measurement, which the insight path says. Two sides named ("compare
    my running notes and my baking notes") are the side-by-side's, as in the
    digest (`_kind_if_mine`): an overview of both read "two notes about
    compare my running notes and my baking" (audit 1029 C36)."""
    subject = _overview().topic(question)
    p = plan(question, today) if subject else None
    if p is None or p.window or p.constraints or p.kind in ("utility", "recall", "insight"):
        return None
    if p.shape == "compare" and compare_sides(question):
        return None
    return subject


def _subject_stems(subject: str) -> set[str]:
    if subject == _overview().DOING:
        return {subject}
    return {_stem(t) for t in subject_terms(subject)} or {_stem(w) for w in _words(subject)}


def _overview_over_broad(question: str, stems: set[str], views: list[NoteView]) -> bool:
    """A broad question ("what do I know about sourdough") keeps its own
    answer (INBOX 729: how many notes mention it, the note named for it
    first) unless its notes are filed under the subject more than they say
    it: "summarise my uni notes" found the one note that says "uni" and
    missed the five tagged uni."""
    if not (_BROAD.match(question) or _BROAD.match(rephrase(question))):
        return True
    filed = sum(1 for v in views if any(_holds(stem, v.filed_words) for stem in stems))
    worded = sum(1 for v in views if all(_holds(stem, v.words) for stem in stems))
    return filed > worded


def _span_of(out: _Answer, views: list[NoteView]) -> None:
    """", from July to September" over the notes' days; ", all from
    September" when they share a month."""
    days = sorted(v.written for v in views if v.written)
    if not days or not asks_time(getattr(out, "question", "")):
        return
    first, last = _month(out, days[0]), _month(out, days[-1])
    if first == last:
        out.t("ov_span_one").m(first)
    else:
        out.t("ov_span_a").m(first).t("ov_span_b").m(last)


def _overview_lead(out: _Answer, question: str, subject: str, found: list[NoteView], themes: list, filed: int = 0) -> None:
    """The first sentence answers: how many notes, over which days, and the
    thread most of them share."""
    said = _as_typed(subject, question)
    if subject == _overview().DOING:
        out.m(out.count(len(found)).capitalize()).t("ov_doing")
        _span_of(out, found)
        out.t("stop")
        return
    if _PERSON.match(subject):
        out.asked(said).t("ov_who_mid").m(out.count(len(found))).t("ov_who_end")
        _span_of(out, found)
        out.t("stop")
        return
    out.t("ov_lead_a").m(out.count(_overview().pooled(len(found)))).t("ov_lead_b").asked(said)
    _span_of(out, found)
    if filed:
        out.t("semicolon").m(out.count(filed)).t("ov_filed" if filed > 1 else "ov_filed_one")
    if themes:
        label, held = themes[0]
        out.t("semicolon").term(label, held[0]).t("ov_theme_mid").m(out.count(len(held))).t("ov_theme_end")
    else:
        out.t("stop")


def _overview_groups(out: _Answer, found: list[NoteView], themes: list, stems: set[str]) -> int:
    """The notes under their threads, then the rest; how many were shown."""
    themed = {v.id for _, held in themes for v in held}
    rest = [v for v in found if v.id not in themed]
    shown = 0
    for label, held in themes:
        out.t("para", "bold").term(label, held[0]).t("bold")
        shown += _overview_bullets(out, held[:OVERVIEW_PER_THEME], stems | {_stem(label.lower())}, {_stem(label.lower())})
    if rest and shown < OVERVIEW_NOTES:
        out.t("para")
        if themes:
            out.t("bold", "ov_also", "bold")
        shown += _overview_bullets(out, rest[: OVERVIEW_NOTES - shown], stems, set(), first=not themes)
    return shown


def _overview_bullets(out: _Answer, views: list[NoteView], stems: set[str], text_stems: set[str], first: bool = False) -> int:
    """One line a note, oldest first: its day, then the line that stands
    for it (a picture's reading as what it shows and the words in it)."""
    for i, view in enumerate(sorted(views, key=lambda v: (v.written or date.min, v.rank))):
        #: A note of a word or two ("something lol") has no quotable sentence: its first line stands in, never an empty bullet.
        units = _overview().best_line(view.sentences, stems, text_stems) or _label_line(view)
        if i or not first:
            out.t("line")
        out.t("bullet")
        if view.written and asks_time(getattr(out, "question", "")):
            day = out.day(view.written)
            out.m(day[:1].upper() + day[1:]).t("colon")
        elif view.titled or not view.written:
            #: The card carries the day (INBOX 1441): a titled note is named.
            out.name(view, cap=True).t("colon")
        _overview_line(out, units, stems)
    return len(views)


def _overview_links(out: _Answer, found: list[NoteView], themes: list, stems: set[str], views: list[NoteView]) -> None:
    """A name two or more of the notes share that no thread named: what
    links them across the groups ("Jake is in two of these notes.")."""
    skip = {label.lower() for label, _ in themes} | {w for w in stems}
    for name, n in _overview().shared_names(found, skip, views):
        if _stem(name.lower()) in stems:
            continue
        holder = next(v for v in found if name in str(v.note.get("content") or ""))
        out.t("para").term(name, holder).t("ov_shared_mid").m(out.count(n)).t("ov_shared_end")
        return


def _overview_next(question: str, subject: str, found: list[NoteView], themes: list) -> list[list[tuple]]:
    """What to ask next, from what the notes hold: the biggest thread, a
    name that links them, and the latest on the subject."""
    picks: list[list[tuple]] = []
    for label, held in themes[:1]:
        picks.append([("template", PHRASES["ov_next_about"]), ("term", label, held[0].id), ("template", PHRASES["next_tag_b"])])
    picks += _overview_name_chip(found, subject, themes)
    picks += _overview_tag_chip(found, subject)
    said = _as_typed(subject, question)
    if len(said) <= 40 and subject != _overview().DOING:
        picks.append([("template", PHRASES["next_latest_a"]), ("asked", said), ("template", PHRASES["next_tag_b"])])
    return [p for p in picks if len("".join(part[1] for part in p)) <= NEXT_MAX_CHARS][:3]


def _overview_name_chip(found: list[NoteView], subject: str, themes: list) -> list[list[tuple]]:
    """A name in the notes that is neither a thread nor the subject."""
    asked = {_stem(w) for w in _words(subject)}
    skip = {label.lower() for label, _ in themes} | {w.lower() for w in _words(subject)} | {subject.lower()}
    for name, _n in _overview().shared_names(found, skip, least=1):
        if {_stem(w) for w in _words(name)} & asked:
            continue
        holder = next(v for v in found if name in str(v.note.get("content") or ""))
        return [[("template", PHRASES["ov_next_about"]), ("term", name, holder.id), ("template", PHRASES["next_tag_b"])]]
    return []


def _overview_tag_chip(found: list[NoteView], subject: str) -> list[list[tuple]]:
    """A tag two or more of the notes share that the subject is not: a
    thread the next question can pull ("study" under ideas)."""
    asked = {_stem(w) for w in _words(subject)}
    held = Counter(str(t) for v in found for t in dict.fromkeys(v.note.get("tags") or []) if not set(_words(str(t))) & asked)
    for tag, n in held.most_common(1):
        if n >= 2 and re.fullmatch(r"\w[\w -]{1,30}", tag):
            view = next(v for v in found if tag in (v.note.get("tags") or []))
            return [[("template", PHRASES["next_tag_a"]), ("filed", tag, view.id), ("template", PHRASES["next_tag_b"])]]
    return []


def _recall_next(window: tuple, views: list[NoteView]) -> list[list[tuple]]:
    """What to ask after a recall by time (INBOX 787: "last week" offered
    nothing): the threads through that time's notes, then a shared tag."""
    inside = [v for v in views if _in_window(v, window)]
    picks = [
        [("template", PHRASES["ov_next_about"]), ("term", label, held[0].id), ("template", PHRASES["next_tag_b"])]
        for label, held in _overview().themes(inside, set(), _stem, views)
    ]
    picks += _overview_tag_chip(inside, "")
    return [p for p in picks if len("".join(part[1] for part in p)) <= NEXT_MAX_CHARS][:3]
