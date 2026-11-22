"""A question typed the way people type: slang, typos, run-together words.

Asked for by the owner (INBOX 741): "does it cover any and ALL typos, maybe
use similarity or meaning, cover all slang like pls, ty, lol, u, r, wym,
etc?". The composer reads a question's kind (when, why, how many, a
comparison) from its words, so a question typed "whenis teh dentist rn pls"
must reach it as "when is the dentist right now please". Three layers, each
tested, each leaving the person's subject words as they typed them:

1. **Slang and text-speak** (`SLANG`, `SOCIAL`): a table, one entry per
   word, spelled out; pleasantries and laughter ("ty", "lol") are small
   talk, answered as such rather than searched for.
2. **Typo repair** (`repair`): a weighted edit distance against the
   composer's own small vocabulary of asking words (`VOCABULARY`), with a
   neighbouring key, a doubled letter and a swap of two letters cheaper
   than any other edit, scaled to the word's length; words run together
   ("whenis") split and words split ("wh en") joined when the result is
   an asking word. A real word near an asking word ("then", "show") is
   never changed. The subject's own typos are put right against the
   notebook's words by the composer (`composer._fit_terms`), for scoring
   only.
3. **Meaning as the fallback** (`guess_kind`): a question no rule read is
   compared with example questions of each kind, by the embedder's cosine
   when one is loaded and by character trigrams when not, and given a kind
   only when one is clearly nearest.

What is still missed is said in `docs/roadmap/archive/agent-remaining/composer-voice-1006.md`
and measured by `tests/_composer_eval.py --noise`.
"""

from __future__ import annotations

import difflib
import math
import re

from tessellate.core.lazyre import lazy_compile
from tessellate.data import LazyTable
from collections import Counter

from tessellate.ai import act_registry, composer_aboutme, repair_turn, spelling, typo_context
from tessellate.ai.spelling import distance  # noqa: F401 - re-exported: the speller owns it, so the two modules do not import each other

# --- 1. slang and text-speak ----------------------------------------------------

#: Every entry a word people type for a longer one. Only words that are never
#: anything else in a question: "4" and "2" (numbers in "4 weeks"), "ill",
#: "sat", "sun", "mar" and "may" are left out on purpose.
SLANG: dict[str, str] = LazyTable("noise_slang.json")
#: `noise_slang.json` holds four tables merged in this order: the hand-written one, the
#: 2026-10-06 expansion (misspellings, dropped letters, text-speak), the 2026-10-10 Gemini
#: branch additions (3973 entries; a key that is itself a word in `REAL_WORDS` or the shipped
#: word list is left out, since repairing it would "correct" a correctly spelt word, and so is a
#: key with a space, which `repair` never looks up) and the first table's tail. The common
#: misspellings look to come from Wikipedia's "Lists of common misspellings" (CC BY-SA):
#: see docs/THIRD_PARTY.md.

#: Words that are small talk on their own: a message made only of these is
#: answered as small talk (`composer.social`), never searched for. The value
#: is the kind of reply.
SOCIAL: dict[str, str] = LazyTable("noise_social.json")
#: `noise_social.json` also holds the one-word reactions and confusion, thanks in other
#: languages, laughter, greetings, apologies, and the compliments, complaints and feelings
#: added 2026-10-10. A word that is also a slang entry is left out: slang is spelled out first.

#: Words that ride along with small talk without making it a question:
#: "ty for the help", "thanks a lot mate".
_SOCIAL_FILLER = frozenset(
    "for the a lot help helping that this it again man mate bro dude buddy friend all very really much so"
    #: "i'm tired" is tiredness and "you're useless" a complaint, not "ok"
    #: (measured 2026-10-11: both read as an acknowledgement).
    " i i'm im am feel feeling you're youre ur bot was today too tbh".split()
)


#: Laughter typed long ("hahahaha", "lmaooo", "lollll").
_LAUGH = lazy_compile(r"^(?:(?:ha|he|ah){2,}h?|lo+l+(?:o+l+)*|lmf?a+o+|xd+)$", re.I)
#: One range for the supplementary symbols block: a second range inside it
#: (U+1F900 to U+1F9FF) was redundant (CodeQL #551, overly large range).
_EMOJI = lazy_compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U00002300-\U000023FF\U0000FE0F\U0000200D]+"
)
#: Emoticons, read as small talk too.
_EMOTICON = lazy_compile(r"(?:^|\s)(?:[:;=8][-']?[)(DPp/\\|*]+|<3|\^_?\^)(?=\s|$)")


#: Keys hit by accident at a sentence's edge (INBOX 801, the owner: "it
#: doesnt account for accidental extra characters like a backslash"): a stray
#: `\\`, `|`, backtick, `~` or `^` against a word. One beside a colon or a
#: semicolon is an emoticon (":\\", ";|") and stays.
_STRAY_KEYS = "\\|`~^"
_BEFORE_STRAY = "?.!)\"'"
_STRAY_HEAD = lazy_compile(r"^\s*[\\|`~^]+(?=\w)")
_RUN_OF_SPACES = lazy_compile(r"[ \t]{2,}")


_ARCHIVED_WORD = lazy_compile(r"\barchived\b", re.I)


def asks_archived(question: str) -> bool:
    """Whether the question is about archived notes ("archived notes from last
    week"); any other list or count leaves them out."""
    return bool(_ARCHIVED_WORD.search(question or ""))


def _strip_stray_tail(text: str) -> str:
    """The trailing stray keys off a text, by a scan from the end rather than a
    regex: an anchored-at-the-end pattern rescans a long run of backslashes
    from every start (CodeQL, polynomial regex on user input). A run of stray
    keys goes when a word, a space or closing punctuation stands before it; a
    run of slashes only after a sentence's end ("why?/")."""
    body = text.rstrip()
    end = len(body)
    start = end
    while start > 0 and body[start - 1] in _STRAY_KEYS:
        start -= 1
    if start < end and start > 0 and (body[start - 1].isalnum() or body[start - 1] == "_" or body[start - 1].isspace() or body[start - 1] in _BEFORE_STRAY):
        return body[:start]
    start = end
    while start > 0 and body[start - 1] == "/":
        start -= 1
    if start < end and start > 0 and body[start - 1] in "?.!":
        return body[:start]
    return text


#: "new notes", "show new notes", "any new notes please", "see new notes about
#: uni": the newest notes, listed (INBOX 1532: "new notes" was answered with the
#: prompt for making one). "New" before a plural noun is the order word
#: "newest", read as the other four are ("latest", "recent" ...); a singular
#: "new note" with words stays the create act.
_NEW_NOTES = lazy_compile(
    r"^(?P<lead>(?:(?:please|pls|can you|could you|would you)\s+)?(?:(?:show|see|list|give|get|display|open|find|view|read)(?:\s+me)?\s+)?"
    r"(?:(?:any|all|my|the|some|of)\s+)*)new\s+(?P<noun>notes|entries)(?P<tail>(?:\s+(?:about|on|for|from|regarding)\s+\S.*?)?(?:\s+(?:please|pls|now|today))?)[?.!\s]*$",
    re.I,
)


def new_notes_as_newest(text: str) -> str:
    """`text` with "new notes" said as "newest notes" when the whole turn asks
    for them; any other text as it came."""
    found = _NEW_NOTES.match(text or "")
    if not found:
        return text
    return f"{found.group('lead')}newest {found.group('noun')}{found.group('tail')}"


def strip_strays(text: str) -> str:
    """Stray keys off a text's edges and runs of spaces made one; nothing
    else changes (a tool's argument, INBOX 808)."""
    text = _STRAY_HEAD.sub("", _strip_stray_tail(str(text or "")))
    return _RUN_OF_SPACES.sub(" ", text).strip()


_RATING_SLASH = lazy_compile(r"(?<![\w/])(\d{1,3}) ?/ ?(5|10|20|100)\b(?! ?/)")
_DATE_CUES = frozenset("on by due before until till from since at for of around near about after during circa week"
                        " starting ending".split())
# A fraction is a rating only beside a rating word; with none ("what did I do around 9/10") it is a date (the owner,
# 2026-11-11: "9/10 could be a date based on context").
_RATING_CUES = lazy_compile(r"\b(?:is|was|are|were|gave|give|given|giving|rate[ds]?|rating|ratings|scored?|scores|stars?|out)\b", re.I)


def _rating_words(text: str) -> str:
    """"is Piranesi 9/10" is a rating ("9 out of 10", which the readers already take), not 9 October; after "on",
    "by", "due" and the like it stays a date (audit 1030 Z17)."""
    def say(m: re.Match) -> str:
        before = text[: m.start()].split()
        if before and before[-1].lower() in ("a", "an"):  # "I reckon it was around a 9/10": "a 9/10" is always a score
            return f"{m.group(1)} out of {m.group(2)}"
        if int(m.group(1)) > int(m.group(2)) or (before and before[-1].lower() in _DATE_CUES) or not _RATING_CUES.search(text):
            return m.group(0)
        return f"{m.group(1)} out of {m.group(2)}"

    return _RATING_SLASH.sub(say, text) if "/" in text else text


def tidy(text: str) -> str:
    """A question as it was meant before anything reads it (INBOX 801): stray
    keys off its edges, runs of spaces made one (line breaks kept, a pasted
    passage keeps its shape), and a sentence typed all in capitals
    ("NOTEBOOK STATS") put in lower case. One capitalised word ("NASA") is a
    name and stays. Words are never changed here: `repair` does that, for
    the readers that want it."""
    text = _rating_words(strip_strays(text))
    words = re.findall(r"[A-Za-z]{2,}", text)
    if len(words) >= 2 and len(text) <= 200 and not re.search(r"[a-z]", text):
        text = text.lower()
    return text


def strip_symbols(text: str) -> str:
    """Emoji and emoticons off, the rest kept."""
    text = _EMOJI.sub(" ", text or "")
    text = _EMOTICON.sub(" ", text)
    return " ".join(text.split())


#: The asking words before a topic ("what is there about", "search my notes
#: for"), taken off to leave the topic a search_notes call is given.
_ASKING_HEAD = lazy_compile(
    r"^(?:(?:can|could|would) you |please )?(?:what(?:'s| is)? (?:there |do i have |have i got |did i write )?(?:about|on)|"
    r"search (?:my |the )?(?:notes? )?(?:for|about)|search|find (?:my )?(?:notes? )?(?:about|on)?|look (?:for|up)|"
    r"(?:show|list) (?:me )?(?:my )?notes? (?:about|on)|notes? (?:about|on)|anything (?:about|on))(?:\s+|$)",
    re.I,
)


def topic_of(text: str) -> str:
    """The topic a request names, cleaned (`tidy`), with its
    asking words and trailing punctuation off: "what is there about dentist\\"
    gives "dentist". "" when nothing is left."""
    #: The agent's user message carries the notes first and the request
    #: last, after "My request: " (`agent.build_agent_messages`).
    text = str(text or "").rsplit("My request: ", 1)[-1]
    words = _ASKING_HEAD.sub("", tidy(text).strip(" ?.!,;:")).strip(" ?.!,;:")
    return re.sub(r"^(?:the|my|our|a|an)\s+", "", words, flags=re.I)


#: Conversational turns of more than one word, read whole (INBOX 741, the
#: owner: "k is also ok", "right ok", "alright. any and all conversational
#: messages"). Longest first, so "wait what" is confusion before "what" is
#: anything at all.
SOCIAL_PHRASES: dict[str, str] = LazyTable("noise_social_phrases.json")



#: A letter typed three times or more ("yooooo", "heyyy", "thxxx").
_STRETCH = lazy_compile(r"([A-Za-z])\1{2,}")
_LETTERS = lazy_compile(r"[A-Za-z]+")


def _unstretched(word: str) -> str:
    """`word` with each run of three or more of a letter cut to one or two,
    whichever reads as a word: a small-talk word first ("heyyy" is "hey"),
    then a dictionary word with the double kept ("goood" is "good", not
    "god"); as typed when neither does or the runs are many."""
    runs = list(_STRETCH.finditer(word))
    if not runs or len(runs) > 3:
        return word
    shapes = [""]
    last = 0
    for run in runs:
        head = word[last:run.start()]
        shapes = [f"{s}{head}{run.group(1) * n}" for s in shapes for n in (1, 2)]
        last = run.end()
    shapes = [f"{s}{word[last:]}" for s in shapes if len(f"{s}{word[last:]}") >= 2]
    social = next((s for s in shapes if s.lower() in SOCIAL or s.lower() in SOCIAL_PHRASES), None)
    if social:
        return social
    return next((s for s in sorted(shapes, key=len, reverse=True) if spelling.is_word(s.lower())), word)


def destretch(text: str) -> str:
    """`text` with each stretched word read as its word (INBOX 1459: "yooooo"
    was answered as stray keys). Words with no run of three are untouched."""
    if not text or not _STRETCH.search(text):
        return text
    return _LETTERS.sub(lambda m: _unstretched(m.group(0)), text)


#: Sounds typed while thinking ("errrmmm", "umm", "uhh", "hmm"): read past,
#: never searched for (INBOX 1485). Not "er", "um" inside a word, or "hum".
_FILLER = lazy_compile(r"^(?:u+m+|u+h+m*|e+r+m+|e+r{2,}|h+m+|m{2,}|e+h+m+|a+h+m+)$", re.I)
#: A whitespace-bounded run is one word; the shape check is on that run alone
#: (letters, then the punctuation typed after them), so no pattern scans a long
#: run twice (CodeQL 1890, 1894).
_WORD_RUN = lazy_compile(r"\S+")
_FILLER_SHAPE = lazy_compile(r"([A-Za-z]+)[.,;:!…]*")


def is_filler(word: str) -> bool:
    """Whether `word` is a sound typed while thinking ("umm", "errm")."""
    return bool(_FILLER.match(word))


#: Adjectives that colour a request and are not what it is about ("anything
#: interesting", "the cool stuff"): never a subject, so never a search word, a
#: topic or a follow-on (INBOX 1561). One list for all three.
PRAISE_WORDS = frozenset(
    """interesting interested cool fun funny neat nice good great awesome amazing fascinating useful helpful
    impressive special fancy clever handy exciting notable noteworthy""".split()
)

#: Words typed around a note, not naming one ("a random ahh note"): a chip
#: about "random ahh" asks for nothing (INBOX 1496).
_NO_SUBJECT = PRAISE_WORDS | frozenset(
    "random randomly ahh ahhh ahhhh lol lmao ngl tbh bruh idk whatever some any one thing things stuff something "
    "anything like just really very kinda sorta old new little bit".split()
)


def filler_subject(text: str) -> bool:
    """Whether every word of `text` is filler, so it names no subject."""
    words = re.findall(r"[a-z']+", (text or "").lower())
    return bool(words) and all(w in _NO_SUBJECT or is_filler(w) for w in words)


def _without_filler(run: re.Match[str]) -> str:
    word = _FILLER_SHAPE.fullmatch(run.group(0))
    return "" if word and _FILLER.match(word.group(1)) else run.group(0)


#: "What am I reading", "what have I been reading lately": the books the
#: notes keep, not the words "reading" sits in (a question inside an
#: ice-breakers note; audit 1031 C18). "reading" alone names no kind of note.
_READING_NOW = lazy_compile(
    r"(?P<lead>(?:and |so |ok |okay )?what)(?P<mid> am i(?: currently)?) reading"
    r"(?P<tail>(?: (?:right now|at the moment|lately|these days|currently|now|at present|recently|at this time))?[?.!\s]*)",
    re.I,
)


def media_kind(text: str) -> str:
    """"what am I reading" as "what book am I reading": the kind of note the
    verb asks for named, so the notes kept as books are searched. `text`
    itself for any other question."""
    found = _READING_NOW.fullmatch((text or "").strip())
    return f"{found['lead']} book{found['mid']} reading{found['tail']}" if found else text


def drop_filler(text: str) -> str:
    """`text` without its filler words and the punctuation typed after them
    ("errrmmm. hi test test" is "hi test test"); as typed when nothing else
    is left ("hmm" alone is a turn of its own)."""
    if not text or not re.search(r"(?i)\b(?:u|e|h|m|a)", text):
        return text
    kept = _WORD_RUN.sub(_without_filler, text)
    if kept == text:
        return text
    #: Spaces fold within a line; the line breaks stay (a numbered list after a
    #: colon is steps, and "make this a flowchart:\n1. ..." must keep them).
    lines = [" ".join(line.split()) for line in kept.split("\n")]
    kept = "\n".join(line for line in lines if line).lstrip(",.;: \n")
    return kept if re.search(r"\w", kept) else text


#: "r u an ai??", "are you a real person", "am I talking to a bot", "who are
#: you", "what are you": a question about what it is talking to, answered by
#: Atlas about itself, never searched for in the notes or on the web (INBOX
#: 1485). Read at the end of the message, after any lead-in ("whoa, stop
#: right there"). "are u ok" stays a how-are-you.
_WHAT_I_AM = r"(?:an? )?(?:real )?(?:ai|a i|bot|robot|human|person|real|machine|program|computer|chatbot|llm|chatgpt|gpt|human being|actual person)"
_IDENTITY = lazy_compile(
    rf"(?:^| )(?:are|r) (?:you|u|ya) (?:even |actually |really |just )?{_WHAT_I_AM}(?: or (?:not|what|an? \w+|\w+))?(?: (?:lol|haha|though|tho|then|too|right|now|or what))*$"
    rf"|^(?:who|what) (?:are|r) (?:you|u|ya)(?: (?:exactly|even|actually|really|then|again|lol|anyway))*$"
    rf"|(?:^| )am i (?:talking|speaking|chatting|texting) (?:to|with) {_WHAT_I_AM}(?: or \w+(?: \w+)?)?$"
    r"|^(?:is this|is it|this is) (?:an? )?(?:ai|bot|robot|chatbot|real person|human|machine)(?: or \w+(?: \w+)?)?$"
)


def asks_identity(message: str) -> bool:
    """Whether `message` asks what Atlas is (`_IDENTITY`)."""
    text = " ".join(re.split(r"[^\w']+", strip_symbols(drop_filler(message or "")).lower())).strip()
    return len(text) <= 80 and bool(_IDENTITY.search(text))


#: Said to the assistant about itself or about the person, with no note to
#: look in (audit 1031 C21): "do you like me", "what do you think", "how do
#: you feel". Whole message only: "what do you think about Lisbon"
#: names a subject and is a question about the notes.
_OPINION_ASK = lazy_compile(
    r"^(?:(?:do|did|would|will|can|could|does) (?:you|u|ya) (?:even |actually |really |still |ever )?"
    r"(?:like|love|hate|know|trust|miss|want|care about|care|believe|think|feel|reckon|enjoy|mind|get|understand|see|hear|have feelings)"
    r"(?: (?:me|us|so|i am|im|i'm|that|this|it|anything|a thing))?"
    r"|what (?:do|did|would|are) (?:you|u|ya) (?:think|feel|reckon|believe|say)(?: (?:of|about) (?:me|us|yourself|that|this|it))?"
    r"|how (?:do|did|would) (?:you|u|ya) (?:feel|like it|find it|see it)(?: (?:about|towards?) (?:me|us|it|this|that))?"
    r"|(?:are|r) (?:you|u|ya) (?:(?:even |actually |really |just |so )*(?:smart|clever|dumb|stupid|happy|sad|alive|conscious|sentient|lonely|bored|tired|mad|angry|funny|nice|friendly)))"
    r"(?: (?:lol|haha|though|tho|then|too|right|now|or not|at all|honestly|really|even))*$"
)
def addressed_kind(message: str) -> str | None:
    """"who" for a question put to the assistant about itself or the person
    ("do you like me"), else None."""
    text = " ".join(re.split(r"[^\w']+", strip_symbols(drop_filler(message or "")).lower())).strip()
    if len(text) > 80:
        return None
    return "who" if _OPINION_ASK.search(text) else None


_PHRASE_TABLE: list = []


def _phrase_table() -> list:
    """(phrase, kind, pattern) for every social phrase, longest first, built
    once. Sorting and compiling the 380-odd patterns on every call, past the
    `re` cache's 512 entries, was 17 of the dialogue eval's 42 s (CI time
    1102). Rebuilt if the table grew since."""
    if len(_PHRASE_TABLE) != len(SOCIAL_PHRASES):
        _PHRASE_TABLE[:] = [
            (phrase, SOCIAL_PHRASES[phrase], re.compile(rf"(?:^|\s){re.escape(phrase)}(?=\s|$)"))
            for phrase in sorted(SOCIAL_PHRASES, key=len, reverse=True)
        ]
    return _PHRASE_TABLE


def _social_phrases(text: str) -> tuple[list[str], str]:
    """The kinds of the social phrases in `text`, longest first, and the text without them."""
    kinds: list[str] = []
    for phrase, kind, pattern in _phrase_table():
        if phrase in text and pattern.search(text):  # the substring test skips nearly every pattern
            kinds.append(kind)
            text = pattern.sub(" ", text)
    return kinds, text


def asks_how(message: str) -> bool:
    """Whether a message asks how the app is or what it is doing ("hey! whatcha
    doing??"), whatever else it says: a greeting leads the kind, this is the rest."""
    text = " ".join(re.split(r"[^\w']+", strip_symbols(destretch(drop_filler((message or "").strip()))).lower())).strip()
    return "how" in _social_phrases(text)[0]


_SOCIAL_RANK = ("repair", "confused", "thanks", "sorry", "bye", "morning", "greeting", "how", "who", "frustrated", "reaction", "laugh", "compliment", "insult", "emotion", "glad")


def _word_kinds(words: list[str]) -> list[str] | None:
    """The kind each word says; None when one is not a social word."""
    kinds = []
    for word in words:
        kind = "laugh" if _LAUGH.match(word) else SOCIAL.get(word)
        if kind is None:
            return None
        kinds.append(kind)
    return kinds


def _spoken_to_kind(message: str) -> str | None:
    """"who" for a question about what it is talking to, "repair" for "not
    what I asked" (INBOX 1668 b), whatever else the message could be."""
    if asks_identity(message):
        return "who"
    if repair_turn.is_repair(message):
        return "repair"
    return addressed_kind(message) or composer_aboutme.kind(message)


def social_kind(message: str) -> str | None:
    """The kind of conversational turn a message is when every part of it is
    one ("ty", "lol", "ok thx", "right ok", "wait what", "how r u", an emoji
    alone), else None: a turn with a question in it is a question. A question
    about what it is talking to is "who", whatever leads into it."""
    if kind := _spoken_to_kind(message):
        return kind
    raw = destretch(drop_filler((message or "").strip()))
    if raw and not strip_symbols(raw):
        return "reaction" if re.search(r"[\U0001F600-\U0001F64F]", raw) else "ack"
    text = strip_symbols(raw).lower()
    if re.fullmatch(r"[?\s]+", text):
        return "confused"
    text = " ".join(re.split(r"[^\w']+", text)).strip()
    kinds, text = _social_phrases(text)
    words = [w for w in text.split() if w and w not in _SOCIAL_FILLER]
    if not words and not kinds:
        return None
    spoken = _word_kinds(words)
    if spoken is None:
        return None
    #: "ok thanks" is thanks; "lol ok" is laughter: the most telling part.
    return next((k for k in _SOCIAL_RANK if k in kinds + spoken), "ack")


# --- 2. typo repair ------------------------------------------------------------

#: The words whose spelling decides how a question is read: the asking words,
#: the small words around them, and the words that name a kind of question.
VOCABULARY = frozenset(
    """what when where who whom whose why how which many much often long
    is are was were do does did can could should would will has have had am
    the a an my me i you your about for of on in to with and or
    compare versus between difference latest status progress update explain
    summarise summarize overview anything everything recently recent newest
    remind tell list show give name say said know think mean
    there this that these those it its
    week month year today tomorrow yesterday morning tonight
    time date day""".split()
)

#: Asking words: the ones a typo is repaired towards first, and the only
#: ones a run-together word is split into ("whenis" is "when is").
ASKING = frozenset(
    """what when where who whose why how which many much often long
    is are was were do does did can could should would will has have had
    compare versus between difference latest status progress update explain
    summarise summarize overview remind tell list""".split()
)

#: The long words that name a kind of question, repaired wherever they are.
KIND_WORDS = frozenset(
    """compare versus between difference latest status progress update explain
    summarise summarize overview anything everything recently newest
    written writing thought mentioned""".split()
)

#: Real words one edit from an asking word, never "corrected": "then" is not
#: "when", "show" is not "how", "hat" is not "what". Also the words a
#: question's subject is often made of that sit near one.
REAL_WORDS = frozenset(
    """then than them they there here hat that wet wit shy now new few hen
    ten men hoe hot who how why any man main may mean many much lunch bunch
    such song along last lost late lest list lust state stat plain explains
    goes dues does dose lift gift wish wash with tell tall till fell sell
    well bell when what where which while whole whose those these hare care
    dare were wore wire mire ware wear year near dear bear fear gear hear
    rear tear the then toe tie tea ate eat oat cat car bar far jar tar war
    sing long lung hung rung sung wing king ring thing ling ding pong song
    has his hit hut had hid him her hen ham hay hey hi ho he hm mom mum dad
    one won own now how cow row low bow sow tow vow wow know knew knee
    box fox ox oil all ill well wall will mill fill hill kill pill till
    loan load lord lard list lost dentist""".split()
)

def allowance(word: str) -> float:
    """How far a word may be from the one it is read as, by its length: a
    three-letter word one slip, a long word two edits."""
    n = len(word)
    if n <= 2:
        return 0.0
    if n == 3:
        return 0.6
    if n <= 5:
        return 1.0
    if n <= 8:
        return 1.5
    return 2.0


_HOW_NEXT = frozenset("many much often long do does did to come can should far old big".split())


def nearest(word: str, vocabulary, after: str = "") -> str | None:  # noqa: ANN001
    """The one vocabulary word `word` is a typo of, or None: within its
    allowance, and nearer than any other by a clear margin (a tie is a
    guess, and no guess is made, except "how" against "who", which the next
    word settles)."""
    low = word.lower()
    if low in vocabulary or low in VOCABULARY or low in REAL_WORDS or not low.isalpha():
        return None
    limit = allowance(low)
    if not limit:
        return None
    scored = sorted((distance(low, v), v) for v in vocabulary if abs(len(v) - len(low)) <= 2)
    if not scored or scored[0][0] > limit:
        return None
    best = [v for d, v in scored if d <= scored[0][0] + 0.1]
    if set(best) == {"how", "who"}:
        how = after.lower() in _HOW_NEXT
        return "how" if how else "who"
    return best[0] if len(best) == 1 else None


#: How near a second reading must come to the chosen one, or how far the
#: chosen one may sit within its allowance, before the reading is unsure and
#: a "Did you mean ...?" offers the other (INBOX 741, the owner: "composer
#: could have clean fallback with did you mean to substitute??").
UNSURE_GAP = 0.35
UNSURE_SHARE = 0.75


def alternative(word: str, chosen: str, vocabulary) -> str | None:  # noqa: ANN001
    """The other word `word` could have meant when the reading as `chosen`
    is unsure, else None."""
    low = word.lower()
    limit = allowance(low)
    if not limit:
        return None
    mine = distance(low, chosen)
    others = sorted((distance(low, v), v) for v in vocabulary if v != chosen and abs(len(v) - len(low)) <= 2)
    near = [v for d, v in others if d <= limit and d - mine <= UNSURE_GAP]
    if near:
        return near[0]
    return None


def _split(word: str) -> str | None:
    """"whenis" is "when is": an asking word run into a vocabulary word, never
    a word of the English list ("wherein", "canon": VC8)."""
    low = word.lower()
    if len(low) < 5 or low in VOCABULARY or low in REAL_WORDS or spelling.is_word(low, strict=True):
        return None
    #: The head is an asking word, so only cuts up to the longest one are tried (each cut copies the word).
    for cut in range(2, min(len(low) - 1, max(map(len, ASKING)) + 1)):
        head, tail = low[:cut], low[cut:]
        if head in ASKING and tail in VOCABULARY:
            return f"{head} {tail}"
    return None


#: A comma with no space after it ("mindmap,a nd"): the space typed late.
_COMMA_RUN = lazy_compile(r"(?<=[A-Za-z]),(?=[A-Za-z])")


_SMALL_TALK: dict = {}


def _small_talk_words() -> frozenset:
    """SLANG and SOCIAL's words, built once, not as a new set per question."""
    size = len(SLANG) + len(SOCIAL)
    if _SMALL_TALK.get("size") != size:
        _SMALL_TALK.update(size=size, words=frozenset(SLANG.keys() | SOCIAL.keys()))
    return _SMALL_TALK["words"]


def slips_only(text: str, known=frozenset()) -> str:  # noqa: ANN001
    """`repair`, keeping only the slips: a word changed to one that looks like it ("abuot" to "about", "tokio" to
    "Tokyo") is taken, a word spelled out ("Dr" to "doctor", "uni" to "university") stays as typed, so the search
    still finds the notes that say it as the person did (round 3, R3-17). The question as typed when the repair
    added or dropped a word."""
    typed = " ".join((text or "").split())
    fixed = repair(tidy(typed), known=known) or typed
    old, new = typed.split(" "), fixed.split(" ")
    if len(old) != len(new):
        return typed
    return " ".join(b if difflib.SequenceMatcher(None, a.lower().strip("?.,!"), b.lower().strip("?.,!")).ratio() >= 0.6 else a for a, b in zip(old, new, strict=True))


def repair(text: str, report: list | None = None, known=frozenset(), fixed: list | None = None) -> str:  # noqa: ANN001
    """Slang spelled out, asking words put right, run-together words split
    and split words joined, then every other misspelt word read as the word it
    is near (`spelling`, Brief 90). `known` are words that are the person's
    own (their notes' words), never changed; so are names, capitals and
    anything with a digit. An unsure repair is added to `report` as
    {"typed", "chosen", "alternative"}; every misspelling put right (not slang
    spelled out) is added to `fixed` as (typed, chosen), which is what lets an
    answer say how it read the question."""
    #: A small-talk word is a word: "hi test" was glued into "hitest" (INBOX 1485).
    tokens = spelling.rejoin(_COMMA_RUN.sub(", ", strip_symbols(text)).split(" "), known, _small_talk_words(), fixed)
    tokens = [spelling.drop_stray(t, known, fixed) for t in tokens]
    out: list[str] = []
    i = 0
    while i < len(tokens):
        i += _repair_token(tokens, i, out, text, report, known, fixed)
    return " ".join(w for w in _real_word_slips(out, fixed, report) if w)


#: Real-word slips (Brief 104): a word that is a word, read as another only
#: where its neighbour says so. After an intensifier comes an adjective
#: ("insanely god" is "insanely good"); "it's" before a noun is "its" ("it's
#: use of language").
_INTENSIFIERS = frozenset("very really so insanely super pretty too extremely incredibly quite crazy seriously".split())
_AFTER_INTENSIFIER = {"god": "good", "grate": "great"}
_ITS_NOUNS = frozenset(
    """use own name place way job size shape colour color purpose answer answers title content contents settings
    layout design tone voice speed memory language style owner data value text icon label wording choices""".split()
)


_AUX_BEFORE_KNOW = frozenset({"do", "did", "does", "can", "could", "would", "should", "to"})


def _context_slip(out: list[str], i: int, fixed: list | None, report: list | None, words) -> None:  # noqa: ANN001
    """A real word that the sentence and the notebook say is another ("notes form last week", "run my skull"):
    read as it (`typo_context`), the other offered when the two stay close. The notebook's own words weigh in there."""
    word = out[i].rstrip("?!.,:;")
    if not word.islower() or (i and out[i - 1].rstrip("?!.,:;") != out[i - 1]):
        return
    read = typo_context.real_slip(out, i, words)
    if read is None:
        return
    chosen, other = read
    if report is not None and other:
        report.append({"typed": word, "chosen": chosen, "alternative": other})
    if chosen != word.lower():
        typo_context.swap(words, word, chosen)
        out[i] = chosen + out[i][len(word):]
        if fixed is not None:
            fixed.append((word, chosen))


def _real_word_slips(tokens: list[str], fixed: list | None, report: list | None = None) -> list[str]:
    out = list(tokens)
    #: Counted once and kept up to date, so a long question is read in one pass.
    words = typo_context.seen(out)
    for i in range(len(out)):
        _context_slip(out, i, fixed, report, words)
    for i in range(1, len(out)):
        prev = out[i - 1].lower().rstrip("?!.,:;")
        word = out[i].rstrip("?!.,:;")
        tail = out[i][len(word):]
        low = word.lower()
        if prev in _INTENSIFIERS and low in _AFTER_INTENSIFIER and _AFTER_INTENSIFIER[low] != low:
            out[i] = _AFTER_INTENSIFIER[low] + tail
        elif low in _ITS_NOUNS and prev in ("it's", "it’s") and out[i - 1].rstrip("?!.,:;") == out[i - 1]:
            out[i - 1] = "its"
        elif low == "no" and prev in ("i", "we", "you") and i >= 2 and out[i - 2].lower() in _AUX_BEFORE_KNOW and i + 1 < len(out):
            #: "what do i no about hanna": "no" after "do I" is "know" (R9-14).
            out[i] = "know" + tail
        else:
            continue
        if fixed is not None:
            fixed.append((f"{tokens[i - 1]} {tokens[i]}", f"{out[i - 1]} {out[i]}"))
    return out


def _join_asking(low: str, nxt: str, out: list[str]) -> bool:
    """Two pieces of one asking word ("wh en", "ho w"): joined onto `out`."""
    joined = (low + nxt.rstrip("?!.,:;").lower()) if nxt else ""
    if joined in ASKING and low not in VOCABULARY and len(low) <= 3:
        out.append(joined + nxt[len(nxt.rstrip("?!.,:;")):])
        return True
    return False


def _repair_token(tokens: list[str], i: int, out: list[str], text: str, report, known, fixed) -> int:  # noqa: ANN001
    """Puts the repaired reading of `tokens[i]` on `out`; returns how many
    tokens it used (two when the pieces of one asking word were joined)."""
    token = tokens[i]
    #: str.rstrip, not `(.*?)([?!.,:;]*)$`: that was quadratic on "!!!!" (CodeQL).
    word = token.rstrip("?!.,:;")
    tail = token[len(word):]
    low = word.lower()
    nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
    if _join_asking(low, nxt, out):
        return 2
    if _repair_late_space(low, tail, nxt, tokens, i, out, known):
        pass
    elif low in spelling.CONTRACTION_STEMS and word.islower() and nxt and low not in known:
        out.append(spelling.CONTRACTION_STEMS[low] + tail)
    #: A word of the person's own (a category "Uni", a tag) is never spelled out (audit 1028 E9).
    elif low in SLANG and low not in known and not (low in ("r", "y") and not _at_asking_place(out)):
        _repair_slang(low, word, tail, out, fixed)
    elif _split(low):
        out.append(_split(low) + tail)
        if fixed is not None:
            fixed.append((word, _split(low)))
    else:
        _repair_misspelt(token, word, tail, nxt, text, out, report, known, fixed)
    return 1


def _repair_late_space(low: str, tail: str, nxt: str, tokens: list[str], i: int, out: list[str], known) -> bool:  # noqa: ANN001
    """"as ther 17th": a date follows, so it is "the" (a "there" never is);
    "ther eis" is "there is", the space typed a letter late. True when it
    put a reading on `out`."""
    nxt_core = nxt.rstrip("?!.,:;").lower()
    if low in ("ther", "thr") and nxt_core[:1].isdigit() and low not in known:
        out.append("the" + tail)
        return True
    if not (low in SLANG and len(nxt_core) >= 3 and nxt_core.isalpha() and low not in known):
        return False
    if spelling.is_word(nxt_core, known):
        return False
    cut = spelling._resegment(low, nxt_core, known)
    if not cut:
        return False
    out.append(cut[0])
    tokens[i + 1] = cut[1] + nxt[len(nxt.rstrip("?!.,:;")):]
    return True


def _repair_slang(low: str, word: str, tail: str, out: list[str], fixed) -> None:  # noqa: ANN001
    out.append(SLANG[low] + tail)
    #: The table holds misspellings ("wehn") beside slang ("pls"): a
    #: word one slip from its reading is a typo, and is said.
    if fixed is not None and len(low) >= 3 and " " not in SLANG[low] and distance(low, SLANG[low]) <= 1.0:
        fixed.append((word, SLANG[low]))


def _report_alternative(low: str, word: str, chosen: str, pool, after: str, report: list) -> None:  # noqa: ANN001
    other = alternative(low, chosen, pool)
    #: "hwo many" is how and "hwo asked" is who: the next word
    #: settles it, and nothing is offered.
    if {chosen, other} == {"how", "who"} and (after.lower() in _HOW_NEXT or after.lower().endswith("ed")):
        other = None
    if other:
        report.append({"typed": word, "chosen": chosen, "alternative": other})


def _word_core(token: str) -> str:
    """A token without the punctuation after it."""
    while token and not (token[-1].isalnum() or token[-1] == "_"):
        token = token[:-1]
    return token


def _speller_may_read(word: str, out: list[str]) -> bool:
    """A lower-case word, or a capitalised one opening the question, may be a
    typo; shouting and names may not."""
    return word.isalpha() and not word.isupper() and (word.islower() or not out)


def _is_spelt(low: str, word: str, text: str, known) -> bool:  # noqa: ANN001
    """Already a word or an acronym, so not a typo: the speller knows "weird"
    (it is not "were"), and "API" in a sentence is not shouting."""
    return (len(low) >= 4 and spelling.is_word(low, known, strict=True)) or (len(word) > 1 and word.isupper() and not text.isupper())


def _repair_misspelt(token: str, word: str, tail: str, nxt: str, text: str, out: list[str], report, known, fixed) -> None:  # noqa: ANN001
    low = word.lower()
    after = _word_core(nxt)
    spelt = _is_spelt(low, word, text, known)
    chosen = nearest(low, ASKING, after) if _at_asking_place(out) and not spelt else None
    pool = ASKING
    if not chosen and _speller_may_read(word, out):
        if _repair_by_speller(word, tail, after, out, report, known, fixed, text):
            return
    #: Past the opening words only the long words that name a kind
    #: of question are repaired ("lastest"): a subject word near a
    #: small word ("slow", "show") is the subject.
    if not chosen and len(low) >= 6 and not spelt:
        chosen, pool = nearest(low, KIND_WORDS, after), KIND_WORDS
    if chosen and report is not None:
        _report_alternative(low, word, chosen, pool, after, report)
    if chosen and fixed is not None and chosen.lower() != low:
        fixed.append((word, chosen))
    out.append((chosen + tail) if chosen else token)


_SMALL_LEADS = frozenset("or an of to in on at by if so do is it as".split())


def _run_on_reading(word: str, known) -> tuple[str, str] | None:  # noqa: ANN001
    """A lower-case word that is two words run together, one of them small
    ("thenthe"), tried only when no list word is near."""
    if not word.islower():
        return None
    run_on = spelling.split_run_on(word, known)
    #: A small word run into a slang word ("orsmth" is "or smth"): the slang
    #: is not a list word, so `split_run_on` cannot see it; it is read as its
    #: own reading so the text is stable under a second repair.
    return run_on or next(
        ((word[:cut], SLANG[word[cut:]]) for cut in (2, 3) if word[:cut] in _SMALL_LEADS and len(word) > cut + 3 and word[cut:] in SLANG),
        None,
    )


def _speller_reading(word: str, after: str, out: list[str], known, text: str) -> tuple[str, str | None] | None:  # noqa: ANN001
    """The speller's (reading, alternative) for a misspelt word, the sentence choosing between two (INBOX 1745)."""
    low = word.lower()
    read = spelling.fix(
        low, after=after.lower(), before=out[-1].strip("?!.,:;") if out else "", known=known, distance=distance,
    )
    #: A capitalised word read as a name the lists hold is a name of the
    #: person's own, spelled their way: "Cristopher called" is not
    #: "Kristopher called" (Brief 90's list, O3).
    if read and word[:1].isupper() and read[0] not in spelling._common():
        read = None
    if read and read[1] and typo_context.speaks_for(read):
        #: Two readings near the word: the sentence, the notebook and the last turn choose (INBOX 1745).
        read = typo_context.lean(low, [read[0], read[1]], out[-1] if out else "", after, text.split(), False)
    return read


def _repair_by_speller(word: str, tail: str, after: str, out: list[str], report, known, fixed, text: str = "") -> bool:  # noqa: ANN001
    """Reads a misspelt word as the word it is near (`spelling.fix`), or as two
    words run together, one of them small ("thenthe"), tried only when no list
    word is near; True when it did and `out` has the reading."""
    read = _speller_reading(word, after, out, known, text)
    if read:
        chosen = read[0].capitalize() if word[0].isupper() else read[0]
        if report is not None and read[1]:
            report.append({"typed": word, "chosen": chosen, "alternative": read[1]})
        out.append(chosen + tail)
        if fixed is not None:
            fixed.append((word, chosen))
        return True
    run_on = None if spelling.is_word(word.lower(), known, strict=True) else _run_on_reading(word, known)
    if not run_on:
        return False
    out.append(" ".join(run_on) + tail)
    if fixed is not None:
        fixed.append((word, " ".join(run_on)))
    return True


def _at_asking_place(before: list[str]) -> bool:
    """The opening words of a question, or the word after "how" or a
    question word: where an asking word goes."""
    last = before[-1].lower().strip("?!.,:;") if before else ""
    #: Not the word after an article: "a ghose cursor" is not "a whose cursor".
    if len(before) <= 1:
        return last not in ("a", "an", "the")
    return last in ("how", "what", "when", "where", "who", "why", "which")


# --- 2b. repair guided by a router ------------------------------------------------
#
# O3 (BACKLOG "Type tolerance everywhere": "every registered command phrase
# with one keyboard-neighbour slip, one swap, one dropped and one doubled
# letter must route as the clean phrase does"). Measured 2026-10-17: 283 of
# 339 such slips routed as the clean phrase. The speller reads a slip as the
# nearest everyday word ("tmie" as "the", "remive" as "remind", "fid" as
# "did") or leaves a real word alone ("form", "concert"), because it cannot
# know which word a router needs. Here the router decides: a word one slip
# from a word the router reads is read as that word only when the router
# then takes the sentence and did not take it as typed.

#: Words a command reads besides the act registry's own: what a note is
#: called and joined by. A real word ("form", "nore") is read as one of these
#: only, never as a content word, so "a form about taxes" is never a command.
_COMMAND_GLUE = frozenset("note notes from about into to with the my called named".split())


def router_words() -> frozenset[str]:
    """Every word the act registry says a command with: verbs, labels,
    examples and the palette's stems, and the glue between them."""
    if _ROUTER_WORDS:
        return _ROUTER_WORDS[0]
    words = set(_COMMAND_GLUE)
    for act in act_registry.ACTS.values():
        for text in (act.verb, act.intent, act.label, act.example, act.stem):
            words.update(w for w in re.findall(r"[a-z]+", text.lower()) if len(w) >= 2)
    _ROUTER_WORDS.append(frozenset(words))
    return _ROUTER_WORDS[0]


_ROUTER_WORDS: list[frozenset[str]] = []


def guided(text: str, accepts, vocabulary=None, *, real_to=_COMMAND_GLUE, known=frozenset()) -> str | None:  # noqa: ANN001
    """`text` with one word read as the `vocabulary` word it is one slip from
    (`router_words` by default), when `accepts` takes that reading; None when
    no such reading exists. A real word is read only as a word of `real_to`
    (None: any), and a word of the person's own (`known`) never."""
    vocabulary = router_words() if vocabulary is None else vocabulary
    tokens = text.split()
    for i, token in enumerate(tokens):
        core = token.rstrip("?!.,:;")
        low = core.lower()
        if len(low) < 3 or not low.isalpha() or low in vocabulary or low in known or (core[:1].isupper() and i):
            continue
        pool = vocabulary if real_to is None or not spelling.is_word(low) else vocabulary & real_to
        for word in _one_slip_from(low, pool):
            #: A word that is a title, tag or name of the notebook's own is not the command word (INBOX 1745).
            if typo_context.prefers(low, word):
                continue
            reading = " ".join([*tokens[:i], word + token[len(core):], *tokens[i + 1:]])
            if accepts(reading):
                return reading
    return None


def _one_slip_from(low: str, pool) -> list[str]:  # noqa: ANN001
    """The words of `pool` one slip from `low`, nearest first. One slip
    changes at most two letters of the set, so the weighted distance is
    measured only for words that pass that (13 ms a question without it,
    measured on five ordinary questions)."""
    letters = set(low)
    near = [v for v in pool if abs(len(v) - len(low)) <= 1 and len(letters ^ set(v)) <= 2]
    return [word for gap, word in sorted((distance(low, v), v) for v in near) if gap <= 1.0]


# --- 3. meaning as the fallback --------------------------------------------------

#: Example questions of each kind, read when no rule did. Several wordings
#: each, so the nearest example is about the asking, not the subject.
EXAMPLES: dict[str, tuple[str, ...]] = LazyTable("noise_examples.json", lambda d: {k: tuple(v) for k, v in d.items()})

#: How close a question must come to an example, and by how much nearer to
#: one kind than the next, before it is given that kind.
TRIGRAM_FLOOR = 0.36
EMBED_FLOOR = 0.62
MARGIN = 0.06


def _trigrams(text: str) -> Counter:
    padded = f"  {re.sub(r'[^a-z ]', '', text.lower())}  "
    return Counter(padded[i : i + 3] for i in range(len(padded) - 2))


def _cosine(a: Counter, b: Counter) -> float:
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


_EXAMPLE_GRAMS: dict[str, list[Counter]] = {}


def _example_grams() -> dict[str, list[Counter]]:
    """The examples' trigrams, built at the first question that needs them."""
    if not _EXAMPLE_GRAMS:
        _EXAMPLE_GRAMS.update({kind: [_trigrams(e) for e in examples] for kind, examples in EXAMPLES.items()})
    return _EXAMPLE_GRAMS
_EMBED_CACHE: dict[int, dict[str, list[list[float]]]] = {}


def _vector_cosine(a, b) -> float:  # noqa: ANN001
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def guess_kind(asking: str, embed=None) -> str | None:  # noqa: ANN001
    """The kind of question `asking` is nearest to, or None when none is
    clearly nearest. `asking` is the question less its subject words, so
    "the date of the dentist" is compared as "the date of the". With
    `embed` (the embedder's `embed_many`), by cosine of meaning; without,
    by character trigrams."""
    text = (asking or "").strip()
    if len(text) < 3:
        return None
    scores: dict[str, float] = {}
    floor = TRIGRAM_FLOOR
    if embed is not None:
        try:
            cache = _EMBED_CACHE.get(id(embed))
            if cache is None:
                cache = {kind: embed(list(examples)) for kind, examples in EXAMPLES.items()}
                _EMBED_CACHE[id(embed)] = cache
            vector = embed([text])[0]
            scores = {kind: max(_vector_cosine(vector, v) for v in vectors) for kind, vectors in cache.items()}
            floor = EMBED_FLOOR
        except Exception:  # noqa: BLE001 - meaning is a fallback; trigrams stand in
            scores = {}
            floor = TRIGRAM_FLOOR
    if not scores:
        grams = _trigrams(text)
        scores = {kind: max(_cosine(grams, g) for g in examples) for kind, examples in _example_grams().items()}
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    if ranked[0][1] < floor or (len(ranked) > 1 and ranked[0][1] - ranked[1][1] < MARGIN):
        return None
    return ranked[0][0]


#: The Guide reads a question through this (`act_registry.repair`).
act_registry.repair = repair


#: A catch-up asked with no window ("hey what's been happening?", "what have I
#: been up to", "catch me up", "what did I miss"): the past week's recap. Whole
#: question only, so "catch me up on Harbor" stays a recall and "whats
#: happening" alone (small talk, `intent`) and "what's coming up" (the agenda)
#: are not it; "been" or "lately" is what makes "happening" past.
CATCH_LEAD = lazy_compile(r"^(?:(?:hey|hi|hello|hiya|yo|so|ok|okay|well|um)\b[ ,!]*)+", re.I)
_CATCH_UP = lazy_compile(
    r"^(?:(?:what|whats)(?: has| have)? been (?:happening|going on)(?: (?:lately|recently|so far|these days))?"
    r"|(?:what|whats)(?: is| has)? (?:happening|going on|happened) (?:lately|recently|these days)"
    r"|(?:what|whats)(?: have| has| did)? (?:i|we) (?:been (?:up to|doing)|miss(?:ed)?)"
    r"|(?:catch me up|bring me up to speed|fill me in|catch us up))(?: please)?$"
)


def catching_up(question: str) -> bool:
    """Whether the whole question is a catch-up with no window and no subject."""
    text = CATCH_LEAD.sub("", (question or "").strip().lower().replace("\u2019", "'"))
    text = " ".join(re.sub(r"[^a-z' ]", " ", text).replace("'s", "s").replace("'", "").split())
    return bool(text) and len(text) <= 60 and bool(_CATCH_UP.match(text))
