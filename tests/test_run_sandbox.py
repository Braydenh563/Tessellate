"""The Run button's sandbox (INBOX 404): what the page may and may not do.

The owner: "what about code errors, debugging console or smth??" Running a
document's code is the one place this app executes text it did not write, so
the policy the page is served under is the feature's whole safety case and is
held here directive by directive. The runs themselves are measured in
Chromium by `scratchpad/ui-sweeps/docrun.js`.
"""

from __future__ import annotations

from tessellate.api import run_sandbox


def _directives(policy: str) -> dict[str, str]:
    out = {}
    for part in policy.split(";"):
        words = part.split()
        if words:
            out[words[0]] = " ".join(words[1:])
    return out


def test_the_page_is_served_without_a_token_under_its_own_policy(client):
    response = client.get("/documents/run-sandbox")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    #: Its own policy, not the app's: the middleware only `setdefault`s.
    assert response.headers["content-security-policy"] == run_sandbox.RUN_SANDBOX_CSP
    assert response.headers["x-frame-options"] == "SAMEORIGIN"
    assert response.headers["cache-control"] == "no-store"
    assert "window.onmessage" in response.text


def test_the_policy_is_an_opaque_origin_with_no_network():
    d = _directives(run_sandbox.RUN_SANDBOX_CSP)
    #: An opaque origin: no storage, no cookies, not this app's origin.
    assert d["sandbox"] == "allow-scripts", "allow-same-origin would hand the code the notebook"
    #: No network at all, to this server or any other.
    assert d["connect-src"] == "'none'"
    assert d["default-src"] == "'none'"
    assert "'self'" not in d["img-src"] and "http" not in d["img-src"]
    #: Code from nowhere but the page itself and the blob it makes.
    assert d["script-src"] == "'unsafe-inline' 'unsafe-eval' blob:"
    assert "'self'" not in d["script-src"]
    assert d["worker-src"] == "blob:"
    #: Framed by the app only; nothing else navigates or submits.
    assert d["frame-ancestors"] == "'self'"
    assert d["base-uri"] == "'none'" and d["form-action"] == "'none'"


def test_the_runner_only_obeys_its_parent_and_tags_every_message():
    page = run_sandbox.RUN_SANDBOX_HTML
    assert 'if (e.source !== parent || typeof d.mmRun !== "number") return;' in page
    #: A page being run gets the same sandbox again, inside this one.
    assert 'frame.setAttribute("sandbox", "allow-scripts")' in page
    assert "worker.terminate()" in page


def test_the_apps_own_policy_is_not_widened_for_it():
    """Running code is the sandbox page's business: the notebook's own policy
    keeps no eval, no blob scripts and no blob workers."""
    from tessellate.core import security

    d = _directives(security.build_csp([]))
    assert "'unsafe-eval'" not in d["script-src"] and "blob:" not in d["script-src"]
    assert d["worker-src"] == "'self'"


# --- Python, through the Pyodide extra (INBOX 404) ---------------------------


def _install_fake_pyodide():
    """Write the Pyodide extra's folder the way a finished install leaves
    it, with stand-in files: these tests are about what the server serves."""
    import json

    from tessellate.core import extra_downloads, extras

    extra = extras.EXTRAS_BY_ID["pyodide"]
    target = extra_downloads.folder(extra)
    target.mkdir(parents=True, exist_ok=True)
    names = [name for d in extra.downloads for _m, name in d.members]
    for name in names:
        (target / name).write_bytes(b"\0asm" if name.endswith(".wasm") else b"x")
    (target / extra_downloads.MARKER).write_text(
        json.dumps({"version": extra.version, "files": names}), encoding="utf-8"
    )
    return target


def test_the_python_page_may_reach_the_runtime_files_and_nothing_else(client):
    response = client.get("/documents/run-sandbox/python")
    assert response.status_code == 200
    d = _directives(response.headers["content-security-policy"])
    #: The same opaque origin as the JavaScript runner.
    assert d["sandbox"] == "allow-scripts"
    assert d["default-src"] == "'none'"
    #: The one widening, and it is a path: the runtime's own files on this
    #: server. Not the server, not `'self'`, not any other origin.
    base = "http://testserver/documents/pyodide/"
    assert d["connect-src"] == base
    assert d["script-src"] == f"'unsafe-inline' 'unsafe-eval' 'wasm-unsafe-eval' blob: {base}"
    assert "'self'" not in d["script-src"] and "'self'" not in d["connect-src"]
    assert d["worker-src"] == "blob:"
    assert d["frame-ancestors"] == "'self'"
    assert response.headers["x-frame-options"] == "SAMEORIGIN"
    assert "window.onmessage" in response.text


def test_a_hostile_host_header_cannot_write_the_policy(client):
    response = client.get("/documents/run-sandbox/python", headers={"host": "evil; script-src *"})
    assert response.status_code == 400


def test_the_runtime_files_are_not_served_until_installed(client):
    assert client.get("/documents/pyodide/pyodide.mjs").status_code == 404


def test_the_runtime_files_are_served_to_the_sandbox_once_installed(client):
    _install_fake_pyodide()
    response = client.get("/documents/pyodide/pyodide.asm.wasm")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/wasm"
    #: The sandbox is an opaque origin, so its fetches are cross-origin and
    #: need this; the files are the public Pyodide release, nothing of the
    #: notebook's.
    assert response.headers["access-control-allow-origin"] == "*"
    js = client.get("/documents/pyodide/pyodide.mjs")
    assert js.headers["content-type"].startswith("text/javascript")


def test_only_the_runtimes_own_files_are_served(client):
    target = _install_fake_pyodide()
    (target / "secret.txt").write_text("no", encoding="utf-8")
    for name in ("secret.txt", "installed.json", "..%2Fpreferences.json", "%2E%2E"):
        assert client.get(f"/documents/pyodide/{name}").status_code == 404, name


def test_the_python_runner_keeps_the_javascript_runners_contract():
    page = run_sandbox.RUN_SANDBOX_PY_HTML
    #: Obeys only its parent, tags every message with the run's id.
    assert 'if (e.source !== parent || typeof d.mmRun !== "number") return;' in page
    #: Stop is a terminate: a `while True` has no other way out.
    assert "worker.terminate()" in page
    #: The document's own line numbers: the code is compiled under a name the
    #: runner looks for in the traceback.
    assert "<document>" in run_sandbox.PY_RUNNER and "PY_RUNNER" not in page
    #: It says which runner it is, so the app can tell its `ready` apart.
    assert 't: "ready", runner: "python"' in page
    assert 'runner: "python"' not in run_sandbox.RUN_SANDBOX_HTML


def test_the_python_line_cap_matches_the_apps_and_is_kept_at_the_source():
    """A `while True: print(i)` outran the app's tab: the cap is enforced in
    the worker too, at the same number the Output panel stops at."""
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "documents-code.js").read_text(
        encoding="utf-8"
    )
    assert f"const DOC_RUN_MAX_ROWS = {run_sandbox.MAX_LINES};" in source
    assert f"const MAX_LINES = {run_sandbox.MAX_LINES};" in run_sandbox._PY_WORKER
    assert "if (sent > MAX_LINES && !uncaught) return;" in run_sandbox._PY_WORKER


def test_the_sandbox_pages_are_cross_origin_isolated(client):
    """D2: the Python debugger blocks on `Atomics.wait` over a
    `SharedArrayBuffer`, which a page has only when it is cross-origin
    isolated. Measured in Chromium (Brief 70): the sandbox frame is isolated
    only when the app's own page carries the two headers as well, so every
    response does, and the frame is allowed `cross-origin-isolated`."""
    for path in ("/documents/run-sandbox", "/documents/run-sandbox/python", "/"):
        response = client.get(path)
        assert response.headers["cross-origin-opener-policy"] == "same-origin", path
        assert response.headers["cross-origin-embedder-policy"] == "require-corp", path
    #: The two headers are the only change: the policy is the same string.
    assert client.get("/documents/run-sandbox").headers["content-security-policy"] == run_sandbox.RUN_SANDBOX_CSP


def test_every_file_the_sandbox_loads_carries_a_resource_policy(client):
    """Under `require-corp` a cross-origin load without
    `Cross-Origin-Resource-Policy` is refused, and the opaque sandbox's every
    load is cross-origin: the runtime's files say `cross-origin`. The
    vendored libraries are fetched by the app itself (same origin) and handed
    over as text, so they carry the default `same-origin`."""
    _install_fake_pyodide()
    for name in ("pyodide.asm.wasm", "pyodide.mjs"):
        response = client.get(f"/documents/pyodide/{name}")
        assert response.headers["cross-origin-resource-policy"] == "cross-origin", name
    assert client.get("/vendor/sucrase/sucrase.min.js").headers["cross-origin-resource-policy"] == "same-origin"


def test_the_panel_frame_is_allowed_isolation():
    from tests._app_js import JS_DIR

    text = (JS_DIR / "documents-code.js").read_text(encoding="utf-8")
    assert 'frame.setAttribute("allow", "cross-origin-isolated")' in text


def test_the_javascript_debugger_steps_in_the_sandbox_and_obeys_only_its_parent():
    """D3: Debug's runner is a kind like any other, its interpreter handed
    over by the app (the page fetches nothing), and the panel's actions reach
    the stepping worker only through the page's own parent check."""
    page = run_sandbox.RUN_SANDBOX_HTML
    assert "jsdebug: runJsDebug" in page
    assert 'if (typeof lib.interp !== "string")' in page
    handle = page[page.index("function handle(e)") :]
    handle = handle[: handle.index("\n  }\n")]
    assert handle.index("e.source !== parent") < handle.index('d.type === "reply"')
    #: Uncaught exceptions are seen before the stack unwinds.
    assert "I.prototype.unwind = function" in run_sandbox._JS_DEBUG_WORKER


def test_the_python_debugger_waits_on_the_shared_buffer_only_when_isolated():
    page = run_sandbox.RUN_SANDBOX_PY_HTML
    assert "self.crossOriginIsolated" in page and "new SharedArrayBuffer(" in page
    assert "debug: Boolean(d.debug) && Boolean(shared)" in page
    assert "isolated: Boolean(shared)" in page
    worker = run_sandbox._PY_WORKER
    assert "Atomics.wait(ctl, 0, 0)" in worker and "Atomics.store(ctl, 0, 0);" in worker
    assert worker.index("Atomics.store(ctl, 0, 0);") < worker.index("current(JSON.parse(String(text)));")


def test_the_sandbox_files_ship_in_every_build():
    """The pages, workers and runner are files beside the module (audit 1031
    CE9), read at import: a build that leaves them out cannot start."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    assert (root / "src/tessellate/api/run_sandbox_assets").is_dir()
    assert "run_sandbox_assets/*" in (root / "pyproject.toml").read_text(encoding="utf-8")
    for spec in ("linux", "windows"):
        text = (root / "packaging" / spec / "tessellate.spec").read_text(encoding="utf-8")
        assert '"tessellate/api/run_sandbox_assets"' in text, spec
    for name in ("sandbox_page.html", "sandbox_py_page.html", "py_runner.py.txt", "py_worker.js",
                 "js_debug_worker.js", "sql_worker.js", "css_sample.html"):
        assert (root / "src/tessellate/api/run_sandbox_assets" / name).stat().st_size > 0, name


def test_ruffs_files_are_served_to_the_page_only_once_installed_and_only_by_name(client):
    import json

    from tessellate.core import extra_downloads, extras

    assert client.get("/documents/ruff/ruff_wasm.js").status_code == 404
    extra = extras.EXTRAS_BY_ID["ruff"]
    target = extra_downloads.folder(extra)
    target.mkdir(parents=True, exist_ok=True)
    names = [name for d in extra.downloads for _m, name in d.members]
    for name in names:
        (target / name).write_bytes(b"\0asm" if name.endswith(".wasm") else b"export default 1;")
    (target / extra_downloads.MARKER).write_text(json.dumps({"version": extra.version, "files": names}), encoding="utf-8")
    (target / "secret.txt").write_text("no", encoding="utf-8")
    js = client.get("/documents/ruff/ruff_wasm.js")
    assert js.status_code == 200 and js.headers["content-type"].startswith("text/javascript")
    assert client.get("/documents/ruff/ruff_wasm_bg.wasm").headers["content-type"] == "application/wasm"
    for name in ("secret.txt", "installed.json", "..%2Fpreferences.json", "%2E%2E"):
        assert client.get(f"/documents/ruff/{name}").status_code == 404, name
