"""When the notes do not answer: a constraint that kept no note, an empty
time window, and the "nothing found" answer with a did-you-mean.

Moved whole from `composer.py` (audit AR3, gods-1101): the code is unchanged,
and `composer` re-exports every name here that anything reads, so
`composer.empty_window` still works. Imports run one way, down
the layer list in `composer.py`'s docstring, never back to `composer`.
"""

from __future__ import annotations

import contextvars
import re
from datetime import date

from tessellate.ai import composer_compose, composer_lines, composer_tables, grounding, recognise as rec, recognise_windows
from tessellate.ai.composer_answer import _Answer, _SESSION
from tessellate.ai.composer_ask import _holds, _stem, user_today
from tessellate.ai.composer_intent import _ACT_VERBS, _RECALL_VERBS, Plan
from tessellate.ai.composer_phrases import PHRASES
from tessellate.ai.composer_quote import _pick
from tessellate.ai.composer_read import NoteView
from tessellate.ai.composer_select import NOTE_COVERAGE
from tessellate.ai.composer_unfound import _MISSING_MIN, _NOT_A_NOUN, _seen, topic_word


#: The chat's own voice (natural, professional, playful or plain, a persona's
#: cue included) while `compose` runs: the no-answer is composed in it
#: (composer8). Empty means the two registers the callers already pass.
_REGISTER: contextvars.ContextVar[str] = contextvars.ContextVar("composer_register", default="")


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


def window_said(phrase: str, window: tuple | None = None) -> str:
    """A time window as an adverbial, with the preposition it needs ("on 20
    October", "in the last 7 days"; "last week" and "today" as they are):
    `recognise.adverbial`, the one reader of it; said with its capitals (audit
    1030 Z45). `window` (first day, last day) lets "last Christmas" name its year."""
    return recognise_windows.with_holiday_year(rec.proper_days(rec.adverbial(phrase)), window[0] if window else None)


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
        #: A note with more under its title (a table whose header was all it
        #: had, a picture) is not "only a title" (round 2 E1).
        if sum(1 for line in str(v.note.get("content") or "").splitlines() if line.strip()) > 1:
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


def _window_voice(voice: str, register: str) -> str:
    """"natural" or "professional": the chat's own register wins over the saved voice."""
    if register:
        return {"warm": "natural", "formal": "professional"}.get(composer_compose.voice_for(register), composer_compose.voice_for(register))
    return "professional" if composer_tables.voice_of(voice) == "professional" else "natural"


def _nothing_planned(when: str) -> str:
    """A day that has not come holds no notes written then: what is on it is what is planned (R9-8)."""
    return f"Nothing is planned {when if when.startswith(('on ', 'for ', 'in ', 'next ', 'this ')) else 'for ' + when}."


#: The one line an empty notebook gets on every surface (second audit, composed list).
EMPTY_NOTEBOOK = "Nothing yet. Write a first note and I'll have something to say."


def empty_window(when: str, first: date | None, last: date | None, *, voice: str = "natural", seed: str = "",
                 today: date | None = None, register: str = "", window: tuple | None = None) -> str:
    """A time window with no note in it, said as that, and where the notes
    are (`first` and `last` written days; None for an empty notebook).
    `register` is the chat's own voice (a persona's cue included); `window`
    is the days asked, so one that starts after the newest note is answered
    with that note."""
    voice = _window_voice(voice, register)
    today = today or user_today()
    when = window_said(when, window)
    if window and window[0] > today:
        return _nothing_planned(when)
    lead = _pick(seed or when, "empty_window", list(_EMPTY_WINDOW[voice])).format(when=when, When=when[:1].upper() + when[1:])
    if first is None or last is None:
        return EMPTY_NOTEBOOK if voice in ("natural", "professional") else lead

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


def _act_verb(word: str) -> bool:
    """An act's verb in any ending: "added", "removing", "pinned"."""
    word = word.lower()
    bases = {word} | {word[: -len(end)] for end in ("ed", "d", "ing", "s", "es") if word.endswith(end)}
    bases |= {b[:-1] for b in bases if len(b) > 2 and b[-1] == b[-2]} | {b + "e" for b in bases}
    return bool(bases & _ACT_VERBS.keys())


def _says(stem: str, term: str, words: set[str]) -> bool:
    """The word as the person wrote it, in any ending ("agreed" for "agree"), not by a synonym."""
    return stem in words or _seen(term, words)


def stray_match(terms: list[str], views: list[NoteView]) -> list[str]:
    """The question's words no note holds, when the notes meet it only on an
    everyday word they use for something else; else nothing.

    "how many vacation days do I have left" over notes that say "Day trip to
    Nara" and "Water every second day": no note holds "vacation", and the
    notes meet the question only on "day" in passing. The nearest note is a
    stray then, never an answer (CHAT_PLAN, placed 2026-10-30, item 3). Not a
    stray: a note holding more than `NOTE_COVERAGE` of the words as written,
    a shared word that is not everyday ("dentist", "Harbor", "jr"), or one a
    note is about, in its name, tags or category ("the car repair" and the
    note called Car service; "the meeting" and Meeting with Priya)."""
    asked = [(_stem(t), t) for t in dict.fromkeys(terms) if len(t) >= 2]
    held = [v.words | v.title_words | v.filed_words for v in views]
    if len({s for s, _ in asked}) < 2 or any(_covers(asked, words) for words in held):
        return []
    found = [(s, t) for s, t in asked if any(_holds(s, words) for words in held)]
    heads = [v.title_words | v.filed_words | _leads(v) for v in views]
    if not found or len(found) == len(asked) or not all(_in_passing(s, t, heads) for s, t in found):
        return []
    return [t for s, t in asked if not any(_says(s, t, words) for words in held)]


def _covers(asked: list[tuple[str, str]], words: set[str]) -> bool:
    return sum(_says(s, t, words) for s, t in asked) / len(asked) > NOTE_COVERAGE


def _leads(view) -> set[str]:
    """The names of a note's ledger rows: "Phone 30." in a budget is about the phone.
    Only a name and an amount; "Day trip to Nara" opening on "day" is not about days off."""
    return {_stem(s.words[0]) for s in view.sentences if 2 <= len(s.words) <= 3 and s.words[-1][:1].isdigit()}


def _in_passing(stem: str, term: str, heads: list[set[str]]) -> bool:
    """An everyday word no note is about (its name, tags or category)."""
    from tessellate.ai.common_words import WORDS

    return stem in WORDS and not any(_says(stem, term, h) for h in heads)


def _named(stray: list[str]) -> list[str]:
    """The missing words worth naming: not an everyday word ("time", "change",
    "agree") and not a verb's ending ("approved"); none, and the reply names
    nothing."""
    from tessellate.ai.common_words import WORDS

    return [w for w in stray if w.lower() not in WORDS and _stem(w) not in WORDS and not _NOT_A_NOUN.search(w)]


def _modifies(word: str, question: str, terms: list[str]) -> bool:
    """One word no note holds, set just before a word one does ("the spare
    key"), says which of it: a half answer, not a stray."""
    after = re.search(rf"\b{re.escape(word)}\s+([\w'-]+)", question or "", re.I)
    return bool(after) and after.group(1).lower() in {t.lower() for t in terms}


def stray_reply(out: _Answer, question: str, shape: str, terms: list[str], views: list[NoteView], unsure: list[dict], voice: str,
                *, chosen: list, said: str) -> dict | None:
    """The notes meet the question only on an everyday word (`stray_match`):
    said to be missing, never answered with the nearest note (CHAT_PLAN,
    placed 2026-10-30, item 3). None otherwise. An act's own verb no note
    holds ("i need cleaning added"), or a verb of the notebook's own ("what
    have I saved about lectures"), is not a topic the notes lack."""
    if not chosen or said:
        return None
    stray = [w for w in stray_match(terms, views) if topic_word(w) and w.lower() not in _RECALL_VERBS and not _act_verb(w)]
    if not stray or (len(stray) == 1 and _modifies(stray[0], question, terms)):
        return None
    #: Each word quoted on its own ("boss", never "boss scheduled"), and no feature's help: the question is about the person's own things.
    return _nothing(shape, unsure, voice, [_as_typed(w, question) for w in _named(stray)], out)
