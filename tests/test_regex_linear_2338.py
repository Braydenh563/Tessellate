"""CodeQL alerts 2338 and 2339: two act patterns ran slow on long repeats; both now grow in step with the input."""

from __future__ import annotations

import time

from tessellate.ai import commands, library_acts


def _ratio(pattern, make) -> float:
    def took(n: int) -> float:
        text = make(n)
        start = time.process_time()
        for _ in range(5):
            pattern(text)
        return time.process_time() - start

    took(500)
    return took(16_000) / max(took(2_000), 1e-6)


def test_a_before_tail_reads_a_long_run_of_tabs_in_linear_time():
    assert _ratio(commands._BEFORE_TAIL.search, lambda n: "dentist" + "\t" * n + "x") < 30


def test_an_old_lead_reads_a_long_run_of_all_my_in_linear_time():
    assert _ratio(library_acts._OLD.match, lambda n: "all my " * n + "x") < 30


def test_the_patterns_still_read_what_they_read():
    assert commands._BEFORE_TAIL.search("about the dentist the day before")
    for lead in ("all my old ", "all of the old ", "the oldest ", "every stale "):
        assert library_acts._OLD.match(lead + "notes"), lead


def test_study_patterns_and_the_range_read_long_runs_in_linear_time():
    from tessellate.ai import fact_check, study

    assert _ratio(study.clean, lambda n: "[[\\" * n) < 30
    assert _ratio(study._HEADING.match, lambda n: "#" + "\t" * n) < 30
    assert _ratio(study.cards, lambda n: "Q." + "\t" * n) < 30
    assert _ratio(fact_check._RANGE.match, lambda n: "0" * n + "x") < 30


def test_study_still_reads_headings_links_and_pairs():
    from tessellate.ai import study

    assert study._heading_text(study._HEADING.match("## Plan ##")) == "Plan"
    assert study.clean("see [[Trip|the trip]] and [docs](http://x)") == "see the trip and docs"
    assert [c.q for c in study.cards("Q: What is it?\nA: A test.")] == ["What is it?"]


def test_the_two_study_alerts_of_bb908aa8_read_50k_characters_in_linear_time():
    """CodeQL on bb908aa8: a heading of repeated tab and no-break space (study.py:190) and a pair
    opening "Q.!" then a run of "**" (study.py:400). Both run on 50,000 characters and grow in step."""
    from tessellate.ai import study

    heading = lambda n: "#" + "\t\xa0" * n + "x"  # noqa: E731
    pair = lambda n: "Q.!" + "**" * n  # noqa: E731
    for make, read in ((heading, study.title_of), (heading, study._HEADING.match), (pair, study.cards), (pair, study._QA.search)):
        start = time.process_time()
        read(make(25_000))
        assert time.process_time() - start < 0.5, read
        assert _ratio(read, make) < 30, read
