"""Comments stripped at serve time, and each asset stamped by its own bytes.

Audit 2026-10-05, FE-01 and FE-02 (`src/tessellate/api/asset_strip.py`,
`RevalidatedStatic` and `served_index_html` in `api/app.py`):

- 64% of the CSS, about 46% of the JS and 39% of `index.html` was comment
  text sent on every cold load. The files on disk keep it; only what is
  served loses it.
- A per-process boot token on every `?v=` made every launch a cold load (0
  of 49 assets from cache after a restart). Each URL now carries a hash of
  its file instead: an edited file is a new URL, an unchanged one is not.

The stripper is a scanner, not a regex, because a `//` line can sit inside a
template literal and a `/*` inside a string or a regex literal. The edge
cases are below; then every real script is stripped and handed to
`node --check`, and, where acorn is on the box, tokenized before and after
to prove the token streams are identical.
"""

from __future__ import annotations

import gzip
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate import __version__
from tessellate.api import app as app_module
from tessellate.api.app import FRONTEND_DIR, RevalidatedStatic, asset_hash
from tessellate.api.asset_strip import strip_css, strip_html, strip_js

# ------------------------------------------------------------ JS edge cases


def test_a_whole_line_comment_leaves_its_line_empty():
    """Emptied, not removed: an error's file:line names the same line in the
    served file as in the source."""
    assert strip_js("a();\n// note\n  //: more\nb();\n") == "a();\n\n\nb();\n"
    src = "a();\n/* one\n   two */\nb();\n"
    assert strip_js(src) == "a();\n\n\nb();\n"
    assert strip_js(src).count("\n") == src.count("\n")


def test_a_trailing_comment_goes_and_the_code_stays():
    assert strip_js("x = 1; // why\ny = 2;\n") == "x = 1;\ny = 2;\n"


def test_a_line_comment_inside_a_template_literal_is_text():
    src = "const t = `line\n// not a comment\n${a /* c */ + b}\n`;\n"
    assert strip_js(src) == "const t = `line\n// not a comment\n${a + b}\n`;\n"


def test_nested_template_substitutions_and_object_braces():
    src = "x = `a${ {k: `b${c}// in`}.k }// still text`; // gone\n"
    assert strip_js(src) == "x = `a${ {k: `b${c}// in`}.k }// still text`;\n"


def test_comment_markers_inside_strings_are_text():
    src = "s = \"/* no */\"; t = '// no'; u = \"\\\"// no\";\n"
    assert strip_js(src) == src


def test_regex_literals_are_not_comments_or_divisions():
    src = "a = /[/*]/.test(x);\nb = s.split(/\\/\\//);\nfunction f(){ return /\\/*x/g; }\n"
    assert strip_js(src) == src


def test_division_followed_by_a_comment():
    assert strip_js("q = a / b; // half\nr = (c) / 2 /* two */ / d;\n") == (
        "q = a / b;\nr = (c) / 2 / d;\n"
    )


def test_a_multi_line_comment_inside_code_keeps_a_line_break_for_asi():
    # `return /*\n*/ x` returns undefined: the comment is a line terminator.
    assert strip_js("function f(){ return /* a\nb */ x; }\n") == "function f(){ return \nx; }\n"


def test_licence_comments_are_kept():
    src = "/*! keep me */\n/* @license MIT */\n// drop\nx();\n"
    assert strip_js(src) == "/*! keep me */\n/* @license MIT */\n\nx();\n"


def test_tokens_are_never_joined():
    assert strip_js("a/**/b") == "a b"


# ------------------------------------------------- leading indentation


def test_js_loses_its_leading_indentation_and_keeps_every_line():
    src = "function f() {\n\tif (a) {\n    b();\n  }\n}\n  \nx = 1;\n"
    out = strip_js(src)
    assert out == "function f() {\nif (a) {\nb();\n}\n}\n\nx = 1;\n"
    assert out.count("\n") == src.count("\n")


def test_a_template_literal_keeps_its_indented_lines_byte_for_byte():
    src = "f(`a\n    b\n\t${x}\n  c`);\n  g();\n"
    assert strip_js(src) == "f(`a\n    b\n\t${x}\n  c`);\ng();\n"
    # Code inside a substitution is code again; text after its `}` is text.
    nested = "t = `a\n  ${ f(\n      x) }\n  tail ${ `n\n   m` }\n  end`;\n"
    assert strip_js(nested) == "t = `a\n  ${ f(\nx) }\n  tail ${ `n\n   m` }\n  end`;\n"


def test_a_string_continued_over_a_line_keeps_its_leading_spaces():
    src = "s = 'one \\\n    two';\n    t = \"a\\\n  b\";\n"
    assert strip_js(src) == "s = 'one \\\n    two';\nt = \"a\\\n  b\";\n"


def test_regexes_and_kept_comments_are_not_reindented():
    src = "  a = /  x[ ]\\/ y/g;\n    b = c / d;\n  /*! keep\n     this */\n"
    assert strip_js(src) == "a = /  x[ ]\\/ y/g;\nb = c / d;\n/*! keep\n     this */\n"


def test_a_slash_after_a_closing_bracket_that_might_open_a_regex_keeps_later_indents():
    """`if (x)\n /`/.test(y)` is a regex statement, but a `/` after `)` reads
    as division, so its backtick would open a template and the guess would
    strip real template text. Where a quote could be hiding in such a regex
    the rest of the file keeps its indentation; a plain division does not."""
    src = "if (x)\n   /`/.test(y);\n   z = `\n   a`;\n"
    assert strip_js(src) == "if (x)\n/`/.test(y);\n   z = `\n   a`;\n"
    block = "if (x) {}\n  /'/.test(y);\n  z = '\\\n  a';\n"
    assert strip_js(block) == "if (x) {}\n/'/.test(y);\n  z = '\\\n  a';\n"
    # Division with no quote between the slashes is certain: indents still go.
    assert strip_js("n = (a) / 2 / (b);\n  m();\n") == "n = (a) / 2 / (b);\nm();\n"
    mid = 'k = (a - b) / 100 + "." + (c) / 3;\n  m();\n'
    assert strip_js(mid) == 'k = (a - b) / 100 + "." + (c) / 3;\nm();\n'


def test_css_loses_its_leading_indentation_but_not_inside_strings_or_urls():
    src = (
        ".a {\n    color: red;\n\tmargin: 0;\n}\n"
        ".b::after {\n  content: \"x\\\n      y\";\n"
        "  background: url(data:image/svg+xml;utf8,<svg\n    />);\n}\n"
    )
    assert strip_css(src) == (
        ".a {\ncolor: red;\nmargin: 0;\n}\n"
        ".b::after {\ncontent: \"x\\\n      y\";\n"
        "background: url(data:image/svg+xml;utf8,<svg\n    />);\n}\n"
    )


def test_the_real_frontend_files_lose_their_indentation():
    js = (FRONTEND_DIR / "js" / "app.js").read_text(encoding="utf-8")
    css = (FRONTEND_DIR / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    assert re.search(r"^[ \t]+\S", js, re.M) and re.search(r"^[ \t]+\S", css, re.M)
    assert strip_js(js).count("\n") == js.count("\n")
    for out in (strip_js(js), strip_css(css)):
        # What is left at a line start is inside a template, a string or a kept comment.
        assert len(re.findall(r"^[ \t]+\S", out, re.M)) < 400


# ----------------------------------------------------------- CSS and HTML


def test_css_comments_go_and_strings_and_urls_stay():
    src = (
        "/* header */\n.a { content: \"/* x */\"; }\n"
        ".b { background: url(data:image/svg+xml;utf8,<svg/*x*/>); } /* tail */\n"
        ".c { margin: 1px/**/2px; }\n"
    )
    assert strip_css(src) == (
        '\n.a { content: "/* x */"; }\n'
        ".b { background: url(data:image/svg+xml;utf8,<svg/*x*/>); }\n"
        ".c { margin: 1px 2px; }\n"
    )


def test_css_comment_lines_leave_no_empty_lines_behind():
    """A stylesheet is never named by line in a stack trace, so the empty lines
    a stripped comment leaves are dropped (INBOX 776: 7 KB of the boot CSS)."""
    assert strip_css("/* a\n b */\n.a { x: 1; }\n\n\n/* c */\n.b { y: 2; }\n") == "\n.a { x: 1; }\n.b { y: 2; }\n"


def test_html_comments_go_but_not_inside_text_elements_or_attributes():
    #: A `<template>` is not on that list since INBOX 1501: Settings' body sits
    #: in one, and its content is markup like the rest of the page, so its
    #: comments go too (62 KB of the served page).
    src = (
        "<div>\n  <!-- a note -->\n  <p title=\"<!-- not -->\">a<!-- x -->b</p>\n"
        "<pre><!-- kept --></pre><textarea><!-- kept --></textarea>"
        "<template><!-- gone --><template><!-- gone --></template></template>"
        "<script src=\"/a.js\"></script><!-- gone --></div>\n"
    )
    assert strip_html(src) == (
        "<div>\n\n  <p title=\"<!-- not -->\">ab</p>\n"
        "<pre><!-- kept --></pre><textarea><!-- kept --></textarea>"
        "<template><template></template></template>"
        "<script src=\"/a.js\"></script></div>\n"
    )


# ------------------------------------------------- every real script, proven


def _stripped_scripts(tmp_path: Path) -> tuple[Path, Path]:
    before = tmp_path / "before"
    after = tmp_path / "after"
    before.mkdir()
    after.mkdir()
    for path in sorted((FRONTEND_DIR / "js").glob("*.js")):
        text = path.read_text(encoding="utf-8")
        (before / path.name).write_text(text, encoding="utf-8")
        (after / path.name).write_text(strip_js(text), encoding="utf-8")
    return before, after


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_every_stripped_script_still_parses(tmp_path):
    _, after = _stripped_scripts(tmp_path)
    failed = []
    for path in sorted(after.glob("*.js")):
        # harper-worker.js is a module (`import`); node checks it as one.
        target = path
        if re.search(r"^(import|export)\s", path.read_text(encoding="utf-8"), re.M):
            target = path.with_suffix(".mjs")
            path.rename(target)
        run = subprocess.run(
            ["node", "--check", str(target)], capture_output=True, text=True, timeout=60
        )
        if run.returncode:
            failed.append(f"{path.name}: {run.stderr.strip()[:300]}")
    assert not failed, failed


_ACORN_CANDIDATES = [
    os.environ.get("TESSELLATE_ACORN", ""),
    "/opt/node-tools/node_modules/acorn",
]

_TOKEN_SCRIPT = r"""
const acorn = require(process.argv[2]);
const fs = require("fs");
const [before, after] = process.argv.slice(3);
const toks = (src) => {
  for (const sourceType of ["script", "module"]) {
    try {
      const out = [];
      for (const t of acorn.tokenizer(src, { ecmaVersion: "latest", sourceType }))
        out.push(t.type.label + ":" + (t.value === undefined ? "" : String(t.value)));
      return out;
    } catch (e) { if (sourceType === "module") throw e; }
  }
};
const bad = [];
for (const name of fs.readdirSync(before)) {
  const a = toks(fs.readFileSync(before + "/" + name, "utf8"));
  const b = toks(fs.readFileSync(after + "/" + name, "utf8"));
  if (a.length !== b.length || a.some((t, i) => t !== b[i])) bad.push(name);
}
console.log(JSON.stringify(bad));
"""


def test_every_stripped_script_has_the_same_tokens(tmp_path):
    """The proof the stripper only removed comments: acorn's token stream for
    each file before and after is identical. Skipped where acorn is not on
    the box (it is a dev tool here, never a dependency of the app)."""
    acorn = next((c for c in _ACORN_CANDIDATES if c and Path(c).is_dir()), None)
    if acorn is None or shutil.which("node") is None:
        pytest.skip("acorn or node not available")
    before, after = _stripped_scripts(tmp_path)
    script = tmp_path / "tok.js"
    script.write_text(_TOKEN_SCRIPT, encoding="utf-8")
    run = subprocess.run(
        ["node", str(script), acorn, str(before), str(after)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert run.returncode == 0, run.stderr[-500:]
    assert json.loads(run.stdout.strip().splitlines()[-1]) == []


# ------------------------------------------------------------ as served


@pytest.fixture()
def cold(monkeypatch):
    monkeypatch.setattr(RevalidatedStatic, "_gzip_cache", {})


def _raw(client, url, **headers):
    with client.stream("GET", url, headers=headers) as response:
        return response, b"".join(response.iter_raw())


def test_scripts_and_stylesheets_are_served_stripped_and_disk_is_untouched(client, cold):
    on_disk = (FRONTEND_DIR / "js" / "app.js").read_bytes()
    response, raw = _raw(client, f"/js/app.js?v={__version__}", **{"Accept-Encoding": "gzip"})
    served = gzip.decompress(raw)
    assert served == strip_js(on_disk.decode()).encode()
    assert b"\n//:" not in served and len(served) < len(on_disk)
    assert (FRONTEND_DIR / "js" / "app.js").read_bytes() == on_disk
    # Without gzip: the same stripped bytes.
    response, raw = _raw(client, "/js/app.js", **{"Accept-Encoding": "identity"})
    assert raw == served and "content-encoding" not in response.headers
    css = (FRONTEND_DIR / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    response, raw = _raw(client, "/css/07-whiteboard-misc.css", **{"Accept-Encoding": "gzip"})
    assert gzip.decompress(raw) == strip_css(css).encode()


def test_vendored_files_are_served_as_they_are(client, cold):
    response, raw = _raw(client, "/vendor/d3.v7.min.js", **{"Accept-Encoding": "identity"})
    assert raw == (FRONTEND_DIR / "vendor" / "d3.v7.min.js").read_bytes()


def test_the_page_is_served_without_comments_and_stamped_by_content(client):
    html = client.get("/").text
    assert "<!--" not in html.split("<script", 1)[0]
    # Settings' body is in a template (INBOX 1501), and its comments go too.
    assert "<!--" not in html.split('id="settings-body-template"', 1)[1].split("</template>", 1)[0]
    stamp = asset_hash(FRONTEND_DIR / "js" / "app.js")
    assert f'/js/app.js?v={__version__}-{stamp}"' in html
    css_stamp = asset_hash(FRONTEND_DIR / "css" / "07-whiteboard-misc.css")
    assert f"/css/07-whiteboard-misc.css?v={__version__}-{css_stamp}" in html
    # The lazy scripts and the workers are in the page's stamp map.
    meta = html.split('<meta name="asset-stamps" content="', 1)[1].split('"', 1)[0]
    stamps = dict(pair.split("=", 1) for pair in meta.split(","))
    for name in ("graph-worker.js", "harper-worker.js", "library.js"):
        assert stamps[f"/js/{name}"] == f"{__version__}-{asset_hash(FRONTEND_DIR / 'js' / name)}"
    # A lazy bundle's stylesheet too: with app.js's stamp, an edit to it alone
    # was the same immutable URL, and the desktop window kept the old rules.
    lazy_css = stamps["/css/library-lazy.css"]
    assert lazy_css == f"{__version__}-{asset_hash(FRONTEND_DIR / 'css' / 'library-lazy.css')}"


def test_a_stamp_is_a_function_of_the_bytes_not_the_process(tmp_path, monkeypatch):
    """Two server processes agree on an unchanged file's stamp, so a relaunch
    keeps the cache; an edited file gets a new one, so it never serves stale."""
    path = tmp_path / "a.js"
    path.write_text("one();\n")
    first = asset_hash(path)
    monkeypatch.setattr(app_module, "_asset_hashes", {})  # a new process
    assert asset_hash(path) == first
    path.write_text("two();\n")
    os.utime(path, ns=(1, 2_000_000_000))
    assert asset_hash(path) != first
    assert asset_hash(tmp_path / "missing.js") is None


def test_an_edited_stylesheet_changes_the_page_without_a_restart(tmp_path, monkeypatch):
    """The stale-cache report the old per-launch token fixed stays fixed: an
    edited file is a new URL on the next page load, and the page's own cache
    of itself (`_index_cache`) is keyed on every stamp it hands out."""
    (tmp_path / "css").mkdir()
    (tmp_path / "js").mkdir()
    (tmp_path / "css" / "a.css").write_text(".a { color: red; }\n")
    (tmp_path / "js" / "app.js").write_text("go();\n")
    (tmp_path / "index.html").write_text(
        f'<html><head><!-- note --><link rel="stylesheet" href="/css/a.css?v={__version__}">'
        f'<script src="/js/app.js?v={__version__}"></script></head><body></body></html>\n'
    )
    monkeypatch.setattr(app_module, "FRONTEND_DIR", tmp_path)
    monkeypatch.setattr(app_module, "_index_cache", {})
    monkeypatch.setattr(app_module, "_asset_hashes", {})
    first = app_module.served_index_html().decode()
    assert "<!--" not in first
    assert f'href="/css/a.css?v={__version__}-{asset_hash(tmp_path / "css" / "a.css")}"' in first
    assert f'<meta name="asset-stamps" content="/js/app.js={__version__}-' in first
    (tmp_path / "css" / "a.css").write_text(".a { color: blue; }\n")
    os.utime(tmp_path / "css" / "a.css", ns=(1, 5_000_000_000))
    second = app_module.served_index_html().decode()
    assert second != first
    assert f'href="/css/a.css?v={__version__}-{asset_hash(tmp_path / "css" / "a.css")}"' in second
