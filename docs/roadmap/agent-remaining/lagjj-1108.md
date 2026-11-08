# lagjj-1108 (INBOX 1696 jj, q; chatspasm-1108 leftover): remaining list

Probes untracked, scratch dir (p1.js chat send + tempo timing, p2.js pointer moves, p3.js CodeMirror and tab taps). 4x CPU, 60 notes, :8798, fake model. The machine was at load 7 to 10 (other agents), so absolute ms are noisy; compare within a pair.

## Target 1: nameMarkBuddyTempo forced style
- Cause: the beat's reads (`getAnimations` for the look, `playState`) ran before a frame had drawn the previous beat's steps (frames slower than the 50 ms beat at 4x), and the periodic look's idle gate opened while the stream kept dirtying the pane (look at +300 ms after Send: ask false, ready true, 290 to 364 ms forced).
- Fix: a beat waits (3 times, 20 ms) until a frame and a task after it have run since its last write; the periodic look is deferred while `chatStreaming` (6 s) and re-arms its idle gate when the page was written after the gate opened (8 times at most).
- Before (tempo forced ms in the 3.5 s after Send, runs): 108, 190, 187, 193 | 33, 0, 23 (quieter machine). After: 0, 0, 0 and four more zero runs.
- Test: tests/test_tempo_look_1108.py.

## Target 2: pointerout lags (#lock-submit span, #dash-quicklinks, #dash-grid, #settings-nav)
- Every pointerout/mouseout/mouseleave listener reachable (grep): document-level only status.js toastHold (8 ms), the rest are per-element (ask-chart, whiteboard). Handlers run 0 to 31 ms (Event Timing run); the event's duration is its WAIT: pointerout n 194, maxDur 320 to 504 ms, maxWait 249 to 423 (p2.js: 6 mouse in/out passes over six dashboard targets at 4x). So the lag is the main thread busy when the event lands, not a handler; no delegated handler would help.
- The blocker found (instrumented `nmb.afterClean`): a mood's hand-over `nameMarkBuddyBlend(...)` (atlas.js setAtlasMood) 132 and 248 ms of reads at 4x, landing inside the pointer's move.
- Fix: `afterClean(fn, tries, snap, calm)` also waits out a pointer that moved within 160 ms (14 tries, then runs fn, never snaps for a pointer alone).
- pointerout maxDur before 320, 464, 360 -> after 232, 344, 248 ms (maxWait 249, 362, 268 -> 178, 256, 185); LOAF sum 6419, 7001, 12273 -> 3922, 8786, 3764 ms (3 runs each, load ~7).
- Still there: avatars.js `afterClean` timer callbacks `nmb.checkFrame` (32 to 60 ms) and tempo in the pointer window; the `#lock-submit` span is not on screen after sign-in, so that one cannot be hovered on the dashboard (not reproduced; likely the lock screen itself at boot).
