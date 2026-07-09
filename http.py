"""
http — distributed HTTP check via check-host.net

Usage:
  http! <url> [-n NODES]
"""

import sys
import time
import argparse

from .colors import G, R, Y, C, B, DIM, N
from ._deps import ensure_deps

CHECK_HOST = "https://check-host.net"

# رنگ‌بندی بر اساس HTTP status code
def _status_color(code: int) -> str:
    if 200 <= code < 300:
        return G
    if 300 <= code < 400:
        return Y
    return R


def run(host: str, max_nodes: int = 10) -> None:
    import requests
    sess = requests.Session()
    sess.headers["Accept"] = "application/json"

    try:
        r = sess.get(
            f"{CHECK_HOST}/check-http",
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

    if not nodes:
        sys.exit(f"{R}No nodes returned — check-host.net may have rejected the host.{N}")

    print(f"\n{C}HTTP {host}  —  check-host.net{N}")
    print(f"{DIM}{len(nodes)} probe nodes  |  {CHECK_HOST}/check-report/{request_id}{N}\n")

    results: dict = {}
    for _ in range(15):
        time.sleep(2)
        r2 = sess.get(f"{CHECK_HOST}/check-result/{request_id}", timeout=15)
        results = r2.json()
        done = sum(1 for v in results.values() if v is not None)
        print(f"\r  waiting for results ... {done}/{len(nodes)}", end="", flush=True)
        if done >= len(nodes):
            break
    print()

    col_node = 36
    col_loc  = 26
    col_ip   = 17
    col_time = 10

    print(f"\n  {B}{'NODE':<{col_node}} {'LOCATION':<{col_loc}} {'RESOLVED IP':<{col_ip}} {'TIME (ms)':>{col_time}}  STATUS{N}")
    print("  " + "─" * (col_node + col_loc + col_ip + col_time + 12))

    ok_count = 0
    for node, info in nodes.items():
        country  = info[1] if len(info) > 1 else "?"
        city     = info[2] if len(info) > 2 else "?"
        location = f"{city}, {country}"

        res = results.get(node)
        if not res:
            print(f"  {node:<{col_node}} {location:<{col_loc}} {'—':<{col_ip}} {'—':>{col_time}}  {Y}pending{N}")
            continue

        entry = res[0] if res else None

        # فرمت پاسخ: [status_str, status_code, time_sec, resolved_ip]
        if not entry or entry[0] != "OK":
            err = entry[0] if entry else "error"
            print(f"  {node:<{col_node}} {location:<{col_loc}} {'—':<{col_ip}} {'—':>{col_time}}  {R}{err}{N}")
            continue

        code     = entry[1] if len(entry) > 1 else 0
        time_sec = entry[2] if len(entry) > 2 else None
        ip       = entry[3] if len(entry) > 3 and entry[3] else "—"

        time_str = f"{time_sec * 1000:.0f}" if time_sec is not None else "—"
        sc       = _status_color(code)

        print(f"  {node:<{col_node}} {location:<{col_loc}} {ip:<{col_ip}} {time_str:>{col_time}}  {sc}{code}{N}")
        ok_count += 1

    total = len(nodes)
    pct   = ok_count * 100 // total if total else 0
    color = G if pct >= 80 else (Y if pct >= 40 else R)
    print(f"\n  {color}{ok_count}/{total} nodes reached ({pct}%){N}\n")


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="http!",
        description="Distributed HTTP check from multiple global nodes via check-host.net",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  http! https://example.com\n  http! http://1.1.1.1 -n 20",
    )
    ap.add_argument("host", help="URL to check (http:// or https://)")
    ap.add_argument(
        "-n", "--nodes",
        type=int, default=10, metavar="N",
        help="number of probe nodes, 1-220 (default: 10)",
    )

    args = ap.parse_args()
    ensure_deps()

    if not 1 <= args.nodes <= 220:
        ap.error("--nodes must be between 1 and 220")

    try:
        run(args.host, args.nodes)
    except KeyboardInterrupt:
        print(f"\n{Y}aborted{N}")
