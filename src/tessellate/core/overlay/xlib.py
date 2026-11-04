"""The X11 calls the Linux overlay needs, over ctypes (no python-xlib: the app ships
none, and `libX11` is on every X desktop).

`XConn` is the one object the rest of the Linux overlay talks to. It hands back
plain Python (ints, strings, tuples), never an X structure, so the tests replace
the whole class with a fake (`tests/_x11_fake.py`) and the host, runner and
window logic run unchanged.

Every call takes one lock (Xlib is told it is threaded through `XInitThreads`,
and the lock keeps a reply from being read by the wrong thread). Properties are
read as EWMH asks: 32-bit items arrive as C longs, so on a 64-bit machine they
are eight bytes wide.

Not run on Windows or macOS; on Linux it needs a display (`Xvfb` is enough).
"""

from __future__ import annotations

import ctypes
import ctypes.util
import hashlib
import logging
import os
import threading
from typing import Any

logger = logging.getLogger(__name__)
c = ctypes

# event types and masks (X.h)
KEY_PRESS_MASK_NONE = 0
BUTTON_PRESS_MASK = 1 << 2
BUTTON_RELEASE_MASK = 1 << 3
POINTER_MOTION_MASK = 1 << 6
EXPOSURE_MASK = 1 << 15
STRUCTURE_NOTIFY_MASK = 1 << 17
PROPERTY_CHANGE_MASK = 1 << 22
BUTTON_PRESS, BUTTON_RELEASE, MOTION_NOTIFY, EXPOSE, CONFIGURE_NOTIFY, PROPERTY_NOTIFY = 4, 5, 6, 12, 22, 28
CW_BACK_PIXMAP, CW_BORDER_PIXEL, CW_OVERRIDE_REDIRECT, CW_EVENT_MASK, CW_COLORMAP = 1 << 0, 1 << 3, 1 << 9, 1 << 11, 1 << 13
INPUT_OUTPUT, TRUE_COLOR, ALLOC_NONE, Z_PIXMAP = 1, 4, 0, 2
GRAB_MODE_ASYNC, CURRENT_TIME = 1, 0
SHAPE_BOUNDING, SHAPE_INPUT, SHAPE_SET = 0, 2, 0
PROP_MODE_REPLACE = 0
XA_ATOM, XA_CARDINAL, XA_STRING, XA_WINDOW = 4, 6, 31, 33
#: Alpha under this is clear (the same floor the Windows overlay uses).
ALPHA_FLOOR = 8

_ARGS_LOADED = False


class _Visual(c.Structure):
    pass


class XVisualInfo(c.Structure):
    _fields_ = [
        ("visual", c.c_void_p), ("visualid", c.c_ulong), ("screen", c.c_int), ("depth", c.c_int),
        ("klass", c.c_int), ("red_mask", c.c_ulong), ("green_mask", c.c_ulong), ("blue_mask", c.c_ulong),
        ("colormap_size", c.c_int), ("bits_per_rgb", c.c_int),
    ]


class XSetWindowAttributes(c.Structure):
    _fields_ = [
        ("background_pixmap", c.c_ulong), ("background_pixel", c.c_ulong), ("border_pixmap", c.c_ulong),
        ("border_pixel", c.c_ulong), ("bit_gravity", c.c_int), ("win_gravity", c.c_int),
        ("backing_store", c.c_int), ("backing_planes", c.c_ulong), ("backing_pixel", c.c_ulong),
        ("save_under", c.c_int), ("event_mask", c.c_long), ("do_not_propagate_mask", c.c_long),
        ("override_redirect", c.c_int), ("colormap", c.c_ulong), ("cursor", c.c_ulong),
    ]


class XWindowAttributes(c.Structure):
    _fields_ = [
        ("x", c.c_int), ("y", c.c_int), ("width", c.c_int), ("height", c.c_int), ("border_width", c.c_int),
        ("depth", c.c_int), ("visual", c.c_void_p), ("root", c.c_ulong), ("klass", c.c_int),
        ("bit_gravity", c.c_int), ("win_gravity", c.c_int), ("backing_store", c.c_int),
        ("backing_planes", c.c_ulong), ("backing_pixel", c.c_ulong), ("save_under", c.c_int),
        ("colormap", c.c_ulong), ("map_installed", c.c_int), ("map_state", c.c_int),
        ("all_event_masks", c.c_long), ("your_event_mask", c.c_long), ("do_not_propagate_mask", c.c_long),
        ("override_redirect", c.c_int), ("screen", c.c_void_p),
    ]


class XButtonEvent(c.Structure):
    """Button and motion events share this prefix (the root coordinates are what is read)."""

    _fields_ = [
        ("type", c.c_int), ("serial", c.c_ulong), ("send_event", c.c_int), ("display", c.c_void_p),
        ("window", c.c_ulong), ("root", c.c_ulong), ("subwindow", c.c_ulong), ("time", c.c_ulong),
        ("x", c.c_int), ("y", c.c_int), ("x_root", c.c_int), ("y_root", c.c_int), ("state", c.c_uint),
        ("button", c.c_uint), ("same_screen", c.c_int),
    ]


class XPropertyEvent(c.Structure):
    _fields_ = [
        ("type", c.c_int), ("serial", c.c_ulong), ("send_event", c.c_int), ("display", c.c_void_p),
        ("window", c.c_ulong), ("atom", c.c_ulong), ("time", c.c_ulong), ("state", c.c_int),
    ]


class XEvent(c.Union):
    _fields_ = [("type", c.c_int), ("button", XButtonEvent), ("property", XPropertyEvent), ("pad", c.c_long * 24)]


class XImage(c.Structure):
    """Only the fields read here; the rest is X's own."""

    _fields_ = [
        ("width", c.c_int), ("height", c.c_int), ("xoffset", c.c_int), ("format", c.c_int), ("data", c.c_void_p),
    ]


class XRRMonitorInfo(c.Structure):
    _fields_ = [
        ("name", c.c_ulong), ("primary", c.c_int), ("automatic", c.c_int), ("noutput", c.c_int),
        ("x", c.c_int), ("y", c.c_int), ("width", c.c_int), ("height", c.c_int),
        ("mwidth", c.c_int), ("mheight", c.c_int), ("outputs", c.c_void_p),
    ]


class XScreenSaverInfo(c.Structure):
    _fields_ = [
        ("window", c.c_ulong), ("state", c.c_int), ("kind", c.c_int), ("til_or_since", c.c_ulong),
        ("idle", c.c_ulong), ("eventMask", c.c_ulong),
    ]


def _lib(name: str, fallback: str) -> Any:
    found = ctypes.util.find_library(name) or fallback
    return c.CDLL(found)


def _sig(fn: Any, restype: Any, *argtypes: Any) -> Any:
    fn.restype = restype
    fn.argtypes = list(argtypes)
    return fn


class XErrorEvent(c.Structure):
    _fields_ = [("type", c.c_int), ("display", c.c_void_p), ("resourceid", c.c_ulong), ("serial", c.c_ulong),
                ("error_code", c.c_ubyte), ("request_code", c.c_ubyte), ("minor_code", c.c_ubyte)]


# Xlib's default handler calls exit(), so one window closing between a scan's list and its
# query would end the whole process. The handler only records; the failing call returns an
# error status that its caller already treats as "gone".
RECENT_ERRORS: list[tuple[int, int, int]] = []
_ERROR_HANDLER_TYPE = c.CFUNCTYPE(c.c_int, c.c_void_p, c.POINTER(XErrorEvent))


def _on_x_error(_dpy: Any, event: Any) -> int:
    e = event.contents
    RECENT_ERRORS.append((int(e.error_code), int(e.request_code), int(e.resourceid)))
    del RECENT_ERRORS[:-32]
    return 0


_ERROR_HANDLER = _ERROR_HANDLER_TYPE(_on_x_error)  # kept alive for the life of the process


def shape_key(alpha: bytes, width: int, height: int) -> bytes:
    """A cut-shape cache key that cannot collide in practice (a 32-bit crc could)."""
    return hashlib.blake2b(alpha, digest_size=16, salt=width.to_bytes(4, "little") + height.to_bytes(4, "little")).digest()


def libraries_present() -> bool:
    """True when libX11 can be loaded (the rest are optional)."""
    return bool(ctypes.util.find_library("X11"))


class XConn:
    """One display connection: a window of our own, the root's EWMH properties, and the
    pointer. Made by `XConn.open`; raises OSError when there is no display."""

    def __init__(self, x11: Any, display: Any, ext: dict[str, Any]) -> None:
        self.x = x11
        self.dpy = display
        self.ext = ext  # optional libraries: shape, rr, ss
        self.lock = threading.RLock()
        self.screen = x11.XDefaultScreen(display)
        self.root = int(x11.XRootWindow(display, self.screen))
        self._atoms: dict[str, int] = {}
        self._names: dict[int, str] = {}
        self._vinfo: XVisualInfo | None = None
        self._cmap = 0
        self._gc: dict[int, Any] = {}
        self._rr_event_base: int | None = None
        self._shape_cache: dict[bytes, int] = {}
        self._last: dict[int, tuple[bytes, int, int]] = {}
        self.compositor = False

    @property
    def errors(self) -> list[tuple[int, int, int]]:
        """Recent X errors as (error code, request code, resource id)."""
        return RECENT_ERRORS

    # --- opening ---------------------------------------------------------------------

    @classmethod
    def open(cls, name: str | None = None) -> "XConn":
        if not libraries_present():
            raise OSError("libX11 is not installed")
        x = _lib("X11", "libX11.so.6")
        try:
            x.XInitThreads()
        except Exception:  # noqa: BLE001 - an old libX11: the lock alone is what is left
            logger.debug("xlib: XInitThreads missing", exc_info=True)
        _sig(x.XSetErrorHandler, c.c_void_p, _ERROR_HANDLER_TYPE)
        x.XSetErrorHandler(_ERROR_HANDLER)
        _sig(x.XOpenDisplay, c.c_void_p, c.c_char_p)
        dpy = x.XOpenDisplay(name.encode() if name else None)
        if not dpy:
            raise OSError(f"cannot open the X display {name or os.environ.get('DISPLAY', '(DISPLAY is not set)')}")
        cls._signatures(x)
        ext: dict[str, Any] = {}
        for key, lib, fallback in (("shape", "Xext", "libXext.so.6"), ("rr", "Xrandr", "libXrandr.so.2"), ("ss", "Xss", "libXss.so.1")):
            try:
                ext[key] = _lib(lib, fallback)
            except OSError:
                logger.info("xlib: lib%s is not installed; what needs it is skipped", lib)
        conn = cls(x, dpy, ext)
        conn._sign_extensions()
        conn._select_root()
        return conn

    @staticmethod
    def _signatures(x: Any) -> None:
        v, u, lng, i, p = c.c_void_p, c.c_ulong, c.c_long, c.c_int, c.c_char_p
        _sig(x.XDefaultScreen, i, v)
        _sig(x.XRootWindow, u, v, i)
        _sig(x.XInternAtom, u, v, p, i)
        _sig(x.XGetAtomName, v, v, u)
        _sig(x.XFree, i, v)
        _sig(x.XFlush, i, v)
        _sig(x.XSync, i, v, i)
        _sig(x.XConnectionNumber, i, v)
        _sig(x.XPending, i, v)
        _sig(x.XNextEvent, i, v, c.POINTER(XEvent))
        _sig(x.XCloseDisplay, i, v)
        _sig(x.XMatchVisualInfo, i, v, i, i, i, c.POINTER(XVisualInfo))
        _sig(x.XDefaultVisual, v, v, i)
        _sig(x.XDefaultDepth, i, v, i)
        _sig(x.XCreateColormap, u, v, u, v, i)
        _sig(x.XCreateWindow, u, v, u, i, i, c.c_uint, c.c_uint, c.c_uint, i, c.c_uint, v, u, c.POINTER(XSetWindowAttributes))
        _sig(x.XDestroyWindow, i, v, u)
        _sig(x.XMapRaised, i, v, u)
        _sig(x.XRaiseWindow, i, v, u)
        _sig(x.XUnmapWindow, i, v, u)
        _sig(x.XMoveWindow, i, v, u, i, i)
        _sig(x.XMoveResizeWindow, i, v, u, i, i, c.c_uint, c.c_uint)
        _sig(x.XSelectInput, i, v, u, lng)
        _sig(x.XCreateGC, v, v, u, u, v)
        _sig(x.XFreeGC, i, v, v)
        _sig(x.XCreateImage, v, v, v, c.c_uint, i, i, v, c.c_uint, c.c_uint, i, i)
        _sig(x.XPutImage, i, v, u, v, v, i, i, i, i, c.c_uint, c.c_uint)
        _sig(x.XGrabPointer, i, v, u, i, c.c_uint, i, i, u, u, u)
        _sig(x.XUngrabPointer, i, v, u)
        _sig(x.XQueryPointer, i, v, u, c.POINTER(u), c.POINTER(u), c.POINTER(i), c.POINTER(i), c.POINTER(i), c.POINTER(i), c.POINTER(c.c_uint))
        _sig(x.XGetWindowAttributes, i, v, u, c.POINTER(XWindowAttributes))
        _sig(x.XTranslateCoordinates, i, v, u, u, i, i, c.POINTER(i), c.POINTER(i), c.POINTER(u))
        _sig(x.XGetWindowProperty, i, v, u, u, lng, lng, i, u, c.POINTER(u), c.POINTER(i), c.POINTER(u), c.POINTER(u), c.POINTER(v))
        _sig(x.XChangeProperty, i, v, u, u, u, i, i, v, i)
        _sig(x.XCreateBitmapFromData, u, v, u, v, c.c_uint, c.c_uint)
        _sig(x.XFreePixmap, i, v, u)
        _sig(x.XGetSelectionOwner, u, v, u)
        _sig(x.XStoreName, i, v, u, p)
        _sig(x.XSetClassHint, i, v, u, v)

    def _sign_extensions(self) -> None:
        v, u, i = c.c_void_p, c.c_ulong, c.c_int
        shape, rr, ss = self.ext.get("shape"), self.ext.get("rr"), self.ext.get("ss")
        if shape is not None:
            _sig(shape.XShapeQueryExtension, i, v, c.POINTER(i), c.POINTER(i))
            _sig(shape.XShapeCombineMask, None, v, u, i, i, i, u, i)
            base, err = i(), i()
            if not shape.XShapeQueryExtension(self.dpy, c.byref(base), c.byref(err)):
                self.ext.pop("shape")
        if rr is not None:
            _sig(rr.XRRGetMonitors, c.POINTER(XRRMonitorInfo), v, u, i, c.POINTER(i))
            _sig(rr.XRRFreeMonitors, None, c.POINTER(XRRMonitorInfo))
            _sig(rr.XRRQueryExtension, i, v, c.POINTER(i), c.POINTER(i))
            _sig(rr.XRRSelectInput, None, v, u, i)
        if ss is not None:
            _sig(ss.XScreenSaverAllocInfo, c.POINTER(XScreenSaverInfo))
            _sig(ss.XScreenSaverQueryInfo, i, v, u, c.POINTER(XScreenSaverInfo))

    def _select_root(self) -> None:
        """Hear about the work area, the desktop, the window stack and the screen layout."""
        with self.lock:
            self.x.XSelectInput(self.dpy, self.root, STRUCTURE_NOTIFY_MASK | PROPERTY_CHANGE_MASK)
            rr = self.ext.get("rr")
            if rr is not None:
                base, err = c.c_int(), c.c_int()
                if rr.XRRQueryExtension(self.dpy, c.byref(base), c.byref(err)):
                    self._rr_event_base = base.value
                    rr.XRRSelectInput(self.dpy, self.root, 1)  # RRScreenChangeNotifyMask
            self.compositor = bool(self.x.XGetSelectionOwner(self.dpy, self.atom(f"_NET_WM_CM_S{self.screen}")))

    def close(self) -> None:
        with self.lock:
            if self.dpy:
                try:
                    self.x.XCloseDisplay(self.dpy)
                finally:
                    self.dpy = None

    def fileno(self) -> int:
        return int(self.x.XConnectionNumber(self.dpy))

    # --- atoms and properties --------------------------------------------------------

    def atom(self, name: str) -> int:
        if name not in self._atoms:
            self._atoms[name] = int(self.x.XInternAtom(self.dpy, name.encode(), 0))
        return self._atoms[name]

    def atom_name(self, atom: int) -> str:
        if atom not in self._names:
            raw = self.x.XGetAtomName(self.dpy, atom)
            if not raw:
                return ""
            try:
                self._names[atom] = c.string_at(raw).decode("latin-1")
            finally:
                self.x.XFree(raw)
        return self._names[atom]

    def prop(self, win: int, name: str, max_items: int = 4096) -> "list[int] | list[str] | str | None":
        """A property: CARDINAL and WINDOW items as ints, an ATOM list as names, a text
        property as str; None when the window has none (or is gone)."""
        with self.lock:
            kind, fmt, n, after = c.c_ulong(), c.c_int(), c.c_ulong(), c.c_ulong()
            data = c.c_void_p()
            rc = self.x.XGetWindowProperty(
                self.dpy, win, self.atom(name), 0, max_items, 0, 0, c.byref(kind), c.byref(fmt), c.byref(n), c.byref(after), c.byref(data),
            )
            if rc != 0 or not data.value:
                return None
            try:
                count = int(n.value)
                if count == 0:
                    return None
                if fmt.value == 8:
                    text = c.string_at(data.value, count)
                    return text.rstrip(b"\0").decode("utf-8", "replace")
                if fmt.value == 32:
                    items = [int(v) & 0xFFFFFFFF for v in (c.c_ulong * count).from_address(data.value)]
                    if kind.value == XA_ATOM:
                        return [self.atom_name(v) for v in items]
                    return items
                return None
            finally:
                self.x.XFree(data)

    def set_prop(self, win: int, name: str, kind: str, values: "list[int] | str") -> None:
        with self.lock:
            if isinstance(values, str):
                raw = values.encode()
                buf = c.create_string_buffer(raw)
                self.x.XChangeProperty(self.dpy, win, self.atom(name), self.atom(kind), 8, PROP_MODE_REPLACE, buf, len(raw))
                return
            buf = (c.c_ulong * len(values))(*[self.atom(v) if isinstance(v, str) else v for v in values])
            self.x.XChangeProperty(self.dpy, win, self.atom(name), self.atom(kind), 32, PROP_MODE_REPLACE, buf, len(values))

    def geometry(self, win: int) -> tuple[int, int, int, int] | None:
        """A window's client area (x, y, width, height) in root coordinates, or None."""
        with self.lock:
            attrs = XWindowAttributes()
            if not self.x.XGetWindowAttributes(self.dpy, win, c.byref(attrs)):
                return None
            if attrs.map_state != 2:  # IsViewable
                return None
            ox, oy, child = c.c_int(), c.c_int(), c.c_ulong()
            self.x.XTranslateCoordinates(self.dpy, win, self.root, 0, 0, c.byref(ox), c.byref(oy), c.byref(child))
            return ox.value, oy.value, attrs.width, attrs.height

    def pointer(self) -> tuple[int, int]:
        with self.lock:
            root, child = c.c_ulong(), c.c_ulong()
            rx, ry, wx, wy, mask = c.c_int(), c.c_int(), c.c_int(), c.c_int(), c.c_uint()
            self.x.XQueryPointer(self.dpy, self.root, c.byref(root), c.byref(child), c.byref(rx), c.byref(ry), c.byref(wx), c.byref(wy), c.byref(mask))
            return rx.value, ry.value

    def screen_size(self) -> tuple[int, int]:
        with self.lock:
            attrs = XWindowAttributes()
            self.x.XGetWindowAttributes(self.dpy, self.root, c.byref(attrs))
            return attrs.width, attrs.height

    def rr_monitors(self) -> list[tuple[int, int, int, int]]:
        """Each monitor's (x, y, width, height); the whole screen when RandR cannot say."""
        rr = self.ext.get("rr")
        if rr is not None:
            with self.lock:
                count = c.c_int()
                found = rr.XRRGetMonitors(self.dpy, self.root, 1, c.byref(count))
                if found and count.value > 0:
                    try:
                        rows = [(m.x, m.y, m.width, m.height, m.primary) for m in (found[i] for i in range(count.value))]
                    finally:
                        rr.XRRFreeMonitors(found)
                    rows.sort(key=lambda r: not r[4])  # the primary first
                    return [r[:4] for r in rows]
        w, h = self.screen_size()
        return [(0, 0, w, h)]

    def resource_dpi(self) -> float | None:
        """`Xft.dpi` from the root's RESOURCE_MANAGER, which desktops set for scaling."""
        text = self.prop(self.root, "RESOURCE_MANAGER", 65536)
        if not isinstance(text, str):
            return None
        for line in text.splitlines():
            if line.startswith("Xft.dpi:"):
                try:
                    return float(line.split(":", 1)[1].strip())
                except ValueError:
                    return None
        return None

    def idle_ms(self) -> int | None:
        """Milliseconds since the last key or pointer input (the screensaver extension)."""
        ss = self.ext.get("ss")
        if ss is None:
            return None
        with self.lock:
            info = ss.XScreenSaverAllocInfo()
            if not info:
                return None
            try:
                if not ss.XScreenSaverQueryInfo(self.dpy, self.root, info):
                    return None
                return int(info.contents.idle)
            finally:
                self.x.XFree(info)

    # --- our window ------------------------------------------------------------------

    def create_window(self, title: str) -> int:
        """An override-redirect window on a 32-bit ARGB visual (plain depth when the screen has
        none): no frame, no taskbar entry, no focus, placed exactly where it is told."""
        with self.lock:
            x, dpy = self.x, self.dpy
            info = XVisualInfo()
            visual, depth, cmap = x.XDefaultVisual(dpy, self.screen), x.XDefaultDepth(dpy, self.screen), 0
            if x.XMatchVisualInfo(dpy, self.screen, 32, TRUE_COLOR, c.byref(info)):
                visual, depth = info.visual, 32
                cmap = int(x.XCreateColormap(dpy, self.root, visual, ALLOC_NONE))
                self._vinfo = info
            self._cmap = cmap
            attrs = XSetWindowAttributes()
            attrs.background_pixmap = 0
            attrs.border_pixel = 0
            attrs.override_redirect = 1
            attrs.colormap = cmap
            attrs.event_mask = BUTTON_PRESS_MASK | BUTTON_RELEASE_MASK | POINTER_MOTION_MASK | EXPOSURE_MASK
            mask = CW_BACK_PIXMAP | CW_BORDER_PIXEL | CW_OVERRIDE_REDIRECT | CW_EVENT_MASK | (CW_COLORMAP if cmap else 0)
            win = int(x.XCreateWindow(dpy, self.root, 0, 0, 1, 1, 0, depth, INPUT_OUTPUT, visual, mask, c.byref(attrs)))
            if not win:
                raise OSError("XCreateWindow failed")
            self.depth = depth
            x.XStoreName(dpy, win, title.encode())
            self.set_prop(win, "_NET_WM_NAME", "UTF8_STRING", title)
            self.set_prop(win, "_NET_WM_PID", "CARDINAL", [os.getpid()])
            self.set_prop(win, "_NET_WM_WINDOW_TYPE", "ATOM", ["_NET_WM_WINDOW_TYPE_UTILITY"])
            self.set_prop(win, "_NET_WM_STATE", "ATOM", ["_NET_WM_STATE_ABOVE", "_NET_WM_STATE_SKIP_TASKBAR", "_NET_WM_STATE_SKIP_PAGER"])
            self._gc[win] = x.XCreateGC(dpy, win, 0, None)
            x.XFlush(dpy)
            return win

    def present(self, win: int, bgra: bytes, width: int, height: int, x: int, y: int) -> None:
        """Size and place the window, draw the premultiplied BGRA frame, and cut the shape to
        the figure so a click on clear pixels reaches what is under it."""
        with self.lock:
            xl, dpy = self.x, self.dpy
            xl.XMoveResizeWindow(dpy, win, x, y, width, height)
            buf = c.create_string_buffer(bgra, len(bgra))
            image = xl.XCreateImage(dpy, self._vinfo.visual if self._vinfo else xl.XDefaultVisual(dpy, self.screen), self.depth, Z_PIXMAP, 0, buf, width, height, 32, width * 4)
            if not image:
                raise OSError("XCreateImage failed")
            try:
                xl.XPutImage(dpy, win, self._gc[win], image, 0, 0, 0, 0, width, height)
            finally:
                c.cast(image, c.POINTER(XImage)).contents.data = None  # the buffer is ours, not X's
                xl.XFree(image)
            self._last[win] = (bgra, width, height)
            self._cut_shape(win, bgra, width, height)
            xl.XFlush(dpy)

    def redraw(self, win: int) -> None:
        """Draw the last frame again (an Expose, when no compositor keeps the window's pixels)."""
        last = self._last.get(win)
        if last is None:
            return
        with self.lock:
            bgra, width, height = last
            geo = self.window_xy(win)
            self.present(win, bgra, width, height, *geo)

    def window_xy(self, win: int) -> tuple[int, int]:
        with self.lock:
            attrs = XWindowAttributes()
            self.x.XGetWindowAttributes(self.dpy, win, c.byref(attrs))
            return attrs.x, attrs.y

    def _cut_shape(self, win: int, bgra: bytes, width: int, height: int) -> None:
        shape = self.ext.get("shape")
        if shape is None:
            return
        alpha = bgra[3::4]
        key = shape_key(alpha, width, height)
        pix = self._shape_cache.get(key)
        if pix is None:
            bits = alpha_bitmap(alpha, width, height)
            if bits is None:
                return
            buf = c.create_string_buffer(bits, len(bits))
            pix = int(self.x.XCreateBitmapFromData(self.dpy, win, buf, width, height))
            if len(self._shape_cache) >= 48:
                oldest = next(iter(self._shape_cache))
                self.x.XFreePixmap(self.dpy, self._shape_cache.pop(oldest))
            self._shape_cache[key] = pix
        shape.XShapeCombineMask(self.dpy, win, SHAPE_INPUT, 0, 0, pix, SHAPE_SET)
        if not self.compositor:  # nothing blends the clear pixels: cut the picture itself
            shape.XShapeCombineMask(self.dpy, win, SHAPE_BOUNDING, 0, 0, pix, SHAPE_SET)

    def move(self, win: int, x: int, y: int) -> None:
        with self.lock:
            self.x.XMoveWindow(self.dpy, win, x, y)
            self.x.XFlush(self.dpy)

    def map(self, win: int) -> None:
        with self.lock:
            self.x.XMapRaised(self.dpy, win)
            self.x.XFlush(self.dpy)

    def unmap(self, win: int) -> None:
        with self.lock:
            self.x.XUnmapWindow(self.dpy, win)
            self.x.XFlush(self.dpy)

    def raise_window(self, win: int) -> None:
        with self.lock:
            self.x.XRaiseWindow(self.dpy, win)
            self.x.XFlush(self.dpy)

    def destroy(self, win: int) -> None:
        with self.lock:
            for pix in self._shape_cache.values():
                self.x.XFreePixmap(self.dpy, pix)
            self._shape_cache.clear()
            gc = self._gc.pop(win, None)
            if gc:
                self.x.XFreeGC(self.dpy, gc)
            self.x.XDestroyWindow(self.dpy, win)
            self.x.XFlush(self.dpy)

    def grab_pointer(self, win: int) -> None:
        with self.lock:
            self.x.XGrabPointer(
                self.dpy, win, 0, BUTTON_PRESS_MASK | BUTTON_RELEASE_MASK | POINTER_MOTION_MASK,
                GRAB_MODE_ASYNC, GRAB_MODE_ASYNC, 0, 0, CURRENT_TIME,
            )

    def ungrab_pointer(self) -> None:
        with self.lock:
            self.x.XUngrabPointer(self.dpy, CURRENT_TIME)
            self.x.XFlush(self.dpy)

    # --- events ----------------------------------------------------------------------

    def events(self) -> list[tuple[str, int, int]]:
        """Everything waiting, as (kind, root x, root y): "down", "move" (only the last of a
        run), "up", "right", "expose", "display" (layout or work area changed) and "stack"
        (the window stack changed)."""
        out: list[tuple[str, int, int]] = []
        with self.lock:
            ev = XEvent()
            while self.dpy and self.x.XPending(self.dpy):
                self.x.XNextEvent(self.dpy, c.byref(ev))
                kind = ev.type
                if kind == BUTTON_PRESS and ev.button.button == 1:
                    out.append(("down", ev.button.x_root, ev.button.y_root))
                elif kind == BUTTON_RELEASE:
                    out.append(("up" if ev.button.button == 1 else "right" if ev.button.button == 3 else "other", ev.button.x_root, ev.button.y_root))
                elif kind == MOTION_NOTIFY:
                    if out and out[-1][0] == "move":
                        out.pop()
                    out.append(("move", ev.button.x_root, ev.button.y_root))
                elif kind == EXPOSE:
                    out.append(("expose", 0, 0))
                elif kind == CONFIGURE_NOTIFY:
                    out.append(("display", 0, 0))
                elif kind == PROPERTY_NOTIFY:
                    name = self.atom_name(ev.property.atom)
                    if name in ("_NET_WORKAREA", "_NET_CURRENT_DESKTOP", "_NET_DESKTOP_GEOMETRY", "RESOURCE_MANAGER"):
                        out.append(("display", 0, 0))
                    elif name == "_NET_CLIENT_LIST_STACKING":
                        out.append(("stack", 0, 0))
                elif self._rr_event_base is not None and kind == self._rr_event_base:
                    out.append(("display", 0, 0))
        return [e for e in out if e[0] != "other"]


def alpha_bitmap(alpha: bytes, width: int, height: int) -> bytes | None:
    """The alpha plane as an X bitmap (one bit a pixel, least significant bit first, rows
    padded to bytes): set where the pixel is solid enough to take a click."""
    try:
        from PIL import Image
    except ImportError:
        return None
    im = Image.frombytes("L", (width, height), alpha).point(lambda v: 255 if v >= ALPHA_FLOOR else 0).convert("1")
    return im.tobytes("raw", "1;R")
