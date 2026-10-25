"""Study material read out of a note, with no model (INBOX 1351: "just as good
and extremely smart" without Ollama, for lectures on battery).

Pure functions over a note's text, so each is testable with a string:

- `sections` splits a note at its headings;
- `cards` reads question and answer pairs out of it: a definition ("X is Y",
  "**X** means Y", "X: Y"), the points under a heading, a bold term in a
  sentence as a gap to fill, a `Q:` and `A:` pair a flashcard note already
  holds, and the definition turned round ("which term means ...");
- `key_terms` and `summary` are the same reading shown another way;
- `grade` checks a typed answer loosely, by the content words it shares with
  the note's own, so "a program running" still matches "a program in execution".

Every question and every answer is the note's own words (the composer's rule);
only the question frames ("What is ...?") are ours, and several are offered so
a quiz does not read as a template. Nothing is kept: a quiz is rebuilt from
the note on each turn in the same order (`ordered` hashes the topic), so the
dialogue's own text is its state (`composer_study`).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_BULLET = re.compile(r"^\s*(?:[-*+]|\d{1,2}[.)])\s+(?!\[[ xX]\])(.+)$")
_CHECK = re.compile(r"^\s*[-*+]\s+\[([ xX])\]\s+(.+)$")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9*\"“(\[])")
_MARKUP = re.compile(r"(\*\*|__|\*|`)")
_FOOTNOTE = re.compile(r"\[\^[^\]\n]*\]|<sup>[^<]{0,6}</sup>")
_FOOTNOTE_LINE = re.compile(r"^\s*\[\^[^\]]+\]:")
_LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]|\[([^\]]+)\]\([^)]*\)")
_BOLD = re.compile(r"\*\*([^*\n]{2,60})\*\*|__([^_\n]{2,60})__")
_PRONOUNS = frozenset({
    "it", "this", "that", "these", "those", "there", "he", "she", "they", "we", "i", "you", "which", "what", "who", "here",
    "its", "his", "her", "their", "our", "my", "your", "one", "each", "some", "all", "both", "when", "where", "how", "why",
})
_NOT_TERMS = frozenset({
    "note", "tip", "todo", "example", "warning", "remember", "important", "summary", "due", "date", "time", "when", "where",
    "who", "what", "why", "how", "q", "a", "answer", "question", "link", "source", "see", "ps", "nb", "idea", "reminder", "idea",
})
_DEF = re.compile(
    r"^(?P<term>[A-Za-z0-9][\w'’/&()-]*(?: [\w'’/&()-]+){0,4}?)\s+"
    r"(?P<verb>is defined as|is known as|is called|refers to|is when|is the|is a|is an|is|are|means|stands for)\s+(?P<body>.{10,})$"
)
_COLON = re.compile(r"^(?:[-*+]\s+)?\**(?P<term>[A-Za-z0-9][^:*\n]{1,40}?)\**\s*[:–-]\s+(?P<body>\S.{7,})$")
_QA = re.compile(r"^\**Q\**[:.]\**\s*(?P<q>.+?)\s*\n+\**A\**[:.]\**\s*(?P<a>.+?)\s*$", re.M)

STOP = frozenset(
    "a an the of and or to in on at for with by from as is are was were be been being it its this that these those there their them "
    "they he she we you your our my i me not no but if then so than too very can could will would should may might must do does did "
    "have has had having into onto over under about up down out off per via also just only each every any some more most other such "
    "which what when where who whom whose how why".split()
)


def clean(text: str) -> str:
    """Plain words: links to their text, markup off, spaces folded."""
    text = _FOOTNOTE.sub("", text or "")
    text = _LINK.sub(lambda m: m.group(2) or m.group(1) or m.group(3) or "", text or "")
    return " ".join(_MARKUP.sub("", text).split())


def stem(word: str) -> str:
    """A crude stem, enough to match "processes" to "process" and "running" to "run"."""
    w = re.sub(r"[^a-z0-9]", "", word.lower())
    for suffix in ("ing", "ies", "es", "ed", "ly", "s"):
        if len(w) > len(suffix) + 3 and w.endswith(suffix):
            w = w[: -len(suffix)] + ("y" if suffix == "ies" else "")
            break
    return w[:6]


def content_stems(text: str) -> list[str]:
    seen: list[str] = []
    for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]*", clean(text)):
        if word.lower() in STOP:
            continue
        s = stem(word)
        if s and s not in seen:
            seen.append(s)
    return seen


@dataclass
class Section:
    level: int
    title: str
    lines: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines).strip()


def sections(content: str) -> list[Section]:
    """The note split at its headings; text before the first is level 0."""
    out = [Section(0, "")]
    fenced = False
    for line in (content or "").splitlines():
        if line.strip().startswith("```"):
            fenced = not fenced
            continue  # code is not prose: a fence is never a sentence to quiz or summarise
        found = None if fenced else _HEADING.match(line)
        if found:
            out.append(Section(len(found.group(1)), clean(found.group(2))))
        elif not fenced:
            out[-1].lines.append(line)
    return [s for s in out if s.title or s.text]


def title_of(content: str) -> str:
    for line in (content or "").splitlines():
        if line.strip():
            found = _HEADING.match(line)
            return clean(found.group(2)) if found else clean(line)[:80]
    return ""


def _prose(para: str) -> str:
    """The prose lines of a paragraph, or "" when it is a list or a table."""
    lines = [_FOOTNOTE.sub("", ln.strip()) for ln in para.splitlines() if ln.strip() and not _FOOTNOTE_LINE.match(ln)]
    if not lines or all(_BULLET.match(ln) or _CHECK.match(ln) or ln.startswith("|") for ln in lines):
        return ""
    return " ".join(ln for ln in lines if not (_BULLET.match(ln) or _CHECK.match(ln) or ln.startswith(("|", ">", "```"))))


def sentences(text: str) -> list[str]:
    """Sentences of the prose in `text`, markup kept (bold is a signal), list
    bullets and tables left out."""
    out: list[str] = []
    for para in re.split(r"\n\s*\n", text or ""):
        out += [s.strip() for s in _SENTENCE_END.split(_prose(para)) if len(s.strip()) > 3]
    return out


def bullets(text: str) -> list[str]:
    return [clean(m.group(1)) for ln in (text or "").splitlines() if (m := _BULLET.match(ln))]


def open_tasks(content: str) -> list[str]:
    return [clean(m.group(2)) for ln in (content or "").splitlines() if (m := _CHECK.match(ln)) and m.group(1) == " "]


# --- cards ---------------------------------------------------------------------

@dataclass(frozen=True)
class Card:
    q: str
    a: str
    kind: str  # define | term | list | gap | about | pair
    where: str = ""
    items: tuple = ()


def _pick(seed: str, options: tuple) -> str:
    return options[int.from_bytes(hashlib.sha1(seed.encode()).digest()[:2], "big") % len(options)]


_DEFINE_Q = ("What is {t}?", "Define {t}.", "What does {t} mean?", "How would you explain {t}?")
_DEFINE_Q_PLURAL = ("What are {t}?", "Define {t}.", "What do we mean by {t}?")
_TERM_Q = ("Which term means: “{b}”?", "What is the word for: “{b}”?", "Name the term described as: “{b}”.")


def _trim_term(term: str) -> str:
    term = clean(term).strip(" ,;:")
    term = re.sub(r"^(?:the|a|an)\s+", "", term, flags=re.I)
    return term


def _term_ok(term: str) -> bool:
    words = term.split()
    if not words or len(words) > 5 or term.lower() in _NOT_TERMS or words[0].lower() in _PRONOUNS:
        return False
    if re.search(r"\b(?:that|which|because|when|while|if|then)\b", term, re.I):
        return False
    return not term[0].isdigit() or len(words) > 1


def _answer_text(body: str) -> str:
    body = clean(body).strip(" ")
    return body[0].upper() + body[1:] if body else body


def _definition(sentence: str) -> tuple[str, str, str] | None:
    """(term, verb, body) when a sentence defines something; the term is the
    bold one if the sentence has one up front, else the words before the verb."""
    plain = clean(sentence).rstrip(".")
    found = _DEF.match(plain)
    if not found:
        return None
    term = _trim_term(found.group("term"))
    bold = [b[0] or b[1] for b in _BOLD.findall(sentence)]
    if bold and term.lower() != bold[0].lower() and bold[0].lower() in term.lower():
        term = bold[0]
    if not _term_ok(term):
        return None
    verb = found.group("verb")
    body = found.group("body")
    if verb in ("is the", "is a", "is an"):
        body = verb.split(" ", 1)[1] + " " + body
    return term, ("are" if verb == "are" else "is"), body


def _define_cards(sentence: str, where: str) -> list[Card]:
    found = _definition(sentence)
    if not found:
        return []
    term, verb, body = found
    answer = _answer_text(body)
    frame = _define_frame(term, verb)
    cards = [Card(frame, answer, "define", where)]
    if len(content_stems(body)) >= 3 and len(body.split()) <= 24:
        cards.append(Card(_pick(term, _TERM_Q).format(b=body.rstrip(".")), term, "term", where))
    return cards


def _define_frame(term: str, verb: str) -> str:
    options = _DEFINE_Q_PLURAL if verb == "are" else _DEFINE_Q
    return _pick(term.lower(), options).format(t=term)


def _gap_card(sentence: str, where: str) -> Card | None:
    """A sentence with a bold term, the term blanked: "Round robin gives each
    process a fixed ____." The term, not a random word, is what the note stressed."""
    bold = _BOLD.search(sentence)
    if not bold:
        return None
    term = clean(bold.group(1) or bold.group(2))
    plain = clean(sentence)
    if len(plain.split()) < 6 or len(plain.split()) > 32 or not _term_ok(term):
        return None
    blanked = re.sub(re.escape(term), "____", plain, count=1, flags=re.I)
    return Card(f"Fill the gap: {blanked}", term, "gap", where)


def _list_card(heading: str, items: list[str], where: str) -> Card | None:
    items = [i for i in items if 2 <= len(i.split()) <= 20 or len(i) >= 3][:8]
    if len(items) < 2 or not heading:
        return None
    n = len(items)
    q = _pick(heading.lower(), (
        f"Name the {n} points your notes list under “{heading}”.",
        f"What are the {n} items under “{heading}”?",
        f"List the {n} things noted under “{heading}”.",
    ))
    return Card(q, "; ".join(items), "list", where, tuple(items))


def _colon_cards(sec: Section, where: str) -> list[Card]:
    out: list[Card] = []
    for line in sec.text.splitlines():
        colon = _COLON.match(line.strip())
        if not colon or _QA.match(line):
            continue
        term, body = _trim_term(colon.group("term")), colon.group("body")
        stressed = line.lstrip().startswith(("-", "*", "+")) or "**" in line
        if _term_ok(term) and (stressed or body[0].islower()) and not re.match(r"^\d", body):
            out.append(Card(_define_frame(term, "is"), _answer_text(body), "define", where))
    return out


def _section_cards(sec: Section, where: str) -> list[Card]:
    out = _colon_cards(sec, where)
    sents = sentences(sec.text)
    defined = 0
    for sentence in sents:
        made = _define_cards(sentence, where)
        out += made
        defined += bool(made)
        gap = None if made else _gap_card(sentence, where)
        out += [gap] if gap else []
    out += [c for c in [_list_card(sec.title, bullets(sec.text), where)] if c]
    if sec.level >= 2 and sents and not defined and len(clean(sents[0])) >= 24 and not generic_head(sec.title):
        out.append(Card(_pick(sec.title.lower(), (
            f"What do your notes say about {sec.title}?", f"Explain {sec.title} in your own words.",
        )), _answer_text(sents[0]), "about", where))
    return out


def cards(content: str) -> list[Card]:
    """Every question and answer the note holds, in the note's order."""
    out: list[Card] = []
    seen: set[str] = set()
    found = [Card(clean(m.group("q")), _answer_text(m.group("a")), "pair") for m in _QA.finditer(content or "")]
    title = title_of(content)
    for sec in sections(content or ""):
        found += _section_cards(sec, sec.title or title)
    for card in found:
        if card.q not in seen and card.a.strip():
            seen.add(card.q)
            out.append(card)
    return out


def ordered(deck: list[Card], topic: str, limit: int = 8) -> list[Card]:
    """A stable shuffle, one per kind first, so a quiz is varied but the same
    deck in the same order on every turn."""
    ranked = sorted(deck, key=lambda c: hashlib.sha1(f"{topic.lower()}|{c.q}".encode()).hexdigest())
    first: list[Card] = []
    seen_kinds: set[str] = set()
    for c in ranked:
        if c.kind not in seen_kinds:
            seen_kinds.add(c.kind)
            first.append(c)
    rest = [c for c in ranked if c not in first]
    mixed = sorted(first + rest, key=lambda c: hashlib.sha1(f"{topic.lower()}#{c.q}".encode()).hexdigest())
    return mixed[:limit]


# --- terms and summaries ---------------------------------------------------------

_GENERIC_HEADS = frozenset({"summary", "notes", "overview", "introduction", "intro", "todo", "tasks", "agenda", "links", "references", "questions"})
_GENERIC_SQUASHED = _GENERIC_HEADS | {"thingstodo", "checklist", "readinglist", "homework", "deadlines", "reminders", "ideas", "misc", "other", "later", "done", "inprogress", "backlog", "nextsteps", "actionitems", "resources"}


def generic_head(title: str) -> bool:
    """A heading that names a kind of list ("To do", "Next steps"), not a topic:
    no "Explain To do in your own words" question is made from it."""
    return re.sub(r"[^a-z]", "", (title or "").lower()) in _GENERIC_SQUASHED





def _terms_of(sec: Section) -> list[tuple[str, str]]:
    """(term, gloss) for each definition and each stressed "Term: meaning" line of a section."""
    out: list[tuple[str, str]] = []
    for sentence in sentences(sec.text):
        found = _definition(sentence)
        if found:
            out.append((found[0], _answer_text(re.split(r"[;:]|, (?:and|but|which|where)\b", found[2])[0])[:140].rstrip(" ,.")))
    for line in sec.text.splitlines():
        colon = _COLON.match(line.strip())
        term = _trim_term(colon.group("term")) if colon else ""
        if colon and _term_ok(term) and (line.lstrip().startswith(("-", "*", "+")) or "**" in line):
            out.append((term, _answer_text(colon.group("body"))[:140].rstrip(" ,.")))
    return out


def key_terms(content: str, limit: int = 12) -> list[tuple[str, str]]:
    """(term, gloss) pairs: bold terms first (most repeated, then first seen),
    defined terms, then the headings. A gloss is the note's own definition,
    cut to a clause, or empty."""
    glosses: dict[str, str] = {}
    order: list[str] = []
    counts: dict[str, int] = {}

    def see(term: str, gloss: str = "") -> None:
        key = term.lower()
        if key not in glosses:
            order.append(term)
        glosses[key] = glosses.get(key) or gloss
        counts[key] = counts.get(key, 0) + 1

    for b in _BOLD.findall(content or ""):
        if _term_ok(clean(b[0] or b[1])):
            see(clean(b[0] or b[1]))
    secs = sections(content or "")
    for sec in secs:
        for term, gloss in _terms_of(sec):
            see(term, gloss)
    title = title_of(content).lower()
    for sec in secs:
        if sec.level >= 2 and sec.title and not generic_head(sec.title) and sec.title.lower() != title:
            see(sec.title)
    ranked = sorted(order, key=lambda t: (-min(counts[t.lower()], 3), order.index(t)))
    return [(t, glosses[t.lower()]) for t in ranked[:limit]]


def _picks(sec: Section, level: int) -> list[str]:
    sents = sentences(sec.text)
    picks = sents[:1]
    if level >= 0:
        picks += [x for x in sents[1:] if _BOLD.search(x) or re.search(r"\d", x) or _definition(x)][: (1 if level == 0 else 4)]
    if level >= 1:
        picks = list(dict.fromkeys(picks + sents[1:5]))
    shown = 3 if level == 0 else 8
    items = bullets(sec.text)
    if items and level >= 0:
        picks.append("Points: " + "; ".join(items[:shown]) + ("" if len(items) <= shown else f"; and {len(items) - shown} more"))
    return picks


def summary(content: str, level: int = 0) -> list[tuple[str, list[str]]]:
    """(heading, sentences) per section. level -1 is one sentence a section
    and at most four sections, 0 the lead and the best second, 1 everything
    worth saying. Sentences are the note's own, with the markup kept."""
    out = [(sec.title, picks) for sec in sections(content or "") if (picks := [p for p in _picks(sec, level) if clean(p).strip(" -*+")])]
    return out[: 4 if level < 0 else 8 if level == 0 else 20]


# --- grading ---------------------------------------------------------------------

def _word_forms(text: str) -> set[str]:
    return {stem(w) for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]*", clean(text)) if w.lower() not in STOP}


def _grade_list(said: set[str], card: Card) -> str:
    hit = sum(1 for item in card.items if _share(item, said) >= 0.5)
    return "right" if hit >= max(1, round(len(card.items) * 0.6)) else "close" if hit else "wrong"


def grade(reply: str, card: Card) -> str:
    """"right", "close" or "wrong": how many of the answer's own content words
    (less the question's) the reply uses. Loose on purpose: a student's own
    phrasing, a plural, a missing article, still counts."""
    said = _word_forms(reply)
    if not said:
        return "wrong"
    if card.kind == "list":
        return _grade_list(said, card)
    asked = _word_forms(card.q)
    want = [s for s in content_stems(card.a) if s not in asked] or content_stems(card.a)
    if not want:
        return "right" if clean(reply).lower() == card.a.lower() else "wrong"
    if card.kind in ("term", "gap") or len(want) <= 2:
        share = len(set(want) & said) / len(want)
        return "right" if share >= 1 else "close" if share >= 0.5 else "wrong"
    key = sorted(want, key=lambda s: -len(s))[:6]
    share = len(set(key) & said) / len(key)
    return "right" if share >= 0.6 else "close" if share >= 0.3 else "wrong"


def _share(item: str, said: set[str]) -> float:
    want = content_stems(item)
    return len(set(want) & said) / len(want) if want else 0.0


def hint(card: Card) -> str:
    """A nudge that gives away the start, not the answer."""
    words = card.a.split()
    if card.kind == "list":
        return f"it starts with “{card.items[0].split()[0]}”."
    if len(words) <= 3:
        return f"it starts with “{card.a[0]}” and is {len(words)} word{'s' if len(words) != 1 else ''} long."
    return "it begins “" + " ".join(words[:3]) + " ...”."
