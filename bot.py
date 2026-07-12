"""
ForceCheck Telegram Bot
Modern inline-keyboard UI · scheduled IP monitoring via check-host.net

Setup: bot! --token <TOKEN>
       or:  fcheck → 8 (Bot Settings)
"""

import asyncio
import json
import re
import sys
import time
from pathlib import Path

STORE_PATH = Path.home() / ".forcecheck_bot.json"
CHECK_HOST = "https://check-host.net"
_IP_RE     = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")

E_OK    = "✅"
E_ERR   = "❌"
E_WARN  = "⚠️"
E_RED   = "🔴"
E_GLOBE = "🌐"
E_GEM   = "💎"
E_CLOCK = "🕐"
E_BOLT  = "⚡"
E_IRAN  = "🇮🇷"

# ── awaiting-state keys ───────────────────────────────────────────────────────
_S_IP       = "ip"
_S_INTERVAL = "interval"

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


# ── check-host.net ────────────────────────────────────────────────────────────

def _is_iran(info: list) -> bool:
    return "iran" in (info[1] if len(info) > 1 else "").lower()


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
        "iran_ok":      iran_ok > 0,
        "global_ok":    global_ok > 0,
        "iran_nodes":   iran_ok,
        "global_nodes": global_ok,
        "total_iran":   iran_total,
        "total_global": global_total,
    }


# ── message text builders ─────────────────────────────────────────────────────

def _ip_block(ip: str, res: dict) -> str:
    if not res:
        return (
            f"<code>  {ip}</code>\n"
            f"  {E_ERR}  Could not reach check-host.net"
        )
    ir = res["iran_ok"]
    gl = res["global_ok"]
    ir_n = f"{res['iran_nodes']}/{res['total_iran']}"
    gl_n = f"{res['global_nodes']}/{res['total_global']}"
    if ir and gl:
        icon, label = E_OK,   "Globally Accessible"
    elif ir and not gl:
        icon, label = E_RED,  "Iran Access Only"
    elif not ir and gl:
        icon, label = E_WARN, "Restricted  ·  Filter"
    else:
        icon, label = E_ERR,  "Host Unreachable"
    return (
        f"<code>  {ip}</code>\n"
        f"  {icon}  {label}\n"
        f"  {E_IRAN} <code>{ir_n}</code>    {E_GLOBE} <code>{gl_n}</code>"
    )


def _menu_text(user: dict) -> str:
    ips      = user.get("ips", [])
    interval = user.get("interval", 60)
    active   = user.get("active", True)
    n        = len(ips)
    ip_str   = f"{n} IP{'s' if n != 1 else ''}" if n else "—"
    sch_str  = f"every  {interval} min" if active else "paused"
    return (
        f"{E_GEM}  <b>ForceCheck Monitor</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━━━━━━</code>\n\n"
        f"<code>  Watching   {ip_str}</code>\n"
        f"<code>  Schedule   {sch_str}</code>"
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

    # ── keyboard factories ────────────────────────

    def _main_kb(user: dict) -> Kbd:
        active = user.get("active", True)
        toggle = ("⏸  Pause",   "pause") if active else ("▶️  Resume", "resume")
        return Kbd([
            [Btn("🔍  Check All",          callback_data="check")],
            [Btn("📋  My IPs",             callback_data="list"),
             Btn("➕  Add IP",             callback_data="add")],
            [Btn("🗑  Remove IP",          callback_data="remove"),
             Btn("⏱  Set Interval",       callback_data="interval")],
            [Btn(toggle[0],               callback_data=toggle[1])],
        ])

    def _back_kb(also_check: bool = False) -> Kbd:
        row = []
        if also_check:
            row.append(Btn("🔄  Check Again", callback_data="check"))
        row.append(Btn("◀  Menu",            callback_data="menu"))
        return Kbd([row])

    def _cancel_kb() -> Kbd:
        return Kbd([[Btn("✖  Cancel", callback_data="menu")]])

    def _ip_select_kb(ips: list) -> Kbd:
        rows = [[Btn(f"🗑  {ip}", callback_data=f"del:{ip}")] for ip in ips]
        rows.append([Btn("◀  Cancel", callback_data="menu")])
        return Kbd(rows)

    # ── scheduling ────────────────────────────────

    async def _job_check(ctx: ContextTypes.DEFAULT_TYPE) -> None:
        uid   = ctx.job.data["uid"]
        store = _load()
        user  = store["users"].get(uid, {})
        if not user.get("active", True) or not user.get("ips"):
            return
        ips   = user["ips"]
        loop  = asyncio.get_running_loop()
        tasks = [loop.run_in_executor(None, _check_ip, ip) for ip in ips]
        res   = await asyncio.gather(*tasks)
        div   = f"\n<code>{'─' * 27}</code>\n"
        text  = (
            f"{E_CLOCK}  <b>Scheduled Check</b>\n"
            f"<code>━━━━━━━━━━━━━━━━━━━━━━━━━</code>\n\n"
            + div.join(_ip_block(ip, r) for ip, r in zip(ips, res))
        )
        try:
            await ctx.bot.send_message(
                chat_id=int(uid),
                text=text,
                parse_mode="HTML",
                reply_markup=_back_kb(also_check=True),
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
        uid = str(update.effective_user.id)
        _, user = _get_user(uid)
        text = _menu_text(user)
        kb   = _main_kb(user)
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
        uid = str(update.effective_user.id)
        store, _ = _get_user(uid)
        _save(store)
        ctx.user_data.clear()
        await _show_menu(update, ctx)

    # ── free text handler ─────────────────────────

    async def handle_text(
        update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> None:
        uid   = str(update.effective_user.id)
        text  = update.message.text.strip()
        state = ctx.user_data.get("awaiting")

        # ── waiting for an IP ──────────────────────
        if state == _S_IP:
            ctx.user_data.pop("awaiting", None)
            if not _IP_RE.match(text):
                await update.message.reply_html(
                    f"{E_ERR}  <b>Invalid IP address</b>\n\n"
                    f"<code>{text}</code>\n\n"
                    f"Send a valid IPv4 address:\n"
                    f"<code>  e.g.  1 . 2 . 3 . 4</code>",
                    reply_markup=_cancel_kb(),
                )
                return
            store, user = _get_user(uid)
            if text in user["ips"]:
                await update.message.reply_html(
                    f"{E_WARN}  Already monitoring  <code>{text}</code>",
                    reply_markup=_back_kb(),
                )
                return
            if len(user["ips"]) >= 20:
                await update.message.reply_html(
                    f"{E_ERR}  Maximum 20 IPs per user.",
                    reply_markup=_back_kb(),
                )
                return
            user["ips"].append(text)
            _save(store)
            if user.get("active", True):
                _schedule(ctx.job_queue, uid, user.get("interval", 60))
            await update.message.reply_html(
                f"{E_OK}  <b>Added</b>  <code>{text}</code>\n\n"
                f"{E_CLOCK}  Next auto-check in  <b>{user.get('interval', 60)} min</b>",
                reply_markup=Kbd([
                    [Btn("➕  Add Another", callback_data="add"),
                     Btn("◀  Menu",        callback_data="menu")],
                ]),
            )

        # ── waiting for interval ──────────────────
        elif state == _S_INTERVAL:
            ctx.user_data.pop("awaiting", None)
            try:
                mins = int(text)
            except ValueError:
                await update.message.reply_html(
                    f"{E_ERR}  Please send a <b>number</b> of minutes.",
                    reply_markup=_cancel_kb(),
                )
                return
            if mins < 5:
                await update.message.reply_html(
                    f"{E_WARN}  Minimum interval is  <b>5 minutes</b>.",
                    reply_markup=Kbd([
                        [Btn("⏱  Try Again", callback_data="interval"),
                         Btn("◀  Menu",     callback_data="menu")],
                    ]),
                )
                return
            store, user = _get_user(uid)
            user["interval"] = mins
            _save(store)
            if user.get("active", True) and user.get("ips"):
                _schedule(ctx.job_queue, uid, mins)
            await update.message.reply_html(
                f"{E_OK}  Interval set to  <b>{mins} minutes</b>",
                reply_markup=_back_kb(),
            )

        # ── no active state: show menu ────────────
        else:
            await _show_menu(update, ctx)

    # ── callback query handler ────────────────────

    async def handle_cb(
        update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        await query.answer()
        uid  = str(update.effective_user.id)
        data = query.data

        # menu
        if data == "menu":
            ctx.user_data.pop("awaiting", None)
            await _show_menu(update, ctx, edit=True)

        # check all
        elif data == "check":
            _, user = _get_user(uid)
            ips = user.get("ips", [])
            if not ips:
                await query.edit_message_text(
                    f"{E_WARN}  <b>No IPs to check.</b>\n\nAdd some IPs first.",
                    parse_mode="HTML",
                    reply_markup=Kbd([
                        [Btn("➕  Add IP", callback_data="add"),
                         Btn("◀  Menu",  callback_data="menu")],
                    ]),
                )
                return
            n = len(ips)
            await query.edit_message_text(
                f"🔍  <b>Checking {n} IP{'s' if n > 1 else ''}…</b>\n\n"
                f"<code>  Please wait · 30–60 seconds</code>",
                parse_mode="HTML",
            )
            loop  = asyncio.get_running_loop()
            tasks = [loop.run_in_executor(None, _check_ip, ip) for ip in ips]
            res   = await asyncio.gather(*tasks)
            div   = f"\n<code>{'─' * 27}</code>\n"
            text  = (
                f"🔍  <b>Check Results</b>\n"
                f"<code>━━━━━━━━━━━━━━━━━━━━━━━━━</code>\n\n"
                + div.join(_ip_block(ip, r) for ip, r in zip(ips, res))
            )
            await query.edit_message_text(
                text, parse_mode="HTML",
                reply_markup=_back_kb(also_check=True),
            )

        # list IPs
        elif data == "list":
            _, user = _get_user(uid)
            ips      = user.get("ips", [])
            interval = user.get("interval", 60)
            active   = user.get("active", True)
            if not ips:
                await query.edit_message_text(
                    f"{E_WARN}  <b>No IPs monitored.</b>",
                    parse_mode="HTML",
                    reply_markup=Kbd([
                        [Btn("➕  Add IP", callback_data="add"),
                         Btn("◀  Menu",  callback_data="menu")],
                    ]),
                )
                return
            st    = "▶  Active" if active else "⏸  Paused"
            lines = [
                f"{E_GEM}  <b>My IPs</b>  ·  {st}  ·  every {interval} min",
                f"<code>━━━━━━━━━━━━━━━━━━━━━━━━━</code>",
                "",
            ] + [f"<code>  {i}.  {ip}</code>" for i, ip in enumerate(ips, 1)]
            await query.edit_message_text(
                "\n".join(lines),
                parse_mode="HTML",
                reply_markup=Kbd([
                    [Btn("➕  Add",    callback_data="add"),
                     Btn("🗑  Remove", callback_data="remove"),
                     Btn("◀  Menu",   callback_data="menu")],
                ]),
            )

        # add IP — prompt for text input
        elif data == "add":
            ctx.user_data["awaiting"] = _S_IP
            await query.edit_message_text(
                f"➕  <b>Add an IP to monitor</b>\n"
                f"<code>━━━━━━━━━━━━━━━━━━━━━━━━━</code>\n\n"
                f"Send the IP address:\n"
                f"<code>  e.g.  1 . 2 . 3 . 4</code>",
                parse_mode="HTML",
                reply_markup=_cancel_kb(),
            )

        # remove — show IP list as buttons
        elif data == "remove":
            _, user = _get_user(uid)
            ips = user.get("ips", [])
            if not ips:
                await query.edit_message_text(
                    f"{E_WARN}  <b>No IPs to remove.</b>",
                    parse_mode="HTML",
                    reply_markup=_back_kb(),
                )
                return
            await query.edit_message_text(
                f"🗑  <b>Select IP to remove:</b>",
                parse_mode="HTML",
                reply_markup=_ip_select_kb(ips),
            )

        elif data.startswith("del:"):
            ip_del       = data[4:]
            store, user  = _get_user(uid)
            if ip_del in user["ips"]:
                user["ips"].remove(ip_del)
                _save(store)
                await query.edit_message_text(
                    f"{E_OK}  <b>Removed</b>  <code>{ip_del}</code>",
                    parse_mode="HTML",
                    reply_markup=Kbd([
                        [Btn("🗑  Remove Another", callback_data="remove"),
                         Btn("◀  Menu",           callback_data="menu")],
                    ]),
                )
            else:
                await _show_menu(update, ctx, edit=True)

        # interval — prompt for text input
        elif data == "interval":
            _, user = _get_user(uid)
            ctx.user_data["awaiting"] = _S_INTERVAL
            await query.edit_message_text(
                f"{E_CLOCK}  <b>Set Check Interval</b>\n"
                f"<code>━━━━━━━━━━━━━━━━━━━━━━━━━</code>\n\n"
                f"Current:  <b>every {user.get('interval', 60)} minutes</b>\n\n"
                f"Send the new interval in minutes:\n"
                f"<code>  minimum  5</code>",
                parse_mode="HTML",
                reply_markup=_cancel_kb(),
            )

        # pause / resume
        elif data in ("pause", "resume"):
            store, user = _get_user(uid)
            active      = (data == "resume")
            user["active"] = active
            _save(store)
            if active and user.get("ips"):
                _schedule(ctx.job_queue, uid, user.get("interval", 60))
            else:
                for j in ctx.job_queue.get_jobs_by_name(f"fc_{uid}"):
                    j.schedule_removal()
            await _show_menu(update, ctx, edit=True)

    # ── post_init: restore schedules on startup ───

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
