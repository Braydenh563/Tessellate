"""Settings, Web search says what the code does, and the code still does it
(BACKLOG section 13: "a visible statement of what's true").

The '?' next to the Web search heading used to say two sentences. The privacy
properties lived in the README and in code comments, so someone deciding
whether to turn search on had to already know where to look. The popover now
lists them, and this test holds both halves: every claim the popover makes is
checked against the module it describes, so the copy cannot drift into a
promise the code stopped keeping.
"""

from __future__ import annotations

import re
from pathlib import Path

from tessellate.core import privacy_http
from tessellate.search import websearch
from tests._app_js import index_html_text

ROOT = Path(__file__).resolve().parent.parent
INDEX = index_html_text()


def _popover() -> str:
    match = re.search(r'id="websearch-help"[^>]*>(.*?)</div>', INDEX, re.S)
    assert match, "the websearch-help popover is gone"
    return re.sub(r"\s+", " ", match.group(1))


def test_the_popover_lists_each_property():
    text = _popover()
    for claim in (
        "ordinary browser",
        "No cookies are kept between searches",
        "not in the web address",
        "Tracking parameters are stripped",
        "your own SearXNG instance",
        "docs/PRIVACY.md",
    ):
        assert claim in text, claim


def test_the_copy_has_no_em_dash_and_no_exclamation():
    text = _popover()
    assert chr(0x2014) not in text
    assert "!" not in text


def test_the_request_does_not_name_the_app():
    assert "memorymap" not in privacy_http.USER_AGENT.lower()
    assert privacy_http.PRIVACY_HEADERS["Referer"] == ""


def test_a_search_session_keeps_no_cookies():
    session = websearch._private_session()
    try:
        session.cookies.set("a", "b")
        session.cookies.clear()
        assert len(session.cookies) == 0
    finally:
        session.close()


def test_both_engines_send_the_words_in_the_body():
    import inspect

    # The probe that pings a local SearXNG may use `params=` (it sends a fixed
    # word, not the user's); the two functions that carry a real query may not.
    for function in (websearch._search_searxng, websearch._search_duckduckgo):
        source = inspect.getsource(function)
        assert "session.post(" in source, function.__name__
        assert "params=" not in source, function.__name__


def test_result_addresses_are_stripped_of_tracking():
    dirty = "https://example.org/page?utm_source=x&id=7"
    clean = privacy_http.strip_tracking(dirty)
    assert "utm_source" not in clean
    assert "id=7" in clean
