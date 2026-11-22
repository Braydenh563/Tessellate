"""L544: the own-file link rule (a markdown link to `/media/` or `/files/`) has one home, att-chip.js."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]


def test_the_rule_is_written_once_and_both_readers_use_it():
    text = app_js_text()
    #: The link form, `](/media/...)`; a bare url test such as `^/(?:media|files)/` is another rule.
    assert len(re.findall(re.escape(r"\((\/(?:media|files)"), text)) == 1
    kit = (ROOT / "frontend/js/answer-kit.js").read_text(encoding="utf-8")
    assert "(?:media|files)" not in kit and "ownFileLinks(entry?.content)" in kit
    library = (ROOT / "frontend/js/library.js").read_text(encoding="utf-8")
    graph = (ROOT / "frontend/js/graph.js").read_text(encoding="utf-8")
    assert "ownFileLinks(content)" in library and "ownFileLinks(entry.content)" in graph


def test_own_file_links_reads_images_and_files_and_skips_the_web():
    script = (ROOT / "frontend/js/att-chip.js").read_text(encoding="utf-8")
    probe = "![A heron](/media/a.png) [scan](/files/12) ![web](https://x.test/b.png)"
    run = f"const window = globalThis;\n{script}\nconsole.log(JSON.stringify(ownFileLinks({json.dumps(probe)}).map((m) => m.slice(1))));"
    out = subprocess.run(["node", "-e", run], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == [["!", "A heron", "/media/a.png"], ["", "scan", "/files/12"]]
