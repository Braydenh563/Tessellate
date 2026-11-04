# stopwatch-diagram-1104 remaining

- done 2f30451: INBOX 1651, a stopwatch's laps area holds its height (`.clock-laps-held`, utilities-lazy.css); Lap top 768.8 / 750.8 / 732.8 / 678.8 before for 0/1/2/5 laps, 672.8 at every count after.
- done (diagram commit): INBOX 1652, the 100% button is a live readout (`math.percent`, diagram-view.js paint); 100% / 125% / 156% / 100% over open, Ctrl+wheel, plus, Fit.
- not reproduced: a giant three-block picture on a fresh open (img 186x354 = viewBox 186x354, pane 659x434); the owner's was a zoomed state with a static "100%" label, or an older cached asset (assets are hash-stamped; owner should reload).
- next: INBOX 1652 asks for diagram R3 so the change is visible (DOCUMENTS_PLAN); not done here.
- orchestrator: CHANGELOG lines, INBOX 1651/1652 resolve; stopwatch card is now 96px taller from the first lap (reserved space), judge if a smaller reserve is wanted (utilities-lazy.css .clock-laps-held).
- not verified: touch pinch path (shares zoomTo/paint with the wheel path), the owner's actual build.
