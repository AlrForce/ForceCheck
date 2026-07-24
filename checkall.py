"""
checkall — run info, ping, tcp, and bgp checks in parallel

Usage:
  checkall! <host> [port]        (default TCP port: 22)
"""

import sys
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from .colors import G, R, Y, C, B, DIM, N
from ._deps import ensure_deps
from .ansinfo import _resolve_to_ip, _fetch_geo
from .bgp import _api as _ripe

CHECK_HOST = "https://check-host.net"



def _chost_start(sess, endpoint: str, params: dict):
    """Start a check-host job. Returns (data, err): err is 'limit_exceeded',
    another error string, or None on success."""
    import random
    for _ in range(4):
        try:
            r = sess.get(f"{CHECK_HOST}/{endpoint}", params=params, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception:
            return None, "error"
        if data.get("error") == "limit_exceeded":
            time.sleep(1.5 + random.random() * 2.0)
            continue
        if data.get("error"):
            return None, data["error"]
        return data, None
    return None, "limit_exceeded"


def _poll(sess, request_id: str, node_count: int,
          interval: int = 2, max_tries: int = 15) -> dict:
    results = {}
    for _ in range(max_tries):
        time.sleep(interval)
        try:
            results = sess.get(f"{CHECK_HOST}/check-result/{request_id}", timeout=15).json()
        except Exception:
            continue
        if not isinstance(results, dict):
            continue
        if sum(1 for v in results.values() if v is not None) >= node_count:
            break
    return results if isinstance(results, dict) else {}



def _check_info(ip: str) -> dict:
    return _fetch_geo(ip) or {}


def _check_ping(host: str, max_nodes: int = 10) -> dict:
    import requests
    sess = requests.Session()
    sess.headers["Accept"] = "application/json"

    data, err = _chost_start(sess, "check-ping",
                             {"host": host, "max_nodes": max_nodes})
    if err == "limit_exceeded":
        return {"rate_limited": True}
    if not data:
        return {}
    nodes = data.get("nodes", {})
    if not nodes:
        return {}

    results = _poll(sess, data["request_id"], len(nodes))
    rtts, ok = [], 0
    for node in nodes:
        pings = results.get(node)
        if not pings:
            continue
        ok_pings = [p for p in (pings[0] or []) if p and p[0] == "OK"]
        if ok_pings:
            rtts.append(sum(p[1] * 1000 for p in ok_pings) / len(ok_pings))
            ok += 1

    return {
        "ok":      ok,
        "total":   len(nodes),
        "rtt_min": min(rtts) if rtts else None,
        "rtt_avg": sum(rtts) / len(rtts) if rtts else None,
        "rtt_max": max(rtts) if rtts else None,
    }


def _check_tcp(host: str, port: int = 22, max_nodes: int = 10) -> dict:
    import requests
    sess = requests.Session()
    sess.headers["Accept"] = "application/json"

    data, err = _chost_start(sess, "check-tcp",
                             {"host": f"{host}:{port}", "max_nodes": max_nodes})
    if err == "limit_exceeded":
        return {"rate_limited": True, "port": port}
    if not data:
        return {"port": port}
    nodes = data.get("nodes", {})
    if not nodes:
        return {"port": port}

    results = _poll(sess, data["request_id"], len(nodes))
    rtts, ok = [], 0
    for node in nodes:
        res = results.get(node)
        probe = res[0] if isinstance(res, list) and res and isinstance(res[0], dict) else None
        if probe and "time" in probe:
            ok += 1
            if isinstance(probe["time"], (int, float)):
                rtts.append(probe["time"] * 1000)

    return {
        "ok":      ok,
        "total":   len(nodes),
        "port":    port,
        "rtt_avg": sum(rtts) / len(rtts) if rtts else None,
    }


def _check_bgp(ip: str) -> dict:
    import requests
    sess = requests.Session()
    sess.headers.update({"Accept": "application/json"})

    d = _ripe(sess, "prefix-overview", ip, silent=True)
    if not d or not d.get("announced"):
        return {}

    asns   = d.get("asns", [])
    origin = asns[0] if asns else {}
    return {
        "prefix": d.get("resource", "—"),
        "asn":    origin.get("asn", ""),
        "holder": origin.get("holder", "—"),
    }



def _section(title: str) -> None:
    print(f"\n  {B}{title}{N}")
    print("  " + "─" * 52)


def _row(label: str, value: str) -> None:
    print(f"    {DIM}{label:<16}{N}{value}")


def _pct_color(pct: int) -> str:
    return G if pct >= 80 else (Y if pct >= 40 else R)


def _no_data(res: dict) -> None:
    if res and res.get("rate_limited"):
        print(f"    {Y}⏳  rate limited — check-host is throttling, try again{N}")
    else:
        print(f"    {Y}no data{N}")


def run(host: str, port: int = 22) -> None:
    ip = _resolve_to_ip(host)

    print(f"\n{C}CHECKALL  {host}{N}", end="")
    if ip != host.split("/")[0]:
        print(f"  {DIM}→ {ip}{N}", end="")
    print(f"\n  {'═' * 52}")
    print(f"  {DIM}running 4 checks in parallel ...{N}\n", flush=True)

    tasks = {
        "info": (_check_info, (ip,)),
        "ping": (_check_ping, (host,)),
        "tcp":  (_check_tcp,  (host, port)),
        "bgp":  (_check_bgp,  (ip,)),
    }

    results   = {}
    completed = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        future_map = {pool.submit(fn, *args): name for name, (fn, args) in tasks.items()}
        for future in as_completed(future_map):
            name = future_map[future]
            results[name] = future.result() or {}
            completed += 1
            done_names = ", ".join(results.keys())
            print(f"\r  {DIM}✓ {done_names:<36}{N} ({completed}/4)", end="", flush=True)
    print(f"\r{' ' * 60}\r", end="")

    i = results.get("info", {})
    _section("INFO")
    if i:
        _row("Country",   i.get("country") or "—")
        _row("City",      i.get("city") or "—")
        _row("ISP / Org", i.get("isp") or "—")
        _row("ASN",       f"AS{i['asn']}" if i.get("asn") else "—")
        if i.get("timezone"):
            _row("Time zone", i["timezone"])
    else:
        _no_data(i)

    p = results.get("ping", {})
    _section(f"PING  —  {p.get('total', 0)} nodes")
    if p.get("rate_limited") or not p:
        _no_data(p)
    else:
        pct = p["ok"] * 100 // p["total"] if p["total"] else 0
        _row("Reachability", f"{_pct_color(pct)}{p['ok']}/{p['total']}  ({pct}%){N}")
        if p["rtt_avg"] is not None:
            _row("RTT",
                 f"min {p['rtt_min']:.1f} ms  "
                 f"·  avg {p['rtt_avg']:.1f} ms  "
                 f"·  max {p['rtt_max']:.1f} ms")

    t = results.get("tcp", {})
    _section(f"TCP  —  port {t.get('port', port)}")
    if t.get("rate_limited") or not t.get("total"):
        _no_data(t)
    else:
        pct = t["ok"] * 100 // t["total"] if t["total"] else 0
        state = f"{G}open{N}" if t["ok"] else f"{R}closed / filtered{N}"
        _row("Port",  f"{t['port']}  ·  {state}")
        _row("Open",  f"{_pct_color(pct)}{t['ok']}/{t['total']}  ({pct}%){N}")
        if t.get("rtt_avg") is not None:
            _row("Avg RTT", f"{t['rtt_avg']:.1f} ms")

    b = results.get("bgp", {})
    _section("BGP")
    if b:
        _row("Prefix",    b.get("prefix", "—"))
        asn = b.get("asn")
        _row("Origin AS", f"AS{asn}  {DIM}({b.get('holder', '—')}){N}" if asn else "—")
    else:
        _no_data(b)

    print()


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="checkall!",
        description="Run info, ping, tcp, and bgp checks in parallel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  checkall! 8.8.8.8\n  checkall! google.com 443",
    )
    ap.add_argument("host", help="IP address or hostname")
    ap.add_argument("port", nargs="?", type=int, default=22,
                    help="TCP port to test (default: 22)")

    args = ap.parse_args()
    ensure_deps()

    if not 1 <= args.port <= 65535:
        ap.error("port must be between 1 and 65535")

    try:
        run(args.host, args.port)
    except KeyboardInterrupt:
        print(f"\n{Y}aborted{N}")
