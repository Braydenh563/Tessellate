# deskfloat-1109 remaining

Done: a2dda42 (1699: hang tail clip, hang follows its window); the reactions commit (1700) follows it in `git log`.

- Not verified on a real Windows desktop: the clip fix is measured on the shipped frames at 96 and 192 dpi, and the reaction path on the fake win32; nothing ran against a real `GetForegroundWindow`, `EnumWindows` or a 200% display.
- Stretch clip (found, not fixed): a pose stretch (`sy` above 1) is anchored at the feet and grows upward, so frames with a small top margin (`fall`, 0 px at sy 1.1) can touch the canvas top. Needs the engine's real `sy` range per frame before a margin is chosen: `sprites.py` `_warp`.
- Cursor glance (owner's "follow the cursor"): the pointer watch exists (`extras.WATCH_MS`, the notice state); no new look-at-cursor reaction was added. If the owner still sees none, log the pointer reads first: `engine.py` notice entry.
- A float that settles with no hang (a drift goal over a window that left) was not reproduced; the hang case was the only mid-air state found (`runner._wants_scan` skipped a hang).
