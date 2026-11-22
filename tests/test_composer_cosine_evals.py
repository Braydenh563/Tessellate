"""The composer's cosine lines measured on the real embedder (L-chat-63, CHAT_PLAN
decision 19).

Decision 19 set SAME_COSINE and TOPIC_COSINE by reasoning; this measures them
with bge-small (the default embedder) over hand-labelled pairs written in the
showcase notebook's subjects, and reads the spread of every pair the composer
compares on the 25-question showcase eval. Runs only with
`TESSELLATE_EVALS_EMBED=1` and fastembed installed (it downloads the 67 MB
model once), the same opt-in seam as the model evals: CI never fetches it. Measured 2026-11-14: one claim 0.904 to 0.991, one subject 0.433 to
0.813, apart 0.346 to 0.538; the showcase's compared pairs 0.429 to 0.746.
"""

from __future__ import annotations

import math
import os

import pytest

from tessellate.ai import composer, composer_select

pytestmark = [
    pytest.mark.evals,
    pytest.mark.skipif(not os.environ.get("TESSELLATE_EVALS_EMBED"), reason="export TESSELLATE_EVALS_EMBED=1 to run"),
]
fastembed = pytest.importorskip("fastembed")

SAME = [  # one claim, said twice
 ("The launch is on the 14th.", "We launch on the 14th."),
 ("Harbor ships to the public on the 14th of next month.", "The public release of Harbor is the 14th next month."),
 ("The boiler pressure keeps dropping to 0.8.", "Boiler pressure keeps falling to 0.8."),
 ("Take a gel every 40 minutes after the first hour.", "A gel every 40 minutes past the first hour."),
 ("Beta testers did not know Harbor works offline.", "The beta testers didn't realise Harbor works offline."),
 ("Lisbon to Porto on the Alfa Pendular takes 2h50.", "The Alfa Pendular from Lisbon to Porto is 2h50."),
 ("Foam roll the IT band after every long run.", "After each long run, foam roll the IT band."),
 ("The old pair of shoes has 700 km on it.", "My old shoes have done 700 km."),
 ("Cut sign-up from nine fields to four.", "Reduce the sign-up form from nine fields to four."),
 ("The engineer said the valve was worn.", "Last time the engineer told me the valve was worn."),
 ("Tickets open 60 days ahead.", "Tickets go on sale 60 days in advance."),
 ("Offline mode is hard to find.", "It is hard to find offline mode."),
]
TOPIC = [  # same subject, different claims
 ("The launch is on the 14th.", "The launch email still needs a subject line."),
 ("Take a gel every 40 minutes after the first hour.", "Practise race fuelling in training, never new on race day."),
 ("Lisbon to Porto on the Alfa Pendular takes 2h50.", "Hire a car in Porto."),
 ("The boiler pressure keeps dropping to 0.8.", "The engineer said the valve was worn."),
 ("Beta testers did not know Harbor works offline.", "Three people in the beta asked for dark mode."),
 ("Foam roll the IT band after every long run.", "The long run grows by a kilometre a week."),
 ("Cut sign-up from nine fields to four.", "Draft screens are on the launch board."),
 ("Twelve weeks to the October race.", "Bib and pins the night before."),
 ("Loaf 6: 78% hydration, 20 hour cold proof.", "Feed the starter 1:5:5 at night."),
 ("Stay one night at a quinta near Pinhão.", "Out to Lisbon, back from Porto."),
 ("Designing Data-Intensive Applications covers replication.", "Leaderless replication and read repair."),
 ("Write a short post after each book.", "The bathtub example finally made it click."),
 ("Harbor gets two thirds of the team until launch week.", "The sync rewrite starts after launch."),
 ("Booked seats 14A and 14B.", "A light jacket for the evenings."),
]
APART = [  # different subjects in one notebook
 ("The launch is on the 14th.", "Foam roll the IT band after every long run."),
 ("Take a gel every 40 minutes after the first hour.", "Cut sign-up from nine fields to four."),
 ("Lisbon to Porto on the Alfa Pendular takes 2h50.", "The boiler pressure keeps dropping to 0.8."),
 ("Beta testers did not know Harbor works offline.", "Loaf 6: 78% hydration, 20 hour cold proof."),
 ("Twelve weeks to the October race.", "Leaderless replication and read repair."),
 ("Stay one night at a quinta near Pinhão.", "Crash reporting for the mobile app."),
 ("The engineer said the valve was worn.", "Write a short post after each book."),
 ("Feed the starter 1:5:5 at night.", "Draft screens are on the launch board."),
 ("A light jacket for the evenings.", "Harbor gets two thirds of the team until launch week."),
 ("The old pair of shoes has 700 km on it.", "Tickets open 60 days ahead."),
 ("Plug adapter.", "The bathtub example finally made it click."),
 ("Designing Data-Intensive Applications.", "Bib and pins the night before."),
 ("Booked seats 14A and 14B.", "Practise race fuelling in training."),
 ("Offline mode is hard to find.", "Hire a car in Porto."),
]


@pytest.fixture(scope="module")
def embed():
    model = fastembed.TextEmbedding("BAAI/bge-small-en-v1.5")
    return lambda texts: [list(v) for v in model.embed(list(texts))]


def _cos(embed, a: str, b: str) -> float:
    va, vb = embed([a, b])
    dot = sum(x * y for x, y in zip(va, vb))
    return dot / (math.sqrt(sum(x * x for x in va)) * math.sqrt(sum(y * y for y in vb)))


def test_one_claim_said_twice_is_above_the_same_line_and_nothing_else_is(embed):
    same = [_cos(embed, a, b) for a, b in SAME]
    other = [_cos(embed, a, b) for a, b in TOPIC + APART]
    assert min(same) >= composer_select.SAME_COSINE > max(other)


def test_the_topic_line_misreads_the_fewest_pairs(embed):
    topic = [_cos(embed, a, b) for a, b in TOPIC]
    apart = [_cos(embed, a, b) for a, b in APART]

    def misread(line: float) -> int:
        return sum(c < line for c in topic) + sum(c >= line for c in apart)

    best = min(misread(i / 1000) for i in range(300, 900))
    assert misread(composer_select.TOPIC_COSINE) == best
    assert best <= 4


def test_no_showcase_pair_reads_as_one_claim(embed):
    """The showcase notes say each thing once, so no pair the composer compares
    on its 25 questions may fold as a repeat."""
    from tests import _composer_eval as ev

    seen: list[float] = []
    original = composer_select._Meaning.cosine

    def record(self, a, b):  # noqa: ANN001, ANN202
        value = original(self, a, b)
        if value is not None and a.text != b.text:
            seen.append(value)
        return value

    data = ev.load()
    on = ev.today(data)
    composer_select._Meaning.cosine = record
    try:
        for entry in data["questions"]:
            recent = str(entry.get("search_mode") or "").endswith("recent")
            composer.compose(entry["question"], ev.notes_for(entry, data), today=on, embed=embed, recent=recent)
    finally:
        composer_select._Meaning.cosine = original
    assert seen
    assert max(seen) < composer_select.SAME_COSINE
