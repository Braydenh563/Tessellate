# lagjj-1108 (INBOX 1696 jj, q; chatspasm-1108 leftover): remaining list

Probes untracked, scratch dir (p1.js chat send + tempo timing, p2.js pointer moves, p3.js CodeMirror and tab taps). 4x CPU, 60 notes, :8798, fake model. The machine was at load 7 to 10 (other agents), so absolute ms are noisy; compare within a pair.

## Target 1: nameMarkBuddyTempo forced style
- Cause: the beat's reads (`getAnimations` for the look, `playState`) ran before a frame had drawn the previous beat's steps (frames slower than the 50 ms beat at 4x), and the periodic look's idle gate opened while the stream kept dirtying the pane (look at +300 ms after Send: ask false, ready true, 290 to 364 ms forced).
- Fix: a beat waits (3 times, 20 ms) until a frame and a task after it have run since its last write; the periodic look is deferred while `chatStreaming` (6 s) and re-arms its idle gate when the page was written after the gate opened (8 times at most).
- Before (tempo forced ms in the 3.5 s after Send, runs): 108, 190, 187, 193 | 33, 0, 23 (quieter machine). After: 0, 0, 0 and four more zero runs.
- Test: tests/test_tempo_look_1108.py.
