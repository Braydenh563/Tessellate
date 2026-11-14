"""The agent's link tool offers the notebook's own kinds of link
(GRAPH_PLAN, "After KG1 to KG9").

`link_notes` took no kind at all, while two prompts told the model to link
"with link_type 'contradicts'". The parameter now exists, accepts a built-in
or a person's own relation type (KG3), and its description lists what exists
so a small model can pick without a second call. Prompt text is budgeted
(`agent.PROSE_BUDGET_CHARS`), so the list is capped and says how many it left
out.
"""

from __future__ import annotations

import json

from tessellate.ai import tools
from tessellate.core.database import EntryLink, RelationType
from sqlalchemy import select


def _link_type_description(session=None) -> str:
    offered = tools.ollama_tools(["link_notes"], session=session) if session is not None else tools.ollama_tools(["link_notes"])
    schema = offered[0]["function"]["parameters"]
    return schema["properties"]["link_type"]["description"]


def _two_notes(client):
    first = client.post("/entries", json={"content": "Wheel"}).json()["id"]
    second = client.post("/entries", json={"content": "Car"}).json()["id"]
    return first, second


def test_the_static_schema_names_the_built_in_kinds():
    text = _link_type_description()
    for key in ("related", "continues", "context", "supports", "contradicts", "example_of"):
        assert key in text


def test_the_offered_schema_lists_a_custom_type(client, session):
    client.post("/relation-types", json={"name": "Part of", "inverse": "Has part"})
    assert "part_of" in _link_type_description(session)
    assert "part_of" not in _link_type_description()


def test_the_list_is_budgeted_however_many_types_exist(client, session):
    for index in range(60):
        session.add(RelationType(key=f"kind_{index:02d}", name=f"Kind number {index}", directed=False))
    session.commit()
    session.info.pop("relation_types", None)
    text = _link_type_description(session)
    assert len(text) <= tools.LINK_TYPE_DESCRIPTION_CHARS
    assert "more" in text
    assert "related" in text  # the built-ins always lead


def test_link_notes_stores_a_custom_type(client, session):
    client.post("/relation-types", json={"name": "Part of", "inverse": "Has part"})
    wheel, car = _two_notes(client)
    out = tools.execute_tool(
        session, "link_notes", {"note_id": wheel, "other_note_id": car, "link_type": "part_of"}
    )
    assert "error" not in out, out
    link = session.scalars(select(EntryLink)).one()
    assert link.link_type == "part_of"


def test_link_notes_stores_a_built_in_type(client, session):
    wheel, car = _two_notes(client)
    out = tools.execute_tool(
        session, "link_notes", {"note_id": wheel, "other_note_id": car, "link_type": "supports"}
    )
    assert "error" not in out, out
    assert session.scalars(select(EntryLink)).one().link_type == "supports"


def test_an_unknown_type_is_refused_with_the_list(client, session):
    client.post("/relation-types", json={"name": "Part of"})
    wheel, car = _two_notes(client)
    out = tools.execute_tool(
        session, "link_notes", {"note_id": wheel, "other_note_id": car, "link_type": "bogus"}
    )
    assert "error" in out and "part_of" in out["error"] and "related" in out["error"]
    assert session.scalars(select(EntryLink)).first() is None


def test_no_type_still_links_as_before(client, session):
    wheel, car = _two_notes(client)
    out = tools.execute_tool(session, "link_notes", {"note_id": wheel, "other_note_id": car})
    assert out["linked"] == [wheel, car]
    assert session.scalars(select(EntryLink)).one().link_type is None


def test_the_schema_stays_valid_json_for_the_wire(client, session):
    client.post("/relation-types", json={"name": "Part of"})
    json.dumps(tools.ollama_tools(None, session=session))
