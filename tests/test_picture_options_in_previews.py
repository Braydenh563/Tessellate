"""A picture's options are not words (UX review 1031, item 8).

`![A river|300|right](/media/x.png)` keeps its width and alignment in the alt
text. Every preview that reduces a note to plain words must drop them: the
Library card read "A river 300 right after", the Timeline row "A river|center
after", and the desktop companion's search showed the whole markdown.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest
from tessellate.entry.manager import strip_inline_markdown
from tests._app_js import JS_DIR, app_js_text


def test_the_server_preview_drops_a_pictures_width_and_alignment():
    assert strip_inline_markdown("![A river|300|right](/media/x.png) after") == "A river after"
    assert strip_inline_markdown("![A river|center](/media/x.png)") == "A river"
    assert strip_inline_markdown("![A river|300x200](/media/x.png)") == "A river"
    # a caption written after the options is what the picture is captioned
    assert strip_inline_markdown("![A river|The bend|400](/media/x.png)") == "The bend"
    # a plain picture and a link are unchanged
    assert strip_inline_markdown("![A river](/media/x.png) [a|b](http://x)") == "A river a|b"


def _node(script: str) -> str:
    return subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_client_previews_drop_them_too():
    source = app_js_text()
    strip = re.search(r"^function stripMarkdownPreview\(text\) \{.*?^\}", source, re.S | re.M).group(0)
    flat = re.search(r"^function flattenNoteMarkdown\(md\) \{.*?^\}", source, re.S | re.M).group(0)
    script = (
        "function stripFrontmatter(t){return t}\n" + strip + "\n" + flat
        + "\nprocess.stdout.write(JSON.stringify(["
        + "stripMarkdownPreview('![A river|center](/media/x.png) after'),"
        + "flattenNoteMarkdown('![A river|300|right](/media/x.png) after')]))"
    )
    assert json.loads(_node(script)) == ["A river after", "A river after"]


def test_the_companion_search_snippet_is_plain_words():
    desk = (JS_DIR / "desk-companion.js").read_text(encoding="utf-8")
    plain = desk[desk.index("const plain = ") :][:300]
    assert "\\]\\(" in plain  # a markdown picture or link is reduced to its text
