# aifix-1031 (branch agent/aifix-1031, port 8858)

## Done
- AI1 + HR1: away pauses every loop (running animations 64 to 6 on a non-home tab), `atlasFrameBudget` lite set (4x CPU idle 5 s: task 4.94 s to 2.18 s, style 2.52 s to 0.48 s), probe by events, blend skips planets (agent turn getAnimations 260 ms to 140 ms at 1x; the audit's 1,003 ms is not reproduced on this profile: 65 animations here against about 130 there).

- AI4, AI18 (fork up_to, mode, note_ids 422; persona fallback kept by design, test_chat_uses_selected_persona), HR3 (SummarizeBody bound), AI9 server half and HR7 (`search_manager.clip_query`), HR5 (fence in filing_prompt, evidence and janitor.SYSTEM_PROMPT), HR8 (RECOMMEND_FLOOR 0.5). HR13 already fixed on this head (POST /memory 700 chars is 422, cap 200).

- AI2 (.msg-meta colour token, no opacity), AI12 (`_stated_lead` verb follows the state; test_guide_composed_787 updated, its intent moved: the old test locked the contradiction), AI19 (the title field is required; the toast is gone; test_audit_1030_ai_ui A33 follows, intent moved), HR9, HR10, HR11, HR17 (`settingListWords`), HR19.

- AI3 (the dodged companion is `inert`; the tab-away state was already `visibility: hidden`, so the audit's opacity-0 stop is not reproduced), AI16 (already `visibility: hidden` on the parked sheet's children: 0 sidebar stops in 40 Tabs at 390, measured).

- AI7, AI8, AI10, AI11, AI17 (arrow nudge; the emblem's gentle reduced-motion breath is a built decision, kept), HR2, HR12.

- AI6 (`_composed_chat` in routes_chat.py; test_chat_api's two apology assertions follow, intent moved). Web panel code to web-results.js (boot ratchet: chat.js gz 17,025 to 14,819).

- AI5 (confirm before web search on), AI13 (guide_aliases restore row), AI14 (Esc and cancelEdit focus), AI15 (target-min on action buttons, fold summaries, history rows, Ask-AI switch label; the 32x18 switch input is by design, DESIGN.md Hit targets), AI20 and AI21 (not reproduced; regression tests added), HR4 (folded task runs), HR6 (Activity row in the chat menu), HR21 (log filter focus), HR20 (confirm queue in app.js), HR18 (cards built when a group opens: 31 to 8 cards, pane nodes 1,180 to 655), HR15 (resolved by design, DESIGN.md Hit targets), HR23 (log list draws the newest 200: 500 records 90 to 126 ms down to 38 ms; the companion poof off-screen while Settings is open is left), HR22 (hovered engine detail takes the body colour: axe clean in both themes).
- test_the_keyboard_lands_somewhere_after_every_note_step: the test read the pre-N11 shape; it now pins `restoreFocusTo` (the intent holds).

## Next
- HR14, AI22 (not reproduced), AI23 (L effort).

## Left
- wake_sources_seed.json atlas-life.js::raf 3 to 4: the frame budget's one rAF site times 3 s of frames beside animations that already force frames; it cannot be the tail's rAF (the tail rests on a timer).
