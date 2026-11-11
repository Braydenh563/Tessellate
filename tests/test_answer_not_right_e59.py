"""Not right on a whole answer (audit 1028 E59).

The answer's menu marks it not right: one `wrong_answer` correction per note
the answer cited, against the question as asked. From then on, a question like
that one (the same half-the-words rule `open_after_ask` uses) reads those notes
last, and leaves them out once the person has said so twice ("once is a
mistake, twice is a rule", `learning.EXCLUDE_AFTER`). The search is the one
retrieval a composed answer and a model's both read, so neither path learns
without the other. The undo is the correction's own Delete.
"""

from __future__ import annotations

from tessellate.ai import learning
from tessellate.core import deps
from tessellate.entry import manager
from tessellate.search import search_manager


def _note(session, text):
    entry = manager.create_entry(session, text, tags=[])
    session.commit()
    return entry


def _ids(session, question):
    entries, _mode = search_manager.retrieve(session, question, deps.get_embeddings(), limit=5)
    return [entry.id for entry in entries]


def _two(session):
    a = _note(session, "sourdough starter feeding schedule, morning and night")
    b = _note(session, "sourdough loaf shaping and scoring notes")
    return a, b


def test_a_marked_note_is_read_last_for_a_question_like_it(session):
    a, b = _two(session)
    first = _ids(session, "sourdough notes")[0]
    other = b.id if first == a.id else a.id
    learning.record(session, kind="wrong_answer", subject={"question": "sourdough notes", "entry_id": first})
    session.commit()
    after = _ids(session, "my sourdough notes")
    assert after[0] == other and after[-1] == first


def test_marked_twice_is_left_out_but_never_for_an_unlike_question(session):
    _two(session)
    first = _ids(session, "sourdough notes")[0]
    for _ in range(learning.EXCLUDE_AFTER):
        learning.record(session, kind="wrong_answer", subject={"question": "sourdough notes", "entry_id": first})
    session.commit()
    assert first not in _ids(session, "my sourdough notes")
    unlike = _note(session, "tax return deadline and the sourdough class fee")
    assert unlike.id in _ids(session, "tax return deadline")


def test_a_correction_is_taken_back_by_its_delete(client, session):
    _two(session)
    first = _ids(session, "sourdough notes")[0]
    made = client.post(
        "/learned/answer-verdict", json={"question": "sourdough notes", "entry_ids": [first], "line": "sourdough"}
    )
    assert made.status_code == 201
    ids = made.json()["ids"]
    assert len(ids) == 1
    assert _ids(session, "sourdough notes")[-1] == first
    taken_back = client.delete(f"/learned/corrections/{ids[0]}")
    assert taken_back.status_code == 200
    session.expire_all()
    assert _ids(session, "sourdough notes")[0] == first


def test_the_route_records_one_correction_per_cited_note_and_refuses_nothing_to_mark(client, session):
    a, b = _two(session)
    made = client.post("/learned/answer-verdict", json={"question": "sourdough notes", "entry_ids": [a.id, b.id, a.id]})
    assert made.status_code == 201
    assert made.json()["count"] == 2
    kinds = client.get("/learned/corrections", params={"kind": "wrong_answer"}).json()
    assert {item["subject"]["entry_id"] for item in kinds} == {a.id, b.id}
    assert all(item["subject"]["question"] == "sourdough notes" for item in kinds)
    nothing = client.post("/learned/answer-verdict", json={"question": "q", "entry_ids": [999999]})
    assert nothing.status_code == 422


def test_a_private_note_is_not_marked(client, session):
    secret = _note(session, "secret sourdough recipe")
    secret.is_private = True
    session.commit()
    assert client.post("/learned/answer-verdict", json={"question": "sourdough", "entry_ids": [secret.id]}).status_code == 422


def test_the_switch_for_corrections_stops_it(session, monkeypatch):
    _two(session)
    first = _ids(session, "sourdough notes")[0]
    learning.record(session, kind="wrong_answer", subject={"question": "sourdough notes", "entry_id": first})
    session.commit()
    from tessellate.ai import facts

    monkeypatch.setattr(facts, "runner_enabled", lambda name: False if name == "corrections" else True)
    assert _ids(session, "sourdough notes")[0] == first


def test_the_menu_item_marks_the_cited_notes_and_hides_in_a_private_chat():
    from tests._app_js import JS_DIR

    turn = (JS_DIR / "chat-turn.js").read_text(encoding="utf-8")
    assert 'title: "This answer is wrong", onClick: () => markAnswerNotRight(bubble, question)' in turn
    assert "!chatConv?.private && question && bubble.querySelector(\".chat-source-card[data-note-id]\")" in turn
    assert '"/learned/answer-verdict"' in turn
    assert "/learned/corrections/${id}" in turn  # the undo is the correction's own Delete


def test_the_guide_says_where_not_right_is():
    from tessellate.ai import help_chat

    topic = next(t for t in help_chat.HELP_TOPICS if t["id"] == "answer-menu")
    assert "This answer is wrong" in topic["body"] and "Regenerate as" in topic["body"]
    assert "answer-menu" in help_chat.TOPIC_META
