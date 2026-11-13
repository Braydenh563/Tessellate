"""Laying out the answer by its shape: the opening, the lead, the other
notes, a timeline, a comparison, a broad summary, what is still open, the
newest.

Moved whole from `composer.py` (audit AR3, gods-1101): the code is unchanged,
and `composer` re-exports every name here that anything reads, so
`composer._body` still works. Imports run one way, down
the layer list in `composer.py`'s docstring, never back to `composer`.
"""

from __future__ import annotations

import contextvars
import re
from datetime import date

from tessellate.ai import composer_frame, composer_versus, question_noise, recognise as rec, utilities, when as when_words
from tessellate.ai import recognise_questions
from tessellate.ai.composer_answer import _Answer
from tessellate.ai.composer_ask import _holds, _overview, _stem, _words, subject_terms
from tessellate.ai.composer_quote import _ENDED, _joined, _list_block, _list_lead, _list_sentence, _lowered, _pick, _quotes, _said_before, _sentence_case, _unlike_before, _with_context, decap
from tessellate.ai.composer_read import NoteView, Sentence, _NUMBER_CUE, _cue
from tessellate.ai.composer_select import _Meaning, _was_said, centrality, disagree, select
from tessellate.ai.composer_unfound import _says_every
from tessellate.core.lazyre import lazy_compile


#: What the person said of insights (decision 60, `insights.Memory`), set by
#: `compose` for one answer: dismissed ones are not said, confirmed ones are
#: said as their own word.
_LEARNED: contextvars.ContextVar = contextvars.ContextVar("composer_learned", default=None)


_OPENERS = (
    "open_notes", "open_wrote", "open_put", "open_figure", "open_date", "open_where",
    "closest_a", "closest_b", "going_by", "notes_have", "wrote_on_a",
)


#: Each shape's openers, the empty one a bare quote. A count's and a date's
#: openers promise a number or a date, so they are offered only when the
#: sentence holds one (`_OPENER_NEEDS`); otherwise the plain ones are.
_OPENERS_BY_SHAPE = {
    "count": ("", "open_figure", "open_notes"),
    "when": ("", "open_date"),
    "explain": ("", "open_put", "open_notes"),
    "where": ("", "open_where", "open_notes"),
}
_PLAIN_OPENERS = ("", "open_notes", "open_wrote")
_OPENER_NEEDS = {"count": _NUMBER_CUE.search, "when": when_words.find}


def _opening(out: _Answer, s: Sentence, shape: str, question: str) -> None:
    """What comes before the strongest sentence on the first line, which is
    the answer: often nothing, the sentence itself, or a short opener chosen
    by the question so answers in a row do not start alike. The note is not
    named here; its citation follows the quote (`_Answer.cite`)."""
    view = out.views[s.note_id]
    if out.brief and shape not in ("yesno", "when"):
        #: Asked for briefly: the sentence itself, nothing before it.
        return
    if shape == "when" and view.written and not when_words.find(s.text):
        #: No date in the sentence: the day the note was written is the one
        #: date the app knows, and it is said as that and nothing more.
        out.t("wrote_on_a").m(out.day(view.written)).t("wrote_on_b")
        return
    options = _opener_options(out, s, shape, view)
    key = _pick(question, "lead", _fresh_openers(out, options))
    if key == "going_by" and _lowered(s):
        out.t("going_by", "comma")
        out.lower_next = True
    elif key:
        out.t("notes_have" if key == "going_by" else key)


_WORRIES = lazy_compile(r"\b(?:risks?|concerns?|worr(?:y|ies)|blockers?|problems?)\b", re.I)


def _opener_options(out: _Answer, s: Sentence, shape: str, view: NoteView) -> tuple[str, ...]:
    if shape == "yesno":
        #: A sentence that holds every word the question is about answers it
        #: in the note's own words: "Going by your notes, the deposit is
        #: paid." Never a yes or a no of the app's own (INBOX 688's rule).
        stems = out.subject
        #: An entry of a risks list says what might go wrong, not how things
        #: stand ("The pricing page is not signed off in time."): the nearest
        #: the notes come, said so (the blind panel's Q17).
        worry = s.kind == "item" and _WORRIES.search(view.title or "")
        return ("going_by", "notes_have") if stems and _says_every(stems, s, view) and not worry else ("closest_a", "closest_b")
    needs = _OPENER_NEEDS.get(shape)
    if needs is not None and not needs(s.text):
        return _PLAIN_OPENERS
    return _OPENERS_BY_SHAPE.get(shape, _PLAIN_OPENERS)


def _fresh_openers(out: _Answer, options: tuple[str, ...]) -> list[str] | tuple[str, ...]:
    """Not the opener the turn before opened with, and after a turn that
    opened with a bare quote, a worded one when there is one: two answers
    in a row never start alike (INBOX 741, vary openers across turns)."""
    fresh = [o for o in options if not (o and _said_before(out, o))]
    if out.previous and not any(_said_before(out, o) for o in _OPENERS):
        fresh = [o for o in fresh if o] or fresh
    return fresh or options


def _span(out: _Answer, views: list[NoteView]) -> None:
    """", from 3 March to 12 May" over these notes, when their days are known."""
    days = sorted(v.written for v in views if v.written)
    if not days:
        return
    if days[0] == days[-1]:
        #: ", from today", never ", on today" (the routing gold, 2026-10-11).
        said = out.day(days[0])
        out.t("from_span" if said in ("today", "yesterday") else "on_day").m(said)
    else:
        out.t("from_span").m(out.day(days[0])).t("to_span").m(out.day(days[-1]))


#: The shapes that ask for one fact: answered by it, and by at most
#: `FACT_OTHERS` more notes, since a chat answer to "how many" does not go on
#: for five paragraphs about everything else that has a number in it.
FACT_SHAPES = ("count", "when", "who", "yesno", "where")


FACT_OTHERS = 2


def _lead_block(out: _Answer, shape: str, lead: Sentence, chosen: list[Sentence], terms: list[str], question: str) -> None:
    """The first paragraph: the opening and the lead note's chosen sentences,
    in the note's own order; then its list, when the answer is a list."""
    view = out.views[lead.note_id]
    same = [s for s in chosen if s.note_id == lead.note_id]
    if shape == "when":
        same = [lead]
    if shape in FACT_SHAPES and lead.kind == "item":
        #: "Is the pricing page signed off?" is answered by the one entry of
        #: the risks list that says so, not by the whole list.
        _opening(out, lead, shape, question)
        _quotes(out, [lead], terms)
        out.cite(view)
        return
    prose = sorted(_with_context(out, [s for s in same if s.kind == "prose" or s.kind.startswith("picture")]), key=lambda s: s.order)
    items = [s for s in same if s.kind in ("item", "task")]
    if items:
        #: One ticked item of four reads as the whole list: a list is shown
        #: whole, in its order, with its ticks.
        items = [s for s in view.sentences if s.kind in ("item", "task")][:8]
    if not prose:
        _list_block(out, view, items, terms, "opening")
        return
    if prose[0].kind.startswith("picture") and len(prose) == 1:
        _quotes(out, prose, terms)
    else:
        _opening(out, lead if lead in prose else prose[0], shape, question)
        _quotes(out, prose, terms)
        out.cite(view)
    if items and shape != "when" and not out.brief:
        out.t("para")
        _list_block(out, view, items, terms, "continued")


def _relation(out: _Answer, meaning: _Meaning, s: Sentence, before: list[Sentence], lead: Sentence) -> str:
    """How a note's sentence relates to what the answer already said: "later"
    for the same subject in a newer note than the lead's, "also" for the same
    topic, "separately" for another one."""
    #: On the question's subject is "also" whatever else it says: a second
    #: note about the beta testers is more about them, not a change of topic.
    close = any(meaning.same_topic(s, b) for b in before)
    on_topic = close or bool(meaning.subject & set(s.words))
    view, lead_view = out.views[s.note_id], out.views[lead.note_id]
    #: "Later" only for a newer note on the same thread as what was said, not
    #: merely the same subject: "41 testers active" then, weeks on, "Beta
    #: testers did not know Harbor works offline" is not a later chapter.
    if close and view.written and lead_view.written and view.written > lead_view.written:
        return "later"
    return "also" if on_topic else "separately"


def _clusters(meaning: _Meaning, units: list[list[Sentence]]) -> list[list[list[Sentence]]]:
    """Notes' sentences grouped by topic, a group's order its best note's:
    each group one paragraph, so the answer moves from one thread to the next
    rather than back and forth. The notes that say the question's subject in
    their own words are one group, the first."""
    groups: list[list[list[Sentence]]] = []
    for unit in units:
        on_subject = any(meaning.subject & set(s.words) for s in unit)
        home = next(
            (
                g
                for g in groups
                if any(meaning.same_topic(a, b) for other in g for a in unit for b in other)
                or (on_subject and any(meaning.subject & set(s.words) for other in g for s in other))
            ),
            None,
        )
        if home is None:
            groups.append([unit])
        else:
            home.append(unit)
    return groups


def _by_note(sentences: list[Sentence]) -> list[int]:
    """The notes the sentences come from, in the order they first appear."""
    return list(dict.fromkeys(s.note_id for s in sentences))


def _others(out: _Answer, meaning: _Meaning, lead: Sentence, rest: list[Sentence], terms: list[str], question: str) -> None:
    """The other notes, one sentence group each, as prose: each joined to
    what came before by how it relates to it (also, later, separately), each
    topic its own paragraph. Prose only: a list item quoted inside a sentence
    loses the list that gave it its meaning."""
    rest = _with_context(out, [s for s in rest if s.kind == "prose" or s.kind.startswith("picture")])
    if not rest:
        return
    units = [sorted((s for s in rest if s.note_id == i), key=lambda s: s.order) for i in _by_note(rest)]
    said = [s for s in out.views[lead.note_id].sentences if s.key in out.cited]
    used: set[str] = set()
    for group in _clusters(meaning, units):
        for g, unit in enumerate(group):
            #: Two notes to a paragraph at most: a topic's paragraph that runs
            #: on through five notes reads as a wall.
            out.t("space" if g % 2 else "para")
            view = out.views[unit[0].note_id]
            relation = _relation(out, meaning, unit[0], said or [lead], lead)
            _other(out, unit, relation, used, terms, f"{question}:{view.id}", view.written)
            out.cite(view)
            said.extend(unit)


def _other(out: _Answer, unit: list[Sentence], relation: str, used: set[str], terms: list[str], salt: str, written: date | None) -> None:
    """One other note's sentences, after the joiner its relation earns, if
    any; `used` holds the joiners already said: never the same joining
    words twice in one answer."""
    view = out.views[unit[0].note_id]
    #: A list is its note's: "Your Reading list note lists A, B and C", never a connector in front of
    #: its entries lower-cased ("Over in another note, the Dispossessed, Middlemarch") (R3-14).
    if len(unit) >= 2 and view.titled and all(s.kind == "item" for s in unit):
        _list_lead(out, view, "opening")
        _list_sentence(out, unit, terms)
        return
    if unit[0].kind.startswith("picture") and len(unit) == 1:
        #: A picture's reading names its note itself ("The picture
        #: in **Sketches** shows ..."): no joiner before it.
        _quotes(out, unit, terms)
        return
    if relation == "later":
        #: "Later, on" once, "And on" once, then the sentence alone:
        #: newer notes are not in date order among themselves here,
        #: so "Then on" (which says "after that") is never used.
        joiner = next((k for k in ("later_on", "and_on") if k not in used), "")
    else:
        joiner = _pick(salt, "join", [o for o in _joiners(relation, unit[0]) if o not in used] or [""])
    if not joiner:
        _quotes(out, unit, terms)
        return
    used.add(joiner)
    _joined(out, [joiner], unit, terms, written if relation == "later" else None)


def _joiners(relation: str, first: Sentence) -> list[str]:
    """The joiners a note "also" or "separately" related may take.

    The same subject mostly needs no joiner: the sentence and its citation
    are enough, and a pile of "also" is what the owner read as a template
    (INBOX 741). A joiner for the same subject only where the quote can
    follow it after a comma: "On top of that: Subject: ..." is two colons
    and no sentence."""
    if relation != "also":
        return ["separately", "elsewhere", "another_note"]
    return ["", "and_join", "on_top"] if _lowered(first) else [""]


#: A sentence that names its own date ("on 3 October", "11 November"), which the day it was written must not stand in front of.
_OWN_DATE = lazy_compile(
    r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b"
    r"|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}\b", re.I)


def _timeline(out: _Answer, sentences: list[Sentence], terms: list[str]) -> None:
    """A "when" question's other notes, as bullets in the order they were
    written: a timeline is a list, and reads as one."""
    sentences = _with_context(out, [s for s in sentences if s.kind != "task"])
    if not sentences:
        return
    order = _by_note(sentences)
    order.sort(key=lambda note_id: out.views[note_id].written or date.min)
    out.t("para", "timeline")
    for note_id in order:
        view = out.views[note_id]
        out.t("line", "bullet")
        mine = sorted((s for s in sentences if s.note_id == note_id), key=lambda s: s.order)
        # "today: Went to the dentist on 3 October" puts the write day before an event with its own (R3-18).
        dated = any(_OWN_DATE.search(s.text) for s in mine)
        if view.written and not dated:
            out.m(out.day(view.written)).t("colon")
        _quotes(out, mine, terms)
        if view.titled or not view.written or dated:
            out.cite(view)


def _earlier(out: _Answer, sentences: list[Sentence], terms: list[str]) -> None:
    """A "latest" question's older notes, newest first, as prose that walks
    back: "Before that, on 12 September, three workstreams ... [**Q4 roadmap**]".
    Every joiner faces back: `then_on` ("Soon after, on 29 August" under a 12
    September note) read as forward in time, which the blind panel marked."""
    sentences = _with_context(out, [s for s in sentences if s.kind == "prose" or s.kind.startswith("picture")])
    order = _by_note(sentences)
    order.sort(key=lambda note_id: out.views[note_id].written or date.min, reverse=True)
    for i, note_id in enumerate(order):
        view = out.views[note_id]
        out.t("para")
        unit = sorted((s for s in sentences if s.note_id == note_id), key=lambda s: s.order)
        if view.written:
            _joined(out, [("before_that", "earlier_on", "earlier_on")[i] if i < 3 else "and_on"], unit, terms, view.written)
        else:
            _quotes(out, unit, terms)
        out.cite(view)


_DAYISH = lazy_compile(r"\d+|(?:mon|tues?|wednes|thurs?|fri|satur|sun)(?:day)?|(?:jan|febr?|mar|apr|may|jun|jul|aug|sept?|oct|nov|dec)[a-z]*", re.I)


def _other_subjects(views: dict, a: Sentence, b: Sentence) -> bool:
    """Whether two notes are titled for different things ("Tokyo trip" and "Lisbon trip"): each title has a
    word the other lacks. Their figures differ because the notes are about different things (R3-24)."""
    left, right = (getattr(views.get(s.note_id), "title_words", None) for s in (a, b))
    if not (left and right):
        return False
    #: "Monday" and "Friday" name days of one subject, not two subjects.
    return bool({w for w in left - right if not _DAYISH.fullmatch(w)} and {w for w in right - left if not _DAYISH.fullmatch(w)})


def _disagreement(chosen: list[Sentence], views: dict | None = None) -> tuple[Sentence, Sentence] | None:
    for i, a in enumerate(chosen):
        for b in chosen[i + 1:]:
            if disagree(a, b) and not _other_subjects(views or {}, a, b):
                return a, b
    return None


def _disagreements(out: _Answer, pair: tuple[Sentence, Sentence], lead: Sentence, terms: list[str]) -> None:
    """Two sentences that may disagree, said as a "but": the lead's rival
    straight after it, or both, the older first, at the end."""
    a, b = sorted(pair, key=lambda s: out.views[s.note_id].written or date.min)
    days = (out.views[a.note_id].written, out.views[b.note_id].written)
    newer = bool(days[0] and days[1] and days[1] > days[0])
    out.t("para")
    if lead.note_id in (a.note_id, b.note_id):
        #: One side is the lead's own note, already quoted above: only the
        #: other side is said, as the "but" to it.
        other = b if a.note_id == lead.note_id else a
        view = out.views[other.note_id]
        _joined(out, [("but_newer" if other is b else "but_older") if newer else "but_other"], [other], terms)
        out.cite(view, again=True)
        out.t("disagree_check")
        return
    out.t("disagree_lead")
    _quotes(out, [a], terms)
    out.cite(out.views[a.note_id], again=True)
    out.t("space")
    _joined(out, ["but_newer" if newer else "but_other"], [b], terms)
    out.cite(out.views[b.note_id], again=True)


def _own_notes(own_stems: set[str], other_stems: set[str], views: list[NoteView]) -> list[NoteView]:
    """The notes a side names by title. A title that holds every word of the
    side is the note named: "running log" is the Running log, not also the
    Running plan that shares "running" (2026-10-30 sweep)."""
    mine = own_stems - other_stems
    titled = [(v, {_stem(w) for w in v.title_words}) for v in views]
    whole = [v for v, words in titled if len(own_stems) > 1 and own_stems <= words]
    #: A title that is the side's words and no more is the note, though the
    #: other side's words take them all ("Gym" against "Gym plan").
    exact = [v for v, words in titled if words == own_stems]
    return whole or exact or [v for v, words in titled if mine & words]


def _kinds(notes: list[NoteView], side: set[str]) -> set[str]:
    return {_stem(w) for v in notes for w in v.title_words} - side


def _parallel(mine: list[NoteView], side: set[str], theirs: list[NoteView], other: set[str]) -> list[NoteView]:
    """A side's notes of the same kind as the other side's: "Lisbon vs Tokyo"
    is the Lisbon trip against the Tokyo trip, not the Lisbon packing list
    (audit 1030 Z58). All of them when none is."""
    kinds = _kinds(theirs, other)
    same = [v for v in mine if _kinds([v], side) & kinds]
    return same or mine


def _opens_at(view: NoteView, side: set[str]) -> int:
    """Where in a note's name a side's words first appear (99: nowhere)."""
    return next((i for i, w in enumerate(_words(view.title)) if _stem(w) in side), 99)


def _opening_wins(own: list[list[NoteView]], stems: list[set[str]]) -> list[list[NoteView]]:
    """A note two sides both name goes to the side its name opens with:
    "Study plan for November: revise biology on Monday" is the study plan,
    though "biology" is in its name too (audit 1028 E16). A tie keeps both.
    A note titled exactly for one side goes to it alone: "Gym and Gym plan"
    is the Gym note against the Gym plan note (round 1107 D1)."""
    return _by_opening(_by_exact_title(own, stems), stems)


def _by_exact_title(own: list[list[NoteView]], stems: list[set[str]]) -> list[list[NoteView]]:
    for view in {id(v): v for mine in own for v in mine}.values():
        title = {_stem(w) for w in view.title_words}
        exact = [i for i, side in enumerate(stems) if side == title]
        if len(exact) == 1:
            own = [[v for v in mine if v is not view or i == exact[0]] for i, mine in enumerate(own)]
    return own


def _by_opening(own: list[list[NoteView]], stems: list[set[str]]) -> list[list[NoteView]]:
    for view in {id(v): v for mine in own for v in mine}.values():
        at = {i: _opens_at(view, stems[i]) for i, mine in enumerate(own) if any(v is view for v in mine)}
        best = min(at.values(), default=99)
        if len(at) > 1 and list(at.values()).count(best) == 1:
            own = [[v for v in mine if v is not view or at.get(i, best) == best] for i, mine in enumerate(own)]
    return own


def _sides_own(stems: list[set[str]], views: list[NoteView]) -> list[list[NoteView]]:
    """The notes named for each side, of like kind; none when two sides
    claim the same note."""
    n = len(stems)
    others = [set().union(*(st for j, st in enumerate(stems) if j != i)) for i in range(n)]
    own = _opening_wins([_own_notes(stems[i], others[i], views) for i in range(n)], stems)
    ids = [set(map(id, mine)) for mine in own]
    if any(ids[i] & ids[j] for i in range(n) for j in range(i)):
        return [[] for _ in stems]
    return [_parallel(own[i], stems[i], [v for j, o in enumerate(own) if j != i for v in o], others[i]) for i in range(n)]


def _side_picks(sides: tuple[str, ...], views: list[NoteView], meaning_for):  # noqa: ANN001, ANN202
    """Each side's sentences as (terms, stems, own notes, picks); a note named
    for a side belongs to it even when its sentences never repeat the name
    ("Trip to Lisbon": "Flights booked for 3 December"), and a sentence in the
    other sides' notes that mentions this side is still theirs."""
    terms = [subject_terms(label) for label in sides]
    stems = [{_stem(t) for t in ts} for ts in terms]
    own = _sides_own(stems, views)
    picks = [select("compare", terms[i], own[i] or views, limit=6, meaning=meaning_for(terms[i])) for i in range(len(sides))]
    #: A note the person named is read from its top, not by which of its
    #: sentences repeat the name.
    picks = [[s for v in own[i] for s in v.sentences[:3]] or picks[i] for i in range(len(sides))]
    return terms, stems, own, picks


def _cased(out: _Answer, label: str) -> str:
    """A lower-case name the notes write with a capital is said as they write it ("tom" is "Tom")."""
    if not label.islower():
        return label
    for view in out.views.values():
        hit = re.search(rf"\b{re.escape(label)}\b", str(view.note.get("content") or ""), re.I)
        if hit and hit.group(0)[:1].isupper():
            return hit.group(0)
    return label


def _only_lead(out: _Answer, sides: tuple[str, ...], counts: list[int]) -> None:
    """One side with nothing is said once, not as "no mention Tokyo" beside the other (R3-14)."""
    found = [label for label, n in zip(sides, counts) if n]
    out.t("only_lead")
    for i, label in enumerate(found):
        if i:
            out.t("and")
        out.asked(label)
    out.t("only_appear" if len(found) == 1 else "only_appear_many")
    for i, label in enumerate(label for label, n in zip(sides, counts) if not n):
        if i:
            out.t("and")
        out.asked(label)


def _capital(word: str) -> str:
    return word[:1].upper() + word[1:]


def _compare_lead(out: _Answer, sides: tuple[str, ...], counts: list[int]) -> None:
    sides = tuple(_cased(out, label) for label in sides)
    if 0 in counts and any(counts):
        _only_lead(out, sides, counts)
        return
    #: No "Of the notes found," before it: the counts are the opener (L205, D20). Said twice running the same way,
    #: the second opens on the first name instead ("Tokyo comes up in two notes and Lisbon in three notes").
    again = bool(re.match(r"\w+ notes? mention", out.previous or ""))
    #: Asked again later in the chat: a varied lead before the counts, so twenty turns do not open one way.
    led = out.later_turn() and not again
    if led:
        out.t("compare_lead")
    for i, (label, n) in enumerate(zip(sides, counts)):
        if i:
            out.t("and")
        if again:
            out.asked(label).t("side_in" if i else "comes_up_in").m(out.count(n)).t("side_note" if n == 1 else "side_notes")
            continue
        out.m(_capital(out.count(n)) if not (i or led) else out.count(n))
        out.t(*((("side_note" if n == 1 else "side_notes"),) if not i else ())).t("mentions_one" if n == 1 else "mention_many").asked(label)


_LENGTH_ASK = lazy_compile(r"\b(?:longer|shorter|bigger|smaller)\b", re.I)


def _length_lead(out: _Answer, question: str, own: list[list[NoteView]]) -> bool:
    """"which is longer, A or B" with one note a side: both lengths first."""
    asked = _LENGTH_ASK.search(question or "")
    if not asked or len(own) != 2 or len(own[0]) != 1 or len(own[1]) != 1:
        return False
    sized = sorted(((composer_frame.note_words(v.note.get("content")), v) for v in (own[0][0], own[1][0])), key=lambda p: -p[0])
    if sized[0][0] == sized[1][0]:
        return False
    shorter = asked.group(0).lower() in ("shorter", "smaller")
    (n, first), (m, second) = sized[::-1] if shorter else sized
    out.name(first, cap=True).t("is_shorter" if shorter else "is_longer").m(str(n)).t("words_against").m(str(m)).t("words_in").name(second)
    return True


def _versus_answer(out: _Answer, versus) -> None:  # noqa: ANN001
    """The lead of `composer_versus.which_one`, then the line each figure or
    day was read from."""
    composer_versus.write(out, versus)
    out.t("stop")
    for i, row in enumerate(versus.rows[:4]):
        at = row.at
        view = row.view
        s = next((x for x in view.sentences if at is not None and x.start <= at < x.end), None) or (view.sentences[0] if view.sentences else None)
        if s is not None:
            out.t("para" if i == 0 else "line").item(s, []).cite(view, again=True)


def _versus_lead(out: _Answer, question: str, own: list[list[NoteView]], sides: tuple[str, ...] = ()) -> bool:
    """"which is cheaper, A or B": both figures (or days) first."""
    versus = composer_versus.two(question, own, out.today)
    if versus:
        composer_versus.write(out, versus)
        return True
    #: One note that has a line for each side ("Japan: £2,400 ... Portugal: £1,100"), R9-10.
    return composer_versus.named_two(out, question, sides, list(out.views.values()))


def _said_once(only: list[list], stems: list[set[str]]) -> list[list]:
    """A line picked for two sides is said under the side it names, with what
    speaks of both, and not at all when it names neither (audit 1028 E16)."""
    def twice(s) -> bool:  # noqa: ANN001
        return sum(any(x is s for x in side) for side in only) > 1

    def names(s) -> list[int]:  # noqa: ANN001
        return [j for j in range(len(stems)) if stems[j] & set(s.words)]

    return [[s for s in side if not twice(s) or names(s) == [i]] for i, side in enumerate(only)]


def _compare_shares(stems, own, picks) -> tuple[list, list]:  # noqa: ANN001
    """What is said of each side only, then what speaks of two or more."""
    n = len(picks)
    others = [set().union(*(stems[j] for j in range(n) if j != i)) for i in range(n)]
    only = [[s for s in picks[i] if own[i] or not (others[i] & set(s.words))][:3] for i in range(n)]
    only = _said_once(only, stems)
    #: What speaks of two sides is not a line already said under a side.
    said = {id(s) for side in only for s in side}
    both = [s for s in picks[0] if others[0] & set(s.words) and id(s) not in said][:2] if n == 2 else _shared(picks, others, said)
    return only, both


def _compare_grid(out: _Answer, sides: tuple[str, ...], own: list[list[NoteView]]) -> None:
    grid = composer_versus.table([heading_name(label) for label in sides], own, out.today)
    if grid:
        out.t("para")
        out.parts.append(("template", grid))


def _compare(out: _Answer, sides: tuple[str, ...], views: list[NoteView], meaning_for, question: str = "") -> bool:  # noqa: ANN001
    """A line that counts each side, each side its own short list, then what
    speaks of two or more of them."""
    terms, stems, own, picks = _side_picks(sides, views, meaning_for)
    only, both = _compare_shares(stems, own, picks)
    if not any(only):
        return False
    if not _length_lead(out, question, own) and not _versus_lead(out, question, own, sides):
        #: Every found note that names a side, not the lines shown under it:
        #: a note about both is a mention of each (the blind panel's Q6).
        _compare_lead(out, sides, [sum(1 for v in views if any(_holds(t, v.words | v.title_words) for t in stems[i])) for i in range(len(sides))])
    #: The lead names only what follows (probe P15): no "Here is what
    #: each says." before the headings that say it.
    out.t("stop")
    for label, side, side_terms in zip(sides, only, terms):
        if side or not any(only):
            _compare_side(out, label, side, side_terms)
    _compare_grid(out, sides, own)
    if both:
        out.t("para", "bold", "both", "bold")
        for s in both:
            out.t("line").item(s, [t for ts in terms for t in ts]).cite(out.views[s.note_id], again=True)
    return True


def _shared(picks: list[list], others: list[set[str]], said: set[int]) -> list:
    """Sentences, under three or more sides, that mention another side than
    the one they were picked for."""
    seen: list = []
    for i, side in enumerate(picks):
        seen += [s for s in side if others[i] & set(s.words) and id(s) not in said and s not in seen]
    return seen[:2]


_LEADING_ARTICLE = lazy_compile(r"^(?:the|a|an|my|our|your)\s+(?=\S)", re.I)


def heading_name(label: str) -> str:
    """A side's name where a sentence or a heading starts with it: "the Lisbon
    trip" is "Lisbon trip" there (mid-sentence it keeps its "the")."""
    return _LEADING_ARTICLE.sub("", label.strip(), count=1)


def _compare_side(out: _Answer, label: str, side: list, side_terms) -> None:  # noqa: ANN001
    """One side's heading and its lines."""
    name = heading_name(label)
    #: Starts the line it heads, so it takes a capital as the note's title does (audit 1031 C24).
    out.t("para", "bold").asked(name[:1].upper() + name[1:]).t("bold")
    #: The lead said each side's count ("one mentions Lisbon and two
    #: mention Porto"); the heading does not say it again (decision 52).
    if not side:
        out.t("line").t("side_none")
        return
    previous = None
    for s in side:
        out.t("line").item(s, side_terms)
        if s.note_id != previous:
            #: The note is named where its lines begin, not after each of them (bt-compcomp-1109 item 6).
            out.cite(out.views[s.note_id], again=True)
        previous = s.note_id


#: "briefly", "in short", "quick": the lead note alone. "in detail",
#: "everything": more points than an ordinary answer (INBOX 741, length
#: fitted to the question).
_BRIEF = lazy_compile(r"\b(briefly|in brief|in short|short answer|quick(?:ly)?|tl;?dr|in a (?:word|sentence|line)|just tell me)\b", re.I)


_FULL = lazy_compile(r"\b(in detail|in depth|more detail|detailed|thorough(?:ly)?|the full|everything|all (?:the|of the))\b", re.I)


FULL_POINTS = 9


def length_wish(question: str) -> str:
    """"brief", "full" or "": how long the person asked the answer to be."""
    text = question or ""
    if _BRIEF.search(text):
        return "brief"
    if _FULL.search(text):
        return "full"
    return ""


#: A broad question names at most this many notes, one sentence each.
BROAD_NOTES = 5



def _asked_span(question: str, terms: list[str]) -> str:
    """The question's subject as typed, from its first subject word to its
    last ("half marathon training plan"), or "" when they are not in order."""
    lower = (question or "").lower()
    if not terms:
        return ""
    start = lower.find(terms[0])
    end = lower.rfind(terms[-1])
    if start < 0 or end < start:
        return ""
    #: The span may hold the question's own verb ("book am I reading"); the chips refuse
    #: such a topic in `composer_digest._topic_chips` (R3-36, D19), while a follow-on
    #: ("what about the garden?") swaps the whole span, so it must stay here.
    return question[start : end + len(terms[-1])]


def _insights_for(question: str, terms: list[str], views: list[NoteView], today: date) -> list:
    from tessellate.ai import insights

    subject = _asked_span(question, terms)
    #: The route's notes carry their day as `written` words, not an ISO
    #: `created_at`, which is what the rules read: the day the composer
    #: already read is handed over, or no insight ever fired in Chat (found
    #: by Brief 67's sweep; the evals' notes have `created_at`).
    notes = [{**v.note, "created_at": v.written.isoformat()} if v.written else v.note for v in views]
    found = insights.for_subject(subject, notes, today, question) if subject else []
    known = _LEARNED.get()
    return [i for i in found if insights.key(i) not in known.dismissed] if known else found


def _said_insight(out: _Answer, insight) -> None:  # noqa: ANN001
    """Note an insight line the answer says, for its Confirm and Not right."""
    from tessellate.ai import insights

    out.insights = [*getattr(out, "insights", []), insights.as_row(insight, _LEARNED.get())]


def _confirmed_lead(out: _Answer, question: str, terms: list[str]) -> bool:
    """A question about a subject the person confirmed an insight on opens
    with their word, as a fact (decision 60): "Golf is a hobby of yours,
    as you told me on 10 October." False when none matches."""
    known = _LEARNED.get()
    if not known or not known.confirmed:
        return False
    from tessellate.ai import insights

    asked = {insights._stems(t) for t in [_asked_span(question, terms), *terms] if t}
    for subject, line in known.subjects().items():
        if subject in asked:
            out.parts.append(("confirmed", line))
            out.t("para")
            out.confirmed_said = True
            return True
    return False


def _insight_close(out: _Answer, question: str, terms: list[str], views: list[NoteView]) -> None:
    """A broad answer closes with what the notes measure about its subject
    (decision 32), when a rule fires: one line, marked measured."""
    found = _insights_for(question, terms, views, out.today)
    if not found or getattr(out, "confirmed_said", False):
        return
    insight = found[0]
    _said_insight(out, insight)
    if insight.rule == "recurrence" and getattr(out, "mentioned", None):
        #: The lead already said how many notes and from when (decision 52's
        #: quantity maxim: one fact once), so the close says only what is new:
        #: how many were after work, and the hedge.
        from tessellate.ai import insights

        if closing := insights.after_lead(insight):
            out.t("para").m(closing)
        return
    out.t("para").m(insight.text)


def _insight_lead(out: _Answer, question: str, terms: list[str], views: list[NoteView]) -> bool:
    """"Any patterns in my golf notes": the measured line first, then the
    sentences it rests on (decision 31's insight schema). False when no rule
    fires, and the answer is the subject's as usual."""
    found = _insights_for(question, terms, views, out.today)
    if not found:
        return False
    _said_insight(out, found[0])
    out.m(found[0].text).t("para")
    return True


def _mentions(out: _Answer, question: str, terms: list[str], views: list[NoteView]) -> bool:
    """"At least four of your notes mention “sourdough”, from 7 September to
    3 October." "At least": the notes found are some of the notebook, and the
    count is of those. False when fewer than two do, which is not news."""
    stems = {_stem(t) for t in terms}
    subject = _asked_span(question, terms)
    if not stems or not subject:
        return False
    holding = [v for v in views if stems <= (v.words | v.title_words | v.filed_words) and not v.note.get("connected")]
    if len(holding) < 2:
        return False
    out.mentioned = len(holding)
    out.t("mention_lead").m(out.count(len(holding))).t("mention_mid", "open_quote")
    out.asked(subject).t("close_quote")
    _span(out, holding)
    out.t("stop", "space")
    return True


def _summary(out: _Answer, question: str, terms: list[str], firsts: list[Sentence]) -> None:
    """"I found two notes on “running”." A broad answer that quotes several
    notes, none holding every word asked, says what it is about and how many
    notes before the first quote (INBOX 729), so the quotes read as one
    answer rather than as sentences joined by "Also"."""
    #: Only the words some note holds are the lead's subject ("plumber 9988",
    #: when no note holds "9988", was "notes that bear on plumber 9988" and then,
    #: at the close, "these notes do not talk about 9988"; audit 1031 N36).
    found: set[str] = set()
    for view in out.views.values():
        found |= view.words | view.title_words | view.filed_words
    held = [t for t in terms if _stem(t) in found or t in found]
    subject = _asked_span(question, held or terms)
    count = len({s.note_id for s in firsts})
    if count < 2 or not subject:
        return
    out.t("summary_lead").m(out.count(count)).t("summary_mid", "open_quote")
    out.asked(subject).t("close_quote", "stop", "space")


def _broad_pool(out: _Answer, chosen: list[Sentence], terms: list[str]) -> list[Sentence]:
    """One sentence from each note a broad question is about: the chosen ones,
    and for a note that holds the subject in its name or its tags but whose
    sentences scored under the floor, its best-scored sentence, so "at least
    three of your notes" is followed by three notes."""
    stems = {_stem(t) for t in terms}
    pool = list(chosen)
    have = {s.note_id for s in pool}
    for view in sorted(out.views.values(), key=lambda v: v.rank):
        if len(pool) >= BROAD_NOTES:
            break
        if view.id in have or view.note.get("connected") or not stems or not stems <= (view.words | view.title_words | view.filed_words):
            continue
        prose = [s for s in view.sentences if s.kind == "prose" and not _was_said(s, out.said)]
        if prose:
            best = max(prose, key=lambda s: (s.score, -s.order))
            pool.append(best)
            have.add(view.id)
    return pool


def _topic_extras(out: _Answer, pool: list[Sentence], stems: set[str]) -> list[Sentence]:
    """A note whose name or tags are the subject is the note about it, so a
    broad question quotes its next-best sentence as well (INBOX 813, 2700); a
    note that only mentions the subject in passing is quoted once. The extra
    is a sentence of that note that is not already in the pool and not said."""
    extras: list[Sentence] = []
    for first in pool:
        view = out.views[first.note_id]
        if not stems or not stems <= (view.title_words | view.filed_words) or view.note.get("connected"):
            continue
        more = [s for s in view.sentences if s.kind == "prose" and s.key != first.key and s.score > 0 and not _was_said(s, out.said)]
        if more:
            extras.append(max(more, key=lambda s: (s.score, -s.order)))
    return extras


def _status_body(out: _Answer, chosen: list[Sentence], terms: list[str], question: str, skip: set[tuple]) -> Sentence:
    ordered = sorted(chosen, key=lambda s: (out.views[s.note_id].written or date.min, s.score), reverse=True)
    lead = ordered[0]
    view = out.views[lead.note_id]
    same = sorted(_with_context(out, [s for s in ordered if s.note_id == lead.note_id and s.kind == "prose"]), key=lambda s: s.order)
    if view.written:
        key = _pick(question, "lead", _unlike_before(out, ["latest_a", "latest_b", "latest_c"]))
        _joined(out, [key], same or [lead], terms, view.written, colon=key == "latest_b")
    else:
        out.t("latest_undated")
        _quotes(out, same or [lead], terms)
    out.cite(view)
    _earlier(out, [s for s in ordered if s.note_id != lead.note_id and s.key not in skip], terms)
    return lead


def _list_body(
    out: _Answer, chosen: list[Sentence], terms: list[str], question: str, meaning: _Meaning, skip: set[tuple]
) -> Sentence | None:
    """A "which" or "list" question is best answered by a list the person
    wrote: the best-placed chosen note that holds one leads. None when no
    chosen note holds one."""
    listed = [s for s in chosen if sum(1 for u in out.views[s.note_id].sentences if u.kind in ("item", "task")) >= 2]
    if not listed:
        return None
    lead = listed[0]
    view = out.views[lead.note_id]
    items = [s for s in view.sentences if s.kind in ("item", "task")][:8]
    _list_block(out, view, items, terms, "opening")
    _others(out, meaning, lead, [s for s in chosen if s.note_id != lead.note_id and s.key not in skip], terms, question)
    return lead


def _broad_body(
    out: _Answer, shape: str, chosen: list[Sentence], terms: list[str], question: str, meaning: _Meaning, skip: set[tuple]
) -> Sentence:
    firsts = _broad_pool(out, chosen, terms)
    rank = centrality(firsts, meaning)
    stems = {_stem(t) for t in terms}
    #: The note named for the subject leads ("Sourdough log" for
    #: sourdough); among the rest, the sentence the others lean towards.
    lead = max(
        firsts,
        key=lambda s: (bool(stems) and stems <= out.views[s.note_id].title_words, rank.get(s.key, 0.0) * s.score, -s.rank),
    )
    if not _mentions(out, question, terms, list(out.views.values())):
        _summary(out, question, terms, firsts)
    more = _topic_extras(out, firsts, stems)
    _lead_block(out, shape, lead, [lead] + [s for s in more if s.note_id == lead.note_id], terms, question)
    _others(out, meaning, lead, [s for s in firsts + more if s.note_id != lead.note_id and s.key not in skip], terms, question)
    return lead


def _fact_rest(out: _Answer, lead: Sentence, rest: list[Sentence], shape: str) -> list[Sentence]:
    #: A lead that holds every word asked and what the shape looks for
    #: (a date for a "when") has answered: one more note at most, so a
    #: one-fact question gets a one-fact answer.
    #: A "when" keeps its timeline of the other dated mentions.
    strong = shape != "when" and _cue(shape, lead.text) > 0 and out.subject and all(
        _holds(t, set(lead.words) | out.views[lead.note_id].title_words) for t in out.subject
    )
    keep = list(dict.fromkeys(s.note_id for s in rest))[: 1 if strong else FACT_OTHERS]
    return [s for s in rest if s.note_id in keep]


def _body(
    out: _Answer,
    shape: str,
    chosen: list[Sentence],
    terms: list[str],
    question: str,
    meaning: _Meaning,
    broad: bool,
    skip: set[tuple],
) -> Sentence:
    """The lead and the points under it, laid out by the question's shape.
    Returns the lead sentence. `skip` are the sentences a "may disagree"
    paragraph says at the end, left out of the body so nothing is said twice."""
    if shape == "status":
        return _status_body(out, chosen, terms, question, skip)
    if shape == "list":
        listed = _list_body(out, chosen, terms, question, meaning, skip)
        if listed is not None:
            return listed
    if broad:
        return _broad_body(out, shape, chosen, terms, question, meaning, skip)
    lead = chosen[0]
    _lead_block(out, shape, lead, chosen, terms, question)
    rest = [s for s in chosen if s.note_id != lead.note_id and s.key not in skip]
    if shape in FACT_SHAPES:
        rest = _fact_rest(out, lead, rest, shape)
    if shape == "when" and rest:
        _timeline(out, rest, terms)
        return lead
    _others(out, meaning, lead, rest, terms, question)
    return lead


#: "what is still open on the harbor launch", "whats left to do for X",
#: "what do I still need to do for X" (ledger row 444).
_STILL_OPEN = lazy_compile(
    r"^(?:what(?:'s|s| is| are)?|which)(?: things?| items?| tasks?)?(?: is| are)?(?: still)? "
    r"(?:open|left(?: to [a-z]+)?|outstanding|remaining|not done|undone|unticked|unchecked|to do|todo|pending)(?: still)? "
    r"(?:on|for|in|from|with|about) (?P<a>.+)$"
    #: "what do I still need to read for history" (E11): any verb, not only "do".
    r"|^what (?:else )?(?:do|have|must|should) i (?:still |also |got )?(?:have |need |got |want )?(?:left )?to (?:[a-z']+ ){1,3}?(?:on|for|in|about|from|before) (?P<b>.+)$",
    re.I,
)


def _notes_named_by(views: list[NoteView], wanted: set[str], names: set[str] = frozenset()) -> list[NoteView]:
    """The notes a "still open" question names, best-ranked first."""

    def titled(v: NoteView) -> set[str]:
        return {_stem(w) for w in v.title_words} | {_stem(w) for w in v.filed_words}

    ranked = sorted(views, key=lambda v: v.rank)
    #: Named by its filing or heading ("for uni", "for history"): every word
    #: of the subject. One shared word ("packing list" for the Tokyo list) is
    #: a near note, not the one asked about (audit 1029 C33).
    named = [v for v in ranked if wanted <= titled(v) | {_stem(w) for w in v.words}]
    if not names or any(s.kind == "task" for v in named for s in v.sentences):
        return named
    #: Nothing to tick there: then the notes titled or filed with every name
    #: the subject carries. "before the Lisbon trip" is the Lisbon packing
    #: list when the trip note holds no checklist (audit 1029 C33); the name
    #: is what keeps the Tokyo list out.
    return named + [v for v in ranked if names <= titled(v) and v not in named]


def _say_open_notes(out: _Answer, named: list[NoteView], subject: str, wanted: set[str]) -> bool:
    """The open items of up to three named notes; False when none was named."""
    open_in = [(v, [s for s in v.sentences if s.kind == "task"]) for v in named]
    open_in = [(v, tasks) for v, tasks in open_in if tasks]
    if not open_in:
        #: Nothing to tick on what was named, or no note named: said, not
        #: answered with another note's checklist (E11: biology answered with
        #: the history sources; audit 1029 C33: Tokyo with the Lisbon list).
        out.t("open_nowhere_a").asked(subject.strip(" ?.")).t("open_nowhere_b")
        return True
    for i, (view, tasks) in enumerate(open_in[:3]):
        if i:
            out.t("para")
        _say_open(out, view, tasks, wanted)
    return True


def _still_open(out: _Answer, question: str, views: list[NoteView]) -> bool:
    """The checklist items not ticked on the note the question names: how
    many of how many, then those items. False when the question is not
    that, or no note found names it with a checklist."""
    asked = question_noise.repair(question_noise.tidy(" ".join((question or "").split())))
    found = _STILL_OPEN.match(asked.rstrip("?."))
    if not found:
        return False
    subject = found.group("a") or found.group("b")
    wanted = {_stem(w) for w in _words(subject)} - {_stem(w) for w in _NOTE_NOUNS}
    if not wanted:
        return False
    names = {_stem(w) for w in re.findall(r"\b[A-Z][\w'-]*", subject) if w != "I"}
    return _say_open_notes(out, _notes_named_by(views, wanted, names & wanted), subject, wanted)


def _say_open(out: _Answer, view: NoteView, tasks: list, wanted: set[str]) -> None:
    """"Two of three items are still open on Harbor launch:", then each."""
    still = [s for s in tasks if not s.done]
    total = len(tasks)
    if not still:
        out.t("open_none_a").name(view).t("open_none_b").m(out.count(total)).t("open_none_c")
        return
    if total == 1:
        out.t("open_single_a").name(view).t("open_single_b")
    elif len(still) == total:
        out.t("open_all_a").m(out.count(total)).t("open_all_b").name(view).t("open_all_c")
    else:
        out.m(out.count(len(still)).capitalize()).t("checklist_of").m(out.count(total))
        out.t("open_one" if len(still) == 1 else "open_some").name(view)
    out.t("end_colon", "para")
    for i, s in enumerate(still):
        if i:
            out.t("line")
        out.item(s, list(wanted))


def _until_note(out: _Answer, question: str, views: list[NoteView], today: date) -> bool:
    """"How many days until the dentist": the day is in a note, so the
    count is from today to the nearest day the note on the subject names
    (ledger row 441, `utilities.until_subject`). False, and nothing said,
    when no note found names the subject with a day."""
    asked = utilities.until_subject(question)
    if not asked:
        return False
    ahead = asked[0] == "future"
    #: A particle is no subject: "the stand up" is not the "Check-up" note.
    wanted = {_stem(w) for w in _words(asked[1]) if len(w) > 2} - {_stem(w) for w in _NOTE_NOUNS}
    #: The note titled as the subject first (note_rank's order), so "the
    #: dentist" is the Dentist note and not a to-do that says "call the dentist".
    from tessellate.ai import note_rank  # at the call: note_rank reads the composer, so a module import closes a cycle

    for view in note_rank.lead_by(sorted(views, key=lambda v: v.rank), asked[1], lambda v: v.note):
        if not wanted or not wanted & {_stem(w) for w in _words(str(view.note.get("content") or ""))}:
            continue
        dated, ahead = _dated_either_way(view, today, asked[0], ahead)
        if not dated:
            continue
        day, at = min(dated, key=lambda d: abs((d[0] - today).days))
        sentence = next((s for s in view.sentences if s.start <= at < s.end), None)
        if sentence is None:
            continue
        _say_until(out, day, today, ahead)
        out.t("until_by_note").q(sentence, list(wanted)).cite(view)
        return True
    return False


def _dated_either_way(view: NoteView, today: date, tense: str, ahead: bool) -> tuple[list[tuple[date, int]], bool]:
    """The days the note names in the tense asked; none there, the other tense, said the way it stands ("until" of a day gone by)."""
    dated = _days_named(view, today, tense)
    if dated:
        return dated, ahead
    return _days_named(view, today, "past" if ahead else "future"), not ahead


def _say_until(out: _Answer, day: date, today: date, ahead: bool) -> None:
    """"Ten days from today, on 21 October", or "That's today"."""
    days = abs((day - today).days)
    if days == 0:
        out.t("until_today")
        return
    unit = "day" if days == 1 else "days"
    #: The day by its date, never "yesterday" after "one day ago".
    out.m(out.count(days).capitalize()).t(f"until_{'ahead' if ahead else 'ago'}_{unit}").m(composer_versus._said_day(day, "day", today))  # noqa: SLF001


def _days_named(view: NoteView, today: date, tense: str) -> list[tuple[date, int]]:
    """The days a note names on the side of today `tense` asks ("future" or
    "past"), each with where it is written."""
    from tessellate.ai import factgraph

    ahead = tense == "future"
    dated = []
    #: The route's notes carry their day as `written` words and no ISO
    #: `created_at`, which the fact graph anchors "Friday" and a bare day and
    #: month on: handed over, as `_insights_for` does (measured 2026-10-18:
    #: "what is due this week" found no day in notes that name three).
    note = {**view.note, "created_at": view.written.isoformat()} if view.written and not view.note.get("created_at") else view.note
    for fact in factgraph.facts(note):
        if fact.kind != "date" or not fact.when or fact.when[2] != "day":
            continue
        day = composer_versus.fact_day(fact, today, tense) if ahead else fact.when[0]
        if ahead and told_as_past(str(note.get("content") or ""), fact.start):
            continue
        if _a_schedule_day(str(note.get("content") or ""), fact):
            continue
        if day >= today if ahead else day <= today:
            dated.append((day, fact.start))
    return dated


def _a_schedule_day(content: str, fact) -> bool:  # noqa: ANN001
    """A weekday of a recurring schedule, said alone, is a habit and not a day that falls due (item 8)."""
    if fact.text.strip().lower() not in _WEEKDAY_WORDS:
        return False
    start = max(content.rfind(m, 0, fact.start) for m in (". ", "! ", "? ", "\n")) + 1
    stops = [i for i in (content.find(m, fact.start) for m in (". ", "! ", "? ", "\n")) if i >= 0]
    return rec.recurring_schedule(content[start: min(stops) if stops else len(content)])


_WEEKDAY_WORDS = frozenset("monday tuesday wednesday thursday friday saturday sunday".split())


def told_as_past(content: str, at: int) -> bool:
    """Whether the sentence of `content` holding `at` tells of something that
    happened (`recognise.told_as_past`, audit 1030 Z26)."""
    start = max(content.rfind(m, 0, at) for m in (". ", "! ", "? ", "\n")) + 1
    stops = [i for i in (content.find(m, at) for m in (". ", "! ", "? ", "\n")) if i >= 0]
    return recognise_questions.told_as_past(content[start: min(stops) if stops else len(content)])


def _newest_lead(out: _Answer, count: int, guessing: bool) -> None:
    """"Your five newest notes" for several, "your newest note" for one, never "your one newest notes" (R3-16)."""
    if count == 1:
        out.t("newest_one_guess" if guessing else "newest_one_lead")
    else:
        out.t("newest_guess" if guessing else "newest_lead").m(out.count(count)).t("newest_mid")


def _newest(out: _Answer, views: list[NoteView], guessing: bool = False) -> None:
    """The newest notes, each by its first sentence, newest first. When the
    question named nothing to look for, the lead says these are a fallback."""
    shown = [v for v in views if v.sentences][:5]
    if not shown:
        return
    _newest_lead(out, len(shown), guessing)
    _span(out, shown)
    out.t("end_colon")
    for view in shown:
        out.t("line", "bullet")
        #: Each line's name opens its note (brief composer item 4: a listing
        #: offers the way to what it lists, as the tools' lists do), a
        #: title-less note by the day it was written.
        linked = view.kind == "note" and isinstance(view.id, int) and view.id > 0 and (view.titled or bool(view.written))
        if linked:
            out.address("[")
        if view.titled:
            out.name(view)
            if linked:
                out.address(f"](#/notes/{view.id})")
            out.dated(view)
        elif view.written:
            #: The note's words are its name, the day a muted second field (R3-15).
            out.term(composer_frame.name_of(view.note), view)
            if linked:
                out.address(f"](#/notes/{view.id})")
            out.dated(view)
        else:
            out.name(view, cap=True)
        out.t("colon")
        #: A picture's note as what it shows and its words; a note's
        #: heading with the sentence after it (INBOX 787).
        _overview_line(out, _overview().best_line(view.sentences, set()), set())


_NOTE_NOUNS = frozenset({"note", "notes", "entry", "entries", "jotting", "jottings"})


def _overview_line(out: _Answer, units: list[Sentence], stems: set[str]) -> None:
    """A note's line: its sentences, each ended; a picture as what it shows,
    then ", which reads" and its words in quotes."""
    terms = sorted(stems)
    if len(units) > 1 and all(s.kind in ("item", "task") for s in units):
        _overview_list(out, units, terms)
        return
    for i, s in enumerate(units):
        if s.kind == "picture_text":
            out.t("ov_reads" if i else "picture_text_lead", "open_quote").q(s, terms).t("close_quote")
            continue
        if i:
            out.t("space")
        followed = i + 1 < len(units) and units[i + 1].kind == "picture_text"
        out.q(s, terms, s.text.rstrip(".") if followed else None)
        if not followed and not _ENDED.search(s.text):
            out.t("stop")
    if units and units[-1].kind == "picture_text":
        out.t("stop")


def _overview_list(out: _Answer, units: list[Sentence], terms: list[str]) -> None:
    """A list note as one sentence: "a list: a habit tracker, ...", its
    entries lowered only when all are written that way, and parted by
    semicolons when not, so no capital follows a comma."""
    out.t("ov_list")
    lower = _sentence_case(units)
    between = "comma" if lower else "semicolon"
    for n, s in enumerate(units):
        if n:
            out.t("and" if n == len(units) - 1 else between)
        text = s.text.rstrip(".")
        out.q(s, terms, decap(text) if lower else text)
    out.t("stop")
