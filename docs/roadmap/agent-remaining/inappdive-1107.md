# inappdive-1107 (in-app companion and Atlas dive) remaining

Done (driven in a browser, base :8882 against mine :8883, Chromium via Playwright):
- C1/C2 `bfc9c317`: a bar or hang companion looks again 900 ms after a tab switch and steps aside when it covers a control; with no free spot it beats again at 250 ms. The peek face is clipped to the edge strip. Seconds a control stayed covered after a switch: Notes about 6 s to 1.0 s; Chat 7.7 to 9.4 s to 1.5 to 2.3 s; Graph 7.1 to 9.5 s to 1.6 to 2.8 s.
- C3 `ba661be3`: the face has a title and an aria-label that names the right-click and Shift+F10 menu; the menu has a "Quieter" row (becomes "Livelier"); the Guide topic says both.
- C4 `8cdfa44e`: a "Focus companion" palette command, shown only while the companion shows.
- Boot gzip is unchanged (260,814 for base and mine); avatars.js is not in that count.

C11: no fix. The brief said companion-throw.js is boot; it is lazy, and the first fling loads it in about 50 ms.

C6 (restyle count): not fixed, measured. All restyles at rest are reason "Animation" (running CSS and WAAPI animations restyle on every frame, composited or not). Counts per 4 s at rest on one page, pacer on against pacer off, 3 alternations, 2 runs: on 106 91 76 / 78 50 88; off 40 69 134 / 58 76 93. The spread (40 to 134) is wider than any difference, so cutting the pacer's `playState` read or beats is not shown to help. The JS writers are small (Aim batches, tail timers, one flow rebuild per 5 to 9 s, blink classes). A real cut needs fewer running animations on the figure (the `atl-prop` coil loop is paused and stepped by hand because the compositor refuses its svg `scale`, bit 19), which touches the compositor bits 18, 19, 6 and the 7-site composite cap, so it was left.

Not done or not verified:
- C5: done in round 2 (below).
- C7: the pacer pause was not reproduced.
- C8: idle variety; the owner asked for quiet, dropped.
- C9: miffed face, scrabble, pull-up and shake-off not re-driven in a browser.
- C10: reduced-motion and hidden-document runs not re-driven.
- The 390 px phone rAF claim was not verified.
- The C1 fix on Timeline (0 overlap in these runs) and the 25-item menu height were not measured.
- The long-task count should not go into the lag sweep (too noisy).
- The earlier hint toast: it still fires only after 3 days or on first opening Appearance.
- Not measured: the 4x CPU spread.

Port 8881 collided with another agent's server, so mine used 8883 and base 8882.

Round 2 (blind test of 8cdfa44e, 8896 against the merged base 417974af; Chromium via Playwright):
- Fixed: the focus ring (C5 above): a 2px accent outline on the haze's ellipse; pixel contrast against the page at the ring, light 4.74:1 (was about 1.9 analytic), dark 6.8 to 7.0:1; the haze lost its middle stop to pay for the bytes (boot CSS gzip 179,300 = cap, unchanged). Quieter and Livelier now make the companion say "Quieter now." or "Livelier again." (pref went to off in the run) and the row's title names Settings' "Reduce actions". Hide by the menu or by Ctrl+Shift+Y with the face focused leaves focus on the toast's Show it (was BODY); a hide with focus elsewhere moves nothing (measured: stays on the tab page). The menu removes the companion's speech bubble before opening over it.
- Rejected: (1) no hover hint: title is empty until pointerenter, then holds the full how-to (measured); headless Chromium draws no native tooltips, and a fresh data dir has the companion off ("avatar-buddy" default "off", the Appearance nudge covers that), so the report's "on by default" was its own data dir. (3) Enlarge: the dialog is named "Atlas, enlarged" and the figure measured 2.2x (145x206 against 64x92); its 3-item menu inside the card is intended (companion-menu.js, "a place on the page ... mean nothing inside the card"). (6) the perch over the status nav, the hang beside the Local pill and the tucked 390 px head are the perch choices; the control under it still wins the hit test. (7) 12 clicks 120 ms apart are one double-click run (event.detail >= 2 returns, the poke is coalesced): the bubble came 400 ms after the last click ("Breathe."); at 700 ms apart each click answered, and the fifth turned grumpy with "Hmph.".
- Not fixed, naming only: "Companion" and "Atlas look" submenus and the five names for the figure (Atlas, companion, avatar, guide); a wording change across Settings, the Guide and the palette, left to the owner.
- Not verified: forced-colors rendering of the ring (an outline survives that mode by spec; not run), a screen reader, the desktop shell, 390 px touch drag.
- Round 2 warranted: no. Everything that came back was a rejection or a small fix with a measured number; a third pass on this surface would be dry unless the owner names the "five names" copy pass.
