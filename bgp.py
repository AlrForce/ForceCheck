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
    """ساخت و نمایش BGP path با استفاده از asn-neighbours"""

    path = [(origin_asn, origin_holder)]
    visited = {origin_asn}
    current = origin_asn

    for _ in range(4):
        d = _api(sess, "asn-neighbours", f"AS{current}", silent=True)
        neighbours = d.get("neighbours", [])

        upstreams = sorted(
            [n for n in neighbours if n.get("type") == "left"],
            key=lambda x: x.get("power", 0), reverse=True
        )
        if not upstreams:
            break

        next_asn = upstreams[0].get("asn")
        if not next_asn or next_asn in visited:
            break

        visited.add(next_asn)
        info = _api(sess, "as-overview", f"AS{next_asn}", silent=True)
        name = info.get("holder", f"AS{next_asn}")
        path.append((next_asn, name))
        current = next_asn

    if len(path) < 2:
        return

    path.reverse()

    _CYAN   = '\033[96m'
    _GOLD   = '\033[93m'
    _WHITE  = '\033[97m'

    _PALETTE = [_CYAN, _GOLD, _WHITE]

    total = len(path)

    def _hop_style(idx: int) -> tuple:
        if idx == total - 1:
            return _WHITE, f"  {_WHITE}◀ origin{N}"
        elif idx == 0:
            return _CYAN, f"  {_CYAN}▲ upstream{N}"
        else:
            return _GOLD, f"  {_GOLD}◆ transit{N}"

    print(f"\n  {_CYAN}── BGP MAP ──────────────────────────────────────────{N}")
    print(f"  {DIM}  {total} hops  ·  upstream → origin{N}\n")

    for i, (asn, name) in enumerate(path):
        color, tag = _hop_style(i)
        label      = f"AS{asn}"

        inner_w = max(len(label) + 6, len(name) + 4)
        top = f"╔═[ {label} ]{'═' * (inner_w - len(label) - 5)}╗"
        bot = f"╚{'═' * inner_w}╝"
        pad = " " * (inner_w - len(name) - 2)

        if i > 0:
            print(f"        {DIM}│{N}")

        print(f"  {color}{top}{N}")
        print(f"  {color}║  {DIM}{name}{color}{pad}║{N}{tag}")
        print(f"  {color}{bot}{N}")

    print(f"        {DIM}│{N}")
    print(f"  {_GOLD}  ▶  {prefix}  ◀ destination{N}")
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

    rir_d = _api(sess, "rir", prefix)
    rirs  = rir_d.get("rirs", [])
    if rirs:
        print(f"\n  {DIM}RIR Allocation{N}")
        _row("  RIR", rirs[0].get("rir", "—"))

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
