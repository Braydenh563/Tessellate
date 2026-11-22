"""L-world-class-22 (note templates): the variables a template fills and the
prompted `${Label}` fields, and that the help says so."""

from __future__ import annotations

from pathlib import Path

from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]


def _body(app: str, name: str) -> str:
    return app.split(name, 1)[1].split("\n}\n", 1)[0]


def test_a_template_fills_title_weekday_and_space():
    text = _body(app_js_text(), "function noteTemplateText(")
    for variable in ("{{weekday}}", "{{title}}", "{{space}}", "{{clipboard}}"):
        assert variable in text
    assert "entry-title" in text and "spacesCache.find(" in text


def test_a_field_is_asked_once_through_the_prompt_dialog_and_filled_everywhere():
    app = app_js_text()
    use = _body(app, "async function noteTemplateForUse(")
    assert "new Set(" in use and "raw.matchAll(" in use and "promptDialog(label" in use
    assert "if (!answer) return null" in use, "cancelling a field cancels the use"
    assert "replace(/\\$\\{([^}]+)\\}/g" in _body(app, "function noteTemplateText("), "every occurrence is filled"


def test_every_caller_of_a_template_stops_when_a_field_is_cancelled():
    for name in ("note-templates.js", "editor.js", "utility-tools.js"):
        text = (ROOT / "frontend" / "js" / name).read_text(encoding="utf-8")
        after = text.split("await noteTemplateForUse(template);", 1)[1][:60]
        assert "if (!filled) return;" in after, name


def test_the_help_names_the_new_variables_and_fields():
    source = (ROOT / "src" / "tessellate" / "ai" / "help_topics_more.py").read_text(encoding="utf-8")
    block = source.split('"id": "insert-template"', 1)[1][:1500]
    for word in ("{{weekday}}", "{{title}}", "{{space}}", "${Label}", "{{cursor}}"):
        assert word in block
    page = (ROOT / "frontend" / "surfaces" / "settings.html").read_text(encoding="utf-8")
    popover = page.split('id="templates-help"', 1)[1][:1800]
    for word in ("{{weekday}}", "{{space}}", "${Label}"):
        assert word in popover
