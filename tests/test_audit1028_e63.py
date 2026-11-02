"""Audit 1028 E63: three or more clauses are a list, not a run-on."""

from __future__ import annotations


import pytest

from tessellate.entry import manager
from tests.test_composer_route_688 import _ask


def _said(client, question):
    return _ask(client, question, use_tools=False)["text"]


# --- E63: three or more clauses are a list, not a run-on -------------------------------


@pytest.fixture
def respiration(session):
    manager.create_entry(
        session,
        "# Cell respiration\n\nCellular respiration turns glucose into ATP.\n\n"
        "Glycolysis happens in the cytoplasm and makes 2 ATP; the Krebs cycle happens in the mitochondrial matrix and makes 2 ATP; "
        "the electron transport chain makes about 32 ATP at the inner membrane.",
        category_name="Uni",
    )
    session.commit()


@pytest.mark.parametrize("question", ["what do my notes say about cellular respiration", "what do I know about glycolysis", "what is the krebs cycle", "explain cell respiration"])
def test_a_sentence_of_three_clauses_is_told_as_a_list(client, respiration, question):
    said = _said(client, question)
    assert not any(line.count("; ") >= 2 for line in said.splitlines()), said
    items = [line for line in said.splitlines() if line.startswith("- ")]
    assert len(items) == 3, said
    assert any("Krebs cycle happens in the mitochondrial matrix" in i for i in items)


def test_a_sentence_of_two_clauses_stays_a_sentence(client, session):
    manager.create_entry(session, "# Plan\n\nThe alliance system made a local crisis into a continental war; Germany feared encirclement and Russia mobilised early.", category_name="Uni")
    session.commit()
    said = _said(client, "what do my notes say about the alliance system")
    assert "; Germany feared" in said and "\n- " not in said


