# perch-1104 remaining

- done: code + tests (INBOX 1640): Drop falls back to the chooser, LandNear takes the perch under open air, NextSpot drops a restored float.
- next: nothing blocking. Not verified: a dashboard seeded with real "Most used" notes (the fresh notebook only has the first-steps card); real inference n/a.
- found-not-fixed: avatars.js ~5088 (perch lost), ~5142 (held at a bar) and companion-menu.js ~222 (enlarged preview), ~870 are mid-move or a view's own float, left as they are.
- found-not-fixed: "me" thrown up from y 274 falls 600px straight to the bar (x kept); Atlas thrown up-right ends hanging from the top bar 242px above its rest. Both are the nearest perch, not a float.
- found: scratchpad/ui-sweeps/throwsettle1402.js and the other buddy sweeps set the companion via `#avatar-buddy` before settings-body is built (it is a template now): call settingsBodyBuild() and prefs.set('avatar-buddy', k); syncNameMarkBuddy() instead.
