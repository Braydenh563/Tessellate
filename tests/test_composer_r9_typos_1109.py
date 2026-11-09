"""R9-14 (composer audit round 9): "no" for "know" after "do I" is repaired, and "pls" after a subject asks
for the subject's number. Seed: `tests/_seed_r9_1109.py`."""

from __future__ import annotations

import pytest

import tests._seed_r9_1109 as sd
from tessellate.ai import question_noise


@pytest.fixture
def say(client, session, monkeypatch):
    sd.seed(session)
    go = sd.asker(client, monkeypatch)
    return lambda q: go(q)[0]


@pytest.mark.parametrize(("typed", "fixed"), [
    ("what do i no about hanna", "what do i know about hanna"),
    ("what did I no about the garden", "what did I know about the garden"),
])
def test_no_for_know_is_repaired_after_do_i(typed, fixed):
    assert question_noise.repair(typed).lower() == fixed.lower()


def test_no_stays_no_elsewhere():
    assert question_noise.repair("do i have no notes about it").lower() == "do i have no notes about it"


def test_a_plumbers_number_with_pls_is_the_number(say):
    assert "07700 900789" in say("plumbers number pls")
