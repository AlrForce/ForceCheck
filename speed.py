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


# ── helpers ─────────────────────────────────────────────────────────────────

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
    # Cloudflare caps a single __down request, so pull moderate chunks
    # back-to-back until the time window is filled.
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
                if per > 2_000_000:      # back off if the size is rejected
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


# ── entry ───────────────────────────────────────────────────────────────────

def run(max_secs: float = 12.0) -> None:
    import requests

    sess = requests.Session()
    sess.headers["User-Agent"] = "ForceCheck-speed"

    print(f"\n{C}SPEED TEST  —  Cloudflare{N}")
    tr = _trace(sess)
    if tr.get("ip"):
        colo = tr.get("colo", "?")
        loc  = tr.get("loc", "?")
        print(f"{DIM}server {colo}  ·  your IP {tr['ip']}  ({loc}){N}\n")
    else:
        print(f"{DIM}measuring …{N}\n")

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
        epilog="Examples:\n  speed!\n  speed! --time 8",
    )
    ap.add_argument("--time", type=float, default=12.0, metavar="SEC",
                    help="download/upload window in seconds (default: 12)")
    args = ap.parse_args()
    ensure_deps()

    secs = max(3.0, min(30.0, args.time))
    try:
        run(secs)
    except KeyboardInterrupt:
        print(f"\n{Y}aborted{N}")
