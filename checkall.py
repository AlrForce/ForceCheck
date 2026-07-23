"""
checkall — run ping, http, whois, and traceroute in parallel

Usage:
  checkall! <host>
"""

import sys
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from .colors import G, R, Y, C, B, DIM, N
from ._deps import ensure_deps
from .ansinfo import _resolve_to_ip, _entity_name
from .http import _http_code

CHECK_HOST = "https://check-host.net"
RDAP_IP    = "https://rdap.org/ip/{}"


# ── توابع جمع‌آوری داده ────────────────────────────────────────────────────

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
    import requests
    results = {}
    for _ in range(max_tries):
        time.sleep(interval)
        try:
            r = sess.get(f"{CHECK_HOST}/check-result/{request_id}", timeout=15)
            results = r.json()
        except Exception:
            continue
        if not isinstance(results, dict):
            continue
        if sum(1 for v in results.values() if v is not None) >= node_count:
            break
    return results if isinstance(results, dict) else {}


def _check_whois(ip: str) -> dict:
    import requests
    try:
        r = requests.get(RDAP_IP.format(ip), timeout=15,
                         headers={"Accept": "application/rdap+json"})
        r.raise_for_status()
        d = r.json()
    except Exception:
        return {}

    cidrs    = d.get("cidr0_cidrs", [])
    cidr_str = ", ".join(
        f"{c.get('v4prefix', c.get('v6prefix', '?'))}/{c.get('length', '?')}"
        for c in cidrs
    ) or "—"

    org = "—"
    for ent in d.get("entities", []):
        if any(role in ent.get("roles", []) for role in ("registrant", "administrative")):
            org = _entity_name(ent)
            for sub in ent.get("entities", []):
                if "registrant" in sub.get("roles", []):
                    org = _entity_name(sub)
            break

    return {
        "handle":  d.get("handle") or "—",
        "name":    d.get("name") or "—",
        "cidr":    cidr_str,
        "org":     org or "—",
        "country": d.get("country") or "—",
    }


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

    rtts = []
    ok   = 0
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


def _check_http(host: str, max_nodes: int = 10) -> dict:
    import requests
    url = host if host.startswith(("http://", "https://")) else f"http://{host}"
    sess = requests.Session()
    sess.headers["Accept"] = "application/json"

    data, err = _chost_start(sess, "check-http",
                             {"host": url, "max_nodes": max_nodes})
    if err == "limit_exceeded":
        return {"rate_limited": True}
    if not data:
        return {}

    nodes = data.get("nodes", {})
    if not nodes:
        return {}

    results  = _poll(sess, data["request_id"], len(nodes))
    ok       = 0
    codes: dict = {}
    times_ms = []

    for node in nodes:
        res = results.get(node)
        if not res or not res[0] or res[0][0] != 1:
            continue
        entry = res[0]
        ok   += 1
        code  = _http_code(entry)
        if code:
            codes[code] = codes.get(code, 0) + 1
        t_sec = entry[1] if len(entry) > 1 and isinstance(entry[1], (int, float)) else None
        if t_sec is not None:
            times_ms.append(float(t_sec) * 1000)

    return {
        "ok":       ok,
        "total":    len(nodes),
        "codes":    codes,
        "time_avg": sum(times_ms) / len(times_ms) if times_ms else None,
    }


def _check_trace(host: str, max_nodes: int = 3) -> dict:
    import requests
    sess = requests.Session()
    sess.headers["Accept"] = "application/json"

    data, err = _chost_start(sess, "check-traceroute",
                             {"host": host, "max_nodes": max_nodes})
    if err == "limit_exceeded":
        return {"rate_limited": True}
    if not data:
        return {}

    nodes = data.get("nodes", {})
    if not nodes:
        return {}

    results    = _poll(sess, data["request_id"], len(nodes), interval=3, max_tries=20)
    completed  = 0
    hop_counts = []

    for node in nodes:
        hops_raw = results.get(node)
        if not hops_raw:
            continue
        hops = hops_raw[0] if hops_raw else []
        if hops:
            completed += 1
            hop_counts.append(len(hops))

    return {
        "completed": completed,
        "total":     len(nodes),
        "avg_hops":  sum(hop_counts) / len(hop_counts) if hop_counts else None,
    }


# ── رندر خروجی ────────────────────────────────────────────────────────────

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


def run(host: str) -> None:
    ip = _resolve_to_ip(host)

    print(f"\n{C}CHECKALL  {host}{N}", end="")
    if ip != host.split("/")[0]:
        print(f"  {DIM}→ {ip}{N}", end="")
    print(f"\n  {'═' * 52}")
    print(f"  {DIM}running 4 checks in parallel ...{N}\n", flush=True)

    tasks = {
        "whois": (_check_whois, (ip,)),
        "ping":  (_check_ping,  (host,)),
        "http":  (_check_http,  (host,)),
        "trace": (_check_trace, (host,)),
    }

    results   = {}
    completed = [0]

    with ThreadPoolExecutor(max_workers=4) as pool:
        future_map = {pool.submit(fn, *args): name for name, (fn, args) in tasks.items()}

        for future in as_completed(future_map):
            name = future_map[future]
            results[name] = future.result() or {}
            completed[0] += 1
            done_names = ", ".join(results.keys())
            print(f"\r  {DIM}✓ {done_names:<36}{N} ({completed[0]}/4)", end="", flush=True)

    print(f"\r{' ' * 60}\r", end="")  # پاک کردن خط progress

    # ── WHOIS ──────────────────────────────────────────
    _section("WHOIS")
    w = results.get("whois", {})
    if w:
        _row("Network",      f"{w['handle']}  {DIM}({w['name']}){N}")
        _row("CIDR",         w["cidr"])
        _row("Organization", w["org"])
        _row("Country",      w["country"])
    else:
        print(f"    {Y}no data{N}")

    # ── PING ───────────────────────────────────────────
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

    # ── HTTP ───────────────────────────────────────────
    h = results.get("http", {})
    _section(f"HTTP  —  {h.get('total', 0)} nodes")
    if h.get("rate_limited") or not h:
        _no_data(h)
    else:
        pct = h["ok"] * 100 // h["total"] if h["total"] else 0
        _row("Reachability", f"{_pct_color(pct)}{h['ok']}/{h['total']}  ({pct}%){N}")
        if h["codes"]:
            codes_str = "  ".join(f"{c} ×{n}" for c, n in sorted(h["codes"].items()))
            _row("Status codes", codes_str)
        if h["time_avg"] is not None:
            _row("Avg response", f"{h['time_avg']:.0f} ms")

    # ── TRACEROUTE ─────────────────────────────────────
    t = results.get("trace", {})
    _section(f"TRACEROUTE  —  {t.get('total', 0)} nodes")
    if t.get("rate_limited") or not t:
        _no_data(t)
    else:
        pct = t["completed"] * 100 // t["total"] if t["total"] else 0
        _row("Completed", f"{_pct_color(pct)}{t['completed']}/{t['total']}{N}")
        if t["avg_hops"] is not None:
            _row("Avg hops", f"{t['avg_hops']:.0f}")

    print()


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="checkall!",
        description="Run ping, http, whois, and traceroute checks in parallel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  checkall! 8.8.8.8\n  checkall! google.com",
    )
    ap.add_argument("host", help="IP address or hostname")

    args = ap.parse_args()
    ensure_deps()

    try:
        run(args.host)
    except KeyboardInterrupt:
        print(f"\n{Y}aborted{N}")
