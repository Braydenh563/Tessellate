"""The facts under a note's sentences, typed by rule (CHAT_PLAN Phase 6,
decision 30): the layer the composer measures, times and relates notes with.

A fact is a span of the note's own text and what kind of thing it says: an
event ("met Sam"), a quantity ("5 km"), a count of things ("5 sets"), money ("$1,200"), a date ("on
Friday", resolved against the day the note was written), a duration, an
entity (a capitalised name), a list or checklist item, a decision, a
preference, a plan, a question, a link, a quotation, a topic. Every fact
carries its offsets, so whatever is said from it can be traced back to the
characters it came from, and its *mode*: asserted, negated, hypothetical
("maybe", "might"), conditional ("if"), question, or quoted (inside quotation
marks, or after "said", "wrote", "according to"). Someone else's words are
never read as the person's own: no event, plan, decision or preference is
taken from inside a quotation, and the realiser never shifts its pronouns.

Rules only: tables and patterns, no model, no network. Built lazily per note
and cached per revision (the note's id, its edit time and a hash of its
text), so a notebook read twice is read once. Polarity by lexicon, in the
specification, is left out: no feature asked for uses it (decision 30's own
condition), and the contrast insight reads preferences, which are typed here.
"""

from __future__ import annotations

import calendar
import hashlib
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import date, datetime, time

from tessellate.ai import recognise
from tessellate.ai import recognise_units
from tessellate.ai import recognise_questions
from tessellate.ai import when as when_words
from tessellate.core import clock
from tessellate.core.lazyre import lazy_compile

_WEEKDAY_WORDS = frozenset("monday tuesday wednesday thursday friday saturday sunday mon tue tues wed thu thur thurs fri sat sun".split())

KINDS = (
    "event", "quantity", "count", "money", "date", "duration", "entity", "list_item", "check_item",
    "decision", "preference", "plan", "question", "link", "quote", "topic",
)
MODES = ("asserted", "negated", "hypothetical", "conditional", "question", "quoted")


@dataclass(frozen=True)
class Fact:
    """One typed span of a note. `start`/`end` index the note's `content`;
    `text` is exactly `content[start:end]`. `when` is (first day, last day,
    grain) the sentence's time words name, read against the note's own date;
    a sentence with none inherits the note's day (`inherited`)."""

    kind: str
    source_id: int
    start: int
    end: int
    text: str
    attrs: dict = field(default_factory=dict, compare=False, hash=False)
    mode: str = "asserted"
    when: tuple | None = None
    inherited: bool = False
    confidence: float = 1.0


# --- the tables ------------------------------------------------------------------

#: Irregular verbs: lemma, past, past participle. The common ones a notebook
#: says what happened with; a past form here or a regular "-ed" of a lemma in
#: `_REGULAR` is an event.
_IRREGULAR = (
    ("be", "was were", "been"), ("begin", "began", "begun"), ("break", "broke", "broken"), ("bring", "brought", "brought"),
    ("build", "built", "built"), ("buy", "bought", "bought"), ("catch", "caught", "caught"), ("choose", "chose", "chosen"),
    ("come", "came", "come"), ("cut", "cut", "cut"), ("do", "did", "done"), ("draw", "drew", "drawn"), ("drink", "drank", "drunk"),
    ("drive", "drove", "driven"), ("eat", "ate", "eaten"), ("fall", "fell", "fallen"), ("feel", "felt", "felt"),
    ("fight", "fought", "fought"), ("find", "found", "found"), ("fly", "flew", "flown"), ("forget", "forgot", "forgotten"),
    ("get", "got", "gotten"), ("give", "gave", "given"), ("go", "went", "gone"), ("grow", "grew", "grown"),
    ("hang", "hung", "hung"), ("have", "had", "had"), ("hear", "heard", "heard"), ("hold", "held", "held"),
    ("keep", "kept", "kept"), ("know", "knew", "known"), ("lead", "led", "led"), ("leave", "left", "left"),
    ("lend", "lent", "lent"), ("lose", "lost", "lost"), ("make", "made", "made"), ("meet", "met", "met"),
    ("pay", "paid", "paid"), ("put", "put", "put"), ("read", "read", "read"), ("ride", "rode", "ridden"),
    ("ring", "rang", "rung"), ("rise", "rose", "risen"), ("run", "ran", "run"), ("say", "said", "said"),
    ("see", "saw", "seen"), ("sell", "sold", "sold"), ("send", "sent", "sent"), ("set", "set", "set"),
    ("shoot", "shot", "shot"), ("sing", "sang", "sung"), ("sit", "sat", "sat"), ("sleep", "slept", "slept"),
    ("speak", "spoke", "spoken"), ("spend", "spent", "spent"), ("stand", "stood", "stood"), ("steal", "stole", "stolen"),
    ("swim", "swam", "swum"), ("take", "took", "taken"), ("teach", "taught", "taught"), ("tell", "told", "told"),
    ("think", "thought", "thought"), ("throw", "threw", "thrown"), ("understand", "understood", "understood"),
    ("wake", "woke", "woken"), ("wear", "wore", "worn"), ("win", "won", "won"), ("write", "wrote", "written"),
    ("hit", "hit", "hit"), ("let", "let", "let"), ("quit", "quit", "quit"), ("shut", "shut", "shut"), ("dig", "dug", "dug"),
    ("feed", "fed", "fed"), ("light", "lit", "lit"), ("slide", "slid", "slid"), ("stick", "stuck", "stuck"),
    ("swing", "swung", "swung"), ("bend", "bent", "bent"), ("bite", "bit", "bitten"), ("blow", "blew", "blown"),
    ("freeze", "froze", "frozen"), ("hide", "hid", "hidden"), ("shake", "shook", "shaken"), ("tear", "tore", "torn"),
)
#: Regular verbs a note records doing; their "-ed" is an event's past.
_REGULAR = frozenset(
    """add agree allow answer apply arrange arrive ask attend avoid bake book borrow call cancel change charge check
    clean climb close collect compare complete confirm contact cook copy cover cross dance decide deliver deploy design
    discuss drop email end enjoy enter fail file finish fix follow help hike hire install invite join jump kick land
    launch learn like list listen live look love mail manage mark measure mention merge miss move name need note open
    order organise organize pack paint pass pick plan plant play post prepare present print promise publish pull push
    rain reach receive record register release remember remove rent repair replace reply report request rest return
    review rinse save schedule search serve share ship shop sign simmer start stay stop study submit test text thank
    tidy touch train travel try turn update upgrade use visit vote wait walk want wash watch water work worry
    backup bike camp code commit email fill fry jog lift log mix park ping pitch row sail ski skate slice stretch
    surf sync tag text tour type wire wrap""".split()
)
_AUX_FUTURE = lazy_compile(r"\b(?:will|'ll|shall|going to|gonna)\s+(?:not\s+)?([a-z]+)\b", re.I)
_DID_NOT = lazy_compile(r"\b(?:did not|didn't|never)\s+([a-z]+)\b", re.I)
_PROGRESSIVE_FUTURE = lazy_compile(r"\b(?:am|is|are|'m|'re)\s+(going)\b(?!\s+to\b)", re.I)


def _past_forms() -> dict[str, str]:
    forms: dict[str, str] = {}
    for lemma, past, _participle in _IRREGULAR:
        if lemma in ("be", "have"):
            continue
        for word in past.split():
            forms[word] = lemma
    for lemma in _REGULAR:
        if lemma.endswith("e"):
            forms[lemma + "d"] = lemma
        elif lemma.endswith("y") and lemma[-2:-1] not in "aeiou":
            forms[lemma[:-1] + "ied"] = lemma
        elif re.fullmatch(r"[^aeiou]*[aeiou][bdgmnprt]", lemma) and len(lemma) <= 4:
            forms[lemma + lemma[-1] + "ed"] = lemma
        else:
            forms[lemma + "ed"] = lemma
        if lemma.endswith("l") and not lemma.endswith("ll"):
            forms[lemma + "led"] = lemma  # "cancelled", "travelled"
    return forms


_PAST: dict[str, str] = {}
_LEMMAS: frozenset[str] = frozenset()


def _tables() -> None:
    global _PAST, _LEMMAS
    if not _PAST:
        _PAST = _past_forms()
        _LEMMAS = frozenset({lemma for lemma, _p, _pp in _IRREGULAR} | _REGULAR)


#: Where an event's object stops: a time or place phrase, a clause break.
_OBJECT_STOP = frozenset("on at in after before during since until for with by from because but and so then when while".split())
_NEGATORS = frozenset("not no never didn't don't doesn't won't can't cannot isn't wasn't aren't weren't haven't hasn't hadn't nothing".split())
_HEDGES = lazy_compile(r"\b(maybe|might|perhaps|possibly|probably|could|would)\b", re.I)
_IF = lazy_compile(r"^\s*(?:if|unless|in case)\b|\b(?:if|unless)\b", re.I)

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "a dozen": 12, "half a dozen": 6,
}
_NUMBER = r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|" + "|".join(sorted(_NUMBER_WORDS, key=len, reverse=True)) + r")"
#: Time units: a number with one of these is a duration, in seconds.
_TIME_UNITS = {
    "second": 1, "seconds": 1, "secs": 1, "sec": 1, "minute": 60, "minutes": 60, "mins": 60, "min": 60,
    "hour": 3600, "hours": 3600, "hrs": 3600, "hr": 3600, "day": 86400, "days": 86400, "week": 604800,
    "weeks": 604800, "month": 2629800, "months": 2629800, "year": 31557600, "years": 31557600,
}
_UNITS = frozenset(
    """km kms kilometres kilometers kilometre kilometer m metres meters mile miles mi kg kgs kilos g grams lb lbs pounds
    oz cm mm l litres liters ml percent % sets reps laps times steps pages words people notes loaves cups tbsp tsp
    degrees grit bpm kcal calories items tickets users testers""".split()
)
#: Plural-looking words that are not things counted: "10 miles across", "2 less".
_NOT_THINGS = frozenset("less always perhaps towards afterwards sometimes besides yours ours theirs hers its".split())
_MEASURES = frozenset(u.lower() for u in recognise_units.UNITS)
_QUANTITY = lazy_compile(r"\b" + _NUMBER + r"\s*(%|[a-z]+)\b(?:\s+of\s+([a-z]+(?:\s[a-z]+)?))?", re.I)
_DECISION = lazy_compile(r"\b(decided|going with|chose|settled on|opted for)\b\s*(?:to\s+go\s+with\s+|to\s+|on\s+)?", re.I)
_PREFERENCE = lazy_compile(
    r"\b(?:(?:i|we)\s+(?:really\s+|also\s+)?(?P<neg>don't |do not |didn't |never )?(?P<verb>like|love|prefer|hate|dislike|enjoy|adore|can't stand|cannot stand)"
    r"|(?:my\s+)?(?P<fav>favou?rite)\b)\s*",
    re.I,
)
_NEGATIVE_PREFERENCE = frozenset({"hate", "dislike", "can't stand", "cannot stand"})
_PLAN = lazy_compile(r"\b(plan(?:ning)? to|want to|wants to|going to|need to|needs to|should|have to|has to)\s+(?!be\b)", re.I)
_LINK = lazy_compile(r"https?://[^\s)>\]]+|\[\[[^\]\n]{1,120}\]\]")
_QUOTED = lazy_compile(r"[\"“]([^\"“”\n]{2,400})[\"”]")
_SAID = lazy_compile(r"\b([A-Z][a-z]+|[Ss]he|[Hh]e|[Tt]hey)\s+(?:said|says|wrote|writes|told me|replied|asked)\s*[:,]?\s*", re.U)
_ACCORDING = lazy_compile(r"\baccording to\s+([A-Z][\w ]{0,40}?),\s*", re.U)
_CAPITAL = lazy_compile(r"\b[A-Z][a-z]+(?:[ -][A-Z][a-z]+)*\b")
_SPEECH_AFTER = lazy_compile(r"^\s*(?:and I\b|and me\b|said\b|says\b|wrote\b|told\b|asked\b|replied\b)")
_PERSON_BEFORE = lazy_compile(r"\b(?:met|with|told|asked|called|emailed|texted|saw|and|from|to|by)\s+$", re.I)
_PLACE_BEFORE = lazy_compile(r"\b(?:at|in|near|to)\s+(?:the\s+)?$", re.I)
_PLACE_AFTER = lazy_compile(r"^\s+(?:cafe|café|course|park|street|road|lane|beach|station|gym|office|hotel|airport|centre|center|hall|bar|pub|market|lake|river)\b", re.I)
_ORG_AFTER = lazy_compile(r"^\s+(?:Inc|Ltd|LLC|Corp|Co|Group|Labs|University|Bank)\b")
_NOT_NAMES = frozenset(
    """I I'm I've I'll I'd Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April May
    June July August September October November December Today Tomorrow Yesterday The A An This That These Those It
    My Our Your We He She They Then Also But And So Next Last Ok Okay Yes No""".split()
)
_HEADING = lazy_compile(r"^\s{0,3}#{1,6}\s+")
_ITEM = lazy_compile(r"^(\s*(?:[-*+]|\d{1,3}[.)])\s+)(\[([ xX])\]\s+)?")
_SPLIT = lazy_compile(r"([.!?][\"”’)]?)\s+(?=[\"“‘(]?[A-Z0-9])")
_PICTURES_HEAD = "[Pictures in this note"
_JOKE = lazy_compile(r"\bjoke\b|\bpunchline\b", re.I)


# --- reading -----------------------------------------------------------------------


def _written(note: dict) -> date | None:
    raw = str(note.get("created_at") or note.get("written_on") or "")
    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            return None
    return None


def _anchor(note: dict) -> date | None:
    """The day a bare "25 October" is read against: the later of the day the
    note was written and the day it was last edited, since a running log
    gains its lines over weeks and a line is no older than the edit that
    added it (round 4, E17: "a year ago" for a date two weeks off)."""
    written = _written(note)
    edited = str(note.get("entry_edited_at") or note.get("edited_at") or note.get("updated_at") or "")
    try:
        later = date.fromisoformat(edited[:10]) if re.match(r"\d{4}-\d{2}-\d{2}", edited) else _edited_in_words(note)
    except ValueError:
        later = None
    return max(written, later) if written and later else (written or later)


_EDITED_WORDS = re.compile(r", edited \w+ (\d{1,2}) (\w+) (\d{4})")


def _edited_in_words(note: dict) -> date | None:
    """The edit day the chat route states in the note's `written` words ("..., edited Monday 2 November 2026,
    10:00"), the only form a retrieved note carries it in (L106 E17)."""
    found = _EDITED_WORDS.search(str(note.get("written") or ""))
    months = [m.lower() for m in calendar.month_name]
    if not found or found.group(2).lower() not in months:
        return None
    return date(int(found.group(3)), months.index(found.group(2).lower()), int(found.group(1)))


def _line_units(content: str, line: str, start: int, body_end: int) -> list[tuple[int, int, str, bool | None]]:
    """The claims of one body line: a list or check item is one unit, prose is
    split into sentences."""
    item = _ITEM.match(line)
    if item:
        box = item.group(3)
        kind = "check_item" if box is not None else "list_item"
        return [(start + item.end(), body_end, kind, None if box is None else box.lower() == "x")]
    out: list[tuple[int, int, str, bool | None]] = []
    lead = len(line) - len(line.lstrip(" >"))
    cursor = start + lead
    for match in _SPLIT.finditer(content, cursor, body_end):
        out.append((cursor, match.end(1), "prose", None))
        cursor = match.end()
    if cursor < body_end:
        out.append((cursor, body_end, "prose", None))
    return out


def _units(content: str) -> list[tuple[int, int, str, bool | None]]:
    """(start, end, kind, done) for every sentence and list line of the body:
    the heading line is the note's name, not a claim; code is skipped; a
    picture caption is content (decision 37)."""
    out: list[tuple[int, int, str, bool | None]] = []
    offset = 0
    in_fence = False
    first = True
    for line in content.splitlines(keepends=True):
        start, offset = offset, offset + len(line)
        stripped = line.strip()
        body_end = start + len(line.rstrip("\r\n"))
        if first and _HEADING.match(line):
            first = False
            continue
        first = first and not stripped
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped or _HEADING.match(line) or stripped.startswith((_PICTURES_HEAD, "|", "![")):
            continue
        out.extend(_line_units(content, line, start, body_end))
    return [(s, e, k, d) for s, e, k, d in out if content[s:e].strip()]


def _quoted_spans(sentence: str) -> list[tuple[int, int, str]]:
    """(start, end, speaker) of every stretch in someone else's words: inside
    quotation marks, or after "Sam said:" / "according to X," to the end."""
    spans: list[tuple[int, int, str]] = []
    said = _SAID.search(sentence) or _ACCORDING.search(sentence)
    for match in _QUOTED.finditer(sentence):
        speaker = said.group(1) if said and said.end() <= match.start() + 1 else ""
        spans.append((match.start(1), match.end(1), speaker))
    if said and not spans:
        rest = sentence[said.end():].rstrip()
        if len(rest.split()) >= 2:
            spans.append((said.end(), len(sentence.rstrip()), said.group(1)))
    return spans


def _inside(spans: list[tuple[int, int, str]], start: int, end: int) -> bool:
    return any(s <= start and end <= e for s, e, _ in spans)


def _mode(sentence: str, local_start: int, quoted: list) -> str:
    """The assertion mode at a point of a sentence."""
    if _inside(quoted, local_start, local_start + 1):
        return "quoted"
    if sentence.rstrip().endswith("?"):
        return "question"
    before = sentence[:local_start].lower().split()[-3:]
    if any(w.strip(",.") in _NEGATORS for w in before) or re.search(r"n't\s*$", sentence[:local_start]):
        return "negated"
    if _IF.search(sentence):
        return "conditional"
    if _HEDGES.search(sentence):
        return "hypothetical"
    return "asserted"


def _object(sentence: str, start: int) -> tuple[int, str]:
    """An event's object: the words after the verb up to a time or place
    phrase or a clause break; a bare "to the gym" after a motion verb when
    nothing else follows."""
    rest = sentence[start:]
    words = re.finditer(r"[A-Za-z0-9'%$£€.-]+|[,;:.!?]", rest)
    end = 0
    taken = 0
    for word in words:
        token = word.group(0)
        if token in ",;:.!?":
            break
        bare = token.rstrip(".")
        if bare.lower() in _OBJECT_STOP and (taken or bare.lower() != "to"):
            break
        end = word.start() + len(bare)
        taken += 1
        if bare != token or taken >= 8:
            break
    obj = rest[:end].strip()
    return start, obj


def _date_value(phrase: str, anchor: date | None, tense: str | None) -> tuple | None:
    if anchor is None:
        return None
    return when_words.span(phrase, anchor, tense)


_MONTH_WORD = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"


def _sentence_tense(sentence: str) -> str | None:
    _tables()
    if _AUX_FUTURE.search(sentence) or _PROGRESSIVE_FUTURE.search(sentence) or re.search(r"\b(?:plan|want|need)s? to\b", sentence, re.I) or recognise_questions.says_ahead(sentence):
        return "future"
    if re.search(r"\bfor\s+(?:the\s+)?\d{1,2}(?:st|nd|rd|th)\b", sentence, re.I):
        return "future"
    #: "Check-up booked for 21 October": what something is booked for is
    #: ahead of the booking, though "booked" is past (ledger row 441).
    if re.search(rf"\b(?:(?:booked|scheduled|planned|set|arranged)\s+for|(?:moved|pushed)\s+(?:back\s+)?to|due(?:\s+on|\s+by)?)\s+(?:(?:the\s+)?\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTH_WORD}|{_MONTH_WORD}\s+\d{{1,2}})\b", sentence, re.I):
        return "future"
    if any(w.lower() in _PAST for w in re.findall(r"[A-Za-z']+", sentence)):
        return "past"
    return None


def _after_object(sentence: str, pos: int, obj: str) -> int:
    """Where a verb's object ends: past the spaces after `pos` and the object."""
    tail = sentence[pos:]
    return pos + (len(tail) - len(tail.lstrip()) + len(obj) if obj else 0)


class _SentenceReader:
    """The facts of one sentence. The order of the steps in `read` is the order
    the facts are collected in, which the final stable sort keeps for ties."""

    #: The day dates are read against, when it is not the day written.
    anchor: date | None = None

    def __init__(self, content: str, source: int, written: date | None, tags: list[str], unit: tuple) -> None:
        self.content, self.source, self.written, self.tags = content, source, written, tags
        self.u_start, u_end, self.u_kind, self.done = unit
        self.sentence = content[self.u_start:u_end]
        self.quoted = _quoted_spans(self.sentence)
        self.tense = _sentence_tense(self.sentence)
        self.local: list[Fact] = []
        #: Spans already read as a date, sum or length: not quantities.
        self.taken: list[tuple[int, int]] = []
        self.dated: list[tuple] = []

    def add(self, kind: str, s: int, e: int, attrs: dict | None = None, mode: str | None = None, confidence: float = 0.8) -> None:
        text = self.sentence[s:e]
        stripped = text.strip() if kind == "quote" else text.strip().rstrip(".,;:")
        if not stripped:
            return
        s += len(text) - len(text.lstrip())
        e = s + len(stripped)
        self.local.append(Fact(kind, self.source, self.u_start + s, self.u_start + e, self.content[self.u_start + s:self.u_start + e],
                               attrs or {}, mode or _mode(self.sentence, s, self.quoted), None, False, confidence))

    def structure(self, index: int) -> None:
        if self.u_kind == "check_item":
            self.add("check_item", 0, len(self.sentence), {"done": bool(self.done), "index": index}, "asserted", 1.0)
        elif self.u_kind == "list_item":
            self.add("list_item", 0, len(self.sentence), {"index": index}, "asserted", 1.0)
        for s, e, speaker in self.quoted:
            self.add("quote", s, e, {"speaker": speaker}, "quoted", 0.9)

    def dates(self) -> None:
        # dates first: their spans are not quantities
        found = when_words.find(self.sentence)
        for i, (s, e, phrase) in enumerate(found):
            after = found[i + 1] if i + 1 < len(found) else None
            if after and after[0] - e in (1, 2) and phrase.lower().removeprefix("on ") in _WEEKDAY_WORDS and after[2][:1].isdigit() and self.sentence[e:after[0]] in (" ", ", "):
                continue  # "Monday 16 November": the date names the day, the weekday beside it is no second one (bt-compcomp item 1)
            resolved = _date_value(phrase, self.anchor or self.written, self.tense)
            self.add("date", s, e, {"phrase": phrase, "resolved": resolved[0].isoformat() if resolved else None,
                                    "through": resolved[1].isoformat() if resolved else None,
                                    "grain": resolved[2] if resolved else "unknown"}, confidence=0.9 if resolved else 0.5)
            self.taken.append((s, e))
            if resolved:
                self.dated.append(resolved)

    def money(self, spans: list) -> None:
        #: Money is read by `ai/recognise.py` (CHAT_PLAN decision 46). A sum
        #: that also reads as a weight ("lost 5 pounds") is left to the
        #: quantities below, as it always was here.
        for found in spans:
            if found.kind != "money" or found.rank or any(o.rank and (o.start, o.end) == (found.start, found.end) for o in spans):
                continue
            value, currency = found.value
            self.add("money", found.start, found.end, {"value": int(value) if value == int(value) else value, "currency": currency}, confidence=0.95)
            self.taken.append((found.start, found.end))

    def durations(self, spans: list) -> None:
        for found in spans:
            if found.kind != "duration" or found.rank or any(st <= found.start < en for st, en in self.taken):
                continue
            #: "three times a week" is how often, not how long.
            if re.search(r"\b(?:times|once|twice|per|every)\s+$", self.sentence[: found.start], re.I):
                continue
            unit = found.text.lower().split()[-1] if " " in found.text else found.text.lower().lstrip("0123456789.,")
            self.add("duration", found.start, found.end, {"seconds": int(found.value.total_seconds()), "unit": unit}, confidence=0.9)
            self.taken.append((found.start, found.end))

    @staticmethod
    def _counted_unit(unit: str) -> bool:
        """Whether a word after a number is a unit worth keeping."""
        plural = unit.endswith("s") and len(unit) > 3 and not unit.endswith(("ss", "us", "is")) and unit not in _NOT_THINGS
        if unit not in _UNITS and not plural:
            return False
        return unit not in ("am", "pm", "st", "nd", "rd", "th") and unit not in _TIME_UNITS

    def quantities(self) -> None:
        for match in _QUANTITY.finditer(self.sentence):
            if any(s <= match.start() < e or s < match.end() <= e for s, e in self.taken):
                continue
            unit = match.group(2).lower()
            if not self._counted_unit(unit):
                continue
            raw = match.group(1).lower()
            value = _NUMBER_WORDS.get(raw)
            if value is None:
                number = float(raw.replace(",", ""))
                value = int(number) if number == int(number) else number
            end = match.end(2)
            attrs = {"value": value, "unit": unit, "of": None}
            if match.group(3) and not re.fullmatch(r"\d.*", match.group(3)):
                attrs["of"] = match.group(3)
                end = match.end(3)
            #: A measure is a unit `recognise` knows ("80 kg"); anything else a
            #: number counts is a count of things ("5 sets", "three times").
            measured = unit in _MEASURES or unit == "%"
            self.add("quantity" if measured else "count", match.start(), end, attrs, confidence=0.85)
            self.taken.append((match.start(), end))

    def _bare_past_verb(self, match: re.Match, low: str) -> bool:
        """A past form that is really a bare verb or a negation ("did not")."""
        if low == "did" and re.match(r"\s+(?:not\b|n't)", self.sentence[match.end():]):
            return True
        return low in ("left", "set", "put", "cut", "read", "hit", "let", "quit", "shut", "lit") and not re.search(
            r"\b(?:I|we|you|he|she|they)\s+$", self.sentence[:match.start()], re.I
        )

    def past_events(self) -> None:
        # events: a past form of a known verb, or a future auxiliary
        for match in re.finditer(r"[A-Za-z']+", self.sentence):
            word = match.group(0)
            low = word.lower()
            lemma = _PAST.get(low)
            if lemma is None or self._bare_past_verb(match, low):
                continue
            _obj_start, obj = _object(self.sentence, match.end())
            end = _after_object(self.sentence, match.end(), obj)
            if _inside(self.quoted, match.start(), match.end()):
                continue
            self.add("event", match.start(), end, {"verb": word, "lemma": lemma, "object": obj, "tense": "past"}, confidence=0.8)

    def _event_from(self, match: re.Match, lemma: str, tense: str, mode: str | None, confidence: float) -> None:
        if lemma not in _LEMMAS or _inside(self.quoted, match.start(), match.end()):
            return
        _s, obj = _object(self.sentence, match.end())
        end = _after_object(self.sentence, match.end(), obj)
        self.add("event", match.start(), end, {"verb": match.group(0), "lemma": lemma, "object": obj, "tense": tense}, mode=mode, confidence=confidence)

    def negated_and_future_events(self) -> None:
        for match in _DID_NOT.finditer(self.sentence):
            self._event_from(match, match.group(1).lower(), "past", "negated", 0.7)
        for match in list(_AUX_FUTURE.finditer(self.sentence)) + list(_PROGRESSIVE_FUTURE.finditer(self.sentence)):
            verb = match.group(1).lower()
            self._event_from(match, "go" if verb == "going" else verb, "future", None, 0.7)

    def decisions(self) -> None:
        for match in _DECISION.finditer(self.sentence):
            if _inside(self.quoted, match.start(), match.end()):
                continue
            _s, choice = _object(self.sentence, match.end())
            tail = self.sentence[match.end():]
            self.add("decision", match.start(), match.end() + len(tail) - len(tail.lstrip()) + len(choice), {"choice": choice}, confidence=0.85)

    def preferences(self) -> None:
        for match in _PREFERENCE.finditer(self.sentence):
            if _inside(self.quoted, match.start(), match.end()):
                continue
            verb = (match.group("verb") or match.group("fav") or "").lower()
            positive = verb not in _NEGATIVE_PREFERENCE
            if match.group("neg"):
                positive = not positive
            tail = self.sentence[match.end():]
            obj = re.split(r"[.,;!?]", tail, maxsplit=1)[0].strip()
            self.add("preference", match.start(), match.end() + len(tail) - len(tail.lstrip()) + len(obj),
                     {"polarity": 1 if positive else -1, "object": obj, "verb": verb},
                     mode="negated" if match.group("neg") else None, confidence=0.85)

    def plans(self) -> None:
        for match in _PLAN.finditer(self.sentence):
            if _inside(self.quoted, match.start(), match.end()):
                continue
            tail = self.sentence[match.end():]
            obj = re.split(r"[.;!?]|,\s(?:but|and then)\b", tail, maxsplit=1)[0].strip()
            if obj:
                self.add("plan", match.start(), match.end() + len(obj), {"object": obj, "cue": match.group(1).lower()}, confidence=0.75)

    def question(self, index: int, units: list, joke: bool) -> None:
        sentence = self.sentence
        if not (self.u_kind == "prose" and sentence.rstrip().endswith("?") and not _inside(self.quoted, len(sentence.rstrip()) - 1, len(sentence.rstrip()))):
            return
        nxt = self.content[units[index + 1][0]:units[index + 1][1]] if index + 1 < len(units) else ""
        if not (joke and nxt and not nxt.rstrip().endswith("?")):
            self.add("question", 0, len(sentence), {}, "question", 0.95)

    def links(self) -> None:
        for match in _LINK.finditer(self.sentence):
            self.add("link", match.start(), match.end(), {"target": match.group(0).strip("[]")}, "asserted", 1.0)

    def _entity_of(self, match: re.Match) -> tuple | None:
        """(start, name, kind) of a capitalised run that names something, or None."""
        sentence, name = self.sentence, match.group(0)
        if name.split()[0] in _NOT_NAMES or len(name) < 2:
            return None
        start = match.start()
        at_start = not sentence[:start].strip() or re.search(r"[.!?:\"“]\s*$", sentence[:start])
        after = sentence[match.end():]
        if at_start and " " in name and not _SPEECH_AFTER.match(after):
            #: "Ship Harbor": the sentence's own capital is not a name, the
            #: rest of the run may be.
            head, name = name.split(" ", 1)
            start += len(head) + 1
            at_start = False
            if name.split()[0] in _NOT_NAMES:
                return None
        before = sentence[:start]
        if at_start and not _SPEECH_AFTER.match(after) and name.lower() not in {t.lower() for t in self.tags}:
            return None
        return start, name, self._entity_kind(after, before)

    @staticmethod
    def _entity_kind(after: str, before: str) -> str:
        if _PLACE_AFTER.match(after) or (_PLACE_BEFORE.search(before) and not _PERSON_BEFORE.search(before)):
            return "place"
        if _ORG_AFTER.match(after):
            return "org"
        if _SPEECH_AFTER.match(after) or _PERSON_BEFORE.search(before):
            return "person"
        return "unknown"

    def entities(self) -> None:
        for match in _CAPITAL.finditer(self.sentence):
            found = self._entity_of(match)
            if found is not None:
                start, name, kind = found
                self.add("entity", start, match.end(), {"type": kind, "name": name}, confidence=0.7 if kind == "unknown" else 0.8)

    def read(self, index: int, units: list, joke: bool) -> list[Fact]:
        self.structure(index)
        self.dates()
        spans = recognise.recognise(self.sentence, now=datetime.combine(self.written or clock.today(), time(12)))
        self.money(spans)
        self.durations(spans)
        self.quantities()
        self.past_events()
        self.negated_and_future_events()
        self.decisions()
        self.preferences()
        self.plans()
        self.question(index, units, joke)
        self.links()
        self.entities()
        topics = _topics(self.sentence)
        if topics:
            self.add("topic", 0, len(self.sentence), {"labels": topics}, "asserted", 0.6)
        when = self.dated[0] if self.dated else ((self.written, self.written, "day") if self.written else None)
        inherited = not self.dated and self.written is not None
        return [Fact(f.kind, f.source_id, f.start, f.end, f.text, f.attrs, f.mode, when, inherited, f.confidence) for f in self.local]


def _note_facts(note: dict) -> list[Fact]:
    _tables()
    content = str(note.get("content") or "")
    source = int(note.get("id") or 0)
    written = _written(note)
    tags = [str(t) for t in note.get("tags") or []]
    joke = bool(_JOKE.search(content))
    units = _units(content)
    facts: list[Fact] = []
    anchor = _anchor(note)
    for index, unit in enumerate(units):
        reader = _SentenceReader(content, source, written, tags, unit)
        reader.anchor = anchor
        facts += reader.read(index, units, joke)
    facts.sort(key=lambda f: (f.start, KINDS.index(f.kind), f.end))
    return facts


def _topics(sentence: str) -> list[str]:
    """The taxonomy map's domains a sentence's words belong to, once each."""
    from tessellate.ai import taxonomy

    return list(dict.fromkeys(taxonomy.extract_categories(sentence)))


# --- the cache ---------------------------------------------------------------------

#: Notes read, by revision; a notebook is a few thousand notes and a fact list
#: a few hundred bytes, so the bound is about memory nobody notices.
CACHE_SIZE = 4096
_CACHE: OrderedDict[tuple, list[Fact]] = OrderedDict()


def _revision(note: dict) -> tuple:
    content = str(note.get("content") or "")
    edited = note.get("entry_edited_at") or note.get("edited_at") or note.get("updated_at") or ""
    return (note.get("id"), str(edited), str(note.get("created_at") or ""), hashlib.sha1(content.encode()).hexdigest(),
            tuple(note.get("tags") or ()))


def facts(note: dict) -> list[Fact]:
    """The note's facts, in text order, built once per revision."""
    key = _revision(note)
    cached = _CACHE.get(key)
    if cached is not None:
        _CACHE.move_to_end(key)
        return cached
    built = _note_facts(note)
    _CACHE[key] = built
    if len(_CACHE) > CACHE_SIZE:
        _CACHE.popitem(last=False)
    return built


def of_kind(note: dict, kind: str) -> list[Fact]:
    return [f for f in facts(note) if f.kind == kind]
