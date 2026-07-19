"""
dns — DNS poisoning / filtering detector (Iran-focused)

Queries a domain from many resolvers (international + Iranian + your ISP)
and compares the answers to reveal DNS-level filtering.

Usage:
  dns! <domain>
"""
 
import sys
import socket
import struct
import random
import argparse
from concurrent.futures import ThreadPoolExecutor

from .colors import G, R, Y, C, B, DIM, N

# (label, server IP, group)   group: "intl" | "iran"
_RESOLVERS = [
    ("Google",      "8.8.8.8",        "intl"),
    ("Cloudflare",  "1.1.1.1",        "intl"),
    ("Quad9",       "9.9.9.9",        "intl"),
    ("OpenDNS",     "208.67.222.222", "intl"),
    ("Shecan",      "178.22.122.100", "iran"),
    ("Electro",     "78.157.42.100",  "iran"),
    ("Begzar",      "185.55.226.26",  "iran"),
    ("403.online",  "10.202.10.202",  "iran"),
    ("Radar",       "10.202.10.10",   "iran"),
]

# Known Iranian filter / blackhole answers (the "peyvandha" filter page)
_FILTER_IPS = {"10.10.34.34", "10.10.34.35", "10.10.34.36"}

_COL_NAME = 13
_COL_SRV  = 17
_COL_RES  = 24
_W        = _COL_NAME + _COL_SRV + _COL_RES + 14


# ── minimal DNS over UDP (no dependencies) ─────────────────────────────────

def _build_query(domain: str, qid: int) -> bytes:
    header = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0)  # RD set, 1 question
    q = b""
    for label in domain.split("."):
        if not label:
            continue
        q += bytes([len(label)]) + label.encode("idna")
    q += b"\x00"
    q += struct.pack(">HH", 1, 1)  # QTYPE=A, QCLASS=IN
    return header + q


def _skip_name(data: bytes, offset: int) -> int:
    """Advance past a DNS name (handles compression pointers)."""
    while offset < len(data):
        length = data[offset]
        if length == 0:
            return offset + 1
        if length & 0xC0 == 0xC0:      # compression pointer → name ends here
            return offset + 2
        offset += 1 + length
    return offset


def _query(server: str, domain: str, timeout: float = 3.0):
    """Return list of A-record IPs, [] for no-answer/error, or None on timeout."""
    qid    = random.randint(0, 0xFFFF)
    packet = _build_query(domain, qid)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(packet, (server, 53))
        data, _ = s.recvfrom(1024)
    except Exception:
        return None
    finally:
        s.close()

    if len(data) < 12:
        return []
    _, flags, qd, an, _, _ = struct.unpack(">HHHHHH", data[:12])
    if flags & 0x000F != 0:            # rcode != 0 (NXDOMAIN / refused / ...)
        return []

    offset = 12
    for _ in range(qd):
        offset = _skip_name(data, offset) + 4   # + QTYPE + QCLASS

    ips = []
    for _ in range(an):
        offset = _skip_name(data, offset)
        if offset + 10 > len(data):
            break
        rtype, _, _, rdlen = struct.unpack(">HHIH", data[offset:offset + 10])
        offset += 10
        rdata = data[offset:offset + rdlen]
        offset += rdlen
        if rtype == 1 and rdlen == 4:  # A record
            ips.append(".".join(str(b) for b in rdata))
    return ips


def _query_system(domain: str):
    """Resolve via the OS resolver (= your ISP's DNS inside Iran)."""
    try:
        _, _, addrs = socket.gethostbyname_ex(domain)
        return addrs or []
    except Exception:
        return None


# ── analysis ───────────────────────────────────────────────────────────────

def _is_bogon(ip: str) -> bool:
    return (
        ip.startswith(("10.", "127.", "0.", "169.254.", "192.168."))
        or ip.startswith("172.") and 16 <= int(ip.split(".")[1] or 0) <= 31
        or ip == "0.0.0.0"
    )


def _classify(ips, intl_set: set) -> str:
    if ips is None:
        return "timeout"
    if not ips:
        return "nxdomain"
    if any(ip in _FILTER_IPS for ip in ips):
        return "filtered"
    if any(_is_bogon(ip) for ip in ips):
        return "bogon"
    if intl_set and not (set(ips) & intl_set):
        return "differs"
    return "ok"


_TAGS = {
    "ok":       (G, "✓  clean"),
    "differs":  (Y, "≠  differs"),
    "filtered": (R, "⛔  FILTERED"),
    "bogon":    (R, "⛔  blackhole"),
    "nxdomain": (Y, "∅  no record"),
    "timeout":  (DIM, "·  timeout"),
}


def _normalize(domain: str) -> str:
    domain = domain.strip().lower()
    for scheme in ("https://", "http://"):
        if domain.startswith(scheme):
            domain = domain[len(scheme):]
            break
    domain = domain.split("/")[0]
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def run(domain: str) -> None:
    domain = _normalize(domain)
    if not domain or "." not in domain:
        sys.exit(f"{R}Invalid domain.{N}")

    print(f"\n{C}DNS  {domain}  —  poisoning check{N}")
    print(f"{DIM}querying {len(_RESOLVERS) + 1} resolvers ...{N}\n")

    # ── query everything in parallel ───────────────────────────────
    results = {}   # label -> (ips, server, group)
    with ThreadPoolExecutor(max_workers=12) as pool:
        fut = {pool.submit(_query, srv, domain): (lbl, srv, grp)
               for lbl, srv, grp in _RESOLVERS}
        fut[pool.submit(_query_system, domain)] = ("System / ISP", "—", "system")
        for f in fut:
            lbl, srv, grp = fut[f]
            try:
                results[lbl] = (f.result(), srv, grp)
            except Exception:
                results[lbl] = (None, srv, grp)

    # ── international consensus ─────────────────────────────────────
    intl_set = set()
    for lbl, (ips, srv, grp) in results.items():
        if grp == "intl" and ips:
            intl_set.update(ips)

    # ── table ───────────────────────────────────────────────────────
    print(f"  {B}{'RESOLVER':<{_COL_NAME}} {'SERVER':<{_COL_SRV}} {'ANSWER':<{_COL_RES}} STATUS{N}")
    print("  " + "─" * _W)

    order = ["System / ISP"] + [l for l, _, _ in _RESOLVERS]
    poisoned = []
    for lbl in order:
        ips, srv, grp = results.get(lbl, (None, "—", ""))
        status        = _classify(ips, intl_set)
        col, tag      = _TAGS[status]

        if ips:
            ans = ", ".join(ips)
            if len(ans) > _COL_RES - 1:
                ans = ans[:_COL_RES - 2] + "…"
        elif ips == []:
            ans = "—"
        else:
            ans = "—"

        print(f"  {lbl:<{_COL_NAME}} {srv:<{_COL_SRV}} {ans:<{_COL_RES}} {col}{tag}{N}")

        if status in ("filtered", "bogon"):
            poisoned.append((lbl, ", ".join(ips or [])))

    # ── verdict ─────────────────────────────────────────────────────
    has_filter = bool(poisoned)
    has_differ = any(
        _classify(ips, intl_set) == "differs"
        for ips, _, _ in results.values()
    )

    print(f"\n  {'═' * _W}\n")
    if has_filter:
        print(f"  {R}╔{'═' * 42}╗{N}")
        print(f"  {R}║{'⛔  DNS Poisoning Detected':^42}║{N}")
        print(f"  {R}╚{'═' * 42}╝{N}")
    elif has_differ:
        print(f"  {Y}╔{'═' * 42}╗{N}")
        print(f"  {Y}║{'≠  Inconsistent Results':^42}║{N}")
        print(f"  {Y}╚{'═' * 42}╝{N}")
        print(f"  {DIM}Answers differ across resolvers — could be a CDN,{N}")
        print(f"  {DIM}or partial filtering.{N}")
    elif intl_set:
        print(f"  {G}╔{'═' * 42}╗{N}")
        print(f"  {G}║{'✓  Clean — consistent worldwide':^42}║{N}")
        print(f"  {G}╚{'═' * 42}╝{N}")
    else:
        print(f"  {Y}No conclusive data (resolvers unreachable).{N}")

    if intl_set:
        print(f"\n  {DIM}International consensus:{N} {G}{', '.join(sorted(intl_set))}{N}")
    if poisoned:
        print(f"  {DIM}Poisoned resolvers:{N}")
        for lbl, ans in poisoned:
            print(f"    {R}·{N} {lbl:<13} → {R}{ans}{N}")
    print()


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="dns!",
        description="DNS poisoning / filtering detector — compares resolvers worldwide",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  dns! google.com\n  dns! twitter.com\n  dns! example.ir",
    )
    ap.add_argument("domain", help="Domain name to check")
    args = ap.parse_args()

    try:
        run(args.domain)
    except KeyboardInterrupt:
        print(f"\n{Y}aborted{N}")
