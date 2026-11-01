"""A composed answer with no model in it: the notes' own sentences, shaped.

Asked for directly (INBOX 688, the owner): *"is there a way to do very good
imitations of ai responses but using string concatenation with the app when
the ai isnt available ... it needs to be VERY refined and well worded and
designed ... nice and understandable to read, well structured"*.

**The rule, which is the notebook's integrity and is not traded for fluency.**
Every factual clause of a composed answer is one of two things:

- the person's own words: a sentence or a list item from a note, quoted whole
  or lightly trimmed (a leading "So," or "Also," taken off, the first letter
  raised, a very long sentence cut at a word with an ellipsis), and cited; or
- a value the app measured: how many notes, the day each was written, whether
  a checklist item is ticked, which of the question's words no note found
  contains.

Only the connective tissue between them is written here, and it comes from
`PHRASES`, a closed list that says nothing about the world: "Separately,",
"Later, on", "None of these notes mention ...". No sentence is paraphrased, no half-sentence is joined to
another, and nothing is concluded: a yes/no question gets the closest sentence,
never a yes or a no. `compose` returns the answer as `parts` as well as text,
each tagged with what it is, so the tests hold every clause of every answer to
the notes it came from (`tests/test_composer_688.py`).

**Why this beside `extractive.py` rather than inside it.** The extractive
answer (INBOX 269) quotes the best forty-word window of each note. A window is
not a sentence: it starts and ends mid-thought, swallows the note's heading and
flattens a checklist into one line of dashes (measured on the showcase
notebook, docs/roadmap/archive/agent-remaining/composer688-1006.md). This works in
sentences and list items, reads what kind of question was asked, and lays the
answer out the way a careful reader would: the strongest sentence first, set
apart as a quote and attributed; the rest grouped by note under a measured
line; a timeline for a "when", the newest first for a "latest", two sides for
a "compare"; two notes that may disagree named; and the question's words that
no note found contains, said in one line.

**Read like a person wrote it (INBOX 725, the owner: "I want it soooo good it
is almost like a chat bot").** The rule above does not move; what changed is
how the quotes are strung together, each step measured on the showcase eval
(`tests/_composer_eval.py`) and kept because it moved a number:

- the first line is the answer: the lead sentence itself, its note named
  after it as the citation, once (INBOX 741: never "Your note ... says:",
  never a note named by its first words), a list of short entries said as one sentence ("lists four: A,
  B, C and D"), a checklist with how many are ticked, a broad question
  opened by how many notes mention it ("At least five of your notes mention
  “running”, from 20 August to 21 September");
- the other notes are joined by how they relate to what came before, by
  meaning (`_Meaning`: the embedder's cosine when it is running, shared
  words when not): no joiner or "And" for the same subject, "Later, on"
  for a newer note on the same thread, "Separately" for another topic, "But
  in a newer note" for two that may disagree; no joiner twice in an answer,
  one topic to a paragraph;
- a sentence other notes repeat is said once, with how many say it; a
  broad question's lead is the sentence the others lean towards (TextRank,
  `centrality`), the note named for the subject first;
- lead-ins ("So basically,") come off a quote from a tested list
  (`LEAD_INS`), and a picture's reading is introduced as the picture's;
- two or three next questions are built from what the answer found and did
  not say (`next`), and "tell me more" or "the second one" is read against
  the turn before (`follow_on`).

Pure and deterministic: the same question over the same notes gives the same
answer. The opening is chosen by a hash of the question, so two different
questions in a row do not open with the same words.

**Where the pieces are (audit AR3, gods-1101).** This file is the pipeline:
read the question, plan it, pick the notes' sentences, phrase the answer
(`compose`, `brief`, `split_parts`). The layers it calls were moved out whole
and are re-exported here; each imports only the layers before it in this list,
never this file: `composer_phrases` (the joining words), `composer_ask`
(reading the question), `composer_read` (reading a note), `composer_select`
(choosing what to quote), `composer_answer` (the answer being built).
"""

from __future__ import annotations

import functools
import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from tessellate.ai import act_registry, composer_ack, composer_compose, composer_frame, composer_lines, composer_links, composer_open, composer_parts, composer_replies, composer_tables, composer_tree, composer_versus, grounding, phrasing, question_noise, spelling, utilities
from tessellate.ai import recognise as rec
from tessellate.ai import when as when_words
from tessellate.search import query as query_understanding
from tessellate.ai.composer_phrases import PHRASES, phrase_options  # noqa: F401  (moved; re-exported)
from tessellate.ai.composer_ask import IRREGULAR_PAST, SHAPES, SYNONYM_GROUPS, _ASKING_WORDS, _ASKS_FIRST, _BIN_WORDS, _COMPARE_SIDES, _CONTRACTIONS, _DEFINE, _IF, _KNOWN, _MONTHS, _MONTH_INDEX, _NUMBER_WORDS, _SHAPE_RULES, _TRAILERS, _WEEKDAYS, _WHEN_NOISE, _WRAPPERS, _alternatives, _build_synonyms, _guessing_recent, _holds, _overview, _stem, _stem_plain, _still_recent, _without_command, _words, asks_time, asks_written_when, classify, compare_sides, rephrase, subject_terms, user_now, user_today, what_is  # noqa: F401  (moved; re-exported)
from tessellate.ai.composer_read import LEAD_INS, LEAD_INS_BARE, MAX_QUOTE_CHARS, NoteView, Sentence, _HEADING_LEAD, _ITEM, _LEAD_IN, _MARKS, _NUMBER_CUE, _PICTURES_HEAD, _SPLIT, _SPLIT_HYPHEN, _WHERE_CUE, _cue, _depth, _discourse, _distinct_ids, _heading_text, _picture_groups, _picture_spans, _picture_text_breaks, _short_fact, _title, _unit, _written, plain_words, read_note, source_kind as source_kind  # noqa: F401  (moved; re-exported)
from tessellate.ai.composer_select import KIND_WORDS, MAX_PER_NOTE, MAX_POINTS, MEANING_POOL, NEAR_DUPLICATE, RELATIVE_FLOOR, _ASKS_NOW, _FIGURE, _Meaning, _NEGATION, _score, _term_weights, _was_said, centrality, correcting, disagree, select, superseded  # noqa: F401  (moved; re-exported)
from tessellate.ai.composer_answer import _Answer, _LEARNED, _NOW_WORDS, _REGISTER, _RELATIVE_DAYS, _SESSION, _count_word, _due, figures_of  # noqa: F401  (moved; re-exported)


def _pick(question: str, salt: str, options: list[str]) -> str:
    """One of `options`: the same one every time for this question (and, in
    a conversation, this turn), a different one for most different
    questions."""
    session = _SESSION.get()
    digest = hashlib.sha1(f"{salt}:{question.strip().lower()}{':' + session if session else ''}".encode()).digest()
    return options[digest[0] % len(options)]


#: The first words a quote may have lowered after a joiner ("Separately,
#: the hills are steep"): words that are never a name. Anything else, a
#: name, "I", a capitalised word the app cannot tell from a name, keeps its
#: capital and takes the joiner after a colon instead.
_LOWERABLE = frozenset(
    """a an the it its this that these those there they their them we our
    you your he she his her one two three four five six seven eight nine ten
    every each some most all no not after before when if then in on at for
    to with without from by of only just still maybe once both next last
    first until since cut try keep ask write ship book buy call check get go
    make use add need plan start stop slow hire pair pairs foam sign
    out back""".split()
)


def _lowered(s: Sentence) -> str | None:
    """The quote with its first letter lowered, when its first word is one
    that is never a name ("The", "Ship", not "Harbor" or "I"); None otherwise."""
    if s.kind not in ("prose", "item") or len(s.text) < 2:
        return None
    first = re.match(r"[A-Za-z]+", s.text)
    if not first or first.group(0).lower() not in _LOWERABLE or first.group(0)[1:] != first.group(0)[1:].lower():
        return None
    return s.text[0].lower() + s.text[1:]


#: A sentence opening with one of these leans on the one before it: "It
#: forces the reading to be active" quoted alone has lost what "it" is.
_LEANS_BACK = re.compile(r"^(it|this|that|these|those|they|he|she|then|there|which|second|third|another)\b", re.I)


def _with_context(out: _Answer, sentences: list[Sentence]) -> list[Sentence]:
    """The sentences, each one that leans back preceded by the sentence it
    leans on (the note's own previous sentence, quoted whole too)."""
    have = {(s.note_id, s.order) for s in sentences}
    result: list[Sentence] = []
    for s in sentences:
        if s.order and s.kind == "prose" and _LEANS_BACK.match(s.text) and (s.note_id, s.order - 1) not in have:
            before = out.views[s.note_id].sentences[s.order - 1]
            if before.kind == "prose":
                before.score = before.score or s.score
                result.append(before)
                have.add((s.note_id, before.order))
        result.append(s)
    return result


def _quotes(out: _Answer, sentences: list[Sentence], terms: list[str], lower_first: bool = False) -> None:
    """Sentences of one note, run together in the note's own order; a picture's
    reading introduced as the app's reading of it, and each sentence other
    notes repeat followed by how many say it. `lower_first` lowers the first
    sentence's first letter, after a joiner that ends in a comma."""
    lower_first, out.lower_next = lower_first or out.lower_next, False
    for i, s in enumerate(sentences):
        if _said_with_before(sentences, i):
            continue
        if i:
            out.t("space")
        if not i and lower_first and _lowered(s):
            out.q(s, terms, _lowered(s))
            if s.echoes:
                out.t("echo").m(out.count(1 + len(s.echoes))).t("echo_end")
            continue
        if s.kind.startswith("picture"):
            _picture_said(out, sentences, i, terms)
        else:
            out.q(s, terms)
            if s.kind == "prose" and i + 1 < len(sentences) and not _ENDED.search(s.text):
                #: A first line with no full stop ("Side project ideas from
                #: the hackathon") ran into the next quote (INBOX 787).
                out.t("stop")
        if s.echoes:
            out.t("echo").m(out.count(1 + len(s.echoes))).t("echo_end")


#: A picture's words said in full up to this many lines.
PICTURE_LINES = 6


def _said_with_before(sentences: list[Sentence], i: int) -> bool:
    """A picture's line said with the reading before it (`_picture_said`)."""
    s, before = sentences[i], sentences[i - 1] if i else None
    return s.kind == "picture_text" and before is not None and before.kind.startswith("picture") and before.note_id == s.note_id


def _picture_said(out: _Answer, sentences: list[Sentence], i: int, terms: list[str]) -> None:
    """One picture's reading said once (INBOX 787): "The picture in your note
    from 5 September shows a screenshot of ..., which reads “Ranked
    Solo/Duo” and “Gold II”." Its lines after the first are said with it,
    never as a sentence each that names the picture again."""
    s = sentences[i]
    run = _picture_run(out, sentences, i)
    out.t("picture_in").name(out.views[s.note_id])
    reads = run
    if s.kind == "picture":
        out.t("picture_shows").q(s, terms, s.text.rstrip(".") if len(run) > 1 else None)
        reads = run[1:]
        out.t(*(("ov_reads",) if reads else ()))
    else:
        out.t("picture_reads")
    _quoted_lines(out, reads, terms)
    if reads or not _ENDED.search(s.text):
        out.t("stop")


def _quoted_lines(out: _Answer, lines: list[Sentence], terms: list[str]) -> None:
    """“A”, “B” and “C”: a picture's lines in quotes."""
    for n, line in enumerate(lines):
        if n:
            out.t("and" if n == len(lines) - 1 else "comma")
        out.t("open_quote").q(line, terms).t("close_quote")


def _picture_run(out: _Answer, sentences: list[Sentence], i: int) -> list[Sentence]:
    """The reading at `i` and the lines of its words said with it: every line,
    up to six, when the answer chose one of them ("what is on my feature
    list" asked for the list, and two lines of five were said); else the
    lines chosen right after it."""
    s = sentences[i]
    lines = [u for u in out.views[s.note_id].sentences if u.kind == "picture_text" and u.order >= s.order]
    chosen = any(u.kind == "picture_text" and u.note_id == s.note_id for u in sentences[i:])
    if chosen and len(lines) <= PICTURE_LINES + 1:
        return [s, *[u for u in lines if u is not s][:PICTURE_LINES]]
    run = [s]
    for later in sentences[i + 1:]:
        if later.kind != "picture_text" or later.note_id != s.note_id:
            break
        run.append(later)
    return run


_ENDED = re.compile(r"[.!?…:;\"”’)\]]\s*$")


#: A list the person wrote reads as one sentence when every entry is a short
#: phrase: "Designing Data-Intensive Applications, The Mom Test and A Pattern
#: Language". Past these it is a list, and is shown as one.
FUSE_MAX_ITEMS = 6
FUSE_MAX_WORDS = 10


def _fusable(items: list[Sentence]) -> bool:
    """Every entry a phrase lifted whole from the list (no sentence of its own
    inside it, no colon), short enough to read in one breath."""
    return (
        2 <= len(items) <= FUSE_MAX_ITEMS
        and all(s.kind == "item" for s in items)
        and all(len(s.text.split()) <= FUSE_MAX_WORDS and not re.search(r"[.!?:;]\s*$|:\s", s.text) for s in items)
    )


def _sentence_case(items: list[Sentence]) -> bool:
    """Entries written as sentence-case phrases ("A light jacket", "Plug
    adapter"), not names ("The Mom Test"): only these have their first letter
    lowered inside a sentence, which leaves the person's words as they wrote
    them everywhere else."""
    return all(not re.search(r"\s[A-Z]", s.text) for s in items)


def _joined(out: _Answer, keys: list[str], unit: list[Sentence], terms: list[str], when: date | None = None, colon: bool = False) -> None:
    """A joiner, an optional measured day, then the note's sentences: after a
    comma with the first letter lowered when it can be ("Later, on 3 March,
    the hotel is booked"), after a colon when it cannot or `colon` says so
    (a joiner that is not a clause: "The newest, from 3 March: ...")."""
    out.t(*keys)
    if when:
        out.m(out.day(when))
    if _lowered(unit[0]) and not colon:
        if when or not PHRASES[out.voiced(keys[-1])].endswith(" "):
            out.t("comma")
        _quotes(out, unit, terms, lower_first=True)
    else:
        out.t("colon")
        _quotes(out, unit, terms)


def _list_sentence(out: _Answer, items: list[Sentence], terms: list[str]) -> None:
    """" A, B and C." from the list's own entries."""
    lower = _sentence_case(items)
    for i, s in enumerate(items):
        if i:
            out.t("and" if i == len(items) - 1 else "comma")
        shown = decap(s.text) if lower else s.text
        out.q(s, terms, shown)
    out.t("stop")


def _your_kind(view: NoteView) -> str:
    """"Your note", or "Your board", "Your mind map", "Your document" for a
    source that is not a note (INBOX 744: "a board must say board")."""
    return f"your_{view.kind}_cap" if view.kind in ("board", "map", "document") else "your_note_cap"


def _list_lead(out: _Answer, view: NoteView, lead: str) -> None:
    """What introduces a list: "Your note **Reading list** lists ", or "It
    also lists " when the answer already named the note."""
    if lead == "opening" and _unlike_before(out, ["your_note_cap", "in_cap"])[0] == "in_cap":
        #: "In **Reading list** you listed four: ...", after a turn that
        #: opened "Your note ...".
        out.t("in_cap").name(view).t("you_listed")
    elif lead == "opening":
        if view.titled:
            out.t(_your_kind(view), "space")
        out.name(view, cap=True).t("lists")
    else:
        out.t("it_lists")


def _checklist_count(out: _Answer, view: NoteView, tasks: list[Sentence], lead: str) -> None:
    """How many of a checklist are ticked. Zero is "none of its three", one
    left unticked is "one item, not done": a count word before "of" is never
    "no" (audit 1029 C6)."""
    ticked = sum(1 for s in tasks if s.done)
    opening = lead == "opening"
    if opening:
        if view.titled:
            out.t(_your_kind(view), "space")
        out.name(view, cap=True)
    if ticked:
        out.t("has" if opening else "checklist").m(out.count(ticked)).t("checklist_of").m(out.count(len(tasks)))
        out.t("checklist_items_done" if opening else "checklist_done")
    elif len(tasks) == 1:
        out.t("has" if opening else "checklist").t("one_open")
    else:
        out.t("has_none_of_its" if opening else "checklist_none_of_its").m(out.count(len(tasks)))
        out.t("checklist_items_done" if opening else "checklist_done")


def _list_block(out: _Answer, view: NoteView, items: list[Sentence], terms: list[str], lead: str) -> None:
    """A note's list, introduced by what it holds: "Your note **Reading
    list** lists four: ...", a checklist with how many are ticked."""
    tasks = [s for s in items if s.kind == "task"]
    if tasks and len(tasks) == len(items):
        _checklist_count(out, view, tasks, lead)
        out.t("para")
        for i, s in enumerate(tasks):
            if i:
                out.t("line")
            out.item(s, terms)
        return
    _list_lead(out, view, lead)
    if composer_tree.nested(items):
        composer_tree.write(out, items, terms)
        return
    out.m(out.count(len(items)))
    if _fusable(items):
        out.t("colon")
        _list_sentence(out, items, terms)
        return
    out.t("end_colon", "para")
    for i, s in enumerate(items):
        if i:
            out.t("line")
        out.item(s, terms)


_OPENERS = (
    "open_notes", "open_wrote", "open_put", "open_figure", "open_date", "open_where",
    "closest_a", "closest_b", "going_by", "notes_have", "wrote_on_a",
)


def _unlike_before(out: _Answer, keys: list[str]) -> list[str]:
    """`keys` less any the turn before opened with, in their order; all of
    them when every one did."""
    fresh = [k for k in keys if not _said_before(out, k)]
    return fresh or keys


def _said_before(out: _Answer, key: str) -> bool:
    """Whether the turn before opened with `key`'s words in any variant of
    either voice."""
    names = {key}
    for voice in composer_tables.VOICES:
        names.update(composer_tables.VOICE_VARIANTS[voice].get(key, ()))
    return any(out.opened_with(PHRASES[name]) for name in names)


def _opening(out: _Answer, s: Sentence, shape: str, question: str) -> None:
    """What comes before the strongest sentence on the first line, which is
    the answer: often nothing, the sentence itself, or a short opener chosen
    by the question so answers in a row do not start alike. The note is not
    named here; its citation follows the quote (`_Answer.cite`)."""
    view = out.views[s.note_id]
    if out.brief and shape not in ("yesno", "when"):
        #: Asked for briefly: the sentence itself, nothing before it.
        return
    if shape == "count" and _NUMBER_CUE.search(s.text):
        options = ["", "open_figure", "open_notes"]
    elif shape == "when" and when_words.find(s.text):
        options = ["", "open_date"]
    elif shape == "when" and view.written:
        #: No date in the sentence: the day the note was written is the one
        #: date the app knows, and it is said as that and nothing more.
        out.t("wrote_on_a").m(out.day(view.written)).t("wrote_on_b")
        return
    elif shape == "yesno":
        #: A sentence that holds every word the question is about answers it
        #: in the note's own words: "Going by your notes, the deposit is
        #: paid." Never a yes or a no of the app's own (INBOX 688's rule).
        stems = out.subject
        if stems and _says_every(stems, s, view):
            options = ["going_by", "notes_have"]
        else:
            options = ["closest_a", "closest_b"]
    elif shape == "explain":
        options = ["", "open_put", "open_notes"]
    elif shape == "where":
        options = ["", "open_where", "open_notes"]
    else:
        options = ["", "open_notes", "open_wrote"]
    #: Not the opener the turn before opened with, and after a turn that
    #: opened with a bare quote, a worded one when there is one: two answers
    #: in a row never start alike (INBOX 741, vary openers across turns).
    fresh = [o for o in options if not (o and _said_before(out, o))]
    if out.previous and not any(_said_before(out, o) for o in _OPENERS):
        fresh = [o for o in fresh if o] or fresh
    key = _pick(question, "lead", fresh or options)
    if key == "going_by" and _lowered(s):
        out.t("going_by", "comma")
        out.lower_next = True
    elif key:
        out.t("notes_have" if key == "going_by" else key)


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


def _others(out: _Answer, meaning: _Meaning, lead: Sentence, rest: list[Sentence], terms: list[str], question: str) -> None:
    """The other notes, one sentence group each, as prose: each joined to
    what came before by how it relates to it (also, later, separately), each
    topic its own paragraph. Prose only: a list item quoted inside a sentence
    loses the list that gave it its meaning."""
    rest = _with_context(out, [s for s in rest if s.kind == "prose" or s.kind.startswith("picture")])
    if not rest:
        return
    order: list[int] = []
    for s in rest:
        if s.note_id not in order:
            order.append(s.note_id)
    units = [sorted((s for s in rest if s.note_id == i), key=lambda s: s.order) for i in order]
    said = [s for s in out.views[lead.note_id].sentences if s.key in out.cited]
    last = ""
    used: set[str] = set()
    for group in _clusters(meaning, units):
        for g, unit in enumerate(group):
            #: Two notes to a paragraph at most: a topic's paragraph that runs
            #: on through five notes reads as a wall.
            out.t("space" if g % 2 else "para")
            view = out.views[unit[0].note_id]
            relation = _relation(out, meaning, unit[0], said or [lead], lead)
            if unit[0].kind.startswith("picture") and len(unit) == 1:
                #: A picture's reading names its note itself ("The picture
                #: in **Sketches** shows ..."): no joiner before it.
                _quotes(out, unit, terms)
            elif relation == "later":
                #: "Later, on" once, "And on" once, then the sentence alone:
                #: newer notes are not in date order among themselves here,
                #: so "Then on" (which says "after that") is never used.
                last = next((k for k in ("later_on", "and_on") if k not in used), "")
                if last:
                    used.add(last)
                    _joined(out, [last], unit, terms, view.written)
                else:
                    _quotes(out, unit, terms)
            else:
                #: The same subject mostly needs no joiner: the sentence and
                #: its citation are enough, and a pile of "also" is what the
                #: owner read as a template (INBOX 741). Never the same
                #: joining words twice in one answer. A joiner for the same subject only where the quote can
                #: follow it after a comma: "On top of that: Subject: ..." is
                #: two colons and no sentence.
                pool = ["", "and_join", "on_top"] if relation == "also" and _lowered(unit[0]) else [""]
                if relation != "also":
                    pool = ["separately", "elsewhere", "another_note"]
                options = [o for o in pool if o not in used] or [""]
                last = _pick(f"{question}:{view.id}", "join", options)
                if last:
                    used.add(last)
                if last:
                    _joined(out, [last], unit, terms)
                else:
                    _quotes(out, unit, terms)
            out.cite(view)
            said.extend(unit)


def _timeline(out: _Answer, sentences: list[Sentence], terms: list[str]) -> None:
    """A "when" question's other notes, as bullets in the order they were
    written: a timeline is a list, and reads as one."""
    sentences = _with_context(out, [s for s in sentences if s.kind != "task"])
    if not sentences:
        return
    order: list[int] = []
    for s in sentences:
        if s.note_id not in order:
            order.append(s.note_id)
    order.sort(key=lambda note_id: out.views[note_id].written or date.min)
    out.t("para", "timeline")
    for note_id in order:
        view = out.views[note_id]
        out.t("line", "bullet")
        if view.written:
            out.m(out.day(view.written)).t("colon")
        _quotes(out, sorted((s for s in sentences if s.note_id == note_id), key=lambda s: s.order), terms)
        if view.titled or not view.written:
            out.cite(view)


def _earlier(out: _Answer, sentences: list[Sentence], terms: list[str]) -> None:
    """A "latest" question's older notes, newest first, as prose that walks
    back: "Before that, on 12 September, three workstreams ... [**Q4 roadmap**]"."""
    sentences = _with_context(out, [s for s in sentences if s.kind == "prose" or s.kind.startswith("picture")])
    order: list[int] = []
    for s in sentences:
        if s.note_id not in order:
            order.append(s.note_id)
    order.sort(key=lambda note_id: out.views[note_id].written or date.min, reverse=True)
    for i, note_id in enumerate(order):
        view = out.views[note_id]
        out.t("para")
        unit = sorted((s for s in sentences if s.note_id == note_id), key=lambda s: s.order)
        if view.written:
            _joined(out, [("before_that", "then_on", "earlier_on")[i] if i < 3 else "and_on"], unit, terms, view.written)
        else:
            _quotes(out, unit, terms)
        out.cite(view)


def _disagreement(chosen: list[Sentence]) -> tuple[Sentence, Sentence] | None:
    for i, a in enumerate(chosen):
        for b in chosen[i + 1:]:
            if disagree(a, b):
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


#: Words too short or too common to report as missing: a two-letter word
#: missing from a note says nothing about the note.
_MISSING_MIN = 3


def _one_edit(a: str, b: str) -> bool:
    """One letter added, dropped or changed: "gamin" for "gaming"."""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return a[i + 1 :] == b[i + 1 :] or a[i:] == b[i + 1 :]
    return True


def _seen(term: str, found: set[str]) -> bool:
    """A word asked is not missing when a note has it in another shape: a
    past form ("buy" in "I just bought"), or the word mistyped ("gamin" for
    "gaming"), which said "I couldn't find any reference to buy or gamin"
    under the answer that quoted both (owner, 2026-10-12)."""
    from tessellate.ai import factgraph

    stem = _stem(term)
    #: The dropped "g" ("gamin", "runnin") stems as its own word.
    if stem in found or (term.lower().endswith("in") and _stem(term + "g") in found):
        return True
    factgraph._tables()
    if any(factgraph._PAST.get(word) == stem for word in found):
        return True
    return len(stem) >= 4 and any(_one_edit(stem, word) for word in found if word[:1] == stem[:1])


#: Words that tell the composer how to answer, never what to find: a note
#: that does not hold "sentences" is not missing anything (audit 1029 C37).
_INSTRUCTION_STEMS = frozenset(
    _stem_plain(w)
    for w in """main two three four five six seven eight nine ten both sentence paragraph line point bullet tag category categories
    improve improvement related similar recur recurring older newer oldest newest favourite favorite best worst everything
    summary list top first second third biggest largest smallest cheapest priciest
    gist overview story stuff style preferred prefer relationship give quick rough general overall kind sort type
    recorded outgoing mean meaning refer referring exact""".split()
)
#: An adverb says how, not what: "what did I personally think", "is it
#: actually recorded" are never missing their "personally" (stress run 2026-10-30).
_MANNER = re.compile(r"(?:ally|ely|ently|antly|ously|ively|edly|icitly)$", re.I)


def _quoted_words(out: _Answer, views: list[NoteView]) -> set[str]:
    """Words of the sentences the answer quoted and of the notes it named."""
    quoted = {w for v in views for s in v.sentences if s.key in out.cited for w in s.words}
    quoted |= {w for v in views if v.id in out.named for w in v.title_words | v.filed_words}
    return quoted


@functools.lru_cache(maxsize=1)
def _shape_stems() -> dict[str, str]:
    return {_stem(word): shape for word, shape in composer_tables.SHAPE_WORDS.items()}


def _says_every(stems, sentence, view) -> bool:  # noqa: ANN001
    """Every question word is in the sentence, its note's name, or its shape."""
    words = set(sentence.words) | view.title_words
    return all(_holds(t, words) or _said_by_shape(t, sentence.text) for t in stems)


def _said_by_shape(term: str, quoted_text: str) -> bool:
    """A question word the sentence says by its shape ("money" by "$40")."""
    shape = composer_tables.SHAPE_WORDS.get(term.lower()) or _shape_stems().get(_stem(term))
    return bool(shape and rec.says_shape(shape, quoted_text))


#: Words that frame a question rather than name its topic, read from its
#: shape: the word after "how" ("how hot"), the verb after "do I" or "I've"
#: ("do I turn", "have I seen"), and aggregate, pronoun and comparison words.
#: Named as "not mentioned" they told the person a note was missing a word
#: no note would hold (audit 1030 Z16: "turn", "seen", "total", "him").
_FRAME_SHAPES = re.compile(
    r"\bhow (?!to\b)(\w+)"
    r"|\b(?:do|does|did|can|could|should|would|will|have|has|had|am|is|are|was|were) (?:i|we|you) (?:\w+ly )?(?!a\b|an\b|the\b)(\w+)"
    r"|\b(?:i|we)(?:'ve|'d|'ll| have| had| will)? (?!have\b|had\b|am\b|was\b)(\w+)"
    r"|\bwhat (\w+s) (?:in|into|inside|with|on)\b",
    re.I,
)
_FRAME_WORDS = frozenset(
    _stem_plain(w)
    for w in """total sum plus overall whole altogether notebook theme themes him her them myself yourself ourselves
    more less sooner later further farther right now ingredient ingredients contents details information""".split()
)


@functools.lru_cache(maxsize=256)
def _frame_stems(question: str) -> frozenset[str]:
    said = {w for m in _FRAME_SHAPES.finditer(question or "") for w in m.groups() if w}
    return frozenset(_stem(w) for w in said) | _FRAME_WORDS


def _is_unfound(out: _Answer, term: str, found: set[str], quoted: set[str], quoted_text: str = "") -> bool:
    if len(term) < _MISSING_MIN or _stem(term) in _INSTRUCTION_STEMS or _MANNER.search(term) or _seen(term, found):
        return False
    if _stem(term) in _frame_stems(out.question or ""):
        return False
    if _alternatives(_stem(term)) & quoted or _said_by_shape(term, quoted_text):
        return False
    return not out.question or term.lower() in out.question.lower()


def _unfound_terms(out: _Answer, terms: list[str], views: list[NoteView]) -> list[str]:
    found: set[str] = set()
    for view in views:
        found |= view.words | view.title_words | view.filed_words
    #: A synonym counts as found only in a sentence the answer quoted: "trip
    #: cost" answered by the budget's own line is not missing "cost", but a
    #: "hotel" no quote (or quoted note's name) stands in for is still said
    #: to be missing.
    quoted = _quoted_words(out, views)
    quoted_text = " ".join(s.text for v in views for s in v.sentences if s.key in out.cited)
    return [t for t in terms if _is_unfound(out, t, found, quoted, quoted_text)]


def _missing(out: _Answer, terms: list[str], views: list[NoteView]) -> None:
    """"None of these notes mention “hotel”." for the question's words that no
    note found contains, measured over every word of every one of them.

    Said of "these notes", the ones found, and not of the notebook: retrieval
    chose them, and a claim about every note would be a claim nothing here
    measured."""
    missing = _unfound_terms(out, terms, views)
    if not missing or len(missing) == len(terms):
        return
    out.t("para", "missing")
    for i, word in enumerate(missing[:3]):
        if i:
            out.t("or")
        out.t("open_quote").asked(word).t("close_quote")
    out.t("stop")


def _own_notes(own_stems: set[str], other_stems: set[str], views: list[NoteView]) -> list[NoteView]:
    """The notes a side names by title. A title that holds every word of the
    side is the note named: "running log" is the Running log, not also the
    Running plan that shares "running" (2026-10-30 sweep)."""
    mine = own_stems - other_stems
    titled = [(v, {_stem(w) for w in v.title_words}) for v in views]
    whole = [v for v, words in titled if len(own_stems) > 1 and own_stems <= words]
    return whole or [v for v, words in titled if mine & words]


def _kinds(notes: list[NoteView], side: set[str]) -> set[str]:
    return {_stem(w) for v in notes for w in v.title_words} - side


def _parallel(mine: list[NoteView], side: set[str], theirs: list[NoteView], other: set[str]) -> list[NoteView]:
    """A side's notes of the same kind as the other side's: "Lisbon vs Tokyo"
    is the Lisbon trip against the Tokyo trip, not the Lisbon packing list
    (audit 1030 Z58). All of them when none is."""
    kinds = _kinds(theirs, other)
    same = [v for v in mine if _kinds([v], side) & kinds]
    return same or mine


def _sides_own(stems: list[set[str]], views: list[NoteView]) -> list[list[NoteView]]:
    """The notes named for each side, of like kind; none when two sides
    claim the same note."""
    n = len(stems)
    others = [set().union(*(st for j, st in enumerate(stems) if j != i)) for i in range(n)]
    own = [_own_notes(stems[i], others[i], views) for i in range(n)]
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


def _compare_lead(out: _Answer, sides: tuple[str, ...], counts: list[int]) -> None:
    out.t(_unlike_before(out, ["of_found", "across_found"])[0])
    for i, (label, n) in enumerate(zip(sides, counts)):
        if i:
            out.t("and")
        out.m(out.count(n)).t("mentions_one" if n == 1 else "mention_many").asked(label)


_LENGTH_ASK = re.compile(r"\b(?:longer|shorter|bigger|smaller)\b", re.I)


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


def _versus_lead(out: _Answer, question: str, own: list[list[NoteView]]) -> bool:
    """"which is cheaper, A or B": both figures (or days) first."""
    versus = composer_versus.two(question, own, out.today)
    if versus:
        composer_versus.write(out, versus)
    return versus is not None


def _compare_shares(stems, own, picks) -> tuple[list, list]:  # noqa: ANN001
    """What is said of each side only, then what speaks of two or more."""
    n = len(picks)
    others = [set().union(*(stems[j] for j in range(n) if j != i)) for i in range(n)]
    only = [[s for s in picks[i] if own[i] or not (others[i] & set(s.words))][:3] for i in range(n)]
    #: What speaks of two sides is not a line already said under a side.
    said = {id(s) for side in only for s in side}
    both = [s for s in picks[0] if others[0] & set(s.words) and id(s) not in said][:2] if n == 2 else _shared(picks, others, said)
    return only, both


def _compare(out: _Answer, sides: tuple[str, ...], views: list[NoteView], meaning_for, question: str = "") -> bool:  # noqa: ANN001
    """A line that counts each side, each side its own short list, then what
    speaks of two or more of them."""
    terms, stems, own, picks = _side_picks(sides, views, meaning_for)
    only, both = _compare_shares(stems, own, picks)
    if not any(only):
        return False
    if not _length_lead(out, question, own) and not _versus_lead(out, question, own):
        _compare_lead(out, sides, [len({s.note_id for s in side}) for side in only])
    #: The lead names only what follows (probe P15): no "Here is what
    #: each says." before the headings that say it.
    out.t("stop")
    for label, side, side_terms in zip(sides, only, terms):
        _compare_side(out, label, side, side_terms)
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


_LEADING_ARTICLE = re.compile(r"^(?:the|a|an|my|our|your)\s+(?=\S)", re.I)


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
    for s in side:
        out.t("line").item(s, side_terms).cite(out.views[s.note_id], again=True)


#: A question that asks for everything on a subject rather than one fact:
#: answered by how many notes mention it, then the sentence most of them lean
#: towards (`centrality`), then one sentence from each other note.
_BROAD = re.compile(
    r"^\s*(?:what (?:do|did|have) (?:i|we|my notes|you) (?:know|say|said|written|write|wrote|got|have)\b"
    r"|what(?:'s| is) in my notes\b|tell me (?:about|everything)\b|everything (?:about|on)\b"
    r"|summari[sz]e\b|give me an overview\b|(?:an )?overview of\b"
    r"|(?:is there )?anything (?:about|on)\b|do i have (?:any )?(?:notes? )?(?:about|on)\b"
    r"|have i (?:written|got|noted) (?:anything |down )?(?:about|on)\b|what(?: is|'s)? the deal with\b"
    r"|what do (?:i|you) have on\b|how many (?:of my )?notes\b|catch me up on\b|fill me in on\b|bring me up to speed on\b)",
    re.I,
)

#: "briefly", "in short", "quick": the lead note alone. "in detail",
#: "everything": more points than an ordinary answer (INBOX 741, length
#: fitted to the question).
_BRIEF = re.compile(r"\b(briefly|in brief|in short|short answer|quick(?:ly)?|tl;?dr|in a (?:word|sentence|line)|just tell me)\b", re.I)
_FULL = re.compile(r"\b(in detail|in depth|more detail|detailed|thorough(?:ly)?|the full|everything|all (?:the|of the))\b", re.I)
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

        out.t("para").m(insights.after_lead(insight))
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
    _lead_block(out, shape, lead, [lead], terms, question)
    _others(out, meaning, lead, [s for s in firsts if s.note_id != lead.note_id and s.key not in skip], terms, question)
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
_STILL_OPEN = re.compile(
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
    for view in sorted(views, key=lambda v: (v.title_words != wanted, not wanted <= v.title_words, v.rank)):
        if not wanted or not wanted & {_stem(w) for w in _words(str(view.note.get("content") or ""))}:
            continue
        dated = _days_named(view, today, asked[0])
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


def _say_until(out: _Answer, day: date, today: date, ahead: bool) -> None:
    """"Ten days from today, on 21 October", or "That's today"."""
    days = abs((day - today).days)
    if days == 0:
        out.t("until_today")
        return
    unit = "day" if days == 1 else "days"
    out.m(out.count(days).capitalize()).t(f"until_{'ahead' if ahead else 'ago'}_{unit}").m(out.day(day))


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
        if day >= today if ahead else day <= today:
            dated.append((day, fact.start))
    return dated


def told_as_past(content: str, at: int) -> bool:
    """Whether the sentence of `content` holding `at` tells of something that
    happened (`recognise.told_as_past`, audit 1030 Z26)."""
    start = max(content.rfind(m, 0, at) for m in (". ", "! ", "? ", "\n")) + 1
    stops = [i for i in (content.find(m, at) for m in (". ", "! ", "? ", "\n")) if i >= 0]
    return rec.told_as_past(content[start: min(stops) if stops else len(content)])


def _newest(out: _Answer, views: list[NoteView], guessing: bool = False) -> None:
    """The newest notes, each by its first sentence, newest first. When the
    question named nothing to look for, the lead says these are a fallback."""
    shown = [v for v in views if v.sentences][:5]
    if not shown:
        return
    out.t("newest_guess" if guessing else "newest_lead").m(out.count(len(shown))).t("newest_mid")
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
            out.t("list_from").m(out.day(view.written))
            if linked:
                out.address(f"](#/notes/{view.id})")
        else:
            out.name(view, cap=True)
        out.t("colon")
        #: A picture's note as what it shows and its words; a note's
        #: heading with the sentence after it (INBOX 787).
        _overview_line(out, _overview().best_line(view.sentences, set()), set())


# --- what to ask next -----------------------------------------------------------

#: A suggested question longer than this is not a chip (`followups.MAX_LENGTH`).
NEXT_MAX_CHARS = 90
_NOTE_NOUNS = frozenset({"note", "notes", "entry", "entries", "jotting", "jottings"})


def _own_terms(terms: list[str]) -> list[str]:
    """"notes" is how the question was put, not what it is about: the chip
    once asked "What is the latest on notes about sourdough?" (row 410)."""
    return [t for t in terms if t.lower() not in _NOTE_NOUNS]


def _tag_holders(views: list[NoteView], asked: set[str]) -> dict[str, list[NoteView]]:
    holders: dict[str, list[NoteView]] = {}
    for view in sorted(views, key=lambda v: v.rank):
        if view.note.get("connected"):
            continue
        for tag in dict.fromkeys(str(t) for t in (view.note.get("tags") or [])):
            if re.fullmatch(r"\w[\w -]{1,30}", tag) and _words(tag) and not set(_words(tag)) & asked:
                holders.setdefault(tag.lower(), []).append(view)
    return holders


def _shared_tag_pick(views: list[NoteView], asked: set[str], cited: set[int]) -> list[tuple] | None:
    #: A tag two or more of the notes found share, the question did not name:
    #: a thread through them ("harbor" under a question about beta testers).
    #: One note's tag alone ("admin" on the dentist note) is not a thread.
    holders = _tag_holders(views, asked)
    shared = [(tag, held) for tag, held in holders.items() if len(held) >= 2 and any(v.id in cited for v in held)]
    if not shared:
        return None
    tag, held = max(shared, key=lambda pair: (len(pair[1]), -min(v.rank for v in pair[1])))
    view = next(v for v in held if v.id in cited)
    original = next(str(t) for t in view.note.get("tags") or [] if str(t).lower() == tag)
    return [("template", PHRASES["next_tag_a"]), ("filed", original, view.id), ("template", PHRASES["next_tag_b"])]


def _unquoted_note_pick(views: list[NoteView], asked: set[str], cited: set[int]) -> list[tuple] | None:
    #: A note found and not quoted that has something to say about the
    #: question (a sentence of it scored at least half the best), by its name.
    best = max((s.score for v in views for s in v.sentences), default=0.0)
    for view in sorted(views, key=lambda v: v.rank):
        if view.id in cited or view.note.get("connected") or not view.titled:
            continue
        if (view.title_words and view.title_words <= asked) or not any(s.score >= best / 2 > 0 for s in view.sentences):
            continue
        return [("template", PHRASES["next_note_a"]), ("title", view.title, view.id), ("template", PHRASES["next_note_b"])]
    return None


def _subject_pick(question: str, shape: str, terms: list[str]) -> list[tuple] | None:
    #: The question's own subject, when it is a short name ("dentist
    #: check-up", "sourdough"), asked the other way round in time.
    own = _own_terms(terms)
    subject = _asked_span(question, own)
    if subject and len(subject.split()) == len(own) <= 3 and shape not in ("status", "recent", "compare"):
        prefix = "next_latest_a" if shape == "when" or _pick(question, "next", ["a", "b"]) == "a" else "next_when_a"
        return [("template", PHRASES[prefix]), ("asked", subject), ("template", PHRASES["next_tag_b"])]
    return None


def _next_questions(question: str, shape: str, terms: list[str], views: list[NoteView], cited: set[int]) -> list[list[tuple]]:
    """Two or three questions the answer opens up, built from what it found and
    did not say (INBOX 725, 5): a tag of the notes it quoted that the question
    did not name, a note it found and did not quote, and the latest on the
    question's own subject. Each is a fixed question around the person's own
    words, so a chip never offers what the notes cannot answer about."""
    asked = {_stem(t) for t in terms} | {_stem(w) for w in query_understanding.search_terms(question)}
    #: "random ahh" names no subject: the chips about it would ask for nothing.
    if question_noise.filler_subject(" ".join(terms)):
        terms = []
    found = (
        _shared_tag_pick(views, asked, cited),
        _unquoted_note_pick(views, asked, cited),
        _subject_pick(question, shape, terms),
    )
    picks = [pick for pick in found if pick]
    out = [p for p in picks if len("".join(part[1] for part in p)) <= NEXT_MAX_CHARS]
    return out[:3]


# --- a follow-up, read against the turn before ----------------------------------

_MORE = re.compile(
    r"^\s*(?:tell me more|more|go on|continue|keep going|say more|what else|anything else|and|more please|"
    r"more about (?:that|it|this|those))[\s?.]*$",
    re.I,
)
_ORDINALS = {"first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2, "fourth": 3, "4th": 3, "fifth": 4, "5th": 4, "last": -1}
_ORDINAL = re.compile(r"\bthe (first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th|last) (?:one|note)\b", re.I)
_PRONOUN = re.compile(r"\b(it|that|this|them|those|they)\b", re.I)
#: A question that leans on the answer before it (audit 1030 Z53): it opens
#: with an asking word and either says "it" or has no subject of its own.
_ASKS_SLOT = re.compile(r"^(?:and |so |ok |okay )*(?:what|when|where|who|which|how|why|is|are|was|were|does|do|did|can|could|will|would|should)\b", re.I)
_SLOT_PRONOUN = re.compile(r"\b(?:it|its|that|them|those)\b", re.I)
#: A question about a total or an instance with no subject of its own:
#: "how far in total", "what's the total", "when was the last one".
_TOTAL_WORDS = frozenset({"far", "much", "many", "long", "total", "last", "latest", "first", "next", "previous", "one", "altogether"})
_TOTAL_ASK = re.compile(
    r"^(?:and |so |ok |okay )*(?:what|when|where|how)\b(?!.*(?-i:[A-Z]\w|\d))"
    r"(?=.*\b(?:in total|in all|altogether|the total|(?:the )?(?:last|latest|first|next|previous) one)\b)[^.]*$",
    re.I,
)
#: A pronoun that is the point of the phrase, not a reference to a note.
_NOT_REFERRING = re.compile(r"\b(?:what|how|when) (?:is|was) (?:it|that) like\b|\bwhat is (?:it|that)\b$|\bhow is it\b", re.I)


def refers_back(question: str) -> bool:
    """Whether `question` is about whatever the last answer was about: it says
    "it" ("when is it", "how much does it cost", "what did we decide about
    it") or has no subject of its own ("what time", "who is it with"). Not a
    question with a name, a number or a time window of its own, nor one that
    compares: those stand alone."""
    q = " ".join((question or "").split()).rstrip("?.! ")
    if not q or not _ASKS_SLOT.match(q) or _NOT_REFERRING.search(q) or rec.without_windows(q) != q:
        return False
    if re.search(r"\b[A-Z][a-z]|\d|\b(?:compare|versus|vs|than|between)\b", q[1:]):
        return False
    pronoun = bool(_SLOT_PRONOUN.search(q))
    return pronoun or not [t for t in subject_terms(q) if not _SLOT_PRONOUN.fullmatch(t)]
#: "what about the boiler?", "and the boiler?", "how about Porto": the turn
#: before asked again of something else (INBOX 741, turn-aware follow-ons).
_SWAP = re.compile(
    r"^\s*(?:(?:and|but|ok|okay|so)[, ]+)?(?:what|how) about\s+(?P<x>[^\s,].*)$"
    r"|^\s*(?:and|but)\s+(?P<y>(?!(?:what|when|who|where|why|how|which|is|are|do|does|did)\b)[^\s?].*)$",
    re.I,
)
#: "why?", "and when?", "how come?": the asking word alone, about the turn
#: before's subject.
#: The "Did you mean “how”?" chip, pressed.
#: Closing quote and "?" come off in code: `(.+?)...\s*\?*\s*$` was quadratic
#: on a run of whitespace (CodeQL); so for `_CORRECTION`, `_LENGTH`,
#: `_WINDOW_ONLY` and `_BARE` below.
_MEANT = re.compile(r"^\s*did you mean\s+[“\"']?(\S.*)$", re.I)
_BARE = re.compile(r"^\s*(?:(?:and|but|so|ok|okay)[, ]+)?(why|when|where|who|how come|how many|how much|how|since when)[\s?.!]*$", re.I)
_BOLD = re.compile(r"\*\*(.+?)\*\*")
#: "no, the gym one", "not that one, the running note", "I meant the dentist
#: note": the turn before answered from the wrong note (decision 35).
_CORRECTION = re.compile(
    r"^\s*(?:no|nope|not that(?: one)?|wrong one|not quite)[,.!]?\s+(?:i meant\s+|i mean\s+|the one about\s+)?(?P<x>\S.*)$"
    r"|^\s*i meant\s+(?P<x2>\S.*)$",
    re.I,
)
#: "shorter", "in more detail": the turn before again, at another length.
_LENGTH = re.compile(
    r"^\s*(?:shorter|briefer|less|in short|tl;?dr|summari[sz]e that|longer|more detail|in (?:more )?detail|"
    r"(?:make it|say it|be|can you be) (?:shorter|briefer|longer|more detailed))(?:\s+please)?[\s.?!]*$",
    re.I,
)
#: "and last week?", "what about yesterday?": the turn before over another time.
_WINDOW_ONLY = re.compile(r"^\s*(?:(?:and|but|so|ok)[, ]+)?(?:(?:what|how) about\s+)?(?P<w>[^\s,].*)$", re.I)


def _without_length(question: str) -> str:
    """The question with a length wish ("briefly", "in detail") taken off."""
    text = _BRIEF.sub("", question)
    text = _FULL.sub("", text)
    return " ".join(text.replace(" ,", ",").split()).strip(" ,")


@dataclass
class FollowOn:
    """A question read against the turn before it: `question` is what is
    searched for and answered, `previous` the earlier question it leans on,
    `said` the earlier answer (a "tell me more" quotes something new)."""

    question: str
    previous: str
    said: str = ""
    kind: str = "more"
    #: A correction's words ("no, the gym one": "gym"): the notes they name
    #: are put first, the ones the answer before quoted after (decision 35).
    prefer: str = ""


def _named_notes(answer: str) -> list[str]:
    """The notes an earlier composed answer named, in the order it named
    them: its bold names, less the bold words that are not a note's."""
    fixed = {value.strip("* ") for value in PHRASES.values()}
    names: list[str] = []
    for name in _BOLD.findall(answer or ""):
        if name not in fixed and name not in names:
            names.append(name)
    return names


#: "Which is the main note on uni", "which one is the defining note": the
#: note that is plainly about the subject (`composer_digest._defines`), asked
#: for, not a note property to search for (audit 1031 C26).
_DEFINING_WORD = r"(?:main|defining|key|best|central|principal|primary|core|top|most important|definitive)"
_DEFINING = re.compile(
    rf"(?:and |so |ok |okay )?(?:which|whats?)(?:'s| is| one is| note is| one's)?(?: (?:is|note is|one is))? (?:my |the |your )?{_DEFINING_WORD}"
    r"(?: (?:note|one|entry))?(?: (?:note|one|entry))?(?: (?:on|about|for|in|of) (?P<x>.+?))?[?.!\s]*",
    re.I,
)


def _defining_ask(question: str, turns: list[dict]) -> FollowOn | None:
    """The overview of the subject, whose lead is its defining note: the
    subject is named, or the earlier question's."""
    found = _DEFINING.fullmatch((question or "").strip())
    if not found:
        return None
    previous = str(turns[-1].get("question") or "").strip() if turns else ""
    named = re.sub(r"^(?:the|my|our)\s+", "", (found.group("x") or "").strip(), flags=re.I)
    terms = subject_terms(previous) if previous else []
    subject = named or (_asked_span(previous, terms) or " ".join(terms) if previous else "")
    return FollowOn(f"what do I know about {subject}", previous, "", "subject") if subject else None


def follow_on(question: str, history: list[dict] | None) -> FollowOn | None:
    """"Tell me more", "what about the second one", "when was that": a
    follow-up that only means something against the turn before (INBOX 725,
    6). None for a question that stands on its own, or with no turn before.

    - "Tell me more" is the earlier question again, quoting what it did not.
    - "The second one" is the second note the earlier answer named.
    - A question whose only subject is "it" or "that" takes the earlier
      question's subject in its place.
    """
    #: Small talk between ("ty", "lol ok") is not the turn a follow-on leans
    #: on: "what about the boiler?" after "ty" still means the question
    #: before the thanks (measured in Chat, INBOX 741).
    turns = [
        t for t in (history or [])
        if str(t.get("question") or "").strip() and not question_noise.social_kind(str(t.get("question") or ""))
    ]
    defining = _defining_ask(question, turns)
    if defining is not None:
        return defining
    if not turns:
        return None
    return _follow_one(question, _standing(turns))


#: Follow-on kinds whose reading is a question in its own right ("and last
#: week?", "what about Lisbon?"). The others ("longer", "why?", "no, the
#: launch one") lean on the question before, which stays the one the next
#: terse turn leans on: "why?" after "longer" asks about the subject, not
#: about "longer".
_RESTATES = frozenset({"window", "subject", "entity", "pronoun", "did_you_mean", "ordinal"})


def _standing(turns: list[dict]) -> list[dict]:
    """The turns with each terse one replaced by the question it stood for,
    read forwards, so a follow-on never leans on another follow-on's words."""
    out: list[dict] = []
    for turn in turns:
        text = str(turn.get("question") or "").strip()
        follow = _follow_one(text, out) if out else None
        prefer = ""
        if follow:
            text = follow.question if follow.kind in _RESTATES else follow.previous
            #: A correction's note stays chosen for the turns that lean on it:
            #: "no, the data structures one", then "shorter", is still that note (B8).
            prefer = follow.prefer or (out[-1].get("prefer", "") if follow.kind != "subject" else "")
        out.append({**turn, "question": text, "prefer": prefer})
    return out


#: A reader that does not recognise the turn returns this, so the next one is
#: tried; None means "recognised, and nothing to lean on", which ends the read.
_NOT_THIS: Any = object()


def _follow_more(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    if not _MORE.match(text):
        return _NOT_THIS
    #: A "more" after a "more" still means the question before both.
    for turn in reversed(turns):
        if not _MORE.match(str(turn.get("question") or "")):
            previous = str(turn.get("question") or "").strip()
            break
    said = "\n".join(str(t.get("answer") or "") for t in turns[-3:])
    return FollowOn(previous, previous, said, "more")


def _follow_ordinal(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    ordinal = _ORDINAL.search(text)
    if not ordinal:
        return _NOT_THIS
    names = _named_notes(str(last.get("answer") or ""))
    index = _ORDINALS[ordinal.group(1).lower()]
    if names and (index == -1 or index < len(names)):
        resolved = text[: ordinal.start()] + f"“{names[index]}”" + text[ordinal.end():]
        return FollowOn(resolved, previous, "", "ordinal")
    #: No list to count in: "when was the last one" may still lean on the subject.
    return _NOT_THIS


def _follow_correction(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    correction = _CORRECTION.match(text)
    if not correction:
        return _NOT_THIS
    #: The second alternative ("I meant the dentist note") fills x2, not x.
    said = (correction.group("x") or correction.group("x2") or "").rstrip(" \t.?!")
    prefer = re.sub(r"^(?:the|my|that|this)\s+", "", said.strip(), flags=re.I)
    prefer = re.sub(r"\s(?:one|note|entry)$", "", prefer, flags=re.I).strip()
    return FollowOn(previous, previous, "", "correction", prefer) if prefer else _NOT_THIS


def _follow_length(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    if not _LENGTH.match(text):
        return _NOT_THIS
    shorter = text.lstrip().lower().startswith(("shorter", "briefer", "in short", "tl;dr", "tldr", "summarise that", "summarize that", "less"))
    base = _without_length(previous)
    return FollowOn(f"briefly, {base}" if shorter else f"{base.rstrip('?.!')} in detail?", previous, "", "length", str(last.get("prefer") or ""))


def _follow_window(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    window = _WINDOW_ONLY.match(text)
    window_text = window.group("w").rstrip(" \t?.!") if window else ""
    found_time = when_words.find(window_text) if window else []
    #: Only a turn that is nothing but a time ("and last week?"): "what did
    #: I write yesterday" is a question of its own.
    if not (found_time and not window_text.replace(found_time[0][2], "").strip(" ,")):
        return _NOT_THIS
    base = previous
    for _s, _e, old_phrase in when_words.find(previous):
        base = base.replace(old_phrase, "")
    base = " ".join(base.split()).rstrip(" ?.!")
    return FollowOn(f"{base} {found_time[0][2]}?", previous, "", "window")


def _follow_meant(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    meant = _MEANT.match(text)
    if not meant:
        return _NOT_THIS
    word = meant.group(1).rstrip(" \t?").rstrip("”\"'").strip(" \t?")
    tokens = re.findall(r"[\w']+", previous)
    candidates = [t for t in tokens if t.lower() != word.lower() and len(t) >= 2]
    if not candidates:
        return None
    typed = min(candidates, key=lambda t: question_noise.distance(t, word))
    if question_noise.distance(typed, word) > max(1.0, question_noise.allowance(word) + 0.5):
        return None
    resolved = re.sub(rf"\b{re.escape(typed)}\b", word, previous, count=1)
    return FollowOn(resolved, previous, "", "did_you_mean")


def _follow_bare(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    bare = _BARE.match(text) or _BARE.match(rephrase(text))
    if not bare:
        return _NOT_THIS
    subject = _asked_span(previous, subject_terms(previous))
    if not subject:
        return None
    start = previous.lower().find(subject.lower())
    article = re.search(r"\b(?:the|my|our|a|an)\s+$", previous[:start], re.I)
    subject = previous[article.start():start] + subject if article else subject
    word = bare.group(1).lower()
    word = "why" if word == "how come" else word
    verb = {"why": "", "how": "do I", "how many": "", "how much": "is", "since when": ""}.get(word, "is")
    resolved = " ".join(w for w in (word.capitalize(), verb, subject) if w) + "?"
    return FollowOn(resolved, previous, "", word)


def _swap_in_shape(previous: str, other: str, subject: str, entity: bool) -> FollowOn:
    """The previous question with its subject swapped for `other`, when the
    question has a shape of its own."""
    start = previous.lower().find(subject.lower())
    before = previous[:start]
    if re.search(r"\b(the|my|a|an)\s+$", before, re.I):
        other = re.sub(r"^(the|my|a|an)\s+", "", other, flags=re.I)
    resolved = before + other + previous[start + len(subject):]
    return FollowOn(resolved, previous, "", "entity" if entity else "subject")


def _swap_plain_what(previous: str, other: str, subject: str, entity: bool) -> FollowOn:
    #: A plain "what" asked again of something else ("what did I do
    #: at the gym", then "what about running?"): the subject's phrase
    #: (its preposition and article too) gives way to the new one.
    start = previous.lower().find(subject.lower())
    lead_in = re.search(r"(?:\b(?:at|in|on|for|about|with|of|to)\s+)?(?:\b(?:the|my|a|an)\s+)?$", previous[:start], re.I)
    head = previous[: lead_in.start() if lead_in else start].rstrip()
    tail = previous[start + len(subject):]
    kind = "entity" if entity else "subject"
    if re.search(r"\b(?:is|are|was|were|'s)$", head, re.I):
        #: "What is the launch plan?" then "what about the boiler?":
        #: not "what is the boiler", which asks something else.
        return FollowOn(f"What do my notes say about {other}?", previous, "", kind)
    bare_other = re.sub(r"^(the|my|a|an)\s+", "", other, flags=re.I)
    joined = f"with {other}" if entity else f"about {bare_other}"
    return FollowOn(f"{head} {joined}{tail}", previous, "", kind)


def _follow_swap(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    swap = _SWAP.match(text) or _SWAP.match(rephrase(text))
    if swap and swap.group("y") is not None and not text.rstrip().endswith("?"):
        swap = None
    if not swap:
        return _NOT_THIS
    other = (swap.group("x") or swap.group("y") or "").rstrip(" \t?.!").strip()
    subject = _asked_span(previous, subject_terms(previous))
    #: Only a question with a shape of its own is asked again of the
    #: new subject; "what about X" after a plain "what" is its own
    #: question, and stands as typed.
    entity = bool(re.fullmatch(r"(?:[A-Z][\w'-]*)(?: [A-Z][\w'-]*)*", other))
    if other and subject and classify(previous) not in ("what", "recent") and subject_terms(other):
        return _swap_in_shape(previous, other, subject, entity)
    if other and subject and subject_terms(other):
        return _swap_plain_what(previous, other, subject, entity)
    return None


#: "what should I get her", "what else do I know about him": a person the turn
#: before named (audit 1031 C12).
_PERSON_PRONOUN = re.compile(r"\b(?:her|him|she|he|hers|his)\b", re.I)


def _pronoun_kind(text: str) -> str:
    """Which pronoun follow-on `text` is: "bare" (a pronoun and no subject),
    "slot" ("how much does it cost"), "person" ("what should I get her"),
    "total" (no subject of its own at all), or "" for none."""
    bare = _PRONOUN.search(text) and not [t for t in subject_terms(text) if not _PRONOUN.fullmatch(t)]
    if bare:
        return "bare"
    #: "how much does it cost", "when is it due": the slot word is not a subject.
    if refers_back(text) and _SLOT_PRONOUN.search(text):
        return "slot"
    if _ASKS_SLOT.match(text.strip()) and _PERSON_PRONOUN.search(text) and not re.search(r"\b[A-Z][a-z]", text.strip()[1:]):
        return "person"
    #: "what's the total", "how far in total": no subject of its own at all.
    if _TOTAL_ASK.search(text) and not _PRONOUN.search(text) and not set(subject_terms(text)) - _TOTAL_WORDS:
        return "total"
    return ""


def _pronoun_swap(text: str, named: str, kind: str) -> str:
    """`text` with its pronoun replaced by the subject's name."""
    pattern = _PRONOUN if kind == "bare" else (_SLOT_PRONOUN if kind == "slot" else _PERSON_PRONOUN)

    def said(match: re.Match) -> str:
        #: "her birthday" is "Sara's birthday"; "get her" is "get Sara".
        word = match.group(0).lower()
        possessive = word in ("his", "hers") or (word == "her" and bool(text[match.end():].strip(" ?.!")))
        return named + ("'s" if possessive and kind == "person" else "")

    return pattern.sub(said, text, count=1)


def _follow_pronoun(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    kind = _pronoun_kind(text)
    if not kind:
        return None
    subject = _asked_span(previous, subject_terms(previous))
    if not subject:
        return None
    article = re.search(r"\b(?:the|my|our)\s+$", previous[: previous.lower().find(subject.lower())], re.I)
    #: A bare "that" keeps the old bare subject; the newer slot and person
    #: follow-ons read with the article ("how much does the Lisbon trip cost").
    named = (article.group(0).strip() + " " if article and kind != "bare" else "") + subject
    if kind == "total":
        return FollowOn(f"{text.rstrip(' ?.!')} for {named}?", previous, "", "pronoun")
    return FollowOn(_pronoun_swap(text, named, kind), previous, "", "pronoun")


#: Tried in this order: a "more" is not a correction, and a correction is not a swap.
_FOLLOW_READERS = (
    _follow_more, _follow_ordinal, _follow_correction, _follow_length, _follow_window, _follow_meant,
    _follow_bare, _follow_swap, _follow_pronoun,
)


def _follow_one(question: str, turns: list[dict]) -> FollowOn | None:
    last = turns[-1]
    previous = str(last.get("question") or "").strip()
    text = (question or "").strip()
    for reader in _FOLLOW_READERS:
        got = reader(text, previous, last, turns)
        if got is not _NOT_THIS:
            return got
    return None


@dataclass
class Dialogue:
    """What a conversation has said so far (decision 35), built from the
    request's history, never kept on the server: the turns, the sentences
    and notes already quoted, the subjects in order, the names mentioned,
    the last answer's measured values, the corrections, and the salt that
    makes "Ask again" in this chat a different wording of the same answer.
    `compose(dialogue=...)` reads it and adds the turn it answers."""

    history: list[dict] = field(default_factory=list)
    quoted: list[str] = field(default_factory=list)
    quoted_ids: set[int] = field(default_factory=set)
    topic_stack: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    last_measures: list[str] = field(default_factory=list)
    corrections: list[str] = field(default_factory=list)
    used: set[str] = field(default_factory=set)
    salt: str = ""

    @property
    def turns(self) -> int:
        return len(self.history)

    @classmethod
    def from_history(cls, history: list[dict] | None, salt: str = "") -> Dialogue:
        """The dialogue a request's history describes: the chat's salt is
        its first question's (stable for the chat) unless one is given, and
        the words earlier answers used are found in their text."""
        turns = [{"question": str(t.get("question") or ""), "answer": str(t.get("answer") or "")} for t in history or []]
        dialogue = cls(history=turns, salt=salt or (hashlib.sha1(turns[0]["question"].encode()).hexdigest()[:12] if turns else ""))
        for turn in turns:
            dialogue.used |= _templates_in(turn["answer"])
            dialogue.topic_stack += [t for t in subject_terms(turn["question"]) if t not in dialogue.topic_stack]
        return dialogue

    def record(self, question: str, result: dict) -> None:
        """Add the turn `result` answered."""
        self.history.append({"question": question, "answer": result.get("text", "")})
        for row in result.get("grounding") or []:
            self.quoted.append(row["sentence"])
            self.quoted_ids.add(row["note_id"])
        self.topic_stack += [t for t in subject_terms(question) if t not in self.topic_stack]
        self.entities += [p[1] for p in result.get("parts") or [] if p[0] == "title" and p[1] not in self.entities]
        self.last_measures = [p[1] for p in result.get("parts") or [] if p[0] == "measure"]
        self.used |= {p[1] for p in result.get("parts") or [] if p[0] == "template" and _TEMPLATE_WORDS.search(p[1])}


#: A joining or opening phrase (letters and length), as opposed to a stop or
#: a space: the words a conversation should not hear twice.
_TEMPLATE_WORDS = re.compile(r"[A-Za-z]{3}")


def _templates_in(answer: str) -> set[str]:
    """The worded `PHRASES` an earlier answer's text holds."""
    if not answer:
        return set()
    return {v for v in _WORDED_PHRASES() if v in answer}


_WORDED: list[str] = []


def _WORDED_PHRASES() -> list[str]:  # noqa: N802  # a cached table, read like one
    if not _WORDED:
        _WORDED.extend(v for v in set(PHRASES.values()) if len(v.strip()) >= 6 and _TEMPLATE_WORDS.search(v))
    return _WORDED


# --- a question in two parts, and one that could mean two things -------------

#: Where one question ends and the next begins inside one message: a question
#: mark with more after it, or "and" before a question word ("when is the
#: dentist and what should I pack"). At most `MAX_PARTS` are answered.
#: `split_parts` collapses whitespace first, so one space is the break;
#: `\s+` here was quadratic on a run of whitespace (CodeQL).
_PART_BREAK = re.compile(r"(?<=\?) ")
_PART_AND = re.compile(
    r",? (?:and|also|plus) (?=(?:what|when|who|where|why|how|which|is|are|do|does|did|can|should|will)\b)",
    re.I,
)
MAX_PARTS = 3


def split_parts(question: str) -> list[str]:
    """The questions one message asks, each as typed: two or three, or the
    one. A comparison is one question however many "and"s it has."""
    text = " ".join((question or "").split())
    if not text or _SHAPE_RULES[0][1].search(text):
        return [text]
    pieces: list[str] = []
    for chunk in _PART_BREAK.split(text):
        pieces.extend(p for p in _PART_AND.split(chunk) if p.strip())
    #: Each part must ask about something of its own: "and how?" is not a
    #: second question, it leans on the first.
    pieces = [p.strip(" ,") for p in pieces]
    if len(pieces) < 2 or any(len(subject_terms(p)) == 0 for p in pieces):
        return [text]
    return pieces[:MAX_PARTS]


def _multi(question: str, parts: list[str], notes: list[dict], **kwargs) -> dict | None:
    """Each part answered on its own, under the person's own words for it in
    bold: "**When is the dentist?** Check-up booked for the 21st."."""
    answers = [(part, compose(part, notes, **kwargs)) for part in parts]
    answers = [(part, a) for part, a in answers if a["grounding"]]
    if len(answers) < 2:
        return None
    pieces: list[tuple] = []
    rows: list[dict] = []
    seen: set[tuple] = set()
    nexts: list[list[tuple]] = []
    for i, (part, answer) in enumerate(answers):
        if i:
            pieces.append(("template", PHRASES["para"]))
        label = part.rstrip("?.! ")
        pieces += [("template", PHRASES["bold"]), ("asked", label[0].upper() + label[1:]), ("template", PHRASES["qmark"])]
        pieces += [("template", PHRASES["bold"]), ("template", PHRASES["space"])]
        pieces += list(answer["parts"])
        for row in answer["grounding"]:
            if (row["note_id"], row["start"]) not in seen:
                seen.add((row["note_id"], row["start"]))
                rows.append(row)
        nexts += [p for p in answer["next_parts"] if p not in nexts]
    text = "".join(piece[1] for piece in pieces)
    return {
        "text": text,
        "grounding": rows,
        "support": grounding.support("\n\n".join(row["sentence"] for row in rows), rows),
        "shape": "multi",
        "parts": pieces,
        "next": ["".join(part[1] for part in p) for p in nexts[:3]],
        "next_parts": nexts[:3],
    }


#: Two notes this close in score, on different topics, both named for what
#: was asked, and a question this short: it could mean either.
CLARIFY_RATIO = 0.85


def _clarify(out: _Answer, shape: str, terms: list[str], lead: Sentence, meaning: _Meaning, views: list[NoteView]) -> None:
    """"Did you mean **Boiler service** or **House**?" after an answer to a
    short question two notes answer about equally and differently. The
    likelier is answered first, so the question is never all the reply."""
    if shape not in ("what", "yesno", "when", "where", "who") or not 1 <= len(terms) <= 2:
        return
    best: dict[int, Sentence] = {}
    for view in views:
        for sentence in view.sentences:
            if sentence.score and (view.id not in best or sentence.score > best[view.id].score):
                best[view.id] = sentence
    top = best.get(lead.note_id)
    if not top or not out.views[lead.note_id].titled:
        return
    stems = {_stem(t) for t in terms}
    rivals = [
        s for note_id, s in best.items()
        if note_id != lead.note_id
        and out.views[note_id].titled
        and not out.views[note_id].note.get("connected")
        and s.score >= CLARIFY_RATIO * top.score
        and not meaning.same_topic(s, top)
        and stems & out.views[note_id].title_words
    ]
    #: The lead's heading holding more of the words asked than the rival's
    #: settles it: that note is the one called what was asked about.
    lead_hits = len(stems & out.views[lead.note_id].title_words)
    if len(rivals) != 1 or lead_hits > len(stems & out.views[rivals[0].note_id].title_words):
        return
    out.t("para", "clarify_a").name(out.views[lead.note_id]).t("clarify_or").name(out.views[rivals[0].note_id]).t("qmark")
    out.readings = [lead.note_id, rivals[0].note_id]


#: A question that is only a name ("the meeting", "harbor"), at most this
#: many words, that two or more notes are called: it could mean any of them.
READINGS_WORDS = 4
MAX_READINGS = 4


def _readings(out: _Answer, question: str, terms: list[str], views: list[NoteView]) -> None:
    """The numbered readings of a question that only names something two or
    more notes are called (decision 45): "Which do you mean: 1. **Meeting
    with Sam**; 2. **Meeting notes, Thursday**?" With a model running it
    picks one (or asks); with none, the person does. Never added when
    `_clarify` already asked."""
    if out.readings or not terms or len((question or "").split()) > READINGS_WORDS or _ASKS_FIRST.match(rephrase(question)):
        return
    stems = {_stem(t) for t in terms}
    named = [v for v in views if v.titled and not v.note.get("connected") and stems <= {w for t in v.title_words for w in (t, _stem(t))}]
    if len(named) < 2:
        return
    out.readings = [v.id for v in named[:MAX_READINGS]]
    out.t("para", "readings_a")
    for i, view in enumerate(named[:MAX_READINGS], 1):
        if i > 1:
            out.t("semicolon")
        out.m(str(i)).t("reading_dot").name(view)
    out.t("qmark")


def _meant(term: str, stem: str, vocabulary: set[str]) -> bool:
    """A word the notes hold, or a dictionary word, is what was meant:
    "rust" is not "rest" (it once quoted a soup recipe for "what do I know
    about rust")."""
    return _holds(stem, vocabulary) or term.lower() in spelling.english()


def _fit_terms(terms: list[str], views: list[NoteView], report: list | None = None) -> list[str]:
    """The question's words, each one no note holds put right against the
    notes' own words ("lisbn" is "lisbon" when a note says Lisbon): one
    edit for a short word, two for a long one, and only to a single nearest
    word. For scoring only: the answer never prints a word the person did
    not type."""
    vocabulary: set[str] = set()
    for view in views:
        vocabulary |= view.words | view.title_words | view.filed_words
    fitted: list[str] = []
    for term in terms:
        stem = _stem(term)
        #: Four letters at least, the same first letter, and never to a
        #: shorter word: "peru" is not a typo of "per", "hotle" is of "hotel".
        if len(stem) < 4 or _meant(term, stem, vocabulary):
            fitted.append(term)
            continue
        allowed = question_noise.allowance(stem)
        near = sorted(
            (question_noise.distance(stem, word), word) for word in vocabulary
            if word[:1] == stem[:1] and len(word) >= max(4, len(stem)) and len(word) - len(stem) <= allowed
        )
        best = [word for d, word in near if near and d <= near[0][0] + 0.1]
        chosen = best[0] if near and near[0][0] <= allowed and len(best) == 1 else term
        fitted.append(chosen)
        if chosen != term and report is not None:
            #: A second note word nearly as near makes the reading unsure:
            #: "Did you mean “hostel”?" is offered beside the answer.
            others = [w for d, w in near if w != chosen and d <= allowed and d - near[0][0] <= question_noise.UNSURE_GAP]
            if others:
                report.append({"typed": term, "chosen": chosen, "alternative": others[0]})
    return fitted


# --- small talk, in the app's own voice ----------------------------------------

#: What the composer says to "hi", "thanks", "how are you", "bye" and "what
#: can you do" when no model is running (INBOX 741, the owner: "more social,
#: more engaging"). Warm and brief, Atlas's voice by default (CHAT_PLAN
#: decision 26); each kind has several, chosen by the message, so the same
#: greeting twice in a row is not answered word for word the same. Nothing
#: here says anything about the notes: these are the app's own words.
SOCIAL: dict[str, tuple[str, ...]] = {
    "morning": (
        "Good morning. What would you like to look up?",
        "Morning. Your notes are ready when you are.",
        "Morning. Ask me about anything you have jotted down.",
    ),
    "how": (
        "All good here, and your notes are in order. What can I find for you?",
        "Doing well, thanks for asking. What would you like to know?",
        "Fine, thank you. Anything you want to look up?",
        "Everything is excellent. How can I assist you with your notes?",
        "I am well, thanks. Let's dig into your records.",
    ),
    "sorry": (
        "No need to apologise. What would you like to try?",
        "Not at all. Ask it another way and I will look again.",
        "It's completely fine. What can I do for you?",
        "Don't worry about it. Let's try again.",
        "That's okay. What are you looking for?",
        "It is no trouble. Let me know what you need.",
        "All good. Let's find what you need in your notes.",
    ),
    "laugh": (
        "Glad something made you smile. Anything else I can find?",
        "Ha. What next?",
        "Good to hear. Ask whenever you like.",
        "Haha, very nice. What should we look up now?",
        "Glad you found that funny. Ready for the next question?",
        "Heh. Let me know if you need to search anything else.",
    ),
    "reaction": (
        "I know. Anything you want to look up about it?",
        "Quite something. What next?",
        "Fair reaction. Want me to find anything else?",
        "Absolutely. Shall we search for something else?",
        "Totally. Let me know what to look up.",
        "Understood. Anything more to check?",
        "I hear you loud and clear. What next?",
        "Indeed. Let me know if you have another question.",
    ),
    "confused": (
        "Sorry, that was not clear. Ask it another way, or say “tell me more” for the rest of what I found.",
        "Let me try again: put it in other words, or name the note you mean.",
        "My answer may have missed. Which part should I look at again?",
        "Apologies, I didn't get that. Mind rephrasing your question?",
        "I seem to be a bit confused. Can you try asking in a different way?",
        "I'm not quite following. Can you tell me exactly what note to look for?",
        "Could you clarify? Let's try searching one more time.",
    ),
    "ack": (
        "Good. Anything else?",
        "All right. What next?",
        "Noted. Ask whenever you like.",
        "Got it. What else can I find?",
        "Understood. Ready when you are.",
        "Okay. Let me know if you need more.",
        "Acknowledged. Let's move on to the next search.",
        "Sure thing. What is next on the list?",
    ),
    "who": (
        "I am the notebook's assistant. With no model running I answer from your notes in their own words.",
        "I am here to find things in your notes and say what they say.",
        "I am a search assistant designed to retrieve exactly what you have written in your notes.",
        "I am your dedicated notebook assistant. Ask a question and I'll find it in your records.",
    ),
    "about_app": (
        "I answer from your notes: ask when something is, who said what, what the latest is on a project, or what you know about a subject. Connecting a model adds writing, summaries in its own words and tools.",
        "Ask me about anything you wrote down: a date, a decision, a list, how a project is going. Two questions in one message work too. Connecting a model adds writing and tools.",
        "I'm built to read your notes and report back exactly what you recorded. Try asking about a specific event or task.",
        "I help you comb through your notes without needing to summarize them. Ask me when something happened or who said what.",
    ),
    "joke": (
        "I have no jokes of my own: I only say what is in your notes. If you saved one, ask me for it.",
        "Jokes are not something I make up. If one of your notes has a good one, I can find it.",
    ),
    "unclear": (
        "I could not read that one. Ask about a note, a date or a list, or say what you want to do.",
        "That did not read as words to me. What would you like to find?",
    ),
    "compliment": (
        "I am glad to hear that. What can I find for you next?",
        "That's kind of you. What else should we search for?",
        "Much appreciated. Anything else in your notes to find?",
        "Glad I could be of service. Let me know what else you need.",
    ),
    "insult": (
        "Apologies. Let's try rephrasing the question.",
        "My apologies. I will try to get it right next time.",
        "I am sorry if I let you down. How can I improve this search?",
        "Sorry about that. Could you try asking in a different way?",
        "My bad. I'm limited to exact matches in your notes, so try a different wording.",
        "Apologies for the frustration. What should we look for instead?",
    ),
    "emotion": (
        "I understand. What can I help you find?",
        "Okay. I am here when you need to search your notes.",
        "I hear you. Take your time, and let me know what you need.",
        "Got it. Whenever you are ready, I can search your notes.",
        "I'm sorry to hear that. What can I look up for you?",
        "That's totally fair. Let's focus on what we can find in your notes.",
        "Understood. I am here to assist with any searches you need.",
        "I can imagine. Let me know what you want to review in your notes.",
    ),
}

for _kind, _more in composer_tables.SOCIAL_NATURAL_EXTRA.items():
    SOCIAL[_kind] = SOCIAL[_kind] + _more
SOCIAL_PROFESSIONAL = composer_tables.SOCIAL_PROFESSIONAL
#: **The engine is Atlas** (CHAT_PLAN decision 36; the owner: "Composer
#: doesn't know it is atlas"): who it is and what it does are said in its
#: name, in both voices, with no model and with one.
SOCIAL["who"] = (
    "This is Atlas's assistant speaking. With no model running I answer from your notes in their own words.",
    "Atlas's assistant, that's me. I find things in your notes and say what they say.",
    "Atlas's assistant, at your service: I answer from your notes, and to talk to Atlas itself you can connect a model.",
    "Think of me as Atlas's assistant: ask me when something is, what you decided or what you did last week.",
)
SOCIAL["about_app"] = (
    "I'm Atlas's assistant. I answer from your notes: when something is, who said what, what the latest is on a project. "
    "I also set reminders, tag, pin and move notes, and work out sums and conversions. Connecting a model adds writing in its own words.",
    "Atlas's assistant here. Ask about anything you wrote down: a date, a decision, a list, how a project is going or what you did "
    "last week. Say \"remind me to...\" and I set it. Connecting a model adds writing and tools.",
    "I'm Atlas's assistant, and I read your notes for you: ask when something happened or who said what, or tell me to pin, tag or delete a note.",
)

#: Eight phrasings or more in every family, of more than one shape
#: (`composer_replies`; the owner: "can it have more varied responses??").
for _kind, _more in composer_replies.SOCIAL_NATURAL.items():
    SOCIAL[_kind] = SOCIAL.get(_kind, ()) + _more
for _kind, _more in composer_replies.SOCIAL_PROFESSIONAL.items():
    SOCIAL_PROFESSIONAL[_kind] = SOCIAL_PROFESSIONAL.get(_kind, ()) + _more
#: A hello, a thanks and a goodbye are a head and a tail chosen as a pair
#: (`composer_parts`), not a stored line said whole.
SOCIAL.update(composer_parts.lines("natural"))
SOCIAL_PROFESSIONAL.update(composer_parts.lines("professional"))

_SOCIAL_KIND = (
    ("morning", re.compile(r"\bgood (?:morning|afternoon|evening|day)\b|^morning\b", re.I)),
    ("thanks", re.compile(r"\b(?:thanks?|thank you|ta|cheers|nice one|appreciated?)\b", re.I)),
    ("how", re.compile(r"\bhow(?:'?s| is| are)(?: it going| things| you|you)\b|\bwhat'?s up\b|\bare you (?:ok|okay|there|awake|alive)\b", re.I)),
    ("bye", re.compile(r"\b(?:bye|goodbye|good night|night|see (?:ya|you)|later|cya)\b|\bthat'?s all\b|\bleave it there\b|\bcall it a day\b", re.I)),
    ("sorry", re.compile(r"\b(?:sorry|my bad)\b", re.I)),
    ("who", re.compile(r"\bwho are you\b|\byour name\b|\bare you (?:an? )?(?:ai|bot|robot|human|real|person|real person)\b", re.I)),
    ("greeting", re.compile(r"^\W*(?:hi|hey|hello|hiya|yo|sup|howdy)\b", re.I)),
    ("joke", re.compile(r"\b(?:joke|jokes|something funny|make me laugh)\b", re.I)),
    ("unclear", re.compile(r"^\W*\w*(?:asdf|sdfg|dfgh|fghj|ghjk|hjkl|qwer|wert|erty|rtyu|tyui|yuio|uiop|zxcv|xcvb|cvbn|vbnm|fdsa|lkjh|poiu|rewq)\w*\W*$", re.I)),
)


#: The kinds of turn after which the reply may offer the next step on what
#: was being talked about ("Say “tell me more” for more on “sync rewrite”.").
_NEXT_STEP_KINDS = ("ack", "thanks", "laugh", "reaction")
NEXT_STEPS = (
    "Say “tell me more” for more on “{subject}”.",
    "I can say more about “{subject}” if you like.",
    "Want the latest on “{subject}” next?",
    *composer_tables.NEXT_STEPS_EXTRA,
)
NEXT_STEPS_PROFESSIONAL = composer_tables.NEXT_STEPS_PROFESSIONAL

#: **A greeting composed from parts, one of them the person's own** (O5;
#: INBOX 904 B07, the owner: replies should vary and feel alive; CHAT_PLAN
#: decision 76's rundown is composed the same way). After a stored opener, a
#: hello, a test or an unclear turn gets an invitation built on a word of
#: the newest note (`invite`, the route's), so the same "hi" reads
#: differently as the notebook changes, and the ask it offers is one the
#: notes answer.
_INVITE_KINDS = ("greeting", "morning", "test", "unclear")
INVITES = {
    "natural": (
        "Your newest note mentions {subject}: ask “what did I write about {subject}” to pick up from there.",
        "Lately you've been writing about {subject}; ask me “what did I write about {subject}” to pick that back up.",
        "Your last note was about {subject}, so ask “what did I write about {subject}” to start there.",
        "Picking up where you left off: ask “what did I write about {subject}”.",
        "The last thing you wrote touched on {subject}. Ask me “what did I write about {subject}” and I'll find the notes.",
        "If it helps, ask me “what did I write about {subject}” and I will bring back your newest note.",
        "Your notes most recently turned to {subject}; ask me “what did I write about {subject}” and I'll go through them with you.",
        "Carry on from your latest note: ask “what did I write about {subject}”.",
    ),
    "professional": (
        "The most recent note concerns {subject}; ask “what did I write about {subject}” to review it.",
        "The latest entry mentions {subject}; ask “what did I write about {subject}” to bring up the notes.",
        "Your most recent entry refers to {subject}; ask “what did I write about {subject}” to review it.",
        "To continue, ask “what did I write about {subject}”.",
        "The newest note relates to {subject}; ask “what did I write about {subject}” to return to it.",
        "Recent entries mention {subject}; ask “what did I write about {subject}” to retrieve them.",
        "To see the most recent entry, ask “what did I write about {subject}”.",
        "The last entry recorded was about {subject}; ask “what did I write about {subject}” to see it.",
    ),
}


def social_kind(message: str, intent: str = "smalltalk") -> str:
    """The kind of conversational turn `message` is: one of `SOCIAL`."""
    if intent == "about_app":
        return "about_app"
    from tessellate.ai import intent as intent_module

    if intent_module.is_mash(message):
        return "unclear"
    if intent_module.is_test(message):
        return "test"
    return question_noise.social_kind(message) or next(
        (name for name, pattern in _SOCIAL_KIND if pattern.search(message or "")), "ack"
    )


def social(
    message: str,
    intent: str = "smalltalk",
    previous: str = "",
    last_question: str = "",
    voice: str = composer_tables.DEFAULT_VOICE,
    recent: list[str] | tuple = (),
    seed: str = "",
    invite: str = "",
) -> str:
    """The app's reply to a conversational turn with no model running (INBOX
    741: "any and all conversational messages"): warm, short, of the turn's
    kind, opening unlike any of the last three replies (`recent`, oldest
    first; `previous` alone when that is all there is) and shaped unlike the
    last (`phrasing.choose`), and after an acknowledgement or thanks, a next
    step on what was being talked about. `seed` is the conversation's: the
    same seed and turns give the same words. `invite` is a word of the
    newest note: a hello, a test or an unclear turn ends on an ask about it
    (`INVITES`) when its opener offered none."""
    #: A repair is worded by the route, which has the turn before
    #: (`composer_social.repair`); anywhere else it is confusion.
    kind = social_kind(message, intent).replace("repair", "confused")
    line = _social_line(message, kind, previous, last_question, voice, recent, seed)
    if invite and kind in _INVITE_KINDS and "“" not in line and not line.endswith("?"):
        line = f"{line} {invitation(message, invite, voice, seed)}"
    return line


def invitation(message: str, subject: str, voice: str, seed: str) -> str:
    """The invitation built on a word of the newest note (`INVITES`)."""
    said = "professional" if composer_tables.voice_of(voice) == "professional" else "natural"
    return _pick(f"{message}|{subject}", f"invite:{seed}", list(INVITES[said])).format(subject=subject)


def greeting_ask(message: str, voice: str, seed: str) -> str:
    """A plain offer to end a welcome that already names the last note (the
    invitation would say it twice, audit 1030 Z51)."""
    mood = composer_compose.voice_for(composer_tables.voice_of(voice))
    pool = [x.text for x in composer_lines.SOCIAL_TAILS["*"] if not x.emotions and mood in x.voices and x.text.endswith("?")]
    return _pick(message, f"greeting_ask:{seed}", pool) if pool else ""


def _social_line(message: str, kind: str, previous: str, last_question: str, voice: str, recent, seed: str) -> str:  # noqa: ANN001
    """The stored opener of `kind`, and a next step after an acknowledgement."""
    recent = [r for r in recent if r] or ([previous] if previous else [])
    professional = composer_tables.voice_of(voice) == "professional"
    if f"social_{kind}" in composer_lines.FRAMES:
        #: Composed in the voice and mood of the turn (CHAT_PLAN 1353).
        mood = composer_compose.mood_of(message, voice=voice, seed=f"{seed or _SESSION.get()}|{message}")
        line = phrasing.choose(composer_compose.eligible(f"social_{kind}", mood), f"social:{kind}:{message}", recent, seed or _SESSION.get())
    else:
        line = _stored_social(message, kind, professional, recent, seed)
    subject = _talked_about(last_question)
    if kind in _NEXT_STEP_KINDS and subject and len(subject) <= 40:
        line = f"{line} {_next_step(line, message, subject, professional)}"
    return line


def _talked_about(last_question: str) -> str:
    """What the turn before asked about, for a next step, or "" when it asked
    nothing of the notes: "fuck" after "yooooo" once offered more on
    “yooooo” (INBOX 1459). Whether its notes matched is the caller's to
    say: the chat passes `last_question` only for a turn that named notes."""
    from tessellate.ai import intent as intent_module

    if not last_question or intent_module.classify(last_question) != intent_module.NOTES:
        return ""
    return _asked_span(last_question, subject_terms(last_question))


def social_surfaces(kind: str, professional: bool = False) -> list[str]:
    """Every line `social` can say for `kind`: the stored ones, and for the
    kinds the composition layer words every sentence it can build."""
    built = [x.text for x in composer_compose.surfaces(f"social_{kind}")] if f"social_{kind}" in composer_lines.FRAMES else []
    return [*(SOCIAL_PROFESSIONAL if professional else SOCIAL)[kind], *built]


def _stored_social(message: str, kind: str, professional: bool, recent: list[str], seed: str) -> str:
    lines = (SOCIAL_PROFESSIONAL if professional else SOCIAL)[kind]
    #: A composed line never ends on a sentence one of the last few ended on.
    lines = [x for x in lines if not composer_parts.repeats_tail(x, recent[-phrasing.RECENT:])] or lines
    return phrasing.choose(lines, f"social:{kind}:{message}", recent, seed or _SESSION.get())


def _next_step(line: str, message: str, subject: str, professional: bool) -> str:
    """Never two questions back to back: after a line that asks, the next
    step is said, not asked."""
    steps = [n for n in (NEXT_STEPS_PROFESSIONAL if professional else NEXT_STEPS) if not (line.endswith("?") and n.endswith("?"))]
    return _pick(f"{message}|{subject}", "social:next", steps).format(subject=subject)


def call(names: list[str] | str, recent: list[str] | tuple = (), seed: str = "", voice: str = composer_tables.DEFAULT_VOICE) -> str:
    """The reply to a message that only called the assistant ("yo
    brotatockiibidyrizzler", `vocative.py`): here, and what it can do. A
    line that says the name back is one of several, so a nickname is
    acknowledged now and then, never every time, and never "Ha" at its own
    name."""
    name = names if isinstance(names, str) else (names[0] if names else "")
    lines = composer_replies.CALL[composer_tables.voice_of(voice)]
    own = name.lower() in ("atlas", "")
    usable = [line for line in lines if "{name}" not in line or not (own and line.startswith("Ha"))]
    if not name:
        usable = [line for line in usable if "{name}" not in line]
    line = phrasing.choose(usable, f"call:{name}", [r for r in recent if r], seed or _SESSION.get())
    return line.replace("{name}", name[:1].upper() + name[1:])


def call_asks(seed: str = "", count: int = 3) -> list[str]:
    """What a call offers next: `count` of `composer_replies.CALL_ASKS`,
    a different few for a different conversation."""
    asks = list(composer_replies.CALL_ASKS)
    start = int(hashlib.sha1(f"asks|{seed}".encode()).hexdigest(), 16) % len(asks)
    return [asks[(start + i) % len(asks)] for i in range(count)]


# --- the query plan (CHAT_PLAN Phase 6, decision 31) ------------------------------

#: The answer kinds a plan names (decision 31's discourse schemas): the shape
#: a question is read in, plus what only the plan sees (a time window, a
#: utility, a recall by time, an insight, a recommendation).
PLAN_KINDS = (
    "fact", "when", "list", "timeline", "comparison", "count", "yesno", "why", "how", "status",
    "recommendation", "recall", "insight", "utility",
)
_SHAPE_KIND = {
    "what": "fact", "who": "fact", "where": "fact", "when": "when", "count": "count", "yesno": "yesno",
    "list": "list", "compare": "comparison", "status": "status", "recent": "recall",
}
_WHY = re.compile(r"^\s*(?:why|how come|what (?:made|makes|caused|causes)|explain why)\b", re.I)
_RECALL = re.compile(
    r"\bwhat (?:did|have|had) (?:i|we) (?:do|did|done|write|wrote|written|get up to|work on|worked on|note|noted|been up to)\b"
    r"|\bwhat (?:did|have|had) (?:i|we) (?:add|added|save|saved|make|made|jot|jotted|capture|captured)\b"
    r"|\banything (?:i|we) (?:added|saved|made|wrote|noted|jotted|did|captured)\b|\bdid (?:i|we) (?:add|write|save|make|note|jot) anything\b"
    r"|\bwhat happened\b|\bwhat was i (?:doing|up to)\b|\bwhat(?:'s| is| was) (?:been )?going on\b|\banything (?:new|happen)\b",
    re.I,
)
#: The verbs of such a question, which are not subjects to search for.
_RECALL_VERBS = frozenset("add added save saved make made jot jotted capture captured anything write wrote note noted".split())
_INSIGHT = re.compile(r"\b(?:patterns?|habits?|trends?|keeps? coming up|how often do i|what do i (?:keep|always))\b", re.I)
_RECOMMEND = re.compile(r"^\s*(?:what|which) should (?:i|we)\b|^\s*should (?:i|we)\b|\brecommend|\bsuggest(?:ion)?s?\b", re.I)
_TAGGED = re.compile(r"\b(?:tagged(?: with)?|with the tags?|under the tags?)\s+#?([\w-]{1,40})|(?<![\w&])#([A-Za-z][\w-]{0,39})", re.I)
#: The words that name a kind of source (decision 37), and the kind.
_SOURCE_WORDS = (
    ("board", re.compile(r"\b(?:white)?boards?\b", re.I)),
    ("map", re.compile(r"\bmind ?maps?\b|\bmaps?\b", re.I)),
    ("document", re.compile(r"\bdocuments?\b|\bdocs\b", re.I)),
    ("picture", re.compile(r"\b(?:pictures?|photos?|images?|screenshots?)\b", re.I)),
)


@dataclass
class Plan:
    """What a question asks for, read before any note is (decision 31):
    the answer kind, the time window, the constraints, the subject's words
    and the length wished for. `compose` follows it; the route reads it to
    fetch the right notes (a recall by time fetches the window's notes)."""

    kind: str
    shape: str
    terms: list[str]
    window: tuple | None = None
    grain: str | None = None
    window_phrase: str = ""
    constraints: dict = field(default_factory=dict)
    source_kind: str | None = None
    length: str = ""
    utility: str | None = None


def _time_phrase(question: str) -> str:
    found = when_words.find(question or "")
    return found[0][2] if found else ""


def _plan_phrase(question: str, terms: list[str]) -> str:
    """The question's time phrase, or "" for a bare "recently" with no subject:
    "what did I write recently" asks for the newest notes, not a fortnight."""
    phrase = _time_phrase(question)
    return "" if not terms and rec.is_lately(phrase) else phrase


#: What the planner reads of a question. Its passes cost words x length, so a
#: 20,000-character paste took 38 s; the model still gets the whole question.
PLAN_CHARS = 2000


def _planned_text(question: str | None) -> str:
    return (question or "")[:PLAN_CHARS]


def _plan_constraints(question: str, terms: list[str]) -> tuple[dict, list[str], str | None]:
    """The tags and source kind a question names, and its terms without them."""
    constraints: dict = {}
    tags = [a or b for a, b in _TAGGED.findall(question or "")]
    if tags:
        constraints["tags"] = [t.lower() for t in tags]
        terms = [t for t in terms if t not in ("tagged", "tag", "tags") and t.lower() not in constraints["tags"]]
    source_kind = None
    for kind, pattern in _SOURCE_WORDS:
        if pattern.search(question or ""):
            source_kind = kind
            terms = [t for t in terms if not pattern.fullmatch(t)]
            break
    if source_kind:
        constraints["source_kind"] = source_kind
    return constraints, terms, source_kind


def _plan_kind(question: str, utility: str | None, shape: str, spanned: bool, has_terms: bool) -> str:
    if utility and utility != "until_note":
        return "utility"
    if spanned and not has_terms and (_RECALL.search(question or "") or shape in ("what", "recent", "list")):
        return "recall"
    if _INSIGHT.search(question or ""):
        return "insight"
    if _RECOMMEND.search(question or ""):
        return "recommendation"
    if shape == "explain":
        return "why" if _WHY.match(rephrase(question)) else "how"
    return _SHAPE_KIND.get(shape, "fact")


def _subject_left(question: str, terms: list[str], phrase: str) -> bool:
    """Whether the question has a subject besides its time phrase. A window
    still ahead ("May next year") is dropped when it has ("my trip next
    month" is notes about the trip, written now) and kept when it has none
    ("what did I write in May next year": nothing yet, said as that)."""
    said = set(phrase.lower().split())
    left = [t for t in terms if t.lower() not in said]
    return bool([t for t in left if t.lower() not in _RECALL_VERBS] if _RECALL.search(question or "") else left)


def window_verb_stems(question: str, phrase: str) -> list[str]:
    """The words of a question that is not a recall but names a window and no
    subject ("how much did I save in October": save): what a note in the
    window must hold to be read, the phrase's own words and the asking words
    left out."""
    said = {_stem(w) for w in re.findall(r"[\w']+", (phrase or "").lower())}
    return [st for st in _words(question) if st not in said and st not in _ASKING_WORDS and len(st) > 2]


def holds_any(stems: list[str], text: str) -> bool:
    """Whether `text` holds any of the stems, or a word that starts with one
    ("save" in "saved")."""
    words = set(_words(text))
    return any(_holds(st, words) or any(w.startswith(st) for w in words) for st in stems)


def _plan_window(question: str, terms: list[str], phrase: str, today: date) -> tuple[tuple | None, list[str]]:
    """The window the phrase names (None for none, or for one still ahead
    that sits beside a subject) and the subject terms left once the phrase's
    own words are taken out."""
    if phrase and rec.a_topic_phrase(question, phrase):
        said = [w for w in re.findall(r"[\w']+", phrase.lower()) if w not in rec.PHRASE_FILLER]
        return None, terms + [w for w in said if w not in terms]
    span = when_words.span(phrase, today, "past") if phrase else None
    if span and span[0] > today and _subject_left(question, terms, phrase):
        return None, terms
    return span, _without_window_words(question, terms, phrase) if span else terms


def _without_window_words(question: str, terms: list[str], phrase: str) -> list[str]:
    """"what did I write on Monday": the day is the window, not a subject to
    search the notes for (the phrase's own words, "monday", go, and a recall
    verb, and "archived", a state of the notes)."""
    gone = set(phrase.lower().split())
    if _RECALL.search(question or ""):
        gone |= _RECALL_VERBS
    if question_noise.asks_archived(question):
        gone.add("archived")
    return [t for t in terms if t.lower() not in gone]


def plan(question: str, today: date | None = None, *, recent: bool = False, embed=None) -> Plan:  # noqa: ANN001
    """The query plan for `question` on `today` (the person's own day), read
    from its first `PLAN_CHARS` characters."""
    question = _planned_text(question)
    today = today or user_today()
    utility = utilities.kind_of(question)
    shape = "recent" if recent else classify(question, embed)
    terms = subject_terms(question)
    verb = _lead_act_verb(question)
    if verb:
        #: The instruction is not a subject: "add" in "add milk to my
        #: shopping list" matched "add tomatoes" in a recipe (E12).
        terms = [t for t in terms if t.lower() != verb] or terms
    constraints, terms, source_kind = _plan_constraints(question, terms)
    phrase = _plan_phrase(question, terms)
    span, terms = _plan_window(question, terms, phrase, today)
    kind = _plan_kind(question, utility, shape, bool(span), bool(terms))
    return Plan(
        kind=kind,
        shape=shape,
        terms=terms,
        window=(span[0], min(span[1], today)) if span else None,
        grain=span[2] if span else None,
        window_phrase=phrase if span else "",
        constraints=constraints,
        source_kind=source_kind,
        length=length_wish(question),
        utility=utility,
    )


#: A message this short that names one of the app's own tools ("timer",
#: "countdown", "pomodoro") is a request for the tool as much as a search.
_FEATURE_WORDS = 3
#: Words that make a request polite or pointed without naming anything: "undo
#: the last change" asks for Undo as much as "undo" does (Z64).
_FEATURE_FILLER = frozenset({"the", "a", "an", "my", "that", "this", "it", "last", "latest", "please"})


def _may_name_a_tool(question: str, words: list[str]) -> bool:
    """Short enough, and not a follow-on or a length control ("tell me more",
    "shorter"), which is about the answer before, never a tool: the Follow-up
    trail's help line says "tell me more" in its own words."""
    return bool(words) and len(words) <= _FEATURE_WORDS and not (_MORE.match(question) or length_wish(question))


def _feature_help(question: str, absent: list[str]) -> tuple[str, str] | None:
    """The help line of the app feature a two- or three-word message names
    (the words are the line's own), or None."""
    words = [w for w in re.findall(r"[a-z]+", (question or "").lower()) if w not in _FEATURE_FILLER]
    if not _may_name_a_tool(question or "", words):
        return None
    from tessellate.ai import help_chat

    best = help_line(question, help_chat.topics_for(question or ""))
    if best is None:
        return None
    #: The thing asked for is named in the help line itself: "spare key
    #: where" is a lost key, not the keyboard shortcuts (test_composer_eval_741).
    #: Outside the line's own examples: "who is Sam" is a person, not the
    #: Names tool whose help line quotes "Sam" and "Sam Lee" as its example;
    #: "what about running?" is a follow-up, not the Follow-up trail topic
    #: that gives it in brackets as one.
    line = re.sub(r"\"[^\"]*\"|“[^”]*”|‘[^’]*’|\([^)]*\)", " ", best[0])
    wanted = absent or [w for w in words if len(w) >= 4]
    if not wanted or not all(re.search(rf"\b{re.escape(w)}", line, re.I) for w in wanted):
        return None
    return best


def _feature_instead(question: str, absent: list[str]) -> dict | None:
    """Nothing in the notes, and a two- or three-word message that names an
    app feature (INBOX 1334, "timer\\" got "Which note might it be in?"):
    say the notes are silent on it in one clause, then how to use the feature
    from the Guide's topic. None for anything longer or no topic."""
    best = _feature_help(question, absent)
    if best is None:
        return None
    words = re.findall(r"[a-z]+", (question or "").lower())
    said = absent[0] if absent else " ".join(words)
    #: The feature first: "Nothing in your notes mentions timer" was a
    #: not-found answer to a request for the timer (INBOX 1357, class B).
    lead = f"“{said[:1].upper()}{said[1:]}” is one of the app's own tools, not something in your notes. "
    return _result([("template", lead), ("help", best[0], best[1])], "help")


def offered(result: dict | None, question: str) -> dict | None:
    """A note does mention the word a short message names as a feature
    ("timer" with a Kitchen timer note): the note answers, and the tool is
    offered after it from the same help line (INBOX 1334, the open half).
    The digest and `compose` both answer a chat turn, so both pass through."""
    if not result or result.get("shape") in ("help", None) or result.get("missed") or not result.get("parts"):
        return result
    best = _feature_help(question, [])
    if best is None:
        return result
    more = [("template", PHRASES["feature_offer"]), ("help", best[0], best[1])]
    return {**result, "parts": [*result["parts"], *more], "text": result["text"] + "".join(part[1] for part in more)}


def decap(text: str) -> str:
    """`text` with its first letter lowered for the middle of a sentence,
    unless its first word is a name by its shape: "I", or a capital after
    the first letter ("IaaS", "iPhone", "GPU"). INBOX 1357: a map's items
    were said as "iaaS, paaS and saaS"."""
    first = re.match(r"[A-Za-z][\w'-]*", text or "")
    if first and (first.group(0) in ("I", "I'm", "I've", "I'd", "I'll") or any(c.isupper() for c in first.group(0)[1:])):
        return text
    return text[:1].lower() + text[1:]


def _help_answer(question: str) -> dict | None:
    """A how-to answered by the step sentence of the Help topic it names
    (decision 36's help register): the sentence of the best topic that
    shares the most of the question's words, then where to read the rest.
    None when no topic matches."""
    from tessellate.ai import help_chat

    best = help_line(question, help_chat.topics_for(question or ""))
    if best is None:
        return None
    #: The topic's sentence is the protected span; the pointer after it varies
    #: by chat and turn like any opener (decision 51), so "Ask again" in help
    #: does not repeat itself word for word.
    more = _pick(question, "help_more", [PHRASES[k] for k in ("help_more", *(f"help_more_{n}" for n in range(2, 11)))])
    parts = [("help", best[0], best[1]), ("template", more)]
    return _result(parts, "help")


#: Verbs of one doing, for the help line: a sentence saying "add" answers
#: "how do I make" half as well as one saying "make".
_HELP_DOING: dict[str, frozenset[str]] = {
    word: group - {word}
    for group in (
        frozenset({"make", "create", "add", "new", "set", "start", "type"}),
        frozenset({"delete", "remove", "bin", "trash", "clear"}),
        frozenset({"change", "switch", "pick", "choose", "edit"}),
        frozenset({"find", "search", "look", "open"}),
        frozenset({"stop", "disable", "pause", "off", "hide"}),
        frozenset({"see", "view", "show", "list", "read"}),
    )
    for word in group
}


#: Words that count a quarter: how many, not what ("two notes", "lots").
_HELP_WEAK = frozenset("one two three four five lots many several all every".split())


def _help_verb(question: str) -> str:
    """The doing a how-to asks about, its first word after the asking frame
    ("export" in "how do I export my notes"), or ""."""
    from tessellate.ai import help_chat

    frame = help_chat._HOW_FRAME.match(question or "")
    rest = _words(question[frame.end():]) if frame else []
    return rest[0] if rest else ""


def _help_pairs(question: str) -> set[str]:
    """Adjacent content words of a question, as typed ("back up", "hide
    unlinked"), the asking and counting words left out."""
    typed = re.findall(r"[a-z0-9]+", (question or "").lower())
    content = [bool(_words(w)) and w not in _HELP_WEAK for w in typed]
    return {f"{typed[i]} {typed[i + 1]}" for i in range(len(typed) - 1) if content[i] and content[i + 1]}


def _help_ask(question: str, topic: dict) -> dict:
    """What a question asks of one topic, for scoring its sentences."""
    #: Every word of the question counts here, "note" included: the asking
    #: words that are noise in a notebook ("note") name the control in Help.
    wanted = set(_words(question))
    #: The topic's own name is what every one of its sentences is about, so it
    #: counts half: the verb asked ("make") is what picks the sentence. Unless
    #: the name is the verb asked: "how do I export my notes" in import-export
    #: led with Tidy up duplicates, since "notes" outweighed a halved "export".
    verb = _help_verb(question)
    named = set(_words(str(topic.get("id", "")).replace("-", " "))) - {verb}
    doing = {verb, *_HELP_DOING.get(verb, ())} if verb else set()
    return {"wanted": wanted, "named": named, "pairs": _help_pairs(question), "doing": doing}


def _help_have(line: str, doing: set[str]) -> set[str]:
    """The stems a sentence says. The doing asked in a past form describes, it
    does not instruct: "how do I change the widgets" led with the Dashboard's
    inventory sentence, on "what changed" and "edited" (the owner,
    2026-10-27), over the one that says how ("Edit layout and Widgets")."""
    return {_stem(w) for w in query_understanding.search_terms(line) if not (w.endswith("ed") and any(d.startswith(_stem(w)) for d in doing))}


def _help_one(w: str, h: str) -> bool:
    """A word and its longer form ("remind", "reminder") are one word here."""
    return h == w or (min(len(h), len(w)) >= 5 and (h.startswith(w) or w.startswith(h)))


def _help_shared(line: str, ask: dict) -> float:
    """How much of the question a sentence says: a word each, a weak or topic
    word less, a verb of the same doing ("make" for "set") half a word (INBOX
    787: "how do I make a reminder" led with how the tab is laid out), two
    content words side by side ("back up", "hide unlinked": the control's
    name) half a word more."""
    wanted, named = ask["wanted"], ask["named"]
    have = _help_have(line, ask["doing"])
    hits = sum(0.25 if w in _HELP_WEAK else 0.5 if w in named else 1 for w in wanted if any(_help_one(w, h) for h in have))
    kin = sum(1 for w in wanted if not any(_help_one(w, h) for h in have) and any(_help_one(g, h) for g in _HELP_DOING.get(w, ()) for h in have))
    said = " " + " ".join(re.findall(r"[a-z0-9]+", line.lower())) + " "
    return hits + 0.5 * kin + 0.5 * sum(1 for p in ask["pairs"] if f" {p} " in said)


def _help_best(lines: list[str], ask: dict, doing: float = 0.0) -> str:
    """The line that says the most; a later one must say more to lead (the
    topic opens on its point: "Link one note to another by typing [[" over
    the Suggestions sheet, which says "link" and "notes" too: the Guide's
    gold, 2026-10-11). `doing` is the extra a line earns for saying the verb
    asked, which picks among the clauses of one sentence."""
    def score(line: str) -> float:
        verb = bool(ask["doing"]) and any(_stem(d) in _help_have(line, set()) for d in ask["doing"])
        return _help_shared(line, ask) + (doing if verb else 0.0) - 0.05 * lines.index(line)

    return max(lines, key=lambda line: (score(line), -lines.index(line)))


#: The acts a how-to can name, and the words that say each in a help sentence
#: (the coordinator, 2026-10-31: "how do I export documents?" led with the
#: editor's four views, a sentence that never says export). A question that
#: names an act is answered by the sentence that names it, whichever matched
#: topic holds it.
_HELP_ACTS: dict[str, tuple[str, ...]] = {
    "export": ("export", "download"),
    "import": ("import", "bring"),
    "print": ("print", "pdf"),
    "share": ("share", "publish", "send"),
    "delete": ("delete", "remove", "trash", "bin"),
    "restore": ("restore", "recover", "undelete"),
    "move": ("move", "drag", "reorder"),
    "rename": ("rename", "retitle"),
    "attach": ("attach", "upload"),
    "pin": ("pin", "unpin", "star", "favourite", "favorite"),
}


@functools.lru_cache(maxsize=1)
def _help_act_stems() -> dict[str, frozenset[str]]:
    """The acts' stems, built on first use: `_stem` reads the spelling pairs
    (about 0.4 s to build), which the cold import is budgeted not to pay
    (tests/test_engine_budgets.py)."""
    return {act: frozenset(_stem(w) for w in words) for act, words in _HELP_ACTS.items()}


def _help_act(question: str) -> str:
    """The act a how-to names (the first one typed), or ""."""
    for word in re.findall(r"[a-z]+", (question or "").lower()):
        stem = _stem(word)
        for act, stems in _help_act_stems().items():
            if stem in stems:
                return act
    return ""


def _act_score(line: str, at: int, ask: set, stems: set[str], topic: dict, place: tuple[int, int]) -> float:
    """How well `line` leads for an act named at word `at`: shared words with
    the question, an early act word (a sentence that opens on the act is about
    it; one that mentions it in passing is not), the topic named for the act
    ("import-export"), a wall of a sentence being a poor lead, and a little
    for coming first (`place` is the topic's and the line's order)."""
    named = 2.0 if stems & {_stem(w) for w in str(topic.get("id", "")).split("-")} else 0.0
    early = 1.5 if at < 5 else 0.75 if at < 12 else 0.0
    long = 1.0 if len(line.split()) > _HELP_LEAD_WORDS else 0.0
    return _help_shared(line, ask) + named + early - long - 0.15 * place[0] - 0.05 * place[1]


def _act_lead(lead: str, stems: set[str], question: str, topic_id: str) -> str:
    """A long act sentence cut to its clause that names the act."""
    if len(lead.split()) <= _HELP_LEAD_WORDS:
        return lead
    clauses = [c for c in _clauses(lead) if stems & {_stem(w) for w in re.findall(r"[a-z]+", c.lower())}]
    return max(clauses, key=lambda c: _help_shared(c, _help_ask(question, {"id": topic_id}))) if clauses else lead


def _act_sentence(question: str, topics: list[dict], act: str) -> tuple[str, str] | None:
    """The sentence naming `act` that says the most of the question, over every
    matched topic (the first earns a little for coming first), with its
    topic's id; None when no matched topic names the act."""
    from tessellate.ai import help_chat

    stems = _help_act_stems()[act]
    best: tuple[float, str, str] | None = None
    for order, topic in enumerate(topics):
        ask = _help_ask(question, topic)
        for index, line in enumerate(help_chat.help_sentences(str(topic.get("body") or ""))):
            words = [_stem(w) for w in re.findall(r"[a-z]+", line.lower())]
            at = next((i for i, w in enumerate(words) if w in stems), None)
            if at is None:
                continue
            score = _act_score(line, at, ask, stems, topic, (order, index))
            if best is None or score > best[0]:
                best = (score, line, str(topic.get("id", "")))
    return None if best is None else (_act_lead(best[1], stems, question, best[2]), best[2])


def help_line(question: str, topics: list[dict]) -> tuple[str, str] | None:
    """The one sentence of the best topic that answers a how-to (its step
    sentence sharing the most of the question's words) and the topic's id:
    Chat's help register and the Guide's first line (decision 59, step 4),
    so help and chat say it in one voice. None with no topic."""
    if not topics:
        return None
    act = _help_act(question)
    named = _act_sentence(question, topics, act) if act else None
    if named is not None:
        return named
    topic = topics[0]
    from tessellate.ai import help_chat

    sentences = help_chat.help_sentences(str(topic.get("body") or ""))
    if not sentences:
        return None
    ask = _help_ask(question, topic)
    lead = _help_best(sentences, ask)
    #: A lead is a line, not an inventory (INBOX 1406: "how do I see what
    #: changed" got a 134-word sentence): over the budget, its best clause.
    if len(lead.split()) > _HELP_LEAD_WORDS:
        clauses = _clauses(lead)
        if len(clauses) > 1:
            lead = _help_best(clauses, ask, doing=0.5)
    return lead, str(topic.get("id", ""))


#: The longest sentence the Guide and Chat lead with whole.
_HELP_LEAD_WORDS = 40


def _semicolon_parts(sentence: str) -> list[str]:
    """A sentence cut at its `;` outside brackets and quotes."""
    parts, depth, quote, start = [], 0, False, 0
    for i, ch in enumerate(sentence):
        depth = max(0, depth + (ch in "([") - (ch in ")]"))
        quote ^= ch in "\"“”"
        if ch == ";" and not depth and not quote:
            parts.append(sentence[start:i])
            start = i + 1
    return [*parts, sentence[start:]]


def _clauses(sentence: str) -> list[str]:
    """A sentence's `;` clauses outside brackets and quotes, each a sentence
    of its own (capital first, its stop kept): "(a busy week; Tidy lists
    them)" is one thought, not two. One too short to answer alone belongs to
    the clause before."""
    out: list[str] = []
    for part in (p.strip() for p in _semicolon_parts(sentence)):
        if len(part.split()) < 5 and out:
            out[-1] += "; " + part
        elif part:
            out.append(part)
    ended = [c if c.endswith((".", "!", "?", "。", "！", "？")) else c + "." for c in out]
    return [c[:1].upper() + c[1:] for c in ended]


_JA_STOP = re.compile(r"([。！？])\.")


def _result(parts: list[tuple], shape: str, rows: list[dict] | None = None, next_parts: list | None = None) -> dict:
    """A composed result from its parts: the text is their join."""
    rows = rows or []
    quotes = "\n\n".join(row["sentence"] for row in rows)
    next_parts = next_parts or []
    return {
        #: A full-width stop already ends a sentence: no ASCII one follows it (audit 1031 C38).
        "text": _JA_STOP.sub(r"\1", "".join(part[1] for part in parts)),
        "grounding": rows,
        "support": grounding.support(quotes, rows),
        "shape": shape,
        "parts": parts,
        "next": ["".join(part[1] for part in chip) for chip in next_parts],
        "next_parts": next_parts,
    }


def _utility(question: str, now: datetime | None, salt: str) -> dict | None:
    """A utility's answer (decision 41): computed sentences, or a fixed line
    for what the app cannot do (the weather, translating with no model)."""
    found = utilities.answer(question, now, salt)
    if not found:
        return None
    parts = [("template", PHRASES[text]) if kind == "phrase" else (kind, text) for kind, text in found]
    return _result(parts, "utility")


def _in_window(view: NoteView, window: tuple, *, mentions: bool = True) -> bool:
    """Written in the window, or (E6) saying the day: a note that reads "3
    November at 2pm" or "Friday deadlift" is on that day for a question about
    the day, whenever it was written. `mentions=False` is a question about
    writing ("what did I write on Friday"), which only creation answers."""
    if mentions and view.note.get("dated_in_window"):
        return True
    return view.written is not None and window[0] <= view.written <= window[1]


#: A recall by time lists at most this many notes; the count says how many.
RECALL_NOTES = 8


#: A question about the act of writing: only the day a note was made answers it.
_WROTE_VERB = re.compile(r"\b(?:wrote|write|written|made|created|added|saved|captured|jotted|typed)\b", re.I)


def _recall(out: _Answer, p: Plan, views: list[NoteView], question: str) -> None:
    """Recall by time (decision 31's schema): the notes in the window, newest
    first, grouped by day, under the count; "nothing from then" when none."""
    wrote = bool(_WROTE_VERB.search(question or ""))
    #: A board or a mind map is made, not written: it is no "note" in the count.
    inside = sorted(
        (v for v in views if _in_window(v, p.window, mentions=not wrote) and str(v.note.get("kind") or "note") not in ("board", "map")),
        key=lambda v: (v.written, -v.rank), reverse=True,
    )
    said = window_said(_as_typed(p.window_phrase, question))
    if not inside:
        out.t("recall_none").asked(said).t("stop")
        return
    out.t("recall_a").m(out.count(len(inside))).t("recall_note" if len(inside) == 1 else "recall_notes").asked(said)
    out.t("recall_b" if len(inside) > 1 else "end_colon")
    for view in inside[:RECALL_NOTES]:
        out.t("line", "bullet")
        if view.titled:
            out.name(view).dated(view)
        else:
            out.t("list_from").m(out.day(view.written))
        #: A picture's note as what it shows and its words; a note's
        #: heading with the sentence after it (INBOX 787).
        units = _overview().best_line(view.sentences, set()) or _label_line(view)
        if not units:
            out.t("stop")
            continue
        out.t("colon")
        _overview_line(out, units, set())
    if len(inside) > RECALL_NOTES:
        out.t("para", "recall_more_a").m(out.count(len(inside) - RECALL_NOTES)).t("recall_more_b")


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
_PERSON = re.compile(r"^[A-Z][\w'-]+$")


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
    _overview_rest(out, len(found) - shown)
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
    out.t("ov_lead_a").m(out.count(len(found))).t("ov_lead_b").asked(said)
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
        if i or not first:
            out.t("line")
        out.t("bullet")
        if view.written and asks_time(getattr(out, "question", "")):
            day = out.day(view.written)
            out.m(day[:1].upper() + day[1:]).t("colon")
        elif view.titled or not view.written:
            #: The card carries the day (INBOX 1441): a titled note is named.
            out.name(view, cap=True).t("colon")
        _overview_line(out, _overview().best_line(view.sentences, stems, text_stems), stems)
    return len(views)


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


def _filtered(views: list[NoteView], p: Plan) -> tuple[list[NoteView], tuple | None]:
    """The notes the plan's constraints keep, and, when a constraint keeps
    none, which one (to say so rather than answer from the others)."""
    tags = p.constraints.get("tags")
    if tags:
        kept = [v for v in views if {str(t).lower() for t in v.note.get("tags") or []} & set(tags)]
        if not kept:
            return [], ("none_tagged", tags[0])
        views = kept
    kind = p.source_kind
    if kind and kind != "picture":
        kept = [v for v in views if str(v.note.get("kind") or "note") == kind]
        if kept:
            views = kept
    return views, None


def _did_you_mean(unsure: list[dict]) -> list[list[tuple]]:
    """One "Did you mean “how”?" chip for the first unsure reading: pressing
    it asks the question again with that word (`follow_on`)."""
    if not unsure:
        return []
    return [[("template", PHRASES["did_you_mean_a"]), ("corrected", unsure[0]["alternative"]), ("template", PHRASES["did_you_mean_b"])]]


def _as_phrase(absent: list[str], question: str) -> list[str]:
    """Words side by side in the question said as the one phrase they are:
    “quantum chromodynamics”, not “quantum” or “chromodynamics” (INBOX
    1357, class H)."""
    if len(absent) > 1:
        joined = " ".join(absent)
        if joined.lower() in " ".join(re.findall(r"[\w'-]+", (question or "").lower())):
            return [joined]
    return absent


def _absent(terms: list[str], views: list[NoteView]) -> list[str]:
    """The question's words no note found holds, when that is all of them:
    what a no-answer can name ("No note found mentions “gym”.")."""
    found: set[str] = set()
    for view in views:
        found |= view.words | view.title_words | view.filed_words
    absent = [t for t in terms if len(t) >= _MISSING_MIN and not _holds(_stem(t), found)]
    return absent if terms and len(absent) == len(terms) else []


def window_said(phrase: str) -> str:
    """A time window as an adverbial, with the preposition it needs ("on 20
    October", "in the last 7 days"; "last week" and "today" as they are):
    `recognise.adverbial`, the one reader of it; said with its capitals (audit
    1030 Z45)."""
    return rec.proper_days(rec.adverbial(phrase))


def _as_typed(word: str, question: str) -> str:
    """`word` as the question spelled it: "Sam", not the lowered "sam"."""
    found = re.search(rf"\b{re.escape(word)}\b", question or "", re.I)
    return found.group(0) if found else word


def _bare_title(out: _Answer, terms: list[str], views: list[NoteView]) -> NoteView | None:
    """A note that is only a title ("Work", "Gym") asked about by that name
    has no sentence to quote, so the answer used to be "your notes don't
    cover that" beside a note that plainly is it. Say what it is instead."""
    stems = {_stem(t) for t in terms}
    if not stems:
        return None
    for v in views:
        if v.sentences or not v.title:
            continue
        named = v.title_words | v.filed_words | v.words
        if all(_holds(stem, named) for stem in stems):
            out.t("bare_a", "open_quote").asked(v.title).t("close_quote", "bare_b")
            return v
    return None


#: A window asked about that holds no note ("what did I write last month" in
#: a notebook begun this week): said as that, with where the notes are, never
#: "I couldn't find any saved notes matching that question" (O1, measured
#: 2026-10-17 on the Guide's own suggested asks).
_EMPTY_WINDOW = {
    "natural": (
        "You wrote nothing {when}.",
        "Nothing went into your notes {when}.",
        "No notes were written {when}.",
        "I can't find a note written {when}.",
        "{When}, you wrote nothing down.",
        "There's nothing written {when}.",
        "Your notebook has nothing {when}.",
        "Nothing turns up {when}.",
    ),
    "professional": (
        "No notes were recorded {when}.",
        "There are no entries {when}.",
        "The notebook holds nothing {when}.",
        "Nothing was recorded {when}.",
        "{When}, nothing was recorded.",
        "No records exist {when}.",
        "The notes contain nothing written {when}.",
        "Nothing was entered {when}.",
    ),
}
_EMPTY_WINDOW_SPAN = {
    "natural": (
        "Your notes run from {first} to {last}.",
        "Your earliest note is from {first}.",
        "Everything you have is from {first} on.",
        "Your notebook starts on {first}.",
    ),
    "professional": (
        "The notes span {first} to {last}.",
        "The earliest entry is dated {first}.",
        "Entries begin on {first}.",
        "The notebook begins on {first}.",
    ),
}
#: The terse and playful chat voices say the same two things their own way
#: (composer8): a persona that asks for either is heard on an empty window too.
_EMPTY_WINDOW["terse"] = (
    "Nothing {when}.", "No notes {when}.", "Empty {when}.", "{When}: nothing.", "Nothing written {when}.", "No entries {when}.", "Blank {when}.", "{When}: no notes.",
)
_EMPTY_WINDOW["playful"] = (
    "Not a word written {when}.", "{When}, the pages stayed blank.", "The notebook was quiet {when}.", "Crickets {when}.",
    "Nothing in the notebook {when}, not even a doodle.", "{When} left no ink behind.", "The pages are bare {when}.", "No scribbles {when}.",
)
_EMPTY_WINDOW_SPAN["terse"] = ("Notes run {first} to {last}.", "Earliest: {first}.", "Starts {first}.", "From {first}.")
_EMPTY_WINDOW_SPAN["playful"] = (
    "The ink starts on {first} and ends on {last}.", "Your first page is dated {first}.", "The notebook begins on {first}, so look there.", "Everything starts on {first}.",
)
_EMPTY_WINDOW_ONE = {
    "natural": "All your notes are from {first}.", "professional": "Every entry is dated {first}.",
    "terse": "All from {first}.", "playful": "Every page is from {first}.",
}


#: A window past the newest note (today, this week) is answered with the
#: newest note, not with where the notebook starts (audit 1029 C12).
_EMPTY_WINDOW_NEWEST = {
    "natural": ("Your newest note is from {last}.", "The last thing you wrote was {last}."),
    "professional": ("The newest entry is dated {last}.", "The latest entry is from {last}."),
    "terse": ("Newest: {last}.", "Last: {last}."),
    "playful": ("Your latest page is from {last}.", "The ink last dried {last}."),
}


def empty_window(when: str, first: date | None, last: date | None, *, voice: str = "natural", seed: str = "",
                 today: date | None = None, register: str = "", window: tuple | None = None) -> str:
    """A time window with no note in it, said as that, and where the notes
    are (`first` and `last` written days; None for an empty notebook).
    `register` is the chat's own voice (a persona's cue included); `window`
    is the days asked, so one that starts after the newest note is answered
    with that note."""
    voice = "professional" if composer_tables.voice_of(voice) == "professional" else "natural"
    if register:
        voice = {"warm": "natural", "formal": "professional"}.get(composer_compose.voice_for(register), composer_compose.voice_for(register))
    today = today or user_today()
    when = window_said(when)
    lead = _pick(seed or when, "empty_window", list(_EMPTY_WINDOW[voice])).format(when=when, When=when[:1].upper() + when[1:])
    if first is None or last is None:
        return lead

    def day(d: date) -> str:
        return f"{d.day} {d:%B}" if d.year == today.year else f"{d.day} {d:%B %Y}"

    if window and window[0] > last:
        ago = (today - last).days
        said = "yesterday" if ago == 1 else day(last)
        newest = _pick(seed or when, "empty_window_newest", list(_EMPTY_WINDOW_NEWEST.get(voice, _EMPTY_WINDOW_NEWEST["natural"])))
        return f"{lead} {newest.format(last=said)}"
    if first == last:
        span = _EMPTY_WINDOW_ONE[voice].format(first=day(first))
    else:
        span = _pick(seed or when, "empty_window_span", list(_EMPTY_WINDOW_SPAN[voice])).format(first=day(first), last=day(last))
    return f"{lead} {span}"


def _nothing(
    shape: str,
    unsure: list[dict] | None = None,
    voice: str = composer_tables.DEFAULT_VOICE,
    absent: list[str] | None = None,
    out: _Answer | None = None,
) -> dict:
    """No answer, said plainly and asked back, in one of eight wordings or
    more a voice: never one the last three answers opened with (`out`)."""
    chips = _did_you_mean(unsure or [])
    if out is None:
        out = _Answer({}, user_today())
        out.voice = composer_tables.voice_of(voice)
    parts: list[tuple] = [("template", PHRASES[out.voiced("nothing")])]
    if _REGISTER.get():
        parts = _nothing_parts(out, _REGISTER.get(), absent or [])
    elif absent:
        #: Measured over the notes found: the words asked about that none of
        #: them holds, said before the question back.
        parts = [("template", PHRASES[out.voiced("none_found")])]
        for i, word in enumerate(absent[:3]):
            if i:
                parts.append(("template", PHRASES["or"]))
            parts += [("template", PHRASES["open_quote"]), ("asked", word), ("template", PHRASES["close_quote"])]
        parts += [("template", PHRASES["stop"]), ("template", PHRASES["space"]), ("template", PHRASES[out.voiced("nothing_ask")])]
    return {
        "text": "".join(part[1] for part in parts),
        "grounding": [],
        "support": grounding.support("", []),
        "shape": shape,
        "parts": parts,
        "next": ["".join(part[1] for part in chip) for chip in chips],
        "next_parts": chips,
        #: No answer in the notes: `compose` may give the app's help instead.
        "missed": True,
    }


def _nothing_parts(out: "_Answer", register: str, absent: list[str]) -> list[tuple]:
    """The no-answer composed in the chat's voice and mood (composer8): a
    head and a tail, or, naming the words no note holds, a lead, those words
    and a tail; never the opening one of the last answers used."""
    seen = [x for x in (*(out.recent or []), out.previous) if x]
    mood = composer_compose.mood_of(out.question, voice=register, seed=f"{_SESSION.get()}|{out.question}", said=seen)
    if not absent:
        text = composer_compose.pick(composer_compose.surfaces("social_nothing"), "nothing", mood)
        return [("template", text.text if text else PHRASES[out.voiced("nothing")])]
    lead = composer_compose.pick(composer_lines.NONE_FOUND_LEADS, "none_found", mood)
    tail = composer_compose.pick(composer_lines.SOCIAL_TAILS["nothing"], "nothing_ask", mood)
    parts: list[tuple] = [("template", lead.text if lead else PHRASES[out.voiced("none_found")])]
    for i, word in enumerate(absent[:3]):
        if i:
            parts.append(("template", PHRASES["or"]))
        parts += [("template", PHRASES["open_quote"]), ("asked", word), ("template", PHRASES["close_quote"])]
    parts += [("template", PHRASES["stop"]), ("template", PHRASES["space"]), ("template", tail.text if tail else PHRASES[out.voiced("nothing_ask")])]
    return parts


def compose(
    question: str,
    notes: list[dict],
    *,
    today: date | None = None,
    recent: bool = False,
    embed=None,  # noqa: ANN001
    said: str = "",
    previous: str = "",
    voice: str = composer_tables.DEFAULT_VOICE,
    now: datetime | None = None,
    salt: str = "",
    turn: int | None = None,
    dialogue: Dialogue | None = None,
    prefer: str = "",
    resolved: bool = False,
    learned=None,  # noqa: ANN001
    register: str = "",
) -> dict:
    """`{"text", "grounding", "support", "shape", "parts", "next", "next_parts"}`
    for one question.

    `notes` are the route's retrieved notes, ranked (each with `id`,
    `content`, and `written` or `created_at`). `recent` is the retrieval's
    "newest notes" mode: a question with a time and no subject. `embed`, when
    given, is the embedder's `embed_many` (texts in, vectors out): meaning is
    then measured by cosine, and without it by shared words. `said` is the
    earlier answer a "tell me more" follows (`follow_on`): what it quoted is
    left out. `previous` is the answer the turn before gave: this one does
    not open with the same words. `voice` is the register the connecting
    words are written in, "natural" or "professional" (the `composer_voice`
    preference); the notes' own sentences are quoted the same in both.

    In a conversation (CHAT_PLAN decisions 34 and 35): `turn` and `salt` (the
    chat's) choose the openers and joins, so "Ask again" is worded anew while
    the lead sentence stays; `dialogue` reads a terse turn against the ones
    before, keeps "tell me more" from quoting a sentence twice, and records
    this turn (`resolved`: the caller already read the follow-on); `prefer`
    is a correction's words ("no, the gym one"), whose notes come first.
    """
    if voice == "help":
        helped = _help_result(question, salt=salt, turn=turn, dialogue=dialogue, previous=previous)
        if helped:
            return helped
        voice = composer_tables.DEFAULT_VOICE
    #: In a conversation (decision 34, 35): the turn and the chat's salt
    #: choose the wording, and a terse turn is read against the ones before.
    asked = question
    if dialogue is not None:
        question, salt, turn, said, prefer, previous = _read_in_dialogue(
            question, dialogue, salt=salt, turn=turn, said=said, prefer=prefer, previous=previous, resolved=resolved
        )
    token = _SESSION.set(f"{salt}:{turn}" if (salt or turn) else "")
    registered = _REGISTER.set(register)
    #: `learned`: what the person said of insights (`insights.memory`).
    known = _LEARNED.set(learned)
    words = _note_words(notes)
    owned = _KNOWN.set(words)
    current = _ASKS_NOW.set(bool(_NOW_WORDS.search(question)))
    try:
        result = _answer_turn(question, notes, today=today, recent=recent, embed=embed, said=said, previous=previous,
                              voice=voice, now=now, salt=salt, turn=turn, dialogue=dialogue, prefer=prefer)
        result = offered(result, asked)
        result = _acknowledged(result, asked, voice=composer_tables.voice_of(voice), seed=f"{asked.strip().lower()}:{salt}:{turn}",
                               history=dialogue.history if dialogue is not None else [{"answer": previous}], previous=previous, known=words)
    finally:
        _SESSION.reset(token)
        _REGISTER.reset(registered)
        _LEARNED.reset(known)
        _KNOWN.reset(owned)
        _ASKS_NOW.reset(current)
    #: A how-to the notes have nothing on that plainly names the app ("how do
    #: I connect a model") is the help register's (O1): it was answered 'No
    #: note I found says anything about "connect" or "model"'.
    if result.get("missed") and _names_app(asked):
        helped = _help_result(asked, salt=salt, turn=turn, dialogue=None, previous=previous)
        if helped:
            result = helped
    if dialogue is not None:
        dialogue.record(asked, result)
    return result


def _names_app(question: str) -> bool:
    from tessellate.ai import help_chat

    return help_chat.names_app(question)


def _help_result(question: str, *, salt: str, turn: int | None, dialogue: Dialogue | None, previous: str) -> dict | None:
    """The help register (decision 36): a how-to answered from the app's own
    Help, the Guide's topics, so the Guide and Chat are one engine."""
    session = _SESSION.set(f"{salt or (dialogue.salt if dialogue else '')}:{turn}" if (salt or turn or dialogue) else "")
    try:
        helped = _help_answer(question)
    finally:
        _SESSION.reset(session)
    if not helped:
        return None
    return _acknowledged(helped, question, voice=composer_tables.DEFAULT_VOICE, seed=f"{question.strip().lower()}:{salt}:{turn}",
                         history=dialogue.history if dialogue else [{"answer": previous}], previous=previous)


def _read_in_dialogue(question: str, dialogue: Dialogue, *, salt: str, turn: int | None, said: str, prefer: str,
                      previous: str, resolved: bool) -> tuple:
    """`(question, salt, turn, said, prefer, previous)` once a terse turn is
    read against the ones before it."""
    salt = salt or dialogue.salt
    turn = turn if turn is not None else dialogue.turns + 1
    follow = follow_on(question, dialogue.history) if dialogue.history and not resolved else None
    if follow:
        question = follow.question
        prefer = prefer or follow.prefer
        if follow.kind == "more":
            said = "\n".join([said, *dialogue.quoted]).strip()
        if follow.kind == "correction":
            dialogue.corrections.append(follow.prefer)
    previous = previous or (dialogue.history[-1]["answer"] if dialogue.history else "")
    return question, salt, turn, said, prefer, previous


def _note_words(notes: list[dict]) -> frozenset:
    """The words of the notes the question is asked of, lower case."""
    found: set[str] = set()
    for note in notes or []:
        found.update(re.findall(r"[a-z]{3,}", f"{note.get('title') or ''} {note.get('content') or ''}".lower()))
    return frozenset(found)


def _acknowledged(result: dict, asked: str, *, voice: str, seed: str, history: list[dict], previous: str = "",
                  known: frozenset = frozenset()) -> dict:
    """The answer, opened by how the question was read when it had a
    misspelling put right (Brief 90: "hwo do I" read as "how do I"). The
    wording varies (`composer_ack`): not the answer before's, not the last
    acknowledgement made. A question that needed no repair, and a slang word
    spelled out, are not acknowledged."""
    if not result or not result.get("parts") or not (asked or "").strip():
        return result
    fixed: list[tuple[str, str]] = []
    tidy = question_noise.tidy(" ".join(asked.split()))
    repaired = question_noise.repair(tidy, fixed=fixed, known=known)
    #: A worked answer says the reading the utility used, which may be a
    #: router's reading rather than the speller's: "what tmie is it in jaan"
    #: was answered for Tokyo under "I took that to mean 'what the is it in
    #: jan'" (O3).
    if result.get("shape") == "utility" or utilities.kind_of(tidy) not in (None, "until_note"):
        heard = utilities._heard(tidy)
        fixed = [(a, b) for a, b in zip(tidy.split(), heard.split()) if a != b] if heard != tidy else []
        repaired = heard
    if not fixed:
        return result
    parts = [*composer_ack.acknowledge(repaired, voice=voice, seed=seed, history=history, previous=previous), *result["parts"]]
    return {**result, "parts": parts, "text": "".join(part[1] for part in parts)}


def _answer_turn(question: str, notes: list[dict], **kwargs) -> dict:
    """A topic asked about as a whole is an overview (INBOX 787); anything
    else, or a topic with one note about it, is `_compose`'s. A question
    about a link is the link table's (audit 1031 C49)."""
    linked = [] if kwargs["said"] else composer_links.answer_parts(question, notes)
    if linked:
        return {**_result(linked, "none"), "answered": True}
    return _overview_answer(
        question, notes, today=kwargs["today"] or user_today(), voice=kwargs["voice"], said=kwargs["said"],
        prefer=kwargs["prefer"], dialogue=kwargs["dialogue"],
    ) or _compose(question, notes, **kwargs)


def _from_dialogue(out: "_Answer", dialogue) -> None:  # noqa: ANN001  # a Dialogue or None
    """What the conversation gives the answer: the sentences already said,
    and the last answers, so a reply opens unlike them."""
    if dialogue is None:
        return
    out.used = set(dialogue.used)
    out.recent = [str(turn.get("answer") or "").lstrip() for turn in (dialogue.history or [])[-phrasing.RECENT :]]


def _checklist_or_until(out: "_Answer", said: object, question: str, views: list, today: date) -> dict | None:
    """What is still open on a checklist, or the days until a note's day,
    when the question asks that and nothing was said before; else None.
    Read as repaired: "hw many days til the dentst" is the same count."""
    if said:
        return None
    if _still_open(out, question, views):
        return {**_result(out.parts, "list", out.rows), "answered": not out.rows}
    until = question_noise.repair(question_noise.tidy(" ".join((question or "").split())))
    if utilities.kind_of(until) == "until_note" and _until_note(out, until, views, today):
        return _result(out.parts, "when", out.rows)
    return None


def _early_answer(question: str, notes: list[dict], *, said: str, recent: bool, today: date, embed, voice: str, salt: str, turn: int | None, now: datetime | None) -> dict | None:  # noqa: ANN001
    """The answers that need no notes read: a worked sum, or a question of
    several parts answered part by part."""
    #: A sum is answered whatever retrieval did: the route hands "what is
    #: 12 * 7" the newest notes when nothing matches, and those used to be
    #: listed instead of the 84 (engine probe P3).
    if said:
        return None
    worked = _utility(question, now or datetime.combine(today, user_now().time()), salt)
    if worked:
        return worked
    parts = split_parts(question) if not recent else []
    if len(parts) > 1:
        return _multi(question, parts, notes, today=today, embed=embed, voice=voice, salt=salt, turn=turn) or None
    return None


#: The words that start an act on a note, and the act (`act_registry`).
_ACT_VERBS = {
    "rename": "rename", "retitle": "rename", "tag": "tag", "label": "tag", "untag": "untag", "pin": "pin", "unpin": "unpin",
    "star": "pin", "unstar": "unpin", "delete": "delete", "remove": "delete", "bin": "delete", "trash": "delete",
    "erase": "delete", "discard": "delete", "link": "link", "unlink": "unlink", "connect": "link", "add": "append",
    "append": "append", "move": "move", "file": "move",
}
_ACT_LEADS = ("please ", "pls ", "can you ", "could you ", "would you ", "will you ", "i want to ", "i'd like to ", "i would like to ", "just ", "ok ", "okay ", "hey ")


def _lead_act_verb(question: str) -> str | None:
    """The act verb a command opens with ("please rename ..."), or None for a
    question or any other sentence."""
    text = " ".join((question or "").lower().split()).strip(" .!?")
    changed = True
    while changed:
        changed = False
        for lead in _ACT_LEADS:
            if text.startswith(lead):
                text, changed = text[len(lead):], True
    first, _, rest = text.partition(" ")
    if first not in _ACT_VERBS or not rest or len(text.split()) > 14:
        return None
    #: "add up the budget" is a sum, not a line to add to a note.
    return None if first == "add" and rest.split()[0] in ("up", "together") else first


def _unfinished_act(question: str, now: datetime) -> dict | None:
    """A command that starts like an act on a note but names no note or no
    change ("rename my gym log", "tag my gym log"), which the acts could not
    read: said with the way to say it, never answered by quoting whichever note
    shares a word with it (E12: "rename my gym log" quoted the gym note and
    called "rename" a word no note mentions)."""
    first = _lead_act_verb(question)
    if first is None:
        return None
    from tessellate.ai import act_registry

    if act_registry.READER is None or act_registry.READER(question, now) is not None:
        return None
    act = act_registry.ACTS.get(_ACT_VERBS[first])
    if act is None:
        return None
    line = f"I could not tell which note to {first}, or what to change. To {act.label[0].lower() + act.label[1:]}, say it like this: {act.example}."
    return {**_result([("template", line)], "none"), "answered": True}


_UNTICK = re.compile(r"^(?:please |can you |could you )?(?:un-?tick|un-?check|un-?mark|un-?cross)\b", re.I)


def _cannot_untick(question: str) -> dict | None:
    """"Untick bread": a tick is undone in the note, not by a sentence, and
    the answer says so rather than quoting the list with a word no note
    mentions (audit 1030 Z37)."""
    if not _UNTICK.match(" ".join((question or "").split())):
        return None
    line = "I can tick items off, but I cannot untick one yet. Open the note and clear the box."
    return {**_result([("template", line)], "none"), "answered": True}


def _note_views(notes: list[dict]) -> list:
    return [v for v in (read_note(n, i) for i, n in enumerate(_distinct_ids(notes or []))) if v]


def _correction_order(notes: list[dict], prefer: str, dialogue: Dialogue | None) -> list[dict]:
    """A correction ("no, the gym one"): the notes it names first, the ones the
    answer before quoted last (decision 35)."""
    wanted = {_stem(w) for w in _words(prefer)}
    quoted = dialogue.quoted_ids if dialogue is not None else set()
    return sorted(
        notes or [],
        key=lambda n: (not (wanted & set(_words(str(n.get("content") or "")))), n.get("id") in quoted),
    )


def _steer_to_correction(p, prefer: str, notes: list[dict]) -> None:  # noqa: ANN001
    #: A note the correction names that is not among these notes (a later
    #: turn's search found others) orders nothing and asks for nothing: its
    #: words would only make the answer "Nothing I found mentions" them.
    if prefer and any({_stem(w) for w in _words(prefer)} & set(_words(str(n.get("content") or ""))) for n in notes or []):
        p.window, p.kind = None, (p.kind if p.kind != "recall" else "fact")
        p.terms = list(dict.fromkeys([*p.terms, *_words(prefer)]))


def _meaning_maker(shape: str, views_list: list, embed):  # noqa: ANN001, ANN202
    def meaning_for(side_terms: list[str]) -> _Meaning:
        pool = sorted(_score(shape, side_terms, views_list), key=lambda s: (-s.score, s.rank, s.order))[:MEANING_POOL]
        return _Meaning(pool, embed, {_stem(t) for t in side_terms})

    return meaning_for


def _window_gate(out: "_Answer", p, said: str, question: str, shape: str, views_list: list) -> tuple:  # noqa: ANN001
    """A result when the question's window decides the answer, else the views
    narrowed to the window."""
    if p.kind == "recall" and p.window and not said:
        _recall(out, p, views_list, question)
        return _result(out.parts, "recall", out.rows, _recall_next(p.window, views_list)), views_list
    if p.window and not said and views_list and not any(_in_window(v, p.window) for v in views_list):
        #: A window no note found falls in: said, never answered from notes
        #: written at another time.
        out.t("recall_none").asked(window_said(_as_typed(p.window_phrase, question))).t("stop")
        return _result(out.parts, shape), views_list
    if p.window and not said:
        views_list = [v for v in views_list if _in_window(v, p.window)]
        out.views = {v.id: v for v in views_list}
    return None, views_list


def _best_dated_title(stems: set, views_list: list):  # noqa: ANN202
    """The dated note whose name holds every stem, the better-ranked on a tie;
    None when no note's name holds them all."""
    best, hits = None, 0
    for view in views_list:
        if view.written is None or not view.titled:
            continue
        held = sum(1 for t in stems if _holds(t, view.title_words | view.filed_words))
        if held > hits or (held == hits and held and best is not None and view.rank < best.rank):
            best, hits = view, held
    return best if best is not None and hits >= len(stems) else None


def _written_when(out: "_Answer", question: str, p, views_list: list):  # noqa: ANN001
    """The day a named note was written, from its own date (E6: "when was my
    gym log written" quoted a lift). None unless the question is that shape and
    one note's name holds what it names."""
    if p.window or not asks_written_when(question) or not p.terms:
        return None
    stems = {_stem(t) for t in p.terms if t.lower() not in _WHEN_NOISE}
    if not stems:
        return None
    best = _best_dated_title(stems, views_list)
    if best is None:
        return None
    when = best.written
    out.name(best, cap=True).t("written_on").m(f"{when:%A} {when.day} {when:%B}" + (f" {when.year}" if when.year != out.today.year else "")).t("stop")
    return {**_result(out.parts, "when", []), "answered": True}


_DAY_WORD = rec.WEEKDAY_WORD


def _day_terms(p, views_list: list) -> list[str]:  # noqa: ANN001
    """The words a note uses for the one day asked about: the weekday's name,
    else the month's, when some note here was found by mentioning that day."""
    if not p.window or p.window[0] != p.window[1] or not any(v.note.get("dated_in_window") for v in views_list):
        return []
    named = _DAY_WORD.search(p.window_phrase or "")
    return [named.group(1).lower()] if named else [p.window[0].strftime("%B").lower()]


def _write_body(out: "_Answer", p, shape: str, chosen: list, terms: list, question: str, meaning, broad: bool, views_list: list) -> None:  # noqa: ANN001
    pair = _disagreement(chosen)
    if _confirmed_lead(out, question, terms):
        pass
    elif p.kind == "insight" and _insight_lead(out, question, terms, views_list):
        broad = True
    out.broad = broad
    lead = _body(out, shape, chosen, terms, question, meaning, broad, {s.key for s in pair} if pair else set())
    if pair:
        _disagreements(out, pair, lead, terms)
    elif not broad:
        _clarify(out, shape, terms, lead, meaning, views_list)
    _readings(out, question, terms, views_list)
    if broad and p.kind != "insight":
        _insight_close(out, question, terms, views_list)
    _missing(out, terms, views_list)


def _is_broad(shape: str, question: str) -> bool:
    """Whether the question asks for a spread across notes, not one fact."""
    return shape == "what" and bool(_BROAD.match(question) or _BROAD.match(rephrase(question)))


def _by_the_day(p, shape: str, terms: list, views_list: list, said: str) -> tuple[list, list]:  # noqa: ANN001
    """The sentences that say the day the question anchors on, with the day
    as the terms when they answer; nothing and the terms as they were if not."""
    #: The day was the anchor and the note says it ("Friday deadlift 100kg"
    #: for "how much did I lift on friday"): the sentences that say the
    #: day answer, whatever word the question used for the thing (E6).
    day = _day_terms(p, views_list)
    chosen = select(shape, day, views_list, limit=MAX_POINTS, per_note=MAX_PER_NOTE, said=said) if day else []
    return chosen, (day if chosen else terms)


def _fill_selected(out: "_Answer", p, shape: str, question: str, terms: list, typed: list, unsure: list, views_list: list, said: str, embed, voice: str) -> dict | None:  # noqa: ANN001
    """Choose the sentences and write the answer; a result only when there is
    nothing to say."""
    #: Read on the question as asked too: `rephrase` takes "what do my
    #: notes say about" off, which is the frame that says it is broad
    #: (INBOX 729: "what do my notes say about running" was answered
    #: as one fact with the other notes tacked on by "Elsewhere").
    broad = _is_broad(shape, question)
    meaning = _meaning_maker(shape, views_list, embed)(terms)
    wish = length_wish(question)
    chosen = select(
        shape, terms, views_list,
        limit=BROAD_NOTES if broad else FULL_POINTS if wish == "full" else MAX_POINTS,
        meaning=meaning,
        per_note=1 if broad else MAX_PER_NOTE,
        said=said,
    )
    if not chosen:
        chosen, terms = _by_the_day(p, shape, terms, views_list, said)
    if not chosen:
        if _bare_title(out, terms, views_list) is not None:
            return _result(out.parts, shape, out.rows)
        absent = _as_phrase([_as_typed(w, question) for w in _absent(typed, views_list)], question)
        return _feature_instead(question, absent) or _nothing(shape, unsure, voice, absent, out)
    if wish == "brief":
        chosen = [s for s in chosen if s.note_id == chosen[0].note_id]
        broad = False
        out.brief = True
    _write_body(out, p, shape, chosen, terms, question, meaning, broad, views_list)
    return None


def _answer_dict(out: "_Answer", shape: str, question: str, terms: list, views_list: list, unsure: list) -> dict:
    quotes = "\n\n".join(row["sentence"] for row in out.rows)
    cited = {row["note_id"] for row in out.rows}
    next_parts = (_did_you_mean(unsure) + _next_questions(question, shape, terms, views_list, cited))[:3]
    readings = [
        {"n": i, "note_id": out.views[v].note.get("source_id", v), "label": out.views[v].title}
        for i, v in enumerate(out.readings, 1)
    ]
    return {
        "readings": readings,
        "text": out.text,
        "grounding": out.rows,
        #: Counted over the quotes, the only claims an answer here makes: the
        #: connective phrases are not claims, and counting them as sentences
        #: "no note backs" would report a wholly quoted answer as half made up.
        "support": grounding.support(quotes, out.rows),
        "shape": shape,
        "parts": out.parts,
        "next": ["".join(part[1] for part in parts) for parts in next_parts],
        "next_parts": next_parts,
        #: The insight lines said, each with its key, for Confirm and Not right.
        "insights": getattr(out, "insights", []),
        #: A broad question ("what do my notes say about running"): opens with
        #: the topic and the count when it quotes several notes (INBOX 729).
        "broad": bool(getattr(out, "broad", False)),
    }


def _fresh_answer(views_list: list, today: date, dialogue: Dialogue | None, said: str, previous: str, voice: str, question: str) -> "_Answer":
    out = _Answer({v.id: v for v in views_list}, today)
    _from_dialogue(out, dialogue)
    out.said = said
    out.subject = {_stem(t) for t in subject_terms(question)}
    out.previous = (previous or "").lstrip()
    out.voice = voice
    out.question = question
    return out


def _fill_by_shape(out: "_Answer", p, shape: str, question: str, terms: list, typed: list, unsure: list, views_list: list, said: str, embed, voice: str) -> tuple:  # noqa: ANN001
    """Write the answer the shape asks for; the (possibly changed) shape and a
    result only when there is nothing to say."""
    if shape == "recent":
        _newest(out, views_list, guessing=_guessing_recent(question))
        return shape, None
    sides = compare_sides(question) if shape == "compare" else None
    versus = None if sides else composer_versus.which_one(question, views_list, out.today, _stem)
    if versus:
        _versus_answer(out, versus)
        return shape, None
    if sides and _compare(out, sides, views_list, _meaning_maker(shape, views_list, embed), question):
        return shape, None
    shape = "what" if shape == "compare" else shape
    return shape, _fill_selected(out, p, shape, question, terms, typed, unsure, views_list, said, embed, voice)


def _refusal(refused: tuple, question: str, shape: str) -> dict:
    """The answer that says the word asked about is one the notes are kept
    from (a filter refused it)."""
    key, word = refused
    return _result([("template", PHRASES[key]), ("template", PHRASES["open_quote"]), ("asked", _as_typed(word, question)),
                    ("template", PHRASES["close_quote"]), ("template", PHRASES["stop"])], shape)


def _planned(question: str, today: date, recent: bool, embed, prefer: str, notes: list[dict], views_list: list):  # noqa: ANN001, ANN202
    """The plan for the question, the notes it may read, and the refusal when
    a word it asks about is one the notes are kept from (else None)."""
    p = plan(question, today, recent=recent, embed=embed)
    _steer_to_correction(p, prefer, notes)
    views_list, refused = _filtered(views_list, p)
    return p, views_list, (_refusal(refused, question, p.shape) if refused else None)


def _compose(
    question: str,
    notes: list[dict],
    *,
    today: date | None,
    recent: bool,
    embed,  # noqa: ANN001
    said: str,
    previous: str,
    voice: str,
    now: datetime | None,
    salt: str,
    turn: int | None,
    dialogue: Dialogue | None,
    prefer: str,
) -> dict:
    """`compose`'s body, inside the conversation's salt."""
    voice = composer_tables.voice_of(voice)
    today = today or user_today()
    #: The newest notes answer a question with a time and no subject. When
    #: retrieval fell back to them for a question with a subject ("summarise
    #: my gym notes" with no gym note), the subject is answered, or said to
    #: be in no note found (engine probe P7).
    #: Unless retrieval read it as a recency ask outright ("What have I saved
    #: recently?": "saved" is a verb there, not a subject; owner, 2026-10-17).
    recent = recent and _still_recent(question)
    early = _early_answer(question, notes, said=said, recent=recent, today=today, embed=embed, voice=voice, salt=salt, turn=turn, now=now)
    early = early or (None if said else _cannot_untick(question))
    early = early or (None if said else _unfinished_act(question, now or datetime.combine(today, datetime.min.time())))
    if early:
        return early
    notes = _correction_order(notes, prefer, dialogue) if prefer else notes
    views_list = _note_views(notes)
    p, views_list, refusal = _planned(question, today, recent, embed, prefer, notes, views_list)
    if refusal is not None:
        return refusal
    out = _fresh_answer(views_list, today, dialogue, said, previous, voice, question)
    return _answer_views(out, p, question, views_list, today, recent=recent, embed=embed, said=said, voice=voice)


def _answer_views(out: "_Answer", p, question: str, views_list: list, today: date, *, recent: bool, embed, said: str, voice: str) -> dict:  # noqa: ANN001
    """Classify the question and write the answer from the notes it may read."""
    shape = "recent" if recent else classify(question, embed)
    typed = p.terms if shape != "recent" else []
    unsure: list[dict] = []
    question_noise.repair(" ".join((question or "").split()), unsure)
    terms = _fit_terms(typed, views_list, unsure)
    counted = _checklist_or_until(out, said, question, views_list, today)
    if counted is not None:
        return counted
    dated = _written_when(out, question, p, views_list)
    if dated is not None:
        return dated
    decided, views_list = _window_gate(out, p, said, question, shape, views_list)
    if decided is not None:
        return decided
    shape, nothing = _fill_by_shape(out, p, shape, question, terms, typed, unsure, views_list, said, embed, voice)
    if nothing is not None:
        return nothing
    if not out.rows:
        return _nothing(shape, unsure, voice, out=out)
    return _answer_dict(out, shape, question, terms, views_list, unsure)


# --- the brief a running model reads ------------------------------------------------

#: At most this many sentences quoted for a model, and this many from one note.
#: Twice an answer's: the model writes the answer, so it is handed the
#: material for one with room to choose, not the composer's choice alone.
BRIEF_POINTS = 12
BRIEF_PER_NOTE = 4
#: A note whose quoted parts come to this share of it goes whole: the cut
#: would save a few characters and cost the model the sentences around them.
BRIEF_WHOLE = 0.8


def _raw(content: str, s: Sentence) -> str:
    """The sentence as the note has it: the offsets, not the cleaned text, so a
    model reads (and the grounding pass later matches) the person's words."""
    return " ".join(content[s.start : s.end].split())


def brief(
    question: str,
    notes: list[dict],
    *,
    recent: bool = False,
    embed=None,  # noqa: ANN001
    composed: dict | None = None,
) -> dict | None:
    """The notes a running model reads, composed (CHAT_PLAN, "the composer
    everywhere" 9 and 10, the owner: "the composer should be used to lessen
    the load ... as well as cheapen the run cost of the ai").

    Every note stays, in its place, with its id and every other field the
    prompt reads (category, dates, tags, the connected flag), so nothing the
    model was told about a note is lost and nothing is renumbered. Only
    `content` changes, and only for a retrieved note whose text is longer than
    what bears on the question:

    - a note with sentences the composer chose keeps its name and those
      sentences, in the note's order, "…" where text was left out;
    - a note with none keeps its name and its first sentence: retrieval found
      it by meaning or by a link, and the question's words may not be in it;
    - a note attached by hand, a document, a file or a mind map goes whole: the
      person chose it, it is the subject;
    - a note the cut would barely shorten (`BRIEF_WHOLE`) goes whole.

    A shortened note carries `briefed: True`; `librarian.note_for_prompt` says
    so after it, naming `get_note` when the model has tools. None when there is
    nothing to brief: a "newest notes" question (the newest are the subject),
    or no sentence chosen at all (the composer has no reading of the question,
    and the notes as they are are the honest fallback).

    `composed` is `compose()`'s result for the same question, when the caller
    has it (the route does: it shows it while the model writes).

    Returns `{"notes", "quoted", "shortened", "chars_before", "chars_after"}`.
    """
    if recent or not notes:
        return None
    shape = classify(question)
    terms = subject_terms(question)
    views: dict[int, NoteView] = {}
    for i, note in enumerate(notes):
        if note.get("attached") or not isinstance(note.get("id"), int):
            continue
        view = read_note(note, i)
        if view is not None:
            views[i] = view
    candidates = list(views.values())
    pool = sorted(_score(shape, terms, candidates), key=lambda s: (-s.score, s.rank, s.order))[:MEANING_POOL]
    chosen = select(
        shape, terms, candidates,
        limit=BRIEF_POINTS,
        meaning=_Meaning(pool, embed, {_stem(t) for t in terms}),
        per_note=BRIEF_PER_NOTE,
    )
    if not chosen:
        return None
    by_note: dict[int, list[Sentence]] = {}
    for s in chosen:
        by_note.setdefault(s.note_id, []).append(s)
    #: Everything the composed answer quotes is in the brief too, whatever the
    #: caps above left out (a long checklist, the two sides of a compare): the
    #: answer shown while the model writes (`routes_chat`) never says a thing
    #: the model was not shown.
    composed = composed if composed is not None else compose(question, notes, recent=recent, embed=embed)
    spans = {(row["note_id"], row["start"]) for row in composed.get("grounding") or []}
    for view in candidates:
        for s in view.sentences:
            if (view.id, s.start) in spans and s not in by_note.get(view.id, []):
                by_note.setdefault(view.id, []).append(s)
    out: list[dict] = []
    shortened = before = after = 0
    for i, note in enumerate(notes):
        content = str(note.get("content") or "")
        before += len(content)
        view = views.get(i)
        text = _brief_text(view, content, by_note) if view else None
        if text is None or len(text) >= BRIEF_WHOLE * len(content.strip()):
            out.append(note)
            after += len(content)
            continue
        out.append({**note, "content": text, "briefed": True})
        after += len(text)
        shortened += 1
    return {
        "notes": out,
        "quoted": sum(len(kept) for kept in by_note.values()),
        "shortened": shortened,
        "chars_before": before,
        "chars_after": after,
    }


def _brief_text(view: NoteView, content: str, by_note: dict[int, list[Sentence]]) -> str:
    """One note's part of the brief: its name, then the sentences kept."""
    if view.id in by_note:
        picked = sorted(by_note[view.id], key=lambda s: s.order)
    else:
        picked = view.sentences[:1]
    parts: list[str] = []
    #: An untitled note is named by its first words; when its first sentence
    #: is kept, the name would only say those words twice.
    opens_with_name = bool(picked) and picked[0].order == 0 and _raw(content, picked[0]).startswith(view.title.rstrip("…"))
    if view.title and not opens_with_name:
        parts.append(view.title)
    last = -1
    for s in picked:
        if parts and s.order != last + 1:
            parts.append("…")
        parts.append(_raw(content, s))
        last = s.order
    if last < len(view.sentences) - 1:
        parts.append("…")
    return " ".join(parts)


act_registry.help_sentence = help_line


def open_note_answer(question: str, note: dict, *, today: date, salt: str = "") -> dict | None:
    """The open note's answer to `question` as a composer result, or None
    when the question is not one of this module's kinds."""
    ask = composer_open.kind(question)
    if ask not in ("left", "when", "who", "done"):
        return None
    view = read_note(note, 0)
    if view is None:
        return None
    out = _fresh_answer([view], today, None, "", "", composer_open.composer_voice(), question)
    {"left": composer_open._left, "when": composer_open._when, "who": composer_open._who, "done": composer_open._done}[ask](out, view, question, salt)
    return _answer_dict(out, "open_" + ask, question, [], [view], [])
