# motion-1031 remaining (INBOX 1462)

Done: page arrival (opacity plus 4px `translate`, `--ui-base`), selection popup, spelling menu and OCR popover on the shared menu recipe, graph hover card fade, Settings sections on `ui-fade`.

Left, one line each:
- Exits of the three added popups stay instant (an exit needs the `.hidden` discrete-display rule per surface; 10-responsive.css, "the floating panels" section).
- Sub-tab panels (Library, Notes) still do not fade: `@starting-style` cannot tell a section from its page arriving (08-consistency.css, "a page arrives"). Not changed.
- `.ai-status-popup` reads `--motion-fast` (00-tokens-shell.css:1612, listed DECORATIVE), so it ignores the Interface animations switch.
- The brief asked for reduced motion and perf mode to turn this off; the standing owner decision (DESIGN.md, "Interface animations", 2026-10-05) keeps the polish on under both, governed by the switch. Not remade.
- Boot CSS headroom is 15 bytes (179,085 of 179,100).
- Extra layouts: about 2 per switch on chat and reminders (the companion's `transitionrun`/`transitionend` keep-up, avatars.js:5398); not reduced.
