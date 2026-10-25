"""Which address the server listens on: this computer only, or the network.

LAN mode (WORLD_CLASS_PLAN §12, Brief 15): "Allow other devices on this
network". Off by default, and the default is the point: the launcher binds
127.0.0.1 and nothing on the network can reach the app. On, it binds
0.0.0.0 at the next launch, so a phone or a second computer on the same
network can open the notebook with the password.

Three things live here because the launcher, the auth routes and the privacy
receipt all need the same answer:

- `bind_host(config, has_password=...)`: the address the launcher binds,
  from the one preference, and never beyond loopback without a password. The preference is written only by `POST /auth/lan-access`,
  which asks for the password to turn it on, never by `PUT /preferences`.
- `set_current` / `current`: the address the launcher *did* bind, so the
  receipt reports what happened rather than what the default is.
- `host_allowed`: the DNS-rebinding guard for LAN mode. A page on
  evil.example re-pointed at this machine's address is same-origin with
  itself, so the Origin check passes it; the Host it sends is still its own
  name. A request is allowed only when the Host names this computer: a
  loopback name, this machine's own name, or an address literal (a
  rebinding page can only ever send a *name*, never a numeric Host).
"""

from __future__ import annotations

import ipaddress
import os
import re
import socket
import struct
import sys

from tessellate.core import lantrust
from tessellate.core.config import ConfigManager

LOOPBACK = "127.0.0.1"
ALL_INTERFACES = "0.0.0.0"  # noqa: S104  # LAN mode's whole point, behind a password-gated switch
#: Every interface, IPv4 and IPv6 at once (WORLD_CLASS_PLAN §12, row 2): one
#: dual-stack socket, which the launcher makes itself (`listening_socket`)
#: because `uvicorn.run(host="::")` is IPv6 only wherever IPV6_V6ONLY
#: defaults on, Windows among them, and would stop answering on IPv4.
ALL_INTERFACES_V6 = "::"
LAN_PREF = "allow_lan"

_LOOPBACK_NAMES = frozenset({"localhost", "127.0.0.1", "::1"})

_current: str | None = None
_current_lan_port: int | None = None

#: **LAN mode is HTTPS on a port of its own** (the owner, 2026-10-05, "Yes,
#: self-signed HTTPS"; core/lancert.py). Loopback stays plain http on the
#: app's port, which the launcher, the desktop window and every saved tab
#: use; the network gets TLS on this one. Two ports, because one socket
#: cannot speak both, and a wildcard bind and a loopback bind on one port
#: conflict on Linux. `TESSELLATE_LAN_PORT` overrides it.
LAN_PORT_OFFSET = 443


def lan_port(port: int | None) -> int:
    """The HTTPS port other devices use: 8443 beside the default 8000."""
    raw = os.environ.get("TESSELLATE_LAN_PORT", "").strip()
    if raw.isdigit() and 0 < int(raw) < 65536:
        return int(raw)
    base = int(port or 8000)
    return base + LAN_PORT_OFFSET if base + LAN_PORT_OFFSET < 65536 else base - LAN_PORT_OFFSET


#: How many ports, from the usual one up, the launcher tries for the LAN
#: listener before giving up and staying on this computer only.
LAN_PORT_TRIES = 10


def lan_port_candidates(port: int) -> list[int]:
    """The LAN port, then the next ones up, for when another notebook on
    this computer has it. An explicit TESSELLATE_LAN_PORT is kept exactly."""
    if os.environ.get("TESSELLATE_LAN_PORT", "").strip().isdigit():
        return [port]
    return [p for p in range(port, port + LAN_PORT_TRIES) if p < 65536]


def set_lan_port(port: int | None) -> None:
    """Called by the launcher with the port the HTTPS listener took."""
    global _current_lan_port
    _current_lan_port = port


#: **A container's bind** (Brief 40, Docker). Inside Docker the browser reaches
#: the app through the bridge, so a loopback-only bind is unreachable and the
#: LAN switch (a password-gated preference, a second HTTPS port) is the wrong
#: tool: the operator publishes the port themselves, usually on the host's
#: loopback, and puts TLS in front. `TESSELLATE_BIND` names the address; unset,
#: nothing changes. A junk value falls back to loopback rather than raising,
#: like `TESSELLATE_PORT`: refusing to start over a stray variable is worse.
BIND_ENV = "TESSELLATE_BIND"
_explicit_bind = False


def env_bind(raw: str | None = None) -> str:
    """The address `TESSELLATE_BIND` asks for, or loopback when unset or unusable."""
    if raw is None:
        raw = os.environ.get(BIND_ENV, "")
    text = str(raw).strip().strip("[]")
    if not text:
        return LOOPBACK
    if text.lower() == "localhost":
        return LOOPBACK
    try:
        return str(ipaddress.ip_address(text))
    except ValueError:
        return LOOPBACK


#: **Names a reverse proxy forwards** (OPEN ledger 318). Behind Caddy, nginx
#: or Traefik the Host is the public name (`memory.example.com`), which is not
#: this computer's, so the rebinding guard answered 421. `TESSELLATE_ALLOWED_HOSTS`
#: is a comma-separated list of those names; unset, nothing changes. Names
#: only: `*` is ignored (it would switch the guard off) and a URL is read for
#: its host.
ALLOWED_HOSTS_ENV = "TESSELLATE_ALLOWED_HOSTS"
_HOST_NAME = re.compile(r"[a-z0-9]([a-z0-9.-]*[a-z0-9])?")


def extra_allowed_hosts() -> frozenset[str]:
    """The operator's extra host names, lower-cased, or empty."""
    raw = os.environ.get(ALLOWED_HOSTS_ENV, "")
    found = set()
    for token in raw.replace(";", ",").split(","):
        text = token.strip().lower()
        if not text:
            continue
        if "://" in text:
            text = text.split("://", 1)[1]
        text = text.split("/", 1)[0]
        if text.count(":") == 1:
            text = text.rsplit(":", 1)[0]
        if _HOST_NAME.fullmatch(text):
            found.add(text)
    return frozenset(found)


def set_explicit_bind(value: bool) -> None:
    """The launcher says the operator chose a non-loopback bind."""
    global _explicit_bind
    _explicit_bind = bool(value)


def explicit_bind() -> bool:
    """True when `TESSELLATE_BIND` chose a non-loopback address. The no-password
    403 (SEC-01) is for a notebook that went on the network by a preference;
    here the operator published the port on purpose, and refusing the first
    visitor would leave a fresh container with no way to set a password."""
    return _explicit_bind


def lan_enabled(config: ConfigManager) -> bool:
    """Whether the switch is on. Only a literal True counts: the preferences
    file is one a person may edit by hand, and a stray value must not open the
    notebook to the network."""
    return config.get_preference(LAN_PREF, False) is True


def dual_stack() -> bool:
    """Can one socket here take IPv4 and IPv6 both? False on a machine with
    no IPv6 at all (this sandbox: `AF_INET6` is not even a supported family),
    and then LAN mode binds IPv4 as it always did."""
    try:
        return bool(socket.has_ipv6 and socket.has_dualstack_ipv6())
    except (AttributeError, OSError):
        return False


def bind_host(config: ConfigManager, *, has_password: bool) -> str:
    """The address to listen on. Loopback unless the switch is on *and* a
    password exists (SEC-01, audit 2026-10-05): `--reset-password` deletes the
    password and used to leave the switch on, so the next launch put a
    notebook with nothing to ask for on the network. `has_password` has no
    default so no caller can forget to say."""
    if not has_password or not lan_enabled(config):
        return LOOPBACK
    return ALL_INTERFACES_V6 if dual_stack() else ALL_INTERFACES


def listening_socket(host: str, port: int) -> socket.socket | None:
    """The socket the launcher hands uvicorn for the dual-stack bind, or None
    for every other host (uvicorn binds those itself, as before).

    `create_server(..., dualstack_ipv6=True)` clears IPV6_V6ONLY, so the one
    socket answers `[::1]`, a global IPv6 address and every IPv4 address (as
    `::ffff:a.b.c.d`). Should the dual-stack bind fail at the last moment, the
    IPv4 bind LAN mode always made is the fallback, and `set_current` is told.
    """
    if host != ALL_INTERFACES_V6:
        return None
    try:
        return socket.create_server(
            (ALL_INTERFACES_V6, port), family=socket.AF_INET6, dualstack_ipv6=True
        )
    except (OSError, ValueError):
        return None


def url_host(address: str) -> str:
    """An address as it goes in a URL: an IPv6 one in brackets."""
    return f"[{address}]" if ":" in address and not address.startswith("[") else address


def set_current(host: str) -> None:
    """Called by the launcher with the address uvicorn is about to bind."""
    global _current
    _current = host


def current() -> str:
    return _current or LOOPBACK


def is_loopback_bind(host: str | None = None) -> bool:
    return (host or current()) in _LOOPBACK_NAMES


def arrived_on_loopback(server) -> bool:  # noqa: ANN001  # an ASGI scope's `server`, or None
    """Whether a request came in on this computer's own loopback interface.

    The ASGI scope's `server` is the address the listening socket accepted
    on, which is the fact `is_loopback_bind` only remembers the launcher
    saying: a server started any other way on 0.0.0.0 never called
    `set_current`. Only a numeric address off loopback says "the network";
    a name (the test client's `testserver`) or no address at all is read as
    local, since nothing can be judged from it.
    """
    if not isinstance(server, (tuple, list)) or not server or not isinstance(server[0], str):
        return True
    text = server[0].strip().strip("[]").split("%", 1)[0]
    try:
        address = ipaddress.ip_address(text)
    except ValueError:
        return True
    #: On the dual-stack socket an IPv4 client arrives as `::ffff:127.0.0.1`,
    #: which Python does not call loopback: read the IPv4 address inside it.
    mapped = getattr(address, "ipv4_mapped", None)
    return (mapped or address).is_loopback


def arrived_on_socket(server) -> bool:  # noqa: ANN001  # an ASGI scope's `server`, or None
    """Whether the scope names a real listening address (a number), as every
    request uvicorn accepts does. The in-process test client names its
    server (`testserver`) instead, and so does nothing else."""
    if not isinstance(server, (tuple, list)) or not server or not isinstance(server[0], str):
        return False
    try:
        ipaddress.ip_address(server[0].strip().strip("[]").split("%", 1)[0])
    except ValueError:
        return False
    return True


def _own_names() -> set[str]:
    try:
        name = socket.gethostname().lower()
    except OSError:
        return set()
    short = name.split(".", 1)[0]
    return {name, short, f"{short}.local"}


#: **The friendly local name** (`TESSELLATE_LOCAL_NAME=tessellate` opens
#: `http://tessellate.localhost:PORT`). Browsers that follow RFC 6761 answer
#: every `*.localhost` with loopback themselves; one that hands the lookup to
#: the network's DNS would let a hostile resolver point `evil.localhost` at
#: this computer's LAN address and rebind. So the guard accepts the one name
#: configured, never any other `*.localhost`, and only on a request that
#: arrived on loopback (lansec-1025).
LOCAL_NAME_ENV = "TESSELLATE_LOCAL_NAME"


def local_name() -> str:
    """`<name>.localhost` for the configured name, or "" when none is set."""
    name = os.environ.get(LOCAL_NAME_ENV, "").strip().lower()
    return f"{name}.localhost" if re.fullmatch(r"[a-z0-9-]{1,63}", name) else ""


def host_allowed(host_header: str | None, *, on_loopback: bool = False) -> bool:
    """Is this Host one that names this computer? (the rebinding guard).
    `on_loopback`: the request arrived on loopback, the only place the
    friendly local name (`local_name`) is accepted."""
    if not host_header:
        return True  # HTTP/1.0 or a local tool: nothing to judge, nothing to rebind
    text = host_header.strip().lower()
    if text.startswith("["):  # [::1]:8000
        host = text[1:].split("]", 1)[0]
    else:
        host = text.rsplit(":", 1)[0] if text.count(":") == 1 else text
    if host in _LOOPBACK_NAMES:
        return True
    if host.endswith(".localhost"):
        return on_loopback and host == local_name()
    try:
        ipaddress.ip_address(host.split("%", 1)[0])
        return True
    except ValueError:
        pass
    return host in _own_names() or host in extra_allowed_hosts()


def _usable_v6(ip: ipaddress.IPv6Address) -> bool:
    """A global or unique-local IPv6 address another device can type.

    Never link-local (fe80::/10): it needs a zone id (`%eth0`) that no
    browser's address bar accepts, so listing it would be listing a URL that
    cannot be opened. Never loopback, unspecified, multicast or an IPv4
    address in IPv6 clothing (that one is already listed as IPv4).
    """
    return not (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_unspecified
        or ip.is_multicast
        or ip.ipv4_mapped is not None
        or ip.is_site_local
    )


def _proc_v6_addresses() -> list[str]:
    """Linux's own list of this machine's IPv6 addresses, read, not probed."""
    try:
        with open("/proc/net/if_inet6", encoding="ascii") as table:
            rows = table.read().split("\n")
    except OSError:
        return []
    found = []
    for row in rows:
        parts = row.split()
        if parts and len(parts[0]) == 32:
            try:
                found.append(str(ipaddress.IPv6Address(int(parts[0], 16))))
            except ValueError:
                continue
    return found


def lan_addresses(include_v6: bool | None = None) -> list[str]:
    """This machine's addresses other devices could use, best effort: IPv4
    first, then global and unique-local IPv6 when the bind can answer on
    IPv6 (`include_v6`, which defaults to `dual_stack()`).

    No connection is opened to find them (the usual trick, a UDP "connect" to
    a public address, would put a destination on the privacy receipt that
    nothing ever talked to): the addresses the host name resolves to, and on
    Linux each interface's own address by `SIOCGIFADDR` and the kernel's
    IPv6 address table.
    """
    if include_v6 is None:
        include_v6 = dual_stack()
    found: list[str] = []
    found_v6: list[str] = []

    def add(address: str) -> None:
        try:
            ip = ipaddress.ip_address(address.split("%", 1)[0])
        except ValueError:
            return
        if ip.version == 4:
            if not ip.is_loopback and not ip.is_unspecified and str(ip) not in found:
                found.append(str(ip))
        elif include_v6 and _usable_v6(ip) and str(ip) not in found_v6:
            found_v6.append(str(ip))

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            add(info[4][0])
    except OSError:
        pass  # no resolvable hostname: the interface scan below still runs
    if sys.platform.startswith("linux"):
        try:
            import fcntl

            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                for _index, name in socket.if_nameindex():
                    try:
                        packed = fcntl.ioctl(
                            probe.fileno(), 0x8915, struct.pack("256s", name.encode()[:15])  # SIOCGIFADDR
                        )
                    except OSError:
                        continue  # an interface with no IPv4 address
                    add(socket.inet_ntoa(packed[20:24]))
        except (OSError, ImportError):
            pass  # no ioctl here: the hostname addresses above are all we can offer
    if include_v6:
        try:
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET6):
                add(info[4][0])
        except (OSError, AttributeError):
            pass  # no IPv6 name for this host: the table below may still have some
        if sys.platform.startswith("linux"):
            for address in _proc_v6_addresses():
                add(address)
    return found + found_v6


FIREWALL_RULE = "Tessellate (private networks)"


def firewall_hint(port: int | None, platform: str | None = None) -> dict | None:
    """The one-line Windows Defender Firewall rule that lets other devices
    reach the HTTPS port (OPEN ledger 315 and 316). Windows asks about a new
    listener once and, on a Public profile, blocks the next request; the app
    cannot add a rule without administrator rights, so Settings shows the line
    to paste into an administrator Command Prompt. Private profile only: a
    cafe's network is never opened by it. None off Windows or with no port."""
    if (platform or sys.platform) != "win32" or not port:
        return None
    return {
        "rule": FIREWALL_RULE,
        "command": (
            f'netsh advfirewall firewall add rule name="{FIREWALL_RULE}" '
            f"dir=in action=allow protocol=TCP localport={int(port)} profile=private"
        ),
        "remove": f'netsh advfirewall firewall delete rule name="{FIREWALL_RULE}"',
    }


def _shown_addresses(config: ConfigManager, listening: bool, enabled: bool, port: int | None):
    """The network this computer is on, the addresses to show for it (the
    phone's first), and the HTTPS port they are typed with."""
    from tessellate.core import lantrust

    raw = lan_addresses() if listening or enabled else []
    https_port = _current_lan_port or (lan_port(port) if port else None)
    network = lantrust.current_network() if listening else None
    if network is None and enabled:
        network = lantrust.network_for_display()
    return network, order_addresses(raw, network), https_port


def describe(config: ConfigManager, port: int | None = None) -> dict:
    """What the receipt and Settings say about who can reach the app.

    `port` is the port the request came in on. The addresses are the HTTPS
    ones other devices type: the LAN listener's port once it is running,
    else the one it will take (`lan_port`) beside this loopback port."""
    from tessellate.core import lantrust

    host = current()
    listening = not is_loopback_bind(host)
    trust = lantrust.status()
    #: INBOX 867: the LAN port is bound only while this network is allowed
    #: (core/lantrust.py); "off" is a server started without that gate.
    held = listening and trust["reason"] != "off" and not trust["open"]
    other_devices = listening and not held
    enabled = lan_enabled(config)
    network, shown, https_port = _shown_addresses(config, listening, enabled, port)

    def url(a: str) -> str:
        return f"https://{url_host(a)}:{https_port}" if https_port else url_host(a)

    return {
        "host": host,
        "other_devices": other_devices,
        "lan_on_next_launch": enabled,
        "restart_required": enabled == is_loopback_bind(host),
        #: The phone's address first (the default route's interface), then
        #: the rest, IPv6 last; virtual adapters left out (the owner's
        #: Windows list had VirtualBox's 192.168.56.1, which no phone reaches).
        "addresses": [url(a) for a in shown],
        "primary_address": url(shown[0]) if shown else "",
        "network": trust if listening else None,
        "held": trust["reason"] if held else None,
        "firewall": firewall_hint(https_port) if enabled else None,
    }


def order_addresses(addresses: list[str], network) -> list[str]:  # noqa: ANN001  # a netid.Network or None
    """The address on the network's own interface first, virtual adapters
    out, IPv4 before IPv6. Never empties the list: the primary is kept even
    on an interface the kernel calls virtual (a container's eth0)."""
    primary = getattr(network, "address", "") or ""
    virtual = set(getattr(network, "virtual", ()) or ()) - {primary}
    kept = [a for a in addresses if a not in virtual] or list(addresses)

    def rank(a: str) -> tuple:
        return (a != primary, ":" in a)

    return sorted(kept, key=rank)


def _any_address() -> bool:
    return bool(lan_addresses(include_v6=True))


lantrust.online_probe = _any_address
