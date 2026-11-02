"""Fable-eye F15 (no model): an overview said "You still need to renew
library membership" when a later note records it done. One item has one
state: an open line that a later note records doing is not still to do in
an overview either (`composer_slots.recorded_later`, as the offer and the
slot readers already ask)."""

from __future__ import annotations

import datetime as dt

import pytest

from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

D = dt.datetime


@pytest.mark.parametrize("question", ["what have I saved about errands", "tell me about my errands", "errands", "what is still open in errands", "what is left to do in errands"])
@pytest.mark.parametrize(("task", "done"), [
    ("renew library membership", "Renewed my library membership at the desk."),
    ("renew library membership - due 28 October", "Renewed my library membership today."),
    ("book the dentist", "Booked the dentist for the 21st."),
    ("pay the water bill", "Paid the water bill online."),
])
def test_an_item_done_later_is_not_still_to_do(client, session, question, task, done):
    plan = manager.create_entry(session, f"# Errands\n\n- [ ] {task}.\n- [ ] buy stamps", category_name="Errands", tags=["errands"])
    plan.created_at = D(2026, 10, 1, 9)
    later = manager.create_entry(session, done, category_name="Errands", tags=["errands"])
    later.created_at = D(2026, 10, 10, 9)
    session.commit()
    said = _ask(client, question, use_tools=False, notes_only=True, answer_from="notes")["text"]
    thing = task.split(" - ")[0]
    assert f"need to {thing}" not in said.lower() and f"{thing} is still open" not in said.lower(), said
    assert "buy stamps" in said.lower(), said
