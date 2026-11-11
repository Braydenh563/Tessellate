# avatars2-1111 (INBOX 1716, 1726, 1741; follow-on to avatars-1111.md)

Probe setup: Playwright, 4x CPU, 1280x800 at scale 2, Library Images tab (about 30,000 nodes), alternating base and new, 3 rounds, 6 s warm-up. Probes stay untracked in the session scratch dir.

- Done: the companion band is appended under `<html>` (not `<body>`), so no companion mutation reaches the body-level `:has()` rules. Poke timer script/forced 137-218/111-195 to 17-61/5-30 ms; Blend sum 822-1315 to 136-226 ms (max 169-196 to 27-72); Tempo max 127-264 to 7-14 ms; Act per call 5-33 ms. Pointerup/click durations stay noisy (cold first click highest) and are not claimed.
- Disproved: priming, deferring or reordering the Blend reads (the swap's `:has()` cost is paid before the next frame either way); Act ahead of Express would drop the joy bounce.
