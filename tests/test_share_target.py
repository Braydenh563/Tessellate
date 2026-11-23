"""The installed app is a share target, and what is shared lands in Capture.

UI_MODERNISATION_PLAN Phase 11 item 5, "upload from the share sheet". The
manifest declares the POST form so a file (a picture from the camera roll)
can come in too: the service worker takes the form, keeps the files in their
own cache and opens `/` with the text in the query and `share_files` naming
how many wait (the query survives the lock screen), and shared-intake.js
takes them once the entries have loaded. The suite cannot open a share
sheet; it holds the three halves to the same names, which is the one way
this silently breaks. Driven in Chromium by submitting the same multipart
form through the registered worker (CHANGELOG, L-ui-modernisation-7).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "frontend" / "manifest.webmanifest"
def test_the_manifest_declares_a_post_share_target_that_takes_files():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    target = manifest["share_target"]
    assert target["method"] == "POST", "a file share needs the POST form"
    assert target["enctype"] == "multipart/form-data"
    assert target["action"] == "/share-target"
    params = target["params"]
    assert {k: params[k] for k in ("title", "text", "url")} == {
        "title": "share_title",
        "text": "share_text",
        "url": "share_url",
    }
    files = params["files"]
    assert [f["name"] for f in files] == ["share_files"]
    assert "image/*" in files[0]["accept"]


def test_the_worker_takes_the_share_and_keeps_files_out_of_the_asset_cache():
    worker = (ROOT / "frontend" / "sw.js").read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert f'const SHARE_PATH = "{manifest["share_target"]["action"]}"' in worker
    handler = worker[worker.index('self.addEventListener("fetch"') :]
    assert handler.index("SHARE_PATH") < handler.index('request.method !== "GET"'), (
        "the POST must be taken before the worker hands every non-GET to the network"
    )
    assert 'const SHARE_CACHE = "tessellate-share-inbox"' in worker
    assert not "tessellate-share-inbox".startswith("tessellate-assets-"), "activate would delete waiting files"
    take = worker[worker.index("async function takeShare") :]
    assert 'getAll("share_files")' in take and "share_files" in take
    assert "Response.redirect(" in take and "303" in take


def test_the_app_reads_exactly_the_names_the_manifest_sends():
    app = app_js_text()
    intake = (ROOT / "frontend" / "js" / "shared-intake.js").read_text(encoding="utf-8")
    declared = re.search(r"const SHARE_PARAMS = \[([^\]]*)\]", intake)
    assert declared, "SHARE_PARAMS is missing from shared-intake.js"
    names = set(re.findall(r'"([^"]+)"', declared.group(1)))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    params = manifest["share_target"]["params"]
    sent = {v for k, v in params.items() if k != "files"} | {f["name"] for f in params["files"]}
    assert names == sent
    intake_cache = re.search(r'const SHARE_CACHE = "([^"]+)"', intake)
    assert intake_cache and intake_cache.group(1) == "tessellate-share-inbox"
    assert "caches.delete(SHARE_CACHE)" in intake, "taken files must not wait to be shared again"
    assert "handleFileUpload(box, files)" in intake, "files are staged as a paste into the composer would be"
    assert "takeSharedIntake" in app[app.index("function startApp()") :], "the intake is not a boot step"
    assert "history.replaceState" in intake[intake.index("function takeSharedIntake()") :][:1600], (
        "the query must be cleared, or a reload shares it again"
    )


def test_the_manifest_has_no_em_dash():
    assert "\u2014" not in MANIFEST.read_text(encoding="utf-8")


def test_one_bad_file_name_keeps_the_other_shared_files():
    """Source text: review (shared-intake.js sharedFiles): a name that would not
    decode threw inside the loop and the catch returned no files at all; each
    name decodes on its own now, falling back to `shared-<index>`."""
    import shutil
    import subprocess

    import pytest

    if not shutil.which("node"):
        pytest.skip("node is not installed")
    src = (ROOT / "frontend/js/shared-intake.js").read_text()
    start = src.index("  async function sharedFiles(count) {")
    fn = src[start : src.index("\n  }\n", start) + 4]
    script = (
        'const SHARE_CACHE = "x";\n'
        "class File { constructor(parts, name) { this.name = name; } }\n"
        "const names = ['a%20b.png', 'bad%E0%A4%A.png', 'c.png'];\n"
        "const hit = (n) => ({ headers: { get: (h) => (h === 'X-Share-Name' ? n : '') }, blob: async () => '' });\n"
        "globalThis.window = { caches: true };\n"
        "globalThis.caches = { open: async () => ({ match: async (u) => hit(names[+u.split('/').pop()]) }),"
        " delete: async () => {} };\n"
        f"{fn}\n"
        "sharedFiles(3).then((f) => console.log(JSON.stringify(f.map((x) => x.name))));\n"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout
    assert json.loads(out) == ["a b.png", "shared-1", "c.png"]
