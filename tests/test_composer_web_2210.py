"""A pasted link, a web search that cannot run, and a page read without a model.

The 22-10 bug doc: "Read <url> and tell me about it" searched the notes for
"read", "www" and "thesaurus"; a web search with SearXNG down said nothing
useful. A link is offered a fetch and a summary (or the setting that allows
it), a failing service is named with the setting that fixes it, and a page is
analysed into key points, key terms and sections by the composer.
"""

from __future__ import annotations

import re
import pytest

from tessellate.ai import composer_web, page_analysis
from tessellate.core import deps
from tessellate.search import websearch
from tests.test_composer_route_688 import _ask

BLOCKS = [
    {"type": "heading", "level": 1, "text": "Tides explained"},
    {"type": "p", "text": "Tides are caused by the pull of the moon and the sun on the oceans. The moon matters most because it is close."},
    {"type": "heading", "level": 2, "text": "Spring tides"},
    {"type": "p", "text": "Spring tides come at new and full moon, when the sun and the moon pull along one line. They give the biggest range."},
    {"type": "li", "text": "Spring tides are not named for the season."},
    {"type": "heading", "level": 2, "text": "Neap tides"},
    {"type": "p", "text": "Neap tides come at the quarter moons, when the sun and the moon pull at right angles. The range is smallest then."},
    {"type": "p", "text": "Sailors have kept tide tables for centuries."},
]
PAGE = {
    "url": "https://example.org/tides",
    "title": "Tides explained",
    "domain": "example.org",
    "blocks": BLOCKS,
    "text": "\n\n".join(b["text"] for b in BLOCKS),
    "words": 90,
    "read_minutes": 1,
}


# --- the link ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("question", "url"),
    [
        ("Read https://www.thesaurus.com/browse/happy and tell me about it", "https://www.thesaurus.com/browse/happy"),
        ("what is on www.example.com/a/b, please", "https://www.example.com/a/b"),
        ("https://example.org/tides", "https://example.org/tides"),
        ("summarise (https://example.org/tides).", "https://example.org/tides"),
        ("no link here", None),
    ],
)
def test_url_in(question, url):
    assert composer_web.url_in(question) == url


@pytest.mark.parametrize(
    ("question", "reads"),
    [
        ("Read https://example.org/x and tell me about it", True),
        ("https://example.org/x", True),
        ("what does https://example.org/x say", True),
        ("summarise https://example.org/x", True),
        ("analyse this page https://example.org/x", True),
        ("save https://example.org/x to my notes", False),
        ("add https://example.org/x to the reading list note", False),
        ("what is the weather", False),
    ],
)
def test_reads_link(question, reads):
    assert composer_web.reads_link(question) is reads


def test_page_analysis_key_points_are_the_pages_own_sentences():
    found = page_analysis.analyse(BLOCKS)
    assert 2 <= len(found["key_points"]) <= 5
    for point in found["key_points"]:
        assert point.rstrip(".") in PAGE["text"]
    assert len(found["key_points"]) == len(set(found["key_points"]))
    # Page order, so the points read as the page does.
    positions = [PAGE["text"].index(p.rstrip(".")) for p in found["key_points"]]
    assert positions == sorted(positions)


def test_page_analysis_terms_and_sections():
    found = page_analysis.analyse(BLOCKS)
    assert "tides" in found["terms"] or "tide" in found["terms"]
    assert "moon" in found["terms"]
    assert all(len(t) > 2 for t in found["terms"]) and len(found["terms"]) <= 8
    assert [s["title"] for s in found["sections"]] == ["Tides explained", "Spring tides", "Neap tides"]
    assert [s["level"] for s in found["sections"]] == [1, 2, 2]


def test_page_analysis_of_nothing_is_empty_not_an_error():
    assert page_analysis.analyse([]) == {"key_points": [], "terms": [], "sections": []}
    assert page_analysis.analyse([{"type": "p", "text": "Hi."}])["key_points"] in ([], ["Hi."])


# --- through /chat/stream --------------------------------------------------------------


def test_a_link_with_web_off_says_what_is_needed_not_a_notes_search(client, session):
    deps.get_config().set_preference("web_search_enabled", False)
    out = _ask(client, "Read https://www.thesaurus.com/browse/happy and tell me about it", use_tools=True)
    text = out["text"]
    assert "web" in text.lower() and "off" in text.lower()
    assert re.search(r"(?<![\w.])thesaurus\.com(?![\w.])", text)
    assert "don't see any mention" not in text and "closest note" not in text.lower()


def test_a_link_with_web_on_is_fetched_and_summarised(client, session, monkeypatch):
    deps.get_config().set_preference("web_search_enabled", True)
    seen = []
    monkeypatch.setattr(websearch, "fetch_readable_cached", lambda url: seen.append(url) or dict(PAGE))
    out = _ask(client, "Read https://example.org/tides and tell me about it", use_tools=True)
    assert seen == ["https://example.org/tides"]
    assert "Tides explained" in out["text"]
    assert "Spring tides come at new and full moon" in out["text"]
    assert re.search(r"(?<![\w.])example\.org(?![\w.])", out["text"])


def test_a_page_that_cannot_be_read_is_said_plainly(client, session, monkeypatch):
    deps.get_config().set_preference("web_search_enabled", True)

    def refuse(url):  # noqa: ANN001, ARG001
        raise websearch.WebSearchError("example.org refused the reader (403)")

    monkeypatch.setattr(websearch, "fetch_readable_cached", refuse)
    out = _ask(client, "Read https://example.org/tides and tell me about it", use_tools=True)
    assert "could not read" in out["text"].lower() or "couldn't read" in out["text"].lower()
    assert "403" in out["text"]


def test_a_search_that_cannot_run_names_the_service_and_the_setting(client, session, monkeypatch):
    deps.get_config().set_preference("web_search_enabled", True)

    def down(*args, **kwargs):  # noqa: ANN002, ANN003, ARG001
        raise websearch.WebSearchError("Could not reach SearXNG at http://127.0.0.1:8888 (connection refused)")

    monkeypatch.setattr(websearch, "search_web", down)
    out = _ask(client, "what causes spring tides", use_tools=True)
    text = out["text"]
    assert "search" in text.lower() and "8888" in text
    assert "settings" in text.lower()
    assert "general knowledge" not in text


def test_a_down_service_offers_the_buttons_that_fix_it_not_a_command():
    #: INBOX 1490 (the owner): buttons, not a pasted docker command. The command
    #: stays in the Guide (below) and in Settings, Web search.
    out = composer_web.search_down("connection refused", "http://127.0.0.1:8888", "auto", can_start=True)
    assert "docker" not in out["text"].lower() and "8888" in out["text"]
    assert out["offer"]["kind"] == "searxng-start" and out["offer"]["also"][0] == {"kind": "open", "surface": "settings:websearch", "label": composer_web.SETUP_LABEL}


def test_web_search_that_was_never_set_up_says_so_and_links_the_setting():
    out = composer_web.search_down("no address", "", "searxng")
    assert "not set up" in out["text"] and "not answering" not in out["text"]
    assert out["offer"]["surface"] == "settings:websearch"


def test_the_guide_repeats_the_one_liner():
    from tessellate.ai import help_chat

    body = next(t["body"] for t in help_chat.HELP_TOPICS if t["id"] == "websearch")
    assert composer_web.DOCKER_ONE_LINER in body
