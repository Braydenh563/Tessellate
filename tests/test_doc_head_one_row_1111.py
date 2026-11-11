"""The Documents sidebar's Recent head holds one row at 220 to 320px (the owner, 2026-11-11:
"these elements have wrapped to a new row"). Measured at 260 before: head 58 px tall, 97 px at 220.
The tools no longer wrap; narrow sidebars shed the New word, then fold help, template and diagram
into the head's own kebab. The pixel numbers are checked by driving the app; these pin the parts."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAZY = (ROOT / "frontend/css/library-lazy.css").read_text()
DOCK = (ROOT / "frontend/css/04-chat-dock-appearance.css").read_text()
DOCS_JS = (ROOT / "frontend/js/documents.js").read_text()
HTML = (ROOT / "frontend/index.html").read_text()


def test_the_head_and_its_tools_do_not_wrap():
    head = LAZY.split("#doc-sidebar-list > .sidebar-head {", 2)[2].split("}", 1)[0]
    assert "flex-wrap: nowrap" in head
    tools = LAZY.split("#doc-sidebar-list > .sidebar-head > .row {", 2)[2].split("}", 1)[0]
    assert "flex-wrap: nowrap" in tools and "flex-wrap: wrap" not in tools


def test_the_tools_group_is_marked_in_the_markup():
    assert 'class="row doc-head-tools"' in HTML


def test_a_narrow_sidebar_sheds_the_word_then_folds_the_icons_into_a_kebab():
    assert "container: doc-sidebar / inline-size" in DOCK
    fold = DOCK.split("@container doc-sidebar (max-width: 16rem)", 1)[1].split("\n}\n", 1)[0]
    assert ".toolbar-word" in fold
    assert "#doc-new-template" in fold and "#doc-new-diagram" in fold and ".doc-head-more" in fold
    assert ".doc-sidebar .doc-head-more {\n  display: none;" in DOCK


def test_the_kebab_presses_the_real_buttons_and_is_built_in_js():
    body = DOCS_JS.split("function docTypeMount()", 1)[1].split("\n}\n", 1)[0]
    for target in ("graph-help-toggle", "#doc-new-template", "#doc-new-diagram"):
        assert target in body
    assert "kebabMenu(" in body
    assert "doc-head-more" not in HTML  # the boot document is element-capped


def test_the_help_says_where_the_buttons_went():
    assert "sit in the More menu (three dots) beside New" in HTML


def test_the_outline_heads_help_ends_the_row_and_is_not_clipped_at_the_top():
    rule = DOCK.split("#doc-sidebar-outline > .sidebar-head {", 1)[1].split("}", 1)[0]
    assert "padding-right: 0" in rule
    assert "margin-top: var(--ring-room)" in rule
