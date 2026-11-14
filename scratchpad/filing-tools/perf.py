"""L535: `lexical_filing.decide` per call at 5,000 notes.

Run: copy into tests/ (it needs the `session` fixture), `pytest <copy> -s`, delete the copy.
Measured 2026-11-13: 6.8 ms a call.
"""

from __future__ import annotations

import json
import random
import time

from tessellate.ai import lexical_filing
from tessellate.core.database import Category, Entry

WORDS = {
    "Fitness": "squats deadlift gym run cardio protein reps bench stretch marathon".split(),
    "Cooking": "lentils recipe oven garlic simmer pasta bake curry onion basil".split(),
    "Work": "meeting deadline client report invoice quarterly roadmap slides budget hire".split(),
    "Travel": "flight hotel passport itinerary train beach museum visa luggage map".split(),
    "Money": "savings pension mortgage tax isa shares rent bills interest loan".split(),
}
FILL = "the a today then note remember also with about and later good new".split()


def test_decide_at_5000_notes(session):
    rnd = random.Random(1)
    cats = {}
    for name in WORDS:
        category = Category(name=name)
        session.add(category)
        session.flush()
        cats[name] = category.id
    rows = []
    for _ in range(5000):
        name = rnd.choice(list(WORDS))
        pool = WORDS[name]
        text = " ".join(rnd.choice(pool if rnd.random() < 0.4 else FILL) for _ in range(rnd.randint(8, 40)))
        rows.append({"content": text, "category_id": cats[name], "tags": json.dumps([name.lower()])})
    session.execute(Entry.__table__.insert(), rows)
    session.commit()
    question = "booked a flight and hotel for the marathon, need passport"
    lexical_filing.decide(session, question)
    started = time.perf_counter()
    for _ in range(20):
        lexical_filing.decide(session, question)
    print("\nper call ms", (time.perf_counter() - started) / 20 * 1000)
