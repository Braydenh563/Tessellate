"""The model picks among the engine's numbered readings, never writes its own
(CHAT_PLAN decision 45, decision 17's handoff).

When a question only names something two or more notes are called, the
composer lists numbered readings (`composer._readings`). With a model running
it is asked one thing: which number? Its reply is read for a digit in range;
anything else (no digit, a number out of range, an error, a model that is not
running) is "none", and the engine's own question stands. The chosen reading is
then answered by the engine over that one note, so the model's words never
reach the answer: it reorders and selects, it adds no sentence.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable

_log = logging.getLogger(__name__)

_BARE = re.compile(r"^\s*(\d+)\s*\.?\s*$")

RULE = (
    "You choose between readings of a question about someone's notes. "
    "Reply with the number of the one reading that fits best, and nothing else. "
    "If you cannot tell which fits, reply with the word none."
)


def messages(question: str, readings: list[dict]) -> list[dict]:
    """The one constrained question the model is asked: the readings by number and label only."""
    listed = "\n".join(f"{r['n']}. {r['label']}" for r in readings)
    return [{"role": "system", "content": RULE}, {"role": "user", "content": f"Question: {question}\n\nReadings:\n{listed}"}]


def choice(reply: str, readings: list[dict]) -> int | None:
    """The note id of the reading the reply names. Only a bare number ("2", "2.") counts: anything else, "none" included, is no pick."""
    found = _BARE.match(reply)
    wanted = int(found.group(1)) if found else None
    return next((r["note_id"] for r in readings if r["n"] == wanted), None)


def pick(question: str, readings: list[dict], chat: Callable[[list[dict]], str]) -> int | None:
    """The note id the model chose among `readings`, or None (ask the person)."""
    if len(readings) < 2:
        return None
    try:
        return choice(chat(messages(question, readings)) or "", readings)
    except Exception as exc:  # noqa: BLE001  # a model that fails is a model that did not choose
        _log.info("reading pick skipped, the engine's own reading stands: %s", exc)
        return None


def settle(req: object, result: dict, pool: list, recompose: Callable[[list], dict]) -> dict:
    """`result`, answered over the one note the model chose when it chose; else unchanged."""
    readings = result.get("readings") or []
    ollama, manager = getattr(req, "ollama", None), getattr(req, "model_manager", None)
    if len(readings) < 2 or ollama is None or not ollama.is_running():
        return result
    model = manager.served_chat_model(ollama)
    chosen = pick(str(getattr(req, "question", "")), readings, lambda msgs: str(ollama.chat(model, msgs).get("content") or ""))
    only = [n for n in pool if str(n.get("source_id", n.get("id"))) == str(chosen)] if chosen is not None else []
    return recompose(only) if only else result
