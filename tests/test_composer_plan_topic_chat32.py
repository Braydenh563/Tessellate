"""L-chat-32: "organise everything about the harbor" names a topic, not a time window, so it is no week plan."""

from __future__ import annotations

import pytest

from tessellate.ai import composer_plan


@pytest.mark.parametrize("said", [
    "organise everything about the harbor",
    "can you sort out my boiler stuff",
    "sort out all my notes on the garden",
    "arrange everything to do with the move",
])
def test_a_named_topic_is_not_a_plan_ask(said):
    assert composer_plan._topic_target(composer_plan._PLAN.match(said))


@pytest.mark.parametrize("said", [
    "organise my week", "plan my day", "sort out my tasks", "prioritise my tasks this week",
    "organise my stuff for the week", "plan tomorrow",
])
def test_a_time_or_task_ask_stays_a_plan(said):
    assert not composer_plan._topic_target(composer_plan._PLAN.match(said))
