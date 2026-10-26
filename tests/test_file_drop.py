"""Drop files anywhere to add them to the Library (ledger libr-1011 row 1266).

The boot code is one `dragenter` stub that loads `file-drop.js`; the module
takes only drops nothing else defended, sends pictures and PDFs to the
Library's upload and everything else to the documents import, and shows the
drop veil (DESIGN.md "A drop target") while it works. The router runs in node
with stand-ins for the network."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DROP = (ROOT / "frontend/js/file-drop.js").read_text(encoding="utf-8")
WIRING = (ROOT / "frontend/js/settings-wiring.js").read_text(encoding="utf-8")
APP = (ROOT / "frontend/js/app.js").read_text(encoding="utf-8")


def _block(source: str, start: str, end: str) -> str:
    begin = source.index(start)
    return source[begin : source.index(end, begin) + len(end)]


def test_the_boot_cost_is_one_stub_that_loads_two_files():
    stub = _block(WIRING, 'document.addEventListener("dragenter"', "});\n")
    assert '["/css/file-drop-lazy.css", "/js/file-drop.js"].forEach(lazyScript)' in stub
    assert len(stub.splitlines()) <= 4
    assert "fileDrop" not in re.sub(r"fileDropBox", "", WIRING), "settings-wiring.js names no function of the module"
    assert DROP.rstrip().endswith("fileDropEnter();"), "the module starts itself"
    assert "fileDrop" not in APP, "app.js, at its gzip cap, carries nothing for it"


def test_it_takes_only_what_nothing_else_took():
    over = _block(DROP, "function fileDropOver(event) {", "\n}\n")
    assert "event.defaultPrevented" in over
    arm = _block(DROP, "function fileDropArm() {", "\n}\n")
    assert "event.defaultPrevented" in arm and "fileDropLocked()" in arm


def _run(names: list[str], fail: set[str] | None = None) -> dict:
    node = shutil.which("node")
    if not node:  # pragma: no cover
        pytest.skip("node is not available")
    script = (
        'const FILE_DROP_MEDIA = /\\.(png|jpe?g|gif|webp|avif|bmp|ico|pdf)$/i;\n'
        "const fileDrop = { busy: false, timer: 0 };\n"
        + _block(DROP, "async function fileDropImport(files) {", "\n}\n")
        + """
const names = JSON.parse(process.argv[1]); const fail = new Set(JSON.parse(process.argv[2]));
const log = { uploads: [], docs: [], toasts: [], says: [], modules: [], undos: [] };
class FormData { constructor() { this.f = {}; } append(k, v) { this.f[k] = v; } }
const api = { upload: async (path, form) => { if (fail.has(form.f.file.name)) throw new Error("too big"); log.uploads.push([path, form.f.file.name, form.f.direct]); return { json: async () => ({ id: form.f.file.name }) }; } };
const pushUploadUndo = (label, base, made) => log.undos.push([label, base, made && made.id]);
const toast = (m) => log.toasts.push(m);
const toastAction = (m, label) => log.toasts.push(m + " / " + label);
async function ensureModule(n) { log.modules.push(n); return true; }
async function importLibraryDocuments(files) { log.docs = files.map((f) => f.name); }
async function switchTab() {}
const document = { querySelector: () => null };
function fileDropShow(t) { log.says.push(t); }
function fileDropHide() { log.says.push("hidden"); }
(async () => {
  await fileDropImport(names.map((name) => ({ name })));
  process.stdout.write(JSON.stringify({ ...log, busy: fileDrop.busy }));
})();
"""
    )
    out = subprocess.run([node, "-e", script, json.dumps(names), json.dumps(sorted(fail or []))], capture_output=True, text=True, timeout=60, check=False)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_pictures_and_pdfs_are_uploaded_direct_and_the_rest_become_documents():
    got = _run(["a.png", "b.PDF", "notes.docx", "c.md"])
    assert got["uploads"] == [["/media/upload", "a.png", "true"], ["/media/upload", "b.PDF", "true"]]
    assert got["docs"] == ["notes.docx", "c.md"]
    #: Each picture is one step on the undo stack (INBOX 898).
    assert got["undos"] == [["Added “a.png”", "/media", "a.png"], ["Added “b.PDF”", "/media", "b.PDF"]]
    assert got["modules"] == ["libraryList"]
    assert any(t.startswith("Added 2 pictures or PDFs to your Library. / Show") for t in got["toasts"])
    assert got["says"][0] == "Adding 4 files…" and got["says"][-1] == "hidden" and got["busy"] is False


def test_a_refused_file_is_named_and_the_others_still_go():
    got = _run(["a.png", "b.jpg"], fail={"a.png"})
    assert got["uploads"] == [["/media/upload", "b.jpg", "true"]]
    assert "a.png: too big" in got["toasts"]
    assert any(t.startswith("Added 1 picture or PDF") for t in got["toasts"])
    assert got["modules"] == []


def test_the_veil_is_a_status_with_no_press_and_no_blur():
    css = (ROOT / "frontend/css/file-drop-lazy.css").read_text(encoding="utf-8")
    assert "pointer-events: none" in css and "blur" not in css
    assert 'veil.setAttribute("role", "status")' in DROP
    assert "innerHTML" not in DROP


def test_a_notice_about_a_pdf_opens_library_files_not_images():
    """attach-1026 A4: the toast and its bell row name the sub-tab the drop
    filled; the bell reopens it from the stored `go.media`."""
    assert 'go: { tab: "library", media: where }' in DROP
    assert 'lands.add(/\\.pdf$/i.test(file.name) ? "files" : "images")' in DROP
    bell = (ROOT / "frontend/js/notifications.js").read_text(encoding="utf-8")
    assert 'data-media-kind="${action.media}"' in bell
    kept = (ROOT / "frontend/js/chat-attach.js").read_text(encoding="utf-8")
    assert '{ go: { tab: "library", media: "files" } }' in kept
