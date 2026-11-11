# OPEN: everything still open from the agent files, in one place

## Work order (2026-11-09)

One ranked, deduplicated order of everything open before the BACKLOG, to be followed across the next sessions. Built from the 2026-11-09 bookkeeping: [book1](book1-1109.md) (audits 1028 to 1031; "open" there means no fix record found, so those rows start with a verify step), [book2](book2-1109.md), [book3](book3-1109.md), [book4](book4-1109.md), [book5](book5-1109.md), [book6](book6-1109.md), [bt-compcomp](bt-compcomp-1109.md), [c13](c13-1109.md), [sec](sec-1109.md), [zoom4](zoom4-1109.md), [cispeed](cispeed-1109.md), [lag](lag-1109.md) and HANDOVER's 09d to 09f "Now" lines. The detail of every row stays in its source; a row here is one line with its refs.

How to read it:
- Tiers: A security and data loss; B daily bugs, broken core flows, lag, the companion in the way; C UX and accessibility on daily surfaces; D performance and CI time; E polish; F plan horizon. Within a tier, cheap and high-reach first.
- A batch is one surface and one file area for one agent (1 to 3 hours). Batches in the same session never share files. Rung: Haiku verify, Sonnet implement, Opus design or ambiguous.
- Ref keys: `1028-agent E1` and the like are book1 rows (audit file and id); `1107 D1`, `R3-8`, `E9` are the 1107 composer audits (book4 probe marks); `c13#7`, `bt#14` are c13 and bt-compcomp items; `t20#n` is book3's top-20 list; `INBOX n`; `<PLAN>#<section>` are book5 rows; `oa <id>` is owner-asks-audit-1108 (book2).
- "Verify first": a Haiku scout re-reads the code or drives the app and marks each row true, fixed (sha) or stale before the Sonnet builds; a fixed row is struck here at merge.
- Every batch: tests first, `bash scripts/gate.sh --staged`, the targeted tests named, `node --check` on JS, a five-line report, its rows struck here and the source file marked.

### Owner answers, 2026-11-11 (one sitting)

The recommendation was taken for Q1 to Q9, Q12, Q14, Q18 to Q24, Q26 and Q28. Q13 was not asked; its recommendation stands. Rows waiting "after Qn" can start. The answers that differ from the recommendation, quoted in INBOX 1748:
- ~~Q10~~ **Stale: built** (Appearance, Motion at rest, "Still when idle"; tests/test_companion_rest_w14.py). Atlas's rAF loops keep running by default ("I still want it to feel biological and have life"). An Advanced setting stops them after 2 s with no input. | W14
- ~~Q11 The Ollama probe is cached for 30 s, dropped on a failure, and also dropped the moment Ollama is seen coming online (the model status poll or the start event), so the composer never answers in that window. | W16~~ **W34: fixed 94cff43** (w34-fix1-1111.md)
- ~~Q25~~ **Built settings-1111** (Settings, General, Search; date order; welcome preferences card). `before:` is a Settings choice, excluding by default. The owner also wants a first-run calibration of preferences like this (INBOX 1748). | W11
- ~~Q27~~ **Built pr216-settings** (mounts in pkg-1111.md). Q27 RapidOCR is bundled if small, otherwise an optional extra. Every feature that needs an optional package (RapidOCR, SearXNG, the PDF viewer and the rest) shows a dismissable notice with a one-click Install when it is used. The notice comes back if the package is uninstalled, on the no-model notice recipe (INBOX 1748). | F5
- ~~Q30~~ **Stale: built** (tests/test_private_by_default_1695.py). Private notes by default is a Settings switch, off by default, and follows the space: a note made in a private space is private. | F6
- Q31 and Q32: the owner says these are already done; they are closed here.
- Q33 is parked: the owner will check whether the stutter returns. W34: owner-call (parked), w34-L1-1111.md.
- Q34 Go on all of them: sync (B6) (**sync: built 2026-11-11, WORLD_CLASS_PLAN B6 decisions 1 to 14, over the home network and through a folder**), ~~offline studio and audio~~ (built 2026-11-11, HISTORY "Moved from the plans, 2026-11-11 (Q34, WORLD_CLASS rows 35 to 37)"), the desktop pet outside the window, the custom domain (**built 2026-11-11, Settings, Address names; see HISTORY**) and the blind panel. Fable stays off. | F8 W34: owner-call, w34-L1-1111.md. Desktop pet: decided (UI_MODERNISATION_PLAN, Q34 decisions): it is the built desktop companion; card-window menu fit fixed, q34pet-1111.md.
- ~~D30 spell-check language packs (owner decision 2026-11-11: optional downloads, never vendored)~~ **Built d30-1111 (2026-11-11):** French, German and Spanish spelling are optional downloads (Settings, Packages: `spell-fr`, `spell-de`, `spell-es`; sha256-pinned Hunspell files from the `dictionary-*` npm tarballs, kept in the data folder, never vendored, egress labelled), built lazily in the Harper worker when a document's `lang:` matches; the panel note offers the install through `extraNoticeMount`. English unchanged. Grammar stays English; autocorrect lists per language are not built. Evidence: `tests/test_spell_packs_1111.py` (22, fake transport); real pinned French tarball through a local mirror in the app: note and Install notice before, French misspellings flagged after, no console errors; worker build fr 4.4 s, de 0.9 s, es 1.0 s; 44 words in 35 to 40 ms; 0% of dictionary stems missed. Not driven in a browser: de and es, dark or narrow layouts, the Packages card visually. d30-1111.md.
- ~~sm-1111 row 22: on lock, typed fields move into the encrypted draft store and are cleared, then restored on unlock. Add an easy way to pick them back up, a "where you left off" or recent drafts list. | sm row 22~~ **W34: fixed** (w34-L1-1111.md)
- Q15 to Q17 stay parked (P1 to P3) until the owner sends examples. W34: owner-call (parked), w34-L1-1111.md.

Not a question: the CI test timeout is not raised (HANDOVER 09d, "never raise the cap"); the jobs get faster instead (W24).

Parked until the owner's data or a check on real hardware:
- P1 Chat Sources rows extend to the right | INBOX 1712, uifix L3 W34: owner-call (parked), w34-L1-1111.md.
- P2 Companion carried over the top bar by Ask scroll | INBOX 1598, oa 1598 W34: owner-call (parked), w34-L1-1111.md.
- P3 Composer "response issues" round | INBOX 1719 (c) W34: owner-call (parked), w34-L1-1111.md.
- P4 Win+arrow snap resets the window; tray icon after X; companion over Wallpaper Engine | INBOX 1671, oa 1620 tray W34: owner-call (parked), w34-L1-1111.md.
- P5 The 15 s /chat/followups log; graph `gcRequestDraw` 55 calls a second | oa 1691 b, lag L12 W34: owner-call (parked), w34-L1-1111.md.
- P6 Desk overlay O5 on Windows; every desk motion unverified on real Windows | INBOX 1645, 1683, travel L6 W34: owner-call (parked), w34-L1-1111.md.

### Tier A: security and data loss

**W0 Diagram builder opens and closes in 10 to 15 s** (B, diagram, in progress: agent `dglag-1109`). Item 0, the owner hit it 2026-11-09; merge and gate it first in Session 1.

**W1 Chat turns that corrupt the chat or keep running** (A, chat, Opus; verify first). Files: `frontend/js/chat*.js`, `chat-turn.js`, `api/routes_chat.py`, `api/routes_ask_history.py`. Checks: `tests/test_chat_*`, a Playwright regenerate and stop run. Done when: regenerate and edit never repeat an act or a write, Stop ends the server stream, every stopped answer ends with a done line.
- ~~A1 Regenerate from a non-last answer corrupts the saved chat | 1028-agent E1~~ **Stale: fixed 9dbf3f956**, re-driven by w1-1110 (saved turns after regenerating turn 1 of 3: the one regenerated turn)
- ~~A2 Regenerate and Edit-and-resend re-run composer acts and agent writes (two notes) | 1028-agent E2~~ **Fixed 936dacce6** (the confirm survives a reload; live confirm 9dbf3f956; composer acts deduped server-side)
- ~~A3 Browser Stop does not stop generation server-side; a stopped answer has no done line | 1028-agent E3, t20#9~~ **Fixed 936dacce6** (done line on an Activity Stop, ddfece902; "Stopped" on every stopped answer; browser Stop already cut the model, 90523c72c)
- ~~A4 A pasted lecture over 20,000 characters returns 422 with the wrong message | 1028-agent E8~~ **Fixed 2cd0513f7** (edit path; the send guard was 26b52c850)
- ~~A5 An Ask stored turn recounts support with the model counter | chatfoot L6~~ **Fixed db9b00fdd**

**W2 Outside text reaching write tools; the speller rewriting the person's words** (A, agent and acts, Opus; verify first). Files: `ai/agent.py`, the taint and confirm path, the speller module. Checks: `tests/test_agent_*`, `tests/test_composer_grammar.py`. Done when: every write from a tainted turn confirms, and a word inside an act's payload is never respelled.
- ~~A6 Library files, imports and pasted mail reach the model untainted, so writes run unconfirmed | 1028-agent E4, E42~~ done w2-1110 (E4 doors already tainted; pasted mail now taints)
- ~~A7 The speller respells the person's words before acts ("uni", "oat milk" to "At milk") | 1028-agent E9, 1029-composer C40~~ done w2-1110 ("oat milk" already fixed; "uni" with a misspelt verb fixed)
- ~~A8 "delete all notes about gym" quietly becomes one note | 1028-agent E66~~ done w2-1110 (composer already listed all; Agent mode now one card for all)

**W3 Vault, lock and private notes** (A, shell and server, Sonnet; verify first). Files: `frontend/js/lock*.js`, `api/routes_graph.py`, tags and links routes, the search index. Checks: `tests/test_vault_*`, a locked-vault sweep. Done when: nothing of a private note (preview, tags, counts, link chip) leaves while locked, and the lock dialog takes focus.
- ~~A9 The graph carries decrypted previews of private notes | 1029-harness H15~~ stale: locked graph shows "Private note", open shows the person's own text by design (tests/test_vault_read_surfaces.py)
- ~~A10 While locked, a private note's tags, word count and presence show in the list, graph and /tags | 1029-notes N21~~ stale: locked list, graph and /tags drop tags, count and text (tests/test_vault_read_surfaces.py)
- ~~A11 Links to a private note are accepted by API while locked; the [[ picker and link mode disagree | 1031-notes N23, N40~~ fixed w3-1110: 409 "Unlock first." for either end while locked, link mode refuses a private note like the picker (tests/test_vault_w3_1110.py)
- ~~A12 Export while locked answers 200 with the placeholder as content | 1029-notes N12~~ stale: export and history answer 409 while locked (tests/test_vault_read_surfaces.py)
- ~~A13 With the vault open, a private note is never searchable | 1031-notes N3~~ stale: /search and /entries/query never return a private note, open or locked (tests/test_vault_w3_1110.py)
- ~~A14 Lock screen: focus not on the field, no dialog semantics, no throttle hint, focus dropped after errors | 1028-shell S4, S25, 1029-extras X23~~ stale: Playwright 2026-11-10 shows focus on #lock-password, role dialog, aria-modal, aria-describedby, aria-invalid, focus kept after 5 wrong tries, 429 countdown on the button
- ~~A15 Sign-in off never driven (persistent profile, second LAN device, restored preferences) | t20#17~~ driven w3-1110: persistent, relaunched and fresh browsers open with no prompt, vault stays locked; second LAN device and a real restore not driven (no second host); backups exclude the switch
- ~~A16 `/media` 403 and 409 unified (after Q18)~~ (built sm-1111: 409 "Unlock first.", tests/test_vault_attachments.py) | sec L14

**W4 Documents that lose words** (A, documents, Sonnet; verify first). Files: `frontend/js/documents.js` save and lock paths. Checks: `tests/test_doc*`, a slow-PUT Playwright run. Done when: no typing during a save is lost, an offline first save says "Not saved" and keeps a draft, locking clears every word from the page.
- ~~A17 Autosave has no in-flight guard; a slow PUT plus typing sends a stale hash~~ (stale: built, tests/test_doc_save_serial.py) | 1028-docs D1
- ~~A18 The save reply marks clean and forgets the local edit even when typing continued~~ (stale: built, tests/test_doc_save_serial.py) | 1028-docs D2
- ~~A19 A new document by typing has no catch: offline or 500 is silent~~ (built w4-1110, tests/test_doc_new_draft_1110.py) | 1028-docs D3, D36
- ~~A20 Failed-save retry and a crash draft~~ (built: retry toast and pagehide draft existed, new-document draft w4-1110) | DOCUMENTS#24 row 6
- ~~A21 Locking leaves the document's words on the page; the AI panel sits over the lock~~ (stale: built, tests/test_lock_document_panels_1031.py) | 1031-docs DC1, DC2

**W5 Server integrity** (A, backend, Sonnet; verify first). Files: `api/routes_entries.py`, `api/security.py`, `routes_auth.py`, board and backup routes, `core/db`. Checks: `tests/test_routes_*`, `tests/test_auth*`, a 24-parallel-POST test. Done when: a burst of creates all land, binned notes refuse writes, tokens and throttle are thread safe.
- ~~A22 24 parallel note creations: 5 answer 500 after 30 s (pool timeout) | 1031-backend BK1~~ fixed (core/concurrency.py, test_concurrency_sizing_1031)
- ~~A23 A note in the bin can be edited by PUT | 1031-backend BK2~~ fixed (test_bin_guard_1031)
- ~~A24 A binned note comes back in default search; opening it says "No such note." | 1029-notes N3~~ stale: search excludes the bin (probe w5-1110)
- ~~A25 Session token store has no lock; the login throttle is check-then-act | 1028-backend K2, K3, K23, 1031-backend BK7~~ fixed (test_token_tables_1031)
- ~~A26 Board x and y are unbounded; one far object breaks the board | 1031-board BD1~~ fixed (test_board_coordinates_1031)
- ~~A27 Backups DELETE with a traversal and inconsistent id shapes | 1031-backend BK9~~ fixed (test_drifted_copies_1031)
- ~~A28 `safeHref` lets `java\tscript:` through | 1028-docs D14~~ fixed (notes-list.js:858, test_link_schemes_controls)
- ~~A29 No pre-Brief-7 database was ever upgraded for real | t20#18~~ done w5-1110: tests/test_upgrade_pre_brief7_db.py upgrades a real pre-Brief-7 dump; no bug found
- ~~A30 Deleting a space still purges in one path | 1029-extras X5, 1031-extras Z20~~ fixed (purge needs ?purge=1, name typed; test_space_delete_confirm_1031)
~~- A31 Key storage and MCP auth (after Q22) | a30i-1102 B40, B33, B24, D46, K26, K11, K13, E43~~ done backend-1111 b155304 (K11), 6ff76a7 (K13), 0389648 (E43); K26 closed by design; B40/B33/B24/D46 belong to other batches (W19, composer)

**W6 Recordings and swallowed deletes** (A, voice notes, Sonnet; verify first). Files: `frontend/js/meetings.js`, `media.js`, the board delete handlers. Checks: `tests/test_meeting*`, a Playwright record and reload run. Done when: no audio is dropped on pause, close warns while recording, typing a title never starts the mic.
- ~~A32 The voice dialog opens on Record: a typed space starts the mic, other keys fire shortcuts | 1029-extras X1~~ [struck 2026-11-10 w6-1110: verified fixed on head, tests in test_recording_is_unsaved_work_1029.py, test_xfix_1031.py, test_wb_board_1028.py]
- ~~A33 Closing or reloading during a recording gives no warning | 1029-extras X2~~ [struck 2026-11-10 w6-1110: verified fixed on head, tests in test_recording_is_unsaved_work_1029.py, test_xfix_1031.py, test_wb_board_1028.py]
- ~~A34 Up to 10 s of audio lost on pause (no requestData) | 1029-extras X3~~ [struck 2026-11-10 w6-1110: verified fixed on head, tests in test_recording_is_unsaved_work_1029.py, test_xfix_1031.py, test_wb_board_1028.py]
- ~~A35 A failed Discard is swallowed and the dialog closes | 1031-extras Z12~~ [struck 2026-11-10 w6-1110: verified fixed on head, tests in test_recording_is_unsaved_work_1029.py, test_xfix_1031.py, test_wb_board_1028.py]
- ~~A36 Board delete failures swallowed; undo pushed before the DELETE | 1028-board B8, B40~~ [struck 2026-11-10 w6-1110: verified fixed on head, tests in test_recording_is_unsaved_work_1029.py, test_xfix_1031.py, test_wb_board_1028.py]

### Tier B: daily bugs, core flows, lag, the companion in the way

**W7 Composer: which note leads and what it is called** (B, composer, Sonnet high). Files: `ai/composer_body.py`, `composer_names.py`, `composer_frame.py`, `composer_likeness.py`. Checks: `tests/test_composer*` on the r5 and r9 seeds (`tests/_r5_1108.py`, `tests/_seed_r9_1109.py`), the book4 probe. Done when: each row's probe answers right and its sibling phrasings pass (fix the class, INBOX 1357).
~~- B1 The defining note does not lead ("tl;dr Lisbon", "summarise Lisbon", pronoun body) | 1107 D1, R3-20, 1029-composer C19, 1031-composer C1, C4~~ **Fixed w7-1110** (`note_rank.lead_by`: among alike-titled notes the fuller one leads unless the ask is for the latest; r5 "tl;dr Lisbon" and "summarise Lisbon" lead Lisbon trip; the pronoun-body case "who is Tom" already named the Tom note).
~~- B2 Number and property questions answered without the number (squat 80 kg, passport) | 1107 D7, R3-2, R3-28, E12, 1029-composer C21, 1031-composer C16~~ **Fixed w7-1110** (squat 80 kg answered in the 1031c and 1030 seeds; "passport number" and visa, student, employee, customer, parcel numbers are numbered things: "None of your notes give a passport number." when no note holds one, and a bare "passport number" is no longer "Not sure what you mean").
~~- B3 Title-less notes get many names; "who is Marcus" omits the bare Marcus Lee note | 1107 D11, R3-15, 1029-composer C8, c13#10~~ **Fixed w8-1110** (owner 2026-11-10: a title-less note is named by its first line, about six words, quoted, with an ellipsis, in lists, compare, prose and the Open chip: `composer_answer._Answer.name` and `cite`, `composer_frame.name_of` and `link_text`; the compare cites "[“Marcus Lee, chair of the garden…”]", "who is Marcus" counts the bare note, a lower-case one-line note is quoted (“hi”); a when-ask still carries the day in the cite; tests moved with the decision: test_composer_741, test_composer_voice, body_paths.json, `_voice_eval`, `_composer_eval`).
~~- B4 A pronoun-led line quoted without the person ("He fixes the boiler") | 1107 D12, R3-25~~ **Stale: fixed earlier**, now pinned (r5 "what do I know about the boiler" says José García fixes the boiler; who fixes, what does José fix likewise).
~~- B5 A lower-case pair ("anna and josé", "tom and sara") pooled as one subject | E10, composer-r6 L23, composer-r8 L13~~ **Fixed w7-1110** (accented names were cut at the accent in `_note_words`; a guest list "Anna, Tom and Sara" was read as a phrase; the pair is looked up per word in `chat_pool._lower_pair`; names shown as the notes write them).
~~- B6 Likeness: "cat" matches fish, "boiler" the radiator note | R9-11, c12 L6~~ **Fixed w7-1110** (`_scored_members`: with notes that write the word itself, a note that only shares a synonym group is not a member; with none, the synonym still answers).
~~- B7 (part: reading list fixed w7-1110; "latest on sourdough" open, see w7-1110.md) "latest on sourdough" leads the wrong note; "what do I need to read" names by date and says "Three three" | R9-3, R3-22, book4 new~~ **Built 2026-11-11, 50b8cf54e (merged 02d3efa49; w7b-1111.md, tests/test_composer_w7b_1111.py):** "latest on sourdough" names the subject from the notes (`composer_aliases`, "Doug"), "what do I want / plan to read" opens the to-read list.
~~- B8 "compare Priya and Marcus" says nothing mentions Marcus (`_sides_own`) | c13#2~~ **Stale: not reproducible** on the bt seed (compare, vs, differ all give both sides); pinned by `test_a_note_naming_both_sides_does_not_hide_a_side`.
~~- B9 One-note notebook and `as_of` (time travel) answers | R3-31, R3-32~~ **Fixed w7-1110** (no "search by meaning" footer in a one-note notebook; `as_of` answers "what is in my notebook" as that day's count and span, `notebook_stats.answer_chat(..., as_of)`).
~~- B10 A name matches inside another word; a plural subject is required verbatim | 1029-composer C16, 1031-composer C8~~ **Stale for names and plurals**: "show me notes about Tom" no longer lists tomato notes and "meetings" finds Meeting notes (1030 seed); left open: "books" still adds "book the tram" as loosely related (verb for noun), see w7-1110.md. **Verb use built 2026-11-11 (50b8cf54e (merged 02d3efa49; w7b-1111.md, tests/test_composer_w7b_1111.py)):** "books" no longer lists "book the tram".

**W8 Composer: dates, events and footers** (B, composer, Sonnet high). Files: `ai/composer_ahead.py`, `factgraph.py`, `composer_unfound.py`, `recognise.py`, `api/chat_web.py`. Checks: as W7, fixed clock. Done when: as W7.
~~- B11 "written today" and "as your X note has it" bolted on every answer | 1107 D13, R3-34~~ **Fixed w8-1110** (a fact that carries its own date drops the write day: `composer_digest._when_tail` for a when-ask, `_from_name`; "how long ago did I write the Sara note" has its own shape in `composer._written_when`).
~~- B12 Footers name question words the answer did not need ("new", "valid", "schedule", "coffee") | 1107 D16, R3-29, 1030-composer Z16, bt#11, bt#16~~ **Fixed w8-1110** (`composer_unfound._FRAME_WORDS` += new, brief, valid, name, schedule, appointment; the "coffee" case is stale: not reproducible on the r5 seed).
~~- B13 "Sources: 10 notes" under an unfound answer | c13#12~~ **Fixed w8-1110** (a second `meta` with no rows after an unfound answer: `chat_web.nothing_found_meta`, inserted in `routes_chat._composed_events`).
~~- B14 Recurring schedules not placed on their days; "anything on Wednesday" lists notes | 1107 D17, D24, R3-8~~ **Fixed w8-1110** (`composer_plan`: a habit ("Gym on Monday, Wednesday and Friday at 7am") is placed on its days, "anything on Wednesday" is the dated list, a habit is not a deadline in a week list, a day with nothing says the next one without a stray stop or a doubled date).
~~- B15 Event questions answered from the creation log ("what happened on 25 October") | 1107 D18, E16~~ **Fixed w8-1110** (`activity._named_on`: "what happened on 25 October" leads with the notes' own sentences that hold the date, then the creation log).
~~- B16 "Heads up: I could not find 4" (a date read as a figure) | book4 new (D14 grounding)~~ **Fixed w8-1110** (`source_check.sources_from_messages` backs today's date from the prompt's own clock line, so "today, 4 November" is not "could not find 4"; unit-tested, not driven with a real model).
~~- B17 "last week" and "in October" lists: capitals and doubled heads (after Q24) | E18~~ **Fixed w8-1110** (Q24: `recognise.days_since("last week")` is Monday of the week before, "past week" rolls; `activity._head` has no span when the window names its month: one head, a capital).
~~- B18 Chat and Ask carry no locale, so "3/4" reads day first | t20#8~~ **Fixed w8-1110** (`recognise.spell_numeric_days` orders a bare day and month once in `routes_chat._asked`, by `body.locale`, for questions only; `_numeric_dates` follows the reported locale when a reader has none).
~~- B19 Holiday or month word read as a date window; past dates read as next; "next two weeks", "overdue" | 1031-composer C3, C9, 1029-composer C24, C25, C26~~ **Fixed w8-1110, in part** (month names are no longer one synonym group, so "December" is not "Rent"; "before Christmas" ends the day before; "next two weeks" and "overdue" read right; holiday-as-topic is stale. Open: "last Christmas" carries no year, see w8-1110.md).
~~- B20 Verdict date written long (after Q8) | c13 owner question~~ **Fixed w8-1110** (Q8: `composer_ahead.long_form`; the verdict writes "No, not tomorrow. Thursday 12 November, 9:30" and keeps "at 8am" where the note said it).

**W9 Composer: follow-ons, chips and acts** (B, composer, Sonnet high). Files: `ai/composer_follow.py`, `composer_dialogue.py`, `commands.py`, the chips builder. Checks: as W7. Done when: as W7.
- B21 (built 2026-11-11: Ask and Chat both send `objects` now; "tell me more about it" is scoped to the cited note (`chat_request._bind_cited`), "and the other one?" asks about the other cited note (`composer_talk.cited_question`), pinned by tests/test_composer_w9b_1111.py; "who wrote it" answers honestly that the note does not say; "and the dentist" / "what about him" ask what is meant, kept) A follow-on loses its subject ("and the other one?", "who wrote it", "and the dentist"; Ask sends no objects) | R9-9, c13#7, E25, 1107 D6, 1031-composer C12, 1029-composer C44 W34: skipped (composer spoke), w34-fix1-1111.md.
~~- B22 Chips built from leftover words ("about the sara?", "about project?") | 1107 D19, R3-36, 1031-composer C47, bt#17, c13#15-18~~ **Fixed w9b-1110, in part** ("the Sara" is "Sara": `composer_chip_subject._owned`; the audit's other chips were re-driven on the 1031 seed and no longer appear; tag chips such as "about project" are the person's own tags, left).
~~- B23 Offers nothing answers ("yes" after an offer) | 1107 D10~~ **Fixed w9b-1110, for reminders; composer batch 2 (2026-11-11) for the checklist, pick and new-list offers** (`composer_talk._note_offer_sentence`: a bare "yes" after "Save it as a checklist note?" is a checklist note of the lines above it, after "Note the X as your pick?" the pick note, after "Start a list of films to watch next?" an empty list; the yes is the consent, run with Undo in Chat, Ask says it is for Chat as for a reminder; `tests/test_composer_batch2_1111.py`). Gather and Track-in-a-table: **fixed, composer batch 3 (2026-11-11)**: the server parks the offer's note under an `offer_id` (`consent.attach`, `consent_store`), the page sends the id back on the last turn until the button is pressed (`chatHeldOffer`), and a bare yes in Chat makes that note with Undo, once (`composer_talk.held_offer`; `tests/test_composer_offer_ids_1111.py`).
~~- B24 Four confirm wordings; typed "undo" alone gives the keys | 1107 D23, E7~~ **Fixed w9b-1110** (every `CONFIRM` wording names Confirm and Cancel, eight openers kept for test_reply_variety; a tag or move names the note by title; "undo" after a pin or unpin takes it back; "undo" with no act before it still gives the keys, by design).
~~- B25 "call anna" in lower case; "make a checklist for my trip" | composer-r8 L12, L14~~ **Fixed w9b-1110** (`commands._bare_call`: lower-case names for call/ring/phone, "the dentist", "my boss"; `task_acts._subject_checklist`: "Trip checklist" with one empty line).
- ~~B26 Remind wording, "called X with Y", one list-add rule (after Q4, Q5, Q6) | c12 L13, L14, L15~~ **Built (all three):** Q4 w9b-1110; Q5 and Q6 17d5d14 (`commands._PLAIN_NAME` keeps "called Christmas with mum, dad and Sara" whole; every list add asks, a missing list is offered as a note; tests/test_composer_lists_1111.py, test_new_note_called_1102 moved with its stated intent). Re-run 1111: 119 targeted tests pass.
~~- B27 Agent mode with no model answers the whole sentence ("find notes simlar to my dentist one yk") | t20#14~~ **Fixed w9b-1110** (`find_topic.topic` in `commands._found_object`: the likeness words, "one" and the filler come off; searches "dentist").
~~- B28 "show the note about golf" answers the tag chart | 1031-notes N32~~ **Stale** (conv-1110, route probe, model off: "show the note about golf" lists the two golf notes with links, no chart)
- ~~B29 No tasks: "add a task to read chapter 5 tomorrow" and the "tick off" forms | 1028-agent E10 (conv-1110: the add form now answers "Got it, I will add a task due tomorrow at 9am (the default): read chapter 5"; the tick-off forms re-checked 2026-11-11: tick off, mark as done, complete, cross off, check off each give a confirm card, pinned by tests/test_composer_w9b_1111.py; the loose "I finished X" without a kind word stays a question by the audit 1030 A15 guard)~~ **W34: fixed** (w34-L1-1111.md)

**W10 Composer: compare, summary and lists** (B, composer, Sonnet high; not beside W7). Files: `ai/composer_digest.py`, `composer_lists.py`, `composer_each.py`. Checks: as W7. Done when: as W7.
~~- B30 Compare and summary shapes ("one mentions X and one mentions Y"; recipe summary is the ingredients only; summary drops "Work starts 16 November") | 1107 D20, E9, bt#14, R9-17~~ **Fixed s5-1110 (`study._worth`: a dated sentence outranks a phone number, a recipe keeps its method, a name said again with a label leads nothing; the composer's own "one mentions X and one mentions Y" lead said back is a comparison; "boil down" and "condense" summarise).**
~~- B31 Dead ends where the notebook can answer (checklists, favourites, tables, done items) | 1107 D22, E19, E21~~ **Fixed s5-1110, in part ("show my done items" is the ticked list; "my favourites" is the pinned list; "which notes are linked" counts [[links]]; checklists, tables and ticked items were built before; a note with no word for it still says so).**
~~- B32 List rows end "· Uncategorised" in the answer text | E24~~ **Fixed s5-1110 (`tool_say._note_row` drops the default filing).**
~~- B33 A proper noun lowercased in a quoted line ("orchard"); first-letter capitals lost | c13#13, 1029-composer C1~~ **Built 2026-11-11, 50b8cf54e (merged 02d3efa49; w7b-1111.md, tests/test_composer_w7b_1111.py):** a proper noun keeps its capital in a quoted line.
~~- B34 The joke note leads by its quote, not its name | composer-r7 L7, composer-r8 L16~~ **Built 2026-11-11, 50b8cf54e (merged 02d3efa49; w7b-1111.md, tests/test_composer_w7b_1111.py):** a question-then-answer joke note is one piece and leads by its joke.
~~- B35 Key-value notes ("Rent 650.") dropped as fragments | 1028-agent E5~~ **Fixed before s5-1110 (`composer_read._short_fact`, CHANGELOG 1501; verified).**
~~- B36 One-liner naming (after Q3) | c12 L16~~ **Fixed s5-1110 (Q3: `composer_frame._order_title` names a short capitalised order plain).**

**W11 Notes core** (B, notes, Sonnet; verify first). Files: `frontend/js/notes-list.js`, `navigation.js`, `search/query.py`, the export route. Checks: `tests/test_notes_*`, `tests/test_search_*`. Done when: jump-to-note opens any note, flag filters answer right, export works for any title.
- ~~B37 Jump-to-note does nothing past the first 60 rendered rows | 1028-shell S1~~ **Stale** (w11-1110, Chromium, 174 notes: `flashEntry(oldest)` lands the row at top 326 of 900, the middle one at 436; capture-ask.js resolves the page first)
- ~~B38 `is:pinned` and every flag filter answer wrongly; unknown values match nothing silently | 1029-notes N2, N16~~ **Stale** (w11-1110, fresh data dir: `/search?q=is:pinned` and `is:favourite` find the one pinned note among newer ones; `is:private` answers "No filter called is:private. Try is:pinned..."; tests/test_search_operators_1029.py)
- ~~B39 A short title "mentions" most of the notebook | 1029-notes N1~~ **Stale** (w11-1110: a note "t" has 0 incoming connections and 0 reference count with notes saying "t"; entry/mentions.py floor of 3 characters, whole words)
- ~~B40 Download .md is a 500 for a non-Latin title | 1031-notes N31~~ **Stale** (w11-1110: `/entries/{id}/export.md` is 200 for Japanese, Cyrillic, Arabic, emoji and 300-character titles; `attachment_headers` adds `filename*=UTF-8''`)
- ~~B41 The server accepts whitespace-only notes | 1029-notes N6~~ **Stale** (w11-1110: `POST /entries` with "   " and a blank line is 422 "That note is blank"; `EntryCreate` validator `not_blank`)
- ~~B42 `before:` excludes its day (after Q25) | OPEN 456~~ **Built w11-1110** (`before:` was already exclusive for ISO dates; Q25 made `before:tuesday`, `yesterday`, `march` and `"last week"` read through `recognise.span`; `tests/test_search_engine.py::test_a_named_day_is_a_date_for_the_operators`)

**W12 Navigation and overlays** (B, shell, Sonnet). **Done wb-1111** (Back closes the history, connections, bin, skill-run, board-help, meeting, extract, OCR and document-AI overlays; see wb-1111.md). Files: `frontend/js/navigation.js`, `settings.js`, notices. Checks: `tests/test_navigation*`, a Playwright Back and Forward run. Done when: Back closes an open overlay first and the hash matches what shows.
- ~~B43 Browser Back with an overlay open steps the tab history and leaves it open | t20#2~~ **Stale for the overlays** (w12-1110, Chromium: shortcuts, palette, finder, features, agent palette, notifications, dialog, lightbox, sketch all close on Back with the stack unchanged); the real gap was the manual and Statistics address, fixed
- ~~B44 Escape on Settings rewrites the hash to the tab beneath | t20#3~~ **Stale** (w12-1110: Escape on Settings from #/library gives #/library idx 2, Forward gives #/settings/models, Back #/library)
- ~~B45 A notice's `go: {settings, focus}` does not scroll the phone Settings sheet | t20#7~~ **Stale** (w12-1110, 390x700: 4 of 4 targets inside the sheet scroller, also with Settings already open)
- ~~B46 The navigation and undo audit table, then its fixes | WORLD_CLASS#8 row 32~~ **Built w12-1110**: audit table in WORLD_CLASS_PLAN row 32; fix: overlay addresses; left rows are listed under the table

**W13 Page lag outside the companion** (B, settings, dashboard, library, Sonnet high; trace first). Files: `settings*.js`, `dashboard.js`, `library*.js`, `api/routes_models.py`. Checks: the lag-1109 probes (`lagprobe.js`, `lagset.js`, `lagboot.js`) at 4x, before and after numbers. Done when: each named handler is under 50 ms at 4x or traced to the browser. *Traced (claude/pr216-graph): over-50 ms handlers at 4x are native style and layout; the one JS-attributed forced layout is the companion's nameMarkRasterise (avatars.js:1305, 86 ms), out of scope; Settings tools, Library and Dashboard script self time is 18 ms or less per function. Left to the browser.*
- ~~B47 Settings open: `/health` continuation 204 ms forced layout; backdrop click 880 ms~~ **Part fixed 774640ed9, rest browser** (w13-1110, 4x): the Settings head redraw 61 to 18 ms on the first open and 0 after; the open's `focus` (80 ms) and the backdrop close's `getClientRects` (60 to 70 ms) are the modal's own show and hide (a bare classList toggle and one read cost 105 ms in a page script; CPU profile JS self time under 10 ms); the `/health` continuation 11 to 34 ms | lag L7, L8, oa 1620 lag
- ~~B48 Dashboard card pointerout 312 to 1072 ms; boot first-reader rAF 55 to 121 ms~~ **Browser** (w13-1110, 4x): card hover or leave costs 0.3 to 3.4 ms of style and 0 layouts on a settled dashboard (dashboard.js has no pointerout handler); the long pointerout is an input waiting behind the page's own work; the boot `toEnd` is the heat cells' first layout (23 to 33 ms), a width-keyed skip made the first-visit scroll flaky, not kept | lag L6, L11, oa 1620 lag
- ~~B49 Windows lag log lines: icon-picker, settings-wiring keydown, OCR request, web-search start, quick panel flip~~ **Part fixed 774640ed9** (w13-1110, 4x): the document keydown read every modal's layout on each Ctrl chord (26 `getClientRects` to 0, the 179 ms line); icon picker first open: the script's onload is parse only (CPU profile 0 ms of JS), `focus` 53 to 80 ms is the first layout of 429 emoji tiles (`content-visibility` on the groups did not move it, reverted); web-search start is a request that waits for SearXNG, not a lag; OCR and the quick panel flip not re-driven (need a real PDF and a Windows desktop) | INBOX 1716
- ~~B50 Notes tab-switch pointerup 312 ms; dashboard 266 ms timer~~ **Browser** (w13-1110, 4x): Notes click 21 ms and Dashboard click 93 ms of script, of which `getBoundingClientRect` 27 to 35 ms is the first layout of the tab being shown (renderNotesRail, toEnd, settle); no handler over 50 ms of its own work | oa 1643 b
- ~~B51 `/models/status` 3220 ms; stop the 30 s model job~~ **Already fixed, not reproduced** (w13-1110): `/models/status` answers in 6 to 11 ms (12 polls) and 22 ms for 4 at once against a runner that holds every call 5 s; the 30 s `model-poll` is quiet and opens no run (`tests/test_f7_pool_moves.py`) | oa 1620 lag: models
- ~~B52 Library tab click, openDoc, panel-movable, objDragMove on a large notebook~~ **Open, needs a large notebook** (w13-1110, 4x, 44 notes, no library cards): Library click 35 to 40 ms of script, the draw is skipped when `/library` answers the same; `Response.json.then` 129 ms (first load) is spread over small functions (setLabel 27, libraryCard 17, none over 30 ms) | lag L10, oa 1667 f, i, m

**W14 The companion at rest and in the way** (B, in-app companion, Sonnet high; after Q10). Files: `frontend/js/avatars.js`, `atlas*.js`, `lag-watch.js`. Checks: `tests/test_atlas_*`, `tests/test_overlay_idle*`, a 10 s at-rest layout count. Done when: the companion at rest makes under 1 layout a second and typing with it on matches typing with it off.
- ~~B53 At rest it restyles the page 20 to 27 times a second (a seventh of a core); 130 animations on Chat | audit-1108-perf P1, 1031-perf PF2, 1031-ai AI1~~ **Fixed** (w14-1110: layouts a second at rest, chat 43 to 0, graph 36 to 0.1; recalcs 45 to 7)
- ~~B54 Typing with Atlas on makes 3.4x the layouts; chat send keydown 712 ms in `nameMarkBuddyTempo` | audit-1108-perf P5, 1031-perf PF1, oa 1643 c~~ **Fixed at rest** (w14-1110: 37 characters, 41 to 43 layouts on, 43 hidden; was 210; companion active in the 2 s after a pointer move still watches and nods as before)
- ~~B55 An agent turn spends a second reading animations | 1031-harness HR1~~ **Fixed in part** (w14c-1110: the pacer's own reads in a turn were 5 in 8 s; the cost was the Atlas tail beat's 120 `playState` reads a second, 1120 to 256 in 8 s at 4x, 47 to 14 ms; the turn's drawn motion is unchanged)
- B56 (not reproduced 2026-11-10, w14c-1110: at 4x, 9 s after opening a 1200-character note no avatars.js timer over 8 ms and none at 4.5 s; keep-up reads 0 in the companion's code; the pacer 5 reads, 15 ms) The 4.5 s avatars.js timer after opening a note; keep-up reads | oa 1667 l, d, oa 1620 lag: Atlas, INBOX 1716
- ~~B57 The throw must not scroll the page; no layout reads in a throw frame | oa 1667/1634 a, 1667 b, 1634 c, d~~ **Fixed (walks)** (w14c-1110: 0 scroll events in 4 throws at 4x, before and after; the landing's surface walk ran 3 times in the flight, 1800 box reads, now 1 (600) in one idle frame after the plan; the walk at the small size is the one left)
- B58 (not reproduced 2026-11-10, w14-1110: after 1440 to 480 to 390 the figure is 10 px clear of Send at 480 and far from it at 390; the bubble not exercised) On a phone, after a resize, it covers Send; its bubble overflows at 480 and 390 | bt#25, zoom4 found-not-fixed
- ~~B59 The chat area spasms up and down with the companion on | oa 1693 b1, S18~~ **Fixed (class writes)** (w14-1110: 36 `ring-held` rewrites for 37 keys to 1, the clear button's `hidden` too; the chat area's pixel movement not separately measured)
- ~~B60 Reset appearance does not clear its motion and entrances prefs | fablecomp Reset appearance~~ **Fixed** (w14-1110: Reset appearance clears Companion movement, Motion at rest and Showy entrances)
- ~~B61 Stand-to-hang walks keep the walk class on the way out | appdrag L5~~ **Fixed** (w14c-1110, read as: the hang pose with the walk's legs; 2 stride loops and the walk class through the 1.6 s slide to 0; the walk to any other pose is unchanged)

**W15 The desk companion** (B, overlay, Sonnet; real Windows unverified). Files: `src/tessellate/core/overlay/*`, desk windows. Checks: `tests/test_overlay_*` (serially), the 1696 lists. Done when: each list row is built or has a reason.
- ~~B62 Cut off on the ride, sits 20 px above the taskbar, flicker, nebula flicker | oa 1670 a, f, l~~ **Fixed on the engine** (ed1f878e7, e40711a2b, 70ef502; re-measured 2026-11-10 on the simulation: foot gap 0 to 1 px masculine and -3 to 0 feminine, nebula wash worst frame step 4.2 and 7.5 percent, feet travel at rest 0.14 to 0.18 px a minute; tests/test_overlay_ride_1670.py, test_overlay_bob_1670.py, test_overlay_rest_1670.py pass). Not verified on real Windows: if the owner still sees a gap, log the taskbar rect and rcWork next to the feet line
- ~~B63 Companion does not show: root cause | oa 1638 b~~ **Closed w15-1111** (HISTORY 1633 and 1638: the overlay shows, the layered window is created and drawn=True on the owner's log; the later show/hide flap is B66's). Next log to look for: none for this row
- B64 The 1696 lists, the falling stutter (a) | INBOX 1696, atlasf1696-1108c, ui1696c-1108c **Engine side measured graph-1111** (seeded fall, both looks, Pillow installed in the venv: the engine's wake in a fall was 31.25 ms on `SetTimer`, now 16.67 ms on the pacing grid, 16 to 31 ticks; step per tick mean 18.4 to 9.9 px, max 34.1 to 19.0 px). The owner's 8 frames a second is not on the engine; a layered-window draw cost on real Windows is unverified, so (a) stays open until a Windows trace **Desk half w15-1111, 4bc274f96:** the picture build is not the cause (median 0.2 to 0.7 ms per fall frame). What did share a tick with a fall: the periodic reads (window list of about 590 windows, foreground/battery/downloads poll, typing and notification read). Seeded sweep (`tests/overlay_airborne_reads.py`, throw 1500 px/s, 3.2 s in the air, 2560x1504 at dpi 192, timers spread over 10 s): 3.0 reads per flight and 100% of flights met one; now 0.0 and 0%, the reads wait for the landing (at most 8 s) and come back on separate ticks. **Blocked on Windows:** the cost of one layered-window draw is unmeasured; the next owner log must show, or not show, "overlay: a slow tick, N ms in state fall (timed reads: ...)" lines during a fall: a line naming a read means that read still stops it, no line while it stutters means the draw or the compositor
- B65 The 1683 travel mix | INBOX 1683, travel L9, L10 **L10 done w15-1111, a5b795b81** (hop chain on a perch: about 6 hops over 816 px, peak lift 24.3 px of 152, body y constant, perch kept, lift eased to nothing; tests/test_overlay_perch_hops_1683.py). **L9 open:** new art for the travel acts is design work, not an engine fix (W34 marked the row stale, w34-unv1-1111.md; L9, new travel art, is design work and stays listed in compalive-1109.md.)
- ~~B66 Owner 2026-11-10, verbatim: "the desktop companion doesnt hang from the top of my screen for long before it falls down. it always falls down". Recommendation, taken: a hang from the screen top lasts its full rest (no fall roll while hanging), and ends only by a chosen drop or a drag | owner 2026-11-10~~ **Fixed** (w15-1110: a top hang holds its full rest, 60 to 300 s, then a swing onto a window or a calm drop to its feet; a drag or request ends it any time)
- B66 Desk window scan counts Explorer and Chrome as invisible; perch filter finds almost nothing | INBOX 1716, oa 1667 n **In part** (w15-1110: tests from the owner classes and rects pass, the classifier is right; the let-go log now says titled or not and the style for a hidden window; the Windows cause needs one more log, see w15-1110.md) **w15-1111, 5dceb54f8:** every flip of the app window's away state now logs its source and the seconds the last state held ("the app window is away (event minimized)", "is back (event restored), 3.5 s after the last change"). **Blocked on Windows:** the next log must show those lines (a flip back under 2 s is an event that fires twice, a steady 3 to 4 s is something raising and lowering the window) and the titled/WS_VISIBLE style detail for the hidden Explorer and Chrome windows; no debounce was added without that interval data
- ~~B67 Display-paced timer 16.7 ms plus or minus 3; runs properly on Linux | oa 1670 r, u~~ **Fixed** (e2c1c20d6: pacing.py grid, Windows waitable timer in host.py, `select` timeout in x11.py; re-measured on the simulation: tick interval 16.67 ms exactly for walk, float and throw, was 31.25 on SetTimer; step at walk speed 3.0 px, was 5.0). Real Windows and a real Linux display not run here

**W16 Real-model check** (B, chat with a model, Sonnet; needs `scratchpad/llama-dev.sh serve`). Files: tests first, then fixes where they fall. Checks: `pytest -m evals`. Done when: each row reports a measured number or a fixed failure.
- B68 Model-on parity: composer text as context, not the answer (decision 75) | 1107 D28, P1, fable-fix F6 W34: owner-call (tracked in the plans), w34-L1-1111.md.
- B69 Evals gate: 8 of 8 loose ends, 80 % of skills with no invalid call on a 3B | CHAT#5 Phase 4 W34: hardware-only (3B model), w34-unv1-1111.md. **Real model run 2026-11-11 (w34-unv1-1111.md): not measurable on this box.** Qwen2.5-3B Q4_K_M ran (llama-cpp-python 0.3.36 prebuilt wheel), but at load average 13 to 19 on 4 cores it decoded about 3 s a token, so one plain answer took 271 to 344 s; the 8 loose ends and the 80 % skills bar were not reached. No gate figure
- B70 SKILLS Phase D never ran on a model | t20#19 W34: hardware-only (3B model), w34-unv1-1111.md. **Real model run 2026-11-11: not run** (same box limit as B69). No figure
- B71 Entity extraction and topic sentence on a local model | GRAPH#KG1-KG9 W34: hardware-only (model), w34-unv1-1111.md. **Real model run 2026-11-11: not run** (same box limit as B69; no extraction was timed). No figure
- B72 BACKGROUND_MODE (think off) for utility jobs, measured | CHAT 1691, oa 1691 W34: hardware-only (needs a model with a think switch), w34-unv1-1111.md. **Real model run 2026-11-11: not run** (no Qwen3-class model fetched; the box is too slow to time think-off). No figure
- ~~B73 The probe cache (after Q11) | deskperf L4, audit-1108-perf P7~~ **Fixed 94cff43** (30 s up window, dropped on a failure and on seeing Ollama online; tests/test_ollama_probe_30s.py)
- B74 Tool contracts on Ollama, model bench gates | WORLD_CLASS#8 rows 5, 6, 19, 21 W34: hardware-only (Ollama), w34-unv1-1111.md. **Real model run 2026-11-11: not run** (Ollama is not installed here and was not fetched). No figure

### Tier C: UX and accessibility on daily surfaces

**W17 Diagram builder fixes** (C, diagram, Sonnet; after W0 merges). Files: `frontend/js/diagram-*.js`. Checks: `tests/test_diagram_*`, the dgbt Playwright sweeps at 1440, 667 and 390. Done when: each row fixed or measured not reproduced.
- ~~C1 Keys typed straight after Add reach the sheet (a stray block, a context menu) | dgbt L19~~ **Fixed w17-1110** (390 px, list folded: reproduced as a lost name and a stray block; letters, Enter and Escape now wait for the name box; the touch Enter-in-the-first-second case is in w17-1110.md)
- ~~C2 Label under the handles; List footer help one scroll down at 667; backward arrow from a mid drop | dgbt L20, L21, L22~~ **Fixed w17-1110** (handles: not reproduced, 0 px on touch, 7 px into a 152 px box at 1440 clear of the text; help line was hidden under the sticky foot, now whole at scroll end; the drop word says Connect back to)
- ~~C3 The folded shelf button covers a box at 1440; a part added while folded is named | dgmseq L15, dgpic L17~~ **Not reproduced w17-1110** (overlap 0 px2 on five diagrams, button bottom 222 over picture top 235; named in 318 to 571 ms on four kinds)
- C4 "Connect to…" is an icon with no words; the door dialog repeats the page | diagram-fable w3, w12 **Measured w17-1110, not changed:** the arrow-only row is by design where the name would be squeezed (390: words 85 px leave the name 49 px, 320: 5 px; 1440: list 224 px); a 667 px sideways phone has room (219 px name) but the breakpoint set (test_breakpoints) has no 480 step; the door dialog is not touched (design pass, w17-1110.md)
- ~~C5 Handles at rest at 3:1 on both themes; a connector selects on a click | diagram-fable m1, oa 1661 f~~ **Not reproduced w17-1110** (ring 5.9:1 light, 7.0:1 dark against the stage; a click 30 percent along an arrow picks it with two ends, Escape lets go; the exact midpoint opens the name box, noted in w17-1110.md)
- ~~C6 A press on empty canvas and Escape clear the selection; arrow-added nodes never overlap | oa 1661 h, g~~ **Not reproduced w17-1110** (empty press: 1 box and 4 handles to 0 at 1440 and 390; Escape clears at 390; 14 handle-added blocks, 0 overlapping pairs)
- ~~C7 Name Canvas and Blocks for what they are; kind picker as a labelled Kind menu | oa 1661 i, k, S11~~ **Already built, verified w17-1110** (the seg reads Picture, List, Source; the Kind button shows its sample and word, 140 px; the dialog's title row has the Kind label)
- ~~C8 Default fold (after Q14); both side panels fold to a rail | INBOX 1720, oa 1661 m, S14~~ **Fixed w17-1110** (a blank or starter diagram opens with the list a 32 px rail while no fold was ever chosen, nothing stored; an existing one opens at 224 px; both rails exist and are named)
- C9 Shelf is mouse only; the diagram tray "Open" row; Done silently creating a file; Tab stops | dgml L14, DOCUMENTS#22.4 R9a, R11 **Shelf: not reproduced w17-1110** (Right arrow roves six tiles and More, Enter adds); the tray row and Done not driven (code toasts the save), see w17-1110.md. **1111 docs spoke:** read diagram-embed.js `save()`: Done makes the file with a named toast ("Saved “title” to the Library."), an Undo step and, from a fence, a Link the fence button, so it is not silent; no tray "Open" row exists in diagram-*.js (grep); W17 closed

~~**W19 Whiteboard daily UX** (C, boards, Sonnet; verify first).~~ **Done wb-1111** (U1, U2, U5, U13 were built; U3 and B33 built here, B10 is the dialog's Print note). Files: `frontend/js/whiteboard*.js` outside the render path (W30). Checks: `tests/test_wb_*`, `contrast.js` on a board. Done when: ink reads on both themes and every insert works by keyboard.
~~- C10 Stored black ink does not remap on dark; white ink on a yellow sticky | 1028-ux U1, U2~~ **Fixed before s5-1110 (cc6892028: `wbDefaultInk`).**
~~- C11 Insert, Sticky note by keyboard adds nothing and drops focus | 1028-ux U3~~ **Fixed before s5-1110 (cc6892028).**
~~- C12 Ring and chevron buttons under 24 px at zoom; Delete 2 px from Undo | 1028-ux U5, U14~~ **Fixed before s5-1110 (cc6892028, CHANGELOG 755).**
~~- C13 Lock shown by hover only; the eraser skips strokes on touch; one key, three meanings | 1028-board B20, B21, B12~~ **Fixed before s5-1110 (CHANGELOG 1286, 746; pointer-path eraser).**
~~- C14 `contrast.js` never visits a board or a map | WHITEBOARD#Placed 2026-10-05~~ **Verified s5-1110: contrast.js opens a board and a map, all selected, and every sidebar tab; dark: 0 findings, 21 and 17 text elements.**
~~- C15 Connector label look controls (size, bold, colour, chip, position) | t20#12, INBOX 819~~ **Fixed s5-1110 (Format, Line: Label size, colour, bold and chip; `label_size`, `label_color`, `label_bold`, `label_chip`).**
~~- C16 The map-created toast to one line (after Q21) | U41~~ **Fixed before s5-1110 (test_wb_dog1_fixb U41 says one line).**

**W20 Shell accessibility and narrow widths** (C, shell and CSS, Sonnet). Files: `frontend/css/10-responsive.css`, `palette.js` (accessibility only), `index.html`. Checks: `tests/test_zoom_wrap_1717.py`, `scratchpad/ui-sweeps/zoom1717.js` at 600, 480 and 390, axe. Done when: 0 overflows at 390 and axe clean on the palette and the space menu.
~~- C17 The palette is not a combobox: no `aria-activedescendant`, results not announced | 1028-shell S5~~ **Fixed before s5-1110 (CHANGELOG 1503).**
~~- C18 The space menu fails axe (aria-required-children, nested-interactive) | 1029-extras X4~~ **Fixed before s5-1110 (CHANGELOG 1517).**
- ~~C19 Ask button clipped at 390; quiet chips 28.6 px on a phone; selection ticks 44 px | 1028-shell S6, chatfoot L5, UI#11 item 12~~ **Built earlier (HISTORY, W20 C17 to C19); re-measured pr216-settings at 360 and 390: Ask button 59 by 44 px, right edge 147, no chip under 32 px, 0 sideways scroll.**
- ~~C20 Notes dock wraps from 1280 to 1500 with the rail open; capture row wrap at 1024; tab bar 600 to 819 | t20#10, WORLD_CLASS#13~~ **Not reproduced pr216-settings 2026-11-11, again at 360, 390 and 1280** (360 and 390: the notes dock stacks on three rows by design, tab bar one line, no document sideways scroll; 1280: dock 46 px one row, tab bar 36 px; Chromium on :8791, rail open, 1280, 1366, 1440 and 1500: no flex-wrap bar on two lines; capture rows at 1440, 1280 and 1024: each 36 px, one line; tab bar at 819, 700 and 600: one line, 7 tabs, 0 overflow).
- ~~C21 Settings scrolls sideways at 768; Recent head clipped under 1200 | UI#11 item 12, zoom4~~ **Found and fixed at 360 pr216-settings 2026-11-11:** the Microphone row (83 px label plus 180 px select in a 234 px row) made Settings General scroll sideways by 14 px; it is a grid now (`meetings-lazy.css`, tests/test_mic_row_fits_c21.py): scrollWidth equals clientWidth at 360 (292 vs 278 before), 390 and 1280, the select stays right-aligned. Earlier read: **Not reproduced** (Settings General, Models, Packages, Data at 768 to 1500: 0 sideways scroll, 0 elements past the viewport; the Recent title is hidden under 1200 on purpose, `10-responsive.css` rule 9, and from 1200 it sits above its four buttons on its own line, nothing clipped).
- ~~C22 1920 by 1080 at 125 to 200 % not driven | zoom4~~ **Driven before (HISTORY, W20 C22).**
- ~~C23 "?" after a Dashboard click hands focus to CodeMirror | row21 L47~~ **Not reproduced** (HISTORY and pr216-settings 2026-11-11: Dashboard click, then "?": focus lands on the shortcuts Close, not CodeMirror, empty notebook; again at 360, 390 and 1280: `#shortcuts-close` each time).

**W21 Dashboard, timeline and counts** (C, dashboard, Sonnet; verify first). Files: `dashboard.js`, `timeline*.js`, the import toast, the appearance settings. Checks: `tests/test_dashboard_*`, `tests/test_timeline_*`. Done when: every count is the true total. Verified 2026-11-11 (graph-1111.md): no count short of the true total found; the Timeline's "N+" became a true total (`/timeline` first page `total`, tests/test_timeline.py).
~~- C24 Dashboard insight counts capped by a fixed limit | 1028-shell S8~~ **Fixed before s5-1110 (count in SQL).**
~~- C25 Timeline header count and "days" plural wrong for 1 and for paged data | 1028-shell S7~~ **Fixed before s5-1110 (CHANGELOG 1562).**
~~- C26 Import toast gives no skipped or duplicate breakdown | 1028-shell S9~~ **Fixed before s5-1110 (import toast).**
~~- C27 A theme change wipes the page background | 1028-shell S10~~ **Fixed before s5-1110 (page background pair).**
~~- C28 Statistics drops private notes silently; "6 more than last week (0)" | 1029-extras X13~~ **Fixed before s5-1110 (statistics `left_out`).**
~~- C29 One click on the timer chip stops a 25-minute timer with no Undo | 1031-extras Z2~~ **Fixed before s5-1110 (`stopUtilityClock` offers Undo).**

**W22 Chat, Ask and the Guide** (C, Ask and help, Sonnet; not beside W1). Files: `capture-ask.js`, `ask-compose.js`, `ai/help_chat.py`, `ai/help_topics_more.py`. Checks: `tests/test_manual_parity.py`, `tests/test_guide_*`. Done when: each row fixed, help moved with it (order 13).
- C30 Ask redesign at half width | t20#4, OPEN 22-10 doc. **Measured 1111 docs spoke, not changed:** the Ask section at 720 and 960 px wide has 0 elements past the viewport and scrollWidth equal to the width; the row has no spec beyond "half width", so a redesign is an owner call
- ~~C31 Start SearXNG from a button | t20#6~~ **Stale: built** (ask-compose.js searxng-start offer), s6-1110
- ~~C32 One-line summary at the top of every Help topic | oa 1607 e, 1612 b~~ **Stale: built** (help_leads.py), s6-1110
- ~~C33 The Guide's no-model answer prints no "I took that to mean" | t20#13~~ **Stale: built** (offline_answer says "Assuming you meant"), s6-1110
- ~~C34 Ask history shows glued titles | 1107 D26~~ **Not reproduced: same cause as D5 (fixed)**, s6-1110
- C35 Citation style (after Q1); ~~path-first Guide answers (after Q23)~~ | 1107 D25, E33. **E33 built 1111 docs spoke** (spoken lead first, place as its own last line for a how-to with no steps; where-questions and stepped how-tos already led with the place). **D25 built 517ee90 (composer spoke 2026-11-11: `linkCitedTitles` removed from ask-compose.js, pinned in tests/test_composer_688.py; numbered marks match Sources); Q2 (Atlas voice) and Q7 (contiguous quote) verified pinned by tests/test_engine_identity.py and tests/test_composer_cfix_1031.py:694.** (was: D25 left for the composer spoke:) the bracketed title is written by `composer_phrases`, `composer_answer`, `composer_notes` and `composer_openlinks`, so removing it (and then `linkCitedTitles` in ask-compose.js and tests/test_composer_688.py) is one change across files this spoke does not own
~~C36 "buttons disappeared" after opening Why: not reproduced, one more drive | chatfoot L4~~ **Closed 1111 docs spoke as unverifiable:** O26 already records 0 removals in three drives; a fourth adds nothing without a repro

**W23 Documents daily UX** (C, documents, Sonnet; verify first; not beside W4 or W28). Files: `documents*.js` outside the save path. Checks: `tests/test_doc*`. Done when: rows fixed or struck.
- ~~C37 Spell and autocorrect split non-ASCII words ("café") | 1028-docs D8~~ **Stale: fixed** (CHANGELOG 1499), s6-1110
- ~~C38 History previews leak raw markup | audit-1102-docs DX27~~ **Stale: built** (7af47c4), s6-1110
- ~~C39 Link offers have no Settings switch; "Untitled document N" naming | t20#15, t20#16~~ **Stale: built** (Settings link offers switch; documents.js Untitled document N), s6-1110
- ~~C40 Equation panel jump row and Inline/Display pill | DOCUMENTS 1566~~ **Stale: built 6c08378**, s6-1110
- ~~C41 The remaining 1028-docs and 1031-docs open rows | book1 (40 and 7 rows)~~ **Re-verified 1111 docs spoke, one by one:** built D2, D3 (W4: test_doc_save_serial, test_doc_new_draft_1110), D36 (`docDropIfUntouched` re-adds the row on a failed delete), DC8 (archived PUT is 409; `filetypes.require` refuses an unknown type), DC11 (the template dialog focuses the checked radio, measured; the panel reads "Fix all N" and "N suggestions in view"); stale D29, D34, D40, D41, DC7, DC10; built here D28; won't D25, D23, D45, D46; deferred large (D22, D42, D43, D47, D52, DC13); partial D39 (a status-bar Autocorrect switch is not built, the Editor menu one is); DC1 and DC2 (lock leaves words on the page; AI panel over the lock screen) are lock code, another worker's
- ~~D28 Text size is three steps, no Ctrl+wheel | 1028-docs D28~~ built e2775e4 (five sizes, Ctrl+wheel, tests/test_doc_text_zoom_1111.py); D29, D40, D41 stale (built); D25 won't do (rules interleave with the shared note toolbar and theme overrides, no measured defect, cascade-order risk in a move)

### Tier D: performance and CI time

**W24 CI time** (D, overlay engine and tests, Sonnet high). Files: `core/overlay/behaviour.py`, `engine.py`, `tests/test_overlay_*`, `.github/workflows/`. Checks: seeded output hashes identical before and after (the cispeed method), `--durations=0` on CI. Done when: the 3.11 and 3.12 jobs finish under 45 minutes. **Built 2026-11-11 (5b2dc80bd, 3b29229d6):** CI runs in two legs per version (`pytest --shard i/2`, `tests/_shard.py`), shared overlay hours, split portal/puff and life tests, scope ratchet 62 s to 2 s, durations summary per file. **Left, needs CI:** read the first "Test time by file" summary and tune `WEIGHTS` in `tests/_shard.py`; confirm each leg is under 45 minutes; a branch-protection rule naming `Tests (Python 3.11)` must be changed to the six leg names (owner setting).
- ~~D1 `FlowField.step` closed-form rest for a settled flow; `_next_act_pose_change` 30 samples a wake | cispeed L5~~ **Done** (Flow.step rest; `_next_act_pose_change` left), s6-1110
- ~~D2 The longest overlay tests (rest 81 s, life 69 s) | cispeed L4~~ **W34: fixed 7d9cfbbc7** (w34-unv1-1111.md)
- D3 Slow tests outside the overlay (launcher 20 s, resurface 18 s, search spec 15 s, backup 13 s) | cispeed L6 W34: true-deferred, w34-fix1-1111.md.
- D4 Find the unexplained tail: `--durations=0` on one CI run | HANDOVER 09b W34: hardware-only (CI), w34-unv1-1111.md.
- ~~D5 `test_complexity.py` over 15 and two lazy import cycles; complexity.yml baseline (after Q20) | fablecomp, OPEN lint debt~~ **Partly done** (PERF baseline zero and failing, Q20); the seed functions and two lazy cycles remain, s6-1110

**W25 Palette and tab open** (D, shell, Sonnet high; not beside W11 or W20). Files: `palette.js`, `notes-list.js`, `settings*.js`. Checks: long tasks at 4x before and after. Done when: the palette is under 150 ms a keystroke at 4x. *Measured (claude/pr216-graph): palette keystroke at 4x p90 41 ms JS, 98 ms to paint, max 133; target met. Settings open remains the design pass (D8).*
- ~~D6 The palette blocks on open and on every letter (5.6 s at 4x) | 1031-shell SH1, 1031-perf PF3, UI Palette row 2~~ **Done s7-1110** (PF3 had drawn a 24-row window; now the ranking is kept 2 s for the same words so the notes arriving redraw nothing new, and the nearest-word scan splits each row once: 500 notes, 4x, key to second frame p50 68 to 67 ms, p90 191 to 123/127/183 ms over three runs on a loaded host, 43 keys; under 150 ms at p50)
- ~~D7 Opening a tab blocks for seconds at 4x; the notes list at 4x; a phone renders every note | 1031-perf PF5, 1031-notes N4, 1031-shell SH7~~ **Done s7-1110** (a tab opens in 150 to 400 ms wall at 4x with 500 notes, no task over 340 ms; the dashboard sizer's `checkVisibility` forced a 129 ms style pass as the tab went hidden, now the class is read first; the list is `content-visibility` rows, 1,098 nodes for 500 cards on desktop and 899 on a phone)
- ~~D8 Settings panes block on open; the pane-by-pane build | 1031-shell SH12, audit-1108-perf P4~~ **Stale, measured f6-1111 (not built):** the idle pre-parse (8d2899519) took the open to 415 to 510 ms painted at 4x CPU with a 200 ms longest task (s7-1110 had 2.0 s and 655 ms), 80 to 150 ms at 1x with no long task; a profile of the open at 4x puts 10 ms in `replaceWith` of the 3,000 nodes and the rest in style and layout of the one visible pane plus `panel-movable.js` forced layouts (`panelPinned`, `panelAdopt`, `panelGripRoom`, about 90 ms), because the other 20 panes are `.hidden` and unstyled. A pane-by-pane build could save only that 10 ms and would need `settingRows`, the Settings index and the palette's `settingsIndex` to build every pane to scan it; the real remaining cost is panel-movable's layout reads at open, not the template
~~- D9 A composed chat answer mounts 500 to 860 nodes | audit-1108-perf P8~~ **Built s58left3-1110** (older replies' corner head is an svg/use of one hidden copy: 167 to 8 nodes a reply, pixels within 2 of 255; the answer body itself, about 100 nodes, is untouched)
- ~~D10 `?preview=300` (after Q9) | fitaudit 42~~ **Stale: built** (CHANGELOG, INBOX 1525: list pages, the by-id refresh and the Semantic list carry `?preview=300`; `tests/test_entry_writers_whole_1525.py`)

**W26 Graph at scale** (D, graph, Opus). Files: `graph*.js`, `graph-worker.js`. Checks: the 500 and 2,000 note fixtures at 1x and 4x. Done when: a 2,000-note settle is under 5 s with no task over 50 ms. Part done 2026-11-11 (settle 3.3 s; tasks over 50 ms 10 to 5 at 1x; minimap one parse, balance waits for rest, link grid chords); rest in `graph-1111.md`.
- ~~D11 2,000 notes: layout 28 s and main-thread long tasks | 1029-graph G3, 1028-shell S2, GRAPH row 19~~ **W34: fixed** (w34-L1-1111.md)
- D12 500 notes at 4x: hover p50 83 ms, wheel 133 ms | 1029-graph G5, GRAPH Rank 36 W34: owner-call, w34-L1-1111.md.
- ~~D13 Hover and wheel at rest redraw whole layers; the crossing count is output-bound | graph19 L4, L5~~ **W34: fixed** (w34-L1-1111.md)
- D14 Redraw only while something moves; crossings and hub spokes at 40 nodes | UI 1643, oa 1643 a, GRAPH 1306 W34: owner-call (tracked in the plans), w34-L1-1111.md.

**W27 Boot weight** (D, boot, Sonnet). Files: `index.html`, `meetings.js` (after W6), `prefs.js`, the boot caps. Checks: `tests/test_static_compression.py`, the boot caps. Done when: each surface is lazy, with its number. *Partly built (claude/pr216-graph): 12 single-caller helpers moved lazy, boot gzip 250,954 to 250,434; the rest of the candidates are read by tests or lazy-to-lazy calls (list in graph-1111.md).*
- ~~D15 index.html 1.1 MB with comment blocks and companion code in the boot path | 1028-shell S3~~ **Stale, s7-1110:** `served_index_html` strips comments; served it is 811,185 bytes (156,226 gzip) of the 1,172,267 on disk; 434 KB of that is the five `<template data-surface>` blocks (settings 267 KB, board 149 KB). Inline SVG is 11 KB, inline scripts 2 KB
- ~~D16 Meeting recorder card, graph options panel and boot CSS lazy | row21 L43, L44, L45~~ **Stale, measured f6-1111 (not built):** `#graph-options` is not in the boot DOM at all (it sits in the lazy `graph` surface: 0 nodes at 4 s after load, so the null-read risk named in s7-1110 is moot); `#meeting-overlay` is 61 of 1,796 nodes (3.4 percent) and 2,089 gzip bytes, and its CSS is already `meetings-lazy.css`; the graph options panel's boot CSS (03-dashboard-widgets.css lines 3815 to 4035) is 466 gzip bytes of the 178,830 boot CSS (0.26 percent; cap 179,300) and moving it later in the cascade changes which equal-weight rule wins, for under a third of a percent. Not worth the cascade risk
- ~~D17 Boards list lazy until visible (500-board fixture) | oa 1667 c~~ **Measured fine, s7-1110:** with 500 boards the Boards & maps sub-tab adds 215 nodes and three tasks (63, 81, 75 ms) at 4x
- D18 Recordings: trim decodes the whole file (700 MB an hour); notes cannot embed a recording | t20#11. Not started: a server-side cut needs a container writer (a design call) W34: owner-call, w34-L1-1111.md.

**W28 Documents typing and split** (D, documents, Opus; not beside W4 or W23). Files: `documents.js`, `docLivePlugin`. Checks: typing latency at 4x on the DX1 document. Done when: key-to-paint p50 under 16 ms on the long document.
~~- D19 Typing in a long rich document cannot keep up; 5 layouts a key | audit-1102-docs DX1, audit-1108-perf P9.~~ **Closed s58left4-1110:** spell marks measured, see HISTORY ("s58left4-1110"); the p50 gate stays unmet with or without marks and no cheap app-side cut is left.
- ~~D20 `docHistoryPersist` serialises the undo stack every keystroke | 1028-docs D6~~ **Stale: built 9a5227132** (`undoStorePut(key, () => state.toJSON(...))`, serialised at the store's pause)
- ~~D21 Split `docLivePlugin` and `documents.js` by responsibility | DOCUMENTS D23, fitaudit 22. Not started: `docLivePlugin` is already `documents-cm.js`; the next carve is `documents.js` 16,381 to 17,190 (CodeMirror view glue, 810 lines), which costs a line in `app.js`'s library bundle list against the gzip cap (260,857 of 260,860) and breaks tests that read `documents.js` by name (`test_code_vscode.py`, `test_docs_perf_1030.py`)~~ built (documents-view.js carved, 867 lines; documents.js 17,190 to 16,500; sha in the commit)

**W29 Structure ratchets** (D, cross-cutting, Opus design then Sonnet). Files: one carve per run, outside the files of the same session's other batches. Checks: `tests/test_global_scope_ratchet.py`, `tests/test_complexity.py`. Done when: each ratchet moves down.
- ~~D22 IIFE wraps (audit 37a, after iife4) and surfaces (21, 36) | fitaudit 19, 21, 36, 37~~ **W34: fixed** (w34-L1-1111.md)
- D23 Routes are the data layer (359 ORM queries in routes) | 1031-architecture AR1 W34: owner-call (tracked in the plans), w34-L1-1111.md.
- D24 One global scope of 10,000 names | 1031-architecture AR2. **Part done s58-1110:** 9,096 to 9,044 names (settings-packages.js, appearance-panel.js, whiteboard-history.js wrapped whole). **Part fixed scope-wrap-1111:** 8,504 to 8,454 names (lag-watch.js and agent-activity.js wrapped whole, tests read them through `_js_scope.unwrapped`); math-field.js, ask-chart.js and capture-card-more.js were already wrapped (W29 carves 10, 12, 14). The row stays open for the other unwrapped files
- ~~D25 Split `run_agent`; data tables out of code | SESSION_BRIEFS 62, 63~~ **W34: fixed** (w34-L1-1111.md)

**W30 Whiteboard render cost** (D, boards render, Opus). **Done wb-1111** (B39, the connector batch, the colour memo, B4 shape and connector paint key, B23 export index; see wb-1111.md). Files: `whiteboard.js` render path, `whiteboard-map.js`. Checks: frame time on a 500-object board. Done when: one edit re-renders only what changed.
- ~~D26 Every render rebuilds all map nodes; no dirty set | 1028-board B3, B4~~ **Done s7-1110** (topics and pen strokes were keyed, dec005f44; the cost left was the links: a 500-topic map with 300 cross-links at 4x CPU, median render: nothing changed 1,361 to 342 ms, one topic moved 1,501 to 309 ms, every topic moved 2,678 to 1,072 ms. One `querySelectorAll` of the topic boxes before the link pass instead of 600 `querySelector` walks, and each link's look found once a pass instead of three times, keyed on both ends' place and box. Link paths identical to a fresh computation after a move, a resize, two moves in one task)
- D27 Split `whiteboard.js` (26,103 lines) and `whiteboard-map.js` by carve | 1028-board B1, B2, WHITEBOARD#Placed 2026-11-04. Not started in s7-1110 (the files are 26,164 and 11,050 lines) W34: true-deferred, w34-fix1-1111.md.
- ~~D28 The composer's topical digests take 0.45 to 0.78 s on 500 notes (W10's files, Session 7) | audit-1108-perf P6.~~ **Closed 1111 with numbers** (500 topical notes, 6 topics, no model, `/chat/stream`, 8 topical questions, median of 4, a loaded 4-core host): the whole request is 0.08 to 0.17 s (was 0.45 to 0.78 s), of which `_digest_for` (`_subject_facts` included) 30 to 37 ms, retrieval 16 to 22 ms, follow-up chips 25.5 to 19.0 ms after the full-turn stop (`chat_chips.continue_chips` no longer composes chips past `MAX_CHIPS`; tests/test_chat_chips_cost_d28_1111.py). `raw_results` stays uncapped by design (12 front-end sites read it; 20 to 42 KB a response); no cost left that a budget would catch.

### Tier E: polish

**W31 Companion life** (E, overlay and in-app acts, Opus for the masculine design, Sonnet for acts; not beside W15 or W24). Files: `core/overlay/*`, `atlas*.js`, frames. Checks: `tests/test_companion_catalogue_1108.py`, the weights test (after Q12). Done when: each act is drawn on both sides or listed with a reason.
- E1 Acts to the desk: meditate, lounge, rest_head; in-app firefly, star pile | compalive, INBOX 1711 W34: owner-call (tracked in the plans), w34-L1-1111.md.
- E2 In-app-only acts that need desk frames (dangle, kick_legs, hang_one_hand) | INBOX 1710 W34: owner-call (tracked in the plans), w34-L1-1111.md.
- E3 The life-1109 ranked list (follow-through, startle settle, micro-saccades, stand-loop drift) | INBOX 1719 (b), life-1109 W34: owner-call (tracked in the plans), w34-L1-1111.md.
- E4 Masculine Atlas: head, eyes, shoulder join, expressions | oa 1607 b, c, d, B16 W34: owner-call (tracked in the plans), w34-L1-1111.md.
- E5 Own activities with props; wind-spirit travel; ambient acts by hour | oa 1692 e, n, d W34: owner-call (tracked in the plans), w34-L1-1111.md.
- E6 Lower body and nebula follow the pose; landing outcomes; edge squash; portal | oa 1692 e/n, B1, B3, T1, N5, N9 W34: owner-call (tracked in the plans), w34-L1-1111.md.

**W32 Backend tidy** (E, backend, Haiku verify then Sonnet). Files: small fixes in `api/`. Checks: targeted route tests.
~~- E7 Validation copy leaks field names | 1031-backend BK8~~ **Already built c6cc5767a** (field labels and the limit in the message; tests/test_validation_copy.py). Verified s8-1110.
- E8 ~~A disabled tool refused with the wrong reason (H11, `_refuse_if_off` 3f0030d41); duplicated loopback lists (K28, one list in core/security)~~; token sweep per request (K33) **not built, s8-1110**: `tests/test_vault_sessions.py::test_the_key_goes_when_the_last_granted_session_expires` pins that every authenticated request sweeps (a token injected into `_active_tokens` with an old stamp must revoke the vault key on the next request). A once-a-minute sweep fails it; needs the owner to move that test's intent, or a sweep keyed on a min-expiry that the test's direct injection also lowers | 1029-harness H11, 1028-backend K28, K33
- ~~E9 Real Tesseract and PDFium reads never ran | sec L13, OPEN RapidOCR row [unverifiable here: no tesseract or pypdfium2; needs a machine with both]~~ **W34: fixed** (w34-unv1-1111.md)
- ~~E10 The other 1028-backend and 1031-backend open rows | book1 (37 and 12 rows)~~ **Verified on head, backend-2-1111:** BK10, K19, K29 closed, E9 fixed (W34), K33 fixed 8d9cfce9e (the E8 note above is stale), K32 built 62af9c7; the only live rows are the god-module splits K24, K25, BK11 (Bk2 structure ratchets, not an owner call): routes_settings extras and logs blocks moved whole to `routes_settings_extras.py` and `routes_settings_logs.py` (2,762 to 2,317 lines). Left in k24-1111.md: recognise.py, entry/manager.py, core/database.py, `__main__.py`; `_start_tray` and `_run_desktop` Windows paths are unverifiable here.

**W33 Copy and help** (E, copy, Haiku then Sonnet). Files: help topics, copy strings.
~~- E11 "Tools and features" omits 60 palette rows | 1031-extras Z3~~ **Already built 073cc0c6b** (`featureCommandRows`; tests/test_xfix_1031.py). Verified s8-1110.
- ~~E12 The tool describes itself in the answer ("Read as the days from today") | 1030-composer Z49~~ **Waits on the owner** (49 assertions pin the "Read as" lines, the 1108 ask; decision 54; s8-1110.md). W34: skipped (composer spoke), w34-fix1-1111.md.
- ~~E13 "¦" written for "&" in a category; a "conversation" topic on a gym note | oa 1620 categories b, topics c~~ **No repro** (no writer of the character in src or frontend; s8-1110.md; needs the owner's data). W34: owner-call, w34-unv1-1111.md.
- ~~E14 Manual pictures as WebP made by the sweeps | oa 1612 c~~ **Deliberately empty** (s8-1110.md; the owner has not asked for a sweep-made image).

**W34 Verify sweeps** (E, docs only, Haiku, stackable outside the four). Each scout marks rows true, fixed or stale in its source and hands true rows to the batch of their surface.
- E15 book1 audits 1028 (agent, backend, board, docs, shell, ux; 303 rows) | book1 W34: owner-call (tracked in the plans), w34-L1-1111.md.
- E16 book1 audits 1029 to 1031 (362 rows) | book1 W34: owner-call (tracked in the plans), w34-L1-1111.md.
- E17 The OPEN.md ledger, 677 bullets, by section | book3 W34: owner-call (tracked in the plans), w34-L1-1111.md.
- E18 INBOX 904 B01 to B86; the INBOX 1670 and 1694 status lines | book6 W34: owner-call (tracked in the plans), w34-L1-1111.md.
- E19 SESSION_BRIEFS, 21 unmarked (43's duplicate body, 89, 91, 102 first) | book6 section 2 W34: owner-call (tracked in the plans), w34-L1-1111.md.
~~- E20 Plans' mixed multi-part reports, per part (CHAT 2026-10-10, WORLD_CLASS 399, 421 to 430, MINDMAP 431, WHITEBOARD 1352 to 1355, GRAPH 798, 802)~~ | book5. **Done s58left4-1110:** every part marked per part in CHAT_PLAN and WORLD_CLASS_PLAN (driven or CHANGELOG-read, said per part). Left as parts: 423 (b) Word TOC field, shading and columns; 423 (e) (h) (j); 424 (n) (o); 425 (e) to (g), (n); 430's phone, tablet and Settings list; CHAT's Guide gap, SearXNG timing, "show them", citation hover, web retry.
- E21 The 1692 and 1683 owner-asks partial rows | book2 owner-asks W34: owner-call (tracked in the plans), w34-L1-1111.md.

### Tier F: plan horizon (before the BACKLOG)

Rows are book5's plan sections; each batch takes its plan's open rows smallest first.
- **W18 Diagram features** (Sonnet): ~~R12 find, R14 both-ways arrows and shapes, R16 edge colour and block colour (built earlier: 625c1f1b0, 81b7778e2, a9378c781), R13 curve and spacing, R16 six more templates, typed zoom field (76b77b1), page head (Q26)~~ **built, s9-1110** (see HISTORY, "s9-1110"). ~~R15 corner minimap, Q26 Export button, select and add on the picture (S13, found built and measured), present-mode page fields (oa 1694 b3, built; phone target fixed)~~ **built, s9b-1110** (see HISTORY, "s9b-1110"). Left: templates sorted by use | DOCUMENTS#22.4, oa 1661 a, c, e, l, S13, oa 1694 b3
- **F1 Documents** (Sonnet): live code blocks, the 2026-10-19 gap rows, `\eqref`, the guided equation editor, VC rows, links L6 | DOCUMENTS (book5) | s9-1110: `\eqref` built (HISTORY); s9c-1110: `\eqref` across columns, gap row 14 built; the rest left (agent-remaining/s9c-1110.md); f1-graph-1111: graph block built (HISTORY); VC4 (documents-ide.js:66 unifiedMergeView), VC7 (filetypes.py diff and dockerfile), VC6 (harper-worker.js:107 own words) and the fold-all part of VC13 (documents-ide.js:109) are already built (stale); f1-graph-1111 (final): built gap row 1 (recording embed), row 9 (clipper properties), L6 import, export and tags, Ctrl+K equation row; blocked, one line each in agent-remaining/f1-graph-1111.md: row 10 (the whiteboard is a singleton, `wbState`, so a board embed editable in place needs a per-instance refactor of whiteboard.js first), row 5 (synced blocks: `![[Doc#^id]]` is read-only, an editable transclusion needs a design), row 6 (database view: no cross-note property query endpoint, then a lazy table renderer), video embed (out by decision 2)
- **F2 Whiteboard** (Sonnet): nine Format gaps, save each board's view, colour picker, BPMN and icon sets, draw.io rows | WHITEBOARD (book5) | **Built 2026-11-11 (HISTORY "f2-1111", s9c-1110.md "F2 run 3"):** all nine Format gaps (Label background, outline, place, width, wrap and spacing; frame Padding; the rest earlier), the colour picker (struck as already built, c939da6: Hex, R G B, Opacity, From screen; blind-tester timing not run), BPMN and icon sets (built earlier), View switches for the connection arrows and points. **Left, true size:** the other draw.io S rows in WHITEBOARD_PLAN section 10 (ER and iso routes, self-loop side, layer show, lock and order, paper-size frames, replace-all in search, Home key, Ctrl+Delete, tooltips, a second edge label, ports with offsets)
- **F3 Mind map** (Sonnet): ~~outline view, branch palette and font, a note node that edits, render pass 13b, rainbow every level, legend, Replace all on notes~~ built (HISTORY "s9c-1110 part 3"); left: audio notes (needs an owner decision on keeping raw audio: /media/upload takes images and PDFs only), Gantt (topics carry a due day, no start) | MINDMAP (book5) | s9-1110: search inside topic notes built (HISTORY); outline view was already built (MINDMAP_PLAN item 8); the rest left (s9c-1110.md)
- **F4 Chat** (Opus): composition layer (INBOX 1353), Phase 5 (a) to (g), Foundation F5, "X versus Y" | CHAT (book5) W34: owner-call (tracked in the plans), w34-L1-1111.md.
- **F5 World class** (Sonnet): durable jobs, ~~margin reader~~ (built for notes, s10b-1110), multi-window, torch at launch, F1 prefs, RapidOCR (after Q27), ~~filing vocabulary (Q29 taken: bar, related topics, frozen fixture; no second vocabulary)~~ | WORLD_CLASS (book5)
- **F6 UI** (Sonnet): Settings panes indexed, token budget and `!important` to 0 (**Fixed css-important-1111** for 21 of the 117 declarations, **and f6-1111 for 9 more: 87 left**, the dead `.dock-native-hidden` rule (7; nothing ever applied the class) and the ai-mark's art size (2; drawn at 24px inline already); what is left is measured to need `!important`: the motion switches (08, motion-still, 02), `.hidden` and `[hidden]`, the Appearance border-style and the two `border: none` that answer it, print's `display` (05, library-lazy, manual-lazy), the glass-off `backdrop-filter`, the sidebar resize handle's inline grid columns, and `.select-native-hidden`'s size, where the id-weight trick `:not(#_)` was tried and measured to lose to `.wb-topbar #wb-board-select` and `.wb-rail #wb-map-layout` (minWidth 0 became 96px and 144px), so `!important` is the right tool there; **Settings panes indexed built f6-1111**: 20 of 21 panes gave rows to the Settings search and Memory gave none, so its field has a visually-hidden label (tests/test_settings_panes_indexed_1111.py holds every pane to a row); **token budget built tokens-1111: 428 to 417, and 417 is the floor** (computed-style diff 0 over 39 surfaces at light and dark, 360/820/1440: six single-use tokens inlined, `--panel`, `--card-bg`, `--card-bg-hover`, `--border-light`, `--toast-ctl` merged into the root tokens they named; 170 tokens are named by a script and 81 more vary by theme or element and are read twice or more, 251 over 200 before any recipe pin, Atlas pose state or literal ratchet; `TOKEN_BUDGET` 417, DESIGN.md decision 9)), dissolve the 08 and 10 stylesheets, statistics and utilities rows, private-by-default (Q30: setting and create flag built s10-1110; Private view and bulk make-all built s10b-1110; left: the new-note lock toggle), voice dialog V1 to V8 built (voiceup); share target was already built | UI_MODERNISATION (book5), SESSION_BRIEFS 58
- **F7 Graph and timeline** (Sonnet): `?since=` cursor, tessellation view (after Q31), dot density at 5,000, day strip and spans (after Q32) | GRAPH, TIMELINE (book5) W34: owner-call (tracked in the plans), w34-L1-1111.md.
- **F8 Owner go** (held; sync, offline studio and audio built 2026-11-11, WORLD_CLASS rows 35 to 37): desktop pet, custom domain, blind panel, Fable diagram dive (after Q34) | WORLD_CLASS rows 35 to 37, OPEN shell W34: owner-call (tracked in the plans), w34-L1-1111.md.

### Session plan

Cap per session: four agents, at most two Opus; Haiku scouts stack on top. A fresh session per PR (order 8). Each session merges, gates and sweeps its batches in one pass (order 5a), then strikes the rows here.

| Session | Batches (parallel) | Haiku stacked |
| --- | --- | --- |
| 1 | W0 merge, then W1 (Opus), W2 (Opus), W3, W4 | E15, E16 (W5 to W11 rows first) |
| 2 | W5, W6, W7, W12 | E17 |
| 3 | W8, W11, W13, W14 | E18 |
| 4 | W9, W15, W16 (model up), W17 | E19 |
| 5 | W10, W19, W20, W21 | E20 |
| 6 | W22, W23, W24, W26 (Opus) | E21 |
| 7 | W25, W27, W28 (Opus), W30 (Opus) | none |
| 8 | W29 (Opus), W31 (Opus), W32, W33 | none |
| 9 | W18, F1, F2, F3 | none |
| 10 | F4 (Opus), F5, F6, F7 | none |
| 11 to 12 | Rows the scouts found true (E15 to E21), in their surface's batch; then the BACKLOG | none |

Estimate: 12 sessions to the BACKLOG boundary, honestly 11 to 14: the verify sweeps will add rows, and composer batches usually take a second round. F8 waits on Q34 and is not counted.

## From the 22-10 bug doc (owner, not fixed in 0.6.1)

Composer and Guide
- Aware of the screen and recent actions; varied, shorter, warmer replies with a closing line or next step; length adjustable; personas disabled when no model. **Partly done 7072808** (no-model closing line from the newest note, Length picker applies, persona noted in Help; not done at that commit: awareness of the screen, a disabled persona picker). **Then done by composer2**: screen awareness (tab, open note, last 3 actions, chat topic; local, private notes never named), the persona picker disabled with a reason while no model is reachable, and richer composer phrasings (36-row table). Real-model behaviour unverified. (checked 2026-11-09) [verified 2026-11-10: fixed, composer2 built screen awareness, the disabled persona picker and the phrasings; real-model behaviour unverified]
- Ask tab replies are identical across notes and list dates and links instead of answering; redesign Ask at half width. **Fixed 67ef381** for an open note (composer_open.py); the half-width redesign is not done. (checked 2026-11-09) [verified 2026-11-10: true, half-width Ask redesign not built; 67ef381 covers the open-note reply only]
- Web search with no model needs SearXNG on 127.0.0.1:8888, which was not running (log in the doc); offer to start it or say how. **Fixed 33f7a0b** (says so, links the setting). **Then composer2**: the reply gives the one-line Docker command and the Guide's web search topic repeats it; with SearXNG chosen and no address saved it says web search is not set up. Starting the service from a button is not done. (checked 2026-11-09) [verified 2026-11-10: true, Start-from-a-button not built; the Docker line and disabled-state text are in composer.py]
- Ask tab: the owner reports the "You asked: ..." line above the answer is gone. It was removed on purpose in INBOX 1301 (tests/test_composer_form_1301.py pins it as a duplicate of the box). Confirm whether to bring it back; if so, change that test with the reason, and note the boot JS cap now has about 20 KB spare (bg-art.js went lazy, composer2). (checked 2026-11-09) [verified 2026-11-10: true, line removed on purpose (INBOX 1301); tests/test_composer_form_1301.py pins it; decision open]
- **Owner, 2026-10-22: the Composer and the needle (small local model) need a lot of improvement and expansion.** Open requests, web search, reading a pasted link, failure messages and the items above are examples, not the whole list. Treat as a top-priority theme for the next PR: measure a set of everyday requests against the Composer and a small model, then widen what each can do. (checked 2026-11-09) [verified 2026-11-10: true, open theme; no closing evidence in code]

Lint debt (from the 0.6.1 CI log)
- `complexity.yml` runs `ruff check src --select C901,PERF --exit-zero`, so it always passes and lists about 100 findings (C901 over 15, PERF401/403/101/102) as red annotations. Decide: a tracked cleanup (worst first: `docx_to_markdown` 55, `_optimization_pass` 37, `build_tree` 35, `provider.extract_text_tool_calls` 31, `relations.recognise` 31), or drop `--exit-zero` behind a baseline. (checked 2026-11-09) [verified 2026-11-10: true, .github/workflows/complexity.yml:26 still runs ruff with --exit-zero]
- `_start_tray` went 20 to 23 with the tray start-up logging: split menu building from start-up. Test on Windows. (checked 2026-11-09) [verified 2026-11-10: true, _start_tray still in src/tessellate/__main__.py; no split found]
- Reminder edit form: the time field keeps its bottom margin and may sit about 0.2rem high against the selects; the boot JS cap left no room (588,400 gz; fixed by moving a boot surface lazy). (checked 2026-11-09) [verified 2026-11-10: true, UI spacing; not driven here; boot cap note still stands]

Shell
- A desktop companion (pet) outside the window, as ChatGPT desktop's: quick open, new note, reminders. (checked 2026-11-09) [verified 2026-11-10: true, no desktop pet surface in frontend/ or src/] **Wrong, 2026-11-11 (q34pet-1111):** the desktop companion is that pet (`frontend/desktop-companion.html`, `core/desk_companion.py`, `core/overlay`): Quick note, Quick search, New reminder, Open today, due reminder cards; see UI_MODERNISATION_PLAN, Q34 decisions.
- Custom domain instead of localhost: **built 2026-11-11 (Settings, Address names).** (checked 2026-11-09) [verified 2026-11-10: true, custom domain not built (owner answer recorded, no code)]

## Everything open, 2026-10-11

One list of all open work, built 2026-10-11 by the ledger agent from INBOX, every agent-remaining file (head and unmerged branches), SESSION_BRIEFS, the nine plans, ROADMAP and BACKLOG. Nothing was fixed. Rows run owner first (running, then queued), then unassigned in batch order, so the batch ranges below are id ranges.

How to read it, and what it cannot promise:

- A row is one open line from its source, cut to one sentence. The source column is `file:line` at this commit; OPEN.md lines already include the shift made by this section. Branch ledgers show `branch:file:line`.
- Plan and BACKLOG rows come from the sections that hold open work (Placed from INBOX, Still open, Not verified, canvasdepth, the numbered open lists). Rows whose first 260 characters say built, fixed, done or closed were dropped, and rows with those words only later may be built already: check the code before building (CLAUDE.md section 1).
- Size is S (under an hour, one named fix or one check), M (a session, one surface) or L (several steps or a design pass). It comes from the source's own tag when it has one and from a text rule otherwise, so treat it as a first guess.
- The same fact can appear in two sources (a plan row and an OPEN row); exact repeats were merged, near repeats were not.
- Sections whose built state the plans do not mark row by row (WORLD_CLASS_PLAN dossiers, UI Phase 11, DOCUMENTS sections 10 to 17) are one `Section:` row each, not split.
- Briefs 2 to 33 are unmarked in SESSION_BRIEFS although HISTORY moved some of them; they are grouped rows to verify, then close or build.
- Branch ledgers of agents merging now (mergetrain) are listed from the branches, since their remaining files are not on this head yet; their rows have owner unassigned where the leftover is not part of a queued agent.

The older per-agent sections stay below this one, unchanged, as the long form of the OPEN rows (their text is the full detail behind each cut line).

Totals: 1667 rows, 183 with an owner (running or queued), 1484 unassigned. (2026-11-02: the 132 rows marked running belonged to agents that ended in October; their owner now reads "ended, unassigned".)

| Source | Assigned | Unassigned | Total |
| --- | --- | --- | --- |
| Brief assignments (this run) | 21 | 0 | 21 |
| agent-remaining files on unmerged branches | 136 | 87 | 223 |
| Plans and ROADMAP.md | 20 | 469 | 489 |
| INBOX.md | 5 | 18 | 23 |
| SESSION_BRIEFS.md | 1 | 24 | 25 |
| agent-remaining/OPEN.md | 0 | 643 | 643 |
| agent-remaining per-agent files (head) | 0 | 83 | 83 |
| BACKLOG.md | 0 | 160 | 160 |
| All | 183 | 1484 | 1667 |

Plan and ROADMAP rows by file: WORLD_CLASS_PLAN 114, UI_MODERNISATION_PLAN 91, CHAT_PLAN 87, MINDMAP_PLAN 70, DOCUMENTS_PLAN 54, WHITEBOARD_PLAN 37, AGENT_SKILLS_REFORM 12, GRAPH_PLAN 11, TIMELINE_PLAN 9, ROADMAP 4.

| id | item | source | size | owner |
| --- | --- | --- | --- | --- |
| 1 | INBOX 899: composer and agents pull from the notes' time words and time references | INBOX 899 (atlas branch) | M | atlas (ended, unassigned) W34: true, w34-L2r-1111.md. |
| 2 | Later rows for the queue: B20 to B27, B40. | agent/atlas-1011:docs/roadmap/archive/agent-remaining/atlas-1011.md:10 | S | atlas (ended, unassigned) |
| 3 | Not verified: any real model; the non-stream /chat route (routes_chat.py ~1571) does not answer capability questions from the list. | agent/atlas-1011:docs/roadmap/archive/agent-remaining/atlas-1011.md:12 | S | atlas (ended, unassigned) |
| 4 | Found, not fixed: a chat title keeps a trailing backslash ("what is there about a gaming mouse?\"); a digest answer has no Ask next chips except B9's... | agent/atlas-1011:docs/roadmap/archive/agent-remaining/atlas-1011.md:14 | L | atlas (ended, unassigned) |
| 5 | B10 rest: a document or board open in the Library (agentOpenSubject knows it; the Ask body sends only the note and category). B12 rest: flashcards... **Built 2026-11-01: B10 done: the Ask body sends `open_document_id` and `open_board_id` (capture-ask.js `askOpenContext`), `_open_surface` in routes_chat reads them; B12 flashcards still open (no flashcards feature, gold Q20).** | agent/atlas-1011:docs/roadmap/archive/agent-remaining/atlas-1011.md:6 | M | atlas (ended, unassigned) |
| 6 | B30 rest: the Chat tab's bubble draws the why event too. B31/B32 rest: decision 68's audit (not built) is to retire claims overlapping a wrong row... **Built 2026-11-01 (why-1101): the Chat bubble and the popup agent draw the why fold (`drawWhyTrail`, ask-compose.js); stubbed event, both themes, 360 wide: folded 28px (44px at 360), open 146px (345px at 360) in Chat, 183px (382px) in the popup, no overflow. Decision 68 stays open: see agent-remaining/why-1101.md.** | agent/atlas-1011:docs/roadmap/archive/agent-remaining/atlas-1011.md:7 | M | atlas (ended, unassigned) |
| 7 | INBOX 895: the composer as a legitimately smart chatbot, gold answers (semester example), Atlas answers | brief assignment; INBOX 895 (atlas branch) | L | atlas (ended, unassigned) |
| 8 | CHAT_PLAN decisions 65 to 70 and rows A1 to A8, B1 to B12, B30 to B32: Atlas as the app's assistant (A5 tool-result cards, A6 query clean-up, A3 history records, A7 background uses, A8 ghost text) | docs/roadmap/CHAT_PLAN.md:1765 | L | atlas (ended, unassigned) |
| 9 | A question about Atlas is answered about Atlas. Questions about capability ("can you", "do you", "are you able", "what can I do here") route to the... **Built 2026-11-01: ai/capability.py; routes_chat.py `_capability_answer` (capability.asks).** | docs/roadmap/CHAT_PLAN.md:1776 | M | atlas (ended), then queued: composer |
| 10 | Web results are a source panel, and a page is read in place. A web search shows its results in a collapsible block, the thinking box's recipe: title... **Built 2026-11-01: `web_search` tool results draw the web fold (closed 28px, open 314px, no overflow, reader in place; /tmp sweep open-web.js) in chat-attach.js and palette.js, beside the Ask fold (`renderWebSources`); the Web tab's own list stays open on purpose.** | docs/roadmap/CHAT_PLAN.md:1781 | S | atlas (ended), then queued: composer |
| 11 | **Built 2026-11-02 (HISTORY.md:219; facts._in_context).** A fact is learned only in its context. A note tagged joke, quote, fiction, test or draft, or a sentence inside a quote, a list of jokes or a Q-and-A... | docs/roadmap/CHAT_PLAN.md:1787 | M | atlas (running), then queued: composer **Built 2026-11-01 (audit68-1101, both halves): the night shift no longer reads a sentence into a claim when `learned_audit.context_reason` says it is out of context (`facts._in_context`: a note tagged joke, quote, fiction, test or draft, a sentence inside a quote or `>` line, a line of a Q-and-A list), and the check retires what was learned before (tests/test_learned_audit.py, test_learned_audit_run.py `test_the_night_shift_does_not_learn_out_of_context_in_the_first_place`; driven in the app: a joke-tagged note's claim retired with 'The note is tagged joke, so this is not a claim about you.'). Not built: a note's kind beyond tags (boards are not read as prose already).** |
| 12 | **Built 2026-11-02 (HISTORY.md:219; ai/learned_audit.py).** The learned store audits itself. "Check what it learned" is a runnable pass. It runs as a scheduled background job (Settings, Schedules), as a skill... | docs/roadmap/CHAT_PLAN.md:1793 | M | atlas (running), then queued: composer **Built 2026-11-01 (audit68-1101): ai/learned_audit.py (pure: note gone or edited, out of context, marked wrong, repeats, pair side gone retire; disagreeing newer note and passed dates flag), ai/learned_audit_run.py (stamped tombstones, undo and redo by stamp), the `learned-audit` job (core/passes.py Run now, Settings Background jobs; each autonomous pass runs it after the night shift) with lines, /learned/audit/{run,last,flags,undo,redo}, the button on What it learned's bar with its result box, Undo and Check this marks (settings-controls.js), the agent tool and skill `check_learned` / Check what it learned, Guide topic learned. Driven in the app (Playwright, 1440 and 390): 6 checked, 1 retired (joke tag), 2 flagged (passed date, 900 vs 950 rent); Undo put it back, Ctrl+Z retired it again. Not built: a per-flag Keep it action; the model-read contradictions beyond a number or a not (the Tensions pass already offers those); a settings switch for the scheduled run (it follows the night shift's).** |
| 13 | Completions are ghost text from the person's own words. In the capture box, the chat box and search: a greyed suggestion after the caret, Tab or... | docs/roadmap/CHAT_PLAN.md:1800 | L | atlas (ended), then queued: composer |
| 14 | The answer is judged against gold answers, not rule counts (INBOX 812: "you keep saying youve improved it but i still cant see much. I feel like Im... | docs/roadmap/CHAT_PLAN.md:1807 | L | atlas (ended), then queued: composer |
| 15 | Length adapts. The question's kind sets the answer's shape: a fact is one line, an overview is decision 70's shape, a compare is a table, a count is... | docs/roadmap/CHAT_PLAN.md:1853 | S | atlas (ended), then queued: composer |
| 16 | Voice is a setting. The presets are Warm and concise (the default), Neutral, Playful and Plain. One table of openings, joins and closings per preset... **Built 2026-11-01: index.html `#pref-voice` with `#pref-voice-sample`; ai/composer_voice.py.** | docs/roadmap/CHAT_PLAN.md:1858 | M | atlas (ended), then queued: composer |
| 17 | Volunteered insight is a switch, and dynamic. Off, one line, or as found. At "one line" the engine adds at most one gap, bridge, change or offer... **Built 2026-11-01: Settings, Chat `#pref-insight` (off, one line, all) saved as `insight_level`; routes_chat `_insight_level`; composer_digest `_volunteer`, `insight_bar`; tests/test_insight_b11.py.** | docs/roadmap/CHAT_PLAN.md:1862 | S | atlas (ended), then queued: composer |
| 18 | All four areas, in this order of build: answers (B1 to B12), trust (B30 to B32), utilities (rows A1 to A4), then the composer everywhere (B20 to... | docs/roadmap/CHAT_PLAN.md:1866 | M | atlas (ended), then queued: composer |
| 19 | Model up: it leads, the composer's facts are only labelled context (a test per surface); model down: the composer covers every act (the owner... | docs/roadmap/CHAT_PLAN.md:1870 | S | atlas (ended), then queued: composer |
| 20 | INBOX placed log: INBOX 895 smart chatbot placed with atlas, then the composer agent (Briefs 104 and 97) | docs/roadmap/INBOX.md:277 | S | atlas, queued: composer |
| 21 | Not verified: a real phone; the sweep's phone right flick is sometimes a drop here because the let-go reaches the page over 100 ms after the last... | agent/throw-1011:docs/roadmap/archive/agent-remaining/throw-1011.md:11 | S | throw (ended, unassigned) |
| 22 | **Already fixed 2026-11-02 (tests/test_companion_motion.py::test_every_way_to_a_note_counts_as_opening_it passes at head).** Found, not fixed (pre-existing on the base): test_companion_motion.py::test_every_way_to_a_note_counts_as_opening_it (flashEntry lost its typeof... | agent/throw-1011:docs/roadmap/archive/agent-remaining/throw-1011.md:13 | M | done (checked 2026-11-02: passes on claude/next-queue-1102) |
| 23 | INBOX 902 and Brief 88: companion physics (throw flight and feel, click arm, eased starts, resting pose) | docs/roadmap/SESSION_BRIEFS.md:1748 | L | throw (ended, unassigned) |
| 24 | scripts/rebrand.py (idempotent; --check; --repo-url, default Braydenh563/Tessellate; --brand-only). The orchestrator re-runs it after every merge... **Built 2026-11-01: scripts/rebrand.py (tests/test_brand_name.py runs it).** | agent/rebrand-1011:docs/roadmap/archive/agent-remaining/rebrand-1011.md:12 | S | rebrand (ended, unassigned) |
| 25 | INBOX 903: rename the product to Tessellate, formerly MemoryMap AI (step 2: internal identifiers; docs; pages site) **Built 2026-11-01: the src/tessellate package.** | agent/rebrand-1011:docs/roadmap/archive/agent-remaining/rebrand-1011.md:13 | L | rebrand (ended, unassigned) |
| 26 | Former name noted: README top, Settings, About, the Guide's "name" topic, the Pages footer, both CHANGELOGs. **Built 2026-11-01: README.md:8 (`Formerly MemoryMap AI`).** | agent/rebrand-1011:docs/roadmap/archive/agent-remaining/rebrand-1011.md:15 | S | rebrand (ended, unassigned) |
| 27 | Kept on purpose, with brand: keep beside each: the LAN certificate subject, the bcrypt-input salt (memorymap-bcrypt-input), the stored caption... **Built 2026-11-01: routes_auth.py `MEDIA_COOKIE` and the bcrypt-input salt, kept with brand: keep (tests/test_brand_name.py).** | agent/rebrand-1011:docs/roadmap/archive/agent-remaining/rebrand-1011.md:17 | M | rebrand (ended, unassigned) |
| 28 | ~~Shortcuts are renamed; the old ones go on upgrade and on uninstall.~~ **W34: fixed** (w34-L1-1111.md) | agent/rebrand-1011:docs/roadmap/archive/agent-remaining/rebrand-1011.md:22 | S | rebrand (ended, unassigned) |
| 29 | /health says Tessellate; every check accepts both names (instance_lock.APP_NAMES, start/uninstall .sh/.bat). **Built 2026-11-01: core/instance_lock.py:206 `APP_NAMES`.** | agent/rebrand-1011:docs/roadmap/archive/agent-remaining/rebrand-1011.md:23 | S | rebrand (ended, unassigned) |
| 30 | Package src/tessellate; src/memorymap is a shim (a meta-path alias to the same module objects, and python -m memorymap). The memorymap console script... **Built 2026-11-01: the src/memorymap shim (`__init__.py`, `__main__.py`).** | agent/rebrand-1011:docs/roadmap/archive/agent-remaining/rebrand-1011.md:28 | S | rebrand (ended, unassigned) |
| 31 | TESSELLATE_* settings; core/envnames.py reads MEMORYMAP_* as the fallback; launchers, compose and CI do the same. **Built 2026-11-01: core/envnames.py.** | agent/rebrand-1011:docs/roadmap/archive/agent-remaining/rebrand-1011.md:31 | S | rebrand (ended, unassigned) |
| 32 | Data folder: an existing MemoryMap AI folder is used where it is (never moved); a new install gets Tessellate (config._default_data_dir... **Built 2026-11-01: core/config.py `_default_data_dir`; tests/test_upgrade_keeps_data_folder.py.** | agent/rebrand-1011:docs/roadmap/archive/agent-remaining/rebrand-1011.md:33 | S | rebrand (ended, unassigned) |
| 33 | Browser: memorymap.ocr.* keys move once when library.js loads, beside their only reader (the app head is at its size ratchet); the undo store... **Built 2026-11-01: library.js `OCR_VIEW_KEY` and `OCR_READER_KEY` are `tessellate.ocr.*`, the old keys copied once and removed (d6deab4); tests/test_brand_name.py.** | agent/rebrand-1011:docs/roadmap/archive/agent-remaining/rebrand-1011.md:36 | S | rebrand (ended, unassigned) |
| 34 | Kept, as names on disk or on the wire: memorymap.db, backups memorymap-*.db, the memorymap_media cookie, export and import formats (memorymap-folder... **Built 2026-11-01: routes_auth.py `MEDIA_COOKIE` and the salt kept by name.** | agent/rebrand-1011:docs/roadmap/archive/agent-remaining/rebrand-1011.md:39 | M | rebrand (ended, unassigned) |
| 35 | Windows: the installer, an upgrade from a pre-rename release, the .bat fallbacks and the package-check workflow. No Windows here; CI runs them. | agent/rebrand-1011:docs/roadmap/archive/agent-remaining/rebrand-1011.md:47 | S | rebrand (ended, unassigned) W34: hardware-only (Windows), w34-unv1-1111.md. |
| 36 | A packaged (PyInstaller) build after the package rename. | agent/rebrand-1011:docs/roadmap/archive/agent-remaining/rebrand-1011.md:49 | S | rebrand (ended, unassigned) W34: hardware-only (Windows), w34-unv1-1111.md. |
| 37 | The icons' own <title> (favicon.svg, icon-maskable.svg) still say the old name: the owner's logo pass owns them. **Built 2026-11-01: frontend/favicon.svg and icon-maskable.svg line 3 say `<title>Tessellate</title>`.** | agent/rebrand-1011:docs/roadmap/archive/agent-remaining/rebrand-1011.md:50 | S | rebrand (ended, unassigned) |
| 38 | Branches cut before the rename: merge, then python scripts/rebrand.py (rewrites memorymap. imports, MEMORYMAP_ names and copy), then git mv any new... **Built 2026-11-01: scripts/rebrand.py rewrites old imports, names and copy.** | agent/rebrand-1011:docs/roadmap/archive/agent-remaining/rebrand-1011.md:55 | S | rebrand (ended, unassigned) |
| 39 | ~~New logo (favicon.svg and icon-maskable.svg titles still carry the old name)~~ **W34: fixed** (w34-L1-1111.md) | agent/rebrand-1011:docs/roadmap/archive/agent-remaining/rebrand-1011.md:30 | M | logo (ended, unassigned) |
| 40 | Not verified in a browser: the Alert menu, Undo the run then Ctrl+Z, the timeline range change (source and node tests only). | agent/data101b-1011:docs/roadmap/archive/agent-remaining/data101b-1011.md:6 | S | data101b (ended, unassigned) |
| 41 | **Already fixed 2026-11-02 (tests/test_activity.py::test_every_thread_site_is_registered_with_activity passes at head).** tests/test_activity.py::test_every_thread_site_is_registered_with_activity fails on the base: core/lanserve.py starts a thread nothing lists. | agent/data101b-1011:docs/roadmap/archive/agent-remaining/data101b-1011.md:7 | S | data101b (ended, unassigned) |
| 42 | Stop mid-call covers skill runs and write tools only; a plain Chat agent turn has no budget, so Stop there still lands at the next yield. | agent/data101b-1011:docs/roadmap/archive/agent-remaining/data101b-1011.md:8 | S | data101b (ended, unassigned) W34: true, w34-L2r-1111.md. |
| 43 | reminder_token.key sits beside the notes in the data folder: check backups and strip_leftovers do not need to leave it out. | agent/data101b-1011:docs/roadmap/archive/agent-remaining/data101b-1011.md:9 | S | data101b (ended, unassigned) |
| 44 | Brief 101b: data fixes (import bin clock, monthly anchor day, Alert menu, timeline load-more, token key) and its leftovers | docs/roadmap/SESSION_BRIEFS.md:1823 | M | data101b (ended, unassigned) |
| 45 | Brief 101: the found-not-fixed ledger of 41 unplaced rows (room101 is 101a; data101b running; first101c queued) | docs/roadmap/SESSION_BRIEFS.md:1823 | L | data101b (running), queued: first101c |
| 46 | INBOX placed log: INBOX 898 undo and redo universal sent to undoall | docs/roadmap/INBOX.md:275 | S | undoall2 |
| 47 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard.js:createNewBoard POST /board-library/new-board | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:100 | S | undoall2 (ended, unassigned) |
| 48 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard.js:finish PUT /whiteboard/boards/${boardId} | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:101 | S | undoall2 (ended, unassigned) |
| 49 | ~~**Already met 2026-11-02 (tests/test_undo_coverage.py EXEMPT: reason class given there).** whiteboard.js:initWhiteboard POST /media/upload~~ **W34: fixed** (w34-L1-1111.md) | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:102 | S | undoall2 (ended, unassigned) |
| 50 | ~~**Already met 2026-11-02 (tests/test_undo_coverage.py EXEMPT: reason class given there).** whiteboard.js:uploadToLibrary POST /media/upload~~ **W34: fixed** (w34-L1-1111.md) | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:103 | S | undoall2 (ended, unassigned) |
| 51 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard.js:wbClearBoard DELETE ${base}/${item.id} | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:104 | S | undoall2 (ended, unassigned) |
| 52 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard.js:wbCloneConnect POST /whiteboard/sketches | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:105 | S | undoall2 (ended, unassigned) |
| 53 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard.js:wbCreateBlankBoard POST /whiteboard/boards | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:106 | S | undoall2 (ended, unassigned) |
| 54 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard.js:wbImportOutlineFile POST /whiteboard/boards/import | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:107 | S | undoall2 (ended, unassigned) |
| 55 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard.js:wbNewUntitledBoard PUT /whiteboard/boards/${boardId} | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:108 | S | undoall2 (ended, unassigned) |
| 56 | ~~**Already met 2026-11-02 (tests/test_undo_coverage.py EXEMPT: reason class given there).** whiteboard.js:wbPlaceUploadedImage POST /media/upload~~ **W34: fixed** (w34-L1-1111.md) | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:109 | S | undoall2 (ended, unassigned) |
| 57 | Open design: stand-alone capture.js and clip.js windows have no stack; the board library 'new library' and 'delete library'; board objects the board... | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:11 | S | undoall2 (ended, unassigned) W34: owner-call, w34-L1-1111.md. |
| 58 | ~~**Already met 2026-11-02 (tests/test_undo_coverage.py EXEMPT: reason class given there).** whiteboard.js:wbRestoreLinks POST /whiteboard/sketches~~ **W34: fixed** (w34-L1-1111.md) | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:110 | S | undoall2 (ended, unassigned) |
| 59 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** ask-history.js:clearAskHistory DELETE /ask-history | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:16 | S | undoall2 (ended, unassigned) |
| 60 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** ask-history.js:deleteAskHistoryTurn DELETE /ask-history/${id} | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:17 | S | undoall2 (ended, unassigned) |
| 61 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** ask-history.js:forgetRecentQuestion DELETE /chat/recent?question=${encodeURIComponent(quest | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:18 | S | undoall2 (ended, unassigned) |
| 62 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** attach-to.js:renderAttachToBoard POST /whiteboard/nodes | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:19 | S | undoall2 (ended, unassigned) |
| 63 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** attachment-actions.js:remove DELETE /files/${spec.attachment.id} | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:20 | S | undoall2 (ended, unassigned) |
| 64 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** capture-ask.js:renderAnswerGrounding POST /learned/corrections | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:21 | S | undoall2 (ended, unassigned) |
| 65 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** capture.js:save POST /entries | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:22 | S | undoall2 (ended, unassigned) |
| 66 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** categories-panel.js:drawCategoryTidy POST /tidy-proposals/dismiss | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:23 | S | undoall2 (ended, unassigned) |
| 67 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** chat-agent.js:answer POST /memory/${proposal.id}/answer | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:24 | S | undoall2 (ended, unassigned) |
| 68 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** chat-edit.js:editAndResend POST /conversations/${chatConv.id}/truncate | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:25 | S | undoall2 (ended, unassigned) |
| 69 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** clip.js:save POST /links/clip-page | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:26 | S | undoall2 (ended, unassigned) |
| 70 | ~~dashboard.js:nightFactRow POST /entries/tensions/accept~~ **W34: fixed** (w34-L1-1111.md) | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:27 | S | undoall2 (ended, unassigned) |
| 71 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** dashboard.js:paintFadedNotes POST /learned/corrections | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:28 | S | undoall2 (ended, unassigned) |
| 72 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** documents.js:runDocAiEdit POST /documents/${currentDoc.id}/ai-edit | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:29 | S | undoall2 (ended, unassigned) |
| 73 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: no GAP entry left; INBOX 898 closed).** INBOX 898: undo and redo universal, 89 GAP entries left in tests/test_undo_coverage.py EXEMPT | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:3 | L | undoall2 (ended, unassigned) |
| 74 | ~~**Already met 2026-11-02 (tests/test_undo_coverage.py EXEMPT: reason class given there).** editor.js:inlineAiSubmit POST /documents/${currentDoc.id}/ai-edit~~ **W34: fixed** (w34-L1-1111.md) | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:30 | S | undoall2 (ended, unassigned) |
| 75 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** graph-canvas.js:gcDragEnd PUT /graph/pins | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:31 | S | undoall2 (ended, unassigned) |
| 76 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** graph-canvas.js:gcSaveTopicName PUT /graph/topics/name | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:32 | S | undoall2 (ended, unassigned) |
| 77 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** graph-canvas.js:gcTogglePin PUT /graph/pin/${node.id} | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:33 | S | undoall2 (ended, unassigned) |
| 78 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** graph-canvas.js:gcWireSelectionDock PUT /entries/${node.id} | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:34 | S | undoall2 (ended, unassigned) |
| 79 | ~~graph.js:renderGraphSvg PUT /graph/pin/${d.id}~~ **W34: fixed** (w34-L1-1111.md) | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:35 | S | undoall2 (ended, unassigned) |
| 80 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** library.js:bulkDeleteLibraryMedia DELETE endpoint | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:36 | S | undoall2 (ended, unassigned) |
| 81 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** library.js:filterLibraryImagesGallery DELETE endpoint | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:37 | S | undoall2 (ended, unassigned) |
| 82 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** library.js:finish PUT /graph/topics/name | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:38 | S | undoall2 (ended, unassigned) |
| 83 | ~~**Already met 2026-11-02 (tests/test_undo_coverage.py EXEMPT: reason class given there).** library.js:libraryActions PUT /conversations/${item.id}/pin~~ **W34: fixed** (w34-L1-1111.md) | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:39 | S | undoall2 (ended, unassigned) |
| 84 | ~~**Already met 2026-11-02 (tests/test_undo_coverage.py EXEMPT: reason class given there).** library.js:noteRead PUT /bookmarks/${bookmark.id}~~ **W34: fixed** (w34-L1-1111.md) | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:40 | S | undoall2 (ended, unassigned) |
| 85 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** lightbox-view.js:readingDelete POST /media/${id}/${source === vision ? vision-ocr : | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:41 | S | undoall2 (ended, unassigned) |
| 86 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** lightbox-view.js:run PUT /media/${item.id} | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:42 | S | undoall2 (ended, unassigned) |
| 87 | ~~**Already met 2026-11-02 (tests/test_undo_coverage.py EXEMPT: reason class given there).** meetings.js:meetingTakeBegin POST /recordings~~ **W34: fixed** (w34-L1-1111.md) | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:43 | S | undoall2 (ended, unassigned) |
| 88 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** meetings.js:meetingTakeDiscard DELETE /recordings/${id} | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:44 | S | undoall2 (ended, unassigned) |
| 89 | ~~**Already met 2026-11-02 (tests/test_undo_coverage.py EXEMPT: reason class given there).** meetings.js:meetingTakeFinish POST /recordings/${meetingTake.id}/finish~~ **W34: fixed** (w34-L1-1111.md) | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:45 | S | undoall2 (ended, unassigned) |
| 90 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** note-cards.js:entryItem PUT /entries/${entry.id} | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:46 | S | undoall2 (ended, unassigned) |
| 91 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** notes-list.js:offerWikiRename POST /entries/${entryId}/wiki-rename | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:47 | S | undoall2 (ended, unassigned) |
| 92 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** quick-note.js:flushNoteOutbox POST /entries | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:48 | S | undoall2 (ended, unassigned) |
| 93 | ~~settings.js:learnedBulk POST /learned/bulk~~ **W34: fixed** (w34-L1-1111.md) | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:49 | S | undoall2 (ended, unassigned) |
| 94 | ~~settings.js:learnedDelete DELETE /learned/${fact.id}~~ **W34: fixed** (w34-L1-1111.md) | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:50 | S | undoall2 (ended, unassigned) |
| 95 | ~~settings.js:learnedForget DELETE /learned~~ **W34: fixed** (w34-L1-1111.md) | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:51 | S | undoall2 (ended, unassigned) |
| 96 | ~~**Already met 2026-11-02 (tests/test_undo_coverage.py EXEMPT: reason class given there).** skills.js:saveFile POST /files/save~~ **W34: fixed** (w34-L1-1111.md) | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:52 | S | undoall2 (ended, unassigned) |
| 97 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** spaces-find.js:initSpaceSwitcher POST /spaces | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:53 | S | undoall2 (ended, unassigned) |
| 98 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** suggestions-inbox.js:inboxCorrection POST /learned/corrections | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:54 | S | undoall2 (ended, unassigned) |
| 99 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** suggestions-inbox.js:inboxTypeRow POST /suggestions/types/accept | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:55 | S | undoall2 (ended, unassigned) |
| 100 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** suggestions-inbox.js:tensionCard POST /entries/tensions/accept | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:56 | S | undoall2 (ended, unassigned) |
| 101 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** tidy.js:tidyDismiss POST ${path}/dismiss | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:57 | S | undoall2 (ended, unassigned) |
| 102 | ~~wiring.js:applyPendingChatTitle PUT /conversations/${conversationId}~~ **W34: fixed** (w34-L1-1111.md) | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:58 | S | undoall2 (ended, unassigned) |
| 103 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** chat-attach.js:commitStagedImages POST /media/upload | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:62 | S | undoall2 (ended, unassigned) |
| 104 | ~~**Already met 2026-11-02 (tests/test_undo_coverage.py EXEMPT: reason class given there).** documents-word.js:docWordUploadPicture POST /media/upload~~ **W34: fixed** (w34-L1-1111.md) | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:63 | S | undoall2 (ended, unassigned) |
| 105 | ~~library.js:(anonymous /media/upload) POST /media/upload~~ **W34: fixed** (w34-L1-1111.md) | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:64 | S | undoall2 (ended, unassigned) |
| 106 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** media.js:saveSketch POST /media/upload | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:65 | S | undoall2 (ended, unassigned) |
| 107 | ~~**Already met 2026-11-02 (tests/test_undo_coverage.py EXEMPT: reason class given there).** settings-wiring.js:commitCaptureImages POST /media/upload~~ **W34: fixed** (w34-L1-1111.md) | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:66 | S | undoall2 (ended, unassigned) |
| 108 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** settings-wiring.js:handleFileUpload POST /media/upload | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:67 | S | undoall2 (ended, unassigned) |
| 109 | Not verified: nothing here was driven in a browser (Playwright); every helper is checked by node --check and the scanner only. Undo of a board step... | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:7 | S | undoall2 (ended, unassigned) |
| 110 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard-interchange.js:post POST /whiteboard/sketches | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:71 | S | undoall2 (ended, unassigned) |
| 111 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard-interchange.js:wbDrawioPlace POST /whiteboard/sketches | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:72 | S | undoall2 (ended, unassigned) |
| 112 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard-interchange.js:wbImportBoardRows POST /whiteboard/sketches | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:73 | S | undoall2 (ended, unassigned) |
| 113 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard-interchange.js:wbImportMermaid POST /whiteboard/sketches | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:74 | S | undoall2 (ended, unassigned) |
| 114 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard-interchange.js:wbMermaidPlaceNode POST /whiteboard/sketches | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:75 | S | undoall2 (ended, unassigned) |
| 115 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard-library.js:run DELETE /board-library/libraries/${lib.id} | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:76 | S | undoall2 (ended, unassigned) |
| 116 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard-library.js:wbLibImportFile POST /board-library/import | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:77 | S | undoall2 (ended, unassigned) |
| 117 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard-library.js:wbLibNewBoardFrom POST /board-library/new-board | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:78 | S | undoall2 (ended, unassigned) |
| 118 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard-library.js:wbLibNewLibrary POST /board-library/libraries | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:79 | S | undoall2 (ended, unassigned) |
| 119 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard-library.js:wbLibPlace POST /whiteboard/boards/${boardId}/place | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:80 | S | undoall2 (ended, unassigned) |
| 120 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard-library.js:wbLibReplace PUT /board-library/${entry.ref.slice(5)} | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:81 | S | undoall2 (ended, unassigned) |
| 121 | ~~**Already met 2026-11-02 (tests/test_undo_coverage.py EXEMPT: reason class given there).** whiteboard-map.js:wbMapAdoptProvisional POST /whiteboard/boards/${row.board_id}/nodes~~ **W34: fixed** (w34-L1-1111.md) | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:82 | S | undoall2 (ended, unassigned) |
| 122 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard-map.js:wbMapClearEveryTopic POST /whiteboard/boards/${boardId}/nodes/clear-style | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:83 | S | undoall2 (ended, unassigned) |
| 123 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard-map.js:wbMapClearToOneTopic DELETE /whiteboard/objects/${root.id} | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:84 | S | undoall2 (ended, unassigned) |
| 124 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard-map.js:wbMapCrossLinkToBranch DELETE /whiteboard/sketches/${sketchId} | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:85 | S | undoall2 (ended, unassigned) |
| 125 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard-map.js:wbMapCutCrossLink DELETE /whiteboard/sketches/${sketchId} | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:86 | S | undoall2 (ended, unassigned) |
| 126 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard-map.js:wbMapFromDocument POST /whiteboard/boards/import | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:87 | S | undoall2 (ended, unassigned) |
| 127 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard-map.js:wbMapPasteText POST /whiteboard/boards/${boardId}/nodes/outline | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:88 | S | undoall2 (ended, unassigned) |
| 128 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard-map.js:wbMapRemoveKeepingBranch PUT /whiteboard/boards/${boardId}/nodes/move-many | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:89 | S | undoall2 (ended, unassigned) |
| 129 | Needs the server (no restore route): media/file deletes and uploads, ask-history delete/clear, learned delete/forget, tidy and tension dismiss... | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:9 | S | undoall2 (ended, unassigned) W34: owner-call (tracked in the plans), w34-L1-1111.md. |
| 130 | ~~**Already met 2026-11-02 (tests/test_undo_coverage.py EXEMPT: reason class given there).** whiteboard-map.js:wbMapRestoreRows POST /whiteboard/boards/${boardId}/nodes~~ **W34: fixed** (w34-L1-1111.md) | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:90 | S | undoall2 (ended, unassigned) |
| 131 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard-map.js:wbMapReverseCrossLink PUT /whiteboard/sketches/${sketchId} | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:91 | S | undoall2 (ended, unassigned) |
| 132 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard-map.js:wbMapReverseEdge PUT /whiteboard/boards/${boardId}/nodes/${id}/move | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:92 | S | undoall2 (ended, unassigned) |
| 133 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard-map.js:wbMapSetLayout PUT /whiteboard/boards/${boardId} | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:93 | S | undoall2 (ended, unassigned) |
| 134 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard-map.js:wbMapSetNumbered PUT /whiteboard/boards/${boardId} | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:94 | S | undoall2 (ended, unassigned) |
| 135 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard-map.js:wbMapSetTheme PUT /whiteboard/boards/${boardId} | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:95 | S | undoall2 (ended, unassigned) |
| 136 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard-map.js:wbMapSever PUT /whiteboard/boards/${boardId}/nodes/${id}/move | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:96 | S | undoall2 (ended, unassigned) |
| 137 | ~~**Already met 2026-11-02 (tests/test_undo_coverage.py EXEMPT: reason class given there).** whiteboard-map.js:wbMapTakePicture POST /media/upload~~ **W34: fixed** (w34-L1-1111.md) | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:97 | S | undoall2 (ended, unassigned) |
| 138 | **Already fixed 2026-11-02 (tests/test_undo_coverage.py: not in EXEMPT, passes at head).** whiteboard-map.js:wbMapWriteDocument POST /documents | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:98 | S | undoall2 (ended, unassigned) |
| 139 | ~~whiteboard.js:createConceptMap POST /whiteboard/boards~~ **W34: fixed** (w34-L1-1111.md) | agent/undoall-1011:docs/roadmap/archive/agent-remaining/undoall-1011.md:99 | S | undoall2 (ended, unassigned) |
| 140 | INBOX placed log: INBOX 871 help search bar below the welcome tour sent to chattime; 872 restart fixed; 873 smooth transition placed | docs/roadmap/INBOX.md:280 | S | mergetrain (chattime) |
| 141 | INBOX placed log: INBOX 897 sizes per device sent to devsize | docs/roadmap/INBOX.md:276 | S | mergetrain (devsize) |
| 142 | Merge train: cifix2, chattime, phonegraph, phone2, room101, lansafe, restart, scan, ownerfix3, meaning94, voiceup, tags89, graph100, devsize, wbfix, small, themes95, wbcolour, secscan (19 branches) | git branch --list 'agent/*' | L | mergetrain (ended, unassigned) |
| 143 | ~~INBOX 828, the owner 2026-10-11, verbatim (the Voice note dialog: transcribing, then "couldn't be transcribed"): "also if I record a meeting or audio...~~ (built, voiceup: 70f2622cc, 72fc97ee8, 1a27526f8; HISTORY s10b-1110) | docs/roadmap/UI_MODERNISATION_PLAN.md:1568 | L | mergetrain (voiceup) |
| 144 | ~~INBOX 829, the owner 2026-10-11, verbatim (the Focus timer widget): "can you redesign the focus timer as well??" (board and map previews are in...~~ (built, voiceup: 70f2622cc, 72fc97ee8, 1a27526f8; HISTORY s10b-1110) | docs/roadmap/UI_MODERNISATION_PLAN.md:1569 | L | mergetrain (voiceup) |
| 145 | ~~V2. Input: a device picker (every microphone the browser lists, remembered), noise suppression, echo cancellation and automatic gain as switches (the...~~ (built, voiceup: 70f2622cc, 72fc97ee8, 1a27526f8; HISTORY s10b-1110) | docs/roadmap/UI_MODERNISATION_PLAN.md:1575 | M | mergetrain (voiceup) |
| 146 | ~~V3. Enhancement on save, local: a high-pass and loudness normalise pass on the kept audio, a switch, on by default; the original is kept until the...~~ (built, voiceup: 70f2622cc, 72fc97ee8, 1a27526f8; HISTORY s10b-1110) | docs/roadmap/UI_MODERNISATION_PLAN.md:1576 | S | mergetrain (voiceup) |
| 147 | ~~V4. The level line draws the analyser's real signal and is measured to move; with reduced motion it is a static meter.~~ (built, voiceup: 70f2622cc, 72fc97ee8, 1a27526f8; HISTORY s10b-1110) | docs/roadmap/UI_MODERNISATION_PLAN.md:1577 | S | mergetrain (voiceup) |
| 148 | ~~V5. Live transcription: while recording, the captions pipeline writes the words into the dialog as they are spoken; the full pass replaces them after.~~ (built, voiceup: 70f2622cc, 72fc97ee8, 1a27526f8; HISTORY s10b-1110) | docs/roadmap/UI_MODERNISATION_PLAN.md:1578 | L | mergetrain (voiceup) |
| 149 | ~~V6. Live captions are reachable where a person looks: a Captions button in the voice note dialog and the Recordings bar, a row in the shell's tools...~~ (built, voiceup: 70f2622cc, 72fc97ee8, 1a27526f8; HISTORY s10b-1110) | docs/roadmap/UI_MODERNISATION_PLAN.md:1579 | S | mergetrain (voiceup) |
| 150 | ~~V7. The dialog redesigned from DESIGN recipes: name field, one large record control with the timer, the level line, the device chip, Pause, Stop and...~~ (built, voiceup: 70f2622cc, 72fc97ee8, 1a27526f8; HISTORY s10b-1110) | docs/roadmap/UI_MODERNISATION_PLAN.md:1580 | L | mergetrain (voiceup) |
| 151 | ~~V8. The focus timer: a ring with the time large, presets as a segmented control plus a custom stepper, Start and Pause as one primary, a chime and a...~~ (built, voiceup: 70f2622cc, 72fc97ee8, 1a27526f8; HISTORY s10b-1110) | docs/roadmap/UI_MODERNISATION_PLAN.md:1581 | M | mergetrain (voiceup) |
| 152 | **Already fixed 2026-11-02 (src/tessellate/api/wb_board.py:519 `_on_current_layer` drops a `""` layer).** frontend/js/whiteboard.js:8685: Undo of a delete re-creates the item with POST and a payload passed through wbKeepOwnLayer. | agent/wbfix-1011:docs/roadmap/archive/agent-remaining/wbfix-1011.md:24 | S | mergetrain (wbfix) |
| 153 | frontend/js/whiteboard-library.js:1653-1662, wbKeepOwnLayer: for a sketch it parses data and, when there is no truthy layer, writes layer: "". For an... | agent/wbfix-1011:docs/roadmap/archive/agent-remaining/wbfix-1011.md:25 | M | mergetrain (wbfix) |
| 154 | **Already fixed 2026-11-02 (src/tessellate/api/wb_board.py:519 `_on_current_layer`, the `""` case).** src/memorymap/api/routes_whiteboard.py:1328, _on_current_layer: on every create, if "layer" is absent it stamps the current layer. If the key is... | agent/wbfix-1011:docs/roadmap/archive/agent-remaining/wbfix-1011.md:26 | M | mergetrain (wbfix) |
| 155 | **Already fixed 2026-11-02 (src/tessellate/api/wb_board.py:519-523: `""` means no layer, key removed).** Recommended: make "" mean "no layer" on the server. In _on_current_layer, when data.get("layer") == "", return the data with the layer key removed... | agent/wbfix-1011:docs/roadmap/archive/agent-remaining/wbfix-1011.md:32 | M | mergetrain (wbfix) |
| 156 | Do not fix it by changing the sweep's comparator to ignore layer. That hides a real change to stored data. | agent/wbfix-1011:docs/roadmap/archive/agent-remaining/wbfix-1011.md:33 | S | mergetrain (wbfix) |
| 157 | **Already fixed 2026-11-02 (src/tessellate/api/wb_board.py:519: every create, text boxes too, goes through `_on_current_layer`).** Objects: the same layer:"" is written for text boxes (wbKeepOwnLayer line 1654). wbtrash660.js does not show it, because boardState() prints only... | agent/wbfix-1011:docs/roadmap/archive/agent-remaining/wbfix-1011.md:34 | M | mergetrain (wbfix) |
| 158 | Add a targeted test first, in the file that covers _on_current_layer (grep _on_current_layer under tests/): create with layer: "", assert the stored... | agent/wbfix-1011:docs/roadmap/archive/agent-remaining/wbfix-1011.md:38 | M | mergetrain (wbfix) |
| 159 | Restart the server after the Python change (uvicorn does not reload). | agent/wbfix-1011:docs/roadmap/archive/agent-remaining/wbfix-1011.md:39 | S | mergetrain (wbfix) |
| 160 | Rerun ONLY=board node scratchpad/ui-sweeps/wbtrash660.js (expect 39/39) and scripts/gate.sh --changed. Never the full suite. | agent/wbfix-1011:docs/roadmap/archive/agent-remaining/wbfix-1011.md:40 | L | mergetrain (wbfix) |
| 161 | scratchpad/ui-sweeps/wbphone.js (fixed by the sweep commit, not an app issue): intermittent. Across about 12 runs it failed 2 times. One failure was... | agent/wbfix-1011:docs/roadmap/archive/agent-remaining/wbfix-1011.md:44 | M | mergetrain (wbfix) |
| 162 | INBOX 896: LAN status-bar icon and popup, palette hotkey, live open/close on network change | INBOX 896 (docs/roadmap/INBOX.md:252) | L | queued: lanbar |
| 163 | INBOX 892: hotspot, re-issue the certificate when the address set changes | INBOX 896 (docs/roadmap/INBOX.md:252) | M | queued: lanbar |
| 164 | INBOX 894: each phone connection on the privacy receipt as an incoming row | INBOX 896 (docs/roadmap/INBOX.md:252) | S | queued: lanbar |
| 165 | INBOX 900: toggle LAN on or off from the status-bar icon, no restart | INBOX 896 (docs/roadmap/INBOX.md:252) | M | queued: lanbar |
| 166 | ~~A network change takes up to 30 s (lanserve.REFRESH_SECONDS) to close or open the port.~~ **W34: stale** (w34-L1-1111.md) | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/lansafe-1011.md:39 | S | queued: lanbar |
| 167 | ~~MEDIUM: PUT /preferences let a phone set searxng_url (SSRF to any LAN/localhost host, path /search), export_save_dir (where files land), auto-update...~~ **W34: fixed** (w34-L1-1111.md) | agent/secscan-1011:docs/roadmap/archive/agent-remaining/secscan-1011.md:25 | M | queued: lanbar |
| 168 | ~~MEDIUM (lansafe's lines, not edited here): POST /auth/lan-options lets a phone with the password turn "Allow on any network" on and "Ask before a new...~~ **W34: fixed** (w34-L1-1111.md) | agent/secscan-1011:docs/roadmap/archive/agent-remaining/secscan-1011.md:35 | M | queued: lanbar |
| 169 | ~~MEDIUM: QUT wifi. Base has no allowed-network gate: once LAN mode is on, the https port listens on every network the laptop joins, protected by the...~~ **W34: fixed** (w34-L1-1111.md) | agent/secscan-1011:docs/roadmap/archive/agent-remaining/secscan-1011.md:36 | M | queued: lanbar |
| 170 | ~~LOW, not fixable without remaking a decision: semantic auto-install (default on, the owner's choice) can be started by a failed embed that a phone's...~~ **W34: fixed** (w34-L1-1111.md) | agent/secscan-1011:docs/roadmap/archive/agent-remaining/secscan-1011.md:37 | M | queued: lanbar |
| 171 | ~~secscan decision 1: a phone-triggered auto-install is refused (semantic auto-install failed embed from a phone save)~~ **W34: fixed** (w34-L1-1111.md) | agent/secscan-1011:docs/roadmap/archive/agent-remaining/secscan-1011.md:44 | S | queued: lanbar |
| 172 | secscan decision 2: LAN auto-off after 14 days unused | brief assignment (secscan) | M | queued: lanbar |
| 173 | INBOX placed log: INBOX 892 and 894 placed with 896 (lanbar) | docs/roadmap/INBOX.md:278 | S | queued: lanbar |
| 174 | Not verified: a real iPhone (profile install, trust steps), Windows' Public/Private category (parsed from fixture JSON only), macOS readers (parsed... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/lansafe-1011.md:34 | S | queued: iPhone sweep |
| 175 | 887 keyboard: verify on a real iPhone in Safari. Sandbox only stubs visualViewport (scratchpad/ui-sweeps/kbinset.js); the owner's "covers the text... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/phone2-1011.md:6 | S | queued: iPhone sweep W34: unverifiable, w34-L2r-1111.md. |
| 176 | Not verified: a real iPhone Safari (the select picker opening on script focus is Chromium emulation evidence plus the owner's report); the compact... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/phonegraph-1011.md:7 | S | queued: iPhone sweep |
| 177 | iPhone sweep: verify the phone fixes on a real iPhone (keyboard 887, pinch 888, select picker 885, LAN profile install) | agent/phone2-1011 and agent/phonegraph-1011 ledgers | M | queued: iPhone sweep W34: unverifiable, w34-L2r-1111.md. |
| 178 | Not verified: a real phone on a real LAN (iPhone Safari); lansafe merged on top. | agent/secscan-1011:docs/roadmap/archive/agent-remaining/secscan-1011.md:40 | S | queued: iPhone sweep |
| 179 | Brief 101c: the found-not-fixed ledger, third agent | docs/roadmap/SESSION_BRIEFS.md:1823 | M | queued: first101c |
| 180 | INBOX 895 part 2: the composer as a smart chatbot after atlas | brief assignment | L | queued: composer |
| 181 | UK and US spelling equivalence in search (colour/color, organise/organize) | brief assignment | S | queued: composer |
| 182 | Brief 97: the composer as the place to go, the graph maker (INBOX 860) | docs/roadmap/SESSION_BRIEFS.md:1799 | L | queued: composer |
| 183 | Brief 104: typos read in context, not as slang (INBOX 869) | docs/roadmap/SESSION_BRIEFS.md:1845 | M | queued: composer |
| 184 | Not driven: the code IDE, the OCR workspace, the phone More sheet, the lock screen, the board's tools and Present. | docs/roadmap/agent-remaining/OPEN.md:2277 | S | unassigned |
| 185 | Not verified: a real Needle engine on leftover turns; a real chat model on a one-option ask_user. | docs/roadmap/agent-remaining/OPEN.md:2284 | S | unassigned |
| 186 | Not driven: dark theme for the hand-drawn look, tables, the Data tab and the current layer; a real touch double-tap into a table cell; an .xmind... | docs/roadmap/agent-remaining/OPEN.md:2293 | S | unassigned |
| 187 | No real model here: skill_rates.json ships empty, the small-class gate, time to first step and DEFAULT_CALLS_PER_STEP are unmeasured. | docs/roadmap/agent-remaining/OPEN.md:2314 | S | unassigned |
| 188 | Not verified: printed manual output, real-model answers, iOS zoom on the 13.6px name field. | docs/roadmap/agent-remaining/OPEN.md:2333 | S | unassigned |
| 189 | Not verified: a real model or Needle answering the assistant's prompts; the tablet layout beyond one measure at 1024. | docs/roadmap/agent-remaining/OPEN.md:2350 | S | unassigned |
| 190 | Not verified: real Whisper segments, a real model's rewording and speaker naming, "Name the speakers" driven in the page. | docs/roadmap/agent-remaining/OPEN.md:2358 | S | unassigned |
| 191 | Not verified: the path with a real model running (its grounded tags first, then the engine's); dark theme. | docs/roadmap/agent-remaining/OPEN.md:2372 | S | unassigned |
| 192 | Not verified: the owner's screen, Saved views, local and global switching, reduced motion in a browser. | docs/roadmap/agent-remaining/OPEN.md:2398 | S | unassigned |
| 193 | Not verified: a real embedder, the professional voice in a browser, 390px, the picture notice in a browser. | docs/roadmap/agent-remaining/OPEN.md:2442 | S | unassigned |
| 194 | Not verified: a Chat tap 700 ms after boot at 390 on an idle machine; the Highlight API in the macOS webview. | docs/roadmap/agent-remaining/OPEN.md:2452 | S | unassigned |
| 195 | Not verified: real Whisper on a kept recording; a real microphone, Safari (mp4) and Firefox (ogg). | docs/roadmap/agent-remaining/OPEN.md:2483 | S | unassigned |
| 196 | Not verified: under 1 s through the sheet on an unloaded machine; a real network install inside the app; WebView2 and Safari. | docs/roadmap/agent-remaining/OPEN.md:2492 | S | unassigned |
| 197 | Not verified: any real whisper-server or microphone, Firefox and Safari capture, Chromium's fake-mic start offset. | docs/roadmap/agent-remaining/OPEN.md:2510 | S | unassigned |
| 198 | Not verified against a real model: whether it plans act-shaped steps plan_writes can preview and uses the narrowed tools a planned step is offered... | docs/roadmap/agent-remaining/OPEN.md:2514 | S | unassigned |
| 199 | Not verified in the browser: Chat's own path for the plan card and per-write undo (chat-attach.js onTool); an edit's diff under a step (pytest only). | docs/roadmap/agent-remaining/OPEN.md:2515 | S | unassigned |
| 200 | Not verified: Firefox and Safari permission help, the webview's denied state, firing in a hidden tab (falls to the minute poll), a real non-UTC... | docs/roadmap/agent-remaining/OPEN.md:2534 | S | unassigned |
| 201 | Not verified: the dictionary spelling offer in a live empty result; the server's own correction answered every typo tried, so finderSpellingOffer was... | docs/roadmap/agent-remaining/OPEN.md:2538 | S | unassigned |
| 202 | Not verified: an act row against a running model; with no model it opens Chat with the act's opening words at 1440 and 390 and sends nothing... | docs/roadmap/agent-remaining/OPEN.md:2539 | S | unassigned |
| 203 | Brief 84, not verified: the Guide's new first line and act topics in a browser (API and unit tests only); no real model. | docs/roadmap/agent-remaining/OPEN.md:2615 | S | unassigned |
| 204 | Brief 34, not verified: the arm angle over a walk cycle; 104 px faces (2 to 3 of 15 distinct in light); no real WebView2 or WebKitGTK; all timings... | docs/roadmap/agent-remaining/OPEN.md:2644 | S | unassigned |
| 205 | Brief 69, not verified: the desktop webview; dark theme for the new panel rows; a large SQL result; touch.js on the other surfaces. | docs/roadmap/agent-remaining/OPEN.md:2668 | S | unassigned |
| 206 | Not measured by Brief 56: 1024 and 820 widths, dark-theme counts, a Chat with a conversation, the document AI panel, a board with a selection. | docs/roadmap/agent-remaining/OPEN.md:2677 | S | unassigned |
| 207 | The launchers want one run on a real Windows machine: start.bat, start.bat --doctor, start.bat --shortcut and uninstall.bat --dry-run, watching the... | docs/roadmap/agent-remaining/OPEN.md:2747 | M | unassigned |
| 208 | backend-0926.md: F7's thread modules onto core/jobs.py (13 left, tests/test_flaw_class_lints.py's ratchet). Not verified: the receipt against a real... | docs/roadmap/agent-remaining/OPEN.md:2776 | S | unassigned |
| 209 | Every provider test runs against a fake transport (CLAUDE.md section 4), and that covers more open work than any other single line here: no real... | docs/roadmap/agent-remaining/OPEN.md:3179 | S | unassigned |
| 210 | Not verified: whether the closed .doc-dock-menu-list at 390 paints (it lays out, 13 items, x = -32 on a code document); open it and measure before... | docs/roadmap/agent-remaining/OPEN.md:3291 | S | unassigned |
| 211 | Not verified: the map grip that overlaps "Add a child to" (its accessible name was not read; it shows only with a topic selected after adding... | docs/roadmap/agent-remaining/OPEN.md:3292 | S | unassigned |
| 212 | Not driven: Summarise's 503 with no model (read from routes_meetings.py), pinch zoom in the OCR workspace, the phone path of any board or map... | docs/roadmap/agent-remaining/OPEN.md:3294 | S | unassigned |
| 213 | CHAT: the evals gate runs on a 3B model (hours on these cores) and waits on a real-model run. (from op3-1005.md) | docs/roadmap/agent-remaining/OPEN.md:3308 | S | unassigned |
| 214 | Not verified in a browser: the another-device notice on the recovery card (the sweep server binds loopback only); a real phone and a screen reader on... | docs/roadmap/agent-remaining/OPEN.md:3369 | S | unassigned |
| 215 | Not verified: a real model's greeting in the new layout (a long AI line widens the left column up to its 45% cap; measured with handwritten phrases... | docs/roadmap/agent-remaining/OPEN.md:3371 | S | unassigned |
| 216 | Not verified: a real model load for the new built-in embedding models (no sentence-transformers here); Pull a model by name is tested against a... | docs/roadmap/agent-remaining/OPEN.md:3383 | S | unassigned |
| 217 | Not measured at 390: the Documents sidebar and the board zoom pill are not on screen there (the sidebar is a sheet), so both were measured at 1440... | docs/roadmap/agent-remaining/OPEN.md:3387 | S | unassigned |
| 218 | Not measured: the chat dock's controls, the board's context bar, the stepper and the map strip, named in PILL_CONTROLS with full-round rules. (from... | docs/roadmap/agent-remaining/OPEN.md:3388 | S | unassigned |
| 219 | Not verified: suggestion mode switched on while a candidate is chosen (the replacement goes through docProseFix), a touch long-press on a suggested... | docs/roadmap/agent-remaining/OPEN.md:3393 | S | unassigned |
| 220 | Not verified: the phone's action sheet (openKebabSheet) and touch below 600 (its dismissal was not pressed twice), a real screen reader, and the... | docs/roadmap/agent-remaining/OPEN.md:3396 | S | unassigned |
| 221 | Not verified: the contrast of the accent count on the broom (contrast.js), a browser run of the automatic pass after filing (pytest only), and a real... | docs/roadmap/agent-remaining/OPEN.md:3405 | S | unassigned |
| 222 | Not verified: Summarise against a real small model (the fake model only; its pipe format and quoting are unknown), and transcription (no... | docs/roadmap/agent-remaining/OPEN.md:3408 | S | unassigned |
| 223 | Not verified: the other 100 toast(..., true) call sites were not each triggered. A lint covers them; their situations (a formatter refusing a file... | docs/roadmap/agent-remaining/OPEN.md:3412 | S | unassigned |
| 224 | Not measured: dark theme for axe target-size and scrollable-region-focusable; the 1024 width. (from a11yfix-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3462 | S | unassigned |
| 225 | Decision 45: the readings are listed (composer._readings, src/memorymap/ai/composer.py:2693); a running model does not yet pick among them (needs a... | docs/roadmap/agent-remaining/OPEN.md:3493 | S | unassigned |
| 226 | Not verified: Ollama's real keep_alive: 0 and /api/ps (a slow fake in the agent's scratch dir stood in), the desktop window, WebKit. | docs/roadmap/agent-remaining/OPEN.md:3526 | S | unassigned |

**B. Plan tails, by surface.** Moved to HISTORY.md, "OPEN.md rows closed, 2026-10-05", 2026-10-05: every row was built or held by its plan. Two stay open: MINDMAP_PLAN's mapux leftover list (this file's Mind map section, the mind map agent's) and UI_MODERNISATION_PLAN Phase 11 item 11's screenshot set for the owner. Section C, the horizon, is WORLD_CLASS_PLAN section 8's own ranked list.
| 227 | Not verified: the .docx opened in Word itself (its XML and Mammoth's reading only); Format on a large real file; the list chords on a non-US layout... | docs/roadmap/agent-remaining/OPEN.md:3540 | S | unassigned |
| 228 | Not verified by either: a real model's path; a screen reader toggling a chip; a browser locale other than en-US; the full suite. [f1-1010, f2-1010] | docs/roadmap/agent-remaining/OPEN.md:3581 | S | unassigned |
| 229 | Not verified: real-model answers through the validators (fake transport and the route test only); dark mode. [f3-1010] | docs/roadmap/agent-remaining/OPEN.md:3592 | S | unassigned |
| 230 | Not verified: hybrid ranking cost at 5,000 notes with a real embedding model (keyword plus the fake backend only); the saved-search ⋯ menu opened in... | docs/roadmap/agent-remaining/OPEN.md:3600 | S | unassigned |
| 231 | Not verified: tests elsewhere that relied on blank lines removed from CSS files 00, 01, 02, 05, 06, 07 and 10 to pay for the CSS budget; the picker... | docs/roadmap/agent-remaining/OPEN.md:3673 | S | unassigned |
| 232 | Not driven with a real model: a live streamed answer getting its time when the meta row lands (driven with addAssistantBubble plus messageMetaLine in... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/chattime-1010.md:5 | S | unassigned W34: unverifiable, w34-L2r-1111.md. |
| 233 | Not verified: dark theme and phone width for the moved rules (only errors.js at 390: 0 findings); the first press of the bell on a slow link (the... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/room101-1011.md:10 | S | unassigned |
| 234 | Autocorrect with an IME, on a real phone keyboard (its own suggestions fire insertReplacementText, which this leaves alone), and in the graph's and... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/meaning94-1011.md:12 | S | unassigned W34: unverifiable, w34-L2r-1111.md. |
| 235 | A real model (Ollama or llama.cpp): every filing, Ask and Chat result above is against a stand-in server or no model. "Filing catches up once a model... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/scan-1011.md:15 | S | unassigned W34: unverifiable, w34-L2r-1111.md. |
| 236 | Enhancement on a real voice: measured on synthetic tones through Chromium's fake microphone (RMS 0.054 to 0.082, peak 0.158 to 0.254); takes over 30... | agent/voiceup-1011:docs/roadmap/archive/agent-remaining/voiceup-1011.md:15 | M | unassigned W34: unverifiable, w34-L2r-1111.md. |
| 237 | Not verified: any real model's behaviour in the handoff (choosing among numbered readings, "reorder, do not add"); the taxonomy pack's size as a... | docs/roadmap/archive/agent-remaining/assistant-1010.md:15 | S | unassigned |
| 238 | Not verified: Saved views and local/global switches through the view-change sweep (layouts, Refresh and a return to the tab were measured); the... | docs/roadmap/archive/agent-remaining/graphfeel-1010.md:23 | S | unassigned |
| 239 | Boot gzip budget, what the 2026-10-05 split did not take (792,754 to 758,418 bytes, notes-list.js 63,548 to 57,929; test_static_compression.py has... | docs/roadmap/agent-remaining/OPEN.md:1882 | L | unassigned |
| 240 | The budgets spec flaps in CI (a different budget each run: list, search, board, first_interaction) while it shares the runner with the other specs... | docs/roadmap/agent-remaining/OPEN.md:2219 | M | unassigned |
| 241 | App scripts at 320,589 of 320,600 gzipped (11 bytes); seven typeof guards removed on eager functions, each path not driven by hand. | docs/roadmap/agent-remaining/OPEN.md:2227 | S | unassigned |
| 242 | Decisions 12 (layers, 115 literals), 13 (19 drop shadows), 16 (128 .important) are ratchets only; 13.R not started. | docs/roadmap/agent-remaining/OPEN.md:2250 | S | unassigned |
| 243 | The run's budget usage is on the result event but not drawn in chat-agent.js's result box. | docs/roadmap/agent-remaining/OPEN.md:2316 | S | unassigned |
| 244 | Right-click and long-press on a snippet row do not open its menu (needs navigation.js ROW_MENU_HOSTS, a boot file, and TOTAL_CAP had 35 bytes). **Fixed 2026-11-02:** `.doc-snippet-item` is a host; in the app `rowMenuAtEvent` on a real `docSnippetRow` finds the item and its ⋯. | docs/roadmap/agent-remaining/OPEN.md:2348 | S | done |
| 245 | First interaction (about 4.4 s) is the slowest number; decision 54's 5,000-note list and search not re-measured; no Settings UI shows the budgets. | docs/roadmap/agent-remaining/OPEN.md:2389 | S | unassigned |
| 246 | Guide topics whiteboard-controls (1915 of 1920) and mind-map-features are at the reply budget. | docs/roadmap/agent-remaining/OPEN.md:2416 | S | unassigned |
| 247 | TOTAL_CAP (all app scripts) has 32 bytes of headroom; the next lever is the meeting overlay's listeners in settings-wiring.js. | docs/roadmap/agent-remaining/OPEN.md:2458 | S | unassigned |
| 248 | confirmDialog and promptDialog mount on <body>, so one asked from inside a modal opens beneath it; app.js is at its gzip ratchet. **Found already fixed 2026-11-02:** both use `.modal-overlay.confirm-overlay`, z-index 2100, above the 2000 palettes and every sheet (01-forms-settings.css 3283, INBOX 790). | docs/roadmap/agent-remaining/OPEN.md:2500 | S | done |
| 249 | timelinepaging.js: the strip-click check fails on the base too; its 100 ms frame check passed once and failed twice under load. | docs/roadmap/agent-remaining/OPEN.md:2532 | S | unassigned |
| 250 | VC12 (Harper on node labels) not started: the budget went to rows 1 to 9. MINDMAP_PLAN "Vendored capabilities to use" still holds it. | docs/roadmap/agent-remaining/OPEN.md:2550 | S | unassigned |
| 251 | maplayouts.js "tree-left carries the branch bar on the edge the parent is on" fails on the base too (1px against 1px). | docs/roadmap/agent-remaining/OPEN.md:2555 | S | unassigned |
| 252 | Step 5 not built: one curve table for every joint (120 to 400 ms), the idle pool's never-within-five rule and a reaction budget a minute beyond the... | docs/roadmap/agent-remaining/OPEN.md:2630 | M | unassigned |
| 253 | **Already fixed 2026-11-02 (tests/test_icon_conventions.py::test_the_vertical_kebab_is_only_at_the_end_of_a_vertical_list_row_or_in_a_narrow_column passes at head).** tests/test_icon_conventions.py::test_the_vertical_kebab_is_only_at_the_end_of_a_vertical_list_row_or_in_a_narrow_column fails on this branch's head... | docs/roadmap/agent-remaining/OPEN.md:2653 | M | unassigned |
| 254 | Brief 77, found: the shape flyout opens only from its 10 px caret or a long-press, too small for a finger on a phone; boot CSS is within 12 bytes... | docs/roadmap/agent-remaining/OPEN.md:2669 | S | unassigned |
| 255 | A flaky timing test: tests/test_relations_kg2.py's 10k timing is flaky under load (the typo, message-wording, thread-ratchet and list-paging tests... | docs/roadmap/agent-remaining/OPEN.md:3067 | S | unassigned |
| 256 | The behaviour model (Brief 34, second part): a state machine with blended transitions, idle variation from a weighted pool, reactions to every app... | docs/roadmap/agent-remaining/OPEN.md:3271 | M | unassigned |
| 257 | Timings: two runs at 1440, one at 390, the second 1440 run under a concurrent sweep; ranges, not budgets. (from deepen-b-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3423 | S | unassigned |
| 258 | The boot CSS cap (tests/test_boot_budget.py, 183,300) had 3 bytes of room; this work spent it with blank-line collapses in 00-tokens-shell.css and... | docs/roadmap/agent-remaining/OPEN.md:3459 | M | unassigned |
| 259 | app.js is within 14 bytes of its ratchet (tests/test_static_compression.py, 14,300): makeUnlinkAccessible moved out to note-cards.js to stay under... | docs/roadmap/agent-remaining/OPEN.md:3460 | S | unassigned |
| 260 | **Built 2026-11-11: the owner moved the bar to 0.6 (0.625 filed outright, test passes) and asked for "ask when unsure" (built, off by default).** Decision 8's bar, "below 0.8 top-1 without a model the step is not done": 0.417 (tests/test_filing_accuracy.py, strict xfail). Forced to choose, the... | docs/roadmap/agent-remaining/OPEN.md:3463 | M | unassigned |
| 261 | **Already fixed (passes at head, 2026-10-19).** Found, not mine: tests/test_ask_answer_object.py::test_ask_is_never_disabled_when_the_model_is_off fails on the base too (the chat skills trigger's... | docs/roadmap/agent-remaining/OPEN.md:3499 | S | unassigned |
| 262 | **Already fixed (tests/test_reading.py asks "What time on Friday ..."; 2026-10-19).** ai/reading.py reads "review budget friday" (reminder surface) as sure at 09:00 while quickadd.js asks "What time on ...?" (decision 50); the reading... | docs/roadmap/agent-remaining/OPEN.md:3577 | S | unassigned |
| 263 | Dashboard: the digest is in dashboard.js (a boot file, about 700 bytes gzipped); a lazy home would delay the first paint of the widget it opens. The... | docs/roadmap/agent-remaining/OPEN.md:3606 | M | unassigned |
| 264 | Boot JS 582,371 to 583,240 bytes gzipped (+869: the digest, the Library and Graph filters, the palette rows, the voice table, textCounts; cap... | docs/roadmap/agent-remaining/OPEN.md:3616 | M | unassigned |
| 265 | The 68 broad excepts that log nothing and return a fallback (89 minus the 21 seeded) are not ratcheted; decide whether decision 57 means them.... | docs/roadmap/agent-remaining/OPEN.md:3644 | S | unassigned |
| 266 | Graph at rest (1 to 10 long tasks) and the companion (4 to 6 at rest) are the two surfaces over the zero target (frames.js REST_BUDGET).... | docs/roadmap/agent-remaining/OPEN.md:3648 | S | unassigned |
| 267 | The constellation fades in; its stars do not glide in from a first position (dashboard.js is a boot script with 11 bytes of gzip headroom). | agent/graph100-1011:docs/roadmap/archive/agent-remaining/graph100-1011.md:23 | S | unassigned W34: true, w34-L2r-1111.md. |
| 268 | **Already fixed 2026-11-02 (tests/test_complexity.py passes at head).** tests/test_complexity.py fails on spelling.py, utilities.py, activity.py. | agent/graph100-1011:docs/roadmap/archive/agent-remaining/graph100-1011.md:32 | S | unassigned |
| 269 | Boot CSS 177,905 to 176,370 bytes gzipped (cap 183,300, unchanged): room 5,395 to 6,930. 89 Library-only rules moved to library-lazy.css, ahead of... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/room101-1011.md:3 | S | unassigned |
| 270 | 381 more Library-only CSS rules could move (633 qualify by selector, 470 pass the file ratchets, 89 moved). The rest tie on specificity with a rule... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/room101-1011.md:6 | M | unassigned |
| 271 | Found, not fixed: scratchpad/ui-sweeps/wbtrash660.js "shape: Undo restores the board identically" fails on the base too... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/phone2-1011.md:10 | S | unassigned |
| 272 | QR code of the address: not built (scripts gzip budget had 1 byte left before the merge; frontend/js/status.js startReminderWatch hook). Would go in... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/lansafe-1011.md:31 | S | unassigned |
| 273 | Tool results accumulate within a turn (already capped by TOOL_RESULT_BUDGET_CHARS, but the cap is generous at 24k characters). | docs/roadmap/BACKLOG.md:909 | S | unassigned |
| 274 | Budgeted the same way everything else is (ai/context.py), with its own share, so a long guide crowds out notes visibly rather... | docs/roadmap/BACKLOG.md:2531 | S | unassigned |
| 275 | Internal navigation is one lazy file, settings-find.js (loaded with the first open of Settings, so outside the boot gzip budget, which sits 842 bytes... | docs/roadmap/UI_MODERNISATION_PLAN.md:1162 | L | unassigned |
| 276 | Generation measured 2.0 to 2.7 s wall at load average 12 to 15 on four cores (2026-10-10); no unloaded figure was taken, and the 3 s lint budget is... | docs/roadmap/archive/agent-remaining/codemap-1010.md:8 | S | unassigned |
| 277 | found-1010: reader count ratchet (6 files outside the allowed two), five date readers and no unit reader, probe tables (23 when.resolve rows wrong on... | docs/roadmap/archive/agent-remaining/found-1010.md:7 | M | unassigned |
| 278 | The desktop webview (pywebview) and a slow machine: the 450 ms warm-up budget on a slow CPU records fewer ticks, so the playback is shorter. | docs/roadmap/archive/agent-remaining/graphfeel-1010.md:12 | S | unassigned W34: stale in part, w34-unv1-1111.md. |
| 279 | **Already fixed 2026-11-02 (tests/test_global_scope_ratchet.py passes at head).** tests/test_global_scope_ratchet.py: 278 typeof x === "function" guards against a cap of 277. | docs/roadmap/archive/agent-remaining/graphfeel-1010.md:17 | S | unassigned |
| 280 | Every wall time was taken at load average 8 to 10 on 4 cores (other sessions' browsers and servers); re-run measure-interactions.js and... | docs/roadmap/archive/agent-remaining/measure-1010.md:3 | M | unassigned |
| 281 | ~~Performance budget (import under 0.5 s, compose under 150 ms for 20 notes) and the model-dies-mid-answer route bug (routes_chat.py near 1963).~~ **W34: fixed** (w34-L1-1111.md) | docs/roadmap/archive/agent-remaining/spec39-1010.md:15 | S | unassigned |
| 282 | Tool schemas at 32,762 of 32,768 characters for a 32k window (tests/test_prompt_budget.py): the next tool added trims every description. | docs/roadmap/archive/agent-remaining/triage-1010.md:26 | S | unassigned W34: true (watch item), w34-fix1-1111.md. |
| 283 | Boot CSS 3 bytes under its cap, boot JS about 100 bytes under (tests/test_boot_budget.py, tests/test_static_compression.py): the cited-name code went... | docs/roadmap/archive/agent-remaining/triage-1010.md:27 | S | unassigned W34: true (watch item), w34-fix1-1111.md. |
| 284 | The tracks table: track 11 audio, 12 packaging (Docker image, installer optional packages), 14 learnability (docs/ROADMAP.md) | docs/ROADMAP.md:113 | L | unassigned |
| 285 | The Windows grammar worker failure not reproduced (now names its reason). | docs/roadmap/agent-remaining/OPEN.md:2253 | S | unassigned |
| 286 | No live sync between two open windows; a change shows in the other after a reload. | docs/roadmap/agent-remaining/OPEN.md:2307 | S | unassigned |
| 287 | Windows and macOS not run: both need a check by hand. On Windows a toast pressed in the Action Center after 600 s does nothing (needs a COM... | docs/roadmap/agent-remaining/OPEN.md:2364 | M | unassigned |
| 288 | The packaged helper: a Download pin per platform (URL, sha256, size) for whisper-server and a model in core/extras.py (id="captions"; the release... | docs/roadmap/agent-remaining/OPEN.md:2505 | M | unassigned |
| 289 | Utilities row 5, "every utility has ... a data-help-for popover": the timer, stopwatch and Count words are palette rows with no surface of their own... | docs/roadmap/agent-remaining/OPEN.md:2562 | M | unassigned |
| 290 | Nothing Windows was executed: splash.ps1 has never been drawn (layout, the marquee, the Details toggle, Clipboard::SetText from a hidden host, the... | docs/roadmap/agent-remaining/OPEN.md:3186 | M | unassigned |
| 291 | installer.iss's ISPP version reader (#sub, #for, RPos) compiles only on Windows; it is not verified until a Windows CI run passes. (from... | docs/roadmap/agent-remaining/OPEN.md:3321 | S | unassigned |
| 292 | The upgrade step downloads the latest release with gh and github.token; a fork or a repo without releases fails it loudly. (from... | docs/roadmap/agent-remaining/OPEN.md:3322 | S | unassigned |
| 293 | The traceback check in the smoke step reads the app's whole output; a benign logged traceback on Windows would fail it. (from... | docs/roadmap/agent-remaining/OPEN.md:3323 | S | unassigned |
| 294 | The installer's optional packages (owner, 2026-10-07: "there's no indicator for the optional packages install and I cant minimise or close the... | docs/roadmap/agent-remaining/OPEN.md:3324 | M | unassigned |
| 295 | Brief 17 (launchers, splash): agent-remaining/OPEN.md:405 names the rest of Brief 17 as open. (from briefs-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3447 | S | unassigned |
| 297 | Rule 14: /health stays the launcher's open probe (instance_lock.py, __main__.py read it unauthenticated, and it answers on the LAN); the fields are... | docs/roadmap/agent-remaining/OPEN.md:3524 | M | unassigned |
| 298 | .diff, .patch, .vb and .vbs are not in docview.CODE_SUFFIXES, so a Library import of one is refused (415); a Dockerfile has no suffix at all... | docs/roadmap/agent-remaining/OPEN.md:3536 | M | unassigned |
| 299 | Documents: the status bar shows characters, words and reading time; lines (wc -l) are counted by textCounts but shown nowhere. "find with the same... | docs/roadmap/agent-remaining/OPEN.md:3607 | M | unassigned |
| 300 | ~~502c138d5: core/netid.py (Linux /proc, macOS route/arp, Windows one PowerShell call with a route print + arp fallback; every command timed; failure...~~ **W34: fixed** (w34-L1-1111.md) | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/lansafe-1011.md:12 | M | unassigned |
| 301 | ~~cb46444e0: the gate in lanserve and the launcher, the routes, the held unlock, netbind.describe ordering; real-socket and launcher e2e tests.~~ **W34: fixed** (w34-L1-1111.md) | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/lansafe-1011.md:16 | S | unassigned |
| 302 | Update channels (stable/beta/dev): Next: the installers ship now (release.yml), so this is unblocked; api/routes_update.py... | docs/roadmap/BACKLOG.md:1715 | M | unassigned |
| 303 | MCP tool support: Pointer: WORLD_CLASS_PLAN B8 "Extensions" and PLAN.md harness row A7 ("MCP in and out"); the consume half waits... | docs/roadmap/BACKLOG.md:1845 | L | unassigned |
| 304 | Reuse the system Python's packages. Recommendation: offer it, never default it. start.sh line 1070 and start.bat line 602 run... | docs/roadmap/BACKLOG.md:4211 | L | unassigned |
| 305 | Brief 17: launchers, uninstallers and the splash made impressive (Opus): unmarked | docs/roadmap/SESSION_BRIEFS.md:549 | L | unassigned |
| 306 | Brief 40: research and placement (done; docker build, phone repro and parity-row browser checks left in research-1010) | docs/roadmap/SESSION_BRIEFS.md:1315 | S | unassigned |
| 307 | Brief 43: the expert audit and the nine probes (release 0.5 gate) | docs/roadmap/SESSION_BRIEFS.md:1406 | L | unassigned |
| 308 | Release artifact naming: <name>-<version>-<platform>-<arch>.<ext>, one scheme across every installer. INBOX 266 asked for version, platform and... | docs/roadmap/WORLD_CLASS_PLAN.md:1826 | L | unassigned |
| 309 | 0.5.0, "the notebook that thinks": the night shift's review UI, the margin reader (I2), open questions (I3), resurfacing (I4), the web clipper's... | docs/roadmap/WORLD_CLASS_PLAN.md:2435 | S | unassigned |
| 310 | 1.0.0: a stable API (B7), a screen-reader-audited UI, the installer and update path proven on clean Windows machines, and the docs complete. | docs/roadmap/WORLD_CLASS_PLAN.md:2440 | S | unassigned |
| 311 | The owner, 2026-09-23, with the Gemini/Antigravity pass on fix/gemini-fixes-5 (1e63d87, 2c3e16e): "fix and refine the changes attempted by gemini ...... | docs/roadmap/WORLD_CLASS_PLAN.md:2500 | L | unassigned |
| 312 | "Should we integrate it as a docker build and image and make it available as a docker app as well??" Recommendation: a Dockerfile and compose file... | docs/roadmap/WORLD_CLASS_PLAN.md:3105 | M | unassigned |
| 313 | "Does the mcp server work or need to be improved?? I don’t think it has been properly integrated as a feature yet." Recommendation: run the MCP... | docs/roadmap/WORLD_CLASS_PLAN.md:3109 | M | unassigned |
| 314 | "what is this app file installer?? can this app use it and is it free??" Recommendation: answer it in the Brief 40 research with the licence and... | docs/roadmap/WORLD_CLASS_PLAN.md:3113 | M | unassigned |
| 315 | The Windows firewall profile (Public blocks, Private allows) answering the first request and not the next; the launchers add no rule. | docs/roadmap/WORLD_CLASS_PLAN.md:3182 | S | unassigned |
| 316 | Add a Windows Defender Firewall rule at the opt-in (private profile only), or print the one-line netsh command when turning the switch on. | docs/roadmap/WORLD_CLASS_PLAN.md:3211 | S | unassigned |
| 317 | Docker image not built: docker is on PATH but docker info reports no daemon here. docker/Dockerfile and docker/compose.yaml are unbuilt; the first... | docs/roadmap/archive/agent-remaining/packaging-1010.md:3 | M | unassigned |
| 318 | Docker behind a reverse proxy: host_allowed answers 421 for a Host that is a name other than the container's own; a proxy forwarding... | docs/roadmap/archive/agent-remaining/packaging-1010.md:4 | M | unassigned |
| 319 | MCP: no resources (notes) or prompts (skills); startup still loads the embedder (mcp_server.serve, deps.init_app_state); stdio only, so no... | docs/roadmap/archive/agent-remaining/packaging-1010.md:5 | M | unassigned |
| 320 | ~~MCP Settings row (#mcp-config-group, renderMcpSnippet in frontend/js/skills.js) was not opened in a browser; the lints and API test pass, the layout...~~ **W34: fixed** (w34-L2r-1111.md) | docs/roadmap/archive/agent-remaining/packaging-1010.md:6 | S | unassigned |
| 321 | System site-packages: shell launcher only (env variable MEMORYMAP_SYSTEM_SITE_PACKAGES=1, not a --flag, because the flag-order lint requires... | docs/roadmap/archive/agent-remaining/packaging-1010.md:7 | S | unassigned |
| 322 | Section: Phase 11: the phone, done properly (412-line phase; many built marks, status per row unverified) | docs/roadmap/UI_MODERNISATION_PLAN.md:601 | L | unassigned |
| 323 | Section: Section 12: security review items (each names its file) | docs/roadmap/WORLD_CLASS_PLAN.md:917 | M | unassigned |
| 324 | Nav history on a phone: the popup was measured by calling openNavHistoryMenu directly (the status-bar button is not drawn at 390), so its placement... | docs/roadmap/agent-remaining/OPEN.md:1873 | S | unassigned |
| 325 | Sign-in off, not driven: the desktop window's persistent profile, a real second device on the LAN, the prompt card in dark, and whether a restored... | docs/roadmap/agent-remaining/OPEN.md:1939 | S | unassigned |
| 326 | The citation mark's touch box overlaps the lines above and below (a decision to note, not a bug): the ::after box is 44px tall around a 13px glyph... | docs/roadmap/agent-remaining/OPEN.md:2035 | M | unassigned |
| 327 | errors.js at 390 stops on its own second login check (#lock-password reads visible after the unlock); 1440, 1024 and 820 report 0 errors. | docs/roadmap/agent-remaining/OPEN.md:2120 | S | unassigned |
| 328 | Two icon-gap outliers, both judged deliberate: 10 meta chips at 3.6px (.chip.when, .map-chip) against the app's 242 controls at 6.4px, and... | docs/roadmap/agent-remaining/OPEN.md:2194 | M | unassigned |
| 329 | **Already fixed 2026-11-02 (src/tessellate/core/reminder_token.py:66-93 keeps the key in `reminder_token.key` in the data folder).** The reminder action token's key is per process (the app has no persisted signing secret): a restart ends open notifications' buttons. | docs/roadmap/agent-remaining/OPEN.md:2340 | S | unassigned |
| 330 | Timeline at 390: the On this day row moves the list down 44 px; a phone may want it folded (#timeline-recall). | docs/roadmap/agent-remaining/OPEN.md:2527 | S | unassigned |
| 331 | deepen72b.js's timeline row at 390 waits for .timeline-rows but the phone keeps the table view, so it times out (deepen72b.js:61). | docs/roadmap/agent-remaining/OPEN.md:2528 | S | unassigned |
| 332 | errors.js at 390 stops at its login: a second fill and click (errors.js:86) race an unlock slower than its fixed 2.5 s wait; reproduced on the base... | docs/roadmap/agent-remaining/OPEN.md:2543 | M | unassigned |
| 333 | companion-r5.md: the toss on a phone (a quick swipe on the companion tosses it) was not tried on a device; test_unlock_throttle_per_client.py failed... | docs/roadmap/agent-remaining/OPEN.md:2791 | M | unassigned |
| 334 | Phone selection menus and the selection bar (documents): iOS and Android draw Cut, Copy and Paste above a selection, where the bar also goes; if a... | docs/roadmap/agent-remaining/OPEN.md:2903 | S | unassigned |
| 335 | docs/CHANGELOG.md, docs/CONTRIBUTING.md and docs/SECURITY.md are mirrors that nothing reads now (the old site fetched them). Keeping or retiring them... | docs/roadmap/agent-remaining/OPEN.md:3325 | S | unassigned |
| 336 | A ring on a control in a body-level fixed sheet that touches the viewport edge (the phone Writing room's draft textarea) is treated as scroll... | docs/roadmap/agent-remaining/OPEN.md:3348 | S | unassigned |
| 337 | The icon-only chat-dock toggles are checked by text content and title only; no keyboard or screen-reader pass was run. The phone (under 600) sheet... | docs/roadmap/agent-remaining/OPEN.md:3364 | M | unassigned |
| 338 | The Focused hero is taller than before: 157px at 900 to 1920 (was 71), 278px at 390 (was 71 to 87). If the owner finds it too tall on a phone, the... | docs/roadmap/agent-remaining/OPEN.md:3370 | M | unassigned |
| 339 | Phone (390, touch): the first frames of a toggle take 50 to 80ms in headless emulation, so the first frame of the height animation can jump about 40%... | docs/roadmap/agent-remaining/OPEN.md:3391 | S | unassigned |
| 340 | Phone: a collapsed row's always-shown buttons sit in the details line's scrolled lane, off the row's right edge (right -87.8px, measured; unchanged... | docs/roadmap/agent-remaining/OPEN.md:3392 | S | unassigned |
| 341 | **Fixed 2026-10-19.** The Timeline's table view (a phone's default) has no mark column, so a meeting reads as a Note there; the feed view shows the meeting mark. (from... | docs/roadmap/agent-remaining/OPEN.md:3407 | S | unassigned |
| 342 | The phone paths through the More sheet: the agent (toggleAgentPalette() leaves the overlay hidden at 390), the Guide, the timeline and reminders were... | docs/roadmap/agent-remaining/OPEN.md:3418 | S | unassigned |
| 343 | The reminders quick-add row at 390 (not visible; the phone compose not driven). (from deepen-b-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3419 | S | unassigned |
| 344 | The palette is never shown on a phone (toggleAgentPalette goes to Chat), so its 390px notice is unmeasured by design. (from notice-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3480 | S | unassigned |
| 345 | A notice's go: { settings, focus } scrolls Settings to the control at 1440 (Back up now at y 499 of 900) but not at 390 (y 1527 of 900): the phone... | docs/roadmap/agent-remaining/OPEN.md:3659 | M | unassigned |
| 346 | 889 OCR workspace: stacked columns, 44px targets and no sideways scroll already held at 390 and 320 before this work (ocrphone.js); only the source... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/phone2-1011.md:8 | M | unassigned |
| 347 | ~~Text size "Small" puts phone tap targets under 44 px. --target-min: 2.75rem (00-tokens-shell.css:530 and the 820 band) is in rem and the root is 14.5...~~ **W34: fixed 48655b22d** (w34-L2r-1111.md) | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/scan-1011.md:8 | L | unassigned |
| 348 | ~~Other icon-only rows on the phone with no labels (not touched): the whiteboard toolbar and the selection dock; sweep with touch.js for tooltip-only...~~ **W34: fixed** (w34-L2r-1111.md) | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/phonegraph-1011.md:9 | S | unassigned |
| 349 | ~~f940fad8d: LAN port refuses a client not on this network (private, shared, link-local, this computer's own addresses, its global IPv6 /64s).~~ **W34: fixed** (w34-L1-1111.md) | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/lansafe-1011.md:10 | S | unassigned |
| 350 | The desktop webview (pywebview), the tour on a phone, voice and recordings, OCR, the web clipper (no network), update checking, backups restore... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/scan-1011.md:16 | M | unassigned W34: unverifiable, w34-L2r-1111.md. |
| 351 | ~~1b96f48cf: renderLanAddresses (one renderer, Settings and the receipt), lan-watch.js (Allow/Deny toast and bell), Settings lists and options, the...~~ **W34: fixed** (w34-L1-1111.md) | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/lansafe-1011.md:18 | S | unassigned |
| 352 | The phone's lock screen does not retry by itself after Allow: the server holds the request 45 s, then says to press Unlock again. | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/lansafe-1011.md:44 | S | unassigned W34: owner-call, w34-L1-1111.md. |
| 353 | ~~HIGH: a notebook with no password answered every device. After /auth/reset (or a restored backup with no password) the LAN listener stays up until...~~ **W34: fixed** (w34-L1-1111.md) | agent/secscan-1011:docs/roadmap/archive/agent-remaining/secscan-1011.md:23 | M | unassigned |
| 354 | ~~HIGH: /health said desktop: true to the phone, so the phone wrote exports onto the computer's disk (/files/save, any bytes, any extension) and its...~~ **W34: fixed** (w34-L1-1111.md) | agent/secscan-1011:docs/roadmap/archive/agent-remaining/secscan-1011.md:24 | M | unassigned |
| 355 | ~~MEDIUM: model and embedding-model downloads (any Ollama name or Hugging Face repo, GBs to disk) and removal from a phone. Host-only.~~ **W34: fixed** (w34-L1-1111.md) | agent/secscan-1011:docs/roadmap/archive/agent-remaining/secscan-1011.md:26 | S | unassigned |
| 356 | ~~MEDIUM: recovery-key save opened a native Save dialog on the computer from a phone; LAN switch on, certificate regenerate, password-on-open off...~~ **W34: fixed** (w34-L1-1111.md) | agent/secscan-1011:docs/roadmap/archive/agent-remaining/secscan-1011.md:27 | S | unassigned |
| 357 | **Already fixed 2026-11-02 (src/tessellate/core/security.py:662 adds Strict-Transport-Security).** LOW: no HSTS on the https port; added (https only, never on loopback). | agent/secscan-1011:docs/roadmap/archive/agent-remaining/secscan-1011.md:28 | S | unassigned |
| 358 | ~~LOW: phone Quit showed "MemoryMap has stopped" when the server had refused; now toasts the refusal. Phone full screen POSTed to the desktop toggle...~~ **W34: fixed** (w34-L1-1111.md) | agent/secscan-1011:docs/roadmap/archive/agent-remaining/secscan-1011.md:29 | L | unassigned |
| 359 | It works with no network at all. Already true and almost never said. The notebook_stats work in this session is the shape to... | docs/roadmap/BACKLOG.md:3789 | S | unassigned |
| 360 | Library verdicts to carry into Brief 35's stripping: drop networkx (write the 60 lines notebook_stats.py uses), whoosh, pint... | docs/roadmap/BACKLOG.md:4260 | M | unassigned |
| 361 | Live refresh across devices (INBOX 881, the owner 2026-10-11: "what if I make a change on my phone?? does it live update??"). A... | docs/roadmap/BACKLOG.md:4293 | M | unassigned |
| 362 | Briefs 25 to 31 (TIMELINE 1 to 4, CHAT 2 and 3, UI Phase 11 phone, DOCUMENTS 5 to 8, GRAPH 4 part two, MINDMAP 12, SKILLS D): unmarked; phases partly built per the plans | docs/roadmap/SESSION_BRIEFS.md:767 | L | unassigned |
| 363 | The status bar at 320: taken, the first way. Measured 2026-09-12, after the header was made to fit: at 320 x 844 the page still scrolled sideways... | docs/roadmap/UI_MODERNISATION_PLAN.md:886 | L | unassigned |
| 364 | The bottom tab bar exists and is five columns (#phone-tab-dock, 10-responsive.css; dockTabBar, app.js). Measured at 390, 360 and 320: five columns... | docs/roadmap/UI_MODERNISATION_PLAN.md:904 | M | unassigned |
| 365 | The sheets: one recipe, two in place, and the boundary between them is now written down (2026-09-13). openSheet builds a *modal bottom* sheet out of... | docs/roadmap/UI_MODERNISATION_PLAN.md:914 | L | unassigned |
| 366 | Gates. scratchpad/ui-sweeps/phone.js exists (2026-09-13) and holds four of them per tab at 390x844 and 430x932: no horizontal scroll (page and inside... | docs/roadmap/UI_MODERNISATION_PLAN.md:937 | L | unassigned |
| 367 | Download another model takes an Ollama name or a Hugging Face link or hf.co/ name, says what it is before anything downloads (POST /models/inspect... | docs/roadmap/UI_MODERNISATION_PLAN.md:1186 | M | unassigned |
| 368 | Density and rhythm. Cards carry 24px of padding and 17px body text at every width; on a laptop the list reads like a phone app scaled up. | docs/roadmap/WORLD_CLASS_PLAN.md:2383 | S | unassigned |
| 369 | 0.6.0, "many devices": LAN polish for tablets, local-first sync design (B6) made real, extensions (B8). | docs/roadmap/WORLD_CLASS_PLAN.md:2438 | S | unassigned |
| 370 | The owner, 2026-09-23 night, verbatim. "what is left in the world class plan?? can you poke more holes in the application for bugs, security, poor... | docs/roadmap/WORLD_CLASS_PLAN.md:2445 | L | unassigned |
| 371 | The owner, 2026-09-23, verbatim, for after 391: "poke holes in the application as in find bugs, security flaws places where there is unintuitive... | docs/roadmap/WORLD_CLASS_PLAN.md:2533 | L | unassigned |
| 372 | "this didnt work "https://192.168.0.107:8443", on my phone it said the page was unsecure, and then I clicked continue, and it said "safari can't open... | docs/roadmap/WORLD_CLASS_PLAN.md:3088 | M | unassigned |
| 373 | "it says the connection isnt secure and the page cant be reached" / "on brave browser on my phone" Recommendation: the same trust flow as the entry... | docs/roadmap/WORLD_CLASS_PLAN.md:3090 | M | unassigned |
| 374 | "Also I still cant access the application on my phone, the connection just doesn’t go through and there are security issues with a not trustworthy... | docs/roadmap/WORLD_CLASS_PLAN.md:3092 | M | unassigned |
| 375 | "is it possible to customise the domain name on the network accessible url??" Recommendation: an optional local host name for the LAN address (a mDNS... | docs/roadmap/WORLD_CLASS_PLAN.md:3103 | M | unassigned |
| 376 | "I want to deep analyse this repo and see if we can cake a use/replicate/take a lot from it https://github.com/haifengl/smile.git" Recommendation... | docs/roadmap/WORLD_CLASS_PLAN.md:3128 | M | unassigned |
| 377 | TLS 1.2 and 1.3 both negotiate (TLS_AES_256_GCM_SHA384, a 256-bit key); no ALPN, so HTTP/1.1 only. Neither is a plausible cause. | docs/roadmap/WORLD_CLASS_PLAN.md:3146 | S | unassigned |
| 378 | The certificate names the LAN address as an IP SAN and a request to a name it does not carry fails (curl: no alternative certificate subject name... | docs/roadmap/WORLD_CLASS_PLAN.md:3148 | M | unassigned |
| 379 | The leaf is self-issued, 825 days, with SAN, basicConstraints and EKU serverAuth but no keyUsage. Apple limits certificates that chain to a trusted... | docs/roadmap/WORLD_CLASS_PLAN.md:3156 | M | unassigned |
| 380 | The front end uses NDJSON over fetch, not WebSocket or EventSource (capture-ask.js line 2544, settings.js line 1018), so a WebSocket over an... | docs/roadmap/WORLD_CLASS_PLAN.md:3160 | M | unassigned |
| 381 | HostCheckMiddleware lets any numeric Host through, so the rebinding guard is not refusing the phone. | docs/roadmap/WORLD_CLASS_PLAN.md:3166 | S | unassigned |
| 382 | The phone's per-connection trust: Safari opens several parallel connections and a clicked-through exception on a self-signed leaf is per-session, so... | docs/roadmap/WORLD_CLASS_PLAN.md:3172 | M | unassigned |
| 383 | A stale name (above), after a DHCP change, shown the same way as a plain untrusted warning. | docs/roadmap/WORLD_CLASS_PLAN.md:3176 | S | unassigned |
| 384 | AdGuard on the phone: a DNS profile does not touch an IP address, but the AdGuard app's local VPN mode and iOS 14's Local Network permission for... | docs/roadmap/WORLD_CLASS_PLAN.md:3178 | M | unassigned |
| 385 | A local CA, mkcert style, made with cryptography (already a dependency): an EC P-256 CA kept in lan-tls/ (0600), a leaf signed by it for 397 days... | docs/roadmap/WORLD_CLASS_PLAN.md:3186 | S | unassigned |
| 386 | Settings, Other devices, "Trust this notebook on your phone": a QR code to http://<ip>:8000/lan/trust (a plain-http route that serves only the public... | docs/roadmap/WORLD_CLASS_PLAN.md:3192 | M | unassigned |
| 387 | A plain-http option for the home network, off by default, with the password warning in one sentence ("anyone on this Wi-Fi can read it") and the... | docs/roadmap/WORLD_CLASS_PLAN.md:3201 | M | unassigned |
| 388 | A diagnostics line in Settings, Network: the addresses now, the names the certificate carries (green when every address is covered, amber with... | docs/roadmap/WORLD_CLASS_PLAN.md:3206 | M | unassigned |
| 389 | (Odysseus, fourth read 2026-10-10) | docs/roadmap/WORLD_CLASS_PLAN.md:3215 | S | unassigned |
| 390 | Staged gate: ruff check . fails on vendored src/memorymap/vendor/whoosh (1,140 findings, same on the base checkout); test_plan_hygiene (vendor... | docs/roadmap/archive/agent-remaining/codemap-1010.md:9 | M | unassigned |
| 391 | UML and "network" libraries. Upstream has no UML stencil library (UML is drawn by Shapes.js classes); networks.xml stood in for network. The... | docs/roadmap/archive/agent-remaining/drawio-1010.md:38 | S | unassigned |
| 392 | Cold boot excludes the service worker and a warm HTTP cache; no phone-width run. | docs/roadmap/archive/agent-remaining/measure-1010.md:10 | S | unassigned |
| 393 | Triage-agent lints still red on this branch: README tool count (67) and the networkx conflict marker. | docs/roadmap/archive/agent-remaining/packaging-1010.md:8 | S | unassigned |
| 394 | bash scripts/gate.sh --staged fails here on lints that predate this work: ruff over src/memorymap/vendor/ (1140 errors, whoosh), the networkx... | docs/roadmap/archive/agent-remaining/proofing-1010.md:6 | S | unassigned |
| 395 | Road to 1.0: 0.5 Reliable, 0.6 Engine, 0.7 Surfaces, 0.8 Design, 0.9 Public beta, 1.0 exit criteria (docs/ROADMAP.md) | docs/ROADMAP.md:171 | L | unassigned |
| 396 | Section: Phase 5: the composer after INBOX 725 (open) | docs/roadmap/CHAT_PLAN.md:385 | L | unassigned |
| 397 | Section: Phase 6: the deterministic engine, steps 1 to 10, measured gates (Brief 39; spec39 lists untested decisions) | docs/roadmap/CHAT_PLAN.md:405 | L | unassigned |
| 398 | Section: The deterministic foundation F0 to F5 phases with gates and its Not verified list | docs/roadmap/CHAT_PLAN.md:1565 | L | unassigned |
| 399 | Attach: at 390 #attach-image reads a 999px radius while #attach-note reads 4.8px in the chat composer row (the owner's 841 asked for one corner; only... | docs/roadmap/agent-remaining/OPEN.md:1870 | M | unassigned |
| 400 | The guide topic ask-chat is at 1916 of 1919 characters (tests/test_help_controls.py), so Agent-with-no-model could not be named in the Guide without... | docs/roadmap/agent-remaining/OPEN.md:1871 | M | unassigned |
| 401 | Ask's answer object was measured on the offline branch only. The sweep runs against a server with no model, so sentences was empty in every... | docs/roadmap/agent-remaining/OPEN.md:2042 | M | unassigned |
| 402 | The evals marker and its fixture set (Brief 13's done-when). At least 80% of the built-in skills complete with zero invalid tool calls under... | docs/roadmap/agent-remaining/OPEN.md:2061 | L | unassigned |
| 403 | Not engine-readable, left out of the fixture: "corder" (corner; a one-letter swap in a six-letter word is refused on purpose, it reads "coder")... | docs/roadmap/agent-remaining/OPEN.md:2212 | S | unassigned |
| 404 | The Guide's no-model system answer (help_chat.system_answer) does not say "I took that to mean"; only composer.compose answers do. | docs/roadmap/agent-remaining/OPEN.md:2233 | S | unassigned |
| 405 | A real word missing from both word lists can be mis-repaired; add it to common_words.py and LEFT_ALONE. | docs/roadmap/agent-remaining/OPEN.md:2234 | S | unassigned |
| 406 | The asking-word nearest rule turns an all-caps token ("NASA") into "has" unless the whole text is capitals. | docs/roadmap/agent-remaining/OPEN.md:2235 | S | unassigned |
| 407 | Readings guessed: "liks" (like), "mut" (must), "odf" (of), "ro" (or). Brief 90 is standing: each new prompt's typos join owner_typos.json. | docs/roadmap/agent-remaining/OPEN.md:2236 | S | unassigned |
| 408 | **Fixed 2026-10-19.** Mechanical: the header's six buttons lose 0.5px of their ring at the window top; the Library active sub-tab's border is cut 2.3px at 390; the chat... | docs/roadmap/agent-remaining/OPEN.md:2275 | S | unassigned |
| 409 | "What do I know about X" still quotes one sentence unless its notes are tagged with the subject (the 725 and 741 evals pin it). | docs/roadmap/agent-remaining/OPEN.md:2440 | S | unassigned |
| 410 | Single-note answers still end with "[your note, date]"; some next-question chips repeat the subject; an overview over more than 24 notes should say... | docs/roadmap/agent-remaining/OPEN.md:2441 | S | unassigned |
| 411 | Send stays off the undo bar (Ctrl+Z in the composer is text undo); recommended as is. | docs/roadmap/agent-remaining/OPEN.md:2448 | S | unassigned |
| 412 | Needle with the server up but no model leaves Agent greyed: tools_engine is reported only when the server is down (routes_chat.py ~2534). | docs/roadmap/agent-remaining/OPEN.md:2472 | L | unassigned |
| 413 | The document menu's "Translate this passage..." still hands the passage to chat, not the offline engine. | docs/roadmap/agent-remaining/OPEN.md:2491 | L | unassigned |
| 414 | **Already fixed 2026-11-02 (src/tessellate/ai/recognise.py:796 `_add_months` takes `day_of_month` and returns to the 31st).** A monthly repeat from the 31st lands on the 28th in February and stays there (recognise.py _add_months). | docs/roadmap/agent-remaining/OPEN.md:2530 | S | unassigned |
| 415 | Statistics row 4 (Brief 37): the page's "not used lately" list (86 on the fixture) is the feed the weekly offer wants; not wired. | docs/roadmap/agent-remaining/OPEN.md:2564 | S | unassigned |
| 416 | "new ways to do and output info" (INBOX 758): the Ask box ignores the chart event (capture-ask.js Ask handlers, ~3065); only the Chat tab draws it... | docs/roadmap/agent-remaining/OPEN.md:2608 | S | unassigned |
| 417 | The Guide's "how do I set a reminder" first line is the topic's first matching sentence ("The Reminders tab groups items..."), not the step that sets... | docs/roadmap/agent-remaining/OPEN.md:2611 | M | unassigned |
| 418 | Guide rows 4 to 6 (CHAT_PLAN "The Guide" table): trust-surface topics, the weekly unused feature, typos through the word list (VC15). | docs/roadmap/agent-remaining/OPEN.md:2613 | S | unassigned |
| 419 | WORLD_CLASS_PLAN 9's dev-only llama.cpp runner is the blocker behind four open items: the evals marker, Skills Phase D's central claim, the retrieval... | docs/roadmap/agent-remaining/OPEN.md:2723 | L | unassigned |
| 420 | A check that cannot tell "nothing matched" from "labels are broken" cries wolf on every small fixture. Two of graph2.js's five failures were exactly... | docs/roadmap/agent-remaining/OPEN.md:2734 | S | unassigned |
| 421 | IME composition inside the editor engine, and the fallback path reached by a genuinely blocked request rather than by setting docCmBroken by hand.... | docs/roadmap/agent-remaining/OPEN.md:3241 | L | unassigned |
| 422 | Real-browser text metrics beyond Chromium. The wrap sweep measured 420 to 2200px at the app's own 95% --zoom; a different engine could shift an exact... | docs/roadmap/agent-remaining/OPEN.md:3264 | L | unassigned |
| 423 | With a model, the composer shows "Filed under Work (100% sure)" for a small model's pick (a dentist appointment); the certainty shown for a small... | docs/roadmap/agent-remaining/OPEN.md:3304 | S | unassigned |
| 424 | Found: one_line for "when is the harbor launch?" quotes the Q4 roadmap rather than the dated sentence; the compose grounding rows lack it. (from... | docs/roadmap/agent-remaining/OPEN.md:3349 | S | unassigned |
| 425 | The eval numbers for the whole voice track (before and after) were not reported: run tests/_composer_eval.py and record them. (from... | docs/roadmap/agent-remaining/OPEN.md:3351 | S | unassigned |
| 426 | Browser check of Ask and Chat with no model at 1440 and 390, light and dark: the "Did you mean" chip and the clarifying question. The sweep... | docs/roadmap/agent-remaining/OPEN.md:3352 | M | unassigned |
| 427 | The noisy-question set's coverage (owner: "any and ALL typos ... all slang"): what is still missed, from the eval. (from composer-voice-1006.md) | docs/roadmap/agent-remaining/OPEN.md:3353 | S | unassigned |
| 428 | Professional variants for the next-question chips and the citation phrases (mention_*, lists, echo), and other languages' wrappers. (from... | docs/roadmap/agent-remaining/OPEN.md:3354 | S | unassigned |
| 429 | The Settings voice row was checked in Chromium on the light theme only at 1440 and 390; dark not run. (from composer-voice-1006.md) | docs/roadmap/agent-remaining/OPEN.md:3355 | S | unassigned |
| 430 | **No change needed 2026-10-19:** the scope is only ever set by the Questions view's own Ask button, in the same init that wires Clear, so Clear is always wired while the scope shows. Ask's "Ask all notes" (#ask-scope-clear) is wired only once the Questions view has been opened, so the scope is only set from there (pre-existing).... | docs/roadmap/agent-remaining/OPEN.md:3357 | S | unassigned |
| 431 | At 390 the Ask head's model picker sits on its own short line (224px of 330), pre-existing. (from composer688-1006.md) | docs/roadmap/agent-remaining/OPEN.md:3358 | S | unassigned |
| 432 | Clicking an Ask chip was not driven: the sweep's button selector missed the chip element. (from composer725-1006.md) | docs/roadmap/agent-remaining/OPEN.md:3360 | S | unassigned |
| 433 | Link reasons from the composer (owner: "can the composer be user to write better link reasons other than just similar in meaning??"): not started.... | docs/roadmap/agent-remaining/OPEN.md:3361 | M | unassigned |
| 434 | ocrflow.js still reads #ocr-engine as a line and clicks #ocr-more; it was not re-run, and its engine checks may need the popover opened first. The... | docs/roadmap/agent-remaining/OPEN.md:3377 | L | unassigned |
| 435 | The fixture is 96 notes (the seed ran twice), not 48. (from deepen-b-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3426 | S | unassigned |
| 436 | Ask cannot show a relevant map as a map. Decision taken: retrieval is notes only (a map's entry text is its title, so it grounds nothing). Owner's... | docs/roadmap/agent-remaining/OPEN.md:3430 | M | unassigned |
| 437 | Brief 13 (verifier): agent-remaining/OPEN.md:189 still names Brief 13's evals marker and fixture set as open. (from briefs-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3444 | S | unassigned |
| 438 | The lexicon (decision 7) costs one note in the online simulation (0.521 to 0.510, scratchpad/filing-tools/online.py); the fixture has no category... | docs/roadmap/agent-remaining/OPEN.md:3468 | S | unassigned |
| 439 | Decision 9 (the 30 context rules, 50 acceptance fixtures): not started; taxonomy.context_rules() and... | docs/roadmap/agent-remaining/OPEN.md:3469 | S | unassigned |
| 440 | Blind panel (decision 40): the owner's rating against the 1 to 3B model; not runnable by an agent. | docs/roadmap/agent-remaining/OPEN.md:3486 | S | unassigned |
| 441 | P10 days until a note's date ("how many days until the dentist"): utilities.until_subject (src/memorymap/ai/utilities.py:313) finds the subject... | docs/roadmap/agent-remaining/OPEN.md:3487 | S | unassigned |
| 442 | P12 a list filtered by category or tag ("list my work notes"): composer._filtered (src/memorymap/ai/composer.py:3155) filters by tag and source kind... | docs/roadmap/agent-remaining/OPEN.md:3489 | S | unassigned |
| 443 | P15 a lead-in chosen after the parts: the compare opener is still chosen first. | docs/roadmap/agent-remaining/OPEN.md:3491 | S | unassigned |
| 444 | P16 a note's open checklist items for "what is still open on X". | docs/roadmap/agent-remaining/OPEN.md:3492 | S | unassigned |
| 445 | Captions: the composer reads them as note content; keyword search finds them as the picture's own row (src/memorymap/search/index.py:793), not as its... | docs/roadmap/agent-remaining/OPEN.md:3495 | S | unassigned |
| 446 | Dates like 3/4 read day first (when._date_phrase, src/memorymap/ai/when.py:420); no locale order. | docs/roadmap/agent-remaining/OPEN.md:3496 | S | unassigned |
| 447 | Not seen in a browser: the web sources list with a real search engine; contrast sweeps over .said and the act card. | docs/roadmap/agent-remaining/OPEN.md:3497 | L | unassigned |
| 448 | Polarity in the fact layer: dropped by decision 30's own condition (no feature uses it). | docs/roadmap/agent-remaining/OPEN.md:3498 | S | unassigned |
| 449 | INBOX 694 part 1, "the bottom of these pills gets cut off": not reproduced at DPR 1 (Ask/Agent and Settings .seg: each segment 1 px inside the 32 px... | docs/roadmap/agent-remaining/OPEN.md:3506 | S | unassigned |
| 450 | INBOX 744 (b) and (c), "it didn mention other matching records": composer and grounding work (composer*.py, renderAnswerGrounding), off this agent's... | docs/roadmap/agent-remaining/OPEN.md:3510 | S | unassigned |
| 451 | Start SearXNG "takes a while": not reproduced (status 21 to 101 ms, chat.js:1031 setWebSearxngRunning); a search that failed should retry by itself... | docs/roadmap/agent-remaining/OPEN.md:3511 | L | unassigned |
| 452 | Citation hover, the composer and captions in retrieval (Brief 39) and the density items (Brief 41) are owned elsewhere. | docs/roadmap/agent-remaining/OPEN.md:3513 | S | unassigned |
| 453 | ai/composer.py _DATE_CUE (about line 380) and its second date pattern (about 933) still compile date words; replace with recognise.recognise(...)... | docs/roadmap/agent-remaining/OPEN.md:3568 | M | unassigned |
| 454 | entry/timewords.py keeps its own weekday and number tables (the plan's second allowed reader, for stored precision). Brief 68 decides whether find... | docs/roadmap/agent-remaining/OPEN.md:3569 | S | unassigned |
| 455 | ai/factgraph.py _QUANTITY still reads counts of things ("3 sets", "5 people"); a "count" kind (number plus plural noun) in recognise would let it... | docs/roadmap/agent-remaining/OPEN.md:3570 | S | unassigned |
| 456 | **Built w11-1110 (B42).** search/query.py before:/after: stay ISO only (test_an_unreadable_date_invents_nothing holds it); before:tuesday is one call to recognise.span if the... | docs/roadmap/agent-remaining/OPEN.md:3571 | S | unassigned |
| 457 | "last week" is the last seven days in search and the previous Monday to Sunday in recognise; both written down, the Reading says the search's window.... | docs/roadmap/agent-remaining/OPEN.md:3572 | S | unassigned |
| 458 | when.resolve("in march"), "march", "q4" give the next one at 09:00 (a reminder is never in the past); the past one comes from when.window and... | docs/roadmap/agent-remaining/OPEN.md:3573 | S | unassigned |
| 459 | "on my birthday" reads only with a stored birthday (context["birthday"], birthday= on /read); no setting holds one yet. [f1-1010] | docs/roadmap/agent-remaining/OPEN.md:3574 | S | unassigned |
| 460 | Quick add is 56 of 60 on tests/fixtures/composer/quickadd_1010.json measured before F1's four fixes landed; re-run scratchpad/ui-sweeps/quickadd.js... | docs/roadmap/agent-remaining/OPEN.md:3576 | S | unassigned |
| 461 | A reminder with no time said is guessed as tomorrow at 9, shown "(no time was said)" (commands.py, when.resolve("tomorrow")); decisions 48 and 50 say... | docs/roadmap/agent-remaining/OPEN.md:3587 | M | unassigned |
| 462 | Ask draws no Confirm and Not right: capture-ask.js keeps onGrounding's insights unread though the route sends them (decision 60 lists chat, Tidy and... | docs/roadmap/agent-remaining/OPEN.md:3588 | S | unassigned |
| 463 | tag: with words still filters after the keyword pass's 200 candidates (engine.search, the wanted_tags block), so a common word plus a rare tag can... | docs/roadmap/agent-remaining/OPEN.md:3597 | L | unassigned |
| 465 | Note editor: offers on the Edit form are wired (note-edit-panels.js after li.append(surface, ...)) but measured only on the Capture composer; the... | docs/roadmap/agent-remaining/OPEN.md:3604 | M | unassigned |
| 466 | Filters: "last week" is the last seven days here (the search's meaning) and the Monday to Sunday week in recognise; F1's owner decision row still... | docs/roadmap/agent-remaining/OPEN.md:3610 | S | unassigned |
| 467 | Import: people and places are named in the summary only; they are not written as tags or entities (the save's own extraction runs as before).... | docs/roadmap/agent-remaining/OPEN.md:3612 | M | unassigned |
| 468 | Library boxes (Library filter, graph filter) are not on the meaning layer: they search notes through /read/filter and the search engine, whose... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/meaning94-1011.md:6 | L | unassigned W34: true, w34-L2r-1111.md. |
| 469 | Autocorrect's table takes Brief 90's owner typos by hand (73 pairs read from agent/typos90*-1011's owner_typos.json, 47 kept: the rest are real... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/meaning94-1011.md:8 | S | unassigned |
| 470 | 856: the owner's exact element ("an Ask question link") was not reproduced. scratchpad/ui-sweeps/hoverradius.js measured 0 square hover grounds... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/ownerfix3-1011.md:14 | M | unassigned |
| 471 | Re-ranking with a small cross-encoder over the top-20, behind a setting. Next: nothing in src/ re-ranks (checked 2026-10-05); the... | docs/roadmap/BACKLOG.md:866 | L | unassigned |
| 472 | An eval/benchmark harness tied to changes here. Pointer: WORLD_CLASS_PLAN B5 "Evals as fixtures" and I8; tests/eval/, pytest -m... | docs/roadmap/BACKLOG.md:878 | L | unassigned |
| 473 | Re-rank the top N with the utility model. Next: same item as section 11's "Re-ranking" (nothing re-ranks in src/); the seam is... | docs/roadmap/BACKLOG.md:2404 | L | unassigned |
| 474 | Selected, not always-on. Attached explicitly in the composer or the document editor, and *offered* by the same deterministic... | docs/roadmap/BACKLOG.md:2525 | M | unassigned |
| 475 | Every Mermaid kind renders where Markdown renders: documents, chat, Ask answers, note previews and the print view: flowchart... | docs/roadmap/BACKLOG.md:2597 | M | unassigned |
| 476 | The AI: steps 5 and 6 above use the full renderer for the preview; the agent gets a render_mermaid check tool so it can see its... | docs/roadmap/BACKLOG.md:2611 | L | unassigned |
| 477 | §88.4 items 1, 2 (ROADMAP.md) are the reason "jump between notes" is already partly real: graph_expansion() walks linked... | docs/roadmap/BACKLOG.md:2847 | M | unassigned |
| 478 | Chasing Notion's block editor. Documents has four views and a real toolbar. Deciding *whether the note composer converges with... | docs/roadmap/BACKLOG.md:3892 | S | unassigned |
| 479 | The owner, 2026-09-21, verbatim: "in the ask subtab in notes, make sure there are appropriate gaps between uploaded files and attachments and the... | docs/roadmap/CHAT_PLAN.md:675 | S | unassigned |
| 480 | The owner, 2026-09-21, verbatim: "there's no generating animation while the model is thinking and streaming in the ask tab either." | docs/roadmap/CHAT_PLAN.md:679 | S | unassigned |
| 481 | The owner, 2026-09-21, verbatim: "can the notes in the matching records that appear in the ask tab be numbered accordingly to match the inline... | docs/roadmap/CHAT_PLAN.md:682 | S | unassigned |
| 482 | The owner, 2026-09-21, verbatim: "fix the ui of this sources button in the ask tab." | docs/roadmap/CHAT_PLAN.md:686 | S | unassigned |
| 483 | The composer assists the model, never replaces it: when a model is running it is the chat bot; the composer supplies the grounded material (the... | docs/roadmap/CHAT_PLAN.md:757 | M | unassigned |
| 484 | The composer writes for the model and the agent, not only for the person (the owner, 2026-10-06, after reading one of this harness's own templated... | docs/roadmap/CHAT_PLAN.md:775 | L | unassigned |
| 485 | A notebook that reads as written for you (the owner, 2026-10-06, verbatim: "the composer could even be used to customise notifications, make the... | docs/roadmap/CHAT_PLAN.md:794 | M | unassigned |
| 486 | No answer is said plainly. "Nothing here says that. The closest is X", plus a suggested question the person could answer with a note. | docs/roadmap/CHAT_PLAN.md:821 | S | unassigned |
| 487 | The bar is all four, each measured: a blind test of composer answers against a 1 to 3B local model on the person's own notes; zero wrong facts, every... | docs/roadmap/CHAT_PLAN.md:823 | M | unassigned |
| 488 | Notes are a mix: the eval weights short jottings (rewrites, joining) and long writing (summaries, choosing the sentence) equally. | docs/roadmap/CHAT_PLAN.md:832 | L | unassigned |
| 489 | "the "start searxng" button doesnt appear for a while" Recommendation: show the SearXNG start control as soon as the web engine is found down, not... | docs/roadmap/CHAT_PLAN.md:851 | L | unassigned |
| 490 | "I pressed the "ask about this" button and it put it in the chat but I was on "ask" mode, shouldnt it have been auto put on "agent"??"... | docs/roadmap/CHAT_PLAN.md:855 | M | unassigned |
| 491 | "I tried to ask for more info from the retrieved website in the previous prompt and it just straight up ignored me and started talking about my... | docs/roadmap/CHAT_PLAN.md:859 | M | unassigned |
| 492 | "not every chat response needs to be related to notes if it is othe rthings about the application." Recommendation: questions about the app are... | docs/roadmap/CHAT_PLAN.md:863 | L | unassigned |
| 493 | "a whitebaord showed as a note in the notes ask subtab matching records column" Recommendation: each match carries its kind (board, map, note... | docs/roadmap/CHAT_PLAN.md:867 | S | unassigned |
| 494 | "I pressed show them, but it just navigated me to the Ask subtab on the notes tab as that was what I was just on in the notes tab and not to the "you... | docs/roadmap/CHAT_PLAN.md:875 | M | unassigned |
| 495 | "Note captions arent counted as note content??" Recommendation: captions join the retrieval text and the fact layer, with a fixture that a... | docs/roadmap/CHAT_PLAN.md:879 | S | unassigned |
| 496 | "I think a lot of composer responses start with "ah,"??" Recommendation: the opener set loses the repeated "ah," and is checked by openers_distinct... | docs/roadmap/CHAT_PLAN.md:885 | M | unassigned |
| 497 | "The composer is shit and I don’t like it, it needs soooo much improvement" / "Still ass composer" Recommendation: this is the composer quality bar... | docs/roadmap/CHAT_PLAN.md:887 | M | unassigned |
| 498 | "There's no way to clear your ask history" Recommendation: add clear-all to the Ask history, with the same control as the destination history. Also... | docs/roadmap/CHAT_PLAN.md:891 | S | unassigned |
| 499 | "Do plan and web search work with the composer?? if not we should disable the plan button and if the user asks the composer to search the web, it can... | docs/roadmap/CHAT_PLAN.md:893 | M | unassigned |
| 500 | "Composer chat messages in the chat and other interfaces should say if the composer or a specific ai model generated it" Recommendation: every... | docs/roadmap/CHAT_PLAN.md:898 | S | unassigned |
| 501 | "Composer responses just appear, I think there should be an animation or smooth transition." Recommendation: a short fade-in with a reduced-motion... | docs/roadmap/CHAT_PLAN.md:900 | M | unassigned |
| 502 | "Ask subtab responses need to have better hierarchy with their sentence connectors." Recommendation: headings, paragraph breaks and connectors are... | docs/roadmap/CHAT_PLAN.md:902 | M | unassigned |
| 503 | "It just uses arrows to go between key sentences and doesn’t join or smoothly write it out at all" Recommendation: the realiser joins key sentences... | docs/roadmap/CHAT_PLAN.md:904 | M | unassigned |
| 504 | "Also the composer should probably use better md rendering and structuring, quotation marks, as well as alter personal words used in notes like "my"... | docs/roadmap/CHAT_PLAN.md:906 | M | unassigned |
| 505 | "Also the composer should note timewords so it can be like, last Friday you did this… etc" Recommendation: time words in the question and the notes... | docs/roadmap/CHAT_PLAN.md:908 | M | unassigned |
| 506 | "I want the composer to be more like a chatbot and not just somenthing that reads out my notes,as I can clearly see them in the right column"... | docs/roadmap/CHAT_PLAN.md:910 | M | unassigned |
| 507 | "also when I use the composer and press "ask this question again" to get a new ai response, the composer doesnt change it up. I want the composer to... | docs/roadmap/CHAT_PLAN.md:912 | M | unassigned |
| 508 | "the composer should have more insights, some social and conversational aspects, more response variation. more stuff than just lkisting my notes back... | docs/roadmap/CHAT_PLAN.md:914 | L | unassigned |
| 509 | "t needs more social and world and word understanding, needs to understand mroe typos, needs better and mroe verything" Recommendation: extend the... | docs/roadmap/CHAT_PLAN.md:916 | S | unassigned |
| 510 | "this is confusing?? I want a better chatbot. is there any more magic we can do?" Recommendation: the bubble explains which engine answered and what... | docs/roadmap/CHAT_PLAN.md:918 | L | unassigned |
| 511 | "Composer doesn’t know it is atlas?? Should the composer be distinct from atlas??" Recommendation: one voice, named Atlas, with the composer as its... | docs/roadmap/CHAT_PLAN.md:920 | L | unassigned |
| 512 | "sounds good. but only if the suer has web search and the tools enabled." (the owner's feedback in the Gemini thread, on the web-aware composer)... | docs/roadmap/CHAT_PLAN.md:922 | M | unassigned |
| 513 | "I just want it to do its job, and I dont want to change the ai, just improve and fix the deterministic composer." (the owner's feedback in the... | docs/roadmap/CHAT_PLAN.md:924 | M | unassigned |
| 514 | "I don’t like the genz version, remove It and expand the composer more. It needs a lot of fixing, expanding, and refining." Recommendation: remove... | docs/roadmap/CHAT_PLAN.md:926 | M | unassigned |
| 515 | "there should be a retry button for failed web searches and/or a button to auto retry when searxng or another engine is available." Recommendation: a... | docs/roadmap/CHAT_PLAN.md:931 | L | unassigned |
| 516 | "I want the composer to be more integrated, have more abilities, utilities, functions, and more." Recommendation: the composer's tool list is the... | docs/roadmap/CHAT_PLAN.md:942 | L | unassigned |
| 517 | "could it have insights?? like with my note about hitting some golf balls after work could imply I may enjoy playing golf or have it as a hobby??... | docs/roadmap/CHAT_PLAN.md:944 | L | unassigned |
| 518 | "can you improve on and expand it further?? cover any flaws, optimise, enhance. impress me." Recommendation: this is the composer's brief at large... | docs/roadmap/CHAT_PLAN.md:946 | M | unassigned |
| 519 | 744 (b) and (c), the unquoted sources and the alarm notice. "it didn mention other matching records i dont think". (b) the composer names the sources... | docs/roadmap/CHAT_PLAN.md:1758 | M | unassigned |
| 520 | INBOX 725 composer: make answers feel like a chatbot (CHAT_PLAN Phase 5 and 6, Briefs 39, 65 to 68) | docs/roadmap/INBOX.md:48 | L | unassigned |
| 521 | INBOX 730 composer files new notes by meaning, keyword and embeddings: held-out accuracy and a one-line explanation per filing (Brief 39b) | docs/roadmap/INBOX.md:57 | M | unassigned |
| 522 | INBOX 741 composer writing quality: speak the content directly with the citation as a marker (CHAT_PLAN Phase 6, Brief 39 realiser) | docs/roadmap/INBOX.md:90 | M | unassigned |
| 523 | INBOX 810 personas row actions styled like the shortcuts Change button; What it learned checks context (joke notes); composer as the app's Siri (maths, timezones, web panel, ghost text, audit the learned store) | docs/roadmap/INBOX.md:199 | L | unassigned |
| 524 | INBOX 812 Ask: answer reads like notes not prose; three citation marks per line; sources shown three times; empty badges while loading; Atlas over the answer | docs/roadmap/INBOX.md:234 | L | unassigned |
| 525 | INBOX placed log: INBOX 899 (composer and agents pull from time words) sent to atlas; 900 folded into 896; 901 (show more and less awkward on wide panes) placed | docs/roadmap/INBOX.md:274 | S | unassigned |
| 526 | INBOX placed log: INBOX 867 to 870 placed as Briefs 102, 103, 104 and a composer opening/joining row | docs/roadmap/INBOX.md:281 | S | unassigned |
| 527 | Briefs 35 to 38 (Gemini triage, whiteboard and mind map, Chat/Ask/first run bugs, graph topics and note properties): unmarked; triage built (triage-1010) | docs/roadmap/SESSION_BRIEFS.md:1247 | L | unassigned |
| 528 | One new section, searchindex ("Search and index"): the search engine, the search index and the search relevance floor, which were in Models (two) and... | docs/roadmap/UI_MODERNISATION_PLAN.md:1144 | L | unassigned |
| 529 | INBOX 761, mind maps listed as notes. The Ask results show a mind map as an Uncategorised note card; check every reader of notes (Ask, Notes, search... | docs/roadmap/UI_MODERNISATION_PLAN.md:1239 | M | unassigned |
| 530 | "very messy" Recommendation: the owner has not named the surface; ask for the screen when the next session starts, and meanwhile run the Brief 41... | docs/roadmap/UI_MODERNISATION_PLAN.md:1266 | S | unassigned |
| 531 | "Also can things still work with all the similarity stuff for the composer and filing and other stuff if sentence-transformers isnt installed??"... | docs/roadmap/WORLD_CLASS_PLAN.md:3096 | M | unassigned |
| 532 | ~~Section 0 finding 1 is unfixed: Gemini-branch utilities are discarded by if not out.rows in ai/composer.py (~2706 to 2795). Owner: "I want the...~~ **W34: fixed** (w34-L1-1111.md) | docs/roadmap/archive/agent-remaining/assistant-1010.md:6 | M | unassigned |
| 533 | ~~Finding 2 unfixed: the translate rule at ai/composer.py:292 ends in to\s+([a-zA-Z]+)\b and swallows "what do I need to buy", "how to cook rice"...~~ **W34: fixed** (w34-L1-1111.md) | docs/roadmap/archive/agent-remaining/assistant-1010.md:7 | S | unassigned |
| 534 | ~~Finding 3 unfixed: "summarise my gym notes" raises UnboundLocalError on sides (ai/composer.py ~2795).~~ **W34: fixed** (w34-L1-1111.md) | docs/roadmap/archive/agent-remaining/assistant-1010.md:8 | S | unassigned |
| 535 | ~~when.resolve("last friday") returns the next Friday (ai/when.py resolve); recall must use entry/timewords.find, which is right; "since March", "the...~~ **W34: fixed** (w34-L1-1111.md) | docs/roadmap/archive/agent-remaining/assistant-1010.md:9 | S | unassigned |
| 536 | ~~None of the 16 eval fixtures in section 4 exist; the five in decision 40 and the eight proposed ones need their rows written (645 rows), and the...~~ **W34: fixed** (w34-L1-1111.md) | docs/roadmap/archive/agent-remaining/assistant-1010.md:11 | S | unassigned |
| 537 | Sources whose pages did not state a mechanism, to read from their repositories if the detail matters: Mycroft Adapt's confidence and one_of and... | docs/roadmap/archive/agent-remaining/assistant-1010.md:14 | S | unassigned W34: owner-call (tracked in the plans), w34-L1-1111.md. |
| 538 | Found, not fixed: ai/tool_summary.py is named by commands.py on origin/wip/composer-acts and does not exist on this branch; entry.query entity: finds... | docs/roadmap/archive/agent-remaining/assistant-1010.md:16 | M | unassigned |
| 539 | engine-probe-1010: P1 to P16 probe bugs (word-boundary match, empty social answers, route order, count over retrieval); re-run the probe to see which... | docs/roadmap/archive/agent-remaining/engine-probe-1010.md:7 | M | unassigned W34: true (part), w34-L2r-1111.md. |
| 540 | Search latency of the engine alone (without HTTP and background work) is not isolated; GET /search p50 1.8 to 5.0 s is the loaded figure. A trivial... | docs/roadmap/archive/agent-remaining/measure-1010.md:4 | L | unassigned |
| 541 | Decision 34: lead_in_repeats and openers_distinct over a 20-turn session need the eval fixtures (decision 40). | docs/roadmap/archive/agent-remaining/spec39-1010.md:7 | S | unassigned W34: owner-call (tracked in the plans), w34-L1-1111.md. |
| 542 | **Already fixed 2026-11-02 (tests/test_composer_725.py::test_unrelated_words_do_not_meet; `composer._stem("news")` gives "news", not "new").** _stem turns "news" into "new", which its own comment says it must not (src/memorymap/ai/composer.py:453); found writing the stemmer test, not changed. | docs/roadmap/archive/agent-remaining/triage-1010.md:25 | S | unassigned |
| 543 | ~~intent.py's _NOTE_WORDS gained "think", "plan", "idea" and more on the Gemini branch (src/memorymap/ai/intent.py:65), so "I think so" routes to the...~~ **W34: fixed** (w34-L1-1111.md) | docs/roadmap/archive/agent-remaining/triage-1010.md:30 | S | unassigned |
| 544 | Section: Phase D: recovery (Brief 31) | docs/roadmap/AGENT_SKILLS_REFORM.md:104 | M | unassigned |
| 545 | Section: Does the MCP server work: resources, prompts, ask_user and make_plan to a bare client | docs/roadmap/AGENT_SKILLS_REFORM.md:345 | M | unassigned |
| 546 | Section: Phase 4: skills that finish (Brief 13) | docs/roadmap/CHAT_PLAN.md:365 | M | unassigned |
| 547 | Section: Section 15: inventions I1 to I9 (night shift, margin reader, open questions, resurfacing, time travel, evidence cards, corrections loop, model bench, what it learned) | docs/roadmap/WORLD_CLASS_PLAN.md:1085 | L | unassigned |
| 548 | SKILLS Phase D: no model ran any of it. The fake transport answers every step, so "a rewritten step fixes a run a 3B model stalled on" is the claim... | docs/roadmap/agent-remaining/OPEN.md:2055 | M | unassigned |
| 549 | The follow-up chips were stubbed at the route in the sweep, because /chat/followups answers [] with no model. What is measured is the request a chip... | docs/roadmap/agent-remaining/OPEN.md:2071 | M | unassigned |
| 550 | #chat-results's second half is the only .panel-head with no actions. The next head that wants a control beside its title should take family 8 rather... | docs/roadmap/agent-remaining/OPEN.md:2200 | S | unassigned |
| 551 | The Guide's no-model system answer still prints no "I took that to mean". | docs/roadmap/agent-remaining/OPEN.md:2213 | S | unassigned |
| 552 | The Library's documents, boards, images, bookmarks, recordings and skills boxes suggest recents only, not their own titles. | docs/roadmap/agent-remaining/OPEN.md:2225 | S | unassigned |
| 553 | The Guide, drafting and document review get a ledger run but no narrated lines; chat and agent turns are never announced. | docs/roadmap/agent-remaining/OPEN.md:2243 | S | unassigned |
| 554 | Row actions (rowActions) not yet in meetings, the suggestions inbox, the tag manager; "Kinds: all" triggers and the chat strip's pill toggles a... | docs/roadmap/agent-remaining/OPEN.md:2251 | S | unassigned |
| 555 | Open: a country with several time zones names one ("the time in Australia" says Sydney's). | docs/roadmap/agent-remaining/OPEN.md:2286 | S | unassigned |
| 556 | Open: the user's own bubble shows a trailing backslash as typed. | docs/roadmap/agent-remaining/OPEN.md:2288 | S | unassigned |
| 557 | A held-back skill is still runnable through the agent's run_skill tool; the label is only in the picker and Settings. | docs/roadmap/agent-remaining/OPEN.md:2315 | S | unassigned |
| 558 | Import replaces skills, personas and templates whole (no merge); the desktop save path for Export settings not driven. | docs/roadmap/agent-remaining/OPEN.md:2323 | S | unassigned |
| 559 | The Guide topics board-library and whiteboard-controls sit at 1,918 of 1,920 characters: the next board help line needs a split topic. | docs/roadmap/agent-remaining/OPEN.md:2381 | S | unassigned |
| 560 | Tab-level Guide topics ring the tab's main control, not each topic's own control. | docs/roadmap/agent-remaining/OPEN.md:2449 | S | unassigned |
| 561 | The "remind me" chat answer's text appears twice in the bubble's innerText (not checked whether drawn twice). | docs/roadmap/agent-remaining/OPEN.md:2450 | S | unassigned |
| 562 | The other tabs' starters (Notes, Chat, Graph, Library, Documents) are not in ai/starter_acts.py; with no model they get the composed answer... | docs/roadmap/agent-remaining/OPEN.md:2518 | S | unassigned |
| 563 | A file of tests (describe/it, unittest) debugs as a plain script, without the harness: the tests do not run under Debug. | docs/roadmap/agent-remaining/OPEN.md:2580 | S | unassigned |
| 564 | "the other one" (decision 57) in Chat: routes_chat._spoken_act sends objects only when the client puts them on history turns; chat-attach.js does not... | docs/roadmap/agent-remaining/OPEN.md:2609 | S | unassigned |
| 565 | INBOX 731 (the Guide failing with a model): not touched; the model-path fallback in help_chat.answer_stream still needs the log line read. | docs/roadmap/agent-remaining/OPEN.md:2612 | S | unassigned |
| 566 | Row 9 (rule 12): "a board AI act as one chat tool (summarise this board; a board from a note)". Not built: a tool under src/memorymap/ai/tools/ with... | docs/roadmap/agent-remaining/OPEN.md:2651 | M | unassigned |
| 567 | Eight dialogs open as centred cards at 390 and should be bottom sheets (extract, history, connections, binned, run a skill, board keys, meeting... | docs/roadmap/agent-remaining/OPEN.md:2674 | S | unassigned |
| 568 | Fixed 8c2e4e5 (docks fold by width). Six of 14 content docks show more than seven items at 1440 (Notes 10, Graph 9, Library 9, Chat 8, Timeline 8, Boards 8); fold by count, 13.1 row 2... | docs/roadmap/agent-remaining/OPEN.md:2675 | S | done 8c2e4e5 |
| 569 | The README tour still has two gaps. The chat screenshot shows an empty conversation (no model in the sandbox), so a machine with Ollama should retake... | docs/roadmap/agent-remaining/OPEN.md:2739 | M | unassigned |
| 570 | guideia.md: the Guide is a modal sheet whose scrim dims the app, so "Open the Reminders tab" cannot be read against the tab. [guideia] *Needs: a... | docs/roadmap/agent-remaining/OPEN.md:2796 | S | unassigned |
| 571 | uipolish-0924.md: the surface-by-surface pass (its item D) is already a row above. Triaged: deadbtn.js's findings for Chat's #chat-export and... | docs/roadmap/agent-remaining/OPEN.md:2841 | M | unassigned |
| 572 | Help audit's remainder: menus drawn on press (the chat "/" menu, a message's menu, the board menus, the notes list's menus) are checked by source... | docs/roadmap/agent-remaining/OPEN.md:2986 | M | unassigned |
| 573 | Chat panels not measured: #chat-model-panel with a model connected (popupsart.js (removed 2026-10-12, recoverable from git history) cannot open it without one; use scratchpad/llama-dev.sh) and the... | docs/roadmap/agent-remaining/OPEN.md:2993 | S | unassigned |
| 574 | The popup agent's results pane with a conversation in it. Everything was measured on the empty state, since this sandbox has no model... | docs/roadmap/agent-remaining/OPEN.md:3252 | L | unassigned |
| 575 | The .skill-fact-reads chip reads dy +4px in one of four identical instances on the Skills sub-tab at 1440 (badgealign.js); the instance is not... | docs/roadmap/agent-remaining/OPEN.md:3309 | S | unassigned |
| 576 | Owner (2026-10-07): the janitor warmed a default chat model it never checked ("Chat with 'llama3.2' failed"). warm_filing_model (janitor.py:741)... | docs/roadmap/agent-remaining/OPEN.md:3336 | M | unassigned |
| 577 | Owner (2026-10-07): on first launch, choose the chat, background and image models from the installed ones instead of llama3.2 (Atlas said "was... | docs/roadmap/agent-remaining/OPEN.md:3337 | M | unassigned |
| 578 | Chat's next-question chips were not seen in the browser: the sweep found no .chat-followups button. Check refreshFollowupVisibility and the chip... | docs/roadmap/agent-remaining/OPEN.md:3359 | M | unassigned |
| 579 | Chat dock at narrow widths: the streaming state (Stop shown, Send hidden) was not measured. (from dock694-1006.md) | docs/roadmap/agent-remaining/OPEN.md:3363 | S | unassigned |
| 580 | Chat's 82 (1440) and 136 (390) overlaps after answers: a sticky head over scrolled cards or a real paint clash. (from deepen-b-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3420 | S | unassigned |
| 581 | Whether each Guide topic answers its question (only the topic's head was read). (from deepen-b-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3421 | S | unassigned |
| 582 | Chat with no model: "what is 15% of 240" quotes a note; "convert 5 km to miles", "what day is it today" and "summarise my week" answer "Nothing in... | docs/roadmap/agent-remaining/OPEN.md:3427 | M | unassigned |
| 583 | Item 32, "metadata ... very messy": the chat answer's foot is still three rows (Sources, Grounded in, meta), 148 px measured on a five-source answer... | docs/roadmap/agent-remaining/OPEN.md:3505 | S | unassigned |
| 584 | INBOX 731, "the help guide failed??": with a model only; no model answers (help-chat.js:329 is the catch). Needs the server log line from a model run. | docs/roadmap/agent-remaining/OPEN.md:3507 | S | unassigned |
| 585 | Web link cards in chat and the web reader share no recipe with markdown.js:1258 linkCard; one recipe for both. | docs/roadmap/agent-remaining/OPEN.md:3512 | S | unassigned |
| 586 | Rule 5: a stopped answer ends its stream without a done line; how Chat, the Guide and the documents panel render that end is not verified in the page. | docs/roadmap/agent-remaining/OPEN.md:3522 | S | unassigned |
| 587 | Chat "Save this chat as a document": creates a document, no undo (chat.js; 28 write functions, 7 with an undo path). | docs/roadmap/agent-remaining/OPEN.md:3550 | S | unassigned |
| 588 | The 390 px layout of the Tidy Patterns rows and the Chat pattern line is not measured (1440: Tidy row buttons 32 px, no overflow; Chat line 55 px).... | docs/roadmap/agent-remaining/OPEN.md:3589 | S | unassigned |
| 589 | A chat is one search row (the whole thread), so a hit opens the chat, not the turn that matched (index._conversation_row). [search-1010] | docs/roadmap/agent-remaining/OPEN.md:3596 | S | unassigned |
| 590 | Decision 7: only note cards changed (category pill to a dot and a word); chat bubble metadata not measured (no conversation without a model) and... | docs/roadmap/agent-remaining/OPEN.md:3668 | S | unassigned |
| 591 | One focus ring at 1:1 in Chat (button.active, its outline takes the ground colour, both themes; scratchpad/ui-sweeps/focusring.js). Bug.... | docs/roadmap/agent-remaining/OPEN.md:3672 | S | unassigned |
| 592 | Messages saved before stamps existed show no time (the owner: "a time stamp on each chat message"): showing the chat's own time on every old line... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/chattime-1010.md:3 | M | unassigned |
| 593 | ~~The chat list row still reads "3h ago" (relativeTime of the last message), not a clock time: sheets-selects.js loadConversationList; the exact time...~~ **W34: fixed 9a3770e68** (w34-L2r-1111.md) | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/chattime-1010.md:4 | S | unassigned |
| 594 | Guide topics: board-library (1,496) with board-library-saving (672) and whiteboard-controls (659) with whiteboard-selection (1,504) were already... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/room101-1011.md:5 | S | unassigned |
| 595 | Library's chat rows and the Shelved list still show their own updated_at, not last_at. | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/chattime-1010.md:6 | S | unassigned |
| 596 | The Guide answers an off-topic question with the open tab's help, unlabelled. "what is the weather today" asked from the Library returned "From the... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/scan-1011.md:10 | M | unassigned |
| 597 | ~~852: the Contents, Skills, Boards and Documents renderers were not changed; their shifts measured under 0.02 in the flick loop, with a small seeded...~~ **W34: stale** (w34-L1-1111.md) | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/ownerfix3-1011.md:18 | S | unassigned |
| 598 | H4. Evals breadth. The same ten cases at 3B and 4B, and the required first call measured over twenty imperatives and ten questions, with a tighter... | docs/roadmap/AGENT_SKILLS_REFORM.md:274 | M | unassigned W34: unverifiable, w34-L2r-1111.md. |
| 599 | Tools that mean something only inside the chat UI are offered anyway: ask_user, make_plan, compress_chat, search_chat_history, get_app_navigation... | docs/roadmap/AGENT_SKILLS_REFORM.md:368 | M | unassigned |
| 600 | Results carry the app's own label with an icon name in front ("ph:folders Listed your categories"); an external client reads "ph:folders" as text.... | docs/roadmap/AGENT_SKILLS_REFORM.md:373 | S | unassigned |
| 601 | No tool annotations (readOnlyHint, destructiveHint), so a client cannot auto-approve the read tools; the registry already knows which are which. | docs/roadmap/AGENT_SKILLS_REFORM.md:376 | S | unassigned |
| 602 | protocolVersion is a constant, 2024-11-05, with no negotiation of the client's version; no resources (notes as resources would suit a notebook) and... | docs/roadmap/AGENT_SKILLS_REFORM.md:378 | S | unassigned |
| 603 | ~~Startup loads the embedder (stderr shows "Loading weights"), 1.6 s warm and longer cold; a client that times out at 5 s on first call would fail.~~ **W34: fixed** (w34-L2r-1111.md) | docs/roadmap/AGENT_SKILLS_REFORM.md:381 | S | unassigned |
| 604 | Only stdio, so only a process on this computer with a Python that can import the app. The packaged app has no Python (/capabilities already says so... | docs/roadmap/AGENT_SKILLS_REFORM.md:383 | M | unassigned |
| 605 | Settings has no panel for it: nothing shows the client config snippet ({"command": ".../python", "args": ["-m", "memorymap.mcp_server"], "env"... | docs/roadmap/AGENT_SKILLS_REFORM.md:390 | S | unassigned |
| 606 | The run object carries its budget: steps, tool calls, tokens and wall time against the skill's declared caps; a run that exceeds one stops with a... | docs/roadmap/AGENT_SKILLS_REFORM.md:412 | S | unassigned |
| 607 | Every tool result is checked by the harness before the model sees it (the 2026-09-21 decision, made a lint): a tool that can write has a verifier in... | docs/roadmap/AGENT_SKILLS_REFORM.md:415 | S | unassigned |
| 608 | **Already fixed 2026-11-02 (frontend/js/chat-attach.js `deleteCurrentChat`, the toolbar Delete).** Empty chats could not be deleted. A Delete button in the chat toolbar now covers both cases, an empty or unsaved pane resets... | docs/roadmap/BACKLOG.md:105 | M | unassigned |
| 609 | Chat: plain grounded Q&A | docs/roadmap/BACKLOG.md:184 | S | unassigned |
| 610 | There is no token bill. Ollama runs on the user's own machine, so a token costs latency and context window, not money. Headroom's... | docs/roadmap/BACKLOG.md:719 | S | unassigned |
| 611 | A model comparison / test-run feature, Pointer: WORLD_CLASS_PLAN I8 "The model bench" (H3, row 21; model_bench switch in... | docs/roadmap/BACKLOG.md:827 | L | unassigned |
| 612 | Prompt reuse. Every agent round resends the whole message list; keep_alive is set now (OllamaClient, 30 minutes, checked... | docs/roadmap/BACKLOG.md:857 | S | unassigned |
| 613 | The system prompt is long and grew again this session; it is re-sent every round of every turn, which is where Ollama's... | docs/roadmap/BACKLOG.md:911 | S | unassigned |
| 614 | That skills exist at all (the tools are there; the prompt never mentions them) | docs/roadmap/BACKLOG.md:967 | S | unassigned |
| 615 | Deciding *when* to search, not just how well it searches once asked. Asked for as "better agentic web search through chat", read... | docs/roadmap/BACKLOG.md:1040 | L | unassigned |
| 616 | Undo is a single tool call posted back to /chat/tools/execute (chat-agent.js, changeRow). Its arguments may carry extra keys... | docs/roadmap/BACKLOG.md:1087 | S | unassigned |
| 617 | No fallback when the configured chat/agent endpoint errors. Checked directly: ai/ollama_client.py, ai/openai_client.py, and... | docs/roadmap/BACKLOG.md:1238 | L | unassigned |
| 618 | Benchmark installed models on first run, to suggest a default rather Pointer: WORLD_CLASS_PLAN I8 "The model bench" (H3); this... | docs/roadmap/BACKLOG.md:1827 | M | unassigned |
| 619 | A VS Code extension. Next: nothing is buildable until the owner states a purpose; the HTTP tool API (GET /chat/tools, POST... | docs/roadmap/BACKLOG.md:1860 | M | unassigned |
| 620 | Chat history has retention; nothing else does. §86 added conversation_retention_days (off by default, pinned chats exempt). The... | docs/roadmap/BACKLOG.md:2265 | L | unassigned |
| 621 | A "this model is struggling" signal. Next: the probe is _tools_path_is_broken in ai/ollama_client.py:571 (§94); count its... | docs/roadmap/BACKLOG.md:2383 | M | unassigned |
| 622 | Conversation summaries as retrieval targets. Next: register a chat source in search/index.py (source_for raises on an... | docs/roadmap/BACKLOG.md:2408 | M | unassigned |
| 623 | A plugin system. Skills already cover the "make the app do a new thing" case without a new extension surface to secure. | docs/roadmap/BACKLOG.md:2495 | S | unassigned |
| 624 | A skill is a *procedure* the agent runs, start to finish. | docs/roadmap/BACKLOG.md:2516 | S | unassigned |
| 625 | A Guide is a *format contract* for one piece of output, it does not run, it constrains. Several can apply at once (an assignment... | docs/roadmap/BACKLOG.md:2517 | S | unassigned |
| 626 | Stored like skills (a table, editable in Settings), with a name, a trigger hint, and the instruction body. | docs/roadmap/BACKLOG.md:2523 | S | unassigned |
| 627 | Applies to all three surfaces the user named: chat replies, note drafting, and POST /documents/{id}/ai-edit. | docs/roadmap/BACKLOG.md:2533 | S | unassigned |
| 628 | Wider Mermaid: sequence and timeline diagrams render in documents and chat, and import to boards as frames; anything else stays... | docs/roadmap/BACKLOG.md:2583 | S | unassigned |
| 629 | **Already met 2026-11-02 (src/tessellate/api/routes_chat.py:315 `attached_notes_only`; the row calls its claim false).** *"No way to scope a chat query to chosen notes"*, false. note_ids plus attached_notes_only (routes_chat.py) already do exactly... | docs/roadmap/BACKLOG.md:2895 | M | unassigned |
| 630 | The AI Skills tab's step/tool lists: reported directly, with a screenshot: expanded, they read as plain paragraphs sat right on... | docs/roadmap/BACKLOG.md:3380 | M | unassigned |
| 631 | A "Clear" button for the AI Skills sidebar's own log list, DELETE /audit?entity_type=... (entity_type required, so this can never... | docs/roadmap/BACKLOG.md:3407 | M | unassigned |
| 632 | Per-note pinned AI context, Next: note_ids and attached_notes_only (routes_chat.py) already scope a turn; a Entry.pinned_context... | docs/roadmap/BACKLOG.md:3616 | M | unassigned |
| 633 | A plugin marketplace. The skills library covers reusable prompts; arbitrary third-party code in a privacy-first app is a... | docs/roadmap/BACKLOG.md:3890 | S | unassigned |
| 634 | The owner, 2026-09-21, verbatim, with the session's reading beneath it: "it'd be cool if the user can upload songs or connect an... | docs/roadmap/BACKLOG.md:3959 | L | unassigned |
| 635 | "Read all my requests and chat messages sent during and since october 7, analyse them and log them for a new session as I want to... | docs/roadmap/BACKLOG.md:4167 | L | unassigned |
| 636 | The owner, 2026-09-24, verbatim, with a chat screenshot. "I was in a document in the editor, I opened the suggestions panel and pressed check with... | docs/roadmap/CHAT_PLAN.md:694 | L | unassigned |
| 637 | "on the guide the thinking shows below the thinking indicator and stuff" / "with no gap either" Recommendation: measure the gap between the thinking... | docs/roadmap/CHAT_PLAN.md:847 | M | unassigned |
| 638 | "should that no chats text be at the top not the bottom??" Recommendation: place the empty-chat text at the top of the list and measure its position... | docs/roadmap/CHAT_PLAN.md:849 | S | unassigned |
| 639 | "also I just asked another question, didnt like the response so I deleted it, and now somehow the token usage I was at for that chat has lowered??"... | docs/roadmap/CHAT_PLAN.md:861 | M | unassigned |
| 640 | "I can still activate skills and the suggested skill popup still appears when I have no model running." / "The ai model isnt running, skills are... | docs/roadmap/CHAT_PLAN.md:871 | M | unassigned |
| 641 | "Its still allowing me on agent mode even when the ai model isnt connected" Recommendation: agent mode is disabled with its reason when no model is... | docs/roadmap/CHAT_PLAN.md:873 | S | unassigned |
| 642 | "I tried to press "a note" on the slash menu in the chat tab and the panel flickered then nothing happened" / "Same with the other options like "a... | docs/roadmap/CHAT_PLAN.md:889 | M | unassigned |
| 643 | 731, the Guide failing with a model. "the help guide failed??" (Atlas answering "whiteboard templates" with "Something went wrong asking that"). Not... | docs/roadmap/CHAT_PLAN.md:1757 | M | unassigned |
| 644 | INBOX 808 Agent mode: ask_user with one option, search_notes with no query, backslash kept in query, grammar worker did not start | docs/roadmap/INBOX.md:190 | S | unassigned |
| 645 | Briefs 13, 14 and 16 (harness verifier B5, docs condensed, docs refined): unmarked; verify then close | docs/roadmap/SESSION_BRIEFS.md:430 | S | unassigned |
| 646 | Brief 18: the complete open scope sections A to G (bugs, documents, graph, chat, boards, library, plan remainders): unmarked | docs/roadmap/SESSION_BRIEFS.md:660 | L | unassigned |
| 647 | Six nav groups, by what the person is doing: AI (Models, Search and index, Personas, Skills, Tools it can use, What it remembers, What it learned... | docs/roadmap/UI_MODERNISATION_PLAN.md:1137 | M | unassigned |
| 648 | Answer style moves from General to Personas: it is Atlas's voice, and the Personas pane already says so. General is left with the recycle bin, chat... | docs/roadmap/UI_MODERNISATION_PLAN.md:1148 | S | unassigned |
| 649 | Suggested downloads are model cards, grouped by purpose (chat and filing, bigger machines, search, images, reading text), settings-models.js. One... | docs/roadmap/UI_MODERNISATION_PLAN.md:1174 | L | unassigned |
| 650 | "Note metadata and chat bubble metadata still feels incredibly messy, not modern, and unrefined. The whole app needs another ui/ux modernisation... | docs/roadmap/UI_MODERNISATION_PLAN.md:1272 | L | unassigned |
| 651 | "Things that feel off that I cannot place." After the consistency and docks lists close, one review pass per tab with the vendored design skills... | docs/roadmap/WORLD_CLASS_PLAN.md:1563 | M | unassigned |
| 652 | The Guide's row is the answer to INBOX 288 but not to its cause. Smart model routing off silently moves the Guide, an interactive panel, onto the... | docs/roadmap/WORLD_CLASS_PLAN.md:2274 | M | unassigned |
| 653 | A per-feature model is shown on the Chat tab and nowhere else. The chat pill (#chat-active-model) reads the pinned model now, but the writing desk... | docs/roadmap/WORLD_CLASS_PLAN.md:2281 | M | unassigned |
| 654 | 0.4.0, "laptop perfect": 22.1 items 1 to 6, and the devibecode programme through the shell, Notes, Dashboard, Chat and Settings. | docs/roadmap/WORLD_CLASS_PLAN.md:2433 | L | unassigned |
| 655 | The Guide's corpus and the Help accordion are kept in step by hand (guide; the synonym column it asked for exists, help_chat.py's keyword table).... | docs/roadmap/WORLD_CLASS_PLAN.md:3050 | S | unassigned |
| 656 | ~~Reduced motion was checked in source and the harness, not in a browser run.~~ **W34: stale** (w34-unv1-1111.md) | docs/roadmap/archive/agent-remaining/graphfeel-1010.md:13 | S | unassigned |
| 657 | Decision 38: the other 13 verbs, confirm card, undo, no-model Agent mode, web search tool. | docs/roadmap/archive/agent-remaining/spec39-1010.md:10 | S | unassigned W34: owner-call (tracked in the plans), w34-L1-1111.md. |
| 658 | ~~"Gemini might have removed the spell checker??" (the owner): it did not touch the editor's speller (its frontend diff is skills.js, index.html...~~ **W34: stale** (w34-L1-1111.md) | docs/roadmap/archive/agent-remaining/triage-1010.md:24 | M | unassigned |
| 659 | ~~Rail nodes (frontend/css/02-chat-graph.css:732): 0.75rem kept, measured on a synthetic run: thinking and plan rows 0.12px from the first line's...~~ **W34: stale** (w34-L1-1111.md) | docs/roadmap/archive/agent-remaining/triage-1010.md:31 | S | unassigned |
| 660 | ~~search_help found nothing for "what is agent mode" and "how does search work" (2 of 10; help_block_for, src/memorymap/ai/help_chat.py:2467).~~ **W34: fixed** (w34-L1-1111.md) | docs/roadmap/archive/agent-remaining/triage-1010.md:32 | S | unassigned |
| 661 | Atlas round 5, the owner's asks (INBOX 427 (1); 2026-09-27): hands and feet drawn as part of each limb's outline (a mitten with a thumb on the inner... | docs/roadmap/agent-remaining/OPEN.md:1903 | L | unassigned |
| 662 | The companion rides with ScrollTimeline (Chromium 115+, so WebView2); WebKitGTK falls back to the script follow. Not driven in either desktop window.... | docs/roadmap/agent-remaining/OPEN.md:1935 | S | unassigned |
| 663 | Atlas's hide act shows shut eyes and nothing of its hands. The companion's new act (a private note opened) raises both arms over the face; Atlas... | docs/roadmap/agent-remaining/OPEN.md:2150 | L | unassigned |
| 664 | The Atlas look row landed under the Settings sheet's head at 390 in one of four runs. | docs/roadmap/agent-remaining/OPEN.md:2451 | S | unassigned |
| 665 | The rest of Atlas's idle cost is the companion's own behaviour, not the tail: with the tail and breath switched off, 670 recalcs and 130 layouts a... | docs/roadmap/agent-remaining/OPEN.md:2619 | M | unassigned |
| 666 | The chest's breath still writes the torso's scale 2.5 times a second at rest (atlas-life.js atlasBreathFrame): a recalc and a layout each. Zero needs... | docs/roadmap/agent-remaining/OPEN.md:2623 | M | unassigned |
| 667 | 104px faces (the welcome, the large view): 2 to 3 of 15 distinct in light by the same metric; the cue is drawn only at the head and tiny levels. The... | docs/roadmap/agent-remaining/OPEN.md:2626 | M | unassigned |
| 668 | Arm angle over a walk cycle not measured (atlasarms.js measures still poses; the walk swing is the rig's, atlas-motion.js atlasRigFrame). | docs/roadmap/agent-remaining/OPEN.md:2636 | S | unassigned |
| 669 | #nm-buddy:has(.atl-figure) .nm-buddy-char and the lower layer still slow to 6s under the hint (08-consistency.css, the block after the chin hand... | docs/roadmap/agent-remaining/OPEN.md:2638 | M | unassigned |
| 670 | Companion movement Full keeps the script loops (tail, rings) under Reduce by design (atlasMotionOK); the CSS loops stop under the hint regardless. | docs/roadmap/agent-remaining/OPEN.md:2641 | L | unassigned |
| 671 | Atlas motion, measured left (the owner's rows 554 to 575 are above): atlas619-blend.js stepped by hand shows laughing's end moving the figure about... | docs/roadmap/agent-remaining/OPEN.md:2969 | L | unassigned |
| 672 | The owner, 2026-10-05, verbatim. "one of the feminine atlas blinking animations has MASSSSIVE eyebrows." Not reproduced (2026-10-05): the live... | docs/roadmap/agent-remaining/OPEN.md:3100 | M | unassigned |
| 673 | The owner, 2026-10-05, verbatim. "the feminine atlas whisps should wrap the body a bit more instead of all of it sitting in front. also the lower... | docs/roadmap/agent-remaining/OPEN.md:3108 | M | unassigned |
| 674 | The owner, 2026-10-05, verbatim. "and a bit more texture can be added to the lower body as well. make it celestial and majestic and magical and... | docs/roadmap/agent-remaining/OPEN.md:3115 | M | unassigned |
| 675 | The owner, 2026-10-05, verbatim. "can you fix or redesign the male main body on the atlas avatar instead of just being an oval?? also fix how the... | docs/roadmap/agent-remaining/OPEN.md:3120 | L | unassigned |
| 676 | The owner, 2026-10-05, verbatim. "can you have the lower body of both atlas avatars change around in position and and how it is sitting ect with... | docs/roadmap/agent-remaining/OPEN.md:3130 | M | unassigned |
| 677 | "I cant right click to view the menu to change the companion in the expanded popup view" Recommendation: the enlarged view gets the same context menu... | docs/roadmap/agent-remaining/OPEN.md:3279 | M | unassigned |
| 678 | "I barely get to see atlas change expression. atlas and the companion movement and behaviour need to be more and more lifelike, natural, smooth... | docs/roadmap/agent-remaining/OPEN.md:3284 | M | unassigned |
| 679 | "The companion and atlas needs a lot more improvement, and lifelike behaviour, more cool and diverse ways to move around, enter the screen, change... | docs/roadmap/agent-remaining/OPEN.md:3286 | M | unassigned |
| 680 | A click in Atlas's own large view costs 22 to 44ms in setAtlasMood (every layer's animations, then atlasApply on 12 layers), 50 to 100ms on a loaded... | docs/roadmap/agent-remaining/OPEN.md:3332 | M | unassigned |
| 681 | The generic (non-Atlas) faces' arms have no rig and so no speed cap; the fastest segment of their wave and hide keyframes was not measured. (from... | docs/roadmap/agent-remaining/OPEN.md:3333 | S | unassigned |
| 682 | INBOX 742 and 743, "atlas doesnt seem to change emotions alot", "more mouse interaction ... rubbing its head. flipping it upside down": gestures... | docs/roadmap/agent-remaining/OPEN.md:3508 | M | unassigned |
| 683 | Palette rows missing (heuristic word match, the destination and its click path): 1 Notifications: # unread (muted except reminders); 1 Atlas files it... | docs/roadmap/agent-remaining/OPEN.md:3562 | L | unassigned |
| 684 | Decision 7's "under 1 ms a minute" is not met by Atlas: its tail is a script-drawn path (atlas-life.js atlasTailFrame), 15 draws a second at rest... | docs/roadmap/agent-remaining/OPEN.md:3624 | M | unassigned |
| 685 | Atlas's faces do not read as different moods (sheet: atlas-sheet-*.png, 15 moods at 104, 28 and 20 px, both looks, light and dark): at 104 the face... | docs/roadmap/agent-remaining/OPEN.md:3625 | M | unassigned |
| 686 | Under the system's reduce-motion hint Atlas keeps its calm CSS loops (an earlier decision, 08-consistency.css:5056): 1,579 style recalcs a minute.... | docs/roadmap/agent-remaining/OPEN.md:3626 | S | unassigned |
| 687 | The owner's "arm movements ... permanently in a downward arc": the arm hold now changes on idle ticks (45%), but the arm angle range over a walk... | docs/roadmap/agent-remaining/OPEN.md:3628 | S | unassigned |
| 688 | Tail, rings, nebula and lower-body "subtle animations that are all cheap" (owner's list): not changed; they exist (atlas-life.js) and are the cost... | docs/roadmap/agent-remaining/OPEN.md:3629 | S | unassigned |
| 689 | Face sheet (facesheet.js (removed 2026-10-12, recoverable from git history), 12 names, light): one silhouette, one outline, readable at 104; crowns spill 6 px past the card's top edge; the gaming... | docs/roadmap/agent-remaining/OPEN.md:3630 | S | unassigned |
| 690 | Companion bubbles: what the companion says about the notebook (a resurfaced note, a pattern this week, a reminder due, an empty day) is composed from... | docs/roadmap/CHAT_PLAN.md:727 | M | unassigned |
| 691 | Voice: Atlas's by default, changeable. Warm and brief in openings and companion bubbles, plain in answers; a setting offers plain and playful too... | docs/roadmap/CHAT_PLAN.md:829 | S | unassigned |
| 692 | Two functions here are among the ten most complex in src (WORLD_CLASS 26.5): api/routes_chat.py::_stream_lines cx 105 over 321 lines and... | docs/roadmap/CHAT_PLAN.md:1763 | M | unassigned |
| 693 | INBOX 742 Atlas changes emotions more: mood-change count per session (Brief 34 second part) | docs/roadmap/INBOX.md:111 | M | unassigned |
| 694 | INBOX 743 more mouse interaction with Atlas: gestures, enlarged view mirroring the corner, oval clip, Show companion notice (Brief 34, OPEN Atlas rows 752) | docs/roadmap/INBOX.md:118 | M | unassigned |
| 695 | INBOX 772 reduced motion keeps poses without loops: decision taken, companion2 continues | docs/roadmap/INBOX.md:151 | S | unassigned |
| 696 | Brief 34 continues: Atlas and the companion (companion2 landed; OPEN Atlas rows remain) | docs/roadmap/SESSION_BRIEFS.md:1390 | L | unassigned |
| 697 | Settings that guard something stay beside it. "Keep Atlas on this machine" stays with the backend address it guards; the Privacy pane reports, it... | docs/roadmap/UI_MODERNISATION_PLAN.md:1151 | S | unassigned |
| 698 | The owner, 2026-09-24 (after the usage reset), with screenshots. Avatars: (a) "the avatar shows even when the app is on the lock screen. it should... | docs/roadmap/WORLD_CLASS_PLAN.md:2886 | L | unassigned |
| 699 | Decision 36: bubble label "Atlas, from your notes" is a frontend check. | docs/roadmap/archive/agent-remaining/spec39-1010.md:8 | S | unassigned W34: owner-call (tracked in the plans), w34-L1-1111.md. |
| 700 | Section: Phases 1 to 5 as first written (built per sections 9 to 11) | docs/roadmap/MINDMAP_PLAN.md:158 | S | unassigned |
| 701 | Section: 12.3 Phase 6c, what only a notebook can do | docs/roadmap/MINDMAP_PLAN.md:505 | M | unassigned |
| 702 | Section: Section 13: the six complaints, phases open | docs/roadmap/MINDMAP_PLAN.md:604 | L | unassigned |
| 703 | Section: 14.4 What is open (core nodes, linked symbols, layer effects, reactions) | docs/roadmap/MINDMAP_PLAN.md:1755 | M | unassigned |
| 704 | The mind map's own leftover list was re-checked item by item, 2026-09-20 (archive/agent-remaining/mindmap.md, "Left to do", rewritten with what a run... | docs/roadmap/agent-remaining/OPEN.md:2087 | L | unassigned |
| 705 | Pre-existing sweep failures on the base scripts: mapcore.js (removed 2026-10-12, recoverable from git history) 14/16 (a core node's spine and size), mindmap.js three FAILs (the Mind map segment's... | docs/roadmap/agent-remaining/OPEN.md:2119 | M | unassigned |
| 706 | Mind map gaps open: a structure per branch, callouts, labels under a topic, .xmind export, stickers and votes. | docs/roadmap/agent-remaining/OPEN.md:2380 | S | unassigned |
| 707 | Mind map library schematics (wbMapThumbSpec) are monochrome, not tinted with branch colours; a hollow diamond draws the shaft through it. | docs/roadmap/agent-remaining/OPEN.md:2414 | S | unassigned |
| 708 | createConceptMap (whiteboard.js ~20240) has no caller but app.js's lazy stub list now that every "concept map" entry makes the mind map: delete it... | docs/roadmap/agent-remaining/OPEN.md:2551 | S | unassigned |
| 709 | mindmap2.md: mindmapimage.js (removed 2026-10-12, recoverable from git history) passes 12 of 12 at 390x844 (measured 2026-10-04); a picture node does not resize to its picture; mindmap3.js times out... | docs/roadmap/agent-remaining/OPEN.md:2821 | L | unassigned |
| 710 | Frames and the map plan's rest: MINDMAP_PLAN 12.2's rest (a boundary round a lassoed set that is not one branch, priority, progress, flags and due... | docs/roadmap/agent-remaining/OPEN.md:2952 | M | unassigned |
| 711 | The size stepper reads "17px" on a main branch and "22px" on the centre, and Classic's level sizes have no S, M, L or XL word, so the well showed... | docs/roadmap/agent-remaining/OPEN.md:3399 | M | unassigned |
| 712 | Mind map "Add a top-level topic": the board stack grows by one, Ctrl+Z leaves the lists differing (/whiteboard/ state not equal to before)... | docs/roadmap/agent-remaining/OPEN.md:3549 | S | unassigned |
| 713 | Whiteboard 43 write functions, 14 with an undo path; mind map 25 and 7; graph 21 and 9; library 30 and 9; dashboard 9 and 1; timeline 5 and 1... | docs/roadmap/agent-remaining/OPEN.md:3551 | S | unassigned |
| 714 | Documents were not probed in the dark run (the list had not loaded when the sweep opened it), and the mind map "Add a top-level topic" undid in one... | docs/roadmap/agent-remaining/OPEN.md:3553 | S | unassigned |
| 715 | #wb-tool-group span.wb-tool-section-label: text 49 to 56px past its box at 820, 1024 and 1440 on the whiteboard and the mind map (36 nodes counted as... | docs/roadmap/agent-remaining/OPEN.md:3554 | S | unassigned |
| 716 | Board: board acts are off on a mind map (wbPaletteActRow returns null when wbIsMap()): a map's layout is its tidy, not a grid. Pasting a list as... | docs/roadmap/agent-remaining/OPEN.md:3608 | M | unassigned |
| 717 | Library: a "boards" or "mind maps" filter resolves to Entry.is_board ids, but the Library's filter keeps note cards only (library.js libraryPhrase)... | docs/roadmap/agent-remaining/OPEN.md:3609 | M | unassigned |
| 718 | Decision 5 for a date field built after boot: the map topic's due date (whiteboard-map.js) stays native; the date picker's typed field sets the date... | docs/roadmap/agent-remaining/OPEN.md:3670 | S | unassigned |
| 719 | Boards and mind maps both ways: a mind map exports to and imports from Mermaid mindmap; sequence and timeline import as frames... | docs/roadmap/BACKLOG.md:2605 | S | unassigned |
| 720 | Nodes are notes: any node can become a note (and stays linked); a note dragged from the Library becomes a node with its card; the map node and the... | docs/roadmap/MINDMAP_PLAN.md:507 | S | unassigned |
| 721 | Grow with the AI: on any node, "Suggest branches" proposes five children from the notebook (grounded, with the source note on each), "Expand from my... | docs/roadmap/MINDMAP_PLAN.md:510 | M | unassigned |
| 722 | From a question: "Make a map of..." in chat proposes a map (exists, Phase 4) and now opens it in the map editor with the proposal as floating topics... | docs/roadmap/MINDMAP_PLAN.md:517 | L | unassigned |
| 723 | The layout maths is not slow either. 76.8ms to lay out 500 topics is a command a person pressed, and wbMapIndex, which every map action calls first... | docs/roadmap/MINDMAP_PLAN.md:730 | S | unassigned |
| 724 | renderWhiteboard is the whole of the *opening*, and it grows faster than the node count: 8.1× the nodes buys 21× the render. 1,282ms is a full second... | docs/roadmap/MINDMAP_PLAN.md:733 | L | unassigned |
| 725 | It lands on the user at the worst possible moment. A second run of the probe recorded where in the gesture the worst frame falls: dragWorstAt 0.03... | docs/roadmap/MINDMAP_PLAN.md:741 | L | unassigned |
| 726 | Absorb the free link into the map's own grammar (the direction this plan should take). The free link keeps being a sketch row; what changes is that... | docs/roadmap/MINDMAP_PLAN.md:794 | M | unassigned |
| 727 | Absorb the tree edge into rows. Cost: a migration of every map, the loss of the one property that makes the tree cheap to read, and every one of the... | docs/roadmap/MINDMAP_PLAN.md:801 | M | unassigned |
| 728 | The rail's most connection-looking control makes the other kind. The Connect section's two buttons, "Straight link (C)" and "Curved link (Shift+C)"... | docs/roadmap/MINDMAP_PLAN.md:831 | M | unassigned |
| 729 | Still one door only: everything on the link ring (reverse, label, cut) needs a right-click on a line, which nothing on screen advertises; "Add a... | docs/roadmap/MINDMAP_PLAN.md:837 | S | unassigned |
| 730 | The data keeps two kinds of connection; the controls stop having two. parent_id stays. What changes is that a map's free link is spoken about in the... | docs/roadmap/MINDMAP_PLAN.md:916 | M | unassigned |
| 731 | The strip is sized like its subject. A control surface for one topic does not take two thirds of the window, and it adapts below 1440 rather than... | docs/roadmap/MINDMAP_PLAN.md:920 | S | unassigned |
| 732 | Customisation grows at the map level, not at the topic level. The eleven per-topic fields are enough; the missing layouts and the absence of any... | docs/roadmap/MINDMAP_PLAN.md:923 | S | unassigned |
| 733 | Nothing is added to the canvas. Per standing order 11, any new affordance comes from DESIGN.md's recipe index or arrives with its own recipe and lint... | docs/roadmap/MINDMAP_PLAN.md:926 | S | unassigned |
| 734 | A cross-link has no colour of its own (taken 2026-09-21, building 13c). It is drawn in --muted, dashed, whatever the rail's ink well held when it was... | docs/roadmap/MINDMAP_PLAN.md:933 | L | unassigned |
| 735 | The ring's middle slot promotes a cross-link to a branch (taken 2026-09-21, building 13c). The gesture that makes one or the other decides from... | docs/roadmap/MINDMAP_PLAN.md:948 | M | unassigned |
| 736 | A map's theme holds the ten fields that describe how a map draws topics, and none of the ones that say which topic this is (taken 2026-09-21... | docs/roadmap/MINDMAP_PLAN.md:953 | L | unassigned |
| 737 | The theme is resolved when a topic is painted, never written onto the topics (taken 2026-09-21, building 13e). A topic's own value always wins, and... | docs/roadmap/MINDMAP_PLAN.md:969 | L | unassigned |
| 738 | The theme lives in one row of the View menu's Map section, and nothing is added to the canvas (taken 2026-09-21, building 13e). Decision 5 above, and... | docs/roadmap/MINDMAP_PLAN.md:991 | L | unassigned |
| 739 | "Reset to branch" and the map-wide reset are one idea at two scopes, not two ideas (taken 2026-09-21, building 13e). The ring's reset drops one... | docs/roadmap/MINDMAP_PLAN.md:1005 | M | unassigned |
| 740 | Delete removes the whole branch (taken 2026-10-03, order 3). The code and the server already did, and now that it is one undo step (the topics and... | docs/roadmap/MINDMAP_PLAN.md:1029 | M | unassigned |
| 741 | Tab adds a topic only when the map was engaged (taken 2026-10-03). Tab on a selected topic added a child from anywhere, so a keyboard user could not... | docs/roadmap/MINDMAP_PLAN.md:1033 | M | unassigned |
| 742 | The board's Insert and Arrange menus stay in the markup (taken 2026-10-04, §13f's remainder). Read as dead markup on a map; measured, it is the... | docs/roadmap/MINDMAP_PLAN.md:1058 | M | unassigned |
| 743 | Numbering is the map's, by outline place, and off until asked (taken 2026-10-04, §12.2 item 7). One switch in the View menu's Map group (the menu's... | docs/roadmap/MINDMAP_PLAN.md:1068 | L | unassigned |
| 744 | A note behind a topic is plain text, a topic's own, and opens in the help popover's shell (taken 2026-10-04, §12.2 item 5's first half). data.note... | docs/roadmap/MINDMAP_PLAN.md:1083 | L | unassigned |
| 745 | A boundary is a branch's, drawn round the topics it holds (taken 2026-10-04, §12.2 item 1, under standing order 3; XMind's shape). data.boundary on... | docs/roadmap/MINDMAP_PLAN.md:1103 | L | unassigned |
| 746 | A summary is words beside a run of siblings, not a topic (taken 2026-10-04, §12.2 item 2). data.summary (up to 80 characters) and data.summary_span... | docs/roadmap/MINDMAP_PLAN.md:1119 | L | unassigned |
| 747 | A map presents by branch (taken 2026-10-05, §12.2 item 9, under standing order 3; MindMeister's shape on the board's machinery, WHITEBOARD_PLAN... | docs/roadmap/MINDMAP_PLAN.md:1134 | L | unassigned |
| 748 | A FreeMind file's single root node is the central topic (taken 2026-10-05, audit FEAT-01, features.md 9.5: the owner's newer words win). This... | docs/roadmap/MINDMAP_PLAN.md:1144 | L | unassigned |
| 749 | A map made from text starts in tree-right and is tidied once as it opens (taken 2026-10-05, audit FEAT-05). The import and the accepted AI proposal... | docs/roadmap/MINDMAP_PLAN.md:1155 | M | unassigned |
| 750 | A new topic is drawn and open for typing before the server answers (taken 2026-10-05, audit FEAT-02). Tab and Enter make a provisional row (negative... | docs/roadmap/MINDMAP_PLAN.md:1160 | L | unassigned |
| 751 | The open map's commands are palette rows (taken 2026-10-05, audit FEAT-11): add, rename, fold, focus, delete, tidy, open every branch, look... | docs/roadmap/MINDMAP_PLAN.md:1183 | S | unassigned |
| 752 | A new topic and its first name are one Undo step (taken 2026-10-05, audit FEAT-15), as in XMind: the rename is folded while the add is still the last... | docs/roadmap/MINDMAP_PLAN.md:1190 | S | unassigned |
| 753 | A committed name hands the keys back to the canvas and is said aloud (taken 2026-10-05, audit FEAT-16), unless the press that ended it went to... | docs/roadmap/MINDMAP_PLAN.md:1193 | S | unassigned |
| 754 | No front-and-back Order on a laid-out map (taken 2026-10-05, audit FEAT-17): a tidied tree never overlaps; a Free map keeps the group. | docs/roadmap/MINDMAP_PLAN.md:1196 | S | unassigned |
| 755 | Text pasted onto a map is a branch (taken 2026-10-05, audit FEAT-09): one topic per line, nested by indentation, a numbered or heading line read as a... | docs/roadmap/MINDMAP_PLAN.md:1198 | M | unassigned |
| 756 | The dashboard draws a map at its own shape (taken 2026-10-05, INBOX 553(d), the owner's decision): the Boards & maps widget's busiest board at the... | docs/roadmap/MINDMAP_PLAN.md:1204 | M | unassigned |
| 757 | A map writes itself as a document, one way first (taken 2026-10-05, the audit's brief M5, first half): the board menu's Write as a document and the... | docs/roadmap/MINDMAP_PLAN.md:1209 | M | unassigned |
| 758 | A concept map's topics are notes that stay on their map (taken 2026-10-05, audit UX-06). A note made by a map gesture (a new concept map's root, a... | docs/roadmap/MINDMAP_PLAN.md:1216 | L | unassigned |
| 759 | A map's outline is a panel of fields in the tree's order (taken 2026-10-05, §12.2 item 8, the audit's M3). View, Outline (and the palette's row)... | docs/roadmap/MINDMAP_PLAN.md:1227 | L | unassigned |
| 760 | A document maps its own headings, one way (taken 2026-10-05, the audit's M5 second half). The document's menu, Map the headings (and the palette's... | docs/roadmap/MINDMAP_PLAN.md:1257 | L | unassigned |
| 761 | Studying a map is presenting with each branch hidden until recalled (taken 2026-10-05, §12.3 item 5, under standing order 3; op5). The board menu's... | docs/roadmap/MINDMAP_PLAN.md:1269 | L | unassigned |
| 762 | A topic's due date is a day, a marker, and a reminder only when asked (taken 2026-10-05, §12.2 item 4, under standing order 3; op5). data.due is a... | docs/roadmap/MINDMAP_PLAN.md:1282 | L | unassigned |
| 763 | (Audit 2026-10-05: 13a-open's figures hold for a move; the add path was never gated and cost two whole renders, see decision 24.) | docs/roadmap/MINDMAP_PLAN.md:1313 | S | unassigned |
| 764 | 13g. The middle-button pan on the owner's own machine. He reports, with 13.1's own gesture: "the whiteboard and mindmap goes haywire and moves to the... | docs/roadmap/MINDMAP_PLAN.md:1333 | L | unassigned |
| 765 | Every figure above is light mode. Dark is unmeasured in this read. | docs/roadmap/MINDMAP_PLAN.md:1433 | S | unassigned |
| 766 | The timings are one machine, one Chromium, one run each except the 500-node row, which was run twice (1,583.3ms and 1,616.5ms worst drag frame). They... | docs/roadmap/MINDMAP_PLAN.md:1434 | S | unassigned |
| 767 | The strip is measured at 1440, 1024 and 390 only. boot() defaults to 1440 but takes opts.viewport, so other widths were reached by passing it; 820... | docs/roadmap/MINDMAP_PLAN.md:1437 | S | unassigned |
| 768 | The free link was created through /whiteboard/sketches with the fields the connect drag writes, not by driving the drag itself. The row is the same... | docs/roadmap/MINDMAP_PLAN.md:1440 | S | unassigned |
| 769 | Nothing here reproduces the owner's phrase "awkward to use". The counts say where the controls are, not what it feels like to reach for one. 13b and... | docs/roadmap/MINDMAP_PLAN.md:1443 | M | unassigned |
| 770 | The owner, 2026-09-21, verbatim: "the mindmap needs A LOT of improving. Tools and utilities are really awkward to use and dont show themselves how id... | docs/roadmap/MINDMAP_PLAN.md:1467 | L | unassigned |
| 771 | The owner, 2026-09-27 after the reset, verbatim. "I think notes appear in the command palate search / Also is there a way to customise the colour the... | docs/roadmap/MINDMAP_PLAN.md:1489 | L | unassigned |
| 772 | Ghost topics on the canvas: the suggestions drawn faded under the topic, Tab to take one, Escape to drop them all. Waits on boot CSS room (the cap is... | docs/roadmap/MINDMAP_PLAN.md:1637 | S | unassigned |
| 773 | Expand from my notes: a topic grown a level from the note it is grounded in (its headings and links), not from search. | docs/roadmap/MINDMAP_PLAN.md:1640 | S | unassigned |
| 774 | The affinity sort (a board, WHITEBOARD_PLAN's territory): thirty stickies grouped into named frames by theme, each placement shown with the notes... | docs/roadmap/MINDMAP_PLAN.md:1642 | S | unassigned |
| 775 | The claim check (DOCUMENTS_PLAN's territory): a document's sentences checked against the notebook, each marked supported, contradicted or not found... | docs/roadmap/MINDMAP_PLAN.md:1645 | S | unassigned |
| 776 | Linked stickers (Illustrator's symbols): edit one placed icon or emoji and every copy follows. Needs a library_ref that is followed, which decision... | docs/roadmap/MINDMAP_PLAN.md:1760 | S | unassigned |
| 777 | The whiteboard half of 641's research, beyond stickers. | docs/roadmap/MINDMAP_PLAN.md:1765 | S | unassigned |
| 778 | The exported picture draws each topic's shape since 2026-10-10 (boardmap-1010); a topic's effect and a Phosphor icon still do not reach PNG or SVG... | docs/roadmap/MINDMAP_PLAN.md:1766 | S | unassigned |
| 779 | The document editor's :shortcode: completion keeps its own 248-entry table (DOC_EMOJI_SOURCE); fold it into ICON_EMOJI_SOURCE when the completion can... | docs/roadmap/MINDMAP_PLAN.md:1768 | S | unassigned |
| 780 | Measured nearly clean (WORLD_CLASS 26.5): the showcase map at rest 0 long tasks, 0 gaps over 20 ms; a drag of one node 4 gaps over 20 ms of 605... | docs/roadmap/MINDMAP_PLAN.md:1824 | S | unassigned |
| 781 | The owner, 2026-10-11, verbatim. "also when I change stuff in the tools for a mindmap node, I cant actually see what the difference is until I click... | docs/roadmap/MINDMAP_PLAN.md:1847 | M | unassigned |
| 782 | INBOX 816, the owner 2026-10-11, verbatim: "should thes ebuttons be that big??" (screenshot: a zoomed-out dark map; the selected topic "test" is... | docs/roadmap/MINDMAP_PLAN.md:1855 | M | unassigned |
| 783 | INBOX 817, the owner 2026-10-11, verbatim: "also that popup edit bar for when I try editing text doesn follow the selected text with scroll or zoom... | docs/roadmap/MINDMAP_PLAN.md:1856 | L | unassigned |
| 784 | INBOX 818, the owner 2026-10-11, verbatim: "labels on mind map links dont move with the links". Target: a link's label is placed on the link's path... | docs/roadmap/MINDMAP_PLAN.md:1857 | S | unassigned |
| 785 | INBOX 819, the owner 2026-10-11, verbatim: "also i dont think there is a way to label links on a whiteboard. also can link labels be customisable??"... | docs/roadmap/MINDMAP_PLAN.md:1858 | L | unassigned |
| 786 | INBOX 762, "just now" on an untouched mind map. The Library card's modified time moved without the owner; find what writes updated_at on a board when... | docs/roadmap/UI_MODERNISATION_PLAN.md:1240 | M | unassigned |
| 787 | INBOX 791, UI, mind map, the owner 2026-10-10 22:42Z, three screenshots. "these buttons on the mindmap nodes are a little hard to see and interact... | docs/roadmap/UI_MODERNISATION_PLAN.md:1540 | S | unassigned |
| 788 | INBOX 792, UI, mind map, whiteboard and fit, the owner 2026-10-10 22:45Z, three screenshots. "also i dont think i should be typing in these outline... | docs/roadmap/UI_MODERNISATION_PLAN.md:1541 | M | unassigned |
| 789 | Tidy layout never measured past five nodes; a newly opened map leaves its root under the top bar. Owner: mindmap.md item H. | docs/roadmap/WORLD_CLASS_PLAN.md:990 | S | unassigned |
| 790 | The owner, 2026-09-24, verbatim, with screenshots of the writing dictionary, New from a template, the map's radial menus and two linked map nodes.... | docs/roadmap/WORLD_CLASS_PLAN.md:2580 | L | unassigned |
| 791 | The owner, 2026-09-24, verbatim, with screenshots (placed in agent briefs, two at a time). (a) "in the radials on the mind map, the items like "add... | docs/roadmap/WORLD_CLASS_PLAN.md:2623 | L | unassigned |
| 792 | Section: The draw.io programme: 18 areas, 288 rows, Build first (converted libraries not loaded yet) | docs/roadmap/WHITEBOARD_PLAN.md:921 | L | unassigned |
| 793 | Section: canvasdepth ranked gaps (round 3 and the export panel, frame fit, ends and guides, previews) | docs/roadmap/WHITEBOARD_PLAN.md:1556 | L | unassigned |
| 794 | graphjitter.js-style rAF sampling is useless on a loaded machine (frames 50 to 170 ms apart, load average 10 to 33); the worker-tick measure... | docs/roadmap/agent-remaining/OPEN.md:1872 | M | unassigned |
| 795 | The floating topic rename field is 42px tall over a 17px plate (gcRenameTopicInline, graph-canvas.js); not seen by eye, size it to the plate. | docs/roadmap/agent-remaining/OPEN.md:2027 | S | unassigned |
| 796 | chatSourcesPanel is shared, the renderer is not. Judged not worth it in 2026-09-13: the three surfaces have genuinely different frames around the... | docs/roadmap/agent-remaining/OPEN.md:2049 | S | unassigned |
| 797 | The whiteboard's own View menu (.wb-board-menu) was never reproduced as broken. It has its own max-height-on-open logic (whiteboard.js, the... | docs/roadmap/agent-remaining/OPEN.md:2103 | M | unassigned |
| 798 | INBOX 739's documents half: boards and maps name themselves (wbUntitledNames, whiteboard-templates.js); "Untitled document N" is not built... | docs/roadmap/agent-remaining/OPEN.md:2113 | S | unassigned |
| 799 | Document comments do not yet share the board's thread (Reply, Edit, Resolve, Attach); whiteboard.js wbCommentRow is the shape to reuse (Brief 42). | docs/roadmap/agent-remaining/OPEN.md:2114 | S | unassigned |
| 800 | A topic's effect (shadow, glow) and a Phosphor icon do not reach the PNG or SVG picture (wbBuildExportSvg, the map-node branch); shapes do. | docs/roadmap/agent-remaining/OPEN.md:2115 | S | unassigned |
| 801 | The frame-preview clip was reproduced only as the selection canvas lagging a container that grew mid-drag (fixed); the owner's exact trigger is not... | docs/roadmap/agent-remaining/OPEN.md:2116 | S | unassigned |
| 802 | WHITEBOARD_PLAN "Placed from INBOX, 2026-10-07 (next PR)": 740's frame hint has no edit path and its connector arrow-head set (none, open, triangle... | docs/roadmap/agent-remaining/OPEN.md:2118 | M | unassigned |
| 803 | .dock-chip-row has no user in the page since cb8060a (only a comment in index.html names it). Its rules are in frontend/css/07-whiteboard-misc.css... | docs/roadmap/agent-remaining/OPEN.md:2181 | M | unassigned |
| 804 | Logs More menu .dock-menu-check rows 34.9px/8px against 32px/12.8px items; the board's Start and End menus not measured for end gaps. | docs/roadmap/agent-remaining/OPEN.md:2252 | S | unassigned |
| 805 | .wb-resize-handle title still says "double-click fits the text" on non-frame objects; a dead .wb-map-actions coarse-pointer rule pinned by... | docs/roadmap/agent-remaining/OPEN.md:2261 | S | unassigned |
| 806 | **Already fixed 2026-11-02 (HISTORY.md:51617, "Moved from the plans, 2026-10-31 (wbopen-1031)").** Done, see HISTORY.md "Moved from the plans, 2026-10-31 (wbopen-1031)": what is there about X with no model. | docs/roadmap/agent-remaining/OPEN.md:2285 | S | wbopen-1031 (built f413351; 33 tests pass) |
| 807 | Tables lack merged cells (column widths: built, wb5); Edit data lacks %name% placeholders; .drawio export is not built; a hidden named layer's item eye and... | docs/roadmap/agent-remaining/OPEN.md:2295 | S | wbopen-1031 (5f75052 .drawio export built; placeholders and layer order already built. Left: merged cells in tables (M)) |
| 808 | **Already fixed 2026-11-02 (HISTORY.md:51617, "Moved from the plans, 2026-10-31 (wbopen-1031)").** Done, see HISTORY.md "Moved from the plans, 2026-10-31 (wbopen-1031)": whiteboard gaps (rough, tables, edit data, current layer, drawio pages, hidden-layer eye). | docs/roadmap/agent-remaining/OPEN.md:2379 | S | wbopen-1031 (built; probe 2 of 2, 7 tests pass) |
| 809 | **Already fixed 2026-11-02 (HISTORY.md:51617, "Moved from the plans, 2026-10-31 (wbopen-1031)").** Done, see HISTORY.md "Moved from the plans, 2026-10-31 (wbopen-1031)": laser sweep at 390. | docs/roadmap/agent-remaining/OPEN.md:2382 | S | wbopen-1031 (built 5f75052; 7 of 7 at 390, 1440, dark) |
| 810 | **Already fixed 2026-11-02 (HISTORY.md:51617, "Moved from the plans, 2026-10-31 (wbopen-1031)").** Done, see HISTORY.md "Moved from the plans, 2026-10-31 (wbopen-1031)": a note's fold in the AI tools and exports. | docs/roadmap/agent-remaining/OPEN.md:2415 | S | wbopen-1031 (built; test_ai_board_edit) |
| 811 | **Already fixed 2026-11-02 (HISTORY.md:51617, "Moved from the plans, 2026-10-31 (wbopen-1031)").** Done, see HISTORY.md "Moved from the plans, 2026-10-31 (wbopen-1031)": sidebar sheet at 390 and the fit. | docs/roadmap/agent-remaining/OPEN.md:2417 | S | wbopen-1031 (by design; 525 of 713px sheet, free 120px) |
| 812 | **Already fixed 2026-11-02 (HISTORY.md:51617, "Moved from the plans, 2026-10-31 (wbopen-1031)").** Done, see HISTORY.md "Moved from the plans, 2026-10-31 (wbopen-1031)": ids in an imported folder. | docs/roadmap/agent-remaining/OPEN.md:2425 | S | wbopen-1031 (built; 8 round-trip tests pass) |
| 813 | Row 4 at 390: press to editable 140 to 159 ms against the 50 ms bar (1440 is 24 to 27). Each forced style pass in the add restyles about 830 elements... | docs/roadmap/agent-remaining/OPEN.md:2549 | M | wbpress-1031 (built b3af755, dec5b0b: cause was style recalculation; 390 px press 30 ms at 20 topics and 51 ms at 200 (0.30x and 0.27x of the base, 0.21x at 4x throttle); 1440 30 and 55 ms; not measured on a phone) |
| 814 | **Already fixed 2026-11-02 (HISTORY.md:51617, "Moved from the plans, 2026-10-31 (wbopen-1031)").** Done, see HISTORY.md "Moved from the plans, 2026-10-31 (wbopen-1031)": mapstrip.js fails. | docs/roadmap/agent-remaining/OPEN.md:2556 | S | wbopen-1031 (built 5f75052; 43 of 43) |
| 815 | Watches and conditions in JavaScript are evaluated natively over the frame's values (evaluate, api/run_sandbox.py:250), not stepped: a watch that... | docs/roadmap/agent-remaining/OPEN.md:2578 | S | wbopen-1031 (left: native evaluation is the design; a stepped watch is a rebuild) |
| 816 | Python's runtime still reloads per document opened (ide1's Left row; the frame lives in the panel); the first Debug on a cold runtime waits for it... | docs/roadmap/agent-remaining/OPEN.md:2582 | S | wbopen-1031 (left: needs the Pyodide extra, not installed here; cannot time the cold Debug) |
| 817 | The console on an .html, .css, .svg or .sql file is JavaScript in a fresh worker, not the page's global: the page runs in a frame whose window the... | docs/roadmap/agent-remaining/OPEN.md:2591 | S | wbopen-1031 (left: the html frame's window is not exposed to the sandbox; a design change) |
| 818 | "more access" (INBOX 758): write tools that are not acts (create_category, rename_tag, delete_tag, merge_categories, board and map tools) are named... | docs/roadmap/agent-remaining/OPEN.md:2610 | S | wbopen-1031 (left: seven act rows with inverses (INBOX 758); M) |
| 819 | Row 2's New is still a menu (details#wb-boards-new-menu): a split button (DESIGN.md's recipe) would make it one press; tour.js and reveal-targets.js... | docs/roadmap/agent-remaining/OPEN.md:2652 | S | board1518-1101 (built; HISTORY "Moved from the plans, 2026-11-01 (board1518-1101") |
| 820 | D6 .md preview in the sandbox frame: not done; a Markdown document already has its own Live and Split views. | docs/roadmap/agent-remaining/OPEN.md:2662 | S | unassigned |
| 821 | Python's runtime reloads on every document opened (5.9 to 7.0 s cold at 1440): the sandbox frame lives in the panel, which is rebuilt per document... | docs/roadmap/agent-remaining/OPEN.md:2663 | M | unassigned |
| 822 | p5 in the sandbox logs "Permissions policy violation: accelerometer" to the console (p5's devicemotion listener in a frame without allow); harmless... | docs/roadmap/agent-remaining/OPEN.md:2665 | S | unassigned |
| 823 | I1's later passes: duplicates, entities and dates as kinds in the same table (tensions are built: pass 4 of the night run, ai/facts.py _pair_passes).... | docs/roadmap/agent-remaining/OPEN.md:2708 | M | unassigned |
| 824 | mapcull.md: freehand and link sketches are not culled (a stroke's box is parsed from its path; worth it only when a board with many strokes measures... | docs/roadmap/agent-remaining/OPEN.md:2807 | M | unassigned |
| 825 | whiteboard-tail.md: the AI half of the map needs a model. INBOX 276 (the sketch pad's toolbar at 820) is closed, HISTORY.md, "OPEN.md rows closed... | docs/roadmap/agent-remaining/OPEN.md:2854 | M | unassigned |
| 826 | Skeletons for a board's Library and Notes tabs (INBOX 596): the tabs (whiteboard-library.js, wbLoadLibrary) draw nothing while they load.... | docs/roadmap/agent-remaining/OPEN.md:2897 | M | unassigned |
| 827 | Board and map history: an agent's or another tab's change is not on a board's stack (decision 17 says the event log is the long memory; a board's... | docs/roadmap/agent-remaining/OPEN.md:2933 | M | unassigned |
| 828 | Draw.io phase 2's tail (WHITEBOARD_PLAN 30 to 36 hold the decisions): Phase G's affinity sort (Group by theme proposes named frames, one Undo) and... | docs/roadmap/agent-remaining/OPEN.md:2941 | L | unassigned |
| 829 | The Boards and maps dashboard widget's tall maps: a 25-topic tree-right map draws a 20x40 paper in the 72x40 row box. Cropping a tall map or a square... | docs/roadmap/agent-remaining/OPEN.md:2965 | M | unassigned |
| 830 | Tablet layouts: the Documents dock is two rows at 1024 (its identity asks for 22rem beside the actions); the arc layout of a 430-note notebook framed... | docs/roadmap/agent-remaining/OPEN.md:3004 | M | unassigned |
| 831 | Every frame-cost number is headless Chromium with no GPU, so the ranking and the order of magnitude hold and the absolute milliseconds do not. The... | docs/roadmap/agent-remaining/OPEN.md:3220 | M | unassigned |
| 832 | The whiteboard's PDF export goes through the browser's print dialog, which Playwright cannot complete, so it is the one pair of the scope-by-format... | docs/roadmap/agent-remaining/OPEN.md:3245 | M | unassigned |
| 833 | Drag to delete takes no drag from the board sidebar (Library, Layers) onto the trash target; a drop from the Library panel is not a delete. (from... | docs/roadmap/agent-remaining/OPEN.md:3302 | S | unassigned |
| 834 | Sweeps that only click the Library tab time out, because the Library opens on its last sub-tab. bm1005-sidebar.js and bm1005-mapmulti.js click Boards... | docs/roadmap/agent-remaining/OPEN.md:3310 | S | unassigned |
| 835 | Sweeps that wait a fixed 1.2 s for the whiteboard's lazy bundle flake under load (initWhiteboard is not defined). op5-1005.js and mapviewmenu.js wait... | docs/roadmap/agent-remaining/OPEN.md:3316 | M | unassigned |
| 836 | The board preview labels (mapPreview in note-cards.js) run over the next shape ("Cut the sign-up fro…" across a diamond); the label placement is... | docs/roadmap/agent-remaining/OPEN.md:3317 | S | unassigned |
| 837 | INBOX 641's rest, which INBOX.md no longer holds: Illustrator linked symbols (library_ref in whiteboard-library.js), Photoshop topic effects (a level... | docs/roadmap/agent-remaining/OPEN.md:3326 | M | unassigned |
| 838 | PNG and SVG export draws every topic as one box: wbBuildExportSvg (whiteboard.js) leaves out levels, shapes and Phosphor icons. (from mc1.md) | docs/roadmap/agent-remaining/OPEN.md:3327 | S | unassigned |
| 839 | Large view: whole-body moves (nmb-hop, a hop, a cheer, a startle) move the head 14 to 17px a frame, 2.2 times the rest. Decision needed on slowing... | docs/roadmap/agent-remaining/OPEN.md:3331 | M | unassigned |
| 840 | Chromium quirk: a blend's implicit end keyframe held rotate at its start value under a CSS animation that starts at the same value. The blend avoids... | docs/roadmap/agent-remaining/OPEN.md:3334 | M | unassigned |
| 841 | Sweep coverage not yet done: an open board or map, the graph's node popup and controls sheet at 390, the print dialog, the lightbox, the confirm... | docs/roadmap/agent-remaining/OPEN.md:3345 | M | unassigned |
| 842 | wbMapDropTargetAt (whiteboard-map.js:2661) still converts by hand. Fold it into wbClientToBoard and update the pinned line in... | docs/roadmap/agent-remaining/OPEN.md:3365 | S | unassigned |
| 843 | scratchpad/ui-sweeps/pickers.js throws pickNotesDialog is not defined at its note-picker section, since that dialog moved into the whiteboard bundle.... | docs/roadmap/agent-remaining/OPEN.md:3372 | M | unassigned |
| 844 | The breath's cost in the large view is not settled: a CSS loop cost the view about half its frames, so the swell is written ten times a second. The... | docs/roadmap/agent-remaining/OPEN.md:3374 | M | unassigned |
| 845 | README docs/screenshots/palette.png (and docs/index.html's copy) still shows notes, a document and a board in the palette. Retake it with... | docs/roadmap/agent-remaining/OPEN.md:3378 | S | unassigned |
| 846 | Other [^\]\n]-style scanners may share the ReDoS shape; the markdown link stripping in the frontend is JS and is not covered by the Python oracle... | docs/roadmap/agent-remaining/OPEN.md:3386 | S | unassigned |
| 847 | .wb-shape-caret has pointer-events: none (per the file), so the Shapes split button's caret never gets a click and the closest(".wb-shape-caret")... | docs/roadmap/agent-remaining/OPEN.md:3397 | M | unassigned |
| 848 | **Already fixed 2026-11-02 (HISTORY.md:51617, "Moved from the plans, 2026-10-31 (wbopen-1031)").** Done, see HISTORY.md "Moved from the plans, 2026-10-31 (wbopen-1031)": two partial-failure toasts are red. | docs/roadmap/agent-remaining/OPEN.md:3410 | S | wbopen-1031 (by design) |
| 849 | **Already fixed 2026-11-02 (HISTORY.md:51617, "Moved from the plans, 2026-10-31 (wbopen-1031)").** Done, see HISTORY.md "Moved from the plans, 2026-10-31 (wbopen-1031)": GET /entries/count. | docs/roadmap/agent-remaining/OPEN.md:3431 | M | wbopen-1031 (built; boards 0, note 1, binned 0) |
| 850 | **Already fixed 2026-11-02 (HISTORY.md:51617, "Moved from the plans, 2026-10-31 (wbopen-1031)").** Done, see HISTORY.md "Moved from the plans, 2026-10-31 (wbopen-1031)": Timeline map under Boards chip. | docs/roadmap/agent-remaining/OPEN.md:3432 | S | wbopen-1031 (built; chip reads Boards and maps) |
| 851 | **Already fixed 2026-11-02 (HISTORY.md:51617, "Moved from the plans, 2026-10-31 (wbopen-1031)").** Done, see HISTORY.md "Moved from the plans, 2026-10-31 (wbopen-1031)": Brief 10 in HISTORY. | docs/roadmap/agent-remaining/OPEN.md:3443 | S | wbopen-1031 (built; section present) |
| 852 | **Already fixed 2026-11-02 (HISTORY.md:51617, "Moved from the plans, 2026-10-31 (wbopen-1031)").** Done, see HISTORY.md "Moved from the plans, 2026-10-31 (wbopen-1031)": mention counts. | docs/roadmap/agent-remaining/OPEN.md:3488 | S | wbopen-1031 (built; 33 tests pass) |
| 853 | **Already fixed 2026-11-02 (HISTORY.md:51617, "Moved from the plans, 2026-10-31 (wbopen-1031)").** Done, see HISTORY.md "Moved from the plans, 2026-10-31 (wbopen-1031)": every date and due this week. | docs/roadmap/agent-remaining/OPEN.md:3490 | S | wbopen-1031 (built; 33 tests pass) |
| 854 | **Already fixed 2026-11-02 (HISTORY.md:51617, "Moved from the plans, 2026-10-31 (wbopen-1031)").** Done, see HISTORY.md "Moved from the plans, 2026-10-31 (wbopen-1031)": p5.js sketch kind. | docs/roadmap/agent-remaining/OPEN.md:3532 | M | wbopen-1031 (built; runP5 and vendor/p5.min.js) |
| 855 | Document comments with the board's thread shape (Reply, Edit, Resolve, Attach): a decision first. Comments are ==words== %%remark%% in the text ("no... | docs/roadmap/agent-remaining/OPEN.md:3533 | L | wbopen-1031 (left: L, take the recommendation in the row (text model, shared row)) |
| 856 | Voice: 67 failure toasts in library.js, whiteboard.js and whiteboard-map.js moved; the other 112 JS files still hold their own strings, and only the... | docs/roadmap/agent-remaining/OPEN.md:3614 | M | wbopen-1031 (left: surface by surface (decision 55)) |
| 857 | **Already fixed 2026-11-02 (HISTORY.md:51617, "Moved from the plans, 2026-10-31 (wbopen-1031)").** Done, see HISTORY.md "Moved from the plans, 2026-10-31 (wbopen-1031)": frames.js notes and documents surfaces. | docs/roadmap/agent-remaining/OPEN.md:3649 | S | wbopen-1031 (built; OPEN 857 in frames.js) |
| 858 | A hover frame at 2,000 notes is still 22 to 24 ms here (drawImage and clearRect dominate); the 16 ms target is not met at 2,000; 300 notes was not... | agent/graph100-1011:docs/roadmap/archive/agent-remaining/graph100-1011.md:21 | S | wbopen-1031 (left: needs an idle machine; 22 to 24 ms is drawImage and clearRect) |
| 859 | **Already fixed 2026-11-02 (HISTORY.md:51617, "Moved from the plans, 2026-10-31 (wbopen-1031)").** Done, see HISTORY.md "Moved from the plans, 2026-10-31 (wbopen-1031)": first-ever Graph open warm-up spread. | agent/graph100-1011:docs/roadmap/archive/agent-remaining/graph100-1011.md:22 | S | wbopen-1031 (by design; INBOX 775) |
| 860 | Frame times on the owner's hardware; the desktop webview (pywebview) for the cache, @starting-style and :has. | agent/graph100-1011:docs/roadmap/archive/agent-remaining/graph100-1011.md:26 | S | wbopen-1031 (left: owner hardware and the desktop webview) W34: unverifiable, w34-L2r-1111.md. |
| 861 | There is no calendar events table: core/events.py is the change log, and the timeline's kinds are note, board, document and... | docs/roadmap/BACKLOG.md:1089 | M | wbopen-1031 (left: tried and deferred as L in BACKLOG) |
| 862 | Ink-to-text (handwriting OCR) on sketches. Decided out: scratchpad/audit1005/features.md section 4 row C5 (no on-device ML, the... | docs/roadmap/BACKLOG.md:1883 | S | unassigned |
| 863 | **Already met 2026-11-02 (src/tessellate/ai/autonomous.py:813 `clean_orphaned_board_cards`).** "Deleting a note leaves whiteboard cards behind, no cascade", already swept: autonomous.clean_orphaned_board_cards()... | docs/roadmap/BACKLOG.md:1958 | S | unassigned |
| 864 | A dry-run mode for the agent. Pointer: WORLD_CLASS_PLAN B5 (planner, verifier, per-run undo); ai/autonomous.py:132 holds the... | docs/roadmap/BACKLOG.md:2445 | M | unassigned |
| 865 | A preview + edit step, the mermaid on one side, the rendered diagram on the other. The document editor's Split view is the same... | docs/roadmap/BACKLOG.md:2558 | S | unassigned |
| 866 | Preview, then act: the step 2 split view, with three actions: Open in whiteboard (a new board via wbMermaidLayout, the source... | docs/roadmap/BACKLOG.md:2580 | S | unassigned |
| 867 | Export: any diagram to SVG and PNG, the .mmd source, and Mermaid kept inside the exported SVG (as boards already do); a diagram... | docs/roadmap/BACKLOG.md:2608 | S | unassigned |
| 868 | One shape for one thing. Two ⋯ builders drew different glyphs; two Stop buttons used different icons; the same setting had two... | docs/roadmap/BACKLOG.md:3869 | S | unassigned |
| 869 | Parity programme, the next brief per surface (full tables in ANALYSIS.md). Whiteboard: the draw.io reader and shape-library... | docs/roadmap/BACKLOG.md:4246 | L | unassigned |
| 870 | Briefs 8 to 10 ( autocomplete and rail, job runtime B2, Library card recipe and widget frame): unmarked; verify then close or build | docs/roadmap/SESSION_BRIEFS.md:312 | M | unassigned |
| 871 | Brief 44: the draw.io programme, editor phases (catalogue and converter landed) | docs/roadmap/SESSION_BRIEFS.md:1447 | L | unassigned |
| 872 | Brief 45 part 2: act on the census (split whiteboard.js initWhiteboard 3730 lines, documents.js, 133 duplicated blocks, 40 dead defs, 424 downward references) | docs/roadmap/SESSION_BRIEFS.md:1496 | L | unassigned |
| 873 | Briefs 61 to 63: services for whiteboard and files (26b), data out of code (26c), runners and embedder (26d) | docs/roadmap/SESSION_BRIEFS.md:1618 | L | unassigned |
| 874 | The grid wants equal heights, and the photograph pays for them. The tile is a column, the frame is the one child that grows, with a 9rem floor and a... | docs/roadmap/UI_MODERNISATION_PLAN.md:346 | M | unassigned |
| 875 | The count and the fold share one line of facts, which is the Files rows' own .library-file-meta shape rather than a new one. They are still two... | docs/roadmap/UI_MODERNISATION_PLAN.md:372 | L | unassigned |
| 876 | INBOX 793, UI, whiteboard, the owner 2026-10-10 22:48Z, two screenshots: "also I think the view and board dropdown menus in the whiteboard need a bit... | docs/roadmap/UI_MODERNISATION_PLAN.md:1542 | S | unassigned |
| 877 | INBOX 794, UI, whiteboard library, the owner 2026-10-10 22:52Z, screenshot: "also the previews in the library arent vissually accurate to what is... | docs/roadmap/UI_MODERNISATION_PLAN.md:1543 | M | unassigned |
| 878 | Whiteboard: export-selection popover opens a full-height list in the wrong place; arrow drawn shows both caps as Arrow in properties; missing... | docs/roadmap/WHITEBOARD_PLAN.md:609 | L | unassigned |
| 879 | Mid-work drop, 2026-09-20, verbatim (the owner), two screenshots. "the rotate line and circle dont sit at the top center of a group selection in the... | docs/roadmap/WHITEBOARD_PLAN.md:648 | L | unassigned |
| 880 | Recommendation, not a change, 2026-09-19 (the session). The reverted outside commit added right-drag to pan the board, filtered so a right-click... | docs/roadmap/WHITEBOARD_PLAN.md:696 | L | unassigned |
| 881 | The small conventions every canvas user takes for granted. The owner, verbatim: "I cant do things on the whiteboard and mindmap like double clcike... | docs/roadmap/WHITEBOARD_PLAN.md:770 | L | unassigned |
| 882 | The owner, 2026-09-24, verbatim. "in the whiteboard, the arrange dropdown menu appears above the top bar, cutting off the contents" (only the Order... | docs/roadmap/WHITEBOARD_PLAN.md:798 | L | unassigned |
| 883 | The owner, 2026-09-24, verbatim, with the board export dialog and two lightbox screenshots. "is there a way to better design all instances of these... | docs/roadmap/WHITEBOARD_PLAN.md:830 | L | unassigned |
| 884 | contrast.js never visits a board or a map (documents was added 2026-10-04). Brief: add whiteboard and mindmap to its TABS with a seeded board (cards... | docs/roadmap/WHITEBOARD_PLAN.md:852 | M | unassigned |
| 885 | The owner, 2026-10-06, verbatim, with an OKR board from the new templates (frame titles "Objective one", hints "A goal worth the quarter") and a... | docs/roadmap/WHITEBOARD_PLAN.md:872 | L | unassigned |
| 886 | The owner, 2026-10-07, verbatim, with a board made from the flowchart template (Start, Do the first step, Did it work?, Try again, End) after... | docs/roadmap/WHITEBOARD_PLAN.md:885 | L | unassigned |
| 887 | The owner, 2026-10-07, verbatim: "also in the whiteboard and mindmap, there's no way to reset a object back to default style". No such action exists... | docs/roadmap/WHITEBOARD_PLAN.md:897 | M | unassigned |
| 888 | The edge arrows also ignore resize and drag (the owner, 2026-10-07, verbatim: "can you fix the edge arrows and line arrows not moving or rotating... | docs/roadmap/WHITEBOARD_PLAN.md:908 | M | unassigned |
| 889 | Measured clean (WORLD_CLASS 26.5): the showcase board at rest has 0 long tasks and 0 gaps over 20 ms in 3 s; a drag of one object has 1 gap over 20... | docs/roadmap/WHITEBOARD_PLAN.md:1550 | M | unassigned |
| 890 | INBOX 797, the owner 2026-10-10 23:02Z: "Also I feel like the mindmap and whiteboard are still missing a lot of features and options and stuff that... | docs/roadmap/WHITEBOARD_PLAN.md:1554 | L | unassigned |
| 891 | One export panel, one recipe. Every Export opens the same panel: a live preview on the left, options on the right, and one primary "Export" with the... | docs/roadmap/WHITEBOARD_PLAN.md:1585 | M | unassigned |
| 892 | The preview is the file. It renders from the same function that writes the file: the PDF's pages, the PNG at its scale, the HTML in a sandboxed... | docs/roadmap/WHITEBOARD_PLAN.md:1591 | M | unassigned |
| 893 | The options per format. - All formats: the format and file name. - PDF: page size, orientation, margins, light or print theme, a header or footer... | docs/roadmap/WHITEBOARD_PLAN.md:1596 | M | unassigned |
| 894 | Nothing is lost silently. The panel lists what the format cannot carry (an ink stroke in Markdown, a video in a PDF) before export. | docs/roadmap/WHITEBOARD_PLAN.md:1605 | S | unassigned |
| 895 | "Show more" shows only when the card's content overflows its size, measured by scrollHeight > clientHeight after layout and re-measured on resize.... | docs/roadmap/WHITEBOARD_PLAN.md:1625 | M | unassigned |
| 896 | Cards resize freely, to any width and height: no snap to preset sizes. Guided snaps instead, while dragging: to a neighbour's width or height, to the... | docs/roadmap/WHITEBOARD_PLAN.md:1626 | M | unassigned |
| 897 | Images and files in a card scale with the card's width: images keep their ratio up to the card's width, and a file chip is one line that truncates... | docs/roadmap/WHITEBOARD_PLAN.md:1627 | S | unassigned |
| 898 | A double-click on a card's resize handle fits the card to its content (the same gesture as a frame's fit, INBOX 821). | docs/roadmap/WHITEBOARD_PLAN.md:1628 | S | unassigned |
| 899 | INBOX 826, the owner 2026-10-11, verbatim (screenshots: a selected note card with no edge arrows; the Start and End menus): "I still feel like the... | docs/roadmap/WHITEBOARD_PLAN.md:1633 | M | unassigned |
| 900 | E1. A note card gets the edge arrows. Its arrow makes a new empty note card joined by a link (copying a note's text would duplicate a note); a shape... | docs/roadmap/WHITEBOARD_PLAN.md:1638 | S | unassigned |
| 901 | E2. Ends added: outlined triangle, concave (stealth) arrow, dot, cross, half arrow, double arrow; and an end size (small, medium, large) beside each... | docs/roadmap/WHITEBOARD_PLAN.md:1639 | S | unassigned |
| 902 | E3. One signature end, "MemoryMap": an open chevron with the brand mark's node dot at its tip, drawn from the mark's own geometry; it sits first... | docs/roadmap/WHITEBOARD_PLAN.md:1640 | S | unassigned |
| 903 | E4. Dragging out a new shape, text box or frame shows the move guides, snaps the moving corner to them, and shows the size ("120 x 80") beside the... | docs/roadmap/WHITEBOARD_PLAN.md:1641 | M | unassigned |
| 904 | C1. Decision E1, with help: the arrow's title, the Guide topic and the manual path. | docs/roadmap/WHITEBOARD_PLAN.md:1645 | S | unassigned |
| 905 | C2. Decision E2: the six ends and the end size, in the Start and End menus, the map's link menu and the export. | docs/roadmap/WHITEBOARD_PLAN.md:1646 | S | unassigned |
| 906 | C3. Decision E3: the signature end, three candidates measured at 1x and 2x, one taken. | docs/roadmap/WHITEBOARD_PLAN.md:1647 | S | unassigned |
| 907 | C4. Decision E4: guides, corner snap and the size readout while drawing. | docs/roadmap/WHITEBOARD_PLAN.md:1648 | S | unassigned |
| 908 | C5. Decision E5: the audit table here, then its top five per surface; it lists the small taken-for-granted things too (Brief 87's list). | docs/roadmap/WHITEBOARD_PLAN.md:1649 | S | unassigned |
| 909 | INBOX 829, the owner 2026-10-11, verbatim (a board card's preview: grey blocks and squiggles): "board map previews need a lot of work, redesigning... | docs/roadmap/WHITEBOARD_PLAN.md:1653 | L | unassigned |
| 910 | P1. A preview is the board itself, drawn small: the real colours, shapes, connectors and the first words of each card, rendered off-screen to an... | docs/roadmap/WHITEBOARD_PLAN.md:1656 | M | unassigned |
| 911 | P2. A map's preview is its real tree: the central topic's title legible, branches in their colours, two levels deep. | docs/roadmap/WHITEBOARD_PLAN.md:1657 | S | unassigned |
| 912 | P3. The card shows the preview cropped to the content's bounds, the title, items and last edited; an empty board shows an empty-state line, not a... | docs/roadmap/WHITEBOARD_PLAN.md:1658 | S | unassigned |
| 913 | Whiteboard board-preview minimap NaN rects: not reproduced 2026-10-05 (six boards, 0 errors at 1440 and 390, errors.js); see worldclass-1005c.md. | docs/roadmap/WORLD_CLASS_PLAN.md:972 | S | unassigned |
| 914 | Quick wins (Fable, 05:20): five features the plans did not list, each a day or less, each with the site. (a) Undo on every delete toast: notes... | docs/roadmap/WORLD_CLASS_PLAN.md:1571 | L | unassigned |
| 915 | Brief 45 part 2 (Opus): act on WORLD_CLASS_PLAN section 24; split whiteboard.js (initWhiteboard is 3730 lines, cx 653) and documents.js along seams... | docs/roadmap/archive/agent-remaining/census-1010.md:3 | M | unassigned |
| 916 | 7983f71a7: scratchpad/stencils/convert_stencils.py, render_compare.js, five converted libraries and the Apache-2.0 NOTICE and LICENSE in... | docs/roadmap/archive/agent-remaining/drawio-1010.md:10 | M | unassigned |
| 917 | c18ce1fa3: WHITEBOARD_PLAN "The draw.io programme, 2026-10-10" (18 areas, 288 table rows, Build first, Decisions). | docs/roadmap/archive/agent-remaining/drawio-1010.md:14 | L | unassigned |
| 918 | Nothing loads the converted sets yet. They sit in frontend/board-library/drawio/, outside the non-recursive glob in routes_board_library.py and... | docs/roadmap/archive/agent-remaining/drawio-1010.md:28 | S | unassigned |
| 919 | wbPortFractions does not read data.ports yet (whiteboard.js 2457); the converter writes it (rebased to the first row's box). Phase 1.... | docs/roadmap/archive/agent-remaining/drawio-1010.md:34 | L | unassigned |
| 920 | Stroke width fidelity: the converter writes 2 board pixels per stencil unit; draw.io's strokewidth="inherit" follows the cell's width. Not compared... | docs/roadmap/archive/agent-remaining/drawio-1010.md:41 | S | unassigned |
| 921 | Bare <rect/> ops (2,378 across all libraries, zero area): faithful to stencils.min.js, counted, drawn as nothing; if a shape looks short a stroke is... | docs/roadmap/archive/agent-remaining/drawio-1010.md:44 | S | unassigned |
| 922 | Not converted: the other 199 libraries (24.1 MB of JSON; run convert_stencils.py --min-js <fork>/src/main/webapp/js/stencils.min.js --out DIR, about... | docs/roadmap/archive/agent-remaining/drawio-1010.md:47 | L | unassigned |
| 923 | 775 "the cluster fills about a fifth of the canvas; after Fit, about half" and "the bubbles overlap": not reproduced here. Seeded 34 notes, 34 links... | docs/roadmap/archive/agent-remaining/graphfeel-1010.md:6 | M | unassigned |
| 924 | ~~Open: notes leaving the picture vanish rather than fade out (gcBornAlpha fades new ones in only; graph-canvas.js).~~ **W34: fixed** (w34-L1-1111.md) | docs/roadmap/archive/agent-remaining/graphfeel-1010.md:21 | S | unassigned |
| 925 | Board open timed from a direct openWhiteboardBoard(id) call, not from a click on the Library tile; document open from openDocument(id), not a click.... | docs/roadmap/archive/agent-remaining/measure-1010.md:6 | M | unassigned |
| 926 | ~~Test shapes (kwargs turn, salt, dialogue, result keys readings, grounding kind, part kinds computed and help) are proposals; the building session may...~~ **W34: stale** (w34-L1-1111.md) | docs/roadmap/archive/agent-remaining/spec39-1010.md:16 | S | unassigned |
| 927 | ~~Unit conversion (Gemini's pint) and the "what time is it" / "reading time" shapes were dropped, not rebuilt: "convert 5 km to miles" is read as a...~~ **W34: fixed** (w34-L1-1111.md) | docs/roadmap/archive/agent-remaining/triage-1010.md:28 | S | unassigned |
| 928 | Section: Phase 6: the node panel redesign (popup agent) remainder | docs/roadmap/GRAPH_PLAN.md:121 | M | unassigned |
| 929 | Section: Still open after KG1 to KG9 (knowledge graph) | docs/roadmap/GRAPH_PLAN.md:536 | L | unassigned |
| 930 | INBOX 839, graph: only the drag's heat is changed (graph-worker.js dragHeat). A single-tick 7.1px step still shows in one of two 8px runs (a... | docs/roadmap/agent-remaining/OPEN.md:1869 | M | unassigned |
| 931 | A topic drag writes its core note's pin with its own PUT /graph/pin beside the group's one PUT /graph/pins (gcDragEnd); one write. | docs/roadmap/agent-remaining/OPEN.md:2028 | S | unassigned |
| 932 | scratchpad/ui-sweeps/graphfslightbox.js reads .lightbox in the tick it calls the lazy openLightbox; the sweep needs an await. | docs/roadmap/agent-remaining/OPEN.md:2029 | S | unassigned |
| 933 | Topics becoming categories is Brief 39b's (GRAPH_PLAN "Decision made, 2026-10-10"). | docs/roadmap/agent-remaining/OPEN.md:2030 | S | unassigned |
| 934 | Constellation yellow stars are about 2.1:1 in light; the Notes rows/cards toggle is 28x24. | docs/roadmap/agent-remaining/OPEN.md:2269 | S | unassigned |
| 935 | Notes leaving the picture vanish instead of fading out. | docs/roadmap/agent-remaining/OPEN.md:2396 | S | unassigned |
| 936 | The close-other-menus fix covers the graph's three head buttons only; app-wide it needs about 98 bytes of app-scripts room. | docs/roadmap/agent-remaining/OPEN.md:2397 | S | unassigned |
| 937 | **Already built 2026-11-02 (a30d-1102; the row asked for Save and Cancel: contentsRenameTopic, library.js, and the note panel via gcRenameTopicInline, graph-canvas.js, both add the Save the name and Keep the old name buttons with mousedown kept off the field so a blur does not pre-empt Cancel).** contentsRenameTopic (library.js) and the note-panel rename (graph.js) still save on blur. | docs/roadmap/agent-remaining/OPEN.md:2433 | S | unassigned |
| 938 | The 13.0 gate's "every offence per decision" for decisions 9 to 17 are stylesheet counts from the plan's method paragraph, not from the sweep; still... | docs/roadmap/agent-remaining/OPEN.md:2678 | S | unassigned |
| 939 | The graph signal needs an open note, and the Notes list rarely has one. file: frontend/js/app.js, id: search-open-note. The list passes entry_id only... | docs/roadmap/agent-remaining/OPEN.md:2695 | L | unassigned |
| 940 | The Writing Room's stretch: measured at 1440x900 light on the two NOTE_SURFACES boxes only, the graph's two note boxes not opened. (The table full... | docs/roadmap/agent-remaining/OPEN.md:2924 | L | unassigned |
| 941 | Chromium only, mostly 1440x900, no second browser and no real touch device. The graph's world constant in gcWorldFor (1.6 to 1.25) is reasoned above... | docs/roadmap/agent-remaining/OPEN.md:3210 | M | unassigned |
| 942 | Owner's test (2026-10-07): "How do I change the widgets?" got the whole Dashboard paragraph. A how-to should lead with its step sentence and keep the... | docs/roadmap/agent-remaining/OPEN.md:3356 | M | unassigned |
| 943 | The card tooltip and the graph still show a deduced reason as "(73% confidence, deduced)", not a strength word. (from tidy691-1006.md) | docs/roadmap/agent-remaining/OPEN.md:3403 | S | unassigned |
| 944 | Brief 4 (Settings two-pane, 54 paragraphs): WORLD_CLASS_PLAN.md:1019 says the 54 paragraphs "not re-checked here, so still open". (from... | docs/roadmap/agent-remaining/OPEN.md:3438 | S | unassigned |
| 945 | Graph topics as categories ("How are they different from categories??", the graph agent's hand-off in archive/agent-remaining/graph-1010.md): not in... | docs/roadmap/agent-remaining/OPEN.md:3473 | S | unassigned |
| 946 | Adjacency matrix: no crossing edges at all, so it stays readable when a force graph has turned into wool. Worth it only once... | docs/roadmap/BACKLOG.md:614 | M | unassigned |
| 947 | Timeline-graph: the graph laid out left-to-right by date, links as arcs. §10's Timeline tab does the axis; this would do the axis... | docs/roadmap/BACKLOG.md:618 | M | unassigned |
| 948 | Galaxy / starfield: notes as stars sized by access count, links as faint filaments. The dashboard's "notebook constellation"... | docs/roadmap/BACKLOG.md:630 | M | unassigned |
| 949 | Plain force-directed stays the default; everything else is a picker. | docs/roadmap/BACKLOG.md:637 | S | unassigned |
| 950 | The Graph options row's toggles (Similarity/Entities/Documents/Hide unlinked/Labels) were bare switches with muted text, hard to... | docs/roadmap/BACKLOG.md:3385 | S | unassigned |
| 951 | Decide what the graph is *for*. It is currently a picture plus a thing the AI can walk. The two uses pull in different... | docs/roadmap/BACKLOG.md:3737 | M | unassigned |
| 952 | Graph node popup panel redesign (screenshot, 00:50; the owner: "include redesigning the graph node popup panels in the graph redesign plan"): title... | docs/roadmap/GRAPH_PLAN.md:231 | L | unassigned |
| 953 | Hovering a node grows it into its own halo (INBOX 149, the owner: "can you make graph nodes temporarily expand to fill their glow bubble when I hover... | docs/roadmap/GRAPH_PLAN.md:324 | M | unassigned |
| 954 | A real local model's name/kind entity extraction and a topic's sentence were never run here (no model in the sandbox); both fall back cleanly. | docs/roadmap/GRAPH_PLAN.md:538 | S | unassigned |
| 955 | VC11, D3 hierarchy layouts as a category overview (M, rank 11). D3's hierarchy module is 15 exports with 2 called; treemap, pack and partition would... | docs/roadmap/GRAPH_PLAN.md:599 | M | unassigned |
| 956 | The graph is not idle at rest: scratchpad/ui-sweeps/frames.js counted 1, 9 and 10 long tasks (58 to 70 ms) in 3 s, 150 to 170 ms of script a second... | docs/roadmap/GRAPH_PLAN.md:603 | M | unassigned |
| 957 | /graph is 22 ms for 45 KB of 71 notes; 10 of that is _payload_key (routes_graph.py:667). Not measured at 5,000 notes. | docs/roadmap/GRAPH_PLAN.md:604 | S | unassigned |
| 958 | INBOX 798, the owner 2026-10-10 23:27Z, screenshot: "the graph is still completely broken 😞 I miss how it used to move 😞 look at how the movement is... | docs/roadmap/GRAPH_PLAN.md:608 | S | unassigned |
| 959 | INBOX 799, the owner 2026-10-10 23:45Z: "Alright work autonomously to fix, finish,redesign, improve and extend everything. I will be at work. Impress... | docs/roadmap/GRAPH_PLAN.md:609 | L | unassigned |
| 960 | INBOX 802, graph, the owner 2026-10-11 03:35Z, verbatim: "The graph movement is a lot closer to how it is on main and better than you had it, but I... | docs/roadmap/GRAPH_PLAN.md:615 | L | unassigned |
| 961 | The card is a picture and one paragraph about it. Its name is on the photograph, its description under it, clamped to two lines, and nothing else is... | docs/roadmap/UI_MODERNISATION_PLAN.md:333 | S | unassigned |
| 962 | INBOX 796, bug, graph, the owner 2026-10-10 23:00Z, two screenshots: "dropdown menus in the graph dont close when another is opened causing a visual... | docs/roadmap/UI_MODERNISATION_PLAN.md:1545 | M | unassigned |
| 963 | INBOX 803, UI and bugs, the owner 2026-10-11 03:35Z to 03:45Z, screenshots (Loose ends, While you were away, Kinds of link, the OCR workspace, the... | docs/roadmap/UI_MODERNISATION_PLAN.md:1558 | L | unassigned |
| 964 | Notes (8) and Graph (9) docks are over the seven-control ceiling. Owner: docks.md; the fix is a second "more" group, not hiding. | docs/roadmap/WORLD_CLASS_PLAN.md:978 | S | unassigned |
| 965 | The SVG graph path stays behind a flag until the drag gate is met on a quieter machine. Owner: GRAPH_PLAN Phase 2. | docs/roadmap/WORLD_CLASS_PLAN.md:984 | L | unassigned |
| 966 | 54 paragraphs still outside popovers. Owner: Brief 4. | docs/roadmap/WORLD_CLASS_PLAN.md:987 | S | unassigned |
| 967 | Three notes at 1440x900 fill 0.80 of the free height (0.798 measured): the fit's zoom clamp (GRAPH_FIT_MAX_ZOOM 2.5, graph.js) stops it; a larger... | docs/roadmap/archive/agent-remaining/graphfeel-1010.md:7 | S | unassigned W34: true-deferred (owner call), w34-fix1-1111.md. |
| 968 | ~~Open: Arc stays a line by design; a person who picks it by mistake sees "a broken graph". Recommendation for INBOX: say the layout's name on the map...~~ **W34: fixed** (w34-L1-1111.md) | docs/roadmap/archive/agent-remaining/graphfeel-1010.md:22 | S | unassigned |
| 969 | Section: Phase 5: the calendar as the third view (Brief 55 landed; deepened rows in sections 10 to 12) | docs/roadmap/TIMELINE_PLAN.md:207 | M | unassigned |
| 970 | Touch drag on a tablet, a day page dropped on another day, and a 1,000-note month are built but not driven. | docs/roadmap/agent-remaining/OPEN.md:2300 | S | unassigned |
| 971 | The contrast and errors sweeps were not run on the calendar view. | docs/roadmap/agent-remaining/OPEN.md:2301 | S | unassigned |
| 972 | The feed's Last-year range filters by when a note was written, so a note about a day this month written over a year ago shows in the calendar and not... | docs/roadmap/agent-remaining/OPEN.md:2302 | S | unassigned |
| 973 | cifix5: a quit with the reminder notifier running can wait up to the job pool's 5 s deadline (stop_notifier runs after the pool's shutdown path). | docs/roadmap/agent-remaining/OPEN.md:2342 | S | unassigned |
| 974 | The service worker acts with the session token stored in the notification's data: a scoped reminder token is with the followups agent. | docs/roadmap/agent-remaining/OPEN.md:2365 | S | unassigned |
| 975 | Timeline row 8's bar, click to rows under 300 ms at 96 notes: 329 at load 6 to 8 (app side 73 to 164); a 57 to 70 ms task right after the rows paint... | docs/roadmap/agent-remaining/OPEN.md:2525 | M | unassigned |
| 976 | Reminders at 390: the floating New (#reminders-new) can lie over the row under it (2 overlaps in one run, 0 in the final; 10-responsive.css:1762). | docs/roadmap/agent-remaining/OPEN.md:2526 | S | unassigned |
| 977 | The reminder edit form cannot change an alert (shell-reminders.js reminderEditForm); an alert is set by words only. | docs/roadmap/agent-remaining/OPEN.md:2529 | S | unassigned |
| 978 | A timeline-days preference arriving after the click renders the timeline twice (once in nine runs at 5,000 notes). | docs/roadmap/agent-remaining/OPEN.md:2531 | S | unassigned |
| 979 | A load-more in flight when the range changes leaves the new range at 100 rows until a scroll (timeline.js timelineLoadMore). | docs/roadmap/agent-remaining/OPEN.md:2533 | S | unassigned |
| 980 | The tree table, timeline and fishbone are column layouts that tidy the whole map on every add (wbMapTidyBranchScope); not timed at 200 topics. | docs/roadmap/agent-remaining/OPEN.md:2553 | S | unassigned |
| 981 | A reminder ticked before done_at existed counts as done but in no week. | docs/roadmap/agent-remaining/OPEN.md:2567 | S | unassigned |
| 982 | libtl-0926.md: the Timeline feed lays out about 39 times a second while scrolling (the rows' content-visibility: auto, INBOX 400's trade); the... | docs/roadmap/agent-remaining/OPEN.md:2799 | L | unassigned |
| 983 | The tour: the Timeline's Options and the reminders' More were measured at 390 only. (The fresh data dir walk and widths 600 to 1100 are done... | docs/roadmap/agent-remaining/OPEN.md:3000 | M | unassigned |
| 984 | Dismissed reminder notifications: a dismissed reminder notification never returns (status.js notificationsDismissed, keyed reminder:<id>), so a... | docs/roadmap/agent-remaining/OPEN.md:3013 | M | unassigned |
| 985 | Dashboard and Timeline: D6's streak (the calendar strip and the day before and after are built, daystrip.js; a streak count has no surface: the dock... | docs/roadmap/agent-remaining/OPEN.md:3017 | M | unassigned |
| 986 | 24 single-line toast("...", true) calls with a literal message remain in frontend/js; some are expected conditions (validation, "nothing to ... yet")... | docs/roadmap/agent-remaining/OPEN.md:3303 | M | unassigned |
| 987 | 401s in the server log (/preferences, /insights/*, /reminders) when pages boot while sweeps unlock; not reproduced in one clean boot. (from... | docs/roadmap/agent-remaining/OPEN.md:3319 | S | unassigned |
| 988 | settings-packages.js (lines 421, 562 and 591 on this head): the toast call on result.message is red when the package action did not start (the flag... | docs/roadmap/agent-remaining/OPEN.md:3409 | M | unassigned |
| 989 | ai-tools.js says "Open Settings, Models" in words, and none is a link. A button on the toast is the next step and is a new control. (from... | docs/roadmap/agent-remaining/OPEN.md:3411 | S | unassigned |
| 990 | The reminders presets menu lays out while closed: 7 overlaps over the filter chips at 1440 (TIMELINE_PLAN 11 row 2). (from deepen-b-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3428 | S | unassigned |
| 991 | Brief 5 (Timeline): TIMELINE_PLAN.md:7 names it as the plan's hand-off and the plan is open. (from briefs-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3439 | S | unassigned |
| 992 | Brief 6 (pagination, scheduler): tests/test_lists_paginate.py the brief names does not exist; TIMELINE_PLAN.md:93 depends on its helper. (from... | docs/roadmap/agent-remaining/OPEN.md:3440 | S | unassigned |
| 993 | Rule 4 "says what happened, why": 24 literal error toasts still fall back to Open the logs rather than an action of their own... | docs/roadmap/agent-remaining/OPEN.md:3519 | M | unassigned |
| 994 | Rule 4: the 338 toast(e.message, true) calls get the why from plainHttpError and the default Open the logs; a per-site retry is not built. | docs/roadmap/agent-remaining/OPEN.md:3520 | S | unassigned |
| 995 | Reminders: "Add" and "Mark done" push nothing (shell-reminders.js; 7 write functions, 3 with an undo path); Ctrl+Z restores neither. | docs/roadmap/agent-remaining/OPEN.md:3547 | S | unassigned |
| 996 | Documents: "Delete" shows a toast Undo, but Ctrl+Z goes to the open editor's history (surfaceHistory in status.js, the Documents branch) so the... | docs/roadmap/agent-remaining/OPEN.md:3548 | M | unassigned |
| 997 | "every weekday", "every other friday" and yearly repeats save once: routes_reminders.Recurring holds only daily, weekly and monthly; the Reading... | docs/roadmap/agent-remaining/OPEN.md:3575 | S | unassigned |
| 998 | Quick note: a reminder chip on a note saved while the server is away (the outbox, saveQuickNote's result.queued branch) is dropped; the note is kept.... | docs/roadmap/agent-remaining/OPEN.md:3578 | S | unassigned |
| 999 | Palette: only the reminder act has a row (quickAddPaletteRow); a note or meeting act and the search window chip (CHAT_PLAN section 1 row 7) wait for... | docs/roadmap/agent-remaining/OPEN.md:3579 | S | unassigned |
| 1000 | Timeline at 390: a long window chip wraps to two lines (39 px), no overflow. [f2-1010] | docs/roadmap/agent-remaining/OPEN.md:3580 | S | unassigned |
| 1001 | Agent: propose_act is offered in the reminder and tag tool groups only; whether a 1 to 3B model calls Calculate rather than computing is not verified... | docs/roadmap/agent-remaining/OPEN.md:3613 | S | unassigned |
| 1002 | **Already met 2026-11-02 (frontend/js/documents-ai.js:279-301 `pushDocAiUndo` calls `pushUndo`).** pushDocAiUndo (documents.js:11084) already calls pushUndo; nothing to fold. It has no toast by design (the AI edit log is its second way back).... | docs/roadmap/agent-remaining/OPEN.md:3657 | S | unassigned |
| 1003 | Step 5b, decision 6 (a primary calendar paired with the reminders): TIMELINE_PLAN section 9 (Phase 5, Brief 55); renderReminderCalendar... | docs/roadmap/agent-remaining/OPEN.md:3666 | L | unassigned |
| 1004 | App scripts (TOTAL_CAP, the 27 counted) 320,352 to 317,151 (cap 320,600, unchanged): room 248 to 3,449. Moved to lazy files: the bell's panel... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/room101-1011.md:4 | M | unassigned |
| 1005 | ~~847 Notification actions on their own row: 0 actions share the close button's row at 1440 and 390.~~ **W34: fixed** (w34-L1-1111.md) | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/ownerfix3-1011.md:8 | S | unassigned |
| 1006 | A server restart under an open page shows the toast "Locked" with "Open the logs" and "Report this" when a setting is changed (the PUT is silent, so... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/scan-1011.md:9 | M | unassigned |
| 1007 | A reminder needs text and a due time. (shell-reminders.js:1528) is shown when only one of the two is missing; naming the missing one needs... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/scan-1011.md:11 | S | unassigned |
| 1008 | The notification bell and Activity count: not a defect, but a fresh launch with no model lists "Warming up the filing model" every launch (one row... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/scan-1011.md:12 | M | unassigned |
| 1009 | 847: toasts built outside status.js (none found by grep) and the notification bell's rows (not changed). | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/ownerfix3-1011.md:21 | S | unassigned |
| 1010 | ~~Timeline table rows: the hover ground is tr:hover td on a border-collapse: collapse table, so the row ends are square (06-timeline-dialogs.css:459)...~~ **W34: fixed** (w34-L1-1111.md) | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/ownerfix3-1011.md:26 | S | unassigned |
| 1011 | ~~Found, not mine: a sticky toast sits under an open modal (the first-run "Check for updates automatically?" confirm, z-index 2100), so Allow cannot be...~~ **W34: fixed** (w34-L1-1111.md) | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/lansafe-1011.md:46 | M | unassigned |
| 1012 | A reload loses the page's watch on a running transcription; the card still reads its state from the server, but no notification fires for a run that... | agent/voiceup-1011:docs/roadmap/archive/agent-remaining/voiceup-1011.md:16 | S | unassigned W34: true, w34-L2r-1111.md. |
| 1013 | Events as bands. Next: no events calendar table exists (the events in core/events.py is the change log, a different thing); it... | docs/roadmap/BACKLOG.md:697 | M | unassigned |
| 1014 | What the user can already see (the step timeline), so it stops re-narrating | docs/roadmap/BACKLOG.md:971 | S | unassigned |
| 1015 | Toasts and confirmations that name the thing ("Moved Passport renewal to the bin; it was linked to 3 notes"). | docs/roadmap/CHAT_PLAN.md:733 | S | unassigned |
| 1016 | Reminders and meetings: the action items and decisions read back as sentences; a reminder's notification says why it matters, from its note. | docs/roadmap/CHAT_PLAN.md:739 | S | unassigned |
| 1017 | Cheap suggestions: follow-up questions, suggested searches, autofill (titles, tags, reminder wording, link reasons) composed first; a model is asked... | docs/roadmap/CHAT_PLAN.md:754 | S | unassigned |
| 1018 | Proactive, rarely and on real signals: a few times a day at most, only for something specific (a due reminder, a resurfaced note, a pattern), never... | docs/roadmap/CHAT_PLAN.md:834 | S | unassigned |
| 1019 | "the notification said it takes a while to pull the first image for searxng but ive already used multiple times" Recommendation: show the first-pull... | docs/roadmap/CHAT_PLAN.md:853 | M | unassigned |
| 1020 | "Issues with these sentences: The picture in Girl with bell shows The image shows a snowy scene with a girl holding a bell, and there is a signature... | docs/roadmap/CHAT_PLAN.md:881 | M | unassigned |
| 1021 | INBOX 561 timeline day strip redesign: built in 543, waits on the owner's look | docs/roadmap/INBOX.md:37 | S | unassigned |
| 1022 | Briefs 2 to 6 (lints, prefs/api.stream, Settings two-pane, Timeline phases 1 and 2, pagination and one scheduler): unmarked; verify against the code, close or build | docs/roadmap/SESSION_BRIEFS.md:72 | M | unassigned |
| 1023 | "The circle on the vertical line on the left isnt in line with the text line" Recommendation: align the rail circle to the first line's centre in... | docs/roadmap/TIMELINE_PLAN.md:204 | S | unassigned |
| 1024 | Month and week grids, agenda on the phone. Month at 1024 and up, week at 768 and up, the feed (already an agenda) below that. The grid is CSS grid... | docs/roadmap/TIMELINE_PLAN.md:216 | M | unassigned |
| 1025 | What sits on the grid: reminders (at their time), day notes (as the cell's head), notes by their written date (dots, not rows, so the grid stays... | docs/roadmap/TIMELINE_PLAN.md:220 | M | unassigned |
| 1026 | Drag reschedules a reminder; dropping a note on a day sets its daily-note date only when it is a day note; anything else is refused with the hint.... | docs/roadmap/TIMELINE_PLAN.md:224 | S | unassigned |
| 1027 | ICS both ways for reminders only: export the reminders as one .ics (routes_reminders), import an .ics as reminders with a report; no account sync... | docs/roadmap/TIMELINE_PLAN.md:227 | S | unassigned |
| 1028 | Keys: T today, arrows move the day, PageUp/PageDown the month, Enter opens the day's feed, N a new reminder on the day. | docs/roadmap/TIMELINE_PLAN.md:230 | S | unassigned |
| 1029 | One calendar (INBOX 768, 2026-10-10): section 9's view is the one grid; the reminders tab's toggle opens it filtered to reminders, and... | docs/roadmap/TIMELINE_PLAN.md:232 | S | unassigned |
| 1030 | VC2, D3's time scale and axis for the timeline and the calendar (M, rank 2). timeline.js builds its date ticks by hand (51 lines with Date( in... | docs/roadmap/TIMELINE_PLAN.md:252 | M | unassigned |
| 1031 | "The whole begin the app for the first time workflow is a mess, popups and notifications clash with each other, the tour gets cancelled, to much goes... | docs/roadmap/UI_MODERNISATION_PLAN.md:1290 | M | unassigned |
| 1032 | 811, the owner, verbatim: "something about the design or smth of those buttons in the notifications and buttons in notifications in the noficiations... | docs/roadmap/UI_MODERNISATION_PLAN.md:1563 | L | unassigned |
| 1033 | 813, the owner, verbatim: "also idk but I feel like it looks awkward when some things have borders and other things dont in a header but idk im not... | docs/roadmap/UI_MODERNISATION_PLAN.md:1564 | M | unassigned |
| 1034 | Every destructive action has an Undo toast, not only deletes of notes. | docs/roadmap/WORLD_CLASS_PLAN.md:2368 | S | unassigned |
| 1035 | Every date and time follows one setting (12 or 24 hour, the locale's order); the status bar clock, the timeline and the reminders do not agree today... | docs/roadmap/WORLD_CLASS_PLAN.md:2369 | S | unassigned |
| 1036 | Toasts overlap content (the reminder toast covers the dashboard head at 1093x614); they belong in a reserved corner above the status bar. | docs/roadmap/WORLD_CLASS_PLAN.md:2391 | S | unassigned |
| 1037 | Dashboard widgets were counted for interactive elements in a notebook of plain notes (no reminders, bookmarks, tensions, activity); clicks were not... | docs/roadmap/archive/agent-remaining/measure-1010.md:7 | S | unassigned |
| 1038 | Decision 32: only the recurrence insight; streak, drift, contrast, load and time-of-day rules, the Tidy and dashboard "Patterns" line, and the slot... | docs/roadmap/archive/agent-remaining/spec39-1010.md:5 | S | unassigned W34: owner-call (tracked in the plans), w34-L1-1111.md. |
| 1039 | Next PR first: INBOX 641 remainder (Illustrator linked symbols, Photoshop layer effects, Miro reactions), 643 OneNote, 644 meeting notes redesign, 646 code editor to VS Code standard | docs/ROADMAP.md:212 | L | unassigned |
| 1040 | Section: Phase 6: responsive by device (partly built) | docs/roadmap/DOCUMENTS_PLAN.md:314 | M | unassigned |
| 1041 | Section: Phase 8: one editor everywhere | docs/roadmap/DOCUMENTS_PLAN.md:396 | M | unassigned |
| 1042 | Section: Section 21: the code editor against VS Code, and writing checks everywhere (INBOX 646) | docs/roadmap/DOCUMENTS_PLAN.md:544 | L | unassigned |
| 1043 | Section: Section 17: the live view for professional use, phases open | docs/roadmap/DOCUMENTS_PLAN.md:1088 | L | unassigned |
| 1044 | Section: Section 23: the code editor as an IDE, phases after I1 to I3 (Briefs 69 to 71 landed) | docs/roadmap/DOCUMENTS_PLAN.md:1267 | L | unassigned |
| 1045 | **Already fixed 2026-11-02 (frontend/js/notes-list.js:3394 `topicRepeatsTag`, the row says built earlier).** BUILT earlier (notes-list.js topicRepeatsTag, tests/test_code_documents.py:345; found stale 2026-10-18, open-1018.md): A tag-named topic's chip repeats the tag chip beside it on the card (noteTopicChip, notes-list.js); dedupe against the card's own tags. | docs/roadmap/agent-remaining/OPEN.md:2026 | S | unassigned |
| 1046 | An uploaded document cannot be given a reading from outside the app. POST /media/{id}/ocr and /media/{id}/vision-ocr both answer 415 for a PDF... | docs/roadmap/agent-remaining/OPEN.md:2131 | L | unassigned |
| 1047 | .sidebar-head is off the dock grammar, deliberately. It carries min-height: var(--sidebar-toggle-size), a negative margin-top that meets the... | docs/roadmap/agent-remaining/OPEN.md:2165 | M | unassigned |
| 1048 | Band 3 (600 to 820): the header is two rows, 128px at 819. The band's recorded design (the strip cannot fit beside the wordmark at any width in the... | docs/roadmap/agent-remaining/OPEN.md:2176 | M | unassigned |
| 1049 | The capture box still moves 2.4px down and 1.6px left on the first click (strip 40 to 42.4px; CodeMirror line padding). | docs/roadmap/agent-remaining/OPEN.md:2268 | S | unassigned |
| 1050 | Open: a misspelled place ("westen australia") is not read. | docs/roadmap/agent-remaining/OPEN.md:2287 | S | unassigned |
| 1051 | The code document's dock at 390 is 238px tall (four rows). | docs/roadmap/agent-remaining/OPEN.md:2349 | S | unassigned |
| 1052 | A code file's editor is capped at 78ch and centred (09-editor.css:59), so its panel is 724px at 1440. | docs/roadmap/agent-remaining/OPEN.md:2432 | S | unassigned |
| 1053 | DOCUMENTS 24 row 7 (the list row's ⋮) not built: it would remake INBOX 722; keep the overlay. | docs/roadmap/agent-remaining/OPEN.md:2498 | S | unassigned |
| 1054 | **Already fixed 2026-11-02 (HISTORY.md:270, "OPEN.md rows closed, 2026-10-18").** BUILT 2026-10-18 (HISTORY, open-1018; the popover at 1440 for dock and find not opened by the sweep): DOCUMENTS 24 row 11: 78 controls, none with its own data-help-for; one '?' per section plus a command per control. | docs/roadmap/agent-remaining/OPEN.md:2499 | S | unassigned |
| 1055 | Replace in every document reads each document by one request; and it has no dock-menu row. | docs/roadmap/agent-remaining/OPEN.md:2501 | S | unassigned |
| 1056 | Statistics row 3 (VC3, Brief 75): the page's two charts use the hand-built askChartTicks; tick labels did not collide at 1440 or 390 with this data... | docs/roadmap/agent-remaining/OPEN.md:2563 | S | unassigned |
| 1057 | D1's folder again: the brief says frontend/js/run/debug-*.js; the pass is frontend/js/run-debug.js for ide1's reason (65 lints glob... | docs/roadmap/agent-remaining/OPEN.md:2576 | S | unassigned |
| 1058 | Variables show one level (a repr, 200 characters): no expanding a list or an object into its children (VS Code's tree). _mm_names in PY_RUNNER, show... | docs/roadmap/agent-remaining/OPEN.md:2577 | S | unassigned |
| 1059 | Python breakpoints persist per document for the tab's life (DOC_DEBUG.breaks), not across a reload; VS Code keeps them in the workspace. | docs/roadmap/agent-remaining/OPEN.md:2581 | S | unassigned |
| 1060 | F11 is shared: Step into while a session is on, Focus mode otherwise (documents.js); the palette row says "F11 while debugging". Brief 71's... | docs/roadmap/agent-remaining/OPEN.md:2583 | S | unassigned |
| 1061 | The breakpoint lane is 0.875rem wide (1.5rem under a coarse pointer); touch.js does not measure gutters, so a tap's size on it is not checked. | docs/roadmap/agent-remaining/OPEN.md:2584 | S | unassigned |
| 1062 | Debug (Brief 70) is a row of DOC_PANEL_TABS since the merge, its pane docDebugView(); Ctrl+Shift+D (the registry's newDocument... | docs/roadmap/agent-remaining/OPEN.md:2588 | M | unassigned |
| 1063 | "the problems panel fed by every linter": harper is a prose linter and prose documents have no panel (the panel is mounted for code files... | docs/roadmap/agent-remaining/OPEN.md:2589 | S | unassigned |
| 1064 | "the JS parse errors sucrase reports": Problems shows the editor's own JS and TS parse errors (the Lezer tree check, the same lines); sucrase's own... | docs/roadmap/agent-remaining/OPEN.md:2590 | M | unassigned |
| 1065 | A console line that never ends (while (true)) is stopped after 10 s (60 s for Python's first line) by terminating the worker, which loses the run's... | docs/roadmap/agent-remaining/OPEN.md:2592 | S | unassigned |
| 1066 | The split's second half carries the language, theme, gutter and wrap of the first, not its completions, lint, snippets or the run panel... | docs/roadmap/agent-remaining/OPEN.md:2593 | S | unassigned |
| 1067 | Ctrl+K Ctrl+S opens the palette for a moment before the sheet (the app's Ctrl+K is kept in code files); VS Code waits for the second chord instead. | docs/roadmap/agent-remaining/OPEN.md:2594 | S | unassigned |
| 1068 | Live Text on the continuous (scroll) layout of a PDF: only the single-page stage carries the layer. library.js ocrBuildScrollPages. | docs/roadmap/agent-remaining/OPEN.md:2598 | S | unassigned |
| 1069 | D5 "load this CSV document as a table": the sandbox's SQL worker takes tables: [{name, columns, rows}] (_SQL_WORKER), but no panel action picks a CSV... | docs/roadmap/agent-remaining/OPEN.md:2659 | S | unassigned |
| 1070 | D9 stdlib completion and signature help from a generated table (scripts/gen_python_completions.py over the installed Pyodide's inspect): not started. | docs/roadmap/agent-remaining/OPEN.md:2660 | S | unassigned |
| 1071 | D9 ruff-wasm lint and format: DOCUMENTS 25 row 4's (Brief 42's linters), not started here. | docs/roadmap/agent-remaining/OPEN.md:2661 | S | unassigned |
| 1072 | A JSX .js document (the jsx alias) runs without the JSX pass; only .tsx paths get it (runStripTypes). | docs/roadmap/agent-remaining/OPEN.md:2666 | S | unassigned |
| 1073 | evidence_checks is the one switch with no runner: stored and shown in Settings, gating nothing. margin_reader (api/routes_editor.py), model_bench... | docs/roadmap/agent-remaining/OPEN.md:2716 | M | unassigned |
| 1074 | codecomplete.md: Python Run via a Pyodide download extra (INBOX 404's recommendation, needs the owner's yes to a download kind of extra) and... | docs/roadmap/agent-remaining/OPEN.md:2783 | M | unassigned |
| 1075 | pass2.md: typing in a note in a 230-note list costs about 12ms of CodeMirror input handling per key; the Library's lists have no user-owned order to... | docs/roadmap/agent-remaining/OPEN.md:2833 | M | unassigned |
| 1076 | perfpolish.md: the document gutter writes a height and reads a layout per gutter. The menu exit is closed, HISTORY.md, "OPEN.md rows closed... | docs/roadmap/agent-remaining/OPEN.md:2838 | M | unassigned |
| 1077 | ARCH-02, the save at 5,000 notes: POST /entries p50 210 ms (one line) and 345 ms (400 words), not under 150; 390 to 615 ms with 384-wide vectors... | docs/roadmap/agent-remaining/OPEN.md:3031 | M | unassigned |
| 1078 | Sweeps: touch.js needs timeout 300; revealcell.js at 390 needs the editor opened first; errors.js took "Target crashed" at a tab switch (2026-10-05)... | docs/roadmap/agent-remaining/OPEN.md:3083 | M | unassigned |
| 1079 | A PDF's page picture was never seen drawn: this sandbox has no PDF render extra (pdfpages.available() is false, /media/pdf-page/... answers 404), so... | docs/roadmap/agent-remaining/OPEN.md:3232 | M | unassigned |
| 1080 | No screen reader was run against aria-current="location" in the documents outline. [doc-sidebar.md] | docs/roadmap/agent-remaining/OPEN.md:3239 | S | unassigned |
| 1081 | A real log stream under load. The live pill reads green and the filters hide the right count (275 records on the seeded server), but nothing here... | docs/roadmap/agent-remaining/OPEN.md:3260 | M | unassigned |
| 1082 | Undo counts for documents (2/11), OCR (0/5) and meetings (1/6) are a static read of each handler for pushUndo, not driven; Brief 74's undo.js... | docs/roadmap/agent-remaining/OPEN.md:3293 | S | unassigned |
| 1083 | At 1440 with the Connections rail open, the Notes dock wraps nine controls onto a second row; DESIGN.md says seven at most. A judgement for the dock... | docs/roadmap/agent-remaining/OPEN.md:3318 | S | unassigned |
| 1084 | DOC_EMOJI_SOURCE (documents-prose.js) is a second emoji table beside ICON_EMOJI_SOURCE (icon-picker.js). (from mc1.md) | docs/roadmap/agent-remaining/OPEN.md:3328 | S | unassigned |
| 1085 | Playwright reported the topic strip's Text toggle "not visible" after an icon pick, though its rect is 58px wide; mc1-iconpicker.js works around it... | docs/roadmap/agent-remaining/OPEN.md:3329 | S | unassigned |
| 1086 | An interrupted glide restarts at the ease's peak speed: a star's fastest step after a second Regenerate is 13 to 16px against 7px before it. A... | docs/roadmap/agent-remaining/OPEN.md:3375 | M | unassigned |
| 1087 | Settings, Packages has its own Embedding models list beside Search and index's, which does the same and more. Recommendation: Packages keeps a single... | docs/roadmap/agent-remaining/OPEN.md:3382 | S | unassigned |
| 1088 | A word touching a suggestion's marker is never a spelling finding: docSpellable (documents.js) rejects a + on either side, and {++ and ++} are +.... | docs/roadmap/agent-remaining/OPEN.md:3394 | M | unassigned |
| 1089 | The prose-tool grammar rules at a CodeMirror lint tooltip (.cm-tooltip-lint) in code documents are not suppressed while a pointer menu is open. Only... | docs/roadmap/agent-remaining/OPEN.md:3395 | S | unassigned |
| 1090 | The note strip, owner's report (d): every control is 6.4px inside the strip's edge at the default look (measured 320 to 1920). The owner's exact... | docs/roadmap/agent-remaining/OPEN.md:3400 | S | unassigned |
| 1091 | Each VC row is unbuilt; the script and test are the only code (Brief 75 says no code beyond them). (from vendor-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3434 | S | unassigned |
| 1092 | Brief 16 (documentation refined): no HISTORY record of the pass. (from briefs-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3446 | S | unassigned |
| 1093 | Cost: decide is 34 ms a call at 5,000 synthetic notes against 8 to 17 ms for the old tally (scratchpad/filing-tools/perf.py); Tidy's uncategorised... | docs/roadmap/agent-remaining/OPEN.md:3470 | S | unassigned |
| 1094 | Decision 43: the currency table is dated (utilities.RATES_DATE, src/memorymap/ai/utilities.py:113) but has no Settings editor. | docs/roadmap/agent-remaining/OPEN.md:3494 | S | unassigned |
| 1095 | Rule 5 "a long-running task that does not register fails": the lint is a table of thread sites (tests/test_activity.py THREAD_SITES); request-bound... | docs/roadmap/agent-remaining/OPEN.md:3521 | S | unassigned |
| 1096 | Word import of tracked changes: the .docx carries w:ins/w:del, but Mammoth reads an insertion as accepted text and drops a deletion... | docs/roadmap/agent-remaining/OPEN.md:3534 | M | unassigned |
| 1097 | A fenced code block's language (js) is not written to Word, so it comes back as a bare fence (docWordBlocks, the pre branch); header cells come back... | docs/roadmap/agent-remaining/OPEN.md:3535 | S | unassigned |
| 1098 | Docks: 0 sibling intersections in 12 surfaces at 5 widths (at 390: 81 bars and 266 sibling pairs examined), so the dock grammar holds; the counts... | docs/roadmap/agent-remaining/OPEN.md:3559 | S | unassigned |
| 1099 | Deeper than 3 (light): 4 Library > Contents > Probe documentDocument·# sections·#h ago > Outline. | docs/roadmap/agent-remaining/OPEN.md:3563 | S | unassigned |
| 1100 | Note editor: a sum only when written with = ("12 + 7 = 21"); a column of amounts with a "Total:" line is not checked (ai/offers.py _SUM). [f4-1010] | docs/roadmap/agent-remaining/OPEN.md:3605 | S | unassigned |
| 1101 | clip.html and capture.html keep unhashed ?v=<version> stamps (static, not rewritten as index.html and offline.html are), so an edit inside one... | docs/roadmap/agent-remaining/OPEN.md:3636 | S | unassigned |
| 1102 | Warm-load speed gain is inside the noise on a shared machine (466 to 570 ms against 613 to 672 ms) because stamped files were already immutable in... | docs/roadmap/agent-remaining/OPEN.md:3637 | M | unassigned |
| 1103 | 5 foreign keys without a leading index (entity_mentions x2, document_bookmarks x2, entry_bookmarks.bookmark_id) and 64 filtered columns without one... | docs/roadmap/agent-remaining/OPEN.md:3646 | M | unassigned |
| 1104 | editor.js:inlineAiUndo (owner's list of six): the inline AI bar's Undo reverts a CodeMirror transaction on unsaved field text, which rule 1.8 gives... | docs/roadmap/agent-remaining/OPEN.md:3655 | S | unassigned |
| 1105 | Decision 8, indent guides: the active line is built (library-lazy.css .cm-activeLineGutter); indent markers are not in the vendored CodeMirror bundle... | docs/roadmap/agent-remaining/OPEN.md:3667 | S | unassigned |
| 1106 | Brief 86's suggest code (status.js) should call meaningAlts for its candidates once it lands beside this. | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/meaning94-1011.md:7 | S | unassigned |
| 1107 | scratchpad/ui-sweeps/notif1005-sweep.js still reads a .notif-side element that no longer exists (stale before this work); its checks of controls on... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/phonegraph-1011.md:8 | S | unassigned |
| 1108 | Sweep trap: context.route does not see requests the page's service worker serves (after the first load), so a CSS or JS override in a sweep silently... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/room101-1011.md:9 | M | unassigned |
| 1109 | Help's topics keep their document order when searching, so the best match by name can sit below others in the same filter (help top-3 38/60 against... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/meaning94-1011.md:15 | S | unassigned |
| 1110 | ~~853: a multi-region reading and a PDF with many pages (the seeded reading is one region); Tesseract is not installed here, the text was posted to...~~ **W34: fixed** (w34-unv1-1111.md) | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/ownerfix3-1011.md:20 | S | unassigned |
| 1111 | Document outline / table of contents, word-count goal, reading time, all three, not just the outline. renderDocOutline builds the... | docs/roadmap/BACKLOG.md:109 | M | unassigned |
| 1112 | Sizing (UI zoom #zoom-slider and Text size exist; Next: line-height and measure are two new tokens read by .entry-content and the... | docs/roadmap/BACKLOG.md:1124 | M | unassigned |
| 1113 | Study / revision: Next: nothing exists (no flashcard or review code in src/ or frontend/js, checked 2026-10-05); the seam is... | docs/roadmap/BACKLOG.md:1201 | M | unassigned |
| 1114 | Before adding more: audit which existing widgets render markdown and which don't (§8's ideas-parking-lot bug) so a new widget... | docs/roadmap/BACKLOG.md:1656 | S | unassigned |
| 1115 | Repair actions from that screen, not just a diagnosis: Next: SearXNG Reinstall and Settings, Models' pull exist; the buttons to... | docs/roadmap/BACKLOG.md:1708 | M | unassigned |
| 1116 | Sources outside the app. Next: Entry.source_url/source_title exist (note-cards.js:1859 draws the badge); the paste-a-highlight... | docs/roadmap/BACKLOG.md:2100 | L | unassigned |
| 1117 | Compression/archival for rarely-used notes, documents, files and chats. (needs owner) Pointer: the same decision as section 26... | docs/roadmap/BACKLOG.md:2302 | L | unassigned |
| 1118 | Web clipper. Pointer: WORLD_CLASS_PLAN D9 "Links and the web clipper"; the clipper agent owns it. read_url exists server-side... | docs/roadmap/BACKLOG.md:2414 | S | unassigned |
| 1119 | A Mermaid editor: a Live and Split view for a fence (source beside the drawing, errors inline with the line), snippets per kind... | docs/roadmap/BACKLOG.md:2602 | S | unassigned |
| 1120 | ATTACHMENT_SUFFIXES (routes_files.py) is broad: pdf/docx/xlsx/csv/md/ txt/code/zip. Attachments are downloaded, never served... | docs/roadmap/BACKLOG.md:2790 | S | unassigned |
| 1121 | MEDIA_SUFFIXES is images + PDF only, and its comment explains why: that folder is served, and *"the AI can write into this folder... | docs/roadmap/BACKLOG.md:2793 | M | unassigned |
| 1122 | *"No import from other note apps"*, overstated. POST /import/markdown and /import/directory (routes_settings.py) already... | docs/roadmap/BACKLOG.md:2901 | M | unassigned |
| 1123 | **Already built 2026-11-02 (a30d-1102; both buttons carry data-help-for and go through wireHelpPopover, index.html:1606 and 2549; tests/test_ui_recipes.py::test_no_help_panel_is_hand_wired).** #search-help and #capture-help were bespoke hand-rolled click toggles from before initHelpToggle existed, never migrated: missing... | docs/roadmap/BACKLOG.md:3370 | M | unassigned |
| 1124 | The lightbox's document preview panel was translucent (var(--card), deliberately glass) sitting over the lightbox's own darkened... | docs/roadmap/BACKLOG.md:3392 | M | unassigned |
| 1125 | "Compose a document from these notes" (gap 10): Next: see section 102 item 10 and section 26. The agent can already do it from a... | docs/roadmap/BACKLOG.md:3581 | M | unassigned |
| 1126 | Live organise-suggestions while typing (gap 9): Next: see section 102 item 9. Offer it *alongside* the audited background... | docs/roadmap/BACKLOG.md:3584 | M | unassigned |
| 1127 | Bookmark URL editing, reported five times, working every time it was tested. The handler was correct and the flow was reproduced... | docs/roadmap/BACKLOG.md:3650 | L | unassigned |
| 1128 | Whether the selection popup should appear in the note editor at all is now moot: it does. What is *not* settled is its dismissal... | docs/roadmap/BACKLOG.md:3664 | M | unassigned |
| 1129 | Highlights as a queryable collection, backlinks panel, conflict-safe editor, per-note pinned AI context, bulk tag editing, all... | docs/roadmap/BACKLOG.md:3670 | M | unassigned |
| 1130 | Three places independently decide what markdown means: Next: one grammar module under frontend/js/ (a table of token, open... | docs/roadmap/BACKLOG.md:3701 | M | unassigned |
| 1131 | Decide whether the note editor is a text box or an editor. It now has a toolbar, a preview and a selection menu, while Documents... | docs/roadmap/BACKLOG.md:3746 | L | unassigned |
| 1132 | Three grammars for markdown (§111.1): Next: section 111.1 carries the brief. MD_ACTIONS, INLINE_MD, and editor.js's "/" menu each... | docs/roadmap/BACKLOG.md:3845 | M | unassigned |
| 1133 | Nothing that is broken. This session alone found a null dereference that silently aborted openConversation, a panel that opened... | docs/roadmap/BACKLOG.md:3861 | M | unassigned |
| 1134 | Note and document helpers: a summary line on a long note, "what links these two notes" on a link, a title suggestion from a note's own words. | docs/roadmap/CHAT_PLAN.md:737 | S | unassigned |
| 1135 | The same features in every surface: Live decorations, note autocomplete, the / menu, the selection toolbar (bold, italic, code, link, list, ask the... | docs/roadmap/DOCUMENTS_PLAN.md:420 | L | unassigned |
| 1136 | One recipe in 09-editor.css: .note-surface with the three size variants, the tokens' radius, --control-h for the strip, the same focus ring; a lint... | docs/roadmap/DOCUMENTS_PLAN.md:425 | S | unassigned |
| 1137 | The engine loads on the first focus of any surface, once per page. | docs/roadmap/DOCUMENTS_PLAN.md:431 | L | unassigned |
| 1138 | The chat composer is not a note editor: it gets and / only, and keeps its own recipe (send on Enter). | docs/roadmap/DOCUMENTS_PLAN.md:432 | S | unassigned |
| 1139 | Languages missing: Visual Basic (vb, vbScript legacy modes), p5.js (JS plus p5 completions from the vendored p5.min.js), PHP stays out (section... | docs/roadmap/DOCUMENTS_PLAN.md:554 | S | unassigned |
| 1140 | Per-language completions and snippets: CSS property values for the property under the cursor, Python, JS, Java, C#, C, C++ keywords and common forms... | docs/roadmap/DOCUMENTS_PLAN.md:557 | M | unassigned |
| 1141 | Where each is used: every code surface (documents, code blocks in notes, chat code, board code blocks) shares one engine and one set of options... | docs/roadmap/DOCUMENTS_PLAN.md:561 | L | unassigned |
| 1142 | Help moves with it (standing order 13). Measure with a Playwright sweep per language; no new required dependency (CLAUDE.md, the owner's offline... | docs/roadmap/DOCUMENTS_PLAN.md:564 | S | unassigned |
| 1143 | "I want to be able to use the documents tab as a plain text editor like before as a view option (not the default though)", "and also if I select a... | docs/roadmap/DOCUMENTS_PLAN.md:655 | L | unassigned |
| 1144 | "i still cant click on a grammar or misspeled underlined word and see a popup like in a realworld editor like obsidian, word, notion, vs code." It... | docs/roadmap/DOCUMENTS_PLAN.md:686 | M | unassigned |
| 1145 | "the whole documents sidebar and ui needs fixing and the document editor still needs a lot of refinement and cleaning but its still in development so... | docs/roadmap/DOCUMENTS_PLAN.md:713 | S | unassigned |
| 1146 | The page is a page. The text sits in a measure with real margins rather than filling its pane to the edge, and the margin is the same on both sides... | docs/roadmap/DOCUMENTS_PLAN.md:1126 | S | unassigned |
| 1147 | The measure is capped. A line of prose has a comfortable length and a wide monitor is not a reason to abandon it. | docs/roadmap/DOCUMENTS_PLAN.md:1129 | S | unassigned |
| 1148 | Nothing is added to the chrome. Every phase below either changes what is already drawn or reveals something on approach. | docs/roadmap/DOCUMENTS_PLAN.md:1131 | S | unassigned |
| 1149 | No new recipe without its lint, per standing order 11. | docs/roadmap/DOCUMENTS_PLAN.md:1133 | S | unassigned |
| 1150 | D1. One run protocol for every language: {kind, source, path, stdin, tests} in and {row, level, line, col} rows out, over postMessage to the sandbox... | docs/roadmap/DOCUMENTS_PLAN.md:1292 | M | unassigned |
| 1151 | D2. The Python debugger is bdb in the Pyodide worker, not a re-implementation: a Bdb subclass posts each stop (frame, line, locals, globals, the... | docs/roadmap/DOCUMENTS_PLAN.md:1297 | L | unassigned |
| 1152 | D3. The JavaScript debugger is JS-Interpreter (Neil Fraser, Apache-2.0, ES5, about 150 KB minified, pure JS, no network), vendored under... | docs/roadmap/DOCUMENTS_PLAN.md:1307 | M | unassigned |
| 1153 | D4. TypeScript runs: sucrase strips the types (no checking) and the row that said "does not compile" becomes "runs without type checking". The same... | docs/roadmap/DOCUMENTS_PLAN.md:1315 | S | unassigned |
| 1154 | D5. SQL runs against SQLite in the browser: sql.js (MIT, SQLite compiled to WASM, about 1.3 MB, lazy, measured first) under frontend/vendor/sqljs; a... | docs/roadmap/DOCUMENTS_PLAN.md:1318 | M | unassigned |
| 1155 | D6. Previews are a kind of run: .css previews against a sample document, .svg and .md render in the sandbox frame, .html as today, the p5 kind (INBOX... | docs/roadmap/DOCUMENTS_PLAN.md:1324 | M | unassigned |
| 1156 | D7. Tests are a kind of run: Python runs unittest discovery over the document (and pytest where the extra carries Pyodide's own pytest wheel... | docs/roadmap/DOCUMENTS_PLAN.md:1328 | M | unassigned |
| 1157 | D8. Two consoles: a Python REPL (Pyodide, the document's namespace after a run) and a JavaScript REPL (the worker's global after a run), as one panel... | docs/roadmap/DOCUMENTS_PLAN.md:1334 | M | unassigned |
| 1158 | D9. The Python improvements are deterministic and local: ruff-wasm for lint and format (Brief 42 decides vendoring on its size), stdlib completion... | docs/roadmap/DOCUMENTS_PLAN.md:1339 | M | unassigned |
| 1159 | The owner, 2026-09-21, verbatim: "can you improve the ui and ux of the live view and make it better for professional use and impressive as both a... | docs/roadmap/DOCUMENTS_PLAN.md:1454 | L | unassigned |
| 1160 | The owner, 2026-09-24, verbatim, with screenshots of Settings, Templates, the persona list, a .json document with the formatting bar over it, and the... | docs/roadmap/DOCUMENTS_PLAN.md:1489 | L | unassigned |
| 1161 | Live code blocks in a prose document (the owner, verbatim: "also I want to be able to make special code blocks where the code editor works and code... | docs/roadmap/DOCUMENTS_PLAN.md:1520 | M | unassigned |
| 1162 | "I cant two finger trackpad zoom in or out on documents or images on the ocr workspace?" Recommendation: pinch zoom (ctrl+wheel from a trackpad) on... | docs/roadmap/DOCUMENTS_PLAN.md:1536 | M | unassigned |
| 1163 | "The note capture subtab formatting toolbar wont open :(" Recommendation: reproduce from the Notes Capture subtab, then fix the toolbar's open state... | docs/roadmap/DOCUMENTS_PLAN.md:1538 | S | unassigned |
| 1164 | "Gemini might have removed the spell checker??" (the owner's words in the Gemini thread: "you removed spellchecker.py") Recommendation: keep... | docs/roadmap/DOCUMENTS_PLAN.md:1540 | M | unassigned |
| 1165 | "I saved a website as a bookmark but the icon didnt change" Recommendation: a saved bookmark takes the site's icon at save time and refreshes it on... | docs/roadmap/DOCUMENTS_PLAN.md:1542 | M | unassigned |
| 1166 | "on vs code selected lines have their line number bolded, the line subtly bordered and there are also indentation lines on vs code as well"... | docs/roadmap/DOCUMENTS_PLAN.md:1547 | M | unassigned |
| 1167 | "also I want a better and more cardlike rendering of links or special liks like bookmarks and maybe even the ability to choose special icons or... | docs/roadmap/DOCUMENTS_PLAN.md:1549 | M | unassigned |
| 1168 | "The document editor and whiteboard and mindmap still have many design issues, functionality bugs, poor usability, lack features, and need... | docs/roadmap/DOCUMENTS_PLAN.md:1551 | M | unassigned |
| 1169 | "And we should massively improve, expand, refine and better integrate long form note taking." Recommendation: the long-form path (document editor)... | docs/roadmap/DOCUMENTS_PLAN.md:1553 | M | unassigned |
| 1170 | "Idea: on long form notes and documents, you can define topics, or use special characters, commands etc to label and link sections of documents on... | docs/roadmap/DOCUMENTS_PLAN.md:1558 | M | unassigned |
| 1171 | **Already fixed 2026-11-02 (HISTORY.md:270, "OPEN.md rows closed, 2026-10-18 (open-1018)").** BUILT 2026-10-18 (HISTORY.md, "OPEN.md rows closed, 2026-10-18 (open-1018)"; tag offers dropped, a document has no tags): VC5, FlashText link offers and tag offers (M, rank 5). FlashText is used by ai/taxonomy.py alone (2 of 19 members: add_keyword, extract_keywords)... | docs/roadmap/DOCUMENTS_PLAN.md:1566 | M | unassigned |
| 1172 | VC6, Harper's own dictionary and the other three dialects (S, rank 6). The worker uses 3 of 29 Linter members; import_words and export_words take a... | docs/roadmap/DOCUMENTS_PLAN.md:1567 | S | unassigned |
| 1173 | VC7, the diff and dockerFile modes already in the bundle (S, rank 7). legacy modes 15 of 18 called; diff, dockerFile and the sql factory are bundled... | docs/roadmap/DOCUMENTS_PLAN.md:1568 | S | unassigned |
| 1174 | VC13, the lint panel and fold-all in the palette (S, rank 13). lint is 5 of 12 (gutter and next/previous only; openLintPanel and lintKeymap unused)... | docs/roadmap/DOCUMENTS_PLAN.md:1569 | S | unassigned |
| 1175 | VC17, Emmet's stylesheet syntaxes (L, rank 17, lowest). Emmet is fully used (6 of 6 functions) but 4 of its 10 syntaxes are passed (html, css, xml... | docs/roadmap/DOCUMENTS_PLAN.md:1570 | L | unassigned |
| 1176 | documents.js holds 14 requestAnimationFrame sites, 7 scroll listeners, 3 ResizeObserver and 4 MutationObserver (WORLD_CLASS 26.5, scripts/handlers.py... | docs/roadmap/DOCUMENTS_PLAN.md:1574 | M | unassigned |
| 1177 | INBOX 788, the owner: "can you add code templates as document templates as well??", "maybe even add a code modules library like with the whiteboard... | docs/roadmap/DOCUMENTS_PLAN.md:1578 | M | unassigned |
| 1178 | INBOX 827, the owner 2026-10-11, verbatim (screenshots: a file's "Text extracted from this file" box; the empty Recordings tab; a link's details)... | docs/roadmap/DOCUMENTS_PLAN.md:1582 | M | unassigned |
| 1179 | L1. Extracted text: the disclosure is a quiet row (DESIGN "Row actions"), not a bordered button; open, the text sits in a reading column (body size... | docs/roadmap/DOCUMENTS_PLAN.md:1585 | S | unassigned |
| 1180 | L2. Recordings empty state from DESIGN's empty-state recipe: an icon, one line, Record and Import audio, and a second line saying a meeting's... | docs/roadmap/DOCUMENTS_PLAN.md:1586 | S | unassigned |
| 1181 | L3. A link's details: the card shows icon, title, site and a two-line excerpt; the full extract is behind "Show page text" in the L1 reader, never a... | docs/roadmap/DOCUMENTS_PLAN.md:1587 | S | unassigned |
| 1182 | L4. Folders: drag a link onto another to make a folder (named "Folder", renamed in place), drag into and out of folders, and New folder in the bar... | docs/roadmap/DOCUMENTS_PLAN.md:1588 | S | unassigned |
| 1183 | L5. Each link and folder takes an icon (the site's own, an app icon or an emoji) and a highlight colour from the palette tokens, from its kebab menu... | docs/roadmap/DOCUMENTS_PLAN.md:1589 | S | unassigned |
| 1184 | INBOX 735 p5.js as a document kind and code completion (DOCUMENTS_PLAN 23, Brief 42, Briefs 69 to 71) | docs/roadmap/INBOX.md:67 | M | unassigned |
| 1185 | INBOX 737 debugging for other languages (DOCUMENTS_PLAN 23 decisions D1 to D9, Brief 75 vendoring) | docs/roadmap/INBOX.md:77 | L | unassigned |
| 1186 | INBOX 804 console line border clash and the document assistant's buttons, field and send height (backups part fixed) | docs/roadmap/INBOX.md:159 | S | unassigned |
| 1187 | The lightbox is an image viewer showing a document. Reported: "the lightbox needs improving for file and pdf previews, no sections or info are below... | docs/roadmap/UI_MODERNISATION_PLAN.md:234 | M | unassigned |
| 1188 | Region select → read just that. Asked as a question, and it is a good one: "can there be a way for the user to manually outline and single out... | docs/roadmap/UI_MODERNISATION_PLAN.md:248 | M | unassigned |
| 1189 | The Files sub-tab has to show more than a row can hold. OCR text for a long document does not fit where a photo's caption fits; the row needs a... | docs/roadmap/UI_MODERNISATION_PLAN.md:256 | S | unassigned |
| 1190 | The command palette and Tools & features, and nothing new. Ctrl/Cmd-K reaches "Read a document or image with AI" from any tab, and the features... | docs/roadmap/UI_MODERNISATION_PLAN.md:285 | M | unassigned |
| 1191 | Everything you can do to a picture is a row of the card's kebab, not a control on it: open full size, copy the markdown reference, write a... | docs/roadmap/UI_MODERNISATION_PLAN.md:341 | S | unassigned |
| 1192 | Provenance is inside the fold, with the reading it describes. "Described by X, read by Y" has been called noise twice (INBOX 56 and the second design... | docs/roadmap/UI_MODERNISATION_PLAN.md:354 | S | unassigned |
| 1193 | The description holds its second line open (min-height: 2lh while clamped, picture cards only). A one-line caption left the card 21.8px shorter... | docs/roadmap/UI_MODERNISATION_PLAN.md:380 | M | unassigned |
| 1194 | "I pressed install on the documents package and the progress bars appeared for the vision package and the documents package didn’t progress at all"... | docs/roadmap/UI_MODERNISATION_PLAN.md:1255 | M | unassigned |
| 1195 | "Also it failed to let me view the pdf doc I had as the package wasn’t installex, it should have given me a link to nav to where I can install it or... | docs/roadmap/UI_MODERNISATION_PLAN.md:1257 | M | unassigned |
| 1196 | "idk if it is just me but the ui still needs a more modern and professional polish. I think an issue might be that some of the ui elements, controls... | docs/roadmap/UI_MODERNISATION_PLAN.md:1278 | M | unassigned |
| 1197 | "There needs to be more utility on all features app wide and more ui/ux cleansing" Recommendation: this is the Brief 41 refinement pass plus the... | docs/roadmap/UI_MODERNISATION_PLAN.md:1294 | L | unassigned |
| 1198 | INBOX 788, UI and features, documents and code, the owner 2026-10-10 22:35Z, six screenshots. "the topic edit popup needs a redesign and fix. are... | docs/roadmap/UI_MODERNISATION_PLAN.md:1537 | L | unassigned |
| 1199 | T1. Tidy is one list of reviews with counts; a review opens in place with a back link (not a bordered button beside a small title), its one-line... | docs/roadmap/UI_MODERNISATION_PLAN.md:1590 | S | unassigned |
| 1200 | T4. A menu's first and last items sit one menu padding from its edge, never a group label's or a separator's gap (owner: grammar57, with 813's one... | docs/roadmap/UI_MODERNISATION_PLAN.md:1593 | S | unassigned |
| 1201 | Deleting a space leaves its notes in "All spaces". Read and not reproduced in code: routes_spaces.delete_space hard-deletes every workspace-scoped... | docs/roadmap/WORLD_CLASS_PLAN.md:1544 | L | unassigned |
| 1202 | Suggested links panel UI refine (screenshot: rows of quoted pairs, a wide "Why?" input, a percent chip, Link and X). Owner: Opus, next slot: two note... | docs/roadmap/WORLD_CLASS_PLAN.md:1592 | M | unassigned |
| 1203 | The feature list is inside #models-config, which Settings hides whole when no backend is answering. So with the model server down there is no way to... | docs/roadmap/WORLD_CLASS_PLAN.md:2269 | M | unassigned |
| 1204 | Ctrl+S, Ctrl+Z and Escape behave the same in every editor and dialog (the key contract, 1.6, has no lint for Escape yet). | docs/roadmap/WORLD_CLASS_PLAN.md:2364 | S | unassigned |
| 1205 | Search highlights the match inside the note it opens, and remembers the last few queries. | docs/roadmap/WORLD_CLASS_PLAN.md:2366 | S | unassigned |
| 1206 | Icon consistency. Mixed stroke weights between Phosphor regular and the bold ones on the status bar; one weight app-wide. | docs/roadmap/WORLD_CLASS_PLAN.md:2387 | S | unassigned |
| 1207 | Frontend ids are every id="..." text in index.html, including any inside HTML comments; not checked for false hits. | docs/roadmap/archive/agent-remaining/codemap-1010.md:6 | S | unassigned W34: true, w34-L2r-1111.md. |
| 1208 | ~~tests/test_frontend_wake_sources.py: documents.js raf 14 to 15.~~ **W34: fixed** (w34-L1-1111.md) | docs/roadmap/archive/agent-remaining/graphfeel-1010.md:16 | S | unassigned |
| 1209 | ~~Root cause of the line, as reproduced: the Layout preference holds Tree or Arc (mirrored server-side, MIRRORED_UI_EXTRAS in ai-tools.js), both...~~ **W34: fixed** (w34-L1-1111.md) | docs/roadmap/archive/agent-remaining/graphfeel-1010.md:20 | M | unassigned |
| 1210 | Decision 37: map, document and web-page sources; scrollable web source list. | docs/roadmap/archive/agent-remaining/spec39-1010.md:9 | S | unassigned W34: owner-call (tracked in the plans), w34-L1-1111.md. |
| 1211 | ~~The Gemini misspelling table looks drawn from Wikipedia's lists (CC BY-SA); its origin is unrecorded (docs/THIRD_PARTY.md, Data).~~ **W34: fixed** (w34-L1-1111.md) | docs/roadmap/archive/agent-remaining/triage-1010.md:33 | S | unassigned |
| 1212 | Section: Audio in the notebook: architecture decided, build deferred (partly built by Brief 80, 82, 83, voiceup) | docs/roadmap/WORLD_CLASS_PLAN.md:2135 | L | unassigned |
| 1213 | Section: 28.4 and 28.5 deepened: OCR workspace and audio set rows (Briefs 79, 80 landed; rest open) | docs/roadmap/WORLD_CLASS_PLAN.md:4106 | L | unassigned |
| 1214 | The README's OCR shot is the 0.3.2 capture, in dark: seed-ocr.js (removed 2026-10-12, recoverable from git history) needs a Tesseract binary this sandbox does not have, so it was not retaken with the... | docs/roadmap/agent-remaining/OPEN.md:1962 | S | unassigned |
| 1215 | INBOX 803 item 4 (the OCR workspace's empty squashed box): not reproduced in five states; needs the owner's screenshot or state. | docs/roadmap/agent-remaining/OPEN.md:2267 | S | unassigned |
| 1216 | The recorder saves plain transcript text into the meeting note; the timed lines live only on the recording. /voice/transcribe-meeting still returns... | docs/roadmap/agent-remaining/OPEN.md:2356 | S | unassigned |
| 1217 | The attached-image thumbnail path in the preview (attachmentObjectUrl) was not driven, only inline images. | docs/roadmap/agent-remaining/OPEN.md:2466 | S | unassigned |
| 1218 | Notes cannot link to or embed a recording yet (only entry_id); search does not find recordings. | docs/roadmap/agent-remaining/OPEN.md:2479 | S | unassigned |
| 1219 | Trim decodes the whole file in the page (about 700 MB of samples for an hour). | docs/roadmap/agent-remaining/OPEN.md:2480 | S | unassigned |
| 1220 | Live captions is a palette act, so it cannot be a Quick access tile. | docs/roadmap/agent-remaining/OPEN.md:2481 | S | unassigned |
| 1221 | Brief 81: the stop path is now meetingRecordingStopped; transcription goes through POST /recordings/{id}/transcribe. | docs/roadmap/agent-remaining/OPEN.md:2482 | S | unassigned |
| 1222 | Live translated captions (28.5 row 10, "for ... captions") not built: Brief 82 landed mid-build. | docs/roadmap/agent-remaining/OPEN.md:2489 | S | unassigned |
| 1223 | Only English to Spanish: more pairs are a download block plus a PAIRS row, and the sheet then needs a pair picker. | docs/roadmap/agent-remaining/OPEN.md:2490 | S | unassigned |
| 1224 | Real latency: scratchpad/captions_audio.py through a real whisper-server on the reference laptop (pytest -m captions tests/test_captions_live.py)... | docs/roadmap/agent-remaining/OPEN.md:2506 | M | unassigned |
| 1225 | Accuracy under a cut audio_ctx was read on one sentence only. | docs/roadmap/agent-remaining/OPEN.md:2507 | S | unassigned |
| 1226 | Stop saves a note until Brief 80's recording object lands; then routes_captions._save attaches the audio and makes the transcript its text; the Audio... | docs/roadmap/agent-remaining/OPEN.md:2508 | S | unassigned |
| 1227 | ScriptProcessorNode is deprecated; an AudioWorklet needs a blob: worker the CSP does not allow (captions.js startLiveCaptions). | docs/roadmap/agent-remaining/OPEN.md:2509 | S | unassigned |
| 1228 | A regions cache stored before 2026-10-10 has no words; Live Text appears after the page is read again. routes_files.py PageRead.regions. | docs/roadmap/agent-remaining/OPEN.md:2599 | S | unassigned |
| 1229 | An image's whole reading deleted from the lightbox or the gallery's row menu still clears without the bin (only the workspace's deletes were moved).... | docs/roadmap/agent-remaining/OPEN.md:2600 | M | unassigned |
| 1230 | Undoing a fresh read writes the old text back through the text route, so it keeps the new read's model name ("Read by X") rather than the old one's.... | docs/roadmap/agent-remaining/OPEN.md:2601 | S | unassigned |
| 1231 | undo.js (the trust sweep) does not walk the OCR workspace; ocr79.js measures it instead. | docs/roadmap/agent-remaining/OPEN.md:2602 | S | unassigned |
| 1232 | ocr-reading.md: a page joins the reading panel only once looked at or read (nothing reads ahead, deliberately); nothing was verified with a real... | docs/roadmap/agent-remaining/OPEN.md:2829 | M | unassigned |
| 1233 | Owner's call: RapidOCR ships as an optional extra (Settings, Packages); confirm it against the 2026-10-05 "fully local, vendored" rule... | docs/roadmap/agent-remaining/OPEN.md:3314 | S | unassigned |
| 1234 | Pills still in popups: the Attach picker's five sources (#note-picker-sources, index.html:2842) and pickLibraryItemDialog's sources (selection.js)... | docs/roadmap/agent-remaining/OPEN.md:3343 | M | unassigned |
| 1235 | If the owner means every pill in a popup, these values are next (kept as .seg by DESIGN.md's two-or-three rule): doc-history-filter, ocr-zoom... | docs/roadmap/agent-remaining/OPEN.md:3344 | M | unassigned |
| 1236 | Touch drag from the Library is not tested: HTML5 drag-and-drop does not run on touch. The drag image (its thumbnail and offset) is asserted in source... | docs/roadmap/agent-remaining/OPEN.md:3366 | S | unassigned |
| 1237 | RapidOCR and Tesseract never ran for real here: "ready" and the RapidOCR path are faked through /ocr-readers and monkeypatched tests. A real install... | docs/roadmap/agent-remaining/OPEN.md:3376 | S | unassigned |
| 1238 | Meeting cards show their section headings as raw ## Agenda text, as every note card does. A meeting-aware card preview (when, who, open action items)... | docs/roadmap/agent-remaining/OPEN.md:3406 | S | unassigned |
| 1239 | ~~852 Library sub-tab flicker: layout shift 0.37 to 0.52 became 0.017 (1440) and 0.016 (390).~~ **W34: fixed** (w34-L1-1111.md) | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/ownerfix3-1011.md:6 | S | unassigned |
| 1240 | Left in the counted scripts, each used by two bundles so it needs a shared home or a stand-in: noteFirstImage (library.js only, move with... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/room101-1011.md:7 | S | unassigned |
| 1241 | ~~853 OCR find marks every match, "n of m", Enter and Shift+Enter, prev and next buttons.~~ **W34: fixed** (w34-L1-1111.md) | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/ownerfix3-1011.md:9 | S | unassigned |
| 1242 | ~~library-activity rows keep their ground in a box-shadow spine, not a background.~~ **W34: stale** (w34-L1-1111.md) | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/ownerfix3-1011.md:27 | S | unassigned |
| 1243 | One commit per item was not kept for V1 with V2 and V3 to V7: a staged gate took 12 to 25 minutes under load, so items sharing meetings.js were gated... | agent/voiceup-1011:docs/roadmap/archive/agent-remaining/voiceup-1011.md:10 | S | unassigned |
| 1244 | The plan's Built blocks for V1 to V8, T1, T2 (UI_MODERNISATION_PLAN "Placed from INBOX, 2026-10-11 (voice notes ...)" and "(Tidy ...)") move to... | agent/voiceup-1011:docs/roadmap/archive/agent-remaining/voiceup-1011.md:11 | S | unassigned |
| 1245 | Real transcription: faster-whisper is not installed; every run used a stubbed voice.iter_segments (vu/stubserve.py), and live words used... | agent/voiceup-1011:docs/roadmap/archive/agent-remaining/voiceup-1011.md:14 | S | unassigned W34: unverifiable, w34-L2r-1111.md. |
| 1246 | It would compete for the same CPU. The compression path wants ONNX Runtime and a transformer of its own, running immediately... | docs/roadmap/BACKLOG.md:722 | M | unassigned |
| 1247 | Voice capture beyond dictation. Next: mic-note dictates into the capture box and Save files it (two clicks); a one-tap "record a... | docs/roadmap/BACKLOG.md:2428 | M | unassigned |
| 1248 | A persona changes *voice* and applies to everything. | docs/roadmap/BACKLOG.md:2515 | S | unassigned |
| 1249 | Route by type at upload time: an image goes to media/ (served, narrow allowlist, unchanged), anything else goes to the... | docs/roadmap/BACKLOG.md:2803 | M | unassigned |
| 1250 | Widen MEDIA_SUFFIXES and harden serving (explicit Content-Type, Content-Disposition: attachment, a sandboxed CSP on that route).... | docs/roadmap/BACKLOG.md:2808 | M | unassigned |
| 1251 | A live "rough bullets + transcript → merged note" capture flow Next: frontend/js/media.js's meeting overlay gets a bullets... | docs/roadmap/BACKLOG.md:2911 | L | unassigned |
| 1252 | ~~Basic local speaker separation on a transcript Next: faster-whisper does not diarize and a diarization library pulls torch...~~ **Built diarize-1111 (owner, 2026-11-11; ai/diarize.py, tests/test_diarize_1111.py).** | docs/roadmap/BACKLOG.md:2957 | M | unassigned |
| 1253 | .library-subtabs button was more rounded than .notes-subtabs button, traced to cascade order, not a missing class: a global... | docs/roadmap/BACKLOG.md:3397 | M | unassigned |
| 1254 | ~~Speaker labelling on transcripts (gap 12): Next: same decision as section 102 item 8 (the owner). Transcription is already local...~~ **Built diarize-1111 (owner, 2026-11-11; ai/diarize.py, tests/test_diarize_1111.py).** | docs/roadmap/BACKLOG.md:3573 | S | unassigned |
| 1255 | ~~Speaker labelling on transcripts. Next: the owner's call, section 102 item 8. Transcription is already local, so "Speaker 1/2/3"...~~ **Built diarize-1111 (owner, 2026-11-11; ai/diarize.py, tests/test_diarize_1111.py).** | docs/roadmap/BACKLOG.md:3729 | S | unassigned |
| 1256 | Tidy and filing: every reason ("filed under Work because…") in one voice. | docs/roadmap/CHAT_PLAN.md:741 | S | unassigned |
| 1257 | Brief 87 (vendor candidates, voice and dictation): research table added; Opus build of what to vendor unassigned | docs/roadmap/SESSION_BRIEFS.md:1742 | L | unassigned |
| 1258 | It opens on a file rather than on a picker, in this order: the file you last had open in it, else the most recently added readable file, else the... | docs/roadmap/UI_MODERNISATION_PLAN.md:292 | M | unassigned |
| 1259 | Four verbs, without opening anything: open it in the reader (the row's one filled control), save a copy of the original, rename, delete. The last... | docs/roadmap/UI_MODERNISATION_PLAN.md:316 | S | unassigned |
| 1260 | "there's no option to have the ocr workspace in the quick access section in the dashboard, it also isnt accessible in the cmd palatte or find... | docs/roadmap/UI_MODERNISATION_PLAN.md:1288 | M | unassigned |
| 1261 | INBOX 790, UI and bug, the owner 2026-10-10 22:40Z, three screenshots. "can you resesign or restyle these buttons in the ocr workspace header??" then... | docs/roadmap/UI_MODERNISATION_PLAN.md:1539 | M | unassigned |
| 1262 | Tab bar scrolls between 600 and 819px; short tab captions below 480 are a copy decision for the owner. Owner: responsive.md. | docs/roadmap/WORLD_CLASS_PLAN.md:976 | S | unassigned |
| 1263 | #library-media-refresh is misnamed; Settings has two heading indents. Owner: docks.md. | docs/roadmap/WORLD_CLASS_PLAN.md:988 | S | unassigned |
| 1264 | Files sub-tab rows "could still use a massive redesign upgrade", and clicking the file name does nothing. Owner: Library dossier (WORLD_CLASS 4)... | docs/roadmap/WORLD_CLASS_PLAN.md:1587 | L | unassigned |
| 1265 | OCR alternative to pytesseract, asked directly. Answer: RapidOCR (PaddleOCR models on onnxruntime, pip-installable, no system binary, better on... | docs/roadmap/WORLD_CLASS_PLAN.md:1597 | M | unassigned |
| 1266 | Drag and drop of files onto any page imports them (Library only today). | docs/roadmap/WORLD_CLASS_PLAN.md:2372 | S | unassigned |
| 1267 | "Filing and suggested tags and categories and stuff need a lot of improving. Should we include a library of common possible categories and even ways... | docs/roadmap/WORLD_CLASS_PLAN.md:3119 | L | unassigned |
| 1268 | "I think meeting notes should be different or at least partially separate from dictation and audio transcribing. Can there be an auto captioning and... | docs/roadmap/WORLD_CLASS_PLAN.md:3123 | M | unassigned |
| 1269 | "are there any other libraries that could be used that I and u havent found or mentioned??" Recommendation: the candidate-library table in Brief 40... | docs/roadmap/WORLD_CLASS_PLAN.md:3130 | S | unassigned |
| 1270 | ~~Five proposed decisions (computed values, no archive verb, dated currency table, playful voice waits, model picks among readings) are for the...~~ **W34: stale** (w34-L1-1111.md) | docs/roadmap/archive/agent-remaining/assistant-1010.md:12 | M | unassigned |
| 1271 | "Clear dismissed suggestions" does not reach per-note "Not suggested" tags; changes are noted only while Settings is open (the top-bar theme button... | docs/roadmap/agent-remaining/OPEN.md:2226 | M | unassigned |
| 1272 | Free lines and arrows (not links) still draw the shaft through hollow ends: their stored path is re-read as the endpoints, so trimming would drift... | docs/roadmap/agent-remaining/OPEN.md:2339 | S | unassigned |
| 1273 | Suggesting tags from a note's own words for a notebook with no tags yet scored 4 of 12 and was not shipped. | docs/roadmap/agent-remaining/OPEN.md:2373 | S | unassigned |
| 1274 | The Connections unlinked-mention Link button is still a bordered ghost button; the tool-confirm pair is untouched. | docs/roadmap/agent-remaining/OPEN.md:2406 | S | unassigned |
| 1275 | Link-label blur not reproduced headless; the re-raster after zoom is untested on a GPU compositor or the desktop webview. | docs/roadmap/agent-remaining/OPEN.md:2413 | S | unassigned |
| 1276 | The sidebar's Comments, Linked from and Notes rows keep their old styling. | docs/roadmap/agent-remaining/OPEN.md:2434 | S | unassigned |
| 1277 | After Undo the run, the per-write stack entries stay; a later Ctrl+Z re-runs an already applied inverse (harmless for pin, tag and edit).... | docs/roadmap/agent-remaining/OPEN.md:2517 | S | unassigned |
| 1278 | **Fixed 2026-10-19.** Dashboard quick links overflow by 4 px at 1440 and 390 (#dash-quicklinks .launch-group). | docs/roadmap/agent-remaining/OPEN.md:2520 | S | unassigned |
| 1279 | The More sheet on a map is 59 to 62 rows at 390 (the table plus the map palette); grouped by hairlines but long. A search field or the palette's own... | docs/roadmap/agent-remaining/OPEN.md:2552 | S | unassigned |
| 1280 | EntryLink rows are counted whole: a link to a binned or private note is still a link on the page (_notebook_block). | docs/roadmap/agent-remaining/OPEN.md:2568 | S | unassigned |
| 1281 | The other search surfaces still do their own thing Closed. The account is in HISTORY.md, "OPEN.md rows closed, 2026-10-05 (the open-ledger pass)". | docs/roadmap/agent-remaining/OPEN.md:2693 | S | unassigned |
| 1282 | maptheme.md: the theme is resolved into each node on export rather than carried; an <arrowlink> written by FreeMind itself is untested. [maptheme]... | docs/roadmap/agent-remaining/OPEN.md:2817 | M | unassigned |
| 1283 | wbtopbar.md: #wb-search-toggle and #wb-navigator-toggle duplicate View menu switches (UI_MODERNISATION_PLAN Phase 8 names them as the bar's find... | docs/roadmap/agent-remaining/OPEN.md:2848 | L | unassigned |
| 1284 | The capture draft counts as unsaved work, so every tab switch with a draft asks "Leave without saving?" though the draft is kept and the switch loses... | docs/roadmap/agent-remaining/OPEN.md:3025 | S | unassigned |
| 1285 | Retrieval and the learned loop, plan rows whose half-built parts live in the scratchpad: "most opened this month" is parked in... | docs/roadmap/agent-remaining/OPEN.md:3060 | M | unassigned |
| 1286 | Retrieval and the learned loop, plan rows: the "wrong" correction on an evidence card (I7's second half) and I1 pass 2's kinds as derived facts... | docs/roadmap/agent-remaining/OPEN.md:3071 | M | unassigned |
| 1287 | Every cosine number in the retrieval work came from the 4-dimensional fake. A real backend is 384-dimensional, anisotropic, and its embed_text per... | docs/roadmap/agent-remaining/OPEN.md:3205 | L | unassigned |
| 1288 | Owner (2026-10-07), a fresh install's search model: an empty or partial models--BAAI--bge-small-en-v1.5 folder is treated as present, the load runs... | docs/roadmap/agent-remaining/OPEN.md:3335 | M | unassigned |
| 1289 | Owner (2026-10-07): the app repairs a broken or missing search-model cache itself. On EmbeddingCacheBroken, start the reinstall as a visible... | docs/roadmap/agent-remaining/OPEN.md:3338 | M | unassigned |
| 1290 | Owner (2026-10-07): each embedding row shows its real state (Downloaded with its size on disk, Not downloaded, or Files missing with Reinstall). The... | docs/roadmap/agent-remaining/OPEN.md:3339 | M | unassigned |
| 1291 | renderAutonomousSettings fills the Models-pane checkboxes only when Background tasks or Web search opens (settings.js, per the file, about line 158)... | docs/roadmap/agent-remaining/OPEN.md:3340 | M | unassigned |
| 1292 | Autonomous with no model running ends "Finished analysing and linking notes." in 65 ms; it should say it had no model (check agent.run_agent for a... | docs/roadmap/agent-remaining/OPEN.md:3341 | S | unassigned |
| 1293 | Older sweeps that expect note rows in the palette (grep palette-input): ux1005-palette.js (removed 2026-10-12, recoverable from git history) and search1005-lazy.js read command rows only, and... | docs/roadmap/agent-remaining/OPEN.md:3380 | S | unassigned |
| 1294 | Stop part way: the night shift, the backup, resurfacing and the embeddings backfill are each one call with no step to stop at. Only housekeeping... | docs/roadmap/agent-remaining/OPEN.md:3381 | M | unassigned |
| 1295 | /entries/{id}/related lists notes that are already linked, so a press on one answers 400 "already linked" (pre-existing). (from tidy691-1006.md) | docs/roadmap/agent-remaining/OPEN.md:3404 | S | unassigned |
| 1296 | Notes keep the old updated_at rule (any write moves it): edited_at answers "when a person changed it", but lexical_filing... | docs/roadmap/agent-remaining/OPEN.md:3433 | M | unassigned |
| 1297 | Row 4 measured on a seeded notebook (13 notes), not the report's: title-only icon controls in the Notes list 54 to 0 at 1440, 21 to 0 at 390. Other... | docs/roadmap/agent-remaining/OPEN.md:3461 | M | unassigned |
| 1298 | Decision 6 says "the pack's flag": the pack has none. The 49 sensitive topics are MemoryMap's own list in... | docs/roadmap/agent-remaining/OPEN.md:3464 | S | unassigned |
| 1299 | The data path: section 23 says src/memorymap/ai/data/taxonomy/, section 26 decision 56 says src/memorymap/data/; section 23's was followed. (from... | docs/roadmap/agent-remaining/OPEN.md:3465 | S | unassigned |
| 1300 | Decision 4, "alternate names come from the pack's labels and the person's own titles": only the pack's labels (entry/tidy.py _rows_category_names).... | docs/roadmap/agent-remaining/OPEN.md:3466 | S | unassigned |
| 1301 | Decision 4's centroid test needs the search model; with it off the merge review uses topics alone at 0.8 and says so in the row... | docs/roadmap/agent-remaining/OPEN.md:3467 | S | unassigned |
| 1302 | The tag picker on an empty field puts the tags the note says first ("training 10 notes, in this note"), but on a note that says none of them it still... | docs/roadmap/agent-remaining/OPEN.md:3471 | M | unassigned |
| 1303 | The model's tag reply is grounded against a faked reply (tests/test_tag_grounding.py); what a real small model answers is not verified. (from... | docs/roadmap/agent-remaining/OPEN.md:3472 | S | unassigned |
| 1304 | Brief 42's other items not started: highlights on pages, comments with bookmarks and links, link cards with a viewer, the long-form preference at... | docs/roadmap/agent-remaining/OPEN.md:3539 | S | unassigned |
| 1305 | Counts scale with the number of seeded notes (the notes list repeats one finding per card): the table in 28.4 was taken on 13 to 23 notes. | docs/roadmap/agent-remaining/OPEN.md:3560 | S | unassigned |
| 1306 | Brief 47's "the sidebar's search field routes here": the Notes sidebar has no search field; the no-match Search everything button and the... | docs/roadmap/agent-remaining/OPEN.md:3599 | S | unassigned |
| 1307 | Import cost 3.3 s against decision 56's 1.5 s: ai.autonomous pulls ai.agent (503 ms), ai.help_chat 271 ms, api.routes_search 226 ms. Brief 62.... | docs/roadmap/agent-remaining/OPEN.md:3647 | S | unassigned |
| 1308 | Sweeps: touch.js reports Settings appearance and privacy "did not open" (section names moved); overlap.js still counts 4 px rows on #notes-tidy... | docs/roadmap/agent-remaining/OPEN.md:3671 | S | unassigned |
| 1309 | Neighbours barely follow a drag (measured: notes with 4 to 5 links move 20 to 50 of the 340 units the note in hand does, then return to their... | agent/graph100-1011:docs/roadmap/archive/agent-remaining/graph100-1011.md:20 | M | unassigned |
| 1310 | **Already fixed 2026-11-02 (tests/test_properties_never_in_previews.py::test_the_dashboards_note_widgets_read_past_the_block passes at head).** tests/test_properties_never_in_previews.py::test_the_dashboards_note_widgets_read_past_the_block (dashboard.js no longer has the stripFrontmatter... | agent/graph100-1011:docs/roadmap/archive/agent-remaining/graph100-1011.md:30 | S | unassigned |
| 1311 | tests/test_ownerfix_1011.py::test_a_link_row_underlines_its_words_not_its_icon (ValueError: substring not found). | agent/graph100-1011:docs/roadmap/archive/agent-remaining/graph100-1011.md:31 | S | unassigned |
| 1312 | Filing against a model that never answers is serial and slow (measured, a stand-in server that holds every request): a burst of 20 notes saved the... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/scan-1011.md:6 | L | unassigned |
| 1313 | A note created without defer_filing holds a database connection for the whole model wait. Twenty such POST /entries at once against the stand-in (the... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/scan-1011.md:7 | L | unassigned |
| 1314 | 888 pinch: handles (resize, rotate, link ends) still start their own d3-drag on a second finger; they are cancelled by wbCancelGesture but a second... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/phone2-1011.md:9 | S | unassigned W34: unverifiable, w34-L2r-1111.md. |
| 1315 | ~~854 Filing style is a span like Categories and Tags; lint on every .setting-label head.~~ **W34: fixed** (w34-L1-1111.md) | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/ownerfix3-1011.md:10 | S | unassigned |
| 1316 | Close in meaning against a real embedding model: no torch in the sandbox; the route is tested with a letter-count embedder and the page with... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/meaning94-1011.md:11 | S | unassigned W34: unverifiable, w34-L2r-1111.md. |
| 1317 | Found, not fixed (base, not my files): tests/test_undo_contract.py (settings-data.js:settingsHistoryUndo), tests/test_inbox_435.py (tags field... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/phone2-1011.md:11 | M | unassigned |
| 1318 | Browse: web search results, reader view, page history | docs/roadmap/BACKLOG.md:188 | S | unassigned |
| 1319 | Treemap / sunburst: area as weight, so a category with 200 notes looks like one. Best for "where does my writing actually go?"... | docs/roadmap/BACKLOG.md:605 | M | unassigned |
| 1320 | Subway map: orthogonal edges, categories as lines. Beautiful and genuinely hard: it needs edge routing, which is real work rather... | docs/roadmap/BACKLOG.md:622 | M | unassigned |
| 1321 | Sea chart: islands per category, notes as landmarks, links as shipping routes, unlinked notes adrift. Parchment palette pairs... | docs/roadmap/BACKLOG.md:634 | M | unassigned |
| 1322 | Retrieved notes are re-sent in full on every turn, including turns that are a follow-up to the previous answer and need no new... | docs/roadmap/BACKLOG.md:906 | L | unassigned |
| 1323 | That a search snippet is rarely enough and read_url exists | docs/roadmap/BACKLOG.md:970 | S | unassigned |
| 1324 | Query expansion: two or three phrasings, results fused. Next: search/websearch.py:329 (search_web) takes one query; add a... | docs/roadmap/BACKLOG.md:1008 | M | unassigned |
| 1325 | A global quick-capture hotkey in desktop mode. Not asked for directly, but the app's own pitch, "just capture, a local AI files... | docs/roadmap/BACKLOG.md:1171 | L | unassigned |
| 1326 | Multi-category is a schema change, entries.category_id becomes a join table (entry_categories), and the janitor's cheap match (§4... | docs/roadmap/BACKLOG.md:1616 | M | unassigned |
| 1327 | Manual grouping, kept genuinely separate from categories/tags, is smaller: a collections table and a join table, with no AI... | docs/roadmap/BACKLOG.md:1622 | M | unassigned |
| 1328 | **Already met 2026-11-02 (no `wb-search` id in frontend/index.html; the row says it was deleted in 993e639).** "#wb-search unwired, P0 bug", already deleted, 993e639 (see ROADMAP.md §0/§1). | docs/roadmap/BACKLOG.md:1956 | S | unassigned |
| 1329 | Email-in. Next: a decision for the owner: an IMAP poll is a second outbound connection, and routes_settings.py:220 and... | docs/roadmap/BACKLOG.md:2416 | M | unassigned |
| 1330 | A live, inline organization suggestion while typing Next: ai/passive_capture.py and frontend/js/tag-suggest.js are the nearest... | docs/roadmap/BACKLOG.md:2962 | L | unassigned |
| 1331 | Suggested-link reasons, the thing "Explain your existing links" was reported as not doing (it never could: see that button's own... | docs/roadmap/BACKLOG.md:3415 | M | unassigned |
| 1332 | Search-result grouping by category/tag, with counts, Next: GET /search (api/routes_search.py) already returns each hit's kind and... | docs/roadmap/BACKLOG.md:3614 | M | unassigned |
| 1333 | /entries/link-suggestions/reasons is sequential. Up to twelve model round-trips one after another in a threadpool endpoint.... | docs/roadmap/BACKLOG.md:3692 | M | unassigned |
| 1334 | Filing costs a model round-trip per capture since the order was reversed. Now a preference (ai_first_filing), so this is a... | docs/roadmap/BACKLOG.md:3697 | M | unassigned |
| 1335 | "Like this is somewhat a hobby but it is also about ai, local llms and other things." Recommendation: context for the scope of... | docs/roadmap/BACKLOG.md:4169 | M | unassigned |
| 1336 | Does a first install need the internet? Yes, once, and the app says so in one place only. README.md (line about "The first launch... | docs/roadmap/BACKLOG.md:4228 | L | unassigned |
| 1337 | Search and Find anything: a one-line answer above the results when the query is a question. | docs/roadmap/CHAT_PLAN.md:735 | S | unassigned |
| 1338 | "Also if I click the "not about [this tag], don’t show this again", is there a way to undo it or see the list of things not to show again for... | docs/roadmap/CHAT_PLAN.md:928 | M | unassigned |
| 1339 | "also should accessed web links in the sources dropdown be lised at the top of the sources??" Recommendation: sort accessed web links to the top of... | docs/roadmap/CHAT_PLAN.md:933 | M | unassigned |
| 1340 | Brief 39b: filing and the taxonomy (WORLD_CLASS_PLAN 23) | docs/roadmap/SESSION_BRIEFS.md:1305 | M | unassigned |
| 1341 | Notes. Capture as a full-height sheet from the floating + button; the list as full-width rows with swipe actions (pin, bin) matched to the row's menu... | docs/roadmap/UI_MODERNISATION_PLAN.md:637 | L | unassigned |
| 1342 | Every existing id and data-section is kept. A deep link that names a control is resolved to the section that holds the control now (openSettingsModal... | docs/roadmap/UI_MODERNISATION_PLAN.md:1154 | S | unassigned |
| 1343 | INBOX 767, the no-model notice. One row at 1440 (icon, one short sentence, the action as a link-styled button, the X at the end), wraps to two only... | docs/roadmap/UI_MODERNISATION_PLAN.md:1241 | S | unassigned |
| 1344 | "is it possible to add and customise the metadata a little more??" Recommendation: custom note properties, shown in the metadata rows with one... | docs/roadmap/UI_MODERNISATION_PLAN.md:1270 | M | unassigned |
| 1345 | "also I think the topbar is a little large but idk maybe not. maybe research design principles or standards?? ensure wcag 2.2 accessibility is... | docs/roadmap/UI_MODERNISATION_PLAN.md:1280 | M | unassigned |
| 1346 | INBOX 830, the owner 2026-10-11, verbatim (Tidy's "Category names" review, empty; Patterns rows with Confirm and Not right; "Recent runs (3)"): "this... | docs/roadmap/UI_MODERNISATION_PLAN.md:1587 | L | unassigned |
| 1347 | 1024px still wraps the Writing Room controls and the capture attachment row. Owner: consistency.md. | docs/roadmap/WORLD_CLASS_PLAN.md:974 | S | unassigned |
| 1348 | "Still lots of issues with filing without the ai model running but it should still work right because the embedding model is running??" / "I filed a... | docs/roadmap/WORLD_CLASS_PLAN.md:3094 | M | unassigned |
| 1349 | "just continue and research categories and tags etc. make it extensive and also dynamic. some categories for example might not just be "gym" or... | docs/roadmap/WORLD_CLASS_PLAN.md:3121 | M | unassigned |
| 1350 | Decision 30 kinds not asserted: duration, link, plan, polarity, topic, list_item; inherited-date flag; fact cache by entry_edited_at. | docs/roadmap/archive/agent-remaining/spec39-1010.md:3 | S | unassigned W34: owner-call (tracked in the plans), w34-L1-1111.md. |
| 1351 | Decision 31: only recall, tag and source kind are specified; the other answer kinds (comparison, why, how, status, recommendation) and length wish... | docs/roadmap/archive/agent-remaining/spec39-1010.md:4 | S | unassigned W34: owner-call (tracked in the plans), w34-L1-1111.md. |
| 1352 | Decision 39: filing and link explanation lines. | docs/roadmap/archive/agent-remaining/spec39-1010.md:11 | S | unassigned W34: owner-call (tracked in the plans), w34-L1-1111.md. |
| 1353 | "Study and university tags are suggested on the top note if it has no tags no matter what the note is about" (the owner, 2026-10-10): not reproduced... | docs/roadmap/archive/agent-remaining/triage-1010.md:23 | M | unassigned |
| 1354 | Section: B2 job runtime (durable, resumable), B6 local-first sync (design now), B7 API contract, B8 extensions | docs/roadmap/WORLD_CLASS_PLAN.md:535 | L | unassigned |
| 1355 | Measured on synthetic rows and one real destination; the status ring under "auto" motion not measured. | docs/roadmap/agent-remaining/OPEN.md:2244 | S | unassigned |
| 1356 | The first load after the upgrade has no ui-synced mark, so a stale second browser pushes its look to the notebook once. | docs/roadmap/agent-remaining/OPEN.md:2308 | S | unassigned |
| 1357 | Not checked in the desktop webview profile or on a second machine. | docs/roadmap/agent-remaining/OPEN.md:2309 | S | unassigned |
| 1358 | The bin row's long label wraps when its reset appears; theme, palette, accent and zoom keep their own resets (no per-row marker). | docs/roadmap/agent-remaining/OPEN.md:2324 | S | unassigned |
| 1359 | The owner's line was a saved Tree or Arc layout (synced, static by design). Recommendation: name the current layout on the map as one dock chip... | docs/roadmap/agent-remaining/OPEN.md:2395 | S | unassigned |
| 1360 | A 5,000-note import takes 45.9 s: each note commits on its own. | docs/roadmap/agent-remaining/OPEN.md:2423 | S | unassigned |
| 1361 | Binned notes import with their old deleted_at, so the startup purge removes expired ones at the next restart. | docs/roadmap/agent-remaining/OPEN.md:2424 | S | unassigned |
| 1362 | Stop is between steps, not mid-call: a step whose model call has already returned still writes when Stop lands during the call (the sync generator's... | docs/roadmap/agent-remaining/OPEN.md:2516 | S | unassigned |
| 1363 | deepen72a.js's shared overlap measure now ignores a clipped scrolling edge, so other surfaces' overlap counts may drop; undo.js was not run on the... | docs/roadmap/agent-remaining/OPEN.md:2521 | S | unassigned |
| 1364 | JavaScript constructs not lowered for the stepper (classes, destructuring, spread and rest, for...of, default parameters, async and generators, ??... | docs/roadmap/agent-remaining/OPEN.md:2579 | M | unassigned |
| 1365 | Sync (B6) as log shipping. id: events-sync. Unstarted and no longer blocked: it needed the retention rule, which now exists. A compacted snapshot... | docs/roadmap/agent-remaining/OPEN.md:2703 | M | unassigned |
| 1366 | world-class-rows-1-2-9.md: two decisions taken differently from Brief 15 (S1 is a cookie, S3 confines to home and the data folder) that the owner may... | docs/roadmap/agent-remaining/OPEN.md:2857 | M | unassigned |
| 1367 | Package bundles: the Word writer's five tests ran once in a scratch venv with python-docx 1.2.0 (2026-10-05, tests/test_docexport_pictures.py 13 of... | docs/roadmap/agent-remaining/OPEN.md:2916 | M | unassigned |
| 1368 | Smaller backend and gate rows: a note type made through POST /note-types before the list was read, then deleted, loses its id on Undo (not... | docs/roadmap/agent-remaining/OPEN.md:3074 | M | unassigned |
| 1369 | No pre-Brief-7 database was upgraded. Both migrations are exercised by the suite and written to be idempotent, but a real year-old file was never... | docs/roadmap/agent-remaining/OPEN.md:3195 | M | unassigned |
| 1370 | wbSyncMapStrip sets a themed field's effective value onto the select, so a topic following the map shows the map's look pressed rather than ringed... | docs/roadmap/agent-remaining/OPEN.md:3401 | M | unassigned |
| 1371 | Settings, every switch and choice: 13 pressed, 0 undone by Ctrl+Z (settings-controls.js has the only pushUndo; 48 write functions in settings*.js and... | docs/roadmap/agent-remaining/OPEN.md:3546 | S | unassigned |
| 1372 | dashboard.js:undoActorFrom / activityUndoControl (and their two helpers) and note-history.js:undoSkillRun: an undo of the AI's changes through POST... | docs/roadmap/agent-remaining/OPEN.md:3656 | M | unassigned |
| 1373 | No backup schedule "shown with the last success" (WORLD_CLASS 4018 row) beyond Settings, About, Health's last backup line. [safety-1010] | docs/roadmap/agent-remaining/OPEN.md:3660 | S | unassigned |
| 1374 | move_notes to a space can reuse routes_spaces.py's move_notes_to_space, once that body is lifted into a shared helper.... | docs/roadmap/BACKLOG.md:1088 | S | unassigned |
| 1375 | Async httpx client: Next: section 78 says the sync routes are correct, so this is optional; measure first with... | docs/roadmap/BACKLOG.md:1295 | M | unassigned |
| 1376 | Archive: already scoped in §4 item 2 (an archived_at column, additive migration). This section doesn't repeat it, just notes it's... | docs/roadmap/BACKLOG.md:1736 | S | unassigned |
| 1377 | A real storage breakdown, not just the database file. Asked for directly: "can the user see a visual depiction of the storage... | docs/roadmap/BACKLOG.md:1747 | L | unassigned |
| 1378 | Note compression: asked for directly, and worth being honest about the payoff before building it. Notes are short text in SQLite... | docs/roadmap/BACKLOG.md:1784 | M | unassigned |
| 1379 | AI-readability additions: Pointer: scratchpad/audit1005/features.md Phase G (FEAT-12 tools; the outline export is row C14 to C18... | docs/roadmap/BACKLOG.md:1996 | M | unassigned |
| 1380 | A Readwise/Kindle importer: Pointer: the imports agent (section 115 row 1 is the importer set; Readwise is not on it, so size it... | docs/roadmap/BACKLOG.md:2106 | M | unassigned |
| 1381 | Sync / multi-device. It is the most-asked-for thing in every notebook app and it is the one that would break this one: the app's... | docs/roadmap/BACKLOG.md:2490 | M | unassigned |
| 1382 | Mobile apps and sync. The offline, single-machine promise is the product. Sync is a distributed-systems project that would... | docs/roadmap/BACKLOG.md:3886 | M | unassigned |
| 1383 | INBOX 805 backups: mark the latest, date in words, what made it, size, checked; one process ledger for every AI and background run (transparency) | docs/roadmap/INBOX.md:170 | M | unassigned |
| 1384 | T2. Recent runs is a quiet disclosure row (DESIGN "Row actions"), not a full-width bordered box. | docs/roadmap/UI_MODERNISATION_PLAN.md:1591 | S | unassigned |
| 1385 | T3. A confirmed or rejected pattern keeps an Undo on its row and in "What it learned" (owner: learnaudit, with decision 68). | docs/roadmap/UI_MODERNISATION_PLAN.md:1592 | S | unassigned |
| 1386 | Data safety is there but hidden. Backups exist (routes_backups.py), revisions exist (EntryRevision), export exists, but none is on the Dashboard or... | docs/roadmap/WORLD_CLASS_PLAN.md:2351 | M | unassigned |
| 1387 | Section: Phase 12: density, refinement and WCAG 2.2 remainder (density agent left rows; see OPEN) | docs/roadmap/UI_MODERNISATION_PLAN.md:1013 | L | unassigned |
| 1388 | Section: Settings information architecture (INBOX 444): decisions made, build status unverified | docs/roadmap/UI_MODERNISATION_PLAN.md:1112 | M | unassigned |
| 1389 | Section: Deepened statistics, utilities, palette and Find anything (Brief 72b rows; built parts moved) | docs/roadmap/UI_MODERNISATION_PLAN.md:1444 | L | unassigned |
| 1390 | tests/test_name_mood.py asserts oklch(from var(--accent) in the CSS: it holds (the accent tints the glow), but a test for the fixed palette would be... | docs/roadmap/agent-remaining/OPEN.md:1899 | M | unassigned |
| 1391 | The dashboard scroll jump (426 u) was not reproduced by wheel, idle or any scroll call; if it recurs, scrolljump.js with the owner's preferences... | docs/roadmap/agent-remaining/OPEN.md:1947 | M | unassigned |
| 1392 | The View menu is 714px of content on a map. Under about a 730px-tall window it still scrolls, which is correct and may still read as the report. If... | docs/roadmap/agent-remaining/OPEN.md:2081 | M | unassigned |
| 1393 | "spacing is really close ... bunched up" on insert: gaps measured 26px before and after on both layouts; only the branch's jump to the end was found... | docs/roadmap/agent-remaining/OPEN.md:2117 | S | unassigned |
| 1394 | The Dashboard hero is deferred by the owner, not by judgement. Do not touch .dash-hero, .dash-wordmark, .dash-greeting, .dash-clock* in... | docs/roadmap/agent-remaining/OPEN.md:2188 | M | unassigned |
| 1395 | At 25% zoom the 20px + overlaps its parent by about 5px; radial and tree-down layouts not driven. | docs/roadmap/agent-remaining/OPEN.md:2260 | S | unassigned |
| 1396 | Design, for Briefs 57 to 59: the Notes dock has 10 items; Tidy's "40" is a pill badge; 177 controls sit off the 28/32/44 height steps (a 36px family... | docs/roadmap/agent-remaining/OPEN.md:2276 | S | unassigned |
| 1397 | **Already fixed 2026-11-02 (a30d-1102; settings-reset is in HELP_GROUPS Getting started, help_topics_more.py; tests/test_help_coverage.py passes at head).** settings-reset is in no help group (test_help_coverage.py). | docs/roadmap/agent-remaining/OPEN.md:2278 | S | unassigned |
| 1398 | maplayouts.js "tree-left carries the branch bar" fails on base too (it measures the centre topic). | docs/roadmap/agent-remaining/OPEN.md:2294 | S | unassigned |
| 1399 | The 14 browser-only appearance settings do not follow you to a second browser: decided (WORLD_CLASS 25f, placed 2026-10-11): mirror them all except... | docs/roadmap/agent-remaining/OPEN.md:2322 | S | unassigned |
| 1400 | **Fixed 2026-10-19.** smallButton (app.js) names every worded button by its tooltip (WCAG 2.5.3); only the first-steps buttons are fixed. | docs/roadmap/agent-remaining/OPEN.md:2330 | S | unassigned |
| 1401 | Most used in the sidebar keeps a binned note for up to 30 s (status.js cacheMs). | docs/roadmap/agent-remaining/OPEN.md:2331 | S | unassigned |
| 1402 | The first-run queue (welcome, recovery key, updates) costs 3 acts before the dashboard. | docs/roadmap/agent-remaining/OPEN.md:2332 | S | unassigned |
| 1403 | Still open from uipolish: the rows-view 28px meta button in a 24px line, the tool-confirm pair, lowering BOOT_CSS_CAP. | docs/roadmap/agent-remaining/OPEN.md:2341 | S | unassigned |
| 1404 | .dash-find is the one glyph-only hover left; a rows-view meta icon button is 28px in a 24px line. | docs/roadmap/agent-remaining/OPEN.md:2405 | S | unassigned |
| 1405 | BOOT_CSS_CAP can be lowered now that strip_css drops comment-leftover lines (about 7 KB freed). | docs/roadmap/agent-remaining/OPEN.md:2407 | S | unassigned |
| 1406 | The Background jobs Report button waits for boot room; the Activity panel at 390 is translucent. | docs/roadmap/agent-remaining/OPEN.md:2426 | S | unassigned |
| 1407 | A Settings row whose element is a label or head is focused as that element, not its control ("Accent colour" lands on its DIV at both widths)... | docs/roadmap/agent-remaining/OPEN.md:2540 | S | unassigned |
| 1408 | The learned order is exact words only; Raycast also learns prefixes. Recommendation (take it): add the prefix with half weight once picks have a week... | docs/roadmap/agent-remaining/OPEN.md:2541 | S | unassigned |
| 1409 | Acts with no stem start with the example's first word ("remind ", "note: "); a stem per act in act_registry._ACTS would read better but adds rows to... | docs/roadmap/agent-remaining/OPEN.md:2542 | S | unassigned |
| 1410 | Row 8 (rule 6): "every rail and top-bar control has a data-help-for popover and a palette row; 0 missing". Not built. A first count from the DOM... | docs/roadmap/agent-remaining/OPEN.md:2650 | M | unassigned |
| 1411 | errors.js at 1440 and 390: 0 errors, 0 layout findings each. | docs/roadmap/agent-remaining/OPEN.md:2654 | S | unassigned |
| 1412 | 110 distinct controls show no change on keyboard focus (a11yname.js, 312 stops over 14 surfaces): every .status-item, the .ghost.small buttons, the... | docs/roadmap/agent-remaining/OPEN.md:2673 | M | unassigned |
| 1413 | The markup has 18 overlays plus the built confirm and the tour card, not the plan's 15; $S/design/hierarchy.json lists each with its size (Brief 59... | docs/roadmap/agent-remaining/OPEN.md:2676 | S | unassigned |
| 1414 | mapread.md and maprender.md: 13g, the haywire middle-button pan, needs the owner (it never reproduced headless; do not fix blind); the 50-topic open... | docs/roadmap/agent-remaining/OPEN.md:2811 | M | unassigned |
| 1415 | The frontend audit's leftovers (scratchpad/audit1005/frontend.md (removed 2026-10-12, recoverable from git history)): FE-09 unused CSS (no coverage-driven deletion started); FE-10 Settings panes'... | docs/roadmap/agent-remaining/OPEN.md:3052 | M | unassigned |
| 1416 | Not verified: Quit's 0.72 opacity contrast is computed (about 3.1:1 light, 5:1 dark), not read from pixels; the line numbers' baseline drop is... | docs/roadmap/agent-remaining/OPEN.md:3089 | S | unassigned |
| 1417 | How the dark palette reads on an OLED panel or at another display gamma, and the luminance column glassdepth.js takes, which was not re-run after the... | docs/roadmap/agent-remaining/OPEN.md:3229 | S | unassigned |
| 1418 | Write with AI was measured with the model off, so "Draft it" is disabled and the draft box is empty in every measurement. The column heights are the... | docs/roadmap/agent-remaining/OPEN.md:3256 | M | unassigned |
| 1419 | **Already fixed 2026-11-02 (a30d-1102; wireHelpPopover close() waits for the exit through afterMenuExit and .help-popover.hidden has the exit transition, 10-responsive.css; tests/test_help_popover_in_dialogs.py).** Help popovers close at once: a popover goes home and is removed on close, which cancels its exit transition. (from motion-1005.md) | docs/roadmap/agent-remaining/OPEN.md:3306 | S | unassigned |
| 1420 | A sub-tab's panel does not cross-fade; only its line slides. CSS cannot tell a section switch from a page arriving; it needs a class set by... | docs/roadmap/agent-remaining/OPEN.md:3307 | S | unassigned |
| 1421 | 444 decision 10, still open: the Tools (4,247px) and Appearance (1,296px) panes are indexed, not split. (from op4-1005.md) | docs/roadmap/agent-remaining/OPEN.md:3312 | S | unassigned |
| 1422 | Doc-focus panels between 720 and 819px cover the page, as below 720 did before; not driven in a sweep. (from op5-1005.md) | docs/roadmap/agent-remaining/OPEN.md:3315 | S | unassigned |
| 1423 | scroll-padding: a control focused by Tab in a scroller is scrolled to the edge with its ring half cut. scroll-padding: var(--ring-room) on .tab-page... | docs/roadmap/agent-remaining/OPEN.md:3346 | S | unassigned |
| 1424 | /jobs/last-runs is polled after a lock and answers 401 once or twice per lock (forgotpw.js's refused list). Next: stop the poll in lockNow and... | docs/roadmap/agent-remaining/OPEN.md:3368 | M | unassigned |
| 1425 | tests-e2e/specs/shell.spec.js has a handoff test that has only had node --check; Playwright's runner has not run it. (from palette666-1006.md) | docs/roadmap/agent-remaining/OPEN.md:3379 | S | unassigned |
| 1426 | The owner's second screenshot showed a stray circle after the hover buttons on an opened row. Not reproduced at 1440, 1920 or 390, light or dark... | docs/roadmap/agent-remaining/OPEN.md:3390 | S | unassigned |
| 1427 | The Notes dock wraps to two rows from about 1280 to 1500 with the connections rail open (90px); Tidy's 40px extends that band to about 1640. Moving... | docs/roadmap/agent-remaining/OPEN.md:3402 | M | unassigned |
| 1428 | Brief 32 (templates and base layouts): deferred by the owner; BACKLOG 4b carries the standing row. (from briefs-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3450 | S | unassigned |
| 1429 | 745 (d): the hover-only tour step reveal is built nowhere (tour.js has no hover handling). (from coverage-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3452 | S | unassigned |
| 1430 | design-1010 row 5, 110 controls with no focus change (a11yname.js focus pass): Brief 57, decision 15. (from a11yfix-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3458 | S | unassigned |
| 1431 | Row height at 1440 is 46.8px, not "one line plus padding" (about 38px): the Connect button's 28.8px target floor sets the row. Left as is; shrinking... | docs/roadmap/agent-remaining/OPEN.md:3479 | S | unassigned |
| 1432 | Rule 14: the Health block stays in Settings, About (where it was built, PLAN B9) rather than its own section; reach is the palette's Health (1) and... | docs/roadmap/agent-remaining/OPEN.md:3525 | S | unassigned |
| 1433 | Not reached by the sweep: right-click menus, keyboard-only acts (Tab for a branch), controls that open a picker and then need a second choice (note... | docs/roadmap/agent-remaining/OPEN.md:3552 | M | unassigned |
| 1434 | #select-btn span.dock-word 40px and #notes-filter-menu span.dock-word 32px clipped at 320 to 1024: the labelled-to-icon collapse hides words by... | docs/roadmap/agent-remaining/OPEN.md:3556 | S | unassigned |
| 1435 | **Fixed 2026-10-19.** button#notes-tidy.ghost.small 4px at every width; #tab-notes div.layout 4px at 320 to 1024. | docs/roadmap/agent-remaining/OPEN.md:3557 | S | unassigned |
| 1436 | Dashboard: 3 overflow and 1 clipped text at 320 and 390, 2 overflow at 820 and wider (selectors in the sweep output, not yet named here). | docs/roadmap/agent-remaining/OPEN.md:3558 | S | unassigned |
| 1437 | Crawl: 55 destinations found from the dashboard (1, 14, 36, 3 and 1 at depths 0 to 4, crawl complete to depth 4), 1 deeper than 3, 16 with no palette... | docs/roadmap/agent-remaining/OPEN.md:3561 | M | unassigned |
| 1438 | The crawl presses navigation-looking controls only and one item of each repeated list; a destination absent from it is "not found by the crawl", not... | docs/roadmap/agent-remaining/OPEN.md:3564 | M | unassigned |
| 1439 | Palette rows from the registry: acts.palette_rows (src/memorymap/ai/acts.py) has no caller and palette.js still lists its own starters; a route and... | docs/roadmap/agent-remaining/OPEN.md:3585 | S | unassigned |
| 1440 | Settings: the synonym groups and the filler list are a hand table (filters.SETTING_WORDS, SETTING_FILLER), measured on 10 phrases in the browser; no... | docs/roadmap/agent-remaining/OPEN.md:3611 | S | unassigned |
| 1441 | The plan row names a "Versions" row; the note menu's existing row is "History" (versions plus every other event). Not renamed: a rename moves help in... | docs/roadmap/agent-remaining/OPEN.md:3658 | S | unassigned |
| 1442 | Decision 1, panel padding 12 and sidebar gutter 8: not measured or moved; the Notes dock wraps to two rows at 1440 (86 px). [density-1010] | docs/roadmap/agent-remaining/OPEN.md:3669 | S | unassigned |
| 1443 | **Already fixed 2026-11-02 (tests/test_finder_star_790.py passes at head).** Failing on the base commit, not touched: test_finder_star_790 (expects a clip-path star, the CSS draws a mask), test_has_invalidation (22 unkeyed... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/room101-1011.md:8 | M | unassigned |
| 1444 | ~~856 Hover-ground lint and sweep (see below); the owner's element was not found.~~ **W34: fixed** (w34-L1-1111.md) | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/ownerfix3-1011.md:11 | S | unassigned |
| 1445 | 856: tests/test_hover_grounds_have_a_radius.py is a class-level scan with a reviewed list; it cannot see an element whose corner comes from a parent... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/ownerfix3-1011.md:15 | S | unassigned W34: owner-call, w34-L1-1111.md. |
| 1446 | Dark mode and 390 px beyond errors.js (0 errors, 0 layout findings at 1440 and 390, light and dark), contrast.js, docks.js, touch.js and chrome.js. | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/scan-1011.md:17 | S | unassigned |
| 1447 | ~~851: rows view at 390 (the view toggle is hidden there) and the dark theme for the tick's colours were not measured; cards at 390 dark were.~~ **W34: stale** (w34-unv1-1111.md) | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/ownerfix3-1011.md:19 | S | unassigned |
| 1448 | Measured (Playwright at 390, X-Forwarded-For: 192.168.0.50 against :8893): data-other-device=1, 12 note lines, #quit-btn display none, a marked... | agent/secscan-1011:docs/roadmap/archive/agent-remaining/secscan-1011.md:39 | M | unassigned |
| 1449 | Getting one error OUT of the log (asked for directly after the console landed: "make sure that if there is an error in the log... | docs/roadmap/BACKLOG.md:50 | L | unassigned |
| 1450 | The JSON it would compress is the JSON that cannot be compressed. This one was worth measuring rather than assuming, and the... | docs/roadmap/BACKLOG.md:727 | M | unassigned |
| 1451 | More themes and palettes (#palette-grid; Next: a "surprise me" is a seeded pick of accent, palette and density from the existing... | docs/roadmap/BACKLOG.md:1128 | M | unassigned |
| 1452 | Live preview while hovering a theme, before committing. Next: applySavedTheme writes through appearancePref; a hover preview... | docs/roadmap/BACKLOG.md:1136 | M | unassigned |
| 1453 | Task management: Next: a decision for the owner, not a build; checklists in notes already feed the Unfinished widget... | docs/roadmap/BACKLOG.md:1199 | M | unassigned |
| 1454 | A screen-reader pass: Pointer: section 115 row 4 of this file (WCAG AA and an axe pass, gate a11yname.js, contrast.js, touch.js)... | docs/roadmap/BACKLOG.md:1285 | M | unassigned |
| 1455 | Opt-in retention rules: "forgetting," not just "archiving." Archive above is a manual action; nothing today acts on a note's age... | docs/roadmap/BACKLOG.md:1774 | L | unassigned |
| 1456 | A swatches/saved-palette panel: Pointer: scratchpad/audit1005/features.md section 4 row C9 and section 8.2 kind 3 (saved styles... | docs/roadmap/BACKLOG.md:1986 | M | unassigned |
| 1457 | §88.4 item 3 ("memory is a surface, not a system") Pointer: PLAN.md row A3 ("Memory with provenance"; Settings, The AI, What it... | docs/roadmap/BACKLOG.md:2853 | M | unassigned |
| 1458 | Gallery kebab stayed open over the rename field. The close-on-pick listener was on the bubble phase, with a comment explaining... | docs/roadmap/BACKLOG.md:3627 | S | unassigned |
| 1459 | The Regenerate-greeting button wrapping onto its own line. The (usually empty) status span had flex: 1 1 auto, giving it a 178px... | docs/roadmap/BACKLOG.md:3646 | M | unassigned |
| 1460 | The suite is 2,700 tests and ~8 minutes. Still fine; worth watching. The lints (test_style_scale, test_frontend_ids... | docs/roadmap/BACKLOG.md:3848 | S | unassigned |
| 1461 | A first run that explains itself. The onboarding overlay exists. What does not exist is the answer to "I have 4,000 notes in... | docs/roadmap/BACKLOG.md:3878 | S | unassigned |
| 1462 | The owner, 2026-09-23 night, verbatim, from the desktop window with a screenshot. "I pressed next on the first panel of the... | docs/roadmap/BACKLOG.md:4133 | L | unassigned |
| 1463 | "why is the token window limit for this model soooo low :(" Recommendation: show the model's real context limit and the reason for it in the token... | docs/roadmap/CHAT_PLAN.md:857 | S | unassigned |
| 1464 | "Hovering over an intext reference opens up the sources dropdown." Recommendation: hover shows a short preview of the source and a click opens the... | docs/roadmap/CHAT_PLAN.md:877 | M | unassigned |
| 1465 | "when I click the token window button pill, i expect to see a dropdown to see my token distribution stats, not it to be a button to compact the... | docs/roadmap/CHAT_PLAN.md:935 | M | unassigned |
| 1466 | Brief 32 (templates and base layouts) and Brief 33 (the rest of WORLD_CLASS_PLAN): unmarked | docs/roadmap/SESSION_BRIEFS.md:850 | L | unassigned |
| 1467 | Brief 92: the whole-app pass the owner asked for (first run, tour, element libraries, themes; INBOX 843) | docs/roadmap/SESSION_BRIEFS.md:1767 | L | unassigned |
| 1468 | "There's overlap on these settings tabs in the sidebar" Recommendation: measure the overlap of the settings tabs at the sidebar width, then fix the... | docs/roadmap/UI_MODERNISATION_PLAN.md:1259 | S | unassigned |
| 1469 | "Some tooltip buttons are circles and some are rounded squares. Should they have backgrounds or borders that are visible??" Recommendation: one... | docs/roadmap/UI_MODERNISATION_PLAN.md:1274 | S | unassigned |
| 1470 | "No vertical gap" Recommendation: the owner has not named the surface; find the gap by the density census and fix it under the spacing tokens. Also... | docs/roadmap/UI_MODERNISATION_PLAN.md:1276 | S | unassigned |
| 1471 | "Ive been screenhotting parts of the perplexity interface and others but there are soo many more modern examples and ways to structure stuff. I think... | docs/roadmap/UI_MODERNISATION_PLAN.md:1282 | M | unassigned |
| 1472 | "feel like there should be a subtle like meatball icon in the top right on the same line as the quick access title on aligned to the right above the... | docs/roadmap/UI_MODERNISATION_PLAN.md:1284 | M | unassigned |
| 1473 | "do way to view logs of bg processes" Recommendation: a background tasks log in settings, read from the job runtime. Also carried by Brief 37 (logs... | docs/roadmap/UI_MODERNISATION_PLAN.md:1286 | S | unassigned |
| 1474 | INBOX 789, UI, the owner 2026-10-10 22:38Z, two screenshots. "not all buttons have the same hover states?? all the ui styles across the app need to... | docs/roadmap/UI_MODERNISATION_PLAN.md:1538 | M | unassigned |
| 1475 | 809, the owner, verbatim: "is there a way to redesign areas in the app like these??" (Help, "Welcome and tours": fourteen bordered tinted buttons and... | docs/roadmap/UI_MODERNISATION_PLAN.md:1562 | L | unassigned |
| 1476 | Settings > Packages rows misaligned (icon, text and the install button on different baselines). Owner: consistency.md item 4; the alignment sweep... | docs/roadmap/WORLD_CLASS_PLAN.md:1558 | S | unassigned |
| 1477 | Settings > Help gaps (accordion rows touch, sections have no rhythm). Owner: help-popovers.md, with item 22. | docs/roadmap/WORLD_CLASS_PLAN.md:1561 | S | unassigned |
| 1478 | The laptop screen is mostly chrome. At 1093x614 the top bar (72px), sub-tabs (55), the list toolbar (55) and the status bar (37) take about 36% of... | docs/roadmap/WORLD_CLASS_PLAN.md:2320 | M | unassigned |
| 1479 | A "Copy diagnostics" button on the About page (versions, model, recent errors) for bug reports from test users. | docs/roadmap/WORLD_CLASS_PLAN.md:2375 | S | unassigned |
| 1480 | The status bar's "." dot says what it means on hover and click. | docs/roadmap/WORLD_CLASS_PLAN.md:2377 | S | unassigned |
| 1481 | Hierarchy in Settings. Section heads are the same weight as labels (in the Sonnet batch). | docs/roadmap/WORLD_CLASS_PLAN.md:2385 | S | unassigned |
| 1482 | **Already met 2026-10-19** (5.91:1 light, 7.96:1 dark, 13.6px `.empty-line`); only the icon-and-action recipe is design work. Empty states. The Chats sidebar's empty text is body size and grey on grey; empty states should use one recipe (icon, one line, one action). | docs/roadmap/WORLD_CLASS_PLAN.md:2389 | S | unassigned |
| 1483 | "I pressed a restart button and it failed: {"[1007/230819.346:ERROR:ui\gfx\win\window_impl.cc:172] Failed to unregister class Chrome_WidgetWin_0.... | docs/roadmap/WORLD_CLASS_PLAN.md:3086 | M | unassigned |
| 1484 | "Also I feel like we should reference all the vendored repos and libraries somewhere to give them credit." Recommendation: a credits list in Help... | docs/roadmap/WORLD_CLASS_PLAN.md:3115 | M | unassigned |
| 1485 | 25f: the 14 appearance settings kept only in this browser do not follow the person to a second browser. Decision, taken: mirror them all to the... | docs/roadmap/WORLD_CLASS_PLAN.md:4192 | M | unassigned |
| 1486 | errors.js ran light theme only; THEME=dark and FAULTS=1 not run. | docs/roadmap/archive/agent-remaining/census-1010.md:4 | S | unassigned |
| 1487 | 24.5 undercounts untested routes (path-param wildcard) and over-reports unused CSS names (string-built classes). | docs/roadmap/archive/agent-remaining/census-1010.md:5 | S | unassigned |
| 1488 | Not indexed: class methods, nested functions, let/var helpers, and JS functions declared in a form other than function name( or const name = (. | docs/roadmap/archive/agent-remaining/codemap-1010.md:5 | S | unassigned W34: true, w34-L2r-1111.md. |
| 1489 | Settings help mapping is a heuristic (measure-settings-help.py header says the rule); 31 of 72 keys have no Settings control it could find, and some... | docs/roadmap/archive/agent-remaining/measure-1010.md:8 | S | unassigned |
| 1490 | Decision 43: editable rate table in Settings, never fetched without the web toggle. | docs/roadmap/archive/agent-remaining/spec39-1010.md:13 | S | unassigned W34: owner-call (tracked in the plans), w34-L1-1111.md. |
| 1491 | After the bugs: the parity programme, the 'build first' rows of every ANALYSIS parity table (docs/ROADMAP.md) | docs/ROADMAP.md:132 | L | unassigned |
| 1492 | Section: Assistant catalogue section 5: build first, fifteen capabilities by value over cost | docs/roadmap/CHAT_PLAN.md:1516 | L | unassigned |
| 1493 | Section: Phase 7: reports from the v0.2.2 round still open (items 2 and 6 and the rest after Built 1, 3, 4, 5) | docs/roadmap/UI_MODERNISATION_PLAN.md:229 | M | unassigned |
| 1494 | Section: Phase 10: the Liquid Glass adoptions (half a session; confirm what is built) | docs/roadmap/UI_MODERNISATION_PLAN.md:590 | S | unassigned |
| 1495 | Section: 12z Learnability measured on a fresh profile (INBOX 749) | docs/roadmap/UI_MODERNISATION_PLAN.md:1297 | M | unassigned |
| 1496 | Section: Phase 13: design review; 13a built (Brief 57), 13b and 13c (Briefs 58, 59) open | docs/roadmap/UI_MODERNISATION_PLAN.md:1314 | L | unassigned |
| 1497 | Section: Section 2: competitor gaps (what they have that this app does not) | docs/roadmap/WORLD_CLASS_PLAN.md:225 | L | unassigned |
| 1498 | Section: Section 3: frontend dossiers D1 to D16 (each a hand-off brief; build status per dossier unverified) | docs/roadmap/WORLD_CLASS_PLAN.md:289 | L | unassigned |
| 1499 | Section: Section 7: the small things checklist that sessions keep reopening | docs/roadmap/WORLD_CLASS_PLAN.md:740 | M | unassigned |
| 1500 | Section: Section 10: flaws found by static probes (each with its command) | docs/roadmap/WORLD_CLASS_PLAN.md:861 | M | unassigned |
| 1501 | Section: Section 18: the next horizon H1 to H9 | docs/roadmap/WORLD_CLASS_PLAN.md:1726 | L | unassigned |
| 1502 | Section: Section 19: architecture review (776 MB resident idle; 19.5 not covered yet) | docs/roadmap/WORLD_CLASS_PLAN.md:1911 | M | unassigned |
| 1503 | Section: Section 20: a model per feature, Still open | docs/roadmap/WORLD_CLASS_PLAN.md:2220 | M | unassigned |
| 1504 | Section: Section 21: every failure names its way out | docs/roadmap/WORLD_CLASS_PLAN.md:2290 | M | unassigned |
| 1505 | Section: Section 22: the professional baseline gaps and the devibecode programme | docs/roadmap/WORLD_CLASS_PLAN.md:2317 | L | unassigned |
| 1506 | Section: Section 24: codebase census acts (Brief 45 part 2) | docs/roadmap/WORLD_CLASS_PLAN.md:3217 | L | unassigned |
| 1507 | Section: 25.2 Surface by surface bars and gaps (Briefs 46 to 55 landed mostly; gaps per surface remain) | docs/roadmap/WORLD_CLASS_PLAN.md:3755 | L | unassigned |
| 1508 | Section: 26.3 Backend phases with gates (Briefs 61 to 63 open) | docs/roadmap/WORLD_CLASS_PLAN.md:3924 | L | unassigned |
| 1509 | Section: 27.1 Feature by feature gaps and 27.2 the popups one by one | docs/roadmap/WORLD_CLASS_PLAN.md:3984 | L | unassigned |
| 1510 | Section: 28.3 Trust contract phases and the rules still open | docs/roadmap/WORLD_CLASS_PLAN.md:4097 | M | unassigned |
| 1511 | uipolish-0924 leftovers: the surface-by-surface pass (its item D); the icon-only floor is done and measured by iconfloor.js. The footer overlap... | docs/roadmap/agent-remaining/OPEN.md:1951 | L | unassigned |
| 1512 | No lint makes a new outbound call site name its purpose (egress.purpose, nine sites do). | docs/roadmap/agent-remaining/OPEN.md:2242 | S | unassigned |
| 1513 | INBOX 819 (2): a label's look controls (size, bold, colour, chip, position); owner the cards agent. | docs/roadmap/agent-remaining/OPEN.md:2259 | S | unassigned |
| 1514 | Speaker names cannot be edited; the decision and action rules read English cue words only. | docs/roadmap/agent-remaining/OPEN.md:2357 | S | unassigned |
| 1515 | A tab hidden over five minutes can fire up to 60 s late (Chromium's timer throttling). | docs/roadmap/agent-remaining/OPEN.md:2366 | S | unassigned |
| 1516 | Caps measured on a loaded machine sit close to the noise; re-measure idle and tighten (table, README and test move together). | docs/roadmap/agent-remaining/OPEN.md:2388 | S | unassigned |
| 1517 | **Already fixed 2026-11-02 (a30d-1102; the shimmer runs only when motion is not reduced or Always move was chosen, data-progress-chosen, 02-chat-graph.css; tests/test_motion_tokens.py passes).** The skeleton shimmer still runs under the OS reduced-motion setting (data-progress-motion defaults to "always"). | docs/roadmap/agent-remaining/OPEN.md:2404 | S | unassigned |
| 1518 | A slow or failed fetch of app-features.js and a late Quick access first paint were not exercised. | docs/roadmap/agent-remaining/OPEN.md:2459 | S | unassigned |
| 1519 | Questions split at quote marks: INBOX 745 (b) decided a quoted prompt is not the person's own question, so the extractor rejects them; the fragments... | docs/roadmap/agent-remaining/OPEN.md:2465 | M | unassigned |
| 1520 | **Already fixed 2026-11-02 (a30d-1102; refreshModelStatus keeps the last good status on a timeout and flags modelStatusProblem slow, status.js; tests/test_inbox_435.py).** A failed or slow status poll nulls modelStatus, so Agent greys until the next good poll and may flicker. | docs/roadmap/agent-remaining/OPEN.md:2473 | S | unassigned |
| 1521 | Other AI controls still gate on aiIsOff(); model_ready is the field to move them to. | docs/roadmap/agent-remaining/OPEN.md:2474 | S | unassigned |
| 1522 | **Fixed 2026-11-02 (a30d-1102; tests/test_note_by_number_1102.py: _target reads note 12 to a note_id, _resolve_one and _which look it up, link takes both numbers).** The reading does not take a note by its number ("pin note 12"): commands._one_target. | docs/roadmap/agent-remaining/OPEN.md:2519 | S | unassigned |
| 1523 | The fishbone's rib runs behind its causes' boxes (lines are under nodes); the look is not compared against XMind's. | docs/roadmap/agent-remaining/OPEN.md:2554 | S | unassigned |
| 1524 | **Already built 2026-11-02 (a30d-1102; week_first_day in core/config.py reads the week_start choice, then the locale; its value reaches week_review, page and stats_ask as first_day; tests/test_notebook_stats_page.py::test_the_first_day_follows_the_choice_then_the_locale_then_monday).** The week is Monday-first on user_now; a Sunday-first locale reads it a day out (notebook_stats.week_start). | docs/roadmap/agent-remaining/OPEN.md:2565 | S | unassigned |
| 1525 | Words written this week are the words in the notes made that week; edits to older notes are not counted (no per-edit word delta is stored). | docs/roadmap/agent-remaining/OPEN.md:2566 | S | unassigned |
| 1526 | D1's folder: the brief and D1 say frontend/js/run/; the files are frontend/js/run-*.js because 65 lints (test_frontend_symbols, the em-dash and... | docs/roadmap/agent-remaining/OPEN.md:2658 | S | unassigned |
| 1527 | input() is answered before the run (the Input box), not interactively mid-run: that needs SharedArrayBuffer and the COOP/COEP headers, which are D2's... | docs/roadmap/agent-remaining/OPEN.md:2664 | S | unassigned |
| 1528 | netbind.host_allowed("localhost.") and a trailing-dot own name are refused (fail closed, as intended; noted so nobody reads a 421 on localhost. as a... | docs/roadmap/agent-remaining/OPEN.md:2688 | S | unassigned |
| 1529 | arch.md (removed 2026-10-12, recoverable from git history): INBOX 266's usability and lightweight items belong to nobody. [arch] (The emblem's idle cost is built: HISTORY.md, "OPEN.md rows closed... | docs/roadmap/agent-remaining/OPEN.md:2772 | S | unassigned |
| 1530 | writing-desk.md: Stop mid-pass is unverified (the stand-in answers in about 150ms; a slow backend behind an env var in fake_openai_server.py would... | docs/roadmap/agent-remaining/OPEN.md:2863 | M | unassigned |
| 1531 | Prose tools: Harper's lint config per kind in the dictionary dialog (harper-worker.js, setLintConfig; about 200 rules, all or nothing today)... | docs/roadmap/agent-remaining/OPEN.md:2910 | L | unassigned |
| 1532 | Map render and persistence: (the wbMapNodeSize 94px row is closed, HISTORY.md, "OPEN.md rows closed, 2026-10-05 (the pre-0.4.0 buildable rows, sweeps... | docs/roadmap/agent-remaining/OPEN.md:2957 | M | unassigned |
| 1533 | The rest of the architecture audit (scratchpad/audit1005/arch.md (removed 2026-10-12, recoverable from git history)): ARCH-04's client half (the cursor exists, after and X-Next-Cursor, but... | docs/roadmap/agent-remaining/OPEN.md:3040 | L | unassigned |
| 1534 | Nothing in the learning loop was measured past a test-sized notebook. The pass is O(notes) with one query per note for the already-known... | docs/roadmap/agent-remaining/OPEN.md:3200 | M | unassigned |
| 1535 | The desktop window was never run (start-desktop.sh); every visual claim on this branch is a browser tab. [prose-intelligence.md, visual-c.md] | docs/roadmap/agent-remaining/OPEN.md:3218 | S | unassigned |
| 1536 | Timings vary two to four times between runs (the machine was shared with other agents; map add-a-child 102 to 424 ms); the blocks give ranges. Rerun... | docs/roadmap/agent-remaining/OPEN.md:3295 | S | unassigned |
| 1537 | Bergamot's licence (MPL-2.0 into AGPL-3.0) and sizes are stated as the evaluation's job (Brief 83), not checked here. | docs/roadmap/agent-remaining/OPEN.md:3296 | S | unassigned |
| 1538 | A row added or removed after a list's first render does not fade; the lists redraw whole, so this needs keyed rendering first. (from motion-1005.md) | docs/roadmap/agent-remaining/OPEN.md:3305 | S | unassigned |
| 1539 | UI_MOD Phase 11 item 11: the screenshot set for the owner, which needs a place the owner reads. (from op4-1005.md) | docs/roadmap/agent-remaining/OPEN.md:3311 | L | unassigned |
| 1540 | Two-finger scroll jump (460): not reproduced twice; needs a real touchpad trace. (from op4-1005.md) | docs/roadmap/agent-remaining/OPEN.md:3313 | S | unassigned |
| 1541 | scratchpad/ui-sweeps/lib.js LOOK= writes the look into the server's preferences, so later sweeps on that data dir inherit it; run a LOOK=utilitarian... | docs/roadmap/agent-remaining/OPEN.md:3320 | S | unassigned |
| 1542 | The night shift's pairing phase is slow (120 s for 2,400 facts and 4,786 pairings with the local matcher), and the bar resets between the reading and... | docs/roadmap/agent-remaining/OPEN.md:3342 | S | unassigned |
| 1543 | The ring sweep skips a control at the end of a scroller with more content past it, so a real cut at a scrolled edge is not seen; text cut by a fixed... | docs/roadmap/agent-remaining/OPEN.md:3347 | S | unassigned |
| 1544 | Found: a titled note's every sentence scores on its title (_score, TITLE_WEIGHT), so the brief keeps up to four dated sentences of a note named for... | docs/roadmap/agent-remaining/OPEN.md:3350 | S | unassigned |
| 1545 | CI margin: Tests (Python 3.13) took 16 m 14 s of its 25 m timeout on the head that was scanned (3.11 took 15 m 01 s, 3.12 14 m 37 s). A slow runner... | docs/roadmap/agent-remaining/OPEN.md:3367 | M | unassigned |
| 1546 | Markers' Flag is still two previews (seg665-1006.md item 5). (from inbox670-1006.md) | docs/roadmap/agent-remaining/OPEN.md:3373 | S | unassigned |
| 1547 | Other jobruns detail strings that carry {exc} (grep note_finished and run.fail( in src/) were not audited; only the two named in item 5 were changed.... | docs/roadmap/agent-remaining/OPEN.md:3385 | S | unassigned |
| 1548 | An opened row with no title starts with its text, whose first line's centre is 19.4px from the top against the chevron's and cluster's 22px (2.6px... | docs/roadmap/agent-remaining/OPEN.md:3389 | M | unassigned |
| 1549 | The topic bar wraps to two rows at 390 (348x102), measured identical on the base: the Branch line and the reset go to a second row under the open... | docs/roadmap/agent-remaining/OPEN.md:3398 | S | unassigned |
| 1550 | "last week" in Find anything: a window or the words. (from deepen-b-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3422 | S | unassigned |
| 1551 | Any real-model behaviour of the agent (CLAUDE.md section 4). (from deepen-b-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3424 | S | unassigned |
| 1552 | The rail-dot alignment at 390 (0 px at 1440). (from deepen-b-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3425 | S | unassigned |
| 1553 | The agent panel with no model: 16 of 20 controls disabled (AGENT_SKILLS_REFORM, Deepened row 1). (from deepen-b-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3429 | S | unassigned |
| 1554 | The p5 API list in scratchpad/vendor_use.py is a Chromium dump pinned to 1.9.4; regenerate it with a p5 upgrade. (from vendor-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3435 | S | unassigned |
| 1555 | Brief 2 (consistency lints): HISTORY mentions it only as an owner reference; no record of the lint set being built as the brief. (from briefs-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3436 | S | unassigned |
| 1556 | Brief 3 (prefs, api.stream/upload, innerHTML): HISTORY line 43146 area still lists api.stream/api.upload and the no-bare-fetch lint as not built.... | docs/roadmap/agent-remaining/OPEN.md:3437 | S | unassigned |
| 1557 | Brief 8 ( autocomplete, connections rail): HISTORY has only the plan table rows, no Built record. (from briefs-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3441 | S | unassigned |
| 1558 | Brief 9 (job runtime): tests/test_jobs.py the brief names does not exist; HISTORY has no Built record. (from briefs-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3442 | S | unassigned |
| 1559 | Brief 14 (docs condensed): HANDOVER.md is 486 lines against a 300-line done-when; NEXT_FABLE_WINDOW.md does not exist. (from briefs-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3445 | S | unassigned |
| 1560 | Brief 18 (the complete open scope): an umbrella brief, only section A recorded in HISTORY. (from briefs-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3448 | S | unassigned |
| 1561 | Briefs 25 to 31 (group): each plan phase list is still open; "nothing is built" for 25. (from briefs-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3449 | S | unassigned |
| 1562 | Brief 33 (rest of WORLD_CLASS_PLAN): HANDOVER.md:450 names it as the next brief. (from briefs-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3451 | S | unassigned |
| 1563 | Rule 5: "the managed runner killed" has nothing to act on: the app starts no model runner (extras.py says llama-server is run by hand), so an... | docs/roadmap/agent-remaining/OPEN.md:3523 | S | unassigned |
| 1564 | **Already fixed 2026-11-02 (a30d-1102; Brief 69 block in library-lazy.css: under pointer coarse or below 820px the output grip is var(--target-min), 44px, grown upward so the hairline stays).** The output grip is 24 px (the grip recipe), under touch.js's 44 px floor at 390; touch.js does not list the run panel as a surface. [docs42b] | docs/roadmap/agent-remaining/OPEN.md:3537 | S | unassigned |
| 1565 | js-beautify on a selection is not used (a selection keeps the conservative re-indent); vendor_use.py reports "selection" as its one unused... | docs/roadmap/agent-remaining/OPEN.md:3538 | S | unassigned |
| 1566 | **Not reproduced 2026-11-02 (a30d-1102; 5 seeded notes with long titles, 3 to 4 tags, links and a reminder, touch context: at 390 the meta line is 316px in a 360px li and at 320 it is 246px in a 290px li, scrollWidth equals clientWidth, no fact ends past the line's right edge, page scrollWidth 390 and 320).** #entry-list div.entry-meta.note-meta: 64 to 72px wider than its card at 320 and 390 (one per note, 33 to 42 nodes); #entry-list li 24 to 48px at 320. | docs/roadmap/agent-remaining/OPEN.md:3555 | S | unassigned |
| 1567 | A model's proposed act through the registry: acts.propose is tested but nothing calls it; the agent's write tools keep their own confirm path... | docs/roadmap/agent-remaining/OPEN.md:3586 | S | unassigned |
| 1568 | "Grounded in" says 4 notes while the support chip says "3 of 3 from your notes" on "tell me about golf" (seen in a sweep screenshot, not... | docs/roadmap/agent-remaining/OPEN.md:3590 | S | unassigned |
| 1569 | The decision 54 sum rule: "12 * 7 is 84." is read as its own "Read as" because it restates the question's sum; every other utility answer has a "Read... | docs/roadmap/agent-remaining/OPEN.md:3591 | S | unassigned |
| 1570 | Scorecard: the follow-up column needs decision 58's 200 spoken lines, which are not written; variety's minimum is 3 of 20 against the plan's target... | docs/roadmap/agent-remaining/OPEN.md:3615 | S | unassigned |
| 1571 | Brief 34 second part (INBOX 752): snapping transitions per minute (60 Hz joint sampling), 12 distinct idle motions per ten minutes and reaction... | docs/roadmap/agent-remaining/OPEN.md:3627 | S | unassigned |
| 1572 | Decision 58's core/background.py registry (name, started, stop) is not built; the lint only counts sites. Brief 63 neighbour.... | docs/roadmap/agent-remaining/OPEN.md:3643 | S | unassigned |
| 1573 | 49 routes need a test or removal (tests/test_routes_named.py SEED); several are reached by a loop over verbs, check before writing duplicates.... | docs/roadmap/agent-remaining/OPEN.md:3645 | S | unassigned |
| 1574 | The drag's feel by hand; the open-card ring with a keyboard user. | agent/graph100-1011:docs/roadmap/archive/agent-remaining/graph100-1011.md:27 | S | unassigned W34: unverifiable, w34-L2r-1111.md. |
| 1575 | /tmp filled to 100% once during this session (ENOSPC); outputs moved to /dev/shm. | agent/graph100-1011:docs/roadmap/archive/agent-remaining/graph100-1011.md:33 | S | unassigned |
| 1576 | INBOX 883, 884, 885 and 874 are not numbered items in this branch's docs/roadmap/INBOX.md (874 appears only in the "Placed" log), so inbox_resolve.py... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/phonegraph-1011.md:6 | M | unassigned |
| 1577 | ~~851 Select-mode tick in the gutter: card and row heights unchanged, centre within 1px of the first line.~~ **W34: fixed** (w34-L1-1111.md) | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/ownerfix3-1011.md:7 | S | unassigned |
| 1578 | 887/888/889 are not in this branch's docs/roadmap/INBOX.md (they live on the orchestrator's); resolve them there with python... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/phone2-1011.md:7 | S | unassigned |
| 1579 | ~~19d3155c5: merge of the working branch (next-free-port kept with the gate).~~ **W34: stale** (w34-L1-1111.md) | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/lansafe-1011.md:21 | S | unassigned |
| 1580 | ~~The staged gate ran per commit for 852, 851 and 847; 853, 854 and 856 were gated once together on the final staged tree.~~ **W34: stale** (w34-L1-1111.md) | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/ownerfix3-1011.md:22 | S | unassigned |
| 1581 | ~~Contents sub-tab's outline shifts 0.013 to 0.016 on first paint (contents-outline 266px to 634px).~~ **W34: fixed** (w34-L1-1111.md) | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/ownerfix3-1011.md:25 | S | unassigned |
| 1582 | Pending device requests live in memory (lantrust._pending, 10 minutes); a restart forgets them, and a device that asked and went away still shows a... | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/lansafe-1011.md:41 | S | unassigned W34: skipped (backend spoke), w34-fix1-1111.md. |
| 1583 | ~~Stray files from this run at the filesystem root: /lansafe-gz.py, /lansafe-tf.txt (removal was refused by the sandbox).~~ **W34: fixed** (w34-L1-1111.md) | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/lansafe-1011.md:51 | S | unassigned |
| 1584 | SESSION_BRIEFS Brief 102: the Built block move to HISTORY is the orchestrator's at merge. | agent/mergetrain-1011:docs/roadmap/archive/agent-remaining/lansafe-1011.md:53 | S | unassigned |
| 1585 | The chime is not heard by a sweep; only that no error is thrown. | agent/voiceup-1011:docs/roadmap/archive/agent-remaining/voiceup-1011.md:17 | S | unassigned W34: unverifiable, w34-L2r-1111.md. |
| 1586 | The Tidy review title was 12px because .card h3 (the eyebrow) outranked .tidy-title; fixed here, but other sheets' h3 titles may carry the same rank... | agent/voiceup-1011:docs/roadmap/archive/agent-remaining/voiceup-1011.md:20 | S | unassigned |
| 1587 | Agent: tool-calling with its own controls: which tools are allowed this turn, max rounds, visible plan/progress, and a stop that... | docs/roadmap/BACKLOG.md:185 | S | unassigned |
| 1588 | A dependency-vulnerability sweep (pip-audit / npm audit equivalent for the vendored JS, since nothing currently checks either)... | docs/roadmap/BACKLOG.md:564 | M | unassigned |
| 1589 | Dynamically switch models by task complexity. Next: the manual per-mode assignment this item says to build first exists... | docs/roadmap/BACKLOG.md:820 | L | unassigned |
| 1590 | MAX_CLIENT_HISTORY turns of prior Q&A go up each time, whole. | docs/roadmap/BACKLOG.md:908 | S | unassigned |
| 1591 | That taking several rounds deliberately is expected, plan, act, check, answer | docs/roadmap/BACKLOG.md:966 | S | unassigned |
| 1592 | What to do when a tool fails, the error is returned with no guidance, so small models give up or repeat the same call | docs/roadmap/BACKLOG.md:968 | S | unassigned |
| 1593 | The six named tools are still missing. Check the registry's real count first: the README says 65, while this section said 58. | docs/roadmap/BACKLOG.md:1085 | S | unassigned |
| 1594 | execute_tool already files writes as ai:<tool> through events.acting_as (ai/tools/__init__.py), so a new tool only needs a test... | docs/roadmap/BACKLOG.md:1086 | S | unassigned |
| 1595 | Fonts (#font-seg offers System, Serif, Mono, Arial; Next: a dyslexia-friendly face must be vendored under frontend/vendor/fonts/... | docs/roadmap/BACKLOG.md:1122 | M | unassigned |
| 1596 | The agent controlling the screen itself, "allow the agent to control your screen within the application to navigate and make... | docs/roadmap/BACKLOG.md:1250 | L | unassigned |
| 1597 | Crash-safe recovery for a re-index or a model download interrupted mid-way. Half-checked directly. The re-index half is safe by... | docs/roadmap/BACKLOG.md:1405 | L | unassigned |
| 1598 | A "forgotten connections" widget: proactive rather than on-demand. Pointer: WORLD_CLASS_PLAN I1 "The night shift" (its findings... | docs/roadmap/BACKLOG.md:1644 | L | unassigned |
| 1599 | Numeric X/Y/W/H/rotation entry: Pointer: scratchpad/audit1005/features.md section 4 row C3 (P2, the Format panel, Phase B).... | docs/roadmap/BACKLOG.md:1984 | S | unassigned |
| 1600 | Smaller polish items: Pointer: scratchpad/audit1005/features.md section 4 rows C3 (resize from centre, flip), C9 (whole-object... | docs/roadmap/BACKLOG.md:2006 | M | unassigned |
| 1601 | Tests and guards: a lazy-load test (not in app_js_files), a vendored-file licence notice test, a CSP test that no inline style or... | docs/roadmap/BACKLOG.md:2653 | M | unassigned |
| 1602 | Nav-history popup, genuinely broken this time, reproduced: a history of short single-word entries (a plain tab visit, no... | docs/roadmap/BACKLOG.md:3361 | M | unassigned |
| 1603 | The AI's honesty surface is the app's real differentiator. Answers already carry the notes behind them and the librarian is... | docs/roadmap/BACKLOG.md:3741 | M | unassigned |
| 1604 | It can read everything, not a retrieved sample. A cloud tool meters tokens, so it retrieves five notes and hopes. A local model... | docs/roadmap/BACKLOG.md:3780 | M | unassigned |
| 1605 | It can be wrong safely. Nothing leaves the machine, so a speculative suggestion costs nothing but a dismissal. That is why... | docs/roadmap/BACKLOG.md:3786 | M | unassigned |
| 1606 | Real-time collaboration. Same reason, more so. | docs/roadmap/BACKLOG.md:3889 | S | unassigned |
| 1607 | Mid-work drop, 2026-09-14 morning, verbatim (the owner), the last scan. "finish all the agents, scan for bugs and high complexity... | docs/roadmap/BACKLOG.md:3979 | L | unassigned |
| 1608 | Mid-work drop, 2026-09-20, verbatim (the owner). "What usability and information architecture things are missing and can be... | docs/roadmap/BACKLOG.md:4023 | L | unassigned |
| 1609 | "Is it possible to create custom libraries like the ones vendored that are really good and extensive in their purpose, which can... | docs/roadmap/BACKLOG.md:4171 | L | unassigned |
| 1610 | "no way to clear the destination history or delete individual records??" Recommendation: add clear-all and per-record delete to the destination... | docs/roadmap/CHAT_PLAN.md:865 | S | unassigned |
| 1611 | "it got jokes from another note but not the separate one from the top of the matching records" Recommendation: an answer names the note each claim... | docs/roadmap/CHAT_PLAN.md:869 | M | unassigned |
| 1612 | "These notes do not mention “summarise”." Recommendation: a claim with no source note is dropped before the answer is written, with the summarise... | docs/roadmap/CHAT_PLAN.md:883 | S | unassigned |
| 1613 | "Intext reference should be square brackets or styled differently." Recommendation: in-text references use square brackets or a styled marker... | docs/roadmap/CHAT_PLAN.md:937 | M | unassigned |
| 1614 | "should we store recently retrieved website content for easy reretieval??" Recommendation: keep fetched page text with its fetch time and a re-fetch... | docs/roadmap/CHAT_PLAN.md:948 | M | unassigned |
| 1615 | INBOX 771 the owner asleep: continue autonomously through every open brief (standing) | docs/roadmap/INBOX.md:143 | L | unassigned |
| 1616 | INBOX 807 Where your data went: say what each destination fetched or sent and why | docs/roadmap/INBOX.md:183 | S | unassigned |
| 1617 | Brief 46: measure the table (WORLD_CLASS 25 bars) | docs/roadmap/SESSION_BRIEFS.md:1526 | M | unassigned |
| 1618 | Briefs 58 and 59: the stylesheet's structure (13b) and the surfaces (13c) | docs/roadmap/SESSION_BRIEFS.md:1592 | L | unassigned |
| 1619 | Brief 64: measure the foundation (F0): done as found-1010; confirm | docs/roadmap/SESSION_BRIEFS.md:1634 | S | unassigned |
| 1620 | Briefs 72 to 74: trust contract (WORLD_CLASS 28): 72a/72b/73/74 landed with leftovers; confirm remaining rules | docs/roadmap/SESSION_BRIEFS.md:1700 | M | unassigned |
| 1621 | Brief 85 (second use of the number): the launch splash reimagined (INBOX 834) | docs/roadmap/SESSION_BRIEFS.md:1733 | M | unassigned |
| 1622 | Brief 98: goals and lists (INBOX 861) | docs/roadmap/SESSION_BRIEFS.md:1807 | L | unassigned |
| 1623 | Brief 99: the full functionality scan (scan-1011 built the scan; its Open list is in the ledger rows) | docs/roadmap/SESSION_BRIEFS.md:1813 | S | unassigned |
| 1624 | The agent activity panel, see AGENT_SKILLS_REFORM.md Phase C, which owns it. | docs/roadmap/UI_MODERNISATION_PLAN.md:259 | S | unassigned |
| 1625 | No new markup. Both entries are rows in existing catalogues, so there is no new id, no new surface and nothing for the recipe index to cover. | docs/roadmap/UI_MODERNISATION_PLAN.md:299 | S | unassigned |
| 1626 | Two ranks, not five. The name is the row. Under it, one wrapping line of facts at one rank: what the file is (kind, size, pages, added), whether it... | docs/roadmap/UI_MODERNISATION_PLAN.md:311 | M | unassigned |
| 1627 | A fact is not a control and a control is not a chip. The reading badge states; the "Used in" chips open the note they name; the kebab acts. A row... | docs/roadmap/UI_MODERNISATION_PLAN.md:321 | M | unassigned |
| 1628 | A fact is a line of text, a disclosure is a control, and neither is the other. Where the picture is used is a count you read (Used in 2 places, the... | docs/roadmap/UI_MODERNISATION_PLAN.md:336 | M | unassigned |
| 1629 | The owner, 2026-10-03 night, verbatim. "I keep experiencing scroll jump when scrolling with two fingers on my trackpad?? idk". Placed: the... | docs/roadmap/UI_MODERNISATION_PLAN.md:1208 | L | unassigned |
| 1630 | INBOX 760, card dates. The time floats mid-card on a card the grid stretched taller than its content (about 110px under it on the tallest card, 40px... | docs/roadmap/UI_MODERNISATION_PLAN.md:1238 | M | unassigned |
| 1631 | "popup panels appearing at the start on a new install are messy and clash/overlap a lot" Recommendation: one first-run queue with no overlapping... | docs/roadmap/UI_MODERNISATION_PLAN.md:1247 | M | unassigned |
| 1632 | "that's the box in the corner I was telling you temporarily appeared" Recommendation: reproduce on a fresh profile and name the box in the owner's... | docs/roadmap/UI_MODERNISATION_PLAN.md:1253 | M | unassigned |
| 1633 | "These elements in the lightbox aren’t the same height" Recommendation: give lightbox controls one height token and measure their heights in the... | docs/roadmap/UI_MODERNISATION_PLAN.md:1261 | S | unassigned |
| 1634 | "this panel looks like a demo and not professional" Recommendation: name the panel, then give it the designed empty, error and first-run states that... | docs/roadmap/UI_MODERNISATION_PLAN.md:1268 | M | unassigned |
| 1635 | INBOX 795, UI, the owner 2026-10-10 22:55Z, two screenshots: "just make sure that the app actually recieves a propper ui polish and refinement. there... | docs/roadmap/UI_MODERNISATION_PLAN.md:1544 | L | unassigned |
| 1636 | INBOX 800, UI, the owner 2026-10-11 02:40Z, verbatim: "Can you do another devibecoding, ui/ux modernisation and professionalisation sweep across all... | docs/roadmap/UI_MODERNISATION_PLAN.md:1552 | L | unassigned |
| 1637 | #wb-topbar is 104px at 390. Owner: responsive.md. | docs/roadmap/WORLD_CLASS_PLAN.md:980 | S | unassigned |
| 1638 | The same decision as 62; moved with it. | docs/roadmap/WORLD_CLASS_PLAN.md:1604 | S | unassigned |
| 1639 | Found by scan, 2026-09-19 (the session, not the owner). Ten routes the app serves that frontend/js/*.js never names, from... | docs/roadmap/WORLD_CLASS_PLAN.md:2069 | L | unassigned |
| 1640 | Tabs lose their names on a laptop. Under about 1100px the tab strip is icons only with the active tab labelled, so six of seven tabs are guesses.... | docs/roadmap/WORLD_CLASS_PLAN.md:2329 | S | unassigned |
| 1641 | **Already built (Local chip, DESIGN.md row 677; 2026-10-19).** Offline promise, visible. The Privacy receipt now exists; the top bar should say "Local" with the same verdict, one click to the receipt. S, Sonnet. | docs/roadmap/WORLD_CLASS_PLAN.md:2357 | S | unassigned |
| 1642 | The window title names the view and the open item (22.1.1). | docs/roadmap/WORLD_CLASS_PLAN.md:2363 | S | unassigned |
| 1643 | Every list with more than 20 rows can be filtered by typing. | docs/roadmap/WORLD_CLASS_PLAN.md:2373 | S | unassigned |
| 1644 | Right-click works on every card and row, with a hold as its twin on touch. | docs/roadmap/WORLD_CLASS_PLAN.md:2374 | S | unassigned |
| 1645 | The "Default Space" chip is hidden when only one space exists (it is on every card today and says nothing). | docs/roadmap/WORLD_CLASS_PLAN.md:2378 | S | unassigned |
| 1646 | Glass is still on some surfaces the performance plan listed for removal; the glass-off list lint should cover every blurred surface. | docs/roadmap/WORLD_CLASS_PLAN.md:2393 | S | unassigned |
| 1647 | 0.3.x (now): finish INBOX 430, green CI, the full suite, then publish. | docs/roadmap/WORLD_CLASS_PLAN.md:2432 | L | unassigned |
| 1648 | The owner, 2026-09-23 night, verbatim. "for me, trust in the application isn't just the information it shows but that is very much a key point, it is... | docs/roadmap/WORLD_CLASS_PLAN.md:2482 | L | unassigned |
| 1649 | The owner, 2026-10-03, verbatim. "Can you make sure everything in the frontend, backend, function, utility and process for how the user can write... | docs/roadmap/WORLD_CLASS_PLAN.md:3056 | L | unassigned |
| 1650 | "Is it possible to make use of python libraries that the user already may have installed globally on their computer so the user doesn’t have to... | docs/roadmap/WORLD_CLASS_PLAN.md:3107 | M | unassigned |
| 1651 | "Does the user have to be connected to the interned for the initial install for installing all the dependencies?? Should the user be informed of that... | docs/roadmap/WORLD_CLASS_PLAN.md:3111 | M | unassigned |
| 1652 | "I also want to integrate and use the new vendored repositories and libraries better and also see if there are more complimentary libraries and repos... | docs/roadmap/WORLD_CLASS_PLAN.md:3117 | L | unassigned |
| 1653 | "did you vendor the other libraries and binaries?? do we need to?? what else is there to do??" Recommendation: answer in ANALYSIS.md: which libraries... | docs/roadmap/WORLD_CLASS_PLAN.md:3132 | M | unassigned |
| 1654 | "doesnt harper use a binary though?? are there any other repos or libraries that we can vendor??" Recommendation: Harper is a WebAssembly build in... | docs/roadmap/WORLD_CLASS_PLAN.md:3134 | M | unassigned |
| 1655 | ~~A model that fails mid-answer leaves an error line, not the composed answer (api/routes_chat.py ~1963 to 1976); write tests/test_chat_degrades.py...~~ **W34: fixed** (w34-L1-1111.md) | docs/roadmap/archive/agent-remaining/assistant-1010.md:10 | S | unassigned |
| 1656 | ~~Re-run the 37-question probe (section 0 method) on Brief 35's head, since the triage may already change findings 1 to 3.~~ **W34: stale** (w34-L1-1111.md) | docs/roadmap/archive/agent-remaining/assistant-1010.md:13 | S | unassigned |
| 1657 | Routes match only @router.<method> and @app.<method> decorators; another router name is missed. | docs/roadmap/archive/agent-remaining/codemap-1010.md:7 | S | unassigned W34: true, w34-L2r-1111.md. |
| 1658 | Not wired into scripts/gate.sh or CI; it runs only as part of the test suite. | docs/roadmap/archive/agent-remaining/codemap-1010.md:10 | S | unassigned |
| 1659 | Known failures this worktree inherits, none from this work: test_scratchpad_size.py (1,018 tracked files over a cap of 1,003 before this branch; this... | docs/roadmap/archive/agent-remaining/drawio-1010.md:51 | M | unassigned |
| 1660 | ~~INBOX 775, 792 and 796 stay in INBOX for the orchestrator to resolve at merge.~~ **W34: stale** (w34-L1-1111.md) | docs/roadmap/archive/agent-remaining/graphfeel-1010.md:9 | S | unassigned |
| 1661 | The first server grew to 8.5 GB resident over 35 minutes of seeding and sweeps; after a restart it sat at 0.74 to 2.1 GB. Not reproduced, cause not... | docs/roadmap/archive/agent-remaining/measure-1010.md:5 | M | unassigned |
| 1662 | **Fixed 2026-11-02 (a30d-1102; scratchpad/ui-sweeps/measure-static.py key_checks counts toLowerCase, a local alias and each case of switch (e.key); tests/test_measure_keys_1102.py; 748 checks before, 1086 after).** Key checks written as key.toLowerCase() === "x" or switch (e.key) are not counted. | docs/roadmap/archive/agent-remaining/measure-1010.md:9 | S | unassigned |
| 1663 | The --staged gate took 6 minutes with other gates running; its slowest step is worth measuring. | docs/roadmap/archive/agent-remaining/proofing-1010.md:7 | S | unassigned |
| 1664 | Decision 33: tense shift for a past-due plan, number agreement, comma capitalisation, word-boundary title cuts, list "and" and Oxford comma, quote... | docs/roadmap/archive/agent-remaining/spec39-1010.md:6 | S | unassigned W34: owner-call (tracked in the plans), w34-L1-1111.md. |
| 1665 | Decision 41: date arithmetic, word count and reading time, text transforms. | docs/roadmap/archive/agent-remaining/spec39-1010.md:12 | S | unassigned W34: owner-call (tracked in the plans), w34-L1-1111.md. |
| 1666 | Decision 45: model choosing among readings (needs the evals marker). | docs/roadmap/archive/agent-remaining/spec39-1010.md:14 | S | unassigned W34: owner-call (tracked in the plans), w34-L1-1111.md. |
| 1667 | Gemini's light rewrites ("I" to "you", CHAT_PLAN decision 23) were dropped because they changed quoted text and broke grounding; a marked rewrite... | docs/roadmap/archive/agent-remaining/triage-1010.md:29 | L | unassigned W34: owner-call (tracked in the plans), w34-L1-1111.md. |
| 1683b | Desk half of B1, B3, B5, B6 not built: pose-keyed lower-body and nebula variants rendered into the frames (`scripts/render_desk_frames.*`, `sprites.py`), a live Trail on the veil (`behaviour.py`), and the measures (desk nebula changed-pixel flicker 363 feminine and 331 masculine or lower, lower body within 4 degrees of the torso in a browser, under 2 ms a frame at 4x CPU). Built so far: per-strand arrangements in `Flow.view(frame=)`, and the app (1e686a2, 5edaab1). Held back to avoid the engine lane (landing, loops, shared mind) re-rendering frames under it. | companion-asks.md B1 | M | unassigned |

### Unassigned, proposed batches

Each batch is one agent, 5 to 15 rows, one surface, by id range (the ids above are contiguous per batch). Model and effort follow CLAUDE.md standing order 4: Opus for design judgement (layout, visual, plan phases, engine), Sonnet for named labour (verification, fixtures, lints, sweeps, bugs whose fix is named). Verification batches run a real browser or model where the row says so; a row that needs hardware the sandbox lacks (a real iPhone, Windows, a real model) cannot close in a batch and stays as a stated non-verification.

| batch | surface | ids | rows | S / M / L | model, effort |
| --- | --- | --- | --- | --- | --- |
| B01 | Verification of unverified claims | 184 to 197 | 14 | 14 / 0 / 0 | Sonnet, medium |
| B02 | Verification of unverified claims | 198 to 211 | 14 | 13 / 1 / 0 | Sonnet, medium |
| B03 | Verification of unverified claims | 212 to 225 | 14 | 14 / 0 / 0 | Sonnet, medium |
| B04 | Verification of unverified claims | 226 to 238 | 13 | 12 / 1 / 0 | Sonnet, medium |
| B05 | Red tests, CI and ratchets | 239 to 253 | 15 | 11 / 3 / 1 | Sonnet, medium |
| B06 | Red tests, CI and ratchets | 254 to 268 | 15 | 10 / 5 / 0 | Sonnet, medium |
| B07 | Red tests, CI and ratchets | 269 to 283 | 15 | 11 / 3 / 1 | Sonnet, medium |
| B08 | Packaging, release and installers | 284 to 296 | 13 | 7 / 5 / 1 | Sonnet, high |
| B09 | Packaging, release and installers | 297 to 309 | 13 | 3 / 5 / 5 | Opus, high |
| B10 | Packaging, release and installers | 310 to 321 | 12 | 5 / 6 / 1 | Sonnet, high |
| B11 | Phone, LAN and security | 322 to 336 | 15 | 9 / 5 / 1 | Opus, medium |
| B12 | Phone, LAN and security | 337 to 351 | 15 | 9 / 5 / 1 | Opus, medium |
| B13 | Phone, LAN and security | 352 to 366 | 15 | 5 / 5 / 5 | Opus, high |
| B14 | Phone, LAN and security | 367 to 381 | 15 | 4 / 9 / 2 | Opus, high |
| B15 | Phone, LAN and security | 382 to 394 | 13 | 7 / 6 / 0 | Opus, high |
| B16 | Composer, engine and Ask | 395 to 409 | 15 | 7 / 3 / 5 | Opus, high |
| B17 | Composer, engine and Ask | 410 to 424 | 15 | 9 / 1 / 5 | Opus, high |
| B18 | Composer, engine and Ask | 425 to 439 | 15 | 11 / 3 / 1 | Opus, medium |
| B19 | Composer, engine and Ask | 440 to 454 | 15 | 12 / 1 / 2 | Opus, high |
| B20 | Composer, engine and Ask | 455 to 469 | 15 | 10 / 3 / 2 | Opus, high |
| B21 | Composer, engine and Ask | 470 to 484 | 15 | 5 / 5 / 5 | Opus, high |
| B22 | Composer, engine and Ask | 485 to 499 | 15 | 4 / 8 / 3 | Opus, high |
| B23 | Composer, engine and Ask | 500 to 514 | 15 | 2 / 10 / 3 | Opus, high |
| B24 | Composer, engine and Ask | 515 to 529 | 15 | 2 / 5 / 8 | Opus, high |
| B25 | Composer, engine and Ask | 530 to 543 | 14 | 9 / 4 / 1 | Opus, medium |
| B26 | Chat, Guide, agent and skills | 544 to 558 | 15 | 9 / 5 / 1 | Opus, medium |
| B27 | Chat, Guide, agent and skills | 559 to 573 | 15 | 11 / 4 / 0 | Opus, medium |
| B28 | Chat, Guide, agent and skills | 574 to 588 | 15 | 10 / 4 / 1 | Opus, medium |
| B29 | Chat, Guide, agent and skills | 589 to 603 | 15 | 11 / 4 / 0 | Opus, medium |
| B30 | Chat, Guide, agent and skills | 604 to 618 | 15 | 9 / 3 / 3 | Opus, high |
| B31 | Chat, Guide, agent and skills | 619 to 633 | 15 | 7 / 7 / 1 | Opus, high |
| B32 | Chat, Guide, agent and skills | 634 to 648 | 15 | 5 / 6 / 4 | Opus, high |
| B33 | Chat, Guide, agent and skills | 649 to 660 | 12 | 5 / 4 / 3 | Opus, high |
| B34 | Atlas and the companion | 661 to 673 | 13 | 3 / 6 / 4 | Opus, high |
| B35 | Atlas and the companion | 674 to 686 | 13 | 2 / 9 / 2 | Opus, high |
| B36 | Atlas and the companion | 687 to 699 | 13 | 7 / 4 / 2 | Opus, high |
| B37 | Mind map | 700 to 713 | 14 | 6 / 5 / 3 | Opus, high |
| B38 | Mind map | 714 to 727 | 14 | 6 / 5 / 3 | Opus, high |
| B39 | Mind map | 728 to 741 | 14 | 4 / 6 / 4 | Opus, high |
| B40 | Mind map | 742 to 755 | 14 | 4 / 3 / 7 | Opus, high |
| B41 | Mind map | 756 to 769 | 14 | 5 / 3 / 6 | Opus, high |
| B42 | Mind map | 770 to 783 | 14 | 9 / 2 / 3 | Opus, high |
| B43 | Mind map | 784 to 791 | 8 | 3 / 2 / 3 | Opus, high |
| B44 | Whiteboard and boards | 792 to 805 | 14 | 8 / 4 / 2 | Opus, high |
| B45 | Whiteboard and boards | 806 to 819 | 14 | 13 / 1 / 0 | Opus, medium |
| B46 | Whiteboard and boards | 820 to 833 | 14 | 3 / 10 / 1 | Opus, high |
| B47 | Whiteboard and boards | 834 to 847 | 14 | 6 / 8 / 0 | Opus, high |
| B48 | Whiteboard and boards | 848 to 861 | 14 | 9 / 4 / 1 | Opus, medium |
| B49 | Whiteboard and boards | 862 to 875 | 14 | 6 / 3 / 5 | Opus, high |
| B50 | Whiteboard and boards | 876 to 889 | 14 | 1 / 5 / 8 | Opus, high |
| B51 | Whiteboard and boards | 890 to 903 | 14 | 6 / 7 / 1 | Opus, high |
| B52 | Whiteboard and boards | 904 to 917 | 14 | 8 / 3 / 3 | Opus, high |
| B53 | Whiteboard and boards | 918 to 927 | 10 | 6 / 2 / 2 | Opus, high |
| B54 | Graph | 928 to 941 | 14 | 8 / 3 / 3 | Opus, high |
| B55 | Graph | 942 to 955 | 14 | 6 / 7 / 1 | Opus, high |
| B56 | Graph | 956 to 968 | 13 | 7 / 2 / 4 | Opus, high |
| B57 | Timeline, reminders and notifications | 969 to 982 | 14 | 11 / 2 / 1 | Opus, medium |
| B58 | Timeline, reminders and notifications | 983 to 996 | 14 | 7 / 7 / 0 | Opus, high |
| B59 | Timeline, reminders and notifications | 997 to 1010 | 14 | 10 / 3 / 1 | Opus, medium |
| B60 | Timeline, reminders and notifications | 1011 to 1024 | 14 | 8 / 6 / 0 | Opus, high |
| B61 | Timeline, reminders and notifications | 1025 to 1038 | 14 | 9 / 4 / 1 | Opus, medium |
| B62 | Documents and the code editor | 1039 to 1053 | 15 | 6 / 4 / 5 | Opus, high |
| B63 | Documents and the code editor | 1054 to 1068 | 15 | 13 / 2 / 0 | Opus, medium |
| B64 | Documents and the code editor | 1069 to 1083 | 15 | 7 / 8 / 0 | Opus, high |
| B65 | Documents and the code editor | 1084 to 1098 | 15 | 12 / 3 / 0 | Opus, medium |
| B66 | Documents and the code editor | 1099 to 1113 | 15 | 9 / 6 / 0 | Opus, medium |
| B67 | Documents and the code editor | 1114 to 1128 | 15 | 4 / 8 / 3 | Opus, high |
| B68 | Documents and the code editor | 1129 to 1143 | 15 | 5 / 5 / 5 | Opus, high |
| B69 | Documents and the code editor | 1144 to 1158 | 15 | 6 / 8 / 1 | Opus, high |
| B70 | Documents and the code editor | 1159 to 1173 | 15 | 3 / 10 / 2 | Opus, high |
| B71 | Documents and the code editor | 1174 to 1188 | 15 | 7 / 6 / 2 | Opus, high |
| B72 | Documents and the code editor | 1189 to 1203 | 15 | 5 / 7 / 3 | Opus, high |
| B73 | Documents and the code editor | 1204 to 1211 | 8 | 7 / 1 / 0 | Opus, medium |
| B74 | Library, OCR, audio and media | 1212 to 1226 | 15 | 12 / 1 / 2 | Opus, high |
| B75 | Library, OCR, audio and media | 1227 to 1241 | 15 | 11 / 4 / 0 | Opus, medium |
| B76 | Library, OCR, audio and media | 1242 to 1256 | 15 | 8 / 6 / 1 | Opus, high |
| B77 | Library, OCR, audio and media | 1257 to 1270 | 14 | 5 / 6 / 3 | Opus, high |
| B78 | Search, filing, tags and notes | 1271 to 1284 | 14 | 11 / 2 / 1 | Sonnet, high |
| B79 | Search, filing, tags and notes | 1285 to 1298 | 14 | 4 / 9 / 1 | Sonnet, high |
| B80 | Search, filing, tags and notes | 1299 to 1312 | 14 | 11 / 2 / 1 | Sonnet, high |
| B81 | Search, filing, tags and notes | 1313 to 1326 | 14 | 5 / 6 / 3 | Opus, high |
| B82 | Search, filing, tags and notes | 1327 to 1340 | 14 | 2 / 10 / 2 | Sonnet, high |
| B83 | Search, filing, tags and notes | 1341 to 1353 | 13 | 6 / 5 / 2 | Sonnet, high |
| B84 | Data, backup, export and import | 1354 to 1364 | 11 | 9 / 1 / 1 | Sonnet, high |
| B85 | Data, backup, export and import | 1365 to 1375 | 11 | 3 / 8 / 0 | Sonnet, medium |
| B86 | Data, backup, export and import | 1376 to 1386 | 11 | 3 / 7 / 1 | Sonnet, high |
| B87 | Settings, themes and UI system | 1387 to 1401 | 15 | 8 / 5 / 2 | Opus, high |
| B88 | Settings, themes and UI system | 1402 to 1416 | 15 | 11 / 4 / 0 | Opus, medium |
| B89 | Settings, themes and UI system | 1417 to 1431 | 15 | 12 / 3 / 0 | Opus, medium |
| B90 | Settings, themes and UI system | 1432 to 1446 | 15 | 11 / 4 / 0 | Opus, medium |
| B91 | Settings, themes and UI system | 1447 to 1461 | 15 | 4 / 9 / 2 | Opus, high |
| B92 | Settings, themes and UI system | 1462 to 1476 | 15 | 6 / 5 / 4 | Opus, high |
| B93 | Settings, themes and UI system | 1477 to 1490 | 14 | 10 / 4 / 0 | Opus, medium |
| B94 | Tooling, docs and housekeeping | 1491 to 1505 | 15 | 1 / 7 / 7 | Sonnet, medium |
| B95 | Tooling, docs and housekeeping | 1506 to 1520 | 15 | 8 / 2 / 5 | Sonnet, medium |
| B96 | Tooling, docs and housekeeping | 1521 to 1535 | 15 | 10 / 3 / 2 | Sonnet, medium |
| B97 | Tooling, docs and housekeeping | 1536 to 1550 | 15 | 12 / 2 / 1 | Sonnet, medium |
| B98 | Tooling, docs and housekeeping | 1551 to 1565 | 15 | 15 / 0 / 0 | Sonnet, medium |
| B99 | Tooling, docs and housekeeping | 1566 to 1580 | 15 | 14 / 1 / 0 | Sonnet, medium |
| B100 | Tooling, docs and housekeeping | 1581 to 1595 | 15 | 12 / 2 / 1 | Sonnet, medium |
| B101 | Tooling, docs and housekeeping | 1596 to 1610 | 15 | 3 / 6 / 6 | Sonnet, medium |
| B102 | Tooling, docs and housekeeping | 1611 to 1625 | 15 | 6 / 6 / 3 | Sonnet, medium |
| B103 | Tooling, docs and housekeeping | 1626 to 1640 | 15 | 4 / 7 / 4 | Sonnet, medium |
| B104 | Tooling, docs and housekeeping | 1641 to 1655 | 15 | 7 / 4 / 4 | Sonnet, medium |
| B105 | Tooling, docs and housekeeping | 1656 to 1667 | 12 | 9 / 2 / 1 | Sonnet, medium |

Order to run them: Verification and Red tests batches first (cheap, they shrink the list), then Phone, LAN and security after lanbar lands, Composer and Chat after atlas and composer, then the surface batches by the owner's priority (documents, graph, whiteboard, mind map, timeline) and Settings and UI last, since the Brief 92 whole-app pass touches it.

### Branches with commits not on the working branch

`git log gemini/composer-improvements..BRANCH` counts below. This clone is shallow and old merges used merge commits, so the count alone overstates: a branch is listed as not merged only when no merge subject or remaining file on the working branch names it (35 of 111). The other 76 show commits by ancestry but are on the branch by content.

| branch | commits | last subject | state |
| --- | --- | --- | --- |
| agent/mergetrain-1011 | 52 | Merge agent/meaning94-1011; meaning.js listed as a lazy piece; one-off | mergetrain (ended, unassigned) |
| agent/atlas-1011 | 25 | A3: "what did I search yesterday", "what ran overnight", "when did I l | atlas (ended, unassigned) |
| agent/cifix-1010 | 13 | CI M: changelog line | unmerged, unassigned: check, may be on the branch by cherry-pick |
| agent/data101b-1011 | 9 | Codemap and remaining list for data101b | data101b (ended, unassigned) |
| agent/cifix2-1011 | 8 | Search suggest places its list on a short timer instead of a frame loo | mergetrain (merging) |
| agent/graph100-1011 | 6 | Brief 100: CHANGELOG lines and the remaining list (graph100-1011) | mergetrain (merging) |
| agent/lansafe-1011 | 6 | lansafe-1011: remaining list (Brief 102) | mergetrain (merging) |
| agent/ownerfix3-1011 | 6 | Hover grounds: a lint and a sweep for square corners; the remaining fi | mergetrain (merging) |
| agent/throw-1011 | 6 | Atlas: its props read against its body and say what they are | throw (ended, unassigned) |
| agent/voiceup-1011 | 6 | voiceup-1011: the remaining file with the commits | mergetrain (merging) |
| agent/wbcolour-1011 | 6 | Whiteboard: one colour menu, and a selection's shared properties | mergetrain (merging) |
| agent/scan-1011 | 4 | Scan 1011: what the full scan found and left (remaining file), changel | mergetrain (merging) |
| agent/secscan-1011 | 4 | secscan-1011: remaining list | mergetrain (merging) |
| agent/chattime-1011 | 3 | chattime agent: what is left (Brief 103, INBOX 871) | mergetrain (merging) |
| agent/meaning94-1011 | 3 | Autocorrect leaves the editor: notes, chat, Ask and titles, with undo | mergetrain (merging) |
| agent/phone2-1011 | 3 | Files tab and OCR workspace on a phone: no sideways scroll from an ope | mergetrain (merging) |
| agent/phonegraph-1011 | 3 | Notifications: the read circle and remove cross are the row's centred  | mergetrain (merging) |
| agent/room101-1011 | 3 | Room under the caps: remaining ledger, two stale OPEN rows replaced | mergetrain (merging) |
| agent/themes95-1011 | 3 | Themes: Parchment and Ember dark retoned; every look 0 low-contrast (B | mergetrain (merging) |
| agent/devsize-1011 | 2 | INBOX 897 resolved: sizes per device measured and moved to HISTORY | mergetrain (merging) |
| agent/undoall-1011 | 2 | undoall-1011: the remaining ledger (INBOX 898) | undoall2 (ended, unassigned) |
| agent/wbfix-1011 | 2 | An undone shape on no layer comes back identical | mergetrain (merging) |
| agent/cifix3-1010 | 1 | CI red on 142aa25f5: ten failures from the Brief 80, pickers and Brief | unmerged, unassigned: check, may be on the branch by cherry-pick |
| agent/cifix4-1010 | 1 | CI fixes: /recordings takes a cursor, insight questions skip the overv | unmerged, unassigned: check, may be on the branch by cherry-pick |
| agent/cifix5-1011 | 1 | CI red: reminder notifier on the pool, no console flash, stale toast e | unmerged, unassigned: check, may be on the branch by cherry-pick |
| agent/codeql-1010 | 1 | CodeQL-proof census.py and codemap.py: bounded route regex, case-insen | unmerged, unassigned: check, may be on the branch by cherry-pick |
| agent/gzip-1010 | 1 | Boot gzip budget: MCP snippet and LAN state render move into the lazy  | unmerged, unassigned: check, may be on the branch by cherry-pick |
| agent/placement-1010 | 1 | Placed from the owner's list, 2026-10-10: 133 items into the plans | unmerged, unassigned: check, may be on the branch by cherry-pick |
| agent/rebrand-1011 | 1 | Rename the product to Tessellate, formerly MemoryMap AI (INBOX 903) | rebrand (ended, unassigned) |
| agent/restart-1011 | 1 | Restart works in every launch, and the new copy waits for the old one | mergetrain (merging) |
| agent/review56-1010 | 1 | Brief 56 re-run: already built (021fd6c9c, 41655fc24); remaining list  | unmerged, unassigned: check, may be on the branch by cherry-pick |
| agent/tags89-1011 | 1 | Notes: a "+ Tag" chip on notes with fewer than three tags, with sugges | mergetrain (merging) |
| agent/first101c-1011 | 0 | INBOX 895 to 897: the composer's reach, the LAN status bar, sizes per  | queued: first101c |
| agent/graphfeel100-1011 | 0 | Merge typos90b: 80 of the owner's typos understood (a stray semicolon, | unmerged, unassigned: check, may be on the branch by cherry-pick |
| agent/logo-1011 | 0 | INBOX 895 to 902 placed: composer, sizes, undo, time words, LAN toggle | logo (ended, unassigned) |

Branches 76 of 111 (the -1010 round and most of -1011) are merged by content; their remaining files are the head's agent-remaining files and OPEN.md rows above.

## Left by the ownerfix2 agent (Brief 91, the owner's small UI reports, merged 2026-10-11)

The file is `docs/roadmap/archive/agent-remaining/ownerfix2-1011.md`.

- INBOX 839, graph: only the drag's heat is changed (graph-worker.js `dragHeat`). A single-tick 7.1px step still shows in one of two 8px runs (a non-dragged node, 3 ticks after release); not traced. The main-thread glide (graph-canvas.js `gcGlideStep`) was not touched. (checked 2026-11-09) [verified 2026-11-10: true, graph-worker.js dragHeat present; the 7.1px step was not traced]
- Attach: at 390 `#attach-image` reads a 999px radius while `#attach-note` reads 4.8px in the chat composer row (the owner's 841 asked for one corner; only the gear was in scope). 04-chat-dock-appearance.css, `#attach-image.has-attachments` near line 2854 is the nearest rule. (checked 2026-11-09) [verified 2026-11-10: true, 04-chat-dock-appearance.css:2810 #attach-image rule present; radius mismatch not changed]
- The guide topic `ask-chat` is at 1916 of 1919 characters (`tests/test_help_controls.py`), so Agent-with-no-model could not be named in the Guide without trimming another sentence. The segment's title and the hint line carry it. (checked 2026-11-09) [verified 2026-11-10: true, help_topics_core.py:1230 ask-chat present; char budget note still stands]
- `graphjitter.js`-style rAF sampling is useless on a loaded machine (frames 50 to 170 ms apart, load average 10 to 33); the worker-tick measure (graphticks.js: per-tick steps from the 'tick' messages, the page's onmessage wrapped) is the one that holds. (checked 2026-11-09) [verified 2026-11-10: stale, measurement method note, no open item; graphjitter.js is not in the repo]
- Nav history on a phone: the popup was measured by calling `openNavHistoryMenu` directly (the status-bar button is not drawn at 390), so its placement on a phone was not verified, only its widths and 44px targets. (checked 2026-11-09) [verified 2026-11-10: true, phone placement of openNavHistoryMenu not verified; not re-driven]

## Left by the 0.3.3 agents (INBOX 426), 2026-09-26

The four agent files of that round (`companion-426.md`, `atlas-fable.md`,
`ui-426.md`, `auth-optional.md`) are in `archive/agent-remaining/`; what
they left that is still true on the 0.3.3 head is here, one line each. The
two decisions only the owner can take are INBOX 427.

- **Boot gzip budget, what the 2026-10-05 split did not take** (792,754 to
  758,418 bytes, notes-list.js 63,548 to 57,929; `test_static_compression.py`
  has the numbers). Candidates measured and left, each with its catch:
  the chord guide in settings-wiring.js (`showTabJumpHint`, `chordGuideEl`,
  `chordGuideGroup`, about 3 KB gzipped; a stand-in makes the guide appear a
  moment after the first `m`, so the real function would need a "still armed"
  check or the second key can leave it stuck on screen); the SearXNG host
  block in settings-wiring.js (about 3 KB; its caller
  is `renderWebSearch`, a Settings render, so it wants `await ensureModule` there); the Ask
  rendering in capture-ask.js (`askQuestion`, `renderChatMeta`,
  `renderAnswerGrounding`, `placeAnswerFigures`; about 10 KB but read by the
  Ask tab's own submit path, so it is a design judgement, not a move); the
  edit form in notes-list.js (`renderEditForm`, 4.5 KB: `renderEntries` calls
  it synchronously and reads the card it fills, so it needs `openNoteEditor`
  to load the file first and every other way into `editingId` checked).
  [split1005] (checked 2026-11-09) [verified 2026-11-10: true, boot gzip candidates listed as left; test_static_compression.py holds the numbers]
- **`tests/test_name_mood.py` asserts `oklch(from var(--accent)` in the
  CSS**: it holds (the accent tints the glow), but a test for the fixed
  palette would be the honest one. [atlas-fable]
  *Needs: a test for the fixed palette needs the palette's values decided first.* (checked 2026-11-09) [verified 2026-11-10: true, tests/test_name_mood.py still asserts oklch(from var(--accent)); fixed-palette test not built]
- **Atlas round 5, the owner's asks (INBOX 427 (1); 2026-09-27)**: hands
  and feet drawn as part of each limb's outline (a mitten with a thumb on
  the inner side, a turned-out foot with a heel; `atlasStem`'s `tip`), the
  legs a third of the height on a shorter torso (hips at 58, soles at 90,
  from a fifth showing before), the hair drawn full on both looks (the
  feminine: seven wavy locks fanning from the crown over a soft mass, one
  falling forward to the shoulder; the crest a quarter fuller), the
  feminine lower body two ribbons (a wide sash from the left hip, a
  narrower one from the right) in the swaying layer, the Auto look reading
  Your look when Face looks is Neutral (`atlasLookReason`), and the lab's
  Morning review card (both looks, every expression, every pose, every
  size, with what Auto would draw and why). Proofs
  `scratchpad/shots/atlas-r5/`. Left: the hands' fingers are two soft
  swells, not drawn fingers (the sprite's are mittens, so by choice); the
  feminine hair now reaches x 78 and y -9, past the companion's 64px box
  by the tail's margin; the ring drift and per-glint twinkles stay off at
  companion size; the simulator's stand-in menu says nothing about where
  app.js's menu lands; three CSP "inline style" console warnings on the
  lab come from a style attribute in avatars.js's generated faces; the
  organic body, ribbon tail, strand and heart star await the owner's read
  of the review card. A mood's body move (hop, giggle, doze, sway, ponder)
  runs on the figure box and the Zs and hearts on two roots of their own,
  so at rest in any mood the figure is 0 layouts and 0 paints
  (companionperf.js, atlaswalk.js, 2026-09-27); what still animates inside
  a layer's svg is a mood's small effects (the sparkles of delighted and
  proud, the thinking dots and node pulses, the sad drops, the confused
  wobble), which the companion's pacer steps at 20 Hz for as long as that
  mood lasts, 20 layouts a second. The hook that would end it is the
  pacer's own (avatars.js `nameMarkBuddyTempo`): skip animations whose
  target is inside an `.atl-layer` svg and let them run free (a repaint of
  one 64 by 92 layer, no layout), or pace them at 10 Hz. [atlas-fable]
  *Needs: what is left is drawing changes that await the owner's read of the review card.* (checked 2026-11-09) [verified 2026-11-10: true, atlasStem tip present in atlas.js; round-5 shot folder scratchpad/shots/atlas-r5 is gone]
- **The companion rides with `ScrollTimeline`** (Chromium 115+, so WebView2);
  WebKitGTK falls back to the script follow. Not driven in either desktop
  window. [companion-426]
  *Needs: a WebView2 or WebKitGTK window.* (checked 2026-11-09) [verified 2026-11-10: true, ScrollTimeline in avatars.js; WebView2 and WebKitGTK not driven]
- **Sign-in off, not driven**: the desktop window's persistent profile, a
  real second device on the LAN, the prompt card in dark, and whether a
  restored backup's `preferences.json` brings the setting back (a sweep
  can now boot such a data dir: `lib.js` `boot()` returns `signIn: 'app'`).
  [auth-optional]
  *Needs: the desktop window and a second device.* (checked 2026-11-09) [verified 2026-11-10: true, needs a real desktop profile and LAN device; boot signIn hook in lib.js]
- **The dashboard scroll jump (426 u)** was not reproduced by wheel, idle or
  any scroll call; if it recurs, `scrolljump.js` with the owner's
  preferences (`LS=`) and the companion on. [ui-426]
  *Needs: the owner's preferences (`LS=`) to reproduce.* (checked 2026-11-09) [verified 2026-11-10: true, not reproduced; needs owner's preferences; scrolljump.js reference holds]
- **uipolish-0924 leftovers**: the surface-by-surface pass (its item D);
  the icon-only floor is done and measured by `iconfloor.js`. The footer
  overlap `deadbtn.js` reported was the sweep's, settled 2026-09-26: no tab's
  scroller runs under the status bar (each ends at or above its top, at 1440
  and 390), and the three were controls half scrolled out of their own box,
  whose centre the point test found the bar under; the sweep now checks the
  centre against each scrolling ancestor first, 0 findings at 1440 and at 390
  (the graph's `#graph-fullscreen` case is closed, HISTORY.md, "OPEN.md rows
  closed, 2026-10-05 (the pre-0.4.0 buildable rows, sweeps on port 8815)").
  [ui-426]
  *Needs: a surface-by-surface design pass.* (checked 2026-11-09) [verified 2026-11-10: true, iconfloor.js and deadbtn.js present; surface-by-surface pass not done]
- **The README's OCR shot is the 0.3.2 capture, in dark**: `seed-ocr.js` (removed 2026-10-12, recoverable from git history)
  needs a Tesseract binary this sandbox does not have, so it was not retaken
  with the rest (`SKIP=ocr`). [docs-0.3.3]
  *Needs: a Tesseract binary.* (checked 2026-11-09) [verified 2026-11-10: true, seed-ocr.js removed 2026-10-12 (bullet's own note); README OCR shot not retaken]

## Graph

Left by the graph agent (Brief 38, merged 2026-10-10):

- `scratchpad/ui-sweeps/graphfslightbox.js` reads `.lightbox` in the tick it calls the lazy `openLightbox`; the sweep needs an await. (checked 2026-11-09) [verified 2026-11-10: true, scratchpad/ui-sweeps/graphfslightbox.js exists; await not added]
- Topics becoming categories is Brief 39b's (GRAPH_PLAN "Decision made, 2026-10-10"). (checked 2026-11-09) [verified 2026-11-10: true, pointer to Brief 39b in GRAPH_PLAN; work still open there]

## Chat and popup agent

- **The citation mark's touch box overlaps the lines above and below** (a
  decision to note, not a bug): the `::after` box is 44px tall around a
  13px glyph, so on a phone a tap within 14px above or below a mark opens
  the peek rather than acting on that line's text. By design (6df7310);
  worth a look on an answer dense with marks.
  *Left: by design (6df7310); look only if an answer dense with marks is reported.* (checked 2026-11-09) [verified 2026-11-10: true, by design per 6df7310, but the phone tap overlap is an open look]
- **Ask's answer object was measured on the offline branch only.** The sweep
  runs against a server with no model, so `sentences` was empty in every
  measurement and the grounding chips and inline marks under an Ask answer
  were not re-measured. Next step: anyone with a local model runs
  `chatphase3.js` again and adds a line for the sentence count and the mark
  count. [chat-timeline-skills.md]
  *Needs: a local model.* (checked 2026-11-09) [verified 2026-11-10: true, needs a local model; chatphase3.js is absent so the re-run is open]
- **`chatSourcesPanel` is shared, the renderer is not.** Judged not worth it
  in 2026-09-13: the three surfaces have genuinely different frames around the
  same three shared components. Next step if a fourth surface appears: move
  the Chat bubble's foot onto `renderAskAnswerFoot` (renamed) and delete the
  palette's own `cmdPaletteResultRow`. [chat-timeline-skills.md]
  *Left: a decision, revisit if a fourth surface appears.* (checked 2026-11-09) [verified 2026-11-10: stale, decision not to share renderer, judged not worth it in 2026-09-13]
- **SKILLS Phase D: no model ran any of it.** The fake transport answers every
  step, so "a rewritten step fixes a run a 3B model stalled on" is the claim
  the mechanism is for and not one the tests make. The chat control (Edit step
  N, beside Resume) is asserted statically against `app.js` because reaching
  it needs a run that stops, which needs a model. [chat-timeline-skills.md]
  *Needs: a model (`scratchpad/llama-dev.sh`; `tests/test_skills_evals.py` holds four evals).* (checked 2026-11-09) [verified 2026-11-10: true, tests/test_skills_evals.py present; no small-model run (fake transport only)]
- **The `evals` marker and its fixture set (Brief 13's done-when).** At least
  80% of the built-in skills complete with zero invalid tool calls under
  small-model mode, and a loose-ends fixture of 70 notes with eight planted
  loose ends, all eight found. Deliberately not built against the fake
  transport: a fake calls whatever its script says. File: a new
  `tests/test_skill_evals.py`, marker `evals` registered in `pyproject.toml`
  and the module skipped unless the dev model is reachable. Next step:
  WORLD_CLASS_PLAN 9's runner first. [brief-13-harness.md]
  *Partly built since: the marker and four evals exist (`tests/test_skills_evals.py`); the 80% built-in-skills run and the 70-note loose-ends fixture still need a model.* (checked 2026-11-09) [verified 2026-11-10: true, tests/test_skill_evals.py present; 80% and 70-note fixture not built]
- **The follow-up chips were stubbed at the route in the sweep**, because
  `/chat/followups` answers `[]` with no model. What is measured is the
  request a chip causes, not the model's choice of question. Worth knowing
  before reading the sweep as proof of the whole feature.
  [chat-timeline-skills.md]
  *Left: a caveat about the sweep, not a bug; the chips' model choice needs a model.* (checked 2026-11-09) [verified 2026-11-10: true, /chat/followups returns [] with no model in tests; caveat stands]

## Whiteboard and mind map

- **The View menu is 714px of content on a map.** Under about a 730px-tall
  window it still scrolls, which is correct and may still read as the report.
  If it comes back the fix is the menu's own length (four groups, sixteen
  rows), not its placement, which is measured and right from 500 to 1000px
  tall. [visual-c.md]
  *Opus: the menu's own length is a design call.* (checked 2026-11-09) [verified 2026-11-10: true, 714px menu on a map; scroll behaviour is correct, length fix not made]
- **The mind map's own leftover list was re-checked item by item, 2026-09-20**
  (`archive/agent-remaining/mindmap.md`, "Left to do", rewritten with what a run
  against this head finds). Four of its six items were already done, two of
  them by decisions taken after the list was written: the dock's Layout
  section exists and MINDMAP_PLAN §12.5 decided a map shows no Insert or
  Arrange menu at all, both sweeps take `VIEWPORT`, `mapstrip.js` runs 39/39
  on `#wb-context`, `mapperspective.js` (removed 2026-10-12, recoverable from git history) measures every Colour by on a map of
  twenty notes 12/12 (category 5 colours, 4.59:1 to 9.13:1 against the card),
  and `wbrail.js` reads the rail against the bar recipe 6/6. Of what that
  re-check found actually left, ~~**curve control points on a tree edge**~~ and
  ~~**an image in a node**~~ were built 2026-09-21 (MINDMAP_PLAN §12.1 items 2
  and 5, moved whole to HISTORY.md, "Moved from the plans, 2026-09-21";
  `scratchpad/ui-sweeps/mindmapcurve.js` 14/14 and `mindmapimage.js` (removed 2026-10-12, recoverable from git history) 12/12, light and dark,
  both now in `scripts/gate.sh`'s sweep list). What is left of that list is the
  AI half, which no sandbox here can exercise.
  *Blocked here: the AI half needs a model.* (checked 2026-11-09) [verified 2026-11-10: true, two of the mind map's leftover items still open; archive/agent-remaining/mindmap.md]
- **The whiteboard's own View menu (`.wb-board-menu`) was never reproduced as
  broken.** It has its own max-height-on-open logic (`whiteboard.js`, the
  `wb-board-menu-wrap` toggle listener), unrelated to the `details.dock-menu`
  family INBOX 31's fix targeted. Worth a Chromium check in its own right if
  it is still reported. [batch-a.md]
  *Left: measure in Chromium only if it is reported again.* (checked 2026-11-09) [verified 2026-11-10: true, wb-board-menu-wrap toggle in whiteboard.js; never reproduced, Chromium check still open]

### Left by the boardmap agent (the owner's 2026-10-10 list, merged 2026-10-10)

- INBOX 739's documents half: boards and maps name themselves (`wbUntitledNames`, `whiteboard-templates.js`); "Untitled document N" is not built (`documents.js`, Brief 42). 739 stays in INBOX until then. (checked 2026-11-09) [verified 2026-11-10: true, documents.js has no 'Untitled document N' naming; boards name themselves in whiteboard.js]
- Document comments do not yet share the board's thread (Reply, Edit, Resolve, Attach); `whiteboard.js` `wbCommentRow` is the shape to reuse (Brief 42). (checked 2026-11-09) [verified 2026-11-10: true, whiteboard.js wbCommentRow exists; document comments do not use it]
- A topic's effect (shadow, glow) and a Phosphor icon do not reach the PNG or SVG picture (`wbBuildExportSvg`, the map-node branch); shapes do. (checked 2026-11-09) [verified 2026-11-10: true, wbBuildExportSvg present in whiteboard-interchange.js; topic effects not in picture export]
- The frame-preview clip was reproduced only as the selection canvas lagging a container that grew mid-drag (fixed); the owner's exact trigger is not known. (checked 2026-11-09) [verified 2026-11-10: fixed, frame-preview clip fix noted as fixed; the owner's trigger is still unknown]
- "spacing is really close ... bunched up" on insert: gaps measured 26px before and after on both layouts; only the branch's jump to the end was found and fixed. A screenshot if it recurs. (checked 2026-11-09) [verified 2026-11-10: fixed, jump found and fixed per the bullet; gaps measured at 26px on both layouts]
- WHITEBOARD_PLAN "Placed from INBOX, 2026-10-07 (next PR)": 740's frame hint has no edit path and its connector arrow-head set (none, open, triangle, circle, diamond, bar) is not built; 747's "Reset style" for a board object is not built. (checked 2026-11-09) [verified 2026-11-10: true, 740 frame-hint edit path and 747 Reset style not built (whiteboard surfaces)]
- Pre-existing sweep failures on the base scripts: `mapcore.js` (removed 2026-10-12, recoverable from git history) 14/16 (a core node's spine and size), `mindmap.js` three FAILs (the Mind map segment's active mark, "an ordinary board shows no map chrome", the P5 template tile click timing out), `mapstyle.js` (removed 2026-10-12, recoverable from git history) "Aa grip overlaps the actions". (checked 2026-11-09) [verified 2026-11-10: true, mindmap.js sweep still present; mapcore.js and mapstyle.js removed, FAILs not re-run]
- `errors.js` at 390 stops on its own second login check (`#lock-password` reads visible after the unlock); 1440, 1024 and 820 report 0 errors. (checked 2026-11-09) [verified 2026-11-10: true, errors.js present; second login check at 390 not changed]

## Library

- **An uploaded document cannot be given a reading from outside the app.**
  `POST /media/{id}/ocr` and `/media/{id}/vision-ocr` both answer 415 for a
  PDF, because `ocr.OCR_SUFFIXES` and `vision_ocr.VISION_OCR_SUFFIXES` are the
  six image types, so every seeded PDF's fold says "nothing has read this yet"
  and no sweep can measure the Files fold with a reading behind it. A document's
  reading lives in `PageRead` rows instead (`/media/{id}/ocr-page-read`, which
  needs a model). Not a bug on its own; it is the reason the Files fold's filled
  state is still unmeasured. [readings.md]
  *Needs: a local model (`/media/{id}/ocr-page-read`) to fill a PDF's reading; not a bug, and the only route to the Files fold's filled state.* (checked 2026-11-09) [verified 2026-11-10: true, vision_ocr.py:98 VISION_OCR_SUFFIXES is images only; PDF still 415]

## App wide: shell, phone and the shared recipes

- **Atlas's `hide` act shows shut eyes and nothing of its hands.** The
  companion's new act (a private note opened) raises both arms over the
  face; Atlas draws its arms under its head in the body layer, so at the
  act's middle both arms sit inside the head's box (armL 1227..1244 x
  77..98 against the head's 1209..1266 x 46..95, `hidecheck.js`) and are
  not seen. Its eyes shut with the lids layer over the act's middle (the
  generic `.nm-eyes` squash flattened them to a 1.3px line 21px above their
  place, transform-box view-box; fixed 2026-09-26, `atl-lids-hide`). Paws
  over the face would need the arms drawn in the front layer for this act,
  a drawing change for the owner's call (atlas-r6-hide-mid.png).
  *Needs: a drawing change for the owner's call.* (checked 2026-11-09) [verified 2026-11-10: true, hide act's arms still not in the body layer; hidecheck.js absent, not re-driven]
- **`.sidebar-head` is off the dock grammar, deliberately.** It carries
  `min-height: var(--sidebar-toggle-size)`, a negative `margin-top` that meets
  the absolutely positioned collapse toggle, and `padding-right` reserving
  that toggle's lane; two of the three exist because of reports. If a future
  session wants them on the grammar the only safe route is all three at once
  (`frontend/index.html`: `#chat-sidebar` ~1134, `#sidebar` ~523, the
  documents sidebar ~2172; `frontend/css/05-sidebars-themes.css` line 17),
  with `.dock` gaining the three properties behind a `.dock.is-sidebar`
  modifier and `heads.js` run before and after. [docks.md]
  *Left: deliberate; all three properties or none.* (checked 2026-11-09) [verified 2026-11-10: stale, deliberate off-grammar choice per the bullet; not an open defect]
- **Band 3 (600 to 820): the header is two rows, 128px at 819.** The band's
  recorded design (the strip cannot fit beside the wordmark at any width in
  the band, and the wordmark is what was reported twice when it was hidden),
  so it is known rather than open. [ui-phase-11.md]
  *Left: known and recorded design.* (checked 2026-11-09) [verified 2026-11-10: stale, recorded design decision at 600 to 820; not an open defect]
- **The Dashboard hero is deferred by the owner, not by judgement.** Do not
  touch `.dash-hero`, `.dash-wordmark`, `.dash-greeting`, `.dash-clock*` in
  `frontend/css/03-dashboard-widgets.css`, the hero markup in
  `frontend/index.html` (`#dash-hero`, around line 489), or `dashboard.js`'s
  `renderEmblem($("dash-hero-emblem"), ...)` call. [docks.md]
  *Left: the owner's call, do not touch.* (checked 2026-11-09) [verified 2026-11-10: true, owner deferral of the dashboard hero still stands in 03-dashboard-widgets.css]
- **Two icon-gap outliers, both judged deliberate**: 10 meta chips at 3.6px
  (`.chip.when`, `.map-chip`) against the app's 242 controls at 6.4px, and
  `#conv-browse-all` at 17.7px at 1024 only (it is `width: 100%` with
  `justify-content: center`). Revisit only if the owner reads them as
  inconsistent. [consistency.md]
  *Left: judged deliberate.* (checked 2026-11-09) [verified 2026-11-10: stale, judged deliberate in the bullet; not an open defect]
- **`#chat-results`'s second half is the only `.panel-head` with no actions.**
  The next head that wants a control beside its title should take family 8
  rather than inventing a fourth arrangement, which is what the lint is there
  to insist on. [ask-head-ocr.md]
  *Left: a rule for the next head that wants a control.* (checked 2026-11-09) [verified 2026-11-10: true, #chat-results panel-head still has no actions; no family-8 control added]

## Left by the typos90b agent (Brief 90 follow-up, 80 owner typos understood, merged 2026-10-11)

File: `docs/roadmap/archive/agent-remaining/typos90b-1011.md`.

- Not engine-readable, left out of the fixture: "corder" (corner; a one-letter swap in a six-letter word is refused on purpose, it reads "coder"), "nire" (more), "meen", "enout", "thingt", "ohf", "unig". (checked 2026-11-09) [verified 2026-11-10: stale, intentional fixture exclusion, not a defect]
- The Guide's no-model system answer still prints no "I took that to mean". (also: Left by the typos90 agent (Brief 90, the owner's typos as composer fixtures, merged 2026-10-11)) (checked 2026-11-09) [verified 2026-11-10: fixed, composer_ack.py:20 prints 'I took that to mean' on the no-model path]

## Left by the e2efix2 agent (CI E2E: draft recovery after a killed server, the documents count race, merged 2026-10-11)

File: `docs/roadmap/archive/agent-remaining/e2efix2-1011.md`.

- The budgets spec flaps in CI (a different budget each run: list, search, board, first_interaction) while it shares the runner with the other specs; HEAD measured no slower than the last green E2E (list 150 vs 198 ms best of five). Recommendation: run `budgets.spec.js` alone in a second Playwright invocation in the CI job; no cap raised. (checked 2026-11-09) [verified 2026-11-10: true, tests budgets.spec.js present; flake not addressed]

## Left by the search86 agent (Brief 86, search suggestions, Clear and forget, Recent changes, merged 2026-10-11)

File: `docs/roadmap/archive/agent-remaining/search86-1011.md`.

- The Library's documents, boards, images, bookmarks, recordings and skills boxes suggest recents only, not their own titles. (checked 2026-11-09) [verified 2026-11-10: true, Library boxes still suggest recents only; not built]
- "Clear dismissed suggestions" does not reach per-note "Not suggested" tags; changes are noted only while Settings is open (the top-bar theme button is not in Recent changes); a look change's Undo toast lands about 1.5 s late. (checked 2026-11-09) [verified 2026-11-10: true, per-note Not suggested tags and Undo timing still noted as open]
- App scripts at 320,589 of 320,600 gzipped (11 bytes); seven `typeof` guards removed on eager functions, each path not driven by hand. (checked 2026-11-09) [verified 2026-11-10: true, bundle at 320,589 of 320,600 per the bullet; typeof guards not driven]

## Left by the typos90 agent (Brief 90, the owner's typos as composer fixtures, merged 2026-10-11)

File: `docs/roadmap/archive/agent-remaining/typos90-1011.md`.

- A real word missing from both word lists can be mis-repaired; add it to `common_words.py` and `LEFT_ALONE`. (checked 2026-11-09) [verified 2026-11-10: true, src/tessellate/ai/common_words.py present; LEFT_ALONE in tests/test_owner_typos.py]
- The asking-word nearest rule turns an all-caps token ("NASA") into "has" unless the whole text is capitals. (checked 2026-11-09) [verified 2026-11-10: true, all-caps NASA rule not changed]
- Readings guessed: "liks" (like), "mut" (must), "odf" (of), "ro" (or). Brief 90 is standing: each new prompt's typos join `owner_typos.json`. (checked 2026-11-09) [verified 2026-11-10: true, guessed readings still listed; owner_typos.json present]

## Left by the transparency agent (one ledger, the running panel, backups, where your data went, merged 2026-10-11)

File: `docs/roadmap/archive/agent-remaining/transparency-1011.md`.

- No lint makes a new outbound call site name its purpose (`egress.purpose`, nine sites do). (checked 2026-11-09) [verified 2026-11-10: true, egress.purpose used at 2 files only; no lint for new call sites]
- The Guide, drafting and document review get a ledger run but no narrated lines; chat and agent turns are never announced. (checked 2026-11-09) [verified 2026-11-10: true, narrated lines not added for Guide, drafting or review]
- Measured on synthetic rows and one real destination; the status ring under "auto" motion not measured. (checked 2026-11-09) [verified 2026-11-10: true, status ring under auto motion not measured]

## Left by the grammar57 agent (Brief 57, the stylesheet's grammar, merged 2026-10-11)

File: `docs/roadmap/archive/agent-remaining/grammar57-1011.md`.

- Decisions 12 (layers, 115 literals), 13 (19 drop shadows), 16 (128 `!important`) are ratchets only; 13.R not started. (checked 2026-11-09) [verified 2026-11-10: true, ratchets only; 13.R not started]
- Row actions (`rowActions`) not yet in meetings, the suggestions inbox, the tag manager; "Kinds: all" triggers and the chat strip's pill toggles a different family. (checked 2026-11-09) [verified 2026-11-10: true, rowActions name in meetings.js; coverage in the inbox and tag manager not confirmed]
- Logs More menu `.dock-menu-check` rows 34.9px/8px against 32px/12.8px items; the board's Start and End menus not measured for end gaps. (checked 2026-11-09) [verified 2026-11-10: true, menu gap measurements not taken]
- The Windows grammar worker failure not reproduced (now names its reason). (checked 2026-11-09) [verified 2026-11-10: fixed, grammar worker now names its reason per the bullet]

## Left by the mapfix agent (the topic's tools and the board's frames, merged 2026-10-11)

File: `docs/roadmap/archive/agent-remaining/mapfix-1011.md`.

- INBOX 819 (2): a label's look controls (size, bold, colour, chip, position); owner the cards agent. (checked 2026-11-09) [verified 2026-11-10: true, label look controls (INBOX 819 item 2) not built]
- At 25% zoom the 20px + overlaps its parent by about 5px; radial and tree-down layouts not driven. (checked 2026-11-09) [verified 2026-11-10: true, 25% zoom overlap and radial/tree-down layouts not driven]
- `.wb-resize-handle` title still says "double-click fits the text" on non-frame objects; a dead `.wb-map-actions` coarse-pointer rule pinned by `test_map_actions_clear_of_label.py`. (checked 2026-11-09) [verified 2026-11-10: true, wb-map-actions still in library-lazy.css; resize handle title unchanged]

## Left by the ownerfix agent (the owner's UI items, merged 2026-10-11)

File: `docs/roadmap/archive/agent-remaining/ownerfix-1011.md`.

- INBOX 803 item 4 (the OCR workspace's empty squashed box): not reproduced in five states; needs the owner's screenshot or state. (checked 2026-11-09) [verified 2026-11-10: true, needs the owner's screenshot or state]
- The capture box still moves 2.4px down and 1.6px left on the first click (strip 40 to 42.4px; CodeMirror line padding). (checked 2026-11-09) [verified 2026-11-10: true, capture box offset is a measured open item]
- Constellation yellow stars are about 2.1:1 in light; the Notes rows/cards toggle is 28x24. (checked 2026-11-09) [verified 2026-11-10: true, contrast and 28x24 toggle are measured open items]

## Left by the uisweep agent (the 2026-10-11 sweep and learnability, merged 2026-10-11)

File: `docs/roadmap/archive/agent-remaining/uisweep-1011.md`.

- Mechanical: the header's six buttons lose 0.5px of their ring at the window top; the Library active sub-tab's border is cut 2.3px at 390; the chat composer's ring is cut 3px each side at 390. (checked 2026-11-09) [verified 2026-11-10: true, mechanical ring clipping open per the bullet]
- Design, for Briefs 57 to 59: the Notes dock has 10 items; Tidy's "40" is a pill badge; 177 controls sit off the 28/32/44 height steps (a 36px family among them); the timeline scrubber reads as a glitch; the Dashboard boards-and-maps miniature overlaps its text; the board view menu's labels sit 26px off the rows' text column; Settings Help has 196 buttons. (checked 2026-11-09) [verified 2026-11-10: true, design list for Briefs 57 to 59 still open]
- Not driven: the code IDE, the OCR workspace, the phone More sheet, the lock screen, the board's tools and Present. (checked 2026-11-09) [verified 2026-11-10: true, surfaces not driven; open verification]

## Left by the noagent agent (Agent mode with no model, merged 2026-10-11)

File: `docs/roadmap/archive/agent-remaining/noagent-1011.md`.

- Not verified: a real Needle engine on leftover turns; a real chat model on a one-option ask_user. (checked 2026-11-09) [verified 2026-11-10: true, needs a real Needle engine and a real chat model]
- Open: a country with several time zones names one ("the time in Australia" says Sydney's). (checked 2026-11-09) [verified 2026-11-10: true, time-zone naming open; no code change seen]
- Open: a misspelled place ("westen australia") is not read. (checked 2026-11-09) [verified 2026-11-10: true, misspelled place not read; open]
- Open: the user's own bubble shows a trailing backslash as typed. (checked 2026-11-09) [verified 2026-11-10: true, trailing backslash in user bubble; open]

## Left by the canvasdepth2 agent (canvas depth round 2, merged 2026-10-11)

Full list: [archive/agent-remaining/canvasdepth2-1011.md](../archive/agent-remaining/canvasdepth2-1011.md).
- Not driven: dark theme for the hand-drawn look, tables, the Data tab and the current layer; a real touch double-tap into a table cell; an .xmind opened in XMind; a real multi-page draw.io file; callouts, labels and stamps in the map's PNG and SVG. (checked 2026-11-09) [verified 2026-11-10: true, undriven list; open]
- maplayouts.js "tree-left carries the branch bar" fails on base too (it measures the centre topic). (also: Left by the map78 agent (Brief 78, merged 2026-10-10)) (checked 2026-11-09) [verified 2026-11-10: true, maplayouts.js tree-left check fails on base per the bullet]
- Tables lack merged cells (OPEN 807, wbopen-1031: the `.drawio` export is built; `%name%` placeholders and layer order were already). (checked 2026-11-09) [verified 2026-11-10: true, merged table cells not in the drawio or table code; open]

## Left by the calendar55 agent (Brief 55, merged 2026-10-11)

Full list: [archive/agent-remaining/calendar55-1011.md](../archive/agent-remaining/calendar55-1011.md).
- Touch drag on a tablet, a day page dropped on another day, and a 1,000-note month are built but not driven. (checked 2026-11-09) [verified 2026-11-10: true, built but not driven; open verification]
- The feed's Last-year range filters by when a note was written, so a note about a day this month written over a year ago shows in the calendar and not the feed. (checked 2026-11-09) [verified 2026-11-10: true, Last-year range filter by written date; open per bullet]

## Left by the appsync agent (WORLD_CLASS 25f, merged 2026-10-11)

Full list: [archive/agent-remaining/appsync-1011.md](../archive/agent-remaining/appsync-1011.md).
- No live sync between two open windows; a change shows in the other after a reload. (checked 2026-11-09) [verified 2026-11-10: true, no live sync between windows; open]
- The first load after the upgrade has no `ui-synced` mark, so a stale second browser pushes its look to the notebook once. (checked 2026-11-09) [verified 2026-11-10: true, ui-synced mark logic in ai-tools.js:979-988; first-load case open]
- Not checked in the desktop webview profile or on a second machine. (checked 2026-11-09) [verified 2026-11-10: true, desktop webview and second machine not checked; open]

## Left by the skills54 agent (Brief 54, merged 2026-10-11)

Full list: [archive/agent-remaining/skills54-1011.md](../archive/agent-remaining/skills54-1011.md).
- No real model here: `skill_rates.json` ships empty, the small-class gate, time to first step and `DEFAULT_CALLS_PER_STEP` are unmeasured. (checked 2026-11-09) [verified 2026-11-10: true, skill_rates.json ships empty; DEFAULT_CALLS_PER_STEP in budget.py; no real-model measure]
- A held-back skill is still runnable through the agent's `run_skill` tool; the label is only in the picker and Settings. (checked 2026-11-09) [verified 2026-11-10: true, run_skill present in agent_turn.py; held-back skills still runnable]
- The run's budget usage is on the result event but not drawn in chat-agent.js's result box. (checked 2026-11-09) [verified 2026-11-10: true, result-event budget not drawn in chat-agent.js; open]

## Left by the settings52 agent (Brief 52, merged 2026-10-11)

Detail: [settings52-1011.md](../archive/agent-remaining/settings52-1011.md).

- The 14 browser-only appearance settings do not follow you to a second browser: decided (WORLD_CLASS 25f, placed 2026-10-11): mirror them all except `perf`. (checked 2026-11-09) [verified 2026-11-10: true, mirror decision recorded; no sync of the 14 settings seen in code]
- Import replaces skills, personas and templates whole (no merge); the desktop save path for Export settings not driven. (checked 2026-11-09) [verified 2026-11-10: true, import still replaces whole; desktop save path not driven]
- The bin row's long label wraps when its reset appears; theme, palette, accent and zoom keep their own resets (no per-row marker). (checked 2026-11-09) [verified 2026-11-10: true, bin row reset wrap not changed; open]

## Left by the firstrun49 agent (Brief 49, merged 2026-10-11)

Detail: [firstrun49-1011.md](../archive/agent-remaining/firstrun49-1011.md).

- smallButton (app.js) names every worded button by its tooltip (WCAG 2.5.3); only the first-steps buttons are fixed. (checked 2026-11-09) [verified 2026-11-10: true, smallButton names by tooltip (app.js:1102 comment); only first-steps fixed]
- Most used in the sidebar keeps a binned note for up to 30 s (status.js cacheMs). (checked 2026-11-09) [verified 2026-11-10: true, status.js cacheMs 30000 still in place]
- The first-run queue (welcome, recovery key, updates) costs 3 acts before the dashboard. (checked 2026-11-09) [verified 2026-11-10: true, first-run queue of 3 acts still in place per bullet; open]
- Not verified: printed manual output, real-model answers, iOS zoom on the 13.6px name field. (checked 2026-11-09) [verified 2026-11-10: true, not verified; needs printed output and a real model]

## Left by the followups agent (merged 2026-10-11)

Detail: [followups-1011.md](../archive/agent-remaining/followups-1011.md).

- Free lines and arrows (not links) still draw the shaft through hollow ends: their stored path is re-read as the endpoints, so trimming would drift the line. (checked 2026-11-09) [verified 2026-11-10: true, free lines and arrows still re-read as endpoints; open]
- The reminder action token's key is per process (the app has no persisted signing secret): a restart ends open notifications' buttons. (checked 2026-11-09) [verified 2026-11-10: true, no persisted signing secret found for reminder action tokens]
- Still open from uipolish: the rows-view 28px meta button in a 24px line, the tool-confirm pair, lowering BOOT_CSS_CAP. (checked 2026-11-09) [verified 2026-11-10: true, rows-view meta button, tool-confirm pair and BOOT_CSS_CAP open]

## Left by the codedocs agent (INBOX 788, merged 2026-10-11)

Detail: [codedocs-1010.md](../archive/agent-remaining/codedocs-1010.md).

- Right-click and long-press on a snippet row do not open its menu (needs navigation.js ROW_MENU_HOSTS, a boot file, and TOTAL_CAP had 35 bytes). (checked 2026-11-09) [verified 2026-11-10: true, ROW_MENU_HOSTS in navigation.js; snippet row menu not wired]
- The code document's dock at 390 is 238px tall (four rows). (checked 2026-11-09) [verified 2026-11-10: true, code document dock 238px tall per bullet; open]
- Not verified: a real model or Needle answering the assistant's prompts; the tablet layout beyond one measure at 1024. (checked 2026-11-09) [verified 2026-11-10: true, not verified; needs a real model]

## Left by the meet81 agent (Brief 81, merged 2026-10-11)

Detail: [meet81-1010.md](../archive/agent-remaining/meet81-1010.md).

- The recorder saves plain transcript text into the meeting note; the timed lines live only on the recording. `/voice/transcribe-meeting` still returns text only. (checked 2026-11-09) [verified 2026-11-10: true, /voice/transcribe-meeting still text only; timed lines on recording only]
- Speaker names cannot be edited; the decision and action rules read English cue words only. (checked 2026-11-09) [verified 2026-11-10: true, speaker names not editable; English cue words only]
- Not verified: real Whisper segments, a real model's rewording and speaker naming, "Name the speakers" driven in the page. (checked 2026-11-09) [verified 2026-11-10: true, not verified; needs a real Whisper run]

## Left by the notify86 agent (Brief 86, merged 2026-10-11)

Detail: [notify86-1010.md](../archive/agent-remaining/notify86-1010.md).

- Windows and macOS not run: both need a check by hand. On Windows a toast pressed in the Action Center after 600 s does nothing (needs a COM activator); on macOS osascript notifications have no buttons and a click opens Script Editor. (checked 2026-11-09) [verified 2026-11-10: true, Windows and macOS not run; needs a hand check]
- A tab hidden over five minutes can fire up to 60 s late (Chromium's timer throttling). (checked 2026-11-09) [verified 2026-11-10: true, Chromium timer throttling is a platform fact; open]

## Left by the filing agent (INBOX 781, merged 2026-10-11)

Detail: [filing-1010.md](../archive/agent-remaining/filing-1010.md).

- Not verified: the path with a real model running (its grounded tags first, then the engine's); dark theme. (checked 2026-11-09) [verified 2026-11-10: true, not verified with a real model; dark theme open]
- Suggesting tags from a note's own words for a notebook with no tags yet scored 4 of 12 and was not shipped. (checked 2026-11-09) [verified 2026-11-10: stale, experiment scored 4 of 12 and was not shipped; recorded rejection]

## Left by the canvasdepth agent (INBOX 797, merged 2026-10-11)

Detail: [canvasdepth-1010.md](../archive/agent-remaining/canvasdepth-1010.md).

- Mind map gaps open: a structure per branch, callouts, labels under a topic, .xmind export, stickers and votes. (checked 2026-11-09) [verified 2026-11-10: true, mind map gaps (callouts, labels, xmind export, stickers, votes) open]
- The Guide topics at the 1,920-character reply budget now are ask-chat 1,918, chat-controls and answers-from-notes 1,913, code-files 1,905, tidy 1,899 and graph-controls 1,896; the board topics were split in two earlier (whiteboard-controls 659 and whiteboard-selection 1,504, board-library 1,496 and board-library-saving 672). [room101-1011] (checked 2026-11-09) [verified 2026-11-10: true, Guide topic char budgets are measured figures; ask-chat present in help_topics_core.py]

## Left by the budgets53 agent (Brief 53, merged 2026-10-11)

Detail: [budgets53-1010.md](../archive/agent-remaining/budgets53-1010.md).

- Caps measured on a loaded machine sit close to the noise; re-measure idle and tighten (table, README and test move together). (checked 2026-11-09) [verified 2026-11-10: true, caps measured on a loaded machine; idle re-measure open]
- First interaction (about 4.4 s) is the slowest number; decision 54's 5,000-note list and search not re-measured; no Settings UI shows the budgets. (checked 2026-11-09) [verified 2026-11-10: true, first interaction 4.4 s not re-measured; no budget UI]

## Left by the graphfeel agent (INBOX 775, 792, 796, 798, merged 2026-10-11)

Detail: [graphfeel-1010.md](../archive/agent-remaining/graphfeel-1010.md).

- The owner's line was a saved Tree or Arc layout (synced, static by design). Recommendation: name the current layout on the map as one dock chip whenever it is not Force. (checked 2026-11-09) [verified 2026-11-10: true, recommendation to name the saved layout on the map; not built]
- Notes leaving the picture vanish instead of fading out. (checked 2026-11-09) [verified 2026-11-10: true, notes leaving the picture vanish; no fade seen]
- The close-other-menus fix covers the graph's three head buttons only; app-wide it needs about 98 bytes of app-scripts room. (checked 2026-11-09) [verified 2026-11-10: true, app-wide close-other-menus open; needs script room]
- Not verified: the owner's screen, Saved views, local and global switching, reduced motion in a browser. (checked 2026-11-09) [verified 2026-11-10: true, not verified; needs a browser and the owner's screen]

## Left by the uipolish agent (INBOX 776 to 786, merged 2026-10-11)

Detail: [uipolish-1010.md](../archive/agent-remaining/uipolish-1010.md).

- The skeleton shimmer still runs under the OS reduced-motion setting (data-progress-motion defaults to "always"). (checked 2026-11-09) [verified 2026-11-10: true, skeleton shimmer under reduced motion per bullet; open]
- `.dash-find` is the one glyph-only hover left; a rows-view meta icon button is 28px in a 24px line. (checked 2026-11-09) [verified 2026-11-10: true, .dash-find glyph-only hover still open]
- The Connections unlinked-mention Link button is still a bordered ghost button; the tool-confirm pair is untouched. (checked 2026-11-09) [verified 2026-11-10: true, Link button still ghost style; tool-confirm pair untouched]

## Left by the canvasui agent (INBOX 790 to 794, merged 2026-10-11)

Detail: [canvasui-1010.md](../archive/agent-remaining/canvasui-1010.md).

- Link-label blur not reproduced headless; the re-raster after zoom is untested on a GPU compositor or the desktop webview. (checked 2026-11-09) [verified 2026-11-10: true, link-label blur untested on GPU compositor; open]
- Mind map library schematics (wbMapThumbSpec) are monochrome, not tinted with branch colours; a hollow diamond draws the shaft through it. (checked 2026-11-09) [verified 2026-11-10: true, wbMapThumbSpec in whiteboard-library.js is monochrome; open]

## Left by the export48 agent (Brief 48, merged 2026-10-10)

Detail: [export48-1010.md](../archive/agent-remaining/export48-1010.md).

- A 5,000-note import takes 45.9 s: each note commits on its own. (checked 2026-11-09) [verified 2026-11-10: true, 5,000-note import 45.9 s per note commit; open]
- Binned notes import with their old deleted_at, so the startup purge removes expired ones at the next restart. (checked 2026-11-09) [verified 2026-11-10: true, binned notes keep deleted_at on import; open]
- Not verified (OPEN 812, wbopen-1031): private notes, several spaces and a browser upload of 5,000 files in the folder import. (checked 2026-11-09) [verified 2026-11-10: true, not verified (OPEN 812); needs a browser upload]
- The Background jobs Report button waits for boot room; the Activity panel at 390 is translucent. (checked 2026-11-09) [verified 2026-11-10: true, Report button boot-room wait and translucent Activity panel not changed; open]

## Left by the docsui agent (INBOX 788 design, merged 2026-10-10)

Detail: [docsui-1010.md](../archive/agent-remaining/docsui-1010.md).

- A code file's editor is capped at 78ch and centred (09-editor.css:59), so its panel is 724px at 1440. (checked 2026-11-09) [verified 2026-11-10: true, 78ch cap still in 09-editor.css per bullet; open]
- contentsRenameTopic (library.js) and the note-panel rename (graph.js) still save on blur. (checked 2026-11-09) [verified 2026-11-10: true, contentsRenameTopic and graph.js rename still save on blur; open]
- The sidebar's Comments, Linked from and Notes rows keep their old styling. (checked 2026-11-09) [verified 2026-11-10: true, sidebar rows keep old styling; open]

## Left by the composer agent (INBOX 787, merged 2026-10-10)

Detail: [composer-1010.md](../archive/agent-remaining/composer-1010.md).

- "What do I know about X" still quotes one sentence unless its notes are tagged with the subject (the 725 and 741 evals pin it). (checked 2026-11-09) [verified 2026-11-10: true, one-sentence quoting pinned by the 725 and 741 evals; open]
- Single-note answers still end with "[your note, date]"; some next-question chips repeat the subject; an overview over more than 24 notes should say "at least". (checked 2026-11-09) [verified 2026-11-10: true, '[your note, date]' ending and chip repeats still open]
- Not verified: a real embedder, the professional voice in a browser, 390px, the picture notice in a browser. (checked 2026-11-09) [verified 2026-11-10: true, not verified; needs a real embedder and browser]

## Left by the chat88 agent (Brief 88, merged 2026-10-10)

Detail: [chat88-1010.md](../archive/agent-remaining/chat88-1010.md).

- Send stays off the undo bar (Ctrl+Z in the composer is text undo); recommended as is. (checked 2026-11-09) [verified 2026-11-10: stale, recommended as is in the bullet; decision to keep, not a defect]
- Tab-level Guide topics ring the tab's main control, not each topic's own control. (checked 2026-11-09) [verified 2026-11-10: true, tab-level Guide topic ring behaviour still open]
- The "remind me" chat answer's text appears twice in the bubble's innerText (not checked whether drawn twice). (checked 2026-11-09) [verified 2026-11-10: true, innerText duplication not checked; open]
- The Atlas look row landed under the Settings sheet's head at 390 in one of four runs. (checked 2026-11-09) [verified 2026-11-10: true, Atlas look row placement at 390 in one run of four; open]
- Not verified: a Chat tap 700 ms after boot at 390 on an idle machine; the Highlight API in the macOS webview. (checked 2026-11-09) [verified 2026-11-10: true, not verified on an idle machine or in the macOS webview]

## Left by the bootdiet agent (merged 2026-10-10)

Detail: [bootdiet-1010.md](../archive/agent-remaining/bootdiet-1010.md).

- `TOTAL_CAP` (all app scripts) has 3,449 bytes of headroom since the bell's panel and the meeting recorder's buttons moved out of the 27 counted scripts (room101-1011); `BOOT_CSS_CAP` has 6,930. (checked 2026-11-09) [verified 2026-11-10: true, TOTAL_CAP and BOOT_CSS_CAP headroom figures in test_static_compression.py and test_boot_budget.py]
- A slow or failed fetch of app-features.js and a late Quick access first paint were not exercised. (checked 2026-11-09) [verified 2026-11-10: true, slow or failed app-features.js fetch not exercised]

## Left by the pickers agent (INBOX 784, 785, merged 2026-10-10)

Detail: [pickers-1010.md](../archive/agent-remaining/pickers-1010.md).

- Questions split at quote marks: INBOX 745 (b) decided a quoted prompt is not the person's own question, so the extractor rejects them; the fragments were old rows, now retired on read. Keeping quoted prompts as questions would reverse 745 (b): the owner's call. (checked 2026-11-09) [verified 2026-11-10: true, quoted-prompt rule (INBOX 745 b) still rejects quoted questions]
- The attached-image thumbnail path in the [[ preview (attachmentObjectUrl) was not driven, only inline images. (checked 2026-11-09) [verified 2026-11-10: true, attachmentObjectUrl thumbnail path not driven]

## Left by the agentgate agent (INBOX 778, merged 2026-10-10)

Detail: [agentgate-1010.md](../archive/agent-remaining/agentgate-1010.md).

- Needle with the server up but no model leaves Agent greyed: `tools_engine` is reported only when the server is down (routes_chat.py ~2534). (checked 2026-11-09) [verified 2026-11-10: true, tools_engine reported only when server down (routes_chat.py); Agent greyed]
- A failed or slow status poll nulls `modelStatus`, so Agent greys until the next good poll and may flicker. (checked 2026-11-09) [verified 2026-11-10: true, modelStatus nulls on a failed poll; open]
- Other AI controls still gate on `aiIsOff()`; `model_ready` is the field to move them to. (checked 2026-11-09) [verified 2026-11-10: true, aiIsOff gates still in meetings.js and sheets-selects.js; model_ready not adopted]
## Left by the audio80 agent (Brief 80, merged 2026-10-10)

Detail: [audio80-1010.md](../archive/agent-remaining/audio80-1010.md).

- Notes cannot link to or embed a recording yet (only `entry_id`). Search finds recordings now (libr-1011). (checked 2026-11-09) [verified 2026-11-10: true, notes still link only by entry_id (composer_voice and activity use it)]
- Trim decodes the whole file in the page (about 700 MB of samples for an hour); the sheet now says so from 20 minutes (libr-1011). A server-side cut needs a container writer. (checked 2026-11-09) [verified 2026-11-10: true, trim decodes whole file in page; server cut open]
- Brief 81: the stop path is now `meetingRecordingStopped`; transcription goes through `POST /recordings/{id}/transcribe`. (checked 2026-11-09) [verified 2026-11-10: stale, states the current stop path (meetingRecordingStopped, transcribe route); no open item]
- Not verified: real Whisper on a kept recording; a real microphone, Safari (mp4) and Firefox (ogg). (checked 2026-11-09) [verified 2026-11-10: true, not verified with real Whisper or browsers]

## Left by the translate83 agent (Brief 83, merged 2026-10-10)

Detail: [translate83-1010.md](../archive/agent-remaining/translate83-1010.md).

- Live translated captions: the dock's Translate button is built (libr-1011) against a fake translator; the real model through the dock is not driven (needs device). (checked 2026-11-09) [verified 2026-11-10: true, live translated captions not driven with a real model]
- Only English to Spanish: more pairs are a download block plus a PAIRS row, and the sheet then needs a pair picker. (checked 2026-11-09) [verified 2026-11-10: true, only English to Spanish; pair picker not built]
- The document menu's "Translate this passage..." still hands the passage to chat, not the offline engine. (checked 2026-11-09) [verified 2026-11-10: true, 'Translate this passage' still goes to chat]
- Not verified: under 1 s through the sheet on an unloaded machine; a real network install inside the app; WebView2 and Safari. (checked 2026-11-09) [verified 2026-11-10: true, timing and WebView2 and Safari checks not run]

## Left by the docs76 agent (Brief 76, merged 2026-10-10)

Detail: [docs76-1010.md](../archive/agent-remaining/docs76-1010.md).

- DOCUMENTS 24 row 7 (the list row's ⋮) not built: it would remake INBOX 722; keep the overlay. (checked 2026-11-09) [verified 2026-11-10: true, DOCUMENTS row 7 overlay not built]
- `confirmDialog` and `promptDialog` mount on `<body>`, so one asked from inside a modal opens beneath it; app.js is at its gzip ratchet. (checked 2026-11-09) [verified 2026-11-10: true, confirmDialog and promptDialog mount on body; app.js at ratchet]
- Replace in every document reads each document by one request; and it has no dock-menu row. (checked 2026-11-09) [verified 2026-11-10: true, Replace in every document still one request each; no dock-menu row]

## Left by the caption82 agent (Brief 82, merged 2026-10-10)

- The packaged helper: a Download pin per platform (URL, sha256, size) for whisper-server and a model in `core/extras.py` (`id="captions"`; the release asset list was unreadable from the sandbox), then a supervisor that starts it on 127.0.0.1 and sets the URL (`ai/captions.helper_url` reads only the environment today). Linux and macOS have no official binary confirmed. Until then Settings, Packages marks Live captions unavailable and only `MEMORYMAP_CAPTIONS_URL` works. (checked 2026-11-09) [verified 2026-11-10: true, captions helper pins not packaged; TESSELLATE_CAPTIONS_URL used in captions.py:85, extras id captions present]
- Real latency: `scratchpad/captions_audio.py` through a real whisper-server on the reference laptop (`pytest -m captions tests/test_captions_live.py`), then tune `STEP_MS`, `LENGTH_MS` and the `audio_ctx` margin (`ai/captions.py`). Measured here against the fake: median 1.03 to 1.12 s from word start at a 0.5 s stand-in, worst word 1.2 s quiet and 2.2 s under load; whisper.cpp tiny.en 0.51 s and base.en 1.85 s per 5 s window with the cut context on one thread (4 threads ran 25 times slower in this container). (checked 2026-11-09) [verified 2026-11-10: true, scratchpad/captions_audio.py present; live latency tuning not done]
- Accuracy under a cut `audio_ctx` was read on one sentence only. (checked 2026-11-09) [verified 2026-11-10: true, audio_ctx accuracy read on one sentence only]
- Stop saves a note until Brief 80's recording object lands; then `routes_captions._save` attaches the audio and makes the transcript its text; the Audio section (28.5 row 3) takes a status-bar tool for captions. (checked 2026-11-09) [verified 2026-11-10: true, routes_captions._save attaches audio only after Brief 80 object lands; open dependency]
- `ScriptProcessorNode` is deprecated; an AudioWorklet needs a blob: worker the CSP does not allow (`captions.js` `startLiveCaptions`). (checked 2026-11-09) [verified 2026-11-10: true, captions.js:235 still uses createScriptProcessor (deprecated)]
- Not verified: any real whisper-server or microphone, Firefox and Safari capture, Chromium's fake-mic start offset. (checked 2026-11-09) [verified 2026-11-10: true, not verified with a real whisper-server or microphone]

## Left by the agent87 agent (Brief 87, merged 2026-10-10)

- Not verified against a real model: whether it plans act-shaped steps `plan_writes` can preview and uses the narrowed tools a planned step is offered (`skill_runner._plan_step_offer`); rows 3 and 4 ran against the scripted fake only. (checked 2026-11-09) [verified 2026-11-10: true, plan_writes in skill_runner.py; _plan_step_offer name not found, real-model check open]
- Not verified in the browser: Chat's own path for the plan card and per-write undo (`chat-attach.js` onTool); an edit's diff under a step (pytest only). (checked 2026-11-09) [verified 2026-11-10: true, Chat plan card and per-write undo not driven in browser]
- The other tabs' starters (Notes, Chat, Graph, Library, Documents) are not in `ai/starter_acts.py`; with no model they get the composed answer (palette.js AGENT_TAB_STARTERS). (checked 2026-11-09) [verified 2026-11-10: true, other tabs' starters absent from ai/starter_acts.py]
- The reading does not take a note by its number ("pin note 12"): `commands._one_target`. (checked 2026-11-09) [verified 2026-11-10: true, commands.py:484 _one_target used for pin note 12; number not taken]
- deepen72a.js's shared overlap measure now ignores a clipped scrolling edge, so other surfaces' overlap counts may drop; undo.js was not run on the agent surface. (checked 2026-11-09) [verified 2026-11-10: true, deepen72a overlap measure change; undo.js not run on agent surface]

## Left by the time85 agent (Brief 85, merged 2026-10-10)

- Timeline row 8's bar, click to rows under 300 ms at 96 notes: 329 at load 6 to 8 (app side 73 to 164); a 57 to 70 ms task right after the rows paint; `content-visibility` on the day sections would cut it but the scrubber reads real heights (timeline.js `drawTimelineWindow`). The boot CSS budget is at its cap (183,300 gzipped, 0 bytes left after this merge: the recall row's rule moved into `.library-filters`): the next timeline or reminders CSS goes in a lazy file, or the timeline's stylesheet becomes one. (checked 2026-11-09) [verified 2026-11-10: true, timeline row 8 click latency at 96 notes; content-visibility not applied to day sections]
- Timeline at 390: the On this day row moves the list down 44 px; a phone may want it folded (`#timeline-recall`). (checked 2026-11-09) [verified 2026-11-10: true, On this day row shifts list 44px at 390; not folded]
- deepen72b.js's timeline row at 390 waits for `.timeline-rows` but the phone keeps the table view, so it times out (deepen72b.js:61). (checked 2026-11-09) [verified 2026-11-10: true, deepen72b.js waits for .timeline-rows and times out on phone table view]
- A `timeline-days` preference arriving after the click renders the timeline twice (once in nine runs at 5,000 notes). (checked 2026-11-09) [verified 2026-11-10: true, timeline-days preference race renders twice; open]
- timelinepaging.js: the strip-click check fails on the base too; its 100 ms frame check passed once and failed twice under load. (checked 2026-11-09) [verified 2026-11-10: true, timelinepaging.js strip-click check fails on base per the bullet; frame check flaky]
- Not verified: Firefox and Safari permission help, the webview's denied state, firing in a hidden tab (falls to the minute poll), a real non-UTC browser for the completion day maths, Move to an existing category, space or Publish drafts from the timeline bar. (checked 2026-11-09) [verified 2026-11-10: true, not verified; several browser and permission states open]

## Left by the palette90 agent (Brief 90, merged 2026-10-10)

- Not verified: the dictionary spelling offer in a live empty result; the server's own correction answered every typo tried, so `finderSpellingOffer` was driven directly (search.js). (checked 2026-11-09) [verified 2026-11-10: true, finderSpellingOffer in search.js driven directly only; live empty result unverified]
- Not verified: an act row against a running model; with no model it opens Chat with the act's opening words at 1440 and 390 and sends nothing (app-palette.js `paletteStartAct`). (checked 2026-11-09) [verified 2026-11-10: true, paletteStartAct in app-palette.js; act row with a running model not verified]
- A Settings row whose element is a label or head is focused as that element, not its control ("Accent colour" lands on its DIV at both widths): settings-find.js `openSettingRow`. (checked 2026-11-09) [verified 2026-11-10: true, openSettingRow in settings-find.js still focuses the label or head]
- The learned order is exact words only; Raycast also learns prefixes. Recommendation (take it): add the prefix with half weight once picks have a week of use (app-palette.js `paletteRanked`). (checked 2026-11-09) [verified 2026-11-10: true, paletteRanked learns exact words only; prefix recommendation not built]
- Acts with no stem start with the example's first word ("remind ", "note: "); a stem per act in `act_registry._ACTS` would read better but adds rows to the agent palette's Do group. (checked 2026-11-09) [verified 2026-11-10: true, act stems not set; act_registry._ACTS not found by that name, stem gap still described]
- errors.js at 390 stops at its login: a second fill and click (errors.js:86) race an unlock slower than its fixed 2.5 s wait; reproduced on the base commit. Recommendation (take it): wait for `#lock-password` to be hidden. (checked 2026-11-09) [verified 2026-11-10: true, errors.js login race at errors.js:86 per the bullet; wait recommendation not taken]

## Left by the map78 agent (Brief 78, merged 2026-10-10)

The remaining file is in `archive/agent-remaining/`; the rows below are what it left, one line each.

- Row 4 at 390: press to editable 140 to 159 ms against the 50 ms bar (1440 is 24 to 27). Each forced style pass in the add restyles about 830 elements at 390; dropping the root/body/tab-page `:has()` rules one group at a time did not change the count, so the cause is not isolated (`renderWbObjects` measure read, whiteboard.js ~19179, and `wbBeginTextEdit`'s contenteditable read, ~7859, are the two left). Measure on a quiet machine first: load was 4 to 8 on four cores. (checked 2026-11-09) [verified 2026-11-10: true, row 4 press latency 140 to 159 ms at 390; :has() rules not dropped]
- VC12 (Harper on node labels) not started: the budget went to rows 1 to 9. MINDMAP_PLAN "Vendored capabilities to use" still holds it. (checked 2026-11-09) [verified 2026-11-10: true, VC12 not started; MINDMAP_PLAN holds it]
- The More sheet on a map is 59 to 62 rows at 390 (the table plus the map palette); grouped by hairlines but long. A search field or the palette's own filter in the sheet would shorten the walk. (checked 2026-11-09) [verified 2026-11-10: true, More sheet 59 to 62 rows at 390; no filter added]
- The tree table, timeline and fishbone are column layouts that tidy the whole map on every add (`wbMapTidyBranchScope`); not timed at 200 topics. (checked 2026-11-09) [verified 2026-11-10: true, wbMapTidyBranchScope tidies whole map per add; not timed at 200 topics]
- The fishbone's rib runs behind its causes' boxes (lines are under nodes); the look is not compared against XMind's. (checked 2026-11-09) [verified 2026-11-10: true, fishbone rib runs behind causes; not compared with XMind]

## Left by the stats89 agent (Brief 89, merged 2026-10-10)

The remaining file is in `archive/agent-remaining/`; the rows below are what it left, one line each.

- Utilities row 5, "every utility has ... a `data-help-for` popover": the timer, stopwatch and Count words are palette rows with no surface of their own, so their in-place help is the row's `about` line and the Guide topic; a '?' needs a surface to sit on (a palette head '?' is a design call for Brief 90). `settings-panes.js` `paletteCommands`, the three rows. (checked 2026-11-09) [verified 2026-11-10: true, timer, stopwatch and Count words have no in-place help surface]
- Statistics row 3 (VC3, Brief 75): the page's two charts use the hand-built `askChartTicks`; tick labels did not collide at 1440 or 390 with this data (0 and 0), not checked at a 0 to 1,240 range. (checked 2026-11-09) [verified 2026-11-10: true, askChartTicks not checked at a 0 to 1,240 range]
- Statistics row 4 (Brief 37): the page's "not used lately" list (86 on the fixture) is the feed the weekly offer wants; not wired. (checked 2026-11-09) [verified 2026-11-10: true, not-used-lately feed not wired to the weekly offer]
- The week is Monday-first on `user_now`; a Sunday-first locale reads it a day out (`notebook_stats.week_start`). (checked 2026-11-09) [verified 2026-11-10: true, week_start Monday-first on user_now; Sunday-first locale open]
- Words written this week are the words in the notes made that week; edits to older notes are not counted (no per-edit word delta is stored). (checked 2026-11-09) [verified 2026-11-10: true, words-this-week counts only notes made that week; by design but open]
- `EntryLink` rows are counted whole: a link to a binned or private note is still a link on the page (`_notebook_block`). (checked 2026-11-09) [verified 2026-11-10: true, EntryLink counted whole in notebook_stats._notebook_block]

## Left by the debug70, shell71 and ocr79 agents (Briefs 70, 71 and 79, merged 2026-10-10)

The three remaining files are in `archive/agent-remaining/`; the rows below are what they left, one line each.

### debug70 (Brief 70, the debugger)

- D1's folder again: the brief says `frontend/js/run/debug-*.js`; the pass is `frontend/js/run-debug.js` for ide1's reason (65 lints glob `frontend/js/*.js`). Recommendation (take it): keep the prefix. (checked 2026-11-09) [verified 2026-11-10: stale, recommendation is to keep the frontend/js/run-debug.js prefix; the brief path is not used]
- Variables show one level (a repr, 200 characters): no expanding a list or an object into its children (VS Code's tree). `_mm_names` in `PY_RUNNER`, `show` in `_JS_DEBUG_WORKER` (api/run_sandbox.py:186). (checked 2026-11-09) [verified 2026-11-10: true, _mm_names and show keep one-level variables; no expanding tree]
- Watches and conditions in JavaScript are evaluated natively over the frame's values (`evaluate`, api/run_sandbox.py:250), not stepped: a watch that calls a function of the script runs a native copy of its value, not the interpreter's function; a watch never changes the script's state. (checked 2026-11-09) [verified 2026-11-10: true, watches evaluated natively in run_sandbox.py evaluate; open]
- JavaScript constructs not lowered for the stepper (classes, destructuring, spread and rest, for...of, default parameters, async and generators, `??`, `?.`, `**`): named with their line and refused (`RUN_DEBUG_REFUSED`, run-debug.js:18). A class lowering is the next most useful one. (checked 2026-11-09) [verified 2026-11-10: true, RUN_DEBUG_REFUSED in run-debug.js names unlowered constructs; list open]
- A file of tests (describe/it, unittest) debugs as a plain script, without the harness: the tests do not run under Debug. (checked 2026-11-09) [verified 2026-11-10: true, test files debug as plain scripts; open]
- Python breakpoints persist per document for the tab's life (`DOC_DEBUG.breaks`), not across a reload; VS Code keeps them in the workspace. (checked 2026-11-09) [verified 2026-11-10: true, DOC_DEBUG.breaks is per tab in documents-code.js; not persisted]
- Python's runtime still reloads per document opened (ide1's Left row; the frame lives in the panel); the first Debug on a cold runtime waits for it (about 5 s at 1440). (checked 2026-11-09) [verified 2026-11-10: true, runtime reload per document and cold-start wait open]
- F11 is shared: Step into while a session is on, Focus mode otherwise (documents.js); the palette row says "F11 while debugging". Brief 71's keybindings sheet should show the context. (checked 2026-11-09) [verified 2026-11-10: true, F11 shared between Step into and Focus mode; keybindings sheet open]
- The breakpoint lane is 0.875rem wide (1.5rem under a coarse pointer); touch.js does not measure gutters, so a tap's size on it is not checked. (checked 2026-11-09) [verified 2026-11-10: true, breakpoint lane 0.875rem; gutter tap size not measured]

### shell71 (Brief 71, the IDE shell)

- Debug (Brief 70) is a row of `DOC_PANEL_TABS` since the merge, its pane `docDebugView()`; Ctrl+Shift+D (the registry's newDocument, settings-wiring.js:919) is answered by the editor and stopped there, and has no row in `DOC_COMMANDS`, so the sheet does not list it. (checked 2026-11-09) [verified 2026-11-10: true, DOC_PANEL_TABS row; Ctrl+Shift+D still answered by the editor]
- "the problems panel fed by every linter": harper is a prose linter and prose documents have no panel (the panel is mounted for code files, `docCompletionExtras`); its findings stay in the editor's underlines and F8, not in a Problems tab. (checked 2026-11-09) [verified 2026-11-10: true, problems panel mounted for code files only; prose linter findings stay in underlines]
- "the JS parse errors sucrase reports": Problems shows the editor's own JS and TS parse errors (the Lezer tree check, the same lines); sucrase's own message appears only in Output when a run is prepared, not in Problems before a run. (checked 2026-11-09) [verified 2026-11-10: true, Problems shows Lezer tree errors, sucrase message only in Output]
- The console on an .html, .css, .svg or .sql file is JavaScript in a fresh worker, not the page's global: the page runs in a frame whose window the sandbox does not expose (run_sandbox.py `runHtml`). (checked 2026-11-09) [verified 2026-11-10: true, runHtml in sandbox_page.html; page console is a fresh worker]
- A console line that never ends (`while (true)`) is stopped after 10 s (60 s for Python's first line) by terminating the worker, which loses the run's namespace: the next line starts fresh. (checked 2026-11-09) [verified 2026-11-10: true, 10 s stop by terminating the worker loses namespace; open]
- The split's second half carries the language, theme, gutter and wrap of the first, not its completions, lint, snippets or the run panel (documents-ide.js `docIdeToggleSplit`). (checked 2026-11-09) [verified 2026-11-10: true, docIdeToggleSplit second half lacks completions, lint and run panel]
- Ctrl+K Ctrl+S opens the palette for a moment before the sheet (the app's Ctrl+K is kept in code files); VS Code waits for the second chord instead. (checked 2026-11-09) [verified 2026-11-10: true, Ctrl+K Ctrl+S opens the palette first; chord not waited for]

### ocr79 (Brief 79, OCR)

- Live Text on the continuous (scroll) layout of a PDF: only the single-page stage carries the layer. library.js `ocrBuildScrollPages`. (checked 2026-11-09) [verified 2026-11-10: true, ocrBuildScrollPages in library.js: Live Text only on single-page stage]
- An image's whole reading deleted from the lightbox or the gallery's row menu still clears without the bin (only the workspace's deletes were moved). library.js callers of `analyseMediaRow(..., { text: "" })` outside the workspace. (checked 2026-11-09) [verified 2026-11-10: true, lightbox and gallery whole-reading delete bypasses the bin; analyseMediaRow callers]
- Undoing a fresh read writes the old text back through the text route, so it keeps the new read's model name ("Read by X") rather than the old one's. library.js `ocrTextWriter`. (checked 2026-11-09) [verified 2026-11-10: true, ocrTextWriter undo keeps the new model name]
- `undo.js` (the trust sweep) does not walk the OCR workspace; `ocr79.js` measures it instead. (checked 2026-11-09) [verified 2026-11-10: true, undo.js does not walk the OCR workspace; ocr79.js measures it instead]

## Left by the atlas84 and companion2 agents (Briefs 84 and 34, merged 2026-10-10)

Atlas everywhere (Brief 84, CHAT_PLAN F5, the four steps built):

- "new ways to do and output info" (INBOX 758): the Ask box ignores the `chart` event (capture-ask.js Ask handlers, ~3065); only the Chat tab draws it (chat-attach.js `onChart`). (checked 2026-11-09) [verified 2026-11-10: true, capture-ask.js Ask handlers ignore the chart event; onChart only in chat-turn/answer-kit]
- "the other one" (decision 57) in Chat: `routes_chat._spoken_act` sends `objects` only when the client puts them on history turns; chat-attach.js does not yet send each answer's note titles. (checked 2026-11-09) [verified 2026-11-10: true, routes_chat._spoken_act not found by that name; objects not sent per turn; open]
- "more access" (INBOX 758): write tools that are not acts (create_category, rename_tag, delete_tag, merge_categories, board and map tools) are named by the reading but not run with no model; each needs an act row in `act_registry._ACTS` with an inverse. (checked 2026-11-09) [verified 2026-11-10: true, write tools that are not acts still lack act rows; act_registry._ACTS name not found]
- The Guide's "how do I set a reminder" first line is the topic's first matching sentence ("The Reminders tab groups items..."), not the step that sets one: `composer.help_line` picks by shared words (composer.py `help_line`). (checked 2026-11-09) [verified 2026-11-10: true, composer.help_line picks by shared words; wrong first line open]
- INBOX 731 (the Guide failing with a model): not touched; the model-path fallback in `help_chat.answer_stream` still needs the log line read. (checked 2026-11-09) [verified 2026-11-10: true, help_chat.answer_stream fallback log line not read]
- Guide rows 4 to 6 (CHAT_PLAN "The Guide" table): trust-surface topics, the weekly unused feature, typos through the word list (VC15). (checked 2026-11-09) [verified 2026-11-10: true, Guide rows 4 to 6 of CHAT_PLAN not built]

- Brief 84, not verified: the Guide's new first line and act topics in a browser (API and unit tests only); no real model. (checked 2026-11-09) [verified 2026-11-10: true, Brief 84 browser and real-model checks not run]

The companion (Brief 34, second round: faces at 28 and 20 px, the tail on the compositor, reduce motion, calm's arms; smoothness measured only):

- The rest of Atlas's idle cost is the companion's own behaviour, not the
  tail: with the tail and breath switched off, 670 recalcs and 130 layouts a
  minute remain (recalc probe), all from avatars.js timers. Decision 7's 1 ms
  needs the behaviour picker and perch checks profiled next. (checked 2026-11-09) [verified 2026-11-10: true, companion idle cost measured per the bullet; open]
- The chest's breath still writes the torso's `scale` 2.5 times a second at
  rest (atlas-life.js `atlasBreathFrame`): a recalc and a layout each. Zero
  needs the torso on its own layer root (a drawing change, `atlasDrawFigure`). (checked 2026-11-09) [verified 2026-11-10: true, atlasBreathFrame in atlas-life.js still writes torso scale]
- 104px faces (the welcome, the large view): 2 to 3 of 15 distinct in light by
  the same metric; the cue is drawn only at the head and tiny levels. The
  owner's "I barely get to see atlas change expression" may also mean the
  companion figure (12px face); a cue on the figure is the next step. (checked 2026-11-09) [verified 2026-11-10: true, 104px face distinctness measured; open]
- Step 5 not built: one curve table for every joint (120 to 400 ms), the
  idle pool's never-within-five rule and a reaction budget a minute beyond
  the existing 6s gap (avatars.js `NMB_REACT_GAP`). The one snap (both hands
  jumping over 4px out of stillness while hanging, atlasdepth2.js atlassmooth) is likely
  the held arms' crossfade (`atlasRigRead`, -158 degrees); one latency trial
  of five was over 100 ms, the frame wait under load. (checked 2026-11-09) [verified 2026-11-10: true, step 5 not built; NMB_REACT_GAP in avatars.js]
- Arm angle over a walk cycle not measured (atlasarms.js measures still
  poses; the walk swing is the rig's, atlas-motion.js `atlasRigFrame`). (checked 2026-11-09) [verified 2026-11-10: true, walk-cycle arm angle not measured; atlasRigFrame present]
- `#nm-buddy:has(.atl-figure) .nm-buddy-char` and the lower layer still slow
  to 6s under the hint (08-consistency.css, the block after the chin hand
  rule) rather than stopping: they may carry acts, so left for a driven check. (checked 2026-11-09) [verified 2026-11-10: true, nm-buddy slow-to-6s rule under the hint still in 08-consistency.css]
- Companion movement Full keeps the script loops (tail, rings) under Reduce
  by design (`atlasMotionOK`); the CSS loops stop under the hint regardless. (checked 2026-11-09) [verified 2026-11-10: stale, kept by design (atlasMotionOK); not a defect]

- Brief 34, not verified: the arm angle over a walk cycle; 104 px faces (2 to 3 of 15 distinct in light); no real WebView2 or WebKitGTK; all timings from a loaded machine. (checked 2026-11-09) [verified 2026-11-10: true, not verified on WebView2 or WebKitGTK]

## Left by the wb77 and ide1 agents (Briefs 77 and 69, merged 2026-10-10)

Whiteboard (Brief 77, rows 1 to 4 built; 8 and 9 not started):

- Row 8 (rule 6): "every rail and top-bar control has a `data-help-for` popover and a palette row; 0 missing". Not built. A first count from the DOM (`#wb-topbar`, `#wb-tools-panel`, `.wb-board-menu` controls against `WB_COMMANDS` by `data-wb-cmd`, `run.tool`, `run.clickId`) found 240 controls and 166 with no table row, but the board picker's rows and the View menu's switches inflate it; the measure needs the picker excluded and the switches counted once (whiteboard-commands.js `WB_COMMANDS`, index.html 6267 to 6560). (checked 2026-11-09) [verified 2026-11-10: true, data-help-for coverage for rail and top bar not built]
- Row 9 (rule 12): "a board AI act as one chat tool (summarise this board; a board from a note)". Not built: a tool under `src/memorymap/ai/tools/` with its test, README's tool count (`tests/test_readme_freshness.py`), deepen72a.js's "No model" row before and after. (checked 2026-11-09) [verified 2026-11-10: true, board AI chat tool not built; old src/memorymap path, package is src/tessellate]
- `errors.js` at 1440 and 390: 0 errors, 0 layout findings each. (checked 2026-11-09) [verified 2026-11-10: stale, reports 0 errors and 0 layout findings; no open item]

Code editor (Brief 69, I1 built):

- D1's folder: the brief and D1 say `frontend/js/run/`; the files are `frontend/js/run-*.js` because 65 lints (`test_frontend_symbols`, the em-dash and innerHTML lints, the global scope ratchet) glob `frontend/js/*.js` only. Recommendation (take it): keep the prefix; a folder needs every lint made recursive first. (checked 2026-11-09) [verified 2026-11-10: stale, folder decision resolved to run-*.js by the 65 lints]
- D5 "load this CSV document as a table": the sandbox's SQL worker takes `tables: [{name, columns, rows}]` (`_SQL_WORKER`), but no panel action picks a CSV document and sends it yet (`run-core.js`, the sql row). (checked 2026-11-09) [verified 2026-11-10: true, CSV to SQL table action not wired; _SQL_WORKER present]
- D9 stdlib completion and signature help from a generated table (`scripts/gen_python_completions.py` over the installed Pyodide's `inspect`): not started. (checked 2026-11-09) [verified 2026-11-10: true, scripts/gen_python_completions.py exists; table not generated]
- D9 `ruff-wasm` lint and format: DOCUMENTS 25 row 4's (Brief 42's linters), not started here. (checked 2026-11-09) [verified 2026-11-10: true, ruff-wasm lint not started]
- D6 `.md` preview in the sandbox frame: not done; a Markdown document already has its own Live and Split views. (checked 2026-11-09) [verified 2026-11-10: stale, decision not to add a .md sandbox preview; Markdown has Live and Split]
- Python's runtime reloads on every document opened (5.9 to 7.0 s cold at 1440): the sandbox frame lives in the panel, which is rebuilt per document (`docRunPanel`, documents-code.js). One frame kept across documents would make a second .py run warm. (checked 2026-11-09) [verified 2026-11-10: true, docRunPanel rebuilt per document; cold reload open]
- `input()` is answered before the run (the Input box), not interactively mid-run: that needs `SharedArrayBuffer` and the COOP/COEP headers, which are D2's (Brief 70). (checked 2026-11-09) [verified 2026-11-10: true, input() answered before run; needs SharedArrayBuffer headers]
- p5 in the sandbox logs "Permissions policy violation: accelerometer" to the console (p5's devicemotion listener in a frame without `allow`); harmless, not silenced. (checked 2026-11-09) [verified 2026-11-10: stale, harmless console message left as is by decision]
- A JSX `.js` document (the `jsx` alias) runs without the JSX pass; only `.tsx` paths get it (`runStripTypes`). (checked 2026-11-09) [verified 2026-11-10: true, runStripTypes runs for .tsx only; jsx alias not covered]

- Brief 69, not verified: the desktop webview; dark theme for the new panel rows; a large SQL result; touch.js on the other surfaces. (checked 2026-11-09) [verified 2026-11-10: true, Brief 69 desktop and dark theme checks not run]
- Brief 77, found: the shape flyout opens only from its 10 px caret or a long-press, too small for a finger on a phone; boot CSS is within 12 bytes gzipped of its budget. (checked 2026-11-09) [verified 2026-11-10: true, shape flyout caret too small for touch; open]

## Left by the design agent (Brief 56, merged 2026-10-10)

- 110 distinct controls show no change on keyboard focus (`a11yname.js`, 312 stops over 14 surfaces): every `.status-item`, the `.ghost.small` buttons, the status bar; a focus ring rule in the stylesheet's grammar (Brief 57). (checked 2026-11-09) [verified 2026-11-10: true, 110 controls with no focus change per a11yname.js sweep; open]
- Eight dialogs open as centred cards at 390 and should be bottom sheets (extract, history, connections, binned, run a skill, board keys, meeting notes, features): Brief 59. (checked 2026-11-09) [verified 2026-11-10: true, eight dialogs still centred cards at 390; Brief 59]
- The markup has 18 overlays plus the built confirm and the tour card, not the plan's 15; `$S/design/hierarchy.json` lists each with its size (Brief 59 reads it first). (checked 2026-11-09) [verified 2026-11-10: true, 18 overlays per the markup; hierarchy.json lives outside the repo]
- Not measured by Brief 56: 1024 and 820 widths, dark-theme counts, a Chat with a conversation, the document AI panel, a board with a selection. (checked 2026-11-09) [verified 2026-11-10: true, 1024 and 820 and dark measures not taken]
- The 13.0 gate's "every offence per decision" for decisions 9 to 17 are stylesheet counts from the plan's method paragraph, not from the sweep; still to be read from code (Brief 57). (checked 2026-11-09) [verified 2026-11-10: true, decisions 9 to 17 counts not read from code yet]

## Backend

- **`netbind.host_allowed("localhost.")` and a trailing-dot own name are
  refused** (fail closed, as intended; noted so nobody reads a 421 on
  `localhost.` as a bug). `_own_names()` calls `gethostname` per request
  off loopback, one syscall.
  *Left: intended behaviour, noted so a 421 on `localhost.` is not read as a bug.* (checked 2026-11-09) [verified 2026-11-10: stale, note that fail-closed host refusal is intended, not an open defect]
- **The graph signal needs an open note, and the Notes list rarely has one.**
  `file: frontend/js/app.js`, `id: search-open-note`. The list passes `entry_id`
  only in rows view or while editing; in card view the third signal is zero.
  Next step: decide what "open" means on that surface, per the app's own focus
  model. [brief11-retrieval-engine.md]
  *Needs: what "open" means on the card view is a decision.* (checked 2026-11-09) [verified 2026-11-10: true, graph signal needs an open note; search-open-note id present]
- **Sync (B6) as log shipping.** `id: events-sync`. **Decided and first slice built 2026-11-11** (WORLD_CLASS_PLAN B6 decisions 1 to 14; HISTORY, "WORLD_CLASS B6, sync first slice", "LAN pairing", "documents, boards and files" and "one sync story"). Built: notes, private notes, documents, boards and attached files, over the home network and through a folder by one apply path. [brief7-event-log.md]
  *Needs: a large unstarted feature.* (checked 2026-11-09) [verified 2026-11-10: true, sync log shipping unstarted; events-sync id]
- **I1's later passes**: duplicates, entities and dates as kinds in the same
  table (tensions are built: pass 4 of the night run, `ai/facts.py`
  `_pair_passes`). `ai/entities.py` already produces entities in its own
  shape; folding it in means giving it a span and a `DerivedFact` row, not a
  second pipeline. [learning-loop.md]
  *Needs: design, folding entities into the fact table.* (checked 2026-11-09) [verified 2026-11-10: true, I1 later passes partly built in facts.py; duplicates and dates still open]
- **`evidence_checks` is the one switch with no runner**: stored and shown in
  Settings, gating nothing. `margin_reader` (`api/routes_editor.py`),
  `model_bench` (`api/routes_bench.py`) and `open_questions` (`ai/facts.py`,
  the night pass) read theirs. Evidence cards are built per answer sentence
  (`grounding`, `search/chunks.py`) with no background pass to switch off.
  [learning-loop.md]
  *Needs: a decision on what the switch gates (the per-answer evidence view, or a future background check).* (checked 2026-11-09) [verified 2026-11-10: true, evidence_checks has no runner (facts.py); margin_reader and model_bench still ungated]
- **WORLD_CLASS_PLAN 9's dev-only llama.cpp runner is the blocker behind four
  open items**: the `evals` marker, Skills Phase D's central claim, the
  retrieval engine's real-embedding numbers, and the paging nudge a real small
  model would have to act on. The suite must never depend on it.
  [brief-13-harness.md, chat-timeline-skills.md, brief11-retrieval-engine.md]
  *Left: the runner exists now (`scratchpad/llama-dev.sh`); the four items still need a model.* (checked 2026-11-09) [verified 2026-11-10: true, dev-only llama runner blocker; scratchpad/llama-dev.sh present]

## Sweeps and tooling

- **A check that cannot tell "nothing matched" from "labels are broken" cries
  wolf on every small fixture.** Two of `graph2.js`'s five failures were
  exactly that, measured on a scratch profile holding a single note. The
  lesson is the sweep's, not the graph's. [graph.md]
  *Left: a lesson for the next sweep author.* (checked 2026-11-09) [verified 2026-11-10: true, graph2.js check still cries wolf on small fixtures]
- **The README tour still has two gaps.** The chat screenshot shows an empty
  conversation (no model in the sandbox), so a machine with Ollama should
  retake `docs/screenshots/chat.png` with a real exchange; and the page reader
  has no shot at all, because it wants a multi-page PDF and an OCR binary and
  this sandbox has neither. Files: `scratchpad/ui-sweeps/readmeshots.js`, the
  `chat` entry. [picker-catalog-readme.md]
  *Needs: Ollama and a Tesseract binary.* (checked 2026-11-09) [verified 2026-11-10: true, chat.png still shows an empty conversation]
- **The launchers want one run on a real Windows machine**: `start.bat`,
  `start.bat --doctor`, `start.bat --shortcut` and `uninstall.bat --dry-run`,
  watching the splash through a first-run install. Everything else in Brief 17
  has been exercised. Two things deliberately left: Copy diagnostics copies
  the step history rather than running `--doctor` live (which would probe the
  port the app is about to bind and talk to the git remote mid-install; the
  safe shape is a `--doctor --offline`), and the dry run's "frees about"
  figure counts `.venv` only on Windows, which is 300 MB of a 305 MB answer.
  [launcher.md]
  *Needs: Windows.* (checked 2026-11-09) [verified 2026-11-10: true, Windows launcher run not done; start.bat present]

## Carried from the agent files archived 2026-10-04

Thirty-three finished agent files moved to [`../archive/agent-remaining/`](../archive/agent-remaining)
(their finished work is in HISTORY.md; the files had stopped being written to). What each still held that is open is one row here, tagged; the
archived file has the measurements. Rows that were already in this ledger, or
that the head had since built, are not repeated; the ones the check found built
are named in HISTORY.md, "OPEN.md rows closed, 2026-10-04".

`asktab`, `boot`, `briefs-2026-09-13-night`, `chrome-help`, `documents-tail` and
`readings` hold nothing that is not already a row in this ledger or built on
the head, so they carry no row of their own.

- **arch.md (removed 2026-10-12, recoverable from git history)**: INBOX 266's usability and lightweight items belong to nobody.
  [arch] (The emblem's idle cost is built: HISTORY.md, "OPEN.md rows closed,
  2026-10-05 (docs hygiene before 0.4.0)".) (checked 2026-11-09) [verified 2026-11-10: true, INBOX 266 items unowned; arch.md removed, its items still open]
- **backend-0926.md**: F7's thread modules
  onto `core/jobs.py` (13 left, `tests/test_flaw_class_lints.py`'s ratchet).
  Not verified: the receipt against a real outbound call, the five UIs in the
  desktop window, LAN from a second device, the `.ics` in a real calendar app.
  [backend-0926]
  *Needs: a second device, the desktop window and a calendar app, for the unverified list. The Undo row, the night card's scroll and the ledger's flush are closed, HISTORY.md, "OPEN.md rows closed, 2026-10-04".* (checked 2026-11-09) [verified 2026-11-10: true, F7 thread modules not moved to core/jobs.py (ratchet 13 left)]
- **codecomplete.md**: Python Run via a Pyodide download extra (INBOX 404's
  recommendation, needs the owner's yes to a download kind of extra) and
  TypeScript Run via a vendored type-stripper; SCSS, Less and SVG are not file
  types, so Emmet has nowhere to run for them. Not verified: WebView2's
  handling of the run sandbox's CSP, the native colour picker's window.
  [codecomplete]
  *Needs: a decision and a vendored dependency each.*
  *Needs owner, 2026-10-05: a Pyodide "download extra" fetches at runtime, which the owner's fully-local rule of 2026-10-05 forbids unless it is vendored (about 10 MB, MPL-2.0); the TypeScript stripper is a vendoring call of the same kind.* (checked 2026-11-09) [verified 2026-11-10: true, codecomplete Pyodide and TypeScript runs open]
- **companion-r5.md**: the toss on a phone (a quick swipe on the companion
  tosses it) was not tried on a device; `test_unlock_throttle_per_client.py`
  failed once under load and passes alone. [companion-r5]
  *Needs: a phone; the flake is load, not the test.* (checked 2026-11-09) [verified 2026-11-10: true, phone toss not tried on a device; throttle test file absent]
- **guideia.md**: the Guide is a modal sheet whose scrim dims the app, so
  "Open the Reminders tab" cannot be read against the tab. [guideia]
  *Needs: a non-modal Guide changes `openSheet`'s focus and backdrop contract.* (checked 2026-11-09) [verified 2026-11-10: true, guide is a modal sheet; openSheet in index.html]
- **libtl-0926.md**: the Timeline feed lays out about 39 times a second while
  scrolling (the rows' `content-visibility: auto`, INBOX 400's trade); the
  Library search keystroke was 17 to 191ms under load, not re-measured idle;
  the "Mind maps" chip at zero offers "New concept map" (a naming decision);
  Atlas's feminine right arm sits behind the hair at full size; a mood or act
  change swaps loops rather than cross-fading; the graph tab keeps the
  companion on the bottom bar. [libtl-0926]
  *Needs: drawing-order and animation-blend changes; the rest are measurements to retake idle.* (checked 2026-11-09) [verified 2026-11-10: true, timeline layout about 39 times a second while scrolling; open]
- **mapcull.md**: freehand and link sketches are not culled (a stroke's box is
  parsed from its path; worth it only when a board with many strokes measures
  slow). [mapcull]
  *Left: measure a many-stroke board before building.* (checked 2026-11-09) [verified 2026-11-10: true, freehand and link sketches not culled; open]
- **mapread.md and maprender.md**: 13g, the haywire middle-button pan, needs
  the owner (it never reproduced headless; do not fix blind); the 50-topic
  open is 393ms and not the render; `mapperf.js` takes minutes (whether the
  gate should pass `SIZES=50`); the keyed render is invalidated by one list,
  `wbObjectPaintKey`, which a new paint input must join. [mapread, maprender]
  *Needs owner: 13g. Left: the rest are notes for whoever touches the paint.* (checked 2026-11-09) [verified 2026-11-10: true, 13g pan needs owner; mapperf.js present]
- **maptheme.md**: the theme is resolved into each node on export rather than
  carried; an `<arrowlink>` written by FreeMind itself is untested. [maptheme]
  *Needs: schema and export design.* (The palette, the font and the pin back to
  the app's default are built, MINDMAP_PLAN 13e.) (checked 2026-11-09) [verified 2026-11-10: true, theme resolved on export; arrowlink untested]
- **mindmap2.md**: `mindmapimage.js` (removed 2026-10-12, recoverable from git history) passes 12 of 12 at 390x844 (measured
  2026-10-04); a picture node does not resize to its picture; `mindmap3.js`
  times out at `#wb-boards-generate` (the AI half); `mindmapcurve.js` at
  390x844 passes 11 of 14 (its map is laid out wider than a phone, so the
  hover reveal and the straight-line kink aim at off-screen handles: the
  probe's layout, not the app; the add-button overlap that timed it out was
  the app's and is closed, HISTORY.md). [mindmap2]
  *Needs: lay the curve probe's map out inside 390 wide. Tried 2026-10-05 (topics 110 wide at x 8, 220 and 250, `mindmapcurve.js`): the reveal check passes (the handle's top element is the svg layer, not a button) but every drag moves 0 (9 of 14), so the layout is not the only thing at 390; not kept.* (checked 2026-11-09) [verified 2026-11-10: true, picture node resize open; mindmapimage.js removed, finding outlives it]
- **ocr-reading.md**: a page joins the reading panel only once looked at or
  read (nothing reads ahead, deliberately); nothing was verified with a real
  Tesseract or a vision model. [ocr-reading]
  *Needs: Tesseract and a model.* (checked 2026-11-09) [verified 2026-11-10: true, ocr-reading: page joins panel only when read; no real Tesseract or vision run]
- **pass2.md**: typing in a note in a 230-note list costs about 12ms of
  CodeMirror input handling per key; the Library's lists have no user-owned
  order to drag; grey-scale text in composited scrollers on a 1x ClearType
  display was not seen. [pass2]
  *Needs: a Windows display; the rest is CodeMirror's own cost.* (checked 2026-11-09) [verified 2026-11-10: true, pass2 typing cost and list ordering open per bullet]
- **perfpolish.md**: the document gutter writes a height and reads a layout
  per gutter. The menu exit is closed, HISTORY.md, "OPEN.md rows closed,
  2026-10-05 (the pre-0.4.0 buildable rows, sweeps on port 8815)". [perfpolish] (checked 2026-11-09) [verified 2026-11-10: true, perfpolish gutter layout reads per gutter; open]
- **uipolish-0924.md**: the surface-by-surface pass (its item D) is already a
  row above. Triaged: `deadbtn.js`'s findings for Chat's `#chat-export` and
  `#chat-delete` are visually-hidden, `aria-hidden` proxies the ⋯ rows click
  (index.html ~2335), the sweep's finding and not a dead control; the
  Packages rows' title-to-description gap measures 12.8px at 1440, 1024, 820
  and 390 (`packagesgap.js` (removed 2026-10-12, recoverable from git history)), not the 16px reported. [uipolish-0924]
  *Needs: item D, a design pass per surface.* (checked 2026-11-09) [verified 2026-11-10: true, uipolish-0924 leftovers; deadbtn.js findings triaged, rest open]
- **wbtopbar.md**: `#wb-search-toggle` and `#wb-navigator-toggle` duplicate View
  menu switches (UI_MODERNISATION_PLAN Phase 8 names them as the bar's find
  zone); `#wb-context-menu` is not swept (`wbcontextphone.js` is where it
  belongs). INBOX 47's counting question no longer decides anything: the
  Notes and Library docks measure 6 controls each (`docks.js`). [wbtopbar]
  *Needs: the whiteboard agent (a sweep for `#wb-context-menu`).* (checked 2026-11-09) [verified 2026-11-10: true, wb-search-toggle and wb-navigator-toggle still duplicate View switches]
- **whiteboard-tail.md**: the AI half of the map needs a model. INBOX 276 (the
  sketch pad's toolbar at 820) is closed, HISTORY.md, "OPEN.md rows closed,
  2026-10-05 (the pre-0.4.0 buildable rows, sweeps on port 8815)". [whiteboard-tail] (checked 2026-11-09) [verified 2026-11-10: true, AI half of map needs a model; open]
- **world-class-rows-1-2-9.md**: two decisions taken differently from Brief 15
  (S1 is a cookie, S3 confines to home and the data folder) that the owner may
  want to confirm; the export-folder preference accepts any writable absolute
  path; a clean full-suite run on that worktree was owed.
  [world-class-rows-1-2-9]
  *Needs: the owner's yes or no on the two decisions and on the export-folder path rule.* (checked 2026-11-09) [verified 2026-11-10: true, two decisions for the owner to confirm; open]
- **writing-desk.md**: Stop mid-pass is unverified (the stand-in answers in
  about 150ms; a slow backend behind an env var in `fake_openai_server.py`
  would do); the thinking panel has never held real thinking; the five draft
  prompts are tested, not judged; sources are notes only. The readOnly hole
  it named is fixed (CHANGELOG, `draftreadonly.js`). [writing-desk]
  *Needs: a slow backend and a real model.* (checked 2026-11-09) [verified 2026-11-10: true, writing-desk Stop mid-pass unverified; fake_openai_server.py present]

No per-agent file stays in this folder: the 2026-10-05 pass carried the last
ones' rows below and archived them (`agent_common.md` and `agent_rules_1005.md`,
the rules every agent carries, stay). A running agent writes its own
`<name>.md` here; the next ledger pass carries what it left.

## Carried from the agent files archived 2026-10-05

Thirty-eight finished agent files moved to
[`../archive/agent-remaining/`](../archive/agent-remaining) (no agent was
running; the finished work is in HISTORY.md). Each row below is what a file
still held that the code, INBOX, BACKLOG and the plans do not already hold,
checked by grep on the head the day they moved; the file named in brackets has
the measurements. Items the plans already carry (the Atlas rows 540 to 575,
WORLD_CLASS_PLAN's B2 and I7 rows, the web clipper's page intake,
UI_MODERNISATION_PLAN's off-band widths, WHITEBOARD_PLAN decisions 30 to 36's
ghosts, line jumps and carried waypoints, AGENT_SKILLS_REFORM's skill-run Undo)
are not repeated. Found built since and dropped: the entity merge Undo, the
note-type, space and conversation delete Undos, `autonomous.reset_state()`,
the `settingsnav.js` skip below 640, `stripground.js` and
`settings-skeletons.js` on the branch, the board card's expanded state (INBOX
238), the lazy graph popup resize stand-in, the reminder chime primed on the
first press, the OCR reading's collapse, Atlas hiding behind a modal, the
Atlas persona text in Settings, the spelling "Boards & maps" and the About
pane's name, the errors sweep's aside clipping at 390.

### Notes, Documents and Library

- **Skeletons for a board's Library and Notes tabs** (INBOX 596): the tabs
  (`whiteboard-library.js`, `wbLoadLibrary`) draw nothing while they load.
  [boardmap-1005, small-1005]
  *Left: the whiteboard's own rail, owned by the WHITEBOARD plan's agent.* (checked 2026-11-09) [verified 2026-11-10: true, wbLoadLibrary draws nothing while loading; skeletons not built]

- **Phone selection menus and the selection bar** (documents): iOS and Android
  draw Cut, Copy and Paste above a selection, where the bar also goes; if a
  report arrives the bar goes below the selection on `(pointer: coarse)` (one
  line in `selectionBarShow`). Section 18's chat commands on a phone press
  controls in the chat dock and were never measured against it.
  [documents-1004]
  *Needs: a phone.* (checked 2026-11-09) [verified 2026-11-10: true, phone selection bar overlaps native Cut Copy Paste menu; open]
- **Prose tools**: Harper's lint config per kind in the dictionary dialog
  (`harper-worker.js`, `setLintConfig`; about 200 rules, all or nothing today);
  suggestion mode's author and date (CriticMarkup `{>>comment<<}`; export
  writes `MemoryMap` for every revision); a voice and speed picker for read
  aloud (system voices only today). [proseeditor]
  *Checked 2026-10-05: neither is built (`harper-worker.js` turns off the one rule `UseTitleCase` in `HARPER_RULES_OFF` and nothing else; `docReadAloudVoice` in `documents-prose.js` picks the first local voice for the language). Needs a design call: where the two controls live (the dictionary dialog, Settings), what is stored, and the help that moves with them.* (checked 2026-11-09) [verified 2026-11-10: true, HARPER_RULES_OFF in harper-worker.js; setLintConfig per kind not built]
- **Package bundles**: the Word writer's five tests ran once in a scratch venv
  with python-docx 1.2.0 (2026-10-05, `tests/test_docexport_pictures.py` 13 of
  13, none skipped; `test_docexport_bundle.py`, `test_document_import.py`,
  `test_docview_import.py`, `test_extras_bundles.py` 57 passed), but no export
  was opened in Word or LibreOffice; no real pip ran (every bulk test fakes `subprocess.Popen`);
  the bundle groupings are a recommendation (`BUNDLES`, one tuple); the phone
  rows measured clean, not designed further. [extras-bundles]
  *Needs: Word or LibreOffice.* (checked 2026-11-09) [verified 2026-11-10: true, bundle tests named in the bullet not found at those paths; Word writer checks open]
- **The Writing Room's stretch**: measured at 1440x900 light on the two
  `NOTE_SURFACES` boxes only, the graph's two note boxes not opened. (The table
  full view's X is built: 28x28 at 1440 and 44x44 at 390, each equal to
  `--target-min`; `tablefullclose.js` (removed 2026-10-12, recoverable from git history) asserts it. Its phone width and the Writing
  Room's are closed, HISTORY.md, "OPEN.md rows closed, 2026-10-05 (the pre-0.4.0
  buildable rows, sweeps on port 8815)".) [notes] (checked 2026-11-09) [verified 2026-11-10: true, Writing Room stretch measured on two boxes only; open]

### Whiteboard, mind map and Atlas

- **Board and map history**: an agent's or another tab's change is not on a
  board's stack (decision 17 says the event log is the long memory; a board's
  undo survives a reload since 2026-10-05, `undo-store.js`); redo of the board-level steps (theme,
  numbering, layout) is not swept; `wbMapCrossLinkToBranch`,
  `wbMapReverseCrossLink`, `wbMapCutCrossLink`, `wbMapAddReference`,
  `wbApplyMapTemplate`, `wbArrangeMindMap`, `wbMindMapAddCard`, bucket fill and
  fit to text are recorded through `wbRecordGesture` but not swept one by one.
  [undo-1005] (checked 2026-11-09) [verified 2026-11-10: true, board and map history cross-tab and agent changes not on the stack; open]
- **Draw.io phase 2's tail** (WHITEBOARD_PLAN 30 to 36 hold the decisions):
  Phase G's affinity sort (Group by theme proposes named frames, one Undo) and
  the claim check, both with faked-transport tests and
  `agent.PROSE_BUDGET_CHARS`; the time machine's plain-words "what changed";
  expand from my notes (MINDMAP_PLAN 12.3 item 2);
  ports are mouse and pen only (touch has no hover). Found: SQLite reuses a
  deleted row's id (no AUTOINCREMENT on the board item tables), so one id's log
  can hold two items; the board history starts a fresh state on each `created`
  but any other reader of an item's log (`events.replay`) would merge them;
  placements made before the history, a duplicated board's copies and a
  generated map's topics have no `created` event. [wb-phase2] (checked 2026-11-09) [verified 2026-11-10: true, draw.io phase 2 tail (Group by theme, claim check) open per bullet]
- **Frames and the map plan's rest**: MINDMAP_PLAN 12.2's rest (a boundary round
  a lassoed set that is not one branch, priority, progress, flags and due
  dates, floating topics and palettes, an outline pane). The nested frames'
  shared title area is measured, HISTORY.md, "OPEN.md rows closed, 2026-10-05
  (the pre-0.4.0 buildable rows, sweeps on port 8815)". [harness-wb-1004] (checked 2026-11-09) [verified 2026-11-10: true, map plan 12.2 rest open]
- **Map render and persistence**: (the `wbMapNodeSize` 94px row is closed,
  HISTORY.md, "OPEN.md rows closed, 2026-10-05 (the pre-0.4.0 buildable rows,
  sweeps on port 8815)"); a map does not re-frame
  after a tidy (a decision: frame after a tidy that pushed content off the
  canvas, or rely on Fit); tidy, copy branch and
  "open every folded branch" persist one node per request (a bulk endpoint if
  any ever matters); `mapstyle.js` (removed 2026-10-12, recoverable from git history)'s "radial slot" check reads `w: 0` on the
  base too. [mindmap, mapux2] (checked 2026-11-09) [verified 2026-11-10: true, map render and persistence rest open; wbMapNodeSize row closed elsewhere]
- **The Boards and maps dashboard widget's tall maps**: a 25-topic tree-right
  map draws a 20x40 paper in the 72x40 row box. Cropping a tall map or a
  square box is the owner's judgement. [mindmap-13e]
  *Needs: the owner's call.* (checked 2026-11-09) [verified 2026-11-10: true, tall-map crop in the dashboard widget is the owner's judgement; open]
- **Atlas motion, measured left** (the owner's rows 554 to 575 are above):
  `atlas619-blend.js` stepped by hand shows laughing's end moving the figure
  about 3px over three frames, base and fix alike (390 dark: the masculine
  tilt's start 7px, the feminine wiggle's end 3.3px; not isolated, trace the
  figure box's computed transform per stepped frame at 390); `atlas601-tail.js`
  still reads the tail's tip still for 1.8 to 2.2s under load 15 to 21
  (re-measure on a quiet machine); at 390 the props and viewer sweeps ran 2 to 7
  frames a second, so the coil, the moon and the feminine sit's calm read under
  threshold there; the masculine cloak's flare leaves the torso's taper at the
  join by 0.1 to 0.2 drawing units. Deferred since 2026-09-27: an arm rig for
  poses that cross in front of the body (hands on hips, clasped, to chest; the
  arms are separate svg roots behind the body in every look), and a fuller
  front hair mass for the feminine look (the owner at release). The Atlas guide
  panel's '?' did not reproduce (needs the owner's case). [atlas-1005, wrapup-0927] (checked 2026-11-09) [verified 2026-11-10: true, Atlas laughing blend measured by hand; scratch file gone, finding stands]

### Settings, help and the shell

- **Help audit's remainder**: menus drawn on press (the chat "/" menu, a
  message's menu, the board menus, the notes list's menus) are checked by
  source grep only, and a sweep that presses each and lists its items would
  close it; the JS-built popovers (`manage-cat-help`, `manage-tags-help`,
  `inbox-help`) and the whiteboard and map help bodies were not read; the sweep
  runs at 1440 only, so a control a narrow window moves into a menu is named for
  the wide layout. [helpaudit-1005] (checked 2026-11-09) [verified 2026-11-10: true, help audit remainder for press-drawn menus open]
- **Chat panels not measured**: `#chat-model-panel` with a model connected
  (`popupsart.js` (removed 2026-10-12, recoverable from git history) cannot open it without one; use `scratchpad/llama-dev.sh`)
  and the chat dock's select menus opened from inside the How it answers sheet
  at 390. Status chips: WORLD_CLASS_PLAN 1.2's wording and DESIGN.md's label
  recipe disagree (taken: the label recipe, `META_EDGED`; if the owner wants
  statuses edgeless it is one rule, `.chip.item-label`'s border). [design-1004]
  *Needs: the owner's call on the chips.* (checked 2026-11-09) [verified 2026-11-10: true, chat model panel not measured; open]
- **The tour**: the Timeline's Options and the reminders' More were measured at
  390 only. (The fresh data dir walk and widths 600 to 1100 are done, HISTORY.md,
  "OPEN.md rows closed, 2026-10-05 (the pre-0.4.0 buildable rows, sweeps on port
  8815)".) [tourdepth] (checked 2026-11-09) [verified 2026-11-10: true, Timeline Options and reminders More at 390 only; open]
- **Tablet layouts**: the Documents dock is two rows at 1024 (its identity
  asks for 22rem beside the actions); the arc layout of a 430-note notebook
  framed whole is a line of dots until zoomed; the Notes sub-tabs do not fit the
  list dock's row at 1093 (on a window 700px tall or less the strip could take
  the identity slot as a compact seg, which changes the dock grammar: the
  owner's or the plan's decision). The status bar's fold into the top bar under
  680px is not built, and measured it overlaps nothing, HISTORY.md, "OPEN.md rows
  closed, 2026-10-05 (the pre-0.4.0 buildable rows, sweeps on port 8815)".
  [graph-wb-0926] (checked 2026-11-09) [verified 2026-11-10: true, Documents dock two rows at 1024; arc layout open]
- **Dashboard and Timeline**: D6's streak (the calendar strip and the day
  before and after are built, `daystrip.js`; a streak count has no surface:
  the dock is at its grammar and `.dock-chip-row` is held at zero uses); "Undo all" for a
  background pass or a skill run (each change has its own Undo; an honest "all"
  needs `tools.execute_tool` to run the undos in one transaction, or it is N
  requests that can half fail); the graph signal needs an open note, and the
  Notes filter uses `/search` for operators it does not know. [openitems]
  *Needs: design steps, each its own brief.* (checked 2026-11-09) [verified 2026-11-10: true, D6 streak has no surface; open]
- **The capture draft counts as unsaved work**, so every tab switch with a
  draft asks "Leave without saving?" though the draft is kept and the switch
  loses nothing: a decision, not a bug. [wrapup-0927] (checked 2026-11-09) [verified 2026-11-10: stale, decision that the draft counts as unsaved work, not a defect]

### Backend, architecture and tooling

- **ARCH-02, the save at 5,000 notes**: `POST /entries` p50 210 ms (one line)
  and 345 ms (400 words), not under 150; 390 to 615 ms with 384-wide vectors
  against 61 to 96 ms at 500. The profile (`scratchpad/perf2-1005-prof.py` (removed 2026-10-12, recoverable from git history)):
  the lexical pass walks all 4,000 kept docs per save, `nearest` reads up to
  4,000 postings, `janitor._knn_match` takes 52 ms over the matrix. Tried and
  reverted: a test instead of a list and per-category counts in the corpus
  (exact, removed the walks, not the time). Next: a smaller postings budget
  measured with `scratchpad/filing_eval.py`, or the k nearest read from the
  engine's matrix once per save. [arch1005, perf2-1005] (checked 2026-11-09) [verified 2026-11-10: true, POST /entries 210 to 615 ms, above the 150 ms target; open]
- **The rest of the architecture audit** (`scratchpad/audit1005/arch.md` (removed 2026-10-12, recoverable from git history)):
  ARCH-04's client half (the cursor exists, `after` and `X-Next-Cursor`, but
  `notes-list.js` still reads every page by offset into `allEntries`); ARCH-13
  (response models for the busiest routes and one paging helper; the shape lint
  is built); ARCH-16 (follow-ups are skipped while a turn streams but there is
  no preference and no hardware probe saying "CPU only"); ARCH-22
  (`skill_runner._run_one_step`, 425 lines, and `agent.run_agent`, 416, need a
  state object before they split; `scratchpad/perf2-1005-longfns.py` (removed 2026-10-12, recoverable from git history)); ARCH-10
  (the import-cycle ratchet holds 15 and 3); ARCH-25 (the pool size, a chat
  stream holding its connection, `restore_backup` with sessions open: read, not
  reproduced). ARCH-09 stays as built: `file-entry` shares the one-wide model
  lane with captions on purpose. [arch1005, perf2-1005] (checked 2026-11-09) [verified 2026-11-10: true, architecture audit rest open; ARCH-04 client half]
- **The frontend audit's leftovers** (`scratchpad/audit1005/frontend.md` (removed 2026-10-12, recoverable from git history)):
  FE-09 unused CSS (no coverage-driven deletion started); FE-10 Settings panes'
  markup is not fetched on first open (a `<template>` is still parsed and boot
  code reads Settings ids; a real gain moves every boot reader behind it);
  FE-11 the 720 and 640 groups (26 + 6 and 11 queries, each needing its own
  sweep); FE-13 the tab JS at 5,000 notes was not profiled again; FE-14 on a
  phone the chips' overhang is 44px and a card clips it below its last row
  (34px reached). [perf2-1005] (checked 2026-11-09) [verified 2026-11-10: true, FE-09 unused CSS audit leftovers open]
- **Retrieval and the learned loop, plan rows whose half-built parts live in
  the scratchpad**: "most opened this month" is parked in
  `scratchpad/wc1005b-most-opened.md` (removed 2026-10-12, recoverable from git history) (`core/opens.py`, `GET
  /entries/most-accessed?period=month`, hooks on `flashEntry` and
  `openNotePage`, the Most used widget's seg, then the HISTORY block and a
  CHANGELOG line); the "wrong" correction on an evidence card (I7's second (checked 2026-11-09) [verified 2026-11-10: true, most-opened parked; /entries/most-accessed route exists, core/opens.py absent]

- **A flaky timing test**: `tests/test_relations_kg2.py`'s 10k timing is flaky
  under load (the typo, message-wording, thread-ratchet and list-paging tests
  perf2-1005 and worldclass-1004 recorded as red pass on the head, 2026-10-05).
  [perf2-1005] (checked 2026-11-09) [verified 2026-11-10: true, tests/test_relations_kg2.py 10k timing flaky under load]
- **Retrieval and the learned loop, plan rows**: the "wrong" correction on an evidence card (I7's second
  half) and I1 pass 2's kinds as derived facts (dates, duplicates, entities)
  are WORLD_CLASS_PLAN rows. [worldclass-1005b, worldclass-1004] (checked 2026-11-09) [verified 2026-11-10: true, wrong-correction on evidence card and I1 pass 2 kinds open]
- **Smaller backend and gate rows**: a note type made through `POST
  /note-types` before the list was read, then deleted, loses its id on Undo
  (not reproduced, pinned by a test); `gate.sh --changed` selects most of the
  suite on this branch; `tests/test_name_mood.py`'s palette test needs
  the palette decided; the container's shared `/tmp/pytest-of-root` grew to 11G
  once and filled the filesystem (`rm -rf` it); the Guide's longest topics sit
  at 1,916 of 1,920 characters and boot CSS at 183,210 of 183,300 gzipped
  bytes, so any new rule needs dead CSS cut first.
  [integ-1005, open-rows-1005, wb-phase2, sweeps, backend-probe, boardmap-1005] (checked 2026-11-09) [verified 2026-11-10: true, note-types undo id loss not reproduced; open]
- **Sweeps**: `touch.js` needs `timeout 300`;
  `revealcell.js` at 390 needs the editor opened first; `errors.js` took
  "Target crashed" at a tab switch (2026-10-05): it did not reproduce on a fresh
  data dir, so the sweep is hardened (a browser per width,
  `--disable-dev-shm-usage`, a crash reported as a finding) and the cause is
  named by its signature, not measured. [sweeps, small-1005, backlog-1005b] (checked 2026-11-09) [verified 2026-11-10: true, sweep caveats open (touch.js timeout, errors.js crash)]
- **Not verified**: Quit's 0.72 opacity contrast is computed (about 3.1:1
  light, 5:1 dark), not read from pixels; the line numbers' baseline drop is
  measured in the sandbox's system-ui only (Segoe UI has other metrics); the
  Windows rasteriser at 125% and 150%; every tablet and phone number is
  Chromium emulation; a real model for the Atlas, retrieval and skill rows.
  [design-rows-1005, quick-gutter, iconalign-skel-1005] (checked 2026-11-09) [verified 2026-11-10: true, Quit opacity contrast computed not read; open]

## Closed 2026-10-06 (the last round's three found-not-fixed items)

- **The shell at 360 wide, Large text, Spacious density was 368px** (hash
  c069120). Cause: the header's six squares take `--target-min` and
  `--header-control-h`, rems, so Large text made them 49.5px; the dock only
  followed the stretched layout viewport. Both are capped at 44px inside
  `header#top-bar`, and below 360 the bar's padding and gaps step down (inside
  07-whiteboard-misc.css's one 359.98 query; `test_breakpoints.py` allows one).
  `shellwidth.js`: scrollWidth <= viewport at 320, 360, 390 x small, normal,
  large x compact, comfortable, spacious x all seven tabs, 20 failures to 0;
  `phonehead.js` 0 findings. Note `innerWidth` grows with the content on a
  mobile context (it read 368), so the sweep bounds against the viewport it
  asked for. (checked 2026-11-09) [verified 2026-11-10: true, 360px header overflow at Large text, hash c069120; cause open]
- **Four sweeps repaired** (447d6fb, e4c1b76, and the commit that records this).
  `kebab-viewport.js` ran 80s, the Bash limit's edge: `ONLY=menus|dock|wb`
  splits it (12, 8 and 60 checks) and a not-found or did-not-open line now
  fails it. `selmenu.js` selected a notes row, where a drag selects nothing; it
  takes a paragraph and ends in PASS or FAIL. `libtab.js` listed no board on a
  fresh data dir; it creates a board and a map and asserts the Library tab
  leaves each. `mapstrip.js` asserts the corner `.wb-map-resize-grip` (absent
  until selected, nwse-resize, grows the box, Shift scales text, 72x40 and 10
  to 44 clamps), 43/43. It found a real fault: the grip, link and reference
  doors closed over the object the node was built with (`wbMapLiveDatum` now
  looks it up by id), so after a refresh a plain grip drag restored a cleared
  25px text size. (checked 2026-11-09) [verified 2026-11-10: fixed, four sweeps repaired at 447d6fb and e4c1b76, both in history]
- *Found, not fixed:* `phonetabs.js` reports 3 findings on a near-empty
  notebook (the bar does not recede on scroll there: nothing scrolls); not
  compared against the base, since the change here does not touch the dock. (checked 2026-11-09) [verified 2026-11-10: true, phonetabs.js 3 findings on a near-empty notebook; found, not fixed]

## Not verified

- **Every provider test runs against a fake transport** (CLAUDE.md section 4),
  and that covers more open work than any other single line here: no real
  model has run a skill, the night pass, the Guide's tab context, the paging
  nudge with an offset written into it, or a grounding answer that
  paraphrases. The grounding event that was measured came from seeding a note
  containing the stand-in's one fixed sentence. [chat-b.md,
  brief-13-harness.md, learning-loop.md, chat-popup-agent.md] (checked 2026-11-09) [verified 2026-11-10: true, fake transport caveat; real-model work unverified]
- **Nothing Windows was executed**: `splash.ps1` has never been drawn (layout,
  the marquee, the Details toggle, `Clipboard::SetText` from a hidden host,
  the error card's button swap), `start.bat --doctor` has never printed its
  table, `--shortcut`'s `.lnk` and `uninstall.bat --shortcuts` have never run,
  nor `netstat` port detection or the `%DATE%`-derived log filename on a
  non-English Windows. **Not run on macOS** either: `./start.sh --shortcut`'s
  Finder-alias branch, its symlink fallback and the `notify`-mode splash. The
  doctor's Ollama and Updates rows were exercised only in their negative
  state. [launcher.md] (checked 2026-11-09) [verified 2026-11-10: true, Windows splash never drawn; splash.ps1 present]
- **No pre-Brief-7 database was upgraded.** Both migrations are exercised by
  the suite and written to be idempotent, but a real year-old file was never
  opened; compaction's numbers come from a database this sandbox built (150
  notes, 40 edits each) and one running app's notebook.
  [brief7-event-log.md] (checked 2026-11-09) [verified 2026-11-10: true, no pre-Brief-7 database upgraded for real]
- **Nothing in the learning loop was measured past a test-sized notebook.**
  The pass is O(notes) with one query per note for the already-known
  fingerprints, which is the first thing to profile on a real notebook. The
  resurfacing numbers are this sandbox's: read 6.7 ms at 800 notes, compute 50
  to 230 ms. [learning-loop.md] (checked 2026-11-09) [verified 2026-11-10: true, learning loop not measured past test size]
- **Every cosine number in the retrieval work came from the 4-dimensional
  fake.** A real backend is 384-dimensional, anisotropic, and its `embed_text`
  per query is the cost the engine does not measure. Next step:
  WORLD_CLASS_PLAN 9's runner, then re-run
  `scratchpad/search/measure_engine.py` (removed 2026-10-12, recoverable from git history). [brief11-retrieval-engine.md] (checked 2026-11-09) [verified 2026-11-10: true, cosine numbers from 4-dim fake; embed_text cost open]
- **Chromium only, mostly 1440x900, no second browser and no real touch
  device.** The graph's world constant in `gcWorldFor` (1.6 to 1.25) is
  reasoned above about a thousand notes; touch and pinch on the map are
  untested; the whiteboard was seen at 1440x900 and 390x844 at DPR 1 only;
  the documents contrast ratios use one sampled ground (`--page` is a
  gradient, so the dark figure `rgb(27, 31, 44)` comes from
  `scratchpad/pngpixel.py` on three points of a screenshot). [graph.md,
  whiteboard-phases.md, documents-batch.md, visual-c.md] (checked 2026-11-09) [verified 2026-11-10: true, Chromium only, no real touch device; gcWorldFor constant open]
- **The desktop window was never run** (`start-desktop.sh`); every visual
  claim on this branch is a browser tab. [prose-intelligence.md, visual-c.md] (checked 2026-11-09) [verified 2026-11-10: true, start-desktop.sh never run; desktop window unverified]
- **Every frame-cost number is headless Chromium with no GPU**, so the ranking
  and the order of magnitude hold and the absolute milliseconds do not. The
  background slider's visible effect per step is still unmeasured: ink on the
  canvas varies by about 0.15 points between two boots of the same settings
  (every style places its marks with `p.random`), and frame cost at the two
  ends moves by less than this environment's noise. The honest next step is a
  person looking at five screenshots, or a design change so the slider drives
  something with a large signature (the wash's own alpha). Mesh is the
  expensive style (+27.6ms a frame, worst frame 166.7ms). [responsive.md] (checked 2026-11-09) [verified 2026-11-10: true, frame-cost numbers headless with no GPU; open]
- **How the dark palette reads on an OLED panel or at another display gamma**,
  and the luminance column `glassdepth.js` takes, which was not re-run after
  the shadow tokens changed. [responsive.md, visual-c.md] (checked 2026-11-09) [verified 2026-11-10: true, OLED and display gamma not checked; glassdepth.js not re-run]
- **A PDF's page picture was never seen drawn**: this sandbox has no PDF
  render extra (`pdfpages.available()` is false, `/media/pdf-page/...` answers
  404), so the OCR workspace's stage stayed empty for a PDF. Choosing a reader
  was not exercised end to end either: all three options are `disabled` here,
  so the option row's click handler correctly returns without changing the
  value. Nothing measures a real reading: no vision model and no Tesseract ran.
  [library-blockers.md, ask-head-ocr.md] (checked 2026-11-09) [verified 2026-11-10: true, PDF page picture never seen; pdfpages.available false here]
- **No screen reader was run** against `aria-current="location"` in the
  documents outline. [doc-sidebar.md] (checked 2026-11-09) [verified 2026-11-10: true, no screen reader run against aria-current]
- **IME composition inside the editor engine**, and the fallback path reached
  by a genuinely blocked request rather than by setting `docCmBroken` by hand.
  (The fallback surface itself was verified in 2026-09-13's `docfallback.js` (removed 2026-10-12, recoverable from git history)
  run, 8 of 8.) [documents-engine.md, documents-phases.md] (checked 2026-11-09) [verified 2026-11-10: true, IME composition and docCmBroken fallback path not driven; open]
- **The whiteboard's PDF export** goes through the browser's print dialog,
  which Playwright cannot complete, so it is the one pair of the
  scope-by-format matrix no sweep asserts; pen pressure and the rail's
  long-press flyout have never been driven by a touch device; the
  highlighter's Shift-straight branch is exercised by hand, not by the gate.
  [whiteboard-phases.md] (checked 2026-11-09) [verified 2026-11-10: true, PDF export via print dialog not testable in Playwright; open]
- **The popup agent's results pane with a conversation in it.** Everything was
  measured on the empty state, since this sandbox has no model;
  `.command-palette-results` keeps its own `--card-pad-x` inset, and that is
  reasoned, not observed. [popup-redesigns.md] (checked 2026-11-09) [verified 2026-11-10: true, popup results pane with a conversation not measured; open]
- **Write with AI was measured with the model off**, so "Draft it" is disabled
  and the draft box is empty in every measurement. The column heights are the
  same either way (the boxes stretch), but an in-flight draft with its Stop
  button and a long status line has not been seen. [notes-subtabs.md] (checked 2026-11-09) [verified 2026-11-10: true, Write with AI measured with model off; open]
- **A real log stream under load.** The live pill reads green and the filters
  hide the right count (275 records on the seeded server), but nothing here
  produced a burst, so Follow's scroll-pinning was not exercised beyond
  toggling it. [logs-cards-links.md] (checked 2026-11-09) [verified 2026-11-10: true, real log stream under load not produced; open]
- **Real-browser text metrics beyond Chromium.** The wrap sweep measured
  420 to 2200px at the app's own 95% `--zoom`; a different engine could shift
  an exact wrap breakpoint by a few pixels, and none of the fixes depends on
  one holding. [wrap-sweep.md] (checked 2026-11-09) [verified 2026-11-10: true, text metrics beyond Chromium not measured; open]

## Atlas and the companion, placed from INBOX 752 (2026-10-10)

- The behaviour model (Brief 34, second part): a state machine with blended transitions, idle variation from a weighted pool, reactions to every app event with a budget, gaze and lean, the enlarged view on the same state. Measures: snapping transitions per minute 0; 12 distinct idle motions per ten minutes; reaction latency under 100 ms. (checked 2026-11-09) [verified 2026-11-10: true, Brief 34 behaviour model second part; open]

## Atlas, placed from the owner's list 2026-10-10

Entries are the owner's words, then the recommendation. Bugs come first, then design requests. Brief 34 carries the whole group.

### Bugs

- "I cant right click to view the menu to change the companion in the expanded popup view"
  Recommendation: the enlarged view gets the same context menu as the small companion, with the change-companion item in it. Also carried by Brief 34 (the enlarged view). (checked 2026-11-09) [verified 2026-11-10: true, enlarged popup lacks the small view's context menu; open]

### Design requests

- "I barely get to see atlas change expression. atlas and the companion movement and behaviour need to be more and more lifelike, natural, smooth, varied, and more."
  Recommendation: mood changes are visible within a short session, measured as mood changes per session before and after. Also carried by Brief 34 (moods that change, lifelike motion). (checked 2026-11-09) [verified 2026-11-10: true, owner ask on expressions and lifelike motion; open]
- "The companion and atlas needs a lot more improvement, and lifelike behaviour, more cool and diverse ways to move around, enter the screen, change between behaviours and more."
  Recommendation: add entrance and behaviour-change animations to the companion and Atlas, and count the distinct movements per session. Also carried by Brief 34 (gestures, entries and the walk cycle). (checked 2026-11-09) [verified 2026-11-10: true, owner ask on companion behaviour variety; open]

## Left by the deepen agent (Brief 72a, merged 2026-10-10)

- Not verified: whether the closed `.doc-dock-menu-list` at 390 paints (it lays out, 13 items, x = -32 on a code document); open it and measure before Brief 76 row 2. (checked 2026-11-09) [verified 2026-11-10: true, closed .doc-dock-menu-list paint at 390 not measured]
- Not verified: the map grip that overlaps "Add a child to" (its accessible name was not read; it shows only with a topic selected after adding children). (checked 2026-11-09) [verified 2026-11-10: true, map grip overlap with 'Add a child to' not read; open]
- Undo counts for documents (2/11), OCR (0/5) and meetings (1/6) are a static read of each handler for `pushUndo`, not driven; Brief 74's `undo.js` replaces them. (checked 2026-11-09) [verified 2026-11-10: true, undo counts from static reads; undo.js replaces them]
- Not driven: Summarise's 503 with no model (read from `routes_meetings.py`), pinch zoom in the OCR workspace, the phone path of any board or map command, Find anything for "ocr". (checked 2026-11-09) [verified 2026-11-10: true, Summarise 503, pinch zoom and phone board paths not driven]
- Timings vary two to four times between runs (the machine was shared with other agents; map add-a-child 102 to 424 ms); the blocks give ranges. Rerun `deepen72a.js` on an idle machine before a brief quotes a "before". (checked 2026-11-09) [verified 2026-11-10: true, timings vary between runs; rerun of deepen72a.js open]
- Bergamot's licence (MPL-2.0 into AGPL-3.0) and sizes are stated as the evaluation's job (Brief 83), not checked here. (checked 2026-11-09) [verified 2026-11-10: true, Bergamot licence check left to Brief 83; open]

## Carried from the agent files archived 2026-10-10

Thirty-nine finished agent files moved to [`../archive/agent-remaining/`](../archive/agent-remaining) on 2026-10-10, in four batches: every file dated 1005 or 1006, and landing-645, meetings-644 and mc1. Each row is what a file still held that is open on the head the day it moved and that neither HISTORY.md, CHANGELOG.md, the plans nor INBOX holds. The file in brackets has the measurements.

- Drag to delete takes no drag from the board sidebar (Library, Layers) onto the trash target; a drop from the Library panel is not a delete. (from av1-1005.md) (checked 2026-11-09) [verified 2026-11-10: true, drag from board sidebar to trash not a delete; open]
- 24 single-line `toast("...", true)` calls with a literal message remain in `frontend/js`; some are expected conditions (validation, "nothing to ... yet") that carry Report this. A `report: false` option costs boot bytes. (from e2e-1005.md) (checked 2026-11-09) [verified 2026-11-10: true, 24 literal toast calls remain in frontend/js]
- With a model, the composer shows "Filed under Work (100% sure)" for a small model's pick (a dentist appointment); the certainty shown for a small model's pick is too high. (from e2e-1005.md) (checked 2026-11-09) [verified 2026-11-10: true, Filed under Work (100% sure) shown for small model picks; open]
- A row added or removed after a list's first render does not fade; the lists redraw whole, so this needs keyed rendering first. (from motion-1005.md) (checked 2026-11-09) [verified 2026-11-10: true, lists redraw whole so no fade on add or remove; open]
- Help popovers close at once: a popover goes home and is removed on close, which cancels its exit transition. (from motion-1005.md) (checked 2026-11-09) [verified 2026-11-10: true, help popovers remove on close, cancelling exit transition]
- A sub-tab's panel does not cross-fade; only its line slides. CSS cannot tell a section switch from a page arriving; it needs a class set by `showNotesSection`. (from motion-1005.md) (checked 2026-11-09) [verified 2026-11-10: true, sub-tab panel does not cross-fade; showNotesSection class not set]
- CHAT: the evals gate runs on a 3B model (hours on these cores) and waits on a real-model run. (from op3-1005.md) (checked 2026-11-09) [verified 2026-11-10: true, evals gate waits on a real-model run; open]
- The `.skill-fact-reads` chip reads dy +4px in one of four identical instances on the Skills sub-tab at 1440 (badgealign.js); the instance is not isolated. (from op3-1005.md) (checked 2026-11-09) [verified 2026-11-10: true, .skill-fact-reads dy +4px on one instance; not isolated]
- Sweeps that only click the Library tab time out, because the Library opens on its last sub-tab. `bm1005-sidebar.js` and `bm1005-mapmulti.js` click Boards and maps first; the rest do not. (from op3-1005.md) (checked 2026-11-09) [verified 2026-11-10: true, Library sweeps time out; bm1005 scripts still click Boards and maps]
- UI_MOD Phase 11 item 11: the screenshot set for the owner, which needs a place the owner reads. (from op4-1005.md) (checked 2026-11-09) [verified 2026-11-10: true, owner screenshot set for UI Phase 11 item 11 not placed]
- 444 decision 10, still open: the Tools (4,247px) and Appearance (1,296px) panes are indexed, not split. (from op4-1005.md) (checked 2026-11-09) [verified 2026-11-10: true, Tools and Appearance panes indexed, not split (decision 10)]
- Two-finger scroll jump (460): not reproduced twice; needs a real touchpad trace. (from op4-1005.md) (checked 2026-11-09) [verified 2026-11-10: true, two-finger scroll jump not reproduced; needs a touchpad trace]
- Owner's call: RapidOCR ships as an optional extra (Settings, Packages); confirm it against the 2026-10-05 "fully local, vendored" rule (WORLD_CLASS_PLAN row 31). (from op4-1005.md) (checked 2026-11-09) [verified 2026-11-10: true, owner's call on RapidOCR as an optional extra; open]
- Doc-focus panels between 720 and 819px cover the page, as below 720 did before; not driven in a sweep. (from op5-1005.md) (checked 2026-11-09) [verified 2026-11-10: true, doc-focus panels 720 to 819px not driven]
- Sweeps that wait a fixed 1.2 s for the whiteboard's lazy bundle flake under load (`initWhiteboard is not defined`). `op5-1005.js` and `mapviewmenu.js` wait for the function; the other sweeps with a fixed wait do not. (from op5-1005.md) (checked 2026-11-09) [verified 2026-11-10: true, fixed 1.2 s waits in op5-1005.js and mapviewmenu.js; flake open]
- The board preview labels (`mapPreview` in note-cards.js) run over the next shape ("Cut the sign-up fro…" across a diamond); the label placement is INBOX 263's design and the whiteboard agent's surface. (from qa-1005.md) (checked 2026-11-09) [verified 2026-11-10: true, mapPreview labels run over the next shape; open]
- At 1440 with the Connections rail open, the Notes dock wraps nine controls onto a second row; DESIGN.md says seven at most. A judgement for the dock grammar's owner. (from qa-1005.md) (checked 2026-11-09) [verified 2026-11-10: true, Notes dock wraps nine controls at 1440 with rail open; owner judgement]
- `scratchpad/ui-sweeps/lib.js` LOOK= writes the look into the server's preferences, so later sweeps on that data dir inherit it; run a LOOK=utilitarian sweep last. (from qa-1005.md) (checked 2026-11-09) [verified 2026-11-10: true, lib.js LOOK= writes into server preferences; sweep caveat stands]
- installer.iss's ISPP version reader (`#sub`, `#for`, `RPos`) compiles only on Windows; it is not verified until a Windows CI run passes. (from windows-packaging-1005.md) (checked 2026-11-09) [verified 2026-11-10: true, installer.iss ISPP reader unverified until Windows CI]
- The upgrade step downloads the latest release with `gh` and `github.token`; a fork or a repo without releases fails it loudly. (from windows-packaging-1005.md) (checked 2026-11-09) [verified 2026-11-10: true, upgrade step fails on forks without releases; open]
- The traceback check in the smoke step reads the app's whole output; a benign logged traceback on Windows would fail it. (from windows-packaging-1005.md) (checked 2026-11-09) [verified 2026-11-10: true, smoke traceback check reads whole output; open]
- The installer's optional packages (owner, 2026-10-07: "there's no indicator for the optional packages install and I cant minimise or close the window"): Setup waits on pip and cannot repaint, minimise or cancel. Recommendation: Setup records the picks and finishes; the app installs them on first launch as a background task with progress, a log and Stop (a stopped install rolls back, `extras._roll_back`). (from windows-packaging-1005.md) (checked 2026-11-09) [verified 2026-11-10: true, optional packages indicator on installer; extras._roll_back not found, open]
- `docs/CHANGELOG.md`, `docs/CONTRIBUTING.md` and `docs/SECURITY.md` are mirrors that nothing reads now (the old site fetched them). Keeping or retiring them is the orchestrator's call. (from landing-645.md) (checked 2026-11-09) [verified 2026-11-10: true, docs CHANGELOG, CONTRIBUTING and SECURITY mirrors exist; retire decision open]
- INBOX 641's rest, which INBOX.md no longer holds: Illustrator linked symbols (`library_ref` in whiteboard-library.js), Photoshop topic effects (a level field each, `WB_MAP_LEVEL_FIELDS` and `MAP_LEVEL_FIELDS`), Miro reactions, and the whiteboard half of the research. (from mc1.md) (checked 2026-11-09) [verified 2026-11-10: true, INBOX 641 rest (library_ref, level fields) not in the board code]
- PNG and SVG export draws every topic as one box: `wbBuildExportSvg` (whiteboard.js) leaves out levels, shapes and Phosphor icons. (from mc1.md) (checked 2026-11-09) [verified 2026-11-10: true, wbBuildExportSvg leaves out levels, shapes and icons]
- `DOC_EMOJI_SOURCE` (documents-prose.js) is a second emoji table beside `ICON_EMOJI_SOURCE` (icon-picker.js). (from mc1.md) (checked 2026-11-09) [verified 2026-11-10: true, DOC_EMOJI_SOURCE and ICON_EMOJI_SOURCE both present]
- Playwright reported the topic strip's Text toggle "not visible" after an icon pick, though its rect is 58px wide; `mc1-iconpicker.js` works around it with evaluate clicks. Not investigated. (from mc1.md) (checked 2026-11-09) [verified 2026-11-10: true, mc1-iconpicker.js absent; Text toggle workaround note open]

- Large view: whole-body moves (`nmb-hop`, a hop, a cheer, a startle) move the head 14 to 17px a frame, 2.2 times the rest. Decision needed on slowing them in the large view; recommendation: a gentler `nmb-hop` only under `.nm-viewer-figure`. (from atlas669-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, nmb-hop head moves 2.2 times the rest; decision open]
- A click in Atlas's own large view costs 22 to 44ms in `setAtlasMood` (every layer's animations, then `atlasApply` on 12 layers), 50 to 100ms on a loaded machine: a stall, not a jump. `atlas669-clickcost.js` measures it. (from atlas669-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, setAtlasMood click cost in avatars.js and atlas.js; open]
- The generic (non-Atlas) faces' arms have no rig and so no speed cap; the fastest segment of their wave and hide keyframes was not measured. (from atlas669-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, generic faces' arms have no rig speed cap; not measured]
- Chromium quirk: a blend's implicit end keyframe held `rotate` at its start value under a CSS animation that starts at the same value. The blend avoids it by easing only the values that moved; not reduced to a minimal case. (from atlas669-1006.md) (checked 2026-11-09) [verified 2026-11-10: stale, Chromium quirk already avoided by the blend's easing per the bullet]
- Owner (2026-10-07), a fresh install's search model: an empty or partial `models--BAAI--bge-small-en-v1.5` folder is treated as present, the load runs offline and fails with `EmbeddingCacheBroken`. Treat the model as present only when its weights and config are in the snapshot; otherwise download it as a background task with progress; test an empty and a half-filled cache. (from autoinstall-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, EmbeddingCacheBroken in embeddings.py; empty model folder case open]
- Owner (2026-10-07): the janitor warmed a default chat model it never checked ("Chat with 'llama3.2' failed"). `warm_filing_model` (janitor.py:741) should skip quietly, and Settings, Models should say no chat model is chosen. (from autoinstall-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, warm_filing_model in janitor.py:741 still warms unchecked model]
- Owner (2026-10-07): on first launch, choose the chat, background and image models from the installed ones instead of llama3.2 (Atlas said "was running llama3.2, which is not installed any more" on a fresh install with five models present). Say once what was chosen and why, with Change. (from autoinstall-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, first-launch model choice from installed models not built]
- `renderAutonomousSettings` fills the Models-pane checkboxes only when Background tasks or Web search opens (settings.js, per the file, about line 158); the new switch is filled in `renderPrefs` instead. (from autoinstall-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, renderAutonomousSettings lazy fill in settings.js]
- Autonomous with no model running ends "Finished analysing and linking notes." in 65 ms; it should say it had no model (check `agent.run_agent` for a no-provider error event). (from bgprogress-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, autonomous no-model message still says finished; agent.run_agent path open]
- The night shift's pairing phase is slow (120 s for 2,400 facts and 4,786 pairings with the local matcher), and the bar resets between the reading and comparing phases. (from bgprogress-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, night-shift pairing timing; open]
- If the owner means every pill in a popup, these values are next (kept as `.seg` by DESIGN.md's two-or-three rule): doc-history-filter, ocr-zoom, ocr-view, theme-seg, fontsize-seg, border-style-seg, privacy-range, log-view-toggle, confirm-seg, the print setup, chat-skill-pace, wb-export-seg. (from board715-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, conditional on owner's meaning of every popup pill; open]
- Sweep coverage not yet done: an open board or map, the graph's node popup and controls sheet at 390, the print dialog, the lightbox, the confirm dialog, the onboarding tour, the Attach dialog, the date and time pickers, every card's kebab menu; other looks (`LOOK=`), `CONTRAST=on`, forced colours, Large text with Spacious density. (from clip685-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, sweep coverage list not done]
- `scroll-padding`: a control focused by Tab in a scroller is scrolled to the edge with its ring half cut. `scroll-padding: var(--ring-room)` on `.tab-page`, `.tab-main`, `.modal-content` and `.library-view-section` would close it; not applied on this head (grep), not measured (the sweep does not tab). (from clip685-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, scroll-padding on tab pages; ring cut at scroller edge]
- The ring sweep skips a control at the end of a scroller with more content past it, so a real cut at a scrolled edge is not seen; text cut by a fixed height without `overflow` is not seen either. (from clip685-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, ring sweep skips the end-of-scroller control; open]
- A ring on a control in a body-level fixed sheet that touches the viewport edge (the phone Writing room's draft textarea) is treated as scroll position; no measured fix. (from clip685-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, body-level fixed sheet ring treated as scroll position; open]
- Found: `one_line` for "when is the harbor launch?" quotes the Q4 roadmap rather than the dated sentence; the compose grounding rows lack it. (from composer-everywhere-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, one_line quotes the Q4 roadmap for harbor launch; open]
- Found: a titled note's every sentence scores on its title (`_score`, `TITLE_WEIGHT`), so the brief keeps up to four dated sentences of a note named for its subject. (from composer-model-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, TITLE_WEIGHT in composer_select.py; title scores every sentence; open]
- The eval numbers for the whole voice track (before and after) were not reported: run `tests/_composer_eval.py` and record them. (from composer-voice-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, tests/_composer_eval.py present; numbers not recorded]
- Browser check of Ask and Chat with no model at 1440 and 390, light and dark: the "Did you mean" chip and the clarifying question. The sweep `scratchpad/ui-sweeps/voice741.js` is on branch `wip/composer-voice` only. (from composer-voice-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, voice741.js and wip/composer-voice absent; browser check not done]
- The noisy-question set's coverage (owner: "any and ALL typos ... all slang"): what is still missed, from the eval. (from composer-voice-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, noisy-question coverage open]
- Professional variants for the next-question chips and the citation phrases (`mention_*`, `lists`, `echo`), and other languages' wrappers. (from composer-voice-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, professional variants and other languages open]
- The Settings voice row was checked in Chromium on the light theme only at 1440 and 390; dark not run. (from composer-voice-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, Settings voice row dark theme not run]
- Owner's test (2026-10-07): "How do I change the widgets?" got the whole Dashboard paragraph. A how-to should lead with its step sentence and keep the rest behind "More about the Dashboard". The help voice (`voice="help"`) is in CHAT_PLAN. (from composer-voice-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, how-to answers lead with the Dashboard paragraph; open]
- Ask's "Ask all notes" (`#ask-scope-clear`) is wired only once the Questions view has been opened, so the scope is only set from there (pre-existing). (from composer688-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, Ask all notes wired only after Questions opened]
- At 390 the Ask head's model picker sits on its own short line (224px of 330), pre-existing. (from composer688-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, Ask head model picker on its own line at 390]
- Chat's next-question chips were not seen in the browser: the sweep found no `.chat-followups button`. Check `refreshFollowupVisibility` and the chip element (it may not be a button), then fix the element or the sweep. (from composer725-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, Chat next-question chips not seen in browser; refreshFollowupVisibility present]
- Clicking an Ask chip was not driven: the sweep's `button` selector missed the chip element. (from composer725-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, Ask chip click not driven]
- Link reasons from the composer (owner: "can the composer be user to write better link reasons other than just similar in meaning??"): not started. INBOX 691 is not in INBOX.md, so its concrete overlaps (one note names the other, a shared tag, a shared rare word or name, the same category in the same week) and the sentence-pair reason are open. (from composer725-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, link reasons from the composer not started]

- Chat dock at narrow widths: the streaming state (Stop shown, Send hidden) was not measured. (from dock694-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, chat dock streaming state at narrow widths not measured]
- The icon-only chat-dock toggles are checked by text content and title only; no keyboard or screen-reader pass was run. The phone (under 600) sheet paths (`openChatDockMore`) were measured as a one-line strip and composer at 390, not opened. (from dock694-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, icon-only dock toggles not keyboard or screen-reader checked]
- `wbMapDropTargetAt` (whiteboard-map.js:2661) still converts by hand. Fold it into `wbClientToBoard` and update the pinned line in `tests/test_map_drag_cost.py`. (from dropplace-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, wbMapDropTargetAt still converts by hand at whiteboard-map.js]
- Touch drag from the Library is not tested: HTML5 drag-and-drop does not run on touch. The drag image (its thumbnail and offset) is asserted in source only, since a headless drag shows no ghost. (from dropplace-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, touch drag from Library untested]
- CI margin: Tests (Python 3.13) took 16 m 14 s of its 25 m timeout on the head that was scanned (3.11 took 15 m 01 s, 3.12 14 m 37 s). A slow runner is a red build; raising the timeout is the owner's call. (from final-scan-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, CI test job at 16 m 14 s of a 25 m timeout per the bullet]
- `/jobs/last-runs` is polled after a lock and answers 401 once or twice per lock (forgotpw.js's refused list). Next: stop the poll in `lockNow` and `purgeLockedContent` (`settings.js` reads it at about line 4425). (from forgotpw-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, /jobs/last-runs polled after lock; lockNow in app.js still polls]
- Not verified in a browser: the another-device notice on the recovery card (the sweep server binds loopback only); a real phone and a screen reader on the card. (from forgotpw-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, recovery card notice not verified in browser]
- The Focused hero is taller than before: 157px at 900 to 1920 (was 71), 278px at 390 (was 71 to 87). If the owner finds it too tall on a phone, the next step is the glance as one scrolling row there. (from hero675-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, Focused hero height 157px and 278px at 390; owner check open]
- Not verified: a real model's greeting in the new layout (a long AI line widens the left column up to its 45% cap; measured with handwritten phrases only), the desktop window and RTL. (from hero675-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, real model greeting not verified]
- `scratchpad/ui-sweeps/pickers.js` throws `pickNotesDialog is not defined` at its note-picker section, since that dialog moved into the whiteboard bundle. `segbars.js` and `left1005-openrows.js` still read `#graph-layout` as a segmented control. (from inbox670-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, pickers.js throws pickNotesDialog not defined; open]
- Markers' Flag is still two previews (seg665-1006.md item 5). (from inbox670-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, Flag still two previews per the bullet]
- An interrupted glide restarts at the ease's peak speed: a star's fastest step after a second Regenerate is 13 to 16px against 7px before it. A velocity-matched retarget (a spring) would remove the kick; it was not asked for. (from motion686-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, interrupted glide restarts at peak speed; open]
- RapidOCR and Tesseract never ran for real here: "ready" and the RapidOCR path are faked through `/ocr-readers` and monkeypatched tests. A real install and a real read are open. (from ocr717-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, RapidOCR and Tesseract never ran for real; /ocr-readers faked in tests]
- `ocrflow.js` still reads `#ocr-engine` as a line and clicks `#ocr-more`; it was not re-run, and its engine checks may need the popover opened first. The region drag (outlining a rectangle) was not re-measured after the Regions toggle became a button. (from ocr717-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, ocrflow.js engine checks not re-run]
- README `docs/screenshots/palette.png` (and `docs/index.html`'s copy) still shows notes, a document and a board in the palette. Retake it with `scratchpad/ui-sweeps/readmeshots.js` so the picture matches the alt text. (from palette666-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, README palette.png still shows notes, document and board]
- `tests-e2e/specs/shell.spec.js` has a handoff test that has only had `node --check`; Playwright's runner has not run it. (from palette666-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, shell.spec.js handoff test not run by Playwright]
- Older sweeps that expect note rows in the palette (grep `palette-input`): `ux1005-palette.js` (removed 2026-10-12, recoverable from git history) and `search1005-lazy.js` read command rows only, and `readmeshots.js` types "launch". (from palette666-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, older sweeps expect palette note rows; ux1005-palette.js gone, pointer open]
- Stop part way: the night shift, the backup, resurfacing and the embeddings backfill are each one call with no step to stop at. Only housekeeping reads `passes.stop_requested` (passes.py:184); the backfill's loop could check it. (from progress696-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, night shift, backup and backfill have no stop step; passes.stop_requested only for housekeeping]
- Settings, Packages has its own Embedding models list beside Search and index's, which does the same and more. Recommendation: Packages keeps a single line pointing to Search and index. (from progress696-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, Packages duplicates the Search and index embedding models list; open]
- Not verified: a real model load for the new built-in embedding models (no sentence-transformers here); Pull a model by name is tested against a mocked Hub; Ollama pulls and the found scan against a real Ollama; the dark theme for the new rows. (from progress696-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, real model load for built-in embedding models not run; mocked pull]

- Other jobruns detail strings that carry `{exc}` (grep `note_finished` and `run.fail(` in `src/`) were not audited; only the two named in item 5 were changed. (from quickwins-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, other jobruns detail strings with {exc} not audited]
- Other `[^\]\n]`-style scanners may share the ReDoS shape; the markdown link stripping in the frontend is JS and is not covered by the Python oracle tests. (from quickwins-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, other [^]\n]-style scanners not covered by Python oracle tests]
- Not measured at 390: the Documents sidebar and the board zoom pill are not on screen there (the sidebar is a sheet), so both were measured at 1440 only. (from radius682-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, Documents sidebar and board zoom pill not measured at 390]
- Not measured: the chat dock's controls, the board's context bar, the stepper and the map strip, named in `PILL_CONTROLS` with full-round rules. (from radius682-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, PILL_CONTROLS in 08-consistency.css; chat dock and board context bar not measured]
- An opened row with no title starts with its text, whose first line's centre is 19.4px from the top against the chevron's and cluster's 22px (2.6px off). A title row is exact; the fix wants the text's own line box (`1lh`), not a number per font size. (from rows676-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, opened untitled row text sits 2.6px off the chevron centre]
- The owner's second screenshot showed a stray circle after the hover buttons on an opened row. Not reproduced at 1440, 1920 or 390, light or dark, open or closed. If it recurs, the seed lacks its state (a draft's Publish, a busy chip, a filing chip). (from rows676-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, stray circle on opened row not reproduced; open]
- Phone (390, touch): the first frames of a toggle take 50 to 80ms in headless emulation, so the first frame of the height animation can jump about 40% of the change. Not measured on a real phone. (from rows676-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, first toggle frames 50 to 80 ms in headless; open]
- Phone: a collapsed row's always-shown buttons sit in the details line's scrolled lane, off the row's right edge (right -87.8px, measured; unchanged by the work). (from rows676-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, collapsed row buttons off the right edge at 390, measured]
- Not verified: suggestion mode switched on while a candidate is chosen (the replacement goes through `docProseFix`), a touch long-press on a suggested change, and the phone width. (from suggest689-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, suggestion mode and docProseFix path not verified]
- A word touching a suggestion's marker is never a spelling finding: `docSpellable` (documents.js) rejects a `+` on either side, and `{++` and `++}` are `+`. `{++faque++}` has no finding; `{++the faque ++}` does. Fix: treat `{++` before and `++}` after as a boundary, with a test in `tests/test_prose_tools.py`. (from suggest689-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, docSpellable rejects a + on either side; word-marker case open]
- The prose-tool grammar rules at a CodeMirror lint tooltip (`.cm-tooltip-lint`) in code documents are not suppressed while a pointer menu is open. Only code files are affected, where no suggestion marks exist. (from suggest689-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, prose grammar tooltip in code documents not suppressed under a menu]
- Not verified: the phone's action sheet (`openKebabSheet`) and touch below 600 (its dismissal was not pressed twice), a real screen reader, and the Settings sidebar at 390 as a jump list. (from toggles681-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, openKebabSheet and touch below 600 not verified]
- `.wb-shape-caret` has `pointer-events: none` (per the file), so the Shapes split button's caret never gets a click and the `closest(".wb-shape-caret")` branch in `wbWireToggleGestures` is dead code. A product choice (a 10px caret target), left. (from toggles681-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, .wb-shape-caret pointer-events none; split caret never clicked]
- The topic bar wraps to two rows at 390 (348x102), measured identical on the base: the Branch line and the reset go to a second row under the open door. (from seg665-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, topic bar two rows at 390; same on base]
- The size stepper reads "17px" on a main branch and "22px" on the centre, and Classic's level sizes have no S, M, L or XL word, so the well showed "Map" pressed there. A level-size vocabulary is not in MINDMAP_PLAN. (from seg665-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, size stepper label mismatch and missing S M L XL words]
- The note strip, owner's report (d): every control is 6.4px inside the strip's edge at the default look (measured 320 to 1920). The owner's exact state (look, zoom, text size) was not reproduced. (from seg665-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, note strip controls 6.4px from edge at default look]
- `wbSyncMapStrip` sets a themed field's effective value onto the select, so a topic following the map shows the map's look pressed rather than ringed, except where the value has no option (the 17px size; the level's fill). (from seg665-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, wbSyncMapStrip shows map look pressed rather than ringed]
- The Notes dock wraps to two rows from about 1280 to 1500 with the connections rail open (90px); Tidy's 40px extends that band to about 1640. Moving the words-hidden threshold from 1400 to 1680 fixed both, but `tests/test_breakpoints.py` allows no new width query, so the dock needs a rethink (fewer worded controls above 1400, or a narrower rail). (from tidy691-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, Notes dock two rows from about 1280 to 1500 with rail open]
- The card tooltip and the graph still show a deduced reason as "(73% confidence, deduced)", not a strength word. (from tidy691-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, deduced reason shown as a percentage on card and graph]
- `/entries/{id}/related` lists notes that are already linked, so a press on one answers 400 "already linked" (pre-existing). (from tidy691-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, /entries/{id}/related answers 400 for already linked notes]
- Not verified: the contrast of the accent count on the broom (`contrast.js`), a browser run of the automatic pass after filing (pytest only), and a real model for the "Tags Atlas added" review (the tool door only). (from tidy691-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, accent count contrast and automatic pass not verified]
- Meeting cards show their section headings as raw `## Agenda` text, as every note card does. A meeting-aware card preview (when, who, open action items) needs its own pass. (from meetings-644.md) (checked 2026-11-09) [verified 2026-11-10: true, meeting cards show raw section headings]
- The Timeline's table view (a phone's default) has no mark column, so a meeting reads as a Note there; the feed view shows the meeting mark. (from meetings-644.md) (checked 2026-11-09) [verified 2026-11-10: true, Timeline table view has no meeting mark column]
- Not verified: Summarise against a real small model (the fake model only; its pipe format and quoting are unknown), and transcription (no faster-whisper in the sandbox; the save is driven with a typed transcript). (from meetings-644.md) (checked 2026-11-09) [verified 2026-11-10: true, Summarise with a real small model and transcription not verified]
- `ai-tools.js` says "Open Settings, Models" in words, and none is a link. A button on the toast is the next step and is a new control. (from toasts-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, toast says Open Settings in words, no link; open]
- Not verified: the other 100 `toast(..., true)` call sites were not each triggered. A lint covers them; their situations (a formatter refusing a file, Atlas off in Suggestions) were not driven. (from toasts-1006.md) (checked 2026-11-09) [verified 2026-11-10: true, 100 other toast true call sites not triggered]

## Left by the agents merged 2026-10-10 (deepen-b 72b, mapnotes, vendor 75, briefs, coverage)

The five files are in [`../archive/agent-remaining/`](../archive/agent-remaining); decisions 768 and 769 taken, 728 fixed, 761 and 762 fixed.

- The phone paths through the More sheet: the agent (`toggleAgentPalette()` leaves the overlay hidden at 390), the Guide, the timeline and reminders were reached with `switchTab` or not at all. (from deepen-b-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, phone More sheet paths for agent, Guide, timeline and reminders not driven]
- The reminders quick-add row at 390 (not visible; the phone compose not driven). (from deepen-b-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, reminders quick-add row at 390 not visible; open]
- Chat's 82 (1440) and 136 (390) overlaps after answers: a sticky head over scrolled cards or a real paint clash. (from deepen-b-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, Chat 82 and 136 px overlaps after answers; open]
- Whether each Guide topic answers its question (only the topic's head was read). (from deepen-b-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, each Guide topic answer not checked beyond its head]
- "last week" in Find anything: a window or the words. (from deepen-b-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, last week window or words in Find anything; open]
- Timings: two runs at 1440, one at 390, the second 1440 run under a concurrent sweep; ranges, not budgets. (from deepen-b-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, timings are ranges, not budgets]
- Any real-model behaviour of the agent (CLAUDE.md section 4). (from deepen-b-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, real-model agent behaviour not verified]
- The rail-dot alignment at 390 (0 px at 1440). (from deepen-b-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, rail-dot alignment at 390 open]
- The fixture is 96 notes (the seed ran twice), not 48. (from deepen-b-1010.md) (checked 2026-11-09) [verified 2026-11-10: stale, corrected fixture size (96 notes); the note itself is the fix]
- Chat with no model: "what is 15% of 240" quotes a note; "convert 5 km to miles", "what day is it today" and "summarise my week" answer "Nothing in the notes"; "remind me to call Sam tomorrow at 9" makes no reminder (CHAT_PLAN foundation 7). (from deepen-b-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, no-model Chat answers wrong for arithmetic, units and dates; open]
- The agent panel with no model: 16 of 20 controls disabled (AGENT_SKILLS_REFORM, Deepened row 1). (from deepen-b-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, 16 of 20 agent controls disabled with no model; open]
- Ask cannot show a relevant map as a map. Decision taken: retrieval is notes only (a map's entry text is its title, so it grounds nothing). Owner's words: "mindmaps still appear as notes in the ask subtab search". To surface maps, add a `maps` list to `ChatResponse` (`src/memorymap/api/routes_chat.py:673`) and draw it with `mapChip` in `frontend/js/capture-ask.js` (the `raw_results` loop near line 2296), fed by `search.engine` hits of kind `map`. (from mapnotes-1010.md) (checked 2026-11-09) [verified 2026-11-10: stale, decision taken: retrieval is notes only; recorded as decided]
- Notes keep the old `updated_at` rule (any write moves it): `edited_at` answers "when a person changed it", but `lexical_filing` (`src/memorymap/ai/lexical_filing.py:554`) keys stamps on `updated_at`, so the board-only guard in `core/database.py` was not widened. (from mapnotes-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, updated_at still moves on any write; edited_at not used for the rule]
- Each VC row is unbuilt; the script and test are the only code (Brief 75 says no code beyond them). (from vendor-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, VC rows unbuilt; script and test only]
- The p5 API list in `scratchpad/vendor_use.py` is a Chromium dump pinned to 1.9.4 (the vendored p5 is 1.11.13 since 2026-10-11, not yet regenerated); regenerate it with a p5 upgrade. (from vendor-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, p5 API list pinned to 1.9.4 while vendored p5 is 1.11.13]
- Brief 2 (consistency lints): HISTORY mentions it only as an owner reference; no record of the lint set being built as the brief. (from briefs-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, Brief 2 lint set not recorded as built]
- Brief 3 (prefs, api.stream/upload, innerHTML): HISTORY line 43146 area still lists `api.stream`/`api.upload` and the no-bare-fetch lint as not built. (from briefs-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, api.stream and api.upload exist in app.js and settings.js; Brief 3 list still open]
- Brief 4 (Settings two-pane, 54 paragraphs): WORLD_CLASS_PLAN.md:1019 says the 54 paragraphs "not re-checked here, so still open". (from briefs-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, Settings two-pane 54 paragraphs not re-checked per WORLD_CLASS_PLAN]
- Brief 8 (`[[` autocomplete, connections rail): HISTORY has only the plan table rows, no Built record. (from briefs-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, Brief 8 has no Built record in HISTORY]
- Brief 9 (job runtime): `tests/test_jobs.py` the brief names does not exist; HISTORY has no Built record. (from briefs-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, tests/test_jobs.py named by the brief is absent; no Built record]
- Brief 13 (verifier): agent-remaining/OPEN.md:189 still names Brief 13's `evals` marker and fixture set as open. (from briefs-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, evals marker still listed as open; no evals marker found in tests]
- Brief 14 (docs condensed): HANDOVER.md is 486 lines against a 300-line done-when; `NEXT_FABLE_WINDOW.md` does not exist. (from briefs-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, HANDOVER.md over the 300-line done-when; NEXT_FABLE_WINDOW.md absent]
- Brief 16 (documentation refined): no HISTORY record of the pass. (from briefs-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, no HISTORY record of the documentation pass]
- Brief 17 (launchers, splash): agent-remaining/OPEN.md:405 names the rest of Brief 17 as open. (from briefs-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, rest of Brief 17 still named open in agent-remaining]
- Brief 18 (the complete open scope): an umbrella brief, only section A recorded in HISTORY. (from briefs-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, umbrella brief, only section A recorded]
- Briefs 25 to 31 (group): each plan phase list is still open; "nothing is built" for 25. (from briefs-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, plan phase lists for Briefs 25 to 31 still open]
- Brief 32 (templates and base layouts): deferred by the owner; BACKLOG 4b carries the standing row. (from briefs-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, deferred by the owner; BACKLOG row carries it]
- Brief 33 (rest of WORLD_CLASS_PLAN): HANDOVER.md:450 names it as the next brief. (from briefs-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, HANDOVER names Brief 33 as next]
- 745 (d): the hover-only tour step reveal is built nowhere (tour.js has no hover handling). (from coverage-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, hover-only tour step reveal not in tour.js]

## Left by the a11yfix and filing agents (merged 2026-10-10)

Both files are in [`../archive/agent-remaining/`](../archive/agent-remaining). The filing numbers (top-1 0.417 without a model against decision 8's 0.8, 0.808 with the embedder) are in the archived file; decision 6's scope ruling is INBOX 770 (taken); torch and sentence-transformers were removed from the shared venv.

- design-1010 row 5, 110 controls with no focus change (`a11yname.js` focus pass): Brief 57, decision 15. (from a11yfix-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, 110 controls with no focus change; Brief 57 open]
- The boot CSS cap (`tests/test_boot_budget.py`, 183,300) had 3 bytes of room; this work spent it with blank-line collapses in `00-tokens-shell.css` and `01-forms-settings.css`. The next CSS addition needs a lazy file or a cap-lowering trim first. (from a11yfix-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, boot CSS cap headroom at 3 bytes; blank-line collapses noted]
- `app.js` is within 14 bytes of its ratchet (`tests/test_static_compression.py`, 14,300): `makeUnlinkAccessible` moved out to `note-cards.js` to stay under it. (from a11yfix-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, app.js within 14 bytes of its ratchet; makeUnlinkAccessible moved to note-cards.js]
- Row 4 measured on a seeded notebook (13 notes), not the report's: title-only icon controls in the Notes list 54 to 0 at 1440, 21 to 0 at 390. Other title-only icon buttons built outside the Notes list (other tabs, Settings) were not counted. (from a11yfix-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, row 4 icon control counts measured on a 13-note seed, not the report's]
- Not measured: dark theme for axe `target-size` and `scrollable-region-focusable`; the 1024 width. (from a11yfix-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, dark theme axe checks and 1024 width not measured]
- **Built 2026-11-11: the owner moved the bar to 0.6 (0.625 filed outright, test passes) and asked for "ask when unsure" (built, off by default).** Decision 8's bar, "below 0.8 top-1 without a model the step is not done": 0.417 (`tests/test_filing_accuracy.py`, strict xfail). Forced to choose, the evidence is right 0.61; 39 of 120 notes name no pack phrase ("dal", "boiler", "episode", "MOT", "nursery"). Recommendation: an everyday vocabulary supplement beside the pack, reviewed by the owner (a pack migration, so the owner's call), measured on a second fixture written after it. (from filing-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, filing top-1 0.417 under strict xfail in test_filing_accuracy.py]
- Decision 6 says "the pack's flag": the pack has none. The 49 sensitive topics are MemoryMap's own list in `src/memorymap/ai/data/taxonomy/memorymap_filing.json`. (from filing-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, pack has no flag; sensitive topics are the app's own list]
- The data path: section 23 says `src/memorymap/ai/data/taxonomy/`, section 26 decision 56 says `src/memorymap/data/`; section 23's was followed. (from filing-1010.md) (checked 2026-11-09) [verified 2026-11-10: stale, taxonomy path in section 23 no longer exists; package now src/tessellate]
- Decision 4, "alternate names come from the pack's labels and the person's own titles": only the pack's labels (`entry/tidy.py` `_rows_category_names`). (from filing-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, alternate names use pack labels only in tidy.py _rows_category_names]
- Decision 4's centroid test needs the search model; with it off the merge review uses topics alone at 0.8 and says so in the row (`tidy.MERGE_TOPIC_OVERLAP_ALONE`). (from filing-1010.md) (checked 2026-11-09) [verified 2026-11-10: stale, MERGE_TOPIC_OVERLAP_ALONE not in repo; the rule it names is gone]
- The lexicon (decision 7) costs one note in the online simulation (0.521 to 0.510, `scratchpad/filing-tools/online.py`); the fixture has no category named for a topic another holds, so the case it is for ("Work, not Software") is only in `tests/test_tidy_categories.py`. (from filing-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, lexicon costs one note in the online simulation; open decision]
- Decision 9 (the 30 context rules, 50 acceptance fixtures): not started; `taxonomy.context_rules()` and `tests/fixtures/taxonomy/context_acceptance_fixtures.json` are in place. (from filing-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, decision 9 context rules not started; taxonomy.context_rules absent]
- Cost: `decide` is 34 ms a call at 5,000 synthetic notes against 8 to 17 ms for the old tally (`scratchpad/filing-tools/perf.py`); Tidy's uncategorised review calls it once a note. (from filing-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, decide cost 34 ms at 5,000 notes; perf.py absent, measurement open]
- The tag picker on an empty field puts the tags the note says first ("training 10 notes, in this note"), but on a note that says none of them it still lists every tag by use (`frontend/js/tag-suggest.js` `fillTagSuggest`): a completion list, not a suggestion, so left. (from filing-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, tag picker lists tags the note does not say; tag-suggest.js]
- The model's tag reply is grounded against a faked reply (`tests/test_tag_grounding.py`); what a real small model answers is not verified. (from filing-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, tag grounding tested against a fake reply only]
- Graph topics as categories ("How are they different from categories??", the graph agent's hand-off in `archive/agent-remaining/graph-1010.md`): not in section 23's steps, so not done. (from filing-1010.md) (checked 2026-11-09) [verified 2026-11-10: true, graph topics as categories not built]

## Left by the notice agent (INBOX 767, merged 2026-10-10)

The no-model notice is one row on the `.notice` recipe on all five surfaces (46.8px at 1440, two rows only under 600px); its 58 gzipped bytes were paid for by the blank lines of 08-consistency.css, so the boot CSS cap stands at 183,300 and the next CSS goes in a lazy file.

- Row height at 1440 is 46.8px, not "one line plus padding" (about 38px): the Connect button's 28.8px target floor sets the row. Left as is; shrinking it would break the touch-target lint. (from notice-1010.md) (checked 2026-11-09) [verified 2026-11-10: stale, row height left as is by decision (Connect target floor)]
- The palette is never shown on a phone (`toggleAgentPalette` goes to Chat), so its 390px notice is unmeasured by design. (from notice-1010.md) (checked 2026-11-09) [verified 2026-11-10: stale, palette never shown on phone by design; unmeasured by design]

## Left by the engine agent (Brief 39, CHAT_PLAN Phase 6, merged 2026-10-10)

The file is in [`../archive/agent-remaining/engine-1010.md`](../archive/agent-remaining/engine-1010.md); its numbers are in the merge commit.

- Blind panel (decision 40): the owner's rating against the 1 to 3B model; not runnable by an agent. (checked 2026-11-09) [verified 2026-11-10: true, blind panel rating needs a person; not runnable by an agent]
- P10 days until a note's date ("how many days until the dentist"): `utilities.until_subject` (src/memorymap/ai/utilities.py:313) finds the subject; compose does not yet look the date up in the notes. (checked 2026-11-09) [verified 2026-11-10: true, P10 days-until subject found by utilities.until_subject; open]
- P12 a list filtered by category or tag ("list my work notes"): `composer._filtered` (src/memorymap/ai/composer.py:3155) filters by tag and source kind, not by category. (checked 2026-11-09) [verified 2026-11-10: true, composer filtering by category or tag not built; _filtered not found]
- P15 a lead-in chosen after the parts: the compare opener is still chosen first. (checked 2026-11-09) [verified 2026-11-10: true, compare opener still chosen first]
- P16 a note's open checklist items for "what is still open on X". (checked 2026-11-09) [verified 2026-11-10: true, open checklist items for 'what is still open on X' not built]
- Decision 45: the readings are listed (`composer._readings`, src/memorymap/ai/composer.py:2693); a running model does not yet pick among them (needs a real model; `pytest -m evals`). (checked 2026-11-09) [verified 2026-11-10: true, readings listed but no model picks among them; _readings not found by name]
- Decision 43: the currency table is dated (`utilities.RATES_DATE`, src/memorymap/ai/utilities.py:113) but has no Settings editor. (checked 2026-11-09) [verified 2026-11-10: true, currency table has no Settings editor]
- Captions: the composer reads them as note content; keyword search finds them as the picture's own row (src/memorymap/search/index.py:793), not as its note's. (checked 2026-11-09) [verified 2026-11-10: true, captions read as note content in composer; keyword search row]
- Dates like 3/4 read day first (`when._date_phrase`, src/memorymap/ai/when.py:420); no locale order. (checked 2026-11-09) [verified 2026-11-10: true, dates like 3/4 read day first; no locale order]
- Not seen in a browser: the web sources list with a real search engine; contrast sweeps over `.said` and the act card. (checked 2026-11-09) [verified 2026-11-10: true, web sources list and contrast sweeps not seen in browser]
- Polarity in the fact layer: dropped by decision 30's own condition (no feature uses it). (checked 2026-11-09) [verified 2026-11-10: stale, polarity dropped by decision 30's own condition]

## Left by the chatui agent (the owner's 2026-10-10 chat and first-run list, merged 2026-10-10)

The file is in [`../archive/agent-remaining/chatui-1010.md`](../archive/agent-remaining/chatui-1010.md).

- Item 32, "metadata ... very messy": the chat answer's foot is still three rows (Sources, Grounded in, meta), 148 px measured on a five-source answer; fold Grounded in and meta into one muted line (chat-agent.js:2275, the sources block). The head label and the result-card reason are done. (checked 2026-11-09) [verified 2026-11-10: true, chat answer foot still three rows, 148 px on five sources]
- INBOX 694 part 1, "the bottom of these pills gets cut off": not reproduced at DPR 1 (Ask|Agent and Settings `.seg`: each segment 1 px inside the 32 px track top and bottom); the Pace pill is drawn in skills.js:462 (outside this agent's files) and was not measured; try DPR 1.25 and dark. (checked 2026-11-09) [verified 2026-11-10: true, INBOX 694 pill cut-off not reproduced at DPR 1; open]
- INBOX 731, "the help guide failed??": with a model only; no model answers (help-chat.js:329 is the catch). Needs the server log line from a model run. (checked 2026-11-09) [verified 2026-11-10: true, Guide failure with a model; help-chat.js:329 catch, log line needed]
- INBOX 742 and 743, "atlas doesnt seem to change emotions alot", "more mouse interaction ... rubbing its head. flipping it upside down": gestures, moods from app events, the enlarged view mirroring live state. Not started. (checked 2026-11-09) [verified 2026-11-10: true, atlas emotions and gestures open]
- INBOX 744 (b) and (c), "it didn mention other matching records": composer and grounding work (composer*.py, renderAnswerGrounding), off this agent's list. (checked 2026-11-09) [verified 2026-11-10: true, INBOX 744 composer and grounding work open]
- Start SearXNG "takes a while": not reproduced (status 21 to 101 ms, chat.js:1031 `setWebSearxngRunning`); a search that failed should retry by itself once the engine answers. (checked 2026-11-09) [verified 2026-11-10: true, not reproduced (status 21 to 101 ms); retry-on-failure note still open]
- Web link cards in chat and the web reader share no recipe with markdown.js:1258 `linkCard`; one recipe for both. (checked 2026-11-09) [verified 2026-11-10: true, linkCard in markdown.js; web cards share no recipe with it]
- Citation hover, the composer and captions in retrieval (Brief 39) and the density items (Brief 41) are owned elsewhere. (checked 2026-11-09) [verified 2026-11-10: stale, pointer only; the work is owned by Briefs 39 and 41]

## Left by the trust73 agent (Brief 73, rules 4, 5 and 14, merged 2026-10-10)

The file is in [`../archive/agent-remaining/trust73-1010.md`](../archive/agent-remaining/trust73-1010.md).

- Rule 4 "says what happened, why": 24 literal error toasts still fall back to Open the logs rather than an action of their own (`tests/test_error_toasts.py` LOGS_ACTION_CAP 24): chat-attach.js 2548/2768/2956, library.js bulk failures (1846, 1892, 3360, 9967, 10106) and 4671, settings.js 3463/3508/3527, whiteboard.js 8335/8351/10359/14697, shell-reminders.js 1135/1143, settings-controls.js 320/393, update-dialogs.js 216, lightbox-view.js 753, note-properties.js 44, documents-code.js 1499. Each wants a Try again bound to its own function, and a why where "Couldn't X." has none. (checked 2026-11-09) [verified 2026-11-10: true, 24 literal error toasts still fall back to Open the logs]
- Rule 4: the 338 `toast(e.message, true)` calls get the why from `plainHttpError` and the default Open the logs; a per-site retry is not built. (checked 2026-11-09) [verified 2026-11-10: true, toast(e.message, true) sites use plainHttpError; per-site retry not built]
- Rule 5 "a long-running task that does not register fails": the lint is a table of thread sites (`tests/test_activity.py` THREAD_SITES); request-bound long work outside the four streams, transcription and picture reading (a document import, a meeting summary, the jobs pool's model lane rows) registers only through `collect()` or not at all; `core/activity.track` is the one line to add. (checked 2026-11-09) [verified 2026-11-10: true, THREAD_SITES lint in test_activity.py; request-bound tasks not covered]
- Rule 5: a stopped answer ends its stream without a `done` line; how Chat, the Guide and the documents panel render that end is not verified in the page. (checked 2026-11-09) [verified 2026-11-10: true, stopped-answer end rendering not verified in page; done line fix noted in the top list]
- Rule 5: "the managed runner killed" has nothing to act on: the app starts no model runner (extras.py says llama-server is run by hand), so an OpenAI-compatible backend answers that it keeps its own model. (checked 2026-11-09) [verified 2026-11-10: true, managed runner killed message has no runner to act on]
- Rule 14: `/health` stays the launcher's open probe (instance_lock.py, __main__.py read it unauthenticated, and it answers on the LAN); the fields are on the signed-in `GET /debug/health` under `trust`. Moving them onto `/health` needs the owner's yes. (checked 2026-11-09) [verified 2026-11-10: true, /health stays the launcher probe, unauthenticated on the LAN]
- Rule 14: the Health block stays in Settings, About (where it was built, PLAN B9) rather than its own section; reach is the palette's Health (1) and Settings, About (2). (checked 2026-11-09) [verified 2026-11-10: true, Health block stays in About by decision; reach note open]
- Not verified: Ollama's real `keep_alive: 0` and `/api/ps` (a slow fake in the agent's scratch dir stood in), the desktop window, WebKit. (checked 2026-11-09) [verified 2026-11-10: true, Ollama keep_alive and /api/ps not verified against the real server]

## Left by the docs42 and docs42b agents (Brief 42, INBOX 736, merged 2026-10-10)

The files, with the measured before table and the vendoring keep-or-drop table, are in [`../archive/agent-remaining/docs42-1010.md`](../archive/agent-remaining/docs42-1010.md) and [`docs42b-1010.md`](../archive/agent-remaining/docs42b-1010.md); what docs42b built is in HISTORY "Moved from the plans, 2026-10-10 (DOCUMENTS Brief 42 remainder)".

- Document comments with the board's thread shape (Reply, Edit, Resolve, Attach): a decision first. Comments are `==words== %%remark%%` in the text ("no comment store and there must not be one", documents.js `renderDocComments`) while `wbCommentRow` needs ids, `reply_to`, `edited`, `resolved`. Recommendation (take it): keep the text model; a reply is the next `%%…%%` on the same line, Edit rewrites in place, Attach appends a `[[link]]`, Resolve takes it out; lift `wbCommentRow`'s DOM into a shared row taking `{list, save, refresh}` and add the recipe ratchet in `tests/test_ui_recipes.py`. [docs42b] (checked 2026-11-09) [verified 2026-11-10: true, document comments not on the board thread shape; a decision is needed]
- Word import of tracked changes: the .docx carries `w:ins`/`w:del`, but Mammoth reads an insertion as accepted text and drops a deletion (documents-word.js `docWordImport`); the server reader `docview.docx_to_markdown` keeps them, so a .docx with revisions could go there. [docs42b] (checked 2026-11-09) [verified 2026-11-10: true, w:ins and w:del not read as tracked changes in documents-word.js]
- A fenced code block's language (```js) is not written to Word, so it comes back as a bare fence (`docWordBlocks`, the `pre` branch); header cells come back bold (as before). [docs42b] (checked 2026-11-09) [verified 2026-11-10: true, code block language lost on Word export]
- .diff, .patch, .vb and .vbs are not in `docview.CODE_SUFFIXES`, so a Library import of one is refused (415); a Dockerfile has no suffix at all (core/docview.py, with the chat picker's `accept` list `tests/test_docview.py` pins). Bug. [docs42b] (checked 2026-11-09) [verified 2026-11-10: true, .diff .patch .vb .vbs not in docview.CODE_SUFFIXES; Dockerfile has no suffix]
- The output grip is 24 px (the grip recipe), under touch.js's 44 px floor at 390; touch.js does not list the run panel as a surface. [docs42b] (checked 2026-11-09) [verified 2026-11-10: true, output grip 24px under touch floor at 390]
- js-beautify on a selection is not used (a selection keeps the conservative re-indent); `vendor_use.py` reports "selection" as its one unused capability. [docs42b] (checked 2026-11-09) [verified 2026-11-10: true, js-beautify on a selection not used; vendor_use reports one unused capability]
- Brief 42's other items not started: highlights on pages, comments with bookmarks and links, link cards with a viewer, the long-form preference at first run, labelled sections with a local graph (a Phase row first), doctype.js under 30 ms. [docs42] (checked 2026-11-09) [verified 2026-11-10: true, Brief 42 items not started (highlights, comment bookmarks, link cards)]
- Not verified: the .docx opened in Word itself (its XML and Mammoth's reading only); Format on a large real file; the list chords on a non-US layout; the docx extra's removal on an install that has python-docx (it stops being listed). [docs42b] (checked 2026-11-09) [verified 2026-11-10: true, .docx in Word, large file Format and non-US chords not verified]

## Left by the trust agent (Brief 74, T0 sweeps for 72a, 72b and 73, merged 2026-10-10)

The file, with the T0 table, is in [`../archive/agent-remaining/trust-1010.md`](../archive/agent-remaining/trust-1010.md); the plan's pointer is WORLD_CLASS_PLAN 28.6.

- Settings, every switch and choice: 13 pressed, 0 undone by Ctrl+Z (`settings-controls.js` has the only `pushUndo`; 48 write functions in `settings*.js` and `prefs.js`, 3 with an undo path). (checked 2026-11-09) [verified 2026-11-10: true, 13 Settings controls pressed, none undone; only settings-controls.js has pushUndo]
- Documents: "Delete" shows a toast Undo, but Ctrl+Z goes to the open editor's history (`surfaceHistory` in `status.js`, the Documents branch) so the deleted document stays deleted; "Archive" and "Start a new document" push nothing (21 write functions, 5 with an undo path). (checked 2026-11-09) [verified 2026-11-10: true, Documents delete Undo toast does not reach Ctrl+Z; surfaceHistory in status.js]
- Mind map "Add a top-level topic": the board stack grows by one, Ctrl+Z leaves the lists differing (`/whiteboard/` state not equal to before); unverified which list. (checked 2026-11-09) [verified 2026-11-10: true, mind map add top-level topic: Ctrl+Z leaves lists differing]
- Chat "Save this chat as a document": creates a document, no undo (`chat.js`; 28 write functions, 7 with an undo path). (checked 2026-11-09) [verified 2026-11-10: true, Save this chat as a document has no undo in chat.js]
- Whiteboard 43 write functions, 14 with an undo path; mind map 25 and 7; graph 21 and 9; library 30 and 9; dashboard 9 and 1; timeline 5 and 1 (`measure-writes.py --list SURFACE` names the gaps). (checked 2026-11-09) [verified 2026-11-10: true, write functions with undo paths counted per surface; most still lack one]
- Not reached by the sweep: right-click menus, keyboard-only acts (Tab for a branch), controls that open a picker and then need a second choice (note "Move to another category", "Add tags"), and library delete (all 14 pressed in the library were views or pickers). The 25 pressed actions are a floor on what is exposed, not the whole surface; `measure-writes.py` is the full-coverage count. (checked 2026-11-09) [verified 2026-11-10: true, right-click, keyboard-only acts and second-choice pickers not reached by sweep]
- Documents were not probed in the dark run (the list had not loaded when the sweep opened it), and the mind map "Add a top-level topic" undid in one light run and not another: re-run both before quoting them. (checked 2026-11-09) [verified 2026-11-10: true, Documents not probed in dark run; undo in one light run only]
- `#wb-tool-group span.wb-tool-section-label`: text 49 to 56px past its box at 820, 1024 and 1440 on the whiteboard and the mind map (36 nodes counted as overflow and as clipped text). (checked 2026-11-09) [verified 2026-11-10: true, wb-tool-section-label text 49 to 56px past its box at 820 to 1440]
- `#entry-list div.entry-meta.note-meta`: 64 to 72px wider than its card at 320 and 390 (one per note, 33 to 42 nodes); `#entry-list li` 24 to 48px at 320. (checked 2026-11-09) [verified 2026-11-10: true, entry-meta 64 to 72px wider than its card at 320 and 390]
- `#select-btn span.dock-word` 40px and `#notes-filter-menu span.dock-word` 32px clipped at 320 to 1024: the labelled-to-icon collapse hides words by clipping instead of removing them (may be intended; if so the rule needs the exception written down). (checked 2026-11-09) [verified 2026-11-10: true, dock-word labels clipped at 320 to 1024 in two selects]
- `button#notes-tidy.ghost.small` 4px at every width; `#tab-notes div.layout` 4px at 320 to 1024. (checked 2026-11-09) [verified 2026-11-10: true, notes-tidy 4px and tab-notes layout 4px at 320 to 1024 per sweep]
- Dashboard: 3 overflow and 1 clipped text at 320 and 390, 2 overflow at 820 and wider (selectors in the sweep output, not yet named here). (checked 2026-11-09) [verified 2026-11-10: true, Dashboard overflow and clipped text at 320 to 820; selectors not named]
- Docks: 0 sibling intersections in 12 surfaces at 5 widths (at 390: 81 bars and 266 sibling pairs examined), so the dock grammar holds; the counts that fail are text and content boxes. (checked 2026-11-09) [verified 2026-11-10: stale, dock grammar holds: 0 sibling intersections across 12 surfaces]
- Counts scale with the number of seeded notes (the notes list repeats one finding per card): the table in 28.4 was taken on 13 to 23 notes. (checked 2026-11-09) [verified 2026-11-10: true, counts scale with seeded notes; 28.4 table taken on 13 to 23 notes]
- Crawl: 55 destinations found from the dashboard (1, 14, 36, 3 and 1 at depths 0 to 4, crawl complete to depth 4), 1 deeper than 3, 16 with no palette command (of 80 commands); dark: 55 destinations, 1 deeper than 3, 14 without a command. (checked 2026-11-09) [verified 2026-11-10: true, crawl found 55 destinations; 1 deeper than 3 and 16 without palette commands]
- Palette rows missing (heuristic word match, the destination and its click path): 1  Notifications: # unread (muted except reminders); 1  Atlas files it for you; 1  Draw, then keep it as a note; 2  Chat > About this chat; 2  Chat > Search everything and jump anywhere (Ctrl+K); 2  Library > Boards & maps; 2  Library > Bookmarks; 2  Library > Contents; 2  Settings > Search and index; 2  Settings > What it learned; 2  Settings > Web search; 2  Atlas files it for you > Manage categories; 2  Answered from your notes > About the Use AI switch; 3  Notes > Writing room > Write from notes you already have, up to six of; 3  Library > Contents > Probe documentDocument·# sections·#h ago; 3  Atlas files it for you > Manage categories > About managing categories. (checked 2026-11-09) [verified 2026-11-10: true, palette rows missing for Notifications and Atlas files, per crawl]
- Deeper than 3 (light): 4  Library > Contents > Probe documentDocument·# sections·#h ago > Outline. (checked 2026-11-09) [verified 2026-11-10: true, deeper-than-3 destination list open]
- The crawl presses navigation-looking controls only and one item of each repeated list; a destination absent from it is "not found by the crawl", not proof it is missing. Sub-tabs on one page share candidates, so a button seen on the first sub-tab is not pressed again on the others. (checked 2026-11-09) [verified 2026-11-10: true, crawl is not proof of absence; caveat stands]

## Left by the F1 and F2 agents (Briefs 65 and 66, the one reader and quick add, merged 2026-10-10)

- `ai/composer.py` `_DATE_CUE` (about line 380) and its second date pattern (about 933) still compile date words; replace with `recognise.recognise(...)` spans when Brief 67 makes chat a client of the reading, then empty `STILL_READING` in `tests/test_one_reader.py`. [f1-1010] (checked 2026-11-09) [verified 2026-11-10: true, composer.py _DATE_CUE and second date pattern still compile date words]
- `entry/timewords.py` keeps its own weekday and number tables (the plan's second allowed reader, for stored precision). Brief 68 decides whether `find` becomes `recognise` spans plus a precision map. [f1-1010] (checked 2026-11-09) [verified 2026-11-10: true, entry/timewords.py keeps its own weekday and number tables; Brief 68 decision open]
- `ai/factgraph.py` `_QUANTITY` still reads counts of things ("3 sets", "5 people"); a "count" kind (number plus plural noun) in `recognise` would let it delegate. [f1-1010] (checked 2026-11-09) [verified 2026-11-10: true, factgraph _QUANTITY reads counts without a count kind in recognise]
- `search/query.py` `before:`/`after:` stay ISO only (`test_an_unreadable_date_invents_nothing` holds it); `before:tuesday` is one call to `recognise.span` if the owner wants it. [f1-1010] (checked 2026-11-09) [verified 2026-11-10: true, search before and after stay ISO only; recognise.span not used]
- "last week" is the last seven days in search and the previous Monday to Sunday in `recognise`; both written down, the Reading says the search's window. An owner decision if one meaning is wanted. [f1-1010] (also: Left by the f4 agent (Brief 68, CHAT_PLAN F4, merged 2026-10-10)) (checked 2026-11-09) [verified 2026-11-10: true, last week differs between search and recognise; Q24 not applied]
- `when.resolve("in march")`, "march", "q4" give the next one at 09:00 (a reminder is never in the past); the past one comes from `when.window` and `recognise`. By design. [f1-1010] (checked 2026-11-09) [verified 2026-11-10: true, when.resolve gives next March at 09:00; past form via when.window]
- "on my birthday" reads only with a stored birthday (`context["birthday"]`, `birthday=` on `/read`); no setting holds one yet. [f1-1010] (checked 2026-11-09) [verified 2026-11-10: true, on my birthday needs a stored birthday; no setting holds one]
- Quick add is 56 of 60 on `tests/fixtures/composer/quickadd_1010.json` measured before F1's four fixes landed; re-run `scratchpad/ui-sweeps/quickadd.js` on this head and move CHAT_PLAN F2's Built block to HISTORY only at 60 of 60 (decision 50's gate). [f2-1010] (checked 2026-11-09) [verified 2026-11-10: true, quick add 56 of 60 measured before F1 fixes; re-run open]
- `ai/reading.py` reads "review budget friday" (reminder surface) as sure at 09:00 while quickadd.js asks "What time on ...?" (decision 50); the reading should ask the same question. [f2-1010] (checked 2026-11-09) [verified 2026-11-10: true, reading.py treats 'review budget friday' as sure at 09:00 while quickadd asks the time]
- Quick note: a reminder chip on a note saved while the server is away (the outbox, `saveQuickNote`'s `result.queued` branch) is dropped; the note is kept. [f2-1010] (checked 2026-11-09) [verified 2026-11-10: true, saveQuickNote queued branch drops the reminder chip; capture-card.js result.queued]
- Palette: only the reminder act has a row (`quickAddPaletteRow`); a note or meeting act and the search window chip (CHAT_PLAN section 1 row 7) wait for Brief 67's act registry. [f2-1010] (checked 2026-11-09) [verified 2026-11-10: true, quickAddPaletteRow only for the reminder act; other acts and search chip not built]
- Not verified by either: a real model's path; a screen reader toggling a chip; a browser locale other than en-US; the full suite. [f1-1010, f2-1010] (checked 2026-11-09) [verified 2026-11-10: true, real-model path, screen reader and locale checks not run]

## Left by the F3 agent (Brief 67, the validators and the acts, merged 2026-10-10)

- Palette rows from the registry: `acts.palette_rows` (src/memorymap/ai/acts.py) has no caller and `palette.js` still lists its own starters; a route and the palette drawing them (decision 53; Brief 68 row 7). [f3-1010] (checked 2026-11-09) [verified 2026-11-10: true, acts.palette_rows has no caller; palette.js keeps its own starters]
- A model's proposed act through the registry: `acts.propose` is tested but nothing calls it; the agent's write tools keep their own confirm path (`agent.py`). Brief 68 row 8. [f3-1010] (checked 2026-11-09) [verified 2026-11-10: true, acts.propose tested but no caller; agent write tools keep own confirm path]
- A reminder with no time said is guessed as tomorrow at 9, shown "(no time was said)" (`commands.py`, `when.resolve("tomorrow")`); decisions 48 and 50 say ask once. `acts.missing` and `validate.slots_missing` are in place; the reader fills the slot first. [f3-1010] (checked 2026-11-09) [verified 2026-11-10: true, reminder with no time guessed as 9am tomorrow; decisions 48 and 50 open]
- Ask draws no Confirm and Not right: `capture-ask.js` keeps `onGrounding`'s insights unread though the route sends them (decision 60 lists chat, Tidy and the dashboard; Ask is optional). [f3-1010] (checked 2026-11-09) [verified 2026-11-10: true, capture-ask.js onGrounding insights unread; Confirm and Not right not drawn]
- The 390 px layout of the Tidy Patterns rows and the Chat pattern line is not measured (1440: Tidy row buttons 32 px, no overflow; Chat line 55 px). [f3-1010] (checked 2026-11-09) [verified 2026-11-10: true, 390 layout of Tidy Patterns rows not measured]
- "Grounded in" says 4 notes while the support chip says "3 of 3 from your notes" on "tell me about golf" (seen in a sweep screenshot, not investigated). [f3-1010] (checked 2026-11-09) [verified 2026-11-10: true, Grounded in says 4 notes while support chip says 3 of 3; not investigated]
- The decision 54 sum rule: "12 * 7 is 84." is read as its own "Read as" because it restates the question's sum; every other utility answer has a "Read as" line. [f3-1010] (checked 2026-11-09) [verified 2026-11-10: true, sum rule 'Read as' restatement is an open judgement on decision 54]
- Not verified: real-model answers through the validators (fake transport and the route test only); dark mode. [f3-1010] (checked 2026-11-09) [verified 2026-11-10: true, validators with real model not verified; dark mode not run]

## Left by the search agent (Brief 47, WORLD_CLASS 25a, merged 2026-10-10)

- A chat is one search row (the whole thread), so a hit opens the chat, not the turn that matched (`index._conversation_row`). [search-1010] (checked 2026-11-09) [verified 2026-11-10: true, chat is one search row; index._conversation_row not found by that name]
- `tag:` with words still filters after the keyword pass's 200 candidates (`engine.search`, the `wanted_tags` block), so a common word plus a rare tag can miss notes. [search-1010] (checked 2026-11-09) [verified 2026-11-10: true, tag filter runs after the 200-candidate keyword pass in engine.search]
- Brief 47's "the sidebar's search field routes here": the Notes sidebar has no search field; the no-match Search everything button and the saved-search rows are the routes built. [search-1010] (checked 2026-11-09) [verified 2026-11-10: true, Notes sidebar has no search field; Brief 47 routing claim open]
- Not verified: hybrid ranking cost at 5,000 notes with a real embedding model (keyword plus the fake backend only); the saved-search ⋯ menu opened in a browser; the phone's saved-search rows at 390 beyond the DOM count. [search-1010] (checked 2026-11-09) [verified 2026-11-10: true, hybrid ranking cost at 5,000 notes with a real embedding not measured]

## Left by the f4 agent (Brief 68, CHAT_PLAN F4, merged 2026-10-10)

- Note editor: offers on the Edit form are wired (`note-edit-panels.js` after `li.append(surface, ...)`) but measured only on the Capture composer; the Edit form's filing offer sets the hidden select and redraws the chip through its `change`, not seen in a sweep. [f4-1010] (checked 2026-11-09) [verified 2026-11-10: true, Edit form offers wired but measured only on Capture composer]
- Note editor: a sum only when written with `=` ("12 + 7 = 21"); a column of amounts with a "Total:" line is not checked (`ai/offers.py` `_SUM`). [f4-1010] (checked 2026-11-09) [verified 2026-11-10: true, _SUM in offers.py only sums lines written with =]
- Dashboard: the digest is in dashboard.js (a boot file, about 700 bytes gzipped); a lazy home would delay the first paint of the widget it opens. The model "refining" the digest (the plan's "with the model refining it when present") is not built: Atlas's week below it is the old stream, unchanged. [f4-1010] (checked 2026-11-09) [verified 2026-11-10: true, digest in dashboard.js boot file; lazy home open]
- Documents: the status bar shows characters, words and reading time; lines (`wc -l`) are counted by `textCounts` but shown nowhere. "find with the same windows" is the Library's Search documents box (`GET /documents?q=`); the editor's own Find bar is a substring find, unchanged. [f4-1010] (checked 2026-11-09) [verified 2026-11-10: true, textCounts lines count shown nowhere in the status bar]
- Board: board acts are off on a mind map (`wbPaletteActRow` returns null when `wbIsMap()`): a map's layout is its tidy, not a grid. Pasting a list as stickies or map topics was already built (`wbPasteText`, `wbMapPasteText`). [f4-1010] (checked 2026-11-09) [verified 2026-11-10: true, wbPaletteActRow returns null on a map; board acts off on mind maps]
- Library: a "boards" or "mind maps" filter resolves to `Entry.is_board` ids, but the Library's filter keeps note cards only (`library.js` `libraryPhrase`), so it shows nothing there; the Graph is notes only too. [f4-1010] (checked 2026-11-09) [verified 2026-11-10: true, Library boards and mind maps filter keeps note cards only (libraryPhrase)]
- Settings: the synonym groups and the filler list are a hand table (`filters.SETTING_WORDS`, `SETTING_FILLER`), measured on 10 phrases in the browser; no settings phrase fixture in tests. [f4-1010] (checked 2026-11-09) [verified 2026-11-10: true, SETTING_FILLER in filters.py; the setting word table is a hand list]
- Import: people and places are named in the summary only; they are not written as tags or entities (the save's own extraction runs as before). `recognise` reads a person only in some shapes ("with Ken", "Sam Carter"), not "serviced by Ken" or "Ken Adams serviced" (`ai/recognise.py` `_contact_cands`). [f4-1010] (checked 2026-11-09) [verified 2026-11-10: true, import people and places named in summary only; recognise path open]
- Agent: `propose_act` is offered in the reminder and tag tool groups only; whether a 1 to 3B model calls Calculate rather than computing is not verified (no model here). [f4-1010] (checked 2026-11-09) [verified 2026-11-10: true, propose_act offered in reminder and tag groups only; model choice unverified]
- Voice: 67 failure toasts in library.js, whiteboard.js and whiteboard-map.js moved; the other 112 JS files still hold their own strings, and only the failure shape is in the table (decision 55: surface by surface). One template toast left as written (`library.js` "Couldn't import “${file.name}”"). [f4-1010] (checked 2026-11-09) [verified 2026-11-10: true, 112 JS files still hold their own failure strings; 67 moved]
- Scorecard: the follow-up column needs decision 58's 200 spoken lines, which are not written; variety's minimum is 3 of 20 against the plan's target of 8. [f4-1010] (checked 2026-11-09) [verified 2026-11-10: true, scorecard follow-up column needs 200 spoken lines not written]
- Boot JS 582,371 to 583,240 bytes gzipped (+869: the digest, the Library and Graph filters, the palette rows, the voice table, `textCounts`; cap 588,400); boot CSS 183,286 to 183,286 (cap 183,300, 14 bytes left). New UI otherwise lives in the lazy quick add, library and graph bundles. [f4-1010] (checked 2026-11-09) [verified 2026-11-10: true, boot JS 583,240 bytes gzipped against 588,400 cap; figure open]

Swept on this head: errors.js 0 errors and 0 layout findings at 1440, 1024, 820 and 390 (1024 timed out once on a click under load, 0 on the rerun); touch.js 0 findings. Not verified: a real model's path (no `MEMORYMAP_EVALS_URL`); the agent palette at 390 (it did not open from `toggleAgentPalette` in the phone shell); a screen reader on the new chips; the full suite.

## Left by the companion agent (Brief 34, first round, merged 2026-10-10)

Taken up by the companion2 agent (Brief 34 continues, INBOX 772 and 773).

- Decision 7's "under 1 ms a minute" is not met by Atlas: its tail is a script-drawn path (atlas-life.js `atlasTailFrame`), 15 draws a second at rest, about 770 layouts a minute. Meeting it needs the tail on the compositor (a cached sprite strip, or CSS on layer roots), a drawing change. [companion-1010] (checked 2026-11-09) [verified 2026-11-10: true, Atlas tail is a script-drawn path at 15 draws a second; decision 7 not met]
- Atlas's faces do not read as different moods (sheet: atlas-sheet-*.png, 15 moods at 104, 28 and 20 px, both looks, light and dark): at 104 the face is about 12 px inside rings and tail, at 28 and 20 the moods are one face. Real mascot work changes eyes, brows and mouth boldly, with a mood cue (sweat drop, zZ, hearts, "!") that survives at 20 px. Likely the root of "I barely get to see atlas change expression" (atlas.js `atlasApply`). [companion-1010] (checked 2026-11-09) [verified 2026-11-10: true, Atlas moods do not read as different at 104 px per the sheet]
- Under the system's reduce-motion hint Atlas keeps its calm CSS loops (an earlier decision, 08-consistency.css:5056): 1,579 style recalcs a minute. Decision 7 says reduced motion keeps poses without loops; the owner should say which wins. The app's own Reduce setting was not measured. [companion-1010] (checked 2026-11-09) [verified 2026-11-10: true, reduce-motion hint keeps CSS loops; 1,579 recalcs a minute; decision open]
- Brief 34 second part (INBOX 752): snapping transitions per minute (60 Hz joint sampling), 12 distinct idle motions per ten minutes and reaction latency under 100 ms were not measured; the latency bar conflicts with the 1.5s reaction debounce the owner asked for ("atlas startles a lot"). [companion-1010] (checked 2026-11-09) [verified 2026-11-10: true, Brief 34 second part (INBOX 752) transitions and idle variety open]
- The owner's "arm movements ... permanently in a downward arc": the arm hold now changes on idle ticks (45%), but the arm angle range over a walk cycle and at rest was not measured (atlasarms.js has the probe). [companion-1010] (checked 2026-11-09) [verified 2026-11-10: true, arm angle over a walk cycle not measured; hold changes on idle ticks]
- Tail, rings, nebula and lower-body "subtle animations that are all cheap" (owner's list): not changed; they exist (atlas-life.js) and are the cost above. [companion-1010] (checked 2026-11-09) [verified 2026-11-10: true, tail, rings and nebula animations unchanged; cost noted]
- Face sheet (facesheet.js (removed 2026-10-12, recoverable from git history), 12 names, light): one silhouette, one outline, readable at 104; crowns spill 6 px past the card's top edge; the gaming controller reads as a black block at 104. [companion-1010] (checked 2026-11-09) [verified 2026-11-10: true, face sheet readability at 104 px open; facesheet.js removed, finding stands]

Not verified: Every "Done when" face site was read in code (`nameMark` goes through `characterRendererFor` first), not driven one by one this round. Context reactions (drowsy, sleep, headphones, glasses, nightcap, bell, offline, wave on focus) are present in avatars.js and were measured by earlier sweeps; not re-driven. Timings: other agents held the load at 6 to 10 on four cores; counts (layouts, recalcs) are load-free, milliseconds are not. A WebView2 or WebKitGTK window; a touch rub (mouse and pen only by design).

## Left by the pwa agent (Brief 50, WORLD_CLASS 25d, merged 2026-10-10)

- clip.html and capture.html keep unhashed `?v=<version>` stamps (static, not rewritten as index.html and offline.html are), so an edit inside one version can be served stale from the immutable HTTP cache there. [pwa-1010] (checked 2026-11-09) [verified 2026-11-10: true, clip.html and capture.html keep unhashed version stamps]
- Warm-load speed gain is inside the noise on a shared machine (466 to 570 ms against 613 to 672 ms) because stamped files were already `immutable` in the HTTP cache; the gain is offline-ability and a cache the browser cannot evict as easily. A quiet-machine A/B would settle it. [pwa-1010] (checked 2026-11-09) [verified 2026-11-10: true, warm-load gain inside noise on shared machine; open]

Not verified: a real install prompt (`beforeinstallprompt` was dispatched by hand in Chromium; no real Chrome install, no Edge, no Safari, no iPhone). The iPhone row (no event, "Share, then Add to Home Screen") is source-tested only. frontend/js/settings-wiring.js, `renderInstallRow`. the share target from a real phone share sheet. The query landing in Capture was driven in Chromium with the worker controlling the page (`/?share_title=...` fills `#entry-content` under the Notes tab); the installed-app path is untested. frontend/manifest.webmanifest `share_target` is GET. the desktop (pywebview) window's own cache with the worker; only Chromium was driven.

## Left by the measure60 agent (Brief 60, WORLD_CLASS 26.0 and 26a, merged 2026-10-10)

- The 68 broad excepts that log nothing and return a fallback (89 minus the 21 seeded) are not ratcheted; decide whether decision 57 means them. `tests/test_no_silent_except.py`. [measure60-1010] (checked 2026-11-09) [verified 2026-11-10: true, 68 silent broad excepts not ratcheted; decision 57 open]
- 49 routes need a test or removal (`tests/test_routes_named.py` SEED); several are reached by a loop over verbs, check before writing duplicates. [measure60-1010] (checked 2026-11-09) [verified 2026-11-10: true, 49 routes need a test or removal per SEED in test_routes_named.py]
- 5 foreign keys without a leading index (`entity_mentions` x2, `document_bookmarks` x2, `entry_bookmarks.bookmark_id`) and 64 filtered columns without one: needs a migration and an `EXPLAIN QUERY PLAN` at 5,000 notes first (26.4). [measure60-1010] (checked 2026-11-09) [verified 2026-11-10: true, 5 foreign keys without leading index and 64 filtered columns; entry_bookmarks.bookmark_id not found]
- Import cost 3.3 s against decision 56's 1.5 s: `ai.autonomous` pulls `ai.agent` (503 ms), `ai.help_chat` 271 ms, `api.routes_search` 226 ms. Brief 62. [measure60-1010] (checked 2026-11-09) [verified 2026-11-10: true, import cost 3.3 s against 1.5 s target; ai.autonomous pulls ai.agent]
- Graph at rest (1 to 10 long tasks) and the companion (4 to 6 at rest) are the two surfaces over the zero target (`frames.js` REST_BUDGET). [measure60-1010] (checked 2026-11-09) [verified 2026-11-10: true, graph and companion over the zero long-task target in frames.js]
- `frames.js` has no documents or notes-list surface; add one when DOCUMENTS Phase work lands. [measure60-1010] (checked 2026-11-09) [verified 2026-11-10: true, frames.js has no documents or notes-list surface]

Not verified: Frame figures are one machine at load 5 to 9 on four cores; re-run `frames.js` idle before fixing a budget. Resident memory was measured on an empty notebook; a populated one loads the model at warm-up. The 647 MB is torch 2.14 CPU with bge-small, first embed 6.6 s. Hot-route times are in-process with the thread pool bypassed; `_to_out` at 5,000 notes is an extrapolation. Untested-route match is by path literal in `tests/`; a path built by concatenation of more than a trailing slash is counted untested. The `recalcs` CDP counter equals frames on every surface including the control; not read as a finding.

## Left by the safety agent (Brief 51, WORLD_CLASS 25e, merged 2026-10-10)

- `editor.js:inlineAiUndo` (owner's list of six): the inline AI bar's Undo reverts a CodeMirror transaction on unsaved field text, which rule 1.8 gives to the editor's own history. Recommendation: move it to the lint's editor histories rather than the stack (a stack entry outlives the field it would write to). Needs the decision taken. [safety-1010] (checked 2026-11-09) [verified 2026-11-10: true, editor.js inlineAiUndo reverts a CodeMirror transaction on unsaved text; rule 1.8 open]
- `dashboard.js:undoActorFrom` / `activityUndoControl` (and their two helpers) and `note-history.js:undoSkillRun`: an undo of the AI's changes through `POST /events/undo`, which refuses the person's own changes ("Undo works on the AI's changes, not yours", routes_settings.py:1648), so there is no redo to give `pushUndo`. Needs a server redo (re-apply the reversed events) before they can fold. [safety-1010] (checked 2026-11-09) [verified 2026-11-10: true, activityUndoControl in dashboard.js and undoSkillRun in note-history.js open]
- The plan row names a "Versions" row; the note menu's existing row is "History" (versions plus every other event). Not renamed: a rename moves help in five places for no new reach. Recommendation: keep "History", record the decision. [safety-1010] (checked 2026-11-09) [verified 2026-11-10: stale, not renamed by decision; help impact recorded]
- A notice's `go: { settings, focus }` scrolls Settings to the control at 1440 (Back up now at y 499 of 900) but not at 390 (y 1527 of 900): the phone sheet does not scroll to `scrollToId` (settings.js:245). Shared by every notice that opens Settings. [safety-1010] (checked 2026-11-09) [verified 2026-11-10: true, go scrolls Settings at 1440 but not at 390 (y 1527 of 900); scrollToId in settings.js]
- No backup schedule "shown with the last success" (WORLD_CLASS 4018 row) beyond Settings, About, Health's last backup line. [safety-1010] (checked 2026-11-09) [verified 2026-11-10: true, backup schedule shown beyond Settings, About and Health not built]

Not verified: A real disk failure or power cut; damage was made by overwriting pages of a copy (three embeddings leaves: opens, notice shows; pages read by the start-up backfill: `DamagedNotebookError`). The desktop launcher's loading window showing the damaged-file words was not driven (only `startup_status.get_phase()` asserted). The e2e spec ran locally once (2.0 min); not in CI yet. Folds measured with direct calls to the real functions (`deleteCategoryFromPanel`, `chatDeleteUndo`, `undoImport`, `pushDraftUndo`) after an API setup, not by clicking through each surface's own menu.

## Left by the density agent (Brief 41, UI_MODERNISATION Phase 12, merged 2026-10-10)

- Step 5b, decision 6 (a primary calendar paired with the reminders): TIMELINE_PLAN section 9 (Phase 5, Brief 55); `renderReminderCalendar` (shell-reminders.js) stands until it goes (decision 19). [density-1010] (checked 2026-11-09) [verified 2026-11-10: true, primary calendar for reminders not built; renderReminderCalendar only in tests]
- Decision 8, indent guides: the active line is built (library-lazy.css `.cm-activeLineGutter`); indent markers are not in the vendored CodeMirror bundle (DOCUMENTS_PLAN 25 row 3, Brief 71's shell). [density-1010] (checked 2026-11-09) [verified 2026-11-10: true, indent markers not in vendored CodeMirror bundle; active line built]
- Decision 7: only note cards changed (category pill to a dot and a word); chat bubble metadata not measured (no conversation without a model) and library cards untouched. [density-1010] (checked 2026-11-09) [verified 2026-11-10: true, only note cards changed; chat bubble metadata not measured]
- Decision 1, panel padding 12 and sidebar gutter 8: not measured or moved; the Notes dock wraps to two rows at 1440 (86 px). [density-1010] (checked 2026-11-09) [verified 2026-11-10: true, panel padding and sidebar gutter not moved; Notes dock wraps at 1440]
- Decision 5 for a date field built after boot: the map topic's due date (whiteboard-map.js) stays native; the date picker's typed field sets the date only ("tomorrow at 3pm" does not move the time field). [density-1010] (checked 2026-11-09) [verified 2026-11-10: true, map topic due date stays native; typed date sync open]
- Sweeps: touch.js reports Settings appearance and privacy "did not open" (section names moved); overlap.js still counts 4 px rows on `#notes-tidy`, `#dash-quicklinks`, `.library-controls`. [density-1010] (checked 2026-11-09) [verified 2026-11-10: true, touch.js section names moved; overlap.js still counts 4 px rows]
- One focus ring at 1:1 in Chat (`button.active`, its outline takes the ground colour, both themes; `scratchpad/ui-sweeps/focusring.js`). Bug. [density-1010] (checked 2026-11-09) [verified 2026-11-10: true, focus ring at 1:1 in Chat button.active; bug, open]
- Not verified: tests elsewhere that relied on blank lines removed from CSS files 00, 01, 02, 05, 06, 07 and 10 to pay for the CSS budget; the picker on the Timeline range and Ask's as-of day beyond a smoke check; 390 beyond Reminders. [density-1010] (checked 2026-11-09) [verified 2026-11-10: true, tests relying on removed blank lines not verified]

## Left by the open-rows agent (time reader, 2026-10-17)

Closed (see HISTORY, "OPEN.md rows closed, 2026-10-17"): row 464 and the time-reader gaps found while probing. Still open, none built:

- `when.resolve("in 2 weeks at 3pm")` still reads 15:55 on the day: the clock after a day-sized offset is applied only in `reminder_parser.parse_relative` (`_with_clock`), not in `resolve`. A bare "at one" ("lunch at one") is deliberately unread, since "at one point" is as common; say so to the owner if it matters. (checked 2026-11-09) [verified 2026-11-10: true, in 2 weeks at 3pm reads 15:55 via reminder_parser parse_relative]
- A `before:tuesday` search operator is an owner decision (which side of the day it excludes). (checked 2026-11-09) [verified 2026-11-10: true, before:tuesday side of day is an owner decision]
- chat-agent.js result box budget line (row 243) is blocked by the eager-script gzip caps. (checked 2026-11-09) [verified 2026-11-10: true, chat-agent.js result budget line blocked by eager gzip caps]

## Left by the 0.6.01 bug-document pass (2026-10-22)

Source: the owner's "Tessellate bugs" document (34 screenshots). Fixed in the patch: tray start/log hardening, whiteboard drag-select highlighting, Fill/Border popup placement, skills menu tag. Not verified on a real Windows desktop: the tray icon (could be in the taskbar overflow ^ if it did start). Open, none built:

- Composer: aware of recent activity (what you were writing or viewing) with varied, kinder replies and a suggested next step; answers that stay on the question and differ per note in Ask; a length setting; personas off when no model is connected. (checked 2026-11-09) [verified 2026-11-10: true, composer awareness and kinder replies beyond composer2's first round; open]
- Composer: web search with SearXNG down gives only a failure line; a clarify-first flow for open asks ("open a note"); alternative actions by lexical and cosine similarity when nothing matches. (checked 2026-11-09) [verified 2026-11-10: true, SearXNG down gives only a failure line; clarify-first flow not built]
- Reminders magic add: "remind me to do my tax return when I get home tonight, probably around 7pm" must parse (task, tonight, about 7pm). Edit reminder buttons: equal heights and a gap. (checked 2026-11-09) [verified 2026-11-10: true, magic add with tonight and about 7pm not verified]
- Composer analysing pages in the web panel (key points, highlights, a linked section list). (checked 2026-11-09) [verified 2026-11-10: true, composer page analysis in the web panel not built]
- Whiteboard: frame contents stay rotated when the frame's rotate handle is double-clicked to reset; emojis do not scale with their box; the dimensions label is missing while resizing; anchors and selection borders lag a resize until release. (checked 2026-11-09) [verified 2026-11-10: true, frame contents stay rotated on reset; emoji scale open]
- Documents: hide Harper suggestions temporarily and a list of dismissed ones; checkboxes clickable in read mode, wider comfortable width in full screen; selection toolbar and meatball missing in full screen; highlight colour switching on already-highlighted text, and the highlight menu not closing on an outside click; slash menu closing on an outside click and removing its slash; line-number gutter too wide and wrapped lines not indented in the live view; table meatball overflow and far-off plus button; history popup redesign; layout at half width (top of full screen, Ask tab, notes more-actions button half off the edge, blank bar at the bottom, blank bar at the top of Settings, Models page). **Fixed 72806e6 (Models blank bar, focus-mode bottom band), 17ecb7c (notes more button, folds, suggestions wrap, Ask box), 9721d1e (docs dock one row at 600, companion touch-action), 083b948 (Ask header wraps in the card).** Not verified: companion drag in a browser (buddy absent from the sweep boot). (checked 2026-11-09) [verified 2026-11-10: true, Harper temporary hide and dismissed list open]
- Custom domain: **built 2026-11-11 (Settings, Address names; INSTALL says so).** (checked 2026-11-09) [verified 2026-11-10: true, custom domain documented for Docker only; not built]

## Carried from archived agent files, 2026-10-26

Open items from the agent files moved to `archive/agent-remaining/` on this date,
deduplicated against the ledger above.

- [aboutkit-1011.md] left: Restart now relaunches the app directly (/system/restart, Windows desktop only), not through start.bat, so a pending reinstall runs at the next launcher start; routing it through the launcher needs a Windows check (core/maintenance.py, routes_settings.py restart_app) (checked 2026-11-09) [verified 2026-11-10: true, Restart now relaunches directly, not through start.bat; open]
- [briefs-1011.md] found, not fixed: help-popovers.js fails 6 triggers it cannot click (#skill-tools-help, #skill-verify-help, #custom-css-help, #import-app-help), none touched here; test_background_registry and test_flaw_class_lints fail on the base for core/lanserve.py and routes_recordings.py threads (the phone agent's area). (checked 2026-11-09) [verified 2026-11-10: true, help-popovers.js fails 6 triggers it cannot click]
- [calendar-b72-1017.md] remaining: none. Not verified: a touch double tap on a cell (Playwright mouse only); a real model's reading of the words. (checked 2026-11-09) [verified 2026-11-10: true, touch double tap and real-model reading not verified]
- [canvas-1017.md] B29 popup placement: wb1017-popup.js measured the bar on screen, nothing spilling, at 1440 and 390 for text box, shape, two items, group; kept as a design request. Left: nothing in this file open except the B70 question. (checked 2026-11-09) [verified 2026-11-10: stale, B29 popup placement measured at 1440 and 390; nothing spilling]
- [companion-1018.md] done: step 3 (popup-actions audit: only "Stay here on every page" was silent, it nods now) and step 2 measured, not fixed (armjoint.js: cut line 0.3 to 0.9 units outside the torso in some poses and acts, equal on both arms, not background in pixels per armpixels.js; BACKLOG row updated). Left: nothing in the brief. (checked 2026-11-09) [verified 2026-11-10: true, companion-1018 step 2 measured, not fixed]
- [companion-1018.md] not verified: whether the 0.3 to 0.9 unit sliver is visible to the owner at the large view (2.2x, about 2 px); the pixel read was on the light theme only, THEME=dark did not apply in armpixels.js. (checked 2026-11-09) [verified 2026-11-10: true, 0.3 to 0.9 unit sliver visibility not verified]
- [composer-1011.md] found, not fixed: Agent mode with no model, "find notes simlar to my dentist one yk" answers about the whole sentence as a subject (checked 2026-11-09) [verified 2026-11-10: true, Agent mode no-model answers about the whole sentence; found, not fixed]
- [composer-1017-progress.md] left (open after O5 to O11 rest): B80 new-tag suggestions beyond the notebook's own tags (Auto-tag with no model only uses tags already in use); O10 history-derived previous tools, list_tools offered/held-back per turn; O11 supersede links in the graph, per-subject timeline, ai/factgraph.py integration; the stored social families still whole lines (how, sorry, laugh, reaction, ack, confused, morning). Targeted tests only were run; the full suite was not (standing order 5a). (checked 2026-11-09) [verified 2026-11-10: true, B80 new-tag suggestions beyond own tags open]
- [composer1310-1019.md] left: the model is not handed linked_to or why in its prompt (librarian _match_info_hint), src/tessellate/ai/librarian.py:515; prompt budget not spent (checked 2026-11-09) [verified 2026-11-10: true, model not handed linked_to or why; librarian.py:515]
- [composer1310-1019.md] left: themes come from shared tags and links only; notes with no tags and no links are all "more loosely" (composer_frame.themes) (checked 2026-11-09) [verified 2026-11-10: true, themes from shared tags and links only; untagged notes all loose]
- [composer1324-1019.md] left: "who is on the team offsite list" and "which books have I finished" return a note quote, not the asked fact (a who/status question over a list note), src/tessellate/ai/composer.py select (checked 2026-11-09) [verified 2026-11-10: true, who and stat questions return a note quote, not the fact]
- [composer1324-1019.md] left: "I found five notes about knives" shows one note: total and shown disagree in find, src/tessellate/ai/tool_say.py _found_notes caller (checked 2026-11-09) [verified 2026-11-10: true, five notes about knives shows one; total and shown disagree]
- [composer1324-1019.md] left: "summarise today" says "From today: <title>" per note, composer_digest recall lines (checked 2026-11-09) [verified 2026-11-10: true, summarise today per-note From today lines]
- [composer1324-1019.md] left: "compare the Porto and Lisbon notes" is a themed digest, not a side-by-side table (compare_sides now matches; table needs both sides' facts) (checked 2026-11-09) [verified 2026-11-10: true, compare is a themed digest, not a side-by-side table]
- [composer1324-1019.md] left: a note's fragment lines read "it has best crumb yet and it has next time ..." (composer_digest note-told-as-events join) (checked 2026-11-09) [verified 2026-11-10: true, fragment lines read as joined events in composer_digest]
- [composer1324-1019.md] left: INBOX 1324 and 1315 stay open as standing requests; the Ask AI part is fixed (checked 2026-11-09) [verified 2026-11-10: true, INBOX 1324 and 1315 stay open as standing requests]
- [composer4-1025.md] Not verified: no real browser run of the Chat "can't be reached" message (node --check only); quiz chips render as offers (route-tested, not looked at). (checked 2026-11-09) [verified 2026-11-10: true, Chat can't-be-reached message not browser-run; quiz chips]
- [composer7-1026.md] Not verified: small talk through the running app with a real persona prompt (unit and route tests only); no model. (checked 2026-11-09) [verified 2026-11-10: true, small talk with a real persona prompt not run]
- [composer8-1026.md] Not verified: composed small talk and nothing-found through the running app with a real persona prompt (unit and route tests only, no model); the Ask wrap in dark theme and at 560 px was measured for overflow only at 720, 1000 and 1440. (checked 2026-11-09) [verified 2026-11-10: true, composed small talk and nothing-found not run in app]
- [design6-1018.md] Not verified: a real pointer flick reaching each fate (the sweep seeds direct throws; one real flick only); the look of the splat and climb (measured, not watched); phone size. (checked 2026-11-09) [verified 2026-11-10: true, pointer flick fates and splat look not verified]
- [design7-1018.md] Not verified: a PDF's zoom and page stepper in the new dock (no PDF renderer package in the sweep's data dir, so pages did not render); a real trackpad pinch (wheel with ctrlKey); real touch hardware (CDP touch events only); Windows webview. (checked 2026-11-09) [verified 2026-11-10: true, PDF zoom and stepper in new dock not verified]
- [design7-1018.md] Found, not fixed: scratchpad was 768 files on the base (cap 766); three old sweeps went (lightboxentry.js superseded, graphoptheights.js, seg665-toolbar.js). (checked 2026-11-09) [verified 2026-11-10: true, scratchpad 768 files against cap 766 on base; found, not fixed]
- [docpaste-1026.md] Not verified: real-clipboard Ctrl+V from Word or a browser (events were dispatched ClipboardEvents); phone touch (no Ctrl key: tap the chip). (also: Carried from archived agent files, 2026-10-26) (checked 2026-11-09) [verified 2026-11-10: true, real clipboard Ctrl+V and phone touch not verified]
- [docs5-1026.md] Not verified: real touch on the phone foot bar; scroll-driven animation in the desktop webview (Chromium 115+ only; none shows otherwise). (checked 2026-11-09) [verified 2026-11-10: true, phone foot bar touch and scroll animation not verified]
- [docs6-1026.md] Selection bar at 390 (docs5 finding): not reproduced. A programmatic CodeMirror selection shows #selection-bar (flex, 355x54 at 27,266); an emulated double-tap or CDP long-press selects nothing in headless, so a real finger selection is not verified. (checked 2026-11-09) [verified 2026-11-10: stale, selection bar at 390 not reproduced; a programmatic selection shows it as designed]
- [documents-1018.md] step 2 B19 drag: documents-codekit.js (docSnippetDragStart, docSnippetScrollSpeed, docSnippetDragFrame), library-lazy.css .doc-drop-ghost; sweep snippetdrag1018.js 13/13 (ghost within 2px of the caret; bottom edge scrolled 0 to 1,319px in 0.7 s). Chromium's synthetic drag sends no repeat dragover while still, so the sweep nudges 1px. Not verified: a real mouse drag in the desktop webview, Firefox (draggable buttons). (checked 2026-11-09) [verified 2026-11-10: true, B19 drag step in documents-codekit.js; not confirmed as built here]
- [documents-1018.md] step 3 B23 part 1: right-click or hold on a Live cell opens the table menu at the pointer (docTableMenuAtPoint, one contextmenu listener ahead of the suggestion), nine new commands (move row/column, sort A-Z and Z-A, select row/column/table); pure model in the DOC-TABLE region, tests/test_doc_table_manage.py (25 checks), sweep tablemanage1018.js 20/20 at 1440 and 390. Menu is 19 items, 546px tall at 1440x900. Not verified: a real touch hold on a device. (checked 2026-11-09) [verified 2026-11-10: true, B23 part 1 table menu at pointer; open per the row]
- [documents-1018.md] step 4 B23 part 2: edge grips (docTableGripsPlugin, documents.js, a layer in the scroller; .doc-table-grip* in library-lazy.css). Column bars above the header, row bars beside the rows, a plus at the header's end and under the last row; click selects, drag moves (any distance, docTableMoveRowEdits and docTableMoveColumnEdits now take any delta), right-click or hold opens the menu at that row or column. Sweep tablegrips1018.js 28/28 at 1440 and 390, light and dark (grips flush within 2px of the cells, slot line within 3px of the drop edge). Not verified: a real touch drag on a device (the hit areas are 16px, 9px beside rows at 390 where the page padding is 9.6px; the hold menu is the touch path), tables wider than the editor (grips follow the rendered cells, not scrolled sideways). (checked 2026-11-09) [verified 2026-11-10: true, B23 part 2 edge grips; open per the row]
- [documents-1018.md] step 5 B18: the Snippets panel is open to a markdown document as Sections (DOC_SECTIONS, 24 rows, documents-codekit.js; docSectionPad gives a block its blank lines; {{date}} through docTemplateFill; Save keeps selected text under language md; the prose panel is remembered under docSectionsSide, apart from the code file's docCodeSide). The Assistant stays a code file's (.doc-code-only, and .doc-code-side.is-prose for the phone sheet). tests/test_doc_sections.py (7), sweep docsections1018.js 31/31 at 1440 and 26/26 at 390 (insert, Tab stops, one Ctrl+Z, blank lines on an empty line and mid-sentence drop, save, search, a code file keeps its own rows). test_code_documents.py asserted the panel was hidden for prose: its intent moved, so that assertion now checks only the Assistant's classes. Not verified: a phone's real touch drag of a row (rows are draggable; click is the phone path), prose sections in the Library's note editors. (checked 2026-11-09) [verified 2026-11-10: true, B18 Snippets Sections panel; step state open per the row]
- [documents-1018.md] step 6 B20 (reduced, the owner's recommendation taken): the editor already moved single lines on Alt+Up and Down (the step 0 audit said it did not: wrong), but in prose that welds paragraphs. docBlockMoveEdit (documents.js, pure) moves a paragraph, table, fence, list item with children (numbers stay) or heading section past its neighbour with the gaps untouched; docBlockMoveRun in docCmKeymap; code files and selections keep the line move; palette rows move-block-up and move-block-down. tests/test_doc_block_move.py (29 model checks), sweep docblockmove1018.js 18/18 (live, source, list, section, table, palette, py, selection). Not verified: a drag handle on every block (the heavy reading of "manage mode", still the owner's call above). (checked 2026-11-09) [verified 2026-11-10: true, B20 reduced Alt+Up and Down step; open per the row]
- ~~[dog2-1025.md] [ ] 22 not confirmed: blank dashboard in the harness for 3 to 6 s. (checked 2026-11-09) [verified 2026-11-10: true, blank dashboard in harness 3 to 6 s not confirmed]~~ stale (2026-11-11): the dashboard greeting and subtitle are in the DOM at first paint at 390, 720 and 1440 on the served app; a 3 to 6 s blank under load could not be reproduced (the harness never waits on it), and no code path defers the greeting
- [dog3-1026.md] [ ] 17 A: graph with no links says nothing why; minimap blank; node card covers its own label; empty-canvas double-click opens New note. PARTIAL (dog3a): "no links yet" stats line added; double-click on empty canvas kept (documented Grow the map, help index.html:3955); minimap blank and card over label not measured. (checked 2026-11-09) [verified 2026-11-10: true, graph with no links says nothing; minimap and double-click open] [re-checked 2026-11-11: the two measured parts (empty-graph hint, double-click) stand; minimap blank and card over label still unmeasured, left open for the graph spoke]
- ~~[dog3-1026.md] [ ] 24 A: dashboard greeting at 390: large gap between "Still up." and subtitle. (checked 2026-11-09) [verified 2026-11-10: true, dashboard greeting gap at 390 open]~~ stale (2026-11-11): measured at 390, 720 and 1440: greeting 36 px tall, subtitle margin-top 4 px, gap between them 4 px at every width (getBoundingClientRect), so there is no large gap
- ~~[dog3-1026.md] [ ] S: blank dashboard on 4 of 8 first loads at 720/390 under load 9-13 (not seen at 1440; load not ruled out; dog1 item 22 and sketchfix 6 did not reproduce). (checked 2026-11-09) [verified 2026-11-10: true, blank dashboard on first loads under load; open]~~ stale (2026-11-11): same as dog1 22 above, not reproduced at 720 or 390 on a current head; the greeting is static markup filled on boot
- [dog3a-1026.md] Not verified in a browser: hover-hidden remove cross (pointer devices), empty-Send toast, chat title ellipsis at 720/390, dark theme, touch. (checked 2026-11-09) [verified 2026-11-10: true, hover remove cross, empty Send toast and dark not verified in browser]
- ~~[dog3w-1026.md] [ ] dog3 8 (Fit leaves the root under the rail): not reproduced. Root left after open and after Fit: 1440 110 and 643 (rail ends 62), 720 119 and 291 (rail 71), 390 61 and 119 (no rail). wbFreeArea already takes the rail off. Not tried: a Fit with the Format panel open, a radial map growing left of the root. (checked 2026-11-09) [verified 2026-11-10: stale, Fit leaves root under rail not reproduced; root positions measured]~~ stale (2026-11-11): already verified stale 2026-11-10, root clear of the rail after Fit
- [fixes1-1018.md] Not verified in the app: C31 (link kind sheet), the document half of C32. (checked 2026-11-09) [verified 2026-11-10: true, C31 link kind sheet and document half of C32 not verified]
- [fixes2-1018.md] not verified: splash.ps1 on Windows (C02, C38); a right-drag on macOS, where contextmenu fires on the press (checked 2026-11-09) [verified 2026-11-10: true, splash.ps1 on Windows and macOS right-drag not verified]
- [fixes3-1018.md] Left: C44, C39, C40, C36, Open Packages help (standing order 13). (checked 2026-11-09) [verified 2026-11-10: true, C44, C39, C40, C36 and Open Packages help left]
- [fixes4-1018.md] Left: Escape on the image lightbox (needs an image note), reminders add form, notes edit entry, graph node panel; the chat undo line (undo.js found 0 actions on rerun, not reproduced); Back with the lightbox open is coded (.lightbox takes a synthetic Escape) but not run. (checked 2026-11-09) [verified 2026-11-10: true, Escape on lightbox, reminders add form and graph node panel left]
- [fixes6-1018.md] Found, not fixed: chat/Ask routes carry no locale, so "3/4" in Ask is still day first; the currency table needs to become a preference before decision 43's editor. (checked 2026-11-09) [verified 2026-11-10: true, chat and Ask routes carry no locale; 3/4 day first; currency table open]
- [fixes7-1018.md] Item 4 (ghost topics): done, in the lazy library-lazy.css (boot CSS untouched). Measured: 3 ghosts, 8 px under the topic, Tab/Escape/Tab-Tab-Enter add exactly 2 (untracked sweep, never committed). Not verified: touch, 390 px width, reduced motion (no motion used), dark theme contrast of the faded chip. (checked 2026-11-09) [verified 2026-11-10: fixed, ghost topics done in library-lazy.css per the bullet; measured]
- [fixes8-1018.md] Not verified: light theme (THEME=light did not switch the sweep off dark), the 390 sidebar sheet opened (only page-level scroll measured), real screen reader. (checked 2026-11-09) [verified 2026-11-10: true, light theme and 390 sidebar sheet not verified]
- [fixes8-1018.md] Found, not fixed: at 390 the Categories head is hidden by an existing rule (<600), so that section cannot fold there; chips row stays. (checked 2026-11-09) [verified 2026-11-10: true, Categories head hidden at 390 by existing rule; found, not fixed]
- [fixes9-1018.md] Left: INBOX 1301 still holds D1 to D6 (other agents); D7/D8 marked Fixed in place. (checked 2026-11-09) [verified 2026-11-10: true, INBOX 1301 still holds D1 to D6]
- [graph1306-1019.md] layout: measured only (graphdefault1306.js, seed-graph40.py); two tuning tries (landscape x pull, organic ring stretch floor) moved fill 0.48 to 0.53 and crossings 77 to 72..82, so reverted. Left: crossings and the hub's spokes (graph-worker.js applyGrouping, hub pull), label density (graph-canvas.js label gate). The owner's crowded lower-half labels did not reproduce on this seed. (checked 2026-11-09) [verified 2026-11-10: true, graph layout measured only; tuning open]
- [lanbar-1011.md] Not verified: a real phone, a real wifi drop or hotspot join (netid is the (checked 2026-11-09) [verified 2026-11-10: true, real phone and wifi drop not verified]
- [lansec-1025.md] next: nothing; not verified on a real phone (checked 2026-11-09) [verified 2026-11-10: true, lansec not verified on a real phone]
- [logo-1011.md] Not verified: a real OS install (taskbar, dock, Start menu icon from icon.ico); Android's maskable crop on a device (the test holds the mark inside the 80% circle); the busy lift during a real model turn (driven by pushing a running run onto agentRuns). (checked 2026-11-09) [verified 2026-11-10: true, real OS install and Android maskable crop not verified]
- [mobile1314-1019.md] left: a real phone (safe-area insets are 0 in headless Chromium); the owner's own read of whether Graph behind More is right (decision taken per standing order 3, UI_MODERNISATION_PLAN "Placed from INBOX, 2026-10-19"). (checked 2026-11-09) [verified 2026-11-10: true, real phone and safe-area insets left]
- [mobile1314-1019.md] left: docks with a search field are two rows on a phone (notes 114px, library 114, timeline 114, graph 111; docks.js at 390); by Phase 11's decision (identity zone basis 100%), not changed here. Chrome 14 to 21% of 844, under phonechrome.js's 25% budget. (checked 2026-11-09) [verified 2026-11-10: true, docks with a search field two rows on a phone; open]
- [mobile1314-1019.md] left: phonechrome.js and phone.js measure 390 by default; the 360 band's timeline bleed (the day well 9.6px into the card padding) is exempted as deliberate in both. (checked 2026-11-09) [verified 2026-11-10: true, 360 band timeline bleed; left]
- [open-1018.md] Not verified: the find and dock help popovers at 1440 and the list, outline and find ones at 390 (sweep clicks timed out), 1024 and dark theme; a real mouse and a touch hold; link offers in a code document are off by design. (checked 2026-11-09) [verified 2026-11-10: true, find and dock popovers at 390 and 1024 not verified]
- [open-1018.md] Link offers: no Settings switch (found-not-fixed); "ignore" is per session (docProseIgnored); tag offers dropped (a document has no tags); a title only matches as the whole opening line of a note. (checked 2026-11-09) [verified 2026-11-10: true, link offers have no Settings switch; ignore per session]
- [order-1018.md] found-not-fixed: tests/test_typo_routing.py "search the web for sandwiches" writes ./data when run serially (conftest guard errors, also at base); tests/test_boot_budget.py boot JS 588516 > cap 588400 (staged-lints fails at base). (checked 2026-11-09) [verified 2026-11-10: true, test_typo_routing writes ./data when run serially; found, not fixed]
- [perf-1017.md] found-not-fixed (3): atlasRigFrame (atlas-motion.js ~252, ~296) reads getComputedStyle each frame, a forced style recalc per flight frame (178 in 1.6 s, 530 ms); skipping it while carried is a design call for the arm rig (checked 2026-11-09) [verified 2026-11-10: true, atlasRigFrame reads getComputedStyle each frame; found, not fixed]
- [pin-1012.md] left: Windows DPAPI and macOS Keychain paths never ran here (not verified) (checked 2026-11-09) [verified 2026-11-10: true, DPAPI and Keychain paths never ran]
- [reveal-1018.md] found-not-fixed (Notes): the first recalc (701 and 917 el, 66 and 104 ms) is already content-visibility: auto rows plus the sidebar. A 13-row first paint with no top-up cut it 26 percent in elements, but it changes the settled list (60 rows to about 13), and Select all and Ctrl+F read the rendered rows; with a top-up the reveal sees 60 rows again. Boot JS has 147 bytes of headroom. (checked 2026-11-09) [verified 2026-11-10: true, first Notes recalc cost with content-visibility rows; found, not fixed]
- [reveal-1018.md] found-not-fixed: cv:auto paints text in cards at fractional y up to 1 px differently (3.6k of 1.3M pixels at 1440x900, rows 4+); settled scroll height +56 px until cards are seen. (checked 2026-11-09) [verified 2026-11-10: true, cv:auto text paints differently by up to 1 px; found, not fixed]
- [settings-1017.md] B14 done: Expand all / Collapse all in the dock of panes with 2+ folds (skills, websearch, appearance, shortcuts, help, about; probe p/b14b.js at 1440 and 390). Left: panes with 0-1 fold (models, personas, tools, ...) get none; their "sections" are not collapsible. a29dfab. (checked 2026-11-09) [verified 2026-11-10: fixed, Expand all and Collapse all added; commit a29dfab in history]
- [settings-1017.md] B61 done (smallest honest): dictation sizes marked "(on this computer)" / "(~N MB to download)", confirm on choosing a size that is not here (cancel reverts, nothing downloads until first dictation), Remove this size (DELETE /voice/models/{size}); embedding models already had remove. Left: unsloth gemma embedding licence remark (not touched), a delete for other model kinds. 78f9e0f. (checked 2026-11-09) [verified 2026-11-10: fixed, dictation sizes marked on this computer; commit 78f9e0f in history]
- [settings-1017.md] B55 done in part: the web menu offers Start/Install SearXNG on the DuckDuckGo provider too (was ["Web search settings"] only); palette row finds the Web clipper. Left: the clipper UX redesign (placed). B53: placed (no consume-side MCP UI exists; BACKLOG trust model). B59: investigated, not reproduced (no sentence-transformers here). Next: final report. (checked 2026-11-09) [verified 2026-11-10: fixed, web menu offers Start and Install SearXNG on DuckDuckGo too]
- [settings58-1018.md] left: icon-toggle sweep reached only 11 standalone icon-only toggles with no content seeded; whiteboard map toggles (wb-map-core, edge-dashed/arrow) and ask-time-travel, ocr-zoom-fit show a pressed fill only, no glyph swap (docs: frontend/js/whiteboard-map.js:6900, capture-ask.js:3372, library.js:5996) (checked 2026-11-09) [verified 2026-11-10: true, icon-toggle sweep reached 11 toggles; whiteboard map toggles left]
- [shell-1025.md] not verified: a real touch device; Windows webview (checked 2026-11-09) [verified 2026-11-10: true, real touch device and Windows webview not verified]
- [sugg1329-1019.md] left: the Names and Link types rows (inboxMergeRow, inboxTypeRow, suggestions-inbox.js) still use the older .inbox-row shape (title, reasons with percentages, chip + button + X foot); bring them onto the Links row's grid if the owner wants the four kinds to match. (checked 2026-11-09) [verified 2026-11-10: true, Names and Link types rows still use the older .inbox-row shape]
- [timeline-1018.md] left (not mine, untouched): OPEN.md rows 330 (On this day row moves the list 44 px at 390), 341 (the table has no meeting mark), 850 (a map under the Boards chip); timeline.js sweep's "a bucket head stays pinned after scrolling" fails 1 to 3 times a run on the base too (the week-ahead heads, flaky by run: 1440, 390 then 1440, 1024); errors.js at 390 reports 4 off-screen button.ghost.small on the Notes tab (both themes), not the Timeline. (checked 2026-11-09) [verified 2026-11-10: true, timeline rows left in OPEN.md (44 px shift, meeting mark) not built]
- [uxfix4-1018.md] Not verified: pixel sampling (pngpixel.py) was not used; all values are computed styles composited from the effective background. Topics outside the 390 viewport are culled by the app and were not measured (6 of 31 topic text elements at 390). (checked 2026-11-09) [verified 2026-11-10: true, pixel sampling not used; computed styles only]
- [wb-1025.md] Not verified: the Windows webview, and drag-select outside Chromium. (checked 2026-11-09) [verified 2026-11-10: true, Windows webview and drag-select outside Chromium not verified]
- [wb1327-1019.md] Trackpad: real hardware not verified; the heuristic (deltaX, or |deltaY| under 50 or fractional, gesture = events less than 200ms apart) was tested with synthetic event sequences only. tests/test_wb_middle_pan.py. (checked 2026-11-09) [verified 2026-11-10: true, trackpad heuristic not checked on real hardware]
- [wb2-1025.md] not verified: reorder in tree-down, org and tree-both (x axis, two sides) by pointer; only tree-right swept (checked 2026-11-09) [verified 2026-11-10: true, tree-down, org and tree-both reorder by pointer not verified]
- [wb2-1025.md] found-not-fixed: the export dialog says "Export this board" when it opens on a branch; mmd2-1005-markers.js sweep crashes at its own press() helper (stale sweep) (checked 2026-11-09) [verified 2026-11-10: true, export dialog says Export this board on a branch; found, not fixed]
- [wbpaste-1026.md] Not verified: real OS clipboard (sweep dispatches ClipboardEvents and uses the headless clipboard API); a real spreadsheet copy; touch. (checked 2026-11-09) [verified 2026-11-10: true, real OS clipboard and spreadsheet paste not verified]
- [wbpaste-1026.md] Found-not-fixed: app.js gzip cap (14,300) has no room for one more script line, so the shared helpers and the board paste code sit inside documents-prose.js and whiteboard-commands.js instead of their own files; a split needs the cap to come down elsewhere first. (checked 2026-11-09) [verified 2026-11-10: true, app.js gzip cap has no room for one more line; found, not fixed]
- [worldclass-1018.md] Found, not fixed (A): Escape on Settings rewrites the settings entry's address to the tab underneath (#/reminders), so Forward onto it shows the wrong hash although the dialog is right; a reload on that entry would open the tab, not Settings. Low impact. (checked 2026-11-09) [verified 2026-11-10: true, Escape on Settings rewrites the entry address; found, not fixed]
- [worldclass-1018.md] Found, not fixed (B), the real one: browser Back (history.back()) with an overlay open steps the tab history and leaves the overlay open on the other tab. Palette, finder, Guide, shortcuts and quick note: 5 of 5 left the overlay open and moved Timeline to Notes. Settings is right (closes, stays, 1 of 1). On a phone, where Back is the way out of a sheet, this matters more. Not measured at 390. (checked 2026-11-09) [verified 2026-11-10: true, browser Back with overlay open steps tab history; found, not fixed]

## Boot budget, 2026-11-03

- ~~[ ] Win back the 2026-11-03 raise of the boot gzip cap (260,350 to 260,520, `tests/test_static_compression.py`, INBOX 1603, the tray drop, 1619 and 1620): the next boot diet moves a boot-time wiring to a lazy file and lowers the cap again. (checked 2026-11-09) [verified 2026-11-10: true, boot gzip cap raise from 2026-11-03 still to win back in test_static_compression.py]~~ fixed (2026-11-11): the boot diet moved the cap to TOTAL_CAP 250,450 in tests/test_static_compression.py:163, below the 260,350 it was raised to

## PR 216 close-out: audit and Fable findings (2026-11-11)

Inventory of every finding in the audit and Fable files, taken from the files as merged at 1889fdc74. Docs only; no product code was changed. Status is "fixed" only with evidence; otherwise "open", or "owner call" when it waits on the owner. The full per-row list (with fixed rows) is regenerated by the method below; only open and owner rows are itemised, because the fixed ones need no work.

**Method.** Row marks first (`**Fixed <sha>**`, `[verified 2026-11-10: fixed|stale]`, `[s11-1110: stale]`); then the ranked indexes (1028-verify, 1029-ranked, 1031-ranked) for class-level fixes; then struck or fixed rows in this file's work order; then CHANGELOG lines naming "audit 1029 rank N" or "audit 1031 Z12"; then a code or test grep at file:line for every fixed row without an explicit HISTORY, CHANGELOG or commit pointer (table below). Rows marked only "Open (checked 2026-11-09)" in the 1029 and 1031 files stay open unless an index, test or the code shows otherwise; AR1, BK3, G3, G5, G8, G28, C47 and N17 were downgraded from the index to open because no test or code line could be found. "Stale" rows (not reproduced, or already built before the audit) count as closed.

### Counts

| File family | Open | Owner call | Fixed | Stale | Rows |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1028 audits | 104 | 5 | 216 | 26 | 351 |
| 1029 audits | 23 | 0 | 118 | 0 | 141 |
| 1030 audits | 48 | 1 | 75 | 9 | 133 |
| 1031 audits | 101 | 0 | 169 | 2 | 272 |
| 1102 audits | 2 | 0 | 29 | 1 | 32 |
| 1107 audits | 42 | 1 | 54 | 3 | 100 |
| 1108 audits | 5 | 0 | 6 | 2 | 13 |
| audit68 1101 | 1 | 0 | 0 | 0 | 1 |
| Fable files | 25 | 4 | 21 | 0 | 50 |
| diagram-fable 1679 | 5 | 0 | 33 | 0 | 38 |
| fitaudit 1109 | 2 | 2 | 0 | 0 | 4 |
| owner-asks 1108 | 100 | 9 | 86 | 0 | 195 |
| AUDIT.md, FABLE_BRIEF.md | 0 | 0 | 0 | 0 | 0 |
| MODERNISATION_AUDIT.md (28 headed findings, 4 of them positives) | 18 | 0 | 6 | 0 | 24 |
| **Total (audit and Fable files, without the modernisation row)** | **458** | **22** | **807** | **43** | **1330** |

MODERNISATION_AUDIT.md: fixed B2, B3, C1, D4, D5, G1 (spot-checks above); the other 18 (A1 to A3, B1, B4 to B6, C2 to C4, D1 to D3, E1 to E3, F1 to F3, H2, H3) are reasoned or measured findings that each cite a plan row id, not re-verified here and not itemised; they are batch BM1 below (read-only check, then list what is still open), which fits any slot set. They are not in the totals row. AUDIT.md and FABLE_BRIEF.md are briefs whose work is executed (the findings they asked for are the audit files above); they hold no findings of their own. The 1028 shell, ux, docs and board files have the most open rows because they carry no per-row marks after the work-order tiers closed them in aggregate; the owner-asks Missing and Partial sections carry the rest.

### Spot-checks (fixed without a HISTORY, CHANGELOG or commit pointer)

| Finding | Evidence (grep at file:line) |
| --- | --- |
| 1029 X2, X3 (recording kept unsaved) | frontend/js/navigation.js:1109 (guard comment and flag); CHANGELOG 'w6-1110, audit 1031 Z12' line 105 |
| 1029 X1 (space delete safe) | tests/test_space_delete_safe_1029.py (counts route test, line 12) |
| 1029 G9, G22 (graph reload line) | tests/test_graph_reload_line_1029.py:15 |
| 1029 G19 to G21 (graph contrast) | tests/test_graph_contrast_1029b.py:48 |
| 1029 H9 to H11 (focus feedback) | tests/test_focus_feedback_1029.py:29 |
| 1029 N9 (notes window) | frontend/js/notes-list.js:1875 (one windowed list, audit 1029 N9) |
| 1029 N12 to N14 (note card blocks) | tests/test_note_card_blocks_1029.py:40 |
| 1029 C29 (ranker leads with subject note) | tests/test_composer_ranker_1029.py:80 |
| 1029 C49 (regex linear) | tests/test_composer_regex_linear_1029.py:23 |
| 1031 AI7, AI8, AI10, AI11, AI17 | docs/roadmap/agent-remaining/aifix-1031.md:12 |
| 1031 SH2, SH5 (hint not a live region) | tests/test_a11y_regions_1031.py:22 |
| 1031 PF1 (focus settles keyboard inset) | tests/test_perf_1031.py:11 |
| 1031 BK2 (binned note refuses a put) | tests/test_bin_guard_1031.py:21 |
| 1031 BD13 (board coordinates refused) | tests/test_board_coordinates_1031.py:31 |
| 1031 GR6 (graph draws by heat) | tests/test_perf3_graph_1031.py:48 |
| 1031 HR20 (rewrite bubble names the act) | tests/test_chat_flows_1031.py:20 |
| 1031 N50 (one preview pass) | tests/test_notes_audit_ui_1031.py:43 |
| 1028 E66 (all is not reduced to best) | tests/test_engine_acts.py:116 |
| 1108 P10 (perf) | docs/roadmap/agent-remaining/perfset-1108.md:3 (done list) |
| Modernisation C1 (app.js 26,113 lines) | frontend/js/app.js is 1,920 lines; frontend/js holds 278 files |
| Modernisation D5 (OpenAPI served) | src/tessellate/api/app.py:1818-1820 (docs_url=None, openapi_url=None) |
| Modernisation D4 (pagination) | src/tessellate/api/routes_entries.py:2600-2670 (limit, offset, X-Total-Count); routes_timeline.py, routes_documents.py, routes_duplicates.py also page |
| Modernisation B2 (card actions cover text on touch) | frontend/css/00-tokens-shell.css:2187-2220 (hover: none keeps actions visible, 44 px target) |
| Modernisation B3 (no viewport below 600 px) | frontend/css/00-tokens-shell.css, 05-sidebars-themes.css, 07-whiteboard-misc.css each carry max-width 4xx/5xx queries |
| Modernisation G1 (phone nav scrolls away) | frontend/css/00-tokens-shell.css:3633 (phone dock on the screen edge) |

### Batches

Each batch is Sonnet-sized (about 15 to 28 rows) and sits in one hot-file group, so two batches that share a group are never in one slot set. Hot groups: composer (`ai/composer_*.py`, `ai/commands.py`, `ai/when.py`), chat (`chat-turn.js` and the ask path), documents (`documents*.js`), whiteboard (`whiteboard*.js`), graph (`graph*.js`) with dashboard (`dashboard.js`), diagram (`diagram*.js`). Shell, companion and agent batches avoid those files by group; a row that names a hot file anyway sits in that hot group.

| Batch | Group | Rows | Files (main) |
| --- | --- | ---: | --- |
| BC1 | composer | 20 | audit-1029-composer.md (15), audit-1028-agent.md (3), audit-1030-composer.md (2) |
| BC2 | composer | 20 | audit-1030-composer.md (20) |
| BC3 | composer | 20 | audit-1030-composer.md (11), audit-1031-composer.md (8), audit-1031-architecture.md (1) |
| BC4 | composer | 20 | audit-1031-composer.md (20) |
| BC5 | composer | 20 | audit-1031-composer.md (16), audit-1107-composer-r2.md (4) |
| BC6 | composer | 20 | audit-1107-composer-r3.md (11), audit-1107-composer-r2.md (9) |
| BC7 | composer | 20 | audit-1107-composer.md (13), audit-1107-composer-r3.md (5), audit-1108-perf.md (1), fable-composer-1110.md (1) |
| BC8 | composer | 19 | fable-composer2-1110.md (8), fable-composer-1110.md (6), fable-fix-1030.md (2), fablecomp-1031.md (1) |
| BS1 | shell | 19 | audit-1028-shell.md (11), audit-1028-backend.md (5), audit-1028-agent.md (2), audit-1028-docs.md (1) |
| BS2 | shell | 19 | audit-1028-shell.md (19) |
| BS3 | shell | 19 | audit-1028-ux.md (12), audit-1028-shell.md (3), audit-1029-harness.md (1), audit-1029-notes.md (1) |
| BS4 | shell | 19 | audit-1031-notes.md (8), audit-1031-extras.md (6), audit-1031-architecture.md (2), audit-1030-extras.md (1) |
| BS5 | shell | 19 | audit-1031-notes.md (10), fable-composer-1110.md (3), audit-1031-shell.md (1), audit-1107-composer.md (1) |
| BS6 | shell | 19 | owner-asks-audit-1108.md (14), fitaudit-1109.md (3), fable-eye-1030.md (1), fablecomp-1031.md (1) |
| BS7 | shell | 19 | owner-asks-audit-1108.md (19) |
| BS8 | shell | 18 | owner-asks-audit-1108.md (17), parity-1110.md (1) |
| BK1 | companion | 24 | owner-asks-audit-1108.md (17), audit-1030-ai.md (2), audit-1029-extras.md (1), audit-1031-extras.md (1) |
| BK2 | companion | 24 | owner-asks-audit-1108.md (24) |
| BW1 | whiteboard | 28 | audit-1028-board.md (11), audit-1028-ux.md (8), audit-1028-backend.md (2), owner-asks-audit-1108.md (2) |
| BD1 | documents | 27 | audit-1028-docs.md (14), audit-1031-docs.md (3), audit-1102-docs.md (2), audit-1031-code.md (1) |
| BH1 | chat | 21 | audit-1028-agent.md (10), audit-1031-composer.md (2), owner-asks-audit-1108.md (2), audit-1028-shell.md (1) |
| BG1 | diagram | 15 | owner-asks-audit-1108.md (11), diagram-fable-1679.md (4) |
| BR1 | graph | 16 | audit-1029-graph.md (5), audit-1031-graph.md (4), audit-1028-backend.md (1), audit-1028-shell.md (1) |
| BA1 | agent | 15 | audit-1030-ai.md (9), audit-1028-backend.md (3), audit-1028-shell.md (1), audit-1031-backend.md (1) |

### Slot sets (up to 4 parallel batches, distinct groups)

| Set | Batches |
| --- | --- |
| S1 | BC1 (composer), BS1 (shell), BK1 (companion), BW1 (whiteboard) |
| S2 | BC2 (composer), BS2 (shell), BK2 (companion), BD1 (documents) |
| S3 | BC3 (composer), BS3 (shell), BH1 (chat), BG1 (diagram) |
| S4 | BC4 (composer), BS4 (shell), BR1 (graph), BA1 (agent) |
| S5 | BC5 (composer), BS5 (shell) |
| S6 | BC6 (composer), BS6 (shell) |
| S7 | BC7 (composer), BS7 (shell) |
| S8 | BC8 (composer), BS8 (shell) |

### Open and owner inventory

Format: id | file:line | one line | status.

**BC1 (composer, 20 rows)**

- E54 | audit-1028-agent:66 | Identity is muddled: "I'm the assistant that comes with Tessellate and works for Atlas | stale: decided: CHAT_PLAN decision 76 (owner, 2026-10-17) says the engine is Atlas's assistant and Atlas is the model; composer_lines.py:497
- E56 | audit-1028-agent:68 | remind me ... about the group meeting an hour before, set a timer for 25 minutes, start a pomodoro, show | partial: d1c5a1265: set a timer, start a pomodoro or stopwatch, open the clock now open the Clock with the length ready (tests/test_composer_bc1_1111.py); export, backup, calendar, create and rename category and count-by-tag already answered on this head. Deferred: 'remind me ... an hour before' (when.py) and 'switch to dark mode' (no theme act)
- E69 | audit-1028-agent:81 | Chat input autocorrect (data-autocorrect) runs on a notebook full of names, codes and course IDs; combine | stale: the correction is underlined, a click offers Keep, Put back and Edit, Ctrl+Z or the toast Undo restores it (autocorrect.js:225-245), and the server says 'I read that as' (composer_ack.py)
- C15 | audit-1029-composer:59 | Command and filler words stay in the subject, so the digest is about the wrong thing | stale: fixed 20a9c39e2 (tests/test_composer_subject_1029.py)
- C16 | audit-1029-composer:60 | A name matches inside another word | stale: fixed 20a9c39e2 (tests/test_composer_subject_1029.py)
- C17 | audit-1029-composer:61 | A question about a person is answered as an attendee list | stale: fixed 20a9c39e2 (tests/test_composer_subject_1029.py)
- C18 | audit-1029-composer:62 | A definition request gets the digest | stale: fixed 20a9c39e2 (tests/test_composer_subject_1029.py)
- C19 | audit-1029-composer:68 | The defining note does not lead, in lists, answers and summaries | stale: fixed bb1938c26 (tests/test_composer_ranker_1029.py)
- C20 | audit-1029-composer:69 | Ask and Chat order the same list differently, and "open X" differs | stale: fixed bb1938c26 (tests/test_composer_ranker_1029.py)
- C21 | audit-1029-composer:70 | A question's slot is ignored; the first sentence of the top note is returned | stale: fixed 48ba6b3ac (tests/test_composer_slots_1029b.py)
- C22 | audit-1029-composer:71 | Yes/no questions about ticked items are answered with the wrong item and no yes or no | stale: fixed 26b79257c (tests/test_composer_slots_1029.py)
- C23 | audit-1029-composer:72 | Time-since, how-often and how-old questions get a wrong or invented answer | stale: fixed 26b79257c and 48ba6b3ac (tests/test_composer_slots_1029.py, _1029b.py)
- C31 | audit-1029-composer:85 | Subject ignored in "latest" questions | stale: fixed bb1938c26 (tests/test_composer_ranker_1029.py)
- C33 | audit-1029-composer:92 | A "what is left" question gets the wrong list | stale: fixed 26b79257c (tests/test_composer_slots_1029.py)
- C34 | audit-1029-composer:93 | "open checklist items" -> "Your note The Complete Social Skills Guide lists one | stale: fixed 48ba6b3ac (tests/test_composer_slots_1029b.py)
- C36 | audit-1029-composer:95 | Compare answers one side or garbage | stale: fixed a0b747f50 (tests/test_composer_compare_1029.py)
- C37 | audit-1029-composer:96 | Instruction words are reported as missing evidence (E22, still open, 25+ occurrences) | stale: fixed 20a9c39e2 (instruction stems); the temperature case that still showed it is fixed d1c5a1265
- C47 | audit-1029-composer:111 | Act confirmations use five openers and expose ids (E27, partly fixed) | partial: ids and '1 note' are gone (cards name the note by title, Confirm first); the five openers remain and are Z61 in BC3
- Z7 | audit-1030-composer:90 | The stale-plan line is word-order broken and wrong in mood | deferred: the 'may still be open' wording is fixed (composer_tables.py drift); the quoted plan fragment is built in composer_digest.py, which another agent holds
- Z16 | audit-1030-composer:109 | A verb or instruction word becomes a required term, and the footer tells the person the notes "do not men | partial: d1c5a1265: temperature, oven, hot and degrees questions answered by a quoted figure leave no footer; frame-word list was already in place (composer_unfound.py)

**BC2 (composer, 20 rows)**

- Z17 | audit-1030-composer:110 | Notebook asks (themes, summarise) read the whole notebook (partial | fixed: 13df2e9 and 79652a7db (a rating fraction after a title is a rating; tests/test_composer_bc1_1111.py). Residual: 'did I give X 9/10' still answers 'I found nothing'
- Z20 | audit-1030-composer:113 | A feeling question prefers the line holding a feeling (partial) | fixed: 13df2e9; residual: 'how am I feeling' quotes the Meditation note
- Z21 | audit-1030-composer:119 | A "when" prefers a sentence with a calendar day to a window ("this week"); partial | fixed: b2bccba (rechecked 2026-11-11)
- Z22 | audit-1030-composer:120 | How long since answers from the last dated line (partial | fixed: 13df2e9; 'how long since I called Sara' year and 'how old is the starter' sit in the date files (deferred)
- Z23 | audit-1030-composer:121 | How-often and how-many for an activity count notes, not events, and fall back to the first sentence | deferred: date/count code (composer_slots.py) is held by another agent
- Z24 | audit-1030-composer:122 | A where answer leads with the place, or says there is none | fixed: 13df2e9; residual: 'where does Sara live' quotes Gift ideas
- Z25 | audit-1030-composer:123 | Temperature asks (how hot, what temp, what oven setting) read; partial | fixed: b2bccba and 55e2c26f7: temperature asks answer by a figure and drop the footer
- Z26 | audit-1030-composer:124 | Dates: past-tense or past-dated lines are listed as upcoming | deferred: date lists (composer_ahead.py) are held by another agent
- Z27 | audit-1030-composer:125 | Windows and sets disagree: "what's due soon" says Three dates fall in the next two weeks, 4 November to 1 | deferred: date windows (composer_ahead.py) are held by another agent
- Z28 | audit-1030-composer:126 | A one-day "what did I do on X" says what the notes hold (title and first sentence), not that they were ma | fixed: 07d7194
- Z29 | audit-1030-composer:132 | "Sum of rent and groceries", "what is the total of my budget", "total cost of the Lisbon trip" add the am | fixed: 07d7194; residual: 'how much did I spend on clothes/shopping' finds nothing (category to notes mapping)
- Z32 | audit-1030-composer:135 | A name that is a note's title or category adds every amount in that note (partial | fixed: 07d7194
- Z33 | audit-1030-composer:141 | Open checklist left/done questions answered from the open note (partial) | fixed: b2bccba
- Z36 | audit-1030-composer:144 | Untitled notes are counted and duplicate notes are answered from the notebook (partial | fixed: 07d7194
- Z37 | audit-1030-composer:145 | "Untick" says it cannot yet and "mark X as packed" reads as the tick act (partial | fixed: 07d7194
- Z39 | audit-1030-composer:152 | Citation tags switch style in one answer | deferred: citation tags are drawn by the front end's answer renderer; no composer-side cause found, needs a rendered sweep
- Z40 | audit-1030-composer:153 | The sources column is not in citation order | stale: a number sort exists and the sources column follows citation order on this head
- Z45 | audit-1030-composer:158 | "Here is your newest note" for one, and a capitalised month (partial | fixed: 07d7194
- Z46 | audit-1030-composer:159 | A frame word ("goes", "ingredients", "contents") is no longer named as a missing topic (partial | fixed: c2de394
- Z49 | audit-1030-composer:167 | The tool describes itself in the answer | blocked: decision 54 says a computed sentence always says 'Read as ...'; recommendation: keep the line, shorten it, and decide with the owner

**BC3 (composer, 20 rows)**

- Z50 | audit-1030-composer:168 | A bare note word ("Atlas", "Sara") is a notes ask and "call Sara" with a note about her is the lookup (pa | fixed: 07d7194; rechecked 2026-11-11: 'what is Atlas' answers from the Atlas notes and 'what's your name' says Atlas's assistant (decision 76)
- Z53 | audit-1030-composer:176 | Follow-ons keep the cited note (partial | fixed: b2bccba; 'how much does it cost' with no prior turn still picks the passport (the Ask tab holds no turns)
- Z56 | audit-1030-composer:179 | One checklist-state reader: "is the passport packed" is yes or no with the item, "is everything packed" | fixed: c2de394; 'what have I finished' reads the Books note, residual
- Z57 | audit-1030-composer:180 | The plan-the-week answer puts everything on one day | stale: rechecked 2026-11-11: the week answer groups by day with 'Free weekdays: Monday, Tuesday, Thursday, Friday'
- Z58 | audit-1030-composer:181 | Compare answers use the wrong notes or a missing relation | stale: rechecked 2026-11-11: 'which trip is sooner' compares Lisbon with Tokyo by date and 'Lisbon vs Tokyo' uses the trip notes
- Z59 | audit-1030-composer:182 | "What do I want to learn" gives From your notes | stale: rechecked 2026-11-11: 'what do I want to learn' and 'what am I learning' both say Spanish; the streak is labelled 'writing streak'
- Z61 | audit-1030-composer:189 | The confirmation for the same kind of act is worded five ways | deferred: the eight openers are a deliberate design (composer_replies.CONFIRM, B24) and all name Confirm and Cancel; unify only on an owner decision
- Z62 | audit-1030-composer:190 | Reminder confirmations are fragments with three time formats | deferred: reminder time wording is built in when.py / acts.py with the date files held by another agent
- Z63 | audit-1030-composer:191 | An act that creates a note turns the whole sentence into the title, and the title-only notes then rank ab | open: not reproduced from the Ask tab (acts redirect to Chat); needs a Chat-tab sweep of the note title built from a sentence
- Z67 | audit-1030-composer:200 | Not reproduced on the fix branch (the base answers from the Sara notes only) | stale: rechecked 2026-11-11: 'what does Sara want for her birthday' answers from the Sara note only
- Z68 | audit-1030-composer:208 | With a model up, date and days-until questions in Ask are answered I couldn't find any saved notes matchi | open: needs a model up to reproduce; not verifiable on the fake transport
- AR3 | audit-1031-architecture:29 | The composer is a second application | open: architectural, no cheap fix; recorded as design work
- C2 | audit-1031-composer:45 | The supersede rule treats two facts with the same name key as old and new values of one thing, and report | stale: rechecked 2026-11-11: 'what have I written about Sara' and 'what is in the Sara note' answer from the Sara note without a supersede line
- C3 | audit-1031-composer:46 | A holiday or month word in a topic question is read as a date window, so the notes that hold the word are | stale: rechecked 2026-11-11: 'what do I know about Christmas' and 'who is coming for Christmas' answer from the mum note
- C4 | audit-1031-composer:47 | Term frequency beats the defining note once the notebook has noise | open: reproduces at 207 notes: 'what do I know about reading' leads with filler notes after the Books note
- C5 | audit-1031-composer:48 | Several notes are glued into one sentence with commas and ellipses once the overview runs past its line b | open: reproduces at 207 notes: filler notes are quoted in full, glued with ellipses
- C6 | audit-1031-composer:49 | The count sentence counts the largest theme, not the notes the answer then says, so counts disagree with | partial: rechecked 2026-11-11: 'what have I written about uni' now counts eight and says eight; the 207-note count sentence still disagrees
- C7 | audit-1031-composer:50 | A question naming a titled note ("the X note", "what is in the X note") is not resolved to that note; the | stale: rechecked 2026-11-11: 'what is Tom's note about' and 'what is in the Sara note' answer from the titled note
- C9 | audit-1031-composer:52 | A sentence's own date word is read as the event's day, resolved to the past because the ask is past tense | stale: rechecked 2026-11-11: 'when did I call mum' answers 'On Monday 26 October'
- C10 | audit-1031-composer:53 | A one-line note in a script without spaces or Latin stops is read as a title-only note | open: not probed (needs a CJK note in the seed); recorded in bc-1111.md

**BC4 (composer, 20 rows)**

- C11 | audit-1031-composer:54 | With a note open, "what dates are in this" and every other open-note question outside made, edited and le | stale: rechecked 2026-11-11: tests/test_composer_cfix_1031.py C10 and C11; probe: 'what dates are in this' on the open Packing note says it has no date
- C13 | audit-1031-composer:56 | A verb-first diary line gets "you" as its subject whatever the verb, and a "Diary | stale: rechecked 2026-11-11: cfix C13; probe: 'what do I know about Arrival' gives 'it rained all day, and you baked banana bread and watched Arrival'
- C14 | audit-1031-composer:57 | A group sentence says every member shares a tag that only some carry | stale: rechecked 2026-11-11: cfix C14; probe: the meeting group sentence names no non-holder
- C15 | audit-1031-composer:58 | The event count for an activity counts the newest dated sentence only | stale: rechecked 2026-11-11: cfix C15 (since skips a note-level 'ran twice'); probe: 'how many times did I run' counts four runs
- C16 | audit-1031-composer:59 | The answer to a "when did I" or "how long do I" is the top note's first sentence; the asked property sits | stale: rechecked 2026-11-11: cfix C16; probe: 'when did I bake banana bread' and 'how long do I bake' lead with the asked slot
- C17 | audit-1031-composer:60 | "The short version of X" and "give me the short version" are not read as summarise, so an unrelated note | stale: rechecked 2026-11-11: cfix C17 and C47; probe: 'short version of X' summarises X
- C18 | audit-1031-composer:61 | "What am I reading" matches a question inside a note before the Books note | stale: rechecked 2026-11-11: cfix C18; probe: 'what am I reading' leads with the Books note
- C19 | audit-1031-composer:62 | "Notes mentioning X" asked as a question is a one-note fact in Ask and a three-note find in Chat | stale: rechecked 2026-11-11: cfix C19; probe: 'what do My notes mentioning test saY??' lists two notes in Ask
- C20 | audit-1031-composer:63 | Derived "nothing yet" and offer lines ride on answers they do not belong to | stale: rechecked 2026-11-11: cfix C20 (the overview's own filler lines belong to INBOX 1743: owned by 1743); probe: no offer line on the flights answer
- C21 | audit-1031-composer:64 | "Do you like me", "what do you think" and "ur mum" are answered from the nearest note, and a quoted picku | stale: rechecked 2026-11-11: cfix C21; probe: 'do you like me' and 'what do you think' get the companion reply, 'ur mum' asks what is meant
- C22 | audit-1031-composer:65 | A passing-mention note contributes its opening sentence, not the sentence that matched, so an overview en | stale: rechecked 2026-11-11: cfix C22; probe: the sourdough overview says the matching sentence (overview prose owned by 1743)
- C23 | audit-1031-composer:66 | Summaries show raw note emphasis and summarise one note for a plural ask | stale: rechecked 2026-11-11: cfix C23; probe: a summary shows no ** marks
- C24 | audit-1031-composer:67 | Four compare openers claim a process, side headings switch case, and a side's lines are dropped silently | stale: rechecked 2026-11-11: cfix C24 and test_composer_compare_1029.py; probe: compare headings start with a capital, no process opener
- C25 | audit-1031-composer:68 | The attempt-based rewording changes the facts, not only the words | stale: rechecked 2026-11-11: cfix C25; probe: a retry changes frames only
- C26 | audit-1031-composer:69 | "Nothing matched" fallbacks list the newest notes for a question that named a note property | stale: rechecked 2026-11-11: cfix C26; composer_dialogue._defining_ask answers 'which is the main note' after an overview
- C27 | audit-1031-composer:70 | The day-plan and recap shapes say what was made, not what was done, for "what did I do" (audit 1030 Z28 p | stale: rechecked 2026-11-11: cfix C27; probe: 'what did I do last weekend' says what the notes hold. Residual: a title-less diary note is linked by its whole line
- C28 | audit-1031-composer:71 | A quote is altered: a day is written into it, and "today" is replaced inside quotation marks | stale: rechecked 2026-11-11: cfix C28; probe: 'the Saturday being 24 October' sits outside the quotation marks
- C29 | audit-1031-composer:72 | A checklist's state is lost or misread in the open-note shapes | stale: rechecked 2026-11-11: cfix C29; probe: 'summarise this' on Packing says 'five items, two ticked'
- C30 | audit-1031-composer:73 | "What do I spend on X", "what's the total" and "total spend" do not read the budget note's amounts | fixed 2026-11-11: total spend names the regular amounts beside a single price (tests/test_composer_bc4_1111.py); the rest by cfix C30
- C31 | audit-1031-composer:74 | A title-less note is named four ways across the list shapes and the chips | stale: rechecked 2026-11-11: cfix C31; probe: week and month lists name the title-less note by its words

**BC5 (composer, 20 rows)**

- C32 | audit-1031-composer:75 | Reporting frames wrap things that are not speech | stale: rechecked 2026-11-11: tests/test_composer_cfix_1031.py test_c32 passes on this head
- C33 | audit-1031-composer:76 | Four footers say the same thing in four wordings, and the thing they say is a dangling promise | stale: rechecked 2026-11-11: tests/test_composer_cfix_1031.py test_c33 passes on this head
- C34 | audit-1031-composer:77 | Openers and closers claim a process or pad the answer | stale: rechecked 2026-11-11: tests/test_composer_cfix_1031.py test_c34 passes on this head
- C35 | audit-1031-composer:78 | A month is lower-cased by .capitalize(), and other words lose or gain capitals | stale: rechecked 2026-11-11: tests/test_composer_cfix_1031.py test_c35 passes on this head
- C37 | audit-1031-composer:80 | A one-line title-less note's whole line becomes a run-on with "and | stale: rechecked 2026-11-11: tests/test_composer_cfix_1031.py test_c37 passes on this head
- C38 | audit-1031-composer:81 | Japanese punctuation gets a Latin stop added | stale: rechecked 2026-11-11: tests/test_composer_cfix_1031.py test_c38 passes on this head
- C39 | audit-1031-composer:82 | The courses-and-study answer groups by a name that is not a course and includes a note with no visible bo | stale: rechecked 2026-11-11: tests/test_composer_cfix_1031.py test_c39 passes on this head
- C40 | audit-1031-composer:83 | Mixed citation styles in one answer and bare brackets after fragments | stale: rechecked 2026-11-11: tests/test_composer_cfix_1031.py test_c40 passes on this head
- C41 | audit-1031-composer:84 | Act confirmations: five wordings, an act that runs without confirm beside one that asks, "pin" answered a | stale: rechecked 2026-11-11: tests/test_composer_cfix_1031.py test_c41 passes on this head
- C42 | audit-1031-composer:85 | Chat has no per-answer follow-on chips; Ask has them | stale: rechecked 2026-11-11: tests/test_composer_cfix_1031.py test_c42 passes on this head
- C43 | audit-1031-composer:86 | Due lists and left-item lists put a blank line between bullets; a reminder on a note hides the note's own | stale: rechecked 2026-11-11: tests/test_composer_cfix_1031.py test_c43 passes on this head
- C44 | audit-1031-composer:87 | "What is my longest note" promises a list that is not in the text | stale: rechecked 2026-11-11: tests/test_composer_cfix_1031.py test_c44 passes on this head
- C46 | audit-1031-composer:89 | "I'm a better finder than a comedian" for "tell me a joke" while a jokes note exists | stale: rechecked 2026-11-11: tests/test_composer_cfix_1031.py test_c46 passes on this head
- C47 | audit-1031-composer:90 | The chips the composer offers under an answer are questions it then cannot answer | stale: rechecked 2026-11-11: tests/test_composer_cfix_1031.py C17 and C47 passes on this head
- C48 | audit-1031-composer:91 | "What's new with X" and "the latest on X" answer with the oldest note or a checklist item | stale: rechecked 2026-11-11: tests/test_composer_cfix_1031.py C48 (test_c48 headings) passes on this head
- C49 | audit-1031-composer:92 | A link's reason is never said: the group line says "You linked A to B" and a question about the link gets | stale: rechecked 2026-11-11: tests/test_composer_cfix_1031.py test_c49 passes on this head
- E4 | audit-1107-composer-r2:24 | after "what do I know about José" | stale: fixed, tests/test_composer_r2_1107.py passes on this head (audit row says Fixed)
- E5 | audit-1107-composer-r2:25 | chain: "tell me about the Tokyo trip" / "where is it" / "what should I pack" / "when does it start" | stale: fixed, tests/test_composer_r2_1107.py and test_composer_r5_follow_1108.py passes on this head (audit row says Fixed)
- E9 | audit-1107-composer-r2:29 | "which is cheaper, Lisbon or Tokyo", "Lisbon or Tokyo, which costs more", "who is older, Anna or Tom" | partial: rechecked 2026-11-11: 'which is cheaper' and 'costs more' compare the figures; 'who is older, Anna or Tom' still answers a gift line (no age comparison exists; needs a birth-year reader in composer_amounts)
- E10 | audit-1107-composer-r2:30 | "what do I know about Tom and Sara", "what do I know about Anna and José", "anna and josé", "what do I kn | stale: fixed, tests/test_composer_w7_1110.py and test_composer_each_subject_1109.py passes on this head (audit row says Fixed)

**BC6 (composer, 20 rows)**

- E16 | audit-1107-composer-r2:36 | "what did I do on 3 October" | partial | 1111: partial: line run-on (Phone 020 7946 0011 Dentist check-up) left, see bc6-1111.md
- E18 | audit-1107-composer-r2:38 | "what happened last week", "what did I write about in October" | open | 1111: left: repeat in the milk line, see bc6-1111.md
- E21 | audit-1107-composer-r2:41 | "what is my shortest note", "what is not done", "what did I tick", "which tasks are done", "what haven't | open | 1111: fixed 2026-11-11 (tests/test_composer_bc6_1111.py: which tasks are done, what isn't ticked)
- E24 | audit-1107-composer-r2:44 | "which notes mention the boiler", "list my notes about Lisbon", "what is my oldest note", "list everythin | open | 1111: stale 2026-11-11: probe on the seeded notebook answers it correctly
- P1 | audit-1107-composer-r2:47 | ux (code) | open | 1111: left: gating, see bc6-1111.md
- D1 | audit-1107-composer-r2:53 | Defining note does not lead for "what do I know about X" (round 1's fix leads a title only for "what is X | open | 1111: owned by 1743 (overview answer shape)
- D19 | audit-1107-composer-r2:59 | Chips from leftover words, now accumulating along a chain | open | 1111: left: chips not probed
- D22 | audit-1107-composer-r2:61 | Dead ends | open | 1111: stale 2026-11-11: probe on the seeded notebook answers it correctly
- D23 | audit-1107-composer-r2:62 | Four confirm wordings | open | 1111: left: client-side undo wording
- R3-8 | audit-1107-composer-r3:37 | "do I have anything on Wednesday" -> "I found three notes about “Wednesday”." (list of notes) but "what i | open | 1111: fixed 2026-11-11 for the todo ask (tests/test_composer_bc6_1111.py); the bare list ask does not yet ask which list
- R3-15 | audit-1107-composer-r3:49 | One title-less note, five names in five answers | partial | 1111: left: naming
- R3-17 | audit-1107-composer-r3:56 | "wat do i know abuot lisbn" -> "I read that as “what do i know about” | partial | 1111: stale 2026-11-11: probe on the seeded notebook answers it correctly
- R3-20 | audit-1107-composer-r3:59 | "who is Priya" -> "Priya comes up in two notes | partial | 1111: owned by 1743 (overview answer shape)
- R3-21 | audit-1107-composer-r3:60 | "have I been to Tokyo" -> "I found nothing in your notes about Tokyo." | partial | 1111: stale 2026-11-11: probe on the seeded notebook answers it correctly
- R3-22 | audit-1107-composer-r3:61 | "what am I reading" -> "Three, from your Reading note | partial | 1111: stale 2026-11-11: probe on the seeded notebook answers it correctly
- R3-25 | audit-1107-composer-r3:64 | "who is Priya" / "what do I know about the garden" / "what do I know about the boiler" -> "You wrote “She | open | 1111: owned by 1743 (overview answer shape)
- R3-27 | audit-1107-composer-r3:66 | after "what is the Lisbon trip" | partial | 1111: stale 2026-11-11: probe on the seeded notebook answers it correctly
- R3-28 | audit-1107-composer-r3:67 | "how long is the Tokyo trip" -> "Flights cost $900 return, leaving 3 April..." ("Staying in Shinjuku for | partial | 1111: stale 2026-11-11: probe on the seeded notebook answers it correctly
- R3-29 | audit-1107-composer-r3:68 | "when is my next dentist appointment" -> correct line then "None of these records discuss “appointment”." | open | 1111: stale 2026-11-11: probe on the seeded notebook answers it correctly
- R3-31 | audit-1107-composer-r3:75 | One-note notebook: "what is in my todo" -> "Your one newest notes, from today | partial | 1111: fixed 2026-11-11 (tests/test_composer_bc6_1111.py: no Todo note says so)

**BC7 (composer, 20 rows)**

- R3-32 | audit-1107-composer-r3:76 | as_of set (time travel): "what is in my notebook" -> "I found no mention of “notebook” | partial | 1111: stale 2026-11-11: probe on the seeded notebook answers it correctly
- R3-33 | audit-1107-composer-r3:77 | Chat acts: "add buy stamps to my todo" -> "When's good for a reminder to buy stamps? Tomorrow at 9, ..." | partial | 1111: stale 2026-11-11: probe on the seeded notebook answers it correctly
- R3-34 | audit-1107-composer-r3:78 | "From your Biology note, today | partial | 1111: stale 2026-11-11: probe on the seeded notebook answers it correctly
- R3-35 | audit-1107-composer-r3:79 | "tell me about the dentist" -> "six notes", "dentist" -> "five notes"; "Sara comes up in seven notes" vs | partial | 1111: fixed 2026-11-11 (tests/test_composer_bc6_1111.py: comes-up count)
- R3-36 | audit-1107-composer-r3:80 | chips: "What else have I saved about table is anna?", "...date is the biology Exam?", "...book am I readi | open | 1111: left: chips not probed
- D1 | audit-1107-composer:36 | Defining note does not lead when its title only contains the subject or the question names a titled note | partial | 1111: owned by 1743 (overview answer shape)
- D7 | audit-1107-composer:42 | Number and property questions answered by a sentence without the number | partial | 1111: fixed 2026-11-11 (tests/test_composer_bc7_1111.py: what does Tom want)
- D10 | audit-1107-composer:45 | Offers the composer makes that nothing answers; acts read as questions | open | 1111: left: yes after a card
- D13 | audit-1107-composer:48 | "Written today" and "as your X note has it" are bolted on every "when" and fact answer | open | 1111: stale 2026-11-11: probe on the seeded notebook answers it correctly
- D16 | audit-1107-composer:51 | Footers name words of the question that the answer did not need, or promise what is not there | open | 1111: stale 2026-11-11: probe on the seeded notebook answers it correctly
- D17 | audit-1107-composer:52 | Date answers: filler, repeated heads, recurring words placed on one date | open | 1111: stale 2026-11-11: probe on the seeded notebook answers it correctly
- D18 | audit-1107-composer:53 | Event questions are answered from the creation log | open | 1111: stale 2026-11-11: probe on the seeded notebook answers it correctly
- D19 | audit-1107-composer:54 | Chips are built from the leftover words of the question | open | 1111: left: chips not probed
- D20 | audit-1107-composer:55 | Compare and summary shapes | open | 1111: left: compare opener and repeated cite, see bc6-1111.md
- D22 | audit-1107-composer:57 | Dead ends where the notebook can answer | open | 1111: stale 2026-11-11: probe on the seeded notebook answers it correctly
- D23 | audit-1107-composer:58 | Act replies: wording and gaps | open | 1111: left: client-side undo wording
- D24 | audit-1107-composer:59 | Shapes differ by phrasing | open | 1111: stale 2026-11-11: probe on the seeded notebook answers it correctly
- D28 | audit-1107-composer:63 | Model-on parity (decision 75) not exercised | open | 1111: left: naming parity test
- P6 | audit-1108-perf:43 | composer_digest.py:1570 _subject_facts and :1447 _said_piece still present; raw_results cap not seen | open | 1111: left: perf
- F1 | fable-composer-1110:45 | Follow-on reads what the last answer showed | open | 1111: left

**BC8 (composer, 19 rows)**

- F3 | fable-composer-1110:78 | Next instruction knows what it acts on (follow_items.py, follow_dates.py built); "undo" after "delete it" | open | 1111: fixed 2026-11-11 for the bare delete (tests/test_composer_bc8_1111.py); undo after delete is client-side, left
- F4 | fable-composer-1110:99 | Social and meta turns read (composer_chat.py); bare reactions ("really?", "maybe"), "are you sure", "what | open | 1111: left: social turns, see bc6-1111.md
- F5 | fable-composer-1110:129 | Chips continue the conversation (composer_chips.py, chat_chips.py); small-talk replies still end with no | open | 1111: left: not examined this pass
- F8 | fable-composer-1110:177 | Defining note leads (composer_digest._best); "wats on my shoping list" typo, "do I have a dentist appoint | open | 1111: left: typo, dentist appointment, see bc6-1111.md
- F9 | fable-composer-1110:191 | Agenda clauses built (composer_plan._clauses); "this week" without a day is no clause, chips from the fir | open | 1111: left: not examined this pass
- F13 | fable-composer-1110:218 | a to g and k built; h ("the week before"), i (two summary shapes), j ("what links to it") left (g45-1110. | open | 1111: left: h and the who-am-I-going-with ask, see bc6-1111.md
- G1 | fable-composer2-1110:40 | Ask yes/newer-note: _newest_saying, supersede built (g13-1110.md); "when did I last see the dentist" read | open | 1111: left: how far did I run counts the goal, see bc6-1111.md
- G3 | fable-composer2-1110:64 | Reminders in Ask built (due_summary.py, composer_reminders.py); stats ask fifth wording, "agenda deadline | open | 1111: left: not examined this pass
- G5 | fable-composer2-1110:92 | Guide lead built (guide_lead.py, review_words.py); "how do I record a meeting" lead keeps "there", "where | open | 1111: left: not examined this pass
- G8 | fable-composer2-1110:149 | Companion remarks: dated thing in next three days via composer_plan, poke lines table avatars.js:2731 (g6 | open | 1111: left: not examined this pass
- G10 | fable-composer2-1110:172 | Reminder chip built; "call mum on sunday about christmas plans" loses "christmas" (reminder_parser.read_b | open | 1111: left: not examined this pass
- G11 | fable-composer2-1110:180 | Summaries/amounts/function words built; "which is cheaper", "how much more did I spend eating out", "whos | open | 1111: left: arithmetic in the route
- G12 | fable-composer2-1110:190 | Short form/resurfacing/starter chips built; Patterns sentence template, hedge-once-per-list and its five | open | 1111: left: not examined this pass
- G14 | fable-composer2-1110:201 | Smaller rows a to d, g, h, j partly; a, e, f not reproduced / chip code, "Something sometime" magic add | open | 1111: left: not examined this pass
- FX1 | fable-fix-1030:10 | Three pre-existing red composer tests at the 1030 base (test_composer_owner_1017 hello, test_composer_own | open | 1111: left: not examined this pass
- FX2 | fable-fix-1030:11 | Z59 (streak line pinned by test_composer_streak_1029), Z57, Z58, Z68, Z70, Z46 recast, Z23, Z26, Z27 (com | open | 1111: left: not examined this pass
- ~~FC2 | fablecomp-1031:19 | tests/test_complexity.py failed as merged (composer_digest, composer_lists, composer_study, agent.run_age | open | 1111: left: not examined this pass~~ **W34: stale** (w34-L3-1111.md)
- ~~1693b3 | owner-asks-audit-1108:132 | "whatcha doing" gets a companion line | open | 1111: left: not examined this pass~~ **W34: stale** (w34-unv2-1111.md)
- PAR1 | parity-1110:40 | Parity: contradictions with no model (supersede.current/older_dates; composer_suggest.py:361 _IMPERATIVE | open | 1111: left: not examined this pass

**BS1 (shell, 19 rows)**

- E33 | audit-1028-agent:45 | Guide answers are verbatim topic chunks (first paragraphs) rather than answers; several arrive with a "Re | owner call
- ~~E37 | audit-1028-agent:49 | The AI status control is a red circle with an x and only a visually hidden label; a sighted new user read~~ stale: level off is neutral (--chip-bg, --muted, 00-tokens-shell.css:1637-1650), red only for data-level error; no red x without a failure
- K11 | audit-1028-backend:17 | llm_api_key is stored in plain text in preferences.json; the 0700 folder only helps on POSIX | owner call
- K13 | audit-1028-backend:19 | MCP server: no auth, offers every non-destructive write tool plus web_search/read_url when enabled; separ | owner call
- K26 | audit-1028-backend:32 | Two schema systems: ad hoc _add_missing_columns/_ensure_indexes at every launch plus migrations/ and alem | owner call
- K27 | audit-1028-backend:33 | Dead routes (no frontend call; tests only) | owner call
- K32 | audit-1028-backend:38 | The page polls GET /reminders?include_done=false (a full page of 200 rows) every minute per open tab | open
- D25 | audit-1028-docs:29 | Doc styles are scattered across 11 CSS files (00-10) with only 1,102 lines in 09-editor.css | open
- ~~S23 | audit-1028-shell:29 | Palette has about 103 commands but no recent-first ordering or per-command shortcut hints~~ stale: palette ranks by use (paletteUsage, app-palette.js) and the preview pane shows the bound keys (paletteLight)
- ~~S28 | audit-1028-shell:34 | No wiki-style [[ ]] autocomplete while typing in notes~~ stale: typing [[ opens the note picker (editor.js:1244-1290 editorOpenMenu)
- ~~S30 | audit-1028-shell:36 | No pin-to-top for notes in the list~~ stale: pinned notes sort first (notes-list.js:1842, 3213) and the Favourites row
- ~~S31 | audit-1028-shell:37 | No bulk move to category or bulk tag from the selection bar~~ stale: #batch-bar has the move menu (#batch-category-host), Tags (#batch-tag), Favourite and Archive
- ~~S34 | audit-1028-shell:40 | No export of a single note to Markdown or PDF from the overflow menu~~ stale: the card menu has Download .md (entry-menu.js:118-121); PDF is not asked for elsewhere
- ~~S39 | audit-1028-shell:45 | Focus ring contrast and visibility inconsistent across custom controls~~ stale: scratchpad/ui-sweeps/focusring.js light and dark 1111: 317 stops, 0 under 2px or 3:1, min 3.56:1; the 5 ringless stops are the composer's own text fields
- ~~S41 | audit-1028-shell:47 | Touch targets under 24px in dense rows (WCAG 2.2 target size)~~ stale: 1029 rank 46 (tests/test_ui_targets_1029b.py) put a 24px floor and hit overhang under chips and rows; probe 1111 of every button, link, input and select on the default view: 0 under 24px
- ~~S45 | audit-1028-shell:51 | Reaching Settings sections takes three clicks; palette lacks deep links to each pane~~ stale: the palette searches every Settings row and opens its pane (app-palette.js paletteSettingRows)
- ~~S47 | audit-1028-shell:53 | No keyboard way to reorder or move between notes with j/k in the list~~ stale: ArrowUp/Down/Home/End walk the list (notes-list.js:2593), already marked s11-1110
- ~~S49 | audit-1028-shell:55 | No note version history view~~ stale: the card menu has History (entry-menu.js:108, openEntryHistory)
- ~~S55 | audit-1028-shell:61 | Settings labels use mixed case in places against sentence-case rule~~ stale: grep of index.html and the settings JS labels finds no Title Case copy; only theme names (Sage Study, Deep Ocean) and 'All Time' in the graph (graph owner, deferred)

**BS2 (shell, 19 rows)**

- ~~S56 | audit-1028-shell:62 | Toast stack can cover the bottom nav at phone width~~ stale: 390x844 probe 1111 with 4 error toasts: stack 606-660, tab bar top 787
- ~~S57 | audit-1028-shell:63 | Floating "New note" button overlaps content at 390px~~ stale: 390x844 probe 1111: the New note button is fixed at 729-773, 14px above the tab bar (787)
- ~~S60 | audit-1028-shell:66 | Reduced-motion handling not applied to every animation~~ stale: motion-still.css is the reduced-motion blanket, linked by theme-boot.js for data-motion=reduced; tests/test_motion_resolved.py holds it
- ~~S61 | audit-1028-shell:67 | Colour contrast of muted text in dark theme near threshold on chips~~ stale: contrast.js THEME=dark 1111: every tab and Settings section ok, none under 4.5:1 (empty notebook, no boards or maps)
- ~~S63 | audit-1028-shell:69 | Palette lacks "go to note by title" with live preview~~ stale: note results with snippets already show under the commands (paletteNoteHits, app-palette.js:31)
- ~~S64 | audit-1028-shell:70 | Mascot and avatar assets load even when disabled~~ stale: avatars.js and atlas.js are the lazy characters bundle, fetched at idle (lazy-entries.js:82, index.html:16096); boot probe 1111 with the companion off: 147 KB of it plus atlas-lazy.css, needed by Atlas's own marks, so a setting gate would break them
- ~~S65 | audit-1028-shell:71 | Service worker precache list not trimmed to boot-critical assets~~ stale: frontend/sw.js keeps no precache list: it caches stamped files on first fetch (header, lines 1-60)
- ~~S66 | audit-1028-shell:72 | 27 global-scope scripts raise collision risk; no lint for duplicate top-level names across lazy modules~~ stale: tests/test_global_scope_ratchet.py counts duplicate and total names across the bundles
- S70 | audit-1028-shell:76 | No note count per tag in tag chips | deferred: counts exist in the tag manager and the dashboard tag chips (dashboard.js:2645); counts on every card chip is a design call
- ~~S74 | audit-1028-shell:80 | a Headings row in the note card's~~ built s12b-1110 (Headings row in the card menu)
- S76 | audit-1028-shell:82 | No note linking preview on hover | deferred: hover preview on wiki-links is a new feature (M); citation-peek.js and attachment-peek.js are the recipe to follow
- S78 | audit-1028-shell:84 | Empty states differ in tone and illustration across views | deferred: empty-state recipe is a design pass across views, not a reproducible defect
- S79 | audit-1028-shell:85 | Icon set mixes stroke weights between nav and toolbars | deferred: index.html carries 4 ph-light icons among the regular ones; whether they are meant is a design call
- S80 | audit-1028-shell:86 | Card shadows and borders vary between Library and Notes | deferred: measured 1111: Notes card border 1px transparent, tint rgba(31,36,48,0.04), radius 8px; Library card border 1px rgb(227,225,221), white, radius 6.4px; both no shadow; a design call whether they should match
- S81 | audit-1028-shell:87 | Settings has dense long panes with no sticky section index | deferred: Settings has a section nav (#settings-nav); a sticky index inside a long pane is a design call
- ~~S82 | audit-1028-shell:88 | Segmented view toggle lacks labels for first-time users~~ stale: both buttons have title and aria-label (index.html:2535-2540)
- ~~S84 | audit-1028-shell:90 | Onboarding cannot be re-opened from Help~~ stale: Take the tour is in Help and the palette (first-run.js:197, 335), already marked s11-1110
- S85 | audit-1028-shell:91 | Error toasts say what failed but not what to do | deferred: toast() already takes an action ({ action: [label, fn] }, status.js:347); adding one per error is a sweep of call sites
- S86 | audit-1028-shell:92 | Library to notes round trip needs 3 clicks | deferred: shortcut design, not reproducible as a defect

**BS3 (shell, 19 rows)**

- ~~S88 | audit-1028-shell:94 | utility~~ stale: highlightInto marks search terms (notes-list.js:1148-1224), already marked s11-1110
- ~~S89 | audit-1028-shell:95 | utility~~ stale: Settings, Data has Export JSON, CSV, Markdown, folder and full backup, each with a title, plus an About exports popover (index.html:13604-13623)
- ~~S91 | audit-1028-shell:97 | Page language and title do not update on view change~~ stale: status.js:505-518 pageTitle.view is set per view by the router; <html lang> is a fixed en
- U19 | audit-1028-ux:25 | Mind map | open
- U20 | audit-1028-ux:26 | Code editor | open
- U23 | audit-1028-ux:29 | Mind map phone | open
- U30 | audit-1028-ux:36 | Polish | open
- U31 | audit-1028-ux:37 | Documents | open
- U36 | audit-1028-ux:42 | Doc dark | open
- U37 | audit-1028-ux:43 | Code editor | open
- U39 | audit-1028-ux:45 | Polish | open
- U41 | audit-1028-ux:47 | Board | open
- ~~U42 | audit-1028-ux:48 | Consist~~ stale: #library-boards-filter margin is calc(var(--space-6) - var(--ring-room)) (08-consistency.css:10491)
- U45 | audit-1028-ux:51 | Consist | open
- U49 | audit-1028-ux:55 | Board | open
- H12 | audit-1029-harness:43 | The report's top lag row: 17 frames of 202 to 1,682 ms after a pointerdown on button#settings-nav-models | deferred: same as HR18; needs a performance trace of Settings > Models, not a code reading
- ~~N17 | audit-1029-notes:52 | 240 wiki-link chips in the list share one accessible name, "Go to the note starting “Atlas project”", so~~ fixed 7032dd106: entry-card.js names each icon button after its note ("Edit this entry: Lisbon trip"); live probe 1111 on two notes read distinct names for all eight buttons
- ~~A35 | audit-1030-ai:66 | Not a bug: the focus is a glow on .nm-buddy-face::before (owner decision 2026-10-11); the audit read the~~ closed ff5ac76 (not a bug)
- ~~Y7 | audit-1030-extras:122 | Still open (W7): the bell lists the app's own housekeeping as news to a new person~~ fixed a9f6aea

**BS4 (shell, 19 rows)**

- ~~Y18 | audit-1030-extras:133 | Writing room with no model still says "No model connected" twice (the model select and the banner), W27 n~~ fixed a9f6aea
- AR2 | audit-1031-architecture:28 | One global scope of 10,000 names | deferred: the global-scope ratchet (tests/test_global_scope_ratchet.py) holds the number; wrapping files whole is an ongoing step
- AR5 | audit-1031-architecture:31 | The page carries every surface in one document | deferred: one-document page is an architecture decision, not a batch fix
- BK12 | audit-1031-backend:24 | The page polls GET /reminders?include_done=false every minute per tab (1028 K32); 5.6 KB per poll here, a | partial: one tab polls and a hidden tab stops (status.js:556-566); the 200-row payload remains, same as K32
- ~~Z2 | audit-1031-extras:105 | One click on the status-bar timer chip stops it with no confirm, no pause and no Undo~~ stale: stopUtilityClock offers Undo with the time left (utility-tools.js:140-157)
- ~~Z6 | audit-1031-extras:109 | Questions, "Drop: it no longer matters"~~ stale: Drop toasts 'Dropped the question.' with Undo (questions-view.js:59-66)
- ~~Z7 | audit-1031-extras:110 | Sketch "Save as note" closes the pad, toasts "Sketch saved to your notebook." and leaves focus on body wi~~ stale: media.js:151 announceSavedNote with an opener
- ~~Z14 | audit-1031-extras:117 | The Voice note and Record dialogs show a "Live captions" button when no caption engine is installed; pres~~ stale: syncCaptionsDoors marks the doors captions-off when no engine is installed (meetings.js:2451-2456)
- ~~Z17 | audit-1031-extras:120 | settings-panes.js (a boot script) builds the palette rows "Count words" and "Translate this" around palet~~ stale: paletteCaughtNow guards with typeof paletteCaught (settings-panes.js:1179)
- ~~Z19 | audit-1031-extras:122 | A card dragged out of the Notes list cannot be dropped on a category in the sidebar, a tag, a space or a~~ stale (2026-11-11): obj-carry.js:21-25 `OBJ_FILE_DESTS`, :176-185 category and space renderers; tests/test_xfix_1031.py
- HR18 | audit-1031-harness:34 | Settings > Models (1029 H12) now opens with 9 long tasks of 53 to 95 ms at 1440 and 15,191 DOM elements p | deferred: needs a performance trace of Settings > Models (9 long tasks, 15,191 elements)
- ~~N8 | audit-1031-notes:54 | Date extraction turns "on the 14th of next month" into "Mentions month of Nov 30" (card chip and dates fi~~ stale: timewords.find on 'on the 14th of next month' gives 2026-11-14, precision day (1111, clock 2026-10-06); a bare month shows as 'Nov' (entry-card.js:859)
- ~~N10 | audit-1031-notes:56 | After Save from the capture bar there is no toast and the new note is not the first row (favourites sort~~ stale: capture-card.js:455 announceSavedNote
- ~~N12 | audit-1031-notes:58 | A note saved with YAML frontmatter shows title~~ stale: tests/test_frontmatter_title_1031.py
- ~~N13 | audit-1031-notes:59 | The palette cannot find a title-less note by its first words~~ stale: palette note rows come from the finder (app-palette.js paletteNoteRows)
- ~~N16 | audit-1031-notes:62 | Engine-backed filters (kind:, has:link, title:) cap at 50 and the heading reads "50 of 199" with no way t~~ stale: liveQueryBar says 'The first N notes that match this query, add words to narrow it' when capped (notes-lazy.js)
- ~~N18 | audit-1031-notes:64 | is:draft, has:attachment, in:bin and other unknown flags silently give 0 rows while is:untitled gets a no~~ stale: noMatchHint names the unknown filter and lists the real ones (notes-lazy.js:207); is:draft is a real flag
- ~~N19 | audit-1031-notes:65 | The finder explains a title: hit on a title-less note as "matched your words"; a title-only hit on a note~~ stale: search/engine.py _where_in_body says matched the first line or the text
- N20 | audit-1031-notes:66 | Card menu taxonomy: AI acts are split across "AI actions›" (Tag and file, Proofread, Title, Remove title) | deferred: menu taxonomy is a design call

**BS5 (shell, 19 rows)**

- ~~N24 | audit-1031-notes:70 | The Journal template fills "Journal~~ stale: stampDate writes 'Oct 31, 2026' (capture-ask.js:400)
- ~~N25 | audit-1031-notes:71 | "No similar notes found." with no meaning engine does not say why; the semantic toggle also gives no feed~~ stale: note-panels.js:72 and graph.js:3455 name the missing meaning engine
- ~~N26 | audit-1031-notes:72 | The capture help text ("What can I type in a note?") still says tables and code show as source; cards now~~ stale: the capture help says a note card draws tables, fenced code and quotes (index.html:1647)
- ~~N29 | audit-1031-notes:75 | harness~~ stale: seed-showcase.py:592 opens tessellate.db first
- ~~N34 | audit-1031-notes:80 | The [[ picker inserts the raw first line for a note whose title is a markdown heading~~ stale: editor.js editorLinkMatches strips the heading marker (N34 comment at the value line)
- ~~N39 | audit-1031-notes:85 | [[ picker rows without a preview read "Harbor launch plannote"~~ stale: rich-picker.js:147 joins the spans with a separator
- N44 | audit-1031-notes:90 | Reload does not restore the list state | partial: the filter words persist in sessionStorage 'note-filter' (notes-list.js:2376-2390); sort across a reload not checked
- ~~N47 | audit-1031-notes:93 | An inline edit saved while offline is not kept the way a new note is~~ stale: note-edit-panels.js:449 keeps an offline edit on the device like a new note
- ~~N48 | audit-1031-notes:94 | A deep link to a missing note (#/notes/999999) toasts "No such note." but leaves the dead hash in the bar~~ stale: capture-ask.js:905 returns the address to the list and clears the live region
- ~~N49 | audit-1031-notes:95 | The palette's "Open the bin" row (described "Everything you threw away, in the Library") lands on the Lib~~ stale: router.js ROUTE_LIBRARY has bin; app-features.js:554 has Unlock private notes
- SH12 | audit-1031-shell:23 | Settings panes block on open: Shortcuts 234 ms (275 nodes, 42 controls), Appearance 150, Templates 141, D | partial: 1111 probe on a loaded box (load 10): first open 964 ms (+3,203 nodes), Shortcuts 56, Appearance 195, Data 148, Templates 45, General 74, Models 238; the Shortcuts case is fixed, the rest need a quiet-machine trace
- D25 | audit-1107-composer:60 | Citations double up in the Ask and Chat text | owner call
- P4 | audit-1108-perf:41 | PARTLY FIXED (perfset-1108: listeners 921 to 588, Guide nodes 2,574 to 1,540; the pane-by-pane body build | partial: same 1111 numbers as SH12; first open still around 1 s here, the pane-by-pane build remains
- A68 | audit68-1101:9 | Learned-audit leftovers: per-flag Keep it action (settings-controls.js learnedCheckMark), a Settings swit | open W34: true (part), w34-L2r-1111.md.
- F7 | fable-composer-1110:159 | Voice: stat lines deleted, cite style, openers rewritten (tests/test_voice_1110.py); F7.3 "Read as" lines | owner call
- F12 | fable-composer-1110:212 | Offer accept/decline gate built (tests/test_composer_offers_1110.py); B26 Q5 and Q6 built 17d5d14 | owner call
- F14 | fable-composer-1110:234 | Model-on parity: closed rows in parity-1110.md; what a real model writes is unverified (fake transport on | owner call
- G9 | fable-composer2-1110:163 | Statistics ask built (tag noun before verb etc.); "summarise my week" tag clause, week_review comparison | open
- F6 | fable-eye-1030:54 | F6 model on and off disagree on money and checklist | owner call

**BS6 (shell, 19 rows)**

- F8 | fable-eye-1030:72 | F8 every answer re-reads every note | open
- ~~FC1 | fablecomp-1031:18 | Reset appearance (resetAppearance, settings.js) leaves avatar-buddy-motion and avatar-buddy-entrances as~~ stale: resetAppearance's key list includes avatar-buddy-motion and avatar-buddy-entrances (settings.js:3241)
- FIT55 | fitaudit-1109:6 | Rank 55 (PF2 idle): stop atlas rAF loops after 2 s of no input only while the companion is not walking, l | owner call
- FIT42 | fitaudit-1109:7 | Rank 42 (BK10, BK12, PF7): ?preview=300 adoption waits on server-side note search (Q9) | owner call
- FIT19 | fitaudit-1109:9 | Ranks 19, 21, 36, 37: worker layout and labels layer; surfaces as templates; JS files into IIFEs and rout | open
- 1607d | owner-asks-audit-1108:14 | Masculine facial expressions redrawn | open W34: owner-call (design), w34-unv1-1111.md.
- ~~1607e | owner-asks-audit-1108:15 | One-line summary at the top of every Help topic | open~~ **W34: stale** (w34-unv1-1111.md)
- 1667f | owner-asks-audit-1108:20 | Library d3 mousemove forced layout (757 ms) | open W34: true-deferred, w34-fix2-1111.md.
- 1667i | owner-asks-audit-1108:21 | Boot setTimeout forced layout, 560 ms canvas pointerout, 101 ms most-accessed render, 1207 ms unattribute | open W34: unverifiable, w34-fix2-1111.md.
- 1667m | owner-asks-audit-1108:22 | Frames with no script (337, 214, 240 ms) and codemirror requestMeasure | open W34: true-deferred, w34-fix2-1111.md.
- 1612c | owner-asks-audit-1108:24 | Manual pictures only where needed, as WebP made by the sweeps | open W34: owner-call, w34-fix2-1111.md.
- ~~S14 | owner-asks-audit-1108:27 | Diagram side panels collapsible; no need for the left panel | open~~ **W34: fixed** (w34-fix2-1111.md)
- 1643b | owner-asks-audit-1108:30 | Notes tab-switch pointerup 312 ms; dashboard 266 ms timer and 172 ms load frame | open W34: true-deferred, w34-fix2-1111.md.
- 1620categoriesb | owner-asks-audit-1108:32 | Find what wrote "¦" for "&" ("Courses ¦ Study") | deferred: no writer of the broken bar in src or frontend (grep 1111); the source is model output or an import, needs the owner's data W34: owner-call, w34-unv1-1111.md.
- 1620topicsc | owner-asks-audit-1108:33 | How "conversation" was derived for a gym note | open
- 1620lag:backdropandpointerout | owner-asks-audit-1108:34 | Settings backdrop click 880 ms; dashboard card pointerout 312 to 344 ms | open W34: true-deferred, w34-fix2-1111.md.
- 1692e/N15 | owner-asks-audit-1108:47 | Own activities with props (fishing, reading, beanbag, dinner, chasing sprites) | open W34: true, w34-unv2-1111.md.
- 1692n/S15 | owner-asks-audit-1108:49 | Wind-spirit travel: lean, trailing wisp, spiral on turn, motes, settle eddy; no ferocious blinking | open
- 1683i-climb/T5 | owner-asks-audit-1108:54 | Climb up the side of windows and of the screen | open W34: true, w34-unv2-1111.md.

**BS7 (shell, 19 rows)**

- 1683i-inspect/T8 | owner-asks-audit-1108:55 | Inspect things (window corner, clock, cursor, new window) | open W34: true, w34-unv2-1111.md.
- 1683deeper/B19 | owner-asks-audit-1108:59 | Deeper behaviour tree, many detailed actions; every-limb transitions | open W34: true, w34-unv2-1111.md.
- 1683s/U16 | owner-asks-audit-1108:61 | Load-dependent X11 test race fixed | open
- 1683y-ledger | owner-asks-audit-1108:63 | Coverage ledger first; the dive closes only when every row is built or has a reason | open
- ~~1670a | owner-asks-audit-1108:67 | Cut off on the ride; sits 20 px above the taskbar | open~~ **W34: stale** (w34-unv2-1111.md)
- ~~1670d | owner-asks-audit-1108:68 | Drag to hang anywhere on the top edge | open~~ **W34: stale** (w34-unv2-1111.md)
- 1670f | owner-asks-audit-1108:70 | No flicker or jolt; sits cleanly | open W34: hardware-only, w34-unv2-1111.md.
- ~~1670j | owner-asks-audit-1108:72 | Body and head turn to face the travel direction | open~~ **W34: stale** (w34-unv2-1111.md)
- ~~1670r | owner-asks-audit-1108:74 | Display-paced timer, 16.7 ms plus or minus 3 | open~~ **W34: fixed** (w34-unv2-1111.md)
- 1607c | owner-asks-audit-1108:76 | Smoother masculine shoulder-to-arm join | open
- 1667/1634a | owner-asks-audit-1108:77 | The throw must not scroll the page; Playwright test by mouse, touch, keyboard reading scrollY | open
- 1667b | owner-asks-audit-1108:78 | Throw frame step does no layout reads; under 4 ms a frame at 4x | open W34: true, w34-unv2-1111.md.
- 1667d | owner-asks-audit-1108:80 | Keep-up reads layout once a frame, stops while still | open W34: true, w34-unv2-1111.md.
- ~~1667o | owner-asks-audit-1108:85 | /chat/followups deadline; 5120 token context budget line | open~~ **W34: stale** (w34-fix2-1111.md)
- 1661j/S10 | owner-asks-audit-1108:92 | A further deep-dive round for features and look | open
- 1693a | owner-asks-audit-1108:94 | Autouse clock.today pin in conftest plus a lint | fixed: conftest.py _fixed_day autouse pins clock.today (the lint half not built)
- 1691 | owner-asks-audit-1108:95 | no BACKGROUND_MODE anywhere under src/ (grep, checked 2026-11-09) | deferred: no BACKGROUND_MODE in src (grep 1111); needs pytest -m evals with a real model W34: unverifiable, w34-fix2-1111.md.
- 1643a | owner-asks-audit-1108:96 | Graph redraws only while something moves | open
- ~~1620tag+ | owner-asks-audit-1108:97 | Add tags popover opens under the card's + Tag | open~~ **W34: fixed** (w34-fix2-1111.md)

**BS8 (shell, 18 rows)**

- 1620lag:models | owner-asks-audit-1108:100 | /models/status 3220 ms; stop the 30 s model job | open
- 904 | owner-asks-audit-1108:101 | The 86-item OneNote bug list | open
- N5 | owner-asks-audit-1108:103 | Edge hit squashes and slides, or wraps | open
- N9 | owner-asks-audit-1108:104 | Portal as travel and escape; share measured | open
- S16 | owner-asks-audit-1108:106 | Lower body and nebula change little per pose | open W34: owner-call, w34-unv2-1111.md.
- 1692composer | owner-asks-audit-1108:124 | Composer continuous improvement | open W34: skipped (composer spoke), w34-unv2-1111.md.
- ~~1683y-dynamic | owner-asks-audit-1108:125 | "Make it really dynamic ... also portalling" | open~~ **W34: stale** (w34-unv2-1111.md)
- ~~S18 | owner-asks-audit-1108:133 | Chat spasm; card, badge and Why stick after reload | open~~ **W34: stale** (w34-unv2-1111.md)
- 1606 | owner-asks-audit-1108:139 | Patting over Atlas's head must not lift it 30 px | owner call
- 1598 | owner-asks-audit-1108:140 | Scrolling Ask must not carry Atlas over the top bar | owner call
- 1671 | owner-asks-audit-1108:141 | Win+arrow snap resets to the unmaximised window | owner call W34: hardware-only, w34-unv2-1111.md.
- 1691b | owner-asks-audit-1108:142 | Paste the 15 s /chat/followups log if it returns | owner call W34: unverifiable, w34-fix2-1111.md.
- 1620tray | owner-asks-audit-1108:143 | Closing with X leaves a tray icon; companion shows over Wallpaper Engine | owner call W34: hardware-only, w34-unv2-1111.md.
- ~~T11 | owner-asks-audit-1108:144 | No 90 degree turn after landing | owner call~~ **W34: stale** (w34-unv2-1111.md)
- M8 | owner-asks-audit-1108:145 | Desk very lightweight | owner call
- N20 | owner-asks-audit-1108:146 | Desk look repaints at once | owner call W34: hardware-only, w34-unv2-1111.md.
- N22 | owner-asks-audit-1108:147 | Overlay wins over the card; twenty toggles | owner call W34: hardware-only, w34-unv2-1111.md.
- PAR3 | parity-1110:44 | Parity not driven: boards and maps tools, rename_tag/delete_tag by sentence, save_user_preference, check_ | open

**BK1 (companion, 24 rows)**

- X15 | audit-1029-extras:121 | Dashboard has about 13,250 DOM nodes with six notes, 16.6k to 19.9k after opening settings and dialogs | partial: Guide chat, Reminders, Timeline, Graph, Documents panes and the palette are templates (boot nodes 5,640 to 3,887); chat (533), library (529, nested board template) and notes (1,034) still parse at boot (x15-1111.md)
- ~~A36 | audit-1030-ai:67 | Esc on a companion menu returns focus to an anonymous kebab-opener.pointer-menu-anchor, not the companion | partial~~ fixed 6254337 (checked 2026-11-11)
- A37 | audit-1030-ai:68 | The companion fades to opacity 0 behind the Settings dialog; on phone it sits at about (314,728) over the | open
- ~~Z18 | audit-1031-extras:121 | Background art, when on, costs 0.203 s of script per 5 s (about 4 percent of one core) at 20 fps on this | open~~ fixed 405fbdcaf (12 fps after 30 s without a pointer; checked 2026-11-11)
- ~~HR23 | audit-1031-harness:39 | Pane opens with long tasks at 390 | open~~ fixed (Logs row grid 62,573 to 5,090 px; Memory poof not reproduced; audit-1031-harness.md:98; checked 2026-11-11)
- ~~UX3 | audit-1031-ux:17 | 70 animations run while nothing happens | open~~ fixed 0519dd52a (loops pause after 20 s without input; 77 to 37 endless, task about 4.3 to 3.8 s per 10 s, noisy; checked 2026-11-11)
- P8 | audit-1108-perf:45 | chat answer render path as cited; not re-measured | closed 2026-11-11 (stale: D9 built s58left3-1110)
- 1607b | owner-asks-audit-1108:13 | Masculine Atlas head size and shape against the feminine reference | open W34: owner-call (design), w34-unv1-1111.md.
- B16 | owner-asks-audit-1108:16 | Masculine Atlas design pass (head, eyes, shoulder join, expressions) | open W34: owner-call (design), w34-unv1-1111.md.
- ~~1634c | owner-asks-audit-1108:17 | nameMarkBuddyBlend reads transformOrigin before and after its writes | open~~ **W34: stale** (w34-unv1-1111.md)
- ~~1634d | owner-asks-audit-1108:18 | No throw read in the first second after visibilitychange (5.6 s cold-window spotNow) | open~~ fixed cc0ca315d (a throw on a window just shown waits two frames; checked 2026-11-11)
- 1693b1 | owner-asks-audit-1108:29 | The chat area spasms up and down (Agent greeting, 1920x1270, scrollbars, companion on) | open
- ~~1643c | owner-asks-audit-1108:31 | Chat send keydown 712 ms, frame 589 ms in nameMarkBuddyTempo | open~~ **W34: stale** (w34-fix2-1111.md)
- N14 | owner-asks-audit-1108:35 | Live desk drawing only inside the CPU budget (idle under 1%, moving under 3%) | open
- ~~169200:35/S3 | owner-asks-audit-1108:41 | Built, partial and missing count for the owner; is everything built | open~~ done: counts line at the top of companion-asks.md (checked 2026-11-11)
- 1692c/g/N17 | owner-asks-audit-1108:43 | Two tracks: Atlas more detailed, generated companions own behaviour set | open W34: true (design), w34-unv1-1111.md.
- 1692g/N18 | owner-asks-audit-1108:44 | Every motion drawn every frame; in-app p95 under 8 ms at 4x CPU | open W34: hardware-only, w34-unv1-1111.md.
- 1692m/n/1683g/N11 | owner-asks-audit-1108:45 | The companion should sit on windows | open W34: true, w34-unv1-1111.md.
- 1692p-budget | owner-asks-audit-1108:46 | Live desk drawing within a CPU budget | open W34: hardware-only, w34-unv1-1111.md.
- 1692e/n/B1/B3/N16 | owner-asks-audit-1108:48 | Lower body and nebula follow the pose, distinct silhouettes per pose, desk and in-app | open W34: owner-call, w34-unv2-1111.md.
- 1692d(presence) | owner-asks-audit-1108:50 | Ambient activities by hour and mood on both companions (doodling, blanket nap, leg swing included) | open W34: true, w34-unv2-1111.md.
- ~~1683a | owner-asks-audit-1108:51 | Even desk frame pacing; real Windows frame interval logged | open~~ **W34: fixed** (w34-unv2-1111.md)
- 1683c | owner-asks-audit-1108:52 | Wisps and nebula move all the time, layered noise | open W34: owner-call, w34-unv2-1111.md.
- 1683lower-inapp | owner-asks-audit-1108:53 | In-app wisps measured at 1440; lower body by position; in-app parity | open

**BK2 (companion, 24 rows)**

- 1683x5/N10 | owner-asks-audit-1108:56 | In-app scrabble, pull-up, fling, miffed face | open W34: true, w34-unv2-1111.md.
- N2 | owner-asks-audit-1108:57 | Flail airborne, scrabble on a wall slide | open
- 1683l | owner-asks-audit-1108:58 | One shared mind for both companions | open W34: owner-call, w34-unv2-1111.md.
- ~~1683p | owner-asks-audit-1108:60 | One ledger of every companion ask | open~~ done: companion-asks.md re-graded with a counts line (checked 2026-11-11)
- ~~1683t | owner-asks-audit-1108:62 | Come here row on the in-app menu too | open~~ closed by decision: the in-app menu opens on the companion itself, so "come here" has no pointer to come to; "Call back and reset its place" (companion-menu.js:285) is the analogue (checked 2026-11-11)
- 1645 | owner-asks-audit-1108:64 | Polished goose-style overlay, default on Windows | open
- ~~1645scope | owner-asks-audit-1108:65 | Nothing that touches other windows | open~~ **W34: stale** (w34-unv2-1111.md)
- 1638b | owner-asks-audit-1108:66 | Companion does not show; root out why | open W34: hardware-only, w34-unv2-1111.md.
- ~~1670e | owner-asks-audit-1108:69 | Desk Quick search, Quick note and close button popups cleaned up | open~~ **W34: stale** (w34-unv2-1111.md)
- 1670i | owner-asks-audit-1108:71 | Slow idle; non-Atlas walks, runs, climbs, crouches, sits, lies | open W34: true, w34-unv2-1111.md.
- 1670l | owner-asks-audit-1108:73 | Nebula stops flickering (desk) | open W34: hardware-only, w34-unv2-1111.md.
- ~~1670u | owner-asks-audit-1108:75 | Runs properly on Linux | open~~ **W34: fixed** (w34-unv2-1111.md)
- ~~1560a | owner-asks-audit-1108:79 | Forced layout in nameMarkBuddyBeat; the #dash-grid pointerout handler | open~~ **W34: stale** (w34-fix2-1111.md)
- 1667e | owner-asks-audit-1108:81 | Under 16 ms forced layout per press (tab, Settings, pointerenter, atlas.js step) | open W34: true, w34-unv2-1111.md.
- 1667l | owner-asks-audit-1108:83 | 4.5 s avatars.js timer after opening a note from a dashboard list | open
- ~~1667n | owner-asks-audit-1108:84 | Desk perch filter finds almost nothing | open~~ **W34: stale** (w34-unv2-1111.md)
- 1620lag:Atlas | owner-asks-audit-1108:99 | avatars.js 2249 ms dashboard timer; nameMarkBuddyKeepUp 114 to 337 ms | open
- T1 | owner-asks-audit-1108:102 | Landing outcomes on both, prop tip-over included | open
- S1 | owner-asks-audit-1108:105 | Deep dives done; bugs, security and per-frame cost; plans after this PR | open
- ~~S20 | owner-asks-audit-1108:107 | Owner's logs: no desk travel targets; chat keydown 712 ms; tempo 589 ms; tab 312 ms; dashboard 266 ms | open~~ **W34: stale** (w34-unv2-1111.md)
- 1692p-log | owner-asks-audit-1108:121 | Trips to places with no window (taskbar edge, free corner, cursor's last rest); stop hiding when the app | open W34: true, w34-unv2-1111.md.
- 1692otrips/S6 | owner-asks-audit-1108:122 | Trips several times an hour in visible modes (portal, sparkle blink, cloud, bubble); legs per hour measur | open
- ~~1692f/S5 | owner-asks-audit-1108:123 | In-app wrap gets an exit and entry (squish with wisps), never an instant swap; in-app ambient acts | open~~ **W34: stale** (w34-unv2-1111.md)
- N25 | owner-asks-audit-1108:126 | Layered multi-round deep dives per surface | open W34: owner-call, w34-unv2-1111.md.

**BW1 (whiteboard, 28 rows)**

- K24 | audit-1028-backend:30 | God modules: whiteboard 6,123 lines, composer 5,221, tools 5,159, chat 5,023, entries 4,172, files 4,151 | open (1111: files 4,256 to 2,197 over routes_files_readings and routes_files_ocr; entries 4,423 to 3,776 over routes_entries_relations; settings 3,470 to 2,709 over routes_settings_transfer; left in k24-1111.md)
- K36 | audit-1028-backend:42 | list_boards and list_images: per-board loops with queries; timeline pulls all dates for the scrubber | fixed: wb_preview._preview_stamps_bulk groups the fingerprint across the page (tests/test_board_list_queries_k36.py: 31 statements for 3 and for 12 boards, 67 before); list_images was already batched and the timeline scrubber reads date-only rows
- B1 | audit-1028-board:5 | whiteboard.js is 25,012 lines; initWhiteboard alone is 4,064 lines (one closure holding most handlers), u | open
- B2 | audit-1028-board:6 | whiteboard-map.js is 10,810 lines, 350 functions; wbBuildMapNode is 369 lines | open
- B10 | audit-1028-board:14 | Native PDF export absent: PDF is browser Print > Save as PDF (by design comment), so no page size, no mul | open
- B15 | audit-1028-board:19 | Four overlapping drag/capture mechanisms (pointer capture, window pointermove, mousedown/mousemove/mouseu | open
- B23 | audit-1028-board:27 | wbBuildExportSvg is 342 lines and builds the SVG from live DOM (getComputedStyle per element via wbExport | open
- B24 | audit-1028-board:28 | Dead/duplicate markers: comments reference "decision 43", "INBOX 537", "MINDMAP_PLAN.md section 13a" inli | wontfix: the INBOX and decision numbers are the repo's cited-from-comments convention (CLAUDE.md); the MINDMAP_PLAN section 13a comment no longer exists
- B25 | audit-1028-board:29 | Minimap present (navigator) but its stale flag redraws all items on any render, so it lags on big boards | stale: a pan or zoom frame moves the rectangle and one transform (wbNavigatorUpdateViewport); items redraw only after a board render, which is when they move (whiteboard.js:3405-3420)
- B29 | audit-1028-board:33 | Text formatting: whiteboard-format.js exists (2,208 lines) but not audited for inline rich text in map to | partial: bold, italic and code render in topics (wbMapInlineText); an inline `[text](url)` does not (the Link door is the way); left
- B30 | audit-1028-board:34 | whiteboard-library.js (2,530 lines) and interchange (1,249) have no size-based lazy loading; all 27 class | stale: the library, templates and interchange scripts are in the lazy loader's list (app.js:1653-1660), not boot
- B33 | audit-1028-board:37 | 24 isFinite/NaN guards in whiteboard.js suggest NaN has leaked before; paths without guards (zoom, snap) | fixed: wbSnap returns 0 for a non-finite number (the typed zoom is clamped by its field) (tests/test_wb_nan_guards_b33.py)
- B39 | audit-1028-board:43 | Three module-level mutable singletons (wbDeleteSketchRef, wbRenderQueued, wbRenderFrame, wbNavState) with | stale: wbCancelBoardTimers (B31) resets wbRenderFrame and wbRenderQueued on a board switch; wbDeleteSketchRef no longer exists; wbNavState is marked stale by every render and its drag ends when the overview closes
- S71 | audit-1028-shell:77 | md and .txt dropped on the Notes tab become notes, with Undo (file-drop.js) | stale: built (file-drop.js onNotes: .md and .txt become notes with Undo)
- U1 | audit-1028-ux:7 | Board dark | stale: wbDefaultInk re-picks stored black or white at 4.5:1 (whiteboard.js:10337, tests/test_wb_board_1028.py)
- U2 | audit-1028-ux:8 | Board dark | stale: wbCoreInkFor picks the ink from the fill; stickies are created with ink #2a2a1f
- U3 | audit-1028-ux:9 | Board | stale: Enter on Sticky note places it at the view centre (CHANGELOG 1639)
- U5 | audit-1028-ux:11 | Mind map | stale: library-lazy.css counter-scales .wb-map-collapse and .wb-map-count to a 24px floor (CHANGELOG 1639)
- U13 | audit-1028-ux:19 | Board | stale: the button reads Sidebar (index.html:7258)
- U15 | audit-1028-ux:21 | Board | stale: Arrange is five submenu rows (tests/test_wb_arrange_submenus_u15.py, CHANGELOG 784)
- U17 | audit-1028-ux:23 | Board dark | stale: scratchpad/ui-sweeps/wbgripink.js dark 1440x900 on a sticky, a text box and a dark box: 7.96:1 (need 3:1)
- U18 | audit-1028-ux:24 | Board | stale: bw-1111 probe, 41 boards and 30 stickies at 1440x900 on a loaded machine: undo 33 ms to paint, board list open 32 ms, no long task
- ~~Y5 | audit-1030-extras:120 | Still open (X15, partly fixed)~~ fixed 57421a4b7 (unlock no longer builds Notes; page elements 7 s after login 2,725 to 1,705; checked 2026-11-11)
- BD7 | audit-1031-board:20 | Sizes: whiteboard.js 25,569 lines, 553 functions, initWhiteboard 4,090 lines; whiteboard-map.js 10,929 li | open
- ~~Z10 | audit-1031-extras:113 | sketch-pad.js is one 1,805-line closure ((() => {~~ stale (2026-11-11): map half fixed (tests/test_codemap_closure_z10.py, CODEMAP sketch-pad.js (143)); no JS ratchet exists; bg-art split left by default
- PF4 | audit-1031-perf:38 | Every boot parses the whole app | open
- ~~1667c | owner-asks-audit-1108:19 | notes-list.js:3559 still calls loadMapBoardIndex() at load (checked 2026-11-09) | stale: notes-list.js:3554 only walks the index when a page has a [[link]] (ensureMapChipsFor) and dash-boards.js when the widget draws; bw-1111 probe: 0 /whiteboard/boards requests in the first 3 s~~ **W34: stale** (w34-fix2-1111.md)
- 1694b2 | owner-asks-audit-1108:86 | Typed value field on diagram, whiteboard and mind map zoom | stale: map boards share the board's #wb-zoom-level valueField; bw-1111 probe on a new map board: input present, 100% shown, 150 typed + Enter reads 150%

**BD1 (documents, 27 rows)**

- D22 | audit-1028-docs:26 | 1.1 MB unminified documents.js (24k lines, 648 functions, 7.5k comment lines) plus 852 KB CodeMirror bund | deferred: L split of documents.js into lazy chunks needs an Opus design step; documents.js is 17,322 lines now (audit-1028-docs:26)
- D23 | audit-1028-docs:27 | Hot-spot functions: docLivePlugin 1,559 lines, docCmTheme 1,076, renderDocOutline 298, docTableGripsPlugi | deferred: L split by concern, docLivePlugin sits in documents-cm.js (audit-1028-docs:27). 1111 docs spoke: won't do beyond D21 (the view glue is carved; a 1,559-line plugin split by concern has no measured defect and risks the typing path)
- D28 | audit-1028-docs:32 | No continuous zoom (Ctrl+wheel / zoom % control) | deferred: text size is a three-step stepper (documents.js:9575 DOC_TEXT_SIZES, library-lazy.css:7354); a continuous zoom is an owner call (stepper or slider) (audit-1028-docs:32)
- D29 | audit-1028-docs:33 | Replace-in-all dialog has regex + case but no whole-word, no multiline/dotall flags, no per-document or p | stale (2026-11-11): documents-replace.js has whole word, per-match skip and a context snippet (audit-1028-docs:33)
- D34 | audit-1028-docs:38 | Autosave state is one tiny text ("Unsaved…", "Saved", "Not saved") in the status bar; failure sets .error | stale (2026-11-11): a save failure toasts once per run with Try again (documents.js:2736-2741 `docSaveFailedSaid`) (audit-1028-docs:38)
- D39 | audit-1028-docs:43 | Typo auto-correction rewrites words silently in any language and in prose-like code comments; undo toast | partial (2026-11-11): the Autocorrect switch is in the Editor menu (index.html:5407 `#doc-autocorrect`); a status-bar switch is not built (audit-1028-docs:43)
- D40 | audit-1028-docs:44 | Text-size only small/medium/large and word goal as separate controls; status bar has counts but selection | stale (2026-11-11): selection word count built (documents.js:10818) (audit-1028-docs:44)
- D41 | audit-1028-docs:45 | Word count present (status bar), goal, reading time | stale (2026-11-11): selection word count built (documents.js:10818) (audit-1028-docs:45)
- D42 | audit-1028-docs:46 | No spreadsheet view for CSV docs (SQL run reads them, but editing is raw text) | deferred: L grid view for csv/tsv (audit-1028-docs:46)
- D43 | audit-1028-docs:47 | No real-time collaboration or presence; conflict handling is hash-based 409 only | deferred: out of scope for an offline notebook, hash-based 409 stays (audit-1028-docs:47)
- D45 | audit-1028-docs:49 | Wordlist (871 KB) is fetched on first non-empty text and the dictionary is rebuilt as Set/variants in the | deferred: M, wordlist build in a worker (documents.js:11233) (audit-1028-docs:49). 1111 docs spoke: measured in node, split+trim+Set of 92,972 words is 30 to 36 ms once per session, under the 50 ms long-task line; a worker would add a message path for no measured gain; won't do
- D46 | audit-1028-docs:50 | Comment-to-code ratio ~32% in documents.js (7,570 of 23,963 lines); historical narration ("used to be", o | won't (2026-11-11): comments that say why are the house rule (CLAUDE.md section 7); 5,717 of 17,334 lines in documents.js are comments, no historical-narration lint exists (audit-1028-docs:50)
- D47 | audit-1028-docs:51 | Fallback <textarea> surface duplicated through aliases (value, selectionStart) so two code paths for ever | deferred: L, drop the textarea fallback (documents.js:231) (audit-1028-docs:51)
- D52 | audit-1028-docs:56 | Code editor: no multi-file workspace/tabs/split panes, no command palette inside the editor (only app pal | deferred: L, tabs and split panes in the code editor (audit-1028-docs:56)
- CE9 | audit-1031-code:21 | documents-code.js 6,289 lines, 30 addEventListener to 1 removeEventListener, docCodeScan 427 lines, docRu | deferred: L/M splits of documents-code.js and run_sandbox.py (audit-1031-code:21)
- DC7 | audit-1031-docs:19 | Opening the Documents tab loads the last document and then the one asked for | stale (2026-11-11): driven on :8909 from the dashboard to #/docs/10, requests were GET /documents then GET /documents/10, one open (documents.js:1119-1140 `asked` guard); the list refetch on return not re-measured (audit-1031-docs:19)
- DC10 | audit-1031-docs:22 | The fallback find bar (#doc-find-bar, #doc-find-input, #doc-find-count, #doc-replace-one, #doc-replace-al | fixed board1518-1101 (2026-11-11: `doc-find-bar` is in no frontend file) (audit-1031-docs:22)
- DC13 | audit-1031-docs:25 | Sizes: documents.js 24,437 lines, 673 functions, 232 addEventListener against 7 removeEventListener, docL | deferred: L, same split as D22/D23 (audit-1031-docs:25)
- ~~Z11 | audit-1031-extras:114 | Still open (Y5, X15): opening a surface pays for the hidden DOM~~ stale (2026-11-11): X15 templates, 073cc0c6b, 57421a4b7; Settings first-open stamp is the one-time cost, left by default
- N42 | audit-1031-notes:88 | The autocorrect typo table lives twice and has drifted | stale (2026-11-11): one table, `DOC_AUTOCORRECT = AUTOCORRECT_TYPOS` (documents.js:11347) (audit-1031-notes:88)
- PF6 | audit-1031-perf:40 | The page is heavy and some of it does not come back | deferred: listener growth on timeline/dashboard redraws, not documents (audit-1031-perf:40)
- DX1 | audit-1102-docs:30 | partial: the 4x gate is not met (row status); a29i-1102.md holds the rest | partial: the 4x typing gate stays open, a29i-1102.md holds the rest (audit-1102-docs:30)
- DX21 | audit-1102-docs:50 | At 390, #doc-counts is 0 px wide, still visible and in the tab order (tabindex 0) | partial (2026-11-11, 390 touch on :8909): `#doc-counts` tabindex -1 at width 0 and the footnote reference is 30x29 live and 45x47 read, fixed ee5f5a033; the task box is still 18x18, found not fixed (audit-1102-docs:50)
- P9 | audit-1108-perf:46 | menus.js:59 closeActionMenusOnScroll still present | stale (2026-11-11): the row only noted the handler exists; it is guarded (menus.js:59-75, 200 ms after a menu opens), no defect (audit-1108-perf:46)
- D1.1 | diagram-fable-1679:11 | The page is a text document's page | fixed 29d4ad4e5 (diagram-fable-1679:11)
- FIT22 | fitaudit-1109:8 | Rank 22 (PF6, DC7, CE9, DC13): mechanical splits of documents.js (17,163 lines now) and run_sandbox behin | deferred: mechanical splits of documents.js and run_sandbox.py, L, Opus design (fitaudit-1109:8)
- 1667j | owner-asks-audit-1108:82 | Documents lag (atlas-motion loop, documents.js timer, /documents/7, tab-switch style) | deferred: atlas-motion loop and tab-switch style are outside documents; not re-driven (owner-asks-audit-1108:82)
- ~~F1 Citations: the Cite row is a free-text prompt, so a note title is stored as plain text, not `[[title]]` | bd-1111.md~~ **Fixed doc-citation-picker-1111** (a note picker; `[[title]]` source line, a link in Read; driven at 1440 and 390 in dark)

**BH1 (chat, 21 rows)**

- E43 | audit-1028-agent:55 | /chat/tools/execute runs any registry tool with client-supplied arguments after "Confirm", with nothing t | deferred (2026-11-11): /chat/tools/execute (routes_chat.py:2429) is also the path of the composer act cards (answer-kit.js:2238), Undo and chat-agent.js; signing the parked call needs composer_*.py to sign what it parks
- E44 | audit-1028-agent:56 | chatSendTurn is a single 1,164-line function holding the stream handlers, checkpointing, timeline wiring | deferred (2026-11-11): refactor of chat-turn.js chatSendTurn (about 1,190 lines), no row-sized slice
- E45 | audit-1028-agent:57 | Five AI surfaces with separate stream consumers and renderers | deferred (2026-11-11): five stream consumers, one-AnswerStream refactor
- E48 | audit-1028-agent:60 | Edit and resend destroys the later replies (undoable) instead of keeping versions | deferred (2026-11-11): conversation branches need a stored shape and a pager, an owner design call
- E51 | audit-1028-agent:63 | Citation superscript lands mid-sentence | deferred (2026-11-11): the lead phrase table is composer_*.py, another agent's file
- E58 | audit-1028-agent:70 | Prompt size is modest (agent turn on a 4,096 window | partial (2026-11-11): the saved-chat list does not flash (showSkeletons returns when rows exist, notes-list.js:2991); the refetch per checkpoint stays (sheets-selects.js:1833)
- E59 | audit-1028-agent:71 | No per-answer feedback (thumbs, "that was wrong") that feeds the app's own learning; only insight lines h | deferred (2026-11-11): a thumbs or Not right store that feeds learning is an owner call (what it teaches, and consent)
- E60 | audit-1028-agent:72 | Not found: regenerate with a different model or persona from the answer's menu; "continue" after Stop (on | fixed 61cc1d8e7 (chat-turn.js: a stopped plain answer offers Continue; tool and skill runs had Resume). Regenerate with another model stays open
- E62 | audit-1028-agent:74 | Regenerate for composer answers re-words an act confirmation ("attempt" changes the phrasing) but not the | deferred (2026-11-11): composer retrieval widening, composer_*.py
- E70 | audit-1028-agent:82 | Edit-and-resend and regenerate re-run web search and tool calls in agent mode as well (same call path as | stale (2026-11-11): Regenerate and Edit ask first when the answer wrote (chat-edit.js:205 confirmRerun, dataset.wrote from chat-turn.js:644); web search is a read
- S93 | audit-1028-shell:99 | Test coverage for the flashEntry not-in-DOM path absent | fixed 0d5270bdd (tests/test_flash_entry_missing_s93.py)
- Z70 | audit-1030-composer:210 | The model's context text for each note starts with the [Uncategorised] label and the (written Sunday 18 O | fixed e77ad4072 (no Uncategorised label) and 61cc1d8e7 (a linked, unmatched note is a 240-character line; librarian.py)
- AI23 | audit-1031-ai:41 | Files in this scope over the 800-line bar | deferred (2026-11-11): file splits (avatars.js, routes_chat.py and others), refactors
- AR1 | audit-1031-architecture:27 | Routes are the data layer. 359 ORM queries (session.query( or select() sit in api/routes_.py against 185 | deferred (2026-11-11): repository layer over 359 route queries, a design pass
- BK11 | audit-1031-backend:23 | God modules remain (1028 K24, K25 partly) | deferred (2026-11-11): god-module splits; _start_tray and _run_desktop are Windows paths
- C12 | audit-1031-composer:55 | A follow-on loses its subject: in Ask every time (the Ask client sends no objects), in Chat for every for | deferred (2026-11-11): Ask follow-on subject, composer_*.py and the Ask client
- C36 | audit-1031-composer:79 | Grammar slips in fixed frames | deferred (2026-11-11): the routes_chat.py sentence is gone; the remaining frames are composer_tables.py, another agent's file
- P7 | audit-1108-perf:44 | routes_chat.py:575 _composed_chat still present; the 8 s probe not re-run | deferred (2026-11-11): the first question after a silent model pays the probe once (ollama_client.is_running, then cached quiet); skipping it for exact classes is a stream-flow change to test against a real slow model
- ~~1612b | owner-asks-audit-1108:23 | no summary lead lint in tests/test_manual_parity.py (grep, checked 2026-11-09) | fixed 8e051339a (test_manual_parity.py::test_every_listed_topic_has_a_one_sentence_lead)~~ **W34: fixed** (w34-fix2-1111.md)
- ~~1693b2 | owner-asks-audit-1108:131 | Note card, badge, Why trail and timing survive a session switch | fixed 741dc1f7a (tests/test_chat_reload_by_1693.py)~~ **W34: stale** (w34-unv2-1111.md)
- PAR2 | parity-1110:41 | Parity: model chips carry only the cited note chips, not the composer next chips (chat_turn.py model_chip | deferred (2026-11-11): the composer's next chips need its result frame (chat_chips.continue_chips, composer_chips); a model turn has none

**BG1 (diagram, 15 rows)**

- D1.3 | diagram-fable-1679:13 | diagram-lazy.css:741 and :757 still hide .ph-text inside .dgm-tight | fixed b8475fc09
- D1.8 | diagram-fable-1679:18 | One branch is silent. Off "Valid?" the first arrow got no words (C --> D), the second asked "Words for th | fixed 5017d6e06
- D1.12 | diagram-fable-1679:22 | R11 left: Done still saves silently (not re-driven) | stale (2026-11-11)
- D2.1 | diagram-fable-1679:30 | handles, pick and reconnect landed; reverse and connector delete bar not confirmed | deferred
- 1661m | owner-asks-audit-1108:25 | Both diagram side panels fold to a rail with a labelled toggle and key, kept per user; blind test | fixed ff33cd1fe
- S11 | owner-asks-audit-1108:28 | Diagram kind picker alone on its row | fixed 262c70da3
- 1692b | owner-asks-audit-1108:42 | Deep dives (desk, in-app, diagram) each with a coverage table and ranked list | deferred W34: skipped (docs deliverable), w34-unv1-1111.md.
- 1661a | owner-asks-audit-1108:88 | Builder picture-first; the blocks list an outline that hides | stale (2026-11-11)
- 1661c | owner-asks-audit-1108:89 | Templates, styles, align and distribute, find, copy as picture, shortcuts | deferred
- 1661e | owner-asks-audit-1108:90 | Each connection once under its source as "to Y" with an editable label | stale (2026-11-11)
- 1661f | owner-asks-audit-1108:91 | Connect handle and on-picture controls meet 3:1 on both themes | fixed b8475fc09
- 1661k | owner-asks-audit-1108:93 | Kind picker as a labelled Kind menu in the Title row with samples | fixed 262c70da3
- 1661g/S7 | owner-asks-audit-1108:127 | Arrow-added node does not overlap (0 in 20 adds); overlays follow scroll | fixed b006cfaf9
- 1661h/S8 | owner-asks-audit-1108:128 | A press on empty canvas and Escape clear the selection | fixed b006cfaf9
- 1661i/S9 | owner-asks-audit-1108:129 | Name Canvas and Blocks for what they are | fixed b006cfaf9

**BR1 (graph, 16 rows)**

- K25 | audit-1028-backend:31 | 18 functions over 150 lines: _start_tray 346, _build_graph 324, _run_desktop 324, _optimization_pass 323 | deferred (2026-11-11): _build_graph and _optimization_pass are now under 150 lines; _start_tray 350 and _run_desktop 296 in __main__.py are the Windows tray and desktop launch, unverifiable here
- S52 | audit-1028-shell:58 | Graph has no search-to-focus node field on the main bar | stale (2026-11-11): #graph-search is the find box (index.html, graph.js:2317)
- G3 | audit-1029-graph:27 | 2,000 notes: cold layout takes about 28 s to the worker's end message at both 1x and 4x | fixed 2026-10-30 (graph-1030: plain frames while a big map moves; 25 to 9-10 s); not re-measured at 2,000 notes on this loaded machine
- G5 | audit-1029-graph:29 | 500 notes at 4x CPU (a mid phone or old laptop) | fixed ca46ad4e5 (graph-canvas.js: camera and hover frames composed from cached layers)
- G7 | audit-1029-graph:31 | At 500 notes there are zero labels at fit, and the 81-link hub is unnamed, which contradicts the 2026-09- | owner call (2026-11-11): measured 0 of 12 wanted at the fit and 4 of 183 at 3x on a 500-note random fixture (graphlabels.js); INBOX 693 ended the landmark waiver (gcPlaceLabels, graph-canvas.js:640): a name never sits on a dot or line, so a hub with no free place is unnamed until zoom. Guaranteeing hub names needs that rule relaxed
- G8 | audit-1029-graph:32 | At 36 notes, 4x CPU: wheel zoom p50 33 ms with 14 of 59 frames over 50 ms; hover shows 12 long tasks of 5 | fixed ca46ad4e5 (graph-canvas.js, cached layers)
- G28 | audit-1029-graph:52 | /graph payload is 1.45 MB at 2,000 notes (slim 830 KB), 0.34 s, gzip on | stale (2026-11-11): the map asks /graph?slim=1 (graph.js:1815); at 500 notes slim 199 KB against 348 KB full
- BK10 | audit-1031-backend:22 | /library?limit=50 answers 235 KB and /graph 289 KB at 530 notes (22 KB gzipped for graph); /entries?limit | stale (2026-11-11): /library rows carry a 160-character preview (routes_library.py _clip, 128 KB at 500 notes); /entries sends content on purpose, it is the feed
- GR2 | audit-1031-graph:16 | Interaction at 4x: 506 notes hover sweep p50 52 ms (28 of 54 frames over 50 ms, tasks to 409 ms), wheel p | fixed 4dca18a15, ca46ad4e5 (graph-canvas.js: hairlines while moving, cached layers)
- GR3 | audit-1031-graph:17 | Search at 2,000 notes and 4x: typing 14 characters costs 34 long tasks summing 4.6 s, one of 1,228 ms; at | fixed (graph.js:2353 GRAPH_SEARCH_GAP_MS, query-only cheap draw)
- GR5 | audit-1031-graph:19 | Adding one note from the map re-runs the whole layout | fixed c7b7fb47a (graph-canvas.js:5720 GC_ADD_ALPHA, new notes seeded beside links)
- GR9 | audit-1031-graph:23 | gcDraw 809 lines, gcWireInteraction 467, renderGraphCanvas 366, gcStartWorker 290; graph.js 71 addEventLi | deferred (2026-11-11): splitting gcDraw/gcWireInteraction/gcStartWorker is a multi-day refactor of one hot file, not a row-sized change
- PF10 | audit-1031-perf:44 | The graph draw loop while settling | partial: fixed 20ed22a (label fades); a dirty rectangle per worker tick stays open (graph-canvas.js gcRequestDraw)
- 1620topicsb | owner-asks-audit-1108:98 | Manage topics like tags (rename, merge, remove a note) | owner call (2026-11-11): topics are derived from structure; a rename is stored (PUT /graph/topics/name, routes_graph.py:1472) but merge and remove-a-note have no stored meaning until the owner says what a manual topic is
- Z3 | audit-1031-extras:106 | "Tools and features" says "212 things Tessellate can do" and omits about 60 of the palette's own rows | stale (2026-11-11): featureCatalog draws from paletteCommands (app-features.js:235)
- G6 | fable-composer2-1110:124 | Dashboard greets once and quotes titles (greeting_compose._NEEDS); count bits in dashboard.js:526-532 aft | stale (2026-11-11): built, tests/test_dashboard_greeting_g6_1110.py, greeting_compose._NEEDS

**BA1 (agent, 15 rows)**

- K20 | audit-1028-backend:26 | Import of a memorymap folder: record['file'] raised KeyError becomes a 500 for a malformed sidecar | stale (2026-11-11)
- K33 | audit-1028-backend:39 | _sweep_expired scans every token on every authenticated request, and BodyCap calls _session_is_live per n | fixed 8d9cfce9e
- K38 | audit-1028-backend:44 | /auth/media-link tickets live 120 s and are reusable, delivered in a URL query that reaches uvicorn's acc | fixed 8d9cfce9e (log redaction; single use left, a PDF viewer asks ranges more than once)
- S20 | audit-1028-shell:26 | Cache prefix still carries the old product name | stale (2026-11-11)
- A9 | audit-1030-ai:25 | The web-down message drops the port (shows 127.0.0.1 for 127.0.0.1:8888) and gives the same advice twice | deferred
- A15 | audit-1030-ai:36 | Bare-verb forms miss in many classes (bare-not-ok of total) | fixed 1d3da33, 0ba1a33
- A17 | audit-1030-ai:38 | Covered by test_audit_1030_ai_acts | fixed ff5ac76
- A24 | audit-1030-ai:55 | #web-search-history is empty after a search | stale (2026-11-11)
- A25 | audit-1030-ai:56 | Not a bug: .answer-citation-link::after already pads the hit area to var(--target-min); the audit measure | closed ff5ac76
- A30 | audit-1030-ai:61 | After Clear history the badge still reads "99+" until reload (list is empty, a fresh load hides it) | stale (2026-11-11)
- A43 | audit-1030-ai:70 | unverified | unverified
- A44 | audit-1030-ai:71 | The no-model Chat answer to a question with an attached note ("what does it say" with Gift ideas attached | deferred
- A42 | audit-1030-ai:80 | Streaming at 4x CPU throttle (30 chunks/s for 4.9 s) | fixed 6254337
- BK3 | audit-1031-backend:15 | Workspace scope trusts any header value | fixed (s8, verified 2026-11-10)
- C8 | audit-1031-composer:51 | A plural or inflected subject word is required verbatim, so notes titled with the singular are called mis | deferred

## PR 216 close-out: inbox, handover and remaining lists (2026-11-11)

Scope: INBOX, HANDOVER, OPEN.md (work-order rows W0 to W34 and F1 to F8, "From the 22-10 bug doc", "Everything open"), SESSION_BRIEFS and the other ~470 `agent-remaining/*` files. Not here: the `*_PLAN.md` rows, ROADMAP, BACKLOG (one plan per PR, later) and the `audit-*` and `fable-*` files (another inventory). Docs only; no code was changed and no app was run. Status words: **fixed** only with a pointer; **open**; **owner call** (the question is named); **unverifiable** (real Windows, a real model, a touch device, the owner's data).

How it was built, and its limits:
- Read in full: INBOX (19 items), HANDOVER top blocks and every "Now" line, the work order, SESSION_BRIEFS headings and each unmarked brief's E19 stamp, and the Left, Not verified and Found-not-fixed blocks of the 1109, 1110 and 1111 files. Older files (1101 to 1108, 1026 to 1031, the a28 to a31 series, ~345 files) were not re-read line by line: their open lines were already stamped "Open (checked 2026-11-09)" (214 lines in 30 files) or sorted by the E17 scout into 636 true / 31 stale / 10 fixed bullets of this file's older sections (`e17-1110.md`, by batch). Those 636 are carried below as counted groups (rows X1 to X24), not itemised; the scout's keyword batching is a first sort and some overlap the named rows.
- "Merged" means one row with every source listed. Fixed rows were spot-checked in code or CHANGELOG (see "Spot checks").

### Rows

Columns: id | item | sources (file:line) | status | batch

**INBOX and HANDOVER, owner words**

| id | item | sources | status | batch |
| --- | --- | --- | --- | --- |
| I1 | Graph categories selectable on Map and Tessellation (hover rim, click selects notes, category popover, double-click frames), names never break inside a word, Tessellation polish toward mock A | INBOX:37 (1744), q31-1110.md:10 | open | Gr2 |
| I2 | Tessellation drag-pan from a cell and fitted zoom not cutting the edges | INBOX:37 (states fixed, "drag pans from a cell"); CHANGELOG:22 covers the layout only | fixed (INBOX's own record only, no CHANGELOG line; re-drive in Gr2) | Gr2 |
| I3 | Ask overview written as 2 to 4 grouped paragraphs (lead with span, thread paragraphs, arc read with social awareness, one insight), no filler lines, definitions and slang quoted, no repeated openers, no "Show six more" note list | INBOX:38 (1743), HANDOVER:410 (F4), s10-1110.md:7, compleft-1110.md:12 | open | Co3 |
| I4 | "Smart browser": answer threads as chips that filter Matching records, a card opens its neighbours in place, Back walks the trail | INBOX:38 (1743, design row) | design written 2026-11-11 (CHAT_PLAN "Placed from INBOX, 2026-11-11"), three slices, not built | Co3 |
| I5 | Matching records: one brightness, direct before link-only, links padding, badge clearance, stats on card | INBOX:39; CHANGELOG:13 | fixed | none |
| I6 | Matching records: drop weak meaning-only matches when fewer than 3 word anchors | INBOX:39, mr-1110.md:11 (`meaning_floor`, search_manager.py) | open | Bk1 |
| I7 | Dashboard lag after start: follow loop under a persistent announcer; the 20 ms look from the figure's own tempo writes; `atlasRigWake.after` 96 ms (atlas-motion.js:342) | INBOX:40 (1741), lag-1111.md:5,6,8 | open (owner trace unverifiable) | Cp1 |
| I8 | Dashboard lag: `style and layout 380ms` start frame, widget fill callbacks 98 to 119 ms in dashboard.js, anonymous timers dashboard.js:2036 | INBOX:40, lag-1111.md:7,9 | open | Da1 |
| I9 | Date answers: retelling marked or quoted, no title repeated in the body, "around that time" carries the date subject and gives notes a few days either side nearest first, no "We were on November" | INBOX:41 (1739 points 1 to 3, 6), g13-1110.md:5, w8-1110.md (found-not-fixed) | open | Co2 |
| I10 | Timeline and a date answer disagree on a note's day (event day against written day); answer says both; date answers count documents or say notes only | INBOX:41 (1739 points 4, 5); no timeline fix found | open | Co2 |
| I11 | Desk companion: pat while hanging, hang height on browser tabs, corner loop with no standable tops | INBOX:43 (1721 a to c); CHANGELOG:134 (pat on the edge); deskfix-1110.md:13 | fixed on fakes; real Windows unverifiable | Cp2 |
| I12 | Desk companion: more activities (variety) and visible lower-body and ribbon motion; Opus design pass | INBOX:43 (1721 d, e), INBOX:59, INBOX:64, OPEN:318 (E3), life-1109.md (ranked list) | open | Cp2 |
| I13 | Diagram builder first open slow (3.5 to 3.9 s at 8x, 1.7 to 2.3 s the Library bundle): a `diagramDoor` bundle, `diagramModel` out of documents-mermaid.js | INBOX:44 (1722); `diagramDoor` is not in frontend/js | open | Dg1 |
| I14 | Feminine desk Atlas too purple or pink against the in-app look: pixel-hue parity in `core/overlay` | INBOX:45 (1724) | open | Cp2 |
| I15 | Lag log 1726 residue: chat typing keydown 285 ms, avatars timers 516 ms, graph `gcRequestDraw` 35 to 53 calls/s, notes-subtabs 400 ms, tab clicks, Settings pane clicks 250 ms | INBOX:46, lag-1110.md:7 (not reproduced), lag1726-1110.md:6, s7-1110.md:19 | unverifiable (needs the owner's Windows trace or a 22,800-node chat) | none W34: unverifiable, w34-fix2-1111.md. |
| I16 | Throw hard enough leaves through the top and falls back by throw speed | INBOX:47 (1719 a); CHANGELOG:192 (1.0 to 8.0 s seeded); engine.py:3652 | fixed (desk Windows unverifiable) | none |
| I17 | More life and biological design on both companions (follow-through, startle settle, micro-saccades, stand drift, floater breath, media) | INBOX:47 (1719 b), life-1109.md Remaining 1 to 5 | open | Cp1 (in-app), Cp2 (desk) |
| I18 | Composer "response issues": the owner to give examples, then a deep-audit round | INBOX:47 (1719 c), OPEN:57 (P3, Q17) | owner call: which answers read badly? | none |
| I19 | 1716 lag residue: avatars.js timer 1295 ms (needs the owner's dirty page), phone-shell tab, `openDoc`, web-reader-open, idle graph draws, ocrScheduleFitDock | INBOX:52, log1716.md, OPEN:189 (B56) | unverifiable (not reproduced at 44 notes) | none |
| I20 | Chat Sources rows extend far to the right | INBOX:54 (1712), OPEN:49 (Q15, P1) | owner call: window width and which surface (popup agent, Chat tab or Ask tab)? | none |
| I21 | Companion acts: pointer-idle wave built; remaining catalogue acts (meditate, lounge, rest_head to desk; dangle, kick_legs, hang_one_hand need desk frames; hold still, carry over, catch mid-air, tail pull, drag skid, toss up, pointer chase) | INBOX:56 (1711), OPEN:316,317 (E1, E2), compalive-1109.md desklane block | open | Cp2 (desk frames), Cp1 (in-app) |
| I22 | 1696 a falling stutter at about 8 fps on the downward arc | INBOX:59, OPEN:199 (B64), atlasf1696-1108c.md | open | Cp2 |
| I23 | 1696 b perch finds no standable edges on a real desktop (Explorer, Chrome counted invisible) | INBOX:59, OPEN:202 (B66), w15-1110.md, log1716.md | open; Windows cause needs one more log (unverifiable) | Cp2 |
| I24 | 1696 c to e: Settings selected-bar consistency, md asterisks in What it learned links, selected sidebar item scrolls into comfort | INBOX:59; asterisks fixed CHANGELOG:402; c and e no record found | open (c, e); fixed (d) | Sh1 |
| I25 | Typeable values: lightbox pinch, value field in lightbox, diagram, board zoom, slider readouts built; present-mode page counters and preset dropdowns not checked; zoom per gesture not measured on a real trackpad | INBOX:62 (1694); lightbox-view.js:442; 76b77b1 | open (counters, presets); unverifiable (trackpad) | Wb1 |
| I26 | Chat reply persistence: card, badge, Why trail and timing survive a reload; greeting asked as a question gets a companion line; the "spasm" not reproduced | INBOX:63 (1693 b), small3-1109.md | open (persistence unverified); spasm not reproduced | Co3 |
| I27 | 1693 a: date-dependent composer tests | INBOX:63; tests/conftest.py:157 `_fixed_day` | fixed | none |
| I28 | 1683 residue: desk half of B1, B3, B5, B6 pose-keyed lower body and nebula variants; hop chain on a perch unmeasured; every desk motion unverified on real Windows | INBOX:64, travel-1109.md Left, wisp-1109 note | open (frames); unverifiable (Windows) | Cp2 |
| I29 | 1670 desk companion ride: cut off, sits about 20 px above the bar, not animated | INBOX:70; E18 "true" (e18-1110.md) | open; unverifiable (Windows) | Cp2 |
| I30 | 1598 and 1606: companion carried over the top bar after Ask scroll; a pat over the head lifts Atlas 30 px | INBOX:71, OPEN:50 (Q16, P2) | owner call: window size or a short recording? (not reproduced, a31q) | none |
| I31 | INBOX 904 B01 to B86 owner bug list: 47 fixed, 5 stale, 34 true | INBOX:73, e18-1110.md:3 | 34 open; true ids are marked `**E18 true.**` in INBOX | Ev1 (list them) |
| H1 | Windows Hello on a real origin; WebView2 WebAuthn PRF; localhost fallback | HANDOVER:10, hello-1110.md:8, localhost-1110.md:8,16 | unverifiable (real Windows) | none |
| H2 | Fable named for a read-only composer audit and a whole-app deep dive "next session" | HANDOVER:11,12 | owner call: is Fable named for the close-out? (nothing may start it otherwise, order 4) | none |
| H3 | Q20: `complexity.yml` still `--exit-zero`; CI definition edits guarded in away mode, `tests/test_complexity.py` holds the zero baseline | HANDOVER:412, OPEN:40 (Q20) | owner call: edit the workflow (guarded)? | none |
| H4 | ~~Held: K38 single-use media links (breaks range playback), K32 due-count endpoint (poll redesign), E43/K11/K13/K26 key storage and MCP auth (Q22)~~ decided and built backend-1111 (K38 kept at 120 s; K32 62af9c7; Q22 rows b155304, 6ff76a7, 0389648) | HANDOVER:410, s11-1110.md:8,9 | owner call: Q22 (keyring or 0600 file, one token per MCP server) and K38 (accept a 120 s reusable link?) | none |
| H5 | `test_repo_boundaries::test_orm_calls_in_the_routers_only_go_down` red: 690 ORM calls under api/, cap 687 | g69-1110.md:11 (said 691); run 2026-11-11 | green at f06fd0e09 (re-run, nothing to fix) | Bk2 |
| H6 | Test reds named in older notes: `test_boot_diet3` (3573 vs 3569), `test_lazy_bundle_calls` (dashboard.js:3833,3889), `test_atlas_access` fixture, `test_static_compression` | s9b-1110.md:12, s14-1110.md:6, s58left3-1110.md:10, s12b-1110.md:7; the four pass on 2026-11-11 | fixed (run; only the boundaries test fails) | none |

**Work-order rows (OPEN.md) still open, merged with their remaining files**

| id | item | sources | status | batch |
| --- | --- | --- | --- | --- |
| O1 | A16 `/media/{id}` 403 against 409: unify on 409 "Unlock first." | OPEN:89 (Q18), sec-1109.md Left | open | Bk1 |
| O2 | Real Tesseract and PDFium reads never ran (no `tesseract`, no `pypdfium2` here) | OPEN:326 (E9), s8-1110.md, sec-1109.md | unverifiable (needs a machine with both) | none |
| O3 | B7 "latest on sourdough" leads the wrong note; "what do I need to read" names by date | OPEN:126, w7-1110.md | built 50b8cf54e | Co2 |
| O4 | B21 follow-on loses its subject ("who wrote it", "and the dentist"; Ask sends no objects); frame not saved with a chat | OPEN:144, conv-1110.md:11, fc1-1110.md | open | Co1 |
| O5 | B22/B23: chips from leftover words; a bare "yes" after Gather and Track-in-a-table (the other offers are taken up: composer batch 2, 2026-11-11) | OPEN:149, w9b-1110.md Left | fixed 2026-11-11 (B22 chips still open) | Co1 |
| O6 | B24: four confirm wordings; undo only inverts pin, unpin, tick, untick; "undo" after "delete it" gives Help text | OPEN:149, w9b-1110.md, fc3-1110.md:6, consent-1110.md | open | Co1 |
| O7 | B26 Q5 "called X with Y" is the title, Q6 one list-add rule; both rewrite pinned tests | OPEN:149, w9b-1110.md, fc12-1110.md:4,5 | built 17d5d14 (B26 closed 1111); was owner call: Q5 and Q6 are taken as recommendations; the pinned tests (`test_new_note_called_1102`) must move with a stated reason | Co1 |
| O8 | B27 "similar to X" searches X itself instead of ranking by likeness | w9b-1110.md | open | Co1 |
| O9 | B29 tick-off forms not re-checked | OPEN:152 | open (verify) | Co1 |
| O10 | B33 proper noun lowercased in a quoted line | OPEN:158, compleft-1110.md:17 (not reproduced) | open (not reproduced) | Co2 |
| O11 | B34 joke note leads by quote not name (1705 b) | OPEN:159, composer-r8-1109.md Left | open | Co2 |
| O12 | Composer small asks: "call anna" lower case, "make a checklist for my trip", "tom and sara" pair, "put it in my journal" | composer-r8-1109.md Left (4 rows) | open (left as written; no later commit) | Co1 |
| O13 | B56/B58 (not reproduced at 4x): 4.5 s avatars timer after opening a note; phone resize covers Send | OPEN:189,191, w14-1110.md | unverifiable (not reproduced) | none |
| O14 | ~~w14 next: B55 pacer reads during an agent turn; B57 throw scrolls the page; B59 `ring-held` removed on every keydown (settings-panes.js:350, 36 writes for 37 keys); B60 Reset appearance leaves motion prefs (appearance-panel.js)~~ **W34: stale** (w34-fix3-1111.md) | w14-1110.md:4 to 9 | open | Cp1 (B55, B57), Sh1 (B59, B60) |
| O15 | B63 companion does not show: root cause; B62 to B67 list | OPEN:198, b62-1110.md | open; unverifiable (Windows) | Cp2 |
| O16 | B65 the 1683 travel mix | OPEN:200, travel-1109.md | open | Cp2 |
| O17 | W16 real-model: B68 model-on parity, B69 evals gate, B70 SKILLS Phase D, B71 entity extraction, B72 BACKGROUND_MODE, B74 tool contracts on Ollama | OPEN:206 to 212 | unverifiable (needs `scratchpad/llama-dev.sh serve`) | Mo |
| O18 | B73 probe cache (Q11 recommendation: cache 30 s, drop on failure) | OPEN:211, deskperf-1109.md | open | Co3 |
| O19 | C1/C2/C4/C5/C9 diagram: Connect words on a sideways phone, door dialog repeats the page, midpoint click on an arrow opens the name box, tray "Open" row and Done silently creating a file not driven, touch Add-then-Enter adds a second block, Versions "Named only" filter, Ask for mind maps, timelines, sequence | OPEN:220,225, w17-1110.md Left, dgai-1110.md:29, dgml-1109.md Left | open | Dg1 |
| O20 | Diagram unverified: touch long-press and one-finger pan, Space+drag, Cmd+arrows, 17 px scrollbars, 390 px for new shelf kinds, group border long press | dgsel-1111.md:5 to 7, dgfold-1110.md:4, dgroup-1110.md:4, dgmseq-1109.md | unverifiable (touch device, macOS, Windows scrollbars) | none |
| O21 | Diagram default fold: Q14 decided fold on New diagram only | dgml-1109.md Left, OPEN:54 (Q14), HANDOVER:12 | fixed by decision; code not re-checked, verify in Dg1 | Dg1 |
| O22 | C19 to C22 shell widths: Ask button clipped at 390, quiet chips 28.6 px, Notes dock wrap 1280 to 1500, Settings sideways at 768, 1920 by 1080 at 125 to 200 % | OPEN:239 to 242, s5-1110.md:11 | open | Sh1 |
| O23 | C23 "?" after a Dashboard click hands focus to CodeMirror | OPEN:243, row21-1109.md, s58left-1110.md:9 | unverifiable (not reproduced on an empty notebook) | none |
| O24 | C30 Ask redesign at half width | OPEN:254, 22-10 doc section | open | Co3 |
| O25 | C35 citation style: numbered marks match Sources, bracket link removed (D25, Q1 taken); E33 path-first Guide answers (Q23) | OPEN:259, HANDOVER:12 | Q1 built 517ee90 (D25); Q23 path-first built (E33, docs spoke 1111) | Co3 |
| O26 | C36 "buttons disappeared" after Why | OPEN:260, s58left-1110.md:8 | unverifiable (0 removals in three drives) | none |
| O27 | C41 remaining 1028-docs and 1031-docs rows (40 and 7) | OPEN:267, e15-1110.md (docs true rows D25, D28, D29, D40, D41) | open | Do1 |
| O28 | D2 to D4 CI time: longest overlay tests (81 s, 69 s), slow tests outside overlay, `--durations=0` on one CI run | OPEN:273 to 275, cispeed-1109.md | open | Ci1 |
| O29 | D8 Settings panes block on open (655 ms task, 3,000 nodes in one template) | OPEN:281 | open (measured, not built) | Sh1 |
| O30 | D11 to D14 graph at scale: 2,000-note layout 28 s, 500-note hover p50 83 ms, redraw only while something moves | OPEN:286 to 289, graph19-1109.md | open | Gr1 |
| O31 | D16 lazy meeting recorder card, graph options panel (26 KB, 79 ids), boot CSS | OPEN:293, row21-1109.md | open (measured, not built) | Sh2 |
| O32 | D18 trim decodes the whole recording (700 MB an hour); notes cannot embed a recording | OPEN:295 | owner call: a server-side cut needs a container writer; keep raw audio? | none |
| O33 | D21 split documents.js 16,381 to 17,190 (CodeMirror glue); D27 split whiteboard.js (26,164 lines) and whiteboard-map.js (11,050) | OPEN:300,310 | open | Do2 (D21), Wb2 (D27) |
| O34 | D22 to D25 ratchets: IIFE wraps, 359 ORM queries in routes, 9,044 global names, split `run_agent`, data tables out of code | OPEN:303 to 306, s8-1110.md, SESSION_BRIEFS:216,223 | open | Bk2 |
| O35 | D28 composer topical digests 0.45 to 0.78 s on 500 notes (closed 1111, numbers in the D28 row) | OPEN:311 | done | Co2 |
| O36 | D19 typing in a long document: p50 56 to 112 ms, gate under 16 ms not met | OPEN:297, s7-1110.md:12 | open (closed s58left4-1110 as "no cheap app-side cut") | Do2 |
| O37 | E1 to E6 companion life: acts to desk, in-app-only acts need frames, life list, masculine Atlas, props, lower body follow-through | OPEN:316 to 321 | open | Cp1, Cp2 |
| O38 | E8 K33 token sweep per request (pinned by `test_vault_sessions`) | OPEN:325, s8-1110.md:5 | owner call: may that test's intent move (Q22 area)? | none |
| O39 | E10 backend rows true: BK6 update signature, BK10 list payloads, BK11 god modules, BK12 reminders poll, K36 N+1 in `list_boards`, K20, K24, K25, K27 kept routes | OPEN:327, s8-1110.md, s14-1110.md:6, e15-1110.md | open | Bk1 (BK6, BK10, K36, K20), Bk2 (BK11, K24, K25) |
| O40 | E12 "Read as ..." lines under computed answers (49 assertions in about 18 test files) | OPEN:331, fc7-1110.md:14, s8-1110.md | owner call: drop the lines that only restate the sum? (moves a stated intent) | none W34: skipped (composer spoke), w34-fix1-1111.md. |
| O41 | E13 "¦" for "&" in a category; "conversation" topic on a gym note | OPEN:332, s8-1110.md | open; needs a repro from the owner's data | none |
| O42 | E14 manual pictures as WebP from sweeps | OPEN:333 | owner call: want one sweep-made image? | none |
| O43 | E15 verify 1028 audits | OPEN:336, e15-1110.md (303 rows: 62 true, 155 fixed, 20 stale, 52 not reached, 14 skipped) | fixed (62 true rows moved to batches; the 52 not reached stay open for a scout) | Ev1 |
| O44 | E16 verify 1029 to 1031 audits (362 rows) | OPEN:337; no e16 file exists | open (belongs to the audit inventory; listed so it is not lost) | Ev1 |
| O45 | E17, E18, E19, E20 verify sweeps | e17-1110.md, e18-1110.md, e19-1110.md, s58left4-1110.md:5 | fixed | none |
| O46 | E21 the 1692 and 1683 owner-asks partial rows | OPEN:342, book2-1109.md | open | Ev1 |
| O47 | F1 documents: live code blocks done; open gap rows 1, 2, 5, 6, 9, 10, 12, guided equation editor items, Live multi-line `$$`, label completion, VC rows, links L6, Guide topic for slides, `{{cursor}}` caret | OPEN:348, s9c-1110.md:5,6,9 | open | Do1 W34: true (hub surface), w34-L3-1111.md. |
| O48 | F2 whiteboard Format gaps: Edit image, draggable crop, BPMN and icon sets, draw.io rows, board view per device only, cross-link default on a map | OPEN:349, s9c-1110.md:8, s9-1110.md:12 | Built 2026-11-11 except the draw.io rows named at OPEN F2 | Wb1 W34: true-deferred, w34-fix3-1111.md. |
| O49 | ~~F3 mind map: Replace all does not rewrite notes (`wbBoardReplaceAll`), render pass 13b, row 2 citations~~ **W34: stale** (w34-fix3-1111.md) | OPEN:350, s9-1110.md:13, s9c-1110.md:10 | open | Wb1 |
| O50 | F4 chat: composition layer (INBOX 1353), Phase 5 a to g, Foundation F5, "X versus Y" | OPEN:351, s10-1110.md:7, compleft-1110.md | open | Co3 W34: owner-call (tracked in the plans), w34-L3-1111.md. |
| O51 | F5 world class: durable jobs, multi-window, torch at launch, F1 prefs, RapidOCR (Q27), web-search store, Try again on a failed web tool chip | OPEN:352, s10-1110.md:6, wc3-1110.md | open | Ui1 W34: owner-call (tracked in the plans), w34-L3-1111.md. |
| O52 | F6 UI: Settings panes indexed, token budget, `!important` to 0 (96 left; 21 taken **Fixed css-important-1111**), dissolve 08 and 10 stylesheets, new-note lock toggle | OPEN:353, s10-1110.md:4, s10b-1110.md:9 | open | Ui1 W34: owner-call (tracked in the plans), w34-L3-1111.md. |
| O53 | F7 graph and timeline: `?since=` cursor (deferred, no caller), dot density at 5,000, day strip and spans (Q32 parked) | OPEN:354, s10-1110.md:5 | open (`?since=` deferred by design); owner call (Q32) for the day strip | Gr2 W34: owner-call (tracked in the plans), w34-L3-1111.md. |
| O54 | F8 owner go: sync, offline studio, audio, desktop pet, custom domain, blind panel, Fable diagram dive | OPEN:355, OPEN:55 (Q34) | owner call: say go | none |
| O55 | The 84 struck rows of the work order (W1 to W34) | OPEN:69 to 340 (`~~`) | fixed (each row carries its sha or "Fixed before s5-1110") | none |

**22-10 bug doc, SESSION_BRIEFS and remaining-file items not in the work order**

| id | item | sources | status | batch |
| --- | --- | --- | --- | --- |
| P1 | "You asked: ..." line above the Ask answer stays removed (Q19) | OPEN:381, OPEN:54 | fixed by decision (HANDOVER:12; a test pins it) | none |
| P2 | Start SearXNG from a button | OPEN:379 | open | Bk1 |
| P3 | `_start_tray` over complexity 20 (now 23): split menu build from start-up; test on Windows | OPEN:389 | built deb7ab83d (callbacks module-level, 130 lines); Windows part unverifiable | Bk2 |
| P4 | Reminder edit form: time field about 0.2 rem high | OPEN:390 | open | Sh1 |
| P5 | Brief 27 phone bottom bar | SESSION_BRIEFS:132 | fixed (phone-shell.js:673, shell-reminders.js:588; E19 stale) | none |
| P6 | Brief 34 second part: one snap in ten minutes; reaction rows | SESSION_BRIEFS:154 | open | Cp1 |
| P7 | Brief 88 N8 dodge glance (avatars.js:4155), N10 milestone cheer | SESSION_BRIEFS:251,258 | open | Cp1 |
| P8 | Brief 45 part 2 / 58 / 59 file splits (`index.html` 16,043, `status.js` 3,283, `notes-list.js` 3,805, `chat.js`) | SESSION_BRIEFS:176,194,200 | open | Bk2 (non-hot files only) |
| P9 | Brief 62 data out of code; Brief 63 runners (embedder half built) | SESSION_BRIEFS:216,223 | open | Bk2 |
| P10 | Brief 87 step 2: build top two vendor candidates (TTS listening pair, dictation WER on 20 clips) | SESSION_BRIEFS:245 | unverifiable (needs a listening test and models) | none |
| P11 | Brief 90/91: 838 not met (dash-art.js:131 one-frame redraw), two more of five open | SESSION_BRIEFS:278,285 | open | Da1 |
| P12 | Brief 92 (b): Radix, shadcn and APG element comparison has no record | SESSION_BRIEFS:291 | open | Sh1 |
| P13 | Brief 101b/c found-not-fixed rows (binned notes purged by the startup sweep, monthly repeat from the 31st, reminder action token across restarts, Agent undo then Ctrl+Z) | SESSION_BRIEFS:335 (E19: true) | open | Bk1 |
| P14 | Brief 104 typos read in context (no notebook word-pair scoring) | SESSION_BRIEFS:359, spelling.py:456 | open | Co1 |
| P15 | Briefs 95, 97, 98, 102 | SESSION_BRIEFS:304,313,323,346 | open, unstamped (no E19 mark and no HISTORY pointer found) | Ev1 |
| P16 | Notes filter box reads only ISO dates for `before:`/`after:`; `before:tuesday` is a word there | w11-1110.md:7, notes-list.js:353 | open | Sh1 |
| P17 | Pasted `#/Manual` / `#/Statistics` ignored at load; manual opened in first 3 s writes `#/dashboard` | w12-1110.md:4, router.js | open | Sh1 W34: owner-call (tracked in the plans), w34-L3-1111.md. |
| P18 | Early press on Capture's Private button does nothing in the first 3 s (quick-note.js preloaded late) | s14-1110.md:5, s9c-1110.md (says built) | open (verify) | Sh2 |
| P19 | Agent tool writes on a confirmed "Run again": no idempotency by turn id (E70) | w1-1110.md:14 | open | Bk1 |
| P20 | Private spaces: recordings, bookmarks and files not sealed; deleting a locked space offers no unlock prompt | pspace-1110.md Left | open | Bk1 |
| P21 | Private spaces unverified: desk companion while locked, real OS keyring PIN, real model in a private chat | pspace-1110.md Not verified | unverifiable | none |
| P22 | New note popover has no `data-help-for` (order 13); refresh icon report not reproduced | priv-1110.md:5,7 | open (help); not reproduced | Sh1 |
| P23 | Consent: `"run": True` keys in task_acts.py (5 sites), Undo row after a typed yes on a parked tool call, a typed yes does not reach skill and plan cards | consent-1110.md:20, compleft-1110.md:3 | open | Co3 |
| P24 | Parity acts: Undo of merge or delete category loses description and binned notes; in-place find and replace in a note not built; "make reminders from my todo note" (todo to "to do") | compleft-1110.md:4 to 6 | open | Co3 |
| P25 | Fable F-rows left: F1 bound slot lead, F5 chips on small talk and clarifications, "What else is on that week?", F6 "which is higher", "by how much", compare with no figures, F8 ranking ("wats on my shoping list", dentist, "who is anna"), F9 agenda ("this week" is no day), F13 e to k, F4 bare reactions ("really?", "are you sure") | fc1-1110.md, fc56-1110.md, fc8-1110.md, fc24-1110.md, left-1110.md, g45-1110.md:7 | open | Co1 (F4, F5), Co2 (F1, F6, F8, F9, F13) |
| P26 | Composer G-rows left: G1 ("when did I last see the dentist", "how far did I run", "has the launch date changed"), G3 stats wording, G5 guide leads, G6 today line and year gaps, G8 poke lines table (avatars.js:2731) and dated things in the notes, G9 week_review, G11, G12, G14 a, e, f, i | g13-1110.md:4,5, g45-1110.md:6, g69-1110.md, g1014-1110.md | open (G14 a, f not reproduced) | Co2 (composer files), Da1 (dashboard.js:526,633,3018,4229, statistics.js:121), Co3 (voice) |
| P27 | Name use rules 5 and 4 across a restart; Guide "profile" topic; 20-turn eval | g69-1110.md | open | Co3 |
| P28 | E54 identity copy "Atlas's assistant" (CHAT_PLAN decision 36): composer_lines.py:497, composer_smalltalk.py:147, composer_tables.py:1157 | s12b-1110.md:5 | open | Co3 |
| P29 | ~~E69 as-typed echo after autocorrect (design call); E59 to E62, E44, E45, E48 chat design~~ **W34: stale** (w34-L3-1111.md) | s13-1110.md:5, s11-1110.md:9 | owner call: where the "as typed" line shows | none |
| P30 | W8 found-not-fixed: "is my dentist appointment tomorrow" no verdict, "last Christmas" no year, single-day head printed twice, "phone mum" synonym | w8-1110.md | built 2026-11-11 (composer spoke; 112986860, ce70ddac9, b817900c7, d79ea5b01, merged c0a3bc8db; w8b-1111.md, tests/test_composer_w8b_1111.py); left: source_check can flag a date's own figures, "are we meeting on Tuesday" not read as a window ask, "Rung mum" has no you form | Co2 |
| P31 | Web-search store of recent pages; Try again on a failed non-SearXNG web chip | wc3-1110.md:5,7 | owner call: store fetched pages with a re-fetch control? | none |
| P32 | Tour at 390 reports a 455 px spill on one step; Memory and Logs panes hide h3 on a phone | wc3-1110.md:9, wc-1110.md:7 | open | Sh1 |
| P33 | Spell hold in documents editor and Add to dictionary row not driven; LanguageTool install not proven (jar never started) | spell-1110.md:5, lag1726-1110.md:4 | unverifiable (running a downloaded jar was refused here) | none |
| P34 | Q29 filing: re-measure with the embedder; review `memorymap_related.json` (236 sources) | q29-1111.md:4,5 | owner call: review the related-topic table? | none |
| P35 | Gantt, audio note and row 8 (cover and icon) not verified at 390 or with a physical click | s9c-1110.md:10 | unverifiable (touch) | none |
| P36 | Chat avatar loader path unverified in a browser | small-1110.md:7 | open (verify) | Cp1 |
| P37 | Older "found, not fixed" notes stamped stale: test reds that now pass, desk `blink` catalogue row, wake-sources tests | compalive-1109.md, dgml-1109.md, dgmseq-1109.md ("Stale" stamps) | fixed (stamped stale against a pass run) | none |

**Grouped bulk (E17 true bullets in OPEN.md's older sections, not itemised)**

Counts are from `e17-1110.md` "True, by work order batch"; the scout's own caveat applies (keyword sort, may overlap the named rows). 636 true, 31 stale, 10 fixed.

| id | batch group | count | status | work batch |
| --- | --- | --- | --- | --- |
| X1 | W6 recordings and deletes | 11 | open | Sh2 |
| X2 | W7 composer which note leads | 37 | open | Co2 |
| X3 | W8 composer dates | 23 | open | Co2 |
| X4 | W9 composer follow-ons | 10 | open | Co1 |
| X5 | W10 composer compare and lists | 14 | open | Co2 |
| X6 | W11 notes core | 36 | open | Sh1 |
| X7 | W12 navigation | 11 | done wb-1111 (Back and overlays) | Sh1 |
| X8 | W14 in-app companion | 20 | open | Cp1 |
| X9 | W15 desk companion | 11 | open | Cp2 |
| X10 | W19 whiteboard daily UX | 76 | done (wb-1111) | Wb1 |
| X11 | W20 shell accessibility | 7 | open | Sh1 |
| X12 | W21 dashboard, timeline | 15 | open | Da1 |
| X13 | W22 chat, Ask, Guide | 15 | open | Co3 |
| X14 | W23 documents daily UX | 223 | open | Do1, then a later Do batch |
| X15 | W24, W25, W26, W28, W29 (3, 3, 5, 4, 4) | 19 | open | Ci1, Sh1, Gr1, Do2, Bk2 |
| X16 | W27 boot weight | 15 | open | Sh2 |
| X17 | W30 whiteboard render | 19 | done (wb-1111: B39, B4, B23 and two costs) | Wb2 |
| X18 | W31 companion life | 29 | open | Cp1, Cp2 |
| X19 | W33 copy and help | 4 | open | Ui1 |
| X20 | W34 verify | 41 | open | Ev1 |
| X21 | Stale bullets (lines listed in e17-1110.md) | 31 | stale, to strike | Ev1 |
| X22 | Fixed bullets (lines listed in e17-1110.md) | 10 | fixed | none |
| X23 | Residue the scout mapped to no batch (W5, W13, W16, W17, W18, W32 surfaces) | see e17-1110.md | open | Ev1 |
| X24 | E15 true rows by batch (62): W5 E43 K11 K13 K26 K33 K38; W9 E56; W11 S28 S47 S71 S74 S88; W19 U1 U2 U3 U5 U13 B10 B33; W21 S51; W22 E33 E44 E45 E48 E59 E60; W23 D25 D28 D29 D40 D41; W26 S52; W27 S3 B30 D22; W28 D23 D45; W29 K24 K25 B1 B2 B24 D46; W30 B4 B23 B39; W32 K20 K27 K32 K34; W33 E54 S84; backlog D43 D52 S49 S77 | e15-1110.md:20 to 40, s11-1110.md, s12-1110.md | open (minus S71, S74, K34 built, and the 9 s11 stale rows) | per batch |

### Spot checks (2026-11-11)

- Verified in code or CHANGELOG: 1693 a `tests/conftest.py:157 _fixed_day`; 1694 `frontend/js/lightbox-view.js:442 valueField(zoomLabel`; W19 C10 `whiteboard.js:10337 wbDefaultInk` (used at 22619); lag 1741 `atlas.js:4130 function charactersArrivedTask`; 1719 a CHANGELOG:192 and `engine.py:3652 _ceiling_holds`; 1721 a CHANGELOG:134; Matching records CHANGELOG:13; 1696 d CHANGELOG:402; consent cap `ai/agent.py:470 MAX_PARKED_CONFIRMS`.
- Wrong or unproven: `diagramDoor` (INBOX 1722) is not in frontend/js; `?since=` is not in routes_graph.py (deferred by design); INBOX 1744 "drag pans from a cell" has no CHANGELOG line (INBOX's own word only); INBOX 1696 c and e have no record; E16 has no file or CHANGELOG record (CHANGELOG:837 "Audit E16" is an unrelated compare fix); `tests/test_repo_boundaries.py` fails at 690 against 687.
- Run with `/home/user/Tessellate/.venv/bin/python` and `PYTHONPATH=src` (the default python has no fastapi).

### Owner-call list

1. I18 / Q17: examples of the composer answers that still read badly. 2. I20 / Q15: window width and surface of the Chat Sources rows. 3. I30 / Q16: window size or a recording for the companion over the top bar. 4. H2: is Fable named for this close-out. 5. H3 / Q20: guarded edit of `complexity.yml`. 6. H4 / Q22 and K38: key storage, one token per MCP server, the 120 s reusable media link; K32. 7. O7: confirm Q5 and Q6 (they move pinned tests). 8. O32: D18 trim and raw audio. 9. O38: the K33 token sweep against its pinned test. 10. O40: drop the "Read as ..." lines. 11. O42: a sweep-made WebP in the manual. 12. O53 / Q32: the timeline day strip. 13. O54 / Q34: go on sync, offline studio, audio, desktop pet, custom domain, blind panel, Fable diagram dive. 14. P29: where the "as typed" line shows. 15. P31: store fetched pages. 16. P34: review the related-topic table.

### Batches (up to 4 parallel slots per session; no two slots in a session share a hot file)

Hot families: `ai/composer_*.py` plus `commands.py`; `chat-turn.js`; `documents*.js` (including documents-mermaid.js); `whiteboard*.js`; `graph*.js`; `diagram*.js`; `dashboard.js`; atlas, avatars, `core/overlay`. Rung: Sonnet unless named.

| Session | Slot | Batch, files, item ids |
| --- | --- | --- |
| 1 | A | Co1 composer follow-ons: `composer_follow.py`, `composer_dialogue.py`, `composer_talk.py`, `composer_chips.py`, `commands.py`, `spelling.py`; O4 to O9, O12, P14, P25 (F4, F5) |
| 1 | B | Cp1 in-app companion: `avatars.js`, `atlas*.js`, `lag-watch.js`; I7, I17 (in-app), O14 (B55, B57), O37, P6, P7, P36, X8, X18 |
| 1 | C | Gr1 graph at scale (Opus): `graph-canvas.js`, `graph-worker.js`, `graph*.js`; O30 (D11 to D14) |
| 1 | D | Sh1 shell and notes (no hot files): `10-responsive.css`, `router.js`, `navigation.js`, `notes-list.js`, `settings*.js`, `index.html`; I24, O14 (B59, B60), O22, O29, P4, P12, P16, P17, P22, P32, X6, X7, X11 |
| 2 | A | Co2 composer dates and ranking: `composer_ahead.py`, `composer_digest.py`, `composer_slots.py`, `composer_money.py`, `composer_plan.py`, `composer_figures.py`, `factgraph.py`, `chat_extra.py`; I9, I10 (with timeline reading), O3, O10, O11, O35, P25 (F1, F6, F8, F9, F13), P26 (composer G-rows), P30, X2, X3, X5 |
| 2 | B | Cp2 desk companion: `core/overlay/*`, `tests/test_overlay_*` (serial); I12, I14, I21, I22, I23, I28, I29, O15, O16, O37, X9, X18 |
| 2 | C | Do1 documents: `documents*.js` outside the save path, DOCUMENTS gap rows; O27, O47, X14 (first slice of 223) |
| 2 | D | Bk1 backend: `api/routes_*`, `core/security`, `search_manager.py`; I6, O1, O39 (BK6, BK10, K36, K20), P2, P13, P19, P20 |
| 3 | A | Co3 composer voice, overview and consent (Opus): `composer_voice.py`, `composer_lines.py`, `composer_tables.py`, `composer_smalltalk.py`, `composer_openlinks.py`, `ai/parity_acts.py`, `chat-turn.js`, `ask-compose.js`, `capture-ask.js`; I3, I4, I26, O18, O24, O25, O50, P23, P24, P26 (voice), P27, P28, X13 |
| 3 | B | Wb1 whiteboard daily: `whiteboard*.js` outside the render path; I25, O48, O49, X10 (76 rows) |
| 3 | C | Dg1 diagram: `diagram-*.js` and `documents-mermaid.js` (the `diagramDoor` carve); I13, O19, O21 |
| 3 | D | Ci1 CI time: overlay test speed, `.github/workflows` only if the owner says (H3); O28 (D2 to D4) |
| 4 | A | Gr2 graph features: `graph*.js`, tessellation; I1, I2, O53 |
| 4 | B | Wb2 whiteboard render split (Opus): `whiteboard.js`, `whiteboard-map.js`; O33 (D27), X17 |
| 4 | C | Da1 dashboard and timeline: `dashboard.js`, `timeline*.js`, `statistics.js`; I8, P11, P26 (JS rows), X12 |
| 4 | D | Ui1 UI and world class: stylesheets, F5/F6 rows; O51, O52, X19 |
| 5 | A | Do2 documents split (Opus): `documents.js` 16,381 to 17,190, `docLivePlugin`; O33 (D21), O36, X14 (rest) |
| 5 | B | Sh2 boot and recordings: `meetings.js`, `index.html`, `prefs.js`; O31, P18, X1, X16 |
| 5 | C | Bk2 structure ratchets (non-hot files): O34, O39 (BK11, K24, K25), P3, P8, P9, H5, X15 |
| 5 | D | Ev1 Haiku scouts, docs only: O44 (E16), O46 (E21), I31 (34 true B-rows), P15, X20 to X23; then Mo (O17, needs `llama-dev.sh serve`) |

Session count: 5 sessions (20 slots, 4 Opus in all, at most 1 per session) clear every named open row; honestly 9 (range 8 to 11), because X14 (223 documents rows), X10 (76 whiteboard rows) and the rest of the E17 bulk are 636 bullets with unknown overlap, composer batches usually need a second round, and F8 and the owner-call rows wait outside the count.
