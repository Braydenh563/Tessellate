# graphfeel-1010 (INBOX 775, 792, 796)

Built: the warm-up played back after a `frame` fit (graph-worker.js `warmLayout`, `introStep`; graph-canvas.js `gcFrameIntro`); `graphFitFrame` (graph.js) with overlay and panel insets (`gcFitInsets`, `GC_FIT_OVERLAYS`) and a refit on a panel opening or closing (`gcRefitForPanels`); `smallSpread` (graph-worker.js). Sweep: scratchpad/ui-sweeps/graphfeel.js.

Open:
- 775 "the cluster fills about a fifth of the canvas; after Fit, about half" and "the bubbles overlap": not reproduced here. Seeded 34 notes, 34 links (7 categories, 12 unlinked), 1440x900, DPR 1 and 1.5: base fill 0.92 of the free canvas, 0 overlapping pairs at rest, also with 50 similarity lines in the worker harness. Needs the owner's notebook state (Shape, sliders, similarity, a saved view) or a screenshot with the options open.
- Three notes at 1440x900 fill 0.80 of the free height (0.798 measured): the fit's zoom clamp (`GRAPH_FIT_MAX_ZOOM` 2.5, graph.js) stops it; a larger `SMALL_SPREAD` (graph-worker.js) or clamp would clear it.
- 796 built: `graphCloseOtherMenus` (graph.js, the lazy bundle), caught on the way down from the head's '?', gear and ⋯; app-wide it is not done: the boot and app-script gzip caps had 35 bytes free (a shared `closeOtherMenus` in menus.js cost 98).
- INBOX 775, 792 and 796 stay in INBOX for the orchestrator to resolve at merge.

Not verified:
- The desktop webview (pywebview) and a slow machine: the 450 ms warm-up budget on a slow CPU records fewer ticks, so the playback is shorter.
- Reduced motion was checked in source and the harness, not in a browser run.

Found, not fixed (pre-existing on the base, gemini/composer-improvements at 3b8e4342c):
- tests/test_frontend_wake_sources.py: documents.js raf 14 to 15.
- tests/test_global_scope_ratchet.py: 278 `typeof x === "function"` guards against a cap of 277.

Round 2 (the owner: "the graph is still completely broken", the line; "it just suddenly changes or disappears and reappears"):
- Root cause of the line, as reproduced: the Layout preference holds Tree or Arc (mirrored server-side, `MIRRORED_UI_EXTRAS` in ai-tools.js), both static; a 34-note tree was framed to its width only and ran off the map. Not reproduced: the owner's exact screen (vertical Arc needs a map taller than 1.15x its width). If the owner is on Force, this is not the cause: ask for the Layout value.
- Open: notes leaving the picture vanish rather than fade out (`gcBornAlpha` fades new ones in only; graph-canvas.js).
- Open: Arc stays a line by design; a person who picks it by mistake sees "a broken graph". Recommendation for INBOX: say the layout's name on the map when it is not Force (one chip in the dock).
- Not verified: Saved views and local/global switches through the view-change sweep (layouts, Refresh and a return to the tab were measured); the reduced-motion path of the computed-layout glide in a browser.


## Moved from agent-remaining, 2026-10-26

Built: the warm-up played back after a `frame` fit (graph-worker.js `warmLayout`, `introStep`; graph-canvas.js `gcFrameIntro`); `graphFitFrame` (graph.js) with overlay and panel insets (`gcFitInsets`, `GC_FIT_OVERLAYS`) and a refit on a panel opening or closing (`gcRefitForPanels`); `smallSpread` (graph-worker.js). Sweep: scratchpad/ui-sweeps/graphfeel.js.

Open:
- 775 "the cluster fills about a fifth of the canvas; after Fit, about half" and "the bubbles overlap": not reproduced here. Seeded 34 notes, 34 links (7 categories, 12 unlinked), 1440x900, DPR 1 and 1.5: base fill 0.92 of the free canvas, 0 overlapping pairs at rest, also with 50 similarity lines in the worker harness. Needs the owner's notebook state (Shape, sliders, similarity, a saved view) or a screenshot with the options open.
- Three notes at 1440x900 fill 0.80 of the free height (0.798 measured): the fit's zoom clamp (`GRAPH_FIT_MAX_ZOOM` 2.5, graph.js) stops it; a larger `SMALL_SPREAD` (graph-worker.js) or clamp would clear it.
- 796 built: `graphCloseOtherMenus` (graph.js, the lazy bundle), caught on the way down from the head's '?', gear and ⋯; app-wide it is not done: the boot and app-script gzip caps had 35 bytes free (a shared `closeOtherMenus` in menus.js cost 98).
- INBOX 775, 792 and 796 stay in INBOX for the orchestrator to resolve at merge.

Not verified:
- The desktop webview (pywebview) and a slow machine: the 450 ms warm-up budget on a slow CPU records fewer ticks, so the playback is shorter.
- Reduced motion was checked in source and the harness, not in a browser run.

Found, not fixed (pre-existing on the base, gemini/composer-improvements at 3b8e4342c):
- tests/test_frontend_wake_sources.py: documents.js raf 14 to 15.
- tests/test_global_scope_ratchet.py: 278 `typeof x === "function"` guards against a cap of 277.

Round 2 (the owner: "the graph is still completely broken", the line; "it just suddenly changes or disappears and reappears"):
- Root cause of the line, as reproduced: the Layout preference holds Tree or Arc (mirrored server-side, `MIRRORED_UI_EXTRAS` in ai-tools.js), both static; a 34-note tree was framed to its width only and ran off the map. Not reproduced: the owner's exact screen (vertical Arc needs a map taller than 1.15x its width). If the owner is on Force, this is not the cause: ask for the Layout value.
- Open: notes leaving the picture vanish rather than fade out (`gcBornAlpha` fades new ones in only; graph-canvas.js).
- Open: Arc stays a line by design; a person who picks it by mistake sees "a broken graph". Recommendation for INBOX: say the layout's name on the map when it is not Force (one chip in the dock).
- Not verified: Saved views and local/global switches through the view-change sweep (layouts, Refresh and a return to the tab were measured); the reduced-motion path of the computed-layout glide in a browser.
