"""The app's voice eval (CHAT_PLAN, "the composer everywhere"): every surface
the composer speaks on outside an answer, over the showcase notebook.

Not a test module: `tests/test_composer_voice.py` holds the gates and
`PYTHONPATH=src python -m tests._voice_eval` prints the table the report
quotes. The notebook is the one `_composer_eval` reads
(`fixtures/composer/showcase_725.json`), so the numbers sit beside 725's.

The measures, each a number:

- **grounded**: the share of a remark's factual parts that trace back to the
  notes, the reminders or a measured value. The rule says 1.0.
- **distinct in 20**: the companion over twenty days, keeping what it has
  said (as the page does): how many of its twenty remarks are new words. The
  ask was "never twice the same", so 20 of 20.
- **openings**: how many different first three words those twenty start with.
- **words**: mean words a remark, the bubble being read at a glance.
"""

from __future__ import annotations

import ast
import re
from datetime import date, timedelta

from tessellate.ai import composer, composer_voice
from tessellate.ai import composer_answer
from tests import _composer_eval

EM_DASH = chr(0x2014)

REMINDERS = [
    {"id": 1, "text": "Ring the landlord about the boiler", "due_at": "2026-10-06T15:00", "done": False, "entry_id": None},
    {"id": 2, "text": "Send the launch email", "due_at": "2026-10-05T09:00", "done": False, "entry_id": "1"},
]


def load() -> dict:
    data = _composer_eval.load()
    for note in data["notes"]:
        tags = note.get("tags")
        if isinstance(tags, str):
            try:
                note["tags"] = ast.literal_eval(tags)
            except (ValueError, SyntaxError):
                note["tags"] = []
    return data


def notes_until(data: dict, day: date) -> list[dict]:
    """The notebook as it stood on `day`: nothing written after it."""
    return [n for n in data["notes"] if str(n["created_at"])[:10] <= day.isoformat()]


def measured(notes: list[dict], on: date) -> set[str]:
    values: set[str] = set()
    for n in range(len(notes) + 2):
        word = composer_answer._count_word(n)
        values |= {str(n), word, word.capitalize()}
    answer = composer._Answer({}, on)
    for note in notes:
        day = date.fromisoformat(str(note["created_at"])[:10])
        values |= {answer.day(day), str(day.year)}
    for r in REMINDERS:
        values.add(answer.day(date.fromisoformat(r["due_at"][:10])))
    values.add(answer.day(on))
    return values


def _in_note(text: str, content: str) -> bool:
    return _composer_eval._in_note(text, content)


def trace(remark: dict, notes: list[dict], on: date, *, answer_phrases: bool = False) -> list[str]:
    """Every part of a remark that is not what it says it is."""
    by_id = {note["id"]: note for note in notes}
    templates = set(composer_voice.VOICE.values())
    if answer_phrases:
        templates |= set(composer.PHRASES.values())
    values = measured(notes, on)
    failures: list[str] = []
    parts = remark["parts"]
    if "".join(p[1] for p in parts) != remark["text"]:
        failures.append("the parts are not the whole text")
    named = [p[2] for p in parts if p[0] == "title"]
    for part in parts:
        kind, text = part[0], part[1]
        if kind == "template":
            if text not in templates:
                failures.append(f"not a fixed phrase: {text!r}")
        elif kind in ("quote", "picture"):
            if not _in_note(text, by_id[part[2]]["content"]):
                failures.append(f"quote not in note {part[2]}: {text!r}")
        elif kind == "title":
            view = composer.read_note(by_id[part[2]], 0)
            #: A title-less note is named by its first line cut at about six words (owner 2026-11-10), in quotes.
            from tessellate.ai import composer_frame

            said = view.title if view and getattr(view, "titled", True) else composer_frame.name_of(by_id[part[2]])
            if not view or said != text:
                failures.append(f"not note {part[2]}'s name: {text!r}")
        elif kind == "filed":
            note = by_id[part[2]]
            filed = [str(t) for t in note.get("tags") or []] + [str(note.get("category") or "")]
            if text not in filed:
                failures.append(f"not filed under: {text!r}")
        elif kind == "word":
            for nid in named:
                if not re.search(rf"\b{re.escape(text)}\b", by_id[nid]["content"], re.I):
                    failures.append(f"note {nid} does not hold {text!r}")
        elif kind == "address":
            #: A link around a note's name: "[" and "](#/notes/<a note found>)".
            linked = re.fullmatch(r"\]\(#/notes/(\d+)\)", text)
            if text != "[" and not (linked and int(linked.group(1)) in by_id):
                failures.append(f"not a link to a note found: {text!r}")
        elif kind == "reminder":
            if text not in [r["text"] for r in REMINDERS]:
                failures.append(f"not a reminder's words: {text!r}")
        elif kind == "measure":
            if text not in values:
                failures.append(f"not a measured value: {text!r}")
        elif kind in ("asked", "reading"):
            pass  # the question's own words, or how it was read; held by the find eval's caller
        elif kind == "shifted":
            problem = _composer_eval.shifted_failure(part, by_id[part[2]]["content"], date.today())
            if problem:
                failures.append(problem)
        else:
            failures.append(f"unknown part kind {kind!r}")
    if EM_DASH in remark["text"] or "!" in remark["text"]:
        failures.append("an em-dash or an exclamation mark")
    return failures


def _factual(remark: dict) -> int:
    return sum(1 for p in remark["parts"] if p[0] != "template")


def _words(text: str) -> int:
    return len(re.sub(r"\*\*", "", text).split())


def companion_draws(data: dict, days: int = 20) -> list[dict]:
    """Twenty days of the companion, one remark a day, never one it said."""
    end = date.fromisoformat(data["today"])
    said: set[str] = set()
    picked: list[dict] = []
    for back in range(days - 1, -1, -1):
        day = end - timedelta(days=back)
        notes = notes_until(data, day)
        # The resurfaced pick: the three oldest notes not yet a month old
        # are what the fading score favours; stand-in, measured the same.
        olds = sorted((n for n in notes if (day - date.fromisoformat(n["created_at"][:10])).days > 10),
                      key=lambda n: (n["created_at"], str(n["id"])))
        resurfaced = [n["id"] for n in olds[(back * 3) % max(1, len(olds)):][:3]]
        options = composer_voice.remarks(notes, today=day, reminders=REMINDERS if back == 0 else [], resurfaced=resurfaced)
        fresh = next((r for r in options if r["key"] not in said), None)
        if fresh:
            said.add(fresh["key"])
            picked.append({**fresh, "day": day, "notes": notes})
    return picked


def run(data: dict | None = None) -> dict:
    data = data or load()
    today = date.fromisoformat(data["today"])
    notes = data["notes"]
    rows: dict[str, list[tuple[dict, list[dict], date, bool]]] = {
        "companion": [], "today": [], "week": [], "find": [], "searches": [],
    }
    draws = companion_draws(data)
    rows["companion"] = [(r, r["notes"], r["day"], False) for r in draws]
    for back in range(7):
        day = today - timedelta(days=back)
        line = composer_voice.today_line(notes_until(data, day), today=day)
        if line:
            rows["today"].append((line, notes_until(data, day), day, False))
        rows["week"].append((composer_voice.week_review(notes_until(data, day), today=day, unlinked={"77", "76"}), notes_until(data, day), day, False))
    for entry in data["questions"]:
        q = entry["question"]
        given = _composer_eval.notes_for(entry, data)
        line = composer_voice.one_line(q, given, today=today)
        if line:
            rows["find"].append((line, given, today, True))
    for s in composer_voice.suggested_searches(notes, today=today):
        rows["searches"].append((s, notes, today, True))
    table: dict[str, dict] = {}
    for surface, items in rows.items():
        factual = sum(_factual(r) for r, *_ in items)
        failures = [f for r, n, d, phrases in items for f in trace(r, n, d, answer_phrases=phrases)]
        texts = [r["text"] for r, *_ in items]
        table[surface] = {
            "count": len(items),
            "grounded": round(1 - len(failures) / factual, 3) if factual else 1.0,
            "failures": failures[:5],
            "distinct": len(set(texts)),
            "openings": len({" ".join(re.sub(r"\*\*", "", t).split()[:3]) for t in texts}),
            "words": round(sum(_words(t) for t in texts) / len(texts), 1) if texts else 0.0,
        }
    titles = [(n, composer_voice.title_for(n["content"].split("\n", 1)[-1].strip())) for n in notes]
    made = [(n, t) for n, t in titles if t]
    table["titles"] = {
        "count": len(made),
        "grounded": round(sum(1 for n, t in made if t[1:] in n["content"]) / len(made), 3) if made else 1.0,
        "words": round(sum(len(t.split()) for _, t in made) / len(made), 1) if made else 0.0,
    }
    finds = [entry for entry in data["questions"]]
    table["find"]["questions"] = len(finds)
    return table


if __name__ == "__main__":
    for surface, row in run().items():
        print(surface, {k: v for k, v in row.items() if k != "failures"}, row.get("failures") or "")
