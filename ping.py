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
_W        = _COL_NODE + _COL_LOC + _COL_RTT + 12


def _is_iran(info: list) -> bool:
    return "iran" in (info[1] if len(info) > 1 else "").lower()


def _parse(pings) -> tuple[str, str, bool]:
    attempts = (pings[0] or []) if pings else []
    ok = [p for p in attempts if p and p[0] == "OK"]
    if ok:
        avg = sum(p[1] * 1000 for p in ok) / len(ok)
        return f"{avg:.1f}", f"{G}OK{N}", True
    return "—", f"{R}timeout{N}", False


def _header(title: str, color: str) -> None:
    print(f"\n  {color}▌ {title}{N}")
    print(f"  {B}{'NODE':<{_COL_NODE}} {'LOCATION':<{_COL_LOC}} {'RTT (ms)':>{_COL_RTT}}  STATUS{N}")
    print("  " + "─" * _W)


def _row(node: str, info: list, pings) -> bool:
    country  = info[1] if len(info) > 1 else "?"
    city     = info[2] if len(info) > 2 else "?"
    location = f"{city}, {country}"
    rtt_str, status, ok = _parse(pings)
    print(f"  {node:<{_COL_NODE}} {location:<{_COL_LOC}} {rtt_str:>{_COL_RTT}}  {status}", flush=True)
    time.sleep(0.04)
    return ok


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

    # ── جمع‌آوری نتایج ────────────────────────────────────────────────
    results: dict = {}
    for _ in range(20):
        time.sleep(2)
        r2      = sess.get(f"{CHECK_HOST}/check-result/{request_id}", timeout=15)
        results = r2.json()
        done    = sum(1 for v in results.values() if v is not None)
        print(f"\r  {DIM}collecting ... {done}/{total}{N}   ", end="", flush=True)
        if done >= total:
            break
    print(f"\r{' ' * 40}\r", end="")

    iran_nodes   = [(n, info) for n, info in nodes.items() if _is_iran(info)]
    global_nodes = [(n, info) for n, info in nodes.items() if not _is_iran(info)]

    iran_ok = iran_fail = global_ok = global_fail = 0

    # ── بخش ایران ─────────────────────────────────────────────────────
    if iran_nodes:
        _header("IRAN", Y)
        for node, info in iran_nodes:
            ok = _row(node, info, results.get(node))
            if ok:
                iran_ok += 1
            else:
                iran_fail += 1

    # ── بخش جهانی ─────────────────────────────────────────────────────
    if global_nodes:
        _header("GLOBAL", C)
        for node, info in global_nodes:
            ok = _row(node, info, results.get(node))
            if ok:
                global_ok += 1
            else:
                global_fail += 1

    # ── نتیجه ─────────────────────────────────────────────────────────
    iran_total   = len(iran_nodes)
    global_total = len(global_nodes)
    iran_reach   = iran_ok > 0
    global_reach = global_ok > 0

    print(f"\n  {'═' * _W}")
    print(f"\n  {B}RESULT{N}\n")
    print(f"  {DIM}Iran    {iran_ok}/{iran_total} responded   "
          f"Global  {global_ok}/{global_total} responded{N}\n")

    if not iran_reach and global_reach:
        print(f"  {R}╔{'═' * 40}╗{N}")
        print(f"  {R}║{'⚠  This IP is Restricted  ( Filter )':^40}║{N}")
        print(f"  {R}╚{'═' * 40}╝{N}")
    elif iran_reach and not global_reach:
        print(f"  {Y}╔{'═' * 40}╗{N}")
        print(f"  {Y}║{'◎  This IP Is Iran Access Only':^40}║{N}")
        print(f"  {Y}╚{'═' * 40}╝{N}")
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
