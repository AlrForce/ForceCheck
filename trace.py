"""
trace — distributed traceroute via check-host.net

Usage:
  trace! <host> [-n NODES]
"""

import sys
import time
import argparse

from .colors import G, R, Y, C, B, DIM, N
from ._deps import ensure_deps

CHECK_HOST = "https://check-host.net"


def run(host: str, max_nodes: int = 5) -> None:
    import requests
    sess = requests.Session()
    sess.headers["Accept"] = "application/json"

    try:
        r = sess.get(
            f"{CHECK_HOST}/check-traceroute",
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
    nodes      = data.get("nodes", {})

    if not nodes:
        sys.exit(f"{R}No nodes returned — check-host.net may have rejected the host.{N}")

    print(f"\n{C}TRACEROUTE {host}  —  check-host.net{N}")
    print(f"{DIM}{len(nodes)} probe nodes  |  {CHECK_HOST}/check-report/{request_id}{N}\n")

    # traceroute نیاز به زمان بیشتری دارد
    results: dict = {}
    for _ in range(20):
        time.sleep(3)
        r2 = sess.get(f"{CHECK_HOST}/check-result/{request_id}", timeout=15)
        results = r2.json()
        done = sum(1 for v in results.values() if v is not None)
        print(f"\r  waiting for results ... {done}/{len(nodes)}", end="", flush=True)
        if done >= len(nodes):
            break
    print("\n")

    for node, info in nodes.items():
        country  = info[1] if len(info) > 1 else "?"
        city     = info[2] if len(info) > 2 else "?"
        location = f"{city}, {country}"

        print(f"  {B}{node}{N}  {DIM}{location}{N}")

        hops_raw = results.get(node)
        if not hops_raw:
            print(f"    {Y}no result{N}\n")
            continue

        hops = hops_raw[0] if hops_raw else []
        if not hops:
            print(f"    {Y}no hops{N}\n")
            continue

        for hop in hops:
            if not hop:
                continue

            ttl      = hop[0] if len(hop) > 0 else "?"
            ip       = hop[1] if len(hop) > 1 and hop[1] else "*"
            hostname = hop[2] if len(hop) > 2 and hop[2] else ""
            rtt_raw  = hop[3] if len(hop) > 3 else None

            if rtt_raw is not None:
                rtt_str = f"{G}{rtt_raw * 1000:.1f} ms{N}"
            else:
                rtt_str = f"{R}*{N}"

            if hostname and hostname != ip:
                addr = f"{ip}  {DIM}({hostname}){N}"
            else:
                addr = ip

            print(f"    {DIM}{ttl:>2}{N}  {addr:<55}  {rtt_str}")

        print()


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="trace!",
        description="Distributed traceroute from multiple global nodes via check-host.net",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  trace! 8.8.8.8\n  trace! google.com -n 5",
    )
    ap.add_argument("host", help="IP address or hostname")
    ap.add_argument(
        "-n", "--nodes",
        type=int, default=5, metavar="N",
        help="number of probe nodes, 1-220 (default: 5)",
    )

    args = ap.parse_args()
    ensure_deps()

    if not 1 <= args.nodes <= 220:
        ap.error("--nodes must be between 1 and 220")

    try:
        run(args.host, args.nodes)
    except KeyboardInterrupt:
        print(f"\n{Y}aborted{N}")
