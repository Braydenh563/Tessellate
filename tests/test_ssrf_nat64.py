"""NAT64 forms of local addresses are refused, whatever Python's own address table says.

Source: LEDGER L-general-1 (ANALYSIS.md:4350). The well-known NAT64 prefix 64:ff9b::/96 carries an
IPv4 address in its last 32 bits, which a NAT64 gateway then reaches. Python 3.11 and 3.12 (both
supported) report the whole prefix as global, so 64:ff9b::7f00:1 (127.0.0.1) and
64:ff9b::a9fe:a9fe (the cloud metadata service) passed `is_internal_address`.
"""

from __future__ import annotations

import ipaddress

import pytest

from tessellate.core import security


@pytest.mark.parametrize(
    ("nat64", "ipv4"),
    [("64:ff9b::7f00:1", "127.0.0.1"), ("64:ff9b::a9fe:a9fe", "169.254.169.254"), ("64:ff9b::a00:5", "10.0.0.5")],
)
def test_a_nat64_address_is_judged_by_the_ipv4_address_it_carries(monkeypatch, nat64, ipv4):
    assert security._nat64_embedded(ipaddress.ip_address(nat64)) == ipaddress.ip_address(ipv4)
    monkeypatch.setattr(security, "_resolve", lambda host: [nat64])
    with pytest.raises(security.UnsafeUrl, match="local address"):
        security.public_addresses("https://example.com/")


def test_the_decode_only_reads_the_nat64_prefix():
    for other in ("2001:db8::7f00:1", "::ffff:127.0.0.1", "127.0.0.1", "64:ff9b:1::7f00:1"):
        assert security._nat64_embedded(ipaddress.ip_address(other)) is None


def test_the_decode_holds_even_where_python_calls_the_prefix_global(monkeypatch):
    """Stand in for 3.11 and 3.12: the embedded address decides, not the prefix's own flags."""

    class GlobalLooking(ipaddress.IPv6Address):
        is_global = True
        is_private = is_loopback = is_link_local = is_reserved = is_multicast = is_unspecified = False

    assert security.is_internal_address(GlobalLooking("64:ff9b::7f00:1")) is True
    assert security.is_internal_address(GlobalLooking("64:ff9b::808:808")) is False
