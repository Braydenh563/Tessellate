"""Source text: the dashboard's note text is drawn in a browser (L-ui-modernisation-67;
measured with 35 widgets, none left showing `_x_`, `[ ]` or `[[x]]` literally).
These pin the three rules that measurement depended on."""

from tests._app_js import frontend_text


def _between(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i : text.index(end, i)]


def test_list_rows_render_underscore_emphasis_and_drop_task_marks():
    js = frontend_text("dashboard.js")
    rows = _between(js, 'textEl.className = "dash-list-text";', "li.appendChild(textEl);")
    assert rows.count("underscoreSyntax: true") == 2
    assert r"(?:\[[ xX]\]\s+)?" in rows


def test_rediscover_unwraps_wiki_links():
    js = frontend_text("dashboard.js")
    line = next(row for row in js.splitlines() if "renderMarkdown(text, truncateMarkdownSafe(" in row)
    assert r"\[\[" in line and '"$1"' in line
