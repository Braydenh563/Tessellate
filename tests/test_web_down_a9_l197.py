"""L197 (A9): the web-down reply keeps the service's address and port, and
says each piece of advice once (the head names no button the lines repeat)."""

from __future__ import annotations

import pytest

from tessellate.ai import agent_policy, composer_web


@pytest.mark.parametrize("can_start", [True, False])
def test_the_port_is_kept_and_no_line_repeats(can_start):
    text = composer_web.search_down("timed out", "http://127.0.0.1:8888", "searxng", can_start=can_start)["text"]
    assert "http://127.0.0.1:8888" in text
    lines = [line for line in text.split("\n") if line.strip()]
    assert len(lines) == len(set(lines)), lines
    head = lines[0].lower()
    for button in lines[1:]:
        assert button.lower() not in head, button


def test_the_agent_hint_for_a_dead_search_is_one_instruction_not_a_retry():
    hint = agent_policy._recovery_hint("web_search", "connection refused")
    assert hint == agent_policy._RECOVERY_HINTS["web_down"]
    assert "Do not retry" in hint and hint.count("Settings") == 1
