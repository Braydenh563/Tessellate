"""Audit 1031 row 12 (AI9, client half): one question cap, and a long question is never searched whole.

Measured on :8886 with the fake model (scratchpad notes, 160 notes): `GET /search`
with a 20,000-character query took 2,233 and 2,485 ms; the page sent the whole
question to the search box routes, the warm route and the follow-on route.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from tests._app_js import with_pieces

from tessellate.api import chat_request, routes_search
from tessellate.search import query as search_query
from tessellate.search import search_manager

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _js(name: str) -> str:
    return with_pieces(name)


def _field_max(model, name: str) -> int:
    return next(m.max_length for m in model.model_fields[name].metadata if hasattr(m, "max_length"))


def test_one_question_cap_on_the_server():
    assert search_query.QUESTION_CAP == 4000
    assert search_manager.SEARCH_QUERY_CHARS == search_query.QUESTION_CAP
    assert _field_max(routes_search.WarmBody, "q") == search_query.QUESTION_CAP
    assert _field_max(chat_request.FollowupBody, "question") == search_query.QUESTION_CAP


def test_one_question_cap_on_the_page_matches_the_server():
    chat = _js("chat.js")
    made = re.search(r"const CLIP_LIMITS = \(\(cap\) => \(\{([^}]*)\}\)\)\((\d+)\);", chat)
    assert made and int(made.group(2)) == search_query.QUESTION_CAP
    limits = made.group(1)
    assert "warmMax: 500" in limits
    for route in ("warm", "search", "question"):
        assert re.search(rf"\b{route}: cap\b", limits), route
    #: warm12-1101, fixed: the follow-on route shows the model 500 characters of the question, so the page sends
    #: no more (it sent the 4,000 cap). Changed from `followQuestion: cap`: the route's own read is the number now.
    from tessellate.ai import followups

    assert f"followQuestion: {followups.FOLLOWUP_QUESTION_CHARS}" in limits


def test_the_warm_is_sent_only_for_a_short_question():
    nav = _js("navigation.js")
    block = nav[nav.index('document.addEventListener("input"'):nav.index("async function switchTab")]
    assert "q.length >= CLIP_LIMITS.warmMax" in block
    assert 'clipFor("warm", q)' in block


def test_the_warm_route_refuses_past_the_cap_and_clips_what_it_embeds(client, monkeypatch):
    long = "a trip to kyoto in spring " * 400
    refused = client.post("/search/warm", json={"q": "x" * (search_query.QUESTION_CAP + 1)})
    assert refused.status_code == 422
    seen = []
    monkeypatch.setattr(search_manager, "query_vector", lambda emb, text: seen.append(text) or None)
    from tessellate.core import deps

    monkeypatch.setattr(deps.get_embeddings(), "is_ready", lambda: True, raising=False)
    taken = client.post("/search/warm", json={"q": long[: search_query.QUESTION_CAP]})
    assert taken.status_code == 200
    assert all(len(text) <= search_query.QUESTION_CAP for text in seen)
    assert all(len(text.split()) <= search_manager.SEARCH_QUERY_WORDS for text in seen)


def test_the_finder_route_bounds_what_it_searches_of_a_long_query(client, monkeypatch):
    """GET /search read the whole query: 2,233 ms for 20,000 characters."""
    seen = []
    real = routes_search.engine.search

    def spy(session, q, *args, **kwargs):
        seen.append(q)
        return real(session, q, *args, **kwargs)

    monkeypatch.setattr(routes_search.engine, "search", spy)
    long = " ".join(f"word{i}" for i in range(5000))
    r = client.get("/search", params={"q": long})
    assert r.status_code == 200
    assert seen and all(len(q.split()) <= search_manager.SEARCH_QUERY_WORDS and len(q) <= search_query.QUESTION_CAP for q in seen)
    assert len(r.json()["query"]) <= search_query.QUESTION_CAP


SEARCH_CALLS = {
    "app-palette.js": 1,
    "library.js": 1,
    "notes-lazy.js": 2,
    "notes-list.js": 2,
    "search.js": 2,
}


@pytest.mark.parametrize("name", sorted(SEARCH_CALLS))
def test_every_page_path_that_searches_clips_the_query_first(name):
    text = (JS / name).read_text()
    calls = re.findall(r"/search\?q=\$\{encodeURIComponent\(([^}]*)\)\}", text)
    assert len(calls) == SEARCH_CALLS[name], (name, calls)
    for call in calls:
        assert call.startswith('clipFor("search", ') and call.endswith(")"), (name, call)


def test_the_desktop_companion_has_its_own_copy_of_the_cap():
    """Its page loads no chat.js, so `clipFor` is not there."""
    text = _js("desk-companion.js")
    assert re.search(r"const DESK_QUESTION_CAP = (\d+);", text).group(1) == str(search_query.QUESTION_CAP)
    # INBOX 1528: the clip keeps the end too, the way chat.js `clipFor` does.
    assert "/search?q=${encodeURIComponent(deskClip(q))}" in text
    assert "clipFor" not in text


def test_no_unlisted_file_searches_with_text_unclipped():
    for path in sorted(JS.glob("*.js")):
        if path.name in SEARCH_CALLS or path.name in ("navigation.js", "desk-companion.js"):
            continue
        assert not re.search(r"/search\?q=", path.read_text()), path.name


def test_the_follow_up_and_from_notes_requests_send_the_clipped_question():
    for name in ("chat-turn.js", "ask-compose.js"):
        assert 'clipFor("followQuestion", question)' in _js(name)
    ask = _js("ask-compose.js")
    peek = ask[ask.index("async function fetchComposedPeek"):]
    peek = peek[: peek.index("\n}\n")]
    assert 'question: clipFor("question", question)' in peek


def test_the_after_answer_work_waits_for_the_answer_frame():
    chat = _js("chat.js")
    assert "CLIP_LIMITS.afterAnswer = (fn) =>" in chat
    assert "requestIdleCallback" in chat[chat.index("CLIP_LIMITS.afterAnswer"):][:300]
    turn = _js("chat-turn.js")
    start = turn.index("CLIP_LIMITS.afterAnswer(() => {")
    block = turn[start : turn.index("\n  });\n", start)]
    for call in ("loadRecentQuestions();", "loadMostUsed();", "offerFollowups(bubble, question, answerRaw,", "offerReminder(bubble, question);"):
        assert call in block, call
    assert "CLIP_LIMITS.afterAnswer(" in _js("ask-compose.js")
