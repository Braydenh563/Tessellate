"""A language named as a property of a note (INBOX 1490, the owner, 2026-10-31).

"japanese", "japanese note" and "I have a note written in japanese", with a
note in Japanese script in the notebook, answered with a failed web search:
nothing read a language as something a note can be. A language is found by
its script (Unicode ranges) and, for the Latin-script ones, by a cheap check
of how many of a note's words are that language's everyday words and not
English ones. No model, no download, no network.

`asked` reads the message ("japanese note", "my note in Japanese", "notes
written in french", "the chinese one", a bare "japanese"); a message about
the language itself ("how do you say hello in japanese", "learn japanese")
is not one. `notes_in` lists the notes in that language.
"""

from __future__ import annotations

import re

#: Script languages: the character ranges that make one, and how a note must
#: use them. Japanese is any kana; Chinese is Han with no kana (Han alone is
#: ambiguous, and a note with kana is Japanese).
_SCRIPTS: dict[str, str] = {
    "kana": "぀-ヿㇰ-ㇿ",
    "han": "㐀-䶿一-鿿",
    "hangul": "ᄀ-ᇿ㄰-㆏가-힯",
    "cyrillic": "Ѐ-ӿ",
    "arabic": "؀-ۿݐ-ݿ",
    "hebrew": "֐-׿",
    "greek": "Ͱ-Ͽἀ-῿",
    "thai": "฀-๿",
    "devanagari": "ऀ-ॿ",
}
_RANGES = {name: re.compile(f"[{chars}]") for name, chars in _SCRIPTS.items()}
#: A language the script alone names (several share one: Cyrillic is Russian,
#: Ukrainian and others; the one the person names matches the script).
_SCRIPT_OF = {
    "korean": "hangul", "russian": "cyrillic", "ukrainian": "cyrillic", "bulgarian": "cyrillic", "arabic": "arabic", "hebrew": "hebrew",
    "greek": "greek", "thai": "thai", "hindi": "devanagari", "nepali": "devanagari", "marathi": "devanagari",
}
#: Latin-script languages, by their everyday words.
_WORDS: dict[str, frozenset[str]] = {
    "french": frozenset("le la les un une des du de et est sont je tu il elle nous vous ils elles ce cette ces pour dans sur avec pas que qui mais ou où au aux mon ma mes ton son sa ses très être avoir fait comme plus bien aussi".split()),
    "spanish": frozenset("el la los las un una unos unas y es son yo tú él ella nosotros ustedes ellos de del que en con por para pero como más muy está estoy tengo hoy mi mis su sus se lo al no sí también".split()),
    "german": frozenset("der die das den dem ein eine einen und ist sind ich du er sie es wir ihr nicht mit für auf von zu im in aber oder auch sehr heute mein meine dein wie wenn dass war haben habe".split()),
    "italian": frozenset("il lo la gli le un una e è sono io tu lui lei noi voi loro di del della che in con per ma come più molto oggi mio mia non anche ho ha sono sì".split()),
    "portuguese": frozenset("o a os as um uma e é são eu tu ele ela nós vocês eles de do da que em com por para mas como mais muito hoje meu minha não também está estou tenho".split()),
    "dutch": frozenset("de het een en is zijn ik jij hij zij wij jullie ze niet met voor op van te in maar of ook zeer vandaag mijn je dat die wat hebben heb".split()),
}
_ENGLISH = frozenset("the a an and is are was were i you he she it we they this that these those of to in on for with not but or also very my your have has had be been what how do does did at by from as".split())

_LANGS = sorted({*_SCRIPT_OF, "japanese", "chinese", *_WORDS}, key=len, reverse=True)
_LANG = "(?P<lang>" + "|".join(_LANGS) + ")"
#: Said about a language, not about a note: translation, learning, speaking.
_ABOUT_THE_LANGUAGE = re.compile(
    r"\b(?:translat\w*|how (?:do|would|can|to) (?:you|i|we) say|how to say|word for|words for|learn\w*|lessons?|course|speak\w*|fluent|restaurants?|food|recipes?|"
    r"meaning of|what does .{1,30} mean|mean in|say in|phrase\w*|pronounc\w*|alphabet|grammar|dictionary|anime|manga|culture|history)\b",
    re.I,
)
_NOTE_NOUN = r"(?:notes?|nore|noet|entr(?:y|ies)|ones?|texts?|writing|stuff|bits?|files?|docs?|documents?|pages?)"
_SAYS = [
    #: "written in japanese", "typed in french"
    re.compile(rf"\b(?:written|writing|typed|saved|jotted|done|made|wrote)\s+in\s+(?:the\s+)?{_LANG}\b", re.I),
    #: "japanese note", "the chinese one", "my french notes"
    re.compile(rf"\b{_LANG}\s+{_NOTE_NOUN}\b", re.I),
    #: "notes in japanese", "the note that is in french"
    re.compile(rf"\b{_NOTE_NOUN}\s+(?:(?:(?:that|which)\s+)?(?:is|are)\s+|i\s+(?:wrote|made|have|typed)\s+)?in\s+(?:the\s+)?{_LANG}\b", re.I),
    #: just the language
    re.compile(rf"^\W*(?:the\s+)?{_LANG}\W*$", re.I),
]


def asked(message: str) -> str:
    """The language a message names as a property of a note, lowercase, or ""."""
    text = " ".join((message or "").split())
    if not text or _ABOUT_THE_LANGUAGE.search(text):
        return ""
    for pattern in _SAYS:
        found = pattern.search(text)
        if found:
            return found.group("lang").lower()
    return ""


def _letters(text: str) -> list[str]:
    return re.findall(r"[^\W\d_]+", text.lower())


def _share(text: str, name: str) -> tuple[int, float]:
    """(characters of a script, their share of the note's letters)."""
    letters = sum(len(w) for w in _letters(text))
    count = len(_RANGES[name].findall(text))
    return count, (count / letters if letters else 0.0)


def _in_script(text: str, language: str) -> bool:
    if language == "japanese":
        kana, _ = _share(text, "kana")
        marks = kana + len(_RANGES["han"].findall(text))
        return kana >= 2 and marks / max(1, sum(len(w) for w in _letters(text))) >= 0.25
    if language == "chinese":
        han, share = _share(text, "han")
        return han >= 3 and share >= 0.25 and not _RANGES["kana"].search(text)
    count, share = _share(text, _SCRIPT_OF[language])
    return count >= 3 and share >= 0.25


def _in_words(text: str, language: str) -> bool:
    """The language whose everyday words most of the note is made of: more of
    them than English and than any other Latin-script language (Italian and
    Spanish share many)."""
    words = _letters(text)
    if len(words) < 4:
        return False
    score = {name: sum(1 for w in words if w in known) for name, known in _WORDS.items()}
    own = score[language]
    rivals = max([sum(1 for w in words if w in _ENGLISH), *(n for name, n in score.items() if name != language)])
    return own >= 3 and own / len(words) >= 0.15 and own > rivals


def is_in(text: str, language: str) -> bool:
    """Whether a note's text is in `language`: its script, or its everyday words."""
    if language in _WORDS:
        return _in_words(text, language)
    if language == "japanese" or language == "chinese" or language in _SCRIPT_OF:
        return _in_script(text, language)
    return False


def notes_in(rows: list[tuple[int, str]], language: str) -> list[tuple[int, str]]:
    """The `(id, content)` rows in `language`, in the order given."""
    return [(i, c) for i, c in rows if is_in(c or "", language)]


def label(language: str) -> str:
    return language.capitalize()
