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

_COL_NODE = 36
_COL_LOC  = 20
_COL_CODE = 6
_COL_TIME = 10
_W        = _COL_NODE + _COL_LOC + _COL_CODE + _COL_TIME + 12


def _code_color(code: int) -> str:
    if 200 <= code < 300:
        return G
    if 300 <= code < 400:
        return Y
    return R


def _header() -> None:
    print(f"  {B}{'NODE':<{_COL_NODE}} {'LOCATION':<{_COL_LOC}} {'CODE':>{_COL_CODE}} {'TIME (s)':>{_COL_TIME}}  STATUS{N}")
    print("  " + "─" * _W)


def _row(node: str, info: list, res) -> bool:
    # فقط اسم کشور
    country = info[1] if len(info) > 1 else "?"

    # فرمت check-host.net: [1, "200 OK", time_sec, "ip"] یا [0, "error msg"]
    entry = res[0] if res else None

    if not entry or entry[0] != 1:
        # entry[1] میتواند string پیام خطا یا float باشد
        err_raw = entry[1] if entry and len(entry) > 1 else "timeout"
        err     = str(err_raw)[:18] if isinstance(err_raw, str) else "timeout"
        print(f"  {node:<{_COL_NODE}} {country:<{_COL_LOC}} {'—':>{_COL_CODE}} {'—':>{_COL_TIME}}  {R}{err}{N}", flush=True)
        time.sleep(0.04)
        return False

    # فرمت موفق: [1, http_code_int, time_float, "ip"]
    code     = entry[1] if len(entry) > 1 else 0
    time_sec = entry[2] if len(entry) > 2 else None
    try:
        time_str = f"{float(time_sec):.2f}s"
    except (TypeError, ValueError):
        time_str = "—"

    sc = _code_color(code if isinstance(code, int) else 0)
    print(f"  {node:<{_COL_NODE}} {country:<{_COL_LOC}} {sc}{code:>{_COL_CODE}}{N} {time_str:>{_COL_TIME}}  {G}OK{N}", flush=True)
    time.sleep(0.04)
    return isinstance(code, int) and 200 <= code < 400


def run(host: str, max_nodes: int = 220) -> None:
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
    total      = len(nodes)

    if not nodes:
        sys.exit(f"{R}No nodes returned — check-host.net may have rejected the host.{N}")

    print(f"\n{C}HTTP {host}  —  check-host.net{N}")
    print(f"{DIM}{total} probe nodes  |  {CHECK_HOST}/check-report/{request_id}{N}\n")
    _header()

    seen     = set()
    ok_count = 0

    for _ in range(20):
        time.sleep(1.5)
        batch = sess.get(f"{CHECK_HOST}/check-result/{request_id}", timeout=15).json()

        for node, info in nodes.items():
            if node in seen or batch.get(node) is None:
                continue
            seen.add(node)
            if _row(node, info, batch[node]):
                ok_count += 1

        if len(seen) >= total:
            break

    # نودهایی که جواب ندادند
    for node, info in nodes.items():
        if node not in seen:
            _row(node, info, None)

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
