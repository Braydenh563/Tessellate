# shell-1112: remaining after the shell build agent (Sh1, Sh2, Wb1)

Branch worktree-wf_ee46a876-5a8-4. All ten rows are done; two have a part that cannot be done here.

- X16 (D18): trim decodes the whole recording (about 700 MB an hour). A server-side cut needs a container writer and a decision on keeping raw audio; owner call O32 (OPEN.md:4771 item 8). Not started.
- X16 (boot CSS): measured, not moved. `bootcsscov.js` shows the largest unmatched runs (`nm-buddy` in 08, 6,826 gz; md-table and code blocks in 05, 4,434 gz; whiteboard topbar and map strip in 07, 3,100 gz each). `nm-buddy` and `nm-atlas` are read by seven scripts and about 300 test lines; moving them is a cascade-order and design call for a session that can sweep every look.
- I25 (trackpad): the lightbox pinch rate per gesture needs a real trackpad. Everything else on the row (preset dropdowns, the present page counter) is driven and passes.
- Found, not fixed: `scratchpad/ui-sweeps/toursteps.js`, `tourdim.js`, `tour.js` read `TOUR_SECTIONS` and `tourRun` as globals; both are inside tour.js's IIFE now, so those sweeps stop on a ReferenceError. Walk the whole tour with `openTour()` (no section) instead.
- Found, not fixed: the lightbox drops the zoom readout below 600 wide (INBOX 430), so the typed zoom of INBOX 1694 b has no phone form there; a decision, not a defect.
