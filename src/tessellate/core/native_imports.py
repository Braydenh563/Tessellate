"""What a native library asks the system for, read without running it (INBOX 699).

The owner, 2026-10-06, about the needle package's row: "is it possible to
remove the part of needle which sends usage data??". The app loads only
needle's native engine; the Python package and command-line tool, which carry
the usage-data client, are never installed. This module is the check at
install that makes "the engine has no network code" something the app
verifies rather than something it was told: it reads the engine's *imported*
symbols (the functions it asks the operating system or another library for)
and `network_calls` names any that open a connection.

Pure Python over `struct`, no new dependency, and nothing is executed or
loaded. Three formats:

- **ELF** (Linux): the dynamic symbol table's undefined entries, and the
  `DT_NEEDED` library names.
- **PE** (Windows): the import directory and the delay-import directory, so
  each imported DLL and each function by name.
- **Mach-O** (macOS): `LC_SYMTAB`'s undefined symbols and the `LC_LOAD_DYLIB`
  family's library names, in a thin file or a fat (universal) one.

What it cannot see: a library that reaches the network by raw system call
or by resolving a function at run time (`dlsym`, `GetProcAddress`) with a
name built on the fly. It is a tripwire against an engine that links a
network stack, which is the case that matters when a vendor swaps the file,
not a sandbox. The hash pin is the other half: the file is the one that was
read.
"""

from __future__ import annotations

import re
import struct


class NotANativeLibrary(ValueError):
    """The bytes are not an ELF, PE or Mach-O file this reader understands."""


#: Exact function names (after `normalise`) that open or use a socket or
#: resolve a host name, across libc, Winsock and the BSD layer.
_NETWORK_FUNCTIONS = frozenset(
    {
        "socket", "socketpair", "connect", "send", "sendto", "sendmsg", "sendmmsg",
        "recv", "recvfrom", "recvmsg", "recvmmsg", "accept", "accept4", "listen",
        "getaddrinfo", "freeaddrinfo", "getnameinfo", "gethostbyname", "gethostbyname2",
        "gethostbyaddr", "getservbyname", "res_query", "res_search", "res_init",
        "wsastartup", "wsasocketa", "wsasocketw", "wsaconnect", "wsasend", "wsarecv",
        "wsasendto", "wsarecvfrom", "getaddrinfow", "getaddrinfoexw", "gethostnamew",
        "nw_connection_create", "nw_connection_start", "nw_endpoint_create_host",
    }
)

#: A name that merely contains one of these is a network API (WinHTTP, WinINet,
#: Foundation's URL loading, CFNetwork, libcurl and the Winsock families).
_NETWORK_SUBSTRINGS = (
    "winhttp", "wininet", "internetopen", "internetconnect", "httpsendrequest",
    "urlsession", "nsurlconnection", "nsurlrequest", "cfnetwork", "cfhttp",
    "cfsocket", "curl_easy", "curl_global",
)

#: A library whose very presence in the import list is a network stack.
_NETWORK_LIBRARIES = (
    "ws2_32", "wsock32", "winhttp", "wininet", "urlmon", "dnsapi", "mswsock",
    "libcurl", "cfnetwork", "network.framework", "libssl", "libcrypto",
)


_MAC_SUFFIX = re.compile(r"\$(nocancel|unix2003|inode64|darwin_extsn)$")


def normalise(name: str) -> str:
    """A symbol as compared: no leading underscore (Mach-O), no `@VERSION` or
    `$suffix`, lower case, so `_connect`, `connect@GLIBC_2.2.5` and
    `CONNECT` are one name."""
    name = name.split("@", 1)[0].lstrip("_").lower()
    # macOS's legacy-variant suffixes (`connect$NOCANCEL`), not Objective-C
    # names, which carry a `$` of their own (`OBJC_CLASS_$_NSURLSession`).
    return _MAC_SUFFIX.sub("", name)


def is_network_symbol(name: str) -> bool:
    low = normalise(name)
    if low in _NETWORK_FUNCTIONS:
        return True
    return any(part in low for part in _NETWORK_SUBSTRINGS)


def is_network_library(name: str) -> bool:
    low = name.lower().rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return any(low.startswith(lib) for lib in _NETWORK_LIBRARIES)


def _cstr(blob: bytes, start: int) -> str:
    if start < 0 or start >= len(blob):
        return ""
    end = blob.find(b"\0", start)
    return blob[start : end if end >= 0 else len(blob)].decode("latin-1")


# --- ELF ---------------------------------------------------------------------


def _elf_sections(data: bytes, bits: int, endian: str) -> list[dict]:
    """The section table: each section's type, offset, size, link and entry size."""
    try:
        if bits == 2:
            shoff, = struct.unpack_from(endian + "Q", data, 0x28)
            shentsize, shnum = struct.unpack_from(endian + "HH", data, 0x3A)
            layout = "IIQQQQIIQQ"
        else:
            shoff, = struct.unpack_from(endian + "I", data, 0x20)
            shentsize, shnum = struct.unpack_from(endian + "HH", data, 0x2E)
            layout = "IIIIIIIIII"
        sections = []
        for i in range(shnum):
            f = struct.unpack_from(endian + layout, data, shoff + i * shentsize)
            sections.append({"type": f[1], "offset": f[4], "size": f[5], "link": f[6], "entsize": f[9]})
        return sections
    except struct.error as exc:
        raise NotANativeLibrary("truncated ELF section table") from exc


def _elf_strings(data: bytes, sections: list[dict], sec: dict) -> bytes | None:
    """The string table a section links to, or None when the link is bad."""
    if not 0 <= sec["link"] < len(sections):
        return None
    strtab = sections[sec["link"]]
    return data[strtab["offset"] : strtab["offset"] + strtab["size"]]


def _elf_imported_symbols(data: bytes, sec: dict, names: bytes, bits: int, endian: str) -> set[str]:
    """The undefined (imported) symbols of one dynamic symbol table."""
    symbols: set[str] = set()
    size = sec["entsize"] or (24 if bits == 2 else 16)
    for off in range(sec["offset"], sec["offset"] + sec["size"] - size + 1, size):
        if bits == 2:
            st_name, _info, _other, shndx = struct.unpack_from(endian + "IBBH", data, off)
        else:
            st_name, _value, _sz, _info, _other, shndx = struct.unpack_from(endian + "IIIBBH", data, off)
        if shndx == 0 and st_name:  # SHN_UNDEF: imported
            symbols.add(_cstr(names, st_name))
    return symbols


def _elf_needed_libraries(data: bytes, sec: dict, names: bytes, bits: int, endian: str) -> set[str]:
    """The DT_NEEDED entries of one dynamic section."""
    libraries: set[str] = set()
    width = 16 if bits == 2 else 8
    fmt = endian + ("qQ" if bits == 2 else "iI")
    for off in range(sec["offset"], sec["offset"] + sec["size"] - width + 1, width):
        tag, val = struct.unpack_from(fmt, data, off)
        if tag == 0:
            break
        if tag == 1:  # DT_NEEDED
            libraries.add(_cstr(names, val))
    return libraries


def _elf(data: bytes) -> tuple[set[str], set[str]]:
    if len(data) < 64:
        raise NotANativeLibrary("truncated ELF header")
    bits = data[4]
    endian = "<" if data[5] == 1 else ">"
    if bits not in (1, 2) or data[5] not in (1, 2):
        raise NotANativeLibrary("bad ELF class")
    sections = _elf_sections(data, bits, endian)

    symbols: set[str] = set()
    libraries: set[str] = set()
    for sec in sections:
        if sec["type"] not in (11, 6):  # SHT_DYNSYM, SHT_DYNAMIC
            continue
        names = _elf_strings(data, sections, sec)
        if names is None:
            continue
        if sec["type"] == 11:
            symbols |= _elf_imported_symbols(data, sec, names, bits, endian)
        else:
            libraries |= _elf_needed_libraries(data, sec, names, bits, endian)
    symbols.discard("")
    if not any(sec["type"] == 11 for sec in sections):
        # A library with no dynamic symbol table cannot be checked, so it is
        # not waved through as "imports nothing".
        raise NotANativeLibrary("ELF file has no dynamic symbol table")
    return symbols, libraries


# --- PE ----------------------------------------------------------------------


def _pe(data: bytes) -> tuple[set[str], set[str]]:
    try:
        pe_off, = struct.unpack_from("<I", data, 0x3C)
        if data[pe_off : pe_off + 4] != b"PE\0\0":
            raise NotANativeLibrary("no PE signature")
        _machine, nsec, _ts, _sym, _nsym, opt_size, _chars = struct.unpack_from("<HHIIIHH", data, pe_off + 4)
        opt = pe_off + 24
        magic, = struct.unpack_from("<H", data, opt)
        if magic == 0x20B:
            dirs = opt + 112
            thunk = 8
        elif magic == 0x10B:
            dirs = opt + 96
            thunk = 4
        else:
            raise NotANativeLibrary("unknown PE optional header")
        sect_base = opt + opt_size
        sections = []
        for i in range(nsec):
            _n, vsize, vaddr, rawsize, rawptr = struct.unpack_from("<8sIIII", data, sect_base + i * 40)
            sections.append((vaddr, max(vsize, rawsize), rawptr))

        def to_off(rva: int) -> int:
            for vaddr, size, rawptr in sections:
                if vaddr <= rva < vaddr + size:
                    return rva - vaddr + rawptr
            return -1

        def directory(index: int) -> int:
            rva, size = struct.unpack_from("<II", data, dirs + index * 8)
            return rva if size else 0

        symbols: set[str] = set()
        libraries: set[str] = set()

        def walk(table_rva: int, entry: int, name_field: int, thunk_field: int) -> None:
            off = to_off(table_rva)
            while off >= 0 and off + entry <= len(data):
                fields = struct.unpack_from("<" + "I" * (entry // 4), data, off)
                if not any(fields):
                    break
                name_off = to_off(fields[name_field])
                if name_off >= 0:
                    libraries.add(_cstr(data, name_off))
                cursor = to_off(fields[thunk_field])
                while cursor >= 0 and cursor + thunk <= len(data):
                    value = int.from_bytes(data[cursor : cursor + thunk], "little")
                    if value == 0:
                        break
                    ordinal = value >> (thunk * 8 - 1)
                    if not ordinal:
                        hint = to_off(value & 0x7FFFFFFF)
                        if hint >= 0:
                            symbols.add(_cstr(data, hint + 2))
                    cursor += thunk
                off += entry

        imports = directory(1)
        if imports:
            walk(imports, 20, 3, 0)  # Name at +12, OriginalFirstThunk at +0
        delay = directory(13)
        if delay:
            walk(delay, 32, 1, 4)  # DllNameRVA at +4, ImportNameTableRVA at +16
        return symbols, libraries
    except struct.error as exc:
        raise NotANativeLibrary("truncated PE file") from exc


# --- Mach-O ------------------------------------------------------------------

_MACHO_MAGICS = {
    b"\xfe\xed\xfa\xce": (">", 32), b"\xce\xfa\xed\xfe": ("<", 32),
    b"\xfe\xed\xfa\xcf": (">", 64), b"\xcf\xfa\xed\xfe": ("<", 64),
}
_DYLIB_COMMANDS = {0xC, 0xD, 0x18, 0x1F, 0x23}  # LOAD, LOAD_WEAK, LAZY_LOAD, REEXPORT, UPWARD


def _macho(data: bytes, base: int = 0) -> tuple[set[str], set[str]]:
    endian, bits = _MACHO_MAGICS[data[base : base + 4]]
    try:
        ncmds, _size = struct.unpack_from(endian + "II", data, base + 16)
        off = base + (32 if bits == 64 else 28)
        symbols: set[str] = set()
        libraries: set[str] = set()
        for _ in range(ncmds):
            cmd, size = struct.unpack_from(endian + "II", data, off)
            if size < 8:
                raise NotANativeLibrary("bad Mach-O load command")
            if cmd in _DYLIB_COMMANDS:
                name_off, = struct.unpack_from(endian + "I", data, off + 8)
                libraries.add(_cstr(data, off + name_off))
            elif cmd == 0x2:  # LC_SYMTAB
                symoff, nsyms, stroff, strsize = struct.unpack_from(endian + "IIII", data, off + 8)
                strtab = data[base + stroff : base + stroff + strsize]
                width = 16 if bits == 64 else 12
                for i in range(nsyms):
                    at = base + symoff + i * width
                    n_strx, n_type, _sect, _desc = struct.unpack_from(endian + "IBBH", data, at)
                    # N_EXT set, N_TYPE (the 0x0e bits) clear: undefined, imported.
                    if n_type & 0x01 and not n_type & 0x0E and n_strx:
                        symbols.add(_cstr(strtab, n_strx))
            off += size
        return symbols, libraries
    except struct.error as exc:
        raise NotANativeLibrary("truncated Mach-O file") from exc


def _fat(data: bytes) -> tuple[set[str], set[str]]:
    big = data[:4] in (b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca")
    endian = ">" if data[:4] in (b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf") else "<"
    try:
        count, = struct.unpack_from(endian + "I", data, 4)
        symbols: set[str] = set()
        libraries: set[str] = set()
        for i in range(min(count, 16)):
            if big:
                _cpu, _sub, offset, _size, _align = struct.unpack_from(endian + "iiQQI", data, 8 + i * 32)
            else:
                _cpu, _sub, offset, _size, _align = struct.unpack_from(endian + "iiIII", data, 8 + i * 20)
            s, lib = _macho(data, offset)
            symbols |= s
            libraries |= lib
        return symbols, libraries
    except (struct.error, KeyError) as exc:
        raise NotANativeLibrary("bad universal Mach-O file") from exc


def read_imports(data: bytes) -> tuple[set[str], set[str]]:
    """(imported symbol names, imported library names) of a native library.
    Raises `NotANativeLibrary` for anything that is not ELF, PE or Mach-O."""
    head = data[:4]
    if head == b"\x7fELF":
        return _elf(data)
    if data[:2] == b"MZ":
        return _pe(data)
    if head in _MACHO_MAGICS:
        return _macho(data)
    if head in (b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca", b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca"):
        return _fat(data)
    raise NotANativeLibrary("not an ELF, PE or Mach-O file")


def network_calls(data: bytes) -> list[str]:
    """The network functions and libraries a native library imports, sorted;
    empty when it imports none. Raises `NotANativeLibrary` if unreadable."""
    symbols, libraries = read_imports(data)
    found = {name for name in symbols if is_network_symbol(name)}
    found |= {name for name in libraries if is_network_library(name)}
    return sorted(found)

