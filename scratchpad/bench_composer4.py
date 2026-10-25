"""300-note timing of the no-model readers (composer4).

Direct: `python scratchpad/bench_composer4.py questions.txt` calls
composer_extra.answer on 300 seeded notes, cold then warm.
Route: add `--url http://127.0.0.1:8817` to time POST /chat/stream against a
running app whose notebook holds the same notes (`--seed` creates them first).
"""
import datetime as dt
import sys
import time

sys.path.insert(0, "src")
from tessellate.ai import composer_extra  # noqa: E402
from tessellate.ai.composer_study import Ctx  # noqa: E402

NOW = dt.datetime(2026, 10, 21, 10, 0)
TOPICS = ["Operating systems", "Databases", "Networks", "Statistics", "Thermodynamics", "Roman history", "Organic chemistry", "Marketing", "Linear algebra", "Ethics"]


def note(i: int) -> str:
    t = TOPICS[i % len(TOPICS)]
    day = 1 + i % 28
    return (
        f"# {t} lecture {i}\n\nA **{t.split()[0].lower()} unit {i}** is a block that manages resources. **Term{i}**: the idea number {i} in {t}.\n\n"
        f"## Key points\n\n- Point one about {t} and revision {i}\n- Point two about exams and the lab\n- A final point on week {i % 12}\n\n"
        f"## Method\n\nThe method for {t} runs in steps. Each step depends on the one before it. Exam on {day} November. "
        f"Essay due Friday. Lab report on the {day}th of December. Meet the tutor tomorrow.\n\n- [ ] Read chapter {i % 9}\n"
    )


def ctx(q: str, notes: list[dict]) -> Ctx:
    rem = [{"id": i, "text": f"Reminder {i}", "due_at": NOW + dt.timedelta(days=i), "done": False, "entry_id": None, "priority": ""} for i in range(10)]
    return Ctx(question=q, notes=notes, now=NOW, history=[], seed="s", open_ids=[], asked=q, reminders=rem)


def main() -> None:
    qs = [line.strip() for line in open(sys.argv[1]) if line.strip()]
    notes = [{"id": i + 1, "content": note(i), "created_at": NOW - dt.timedelta(days=i % 60, hours=i % 24)} for i in range(300)]
    worst = []
    for q in qs:
        c = ctx(q, notes)
        t = time.perf_counter()
        r = composer_extra.answer(c)
        cold = (time.perf_counter() - t) * 1000
        t = time.perf_counter()
        composer_extra.answer(c)
        warm = (time.perf_counter() - t) * 1000
        worst.append(max(cold, warm))
        print(f"{cold:7.1f} cold {warm:7.1f} warm  {'HIT' if r else 'none'}  {q}")
    worst.sort()
    print("p95", round(worst[max(0, int(len(worst) * 0.95) - 1)], 1), "max", round(worst[-1], 1))


main()
