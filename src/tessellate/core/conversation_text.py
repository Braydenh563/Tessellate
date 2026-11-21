"""What a chat says, read from its decoded messages: shared by the chat list route and the agent's
chat search tool, so an `ai` module never imports an `api` route (hub, CI #230 import cycles)."""

from __future__ import annotations

import json

from tessellate.core.database import Conversation


def conversation_matches(conversation: Conversation, term: str) -> bool:
    """Does this chat actually mention `term`?

    Not a LIKE against the `messages` column. That column holds JSON, so its
    own keys are searchable text: "tent" is a substring of "content", which
    made every single conversation match. The decoded message text is the
    only thing a user means by "what was said".
    """
    lowered = term.lower()
    if lowered in conversation.title.lower():
        return True
    try:
        messages = json.loads(conversation.messages)
    except ValueError:
        return False
    return any(lowered in str(m.get("content", "")).lower() for m in messages)
