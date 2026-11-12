"""`[[Target|Shown]]` in the page: the target finds the note, the shown words draw.

The server reads the part before the first `|` as the target
(`tests/test_wiki_links_alias.py`). The page did not: a note card drew the
whole `Target|Shown` as the chip's words, and clicking it looked for a note
that opens with the whole string, found none and offered to create a note by
that name. Found by `scratchpad/ui-sweeps/deepflows.js` (the link flow: a note
holding `[[Link flow B|the second one]]` drew "Link flow B|the second one").

Board references (`board:12|House jobs`) use the bar for the board's title and
are read by `boardEmbedRef`; they must come through untouched.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest
from tests._app_js import app_js_text

pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _function(name: str) -> str:
    source = app_js_text()
    match = re.search(rf"^function {name}\(.*?^\}}", source, re.S | re.M)
    assert match, f"{name} is gone"
    return match.group(0)


def _constant(name: str) -> str:
    match = re.search(rf"^const {name} = .*?;$", app_js_text(), re.S | re.M)
    assert match, f"{name} is gone"
    return match.group(0)


PRELUDE = "\n".join(
    [_constant("BOARD_REF_PATTERN"), _function("boardEmbedRef"), _function("wikiLinkTarget"), _function("wikiLinkShown")]
)


def _run(body: str) -> object:
    script = f"""
{PRELUDE}
{_function("wikiLinkLabel")}
const notePreviewText = (t) => String(t).replace(/^#+\\s*/, '');
process.stdout.write(JSON.stringify({body}));
"""
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@pytest.mark.parametrize(
    ("raw", "target", "shown"),
    [
        ("Eta reading|a friendly alias", "Eta reading", "a friendly alias"),
        ("Eta reading", "Eta reading", "Eta reading"),
        ("Eta reading|", "Eta reading", "Eta reading"),
        ("  Eta reading | shown  ", "Eta reading", "shown"),
        ("# Girl with bell|the girl", "# Girl with bell", "the girl"),
        ("a|b|c", "a", "b|c"),
    ],
)
def test_the_target_is_before_the_first_bar_and_the_rest_is_shown(raw, target, shown):
    got = _run(f"[wikiLinkTarget({json.dumps(raw)}), wikiLinkShown({json.dumps(raw)})]")
    assert got == [target, shown]


@pytest.mark.parametrize("raw", ["board:12|House jobs", "map : 4 | Tea"])
def test_a_board_reference_is_left_alone(raw):
    assert _run(f"[wikiLinkTarget({json.dumps(raw)}), wikiLinkShown({json.dumps(raw)})]") == [raw, raw]


def test_a_label_draws_the_shown_words():
    assert _run('wikiLinkLabel("Eta reading|a friendly alias")') == "a friendly alias"
    assert _run('wikiLinkLabel("# Girl with bell")') == "Girl with bell"


def test_an_empty_alias_draws_the_target():
    assert _run('wikiLinkLabel("Eta reading|")') == "Eta reading"


def test_resolving_an_alias_finds_the_note_named_before_the_bar():
    source = _function("resolveWikiTarget")
    script = f"""
{PRELUDE}
const allEntries = [
  {{ id: 1, content: 'Zeta recipes are here', is_private: false, is_board: false }},
  {{ id: 2, content: 'Eta reading list', is_private: false, is_board: false }},
];
const wikiStem = () => '';
const wikiForms = (e) => ({{ opening: e.content.toLowerCase(), title: '' }});
const mapBoardTitled = () => null;
const loadEmbedDocuments = () => {{}};
function boardEmbedTarget() {{ return null; }}
{source}
const hit = resolveWikiTarget('Eta reading|a friendly alias');
const miss = resolveWikiTarget('Nothing here|Eta reading');
process.stdout.write(JSON.stringify({{ hit: hit && hit.entry.id, miss }}));
"""
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    assert out == {"hit": 2, "miss": None}
