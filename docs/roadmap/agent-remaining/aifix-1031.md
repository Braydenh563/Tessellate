# aifix-1031 (branch agent/aifix-1031, port 8858)

## Done
- AI1 + HR1: away pauses every loop (running animations 64 to 6 on a non-home tab), `atlasFrameBudget` lite set (4x CPU idle 5 s: task 4.94 s to 2.18 s, style 2.52 s to 0.48 s), probe by events, blend skips planets (agent turn getAnimations 260 ms to 140 ms at 1x; the audit's 1,003 ms is not reproduced on this profile: 65 animations here against about 130 there).

- AI4, AI18 (fork up_to, mode, note_ids 422; persona fallback kept by design, test_chat_uses_selected_persona), HR3 (SummarizeBody bound), AI9 server half and HR7 (`search_manager.clip_query`), HR5 (fence in filing_prompt, evidence and janitor.SYSTEM_PROMPT), HR8 (RECOMMEND_FLOOR 0.5). HR13 already fixed on this head (POST /memory 700 chars is 422, cap 200).

## Next
- AI3 + AI16 (inert while faded or collapsed), then the high and medium rows in order.

## Left
- wake_sources_seed.json atlas-life.js::raf 3 to 4: the frame budget's one rAF site times 3 s of frames beside animations that already force frames; it cannot be the tail's rAF (the tail rests on a timer).
