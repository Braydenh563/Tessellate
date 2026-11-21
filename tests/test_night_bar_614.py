"""L614: the night pass is one bar. Each phase (reading, comparing claims, matching questions) fills its
own share, so the bar never runs back to the start between phases."""

from __future__ import annotations

from tessellate.core import jobruns


def test_a_run_in_phases_reads_as_one_bar_that_never_runs_back():
    run = jobruns.Run("night-shift", None)
    seen = []
    for (start, end), total in (((0.0, 0.7), 10), ((0.7, 0.9), 4), ((0.9, 1.0), 2)):
        run.within(start, end)
        for done in range(total + 1):
            run.step(done, total, "phase")
            seen.append(run.snapshot()["progress"])
    assert seen == sorted(seen)
    assert seen[0] == 0.0 and abs(seen[-1] - 1.0) < 1e-9
    assert run.snapshot()["detail"] == "phase: 2 of 2"


def test_a_plain_run_still_counts_from_nothing_to_all():
    run = jobruns.Run("embeddings", None)
    run.step(1, 4)
    assert run.snapshot()["progress"] == 0.25


def test_the_night_pass_gives_each_phase_its_share():
    import inspect

    from tessellate.ai import facts

    source = inspect.getsource(facts)
    for span in ("within(0.0, 0.7)", "within(0.7, 0.9)", "within(0.9, 1.0)"):
        assert span in source


def test_nearest_by_words_keeps_the_old_order_score_then_id():
    """L614 (pairing speed): the numpy scoring returns what the per-candidate loop did."""
    import random
    from types import SimpleNamespace

    from tessellate.ai import facts

    rnd = random.Random(4)
    words = "boiler rent passport gym dentist laptop bike flat pension service renewal checked costs".split()
    pool = [
        SimpleNamespace(id=i + 1, entry_id=i % 40, text=" ".join(rnd.sample(words, rnd.randint(2, 6))))
        for i in range(300)
    ]
    similar = facts._Similar(None, pool)  # noqa: SLF001

    def reference(text, allowed, k):
        terms = facts._terms(text)  # noqa: SLF001
        scored = []
        for row in pool:
            other = facts._terms(row.text)  # noqa: SLF001
            count = len(terms & other)
            union = len(terms | other)
            score = count / union if union else 0.0
            if count and score >= similar.PREFILTER and allowed(row):
                scored.append((score, row))
        scored.sort(key=lambda pair: (-pair[0], pair[1].id))
        seen, out = {" ".join(text.lower().split())}, []
        for score, row in scored:
            wording = " ".join(row.text.lower().split())
            if wording not in seen:
                seen.add(wording)
                out.append((score, row))
        return [pair for pair in out if pair[0] >= facts.PAIR_WORDS][:k]

    for row in pool[:60]:
        allowed = lambda other, row=row: other.entry_id != row.entry_id  # noqa: E731
        got = [(round(score, 9), other.id) for score, other in similar.nearest(row.text, allowed)]
        want = [(round(score, 9), other.id) for score, other in reference(row.text, allowed, facts.PAIR_NEIGHBOURS)]
        assert got == want, row.text
