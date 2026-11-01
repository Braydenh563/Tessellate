"""The corners of `_tool_sources` that `test_tool_sources.py` leaves open.

Characterisation tests written before the function was split by tool
(cc-1101): hits that are not dicts, the cap per call, the alternative field
names a file result may use, a source with nothing to name it, and a tool that
has no sources at all.
"""

from __future__ import annotations

from tessellate.ai.agent_policy import SOURCE_LIMIT, _tool_sources


def test_a_web_hit_that_is_not_a_dict_is_skipped_and_the_rest_are_capped():
    hits = ["junk", None, *({"title": f"T{i}", "url": f"https://x/{i}"} for i in range(SOURCE_LIMIT + 3))]
    rows = _tool_sources("web_search", {"results": hits})
    # The cap counts hits read, not rows kept: two of the first eight were junk.
    assert [r["title"] for r in rows] == [f"T{i}" for i in range(SOURCE_LIMIT - 2)]


def test_a_web_hit_with_no_title_is_named_by_its_address_and_one_with_neither_is_dropped():
    rows = _tool_sources("web_search", {"results": [{"url": "https://x/a"}, {"snippet": "words only"}, {}]})
    assert rows == [{"title": "https://x/a", "url": "https://x/a", "snippet": ""}]


def test_a_page_with_no_title_or_address_is_dropped():
    assert _tool_sources("read_url", {"text": "body"}) == []


def test_file_matches_use_either_field_name_and_skip_what_is_not_a_dict():
    rows = _tool_sources(
        "search_files",
        {"results": ["junk", {"name": "a.md", "text": "from text"}, {"path": "b.md", "snippet": "from snippet"}, {}]},
    )
    assert rows == [
        {"title": "a.md", "url": "", "snippet": "from text"},
        {"title": "b.md", "url": "", "snippet": "from snippet"},
    ]
    assert len(_tool_sources("read_file", {"matches": [{"path": f"{i}.md"} for i in range(SOURCE_LIMIT + 2)]})) == SOURCE_LIMIT


def test_a_single_file_result_reads_its_name_and_content_when_it_has_no_path_or_text():
    rows = _tool_sources("read_file", {"name": "n.md", "content": "the body"})
    assert rows == [{"title": "n.md", "url": "", "snippet": "the body"}]
    assert _tool_sources("read_file", {}) == []
    assert _tool_sources("read_file", {"matches": [], "path": "p.md", "text": "t"}) == [
        {"title": "p.md", "url": "", "snippet": "t"}
    ]


def test_a_tool_with_no_sources_yields_none():
    assert _tool_sources("count_notes", {"count": 3}) == []
