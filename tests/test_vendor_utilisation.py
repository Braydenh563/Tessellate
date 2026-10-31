"""Every vendored library is used at least as much as it is today (Brief 75).

The owner, 2026-10-10: "make sure all the vendored repositories are made full
use of. I want maximum utility." `scratchpad/vendor_use.py` counts, per library
in docs/THIRD_PARTY.md, the exports or capabilities the vendored copy offers
against those the app's own code reaches. This test runs that same counting
(it imports the script) and ratchets each library's called count at the number
below, so a refactor can use a library less only on purpose: lower the number
in the same commit and say why. Raise it when a surface starts using more.

The counts are a lower bound (a name built at run time is not seen), which is
why the floor is a floor. The ranked unused capabilities are rows in the
surface plans under "Vendored capabilities to use, 2026-10-10 (Brief 75)".
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node reads the browser bundles' exports"
)

#: Called counts on 2026-10-10. Never lowered to make a change fit.
CALLED_FLOOR = {
    "codemirror": 102,
    "emmet": 10,
    #: 4 since ledger 1565: a selection formatted at its first line's indent.
    "jsbeautify": 4,
    #: Brief 69: `transform` with the typescript, jsx and imports passes.
    "sucrase": 4,
    #: Brief 69: the SQL runner in api/run_sandbox.py.
    "sqljs": 12,
    #: Brief 70: the JavaScript debugger's worker in api/run_sandbox.py.
    "jsinterpreter": 9,
    "harper": 17,
    "phosphor": 260,
    "wordlist": 2,
    #: Completions after `module.` and the hover card (documents-code.js).
    "pystdlib": 2,
    #: Every face shipped is declared by an @font-face (row 1595).
    "atkinson": 4,
    #: 26 since the Timeline strip's labels (timeline-ticks.js: scaleTime, timeFormat,
    #: timeDay, timeMonday, timeMonth, timeYear) and the Treemap layout (`treemap`,
    #: `treemapSquarify`; GRAPH_PLAN VC11). 22 since the SVG graph renderer was
    #: removed (audit 1029 row 60): its force simulation (`forceCenter`,
    #: `forceManyBody`) and its styling helpers went with it; the canvas graph
    #: lays out in its own worker.
    "d3": 22,
    #: 12 since the Dashboard sky draws on the canvas context (its colour parsing was
    #: 426 ms of 540 ms busy idle at 4x CPU); p5 keeps the sketch, noise and timing.
    "p5": 12,
    "flashtext": 2,
    "stencils": 7,
    "mammoth": 2,
    #: initialize, render and parse, in the diagram frame (mermaid-frame.js).
    "mermaid": 3,
    #: The Word-style equation field (math-field.js): the field, its font and sound
    #: paths, getValue, setValue, insert, executeCommand, the keyboard policy, menuItems.
    "mathlive": 10,
    "docx": 12,
    #: Brief 83: the Translate worker, a download extra (its WASM engine is not vendored).
    "translate": 11,
}


#: Libraries whose every counted capability is in use, each with why that is
#: real rather than a reader counting everything as called.
FULLY_USED = {
    "stencils": "every board-library set is offered in the shape library",
    "jsbeautify": "its three formatters and the selection are all reached from Format",
    "atkinson": "only the four faces the Readable font draws were vendored",
}


def _load_script():
    path = ROOT / "scratchpad" / "vendor_use.py"
    spec = importlib.util.spec_from_file_location("vendor_use", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["vendor_use"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script():
    return _load_script()


@pytest.fixture(scope="module")
def reports(script):
    return script.collect()


def test_each_library_is_used_at_least_as_much_as_today(reports) -> None:
    fell = {
        key: (len(reports[key].called), floor)
        for key, floor in CALLED_FLOOR.items()
        if len(reports[key].called) < floor
    }
    assert fell == {}, f"called count fell below its floor (now, floor): {fell}"


def test_every_report_has_a_floor_and_sane_counts(reports) -> None:
    assert set(reports) == set(CALLED_FLOOR), "a library was added or removed: give it a floor here"
    for key, report in reports.items():
        assert report.available, f"{key}: nothing counted as available, the reader is broken"
        assert set(report.called) <= set(report.available), (
            f"{key}: a called name is not an available one"
        )
        assert len(report.called) < len(report.available) or key in FULLY_USED, (
            f"{key}: nothing unused is suspicious"
        )


def test_every_library_in_third_party_is_reported(script, reports) -> None:
    missing = [
        name
        for name in script.third_party_libraries()
        if script.LIBRARY_KEYS.get(name) not in reports
    ]
    assert missing == [], (
        f"docs/THIRD_PARTY.md names a library the script does not count: {missing}"
    )


def test_the_printed_line_has_the_documented_shape(script, reports) -> None:
    for report in reports.values():
        line = script.format_report(report).splitlines()[0]
        assert f"available {len(report.available)}, called {len(report.called)}, unused:" in line
