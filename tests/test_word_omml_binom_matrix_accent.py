"""Source text: the behaviour is front-end script that pytest cannot run without a browser, so these pin the code's text.

L324 and L325: a binomial, a matrix and an accent are Word maths objects.

`docWordBlob.math` walks the renderer's MathML into docx's maths parts. The
walk is run under node with the vendored docx over a small stand-in for the
MathML tree (the DOM walk in Chromium is the renderer's own output); the
file is written and its `word/document.xml` read for the `m:` elements.
"""

from __future__ import annotations

import base64
import re
import shutil
import subprocess
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from tests import _js_scope

ROOT = Path(__file__).resolve().parents[1]
WORD = ROOT / "frontend" / "js" / "documents-word.js"
DOCX = ROOT / "frontend" / "vendor" / "docx" / "docx.min.js"


def _xml(tree: str) -> str:
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    word = _js_scope.unwrapped(WORD.read_text(encoding="utf-8"))
    start = word.index("docWordBlob.math = ")
    code = word[start : word.index("async function docWordExport", start)]
    script = f"""
const vm = require('vm'), fs = require('fs');
const c = {{ console, setTimeout, clearTimeout, TextEncoder, TextDecoder, URL, Blob, Uint8Array, ArrayBuffer }};
c.window = c; c.self = c; c.globalThis = c; vm.createContext(c);
vm.runInContext(fs.readFileSync({str(DOCX)!r}, 'utf8') + ';this.docx=docx', c);
const D = c.docx;
const docWordBlob = {{}};
const el = (localName, kids = [], attrs = {{}}) => {{
  const node = {{ localName, attrs, children: typeof kids === 'string' ? [] : kids, text: typeof kids === 'string' ? kids : '' }};
  Object.defineProperty(node, 'textContent', {{ get: () => node.text + node.children.map((k) => k.textContent).join('') }});
  node.getAttribute = (n) => (n in attrs ? attrs[n] : null);
  return node;
}};
{code}
(async () => {{
  const math = docWordBlob.math(D, {tree});
  const doc = new D.Document({{ sections: [{{ children: [new D.Paragraph({{ children: [math] }})] }}] }});
  process.stdout.write(await D.Packer.toBase64String(doc));
}})();
"""
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 0, done.stderr[-600:]
    return zipfile.ZipFile(BytesIO(base64.b64decode(done.stdout))).read("word/document.xml").decode("utf-8")


def _fence(open_: str, inner: str, close: str) -> str:
    return f"el('mrow', [el('mo', {open_!r}), {inner}, el('mo', {close!r})])"


def test_a_binomial_is_a_bracketed_fraction_without_a_bar() -> None:
    frac = "el('mfrac', [el('mi', 'n'), el('mi', 'k')], { linethickness: '0' })"
    xml = _xml(f"el('math', [{_fence('(', frac, ')')}])")
    assert '<m:type m:val="noBar"/>' in xml
    assert "<m:d>" in xml and "<m:f>" in xml
    assert xml.count("<m:t>(</m:t>") == 0, "the brackets are the object's, not text"


def test_a_plain_fraction_keeps_its_bar() -> None:
    xml = _xml("el('math', [el('mfrac', [el('mi', 'a'), el('mi', 'b')])])")
    assert "<m:f>" in xml and "noBar" not in xml


def test_a_matrix_is_an_omml_matrix_with_its_rows_and_cells() -> None:
    cell = lambda t: f"el('mtd', [el('mi', {t!r})])"  # noqa: E731
    table = f"el('mtable', [el('mtr', [{cell('a')}, {cell('b')}]), el('mtr', [{cell('c')}, {cell('d')}])])"
    xml = _xml(f"el('math', [{_fence('[', table, ']')}])")
    assert "<m:m>" in xml
    assert xml.count("<m:mr>") == 2
    assert len(re.findall(r"<m:mr>.*?</m:mr>", xml, re.S)[0].split("<m:e>")) == 3, "two cells in the first row"
    assert '<m:begChr m:val="["/>' in xml or "<m:d>" in xml
    for letter in "abcd":
        assert f"<m:t>{letter}</m:t>" in xml


def test_a_bare_matrix_has_no_brackets() -> None:
    table = "el('mtable', [el('mtr', [el('mtd', [el('mi', 'x')])])])"
    xml = _xml(f"el('math', [{table}])")
    assert "<m:m>" in xml and "<m:d>" not in xml


def test_an_accent_is_an_omml_accent_over_its_base() -> None:
    xml = _xml("el('math', [el('mover', [el('mi', 'x'), el('mo', '\\u02c6')], { accent: 'true' })])")
    assert "<m:acc>" in xml
    assert '<m:chr m:val="ˆ"/>' in xml
    assert "<m:t>x</m:t>" in xml


def test_a_big_operator_is_still_an_object_not_an_accent() -> None:
    xml = _xml("el('math', [el('munderover', [el('mo', '\\u2211'), el('mi', 'i'), el('mi', 'n')]), el('mi', 'k')])")
    assert "<m:nary>" in xml and "<m:acc>" not in xml
