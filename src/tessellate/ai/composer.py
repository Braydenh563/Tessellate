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
follow-ons).
"""

from __future__ import annotations

import functools
import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime

from tessellate.ai import act_registry, composer_ack, composer_compose, composer_lines, composer_links, composer_open, composer_parts, composer_replies, composer_tables, composer_versus, grounding, phrasing, question_noise, spelling, utilities
from tessellate.ai import recognise as rec
from tessellate.ai import when as when_words
from tessellate.search import query as query_understanding
from tessellate.ai.composer_phrases import PHRASES, phrase_options  # noqa: F401  (moved; re-exported)
from tessellate.ai.composer_ask import IRREGULAR_PAST, SHAPES, SYNONYM_GROUPS, _ASKING_WORDS, _ASKS_FIRST, _BIN_WORDS, _COMPARE_SIDES, _CONTRACTIONS, _DEFINE, _IF, _KNOWN, _MONTHS, _MONTH_INDEX, _NUMBER_WORDS, _SHAPE_RULES, _TRAILERS, _WEEKDAYS, _WHEN_NOISE, _WRAPPERS, _alternatives, _build_synonyms, _guessing_recent, _holds, _overview, _stem, _still_recent, _without_command, _words, asks_time, asks_written_when, classify, compare_sides, rephrase, subject_terms, user_now, user_today, what_is  # noqa: F401  (moved; re-exported)
from tessellate.ai.composer_read import LEAD_INS, LEAD_INS_BARE, MAX_QUOTE_CHARS, NoteView, Sentence, _HEADING_LEAD, _ITEM, _LEAD_IN, _MARKS, _PICTURES_HEAD, _SPLIT, _SPLIT_HYPHEN, _WHERE_CUE, _cue, _depth, _discourse, _distinct_ids, _heading_text, _picture_groups, _picture_spans, _picture_text_breaks, _short_fact, _title, _unit, _written, plain_words, read_note, source_kind as source_kind  # noqa: F401  (moved; re-exported)
from tessellate.ai.composer_select import KIND_WORDS, MAX_PER_NOTE, MAX_POINTS, MEANING_POOL, NEAR_DUPLICATE, RELATIVE_FLOOR, _ASKS_NOW, _FIGURE, _Meaning, _NEGATION, _score, _term_weights, centrality, correcting, disagree, select, superseded  # noqa: F401  (moved; re-exported)
from tessellate.ai.composer_answer import _Answer, _LEARNED, _NOW_WORDS, _REGISTER, _RELATIVE_DAYS, _SESSION, _count_word, _due, figures_of  # noqa: F401  (moved; re-exported)
from tessellate.ai.composer_quote import _OPENERS, _checklist_count, _joined, _lowered, _pick, _quotes, _sentence_case  # noqa: F401  (moved; re-exported)
from tessellate.ai.composer_unfound import _FRAME_WORDS, _MISSING_MIN, _frame_stems, _missing, _seen  # noqa: F401  (moved; re-exported)
from tessellate.ai.composer_body import BROAD_NOTES, FULL_POINTS, _BROAD, _NOTE_NOUNS, _asked_span, _body, _compare, _confirmed_lead, _days_named, _disagreement, _disagreements, _insight_close, _insight_lead, _insights_for, _kinds, _mentions, _newest, _notes_named_by, _opening, _others, _overview_line, _relation, _span, _still_open, _summary, _timeline, _until_note, _versus_answer, heading_name, length_wish, told_as_past  # noqa: F401  (moved; re-exported)
from tessellate.ai.composer_dialogue import Dialogue, NEXT_MAX_CHARS, _BARE, _BOLD, _MORE, _ORDINAL, _ORDINALS, _PRONOUN, _RESTATES, _follow_pronoun, _named_notes, _next_questions, _standing, follow_on, refers_back  # noqa: F401  (moved; re-exported)


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
