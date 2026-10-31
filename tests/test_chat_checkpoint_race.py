"""A chat turn is saved once, however fast the model answers.

Found taking the README's Chat shot (INBOX 431 (g)): against a model that
streamed a whole answer in about a second, the agent round's checkpoint
(`checkpointTurn`, chat-attach.js) was still creating the conversation when
the turn finished, so the end-of-turn save saw no id and created a second
one. The list showed the same question twice, 43ms apart, one of them a
half-turn. The end save now waits for a checkpoint in flight.
"""

from __future__ import annotations

from tests._app_js import app_js_text

JS = app_js_text()


def test_the_checkpoint_keeps_its_promise() -> None:
    assert "let checkpointRun = null;" in JS
    assert "checkpointRun = writeCheckpoint();" in JS
    # A second call while one is in flight hands back the same write.
    assert "if (checkpointInFlight || convRef.private) return checkpointRun;" in JS


def test_the_end_save_waits_for_a_checkpoint_in_flight() -> None:
    wait = JS.index("if (checkpointRun) await checkpointRun;")
    create = JS.index('const created = await apiJson("/conversations", {\n        method: "POST",\n        body: JSON.stringify(payload),')
    assert wait < create, "the end save must wait before it decides to create"
