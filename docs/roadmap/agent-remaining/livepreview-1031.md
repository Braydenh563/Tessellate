# livepreview-1031: INBOX 1473 (b), Live view reveals per span

- done: 7879a5e span rule, probes, cm-reveal.js; 07f8ec8 recipe row, lint, changelog; ac9b5c9 Guide topic `live-view-marks`. Gate green; cm-live.js all pass, doclonglive.js 6 of 6.
- next: none open. Not verified: a real IME (CDP composition only) and the notes editor's Live box (same plugin, not driven). Found, not mine: typing on 5,000 lines spends most of each key in the prose checker (`renderDocProse`, `docProseSkipMask`, `docLinkOfferAsk`, documents.js ~17697 and ~18010; documents-prose.js ~386), long tasks to 540ms with Live on or off.
- found: cm-reveal.js fails 3 checks on the base branch too (bullet spacing `•a bullet`, task line `a task`, callout label empty).
