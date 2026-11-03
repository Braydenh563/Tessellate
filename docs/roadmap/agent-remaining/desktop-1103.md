# desktop-1103: what is left (INBOX 1620, 1611)

Done: window flags, monitor clamp, menu rows, Guide, tests (`tests/test_desk_companion.py`). Nothing was run on Windows.

Why Wallpaper Engine could hide it: it parents its wallpaper window under the desktop's WorkerW layer. A window that is minimised, saved on a monitor that is gone, or not topmost when the wallpaper window is re-stacked can sit behind it, while the taskbar thumbnail (a window that exists) still shows. Fix: `desk_companion.raise_on_desktop` (tool window style, no taskbar button, topmost, restored if minimised, SW_SHOWNOACTIVATE) after every show, and `pick_area` puts a saved place on a monitor that is there.

Left:
- Verify on Windows 11 with Wallpaper Engine: shown after the X, no taskbar button, stays above the wallpaper, not stealing focus (`core/desk_companion.py` `raise_on_desktop`; `window_handle` assumes pywebview's WinForms `window.native.Handle`).
- If still hidden: re-assert HWND_TOPMOST on a timer or on the display-change event; `focus: False` needs a pywebview that accepts it (the TypeError fallback drops it).
- The menu row needs the desktop-shell answer cached (`isDesktopShell`); the very first right-click of a session may lack the row until `/health` answers (`frontend/js/companion-menu.js`, the `isDesktopShell === true` block).
- 1611: the switch is not yet mirrored into Settings, Appearance, Corner companion (`frontend/index.html` near `pref-desktop-companion`, `settings.js:329`); the new menu row is the second way in.
- The existing desktop icon comes from `start.bat --shortcut` / Settings, or an Inno install with the task ticked; the installers add none by default (`installer.iss:91` is `unchecked`, `installer.wxs` has none). An existing icon is the owner's to delete.
- INBOX 1620 and 1611 not resolved: the Windows check is outstanding.
