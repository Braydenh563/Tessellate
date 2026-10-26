"""The app's voice: the composer's remarks outside an answer.

Asked for by the owner, 2026-10-06 (CHAT_PLAN, "the composer everywhere"):
*"use the composer basically really good sentence model like an ai or apple's
siri really smartly to improve quality of life across the app ... like with
the companion message bubbles"*, with the north star *"soooo good that users
dont even need to install ai"*.

**One engine, one rule.** This is `composer.py`'s other half, not a second
writer: it reads notes with `composer.read_note`, quotes them through the same
`_Answer` (so every quote is a cited row with offsets), names days the way an
answer does, and keeps the rule that module states at its top. Every factual
clause of a remark is one of:

- a note's own sentence or list item, quoted (`quote`), or its name (`title`);
- a tag or category the note is filed under (`filed`);
- a reminder's own words (`reminder`);
- a word that each named note contains (`word`), for a pattern;
- a value the app measured (`measure`): a count, a day, a year.

Everything else comes from `VOICE`, a closed phrasebook that says nothing
about the world ("Still open in ", " is due today."). The tests hold every
part of every remark to that (`tests/test_composer_voice.py`), and the eval
(`tests/_voice_eval.py`) measures what the owner asked for: grounded, never
twice the same, short.

**Kept apart from `composer.py`** so the answer path (Ask and Chat, owned by
another session) and the voice can change without stepping on each other; the
shared machinery is imported, never copied.

Pure and deterministic: the same notes on the same day give the same remarks.
Wording varies by day and by note (`composer._pick` over a salt), so the same
note resurfacing next week is said differently.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import date, datetime, timedelta

from tessellate.ai import composer
from tessellate.ai.composer import NoteView, Sentence, _Answer, _count_word, read_note
from tessellate.search import query as query_understanding

#: The voice's fixed phrases: the only words written here. The punctuation keys
#: mirror an answer's; the rest start `v_`. Sentence case, no em-dash, no
#: exclamation mark (docs/DESIGN.md, "App voice"; the test holds it).
VOICE: dict[str, str] = {
    # Layout and punctuation, the same marks an answer uses, held here so the
    # voice does not move when the answer's phrasebook is reworded.
    "para": "\n\n",
    "line": "\n",
    "bullet": "- ",
    "task_open": "- [ ] ",
    "bold": "**",
    "colon": ": ",
    "comma": ", ",
    "stop": ".",
    "open_quote": "“",
    "close_quote": "”",
    "open_paren": " (",
    "close_paren": ")",
    "and": " and ",
    "to_span": " to ",
    "on_day": ", on ",
    "says_a": "Your note ",
    "says_a_end": " says: ",
    "next_latest_a": "What is the latest on ",
    "next_tag_a": "What else do my notes say about ",
    "next_tag_b": "?",
    # A reminder due.
    "v_due_today": " is due today.",
    "v_due_was": " was due ",
    "v_due_tomorrow": " is due tomorrow.",
    "v_due_from": " It comes from ",
    "v_due_says": ", which says: ",
    # A note brought back.
    "v_back_a": "From ",
    "v_back_a_mid": ", your note ",
    "v_back_b": "A while back, on ",
    "v_back_b_mid": ", you wrote in ",
    "v_back_c": "Remember ",
    "v_back_c_mid": "? You wrote it on ",
    "v_back_c_end": ": ",
    # On this day.
    "v_otd_year": "On this day in ",
    "v_otd_year_mid": ", you wrote ",
    "v_otd_months_end": " months ago today, you wrote ",
    "v_otd_month": "A month ago today, you wrote ",
    # Something left open.
    "v_open_a": "Still open in ",
    "v_open_b": "Not ticked yet, in ",
    "v_open_count": " has ",
    "v_open_count_mid": " of ",
    "v_open_count_end": " items still open, the first: ",
    # A pattern this week.
    "v_pattern_mid": " of your notes this week mention ",
    "v_pattern_tag_mid": " of your notes this week are filed under ",
    # The week as a count.
    "v_week_a": "You have written ",
    "v_week_a_end": " notes this week",
    "v_week_one": "You have written one note this week",
    "v_week_most": ", most of them under ",
    # A day with nothing in it yet.
    "v_empty_a": "Nothing written yet today. Your last note, ",
    "v_empty_a_mid": ", from ",
    "v_empty_b": "A blank page so far today. The last thing you wrote, in ",
    "v_empty_b_mid": " on ",
    "v_says": ", says: ",
    # Today's line on the dashboard.
    "v_today_wrote": "You have written ",
    "v_today_notes": " notes today, the latest ",
    "v_today_one": "You have written one note today, ",
    "v_yesterday": "Yesterday you wrote ",
    "v_and_more": " and ",
    "v_more": " more",
    "v_last_was": "Your last note was ",
    # Variants of today's line (`today_line`'s seed picks among them).
    "v_today_wrote_b": "Today has ",
    "v_today_wrote_c": "So far today: ",
    "v_today_wrote_d": "A busy page today, ",
    "v_today_wrote_e": "Already today, ",
    "v_today_wrote_f": "The page has filled a little: ",
    "v_today_notes_e": " notes, the latest ",
    "v_today_notes_f": " notes, the newest ",
    "v_today_one_e": "Today so far there is one note, ",
    "v_today_one_f": "A single note today, ",
    "v_yesterday_e": "Yesterday you set down ",
    "v_yesterday_f": "Your last page was yesterday: ",
    "v_last_was_e": "It has been a little while. You last wrote ",
    "v_last_was_f": "Picking up from ",
    "v_today_notes_b": " notes so far, the latest ",
    "v_today_notes_c": " notes, the latest ",
    "v_today_notes_d": " notes, the latest of them ",
    "v_today_one_b": "One note so far today, ",
    "v_today_one_c": "Today's page has one note, ",
    "v_today_one_d": "You started today with ",
    "v_yesterday_b": "Yesterday's page held ",
    "v_yesterday_c": "You were here yesterday with ",
    "v_yesterday_d": "Last written yesterday, ",
    "v_last_was_b": "The page is fresh. You last wrote ",
    "v_last_was_c": "Last time you wrote ",
    "v_last_was_d": "Nothing new since ",
    "v_tail_week_a": " That makes ",
    "v_tail_week_b": " in the last seven days.",
    "v_tail_week_c": " That is ",
    "v_tail_week_d": " this week so far.",
    "v_tail_week_e": " ",
    "v_tail_week_f": " notes in the past week.",
    "v_tail_cat": " The week has gone mostly under ",
    "v_otd_short": " On this day in ",
    "v_otd_short_mid": " you wrote ",
    # The week in review.
    "v_review_lead": "You wrote ",
    "v_review_lead_one": "You wrote one note",
    "v_review_notes": " notes",
    "v_review_span": " in the last seven days, from ",
    "v_review_most": " Most went under ",
    "v_review_then": ", then ",
    "v_review_stand": "What stands out:",
    "v_review_open": "Still open:",
    "v_review_open_in": ", in ",
    "v_review_loose": "Linked to nothing yet: ",
    "v_review_none": "Nothing was saved in the last 7 days.",
    # Find anything's one line.
    "v_more_below": " More below.",
    # Suggested searches.
    "v_search_tag": "Notes filed under ",
    "v_search_open": "What is still open in ",
}

#: How far back "this week" and "lately" reach, in days.
WEEK_DAYS = 7
RECENT_DAYS = 14

#: At most this many of each kind of remark, so one kind cannot fill the list
#: the companion picks from.
PER_KIND = 3

#: A pattern needs at least this many of the week's notes to share a word.
PATTERN_NOTES = 3

#: A quote in a remark is cut here: a bubble is read at a glance.
REMARK_QUOTE_CHARS = 140

#: The review lists at most this many standouts and open items.
REVIEW_POINTS = 4
REVIEW_OPEN = 3

#: A word too common in a notebook to be a pattern ("today", "need").
_PLAIN = frozenset(
    """today yesterday tomorrow week weeks day days time thing things need want
    make made get got going go went done new good great also just still really
    note notes work bit lot lots back first last next one two three""".split()
)

#: Lead-ins a title is better without.
_TITLE_LEAD = re.compile(
    r"^(?:note to self|reminder|remember to|remember|need to|i need to|have to|i have to|"
    r"must|todo|to do|today i|so|also|ok|okay)\b[\s:,.-]*",
    re.I,
)
TITLE_WORDS = 7
#: A title never ends on these: the cut at seven words can land on one
#: ("Teh first idea is about"), and nothing follows it to say about what.
TITLE_DANGLING = frozenset(
    "about of to for with in on at by from into onto over under between among against "
    "and or but nor so if because that which who whom whose as than then while until "
    "my your our their his her its this these those a an the".split()
)

_QUESTION = re.compile(
    r"^\s*(what|when|who|whom|whose|where|why|how|which|did|do|does|is|are|was|were|"
    r"have|has|had|can|could|should|will|would)\b",
    re.I,
)


class _Voice(_Answer):
    """`_Answer` with the voice's phrasebook and its own part kinds."""

    def t(self, *names: str) -> _Voice:
        #: `_Answer.name` asks for the answer's own phrases ("your note from").
        for name in names:
            self.parts.append(("template", VOICE.get(name) or composer.PHRASES[name]))
        return self

    def word(self, text: str) -> _Voice:
        self.parts.append(("word", text))
        return self

    def reminder(self, text: str, reminder_id: int) -> _Voice:
        self.parts.append(("reminder", text, reminder_id))
        return self

    def filed(self, text: str, note_id: int) -> _Voice:
        self.parts.append(("filed", text, note_id))
        return self

    def quoted(self, s: Sentence) -> _Voice:
        return self.t("open_quote").q(s, []).t("close_quote")

    def names(self, views: list[NoteView]) -> _Voice:
        """"**A**, **B** and **C**"."""
        for i, view in enumerate(views):
            if i:
                self.t("and" if i == len(views) - 1 else "comma")
            self.name(view)
        return self

    def done(self, kind: str, **extra) -> dict:  # noqa: ANN003
        text = self.text
        sources = list(dict.fromkeys(part[2] for part in self.parts if part[0] in ("title", "quote", "filed")))
        return {
            "kind": kind,
            "text": text,
            "parts": self.parts,
            "grounding": self.rows,
            "sources": sources,
            "key": hashlib.sha1(text.encode()).hexdigest()[:12],
            **extra,
        }


def _clip(s: Sentence) -> Sentence:
    """The sentence, cut at a word for a bubble; offsets kept (the cut is a
    prefix, so the row still points at its own text)."""
    if len(s.text) <= REMARK_QUOTE_CHARS:
        return s
    cut = s.text[:REMARK_QUOTE_CHARS]
    space = cut.rfind(" ")
    text = (cut[:space] if space > REMARK_QUOTE_CHARS // 2 else cut).rstrip(" ,;:.") + "…"
    return Sentence(s.note_id, s.rank, s.start, s.end, text, s.words, s.kind, s.done, s.order)


def lead(view: NoteView) -> Sentence | None:
    """The sentence a note is best remembered by: its first sentence of prose
    that says something (five to thirty words), else its first open checklist
    item, else its first unit. A note's opening sentence is usually what it is
    about; a long note's first line a list of names is not."""
    for s in view.sentences:
        if s.kind == "prose" and 5 <= len(s.text.split()) <= 30:
            return _clip(s)
    for s in view.sentences:
        if s.kind == "task" and not s.done:
            return _clip(s)
    return _clip(view.sentences[0]) if view.sentences else None


def _views(notes: list[dict]) -> list[NoteView]:
    return [v for v in (read_note(n, i) for i, n in enumerate(notes or [])) if v and v.title]


def _day(when) -> date | None:  # noqa: ANN001
    if isinstance(when, datetime):
        return when.date()
    if isinstance(when, date):
        return when
    raw = str(when or "")
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _salt(today: date, *bits: object) -> str:
    return today.isoformat() + ":" + ":".join(str(b) for b in bits)


# --- the remarks ----------------------------------------------------------------


def _due(reminders: list[dict], views: dict[int, NoteView], today: date) -> list[dict]:
    out: list[dict] = []
    for r in reminders or []:
        if r.get("done") or not str(r.get("text") or "").strip():
            continue
        due = _day(r.get("due_at"))
        if due is None or due > today + timedelta(days=1):
            continue
        v = _Voice(views, today)
        v.t("open_quote").reminder(str(r["text"]).strip(), r.get("id")).t("close_quote")
        if due == today:
            v.t("v_due_today")
        elif due > today:
            v.t("v_due_tomorrow")
        else:
            v.t("v_due_was").m(v.day(due)).t("stop")
        view = views.get(r.get("entry_id"))
        s = lead(view) if view else None
        if view and s:
            v.t("v_due_from").name(view).t("v_due_says").quoted(s)
        out.append(v.done("due", reminder_id=r.get("id"), note_id=view.id if view else None))
    return out[:PER_KIND]


def _back(view: NoteView, today: date) -> dict | None:
    s = lead(view)
    if not s or not view.written:
        return None
    v = _Voice({view.id: view}, today)
    style = composer._pick(_salt(today, view.id), "back", ["a", "b", "c"])
    if style == "a":
        v.t("v_back_a").m(v.day(view.written)).t("v_back_a_mid").name(view).t("colon").quoted(s)
    elif style == "b":
        v.t("v_back_b").m(v.day(view.written)).t("v_back_b_mid").name(view).t("colon").quoted(s)
    else:
        v.t("v_back_c").name(view).t("v_back_c_mid").m(v.day(view.written)).t("v_back_c_end").quoted(s)
    return v.done("resurfaced", note_id=view.id)


def _on_this_day(views: list[NoteView], today: date) -> list[dict]:
    out: list[dict] = []
    for view in views:
        when = view.written
        if not when or when.day != today.day or when >= today:
            continue
        s = lead(view)
        if not s:
            continue
        v = _Voice({view.id: view}, today)
        if when.year != today.year:
            v.t("v_otd_year").m(str(when.year)).t("v_otd_year_mid").name(view).t("colon").quoted(s)
        else:
            months = today.month - when.month
            if months == 1:
                v.t("v_otd_month")
            else:
                v.m(_count_word(months).capitalize()).t("v_otd_months_end")
            v.name(view).t("colon").quoted(s)
        out.append(v.done("on_this_day", note_id=view.id))
    return out[:PER_KIND]


def _open_items(views: list[NoteView], today: date) -> list[dict]:
    out: list[dict] = []
    for view in views:
        if not view.written or (today - view.written).days > RECENT_DAYS:
            continue
        tasks = [s for s in view.sentences if s.kind == "task"]
        open_ = [s for s in tasks if not s.done]
        if not open_:
            continue
        v = _Voice({view.id: view}, today)
        first = _clip(open_[0])
        if len(open_) > 1:
            v.name(view).t("v_open_count").m(_count_word(len(open_))).t("v_open_count_mid")
            v.m(_count_word(len(tasks))).t("v_open_count_end").quoted(first)
        else:
            v.t("v_open_a" if composer._pick(_salt(today, view.id), "open", ["a", "b"]) == "a" else "v_open_b")
            v.name(view).t("colon").quoted(first)
        out.append(v.done("open", note_id=view.id))
    return out[:PER_KIND]


def _this_week(views: list[NoteView], today: date) -> list[NoteView]:
    return [v for v in views if v.written and 0 <= (today - v.written).days < WEEK_DAYS]


def _surface(word_stem: str, views: list[NoteView]) -> str | None:
    """The word as the person wrote it most often, lower case."""
    forms: Counter = Counter()
    for view in views:
        for raw in re.findall(r"[^\W\d_][\w'-]*", str(view.note.get("content") or "")):
            if composer._stem(raw) == word_stem:
                forms[raw.lower()] += 1
    return forms.most_common(1)[0][0] if forms else None


def _patterns(views: list[NoteView], today: date) -> list[dict]:
    week = _this_week(views, today)
    if len(week) < PATTERN_NOTES:
        return []
    out: list[dict] = []
    # A tag or category three notes share first: what the person filed them
    # under is the pattern they already named.
    filed: dict[str, list[NoteView]] = {}
    for view in week:
        labels = [str(t) for t in (view.note.get("tags") or [])]
        for label in labels:
            filed.setdefault(label, []).append(view)
    for label, group in sorted(filed.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if len(group) < PATTERN_NOTES:
            break
        v = _Voice({g.id: g for g in group}, today)
        v.m(_count_word(len(group)).capitalize()).t("v_pattern_tag_mid").filed(label, group[0].id).t("colon")
        v.names(group[:3]).t("stop")
        out.append(v.done("pattern", word=label))
        if len(out) >= 1:
            break
    # Then a word three notes share, that is not everyday.
    counts: Counter = Counter()
    for view in week:
        counts.update(w for w in view.words if len(w) > 3 and w not in _PLAIN)
    for stem, n in counts.most_common():
        if n < PATTERN_NOTES or len(out) >= 2:
            break
        group = [view for view in week if stem in view.words]
        word = _surface(stem, group)
        if not word or word in _PLAIN or any(r.get("word") == word for r in out):
            continue
        # Every named note must contain the word as written.
        group = [g for g in group if re.search(rf"\b{re.escape(word)}\b", str(g.note.get("content") or ""), re.I)]
        if len(group) < PATTERN_NOTES:
            continue
        v = _Voice({g.id: g for g in group}, today)
        v.m(_count_word(len(group)).capitalize()).t("v_pattern_mid", "open_quote").word(word).t("close_quote", "colon")
        v.names(group[:3]).t("stop")
        out.append(v.done("pattern", word=word))
    return out


def _week_count(views: list[NoteView], today: date) -> dict | None:
    week = _this_week(views, today)
    if not week:
        return None
    v = _Voice({w.id: w for w in week}, today)
    if len(week) == 1:
        v.t("v_week_one")
    else:
        v.t("v_week_a").m(_count_word(len(week))).t("v_week_a_end")
    cats = Counter(str(w.note.get("category") or "") for w in week if w.note.get("category"))
    if len(week) > 2 and cats:
        cat, n = cats.most_common(1)[0]
        if n * 2 > len(week):
            v.t("v_week_most").filed(cat, next(w.id for w in week if w.note.get("category") == cat))
    v.t("stop")
    return v.done("week")


def _empty_day(views: list[NoteView], today: date) -> dict | None:
    dated = sorted((w for w in views if w.written), key=lambda w: (w.written, -w.rank), reverse=True)
    if not dated or dated[0].written >= today:
        return None
    last = dated[0]
    s = lead(last)
    if not s:
        return None
    v = _Voice({last.id: last}, today)
    if composer._pick(_salt(today, last.id), "empty", ["a", "b"]) == "a":
        v.t("v_empty_a").name(last).t("v_empty_a_mid").m(v.day(last.written)).t("v_says").quoted(s)
    else:
        v.t("v_empty_b").name(last).t("v_empty_b_mid").m(v.day(last.written)).t("v_says").quoted(s)
    return v.done("empty_day", note_id=last.id)


def remarks(
    notes: list[dict],
    *,
    today: date,
    reminders: list[dict] | None = None,
    resurfaced: list[int] | None = None,
) -> list[dict]:
    """What the companion could say about the notebook, best first.

    `notes`: recent notes, any this-day-in-an-earlier-year notes and the day's
    resurfaced ones (each `id`, `content`, `created_at`, `category`, `tags`).
    `reminders`: open ones (`id`, `text`, `due_at`, `done`, `entry_id`).
    `resurfaced`: the ids `/resurface` picked for today. Each remark carries
    a `key` (a hash of its words): the companion never says one it has said.
    """
    views = _views(notes)
    by_id = {v.id: v for v in views}
    out: list[dict] = []
    out += _due(reminders or [], by_id, today)
    out += _on_this_day(views, today)
    for nid in (resurfaced or [])[:PER_KIND]:
        if nid in by_id:
            back = _back(by_id[nid], today)
            if back:
                out.append(back)
    out += _patterns(views, today)
    out += _open_items(views, today)
    for one in (_empty_day(views, today), _week_count(views, today)):
        if one:
            out.append(one)
    seen: set[str] = set()
    unique = []
    for r in out:
        if r["key"] not in seen:
            seen.add(r["key"])
            unique.append(r)
    return unique


# --- the dashboard ----------------------------------------------------------------


def _draw(seed: int, slot: str, n: int) -> int:
    """A stable index below `n` for this seed and slot: slots draw
    independently, so the openings and the tails mix."""
    return int.from_bytes(hashlib.sha1(f"{seed}:{slot}".encode()).digest()[:4], "big") % n


def today_line(notes: list[dict], *, today: date, seed: int = 0) -> dict | None:
    """One short sentence for under the dashboard's greeting: what was written
    today or yesterday, or when the last note was. `seed` rotates the wording:
    the same seed gives the same line, so a test with a fixed clock is exact.
    One sentence only (the owner, 2026-10-18: the hero's sub line must not run
    long). Every fact in it is traced like the rest of the voice."""
    views = _views(notes)
    dated = sorted((w for w in views if w.written), key=lambda w: (w.written, -w.rank), reverse=True)
    if not dated:
        return None
    v = _Voice({w.id: w for w in views}, today)
    _today_opening(v, dated, today, _draw(seed, "open", 6))
    return v.done("today")


def _today_opening(v: _Voice, dated: list, today: date, k: int) -> None:
    todays = [w for w in dated if w.written == today]
    yesterdays = [w for w in dated if (today - w.written).days == 1]
    if len(todays) > 1:
        v.t(("v_today_wrote", "v_today_wrote_b", "v_today_wrote_c", "v_today_wrote_d", "v_today_wrote_e", "v_today_wrote_f")[k])
        v.m(_count_word(len(todays)))
        #: An untitled note names itself "your note from today", which cannot
        #: follow "the latest": the count then ends the sentence on its own.
        if todays[0].titled:
            v.t(("v_today_notes", "v_today_notes_b", "v_today_notes_c", "v_today_notes_d", "v_today_notes_e", "v_today_notes_f")[k])
            v.name(todays[0])
        else:
            v.word(" notes")
        v.t("stop")
    elif todays:
        v.t(("v_today_one", "v_today_one_b", "v_today_one_c", "v_today_one_d", "v_today_one_e", "v_today_one_f")[k]).name(todays[0]).t("stop")
    elif yesterdays:
        v.t(("v_yesterday", "v_yesterday_b", "v_yesterday_c", "v_yesterday_d", "v_yesterday_e", "v_yesterday_f")[k]).name(yesterdays[0])
        if len(yesterdays) > 1:
            v.t("v_and_more").m(_count_word(len(yesterdays) - 1)).t("v_more")
        v.t("stop")
    else:
        v.t(("v_last_was", "v_last_was_b", "v_last_was_c", "v_last_was_d", "v_last_was_e", "v_last_was_f")[k]).name(dated[0])
        #: An untitled note is already named by its day ("your note from 16
        #: October"); saying "on 16 October" again read twice (owner screenshot).
        if dated[0].titled:
            v.t("on_day").m(v.day(dated[0].written))
        v.t("stop")


def week_review(notes: list[dict], *, today: date, unlinked: set[int] | None = None) -> dict:
    """The week in review, composed: how many notes and where they went, the
    sentence each standout note leads with, what is still open, and which of
    the week's notes are linked to nothing. Markdown, every clause traced."""
    views = _this_week(_views(notes), today)
    v = _Voice({w.id: w for w in views}, today)
    if not views:
        v.t("v_review_none")
        return v.done("week_review")
    oldest = min(w.written for w in views)
    if len(views) == 1:
        v.t("v_review_lead_one")
    else:
        v.t("v_review_lead").m(_count_word(len(views))).t("v_review_notes")
    v.t("v_review_span").m(v.day(oldest)).t("to_span").m(v.day(today)).t("stop")
    cats = Counter(str(w.note.get("category")) for w in views if w.note.get("category"))
    if len(views) > 2 and cats:
        top = cats.most_common(2)
        v.t("v_review_most")
        for i, (cat, n) in enumerate(top):
            if i:
                v.t("v_review_then")
            first = next(w for w in views if str(w.note.get("category")) == cat)
            v.t("bold").filed(cat, first.id).t("bold", "open_paren").m(_count_word(n)).t("close_paren")
        v.t("stop")
    # Standouts: the newest note of each category first, so the week's spread
    # shows, then the newest of the rest.
    ordered = sorted(views, key=lambda w: (w.written, -w.rank), reverse=True)
    picks: list[NoteView] = []
    seen_cats: set[str] = set()
    for w in ordered:
        cat = str(w.note.get("category") or "")
        if cat not in seen_cats and lead(w):
            seen_cats.add(cat)
            picks.append(w)
    for w in ordered:
        if w not in picks and lead(w):
            picks.append(w)
    picks = picks[:REVIEW_POINTS]
    if picks:
        v.t("para", "v_review_stand")
        for w in picks:
            v.t("line", "bullet").name(w).dated(w).t("colon").quoted(lead(w))
    open_items = [(w, s) for w in ordered for s in w.sentences if s.kind == "task" and not s.done][:REVIEW_OPEN]
    if open_items:
        v.t("para", "v_review_open")
        for w, s in open_items:
            v.t("line", "task_open").q(_clip(s), []).t("v_review_open_in").name(w)
    loose = [w for w in ordered if unlinked and w.id in unlinked][:4]
    if loose:
        v.t("para", "v_review_loose").names(loose).t("stop")
    return v.done("week_review")


# --- Find anything, titles, suggestions ----------------------------------------------


def asks(query: str) -> bool:
    """Whether a search box query is a question rather than words to find:
    it ends with a question mark, or opens the way a question does, and has
    something to be about."""
    text = (query or "").strip()
    if not text or ":" in text:
        return False
    if not (text.endswith("?") or _QUESTION.match(text)):
        return False
    return bool(composer.subject_terms(text))


def one_line(question: str, notes: list[dict], *, today: date, embed=None, voice: str = "natural") -> dict | None:  # noqa: ANN001
    """The composed answer's first line, for above Find anything's results:
    the line the composer writes to answer the question's shape on its own
    (`composer.compose`, measured 25 of 25 on its eval). None when the notes
    hold nothing to quote."""
    result = composer.compose(question, notes, today=today, embed=embed, voice=voice)
    if not result.get("grounding"):
        return None
    parts: list[tuple] = []
    for part in result["parts"]:
        if part[0] == "template" and part[1].startswith("\n"):
            break
        parts.append(part)
    if not any(p[0] in ("quote", "picture") for p in parts):
        # The first line opens a block ("has two of four checklist items
        # done:"): the one line is then the strongest quote, said whole.
        # A sentence of prose first: a checklist entry alone ("Beta invite
        # list") answers nothing.
        views = {v.id: v for v in _views(notes)}
        found = []
        for row in result["grounding"]:
            view = views.get(row["note_id"])
            unit = next((s for s in view.sentences if s.start == row["start"]), None) if view else None
            if unit is not None:
                wanted = composer._cue(result["shape"], unit.text) <= 0
                found.append((wanted, unit.kind != "prose" or len(unit.text.split()) < 5, len(found), view, unit))
        if not found:
            return None
        *_, view, unit = min(found, key=lambda f: f[:3])
        v = _Voice(views, today)
        v.t("says_a").name(view).t("says_a_end").quoted(unit)
        parts = v.parts
    # A quote set apart under a colon ends the line with its stop; one that
    # opens a block ("lists four:") keeps the colon and the block is below.
    text = "".join(p[1] for p in parts).rstrip()
    rows = [r for r in result["grounding"] if r["sentence"] in text]
    more = len({r["note_id"] for r in result["grounding"]}) > len({r["note_id"] for r in rows})
    if more:
        parts.append(("template", VOICE["v_more_below"]))
    text = "".join(p[1] for p in parts)
    return {
        "kind": "find",
        "text": text,
        "parts": parts,
        "grounding": rows,
        "sources": list(dict.fromkeys(r["note_id"] for r in rows)),
        "shape": result["shape"],
        "key": hashlib.sha1(text.encode()).hexdigest()[:12],
    }


def title_for(content: str) -> str:
    """A title from the note's own words, or "" when it has one already (a
    heading) or nothing to take one from: its first sentence, a lead-in
    ("Remember to", "Note to self:") off, cut at seven words on a word that
    carries meaning, the first letter raised. Never a word the note does not
    hold, in the order it holds them."""
    text = str(content or "").strip()
    if not text or text.lstrip().startswith("#"):
        return ""
    view = read_note({"id": 0, "content": text}, 0)
    first = None
    for s in view.sentences if view else []:
        if s.kind in ("prose", "item", "task") and len(s.text.split()) >= 2:
            first = s
            break
    if first is None:
        return ""
    words = _TITLE_LEAD.sub("", first.text.rstrip("…").rstrip(".!?")).split()
    words = words[:TITLE_WORDS]
    stop = query_understanding.STOPWORDS
    while words and (words[-1].lower().strip(",;:") in stop | TITLE_DANGLING or words[-1].endswith((",", ";", ":"))):
        words.pop()
    if len(words) < 2:
        return ""
    title = " ".join(words).strip(" ,;:-")
    return title[0].upper() + title[1:]


def suggested_searches(notes: list[dict], *, today: date, limit: int = 4) -> list[dict]:
    """Searches worth trying, from the notebook's recent notes: the latest on
    the newest titled note, a tag the week's notes share, what is open in a
    note with a checklist, when a recurring word came up. Each a fixed
    question around a note's name, a tag or a word the notes hold."""
    views = _views(notes)
    recent = sorted((w for w in views if w.written), key=lambda w: (w.written, -w.rank), reverse=True)
    out: list[dict] = []

    def add(v: _Voice, query: str) -> None:
        if len(out) < limit and all(r["query"] != query for r in out):
            out.append({**v.done("search"), "query": query})

    titled = [w for w in recent if str(w.note.get("content") or "").lstrip().startswith("#") and len(w.title.split()) <= 6]
    if titled:
        w = titled[0]
        v = _Voice({w.id: w}, today)
        v.t("next_latest_a").parts.append(("title", w.title, w.id))
        v.t("next_tag_b")
        add(v, v.text)
    tags: Counter = Counter()
    first_of: dict[str, int] = {}
    for w in recent[:30]:
        for tag in w.note.get("tags") or []:
            tags[str(tag)] += 1
            first_of.setdefault(str(tag), w.id)
    for tag, n in tags.most_common(2):
        if n < 2:
            break
        v = _Voice({w.id: w for w in recent}, today)
        v.t("next_tag_a").filed(tag, first_of[tag]).t("next_tag_b")
        add(v, v.text)
    for w in recent[:RECENT_DAYS]:
        if any(s.kind == "task" and not s.done for s in w.sentences) and len(w.title.split()) <= 6:
            v = _Voice({w.id: w}, today)
            v.t("v_search_open").parts.append(("title", w.title, w.id))
            v.t("next_tag_b")
            add(v, v.text)
            break
    return out
