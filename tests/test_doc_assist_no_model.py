"""The documents' assistants with no model (the owner, 2026-10-11: "should
the assistant features in the regular and code document editor be disabled
when the ai isnt available??"). DOCUMENTS_PLAN, Decisions made: visible but
disabled with the reason, never hidden; a question the tools can answer is
routed to them (CHAT_PLAN decision 75); code wording in a code document; all
of it back live when a model connects. Driven in Chromium by
`docs-sweeps/assist.js` (the agent's sweep) at 1440 and 390, model off and on.
"""

from __future__ import annotations

import json
import re

from tests._app_js import INDEX_HTML, JS_DIR
from tests.test_code_documents import _fn, _node
from tests import _js_scope

HTML = INDEX_HTML.read_text(encoding="utf-8")
KIT = _js_scope.unwrapped((JS_DIR / "documents-codekit.js").read_text(encoding="utf-8"))
EDITOR = (JS_DIR / "editor.js").read_text(encoding="utf-8")
STATUS = (JS_DIR / "status.js").read_text(encoding="utf-8")


def test_a_question_the_tools_answer_is_routed_to_them():
    routes = KIT[KIT.index("const DOC_ASSIST_ROUTES = ["): KIT.index("];", KIT.index("const DOC_ASSIST_ROUTES = [")) + 2]
    got = _node(routes + "\n" + _fn(KIT, "docAssistRouteTool"), json.dumps([
        "format this", "run the tests", "where is `total` used", "find usages of double",
        "fix the error", "list the functions", "run it", "what does this do",
    ]) + ".map(docAssistRouteTool)")
    assert [g and g["tool"] for g in got] == [
        "format_code", "run_tests", "find_usages", "find_usages", "quick_fix", "symbols", "run_file", None,
    ]
    assert got[2]["args"] == {"name": "total"} and got[3]["args"] == {"name": "double"}
    ask = _fn(KIT, "docAssistAsk")
    assert 'action === "ask" && docAssistModelOff()' in ask and "docAssistRouteTool(question)" in ask


def test_the_needs_a_model_line_is_the_offline_notice_with_its_settings_link():
    line = re.search(r'<div id="doc-assist-model-line"[^>]*>', HTML).group(0)
    assert 'data-offline-line="Needs a model' in line and "notice" in line
    #: Rendered by the status poll (`renderAiOfflineNotice`), which adds the
    #: "Connect a model in Settings" button and hides it with a model on.
    assert "doc-assist-model-line\").classList.toggle" not in KIT
    question = re.search(r'<input id="doc-assist-question"[^>]*>', HTML).group(0)
    assert "data-offline-placeholder=" in question


def test_the_gate_announces_a_change_and_swaps_placeholders():
    sync = _fn(STATUS, "syncModelGatedControls")
    assert "[data-offline-placeholder]" in sync
    assert 'new CustomEvent("mm-model-gate"' in sync
    assert 'document.addEventListener("mm-model-gate"' in EDITOR


def test_the_inline_bar_is_gated_and_speaks_code_in_a_code_document():
    scope = _fn(EDITOR, "inlineAiDescribeScope")
    assert "Explain, simplify, add types" in scope and "`${count} lines`" in scope and "you selected" in scope
    assert "Tighten this / fix the grammar" in scope
    sync = _fn(EDITOR, "inlineAiSyncModel")
    assert "readOnly" in sync and "needsModel" in sync and "modelOffer" in sync
    submit = _fn(EDITOR, "inlineAiSubmit")
    assert "aiIsOff()" in submit and "openModelOffer(" in submit
    #: The selection bar's rewrite button answers a press with the offer.
    assert re.search(r'action\.inlineAi[\s\S]{0,400}aria-disabled', EDITOR)


def test_the_document_assistant_field_is_gated_too():
    field = re.search(r'<input id="doc-ai-instruction"[^>]*>', HTML).group(0)
    assert "data-needs-model=" in field
    assert re.search(r'<div id="doc-ai-offline"[^>]*data-offline-line=', HTML)
