"""What the notebook worked out for itself (WORLD_CLASS_PLAN 15, I1 and I9).

A derived fact is a sentence the app decided was worth remembering *about* a
note: a claim the note makes, or a question it leaves open. Nothing here is
ever written back into a note. Every row carries where it came from (the note
and the exact offsets in it), who decided (a model by name, or `local` when
none was involved), when, and how sure, because a model that is wrong quietly
is worse than no model, and the only defence is that every derived thing can
be read, corrected, deleted and switched off.

**Why the derivation is local first and the model second.** The obvious
shape is to hand the note to a model and ask for a JSON list of claims and
questions. That shape has two faults this app cannot carry. The first is that
a model's paraphrase does not appear in the note, so the span that is supposed
to point at the source has to be re-found afterwards by string search, which
lands on the wrong sentence in any note that repeats itself and on nothing at
all when the model rewords. The second is that the notebook is offline-first:
a pipeline that derives nothing without a model would give a person with no
model a screen that is empty forever, and would be untestable against the fake
transport every provider test in this project runs on (CLAUDE.md section 4).

So the pass reads the note itself, splits it into sentences with their
offsets, and proposes candidates from the shape of each sentence. A model,
when one is running, is then asked to *narrow* that list, which is the half a
small local model is actually good at and the half where a wrong answer costs
a missing row rather than a fabricated one. `model` on the row names whoever
made the final call: the model when its reply was usable, `local` when it was
not asked or its reply could not be parsed. A row that says `local` is telling
the truth about itself, which is the whole contract.

**The lifecycle** lives on the row (see `DerivedFact` in `core/database.py`):
an edited row is never overwritten by a later run, a deleted row is a
tombstone rather than a `DELETE` so it is never re-derived, and a delete is
*also* written to the corrections store (`ai/learning.py`) because those are
two different jobs: the tombstone stops the re-derivation, and the correction
is what the loop learns from.

**The switches** are preferences, one per invention plus a master. Every
runner asks `runner_enabled()` before it does anything, and "off" means it
computes nothing and shows nothing while its existing rows are kept and inert.

**Nothing here imports `ai/learning.py`,** and the export that needs both
lives in `api/routes_learned.py` for that reason: `learning` asks this module
whether its runner is switched on, so an import the other way would close a
cycle (`tests/test_no_import_cycles.py` counts the statement wherever it
sits, which is the right rule: a function-level import is still a cycle, it
just fails later and further away).
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections import Counter
from types import SimpleNamespace
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.ai import question_cues
from tessellate.core import jobruns, model_gate, undo_bin
from tessellate.core.database import DerivedFact, Entry, EntryLink, utcnow
from tessellate.core.logbuffer import safe_value

logger = logging.getLogger("tessellate.ai.facts")

#: The switch names, and what each is off or on by default.
#:
#: The plan (WORLD_CLASS_PLAN 15, I9) lists some of these as off by default,
#: which was written about the *unattended* runs: "off by default, one switch
#: in Settings, with a token budget per night and a battery guard". Nothing
#: here runs unattended on its own. The night pass runs on the schedule only
#: when `autonomous_tasks_enabled` is on, which is off by default and is the
#: preference that has always meant "may this app think while I am not
#: looking"; these switches are the finer control over *what* it thinks about
#: once it may, and a switch that starts off would make "run now" do nothing
#: the first time anybody pressed it. INBOX 194 records the reading.
SWITCHES: dict[str, bool] = {
    "night_shift": True,
    "margin_reader": True,
    "open_questions": True,
    "resurfacing": True,
    "evidence_checks": True,
    "corrections": True,
    "model_bench": True,
}

#: The master switch. Not one of the seven: it is the answer to "stop all of
#: this now" and has to be readable without knowing what the seven are.
MASTER = "paused"

#: Where a switch is stored. One preference per switch rather than one JSON
#: blob, so a switch added later cannot be lost by a writer that read the blob
#: before it existed.
def _pref_key(name: str) -> str:
    return f"learn.{name}.enabled"


#: The kinds the night pass derives. Claims and questions come from one note
#: each (pass 3); a tension (two claims that disagree, pass 4) and an answer
#: (a later claim that answers an open question, pass 5) are pairs, stored on
#: the later side with the other in `payload`. The lifecycle below does not
#: care which kind a row is.
KINDS = ("claim", "question", "tension", "answered")
PAIR_KINDS = ("tension", "answered")

#: A sentence, and everything that is not one. Deliberately not
#: `grounding.split_sentences`: that one splits an *answer* into strings and
#: throws the offsets away, and an offset thrown away cannot be recovered (a
#: note that says the same sentence twice has two right answers and one of
#: them is wrong). This regex is matched with `finditer` so every candidate
#: carries the span it was cut from.
#: What ends a sentence, and what a sentence may not contain.
_ENDS = frozenset(".!?")
_BREAKS = frozenset(".!?\n")


def _sentence_spans(content: str):  # noqa: ANN202
    """(start, end) of each run up to and including its closing marks, the
    spans `[^.!?\n]+(?:[.!?]+|(?=\n)|$)` found, walked by hand: CodeQL reads
    that pattern as polynomial on a long run of spaces, and a loop says the
    same thing in one pass."""
    at, size = 0, len(content)
    while at < size:
        if content[at] in _BREAKS:
            at += 1
            continue
        end = at
        while end < size and content[end] not in _BREAKS:
            end += 1
        while end < size and content[end] in _ENDS:
            end += 1
        yield at, end
        at = end

#: A sentence shorter than this is a fragment ("Yes.", a list bullet, a
#: heading) and a sentence longer than this is a paragraph somebody forgot to
#: punctuate. Neither is a claim worth showing beside the note it came from.
MIN_SENTENCE_CHARS = 20
MAX_SENTENCE_CHARS = 300

#: How many facts one note may contribute to a single run. A pasted article
#: has hundreds of sentences and none of the value is in the two hundredth:
#: the cap is what stops one paste from becoming most of the table.
MAX_FACTS_PER_ENTRY = 12

#: The words that make a sentence a claim rather than a note to self. A claim
#: takes a position: something is, was, should or must be the case. Without
#: one of these, "ring the dentist" and "chicken, rice, tomatoes" would each
#: become a claim the app would then offer to check against the rest of the
#: notebook, which is noise wearing the clothes of insight.
_STANCE = frozenset(
    {
        "is", "are", "was", "were", "be", "been", "am",
        "should", "must", "will", "wont", "cannot", "cant",
        "has", "have", "had", "does", "do", "did",
        "never", "always", "needs", "need", "means", "costs", "takes",
    }
)

#: Rough tokens per character of prompt. Every local model's tokenizer
#: disagrees with every other one, so this is a budget unit rather than a
#: measurement, and it is deliberately on the generous side: a budget that
#: under-counts is a budget that does not stop anything.
TOKENS_PER_CHAR = 0.3

#: What reading one note costs even when no model is asked. Not zero, because
#: a budget of N has to bound a run over a notebook of any size, and a pass
#: that charges nothing for the notes it reads would walk the whole table
#: whatever budget it was given.
TOKENS_PER_NOTE = 4


@dataclass(frozen=True)
class Candidate:
    """One sentence the pass thinks is worth remembering, with its span."""

    kind: str
    text: str
    start: int
    end: int
    confidence: float


# --- the switches -------------------------------------------------------------


def stored_switches(config) -> dict[str, bool]:  # noqa: ANN001  # config is duck-typed
    """What the person actually set, ignoring the master switch."""
    return {
        name: bool(config.get_preference(_pref_key(name), default))
        for name, default in SWITCHES.items()
    }


def switches(config) -> dict[str, bool]:  # noqa: ANN001  # config is duck-typed
    """The switches as every runner sees them: the master wins.

    The master is reported *with* the seven rather than beside them because
    the question a caller is asking is "may this run", and an answer that
    needs two lookups and a rule to combine them is an answer two callers
    will combine differently.
    """
    paused = bool(config.get_preference(_pref_key(MASTER), False))
    values = stored_switches(config)
    if paused:
        values = dict.fromkeys(values, False)
    return {**values, MASTER: paused}


def set_switches(config, values: dict[str, Any]) -> dict[str, bool]:  # noqa: ANN001
    """Set any subset of the switches. Unknown names are refused."""
    unknown = set(values) - set(SWITCHES) - {MASTER}
    if unknown:
        # The names are for the developer who sent them; the person gets a
        # sentence they can read, and the log keeps the names.
        logging.getLogger("tessellate.facts").warning(
            "unknown switch names %s; known: %s", safe_value(sorted(unknown)), sorted({*SWITCHES, MASTER})
        )
        raise ValueError("Some of those switches don't exist, so none of them were changed.")
    for name, value in values.items():
        config.set_preference(_pref_key(name), bool(value))
    return switches(config)


def enabled(config, name: str) -> bool:  # noqa: ANN001  # config is duck-typed
    """May this runner do anything at all? The one question a runner asks."""
    return bool(switches(config).get(name, False))


# --- the derivation -----------------------------------------------------------


def sentences(content: str) -> list[tuple[str, int, int]]:
    """Every sentence in `content` with the span it occupies, exactly.

    `content[start:end]` is the returned text, character for character. The
    tests assert that, and so does every reader that scrolls a note to the
    sentence a fact came from.
    """
    out: list[tuple[str, int, int]] = []
    for start, end in _sentence_spans(content):
        while start < end and content[start].isspace():
            start += 1
        while end > start and content[end - 1].isspace():
            end -= 1
        if end > start:
            out.append((content[start:end], start, end))
    return out


#: What opens a line that is not the person's own words: a list marker and
#: emphasis (stripped before a question is judged), quote marks, a speaker's
#: label in capitals ("KNIGHT:"), a script's act or scene, a markdown heading.
_LEAD_MARKS = re.compile(r"^(?:\s*(?:[-*+]|\d+[.)])\s+)?(?:\*\*|__|\*|_)?")
_QUOTES = "\"\u201c\u201d"
_OPEN_QUOTES = "\"'\u201c\u2018\u00ab"
_SPEAKER = re.compile(r"^\s*[A-Z][A-Z .'-]{1,30}:\s")
_SCRIPT = re.compile(r"^\s*(?:ACT|SCENE|Act|Scene)\b", re.M)
_HEADING = re.compile(r"^\s*#{1,6}\s", re.M)
_YOU = re.compile(r"\byou(?:r|rs)?\b", re.I)
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")


def _line_around(content: str, start: int, end: int) -> tuple[str, str, int]:
    """The line holding `content[start:end]`, the text on it before the
    sentence, and where the line ends."""
    line_start = content.rfind("\n", 0, start) + 1
    line_end = content.find("\n", end)
    line_end = len(content) if line_end == -1 else line_end
    return content[line_start:line_end], content[line_start:start], line_end


def _answered_next(content: str, line_end: int) -> str | None:
    """The next non-empty line when it reads as a reply: short, not a
    question, not a list item. None otherwise."""
    for line in content[line_end:].split("\n")[1:]:
        if not line.strip():
            continue
        line = line.strip()
        return line if len(line) <= 80 and not line.endswith("?") and not _LIST_ITEM.match(line) else None
    return None


def own_question(content: str, start: int, end: int) -> bool:
    """Whether the question at `content[start:end]` is the person's own, the
    kind the Questions list exists for (INBOX 745 (b), the owner: "these are
    just random questions form my notes?? I didnt actually have any questions
    for myself"). The ones quoted were all one of these, and none is kept:

    * inside quotation marks, or opening on one (a prompt, a quote fragment:
      `- "If you were a spice...`, `" or "What's the most...`), or after "for
      example";
    * a line of a script or dialogue: a note with an act or a scene, or a
      line that opens with a speaker in capitals (`KNIGHT: What daring
      deed...`);
    * a question answered on the next line, where the note does that more
      than once or the reply starts "Because" (a joke list, a FAQ: "What's
      an astronaut's favorite drink?" then "Gravi-tea.");
    * pasted guide text: a note with two or more headings whose question
      speaks to "you".
    """
    text = content[start:end]
    core = text[_LEAD_MARKS.match(text).end():]
    if not core or core[0] in _OPEN_QUOTES:
        return False
    line, before, line_end = _line_around(content, start, end)
    if sum(before.count(mark) for mark in _QUOTES) % 2 or sum(core.count(mark) for mark in _QUOTES) % 2:
        return False
    if re.search(r"(?:for example|for instance|e\.g\.|such as)\W*$", before, re.I):
        return False
    if _SCRIPT.search(content) or _SPEAKER.match(line):
        return False
    if len(_HEADING.findall(content)) >= 2 and _YOU.search(core):
        return False
    if content[end:line_end].strip() == "":
        reply = _answered_next(content, line_end)
        if reply is not None and (reply.lower().startswith(("because", "cause ")) or _qa_pairs(content) >= 2):
            return False
    return True


def kept_question(content: str, start: int, end: int) -> bool:
    """`own_question`, less the kinds it does not see: a rhetorical question,
    one on a quoted line, one pasted from a page (`question_cues.not_asked`)."""
    return own_question(content, start, end) and not question_cues.not_asked(content, start, end)


#: A question in this many notes or more came from a template ("What am I
#: grateful for today?" in every journal page), not from a person asking.
TEMPLATE_NOTES = 3


def _template_questions(session: Session) -> set[str]:
    """The questions, in `question_cues.normal` form, that `TEMPLATE_NOTES`
    or more notes ask word for word."""
    seen: Counter[str] = Counter()
    for content in session.scalars(
        select(Entry.content).where(Entry.is_deleted.is_(False), Entry.is_private.is_(False))
    ):
        if content and ("?" in content or question_cues.cue(content)):
            seen.update({question_cues.normal(text) for text, _s, _e in sentences(content) if question_cues.asks(text)})
    return {text for text, notes in seen.items() if notes >= TEMPLATE_NOTES}


def _proposed(content: str, questions_on: bool, templates: set[str]) -> list[Candidate]:
    """A note's candidates, less its questions when the switch is off or a
    template asked them."""
    return [
        item
        for item in candidates(content)
        if item.kind != "question" or (questions_on and question_cues.normal(item.text) not in templates)
    ]


def _qa_pairs(content: str) -> int:
    """How many lines end in a question answered by the line after."""
    pairs = 0
    offset = 0
    for line in content.split("\n"):
        line_end = offset + len(line)
        if line.rstrip().endswith("?") and not _LIST_ITEM.match(line) and _answered_next(content, line_end) is not None:
            pairs += 1
        offset = line_end + 1
    return pairs


def candidates(content: str) -> list[Candidate]:
    """The claims and questions in one note, before any model sees them."""
    found: list[Candidate] = []
    for text, start, end in sentences(content):
        if not (MIN_SENTENCE_CHARS <= len(text) <= MAX_SENTENCE_CHARS):
            continue
        words = {word.strip("'\"`").lower() for word in re.findall(r"[A-Za-z']+", text)}
        if question_cues.asks(text):
            # A question is the one kind the text states outright, which is
            # why it is checked first and scored highest: no judgement was
            # needed and none should be claimed. One asked without its "?"
            # ("I wonder whether...", "need to find out...", INBOX 1466)
            # scores lower. Only the person's own (`kept_question`); one that
            # is not is neither a question nor a claim.
            if kept_question(content, start, end):
                found.append(Candidate("question", text, start, end, 0.9 if text.endswith("?") else 0.7))
        elif words & _STANCE:
            found.append(Candidate("claim", text, start, end, 0.6))
        if len(found) >= MAX_FACTS_PER_ENTRY:
            break
    return found


def _retire_not_own_questions(session: Session) -> int:
    """Tombstone the stored questions `kept_question` would not take now
    (INBOX 745 (b)): they leave the list at the next pass, and a tombstone is
    "already known", so a later read does not bring them back. A row whose
    note no longer holds its text is left to the edit path. Only the rows the
    rule pass wrote (`model == "local"`): a row a model decided on, or the
    person edited, is not undone by a rule after the fact."""
    rows = list(session.scalars(
        select(DerivedFact).where(
            DerivedFact.kind == "question", DerivedFact.deleted_at.is_(None),
            DerivedFact.model == "local", DerivedFact.edited_by_user.is_not(True),
        )
    ).all())
    notes = {
        entry.id: entry.content or ""
        for entry in session.scalars(select(Entry).where(Entry.id.in_({row.entry_id for row in rows})))
    } if rows else {}
    retired = 0
    for row in rows:
        content = notes.get(row.entry_id, "")
        if content[row.span_start:row.span_end] == row.text and not kept_question(content, row.span_start, row.span_end):
            row.deleted_at = utcnow()
            retired += 1
    if retired:
        session.commit()
    return retired


def _fingerprint(kind: str, text: str) -> str:
    """What makes two facts the same fact across runs.

    Whitespace and case are not part of it: a note re-wrapped by an editor
    would otherwise re-derive every fact in it and orphan every correction
    the person had made.
    """
    normalised = " ".join(text.split()).casefold()
    return f"{kind}:{hashlib.sha256(normalised.encode()).hexdigest()[:32]}"


def fingerprint_of(row: DerivedFact) -> str:
    """A stored row's fingerprint, taken from the model's words.

    `original_text` rather than `text` when the row has been edited, because
    the question this answers is "has the pass already produced this", and
    what the pass produces is the model's wording, not the person's fix.
    """
    return _fingerprint(row.kind, row.original_text or row.text)


_KEEP = re.compile(r"\b(\d+)\b")


def _narrow(provider, model: str, content: str, proposed: list[Candidate]) -> set[int] | None:  # noqa: ANN001
    """Ask the model which candidates are worth keeping. None means it could
    not be asked or could not be understood, and the caller keeps all of them.

    Keeping all of them on a bad reply is the deliberate direction to fail in.
    The alternative, dropping everything the model did not explicitly bless,
    hands a model that answers with prose the power to empty this feature
    silently, and silence is the failure mode this whole section exists to
    prevent.
    """
    if provider is None:
        return None
    listed = "\n".join(f"{i}. {item.text}" for i, item in enumerate(proposed))
    system = (
        "You are reviewing sentences taken from one of the user's own notes. "
        "Some are worth remembering as a claim the note makes or a question it "
        "leaves open; some are chatter. Reply with only the numbers worth "
        "keeping, separated by spaces. Reply with nothing if none are."
    )
    try:
        reply = provider.chat(
            model,
            [{"role": "system", "content": system}, {"role": "user", "content": listed}],
        )
    except Exception as exc:  # noqa: BLE001  # a background pass, any provider
        logger.info("night pass: the model could not be asked (%s)", exc)
        return None
    text = str((reply or {}).get("content") or "").strip()
    if not text:
        return None
    numbers = {int(n) for n in _KEEP.findall(text) if int(n) < len(proposed)}
    if not numbers:
        # Prose with no numbers in it is not an answer to this question. The
        # fake transport every provider test runs against replies exactly
        # this way, which is why the local candidates have to stand on their
        # own: see this module's docstring.
        return None
    return numbers


def _release(session: Session) -> None:
    """Commit what this pass has written so far, before a model call.

    A model call is seconds to minutes on a local runner, and SQLite has one
    write lock per database: any INSERT flushed and not committed holds it
    for the whole call, and every save the person makes meanwhile waits out
    the busy timeout and fails (ARCH-01). Committing here makes each note's
    rows their own short transaction. Facts are keyed by fingerprint and
    pairs by key, so a pass stopped half way leaves rows the next pass skips
    rather than duplicates. The session's factory does not expire on commit,
    so nothing already loaded is read again.
    """
    session.commit()


def _entries_to_read(session: Session, force: bool) -> list[Entry]:
    """The notes this run should look at, newest first.

    Without `force` that is the notes nothing has read yet, or that have been
    edited since they were last read: the cursor the plan asks for, expressed
    as a join rather than a stored timestamp so a run that crashes halfway
    leaves no cursor pointing past the notes it never reached.
    """
    # Private notes are skipped at the *write* as well as at the read, which
    # is not belt and braces: a private note's `content` is ciphertext, so a
    # pass that read one would derive sentences out of base64 and store them
    # as things the person said. The read-side filter (`_visible`) is still
    # the one that matters for a note made private after its facts existed.
    query = (
        select(Entry)
        .where(Entry.is_deleted.is_(False), Entry.is_private.is_(False))
        .order_by(Entry.id.desc())
    )
    entries = list(session.scalars(query).all())
    if force:
        return entries
    seen = dict(
        session.execute(
            select(DerivedFact.entry_id, func.max(DerivedFact.computed_at)).group_by(
                DerivedFact.entry_id
            )
        ).all()
    )
    fresh = []
    for entry in entries:
        last = seen.get(entry.id)
        if last is None or (entry.updated_at and entry.updated_at > last):
            fresh.append(entry)
    return fresh


def run(
    session: Session,
    *,
    budget: int = 2000,
    force: bool = False,
    provider=None,  # noqa: ANN001  # any Provider, or None for the local pass
    model: str = "",
    config=None,  # noqa: ANN001  # ConfigManager, duck-typed
    trigger: str = "manual",
    embeddings=None,  # noqa: ANN001  # an EmbeddingService, for passes 4 and 5
) -> dict:
    """One night pass. Returns what it did, including why it stopped.

    Never raises on a provider that is down or a note that will not parse: it
    is the body of a background task, and the worst thing it can do is take
    the scheduler with it.

    Every pass is a `NightRun` row (not a paused one: a runner switched off
    did not run), and every fact it derives carries the row's id, which is
    what the morning card (`GET /night/latest`) groups by.
    """
    if config is not None and not enabled(config, "night_shift"):
        return {"paused": True}
    # The "open questions" switch (Settings, What the notebook learned) stops
    # the pass collecting questions and pairing them with answers; the ones
    # already collected stay listed and can still be answered or dropped by
    # hand. A note read while it is off keeps its claims but not its questions
    # until it is edited or the pass is forced, the same cursor rule as any
    # note the pass has already read.
    questions_on = config is None or enabled(config, "open_questions")
    from tessellate.core.database import NightRun

    night = NightRun(trigger=trigger, budget=budget, started_at=utcnow())
    session.add(night)
    # **Committed, not flushed.** A flushed INSERT leaves this connection
    # holding SQLite's one write lock until the caller's commit, and the loop
    # below asks the model once per note while it waits: measured on
    # 2026-10-05 (ARCH-01), every save made during "Run now" failed with a
    # 500 after the 5 s busy timeout. The rule for the whole pass is read,
    # release, ask the model, then write in a short transaction of its own
    # (`_release` before every model call).
    session.commit()
    counts: dict[str, int] = {}
    models_used: set[str] = set()

    spent = 0
    scanned = 0
    derived = 0
    stopped = "done"
    try:
        _retire_not_own_questions(session)
        # **One query for what is already known, not one per note.** This read
        # asks "has this note already produced this fact", and asking it inside
        # the loop is a query per note: invisible on a fixture, and a thousand
        # round trips on a real notebook every time the pass runs. Tombstones are
        # included, because "already known" has to mean a deleted fact too or the
        # next pass brings back everything the person threw away.
        known_by_entry: dict[int, set[str]] = {}
        for row in session.scalars(select(DerivedFact)).all():
            known_by_entry.setdefault(row.entry_id, set()).add(fingerprint_of(row))
        to_read = _entries_to_read(session, force)
        templates = _template_questions(session)
        #: What the Background tasks row shows (INBOX 1006): notes read of the
        #: notes this run will reach, which the token budget may cut short.
        progress = jobruns.current("night-shift")
        reachable = min(len(to_read), max(budget // TOKENS_PER_NOTE, 0))
        progress.step(0, reachable, "Reading notes")
        progress.say(f"{len(to_read)} note{'' if len(to_read) == 1 else 's'} to read.")
        for entry in to_read:
            if spent + TOKENS_PER_NOTE > budget:
                stopped = "budget"
                progress.say("Reached the token budget, so it stopped reading.")
                break
            content = entry.content or ""
            spent += TOKENS_PER_NOTE
            scanned += 1
            progress.step(scanned, reachable)
            if scanned % 25 == 0:
                progress.say(f"Read {scanned} of {reachable} notes, {derived} fact{'' if derived == 1 else 's'} found so far.")
            proposed = _proposed(content, questions_on, templates)
            if not proposed:
                continue

            known = known_by_entry.setdefault(entry.id, set())
            # `known` grows as this note's candidates are taken, not only from what
            # was already stored: a note that says the same sentence twice has two
            # spans and one fact, and without this it would get a row per
            # occurrence on the first run and none on any run after (the stored
            # row would then match both).
            kept: list[Candidate] = []
            for item in proposed:
                mark = _fingerprint(item.kind, item.text)
                if mark in known:
                    continue
                known.add(mark)
                kept.append(item)
            proposed = kept
            if not proposed:
                continue

            decided_by = "local"
            cost = int(len(content) * TOKENS_PER_CHAR)
            if provider is not None and model and spent + cost <= budget:
                spent += cost
                _release(session)
                model_gate.yield_to_interactive()
                kept = _narrow(provider, model, content, proposed)
                if kept is not None:
                    proposed = [item for i, item in enumerate(proposed) if i in kept]
                    decided_by = model

            for item in proposed:
                session.add(
                    DerivedFact(
                        entry_id=entry.id,
                        kind=item.kind,
                        text=item.text,
                        span_start=item.start,
                        span_end=item.end,
                        model=decided_by,
                        confidence=item.confidence,
                        computed_at=utcnow(),
                        run_id=night.id,
                    )
                )
                derived += 1
                counts[item.kind] = counts.get(item.kind, 0) + 1
                models_used.add(decided_by)
        if stopped == "done":
            progress.say(f"Read {scanned} note{'' if scanned == 1 else 's'}, found {derived} fact{'' if derived == 1 else 's'}.")
            # Passes 4 and 5 read the rows pass 3 just added, by id.
            session.flush()
            spent, paired, stopped = _pair_passes(
                session,
                night,
                spent=spent,
                budget=budget,
                provider=provider,
                model=model,
                embeddings=embeddings,
                counts=counts,
                models_used=models_used,
                questions_on=questions_on,
                read=to_read[:scanned],
            )
            derived += paired
    except BaseException:
        stopped = "error"
        raise
    finally:
        # In a `finally`: a pass that dies half way (the model server
        # dropped, the app quit) has already committed its earlier notes
        # (`_release`), so its row must still say when it stopped and why.
        night.finished_at = utcnow()
        night.scanned = scanned
        night.derived = derived
        night.tokens_spent = spent
        night.stopped_reason = stopped
        night.counts = counts
        night.model = ", ".join(sorted(models_used)) or "local"
        session.flush()
    return {
        "paused": False,
        "run_id": night.id,
        "scanned": scanned,
        "derived": derived,
        "tokens_spent": spent,
        "budget": budget,
        "stopped_reason": stopped,
    }


# --- passes 4 and 5: tensions and answered questions (I1, H1; row 5) ----------

#: How many neighbours each new claim or question is compared with. The plan's
#: "top-k": past three the fourth-nearest claim is rarely about the same thing,
#: and every pair is a model call.
PAIR_NEIGHBOURS = 3

#: How alike two sentences must be before they are worth comparing at all.
#: Cosine when an embedding backend is up (a sentence pair, not a note pair, so
#: higher than the notes' `TENSION_CANDIDATE_THRESHOLD`), the share of shared
#: meaningful words otherwise.
PAIR_COSINE = 0.6
PAIR_WORDS = 0.34

#: What one pair costs when no model is asked: comparing two sentences
#: locally, so a budget still bounds a notebook of any size.
TOKENS_PER_PAIR = 2

_NEGATION = frozenset({"not", "no", "never", "nothing", "none", "cannot", "cant", "wont", "isnt", "arent", "wasnt", "dont", "doesnt", "didnt"})
_NUMBER = re.compile(r"\b\d+(?:[.,]\d+)?\b")


def _terms(text: str) -> set[str]:
    from tessellate.search.query import search_terms

    return {term for term in search_terms(text) if not term.isdigit()}


def _words_alike(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def _plain_words(text: str) -> set[str]:
    return {word.replace("'", "").lower() for word in re.findall(r"[A-Za-z']+", text)}


def _local_disagreement(a: str, b: str) -> str | None:
    """Two near-identical claims that differ in a number or a negation.

    The one disagreement a pass can see with no model: "the rent is 900" and
    "the rent is 950", or "the boiler is covered" and "the boiler is not
    covered". Anything subtler is the model's to judge, and without one this
    says nothing rather than guessing.
    """
    terms_a, terms_b = _terms(a), _terms(b)
    if _words_alike(terms_a, terms_b) < 0.6:
        return None
    numbers_a, numbers_b = set(_NUMBER.findall(a)), set(_NUMBER.findall(b))
    if numbers_a and numbers_b and numbers_a != numbers_b:
        return "The same thing with a different number."
    negated_a = bool(_plain_words(a) & _NEGATION)
    negated_b = bool(_plain_words(b) & _NEGATION)
    if negated_a != negated_b:
        return "The same thing, once with a not."
    return None


def _local_answer(question: str, claim: str) -> bool:
    """A later claim that holds most of what the question asks about."""
    asked = _terms(question)
    return len(asked) >= 2 and len(asked & _terms(claim)) / len(asked) >= 0.6


_JUDGE_TENSION = (
    "Two sentences from the user's own notes, written at different times. "
    "Do they disagree? Reply with one word, compatible, incompatible or "
    "unrelated, then a dash and one short line saying why."
)
_JUDGE_ANSWER = (
    "A question from the user's notes, and a sentence they wrote later. Does "
    "the sentence answer the question? Reply with one word, yes or no, then a "
    "dash and one short line saying why."
)


def _judge(provider, model: str, system: str, first: str, second: str) -> tuple[str, str] | None:  # noqa: ANN001
    """`(first word, reason)` from the model, or None when it could not be
    asked or did not answer in the shape asked for. None is "no finding",
    never a guess: a pair the model would not judge is not a tension."""
    try:
        reply = provider.chat(
            model,
            [
                {"role": "system", "content": system},
                {"role": "user", "content": f"1. {first}\n2. {second}"},
            ],
        )
    except Exception as exc:  # noqa: BLE001  # a background pass, any provider
        logger.info("night pass: the model could not judge a pair (%s)", exc)
        return None
    text = str((reply or {}).get("content") or "").strip()
    match = re.match(r"\W*([A-Za-z]+)\W*(.*)", text, flags=re.S)
    if not match:
        return None
    word = match.group(1).lower()
    reason = " ".join(match.group(2).split())[:200]
    return word, reason


class _Similar:
    """The sentences nearest one sentence, among a fixed pool.

    Words first, through an inverted index over the pool's meaningful terms:
    two claims that disagree are about the same thing and nearly always say
    so in the same words, and scoring every pair of a first run's twenty
    thousand claims directly is minutes, where the index reads only the
    claims that share a term. Meaning second, when a backend is up: the best
    few by words are re-scored by cosine, so "the flat costs 900" finds "rent
    went up to 950" through what they mean, and only those few are embedded.
    """

    #: How many word-matched candidates the meaning re-score looks at.
    RESCORE = 8
    #: The words floor below which a candidate is not even re-scored.
    PREFILTER = 0.15

    def __init__(self, embeddings, pool: list[DerivedFact]) -> None:  # noqa: ANN001
        self._embeddings = None
        try:
            if embeddings is not None and embeddings.is_ready():
                self._embeddings = embeddings
        except Exception:  # noqa: BLE001  # no backend is a state
            self._embeddings = None
        self.by_meaning = self._embeddings is not None
        self.embedded = 0
        self._vectors: dict[str, Any] = {}
        self._pool = pool
        self._terms = [_terms(row.text) for row in pool]
        self._postings: dict[str, list[int]] = {}
        for index, terms in enumerate(self._terms):
            for term in terms:
                self._postings.setdefault(term, []).append(index)

    def _vector(self, text: str):  # noqa: ANN202
        if text not in self._vectors:
            vector = None
            try:
                raw = self._embeddings.embed_text(text)
                self.embedded += 1
                if raw is not None:
                    import numpy as np

                    vector = np.asarray(raw, dtype="float32")
                    norm = float(np.linalg.norm(vector))
                    vector = vector / norm if norm else None
            except Exception:  # noqa: BLE001  # one sentence that will not embed
                vector = None
            self._vectors[text] = vector
        return self._vectors[text]

    def nearest(self, text: str, allowed, k: int = PAIR_NEIGHBOURS) -> list[tuple[float, DerivedFact]]:  # noqa: ANN001
        """Up to `k` pool rows for which `allowed(row)` holds, best first."""
        terms = _terms(text)
        #: `Counter.update` counts in C; the per-posting dict get and set was
        #: the next biggest cost in this loop (ledger 1542).
        shared: Counter[int] = Counter()
        for term in terms:
            shared.update(self._postings.get(term, ()))
        by_words = []
        #: **The same sentence again is not a neighbour.** A notebook that
        #: says "the rent is 950" in three notes has three identical claims,
        #: and by meaning they are each other's nearest (cosine 1.0): they
        #: filled every one of the k places and the 900 that disagrees with
        #: them was never compared (nightpairs.js, the fifth seeding). One
        #: copy of each wording, and never the query's own.
        seen_texts = {" ".join(text.lower().split())}
        for index, count in shared.items():
            #: `count` is the size of the intersection (one posting hit per
            #: shared term), so the union is a sum, not a new set per
            #: candidate: the set built here was most of the pairing phase
            #: (ledger 1542, 4.4 of 7.4 s at 800 claims).
            union = len(terms) + len(self._terms[index]) - count
            score = count / union if union > 0 else 0.0
            if score >= self.PREFILTER and allowed(self._pool[index]):
                by_words.append((score, self._pool[index]))
        by_words.sort(key=lambda pair: (-pair[0], pair[1].id))
        unique = []
        for score, row in by_words:
            wording = " ".join(row.text.lower().split())
            if wording not in seen_texts:
                seen_texts.add(wording)
                unique.append((score, row))
        by_words = unique
        if not self.by_meaning:
            return [pair for pair in by_words if pair[0] >= PAIR_WORDS][:k]
        query = self._vector(text)
        if query is None:
            return [pair for pair in by_words if pair[0] >= PAIR_WORDS][:k]
        rescored = []
        for _words, row in by_words[: self.RESCORE]:
            vector = self._vector(row.text)
            if vector is not None and vector.shape == query.shape:
                cosine = float(vector @ query)
                if cosine >= PAIR_COSINE:
                    rescored.append((cosine, row))
        rescored.sort(key=lambda pair: (-pair[0], pair[1].id))
        return rescored[:k]


def _pair_key(kind: str, a: int, b: int) -> str:
    low, high = sorted((a, b)) if kind == "tension" else (a, b)
    return f"{kind}:{low}:{high}"


def _known_pairs(session: Session) -> set[str]:
    """Every pair a pass has recorded, tombstones included, so a dismissed
    tension or answer is never found again."""
    import json

    known: set[str] = set()
    for kind, payload in session.execute(
        select(DerivedFact.kind, DerivedFact.payload).where(DerivedFact.kind.in_(PAIR_KINDS))
    ).all():
        try:
            key = json.loads(payload or "{}").get("pair")
        except ValueError:
            key = None
        if key:
            known.add(str(key))
    return known


def _open_claims_and_questions(session: Session) -> tuple[list[DerivedFact], list[DerivedFact]]:
    rows = list(session.scalars(_visible(select(DerivedFact)).where(DerivedFact.kind.in_(("claim", "question")))).all())
    return [row for row in rows if row.kind == "claim"], [row for row in rows if row.kind == "question"]


def _written(session: Session, entry_ids: set[int]) -> dict[int, datetime]:
    return {
        entry_id: created
        for entry_id, created in session.execute(
            select(Entry.id, Entry.created_at).where(Entry.id.in_(entry_ids))
        ).all()
    }


def _pair_fact(kind: str, row: DerivedFact, other: DerivedFact, pair: str, reason: str, decided_by: str, confidence: float, run_id: int, similarity: float) -> DerivedFact:
    """A tension or an answer, stored on the side that came later.

    `entry_id` and the span are the later sentence's, so the row opens the
    note that changed things; the payload names the other side by fact, note,
    words and span, which is all the card and the questions view need without
    a join back to a row that may since have been edited or deleted.
    """
    import json

    return DerivedFact(
        entry_id=row.entry_id,
        kind=kind,
        text=row.text,
        span_start=row.span_start,
        span_end=row.span_end,
        model=decided_by,
        confidence=confidence,
        computed_at=utcnow(),
        run_id=run_id,
        payload=json.dumps(
            {
                "pair": pair,
                "fact_id": row.id,
                "other_fact_id": other.id,
                "other_entry_id": other.entry_id,
                "other_text": other.text,
                "other_span": [other.span_start, other.span_end],
                "reason": reason,
                "similarity": round(float(similarity), 3),
            }
        ),
    )


def _pair_passes(
    session: Session,
    night,  # noqa: ANN001  # NightRun
    *,
    spent: int,
    budget: int,
    provider,  # noqa: ANN001
    model: str,
    embeddings,  # noqa: ANN001
    counts: dict[str, int],
    models_used: set[str],
    questions_on: bool = True,
    read: list[Entry] | None = None,
) -> tuple[int, int, str]:
    """Passes 4 and 5 over what pass 3 just found. Returns `(spent, derived,
    stopped)`; never raises past a single pair.

    Only pairs with at least one side new this run are compared: an old pair
    was compared on the night it became a pair, so a second run with nothing
    new spends nothing here, which is the plan's "zero tokens" test.
    """
    claims, questions = _open_claims_and_questions(session)
    new_claims = [row for row in claims if row.run_id == night.id]
    new_questions = [row for row in questions if row.run_id == night.id] if questions_on else []
    # With no model, a later sentence that states what a question asks
    # answers it (INBOX 1466). Before the early return: a note read this run
    # with no claim or question in it can still answer an older question.
    by_rule = _answers_by_rule(
        session, night, questions, read, questions_on=questions_on, provider=provider, model=model, counts=counts, models_used=models_used
    )
    if not (new_claims or new_questions):
        return spent, by_rule, "done"
    progress = jobruns.current("night-shift")
    progress.say(
        f"Comparing {len(new_claims)} new claim{'' if len(new_claims) == 1 else 's'} "
        f"and {len(new_questions)} question{'' if len(new_questions) == 1 else 's'} against the rest of your notes."
    )
    similar = _Similar(embeddings, claims)
    known = _known_pairs(session)
    written = _written(session, {row.entry_id for row in claims + questions})
    derived = by_rule

    def charge(first: str, second: str) -> int:
        if provider is not None and model:
            return int((len(first) + len(second) + 200) * TOKENS_PER_CHAR)
        return TOKENS_PER_PAIR

    # Pass 4: each new claim against the claims of other notes.
    for claim_index, claim in enumerate(new_claims):
        progress.step(claim_index, len(new_claims), "Comparing claims")

        def other_note(row, claim=claim):  # noqa: ANN001, ANN202
            return row.entry_id != claim.entry_id

        for score, other in similar.nearest(claim.text, other_note):
            pair = _pair_key("tension", claim.id, other.id)
            if pair in known:
                continue
            cost = charge(claim.text, other.text)
            if spent + cost > budget:
                return spent, derived, "budget"
            spent += cost
            known.add(pair)
            later, earlier = (claim, other)
            if written.get(other.entry_id) and written.get(claim.entry_id) and written[other.entry_id] > written[claim.entry_id]:
                later, earlier = other, claim
            found: tuple[str, str, float] | None = None
            if provider is not None and model:
                _release(session)
                model_gate.yield_to_interactive()
                judged = _judge(provider, model, _JUDGE_TENSION, earlier.text, later.text)
                if judged and judged[0] == "incompatible":
                    found = (model, judged[1], 0.7)
            else:
                reason = _local_disagreement(earlier.text, later.text)
                if reason:
                    found = ("local", reason, 0.5)
            if found:
                session.add(_pair_fact("tension", later, earlier, pair, found[1], found[0], found[2], night.id, score))
                derived += 1
                counts["tension"] = counts.get("tension", 0) + 1
                models_used.add(found[0])

    # Pass 5: open questions against claims written later, in other notes,
    # judged by the model (with none, `_answers_by_rule` did this above).
    answered = {
        int(json_payload_value(row.payload, "other_fact_id") or 0)
        for row in session.scalars(
            select(DerivedFact).where(DerivedFact.kind == "answered", DerivedFact.deleted_at.is_(None))
        ).all()
    }
    pending_questions = _for_the_model(questions, questions_on, provider, model)
    progress.step(0, len(pending_questions) or None, "Matching questions to answers")
    for question_index, question in enumerate(pending_questions):
        progress.step(question_index, len(pending_questions))
        if question.id in answered:
            continue
        asked_at = written.get(question.entry_id)
        if asked_at is None:
            continue

        def written_later(row, question=question, asked_at=asked_at):  # noqa: ANN001, ANN202
            at = written.get(row.entry_id)
            return (
                row.entry_id != question.entry_id
                and at is not None
                and at > asked_at
                and (question.run_id == night.id or row.run_id == night.id)
            )

        for score, claim in similar.nearest(question.text, written_later):
            pair = _pair_key("answered", question.id, claim.id)
            if pair in known:
                continue
            cost = charge(question.text, claim.text)
            if spent + cost > budget:
                return spent, derived, "budget"
            spent += cost
            known.add(pair)
            _release(session)
            model_gate.yield_to_interactive()
            judged = _judge(provider, model, _JUDGE_ANSWER, question.text, claim.text)
            found = (model, judged[1], 0.7) if judged and judged[0] == "yes" else None
            if found:
                session.add(_pair_fact("answered", claim, question, pair, found[1], found[0], found[2], night.id, score))
                derived += 1
                counts["answered"] = counts.get("answered", 0) + 1
                models_used.add(found[0])
                answered.add(question.id)
                break
    progress.say(f"Finished comparing: {derived} pairing{'' if derived == 1 else 's'} found.")
    return spent, derived, "done"


#: The most later notes one rule pass reads for answers, newest first.
ANSWER_NOTES = 300
_RULE_REASON = "States what the question asks about, in a note written after it."


def _answered_ids(session: Session) -> set[int]:
    return {
        int(json_payload_value(payload, "other_fact_id") or 0)
        for payload in session.scalars(
            select(DerivedFact.payload).where(DerivedFact.kind == "answered", DerivedFact.deleted_at.is_(None))
        )
    }


def _heading(content: str, question: str) -> str:
    """A note's first sentence, its title in effect, unless it is the
    question itself."""
    first = sentences(content.lstrip().split("\n", 1)[0].lstrip("# ")) if content.strip() else []
    return first[0][0] if first and first[0][0] != question else ""


def _rule_notes(session: Session, since: datetime) -> list[tuple[int, datetime, list[tuple[str, int, int]]]]:
    """The newest `ANSWER_NOTES` readable notes written after `since`, each
    with the sentences in it that can answer."""
    rows = session.execute(
        select(Entry.id, Entry.content, Entry.created_at)
        .where(Entry.is_deleted.is_(False), Entry.is_private.is_(False), Entry.created_at > since)
        .order_by(Entry.created_at.desc())
        .limit(ANSWER_NOTES)
    ).all()
    return [(eid, at, question_cues.answer_sentences(sentences(content or ""))) for eid, content, at in rows]


def _links(session: Session, entry_ids: set[int]) -> set[frozenset[int]]:
    pairs = session.execute(
        select(EntryLink.source_entry_id, EntryLink.target_entry_id).where(
            EntryLink.source_entry_id.in_(entry_ids) | EntryLink.target_entry_id.in_(entry_ids)
        )
    ).all()
    return {frozenset(pair) for pair in pairs}


def _for_the_model(questions: list[DerivedFact], questions_on: bool, provider, model: str) -> list[DerivedFact]:  # noqa: ANN001
    """The questions pass 5 asks the model about: none with no model, where
    `_answers_by_rule` has matched them already."""
    return list(questions) if questions_on and provider is not None and model else []


def _due_questions(session: Session, night, questions: list[DerivedFact], read_ids: set[int]) -> list[DerivedFact]:  # noqa: ANN001
    """The open questions worth comparing this run: new ones, or every one
    when a note was read that might answer it."""
    answered = _answered_ids(session)
    return [q for q in questions if q.id not in answered and (q.run_id == night.id or read_ids)]


def _asked_notes(session: Session, due: list[DerivedFact]) -> dict[int, tuple[str, datetime]]:
    if not due:
        return {}
    rows = session.execute(
        select(Entry.id, Entry.content, Entry.created_at).where(Entry.id.in_({q.entry_id for q in due}))
    ).all()
    return {eid: (content or "", at) for eid, content, at in rows if at is not None}


def _rule_answer(question: DerivedFact, asked: tuple[str, datetime], notes, links: set[frozenset[int]], read_ids: set[int], run_id: int):  # noqa: ANN001, ANN202
    """The best later sentence for one question, from `_rule_notes`."""
    content, at = asked
    fresh = question.run_id == run_id
    later = [
        (eid, frozenset((eid, question.entry_id)) in links, said)
        for eid, written, said in notes
        if eid != question.entry_id and written > at and (fresh or eid in read_ids)
    ]
    return question_cues.best_answer(question_cues.subject(question.text, _heading(content, question.text)), later)


def _answers_by_rule(
    session: Session,
    night,  # noqa: ANN001  # NightRun
    questions: list[DerivedFact],
    read: list[Entry] | None,
    *,
    questions_on: bool,
    provider,  # noqa: ANN001
    model: str,
    counts: dict[str, int],
    models_used: set[str],
) -> int:
    """Pass 5 with no model (INBOX 1466): each open question against the
    sentences of notes written after it, stored as the same `answered` row
    the model's pass writes. Only a question new this run, or a note read
    this run, is compared, so a run with nothing new compares nothing."""
    if not questions_on or (provider is not None and model):
        return 0
    read_ids = {entry.id for entry in read or []}
    due = _due_questions(session, night, questions, read_ids)
    asked = _asked_notes(session, due)
    due = [q for q in due if q.entry_id in asked]
    if not due:
        return 0
    notes = _rule_notes(session, min(asked[q.entry_id][1] for q in due))
    links = _links(session, set(asked))
    known = _known_pairs(session)
    found = 0
    for question in due:
        best = _rule_answer(question, asked[question.entry_id], notes, links, read_ids, night.id)
        pair = f"answered:{question.id}:s{best[1]}:{best[3]}" if best else ""
        if not best or pair in known:
            continue
        value, eid, text, start, end = best
        sentence = SimpleNamespace(id=None, entry_id=eid, text=text, span_start=start, span_end=end)
        session.add(_pair_fact("answered", sentence, question, pair, _RULE_REASON, "local", 0.4, night.id, value))
        known.add(pair)
        found += 1
    if found:
        counts["answered"] = counts.get("answered", 0) + found
        models_used.add("local")
    return found


def json_payload_value(payload: str | None, key: str):  # noqa: ANN201
    """One value from a fact's JSON payload, or None."""
    import json

    try:
        return (json.loads(payload or "{}") or {}).get(key)
    except (ValueError, AttributeError):
        return None


# --- the morning card -----------------------------------------------------------

#: Facts shown per kind on the card; the review list pages through the rest.
CARD_SAMPLES = 3


def _run_json(run) -> dict:  # noqa: ANN001  # a NightRun
    return {
        "id": run.id,
        "trigger": run.trigger,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "scanned": run.scanned,
        "derived": run.derived,
        "tokens_spent": run.tokens_spent,
        "budget": run.budget,
        "stopped_reason": run.stopped_reason,
        "model": run.model,
    }


def visible_counts(session: Session, run_id: int) -> dict[str, int]:
    """What a run found that the person can still see, by kind."""
    rows = session.execute(
        _visible(select(DerivedFact.kind, func.count()).select_from(DerivedFact))
        .where(DerivedFact.run_id == run_id)
        .group_by(DerivedFact.kind)
    ).all()
    return {kind: int(n) for kind, n in rows if n}


def run_facts(
    session: Session, run_id: int, *, kind: str | None = None, limit: int = 50, offset: int = 0
) -> tuple[list[DerivedFact], int]:
    """One page of what a run found, in note order, plus the total."""

    def narrowed(statement):  # noqa: ANN001, ANN202  # a select() over DerivedFact
        statement = statement.where(DerivedFact.run_id == run_id)
        return statement.where(DerivedFact.kind == kind) if kind else statement

    total = session.scalar(narrowed(_visible(select(func.count()).select_from(DerivedFact))))
    rows = list(
        session.scalars(
            narrowed(_visible(select(DerivedFact)))
            .order_by(DerivedFact.entry_id.desc(), DerivedFact.span_start, DerivedFact.id)
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return rows, int(total or 0)


def latest_card(session: Session) -> dict:
    """The "while you were away" card: the latest run, what it found that is
    still visible, a few of each kind, and, when the latest found nothing, the
    last run that did, so a quiet night does not blank the morning."""
    from tessellate.core.database import NightRun

    latest = session.scalars(select(NightRun).order_by(NightRun.id.desc()).limit(1)).first()
    if latest is None:
        return {"run": None, "counts": {}, "samples": {}, "previous": None}
    counts = visible_counts(session, latest.id)
    samples: dict[str, list[dict]] = {}
    for kind in sorted(counts):
        rows, _total = run_facts(session, latest.id, kind=kind, limit=CARD_SAMPLES)
        samples[kind] = [as_json(row) for row in rows]
    previous = None
    if not counts:
        for earlier in session.scalars(
            select(NightRun)
            .where(NightRun.id < latest.id, NightRun.derived > 0)
            .order_by(NightRun.id.desc())
            .limit(5)
        ):
            found = visible_counts(session, earlier.id)
            if found:
                previous = {**_run_json(earlier), "counts": found}
                break
    return {"run": _run_json(latest), "counts": counts, "samples": samples, "previous": previous}


# --- reading and correcting ---------------------------------------------------


def _visible(query):  # noqa: ANN001  # a select() of DerivedFact
    """Only rows the person can actually open.

    Joined rather than copied onto the fact: a note made private *after* its
    facts were derived has to disappear from this listing, and the only way a
    stored copy of "is it private" gets that right is if every writer of
    `is_private` remembers to update it here too (Brief 24, decision 4).
    """
    return (
        query.join(Entry, Entry.id == DerivedFact.entry_id)
        .where(
            DerivedFact.deleted_at.is_(None),
            Entry.is_deleted.is_(False),
            Entry.is_private.is_(False),
        )
    )


def listing(
    session: Session,
    *,
    kind: str | None = None,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[DerivedFact], int]:
    """One page of the table, newest first, plus the total behind it.

    The page and the count are narrowed by the same function, applied twice,
    rather than by two lists of `where` clauses that have to be kept in step.
    They were not: the count applied `kind` and skipped `q`, so a search
    returned forty rows and a total of a hundred and twenty, and the table's
    pager offered two more pages with nothing in them. Nothing caught it
    because nothing called this route until the Settings section was built.
    """

    def narrowed(statement):  # noqa: ANN001, ANN202  # any select() over DerivedFact
        if kind:
            statement = statement.where(DerivedFact.kind == kind)
        if q:
            from tessellate.core.database import LIKE_ESCAPE, like_escape

            statement = statement.where(
                DerivedFact.text.like(f"%{like_escape(q)}%", escape=LIKE_ESCAPE)
            )
        return statement

    total = session.scalar(narrowed(_visible(select(func.count()).select_from(DerivedFact))))
    rows = list(
        session.scalars(
            narrowed(_visible(select(DerivedFact)))
            .order_by(DerivedFact.computed_at.desc(), DerivedFact.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return rows, int(total or 0)


def visible(session: Session, fact_id: int) -> DerivedFact | None:
    """One row, if the person is allowed to see it."""
    return session.scalars(
        _visible(select(DerivedFact)).where(DerivedFact.id == fact_id)
    ).first()


def as_json(row: DerivedFact) -> dict:
    """One row in the shape the table and the export both read."""
    return {
        "id": row.id,
        "entry_id": row.entry_id,
        "kind": row.kind,
        "text": row.text,
        "span": [row.span_start, row.span_end],
        "model": row.model,
        "confidence": row.confidence,
        "computed_at": row.computed_at.isoformat() if row.computed_at else None,
        "edited_by_user": bool(row.edited_by_user),
        "original_text": row.original_text,
        #: A pair's other side (a tension's other claim, an answer's
        #: question), or None for a claim or a question.
        "pair": _pair_json(row),
    }


def _pair_json(row: DerivedFact) -> dict | None:
    if row.kind not in PAIR_KINDS or not row.payload:
        return None
    import json

    try:
        payload = json.loads(row.payload) or {}
    except ValueError:
        return None
    return {
        "entry_id": payload.get("other_entry_id"),
        "fact_id": payload.get("other_fact_id"),
        "text": payload.get("other_text"),
        "span": payload.get("other_span"),
        "reason": payload.get("reason") or "",
    }


def edit(session: Session, row: DerivedFact, text: str) -> DerivedFact:
    """Replace what a fact says. The model never gets it back."""
    if not row.edited_by_user:
        row.original_text = row.text
    row.text = text
    row.edited_by_user = True
    session.flush()
    return row


def reset(session: Session, row: DerivedFact) -> DerivedFact:
    """Put the model's own words back."""
    if row.edited_by_user and row.original_text is not None:
        row.text = row.original_text
    row.edited_by_user = False
    row.original_text = None
    session.flush()
    return row


def remove(session: Session, row: DerivedFact, at: datetime | None = None) -> None:
    """Tombstone a fact so no later run brings it back."""
    row.deleted_at = at or utcnow()
    session.flush()


def tombstoned(session: Session, fact_id: int) -> DerivedFact | None:
    """A deleted fact the person could have opened before it went (Undo's way back)."""
    return session.scalars(
        select(DerivedFact)
        .join(Entry, Entry.id == DerivedFact.entry_id)
        .where(
            DerivedFact.id == fact_id,
            DerivedFact.deleted_at.is_not(None),
            Entry.is_deleted.is_(False),
            Entry.is_private.is_(False),
        )
    ).first()


def restore(session: Session, row: DerivedFact) -> None:
    """Undo of `remove`: the fact is live again, and the next run may keep it."""
    row.deleted_at = None
    session.flush()


def _forgotten_event_type() -> str:
    import sys

    tensions = sys.modules.get("tessellate.ai.tensions")
    return tensions.EVENT_TYPE if tensions is not None else "tension"


def snapshot(session: Session) -> dict[str, list[dict]]:
    """Every row `forget` is about to delete, as plain dicts (INBOX 898), so
    `unforget` can put them back. Taken before, in the same transaction."""
    from sqlalchemy import or_

    from tessellate.core.database import AuditLog, DerivedTension, NightRun, NoteScore

    def rows(model, *where):  # noqa: ANN001, ANN202
        return [undo_bin.row_dict(row) for row in session.scalars(select(model).where(*where))]

    return {
        "facts": rows(DerivedFact),
        "runs": rows(NightRun),
        "scores": rows(NoteScore),
        "tensions": rows(DerivedTension),
        "events": rows(
            AuditLog, or_(AuditLog.action == "correction", AuditLog.entity_type == _forgotten_event_type())
        ),
    }


def unforget(session: Session, saved: dict[str, list[dict]]) -> dict[str, int]:
    """Put back what `snapshot` took. A row whose id is taken again is left alone."""
    import sys

    from tessellate.core.database import AuditLog, DerivedTension, NightRun, NoteScore

    put: dict[str, int] = {}
    for key, model in (
        ("runs", NightRun),
        ("facts", DerivedFact),
        ("scores", NoteScore),
        ("events", AuditLog),
        ("tensions", DerivedTension),
    ):
        count = 0
        for data in saved.get(key, []):
            if session.get(model, data["id"]) is None:
                session.add(undo_bin.row_from(model, data))
                count += 1
        session.flush()
        put[key] = count
    tensions = sys.modules.get("tessellate.ai.tensions")
    if tensions is not None:
        tensions._built.clear()
    return put


def forget(session: Session) -> dict[str, int]:
    """Everything the app derived, gone. Nothing the person wrote is touched.

    Tombstones go too: "forget everything" means the table is empty, not that
    it is full of rows saying what used to be there. The next run is then free
    to derive from scratch, which is what a person who pressed this asked for.
    """
    from tessellate.core.database import AuditLog, NightRun, NoteScore

    facts = session.query(DerivedFact).delete(synchronize_session=False)
    # The runs go with what they found: a card saying "found 4 claims" over
    # an empty table is the ghost this function exists not to leave.
    session.query(NightRun).delete(synchronize_session=False)
    scores = session.query(NoteScore).delete(synchronize_session=False)
    corrections = (
        session.query(AuditLog)
        .filter(AuditLog.action == "correction")
        .delete(synchronize_session=False)
    )
    # The tension events (found, accepted, dismissed) are derived findings and
    # the decisions on them, the same two things as the facts and the
    # corrections above; the table built from them goes with them. A
    # `contradicts` link stays (a person's link), so the table rebuilt next
    # lists it as accepted, and nothing else.
    #: Read from the loaded module rather than imported: `ai/tensions.py`
    #: reaches `core/events`, and an import here (even in the function) puts
    #: it in the cycle `tests/test_import_module_cycles.py` counts. A module
    #: never loaded has built no table to forget.
    import sys

    from tessellate.core.database import DerivedTension

    tensions = sys.modules.get("tessellate.ai.tensions")
    event_type = tensions.EVENT_TYPE if tensions is not None else "tension"
    session.query(AuditLog).filter(AuditLog.entity_type == event_type).delete(synchronize_session=False)
    session.query(DerivedTension).delete(synchronize_session=False)
    if tensions is not None:
        tensions._built.clear()
    session.flush()
    return {"facts": facts, "corrections": corrections, "scores": scores}


def runner_enabled(name: str) -> bool:
    """Is this runner switched on? Asked by the runner, before every pass.

    The one place in this module that reaches for the app's config, so that
    everything above it can be called with nothing around it. A runner invoked
    with no app state (a unit test of the arithmetic, a script) gets True
    rather than an exception, because a missing config means "nobody has
    switched this off", not "stop".
    """
    try:
        from tessellate.core import deps

        return enabled(deps.get_config(), name)
    except Exception:  # noqa: BLE001  # no app state: nothing has been switched off
        return True
