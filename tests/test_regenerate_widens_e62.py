"""Ask again widens what is read, not only the wording (audit 1028 E62).

`attempt` used to salt the composer's phrasing and nothing else: a wrong
answer asked again read the same five notes. From the first retry the
search drops a category the question named and reads more notes, and the
composer and the model share that one search (`_prepare`, CHAT_PLAN
decision 75), so both are widened by the same call.
"""

from __future__ import annotations

from tessellate.api import routes_chat
from tessellate.entry import manager
from tessellate.search import search_manager


def _note(session, content, category):
    return manager.create_entry(session, content, category_name=category)


def _seed(session):
    health = [
        _note(session, "Slept badly, back pain again, booked a physio appointment", "Health"),
        _note(session, "Half marathon plan: three runs a week, long run grows a kilometre", "Health"),
    ]
    outside = _note(session, "Notes about the physio appointment cost for the work trip", "Work")
    return health, outside


def test_a_named_category_is_a_scope_on_the_first_ask(session, fake_embeddings):
    health, outside = _seed(session)
    found = search_manager.retrieve_detailed(session, "my Health notes about the physio appointment", fake_embeddings, limit=5)
    assert found.category == "Health"
    assert outside.id not in {e.id for e in found.entries}


def test_unscoped_drops_the_category_and_reads_beyond_it(session, fake_embeddings):
    health, outside = _seed(session)
    found = search_manager.retrieve_detailed(
        session, "my Health notes about the physio appointment", fake_embeddings, limit=5, unscoped=True
    )
    assert found.category == ""
    assert outside.id in {e.id for e in found.entries}
    assert {e.id for e in health} & {e.id for e in found.entries}


def test_widen_grows_the_limit_in_steps_and_stops_at_twenty():
    assert [search_manager.widened_limit(n) for n in (0, 1, 2, 3, 4, 9)] == [5, 10, 15, 20, 20, 20]


def test_prepare_widens_for_a_retry_and_not_for_a_first_ask(session, fake_embeddings, monkeypatch):
    """The one retrieval both the composer and a model read: `_prepare` takes
    the retry count, so neither path can be widened without the other."""
    _health, outside = _seed(session)
    monkeypatch.setattr(routes_chat.deps, "get_embeddings", lambda: fake_embeddings)
    question = "my Health notes about the physio appointment"
    first = routes_chat._prepare(session, question)
    again = routes_chat._prepare(session, question, widen=1)

    def ids(prepared):
        return {n.get("id") for n in prepared["notes"]}

    assert outside.id not in ids(first)
    assert outside.id in ids(again)


def test_the_stream_widens_on_attempt(client, session):
    """The route reads `attempt` into the search: the notes the reply carries
    (`meta.raw_results`, the same for a composed and a model answer) include the
    note outside the named category only on a retry."""
    from tests.test_composer_route_688 import _ask

    _health, outside = _seed(session)
    session.commit()
    question = "my Health notes about the physio appointment"
    first = _ask(client, question, notes_only=True, answer_from="notes")
    again = _ask(client, question, notes_only=True, answer_from="notes", attempt=1)

    def ids(events):
        return {r["id"] for r in events["meta"][0].get("raw_results", [])}

    assert outside.id not in ids(first)
    assert outside.id in ids(again)
