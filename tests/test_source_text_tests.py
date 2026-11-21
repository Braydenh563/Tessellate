"""L-general-9: a test that reads file text says why in its docstring, and
the gate prints the counts and refuses a bare new one."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("source_text_tests", ROOT / "scripts" / "source_text_tests.py")
source_text_tests = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(source_text_tests)

SAMPLE = '''
from pathlib import Path
CSS = Path("x.css").read_text()

def helper():
    return Path("y.js").read_text()

def test_reads_through_a_constant():
    assert "a" in CSS

def test_reads_through_a_helper():
    """The rule is only in the stylesheet."""
    assert helper()

def test_runs_behaviour():
    assert 1 + 1 == 2
'''


def test_a_test_reading_text_directly_or_through_a_name_is_counted():
    total, reading, bare = source_text_tests.scan_file("test_x.py", SAMPLE)
    assert (total, reading) == (3, 2)
    assert bare == ["test_x.py::test_reads_through_a_constant"]


def test_the_gate_prints_the_counts_and_refuses_new_bare_ones():
    """The gate is a shell script; its wiring is only in its text."""
    gate = (ROOT / "scripts" / "gate.sh").read_text(encoding="utf-8")
    assert '"$PY" scripts/source_text_tests.py\n' in gate
    assert 'step source-text "$PY" scripts/source_text_tests.py --new' in gate
