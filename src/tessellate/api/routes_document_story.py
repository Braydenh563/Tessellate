"""A document's history in a few sentences (L-documents-5).

`POST /documents/{document_id}/revisions/summary` writes nothing. It walks the
newest saved versions pair by pair (each version against the one that replaced
it, the newest against the document as it stands), counts what was added and
removed and in which sections, and asks the local model for a short account of
what happened, shown only the budgeted changed lines, never the whole text.

**Never without an account.** With no model, or a model that fails or answers
nothing, the account is built from the same counts in plain words
(`source: "words"`): lines added and removed, the sections they sit in, one line
per step. The model is a fake transport in every test (CLAUDE.md section 4).
"""

from __future__ import annotations

import difflib
import logging
import re

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from tessellate.api.routes_board_affinity import bounded_chat
from tessellate.core import deps
from tessellate.core.deps import get_session
from tessellate.repo import documents as document_repo

router = APIRouter(prefix="/documents", tags=["documents"])

#: How many saved versions are read, newest first: the story of a long history
#: is its recent part, and every step costs prompt tokens.
STEPS = 6
#: Changed lines shown to the model per step, per side, and their width.
STEP_LINES = 8
LINE_CHARS = 140
#: The whole prompt's share of changed text; later steps give way first.
BUDGET_CHARS = 5000
#: A cold first call to the 1.5B local model passed bounded_chat's 45 s (L-documents-97); only this call waits longer.
SUMMARY_SECONDS = 150.0
SUMMARY_CHARS = 900
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")


def _section_of(lines: list[str], index: int) -> str:
    """The nearest heading at or above a line, or "" before the first one."""
    for k in range(min(index, len(lines) - 1), -1, -1):
        m = _HEADING.match(lines[k])
        if m:
            return m.group(1)[:60]
    return ""


def _names(side: list[str], lo: int, hi: int) -> list[str]:
    """The sections a changed block counts toward: the one its first real line
    sits in, and every heading it brings in or takes out."""
    first = next((k for k in range(lo, hi) if side[k].strip()), lo)
    names = [_section_of(side, first) or "the opening"]
    names += [m.group(1)[:60] for k in range(lo, hi) if (m := _HEADING.match(side[k]))]
    return names


def _step(older: str, newer: str) -> dict:
    """What changed from `older` to `newer`: line counts, the sections they sit
    in (in order of appearance) and the changed lines themselves."""
    a, b = (older or "").splitlines(), (newer or "").splitlines()
    added: list[str] = []
    removed: list[str] = []
    sections: list[str] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        removed += [x for x in a[i1:i2] if x.strip()]
        added += [x for x in b[j1:j2] if x.strip()]
        side = (b, j1, j2) if j2 > j1 else (a, i1, i2)
        for name in _names(*side):
            if name not in sections:
                sections.append(name)
    return {"added": len(added), "removed": len(removed), "sections": sections, "added_lines": added, "removed_lines": removed}


def _clip(line: str) -> str:
    line = " ".join(line.split())
    return line if len(line) <= LINE_CHARS else line[: LINE_CHARS - 1] + "…"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def _step_line(s: dict) -> str:
    if not (s["added"] or s["removed"]):
        return f"{s['when']}: only the title or spacing changed."
    where = f" in {', '.join(s['sections'][:3])}" if s["sections"] else ""
    return f"{s['when']}: {s['added']} added, {s['removed']} removed{where}."


def _plain(steps: list[dict]) -> str:
    """The account without a model, from the counts alone."""
    if not steps:
        return "Nothing has changed in this document yet."
    sections: list[str] = []
    for s in steps:
        sections += [x for x in s["sections"] if x not in sections]
    head = f"Over the last {_plural(len(steps), 'version')}: {_plural(sum(s['added'] for s in steps), 'line')} added, {sum(s['removed'] for s in steps)} removed"
    if sections:
        more = f" and {len(sections) - 5} more" if len(sections) > 5 else ""
        head += f", across {_plural(len(sections), 'section')} ({', '.join(sections[:5])}{more})"
    return "\n".join([head + ".", *map(_step_line, steps)])


def _prompt(steps: list[dict]) -> str:
    left = BUDGET_CHARS
    blocks = []
    for n, s in enumerate(steps, 1):
        rows = [f"Step {n}, {s['when']}: {s['added']} lines added, {s['removed']} removed; sections: {', '.join(s['sections']) or 'none'}"]
        for sign, key in (("+", "added_lines"), ("-", "removed_lines")):
            for line in s[key][:STEP_LINES]:
                text = f"  {sign} {_clip(line)}"
                if left < len(text):
                    break
                left -= len(text)
                rows.append(text)
        blocks.append("\n".join(rows))
    return "Changes, oldest step first:\n" + "\n".join(blocks)


def _ask_model(steps: list[dict]) -> str:
    system = (
        "You tell a writer what changed in their document between saved versions. Use only the changes listed: "
        "the + lines were added, the - lines were removed. Reply with at most four short plain sentences, "
        "no preamble, and never mention anything that is not in the list."
    )
    reply = bounded_chat(
        "Summarising a document's history",
        [{"role": "system", "content": system}, {"role": "user", "content": _prompt(steps)}],
        seconds=SUMMARY_SECONDS,
    )
    return str(reply.get("content") or "").strip()[:SUMMARY_CHARS]


@router.post("/{document_id}/revisions/summary")
def revisions_summary(document_id: int, db: Session = Depends(get_session)) -> dict:
    """An account of the newest versions' changes; nothing written."""
    from tessellate.api.routes_documents import _existing

    document = _existing(db, document_id)
    rows = document_repo.revisions(db, document_id)[:STEPS]
    steps: list[dict] = []
    newer = document.content or ""
    for row in rows:
        step = _step(row.content or "", newer)
        step["when"] = row.created_at.strftime("%d %b %H:%M").lstrip("0")
        steps.append(step)
        newer = row.content or ""
    steps.reverse()
    changed = [s for s in steps if s["added"] or s["removed"]]
    plain = _plain(steps)
    out = {"steps": len(steps), "added": sum(s["added"] for s in steps), "removed": sum(s["removed"] for s in steps)}
    if not changed:
        return {**out, "summary": plain, "source": "words", "reason": "none"}
    if not deps.get_ollama().is_running():
        return {**out, "summary": plain, "source": "words", "reason": "offline"}
    try:
        text = _ask_model(changed)
    except TimeoutError:
        return {**out, "summary": plain, "source": "words", "reason": "timeout"}
    except Exception:
        logging.getLogger("tessellate.documents").warning("History summary: the model failed", exc_info=True)
        return {**out, "summary": plain, "source": "words", "reason": "failed"}
    if not text:
        return {**out, "summary": plain, "source": "words", "reason": "unusable"}
    return {**out, "summary": text, "source": "model", "reason": "model"}
