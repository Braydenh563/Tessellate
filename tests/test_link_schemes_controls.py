"""Link allowlists read the scheme as a browser does (audit 1028 D14 to D16).

A browser drops tabs, newlines and leading control characters from a URL,
so "java\\tscript:alert(1)" runs as javascript:. safeHref tested the raw
string and let it through as "no scheme"; docOpenLink was a blocklist on
the raw string. Rich paste put a clipboard address into `[..](..)` as is, so
a ")" ended the link early.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"


def _function(source: str, head: str) -> str:
    start = source.index(head)
    return source[start : source.index("\n}\n", start) + 3]


needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


@needs_node
@pytest.mark.parametrize("url", ["java\tscript:alert(1)", "java\nscript:alert(1)", "\u0001javascript:alert(1)",
                                 " JAVASCRIPT:alert(1)", "data:text/html,x", "vbscript:x"])
def test_a_hidden_script_scheme_is_refused(url):
    safe = _function((JS / "notes-list.js").read_text(encoding="utf-8"), "function safeHref(")
    out = subprocess.run(["node", "-e", safe + f"\nconsole.log(safeHref({json.dumps(url)}))"],
                         capture_output=True, text=True, timeout=30, check=True)
    assert out.stdout.strip() == "#"


@needs_node
@pytest.mark.parametrize("url", ["https://example.com/a b", "/media/x.png", "#top", "notes/x", "mailto:a@b.c"])
def test_ordinary_links_pass(url):
    safe = _function((JS / "notes-list.js").read_text(encoding="utf-8"), "function safeHref(")
    out = subprocess.run(["node", "-e", safe + f"\nconsole.log(safeHref({json.dumps(url)}))"],
                         capture_output=True, text=True, timeout=30, check=True)
    assert out.stdout.strip() == url


def test_open_link_uses_the_allowlist():
    body = _function((JS / "documents.js").read_text(encoding="utf-8"), "function docOpenLink(")
    assert 'safeHref(clean) === "#"' in body


def test_pasted_addresses_are_encoded_into_markdown():
    source = (JS / "documents.js").read_text(encoding="utf-8")
    assert "value.replace(/[\\s()<>]/g, (c) => encodeURIComponent(c))" in source
