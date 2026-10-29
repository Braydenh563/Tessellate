"""The PWA shell (WORLD_CLASS_PLAN 25d, decision 49).

The service worker caches what can never be stale (a URL stamped with its
file's own hash, the vendored libraries, the icons) and still refuses to paint
the app without its server: a failed navigation gets `offline.html`, an honest
page, never the tabs and empty lists. The owner's words, which this keeps:
"if the backend is closed the ui should fail to load or connect on browsers
until started back up again."

`sw.js` is run for real, in Node with a fake `self`, `caches` and `fetch`, so
the behaviour is asserted rather than the source text. Without Node the
behavioural tests skip; the source-text ones always run.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate import __version__

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
SW = FRONTEND / "sw.js"
OFFLINE = FRONTEND / "offline.html"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="Node is not installed")

#: Runs sw.js under a fake worker scope and prints one JSON result. `scenario`
#: is the body of an async function with `sw`, `fire`, `net` and `cache` in
#: scope; `net.calls` lists every URL the worker asked the network for.
HARNESS = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[2], "utf8");
const scenario = fs.readFileSync(process.argv[3], "utf8");
const listeners = {};
const store = new Map(); // cache name -> Map(url -> Response)
const net = { calls: [], routes: {}, down: false };
function respond(url) {
  if (net.down) return Promise.reject(new TypeError("Failed to fetch"));
  net.calls.push(url);
  const make = net.routes[new URL(url).pathname];
  return Promise.resolve(make ? make() : new Response("body of " + url, { status: 200 }));
}
const caches = {
  async open(name) {
    if (!store.has(name)) store.set(name, new Map());
    const map = store.get(name);
    return {
      async match(key) { const hit = map.get(String(key.url || key)); return hit ? hit.clone() : undefined; },
      async put(key, res) { map.set(String(key.url || key), res); },
      async delete(key) { return map.delete(String(key)); },
      async keys() { return [...map.keys()]; },
    };
  },
  async keys() { return [...store.keys()]; },
  async delete(name) { return store.delete(name); },
};
const scope = {
  location: new URL(process.argv[4]),
  addEventListener(type, fn) { listeners[type] = fn; },
  skipWaiting() { scope.skipped = true; },
  clients: { claim() { scope.claimed = true; return Promise.resolve(); } },
};
scope.self = scope;
const context = vm.createContext({
  self: scope, caches, URL, Response, Request, Headers, console,
  fetch: (req) => respond(typeof req === "string" ? new URL(req, scope.location).href : req.url),
});
vm.runInContext(source, context);
function req(path, init = {}) {
  const url = new URL(path, scope.location).href;
  return {
    url, method: init.method || "GET", mode: init.mode || "no-cors",
    destination: init.destination || "script", headers: new Headers(init.headers || {}),
  };
}
// Dispatches a fetch event; resolves to the response the worker gave, or
// "passthrough" when it never called respondWith (the browser then goes to
// the network by itself, which is how an uncached request must behave).
async function fire(path, init) {
  let given = "passthrough";
  const pending = [];
  listeners.fetch({
    request: req(path, init),
    respondWith(p) { given = Promise.resolve(p); },
    waitUntil(p) { pending.push(p); },
  });
  const res = given === "passthrough" ? given : await given;
  await Promise.all(pending);
  return res;
}
async function lifecycle(type) {
  const pending = [];
  listeners[type]({ waitUntil(p) { pending.push(p); } });
  await Promise.all(pending);
}
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
new AsyncFunction("sw", "fire", "lifecycle", "net", "caches", "store", "Response", scenario)(
  scope, fire, lifecycle, net, caches, store, Response
).then(
  (out) => console.log(JSON.stringify({ ok: true, out })),
  (err) => console.log(JSON.stringify({ ok: false, error: String(err && err.stack || err) })),
);
"""


def run_worker(tmp_path: Path, scenario: str, version: str = "9.9.9") -> object:
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS, encoding="utf-8")
    body = tmp_path / "scenario.js"
    body.write_text(scenario, encoding="utf-8")
    done = subprocess.run(
        [NODE, str(harness), str(SW), str(body), f"http://127.0.0.1:8000/sw.js?v={version}"],
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert done.stdout.strip(), done.stderr
    result = json.loads(done.stdout.strip().splitlines()[-1])
    assert result["ok"], result["error"]
    return result["out"]


# --- the source, always checked ---------------------------------------------


def test_the_worker_has_a_fetch_handler_and_no_longer_claims_to_be_network_only():
    text = SW.read_text(encoding="utf-8")
    assert 'addEventListener("fetch"' in text
    assert "network-only" not in text.splitlines()[0].lower()
    assert "decision 49" in text.lower(), "the header should say why it caches now"
    assert "RETIRED_CACHE_PREFIX" in text, "the cleanup of the old shell caches stays"


def test_the_worker_stores_only_plain_200s():
    code = "\n".join(
        line for line in SW.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("//")
    )
    assert "response.status === 200" in code and 'has("set-cookie")' in code
    assert "/api/" not in code and "/auth/" not in code, "the API is refused by omission, never listed"


def test_the_registration_carries_the_version_and_skips_the_http_cache():
    wiring = (FRONTEND / "js" / "settings-wiring.js").read_text(encoding="utf-8")
    assert '"/sw.js?v=' in wiring or "`/sw.js?v=" in wiring
    assert 'updateViaCache: "none"' in wiring


# --- the worker, run -------------------------------------------------------


@needs_node
def test_the_cache_name_carries_the_app_version(tmp_path):
    names = run_worker(
        tmp_path,
        """
        await lifecycle("install");
        return [...(await caches.keys())];
        """,
        version="1.2.3",
    )
    assert names == ["tessellate-assets-1.2.3"]


@needs_node
def test_a_stamped_file_is_cached_and_the_second_ask_never_reaches_the_network(tmp_path):
    out = run_worker(
        tmp_path,
        """
        const a = await fire("/js/app.js?v=9.9.9-aaaa");
        const b = await fire("/js/app.js?v=9.9.9-aaaa");
        return { first: await a.text(), second: await b.text(), calls: net.calls.length };
        """,
    )
    assert out["calls"] == 1
    assert out["first"] == out["second"]


@needs_node
def test_two_stamps_for_the_same_file_are_two_cache_keys(tmp_path):
    """The plan's staleness test: an edited file has a new stamp, so the old
    entry can never be handed back for it."""
    out = run_worker(
        tmp_path,
        """
        net.routes["/js/app.js"] = (() => { let n = 0; return () => new Response("build " + (++n)); })();
        const old = await (await fire("/js/app.js?v=9.9.9-aaaa")).text();
        const edited = await (await fire("/js/app.js?v=9.9.9-bbbb")).text();
        const oldAgain = await (await fire("/js/app.js?v=9.9.9-aaaa")).text();
        return { old, edited, oldAgain, calls: net.calls.length };
        """,
    )
    assert out == {"old": "build 1", "edited": "build 2", "oldAgain": "build 1", "calls": 2}


@needs_node
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/entries?v=1",
        "/auth/status",
        "/js/app.js",  # unstamped: revalidated by the server, never frozen here
        "/css/00-tokens-shell.css",
        "/documents/export?v=1",
        "/sw.js?v=9.9.9",
    ],
)
def test_nothing_else_is_cached(tmp_path, path):
    out = run_worker(tmp_path, f'return await fire("{path}");')
    assert out == "passthrough"


@needs_node
def test_a_write_is_never_intercepted(tmp_path):
    out = run_worker(tmp_path, 'return await fire("/js/app.js?v=9.9.9-a", { method: "POST" });')
    assert out == "passthrough"


@needs_node
def test_vendor_files_and_icons_are_cached(tmp_path):
    out = run_worker(
        tmp_path,
        """
        for (const p of ["/vendor/d3/d3.min.js", "/vendor/phosphor/Phosphor.woff2", "/icon-512.png", "/manifest.webmanifest"]) {
          await fire(p); await fire(p);
        }
        return net.calls.length;
        """,
    )
    assert out == 4


@needs_node
def test_a_response_that_is_not_a_plain_200_is_not_kept(tmp_path):
    out = run_worker(
        tmp_path,
        """
        net.routes["/js/gone.js"] = () => new Response("nope", { status: 404 });
        net.routes["/js/cookie.js"] = () => new Response("x", { headers: { "set-cookie": "a=b" } });
        for (const p of ["/js/gone.js?v=1", "/js/cookie.js?v=1"]) { await fire(p); await fire(p); }
        return net.calls.length;
        """,
    )
    assert out == 4, "both were fetched twice: neither was stored"


@needs_node
def test_the_shell_is_network_first_and_never_stored(tmp_path):
    out = run_worker(
        tmp_path,
        """
        const nav = { mode: "navigate", destination: "document" };
        net.routes["/"] = () => new Response("the app");
        const res = await fire("/?share_text=hello&share_url=http%3A%2F%2Fx", nav);
        const cache = await caches.open("tessellate-assets-9.9.9");
        return { body: await res.text(), stored: (await cache.keys()).length, called: net.calls };
        """,
    )
    assert out["body"] == "the app", "the network answer, with the share query, untouched"
    assert out["stored"] == 0, "the shell is never cached: it is the empty app offline"
    assert out["called"] == ["http://127.0.0.1:8000/?share_text=hello&share_url=http%3A%2F%2Fx"]


@needs_node
def test_with_the_server_down_a_navigation_gets_the_offline_page_not_the_app(tmp_path):
    out = run_worker(
        tmp_path,
        """
        net.routes["/offline.html"] = () => new Response("<h1>Tessellate is not running on this computer</h1>");
        await lifecycle("install");
        net.down = true;
        const home = await (await fire("/", { mode: "navigate", destination: "document" })).text();
        const index = await (await fire("/index.html", { mode: "navigate", destination: "document" })).text();
        return { home, index };
        """,
    )
    assert "not running on this computer" in out["home"]
    assert out["home"] == out["index"]


@needs_node
def test_the_install_also_keeps_what_the_offline_page_links(tmp_path):
    out = run_worker(
        tmp_path,
        """
        net.routes["/offline.html"] = () => new Response(
          '<link rel="stylesheet" href="/css/00-tokens-shell.css?v=9.9.9-c"><script src="/js/offline.js?v=9.9.9-d"></script><a href="https://x.test/">x</a>');
        await lifecycle("install");
        net.down = true;
        const css = await fire("/css/00-tokens-shell.css?v=9.9.9-c");
        const js = await fire("/js/offline.js?v=9.9.9-d");
        return [await css.text(), await js.text()];
        """,
    )
    assert out[0].startswith("body of") and out[1].startswith("body of")


@needs_node
def test_an_iframe_navigation_is_not_answered_with_the_offline_page(tmp_path):
    out = run_worker(
        tmp_path,
        """
        net.down = true;
        return await fire("/documents/run-sandbox", { mode: "navigate", destination: "iframe" });
        """,
    )
    assert out == "passthrough"


@needs_node
def test_activate_drops_the_old_version_and_the_retired_shell_caches(tmp_path):
    # The legacy `memorymap-assets-*` and `memorymap-shell-*` names are retired
    # with the rename (audit 1029 X28): both go on activate, whatever the version.
    out = run_worker(
        tmp_path,
        """
        await caches.open("memorymap-shell-v10");
        await caches.open("memorymap-assets-1.0.0");
        await caches.open("memorymap-assets-9.9.9");
        await caches.open("tessellate-assets-1.0.0");
        await caches.open("tessellate-assets-9.9.9");
        await caches.open("somebody-elses-cache");
        await lifecycle("activate");
        return { names: (await caches.keys()).sort(), claimed: sw.claimed === true };
        """,
    )
    assert out["names"] == ["somebody-elses-cache", "tessellate-assets-9.9.9"]
    assert out["claimed"]


# --- the offline page -------------------------------------------------------


def test_the_offline_page_says_the_one_true_thing_and_has_a_retry():
    html = OFFLINE.read_text(encoding="utf-8")
    assert "Tessellate is not running on this computer" in html
    assert "Start menu" in html and "launcher" in html
    assert 'id="offline-retry"' in html and ">Retry<" in html
    assert "!" not in re.sub(r"<!--.*?-->|<!DOCTYPE[^>]*>", "", html, flags=re.S), "no exclamation marks"
    assert chr(0x2014) not in html
    assert "<script>" not in html and " style=" not in html, "the CSP refuses both"
    assert 'id="tabs"' not in html and "class=\"tab" not in html, "never the app's chrome"


def test_the_offline_page_script_reloads_in_place():
    js = (FRONTEND / "js" / "offline.js").read_text(encoding="utf-8")
    assert "location.reload()" in js
    assert chr(0x2014) not in js


def test_the_offline_page_is_served_with_current_stamps(client):
    page = client.get("/offline.html")
    assert page.status_code == 200
    assert "not running on this computer" in page.text
    stamps = re.findall(r'(?:src|href)="/(?:js|css)/[^"?]+\?v=([^"]+)"', page.text)
    assert stamps and all(s.startswith(f"{__version__}-") for s in stamps), stamps
    assert "no-cache" in page.headers["cache-control"]


def test_the_offline_page_reaches_a_locked_notebook(client):
    """The page is for the moment nothing else loads; a lock in front of it
    would answer a stopped notebook's owner with JSON."""
    made = client.post("/auth/setup", json={"password": "correct horse battery"})
    assert made.status_code in (200, 201), made.text
    assert client.get("/offline.html").status_code == 200


def test_the_offline_page_is_on_the_locked_routes_allowlist():
    text = (ROOT / "tests" / "test_every_route_is_locked.py").read_text(encoding="utf-8")
    assert '"/offline.html"' in text


# --- the share target -------------------------------------------------------


@needs_node
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("share_text=remember+milk&share_url=https%3A%2F%2Fexample.test%2Fa", "remember milk\n\nhttps://example.test/a"),
        ("share_title=Page&share_text=Quote&share_url=https%3A%2F%2Fe.test", "# Page\n\nQuote\n\nhttps://e.test"),
        ("share_text=see+https%3A%2F%2Fe.test&share_url=https%3A%2F%2Fe.test", "see https://e.test"),
    ],
)
def test_a_share_query_becomes_one_capture(tmp_path, query, expected):
    app = (FRONTEND / "js" / "shared-intake.js").read_text(encoding="utf-8")
    start = app.index("function sharedCaptureText(")
    end = app.index("\n}\n", start) + 3
    probe = tmp_path / "probe.js"
    probe.write_text(
        app[start:end] + f"\nconsole.log(JSON.stringify(sharedCaptureText(new URLSearchParams({query!r}))));\n",
        encoding="utf-8",
    )
    done = subprocess.run([NODE, str(probe)], capture_output=True, text=True, timeout=30, check=False)
    assert json.loads(done.stdout) == expected, done.stderr


def test_the_share_query_survives_the_worker_and_lands_in_capture():
    """`/?share_text=` is a navigation to `/`: the worker's network-first path
    passes it through untouched (asserted above), and app.js switches to the
    Capture box before filling it. The installed app's share action is the
    manifest's `/`, inside the worker's scope."""
    app = (FRONTEND / "js" / "shared-intake.js").read_text(encoding="utf-8")
    intake = app[app.index("function takeSharedIntake()") :][:1800]
    assert 'showNotesSection("capture")' in intake and 'box = $("entry-content")' in intake
    manifest = json.loads((FRONTEND / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["share_target"]["action"] == "/" and manifest["start_url"] == "/"


# --- the install row --------------------------------------------------------


def test_the_install_row_is_in_about_with_its_help_and_stays_hidden_until_offered():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    about = html[html.index('id="settings-about"') :]
    at = about.index('id="about-install-row"')
    row = about[about.rindex("<div", 0, at) :][:1400]
    assert "hidden" in row.split(">")[0], "hidden until the browser offers the install"
    assert 'id="about-install"' in row and "Install as an app" in row
    assert 'data-help-for="about-install-help"' in row
    assert 'id="about-install-help"' in about
    assert "Add to Home Screen" in " ".join(about.split()), "the iPhone path is told in words"


def test_the_install_prompt_is_held_and_the_row_follows_installed_state():
    wiring = (FRONTEND / "js" / "settings-wiring.js").read_text(encoding="utf-8")
    assert 'addEventListener("beforeinstallprompt"' in wiring and "event.preventDefault()" in wiring
    assert 'addEventListener("appinstalled"' in wiring
    assert "(display-mode: standalone)" in wiring and "navigator.standalone" in wiring
    assert "offered.prompt()" in wiring


def test_the_install_row_has_a_guide_topic():
    from tessellate.ai import help_topics_more as more

    topic = next(t for t in more.EXTRA_TOPICS if t["id"] == "install-app") if hasattr(more, "EXTRA_TOPICS") else None
    if topic is None:  # the list's name is not part of this test's contract
        topic = next(
            t for value in vars(more).values() if isinstance(value, list)
            for t in value if isinstance(t, dict) and t.get("id") == "install-app"
        )
    assert "Add to Home Screen" in topic["body"] and "Retry" in topic["body"]
