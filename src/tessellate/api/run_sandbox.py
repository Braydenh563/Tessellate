"""The sandbox a code document's Run button runs in (INBOX 404).

The owner, 2026-09-23: "what about code errors, debugging console or smth??"
Answer placed in INBOX 404: Run with an output console, JavaScript in a
worker and HTML in a preview frame, both sandboxed, nothing compiled.

**Why a route, and why this page carries its own policy.** The app's CSP has
no `'unsafe-eval'` and no `blob:` in `script-src`, on purpose, and running
somebody's code needs one or the other. Widening the notebook's own policy
to run a document would trade the notebook's protection for a feature. A
same-origin HTTP response carries its own policy instead (the HTML preview in
`routes_files` is the precedent), and this is it:

- `sandbox allow-scripts`: an **opaque origin**. The code cannot read this
  app's storage, cookies, IndexedDB or caches, because it is not this app's
  origin; the iframe that loads it says `sandbox="allow-scripts"` as well, so
  either one alone is enough.
- `connect-src 'none'`, `img-src data: blob:`, `default-src 'none'`: **no
  network**, not to this server and not beyond it. A worker made from a
  `blob:` inherits this page's policy, so the worker has none either.
- `script-src 'unsafe-inline' 'unsafe-eval' blob:` and `worker-src blob:`:
  the runner's own inline script, and the user's code as a `blob:` worker or
  inside a `srcdoc` frame. Nothing from any origin, this one included.
- `frame-ancestors 'self'` (and `X-Frame-Options: SAMEORIGIN`, overriding the
  middleware's `DENY`): only the app may frame it.

The only way out is `postMessage` to the parent, which checks that a message
came from its own frame (`event.source`) and treats the payload as text. The
page holds no data, so it is served without the unlock gate
(`tests/test_every_route_is_locked.py` names it and says why).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

router = APIRouter(tags=["documents"])

#: The sandbox pages, the workers and the Python runner are files beside this
#: module (`run_sandbox_assets/`), not strings in it (audit 1031 CE9): they are
#: JavaScript, HTML and Python that an editor can lint and a person can read
#: whole. Read once at import; the module's names and the served text are the
#: same as when they were literals.
_ASSETS = Path(__file__).with_name("run_sandbox_assets")


def _asset(name: str) -> str:
    return (_ASSETS / name).read_text(encoding="utf-8")


def _fill(page: str, **parts: str) -> str:
    """`page` with each `@@NAME@@` replaced by that text as a JSON string
    literal (`</` escaped, so it cannot close the page's own script tag)."""
    for key, value in parts.items():
        page = page.replace(f"@@{key}@@", json.dumps(value).replace("</", "<\\/"))
    return page


#: Cross-origin isolation (D2): with these on the sandbox pages and on the app
#: that frames them, the sandbox and its workers have `SharedArrayBuffer`,
#: which the Python debugger and a mid-run `input()` block on. The policy is
#: unchanged; a webview that drops the headers still runs, and Debug says why
#: it cannot.
ISOLATION_HEADERS = {
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Embedder-Policy": "require-corp",
}

RUN_SANDBOX_CSP = (
    "sandbox allow-scripts; default-src 'none'; "
    "script-src 'unsafe-inline' 'unsafe-eval' blob:; worker-src blob:; "
    "style-src 'unsafe-inline'; img-src data: blob:; font-src data:; media-src data: blob:; "
    "connect-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'"
)

#: The page a `.css` document is previewed against (D6): the elements a
#: stylesheet usually styles, in one short document, with the class names a
#: starter stylesheet tends to use. Plain markup, no script.
CSS_SAMPLE_HTML = _asset("css_sample.html")

#: The SQL runner (D5), a worker made from sql.js's own text (handed over by
#: the app in `lib.js`) with this after it. An **in-memory database per run**,
#: never the app's own: the worker has no network and no storage, and the
#: binary it compiles came over `postMessage` too. Each statement's result is
#: a `table` row (the first 200 rows of it, and how many more there were) on
#: the line the statement starts on; a statement that returns nothing says
#: how many rows it changed. A parse or run error stops the run on its line.
#: `tables` (CSV text already split by the app) are loaded first.
SQL_ROW_CAP = 200

_SQL_WORKER = f"var ROW_CAP = {SQL_ROW_CAP};\n" + _asset("sql_worker.js")


#: The JavaScript debugger (DOCUMENTS_PLAN 23, D3), a worker made from
#: JS-Interpreter's text (handed over by the app in `lib.interp`, from
#: `frontend/vendor/js-interpreter`) with this after it. The script is
#: stepped one interpreter state at a time; at each statement about to run
#: the driver decides whether to stop (a breakpoint and its condition, or the
#: step asked for: in, over, out by the depth of the call stack), and a stop
#: is one message with the line, the frame's variables, the stack and the
#: watches. Between stops the worker is idle, waiting for the panel's next
#: action as an ordinary message, so it needs no shared memory. An exception
#: nothing catches is seen as it is thrown, before the stack unwinds, so its
#: stop has the frame and the variables it was raised with. Watches and
#: conditions are evaluated natively over the frame's values (read-only by
#: intent); timers run as the interpreter's own tasks.
_JS_DEBUG_WORKER = _asset("js_debug_worker.js")

#: The runner. **One protocol for every language** (DOCUMENTS_PLAN 23, D1):
#: the app sends `{type: "run", mmRun, kind, source, path, stdin, tests,
#: lineOffset, lib}` and gets back rows, `{t: "log", level, text, line, col}`
#: (plus `t: "table"` and `t: "test"` rows for the kinds that make them), each
#: tagged with the run's id so a late message from a stopped run is dropped.
#: `kind` picks a runner from `RUNNERS`; the panel, Stop and the limits are the
#: app's, the same for all of them (`frontend/js/run-core.js` builds the
#: message). `lineOffset` is how many lines of the document come before
#: `source` (Run selection, Run cell), so a reported line is still the
#: document's. `lib` is a vendored library's text (and a WebAssembly binary)
#: the app fetched from its own origin and handed over, because this page
#: may fetch nothing at all.
#:
#: - `js`: the code becomes a `blob:` worker with a one-line prelude **on the
#:   code's own first line**, so a line number the browser reports is the
#:   document's line number with nothing subtracted. The prelude sends
#:   `console.*` up as text with the line it was called from, and a closing
#:   `postMessage` says the top level finished. `tests: true` puts the app's
#:   test harness (`run-tests.js`) in front and runs the suite after.
#: - `html`: the page goes into a `srcdoc` frame, which inherits this page's
#:   sandbox and policy, with the same one-line prelude in front of it, and is
#:   shown.
#: - `stop`: the worker is terminated, the frame emptied.
#: - `eval` (the console, D8): one line evaluated in the worker's global as
#:   the last run left it (a fresh worker when nothing ran, or the last run
#:   was not a script). Everything it sends up carries the line's `mmEval`
#:   until its `eval-done`, which holds the value as text.
RUN_SANDBOX_HTML = _fill(
    _asset("sandbox_page.html"), SQL_WORKER=_SQL_WORKER, CSS_SAMPLE=CSS_SAMPLE_HTML, JS_DEBUG=_JS_DEBUG_WORKER
)


@router.get("/documents/run-sandbox")
def run_sandbox() -> Response:
    """The runner page, under its own policy. See the module docstring."""
    return Response(
        content=RUN_SANDBOX_HTML,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Security-Policy": RUN_SANDBOX_CSP,
            "X-Frame-Options": "SAMEORIGIN",
            "Cache-Control": "no-store",
            **ISOLATION_HEADERS,
        },
    )


# --- Python, through the Pyodide extra (INBOX 404) ---------------------------
#
# The owner, 2026-09-24: "Run Python files: yes, as an opt-in extra". The
# runtime is Pyodide, CPython compiled to WebAssembly, downloaded once by the
# `pyodide` entry in `core/extras.py` into the data dir and served from there
# by the route at the bottom of this file. Nothing here is used until it is.
#
# **The same sandbox, one path wider.** The Python page is the JavaScript
# page's policy with exactly one change: the runtime's own files. Pyodide
# loads a module, compiles a WebAssembly binary and fetches its standard
# library, so `script-src` and `connect-src` name `/documents/pyodide/` on
# this server, as a path, and nothing else: not the server's other routes,
# not `'self'`, not another origin. The page is still an opaque origin with
# none of the notebook's storage, and the user's code still reaches the app
# only through `postMessage`.
#
# **Why the origin is written out.** A CSP source with a path cannot be
# spelled with `'self'`, so the policy is built per request from the address
# the page was asked for. That address comes from the Host header, so it is
# checked against a plain host[:port] shape first: a header carrying `;` or a
# space would otherwise write its own directives into the policy.

_HOST_RE = re.compile(r"(?:[A-Za-z0-9.-]+|\[[0-9A-Fa-f:.]+\])(?::\d{1,5})?")

#: Where the runtime's files are served; the policy names exactly this path.
PYODIDE_PATH = "/documents/pyodide/"

#: The app's cap on a run's output (`DOC_RUN_MAX_ROWS` in
#: `frontend/js/documents-code.js`), kept at the source as well; see the worker.
MAX_LINES = 500


def python_csp(base: str) -> str:
    """The JavaScript runner's policy, plus `base` (the runtime's folder URL)
    in `script-src` and `connect-src`. `'wasm-unsafe-eval'` says what the
    WebAssembly compile needs by name; `'unsafe-eval'` already covered it."""
    return (
        "sandbox allow-scripts; default-src 'none'; "
        f"script-src 'unsafe-inline' 'unsafe-eval' 'wasm-unsafe-eval' blob: {base}; "
        "worker-src blob:; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; "
        f"media-src data: blob:; connect-src {base}; base-uri 'none'; form-action 'none'; "
        "frame-ancestors 'self'"
    )


#: The Python half, run inside Pyodide once per worker. `_mm_run` executes a
#: document under the file name `<document>`, so a traceback frame (or a
#: syntax error) that names that file carries the document's own line
#: number. `print` goes through `_MMOut`, which sends each line up with the
#: line of the document that printed it, found by walking the stack to the
#: innermost `<document>` frame. A fresh namespace per run, so one run's
#: variables are not the next run's; imported modules stay cached, which is
#: what makes a second run quick.
PY_RUNNER = _asset("py_runner.py.txt")

#: The worker, a classic one that `import()`s Pyodide's module from its
#: folder. **Not `{type: "module"}`**: measured in Chromium, a module worker
#: made from a `blob:null` URL inside this opaque origin never ran a line
#: (probably its script fetch: a module script is a CORS fetch, and this
#: blob's origin is opaque), while
#: the classic worker with a dynamic `import()` loads all five files. It
#: loads the runtime on its first run and keeps it: a later run reuses it,
#: and Stop (or the app's timeout, or its line cap) terminates the worker,
#: after which the next run loads it again. `started` is sent when the
#: document's code actually begins, so the app's ten seconds count the
#: script, not the runtime's start-up.
_PY_WORKER = (
    "const RUNNER = " + json.dumps(PY_RUNNER) + ";\n"
    + f"const MAX_LINES = {MAX_LINES};\n"
    + _asset("py_worker.js")
)

RUN_SANDBOX_PY_HTML = _fill(_asset("sandbox_py_page.html"), WORKER=_PY_WORKER)


@router.get("/documents/run-sandbox/python")
def run_sandbox_python(request: Request) -> Response:
    """The Python runner page, under the policy `python_csp` builds for the
    address it was asked for. Served whether or not the runtime is installed:
    the app asks `/extras` first, and without the files the worker says it
    could not start."""
    netloc = request.headers.get("host") or request.url.netloc
    if request.url.scheme not in {"http", "https"} or not _HOST_RE.fullmatch(netloc):
        raise HTTPException(status_code=400, detail="Bad host.")
    base = f"{request.url.scheme}://{netloc}{PYODIDE_PATH}"
    return Response(
        content=RUN_SANDBOX_PY_HTML,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Security-Policy": python_csp(base),
            "X-Frame-Options": "SAMEORIGIN",
            "Cache-Control": "no-store",
            **ISOLATION_HEADERS,
        },
    )


_PYODIDE_TYPES = {
    ".mjs": "text/javascript; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".wasm": "application/wasm",
    ".zip": "application/zip",
    ".json": "application/json",
}


def _extra_file(extra_id: str, name: str) -> FileResponse:
    """One file of an installed download extra, by a name the extra itself lists.

    Only the names the extra's entry unpacks are served (not its marker, not
    anything else in the folder), and `name` is looked up in that set rather
    than joined onto a path, so no spelling of `..` reaches the disk. The
    path is built from the release's own list, never from the request:
    `name` only picks an entry, so what reaches the disk is a string this
    file wrote (CodeQL reads a membership test as no guard at all).
    """
    from tessellate.core import extras

    extra = extras.EXTRAS_BY_ID[extra_id]
    served = {file: file for download in extra.downloads for _member, file in download.members}
    folder = extras.download_ready(extra_id)
    listed = served.get(name)
    if folder is None or listed is None or not (folder / listed).is_file():
        raise HTTPException(status_code=404, detail="Not installed.")
    suffix = "." + listed.rsplit(".", 1)[-1]
    return FileResponse(
        folder / listed,
        media_type=_PYODIDE_TYPES.get(suffix, "application/octet-stream"),
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cross-Origin-Resource-Policy": "cross-origin",
            "Cache-Control": "no-cache",
        },
    )


@router.get(PYODIDE_PATH + "{name}")
def pyodide_file(name: str) -> FileResponse:
    """One of the Pyodide runtime's files, once the extra is installed.

    Open without the unlock, like the page that loads them: the sandbox is an
    opaque origin and cannot send the token, and these are the public
    Pyodide release, nothing of the notebook's. `Access-Control-Allow-Origin`
    because that same opaque origin makes every fetch cross-origin.
    """
    return _extra_file("pyodide", name)


RUFF_PATH = "/documents/ruff/"


@router.get(RUFF_PATH + "{name}")
def ruff_file(name: str) -> FileResponse:
    """Ruff's module and wasm, once the extra is installed (L-documents-50).

    Open without the unlock for the same reason as Pyodide's files: the page
    `import()`s the module, and an import cannot send the token. They are the
    public release, nothing of the notebook's.
    """
    return _extra_file("ruff", name)


# --- A long run is a job in the Activity panel (DOCUMENTS_PLAN 25 row 9) ------
#
# Decision 70: background work is "visible and stoppable". A run happens in
# the browser's sandbox, not here, so the panel registers a run that is still
# going after two seconds, renews it every second, and asks each time whether
# Activity's Stop was pressed; the answer stops the run in the tab. The lease
# (`core/activity.py`) ends a row whose tab went away. These routes are
# behind the unlock like every other (`jobs_router`): they name a run, never
# its code.

#: Seconds a run's row lives without a renewal.
RUN_JOB_LEASE_S = 6.0
#: Runs listed at once: a bounded list, whatever a page asks for.
RUN_JOB_MAX = 8
RUN_JOB_KIND = "code-run"

#: Behind the unlock, unlike the sandbox pages above: `app.py` includes this
#: router with the lock, the pages' router without it.
jobs_router = APIRouter(tags=["documents"])


class RunJobBody(BaseModel):
    label: str = Field(default="Running a code document", max_length=120)


def _run_job(job_id: str):
    from tessellate.core import activity

    job = activity.get(job_id)
    if job is None or job.kind != RUN_JOB_KIND:
        raise HTTPException(status_code=404, detail="That run has ended.")
    return job


@jobs_router.post("/documents/run-jobs")
def start_run_job(body: RunJobBody) -> dict:
    """List a long run in Activity, with Stop."""
    from tessellate.core import activity

    if activity.count(RUN_JOB_KIND) >= RUN_JOB_MAX:
        raise HTTPException(status_code=429, detail="Too many runs are listed already.")
    label = " ".join(body.label.split())[:120] or "Running a code document"
    job = activity.start(RUN_JOB_KIND, label, stoppable=True, lease=RUN_JOB_LEASE_S)
    return {"id": job.id, "lease": RUN_JOB_LEASE_S}


@jobs_router.post("/documents/run-jobs/{job_id}/beat")
def beat_run_job(job_id: str) -> dict:
    """Renew the run's row; says whether Activity asked it to stop."""
    job = _run_job(job_id)
    job.touch()
    return {"stopped": job.stopped}


@jobs_router.delete("/documents/run-jobs/{job_id}")
def end_run_job(job_id: str) -> dict:
    """The run ended in the tab: its row goes."""
    from tessellate.core import activity

    activity.finish(_run_job(job_id))
    return {"status": "ok"}
