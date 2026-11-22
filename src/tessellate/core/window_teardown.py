"""The desktop window's own teardown noise is not a failure (L-world-class-117).

On a restart WebView2 (Chromium) can print "Failed to unregister class
Chrome_WidgetWin_0. Error = 1411" (ERROR_CLASS_DOES_NOT_EXIST) as a window
closes; pywebview surfaces it from `webview.start`, and the app took it for a
crash, so Restart closed the window and nothing came back. It is benign: the
class was already gone. Seen on a real Windows machine only; here it is tested
against a fake window and a fake stderr.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)

#: Teardown messages that mean "the window is already gone", never a failure.
BENIGN_TEARDOWN = ("Failed to unregister class Chrome_WidgetWin",)


def is_benign_teardown(text: str) -> bool:
    """True when every non-empty line of `text` is a known teardown message."""
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    return bool(lines) and all(any(m in ln for m in BENIGN_TEARDOWN) for ln in lines)


def run_window(start: Callable[[], object], *, restarting: bool, relaunch: Callable[[], object]) -> str:
    """Run the window loop `start`. Returns "closed", "benign" or "relaunched".

    A benign teardown error is logged and ends the loop like a close; when
    this process is a restart's new copy (`restarting`), it starts the window
    again once through `relaunch` instead of leaving nothing running. Any other
    exception, including a TypeError the caller falls back on, propagates."""
    try:
        start()
    except TypeError:
        raise
    except Exception as exc:
        if not is_benign_teardown(str(exc)):
            raise
        logger.warning("window teardown noise, treated as non-fatal: %s", exc)
        if restarting:
            relaunch()
            return "relaunched"
        return "benign"
    return "closed"
