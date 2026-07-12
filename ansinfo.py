"""
ansinfo — IP & ASN lookup via RDAP + ipinfo.io

Usage:
  info! <ip | hostname | prefix | asn>
"""

import re
import sys
import socket
import argparse

from .colors import G, R, Y, C, B, DIM, N
from ._deps import ensure_deps

RDAP_IP  = "https://rdap.org/ip/{}"
RDAP_ASN = "https://rdap.org/autnum/{}"
IPINFO   = "https://ipinfo.io/{}/json"

_ASN_RE = re.compile(r"^(?:AS)?(\d+)$", re.I)


def _is_ip(s: str) -> bool:
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            socket.inet_pton(family, s)
            return True
        except OSError:
            continue
    return False


def _resolve_to_ip(target: str) -> str:
    bare = target.split("/")[0]
    if _is_ip(bare):
        return bare
    try:
        return socket.gethostbyname(bare)
    except socket.gaierror:
        sys.exit(f"{R}Cannot resolve: {bare}{N}")


def _entity_name(entity: dict) -> str:
    vcard_fields = entity.get("vcardArray", [None, []])[1]
    for field in vcard_fields:
        if field[0] == "fn" and field[3]:
            return field[3]
    return entity.get("handle", "—")


def _fmt_date(s: str) -> str:
    return s[:10] if s else "—"


def _row(label: str, value: str) -> None:
    print(f"  {DIM}{label:<14}{N}{value}")


def run_ip(target: str) -> None:
    import requests

    ip = _resolve_to_ip(target)
    if ip != target.split("/")[0]:
        print(f"\n  {DIM}resolved {target} → {ip}{N}")

    try:
        r = requests.get(
            RDAP_IP.format(ip),
            timeout=15,
            headers={"Accept": "application/rdap+json"},
        )
        r.raise_for_status()
    except requests.exceptions.ConnectionError:
        sys.exit(f"{R}Cannot connect to rdap.org{N}")
    except requests.exceptions.HTTPError as e:
        sys.exit(f"{R}RDAP error:{N} {e}")

    d = r.json()

    handle  = d.get("handle", "—")
    name    = d.get("name", "—")
    country = d.get("country", "—")
    start   = d.get("startAddress", "—")
    end     = d.get("endAddress", "—")

    cidrs = d.get("cidr0_cidrs", [])
    cidr_str = ", ".join(
        f"{c.get('v4prefix', c.get('v6prefix', '?'))}/{c.get('length', '?')}"
        for c in cidrs
    ) or "—"

    org = "—"
    for ent in d.get("entities", []):
        roles = ent.get("roles", [])
        if "registrant" in roles or "administrative" in roles:
            org = _entity_name(ent)
            # زیر-entity برای سازمان اصلی
            for sub in ent.get("entities", []):
                if "registrant" in sub.get("roles", []):
                    org = _entity_name(sub)
            break

    registered = updated = "—"
    for ev in d.get("events", []):
        action = ev.get("eventAction", "")
        if action == "registration":
            registered = _fmt_date(ev.get("eventDate", ""))
        elif action == "last changed":
            updated = _fmt_date(ev.get("eventDate", ""))

    links = d.get("links", [])
    source = links[0].get("href", "").split("/")[2] if links else d.get("port43", "—")

    # geo از ipinfo.io
    geo = {}
    try:
        geo = requests.get(IPINFO.format(ip), timeout=8).json()
    except Exception:
        pass

    print(f"\n{C}INFO  {ip}{N}\n")
    _row("Network",      f"{handle}  {DIM}({name}){N}")
    _row("CIDR",         cidr_str)
    _row("Range",        f"{start}  —  {end}")
    _row("Organization", org)
    _row("Country",      country)
    _row("Registered",   registered)
    _row("Updated",      updated)
    _row("Source",       source)

    if geo:
        print(f"\n  {B}── IP Geolocation ─────────────────────────{N}\n")
        city     = geo.get("city", "")
        region   = geo.get("region", "")
        country2 = geo.get("country", "")
        location = ", ".join(filter(None, [city, region, country2]))
        if location:
            _row("Location",  location)
        if geo.get("org"):
            _row("ISP / ASN", geo["org"])
        if geo.get("timezone"):
            _row("Timezone",  geo["timezone"])
        if geo.get("loc"):
            _row("Coords",    geo["loc"])

    print()


def run_asn(asn_num: int) -> None:
    import requests

    try:
        r = requests.get(
            RDAP_ASN.format(asn_num),
            timeout=15,
            headers={"Accept": "application/rdap+json"},
        )
        r.raise_for_status()
    except requests.exceptions.ConnectionError:
        sys.exit(f"{R}Cannot connect to rdap.org{N}")
    except requests.exceptions.HTTPError as e:
        sys.exit(f"{R}RDAP error:{N} {e}")

    d = r.json()

    handle = d.get("handle", f"AS{asn_num}")
    name   = d.get("name", "—")
    start  = d.get("startAutnum", asn_num)
    end    = d.get("endAutnum",   asn_num)

    org = country = "—"
    for ent in d.get("entities", []):
        roles = ent.get("roles", [])
        if any(role in roles for role in ("registrant", "administrative")):
            org = _entity_name(ent)
        c = ent.get("country", "")
        if c:
            country = c

    registered = updated = "—"
    for ev in d.get("events", []):
        action = ev.get("eventAction", "")
        if action == "registration":
            registered = _fmt_date(ev.get("eventDate", ""))
        elif action == "last changed":
            updated = _fmt_date(ev.get("eventDate", ""))

    asn_range = f"{start}" if start == end else f"{start} — {end}"

    print(f"\n{C}WHOIS AS{asn_num}{N}\n")
    _row("ASN",          handle)
    _row("Name",         name)
    _row("Organization", org)
    _row("Country",      country)
    _row("ASN Range",    asn_range)
    _row("Registered",   registered)
    _row("Updated",      updated)
    print()


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="info!",
        description="IP and ASN WHOIS lookup via RDAP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  info! 8.8.8.8\n"
            "  info! google.com\n"
            "  info! 8.8.8.0/24\n"
            "  info! AS15169"
        ),
    )
    ap.add_argument(
        "target",
        help="IP address, hostname, prefix (x.x.x.x/yy), or ASN (AS15169 or 15169)",
    )

    args = ap.parse_args()
    ensure_deps()

    m = _ASN_RE.match(args.target)
    try:
        if m:
            run_asn(int(m.group(1)))
        else:
            run_ip(args.target)
    except KeyboardInterrupt:
        print(f"\n{Y}aborted{N}")
