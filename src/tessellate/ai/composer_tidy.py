"""Tidy and formal passes for the Writing room with no model (INBOX 1488).

The owner, 2026-10-31, on thoughts "I am japanese" that came back "I am
japanese." with every chip still on offer: "if certain features are useless
or not available with no ai they shouldnt be an option". These are two of the
passes the composer does well by rule, and the check that keeps any pass from
handing the input back as if it had done something.

- **Tidy**: the proofreader's spelling, capitals and "I" (`proofread`), the
  names of languages and nationalities raised, a missing apostrophe put back
  ("dont"), a doubled word cut, and each prose line ended with a full stop.
- **Formal**: contractions spelled out, slang swapped for the plain word,
  fillers out, then tidied. Nothing is added.

Both only rearrange or respell what the person wrote.
"""

from __future__ import annotations

import re

#: Raised wherever they stand as a word of their own. "polish" and "turkey"
#: are left out: they are as often a verb and a bird.
_NAMES = (
    "english spanish french german italian portuguese dutch swedish norwegian danish finnish greek russian ukrainian "
    "arabic hindi chinese japanese korean vietnamese indonesian thai hebrew persian latin irish scottish welsh "
    "american british canadian australian mexican brazilian indian african asian european christian muslim jewish "
    "buddhist hindu catholic"
).split()
_NAME_RE = re.compile(r"\b(" + "|".join(_NAMES) + r")\b", re.I)

#: A contraction typed without its apostrophe. "ill", "well", "its", "were"
#: and "id" are words of their own and are never touched.
_APOSTROPHES = {
    "dont": "don't", "doesnt": "doesn't", "didnt": "didn't", "isnt": "isn't", "arent": "aren't", "wasnt": "wasn't",
    "werent": "weren't", "cant": "can't", "wont": "won't", "couldnt": "couldn't", "wouldnt": "wouldn't",
    "shouldnt": "shouldn't", "havent": "haven't", "hasnt": "hasn't", "hadnt": "hadn't", "im": "I'm", "ive": "I've",
    "youre": "you're", "theyre": "they're", "thats": "that's", "whats": "what's", "theres": "there's",
    "youve": "you've", "weve": "we've", "theyve": "they've", "youll": "you'll", "theyll": "they'll",
}
_APOSTROPHE_RE = re.compile(r"(?<![\w'])(" + "|".join(_APOSTROPHES) + r")(?![\w'])", re.I)
_DOUBLED = re.compile(r"\b(\w{2,})(\s+\1\b)+", re.I)
#: A code fence and what is inside it is never touched.
_FENCE = re.compile(r"^\s*(```|~~~)")
_BULLET = re.compile(r"^(\s*(?:[-*+]|\d{1,3}[.)])\s+(?:\[[ xX]\]\s+)?)(\S.*)$")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s")

_CONTRACTIONS = {
    "don't": "do not", "doesn't": "does not", "didn't": "did not", "isn't": "is not", "aren't": "are not",
    "wasn't": "was not", "weren't": "were not", "can't": "cannot", "won't": "will not", "couldn't": "could not",
    "wouldn't": "would not", "shouldn't": "should not", "haven't": "have not", "hasn't": "has not",
    "hadn't": "had not", "i'm": "I am", "i've": "I have", "i'll": "I will", "i'd": "I would", "you're": "you are",
    "you've": "you have", "you'll": "you will", "we're": "we are", "we've": "we have", "we'll": "we will",
    "they're": "they are", "they've": "they have", "they'll": "they will", "it's": "it is", "that's": "that is",
    "what's": "what is", "there's": "there is", "let's": "let us", "he's": "he is", "she's": "she is",
}
_CONTRACTION_RE = re.compile(r"(?<![\w'])(" + "|".join(re.escape(c) for c in _CONTRACTIONS) + r")(?![\w'])", re.I)
#: Slang and loose phrases, with the word a formal reader expects.
_SLANG = {
    "gonna": "going to", "wanna": "want to", "gotta": "have to", "kinda": "somewhat", "sorta": "somewhat",
    "yeah": "yes", "yep": "yes", "nope": "no", "ok": "acceptable", "okay": "acceptable", "kids": "children",
    "guys": "everyone", "stuff": "things", "thanks": "thank you", "asap": "as soon as possible",
    "a lot of": "many", "lots of": "many", "pretty good": "good", "get rid of": "remove", "find out": "learn",
    "look into": "investigate", "come up with": "devise", "figure out": "determine", "sort out": "resolve",
    "tell": "inform", "ask for": "request", "need to": "must", "so": "therefore",
}
#: "tell", "need to" and "so" change meaning in too many places to swap blind.
for _loose in ("tell", "need to", "so", "ask for", "stuff"):
    del _SLANG[_loose]
_SLANG_RE = re.compile(r"(?<![\w'])(" + "|".join(re.escape(s) for s in sorted(_SLANG, key=len, reverse=True)) + r")(?![\w'])", re.I)


def _like(word: str, made: str) -> str:
    """`made` in the case `word` was typed in."""
    if word.isupper() and len(word) > 1:
        return made.upper()
    return made[:1].upper() + made[1:] if word[:1].isupper() else made


def same(a: str, b: str) -> bool:
    """Two texts that differ only in spacing or a final full stop: a pass
    whose result is this has done nothing worth showing (a capital or a
    corrected letter is a change)."""
    def fold(text: str) -> str:
        return re.sub(r"[\s]+", " ", text).strip().rstrip(".")

    return fold(a) == fold(b)


def _fix_line(line: str) -> str:
    line = _NAME_RE.sub(lambda m: m.group(1).capitalize(), line)
    line = _APOSTROPHE_RE.sub(lambda m: _like(m.group(1), _APOSTROPHES[m.group(1).lower()]), line)
    return _DOUBLED.sub(lambda m: m.group(1), line)


def _ended(line: str) -> str:
    """A prose line with its full stop: a line already ended, or one that is
    a label, a question or a single word, is left as typed."""
    body = line.rstrip()
    if len(body.split()) < 2 or body[-1:] in ".!?:;)\"'`*" or body.endswith("..."):
        return line
    return f"{body.rstrip(',')}." + line[len(body):]


def _segments(text: str) -> list[tuple[bool, list[str]]]:
    """The lines as (is code, lines) runs, a fence line belonging to its code."""
    runs: list[tuple[bool, list[str]]] = []
    fenced = False
    for line in text.split("\n"):
        opens = bool(_FENCE.match(line))
        code = fenced or opens
        if opens:
            fenced = not fenced
        if runs and runs[-1][0] == code:
            runs[-1][1].append(line)
        else:
            runs.append((code, [line]))
    return runs


def _tidy_lines(lines: list[str]) -> list[str]:
    from tessellate.ai import proofread

    out: list[str] = []
    for line in proofread.proofread("\n".join(lines))[0].split("\n"):
        item = _BULLET.match(line)
        if not line.strip() or _HEADING.match(line):
            out.append(line)
        elif item:
            fixed = _fix_line(item.group(2))
            out.append(item.group(1) + fixed[:1].upper() + fixed[1:])
        else:
            out.append(_ended(_fix_line(line)))
    return out


def fixed(text: str) -> str:
    """The spelling and capitals of one run of prose, its full stops left."""
    from tessellate.ai import proofread

    return _fix_line(proofread.proofread(text)[0])


def tidy(text: str) -> str:
    """The text spelt, capitalised and ended as a careful typist would leave
    it. Lines, lists, headings and code stay where they were."""
    done: list[str] = []
    for code, lines in _segments((text or "").replace("\r\n", "\n")):
        done.extend(lines if code else _tidy_lines(lines))
    return "\n".join(done)


def formally(text: str) -> str:
    """`tidy`, with contractions spelled out and slang swapped for the word a
    formal reader expects, fillers and wordy phrases out."""
    from tessellate.ai import composer_write as cw

    out: list[str] = []
    for code, lines in _segments(tidy(text)):
        for line in lines:
            if code or _HEADING.match(line) or not line.strip():
                out.append(line)
                continue
            line = _CONTRACTION_RE.sub(lambda m: _like(m.group(1), _CONTRACTIONS[m.group(1).lower()]), line)
            line = _SLANG_RE.sub(lambda m: _like(m.group(1), _SLANG[m.group(1).lower()]), line)
            out.append(_formal_line(line, cw))
    return "\n".join(out)


def _formal_line(line: str, cw) -> str:  # noqa: ANN001
    """Fillers and wordy phrases out of one line, its first letter raised."""
    said = " ".join(cw.concise(cw._FILLERS.sub("", line)).split())
    said = re.sub(r" ([,.;:!?])", r"\1", said)
    lead = re.match(r"\s*", line).group(0)
    marker = _BULLET.match(said)
    if marker:
        return lead + marker.group(1).lstrip() + marker.group(2)[:1].upper() + marker.group(2)[1:]
    return lead + said[:1].upper() + said[1:]
