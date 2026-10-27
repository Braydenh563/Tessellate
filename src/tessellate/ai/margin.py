"""The margin reader: a second reader in the editor, from your own notes
(WORLD_CLASS_PLAN 15, I2; 18, H8).

Every editor's AI writes *for* the person. This one reads *with* them,
against what they wrote before: given the paragraph under the caret, at most
three cards, each typed and each pinned to a sentence in another note:

- ``repeats``: the paragraph says again what a note already says;
- ``contradicts``: the same thing with a different number or a "not" (no
  model needed), or what the model judges a disagreement;
- ``answers``: the paragraph answers an open question the night shift found
  (`DerivedFact` kind ``question``);
- ``date``: a time phrase in the paragraph, read by the same date reader
  that fills a note's dates, offered as a reminder;
- ``related``: the closest note by words and meaning, when nothing sharper
  holds.

**Computed, never stored.** Nothing here writes: the cards are a reading,
and a link or a reminder is made only when the person presses its button,
through the routes that already make them.

**Fast without a model.** The candidates come from the keyword index and,
when the embedding backend is up, the meaning matrix with each long note's
best paragraph (row 6's chunk vectors), so the answer is a few milliseconds
of lookups. `judge=True` with a model up adds one short call per candidate
(at most three), which the editor asks for as a second request after the
fast one has drawn, so a slow model never holds the margin empty.
"""

from __future__ import annotations

import logging
import re
from collections import OrderedDict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import facts
from tessellate.ai.fence import FENCE_RULE, fence
from tessellate.core.database import DerivedFact, Entry
from tessellate.core.logbuffer import safe_value

logger = logging.getLogger("tessellate.ai.margin")

MAX_CARDS = 3
#: How many notes are read closely for one paragraph.
CANDIDATES = 6
#: A paragraph shorter than this has nothing to compare (a heading, "Yes.").
MIN_CHARS = 12
MAX_CHARS = 4000
#: Word overlap at or above which a sentence is the same sentence again.
REPEAT_AT = 0.7
#: Below this a candidate is not related enough to show at all.
RELATED_AT = 0.2

#: The paragraph's vector, by text: the editor asks again for the same
#: paragraph whenever the caret comes back to it.
_VECTORS: "OrderedDict[str, object]" = OrderedDict()
_VECTOR_CACHE = 128

JUDGE_SYSTEM = (
    "Two passages from the user's own notes. Say how the first relates to "
    "the second. Reply with one word, contradicts, repeats, answers or "
    "unrelated, then a dash and one short line saying why."
)
_JUDGED = {"contradicts", "repeats", "answers", "unrelated"}


def _vector(embeddings, text: str):  # noqa: ANN001, ANN202
    if text in _VECTORS:
        _VECTORS.move_to_end(text)
        return _VECTORS[text]
    vector = embeddings.embed_text(text)
    _VECTORS[text] = vector
    while len(_VECTORS) > _VECTOR_CACHE:
        _VECTORS.popitem(last=False)
    return vector


def _alike(a: str, b: str) -> float:
    return facts._words_alike(facts._terms(a), facts._terms(b))


def _best_sentence(content: str, paragraph: str, span: tuple[int, int] | None = None) -> tuple[str, int, int, float]:
    """The sentence of `content` closest to `paragraph` by words, inside
    `span` when the meaning search named a paragraph."""
    lo, hi = span if span else (0, len(content))
    best = ("", lo, hi, 0.0)
    for text, start, end in facts.sentences(content):
        if start < lo or end > hi:
            continue
        score = _alike(paragraph, text)
        if score > best[3]:
            best = (text, start, end, score)
    if not best[0]:
        text = content[lo:hi].strip()
        best = (text[:300], lo, min(hi, lo + 300), _alike(paragraph, text))
    return best


def _candidates(session: Session, paragraph: str, exclude: set[int], embeddings) -> dict[int, dict]:  # noqa: ANN001
    """`{entry_id: {"score", "span"}}` from words and, when it is up, meaning."""
    from tessellate.search import search_manager

    found: dict[int, dict] = {}
    try:
        for rank, entry in enumerate(search_manager.keyword_search(session, paragraph, limit=CANDIDATES + len(exclude))):
            if entry.id in exclude or entry.is_private:
                continue
            found.setdefault(entry.id, {"score": 0.0, "span": None, "entry": entry})
    except Exception:  # noqa: BLE001  # a broken index must not break the editor
        logger.debug("margin: keyword search failed", exc_info=True)
    if embeddings is not None and getattr(embeddings, "is_ready", lambda: False)():
        try:
            from tessellate.search import chunks, engine

            vector = _vector(embeddings, paragraph)
            if vector is not None:
                backend = embeddings.backend_id()
                for entry, score in search_manager.semantic_search(session, paragraph, embeddings, limit=CANDIDATES) or []:
                    if entry.id in exclude or entry.is_private:
                        continue
                    row = found.setdefault(entry.id, {"score": 0.0, "span": None, "entry": entry})
                    row["score"] = max(row["score"], float(score))
                matrix = engine.current_matrix(session, backend)
                for entry_id, best in chunks.best_paragraphs(session, vector, backend, matrix, only=set(found)).items():
                    found[entry_id]["span"] = (best.start, best.end)
                    found[entry_id]["score"] = max(found[entry_id]["score"], best.score)
        except Exception:  # noqa: BLE001  # meaning refines the margin, never fails it
            logger.debug("margin: meaning search failed", exc_info=True)
    return found


def _open_questions(session: Session, exclude: set[int]) -> list[DerivedFact]:
    rows = session.scalars(
        facts._visible(select(DerivedFact).where(DerivedFact.kind == "question")).limit(500)
    ).all()
    return [row for row in rows if row.entry_id not in exclude]


def _date_card(paragraph: str, now: datetime) -> dict | None:
    from tessellate.entry import timewords

    try:
        mentions = timewords.find(paragraph, now)
    except Exception:  # noqa: BLE001
        return None
    if not mentions:
        return None
    mention = mentions[0]
    at = mention.at if isinstance(mention.at, datetime) else datetime(mention.at.year, mention.at.month, mention.at.day, 9)
    return {
        "kind": "date",
        "text": f"A date: {mention.phrase}. Make a reminder?",
        "when": at.isoformat(timespec="minutes"),
        "phrase": mention.phrase,
        "confidence": 0.6,
        "reason": "A time phrase in this paragraph.",
    }


def _judge(provider, model: str, paragraph: str, source: str) -> tuple[str, str] | None:  # noqa: ANN001
    try:
        reply = provider.chat(model, [
            {"role": "system", "content": f"{JUDGE_SYSTEM} {FENCE_RULE}"},
            {"role": "user", "content": f"First: {fence('paragraph', paragraph[:1200])}\n\nSecond: {fence('note', source[:600])}"},
        ])
    except Exception as exc:  # noqa: BLE001  # a model that fails leaves the local reading
        logger.info("margin: the model could not judge (%s)", safe_value(str(exc), 160))
        return None
    text = (reply.get("content") or "").strip()
    word = re.split(r"[\s\-:,.]+", text.lower(), maxsplit=1)[0] if text else ""
    if word not in _JUDGED:
        return None
    reason = text.split("-", 1)[1].strip() if "-" in text else ""
    return word, reason[:200]


def read(
    session: Session,
    paragraph: str,
    *,
    entry_id: int | None = None,
    exclude: list[int] | None = None,
    embeddings=None,  # noqa: ANN001
    provider=None,  # noqa: ANN001
    model: str = "",
    now: datetime | None = None,
) -> dict:
    """At most `MAX_CARDS` cards for one paragraph; see the module docstring."""
    paragraph = (paragraph or "").strip()[:MAX_CHARS]
    if len(paragraph) < MIN_CHARS:
        return {"cards": [], "judged": False}
    skip = set(exclude or ())
    if entry_id:
        skip.add(int(entry_id))
    cards: list[dict] = []
    for entry_id_, row in _candidates(session, paragraph, skip, embeddings).items():
        entry: Entry = row["entry"]
        content = entry.content or ""
        sentence, start, end, words = _best_sentence(content, paragraph, row["span"])
        if not sentence:
            continue
        title = (entry.title if getattr(entry, "title", None) else content.strip().split("\n", 1)[0])[:80]
        base = {
            "source_entry_id": entry_id_,
            "source_title": title,
            "source_span": [start, end],
            "source_text": sentence[:300],
        }
        disagreement = None
        for mine, _s, _e in facts.sentences(paragraph) or [(paragraph, 0, len(paragraph))]:
            disagreement = facts._local_disagreement(mine, sentence)
            if disagreement:
                break
        if disagreement:
            cards.append({**base, "kind": "contradicts", "confidence": 0.75, "reason": disagreement,
                          "text": f"You wrote something different: “{sentence[:160]}”"})
        elif words >= REPEAT_AT or _alike(paragraph, content) >= REPEAT_AT:
            cards.append({**base, "kind": "repeats", "confidence": round(max(words, 0.7), 2),
                          "reason": "Most of the same words.", "text": f"This repeats your note “{title}”"})
        else:
            closeness = max(row["score"], words)
            if closeness < RELATED_AT:
                continue
            cards.append({**base, "kind": "related", "confidence": round(min(0.55, closeness), 2),
                          "reason": "Close in words and meaning." if row["score"] else "Shares words with this paragraph.",
                          "text": f"Related: “{sentence[:160]}”"})
    cards.extend({
        "kind": "answers",
        "source_entry_id": question.entry_id,
        "source_span": [question.span_start, question.span_end],
        "source_text": question.text[:300],
        "fact_id": question.id,
        "confidence": 0.65,
        "reason": "Holds most of what the question asks about.",
        "text": f"Answers your open question: “{question.text[:160]}”",
    } for question in _open_questions(session, skip) if facts._local_answer(question.text, paragraph))
    dated = _date_card(paragraph, now or datetime.now())
    if dated:
        cards.append(dated)

    judged = False
    if provider is not None and model:
        judged = True
        for card in [c for c in cards if c["kind"] in ("related", "repeats")][:MAX_CARDS]:
            verdict = _judge(provider, model, paragraph, card["source_text"])
            if verdict is None:
                continue
            kind, reason = verdict
            card["judged_by"] = model
            if kind == "unrelated":
                card["kind"] = "dropped"
                continue
            card["kind"] = kind
            card["confidence"] = max(card["confidence"], 0.7)
            if reason:
                card["reason"] = reason
            if kind == "contradicts":
                card["text"] = f"You wrote something different: “{card['source_text'][:160]}”"
            elif kind == "answers":
                card["text"] = f"This answers something in “{card['source_title']}”"

    order = {"contradicts": 0, "answers": 1, "repeats": 2, "date": 3, "related": 4}
    out: list[dict] = []
    seen: set[int] = set()
    #: The same sentence in two notes (a note pasted twice, an import of what
    #: was already here) is one card, not three: measured in the sweep, three
    #: identical Differs cards filled the margin and said one thing.
    said: set[tuple[str, str]] = set()
    for card in sorted(
        (c for c in cards if c["kind"] in order),
        key=lambda c: (-c["confidence"], order[c["kind"]]),
    ):
        source = card.get("source_entry_id")
        words = (card["kind"], " ".join(str(card.get("source_text", card["text"])).lower().split()))
        if (source is not None and source in seen) or words in said:
            continue
        said.add(words)
        if source is not None:
            seen.add(source)
        out.append(card)
        if len(out) == MAX_CARDS:
            break
    return {"cards": out, "judged": judged}
