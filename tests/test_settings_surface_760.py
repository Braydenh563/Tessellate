"""L-world-class-760: Settings' body is a file fetched on the first open, not 355 KB of the page.

`<script type="text/x-surface" data-surface="settings" data-src="/surfaces/settings.html?v=...">` stays in
index.html as an empty stub that names the file and lists the body's ids (`data-ids`), so `$`, `SURFACES.wire`
and `SURFACES.fill` can say which surface owns an id without the text. The text is fetched by `SURFACES.load`
(the gear under the pointer, or `openSettingsModal` when it comes first), or read synchronously by the one caller
that asks for one of its ids before either. Every assertion that used to read the markup in index.html reads it
through `tests/_surface_assets.py` (conftest puts it back in the page's script for the lints).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests._surface_assets import inline_surfaces, surface_text

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
RAW = (FRONTEND / "index.html").read_bytes().decode("utf-8")
STUB = re.search(
    r'<script type="text/x-surface" id="settings-body-template" data-surface="settings"([^>]*)></script>',
    RAW,
)
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def test_the_page_holds_a_stub_not_the_settings_markup():
    assert STUB, "the Settings script is an empty stub that names its file"
    assert 'data-src="/surfaces/settings.html?v=' in STUB.group(1)
    assert 'class="settings-section"' not in RAW and 'id="settings-models"' not in RAW
    assert len(RAW.encode()) < 900_000, "index.html was 1,233,829 bytes with the body in it"
    assert 'class="settings-section"' in surface_text("settings")


def test_the_listed_ids_are_the_ids_of_the_file():
    """`holds` answers from `data-ids` while the text is not in: a drift would build Settings for an id that is
    not in it, or leave an id of it to read as null."""
    listed = re.search(r'data-ids="([^"]*)"', STUB.group(1)).group(1).split(" ")
    in_file = list(dict.fromkeys(re.findall(r'\sid="([^"]+)"', surface_text("settings"))))
    assert listed == in_file, (
        "regenerate data-ids from frontend/surfaces/settings.html (ids in order, once each)"
    )


def test_the_inlined_page_is_what_the_lints_read():
    page = inline_surfaces(RAW)
    assert 'id="settings-models"' in page and len(page) > len(RAW) + 300_000


def test_the_file_is_served_stamped_stripped_and_cacheable(client):
    url = re.search(r'data-src="([^"]+)"', client.get("/").text).group(1)
    assert re.fullmatch(r"/surfaces/settings\.html\?v=[\w.]+-[0-9a-f]+", url), (
        "stamped by the file's own bytes"
    )
    response = client.get(url)
    assert response.status_code == 200
    assert "<!--" not in response.text and 'id="settings-models"' in response.text
    assert "immutable" in response.headers["cache-control"]
    assert len(response.text) < len(surface_text("settings")), (
        "comments are stripped from what is served"
    )
    sw = (FRONTEND / "sw.js").read_text(encoding="utf-8")
    assert 'path.startsWith("/surfaces/")' in sw, (
        "the worker keeps the stamped file like a stamped script"
    )


_FAKE = r"""
const log = [];
let parses = 0, requests = 0;
function makeFragment(html) {
  const ids = new Set(Array.from(html.matchAll(/\sid="([^"]+)"/g), (m) => m[1]));
  return { getElementById: (id) => (ids.has(id) ? { id } : null), querySelectorAll: () => [], ids };
}
const stub = { dataset: { surface: 'settings', src: '/surfaces/settings.html?v=1', ids: 'pane-a field-x' }, text: '', parentNode: { name: 'settings' },
  replaceWith(frag) { log.push('stamp'); for (const id of frag.ids) live.set(id, { id }); } };
const live = new Map();
const document = {
  querySelectorAll: () => [stub],
  getElementById: (id) => live.get(id) ?? null,
  createDocumentFragment: () => { const f = makeFragment(''); f.append = (c) => c.ids.forEach((id) => f.ids.add(id)); return f; },
  createElement: () => { const holder = { get content() { parses++; return makeFragment(this._html); } }; Object.defineProperty(holder, 'innerHTML', { set(v) { this._html = v; } }); return holder; },
};
const window = {};
let answer = { status: 200, responseText: '<section class="settings-section" id="pane-a"><input id="field-x"></section>' };
class XMLHttpRequest { open() {} send() { requests++; Object.assign(this, answer); } }
let fetches = 0;
globalThis.fetch = async () => { fetches++; return { ok: answer.status === 200, text: async () => answer.responseText }; };
globalThis.api = (path) => globalThis.fetch(path); // the load goes through the API door (test_no_bare_fetch)
globalThis.setTimeout = () => 0;
"""


def _run(body: str) -> dict:
    src = (FRONTEND / "js" / "settings-body.js").read_text(encoding="utf-8")
    out = subprocess.run(
        ["node", "-e", "\n".join([_FAKE, src, body])], capture_output=True, text=True, timeout=30
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@needs_node
def test_a_fetched_surface_answers_for_its_ids_without_its_text():
    r = _run(
        """
        const owner = SURFACES.owner('field-x'), none = SURFACES.owner('nope');
        const pending = SURFACES.pending('settings');
        console.log(JSON.stringify({ owner, none: none ?? null, pending, requests, fetches, parses }));
        """
    )
    assert r["owner"] == "settings" and r["none"] is None and r["pending"] is True
    assert r["requests"] == 0 and r["fetches"] == 0 and r["parses"] == 0, (
        "naming an id reads nothing"
    )


@needs_node
def test_load_fetches_once_and_the_build_then_needs_no_synchronous_read():
    r = _run(
        """
        (async () => {
          await Promise.all([SURFACES.load('settings'), SURFACES.load('settings')]);
          const pendingAfter = SURFACES.pending('settings');
          const built = surfaceBuild('settings');
          console.log(JSON.stringify({ fetches, requests, pendingAfter, built, parses, log }));
        })();
        """
    )
    assert r["fetches"] == 1 and r["requests"] == 0 and r["pendingAfter"] is False
    assert r["built"] is True and r["parses"] >= 1 and r["log"] == ["stamp"]


@needs_node
def test_an_id_asked_before_any_fetch_reads_the_file_synchronously_and_builds():
    r = _run(
        """
        const found = surfaceFind('field-x');
        console.log(JSON.stringify({ found, requests, fetches, again: surfaceFind('field-x') }));
        """
    )
    assert r["found"] == {"id": "field-x"} and r["requests"] == 1 and r["fetches"] == 0


@needs_node
def test_a_failed_read_builds_nothing_and_asks_again_next_time():
    r = _run(
        """
        answer = { status: 500, responseText: '' };
        const first = surfaceBuild('settings');
        const second = surfaceBuild('settings');
        answer = { status: 200, responseText: '<i id="field-x"></i>' };
        const third = surfaceBuild('settings');
        console.log(JSON.stringify({ first, second, third, requests, pending: SURFACES.pending('settings') }));
        """
    )
    assert (
        r["first"] is False and r["second"] is False and r["third"] is True and r["requests"] == 3
    )
    assert r["pending"] is False
