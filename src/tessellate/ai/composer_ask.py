"""Reading the question: its shape, its subject words, the stems and synonyms
they match by, the sides a comparison names, and the person's clock.

Moved whole from `composer.py` (audit AR3, gods-1101): the code is unchanged,
and `composer` re-exports every name here that anything reads, so
`composer.classify` still works. Imports run one way, down
the layer list in `composer.py`'s docstring, never back to `composer`.
"""

from __future__ import annotations

import contextvars
import functools
import re
import unicodedata

from tessellate.core.lazyre import lazy_compile
from datetime import date, datetime

from tessellate.ai import common_words, composer_sides, composer_tables, question_noise, recognise as rec, variants
from tessellate.search import query as query_understanding


def user_now() -> datetime:
    """Now on the person's own clock (their saved timezone), as a naive
    datetime: the server's `date.today()` names the wrong day for someone far
    from it (audit 1028 K22). The settings as loaded, never `get_config()`,
    which would start the app in a unit test; with none, the server's zone.
    """
    from tessellate.core import config

    return config.loaded_user_now().replace(tzinfo=None)


def user_today() -> date:
    return user_now().date()


_MONTHS = "January February March April May June July August September October November December".split()


def month_name(month: int) -> str:
    """The month's name for its number, 1 to 12."""
    return _MONTHS[month - 1]


# --- the question -------------------------------------------------------------

#: The shapes a question comes in, read from its wording alone, first match
#: wins. Ordered: "how many" is a count before it is a "how", "what is the
#: latest" is a status before it is a "what", and a comparison can open with
#: any word at all.
_SHAPE_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("compare", lazy_compile(r"\b(compare|versus|vs\.?|differences? between)\b", re.I)),
    ("count", lazy_compile(r"^\s*how (many|much|often|long)\b|\bnumber of\b", re.I)),
    ("when", lazy_compile(r"^\s*(when|what (date|day|time|month|year)|which (date|day|month))\b", re.I)),
    ("who", lazy_compile(r"^\s*(who|whom|whose)\b", re.I)),
    (
        "status",
        lazy_compile(
            r"\b(latest|status|progress|update on|updates on|newest|most recent|so far|"
            r"where (am i|are we|is it|are things) (with|on)|any (news|word) (on|about)|"
            r"how far along|what happened (with|to)|how (is|are) .{2,60}? (going|coming along|getting on))\b",
            re.I,
        ),
    ),
    ("where", lazy_compile(r"^\s*(where|whereabouts|what (address|place|street|room))\b", re.I)),
    (
        "explain",
        lazy_compile(r"^\s*(why|how come|explain|what (made|makes|caused|causes)|how (do|does|did|can|could|should|to|is|are|was|were|would))\b", re.I),
    ),
    #: "What's in the soup", "what do I need for camping": what a note holds (Z46).
    ("list", lazy_compile(r"^\s*(list|which|name)\b|^\s*what are (the|my|all)\b|^\s*what(?:'s| is| goes| go)? in(?:to)?\b(?! (?:my|the|your) (?:notes?|journal|diary|library)\b)"
                        r"|^\s*what do (?:i|you) need (?:for|to make)\b", re.I)),
    ("yesno", lazy_compile(r"^\s*(is|are|do|does|did|can|could|was|were|has|have|had|should|will|would|am)\b", re.I)),
)


SHAPES = ("what", *(name for name, _ in _SHAPE_RULES), "recent")


#: Words that ask rather than name: dropped from the subject, so "what is the
#: latest on the sync rewrite" is scored on "sync rewrite" alone. The verbs a
#: question wraps its subject in ("feel", "say") are here too, so the closing
#: line never reports "feel" as a word no note mentions.
_ASKING_WORDS = frozenset(
    """about all any anything everything define defines definition meaning compare comparison difference differences
    between versus vs latest status progress update updates newest recent
    recently most current currently tell say says said know think thought
    feel felt get got go went make made want need like much many number
    often long ever still actually really there here things thing note notes
    wrote written write mention mentions mentioning mentioned explain should
    could would way am i me my mine whose whom anyone someone near after
    before during without within over under around across through since
    until also again just only some other one ones any every each main
    remind idea forgot forget remember wonder wondering deal hows whats
    wheres whens whos whys going happen happened happening news anything
    next last first per something stuff info information details please thanks thank check
    find look show help kind sort bit quick quickly briefly short detail
    detailed full whole remind possible maybe okay ok hey hi
    whereabouts address place put decide decided conclude concluded doing
    possibly exactly precisely definitely basically honestly kindly truly certainly probably roughly approximately because""".split()
) | composer_tables.EXTRA_ASKING_WORDS | frozenset(
    #: Time words say when, never what (engine probe P6: "what did I write
    #: last week" was told "No note found brings up last"). The window they
    #: name is read by `when.window`; the subject is what is left.
    """last ago today yesterday tonight lately earlier summarise summarize
    summary done pattern patterns habit habits trend trends
    else another rest total version gist tldr""".split()
)


#: A time phrase names a window, not a subject: "last week", "3 days ago",
#: "this month" come off whole before the subject is read, so "week 4"
#: stays a subject and "last week" is not one.

#: The wrappers a casual or indirect question comes in, taken off before its
#: shape and its subject are read (INBOX 741, the owner: "better to
#: understand"): "can you remind me when the dentist is" asks "when the
#: dentist is"; "any idea if the deposit is paid" asks "is the deposit paid".
#: Each is a fixed, tested pattern; what is left is the person's own words.
_WRAPPERS = (
    lazy_compile(r"^(?:hey|hi|hello|ok|okay|so|um+|uh+|right|quick question|question|hmm+)\b[,.!:]?\s+", re.I),
    lazy_compile(r"^(?:please\s+)?(?:can|could|would|will) you\s+(?:please\s+)?(?:tell me|remind me(?: of)?|let me know|check|find(?: out)?|look up|show me|say|help me (?:find|remember))\s+", re.I),
    lazy_compile(r"^(?:(?:do|does) )?(?:you|anyone) (?:know|remember|recall)\s+", re.I),
    lazy_compile(
        r"^(?:i do not know|i don't know|i dunno|to be honest|honestly|not going to lie|by the way|"
        r"ty|thanks|thank you|thx|yo|lol|haha|ok|okay|oh|ah|so)\b[,.!:]?\s+",
        re.I,
    ),
    lazy_compile(r"^(?:any idea|no idea|not sure)\s+", re.I),
    lazy_compile(
        r"^i(?:'m| am)? (?:forgot|forget|can't remember|cannot remember|don't remember|do not remember|wonder|was wondering|"
        r"need to know|want to know|'d like to know|would like to know|need|want|have to check|can't recall)\s+",
        re.I,
    ),
    lazy_compile(r"^(?:remind me|tell me|show me|let me know)\s+(?=(?:what|when|who|where|why|how|which|if|whether)\b)", re.I),
    lazy_compile(r"^(?:remind me)\s+(?:of|about)\s+", re.I),
    lazy_compile(r"^please\s+", re.I),
    lazy_compile(r"^(?:and|but|also|plus)\s+(?=(?:what|when|where|who|why|how|which|is|are|do|does|did|can|should)\b)", re.I),
    lazy_compile(r"^(?:right|alright|cool|nice|great|got it|k|kk|sure|fair enough|makes sense)\b[,.!:]?\s+(?=\w)", re.I),
    lazy_compile(r"^(?:in short|in brief|briefly|quickly|quick one|tl;?dr|in a word|in detail)\b[,:]?\s+", re.I),
    *(lazy_compile(pattern, re.I) for pattern in composer_tables.EXTRA_WRAPPERS),
)


#: "dentist when?", "spare key where": the question word typed last.
_LAST_WORD = lazy_compile(r"^(?P<rest>[^?]*?\S)[,\s]+(?P<q>when|where|who|why|how many|how much|how long|how often)(?P<p>\s*\?*)$", re.I)


_ASKS_FIRST = lazy_compile(r"^(?:what|when|where|who|whom|whose|why|how|which|is|are|do|does|did|can|could|should|will|would|was|were|has|have|had|am|if|whether|compare|list|name|tell|explain)\b", re.I)


_TRAILERS = lazy_compile(
    #: Starts after a word, so a run of blanks is tried once, not from each blank (CodeQL).
    r"(?<![,\s])(?:[,\s]+(?:please|thanks|thank you|again|for me|real quick|quickly|by any chance|"
    + "|".join(re.escape(t) for t in composer_tables.EXTRA_TRAILERS)
    + r"))+\s*([?.!]*)\s*$",
    re.I,
)


#: "whats", "how's" and the rest, spelled out so the shape rules read them.
_CONTRACTIONS = (
    (lazy_compile(r"^(what|how|where|when|who|why)(?:'s|s)\b", re.I), r"\1 is"),
    (lazy_compile(r"^(what|how|where|when|who|why)(?:'re)\b", re.I), r"\1 are"),
    *((lazy_compile(pattern, re.I), spelled) for pattern, spelled in composer_tables.EXTRA_CONTRACTIONS),
)


#: "if the deposit is paid", left after "any idea", asks yes or no.
_IF = lazy_compile(r"^(?:if|whether)\s+", re.I)


#: "what about X", "anything on X", "is there anything about X", "do I have
#: notes on X": everything on a subject, the broad answer.
_ANYTHING_ON = lazy_compile(
    r"^(?:(?:is there )?anything (?:about|on)|do i have (?:any )?(?:notes? )?(?:about|on)|have i (?:written|got|noted) (?:anything |down )?(?:about|on)|"
    r"what(?: is|'s)? the deal with|what is going on with|what's going on with|what(?:'s|s| is) new (?:with|on|about))\b",
    re.I,
)


def _still_recent(question: str) -> bool:
    """Whether a retrieval that fell back to the newest notes still answers
    `question`: it does when there is no subject, or when the whole question is
    a recency ask ("What have I saved recently?": "saved" is a verb there)."""
    from tessellate.ai.note_recency import is_recency_ask

    return not subject_terms(question) or is_recency_ask(question)


_UNNAMED_ASK = lazy_compile(r"^(?:who|where|how (?:much|many)|what (?:should|do you think|would you))\b")


def _guessing_recent(question: str) -> bool:
    """A fallback to the newest notes for a who, where or how-much that names
    nothing to look for: the answer says it is a fallback (audit 1030 Z34)."""
    from tessellate.ai.note_recency import is_recency_ask

    return bool(_UNNAMED_ASK.match(" ".join(question.lower().split()))) and not is_recency_ask(question) and rec.without_windows(question) == question


def _respell(text: str) -> str:
    """Slang and text-speak spelled out, misspelt asking words put right,
    run-together words split (`question_noise`, INBOX 741: "does it cover
    any and ALL typos ... all slang like pls, ty, lol, u, r, wym")."""
    return question_noise.repair(text, known=_KNOWN.get())


#: "define X" and "the meaning of X" ask what "what is X" asks, so they take
#: its answer (audit 1029 C18). The text is single-spaced by here, so the
#: pattern reads one literal space: linear on any input.
_DEFINE = lazy_compile(r"^(?:define|(?:the )?(?:definition|meaning) of) (.+)$", re.I)


def what_is(text: str) -> str:
    """"define X" read as "what is X"; any other text as it came."""
    return _DEFINE.sub(r"what is \1", " ".join(text.split()))


def rephrase(question: str) -> str:
    """The question with its casual wrapper off: "hey, can you remind me
    when the dentist is please?" reads as "when the dentist is?". Text-speak
    is spelled out and a misspelt question word put right first ("whn is
    the launch" reads "when is the launch"). Never adds a word of the
    subject the person did not write."""
    text = _respell(" ".join((question or "").split())).lstrip(".,;:!?-*~ ")
    for _ in range(4):
        before = text
        for pattern in _WRAPPERS:
            text = pattern.sub("", text)
        text = _TRAILERS.sub(r"\1", text)
        for pattern, spelled in _CONTRACTIONS:
            text = pattern.sub(spelled, text)
        if text == before:
            break
    text = what_is(text)
    last = _LAST_WORD.match(text)
    if last and not _ASKS_FIRST.match(text):
        text = f"{last.group('q')} {last.group('rest')}{last.group('p')}"
    return text or _respell(" ".join((question or "").split()))


def classify(question: str, embed=None) -> str:  # noqa: ANN001
    """The question's shape: one of `SHAPES`, "what" when nothing else fits.
    Read after its casual wrapper is off (`rephrase`); a question no rule
    reads and that opens with no asking word ("dentist date?", "reason the
    list was slow") is matched by meaning to example questions of each kind
    (`question_noise.guess_kind`, by `embed` when given)."""
    text = rephrase(question)
    if _IF.match(text):
        return "yesno"
    if _COMPARE_EXTRA.search(text) and compare_sides(text):
        return "compare"
    #: "is there anything about the boiler", "how many notes mention
    #: sourdough": everything on a subject, however they open.
    if _ANYTHING_ON.match(text) or re.match(r"^how many (?:of my )?notes\b", text, re.I):
        return "what"
    for name, pattern in _SHAPE_RULES:
        if pattern.search(text):
            return name
    if not _ASKS_FIRST.match(text):
        guessed = question_noise.guess_kind(text, embed)
        if guessed:
            return guessed
    return "what"


#: Words whose final "s" is not a plural: "news" is not "new", "lens" not
#: "len" (the stemmer's own rule, below; found by the 2026-10-10 triage).
_NOT_PLURAL = frozenset("atlas canvas news lens gas yes always perhaps series species means mathematics physics".split())


_VOWELS = "aeiou"


def _one_syllable_cvc(w: str) -> bool:
    """A stem of one vowel group ending consonant, vowel, consonant ("hir",
    "mak", "writ"): the shape that lost a silent "e" to its suffix (Porter's
    *o rule, held to one syllable so "open" never becomes "opene")."""
    if len(w) < 3 or w[-1] in _VOWELS + "wxy" or w[-2] not in _VOWELS or w[-3] in _VOWELS:
        return False
    groups = re.findall(r"[aeiou]+", w)
    return len(groups) == 1


@functools.cache
def _overview():
    """composer_overview, imported on the first overview question rather than
    with the composer: the cold import is budgeted (test_engine_budgets)."""
    from tessellate.ai import composer_overview

    return composer_overview


def asked_whole(question: str) -> bool:
    """A question, or a subject asked about as a whole ("an overview of my
    sourdough notes"): no bare name to ask "which do you mean" about (L-chat-31)."""
    return bool(_ASKS_FIRST.match(rephrase(question)) or _overview().topic(question))


@functools.lru_cache(maxsize=1 << 16)
def _unaccented(word: str) -> str:
    """"josé" as "jose": the key a word is matched on, so a name typed on a
    phone keyboard without its accents meets the note that has them (E14)."""
    if word.isascii():
        return word
    return "".join(c for c in unicodedata.normalize("NFKD", word) if not unicodedata.combining(c))


def _stem(word: str) -> str:
    """A light stem, so "testers" meets "tester" and "booked" meets "book".

    Suffixes only, and only on words long enough that taking one off leaves a
    word: a stemmer that turned "news" into "new" would match the wrong notes.
    A word without a suffix is left whole, so "same" is never "sam" (engine
    probe P1: "who is Sam" quoted "Same breakfast as the long runs"); the
    silent "e" a suffix took ("hiring", "making") is put back instead.
    """
    #: One key for the UK and US spellings ("colour" meets "color", INBOX
    #: 895); the answer is still made from the note's own words.
    return _stem_plain(variants.canonical(_unaccented(word.lower())))


#: Plurals whose singular ends in f or fe: "find notes about knives" must meet
#: "Knife sharpening" (grading round 1324).
_F_PLURALS = {"knives": "knife", "wives": "wife", "shelves": "shelf", "loaves": "loaf", "leaves": "leaf", "halves": "half", "calves": "calf"}


#: Past forms no suffix rule folds, so a question that says "run" meets the
#: note that says "Ran" (audit 1030 Z4: "when did I run 8 km" answered with
#: another run's sentence). Only forms that are rarely another word: not
#: "saw", "left", "found", "felt".
IRREGULAR_PAST = variants.IRREGULAR_PAST


def _stem_plain(word: str) -> str:
    """`_stem` without the spelling key: what the import-time tables use, so
    importing the composer never loads the English list."""
    w = word.lower()
    if w in _NOT_PLURAL:
        return w
    if w in IRREGULAR_PAST:
        return IRREGULAR_PAST[w]
    if w in _F_PLURALS:
        return _F_PLURALS[w]
    return _strip_suffix(w)


def _suffix_fits(w: str, suffix: str, least: int) -> bool:
    """`w` ends in `suffix` and keeps a stem of `least` letters (or is a
    "baked", "liked", "named": a three-letter stem that lost a silent "e";
    it ends in a consonant; "ahead" and "bread" do not qualify)."""
    short_ed = suffix == "ed" and len(w) == 5 and w[2] not in "aeiou" + "y" and w[-3] not in _VOWELS and _one_syllable_cvc(w[:-2])
    return w.endswith(suffix) and (len(w) - len(suffix) >= least or short_ed)


def _after_suffix(w: str, suffix: str) -> str:
    """"running" is "run" and "stopped" is "stop": the doubled last
    consonant a suffix brought is taken off with it (INBOX 725, measured:
    "what do my notes say about running" missed every note that says "run"
    or is tagged it); "baked" gets its "e" back."""
    if suffix not in ("ing", "ed"):
        return w
    if len(w) >= 3 and w[-1] == w[-2] and w[-1] not in "aeioulsz":
        return w[:-1]
    return w + "e" if _one_syllable_cvc(w) else w


def _strip_suffix(w: str) -> str:
    for suffix, keep, least in (("ies", "y", 4), ("ing", "", 3), ("ed", "", 4), ("es", "", 3), ("s", "", 3)):
        if not _suffix_fits(w, suffix, least):
            continue
        if suffix == "s" and w.endswith(("ss", "us", "is")):
            break
        if suffix == "es" and not w.endswith(("ches", "shes", "sses", "xes", "zes")):
            continue
        w = w[: len(w) - len(suffix)] + keep
        #: A plural of an "-ing" or "-ed" word folds like the word: "meetings"
        #: and "meeting" are one key (audit 1031 C8).
        if suffix in ("s", "es") and w.endswith(("ing", "ed")):
            return _strip_suffix(w)
        return _after_suffix(w, suffix)
    return w


#: Words that name the same thing in a notebook, so "how much will the trip
#: cost" finds "Trip budget" and is never told no note mentions "cost"
#: (measured on the showcase eval, INBOX 741). Small and tested: each group
#: is one thing said two ways, never a broader idea ("trip" is not "holiday"
#: plus "flight" plus "hotel").
SYNONYM_GROUPS = (
    ("cost", "price", "budget", "spend", "expensive", "cheap", "afford"),
    ("hotel", "stay", "staying", "accommodation", "room", "airbnb"),
    ("doctor", "gp", "appointment"),
    ("job", "work", "career"),
    ("buy", "purchase", "shopping"),
    ("film", "movie"),
    ("car", "drive", "driving"),
    ("eat", "cook", "food", "dinner", "lunch", "breakfast", "meal", "recipe"),
    ("book", "books", "reading", "read"),
    ("run", "running", "jog", "race"),
    ("flat", "apartment", "home", "house"),
    ("friend", "friends", "mate"),
    ("meeting", "call", "standup"),
    ("bug", "crash", "error", "broken", "slow"),
    ("idea", "ideas", "thought"),
    ("trip", "travel", "holiday", "vacation"),
    ("pay", "paid", "deposit", "payment"),
    ("hire", "hiring", "recruit"),
    ("launch", "release", "ship"),
    ("pack", "packing", "bring"),
) + composer_tables.EXTRA_SYNONYM_GROUPS


#: One act said five ways ("when did I phone mum" with the note "Called mum"; W8B 1111): the verbs of getting in touch,
#: the irregular past of "ring" included, which no suffix rule folds to its stem. Not a row of `SYNONYM_GROUPS`, whose
#: groups never share a word: "call" is also a meeting, "phone" and "text" also a device and a message.
CONTACT_VERBS = ("call", "phone", "ring", "rang", "rung", "text", "message")


def _build_synonyms(key=None) -> dict[str, frozenset[str]]:  # noqa: ANN001
    key = key or _stem_plain
    table: dict[str, set[str]] = {}
    for group in (*SYNONYM_GROUPS, CONTACT_VERBS):
        stems = {key(w) for w in group}
        for stem in stems:
            table.setdefault(stem, set()).update(stems - {stem})
    return {k: frozenset(v) for k, v in table.items()}


#: The names this question's notes give its subject ("Doug" for sourdough), by subject stem: set for a
#: "latest on X" ask by `composer_aliases.read` and read as synonyms, so the newer note that only says
#: "Doug the starter is bubbly again" is the latest on sourdough (W7b B7).
ALIASES: contextvars.ContextVar[dict] = contextvars.ContextVar("composer_aliases", default={})


def _alternatives(stem: str) -> frozenset[str]:
    """The other stems that name what `stem` names."""
    own = ALIASES.get().get(stem)
    return _keyed_synonyms().get(stem, frozenset()) | own if own else _keyed_synonyms().get(stem, frozenset())


@functools.lru_cache(maxsize=1)
def _keyed_synonyms() -> dict[str, frozenset[str]]:
    """The groups keyed by `_stem`, the UK and US spellings as one
    ("counselling" is "counseling"): built at the first question, not at
    import, which would load the English list (`_build_synonyms()` is the plain one)."""
    return _build_synonyms(_stem)


def _holds(stem: str, words: set[str]) -> bool:
    return stem in words or bool(_alternatives(stem) & words)


#: What a synonym hit is worth beside the word itself: the person's own word
#: is the better evidence.
SYNONYM_WEIGHT = 0.7


@functools.lru_cache(maxsize=1 << 14)
def _words_of(text: str) -> tuple[str, ...]:
    return tuple(_stem(w) for w in query_understanding.search_terms(text))


def _words(text: str) -> list[str]:
    """The stems of a text's words. Cached by text, since every answer reads
    the same notes again (second eye F8); a fresh list, for callers that edit it."""
    return list(_words_of(text))


#: The verbs the app does or answers as acts: a question that opens with one
#: is about what follows it, never about the verb (audit 1029 C15).
_COMMAND_VERBS = frozenset(
    "read open show draft write compose compare explain define summarise summarize archive unarchive restore split merge "
    "duplicate clone combine rename retitle tag untag pin unpin delete remove move file link unlink append add".split()
)


_COMMAND_LEADS = frozenset("please pls can could would will you just ok okay hey and then".split())


_COMMAND_FILLER = frozenset("me my the a an this that these those all both every two three four five".split())


_DRAFTED = frozenset("message messages email emails text reply letter note".split())


_BIN_WORDS = frozenset("bin trash".split())


def _is_clause_start(words: list[str], at: int) -> bool:
    """A word opens a clause at the start, after a comma or semicolon, after
    "then", and after "and" when a command with its object follows ("and merge
    the two"), so "my running notes and my baking notes" keeps both halves."""
    if at == 0:
        return True
    prev = words[at - 1]
    if prev[-1:] in ",;" or prev.casefold() == "then":
        return True
    return prev.casefold() == "and" and at + 1 < len(words) and words[at + 1].casefold() in _COMMAND_FILLER


def _without_command(text: str) -> str:
    """The subject without the commands that wrap it, one pass over the words:
    "draft a message to Sara" is Sara, "move the budget to the bin" is budget,
    "merge the two lentil soup notes" is lentil soup. A verb is a command where
    it leads a clause (the sentence, or after a comma, "then", "and merge the"),
    so "books I am reading" keeps its verb."""
    words = text.split()
    out: list[str] = []
    at = 0
    changed = False
    while at < len(words):
        start = at
        while start < len(words) and words[start].casefold() in _COMMAND_LEADS and _is_clause_start(words, start):
            start += 1
        if start < len(words) and words[start].casefold() in _COMMAND_VERBS and _is_clause_start(words, start):
            end = len(words)
            for nxt in range(start + 1, len(words)):
                if _is_clause_start(words, nxt) and words[nxt].casefold() in _COMMAND_VERBS | _COMMAND_LEADS:
                    end = nxt
                    break
            clause = _without_bin(words[_past_filler(words, start):end])
            if clause:
                out.extend(clause)
                changed = True
                at = end
                continue
        out.append(words[at])
        at += 1
    return " ".join(out) if changed else text


def _past_filler(words: list[str], at: int) -> int:
    """Where the subject starts after the command verb at `at`: past "the",
    and for a draft past "a message to"."""
    drafting = words[at].casefold() in ("draft", "write", "compose")
    at += 1
    while at < len(words) and (words[at].casefold() in _COMMAND_FILLER or (drafting and words[at].casefold() in _DRAFTED)):
        at += 1
    if drafting and at < len(words) and words[at].casefold() in ("to", "for"):
        at += 1
    return at


def _without_bin(rest: list[str]) -> list[str]:
    """"budget to the bin" is budget."""
    if len(rest) >= 3 and rest[-3].casefold() == "to" and rest[-2].casefold() == "the" and rest[-1].casefold().rstrip("?.!") in _BIN_WORDS:
        return rest[:-3]
    return rest


def subject_terms(question: str) -> list[str]:
    """The words the question is about, as typed, without the asking words."""
    question = rephrase(question)
    question = _IF.sub("", question)
    question = _ANYTHING_ON.sub("", question)
    #: The asking words go; "how come" becomes the "why" it means, since a
    #: bare "the list is slow" reads to the parser as a list command.
    question = re.sub(r"^how come\b", "why", question, flags=re.I)
    question = re.sub(r"^(?:what time|how many (?:of my )?notes (?:mention|are about|about|on))\b", "", question, flags=re.I)
    question = rec.without_windows(question)
    understood = query_understanding.understand(question)
    source = understood.subject or question
    #: "List my ..." and "Name the ..." ask; "the reading list" names. Only the
    #: first word is dropped, so the list a question is about stays in it.
    #: "Count my notes about Hobart" asks; it is not a word to find in a note
    #: ("Don't count the balance"; second eye F10).
    if re.match(r"^\s*(list|name|show|tell|count|check|tally)\b", question, re.I):
        source = re.sub(r"^\s*(list|name|show|tell|count|check|tally)\b", "", source, flags=re.I)
    seen: list[str] = []
    #: Only a command the question itself opens with: "what did I add to the
    #: pasta" keeps its "add", which understanding may have moved to the front.
    if _without_command(question) != question:
        source = _without_command(source)
    terms = query_understanding.search_terms(source)
    for at, word in enumerate(terms):
        #: "first order" names a thing; "whose birthday is first" is only the asking (R3-4, G11).
        names_next = word == "first" and at + 1 < len(terms) and terms[at + 1] not in _ASKING_WORDS
        if (word in _ASKING_WORDS and not names_next) or word in seen:
            continue
        seen.append(word)
    seen = _without_asked_shape(question, seen)
    #: A praise word alone names nothing ("anything interesting", "the cool
    #: stuff"); beside a noun ("interesting bean") it stays (INBOX 1561).
    return [] if all(w in question_noise.PRAISE_WORDS for w in seen) else seen


def _without_asked_shape(question: str, seen: list[str]) -> list[str]:
    """The terms less the words that are the question's shape, not its subject."""
    #: "What dates do I have", "the date of my passport expiry" ask for dates; the word is no term to find in a
    #: note ("the date test still fails"; R3-5).
    if _DATE_ASK.search(question):
        seen = [w for w in seen if w not in ("date", "dates")]
    #: "the first note I wrote about Sara": the place in an order, not a word to find ("First day of uni"; R3-4).
    if _ORDINAL_NOTE.search(question):
        seen = [w for w in seen if w not in ("first", "last")]
    #: "When does uni start": the verb is the event's own, not a word to find; kept as a term it finds the
    #: Marathon note's "Start is at 9am" and answers with that race (round 3 review, R3-1).
    if _EVENT_ENDS.search(question) and len(seen) > 1:
        seen = [w for w in seen if w.lower() not in _EVENT_VERBS]
    return seen


_EVENT_ENDS = lazy_compile(r"^\s*when\s+(?:does|do|will|is)\b[^?.!]{1,80}?\b(?:start|begin|end|finish)s?\s*[?.!]*$", re.I)
_EVENT_VERBS = frozenset(("start", "starts", "begin", "begins", "end", "ends", "finish", "finishes"))
_ORDINAL_NOTE = lazy_compile(r"\b(?:first|last)\s+(?:note|notes|entry|entries)\b", re.I)
_DATE_ASK = lazy_compile(r"\b(?:what|which)\s+dates?\b|\bdates?\s+(?:of|for)\b", re.I)


_COMPARE_SIDES = (
    lazy_compile(r"\bdifferences? between (?P<a>.+?) and (?P<b>.+?)[?.!]*$", re.I),
    lazy_compile(r"\bcompare (?P<a>.+?) (?:and|with|to|vs\.?|versus) (?P<b>.+?)[?.!]*$", re.I),
    lazy_compile(r"^(?P<a>[\w' -]+?) (?:vs\.?|versus) (?P<b>.+?)[?.!]*$", re.I),
)


#: The patterns that name a comparison by more than a bare "vs" are tried first:
#: "pros and cons of A vs B" is not a "vs" with "pros and cons of A" on its left.
_COMPARE_SIDES = (*composer_tables.EXTRA_COMPARE_SIDES, *_COMPARE_SIDES, *composer_tables.BARE_COMPARE_SIDES)


#: The extra comparison words ("cheaper than", "compared with", "pros and cons
#: of ... and ..."), read as a comparison only when both sides can be named.
_COMPARE_EXTRA = lazy_compile(composer_tables.COMPARE_SHAPE_EXTRA, re.I)


_NOTES_NOUNS = ("note", "notes", "entries")
_TODO_NAMES = frozenset(("todo", "to-do", "to do", "todos", "to dos"))


_SIDE_NUMBERS = r"one|two|three|four|five|1|2|3|4|5|first|second|third|a|b|c|old|new"


def _bare_side(side: str, shared_noun: bool = False) -> str:
    """One side of a comparison without the noun that names the notes:
    "Lisbon notes" is Lisbon (1324)."""
    side = re.sub(r"^(?:how (?:does|do|is|are) |what (?:does|do) )?(?:my )?(?:notes? )?(?:on |about )?", "", side.strip(" ,"), flags=re.I)
    # Word steps, not `\s+(?:notes?|entries)$`: that regex is quadratic on a run
    # of whitespace (CodeQL py/polynomial-redos).
    head, _, last = side.rstrip().rpartition(" ")
    if head and last.casefold() in _NOTES_NOUNS:
        side, shared_noun = head, True
    if shared_noun:
        #: The article went with the noun: "the Porto notes" is Porto, as a
        #: heading and as a topic (audit 1029 C36: "**the Porto**"), while "the
        #: Lisbon flat" keeps its "the". Lower case only: "The Overstory" is a title.
        side = re.sub(r"^(?:the|my|our|your) ", "", side)
    return side.strip(" ,") or side


_SIDE_CONNECTOR = lazy_compile(r"\s(?:and|with|to|vs\.?|versus)\s", re.I)


#: Strongest first: "Trip to Lisbon and Trip to Porto" splits at "and", the
#: "to" belongs to the first trip's name.
_SIDE_PRIORITY = (r"and", r"vs\.?", r"versus", r"with", r"to")


def _clean_split(span: str) -> tuple[str, str, str] | None:
    for word in _SIDE_PRIORITY:
        hit = re.search(rf"\s{word}\s", span, re.I)
        if hit and span[: hit.start()].strip() and span[hit.end():].strip():
            return span[: hit.start()], span[hit.end():], hit.group(0).strip()
    return None


#: The words that join two sides and may also sit inside a name ("Trip to
#: Lisbon"); a span cut at "or" or "than" was cut where the person meant it.
_NAME_JOINERS = frozenset({"and", "with", "to", "vs", "versus"})


def _raw_sides(text: str, match: re.Match) -> list[str]:
    """The sides a comparison pattern cut, as typed and one list: each of the
    two spans may name several ("the dentist, the Lisbon trip or the Tokyo
    trip"), cut at its commas and at the word that joins them."""
    raw_a, raw_b = match.group("a"), match.group("b")
    words = text[match.end("a"): match.start("b")].lower().replace(",", " ").replace(".", " ").split()
    joiner = words[-1] if words else ""
    if joiner in _NAME_JOINERS and (_SIDE_CONNECTOR.search(f" {raw_a} ") or _SIDE_CONNECTOR.search(f" {raw_b} ")):
        clean = _clean_split(text[match.start("a"): match.end("b")].strip(" ?.!"))
        if clean:
            raw_a, raw_b, joiner = clean[0], clean[1], clean[2].lower().rstrip(".")
    return [*composer_sides.listed(raw_a, joiner), *composer_sides.listed(raw_b, joiner)]


def _numbered_sides(sides: list[str]) -> list[str]:
    """"compare sourdough loaf one and two": a side that is only a number is
    the one before it with its own number (audit 1029 C36)."""
    out: list[str] = []
    for side in sides:
        before = re.match(rf"(.+ )(?:{_SIDE_NUMBERS})$", out[-1].strip(), re.I) if out else None
        out.append(before.group(1) + side if before and re.fullmatch(_SIDE_NUMBERS, side.strip(), re.I) else side)
    return out


#: The category names of the notes a digest answer reads, "and" written "&": "what do I know about
#: courses and study" names one category, not two sides to compare (INBOX 1743).
NOTE_CATEGORIES: contextvars.ContextVar[frozenset] = contextvars.ContextVar("composer_note_categories", default=frozenset())


def _one_category(sides: tuple[str, ...] | None) -> bool:
    """Whether `sides` joined are all of one category's name."""
    return bool(sides) and re.sub(r"\s+", " ", re.sub(r"\band\b", "&", " and ".join(sides).lower())) in NOTE_CATEGORIES.get()


def compare_sides(question: str) -> tuple[str, ...] | None:
    """The things a comparison names, as typed: ("Lisbon", "Porto"), or three
    to six of them for "which is soonest, the dentist, the Lisbon trip or the
    Tokyo trip". A format wish ("in a table", "please") is no part of a name."""
    #: Once, not once per pattern: each reading spell-checks every unknown
    #: word (audit 1030 Z65).
    text = rephrase(question)
    for pattern in _COMPARE_SIDES:
        match = pattern.search(text)
        if not match:
            continue
        raw = _numbered_sides([composer_sides.strip_format(side) for side in _raw_sides(text, match)])
        #: "the Porto and Lisbon notes": one "notes" names every side.
        shared = bool(raw) and raw[-1].rpartition(" ")[2].casefold() in _NOTES_NOUNS
        sides = [_bare_side(side, shared_noun=shared) for side in raw]
        #: The `_TODO_NAMES` are a note's name here, though the parser reads them as the command (L-chat-6).
        sides = [side for side in sides if subject_terms(side) or side.casefold().strip() in _TODO_NAMES]
        if len(sides) >= composer_sides.MIN_SIDES:
            return None if _one_category(tuple(sides)) else tuple(sides[: composer_sides.MAX_SIDES])
    pair = _lower_pair(text)
    return None if _one_category(pair) else pair


#: The words of the notes a digest answer reads, for `_lower_pair` only: `_KNOWN` also steers the speller.
NOTE_WORDS: contextvars.ContextVar[frozenset] = contextvars.ContextVar("composer_note_words", default=frozenset())


#: The notes' own text, as written, for `_lower_pair` only: a pair one note says as a phrase is one subject.
NOTE_TEXTS: contextvars.ContextVar[tuple] = contextvars.ContextVar("composer_note_texts", default=())


def _said_together(a: str, b: str) -> bool:
    """Whether some note says "a and b" (or "a & b", "a, b") as one phrase: "salt and pepper" in a recipe.
    Capitalised in the middle of a sentence it is two names ("Anna, Tom and Sara" is a guest list)."""
    phrase = re.compile(rf"\b{re.escape(a)}\s*(?:and|&|,)\s*{re.escape(b)}\b", re.I)
    for text in NOTE_TEXTS.get():
        for hit in phrase.finditer(text):
            before = text[: hit.start()].rstrip(" \t")
            names = text[hit.start()].isupper() and bool(before) and before[-1] not in ".!?\n:#-*"
            if not names:
                return True
    return False


def _lower_pair(text: str) -> tuple[str, ...] | None:
    """"tom and sara": two lower-case words the notes hold, neither an everyday
    one. "salt and pepper" with no notes about them stays one thing, and so does
    a pair a note says together as a phrase."""
    pair = composer_tables.LOWER_PAIR.match(text.strip())
    known = _KNOWN.get() | NOTE_WORDS.get()
    if not pair or not known:
        return None
    sides = (pair.group("a"), pair.group("b"))
    if all(w.lower() in known and w.lower() not in common_words.WORDS and subject_terms(w) for w in sides) and not _said_together(*(w.lower() for w in sides)):
        return sides
    return None


#: The words the notes under question hold: the person's own, so the speller
#: never "corrects" a name or a term they wrote (`question_noise.repair`).
_KNOWN: contextvars.ContextVar[frozenset] = contextvars.ContextVar("composer_known", default=frozenset())


#: "When was my gym log written", "what day did I create the pasta recipe",
#: "what date was the essay started": about the note's own day, not its words.
_WRITTEN_WHEN = lazy_compile(
    r"\b(?:when|what (?:day|date)|how long)\b.{0,50}?\b(?:written|wrote|made|created|(?:started|began|begun)(?!\s+(?:\w+ing|to\s+\w+)\b)|"
    r"added|saved|put together|jotted|typed|"
    # The base verb is the note's day only after "did I": "when does uni start" and "when do I make
    # the banana bread" ask about the event, not the day it was written (round 3, R3-1).
    r"did\s+(?:I|we)\b.{0,30}?\b(?:write|make|create|(?:start|begin)(?!\s+(?:\w+ing|to\s+\w+)\b)|add|save|put together|jot|type))\b",
    re.I,
)


#: Words that make it a question about the notes' words or ends, not one note's day.
_NOT_ONE_NOTE = lazy_compile(r"\b(?:about|mention\w*|says?|said|last|latest|newest|first|ever|any|every|all)\b", re.I)


_WHEN_NOISE = frozenset(
    "day date time created create creating start started starting began begun note notes page entry entries "
    "made make making added add saved save wrote write written put together jotted typed".split()
)


def when_terms(terms: list[str]) -> list[str]:
    """The terms of "when did I write about X" that name X, not the asking."""
    return [t for t in terms if t.lower() not in _WHEN_NOISE]


def asks_time(question: str | None) -> bool:
    """Whether a question is about time, the only time an answer says a date
    (INBOX 1441: "I dont like how it refers to dates")."""
    return rec.asks_time(question or "") or asks_written_when(question or "")


def asks_written_when(question: str) -> bool:
    return bool(_WRITTEN_WHEN.search(question or "")) and not _NOT_ONE_NOTE.search(question or "")
