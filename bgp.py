"""
bgp — BGP route lookup via stat.ripe.net

Usage:
  bgp! <ip | prefix | asn>
"""

import re
import sys
import argparse

from .colors import G, R, Y, C, B, DIM, N
from ._deps import ensure_deps

RIPESTAT = "https://stat.ripe.net/data"
IPINFO   = "https://ipinfo.io"
_ASN_RE  = re.compile(r"^(?:AS)?(\d+)$", re.I)


def _row(label: str, value: str) -> None:
    print(f"  {DIM}{label:<16}{N}{value}")


def _api(sess, endpoint: str, resource: str, silent: bool = False) -> dict:
    import requests as req
    from urllib.parse import quote
    try:
        # ساخت مستقیم URL تا slash در prefix ها encode نشه
        url = f"{RIPESTAT}/{endpoint}/data.json?resource={quote(resource, safe='/.:')}"
        r = sess.get(url, timeout=15)
        r.raise_for_status()
        return r.json().get("data", {})
    except req.exceptions.ConnectionError:
        if silent:
            return {}
        sys.exit(f"{R}Cannot connect to stat.ripe.net{N}")
    except req.exceptions.HTTPError:
        if silent:
            return {}
        sys.exit(f"{R}API error: endpoint not available{N}")
    except Exception:
        return {}


def _bgp_map(sess, prefix: str, origin_asn: int, origin_holder: str) -> None:
    """نمایش AS path به صورت ASCII map"""
    # looking-glass: AS path از چندین RRC collector
    d = _api(sess, "looking-glass", prefix, silent=True)
    rrcs = d.get("rrcs", [])
    if not rrcs:
        return

    # جمع‌آوری مسیرهای منحصربه‌فرد از همه rrcs
    seen_paths: set = set()
    paths = []
    for rrc in rrcs:
        for entry in rrc.get("entries", []):
            path_raw = entry.get("as_path", [])
            if isinstance(path_raw, str):
                asns = tuple(int(x) for x in path_raw.split() if x.isdigit())
            else:
                asns = tuple(int(x) for x in path_raw if str(x).isdigit())

            # حذف AS prepending (ASN های تکراری پشت سرهم)
            deduped: list = []
            for a in asns:
                if not deduped or deduped[-1] != a:
                    deduped.append(a)
            asns = tuple(deduped)

            if asns and asns not in seen_paths:
                seen_paths.add(asns)
                paths.append(list(asns))

    if not paths:
        return

    # کوتاه‌ترین مسیر
    shortest = min(paths, key=len)

    # دریافت نام‌های ASN به صورت bulk
    asn_names: dict = {origin_asn: origin_holder}
    try:
        resource_str = ",".join(f"AS{a}" for a in dict.fromkeys(shortest))
        names_d = _api(sess, "as-names", resource_str)
        for asn_str, name in names_d.get("names", {}).items():
            try:
                asn_names[int(asn_str)] = name
            except (ValueError, TypeError):
                pass
    except Exception:
        pass

    # نمایش
    W = 46
    print(f"\n  {C}── BGP MAP ──────────────────────────────────────────{N}\n")
    print(f"  {DIM}path hops: {len(shortest)}{N}\n")

    for i, asn in enumerate(shortest):
        name     = asn_names.get(asn, "—")
        is_origin = (asn == origin_asn)
        color    = G if is_origin else B
        tag      = f"  {G}◀ origin{N}" if is_origin else ""

        if i > 0:
            print(f"  {DIM}      │{N}")

        label = f"AS{asn}"
        print(f"  {color}[ {label:<8} ]{N}  {DIM}{name}{N}{tag}")

    print(f"  {DIM}      │{N}")
    print(f"  {G}[ {prefix:<8} ]{N}  {G}◀ destination{N}")
    print()


def run(target: str) -> None:
    import requests
    sess = requests.Session()
    sess.headers.update({"Accept": "application/json"})

    m = _ASN_RE.match(target)
    if m:
        _run_asn(sess, int(m.group(1)))
    else:
        _run_ip(sess, target)


def _run_ip(sess, target: str) -> None:
    print(f"\n{C}BGP  {target}  —  stat.ripe.net{N}\n")

    d = _api(sess, "prefix-overview", target)
    if not d or not d.get("announced"):
        print(f"  {Y}No BGP announcement found for {target}.{N}\n")
        return

    prefix = d.get("resource", target)
    asns   = d.get("asns", [])

    if not asns:
        print(f"  {Y}No ASN associated with {target}.{N}\n")
        return

    # geo از ipinfo.io
    geo = {}
    try:
        ip  = target.split("/")[0]
        geo = sess.get(f"{IPINFO}/{ip}/json", timeout=8).json()
    except Exception:
        pass

    origin_asn    = asns[0].get("asn", 0)
    origin_holder = asns[0].get("holder", "—")

    for asn_info in asns:
        asn    = asn_info.get("asn", "—")
        holder = asn_info.get("holder", "—")

        print(f"  {B}{'─' * 50}{N}")
        _row("Prefix",  f"{G}{prefix}{N}")
        _row("ASN",     f"{B}AS{asn}{N}")
        _row("Network", holder)

        if geo.get("country"):
            _row("Country", geo["country"])
        if geo.get("city"):
            _row("City",    geo["city"])
        if geo.get("org"):
            _row("Org",     geo["org"])

    # RIR
    rir_d = _api(sess, "rir", prefix)
    rirs  = rir_d.get("rirs", [])
    if rirs:
        print(f"\n  {DIM}RIR Allocation{N}")
        _row("  RIR", rirs[0].get("rir", "—"))

    # AS Path Map
    _bgp_map(sess, prefix, origin_asn, origin_holder)


def _run_asn(sess, asn: int) -> None:
    print(f"\n{C}BGP  AS{asn}  —  stat.ripe.net{N}\n")

    d = _api(sess, "as-overview", f"AS{asn}")
    if not d:
        sys.exit(f"{R}No data returned for AS{asn}{N}")

    _row("ASN",    f"AS{d.get('asn', asn)}")
    _row("Holder", d.get("holder", "—"))

    block = d.get("block", {})
    if block:
        _row("RIR",   block.get("desc", "—"))
        _row("Range", block.get("resource", "—"))

    # تعداد prefix ها
    pfx_d = _api(sess, "announced-prefixes", f"AS{asn}")
    pfxs  = pfx_d.get("prefixes", [])
    v4 = sum(1 for p in pfxs if "." in p.get("prefix", ""))
    v6 = sum(1 for p in pfxs if ":" in p.get("prefix", ""))
    _row("Prefixes", f"IPv4: {v4}  ·  IPv6: {v6}")

    print()


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="bgp!",
        description="BGP route lookup via stat.ripe.net (RIPE NCC)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  bgp! 1.1.1.1\n  bgp! 8.8.8.0/24\n  bgp! AS15169\n  bgp! AS43754",
    )
    ap.add_argument("host", help="IP address, prefix (x.x.x.x/yy), or ASN")

    args = ap.parse_args()
    ensure_deps()

    try:
        run(args.host)
    except KeyboardInterrupt:
        print(f"\n{Y}aborted{N}")
