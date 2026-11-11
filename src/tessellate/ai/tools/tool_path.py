"""The read tool for "how are these two notes related": the chain between them (§9).

Moved from `tool_read.py` (module line cap); the body is unchanged. Imports run
one way: this file reads `tool_read`'s preview width, never the other way round.
"""

from __future__ import annotations

from sqlalchemy.orm import Session
from tessellate.ai.tools._common import ToolError, _clip, _readable, _require_note
from tessellate.ai.tools.tool_read import GRAPH_PREVIEW_CHARS
from tessellate.entry import manager, paths
from tessellate.entry.properties import strip as strip_properties


def _path_between(session: Session, args: dict) -> dict:
    """"How are these two related?", the chain, not the neighbourhood (§9).

    `related_notes` answers "what is near this note". This answers "what joins
    these two", which the model could previously only attempt by walking one
    note's neighbourhood, then another's, and eyeballing the overlap, three
    rounds and a guess for something the notebook knows exactly.

    Private notes are not in the graph this searches (`include_private=False`).
    The model may not read one, so a route *through* one would put a preview it
    is barred from into an answer, and a route *to* one would hand it an id it
    cannot open.

    The failure case is written out as prose deliberately. "No path" with no
    reason invites the model to invent one, the notebook's most-used tag being
    ignored is exactly the kind of thing it would otherwise explain away.
    """
    source = _require_note(session, args, "note_id")
    target = _require_note(session, args, "other_note_id")
    index = paths.build(session, include_private=False)

    if source.id == target.id:
        raise ToolError("Those are the same note, pick two different ones.")
    chain = paths.find(index, source.id, target.id)
    if chain is None:
        both_connected = all(
            paths.degree(index, note.id) > 0 for note in (source, target)
        )
        return {
            "found": False,
            "from": source.id,
            "to": target.id,
            "label": f"ph:prohibit No path between #{source.id} and #{target.id}",
            "note": (
                "These two notes are not connected, not by a link, not by a "
                "reply, and not by a shared tag, within "
                f"{paths.MAX_PATH_HOPS} steps. "
                + (
                    "Both are connected to other notes, just not to each other. "
                    if both_connected
                    else "At least one of them is connected to nothing at all. "
                )
                + "Say so plainly rather than describing a connection you "
                "cannot see; use link_notes if the user wants them joined up."
            ),
        }

    hops = [
        {
            "from": step.source,
            "to": step.target,
            "how": step.how,
            # The words the answer should use. A step's kind is what the model
            # must not get wrong: reporting a shared tag as "you linked these"
            # is the same class of mistake as claiming a write that never
            # happened (§35B), one degree quieter.
            "kind": step.kind,
        }
        for step in chain
    ]
    order = [source.id] + [step.target for step in chain]
    return {
        "found": True,
        "from": source.id,
        "to": target.id,
        "hops": len(chain),
        # Not `_graph_summary`: its `how`/`hops` fields answer "how far is this
        # from the note you asked about", which on a path is said by the
        # position in the list and by the step beside it.
        "path": [
            {
                "id": note_id,
                "preview": _clip(
                    strip_properties(_readable(index.entries[note_id])).lstrip(), GRAPH_PREVIEW_CHARS
                ),
                "category": manager.category_name_for(session, index.entries[note_id]),
            }
            for note_id in order
        ],
        "steps": hops,
        "label": (
            f"ph:path {len(chain)} step{'' if len(chain) == 1 else 's'} from "
            f"#{source.id} to #{target.id}"
        ),
        "how_to_read_more": (
            "Each step says how the two notes are joined: a link somebody made, "
            "a reply thread, or a tag they share. Describe the chain in that "
            "order and name the notes by their text, not only by id."
        ),
    }
