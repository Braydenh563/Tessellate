"""One task checkbox, for the note editor and the document editor (INBOX 710).

Both mount the same CodeMirror live view and the same `DocTaskWidget`; the
note's edit form sits in an `.entry-list` row, whose generic tick rule drew
the box as a 28px slab while a document drew it native and 15px. These pin
the shape of the fix: one look in 09-editor.css, the list rule stepping
aside, and no bullet beside a task box.
"""

from pathlib import Path

from tests._app_js import documents_text

ROOT = Path(__file__).resolve().parents[1]
#: The editor's rules are in 09-editor.css and, for the ones only the Library
#: bundle draws, library-lazy.css (UI plan 13b, L459).
EDITOR_CSS = "\n".join((ROOT / "frontend/css" / n).read_text(encoding="utf-8") for n in ("09-editor.css", "library-lazy.css"))
MISC_CSS = (ROOT / "frontend/css/07-whiteboard-misc.css").read_text(encoding="utf-8")
DOCS_JS = documents_text()


def test_the_task_box_is_drawn_once_with_its_own_checked_state():
    rule = EDITOR_CSS.split(".cm-md-task-hit > .cm-md-task {")[1].split("}")[0]
    assert "appearance: none" in rule
    assert "width: 1.1em" in rule
    assert ".cm-md-task-hit > .cm-md-task:checked {" in EDITOR_CSS
    assert ".cm-md-task-hit > .cm-md-task:checked::after {" in EDITOR_CSS


def test_the_list_tick_rule_steps_aside_for_the_editors_box():
    generic = [line for line in MISC_CSS.splitlines() if "entry-list:not(#tool-list) input" in line]
    assert generic
    assert all(":not(:where(.cm-md-task))" in line for line in generic)


def test_a_task_line_hides_its_bullet_while_the_caret_is_elsewhere():
    block = DOCS_JS.split('if (name === "ListItem") {')[1].split('if (name === "Blockquote")')[0]
    assert "taskLead" in block
    assert "hidden.range(from, line.from + taskLead[0].length)" in block
