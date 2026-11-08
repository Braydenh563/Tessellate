# chatspasm-1108 (INBOX 1696 m): remaining list

## Done
- Cause: `syncChatJumpLatest` (frontend/js/chat-agent.js) toggled `.chat-transcript.has-jump-gap` on every other call
  on a thread that fits the pane. A pane never reports scrollHeight under clientHeight, so `spare` read 0 and
  `0 + gap (45px)` beat `SCROLL_STICK_SLACK` (40) whenever the strip was off; with it on, spare read 0 and removed it.
  Each stream delta, scroll or mutation flipped the transcript's padding, so `#chat-messages` went 544 <-> 589px
  (the composer and the message did not move). That is the up and down spasm; it also paid a pane layout per flip.
- Fix: `spare > 0 &&` in the `needed` test. A strip is only for a thread that really overflows; hysteresis kept.
- Test: `tests/test_jump_gap_1590.py::test_a_short_chat_never_toggles_the_strip_on_every_call_1696` (realistic
  scrollHeight >= clientHeight model; failed before the fix).
- Probe: `scratchpad/ui-sweeps/chatspasm1696.js` (BUDDY=1 enables Atlas in-app companion, CPU=4, PRE=n earlier turns,
  DUMP=1 per-frame rows).

## Numbers (4x CPU, new chat, first message, fake model)
- Pane height direction reversals in 3.5 s: 51, 55, 66, 69 (before) -> 0, 0, 0 (after). Amplitude 45 px.
- Composer height reversals 0 before and after; composer top and last-message top never reverse (range 25 px = the
  message arriving). With 1 earlier turn the thread overflows and there were 0 reversals before too.
- LoAF in the 3.5 s after Send with the companion on: sum 1559-1676 ms (before) vs 1171-1252 ms (after).

## Left
- `nameMarkBuddyTempo` (avatars.js:5580) forced style flush (54-187 ms at 4x, 1 frame in 3.5 s) still appears
  during the stream in about half the runs, before and after. A 400 ms `uiSettlingUntil` hold on Send was tried
  and removed: no measured gain (it fires later, mid-stream, when the deltas dirty the pane). Next: make its idle
  gate wait for a stream-quiet frame (chat-turn.js delta path), or read `getAnimations` less often while
  `chatStreaming`.
- The keydown on `#chat-input` (58-79 ms at 4x, 10-14 ms forced) was not reproduced at the owner's 456 ms; a long
  saved chat (PRE=3+) may cost more. Not traced.
- Not verified on the owner's machine or a real model.
