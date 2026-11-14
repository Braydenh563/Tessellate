"""In-app guidance chat: "how do I..." answers about Tessellate itself.

ROADMAP.md item 40's "mini AI chat half", deliberately its own path,
separate from `librarian.converse`/`librarian.answer`, because those two
answer from the user's notes or hold a general conversation, and this one
must do neither: it only explains the app. Uses the utility model (not the
main chat model), its own system prompt, and a preset that is Quick's shape
(low temperature) with two differences: thinking is left to
the model rather than turned off, because the panel draws the thinking while
it happens and Quick's `think: False` made that box dead markup
(`presets.GUIDE_MODE`, which is off the user-facing picker on purpose), and
the reply cap is 640 tokens rather than 256, so a controls reference listed
in full is not cut off mid-list (INBOX 410).

**The model is the utility model, and it is the utility model's own
fallbacks that decide what that means.** `ModelManager.utility_model()`
answers the chat model in two cases: smart model routing turned off, and no
utility model chosen. Both are the documented behaviour and neither is a bug
here, but together they are why the Guide can be seen running the chat model
while every line of copy around it says "your utility model", so
`tests/test_help_chat.py` pins which model a real request takes in each of
the three cases rather than leaving it to be read off this sentence.

**Grounded, not just instructed.** A first version of this module told the
model "don't invent a feature you're not sure exists" and gave it nothing
else to go on, for a small local model that has never heard of Tessellate,
that is an instruction with no way to follow it: refusing to guess and
guessing wrong look identical from inside the prompt. `HELP_TOPICS` below is
the fix: a short, factual reference entry per feature area, and what
Settings, Help lists (drawn from this table since INBOX 448). The question is
matched against it by keyword, and whichever entries match get attached to
the prompt as the only material the model is allowed to answer from. Keeping
`HELP_TOPICS` in step with the app is what "the chatbot's information is up
to date" means in practice, and it is why this module, not the docs alone, is the thing
future sessions should re-check first when a feature's behaviour changes.

No persistence: nothing here writes to the database. The caller (the
frontend) is the one holding the running transcript, in memory only, for
exactly as long as the spec allows, this module only ever sees what it's
handed on each call.
"""

from __future__ import annotations

import functools
import logging
import math
from datetime import datetime
import re
from collections import Counter
from collections.abc import Iterator

from tessellate import SUPPORT_EMAIL
from tessellate.ai import AI_NAME
from tessellate.ai.provider import ProviderError
from tessellate.ai import act_registry, guide_lead, guide_titles, help_words, presets, variants
from tessellate.ai.guide_lead import help_sentences  # the sentence cutter, a leaf with the lead rules (G5)
from tessellate.ai.help_topics_core import HELP_TOPICS  # the table, moved out whole (AI23)
from tessellate.ai import guide_outside
from tessellate.ai.help_leads import TOPIC_LEADS
from tessellate.ai.help_topics_more import HELP_GROUPS, TOPIC_META
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # annotations only: the speller reads this module's topics,
    # and importing the model manager drew in SQLAlchemy for a typed question.
    from tessellate.ai.model_manager import ModelManager
    from tessellate.ai.provider import Provider

#: **The guide's name, in one place** (INBOX 204, the owner: "give the help ai
#: a name fitting for the application like a persona and improve its
#: capabillity and knowledge"; CHAT_PLAN.md section 4 decision 15, which
#: supersedes decision 13's naming half). An atlas is a book of maps, the thing
#: you open to find your way around a place you are already standing in, which
#: is exactly what this chat is for an app called Tessellate. It is a name for a
#: reference work rather than for a person, so decision 13's actual objection
#: still holds: nothing here claims a personality, or to know the reader, or to
#: have read a word of their notebook.
#:
#: Every surface that says the name reads it from here or from
#: `GUIDE_NAME` in the frontend, because a persona whose name is typed out in
#: nine places is a persona with nine chances to be renamed in eight.
GUIDE_NAME = AI_NAME  # one name for the notebook's AI (INBOX 225), spelt once in ai/__init__

SYSTEM_PROMPT = (
    f"You are {GUIDE_NAME}, the in-app guide to Tessellate (formerly MemoryMap AI), a local-first "
    "notebook. Your name is the name of a book of maps: you are a reference "
    "the person opens to find their way around the app, and you say so if "
    "asked who you are. You answer ONLY questions "
    "about how to use the Tessellate app itself: its features, tabs, and "
    "settings. You have no access to the user's notes or documents, so if "
    "asked a question about their notebook's own content, say plainly that "
    "this chat is for app guidance only and point them to the Chat or Ask "
    "tab instead of guessing. Base your answer only on the reference notes "
    "given to you below the question, if any are given, never invent a "
    "button, setting, or feature that isn't in them. If no reference notes "
    "are given, or they don't cover the question, say plainly that you're "
    "not sure and suggest checking the Help topics above this chat instead "
    "of guessing. Keep answers short: a few sentences or a short numbered "
    "list of steps: and name the exact tab or settings section involved. "
    "Write plainly, in sentence case, with no exclamation marks and no "
    "greeting before the answer. If the person describes an error, a crash "
    "or something that does not work, add one line at the end: open "
    "Settings, then Logs, press Email it under the support bundle, and the "
    f"report goes to {SUPPORT_EMAIL} with the bundle to attach."
)

#: Kept only for anything still importing the name. The Guide no longer
#: answers with an apology when the model is off: see `offline_answer`, which
#: hands over the help text this sentence used to point at.
OFFLINE_MESSAGE = (
    f"{GUIDE_NAME} isn't available right now (the local model doesn't seem "
    "to be running): the Help topics above still work without it."
)


#: **Which entry answers "the keys of" a surface.** A question that names a
#: surface and asks about its keys, controls or hidden corners is about that
#: surface's controls entry, and the ranking below cannot see that on words
#: alone: "whiteboard" belongs to the description and "shortcut" to the global
#: shortcuts entry, so without this the question landed on one of those two.
_CONTROLS_FOR: dict[str, str] = {
    "whiteboard": "whiteboard-controls",
    "mind-maps": "mind-map-controls",
    "documents": "documents-controls",
    "graph": "graph-controls",
    "ask-chat": "chat-controls",
    "capture": "notes-controls",
    "library": "library-controls",
    "timeline": "timeline-controls",
    "reminders": "reminders-controls",
    "dashboard": "dashboard-controls",
    #: The code editor's entry is its own controls reference (see its body).
    "code-files": "code-files",
}

#: The words that make a question about a surface a question about its
#: controls. Deliberately narrow: "how do I make a mind map" is not one, and
#: that is the question most people ask.
_CONTROL_INTENT = re.compile(
    r"\b(?:shortcuts?|keybinds?|keybindings?|key ?binds?|hotkeys?|keys|keyboard|"
    r"controls?|gestures?|chords?|hidden|secret|tips|tricks|power user|"
    r"everything (?:i|you) can do|what can i do|all the (?:features|tools|things))\b"
)

#: **The chords themselves are keywords.** "What does F12 do" names nothing
#: but a key, and the entry that documents F12 is the right answer; every
#: chord a controls entry's body names is added to its keywords, lowercased,
#: so the table and the prose cannot disagree about which keys an entry
#: covers. `_normalise_keys` below spells a question's chords the same way.
_CHORD = re.compile(
    r"(?<![\w+])(?:(?:Ctrl|Shift|Alt)\+)+(?:F\d{1,2}|Enter|Tab|Up|Down|Left|Right|"
    r"[A-Za-z0-9]\b|[/.,=\-\[\]])|(?<![\w+])Shift\+F\d{1,2}\b|(?<![\w+])F\d{1,2}\b"
)

#: A tight window: this is guidance, not a conversation to reminisce in.
MAX_HISTORY_TURNS = 6
MAX_MESSAGE_CHARS = 1000
#: **A history turn is the Guide's own answer handed back**, so its bound is
#: what the Guide writes, not what a person types (INBOX 410): an offline
#: controls answer runs past 1,600 characters, and the route refused any turn
#: over `MAX_MESSAGE_CHARS`, so the question after one failed with a 422.
#: The prompt still cuts each turn to `MAX_MESSAGE_CHARS` (`_prompt_for`):
#: this bound is what the route accepts, not what the model is sent.
MAX_HISTORY_TURN_CHARS = 4000
#: **Where the question was asked from** (INBOX 190: "maybe give it more
#: knowledge and capabilitie/function"). The Guide is reachable from every tab
#: now, so "how do I do this" is asked with something specific on screen, and
#: until this it answered as though the question had arrived from nowhere.
#: A tab pulls in its own topics whether or not the question names them, which
#: is what lets "how does this work?" on the Graph tab be a question about the
#: graph. The ids are `HELP_TOPICS` ids; a tab with no entry simply adds
#: nothing, which is the correct behaviour for a surface the topics do not
#: cover yet.
TAB_TOPICS: dict[str, tuple[str, ...]] = {
    "dashboard": ("dashboard",),
    "notes": ("capture", "memory"),
    "chat": ("ask-chat", "skills"),
    "graph": ("graph",),
    "library": ("library", "files-images", "whiteboard"),
    "documents": ("documents",),
    "timeline": ("timeline",),
    "reminders": ("reminders",),
    "whiteboard": ("whiteboard", "whiteboard-controls"),
    "mindmap": ("mind-maps", "mind-map-controls"),
    "statistics": ("statistics",),
    "settings": ("settings-overview",),
}

#: How much of the surface's own help copy the client may send with a
#: question. The caller passes the `.help-body` text of whatever is on screen
#: (frontend/js/settings.js), which is the app's own wording for the thing being
#: asked about and therefore the best possible reference note: it is also
#: user-supplied input on the wire, so it is capped here rather than trusted
#: to have been capped there.
MAX_CONTEXT_CHARS = 1200

#: How many reference entries to hand the model for one question. Kept
#: small on purpose: item 40 asked for "a tight prompt/context budget",
#: and a guidance answer is about one or two features, not a syllabus.
MAX_TOPICS = 3


# Whole-word match, not a raw substring one, a plain `in` check let "ask"
# match inside "basket" and "task", and a wrongly-matched topic means the
# model gets handed reference notes about the wrong feature. Compiled once
# at import time rather than per call: this runs on every `/help/ask`
# request, and re-compiling ~100 small regexes (18 topics x ~6 keywords)
# on every one of them is wasted work an unbounded local model call already
# dwarfs, but costs nothing to avoid.
#
# **Whole word, but not one single form of the word** (INBOX 304, the owner:
# "the help bot is useless, or the suggested questions are bad or both"). He
# asked "Where do reminders live?" and was told the guide was not sure, with
# Notes and What it remembers named as its sources. The reminders entry was
# in this table the whole time: the keyword is "reminder", the pattern was
# `\breminder\b`, and the plural he typed does not match it. Nothing matched,
# so the tab's own topics filled in, and a question about reminders was
# answered from the notes and memory entries. Every plural in the app had the
# same hole: "documents", "notes", "spaces", "backups". The keyword table is
# written in the singular by anyone adding to it, and people ask in whichever
# number reads naturally, so the number is handled here once rather than by
# asking thirty entries to list both forms and catching the next one late.
#
# A fixed set of inflections, not a stemmer: "-s", "-es" and the possessive,
# plus "-y" to "-ies" for a keyword like "library". Anything less regular
# ("recur" to "recurring") is spelt out in the keyword tuple, where it can be
# read, rather than guessed at by a rule loose enough to match it.


#
# **Lookarounds rather than `\b`** (INBOX 410): a keyword can be a chord now
# ("ctrl+/", "tag:"), and `\b` after a "/" or a ":" asks for a word character
# to follow it, which "what does ctrl+/ do" does not have. The guards below are
# `\b` exactly where a keyword starts or ends with a word character, and no
# guard where it does not; a chord is also refused when it is only the tail
# of a longer one ("shift+k" inside "ctrl+shift+k").
def _keyword_pattern(keyword: str) -> re.Pattern[str]:
    if len(keyword) > 3 and keyword.endswith("y") and keyword[-2] not in "aeiou":
        stem = re.escape(keyword[:-1]) + "(?:y|ies)"
    else:
        stem = re.escape(keyword) + "(?:es|'s|s)?"
    start = r"(?<![\w+])" if "+" in keyword else (r"(?<!\w)" if keyword[0].isalnum() else "")
    end = r"(?!\w)" if keyword[-1].isalnum() else ""
    return re.compile(rf"{start}{stem}{end}")


#: A chord as people type it ("ctrl shift f", "Cmd-K", "control k") spelt the
#: way the entries spell it ("ctrl+shift+f"), so a chord keyword can match.
#: The lookahead insists on a key after the modifier, so "shift and drag" and
#: "the control panel" are left alone. The separator is one bounded choice
#: (CodeQL 426: `\s*(?:\+|-|\s)\s*` let a run of tabs split three ways).
_MODIFIER = re.compile(
    r"\b(ctrl|control|cmd|shift|alt|option)(?:\s{0,3}[+\-]\s{0,3}|\s{1,3})"
    r"(?=(?:ctrl|control|cmd|shift|alt|option)\b|f\d{1,2}\b|enter\b|tab\b|up\b|down\b|"
    r"left\b|right\b|[a-z0-9](?![a-z0-9])|[/.,=\-\[\]])"
)
_MODIFIER_NAMES = {"control": "ctrl", "cmd": "ctrl", "option": "alt"}


@functools.lru_cache(maxsize=8192)  # 3,100 keywords a question: 1.5 million calls a 600-turn eval (CI time 1102)
def _normalise_keys(lowered: str) -> str:
    return _MODIFIER.sub(lambda m: _MODIFIER_NAMES.get(m.group(1), m.group(1)) + "+", lowered)


#: The chord keywords, added here rather than beside `_CHORD` because they are
#: compared in `_normalise_keys`'s spelling. **A chord an entry already names
#: in its own keywords is that entry's**: "ctrl k" is the command palette's,
#: and the five controls entries that mention Ctrl+K in passing must not
#: outvote the entry about it.
_CLAIMED_KEYS = {_normalise_keys(k) for _topic in HELP_TOPICS for k in _topic["keywords"]}
for _topic in HELP_TOPICS:
    if _topic["id"] in set(_CONTROLS_FOR.values()) | {"shortcuts", "hidden-features"}:
        _chords = dict.fromkeys(c.lower() for c in _CHORD.findall(_topic["body"]))
        _topic["keywords"] = _topic["keywords"] + tuple(c for c in _chords if c not in _CLAIMED_KEYS)


#: **The Guide's gold, 2026-10-11** (`tests/fixtures/composer/guide_1011.json`,
#: 25 questions typed the way people ask): the words that took a question to
#: the wrong topic, edited on the topics added after the first table, which
#: that table cannot reach. "why is the chat so slow" is speed, not Chat;
#: "where did my deleted notes go" is the bin; "export everything to
#: markdown" is Import & export.
_KEYWORDS_ADD_GUIDE: dict[str, tuple[str, ...]] = {
    "performance": ("so slow", "is slow", "running slow", "takes ages", "sluggish"),
    "undo-bin": ("deleted", "deleted notes", "deleted note", "undo deleting", "undelete"),
    "import-export": ("export", "markdown", "to markdown", "as markdown", "backup", "back up my notes"),
    "meetings": ("record a meeting", "record meetings", "record the meeting"),
    "notes-controls": ("lots of notes", "many notes", "notes at once", "all at once"),
    "tag-manager": ("rename a tag", "rename tags", "merge tags", "delete a tag"),
}
_KEYWORDS_REMOVE_GUIDE: dict[str, tuple[str, ...]] = {
    "storage": ("export everything",),
}
for _topic in HELP_TOPICS:
    _drop = set(_KEYWORDS_REMOVE_GUIDE.get(_topic["id"], ()))
    _topic["keywords"] = tuple(k for k in _topic["keywords"] if k not in _drop) + tuple(
        k for k in _KEYWORDS_ADD_GUIDE.get(_topic["id"], ()) if k not in _topic["keywords"]
    )


@functools.lru_cache(maxsize=None)
def _keyword_regex(keyword: str) -> re.Pattern[str]:
    return _keyword_pattern(_normalise_keys(keyword))


def _keyword_in(keyword: str, lowered: str) -> bool:
    """`_keyword_pattern(keyword)` found in `lowered`, compiled only when it can
    match (compiling all 2,200 at import was 0.5 s of the start, INBOX 1307): a
    pattern matches only where its literal stem occurs, so a substring test settles most."""
    normal = _normalise_keys(keyword)
    stem = normal[:-1] if len(normal) > 3 and normal.endswith("y") and normal[-2] not in "aeiou" else normal
    return stem in lowered and _keyword_regex(keyword).search(lowered) is not None


_WORD = re.compile(r"[a-z0-9]+")

#: Single-word keywords long enough to forgive a typo in (a four-letter word
#: one letter off is usually a different word).
_TYPO_MIN = 5

#: How many topics each keyword belongs to, for the rarity weight below.
#: Every word the topics' keywords use: what a word the English list does not
#: hold is read as (`help_words.forgive`).
_KEYWORD_WORDS = frozenset(w for t in HELP_TOPICS for k in t["keywords"] for w in _WORD.findall(k.lower()) if len(w) >= 4)
_KEYWORD_TOPICS: dict[str, int] = Counter(k for t in HELP_TOPICS for k in set(t["keywords"]))

#: Body vocabulary per topic, for tie-breaking only (see `_matching_topics`).
_BODY_WORDS: dict[str, set[str]] = {
    topic["id"]: set(_WORD.findall(topic["body"].lower())) for topic in HELP_TOPICS
}

#: Words that say nothing about which feature is meant.
_STOP = frozenset(
    "a an the i me my you your it its is are am be to of in on at for and or "
    "how do does did can could would should what whats where which who why "
    "when this that there here with from into about any all some so if not "
    "no yes get got make use using used want need way".split()
)

#: A runner-up worth showing scores at least this share of the best: below
#: it, the second topic is noise the answer would be padded with.
_RUNNER_UP_SHARE = 0.4
_WORD_BAND = help_words.WordBand(HELP_TOPICS, _WORD, _STOP, _keyword_in)


#: The asking frame of a how-to, taken off before the rest is read as a
#: sentence ("how do I pin a note" reads "pin a note").
_HOW_FRAME = re.compile(r"^\s*(?:how (?:do|can|would|should) (?:i|you)|how to|can i|can you|where do i|is there a way to)\s+", re.I)


#: Words naming a surface other than a note: "rename a category" or "add a
#: branch to a mind map" is that surface's own how-to, not a note act.
_OTHER_SURFACE = re.compile(
    r"\b(?:graph|board|whiteboard|canvas|sticky|map|mind ?map|branch|document|chat|category|categories|timeline|"
    r"library|palette|tab|folder|space|file|photo|template|word|order|sort|arrange|reorder|diagram|flowchart)s?\b", re.I)


def _act_of(question: str) -> tuple[str, bool] | None:
    """The act a how-to names, read through the one reading (`ai/reading.py`,
    decision 59 step 4): the sentence after the asking frame, read as an act
    by `reading.read`, or by its first word when that is an act's verb (the
    slots a real request needs are not asked for in a how-to). With whether
    it was read whole (an act the reading itself gave). None for a how-to
    about another surface."""
    inner = _HOW_FRAME.sub("", question or "").strip(" ?.")
    if not inner or inner == (question or "").strip(" ?.") or _OTHER_SURFACE.search(inner):
        return None
    if act_registry.reader is None:
        return None
    got = act_registry.reader(inner, now=datetime.now())
    if got.intent in act_registry.ACTS and got.intent not in ("navigate", "open", "find"):
        return got.intent, True
    first = inner.split()[0].lower()
    for act in act_registry.ACTS.values():
        if act.writes and (act.intent == first or act.verb == first) and act.intent not in ("meeting", "new_note", "append"):
            return act.intent, False
    return None


def _reading_topics(question: str) -> list[dict]:
    """The reading band first (decision 59, step 4): a how-to that reads as
    a note act is answered from the act registry (`act_registry.act_topic`):
    first when the reading gave the act whole or the words reached no topic,
    else after the topic the words reached. The keyword rules are the
    fallback band (`_matching_topics`)."""
    topics = _matching_topics(question)
    read = _act_of(question)
    if read is None:
        return topics
    act, whole = read
    own = act_registry.act_topic(act)
    if topics and (not whole or topics[0]["id"] in act_registry.ACT_HELP_TOPICS.get(act, ())):
        return [topics[0], own, *topics[1:]][:MAX_TOPICS]
    return [own, *topics][:MAX_TOPICS]


def _aliased_topics(question: str) -> list[dict]:
    """The topics a realistic phrasing names (`guide_aliases`, audit 1028
    E31), best first, then what the keyword rules reached that they did not:
    "how do I stop the AI" is the chat's Stop, with Models after it."""
    from tessellate.ai import guide_aliases

    by_id = {topic["id"]: topic for topic in HELP_TOPICS}
    lowered = _repaired(question).lower()
    named = [by_id[i] for i in guide_aliases.topic_ids(lowered) if i in by_id]
    reached = _reading_topics(question)
    #: A soft row never moves the first answer: it follows what the keywords
    #: reached, or stands alone when they reached nothing.
    got = {t["id"] for t in reached}
    soft = [
        by_id[i]
        for name, ids in guide_aliases.intents(lowered)
        if name not in guide_aliases.HARD and not got & set(ids)
        for i in ids
        if i in by_id
    ]
    seen: set[str] = set()
    out: list[dict] = []
    for topic in [*named, *reached, *soft]:
        if topic["id"] not in seen:
            seen.add(topic["id"])
            out.append(topic)
    return out[:MAX_TOPICS] if named or soft else []


def _repaired(question: str) -> str:
    """The question with its typos put right, once `question_noise` has
    registered its repair (`act_registry.repair`), else as typed."""
    return act_registry.repair(question) if act_registry.repair else question


#: "where do I find settings" asks where a place is, not for Find anything
#: (bug sweep 2026-10-12): the asking frame's "find" names no topic.
_WHERE_FIND = re.compile(r"\bwhere (?:do|can|would|should|will) (?:i|you|we) (?:find|locate|get to)\b")


def _forgiven(lowered: str, words: list[str]) -> tuple[str, list[str]]:
    """The question with each word the English list does not hold read as the
    topics' nearest word (VC15, `help_words.forgive`)."""
    fixes = help_words.forgive(words, _KEYWORD_WORDS, variants.english())
    if not fixes:
        return lowered, words
    return _WORD.sub(lambda m: fixes.get(m.group(), m.group()), lowered), [fixes.get(w, w) for w in words]


def _matching_topics(question: str) -> list[dict]:
    """Which `HELP_TOPICS` entries this question is about, best first.

    **Rebuilt 2026-09-24 against a question bank** (INBOX 406,
    `tests/fixtures/help_questions.json`, 100 questions phrased the way people
    type them): the old rule, one point per matching keyword weighted by its
    word count, answered 49 of them first-time right and matched nothing for
    20 (a typo, "pictures" for image, "talk to the ai" for chat). Four rules
    now, each measured against the bank:

    * **A topic qualifies on its keywords, never on its body**, so a question
      about the weather still matches nothing: a keyword is matched as a whole
      phrase with its plural (`_keyword_pattern`), or, for a single keyword of
      five letters or more, as a word one typo away.
    * **A keyword is worth its word count times its rarity**: "web search"
      still outweighs "search", and a word three topics share ("restore")
      says less than one only this topic has.
    * **Body words break ties**: among qualifying topics, one whose own text
      uses more of the question's words ranks higher.
    * **A runner-up must earn its place**: under 40% of the best score it is
      dropped, so the answer is not padded with a topic that matched one
      incidental word.
    """
    #: The question as it was meant (Brief 90, INBOX 837: "noficiations
    #: panel", "thes ebuttons"): misspellings put right, split words joined,
    #: before the keywords are read. The keyword typo rule below stays, for a
    #: word the speller does not know.
    lowered = _WHERE_FIND.sub("where", _normalise_keys(_repaired(question).lower()))
    words = [w for w in _WORD.findall(lowered) if w not in _STOP]
    lowered, words = _forgiven(lowered, words)
    total = len(HELP_TOPICS)
    english = variants.english()
    scores: dict[str, float] = {}
    for topic in HELP_TOPICS:
        score = 0.0
        for keyword in topic["keywords"]:
            rarity = 1.0 + math.log(total / _KEYWORD_TOPICS.get(keyword, 1))
            if _keyword_in(keyword, lowered):
                score += len(keyword.split()) * rarity
            elif (
                " " not in keyword
                and len(keyword) >= _TYPO_MIN
                and any(help_words.typo_of(w, keyword, english, _TYPO_MIN - 1) for w in words)
            ):
                score += 0.8 * rarity
        if (score := max(score, _WORD_BAND.score(words, lowered, topic["id"]))) > 0:
            scores[topic["id"]] = score
    if not scores:
        return _meaning_topics(question)
    #: **A surface's controls entry** (INBOX 410, see `_CONTROLS_FOR`). With
    #: a word asking for keys or controls, the named surface's controls entry
    #: goes above everything the words alone reached, the surface's own score
    #: ordering two named surfaces; without one, a controls entry that already
    #: qualified on its own keywords ("zoom", "lasso") takes the surface's
    #: score as well, which is what tells the graph's zoom from the board's.
    intent = bool(_CONTROL_INTENT.search(lowered))
    top = max(scores.values())
    for surface, controls in _CONTROLS_FOR.items():
        named = scores.get(surface)
        if not named:
            continue
        if intent:
            scores[controls] = max(scores.get(controls, 0.0), top) + named
        elif controls in scores and controls != surface:
            scores[controls] += named
        #: The description stays in the answer as a related entry, so the
        #: offline reply still names "graph" under the graph's controls.
        if controls != surface and controls in scores:
            scores[surface] = max(named, scores[controls] * _RUNNER_UP_SHARE)
    scored: list[tuple[float, int, dict]] = []
    for order, topic in enumerate(HELP_TOPICS):
        score = scores.get(topic["id"])
        if score is None:
            continue
        body = _BODY_WORDS[topic["id"]]
        score += 0.15 * sum(1 for w in words if w in body)
        scored.append((score, order, topic))
    scored.sort(key=lambda row: (-row[0], row[1]))
    best = scored[0][0]
    return [topic for score, _, topic in scored[:MAX_TOPICS] if score >= best * _RUNNER_UP_SHARE]


def _meaning_topics(question: str) -> list[dict]:
    """**By meaning, when no keyword matched** (Brief 94, INBOX 857): the
    words read as the things they name (`meaning.alts`: "too much moving
    stuff" is motion, "the robot" is the companion), held by a topic's title
    and keywords, the nearest first. A fallback only, so the question bank's
    keyword answers are unchanged."""
    from tessellate.ai import meaning

    things = meaning.alts(question)
    if not things or all(len(group) == 1 for group in things):
        return []
    scored = []
    for order, topic in enumerate(HELP_TOPICS):
        named = f"{topic_title(topic)} {' '.join(topic['keywords'])}"
        if meaning.holds(things, named):
            scored.append((meaning.closeness(things, named), order, topic))
    if not scored:
        return []
    scored.sort(key=lambda row: (-row[0], row[1]))
    best = scored[0][0]
    return [topic for score, _, topic in scored[:MAX_TOPICS] if score >= best * _RUNNER_UP_SHARE]


def topic_title(topic: dict) -> str:
    return TOPIC_META.get(topic["id"], {}).get("title") or topic.get("title") or topic["id"].replace("-", " ").capitalize()


#: **The system answer** (INBOX 430, the owner: "a toggle on each answer
#: between the AI's answer and the system-generated answer from the app's
#: help", with "clean formatting: headings, steps, the setting's path, and a
#: link that opens it"). The best-matching entry, laid out: its title as a
#: heading, where it lives, its text, its steps when it has some, and the
#: other entries worth reading named at the end. The link is the entry's
#: badge (`open`), which the client draws as a button that goes there; a
#: link inside the Markdown could only be a URL, and a URL cannot open a
#: settings row. The same text is the offline answer, so the Guide with no
#: model answers exactly as the toggle's other side does.
def system_answer(topics: list[dict], said: str = "") -> dict:
    """The topic as written; `said` is the line that says how a misspelt question was read ("I took that to mean ...", L53)."""
    if not topics:
        return {"content": "", "open": None}
    first = topics[0]
    meta = TOPIC_META.get(first["id"], {})
    lines = ([said.strip()] if said.strip() else []) + [f"### {topic_title(first)}"]
    if meta.get("path"):
        lines.append(f"**Where:** {meta['path']}")
    lines.append(first["body"])
    steps = meta.get("steps") or ()
    if steps:
        lines.append("\n".join(f"{n}. {step}" for n, step in enumerate(steps, 1)))
    related = [topic_title(topic) for topic in topics[1:]]
    if related:
        lines.append("**Related:** " + ", ".join(related))
    return {"content": "\n\n".join(lines), "open": first.get("badge")}


def source_names(topics: list[dict]) -> list[str]:
    return [topic["id"].replace("-", " ").capitalize() for topic in topics]


def help_listing() -> dict:
    """Every entry, in `HELP_GROUPS` order, for Settings, Help (INBOX 448).

    `find` is the entry's keywords, which the Settings search reads beside the title so a row
    is found by the words a person types ("percentage") and not only by its name; `link` is
    the entry's badge, the same tab or section an answer's chip opens."""
    by_id = {topic["id"]: topic for topic in HELP_TOPICS}
    groups = []
    for title, ids in HELP_GROUPS:
        topics = []
        for topic_id in ids:
            if (topic := by_id.get(topic_id)) is None:
                continue
            topics.append(
                {
                    "id": topic_id,
                    "title": topic_title(topic),
                    "path": TOPIC_META.get(topic_id, {}).get("path", ""),
                    "lead": TOPIC_LEADS.get(topic_id, ""),  # never prompt text (INBOX 1612)
                    "body": topic["body"],
                    "find": " ".join(topic["keywords"]),
                    "link": topic["badge"],
                }
            )
        groups.append({"title": title, "topics": topics})
    return {"groups": groups}


def badges_for(topics: list[dict]) -> list[dict]:
    """The quick-access chips for a set of matched topics, de-duplicated by
    label and capped: same cap as `MAX_TOPICS`, since each matched topic
    contributes at most one badge."""
    seen: set[str] = set()
    out: list[dict] = []
    for topic in topics:
        badge = topic["badge"]
        if badge["label"] not in seen:
            out.append(badge)
            seen.add(badge["label"])
    return out


def _about_the_guide(question: str) -> list[dict]:
    """Who and what the Guide is: its own topic grounds a model's answer (the
    offline reply is first person and needs none)."""
    if _WHO.match(question or "") or _CAPABLE.match(question or ""):
        return [topic for topic in HELP_TOPICS if topic["id"] == "guide"]
    return []


#: A question that points at the screen ("how does this work", "what is here").
_DEICTIC = re.compile(r"\b(?:this|here|these|that one|on screen|this page|this tab)\b", re.I)


def _outside_the_app(question: str) -> bool:
    """Whether the open tab's blurb must NOT stand in for an answer: the
    world's questions, requests ("tell me a joke"), prompt injection and
    questions about the person's own notes get the honest "nothing in the
    help matches". A question that points at the screen or asks how to do
    something, or is gibberish, still falls back to the tab (audit 1030 A18)."""
    from tessellate.ai import personal

    if _DEICTIC.search(question):
        return False
    if _off_topic(question) or guide_outside.CREATIVE.match(question) or guide_outside.world_how_to(question):
        return True
    return bool(personal.general(question) or (personal.about_own_record(question) and not guide_outside.HOW_TO_APP.match(question)))


_INJECTION = re.compile(r"\b(?:ignore|disregard|forget) (?:all |any |your |the )?(?:previous|prior|above|earlier|system) (?:instructions|rules|prompt)\b|\b(?:print|show|reveal|repeat) (?:me )?(?:your|the) (?:system )?prompt\b", re.I)


_WHO_IS_MY = re.compile(r"^(?:who(?:'s| is| are| was)|what(?:'s| is) the name of) (?:my|our) \w+(?: \w+)?[?.!]*$", re.I)


#: A request for the person's own list ("what are my tasks", "show my
#: reminders", "what tasks do I have"): the contents are in Chat, and a keyword
#: match with the help ("tasks" is Mind map controls) is no answer (A18).
_ITEMS = r"(?:open |due |overdue |upcoming |current |pending )?(?:tasks?|to-?dos?|to do(?: list)?|todo list|reminders?)"
_MY_ITEMS = re.compile(
    rf"^\s*(?:(?:what|which)(?: are| is|'s)?(?: on)?|show|list|get|see|tell me|give me)(?: me)?(?: all)?(?: of)? (?:my|our) {_ITEMS}\b"
    rf"|^\s*(?:what|which) {_ITEMS} do i have\b",
    re.I,
)


def _off_topic(question: str) -> bool:
    """A request the help text cannot answer however a keyword in it matches:
    a prompt injection, or a question about a person in the person's life
    ("who is my sister" matched the Entities topic). Neither is the app (A18)."""
    return bool(_INJECTION.search(question) or _WHO_IS_MY.match(question.strip()) or _MY_ITEMS.match(question))


def topics_for(question: str, tab: str | None = None) -> list[dict]:
    """The reference entries for one question, asked from one tab.

    What the question names wins outright. The tab's own topics are a
    fallback for a question that names nothing, and they are what makes "how
    does this work?" answerable at all: with no keyword in it, that question
    matched nothing and the model was told to say it was not sure.

    **A fallback, not a supplement** (INBOX 304). They used to be appended to
    whatever the question matched, up to `MAX_TOPICS`, so a question asked
    from the Notes tab was grounded in the notes and memory entries however
    clearly it named its own subject, and the answer printed Notes and What it
    remembers as its sources. Two thirds of the reference material was then
    about something the person had not asked about, on a small local model
    with a 256-token reply: the wrong entries do not sit there politely, they
    are what the model answers from. The tab is still on the prompt as a line
    of its own ("the person asking has the notes tab open"), which is the part
    of the context that was worth having.
    """
    about_guide = _about_the_guide(question) or guide_titles.topic(question, HELP_TOPICS)
    if about_guide:
        return about_guide
    if social_reply(question):
        #: A greeting names no feature, so the open tab's topics are not its
        #: answer either (INBOX 787: "hey" was answered with the Dashboard).
        return []
    #: What the words ask comes before what they share a keyword with (B11):
    #: "how do I use the app" is the overview from any tab, "what is this
    #: page for" the tab's own topic, never the board library's "page".
    from tessellate.ai import guide_intent

    read = guide_intent.topics(question, tab, {topic["id"]: topic for topic in HELP_TOPICS}, TAB_TOPICS)
    if read:
        return read
    if _off_topic(question):
        return []
    topics = _aliased_topics(question) or _reading_topics(question)
    if not tab or topics or _outside_the_app(question):
        return topics
    return _tab_topics(tab, topics)


def _tab_topics(tab: str, topics: list[dict]) -> list[dict]:
    """`topics` with the open tab's own topics after them, up to `MAX_TOPICS`."""
    seen = {topic["id"] for topic in topics}
    by_id = {topic["id"]: topic for topic in HELP_TOPICS}
    for topic_id in TAB_TOPICS.get(tab, ()):
        if len(topics) >= MAX_TOPICS:
            break
        if topic_id in seen or topic_id not in by_id:
            continue
        topics.append(by_id[topic_id])
        seen.add(topic_id)
    return topics


def _prompt_for(
    question: str,
    history: list[dict] | None,
    tab: str | None,
    context: str | None,
) -> tuple[list[dict], list[dict]]:
    """The messages one turn sends, and the topics they were built from.

    Split out of `answer` so the streamed turn cannot build a different
    prompt from the one-shot turn: the two differ only in how the reply
    comes back, and a second copy of this is how a fix to one surface's
    grounding quietly misses the other.
    """
    topics = topics_for(question, tab)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if tab:
        messages.append(
            {
                "role": "system",
                "content": (
                    f"The person asking has the {tab} tab open. Prefer the answer "
                    "that applies to what is in front of them, and say which tab "
                    "or setting anything else is on."
                ),
            }
        )
    #: A greeting, thanks, "who are you" or "that didn't help" matches no
    #: topic, and the rule above then had the model say it was not sure
    #: (INBOX 1414, second round). The offline reply is the model's brief.
    social = social_reply(question)
    if social:
        messages.append(
            {
                "role": "system",
                "content": (
                    "This message is social, not about a feature. Reply in the first person in one or "
                    "two sentences, with no help text, in the spirit of: " + social["content"]
                ),
            }
        )
    if topics:
        reference = "\n".join(f"- {topic_title(topic)}: {topic['body']}" for topic in topics)
        messages.append(
            {"role": "system", "content": f"Reference notes for this question:\n{reference}"}
        )
    on_screen = (context or "").strip()[:MAX_CONTEXT_CHARS]
    if on_screen:
        messages.append(
            {
                "role": "system",
                "content": (
                    "The app's own help text for what is on screen right now, "
                    "which you may answer from as well:\n" + on_screen
                ),
            }
        )
    for turn in (history or [])[-MAX_HISTORY_TURNS:]:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content[:MAX_MESSAGE_CHARS]})
    messages.append({"role": "user", "content": question})
    return messages, topics


#: **The Guide, with no model running.**
#:
#: Asked for directly: *"I want to maximise the ability and function of all
#: the application features without ai, the ai features should just be the
#: bonus"*, and then again for this surface by name.
#:
#: The Guide is the one AI feature that never needed a model to be useful. Its
#: entire knowledge of this app is `HELP_TOPICS` above: one hand-written
#: paragraph per feature area, which is also the model's *only* source of
#: facts when a model does answer. `topics_for` picks the right ones from the
#: question and the tab, by keyword, with no inference anywhere in it. So with
#: no model the honest answer is not "I am not available": it is those
#: paragraphs, unedited, which is most of what the model would have said to
#: begin with.
#:
#: What is lost without the model is real and is not hidden: the paragraphs
#: are not rewritten to fit the question, several may arrive when one would
#: have done, and a question the keywords do not reach gets nothing. The reply
#: says so in its first line rather than passing this off as an answer
#: composed for the asker.
#: Said after the answer, never before it (decision 59, step 4; the Guide
#: row "the answer first, the preface goes"): the reply says where it came
#: from in words a person would use (INBOX 787: "From the app's own help
#: text, word for word: no model is running." read badly).
OFFLINE_LEAD = "From the app's help, with no model running."

#: The miss line never blames the model (G5): its words are `guide_lead.MISS`.
OFFLINE_NOTHING_MATCHED = guide_lead.MISS

def _nothing_matched(question: str) -> str:
    """The no-match line, with the three nearest topic names when the
    question shares words with any ("Did you mean: ..."): a miss is a short
    menu, not a dead end (audit 1028 E31)."""
    from tessellate.ai import guide_aliases

    near = guide_aliases.did_you_mean(question, HELP_TOPICS, topic_title)
    if not near:
        return OFFLINE_NOTHING_MATCHED
    return f"{OFFLINE_NOTHING_MATCHED}\n\nDid you mean: {', '.join(topic_title(t) for t in near)}?"


#: **A greeting is answered as one** (INBOX 787: "hey" was answered with the
#: open tab's topic, the Dashboard's paragraph, twice). The reply says who is
#: answering and the client puts the tab's three starters under it
#: (`atlasStartersFor`), so the first thing to ask is one tap away.
_GREETING = re.compile(
    r"^\W*(?:hi|hey|hello|hiya|howdy|yo|good (?:morning|afternoon|evening))"
    r"(?:\s+(?:there|again|atlas|guide))?\W*$",
    re.I,
)
_THANKS = re.compile(r"^\W*(?:thanks|thank you|thx|cheers|ta)(?:\s+(?:atlas|a lot|so much|very much))?\W*$", re.I)
GREETING_REPLY = (
    f"Hi, I'm {GUIDE_NAME}, the app's guide. Ask me where a feature lives, "
    "what a setting does or how to do something here. Three to start with:"
)
THANKS_REPLY = "You're welcome. Ask me about any tab or setting."
THANKS_WORKED_REPLY = "Glad that worked. Ask me if anything else gets in the way."

#: **Open and social questions** (INBOX 1414), read from the words and answered
#: in the first person, in a line or two, with no help dump and no resume
#: offer. The tab's three starters go under the ones that flag `greeting`.
_THANKS_LONG = re.compile(r"^\W*(?:thanks|thank you|thx|cheers)\b[^?]{0,40}$", re.I)
_WORKED = re.compile(r"\b(?:worked|helped|great|perfect|brilliant|solved|fixed|got it)\b", re.I)
_CAPABLE = re.compile(
    r"^\W*(?:so )?(?:what (?:can|could) you (?:help (?:me )?(?:with|do)|do(?: for me)?)"
    r"|what do you (?:do|know)|what are you (?:for|good for|able to do)|what is your (?:job|purpose))\W*$",
    re.I,
)
_WHO = re.compile(r"^\W*(?:who|what) are you\W*$|^\W*who (?:is|are) (?:atlas|you)\W*$|^\W*what is atlas\W*$", re.I)
_MISSED = re.compile(
    r"^\W*(?:that|this|it)(?:'s| is| was)? ?(?:didn'?t|did not|doesn'?t|does not|isn'?t|is not|wasn'?t|was not|not)"
    r" (?:help|work|right|what i (?:asked|meant|wanted)|helpful|useful|it|correct|answer)\b[^?]{0,30}$"
    r"|^\W*(?:you(?:'re| are)|that(?:'s| is)|this is) (?:wrong|incorrect|useless|not right|no help|not helpful)\W*$"
    r"|^\W*(?:wrong|not helpful|useless|that'?s not what i (?:asked|meant|wanted))\W*$",
    re.I,
)
_ORGANISE = re.compile(
    r"^\W*(?:how (?:do|can|should) (?:i|we)|help me|can you help me|i want to|i need to)\s+"
    r"(?:organi[sz]e|sort|tidy(?: up)?|clean up|arrange)\s+(?:this|it|things|everything|my stuff|stuff|all this)\W*$",
    re.I,
)
_CAN_YOU = re.compile(r"^\W*(?:can|could|would|will) you\b", re.I)
WHO_REPLY = (
    f"I'm {GUIDE_NAME}, the app's guide, named for a book of maps. I answer questions about "
    "Tessellate from its own help: where a feature lives, what a setting does, how to do something."
)
CAPABLE_REPLY = (
    "I can tell you where a feature lives, what a setting does and the steps for most things "
    "in the app. Ask in your own words, or pick one of these:"
)
MISSED_REPLY = (
    "Sorry, that missed. What are you trying to do? A few words is enough, such as "
    "\u201cadd a reminder\u201d, and I will look for the steps. Or pick one of these:"
)
ORGANISE_REPLY = (
    "I can help with that. Do you mean tags and categories on your notes, links between "
    "notes, or the layout of the Graph? Tell me which and I will show you the steps."
)
BEYOND_REPLY = (
    "I can't do that one. I answer questions about using Tessellate: where things are, "
    "what a setting does and how to do something in it. Is there something in the app I can help you find?"
)


def _beyond(question: str) -> dict:
    return {"content": BEYOND_REPLY, "badges": [], "sources": [], "social": True}


def social_reply(question: str) -> dict | None:
    """The Guide's reply to a greeting, thanks, complaint or free-form question
    about itself, or None for a question about the app."""
    text = (question or "").strip()
    if _GREETING.match(text):
        return {"content": GREETING_REPLY, "badges": [], "sources": [], "greeting": True}
    if _THANKS.match(text) or _THANKS_LONG.match(text):
        reply = THANKS_WORKED_REPLY if _WORKED.search(text) else THANKS_REPLY
        return {"content": reply, "badges": [], "sources": [], "social": True}
    if _WHO.match(text):
        return {"content": WHO_REPLY, "badges": [], "sources": [], "social": True}
    if guide_outside.WHAT_ARE_YOU.match(text):
        return {"content": guide_outside.WHAT_ARE_YOU_REPLY, "badges": [], "sources": [], "social": True}
    if _CAPABLE.match(text):
        return {"content": CAPABLE_REPLY, "badges": [], "sources": [], "greeting": True}
    if _MISSED.match(text):
        return {"content": MISSED_REPLY, "badges": [], "sources": [], "greeting": True}
    if _ORGANISE.match(text):
        return {"content": ORGANISE_REPLY, "badges": [], "sources": [], "social": True}
    return None


#: **The composed answer** (INBOX 787, the owner: "they should have the option
#: to see either the base help text or a slightly more customised version with
#: the composer"). The question's own answer first (where it is, for a where;
#: the help sentence that best answers it, for anything else), then the
#: steps or one more sentence, then where the feature lives. Every sentence is
#: the help text's own or a fixed phrase around its path; the topic word for
#: word is the other side of the answer's toggle (`system_answer`).
#: A place is added only to a question that wants one (INBOX 1414: "what can
#: you help me with" was given the guide's own button). A how-to carries its
#: place in its steps.
_FIND_ASKED = re.compile(r"\b(?:where|find|locate|get to|go to|navigate|located|which (?:tab|menu|setting))\b", re.I)
_WHERE_ASKED = re.compile(r"^\s*(?:where(?:'s| is| are| do| can| would)?|which (?:tab|setting|menu))\b", re.I)


#: A second sentence longer than this is a wall, not a help: the topic's
#: own text, a tap away, has it.
SECOND_SENTENCE_WORDS = 35
_HOW_ASKED = re.compile(r"^\s*(?:how (?:do|can|should|would) (?:i|you|we)|how to|can i|is there a way)\b", re.I)
_COUNTS = ("no", "one", "two", "three", "four", "five", "six")


def _place(path: str) -> str:
    """"the Reminders tab" for "Reminders tab", "the gear ..." for "The gear ..."; a Settings path as written."""
    return f"the {path[4:]}" if path.startswith("The ") else (f"the {path}" if path.endswith(" tab") else path)


def _second_sentence(question: str, body: str, said: str) -> str:
    """One more sentence of the topic that shares a word with the question
    and is not the one already said, else ""."""
    wanted = {w for w in _WORD.findall(question.lower()) if w not in _STOP and len(w) > 2}
    for line in help_sentences(body):
        if line == said or said.startswith(line) or line in said or len(line.split()) > SECOND_SENTENCE_WORDS:
            continue
        have = set(_WORD.findall(line.lower()))
        if any(h == w or (min(len(h), len(w)) >= 5 and (h.startswith(w) or w.startswith(h))) for w in wanted for h in have):
            return line
    return ""


def _guide_lead(question: str, topics: list[dict]) -> str:
    """The help sentence that best answers `question` (`composer.help_line`).
    Before the composer is loaded (a bare import of this module), the
    topic's first sentence leads: never an answer with no answer in it."""
    from tessellate.ai import capability

    if topics[0]["id"] == "privacy" and capability.privacy_line(question):
        return capability.privacy_line(question)
    line = act_registry.help_sentence(question, topics) if act_registry.help_sentence else None
    lead = line[0] if line else next(iter(help_sentences(topics[0]["body"])), "")
    #: "Or type the reminder, ...": the topic's joining word is not the
    #: answer's first word.
    joined = re.match(r"(?:Or|And|But|Also|So),? (?=[a-z])", lead)
    return lead[joined.end()].upper() + lead[joined.end() + 1:] if joined else lead


def _guide_opening(question: str, path: str, steps: tuple, lead: str) -> tuple[list[str], bool, bool]:
    """The answer's first lines, and whether it said the place and walked
    the steps: where it is for a where-question; how many steps and where
    from for a how-to with steps; else the lead sentence."""
    where = bool(path) and bool(_WHERE_ASKED.match(question))
    walk = bool(steps) and bool(_HOW_ASKED.match(question)) and len(steps) < len(_COUNTS)
    #: A path that is itself a sentence ("the bin: the Library's Include ...") is not "It's in" it.
    head, colon, tail = path.partition(": ")
    place = (f"It's in {head}, reached with {tail}." if colon else f"It's in {_place(path)}.") if where else ""
    #: A place is said first ("where is the bin"); a question about what happens (`guide_lead.place_last`) opens on the topic's sentence.
    lines = [lead, place] if guide_lead.place_last(question) else [place, lead]
    #: A how-to with steps says the steps, not the sentence before them (G5 g).
    lines = [x for x in lines if x and not (x == lead and walk)]
    return lines, where, walk


def _preference(key: str, default: bool) -> bool:
    try:
        from tessellate.core import deps

        return bool(deps.get_config().get_preference(key, default))
    except Exception:  # noqa: BLE001  # no config (a bare import): say nothing of the state
        return default


def _stated_lead(question: str, topics: list[dict]) -> str:
    """The lead, after the switch's state when the topic has one; a lead
    that only gives the default ("off by default") gives way to the next
    sentence that answers, since the state now says it."""
    state = guide_lead.state_line(topics[0]["id"], _preference)
    lead = _guide_lead(question, topics)
    if state and re.search(r"\bby default\b", lead):
        lead = _second_sentence(question, topics[0]["body"], lead) or lead
    #: The topic's instruction is written for the switch off ("Turn it on
    #: in ..."); said after "... is on now." it contradicts, so each state
    #: gets its own sentence (audit 1031 AI12).
    if state.endswith(" is on now."):
        lead = re.sub(r"^Turn it on\b", "Turn it off", lead)
    return " ".join(x for x in (guide_lead.short_opening(question, topics[0]), state, lead) if x)


def _lead_topic_first(question: str, topics: list[dict]) -> list[dict]:
    """`topics` with the one whose sentence leads the answer first, so its
    steps, place and related list follow the sentence (a question that names
    an act is led by the topic that names it, not the best-ranked one)."""
    line = act_registry.help_sentence(question, topics) if act_registry.help_sentence and len(topics) > 1 else None
    if not line or line[1] == topics[0]["id"]:
        return topics
    lead = next((t for t in topics if t["id"] == line[1]), None)
    return [lead, *(t for t in topics if t is not lead)] if lead else topics


def composed_answer(question: str, topics: list[dict], led: guide_lead.Led | None = None) -> str:
    """The Guide's answer composed for `question` from the best topic; `led`
    is a lead the G5 rules chose (`guide_lead.lead_for`)."""
    led = led or guide_lead.Led(_lead_topic_first(question, topics))
    topics, first = led.topics, led.topics[0]
    meta = TOPIC_META.get(first["id"], {})
    path = str(meta.get("path") or "").rstrip(".")
    steps = tuple(meta.get("steps") or ()) if led.steps else ()
    lead = led.lead or _stated_lead(question, topics)
    lines, where, walk = _guide_opening(question, path, steps, lead)
    more = "" if steps else _second_sentence(question, guide_lead.own_topic(topics, lead, help_sentences)["body"], lead)
    lines += ["\n".join(f"{n}. {step}" for n, step in enumerate(steps, 1))] if steps else [more] if more else []
    #: The click path comes right under the lead sentence (the owner, 2026-11-12,
    #: L725): a question naming an act is still led by the sentence naming it.
    if path and not where and not walk:
        lines.insert(min(1, len(lines)), f"**Where:** {path}")
    related = guide_lead.related_titles(topics, " ".join(lines), topic_title)
    return "\n\n".join(lines + (["**Related:** " + ", ".join(related)] if related else []))


def _aware(reply: dict, question: str, tab: str | None, actions: list[str] | None) -> dict:
    """A composed Guide reply may end with where the person was and what they
    could ask next (`composer_aware`, local only). Nothing is added when the
    client sent no actions, or to a social reply. The next question is the
    tab's how-to only when the answer was about that tab (INBOX 1414: a web
    search answer ended on "how do I tag a note")."""
    from tessellate.ai import composer_aware

    if not actions or reply.get("greeting") or reply.get("social"):
        return reply
    matched = topics_for(question, tab)
    related = bool(matched) and matched[0]["id"] in TAB_TOPICS.get(tab or "", ())
    line = composer_aware.closing(
        composer_aware.build(tab=tab, actions=actions), seed=question.lower(), related=related, asked=question
    )
    #: Beside the answer, not in it (audit 1028 E52), as Chat's `tip` event.
    return with_asks({**reply, "tip": line}) if line else reply


def with_asks(reply: dict) -> dict:
    """`reply` with every question its text suggests as a chip that asks the
    Guide (INBOX 1497: "if it suggests a next question, I want a button
    to one click ask"). The sentence may stay; the chip is the action. A reply
    that already carries its own asks (what to ask in Chat) is left alone."""
    from tessellate.ai import ask_chips

    lifted = [] if reply.get("asks") else ask_chips.lift(f"{reply.get('content') or ''}\n\n{reply.get('tip') or ''}")
    return {**reply, "asks": lifted, "asks_to": "guide"} if lifted else reply


def composed_only(question: str) -> dict | None:
    """The turns that are the same with or without a model (G5 parity): a
    greeting or thanks, a yes or no about the app, and a question about the
    person's own notes, handed to Chat with a chip."""
    social = social_reply(question)
    if social:
        return social
    said = guide_lead.yes_no(question)
    if said:
        by_id = {t["id"]: t for t in HELP_TOPICS}
        used = [by_id[i] for i in said[1] if i in by_id]
        return {"content": said[0], "badges": badges_for(used), "sources": source_names(used)}
    return guide_lead.hands_over(question)


def _early_reply(question: str, tab: str | None) -> dict | None:
    """Read from the words, not the tab (B11, B86): asked for ideas, for help,
    or what Atlas can change; or beyond the app ("can you book a flight")."""
    from tessellate.ai import guide_intent

    read = guide_intent.reply(question, tab, {topic["id"]: topic for topic in HELP_TOPICS})
    if read:
        return read
    if _CAN_YOU.match(question) and not _reading_topics(question) and not guide_intent.read(question):
        return _beyond(question)
    return None


def _unplaced(question: str, context: str | None, *, missed: bool) -> dict:
    """A question this could not place is still asked *from somewhere*, and
    that somewhere describes itself (its help text, when there is any); the world's are outside the app (L-chat-38)."""
    if (outside := _outside_the_app(question)) and not missed and guide_outside.about_the_world(question):
        return {"content": guide_outside.outside_reply(question), "badges": [], "sources": [], "social": True}
    on_screen = (context or "").strip()[:MAX_CONTEXT_CHARS]
    if on_screen and not missed and not outside:
        return {"content": on_screen, "badges": [], "sources": []}
    return {"content": _nothing_matched(question), "badges": [], "sources": []}


def offline_answer(
    question: str,
    tab: str | None = None,
    context: str | None = None,
    history: list[dict] | None = None,
) -> dict:
    """The same shape `answer` returns, composed without a model.

    `content`, `badges` and `sources` all come from the matched topics, so an
    offline reply carries the same quick-access chips and the same named
    sources an online one does: the chips are what turn "reminders live on the
    Reminders tab" into a way to get there, and they are exactly as true with
    the model off.
    """
    from tessellate.ai import guide_intent

    question = (question or "").strip()[:MAX_MESSAGE_CHARS]
    if (fixed := composed_only(question)) is not None:
        return fixed
    question, said = _read_as(question)
    if (fixed := composed_only(question) or _early_reply(question, tab) or guide_outside.summed(question)) is not None:
        return fixed
    #: Understood by its words, so "Taking that as" is not said.
    said = "" if guide_intent.read(question) else said
    topics = topics_for(question, tab) if question else []
    #: "where do they show up" names nothing: it is about the last question's topic (G5 e).
    topics = topics or guide_lead.follow_topics(question, history, topics_for)
    led = guide_lead.lead_for(question, tab, topics, {t["id"]: t for t in HELP_TOPICS}, topic_title) if topics else None
    if not topics or (led and led.miss):
        return _unplaced(question, context, missed=bool(topics))
    #: **Composed by default, the help text a tap away** (INBOX 787). The
    #: composed answer is the content; `system` is the topic as written
    #: (INBOX 430's layout), which the client offers as "From the help".
    topics = led.topics if led else topics
    return with_asks({
        "content": f"{said}{composed_answer(question, topics, led)}",
        "badges": badges_for(topics),
        "sources": source_names(topics),
        "system": system_answer(topics, said),
    })


def _read_as(question: str) -> tuple[str, str]:
    """The question with its misspellings put right, and the line that says
    so ("Reading that as ..."), as the composer's answers open (ledger row
    404): "hwo do i set a remnder" gets the steps "how do I set a reminder"
    gets, not the topic's first sentence."""
    from tessellate.ai import composer_ack, question_noise

    fixed: list = []
    repaired = question_noise.repair(question_noise.tidy(" ".join(question.split())), fixed=fixed) if question else question
    #: A repair that breaks one of the help's own phrases is no repair: "note history" is not "not history" (L-chat-1).
    if not fixed or any(_keyword_in(k, question.lower()) and not _keyword_in(k, repaired.lower()) for k in _KEYWORD_TOPICS):
        return question, ""
    said = "".join(part[1] for part in composer_ack.acknowledge(repaired, voice="natural", seed=question))
    return repaired, said


def answer_stream(
    question: str,
    model_manager: ModelManager,
    ollama: Provider,
    history: list[dict] | None = None,
    tab: str | None = None,
    context: str | None = None,
    actions: list[str] | None = None,
) -> Iterator[dict]:
    """The same turn, streamed.

    Reported: the Guide's reply "will be blurted out really fast like it isnt
    streaming but just outputting at once", and its thinking "only shows up
    after the response is finished". Both were true and neither was a bug in
    the client: `/help/ask` answered in one piece after the whole reply had
    been generated, and the panel faked the writing with a timer, which is
    why it ran at a speed no model types at and why the thinking could not
    appear until there was nothing left to wait for.

    Yields `{"type": "thinking"|"delta", "text": str}` as the model produces
    them and one closing `{"type": "done", ...}` carrying the badges and
    sources, which are known before the first token but are sent last so the
    client has one place to finish a turn.
    """
    question = question.strip()[:MAX_MESSAGE_CHARS]
    if not question:
        yield {"type": "done", "content": "", "badges": [], "sources": []}
        return
    if (fixed := composed_only(question)) is not None:
        yield {"type": "delta", "text": fixed["content"]}
        yield {"type": "done", **fixed, "composed": True}
        return
    if not ollama.is_running():
        #: Not a canned apology: the app's own help text for what was asked,
        #: with the same chips and sources an answered turn carries. See
        #: `offline_answer`.
        offline = _aware(offline_answer(question, tab, context, history), question, tab, actions)
        yield {"type": "delta", "text": offline["content"]}
        #: `composed`: no model wrote it, so it arrives with the app's reveal
        #: (INBOX 1300 C28, `replyReveal` in reply-kit.js).
        yield {"type": "done", **offline, "composed": True}
        return

    messages, topics = _prompt_for(question, history, tab, context)
    pieces: list[str] = []
    #: `GUIDE_MODE` rather than `"quick"`: same brevity, same temperature,
    #: but thinking is not turned off, so the `thinking` events below are
    #: events that can actually happen. Under `"quick"` this loop's
    #: `thinking_delta` branch had never once run on a real backend.
    try:
        for piece in ollama.chat_stream(
            model_manager.utility_model(), messages, mode=presets.GUIDE_MODE
        ):
            thinking = piece.get("thinking_delta")
            if thinking:
                yield {"type": "thinking", "text": thinking}
            delta = piece.get("content_delta")
            if delta:
                pieces.append(delta)
                yield {"type": "delta", "text": delta}
    except ProviderError as exc:
        #: The model call was cut (a closed tab, a model that failed): not a server fault. The
        #: app's own help answers, as `/help/ask` does, and the log says why (L52).
        logging.getLogger("tessellate.help").info("help/ask: the model call ended: %s", exc)
        offline = _aware(offline_answer(question, tab, context, history), question, tab, actions)
        yield {"type": "done", **offline, "composed": True}
        return
    content = "".join(pieces).strip()
    yield {
        "type": "done",
        **with_asks({"content": content}),
        "badges": badges_for(topics),
        "sources": source_names(topics),
        "system": system_answer(topics),
    }


def answer(
    question: str,
    model_manager: ModelManager,
    ollama: Provider,
    history: list[dict] | None = None,
    tab: str | None = None,
    context: str | None = None,
    actions: list[str] | None = None,
) -> dict:
    """One turn of the help chat.

    `history` is whatever the caller is holding client-side for the current
    session (see module docstring): never read from or written to the
    database. `tab` is the surface the question was asked from and `context`
    that surface's own help copy, both optional and both only ever used to
    choose and extend the reference notes. Returns
    `{"content": str, "badges": list[dict]}`."""
    question = question.strip()[:MAX_MESSAGE_CHARS]
    if not question:
        return {"content": "", "badges": [], "sources": []}
    if (fixed := composed_only(question)) is not None:
        return {**fixed, "composed": True}
    if not ollama.is_running():
        return {**_aware(offline_answer(question, tab, context, history), question, tab, actions), "composed": True}

    messages, topics = _prompt_for(question, history, tab, context)
    #: Still `"quick"`, not `GUIDE_MODE`: this is the one-shot fallback, taken
    #: only when a stream could not be opened, and it returns one object at the
    #: end. There is nowhere for thinking to be shown on this path, so paying
    #: a reasoning model to produce it would buy the reader nothing but a wait.
    #: The Guide's own preset, as `answer_stream` uses: this is the fallback
    #: path for the same panel, and it asked for "quick" (Quick's cap, no
    #: thinking) until INBOX 410's cap test caught the two disagreeing.
    reply = ollama.chat(model_manager.utility_model(), messages, mode=presets.GUIDE_MODE)
    content = reply["content"].strip()
    return {
        **with_asks({"content": content}),
        "badges": badges_for(topics),
        "sources": source_names(topics),
        "system": system_answer(topics),
    }


# --- the app's own help, for the Chat tab and the agents --------------------
#
# Asked for directly: "give the chat tab chat ai and agent access to the help
# info as well in case users ask it questions for help". Reported beside it,
# with a screenshot: "how should I use the knowledge graph??" in Chat was
# answered from the notes ("none of them specifically explain how to use a
# knowledge graph"), because the Guide panel was the only thing that could
# read these entries.
#
# **Gated twice.** Topic keywords include everyday words ("note", "chat",
# "question"), so a keyword match alone would attach help to nearly every
# question about the notebook. The question has to be phrased as a how-to
# (`_HOW_TO`) *and* name a topic. Two entries at most, clipped, and carried
# with the question rather than in the system prompt, so the cached prefix
# stays byte-identical turn to turn.
_HOW_TO = re.compile(
    r"\b(how (do|can|should|would) (i|you|we)|how to|what can (i|you)|what does|"
    r"what is the|where (is|are|do|can)|is there a way|can (i|you)|help me|explain)\b",
    re.IGNORECASE,
)
HELP_BLOCK_MAX_TOPICS = 2
HELP_BLOCK_MAX_CHARS = 1400


def names_app(question: str) -> bool:
    """Whether a how-to the notes could not answer plainly names a part of the
    app: a keyword of several words ("connect a model"), or two keywords of
    the topic it matches. One single-word keyword is not enough: "how do I
    learn python" matches Code files on "python", and "how can I improve my
    sleep" Capture on "improve" (O1, measured 2026-10-17)."""
    if not question or not _HOW_FRAME.match(question):
        return False
    topics = _matching_topics(question)
    if not topics:
        return False
    lowered = question.lower()
    hits = [k for k in topics[0]["keywords"] if _keyword_in(k, lowered)]
    return len(hits) >= 2 or any(" " in k.strip() and not _HOW_FRAME.match(k) for k in hits)


def help_block_for(question: str) -> str:
    """The app's own help for a how-to question, as a block to put before it,
    or "" when the question is not asking how the app works."""
    if not question or not _HOW_TO.search(question):
        return ""
    topics = _matching_topics(question)[:HELP_BLOCK_MAX_TOPICS]
    if not topics:
        return ""
    text = "\n".join(f"- {topic_title(topic)}: {topic['body']}" for topic in topics)
    if len(text) > HELP_BLOCK_MAX_CHARS:
        text = text[: HELP_BLOCK_MAX_CHARS - 1].rstrip() + "…"
    return (
        "From Tessellate's own help (use this if the question is about how the "
        f"app works; it is not one of my notes):\n{text}\n\n"
    )
