"""L196 (E58): a long turn's checkpoints refetch the saved-chat list once, when the first one creates the chat, never per round."""

from tests._app_js import frontend_text


def test_only_the_creating_checkpoint_reloads_the_list():
    js = frontend_text("chat-turn.js")
    body = js[js.index("async writeCheckpoint(t) {") :].split("\n  // What was typed", 1)[0]
    assert body.count("loadConversationList()") == 1
    created = body[body.index("if (convRef.id === null) {") : body.index("} else if (t.checkpointed")]
    assert "loadConversationList()" in created
    assert "if (t.checkpointInFlight || t.convRef.private) return t.checkpointRun;" in js
