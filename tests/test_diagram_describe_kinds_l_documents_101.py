"""Describe it (no model) for Gantt, pie, state, class and ER (L-documents-101).

The composer's rule path (`composer_mermaid`) made only a flowchart, a timeline and a mind map; for the five newer kinds
`want` was empty, so a person on a pie chart got a flowchart of their words. Each case here is drawn by rule and then
read back by the kind's own parser in node, so what is written is what the builder opens.
"""

from __future__ import annotations

from datetime import date

import pytest

from tessellate.ai import composer_mermaid as cm
from tests.test_diagram_ask_charts_l_documents_86 import _node

TODAY = date(2026, 3, 2)  # a fixed clock: the Gantt's start when the words give none

CASES = {
    "gantt": ("Launch plan\n1. Write the copy (3 days)\n2. Design the page (1 week)\n3. Publish", "gantt chart"),
    "pie": ("Where the budget goes\n- Rent: 1200\n- Food: 400\n- Fun - 150", "pie chart"),
    "state": ("1. Draft\n2. In review\n3. Approved\n4. Published", "state diagram"),
    "class": ("# Order\n- id: int\n- total: float\n# Customer\n- name: string\n- email", "class diagram"),
    "er": ("# Order\n- id\n- placed date\n# Customer\n- name\n- email\nCustomer has many Order", "er diagram"),
}


def test_each_kind_is_named_by_the_words():
    for kind, (_text, phrase) in CASES.items():
        assert cm.wanted(f"make a {phrase} of this") == kind, kind
    assert cm.wanted("a Gantt of the plan") == "gantt" and cm.wanted("a pie of my spending") == "pie"
    assert cm.wanted("an ER diagram") == "er" and cm.wanted("a UML class diagram") == "class"
    assert cm.wanted("a state machine") == "state"
    assert cm.wanted("make a flowchart") == "flowchart" and cm.wanted("make a diagram") == ""


@pytest.mark.parametrize("kind", list(CASES))
def test_the_rule_path_draws_the_kind_and_the_builder_reads_it_back(kind):
    text, phrase = CASES[kind]
    made = cm.diagram(text, want=cm.wanted(phrase), today=TODAY)
    assert made is not None and made.shape == kind, (kind, made)
    assert "no model" in made.note
    back = _node(kind, made.source, "return { again: A.print(m), n: dakFlatten(A, ko, m).length };")
    assert back["n"] >= 2, (kind, made.source)
    assert back["again"].strip() == made.source.strip(), (kind, made.source, back["again"])


def test_the_drawings_say_what_the_words_said():
    gantt = cm.diagram(CASES["gantt"][0], want="gantt", today=TODAY).source
    assert "dateFormat YYYY-MM-DD" in gantt and "title Launch plan" in gantt
    assert "Write the copy :t1, 2026-03-02, 3d" in gantt and "Design the page :t2, after t1, 7d" in gantt and "Publish :t3, after t2, 1d" in gantt
    pie = cm.diagram(CASES["pie"][0], want="pie").source
    assert '"Rent" : 1200' in pie and '"Fun" : 150' in pie and "title Where the budget goes" in pie
    state = cm.diagram(CASES["state"][0], want="state").source
    assert "[*] --> s1" in state and "s3 --> s4" in state and 's1 : Draft' not in state and 'state "In review" as s2' in state
    klass = cm.diagram(CASES["class"][0], want="class").source
    assert "class Order {" in klass and "+id: int" in klass and "+email" in klass and "class Customer {" in klass
    er = cm.diagram(CASES["er"][0], want="er").source
    assert "CUSTOMER {" in er and "date placed" in er and "CUSTOMER ||--o{ ORDER : has" in er


def test_words_without_the_shape_fall_back_and_say_why():
    made = cm.diagram("just a sentence about nothing in particular. and another one.", want="pie", today=TODAY)
    assert made is None or made.shape != "pie"
    flow = cm.diagram("1. Write\n2. Review\n3. Ship", want="pie", today=TODAY)
    assert flow.shape == "flowchart" and "no numbers to draw a pie chart from" in flow.note


def test_the_pane_sends_the_kind_it_is_in():
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "frontend/js/diagram-kinds-more.js").read_text(encoding="utf-8")
    for want in ("gantt chart", "pie chart", "state diagram", "class diagram", "er diagram"):
        assert f'want: "{want}"' in src, want
    assert 'want: ""' not in src
