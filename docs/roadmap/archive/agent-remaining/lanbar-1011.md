# lanbar-1011: the LAN icon in the status bar, live on and off

The owner, 2026-10-11: "the outgoing lan connection should have a hotkey,
and should also be easily accessible ... an icon and popup window available
from the bottom status bar", "its status of open or close should change if
the user loses wifi or mobile data connection and or moves to an untrusted
network", "view a list of trusted and untrusted networks and be able to
manage it", and "I need maximum trust, proper safe connection, proper
security for the lan and open connection". INBOX 892, 894, 896, 900;
secscan-1011's leftovers. Branch `agent/lanbar-1011`.

## Progress

- done: 56b04344a merge of agent/secscan-1011 (six conflicts, both sides kept).
- done: 10e4cf6ff backend: `core/lanlive.py` supervisor (on and off live, INBOX
  900), certificate re-issued on an address change (892), incoming phone
  connections on the privacy receipt (894), `this_computer_only` on the looser
  lan-options and network allow, a phone's semantic install deferred to this
  computer (`core/origin.py`), the 14-day switch-off.
- done: e53a3fbe7 status bar icon `#status-lan` and panel (896): help popover
  at 1440, sheet below 600, Alt+L, palette row, STATUS_SLOTS, PHONE_STATUS_ROWS,
  Settings untrusted list, Guide topic `lan-networks`.
- done (this commit): Forget refused from another device, the sheet's double
  title, hotspot wording (892 resolved), CHANGELOG both copies, tests.

## Measured (Chromium, port 8794, the real launcher)

- 1440 light and dark: icon 28x28 at 1209,868; off muted (102,100,95 light,
  181,179,173 dark), open --ok (16,101,60 / 74,222,128), closed --warn
  (138,80,3 / 251,191,36). Popover 384 wide, in view, no x-overflow. On,
  Stop trusting, Trust (password), Alt+L, Off: each repaints the icon; the
  LAN uvicorn starts once on and shuts down on off. No page errors.
- 390: the header More row opens the sheet (390x338 off, 432 on), the same
  round trip, no errors.

## Remaining

- Not verified: a real phone, a real wifi drop or hotspot join (netid is the
  sandbox's 192.0.2.1 router), Windows' public-network category.
- Turning LAN mode off from a phone is still allowed (it only lets fewer in,
  and signs that phone out); every other LAN control refuses with REFUSAL.
