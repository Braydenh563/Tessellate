# xleft-1031 (audit-1031-extras Z4, Z7, Z10, Z13, Z18)

Done
- Z7 d5a9d0f: `announceSavedNote` (quick-note.js) is the one announcement for a note that reached the server: Open toast, list refresh, filing watch, Undo, focus back to the opener (the current tab's button when the opener is gone or hidden); a boot-file stand-in in app.js (paid for by dropping the dead `renderMcpSnippet` stand-in) because the bundle is lazy. Sketch, web page and picture text use it; the quick note and capture card already did. Measured at 1440: toast "Sketch saved to your notebook." with an Open button, focus `tab-btn-notes` (was `BODY`), Open lands on `#/notes/N`.
- Z4 b157b4a: the bell records a finished job only when it failed or `origin` is "you" (`taskEndingIsAppsOwn`, chat-tasks.js); a Started row still settles first. Night shift says "read 207 notes and 21 boards" (`describe_night_pass`). Fresh profile: 8 bell rows before, 0 after.
- Z13 916f95e: most of it was already in (02c533a: the `focusin` memory and the Attach or Open offer). Live at 390: a box focused before the sheet pastes (`[[Sketch...]]` in the capture card). Added: a remembered box no longer on screen is not pasted into.
- Z18 405fbdc: `bgArtCalm` after 30 s with no pointer move, press, wheel or touch (keys do not count): 12 fps. Measured: 30 draws a second, 12 after the stamp aged 31 s, 30 after a pointer move.
- Z10 (this file's last commit): the closure is not lifted. The complexity ratchet reads Python only (`tests/test_complexity.py` seed has no .js row), and 22 of the 163 top-level names would clash with app globals (`icon`, `h`, `say`, `open`, `undo`, `build`...), breaking "reads nothing global". `scripts/codemap.py` now lists the functions of any script wrapped whole in one closure: sketch-pad.js 0 to 143, boot-guard, capture, clip, desk-companion, standalone-undo too.

Left
- tests/test_undo_coverage.py `meetings.js:meetingTakeFinish` (line 726) fails on the base too (not mine; needs an Undo or an EXEMPT reason).
- A JS complexity measure (none exists) would be the way to hold sketch-pad.js functions at 15 or below; none of the 143 was measured.
- bg-art.js, tour.js, meetings.js splits named in Z10 are untouched.
