# tabspeed-1031 (INBOX 1492 frontend half: tab switch, openDocument, CodeMirror measure loop)

Setup: wt-tabspeed, port 8848, data /tmp/claude-0/tabspeed-data (500 notes), 4x CPU, 1440 wide. Scripts are in /tmp/claude-0/tabspeed-scr (not in the repo): `tabbench.js` (click event, LoAF), `cpu.js` (style, layout, paint totals per click, one variant per process; the only measure that repeated on a noisy host), `inval.js` (invalidation tracking), `ro.js` (ResizeObserver callbacks), `docprobe.js`.

Done
- 6d6fb05: `--notes-sticky-top` (phone-shell.js `initNotesSubtabHeightToken`) wrote `10px` on hide and `46px` on show; the box decides now and an equal value is not written. This was the whole third style pass (1,794 elements) of the Notes click. Row shells excluded from the `:has()` and `content-visibility` rules (`:where(:not(.row-shell))` keeps specificity), `tabPageScroller` bounded to four levels.
- Before to after, Notes click at 4x: style recalculation 340 to 185ms, layout 90 to 75ms, long frame (LoAF) 463 to 270ms, forced layout 251 to 77ms, click median 544 to 312 (400 in a second run, host load 6 to 7). Dashboard click 424 to 344, Library 256 to 264, Graph 384 to 424 (no change expected, noise). `tabPageScroller` Library 43 to 141ms to 5 to 8ms, Notes 13 to 31ms to under 1ms.

Not reached: the 250ms target (Notes click is 270 to 400). What is left, measured:
- Two style passes remain (601 then 1075 elements, 50 to 100ms each) and about 75ms of layout: the reveal restyles the whole page because `display: none` discards styles. `content-visibility: hidden` on hidden tab roots keeps them and halved style plus layout in a test (style 441/289 to 209/180ms), but it changes `offsetParent`, geometry reads and focus for everything in a hidden tab (44 `offsetParent` reads, whiteboard.js 59 geometry reads, documents.js 23), so it needs its own pass with a test of each reader; not adopted.
- `revealTab` forced layouts (`scrollTo` 20ms at 4x, `routerOnVisit`'s `pushState` 20ms at 4x, native cost). Moving either past the paint changes what Back and `history.state` see.
- The Dashboard's first style pass (769 elements, 100ms) and its p5 art draw (about 250ms of draw time in the two seconds after a visit); `sizeDashWidgets` reads.

openDocument: not reproduced. With a 3,000-line markdown document, a 300-function `.py` file and a remembered position (`docRestorePosition` after a jump to 60%) the continuation forces 0 to 2ms (LoAF `forcedStyleAndLayoutDuration`; 17ms on the very first open, which is the pane's own first layout). The owner's 81ms is a bigger notebook; run `docprobe.js` with `POS=1` there. CodeMirror's idle `work` callbacks cost about 100ms per open, off the input path.

CodeMirror "Measure loop restarted more than 5 times": not reproduced (300-function `.py`, 3,000-line markdown, tables, scrolls, an edit; no warning). Mechanism, from CodeMirror's `measure()`: a plugin that calls `requestMeasure` from `update` on `geometryChanged` or `viewportChanged` (both set inside the measure loop) adds one pass to the loop per geometry change, so a document whose line heights take four passes to settle reaches the sixth. The two plugins that do this are `docStickyScroll` (documents-code.js:2411) and `docTableGripsPlugin` (documents.js:6543). Untested fix: request from those two flags through one `requestAnimationFrame` instead of inside `update`. Both writes are already idempotent or absolute-positioned, so they are not themselves a loop.

Found, not fixed
- The `FrameRequestCallback` wrapper in lag-watch.js:238 is the owner's lag log itself and shows as 25 to 52ms in a traced frame when on; it only wraps while on.
- `scripts/gate.sh --staged` fails `test_handover_is_the_current_state_only` at the base too (HANDOVER over 600 lines).
