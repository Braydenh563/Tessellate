# localhost-1110 (HANDOVER owner note "Hello origin": desktop window at localhost)

Done
- Window URL: `__main__.py` `window_host()` (localhost, or `TESSELLATE_LOCAL_NAME`.localhost) and `_window_url(port)`; used by the main window swap, `_open_window_onto` and the companion. The bind stays `HOST = 127.0.0.1`. Host check, `_from_this_computer`, Origin check and LAN mode already accepted `localhost` (security.LOOPBACK_HOSTS, netbind `_LOOPBACK_NAMES`); no change needed. The service worker is per origin and network-first, so it re-registers at localhost untouched. Browser opens (`page_host`, capture hotkey) are unchanged on purpose.
- Carry-over design (chosen over pywebview `evaluate_js`): the shell cannot read another origin's storage without loading it, then must inject into the next page after its load event, with no hook for "loaded" in `load_url`; that timing is unverifiable here and breaks silently. Instead the first open (no `webview/origin-moved` marker in the webview profile) loads `http://127.0.0.1:PORT/origin-bridge.html?to=localhost`: `js/origin-bridge.js` posts every localStorage key except `token` to `POST /origin-handoff/put` (api/routes_origin_handoff.py: this computer only incl. tunnels, one slot, 120 s, 400 keys, 128-char keys, 256 KiB a value, 1 MiB total, memory only), then goes to the same page at localhost, which takes once (`/take` empties the slot), sets only keys it does not hold, writes its own `origin-moved` marker and goes to `/`. `to` must match localhost or `*.localhost`. "Only the app's own keys": the origin and port are the app's alone and its keys are unprefixed, so there is no prefix to filter on; the token is the one exclusion (the new origin signs in itself).
- No boot JS added (the page and script are separate files; boot gzip untouched). Tests: tests/test_origin_handoff.py; test_desktop_launcher.py first-open URL; allowances for the new file in test_prefs_module.py (3 reads, 2 writes) and test_no_bare_fetch.py (1), each with its reason; open routes listed in test_every_route_is_locked.py.

Left
- Real Windows / WebView2 unverified: that the profile at `webview/` keeps 127.0.0.1 storage across launches, that the bridge's two navigations land, and that Hello then shows.
- The marker is written before the bridge loads, so a launch killed mid-bridge does not retry; the settings then start from defaults. Delete `<data>/webview/origin-moved` to retry.
- Drafts or settings written at 127.0.0.1 after the first move (a second copy opened in a browser) do not follow.
- No user-visible text changed (the bridge says "Opening your notebook." for a moment), so no help or Guide edit (order 13).
- done: this commit; next: nothing in this brief.

- done: opener switch, fallback probe, Settings Hello line, tests.
- left: lock-screen line not added (Hello button is hidden on an IP origin, so nothing is offered there); real Windows/WebView2 fallback unverified.
