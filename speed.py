"""
speed — internet speed test (download / upload / latency) via Cloudflare.

Uses Cloudflare's public speed endpoints (no API key, reachable from most
networks). Time-boxed measurement with a warm-up for steady-state rates.

Usage:
  speed!               full test (latency + download + upload)
  speed! --time 8      set the download/upload window in seconds
"""

import sys
import time
import argparse

from .colors import G, R, Y, C, B, DIM, N
from ._deps import ensure_deps

CF = "https://speed.cloudflare.com"



def _trace(sess) -> dict:
    try:
        text = sess.get(f"{CF}/cdn-cgi/trace", timeout=8).text
        return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)
    except Exception:
        return {}


def _progress(label: str, mbps: float) -> None:
    print(f"\r  {DIM}testing {label:<8}…{N}  {C}{mbps:7.1f}{N} {DIM}Mbps{N}   ",
          end="", flush=True)


def _clear() -> None:
    print("\r" + " " * 44 + "\r", end="", flush=True)


def _latency(sess, n: int = 12):
    """Return (min_ms, jitter_ms) from small round-trips over a kept-alive conn."""
    times = []
    for _ in range(n):
        t = time.perf_counter()
        try:
            sess.get(f"{CF}/__down?bytes=0", timeout=5).content
            times.append((time.perf_counter() - t) * 1000)
        except Exception:
            continue
    if not times:
        return None, None
    times.sort()
    jitter = (sum(abs(times[i] - times[i - 1]) for i in range(1, len(times)))
              / (len(times) - 1)) if len(times) > 1 else 0.0
    return times[0], jitter


def _download(sess, max_secs: float = 12.0):
    chunk = 1 << 16
    per   = 25_000_000
    start = time.perf_counter()
    total = 0
    last  = 0.0
    now   = start
    try:
        while now - start < max_secs:
            r = sess.get(f"{CF}/__down?bytes={per}", stream=True,
                         timeout=max_secs + 15)
            if r.status_code != 200:
                r.close()
                if per > 2_000_000:
                    per //= 2
                    continue
                break
            for data in r.iter_content(chunk_size=chunk):
                total += len(data)
                now = time.perf_counter()
                if now - last > 0.15:
                    el = now - start
                    if el > 0:
                        _progress("download", total * 8 / el / 1e6)
                    last = now
                if now - start >= max_secs:
                    break
            r.close()
            now = time.perf_counter()
    except Exception:
        pass

    el = time.perf_counter() - start
    return total * 8 / el / 1e6 if el > 0 and total else None


def _upload(sess, max_secs: float = 10.0):
    chunk = 1 << 16
    buf   = b"\x00" * chunk
    start = time.perf_counter()
    sent  = [0]
    last  = [0.0]

    def gen():
        while True:
            now = time.perf_counter()
            if now - start >= max_secs:
                return
            sent[0] += chunk
            if now - last[0] > 0.15:
                if now > start:
                    _progress("upload", sent[0] * 8 / (now - start) / 1e6)
                last[0] = now
            yield buf

    try:
        sess.post(f"{CF}/__up", data=gen(), timeout=max_secs + 15,
                  headers={"Content-Type": "application/octet-stream"})
    except Exception:
        pass
    el = time.perf_counter() - start
    return sent[0] * 8 / el / 1e6 if el > 0 and sent[0] else None


def _fmt(mbps) -> str:
    if mbps is None:
        return f"{R}failed{N}"
    if mbps >= 1000:
        return f"{G}{mbps / 1000:.2f}{N} {DIM}Gbps{N}"
    return f"{G}{mbps:.1f}{N} {DIM}Mbps{N}"



def _local_ips() -> list:
    import socket
    seen, out = set(), []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if not ip.startswith(("127.", "169.254.")):
            seen.add(ip); out.append(ip)
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            if info[0] == socket.AF_INET:
                ip = info[4][0]
                if ip not in seen and not ip.startswith(("127.", "169.254.")):
                    seen.add(ip); out.append(ip)
    except Exception:
        pass
    return out[:6]


def _bind_source(sess, ip: str) -> None:
    """Force every request to leave from a specific local IP / interface."""
    from requests.adapters import HTTPAdapter

    class _SrcAdapter(HTTPAdapter):
        def init_poolmanager(self, connections, maxsize, block=False, **kw):
            kw["source_address"] = (ip, 0)
            super().init_poolmanager(connections, maxsize, block, **kw)

    sess.mount("http://", _SrcAdapter())
    sess.mount("https://", _SrcAdapter())



def run(max_secs: float = 12.0, source_ip: str = None) -> None:
    import requests

    if source_ip is None:
        ips = _local_ips()
        if len(ips) > 1 and sys.stdin.isatty():
            print(f"\n{C}SPEED TEST{N}  {DIM}·  choose interface to test from{N}")
            for i, ip in enumerate(ips, 1):
                tag = f"  {DIM}← primary{N}" if i == 1 else ""
                print(f"  {C}{i}{N}  {ip}{tag}")
            try:
                raw = input(f"\n  {DIM}Interface [Enter = auto]:{N} ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if raw.isdigit() and 1 <= int(raw) <= len(ips):
                source_ip = ips[int(raw) - 1]

    sess = requests.Session()
    sess.trust_env = False
    sess.headers["User-Agent"] = "ForceCheck-speed"
    if source_ip:
        _bind_source(sess, source_ip)

    print(f"\n{C}SPEED TEST  —  Cloudflare{N}")
    tr = _trace(sess)
    src = f"  ·  from {source_ip}" if source_ip else ""
    if tr.get("ip"):
        colo = tr.get("colo", "?")
        loc  = tr.get("loc", "?")
        print(f"{DIM}server {colo}  ·  egress {tr['ip']}  ({loc}){src}{N}\n")
    else:
        print(f"{DIM}measuring …{src}{N}\n")

    _progress("latency", 0.0)
    latency, jitter = _latency(sess)

    down = _download(sess, max_secs)
    up   = _upload(sess, max_secs)
    _clear()

    lat_str = (f"{G}{latency:.1f}{N} {DIM}ms{N}  {DIM}(jitter {jitter:.1f} ms){N}"
               if latency is not None else f"{R}failed{N}")

    w = 40
    print(f"  {C}╔{'═' * w}╗{N}")
    print(f"  {C}║{'  Speed Test Results':<{w}}║{N}")
    print(f"  {C}╚{'═' * w}╝{N}\n")
    print(f"  {DIM}Latency {N}  {lat_str}")
    print(f"  {DIM}Download{N}  {_fmt(down)}")
    print(f"  {DIM}Upload  {N}  {_fmt(up)}")
    if tr.get("colo"):
        print(f"\n  {DIM}via Cloudflare {tr['colo']}{N}")
    print()


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="speed!",
        description="Internet speed test (download / upload / latency) via Cloudflare.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  speed!\n  speed! --time 8\n  speed! --interface 1.2.3.4",
    )
    ap.add_argument("--time", type=float, default=12.0, metavar="SEC",
                    help="download/upload window in seconds (default: 12)")
    ap.add_argument("--interface", "-i", metavar="IP", default=None,
                    help="local IP / interface to test from (skip the prompt)")
    args = ap.parse_args()
    ensure_deps()

    secs = max(3.0, min(30.0, args.time))
    try:
        run(secs, args.interface)
    except KeyboardInterrupt:
        print(f"\n{Y}aborted{N}")
