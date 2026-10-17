"""How much memory this computer has, for the Models screen's fit badges.

Standard library only: the app does not install psutil for one number. The
answer is the machine's total physical RAM; what is free right now is read
beside it (`free_memory_gb`) and moves a verdict one step at most, so a badge
never flickers between Fits and Too big as other programs come and go.
Graphics cards are read where the platform says so without a package
(`nvidia-smi`, the AMD driver's sysfs files, Apple silicon's shared memory),
and the person can correct all of it (INBOX 904 B67): `profile` lays the
correction over what was detected.

Linux and macOS answer through `os.sysconf`; Windows through
`GlobalMemoryStatusEx`. `TESSELLATE_RAM_GB` overrides it, for a container whose
limit is lower than the host's and for tests. None means unknown, and the page
then says so instead of guessing.
"""

from __future__ import annotations

import ctypes
import glob
import os
import platform
import subprocess
import sys
import time

from tessellate.core.subproc import NO_WINDOW


def total_memory_bytes() -> int | None:
    override = os.getenv("TESSELLATE_RAM_GB")
    if override:
        try:
            value = float(override)
            if value > 0:
                return int(value * 1024**3)
        except ValueError:
            # Not a number: ignore the override and measure instead.
            pass
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        size = os.sysconf("SC_PAGE_SIZE")
        if pages > 0 and size > 0:
            return int(pages) * int(size)
    except (AttributeError, ValueError, OSError):
        # No sysconf on this platform (Windows): the branch below asks it.
        pass
    if sys.platform == "win32":
        return _windows_total()
    return None


def _windows_total() -> int | None:
    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    try:
        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(MemoryStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined]
            return int(status.ullTotalPhys)
    except (AttributeError, OSError):
        # Not Windows, or the call is unavailable: memory is unknown.
        pass
    return None


def total_memory_gb() -> float | None:
    total = total_memory_bytes()
    return round(total / 1024**3, 1) if total else None


# --- free memory now, graphics cards, and the person's correction (B67) -----------


def parse_meminfo_available(text: str) -> float | None:
    """Bytes of ``MemAvailable`` from /proc/meminfo text; None when absent."""
    for line in text.splitlines():
        if line.startswith("MemAvailable:"):
            try:
                return float(line.split()[1]) * 1024
            except (IndexError, ValueError):
                return None
    return None


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _windows_available() -> float | None:
    try:
        status = _MemoryStatus()
        status.dwLength = ctypes.sizeof(_MemoryStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined]
            return float(status.ullAvailPhys)
    except (AttributeError, OSError):
        # Not Windows, or the call is unavailable: free memory is unknown.
        pass
    return None


def free_memory_gb() -> float | None:
    """Memory that programs could use right now, in gigabytes; None if unknown."""
    available: float | None = None
    try:
        with open("/proc/meminfo", encoding="utf-8") as handle:
            available = parse_meminfo_available(handle.read())
    except OSError:
        # No /proc (macOS, Windows): the platform's own call below, if any.
        available = None
    if available is None and sys.platform == "win32":
        available = _windows_available()
    return round(available / 1024**3, 1) if available else None


def parse_nvidia_smi(text: str) -> list[dict]:
    """Cards from ``nvidia-smi --query-gpu=name,memory.total ... nounits`` rows."""
    cards = []
    for line in text.splitlines():
        name, _, memory = line.rpartition(",")
        try:
            vram = float(memory) / 1024
        except ValueError:
            continue
        if name.strip() and vram > 0:
            cards.append({"name": name.strip(), "vram_gb": round(vram, 1), "shared": False})
    return cards


def _amd_cards() -> list[dict]:
    cards = []
    for path in glob.glob("/sys/class/drm/card[0-9]*/device/mem_info_vram_total"):
        try:
            with open(path, encoding="utf-8") as handle:
                vram = int(handle.read().strip()) / 1024**3
        except (OSError, ValueError):
            continue
        if vram > 0:
            cards.append({"name": "AMD graphics", "vram_gb": round(vram, 1), "shared": False})
    return cards


_gpu_cache: list = []  # [(taken_at, cards)] or empty
_GPU_CACHE_SECONDS = 300


def detect_gpus() -> list[dict]:
    """Graphics cards this computer says it has, with their own video memory.

    ``shared`` marks Apple silicon, whose graphics use system memory (no
    separate video memory to count). Cached for five minutes: the card does
    not change and reading it starts a program.
    """
    now = time.monotonic()
    if _gpu_cache and now - _gpu_cache[0][0] < _GPU_CACHE_SECONDS:
        return [dict(card) for card in _gpu_cache[0][1]]
    cards: list[dict] = []
    try:
        done = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3, check=False, creationflags=NO_WINDOW,
        )
        if done.returncode == 0:
            cards = parse_nvidia_smi(done.stdout)
    except (OSError, subprocess.SubprocessError):
        # No NVIDIA driver on this computer: not an error, just no card to list.
        cards = []
    if not cards and sys.platform.startswith("linux"):
        cards = _amd_cards()
    if not cards and sys.platform == "darwin" and platform.machine() == "arm64":
        cards = [{"name": "Apple silicon graphics", "vram_gb": None, "shared": True}]
    _gpu_cache[:] = [(now, cards)]
    return [dict(card) for card in cards]


def profile(override: dict | None) -> dict:
    """What the Models screen shows and the fit badges use.

    ``override`` is the person's correction: ``ram_gb`` and/or ``vram_gb``
    (0 for "no graphics card"). Detected values stay in the answer so the
    page can offer to go back to them.
    """
    override = override or {}
    detected_ram = total_memory_gb()
    gpus = detect_gpus()
    separate = [g["vram_gb"] for g in gpus if g.get("vram_gb")]
    detected_vram = max(separate) if separate else None
    ram = override.get("ram_gb") or detected_ram
    vram = override["vram_gb"] if "vram_gb" in override else detected_vram
    return {
        "ram_gb": float(ram) if ram else None,
        "detected_ram_gb": detected_ram,
        "free_ram_gb": free_memory_gb(),
        "vram_gb": float(vram) if vram else None,
        "detected_vram_gb": detected_vram,
        "gpus": gpus,
        "override": dict(override) if override else None,
    }
