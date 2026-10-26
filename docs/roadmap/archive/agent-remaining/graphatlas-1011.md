# graphatlas-1011 (Opus): the companion's large view, then the Graph and Atlas ledger rows

`id | status | evidence or commit`. Ids are the scratchpad OPEN-ledger's (rows 661 to 699 Atlas and the companion, B34 to B36; 928 to 968 Graph, B54 to B56).

## Owner reports, 2026-10-11

| id | status | evidence or commit |
| --- | --- | --- |
| companion (a) zzz not animated in the large view | done | see commit: wake-on-open under a still pointer (viewersleep.js: yawned awake 1.8s after the view opened, Zs gone), act left on under sleep ("nmb-act-wave nmb-sleep" 7s) |
| companion (b) box focus ring | done | outline none on :focus and :focus-visible; keyboard glow (radial, 50% radius) behind the figure; click: fv false |
| companion (c) glitchy under load | done | companionload.js CPU=6: after hide mid-act, act stuck "nmb-act-wave" before, "" after; acts held past 2x spec: 6 and 3 before, 1 (the hidden one) and 0 after |
