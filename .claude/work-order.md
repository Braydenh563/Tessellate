mode: continue
status: done
closed: 2026-11-12 (PR 216 merged; its unchecked boxes are built, placed in the plans or LEDGER rows, or superseded, see HISTORY and docs/roadmap/LEDGER.md)
pr: 216
max-continues: 60
max-idle-minutes: 60
finish-up: 70%
started: 2026-11-07 14:40Z
tier: max (weekly 32% at 2026-11-08 16:00Z), four agents at once, Sonnet or Haiku, one Opus for design or risky review; never Fable; owner away from 2026-11-08 16:00Z until about 2026-11-09 06:00Z to 07:00Z (late afternoon owner time, UTC+10)

## 2026-11-09 away queue (tier: four agents, at most two Opus, Haiku scouts extra) (owner asleep from ~14:50Z; stop at 70% weekly; context 200k does not stop the run, owner override)
- [ ] Push the 9 local commits when CI on 7d814c1 finishes; fix its failures
- [ ] Merge zoom2-1109 (1717), desklane-1109 (1696 a,b,h,i,k,aa,kk; 1710 a,b; 1711 b; 1718), small3-1109 (constellation pause, 1693 a)
- [ ] Composer deep-audit round (1719 c), then build its findings in Sonnet batches
- [ ] Throw off the top of the screen, both companions (1719 a)
- [ ] Life and biological design pass (1719 b) with 1696 j, v-w, dd; then Sonnet batches
- [ ] Remaining: 1711 a,d; 1683 a (desk lower-body frames); audit rows 21, 36; further 37a batches; zoom and desk leftovers
- [ ] Then, owner 2026-11-09 ~15:00Z ("the rest includes ..."): every open audit and deep-dive finding (audit-1031-ranked.md, FABLE_BRIEF, deep-dive files), every open INBOX item outside the BACKLOG, every open plan item in docs/roadmap/*_PLAN.md, and continuous refinement: optimisation, bug and security fixing, poke holes (reviewer, security-reviewer, blind-tester rounds), UI and UX redesign and fixes, backend and frontend
- [ ] Priority polish (owner 2026-11-09 ~15:15Z): diagram builder finished and polished (open dgml/dgpic leftovers: shelf touch, gap drop marker, 390 px, default fold call), composer improved round after round, companions in-app and desk; blind-tester and ux-auditor on each
- [ ] Docs and README kept current per merge (owner 2026-11-09 ~15:10Z): CHANGELOG, README numbers and names (test_readme_freshness), ARCHITECTURE, DESIGN, Guide topics; a docs pass before the boundary
- [ ] BACKLOG boundary: HANDOVER Now and Morning summary, push, retro

## 2026-11-08 away queue (HANDOVER Now 2026-11-08g)
- [ ] Merge desklayers-1108 (C1, C4), appacts-1108 (D1, D2), dgmlive-1108 (diagram real-browser checks), deskmood-1108 (sad when left alone, welcome back, confused on a missed landing): targeted tests, reviewer on UI, push
- [ ] Folder CONTEXT.md in frontend/js, src/tessellate/ai, src/tessellate/core/overlay (owner yes 16:00Z)
- [ ] atlascat C2, C3, C5 (atlas-life.js tail acts and lower states) after desklayers
- [ ] perf P6, P7, P9 (audit-1108-perf.md); coil breath on the compositor (restlayout-1108.md)
- [ ] "put it in today's note" read by the move reader; r3fix single-list intro-line route
- [ ] Layered deep dive next round per surface (desk, in-app, Atlas, diagram, composer)
- [ ] Open audit rows on other surfaces (audit-1031-ranked.md first; board, mind map, notes, documents, code editor, OCR), FABLE_BRIEF findings, plans and BACKLOG, smallest first (owner 16:35Z)
- [ ] Session end at 60% weekly or queue done: full suite, Morning summary, retro

## 2026-11-07 overnight queue (HANDOVER Now 2026-11-07c)
- [x] Merge land1683 (e7ad8fe9) (agent/land1683-1107): overlay tests serially, CHANGELOG, CODEMAP, push
- [x] Merge value-field (1d562540; follow-up agent/vf2-1107: keyboard reach, graph clock, scrubber) (agent/value-field-1107, INBOX 1694 b c): every slider readout typeable, lint
- [x] Atlas composite and afterFrames regressions (93b010af; follow-up agent/atlasidle2-1107)
- [x] CI fixes 1a15ca00 (6 failures) and atlasidle2 merged 399f5e3f (3 refused animations to 0; restyle unchanged)
- [ ] Atlas at-rest writers (workflow wf_381edf17-a3a, agent/atlaswriters-1107)
- [ ] Merge companion-s (agent/companion-s-1107): window perch bug, the 1683 (l) mind, S rows; reviewer
- [ ] Coverage ledger of every owner ask (1683 a to y, 1692 a to q, 1694) against code and tests
- [ ] 1683 (x)(y) build: pull-up, fling off a moved window, slide off, poof or portal escape with a miffed face, tuck behind smaller windows, peek from the taskbar on any edge, hidden taskbar, sidebars; in-app parity
- [x] INBOX 1667 perf: partial 5d6bfcae (scroll-edge sync); follow-up agent/atlasidle-1107: idle Atlas restyle 2.2-3.2 s per 6 s at 4x, note-open long tasks
- [ ] Layered deep dive round 1: desk companion (research, audit, fix, re-audit)
- [ ] Deep dive round 1: in-app companion and Atlas
- [x] Deep dive round 1: diagram builder (41a4919f, diagram-dive-1107.md, DD-1 to DD-15)
- [ ] Diagram build: Tier 1 plus DD-7, 8, 9, 14 (workflow wf_cf66c311-c38, branch agent/diagbuild-1107, then review, UX audit, blind test, refix)
- [ ] Deep dive round 1: composer (class rule 1357, parity decision 75)
- [ ] Repeat rounds per surface until a round finds nothing new
- [ ] Open deep-audit and Fable findings: ANALYSIS.md, AUDIT.md, FABLE_BRIEF.md
- [ ] Then plans, BACKLOG, the rest of the 2026-11-07 order
- [ ] Session end: full suite, INBOX 1693, HANDOVER morning summary, retro

- 17:4xZ: companion-s merged locally as c5a644b6 (not pushed): 6 overlay tests fail, all caused by companion-s (pass on ^1, fail on ^2). Fix workflow wf_32497065-27e (fix, review, refix) in the main checkout. Push after it is green, then start the edges build.
- 17:5xZ: diagbuild done (agent/diagbuild-1107, 9 commits: DD-1,2,3,4,7,8 part,9 small,14 + refix of review, UX and blind findings); merge after the companion-s fix workflow lands. Composer round 1 started (wf_ca4f2f32-3d4: research, audit, verify, fix on agent/composer-r1-1107, review, refix). Edges build waits for the companion-s fix (both edit engine.py).
- 19:3xZ: pushed the companion-s merge and its fixes (15688baa, CodeQL 2084/2085 fixed). Composer round 1 done on agent/composer-r1-1107 (7 commits, 12580 passed). Started: edges build wf_2a203452-821 (agent/edges-1107), composer round 2 wf_ee390834-aa3 on the round 1 branch. Waiting to merge after the companion-s fix refix lands: diagbuild, atlaswriters, then composer r1+r2. Next: the Atlas 52 refused animations under the entrance fade.
- 20:1xZ: pushed 0dd4c8a2: diagbuild and atlaswriters merged; boot trims (wf_414073e7-a65) under the ratchet, 260,814 of 260,860, two load-order guards restored after review. Queued (decision taken, standing order 3): strip leading indentation from served JS in asset_strip (line numbers kept; measured about 8.8 KB gzipped off boot), then lower TOTAL_CAP by the saving so the ratchet keeps its bite; bump STRIP_VERSION; acorn token check in test_asset_strip must stay green.
- 21:1xZ: composer r1+r2 merged (23817aea, 11170 passed on the merged composer/chat/help/lint set); r2 not dry (27 findings, 14 verified, fixed E1 tables, E2 negation, E4 missing property, E5 subject carry, E7 undo, E14 accents, E19 to E21, E26; rejected 3 with route evidence). Round 3 queued: digest no-term ask, oldest-note table row, model-on parity (decision 75), D8, research rows. CI fix e496e58e (chat harness chatConv). Running: edges, atlasfade, diagbuild r2 (wf_022acef8-437).
- 22:5xZ pushed edges (90ae25c2) and atlasfade (aa64e4dd) merges after 2184 overlay/desk/companion/atlas tests and 1144 narrow tests passed. Running: diagbuild r2, inappdive.
- 23:2xZ: CI 3.11 red (phone ask over-broad) fixed in b1847e49, pushed. diagbuild r2 merged locally (a1b488a1), tests running (scratchpad/diag.log). Composer round 3 started wf_3e346f99-9c8 (agent/composer-r3-1107). Running: inappdive.
- 23:1xZ: CI fixes pushed (b1847e49 phone ask, 81f7418b write-lock probe order); diagbuild r2 pushed (1680 passed). Automated review 5815491995 (11 findings) -> wf_2079bad2-bf2 on agent/review-1107. Running: composer r3 wf_3e346f99-9c8, inappdive wf_7462cb70-ebc.
- 00:1xZ: merged+pushed inappdive (C1 0% overlap on New note at 390, 4 of 4 loads; focus ring, Quieter, Focus companion; 2 text pins updated with Intent moved) and review fixes (10 of 11 real, 1356+723 tests passed). Composer r3 running.
- 00:0xZ: edges2-1108 started (wf_14eb9563-55e: in-app side tuck, browser shake-off, desk wall pull-up, upside-down top peek). Decision (order 3, no owner answer): the figure is "the companion" in all copy; "Atlas" stays its name and look; "avatar" and "guide" for the figure become "companion" (the Guide is the help chat only). Next free slot: that copy pass across Settings, the Guide topics, the palette and menus, with test_manual_parity.
- 00:5xZ: owner drops: desk hover anger and ring (fixed, 1692), presence (wf_574fd0e3-8eb running), diagram builder (1661 g to j: arrow-added node overlap, scroll-offset rings and edit field, no deselect on empty canvas, Canvas/Blocks names; then a features and look round). Diagram workflow starts at the next free slot, before anything else.
- 01:1xZ: diagram 1661 l and m (direct manipulation on the picture for every kind, both panels fold): handed to diagram-1108's Expand step; what it leaves gets its own workflow next (Opus design, Sonnet build per kind, blind-tester builds a diagram without the left panel).
