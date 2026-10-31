"""A stylesheet that is not linked at boot is loaded by a lazy bundle.

The boot stylesheets are held under a gzipped budget (test_boot_budget.py).
Styles that only a lazy bundle's surfaces draw (a map's outline, a picture's
grip in Live) go in a file that bundle loads (`library-lazy.css`, named in
app.js's `LAZY_MODULES`, which `ensureModule` gives a `<link>`), so the first
paint does not pay for them. A file in frontend/css that neither index.html
links nor a bundle names would be styles nothing ever applies; one a bundle
names that tests/_css_paths.py does not list would escape every CSS lint.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import lazy_modules_source
from tests._css_paths import CSS_FILES

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def _linked(pages: tuple[str, ...] = ("index.html",)) -> set[str]:
    found = set()
    for page in pages:
        html = re.sub(r"<!--.*?-->", "", (FRONTEND / page).read_text(encoding="utf-8"), flags=re.S)
        found |= set(re.findall(r'<link[^>]*rel="stylesheet"[^>]*href="/css/([^"?]+)', html))
    return found


def _lazy() -> set[str]:
    #: app.js's table and lazy-entries.js's rows (tests/_app_js.py).
    listed = set(re.findall(r'"/css/([A-Za-z0-9_.-]+\.css)"', lazy_modules_source()))
    #: A lazy file can also load its own sheet with `lazyScript("/css/x.css")`
    #: (Brief 49: first-run.js, manual.js) without a LAZY_MODULES row.
    loaded = set()
    for path in (FRONTEND / "js").glob("*.js"):
        text = path.read_text(encoding="utf-8")
        loaded |= set(re.findall(r'lazyScript\("/css/([A-Za-z0-9_.-]+\.css)"\)', text))
        #: Or a list of files handed to it: `["/css/x.css", "/js/x.js"].forEach(lazyScript)`
        #: (settings-wiring.js's file-drop stub).
        for files in re.findall(r"\[([^\]]*)\]\.forEach\(lazyScript\)", text):
            loaded |= set(re.findall(r'"/css/([A-Za-z0-9_.-]+\.css)"', files))
    return listed | loaded


def test_every_stylesheet_is_linked_or_loaded_by_a_bundle():
    on_disk = {p.name for p in (FRONTEND / "css").glob("*.css")}
    #: The desktop companion (INBOX 1464) is a page of its own with its own sheet.
    orphans = on_disk - _linked(("index.html", "desktop-companion.html")) - _lazy()
    assert not orphans, f"stylesheets nothing loads: {sorted(orphans)}"


def test_a_lazy_stylesheet_is_not_also_linked_and_is_linted():
    lazy = _lazy()
    assert lazy, "the Library bundle's stylesheet is no longer lazy"
    assert not lazy & _linked(), "a lazy stylesheet linked at boot counts twice"
    listed = {p.name for p in CSS_FILES}
    assert lazy <= listed, "tests/_css_paths.py must list every lazy stylesheet, after the boot files"


def test_the_loader_gives_a_css_file_a_link():
    """`lazyScript` loads every file of a bundle, once, whichever asks first."""
    app = (FRONTEND / "js" / "app.js").read_text(encoding="utf-8")
    body = app[app.index("function lazyScript(") :]
    body = body[: body.index("\n}\n")]
    assert 'file.endsWith(".css")' in body and 'el.rel = "stylesheet"' in body
