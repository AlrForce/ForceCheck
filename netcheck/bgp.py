"""
bgp — BGP route lookup via lg.sdv.fr (AS8839)

Usage:
  bgp <ip | prefix | asn>
"""

import re
import sys
import argparse
import warnings

import requests
from bs4 import BeautifulSoup

from .colors import G, R, Y, C, B, DIM, N

SDV_LG = "http://lg.sdv.fr"

# فیلدهای رایج در looking glass‌های مختلف
_QUERY_FIELDS = {"query", "type", "cmd", "command", "action", "qtype", "querytype"}
_ADDR_FIELDS  = {"addr", "host", "target", "arg", "prefix", "network", "ip", "q"}


def run(target: str) -> None:
    sess = requests.Session()
    sess.headers["User-Agent"] = "Mozilla/5.0 (X11; Linux x86_64) netcheck/1.0"

    print(f"\n{C}BGP  {target}  —  lg.sdv.fr (AS8839){N}\n")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # expired SSL cert on sdv.fr

        try:
            home = sess.get(SDV_LG + "/", verify=False, timeout=15)
        except requests.exceptions.ConnectionError:
            sys.exit(f"{R}Cannot connect to lg.sdv.fr{N}")

        soup = BeautifulSoup(home.text, "html.parser")
        form = soup.find("form")

        if not form:
            _fallback(sess, target)
            return

        action = form.get("action", "/")
        method = form.get("method", "get").lower()
        url    = (SDV_LG + action) if action.startswith("/") else (action or SDV_LG + "/")

        # جمع‌آوری فیلدهای موجود در فرم
        payload: dict = {}
        for tag in form.find_all(["input", "select", "textarea"]):
            name = tag.get("name")
            if not name:
                continue
            if tag.name == "select":
                first = tag.find("option")
                payload[name] = first.get("value", "") if first else ""
            else:
                payload[name] = tag.get("value", "")

        # جایگذاری مقادیر صحیح بر اساس نام فیلد
        for k in list(payload):
            lk = k.lower()
            if lk in _QUERY_FIELDS:
                payload[k] = "bgp"
            elif lk in _ADDR_FIELDS:
                payload[k] = target

        # اگر فیلد آدرس در فرم نبود، اضافه‌اش کن
        if not any(k.lower() in _ADDR_FIELDS for k in payload):
            payload["addr"] = target

        if method == "post":
            resp = sess.post(url, data=payload, verify=False, timeout=20)
        else:
            resp = sess.get(url, params=payload, verify=False, timeout=20)

    _render(resp.text, target)


def _fallback(sess: requests.Session, target: str) -> None:
    """اگر فرم parse نشد، URL‌های رایج looking glass را امتحان می‌کند."""
    candidates = [
        f"{SDV_LG}/?query=bgp&addr={target}",
        f"{SDV_LG}/?query=route&addr={target}",
        f"{SDV_LG}/cgi-bin/lg.cgi?query=bgp&addr={target}",
        f"{SDV_LG}/lg?query=bgp&addr={target}",
    ]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for url in candidates:
            try:
                r = sess.get(url, verify=False, timeout=15)
                if r.status_code == 200 and len(r.text) > 300:
                    _render(r.text, target)
                    return
            except Exception:
                continue
    sys.exit(f"{R}No response from lg.sdv.fr{N}")


def _render(html: str, target: str) -> None:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
        tag.decompose()

    block = (
        soup.find("pre")
        or soup.find("code")
        or soup.find(id=re.compile(r"result|output|content|bgp", re.I))
        or soup.find(class_=re.compile(r"result|output|bgp|pre", re.I))
    )

    text = block.get_text() if block else soup.get_text("\n")

    # پاکسازی خطوط خالی متوالی
    lines, prev_blank = [], False
    for line in text.splitlines():
        s = line.rstrip()
        blank = not s.strip()
        if blank and prev_blank:
            continue
        lines.append(s)
        prev_blank = blank

    base_ip = target.split("/")[0]
    has_data = any(base_ip.split(".")[0] in l for l in lines if l)

    if not has_data:
        print(f"{Y}No BGP data found for {target} in the response.{N}")
        print(f"{DIM}Visit {SDV_LG} directly for manual lookup.{N}\n")
    else:
        print("\n".join(lines[:120]))
        print()


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="bgp",
        description="BGP route lookup via lg.sdv.fr looking glass (AS8839)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  bgp 1.1.1.1\n  bgp 8.8.8.0/24\n  bgp 185.220.101.0/24",
    )
    ap.add_argument("host", help="IP address, prefix (x.x.x.x/yy), or ASN")

    args = ap.parse_args()

    try:
        run(args.host)
    except KeyboardInterrupt:
        print(f"\n{Y}aborted{N}")
