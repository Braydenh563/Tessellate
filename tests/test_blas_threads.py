"""L635: the search matrix products run on one BLAS thread unless the person says otherwise."""
import os
import subprocess
import sys


def _run(env_extra: dict) -> str:
    env = {k: v for k, v in os.environ.items() if k not in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS")}
    env.update(env_extra)
    env["PYTHONPATH"] = "src"
    code = "import tessellate, os; print(os.environ.get('OPENBLAS_NUM_THREADS'), os.environ.get('OMP_NUM_THREADS'))"
    return subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True).stdout.strip()


def test_blas_defaults_to_one_thread():
    assert _run({}) == "1 1"


def test_a_persons_own_value_wins():
    assert _run({"OPENBLAS_NUM_THREADS": "3"}) == "3 1"


def test_tag_reason_is_the_same_with_the_note_cleaned_once():
    """L-world-class-20: `_reasons_for` cleans and stems a note once, not once per tag."""
    from tessellate.ai import tagging
    from tessellate.api import routes_entries

    text = "Booked the dentist for a check-up on Tuesday and paid the invoice for the tax return."
    tags = ("dentist", "invoice", "tax", "garden")
    slow = tuple((tag, why) for tag in tags if (why := tagging.reason(tag, text)))
    assert routes_entries._reasons_for(text, tags) == slow
    assert slow, "the fixture must ground at least one tag"
