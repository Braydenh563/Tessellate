"""The composer's own grammar, read by Harper (O4; BACKLOG INBOX 1299, the
owner: "can we use the vendored grammar repos like harper to improve
composer responses??", recommendation taken: "the vendored Harper rules run
over composer output as a test-time lint first").

Harper (frontend/vendor/harper, Apache-2.0) runs in node through
`scripts/harper_lint.mjs`. The corpus is the gold answers, the Guide's own
replies and the dated digest lines. Spelling, names and markdown are not the
composer's grammar (a quoted note keeps the person's words: "uni",
"Logitech"), so those rules are read as notes and the rest must be clean.
Measured 2026-10-17 on the gold answers before the reported-speech change:
no lint outside those rules.

Also here: a dated line reports what its note said then (B85: "A week on,
by 9 August, you mentioned that you had just recently begun playing League
of Legends").
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

from tessellate.ai import composer, composer_digest, guide_intent, help_chat

ROOT = Path(__file__).resolve().parents[1]
#: Not the composer's grammar: the person's words and names, markdown tables.
NOT_GRAMMAR = {"Spelling", "Capitalization", "Formatting", "Style", "WordChoice", "Typo", "Readability"}
_DAYS = re.compile(r"^(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|january|february|march|april|june|july|august|september|october|november|december)$")

GAMING = [
    {"id": 1, "content": "Gaming: bought a new headset for League of Legends", "created_at": "2026-08-02T10:00:00", "category": "Gaming", "tags": ["gaming"]},
    {"id": 2, "content": "Gaming: I just recently began playing League of Legends ranked with Sam", "created_at": "2026-08-09T10:00:00", "category": "Gaming", "tags": ["gaming"]},
    {"id": 3, "content": "Gaming: I've just started the new season and I'm stuck in silver", "created_at": "2026-08-30T10:00:00", "category": "Gaming", "tags": ["gaming"]},
]


def _digest(question: str) -> str:
    return composer_digest.answer(question, GAMING, today=date(2026, 10, 11))["text"]


def test_a_dated_line_reports_what_its_note_said_then():
    text = _digest("how is gaming going?")
    assert "by 9 August, you" in text and "that you had just recently begun playing League of Legends" in text, text
    assert "that you had started the new season and you were stuck in silver" in text, text
    #: A plain past is already the day's and stays as written.
    assert "On 2 August, you bought a new headset" in text, text
    assert "you have started" not in text and "you're stuck" not in text and "began playing" not in text


def test_the_reported_speech_has_eight_reporting_verbs_and_backshifts():
    assert len(set(composer_digest._REPORTS)) >= 8
    said = {composer_digest._reported("you're stuck in silver", i) for i in range(8)}
    assert len(said) == 8 and all(s.endswith("you were stuck in silver") for s in said), said
    assert composer_digest._reported("you think it's too small", 0).endswith("you thought it's too small")
    assert composer_digest._reported("you bought a headset", 0) == "you bought a headset"


def _corpus() -> list[str]:
    from tests.test_gold_answers import FIXTURE, _answer

    texts = [_answer(item)["text"] for item in FIXTURE["answers"]]
    texts += [_digest(q) for q in ("how is gaming going?", "what have I saved about gaming?")]
    for question, tab in (("what should I ask", "graph"), ("what should I ask", "notes"), ("What can Atlas change in my notebook?", "chat"),
                          ("How do I use the app??", "graph"), ("help", "graph")):
        texts.append(help_chat.offline_answer(question, tab)["content"])
    texts += list(guide_intent._HELP_LINES)
    texts += [composer.empty_window("last month", date(2026, 10, 1), date(2026, 10, 17), voice=v, seed=str(i)) for v in ("natural", "professional") for i in range(12)]
    return [re.sub(r"\*\*|\[([^\]]+)\]\([^)]+\)", lambda m: m.group(1) or "", t) for t in texts]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node for the vendored Harper")
def test_harper_finds_no_grammar_fault_in_the_composers_words():
    texts = _corpus()
    run = subprocess.run(["node", str(ROOT / "scripts" / "harper_lint.mjs"), "uk"], input=json.dumps(texts),
                         capture_output=True, text=True, timeout=110, cwd=ROOT, check=True)
    faults = []
    for text, lints in zip(texts, json.loads(run.stdout)):
        for lint in lints:
            day = lint["rule"] == "Capitalization" and _DAYS.match(lint["problem"])
            if lint["rule"] not in NOT_GRAMMAR or day:
                faults.append((lint["rule"], lint["problem"], lint["message"][:80], text[:120]))
    assert not faults, faults
