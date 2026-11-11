# Owner log 1111 (lag and log items): done and next

Measured at 4x CPU throttle on port 8787 (Playwright, CDP tracing, LoAF).

## Done
- Item 1: browser errors serialise as text (`recordBrowserLog.text`); tests/test_error_log_1549.py.
- Items 2, 8: Settings focus calls run a frame after the press; shell-reminders edge sync skips regions not last seen scrolled. Gear click 91 ms (82 forced) to 42 ms (3); ResizeObserver 23 ms (22) to 11 ms (9).
- Item 3: Dashboard tab click 210 ms (81 forced) to 55 ms (0).
- Item 9: log scroll listener passive and read a frame later; streamed records redraw at most four times a second. Logs forced layout 325 ms over 5 draws to 48 ms over 3.
- Items 6, 4: the idle library warm loaded stylesheets, restyling 850 elements (125 to 250 ms). It loads scripts only now; style and layout after a Settings open 190 to 233 ms to 36 to 39.
- Item 10: nav reveal (`revealRow`) and `skeletonRemember` read layout after the press. 54 ms and 96 ms forced layout to 6 to 10 ms.

## Measured, not reproduced
- Item 7 (`div.dock.dgm-shelf` pointerout): shelf pointerout 24 to 48 ms with 0 in handlers; the 120 ms worst case is render over the diagram shape, and its listeners are in files off limits to this agent.
- Item 4 (`#local-only-wrap` pointerout): the wrap has no handler; hover costs 48 to 64 ms. The large events are busy frames from the Settings open (Logs render chain) plus the warm restyle, both cut above.

## Next
- Item 5 (Dashboard first frame 697 ms): the dashboard has 4,405 DOM nodes at first paint. index.html carries 14 to 15 `<template data-surface>` payloads (693 KB of 828 KB served) that are parsed on load. Cut 1: serve each template from a lazy route and mount it on first visit. Cut 2: build the 365-span heatmap lazily with a placeholder of fixed height. Both cross the boot-budget and first-visit tests, so they are a separate step.
- `/extras` and `/jobs/last-runs` are fetched four times per Settings visit; share one in-flight request.
- Library hover handlers sit in files off limits here (`lightbox-view.js` and neighbours).
- Gzip ratchet: upstream tip is already 156 bytes over TOTAL_CAP (250,606); this branch adds about 31 over tip (250,637). Cap not raised.
