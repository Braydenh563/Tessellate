"""A name typed one slip off ("hanna" for Hannah) is read as the note's name (R9-14).

The speller changes only words of the dictionary; a name is not in it. The names a notebook writes with a capital
and never without ("Hannah", "Marek") are the vocabulary here, so a common word is never "corrected" into one,
and only a subject word is read (after about, is, of, for, ..., or last)."""

from __future__ import annotations


from tessellate.ai import common_words, common_words_more, question_noise
from tessellate.core.lazyre import lazy_compile

#: A word after one of these (or the last word) can be the subject asked about.
_BEFORE_SUBJECT = frozenset({"about", "is", "of", "for", "on", "does", "did", "was", "with", "from", "to", "who", "whos"})
_POSSESSIVE = frozenset({"my", "the", "our", "your"})
_CAPITAL = lazy_compile(r"\b[A-Z][a-z]{3,}\b")
_LOWER = lazy_compile(r"\b[a-z]{3,}\b")


#: Everyday English: a capital on one of these, at the start of a sentence, is only its place.
_ORDINARY = common_words.WORDS | common_words_more.MORE


def _opens_a_sentence(text: str, at: int) -> bool:
    """Whether the word at `at` starts the text or a sentence, line or list item: its capital is its place."""
    while at > 0 and text[at - 1] == " ":
        at -= 1
    return at == 0 or text[at - 1] in ".!?:\n#*|>-"


def _heading(note: dict) -> str:
    """The note's one-word name, lower case: its title, or the "# " line it opens with."""
    first = str(note.get("title") or "").strip() or str(note.get("content") or "").lstrip().split("\n", 1)[0]
    return first.lstrip("# ").strip().lower()


def names_of(notes: list[dict]) -> frozenset[str]:
    """The names the notes write with a capital and never without, lower case. A word that is capitalised only
    for opening a sentence is a name only when it is not an ordinary word ("Pick up the parcel" is not Pick)."""
    text = "\n".join(f"{n.get('title') or ''}\n{n.get('content') or ''}" for n in notes or ())
    capital = {
        m.group(0).lower() for m in _CAPITAL.finditer(text)
        if not _opens_a_sentence(text, m.start()) or m.group(0).lower() not in _ORDINARY
    }
    #: A one-word title ("Budget", "Shopping") is the note's name whatever else says the word (F8).
    titles = {t for n in notes or () if (t := _heading(n)).isalpha() and len(t) >= 4}
    return (frozenset(capital) - frozenset(_LOWER.findall(text))) | titles


def respell(question: str, names: frozenset[str], fixed: list | None = None) -> str:
    """`question` with a subject word that is one slip from one of `names` put right; `fixed` gets
    (typed, chosen) as the speller's repairs do, which is what lets the answer say how it read the question."""
    if not names or not question:
        return question
    tokens = question.split(" ")
    for i, token in enumerate(tokens):
        word = token.strip("?.!,;:").lower()
        last = all(not t.strip("?.!,;:") for t in tokens[i + 1:])
        #: "my shoping list": the word before a bare "list" is the note's name as much as the last word is (F8).
        listed = i > 0 and i + 1 < len(tokens) and tokens[i + 1].strip("?.!,;:").lower() == "list" and tokens[i - 1].lower() in _POSSESSIVE
        if len(word) < 4 or not word.isalpha() or word in names or not (last or listed or (i and tokens[i - 1].lower() in _BEFORE_SUBJECT)):
            continue
        chosen = question_noise.nearest(word, names)
        if chosen:
            tokens[i] = token.lower().replace(word, chosen)
            if fixed is not None:
                fixed.append((token, tokens[i]))
    return " ".join(tokens)

