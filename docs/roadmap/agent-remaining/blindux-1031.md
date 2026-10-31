# blindux-1031: blind test 2026-10-31, friction items 3 to 10

Done (all in branch agent/blindux-1031): 3 (Ask only-note, Open note), 4 (Custom order), 5 (Guide), 6 (Read notes now), 7 (bell), 8 (greeting), 9 and 10 (labels).

Remaining, one line each:
- Item 3, the owner's "count the related notes the composer already finds": not done; the only-note line is softened when only words were searched (`_with_words_only`, routes_chat.py). With search by meaning on, "your only note" still stands.
- Item 4, Move up/Move down in the Library lists' menus (docs, boards, media) lead the menu too, but only the Notes list was measured.
- Item 9, `#notes-tidy` stays icon-only with a badge (the 1200px width decision in index.html above it); only its aria-label changed to "Tidy, 9 things to look at". A visible word needs a width decision.
- Item 9, "Notes tab drops you on the list": not touched (brief said cheap label fixes only).
- Item 10, other unclear labels not touched: the "travel" chip with + and x, "Mentions Jun 14", "Filter" holding one toggle, "Open" for two states, map title vs centre topic, "Save as draft" vs "Save".
- Item 7, "Get started, 2 of 3 done" in the bell: not touched.
- Found, not mine: tests/test_guide_social_1414.py::test_chat_closes_with_the_same_closing_so_a_finished_act_is_not_resumed_there_either fails on the base (it greps routes_chat.py for `seed, recent,`; the call is now `f"{seed}:{req.question}", recent,`).
- Not verified: drag reorder with a real pointer; the notifications list with a real model running; Library list hints (docs, boards, media).
