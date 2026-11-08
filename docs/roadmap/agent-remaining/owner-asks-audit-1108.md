# Owner asks audit, 2026-11-08 (head b04c2b5d, claude/next-queue-1102)

Counts (239 items, eight slices; an ask that two slices both list is counted in each): done 106, partial 83, missing 23, in progress 18, unverifiable 9.

Every desk item rests on fake win32 and X11 tests. Nothing here was driven on the owner's Windows machine. All in-app items are checked against source and tests only; no browser was driven for this audit.

## Missed or skipped

### Missing (23)

| Ref | Ask | Evidence | Next step |
| --- | --- | --- | --- |
| 1607 b | Masculine Atlas head size and shape against the feminine reference | No head-proportion commit or test in the last 300 commits; the INBOX entry says the head pass remains | Design pass in atlas.js with a before and after pose sheet |
| 1607 d | Masculine facial expressions redrawn | No commit or test | Redraw the set with a side-by-side sheet |
| 1607 e | One-line summary at the top of every Help topic | Same as 1612 b | See 1612 b |
| B16 | Masculine Atlas design pass (head, eyes, shoulder join, expressions) | Ledger row M; same gap as 1607 b to d | Spec the pass; measure head and shoulder ratio against the feminine rig |
| 1634 c | nameMarkBuddyBlend reads transformOrigin before and after its writes | Spot-checked: avatars.js:9163 reads before `change()`, then avatars.js:9195 and :9209 call getComputedStyle again after it, so the second layout is still there | Measure the after-read cost at 4x CPU; read once per element after `change()`, or fold the body pass into the held pass |
| 1634 d | No throw read in the first second after visibilitychange (5.6 s cold-window spotNow) | No visibility guard in companion-throw.js; only the tempo re-arms (avatars.js:5689, 6894) | Guard the read behind a 1 s post-visible window or a cached rect; measure a restore after a minute hidden |
| 1667 c | Boards list lazy until the Boards surface or a board widget is visible; 500-board fixture | Spot-checked: notes-list.js:3554 calls loadMapBoardIndex at load, which walks /whiteboard/boards (note-cards.js:168); not gated on visibility | Gate the walk behind the first caller that needs it; add the 500-board query test |
| 1667 f | Library d3 mousemove forced layout (757 ms) | No probe step opens a board; no commit | Add a board step to the perf probe, then fix the per-move read |
| 1667 i | Boot setTimeout forced layout, 560 ms canvas pointerout, 101 ms most-accessed render, 1207 ms unattributed boot frame | Open in the entry; no later commit | Cold-start long-task trace |
| 1667 m | Frames with no script (337, 214, 240 ms) and codemirror requestMeasure | No commit | Per-selector style profile |
| 1612 b | Manual: one-line summary at the top of every topic | No summary field or lint in help_topics_core.py, help_chat.py or test_manual_parity.py (only a "tl;dr" search phrase at help_topics_core.py:1141) | Add a lead line per topic, render it first, lint it in test_manual_parity.py |
| 1612 c | Manual pictures only where needed, as WebP made by the sweeps | No image support in topic rendering | Say it is deliberately empty, or add one sweep-made image |
| 1661 m | Both diagram side panels fold to a rail with a labelled toggle and key, kept per user; blind test | Only the list toggle (diagram-bar.js:109); nothing in the diagram-1108 diff | Design pass, then a rail per panel with a key and a saved fold |
| S13 | Select, edit and add on the picture; drag-and-drop library (sequence first) | Recorded as 1661 l and handed to diagram-1108's Expand step; the diff has none of it | Own workflow: design, then a build per kind, sequence first, with a blind test |
| S14 | Diagram side panels collapsible; no need for the left panel | Same as 1661 m | See 1661 m |
| S11 | Diagram kind picker alone on its row: what it does, redesign | Same as 1661 k (listed partial there); no Kind menu in main or the diagram-1108 diff | See 1661 k |
| 1693 b1 | The chat area spasms up and down (Agent greeting, 1920x1270, scrollbars, companion on) | Not reproduced headless at 1280 and 900; no fix | Reproduce at 1920x1270 with real scrollbars and the companion on; measure thread height over a send |
| 1643 b | Notes tab-switch pointerup 312 ms; dashboard 266 ms timer and 172 ms load frame | No commit names them | Profile with the lag reporter's trace, then fix |
| 1643 c | Chat send keydown 712 ms, frame 589 ms in nameMarkBuddyTempo | Handed to the 1693 b agent; the a0e78b worktree does not touch it | Profile an Agent greeting send with the companion on |
| 1620 categories b | Find what wrote "¦" for "&" ("Courses ¦ Study") | No grep hit for ¦ outside vendor code; no CHANGELOG line | Find the writer (model output or import), add a normaliser, repair stored names |
| 1620 topics c | How "conversation" was derived for a gym note | No commit or test | Reproduce the derivation and fix the word match |
| 1620 lag: backdrop and pointerout | Settings backdrop click 880 ms; dashboard card pointerout 312 to 344 ms | No entry; an earlier pointerout did not reproduce | Profile both at 4x CPU |
| N14 | Live desk drawing only inside the CPU budget (idle under 1%, moving under 3%) | No live-draw path, no budget measure; frame cache stays | Record the cached-frame CPU numbers, or close DG2 as not built |

### Partial (83)

| Ref | Ask | Evidence | Next step |
| --- | --- | --- | --- |
| 1692 00:35 / S3 | Built, partial and missing count for the owner; is everything built | companion-asks.md has statuses but no totals line, and many are stale (N3, N6, N7, N10 M; N11, N12 running) | Re-grade companion-asks.md on this head and put the counts at the top |
| 1692 b | Deep dives (desk, in-app, diagram) each with a coverage table and ranked list | desk-1670.md, inappdive-1107, diagram-dive-1107.md exist; table and ranked list not confirmed in each | Confirm, then run the builds |
| 1692 c/g / N17 | Two tracks: Atlas more detailed, generated companions own behaviour set | behaviour.py Mind is shared; no generated-only repertoire | Table of Atlas-only and generated-only behaviours, then build |
| 1692 g / N18 | Every motion drawn every frame; in-app p95 under 8 ms at 4x CPU | In-app rig continuous, desk frames cached; no p95 measurement | Measure p95; decide desk interpolation |
| 1692 m/n / 1683 g / N11 | The companion should sit on windows | Corrected by the orchestrator, 2026-11-08: the 10:29 log's tally is 11 tool windows, 8 minimised and no other listed window (no "perch", "no title" or "owned popup" counts), so every app was minimised and 0 standable edges is right; at 10:33 one maximised window gave 1 hang spot and the figure went to it ("eager hang: chosen"). The scan works; what is missing is life on an empty desk | 1692 p: window-free travel targets (taskbar edge, a free corner) so an empty desk still sees it move |
| 1692 p-budget | Live desk drawing within a CPU budget | No live path; budget not recorded | See N14 |
| 1692 e / N15 | Own activities with props (fishing, reading, beanbag, dinner, chasing sprites) | props.py has beanbag, rod, book, map, lantern, tea, stargaze; no dinner or sprite chase | Add dinner and sprite chase; check in-app parity |
| 1692 e/n / B1 / B3 / N16 | Lower body and nebula follow the pose, distinct silhouettes per pose, desk and in-app | In-app: six arrangements per pose (tests/test_lower_flow_1683b.py:53). Desk: render_desk_frames.js only skews one lower layer (lines 229-239); no per-pose rendered lower body | Per-pose desk frames and a distinct-silhouettes test |
| 1692 n / S15 | Wind-spirit travel: lean, trailing wisp, spiral on turn, motes, settle eddy; no ferocious blinking | Blink fixed 1b78d3d2; lean exists (engine.py:1078); no motes, turn spiral or eddy | Build them; test blinks per second on a trip |
| 1692 d (presence) | Ambient activities by hour and mood on both companions (doodling, blanket nap, leg swing included) | Desk props cover read, tea, stargaze, fishing, beanbag; presence.py (spells by hour and mood) is uncommitted in presence-desk-1108; no doodle, blanket or leg swing | Commit presence-desk; add the three acts; in-app pass |
| 1683 a | Even desk frame pacing; real Windows frame interval logged | pacing.py, host.py:70 timer; no p50 or p95 interval log line | Once-a-minute interval log, then the owner's log |
| 1683 c | Wisps and nebula move all the time, layered noise | Flow tests exist; desk frames still carry one lower body per pose | See 1692 e/n |
| 1683 lower-inapp | In-app wisps measured at 1440; lower body by position; in-app parity | ATLAS_LOWER_STATES, 20b8bee4; N16 open | Measure distinct arrangements per pose in Chromium |
| 1683 i-climb / T5 | Climb up the side of windows and of the screen | Window side climb (engine.py:2084) and wall pull-up exist; no upward climb along a screen side | Add the screen-side climb and a test |
| 1683 i-inspect / T8 | Inspect things (window corner, clock, cursor, new window) | Clock, peer_at_cursor, window_opened exist; no inspect act | Inspect act for a window corner and a new window; seeded test |
| 1683 x5 / N10 | In-app scrabble, pull-up, fling, miffed face | Spot-checked: pull-up exists (companion-throw.js:22-27 grab and slip), splat and slide, shake-off with flail and face (756-779); no scrabble anywhere in frontend/js | Add the in-app scrabble on a side splat; Chromium test |
| N2 | Flail airborne, scrabble on a wall slide | Desk built; app scrabble absent | See 1683 x5 |
| 1683 l | One shared mind for both companions | Python Mind on the desk, a JS mind in the app; BACKLOG 1678 still lists it | Say whether two ports count as shared; close or list the gap |
| 1683 deeper / B19 | Deeper behaviour tree, many detailed actions; every-limb transitions | props, extras, faces, screenwatch; N15 and N17 open; B19 every-limb bar open | Write the list of missing acts and limb transitions |
| 1683 p | One ledger of every companion ask | companion-asks.md exists; statuses stale | Re-grade (see 1692 00:35) |
| 1683 s / U16 | Load-dependent X11 test race fixed | e14dabb9 gives each Xvfb its own display; no real signal wait; no 20 loaded runs | Run 20 loaded runs with -n 3; wait on MapNotify |
| 1683 t | Come here row on the in-app menu too | Desk only (desk-companion.js:214, tests/test_overlay_come_1683.py) | Add the in-app row or say why not |
| 1683 y-ledger | Coverage ledger first; the dive closes only when every row is built or has a reason | N14, N15, N17, N18, N23, N25 open | Re-grade; dive stays open |
| 1645 | Polished goose-style overlay, default on Windows | overlay package and card fallback built; O5 owner check pending; later reports say it is not there yet | Owner O5 check |
| 1645 scope | Nothing that touches other windows | Superseded by 1683 i and w (perch, tuck) | Record the scope change in INBOX 1645 |
| 1638 b | Companion does not show; root out why | dpi and SetWindowPos fixes; later drops show it draws; no owner confirmation | Owner confirmation |
| 1670 a | Cut off on the ride; sits 20 px above the taskbar | Foot band (engine.py:293); the 10:55Z report came after; no alpha foot-margin test | Test the frame's alpha foot margin against the taskbar top |
| 1670 d | Drag to hang anywhere on the top edge | HANG_REACH, _grab_edge; no drag-to-y=0 assertion found | Add the assertion |
| 1670 e | Desk Quick search, Quick note and close button popups cleaned up | CSS and width fixes, wiring test; no rendered measurement of band, note height or close button | Measure in a sweep |
| 1670 f | No flicker or jolt; sits cleanly | Smoothness tests on simulation only | Owner check |
| 1670 i | Slow idle; non-Atlas walks, runs, climbs, crouches, sits, lies | Bob and drift tests; cat and walker gaits | Confirm crouch, lie and climb frames exist in sprites.py |
| 1670 j | Body and head turn to face the travel direction | Facing and flip in faces.py and sprites; no left-versus-right frame test | Add that test |
| 1670 l | Nebula stops flickering (desk) | Wash step 30% to 6%; not re-confirmed | Owner check |
| 1670 r | Display-paced timer, 16.7 ms plus or minus 3 | Simulation only | Owner check |
| 1670 u | Runs properly on Linux | x11.py and xlib.py on fakes; never on a real Linux desktop | A real Linux desktop run |
| 1607 c | Smoother masculine shoulder-to-arm join | 199e0be9 only measured it ("not changed") | Fix the cut line; add a measurement test |
| 1667/1634 a | The throw must not scroll the page; Playwright test by mouse, touch, keyboard reading scrollY | Guards exist; tests are string asserts; no test reads scrollY | Add the Playwright test; owner confirm |
| 1667 b | Throw frame step does no layout reads; under 4 ms a frame at 4x | Landing read moved before writes (13.6 to 0.8 ms median); no per-frame budget test | Probe forced layouts per throw frame |
| 1560 a | Forced layout in nameMarkBuddyBeat; the #dash-grid pointerout handler | afterClean deferrals; pointerout handler not found; 4 s pointerout recurred 11-07 | Find the listener; measure with 44 notes |
| 1667 d | Keep-up reads layout once a frame, stops while still | 8ff2c94 cut the rest loop to 0; Check 42, Obstacles 41, Tick 38, act timer 84 ms still open | Slice the control sweep across idle time |
| 1667 e | Under 16 ms forced layout per press (tab, Settings, pointerenter, atlas.js step) | test_forced_layout_1667.py, 53c1ba59; blend first arrival, sweeps, panelPinned, settings-find.js:340 and others open | Slice the sweep; widen afterClean's dirty test |
| 1667 j | Documents lag (atlas-motion loop, documents.js timer, /documents/7, tab-switch style) | First three not reproduced; tab-switch style cost open | Per-selector style profile |
| 1667 l | 4.5 s avatars.js timer after opening a note from a dashboard list | 071e9d21, 53c1ba59, probe; not reproduced on the owner's data | Repro with 44 seeded notes with list previews |
| 1667 n | Desk perch filter finds almost nothing | No branch holds it now (companion-s and edges2 merged) | See 1692 m/n |
| 1667 o | /chat/followups deadline; 5120 token context budget line | 777901f4 runs follow-ups in Quick; CHAT_PLAN B6 budget line not checked | Check B6 |
| 1694 b2 | Typed value field on diagram, whiteboard and mind map zoom | Diagram and whiteboard (whiteboard.js:681) done; mind map not confirmed | Check the mind map zoom readout |
| 1694 b3 | Present-mode page fields typeable with a list of every page and title | whiteboard.js:25638 pageField; titles and mind map present unchecked | Read the presets; check the mind map |
| 1661 a | Builder picture-first; the blocks list an outline that hides | Hide-the-list button (diagram-bar.js:109); Canvas and Blocks tabs remain | Lands with diagram-1108 |
| 1661 c | Templates, styles, align and distribute, find, copy as picture, shortcuts | Most built; no align or distribute; DOCUMENTS_PLAN R12 to R16 open | Build align and distribute in diagram-multi.js |
| 1661 e | Each connection once under its source as "to Y" with an editable label | Not confirmed in diagram-outline.js | Open a 3-edge flowchart and check |
| 1661 f | Connect handle and on-picture controls meet 3:1 on both themes | CSS comment claims it (diagram-lazy.css:1606); no measurement | Measure and add a contrast assertion |
| 1661 j / S10 | A further deep-dive round for features and look | Rounds 1 and 2 merged; DD-5, DD-10, DD-12, DD-13 not built; 1108 round has nothing committed | Run the features round after the direct-manipulation build |
| 1661 k | Kind picker as a labelled Kind menu in the Title row with samples | diagram-kindbar.js still a four-button .seg; not in work-order.md, so no agent owns it | Assign and build |
| 1693 a | Autouse clock.today pin in conftest plus a lint | Only the 8 reminder tests fixed (022fae4f); no autouse pin | Autouse fixture (full suite run) and the lint |
| 1691 | BACKGROUND_MODE (no thinking) for every background utility-model call | Follow-ups only (777901f4); no BACKGROUND_MODE in src; ten call sites unchanged | Add it to presets.py, apply to the ten sites, run pytest -m evals before and after |
| 1643 a | Graph redraws only while something moves | Not reproduced; 300-frame bound (eef88b5, d809297) | Owner's next graph log |
| 1620 tag + | Add tags popover opens under the card's + Tag | Now closes instead of dropping to the corner; no anchoring or search-card test | Keep it anchored to the live opener; test from a search card |
| 1620 topics b | Manage topics like tags (rename, merge, remove a note) | Rename in the graph only (graph-canvas.js:1559) | Manage topics list beside Manage tags |
| 1620 lag: Atlas | avatars.js 2249 ms dashboard timer; nameMarkBuddyKeepUp 114 to 337 ms | Only MoveTo, Glue, RideBox fixed | Measure KeepUp and the timer after nmbPlace |
| 1620 lag: models | /models/status 3220 ms; stop the 30 s model job | Job rows gone; 3.2 s not reproduced | Owner log from a slow runner |
| 904 | The 86-item OneNote bug list | About 20 to 25 of B01 to B88 still open (placed rows, owner questions, B50 splash, B04, B55, B70 part-fixed, B87a, B87b, B88a queued) | Work the placed rows and owner-question rows |
| T1 | Landing outcomes on both, prop tip-over included | Desk and most app outcomes built; app beanbag tip-over not found | Confirm app prop tip-over or mark it out |
| N5 | Edge hit squashes and slides, or wraps | Wrap built; squash render not rechecked | Measure the squash |
| N9 | Portal as travel and escape; share measured | _escape_roll uses portal; edges-1107.md measured 8.8% in a seeded hour, but no test pins it | Add the seeded-hour share test |
| S1 | Deep dives done; bugs, security and per-frame cost; plans after this PR | Dives and perf fixes landed; work-order still has the desk dive, the ANALYSIS/AUDIT/FABLE_BRIEF pass and "repeat until nothing new" unchecked | Run the desk dive and the ANALYSIS pass; give the owner a short found and fixed list |
| S16 | Lower body and nebula change little per pose | Same as 1692 e/n | See 1692 e/n |
| S20 | Owner's logs: no desk travel targets; chat keydown 712 ms; tempo 589 ms; tab 312 ms; dashboard 266 ms | Desk window-free targets not in main; lag lines unfixed | See 1692 p-log, 1643 b, 1643 c |

Also partial and counted above, with the same evidence as a row listed: 1683 x5 and N10 (one row), 1692 e/n with B1, B3 and N16, 1692 c/g with N17, 1692 g with N18, 1692 m/n with 1683 g and N11, 1683 s with U16, 1683 i-climb with T5, 1683 i-inspect with T8, 1683 deeper with B19, 1692 n with S15, 1692 00:35 with S3, 1661 j with S10.

### Asks the slices did not cover

- companion-asks.md rows not re-graded by any slice: T12 to T17, T19 to T27, T29 to T42, B4 to B15, B17, B18, B20 to B22, M1 to M3, M9 to M14, U2 to U5, U7 to U15, N1, N23, N24, N26. Most are BF, BM or BU in the ledger. The open ones: B4 (tail and idle body feel like a png, L), M1 and M2 (L), B14 (desk has 15 rendered poses against 55 app acts; the "no repeat in 10 minutes" bar not measured), M3 (desk sleepiness not checked), T32 (ride with a scroll not driven in WebKitGTK), N23 (react to everything, P), T31 and T41 and T42 (not reproduced; T42 and T31 are 1606 and 1598).
- INBOX: all 19 numbered entries (1694, 1693, 1692, 1691, 1683, 1671, 1670, 1667, 1661, 1645, 1643, 1638, 1633, 1620, 1612, 1607, 1606, 1598, 904) and the folded 1634 and 1560 have items. Checked: 1683 (n), (o), (q) and (x)(3) sit inside 1683 lower-inapp, 1683 d, 1683 p and 1683 i-tuck; 1620's seven drops are all listed.
- Not read by any slice: 1692 hover's real feel, the 1694 c1 lint's frozen list of readouts still plain, the 1694 c and d measurements, 1661 b's blind-test result, the 1620 tray close-to-tray path in tests/test_tray*.py.

## In progress (18)

| Ref | Ask | Branch | State |
| --- | --- | --- | --- |
| 1692 p-log | Trips to places with no window (taskbar edge, free corner, cursor's last rest); stop hiding when the app window returns | agent/presence-desk-1108 | Uncommitted; nap corner only (engine.py:1631); the hide on app return is not addressed |
| 1692 o trips / S6 | Trips several times an hour in visible modes (portal, sparkle blink, cloud, bubble); legs per hour measured | agent/presence-desk-1108 | Uncommitted: travel.py:23 adds blink, cloud, bubble; presence.py; tests/test_overlay_presence_1692.py untracked. Was listed missing; spot-check moved it here |
| 1692 f / S5 | In-app wrap gets an exit and entry (squish with wisps), never an instant swap; in-app ambient acts | agent/presence-desk-1108 | Uncommitted companion-travel.js adds blink, cloud, bubble and "the edge walk wraps with an exit and an entry"; the throw wrap in companion-throw.js is unchanged; agent/presence-app-1108 does not exist. Was listed missing |
| 1692 composer | Composer continuous improvement | agent/composer-r3-1107 | Two commits ahead of the head (ddbe2f7a, 2d271656) |
| 1683 y-dynamic | "Make it really dynamic ... also portalling" | none (queued dive rounds, N25) | Not started |
| N25 | Layered multi-round deep dives per surface | agent/composer-r3-1107 and queue | Composer round 3 running; desk dive queued |
| 1661 g / S7 | Arrow-added node does not overlap (0 in 20 adds); overlays follow scroll | agent/diagram-1108 | Uncommitted; no 20-adds overlap test |
| 1661 h / S8 | A press on empty canvas and Escape clear the selection | agent/diagram-1108 | Uncommitted, with a test |
| 1661 i / S9 | Name Canvas and Blocks for what they are | agent/diagram-1108 | Uncommitted rename to Picture and List, help and parity test |
| 1661 l | Direct manipulation on the picture for every kind | agent/diagram-1108 (Expand step) | Planned only; nothing in the diff (see S13) |
| 1693 b2 | Note card, badge, Why trail and timing survive a session switch | worktree-agent-a0e78b4da0f788667 | Uncommitted: chat-turn.js saves `by` and `why`, routes_conversations.py, tests/test_chat_reload_by_1693.py untracked; timing not seen. Was listed missing |
| 1693 b3 | "whatcha doing" gets a companion line | worktree-agent-a0e78b4da0f788667 | Uncommitted: routes_chat.py and question_noise.py map "whatcha doing" to a how-are-you line. Was listed missing |
| S18 | Chat spasm; card, badge and Why stick after reload | worktree-agent-a0e78b4da0f788667 | Reload half uncommitted; the spasm half has no fix (1693 b1) |

## Unverifiable (9)

| Ref | Ask | Why |
| --- | --- | --- |
| 1606 | Patting over Atlas's head must not lift it 30 px | Not reproduced in 8 variations (max 9.7 px); needs the owner's window size or a recording |
| 1598 | Scrolling Ask must not carry Atlas over the top bar | Not reproduced at 1440 and 1024; no clamp test |
| 1671 | Win+arrow snap resets to the unmaximised window | Needs Windows; no WM_SIZE timing log added |
| 1691 b | Paste the 15 s /chat/followups log if it returns | Waiting on the owner |
| 1620 tray | Closing with X leaves a tray icon; companion shows over Wallpaper Engine | Needs Windows with Wallpaper Engine |
| T11 | No 90 degree turn after landing | Owner recheck on Windows |
| M8 | Desk very lightweight | Real CPU on Windows unmeasured |
| N20 | Desk look repaints at once | Windows |
| N22 | Overlay wins over the card; twenty toggles | Windows |

## Done (106)

| Ref | Ask | Evidence |
| --- | --- | --- |
| 1692 hover / S2 | Hover does not make Atlas instantly mad; a poke is a jab that goes back out | extras.py:42-44, 230-248; 0b1c80a6 |
| 1692 hover2 / S4 | Resize ring hangs by the head | sizing.py:77-84; tests/test_overlay_ring_1692.py |
| 1692 a / N8 | Floor is the screen bottom with the taskbar hidden | a888e584; tests/test_companion_taskbar_1107.py |
| 1692 b/d / N24 | Research desktop pets into a findings file | research-companions-1107.md (29 rows) |
| 1692 h / N19 | Size handle on the figure's corner; Small, Medium, Large | 34fabfe2, 62101c34; test_overlay_size_1107.py |
| 1692 i | Desk look repaints at once | 15b25e69; tests/test_desk_look_1107.py |
| 1692 j / N21 | Hanging handle cursor nwse | be9722a9; test_desk_handle_cursor_1107.py |
| 1692 k | Desk figure from the customised figure; twenty toggles | tests/test_desk_look_1107.py:127, :177 |
| 1692 l | A late overlay wins over the card; no sticky timeout | tests/test_desk_look_1107.py:137, :184 |
| 1692 o / N13 | Poof stays, no footprints, no constant long walks | travel.py MODES; LONG_WALK_GAP engine.py:160 |
| 1692 q / N12 | Mind with needs, curves, chains, interrupts, seeded hour | behaviour.py Mind; tests/test_companion_mind_1107.py:154; companion-s merged |
| 1692 presets | Desk Small, Medium, Large share the in-app steps | 62101c34 |
| 1692 edges | Hang or tuck behind edges, taskbar, window; scrabble and slide | edges2 merged at b04c2b5d (0ad5ff8a, ec792128); test_overlay_edges_1107, tuck, scrabble |
| 1683 b | Throw and fall rotation continuous, settles upright | test_overlay_spin_1683.py; landing.py |
| 1683 d | Desk menu not short on first open | test_desk_menu_first_open_1683.py |
| 1683 e | Loops wrap seamlessly; blends between acts | tests/test_overlay_seams_1683e.py |
| 1683 f / T9 | Travel by body; puff and portal rare | travel.py pick_mode; test_overlay_travel_1683.py |
| 1683 h | A hang ends by choice | engine.py HANG_ENDS; test_overlay_hang_end_1683.py |
| 1683 i-wrap / T4 / T18 | Walk off one side and back on the other; same for a throw | Spot-checked: engine.py:2335 "walks off one edge, comes in from the other", :2546 edgein warp, travel.py:52; tests/test_overlay_travel_1683.py, test_overlay_landing_1683k.py:135 |
| 1683 i-tuck / T6 / T7 / N6 / N7 | Tuck behind taskbar, edges and a smaller window | engine.py Cover, TUCK_PLAN; test_overlay_tuck_1107.py, test_overlay_peek_edges_1107.py |
| 1683 j | Continuous motion between acts, no repeats | d19b625f, 2c223072 |
| 1683 k-landing | Landing by outcome; flail airborne | landing.py; test_overlay_landing_1683k.py |
| 1683 k-edge | Screen edge: squash and slide, or wrap through | landing.py wrap; engine.py WALL_SCRABBLE |
| 1683 x1 / N3 | After a scrabble, pull up or drop (desk) | 5a4b9a8b; test_overlay_wallpull_1108.py |
| 1683 x2 / T2 / T3 / N4 | Fast window move flings; lying one slides off; slow move anchored | db4e8ab9; tests/test_overlay_fling_1107.py |
| 1683 x4 | Portal as escape and in the mix, share measured | da779ba8; edges-1107.md 8.8% |
| 1683 m | Resize circle at bottom right when hanging | 9d5fd92 |
| 1683 r / U1 | Resize the desk companion like the in-app one | sizing.py; HISTORY Group 3 |
| 1683 u | Nap sticks until woken; varied exits | 66d494d; test_overlay_nap_1683u.py |
| 1683 v | Rights within 0.6 s after a throw | 861795d; test_overlay_land_1683.py |
| 1683 w | Hang spots and window perches, not only the taskbar | perches.hang_spots; test_overlay_hang_spots_1683.py |
| 1683 y-peek | Peek from behind the real taskbar, appbars, any edge when hidden | win32.py ABM_*; test_overlay_edges_1107.py |
| 1638 a | Where the desktop toggle went | index.html:12139 #desktop-companion-row |
| 1638 c | Goose-style design from Desktop Goose ideas | BACKLOG O1 to O4; ffebbd1a |
| 1633 | Trace the desktop path at info level | Logged steps; tests/test_desk_companion.py |
| 1670 b | Desk companion moves and roams | test_overlay_roam.py, test_overlay_alive_1670.py |
| 1670 c | Keeps the last unlocked look when locked | test_desk_look_locked_1670.py |
| 1670 g / T28 | Rich NPC life, tuck, curious | engine, behaviour, travel; edges2 merged |
| 1670 h | More desk menu options | desk-companion.js grouped rows; test_desk_menu_1670.py |
| 1670 k | Better tail, wisp and nebula physics | engine.py TAIL_WANDER; test_flow_1683.py |
| 1670 m | Long-distance travel and transitions | test_overlay_modes_1107.py |
| 1670 n | Buddy not nuisance; homes at edges | test_overlay_dest_1683.py |
| 1670 o | Steps aside from the caret while typing | Spot-checked: tests/test_overlay_rest_1670.py:159 and :174 (steps off within a second, never on a trip), :214 Win32 caret read |
| 1670 p | Still at rest, alive in place, no jitter | test_overlay_rest_1670.py; 70ef502 |
| 1670 q | Long alive hang; soft landing | test_overlay_hang_throw_1670.py |
| 1670 s | Throws rarely end hanging at the top | test_overlay_throw_ceiling_1670.py |
| 1670 t | Continuous rotation in the air | SPIN_STEPS 48; test_overlay_tumble_1670.py |
| 1670 v | Hidden-for-maximised bug; stuck pose after throw from hang | 236fd45 |
| 1607 a | Masculine eyes: both blink, no resting lid | test_atlas_lids_1301.py; test_atlas_blink_both_eyes_1644.py |
| 1634 a | plan.land() reads every box before any write | b0c8cd4e; test_throw_surfaces_1667.py |
| 1634 b | Keys and wheel on the carried figure swallowed | test_companion_throw_scroll.py; drag-edge.js:75 |
| 1560 b | /models/status answers from cache | ollama_client.py:200 |
| 1560 c | Model-info poll writes no job lines | core/jobs.py:185-188 |
| 1560 d | /voice/transcribe without the huggingface.co check | ai/voice.py:159-163 |
| 1667 g | Lag reporter names the real apiJson caller | Spot-checked: frontend/js/lag-watch.js:91-94 skips the apiJson wrapper |
| 1667 h | First-run toast poll reads no layout | test_forced_layout_1667.py |
| 1667 k | Throw landing reads every rect before the flight | b0c8cd4e; test_throw_surfaces_1667.py |
| 1694 a | Lightbox pinch zoom factor | lightbox-view.js:38-39; test_lightbox_pinch_1694.py |
| 1694 b1 | Typeable lightbox zoom with presets | value-field.js; 06678b49 |
| 1694 b4 | Value field recipe in DESIGN.md with a lint | docs/DESIGN.md:701; test_ui_recipes.py |
| 1694 c1 | Typeable values on slider readouts | valueField.range; lint with a frozen remainder |
| 1694 c2 / S17 | Sketch size number fits the slider | 72da44b2; test_value_field_dock_1694.py:28 |
| 1694 d / S19 | Gap under the graph popup close button | Spot-checked: e5f56578; tests/test_value_field_dock_1694.py:36 pins it (the slice said no test) |
| 1612 a | Help topics Where line spacing and rules | settings-find.js:746; test_settings_row_bar.py |
| 1661 b | One toolbar row at every width | CHANGELOG.md:203; test_diagram_1661a.py |
| 1661 d | Connections changed on the picture | diagram-edge-pick.js:114, :140 |
| 1661 l2 / S12 | Add a block sheet rows keep their height | b47f2fbd; Spot-checked: tests/test_sheet_rows_1661.py exists (the slice said no test) |
| 1620 categories a | Tidy box does not cut the category list | CHANGELOG line 299 |
| 1620 topics a | Topic chip says why a note is in it | CHANGELOG line 299 |
| 1620 constellation | Dashboard constellation draws | CHANGELOG line 300; no regression test |
| 1620 companion menu | Show or hide on desktop in the right-click menu | companion-menu.js:371 |
| 1620 installer | No desktop shortcut by default | installer.iss:91 unchecked |
| 1620 Settings search | settings-find build cost | CHANGELOG line 302 (452 to 6 ms) |
| 1620 drag-edge | Edge-scroll loop sleeps at rest | CHANGELOG line 304 |
| 1620 changelog fold | Fold toggle and closeSettingsModal | CHANGELOG line 303 (1,576 to 21 ms); closing still 267 ms at 4x |
| 1620 agents | Use 3 agents | Standing order in use |
| T10 | Perches on every mind map node | bfe5f817 |
| B2 | In-app lower body natural movement | atlas-life.js; test_lower_flow_1683b.py |
| M4 | Desk reads a book, beanbag, fishing, push-ups, map | props.py |
| M5 | Desk micro-expressions | faces.py; test_overlay_faces.py |
| M6 | Desk reacts to computer events | screenwatch.py |
| M7 | Desk reacts to pointer gestures | extras.py Pointer |
| U6 | Right-click to switch looks on the desk | companion_options enabled; 519119aa |

The done table merges rows the slices listed twice (the ledger and session refs are named beside the INBOX ref), so it has fewer lines than the count of 106.

## Spot-check corrections made in this pass

- Done claims I checked and kept: 1670 o (caret tests), 1667 g (lag-watch.js), 1694 d (it has a test after all), 1661 l2 (it has a test after all), 1683 i-wrap (engine edge walk).
- Done claims I downgraded: N10 to partial (no in-app scrabble); N16 to partial (desk lower body is one skewed layer, not per-pose frames).
- Partial claims I upgraded: T4 and T18 to done (the edge walk exists, engine.py:2335).
- Missing claims I checked and kept: 1634 c (after-change reads at avatars.js:9195, :9209), 1667 c (loaded at notes-list.js:3554), 1612 b (no summary field).
- Missing claims I moved to in progress: 1693 b2, 1693 b3 (worktree-agent-a0e78b4da0f788667), 1692 o trips, 1692 f and S5 (presence-desk-1108, uncommitted).
- Stale branch claims I fixed: edges2-1108 and companion-s-1107 are merged into the head, so 1692 edges and N12 are done, 1670 g needs no merge step, N11 and 1667 n are partial (real-desktop scan), not in flight.
- Risk: the diagram-1108, presence-desk-1108 and a0e78b worktrees hold all their work uncommitted. A lost worktree loses it.
