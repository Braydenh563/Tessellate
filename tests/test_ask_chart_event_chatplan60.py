"""L-chat-60: the Ask box draws the `chart` stream event (CHAT_PLAN F5).

Measured before: `answer-kit.js` handled `event.type === "chart"` only when a
caller passed `onChart`, and `ask-compose.js` passed none, so a no-model answer
that made a chart (a window's counts, a graph ask) drew it in Chat and not in Ask."""

from __future__ import annotations

from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / "frontend/js/ask-compose.js").read_text()


def test_ask_passes_on_chart() -> None:
    assert "onChart: (event)" in SRC
    assert "drawAskChart(chartHost, event.chart)" in SRC


def test_fetched_chart_does_not_wipe_a_streamed_one() -> None:
    assert 'chartHost.dataset.streamed = "1"' in SRC
    assert "!chartHost.dataset.streamed" in SRC
    assert "delete chartHost.dataset.streamed" in SRC
