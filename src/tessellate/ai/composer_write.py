"""The Writing room's passes with no model, by plain rule (INBOX 1466).

The owner, 2026-10-31: "can the writing room be made more useful with the
composer?? can the composer be able to do some of it reasonably well?"
CHAT_PLAN decision 75: with a model on, the model does the work; with none,
the composer does what it can do well and says plainly what it cannot.

What it can do well is what the words already hold, moved around:

- **Prose to bullets**: one sentence (or one `;` clause) a bullet, the
  fillers ("basically", "in order to") trimmed, headings kept.
- **Bullets to prose**: each bullet a capitalised sentence, joined with
  connectives ("First", "Then", "Finally" for steps; "Also" for a list).
- **Say it plainly**: a table of plain words for long ones, the fillers
  trimmed, a sentence over `LONG_WORDS` split at its middle joint.
- **Shorter**: fillers and repeated sentences dropped, then the sentences
  whose words the rest of the text uses least, keeping about two thirds.
- **Add a summary**: the most central sentence or two, under the title.
- **Write up my notes**: the thoughts tidied into sentences, then each chosen
  note under its name and when it was written (`composer_frame.note_title`,
  `realise.relative_day`), its key sentences as bullets rather than its
  opening pasted whole.
- **A diagram**: asked for here (`shape="diagram"`), drawn by
  `composer_mermaid.drafted`, which reads this module and not the reverse.

Carrying on and translating need a model and say so (`NEEDS_MODEL`). Nothing
here invents a fact: every word out is one of the person's, or a joining word.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date

#: A sentence longer than this many words is split at its middle joint.
LONG_WORDS = 24
#: Shorter keeps about this share of a text's sentences, and never fewer than
#: `SHORT_KEEP_MIN` (a three-sentence draft keeps two).
SHORT_SHARE = 0.65
SHORT_KEEP_MIN = 2
#: Key sentences per note in a write-up, and words per sentence before a cut.
WRITE_UP_POINTS = 3
SUMMARY_SENTENCES = 2
SUMMARY_MIN = 3
#: "Key words" under a summary are worth a line only past this many sentences.
KEY_WORDS_MIN = 5

#: The kinds that need a model, with the one line said instead of a draft.
NEEDS_MODEL = {
    "continue": "Carrying on in your voice needs a model. Connect one in Settings, Models, then press Draft again. Your draft is untouched.",
    "translate": "Translating needs a model. Connect one in Settings, Models, then press Draft again. Your text is untouched.",
    "rewrite": "A new voice needs a model; with none, Plain is the voice that works. Connect one in Settings, Models.",
    "revise": "Folding thoughts into a draft needs a model. Connect one in Settings, Models, or pick Draft a note to add them below.",
    "refine": "With no model, Refine takes: shorter, add a summary, as bullets, as a list, as prose, plain, formal, tidy up or a diagram. Connect a model in Settings, Models for anything else.",
}

#: One line for a pass that would hand the text back as it came (INBOX 1488):
#: said instead of a draft that looks like work and is not.
NOTHING_TO_DO = {
    "bullets": "Nothing to split: the text is already bullets, or one short line.",
    "expand": "No bullets to join: the text is already prose. Write the points as a list first, or pick Tidy.",
    "plain": "Nothing to swap: the words are already plain.",
    "shorter": "Already short: there is no filler or repeat to cut.",
    "summary": "Too short to sum up: a summary needs three sentences or more.",
    "note": "Nothing to write up: add thoughts or notes (Use notes) to work from, or pick Tidy for a spelling pass.",
    "tidy": "Nothing to tidy: the spelling, capitals and full stops look right.",
    "formal": "Already formal: no contractions or slang to change.",
}

#: Fillers: dropped wherever they stand as words of their own.
_FILLERS = re.compile(
    r"\b(?:basically|actually|literally|really|very|just|kind of|sort of|you know|i mean|"
    r"at the end of the day|needless to say|it goes without saying that|to be honest|honestly|obviously|"
    r"quite|pretty much|simply|totally|definitely)\b,?\s*",
    re.I,
)
#: Openers that join a sentence to the one before; a bullet stands alone.
_LEADS = re.compile(r"^(?:so|well|also|and|plus|anyway|ok|okay|right|now)\b,?\s+", re.I)

#: Long word or phrase -> plain one. Verbs carry their forms, so "utilised"
#: becomes "used" and "purchasing" "buying".
_PHRASES = {
    "in order to": "to", "prior to": "before", "subsequent to": "after", "in the event that": "if",
    "at this point in time": "now", "at the present time": "now", "due to the fact that": "because",
    "owing to the fact that": "because", "in spite of the fact that": "although", "with regard to": "about",
    "with respect to": "about", "in relation to": "about", "in regard to": "about", "a large number of": "many",
    "a great deal of": "much", "the majority of": "most", "in addition to": "as well as", "in addition": "also",
    "with the exception of": "except", "for the purpose of": "for", "on a daily basis": "daily",
    "on a regular basis": "regularly", "in the near future": "soon", "is able to": "can", "are able to": "can",
    "was able to": "could", "has the ability to": "can", "make a decision": "decide", "take into account": "consider",
}
_WORDS = {
    "approximately": "about", "assistance": "help", "sufficient": "enough", "numerous": "many",
    "regarding": "about", "additional": "extra", "individuals": "people", "individual": "person",
    "consequently": "so", "therefore": "so", "nevertheless": "still", "nonetheless": "still",
    "however": "but", "objective": "aim", "objectives": "aims", "residence": "home", "currently": "now",
    "subsequently": "later", "previously": "before", "frequently": "often", "immediately": "now",
    "commencement": "start", "termination": "end", "methodology": "method", "functionality": "features",
    "beneficial": "useful", "advantageous": "useful", "difficult": "hard", "inexpensive": "cheap",
    "sufficiently": "enough", "principal": "main", "primary": "main", "remainder": "rest",
    "whilst": "while", "amongst": "among", "upon": "on", "utilisation": "use", "utilization": "use",
}
#: (long verb forms) -> (plain forms), base, past, -ing, -s.
_VERBS = (
    (("utilise", "utilised", "utilising", "utilises"), ("use", "used", "using", "uses")),
    (("utilize", "utilized", "utilizing", "utilizes"), ("use", "used", "using", "uses")),
    (("commence", "commenced", "commencing", "commences"), ("start", "started", "starting", "starts")),
    (("initiate", "initiated", "initiating", "initiates"), ("start", "started", "starting", "starts")),
    (("terminate", "terminated", "terminating", "terminates"), ("end", "ended", "ending", "ends")),
    (("purchase", "purchased", "purchasing", "purchases"), ("buy", "bought", "buying", "buys")),
    (("endeavour", "endeavoured", "endeavouring", "endeavours"), ("try", "tried", "trying", "tries")),
    (("attempt", "attempted", "attempting", "attempts"), ("try", "tried", "trying", "tries")),
    (("facilitate", "facilitated", "facilitating", "facilitates"), ("help with", "helped with", "helping with", "helps with")),
    (("demonstrate", "demonstrated", "demonstrating", "demonstrates"), ("show", "showed", "showing", "shows")),
    (("indicate", "indicated", "indicating", "indicates"), ("show", "showed", "showing", "shows")),
    (("obtain", "obtained", "obtaining", "obtains"), ("get", "got", "getting", "gets")),
    (("require", "required", "requiring", "requires"), ("need", "needed", "needing", "needs")),
    (("ascertain", "ascertained", "ascertaining", "ascertains"), ("find out", "found out", "finding out", "finds out")),
    (("inform", "informed", "informing", "informs"), ("tell", "told", "telling", "tells")),
    (("modify", "modified", "modifying", "modifies"), ("change", "changed", "changing", "changes")),
    (("possess", "possessed", "possessing", "possesses"), ("have", "had", "having", "has")),
    (("request", "requested", "requesting", "requests"), ("ask for", "asked for", "asking for", "asks for")),
    (("assist", "assisted", "assisting", "assists"), ("help", "helped", "helping", "helps")),
    (("comprehend", "comprehended", "comprehending", "comprehends"), ("understand", "understood", "understanding", "understands")),
    (("accomplish", "accomplished", "accomplishing", "accomplishes"), ("do", "did", "doing", "does")),
    (("enquire", "enquired", "enquiring", "enquires"), ("ask", "asked", "asking", "asks")),
    (("inquire", "inquired", "inquiring", "inquires"), ("ask", "asked", "asking", "asks")),
    (("establish", "established", "establishing", "establishes"), ("set up", "set up", "setting up", "sets up")),
)
_PLAIN = {**_WORDS, **{long: plain for longs, plains in _VERBS for long, plain in zip(longs, plains)}}
_PHRASE_RE = re.compile(r"\b(" + "|".join(re.escape(p) for p in sorted(_PHRASES, key=len, reverse=True)) + r")\b", re.I)
_WORD_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in sorted(_PLAIN, key=len, reverse=True)) + r")\b", re.I)

#: The joints a long sentence is split at, best first.
_JOINTS = (";", ", but ", ", so ", ", and ", ", because ", ", which ")


class _Line:
    """A line pattern matched on the line with its trailing space cut off.

    The text is user-typed, so a pattern ending in `\\s*$` after `.*\\S` can
    backtrack polynomially on a long run of tabs; cutting the tail first and
    starting the text group on `\\S` leaves one way to match, so it is linear.
    """

    def __init__(self, pattern: str) -> None:
        self._rx = re.compile(pattern)

    def match(self, line: str) -> re.Match[str] | None:
        return self._rx.match(line.rstrip())


_HEADING = _Line(r"^\s{0,3}(#{1,6})\s+(\S.*)$")
_ITEM = _Line(r"^(\s*)(?:([-*+])|(\d{1,3})[.)])\s+(?:\[[ xX]\]\s+)?(\S.*)$")
#: A full stop that is not a sentence's end: a title, an initial, "e.g.".
_ABBREVIATIONS = ("e.g.", "i.e.", "etc.", "vs.", "mr.", "mrs.", "ms.", "dr.", "st.", "approx.")
_STOP = frozenset(
    "the a an and or but of to in on at for with from by is are was were be been it its this that these those "
    "i we you he she they my our your their me us them as so if then than there here not no do does did have has had "
    "will would can could should may might must just also very really about into over up out what when where who how".split()
)


@dataclass
class Pass:
    """One composed pass: the text, the line the status says, and its kind."""

    text: str
    message: str = ""
    shape: str = ""


# --- reading -------------------------------------------------------------------


def sentences(text: str) -> list[str]:
    """The sentences of a run of prose, in order, as written."""
    folded = " ".join((text or "").split())
    if not folded:
        return []
    out: list[str] = []
    buf = ""
    for piece in re.split(r"(?<=[.!?])\s+", folded):
        buf = f"{buf} {piece}".strip() if buf else piece
        if buf.split()[-1].lower() not in _ABBREVIATIONS and not re.search(r"\b[A-Z]\.$", buf):
            out.append(buf)
            buf = ""
    if buf:
        out.append(buf)
    return [s for s in out if s.strip()]


def _blocks(text: str) -> list[tuple[str, list[str]]]:
    """The text as ("heading" | "list" | "prose", lines) blocks, in order."""
    blocks: list[tuple[str, list[str]]] = []
    for line in (text or "").replace("\r\n", "\n").split("\n"):
        kind = "heading" if _HEADING.match(line) else "list" if _ITEM.match(line) else "prose" if line.strip() else ""
        if not kind:
            blocks.append(("", []))
        elif blocks and blocks[-1][0] == kind and kind != "heading":
            blocks[-1][1].append(line)
        else:
            blocks.append((kind, [line]))
    return [(k, lines) for k, lines in blocks if k]


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9']+", text.lower()) if w not in _STOP and len(w) > 2]


def _same(a: str, b: str) -> bool:
    """Two sentences that say the same thing (most of their words shared)."""
    wa, wb = set(_words(a)), set(_words(b))
    return bool(wa and wb) and len(wa & wb) / len(wa | wb) >= 0.7


# --- sentences, tidied ------------------------------------------------------------


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def _decap(text: str) -> str:
    """Lower the first letter unless the first word is a name, "I" or an acronym."""
    first = text.split(" ", 1)[0]
    if first == "I" or first.startswith("I'") or (len(first) > 1 and first[1:].lower() != first[1:]):
        return text
    return text[:1].lower() + text[1:]


def trim(text: str) -> str:
    """A sentence without its fillers or a joining opener, spaces folded."""
    out = _FILLERS.sub("", text)
    out = _LEADS.sub("", out.strip())
    out = re.sub(r" ([,.;:!?])", r"\1", " ".join(out.split()))  # single spaces only after the fold
    return _cap(out.strip(" ,")) if out.strip(" ,") else text.strip()


def _ended(text: str) -> str:
    text = text.rstrip()
    return text if text[-1:] in ".!?:" else f"{text.rstrip(',;')}."


def _matched_case(word: str, plain: str) -> str:
    if word.isupper() and len(word) > 1:
        return plain.upper()
    return _cap(plain) if word[:1].isupper() else plain


def concise(text: str) -> str:
    """`text` with its wordy phrases shortened ("in order to" to "to")."""
    return _PHRASE_RE.sub(lambda m: _matched_case(m.group(0), _PHRASES[m.group(0).lower()]), text)


def plain(text: str) -> str:
    """`text` with the plain-word table applied, case kept."""
    return _WORD_RE.sub(lambda m: _matched_case(m.group(0), _PLAIN[m.group(0).lower()]), concise(text))


def _split_long(sentence: str) -> list[str]:
    """A sentence over `LONG_WORDS` cut at the joint nearest its middle,
    both halves at least six words; shorter ones come back whole."""
    words = sentence.split()
    if len(words) <= LONG_WORDS:
        return [sentence]
    middle = len(sentence) // 2
    best = None
    for joint in _JOINTS:
        for found in re.finditer(re.escape(joint), sentence):
            left, right = sentence[: found.start()], sentence[found.end():]
            if len(left.split()) >= 6 and len(right.split()) >= 6:
                distance = abs(found.start() - middle)
                if best is None or distance < best[0]:
                    best = (distance, left, right, joint)
    if best is None:
        return [sentence]
    _distance, left, right, joint = best
    lead = {", but ": "But ", ", so ": "So ", ", because ": "That is because ", ", which ": "This "}.get(joint, "")
    second = lead + (_decap(right.strip()) if lead else _cap(right.strip()))
    return [_ended(left.strip()), *_split_long(_ended(second))]


# --- the passes ---------------------------------------------------------------------


def _bullet_items(line: str) -> list[str]:
    """One prose line as bullet texts: a sentence each, a `;` clause each,
    wordy phrases shortened, a repeat or a sentence that says nothing out."""
    items: list[str] = []
    for sentence in sentences(line):
        for part in re.split(r";\s+", sentence):
            part = trim(concise(part)).rstrip(".")
            if (len(part.split()) >= 2 or part.endswith("?")) and not _hedge(part) and not any(_same(part, x) for x in items):
                items.append(part)
    return items


def to_bullets(text: str) -> str:
    """Prose closed up into bullets, headings and existing lists kept."""
    out: list[str] = []
    for kind, lines in _blocks(text):
        if kind == "prose":
            items = [item for line in [" ".join(lines)] for item in _bullet_items(line)]
            out.append("\n".join(f"- {item}" for item in items))
        else:
            out.append("\n".join(lines))
    return "\n\n".join(block for block in out if block.strip())


_STEP_JOINS = ("First, ", "Then ", "After that, ", "Next, ", "Then ")
_LIST_JOINS = ("", "Also, ", "", "On top of that, ", "")


def _list_prose(lines: list[str]) -> str:
    """A list block as sentences: each top item a sentence, its sub-items
    sentences after it with no connective."""
    groups: list[tuple[str, list[str], bool]] = []
    base = min(len(_ITEM.match(line).group(1).expandtabs(4)) for line in lines)
    for line in lines:
        found = _ITEM.match(line)
        text = trim(found.group(4))
        if len(found.group(1).expandtabs(4)) > base and groups:
            groups[-1][1].append(text)
        else:
            groups.append((text, [], bool(found.group(3))))
    steps = any(numbered for _t, _s, numbered in groups) or _then_steps([t for t, _s, _n in groups])
    said: list[str] = []
    joined = _each_joined([t for t, _s, _n in groups], steps)
    for (_text, subs, _n), sentence in zip(groups, joined):
        said.append(sentence)
        said.extend(_ended(_cap(sub)) for sub in subs)
    return " ".join(said)


def _each_joined(items: list[str], steps: bool) -> list[str]:
    out = []
    for i, item in enumerate(items):
        if steps and len(items) > 1:
            lead = "Finally, " if i == len(items) - 1 and i > 1 else _STEP_JOINS[min(i, len(_STEP_JOINS) - 1)]
        else:
            lead = "Finally, " if i == len(items) - 1 and i > 2 else _LIST_JOINS[i % len(_LIST_JOINS)] if i else ""
        out.append(_ended(lead + (_decap(item) if lead else _cap(item))))
    return out


def _then_steps(items: list[str]) -> bool:
    return sum(1 for item in items if re.match(r"(?:then|next|after that|finally|first)\b", item, re.I)) >= 2


def to_prose(text: str) -> str:
    """Bullets opened out into sentences, headings and prose kept."""
    out = []
    for kind, lines in _blocks(text):
        out.append(_list_prose(lines) if kind == "list" else "\n".join(lines))
    return "\n\n".join(out)


def plainly(text: str) -> str:
    """Plain words, fillers trimmed, long sentences split; lists stay lists."""
    out = []
    for kind, lines in _blocks(text):
        if kind == "prose":
            said = [part for s in sentences(" ".join(lines)) for part in _split_long(trim(plain(s)))]
            out.append(" ".join(said))
        elif kind == "list":
            out.append("\n".join(_relist(line, lambda t: trim(plain(t))) for line in lines))
        else:
            out.append("\n".join(lines))
    return "\n\n".join(out)


def _relist(line: str, change) -> str:  # noqa: ANN001
    found = _ITEM.match(line)
    marker = line[: found.start(4)]
    return marker + change(found.group(4))


def _centrality(said: list[str]) -> list[float]:
    """How much of the rest of the text each sentence's words are about."""
    counts = Counter(w for s in said for w in set(_words(s)))
    scores = []
    for i, sentence in enumerate(said):
        words = set(_words(sentence))
        shared = sum(counts[w] - 1 for w in words)
        scores.append(shared / (len(words) ** 0.5 or 1) + (0.6 if i == 0 else 0.0))
    return scores


def _kept(said: list[str], keep: int) -> list[str]:
    scores = _centrality(said)
    best = sorted(range(len(said)), key=lambda i: (-scores[i], i))[:keep]
    return [said[i] for i in sorted(best)]


def _hedge(sentence: str) -> bool:
    """A sentence that says nothing on its own: "Anyway, that's it."."""
    return len(_words(sentence)) <= 1 or bool(re.match(r"(?:anyway|so yeah|that'?s (?:it|all)|just a thought)\b", sentence, re.I))


def _cleaned(text: str) -> list[str]:
    """A run of prose as sentences, fillers and wordy phrases out, a repeat
    or a sentence that says nothing dropped."""
    said: list[str] = []
    for s in sentences(text):
        s = trim(concise(s))
        if not _hedge(s) and not any(_same(s, earlier) for earlier in said):
            said.append(_ended(s))
    return said


def _cut_to(said: list[str], words: int) -> list[str]:
    """The least central sentences out until `words` remain or only
    `SHORT_KEEP_MIN` sentences are left; the first is always kept."""
    kept = list(said)
    scores = dict(zip(said, _centrality(said)))
    while len(kept) > SHORT_KEEP_MIN and sum(len(s.split()) for s in kept) > words:
        kept.remove(min(kept[1:], key=lambda s: (scores[s], -kept.index(s))))
    return kept


def shorter(text: str) -> str:
    """Fillers, wordy phrases and repeats out; if that has not taken a fifth
    off, the least central sentences go until about `SHORT_SHARE` is left.
    Headings and list items kept, items trimmed."""
    out = []
    for kind, lines in _blocks(text):
        if kind == "prose":
            prose = " ".join(lines)
            said = _cleaned(prose)
            before, after = len(prose.split()), sum(len(s.split()) for s in said)
            if after > before * 0.8:
                said = _cut_to(said, int(before * SHORT_SHARE))
            out.append(" ".join(said))
        elif kind == "list":
            out.append("\n".join(_relist(line, lambda t: trim(concise(t))) for line in lines))
        else:
            out.append("\n".join(lines))
    return "\n\n".join(o for o in out if o)


_SUMMARY = re.compile(r"^\*\*(?:Summary|In short):\*\*.*$\n*", re.M | re.I)


def summary_of(text: str) -> str:
    """The one or two sentences the rest of the text is most about."""
    said: list[str] = []
    for kind, lines in _blocks(text):
        for s in _block_sentences(kind, lines) if kind != "heading" else []:
            s = _ended(trim(concise(s)))
            if len(s.split()) >= 3 and not _hedge(s) and not any(_same(s, x) for x in said):
                said.append(s)
    #: Under three sentences a summary is the text again.
    if len(said) < SUMMARY_MIN:
        return ""
    lead = _kept(said, SUMMARY_SENTENCES if len(said) > 3 else 1)
    return " ".join(lead) + _key_words(said, lead)


def _key_words(said: list[str], lead: list[str]) -> str:
    """" Key words: a, b, c." for the words the text repeats that the lead
    sentences do not already say; "" when there are none."""
    have = {w for s in lead for w in _words(s)}
    counts = Counter(w for s in said for w in set(_words(s)) if w not in have)
    words = [w for w, n in counts.most_common(3) if n >= 1]
    return f" Key words: {', '.join(words)}." if len(said) >= KEY_WORDS_MIN and words else ""


def _block_sentences(kind: str, lines: list[str]) -> list[str]:
    if kind == "list":
        return [_ITEM.match(line).group(4) for line in lines]
    return sentences(" ".join(lines))


def with_summary(text: str) -> str:
    """The text with "**Summary:** ..." under its title (one already there
    is replaced, so pressing twice gives one)."""
    body = _SUMMARY.sub("", text).strip()
    said = summary_of(body)
    if not said:
        return text
    first, _, rest = body.partition("\n")
    if _HEADING.match(first):
        return f"{first}\n\n**Summary:** {said}\n\n{rest.strip()}".rstrip()
    return f"**Summary:** {said}\n\n{body}"


# --- write up my notes ---------------------------------------------------------------


def _tidy(thoughts: str) -> str:
    """Loose thoughts as a note: each line's sentences capitalised and ended,
    fillers trimmed, list lines kept as a list."""
    from tessellate.ai import composer_tidy

    out = []
    for kind, lines in _blocks(thoughts):
        if kind == "prose":
            out.append(composer_tidy.fixed(" ".join(_ended(trim(concise(s))) for line in lines for s in sentences(line))))
        elif kind == "list":
            out.append("\n".join(_relist(line, lambda t: trim(t).rstrip(".")) for line in lines))
        else:
            out.append("\n".join(lines))
    return "\n\n".join(out)


def note_name(note: dict, size: int = 80) -> str:
    """What the composer calls a note: its label ("Budget review: ..."), else
    its title (`composer_frame`), cut at a word past `size`."""
    from tessellate.ai import composer_frame

    return _cap(composer_frame.note_label(note) or composer_frame.note_title(note.get("content") or "", size=size)) or "Untitled"


def _write_up_name(note: dict) -> str:
    """A note's name for the write-up: its first sentence when that is short
    ("Dentist visit"), so the rest of the note is points under it and not
    part of its name."""
    name = note_name(note)
    first = sentences(name)[0] if sentences(name) else name
    return first.rstrip(".") if len(first.split()) <= 8 and first != name else name


def _named_by(sentence: str, title: str) -> bool:
    """Whether a note's name already says this sentence (a name is often its
    first sentence, cut with an ellipsis)."""
    name = title.rstrip("\u2026").rstrip(" .")
    return sentence in title or (len(name) > 12 and sentence.startswith(name))


def _note_points(content: str, title: str) -> list[str]:
    """A note's key sentences, its own order, its title (or label) left out."""
    from tessellate.ai import study

    said: list[str] = []
    for kind, lines in _blocks(content):
        if kind == "heading":
            continue
        for s in _block_sentences(kind, lines):
            s = study.clean(s)
            if s.lower().startswith(f"{title.lower()}:"):
                s = s[len(title) + 1:].strip()
            s = trim(concise(s)).rstrip(".")
            if len(s.split()) >= 3 and not _named_by(s, title) and not _hedge(s) and not any(_same(s, x) for x in said):
                said.append(s)
    if not said:
        return []
    return _kept(said, min(WRITE_UP_POINTS, len(said)))


def _write_up_title(tidied: str, names: list[str]) -> str:
    """The thoughts' first clause, else the one note's name, else the word
    the notes' names share ("Notes on budget")."""
    from tessellate.ai import no_model_text

    if tidied:
        opening = re.sub(r"^#+\s*|^[-*+]\s+", "", tidied)
        first = re.split(r"[.,;:!?\n]", opening, maxsplit=1)[0]
        title = no_model_text.draft_title(first)
        #: A title that is the whole first sentence only says it twice.
        return "" if title.rstrip(".") == sentences(opening.split("\n")[0])[0].rstrip(".!?") else title
    if len(names) == 1:
        return names[0]
    shared = Counter(w for n in names for w in set(_words(n))).most_common(1)
    return f"Notes on {shared[0][0]}" if shared and shared[0][1] >= 2 else "From my notes"


def _when(source: dict) -> date | None:
    raw = source.get("written")
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw)[:10]) if raw else None
    except ValueError:
        return None


_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _day_heading(day: date, today: date) -> str:
    """"Thursday 29 October" ("Thursday 29 October 2025" in another year)."""
    from tessellate.ai import realise

    year = f" {day.year}" if day.year != today.year else ""
    return f"{_WEEKDAYS[day.weekday()]} {day.day} {realise._MONTHS[day.month - 1]}{year}"


def write_up(thoughts: str, sources: list[dict] | None, today: date) -> str:
    """The thoughts tidied, then the chosen notes oldest first, grouped under
    a heading for each day when they span more than one, each with its key
    points."""
    notes = [(s, _when(s)) for s in sources or [] if (s.get("content") or "").strip()]
    notes.sort(key=lambda pair: pair[1] or date.max)
    tidied = _tidy(thoughts).strip()
    named = [(_write_up_name(s), s, day) for s, day in notes]
    if not tidied and not named:
        return ""
    title = _write_up_title(tidied, [n for n, _s, _d in named])
    parts = [part for part in (f"# {title}" if title else "", tidied) if part]
    return "\n\n".join(parts + _note_blocks(named, today))


def _note_blocks(named: list, today: date) -> list[str]:
    """Each note's block, under a day heading when the notes span days."""
    from tessellate.ai import realise

    days = {day for _n, _s, day in named if day}
    heading: date | None = None
    parts: list[str] = []
    for name, source, day in named:
        if len(days) > 1 and day and day != heading:
            heading = day
            parts.append(f"## {_day_heading(day, today)}")
        said = "" if len(days) > 1 or not day else f", written {realise.relative_day(day, today)}"
        parts.append(_note_block(name, source, said))
    return parts


def _note_block(name: str, source: dict, when: str) -> str:
    points = _note_points(source.get("content") or "", name)
    return "\n".join([f"**{name}**{when}" + (":" if points else "")] + [f"- {p}" for p in points])


# --- the door --------------------------------------------------------------------------

#: A Refine instruction -> the pass that does it. Read in this order: "make it a
#: short timeline" is a diagram before it is shorter.
_ASKS = (
    ("diagram", re.compile(r"\b(?:flow\s?chart|flow diagram|diagram|mind\s?-?map|time\s?line|chart|graph|mermaid)\b", re.I)),
    ("summary", re.compile(r"\b(?:summary|summari[sz]e|sum (?:it )?up|tl;?dr|in short|key points|overview)\b", re.I)),
    ("bullets", re.compile(r"\b(?:bullets?|bullet points|(?:a |into a )?list|point form)\b", re.I)),
    ("expand", re.compile(r"\b(?:prose|paragraphs?|full sentences|write it out)\b", re.I)),
    ("tidy", re.compile(r"\b(?:tidy|tidied|spell\w*|proofread|typos?|grammar|punctuation|capitals?|clean(?:ed)? (?:it )?up|fix (?:it|this|the (?:text|writing|draft)))\b", re.I)),
    ("formal", re.compile(r"\b(?:formal(?:ly)?|professional(?:ly)?|business(?: ?like)?)\b", re.I)),
    ("plain", re.compile(r"\b(?:plain(?:er|ly)?|simpl(?:e|er|ify)|easier|jargon|clearer)\b", re.I)),
    ("shorter", re.compile(r"\b(?:short(?:er|en)?|trim|cut|tighten|tighter|concise|brief(?:er)?|less wordy|condense)\b", re.I)),
)


def refine_kind(instruction: str) -> str:
    """The pass a Refine instruction asks for, or "" when none here does it."""
    for kind, pattern in _ASKS:
        if pattern.search(instruction or ""):
            return kind
    return ""


def _by_kind(kind: str, text: str) -> str:
    from tessellate.ai import composer_tidy

    return {
        "bullets": to_bullets, "expand": to_prose, "plain": plainly, "shorter": shorter, "summary": with_summary,
        "tidy": composer_tidy.tidy, "formal": composer_tidy.formally,
    }[kind](text)


_SAID = {
    "bullets": "Closed up into bullets by plain rule, with no model: one idea a bullet.",
    "expand": "Opened out into sentences by plain rule, with no model.",
    "plain": "Put in plain words by plain rule, with no model: long words swapped, long sentences split.",
    "shorter": "Made shorter by plain rule, with no model: fillers and repeats out, the key sentences kept.",
    "summary": "Added a summary from the draft's own key sentences, with no model.",
    "tidy": "Tidied by plain rule, with no model: spelling, capitals, apostrophes and full stops put right.",
    "formal": "Put in a formal voice by plain rule, with no model: contractions spelled out, slang swapped, fillers out.",
    "note": "Written up by plain rule, with no model: your words tidied and each note's key points under its date.",
}


def _done(shape: str, source: str, made: str) -> Pass:
    """`made` as a pass of `shape`, or the line saying there was nothing to do
    when it is the source over again (INBOX 1488: no control echoes its input)."""
    from tessellate.ai import composer_tidy

    if not made.strip() or composer_tidy.same(made, source):
        return Pass("", NOTHING_TO_DO[shape])
    return Pass(made, _SAID[shape], shape)


def compose(
    *, kind: str, thoughts: str, draft: str, instruction: str = "", tone: str = "", length: str = "",
    sources: list[dict] | None = None, today: date | None = None,
) -> Pass:
    """One Writing room pass with no model: the text, and the line to say.
    An empty `text` means this pass needs a model, or had nothing to change,
    and `message` says which."""
    kind = (kind or "").strip().lower()
    text = draft if (draft or "").strip() else thoughts
    if (instruction or "").strip():
        asked = refine_kind(instruction)
        if not asked:
            return Pass("", NEEDS_MODEL["refine"])
        if asked == "diagram":
            #: Drawn by `composer_mermaid.drafted`, which reads this module.
            return Pass("", "", "diagram")
        return _done(asked, text, _by_kind(asked, text))
    return _by_mode(kind, thoughts, draft, tone, length, sources, today or _user_today())


def _user_today() -> date:
    """The person's day, not the server's (audit 1028 K22)."""
    from tessellate.ai import composer

    return composer.user_today()


def _unchanged(a: str, b: str) -> bool:
    from tessellate.ai import composer_tidy

    return composer_tidy.same(a, b)


#: The kinds that are one pass over the text with nothing else to read.
_ONE_PASS = ("plain", "formal", "tidy")


def _by_mode(kind: str, thoughts: str, draft: str, tone: str, length: str, sources, today: date) -> Pass:  # noqa: ANN001
    text = draft if (draft or "").strip() else thoughts
    if kind.startswith("translate"):
        return Pass("", NEEDS_MODEL["translate"])
    if kind == "rewrite" and tone in ("plain", "formal"):
        kind = tone
    if kind == "rewrite":
        return Pass("", NEEDS_MODEL["rewrite"])
    if kind == "diagram":
        return Pass("", "", "diagram")
    if kind in _ONE_PASS:
        return _done(kind, text, _by_kind(kind, text))
    if kind in ("bullets", "expand"):
        source = thoughts if (thoughts or "").strip() else draft
        made = _toned(_by_kind(kind, source), tone, length)
        return _done(kind, source, made)
    if kind == "note":
        written = write_up(thoughts, sources, today)
        if written.strip() and not sources and _unchanged(written, thoughts):
            return Pass("", NOTHING_TO_DO["note"])
        if (draft or "").strip() and written:
            written = f"{draft.rstrip()}\n\n{written}"
        return Pass(_toned(written, tone, length), _SAID["note"], "note") if written.strip() else Pass("", NOTHING_TO_DO["note"])
    return Pass("", NEEDS_MODEL.get(kind, NEEDS_MODEL["revise"]))


def _toned(text: str, tone: str, length: str) -> str:
    """The two selects, where a rule can honour them: Plain or Formal, and Short."""
    from tessellate.ai import composer_tidy

    if tone == "plain":
        text = plainly(text)
    elif tone == "formal":
        text = composer_tidy.formally(text)
    return shorter(text) if length == "short" else text
