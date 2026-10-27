# composer8-1026 (CHAT_PLAN 1353)

Done (tests/test_composer_seven_1026.py, extended; composer7's file):
- Small talk kinds insult, emotion, who, about_app, joke, unclear, test and the nothing-found line are composed from heads and tails (`composer_lines.SOCIAL_HEADS/SOCIAL_TAILS`) plus whole frames for shape variety, in the chat's voice and persona: 16 or more distinct lines a voice for natural, professional, playful and plain, `phrasing.repeats` 0 over 24 turns, each under 5 ms. Identity kinds name Atlas's assistant in every line.
- The nothing-found line (`composer._nothing_parts`) and the empty window (`composer.empty_window(register=)`) take the chat's own voice through `compose(register=)`, set by `routes_chat._compose_for`, the brief call and the empty-window call. With no register the two-register stored lines are unchanged (library callers and tests).
- The plain "Next up:" line after an empty window is the `next_due` frame set, four voices.
- Ask tab at half width: the composer's controls (length picker, as-of, tune, Ask, Stop) are one `.ask-controls` flex item after a field of 14rem basis, so a narrow card drops them to a second row at the right (no width query; test_breakpoints holds the set). Measured at 720x900 (askhalf probe, not committed): field row 1, controls row 2, Ask 59x36, no overflow (askScrollW 631 = askClientW 631, docScrollW 720); at 1000 and 1440 the single row is unchanged.
- Open requests, pasted links and web-search failure were already built (composer_suggest.py f6c7600, 33f7a0b); checked again with the no-model composer: "search the web" and "translate ..." say what is off and where the setting is.

Remaining:
- Ask tab: the Ask button is 36 px tall beside 44 px icon buttons at 720 (36 at 1000+ with 36 px icons); one control height in the bar is DESIGN's rule (`--control-h`), not changed here.
- dog2 12, 13, 14 (wb2, whiteboard and mind map), 22 (not confirmed): not touched.
- Other tools failing (not web search): the agent says "isn't available here" (agent.py:2592) with no link to a setting; not changed.
- Reminder notification text is built in the browser (frontend/js), boot gzip cap; the "Sources: ... meaning + keywords" line (chat-agent.js:2232): both need the lazy bundle.
- Not verified: composed small talk and nothing-found through the running app with a real persona prompt (unit and route tests only, no model); the Ask wrap in dark theme and at 560 px was measured for overflow only at 720, 1000 and 1440.
