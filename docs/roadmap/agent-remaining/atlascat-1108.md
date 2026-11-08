# atlascat-1108: the companion catalogue and parity (INBOX 1696 dd, v, kk)

Design pass (judge rung). The owner, verbatim: (dd) "can the atlas companion have a lot and i mean A LOT more biological animation and frame and movement options and variation??"; (v) "I want the desktop companion to be just as good as the in-app one and vice versa"; (kk) "the desktop companion doesnt have as many subtle interactions like shaking it makes it turn upside down or flail and get dizzy".

## Step 1: the inventory, as a parity table

Read from the act tables on both sides (2026-11-08, head 0fad02e6). In-app: `NAME_MARK_BUDDY_ACTS` and its additions (avatars.js:3067, 3154, 3167, 3185; companion-menu.js:703; 58 acts), `ATLAS_TAIL_ACTS` (atlas-life.js:66, 8), `ATLAS_LOWER_STATES` (atlas-life.js:818, 15), `ATLAS_MOODS` (atlas.js:131, 15), `ATLAS_MICRO_BASE` (atlas-micro.js:40, 15), `NMB_REACTIONS` (avatars.js, 12), the poke answers (avatars.js:9134), the pointer handlers (pet 6587, rub 6632, flip and dizzy 6665) and the throw (companion-throw.js). Desk: `behaviour.ACTIVITIES` with the prop, plain, spell and reaction acts registered (67), `extras.REACTIONS` (19), `faces.EXPRESSIONS` (12), `presence.SPELLS` (7), `behaviour.FLOW_POSE` (9) and the engine's moves (engine.py).

Counts over the 196 entries built on at least one side: both 91, in-app only 69, desk only 36. The catalogue adds 111 entries built on neither side (step 2). The rows below are generated from `frontend/companion-catalogue.json`; the file is the source, this table a reading of it on 2026-11-08 (line numbers drift; the file's `at` text does not).

### interaction (26)

| id | in-app | desk |
| --- | --- | --- |
| int.poke | yes `avatars.js:9134` (pleased, playful, curious) | yes `extras.py:67` (poke_giggle, poke_miffed, poke_curious) |
| int.pet | yes `avatars.js:6587` | yes `extras.py:67` (hover) |
| int.rub | yes `avatars.js:6632` | yes `extras.py:67` (rub, rub_purr) |
| int.pat | no | yes `extras.py:67` (pat, pat_happy) |
| int.swipe_twirl | no | yes `extras.py:67` (flip, flip_twirl) |
| int.pointer_whoosh | yes `avatars.js:8719` (whoosh, double) | yes `extras.py:67` (flinch, flinch) |
| int.shake_dizzy | yes `avatars.js:6665` | no |
| int.held_upside_down | yes `avatars.js:6665` | no |
| int.long_carry | yes `avatars.js:8719` (carried) | no |
| int.flail | yes `companion-throw.js:431` | yes `engine.py:3373` |
| int.drop | yes `avatars.js:6539` | yes `engine.py:3817` |
| int.throw_tumble | yes `companion-throw.js:473` | yes `engine.py:3498` |
| int.throw_catch_ledge | yes `companion-throw.js:38` | yes `engine.py:3762` |
| int.fling_wall | yes `companion-throw.js:177` | yes `engine.py:3317` |
| int.wrap_edge | yes `companion-throw.js:176` | yes `engine.py:3334` |
| int.ceiling_bonk | no | yes `engine.py:258` |
| int.shaken_off | yes `companion-throw.js:760` | yes `engine.py:1986` |
| int.tickle | no | no |
| int.hold_still | no | no |
| int.carry_over | no | no |
| int.catch_midair | no | no |
| int.boop_nose | no | no |
| int.tail_pull | no | no |
| int.drag_skid | no | no |
| int.toss_up | no | no |
| int.pointer_chase | no | no |

### idle act (88)

| id | in-app | desk |
| --- | --- | --- |
| act.breathe | yes `atlas-life.js:768` (settle) | yes `behaviour.py:176` (breathe) |
| act.shift_weight | yes `avatars.js:3067` (shift, shift) | yes `behaviour.py:177` (shift_weight) |
| act.look_around | yes `avatars.js:3067` (look, turn, around) | yes `behaviour.py:178` (look_around, scan_horizon) |
| act.slow_blink | yes `avatars.js:3067` (blink) | yes `behaviour.py:179` (slow_blink) |
| act.glance_pointer | yes `avatars.js:3067` (glance, glance) | yes `behaviour.py:182` (glance_pointer, peer_at_cursor) |
| act.stretch | yes `avatars.js:3067` (stretch) | yes `behaviour.py:180` (stretch) |
| act.yawn | yes `avatars.js:3067` (yawn, yawn) | yes `behaviour.py:181` (yawn) |
| act.nap | yes `avatars.js:3067` (nap) | yes `behaviour.py:192` (doze, curl_up) |
| act.lie_down | yes `avatars.js:3067` (lie) | yes `behaviour.py:200` (lie_down) |
| act.hop | yes `avatars.js:3067` (hop) | yes `behaviour.py:189` (bounce) |
| act.wave | yes `avatars.js:3067` (wave) | yes `behaviour.py:197` (wave_idle) |
| act.scratch | yes `avatars.js:3067` (scratch) | yes `behaviour.py:207` (scratch) |
| act.dangle | yes `avatars.js:3067` (dangle) | no |
| act.kick_legs | yes `avatars.js:3067` (kick) | no |
| act.peek_top | yes `avatars.js:3067` (peek) | yes `engine.py:2886` |
| act.peek_side | yes `avatars.js:3067` (peekside) | yes `engine.py:2399` |
| act.peek_down_upside | yes `avatars.js:3067` (peekdown, peekback) | yes `engine.py:3162` |
| act.swing | yes `avatars.js:3067` (swing) | yes `engine.py:3133` |
| act.sloth | yes `avatars.js:3067` (sloth) | no |
| act.hang_one_hand | yes `avatars.js:3067` (onehand) | no |
| act.hang_by_feet | yes `avatars.js:3067` (feet) | no |
| act.read | yes `avatars.js:3067` (read) | yes `props.py:54` (read_book, read) |
| act.beanbag | yes `avatars.js:3067` (beanbag) | yes `props.py:59` (lounge_beanbag) |
| act.chair | yes `avatars.js:3067` (chair) | no |
| act.facepalm | yes `avatars.js:3067` (facepalm) | no |
| act.shrug | yes `avatars.js:3067` (shrug) | yes `behaviour.py:187` (shrug) |
| act.lean_tilt | yes `avatars.js:3067` (tilt) | no |
| act.head_tilt | yes `atlas-micro.js:40` (tilt) | no |
| act.ear_twitch | yes `atlas-micro.js:40` (ear) | no |
| act.cast_sparkle | yes `atlas-micro.js:127` (cast) | no |
| act.wiggle | yes `avatars.js:3067` (wiggle) | yes `behaviour.py:188` (wiggle) |
| act.nod | no | yes `behaviour.py:186` (nod) |
| act.shake_off | yes `avatars.js:3067` (shake) | yes `behaviour.py:196` (shake_off) |
| act.groom | yes `avatars.js:3067` (groom) | yes `behaviour.py:206` (groom) |
| act.sniff | yes `avatars.js:3067` (sniff) | no |
| act.sigh | yes `companion-menu.js:703` (sigh) | no |
| act.hands_on_hips | yes `avatars.js:3154` (hips, hip) | no |
| act.clasp_hands | yes `avatars.js:3154` (clasp) | no |
| act.sway | yes `avatars.js:3154` (sway) | yes `behaviour.py:184` (sway) |
| act.juggle | yes `avatars.js:3167` (juggle) | no |
| act.read_map | yes `avatars.js:3167` (map) | yes `props.py:74` (read_map) |
| act.meditate | yes `avatars.js:3167` (meditate) | no |
| act.crouch | yes `avatars.js:3067` (crouch) | yes `behaviour.py:198` (crouch_watch) |
| act.lounge | yes `avatars.js:3067` (lounge) | no |
| act.rest_head | yes `avatars.js:3067` (rest) | no |
| act.ponder | yes `companion-menu.js:703` (ponder) | yes `behaviour.py:185` (ponder) |
| act.toss_stars | yes `companion-menu.js:703` (toss) | no |
| act.hum | yes `atlas-micro.js:40` (hum) | yes `props.py:118` (hum) |
| act.little_dance | no | yes `behaviour.py:183` (little_dance) |
| act.pose_proud | no | yes `behaviour.py:194` (pose_proud) |
| act.look_down | no | yes `behaviour.py:195` (peek_down) |
| act.push_ups | no | yes `props.py:69` (push_ups) |
| act.lift_weights | no | yes `props.py:84` (lift_weights) |
| act.lantern | yes `avatars.js:3067` (lantern) | yes `props.py:79` (hold_lantern) |
| act.carry_note | yes `avatars.js:3067` (carry) | yes `engine.py:2301` |
| act.sip_tea | no | yes `presence.py:35` (sip_tea, tea) |
| act.write_journal | no | yes `presence.py:37` (write_journal, doodle) |
| act.fish | no | yes `presence.py:38` (go_fishing, fish) |
| act.watch_stars | no | yes `presence.py:39` (watch_stars, stargaze, stars) |
| act.blanket_nap | no | yes `presence.py:40` (blanket_nap, doze) |
| act.water_plant | no | yes `presence.py:41` (water_plant, plant) |
| act.tiptoe | no | yes `props.py:119` (tiptoe) |
| act.daydream | no | yes `props.py:121` (daydream) |
| act.puzzle | no | yes `props.py:122` (puzzle) |
| act.snack | no | yes `behaviour.py:208` (snack) |
| act.pace | no | yes `behaviour.py:210` (pace) |
| act.invent_game | no | yes `behaviour.py:211` (invent_game) |
| act.tinker | no | yes `behaviour.py:212` (tinker) |
| act.dust_off | no | yes `behaviour.py:213` (dust_off) |
| act.sit_a_while | yes `avatars.js:3043` | yes `behaviour.py:191` (sit_down) |
| act.cloud_pillow | no | no |
| act.star_catch | no | no |
| act.tail_chase | no | no |
| act.knit_starlight | no | no |
| act.count_stars | no | no |
| act.paper_plane | no | no |
| act.blow_bubbles | no | no |
| act.conduct | no | no |
| act.tail_stretch | no | no |
| act.lean_on_edge | no | no |
| act.foot_tap | no | no |
| act.balance_walk | no | no |
| act.sketch_view | no | no |
| act.sneeze | no | no |
| act.hiccup | no | no |
| act.self_hug | no | no |
| act.kneel_look | no | no |
| act.stargaze_awake | no | no |

### reaction (26)

| id | in-app | desk |
| --- | --- | --- |
| react.startle | yes `avatars.js:3067` (startle) | yes `engine.py:2963` |
| react.wake | yes `avatars.js:3067` (wake) | yes `engine.py:1762` |
| react.task_done | yes `avatars.js:8953` (nod, cheer, streak) | yes `extras.py:67` (download_done, cheer) |
| react.toast | yes `avatars.js:8719` (toast) | yes `extras.py:67` (toast, perk_up) |
| react.app_switched | yes `avatars.js:8371` | yes `extras.py:67` (app_switched, glance_screen) |
| react.window_opened | no | yes `extras.py:67` (window_opened, glance_window) |
| react.window_closed | no | yes `extras.py:67` (window_closed, relief) |
| react.window_dragged | no | yes `extras.py:67` (window_dragged, watch_drag) |
| react.window_maximised | no | yes `extras.py:67` (window_maximised) |
| react.window_restored | no | yes `extras.py:67` (window_restored) |
| react.idle_return | no | yes `extras.py:67` (idle_return, welcome_back) |
| react.hour_chime | no | yes `extras.py:67` (hour_chime, chime_nod) |
| react.battery_low | no | yes `extras.py:67` (battery_low, shiver) |
| react.long_note | yes `avatars.js:8719` (read) | no |
| react.graph_laid | yes `avatars.js:8719` (graph) | no |
| react.private_note | yes `avatars.js:8719` (private, hide) | no |
| react.remark | yes `avatars.js:8719` (remark) | no |
| react.search_nothing | yes `avatars.js:8719` (nothing) | no |
| react.search_found | yes `avatars.js:8719` (found) | no |
| react.note_binned | yes `avatars.js:8719` (binned) | no |
| react.reminder_bell | yes `avatars.js:3067` (bell) | no |
| react.media_playing | no | no |
| react.fullscreen_app | no | no |
| react.typing_burst | no | no |
| react.night_falls | no | no |
| react.morning_hello | no | no |

### movement (17)

| id | in-app | desk |
| --- | --- | --- |
| move.walk | yes `avatars.js:1189` | yes `engine.py:3440` |
| move.glide | yes `avatars.js:3067` (glide) | yes `engine.py:2486` |
| move.drift | yes `avatars.js:3067` (drift) | yes `engine.py:2989` (float_loop) |
| move.climb | yes `avatars.js:3067` (climb) | yes `engine.py:2186` |
| move.emerge | yes `avatars.js:3067` (emerge) | yes `engine.py:3194` |
| move.land | yes `avatars.js:3067` (land) | yes `engine.py:2967` |
| move.portal | yes `avatars.js:6697` | yes `engine.py:2557` |
| move.come | yes `companion-menu.js:904` | yes `engine.py:1772` |
| move.wander | yes `companion-menu.js:913` | yes `engine.py:1846` |
| move.afield | yes `companion-menu.js:912` | no |
| move.cloud_ride | no | yes `engine.py:2641` |
| move.ride_surface | yes `avatars.js:3033` | yes `engine.py:1899` |
| move.tiptoe_sneak | no | no |
| move.skip | no | no |
| move.swim_air | no | no |
| move.somersault | no | no |
| move.slide_pole | no | no |

### body position (13)

| id | in-app | desk |
| --- | --- | --- |
| pos.upright | yes `avatars.js:3043` | yes `engine.py:2939` |
| pos.sit | yes `avatars.js:3043` | yes `engine.py:2943` |
| pos.lie | yes `avatars.js:3067` (lie) | yes `engine.py:648` |
| pos.curl | yes `avatars.js:3067` (nap) | yes `engine.py:2951` |
| pos.crouch | yes `avatars.js:3067` (crouch) | yes `engine.py:1450` |
| pos.lounge | yes `avatars.js:3067` (lounge) | no |
| pos.hang | yes `avatars.js:304` | yes `engine.py:3066` |
| pos.lean | yes `avatars.js:53` | no |
| pos.cross_legged | yes `avatars.js:3167` (meditate) | no |
| pos.edge_dangle | yes `avatars.js:3067` (dangle) | no |
| pos.back_float | yes `avatars.js:3067` (drift) | no |
| pos.belly_sprawl | no | no |
| pos.kneel | no | no |

### transition (66)

| id | in-app | desk |
| --- | --- | --- |
| trans.upright>sit | yes `avatars.js:8338` | no |
| trans.upright>lie | yes `avatars.js:8338` | no |
| trans.upright>curl | yes `avatars.js:8338` | no |
| trans.upright>crouch | yes `avatars.js:8338` | yes `engine.py:2967` |
| trans.upright>hang | no | yes `engine.py:2340` |
| trans.sit>upright | yes `avatars.js:8338` | no |
| trans.sit>curl | yes `avatars.js:8338` | no |
| trans.sit>lounge | yes `avatars.js:8338` | no |
| trans.lie>upright | yes `avatars.js:8338` | yes `engine.py:3552` |
| trans.curl>upright | yes `avatars.js:8338` | yes `engine.py:1762` |
| trans.curl>sit | yes `avatars.js:8338` | no |
| trans.crouch>upright | yes `avatars.js:8338` | yes `engine.py:2967` |
| trans.lounge>sit | yes `avatars.js:8338` | no |
| trans.hang>upright | yes `avatars.js:8338` | yes `engine.py:2131` |
| trans.sit>cross_legged | yes `avatars.js:8338` | no |
| trans.cross_legged>sit | yes `avatars.js:8338` | no |
| trans.sit>edge_dangle | yes `avatars.js:8338` | no |
| trans.edge_dangle>sit | yes `avatars.js:8338` | no |
| trans.upright>back_float | yes `avatars.js:8338` | no |
| trans.back_float>upright | yes `avatars.js:8338` | no |

Every other ordered pair of the 8 core positions, and the 10 via transitions, is built on neither side.

### tail pose (17)

| id | in-app | desk |
| --- | --- | --- |
| tail.sway | yes `atlas-life.js:66` (sway) | yes `sprites.py:36` |
| tail.curl | yes `atlas-life.js:66` (curl) | no |
| tail.wrap | yes `atlas-life.js:66` (wrap) | no |
| tail.flick | yes `atlas-life.js:66` (flick) | yes `behaviour.py:201` (tail_flick) |
| tail.wag | yes `atlas-life.js:66` (wag) | no |
| tail.trail | yes `atlas-life.js:66` (trail) | yes `sprites.py:54` |
| tail.droop | yes `atlas-life.js:66` (droop) | no |
| tail.stiff | yes `atlas-life.js:66` (stiff) | no |
| tail.hook | no | no |
| tail.coil_hold | no | no |
| tail.thump | no | no |
| tail.shiver | no | no |
| tail.loop8 | no | no |
| tail.tuck | no | no |
| tail.tip_twitch | no | no |
| tail.balance | no | no |
| tail.pillow | no | no |

### lower sway (24)

| id | in-app | desk |
| --- | --- | --- |
| lower.idle | yes `atlas-life.js:818` (idle) | yes `behaviour.py:537` (idle) |
| lower.walk | yes `atlas-life.js:818` (walk) | yes `behaviour.py:537` (walk) |
| lower.sit | yes `atlas-life.js:818` (sit) | yes `behaviour.py:537` (sit) |
| lower.lie | yes `atlas-life.js:818` (lie) | no |
| lower.curl | yes `atlas-life.js:818` (curl) | yes `behaviour.py:537` (sleep) |
| lower.gesture | yes `atlas-life.js:818` (gesture) | yes `behaviour.py:537` (wave) |
| lower.think | yes `atlas-life.js:818` (think) | no |
| lower.happy | yes `atlas-life.js:818` (happy) | yes `behaviour.py:537` (hop) |
| lower.sad | yes `atlas-life.js:818` (sad) | no |
| lower.startle | yes `atlas-life.js:818` (startle) | no |
| lower.crouch | yes `atlas-life.js:818` (crouch) | yes `behaviour.py:537` (land) |
| lower.lounge | yes `atlas-life.js:818` (lounge) | no |
| lower.glide | yes `atlas-life.js:818` (glide) | no |
| lower.drift | yes `atlas-life.js:818` (drift) | no |
| lower.hang | yes `atlas-life.js:818` (hang) | yes `behaviour.py:537` (hang) |
| lower.fall | no | yes `behaviour.py:537` (fall) |
| lower.billow | no | no |
| lower.coil | no | no |
| lower.ripple_calm | no | no |
| lower.flutter | no | no |
| lower.pool | no | no |
| lower.hem_kick | no | no |
| lower.spiral | no | no |
| lower.heavy | no | no |

### face (30)

| id | in-app | desk |
| --- | --- | --- |
| face.calm | yes `atlas.js:131` (calm) | yes `faces.py:49` (content) |
| face.happy | yes `atlas.js:131` (happy, pleased) | yes `faces.py:49` (smile) |
| face.delighted | yes `atlas.js:131` (delighted) | yes `faces.py:49` (joy) |
| face.laughing | yes `atlas.js:131` (laughing) | no |
| face.thinking | yes `atlas.js:131` (thinking) | yes `faces.py:49` (focus) |
| face.curious | yes `atlas.js:131` (curious, curious) | yes `faces.py:49` (curious) |
| face.surprised | yes `atlas.js:131` (surprised, surprised) | yes `faces.py:49` (surprised) |
| face.confused | yes `atlas.js:131` (confused) | no |
| face.sleepy | yes `atlas.js:131` (sleepy, sleepy) | yes `faces.py:49` (sleepy) |
| face.sad | yes `atlas.js:131` (sad) | no |
| face.proud | yes `atlas.js:131` (proud) | yes `faces.py:49` (proud) |
| face.shy | yes `atlas.js:131` (shy) | no |
| face.determined | yes `atlas.js:131` (determined, focus) | yes `faces.py:49` (strain) |
| face.love | yes `atlas.js:131` (love) | no |
| face.worried | yes `atlas.js:131` (worried) | yes `faces.py:49` (worried) |
| face.miffed | no | yes `faces.py:49` (miffed) |
| face.smirk | no | yes `faces.py:49` (smirk) |
| face.blink | yes `atlas-motion.js:11` (blink) | yes `engine.py:74` |
| face.slow_blink | yes `atlas-motion.js:11` | yes `sprites.py:77` |
| face.glance | yes `avatars.js:8074` | yes `engine.py:73` |
| face.dizzy | yes `avatars.js:6684` | no |
| face.pout | no | no |
| face.eyes_down | no | no |
| face.cross_eyed | no | no |
| face.wince | no | no |
| face.giggle | no | no |
| face.groggy | no | no |
| face.awe | no | no |
| face.bored | no | no |
| face.relieved | no | no |

## Step 2: the catalogue, `frontend/companion-catalogue.json`

Format: JSON, because both sides parse it with no new dependency. The app fetches it as it fetches `/credits.json` (and as the board library loads `frontend/board-library/*.json`), and the desk reads it through `FRONTEND_DIR`, as `sprites.frames_dir` reads `frontend/img/desk`.
One file both sides read means no table is copied, so parity is a property of one file and the test can check it.
A Python or JS module would need the other side to scrape it.

The catalogue has 307 entries: idle acts 88, transitions 66, faces 30, interactions 26, reactions 26, lower-body sways 24, tail poses 17, movements 17 and body positions 13. Each entry gives:

- its id and kind;
- `seconds`, the duration range;
- weights by mood, by energy (low, mid, high) and by time of day;
- for idle acts, its pose and the tail, lower and face parts it uses, plus `beats`, the pose shifts that keep a long act from holding one pose over 90 s;
- `draw`, what it needs drawn;
- its status per side, with the table names and the code location (`path#text`) on each built side.

The 111 entries built on neither side are new, and each is marked `missing` on both sides. Every entry built on one side only is marked `missing` on the other.

done: step 1 ddce2944; next: commit the catalogue (step 2), then the ratchet test (step 3), then the build order (step 4).

## Step 3: the ratchets, `tests/test_companion_catalogue_1108.py`

- **(a) Parity.** `APP_ONLY` (69) and `DESK_ONLY` (36) are the allow lists, and their caps may only fall, as may `NEITHER_CAP` (111). Every act, tail, lower, mood, micro, reaction and poke row in the app's tables, and every Activity, reaction, face, spell and flow row on the desk, must be catalogued under its exact name, and every catalogued name must still exist in the code. A built side's `at` text must be found in its file.
- **(b) Variety.** `seeded_hour` draws one hour at hours 9, 14, 20 and 23 with seeds 1 to 3, from the catalogue's weights on a fixed clock (no wall time). Measured 2026-11-08:
  - all entries: 48 to 80 distinct acts, longest pose 75.8 s;
  - built in-app: 42 to 50 acts, longest 69.7 s;
  - built on the desk: 32 to 46 acts, longest 69.6 s.

  The test asks for at least 12 acts and no pose over 90 s. `test_built_variety_only_rises` floors the built sides at 38 in-app and 29 desk.

done: step 2 1668e9dc; next: the test (step 3), then the build order (step 4).

## Step 4: the build order (Sonnet builders, batches of 5 rows)

Every row has the same last check, which is the ratchet itself:

- Built on a side: set that side's `s` to `built` with `names` and an `at` the test can find.
- Delete the id from `APP_ONLY` or `DESK_ONLY` in `tests/test_companion_catalogue_1108.py`, and lower the matching cap by the same count. An entry built on neither side that lands on both lowers `NEITHER_CAP`.
- A new entry built on one side only goes onto the other side's list. Its cap rises, which is the one allowed rise, and it is recorded in the row's commit.

Run, per row, `.venv/bin/python -m pytest -q tests/test_companion_catalogue_1108.py` plus the named test, then `bash scripts/gate.sh --staged`. Desk paths are under `src/tessellate/core/overlay/` and app paths under `frontend/js/`. A desk act that needs frames adds them through `scripts/render_desk_frames.js` (the sprite sheet in `frontend/img/desk`) in the same commit.

### Batch A: one table both sides read (do first; the other batches assume it)

| # | Entries | Files | Check |
| --- | --- | --- | --- |
| A1 | the loader (no entry) | new `catalogue.py` (reads `FRONTEND_DIR / "companion-catalogue.json"` once, cached) | new `tests/test_overlay_catalogue_1108.py`: returns 307 entries; a missing file gives an empty table, not a crash |
| A2 | the reader (no entry) | `avatars.js` (fetch `/companion-catalogue.json` once at first idle with `api(path, { silent: true })`, as `settings-find.js:871` loads `/credits.json`) | `node --check`; a static test that the companion keeps its built-in tables when the fetch fails |
| A3 | `durations`: `seconds` and `w` of every act built on both sides | `behaviour.py` (Activity length and weight from the table where an entry exists); `avatars.js` (`NAME_MARK_BUDDY_ACTS` `ms` and `w`) | `test_overlay_idle.py`, `test_atlas_acts_1589.py`; one table, so the two sides' durations agree (new assert in A1's test) |
| A4 | `beats` of every long act (shift within the pose budget) | `behaviour.py` Mind (a beat timer per act); `avatars.js` act runner | `test_long_acts_change_pose_within_the_budget` plus a desk sim over 600 s: no pose held over 90 s |
| A5 | mood, energy and day weights | `behaviour.py` Mind pick; `avatars.js` pick | a seeded desk sim and app sim each reproduce `seeded_hour` act counts within 2 |

### Batch B: shaking, upside down and dizzy on the desk (kk)

| # | Entries | Files | Check |
| --- | --- | --- | --- |
| B1 | `int.shake_dizzy`, `face.dizzy` | `extras.py` classify (a carried shake: 3 direction flips in 0.6 s); `engine.py` a `_dizzy` state after the drop (spiral eyes, 2.5 to 4 s sway); `faces.py` `dizzy` | new `tests/test_overlay_shake_1108.py`: a fake drag with 3 flips lands dizzy, 2 flips does not |
| B2 | `int.held_upside_down` | `engine.py` the carried pose flips when the grab point is the feet or after a shake; `sprites.py` a rotated frame set | the same test file: the carried frame is the flipped set while upside down |
| B3 | `int.long_carry`, `lower.drift` | `engine.py` the carry timer (after 4 s: kick legs, then cross arms, then a sigh); `extras.py` | a carry held 10 s in the fake shows the three stages in order |
| B4 | `face.confused`, `face.sad`, `face.shy`, `face.love`, `face.laughing` | `faces.py` EXPRESSIONS; `scripts/render_desk_frames.js` face frames | `test_overlay_faces.py` covers the five |
| B5 | `int.tickle`, `int.boop_nose` (new; both sides) | `extras.py` classify (fast small rub on the body, a tap on the face); `avatars.js` pet and poke handlers | `test_overlay_peek_flip_1108.py` style fake on desk; static test in-app; both sides built in one commit |

### Batch C: the tail and lower body as layers (dd)

| # | Entries | Files | Check |
| --- | --- | --- | --- |
| C1 | `tail.curl`, `tail.wrap`, `tail.wag`, `tail.droop`, `tail.stiff` on the desk | `sprites.py` a tail layer drawn per tick over the body frame; `runner.py` compositing | new `tests/test_overlay_tail_layer_1108.py`: each pose changes the tail's drawn points, the body frame is unchanged |
| C2 | `tail.hook`, `tail.coil_hold`, `tail.thump`, `tail.shiver`, `tail.tuck` (new) | `atlas-life.js` `ATLAS_TAIL_ACTS`; the desk tail layer from C1 | `test_atlas_acts_1589.py` plus C1's test |
| C3 | `tail.loop8`, `tail.tip_twitch`, `tail.balance`, `tail.pillow` (new) | the same as C2 | the same |
| C4 | `lower.lie`, `lower.think`, `lower.sad`, `lower.startle`, `lower.lounge`, `lower.glide` on the desk | `sprites.py` a lower-body layer; `behaviour.py` FLOW_POSE gains the states | a desk test per state, as in C1 |
| C5 | `lower.billow`, `lower.coil`, `lower.ripple_calm`, `lower.flutter`, `lower.pool`, `lower.hem_kick`, `lower.spiral`, `lower.heavy` (new) | `atlas-life.js` `ATLAS_LOWER_STATES`; the desk lower layer from C4 | `test_atlas_rest_motion.py` plus C4's test |

### Batch D: the app learns the desk's acts (v)

| # | Entries | Files | Check |
| --- | --- | --- | --- |
| D1 | `act.push_ups`, `act.lift_weights`, `act.sip_tea`, `act.snack`, `act.fish` | `avatars.js` `NAME_MARK_BUDDY_ACTS` plus pose bodies; the props drawn in the rig (`atlas.js`) | `test_atlas_acts_1589.py`; the app's act table rows found by `test_every_table_row_is_catalogued[app]` |
| D2 | `act.write_journal`, `act.watch_stars`, `act.blanket_nap`, `act.water_plant`, `act.puzzle` | as D1 | as D1 |
| D3 | `act.nod`, `act.little_dance`, `act.pose_proud`, `act.look_down`, `act.tiptoe` | as D1 | as D1 |
| D4 | `act.daydream`, `act.pace`, `act.invent_game`, `act.tinker`, `act.dust_off`, `face.miffed`, `face.smirk` | as D1; `atlas.js` `ATLAS_MOODS` for the two faces | as D1 plus `test_atlas_face_inherit_1591.py` |
| D5 | `int.pat`, `int.swipe_twirl`, `int.ceiling_bonk`, `move.cloud_ride`, `lower.fall`, `trans.upright>hang` | `avatars.js` pointer handlers (a slow pat on the head; a fast swipe spins once); `companion-throw.js` (a throw into the top bar bonks); a cloud ride as a walk variant | `test_companion_throw_fates.py` plus a static test per handler |

### Batch E: the desk learns the app's acts (v)

| # | Entries | Files | Check |
| --- | --- | --- | --- |
| E1 | `act.dangle`, `act.kick_legs`, `act.hang_one_hand`, `act.hang_by_feet`, `act.sloth` | `engine.py` hang tricks on a window top edge (the hang state exists: `_leap_to_hang`); `props.py` PLAIN_ACTS | `test_overlay_hang.py` gains the five |
| E2 | `act.juggle`, `act.meditate`, `act.toss_stars`, `act.cast_sparkle`, `act.chair` | `props.py` PROP_ACTS and SPELL_ACTS; `render_desk_frames.js` | `test_overlay_life_1670.py` |
| E3 | `act.facepalm`, `act.lean_tilt`, `act.head_tilt`, `act.ear_twitch`, `act.sniff` | `props.py` PLAIN_ACTS | as E2 |
| E4 | `act.sigh`, `act.hands_on_hips`, `act.clasp_hands`, `act.lounge`, `act.rest_head`, `pos.lounge`, `pos.lean` | `props.py` PLAIN_ACTS; `behaviour.py` FLOW_POSE | as E2 |
| E5 | `pos.cross_legged`, `pos.edge_dangle`, `pos.back_float`, `move.afield`, and the 14 app-only transitions | `engine.py` in-between frames per pair (the pattern of `_pull_up`); `sprites.py` | `test_transitions_cover_every_pair`; `test_overlay_moves.py` |

### Batch F: the app's reactions on the desk and the desk's on the app (v)

| # | Entries | Files | Check |
| --- | --- | --- | --- |
| F1 | `react.long_note`, `react.private_note`, `react.remark`, `react.note_binned` | `extras.py` REACTIONS fed by the app events the desk already polls (`runner.py`) | `test_desk_overlay_wiring.py` |
| F2 | `react.graph_laid`, `react.search_found`, `react.search_nothing`, `react.reminder_bell` | as F1 | as F1 |
| F3 | `react.window_opened`, `react.window_closed`, `react.window_dragged`, `react.window_maximised`, `react.window_restored` in-app | `avatars.js` `NMB_REACTIONS`, as analogues: a panel opened, closed, dragged, a surface fullscreened and restored | the app's reaction rows found by `test_every_table_row_is_catalogued[app]` |
| F4 | `react.idle_return`, `react.hour_chime`, `react.battery_low` in-app | `avatars.js` (`visibilitychange`, the clock, `navigator.getBattery` where present) | static test; battery absent is silent |
| F5 | `react.media_playing`, `react.fullscreen_app`, `react.typing_burst`, `react.night_falls`, `react.morning_hello` (new; both sides) | desk `screenwatch.py` and `extras.py`; app `avatars.js` | both allow lists unchanged (built on both in one commit) |

### Batch G: new variety on both sides (dd)

| # | Entries | Files | Check |
| --- | --- | --- | --- |
| G1 | `act.cloud_pillow`, `act.star_catch`, `act.tail_chase`, `act.knit_starlight`, `act.count_stars` | `avatars.js` acts; `props.py` and `render_desk_frames.js` | `test_built_variety_only_rises` floors raised to the new measure |
| G2 | `act.paper_plane`, `act.blow_bubbles`, `act.conduct`, `act.tail_stretch`, `act.lean_on_edge` | as G1 | as G1 |
| G3 | `act.foot_tap`, `act.balance_walk`, `act.sketch_view`, `act.sneeze`, `act.hiccup`, `act.self_hug`, `act.kneel_look`, `act.stargaze_awake` | as G1 | as G1 |
| G4 | `move.tiptoe_sneak`, `move.skip`, `move.swim_air`, `move.somersault`, `move.slide_pole`; `pos.belly_sprawl`, `pos.kneel` | app walk (`atlas-motion.js`); desk `travel.py` and `engine.py` | `test_overlay_moves.py`; the app's motion test |
| G5 | `int.hold_still`, `int.carry_over`, `int.catch_midair`, `int.tail_pull`, `int.drag_skid`, `int.toss_up`, `int.pointer_chase`; `face.pout`, `face.eyes_down`, `face.cross_eyed`, `face.wince`, `face.giggle`, `face.groggy`, `face.awe`, `face.bored`, `face.relieved` | `extras.py` and `faces.py`; `avatars.js` handlers and `atlas.js` moods | `test_overlay_faces.py`; `test_companion_throw_fates.py` |

The 46 transitions built on neither side are drawn last, in batches of 5 rows, after E5 sets the pattern. The gaps stay listed by `test_transitions_cover_every_pair` until then.

done: step 3 62043f4e; step 4 is this build order and the PLAN.md row. Next: Batch A by a Sonnet builder.
