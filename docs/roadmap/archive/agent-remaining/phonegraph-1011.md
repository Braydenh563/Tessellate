# phonegraph-1011 (Sonnet), remaining

Done: cd93e1790 (883, 884: node panel one row on phone, labelled, kebab), 440049848 (885: sheet never focuses a select under touch), notifications 874 (see git log).

Left:
- INBOX 883, 884, 885 and 874 are not numbered items in this branch's `docs/roadmap/INBOX.md` (874 appears only in the "Placed" log), so `inbox_resolve.py` was not run; the orchestrator moves them to HISTORY with the measured lines (graphpopupphone.js, graphgearphone.js, notif874.js).
- Not verified: a real iPhone Safari (the select picker opening on script focus is Chromium emulation evidence plus the owner's report); the compact row on a tablet with `(hover: none)` at 600+ wide.
- `scratchpad/ui-sweeps/notif1005-sweep.js` still reads a `.notif-side` element that no longer exists (stale before this work); its checks of controls on the title's centre line no longer apply. Replace with `notif874.js` or rewrite.
- Other icon-only rows on the phone with no labels (not touched): the whiteboard toolbar and the selection dock; sweep with `touch.js` for tooltip-only controls.
