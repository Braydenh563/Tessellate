"""INBOX 1688 (a): every path that brings the window back keeps a maximised window
maximised. pywebview's restore() sets the Normal state, so it is only for a
minimised window, and a maximised one is put back afterwards."""
from types import SimpleNamespace

import tessellate.__main__ as launcher


class _Event:
    def __init__(self):
        self.handlers = []

    def __iadd__(self, fn):
        self.handlers.append(fn)
        return self

    def set(self):
        for fn in self.handlers:
            fn()


class FakeWindow:
    """Records the state the way a WinForms form does."""

    def __init__(self):
        self.state = "normal"
        self.hidden = False
        self.calls = []
        self.events = SimpleNamespace(maximized=_Event(), minimized=_Event(), restored=_Event())

    def _go(self, state, event):
        self.state = state
        getattr(self.events, event).set()

    def maximize(self):
        self.calls.append("maximize")
        self._go("maximized", "maximized")

    def minimize(self):
        self.calls.append("minimize")
        self._go("minimized", "minimized")

    def restore(self):
        self.calls.append("restore")
        self._go("normal", "restored")

    def show(self):
        self.calls.append("show")
        self.hidden = False

    def hide(self):
        self.calls.append("hide")
        self.hidden = True

    def evaluate_js(self, script):
        pass


def _tracked(state="normal"):
    w = FakeWindow()
    launcher._track_window_state(w)
    if state == "maximized":
        w.maximize()
    w.calls.clear()
    return w


def test_a_maximised_window_hidden_to_the_tray_comes_back_maximised():
    w = _tracked("maximized")
    w.hide()
    launcher._bring_forward(w)
    assert w.state == "maximized" and "restore" not in w.calls


def test_a_maximised_then_minimised_window_returns_maximised():
    w = _tracked("maximized")
    w.minimize()
    launcher._bring_forward(w)
    assert w.state == "maximized"


def test_a_minimised_normal_window_returns_normal():
    w = _tracked()
    w.minimize()
    launcher._bring_forward(w)
    assert w.state == "normal"


def test_every_return_path_goes_through_the_one_helper():
    """Tray items, a reminder card and a second launch all end in `_focus_window`."""
    w = _tracked("maximized")
    w.minimize()
    launcher._focus_window(w)
    assert w.state == "maximized"


def test_an_unmaximised_window_is_never_forced_to_maximise():
    w = _tracked()
    w.hide()
    launcher._bring_forward(w)
    assert "maximize" not in w.calls and w.state == "normal"


def test_a_user_restore_forgets_the_maximised_state():
    w = _tracked("maximized")
    w.restore()
    w.minimize()
    launcher._bring_forward(w)
    assert w.state == "normal"
