"""L-chat-252 (Brief 97 decision a): the chart maker draws area, pie, scatter, histogram and table past bar and
line, and the composer's chart answer names the kind the question asked for instead of saying a pie is bars."""

from __future__ import annotations

import pytest

from tessellate.ai import composer_graph
from tests.test_chart_maker_l171 import _maker, node

KINDS = ("bar", "line", "area", "pie", "scatter", "histogram", "table")
ROWS = [("Mon", 3), ("Tue", 5), ("Wed", 4)]


@node
@pytest.mark.parametrize("kind", KINDS)
def test_the_maker_reads_every_kind_and_the_block_round_trips(kind):
    chart = _maker("parse", f"title: T\nkind: {kind}\nMon, 3\nTue, 5\nWed, 4")
    assert chart["kind"] == kind
    fence = _maker("fence", chart)
    assert _maker("parse", "\n".join(fence.splitlines()[1:-1])) == chart


@node
def test_an_unknown_kind_is_a_bar():
    assert _maker("parse", "kind: radar\nMon, 3")["kind"] == "bar"


@pytest.mark.parametrize(
    ("question", "kind"),
    [("chart this as a pie", "pie"), ("make an area chart of this", "area"), ("scatter plot this", "scatter"), ("a histogram of these", "histogram"),
     ("show this as a table chart", "table"), ("chart this trend", "line"), ("chart this", "bar")],
)
def test_the_composer_names_the_kind_the_question_asked_for(question, kind):
    text = composer_graph._chart_answer(ROWS, "Days", question)["text"]
    assert f"kind: {kind}" in text and f"as a {kind} chart" in text
    assert "not drawn here" not in text
