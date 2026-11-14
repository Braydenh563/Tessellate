"""Saying a quote: picking a wording by the question's hash, lowering a
capital after a joiner, a list said as one sentence, a checklist counted.

Moved whole from `composer.py` (audit AR3, gods-1101): the code is unchanged,
and `composer` re-exports every name here that anything reads, so
`composer._list_sentence` still works. Imports run one way, down
the layer list in `composer.py`'s docstring, never back to `composer`.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date

from tessellate.ai import composer_done, composer_tables, composer_threads, composer_tree
from tessellate.ai.composer_answer import _Answer, _SESSION
from tessellate.ai.composer_phrases import PHRASES
from tessellate.ai.composer_read import NoteView, Sentence
from tessellate.core.lazyre import lazy_compile


def _pick(question: str, salt: str, options: list[str]) -> str:
    """One of `options`: the same one every time for this question (and, in
    a conversation, this turn), a different one for most different
    questions."""
    session = _SESSION.get()
    digest = hashlib.sha1(f"{salt}:{question.strip().lower()}{':' + session if session else ''}".encode()).digest()
    return options[digest[0] % len(options)]


#: The first words a quote may have lowered after a joiner ("Separately,
#: the hills are steep"): words that are never a name. Anything else, a
#: name, "I", a capitalised word the app cannot tell from a name, keeps its
#: capital and takes the joiner after a colon instead.
_LOWERABLE = frozenset(
    """a an the it its this that these those there they their them we our
    you your he she his her one two three four five six seven eight nine ten
    every each some most all no not after before when if then in on at for
    to with without from by of only just still maybe once both next last
    first until since cut try keep ask write ship book buy call check get go
    make use add need plan start stop slow hire pair pairs foam sign
    out back""".split()
)


def _lowered(s: Sentence) -> str | None:
    """The quote with its first letter lowered, when its first word is one
    that is never a name ("The", "Ship", not "Harbor" or "I"); None otherwise."""
    if s.kind not in ("prose", "item") or len(s.text) < 2:
        return None
    first = re.match(r"[A-Za-z]+", s.text)
    if not first or first.group(0).lower() not in _LOWERABLE or first.group(0)[1:] != first.group(0)[1:].lower():
        return None
    return s.text[0].lower() + s.text[1:]


#: A sentence opening with one of these leans on the one before it: "It
#: forces the reading to be active" quoted alone has lost what "it" is.
_LEANS_BACK = lazy_compile(r"^(it|this|that|these|those|they|he|she|then|there|which|second|third|another)\b", re.I)


def _with_context(out: _Answer, sentences: list[Sentence]) -> list[Sentence]:
    """The sentences, each one that leans back preceded by the sentence it
    leans on (the note's own previous sentence, quoted whole too)."""
    have = {(s.note_id, s.order) for s in sentences}
    result: list[Sentence] = []
    for s in sentences:
        if s.order and s.kind == "prose" and _LEANS_BACK.match(s.text) and (s.note_id, s.order - 1) not in have:
            before = out.views[s.note_id].sentences[s.order - 1]
            if before.kind == "prose":
                before.score = before.score or s.score
                result.append(before)
                have.add((s.note_id, before.order))
        result.append(s)
    return result


def _quotes(out: _Answer, sentences: list[Sentence], terms: list[str], lower_first: bool = False) -> None:
    """Sentences of one note, run together in the note's own order; a picture's
    reading introduced as the app's reading of it, and each sentence other
    notes repeat followed by how many say it. `lower_first` lowers the first
    sentence's first letter, after a joiner that ends in a comma."""
    lower_first, out.lower_next = lower_first or out.lower_next, False
    for i, s in enumerate(sentences):
        if _said_with_before(sentences, i):
            continue
        if i:
            out.t("space")
        if not i and lower_first and _lowered(s):
            out.q(s, terms, _lowered(s))
            if s.echoes:
                out.t("echo").m(out.count(1 + len(s.echoes))).t("echo_end")
            continue
        if s.kind.startswith("picture"):
            _picture_said(out, sentences, i, terms)
        else:
            out.q(s, terms)
            if s.kind == "prose" and i + 1 < len(sentences) and not _ENDED.search(s.text):
                #: A first line with no full stop ("Side project ideas from
                #: the hackathon") ran into the next quote (INBOX 787).
                out.t("stop")
        if s.echoes:
            out.t("echo").m(out.count(1 + len(s.echoes))).t("echo_end")


#: A picture's words said in full up to this many lines.
PICTURE_LINES = 6


def _said_with_before(sentences: list[Sentence], i: int) -> bool:
    """A picture's line said with the reading before it (`_picture_said`)."""
    s, before = sentences[i], sentences[i - 1] if i else None
    return s.kind == "picture_text" and before is not None and before.kind.startswith("picture") and before.note_id == s.note_id


def _picture_said(out: _Answer, sentences: list[Sentence], i: int, terms: list[str]) -> None:
    """One picture's reading said once (INBOX 787): "The picture in your note
    from 5 September shows a screenshot of ..., which reads “Ranked
    Solo/Duo” and “Gold II”." Its lines after the first are said with it,
    never as a sentence each that names the picture again."""
    s = sentences[i]
    run = _picture_run(out, sentences, i)
    out.t("picture_in").name(out.views[s.note_id])
    reads = run
    if s.kind == "picture":
        #: A caption with its own verb is quoted whole, never spliced after
        #: "shows" (INBOX 1599); a noun phrase follows it, article lowered.
        whole, said = composer_threads.caption_form(s.text)
        if whole:
            out.t("picture_called", "open_quote").q(s, terms, said).t("close_quote")
        else:
            out.t("picture_shows").q(s, terms, said)
        reads = run[1:]
        out.t(*(("ov_reads",) if reads else ()))
    else:
        out.t("picture_reads")
    _quoted_lines(out, reads, terms)
    if reads or s.kind == "picture" or not _ENDED.search(s.text):
        out.t("stop")


def _quoted_lines(out: _Answer, lines: list[Sentence], terms: list[str]) -> None:
    """“A”, “B” and “C”: a picture's lines in quotes."""
    for n, line in enumerate(lines):
        if n:
            out.t("and" if n == len(lines) - 1 else "comma")
        out.t("open_quote").q(line, terms).t("close_quote")


def _picture_run(out: _Answer, sentences: list[Sentence], i: int) -> list[Sentence]:
    """The reading at `i` and the lines of its words said with it: every line,
    up to six, when the answer chose one of them ("what is on my feature
    list" asked for the list, and two lines of five were said); else the
    lines chosen right after it."""
    s = sentences[i]
    lines = [u for u in out.views[s.note_id].sentences if u.kind == "picture_text" and u.order >= s.order]
    chosen = any(u.kind == "picture_text" and u.note_id == s.note_id for u in sentences[i:])
    if chosen and len(lines) <= PICTURE_LINES + 1:
        return [s, *[u for u in lines if u is not s][:PICTURE_LINES]]
    run = [s]
    for later in sentences[i + 1:]:
        if later.kind != "picture_text" or later.note_id != s.note_id:
            break
        run.append(later)
    return run


_ENDED = lazy_compile(r"[.!?…:;\"”’)\]]\s*$")


#: A list the person wrote reads as one sentence when every entry is a short
#: phrase: "Designing Data-Intensive Applications, The Mom Test and A Pattern
#: Language". Past these it is a list, and is shown as one.
FUSE_MAX_ITEMS = 6


FUSE_MAX_WORDS = 10


def _fusable(items: list[Sentence]) -> bool:
    """Every entry a phrase lifted whole from the list (no sentence of its own
    inside it, no colon), short enough to read in one breath."""
    return (
        2 <= len(items) <= FUSE_MAX_ITEMS
        and all(s.kind == "item" for s in items)
        and all(len(s.text.split()) <= FUSE_MAX_WORDS and not re.search(r"[.!?:;]\s*$|:\s", s.text) for s in items)
    )


def _sentence_case(items: list[Sentence]) -> bool:
    """Entries written as sentence-case phrases ("A light jacket", "Plug
    adapter"), not names ("The Mom Test"): only these have their first letter
    lowered inside a sentence, which leaves the person's words as they wrote
    them everywhere else."""
    return all(not re.search(r"\s[A-Z]", s.text) for s in items)


def _joined(out: _Answer, keys: list[str], unit: list[Sentence], terms: list[str], when: date | None = None, colon: bool = False) -> None:
    """A joiner, an optional measured day, then the note's sentences: after a
    comma with the first letter lowered when it can be ("Later, on 3 March,
    the hotel is booked"), after a colon when it cannot or `colon` says so
    (a joiner that is not a clause: "The newest, from 3 March: ...")."""
    out.t(*keys)
    if when:
        out.m(out.day(when))
    if _lowered(unit[0]) and not colon:
        if when or not PHRASES[out.voiced(keys[-1])].endswith(" "):
            out.t("comma")
        _quotes(out, unit, terms, lower_first=True)
    else:
        out.t("colon")
        _quotes(out, unit, terms)


def _list_sentence(out: _Answer, items: list[Sentence], terms: list[str]) -> None:
    """" A, B and C." from the list's own entries."""
    lower = _sentence_case(items)
    for i, s in enumerate(items):
        if i:
            out.t("and" if i == len(items) - 1 else "comma")
        shown = decap(s.text) if lower else s.text
        out.q(s, terms, shown)
    out.t("stop")


def _your_kind(view: NoteView) -> str:
    """"Your note", or "Your board", "Your mind map", "Your document" for a
    source that is not a note (INBOX 744: "a board must say board")."""
    return f"your_{view.kind}_cap" if view.kind in ("board", "map", "document") else "your_note_cap"


def _list_lead(out: _Answer, view: NoteView, lead: str) -> None:
    """What introduces a list: "Your note **Reading list** lists ", or "It
    also lists " when the answer already named the note."""
    if lead == "opening" and _unlike_before(out, ["your_note_cap", "in_cap"])[0] == "in_cap":
        #: "In **Reading list** you listed four: ...", after a turn that
        #: opened "Your note ...".
        out.t("in_cap").name(view).t("you_listed")
    elif lead == "opening":
        if view.titled:
            out.t(_your_kind(view), "space")
        out.name(view, cap=True).t("lists")
    else:
        out.t("it_lists")


def _done_later(out: _Answer, view: NoteView, tasks: list[Sentence]) -> dict[int, tuple]:
    return composer_done.done_later(list(out.views.values()), view, tasks)


def _done_later_note(got: tuple, today) -> str:  # noqa: ANN001
    return composer_done.done_later_note(got, today)


def _checklist_count(out: _Answer, view: NoteView, tasks: list[Sentence], lead: str) -> None:
    """How many of a checklist are ticked. Zero is "none of its three", one
    left unticked is "one item, not ticked": a count word before "of" is never
    "no" (audit 1029 C6). A line a later note records as done counts done."""
    ticked = sum(1 for s in tasks if s.done) + len(_done_later(out, view, tasks))
    opening = lead == "opening"
    if opening:
        if view.titled:
            out.t(_your_kind(view), "space")
        out.name(view, cap=True)
    if ticked:
        out.t("has" if opening else "checklist").m(out.count(ticked)).t("checklist_of").m(out.count(len(tasks)))
        out.t("checklist_items_done" if opening else "checklist_done")
    elif len(tasks) == 1:
        out.t("has" if opening else "checklist").t("one_open")
    else:
        out.t("has_none_of_its" if opening else "checklist_none_of_its").m(out.count(len(tasks)))
        out.t("checklist_items_done" if opening else "checklist_done")


def _list_block(out: _Answer, view: NoteView, items: list[Sentence], terms: list[str], lead: str) -> None:
    """A note's list, introduced by what it holds: "Your note **Reading
    list** lists four: ...", a checklist with how many are ticked."""
    tasks = [s for s in items if s.kind == "task"]
    if tasks and len(tasks) == len(items):
        _checklist_count(out, view, tasks, lead)
        out.t("para")
        later = _done_later(out, view, tasks)
        for i, s in enumerate(tasks):
            if i:
                out.t("line")
            out.item(s, terms)
            if id(s) in later:
                out.m(_done_later_note(later[id(s)], out.today))
        return
    _list_lead(out, view, lead)
    if composer_tree.nested(items):
        composer_tree.write(out, items, terms)
        return
    out.m(out.count(len(items)))
    if _fusable(items):
        out.t("colon")
        _list_sentence(out, items, terms)
        return
    out.t("end_colon", "para")
    for i, s in enumerate(items):
        if i:
            out.t("line")
        out.item(s, terms)


def _unlike_before(out: _Answer, keys: list[str]) -> list[str]:
    """`keys` less any the turn before opened with, in their order; all of
    them when every one did."""
    fresh = [k for k in keys if not _said_before(out, k)]
    return fresh or keys


def _said_before(out: _Answer, key: str) -> bool:
    """Whether the turn before opened with `key`'s words in any variant of
    either voice."""
    names = {key}
    for voice in composer_tables.VOICES:
        names.update(composer_tables.VOICE_VARIANTS[voice].get(key, ()))
    return any(out.opened_with(PHRASES[name]) for name in names)


def decap(text: str) -> str:
    """`text` with its first letter lowered for the middle of a sentence,
    unless its first word is a name by its shape: "I", or a capital after
    the first letter ("IaaS", "iPhone", "GPU"). INBOX 1357: a map's items
    were said as "iaaS, paaS and saaS"."""
    first = re.match(r"[A-Za-z][\w'-]*", text or "")
    if first and (first.group(0) in ("I", "I'm", "I've", "I'd", "I'll") or any(c.isupper() for c in first.group(0)[1:])):
        return text
    return text[:1].lower() + text[1:]
