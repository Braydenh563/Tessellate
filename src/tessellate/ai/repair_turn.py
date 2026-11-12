"""A correction turn, read by class (INBOX 1668 b, the owner: "not what ai
asked" was searched for and answered "These notes do not mention asked").

"Not what I asked", "that's wrong", "you misunderstood", "no, that's not it",
"nt what i askd": a short message that says the last reply missed. It is
repair, never a search; the route owns the miss and asks again
(`composer_social.repair`). A message with anything else in it ("that's wrong,
I was in Paris in 2019") is a statement, not this. Words are matched after
typo repair against a closed vocabulary, so a new phrasing needs no new row.
"""

from __future__ import annotations

import difflib
from tessellate.core.lazyre import lazy_compile

#: The words a correction is made of; any other word makes the message not one.
_VOCAB = frozenset(
    """not what i asked ask asking meant mean said say saying want wanted need needed after for about no nope nah that thats this it its is was are
    wrong incorrect right correct you youre your got get me misunderstood misunderstand understand understood misread misheard mistaken
    didnt dont did do wasnt isnt aint never really totally completely just so very at all answer reply response answered
    my sorry but again mate dude lol please pls the think thought try""".split()
)
#: Typos that are too short for a fuzzy match.
_SHORT = {"nt": "not", "ai": "i", "u": "you", "wat": "what", "wht": "what", "wut": "what", "wot": "what", "im": "i", "ur": "your", "dnt": "dont", "wrng": "wrong", "tht": "that", "thts": "thats", "isnt": "not", "wasnt": "not", "aint": "not", "arent": "not"}
#: What "what I ..." is followed by, and the verbs of "you ...".
_ASKED = frozenset("asked ask asking meant mean said say saying want wanted need needed".split())
_TRIGGER = frozenset("wrong incorrect misunderstood misread misheard mistaken".split())
_LEAD = frozenset("no nope nah sorry but".split())
_QUESTION_WORD = frozenset("is are was did do does why how what who when where can could should".split())
_WORDS = lazy_compile(r"[a-z]+")


def _normal(message: str) -> list[str]:
    """The words of `message`, apostrophes dropped and typos mended to the
    vocabulary; a word near none stays as it is."""
    words = _WORDS.findall((message or "").lower().replace("’", "'").replace("'", ""))
    out = []
    for word in words:
        word = _SHORT.get(word, word)
        #: "my mistake" owns a slip; it is not "mistaken" (a complaint).
        if word not in _VOCAB and len(word) >= 4 and word not in ("mistake", "mistakes"):
            close = difflib.get_close_matches(word, _VOCAB, n=1, cutoff=0.8)
            #: Two letters swapped ("waht", "taht") score under the cutoff.
            close = close or [v for v in _VOCAB if len(v) == len(word) and sorted(v) == sorted(word) and sum(a != b for a, b in zip(v, word)) == 2]
            word = close[0] if close else word
        out.append(word)
    return out


def _says_not_what_asked(said: set[str]) -> bool:
    """"Not what I asked / meant / said", "I didn't ask that", "you didn't understand"."""
    if {"not", "what", "i"} <= said and said & _ASKED:
        return True
    if {"dont", "think"} <= said and said & {"right", "correct", "it"}:
        return True
    return bool(said & {"didnt", "never", "dont"}) and (
        ("i" in said and bool(said & _ASKED)) or ("you" in said and bool(said & {"understand", "understood", "get"}))
    )


def _says_wrong(words: list[str], said: set[str]) -> bool:
    """"That's wrong", "you got it wrong", "you misunderstood me", "not right", "not it"."""
    if words[0] in _QUESTION_WORD:
        return False
    return bool(said & _TRIGGER) or ("not" in said and bool(said & {"right", "correct", "it"})) or words == ["i", "meant"]


def is_repair(message: str) -> bool:
    """Whether `message` is a correction turn: it says the last reply missed
    and says nothing else."""
    if not message or len(message) > 80:
        return False
    words = _normal(message)
    if not words or len(words) > 8 or not set(words) <= _VOCAB:
        return False
    while words[:1] and words[0] in _LEAD and len(words) > 1:
        words = words[1:]
    said = set(words)
    return _says_not_what_asked(said) or _says_wrong(words, said)


def is_refusal(message: str) -> bool:
    """"No, I don't want that", "I didn't ask for that": said after a reply
    that asked something, the answer to it and not a complaint about an
    earlier reply. It names no miss ("what", "wrong", "misunderstood")."""
    words = _normal(message)
    return is_repair(message) and not (set(words) & ({"what", "meant", "said", "again", "try"} | _TRIGGER))
