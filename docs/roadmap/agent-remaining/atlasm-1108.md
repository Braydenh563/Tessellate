# atlasm-1108: the masculine Atlas design pass (INBOX 1607 b, c, d; audit B16)

The owner (INBOX 1607): "the size or shape or smth of the head looks off and a little creepy", "the connection
between the sholders and the arms could be smoother, the facial expressions need some work". Reference: the
feminine look. This file is the spec (step 1, measured, nothing built); the build is steps 2 to 5.

## How it was measured (rerun for the after numbers)

- `scratchpad/ui-sweeps/atlasm1108.js`: the live companion pinned on a plain ground (aura, rings and nebula
  hidden, as `scripts/render_desk_frames.js` does), every mood standing, sit and walk, both looks, at SCALE=1
  and SCALE=2, with the rig's numbers read from the DOM (`getBoundingClientRect`, `getScreenCTM`,
  `isPointInFill` on the head and the hair, the torso and arm outlines sampled with `getPointAtLength`).
- `scratchpad/ui-sweeps/atlasm1108.py D1 D2 OUT.webp`: the metrics below from those cells and the shipped desk
  frames (`frontend/img/desk/<look>/`, device scale 2), and the pose sheet.
- Before sheet: `scratchpad/atlasm1108-before.webp` (170 KB; rows: in-app 1x masc, fem; 2x masc, fem; then
  desk 1x masc, fem; desk 2x masc, fem; columns: the 15 moods standing, sit, walk; desk: stand, look, blink,
  walk0, walk6, sit, sleep, wave, hang). Server: worktree head a2ca281a, port 8923.

## Before (in-app companion, stand, calm; 1x and 2x agree to 0.01 unless shown)

| Metric | Masculine | Feminine (reference) |
| --- | --- | --- |
| Head skin height over the drawn figure's height | 0.215 | 0.205 to 0.211 |
| Head width over the torso's width at body y 40 | 1.08 (head 18.9 px, shoulders 17.0 units) | 1.56 (shoulders 11.7) |
| Hairline at the face's centre (head units, x 31) | 14.2 | 15.8 |
| Head outline below the brows bordering background, not hair | 0.931 | 0.78 to 0.80 |
| One eye's width over the head's width | 0.341 (scale 0.84) | 0.366 (scale 0.9) |
| Inner gap between the eyes over one eye's width | 0.573 | 0.474 |
| Both scleras' area over the head's area | 0.141 | 0.162 |
| Brow paint in the body views (`.atl-brow-line`) | opacity 0.22, stroke 1.3 | 0.22, 1.1, plus lashes |
| Shoulder seam: arm outline inside the torso, mean step (1x) | 9.8 and 9.9 | 6.2 and 5.2 |
| Seam points that read as a line (1x, stand; sit) | 16/28 and 13/27; 15/31 and 12/29 | 2/24 and 0/17; 3/22 and 0/21 |
| Seam points that read as a line (2x, stand, the hanging arm) | 18/29 (rows body y 42.3 to 46.4) | 1/23 |
| Mood change from calm in the face, mean of 14 (1x; 2x) | 27.3; 30.7 | 27.5; 32.3 |
| Weakest moods (1x) | determined 12.9, happy 17.3, surprised 18.3, worried 18.7 | happy 17.4, worried 19.1 |
| Desk `stand` solid box (2x px) | 155 x 214 | 168 x 205 |

Reading: the head is the same path in both looks (`ATLAS_HEAD_PATH`, atlas.js:472, drawn at
`--atl-head-k: 0.76`), so "the head looks off" is not its height (0.215 against 0.21) but (1) a head on
shoulders 1.45 times hers (head over shoulders 1.08 against 1.56), (2) a bare egg: 93% of his outline below
the brows meets the background where her hair frames 20 to 22%, with a hairline 1.6 units higher, and (3)
smaller eyes set wider (0.84 scale, gap 0.57 of an eye against 0.47) with brows at 22% opacity, so nothing on
the big face carries the mood. The seam is the arm's rim shade on its inner edge across the torso at body y
42 to 46.5, below the shoulder cap's mask (`${id}-shoulders`, full only to about y 43.5 at cy 40.8, ry 5).

## Targets (masculine; the feminine look does not move except where named)

| Metric | Target |
| --- | --- |
| Head over shoulders | 1.28 to 1.45 |
| Head height over figure | 0.21 to 0.225 (stays with hers) |
| Hairline at x 31 | 15.6 to 16.4 |
| Bare outline below the brows | 0.82 or less |
| Eye width over head width; scleras over head | 0.36 to 0.37; 0.155 or more |
| Seam points that read as a line, every arm, stand and sit, 1x and 2x | 3 or fewer; mean step 6.5 or less |
| Mood change from calm, mean | at least the feminine's at 1x and 2x; determined, happy and surprised 20 or more at 1x |
| clip-path in companion code | none added (INBOX 1463 decision) |

## Changes, by step (each its own commit, tests first)

2. **Head proportion and shape (1607 b).** (a) `08-consistency.css:7408`: add
   `.nm-atlas[data-atlas-look="masculine"]:not(.atl-head, .atl-tiny) { --atl-head-k: 0.8; }` (head 18.9 to
   19.9 px; the lids' layer follows, the same var, line 6744). (b) `atlas.js:611` masculine `torso`: the
   shoulders 17.0 to 15.4 across at y 40 (scale its x about 31 by 0.9 above y 44, the waist and hips as they
   are), `armL`/`arm` (618, 619) roots 24.6 to 25.4 and 37.4 to 36.6, the rest of each arm shifted with its
   root; `ATLAS_GEO.shoulders` (459) stays (shared). (c) `atlas.js:548` masculine `cap`: lower the hairline to
   y 16 at the centre with two swept points (no fringe locks, his stays a short cut), and carry each side of
   the cap down the temple as a short sideburn to y 28 inside the head outline, so the bare outline below the
   brows falls to 0.82 or less; the cap is drawn on the head's own group, so no new layer. Tests:
   `tests/test_atlas_shape.py:1028` pins the shared 0.76 (keep it, add the masculine line), the torso and arm
   pins in `test_the_masculine_look_is_a_star_being_not_an_animatronic` (:513) move with an Intent moved note
   (INBOX 614's "defined shoulders 17 across" gives way to 1607's proportion; the V stays: 15.4 over a 9.5
   waist is 1.62, hers 1.44).
3. **Shoulder join (1607 c).** (a) `atlas.js:2758`: the shoulder mask per look, from each look's own arm roots
   (`spec.armL[0]`, `spec.arm[0]`) and not one placing for both: masculine ellipses at the new roots, cy 42.6,
   rx 4.8, ry 6.6 (full to y 46.2 at the gradient's 0.55 stop, gone by 49.2), feminine at hers (26.4, 35.6; today she uses
   his 24.6, 37.4 and passes by luck). (b) His arms turn about their own roots: `armPivots` on the masculine
   look as hers has (`atlas.js` feminine `armPivots`), so a raised arm's root stays inside the torso. (c) Add a
   test that reads the mask's centres from each look's roots, and a sweep check: rerun the sweep, every arm
   3 or fewer line points at 1x and 2x, stand and sit.
4. **Eyes and expressions (1607 d).** (a) `08-consistency.css:7388`: masculine `.atl-eye` scale 0.84 to 0.9
   (Intent moved at `tests/test_atlas_shape.py:523`: round 9's smaller eye was for the stare, which INBOX
   1607's lid fix answered; the half-lid is gone, so the size can match hers). (b) His brows carry the face as
   her lashes do: `08-consistency.css:7212` add `.nm-atlas[data-atlas-look="masculine"] .atl-brow-line {
   opacity: 0.6; stroke-width: 1.5; }` in the body views; the straight brow (`atlas.js:2165`) drawn 10%
   shorter at the outer end so it tapers. (c) A heavier upper lid line for him: `.atl-lash` 1.2 to 1.5 on the
   masculine look and one short outer flick (not her three lashes) from `atlasEye` (`atlas.js:1603`, behind
   the `lashes` flag, a `"flick"` value from the look's spec). (d) Then the four weak moods, read again on the
   sheet: happy (raise `--atl-low` for him to 0.3 so the smiling lower lid shows on the larger eye),
   surprised (brows up 3.4 to 4.2 px for him), determined (knit 8 deg with the brows now visible), worried.
   Rerun `CASE=moods node scratchpad/ui-sweeps/atlasrest1402.js` with `LOOK1402=masculine`: no mood may turn
   "grumpy" by it (INBOX 1402).
5. **Desk.** Regenerate the frames (`scripts/render_desk_frames.py`), re-measure `LID_EYES["masculine"]`
   (`sprites.py:73`; the eyes grow by 0.9/0.84 and the head by 0.8/0.76) and check `faces.py`'s `BROW_UP` and
   `MOUTH_DOWN` (27, 28) still land on the brow and the mouth; run `tests/test_overlay_faces.py`,
   `tests/test_overlay_ride_1670.py`, `tests/test_overlay_moves.py`.

Budgets: atlas.js is under the scripts' gzip total with about 1 byte spare (`tests/test_static_compression.py`
`TOTAL_CAP`): steps 2 to 4 change numbers in place and add CSS (boot CSS cap `tests/test_boot_budget.py:79`);
any new JS (the flick) is paid for in the same commit or goes to a lazy file. No function over 15 complexity.

## Log

- done: spec and before sheet (498cbf49, amended into this commit). next: step 2, `frontend/css/08-consistency.css:7408` and
  `frontend/js/atlas.js:548`, 611, 618.
- done: step 2, head (this commit; head over shoulders 1.09 to 1.31, hairline 14.1 to 16.1, bare 0.93 to 0.80
  by tests/test_atlas_masc_1607.py; shoulders 15.0 not 15.4, since 15.4 gave 1.27; arms in by 1, the CSS origins
  his; his three 18deg inward arms 16deg so a hand stays at the middle). next: step 3, `atlas.js` shoulder mask.
- done: step 3, shoulder join (this commit; the mask on each look's roots, cy 42.6 rx 4.8 ry 6.6; his pivots
  were moved in step 2 by the CSS origins, which are his, so no `armPivots`). Sweep: his remaining "line points"
  (14/31 at 2x) are pixel-identical with his arms hidden (EXTRA css in a scratch copy of the sweep): the torso's
  own shading under the arm's outline, not a join. next: step 4, eyes and brows, `08-consistency.css` 7388, 7212.
