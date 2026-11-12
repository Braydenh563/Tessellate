"""Past chats and the parts of the skill tools that do not need the registry.

Moved whole from `__init__.py` (audit AR3, gods-2): the code is unchanged, and
`__init__` re-exports every name here that anything reads. Imports run one way,
down the layer list in `__init__.py`'s docstring, never back to `__init__`.
"""

from __future__ import annotations

import json

from tessellate.core.database import LIKE_ESCAPE, like_escape
from tessellate.ai.tools._common import PREVIEW_CHARS, ToolError, _clip, _limit_arg
from sqlalchemy.orm import Session
from tessellate.core import deps
from sqlalchemy import select
from tessellate.ai import skills

# --- documents, past chats, and skills ------------------------------------------
# Documents are deliberately kept out of retrieval: a note is a captured
# thought, a document is something you sat down and write, and mixing them
# would put every half-finished draft into every search result. That decision
# also meant the model could not read a document even when explicitly asked
# to. These tools are the "unless you ask for it by name" half of that rule, 
# nothing arrives in context unless the model goes and gets it.



def _excerpts(messages: list, term: str) -> list[dict]:
    """The matching turns of one chat, or its opening exchange when none match."""
    # The matching exchanges, not the whole thread: a long conversation
    # would spend the entire budget on one tool call. Whole turns, though
    #, a question that matched without the answer that followed it is
    # useless for "what did we decide?", which is the question this tool
    # exists to answer.
    wanted_indexes: set[int] = set()
    for index, message in enumerate(messages):
        content = str(message.get("content", ""))
        if not term or term.lower() in content.lower():
            turn_start = index - (index % 2)
            wanted_indexes.update({turn_start, turn_start + 1})
        if len(wanted_indexes) >= 6:
            break
    excerpts = [
        {
            "role": messages[i].get("role"),
            "text": _clip(str(messages[i].get("content", "")), PREVIEW_CHARS),
        }
        for i in sorted(wanted_indexes)
        if i < len(messages)
    ]
    return excerpts or [
        {"role": m.get("role"), "text": _clip(str(m.get("content", "")), PREVIEW_CHARS)} for m in messages[:2]
    ]


def _search_chat_history(session: Session, args: dict) -> dict:
    """Past conversations. "What did we decide last week?" was unanswerable:
    each turn only ever saw its own thread, so the assistant had no memory of
    anything said in a different chat."""
    from tessellate.core.conversation_text import conversation_matches
    from tessellate.core.database import Conversation

    limit = _limit_arg(args, default=5)
    term = str(args.get("query") or "").strip()
    query = select(Conversation)
    if term:
        # Prefilter in SQL, then confirm in Python: `messages` is a JSON
        # column, so a raw LIKE also matches its keys, "tent" is inside
        # "content", which matched every conversation ever saved.
        like = f"%{like_escape(term)}%"
        query = query.where(
            Conversation.title.ilike(like, escape=LIKE_ESCAPE)
            | Conversation.messages.ilike(like, escape=LIKE_ESCAPE)
        )
    rows = list(
        session.scalars(
            query.order_by(Conversation.updated_at.desc()).limit(limit * 4 if term else limit)
        )
    )
    if term:
        rows = [c for c in rows if conversation_matches(c, term)][:limit]
    found = []
    for conversation in rows:
        try:
            messages = json.loads(conversation.messages)
        except ValueError:
            messages = []
        excerpts = _excerpts(messages, term)
        found.append(
            {
                "id": conversation.id,
                "title": conversation.title,
                "updated_at": conversation.updated_at.isoformat(),
                "turns": len(messages) // 2,
                "excerpts": excerpts,
            }
        )
    return {
        "conversations": found,
        "found": len(found),
        "note_to_model": (
            "These are excerpts from earlier chats, including possibly this "
            "one. Say when you're relying on something said in a past "
            "conversation rather than presenting it as the user's notes."
        ),
        "label": f"ph:chat-circle Searched past chats{f' for “{_clip(term, 30)}”' if term else ''}",
    }


def _verify_block(args: dict) -> dict | None:
    """`save_skill`'s four flat `verify_*` arguments, as one block.

    The shape the app stores is nested (`{tool, args, field, expect}`); the
    shape a small model writes reliably is flat. This is the one place they
    meet, and it is deliberately dumb: anything wrong with the values is
    `skills.verify_spec`'s to say, in the sentence it already has for it.
    """
    tool = str(args.get("verify_tool") or "").strip()
    if not tool:
        return None
    predicate = str(args.get("verify_expect") or "").strip().lower() or "unchanged"
    value = args.get("verify_value")
    block: dict = {
        "tool": tool,
        "expect": {predicate: True if predicate == "unchanged" else value},
    }
    if args.get("verify_untagged"):
        block["args"] = {"untagged": True}
        #: `count_notes` answers a filtered question in `count` and an
        #: unfiltered one in `total`, and `VERIFY_COUNT_FIELDS` tries `total`
        #: first, so a filtered block that did not name its field would read
        #: the number it was filtering away from.
        block["field"] = "count"
    return block


def _delete_skill(session: Session, args: dict) -> dict:
    config = deps.get_config()
    name = str(args["name"]).strip()
    stored = skills.stored(config)
    remaining = [s for s in stored if s.get("name") != name]
    if len(remaining) == len(stored):
        if any(name == shipped["name"] for shipped in skills.builtins()):
            raise ToolError(f"“{name}” is a built-in skill and can't be deleted")
        if any(name == own["name"] for own in skills.folder_skills(config)[0]):
            raise ToolError(f"“{name}” comes from a file in the skills folder; delete the file to remove it")  # the person's own file (B8)
        raise ToolError(f"There's no saved skill called “{name}”")
    from tessellate.ai.tools.undo_inverses import skill_restore

    gone = next(s for s in stored if s.get("name") == name)
    config.set_preference("skills", remaining)
    return {"name": name, "label": f"ph:lightning Deleted the “{name}” skill", "undo": skill_restore(gone)}
