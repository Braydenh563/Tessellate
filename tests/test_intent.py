"""How the composer reads a question's shape (`composer.classify`).

The 2026-10-10 triage: the Gemini branch added "translate", "convert",
"utility", "summary", "math" and "reading_time" shapes ahead of the rest, and
the translate pattern matched any "to <word>", so "How long is the train from
Lisbon to Porto?" and "Who are we looking to hire?" were answered as requests
to translate. Those shapes are gone (a sum is `arithmetic`'s, before any
shape is read); this pins every showcase question (`tests/_composer_eval.py`)
to the shape main gave it, so a pattern added ahead of the others cannot
steal a question again without failing here.
"""

from __future__ import annotations

import pytest

from tessellate.ai import composer
from tessellate.ai import composer_ask

SHOWCASE = [
    ("What is the Harbor launch plan?", "what"),
    ("When is the dentist check-up?", "when"),
    ("Who asked for a public API?", "who"),
    ("How many beta testers are active?", "count"),
    ("Which books am I reading?", "list"),
    ("Compare Lisbon and Porto", "compare"),
    ("Why did the list feel slow?", "explain"),
    ("What is the latest on the sync rewrite?", "status"),
    ("Does Harbor work offline?", "yesno"),
    ("What hotel did I book in Porto?", "what"),
    ("What do I know about sourdough?", "what"),
    ("How long is the train from Lisbon to Porto?", "count"),
    ("When is the boiler service due?", "when"),
    ("What should I pack for Portugal?", "what"),
    ("How do I sharpen my knife?", "explain"),
    ("What are the launch risks?", "list"),
    ("Is the pricing page signed off?", "yesno"),
    ("What is my half marathon training plan?", "what"),
    ("How much will the trip cost?", "count"),
    ("What did I learn from Thinking in Systems?", "what"),
    ("Who are we looking to hire?", "who"),
    ("What do my notes say about running?", "what"),
    ("What is the status of the onboarding rewrite?", "status"),
    ("Which dinners take under 30 minutes?", "list"),
]


@pytest.mark.parametrize(("question", "shape"), SHOWCASE)
def test_every_showcase_question_keeps_its_shape(question, shape):
    assert composer.classify(question) == shape


@pytest.mark.parametrize(
    "question",
    [
        "How long is the train from Lisbon to Porto?",
        "Who are we looking to hire?",
        "What did I say to Maria?",
        "How do I get to the station?",
        "Did we move the launch to Friday?",
    ],
)
def test_a_to_in_a_question_is_never_a_translation(question):
    assert composer.classify(question) not in {"translate", "convert"}
    assert "translate" not in composer_ask.SHAPES
