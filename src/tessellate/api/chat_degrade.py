"""The model path degrades to the composed one (CHAT_PLAN "The degrade tests", protocol step 7; L-chat-21).

"Nothing the model does can leave the bubble with less than the composer would
have shown." A model that fails (refused, timed out, died after its first or
last word) already left the composed draft under MODEL_STOPPED_NOTE
(`chat_turn._model_stream_events`); one that finished with no words, or with
words of which no sentence the notes back (each has a figure or a name in none
of the notes nor the question, `validate.source_check`), did not: the bubble
was blank, or held only what the notes never said. Each now leaves the composed
answer, and its stats say `composition.fallback` so the turn's record shows it.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from tessellate.ai import validate
from tessellate.api.chat_said import MODEL_STOPPED_NOTE, MODEL_UNBACKED_NOTE

_SENTENCE = re.compile(r"(?<=[.?!])\s+")


def _unbacked_throughout(text: str, prepared: dict, question: str) -> bool:
    sentences = [s for s in _SENTENCE.split(text.strip()) if len(s.split()) >= 3]
    if not sentences:
        return False
    sources = [question, *(str(note.get("content") or "") for note in prepared.get("notes") or [])]
    return all(validate.source_check(sentence, sources, question) for sentence in sentences)


def falls_back(text: str, prepared: dict, question: str) -> bool:
    """Whether a finished model answer is replaced by the composed draft: there is one, and the answer says nothing the notes back."""
    preview = prepared.get("preview") or {}
    if not preview.get("text"):
        return False
    return not text.strip() or _unbacked_throughout(text, prepared, question)


def fallback_events(prepared: dict, stats: dict | None, composition: dict, streamed_any: bool, rejected: str = "") -> Iterator[dict]:
    """The composed draft as the answer (replacing any words already sent), then the stats marked as a fallback.

    `rejected` is the model's finished answer when the notes backed none of it: the note then says so,
    since the model did not stop."""
    note = MODEL_UNBACKED_NOTE if rejected.strip() else MODEL_STOPPED_NOTE
    said = f"{prepared['preview']['text']}\n\n{note}"
    yield {"type": "answer_final", "text": said} if streamed_any else {"type": "answer", "delta": said}
    yield {"type": "stats", **(stats or {}), "composition": {**composition, "fallback": True}}
