# deskfix-1110 (INBOX 1721 a, b, c)

Done
- a: a hanger answers a click, pat, poke and screen events on the edge (`Extras._fire_hanging`: face + `Engine.hang_kick_at` swing kick, no act). A hang that is changing (scrabble, pull-up, swing wind-up, letting go) leaves the event to the runner's queue, which gives it up after `SCREEN_WAIT` s (stated in the docstring).
- b: `Engine._grip` no longer adds the title-bar offset to a maximised window's "bar" (it is the screen top); `win32._clip_to_monitor` cuts a maximised window's GetWindowRect (top -8) to its monitor. test_overlay_dest_1683's bar grip line moved with it (intent: hands on the bar's edge, now its top).
- c: `_go` walks a leg shorter than `WARP_MIN` (1.5 figure widths) instead of a blink, cloud, bubble or portal. Hour sims with only a hang bar: 7 to 15 warps/hour, rests at both screen edges (unchanged by design: EDGE_ZONE).

Left
- c: with no standable top it still rests only in the two edge zones (travel.EDGE_ZONE); a mid-taskbar roam is a design choice (INBOX 1670 rest rules), not changed.
- c: the log still counts Shell_TrayWnd as "tool window"; the floor is the work area's bottom (rcWork), which is the taskbar's top, so nothing was needed beyond the counter label.
- d and e (activity variety, lower-body and ribbon motion): the Opus design pass.

Not verified: real Windows 11 at 2560x1600 (hang height on a Chrome tab strip, the pat on a hanger, the corner). All tests are FakeWin32 and a fixed clock.
