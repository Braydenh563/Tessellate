# dashcls-1031 remaining

- Done 7ee2603: help popover Escape (frontend/js/menus.js keydown handler): popover only, focus back on its button; 3 Settings/agent cases failed before, 5 of 5 pass after (settings x2, quick note, recovery key, agent panel).
- Done (this branch, second commit): dashboard revisit shift (dashboard.js sizeDashWidgets skips a hidden grid; renderDigestWidget awaits renderDayDigest). CLS over 5 revisits: 1440 0.342 to 0.000, 390 0.031 to 0.000, reduced motion 0.000.
- Not verified: the 0.21 to 0.23 and 3-column jump in the brief did not reproduce on a 40-note notebook (0.34 there, from the causes above); a notebook with many more notes, or a slow `/insights/day`, was not measured.
- Not verified: Escape with a popover open in the other dialogs that hold a "?" (doc template, space edit); the shared handler is the same code path.
- Next (found, not fixed): every Dashboard visit still runs `renderDashboard()` via app.js:1212 and `renderDashboard({refresh:true})` via navigation.js:1955; the second only refreshes bodies in place (no shift now), the first is the full draw hidden by `.dash-filling`. One of the two could go.
