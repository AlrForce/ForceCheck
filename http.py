"""
http — distributed HTTP check via check-host.net

Usage:
  http! <url> [-n NODES]
"""

import sys
import time
import argparse

from .colors import G, R, Y, C, B, DIM, N, loader
from ._deps import ensure_deps

CHECK_HOST = "https://check-host.net"

_COL_NODE = 36
_COL_LOC  = 26
_COL_CODE = 6
_COL_TIME = 10
_W        = _COL_NODE + _COL_LOC + _COL_CODE + _COL_TIME + 12


def _is_iran(info: list) -> bool:
    code = (info[0] if len(info) > 0 else "").lower()
    name = (info[1] if len(info) > 1 else "").lower()
    return code == "ir" or "iran" in name


def _http_code(entry) -> int:
    """Find the HTTP status code anywhere in a check-host result entry.

    Format is [1, time, "Reason", "301", "ip"] — the code is a numeric
    string (entry[3]), not entry[2] which is the reason phrase.
    """
    for x in entry:
        if isinstance(x, bool):
            continue
        if isinstance(x, int) and 100 <= x <= 599:
            return x
        if isinstance(x, str):
            for tok in x.replace("/", " ").split():
                if tok.isdigit() and 100 <= int(tok) <= 599:
                    return int(tok)
    return 0


def _code_color(code: int) -> str:
    if 200 <= code < 300:
        return G
    if 300 <= code < 400:
        return Y
    return R


def _header(title: str, color: str) -> None:
    print(f"\n  {color}▌ {title}{N}")
    print(f"  {B}{'NODE':<{_COL_NODE}} {'LOCATION':<{_COL_LOC}} {'CODE':>{_COL_CODE}} {'TIME (s)':>{_COL_TIME}}  STATUS{N}")
    print("  " + "─" * _W)


def _row(node: str, info: list, res, full_loc: bool = True) -> bool:
    country  = info[1] if len(info) > 1 else "?"
    city     = info[2] if len(info) > 2 else "?"
    location = f"{city}, {country}" if full_loc else country

    entry = res[0] if res else None

    if not entry or entry[0] != 1:
        err_raw = entry[1] if entry and len(entry) > 1 else "timeout"
        err     = str(err_raw)[:18] if isinstance(err_raw, str) else "timeout"
        print(f"  {node:<{_COL_NODE}} {location:<{_COL_LOC}} {R}{'—':>{_COL_CODE}}{N} {'—':>{_COL_TIME}}  {R}{err}{N}", flush=True)
        time.sleep(0.04)
        return False

    time_sec = entry[1] if len(entry) > 1 and isinstance(entry[1], (int, float)) else None
    code     = _http_code(entry)

    try:
        time_str = f"{float(time_sec):.2f}s"
    except (TypeError, ValueError):
        time_str = "—"

    if code:
        sc        = _code_color(code)
        code_disp = str(code)
    else:
        sc        = DIM
        code_disp = "—"

    status = f"{G}OK{N}" if (not code or 200 <= code < 400) else f"{Y}{code}{N}"
    print(f"  {node:<{_COL_NODE}} {location:<{_COL_LOC}} {sc}{code_disp:>{_COL_CODE}}{N} {time_str:>{_COL_TIME}}  {status}", flush=True)
    time.sleep(0.04)
    return (200 <= code < 400) if code else True


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

    data = r.json()
    if data.get("error"):
        if data["error"] == "limit_exceeded":
            sys.exit(f"{Y}⏳  Rate limited by check-host.net — wait ~30s and try again.{N}")
        sys.exit(f"{R}check-host.net error:{N} {data['error']}")

    request_id = data.get("request_id", "")
    nodes      = data.get("nodes", {})
    total      = len(nodes)

    if not nodes:
        sys.exit(f"{R}No nodes returned — check-host.net may have rejected the host.{N}")

    print(f"\n{C}HTTP {host}  —  check-host.net{N}")
    print(f"{DIM}{total} probe nodes  |  {CHECK_HOST}/check-report/{request_id}{N}")

    iran_nodes   = [(n, info) for n, info in nodes.items() if _is_iran(info)]
    global_nodes = [(n, info) for n, info in nodes.items() if not _is_iran(info)]

    results = loader(
        lambda: sess.get(f"{CHECK_HOST}/check-result/{request_id}", timeout=15).json(),
        total, label="checking servers",
    )

    iran_ok = global_ok = 0
    for title, color, group, full in (
        ("IRAN", Y, iran_nodes, True), ("GLOBAL", C, global_nodes, False)
    ):
        if not group:
            continue
        _header(title, color)
        for node, info in group:
            if _row(node, info, results.get(node), full_loc=full):
                if title == "IRAN":
                    iran_ok += 1
                else:
                    global_ok += 1

    iran_total   = len(iran_nodes)
    global_total = len(global_nodes)
    ok_count     = iran_ok + global_ok

    print(f"\n  {'═' * _W}")
    print(f"\n  {B}RESULT{N}\n")
    print(f"  {DIM}Iran    {iran_ok}/{iran_total} reached   "
          f"Global  {global_ok}/{global_total} reached{N}\n")

    pct   = ok_count * 100 // total if total else 0
    color = G if pct >= 80 else (Y if pct >= 40 else R)
    print(f"  {color}{ok_count}/{total} nodes reached ({pct}%){N}\n")


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
