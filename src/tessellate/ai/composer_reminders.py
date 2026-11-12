"""Ask reads the reminders (audit 2 G3): "do I have any reminders today",
"did I pay the phone bill", "what bills are due" were searched as words in the
notes, which hold none of them.

Three asks, each answered only when a reminder answers it (else None, and the
notes' readers go on): the count and list ("do I have any reminders today",
"are there any overdue reminders"), the doing ("did I pay the phone bill": a
ticked reminder is a yes, an open one is "not yet" with its due time), and
the kind of thing that is due ("what bills are due"). The count is
`due_summary`'s, the one rule every surface shares. Nothing here acts: it only
reads, so there is nothing to confirm.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from tessellate.ai import composer_done, composer_plan, due_summary, realise, study
from tessellate.ai.composer_study import Ctx, Reply

_LEAD = r"(?:(?:so|ok|okay|hey|and|please)[, ]+)*"
#: Every part opens with its own word, so the match is linear. Any date words after "reminders"
#: are read by `composer_plan.window` (the one reader), not here.
_HAVE = re.compile(
    rf"^{_LEAD}(?:do i have|have i got|are there|is there|what|which|show me|list)?"
    r"(?: (?:any|some|my|the|all|open|overdue|due|pending|outstanding))* reminders?"
    r"(?: (?:do i have|have i got|are there|are (?:open|overdue|due|pending|outstanding)|do i have set|left|set))?"
    r"(?P<rest>(?: \w+){0,3})\W*$", re.I)
_DID = re.compile(rf"^{_LEAD}(?:did|have|has) i (?:already |ever |yet )?(?P<rest>\w+\s+.+?)(?:\s+yet)?\W*$", re.I)
_KIND = re.compile(rf"^{_LEAD}(?:what|which) (?P<kind>\w+(?:\s\w+)?) (?:are|is|do i have|have i got) (?:due|overdue|open|outstanding|coming up|left|pending)\W*$", re.I)
#: Words that name no kind of reminder: those asks belong to the agenda and the lists.
_GENERIC = frozenset({"things", "thing", "tasks", "task", "items", "item", "reminders", "reminder", "stuff", "bits", "jobs", "deadlines", "notes", "todos"})


#: The open reminders listed when none is due today; more than this are counted.
_COMING = 5


def _open(ctx: Ctx) -> list[dict]:
    rows = [r for r in ctx.reminders if isinstance(r.get("due_at"), datetime) and not r.get("done")]
    return sorted(rows, key=lambda r: r["due_at"])


def _day_said(due: datetime, today: date) -> str:
    gap = (due.date() - today).days
    when = {0: "today", 1: "tomorrow", -1: "yesterday"}.get(gap) or f"{due:%A} {due.day} {due:%B}"
    return f"{when} at {due:%H:%M}"


def _line(r: dict, today: date) -> str:
    due = r["due_at"]
    late = ", overdue" if due.date() < today else ""
    return f"- {str(r.get('text') or '').strip()} ({_day_said(due, today)}{late})"


def _count(n: int, noun: str) -> str:
    return realise.count_noun(n, noun).capitalize()


def _shown(rows: list[dict], today: date, text: str, win) -> tuple[list[dict], str] | None:  # noqa: ANN001
    """The reminders a "do I have any reminders ..." asks for, and the sentence's head."""
    gap = lambda r: (r["due_at"].date() - today).days  # noqa: E731
    if re.search(r"\boverdue\b", text, re.I):
        shown = [r for r in rows if gap(r) < 0]
        return shown, (f"{_count(len(shown), 'reminder')} overdue." if shown else "Nothing is overdue.")
    if win and win[0] > today:
        shown = [r for r in rows if win[0] <= r["due_at"].date() <= win[1]]
        return shown, (f"{_count(len(shown), 'reminder')} due {win[2]}." if shown else f"Nothing is due {win[2]}.")
    if win and win[1] > today:
        shown = [r for r in rows if r["due_at"].date() <= win[1]]
        return shown, (f"{_count(len(shown), 'reminder')} due {win[2]} or overdue." if shown else f"Nothing is due {win[2]}.")
    return None


def _have(ctx: Ctx, found: re.Match) -> Reply | None:
    today = ctx.now.date()
    win = composer_plan.window(found.string, today)
    if found.group("rest").strip() and win is None:
        return None  # "reminders about the boiler" is a search, not a count
    rows = _open(ctx)
    cap = 10
    got = _shown(rows, today, found.string, win)
    if got is None:
        shown = [r for r in rows if r["due_at"].date() <= today]
        if shown:
            head = f"You have {due_summary.say(due_summary.of(rows, ctx.now)).lower()}."
        elif rows:
            #: Every open reminder is named while they are few, else the next few and a count.
            first = f"“{str(rows[0].get('text') or '').strip()}”, {_day_said(rows[0]['due_at'], today)}"
            head = f"Nothing is due today. The next is {first}." if len(rows) == 1 else f"Nothing is due today. You have {len(rows)} open reminders, the next is {first}."
            shown, cap = rows, _COMING
        else:
            head = "You have no open reminders."
        got = shown, head
    shown, head = got
    more = [f"and {len(shown) - cap} more."] if len(shown) > cap else []
    #: A count with nothing in it goes on to the weeks ahead, not the statistics chips (F5).
    return Reply("\n".join([head, *([""] + [_line(r, today) for r in shown[:cap]] + more if shown else [])]), asks=[] if shown else composer_plan.AHEAD_CHIPS)


def _matching(ctx: Ctx, wanted: set[str], verbs: frozenset[str] = frozenset()) -> list[dict]:
    """Reminders (done or open) whose words hold every stem asked; with `verbs`, one of them too."""
    out = []
    for r in ctx.reminders:
        have = set(study.content_stems(str(r.get("text") or "")))
        if wanted and wanted <= have and (not verbs or verbs & have):
            out.append(r)
    return out


def _did(ctx: Ctx, found: re.Match) -> Reply | None:
    words = found.group("rest").split()
    if len(words) < 2:
        return None
    wanted = set(study.content_stems(" ".join(words[1:])))
    verbs = composer_done._verb_forms(words[0])  # noqa: SLF001
    mine = _matching(ctx, wanted, verbs)
    if not mine:
        return None
    today = ctx.now.date()
    ticked = [r for r in mine if r.get("done")]
    if ticked:
        return Reply(f"Yes: your reminder “{str(ticked[0].get('text') or '').strip()}” is ticked off.")
    soonest = min((r for r in mine if isinstance(r.get("due_at"), datetime)), key=lambda r: r["due_at"], default=None)
    if soonest is None:
        return None
    due = soonest["due_at"]
    was = "was due" if due.date() < today or (due.date() == today and due <= ctx.now) else "is due"
    return Reply(f"Not yet: your reminder “{str(soonest.get('text') or '').strip()}” is still open and {was} {_day_said(due, today)}.")


def _kind(ctx: Ctx, found: re.Match) -> Reply | None:
    kind = found.group("kind").lower().split()
    if kind[-1] in _GENERIC:
        return None
    mine = [r for r in _matching(ctx, set(study.content_stems(" ".join(kind)))) if not r.get("done") and isinstance(r.get("due_at"), datetime)]
    if not mine:
        return None
    today = ctx.now.date()
    mine.sort(key=lambda r: r["due_at"])
    head = f"{_count(len(mine), 'open reminder')} on that:"
    return Reply("\n".join([head, "", *[_line(r, today) for r in mine[:10]]]))


def answer(ctx: Ctx) -> Reply | None:
    """A reply when a reminder answers the question, else None."""
    text = " ".join((ctx.asked or ctx.question or "").split())
    if not text or len(text) > 120 or not ctx.reminders:
        return None
    if found := _HAVE.match(text):
        return _have(ctx, found)
    if found := _DID.match(text):
        return _did(ctx, found)
    if found := _KIND.match(text):
        return _kind(ctx, found)
    return None
