"""Which network this computer is on, read locally (INBOX 867).

The owner: "what if memory map is open to lan on a public network or wifi??
... Just make sure everything is handled for the user automatically". Other
devices are let in only on networks the person allowed (core/lantrust.py),
and that needs a name for "this network" that a café cannot share with home:
the router's hardware address plus the subnet. Every home router may be
192.168.1.1, but not with the same hardware address.

Nothing here opens a connection or asks anything off this computer: Linux
reads /proc/net/route and /proc/net/arp; macOS runs `route -n get default`,
`arp -n` and `ipconfig`; Windows asks PowerShell for the connection profile
(whose category, Public or Private, it keeps), with `route print` and
`arp -a` as the fallback. Every command has a timeout. Anything that cannot
be read gives None, "an unknown network", which asks rather than opens.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import re
import socket
import struct
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

COMMAND_SECONDS = 3.0
POWERSHELL_SECONDS = 8.0
_MAC = re.compile(r"([0-9a-fA-F]{1,2}[:-]){5}[0-9a-fA-F]{1,2}")


@dataclass(frozen=True)
class Network:
    gateway: str
    gateway_mac: str
    subnet: str = ""
    #: Windows' own judgement of the network: "public", "private" or "domain".
    category: str | None = None
    #: A name a person recognises (the Wi-Fi name on Windows), best effort.
    name: str = ""
    #: This computer's address on it: the one a phone on this network uses.
    address: str = ""
    #: Addresses of virtual adapters (VirtualBox, Hyper-V, Docker), which no
    #: phone can reach: Settings leaves them out of the list it shows.
    virtual: tuple = field(default=())

    @property
    def key(self) -> str:
        """The network's identity: router hardware address plus subnet."""
        raw = f"{self.gateway_mac}|{self.subnet or self.gateway}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @property
    def router(self) -> str:
        """The router alone (its hardware address with its address): two
        readings of one network, one without the subnet (Windows' fallback
        when PowerShell is slow), share it. `lantrust` treats them as one
        network only when one of them lacks the subnet."""
        raw = f"{self.gateway_mac}|{self.gateway}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @property
    def label(self) -> str:
        if self.name:
            return self.name
        return f"the network with router {self.gateway}"

    def public(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "gateway": self.gateway,
            "subnet": self.subnet,
            "category": self.category,
            "address": self.address,
        }


def normal_mac(text: str) -> str:
    """aa:bb:cc:dd:ee:ff, from any of the three systems' spellings, or ""."""
    match = _MAC.search(text or "")
    if not match:
        return ""
    parts = re.split(r"[:-]", match.group(0))
    mac = ":".join(p.zfill(2).lower() for p in parts)
    return "" if mac in ("00:00:00:00:00:00", "ff:ff:ff:ff:ff:ff") else mac


def _subnet(address: str, mask: str) -> str:
    try:
        return str(ipaddress.ip_network(f"{address}/{mask}", strict=False))
    except ValueError:
        return ""


def _run(argv: list[str], timeout: float = COMMAND_SECONDS) -> str:
    try:
        done = subprocess.run(  # noqa: S603  # fixed argv, no shell
            argv, capture_output=True, text=True, timeout=timeout, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return ""
    return done.stdout or ""


# --- Linux ---------------------------------------------------------------------


def _hex_ip(value: str) -> str:
    return socket.inet_ntoa(struct.pack("<I", int(value, 16)))


def _default_route(rows: list[list[str]]) -> tuple[int, str, str] | None:
    """(metric, interface, gateway) of the default route with the lowest metric."""
    best = None
    for row in rows:
        try:
            if len(row) >= 8 and row[1] == "00000000" and row[7] == "00000000" and int(row[3], 16) & 0x2:
                metric = int(row[6])
                if best is None or metric < best[0]:
                    best = (metric, row[0], _hex_ip(row[2]))
        except ValueError:
            continue
    return best


def _route_subnet(rows: list[list[str]], iface: str, gateway: str) -> str:
    """The on-link route of `iface` that holds the gateway, as a network."""
    for row in rows:
        if len(row) < 8 or row[0] != iface or row[2] != "00000000" or row[7] == "00000000":
            continue
        try:
            candidate = _subnet(_hex_ip(row[1]), _hex_ip(row[7]))
            if candidate and ipaddress.ip_address(gateway) in ipaddress.ip_network(candidate):
                return candidate
        except ValueError:
            continue
    return ""


def parse_proc_route(text: str) -> tuple[str, str, str] | None:
    """(interface, gateway, subnet) of the default route with the lowest metric."""
    rows = [line.split() for line in text.splitlines()[1:] if line.strip()]
    best = _default_route(rows)
    if best is None:
        return None
    _, iface, gateway = best
    return iface, gateway, _route_subnet(rows, iface, gateway)


def parse_proc_arp(text: str, gateway: str, iface: str = "") -> str:
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 6 and parts[0] == gateway and (not iface or parts[5] == iface):
            if parts[2] == "0x0":
                continue  # an incomplete entry: no answer from the router yet
            return normal_mac(parts[3])
    return ""


def _linux_virtual() -> tuple:
    """IPv4 addresses on interfaces the kernel calls virtual (docker0,
    vboxnet0, virbr0): /sys/devices/virtual/net lists them."""
    root = Path("/sys/devices/virtual/net")
    try:
        names = {p.name for p in root.iterdir()} - {"lo"}
    except OSError:
        return ()
    found = []
    try:
        import fcntl

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            for name in sorted(names):
                try:
                    packed = fcntl.ioctl(probe.fileno(), 0x8915, struct.pack("256s", name.encode()[:15]))
                except OSError:
                    continue
                found.append(socket.inet_ntoa(packed[20:24]))
    except (OSError, ImportError):
        return ()
    return tuple(found)


def _linux_address(iface: str) -> str:
    try:
        import fcntl

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            packed = fcntl.ioctl(probe.fileno(), 0x8915, struct.pack("256s", iface.encode()[:15]))
        return socket.inet_ntoa(packed[20:24])
    except (OSError, ImportError):
        return ""


def read_linux(proc: Path = Path("/proc/net")) -> Network | None:
    try:
        route = (proc / "route").read_text(encoding="ascii", errors="replace")
        arp = (proc / "arp").read_text(encoding="ascii", errors="replace")
    except OSError:
        return None
    found = parse_proc_route(route)
    if not found:
        return None
    iface, gateway, subnet = found
    mac = parse_proc_arp(arp, gateway, iface)
    if not mac:
        return None
    return Network(gateway, mac, subnet, address=_linux_address(iface), virtual=_linux_virtual())


def gateway_linux(proc: Path = Path("/proc/net")) -> str:
    """The default route's gateway alone, or "" (no hardware address needed)."""
    try:
        found = parse_proc_route((proc / "route").read_text(encoding="ascii", errors="replace"))
    except OSError:
        return ""
    return found[1] if found else ""


# --- macOS ---------------------------------------------------------------------


def parse_route_get(text: str) -> tuple[str, str]:
    gateway = iface = ""
    for line in text.splitlines():
        name, _, value = line.strip().partition(":")
        if name == "gateway":
            gateway = value.strip()
        elif name == "interface":
            iface = value.strip()
    return gateway, iface


def read_macos() -> Network | None:
    gateway, iface = parse_route_get(_run(["route", "-n", "get", "default"]))
    try:
        ipaddress.ip_address(gateway)
    except ValueError:
        return None
    mac = normal_mac(_run(["arp", "-n", gateway]))
    if not mac:
        return None
    address = mask = ""
    if iface:
        address = _run(["ipconfig", "getifaddr", iface]).strip()
        mask = _run(["ipconfig", "getoption", iface, "subnet_mask"]).strip()
    return Network(gateway, mac, _subnet(address, mask) if address and mask else "", address=address)


# --- Windows -------------------------------------------------------------------

#: One PowerShell call: the default route's gateway and interface, that
#: interface's address and prefix, its profile (category and name), the
#: router's hardware address, and the addresses of adapters that are not
#: hardware (VirtualBox host-only, Hyper-V, VPNs).
_PS_SCRIPT = (
    "$ErrorActionPreference='SilentlyContinue';"
    "$r=Get-NetRoute -DestinationPrefix 0.0.0.0/0|Sort-Object RouteMetric|Select-Object -First 1;"
    "$i=$r.InterfaceIndex;"
    "$a=Get-NetIPAddress -InterfaceIndex $i -AddressFamily IPv4|Select-Object -First 1;"
    "$p=Get-NetConnectionProfile -InterfaceIndex $i|Select-Object -First 1;"
    "$n=Get-NetNeighbor -IPAddress $r.NextHop|Select-Object -First 1;"
    "$v=@(Get-NetAdapter|Where-Object {-not $_.HardwareInterface}|ForEach-Object "
    "{(Get-NetIPAddress -InterfaceIndex $_.ifIndex -AddressFamily IPv4).IPAddress});"
    "@{gateway=$r.NextHop;address=$a.IPAddress;prefix=$a.PrefixLength;"
    "category=[string]$p.NetworkCategory;name=$p.Name;mac=$n.LinkLayerAddress;virtual=$v}"
    "|ConvertTo-Json -Compress"
)


def _windows_category(data: dict) -> str | None:
    category = str(data.get("category") or "").lower()
    return {"public": "public", "private": "private", "domainauthenticated": "domain"}.get(category)


def _windows_subnet(data: dict, address: str) -> str:
    prefix = data.get("prefix")
    return _subnet(address, str(prefix)) if address and prefix not in (None, "") else ""


def parse_windows_json(text: str) -> Network | None:
    try:
        data = json.loads(text.strip() or "null")
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    gateway = str(data.get("gateway") or "")
    mac = normal_mac(str(data.get("mac") or ""))
    try:
        ipaddress.ip_address(gateway)
    except ValueError:
        return None
    if not mac:
        return None
    address = str(data.get("address") or "")
    virtual = data.get("virtual") or []
    if isinstance(virtual, str):
        virtual = [virtual]
    return Network(
        gateway, mac, _windows_subnet(data, address), category=_windows_category(data),
        name=str(data.get("name") or "")[:80], address=address,
        virtual=tuple(str(v) for v in virtual if v),
    )


def parse_route_print(text: str) -> str:
    """The gateway of the lowest-metric 0.0.0.0 route in `route print`."""
    best = None
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0] == "0.0.0.0" and parts[1] == "0.0.0.0":
            try:
                ipaddress.ip_address(parts[2])
                metric = int(parts[-1])
            except ValueError:
                continue
            if best is None or metric < best[0]:
                best = (metric, parts[2])
    return best[1] if best else ""


def read_windows() -> Network | None:
    found = parse_windows_json(
        _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS_SCRIPT], POWERSHELL_SECONDS)
    )
    if found is not None:
        return found
    # No PowerShell answer: the router alone, and no category, so a network
    # Windows would call Public is never mistaken for one it calls Private.
    gateway = parse_route_print(_run(["route", "print", "-4", "0.0.0.0"]))
    if not gateway:
        return None
    mac = normal_mac(_run(["arp", "-a", gateway]))
    return Network(gateway, mac) if mac else None


def gateway() -> str:
    """The default gateway now, or "" where it cannot be told without a full read."""
    try:
        return gateway_linux() if sys.platform.startswith("linux") else ""
    except Exception:  # noqa: BLE001  # never let reading the network stop the app
        log.debug("Could not read the default gateway; the full read decides.", exc_info=True)
        return ""


def read() -> Network | None:
    """This computer's network now, or None when it cannot be told."""
    try:
        if sys.platform.startswith("linux"):
            return read_linux()
        if sys.platform == "darwin":
            return read_macos()
        if sys.platform == "win32":
            return read_windows()
    except Exception:  # noqa: BLE001  # never let reading the network stop the app: unknown asks
        log.debug("Could not read this computer's network; treating it as unknown.", exc_info=True)
        return None
    return None
