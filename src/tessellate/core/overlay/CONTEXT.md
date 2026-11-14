# core/overlay: orientation

The goose-style desktop companion: a native, transparent window that lives on the desktop, with a pure behaviour engine and per-platform windowing.

| group | files (globs) | what | guarding tests (globs) |
| --- | --- | --- | --- |
| Window and loop | `__init__.py`, `host.py`, `runner.py`, `win32.py`, `x11.py`, `xlib.py` | The layered popup on its own thread, the Win32 and X11 calls, the join of window, behaviour and frames | `tests/test_overlay_host*.py`, `tests/test_overlay_runner*.py`, `tests/test_overlay_x11*.py`, `tests/test_overlay_roam*.py`, `tests/_x11_fake.py`, `tests/_overlay_fake.py` |
| Behaviour engine | `engine.py` (and its mixins `engine_flight.py`, `engine_touch.py`, `engine_beats.py`), `behaviour.py`, `pacing.py`, `presence.py`, `travel.py`, `perches.py`, `landing.py`, `sizing.py` | The pure state machine: moods and body language, roaming, perches on window tops, travel, landing, pacing, size | `tests/test_overlay_*.py`, `tests/overlay_*.py`, `tests/test_companion_travel*.py`, `tests/test_companion_perch*.py`, `tests/test_companion_landing*.py` |
| Extras and figure | `extras.py`, `props.py`, `screenwatch.py`, `faces.py`, `sprites.py`, `capture.py`, `catalogue.py` | Small acts and props, reactions to what is on screen, micro expressions, pre-rendered frames, the companion catalogue | `tests/test_extras*.py`, `tests/test_overlay_faces*.py`, `tests/test_overlay_sprites*.py`, `tests/test_throw*.py`, `tests/test_companion_catalogue*.py`, `tests/test_catalogue*.py` |

Find a function: grep `docs/CODEMAP.md`, then read that line range.
