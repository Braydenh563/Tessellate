# hascss-1111 (INBOX 1716, the `:has()` restyle)

Probe: Playwright, CDP 4x CPU, 2560x1504 at scale 2, Library Images tab, 240 tiles (14,000 elements); `document.body.appendChild(span); document.body.offsetHeight`, median of 15.

- Done `86e47c3c2`: `body:has(#library-media-selectbar:not(.hidden))` (07-whiteboard-misc.css, 08-consistency.css) became `body.library-media-selecting`, set in `syncLibraryMediaSelectbar` (library.js). Body append 77.8 to 2.3ms (light), 76.7 to 2.4ms (dark); `<html>` append 2.4ms. Computed style of tiles and ticks identical in four states, both themes. `tests/test_css_body_has.py` allowlist is empty; `tests/test_lag_has_library_1716.py` pins it.
- Pinned by a trace (Tracing, `disabled-by-default-devtools.timeline.invalidationTracking`): `ScheduleStyleInvalidationTracking changedPseudo=has` on BODY (two sets), then 976 `Related style rule` recalcs (480 elements: 240 figures, 240 ticks). A CSSOM bisect (delete every `:has` rule, reload, measure) was run before the fix and left the median at 61 to 67ms (deleteRule does not rebuild the invalidation sets), so it is not the method; the trace, not the bisect, is the method.
- Not the cause: `.library-image-tile:has(> .library-image-frame)` (per-tile, child-combinator subjects), `00-tokens-shell.css` and `library-lazy.css` `:has` rules; none appeared in the body-append trace.
- Found, not fixed: `tests/test_static_compression.py::test_the_app_scripts_stay_under_the_ratchet` fails at base (250606 bytes gzipped, cap 250450), with and without this change; `bash scripts/gate.sh --staged` fails on it alone.
- Next: a text change inside a `:has()` subject is not slow here (0.7 to 1.1ms); the owner's 40 to 300ms text case, if it returns, needs a trace at his zoom.
