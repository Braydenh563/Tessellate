# Deep audit 2026-10-31: backend (auth, sessions, workspaces, private notes, uploads, backups, limits, concurrency, errors, routes)

Fable suite, surface 8 of 12. Server on 8852 (`serve.sh`, fake model on
11600), notebook of about 530 notes. Two curl probes (kprobe, 60 requests
across every router; a second probe of uploads, bursts, limits, traversal, the
bin and the lock) plus code greps. Observed unless marked code. The 1028
backend audit (`audit-1028-backend.md`, K1 to K38) is re-verified below.

## Rows

| Row | Sev | Kind | Finding | Evidence | Where | Verified | Fix | Size |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BK1 | high | reliability | **A burst of note creations fails.** 24 parallel `POST /entries`: 19 answered 201 and 5 answered 500 after 30 s (`sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 10 reached`). One create takes 60 ms; 12 in parallel all pass in 0.6 to 0.7 s. The engine uses the default pool (5 + 10) with no `pool_timeout`, while sync routes run on a 40-thread pool, so the 16th request waits 30 s for a connection and then dies as a bare 500. A paste-import, a sync from another device or the composer filing a batch can reach this. | probe `19 201 5 500`; `server.log` traceback `manager.py:191` `_find` | `database.py:2320` (engine, default `QueuePool`); `routes_entries.py:821` | run | `pool_size` at least the thread pool's size for SQLite (connections are cheap) or `NullPool`; a `pool_timeout` of 5 s answering 503 "Busy, try again" with `Retry-After`; a single writer lock around creates so waiters queue in order. | S |
| BK2 | med | data | **A note in the bin can be edited.** After `DELETE /entries/{id}` (200) a `GET` is 404 but a `PUT` with new content answers 200 and rewrites the binned note; the client never learns it is editing something it cannot see. | probe `delete 200 get deleted 404 put deleted 200` (ids 2030 and the bin note) | `routes_entries.py` update route (no `deleted_at` guard) | run | 409 "This note is in the bin. Restore it first." (and the same guard on PUT for documents and boards, not verified). | S |
| BK3 | med | security | **Workspace scope trusts any header value.** `X-Workspace-ID: None`, `bogus`, `../x` and junk all answer 200; a note created under `None` (id 2008) is readable from the default workspace and from `/export/json` but 404 from workspace 1; `/chat` raw results include it. The scope is an ORM filter keyed on an unvalidated client header (1028 K16). | kprobe rows `ws None 200`, `ws bogus 200`; `deps.py:382` sets `session.info["workspace_id"]` with no lookup | `core/deps.py:378` to `:400`; `database.py:180` | run | 422 for any id that is not a `Space` row or `all`; store the space id on the session server-side and let the header pick among known spaces only. | S |
| BK4 | med | security | `POST /logs/client` is open without a session (204; 1028 K10): message 2,000 and source 500 characters are capped per line but nothing limits lines per client, so any process on the machine (or the LAN when the server is bound there) can fill the 500-line ring buffer and the terminal for ever. | kprobe `logs/client unauth 204`; `routes_settings.py:2346` `open_router`; `ClientError` fields `:2319`, `:2323` | `routes_settings.py:2346` | run | Require the session token (the page always has it) or keep it open with a per-client budget of 20 lines a minute and drop the rest. | S |
| BK5 | med | reliability | Restore disposes the engine while other requests and jobs may be mid-transaction (1028 K19, still so): `engine.dispose()` at two sites, no drain or pause of the job runner first. | code `routes_backups.py:187`, `:308` | `routes_backups.py` | code | Pause the job runner, wait for in-flight sessions (a counter on `get_session`), then dispose and swap. | M |
| BK6 | med | security | The update installer runs with a host allowlist and a truncation check only, no signature or pinned hash (1028 K5); the check is off by default (`/update/check` disabled here), which bounds it. | kprobe `update/check disabled`; `routes_update.py:71` no verify | `routes_update.py` | code | Ship a public key with the app and verify a detached signature before running anything. | M |
| BK7 | low | security | Session tokens, media tickets, network and device tokens live in plain dicts (1028 K2, K23 open): no lock on `_active_tokens`, lost on restart. The AI key is plain text in `preferences.json` (K11; local-first, 0700 folder). | code `routes_auth.py:85`, `:110`, `:121`, `:802`, `:805`; `config.py:147` | `routes_auth.py`, `config.py` | code | One `threading.Lock` around the token tables; keep the key where it is but say so in Settings help. | S |
| BK8 | low | copy | Validation copy leaks field and library names: a bad reminder time says "Check the due at and try again."; a 5,000-character category says "String should have at most …" (pydantic's text); a too-large document says "Check the content" without the 500,000 limit (code CE3). | probe reminder bad date, category 5k | error mapper in `core/errors.py` (or the router's handler) | run | A field label table ("due time", "name") and the limit in the message. | S |
| BK9 | low | polish | Inconsistent shapes: `/entries/-1` 404 but `/entries/99999999999999999999` 422; `/timeline?offset=-5` 200; `/backups/{name}` DELETE with a traversal name 405 while GET is 404; `OPTIONS` 405 everywhere (no CORS, fine for same-origin). | probe limits block | routers | run | `ge=0` on ids and offsets; one 404 for unknown backup names on every verb. | S |
| BK10 | low | perf | `/library?limit=50` answers 235 KB and `/graph` 289 KB at 530 notes (22 KB gzipped for graph); `/entries?limit=50` 50 KB. Reads are fast here (link-suggestions 92 ms, timeline 113 ms, search 27 ms) but the payloads carry full content per row. | probe timings | `routes_library.py`, `routes_graph.py` | run | Previews (first 200 characters) in list rows; content on open. | S |
| BK11 | low | arch | God modules remain (1028 K24, K25 partly): `routes_whiteboard.py` 6,168 lines, `composer.py` 6,123, `routes_chat.py` 5,878, `routes_entries.py` 4,275 (58 routes, 132 functions), `routes_files.py` 4,193 (54 routes), `manager.py` 3,697; 12 functions over 150 lines (was 18): `_start_tray` 351, `_run_desktop` 325, `_run_skill` 311, `_dispatch_call` 276. Two schema systems (`alembic.ini` plus `_add_missing_columns`, K26); `_within_dir` and `_within_exports` still both exist (K28 partly). 9 `date.today()` sites (K22). | counts | files | code | Split by resource (entries: crud, bin, links, suggestions; files: serve, thumbs, import); one schema path. | L |
| BK12 | low | perf | The page polls `GET /reminders?include_done=false` every minute per tab (1028 K32); 5.6 KB per poll here, a full page of 200 rows when the list is long. | `status.js:544` | `frontend/js/status.js` | code | A `since` parameter answering 304, or ride the `/events` stream the page already holds. | S |

## 1028 backend rows re-verified

| Row | Now | Evidence |
| --- | --- | --- |
| K1 reset without credential | not re-run | reset is through the terminal card (`routes_auth.py:2172`); not driven |
| K2 token store lock | open (code), BK7 | no lock symbol in `routes_auth.py` |
| K3 throttle race | fixed | 8 parallel wrong passwords: 5 x 401, 3 x 429; `_throttle_lock` `routes_auth.py:363`; recovers after 12 s |
| K4 320 MB body cap | fixed for JSON | 40 MB body to `/entries`: 413 in 1 ms |
| K5 installer unsigned | open, BK6 | |
| K6 SearXNG unpinned | fixed | pinned at `searxng_install.py:72` |
| K7, K8 path containment | not verified | code not re-read this pass |
| K9 restore merges preferences | not verified | `backup_bundle.py:221` to `:225` still describes a merge |
| K10 open client log | open, BK4 | 204 without a token |
| K11 plain API key | open, BK7 | `config.py:147` |
| K12 no-store | fixed | `cache-control: no-store` on API JSON |
| K13 MCP without auth | not re-run | |
| K14 restore caps | fixed | `MAX_UNPACKED_BYTES`, `MAX_ENTRIES` 200,000 at `backup_bundle.py:48` to `:52` |
| K15 xmind size trust | not verified | |
| K16 header-only workspace scope | open, BK3 | junk headers accepted |
| K17 async import_ics | fixed | `def import_ics(` is sync at `routes_reminders.py:472` |
| K18 async thumbnail | not re-run | |
| K19 dispose in flight | open, BK5 | |
| K20 sidecar KeyError | fixed | `record.get("file")` `export_folder.py:698` |
| K21 DDL quoting | fixed | `database.py:2981` |
| K22 date.today | open, BK11 | 9 sites |
| K23 plain dict stores | open, BK7 | |
| K24, K25 god modules | open, partly, BK11 | 12 functions over 150 lines (was 18) |
| K26 two schema systems | open, BK11 | |
| K27 dead routes | mostly fixed | one frontend reference left |
| K28 duplicated helpers | partly | `_LOOPBACK_HOSTS` once; `_within_*` still two |
| K29 async mix | open | 6 route files with `async def` |
| K30 link-suggestions cost | fine at 530 notes | 92 ms; not measured at 2,000 |
| K31 entities cost | not verified | empty table here (6 ms) |
| K32 reminders poll | open, BK12 | |
| K33 to K36 | not re-run | |
| K37 no ANALYZE | open | comments only, `database.py:2678` |
| K38 media-link tickets | not verified | a sweep exists (`routes_auth.py:1029`) |

## Coverage

| Area | Driven | Notes |
| --- | --- | --- |
| Unauthenticated access to every router (60 paths) | run | all 401 but `health`, `auth/status`, `logs/client`; no query or cookie token |
| Headers on `/` and API | run | CSP, `X-Frame-Options: DENY`, no-referrer, permissions policy, `nosniff`, `no-store` |
| Lock and unlock | run | `/auth/lock` 200 kills the token (GET and export 401 after); unlock returns `vault_open: true`; throttle |
| Private notes | run | readable while the vault is open; every route 401 once locked (the vault key goes with the session) |
| Workspaces | run | BK3 |
| Uploads | run | `.html` served as `application/octet-stream`, `.svg` as `image/svg+xml`, both `attachment` with `CSP sandbox; default-src 'none'`; thumbs 404 for both; `/media/upload` refuses non-image |
| Bursts | run | 24 writes BK1; 12 writes fine; 24 reads max 0.31 s |
| Limits | run | `limit` 1e9 and -1 are 422; 10,000-character search 200; 40 MB body 413 |
| Backups | run | create 201 in 0.43 s (13 MB); traversal names 404; restore wants JSON `{name}` (multipart 422; bundles have their own route) |
| Bin | run | delete, 404 on read, search excludes, purge 200; BK2 |
| Validation copy | run | BK8 |
| Jobs, events, logs | run | `/jobs` list; cancel of a bogus id 422; `/events` 200 JSON with the token; `/logs` body carries no token or password |
| Reminders, tags, categories, search | run | past due time refused with a clear line |
| MCP server, media links, device tokens, LAN mode, import of zips and xmind, restore under load, 2,000-note timings | not driven | |

## Already good

- Every router refuses a missing token with 401 and the API answers `no-store`; the page has a CSP, frame denial and a permissions policy.
- Locking the app invalidates the token at once; the login throttle holds under parallel attempts.
- Uploaded HTML and SVG are never rendered on the origin: attachment disposition, `nosniff` and a sandboxed CSP.
- Backups create in under half a second; traversal names in backup paths are refused; restore caps exist.
- Oversized bodies are refused in a millisecond; list limits and pin bounds are validated.

## Not verified

- K7, K8, K9, K13, K15, K18, K31, K33 to K36 and K38 (code not re-read or the surface not driven); the bin guard on documents and boards; timings at 2,000 notes (the graph audit measured `/graph` only); whether BK1 reproduces at 16 to 20 parallel writes (threshold not bisected).
