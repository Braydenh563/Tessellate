# throw-lag-1107 remaining

- done: landing surfaces taken in the release (avatars.js `nameMarkBuddyTakeSurfaces`, companion-throw.js `companionThrowPlan`); header token first call removed (phone-shell.js `initHeaderHeightToken`).
- not verified: the owner's 5956 ms (Windows, real hardware) does not reproduce at 4x CPU here; `phone-shell.js write` 132 ms at boot was not measured on a cold start, only that `--header-h` is still set (2.75rem).
- left: a landing after the window returns from the tray still bills the first layout to the first read (INBOX 1667, 2026-11-04 12:00): snapshot is now taken at release, so only the release pays it; measure a restore with the window hidden for a minute.
- left: the throw scroll part of 1667 is separate and untouched.
