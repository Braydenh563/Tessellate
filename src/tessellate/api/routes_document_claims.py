"""Claim check (the features audit, Phase G): a document's sentences checked
against the notebook.

`POST /documents/{document_id}/claim-check` writes nothing. It splits the text
into sentences, finds the notes that share words with each (the search pads a
thin result with near misses, so a note counts only when it shares a word), and
marks each claim `supported`, `contradicted` or `not_found` with the note behind
the verdict.

**Grounded, and never without an answer.** The model only judges: it is shown
at most `MODEL_CLAIMS` claims that have a note to judge against, and answers
lines of `3: contradicted b` (the claim's number, the verdict, the letter of
the note it read). A verdict that cites no listed note is not trusted, and the
claim falls to the words rule. With no model, or a reply with no usable line,
the whole check is the words rule (`source: "words"`): supported when one note
holds most of the claim's words, otherwise not found. It cannot call anything
contradicted, which takes reading, and says so by never doing it. The model is
a fake transport in every test (CLAUDE.md section 4).
"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.api.routes_board_affinity import _stem, _words, bounded_chat
from tessellate.api.routes_map_suggest import _candidates
from tessellate.core import deps
from tessellate.core.deps import get_session
from tessellate.entry import manager_text

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_TEXT = 500_000
MAX_CLAIMS = 40
MODEL_CLAIMS = 15
MIN_WORDS = 5
#: Notes a claim is judged against, and the characters of each the model reads.
NOTES_PER_CLAIM = 2
EXCERPT = 400
#: A claim is supported offline when one note holds this share of its words.
SUPPORT_SHARE = 0.6
_LETTERS = "abcdefgh"
VERDICTS = ("supported", "contradicted", "unrelated")


class ClaimBody(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT)


def _front_matter_end(text: str) -> int:
    """Where a leading `---` block ends, or 0. By line, not one regex: a
    lazy `.*?` up to a closing `---` was polynomial on '---\n' + 'a---\n' * n
    (CodeQL 2285)."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return 0
    pos = len(lines[0])
    for line in lines[1:]:
        pos += len(line)
        if line.rstrip("\r\n").rstrip(" \t") == "---":
            return pos
    return 0


def _claims(text: str) -> list[tuple[int, int]]:
    """(start, end) of each sentence worth checking, in the text as given:
    not a heading, a code fence's lines, a table row or a frontmatter block."""
    spans: list[tuple[int, int]] = []
    pos, fenced = 0, False
    skip_to = _front_matter_end(text)
    for line in text.splitlines(keepends=True):
        start, pos = pos, pos + len(line)
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            fenced = not fenced
            continue
        if fenced or start < skip_to or not stripped or stripped[0] in "#|":
            continue
        indent = len(line) - len(line.lstrip(" \t"))
        marker = _LIST_MARKER.match(line, indent)
        for at, end in _sentences(line, marker.end() if marker else 0):
            sentence = line[at:end]
            lead = len(sentence) - len(sentence.lstrip())
            body = sentence[lead:].rstrip()
            if len(re.findall(r"[A-Za-z]{2,}", body)) >= MIN_WORDS:
                spans.append((start + at + lead, start + at + lead + len(body)))
    return spans[:MAX_CLAIMS]


#: A real list or quote marker only: a sentence's own number ("2024 revenue
#: rose") is part of the claim, not a marker to strip. Matched after the
#: indent is skipped by `lstrip`, so no pattern repeats over the tabs
#: (CodeQL 2290: a leading `[ \t]*` was polynomial on many tabs).
_LIST_MARKER = re.compile(r"(?:[-*+>]|\d{1,3}[.)])[ \t]+")
#: The longest word the abbreviation check reads back from a full stop.
_WORD_BACK = 24
#: Words whose full stop ends no sentence.
_ABBREVIATIONS = frozenset({"etc.", "vs.", "mr.", "mrs.", "ms.", "dr.", "st.", "no.", "approx.", "cf."})


def _sentences(line: str, begin: int) -> list[tuple[int, int]]:
    """(start, end) of each sentence in `line` from `begin`. A sentence ends at
    `.`, `!` or `?` followed by a space or the line's end, so "3.5" holds
    together; and not after an abbreviation ("e.g.", "U.S.", "etc.")."""
    out, at = [], begin
    for m in re.finditer(r"[.!?](?=\s|$)", line):
        if m.start() < begin:
            continue
        if line[m.start()] == ".":
            #: Read back at most `_WORD_BACK` characters, not the whole line
            #: before each stop: linear on a line of many stops.
            word = line[max(begin, m.end() - _WORD_BACK) : m.end()].rsplit(None, 1)[-1].lower()
            if "." in word[:-1] or word in _ABBREVIATIONS:
                continue
        out.append((at, m.end()))
        at = m.end()
    if line[at:].strip():
        out.append((at, len(line.rstrip("\r\n"))))
    return out


def _notes_for(db: Session, claim: str) -> list[dict]:
    """The notes that share a word with the claim, best first, each with the
    share of the claim's words it holds."""
    words = sorted(_words(claim), key=lambda w: (-len(w), w))
    stems = {_stem(w) for w in words}
    #: The longest few words, bare: a whole sentence with its stop words and
    #: full stop found nothing in the engine (measured), its content words do.
    out = []
    for entry, title, _ in _candidates(db, 0, " ".join(words[:8]), set()):
        full = manager_text.readable_content(entry)
        held = {_stem(w) for w in _words(f"{title} {full[:6000]}")}
        if stems & held:
            out.append({"id": entry.id, "title": title, "text": " ".join(full.split()), "share": len(stems & held) / len(stems)})
        if len(out) >= NOTES_PER_CLAIM:
            break
    return out


def _words_rule(notes: list[dict]) -> tuple[str, dict | None]:
    best = max(notes, key=lambda n: n["share"], default=None)
    if best and best["share"] >= SUPPORT_SHARE:
        return "supported", best
    return "not_found", None


def _ask_model(listed: list[tuple[str, list[dict]]]) -> dict[int, tuple[str, int]]:
    """{claim number (0-based): (verdict, note index)} as the model judged them.
    Pure of the database; raises when the model does."""
    system = (
        "You check a writer's claims against the writer's own notes. For each numbered claim, "
        "reply with ONLY a line 'number: verdict letter' where verdict is supported (a note says it), "
        "contradicted (a note says something that cannot be true together with it) or unrelated, "
        "and letter is the note you read. One line per claim, no preamble."
    )
    blocks = []
    for n, (claim, notes) in enumerate(listed, 1):
        lines = [f"[{n}] {claim}"]
        lines += [f"  ({_LETTERS[k]}) {note['title']}: {note['text'][:EXCERPT]}" for k, note in enumerate(notes)]
        blocks.append("\n".join(lines))
    reply = bounded_chat(
        "Checking a document's claims against your notes",
        [{"role": "system", "content": system}, {"role": "user", "content": "Claims:\n" + "\n".join(blocks)}],
    )
    out: dict[int, tuple[str, int]] = {}
    for line in str(reply.get("content") or "").splitlines():
        m = re.match(r"^\s*\[?(\d+)\]?\s*[:.)-]\s*(supported|contradicted|unrelated)\b\s*\(?([a-h])?\)?", line, re.I)
        if m:
            letter = (m.group(3) or "").lower()
            out[int(m.group(1)) - 1] = (m.group(2).lower(), _LETTERS.index(letter) if letter else -1)
    return out


def _model_verdicts(listed: list[tuple[str, list[dict]]]) -> tuple[dict[int, tuple[str, dict | None]], str]:
    """(verdicts by listed number, reason). A verdict is kept when it cites a
    listed note, or is `unrelated`, which needs none."""
    if not deps.get_ollama().is_running():
        return {}, "offline"
    if not listed:
        return {}, "none"
    try:
        asked = _ask_model(listed)
    except Exception:
        logging.getLogger("tessellate.documents").warning("Claim check: the model failed", exc_info=True)
        return {}, "failed"
    kept: dict[int, tuple[str, dict | None]] = {}
    for n, (verdict, k) in asked.items():
        if not 0 <= n < len(listed):
            continue
        notes = listed[n][1]
        if verdict == "unrelated":
            kept[n] = ("not_found", None)
        elif 0 <= k < len(notes):
            kept[n] = (verdict, notes[k])
    return kept, "model" if kept else "unusable"


def _message(verdict: str, note: dict | None) -> str:
    if verdict == "supported" and note:
        return f"Supported by “{note['title']}”."
    if verdict == "contradicted" and note:
        return f"Your note “{note['title']}” says otherwise."
    return "No note in your notebook says this."


@router.post("/{document_id}/claim-check")
def claim_check(document_id: int, body: ClaimBody, db: Session = Depends(get_session)) -> dict:
    """The document's sentences, each marked against the notebook; nothing written."""
    from tessellate.api.routes_documents import _existing

    _existing(db, document_id)
    spans = _claims(body.text)
    if not spans:
        raise HTTPException(status_code=422, detail="There are no full sentences here to check yet.")
    texts = [body.text[a:b] for a, b in spans]
    notes = [_notes_for(db, t) for t in texts]
    listed_at = [i for i, n in enumerate(notes) if n][:MODEL_CLAIMS]
    judged, reason = _model_verdicts([(texts[i], notes[i]) for i in listed_at])
    claims = []
    for i, ((start, end), text) in enumerate(zip(spans, texts)):
        n = listed_at.index(i) if i in listed_at else -1
        by = "model" if n in judged else "words"
        verdict, note = judged[n] if n in judged else _words_rule(notes[i])
        claims.append(
            {
                "text": text,
                "start": start,
                "end": end,
                "verdict": verdict,
                "by": by,
                "note": {"id": note["id"], "title": note["title"]} if note else None,
                "message": _message(verdict, note),
            }
        )
    source = "model" if judged else "words"
    return {"source": source, "reason": "model" if judged else reason, "claims": claims}
