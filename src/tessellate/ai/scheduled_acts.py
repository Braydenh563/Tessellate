"""The one proactive line a day for a scheduled act (CHAT_PLAN X15, decision 28): a repeating reminder
whose words are an act ("list what is open", `commands._every_act`) is answered when it falls due, once
a day, from the notes, never by a model. The line's key holds the day, so the companion says it once."""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, time

_VERB = re.compile(r"^(?:list|show|tell|find|check|review|send)\s+(?:me\s+)?(?=what|which|how|when|who)", re.I)
ACT = re.compile(r"^(?:list|show|summari[sz]e|tell me|find|check|review|send me)\b", re.I)
#: A bubble, not a report: the answer's first sentence, cut at a word.
MAX_CHARS = 220


def is_act(reminder: dict) -> bool:
    """A repeating reminder that asks for an act rather than naming a task."""
    return bool(reminder.get("recurring") and reminder["recurring"] != "none" and ACT.match(str(reminder.get("text") or "").strip()))


def _first_sentence(text: str) -> str:
    plain = " ".join(re.sub(r"[*#]|\[([^\]]*)\]\([^)]*\)", lambda m: m.group(1) or "", text).split())
    first = re.split(r"(?<=[.!?:])\s", plain, maxsplit=1)[0]
    if len(first) > MAX_CHARS:
        first = first[:MAX_CHARS].rsplit(" ", 1)[0].rstrip(" ,;:.") + "…"
    return first


def _answer(act: str, notes: list[dict], today: date) -> str:
    """What the notes say to the act: the plan reader's answer to the question the act is ("list what is
    open" is "what is open"), else the composer's when a note grounds it; "" when nothing does."""
    from tessellate.ai import composer, composer_plan
    from tessellate.ai.composer_study import Ctx

    reply = composer_plan.answer(Ctx(question=_VERB.sub("", act), notes=notes, now=datetime.combine(today, time(9)), reminders=[]))
    if reply and reply.text:
        return reply.text
    got = composer.compose(act, notes, today=today)
    return str(got.get("text") or "") if got.get("grounding") else ""


def lines(reminders: list[dict], notes: list[dict], today: date) -> list[dict]:
    """One remark per act reminder due by `today`: "Your repeating reminder, “list what is open”: <what the notes say>".
    Nothing for an act the notes say nothing to."""
    out: list[dict] = []
    for r in reminders:
        if r.get("done") or not is_act(r) or str(r.get("due_at") or "")[:10] > today.isoformat():
            continue
        act = str(r["text"]).strip().rstrip(".")
        said = _first_sentence(_answer(act, notes, today))
        if not said:
            continue
        text = f"Your repeating reminder, “{act}”: {said}"
        out.append({"kind": "scheduled_act", "text": text, "parts": [("template", text)], "grounding": [], "sources": [],
                    "key": hashlib.sha1(f"act|{r.get('id')}|{today.isoformat()}".encode()).hexdigest()[:12], "reminder_id": r.get("id")})
    return out
