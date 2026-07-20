"""
trace — distributed traceroute via check-host.net

Usage:
  trace! <host> [--iran | --global | --world]
"""

import sys
import time
import random
import argparse

from .colors import G, R, Y, C, B, DIM, N
from ._deps import ensure_deps

CHECK_HOST = "https://check-host.net"

_MODES = {
    "iran":   {"label": "Iran Trace",   "count": 4},
    "global": {"label": "Global Trace", "count": 4},
    "world":  {"label": "World Trace",  "count": 8},
}


def _loc_of(info):
    """Return the [code, country, city] location list from any node-info shape.

    Handles:
      - list/tuple  ["ir", "Iran", "Qom", ...]        (check-ping / traceroute)
      - dict        {"location": ["ir", "Iran", ...]}  (/nodes/hosts)
    """
    if isinstance(info, (list, tuple)):
        return list(info)
    if isinstance(info, dict):
        loc = info.get("location")
        if isinstance(loc, (list, tuple)):
            return list(loc)
        return [info.get("country", ""), info.get("country_name", "")]
    return []


def _country_of(info) -> str:
    loc = _loc_of(info)
    return str(loc[1]) if len(loc) > 1 else ""


def _is_iran(info) -> bool:
    loc  = _loc_of(info)
    code = str(loc[0]).lower() if len(loc) > 0 else ""
    name = str(loc[1]).lower() if len(loc) > 1 else ""
    return code == "ir" or "iran" in name


def _get_filtered_nodes(region: str, count: int) -> list:
    import requests
    try:
        r = requests.get(
            f"{CHECK_HOST}/nodes/hosts",
            headers={"Accept": "application/json"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        # some API responses wrap nodes under a "nodes" key
        all_nodes = data.get("nodes", data) if isinstance(data, dict) else {}
    except Exception:
        return []

    if region == "iran":
        filtered = [nid for nid, info in all_nodes.items() if _is_iran(info)]
    elif region == "global":
        filtered = [nid for nid, info in all_nodes.items() if not _is_iran(info)]
    else:
        filtered = list(all_nodes.keys())

    random.shuffle(filtered)
    return filtered[:count]


def ask_mode() -> str:
    print(f"\n  {B}1{N}  🇮🇷  Iran Trace     {DIM}· 4 nodes from Iran{N}")
    print(f"  {B}2{N}  🌐  Global Trace   {DIM}· 4 international nodes{N}")
    print(f"  {B}3{N}  🗺   World Trace    {DIM}· 8 worldwide nodes{N}")
    try:
        raw = input(f"\n  {C}Mode:{N} ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""
    return {"1": "iran", "2": "global", "3": "world"}.get(raw, "")


def run(host: str, mode: str = "world") -> None:
    import requests

    cfg   = _MODES.get(mode, _MODES["world"])
    label = cfg["label"]
    count = cfg["count"]

    print(f"\n  {DIM}Fetching {label} nodes ...{N}", end="", flush=True)
    node_list = _get_filtered_nodes(mode, count)

    if not node_list:
        print(f"\r  {R}Failed to fetch node list from check-host.net{N}          ")
        return

    print(f"\r  {DIM}Using {len(node_list)} nodes  [{label}]{N}          ")

    sess = requests.Session()
    sess.headers["Accept"] = "application/json"

    try:
        params = [("host", host)] + [("node", n) for n in node_list]
        r = sess.get(f"{CHECK_HOST}/check-traceroute", params=params, timeout=15)
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

    print(f"\n{C}TRACEROUTE {host}  —  {label}{N}")
    print(f"{DIM}{len(nodes)} probe nodes  |  {CHECK_HOST}/check-report/{request_id}{N}\n")

    results: dict = {}
    for _ in range(20):
        time.sleep(3)
        try:
            r2      = sess.get(f"{CHECK_HOST}/check-result/{request_id}", timeout=15)
            results = r2.json()
        except Exception:
            continue
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

        for ttl, hop in enumerate(hops, 1):
            if not hop:
                print(f"    {DIM}{ttl:>2}{N}  {'*':<55}  {R}*{N}")
                continue

            if isinstance(hop, list):
                probe = hop[0] if hop else None
            elif isinstance(hop, dict):
                probe = hop
            else:
                continue

            if not probe:
                print(f"    {DIM}{ttl:>2}{N}  {'*':<55}  {R}*{N}")
                continue

            if isinstance(probe, dict):
                ip       = probe.get("host") or "*"
                hostname = probe.get("name") or ""
                rtt_raw  = probe.get("rtt")
            else:
                ip       = probe[1] if len(probe) > 1 and probe[1] else "*"
                hostname = probe[2] if len(probe) > 2 and probe[2] else ""
                rtt_raw  = probe[3] if len(probe) > 3 else None

            rtt_str = f"{G}{rtt_raw * 1000:.1f} ms{N}" if rtt_raw is not None else f"{R}*{N}"
            addr    = f"{ip}  {DIM}({hostname}){N}" if hostname and hostname != ip else ip

            print(f"    {DIM}{ttl:>2}{N}  {addr:<55}  {rtt_str}")

        print()


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="trace!",
        description="Distributed traceroute from multiple nodes via check-host.net",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  trace! 8.8.8.8            (interactive mode selection)\n"
            "  trace! 8.8.8.8 --iran\n"
            "  trace! 8.8.8.8 --global\n"
            "  trace! 8.8.8.8 --world"
        ),
    )
    ap.add_argument("host", help="IP address or hostname")

    mg = ap.add_mutually_exclusive_group()
    mg.add_argument("--iran",   action="store_true", help="4 nodes from Iran")
    mg.add_argument("--global", action="store_true", dest="global_",
                    help="4 international nodes")
    mg.add_argument("--world",  action="store_true", help="8 worldwide nodes")

    args = ap.parse_args()
    ensure_deps()

    if args.iran:
        mode = "iran"
    elif args.global_:
        mode = "global"
    elif args.world:
        mode = "world"
    else:
        mode = ask_mode()
        if not mode:
            return

    try:
        run(args.host, mode)
    except KeyboardInterrupt:
        print(f"\n{Y}aborted{N}")
