"""
domain — domain availability and WHOIS lookup via RDAP

Usage:
  domain! <domain>
"""

import sys
import socket
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from .colors import G, R, Y, C, B, DIM, N
from ._deps import ensure_deps

RDAP = "https://rdap.org/domain/{}"

_TLDS = [
    "com", "net", "org", "io", "co", "app", "dev",
    "ai", "me", "info", "biz", "online", "site", "store", "shop",
]


def _row(label: str, value: str) -> None:
    print(f"  {DIM}{label:<14}{N}{value}")


def _rdap(sess, domain: str) -> tuple:
    """('registered'|'available'|'unknown', data)"""
    import requests
    try:
        r = sess.get(RDAP.format(domain), timeout=8,
                     headers={"Accept": "application/rdap+json"})
        if r.status_code == 200:
            return "registered", r.json()
        if r.status_code == 404:
            return "available", {}
    except Exception:
        pass
    try:
        socket.getaddrinfo(domain, None)
        return "registered", {}
    except socket.gaierror:
        return "available", {}


def _check_tld(sess, name: str, tld: str) -> tuple:
    domain = f"{name}.{tld}"
    status, _ = _rdap(sess, domain)
    return domain, status


def _fmt_date(s: str) -> str:
    return s[:10] if s else "—"


def _entity_name(entity: dict) -> str:
    vcard = entity.get("vcardArray", [None, []])[1]
    for field in vcard:
        if field[0] == "fn" and field[3]:
            return str(field[3])
    return entity.get("handle", "—")


def run(domain: str) -> None:
    import requests
    sess = requests.Session()

    domain = domain.lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]
    if "." not in domain:
        domain = f"{domain}.com"

    name        = domain.split(".")[0]
    current_tld = ".".join(domain.split(".")[1:])

    print(f"\n{C}DOMAIN  {domain}  —  rdap.org{N}\n")

    status, data = _rdap(sess, domain)

    w = 36
    if status == "available":
        print(f"  {G}╔{'═' * w}╗{N}")
        print(f"  {G}║{'✓  Available for Registration':^{w}}║{N}")
        print(f"  {G}╚{'═' * w}╝{N}\n")
    else:
        print(f"  {R}╔{'═' * w}╗{N}")
        print(f"  {R}║{'✗  Registered':^{w}}║{N}")
        print(f"  {R}╚{'═' * w}╝{N}\n")

        if data:
            registrar = "—"
            for ent in data.get("entities", []):
                if "registrar" in ent.get("roles", []):
                    registrar = _entity_name(ent)
                    break

            created = expires = "—"
            for ev in data.get("events", []):
                action = ev.get("eventAction", "")
                if action == "registration":
                    created = _fmt_date(ev.get("eventDate", ""))
                elif action == "expiration":
                    expires = _fmt_date(ev.get("eventDate", ""))

            statuses = data.get("status", [])
            ns_list  = [ns.get("ldhName", "") for ns in data.get("nameservers", [])]

            _row("Registrar",   registrar)
            _row("Status",      ", ".join(statuses) if statuses else "—")
            _row("Created",     created)
            _row("Expires",     f"{Y}{expires}{N}" if expires != "—" else "—")
            if ns_list:
                _row("Nameservers", ns_list[0])
                for ns in ns_list[1:4]:
                    _row("", ns)
            print()

    check_tlds = [t for t in _TLDS if t != current_tld]

    print(f"  {B}── Alternative TLDs {'─' * 28}{N}\n")

    tld_results = {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(_check_tld, sess, name, t): t for t in check_tlds}
        for fut in as_completed(futures):
            dom, st = fut.result()
            tld_results[dom] = st

    for tld in check_tlds:
        dom = f"{name}.{tld}"
        st  = tld_results.get(dom, "unknown")
        if st == "available":
            tag = f"{G}✓  available{N}"
        elif st == "registered":
            tag = f"{R}✗  registered{N}"
        else:
            tag = f"{Y}?  unknown{N}"
        print(f"  {DIM}{dom:<28}{N}  {tag}")

    print()


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="domain!",
        description="Domain availability check and WHOIS via RDAP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  domain! example.com\n  domain! mysite\n  domain! coolapp.io",
    )
    ap.add_argument("domain", help="Domain name to check")

    args = ap.parse_args()
    ensure_deps()

    try:
        run(args.domain)
    except KeyboardInterrupt:
        print(f"\n{Y}aborted{N}")
