"""Acts that end somewhere, and copy with no arrows (audit 1031 AI21, AI22, HR16, Z9).

Read from the source, as the surrounding chat tests are: the rewrite bubble
names the act, an archived chat's row is gone before the toast says where it
went, Run waits for a skill, and no sentence a person reads writes a path as
an arrow.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from tests._app_js import frontend_text

SRC = Path(__file__).resolve().parents[1] / "src" / "tessellate"


def test_a_rewrite_bubble_names_the_act_not_the_first_question():
    js = frontend_text("chat.js")
    body = js[js.index("function rewriteAnswerWith(") :]
    body = body[: body.index("\n}\n")]
    assert "displayText: said" in body
    assert 'Make that shorter."' in js and 'Explain that more simply."' in js


def test_an_archived_chat_leaves_the_list_before_the_toast():
    for name in ("sheets-selects.js", "library.js"):
        js = frontend_text(name)
        block = js[js.index("/archive`, { method: \"PUT\" }") :]
        block = block[: block.index("makeMenuItem(\"ph:trash")]
        assert block.index("await loadConversationList()") < block.index('chatWriteRecord("chatArchiveUndo"'), name


def test_run_waits_for_a_chosen_skill():
    js = frontend_text("skills.js")
    assert "run.disabled = true;" in js and "run.disabled = !select.value;" in js


def _sentences(path: Path):
    """Every string constant in a file that is not a docstring."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docs = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(getattr(node.body[0], "value", None), ast.Constant)
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            yield node.lineno, node.value


def test_no_sentence_a_person_reads_writes_a_path_as_an_arrow():
    arrow = re.compile("→| -> ")
    offenders = []
    for name in ("ai/help_chat.py", "ai/help_topics_more.py", "api/routes_update.py", "__main__.py"):
        for line, text in _sentences(SRC / name):
            if arrow.search(text):
                offenders.append(f"{name}:{line}")
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "detail" and isinstance(node.value, ast.Constant):
                if isinstance(node.value.value, str) and arrow.search(node.value.value):
                    offenders.append(f"{path.relative_to(SRC)}:{node.value.lineno}")
    assert not offenders, offenders
