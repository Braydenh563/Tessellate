# shellux-1030: what is left

Branch `agent/shellux-1030` (from `claude/sharp-thompson-45hngp`), not pushed. Sweeps are in /tmp/claude-0/shellux-sweeps (untracked).

Done
- INBOX 1333b: the timeline strip (`timeline` reply panel: `slash_more.timeline_panel`, `slash.timeline`, `replyTimelinePanel`). INBOX 1333 resolved.
- S26 (aef5a83): phone toast compaction. S39 and S41: measured, no change needed.

Left
- S26 residual: at 360x640 the persistent search-by-meaning toast (152px) still covers the Ask box's button (toast top 352, button 361 to 405). Clearing it needs a toast under 119px: the message cut to two lines, which drops the "from huggingface.co and pypi.org" disclosure the owner asked for. Decision for the owner: shorten it on phones or keep the disclosure. At 390x667 it covers 6px of 44, at 390x844 none (gap 147px).
- Found, not fixed: `semanticOffer` (status.js:2885) runs inside `renderSettings`, so the search-by-meaning question toast opens only once Settings has been rendered, not from the status poll its header (semantic-notice.js:3) describes. On the Ask tab with the offer owed and Settings never opened it does not show (0 toasts in 20 s at 390x844, `semantic_offer` true).
- S39 dark tab ring: contrastui.js counts a gradient ground as skipped (145 surfaces skipped per theme), so the negative-offset ring on the main tabs is not measured there; by the tokens it is `rgb(120, 168, 255)` on `rgb(30, 30, 28)`, 7.03:1.
- S41 not changed: `strong.library-card-title.card-open` is 22.1px tall (one of 22 sits within 12px of the status bar when scrolled to the foot); the whole card is its target (`.library-card-whole`), so no change.
- Timeline strip: no `/made` strip for a window in the future, and one point (a single day with one note, in /recent) draws by the hour; the strip is not clickable (no bucket to open). Keyboard reach: it is a labelled image, the numbers are in its label.
