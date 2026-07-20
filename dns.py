"""
dns — find the best DNS resolver for your server and set it system-wide.

Benchmarks well-known resolvers (Iranian anti-sanction + international) by
latency and by real access to the outside world (resolve + TCP-connect to
popular sites), ranks them, and lets you apply the winner to your OS.

Usage:
  dns!                 benchmark, then optionally set the best one
  dns! --apply-best    benchmark and auto-apply the top resolver
  dns! --list          benchmark only (never change system DNS)
"""

import os
import sys
import time
import socket
import struct
import random
import argparse
import platform
import subprocess
from concurrent.futures import ThreadPoolExecutor

from .colors import G, R, Y, C, B, DIM, N

# (label, [primary, secondary])
_CANDIDATES = [
    ("Shecan",     ["178.22.122.100", "185.51.200.2"]),
    ("Electro",    ["78.157.42.100",  "78.157.42.101"]),
    ("Radar",      ["10.202.10.10",   "10.202.10.11"]),
    ("403.online", ["10.202.10.202",  "10.202.10.102"]),
    ("Begzar",     ["185.55.226.26",  "185.55.225.25"]),
    ("Shatel",     ["85.15.1.14",     "85.15.1.15"]),
    ("Pishgaman",  ["5.202.100.100",  "5.202.100.101"]),
    ("Google",     ["8.8.8.8",        "8.8.4.4"]),
    ("Cloudflare", ["1.1.1.1",        "1.0.0.1"]),
    ("Quad9",      ["9.9.9.9",        "149.112.112.112"]),
    ("OpenDNS",    ["208.67.222.222", "208.67.220.220"]),
    ("AdGuard",    ["94.140.14.14",   "94.140.15.15"]),
]

# Sites that matter for "access to the outside" — often filtered/sanctioned.
_TEST_DOMAINS = [
    "google.com",
    "github.com",
    "youtube.com",
    "dl.google.com",
    "registry.npmjs.org",
]

_FILTER_IPS = {"10.10.34.34", "10.10.34.35", "10.10.34.36"}


# ── minimal DNS over UDP (no dependencies) ─────────────────────────────────

def _build_query(domain: str, qid: int) -> bytes:
    header = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0)
    q = b""
    for label in domain.split("."):
        if not label:
            continue
        q += bytes([len(label)]) + label.encode("idna")
    q += b"\x00"
    q += struct.pack(">HH", 1, 1)  # QTYPE=A, QCLASS=IN
    return header + q


def _skip_name(data: bytes, offset: int) -> int:
    while offset < len(data):
        length = data[offset]
        if length == 0:
            return offset + 1
        if length & 0xC0 == 0xC0:
            return offset + 2
        offset += 1 + length
    return offset


def _query(server: str, domain: str, timeout: float = 2.0):
    """Return list of A-record IPs, [] for no answer, or None on timeout."""
    qid    = random.randint(0, 0xFFFF)
    packet = _build_query(domain, qid)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(packet, (server, 53))
        data, _ = s.recvfrom(1024)
    except Exception:
        return None
    finally:
        s.close()

    if len(data) < 12:
        return []
    _, flags, qd, an, _, _ = struct.unpack(">HHHHHH", data[:12])
    if flags & 0x000F != 0:
        return []
    offset = 12
    for _ in range(qd):
        offset = _skip_name(data, offset) + 4
    ips = []
    for _ in range(an):
        offset = _skip_name(data, offset)
        if offset + 10 > len(data):
            break
        rtype, _, _, rdlen = struct.unpack(">HHIH", data[offset:offset + 10])
        offset += 10
        rdata = data[offset:offset + rdlen]
        offset += rdlen
        if rtype == 1 and rdlen == 4:
            ips.append(".".join(str(b) for b in rdata))
    return ips


# ── scoring helpers ────────────────────────────────────────────────────────

def _is_bogon(ip: str) -> bool:
    parts = ip.split(".")
    return (
        ip.startswith(("10.", "127.", "0.", "169.254.", "192.168."))
        or (ip.startswith("172.") and len(parts) > 1 and parts[1].isdigit()
            and 16 <= int(parts[1]) <= 31)
        or ip in _FILTER_IPS
    )


def _can_reach(ip: str, port: int = 443, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False


def _benchmark(label: str, ips: list) -> dict:
    server = ips[0]

    # latency — best of two lightweight queries
    samples = []
    for _ in range(2):
        start = time.perf_counter()
        r = _query(server, "cloudflare.com")
        if r is not None:
            samples.append((time.perf_counter() - start) * 1000)
    if not samples:
        return {"label": label, "ips": ips, "reachable": False}

    latency = min(samples)

    # access — resolve each test domain and actually connect to it
    access = 0
    for dom in _TEST_DOMAINS:
        answer = _query(server, dom)
        if not answer:
            continue
        good = [ip for ip in answer if not _is_bogon(ip)]
        if good and _can_reach(good[0]):
            access += 1

    return {
        "label":     label,
        "ips":       ips,
        "server":    server,
        "reachable": True,
        "latency":   latency,
        "access":    access,
        "total":     len(_TEST_DOMAINS),
    }


# ── OS integration ─────────────────────────────────────────────────────────

def _set_dns_linux(primary: str, secondary: str):
    path, backup = "/etc/resolv.conf", "/etc/resolv.conf.forcecheck.bak"
    note = ""
    if os.path.islink(path):
        note = "resolv.conf is managed (systemd-resolved/NetworkManager); may reset on reboot."
    try:
        import shutil
        if os.path.exists(path) and not os.path.exists(backup) and not os.path.islink(path):
            shutil.copy2(path, backup)
        with open(path, "w") as f:
            f.write("# Set by ForceCheck\n")
            f.write(f"nameserver {primary}\n")
            if secondary:
                f.write(f"nameserver {secondary}\n")
        return True, note
    except PermissionError:
        return False, "permission"
    except Exception as e:
        return False, str(e)


def _set_dns_windows(primary: str, secondary: str):
    try:
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():
            return False, "admin"
    except Exception:
        pass
    try:
        alias = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             "Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | "
             "Sort-Object -Property InterfaceMetric | "
             "Select-Object -First 1 -ExpandProperty Name"],
            text=True, timeout=15,
        ).strip()
        if not alias:
            return False, "no active network adapter found"
        subprocess.run(["netsh", "interface", "ipv4", "set", "dnsservers",
                        f"name={alias}", "static", primary, "primary"],
                       check=True, capture_output=True, timeout=15)
        if secondary:
            subprocess.run(["netsh", "interface", "ipv4", "add", "dnsservers",
                            f"name={alias}", secondary, "index=2"],
                           check=True, capture_output=True, timeout=15)
        return True, f"adapter: {alias}"
    except subprocess.CalledProcessError as e:
        return False, (e.stderr or str(e)).strip()
    except Exception as e:
        return False, str(e)


def _set_dns_macos(primary: str, secondary: str):
    try:
        services = subprocess.check_output(
            ["networksetup", "-listallnetworkservices"], text=True, timeout=10
        ).splitlines()[1:]
        svc = next((s for s in services if s.lower() in ("wi-fi", "ethernet")),
                   services[0] if services else None)
        if not svc:
            return False, "no network service found"
        subprocess.run(["networksetup", "-setdnsservers", svc, primary,
                        secondary or "empty"], check=True, capture_output=True, timeout=10)
        return True, f"service: {svc}"
    except subprocess.CalledProcessError as e:
        return False, (e.stderr or str(e)).strip()
    except Exception as e:
        return False, str(e)


def _apply_dns(primary: str, secondary: str):
    system = platform.system()
    if system == "Linux":
        return _set_dns_linux(primary, secondary)
    if system == "Windows":
        return _set_dns_windows(primary, secondary)
    if system == "Darwin":
        return _set_dns_macos(primary, secondary)
    return False, f"unsupported OS: {system}"


def _manual_hint(primary: str, secondary: str) -> None:
    system = platform.system()
    print(f"\n  {DIM}Set it manually:{N}")
    if system == "Windows":
        print(f"    Run PowerShell/cmd as Administrator, then:")
        print(f"    {C}netsh interface ipv4 set dnsservers \"Ethernet\" static {primary} primary{N}")
        if secondary:
            print(f"    {C}netsh interface ipv4 add dnsservers \"Ethernet\" {secondary} index=2{N}")
    elif system == "Darwin":
        print(f"    {C}networksetup -setdnsservers Wi-Fi {primary} {secondary}{N}")
    else:
        print(f"    {C}sudo tee /etc/resolv.conf <<EOF{N}")
        print(f"    nameserver {primary}")
        if secondary:
            print(f"    nameserver {secondary}")
        print(f"    {C}EOF{N}")


# ── rendering ───────────────────────────────────────────────────────────────

_COL_NUM  = 3
_COL_NAME = 12
_COL_SRV  = 17
_COL_ACC  = 8
_COL_LAT  = 9
_W        = _COL_NUM + _COL_NAME + _COL_SRV + _COL_ACC + _COL_LAT + 10


def _rank(results: list) -> tuple:
    reachable = [r for r in results if r.get("reachable")]
    dead      = [r for r in results if not r.get("reachable")]
    # best access first, then lowest latency
    reachable.sort(key=lambda r: (-r["access"], r["latency"]))
    return reachable, dead


def run(mode: str = "interactive") -> None:
    print(f"\n{C}DNS  benchmark  —  best resolvers for your server{N}")
    print(f"{DIM}testing {len(_CANDIDATES)} providers  ·  latency + real access to "
          f"{len(_TEST_DOMAINS)} sites{N}\n")

    with ThreadPoolExecutor(max_workers=len(_CANDIDATES)) as pool:
        futs = {pool.submit(_benchmark, lbl, ips): lbl for lbl, ips in _CANDIDATES}
        results = [f.result() for f in futs]

    ranked, dead = _rank(results)

    print(f"  {B}{'#':<{_COL_NUM}} {'PROVIDER':<{_COL_NAME}} {'PRIMARY':<{_COL_SRV}} "
          f"{'ACCESS':<{_COL_ACC}} {'LATENCY':<{_COL_LAT}}{N}")
    print("  " + "─" * _W)

    for i, r in enumerate(ranked, 1):
        acc  = f"{r['access']}/{r['total']}"
        lat  = f"{r['latency']:.0f} ms"
        col  = G if r["access"] == r["total"] else (Y if r["access"] else R)
        star = f"  {G}★ best{N}" if i == 1 else ""
        print(f"  {B}{i:<{_COL_NUM}}{N} {r['label']:<{_COL_NAME}} {r['server']:<{_COL_SRV}} "
              f"{col}{acc:<{_COL_ACC}}{N} {lat:<{_COL_LAT}}{star}")

    for r in dead:
        print(f"  {DIM}✗  {r['label']:<{_COL_NAME}} {r['ips'][0]:<{_COL_SRV}} "
              f"{'—':<{_COL_ACC}} unreachable{N}")

    if not ranked:
        print(f"\n  {R}No resolver responded. Check your connection.{N}\n")
        return

    best = ranked[0]
    second = ", " + best["ips"][1] if len(best["ips"]) > 1 else ""
    print(f"\n  {'═' * _W}")
    print(f"\n  {G}Best:{N}  {B}{best['label']}{N}  "
          f"({best['server']}{second})  "
          f"{DIM}· {best['access']}/{best['total']} access · {best['latency']:.0f} ms{N}")

    # ── selection ──────────────────────────────────────────────────────
    if mode == "list":
        print()
        return

    if mode == "apply-best":
        chosen = best
    else:
        try:
            raw = input(f"\n  {C}Set which as system DNS?{N} "
                        f"{DIM}[1-{len(ranked)}, Enter = best, 0 = skip]:{N} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if raw == "0":
            print(f"\n  {DIM}No changes made.{N}\n")
            return
        if raw == "":
            chosen = best
        elif raw.isdigit() and 1 <= int(raw) <= len(ranked):
            chosen = ranked[int(raw) - 1]
        else:
            print(f"\n  {R}Invalid choice.{N}\n")
            return

    primary   = chosen["ips"][0]
    secondary = chosen["ips"][1] if len(chosen["ips"]) > 1 else ""

    print(f"\n  {DIM}Applying {chosen['label']}  ({primary}"
          f"{', ' + secondary if secondary else ''}) ...{N}")

    ok, info = _apply_dns(primary, secondary)
    if ok:
        print(f"\n  {G}✓  System DNS set to {chosen['label']}.{N}")
        if info:
            print(f"  {DIM}{info}{N}")
        if platform.system() == "Linux":
            print(f"  {DIM}Backup: /etc/resolv.conf.forcecheck.bak{N}")
    elif info == "permission":
        print(f"\n  {R}Permission denied — run as root:{N}  sudo ff")
        _manual_hint(primary, secondary)
    elif info == "admin":
        print(f"\n  {R}Administrator required — reopen the terminal as Administrator.{N}")
        _manual_hint(primary, secondary)
    else:
        print(f"\n  {R}Could not set DNS:{N} {info}")
        _manual_hint(primary, secondary)
    print()


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="dns!",
        description="Find the fastest DNS with the best access to the outside — and set it.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  dns!\n  dns! --apply-best\n  dns! --list",
    )
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--apply-best", action="store_true",
                   help="auto-apply the top-ranked resolver")
    g.add_argument("--list", action="store_true",
                   help="benchmark only, never change system DNS")
    args = ap.parse_args()

    mode = "apply-best" if args.apply_best else ("list" if args.list else "interactive")
    try:
        run(mode)
    except KeyboardInterrupt:
        print(f"\n{Y}aborted{N}")
