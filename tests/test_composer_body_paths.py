"""`composer_body._opening` and `composer_body._others`, pinned before they
were split (cmpcc-1101).

Characterisation: each case calls the function on a fresh `_Answer` and keeps
the parts it wrote (kind and text, joined), compared with
`fixtures/composer/body_paths.json`, written by this code before the
refactor. The matrix reaches every branch: each shape's opener options, a
brief answer, a "when" with and without a date or a day written, a yes or no
that does and does not hold every word asked, a previous turn that opened
with an opener or with a bare quote, the lowered "Going by your notes,";
and for the other notes a picture alone, a newer note on the same thread
("Later, on", "And on", then none left), the same subject with and without
a lowered first word, another subject, and every joiner used up. A
difference here is a changed answer, never a test to update.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from tessellate.ai import composer_body
from tessellate.ai.composer_answer import _Answer
from tessellate.ai.composer_ask import _stem
from tessellate.ai.composer_read import read_note
from tessellate.ai.composer_select import _Meaning

TODAY = date(2026, 10, 6)
GOLDEN = Path(__file__).parent / "fixtures" / "composer" / "body_paths.json"


def _note(note_id: int, content: str, days_ago: int | None) -> dict:
    note = {"id": note_id, "content": content}
    if days_ago is not None:
        note["created_at"] = (TODAY - timedelta(days=days_ago)).isoformat()
    return note


NOTES = [
    _note(1, "# Harbor launch plan\n\nShip the mobile app to the public on the 14th of next month. The launch needs three gates closed first.\n\n- [x] Beta invite list\n- [ ] Store listing copy", 30),
    _note(2, "# Beta feedback\n\n41 testers active. The top complaint is the sign-up flow with nine fields. Harbor offline mode is hard to find.", 20),
    _note(3, "# Launch update\n\nThe launch of the mobile app moved to the 21st of next month. The gates are almost closed.", 5),
    _note(4, "# Launch retro\n\nThe mobile app launch went well on the day. It drew 300 sign-ups.", 2),
    _note(5, "# Dentist\n\nCheck-up booked for the 21st. Ask about the night guard.", 9),
    _note(6, "Garden shed roof leaks in the north corner. It is worst after heavy rain.", None),
    _note(7, "# Sketches\n\n![](/media/abc.png)\n\n[Pictures in this note, as this app read them:\n- bean.png: shows a blue bean drawn in pen; text in it: \"bean v2\"]", 3),
    _note(8, "# Launch party\n\nThe launch party for the mobile app is at the harbor bar. Sam books the room.", 1),
    _note(9, "# Lisbon\n\nAlfama has the walk-everywhere feel, but the hills are steep.", 25),
    _note(10, "# Launch budget\n\nThe launch of the mobile app costs 4,000 in ads. Spend is capped per week.", 4),
    _note(11, "# Launch moved again\n\nThe launch of the mobile app moved again, to the 28th of next month.", 1),
    _note(13, "# Cat\n\n![](/media/cat.png)\n\n[Pictures in this note, as this app read them:\n- cat.png: shows a cat asleep on the launch chair]", 2),
    _note(12, "# Launch final\n\nThe launch of the mobile app moved to the 28th of next month for good.", 0),
]
VIEWS = {v.id: v for v in (read_note(n, i) for i, n in enumerate(NOTES))}
QUESTIONS = ("What about the mobile app launch?", "is the launch date set", "tell me about the launch")
SHAPES = ("count", "when", "yesno", "explain", "where", "list", "status")
PREVIOUS = ("", "Going by your notes, the launch is set.", "The launch is set [**Harbor launch plan**].")


def _parts(out: _Answer) -> str:
    return "|".join(f"{p[0]}:{p[1]}" for p in out.parts) + ("|lower_next" if out.lower_next else "")


def _answer(subject: set[str], previous: str = "", brief: bool = False) -> _Answer:
    out = _Answer(VIEWS, TODAY)
    out.subject, out.previous, out.brief = subject, previous, brief
    return out


def opening_cases() -> list[tuple[str, str]]:
    rows = []
    subjects = ({_stem("launch")}, {_stem("launch"), _stem("zebra")})
    leads = [VIEWS[i].sentences[k] for i, k in ((1, 0), (2, 0), (3, 0), (4, 1), (5, 1), (6, 0), (2, 1))]
    for question in QUESTIONS:
        for shape in SHAPES:
            for s in leads:
                for subject in subjects:
                    for previous in PREVIOUS:
                        for brief in ((False, True) if shape in ("yesno", "explain") and not previous else (False,)):
                            out = _answer(subject, previous, brief)
                            composer_body._opening(out, s, shape, question)
                            rows.append((f"{question}/{shape}/{s.note_id}.{s.order}/{len(subject)}/{PREVIOUS.index(previous)}/{brief}", _parts(out)))
    return rows


def others_cases() -> list[tuple[str, str]]:
    rows = []
    subjects = (set(), {_stem("launch")}, {_stem("mobile"), _stem("app")})
    plans = (
        (1, [3, 4, 8, 10, 2]),
        (1, [7, 3, 9, 6, 4, 8, 10]),
        (2, [1, 3, 4, 8, 10, 5]),
        (3, [1, 4, 8]),
        (6, [5, 9, 7, 2]),
        (9, [7]),
        (2, [13, 9, 13]),
        (3, [4, 13]),
        (4, [1, 3]),
        (1, [3, 11, 12, 4]),
    )
    for question in (*QUESTIONS, "launch?", "what changed with the app", "any news on harbor"):
        for subject in subjects:
            for lead_id, rest_ids in plans:
                for cited in (False, True):
                    lead = VIEWS[lead_id].sentences[0]
                    rest = [s for i in rest_ids for s in VIEWS[i].sentences]
                    meaning = _Meaning([lead, *rest], None, subject)
                    out = _answer(subject)
                    if cited:
                        out.cited.add(lead.key)
                    composer_body._others(out, meaning, lead, rest, ["launch"], question)
                    rows.append((f"{question}/{sorted(subject)}/{lead_id}:{rest_ids}/{cited}", _parts(out)))
    lead, out = VIEWS[1].sentences[0], _answer(set())
    composer_body._others(out, _Meaning([lead], None), lead, [s for s in VIEWS[1].sentences if s.kind == "task"], [], "q")
    rows.append(("tasks only", _parts(out)))
    return rows


def cases() -> dict[str, list]:
    """Each case's output as an index into the outputs it shares: most cases
    write one of a few dozen openers, so the golden file stays small."""
    outputs: list[str] = []
    golden: dict[str, list] = {"outputs": outputs}
    for name, rows in (("opening", opening_cases()), ("others", others_cases())):
        golden[name] = []
        for _label, text in rows:
            if text not in outputs:
                outputs.append(text)
            golden[name].append(outputs.index(text))
    return golden


def test_opening_and_others_output_is_unchanged() -> None:
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    for name, rows in (("opening", opening_cases()), ("others", others_cases())):
        assert len(rows) == len(golden[name]), name
        for (label, got), want in zip(rows, golden[name]):
            assert got == golden["outputs"][want], f"{name} {label}"
