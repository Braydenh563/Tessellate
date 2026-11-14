"""The answer a person would give from the notes (CHAT_PLAN decision 70).

INBOX 812, the owner: "the response feels plain, boring, lifeless, and doesnt
give me anything more. I may as well just read the notes I made on the
right". The composer quoted: each note's sentence under a bar with a
bracketed day, then the same notes again as chips and a count. The right
column already shows the notes, so the answer's job is what the column
cannot do: say how many and over which days, put the facts in the
person's terms under a label each, say what the notes do not cover, and
offer one thing to do next.

The shape, from the gold answers (`tests/fixtures/gold_answers.json`):

- one opening sentence that answers, with a count and a span or the fact;
- grouped facts, a bold label and a rewritten sentence each, not a quote;
- what the notes do not say;
- one offer that acts (a reminder, a checklist), never a question for its own sake.

No model and nothing invented: every fact line is a note's own sentence,
cut and turned to the second person, and it carries the note it came
from (`grounding`), so the one citation mark per line lights its card.
Jokes, quotes and other people's words are never said as the person's
facts (decision 67): a note tagged joke is left out unless jokes are asked
for. `answer` returns None for a question this shape does not fit; the
caller then asks `composer.compose`.

The connecting words are in `PHRASES`, one table, so a voice preset
(decision 72) swaps them without touching the facts or the shape.
"""

from __future__ import annotations

import re
import zlib
from collections import Counter
from collections.abc import Iterable
from datetime import date, datetime, timedelta

from tessellate.ai import composer, composer_doings, composer_done, composer_frame, composer_threads, composer_lists, composer_money, composer_slots, composer_sum, composer_tables, glossary, question_noise, realise
from tessellate.ai import composer_ages, composer_answer, composer_nth, composer_oneword, composer_property, composer_small
from tessellate.ai import composer_ahead, composer_ask, composer_notime, composer_clean, composer_event_verdict, factgraph
from tessellate.ai import composer_aliases, composer_assign, composer_chip_subject, composer_overview
from tessellate.ai import composer_close, composer_jokes, composer_select
from tessellate.ai import composer_credit, composer_each, composer_label, composer_refer, composer_tally
from tessellate.ai.composer_lists import clean
from tessellate.ai import recognise as recogniser, recognise_questions
from tessellate.search import query as query_understanding
from tessellate.ai.composer_clause import trailing_clause
from tessellate.ai.composer_digest_sentences import (
    CONTEXT_TAGS, Fact, LINES, PHRASES, VOICES, _ASKED_AS, _ASKS, _ASKS_WORDS, _BAD, _CUES,
    _DAYS_PLURAL, _DAY_NAMES, _FEELING_ASK, _GAPS, _GOOD, _KNOWN, _NAMES, _Out, _RATING,
    _REMINDABLE, _REVIEWED_WORDS, _SEED, _STILL_TO, _SUBJECT_STEMS, _TIMED, _TIME_LABEL, _TODAY,
    _TURN, _VIEWS, _VOICE, _WHEN_ASK, _WORK, _capitalised_inside, _day, _dictionary, _feeling,
    _fragment, _from_source, _isolated, _lead_day, _note_called, _said_day, _says_day,
    _second_person, _set_timing, _span, _spans, _title_only, _unlinked, _vary, _when_gone,
    _your_note, about_this, kind_of, named_category,
)
from tessellate.ai.composer_digest_lines import (
    MORE_LINES, _kind_of_note, _AM_DOING, _CJK_ENDS, _CJK_STOP, _DAY_NAME, _DID, _GOING, _HEARD, _LAST_ONE,
    _LATEST_ASK, _NAMES_A_THING, _PLANNED, _WEEKDAYS, _WEEKDAY_WORDS, _WHEN_DID, _WHEN_LAST,
    _WHEN_NOW, _ahead_if, _answered, _ask_stems, _behind_if, _context_note, _count, _fact_words,
    _facts, _label_names, _lines, _measures, _members, _missing, _names_it, _narrate, _offer,
    _opening, _overview, _pool, _predicate_stems, _prose, _row, _said_in_a_frame, _says_now,
    _says_the_ask, _scored_members, _sentence_day, _subject, _subject_facts, _tidy,
    _title_is_subject, _titled_for_yes_no, _topic, _unfilled, _week_written, _yes_no,
    asks_for_a_topic,
)




def _best(facts: list[Fact], question: str, cue: re.Pattern | None = None) -> Fact | None:
    #: Without the asking words: "what day did I run 8 km" is not about a "day".
    stems = set(_subject(question))
    picked = composer_jokes.pick(facts, stems)
    if picked is not None:
        return picked
    asks = _ask_stems(question) if not _LATEST_ASK.search(question) else set()
    predicate = _predicate_stems(question)
    if isinstance(cue, _MoneyCue):
        #: "what does the hotel cost" is about the hotel; "cost" is the ask.
        stems -= {composer._stem(w) for w in ("cost", "price", "pay", "paid", "charge", "much")}  # noqa: SLF001
    #: A timing or kind word counts less than the subject ("when are the
    #: designs coming": the designs, not the plumber who is coming).
    weight = composer_select._term_weights(sorted(stems))  # noqa: SLF001
    #: A note a newer one corrects says the old value: "when's the dentist
    #: now" is the moved slot, not the first booking (stress run 2026-10-30).
    old = composer_select.superseded(composer.subject_terms(clean(question)), list({id(f.view): f.view for f in facts}.values()))

    #: "is the dentist tomorrow" is about the note titled Dentist, though a to-do line is the one to say "dentist" (bt-compcomp-1109 item 3).
    yes_no = _yes_no(question)
    figures = composer_answer.figures_of(question)
    asks_feeling = bool(_FEELING_ASK.search(question))
    latest = bool(_LATEST_ASK.search(question) or _LAST_ONE.search(question))
    did_ask = bool(_WHEN_DID.match(clean(question)))
    subject_words = list(composer.subject_terms(clean(question)))
    #: "what's the latest on X" asks for news, not for the note titled X (R9-9: how is it now).
    names_a_thing = bool(_NAMES_A_THING.match(clean(question))) and not latest
    going = _AM_DOING.search(clean(question))
    going_on = re.compile(rf"\b{re.escape(going.group(1))}\b", re.I) if going else None
    now_ask = bool(_WHEN_NOW.match(clean(question))) and _TODAY.get() is not None
    last_ask = bool(_WHEN_LAST.match(clean(question)))
    #: "what is Project Atlas" is the note titled that, whatever other note repeats the name (round 1 D1).
    #: Only a "what/who is X" ask: any other ask is weighed by what the lines say (review 1).
    titled_views = {id(f.view) for f in facts if names_a_thing and _defines(f.view, subject_words) == 2}

    def rank(f: Fact) -> tuple:
        words = _fact_words(f)
        own = sum(weight[st] for st in stems if composer._holds(st, words))
        hits = sum(weight[st] for st in stems if composer._holds(st, words | f.view.filed_words | f.view.title_words))
        #: The amount asked about ("8 km") beats a sentence that only shares the verb.
        same_figure = bool(figures & composer_answer.figures_of(f.sentence.text))
        #: Between sources that say it equally well, the one the search ranked first.
        #: Of the notes that fit the subject equally, the newest one for a "latest" ask.
        newest = (f.view.written or date.min) if latest else date.min
        newest_own = _sentence_day(f) if latest else date.min
        #: The sentence that holds the ask's own verb, in a note that holds the rest of the subject (R9-2).
        says_it = _says_the_ask(f, words, asks, stems, predicate)
        #: "when did I bake banana bread": the sentence that says the whole
        #: doing leads, whatever else the note holds (audit 1031 C16).
        acts = bool(did_ask and stems and all(composer._holds(st, set(f.sentence.words)) for st in stems))
        #: A sentence that is itself a question answers none ("What are you reading
        #: at the moment?" in an ice-breakers note, audit 1031 C18).
        asked_back = f.sentence.text.rstrip().endswith("?")
        #: A bare list item ("Passport") is no news of a subject: prose leads a
        #: latest ask. Said in the tuple itself: CodeQL lost the local in this
        #: closure and read it as possibly unset.
        titled = id(f.view) in titled_views
        #: The sentence that says the doing ("Currently reading Piranesi") beats the note that is only about it.
        doing_now = _says_now(going_on, f)
        #: What a titled note is leads with the line it opens on; 
        opens = titled and _opening(f)
        #: "what is Doug", "who is Marek": the sentence that says what it is ("is called Doug", "Builder is Marek", R9-3).
        names_it = _names_it(f.sentence.text, names_a_thing, subject_words)
        #: The note titled for the whole subject speaks for it before a title-less one that only repeats its words (F8, 1110).
        is_the_subject = _title_is_subject(f, stems)
        return (not asked_back, not _in_a_place(f.sentence.text, stems), doing_now, acts, _cued(cue, f.sentence.text), _behind_if(last_ask, f, _TODAY.get()), _ahead_if(now_ask, f), not (latest and f.sentence.kind in {"item", "task"}), id(f.view) not in old, _label_asked(f.label, question), titled, opens, names_it, says_it, hits, newest, newest_own, is_the_subject, _titled_for_yes_no(f, stems, yes_no), own, asks_feeling and _feeling(f.sentence.text), f.view.titled, same_figure, -f.view.rank, -f.sentence.order)

    return max(facts, key=rank) if facts else None


def _say_list(out: _Out, lead: Fact, items: list[str], today: date, question: str = "") -> None:
    """"Hobbies I want to try: bouldering, film photography, ukulele": asked
    what the hobbies are, the answer is the count and the list."""
    day = f", written {_said_day(lead.view.written, today)}" if _TIMED.get() and lead.view.written else ""
    name = f"your note “{lead.label}”" if _label_names(lead.label, lead.view) else _your_note(lead.view)
    out.lines.append(f"{realise.count_word(len(items)).capitalize()}, from {name}{day}: {realise.join_items(items)}.")
    others = [v for v in _VIEWS.get() if v.id != lead.view.id]
    #: Said of things still to try, never of words learned or items had (C20).
    if _TO_TRY.search(question) and not any(composer._holds(composer._stem(w), v.words) for v in others for i in items for w in composer.subject_terms(i)[-1:]):
        out.closing.append(PHRASES["none_own"])


def _from_name(lead: Fact, body: str, today: date) -> str:
    """"From your Psych lecture note, 21 October: ...": a heading the note
    gives itself names the note; a label the answer gave the fact ("How it
    went") does not. "" when the note is named by the very words said ("From
    why did the scarecrow win an award: Why did the scarecrow..." is the
    fact twice; audit 1031 C31) or the fact has no heading."""
    if not lead.label or lead.label in {name for name, _ in _CUES} or _TIME_LABEL.match(lead.label + " x"):
        return ""
    name = f"your {_fragment(lead.label, _NAMES.get())} note" if _label_names(lead.label, lead.view) else _your_note(lead.view)
    spoken = name.lower().strip("“”… .")
    if body.lower().lstrip("“”\" ").startswith(spoken):
        return ""
    day = f", {_said_day(lead.view.written, today)}" if _TIMED.get() and lead.view.written and not _says_day(body, lead.view.written, today) and composer_ahead.date_in(body, today) is None else ""
    if lead.label.strip().capitalize() in _DAY_NAMES:
        #: "Sunday: call Mum" is the note's own Sunday, not the day it was written (round 1 D8: "today: call Mum").
        day = f", on {lead.label.strip()}"
    return f"From {name}{day}: {body}."


_PRONOUN_SAID = re.compile(r"(?:he|she|it)\s+(?=(?:is|was|will|has|had|[a-z]{3,}s)\b)(?!also\b|then\b|still\b)", re.I)


def _with_its_name(lead: Fact) -> str:
    """"He is coming Wednesday" in the note titled "Plumber" is "Plumber is coming Wednesday": a line
    that opens on a pronoun has lost its referent when it leads the answer (R9-6)."""
    body, title = lead.body, str(lead.view.title or "").strip()
    found = _PRONOUN_SAID.match(body)
    if found and lead.view.titled and 0 < len(title.split()) <= 3 and not title.endswith("…") and not _kind_of_note(title, lead.view):
        return f"{title} {body[found.end():]}"
    return body


def _say_fact(out: _Out, lead: Fact, today: date, question: str) -> None:
    body = _with_its_name(lead)
    items = [i.strip() for i in re.split(r",(?!\d)\s*", body) if i.strip()]
    if lead.label and len(items) >= 3 and all(len(i.split()) <= 4 for i in items):
        _say_list(out, lead, items, today, question)
    elif _from_name(lead, body, today):
        out.lines.append(_from_name(lead, body, today))
    else:
        out.lines.append(_from_source(lead.view, body[0].upper() + body[1:], today))
    out.rows.append(_row(body, lead))
    _dated_last(out, lead, today, question)


#: "When did I last write about Harbor?" is answered with the day, not only with the note (F5).
_LAST_WROTE = re.compile(r"^\s*when did i last (?:write|wrote|note|jot|save|mention) (?:about |on |down )?(?P<subject>.+?)\s*\??\s*$", re.I)


def _dated_last(out: _Out, lead: Fact, today: date, question: str) -> None:
    """The day first for "when did I last write about X", so it differs from "what's the latest on X"."""
    asked = _LAST_WROTE.match(clean(question))
    if asked and lead.view.written and out.lines:
        out.lines.insert(len(out.lines) - 1, f"You last wrote about {asked.group('subject')} on {_day(lead.view.written, today)}.")


#: "have bought", "'ve got": said in the past once its day leads.
_PERFECT = re.compile(r"(?:'ve|(?<!\s)\s+have|(?<!\s)\s+has)\s+(?=(?:\w+ed|bought|got|gone|made|found|sold|paid|spent|won|lost|had|taken|seen|met|left|done|read|heard|sent|built|kept|written)\b)", re.I)
_PARTICIPLE = {"gone": "went", "taken": "took", "seen": "saw", "done": "did", "written": "wrote"}


_AIMED_AT = re.compile(r"\b(?:for|until|till|by|before|ahead of|in time for)\s*$", re.I)


def _event_lead(out: _Out, lead: Fact, today: date) -> bool:
    """"On 17 July you bought a gaming mouse, discounted from $150 to $68.":
    the day first, then what happened, in the past and without the note's
    asides (the owner, 2026-10-11). The day is the one the sentence names
    ("bought it yesterday" is the day before the note), else the note's."""
    if lead.view.written is None:
        return False
    text = _unfilled(lead.sentence.text.strip().rstrip(".!"))
    if recognise_questions.set_for_later(text):
        #: "Booked for 14 November" is a day set, not a thing done: said as
        #: the day itself, never read back a year ("Back in November 2025").
        return False
    if re.match(r"(?:finally|then|eventually|also|at last)\s+\w+ed\b", text, re.I):
        #: "Finally finished the 5k": the writer did it.
        text = "I " + text[0].lower() + text[1:]
    body = _second_person(text)
    #: "It rained all day, and you baked banana bread": the clause that is the writer's.
    mine = re.match(r"it \w+[^,]*, and (you .+)$", body, re.I)
    if mine:
        body = mine.group(1)
    day = lead.view.written
    #: A thing done is in the past of the note that tells it: "Planted
    #: tomatoes on 5 October" in a note of 30 October is this year's 5 October,
    #: never next year's (2026-10-30 sweep).
    #: Read against the later of written and edited (E17): a log line added at an edit is no older than it.
    for found in _spans(body, factgraph._anchor(lead.view.note) or lead.view.written, "past"):
        #: "Called mum, she is coming for Christmas": a day a preposition of
        #: aim leads is where something is headed, not the day it happened
        #: (audit 1031 C9); the note's own day stands.
        if _AIMED_AT.search(body[:found.start]):
            continue
        if found.kind in ("date", "datetime"):
            value = found.value.date() if isinstance(found.value, datetime) else found.value
            if isinstance(value, date):
                day = value
                #: The preposition that led the day goes with it ("ran 5 km on 3 October in 28
                #: minutes" is not "ran 5 km on in 28 minutes", audit 1030 Z4).
                body = re.sub(r"\s+(?:on|at)\s*$", "", body[:found.start]) + body[found.end:]
            break
    body = re.sub(r"\s+(?:on|at)\s*$|\s+on(?=\s*[,.])", "", body.strip())
    body = _tidy(body, None)
    body = _PERFECT.sub(" ", body)
    body = re.sub(r"\b(gone|taken|seen|done|written)\b", lambda m: _PARTICIPLE[m.group(1).lower()], body, count=1)
    if not re.match(r"you\s", body, re.I):
        #: "Dentist appointment went fine": no one did it; said as before.
        return False
    body = body[4:].lstrip()
    #: "bought a new gaming mouse": a thing bought is new; "a new" goes.
    body = re.sub(r"\b(bought|got|ordered|picked up) (?:a|an) new (\w)", lambda m: f"{m.group(1)} {'an' if m.group(2).lower() in 'aeiou' else 'a'} {m.group(2)}", body)
    body = re.sub(r"(\w) ((?:discounted|reduced|marked down|down|on sale) from\b)", r"\1, \2", body)
    if len(body.split()) < 2:
        return False
    said = f"on {_day(day, today)}"
    #: Said as a person would (INBOX 1483): "On 8 October, about three weeks
    #: ago, you ...", "Yesterday, you ...", never a bare date to "when did I".
    when = _when_gone(said, day, today) if today and day < today else said
    out.lines.append(f"{when[:1].upper()}{when[1:]}, you {body}.")
    row = _row(out.lines[-1], lead)
    #: The mark sits after the day it vouches for ("On 17 July[1], you ...").
    row["anchor"] = out.lines[-1].split(",", 1)[0]
    out.rows.append(row)
    return True


class _WhenCue:
    """What a "when" answer leads with: a habit's weekdays, or a sentence that
    holds a day as the recogniser reads one ("Exam on 12 November", where the
    old month pattern wanted "in November")."""

    _DAYS = re.compile(r"\b(mon|tues|wednes|thurs|fri|satur|sun)days\b", re.I)

    def search(self, text: str) -> bool:
        return self.score(text) > 0

    def score(self, text: str) -> int:
        """2 for a day named, 1 for a habit's weekdays or a window ("this
        week"): "Beta on 10 November" answers a "when" before "this week I
        prepared the beta" does (audit 1030 Z21)."""
        kinds = {s.kind for s in _spans(text, None)}
        return 2 if kinds & {"date", "datetime"} else int(bool(self._DAYS.search(text)) or "range" in kinds)


def _cued(cue, text: str) -> int:  # noqa: ANN001
    """How well `text` carries what the kind's cue looks for."""
    if cue is None:
        return 0
    return cue.score(text) if isinstance(cue, _WhenCue) else int(bool(cue.search(text)))


_SINGLE_CUES = {
    "when": _WhenCue(),
    "count": re.compile(r"\$\s?\d|\d"),
    "opinion": _RATING,
}


_IN_A_ROW = re.compile(r"\b(\d{1,4})\s+days?\s+(?:in a row|running|straight)\b", re.I)
_STARTED = re.compile(r"\b(?:start|started|begin|began|begun)\b", re.I)


def _streak_start(out: _Out, lead: Fact, rest: list[Fact], question: str, today: date) -> list[Fact] | None:
    """"when did I start learning Spanish" with "42 days in a row" in a note of
    25 October: the day it began is worked out (day one is 41 days before the
    note), said as worked out, and ahead of any day a sentence names (audit
    1031: the note's own day is the day it was last counted, not the start)."""
    streak = next((m for sentence in [lead.sentence, *lead.view.sentences] for m in [_IN_A_ROW.search(sentence.text)] if m), None)
    if not (streak and lead.view.written and _STARTED.search(clean(question))):
        return None
    n = int(streak.group(1))
    began = lead.view.written - timedelta(days=max(n - 1, 0))
    line = f"About {_day(began, today)}: your note of {_day(lead.view.written, today)} says {n} days in a row."
    out.lines.append(line)
    out.rows.append(_row(line, lead))
    return [f for f in rest if f.view.id == lead.view.id]


def _say_fact_ahead(out: _Out, lead: Fact, today: date, question: str) -> None:
    """`_say_fact` for a "when" ask, where a day still ahead is said by its distance (R9-17), not by the write date."""
    token = _WHEN_ASK.set(True)
    try:
        composer_notime.say_noted(_say_fact, out, lead, today, clean(question), question)
    finally:
        _WHEN_ASK.reset(token)


def _single_when(out: _Out, lead: Fact, rest: list[Fact], question: str, today: date) -> list[Fact]:
    """A "when" ask: the day of one thing that happened, or a habit said as
    its days. Returns the facts still to say."""
    started = _streak_start(out, lead, rest, question, today)
    if started is not None:
        return started
    began = composer_doings.first(clean(question), list(_VIEWS.get()), today)
    if began is not None:
        #: The earliest line that says the doing was done, not a plan's weekday.
        line, done = began
        out.lines.append(line)
        out.rows.append(_row(line, Fact(done.view, done.sentence, "Started", done.sentence.text, "")))
        return []
    if _WHEN_DID.match(clean(question)) and _event_lead(out, lead, today):
        return []
    days = _DAYS_PLURAL.search(lead.body)
    #: A habit is weekdays in the plural or more than one ("Tuesdays",
    #: "Monday and Thursday"); "moved to Friday" is one day, said with its
    #: date (composer-1031, item 4).
    habit = days and len(re.findall(r"day", days.group(0), re.I)) + bool(re.search(r"days\b", days.group(0), re.I)) > 1
    if not habit:
        _say_fact_ahead(out, lead, today, question)
        return [f for f in rest if f.view.id == lead.view.id]
    said = days.group(0).strip(" ,")
    out.lines.append(_from_source(lead.view, said[0].upper() + said[1:], today))
    out.rows.append(_row(said, lead))
    rest = [f for f in rest if re.search(r"\b(mon|tues|wednes|thurs|fri|satur|sun)days\b|\bafternoons\b|\bmornings\b|\bevenings\b", f.sentence.text, re.I)]
    return [Fact(f.view, f.sentence, "Also on your week", f.body, f.action) for f in rest]


def _opinion_rest(facts: list[Fact]) -> list[Fact]:
    """What was loved and what was not, one fact each, from a review's clauses."""
    rest: list[Fact] = []
    for f in facts:
        for part in re.split(r"\s+but\s+|;\s*|,\s*|:\s+", f.sentence.text.strip().rstrip(".")):
            if _RATING.search(part) or _WORK.match(part):
                continue
            label = "Loved" if _GOOD.search(part) else "Didn't" if _BAD.search(part) else ""
            if label:
                rest.append(Fact(f.view, f.sentence, label, _fragment(_second_person(part), set()), ""))
    return rest


def _single_opinion(out: _Out, lead: Fact, facts: list[Fact], rest: list[Fact], question: str, today: date) -> list[Fact]:
    work = next((_WORK.match(f.sentence.text.strip()) for f in facts if _WORK.match(f.sentence.text.strip())), None)
    rating = next((_RATING.search(f.sentence.text) for f in facts if _RATING.search(f.sentence.text)), None)
    if not (work and rating):
        _say_fact(out, lead, today, question)
        return rest
    #: "Watched Dune Part Two: 7 out of 10, the sound was incredible":
    #: the title is the words before the rating or its first colon.
    title = re.split(r"\s*[:,(]\s+|\s+-\s+|\s+\d+(?:\.\d+)?\s*(?:/|out of)\b", work.group(1))[0].strip()
    out.lines.append(f"You gave {title} {rating.group(1)} out of {rating.group(2)} on {_day(lead.view.written, today)}.")
    out.rows.append(_row(f"{title} {rating.group(1)} out of {rating.group(2)}", lead))
    return _opinion_rest(facts)


def _against_aim(said: str, facts: list[Fact], lead: Fact) -> tuple[str, list[Fact]]:
    """Against the aim the notes set (INBOX 870): "$84 ..., under your aim of
    $100 a week", which no one note says. Returns the line and the facts left."""
    spent = re.search(r"\$\s?(\d+(?:\.\d+)?)", said)
    aim = next((m for f in facts for m in [re.search(r"\bunder \$\s?(\d+(?:\.\d+)?)((?: a| per) (?:week|month|day))?", f.sentence.text)] if m), None)
    line = said[0].upper() + said[1:]
    if not (spent and aim):
        return line, facts
    key = "aim_under" if float(spent.group(1)) <= float(aim.group(1)) else "aim_over"
    line = _vary(key).format(said=line, aim=f"${aim.group(1)}{aim.group(2) or ''}")
    return line, [f for f in facts if not re.search(r"\bunder \$", f.sentence.text) or f is lead]


def _single_count(out: _Out, lead: Fact, facts: list[Fact], members, question: str, today: date) -> list[Fact]:  # noqa: ANN001
    clauses = re.split(r"\s+and\s+(?=\$?\d)", lead.sentence.text.strip().rstrip("."))
    stems = {composer._stem(t) for t in composer.subject_terms(clean(question))}
    main = next((c for c in clauses if any(composer._holds(st, set(composer._words(c))) for st in stems)), clauses[0])
    said = _tidy(_week_written(_second_person(main), lead.view.written, today), lead.view.written)
    line, facts = _against_aim(said, facts, lead)
    out.lines.append(line if line.endswith(".") else line + ".")
    out.rows.append(_row(said, lead))
    if "week of" in said and len(members) == 1:
        out.closing.append(PHRASES["only_week"])
    rest = [Fact(lead.view, lead.sentence, "Also that week", _tidy(_second_person(c), lead.view.written).lstrip("you spent ").strip(), "") for c in clauses if c is not main]
    return rest + [f for f in facts if f is not lead and f.view.id == lead.view.id]


def _single_heading(out: _Out, lead: Fact, rest: list[Fact], today: date) -> list[Fact]:
    """The note's heading said as prose, its other sentences in the same
    paragraph (the owner, 2026-10-11), one mark for all of them."""
    rest = [f for f in rest if f.view.id == lead.view.id]
    along = [f for f in rest if f.heading and f.label == lead.label][:2]
    rest = [f for f in rest if f not in along]
    held = [lead, *along]
    line = _prose(lead.label, held, [_fragment(f.body, _NAMES.get()) for f in held], 0, today)
    out.lines.append(line + ".")
    row = _row(line, lead)
    if along:
        row["parts"] = [{"note_id": f.view.note.get("source_id", f.view.id), "source": f.sentence.text, "start": f.sentence.start, "end": f.sentence.end} for f in held]
    out.rows.append(row)
    return rest


def _single_close(out: _Out, kind: str, rest: list[Fact], members, question: str = "") -> None:  # noqa: ANN001
    labels = {f.label for f in rest}
    score = re.search(r"You gave .+? (\d+(?:\.\d+)?) out of", out.lines[0]) if out.lines else None
    if kind == "opinion" and score and {"Loved", "Didn't"} <= labels:
        #: The verdict the two lines add up to (INBOX 870).
        out.closing.append(_vary("mixed").format(score=score.group(1)))
    #: One note chosen from a topic many notes carry is not "the only note"
    #: (second eye F10): the closing counts the notes that hold the topic.
    if len(members) == 1 and kind in ("fact", "opinion") and asks_for_a_topic(question) and len(_scored_members(_subject(question), _VIEWS.get())) <= 1:
        word = _reviewed_word(question, members) if kind == "opinion" else ""
        noun = f"{word} review" if word else "note"
        out.lines.append(PHRASES["only_note"] if noun == "note" else PHRASES["only_kind"].format(noun=noun))


_TASKY = re.compile(r"\b(?:to-?do|tasks?|checklist|left|open|unfinished)\b", re.I)


def _drop_tasks(kind: str, lead: Fact, rest: list[Fact], question: str) -> list[Fact]:
    """An unticked checklist item is not a fact about the thing asked
    (composer5: "what is the Krebs cycle" listing "read chapter 4")."""
    if kind != "fact" or lead.sentence.kind == "task" or _TASKY.search(question):
        return rest
    return [f for f in rest if f.sentence.kind != "task"]


#: "Where is book club", "where do I keep the spare key": the sentence that
#: names a place leads ("Meeting at Ana's"), not the first one that names
#: the subject ("Next book is Piranesi"; 2026-10-30 sweep).
#: "What does Priya do", "what is Tom's job": the sentence that says the
#: work leads, not the note's first line (audit 1030 Z12).
_ROLE_ASK = re.compile(
    r"^\s*(?:what (?:does|did) [\w' -]+ do(?: for (?:a )?(?:living|work))?|what(?:'s| is) [\w' -]+'s? (?:job|role|work|title|job title|position|occupation)"
    r"|where (?:does|did) [\w' -]+ work)\s*\??$",
    re.I,
)
_ROLE_CUE = re.compile(r"\b(?:works?|worked|job|role|position|employed|is (?:a|an|the|our) )", re.I)
_WHERE_ASK = re.compile(r"^\s*where(?:'s| is| are| was| were| do| does| did| can| should)?\b", re.I)
_WHERE_CUE = re.compile(
    r"\b(?:at|in|on|near|under|behind|beside|inside|above|below|next to|outside|by)\s+(?:the\s+|my\s+|a\s+|an\s+|our\s+)?[\w'-]+", re.I
)


class _PlaceCue:
    """A place phrase ("at Hotel Alfama", "near the castle"): not "on 14
    November", whose object is a day the recogniser reads (audit 1030 Z24:
    "where is the Lisbon trip" led with the flight dates)."""

    def search(self, text: str) -> bool:
        days = [(s.start, s.end) for s in _spans(text, None) if s.kind in ("date", "datetime", "range", "time")]
        return any(not any(a < m.end() <= b for a, b in days) for m in _WHERE_CUE.finditer(text))


def _same_label_asked(lead: Fact, f: Fact, question: str) -> bool:
    """Asked for "goals for Q1", a fact under Q2 is another answer."""
    if not lead.label or f.label == lead.label:
        return True
    return not _label_asked(lead.label, question)


def _label_asked(label: str, question: str) -> bool:
    """The question names this label, "Q1" in "goals for Q1". Read from the
    raw words: the subject reader takes "Q1" for a window of dates."""
    asked = set(composer._words(question))  # noqa: SLF001
    return bool(label) and {composer._stem(w) for w in label.split()} <= asked


class _MoneyCue:
    """A sentence that holds an amount of money as the recogniser reads one
    ("$420", "85 euros"): "how much are the flights" leads with the price, not
    with the line that merely holds a digit (audit 1030 Z32)."""

    def search(self, text: str) -> bool:
        return recogniser.says_shape("money", text)


_MONEY_ASK = re.compile(r"\bhow much\b|\b(?:costs?|price[sd]?|pay|paid|charge[sd]?)\b", re.I)


#: "how long do I bake it": the lead is the sentence that holds a length of time (audit 1031 C16).
_HOW_LONG = re.compile(r"^\s*how long\s+(?:do|does|did|will|would|should|can|could|is|are|was|were)\b", re.I)
#: "2h50" and "1h 30m" are a length of time too: the journey time of a timetable line.
_DURATION = re.compile(
    r"\b(?:\d+(?:[.,]\d+)?\s*(?:-\s*\d+\s*)?|(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|a few|several)\s+)"
    r"(?:seconds?|secs?|minutes?|mins?|hours?|hrs?|nights?|days?|weeks?|months?|years?)\b"
    r"|\b\d{1,2}\s?h(?:\s?\d{1,2}\s?(?:m(?:in)?)?)?\b", re.I)


def _single_cue(kind: str, asked: str) -> re.Pattern | None:
    """What the leading sentence should say: the kind's own cue, the work for
    "what does Priya do", the place for a where."""
    if kind != "when" and _MONEY_ASK.search(asked):
        return _MoneyCue()
    if _HOW_LONG.match(asked):
        return _DURATION
    if kind in _SINGLE_CUES:
        return _SINGLE_CUES[kind]
    if recognise_questions.event_window_asked(asked):
        #: "is my dentist appointment tomorrow": the line that holds the day leads, not the one that names the
        #: appointment (W8B 1111); its verdict reads the first line.
        return _SINGLE_CUES["when"]
    if _ROLE_ASK.match(asked):
        return _ROLE_CUE
    return _PlaceCue() if _WHERE_ASK.match(asked) else None


def _no_place(out: _Out, cue, lead: Fact) -> None:  # noqa: ANN001
    """A "where" whose best sentence names no place says so first."""
    if isinstance(cue, _PlaceCue) and not cue.search(lead.sentence.text):
        out.lines.append(PHRASES["no_place"])


def _names_whose(view, whose: str) -> bool:  # noqa: ANN001
    """Whether the note is about the person or business whose number was asked ("Sara's phone number"
    must not be the dentist's; R3-2). No subject asked: any note."""
    words = [w for w in re.findall(r"\w+", whose.lower()) if w not in ("the", "my", "our")]
    if not words:
        return True
    text = " ".join([view.title or "", *(x.text for x in view.sentences)]).lower()
    return all(re.search(rf"\b{re.escape(w)}", text) for w in words)


def _property_lead(out: _Out, question: str, members, facts: list[Fact], lead: Fact) -> Fact | None:
    """The fact that holds the property asked for ("his number", "the
    password for the bank"); None, with the line said, when no note read for
    this says it (round 2 E4, E20). `lead` itself when the question asks no such property."""
    prop = composer_property.asked(question)
    if not prop:
        return lead
    whose = composer_property.subject(question) if prop == "phone" else ""
    holders = [f for f in facts if composer_property.held(prop, f.sentence.text) and _names_whose(f.view, whose)]
    if holders:
        return next((f for f in holders if f.view.id == lead.view.id), holders[0])
    if not whose and any(composer_property.held(prop, x.text) for m in members for x in m.sentences):
        return lead
    named = _your_note(lead.view)
    # A person or a business asked for is denied in the notebook's name, not by the lead note alone (R3-2).
    line = f"None of your notes give a phone number for {whose}." if whose else f"{named[:1].upper()}{named[1:]} has no {composer_property.noun(prop)}."
    out.lines.append(line)
    out.rows.append(_row(line, lead))
    return None


_PRICE_WORDS = re.compile(r"\b(?:costs?|price[sd]?|pay|paid|charge[sd]?)\b", re.I)


def _no_price(out: _Out, cue, question: str, members) -> bool:  # noqa: ANN001
    """"what does espresso cost" when no note on it holds an amount: that is
    said, not the machine's model name (R3-28)."""
    if not (isinstance(cue, _MoneyCue) and _PRICE_WORDS.search(question)) or any(cue.search(x.text) for m in members for x in m.sentences):
        return False
    named = [w for w in composer.subject_terms(clean(question)) if not _PRICE_WORDS.fullmatch(w) and w.lower() not in {"much", "does", "did", "do"}]
    out.lines.append(f"None of your {' '.join(named[:2])} notes give a price." if named else "None of your notes give a price.")
    return True


def _heard_heading(lead: Fact) -> bool:
    """A fact under a heading that says what was heard, done or planned."""
    return bool(lead.heading and (_HEARD.search(lead.label) or _DID.search(lead.label) or _PLANNED.search(lead.label)))


def _single(out: _Out, kind: str, question: str, members, facts, today: date) -> None:
    cue = _single_cue(kind, clean(question))
    lead = _best(facts, question, cue)
    if lead is None or _no_price(out, cue, question, members):
        return
    lead = _property_lead(out, question, members, facts, lead)
    if lead is None:
        return
    _no_place(out, cue, lead)
    rest = [f for f in facts if f is not lead]
    rest = _drop_tasks(kind, lead, rest, question)
    if kind == "when":
        rest = _single_when(out, lead, rest, question, today)
    elif kind == "opinion":
        rest = _single_opinion(out, lead, facts, rest, question, today)
    elif kind == "count":
        rest = _single_count(out, lead, facts, members, question, today)
    elif _heard_heading(lead):
        rest = _single_heading(out, lead, rest, today)
    else:
        _say_fact(out, lead, today, question)
        rest = [f for f in rest if f.view.id == lead.view.id and _same_label_asked(lead, f, question)]
        #: "the skeleton joke" is that one, not the noodle joke listed under it.
        stems = set(_subject(question))
        if stems - composer_jokes.CONTEXT_STEMS and composer_jokes.pick([lead], stems) is lead:
            rest = []
    _lines(out, rest, LINES.get(kind, 2))
    _single_close(out, kind, rest, members, question)


_NAME_ASKS = ("tell me about ", "what do i know about ", "what about ", "anything on ", "anything about ")


def _one_name(asked: str, names: set[str]) -> str:
    """The name in "tell me about Tom" and its kin when the notebook writes it
    as a name; empty for anything else. Word steps, no regex, so nothing here
    can go quadratic on a long run of blanks."""
    text = " ".join(asked.lower().split()).rstrip("?.! ")
    for lead in _NAME_ASKS:
        if text.startswith(lead):
            rest = text[len(lead):]
            return rest if rest.isalpha() and rest in names else ""
    return ""


def _named_in_fragment(name: str, views) -> list:  # noqa: ANN001
    """The notes that name the person only in a line too short to be a
    sentence ("Dr Patel." under an appointment): each with its opening
    sentence, which says what the name is attached to (audit 1030 Z13)."""
    seen = re.compile(rf"\b{re.escape(name)}\b", re.I)
    return [(v, v.sentences[0]) for v in views if v.sentences and seen.search(str(v.note.get("content") or ""))]


def _titled_body(view, name: str, sentence) -> str:  # noqa: ANN001
    """What a note titled with the person says, in its own words: its first
    two sentences under "Your Tom note:" (its "he" and "she" stay quoted,
    never turned into "you"), or "" when the sentence names the person."""
    if re.search(rf"\b{re.escape(name)}\b", sentence.text, re.I) or not view.title:
        return ""
    own = [x.text.strip() for x in view.sentences[:2]]
    return f"your {view.title} note: " + " ".join(t if t.endswith((".", "!", "?")) else t + "." for t in own).rstrip(".")


def _who_many(out: _Out, name: str, found: list, today: date) -> None:
    """Every note that names the person: how many, then a line from each."""
    out.lines.append(PHRASES["who_many"].format(name=_name_said(name), count=_count(len({v.id for v, _ in found})), span=_span([v for v, _ in found], today)))
    said, told = set[str](), list[str]()  # the lines read as one paragraph (L210)
    for v, s2 in found[:LINES["overview"]]:
        body = _titled_body(v, name, s2) or _tidy(_second_person(composer_refer.resolved(v, s2)), v.written)
        if not _TIMED.get() and body.lower() in said:
            continue
        said.add(body.lower())
        #: "Sara: a jazz record" means nothing without the list it sits in.
        if v.title and re.match(rf"{re.escape(name)}\s*:", body, re.I) and not _defines(v, name.split()):
            body = f"your {v.title} note has {body}"
        body = re.sub(r"^(You|Your)\b", lambda m: m.group().lower(), body)
        told.append(f"{_lead_day(v.written, today)}{body}." if _TIMED.get() else f"{body[:1].upper() + body[1:]}.")
        #: Each line cites its own note (second eye F2: one row, for the lead,
        #: stood behind sentences taken from several notes).
        out.rows.append({"sentence": body, "note_id": v.note.get("source_id", v.id), "source": s2.text, "start": s2.start, "end": s2.end, "score": 1.0, "digest": True})
    out.lines.append(" ".join(told))


def _who_found(name: str, views) -> list:  # noqa: ANN001
    """Every note that names the person, each with the sentence that does; a
    note TITLED with the name is one too even when its body says "he" and
    "she" (audit 1031 C1), with its opening sentence."""
    seen = re.compile(rf"\b{re.escape(name)}\b", re.I)
    found = [(v, s) for v in views for s in v.sentences if seen.search(s.text)]
    named = {v.id for v, _ in found}
    words = name.split()
    found += [(v, v.sentences[0]) for v in views if v.id not in named and v.sentences and _defines(v, words) == 2]
    return found or _named_in_fragment(name, views)


_PRONOUN_LEAD = re.compile(r"(?:mine|yours|it|he|she|they|his|hers|its|this|that)\b", re.I)


def _who_fact(view, s) -> str:  # noqa: ANN001
    """The sentence that names the person, as the person would say it. A line
    that opens on a pronoun ("Mine is called Doug.") has lost the thing it
    was about, so it is quoted under the note it came from (audit 1031 C31)."""
    text = composer_refer.resolved(view, s)
    if _PRONOUN_LEAD.match(text):
        said = _your_note(view)
        return f"{said[:1].upper() + said[1:]} says “{text.rstrip('.')}”"
    return _tidy(_second_person(text), view.written)


def _name_said(name: str, *, first: bool = True) -> str:
    """The name the frame says: "my landlord" is "Your landlord" (E22), not a
    quoted "My landlord", and the first letter has its capital."""
    said = re.sub(r"^my\b", "your", name, flags=re.I)
    return said[:1].upper() + said[1:] if first else said


def _role_line(view, name: str, fact: str) -> str:  # noqa: ANN001
    """"Plumber is Dave, 07700 900789" in the note titled Plumber, asked "who is Dave": "Dave is your plumber:
    07700 900789 (Plumber)." (R9-17); "" when the note does not say it that way."""
    title = str(view.title or "").strip()
    if not (view.titled and 0 < len(title.split()) <= 3):
        return ""
    found = re.match(rf"{re.escape(title)} is {re.escape(name)}\b[,:]? ?(?P<rest>.{{0,200}})$", fact[:400], re.I)
    if not found:
        return ""
    rest = found["rest"].strip().rstrip(".")
    return f"{_name_said(name)} is your {title.lower()}{': ' + rest if rest else ''} ({title})."


def _who(out: _Out, name: str, views, names: set[str], today: date) -> bool:
    found = _who_found(name, views)
    if not found:
        return False
    #: The note about the person leads, whatever order the search gave
    #: (audit 1030 Z11: "who is Sara" led with a gift list's "Sara: a jazz record").
    found.sort(key=lambda vs: -_defines(vs[0], name.split()))
    view, s = found[0]
    fact = _titled_body(view, name, s) or _who_fact(view, s)
    if len({v.id for v, _ in found}) == 1:
        role = _role_line(view, name, fact)
        out.lines.append(role or PHRASES["who_once"].format(name=_name_said(name), day=_day(view.written, today), fact=fact))
        if not role:
            out.closing.append(PHRASES["only_names"].format(name=_name_said(name, first=not name.lower().startswith("my "))))
    else:
        _who_many(out, name, found, today)
        return True
    out.rows.append({"sentence": fact, "note_id": view.note.get("source_id", view.id), "source": s.text, "score": 1.0, "digest": True})
    return True


def _aliases(sentences: list, side: str) -> set[str]:
    """What a side is called in the notes: its own word and the capitalised
    words that follow it ("Sony" then "WH-1000XM5")."""
    said = {side.lower()}
    for _, s in sentences:
        m = re.search(rf"(?i:\b{re.escape(side)})((?:\s+[A-Z0-9][\w-]*){{1,4}})", s.text)
        if m:
            said |= {w.lower() for w in m.group(1).split() if len(w) > 2}
    return said


def _about(sides: dict[str, set[str]], side: str, text: str) -> bool:
    return any(re.search(rf"\b{re.escape(w)}\b", text, re.I) for w in sides[side])


def _full_names(sentences: list, a: str, b: str) -> dict[str, str]:
    """Each side as the notes write it in full ("Sony WH-1000XM5"), for the ones found."""
    full: dict[str, str] = {}
    for side in (a, b):
        for _, s in sentences:
            m = re.search(rf"\b((?i:the\s+)?(?i:{re.escape(side)})(?:\s+[A-Z0-9][\w-]*){{0,4}})", s.text)
            if m:
                full[side] = re.sub(r"^the\s+", "", m.group(1), flags=re.I)
                break
    return full


_LEANING = re.compile(r"\b(leaning towards|prefer|decided on|going with|chose|picked)\s+(?:the\s+)?(\w+)", re.I)


def _leaning(sentences: list, sides: dict[str, set[str]], a: str, b: str, names: set[str]) -> tuple[str, object, str]:
    """The side a note leans towards, the note, and why: (side, view, why)."""
    winner, why_view, why = "", None, ""
    for v, s in sentences:
        m = _LEANING.search(s.text)
        if not m:
            continue
        for side in (a, b):
            if m.group(2).lower() in sides[side]:
                winner, why_view = side, v
                against = [x.text for x in v.sentences if x is not s and (_about(sides, a, x.text) or _about(sides, b, x.text))]
                why = "you're leaning towards it"
                if against:
                    reason = _tidy(_second_person(re.sub(r"^[^:]{2,30}:\s+", "", against[0])), v.written)
                    why += f" after {_fragment(reason, names)}"
    return winner, why_view, why


def _clause_cell(cells: dict[str, dict[str, str]], side: str, clause: str, written: date | None, sides: dict[str, set[str]], others: list[str]) -> None:
    """One clause of a note, put in the side's price or "what you found" cell."""
    alone = _about(sides, side, clause) and not any(_about(sides, o, clause) for o in others)
    price = re.search(r"\$\s?\d[\d,.]*", clause)
    if alone and price and side not in cells["Price"]:
        cells["Price"][side] = ("about " if "about" in clause else "") + price.group(0)
    elif alone and not price and not _LEANING.search(clause) and side not in cells["What you found"]:
        said = _tidy(_second_person(clause), written)
        said = re.sub(rf"^.*?\b(?:it|{re.escape(side)}\w*)\s+", "", said, count=1, flags=re.I) if len(said.split()) > 8 else said
        cells["What you found"][side] = said


def _side_cells(cells: dict[str, dict[str, str]], side: str, sentences: list, sides: dict[str, set[str]], a: str, b: str, today: date) -> None:
    """What the notes say of one side, put in its column of the table."""
    named = [(v, s) for v, s in sentences if _about(sides, side, s.text)]
    for v, s in named:
        for clause in re.split(r"\s+and\s+(?=the\s)|;\s*|:\s+", s.text.strip().rstrip(".")):
            _clause_cell(cells, side, clause, v.written, sides, [o for o in (a, b) if o != side])
    days = sorted(v.written for v in {v.id: v for v, _ in named}.values() if v.written)
    count = len({v.id for v, _ in named})
    cells["In your notes"][side] = f"{_count(count)}, last on {_day(days[-1], today)}" if days else _count(count)


def _compare_table(sentences: list, sides: dict[str, set[str]], full: dict[str, str], a: str, b: str, today: date) -> str:
    """Decision 71: a comparison is a table, a column a side, a row a thing
    the notes say of both (the price, what you found, how often it comes
    up), so the two can be read across rather than one after the other."""
    cells: dict[str, dict[str, str]] = {"Price": {}, "What you found": {}, "In your notes": {}}
    for side in (a, b):
        _side_cells(cells, side, sentences, sides, a, b, today)
    #: A row the same on both sides compares nothing; it is left out.
    rows = [(name, got) for name, got in cells.items() if got and not (len(got) == 2 and got[a] == got[b])]
    if not rows:
        return ""
    head = f"| | {full[a]} | {full[b]} |"
    body = [f"| {name} | {got.get(a, 'nothing yet')} | {got.get(b, 'nothing yet')} |" for name, got in rows]
    return "\n".join([head, "| --- | --- | --- |", *body])


def _compare(out: _Out, a: str, b: str, views, today: date, names: set[str]) -> bool:  # noqa: ANN001
    sentences = [(v, s) for v in views for s in v.sentences]
    sides = {a: _aliases(sentences, a), b: _aliases(sentences, b)}
    full = _full_names(sentences, a, b)
    if len(full) < 2:
        return False
    winner, why_view, why = _leaning(sentences, sides, a, b, names)
    if not winner:
        return False
    out.lines.append(PHRASES["pick"].format(side=winner[:1].upper() + winner[1:], why=why))
    out.offer = _note_offer(PHRASES["pick_note"].format(side=winner[:1].upper() + winner[1:]), f"My pick: the {full[winner]}")
    out.rows.append({"sentence": why, "note_id": why_view.note.get("source_id", why_view.id), "source": why, "score": 1.0, "digest": True})
    table = _compare_table(sentences, sides, full, a, b, today)
    if table:
        out.lines.append(table)
    return True


def _states_it(dated: list, abbr: str, phrase: str):  # noqa: ANN202
    """The note that gives the abbreviation's phrase, and its sentence, as
    (view, sentence, said outright); None when no note does. A note that
    holds both the phrase and the abbreviation is preferred."""
    holds = [v for v in dated if phrase.lower() in str(v.note.get("content") or "").lower()]
    both = [v for v in holds if re.search(rf"\b{re.escape(abbr)}\b", str(v.note.get("content") or ""))]
    view = (both or holds or [None])[0]
    if view is None:
        return None
    sentence = next((s for s in view.sentences if phrase.lower() in s.text.lower()), view.sentences[0] if view.sentences else None)
    return None if sentence is None else (view, sentence, bool(both))


def _stands_for(out: _Out, abbr: str, views: list, today: date) -> bool:
    """"What does CC stand for?" from the person's own notes (B7): the
    phrase their notes give it, the note that says so, and how much they
    use it. Never a dictionary's reading."""
    phrase = glossary.learn(str(v.note.get("content") or "") for v in views).get(abbr)
    dated = sorted(views, key=lambda v: (v.written or date.min, v.rank))
    found = _states_it(dated, abbr, phrase) if phrase else None
    if found is None:
        return False
    view, sentence, both = found
    #: Said outright ("Cloud Computing (CC)") or only seen beside it: the
    #: second is a reading, and the answer says so.
    line = PHRASES["stands_for" if both else "stands_for_seen"].format(abbr=abbr, phrase=phrase, name=_your_note(view), day=_day(view.written, today))
    out.lines.append(line[:1].upper() + line[1:])
    out.rows.append(_row(line.rstrip("."), Fact(view, sentence, "", phrase)))
    using = [v for v in dated if re.search(rf"\b{re.escape(abbr)}\b", str(v.note.get("content") or ""))]
    if len(using) > 1 and using[-1].written:
        out.closing.append(PHRASES["uses"].format(abbr=abbr, count=_count(len(using)), day=_day(using[-1].written, today)))
    return True


@_isolated
def all_said(question: str, notes: list[dict], *, today: date | None = None, voice: str = "natural") -> dict | None:
    """"Tell me more" when the answer before said everything (B8): that it
    did, how many notes and over which days, rather than "Nothing in the
    notes found answers that" about a topic it has just answered."""
    today = today or composer.user_today()
    asked = clean(question)
    views = [v for v in (composer.read_note(n, i) for i, n in enumerate(composer._distinct_ids(notes or []))) if v]
    members = _members(asked, views) if asked and views else []
    if not members:
        return None
    _TODAY.set(today)
    _VOICE.set(voice if voice in VOICES else "natural")
    _set_timing(question)
    out = _Out()
    line = PHRASES["all_said"].format(topic=_topic(asked, members), count=_count(len(members)), span=_span(members, today))
    out.lines.append(line)
    first = min(members, key=lambda v: (v.written or date.min, v.rank))
    if first.sentences:
        out.rows.append(_row(line.rstrip("."), Fact(first, first.sentences[0], "", "")))
    return _result(out, "more", asked)


#: `_early` found nothing special in the question: the ordinary answer follows.
_ORDINARY = object()


def _begin(question: str, asked: str, notes: list[dict], today: date, voice: str, turn: int, known) -> list:  # noqa: ANN001
    """Read the route's notes and set what this answer's helpers read; the
    notes, or none when there is nothing to answer from."""
    views = [v for v in (composer.read_note(n, i) for i, n in enumerate(composer._distinct_ids(notes or []))) if v]
    if not views:
        return []
    _NAMES.set(_capitalised_inside(views))
    _TODAY.set(today)
    _set_timing(question)
    _VOICE.set(voice if voice in VOICES else "natural")
    _TURN.set(turn)
    _SEED.set(zlib.crc32(asked.lower().encode()))
    _GAPS.set(())
    _VIEWS.set(views)
    _KNOWN.set(known)
    _ASKS_WORDS.set(bool(re.search(r"\b(?:says?|said|reads?|written|text|words?|wording)\b", question, re.I)))
    return views


def _compared(out: _Out, asked: str, views: list, names: set[str], today: date) -> dict | None:
    m = _ASKS["compare"].search(asked)
    if not _compare(out, m.group("a").strip(), m.group("b").strip(), views, today, names):
        return None
    want = next((f for f in (f for v in views for f in _facts(v, names)) if f.label == "What you want"), None)
    if want:
        out.lines.append(f"You want it {want.body}; nothing says which one meets that.")
    return _result(out, "compare", asked)


def _person_asked(asked: str, names: set[str], views: list) -> str:
    """The name "tell me about Tom" asks after; empty when the word is one
    notes are tagged or filed under ("Golf"), which is a topic, not a person."""
    said = _one_name(asked, names)
    stem = composer._stem(said) if said else ""  # noqa: SLF001
    if not said or any(stem in v.filed_words for v in views):
        return ""
    #: "tell me about Lisbon": a name the notes go to, stay in or fly from,
    #: and never speak with, is a place, answered as a topic (audit 1029
    #: C15 residue: it took the who shape).
    texts = [s.text for v in views for s in v.sentences if said in s.text.lower()]
    place = re.compile(rf"\b(?:to|in|from|at|near|around|visit|visiting|visited) {re.escape(said)}\b|\b{re.escape(said)} (?:trip|holiday|flight|flat|hotel)\b", re.I)
    person = re.compile(
        rf"\b(?:with|call|called|text|texted|email|emailed|ask|asked|told|tell|met|meet|thank|thanked) {re.escape(said)}\b"
        rf"|\b{re.escape(said)} (?:said|says|told|asked|thinks|wants|wanted|called|texted|emailed|is coming|came)\b",
        re.I,
    )
    if any(place.search(t) for t in texts) and not any(person.search(t) for t in texts):
        return ""
    return said


def _looked_up(out: _Out, asked: str, question: str, views: list, today: date) -> bool:
    """An abbreviation, a slot, an amount or a computed day said (True)."""
    abbr = glossary.asked(question)
    if abbr and _stands_for(out, abbr, views, today):
        return True
    return _exact_lookup(out, asked, question, views, today)


def _exact_lookup(out: _Out, asked: str, question: str, views: list, today: date) -> bool:
    """The figures the notes hold, worked exactly: a slot, an amount, a sum,
    a day or a count, said (True)."""
    #: A superlative over a table, a count of a list, a distance on a day (R9-10).
    if composer_tally.answer(out, asked, views) or composer_credit.answer(out, asked, views) or composer_label.answer(out, asked, views) or composer_each.answer(out, asked, views):
        return True
    #: The question's slot (a tick, an open task, a dated line) is what
    #: answers it, or the answer says no note holds it (audit 1029 rank 19).
    if composer_money.sums_a_measure(question) and composer_money.answer(out, question, views, today):
        return True
    if composer_sum.most(out, question, views, today):
        return True
    if composer_nth.answer(out, asked, views) or composer_slots.answer(out, asked, views, today) or composer_money.answer(out, question, views, today):
        return True
    if composer_sum.answer(out, question, views, today):
        return True
    #: A day, a count or a filing worked out from the notes (probes P10 to
    #: P13); when the notes do not hold what it needs the ordinary shapes
    #: still answer.
    computed = composer_lists.computed_kind(asked)
    return bool(computed and composer_lists.answer(out, computed, asked, views, today))


_DENIAL = re.compile(r"(?:I found (?:no|nothing)|None of (?:your|these) notes|Your notes do not|There's nothing in your notes|No note )", re.I)


@_isolated
def exact(question: str, notes: list[dict], *, today: date | None = None) -> dict | None:
    """The engine's exact answer to a question over `notes`, as an answer
    result, when it is one a figure or a tick settles (an amount, a sum, a
    day, a checklist's state); None otherwise. A model writing the reply is
    handed these lines as facts, so the figure is the engine's with a model
    on and off alike (second eye F6, CHAT_PLAN decision 75). Its lines only:
    no closing, offer or chips."""
    today = today or composer.user_today()
    asked = composer_ask.what_is(clean(question))
    if _kind_if_mine(asked) is None or composer._lead_act_verb(question):  # noqa: SLF001
        return None
    views, _ = _scope(question, asked, notes, today, "natural", 0, None)
    out = _Out()
    if not views or not _exact_lookup(out, asked, question, views, today):
        return None
    #: A "found nothing" is not a fact a model must keep: it is handed the notes instead (R9-13).
    if out.lines and _DENIAL.match(out.lines[0]):
        return None
    out.closing, out.offer, out.next, out.insights = [], None, [], []
    return _result(out, "fact", asked)


_HOW_MET = re.compile(r"^(?:how|where|when) (?:did|do) (?:i|we) (?:first )?(?:meet|know|get to know) (?P<name>.+?)(?: (?:again|from|first))*$", re.I)


#: "Which note mentions Dr Patel": the notes that name someone, which is what
#: "who is" lists; so it is said that way (audit 1030 Z13).
_WHICH_NAMES = re.compile(
    r"^which (?:of my )?(?:notes?|entries|entry) (?:mentions?|names?|has|have|contains?|says? anything about|talks? about|refers? to)"
    r" (?!the (?:word|phrase)\b)(?:(?:the|a|an|my) )?(?P<name>[\w.' -]{2,40})$",
    re.I,
)


def _which_names(kind: str, asked: str) -> tuple[str, str]:
    """A "which note mentions X" ask as the "who is X" lookup it is."""
    m = _WHICH_NAMES.match(asked.strip(" ?.!")) if kind != "who" else None
    return ("who", f"who is {m.group('name').strip()}") if m else (kind, asked)


#: "how many cells", "number of cells": one counted noun and nothing else.
_COUNTED = re.compile(r"^(?:how many|(?:the )?number of) (?P<noun>[a-z]{3,})(?: (?:do i have|are there|have i got))?$", re.I)
#: Nouns other readers count (notes, words, days): never answered here.
_COUNTED_ELSEWHERE = frozenset({"notes", "entries", "words", "characters", "letters", "sentences", "days", "weeks", "months", "years", "hours", "minutes", "nights", "times", "items", "tasks", "reminders", "lists", "files", "documents", "boards", "pictures", "tags", "categories", "things"})


def _count_of_unwritten(asked: str, views: list) -> str:
    """"how many cells" when no note says the word: its synonym ("cell" is a
    phone) must not stand in, so the answer is that none does (R3-6). When
    notes say it and none gives a figure for it ("3 ripe bananas"), the count
    is of the notes that mention it, never one note's line (R3-5)."""
    m = _COUNTED.match(clean(asked).strip(" ?.!"))
    noun = m.group("noun").lower() if m else ""
    if not noun or noun in _COUNTED_ELSEWHERE:
        return ""
    stems = composer._words(noun)  # noqa: SLF001
    if not stems:
        return ""
    mentioning = [v for v in views if any(st in _pool(v) for st in stems)]
    if not mentioning:
        return f"None of your notes mention {noun}."
    #: A figure beside the noun ("3 ripe bananas", "two phones") is the amounts reader's, not a count of notes.
    figure = re.compile(rf"\b(?:\d[\d.,]*|{'|'.join(realise._NUMBERS)})\s+(?:[\w-]+\s+){{0,2}}{re.escape(noun.rstrip('s'))}", re.I)  # noqa: SLF001
    if any(figure.search(str(v.note.get("content") or "")) for v in mentioning):
        return ""
    if len(mentioning) == 1:
        return f"One of your notes mentions {noun}."
    return f"{realise.count_word(len(mentioning)).capitalize()} of your notes mention {noun}."


_MY_LIST = re.compile(r"^what(?:'s| is| are)? (?:on|in) (?:my|the) (?:check ?)?lists?$", re.I)


_LIST_ITEM_LINE = re.compile(r"(?:[-*+]|\d{1,3}[.)])\s|\[[ xX]\]")


def _list_title(note: dict) -> str:
    """The name of a note that is a list: a title over at most two lines of
    intro and then two or more items, nothing after them; "" for any other."""
    content = str(note.get("content") or "")
    title = composer_frame.title_line(content)
    lines = [ln.strip() for ln in content.splitlines() if ln.strip()][1:]
    kinds = [bool(_LIST_ITEM_LINE.match(ln)) for ln in lines]
    first = kinds.index(True) if True in kinds else len(kinds)
    return title if title and first <= 2 and len(kinds) - first >= 2 and all(kinds[first:]) else ""


def _which_list(out: _Out, asked: str, notes: list) -> bool:
    """"what is on my list" with several lists to be meant: asked which, with
    each as a chip, rather than the first one picked (R3-8). A list may open
    with a line of intro."""
    if not _MY_LIST.match(clean(asked).strip(" ?.!")):
        return False
    names = [n for n in (_list_title(note) for note in notes) if n]
    if len(names) < 2:
        return False
    names = names[:4]
    out.lines.append(f"Which list: {', '.join(names[:-1])} or {names[-1]}?")
    out.next = [f"What is in {n}?" for n in names[:3]]
    return True


def _asked_which(out: _Out, asked: str, views: list) -> bool:
    """The short answers that need no note read: how many notes mention the
    thing counted, and that none does (R3-5, R3-6)."""
    none = _count_of_unwritten(asked, views)
    if none:
        out.lines.append(none)
    return bool(none)


def _as_who(kind: str, asked: str, names: set[str], views: list) -> tuple[str, str]:
    """"tell me about Tom" is "who is Tom": a name has one answer shape (audit
    1029 C17), never an attendee list read as a count. "How did I meet Mia" is
    too: the note that says who she is answers it, never one that only shares
    the verb ("we meet on Thursdays")."""
    met = _HOW_MET.match(asked.strip(" ?.!"))
    #: One meets a person: a name asked so is one even when notes are
    #: tagged with it (#mia), which `_person_asked` reads as a topic.
    said = met.group("name").lower() if met else ""
    said = said if said.isalpha() and said in names else ""
    if said or (kind == "overview" and (said := _person_asked(asked, names, views))):
        return "who", f"who is {said}"
    return kind, asked


def _no_number(out: _Out, question: str, views: list) -> bool:
    """"what is the table number" when no note gives one: said so, not answered with a
    note that only mentions the dinner or the booking (R3-2 residue)."""
    key = composer_property.asked(question)
    if key not in composer_property.NUMBERED or any(composer_property.held(key, x.text) for v in views for x in v.sentences):
        return False
    out.lines.append(f"None of your notes give a {composer_property.noun(key)}.")
    return True


def _early(out: _Out, kind: str, asked: str, question: str, views: list, today: date):  # noqa: ANN202
    """The answers that are one notebook-wide lookup (what an abbreviation
    stands for, who someone is, a comparison, what a category holds): the
    result, None when the ask fits but nothing answers it, or `_ORDINARY`."""
    names = _NAMES.get()
    if _no_number(out, question, views) or composer_assign.answer(out, asked, views, today) or _looked_up(out, asked, question, views, today) or _asked_which(out, asked, views):
        return _result(out, "fact", asked)
    kind, asked = _which_names(kind, asked)
    kind, asked = _as_who(kind, asked, names, views)
    if kind == "who":
        name = _ASKS["who"].search(asked).group("name").strip()
        return _result(out, kind, asked) if _who(out, name, views, names, today) else None
    if kind == "compare":
        return _compared(out, asked, views, names, today)
    if about_this(asked) or named_category(asked, list({str(v.note.get("category") or "") for v in views})):
        #: The route sent only what is open, or the category named (B10):
        #: every note is the subject.
        return _this(out, views, names, today, asked)
    return _ORDINARY


def _compose_body(out: _Out, kind: str, asked: str, members: list, facts: list[Fact], today: date) -> bool:
    """The lines of the answer proper; False when there are none to say."""
    many = kind in ("overview", "likes") and len(members) >= 2
    if many:
        _overview(out, asked, members, facts, today, kind)
    elif kind in ("overview", "likes") and (told := _narrate(out, members[0], facts, today)):
        #: One note with an event: told as what happened, then the rest.
        _lines(out, [f for f in facts if f.sentence.key not in told], 2)
        if asks_for_a_topic(asked):
            out.lines.append(PHRASES["only_note"])
    elif kind in ("overview", "likes"):
        _single(out, "fact", asked, members, facts, today)
    else:
        _single(out, kind, asked, members, facts, today)
    if not out.lines:
        return False
    missing = _missing(members, asked) if many and not out.framed else ""
    if missing:
        #: Under a fold it closes the answer, never sits between the lines
        #: shown and the lines folded (composer-1031).
        (out.closing.insert(0, missing) if out.more else out.lines.append(missing))
    return True


def _finish(out: _Out, kind: str, asked: str, members: list, facts: list[Fact], tie, notes: list[dict], today: date, insight: str, learned) -> dict:  # noqa: ANN001
    """What follows the lines: the tie's question, or the insights a broad
    answer volunteers, then the one offer."""
    if tie:
        _tie_closing(out, asked, members, tie[1], tie[2])
    elif kind in ("overview", "likes"):
        _confirmed_first(out, asked, members, learned)
        #: A woven overview closes on its own cited insight (INBOX 1743); the
        #: volunteered rules speak when it has none.
        if out.spare and insight != "off":
            out.closing.append(out.spare[0])
            out.rows.append(out.spare[1])
        else:
            _volunteer(out, asked, members, notes, today, insight, learned)
    #: A fact answer ("what is the Krebs cycle") offers a to-do only when it is
    #: about it; an overview of notes that hold an open task still offers it.
    out.offer = out.offer or _offer(_answered(out, facts), asked if kind == "fact" else None) or _kind_offer(kind, asked, members, facts, today, out)
    return _result(out, kind, asked)


def _scope(question: str, asked: str, notes: list[dict], today: date, voice: str, turn: int, known) -> tuple[list, bool]:  # noqa: ANN001
    """The notes the answer reads, and whether the question asks for the
    context notes (jokes, quotes) that are otherwise left out."""
    views = _begin(question, asked, notes, today, voice, turn, known)
    wants_context = bool(set(composer._words(asked)) & {composer._stem(t) for t in CONTEXT_TAGS})
    return (views if wants_context else [v for v in views if not _context_note(v)]), wants_context


def _title_holds(view, words: list[str]) -> bool:  # noqa: ANN001
    """Whether the note's title has every word of the subject in it."""
    held = getattr(view, "title_words", None)
    return bool(held) and all(composer._holds(composer._stem(t), held) for t in words)  # noqa: SLF001


def _defines(view, words: list[str]) -> float:
    """How plainly `view` is the note about `words`: 2 when its title is the
    subject ("Sara", "Uni"), 1 when an opening sentence says what it is
    ("Sara is my sister") or it is filed under the subject, else 0 (a passing
    mention). Saying what it is (1.5) outranks being filed under it (1)."""
    #: "Tell me one of my jokes": the top matching record is the one said (`composer_jokes`).
    if composer_jokes.only_context(words):
        return 0
    title = re.sub(r"^(?:the|my|a|an)\s+", "", (view.title or "").strip().lower()) if getattr(view, "titled", False) else ""
    if title and (title == " ".join(words).lower() or composer._words(title) == composer._words(" ".join(words))):
        return 2
    said = re.compile(r"^(?:the\s+)?" + r"\s+".join(re.escape(t) for t in words) + r"\s+(?:is|are|was|were|means|refers to)\b", re.I)
    #: A title that holds every word of the subject ("Meeting with Priya", "Weekend plans") is the note about it,
    #: ahead of a sentence that merely says something (R3-20, D1).
    if title and _title_holds(view, words):
        return 1.8
    #: Filed under the subject (its category, its tag) is a definition too
    #: (audit 1031 C4: the Books note leads "what do I know about reading").
    filed = bool(getattr(view, "filed_words", None)) and all(composer._stem(t) in view.filed_words for t in words)  # noqa: SLF001
    #: Saying what it is outranks being filed under it: the note that defines
    #: "cloud computing" leads the lectures tagged with it.
    if any(said.match(x.text) for x in view.sentences[:2]):
        return 1.5
    return 1 if filed else 0


def _defining_first(asked: str, members: list) -> list:
    """The note named for the subject, or the one that says what the subject
    is ("Cloud computing is the delivery of ..."), leads ahead of a passing
    mention the search ranked higher (INBOX 1420; audit 1030 Z11: "summarise
    everything about uni" led with "Just missed the bus to uni")."""
    terms = composer.subject_terms(clean(asked))
    if not terms or len(members) < 2:
        return members
    #: As typed: the subject may come back widened ("uni" to "university").
    typed = [w for w in re.findall(r"[\w'-]+", asked.lower()) if any(t.startswith(w) or w.startswith(t) for t in terms)]
    rank = {id(v): max(_defines(v, terms), _defines(v, typed)) for v in members}
    best = max(rank.values())
    if not best:
        return members
    return _lead_then_rest(members, rank, best, terms)


def _lead_then_rest(members: list, rank: dict, best: int, terms: list[str]) -> list:
    """The defining note first, then the rest by rank, the ones that only name the subject as a place last."""
    #: Of notes titled alike ("Kitchen renovation", "Kitchen quotes"), the fuller one leads (R9-3).
    lead = max((v for v in members if rank[id(v)] == best), key=lambda v: len(v.sentences))
    rest = [v for v in members if v is not lead]
    #: A note that says the subject only as a place ("in the kitchen drawer") is a mention, told last (R9-3).
    place = {id(v) for v in rest if not rank[id(v)] and _only_a_place(v, terms)}
    return [lead] + sorted((v for v in rest if id(v) not in place), key=lambda v: -rank[id(v)]) + [v for v in rest if id(v) in place]


_PLACE_BEFORE = re.compile(r"\b(?:in|under|on|near|from|to|inside|behind|at|by) (?:the |my |our )?(?:\w+ )?$", re.I)


def _in_a_place(text: str, stems: set[str]) -> bool:
    """Whether every place `text` says a subject word is a place something is in ("the card in the kitchen drawer")."""
    seen = False
    for m in re.finditer(r"[A-Za-z']+", text):
        if composer._stem(m.group(0).lower()) in stems:  # noqa: SLF001
            seen = True
            if not _PLACE_BEFORE.search(text[: m.start()]) or not re.match(r"\s+(?:drawer|sink|cupboard|shelf|table|door|window|floor|wall|corner)\b", text[m.end():], re.I):
                return False
    return seen


def _only_a_place(view, terms: list[str]) -> bool:  # noqa: ANN001
    """Whether `view` says the subject only as a place (R9-3)."""
    stems = {composer._stem(t) for t in terms}  # noqa: SLF001
    held = [s.text for s in view.sentences if any(composer._stem(w.lower()) in stems for w in re.findall(r"[A-Za-z']+", s.text))]  # noqa: SLF001
    return bool(held) and all(_in_a_place(t, stems) for t in held)


def _corrected_first(asked: str, members: list) -> list:
    """A newer note that corrects the subject leads ahead of the older note
    it corrects (stress run 2026-10-30: "when's my dentist appointment now"
    gave the first booking, beside "Moved the dentist appointment to 4
    November")."""
    if len(members) < 2 or not members[0].written:
        return members
    lead = members[0]
    later = [v for v in composer_select.correcting(composer.subject_terms(clean(asked)), members) if v.written > lead.written]
    if not later:
        return members
    newest = max(later, key=lambda v: v.written)
    return [newest] + [v for v in members if v is not newest]


def _named_checklist(kind: str, asked: str, members: list):  # noqa: ANN202
    """The note the question names when that note is nothing but a checklist
    and the question asks for it plainly ("what is the checklist note", "tell
    me about gear"), else None: its list is shown with its ticks
    (`_show_checklist`), never quoted as a lead fact with "Also" the rest."""
    named = _named_note(kind, asked, members)
    if named is None:
        return None
    tasks = [s for s in named.sentences if s.kind == "task"]
    return named if len(tasks) >= 2 and len(tasks) == len(named.sentences) else None


def _named_note(kind: str, asked: str, members: list):  # noqa: ANN202
    """The one note a plain question names by its heading, else None."""
    if kind not in ("fact", "overview") or not members:
        return None
    stems = _subject(asked)
    #: "the gear list" names Gear; "list" and "checklist" only say what kind.
    needed = [st for st in stems if st not in _KIND_WORDS] or stems
    named = [v for v in members if needed and all(composer._holds(st, v.title_words) for st in needed)]
    return named[0] if len(named) == 1 else None


#: "What's in", "what goes in", "what do I need for": a question for what a
#: note holds, which a list note answers whole (audit 1030 Z46).
_HOLDS_ASK = re.compile(r"^\W*what(?:'s| is| goes| go)? in(?:to)?\b|^\W*what do (?:i|you) need (?:for|to make)\b|\bingredients\b", re.I)


def _named_list(kind: str, asked: str, members: list) -> bool:
    """Whether the question asks what a list note holds: the composer says
    the list whole and counted ("lists four: onions, carrots, ..."), where a
    digest said one entry then "Also" the rest (audit 1030 Z46)."""
    if kind not in ("fact", "overview") or not _HOLDS_ASK.search(asked):
        return False
    named = _named_note(kind, asked, members) or (members[0] if len(members) == 1 else None)
    items = [s for s in named.sentences if s.kind in ("item", "task")] if named else []
    return len(items) >= 2 and len(items) >= len(named.sentences) - 1


def _show_checklist(out: _Out, view: composer.NoteView) -> None:
    """A checklist note as the list it is: how many are ticked, then every
    item with its box, as the composer's own list block does."""
    tasks = [s for s in view.sentences if s.kind == "task"]
    #: A box never ticked but done in a later note is done here too, said as
    #: that note: one item, one state (fable-eye F15).
    #: The answer's day, never the server's clock (audit 1030 Z: tests fix the clock).
    views, today = _VIEWS.get(), _TODAY.get() or view.written or date.min
    later = composer_done.done_later(views, view, tasks)
    ticked = sum(1 for s in tasks if s.done or id(s) in later)
    total = realise.count_word(len(tasks))
    name = _your_note(view)
    done = f"{realise.count_word(ticked)} of {total}" if ticked else f"none of its {total}"
    opening = f"{name[0].upper()}{name[1:]} has {done} checklist items done"
    boxes = [
        f"- [{'x' if s.done else ' '}] {s.text[:1].upper()}{s.text[1:]}"
        + (composer_done.done_later_note(later[id(s)], today) if id(s) in later else "")
        for s in tasks
    ]
    out.lines.append(opening + ":\n\n" + "\n".join(boxes))
    out.rows.append({"sentence": opening, "note_id": view.note.get("source_id", view.id), "source": tasks[0].text,
                     "start": tasks[0].start, "end": tasks[0].end, "score": 1.0, "digest": True,
                     "kind": getattr(view, "kind", "note")})


_KIND_WORDS = frozenset({"list", "checklist", "note", "tasklist"})


def _pick_members(asked: str, views: list, wants_context: bool) -> list:
    """The notes the question is about, oldest first; jokes and quotes in the search's order, so
    the top matching record is the one said (the owner's 2026-10-10 jokes bug, L-chat-19)."""
    if wants_context:
        members = [v for v in views if _context_note(v) or any(composer._holds(st, v.words) for st in composer._words(asked))]
        return sorted(members, key=lambda v: v.rank)
    members = _members(asked, views)
    members.sort(key=lambda v: (v.written or date.min, v.rank))
    return members


def _tie_closing(out: _Out, asked: str, members: list, other: str, others: list) -> None:
    topic = _topic(asked, members)
    out.closing.insert(0, PHRASES["tie"].format(topic=topic, category=other, count=_count(len(others))))
    out.next.append(PHRASES["tie_chip"].format(topic=topic, category=other))


def _kind_if_mine(asked: str) -> str | None:
    """The question's kind, or None when the digest should not answer it: an
    empty question, or two things named ("Lisbon vs Porto", "how does A differ
    from B"), which the composer's side-by-side answers; a digest of the best
    note would say one side and drop the other."""
    if not asked or composer.asks_written_when(asked):
        return None  # a note's own day is the composer's, not a digest of its words (E6)
    kind = kind_of(asked)
    return None if kind != "compare" and composer.compare_sides(asked) else kind


def _chosen(asked: str, kind: str, views: list, wants_context: bool, question: str = "") -> tuple[list, tuple | None]:
    """The notes the answer is about, the defining one first, and the tie an
    overview splits on (None when there is none)."""
    members = composer_close.close_by_meaning(kind, question or asked, views, _corrected_first(asked, _defining_first(asked, _pick_members(asked, views, wants_context))))
    tie = _tie(asked, members) if members and kind == "overview" else None
    return (tie[0] if tie else members), tie


@_isolated
def _routed_away(question: str, notes: list[dict], today: date) -> tuple:
    """(reply, question, asked) for the asks that are not a digest: `reply` is
    the answer (None for "not this shape"), or `_ORDINARY` with the question's
    slips put right and its ask read, for `answer` to digest."""
    from tessellate.ai import composer_intent

    #: What is on a named day is one answer, however asked: the recall's (R3-8).
    if composer_intent.asks_the_day(question, today):
        return None, question, None
    #: "who is older, Anna or Tom" compares the ages the notes give, or says they do not (E9).
    if aged := composer_ages.read(question, notes, today.year):
        return _plain_result(*aged), question, None
    if missing := composer_ages.no_todo(question, notes):
        return _plain_result(missing, None), question, None
    if one := composer_oneword.named(question, notes):
        return _one_word_result(one), question, None
    #: "The first note I wrote about Sara" ranks that subject's notes by day (R3-4).
    if ranked := composer_small.ordinal_about(question, notes, today=today):
        return ranked, question, None
    #: "Where did I write about squats" is a sentence naming the note (A22), not a digest of what it says.
    if located := composer_small.where_written(question, notes, today=today):
        return located, question, None
    #: "wen is the exam" is "when is the exam": the asking words put right, the notes' own words never changed (R3-17).
    question = question_noise.slips_only(question, known=composer._note_words(notes))  # noqa: SLF001
    asked = composer_ask.what_is(clean(question))
    #: "what is on my list": which of several lists (R3-8), or the one there is.
    which = _Out()
    if _which_list(which, asked, notes):
        return _result(which, "fact", asked), question, asked
    return _ORDINARY, question, asked


@_isolated
def answer(question: str, notes: list[dict], **kwargs) -> dict | None:  # noqa: ANN003
    """The decision-70 answer to `question` from the route's `notes`, or None
    when the question is not one this shape answers (a sum, a time, a
    command, nothing found): the caller then asks `composer.compose`. Read with
    the notes' words set, as `compose` does: "tom and sara" is two subjects
    only when the notes hold both words."""
    composer_overview.read_pool(notes)
    owned = composer_ask.NOTE_WORDS.set(composer._note_words(notes))  # noqa: SLF001
    texts = composer_ask.NOTE_TEXTS.set(tuple(f"{n.get('title') or ''} {n.get('content') or ''}" for n in notes or ()))
    as_asked = _ASKED_AS.set(question)
    called = composer_aliases.enter(question, notes)
    named = composer_ask.NOTE_CATEGORIES.set(frozenset(re.sub(r"\s+", " ", re.sub(r"\band\b", "&", str(n.get("category") or "").lower())) for n in notes or () if n.get("category")))
    try:
        return composer_event_verdict.answer(question, lambda q: _answer(q, notes, **kwargs), kwargs.get("today") or composer.user_today())
    finally:
        _ASKED_AS.reset(as_asked)
        composer_ask.ALIASES.reset(called)
        composer_ask.NOTE_CATEGORIES.reset(named)
        composer_ask.NOTE_TEXTS.reset(texts)
        composer_ask.NOTE_WORDS.reset(owned)


def _answer(
    question: str, notes: list[dict], *, today: date | None = None, voice: str = "natural", turn: int = 0,
    insight: str = "one", learned=None, known=None,  # noqa: ANN001
) -> dict | None:
    today = today or composer.user_today()
    reply, question, asked = _routed_away(question, notes, today)
    if reply is not _ORDINARY:
        return reply
    kind = _kind_if_mine(asked)
    kind = "overview" if kind == "fact" and composer_jokes.wants_all(question) else kind
    #: An act ("rename my gym log") is not a topic to digest: with its verb off
    #: the subject, it would find the gym log and summarise it.
    if kind is None or composer._lead_act_verb(question):
        return None
    views, wants_context = _scope(question, asked, notes, today, voice, turn, known)
    if not views:
        return None
    names = _NAMES.get()
    out = _Out()
    _SUBJECT_STEMS.set(frozenset(_subject(asked)))
    early = _early(out, kind, asked, question, views, today)
    if early is not _ORDINARY:
        return early
    members, tie = _chosen(asked, kind, views, wants_context, question)
    if _named_list(kind, asked, members):
        return None
    if checklist := _named_checklist(kind, asked, members):
        _show_checklist(out, checklist)
        return _result(out, "fact", asked)
    facts = _subject_facts(members, names, set(_subject(asked)), kind)
    if not facts:
        return None
    if kind == "left":
        return _result(out, kind, asked) if _left(out, asked, members, views, names, today) else None
    if not _compose_body(out, kind, asked, members, facts, today):
        return None
    return _finish(out, kind, asked, members, facts, tie, notes, today, insight, learned)


#: Volunteered insight (CHAT_PLAN decision 73): "off", "one" line, or "all"
#: as found. What it may say: a pattern, a plan gone quiet, a change of mind,
#: from `ai/insights`' measured rules, each over these notes only.
INSIGHT_LEVELS = ("off", "one", "all")
#: How much of an insight must rest on the notes the answer is about, before
#: any dismissal; each "Not right" raises it, so a person who keeps
#: dismissing hears fewer, and only the closest.
INSIGHT_BAR = 0.5
INSIGHT_STEP = 0.1


def insight_bar(learned) -> float:  # noqa: ANN001
    dismissed = len(getattr(learned, "dismissed", ()) or ())
    return min(1.0, INSIGHT_BAR + INSIGHT_STEP * dismissed)


def _restates(item, said: str) -> bool:  # noqa: ANN001
    """Whether an insight quotes a note the answer has already told: "Since 9
    August, no later note picks up this plan: need to lock-in for my
    assignments" after the line that said it says one note twice (INBOX 1665 f)."""
    payload = str((getattr(item, "slots", None) or {}).get("plan") or str(getattr(item, "text", "")).split(". ")[0].rpartition(": ")[2]).lower()
    words = set(re.findall(r"[a-z]{4,}", payload))
    return len(words) >= 3 and sum(w in said for w in words) / len(words) >= 0.6


def _old_news(item, members, said: str) -> bool:  # noqa: ANN001
    """Whether the opening already said what `item` says: "you have written
    about uni 4 times" after "You have four notes about uni" says nothing
    new, and a "N times" that is not the opening's count would be a second,
    disagreeing count of the same subject (C6). A hobby forming is the one
    exception to the first: the count is old news, the hobby is not."""
    if _restates(item, said):
        return True
    if item.rule not in ("recurrence", "streak"):
        return False
    if item.slots.get("hedge") == composer_tables.INSIGHT_HEDGES["hobby"]:
        return False
    count = int(item.slots.get("count") or 0)
    #: Its own count too: "ten notes" then "10 times" said one count twice (1461).
    said_counts = {realise.count_word(len(members)), realise.count_word(count)}
    if any(re.search(rf"\b{c}\b", said, re.I) for c in said_counts):
        return True
    return item.rule == "recurrence" and _opening_count(said) not in (None, count)


def _scored_insights(found: list, ids: set, members, said: str, learned) -> list:  # noqa: ANN001
    """The insights worth saying as (relevance, item), best first: not
    dismissed, not what the person ruled out, not news the opening gave, and
    resting enough on the answer's own notes."""
    from tessellate.ai import insights

    dismissed = getattr(learned, "dismissed", frozenset()) or frozenset()
    known = _KNOWN.get()
    scored = []
    for item in found:
        if insights.key(item) in dismissed or not item.note_ids:
            continue
        #: The person's word on a sentence beats an inference that quotes it.
        #: (The plan a drift rests on is the line's own words, which the
        #: insight's text only paraphrases.)
        if known and (known.quoted_in(item.text) or known.quoted_in(str(item.slots.get("plan") or ""))):
            continue
        if _old_news(item, members, said):
            continue
        relevance = len(set(item.note_ids) & ids) / len(item.note_ids)
        if relevance >= insight_bar(learned):
            scored.append((relevance, item))
    scored.sort(key=lambda pair: -pair[0])
    return scored


def _opening_count(said: str) -> int | None:
    """The count the answer's opening gave, in any of its wordings ("You have
    three notes about uni", "Your notes on uni: three notes", "you've
    written three notes"), or None when it gave none (audit 1031 C25: a
    retry's frame must not let a second, different count in)."""
    words = "|".join(realise.count_word(n) for n in range(21))
    found = re.search(rf"\b(\d+|{words}) notes?\b", said, re.I)
    if not found:
        return None
    word = found.group(1).lower()
    return int(word) if word.isdigit() else next((n for n in range(21) if realise.count_word(n) == word), None)


def _say_insight(out: _Out, item, row: dict, members, said: str) -> None:  # noqa: ANN001
    """One insight said where it belongs: woven into the line that tells its
    plan, as the hedge after the count, or as a closing line."""
    if item.rule == "drift" and _weave_drift(out, str(item.slots.get("plan") or "")):
        #: Said once, in the line that already tells the plan (the owner,
        #: 2026-10-11); the row under the answer only asks if it is right.
        row["in_answer"] = True
    elif item.rule == "recurrence" and realise.count_word(len(members)) in said:
        #: The count is the opening's; what is new is the hedge.
        hedge = str(item.slots.get("hedge") or "")
        if hedge != composer_tables.INSIGHT_HEDGES["recurs"]:
            out.closing.insert(0, hedge[:1].upper() + hedge[1:] + ".")
        row["in_answer"] = True
    else:
        out.closing.insert(0, item.text)
    out.insights.append(row)


def _volunteer(out: _Out, asked: str, members, notes: list[dict], today: date, level: str, learned) -> None:  # noqa: ANN001, ARG001
    """At most one measured insight (all, at "all") the answer has not
    already said, scored by how much of it rests on the answer's notes."""
    if level not in INSIGHT_LEVELS or level == "off":
        return
    from tessellate.ai import insights

    ids = {v.note.get("source_id", v.id) for v in members}
    #: The route's notes carry their day as `written` words; the rules read
    #: an ISO `created_at` (the composer's `_insights_for` does the same).
    own = [{**v.note, "id": v.note.get("source_id", v.id), "created_at": v.written.isoformat()} if v.written else v.note for v in members]
    topic = _topic(asked, members)
    found = [*insights.for_subject(topic, own, today, asked), *insights.drift(own, today), *insights.contrast(own, today)]
    said = " ".join([*out.lines, *out.more]).lower()
    for _, item in _scored_insights(found, ids, members, said, learned)[: 1 if level == "one" else 3]:
        row = insights.as_row(item, learned)
        if not row["confirmed"]:
            _say_insight(out, item, row, members, said)
            continue
        #: The person's word, said as theirs, once (and first when it is
        #: about the subject asked, `_confirmed_first`).
        if row["text"] not in out.lines:
            out.closing.insert(0, row["text"])
        out.insights.append(row)


def _confirmed_first(out: _Out, asked: str, members, learned) -> None:  # noqa: ANN001
    """A subject the person confirmed an insight on opens with their word,
    as a fact (decision 60, as `composer._confirmed_lead` does)."""
    confirmed = getattr(learned, "subjects", None)
    if not callable(confirmed):
        return
    from tessellate.ai import insights

    about = {insights._stems(_topic(asked, members)), *(insights._stems(t) for t in _subject(asked))}
    for subject, line in confirmed().items():
        if subject in about:
            out.lines.insert(0, line)
            return


def _weave_drift(out: _Out, plan: str) -> bool:
    """A plan no later note picks up, said as a clause of the line that
    tells the plan. False when no line tells it."""
    words = re.findall(r"[a-z0-9]+", re.sub(r"^(?:i'?m |i am )?going to ", "", plan.lower()))
    if len(words) < 3:
        return False
    tail = r"\W+".join(words[-4:])
    for i, line in enumerate(out.lines):
        if i and re.search(tail, line.lower()) and not line.startswith("**"):
            out.lines[i] = line.rstrip(".") + ", " + PHRASES["drift_woven"] + "."
            #: The line's mark goes at its end, so its row says all of it.
            for row in out.rows:
                if row.get("sentence") and line.rstrip(".").endswith(row["sentence"]):
                    row["sentence"] = out.lines[i].rstrip(".")
            return True
    return False


def _this_note(out: _Out, v, facts: list[Fact], names: set[str], today: date) -> None:  # noqa: ANN001
    """The open note: its facts under their labels."""
    #: The heading `read_note` found: the note dict carries no `title` of its own
    #: (the 22-10 bug doc: "Your untitled note of 25 October" over a titled note).
    title = _tidy(str(v.note.get("title") or (v.title if v.titled else "")))
    category = str(v.note.get("category") or "").strip()
    where = f", in {category}" if category and category.lower() != "uncategorised" else ""
    #: A title keeps its capital (C1); a note without one is named by its
    #: first clause (C8), never by a section's label or "untitled".
    name = _note_called(title) if title else _your_note(v)
    said = [(_fragment(_second_person(f.body), names), f) for f in facts]
    #: A note named by a label ("Your gym note") says one thing as any titled one
    #: does, and only a "The note that starts ..." name (which would repeat its
    #: own first clause) is dated instead (audit 1030 Z55; INBOX 1441 keeps the
    #: day out of an untimed question).
    if len(said) == 1 and not title and not name.lower().startswith("your "):
        out.lines.append(PHRASES["this_line"].format(day=_day(v.written, today), where=where, pause="," if where else "", fact=said[0][0][:1].upper() + said[0][0][1:].rstrip(".")))
        out.rows.append(_row(said[0][0], said[0][1]))
        return
    if len(said) == 1:
        out.lines.append(PHRASES["this_one"].format(name=name, day=_day(v.written, today), where=where, pause="," if where else "", fact=said[0][0]))
        out.rows.append(_row(said[0][0], said[0][1]))
        return
    out.lines.append(PHRASES["this_note"].format(
        name=name, day=_day(v.written, today), where=where, points=_points_word(said)))
    out.lines.append(_points_block(out, said[:MORE_LINES], title or composer_frame.note_label(v.note)))


def _points_word(said: list) -> str:
    """"five points", or for a checklist "five items, one ticked": its state
    is part of the summary (audit 1031 C29)."""
    ticked = sum(1 for _, f in said if f.sentence.kind == "task" and f.sentence.done)
    if said and all(f.sentence.kind == "task" for _, f in said):
        return f"{realise.count_word(len(said))} items, {realise.count_word(ticked) if ticked else 'none'} ticked"
    return f"{realise.count_word(len(said))} points"


def _points_block(out: _Out, said: list, title: str) -> str:
    """One point a line, as a list: the note's own heading is the lead's, so
    it is not repeated as every line's label. One block, so the list renders
    tight rather than spaced."""
    points = []
    for text, fact in said:
        label = f"**{fact.label}:** " if fact.label and fact.label.lower() != title.lower() else ""
        tick = " (ticked)" if fact.sentence.kind == "task" and fact.sentence.done else ""
        points.append(f"- {label}{text[:1].upper() + text[1:]}{tick}{'' if text.endswith(('.', '。', '！', '？')) else '.'}")
        out.rows.append(_row(text, fact))
    return "\n".join(points)


def _this_category(out: _Out, views: list, facts: list[Fact], today: date) -> None:
    """The open category, as an overview of its notes."""
    category = Counter(str(v.note.get("category") or "") for v in views).most_common(1)[0][0] or "these notes"
    out.lines.append(PHRASES["this_many"].format(count=_count(len(views)), topic=category, span=_span(views, today)))
    _lines(out, facts, LINES["overview"], by_day=today, more=True)
    missing = _missing(views)
    if missing:
        out.lines.append(missing)


def _this(out: _Out, views: list, names: set[str], today: date, asked: str) -> dict | None:
    """"Summarise this" (B10): the open note, its facts under their labels;
    or the open category, as an overview of its notes."""
    views = sorted(views, key=lambda v: (v.written or date.min, v.rank))
    facts = [f for v in views for f in _facts(v, names)]
    if not facts and len(views) == 1 and _title_only(views[0]):
        #: One message for a note that is only its name, open or asked by name
        #: (audit 1030 Z55).
        title = _tidy(composer_frame.own_title(str(views[0].note.get("content") or "").strip()))
        out.lines.append(f"{composer.PHRASES['bare_a']}“{title}”{composer.PHRASES['bare_b']}")
        return _result(out, "overview", asked)
    if not facts:
        return None
    if len(views) == 1:
        _this_note(out, views[0], facts, names, today)
    else:
        _this_category(out, views, facts, today)
    if not out.lines:
        return None
    out.offer = _offer(_answered(out, facts))
    return _result(out, "overview", asked)


def _tie(question: str, members: list) -> tuple[list, str, list] | None:
    """Two readings of one word that tie (B9): the notes split evenly
    between two categories and, past the asked word, share no word at all
    ("python" in Coding and in Pets). The newer reading is answered; the
    other is named, with one chip to ask about it. Anything short of an
    even split with nothing shared is one subject, answered whole."""
    q = clean(question).lower()
    groups: dict[str, list] = {}
    for v in members:
        category = str(v.note.get("category") or "").strip()
        if not category or category.lower() in q or category.lower() == "uncategorised":
            return None
        groups.setdefault(category, []).append(v)
    if len(groups) != 2:
        return None
    (a, first), (b, second) = groups.items()
    #: One note on each side is a passing mention, not a second reading
    #: (a joke note and the homework it was about).
    if len(first) != len(second) or len(first) < 2:
        return None
    asked = set(_subject(question))
    def words(group: list) -> set[str]:
        return {w for v in group for w in v.words if len(w) > 2 and not any(composer._holds(st, {w}) for st in asked)}
    if words(first) & words(second):
        return None
    newest = max(members, key=lambda v: (v.written or date.min, v.rank))
    if newest in second:
        (a, first), (b, second) = (b, second), (a, first)
    return first, b, second


_PLACE = re.compile(r"\b(?:the )?(driving range|range|gym|pool|court|course|track|studio|climbing wall|park)\b", re.I)
_REVIEWED = re.compile(rf"\b({_REVIEWED_WORDS})s?\b", re.I)


def _note_offer(label: str, text: str) -> dict:
    return {"kind": "note", "label": label, "text": text}


def _likes_offer(text: str) -> dict | None:
    places = sorted({m.group(1).lower() for m in _PLACE.finditer(text)}, key=len, reverse=True)
    if not places:
        return None
    where = "the " + places[0]
    return {"kind": "reminder", "label": PHRASES["go_again"].format(place=where), "text": f"Go to {where}"}


#: What to do with each kind of thing reviewed: a book is read, not watched.
_REVIEW_VERB = {"book": "read", "album": "listen to", "game": "play"}


def _reviewed_word(question: str, members, text: str = "") -> str:  # noqa: ANN001
    """What the opinion is about ("film", "book"), from the question, the
    tags and the notes' words; "" when none names it. A review was called a
    "film review" whatever it was (audit 1029 C5: a book), so the word is
    never assumed."""
    tags = " ".join(str(t) for v in members for t in (v.note.get("tags") or []))
    own = " ".join(s.text for v in members for s in v.sentences)
    found = _REVIEWED.search(f"{question} {tags} {text or own}")
    return {"movie": "film"}.get(found.group(1).lower(), found.group(1).lower()) if found else ""


def _opinion_offer(question: str, members, text: str) -> dict | None:  # noqa: ANN001
    noun_word = _reviewed_word(question, members, text)
    if not noun_word:
        return None
    verb = _REVIEW_VERB.get(noun_word, "watch")
    return _note_offer(PHRASES["start_list"].format(noun=noun_word, verb=verb), f"{noun_word.capitalize()}s to {verb} next\n\n- [ ] ")


def _count_offer(question: str, text: str) -> dict | None:
    #: Asked about spending, not about a price: "how much do the flights cost"
    #: is no cue to track spending (audit 1031 C20).
    if re.search(r"\$\s?\d", text) and re.search(r"\b(spen[dt]|spending|budget)", question, re.I):
        return {"kind": "reminder", "label": PHRASES["log_weekly"], "text": "Log your spending every Sunday"}
    return None


#: A question that asks for things still to try, want or do: only there is
#: the first listed item a thing to be reminded of ("words I have learned" is not).
_TO_TRY = re.compile(r"\b(?:want|wanna|should|plan(?:ning)?|hope|hoping|wish|meaning|going) to\b|\b(?:to try|to do|to see|to visit|to watch|to read|ideas?|bucket|wish ?list|next)\b", re.I)


def _fact_offer(out: _Out, question: str = "") -> dict | None:
    if not _TO_TRY.search(question):
        return None
    listed = re.search(r"^\w+, from [^:]+: (.+)\.$", out.lines[0]) if out.lines else None
    if not listed:
        return None
    first = re.split(r",(?!\d)\s*| and ", listed.group(1))[0].strip()
    if not first[:1].islower() or first.split()[0].lower() in _NAMES.get():
        #: "Remind you to try Sara?": a name is not a thing to try (C3).
        return None
    return {"kind": "reminder", "label": PHRASES["try_one"].format(item=first), "text": f"Try {first}"}


def _overview_offer(kind: str, question: str, members, facts: list[Fact], today: date) -> dict | None:  # noqa: ANN001
    """What an overview suggests: gathering jokes or quotes into one note, a
    table to track a lift, or the pick a comparison landed on."""
    if kind == "overview" and members and all(_context_note(v) for v in members) and len(members) >= 2:
        topic = _topic(question, members)
        return _note_offer(PHRASES["gather"], f"{topic[:1].upper() + topic[1:]}\n\n" + "\n\n".join(f.body for f in facts))
    table = _lift_table(members, today) if kind == "overview" and _GOING.search(question) else None
    if table:
        return _note_offer(PHRASES["track_table"].format(what=table[0]), table[1])
    landed = next((f for f in facts if f.label == "Where you landed"), None)
    side = re.search(r"towards (?:the )?(.+)$", landed.body) if landed else None
    if side:
        return _note_offer(PHRASES["pick_note"].format(side=side.group(1).strip()), f"My pick: the {side.group(1).strip()}")
    return None


def _kind_offer(kind: str, question: str, members, facts: list[Fact], today: date, out: _Out) -> dict | None:  # noqa: ANN001
    """The one acting offer when the notes name no to-do of their own (B12):
    what the kind of question suggests doing with the answer, each one a
    thing the app does in one press (a reminder or a note)."""
    text = " ".join(s.text for v in members for s in v.sentences)
    if kind == "opinion":
        return _opinion_offer(question, members, text)
    offer = {"likes": lambda: _likes_offer(text), "count": lambda: _count_offer(question, text), "fact": lambda: _fact_offer(out, question)}.get(kind)
    return (offer() if offer else None) or _overview_offer(kind, question, members, facts, today)


def _lift_table(members, today: date) -> tuple[str, str] | None:
    """Each dated note's measures as one table row ("Track your lifts in a
    table?"): the columns are the measures any note gives."""
    rows, columns = [], []
    for v in members:
        found = {}
        for s in v.sentences:
            for word, _value, figure, unit in _measures(s.text):
                found.setdefault(word, f"{figure} {unit}")
        if found and v.written:
            rows.append((v.written, found))
            columns += [c for c in found if c not in columns]
    if len(rows) < 2:
        return None
    what = "lifts" if any(r[1].endswith("kg") for _, f in rows for r in [tuple(f.items())[0]]) else "numbers"
    head = "| Day | " + " | ".join(c.capitalize() for c in columns) + " |"
    rule = "| --- |" + " --- |" * len(columns)
    body = ["| " + _day(d, today) + " | " + " | ".join(f.get(c, "") for c in columns) + " |" for d, f in rows]
    return what, "\n".join([what.capitalize(), "", head, rule, *body])


def _still_open(views, listed) -> list[str]:  # noqa: ANN001
    """The other things still to do that notes besides the list name."""
    open_bits = []
    for w in views:
        for t in w.sentences:
            still = _STILL_TO.search(t.text)
            if still and w is not listed:
                topic = next((str(x) for x in (w.note.get("tags") or []) if str(x).lower() not in still.group(1).lower()), "")
                #: "the Camping the tent" doubled the article.
                what = re.sub(r"^(the|a|an) ", "", still.group(1).lower()) if topic else still.group(1).lower()
                open_bits.append(f"the {topic[:1].upper() + topic[1:] + ' ' if topic else ''}{what}")
    return open_bits


def _left(out: _Out, question: str, members, views, names: set[str], today: date) -> bool:  # noqa: ANN001
    """"What do I need to buy": the open list first, then the other things
    still to do the notes name."""
    lists = composer_lists.open_lists(question, views)
    if not lists:
        return False
    v, s, head = lists[-1]
    #: "..., and Piranesi": the list's own "and" is not part of its last item (W7 B7).
    items = [re.sub(r"^and\s+", "", i.strip().rstrip("."), flags=re.I) for i in head.group(2).split(",") if i.strip()]
    what = re.sub(r"^(?:want|need|have|plan)s? to ", "to ", head.group(1).strip().lower())
    #: A note with a name of its own is named by it, not by the day it was written.
    source = f"your {v.title} note" if v.titled and v.title and v.title.lower() != what else f"your list of {_day(v.written, today)}"
    #: Decision 71: what is left is a checklist, the opening then a box an
    #: item, so the list reads down rather than along one sentence.
    opening = f"{realise.count_word(len(items)).capitalize()} {what}, from {source}"
    out.lines.append(opening + ":\n" + "\n".join(f"- [ ] {item}" for item in items))
    out.rows.append({"sentence": opening, "note_id": v.note.get("source_id", v.id), "source": s.text,
                     "start": s.start, "end": s.end, "score": 1.0, "digest": True})
    open_bits = _still_open(views, v)
    if open_bits:
        left = open_bits[:2]
        out.lines.append(f"{realise.join_items(left)[:1].upper()}{realise.join_items(left)[1:]} {'is' if len(left) == 1 else 'are'} also still open.")
    out.offer = {"kind": "checklist", "label": PHRASES["checklist"], "text": head.group(1).strip(), "items": items}
    return True


def _more(out: _Out) -> dict | None:
    """What the page folds: the More lines by their labels (the bold words
    each opens with), and the button's words."""
    if not out.more:
        return None
    labels = [m.group(1) for line in out.more if (m := re.match(r"\*\*(.+?):\*\*", line))]
    #: A line said as prose has no label (the owner, 2026-10-11): the page
    #: finds every folded line by the words it opens with.
    starts = [" ".join(re.sub(r"\*\*", "", line).split()[:5]) for line in out.more]
    return {"labels": labels, "starts": starts, "label": PHRASES["more_show"].format(count=realise.count_word(len(out.more))), "lines": list(out.more)}


def _lead_figure(line: str) -> str | None:
    """The figure a count opens with ("$84", "90 kg", "12"), as the
    recogniser reads it, for the page to draw large (`digestShape`): the
    page finds it by its text and never reads a figure itself."""
    lead = re.sub(r"\*\*", "", line)
    found = next((s for s in _spans(lead, None) if s.kind in ("money", "quantity", "number", "duration")), None)
    return found.text if found and found.start <= len("You've spent ") else None


_DAY_OF_MONTH = re.compile(r"\b(?:(\d{1,2}(?:st|nd|rd|th)?) (may|march)|(may|march) (\d{1,2})(?:st|nd|rd|th)?)\b(?!:\d)", re.I)
_SET_ASIDE = re.compile(
    r"“[^”]*”|\"[^\"\n]*\"|`[^`]*`|\[[^\]]*\]\([^)]*\)|https?://\S+|\S+@\S+|"
    r"[\w-]+\.(?:txt|md|pdf|docx?|pptx?|xlsx?|csv|json|png|jpe?g|gif|zip|py|js|html?)\b|^>.*$",
    re.M,
)
#: A sentence opens at a line start or after a full stop; "e.g." and "5 p.m."
#: do not end one.
_SENTENCE_START = re.compile(r"(?:^|(?<=[.!?] ))(\*\*)?([a-z][a-z']*)(?!\w)", re.M)
_NOT_AN_END = re.compile(r"(?:\b(?:e\.g|i\.e|etc|vs|approx|dr|mr|mrs|ms|st|no|cf)|\b[ap]\.m)\. $", re.I)
_VERB_TO = r"(?:go|goes|going|went|gone|head|heads|heading|headed|walk|walks|walking|walked|drive|drives|driving|drove|run|runs|running|ran|come|comes|coming|came|nip|nipped|pop|popped|back)"
#: Places said with "the". Not school, work, bed, church, hospital, uni,
#: college or town, which are said bare.
_PLACES = (
    "gym|shop|shops|supermarket|store|bank|library|pharmacy|chemist|chemists|dentist|doctor|cinema|beach|park|airport|station|"
    "market|mall|barber|barbers|hairdresser|hairdressers|salon|bakery|butcher|butchers|pool|post office|optician|opticians|vet|office"
)
#: What may follow the place: the phrase must end there, so "gym class" and
#: "bank holiday" (a noun on it) are left alone.
_AFTER_WORDS = (
    "and", "or", "but", "then", "on", "at", "in", "after", "before", "every", "today", "tonight", "tomorrow",
    "yesterday", "this", "next", "last", "again", "for", "with", "so", "when", "if", "as", "by", "from", "until",
    "once", "twice", "daily", "weekly", "early", "late", "now", "soon", "later", "instead", "still", "too", "to",
)
_AFTER_PLACE = rf"(?=\s*(?:$|[.,;:!?)]|(?i:{'|'.join(_AFTER_WORDS)}|{_WEEKDAYS})\b))"
_NEEDS_THE = re.compile(rf"\b((?i:{_VERB_TO}(?: back)?)) to ({_PLACES}){_AFTER_PLACE}")


def _capital(m: re.Match) -> str:
    word = m.group(2)
    if _NOT_AN_END.search(m.string[max(0, m.start() - 12):m.start()]):
        return m.group(0)
    known = _dictionary()
    if word in ("a", "i") or word in _WEEKDAY_WORDS or (known and len(word) > 1 and word in known):
        return f"{m.group(1) or ''}{word[0].upper()}{word[1:]}"
    return m.group(0)


def polish(text: str, keep: Iterable[str] = ()) -> str:
    """`text`, composed by the app, with its lead capitals, day and month
    names and "to gym" (to the gym) fixed. `keep` holds sentences that are the
    person's own words (a joke, a quote), left exactly as they are."""
    held: list[str] = []
    text = _unlinked(text)

    def hold(m: re.Match) -> str:
        held.append(m.group(0))
        return f"{len(held) - 1}"

    for phrase in sorted({k.strip() for k in keep if k and k.strip()}, key=len, reverse=True):
        text = re.sub(re.escape(phrase), hold, text, flags=re.I)
    text = _SET_ASIDE.sub(hold, text)
    text = _NEEDS_THE.sub(r"\1 to the \2", text)
    text = _DAY_NAME.sub(lambda m: m.group(0).capitalize(), text)
    text = _DAY_OF_MONTH.sub(lambda m: m.group(0).title() if m.group(1) or m.group(3) else m.group(0), text)
    text = _SENTENCE_START.sub(_capital, text)
    #: A held quote can hold a kept phrase ("“Why don't skeletons fight? ...”"): restored until none is left.
    for _ in range(len(held) + 1):
        if "" not in text:
            break
        text = re.sub("(\\d+)", lambda m: held[int(m.group(1))], text)
    return realise.mend_stops(text)


#: A note's own emphasis marks (`*Bring wine*`, a one-word `cash` code span)
#: show as plain words in a quote: the answer's own bold stays (round 2, research row 11).
_ITALIC_MARK = re.compile(r"(?<![*\w])\*(?![\s*])([^*\n]+?)(?<![\s*])\*(?![*\w])")
_CODE_WORD = re.compile(r"`(\w+)`")


def _plain_marks(line: str) -> str:
    return _CODE_WORD.sub(r"\1", _ITALIC_MARK.sub(r"\1", line))


def _polish_out(out: _Out, kind: str) -> None:
    """The composed lines, said with the grammar pass. A web answer is the
    pages' own words under a one-line lead, so it is not touched."""
    if kind == "web":
        return
    keep = composer_jokes.kept(_VIEWS.get())
    #: A quote is the note's own words, whatever frame said it (INBOX 1515).
    pool = [t for v in _VIEWS.get() for t in (str(v.note.get("content") or ""), *map(str, (v.note.get("link_reasons") or {}).values()))]
    for lines in (out.lines, out.more, out.closing, out.next):
        lines[:] = [_plain_marks(composer_threads.own_words(polish(line, keep), pool)) for line in lines]
    _clean_out(out)
    if out.offer and out.offer.get("label"):
        out.offer = {**out.offer, "label": polish(str(out.offer["label"]), keep)}
    _rows_as_polished(out, lambda t: _plain_marks(composer_threads.own_words(polish(t, keep), pool)))


def _clean_out(out: _Out) -> None:
    """What an answer never says (`composer_clean`, INBOX 1705): a line with an unfit quote goes."""
    for lines in (out.lines, out.more, out.closing):
        lines[:] = [kept for kept in map(composer_clean.line, lines) if kept]


def _rows_as_polished(out: _Out, said_as=_plain_marks) -> None:
    """A row is the sentence as the answer now reads it ("tuesday" became "Tuesday",
    "to gym" "to the gym"), else the card finds no words (INBOX 1665 f, 1767 c)."""
    whole = "\n".join([*out.lines, *out.more, *out.closing, *out.next])
    for row in out.rows:
        said = said_as(str(row.get("sentence") or ""))
        found = re.search(re.escape(said), whole, re.IGNORECASE) if said and said not in whole else None
        row["sentence"] = found.group(0) if found else said
        row["sentence"] += "" if row.get("anchor") else trailing_clause(whole, row["sentence"])


#: Shapes whose chips are their own (a web answer, a "more" turn).
_OWN_NEXT = frozenset({"web", "more"})


#: The verb a question leaves on its subject ("sara like jazz", "tokyo trip cost"): no name to ask about.
#: The question's own verb in a topic: no chip is built from it (D19, R3-36).
_OWN_VERB = re.compile(r"\b(?:am|is|are|was|were|do|does|did|have|has|had|i)\b", re.I)
_TAIL_VERB = re.compile(r"\b(?:likes?|loves?|wants?|needs?|costs?|owes?)\b", re.I)


def _topic_chips(kind: str, topic: str) -> list[str]:
    """The chips about `topic`; none when it carries the question's own verb ("book am I
    reading") and so is no name to ask about (R3-36, D19)."""
    if _OWN_VERB.search(topic) or _TAIL_VERB.search(topic):
        return []
    return [q.format(t=topic) for q in _NEXT_ABOUT.get(kind, _NEXT_ABOUT["fact"])]


def _next_asks(kind: str, question: str, rows: list[dict]) -> list[str]:
    """Two or three questions to ask next, built the way a composed answer
    builds them (`composer._next_questions`): a thread through the notes
    found, a note found and not quoted, the latest on the subject (INBOX
    1466: a digest handed none, so under it only "Why this answer" showed)."""
    if kind in _OWN_NEXT:
        return []
    cited = {r.get("note_id") for r in rows}
    views = list(_VIEWS.get())
    picks = composer._next_questions(question, kind, composer.subject_terms(question), views, cited)
    said = ["".join(part[1] for part in p) for p in picks]
    members = [v for v in views if v.id in cited]
    topic = _topic(question, members) if members else ""
    if topic and topic != "this" and len(topic) <= 40 and not question_noise.filler_subject(topic) and query_understanding.is_chip_subject(topic):
        topic = composer_chip_subject.clean(_chip_subject(topic, question), views, question)
        said += _topic_chips(kind, topic) if topic else []
    return _fresh_chips(said, question)[:3]


def _asked(offer: dict) -> dict:
    """The offer with its prose: the sentence reads "Shall I remind you to X?" while the button
    keeps its pinned label "Remind you to X?" (Q4)."""
    label = str(offer["label"])
    return {**offer, "line": "Shall I remind you " + label[len("Remind you "):]} if label.startswith("Remind you ") else offer


def _fresh_chips(said: list[str], question: str) -> list[str]:
    """The chips not the question just asked, a name in its capitals ("about
    Tom", never "about tom": the who path lower-cases the name it asked
    about), one of each kind: "the latest on social connections" and "the
    latest on conversation" are one ask said twice (audit 1031 C42)."""
    seen = {_ask_key(question)}
    frames: set[str] = set()
    out = []
    names = _NAMES.get()
    views = list(_VIEWS.get())
    for q in said:
        q = composer_chip_subject.fix_chip(q, views, question)
        q = re.sub(r"\b[a-z]+\b", lambda m: m.group(0).capitalize() if m.group(0) in names else m.group(0), q)
        if q and _ask_key(q) not in seen and _chip_frame(q) not in frames:
            seen.add(_ask_key(q))
            frames.add(_chip_frame(q))
            out.append(q)
    return out


_FRAME_CUT = re.compile(r"\s(?:about|on|in|with)\s|[“\"]")


def _chip_frame(chip: str) -> str:
    """A chip's words before its subject: its kind of ask."""
    return _FRAME_CUT.split(re.sub(r"\bwhat's\b", "what is", chip.lower()))[0].strip()


#: Nouns for a person, said with "my" in a chip when the question gave
#: none ("uni friend" is "my uni friend").
_PERSON_NOUNS = frozenset(
    "friend mate mum mom dad brother sister partner boss teacher tutor girlfriend boyfriend wife husband flatmate "
    "roommate housemate cousin aunt uncle son daughter colleague coworker mentor therapist coach grandma grandpa nan".split())
_CHIP_WORD = re.compile(r"[\w'&-]+")


def _chip_hits(wanted: list[str], lower: list[str]) -> list[int]:
    """Where in the question the topic's words were typed; none unless each one was."""

    def means(term: str, word: str) -> bool:
        return word == term or composer._stem(word) == composer._stem(term) or term in composer.subject_terms(word)  # noqa: SLF001

    hits = [i for i, w in enumerate(lower) if any(means(t, w) for t in wanted)]
    if not hits or not all(any(means(t, lower[i]) for i in hits) for t in wanted):
        return []
    return hits


def _chip_owner(lower: list[str], first: int, last: int) -> str:
    """The "my" or "the" a chip's subject carries, from the word before it."""
    before = lower[first - 1] if first else ""
    owner = {"my": "my", "your": "my", "our": "our", "the": "the"}.get(before, "")
    return "my" if not owner and lower[last] in _PERSON_NOUNS else owner


def _chip_subject(topic: str, question: str) -> str:
    """The subject a chip asks about, in the person's own words (INBOX 1483:
    "What's the latest on university friend?" for "my uni friend"): the
    words they typed for it, with their "my" or "the", never the search's
    expansion ("university" for "uni") or the verb they did ("miss bus" for
    "did I miss the bus" is "the bus"). A chip is the person speaking, so
    their "my" stays "my"."""
    asked = _CHIP_WORD.findall(question)
    lower = [w.lower() for w in asked]
    hits = _chip_hits(topic.lower().split(), lower)
    if not hits:
        return topic
    #: "did I miss the bus": what they did is not what it is about.
    while len(hits) > 1 and lower[hits[0] - 1 : hits[0]] == ["i"]:
        hits = hits[1:]
    first, last = hits[0], hits[-1]
    if last - first > 4:
        return topic
    cased = {w.lower(): w for w in topic.split()}
    span = " ".join(cased.get(w.lower(), w) for w in asked[first : last + 1])
    return f"{_chip_owner(lower, first, last)} {span}".strip()


#: Questions about the subject asked, by the answer's shape: what an answer
#: of that shape leaves to ask (INBOX 1466).
_NEXT_ABOUT = {
    "overview": ("What's the latest on {t}?", "When did I last write about {t}?"),
    "when": ("What else have I saved about {t}?", "What's the latest on {t}?"),
    "fact": ("What else have I saved about {t}?", "When did I last write about {t}?"),
}


def _ask_key(question: str) -> str:
    """A question's words, so "What is the latest on X?" and "What's the
    latest on X" are one chip, and the question just asked is none."""
    words = re.sub(r"\bwhat's\b", "what is", question.lower())
    return " ".join(re.findall(r"[a-z0-9]+", re.sub(r"\b(?:the|my|a|an|last)\b", " ", words)))


def _plain_result(text: str, note_id: int | None) -> dict:
    """A one-line reply, cited to the note it read an age from (none when no note says one)."""
    out = _Out()
    out.lines.append(text)
    if note_id is not None:
        out.rows.append({"sentence": text, "note_id": note_id, "source": text, "start": 0, "end": len(text), "score": 1.0, "digest": True, "kind": "note"})
    return _result(out, "fact", "")


def _one_word_result(note: dict) -> dict:
    """The answer for a note that is one word, cited to that note (round 2 E11)."""
    out = _Out()
    out.lines.append(composer_oneword.say(note))
    text = out.lines[0]
    word = " ".join(str(note.get("content") or "").split())
    out.rows.append({
        "sentence": text, "note_id": note.get("source_id", note.get("id")), "source": word, "start": 0, "end": len(word),
        "score": 1.0, "digest": True, "kind": "note",
    })
    return _result(out, "fact", "")


def _result(out: _Out, kind: str, question: str) -> dict:
    if not out.next:
        out.next = _next_asks(kind, question, out.rows)
    _polish_out(out, kind)
    #: One paragraph a line: a single newline inside a paragraph is a space
    #: to every markdown reader, so the labelled lines ran together.
    paragraphs = composer_clean.paragraphs(list(out.lines) + out.more + out.closing[: 2 + len(out.insights)])
    #: A reminder is offered to a question about a date or a task, never to "how much is the budget".
    if out.offer and out.offer.get("kind") == "reminder" and _ASKED_AS.get() is not None and not _REMINDABLE.search(_ASKED_AS.get() or ""):
        out.offer = None
    if out.offer:
        out.offer = _asked(out.offer)
        paragraphs.append(out.offer.get("line") or out.offer["label"])
    #: A full-width stop or closing bracket already ends the quoted sentence,
    #: so no ASCII stop follows it ("（笑）." read as a stray dot, INBOX 1524);
    #: after a bare CJK character the stop is the full-width one.
    text = _CJK_STOP.sub(lambda m: m.group(1) + ("" if m.group(1) in _CJK_ENDS else "。"), "\n\n".join(paragraphs))
    n = len(out.rows)
    return {
        "text": text,
        "grounding": out.rows,
        #: `digest` and `offer` ride on the support too: it is what the Ask
        #: box hands its grounding renderer, which then draws one mark a line
        #: and no chips or count under the answer.
        "support": {"supported": n, "sentences": n, "unsupported": [], "digest": True, "offer": out.offer, "shape": kind, "more": _more(out),
                    "figure": _lead_figure(out.lines[0]) if kind == "count" and out.lines else None},
        "shape": f"digest:{kind}",
        "parts": [("template", text)],
        "next": list(out.next),
        "next_parts": [[("template", n)] for n in out.next],
        "insights": list(out.insights),
        "broad": kind == "overview",
        "digest": True,
        "offer": out.offer,
    }


#: "search the web for X", "look up X": the words that ask, not the subject.
_WEB_ASK = re.compile(r"^(?:(?:hey|hi|ok|okay),? )?(?:(?:can|could|will) (?:you|u) )?(?:(?:please|pls|plz) )?(?:search (?:the )?(?:web|internet|online) (?:for|about)|search up|look up|google|find (?:on|from) the web|web search(?: for)?)\s+", re.I)


#: A question whose answer depends on where the person is ("the weather
#: today", "pharmacies near me") and that names no place itself.
_LOCAL = re.compile(r"\b(?:weather|forecast|temperature|rain(?:ing)?|sunrise|sunset|near me|nearby|open now)\b", re.I)
_NAMES_PLACE = re.compile(r"\b(?:in|at|for|near) (?-i:[A-Z])\w+")


def web_query(question: str, place: str = "") -> str:
    """What to search for: the turn without its "can you search the web for",
    and, for a local question that names no place, the person's own place
    (their timezone's city), so "what's the weather like today" is not
    searched as if from nowhere. `place` comes from settings, never typed."""
    asked = clean(_WEB_ASK.sub("", clean(question))) or question
    if place and _LOCAL.search(asked) and not _NAMES_PLACE.search(asked) and place.lower() not in asked.lower():
        asked = f"{asked.rstrip(' ?.!')} {place}"
    return asked


def _page_span(view, row: dict | None, terms: set[str]) -> str:  # noqa: ANN001
    """The sentence of a page that best meets the question: the one the
    composer picked, else the page's best sentence of five words or more
    that is under 260 characters."""
    if row and row.get("sentence"):
        return str(row["sentence"])
    ranked = sorted(
        (s for s in view.sentences if len(s.text.split()) >= 5 and len(s.text) <= 260),
        key=lambda s: -len(terms & set(s.words)),
    )
    return ranked[0].text.strip() if ranked else ""


@_isolated
def web(question: str, pages: list[dict], composed: dict | None = None) -> dict | None:
    """An answer from web pages in decision 70's shape (decision 66): what
    was searched and how many pages were read, then one line a page, its
    title as the label and its own sentence that best meets the question,
    cited by the page's address. Never empty when a page has text (INBOX
    810: "searched the web ... and then didnt even output the results")."""
    asked = clean(_WEB_ASK.sub("", clean(question)))
    _set_timing(question)
    terms = set(composer._words(asked))
    picked: dict[int, dict] = {}
    for row in (composed or {}).get("grounding") or []:
        picked.setdefault(row.get("note_id"), row)
    out = _Out()

    def meets(page: dict) -> int:
        return len(terms & set(composer._words(str(page.get("content") or ""))))

    order = sorted(pages, key=lambda p: (p["id"] not in picked, -meets(p), pages.index(p)))
    for page in order[:3]:
        view = composer.read_note({**page, "tags": []}, 0)
        span = _page_span(view, picked.get(page["id"]), terms) if view else ""
        if not span:
            continue
        title = " ".join((view.title or page.get("domain") or "A page").split()[:8])
        out.lines.append(f"**{title}:** {span}")
        out.rows.append({
            "sentence": span, "note_id": page["id"], "kind": "web", "url": page["url"], "title": title,
            "score": 1.0, "digest": True, "said": "quoted",
        })
    if not out.lines:
        return None
    n = len(out.lines)
    out.lines.insert(0, f"I searched the web for “{asked}” and read {realise.count_word(n)} {'page' if n == 1 else 'pages'}; each is under the answer to read here.")
    return _result(out, "web", question)


composer_lists.bind(_day, _row, Fact, _span, _your_note)
composer_frame.bind_lower(_said_in_a_frame)


