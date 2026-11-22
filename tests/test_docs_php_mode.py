"""PHP highlighting as a lazy file (L-documents-63): the grammar is 28 KB gzipped, so it is not in the editor bundle.

`@codemirror/lang-php` lives in `frontend/vendor/codemirror/php.min.js`, built by `build.sh` against the main
bundle's own `CM6` (lang-html, the Lezer runtime, language, state and highlight are all mapped onto it, so
nothing is bundled twice) and fetched by `docCmParts.loadPhp` the first time a .php document opens. The
real-browser check (token classes on a .php file, nothing fetched for a .py one) is
`scratchpad/ui-sweeps/php-lazy-l63.js`.
"""

from __future__ import annotations

import gzip
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests._help_text import help_chat_text
from tests._app_js import documents_text

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
VENDOR = ROOT / "frontend" / "vendor" / "codemirror"
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def test_the_php_package_is_pinned_and_built_into_its_own_file() -> None:
    pins = json.loads((VENDOR / "package.json").read_text(encoding="utf-8"))["dependencies"]
    assert pins["@codemirror/lang-php"] == "6.0.2" and pins["@lezer/php"] == "1.0.6"
    php = (VENDOR / "php.min.js").read_text(encoding="utf-8")
    assert php.startswith("/*! @codemirror/lang-php 6.0.2 and @lezer/php 1.0.6, MIT licence")
    assert "Object.assign(window.CM6,{php:" in php
    assert "php.min.js" in (VENDOR / "build.sh").read_text(encoding="utf-8")
    licence = (VENDOR / "LICENSE").read_text(encoding="utf-8")
    assert "@codemirror/lang-php 6.0.2" in licence and "@lezer/php 1.0.6" in licence


def test_the_main_bundle_holds_no_php_grammar_and_the_file_shares_its_runtime() -> None:
    main = (VENDOR / "codemirror.min.js").read_text(encoding="utf-8")
    assert "PhpOpen" not in main and "TextInterpolation" not in main, "the editor bundle must not carry PHP"
    php = (VENDOR / "php.min.js").read_text(encoding="utf-8")
    assert "PhpOpen" in php
    # lang-html, the Lezer runtime and the highlight tags come from the bundle, never a second copy.
    for part in ("html", "language", "highlight", "common", "lr"):
        assert f"window.CM6.{part}" in php, part
    assert len(gzip.compress(php.encode(), 9)) < 30_000
    assert INDEX.count("php.min.js") == 0, "fetched on demand, never at boot"


def test_the_boot_budget_does_not_see_the_editor_bundle_or_php() -> None:
    boot = (ROOT / "tests" / "test_boot_budget.py").read_text(encoding="utf-8")
    assert "codemirror" not in INDEX
    assert "php" not in boot.lower()


def test_php_is_fetched_on_first_open_and_a_failure_offers_try_again() -> None:
    docs = documents_text()
    load = docs[docs.index("async loadPhp()") : docs.index("async loadPhp()") + 700]
    assert '"/vendor/codemirror/php.min.js"' in load and "lazyScript(" in load
    assert '"Try again"' in load and "toast(" in load and "docCmApplied.delete(\"language\")" in load
    assert "docCmSyncLanguage()" in load
    assert 'case "php": return CM.php ? CM.php.php() : [];' in docs, "plain text until the file lands"
    view = (JS / "documents-view.js").read_text(encoding="utf-8")
    assert re.search(r'if \(ext === "php" && !CM\.php\) docCmParts\.loadPhp\(\);', view)


@needs_node
def test_the_php_file_parses_php_in_html_into_a_tree_with_a_php_node() -> None:
    script = f"""
const fs = require("fs"), vm = require("vm");
const ctx = {{ console }}; ctx.window = ctx; vm.createContext(ctx);
const read = (f) => fs.readFileSync({json.dumps(str(VENDOR))} + "/" + f, "utf8");
vm.runInContext(read("codemirror.min.js") + ";globalThis.CM6 = CM6;", ctx);
const before = typeof ctx.CM6.php;
vm.runInContext(read("php.min.js"), ctx);
const out = vm.runInContext(`(() => {{
  const names = (doc) => {{
    const s = CM6.state.EditorState.create({{ doc, extensions: [CM6.php.php()] }});
    const found = new Set(), tree = CM6.language.syntaxTree(s);
    tree.iterate({{ enter: (n) => {{ found.add(n.name); }} }});
    let classes = 0;
    CM6.highlight.highlightTree(tree, CM6.language.defaultHighlightStyle, () => {{ classes += 1; }});
    return {{ names: [...found], classes }};
  }};
  return JSON.stringify({{ plain: names("<?php echo 1; ?>"), mixed: names("<p>hi</p><?php echo 1; ?>") }});
}})()`, ctx);
console.log(JSON.stringify({{ before, php: typeof ctx.CM6.php.php, out: JSON.parse(out) }}));
"""
    got = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    assert got["before"] == "undefined" and got["php"] == "function"
    plain, mixed = got["out"]["plain"], got["out"]["mixed"]
    assert {"PhpOpen", "EchoStatement", "Integer", "PhpClose"} <= set(plain["names"])
    assert plain["classes"] >= 3
    # PHP inside HTML: the HTML parse is the main bundle's own, so a tree built from both highlights without error.
    assert "PhpOpen" in mixed["names"] and "Text" in mixed["names"] and mixed["classes"] >= 3


def test_help_names_the_lazy_php_colours() -> None:
    text = help_chat_text()
    assert "PHP loads on first open" in text
