"""Bookmarks says what it is once (INBOX 464 (19)).

The lede under the dock ("Save links to websites you visit often: a bookmark
shelf that lives in the notebook instead of the browser") and the empty state
under it ("Add a website to keep it a click away.") said the same thing one
above the other. The lede stays, because it is there with a full list too;
the empty state is its title and its one action.
"""
import re
from tests._app_js import index_html_text

INDEX = index_html_text()


def test_the_empty_state_does_not_repeat_the_lede():
    block = re.search(r'<div id="bookmark-empty"[^>]*>(.*?)</div>', INDEX, re.S).group(1)
    #: The complaint was the same words twice (INBOX 464 (19)). The Library's
    #: empty-state recipe is a title and one sentence (`test_first_run_472.py`),
    #: so Bookmarks keeps one, and it must not be the lede's.
    sentences = [
        re.sub(r"<[^>]+>", "", body).strip()
        for attrs, body in re.findall(r"<p\b([^>]*)>(.*?)</p>", block, re.S)
        if "empty-title" not in attrs
    ]
    assert len(sentences) <= 1, sentences
    assert all("Save links to websites you visit often" not in s for s in sentences), (
        "the empty state repeats the lede"
    )
    assert 'data-empty-action="add-link"' in block
    assert "Save links to websites you visit often" in INDEX
