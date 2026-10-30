"""Dashboard insights: stats, on-this-day, weekly digest."""

from __future__ import annotations

import difflib
import json
import random
import re
import threading
from collections.abc import Iterator
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.ai import backend_hint, greeting_compose, librarian
from tessellate.ai.answer_trim import trim_assistant_padding
from tessellate.ai.ollama_client import OllamaError
from tessellate.core import deps
from tessellate.core.config import days_from_today, user_now
from tessellate.core.database import Category, Entry, utcnow
from tessellate.core.deps import get_session
from tessellate.entry import manager, paths

router = APIRouter(prefix="/insights", tags=["insights"])

ACTIVITY_DAYS = 14  # the dashboard's little activity strip
HEATMAP_DAYS = 371  # 53 whole weeks, the contribution-style heatmap


@router.get("/stats")
def stats(session: Session = Depends(get_session)) -> dict:
    # Drafts and boards are not counted: the Notes list and its sidebar leave
    # both out (a board is an Entry row, MINDMAP_PLAN §2), and the owner asked
    # "do I have 29, 30 or 31 notes?" when this said one number and the list
    # another. Measured again after boards: dashboard 75, list 40.
    total = session.scalar(
        select(func.count(Entry.id)).where(Entry.is_deleted == False, Entry.is_draft == False, Entry.is_board == False)  # noqa: E712
    )
    by_category = session.execute(
        select(Category.name, func.count(Entry.id))
        .join(Entry, Entry.category_id == Category.id)
        .where(Entry.is_deleted == False, Entry.is_draft == False, Entry.is_board == False)  # noqa: E712
        .group_by(Category.name)
        .order_by(func.count(Entry.id).desc())
    ).all()

    # Entries per day for the activity strip, oldest day first.
    start = utcnow() - timedelta(days=ACTIVITY_DAYS - 1)
    #: The day is all this reads, so it asks for the day: loading each note
    #: whole (its text and every other column, as an object) was 204 ms on
    #: 5,000 recent notes and is nothing as a bare column.
    recent = session.scalars(
        select(Entry.created_at).where(
            Entry.is_deleted == False,  # noqa: E712
            Entry.is_draft == False,  # noqa: E712
            Entry.is_board == False,  # noqa: E712
            Entry.created_at >= start.replace(hour=0, minute=0, second=0),
        )
    )
    per_day = [0] * ACTIVITY_DAYS
    today = utcnow().date()
    for created_at in recent:
        offset = (today - created_at.date()).days
        if 0 <= offset < ACTIVITY_DAYS:
            per_day[ACTIVITY_DAYS - 1 - offset] += 1

    return {
        "total_entries": total or 0,
        "categories": [{"name": name, "count": count} for name, count in by_category],
        "per_day": per_day,
        "days": ACTIVITY_DAYS,
        #: The review queue's size (WORLD_CLASS_PLAN section 17, row 1), for
        #: the Categories widget's line; the queue itself is the Notes filter
        #: `is:review`.
        "to_review": manager.review_queue_count(session),
    }


# Time-of-day greeting phrases used when the local model isn't available.
# Deliberately name-free: the frontend appends the user's preferred name.
GREETING_FALLBACKS = {
    "morning": ["Good morning", "Morning", "Rise and shine", "A fresh start"],
    "afternoon": ["Good afternoon", "Afternoon", "Hope today's going well"],
    "evening": ["Good evening", "Evening", "Winding down"],
    "night": ["Still up", "Working late", "Burning the midnight oil"],
}

# Keep the greeting from settling into one rut: each generation is nudged
# toward a different flavour, so the banner feels like it's paying attention
# rather than replaying the same line.
GREETING_FLAVOURS = (
    "a plain warm hello",
    "a curious question about what they are working on",
    "a light remark about the time of day",
    "a gentle nudge to capture a thought",
    "a short welcome back",
    "an encouraging line about their notes",
    "a relaxed, casual aside",
)

GREETING_PROMPT = (
    "Write ONE short greeting for someone opening their personal notebook app. "
    "It is currently {block}. Make it {flavour}. Rules: 2 to 7 words, no name, "
    "no quotation marks, no emoji, and do not mention the app by name. It may "
    "be a question. End it with a full stop or a question mark. Reply with "
    "the greeting only."
)

# When the user has set a display name we usually ask the model to weave it in,
# so the greeting reads naturally ("Morning, Sam.") instead of always being a
# phrase with a name bolted on. The name comes from preferences, never
# hardcoded. Not every greeting uses it, so it doesn't get repetitive.
GREETING_PROMPT_NAMED = (
    "Write ONE short greeting for {name}, who is opening their personal "
    "notebook app. It is currently {block}. Make it {flavour}. Rules: 2 to 8 "
    "words, use the name {name} exactly once and spell it exactly as given, no "
    "quotation marks, no emoji, and do not mention the app by name. It may be a "
    "question. End it with a full stop or a question mark. Reply with the "
    "greeting only."
)

# How often a greeting addresses the user by name when one is set.
NAME_USE_CHANCE = 0.75

# The greeting is stored without its final mark so the display name can be
# appended cleanly ("Good morning" + ", Sam" + "."). The mark travels
# separately in `punctuation`. An exclamation mark comes back as a full stop:
# the app's copy carries none (CLAUDE.md, standing order 6), and a small model
# reaches for one whether or not it is asked to (INBOX 472).
_TERMINAL_MARKS = ".!?"


def _clean_greeting(raw: str) -> tuple[str, str] | None:
    """Return (phrase, terminal mark): or None if the reply is unusable."""
    text = (raw or "").strip().splitlines()[0] if (raw or "").strip() else ""
    text = text.strip().strip("\"'`*").strip()
    mark = "."
    # Remember a question so the greeting keeps its tone, then strip trailing
    # punctuation so a name can be appended after it.
    while text and text[-1] in _TERMINAL_MARKS + ",;:":
        if text[-1] == "?":
            mark = "?"
        text = text[:-1].rstrip()
    # A little headroom over the prompt's word limit, since a woven-in name
    # costs a word or two.
    if not text or len(text) > 56 or len(text.split()) > 9:
        return None
    # Small local models often answer in lowercase; the banner is a sentence,
    # so open it with a capital. Only the first character is touched, leaving
    # any legitimately capitalised words alone.
    return _sentence_case(text), mark


def _sentence_case(text: str) -> str:
    return text[0].upper() + text[1:] if text else text


def _composed_greeting(session, config, block: str) -> tuple[str, str, str]:  # noqa: ANN001
    """(phrase, mark, source). Without a model the composer writes it (INBOX 876):
    seven times of day, the weekday and the notebook's own numbers."""
    try:
        now = user_now(config)
        phrase, mark = greeting_compose.compose(now, greeting_compose.gather(session, now))
        return phrase, mark, "composed"
    except Exception:  # noqa: BLE001  # the banner never fails over a count
        return random.choice(GREETING_FALLBACKS.get(block) or GREETING_FALLBACKS["morning"]), ".", "fallback"


@router.get("/greeting")
def greeting(block: str = "morning", session: Session = Depends(get_session)) -> dict:
    """A short greeting phrase for the dashboard banner.

    AI-written when the local model is up, otherwise a handwritten fallback, 
    the banner must never depend on Ollama being available. The phrase never
    contains a name; the frontend adds one from preferences.
    """
    config = deps.get_config()
    phrase, mark, source = _composed_greeting(session, config, block)
    fallback = {
        "greeting": phrase,
        "punctuation": mark,
        "append_name": True,  # composed phrases are name-free
        "source": source,
    }

    ollama = deps.get_ollama()
    if not backend_hint.running(ollama):
        return fallback
    return _greeting_within(config, ollama, block, fallback)


#: How long the banner waits for the model's greeting before it shows the
#: composed one (audit 1030 A39: a hung model held the route 4,005 ms).
GREETING_WAIT = 0.5
_GREETING_FLIGHT: dict[str, Future] = {}


def _spawn(fn, *args) -> Future:  # noqa: ANN001, ANN002
    """`fn(*args)` on a daemon thread, so a model that never answers cannot
    hold the app open when it quits (a pool's threads are joined at exit)."""
    future: Future = Future()

    def run() -> None:
        try:
            future.set_result(fn(*args))
        except BaseException as exc:  # noqa: BLE001  # carried to whoever reads the result
            future.set_exception(exc)

    threading.Thread(target=run, name="greeting", daemon=True).start()
    return future


def _greeting_within(config, ollama, block: str, fallback: dict) -> dict:  # noqa: ANN001
    """The model's greeting if it comes within `GREETING_WAIT`, else the
    composed one now. A call that runs late is not cancelled: the next
    request takes its result, and while one is still running no second is
    started, so a hung model costs one thread and no wait."""
    flight = _GREETING_FLIGHT.get(block)
    if flight is not None:
        if not flight.done():
            return fallback
        _GREETING_FLIGHT.pop(block, None)
        try:
            return flight.result()
        except Exception:  # noqa: BLE001  # a failed late call is the composed greeting
            return fallback
    flight = _spawn(_ai_greeting, config, ollama, block, fallback)
    _GREETING_FLIGHT[block] = flight
    try:
        result = flight.result(timeout=GREETING_WAIT)
    except FutureTimeout:
        return fallback
    except Exception:  # noqa: BLE001  # any model failure degrades to the composed greeting
        result = fallback
    _GREETING_FLIGHT.pop(block, None)
    return result


def _ai_greeting(config, ollama, block: str, fallback: dict) -> dict:  # noqa: ANN001
    # The name is read from preferences here rather than trusted from the
    # client, so there is exactly one source of truth for it.
    name = str(config.get_preference("display_name", "") or "").strip()
    # Most greetings use the name, but not all, variety matters more than
    # rigid consistency here.
    use_name = bool(name) and random.random() < NAME_USE_CHANCE
    flavour = random.choice(GREETING_FLAVOURS)
    # dashboard_persona is an independent override (asked for directly: the
    # dashboard greeting shouldn't have to match whichever persona is active
    # for Chat/search). Empty/unset falls through to that same active
    # persona: resolve_persona_prompt's own `name or active_persona`
    # default: so nothing changes for anyone who hasn't set one.
    dashboard_persona_name = str(config.get_preference("dashboard_persona", "") or "").strip() or None
    persona = librarian.resolve_persona_prompt(dashboard_persona_name, config)
    system = (
        GREETING_PROMPT_NAMED.format(block=block, name=name, flavour=flavour)
        if use_name
        else GREETING_PROMPT.format(block=block, flavour=flavour)
    )
    if persona:
        system = f"{persona.strip()} {system}"
    ask = f"It is {block}. Greet {name}." if use_name else f"It is {block}. Greet me."
    try:
        reply = ollama.chat(
            deps.get_model_manager().utility_model(),
            [
                {"role": "system", "content": system},
                {"role": "user", "content": ask},
            ],
        )
    except Exception:  # noqa: BLE001  # any model failure degrades to fallback
        return fallback

    cleaned = _clean_greeting(reply.get("content", "") if isinstance(reply, dict) else "")
    if not cleaned:
        return fallback
    phrase, mark = cleaned

    # **The name at most once, wherever it falls.** Reported with a screenshot
    # (granite4.1:3b): "Braiden, nice to meet you under the stars, Brayden!".
    # The model spelt it right once and wrong once, as the *first* word, which
    # `_name_like_words` skips, so the exact match below passed the greeting
    # through with both. Every word is counted here, the opening one included:
    # two attempts at the name is not a slip to repair, it is a greeting that
    # names you twice, and the handwritten one is used instead.
    if name:
        mentions = _name_mentions(phrase, name)
        if len(mentions) > 1:
            return fallback
        if mentions and mentions[0].lower() != name.lower():
            phrase = re.sub(rf"\b{re.escape(mentions[0])}\b", name, phrase, count=1)

    # `append_name` tells the frontend whether to add the name itself. It only
    # does so when we asked for a named greeting and the model failed to use
    # one: so the name appears exactly once when wanted, and not at all on the
    # deliberately nameless ones.
    append_name = use_name
    if name:
        match = re.search(re.escape(name), phrase, re.IGNORECASE)
        if match:
            # Normalise to the spelling the user saved, in case the model
            # lower-cased it.
            phrase = phrase[: match.start()] + name + phrase[match.end() :]
            append_name = False
        else:
            phrase, fixed = _repair_misspelt_name(phrase, name)
            if fixed:
                append_name = False

    # **A greeting must never call the user by a name they did not save.**
    # Reported: "the model spelt my name wrong in the dashboard welcome
    # message." The exact-match normalisation above is the only thing that ever
    # touched the model's spelling, so a near miss, "Braden" for "Brayden" , 
    # sailed straight through it, and `append_name` stayed True on top, which
    # is how the banner ends up greeting two people.
    #
    # `_repair_misspelt_name` catches the near misses. This catches the rest: a
    # model that invents a different name entirely, or addresses someone when
    # no name is saved at all. There is no repairing that, so the handwritten
    # greeting is used instead, being greeted impersonally is a non-event, and
    # being greeted by the wrong name is the kind of small wrongness that makes
    # a person stop trusting everything else the app says.
    if _greets_a_stranger(phrase, name):
        return fallback

    return {
        "greeting": phrase,
        "punctuation": mark,
        "append_name": append_name,
        "source": "ai",
    }


#: How close a word has to be to the saved name before it is treated as the
#: model's attempt at it rather than as a different word. 0.72 accepts
#: "Braden"/"Brayden" (0.77) and "Sammy"/"Sam" (0.75) while refusing ordinary
#: words that merely share letters, "Sunday"/"Sam" scores 0.44.
NAME_SIMILARITY = 0.72


def _name_like_words(phrase: str) -> list[str]:
    """The capitalised words in a greeting that could be someone's name.

    The first word is skipped: every greeting starts with one ("Morning",
    "Welcome") and it is capitalised because it opens the sentence, not because
    it is a name.
    """
    words = re.findall(r"[A-Za-z][A-Za-z'\-]*", phrase)
    return [word for word in words[1:] if word[:1].isupper()]


def _name_mentions(phrase: str, name: str) -> list[str]:
    """Every word in the greeting that is the saved name or a near miss of it,
    the opening word included (unlike `_name_like_words`, which is about what
    *could* be a name; this is about what is an attempt at this one)."""
    target = name.lower()
    return [
        word
        for word in re.findall(r"[A-Za-z][A-Za-z'\-]*", phrase)
        if difflib.SequenceMatcher(None, word.lower(), target).ratio() >= NAME_SIMILARITY
    ]


def _repair_misspelt_name(phrase: str, name: str) -> tuple[str, bool]:
    """Put the saved spelling back where the model got it nearly right.

    Returns the phrase and whether anything was replaced. Only the *closest*
    candidate is replaced, and only one: a greeting with two near-miss names in
    it is not a spelling slip, it is a greeting for somebody else.
    """
    best: tuple[float, str] | None = None
    for word in _name_like_words(phrase):
        if word.lower() == name.lower():
            continue
        score = difflib.SequenceMatcher(None, word.lower(), name.lower()).ratio()
        if score >= NAME_SIMILARITY and (best is None or score > best[0]):
            best = (score, word)
    if best is None:
        return phrase, False
    return re.sub(rf"\b{re.escape(best[1])}\b", name, phrase, count=1), True


def _greets_a_stranger(phrase: str, name: str) -> bool:
    """True when the greeting addresses a name that is not the saved one.

    A vocative only: "Hello, Dave" and "Welcome back, Dave!" address someone,
    while "Time to write" and "Morning: Tuesday already" do not. Matching on
    the comma is what keeps ordinary capitalised words (a weekday, a place a
    persona mentions) from being read as names.
    """
    vocative = re.search(r",\s*([A-Z][A-Za-z'\-]*)\s*[.!?]?\s*$", phrase.strip())
    if not vocative:
        return False
    spoken = vocative.group(1)
    if not name:
        return True  # nobody to greet, so any name here is invented
    return spoken.lower() != name.lower()


@router.get("/heatmap")
def heatmap(session: Session = Depends(get_session)) -> dict:
    """Daily note counts for the last ~year, for the activity heatmap.

    Returned oldest-first with the ISO date of the first day so the frontend
    can lay the weeks out without guessing.
    """
    today = utcnow().date()
    start = today - timedelta(days=HEATMAP_DAYS - 1)
    counts = [0] * HEATMAP_DAYS
    #: Only the day, as a column (see `stats`): 208 ms became a few on 5,000
    #: notes created within the year.
    rows = session.scalars(
        select(Entry.created_at).where(
            Entry.is_deleted == False,  # noqa: E712
            # Notes only, the one count the rest of the app shows (boards
            # and drafts are Entry rows too: the heatmap said 77 beside 40).
            Entry.is_draft == False,  # noqa: E712
            Entry.is_board == False,  # noqa: E712
            Entry.created_at >= utcnow() - timedelta(days=HEATMAP_DAYS),
        )
    )
    for created_at in rows:
        offset = (created_at.date() - start).days
        if 0 <= offset < HEATMAP_DAYS:
            counts[offset] += 1
    return {
        "start": start.isoformat(),
        "days": HEATMAP_DAYS,
        "counts": counts,
        "total": sum(counts),
        "busiest": max(counts) if counts else 0,
    }


@router.get("/day")
def day_digest_lines(now: str = "", session: Session = Depends(get_session)) -> dict:
    """The dashboard's day digest (`ai/day_digest.py`): each line a count or
    a quoted span, with no model. `now` (ISO 8601 with an offset) fixes the
    clock for a test; one that does not parse is ignored."""
    from tessellate.ai import day_digest

    clock = user_now(deps.get_config())
    try:
        given = datetime.fromisoformat(now) if now else None
    except ValueError:
        given = None
    if given is not None and given.tzinfo is not None:
        clock = given
    return day_digest.compose(session, clock)


@router.get("/patterns")
def patterns(session: Session = Depends(get_session)) -> dict:
    """The Patterns line (CHAT_PLAN decision 32): what the notes measure,
    each a count or a date with one fixed hedge, never a claim; Tidy and the
    dashboard show it. No model, nothing filed as a fact."""
    from tessellate.ai import insights

    found = insights.from_session(session, user_now(deps.get_config()).date())
    known = insights.memory(session)
    return {"patterns": [insights.as_row(i, known) for i in found]}


@router.get("/today-line")
def today_line(seed: int = 0, session: Session = Depends(get_session)) -> dict:
    """The dashboard's line under the greeting, composed from the notebook
    (`composer_voice.today_line`): the wording and tail rotate with `seed`,
    the page draws a new one each visit and every few minutes. No model;
    private and binned notes are never read. `text` is empty for an empty
    notebook, so the page falls back to its counts."""
    from tessellate.ai import composer_voice

    cats = {c.id: c.name for c in session.scalars(select(Category)).all()}
    shown = (Entry.is_deleted == False, Entry.is_private == False, Entry.is_draft == False, Entry.is_board == False)  # noqa: E712
    rows = session.scalars(select(Entry).where(*shown).order_by(Entry.created_at.desc()).limit(120)).all()
    #: The 120 rows are the sample the line names notes from; how many were
    #: written today and yesterday is counted in SQL, so a bulk import is not
    #: capped at the sample's size (audit 1028 S8).
    today = user_now(deps.get_config()).date()
    day = func.date(Entry.created_at)
    asked = [today.isoformat(), (today - timedelta(days=1)).isoformat()]
    counts = {
        date.fromisoformat(d): n
        for d, n in session.execute(select(day, func.count()).where(*shown, day.in_(asked)).group_by(day)).all()
    }
    notes = [
        {
            "id": e.id,
            "content": e.content or "",
            "created_at": e.created_at.date().isoformat() if e.created_at else "",
            "tags": manager.shown_tags(e),
            "category": "" if cats.get(e.category_id, "").lower().startswith("uncategori") else cats.get(e.category_id, ""),
        }
        for e in rows
    ]
    line = composer_voice.today_line(notes, today=today, seed=seed, counts=counts)
    if not line:
        #: An empty notebook is welcomed in words (CHAT_PLAN 1353), not left blank.
        from tessellate.api import chat_extra

        try:
            now = user_now(deps.get_config()).replace(tzinfo=None)
            voice = str(deps.get_config().get_preference("composer_voice", "natural") or "natural")
            text = chat_extra.welcome_line(session, now, voice=voice, seed=f"{seed}:{now.date()}") if not notes else ""
        except Exception:  # noqa: BLE001  # the page falls back to its counts
            text = ""
        return {"text": text, "kind": "welcome" if text else "none", "sources": []}
    return {"text": line["text"].replace("**", ""), "kind": line["kind"], "sources": line["sources"]}


class InsightVerdict(BaseModel):
    """An insight line as the page has it, with what the person said of it
    (CHAT_PLAN decision 60)."""

    rule: str = Field(max_length=20)
    text: str = Field(default="", max_length=2000)
    note_ids: list[int] = Field(default_factory=list, max_length=200)
    slots: dict = Field(default_factory=dict)


@router.post("/confirm", status_code=201)
def confirm_insight(body: InsightVerdict, session: Session = Depends(get_session)) -> dict:
    """Confirm: the insight is written as a fact the person vouched for,
    "confirmed by you, <date>", and said that way from the next turn on."""
    from tessellate.ai import insights

    try:
        done = insights.confirm(session, body.model_dump(), user_now(deps.get_config()).date())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    return done


@router.post("/dismiss", status_code=201)
def dismiss_insight(body: InsightVerdict, session: Session = Depends(get_session)) -> dict:
    """Not right: this insight and its near-variants are not shown again."""
    from tessellate.ai import insights

    try:
        done = insights.dismiss(session, body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    return done


@router.post("/done", status_code=201)
def done_insight(body: InsightVerdict, session: Session = Depends(get_session)) -> dict:
    """Done: a plan line is finished. Its confirmed fact is removed and it,
    with its variants, is not shown again (INBOX 1412)."""
    from tessellate.ai import insights

    try:
        result = insights.done(session, body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    return result


@router.get("/tag-cloud")
def tag_cloud(session: Session = Depends(get_session)) -> list[dict]:
    """Every tag with its frequency, most-used first, for a weighted cloud.

    Was its own independent full-entry scan + tag-JSON decode, duplicating
    `manager.all_tags`, the same computation, run twice in two places.
    """
    ordered = manager.all_tags(session).items()
    return [{"tag": tag, "count": count} for tag, count in list(ordered)[:60]]


@router.get("/on-this-day")
def on_this_day(session: Session = Depends(get_session)) -> list[dict]:
    """Notes captured on today's date in earlier months/years, a gentle
    resurfacing of old thoughts (from the original idea doc).

    **Not called by this app's own frontend, and that is a decision, not an
    oversight** (INBOX 261, found by `scratchpad/probe_dead_routes.py`, which
    lists every route no `frontend/js/*.js` names). The dashboard's widget
    filters `allEntries` in the browser: one fewer request, and correct once
    the notebook has finished paging in. This stays for anything that talks
    to the app over HTTP rather than through the bundled page, and this
    paragraph is here so the next scan does not re-open the question.

    The day-of-month and "at least 28 days old" checks used to load every
    non-deleted entry and filter in a Python loop; SQLite does both in the
    WHERE clause instead now, so only matching rows are ever hydrated into
    ORM objects. Also now excludes private notes, every other view in this
    app does (search, timeline, embeddings...), and this one, uniquely,
    read `entry.content` straight off the column, which is ciphertext for a
    private note, not the private-note placeholder every other surface uses.
    """
    now = utcnow()
    matched_entries = list(
        session.scalars(
            select(Entry).where(
                Entry.is_deleted == False,  # noqa: E712
                Entry.is_private == False,  # noqa: E712
                Entry.created_at <= now - timedelta(days=28),
                func.strftime("%d", Entry.created_at) == f"{now.day:02d}",
            )
            #: The five it answers with, read as five (ARCH-13): every match
            #: was hydrated, about a thirtieth of the notebook, to keep five.
            .order_by(Entry.id)
            .limit(5)
        )
    )
    category_names = manager.bulk_category_names(session, matched_entries)

    matches = [
        {
            "id": entry.id,
            "content": entry.content,
            "category": category_names.get(entry.category_id, manager.UNCATEGORISED),
            "created_at": entry.created_at.isoformat(),
        }
        for entry in matched_entries
    ]
    return matches[:5]


#: The digest's own instruction. `{today}` is filled in per request by
#: `digest_question`, on the user's own clock.
#:
#: **Dates, not a ban on time words.** Reported 2026-09-23: a note written the
#: day before that said "tonight" came back as "you have work tonight". The
#: model was never told when a note was written or what today is, so
#: "tonight" could only mean tonight. A previous pass told it to use no time
#: references at all, which a small model cannot do while summarising notes
#: that are full of them. Each note now carries its date
#: (`librarian._written_hint`) and this names today, so the words can be read
#: against the right day and a past one said as past.
#:
#: The greeting is asked against here and taken off afterwards
#: (`answer_trim`), because a small model writes it anyway.
DIGEST_QUESTION = (
    "Today is {today}. Give me a short digest of what I saved in the last "
    "seven days, grouped by topic, calling out anything that looks important "
    "or unfinished. Each note shows the day it was written: read words like "
    "'tonight', 'tomorrow' or 'next week' against the day it was written, not "
    "today, and say anything that has already happened in the past tense or "
    "by its date. Start with the digest itself: no greeting, and no sentence "
    "announcing it."
)


def _long_date(when: datetime) -> str:
    """"Wednesday 23 September 2026". Spelled out, because a small model
    reasons about "Tuesday" far more reliably than about "2026-09-22", and
    built by hand because `%-d` does not exist on Windows."""
    return f"{when:%A} {when.day} {when:%B %Y}"


def _written_label(created_at: datetime | None, zone) -> str:  # noqa: ANN001
    """The day a note was written, on the user's own clock.

    Stored in UTC (SQLite hands a naive value back), shown in the zone the
    user reads: a note saved at 11pm is that day's note, not tomorrow's.
    """
    if created_at is None:
        return ""
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return _long_date(created_at.astimezone(zone))


def digest_question(session: Session) -> str:
    """The digest instruction for right now, with its structure sentence."""
    today = user_now(deps.get_config())
    return DIGEST_QUESTION.format(today=_long_date(today)) + digest_structure_note(session)


def _digest_notes(session: Session) -> list[dict]:
    cutoff = utcnow() - timedelta(days=7)
    # `is_private == False`: this content is handed straight to the AI, and a
    # private note's `content` column is ciphertext at rest, sending it here
    # put encrypted bytes in the model's prompt (and, since the model doesn't
    # know that, sometimes into the digest text a user then reads). Every
    # other surface that feeds the AI already excludes private notes;
    # `digest_structure_note` below does too for its own sentence, this was
    # the one place a private note's row still reached the model.
    entries = list(
        session.scalars(
            select(Entry)
            .where(
                Entry.is_deleted == False,  # noqa: E712
                Entry.is_private == False,  # noqa: E712
                Entry.created_at >= cutoff,
            )
            .order_by(Entry.created_at)
            .limit(30)
        )
    )
    category_names = manager.bulk_category_names(session, entries)
    now = user_now(deps.get_config())
    zone = now.tzinfo
    time_words = manager.entry_dates_bulk(session, [e.id for e in entries])
    return [
        {
            "content": e.content,
            "category": category_names.get(e.category_id, manager.UNCATEGORISED),
            "written": _written_label(e.created_at, zone),
            "dates": [
                f'"{d.phrase}" meant {d.at:%A} {d.at.day} {d.at:%B %Y}, {days_from_today(d.at.date(), now.date())}'
                for d in time_words.get(e.id, [])
            ],
        }
        for e in entries
    ]


def digest_structure_note(session: Session) -> str:
    """One sentence about how this week's notes sit in the notebook, or "".

    The digest could see the week's notes and their categories and nothing
    else: which means it could summarise *what* you wrote and never notice
    that five of those notes are joined to nothing, or that three of them
    landed in the same corner of the notebook. That is the thing a weekly recap
    is actually for, and it is exactly what the graph knows.

    Deliberately **facts, not adjectives**: counts the model can repeat and the
    user can verify by clicking, rather than a judgement it would have to take
    on trust. And deliberately one sentence, this rides in the prompt of a
    background job on a utility model, and §11a's budget applies here as much
    as anywhere.
    """
    cutoff = utcnow() - timedelta(days=7)
    fresh = list(
        session.scalars(
            select(Entry).where(
                Entry.is_deleted == False,  # noqa: E712
                Entry.is_private == False,  # noqa: E712
                Entry.created_at >= cutoff,
            )
        )
    )
    if not fresh:
        return ""
    index = paths.build(session, include_private=False)
    loose = set(paths.orphans(index))
    unconnected = [entry for entry in fresh if entry.id in loose]
    if not unconnected:
        return (
            f" Every one of this week's {len(fresh)} notes is connected to "
            "something else in the notebook, say so briefly, it is worth "
            "knowing."
        )
    return (
        f" Of this week's {len(fresh)} notes, {len(unconnected)} are connected "
        "to nothing else in the notebook, no link, no reply, no shared tag. "
        "Mention that count and name one or two of them, so they can be tied "
        "in. Do not guess at connections that are not there."
    )


def composed_week(session: Session) -> str:
    """The weekly digest with no model, from the rows (`activity.week`)."""
    from tessellate.ai import activity

    return activity.week(session, user_now(deps.get_config()))


@router.post("/digest/stream")
def weekly_digest_stream(session: Session = Depends(get_session)) -> StreamingResponse:
    """The weekly digest, streamed token by token (NDJSON).

    Same content as POST /digest, this one just arrives progressively, so a
    slow local model shows words instead of a spinner.
    """
    notes = _digest_notes(session)
    config = deps.get_config()
    ollama = deps.get_ollama()
    model_manager = deps.get_model_manager()

    def lines() -> Iterator[str]:
        def event(payload: dict) -> str:
            return json.dumps(payload) + "\n"

        if not notes:
            yield event({"type": "answer", "delta": "Nothing was saved in the last 7 days."})
            yield event({"type": "done", "cacheable": True})
            return
        if not ollama.is_running():
            #: With no model the composer says the week (owner-1026b K3); not
            #: cached, so a model, once on, writes the next one.
            yield event({"type": "answer", "delta": composed_week(session)})
            yield event({"type": "done", "cacheable": False})
            return

        digest_style = config.get_preference("communication_style", "friendly")
        digest_persona = librarian.resolve_persona_prompt(None, config)
        messages = librarian.build_messages(
            digest_question(session),
            notes,
            style=digest_style,
            profile="",
            persona_prompt=digest_persona,
            # The digest is the worst case for an unbudgeted prompt: it hands
            # over a week of notes at once, so "however many turned up" was
            # never a number anyone checked. Budgeted against the utility
            # model, which is what streams it below, and which is often the
            # *small* model, with the smallest window in the app.
            budget=librarian.plan_budget(
                model_manager.utility_model(), ollama, digest_style, "", digest_persona
            ),
        )
        answer = []
        try:
            for piece in ollama.chat_stream(model_manager.utility_model(), messages):
                if "content_delta" in piece:
                    answer.append(piece["content_delta"])
                    yield event({"type": "answer", "delta": piece["content_delta"]})
                elif "thinking_delta" in piece:
                    yield event({"type": "thinking", "delta": piece["thinking_delta"]})
        except OllamaError:
            #: A server up with no model that can answer: the composed week,
            #: unless the model had already started on its own.
            said = f"\n\n{librarian.OFFLINE_MESSAGE}" if answer else composed_week(session)
            yield event({"type": "answer", "delta": said})
            yield event({"type": "done", "cacheable": False})
            return
        #: The greeting and the announcement come off, the same trim and the
        #: same event the chat stream sends (`routes_chat`): the widget has
        #: already drawn the untrimmed words, so it gets the finished text
        #: once and repaints, rather than a filter on every delta. Only when
        #: something was taken, so an ordinary digest costs no extra event.
        raw = "".join(answer)
        trimmed = trim_assistant_padding(raw)
        if trimmed != raw:
            yield event({"type": "answer_final", "text": trimmed})
        yield event({"type": "done", "cacheable": True})

    return StreamingResponse(lines(), media_type="application/x-ndjson")


@router.post("/digest")
def weekly_digest(session: Session = Depends(get_session)) -> dict:
    """An on-demand AI recap of the last 7 days (reads only).

    **Superseded on the dashboard by `/insights/digest/stream`**, which says
    the same thing a token at a time instead of after a long silence, and is
    what the widget calls (INBOX 261). Kept rather than deleted because it is
    the one shape a caller that cannot read an event stream can use, and
    because the two share `_digest_notes` below, so it costs a function call
    to keep and a second code path to reimplement later.
    """
    notes = _digest_notes(session)
    if not notes:
        # A real, stable fact, safe for the UI to cache for the day.
        return {
            "digest": "Nothing was saved in the last 7 days.",
            "thinking": None,
            "cacheable": True,
        }

    config = deps.get_config()
    # Only a genuine AI answer is worth caching: with no model the digest is
    # the composed week (owner-1026b K3), which a model, once on, replaces.
    ollama_running = deps.get_ollama().is_running()
    if not ollama_running:
        return {"digest": composed_week(session), "thinking": None, "cacheable": False}
    digest, thinking = librarian.answer(
        digest_question(session),
        notes,
        deps.get_model_manager(),
        deps.get_ollama(),
        style=config.get_preference("communication_style", "friendly"),
        persona_prompt=None,
        use_utility_model=True,  # a background job, keep the chat model free
    )
    # The same trim the stream applies (see there).
    return {
        "digest": trim_assistant_padding(digest),
        "thinking": thinking,
        "cacheable": ollama_running,
    }
