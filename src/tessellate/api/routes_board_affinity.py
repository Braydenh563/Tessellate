"""The affinity sort (the features audit, Phase G).

Select a board's stickies and the board proposes frames: the stickies grouped
by theme, each theme named, each sticky shown with the notes in the person's
own notebook that back its place. `POST /whiteboard/boards/{board_id}/affinity`
writes nothing; the client draws the frames the person accepts, in one Undo
step, through the board's own object routes.

**Grounded, and never without an answer.** The backing notes come from the
search engine, as Branches from my notes finds them, so a sticky that matches
nothing is shown with no note rather than an invented one. The model only
groups: it answers lines of `Name: 1, 4, 7` and a number it was not given, a
sticky named twice, or a line that is prose is dropped. A sticky it leaves out
is placed by shared words, and with no model, or a reply with no usable line,
the whole sort is by shared words (`source: "words"`): the word most stickies
share names the group, which is never wrong. The model is a fake transport in
every test (CLAUDE.md section 4).
"""

from __future__ import annotations

import json
import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.api.routes_map_suggest import _candidates
from tessellate.core import deps, egress, jobs
from tessellate.core.deps import get_session
from tessellate.repo import whiteboard as whiteboard_repo

router = APIRouter(prefix="/whiteboard", tags=["whiteboard"])

MAX_STICKIES = 60
#: Notes shown behind a sticky: the closest two are evidence, a longer list is noise.
BACKING = 2
STICKY_CHARS = 160
NAME_CHARS = 40
#: Words that join stickies without meaning anything: grouping by "the" is no grouping.
_STOP = frozenset(
    "a an and are as at be but by do for from get has have how i in is it its my need not of on or our so that the "
    "their then this to up us was we what when who why will with you your".split()
)


class AffinityBody(BaseModel):
    ids: list[int] = Field(min_length=2, max_length=MAX_STICKIES)


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9']{3,}", text.casefold()) if w not in _STOP}


def _by_words(rows: list[tuple[int, str]]) -> list[tuple[str, list[int]]]:
    """Greedy: the word the most unplaced stickies share (two at least) names a
    group of them; what shares nothing is left to the caller."""
    left = {i: _words(text) for i, text in rows}
    #: A word on most of the stickies ("item", the board's own subject) splits nothing.
    onboard: dict[str, int] = {}
    for words in left.values():
        for w in words:
            onboard[w] = onboard.get(w, 0) + 1
    ceiling = max(2, int(len(rows) * 0.6)) if len(rows) >= 4 else len(rows)
    out: list[tuple[str, list[int]]] = []
    while True:
        count: dict[str, int] = {}
        for words in left.values():
            for w in words:
                count[w] = count.get(w, 0) + 1
        shared = [(n, w) for w, n in count.items() if n >= 2 and onboard[w] <= ceiling]
        if not shared:
            return out
        n, word = min(shared, key=lambda p: (-p[0], p[1]))
        members = [i for i in left if word in left[i]]
        out.append((word.capitalize(), members))
        for i in members:
            del left[i]


#: How long a board or document AI call may take before the words rule
#: answers instead: a slow or wedged model must not hold the request open.
MODEL_SECONDS = 45.0


def bounded_chat(label: str, messages: list[dict], seconds: float | None = None) -> dict:
    """The utility model's reply within `seconds` (default `MODEL_SECONDS`); raises TimeoutError
    past it (the caller then falls back to the words rule).

    `utility_model()` is not local only: the provider can be an
    OpenAI-compatible server at any `llm_base_url`, so the call runs under
    `egress.purpose`, and a connection that leaves the computer is named on
    the privacy receipt like every other AI call. Set in the worker thread,
    where the connection is made (the purpose is per thread)."""
    provider, model = deps.get_ollama(), deps.get_model_manager().utility_model()

    def call() -> dict:
        with egress.purpose(label):
            return provider.chat(model, messages)

    return jobs.future("board-ai", call).result(timeout=seconds or MODEL_SECONDS)


def _ask_model(rows: list[tuple[int, str]]) -> list[tuple[str, list[int]]]:
    """The model's groups as (name, row numbers). Pure of the database; raises
    when the model does."""
    system = (
        "You sort sticky notes into themes. Reply with ONLY lines of the form "
        "'Theme name: 1, 4, 7' where the numbers are the stickies in that theme. "
        "Two to six themes, names of one to four words, every sticky in at most "
        "one line, no preamble, no sticky that is not listed."
    )
    listing = "\n".join(f"[{i + 1}] {text}" for i, (_, text) in enumerate(rows))
    reply = bounded_chat(
        "Sorting stickies into themes",
        [{"role": "system", "content": system}, {"role": "user", "content": f"Stickies:\n{listing}"}],
    )
    out = []
    for line in str(reply.get("content") or "").splitlines():
        m = re.match(r"^\s*[-*+]?\s*(.+?)\s*:\s*(\d+(?:\s*,\s*\d+)*)\s*$", line)
        if m:
            out.append((m.group(1).strip().strip("\"*")[:NAME_CHARS], [int(n) - 1 for n in re.findall(r"\d+", m.group(2))]))
    return out


def _model_groups(rows: list[tuple[int, str]]) -> tuple[list[tuple[str, list[int]]], str]:
    """(groups, reason): the model's groups over sticky ids, or [] and why not."""
    if not deps.get_ollama().is_running():
        return [], "offline"
    try:
        asked = _ask_model(rows)
    except Exception:
        logging.getLogger("tessellate.whiteboard").warning("Affinity sort: the model failed", exc_info=True)
        return [], "failed"
    placed: set[int] = set()
    groups = []
    for name, numbers in asked:
        members = [rows[n][0] for n in numbers if 0 <= n < len(rows) and rows[n][0] not in placed and not placed.add(rows[n][0])]
        if name and members:
            groups.append((name, members))
    return groups, "model" if groups else "unusable"


def _stem(word: str) -> str:
    return word[:5]


def _backing(db: Session, board_id: int, text: str) -> list[dict]:
    """The notes that back a sticky. The search is forgiving by design (it pads
    a thin result with near misses: "Budget item 2" found a note about compost),
    so a note counts only when it shares a word with the sticky, and is never
    offered as evidence for words it does not contain."""
    stems = {_stem(w) for w in _words(text)}
    out = []
    for entry, title, body in _candidates(db, board_id, text, set()):
        if stems & {_stem(w) for w in _words(f"{title} {body}")}:
            out.append({"id": entry.id, "title": title})
        if len(out) >= BACKING:
            break
    return out


def _sticky_rows(db: Session, board_id: int, ids: list[int]) -> list[tuple[int, str]]:
    """(id, words) of the selected stickies that are on this board and have words."""
    found = whiteboard_repo.text_objects(db, board_id, ids)
    by_id = {obj.id: obj for obj in found}
    rows: list[tuple[int, str]] = []
    for oid in dict.fromkeys(ids):
        obj = by_id.get(oid)
        try:
            text = " ".join(str(json.loads(obj.data or "{}").get("content") or "").split()) if obj else ""
        except (TypeError, ValueError):
            text = ""
        if text:
            rows.append((oid, text[:STICKY_CHARS]))
    return rows


def _all_groups(rows: list[tuple[int, str]]) -> tuple[list[tuple[str, list[int]]], str, str]:
    """(groups, source, reason): the model's groups, the rest by words, the loose in Other."""
    groups, reason = _model_groups(rows)
    source = "model" if groups else "words"
    placed = {i for _, members in groups for i in members}
    rest = [(i, t) for i, t in rows if i not in placed]
    groups += _by_words(rest) if source == "model" else _by_words(rows)
    placed = {i for _, members in groups for i in members}
    loose = [i for i, _ in rows if i not in placed]
    if loose:
        groups.append(("Other", loose))
    return groups, source, reason if source == "words" else "model"


@router.post("/boards/{board_id}/affinity")
def affinity_sort(board_id: int, body: AffinityBody, db: Session = Depends(get_session)) -> dict:
    """The selected stickies grouped by theme, each with the notes that back
    it, and nothing written."""
    rows = _sticky_rows(db, board_id, body.ids)
    if len(rows) < 2:
        raise HTTPException(status_code=422, detail="Select two or more stickies on this board that have words on them.")
    groups, source, reason = _all_groups(rows)
    text_of = dict(rows)
    return {
        "source": source,
        "reason": reason,
        "count": len(rows),
        "groups": [
            {
                "name": name,
                "ids": members,
                "items": [{"id": i, "text": text_of[i], "notes": _backing(db, board_id, text_of[i])} for i in members],
            }
            for name, members in groups
        ],
    }
