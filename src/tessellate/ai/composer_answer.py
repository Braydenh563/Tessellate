"""The answer being built: `_Answer`, which holds the parts and the notes
they cite, the turn's session salt, and how a due day is said.

Moved whole from `composer.py` (audit AR3, gods-1101): the code is unchanged,
and `composer` re-exports every name here that anything reads, so
`composer._Answer` still works. Imports run one way, down
the layer list in `composer.py`'s docstring, never back to `composer`.
"""

from __future__ import annotations

import contextvars
import hashlib
import re
from datetime import date

from tessellate.ai import composer_tables, grounding, realise, recognise as rec
from tessellate.ai.composer_ask import _MONTHS, _stem
from tessellate.ai.composer_phrases import PHRASES
from tessellate.ai.composer_read import NoteView, Sentence
from tessellate.search import query as query_understanding
from tessellate.core.lazyre import lazy_compile


# --- composition ------------------------------------------------------------------


#: Number words for counts a reader takes in at a glance. Measured values,
#: spelled the way a sentence spells them; past twelve the digits read better.
_NUMBER_WORDS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve")


#: An opener that attributes the quote to the note or its writer.
_OWNS_IT = re.compile(r"\b(?:in your note|you noted)\b", re.I)


class _Answer:
    """The answer as tagged parts, the text being their join:

    - ("template", text): one of `PHRASES`, connective wording only;
    - ("quote", text, note_id): a note's sentence, as `read_note` trimmed it
      (and, inside a list sentence, its first letter lowered);
    - ("picture", text, note_id): the app's reading of a picture in the note;
    - ("title", text, note_id): a note's name, as `_title` read it;
    - ("filed", text, note_id): one of the note's tags or its category;
    - ("measure", text): a count or a day the app measured;
    - ("address", text): a link's brackets and in-app address;
    - ("asked", text): a word or phrase from the question itself.
    """

    def __init__(self, views: dict[int, NoteView], today: date) -> None:
        self.parts: list[tuple] = []
        self.rows: list[dict] = []
        self.views = views
        self.today = today
        self.cited: set[tuple] = set()
        #: The note the last sentence was about, so the next one about the
        #: same note can say "It" (the one pronoun written here, and only of
        #: a note named just before it).
        self.last_note: int | None = None
        #: The notes already named in this answer: a note is named once, at
        #: its first quote, and its later quotes go uncited (INBOX 741).
        self.named: set[int] = set()
        #: Whether a title-less note's citation also says the day it was written (a "when" ask; `composer._fresh_answer`).
        self.day_in_cite = False
        #: The question's subject, stemmed, for the openers that check a
        #: sentence holds all of it; and whether the next quote follows a
        #: joiner that ends in a comma, so its first letter is lowered.
        self.subject: set[str] = set()
        self.lower_next = False
        #: The answer the turn before gave, so this one opens differently.
        self.previous = ""
        #: The last three answers, oldest first: an opener none of them
        #: opened with is said first (`phrasing.RECENT`; the owner: "can it
        #: have more varied responses??").
        self.recent: list[str] = []
        #: The question as typed: a word the answer says it asked about is
        #: one of its words, never a corrected one.
        self.question = ""
        #: Asked for briefly ("in short", "quick"): no opener, no second list.
        self.brief = False
        #: The register the joining phrases and openers are written in.
        self.voice = composer_tables.DEFAULT_VOICE
        #: What earlier answers quoted ("tell me more"): never quoted again.
        self.said = ""
        #: The joining and opening words earlier answers in this conversation
        #: used (`Dialogue.used`): not used again while a variant is left.
        self.used: set[str] = set()
        #: The notes a question could mean, numbered (decision 45).
        self.readings: list[int] = []
        #: Say the person's "I" back as "you" (decision 33), except after an
        #: opener that promised their own words (`t`).
        self.shift = True
        self.verbatim = False

    def opened_with(self, text: str) -> bool:
        """Whether the answer the turn before gave began with `text`."""
        return bool(self.previous) and self.previous.startswith(text.strip() or text)

    def opened_lately(self, text: str) -> bool:
        """Whether one of the last three answers began with `text`: a
        family's wording is chosen against all three, while which family
        opens is chosen against the last alone (measured: against three,
        a 20-turn chat opened 13 ways rather than 15)."""
        lead = text.strip() or text
        return any(said.startswith(lead) for said in (self.recent or [self.previous]) if said)

    def later_turn(self) -> bool:
        """Whether this answer follows another in the chat: a previous answer, or a turn past the first."""
        turn = _SESSION.get().rpartition(":")[2]
        return bool(self.previous) or (turn.isdigit() and int(turn) > 1)

    def voiced(self, name: str) -> str:
        """The `PHRASES` key that says what `name` says in this answer's
        voice: one of its variants, chosen by the question so the same
        question is always answered in the same words, and never one the turn
        before opened with while another is left. The second half of a pair
        ("On " and " you wrote: ") takes its first half's variant."""
        by_voice = composer_tables.VOICE_VARIANTS[self.voice]
        lead = composer_tables.PAIRED.get(name, name)
        leads, mine = by_voice.get(lead), by_voice.get(name)
        if not leads or not mine:
            return name
        usable = [i for i, key in enumerate(leads) if not self.opened_lately(PHRASES[key])] or list(range(len(leads)))
        #: No template twice in a conversation (decision 25): a variant an
        #: earlier answer used is left while another is unused.
        #: Nor twice in one answer: two keys may share a wording ("separately"
        #: and "elsewhere" both say "In another place"), and `used` only learns
        #: an answer when its turn ends. A pair's second half follows its first.
        said = {p[1] for p in self.parts if p[0] == "template"} if lead == name else set()
        fresh = [i for i in usable if PHRASES[mine[i]] not in self.used and PHRASES[mine[i]] not in said]
        usable = fresh or usable
        session = _SESSION.get()
        digest = hashlib.sha1(f"voice:{lead}:{self.question.strip().lower()}{':' + session if session else ''}".encode()).digest()
        return mine[usable[digest[0] % len(usable)]]

    def t(self, *names: str) -> _Answer:
        for name in names:
            text = PHRASES[self.voiced(name)]
            self.parts.append(("template", text))
            #: An opener that promises the person's own words ("You wrote: ",
            #: "Here is how you put it: ") is kept to: what follows it, to the
            #: next line, is quoted as written, never shifted.
            if "\n" in text:
                self.verbatim = False
            if _CLAIMS_WORDS.search(text):
                self.verbatim = True
        return self

    def m(self, text: str) -> _Answer:
        if text in _RELATIVE_DAYS and self.parts and self.parts[-1][0] == "template" and self.parts[-1][1].endswith(("on ", "On ")):
            #: "on yesterday" is not English: the preposition goes, and a day that
            #: opens the sentence gets its capital (audit 1031 C36).
            before = self.parts[-1][1][:-3]
            self.parts[-1] = ("template", before)
            text = text.capitalize() if not before.strip() else text
        self.parts.append(("measure", text))
        return self

    def address(self, text: str) -> _Answer:
        """A link's brackets and its in-app address ("](#/notes/12)"):
        markup around a name, never a claim or a count."""
        self.parts.append(("address", text))
        return self

    def asked(self, text: str) -> _Answer:
        self.parts.append(("asked", text))
        return self

    def term(self, text: str, holder: NoteView) -> _Answer:
        """A word of the notes, as written there: a name or a thread that
        groups them ("League"), never a claim of its own."""
        self.parts.append(("term", text, holder.id))
        return self

    def name(self, view: NoteView, cap: bool = False) -> _Answer:
        """The note's name: its heading in bold, or, for a note with no
        heading, its first line cut at about six words with an ellipsis, in
        quotes (owner 2026-11-10: the same name in lists, compare and prose)."""
        self.last_note = view.id
        self.named.add(view.id)
        if view.titled:
            self.t("bold")
            self.parts.append(("title", view.title, view.id))
            return self.t("bold")
        self.parts.append(("title", self._first_line(view), view.id))
        return self

    @staticmethod
    def _first_line(view: NoteView) -> str:
        from tessellate.ai import composer_frame

        return composer_frame.name_of(view.note)

    def cite(self, view: NoteView, again: bool = False) -> _Answer:
        """The note an answer rests on, once per note unless `again`. No bracketed
        title follows the quote (decision D25, owner 2026-11-10): the numbered mark
        and the Sources list name it. What they cannot say is written, lightly: a
        titled note's name on its first mention in the chat ("From your Gym log
        note."), nothing on later turns about the same note, a title-less note's
        day for a when-ask, and a board, map, document, file or page by its kind."""
        if view.id in self.named and not again:
            return self
        self.named.add(view.id)
        if view.kind != "note":
            self.t("open_paren").t(f"kind_{view.kind}")
            self.parts.append(("title", view.title if view.titled else self._first_line(view), view.id))
            return self.t("close_paren")
        if not view.titled:
            #: Its first words are the quote itself; only a when-ask's day is new.
            return self.dated(view) if view.written and self.day_in_cite else self
        if self._said_before(view.title) or self._opener_names_the_note():
            return self
        bold = view.title
        if again:
            #: A row of a list from several notes: the title, plainly, in a parenthesis.
            self.t("open_paren", "bold")
            self.parts.append(("title", bold, view.id))
            return self.t("bold", "close_paren")
        if re.match(r"(?:the|a|an|my|your)\b", bold.strip(), re.I) or re.search(r"\bnotes?$", bold.strip(), re.I):
            self.t("cite_from_note", "bold")
            self.parts.append(("title", bold, view.id))
            return self.t("bold", "stop")
        self.t("cite_from", "bold")
        self.parts.append(("title", bold, view.id))
        return self.t("bold", "cite_note")

    def _opener_names_the_note(self) -> bool:
        """Whether the opener already says whose words these are ("The day in your note: "), so "From your Dentist
        note." after the quote would say the same twice (E23). Only the first note the answer names: the opener
        speaks for it, and a second note's line still needs its own source."""
        return len(self.named) == 1 and any(p[0] == "template" and _OWNS_IT.search(p[1]) for p in self.parts)

    def _said_before(self, title: str) -> bool:
        """Whether an earlier answer in this chat already named the note."""
        key = title.strip().lower()
        return bool(key) and any(key in (said or "").lower() for said in (*self.recent, self.previous))

    def _shifted(self, s: Sentence, text: str) -> str | None:
        """The sentence said to the person who wrote it (decision 33): "I
        went" as "you went", a plan whose day has passed in the past tense.
        None when nothing changes or the sentence is not the person's prose."""
        if not self.shift or s.kind not in ("prose", "item", "task") or self.verbatim:
            return None
        shifted = realise.shift_person(text)
        if shifted == text:
            return None
        shifted = realise.past_plan(shifted, _due(self.views[s.note_id].note, s), self.today)
        if text[:1].isupper():
            shifted = shifted[:1].upper() + shifted[1:]
        return shifted

    def q(self, s: Sentence, terms: list[str], shown: str | None = None) -> _Answer:
        """A quote, and its citation row: once per sentence, at its first use.
        `shown` is the quote as this answer prints it (a list item's first
        letter lowered inside a sentence); the row cites what is printed.
        A sentence in the first person is said in the second ("shifted"),
        its row keeping the note's own words as `original`."""
        text = s.text if shown is None else shown
        kind = "picture" if s.kind.startswith("picture") else "quote"
        shifted = None if kind == "picture" else self._shifted(s, text)
        if shifted:
            self.parts.append(("shifted", shifted, s.note_id, text))
            original, text = text, shifted
        else:
            self.parts.append((kind, text, s.note_id))
            original = None
        self.last_note = s.note_id
        if s.key in self.cited:
            return self
        self.cited.add(s.key)
        note = self.views[s.note_id].note
        content = str(note.get("content") or "")
        stems = {_stem(t) for t in terms}
        self.rows.append(
            {
                "sentence": text,
                "note_id": note.get("source_id", s.note_id),
                "start": s.start,
                "end": s.end,
                "score": round(s.score, 3),
                "chunk_ordinal": grounding.paragraph_ordinal(content, s.start, s.end),
                #: The quote is the note's own words: every word matches and
                #: it supports itself; no model measured meaning here.
                "signals": {"bm25": 1.0, "cosine": None, "graph": grounding._graph_nearness(note)},
                "verdict": "supported",
                "terms": [w for w in query_understanding.search_terms(text) if _stem(w) in stems][:6],
                "label": realise.cut_title(content, 60),
                #: The name the answer cites it by ("[**Dentist**]"), so the
                #: page can make that name open the note: matched exactly,
                #: never guessed from the label's opening words.
                "title": self.views[s.note_id].title if self.views[s.note_id].titled else "",
                "kind": self.views[s.note_id].kind,
            }
        )
        if note.get("url"):
            #: A web page's sentence is cited by its address (decision 37).
            self.rows[-1]["url"] = str(note["url"])
        #: How the page draws it (decision 33): a quoted sentence in the
        #: quote style, a shifted one with the note's own words on hover.
        self.rows[-1]["said"] = "picture" if kind == "picture" else "shifted" if original is not None else "quoted"
        if original is not None:
            #: Said back in the second person: the note's own words, which
            #: `start` and `end` point at, kept for the page to show.
            self.rows[-1]["original"] = original
        return self

    def item(self, s: Sentence, terms: list[str]) -> _Answer:
        """A bullet holding one quote; a checklist item keeps its tick."""
        if s.kind == "task":
            return self.t("task_done" if s.done else "task_open").q(s, terms)
        return self.t("bullet").q(s, terms)

    def day(self, when: date) -> str:
        """A measured day, worded: "today", "yesterday", "3 March", "3 March 2025"."""
        delta = (self.today - when).days
        if delta == 0:
            return "today"
        if delta == 1:
            return "yesterday"
        if when.year == self.today.year:
            return f"{when.day} {_MONTHS[when.month - 1]}"
        return f"{when.day} {_MONTHS[when.month - 1]} {when.year}"

    def count(self, n: int) -> str:
        return _count_word(n)

    def dated(self, view: NoteView) -> _Answer:
        """" (3 March)" after a note's name, when the day is known."""
        if view.written:
            self.t("open_paren").m(self.day(view.written)).t("close_paren")
        return self

    def placed_day(self, view: NoteView) -> date | None:
        """The day the timeline files the note under when it is not the day it
        was written: the first day its text names, to the day (INBOX 1739)."""
        placed = view.note.get("placed") or {}
        if not (placed.get("on") and view.written and placed.get("precision") in ("day", "minute")):
            return None
        try:
            on = date.fromisoformat(placed["on"])
        except ValueError:
            return None
        return on if on != view.written else None

    def dated_both(self, view: NoteView) -> _Answer:
        """" (3 March)", or, for a note the timeline files elsewhere, " (written
        3 March, about Friday 28 February)": the answer and the timeline agree on
        the note's day, or say both (INBOX 1739)."""
        about = self.placed_day(view)
        if about is None:
            return self.dated(view)
        return self.written_about(view, about).t("close_paren")

    def written_about(self, view: NoteView, about: date, top: bool = False) -> _Answer:
        """" (written 3 March, about Friday 28 February" (the bracket is closed by the caller),
        or, opening a line, "Written 3 March, about Friday 28 February"."""
        named = self.day(about)
        weekday = f"{about:%A} {named}" if named[:1].isdigit() else named
        return self.t("written_top" if top else "written_a").m(self.day(view.written)).t("about_a").m(weekday)

    @property
    def text(self) -> str:
        return realise.mend_stops("".join(part[1] for part in self.parts))


#: The openers that promise the person's words as written: after one, the
#: run is quoted, not shifted (`_Answer.t`).
_CLAIMS_WORDS = lazy_compile(r"\b(?:wrote|written|put it|own words|phrasing|exactly|noted|jotted|write)\b[^:]*:\s*$", re.I)


def _due(note: dict, s: Sentence) -> date | None:
    """The last day a plan or a future event in sentence `s` names, read by
    the fact layer against the note's own day; None when the sentence names
    none (a plan with no day of its own is never moved into the past)."""
    from tessellate.ai import factgraph

    days = [
        f.when[1] for f in factgraph.facts(note)
        if f.kind in ("plan", "event", "date") and s.start <= f.start < s.end and f.when and not f.inherited
        and (f.kind != "event" or f.attrs.get("tense") == "future")
    ]
    return max(days) if days else None


def _count_word(n: int) -> str:
    return _NUMBER_WORDS[n] if 0 <= n < len(_NUMBER_WORDS) else str(n)


#: The conversation's salt and turn, set by `compose` for the length of one
#: answer (decision 34): "Ask again" in the same chat is a later turn, so its
#: openers and joins are chosen again; empty outside a conversation, where the
#: same question gets the same words every time.
_SESSION: contextvars.ContextVar[str] = contextvars.ContextVar("composer_session", default="")


def figures_of(text: str) -> frozenset:
    """The amounts `text` names ("run 8 km"), as (dimension, base value). The
    search drops a lone digit, so a sentence that holds the same amount is
    ranked for it (audit 1030 Z4: "when did I run 8 km" led with a 6 km run)."""
    return frozenset((d, round(v, 6)) for d, v, _unit, _at in rec.measures(text))


_NOW_WORDS = lazy_compile(r"\b(?:now|currently|current|latest|these days|any ?more|new one)\b", re.I)


def asks_now(question: str) -> bool:
    """The question asks what holds now ("what's my current address")."""
    return bool(_NOW_WORDS.search(question))


_RELATIVE_DAYS = frozenset({"today", "yesterday", "tomorrow"})
