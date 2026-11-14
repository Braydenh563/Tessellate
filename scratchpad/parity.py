"""The parity scorecard's engine columns (CHAT_PLAN decision 58), the ones
measurable with no model: variety (decision 51's floor), structure (the
maxims lint, decision 52), grounding (every eval clause traced) and acts
(each with an inverse, decision 53). Brief 68 prints decision 58's six
columns (understanding, grounding, structure, variety, follow-on, repair),
the engine's number beside a model's: the model column reads "not run" when
no `TESSELLATE_EVALS_URL` model is set (CLAUDE.md section 4).

    PYTHONPATH=src:. python scratchpad/parity.py
"""
from tessellate.ai import realise, validate
from tests import _composer_eval as E
from tests.test_realise import FLOOR_QUESTIONS, HELP_QUESTIONS, _chat


def variety() -> dict:
    out = {}
    for voice in ("natural", "professional"):
        seen = [realise.variety(_chat(q, voice)) for q in FLOOR_QUESTIONS]
        out[voice] = (min(s["openers"] for s in seen), max(s["facts"] for s in seen))
    helped = [realise.variety(_chat(q, "help")) for q in HELP_QUESTIONS]
    out["help"] = (min(s["wordings"] for s in helped), max(s["facts"] for s in helped))
    return out


def structure() -> tuple[int, int, int]:
    data = E.load()
    notes = data["notes"] + E.untitled_notes(E.load_voice(), E.today(data))
    rows = E.run() + E.run_voice()
    found = sum(len(validate.maxims(r["result"], r["question"], notes) + validate.computed_rule(r["result"], r["question"])) for r in rows)
    grounded = sum(1 for r in rows if r["grounded"] >= 1.0)
    return len(rows), found, grounded


def acts() -> tuple[int, int]:
    from tessellate.ai import acts as registry

    writes = [a for a in registry.ACTS.values() if a.writes]
    return sum(1 for a in writes if a.inverse), len(writes)


def understanding() -> tuple[int, int]:
    """Act and slot reading on the owner's corpus: the act set (each act read
    as an act, each lookalike as none), the reading set (intent and band) and
    the board and filter sets Brief 68 wrote."""
    import json
    from datetime import datetime
    from pathlib import Path

    from tessellate.ai import acts as registry, filters, reading

    root = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "composer"
    right = total = 0
    act_set = json.loads((root / "acts_1010.json").read_text(encoding="utf-8"))
    now = datetime.fromisoformat(act_set["now"])
    for row in act_set["acts"]:
        total += 1
        right += registry.parse(row["phrase"], now) is not None
    for row in act_set["lookalikes"]:
        total += 1
        phrase = row["phrase"] if isinstance(row, dict) else row
        right += registry.parse(phrase, now) is None
    read_set = json.loads((root / "reading_1010.json").read_text(encoding="utf-8"))
    clock = datetime.fromisoformat(read_set["now"])
    for row in read_set["rows"]:
        total += 1
        got = reading.read(row["text"], now=clock, context=row.get("context") or {})
        right += got.intent == row["intent"] and got.band == row["band"]
    for row in json.loads((root / "board_acts_1010.json").read_text(encoding="utf-8"))["rows"]:
        total += 1
        got = registry.board_parse(row["text"])
        right += ((got["intent"], got["slots"]) if got else (None, {})) == (row["intent"], row["slots"])
    phrases = json.loads((root / "filters_1010.json").read_text(encoding="utf-8"))
    fnow = datetime.fromisoformat(phrases["now"])

    def key(items):
        return sorted(json.dumps({k: v for k, v in f.items() if k != "said"}, sort_keys=True) for f in items)

    for row in phrases["rows"]:
        total += 1
        right += key(filters.read(row["text"], fnow)["filters"]) == key(row["filters"])
    return right, total


def grounding_caught() -> tuple[int, int]:
    """A model answer's unsourced numbers caught (`unsourced_1010.json`)."""
    import json
    from pathlib import Path

    data = json.loads((Path(__file__).resolve().parents[1] / "tests/fixtures/composer/unsourced_1010.json").read_text(encoding="utf-8"))
    caught = total = 0
    for row in data["rows"]:
        got = validate.check_model_answer(row["answer"], [data["sources"][k] for k in row["sources"]])["unbacked"]
        for want in row["unsourced"]:
            total += 1
            caught += want in got
    return caught, total


def repair_rate() -> tuple[int, int]:
    """Of the readings not sure enough to act on, how many take one step of
    the ladder with at most one question."""
    import json
    from datetime import datetime
    from pathlib import Path

    from tessellate.ai import reading

    data = json.loads((Path(__file__).resolve().parents[1] / "tests/fixtures/composer/reading_1010.json").read_text(encoding="utf-8"))
    clock = datetime.fromisoformat(data["now"])
    one = total = 0
    for row in data["rows"]:
        got = reading.read(row["text"], now=clock, context=row.get("context") or {})
        if got.band in ("sure", "likely"):
            continue
        total += 1
        step = reading.repair(got)
        one += step is not None and (step.line or "").count("?") <= 1
    return one, total


def follow_up() -> tuple[int, int]:
    """Decision 58's context column: the 200 spoken lines resolved over the
    last five turns (`tests/fixtures/composer/spoken_1010.json`)."""
    from tests.test_spoken_followups import DATA, right

    return sum(1 for row in DATA["rows"] if right(row)), len(DATA["rows"])


def scorecard() -> None:
    """Decision 58's six columns, the engine's number beside a model's."""
    import os

    model = "run pytest -m evals" if os.environ.get("TESSELLATE_EVALS_URL") else "not run (no model)"
    u, ut = understanding()
    g, gt = grounding_caught()
    n, found, grounded = structure()
    low = min(v[0] for v in variety().values())
    r, rt = repair_rate()
    f, ft = follow_up()
    rows = [
        ("understanding", f"{u} of {ut} ({u / ut:.2f})"),
        ("grounding", f"{g} of {gt} unsourced caught; {grounded} of {n} traced"),
        ("structure", f"{found} maxims findings over {n} answers"),
        ("variety", f"min {low} distinct openers of {realise.VARIETY_TURNS} (floor {realise.VARIETY_FLOOR}, target 8, was 3)"),
        ("follow-up", f"{f} of {ft} spoken lines resolved over five turns"),
        ("repair", f"{r} of {rt} unsure or none readings take one step"),
    ]
    print("\nscorecard (decision 58)")
    for name, engine in rows:
        print(f"  {name:14} {engine:60} model: {model}")



if __name__ == "__main__":
    for voice, (low, facts) in variety().items():
        print(f"variety  {voice:12} min distinct of {realise.VARIETY_TURNS}: {low} (floor {realise.VARIETY_FLOOR}); fact sets per question: {facts}")
    n, found, grounded = structure()
    print(f"maxims   {found} findings over {n} eval answers; grounded 1.0: {grounded} of {n}")
    try:
        have, total = acts()
        print(f"acts     {have} of {total} write acts have an inverse")
    except ImportError:
        print("acts     no registry yet")
    scorecard()
