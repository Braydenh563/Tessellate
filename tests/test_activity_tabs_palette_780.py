"""L-world-class-780: the Activity panel's Agent runs and History tabs each have a palette row (rule 2, three clicks)."""

from tests._app_js import frontend_text


def test_each_activity_tab_has_its_own_palette_row():
    js = frontend_text("app-features.js")
    for label, tab in (("Activity", "running"), ("Agent runs", "runs"), ("Activity history", "history")):
        line = next(row for row in js.splitlines() if f" {label}\", " in row and "openActivity(" in row)
        assert f'openActivity("{tab}")' in line, label
