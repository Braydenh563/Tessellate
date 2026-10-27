"""Analyse a page in the web panel (22-10 bug doc): key points, key terms
highlighted in the page, and a section list whose entries jump to the heading.
No model: `ai/page_analysis.py` reads the blocks the reader already fetched."""

from __future__ import annotations

from pathlib import Path

from tests.test_composer_web_2210 import BLOCKS

ROOT = Path(__file__).resolve().parents[1]


def test_the_analyse_route_reads_the_blocks_it_is_given(client):
    response = client.post("/websearch/analyse", json={"blocks": BLOCKS})
    assert response.status_code == 200
    found = response.json()
    assert 2 <= len(found["key_points"]) <= 5
    assert "moon" in found["terms"]
    assert [s["title"] for s in found["sections"]] == ["Tides explained", "Spring tides", "Neap tides"]
    # Which heading, among the page's headings, a jump link goes to.
    assert [s["n"] for s in found["sections"]] == [0, 1, 2]


def test_the_route_makes_no_request_to_the_web(client, monkeypatch):
    from tessellate.search import websearch

    def refuse(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("analysis must not fetch anything")

    monkeypatch.setattr(websearch, "fetch_readable", refuse)
    monkeypatch.setattr(websearch, "fetch_readable_cached", refuse)
    response = client.post("/websearch/analyse", json={"blocks": BLOCKS})
    assert response.status_code == 200


def test_oversized_input_is_refused(client):
    long_text = client.post("/websearch/analyse", json={"blocks": [{"type": "p", "text": "x" * 6000}]})
    many_blocks = client.post("/websearch/analyse", json={"blocks": [{"type": "p", "text": "word"}] * 3000})
    assert long_text.status_code == 422
    assert many_blocks.status_code == 422


def test_the_reader_has_an_analyse_button_and_a_place_for_it():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="web-reader-analyse"' in html
    assert 'id="web-reader-analysis"' in html
    assert html.index('id="web-reader-analysis"') < html.index('id="web-reader-text"')


def test_the_analysis_is_drawn_without_innerhtml_and_jumps_to_headings():
    js = (ROOT / "frontend" / "js" / "web-clip.js").read_text(encoding="utf-8")
    assert "/websearch/analyse" in js
    assert '$("web-reader-analyse").addEventListener("click", analyseWebPage)' in js
    assert "scrollIntoView" in js and ".reader-heading" in js
    assert "createElement(\"mark\")" in js
    assert "innerHTML =" not in js and ".innerHTML" not in js.replace("never innerHTML", "")
