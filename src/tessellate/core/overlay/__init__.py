"""The goose-style desktop companion: a native, transparent, click-through-where-clear
window that draws pre-rendered frames of the companion and moves along the
screen's floor (INBOX 1645; BACKLOG 16, rows O1 to O4).

`win32` is the only file with ctypes declarations, `host` the window and its
message loop, `sprites` the frames, `engine` the behaviour (pure, no Win32).
Everything imports on any platform; only `win32.load()` needs Windows.
"""
