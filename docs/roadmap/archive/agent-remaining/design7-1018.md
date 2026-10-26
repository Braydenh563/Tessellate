# design7-1018: INBOX 1300 C30 (lightbox redesign)

- done: f4bcef8 C30 (top bar, view dock, filmstrip, keys, swipe, pinch, idle fade; PDF-to-picture zoom fix), then this docs commit.
- next: none.
- Decisions (DESIGN.md "A full-screen viewer of a file"): bars on `--modal-bg` (theme ink, not white on scrim); the readout is against the picture's pixels (53% at Fit for a 2400px picture); below 600 the side arrows move into the dock, and Open in a new tab and the '?' leave the top bar; Details remembered per viewer in localStorage.
- Not verified: a PDF's zoom and page stepper in the new dock (no PDF renderer package in the sweep's data dir, so pages did not render); a real trackpad pinch (wheel with ctrlKey); real touch hardware (CDP touch events only); Windows webview.
- Found, not fixed: scratchpad was 768 files on the base (cap 766); three old sweeps went (lightboxentry.js superseded, graphoptheights.js, seg665-toolbar.js).
