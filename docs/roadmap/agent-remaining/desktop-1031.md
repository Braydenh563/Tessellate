# desktop-1031: the desktop companion (INBOX 1464, BACKLOG 16)

Branch agent/desktop-1031. Built: second window (`core/desk_companion.py`), the page (`frontend/desktop-companion.html`, `desk-env.js`, `desk-companion.js`, `desk-companion-lazy.css`), Settings switch and help, tray item, Guide topic, tests (`tests/test_desk_companion.py`), sweep (`scratchpad/ui-sweeps/deskcompanion.js`).

Left, one line each:
- Windows check, needs the owner's computer: transparency (`transparent=True` is asked only off Windows; Windows draws the `?card=1` card), always on top, bottom-right above the taskbar (`work_area`, `core/desk_companion.py`), drag and resize on a scaled screen (the page sends `screenX` deltas; pywebview may want physical pixels).
- Click-through outside the character's outline (hub decision 2026-10-31): the resting window is only the character's box (112 by 152, `REST_SIZE`); true pass-through needs a native window region (`SetWindowRgn` on `window.native.Handle`), not built, untestable here.
- The wandering companion's behaviour (companion-1031, Fable) is not drawn here: the page draws the still figure through `characterFor(seed).figure()`; if that agent adds an entry point for a standing figure, `desk-companion.js` `draw()` should use it.
- Persona choice draws the greeting's persona (`dashboard_persona`) else Atlas: the chat's persona picker is a live element the page does not have.
- Pre-existing, not mine: `tests/test_undo_coverage.py::test_exempt_only_shrinks` fails on the base (`chat-attach.js:chatSendTurn` no longer needs its EXEMPT row).
