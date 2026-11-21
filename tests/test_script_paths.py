"""Every script the app names resolves to a real file under `frontend/`.

The scripts moved from `frontend/` into `frontend/js/` (2026-10-03). A path
written in three places can drift in three ways and nothing else would see it:
a `<script src>` in index.html that 404s stops the app booting; a
`LAZY_MODULES` entry that 404s leaves a tab dead on first use; and a worker
URL that 404s fails silently (a Worker constructor does not throw for a
missing file). This reads each of them and checks the file exists.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import FRONTEND_DIR, INDEX_HTML, JS_DIR

APP_JS = JS_DIR / "app.js"


def _resolve(url: str) -> Path:
    """A site-absolute URL ("/js/app.js?v=1") as a path under frontend/."""
    return FRONTEND_DIR / url.split("?", 1)[0].lstrip("/")


def test_every_script_tag_resolves():
    html = INDEX_HTML.read_text(encoding="utf-8")
    urls = re.findall(r'<script src="(/[^"]+)"', html)
    assert len(urls) > 30, "index.html's script tags were not found"
    missing = [u for u in urls if not _resolve(u).is_file()]
    assert missing == []


def test_every_local_script_tag_is_under_js_or_vendor():
    html = INDEX_HTML.read_text(encoding="utf-8")
    urls = re.findall(r'<script src="(/[^"]+)"', html)
    stray = [u for u in urls if not u.startswith(("/js/", "/vendor/"))]
    assert stray == []


def test_every_lazy_module_path_resolves():
    source = APP_JS.read_text(encoding="utf-8")
    block = source.split("const LAZY_MODULES = {", 1)[1].split("\n};", 1)[0]
    paths = re.findall(r'"(/[^"]+\.js)"', block)
    assert len(paths) >= 10, "LAZY_MODULES was not found"
    missing = [p for p in paths if not _resolve(p).is_file()]
    assert missing == []


def test_worker_urls_resolve():
    """The workers are named by a URL in the file that starts them."""
    for name, pattern in (
        ("documents-prose.js", r'DOC_GRAMMAR_WORKER_URL = "(/[^"]+)"'),
        ("graph-canvas.js", r"new Worker\(`(/[^?`$]+)"),
        ("shell-reminders.js", r"new Worker\(`(/[^?`$]+)"),
    ):
        text = (JS_DIR / name).read_text(encoding="utf-8")
        match = re.search(pattern, text)
        assert match, f"{name} no longer names its worker"
        assert _resolve(match.group(1)).is_file(), match.group(1)


def test_service_worker_stays_at_the_root():
    """A service worker only controls pages under its own path."""
    assert (FRONTEND_DIR / "sw.js").is_file()
    assert not (JS_DIR / "sw.js").exists()
    wiring = (JS_DIR / "settings-wiring.js").read_text(encoding="utf-8")
    assert "serviceWorker\n    .register(`/sw.js?v=" in wiring or 'serviceWorker.register("/sw.js' in wiring


def test_no_script_is_left_loose_in_frontend():
    loose = sorted(p.name for p in FRONTEND_DIR.glob("*.js"))
    assert loose == ["sw.js"]
