"""L-chat-58 slice 1 (INBOX 1743): a woven overview sends its threads on
`support.threads` as `{label, note_ids}` so the page can draw chips that filter
the Matching records column. Fixture: tests/test_composer_overview_1743.py."""

from __future__ import annotations


from tests.test_composer_overview_1743 import answer, ask, notebook  # noqa: F401


def test_a_woven_overview_sends_threads_that_are_whole_notes(answer):  # noqa: F811
    threads = (answer["support"] or {}).get("threads")
    assert threads, answer["support"]
    cited = {str(row["note_id"]) for event in answer["grounding"] for row in event["sentences"]}
    for thread in threads:
        assert thread["label"].strip() and len(thread["note_ids"]) > 1
        assert {str(i) for i in thread["note_ids"]} <= cited


def test_threads_are_chip_sized(answer):  # noqa: F811
    for thread in answer["support"]["threads"]:
        assert len(thread["label"]) <= 40


def test_a_plain_answer_sends_none(client, notebook):  # noqa: F811
    got = ask(client, "how many notes do I have")
    assert not (got["support"] or {}).get("threads")
