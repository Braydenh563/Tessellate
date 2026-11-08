"""Composer round 5, 2026-11-08 (R3-2): a person's phone number is never another note's."""

from __future__ import annotations

import time

import pytest

from tests import _r5_1108 as r5


@pytest.fixture
def ask(client, session, monkeypatch):
    return r5.driver(client, session, monkeypatch)


@pytest.mark.parametrize("question", ["what is Sara's phone number", "what is Sara's number", "does Sara have a phone number"])
def test_r3_2_a_person_with_no_number_is_denied_in_the_notebooks_name(ask, question):
    said = ask(question)["text"]
    assert said.startswith("None of your notes give a phone number for Sara."), said
    assert "020 7946" not in said, said


def test_r3_2_the_dentists_number_is_still_the_dentists(ask):
    assert "020 7946 0011" in ask("what is the number for the dentist")["text"]


def test_r3_2_the_has_phone_reader_is_linear():
    from tessellate.ai import composer_property

    t0 = time.perf_counter()
    for run in ("does " + "a " * 5000 + "have a", "do " + "x " * 5000, "does " + " " * 9000 + "have a phone"):
        composer_property.subject(run)
    assert time.perf_counter() - t0 < 1.0
