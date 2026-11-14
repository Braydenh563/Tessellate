"""Questions that ask for one insight rule by name (CHAT_PLAN A15, L-chat-92):
"am I on a streak with running", "what was my busiest week", "what do I write
about after work", "how long have I been writing about golf", "what goes with
golf", "what have I stopped writing about", "which plans have gone quiet". Each
reads the dated notes with the rule's own function and says its measured line,
or says plainly that nothing crosses the threshold. No model."""

from __future__ import annotations

import re
from collections import Counter
from datetime import date

from tessellate.ai import insights, insights_more

_SUBJECT = re.compile(r"\b(?:about|with|on|alongside|around|of|in)\s+(?:my |the |our )?([a-z][\w' -]{1,40}?)(?:\s+notes?)?\s*[?.!]*$", re.I)
_STREAK = re.compile(r"\bstreaks?\b|\bweeks? (?:in a row|running)\b|\bevery week\b", re.I)
_LOAD = re.compile(r"\b(?:busiest|heaviest|biggest|most (?:productive|active))\s+(?:week|stretch)\b|\bwhich week\b.*\bmost\b", re.I)
_TIME = re.compile(r"\bafter work\b|\bin the (?:morning|evening)s?\b|\bmorning or evening\b|\bwhat time of day\b|\bwhat part of the day\b", re.I)
_SPAN = re.compile(r"\bhow long have i been (?:writing|noting|keeping notes)\b|\bsince when (?:do|did|have) i\b|\bfirst and last (?:time|mention)\b", re.I)
_TOGETHER = re.compile(r"\bwhat (?:goes|comes up|do i (?:write|mention)) (?:with|alongside|next to)\b|\bwhat (?:else )?(?:goes|comes up) with\b|\bco-?occur", re.I)
_SILENCE = re.compile(
    r"\bwhat (?:have i|haven'?t i|did i) (?:stopped|stop|not|n'?t)? ?(?:writ\w+|mention\w*|note\w*)\b[^?]*\b(?:lately|recently|for a while|any ?more)\b|\bwhat have i stopped\b"
    r"|\b(?:gone|went) quiet\b(?! plans?)|\bnothing (?:new )?about\b[^?]*\bsince\b|\bhave i (?:written|mentioned) (?:about )?[^?]* (?:lately|recently)\b", re.I)
_DRIFT = re.compile(r"\bplans?\b[^?]*\b(?:gone quiet|let slide|slipped|dropped|not (?:followed|picked)|never (?:followed|picked)|still open)\b", re.I)
_NO_SUBJECT = {"my notes", "notes", "the notebook", "my notebook", "it", "them", "lately", "recently", "all"}


def _subject(question: str) -> str | None:
    m = _SUBJECT.search(question.strip())
    subject = m.group(1).strip() if m else ""
    subject = re.sub(r"\s+(?:lately|recently|these days|after work|in the (?:morning|evening)s?)$", "", subject, flags=re.I)
    return None if not subject or subject.lower() in _NO_SUBJECT else subject


def _top_tags(notes: list[dict], n: int = 8) -> list[str]:
    return [t for t, _c in Counter(str(t).lower() for x in notes for t in set(x.get("tags") or [])).most_common(n)]


def _need(subject: str, notes: list[dict]) -> str | None:
    if any(insights._holds(n, subject) and insights._written(n) for n in notes):  # noqa: SLF001
        return None
    return f"I found no dated notes about {subject}."


def _subject_rule(rule, question: str, notes: list[dict], today: date, quiet: str) -> str:  # noqa: ANN001
    subject = _subject(question)
    if not subject:
        return "Name the subject, for example “about golf”, and I will measure it."
    if (missing := _need(subject, notes)):
        return missing
    found = rule(subject, notes, today)
    return found.text if found else quiet.format(subject=subject)


def _drift(q: str, notes: list[dict], today: date) -> str:  # noqa: ARG001
    found = insights.drift(notes, today)[:3]
    return "\n".join(f"- {i.text}" for i in found) if found else "No plan in your dated notes is a month old and unfollowed."


def _load(q: str, notes: list[dict], today: date) -> str:  # noqa: ARG001
    found = insights.load(notes, today)
    return found.text if found else "No week stands out: none has twice the notes of a usual week."


def _span(q: str, notes: list[dict], today: date) -> str:
    return _subject_rule(insights_more.span, q, notes, today, "{subject} is in too few days to give a first and a last.")


def _together(q: str, notes: list[dict], today: date) -> str:
    return _subject_rule(insights_more.together, q, notes, today, "No tag or name shares two notes with {subject}.")


def _time(q: str, notes: list[dict], today: date) -> str:
    subject = _subject(q)
    if not subject or subject.lower() in {"evening", "morning", "the evening", "the morning", "work"}:
        found = [i for t in _top_tags(notes) if (i := insights_more.time_of_day(t, notes, today))]
        return "\n".join(f"- {i.text}" for i in found[:3]) if found else "No tag has three notes that say when you wrote them."
    return _subject_rule(insights_more.time_of_day, q, notes, today, "Fewer than three {subject} notes say when you wrote them.")


def _streak(q: str, notes: list[dict], today: date) -> str:
    subject = _subject(q)
    found = [i for s in ([subject] if subject else _top_tags(notes)) if (i := insights.streak(s, notes, today))]
    return "\n".join(f"- {i.text}" for i in found[:3]) if found else "Nothing has been written about in three weeks running up to now."


def _silence(q: str, notes: list[dict], today: date) -> str:
    subject = _subject(q)
    if not subject:
        quiet = insights_more.quiet_tags(notes, today)
        return "\n".join(f"- {i.text}" for i in quiet) if quiet else "No tag has gone quiet for a month."
    if (missing := _need(subject, notes)):
        return missing
    found = insights_more.silence(subject, notes, today)
    held = [d for n in notes if insights._holds(n, subject) and (d := insights._written(n))]  # noqa: SLF001
    return found.text if found else f"You last wrote about {subject} on {insights._day(max(held), today)}."  # noqa: SLF001


#: In the order the questions are tried: the narrower phrasings first.
_RULES = ((_DRIFT, _drift), (_LOAD, _load), (_SPAN, _span), (_TOGETHER, _together), (_TIME, _time), (_STREAK, _streak), (_SILENCE, _silence))


def answer(question: str, notes: list[dict], today: date) -> str | None:
    """The measured line a rule-named question asks for, else None."""
    q = " ".join(question.split())
    return next((read(q, notes, today) for pattern, read in _RULES if pattern.search(q)), None)
