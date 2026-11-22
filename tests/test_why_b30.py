"""B30, "Why this answer" (CHAT_PLAN, INBOX 805): every answer says how it
was made, as a job's lines: what the question was read as, what was
searched and matched, who wrote it and in what shape, what it cited, and
how long it took."""

from __future__ import annotations

from pathlib import Path

import pytest

from tessellate.ai import why
from tests.test_composer_social import web  # noqa: F401  # the fixture
from tests.test_composer_route_688 import _ask, _seed

ROOT = Path(__file__).resolve().parents[1]


def _texts(rows: list[dict]) -> list[str]:
    return [row["text"] for row in rows]


def test_a_composed_answer_says_each_stage_with_its_time():
    rows = why.lines(intent="notes", mode="hybrid", matched=6, used=4, composed=True, shape="digest:overview",
                     marks={"read": 0.01, "searched": 0.01, "answered": 0.03, "done": 0.05})
    assert _texts(rows) == [
        "Read the question as a question about your notes.",
        "Searched your notes by meaning and keywords: 6 notes matched.",
        "Atlas's assistant wrote it from your notes, with no model: every line comes from a note it cites.",
        "Shaped as an overview, grouped by when you wrote each note.",
        "Cited 4 of the 6; the rest are in the column beside it.",
        "Done in 0.05 s of work here; the time under the answer is the whole wait.",
    ]
    assert [row["at"] for row in rows] == sorted(row["at"] for row in rows)


def test_a_model_answer_names_the_model_and_the_context_it_was_given():
    rows = why.lines(intent="about_app", mode="none", matched=0, used=0, composed=False, model="qwen-small",
                     context=True, marks={"done": 1.5})
    text = " ".join(_texts(rows))
    assert "The model, qwen-small, wrote it." in text
    assert "handed the app's own answer as a fact to use, not as the reply" in text
    assert "Searched" not in text


def test_a_worked_out_answer_says_no_model_and_a_scope_says_so():
    worked = _texts(why.lines(intent="utility", mode="none", matched=0, used=0, composed=False, marks={"done": 0.0}))
    assert "Atlas worked it out itself, with no model." in worked
    scoped = _texts(why.lines(intent="notes", mode="category", matched=1, used=1, scoped=True, composed=True, marks={}))
    assert scoped[1] == "Read only the notes you pointed it at: 1 note matched."
    assert scoped[-2] == "Cited 1 of the 1."


def test_every_line_is_house_copy():
    rows = why.lines(intent="notes", mode="dated", matched=2, used=0, when="last week", composed=False, model="m",
                     shape="when", context=False, marks={"done": 2})
    for text in _texts(rows):
        assert text[0].isupper() and text.endswith(".") and chr(0x2014) not in text and "!" not in text
    assert rows[0]["text"] == "Read the question as a question about your notes, for last week."


def test_through_the_route_the_lines_arrive_before_done(client, session):
    _seed(session)
    out = _ask(client, "What is the Harbor launch plan?", notes_only=True, use_tools=False)
    lines = out["why"][0]["lines"]
    texts = _texts(lines)
    assert texts[0].startswith("Read the question as")
    assert any("matched" in t for t in texts) and texts[-1].startswith("Done in")
    assert any("with no model" in t for t in texts)


@pytest.mark.parametrize("question", ["can you search the web?"])
def test_with_a_model_up_the_lines_name_it_and_its_context(ai_client, fake_ollama, web, question):  # noqa: F811
    """Decision 75: the model answered, and the app's line was its context."""
    out = _ask(ai_client, question, use_tools=False)
    text = " ".join(_texts(out["why"][0]["lines"]))
    assert "wrote it" in text and "handed the app's own answer" in text
    assert "with no model" not in text


def test_the_ask_box_draws_the_lines_in_one_fold():
    js = (ROOT / "frontend/js/answer-kit.js").read_text(encoding="utf-8")
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert 'id="ask-why"' in html
    assert 'else if (event.type === "why" && onWhy) onWhy(event);' in js
    lazy = (ROOT / "frontend/js/ask-compose.js").read_text(encoding="utf-8")
    body = lazy[lazy.index("function renderAskWhy("):]
    body = body[: body.index("\n}\n")]
    assert 'fold.className = "agent-step why-fold"' in body and 'summary.className = "fold-summary"' in body


def test_chat_and_the_popup_agent_draw_the_same_fold_from_the_same_event():
    """OPEN row 6 (B30): the `why` event is not Ask's alone. Chat's bubble and
    the popup agent keep its lines and draw `drawWhyTrail` (the one fold
    builder, `renderAskWhy`) once the answer is final, in the lazy bundle."""
    chat = (ROOT / "frontend/js/chat-turn.js").read_text(encoding="utf-8")
    palette = (ROOT / "frontend/js/palette.js").read_text(encoding="utf-8")
    lazy = (ROOT / "frontend/js/ask-compose.js").read_text(encoding="utf-8")
    assert "onWhy: (event) => { t.whyLines = event.lines; }," in chat
    assert 'ensureModule("askCompose").then(() => drawWhyTrail(recordsHolder, t.whyLines))' in chat
    assert "onWhy: (event) => (trail = event.lines)," in palette
    assert 'ensureModule("askCompose").then(() => drawWhyTrail(agentMsg, trail))' in palette
    assert "function drawWhyTrail(parent, lines, before = null)" in lazy and "renderAskWhy(lines, holder)" in lazy
    for text in (chat, palette):
        assert "why-fold" not in text and "why-lines" not in text
