"""
ForceCheck Telegram Bot
Premium UI · inline keyboards · scheduled IP monitoring via check-host.net

Setup: bot! --token <TOKEN>
       or:  fcheck → 8 (Bot Settings)
"""

import asyncio
import json
import re
import sys
import time
from pathlib import Path

try:
    from . import __version__ as _VER
except ImportError:
    _VER = "?"

STORE_PATH = Path.home() / ".forcecheck_bot.json"
CHECK_HOST = "https://check-host.net"
_IP_RE     = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")

# ── premium animated emoji (message text only) ────────────────────────────────
def _em(eid: str, fb: str) -> str:
    return f'<tg-emoji emoji-id="{eid}">{fb}</tg-emoji>'

E_OK     = _em("5861786805988234706", "✅")
E_ERR    = _em("5040042498634810056", "❌")
E_WARN   = _em("5039665997506675838", "⚠️")
E_RED    = _em("5915490338323042920", "🔴")
E_GLOBE  = _em("5188381825701021648", "🌐")
E_GEM    = _em("5364040533498932357", "💎")
E_CLOCK  = _em("5472306823555985042", "👁")
E_IRAN   = _em("6008155035123327966", "🇮🇷")
E_SAT    = _em("5949501312461707000", "📡")
E_SEARCH = _em("5039649904264217620", "🔍")
E_RELOAD = _em("5978846612087114958", "🔄")
E_ADD    = _em("5298954496016138169", "➕")
E_TRASH  = _em("5039614900280754969", "🗑")
E_PAUSE  = _em("5042036407137207122", "⏸️")
E_PLAY   = _em("5039753786638205957", "▶️")
E_BACK   = _em("5248966320845768373", "◀️")

# ── state keys ────────────────────────────────────────────────────────────────
_S_IP       = "ip"
_S_INTERVAL = "interval"

# ── visual separators ─────────────────────────────────────────────────────────
_HR  = "<code>━━━━━━━━━━━━━━━━━━━━━━━━━━━</code>"
_DIV = "<code>· · · · · · · · · · · · · · ·</code>"

# ── storage ───────────────────────────────────────────────────────────────────

def _load() -> dict:
    if STORE_PATH.exists():
        try:
            return json.loads(STORE_PATH.read_text())
        except Exception:
            pass
    return {"bot_token": "", "users": {}}


def _save(data: dict) -> None:
    STORE_PATH.write_text(json.dumps(data, indent=2))


def _get_user(uid: str) -> tuple:
    store = _load()
    user  = store["users"].setdefault(
        uid, {"ips": [], "interval": 60, "active": True}
    )
    return store, user


def _is_allowed(user_id: int) -> bool:
    allowed = _load().get("allowed_ids", [])
    return not allowed or user_id in allowed


# ── check-host.net ────────────────────────────────────────────────────────────

def _is_iran(info: list) -> bool:
    code = (info[0] if len(info) > 0 else "").lower()
    name = (info[1] if len(info) > 1 else "").lower()
    return code == "ir" or "iran" in name


def _poll_results(sess, rid: str, n: int) -> dict:
    results = {}
    for _ in range(18):
        time.sleep(2)
        try:
            results = sess.get(
                f"{CHECK_HOST}/check-result/{rid}", timeout=15
            ).json()
        except Exception:
            continue
        if sum(1 for v in results.values() if v is not None) >= n:
            break
    return results


def _check_ip(ip: str, max_nodes: int = 25) -> dict:
    import requests
    sess = requests.Session()
    sess.headers["Accept"] = "application/json"
    try:
        r = sess.get(
            f"{CHECK_HOST}/check-ping",
            params={"host": ip, "max_nodes": max_nodes},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
    except Exception:
        return {}
    nodes = data.get("nodes", {})
    if not nodes:
        return {}
    results = _poll_results(sess, data["request_id"], len(nodes))
    iran_ok = iran_total = global_ok = global_total = 0
    for nid, info in nodes.items():
        is_iran = _is_iran(info)
        pings   = results.get(nid)
        ok      = bool(
            pings and pings[0]
            and any(p and p[0] == "OK" for p in pings[0])
        )
        if is_iran:
            iran_total += 1
            if ok: iran_ok += 1
        else:
            global_total += 1
            if ok: global_ok += 1
    return {
        "iran_ok":      iran_ok >= 2,
        "global_ok":    global_ok >= 5,
        "iran_nodes":   iran_ok,
        "global_nodes": global_ok,
        "total_iran":   iran_total,
        "total_global": global_total,
    }




# ── message composers ─────────────────────────────────────────────────────────

def _stream_text(
    ip: str,
    iran_res: dict, global_res: dict,
    total_iran: int, total_global: int,
    done: bool,
) -> str:
    def _line(e: dict) -> str:
        loc = f"{e['city']}, {e['country']}" if e["city"] and e["country"] \
              else e["city"] or e["country"] or "?"
        if len(loc) > 22:
            loc = loc[:21] + "…"
        rtt_str = f"{e['rtt']:.1f}ms" if e["rtt"] is not None else "—"
        mark    = "✓" if e["ok"] else "✗"
        return f"  {loc:<23} {rtt_str:>8}   {mark}"

    iran_lines   = [_line(e) for e in iran_res.values()]
    global_lines = [_line(e) for e in global_res.values()]
    n_iran       = len(iran_res)
    n_global     = len(global_res)

    parts = [f"{E_SEARCH}  <b>Ping Check  ·  <code>{ip}</code></b>\n{_HR}\n\n"]

    if iran_lines:
        ctr = f"  <i>({n_iran}/{total_iran})</i>" if not done else ""
        parts.append(f"{E_IRAN}  <b>IRAN</b>{ctr}\n")
        parts.append("<code>" + "\n".join(iran_lines) + "</code>\n\n")

    if global_lines:
        ctr = f"  <i>({n_global}/{total_global})</i>" if not done else ""
        parts.append(f"{E_GLOBE}  <b>GLOBAL</b>{ctr}\n")
        parts.append("<code>" + "\n".join(global_lines) + "</code>\n\n")

    if not done:
        n_done  = n_iran + n_global
        n_total = total_iran + total_global
        parts.append(f"{E_CLOCK}  <i>Checking…  <b>{n_done} / {n_total}</b> nodes</i>")
    else:
        iran_ok   = sum(1 for e in iran_res.values()   if e["ok"])
        global_ok = sum(1 for e in global_res.values() if e["ok"])
        ir, gl    = iran_ok >= 2, global_ok >= 5
        if   ir and     gl:  icon, label = E_OK,   "GLOBALLY ACCESSIBLE"
        elif ir and not gl:  icon, label = E_RED,  "IRAN ACCESS ONLY"
        elif not ir and gl:  icon, label = E_WARN, "RESTRICTED  ·  FILTERED"
        else:                icon, label = E_ERR,  "HOST UNREACHABLE"
        io, it = iran_ok,   total_iran
        go, gt = global_ok, total_global
        parts.append(
            f"{_HR}\n\n"
            f"  {icon}  <b>{label}</b>\n\n"
            f"  {E_IRAN}  Iran      <code>{io:>2} / {it:<2}</code>  <i>{round(io/it*100) if it else 0}%</i>\n"
            f"  {E_GLOBE}  Global    <code>{go:>2} / {gt:<2}</code>  <i>{round(go/gt*100) if gt else 0}%</i>"
        )
    return "".join(parts)


def _pct(ok: int, total: int) -> str:
    if not total:
        return "  —  "
    return f"  <i>{round(ok / total * 100)}%</i>"


def _menu_text(user: dict) -> str:
    ips      = user.get("ips", [])
    interval = user.get("interval", 60)
    active   = user.get("active", True)
    n        = len(ips)
    ip_str   = f"<b>{n} IP{'s' if n != 1 else ''}</b>" if n else "<b>none</b>"
    play     = E_PLAY if active else E_PAUSE
    st_label = "<b>Active</b> — auto-checks running" if active else "<b>Paused</b> — manual only"
    return (
        f"{E_GEM}  <b>ForceCheck Monitor</b>\n"
        f"{_HR}\n\n"
        f"  {E_SAT}  <b>Watching</b>      {ip_str}\n"
        f"  {E_CLOCK}  <b>Interval</b>      every  <b>{interval} min</b>\n"
        f"  {play}  <b>Status</b>        {st_label}\n\n"
        f"{_HR}\n"
        f"{E_GLOBE}  <i>Monitoring from 100+ global nodes</i>"
    )


def _ip_card(ip: str, res: dict) -> str:
    if not res:
        return (
            f"  {E_SAT}  <b><code>{ip}</code></b>\n\n"
            f"  {E_ERR}  <b>Unreachable</b>\n"
            f"  <i>Could not contact check-host.net</i>"
        )
    ir  = res["iran_ok"]
    gl  = res["global_ok"]
    io  = res["iran_nodes"]
    it  = res["total_iran"]
    go  = res["global_nodes"]
    gt  = res["total_global"]

    if   ir and     gl:  icon, label = E_OK,   "GLOBALLY ACCESSIBLE"
    elif ir and not gl:  icon, label = E_RED,  "IRAN ACCESS ONLY"
    elif not ir and gl:  icon, label = E_WARN, "RESTRICTED  ·  FILTERED"
    else:                icon, label = E_ERR,  "HOST UNREACHABLE"

    iran_bar   = f"<code>{io:>2} / {it:<2}</code>{_pct(io, it)}"
    global_bar = f"<code>{go:>2} / {gt:<2}</code>{_pct(go, gt)}"

    return (
        f"  {E_SAT}  <b><code>{ip}</code></b>\n\n"
        f"  {icon}  <b>{label}</b>\n\n"
        f"  {E_IRAN}  Iran      {iran_bar}\n"
        f"  {E_GLOBE}  Global    {global_bar}"
    )


def _results_text(
    ips: list, res_list: list, is_scheduled: bool = False, interval: int = 0
) -> str:
    icon   = E_CLOCK if is_scheduled else E_SEARCH
    title  = "Scheduled Check" if is_scheduled else "Check Results"
    n      = len(ips)
    cards  = [_ip_card(ip, r) for ip, r in zip(ips, res_list)]
    sep    = f"\n\n{_DIV}\n\n"
    footer = (
        f"\n\n{_HR}\n{E_CLOCK}  <i>Next check in  <b>{interval} min</b></i>"
        if is_scheduled and interval else ""
    )
    ok_count   = sum(1 for r in res_list if r and r.get("iran_ok") and r.get("global_ok"))
    iran_only  = sum(1 for r in res_list if r and r.get("iran_ok") and not r.get("global_ok"))
    restricted = sum(1 for r in res_list if r and not r.get("iran_ok") and r.get("global_ok"))
    unreachable= sum(1 for r in res_list if not r or (not r.get("iran_ok") and not r.get("global_ok")))

    summary_parts = []
    if ok_count:    summary_parts.append(f"{E_OK} <b>{ok_count}</b>")
    if iran_only:   summary_parts.append(f"{E_RED} <b>{iran_only}</b>")
    if restricted:  summary_parts.append(f"{E_WARN} <b>{restricted}</b>")
    if unreachable: summary_parts.append(f"{E_ERR} <b>{unreachable}</b>")
    summary = "  ·  " + "  ".join(summary_parts) if summary_parts else ""

    return (
        f"{icon}  <b>{title}</b>  ·  <b>{n} IP{'s' if n > 1 else ''}</b>{summary}\n"
        f"{_HR}\n\n"
        + sep.join(cards)
        + footer
    )


def _list_text(user: dict) -> str:
    ips      = user.get("ips", [])
    interval = user.get("interval", 60)
    active   = user.get("active", True)
    n        = len(ips)
    play     = E_PLAY if active else E_PAUSE
    st_label = "<b>Active</b>" if active else "<b>Paused</b>"
    lines = [
        f"📋  <b>My IPs</b>",
        f"{_HR}",
        f"",
        f"  {play}  {st_label}  ·  every  <b>{interval} min</b>",
        f"  {E_GLOBE}  Slots used:  <b>{n} / 20</b>",
        f"",
        f"{_DIV}",
        f"",
    ]
    if not ips:
        lines.append(f"  <i>No IPs added yet.</i>")
    else:
        for i, ip in enumerate(ips, 1):
            lines.append(f"  <code>{i:>2}.   {ip}</code>")
    return "\n".join(lines)


def _help_text() -> str:
    return (
        f"{E_SEARCH}  <b>Guide  &  Help</b>\n"
        f"{_HR}\n\n"

        f"{E_SEARCH}  <b>Check All Now</b>\n"
        f"  Instantly pings all your IPs from\n"
        f"  <b>100+ nodes</b> around the world.\n\n"

        f"{E_ADD}  <b>Add IP</b>\n"
        f"  Add an IPv4 address to your watch list.\n"
        f"  <i>Format: 1.2.3.4 · Max 20 IPs</i>\n\n"

        f"{E_TRASH}  <b>Remove IP</b>\n"
        f"  Tap an IP to stop monitoring it.\n\n"

        f"{E_CLOCK}  <b>Set Interval</b>\n"
        f"  How often the bot auto-checks your IPs.\n"
        f"  <i>Min: 5 min · Recommended: 30 – 60 min</i>\n\n"

        f"{E_PAUSE}  <b>Pause</b>  /  {E_PLAY}  <b>Resume</b>\n"
        f"  Stop or restart scheduled auto-checks.\n"
        f"  <i>Manual checks always work when paused.</i>\n\n"

        f"{_HR}\n\n"

        f"<b>Status Legend</b>\n\n"

        f"  {E_OK}  <b>Globally Accessible</b>\n"
        f"  <i>Reachable from Iran AND global nodes.</i>\n\n"

        f"  {E_RED}  <b>Iran Access Only</b>\n"
        f"  <i>Responds from Iran, blocked globally.</i>\n\n"

        f"  {E_WARN}  <b>Restricted · Filtered</b>\n"
        f"  <i>Blocked inside Iran, reachable globally.</i>\n\n"

        f"  {E_ERR}  <b>Host Unreachable</b>\n"
        f"  <i>No response from any node worldwide.</i>\n\n"

        f"{_HR}\n"
        f"{E_GEM}  <i>Powered by ForceCheck  ·  check-host.net</i>"
    )


def _about_text() -> str:
    return (
        f"{E_GEM}  <b>About ForceCheck</b>\n"
        f"{_HR}\n\n"

        f"  <i>Thanks for supporting ForceProjects!</i>\n\n"

        f"{_HR}\n\n"

        f"  {E_SAT}  <b>Telegram</b>    @ThisChannelisX\n"
        f"  {E_GLOBE}  <b>GitHub</b>      <code>github.com/AlrForce</code>\n\n"

        f"{_HR}\n\n"

        f"  {E_GEM}  <b>Support the Project</b>\n\n"

        f"  {E_OK}  <b>Wallet Address</b>  ·  <i>BEP20 — USDT</i>\n"
        f"<code>0x5a8AB785F17006495323F00a62473e638ebE008b</code>\n\n"

        f"{_HR}\n"
        f"{E_RELOAD}  <i>Powered by AlrForce  ·  v{_VER}</i>"
    )


# ── bot application ───────────────────────────────────────────────────────────

def _build_app(token: str):
    from telegram import (
        Update,
        InlineKeyboardButton as Btn,
        InlineKeyboardMarkup as Kbd,
    )
    from telegram.ext import (
        Application, CommandHandler, CallbackQueryHandler,
        MessageHandler, ContextTypes, filters,
    )

    app = Application.builder().token(token).build()

    # ── keyboards ─────────────────────────────────

    def _kb_main(user: dict) -> Kbd:
        active = user.get("active", True)
        toggle = (
            ("⏸️  Pause Monitoring",  "pause")  if active else
            ("▶️  Resume Monitoring", "resume")
        )
        return Kbd([
            [Btn("🔍  Check All Now",       callback_data="check")],
            [Btn("📋  My IPs",              callback_data="list"),
             Btn("➕  Add IP",              callback_data="add")],
            [Btn("🗑  Remove IP",           callback_data="remove"),
             Btn("⏱  Set Interval",        callback_data="interval")],
            [Btn(toggle[0],                callback_data=toggle[1])],
            [Btn("❓  Guide & Help",        callback_data="help"),
             Btn("ℹ️  About",              callback_data="about")],
        ])

    def _kb_check_select(ips: list) -> Kbd:
        rows = [[Btn(f"📡  {ip}", callback_data=f"check_one:{ip}")] for ip in ips]
        rows.append([Btn("🔍  Check All",  callback_data="check_all")])
        rows.append([Btn("◀️  Menu",       callback_data="menu")])
        return Kbd(rows)

    def _kb_back(also_check: bool = False) -> Kbd:
        row = []
        if also_check:
            row.append(Btn("🔄  Check Again", callback_data="check"))
        row.append(Btn("◀️  Menu", callback_data="menu"))
        return Kbd([row])

    def _kb_cancel() -> Kbd:
        return Kbd([[Btn("✖  Cancel", callback_data="menu")]])

    def _kb_remove(ips: list) -> Kbd:
        rows = [[Btn(f"🗑  {ip}", callback_data=f"del:{ip}")] for ip in ips]
        rows.append([Btn("◀️  Cancel", callback_data="menu")])
        return Kbd(rows)

    # ── scheduling ────────────────────────────────

    async def _job_check(ctx: ContextTypes.DEFAULT_TYPE) -> None:
        uid   = ctx.job.data["uid"]
        store = _load()
        user  = store["users"].get(uid, {})
        if not user.get("active", True) or not user.get("ips"):
            return
        ips      = user["ips"]
        interval = user.get("interval", 60)
        loop     = asyncio.get_running_loop()
        tasks    = [loop.run_in_executor(None, _check_ip, ip) for ip in ips]
        res_list = await asyncio.gather(*tasks)
        text     = _results_text(ips, res_list, is_scheduled=True, interval=interval)
        try:
            await ctx.bot.send_message(
                chat_id=int(uid),
                text=text,
                parse_mode="HTML",
                reply_markup=_kb_back(also_check=True),
            )
        except Exception:
            pass

    def _schedule(jq, uid: str, interval: int) -> None:
        for j in jq.get_jobs_by_name(f"fc_{uid}"):
            j.schedule_removal()
        jq.run_repeating(
            _job_check,
            interval=interval * 60,
            first=interval * 60,
            name=f"fc_{uid}",
            data={"uid": uid},
        )

    # ── helpers ───────────────────────────────────

    async def _show_menu(
        update: Update,
        ctx: ContextTypes.DEFAULT_TYPE,
        edit: bool = False,
    ) -> None:
        uid     = str(update.effective_user.id)
        _, user = _get_user(uid)
        text    = _menu_text(user)
        kb      = _kb_main(user)
        if edit and update.callback_query:
            await update.callback_query.edit_message_text(
                text, parse_mode="HTML", reply_markup=kb
            )
        elif update.message:
            await update.message.reply_html(text, reply_markup=kb)
        elif update.callback_query:
            await update.callback_query.message.reply_html(text, reply_markup=kb)

    # ── /start ────────────────────────────────────

    async def cmd_start(
        update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not _is_allowed(update.effective_user.id):
            await update.message.reply_html(
                f"{E_ERR}  <b>Access Denied</b>\n\n"
                f"<i>This bot is private.\n"
                f"Contact the owner for access.</i>"
            )
            return
        uid = str(update.effective_user.id)
        store, _ = _get_user(uid)
        _save(store)
        ctx.user_data.clear()
        await _show_menu(update, ctx)

    # ── free-text handler ─────────────────────────

    async def handle_text(
        update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not _is_allowed(update.effective_user.id):
            return
        uid   = str(update.effective_user.id)
        text  = update.message.text.strip()
        state = ctx.user_data.get("awaiting")

        # waiting for IP ───────────────────────────
        if state == _S_IP:
            ctx.user_data.pop("awaiting", None)

            if not _IP_RE.match(text):
                await update.message.reply_html(
                    f"{E_ERR}  <b>Invalid IP Address</b>\n"
                    f"{_HR}\n\n"
                    f"  <code>{text}</code>\n\n"
                    f"<i>Please send a valid IPv4 address.\n"
                    f"Format: four numbers separated by dots.</i>\n\n"
                    f"  <code>e.g.   1 . 2 . 3 . 4</code>",
                    reply_markup=_kb_cancel(),
                )
                return

            store, user = _get_user(uid)
            if text in user["ips"]:
                await update.message.reply_html(
                    f"{E_WARN}  <b>Already Monitoring</b>\n"
                    f"{_HR}\n\n"
                    f"  {E_SAT}  <b><code>{text}</code></b>\n\n"
                    f"<i>This IP is already in your watch list.\n"
                    f"Send a different IP or go back to menu.</i>",
                    reply_markup=Kbd([
                        [Btn("➕  Add Another", callback_data="add"),
                         Btn("◀️  Menu",        callback_data="menu")],
                    ]),
                )
                return
            if len(user["ips"]) >= 20:
                await update.message.reply_html(
                    f"{E_ERR}  <b>Watch List Full</b>\n"
                    f"{_HR}\n\n"
                    f"  {E_GLOBE}  <b>20 / 20</b>  IPs used\n\n"
                    f"<i>Remove an IP first to add a new one.</i>",
                    reply_markup=Kbd([
                        [Btn("🗑  Remove IP", callback_data="remove"),
                         Btn("◀️  Menu",      callback_data="menu")],
                    ]),
                )
                return

            user["ips"].append(text)
            _save(store)
            if user.get("active", True):
                _schedule(ctx.job_queue, uid, user.get("interval", 60))

            n_used = len(user["ips"])
            await update.message.reply_html(
                f"{E_OK}  <b>Added to Monitoring</b>\n"
                f"{_HR}\n\n"
                f"  {E_SAT}  <b><code>{text}</code></b>\n\n"
                f"  {E_CLOCK}  First check in   <b>{user.get('interval', 60)} min</b>\n"
                f"  {E_GLOBE}  Slots used:      <b>{n_used} / 20</b>",
                reply_markup=Kbd([
                    [Btn("➕  Add Another", callback_data="add"),
                     Btn("◀️  Menu",        callback_data="menu")],
                ]),
            )

        # waiting for interval ─────────────────────
        elif state == _S_INTERVAL:
            ctx.user_data.pop("awaiting", None)

            try:
                mins = int(text)
            except ValueError:
                await update.message.reply_html(
                    f"{E_ERR}  <b>Invalid Input</b>\n"
                    f"{_HR}\n\n"
                    f"  <code>{text}</code>\n\n"
                    f"<i>Please send a whole number (minutes).\n"
                    f"Example: <b>30</b> for every 30 minutes.</i>",
                    reply_markup=_kb_cancel(),
                )
                return

            if mins < 5:
                await update.message.reply_html(
                    f"{E_WARN}  <b>Interval Too Short</b>\n"
                    f"{_HR}\n\n"
                    f"  <b>{mins} min</b>  is below the minimum.\n\n"
                    f"  {E_CLOCK}  Minimum interval:  <b>5 minutes</b>\n"
                    f"  <i>Recommended: 30 – 60 minutes</i>",
                    reply_markup=Kbd([
                        [Btn("⏱  Try Again", callback_data="interval"),
                         Btn("◀️  Menu",     callback_data="menu")],
                    ]),
                )
                return

            store, user = _get_user(uid)
            user["interval"] = mins
            _save(store)
            if user.get("active", True) and user.get("ips"):
                _schedule(ctx.job_queue, uid, mins)

            await update.message.reply_html(
                f"{E_OK}  <b>Interval Updated</b>\n"
                f"{_HR}\n\n"
                f"  {E_CLOCK}  Auto-check every   <b>{mins} min</b>\n\n"
                f"<i>Next scheduled check will run in {mins} min.</i>",
                reply_markup=_kb_back(),
            )

        # no state → show menu ─────────────────────
        else:
            await _show_menu(update, ctx)

    # ── callback handler ──────────────────────────

    async def handle_cb(
        update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        if not _is_allowed(update.effective_user.id):
            await query.answer("⛔ Access denied.", show_alert=True)
            return
        await query.answer()
        uid  = str(update.effective_user.id)
        data = query.data

        if data == "menu":
            ctx.user_data.pop("awaiting", None)
            await _show_menu(update, ctx, edit=True)

        # ── help ──────────────────────────────────
        elif data == "help":
            await query.edit_message_text(
                _help_text(),
                parse_mode="HTML",
                reply_markup=_kb_back(),
            )

        # ── about ─────────────────────────────────
        elif data == "about":
            await query.edit_message_text(
                _about_text(),
                parse_mode="HTML",
                reply_markup=_kb_back(),
            )

        # ── check — show IP selection screen ──────
        elif data == "check":
            _, user = _get_user(uid)
            ips = user.get("ips", [])
            if not ips:
                await query.edit_message_text(
                    f"{E_WARN}  <b>No IPs to Monitor</b>\n"
                    f"{_HR}\n\n"
                    f"<i>Your watch list is empty.\n"
                    f"Add an IP first to start monitoring.</i>",
                    parse_mode="HTML",
                    reply_markup=Kbd([
                        [Btn("➕  Add IP", callback_data="add"),
                         Btn("◀️  Menu",  callback_data="menu")],
                    ]),
                )
                return
            await query.edit_message_text(
                f"{E_SEARCH}  <b>Select IP to Check</b>\n"
                f"{_HR}\n\n"
                f"<i>Tap an IP for a detailed per-node ping,\n"
                f"or check all IPs at once:</i>",
                parse_mode="HTML",
                reply_markup=_kb_check_select(ips),
            )

        # ── single IP — streaming ping ─────────────
        elif data.startswith("check_one:"):
            import requests as _req
            ip   = data[len("check_one:"):]
            loop = asyncio.get_running_loop()
            kb_done = Kbd([
                [Btn("🔄  Check Again", callback_data=f"check_one:{ip}"),
                 Btn("◀️  Back",        callback_data="check")],
                [Btn("◀️  Menu", callback_data="menu")],
            ])

            await query.edit_message_text(
                f"{E_SEARCH}  <b>Ping Check  ·  <code>{ip}</code></b>\n"
                f"{_HR}\n\n"
                f"  {E_CLOCK}  <i>Connecting to check-host.net…</i>",
                parse_mode="HTML",
            )

            # ── start request ──────────────────────
            sess = _req.Session()
            sess.headers["Accept"] = "application/json"
            try:
                pr = await loop.run_in_executor(None, lambda: sess.get(
                    f"{CHECK_HOST}/check-ping",
                    params={"host": ip, "max_nodes": 25},
                    timeout=15,
                ))
                pr.raise_for_status()
                ping_data = pr.json()
            except Exception:
                await query.edit_message_text(
                    _stream_text(ip, {}, {}, 0, 0, done=True),
                    parse_mode="HTML", reply_markup=kb_done,
                )
                return

            nodes = ping_data.get("nodes", {})
            rid   = ping_data.get("request_id", "")
            if not nodes:
                await query.edit_message_text(
                    _stream_text(ip, {}, {}, 0, 0, done=True),
                    parse_mode="HTML", reply_markup=kb_done,
                )
                return

            iran_nodes   = {n: i for n, i in nodes.items() if _is_iran(i)}
            global_nodes = {n: i for n, i in nodes.items() if not _is_iran(i)}
            total_iran   = len(iran_nodes)
            total_global = len(global_nodes)
            total        = len(nodes)
            seen         = set()
            iran_res     = {}   # nid → entry, insertion-ordered
            global_res   = {}

            await query.edit_message_text(
                _stream_text(ip, {}, {}, total_iran, total_global, done=False),
                parse_mode="HTML",
            )

            def _parse_node(info, pings):
                attempts = (pings[0] or []) if pings else []
                ok_list  = [p for p in attempts if p and p[0] == "OK"]
                ok  = bool(ok_list)
                rtt = sum(p[1] * 1000 for p in ok_list) / len(ok_list) if ok_list else None
                return {
                    "city":    info[2] if len(info) > 2 else "?",
                    "country": info[1] if len(info) > 1 else "?",
                    "rtt": rtt, "ok": ok,
                }

            # ── streaming poll loop ─────────────────
            for _ in range(18):
                await asyncio.sleep(2)
                try:
                    batch = await loop.run_in_executor(None, lambda: sess.get(
                        f"{CHECK_HOST}/check-result/{rid}", timeout=15
                    ).json())
                except Exception:
                    continue

                new_data = False
                for nid, info in iran_nodes.items():
                    if nid not in seen and batch.get(nid) is not None:
                        seen.add(nid)
                        iran_res[nid] = _parse_node(info, batch[nid])
                        new_data = True
                for nid, info in global_nodes.items():
                    if nid not in seen and batch.get(nid) is not None:
                        seen.add(nid)
                        global_res[nid] = _parse_node(info, batch[nid])
                        new_data = True

                is_done = len(seen) >= total
                if new_data:
                    txt = _stream_text(ip, iran_res, global_res,
                                       total_iran, total_global, is_done)
                    try:
                        await query.edit_message_text(
                            txt, parse_mode="HTML",
                            reply_markup=kb_done if is_done else None,
                        )
                    except Exception:
                        pass
                if is_done:
                    break

            # ── timeout: mark remaining as ✗ ───────
            if len(seen) < total:
                for nid, info in {**iran_nodes, **global_nodes}.items():
                    if nid not in seen:
                        entry = {"city": info[2] if len(info) > 2 else "?",
                                 "country": info[1] if len(info) > 1 else "?",
                                 "rtt": None, "ok": False}
                        if nid in iran_nodes:
                            iran_res[nid] = entry
                        else:
                            global_res[nid] = entry
                try:
                    await query.edit_message_text(
                        _stream_text(ip, iran_res, global_res,
                                     total_iran, total_global, done=True),
                        parse_mode="HTML", reply_markup=kb_done,
                    )
                except Exception:
                    pass

        # ── check all — summary overview ───────────
        elif data == "check_all":
            _, user = _get_user(uid)
            ips = user.get("ips", [])
            n   = len(ips)
            await query.edit_message_text(
                f"{E_SEARCH}  <b>Checking {n} IP{'s' if n > 1 else ''}…</b>\n"
                f"{_HR}\n\n"
                f"  {E_CLOCK}  Please wait  ·  <b>30 – 60 seconds</b>\n\n"
                f"  <i>Pinging from 100+ global nodes…</i>",
                parse_mode="HTML",
            )
            loop     = asyncio.get_running_loop()
            tasks    = [loop.run_in_executor(None, _check_ip, ip) for ip in ips]
            res_list = await asyncio.gather(*tasks)
            await query.edit_message_text(
                _results_text(ips, res_list),
                parse_mode="HTML",
                reply_markup=Kbd([
                    [Btn("🔄  Check All Again", callback_data="check_all"),
                     Btn("◀️  Back",            callback_data="check")],
                    [Btn("◀️  Menu", callback_data="menu")],
                ]),
            )

        # ── list ──────────────────────────────────
        elif data == "list":
            _, user = _get_user(uid)
            await query.edit_message_text(
                _list_text(user),
                parse_mode="HTML",
                reply_markup=Kbd([
                    [Btn("➕  Add",    callback_data="add"),
                     Btn("🗑  Remove", callback_data="remove"),
                     Btn("◀️  Menu",  callback_data="menu")],
                ]),
            )

        # ── add ───────────────────────────────────
        elif data == "add":
            _, user = _get_user(uid)
            n_used  = len(user.get("ips", []))
            ctx.user_data["awaiting"] = _S_IP
            await query.edit_message_text(
                f"{E_ADD}  <b>Add IP to Monitor</b>\n"
                f"{_HR}\n\n"
                f"Send the <b>IPv4 address</b> you want to monitor:\n\n"
                f"  {E_GLOBE}  Slots:  <b>{n_used} / 20</b> used\n"
                f"  {E_CLOCK}  Interval:  every  <b>{user.get('interval', 60)} min</b>\n\n"
                f"{_DIV}\n\n"
                f"  <code>e.g.   1 . 2 . 3 . 4</code>",
                parse_mode="HTML",
                reply_markup=_kb_cancel(),
            )

        # ── remove ────────────────────────────────
        elif data == "remove":
            _, user = _get_user(uid)
            ips = user.get("ips", [])
            if not ips:
                await query.edit_message_text(
                    f"{E_WARN}  <b>Nothing to Remove</b>\n"
                    f"{_HR}\n\n"
                    f"<i>Your monitoring list is already empty.</i>",
                    parse_mode="HTML",
                    reply_markup=_kb_back(),
                )
                return
            await query.edit_message_text(
                f"{E_TRASH}  <b>Remove IP</b>\n"
                f"{_HR}\n\n"
                f"<i>Tap an IP below to remove it\n"
                f"from your monitoring list:</i>",
                parse_mode="HTML",
                reply_markup=_kb_remove(ips),
            )

        elif data.startswith("del:"):
            ip_del      = data[4:]
            store, user = _get_user(uid)
            if ip_del in user["ips"]:
                user["ips"].remove(ip_del)
                _save(store)
                n_left = len(user["ips"])
                await query.edit_message_text(
                    f"{E_TRASH}  <b>Removed from Monitoring</b>\n"
                    f"{_HR}\n\n"
                    f"  {E_SAT}  <b><code>{ip_del}</code></b>\n\n"
                    f"  {E_GLOBE}  Remaining:  <b>{n_left} / 20</b>",
                    parse_mode="HTML",
                    reply_markup=Kbd([
                        [Btn("🗑  Remove Another", callback_data="remove"),
                         Btn("◀️  Menu",           callback_data="menu")],
                    ]),
                )
            else:
                await _show_menu(update, ctx, edit=True)

        # ── interval ──────────────────────────────
        elif data == "interval":
            _, user = _get_user(uid)
            ctx.user_data["awaiting"] = _S_INTERVAL
            await query.edit_message_text(
                f"{E_CLOCK}  <b>Set Auto-Check Interval</b>\n"
                f"{_HR}\n\n"
                f"  Current:  every  <b>{user.get('interval', 60)} min</b>\n\n"
                f"<i>How often should the bot check your IPs?</i>\n\n"
                f"  {E_OK}  Minimum:        <b>5 min</b>\n"
                f"  {E_GLOBE}  Recommended:  <b>30 – 60 min</b>\n\n"
                f"{_DIV}\n\n"
                f"<i>Send the new interval in minutes:</i>",
                parse_mode="HTML",
                reply_markup=_kb_cancel(),
            )

        # ── pause / resume ────────────────────────
        elif data in ("pause", "resume"):
            store, user = _get_user(uid)
            active = (data == "resume")
            user["active"] = active
            _save(store)
            if active and user.get("ips"):
                _schedule(ctx.job_queue, uid, user.get("interval", 60))
            else:
                for j in ctx.job_queue.get_jobs_by_name(f"fc_{uid}"):
                    j.schedule_removal()
            await _show_menu(update, ctx, edit=True)

    # ── post_init ─────────────────────────────────

    async def _post_init(application) -> None:
        store = _load()
        for uid, user in store["users"].items():
            if user.get("active", True) and user.get("ips"):
                _schedule(
                    application.job_queue,
                    uid,
                    user.get("interval", 60),
                )

    app.post_init = _post_init
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(handle_cb))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    return app


# ── public API ────────────────────────────────────────────────────────────────

def run(token: str) -> None:
    asyncio.set_event_loop(asyncio.new_event_loop())
    app = _build_app(token)
    print("ForceCheck Bot started. Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


def main() -> None:
    import argparse
    from .colors import G, R, Y, C, N

    ap = argparse.ArgumentParser(
        prog="bot!",
        description="ForceCheck Telegram monitoring bot",
        epilog=(
            "Setup:\n"
            "  bot! --token <TOKEN>\n"
            "  or:  fcheck  → 8 (Bot Settings)\n\n"
            "Get a token from @BotFather on Telegram."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--token", "-t", metavar="TOKEN",
                    help="Telegram bot token (from @BotFather)")
    ap.add_argument("--setup", "-s", action="store_true",
                    help="Interactive setup wizard")
    args = ap.parse_args()

    try:
        import telegram  # noqa: F401
    except ImportError:
        print(f"\n{R}Missing dependency:{N} python-telegram-bot\n")
        print(f"Install:  {C}pip install 'python-telegram-bot[job-queue]>=20.0'{N}\n")
        sys.exit(1)

    data  = _load()
    token = args.token or data.get("bot_token", "")

    if args.setup or not token:
        print(f"\n  {C}ForceCheck Bot Setup{N}\n")
        print(f"  {R}Get a token from @BotFather on Telegram.{N}")
        try:
            token = input("\n  Bot token: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not token:
            print(f"  {R}No token entered.{N}")
            return
        data["bot_token"] = token
        _save(data)
        print(f"  {G}Token saved to {STORE_PATH}{N}\n")

    if args.token and args.token != data.get("bot_token"):
        data["bot_token"] = args.token
        _save(data)

    try:
        run(token)
    except KeyboardInterrupt:
        print(f"\n  {Y}Bot stopped.{N}")
