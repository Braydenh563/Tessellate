# secscan-1011: LAN and phone security scan

The owner, 2026-10-11: "I need maximum trust, proper safe connection, proper
security for the lan and open connection", "even downloading files ... i
just worry that someone coule use that to download malicious files to my
computer", "what if I naively allow a network connection for the lan
connection on say QUT's wifi network??", "do a really deep security and bug
scan". Branch `agent/secscan-1011`, from `gemini/composer-improvements` at 7775d461a.

## Routes, classified (566 audited by walking `create_app()`, scratch script `routes.py`)

| Class | Count | Routes |
| --- | --- | --- |
| Host-only, guarded before this scan | 17 | restore, bundle restore, open-exports-folder, provider, console-mode, restart, extras x3, import/directory, fullscreen POST, shutdown, update apply, SearXNG detect/start/stop/reinstall |
| Host-only, guarded by this scan | 10 | `/files/save`, `/models/pull`, `/models/delete`, `/models/embedding-backend`, `/embedding-models/use`, `/embedding-models/pull`, `/embedding-models/{id}/download`, `DELETE /embedding-models/{id}`, `/auth/lan-certificate`, `/auth/recovery-key/save` |
| Narrower guard (one direction, this scan) | 5 | `PUT /preferences` and `/preferences/import` (13 keys: only tighten), `/auth/lan-access` (on), `/auth/password-on-open` (off), `/update/choice` (yes) |
| Answer differs by device (this scan) | 2 | `GET /health` (`desktop`, `os_notify`, new `this_computer`), `GET /desktop/fullscreen` (`available`) |
| Open before unlock, checked | 9 | `/health`, `/instance`, `/instance/focus` (instance-lock token), `/auth/*` sign-in, `/logs/client`, reminder notification act (scoped token), translate files (allowlisted names), LAN certificate PEM (public) |
| Safe for a phone (notebook data behind the unlock) | rest | entries, documents, boards, chat, search, tags, files and media in the data dir, backups list/create/delete, exports list/download, voice, tasks |

## Findings fixed (tests: `tests/test_other_device_limits.py`, `tests/test_this_computer_only.py`, `tests/test_ui_recipes.py`)

- HIGH: a notebook with no password answered every device. After `/auth/reset` (or a restored backup with no password) the LAN listener stays up until the next launch; measured from a 192.168 client: `/entries` 200, `/auth/setup` 200 (took the notebook). Now 401/403 off this computer, except a container's explicit bind (Brief 40).
- HIGH: `/health` said `desktop: true` to the phone, so the phone wrote exports onto the computer's disk (`/files/save`, any bytes, any extension) and its Open folder opened Explorer here: the owner's report. Now per device, and `/files/save` is host-only.
- MEDIUM: `PUT /preferences` let a phone set `searxng_url` (SSRF to any LAN/localhost host, path `/search`), `export_save_dir` (where files land), auto-update on and its channel, SearXNG autostart, semantic auto-install, web search on, local-only AI off, session lifetime up, console/tray/window behaviour. Now only the safe direction from another device; import skips them with a reason.
- MEDIUM: model and embedding-model downloads (any Ollama name or Hugging Face repo, GBs to disk) and removal from a phone. Host-only.
- MEDIUM: recovery-key save opened a native Save dialog on the computer from a phone; LAN switch on, certificate regenerate, password-on-open off, update choice yes from a phone. Host-only.
- LOW: no HSTS on the https port; added (https only, never on loopback).
- LOW: phone Quit showed "MemoryMap has stopped" when the server had refused; now toasts the refusal. Phone full screen POSTed to the desktop toggle and got 403; `GET /desktop/fullscreen` now says unavailable to another device.

Verified already in place (no change): path containment on exports, media, backups delete, import reports, translate files (9 traversal cases in the test); webclip and web reader pin public addresses on every hop; media cookie `HttpOnly; Secure` on https; `SameSite=Strict`; Origin check on state-changing methods; CSP with `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: no-referrer`; auth is the `X-Auth-Token` header (not a cookie), so cross-site requests carry no credential; sessions 12 h idle, 7 days absolute; LAN binds only with a password.

## Found, not fixed

- MEDIUM (lansafe's lines, not edited here): `POST /auth/lan-options` lets a phone with the password turn "Allow on any network" on and "Ask before a new device signs in" off, and `/auth/lan-networks/allow` lets a phone allow the network it is on. Recommend `this_computer_only` on the looser direction of both, as `answer_device` already does. `forget_network` and `forget_device` (tighten only) are fine from a phone.
- MEDIUM: QUT wifi. Base has no allowed-network gate: once LAN mode is on, the https port listens on every network the laptop joins, protected by the password, the login throttle, and the name-constrained certificate. lansafe-1011 adds the gate (unknown network: nothing reaches the notebook until Allow on this network) and per-device Allow/Deny. Beyond it: (1) client isolation is common on campus wifi, so the gate's network identity (gateway MAC/subnet) should not treat "no gateway seen" as a known network; (2) recommend LAN mode turn itself off after N days unused. (Fixed here: turning LAN on now refuses a pre-floor password under 8 characters, which unlock still accepts.)
- LOW, not fixable without remaking a decision: semantic auto-install (default on, the owner's choice) can be started by a failed embed that a phone's note save triggers. It installs a fixed PyPI package, never one the phone names, and a phone can turn the switch off but not on.
- Fixed in the second commit: `/models/bench/budgets?live=true` (replays fixed GETs to 127.0.0.1 with the caller's token, so they looked local) is this computer only; the model cards' Download is dimmed and Remove toasts the reason on another device; the backup list's Restore is left out there; `#custom-download` is marked.
- Measured (Playwright at 390, `X-Forwarded-For: 192.168.0.50` against :8893): `data-other-device=1`, 12 note lines, `#quit-btn` display none, a marked button's opacity 0.5 and its `?` 1, `desktopShell()` false; a press on Install new versions automatically left it unchecked, toasted the refusal, and sent 0 requests. The computer's own page: no attribute, 0 notes, opacity 1. `test_lan_mode_end_to_end` over a real socket and TLS: `this_computer` false and HSTS on the LAN port.
- Not verified: a real phone on a real LAN (iPhone Safari); lansafe merged on top.

## Progress

- done: 6a9a34a3a (guards, /health per device, preferences, no-password, HSTS, recipe), 975d2caf9 (live bench, model cards, backup Restore), 0808fc81e (three base-drift test failures). Targeted run: the 98 test files naming a touched route, `-n 2`; 7 failed, 5 fixed in 0808fc81e, 2 (and 40 errors) were the disk filling (`out of disk space`) and pass on rerun.
- next: nothing on this branch. Left for lansafe's merge: the looser direction of `/auth/lan-options` and `/auth/lan-networks/allow` gets `this_computer_only`.
