# Ledger verified (2026-11-12)

## Counts by status

- fixed: 33
- partly: 56
- open: 18
- blocked-hardware: 5
- owner-call: 9
- stale: 14
- total: 135

## Open and partly, by batch

### Bk1
- O39 (M): BK12 200-row reminders payload remains (OPEN 4277); BK6 not evidenced; K27 dead routes owner call
- P19 (M): E70 server idempotency by turn id not built; no turn_id guard in agent.py or chat routes
- P20 (L): recordings, bookmarks, files in a private space not sealed; deleting a locked space shows 423 message, no unlock prompt

### Bk2
- O34 (L): D24 whiteboard.js names left; D23 359 ORM queries in routes owner-call
- P8 (L): index.html 16,501 lines, status.js 3,321, notes-list.js 3,734, chat.js 1,661 not split
- P9 (L): Brief 62: no src/tessellate/data, no tests/test_import_time.py; question_noise.py 2,818 and composer_tables.py 1,630 lines hold data inline

### Ci1
- O28 (M): D4 --durations=0 needs one CI run (hardware-only CI); D3 slow tests true-deferred

### Ci1, Sh1, Gr1, Do2, Bk2
- X15 (L): D9 composed mount not started; D19 gate unmet; D22 to D25 ratchets partly

### Co1
- O4 (M): 'and the dentist' asks what is meant; frame not saved with a chat (W34 skipped)
- O6 (M): D23 client-side undo wording (OPEN 4148); undo after 'delete it' not shown fixed
- X4 (M): B26 Q5 title, Q6 list-add rule, B24 undo sentences, B27 similar-to ranking

### Co1, Co2
- P25 (M): F8 'wats on my shoping list' typo, F9 'this week' no day, F13 h frame-only window, i two summaries

### Co2
- O11 (S): 'leads by quote not name' for a joke note has no explicit fix or test
- X2 (M): B3 title-less citation vs list naming, B7 latest on sourdough, B10 verb-for-noun 'books', 'what do I want to read'
- X5 (M): B33 lowercased 'orchard', B34 joke note naming decision, B31 backlinks 'link to Mum' and 'bookmarks' mapping

### Co2, Da1, Co3
- P26 (L): G3, G5 guide leads, G6 today line and year gaps, G8 poke table avatars.js:2731, G9 week_review, G12 template, G14 e, i, dashboard.js:526,633

### Co3
- P27 (M): name rules 5 and 4 only wired for first hello and dashboard; Guide 'profile' topic (help_topics_more.py:309) lacks 'call me Sam'; no 20-turn eval
- X13 (M): C35 citation bracket (composer spoke) and remaining rows not individually closed

### Cp1
- I17 (M): **Fixed a7e56bda1** (with 26092ac88). Stand-loop drift and floater breath were already built (E3: `STAND_LEAN`, `_stand_breath`, `drift_phase` on vitals); the round-count cheer now runs on both sides. Left: the media-playing reaction, **blocked-hardware**: it needs the Windows audio session (an in-app half alone is refused by the catalogue's one-sided lint)
- P6 (M): **Fixed 26092ac88** (reaction budget of four a minute, `NMB_REACT_BUDGET`; measured in a browser: 0 snaps in 600 s, 21 distinct motions, 35 to 44 ms reaction latency)
- P7 (S): **Fixed 26092ac88** (glance before the dodge, `milestone` row) and a7e56bda1 (the desk cheers too)
- P36 (S): **Verified, no code change needed** (2026-11-12 drive with the character scripts held 9 s: 4 saved assistant turns had 0 avatar children while `charactersLoaded` was false, then 3 resting plus 1 live Atlas and 0 empty holders)
- X8 (M): **Fixed 42e037951** (the large view's fit reads a part's style only when it reaches past the counted box: 455 style reads to 10). The other hot spots were driven at 4x throttle and did not reproduce above 50 ms

### Cp1, Cp2
- X18 (L): **Fixed 26092ac88, a7e56bda1**. E1, E2, E3, E5, E6 were already built (OPEN.md:291-296); N8 and N10 are built on both sides; N9 is covered by `typing_burst`. E4 is the owner-call (O37). The desk looks are fake-transport tests only, not seen on real Windows

### Cp2
- I12 (L): **Left, owner-call and a human rater**: the travel art redraw (B65 L9) is design work whose look only the owner can judge on Windows. E1, E2, E3, E5, E6 are built; E4 is O37
- I21 (L): **Partly, Fixed 05b51746d** for catch mid-air (`caught`, both sides; driven in a browser: a click on a flight, the reaction on the landing 1.9 s later). Left, **needs new art and a human rater**: hold still (legs dangle), carry over, tail pull, drag skid, toss up, pointer chase. Each needs frames the desk does not ship, and the catalogue refuses a one-sided act
- O16 (M): **Left, owner-call and a human rater**: L9 new travel art is a redraw judged by eye on Windows; L10 hop chain was done earlier
- O37 (M): **Left, owner-call** (OPEN.md:294, w34-L1-1111.md): the masculine Atlas head, eyes and shoulder join wait for the owner's pick

### Da1
- I8 (L): 380ms style-and-layout first frame (13k nodes); dashboard.js widget fill callbacks 98-119ms (lag-1111.md:8,16 Not fixed). Done: named timers, heatmap scroll reads, resize observer
- P11 (S): 839 and 841 never checked (no text located for either)
- X12 (M): the other nine W21 rows not individually closed

### Dg1
- O19 (M): C4 Connect words on sideways phone (no 480 step) and door dialog repeat (design); Versions 'Named only' filter (no code hit)

### Do1
- O27 (L): D39 status-bar Autocorrect switch; deferred-large D22,D42,D43,D47,D52,DC13; DC1/DC2 lock code
- X14 (L): about 47 old documents audit rows not re-verified; DC1 and DC2 lock

### Do2
- O33 (L): D27 whiteboard.js 26,201 and whiteboard-map.js 11,408 lines not split (true-deferred)

### Ev1
- P15 (L): 97 chart maker and answer shapes (only ask-chart.js exists), 98 goals and lists (no surface at all)
- X20 (L): 265 true, 125 owner-call, 22 hardware-only, 153 unverifiable remain, listed by spoke in w34-*.md
- X23 (M): W5, W16 to W18 no record; W32 left E9 (hardware), E10 BK6/BK10/BK12/K36, E12 owner

### Gr1
- O30 (M): D12 (500-note hover p50 83 ms) and D14 (redraw only while moving) owner-call tracked in plans

### Sh1
- P4 (S): drive the reminder edit form and measure that time, priority, repeat, alert share one height
- P12 (M): no Radix, shadcn or APG element comparison record
- P16 (S): notes-list.js:331 date operators match only ISO before:/after:; filter box lacks day names
- P17 (S): pasted #/Manual and #/Statistics ignored at load; no Manual handling in router.js
- P22 (S): #graph-new popover (index.html:4766) has no data-help-for; refresh icon report not reproduced
- P32 (M): tour 455px spill not investigated; Memory and Logs panes hide h3 on a phone (.jump-echo)
- X6 (M): Notes filter box still ISO only (notes-list.js:331); real-browser typing unverified

### Sh2
- X1 (S): record then reload run not driven (static tests only)
- X16 (M): D16 #graph-options and #meeting-overlay templates, D18 server trim needs a decision, remaining boot-CSS laziness unmeasured

### Wb1
- I25 (S): present-mode page counters and preset dropdowns not checked; trackpad zoom unmeasurable without hardware

### composer-acts
- D23 (r2:62) (S): typed 'undo' after an act answers Undo key help (real undo client-side); confirm wordings unification not verified
- D10 (S): bare 'yes' after an offer card not answered; no test
- D23 (S): undo-after-act wording client side; server confirm wording not unified/verified
- F3 (S): 'undo' after 'delete it' answers key help; real undo client side

### composer-agenda
- F9 (S): 'this week' with no day as clause, plumber note in the week, mood-note exclusion not re-verified

### composer-asks
- F8 (S): 'wats on my shoping list' answers Lisbon packing list not Shopping; 'what's in my budget' picks November not re-checked
- G11 (M): 'how much more cheese than milk' returns Milk 1.20 only; no arithmetic route

### composer-chat
- F4 (M): 'you're not very helpful' searched as a note, 'say that again', 'what did I just add'; recheck via route

### composer-chips
- F5 (S): act cards and 'Nothing is overdue.' chips not checked

### composer-dialogue
- F1 (L): general 'reads what the last answer showed' (state beyond last question and 5 titles) not verified or tested
- F13 (M): h 'the week before' and 'who am I going with' return generic lines; i (two summary shapes) and j ('what links to it') not verified

### composer-fx
- FX2 (M): Z58, Z68 (needs model-up Ask run), Z70, Z46 recast, Z23, Z26, Z27 unverified

### composer-guide
- G5 (S): 'how do I record a meeting' lead keeping 'there' and miss-line blaming missing model not re-checked

### composer-lines
- E18 (S): repeat in 'milk' line still reproduced; 'what did I write about in October' restates a line
- D20 (S): 'compare Tokyo and Lisbon' still opens 'Of the notes found...' and repeats '(**Tokyo trip**)' cites; fix opener and repeated cite
- G1 (S): 'how far did I run' adds goal to distance (16 km for 6 km); no fix or test

### composer-misc
- G14 (M): per-letter recheck; chip code and 'Something sometime' magic add not examined

### composer-parity
- P1 (M): routes_chat composed_preview sent first, ungated on composer confidence; needs gate + test; model-on check needs real model
- D28 (S): no per-surface title-less naming parity test (composer vs model-context)
- PAR1 (M): 'do my notes contradict each other' answers 'None of your notes mention contradict'; supersede.py not wired to composer; composer_suggest.py:52 _IMPERATIVE unchanged

### composer-perf
- P6 (M): composer_digest_lines.py:321 _subject_facts and :198 _said_piece present; chat_pool.py:477 _raw_results uncapped; no re-measure on 500 notes

### composer-remarks
- G8 (S): poke-line table avatars.js (fixed two per mood) and dated thing in next three days not verified

### composer-reminders
- G3 (S): stats ask fifth wording and 'agenda deadline' not verified
- G10 (S): 'remember to take the bins out tonight' returns None; 'between 8 and 10' becomes 09:00

### per batch
- X24 (L): remaining of the 62 (K11, K13, K26, K33, E43, U*, B*, S*, D43, D52, S49, S77) unverified

## Blocked-hardware and owner-call

- I22 [blocked-hardware, Cp2, S]: OPEN B64: owner's 8 fps needs real-Windows layered-window trace
- I23 [blocked-hardware, Cp2, S]: OPEN B66: needs next owner Windows log with away-flip intervals and window styles
- I28 [blocked-hardware, Cp2, M]: every desk motion unverified on real Windows (OPEN P6)
- I29 [blocked-hardware, Cp2, S]: OPEN B62: engine fix done; owner's Windows must confirm, log taskbar rect if gap persists
- O24 [owner-call, Co3, S]: OPEN:228 C30: Ask at 720/960 has 0 overflow; redesign is an owner call
- O41 [owner-call, none, S]: OPEN:307 E13 no repro: no writer of the broken-bar character; needs owner's data
- O44 [owner-call, Ev1, L]: audit inventory; OPEN:312 E16 W34 owner-call
- O46 [owner-call, Ev1, M]: owner-asks audit; OPEN:317 E21 W34 owner-call
- O47 [owner-call, Do1, L]: DOCUMENTS_PLAN; OPEN:323 F1 partly built; remainder tracked in plan
- O50 [owner-call, Co3, L]: CHAT_PLAN; OPEN:326 F4 W34 owner-call
- O51 [owner-call, Ui1, L]: WORLD_CLASS_PLAN F5: multi-window, torch at launch, F1 prefs, durable jobs beyond pool kinds
- O53 [owner-call, Gr2, M]: GRAPH_PLAN F7: Q32 day strip is owner's; ?since= deferred; dot density at 5,000 not built
- X9 [blocked-hardware, Cp2, L]: w15-1110.md: B62, B64, B65 L9 art, B66 scan cause, B67 timer need owner's Windows desktop and next log
- X19 [owner-call, Ui1, S]: W33 E12 'Read as' lines wait on owner (49 assertions); E14 manual WebP empty unless owner wants it

## Fixed and stale

| id | status | evidence |
| --- | --- | --- |
| I1 | fixed | CHANGELOG:323-325 category target; HISTORY 1744 |
| I3 | fixed | CHANGELOG:486,296,230; ai/composer_story.py; HISTORY comp1743-1111 |
| I6 | fixed | search_manager.py:1380 meaning_floor, applied :1572 |
| I9 | fixed | CHANGELOG:340, HISTORY 1739; tests/test_date_answers_1739.py |
| I10 | fixed | CHANGELOG:340 written/about wording; test_date_answers_1739.py |
| I13 | fixed | CHANGELOG:475 diagram door light; test_diagram_door_light_1722.py |
| I14 | fixed | CHANGELOG:164 pixel-hue measured both themes; real-Windows eye check not done |
| I24 | fixed | CHANGELOG:787, 402 |
| I26 | fixed | CHANGELOG:818-819, 51; spasm not reproduced |
| O1 | fixed | OPEN:63 A16 409 'Unlock first.'; tests/test_vault_attachments.py |
| O8 | fixed | OPEN:124 B27 w9b-1110; true likeness ranking not built |
| O9 | fixed | OPEN:126 B29 re-checked 2026-11-11 |
| O10 | stale | B33 not reproduced (compleft-1110.md:17); wbSnap NaN guard fixed |
| O12 | fixed | CHANGELOG:618; journal ask not individually confirmed |
| O15 | stale | OPEN:172 B63 closed w15-1111; later flap is B66 (I23) |
| O18 | fixed | OPEN:185 B73 94cff43; tests/test_ollama_probe_30s.py |
| O22 | fixed | OPEN:213-216 C19-C22 |
| O29 | stale | OPEN:256 D8 measured f6-1111, idle pre-parse cut open to 415-510 ms |
| O31 | stale | OPEN:268 D16 measured f6-1111, not worth cascade risk |
| O36 | stale | s58left4-1110 closed D19 as no cheap app-side cut |
| P2 | fixed | startSearxng helper; CHANGELOG:1327,1642; test_searxng_down_1490.py |
| P13 | fixed | import bin clock, 31st repeat, reminder token key, Undo the run clears stack |
| P14 | fixed | CHANGELOG:293 ai/typo_context.py |
| P18 | fixed | 2b58fa5e3; only a physical click not verified |
| P23 | fixed | chat_agent.py:181 _typed_tool_events; CHANGELOG:365 |
| P24 | fixed | compleft-1110.md:12; CHANGELOG:365 |
| P28 | fixed | composer_lines.py:497 etc. say Atlas's assistant (CHAT_PLAN decision 76); ledger text stale |
| X3 | fixed | w8-1110.md, w8b-1111.md; test_composer_w8_1110.py |
| X11 | fixed | s5-1110.md, settings-1111.md C17-C22 |
| E21 | fixed | tests/test_composer_bc6_1111.py |
| E24 | stale | ledger stale 2026-11-11; not reproduced |
| D1 | fixed | HISTORY 1743 3cafbbd30 |
| D19 (r2:59) | fixed | test_composer_chips_1110.py:134,148,108; exact chips not re-probed |
| D22 (r2:61) | stale | ledger stale 2026-11-11; head probes answer |
| R3-8 | fixed | test_composer_bc6_1111.py; head probe |
| R3-25 | fixed | HISTORY 1743 3cafbbd30 |
| R3-29 | stale | ledger stale; head probe no 'None of these' tail |
| R3-36 | fixed | same fix as D19; exact chips not re-probed |
| D13 | stale | ledger stale; no bolted filler |
| D16 | stale | ledger stale; not reproduced |
| D17 | stale | ledger stale; CHANGELOG W8B 1111 |
| D18 | stale | ledger stale; composer_ask.CONTACT_VERBS |
| D19 | fixed | test_composer_chips_1110.py:134,148 |
| D22 | stale | ledger stale; head probes answer |
| D24 | stale | ledger stale; shapes no longer differ |
| G12 | fixed | tests/test_patterns_g12_1110.py; routes_resurface.py _reason |
| FX1 | fixed | three named tests pass on head with test_composer_streak_1029.py |
