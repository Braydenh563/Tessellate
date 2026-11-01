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
(choosing what to quote), `composer_answer` (the answer being built),
`composer_quote` (saying a quote), `composer_unfound` (the words no note has),
`composer_body` (the layout by shape), `composer_dialogue` (next questions and
follow-ons), `composer_smalltalk` (social replies), `composer_intent` (the
question's plan), `composer_help` (help with the app), `composer_empty` (when
nothing answers).
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime

from tessellate.ai import act_registry, composer_ack, composer_links, composer_open, composer_tables, composer_versus, grounding, phrasing, question_noise, spelling, utilities
from tessellate.ai import recognise as rec
from tessellate.ai.composer_phrases import PHRASES, phrase_options  # noqa: F401  (moved; re-exported)
from tessellate.ai.composer_ask import IRREGULAR_PAST, SHAPES, SYNONYM_GROUPS, _ASKING_WORDS, _ASKS_FIRST, _BIN_WORDS, _COMPARE_SIDES, _CONTRACTIONS, _DEFINE, _IF, _KNOWN, _MONTHS, _MONTH_INDEX, _NUMBER_WORDS, _SHAPE_RULES, _TRAILERS, _WEEKDAYS, _WHEN_NOISE, _WRAPPERS, _alternatives, _build_synonyms, _guessing_recent, _holds, _overview, _stem, _still_recent, _without_command, _words, asks_time, asks_written_when, classify, compare_sides, rephrase, subject_terms, user_now, user_today, what_is  # noqa: F401  (moved; re-exported)
from tessellate.ai.composer_read import LEAD_INS, LEAD_INS_BARE, MAX_QUOTE_CHARS, NoteView, Sentence, _HEADING_LEAD, _ITEM, _LEAD_IN, _MARKS, _PICTURES_HEAD, _SPLIT, _SPLIT_HYPHEN, _WHERE_CUE, _cue, _depth, _discourse, _distinct_ids, _heading_text, _picture_groups, _picture_spans, _picture_text_breaks, _short_fact, _title, _unit, _written, plain_words, read_note, source_kind  # noqa: F401  (moved; re-exported)
from tessellate.ai.composer_select import KIND_WORDS, MAX_PER_NOTE, MAX_POINTS, MEANING_POOL, NEAR_DUPLICATE, RELATIVE_FLOOR, _ASKS_NOW, _FIGURE, _Meaning, _NEGATION, _score, _term_weights, centrality, correcting, disagree, select, superseded  # noqa: F401  (moved; re-exported)
from tessellate.ai.composer_answer import _Answer, _LEARNED, _NOW_WORDS, _REGISTER, _RELATIVE_DAYS, _SESSION, _count_word, _due, figures_of  # noqa: F401  (moved; re-exported)
from tessellate.ai.composer_quote import _OPENERS, _checklist_count, _joined, _lowered, _pick, _quotes, _sentence_case  # noqa: F401  (moved; re-exported)
from tessellate.ai.composer_unfound import _FRAME_WORDS, _frame_stems, _missing, _seen  # noqa: F401  (moved; re-exported)
from tessellate.ai.composer_body import BROAD_NOTES, FULL_POINTS, _BROAD, _NOTE_NOUNS, _asked_span, _body, _compare, _confirmed_lead, _days_named, _disagreement, _disagreements, _insight_close, _insight_lead, _insights_for, _kinds, _mentions, _newest, _notes_named_by, _opening, _others, _overview_line, _relation, _span, _still_open, _summary, _timeline, _until_note, _versus_answer, heading_name, length_wish, told_as_past  # noqa: F401  (moved; re-exported)
from tessellate.ai.composer_dialogue import Dialogue, NEXT_MAX_CHARS, _BARE, _BOLD, _MORE, _ORDINAL, _ORDINALS, _PRONOUN, _RESTATES, _follow_pronoun, _named_notes, _next_questions, _standing, follow_on, refers_back  # noqa: F401  (moved; re-exported)
from tessellate.ai.composer_smalltalk import INVITES, NEXT_STEPS, NEXT_STEPS_PROFESSIONAL, SOCIAL, SOCIAL_PROFESSIONAL, _social_line, call, call_asks, greeting_ask, invitation, social, social_kind, social_surfaces  # noqa: F401  (moved; re-exported)
from tessellate.ai.composer_intent import PLAN_CHARS, Plan, _ACT_VERBS, _TAGGED, _WHY, _lead_act_verb, _plan_window, _time_phrase, holds_any, plan, window_verb_stems  # noqa: F401  (moved; re-exported)
from tessellate.ai.composer_help import _act_sentence, _clauses, _feature_instead, _help_act, _help_act_stems, _help_answer, _in_window, _result, _utility, help_line, offered  # noqa: F401  (moved; re-exported)
from tessellate.ai.composer_empty import _absent, _as_phrase, _as_typed, _bare_title, _did_you_mean, _filtered, _nothing, empty_window, window_said  # noqa: F401  (moved; re-exported)


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
