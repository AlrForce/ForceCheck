"""
ping — distributed ping via check-host.net

Usage:
  ping <host> [-n NODES]
"""

import sys
import time
import argparse

from .colors import G, R, Y, C, B, DIM, N
from ._deps import ensure_deps

CHECK_HOST = "https://check-host.net"


def run(host: str, max_nodes: int = 220) -> None:
    import requests
    sess = requests.Session()
    sess.headers["Accept"] = "application/json"

    # ── درخواست اولیه ────────────────────────────────────────────────────
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

    data = r.json()
    request_id = data.get("request_id", "")
    nodes = data.get("nodes", {})

    if not nodes:
        sys.exit(f"{R}No nodes returned — check-host.net may have rejected the host.{N}")

    col_node = 36
    col_loc  = 26
    col_rtt  = 9
    total    = len(nodes)

    print(f"\n{C}PING {host}  —  check-host.net{N}")
    print(f"{DIM}{total} probe nodes  |  {CHECK_HOST}/check-report/{request_id}{N}\n")
    print(f"  {B}{'NODE':<{col_node}} {'LOCATION':<{col_loc}} {'RTT (ms)':>{col_rtt}}  STATUS{N}")
    print("  " + "─" * (col_node + col_loc + col_rtt + 12))

    seen     = set()
    ok_count = 0

    for _ in range(20):
        time.sleep(2)
        r2 = sess.get(f"{CHECK_HOST}/check-result/{request_id}", timeout=15)
        results = r2.json()

        for node, pings in results.items():
            if node in seen or pings is None:
                continue
            seen.add(node)

            info     = nodes.get(node, [])
            country  = info[1] if len(info) > 1 else "?"
            city     = info[2] if len(info) > 2 else "?"
            location = f"{city}, {country}"

            attempts = pings[0] or []
            ok_pings = [p for p in attempts if p and p[0] == "OK"]
            if ok_pings:
                avg_ms   = sum(p[1] * 1000 for p in ok_pings) / len(ok_pings)
                rtt_str  = f"{avg_ms:.1f}"
                status   = f"{G}OK{N}"
                ok_count += 1
            else:
                rtt_str, status = "—", f"{R}timeout{N}"

            print(f"  {node:<{col_node}} {location:<{col_loc}} {rtt_str:>{col_rtt}}  {status}")

        if len(seen) >= total:
            break

    # نودهایی که اصلاً جواب ندادند
    for node, info in nodes.items():
        if node not in seen:
            country  = info[1] if len(info) > 1 else "?"
            city     = info[2] if len(info) > 2 else "?"
            location = f"{city}, {country}"
            print(f"  {node:<{col_node}} {location:<{col_loc}} {'—':>{col_rtt}}  {Y}no response{N}")

    pct   = ok_count * 100 // total if total else 0
    color = G if pct >= 80 else (Y if pct >= 40 else R)
    print(f"\n  {color}{ok_count}/{total} nodes responded ({pct}%){N}\n")


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="ping!",
        description="Distributed ping from multiple global nodes via check-host.net",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  ping 8.8.8.8\n  ping google.com -n 20",
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
