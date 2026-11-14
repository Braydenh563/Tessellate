"""The open-work scanner the plan sessions and the closing session clear (the
owner, 2026-11-12: "after these sessions are done, I should only be left with
the backlog and nothing else")."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import open_scan  # noqa: E402


def test_backlog_and_history_are_never_scanned():
    paths = open_scan.files()
    assert "docs/roadmap/BACKLOG.md" not in paths
    assert "docs/roadmap/HISTORY.md" not in paths
    assert "docs/roadmap/LEDGER.md" in paths


def test_the_signals_catch_open_work_and_pass_history():
    for line in ("- [ ] build the thing", "Still open: the screenshot set", "# TODO wire this", "not yet built",
                 "@pytest.mark.xfail(strict=True, reason='spec')", "deferred to a later PR"):
        assert open_scan.SIGNAL.search(line), line
    for line in ("- [x] built 2026-11-01", "The day strip was approved and built.", "def todo_lines(note):"):
        assert not open_scan.SIGNAL.search(line), line


def test_every_plan_session_owns_its_plan_file():
    for plan, owned in open_scan.OWNERS.items():
        assert any(o.startswith("docs/roadmap/") and o.endswith("_PLAN.md") for o in owned), plan
        assert all((ROOT / o).exists() or any(f.startswith(o) for f in open_scan.files()) for o in owned), plan


def test_a_reminders_default_text_is_copy_not_work():
    """The graph plan session, 2026-11-12: four surfaces prefill a reminder
    with the text `COPY` matches; that string is app copy and never a hit."""
    assert open_scan.COPY.search('textInput.value = `Follow up: ${preview}`;')
    assert not open_scan.COPY.search("follow up on the screenshot set next session")


def test_a_quoted_string_in_app_code_is_copy_and_a_comment_is_not(tmp_path, monkeypatch):
    """The documents plan, 2026-11-14: a checkbox's unticked label, a
    template's heading and the task callout, quoted in app code, are copy;
    the same words in a comment are still a hit (the cases below)."""
    js = tmp_path / "frontend" / "js" / "x.js"
    js.parent.mkdir(parents=True)
    js.write_text('box.setAttribute("aria-label", on ? "Done" : "Not done");\n// TODO wire this\n', encoding="utf-8")
    monkeypatch.setattr(open_scan, "ROOT", tmp_path)
    assert [i for _, i, _ in open_scan.hits(["frontend/js/x.js"])] == [2]


def test_single_quoted_and_template_js_literals_are_copy_but_a_comment_with_an_apostrophe_is_not(tmp_path, monkeypatch):
    """The owner's ruling on INBOX 1810: in code, text in quotes is copy. An
    apostrophe in a comment must not open a quote and hide the marker."""
    js = tmp_path / "frontend" / "js" / "y.js"
    js.parent.mkdir(parents=True)
    js.write_text(
        "toast('Still open: 3');\n"
        "const t = `## Still open\nnot done yet`;\n"
        "// it's a TODO the user's code needs\n"
        "/* don't ship: FIXME */\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(open_scan, "ROOT", tmp_path)
    assert [i for _, i, _ in open_scan.hits(["frontend/js/y.js"])] == [4, 5]


def test_a_python_literal_is_copy_and_a_docstring_comment_or_strict_xfail_is_not(tmp_path, monkeypatch):
    py = tmp_path / "src" / "m.py"
    py.parent.mkdir(parents=True)
    py.write_text(
        'def f():\n'
        '    """The export is not yet built."""\n'
        '    label = "Not done:"\n'
        '    return f"{label} still open"  # TODO trim\n'
        '\n'
        '@pytest.mark.xfail(reason="not built", strict=True)\n'
        'def test_x():\n'
        '    pass\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(open_scan, "ROOT", tmp_path)
    assert [i for _, i, _ in open_scan.hits(["src/m.py"])] == [2, 4, 6]
