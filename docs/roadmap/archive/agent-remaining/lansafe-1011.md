# lansafe-1011: Brief 102 (INBOX 867), LAN safe by default

Owner: "what if memory map is open to lan on a public network or wifi?? ...
Just make sure everything is handled for the user automatically with
possible manual overrides or alterations"; "can this be better styled and
easier to read??" (the receipt and Other devices address lists).

## Done

- f940fad8d: LAN port refuses a client not on this network (private,
  shared, link-local, this computer's own addresses, its global IPv6 /64s).
- 502c138d5: core/netid.py (Linux /proc, macOS route/arp, Windows one
  PowerShell call with a route print + arp fallback; every command timed;
  failure reads as unknown) and core/lantrust.py (allowed networks, held
  devices, closed defaults on a damaged file).
- cb46444e0: the gate in lanserve and the launcher, the routes, the held
  unlock, netbind.describe ordering; real-socket and launcher e2e tests.
- 1b96f48cf: renderLanAddresses (one renderer, Settings and the receipt),
  lan-watch.js (Allow/Deny toast and bell), Settings lists and options,
  the lock screen's Install the certificate, help, DESIGN.md recipe.
- 19d3155c5: merge of the working branch (next-free-port kept with the gate).

Measured (scratchpad/lansafe-ui.js, 1440 and 390, light and dark): main
address 18.4px mono at 1440, 14.72px under 600px (one line at 390); no
clipping of four addresses folded; toast 1.1 to 1.5 s after the phone's
request; the held phone's token about 1.1 s after Allow; lock-screen link
44px tall, its ? 44x44, no page overflow at 390.

## Left

- QR code of the address: not built (scripts gzip budget had 1 byte left
  before the merge; `frontend/js/status.js` startReminderWatch hook).
  Would go in a lazy file with a vendored encoder if the owner wants it.
- Not verified: a real iPhone (profile install, trust steps), Windows'
  Public/Private category (parsed from fixture JSON only), macOS readers
  (parsed only), Chromium over the LAN address in this sandbox (reset before
  accept(); curl and python reach it, so the phone flow was driven by curl
  and the lock card measured on loopback with data-lan set).
- A network change takes up to 30 s (lanserve.REFRESH_SECONDS) to close or
  open the port.
- Pending device requests live in memory (lantrust._pending, 10 minutes);
  a restart forgets them, and a device that asked and went away still shows
  a notice until then (Allow then lets its next Unlock in).
- The phone's lock screen does not retry by itself after Allow: the server
  holds the request 45 s, then says to press Unlock again.
- Found, not mine: a sticky toast sits under an open modal (the first-run
  "Check for updates automatically?" confirm, z-index 2100), so Allow cannot
  be clicked until the dialog closes; the bell and Settings still work.
  Settings at 390: the sticky "Account & security" header with "Reset 1
  change" covers the first row's text while scrolled.
- Stray files from this run at the filesystem root: /lansafe-gz.py,
  /lansafe-tf.txt (removal was refused by the sandbox).
- SESSION_BRIEFS Brief 102: the Built block move to HISTORY is the
  orchestrator's at merge.
