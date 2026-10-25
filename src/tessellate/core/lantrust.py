"""Who may use LAN mode, and from which networks (INBOX 867).

The owner: "what if memory map is open to lan on a public network or wifi??
Is that a security risk?? ... Just make sure everything is handled for the
user automatically with possible manual overrides". Three rules, each on by
default, each loosened only by a password-gated override in Settings, Other
devices (api/routes_auth.py):

- **Allowed networks.** Turning the switch on remembers the network it was
  turned on in (core/netid.py: the router's hardware address plus the
  subnet). On any other network the LAN port stays closed, and Settings and
  the bell say so, with "Allow on this network". A network that cannot be
  read is "unknown" and asks too. Override: "Allow on any network". Windows'
  Public category is never opened without asking, the override included.
- **New devices wait.** The first sign-in from a device over the network is
  held until this computer allows it; allowed devices are remembered by a
  random id in a cookie, kept here only as a hash, and listed with Remove.
  Override: "Ask before a new device signs in", on by default.
- **Nearby clients only** is core/lanserve.py's, with no override.
- **Untrusted networks** (INBOX 896, the owner: "if the user says they
  trust a network, they should be able to change this at any time and view
  a list of trusted and untrusted networks and be able to manage it"). A
  network the port stayed closed on is listed as untrusted, so it can be
  trusted later from the list; "Stop trusting" moves a trusted one there
  and marks it, and a marked network stays closed even with "Allow on any
  network". No network at all (Wi-Fi and mobile data gone) is its own
  closed state, never "unknown".
- **Unused for 14 days, off** (secscan-1011's decision): the last time a
  device connected is kept, and core/lanlive.py turns the switch off when
  nobody has for `UNUSED_DAYS`, leaving `switched_off` for this computer's
  notice.

Kept in `lan-trust.json` in the data folder (0600), never in preferences:
`PUT /preferences` cannot reach it, and a file that cannot be read gives the
defaults, which are the closed ones.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import threading
import time
from pathlib import Path

from tessellate.core import netid

FILE_NAME = "lan-trust.json"
DEVICE_COOKIE = "mm_device"
#: How long a held sign-in waits for an answer on this computer.
PENDING_SECONDS = 10 * 60
#: A device that keeps asking cannot fill this computer's screen.
MAX_PENDING = 8
MAX_DEVICES = 50
MAX_NETWORKS = 20
#: LAN mode switches itself off after this many days with no device.
UNUSED_DAYS = 14
#: The in-memory "a device connected" time is written at most this often.
USE_WRITE_SECONDS = 3600.0

_lock = threading.RLock()
_changed = threading.Condition(_lock)
_gate: dict = {"open": False, "reason": "off", "network": None, "checked": 0.0}
#: A holder rather than a bare module global: CodeQL read the global as unused.
_run: dict[str, dict | None] = {"allowance": None}
_pending: dict[str, dict] = {}
_version = 0
#: Event-loop waiters (`wait_version_change`), woken by `_bump` rather than
#: polling: a watch held open for 25 s used to wake 50 times to ask "yet?".
_waiters: set[tuple[asyncio.AbstractEventLoop, asyncio.Event]] = set()


def _bump() -> None:
    global _version
    _version += 1
    _changed.notify_all()
    for loop, event in list(_waiters):
        with contextlib.suppress(RuntimeError):  # that loop has closed
            loop.call_soon_threadsafe(event.set)


async def wait_version_change(since: int, timeout: float) -> bool:
    """Wait for `version()` to differ from `since`, up to `timeout` seconds.
    True when it changed. One wake per change, none while idle."""
    if _version != since:
        return True
    entry = (asyncio.get_running_loop(), asyncio.Event())
    with _lock:
        _waiters.add(entry)
    try:
        if _version == since:  # a bump between the check and the add
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(entry[1].wait(), timeout)
        return _version != since
    finally:
        with _lock:
            _waiters.discard(entry)


def version() -> int:
    return _version


# --- the file ------------------------------------------------------------------


def _path(data_dir: Path) -> Path:
    return Path(data_dir) / FILE_NAME


def load(data_dir: Path) -> dict:
    """The saved state, with the closed defaults for anything missing or odd."""
    try:
        raw = json.loads(_path(data_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    def listed(name: str) -> list:
        value = raw.get(name)
        return value if isinstance(value, list) else []

    def when(name: str) -> float:
        value = raw.get(name)
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0

    networks = [n for n in listed("networks") if isinstance(n, dict) and isinstance(n.get("key"), str)]
    devices = [d for d in listed("devices") if isinstance(d, dict) and isinstance(d.get("id"), str)]
    trusted = {n["key"] for n in networks}
    untrusted = [
        n for n in listed("untrusted")
        if isinstance(n, dict) and isinstance(n.get("key"), str) and n["key"] not in trusted
    ]
    switched_off = raw.get("switched_off")
    return {
        "networks": networks[:MAX_NETWORKS],
        "devices": devices[:MAX_DEVICES],
        # Only a literal True opens anything; only a literal False stops asking.
        "any_network": raw.get("any_network") is True,
        "ask_new_devices": raw.get("ask_new_devices") is not False,
        "untrusted": untrusted[:MAX_NETWORKS],
        "turned_on": when("turned_on"),
        "last_used": when("last_used"),
        "switched_off": switched_off if isinstance(switched_off, str) else "",
    }


def save(data_dir: Path, state: dict) -> None:
    path = _path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(f".{os.getpid()}.part")
    fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        json.dump(state, out, indent=1)
    os.replace(partial, path)
    with contextlib.suppress(OSError):
        os.chmod(path, 0o600)


def _now_text() -> str:
    return time.strftime("%Y-%m-%d %H:%M")


# --- networks ------------------------------------------------------------------


def _stopped_trusting(state: dict, network: netid.Network | None) -> bool:
    """The person said Stop trusting this network."""
    return network is not None and any(
        _same(n, network) and n.get("blocked") for n in state.get("untrusted") or ()
    )


def evaluate(
    state: dict, network: netid.Network | None, allowance: dict | None = None, *, online: bool = True
) -> tuple[bool, str]:
    """(open, reason). Reasons: allowed, any_network, allowed_this_run,
    unknown_network, new_network, public_network, untrusted_network (the
    person said Stop trusting) and no_network (no address at all)."""
    if network is None and not online:
        return False, "no_network"
    if _stopped_trusting(state, network):
        return False, "untrusted_network"
    if network is None:
        if allowance is not None:
            return True, "allowed_this_run"
        return (True, "any_network") if state["any_network"] else (False, "unknown_network")
    if any(_same(n, network) for n in state["networks"]):
        return True, "allowed"
    if network.category == "public":
        return False, "public_network"
    if allowance is not None and allowance.get("gateway") == network.gateway:
        return True, "allowed_this_run"
    if state["any_network"]:
        return True, "any_network"
    return False, "new_network"


def _same(entry: dict, network: netid.Network) -> bool:
    """A saved network and a reading are one network: the same key, or the
    same router where one of the two was read without its subnet."""
    if entry.get("key") == network.key:
        return True
    return entry.get("router") == network.router and not (entry.get("subnet") and network.subnet)


def _entry(network: netid.Network) -> dict:
    return {
        "key": network.key,
        "router": network.router,
        "label": network.label,
        "gateway": network.gateway,
        "subnet": network.subnet,
        "public": network.category == "public",
        "added": _now_text(),
    }


def _remember(state: dict, network: netid.Network) -> None:
    state["untrusted"] = [n for n in state.get("untrusted") or () if not _same(n, network)]
    known = next((n for n in state["networks"] if _same(n, network)), None)
    if known is None:
        state["networks"].append(_entry(network))
        del state["networks"][:-MAX_NETWORKS]
    elif network.subnet and not known.get("subnet"):
        #: The fuller reading replaces the bare one: its key, its subnet and
        #: the Wi-Fi name, so the list shows one row with the name.
        known.update({k: v for k, v in _entry(network).items() if k != "added"})


def _note_untrusted(state: dict, network: netid.Network) -> bool:
    """A network the port stayed closed on joins the untrusted list, so it
    can be trusted later from there. True when the list changed."""
    listed = state.setdefault("untrusted", [])
    if any(_same(n, network) for n in listed) or any(_same(n, network) for n in state["networks"]):
        return False
    listed.append({**_entry(network), "blocked": False})
    del listed[:-MAX_NETWORKS]
    return True


#: Whether any address another device could reach exists; netbind sets it when
#: it loads (it reads this module in describe, so this module cannot import it).
online_probe = None


def _online() -> bool:
    """Any address another device could reach: none means Wi-Fi and mobile
    data are both gone, which closes the port whatever the overrides say."""
    if online_probe is None:
        return True
    try:
        return bool(online_probe())
    except OSError:
        return False


_UNREAD = object()


def refresh(data_dir: Path, network=_UNREAD, *, online: bool | None = None) -> dict:  # noqa: ANN001  # a netid.Network, None, or unread
    """Read the network again and decide whether the LAN port may be open."""
    if network is _UNREAD:
        network = netid.read()
    if online is None:
        online = network is not None or _online()
    with _lock:
        state = load(data_dir)
        allowance = _run["allowance"]
        # "Allow on this network" on a network that could not be read lasts
        # this run; once the same router answers with its hardware address,
        # it is remembered as the network the person allowed.
        if allowance is not None and network is not None and allowance.get("gateway") in ("", network.gateway):
            _remember(state, network)
            save(data_dir, state)
            _run["allowance"] = None
            allowance = None
        opened, reason = evaluate(state, network, allowance, online=online)
        if reason in ("new_network", "public_network") and network is not None and _note_untrusted(state, network):
            save(data_dir, state)
        before = (_gate["open"], _gate["reason"], _gate["network"] and _gate["network"].key)
        _gate.update(open=opened, reason=reason, network=network, checked=time.time())
        if before != (opened, reason, network and network.key):
            _bump()
        return status()


def is_open() -> bool:
    return bool(_gate["open"])


def current_network() -> netid.Network | None:
    return _gate["network"]


_display: dict = {"at": 0.0, "network": None}


def network_for_display() -> netid.Network | None:
    """The network for Settings while the gate is not running (the switch on,
    the app not yet restarted): read at most once a minute."""
    if time.monotonic() - _display["at"] > 60 or _display["at"] == 0.0:
        _display.update(at=time.monotonic(), network=netid.read())
    return _display["network"]


def status() -> dict:
    network = _gate["network"]
    return {
        "open": bool(_gate["open"]),
        "reason": _gate["reason"],
        "network": network.public() if network else None,
    }


def remember_current(data_dir: Path) -> dict:
    """The switch was turned on: this network becomes an allowed one, unless
    Windows calls it Public (that asks, with "Allow on this network")."""
    network = netid.read()
    with _lock:
        if network is not None and network.category != "public":
            state = load(data_dir)
            # A network the person said Stop trusting stays that way: the
            # switch going on is not an answer to that question.
            if not any(n["key"] == network.key and n.get("blocked") for n in state["untrusted"]):
                _remember(state, network)
                save(data_dir, state)
    return refresh(data_dir, network)


def allow_current(data_dir: Path) -> dict:
    """"Allow on this network": remembered when it can be told apart, else
    allowed until the app restarts."""
    network = netid.read()
    with _lock:
        if network is None:
            _run["allowance"] = {"gateway": ""}
        else:
            state = load(data_dir)
            _remember(state, network)
            save(data_dir, state)
    return refresh(data_dir, network)


def _one_network(a: dict, b: dict) -> bool:
    """Two saved records are one network for the lists: one of them was
    read without its subnet, and they share the router (by `router`, or by
    its address for records saved before `router` existed). Two records
    that both have a subnet are one network only with the same key: the
    same address on another router is another network."""
    if a.get("subnet") and b.get("subnet"):
        return a["key"] == b["key"]
    if a.get("router") and b.get("router"):
        return a["router"] == b["router"]
    return bool(a.get("gateway")) and a.get("gateway") == b.get("gateway")


def _group_of(entries: list, key: str) -> set[str]:
    """`key` and every record on the same list that is the same network."""
    found = next((n for n in entries if n["key"] == key), None)
    if found is None:
        return set()
    return {n["key"] for n in entries if n is found or _one_network(found, n)}


def _named(label: str) -> bool:
    return bool(label) and not label.startswith("the network with router")


def _network_groups(entries: list) -> list[list[dict]]:
    """The records grouped by the network they stand for."""
    groups: list[list[dict]] = []
    for entry in entries:
        group = next((g for g in groups if all(_one_network(entry, other) for other in g)), None)
        if group is None:
            groups.append([entry])
        else:
            group.append(entry)
    return groups


def _listed_row(group: list[dict], here: str) -> dict:
    """One list row for a group of records of the same network."""
    best = max(group, key=lambda n: (_named(n.get("label", "")), bool(n.get("subnet"))))
    keys = [n["key"] for n in group]
    row = {k: best.get(k, "") for k in ("key", "label", "gateway", "subnet", "added")}
    row["label"] = next((n["label"] for n in group if _named(n.get("label", ""))), best.get("label", ""))
    row["subnet"] = next((n["subnet"] for n in group if n.get("subnet")), "")
    row["added"] = max((n.get("added") or "" for n in group), default="")
    row["keys"] = keys
    if here in keys:
        row["key"] = here
    if "blocked" in best:
        row["blocked"] = any(n.get("blocked") for n in group)
    return row


def listed(entries: list, here: str = "") -> list[dict]:
    """The rows the lists show: one per network, named by its Wi-Fi name
    when any record has one, its subnet as the line under it, the latest
    date, and `keys`, every record it stands for. The row's key is the one
    the computer is on now when it is among them, else the fullest record's."""
    return [_listed_row(group, here) for group in _network_groups(entries)]


def forget_network(data_dir: Path, key: str) -> bool:
    """Off both lists, with every record of the same network: a forgotten
    network is new again next time."""
    with _lock:
        state = load(data_dir)
        gone = _group_of(state["networks"], key) | _group_of(state["untrusted"], key)
        kept = [n for n in state["networks"] if n["key"] not in gone]
        unkept = [n for n in state["untrusted"] if n["key"] not in gone]
        if len(kept) == len(state["networks"]) and len(unkept) == len(state["untrusted"]):
            return False
        state["networks"], state["untrusted"] = kept, unkept
        save(data_dir, state)
    refresh(data_dir, _gate["network"])
    return True


def _move_to_trusted(state: dict, found: dict) -> None:
    """Move an untrusted record to the trusted list, with the records known to be the same router."""
    #: A loosening, so only records known to be the same router go
    #: with it: one saved before `router` existed stays where it is.
    moving = [
        n for n in state["untrusted"]
        if n is found or (found.get("router") and n.get("router") == found["router"] and _one_network(found, n))
    ]
    state["untrusted"] = [n for n in state["untrusted"] if not any(n is m for m in moving)]
    for moved in moving:
        entry = {k: v for k, v in moved.items() if k != "blocked"}
        entry["added"] = _now_text()
        if not any(n["key"] == entry["key"] for n in state["networks"]):
            state["networks"].append(entry)
    del state["networks"][:-MAX_NETWORKS]


def trust_network(data_dir: Path, key: str) -> bool:
    """Trust a network from the untrusted list (or the one this computer is
    on now): it moves to the trusted list. The route asks for the password."""
    current = _gate["network"]
    with _lock:
        state = load(data_dir)
        found = next((n for n in state["untrusted"] if n["key"] == key), None)
        if found is None and not (current is not None and current.key == key):
            return False
        if found is not None:
            _move_to_trusted(state, found)
        else:
            _remember(state, current)
        save(data_dir, state)
    refresh(data_dir, current)
    return True


def untrust_network(data_dir: Path, key: str) -> bool:
    """"Stop trusting": the network moves to the untrusted list, marked, so
    it stays closed even with "Allow on any network". Only ever lets fewer
    in. The port shuts at once when it is the network this computer is on."""
    current = _gate["network"]
    with _lock:
        state = load(data_dir)
        group = _group_of(state["networks"], key) or _group_of(state["untrusted"], key)
        records = [n for n in state["networks"] + state["untrusted"] if n["key"] in group]
        if not records and current is not None and current.key == key:
            records = [_entry(current)]
        if not records:
            return False
        #: Every record of the network: Stop trusting only ever lets fewer in.
        gone = {n["key"] for n in records}
        state["networks"] = [n for n in state["networks"] if n["key"] not in gone]
        state["untrusted"] = [n for n in state["untrusted"] if n["key"] not in gone]
        seen: set[str] = set()
        for record in records:
            if record["key"] not in seen:
                seen.add(record["key"])
                state["untrusted"].append({**record, "blocked": True, "added": _now_text()})
        del state["untrusted"][:-MAX_NETWORKS]
        save(data_dir, state)
    refresh(data_dir, current)
    return True


# --- use, and switching off when unused --------------------------------------------

_used = {"at": 0.0, "written": 0.0}


def note_used() -> None:
    """A device connected (core/lanserve.py's accept loop): in memory only,
    written by `persist_use` at most hourly."""
    _used["at"] = time.time()


def persist_use(data_dir: Path) -> None:
    at = _used["at"]
    if not at or at - _used["written"] < USE_WRITE_SECONDS:
        return
    with _lock:
        state = load(data_dir)
        state["last_used"] = max(state["last_used"], at)
        save(data_dir, state)
    _used["written"] = at


def mark_turned_on(data_dir: Path) -> None:
    """The switch went on: the unused clock starts now, and any notice that
    it had switched itself off is spent."""
    with _lock:
        state = load(data_dir)
        state["turned_on"] = time.time()
        state["switched_off"] = ""
        save(data_dir, state)
        _bump()


def unused_since(state: dict) -> float:
    return max(state["turned_on"], state["last_used"], _used["at"])


def mark_switched_off(data_dir: Path) -> None:
    with _lock:
        state = load(data_dir)
        state["switched_off"] = _now_text()
        save(data_dir, state)
        _bump()


def clear_switched_off(data_dir: Path) -> None:
    with _lock:
        state = load(data_dir)
        if state["switched_off"]:
            state["switched_off"] = ""
            save(data_dir, state)
            _bump()


def touch_version() -> None:
    """Something the status bar shows changed (the listener started or
    stopped): the window's held `lan-watch` answers at once."""
    with _lock:
        _bump()


def set_flag(data_dir: Path, name: str, value: bool) -> None:
    if name not in ("any_network", "ask_new_devices"):
        raise ValueError(name)
    with _lock:
        state = load(data_dir)
        state[name] = bool(value)
        save(data_dir, state)
    refresh(data_dir, _gate["network"])


# --- devices -------------------------------------------------------------------


def device_hash(raw: str | None) -> str:
    if not raw:
        return ""
    return hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:32]


def device_known(data_dir: Path, raw: str | None) -> bool:
    found = device_hash(raw)
    return bool(found) and any(d["id"] == found for d in load(data_dir)["devices"])


def plain_address(address: str) -> str:
    """An IPv4 client on a dual-stack socket arrives as ::ffff:10.1.0.15; the
    person reads, and the lists keep, 10.1.0.15."""
    return address[7:] if address[:7].lower() == "::ffff:" and "." in address else address


def touch_device(data_dir: Path, raw: str | None, address: str) -> None:
    found = device_hash(raw)
    address = plain_address(address)
    with _lock:
        state = load(data_dir)
        for device in state["devices"]:
            if device["id"] == found:
                device["last_seen"] = _now_text()
                device["address"] = address
                save(data_dir, state)
                return


def device_name(user_agent: str | None) -> str:
    """"iPhone, Safari": enough to tell which device is asking."""
    ua = user_agent or ""
    kind = "A device"
    for needle, name in (
        ("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android device"),
        ("Macintosh", "Mac"), ("Windows", "Windows computer"), ("CrOS", "Chromebook"),
        ("Linux", "Linux computer"),
    ):
        if needle in ua:
            kind = name
            break
    browser = ""
    for needle, name in (
        ("Edg/", "Edge"), ("Firefox/", "Firefox"), ("FxiOS", "Firefox"), ("CriOS", "Chrome"),
        ("Chrome/", "Chrome"), ("Safari/", "Safari"),
    ):
        if needle in ua:
            browser = name
            break
    return f"{kind}, {browser}" if browser else kind


def _expire(now: float) -> None:
    for key in [k for k, p in _pending.items() if now - p["at"] > PENDING_SECONDS]:
        del _pending[key]


def hold(raw: str, name: str, address: str) -> dict:
    """Hold a sign-in from a new device until this computer answers."""
    found = device_hash(raw)
    address = plain_address(address)
    now = time.time()
    with _lock:
        _expire(now)
        held = _pending.get(found)
        #: An answer already given (Deny while the phone was not waiting) is
        #: kept for the device's next try, which `settle`s it.
        if held is None:
            if len(_pending) >= MAX_PENDING:
                oldest = min(_pending, key=lambda k: _pending[k]["at"])
                del _pending[oldest]
            held = {"id": found, "name": name, "address": address, "at": now, "decision": None}
            _pending[found] = held
            _bump()
        return dict(held)


def pending() -> list[dict]:
    with _lock:
        _expire(time.time())
        return [
            {"id": p["id"], "name": p["name"], "address": p["address"], "at": p["at"]}
            for p in _pending.values()
            if p["decision"] is None
        ]


def decide(data_dir: Path, device_id: str, allow: bool) -> bool:
    """Allow or deny a held device. False when there is no such request."""
    with _lock:
        held = _pending.get(device_id)
        if held is None or held["decision"] is not None:
            return False
        held["decision"] = "allowed" if allow else "denied"
        if allow:
            state = load(data_dir)
            if not any(d["id"] == device_id for d in state["devices"]):
                state["devices"].append(
                    {"id": device_id, "name": held["name"], "address": held["address"],
                     "added": _now_text(), "last_seen": _now_text()}
                )
                del state["devices"][:-MAX_DEVICES]
                save(data_dir, state)
        _bump()
        return True


def wait_decision(raw: str, timeout: float) -> str | None:
    """Block until this device's held sign-in is answered: "allowed",
    "denied", or None when the wait ran out."""
    found = device_hash(raw)
    deadline = time.monotonic() + timeout
    with _changed:
        while True:
            held = _pending.get(found)
            if held is None:
                return None
            if held["decision"] is not None:
                return held["decision"]
            left = deadline - time.monotonic()
            if left <= 0:
                return None
            _changed.wait(left)


def settle(raw: str) -> None:
    """The held sign-in got its answer to the device: forget the request."""
    with _lock:
        if _pending.pop(device_hash(raw), None) is not None:
            _bump()


def devices(data_dir: Path) -> list[dict]:
    return [
        {k: d.get(k, "") for k in ("id", "name", "address", "added", "last_seen")}
        for d in load(data_dir)["devices"]
    ]


def forget_device(data_dir: Path, device_id: str) -> bool:
    with _lock:
        state = load(data_dir)
        kept = [d for d in state["devices"] if d["id"] != device_id]
        if len(kept) == len(state["devices"]):
            return False
        state["devices"] = kept
        save(data_dir, state)
        _pending.pop(device_id, None)
        _bump()
    return True


def reset_for_tests() -> None:
    with _lock:
        _gate.update(open=False, reason="off", network=None, checked=0.0)
        _run["allowance"] = None
        _pending.clear()
        _used.update(at=0.0, written=0.0)
        _bump()
