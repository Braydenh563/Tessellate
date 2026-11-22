"""L603: Settings, About, Health shows the speed budgets (WORLD_CLASS_PLAN
decision 54) against this notebook, so a person can see whether their own
notebook is inside the times the app is held to. The row is built in
settings-health.js (lazy), not shipped in index.html, because the boot page
is at its element cap."""

from tests._app_js import frontend_text
from tessellate.ai import help_topics_more

JS = frontend_text("settings-health.js")


def test_row_is_built_after_integrity_and_not_in_boot_html():
    assert "function speedRow()" in JS
    assert 'id: "health-speed-run"' in JS
    assert 'id="health-speed' not in open("frontend/index.html", encoding="utf-8").read()


def test_check_reads_the_live_budgets_and_this_page_paint():
    body = JS[JS.index("function speedRow()"):]
    assert '"/models/bench/budgets?live=true"' in body
    #: The browser half: this page's own first paint against its cap.
    assert '"first-contentful-paint"' in body
    assert "cap_ms" in body and "server_cap_ms" in body and "live_within" in body


def test_copy_is_plain():
    body = JS[JS.index("function speedRow()"):JS.index("speedRow();")]
    assert "!" not in body.replace("!==", "").replace("!=", "").replace("(!", "").replace(" !", "")
    assert chr(0x2014) not in body


def test_guide_topic_names_the_row():
    topic = next(t for t in help_topics_more.MORE_TOPICS if t["id"] == "health")
    assert "Speed" in topic["body"]
    assert "speed" in topic["keywords"] and "slow" in topic["keywords"]
