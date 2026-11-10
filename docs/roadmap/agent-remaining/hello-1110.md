# hello-1110 (INBOX 1727, Windows Hello unlock)

Done
- f964a5f7f server: core/webauthn.py (ES256/RS256, CBOR subset, origin, RP id, UV, sign count), core/hellostore.py (PRF-wrapped vault key in the OS store, bound like the PIN, single-use 120 s challenges), api/routes_hello.py (`/auth/hello/enrol/begin|finish`, `/begin`, `/unlock`, `/forget`), `/private-spaces/unlock-hello`; every `pinstore.forget` also drops Hello (guarded by a test).
- UI commit: hello-unlock.js in the privateSpaces lazy bundle; lock-screen button (boot hook in app.js `showLockScreen`), private-space card button, Settings, Account & security switch with `data-help-for`; `lockOpened` split out of `submitLockForm`; Guide topics updated.
- Measured (Chromium virtual authenticator, hasPrf): enrol, lock-screen unlock (vault open), private-space unlock, ordinary prompt hides it, 127.0.0.1 hides it, switch off. Boot JS gzip 251,978 before, 251,893 after.

Left
- Real Windows Hello is unverified, and so is WebView2 (the desktop window) offering WebAuthn PRF at all.
- The desktop window opens `http://127.0.0.1:PORT` (`__main__.py` HOST, `page_host`), and browsers refuse an IP address as an RP id, so Hello is hidden there: the window would have to open `localhost` (or `TESSELLATE_LOCAL_NAME`.localhost) for Hello to show. Changing that moves every window's saved settings (origin-keyed localStorage), so it is a decision for the owner, not taken here.
- "Settings, Privacy" in the decision was read as the Privacy and security group: the switch sits in Account & security under the PIN, where the PIN is. Moving it to the Privacy page ("Where your data went") is one line in hello-unlock.js `mountSettings`.
- A platform credential made by an abandoned enrolment stays on the authenticator (no `signalUnknownCredential` call yet).
- done: f964a5f7f, 7d4b051fa, INBOX 1727 resolved to HISTORY; next: nothing in this brief (the Left list above).

- Owner decision 2026-11-10: the desktop window moves to http://localhost and copies the 127.0.0.1 browser storage across on first open (no reset). Not built yet.
