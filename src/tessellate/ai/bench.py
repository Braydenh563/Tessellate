"""The model bench: which installed model is best on *this* notebook
(WORLD_CLASS_PLAN 15, I8; 18, H3).

Every local-AI app tells its owner to "try a model". This one measures each
installed model against the owner's own notes, on their own machine, and
shows the failures, so the recommendation can be checked rather than trusted.
Nothing leaves the computer: the only requests are to the model server the
person already configured.

**The held-out set needs no model to build.** `build_set` samples notes the
person filed themselves (a category other than Uncategorised), and from each
picks one sentence with two distinctive words, words that occur in that note
and in no other sampled note. Three tasks follow from one item:

- *filing*: the note, cold, with the notebook's categories offered, through
  the same system prompt and prompt builder the janitor uses, so the bench
  scores the filing a model would actually do here; right when it names the
  note's own category;
- *citation*: three notes, numbered, the right one among two others, and a
  question naming the two words; right when the answer cites the right
  number. The answer is also timed and its tokens counted;
- *tools*: one tool offered (`find_note`), and an ask to look the first word
  up; right when the model calls that tool with that word.

**Deterministic.** The sample is seeded by the notebook's own ids, so two
runs over an unchanged notebook score the same items and differ only where
the model itself differs (the plan's gate: within two points on a rerun).

**Bounded.** A wall-clock budget and a stop event are checked between every
task, so a slow model or an impatient person never leaves a run that cannot
end; the report says which ended it (`stopped`: "stopped", "budget" or "").
"""

from __future__ import annotations

import json
import logging
import random
import re
import statistics
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai.fence import fence
from tessellate.core.database import Category, Entry
from tessellate.core.logbuffer import safe_value

logger = logging.getLogger("tessellate.ai.bench")

UNCATEGORISED = "Uncategorised"

#: The plan's forty notes is the default for a real run; the route lets a
#: person pick fewer for a quick look.
DEFAULT_SIZE = 40
MAX_SIZE = 80
#: Below this the bench says so rather than ranking models on three notes,
#: which would be a coin toss wearing a table.
MIN_NOTES = 6
#: The plan's gate is a 30-minute run over two models; the default budget is
#: the same half hour, and the route caps what a caller may ask for.
DEFAULT_BUDGET_SECONDS = 30 * 60
#: Each model gets this many tool tasks (the plan's "five scripted").
TOOL_TASKS = 5
#: Failures kept per model per task kind: enough to see a pattern, few
#: enough to read.
FAILURES_PER_TASK = 3

_WORD = re.compile(r"[A-Za-z][A-Za-z'-]{3,}")
_STOP = frozenset(
    "about above after again against also because been before being below between both "
    "could does doing down during each from further have having here into itself just "
    "more most much must only other over same should some such than that their them then "
    "there these they this those through under until very were what when where which "
    "while will with would your yours every never always first".split()
)
_CITE = re.compile(r"\[(\d{1,2})\]")

FIND_NOTE_TOOL = {
    "type": "function",
    "function": {
        "name": "find_note",
        "description": "Search the notebook for notes about a word or phrase.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "What to search for."}},
            "required": ["query"],
        },
    },
}

ANSWER_SYSTEM = (
    "You answer from the numbered notes below and nothing else. Name the note "
    "you used by its number in square brackets, like [2], then quote the "
    "sentence that answers."
)
TOOL_SYSTEM = "You are the assistant of a personal notebook. Use the tool you are given."


@dataclass
class Item:
    """One held-out note and the question it answers."""

    entry_id: int
    category: str
    content: str
    sentence: str
    terms: tuple[str, str]

    @property
    def question(self) -> str:
        first, second = self.terms
        return f"Which note mentions “{first}” and “{second}”? Quote the sentence."


@dataclass
class Failure:
    task: str
    entry_id: int
    question: str
    expected: str
    got: str

    def as_dict(self) -> dict:
        return {
            "task": self.task,
            "entry_id": self.entry_id,
            "question": self.question,
            "expected": self.expected,
            "got": safe_value(self.got, 160),
        }


#: The mean score a model needs before the bench calls it recommended.
RECOMMEND_FLOOR = 0.5


@dataclass
class ModelScore:
    model: str
    filing: list[float] = field(default_factory=list)
    citation: list[float] = field(default_factory=list)
    tools: list[float] = field(default_factory=list)
    latency_ms: list[float] = field(default_factory=list)
    tokens: list[int] = field(default_factory=list)
    failures: list[Failure] = field(default_factory=list)
    errors: int = 0

    def _fail(self, failure: Failure) -> None:
        if sum(1 for f in self.failures if f.task == failure.task) < FAILURES_PER_TASK:
            self.failures.append(failure)

    @staticmethod
    def _mean(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 3) if values else None

    @property
    def score(self) -> float:
        parts = [m for m in (self._mean(self.filing), self._mean(self.citation), self._mean(self.tools)) if m is not None]
        return round(sum(parts) / len(parts), 3) if parts else 0.0

    def as_dict(self) -> dict:
        return {
            "model": self.model,
            "score": self.score,
            "filing": self._mean(self.filing),
            "citation": self._mean(self.citation),
            "tools": self._mean(self.tools),
            "answer_ms": round(statistics.median(self.latency_ms)) if self.latency_ms else None,
            "tokens": round(sum(self.tokens) / len(self.tokens)) if self.tokens else None,
            "tasks": len(self.filing) + len(self.citation) + len(self.tools),
            "errors": self.errors,
            "failures": [f.as_dict() for f in self.failures],
        }


# --- scoring shared with the offline harness ---------------------------------


def citation_score(wanted: set, got: set) -> tuple[float, str]:
    """The share of `wanted` citations present in `got`, and what was missed.

    The one definition of a citation score: `tests/eval/scoring.py` (the
    offline harness over the fixture notebook) imports it, so the harness CI
    runs and the bench a person runs cannot drift apart. Extra citations are
    not penalised, which is the harness's long-standing rule: an answer that
    cites the right note and one more is still right.
    """
    if not wanted:
        return 1.0, ""
    missing = [pair for pair in sorted(wanted) if pair not in got]
    if missing:
        return (len(wanted) - len(missing)) / len(wanted), f"did not cite {missing} (cited: {sorted(got)})"
    return 1.0, ""


def filing_right(reply: str, expected: str) -> tuple[bool, str]:
    """Did the model name the expected category? Returns (right, what it said)."""
    from tessellate.ai.janitor import _extract_json  # the janitor's own parser

    try:
        got = str(_extract_json(reply)["category"]).strip()
    except (ValueError, KeyError, TypeError):
        got = (reply or "").strip()[:60]
        return False, got
    return got.casefold() == expected.casefold(), got


def cited_numbers(reply: str) -> set[int]:
    return {int(n) for n in _CITE.findall(reply or "")}


# --- the held-out set ---------------------------------------------------------


def _words(text: str) -> list[str]:
    return [w.lower().strip("'-") for w in _WORD.findall(text) if w.lower() not in _STOP]


def _candidates(session: Session) -> list[tuple[int, str, str]]:
    rows = session.execute(
        select(Entry.id, Entry.content, Category.name)
        .join(Category, Entry.category_id == Category.id)
        .where(
            Entry.is_deleted.is_(False),
            Entry.is_private.is_(False),
            Entry.is_board.is_(False),
            Entry.archived_at.is_(None),
            Category.name != UNCATEGORISED,
        )
        .order_by(Entry.id)
    ).all()
    return [(i, c or "", n) for i, c, n in rows if len((c or "").strip()) >= 40]


def build_set(session: Session, size: int = DEFAULT_SIZE, seed: int = 0) -> list[Item]:
    """`size` notes, each with a sentence and two words only it holds."""
    from tessellate.ai.facts import sentences

    pool = _candidates(session)
    rng = random.Random(f"bench:{seed}:{len(pool)}:{pool[0][0] if pool else 0}")
    picked = sorted(rng.sample(pool, min(size, len(pool))))
    # A word is distinctive when no other sampled note uses it.
    seen_in = Counter()
    for _, content, _ in picked:
        seen_in.update(set(_words(content)))
    items: list[Item] = []
    for entry_id, content, category in picked:
        for text, _start, _end in sentences(content):
            unique: list[str] = []
            for word in _words(text):
                if seen_in[word] == 1 and word not in unique:
                    unique.append(word)
            if len(unique) >= 2:
                # The two longest: long words are the least ambiguous cues.
                pair = sorted(unique, key=lambda w: (-len(w), unique.index(w)))[:2]
                items.append(Item(entry_id, category, content, text, (pair[0], pair[1])))
                break
    return items


def fingerprint(items: list[Item]) -> str:
    return ",".join(str(i.entry_id) for i in items)


# --- the run ------------------------------------------------------------------


class _Stop(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _tokens(reply: dict) -> int:
    count = reply.get("eval_count")
    if isinstance(count, int) and count >= 0:
        return count
    return max(1, len(reply.get("content") or "") // 4)


def run(
    session: Session,
    provider,  # noqa: ANN001  # the configured Provider, duck-typed for the fakes
    models: list[str],
    size: int = DEFAULT_SIZE,
    budget_seconds: float = DEFAULT_BUDGET_SECONDS,
    stop=None,  # noqa: ANN001  # a threading.Event
    clock: Callable[[], float] = time.monotonic,
    on_progress: Callable[[dict], None] | None = None,
) -> dict:
    """Bench each of `models` over the same held-out set; best first."""
    from tessellate.ai import librarian
    from tessellate.ai.janitor import SYSTEM_PROMPT

    items = build_set(session, size)
    categories = [n for n in session.scalars(select(Category.name)) if n != UNCATEGORISED]
    started = clock()
    total = len(models) * (len(items) * 2 + min(TOOL_TASKS, len(items)))
    done = 0
    scores: list[ModelScore] = []
    stopped = ""

    def tick(model: str) -> None:
        nonlocal done
        if stop is not None and stop.is_set():
            raise _Stop("stopped")
        if clock() - started > budget_seconds:
            raise _Stop("budget")
        if on_progress is not None:
            on_progress({"model": model, "done": done, "total": total})
        done += 1

    try:
        for model in models:
            score = ModelScore(model)
            scores.append(score)
            for item in items:
                tick(model)
                prompt = librarian.filing_prompt(session, item.content, categories)
                try:
                    reply = provider.chat(model, [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ])
                    right, got = filing_right(reply.get("content") or "", item.category)
                except Exception as exc:  # noqa: BLE001  # one failing call is a failed task, not a failed run
                    score.errors += 1
                    right, got = False, f"error: {exc}"
                score.filing.append(1.0 if right else 0.0)
                if not right:
                    score._fail(Failure("filing", item.entry_id, "File this note", item.category, got))
            for index, item in enumerate(items):
                tick(model)
                others = [o for o in items if o.entry_id != item.entry_id]
                distractors = [others[(index + k) % len(others)] for k in (0, 1)] if len(others) >= 2 else others
                shown = distractors[:]
                slot = index % (len(shown) + 1)
                shown.insert(slot, item)
                blocks = "\n\n".join(f"[{n}] {fence('note', o.content)}" for n, o in enumerate(shown, 1))
                began = clock()
                try:
                    reply = provider.chat(model, [
                        {"role": "system", "content": ANSWER_SYSTEM},
                        {"role": "user", "content": f"{blocks}\n\nQuestion: {item.question}"},
                    ])
                    text = reply.get("content") or ""
                    score.latency_ms.append((clock() - began) * 1000)
                    score.tokens.append(_tokens(reply))
                except Exception as exc:  # noqa: BLE001
                    score.errors += 1
                    text = f"error: {exc}"
                value, _ = citation_score({slot + 1}, cited_numbers(text))
                score.citation.append(value)
                if value < 1.0:
                    score._fail(Failure("citation", item.entry_id, item.question, f"[{slot + 1}]", text))
            for item in items[:TOOL_TASKS]:
                tick(model)
                ask = f"Look up my notes about “{item.terms[0]}” with the find_note tool."
                try:
                    reply = provider.chat_tools(model, [
                        {"role": "system", "content": TOOL_SYSTEM},
                        {"role": "user", "content": ask},
                    ], [FIND_NOTE_TOOL])
                    calls = reply.get("tool_calls") or []
                    right = any(
                        c.get("name") == "find_note"
                        and item.terms[0] in str((c.get("arguments") or {}).get("query", "")).lower()
                        for c in calls
                    )
                    got = json.dumps(calls)[:160] if calls else (reply.get("content") or "no tool call")
                except Exception as exc:  # noqa: BLE001  # a model without tools scores 0 here, it does not stop the run
                    score.errors += 1
                    right, got = False, f"error: {exc}"
                score.tools.append(1.0 if right else 0.0)
                if not right:
                    score._fail(Failure("tools", item.entry_id, ask, f"find_note({item.terms[0]})", got))
    except _Stop as halt:
        stopped = halt.reason
        logger.info("bench: %s after %d of %d tasks", halt.reason, done, total)

    rows = [s.as_dict() for s in scores if s.filing or s.citation or s.tools]
    rows.sort(key=lambda r: (-r["score"], r["answer_ms"] if r["answer_ms"] is not None else 1e12))
    return {
        "models": rows,
        #: No recommendation from a run that did not finish: a model that
        #: was cut off after ten tasks has not been compared with the rest.
        #: And none from a run where nothing scored: the first row of a table
        #: of zeros is the model that failed first (audit HR8: "Recommended,
        #: Filing 0%, Answers 0%, Tools 0%").
        "recommended": rows[0]["model"] if rows and not stopped and rows[0]["score"] >= RECOMMEND_FLOOR else None,
        "items": len(items),
        "set": fingerprint(items),
        "stopped": stopped,
        "seconds": round(clock() - started, 1),
    }
