# chat-1693b remaining (INBOX 1693 b)

Done:
- Reload parity (b): the turn saves `by` ({composed, model}) and `why`; `openConversation` (sheets-selects.js) passes them to `finishReply`, which now finds a reopened bubble's answers and head itself and draws the Why trail (reply-kit.js `replyFinish`). A model-less reply gets its timing line. Measured in the app (1920x1000, Agent click, no model): live and reloaded both show badge, note card, Why, 2.6s.
- Greeting (c): "hey! whatcha doing??" gets the welcome plus a how line (`question_noise.asks_how`, `routes_chat._hello_reply`); "whatcha doing" / "whatcha up to" are now read as how-are-you phrases.
- Bytes: the gzip ratchet was 30 over-margin; won back with `?.` tidy-ups in answer-kit.js, chat-turn.js, sheets-selects.js (total 251,9xx, under 251,980).

Not reproduced, not fixed (needs the owner's machine):
- (a) the "spasm". Probe `scratchpad/_a1693/probe.js` (untracked): Agent mode, seeded notes incl. a "The note" card, 1920x1270, SCROLLBARS=1, scale 1, 1.25, 1.5, 0 to 4 prior turns, rAF samples of `#chat-messages` scrollTop/scrollHeight/clientHeight for 8 to 20 s. Result: no oscillation. scrollTop climbs monotonically while the reply reveals (e.g. 1137 -> 1336 -> 1502, scrollHeight 1989 -> 2188 -> 2354) then settles with one 2 px shrink (1502/2354 -> 1500/2352); clientHeight constant 852; composer height constant 36. Open suspects not testable here: real Windows scrollbar plus the companion walking over the chat, and Web on with a model reachable.
- Lag log: `keydown on textarea#chat-input 712 ms`: here keydown 64 ms with an 8 ms handler (Event Timing, no CPU throttle), no long tasks in 20 s; so the 712 ms needs the owner's profile (or `CPU=4`). `nameMarkBuddyTempo` is a 50 ms timer (avatars.js:5543, `NMB_TEMPO_MS`), not per frame; my wrapper saw 0 calls in headless, so its 7 to 13 ms rows stay unverified. Next: run probe.js with `CPU=4` and the companion walking, log `getAnimations` flush time inside `nameMarkBuddyTempo`.

Found, not fixed:
- Old chats saved before this change have no `by`, so they stay text only; no migration (no data to rebuild a badge from).
