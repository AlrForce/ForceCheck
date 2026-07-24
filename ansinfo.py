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


def _local_time(timezone: str) -> tuple:
    """Returns (timezone_display, local_time_str)"""
    import datetime
    if not timezone:
        return "—", "—"
    try:
        import zoneinfo
        tz  = zoneinfo.ZoneInfo(timezone)
        now = datetime.datetime.now(tz)
        off = now.strftime("%z")
        gmt = f"GMT{off[:3]}:{off[3:]}" if len(off) == 5 else ""
        return (
            f"{timezone}, {gmt}",
            now.strftime(f"%H:%M ({off}) %Y.%m.%d"),
        )
    except Exception:
        return timezone, "—"


def _fetch_geo(ip: str) -> dict:
    """Try ip-api.com then ipinfo.io; return normalized fields."""
    import requests

    try:
        r = requests.get(f"http://ip-api.com/json/{ip}", timeout=8)
        if r.status_code == 200:
            d = r.json()
            if d.get("status") == "success":
                as_raw   = d.get("as", "")
                isp_name = d.get("isp", d.get("org", ""))
                asn_num  = ""
                if as_raw.startswith("AS"):
                    parts    = as_raw.split(" ", 1)
                    asn_num  = parts[0][2:]
                    if len(parts) > 1 and not isp_name:
                        isp_name = parts[1]
                country = d.get("country", "")
                cc      = d.get("countryCode", "")
                return {
                    "country":  f"{country} ({cc})" if country and cc else country or cc,
                    "region":   d.get("regionName", ""),
                    "city":     d.get("city", ""),
                    "postal":   d.get("zip", ""),
                    "timezone": d.get("timezone", ""),
                    "asn":      asn_num,
                    "isp":      isp_name,
                }
    except Exception:
        pass

    try:
        r = requests.get(f"https://ipinfo.io/{ip}/json", timeout=8)
        if r.status_code == 200:
            d        = r.json()
            org_raw  = d.get("org", "")
            asn_num, isp_name = "", org_raw
            if org_raw.startswith("AS"):
                parts    = org_raw.split(" ", 1)
                asn_num  = parts[0][2:]
                isp_name = parts[1] if len(parts) > 1 else ""
            return {
                "country":  d.get("country", ""),
                "region":   d.get("region", ""),
                "city":     d.get("city", ""),
                "postal":   d.get("postal", ""),
                "timezone": d.get("timezone", ""),
                "asn":      asn_num,
                "isp":      isp_name,
            }
    except Exception:
        pass

    return {}


def run_ip(target: str) -> None:
    import requests

    ip = _resolve_to_ip(target)
    if ip != target.split("/")[0]:
        print(f"\n  {DIM}resolved {target} → {ip}{N}")

    hostname = ip
    try:
        hostname = socket.gethostbyaddr(ip)[0]
    except Exception:
        pass

    geo = _fetch_geo(ip)

    ip_range = "—"
    try:
        rd = requests.get(RDAP_IP.format(ip), timeout=8,
                          headers={"Accept": "application/rdap+json"})
        if rd.status_code == 200:
            d        = rd.json()
            cidrs    = d.get("cidr0_cidrs", [])
            cidr_str = ", ".join(
                f"{c.get('v4prefix', c.get('v6prefix', '?'))}/{c.get('length', '?')}"
                for c in cidrs
            )
            s = d.get("startAddress", "")
            e = d.get("endAddress", "")
            ip_range = f"{s} - {e}  {DIM}CIDR: {cidr_str}{N}" if cidr_str else f"{s} - {e}"
    except Exception:
        pass

    asn        = geo.get("asn", "")  or "—"
    isp        = geo.get("isp", "")  or "—"
    country    = geo.get("country", "") or "—"
    region     = geo.get("region",  "") or "—"
    city       = geo.get("city",    "") or "—"
    postal     = geo.get("postal",  "") or "—"
    tz_disp, local_time = _local_time(geo.get("timezone", ""))

    print(f"\n{C}INFO  {ip}{N}\n")
    _row("IP address",  f"{B}{ip}{N}")
    _row("Host name",   hostname)
    _row("IP range",    ip_range)
    _row("ASN",         asn)
    _row("ISP / Org",   isp)
    _row("Country",     country)
    _row("Region",      region)
    _row("City",        city)
    _row("Time zone",   tz_disp)
    _row("Local time",  local_time)
    _row("Postal Code", postal)
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
