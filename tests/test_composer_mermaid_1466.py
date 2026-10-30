"""A Mermaid diagram from text or notes, by rule (INBOX 1466).

The owner: "can it be used to generate mermaid diagrams??". Each shape is
tested on several ways of writing it, and every output is read back by
shape: the header, safe ids, quoted labels with no raw quote inside, one
edge less than boxes for a flowchart, a date and a `:` per timeline line,
and a mind map's indentation under one root. Whether the vendored Mermaid
itself parses them is measured in the running app (the agent's sweep).
"""

from __future__ import annotations

import re
from datetime import date

import pytest

from tessellate.ai import composer_mermaid as cm

_BOX = re.compile(r'^(n\d+)\["([^"]*)"\]$')


def _flow(source: str) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    lines = [line.strip() for line in source.splitlines()]
    assert lines[0] == "flowchart TD"
    boxes, edges = [], []
    for line in lines[1:]:
        box = _BOX.match(line)
        edge = re.match(r"^(n\d+) --> (n\d+)$", line)
        assert box or edge, line
        if box:
            boxes.append(box.groups())
        else:
            edges.append(edge.groups())
    ids = [b[0] for b in boxes]
    assert len(ids) == len(set(ids))
    assert len(edges) == len(boxes) - 1
    assert all(a in ids and b in ids for a, b in edges)
    return boxes, edges


def _timeline(source: str) -> list[tuple[str, list[str]]]:
    lines = source.splitlines()
    assert lines[0] == "timeline"
    rows = []
    for line in lines[1:]:
        if line.strip().startswith("title "):
            assert ":" not in line
            continue
        when, *what = [part.strip() for part in line.strip().split(" : ")]
        assert when and what and all(what) and ";" not in line and "#" not in line, line
        rows.append((when, what))
    return rows


def _mindmap(source: str) -> list[tuple[int, str]]:
    lines = source.splitlines()
    assert lines[0] == "mindmap"
    assert re.match(r'^  root\(\("[^"]*"\)\)$', lines[1]), lines[1]
    out = []
    for line in lines[2:]:
        indent = len(line) - len(line.lstrip(" "))
        assert indent >= 4 and indent % 2 == 0, line
        assert _BOX.match(line.strip()), line
        out.append((indent // 2 - 1, _BOX.match(line.strip()).group(2)))
    return out


@pytest.mark.parametrize(
    ("text", "first", "count"),
    [
        ("1. Wake up\n2. Brew coffee\n3. Read the news\n4. Go to work", "Wake up", 4),
        ("First boil the water, then add the pasta, then drain it and finally add the sauce.", "Boil the water", 4),
        ("- First call the bank\n- Then cancel the card\n- Finally order a new one", "Call the bank", 3),
        ("To renew: 1) fill the form\n1) fill the form\n2) post it\n3) wait two weeks", "Fill the form", 3),
        ("Unplug the router. Then wait thirty seconds. Then plug it back in. Next check the lights.", "Unplug the router", 4),
    ],
)
def test_steps_are_a_flowchart(text, first, count):
    made = cm.diagram(text, want="")
    assert made.shape == "flowchart"
    boxes, _edges = _flow(made.source)
    assert len(boxes) == count and boxes[0][1] == first


@pytest.mark.parametrize(
    ("text", "order"),
    [
        ("- 2 April 2026: tomatoes in\n- 2026-03-01 seeds sown\n- May 2026 first harvest", ["2026-03-01", "2 April 2026", "May 2026"]),
        ("We moved in on 3 June 2024. The boiler broke on 12 January 2025. We sold the flat in March 2026.", ["3 June 2024", "12 January 2025", "March 2026"]),
        ("- Jan 5, 2026 kickoff\n- Feb 20, 2026 design done\n- April 1st, 2026 launch", ["Jan 5, 2026", "Feb 20, 2026", "April 1st, 2026"]),
        ("2019: started the job\n2021: promoted\n2023: moved teams", ["2019", "2021", "2023"]),
    ],
)
def test_dated_lines_are_a_timeline_oldest_first(text, order):
    made = cm.diagram(text, want="timeline")
    assert made.shape == "timeline"
    rows = _timeline(made.source)
    assert [when for when, _what in rows] == order
    # The date is not said twice: it left the event's words.
    assert all(when not in " ".join(what) for when, what in rows)


@pytest.mark.parametrize(
    ("text", "root", "depths"),
    [
        ("# Garden\n- Tomatoes\n  - need sun\n- Beans\n- Herbs", "Garden", [1, 2, 1, 1]),
        ("## Trip ideas\n* Lisbon\n* Porto\n    * by train\n", "Trip ideas", [1, 1, 2]),
        ("Reasons to move. The rent is lower. The commute is shorter. The school is closer.", "Reasons to move.", [1, 1, 1]),
        ("# Project\n## Design\n## Build\n- tests first", "Project", [1, 1, 1]),
    ],
)
def test_a_heading_with_points_is_a_mind_map(text, root, depths):
    made = cm.diagram(text, want="mindmap")
    assert made.shape == "mindmap"
    assert f'root(("{root}"))' in made.source
    assert [d for d, _w in _mindmap(made.source)] == depths


@pytest.mark.parametrize(
    "awkward",
    ['Say "hello" [loudly]', "Room #3; floor <2>", "a `code` bit (with parens) {and braces}", "Key: value: more", "C:\\path\\to"],
)
def test_labels_are_escaped_for_mermaid(awkward):
    flow = cm.diagram(f"1. {awkward}\n2. then {awkward}", want="flowchart")
    boxes, _ = _flow(flow.source)
    for _id, words in boxes:
        assert '"' not in words and "`" not in words and "<" not in words
        assert not re.search(r"#(?!35;|quot;|lt;|gt;)", words)
    mind = cm.diagram(f"# {awkward}\n- {awkward}", want="mindmap")
    _mindmap(mind.source)
    time = cm.diagram(f"- 2 May 2026 {awkward}\n- 3 May 2026 {awkward}", want="timeline")
    _timeline(time.source)


def test_a_long_list_is_capped_with_a_count_of_the_rest():
    made = cm.diagram("\n".join(f"{i}. step number {i}" for i in range(1, 31)), want="flowchart")
    boxes, _ = _flow(made.source)
    assert len(boxes) == cm.MAX_NODES and boxes[-1][1] == f"and {30 - cm.MAX_NODES + 1} more steps"
    long = cm.diagram("1. " + "word " * 40 + "\n2. short", want="flowchart")
    assert all(len(w) <= cm.LABEL_CHARS + 10 for _i, w in _flow(long.source)[0])


def test_a_shape_the_words_do_not_have_falls_back_and_says_why():
    made = cm.diagram("1. Wake up\n2. Brew coffee\n3. Leave", want="timeline")
    assert made.shape == "flowchart" and "no dates" in made.note
    assert cm.diagram("Hi.", want="timeline") is None or cm.diagram("Hi.", want="timeline").shape != "timeline"


NOTES = [
    {"content": "# Boiler\nThe boiler was serviced. Next service is due in May.", "written": "2026-09-01"},
    {"content": "Garden: tomatoes went in. The beans need poles.", "written": "2026-10-02"},
    {"content": "Plumber call. He fixed the leak under the sink.", "written": date(2026, 10, 20)},
]


def test_notes_become_a_timeline_by_the_day_each_was_written():
    made = cm.diagram("", want="timeline", notes=NOTES, subject="Home")
    rows = _timeline(made.source)
    assert [w for w, _ in rows] == ["1 Sep 2026", "2 Oct 2026", "20 Oct 2026"]
    assert rows[0][1] == ["Boiler"] and "title Home" in made.source


def test_notes_become_a_mind_map_with_each_note_a_branch():
    made = cm.diagram("", want="", notes=NOTES, subject="Home")
    branches = _mindmap(made.source)
    # Each note under the composer's own name for it (`composer_write.note_name`).
    assert [w for d, w in branches if d == 1] == ["Boiler", "Garden", "Plumber call. He fixed the leak under\u2026"]
    assert any(d == 2 and "beans need poles" in w for d, w in branches)


@pytest.mark.parametrize(
    "question",
    ["make a diagram of my notes on the garden", "turn this into a flowchart", "can you draw a mind map of my trip notes",
     "show my boiler notes as a timeline", "generate a mermaid chart of the project", "put the steps into a flowchart"],
)
def test_a_chat_ask_for_a_diagram_is_read(question):
    assert cm.asks(question)


@pytest.mark.parametrize("question", ["what is the timeline for the move", "when is the boiler service", "what did I write about diagrams"])
def test_a_question_that_only_mentions_a_shape_is_not_an_ask(question):
    assert not cm.asks(question)


@pytest.mark.parametrize(("phrase", "shape"), [("make a flowchart", "flowchart"), ("as a time line", "timeline"), ("mind-map it", "mindmap"), ("a diagram please", "")])
def test_the_shape_named(phrase, shape):
    assert cm.wanted(phrase) == shape


# --- Chat and Ask, with no model --------------------------------------------------------


def _answer(client, question: str, **extra) -> str:
    import json

    response = client.post("/chat/stream", json={"question": question, **extra})
    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    return "".join(e.get("delta", "") for e in events if e.get("type") == "answer")


@pytest.fixture
def garden(ai_client, fake_ollama):
    fake_ollama.running = False
    for content in (
        "# Garden\nTomatoes went in on 2 April. The beans need poles. Water every evening.",
        "Garden plan: raised bed by the shed. Compost in autumn.",
        "Boiler serviced today. Next service is due in May.",
    ):
        ai_client.post("/entries", json={"content": content})
    return ai_client


@pytest.mark.parametrize(
    ("question", "shape"),
    [
        ("make a diagram of my notes on the garden", "mindmap"),
        ("draw a mind map of my garden notes", "mindmap"),
        ("show my garden notes as a timeline", "timeline"),
        ("can you make a flowchart of my notes about the garden", "flowchart"),
    ],
)
def test_chat_draws_a_diagram_of_the_notes_on_a_subject(garden, question, shape):
    said = _answer(garden, question)
    assert said.startswith("Here ") and "drawn by plain rule with no model" in said
    block = re.search(r"```mermaid\n(.*?)\n```", said, re.S).group(1)
    assert block.splitlines()[0].startswith(shape)
    assert "Boiler" not in block  # only the notes on the subject


@pytest.mark.parametrize(
    "question",
    [
        "turn this into a flowchart: first unplug the router, then wait thirty seconds, then plug it in and finally check the lights",
        "make this a flowchart:\n1. Unplug the router\n2. Wait thirty seconds\n3. Plug it in",
    ],
)
def test_chat_turns_the_text_given_into_a_flowchart(garden, question):
    block = re.search(r"```mermaid\n(.*?)\n```", _answer(garden, question), re.S).group(1)
    boxes, _ = _flow(block)
    assert boxes[0][1] == "Unplug the router"


def test_chat_turns_the_answer_before_into_a_diagram(garden):
    history = [{"question": "how do I reset the router", "answer": "1. Unplug it\n2. Wait a minute\n3. Plug it back in"}]
    block = re.search(r"```mermaid\n(.*?)\n```", _answer(garden, "turn that into a flowchart", history=history), re.S).group(1)
    assert [w for _i, w in _flow(block)[0]] == ["Unplug it", "Wait a minute", "Plug it back in"]


def test_with_a_model_the_model_draws_it(ai_client, fake_ollama):
    """Decision 75: with a model on, the composer's diagram is not the answer."""
    ai_client.post("/entries", json={"content": "# Garden\nTomatoes went in on 2 April."})
    fake_ollama.librarian_reply = "From the model."
    assert "drawn by plain rule" not in _answer(ai_client, "make a diagram of my notes on the garden")
