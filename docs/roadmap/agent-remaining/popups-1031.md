# popups-1031 (INBOX 1478): what is left

Done: the anatomy sheet and glyph decorator (`popup-anatomy-lazy.css`, `popup-glyph.js`), glyph tab rows on Skills, Tasks and the Appearance panel, Activity tabs with counts and cards, four-dot theme tiles, the reference's highlight and border on the Appearance panel and Activity, recipe row and lints.

- Cards: only Activity has `.pop-card` sections; the other Settings panes keep their `.card` headings. Next: move one pane at a time onto `.pop-card` (frontend/index.html, Settings panes).
- Tab counts: Skills (installed) and Appearance (themes) carry counts; Tasks pane tab counts show 0 until a run exists. Next: counts for Add and Settings tabs only if they mean something (frontend/js/skills.js).
- Glass: the 32% tint and 24px/170% blur are not adopted (AA fails, third blur variant refused by lint). A reference-style glass needs a new token pair and a lint change, an owner decision.
- Peek in the Settings, Appearance head: not added (the Appearance panel already has Peek).
- Script-built popup glyphs come from a title table (`popup-glyph.js` POPUP_GLYPHS); an unmatched title gets `app-window`.
- Not verified: the glyph on every script-built popup (only the static heads and the five opened by `scratchpad/ui-sweeps/popupanatomy.js`), real touch devices.
