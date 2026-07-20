"""
ping — distributed ping via check-host.net

Usage:
  ping! <host> [-n NODES]
"""

import sys
import time
import argparse

from .colors import G, R, Y, C, B, DIM, N
from ._deps import ensure_deps

CHECK_HOST = "https://check-host.net"

_COL_NODE = 36
_COL_LOC  = 26
_COL_RTT  = 9
_COL_REQ  = 5
_W        = _COL_NODE + _COL_LOC + _COL_RTT + _COL_REQ + 14


def _is_iran(info: list) -> bool:
    code = (info[0] if len(info) > 0 else "").lower()
    name = (info[1] if len(info) > 1 else "").lower()
    return code == "ir" or "iran" in name


def _header(title: str, color: str) -> None:
    print(f"\n  {color}▌ {title}{N}")
    print(f"  {B}{'NODE':<{_COL_NODE}} {'LOCATION':<{_COL_LOC}} {'RTT (ms)':>{_COL_RTT}}  {'REQ':<{_COL_REQ}}  STATUS{N}")
    print("  " + "─" * _W)


def _row(node: str, info: list, pings, full_loc: bool = True) -> bool:
    country  = info[1] if len(info) > 1 else "?"
    city     = info[2] if len(info) > 2 else "?"
    location = f"{city}, {country}" if full_loc else country
    attempts = (pings[0] or []) if pings else []
    ok_list  = [p for p in attempts if p and p[0] == "OK"]
    total_a  = len(attempts)
    ok_a     = len(ok_list)
    req_str  = f"{ok_a}/{total_a}" if total_a else "—"
    if ok_list:
        avg     = sum(p[1] * 1000 for p in ok_list) / len(ok_list)
        rtt_str = f"{avg:.1f}"
        status  = f"{G}OK{N}"
        reached = True
    else:
        rtt_str = "—"
        status  = f"{R}timeout{N}"
        reached = False
    print(f"  {node:<{_COL_NODE}} {location:<{_COL_LOC}} {rtt_str:>{_COL_RTT}}  {req_str:<{_COL_REQ}}  {status}", flush=True)
    time.sleep(0.04)
    return reached


def run(host: str, max_nodes: int = 220) -> None:
    import requests
    sess = requests.Session()
    sess.headers["Accept"] = "application/json"

    try:
        r = sess.get(
            f"{CHECK_HOST}/check-ping",
            params={"host": host, "max_nodes": max_nodes},
            timeout=15,
        )
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        sys.exit(f"{R}HTTP error:{N} {e}")
    except requests.exceptions.ConnectionError:
        sys.exit(f"{R}Cannot connect to check-host.net{N}")

    data       = r.json()
    request_id = data.get("request_id", "")
    nodes      = data.get("nodes", {})
    total      = len(nodes)

    if not nodes:
        sys.exit(f"{R}No nodes returned — check-host.net may have rejected the host.{N}")

    print(f"\n{C}PING {host}  —  check-host.net{N}")
    print(f"{DIM}{total} probe nodes  |  {CHECK_HOST}/check-report/{request_id}{N}")

    iran_nodes   = [(n, info) for n, info in nodes.items() if _is_iran(info)]
    global_nodes = [(n, info) for n, info in nodes.items() if not _is_iran(info)]

    iran_seen   = set()
    global_seen = set()
    iran_hdr    = False
    global_hdr  = False
    iran_ok = global_ok = 0

    # ── نمایش زنده ────────────────────────────────────────────────────
    for _ in range(20):
        time.sleep(1.5)
        batch = sess.get(f"{CHECK_HOST}/check-result/{request_id}", timeout=15).json()

        # ایران اول
        for node, info in iran_nodes:
            if node in iran_seen or batch.get(node) is None:
                continue
            iran_seen.add(node)
            if not iran_hdr:
                _header("IRAN", Y)
                iran_hdr = True
            if _row(node, info, batch[node]):
                iran_ok += 1

        # بعد جهانی
        for node, info in global_nodes:
            if node in global_seen or batch.get(node) is None:
                continue
            global_seen.add(node)
            if not global_hdr:
                _header("GLOBAL", C)
                global_hdr = True
            if _row(node, info, batch[node], full_loc=False):
                global_ok += 1

        if len(iran_seen) + len(global_seen) >= total:
            break

    # ── نودهایی که اصلاً جواب ندادند ─────────────────────────────────
    for node, info in iran_nodes:
        if node not in iran_seen:
            if not iran_hdr:
                _header("IRAN", Y)
                iran_hdr = True
            _row(node, info, None)

    for node, info in global_nodes:
        if node not in global_seen:
            if not global_hdr:
                _header("GLOBAL", C)
                global_hdr = True
            _row(node, info, None, full_loc=False)

    # ── نتیجه ─────────────────────────────────────────────────────────
    iran_total   = len(iran_nodes)
    global_total = len(global_nodes)
    iran_reach   = iran_ok >= 2
    global_reach = global_ok >= 5

    print(f"\n  {'═' * _W}")
    print(f"\n  {B}RESULT{N}\n")
    print(f"  {DIM}Iran    {iran_ok}/{iran_total} responded   "
          f"Global  {global_ok}/{global_total} responded{N}\n")

    if not iran_reach and global_reach:
        print(f"  {R}╔{'═' * 40}╗{N}")
        print(f"  {R}║{'⚠  This IP is Restricted  ( Filter )':^40}║{N}")
        print(f"  {R}╚{'═' * 40}╝{N}")
    elif iran_reach and not global_reach:
        print(f"  {R}╔{'═' * 40}╗{N}")
        print(f"  {R}║{'◎  This IP Is Iran Access':^40}║{N}")
        print(f"  {R}╚{'═' * 40}╝{N}")
    elif iran_reach and global_reach:
        print(f"  {G}╔{'═' * 40}╗{N}")
        print(f"  {G}║{'✓  Globally Accessible':^40}║{N}")
        print(f"  {G}╚{'═' * 40}╝{N}")
    else:
        print(f"  {R}╔{'═' * 40}╗{N}")
        print(f"  {R}║{'✗  Host Unreachable':^40}║{N}")
        print(f"  {R}╚{'═' * 40}╝{N}")

    print()


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="ping!",
        description="Distributed ping from multiple global nodes via check-host.net",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  ping! 8.8.8.8\n  ping! google.com -n 20",
    )
    ap.add_argument("host", help="IP address or hostname")
    ap.add_argument(
        "-n", "--nodes",
        type=int, default=220, metavar="N",
        help="number of probe nodes, 1-220 (default: 220)",
    )

    args = ap.parse_args()
    ensure_deps()

    if not 1 <= args.nodes <= 220:
        ap.error("--nodes must be between 1 and 220")

    try:
        run(args.host, args.nodes)
    except KeyboardInterrupt:
        print(f"\n{Y}aborted{N}")
