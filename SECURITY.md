# Security policy

## Tessellate's security model, in short

Tessellate is a **local-first, single-user app that runs on your own
machine.** By default it listens on `127.0.0.1` only, so nothing on your network
can reach it, and it never sends your notes to the cloud. Your data lives in a
folder on your disk (`data/` beside a source checkout, or your per-user app
folder when installed). Access to the app is gated behind a password you choose
on first run (bcrypt-hashed, stored locally). On a computer only you use, you can
turn the sign-in off; another device and your private notes still ask for the
password.

Letting another device in is a switch you turn on yourself (Settings, Account &
security). It always requires the password, and the network side is HTTPS with a
certificate generated on your computer. [`docs/PRIVACY.md`](docs/PRIVACY.md)
describes this, what can touch the network, and the browser protections in full.

Because of this design, the most important protections for your notes are the
ones your operating system already provides:

- **Encryption at rest.** The database is a plain SQLite file. If your notes are
  sensitive, enable full-disk encryption (BitLocker on Windows, FileVault on
  macOS, LUKS on Linux). SQLCipher is deliberately *not* bundled: it needs a
  native dependency on every platform for a single-user local file, and disk
  encryption covers the same threat more simply. What the app encrypts on its own
  is **private notes**: AES-GCM under a key derived from your password with
  scrypt.
- **Secrets.** A model API key and the MCP tool server's token are kept in
  the operating system's protected store (Windows DPAPI, the macOS Keychain,
  the Linux Secret Service), or where there is none in owner-only files under
  `secrets/` in the data folder; never in `preferences.json` or a backup.
- **Backups.** The app takes a daily local snapshot into your data folder, and
  Settings can write a full backup, which you can seal with a password. A
  snapshot or an unsealed backup is as sensitive as the database, so keep it
  somewhere you trust.

## Phone and other devices

Off by default. When you turn on "Allow other devices on this network"
(Settings, Account & security, with your password), this is what holds:

**Protected**

- **Encrypted on the network, always.** Other devices reach a separate HTTPS
  port (TLS 1.2 or newer). Plain http on that port only answers with a
  redirect to https; the app itself is never served unencrypted off this
  computer. The plain-http port stays on `127.0.0.1`.
- **A certificate made on this computer.** A small certificate authority in
  `lan-tls/` (folder 0700, keys 0600, re-checked at every start, never in a
  backup) signs the server certificate. It is name-constrained to private
  addresses, `.local` and this computer's own names, so even a stolen key
  cannot vouch for a bank's site on a phone that trusts it. Settings and the
  terminal show both SHA-256 fingerprints: compare them with what the phone
  shows before you trust it.
- **Only networks you allowed.** The port is open only on a network you
  allowed from this computer, only to private or link-local addresses, and
  it closes when the computer moves elsewhere or goes unused for 14 days.
- **The password, and this computer's yes.** Every device signs in with the
  password (eight characters or more before the switch turns on). A new
  device is then held until you press Allow on this computer. Wrong
  passwords earn growing waits per device (an IPv6 device by its /64, so it
  cannot dodge them by changing address) and across all devices together.
- **No browser tricks.** A page on another site cannot use your browser to
  reach the app: the Host check refuses a name that is not this computer's
  (the `TESSELLATE_LOCAL_NAME` `.localhost` name only from this computer
  itself), the Origin check refuses requests another site caused, and the
  session is a header, not a cookie. The one cookie, for pictures and files,
  is `HttpOnly`, `SameSite=Strict` and `Secure` over https.
- **The computer stays the computer's.** A device on the network reads and
  writes notes. It cannot turn the network on, allow a network or a device,
  change where files or backups land, point the app at another server,
  install, update, restore, use the PIN or reset the password.

**Not protected**

- **A lost phone that is still signed in.** Its session lasts until it is
  idle for your sign-in timeout (12 hours by default) and at most 7 days. On
  this computer, Remove the device (Other devices) or choose Lock everywhere
  now; changing the password also ends every other session.
- **Someone who knows your password** and whose device you allowed. Private
  notes open on a device that gave the password.
- **Trusting the warning without comparing fingerprints.** The first visit
  before the certificate is installed can be intercepted on a hostile
  network; the fingerprint check is what tells you it was not.
- **A typed `http://` address on a hostile network**, before the phone has
  seen the app over https once: the redirect itself can be intercepted.
  Open the `https://` address or the QR code Settings shows.
- **A device with the password can still read everything it is shown**, and
  can see that this notebook exists on the network (the version on
  `/health`).

## Threat model

What this app protects, where the lines are, who might try to cross them, and
what stops each attempt. Every mitigation names the code or the test that
holds it (tests in `tests/`, code under `src/tessellate/` or `frontend/`); a
**gap** names its open row in `docs/roadmap/LEDGER.md`. Written 2026-11-14
(L-world-class-18); a change to a boundary changes its row here.

**Assets.** The notes, documents, boards and attachments (the SQLite file and
the data folder); private notes and private spaces, and the key that opens
them; the password and the sessions it grants; secrets (a model API key, the
MCP token, the LAN certificate authority's key); backups and exports; and the
computer itself, which the installers, the code runner and the file readers
all touch.

**Trust boundaries.**

1. **Localhost**: the browser and this server on `127.0.0.1`, with other
   sites' pages open in the same browser.
2. **LAN mode**: other devices on a network you allowed, over HTTPS.
3. **Private notes and private spaces**: sealed text inside the same file.
4. **Model output**: whatever a model writes, shown on the page or turned into
   a tool call.
5. **Web search and fetched pages**: text from outside, and addresses the
   server is asked to reach.
6. **Imported files**: uploads, imports from other apps, attachments.
7. **The MCP tool server**: an outside client acting on the notebook.
8. **Downloads that run code**: updates, extras, models.

**Attackers.** A page open in another tab (cross-site requests, DNS
rebinding); a device on the same network; someone with the computer, its disk
or another account on it; the author of a web page, a clipped page or an
imported file (prompt injection, crafted files); the model itself, by mistake
or because something steered it; a local process or MCP client; whoever could
tamper with a download.

| # | Threat | Boundary | What stops it | Status |
| --- | --- | --- | --- | --- |
| T1 | Another site's page sends a request to the app | 1 | The Origin check refuses it before anything reads it (`core/security.py:331`; `test_a_request_from_another_site_is_refused`, `test_a_write_from_another_site_is_refused_too`, `test_the_null_origin_of_a_sandboxed_frame_is_not_trusted`); the session is a header, not a cookie | Mitigated |
| T2 | A DNS-rebinding page reaches the loopback port as same-origin | 1, 2 | The Host check refuses a name that is not this computer (`core/security.py:102`; `test_a_name_that_is_not_this_computer_is_refused_on_loopback_too`, `test_a_non_loopback_host_header_is_refused`) | Mitigated |
| T3 | Guessing the password | 1, 2 | Growing waits per device and overall (`api/routes_auth.py:519`; `test_wrong_passwords_earn_a_growing_wait`, `test_wrong_passwords_for_the_switch_are_throttled_like_an_unlock`); a large body before sign-in is refused unread (`core/security.py:211`; `test_a_huge_body_before_sign_in_is_refused_unread`) | Mitigated |
| T4 | A session token outlives its device | 1, 2 | Idle expiry and a hard cap (`test_a_token_left_alone_too_long_stops_working`, `test_a_token_kept_busy_still_expires_eventually`); expiry drops the private key too (`test_expiry_forgets_the_private_note_key_too`) | Mitigated; a lost phone still signed in is under "Not protected" above |
| T5 | Script injected through a note, a title or model text | 1, 4 | The CSP refuses inline script and style (`core/security.py:468`; `test_the_policy_refuses_inline_script_and_style`, `test_the_policy_closes_the_usual_bypasses`); no `innerHTML` built from values (`test_no_innerhtml_assignment_interpolates`); Markdown is built as DOM nodes (`renderMarkdown`, `frontend/js/navigation.js:381`); every link goes through `safeHref` (`frontend/js/notes-list.js:815`; `test_every_url_sink_the_audit_named_goes_through_safe_href`) | Mitigated |
| T6 | Model output smuggles data out in an image or a link | 4 | The CSP names no remote host, so no remote image or request is made (`test_the_policy_names_no_remote_host`) | Mitigated |
| T7 | Eavesdropping or interception on the network | 2 | HTTPS only, with a certificate made on this computer (`test_a_new_address_gets_a_certificate_that_names_it`) | Mitigated; the first visit before the fingerprint check is under "Not protected" above |
| T8 | A device on the network does what only this computer should | 2 | Off by default and bound to loopback (`test_it_is_off_by_default_and_binds_loopback`); turning it on needs the password and cannot come from preferences (`test_turning_it_on_needs_the_current_password`, `test_put_preferences_cannot_turn_it_on`); a new device is held until allowed here (`core/lantrust.py:731`); admin routes are this computer's only (`api/this_computer.py:46`; `test_the_phone_cannot_turn_the_network_on_or_remake_its_certificate`, `test_a_phone_cannot_loosen_the_lan_options_or_allow_a_network_even_with_the_password`); an untrusted network stays closed and the mode ends after 14 days unused (`test_a_network_marked_untrusted_stays_closed_even_with_any_network`, `test_lan_mode_switches_itself_off_after_fourteen_days_unused`) | Mitigated |
| T9 | Private words read from the disk, a backup or an export | 3 | AES-GCM under a scrypt-derived key (`core/crypto.py:59`, `:137`; `test_the_private_note_key_uses_a_slow_kdf`, `test_everything_in_a_private_space_is_ciphertext_at_rest`); going private scrubs the plain words (`test_making_a_note_private_leaves_none_of_its_words_in_the_file`, `test_a_backup_and_the_export_zip_carry_none_of_its_words`) | Mitigated |
| T10 | Private notes opened by a session that never gave the password | 2, 3 | Per-session grants (`VaultScope`, `api/routes_auth.py:188`; `test_a_network_unlock_does_not_open_private_notes_for_a_session_without_a_password`, `test_the_vault_stays_locked_with_an_auto_session`); the AI reads a private space only from a chat opened inside it (`test_the_ai_reads_a_private_space_only_from_a_chat_opened_inside_it`) | Mitigated |
| T11 | A space taken for a wall between people | 3 | A space organises; it is not a boundary (Scope notes below). The guard only refuses a request that names no space (`SpaceGuard`, `api/app.py:1201`) | By design |
| T12 | Text from outside steers the agent to send data out or change notes | 4, 5, 6 | Outside text arrives fenced under a rule saying so (`ai/fence.py:56`; `test_an_instruction_in_a_note_arrives_fenced_under_a_rule_that_says_so`, `test_a_note_cannot_close_its_own_fence`); once a turn has read outside text, every outbound and write tool parks for a confirm (`ai/agent_policy.py:1301`; `test_after_a_web_read_every_write_parks`, `test_an_imported_note_found_by_search_taints_the_turn`, `test_an_instruction_in_a_web_result_is_fenced_and_cannot_reach_out_or_delete`) | Mitigated for actions; the words of an answer can still be steered, so read an answer drawn from the web as the web |
| T13 | An injection plants a standing instruction for later turns | 4, 5 | A remembered preference is only proposed until you accept it (`ai/tools/tool_learn.py:80`); `save_skill` is a write and parks in a tainted turn (T12) | Mitigated |
| T14 | The model deletes or overwrites by mistake | 4 | A destructive tool always parks with a card (`test_a_destructive_tool_under_the_limit_is_parked_with_a_card`) | Mitigated |
| T15 | The server is made to reach this machine or the local network (SSRF) | 5 | One guard for every outside address (`core/security.py:981`, `:828`; `test_the_guard_refuses_every_way_in`, `test_reader_refuses_a_link_that_points_at_this_machine`, `test_reader_refuses_a_redirect_into_the_local_network`); the address checked is the one connected to (`test_the_checked_address_is_the_one_connected_to`); every module that reaches the network is listed (`test_every_module_that_reaches_the_network_is_written_down`); the local search engine listens on loopback only (`test_searxng_is_published_to_loopback_only`) | Mitigated |
| T16 | A fetched page carries script into the reader | 5 | The reader keeps text and structure only (`test_reader_strips_scripts_and_markup`) | Mitigated |
| T17 | An uploaded file runs as script, or a stored name escapes the folder | 6 | Anything but a picture or a PDF is served as `application/octet-stream` under a `sandbox` policy (`api/routes_files.py:214`; `test_an_attachment_is_never_served_as_script`); `test_a_stored_name_outside_the_folder_is_not_served` | Mitigated |
| T18 | A zip, XML or Word bomb exhausts the machine | 6 | Unpacked-size caps (`entry/app_import.py:55`, `api/wb_import.py:404`, `core/docview.py:334`; `test_a_zip_too_large_unpacked_is_refused`, `test_an_evernote_file_with_an_entity_bomb_is_refused_not_expanded`) | Mitigated |
| T19 | A crafted PDF, Word file or picture exploits a parser | 6 | Size caps only; pypdfium2, markitdown, Pillow and the OCR readers run inside the server process | **Gap**: L-world-class-321 |
| T20 | Code in a code document escapes its runner | 6 | An opaque-origin sandbox with no network and its own policy (`api/run_sandbox.py`; `test_the_policy_is_an_opaque_origin_with_no_network`, `test_the_apps_own_policy_is_not_widened_for_it`) | Mitigated |
| T21 | An MCP client reads or changes more than it should | 7 | A per-notebook token (`mcp_server.py:112`; `test_a_client_without_the_token_is_refused_and_one_with_it_is_served`); reads only until the writes switch is on (`test_a_client_sees_only_readers_until_writes_are_switched_on`); no destructive tool, even by name (`test_no_destructive_tool_is_offered_or_run_by_name`); private notes never listed (`test_a_private_note_is_neither_listed_nor_readable`) | Mitigated |
| T22 | A tampered update | 8 | A digest and a pinned signing key (`test_a_download_that_does_not_match_its_digest_is_never_started`, `test_a_pinned_key_requires_a_valid_signature`) | Mitigated |
| T23 | A tampered extra or model file | 8 | Downloaded extras are https with a pinned sha256 (`test_every_download_is_pinned_https_with_a_sha256_and_a_size`, `test_a_hash_mismatch_is_refused_and_nothing_is_kept`); pip is only given names from the allowlist (`api/routes_settings_extras.py:63`). The pip extras carry no version bound or hash, and embedding weights are checked by size only | **Gap**: L-world-class-320 |
| T24 | Secrets leak into a backup or a log | all | No key file or API key in a backup (`test_the_full_backup_zip_carries_no_key_file_and_no_api_key`); the OS store or an owner-only file (`test_without_a_keyring_the_key_is_an_owner_only_file`); a password in a model address is never logged, and a value cannot forge a log line (`test_a_model_address_typed_with_a_password_is_logged_without_it`, `test_a_logged_value_cannot_forge_a_second_line`) | Mitigated |
| T25 | Another account or process on this computer | 1 | The data folder is its owner's only (`test_the_notebook_folder_is_private_to_its_owner`). The loopback port answers every local account, and with sign-in off a loopback caller gets a session (`test_a_loopback_caller_gets_a_session_without_a_password`) | Accepted: sign-in off is for a computer only you use |
| T26 | Someone with the disk reads ordinary notes | 3 | The app does not encrypt the database; full-disk encryption is the answer (above) | Accepted, by decision |
| T27 | A tampered build in CI | 8 | Not yet: the workflows' actions are not pinned to a commit | **Gap**: L-general-2 |

## Supported versions

This is an actively developed `0.x` project. Security fixes land on `main` and
ship in the next release. Please run the latest release, or the latest `main`.

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Report privately using GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability):
go to the repository's **Security** tab, then **Report a vulnerability**.

When you report, please include:

- what the issue is and where in the code it lives, if you know;
- steps to reproduce; and
- the impact you think it has.

You will get an acknowledgement, and we will work with you on a fix and a
disclosure timeline. Thank you for helping keep Tessellate safe.

## Scope notes

The app is single-user and local, so multi-tenant data leaks do not apply. Web
threats still do, because a page open in another browser tab can send requests to
`localhost`. A **space** is a way to organise notes, not a security boundary: the
app narrows what a request sees by the `X-Workspace-ID` header the page sends, so
anyone who can reach the app can read every space, and a private note's protection
is its key, not the space it sits in. The areas most worth scrutiny are:

- the unlock and sign-in flow, sessions, and the wait after wrong passwords;
- the origin and Host checks, the Content-Security-Policy, and the cross-site
  protections that stop another tab or a DNS-rebinding page reaching the app;
- LAN mode: the switch, the self-signed certificate and what a device on the
  network can reach;
- private notes: the key handling, and anything that could leave their words
  readable in a backup, the search index or a saved answer;
- file upload handling and how attachments are served;
- the opt-in web paths (web search, the reader view, page clipping), their
  address checks, and text from outside reaching the agent;
- anything that could let the agent's tools act without the required
  confirmation;
- the MCP tool server (`docs/MCP.md`): its per-notebook token, and the switch
  that lets an outside client change notes (off by default);
- the installers for optional packages and the update path, which download and run
  code.
