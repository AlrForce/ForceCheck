"""
bgp — BGP route lookup via bgpview.io API

Usage:
  bgp! <ip | prefix | asn>
"""

import re
import sys
import argparse

from .colors import G, R, Y, C, B, DIM, N
from ._deps import ensure_deps

BGPVIEW = "https://api.bgpview.io"
_ASN_RE = re.compile(r"^(?:AS)?(\d+)$", re.I)


def _row(label: str, value: str) -> None:
    print(f"  {DIM}{label:<16}{N}{value}")


def run(target: str) -> None:
    import requests

    m = _ASN_RE.match(target)
    if m:
        _run_asn(requests, int(m.group(1)))
    else:
        _run_ip(requests, target)


def _run_ip(requests, target: str) -> None:
    ip = target.split("/")[0]

    print(f"\n{C}BGP  {target}  —  bgpview.io{N}\n")

    try:
        r = requests.get(f"{BGPVIEW}/ip/{ip}", timeout=15,
                         headers={"Accept": "application/json"})
        r.raise_for_status()
    except requests.exceptions.ConnectionError:
        sys.exit(f"{R}Cannot connect to bgpview.io{N}")
    except requests.exceptions.HTTPError as e:
        sys.exit(f"{R}API error:{N} {e}")

    d = r.json().get("data", {})
    if not d:
        sys.exit(f"{R}No data returned for {target}{N}")

    ptr = d.get("ptr_record") or "—"
    _row("PTR", ptr)

    prefixes = d.get("prefixes", [])
    if not prefixes:
        print(f"  {Y}No BGP prefix found for {target}.{N}\n")
        return

    for pfx in prefixes:
        prefix  = pfx.get("prefix", "—")
        asn_obj = pfx.get("asn", {})
        asn     = asn_obj.get("asn", "—")
        name    = asn_obj.get("name", "—")
        desc    = asn_obj.get("description", "—")
        country = asn_obj.get("country_code", "—")

        print(f"  {B}{'─' * 50}{N}")
        _row("Prefix",  f"{G}{prefix}{N}")
        _row("ASN",     f"{B}AS{asn}{N}  {DIM}({name}){N}")
        _row("Network", desc)
        _row("Country", country)

    rir = d.get("rir_allocation", {})
    if rir:
        print(f"\n  {DIM}RIR Allocation{N}")
        _row("  RIR",       rir.get("rir_name", "—"))
        _row("  Prefix",    rir.get("prefix", "—"))
        _row("  Allocated", (rir.get("date_allocated") or "—")[:10])

    print()


def _run_asn(requests, asn: int) -> None:
    print(f"\n{C}BGP  AS{asn}  —  bgpview.io{N}\n")

    try:
        r = requests.get(f"{BGPVIEW}/asn/{asn}", timeout=15,
                         headers={"Accept": "application/json"})
        r.raise_for_status()
    except requests.exceptions.ConnectionError:
        sys.exit(f"{R}Cannot connect to bgpview.io{N}")
    except requests.exceptions.HTTPError as e:
        sys.exit(f"{R}API error:{N} {e}")

    d = r.json().get("data", {})
    if not d:
        sys.exit(f"{R}No data returned for AS{asn}{N}")

    _row("ASN",          f"AS{d.get('asn', asn)}")
    _row("Name",         d.get("name", "—"))
    _row("Description",  d.get("description", "—"))
    _row("Country",      d.get("country_code", "—"))
    _row("Website",      d.get("website") or "—")
    _row("Looking Glass",d.get("looking_glass") or "—")
    _row("Traffic Lvl",  d.get("traffic_estimation") or "—")

    # تعداد prefix‌ها
    try:
        rp = requests.get(f"{BGPVIEW}/asn/{asn}/prefixes", timeout=15,
                          headers={"Accept": "application/json"})
        pfx_data = rp.json().get("data", {})
        v4 = len(pfx_data.get("ipv4_prefixes", []))
        v6 = len(pfx_data.get("ipv6_prefixes", []))
        _row("Prefixes",  f"IPv4: {v4}  ·  IPv6: {v6}")
    except Exception:
        pass

    print()


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="bgp!",
        description="BGP route lookup via bgpview.io",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  bgp! 1.1.1.1\n  bgp! 8.8.8.0/24\n  bgp! AS15169\n  bgp! 185.220.101.0/24",
    )
    ap.add_argument("host", help="IP address, prefix (x.x.x.x/yy), or ASN")

    args = ap.parse_args()
    ensure_deps()

    try:
        run(args.host)
    except KeyboardInterrupt:
        print(f"\n{Y}aborted{N}")
