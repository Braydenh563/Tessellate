"""INBOX 1722 (the owner, 2026-11-09: the Diagram builder "didt open for liek 10 seconds"). The door waited on the Library bundle
(33 files, 5 MB) only because `diagramModel` lives in documents-mermaid.js, a file whose top level only declares. The
door loads that file alone (it also holds `wireToolbarRoving`, the one helper the builder bars call): no editors, no boards.
A caller holding a text box or a board still brings the Library, because the door writes into them."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests._app_js import lazy_modules_source

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


class _Rows(dict):
    def __missing__(self, name: str) -> list[str]:
        found = re.search(rf"(?<![\w\"]){name}: \[(.*?)\](?:,|\s*[\n}}])", lazy_modules_source(), re.S)
        assert found, name
        body = re.sub(r"//.*", "", found.group(1))
        return re.findall(r'"([^"]+)"', body)


def _rows() -> _Rows:
    return _Rows()


def test_the_door_loads_the_model_file_alone_not_a_bundle_row():
    """No `LAZY_MODULES` row: app.js is at its gzip cap, and `lazyScript` is the same once-per-file load a row would use."""
    assert "diagramDoor:" not in lazy_modules_source()
    assert "/js/documents-mermaid.js" in _rows()["library"]


def test_the_library_bundle_still_carries_the_model_before_the_editor():
    library = _rows()["library"]
    assert library.index("/js/documents-mermaid.js") < library.index("/js/documents.js")


def test_the_builders_own_files_name_what_they_need_beyond_the_library():
    # The level readout is a value field (value-field.js): the Library's list carried it, the door's does not.
    assert _rows()["diagramView"][:2] == ["/css/value-field.css", "/js/value-field.js"]


def test_a_door_with_nothing_in_hand_asks_for_the_builder_alone():
    panes = (JS / "settings-panes.js").read_text(encoding="utf-8")
    row = panes[panes.index('id: "diagram"') : panes.index('id: "diagram"') + 900]
    assert '(t ? ensureModule("library") : lazyScript("/js/documents-mermaid.js"))' in row
    features = (JS / "app-features.js").read_text(encoding="utf-8")
    assert 'lazyScript("/js/documents-mermaid.js").then(() => diagramModel.door({ doc: true }))' in features


def test_the_pieces_that_need_the_library_ask_for_it_when_they_run():
    mermaid = (JS / "documents-mermaid.js").read_text(encoding="utf-8")
    assert "window.wbCommandsLive?.()" in mermaid and "!doc && wbCommandsLive()" not in mermaid
    #: The `docs` guard moved with the list of diagrams to the sheet in diagram-embed.js (R12, 2026-11-12), asserted below.
    # Done lands on the Library's page and Open an existing diagram loads a document: both fetch the bundle first.
    assert mermaid.count('ensureModule("library")') >= 2
    embed = (JS / "diagram-embed.js").read_text(encoding="utf-8")
    assert embed.index('await ensureModule("library");') < embed.index("offerCreateUndo(made);")
    assert 'typeof docs !== "undefined" && Array.isArray(docs)' in embed


@needs_node
def test_the_door_opens_the_builder_with_no_library_name_defined():
    """documents-mermaid.js alone in a bare context: none of `docs`, `wbCommandsLive`, `EDITOR_SURFACES`."""
    prog = (
        "const vm=require('vm'),fs=require('fs');const asked=[];let opened=null;"
        "const ctx={window:null,console,toast:()=>undefined,document:{createElement:()=>({}),querySelector:()=>null},"
        "ensureModule:async(n)=>{asked.push(n);if(n==='diagramEmbed'){ctx.diagramModel.embed={open:(o)=>{opened=o;return Promise.resolve(true);}};}return true;},"
        "lazyModuleLoads:new Map(),LAZY_MODULES:{},switchTab:(t)=>asked.push('tab:'+t),loadDocuments:async()=>asked.push('load'),offerCreateUndo:()=>asked.push('undo'),"
        "apiJson:async()=>({id:7,title:'T'}),apiPagedList:async()=>[]};"
        "ctx.window=ctx;vm.createContext(ctx);"
        f"for(const f of ['documents-mermaid.js'])vm.runInContext(fs.readFileSync({json.dumps(str(JS))}+'/'+f,'utf8'),ctx);"
        "(async()=>{"
        "await ctx.diagramModel.door({target:null});"
        "const out={type:typeof ctx.wireToolbarRoving,draft:opened.draft,named:opened.named,hasPick:typeof opened.existing.pick};"
        "asked.length=0;await opened.onDone('flowchart TD\\n a-->b','', 'N');out.afterDone=asked.slice();"
        "asked.length=0;await opened.existing.open({id:3});out.afterOpen=asked.slice();"
        "process.stdout.write(JSON.stringify(out));})().catch((e)=>{console.error(e);process.exit(1);});"
    )
    got = json.loads(subprocess.run(["node", "-e", prog], capture_output=True, text=True, check=True, timeout=30).stdout)
    assert got["type"] == "function" and got["draft"] == "new" and got["named"] is True and got["hasPick"] == "function"
    # The library is fetched after the save and before the page it lands on is switched to and filled.
    assert got["afterDone"] == ["library", "tab:documents", "load", "undo"]
    assert got["afterOpen"] == ["library", "tab:documents", "load"]
