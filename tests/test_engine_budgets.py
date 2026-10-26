"""The engine's budgets (Brief 39): `import tessellate.ai.composer` cold under
0.2 s, `compose()` under 50 ms on the 20-note Phase 6 seed, no network."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

from tessellate.ai import composer

ROOT = Path(__file__).resolve().parents[1]
SEED = json.loads((ROOT / "tests" / "fixtures" / "composer" / "phase6_seed.json").read_text(encoding="utf-8"))
QUESTIONS = (
    "tell me about golf", "what did I do last week", "what is the Harbor launch plan", "when is the dentist",
    "what have I done for fitness", "what is 12 * 7", "which boards mention Harbor", "how to cook rice",
)


def test_the_composer_imports_cold_in_under_a_fifth_of_a_second():
    code = "import time; t = time.perf_counter(); import tessellate.ai.composer; print(time.perf_counter() - t)"
    #: Best of five: a cold import on a loaded machine is noisy, and the
    #: budget is about what the import does, not about the machine's worst moment.
    best = min(
        float(subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT,
                             env={"PYTHONPATH": str(ROOT / "src")}, check=True).stdout)
        for _ in range(5)
    )
    assert best < 0.2, best


def test_an_answer_over_twenty_notes_takes_under_fifty_milliseconds():
    today = date.fromisoformat(SEED["today"])
    composer.compose("warm up", SEED["notes"], today=today)
    worst = 0.0
    for question in QUESTIONS:
        #: Best of three per question, for the same reason as the import's.
        best = 1.0
        for _ in range(3):
            started = time.perf_counter()
            composer.compose(question, SEED["notes"], today=today)
            best = min(best, time.perf_counter() - started)
        worst = max(worst, best)
    assert worst < 0.05, worst


def test_the_largest_alternations_compile_on_first_use_not_at_import():
    #: `_window_words` was 15 ms and `_discourse` 4 ms of the cold import
    #: (measured, 2026-10-26), which put 3.13 CI at 0.215 s against the budget.
    code = (
        "import tessellate.ai.composer as c, tessellate.ai.recognise as r;"
        "print(r._WINDOW_WORDS is None, c._discourse.cache_info().currsize)"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT,
                         env={"PYTHONPATH": str(ROOT / "src")}, check=True).stdout.split()
    assert out == ["True", "0"]
