"""Audit 1031 class 50 (DC4, DC6, DC9): the document editor's three loose ends.

DC4: Replace in every document keeps the open document's change on the
editor's undo stack, and asks (a second press of the button) when more than
one document changes. DC6: an AI answer under a fifth of the text it replaces
is asked about first. DC9: the word goal's own limits are reported, not
ignored."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _docs() -> str:
    from tests._app_js import documents_text

    return documents_text()


def test_a_replace_across_documents_stays_on_the_undo_stack():
    text = _docs()
    out = text.split("function docWriteOutsideHistory(text, keep = false)", 1)[1].split("\n}\n", 1)[0]
    assert "addToHistory.of(keep)" in out
    assert "function docShowSaved(saved, keep = false)" in text
    assert "docWriteOutsideHistory(saved.content || \"\", keep);" in text
    write = text.split("async function docWriteContents(items, hashes, keep = false)", 1)[1].split("\n}\n", 1)[0]
    assert "docShowSaved(await apiJson(`/documents/${open.id}`), keep)" in write
    run = text.split("async function runDocReplace()", 1)[1].split("\n}\n", 1)[0]
    # The first write keeps the history; the toast's undo and redo write as before.
    assert "await docWriteContents(after, hashes, true);" in run
    assert "() => docWriteContents(before, hashes)," in run


def test_more_than_one_document_changing_asks_on_the_button():
    run = _docs().split("async function runDocReplace()", 1)[1].split("\n}\n", 1)[0]
    ask = run.index('run.dataset.armed !== "1"')
    assert ask < run.index("await docWriteContents(after, hashes, true);")
    assert "after.length > 1" in run
    # A confirm dialog opens behind a modal one, so the ask is on the button.
    assert "confirmDialog" not in run
    disarm = _docs().split("function docReplaceDisarm()", 1)[1].split("\n}\n", 1)[0]
    assert 'run.textContent = "Replace all";' in disarm and "run.dataset.was" in disarm
    # Any change to the find, the options or the ticks puts the label back.
    assert "docReplaceDisarm();" in _docs().split("async function renderDocReplace()", 1)[1].split("const pattern", 1)[0]
    assert "docReplaceDisarm();\n  });" in _docs()


def test_a_much_shorter_answer_is_asked_about():
    text = _docs()
    assert "const DOC_AI_SHORT_SHARE = 0.2;" in text and "const DOC_AI_SHORT_FROM = 200;" in text
    check = text.split("function docAiAnswerIsShort(verb, target, revised)", 1)[1].split("\n}\n", 1)[0]
    assert 'verb === "write"' in check and "target.length < DOC_AI_SHORT_FROM" in check
    accept = text.split("async function acceptDocAiEdit()", 1)[1].split("\n}\n", 1)[0]
    assert accept.index("docAiAnswerIsShort(") < accept.index("box.text = ")
    assert "Replace anyway?" in accept and 'confirmLabel: "Replace anyway"' in accept


def test_the_word_goal_reports_its_own_limits():
    text = _docs()
    submit = text.split('$("doc-word-goal-submit").addEventListener("click", () => {', 1)[1].split("\n});", 1)[0]
    assert submit.index("reportValidity()") < submit.index("setDocWordGoal(")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    field = html.split('id="doc-word-goal-input"', 1)[1].split(">", 1)[0]
    assert 'min="0"' in field and 'max="1000000"' in field


def test_the_guide_says_replace_all_asks_before_more_than_one_document():
    # Left out of documents-controls (1,893 of 1,900 characters) in 1031: it has a topic of its own now.
    from tessellate.ai import help_chat

    topics = {t["id"]: t["body"] for t in help_chat.HELP_TOPICS}
    assert "second" in topics["documents-replace"] and "Undo" in topics["documents-replace"]
    assert len(topics["documents-controls"]) < 1900
