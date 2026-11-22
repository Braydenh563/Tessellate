"""A new test that reads source text says why behaviour cannot be asserted
(L-general-9). Reading a file's text checks what the code says, not what it
does, so it passes for code that never runs; when nothing else can check it,
the test's docstring says so. The count of those without one only falls."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Undocumented source-text tests on 2026-11-22. Lower it when you add a
#: docstring to one; never raise it: give the new test its reason instead.
BARE_CEILING = 3669


def _scanner():
    spec = importlib.util.spec_from_file_location("source_text_tests", ROOT / "scripts" / "source_text_tests.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_new_source_text_test_says_why_it_reads_the_source():
    total, bare = _scanner().scan(ROOT)
    assert total > len(bare) > 0, "the scan found nothing: its readers or the tests folder moved"
    assert len(bare) <= BARE_CEILING, (
        f"{len(bare) - BARE_CEILING} new test(s) read source text with no docstring saying why "
        "behaviour cannot be asserted; add one. Without one, for example: " + ", ".join(bare[-5:])
    )


def test_the_scan_counts_a_reader_call_and_a_constant_read_at_import(tmp_path):
    folder = tmp_path / "tests"
    folder.mkdir()
    (folder / "test_x.py").write_text(
        "from pathlib import Path\n"
        "TEXT = Path('a').read_text()\n"
        "def test_calls():\n    Path('b').read_text()\n"
        "def test_constant():\n    assert TEXT\n"
        "def test_says_why():\n    '''No browser here.'''\n    Path('c').read_text()\n"
        "def test_behaviour():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )
    total, bare = _scanner().scan(tmp_path)
    assert total == 3
    assert bare == ["test_x.py::test_calls", "test_x.py::test_constant"]


def test_the_gate_prints_the_count():
    """The gate is bash; whether it prints is a line in it, not a call to make."""
    gate = (ROOT / "scripts" / "gate.sh").read_text(encoding="utf-8")
    assert "scripts/source_text_tests.py" in gate
