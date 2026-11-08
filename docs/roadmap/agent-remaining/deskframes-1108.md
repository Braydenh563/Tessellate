# deskframes-1108: the desk frames re-rendered (INBOX 1696 x, w, z, hh; atlasm-1108 step 5)

## Done

- Render fixed (`scripts/render_desk_frames.js`): every frame's live tail (`atlasTail`) sits at one moment (the idle
  loop's start for a non-idle frame), the breath and lower-wisp skew too; the rig's own CSS sways (`atl-sway*`,
  `atl-lw-sway*`) are held mid-swing and the other non-act CSS animations at 0, so `at` (the act's moment) no longer
  moves the lower body (stand, blink, look, wave and land were 5 to 7 px apart); the page's blink clock is stopped
  and its `atl-blinking` classes removed (a masculine `stand` shipped with shut eyes). Walk tail and skew: see step 2 below.
- `render_desk_frames.py`: `clip_idle_tails` clips the stand, blink, look and idle frames to one lowest row.
- Frames re-rendered, both looks: 54 files each (56 names less the 2 card frames); masculine 289x304, feminine
  275x298 at the last render (the crop box moves per render: re-measure `LID_EYES` after every render).
- `LID_EYES` measured from the mouth ink (MOUTH_DOWN 13 below the eye line): masculine (110,109,155,125), feminine
  (112,110,157,126) after the last render.
- `faces.py` mouth (INBOX 1696 hh): the calm mouth is painted out from the skin either side of it, row by row, with a
  feathered edge, not a flat disc of the between-the-eyes tone (35 to 63 levels off the face, 10 to 13 now).
- `capture.CAPTURED` leaves out the optional wave frames; `complete()` needs CAPTURED plus the cards.
- Tests: `tests/test_overlay_deskframes_1696.py` (eyes open in stand and the eye box on them, the mouth patch, the
  solidify growth in px); `test_overlay_sprites.py` 50 to 56 and the optional-wave count (Intent moved notes).

## Measured

- Arm (feminine wave2, perpendicular, 2x capture): coverage 5.75 raw to 6.63 solid (+0.88); half-alpha width
  5.34 to 6.54 (+1.2). At 128 px figure height (x 128/306): +0.37 and +0.5 px, under the 1 px bar: ramp unchanged,
  the ratchet pins it (`SOLID_LO` 24, `SOLID_HI` 120: at most +1.0 px at 2x for a soft edge).
- Mouth patch: 44 to 48 levels off the surrounding skin (flat disc, old code) to 10 to 13 (cause: one flat tone
  from `_skin(patch, ox, oy)` over an ellipse 16.5 x 8 px; the face is shaded there and the eye anchor is not always
  on the eyes).

## The 10 overlay failures (step 2): cause and fix

All ten, and three more the frames exposed (bob_1670, spin_1696, flow_1683), pass on the merge base with the old frames;
the four staged lints are cleared by merging claude/next-queue-1102. Causes, measured at 96 dpi:

- The render was not the same twice: the shared stream was the median-mass capture of the set, a different one each run,
  so the figure's right edge and the ring's lowest row moved 8 to 17 px between renders (size 262 to 289 wide). Fixed:
  the stand's stream is the one every stand, idle, walk, wave and held frame shows (`shared_stream`, `STREAM_SHARED`).
- The stand sat 7 to 10 shipped px right of the canvas centre (old frames: 4 left), so a mirrored figure shifted 9 px
  (`_flip_dx`) and hung off the screen edge (size_review window right 1929 over 1920). Fixed: `crop_box` widens its
  narrower side so the stand is centred (+1 px on the right so the shift is never positive).
- Feminine walk frames dipped 11 to 17 px under the stand: the float frame leans the char 4 deg and the tail swing was
  all clockwise. Walk tail is now `-7 + 2.5 sin` deg (never clockwise of the lean), lower skew 6 deg; dip 4 shipped px.
- Stand, blink, look and the idle cycle ended on rows up to 3 apart (feet-line steps 2 px against a 1.7 bound, the
  floater's window 3 against 2): `clip_idle_tails` clips all of them to the highest one at the metrics' own alpha floor.
- `held` had a narrower box than the stand and idle pictures drawn during a rise or a press (1 to 3 px cut at the
  screen edge in the ride test): `held` shares the stand's stream, and `engine._ride_box("held")` takes its sides from
  the whole stand family and idle cycle (the clamp that uses it now holds for every picture drawn there).
- Tests changed only where intent moved, each with an "Intent moved" note: size_review (the handle is left of the solid
  corner, not the drawn box, which includes a faint stream 10 px beyond the head), seams (masculine marker removed, it
  passes; feminine keeps it), bob_1670 (the idle bound reads the body's upper half: the tail's own swing is 1.75 px on
  the whole figure), spin_1696 (literal frame size), flow_1683 (a spell act ticks at 300 ms; a warp's picture takes no
  flow). Nothing was widened for ride, land, tumble, size_1107.
- `LID_EYES` re-measured after the last render: masculine (110,109,155,125), feminine (112,110,157,126).

## Left

- Eye boxes depend on the crop box: a later `render_desk_frames.py` run needs `LID_EYES` re-measured (mouth ink
  centre minus 13 for the eye line).
- The blush ellipses in `faces._mouth` paint a faint green-tinted ring where they overhang the face edge (masculine
  `content`/`smile`); not fixed.
- Feminine idle still jumps at steps 11 to 12, 17 to 18 and 23 to 0 (hair and ring, 4x to 8x the median step): its
  seams test stays strict-xfail.
- Arm rig and tail are the rig's own physics: two renders can still differ by a px or two on the arm; if a ratchet
  moves by one on a re-render, look at the arm first.
- The canvas is wider than the old one (masculine 289x304, feminine 275x298, was 263x302 and 263x299): the centred crop
  and the wave swing's reach. Window size at 100 percent follows it.
- Not verified on a real desktop (Windows overlay): PNG crops and targeted pytest only.
