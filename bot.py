"""
ForceCheck Telegram Bot — IP health monitor via check-host.net

Setup:
  1. Create a bot via @BotFather on Telegram
  2. Run:  bot! --token <TOKEN>
     Or:   fcheck → 8 (Bot Settings)

Telegram commands:
  /start            welcome & register
  /add <ip>         add IP to watch list
  /remove <ip>      remove IP from list
  /list             show watched IPs and interval
  /check            run immediate check on all IPs
  /interval <min>   set auto-check interval (min: 5)
  /pause            pause automatic checks
  /resume           resume automatic checks
"""

import json
import re
import sys
import time
from pathlib import Path

STORE_PATH = Path.home() / ".forcecheck_bot.json"
CHECK_HOST = "https://check-host.net"
_IP_RE     = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")


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


# ── check-host.net ────────────────────────────────────────────────────────────

def _is_iran(node_info: list) -> bool:
    return "iran" in (node_info[1] if len(node_info) > 1 else "").lower()


def _poll_results(sess, request_id: str, node_count: int) -> dict:
    results = {}
    for _ in range(18):
        time.sleep(2)
        try:
            r = sess.get(f"{CHECK_HOST}/check-result/{request_id}", timeout=15)
            results = r.json()
        except Exception:
            continue
        if sum(1 for v in results.values() if v is not None) >= node_count:
            break
    return results


def _check_ip(ip: str, max_nodes: int = 25) -> dict:
    """
    Returns:
      iran_ok, global_ok (bool)
      iran_nodes, global_nodes (int — OK count)
      total_iran, total_global (int)
    """
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
    for node_id, node_info in nodes.items():
        is_iran = _is_iran(node_info)
        pings   = results.get(node_id)
        node_ok = bool(
            pings and pings[0]
            and any(p and p[0] == "OK" for p in pings[0])
        )
        if is_iran:
            iran_total += 1
            if node_ok:
                iran_ok += 1
        else:
            global_total += 1
            if node_ok:
                global_ok += 1

    return {
        "iran_ok":      iran_ok > 0,
        "global_ok":    global_ok > 0,
        "iran_nodes":   iran_ok,
        "global_nodes": global_ok,
        "total_iran":   iran_total,
        "total_global": global_total,
    }


def _status_msg(ip: str, res: dict) -> str:
    if not res:
        return f"❓ <code>{ip}</code>\ncould not reach check-host.net"

    iran_ok   = res["iran_ok"]
    global_ok = res["global_ok"]
    ir_n      = f"{res['iran_nodes']}/{res['total_iran']}"
    gl_n      = f"{res['global_nodes']}/{res['total_global']}"

    if iran_ok and global_ok:
        status = "✅  Globally Accessible"
    elif iran_ok and not global_ok:
        status = "🔴  This IP is Iran Access Only"
    elif not iran_ok and global_ok:
        status = "⚠️  This IP is Restricted  ( Filter )"
    else:
        status = "🚫  Host Unreachable"

    return (
        f"<b>{ip}</b>\n"
        f"{status}\n"
        f"🇮🇷 Iran: <code>{ir_n}</code>  🌐 Global: <code>{gl_n}</code>"
    )


# ── bot ───────────────────────────────────────────────────────────────────────

def _build_app(token: str):
    from telegram import Update
    from telegram.ext import Application, CommandHandler, ContextTypes

    app = Application.builder().token(token).build()

    def _get_user(uid: str) -> tuple:
        store = _load()
        user  = store["users"].setdefault(
            uid, {"ips": [], "interval": 60, "active": True}
        )
        return store, user

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

    # ── /start ───────────────────────────────────────

    async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = str(update.effective_user.id)
        store, _ = _get_user(uid)
        _save(store)
        await update.message.reply_html(
            "👋 <b>ForceCheck Bot</b>\n\n"
            "Monitor your IPs from global nodes.\n\n"
            "<b>Commands:</b>\n"
            "• /add &lt;ip&gt; — watch an IP\n"
            "• /remove &lt;ip&gt; — stop watching\n"
            "• /list — show watched IPs\n"
            "• /check — check all IPs now\n"
            "• /interval &lt;minutes&gt; — auto-check interval\n"
            "• /pause — pause auto checks\n"
            "• /resume — resume auto checks"
        )

    # ── /add ─────────────────────────────────────────

    async def cmd_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = str(update.effective_user.id)
        if not ctx.args:
            await update.message.reply_text("Usage: /add <ip>")
            return
        ip = ctx.args[0].strip()
        if not _IP_RE.match(ip):
            await update.message.reply_text(f"❌ Invalid IP address: {ip}")
            return
        store, user = _get_user(uid)
        if ip in user["ips"]:
            await update.message.reply_html(f"Already monitoring <code>{ip}</code>")
            return
        if len(user["ips"]) >= 20:
            await update.message.reply_text("Maximum 20 IPs per user.")
            return
        user["ips"].append(ip)
        _save(store)
        await update.message.reply_html(f"✅ Now monitoring <code>{ip}</code>")

    # ── /remove ──────────────────────────────────────

    async def cmd_remove(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = str(update.effective_user.id)
        if not ctx.args:
            await update.message.reply_text("Usage: /remove <ip>")
            return
        ip = ctx.args[0].strip()
        store, user = _get_user(uid)
        if ip not in user.get("ips", []):
            await update.message.reply_text(f"Not found: {ip}")
            return
        user["ips"].remove(ip)
        _save(store)
        await update.message.reply_html(f"🗑 Removed <code>{ip}</code>")

    # ── /list ────────────────────────────────────────

    async def cmd_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = str(update.effective_user.id)
        store, user = _get_user(uid)
        ips      = user.get("ips", [])
        interval = user.get("interval", 60)
        active   = user.get("active", True)
        state    = "▶ active" if active else "⏸ paused"
        if not ips:
            await update.message.reply_text("No IPs monitored. Use /add <ip>")
            return
        lines = [f"<b>Monitored IPs</b> — {state} — every {interval} min\n"]
        for i, ip in enumerate(ips, 1):
            lines.append(f"{i}. <code>{ip}</code>")
        await update.message.reply_html("\n".join(lines))

    # ── /check ───────────────────────────────────────

    async def cmd_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        import asyncio
        uid = str(update.effective_user.id)
        store, user = _get_user(uid)
        ips = user.get("ips", [])
        if not ips:
            await update.message.reply_text("No IPs to check. Use /add <ip>")
            return
        await update.message.reply_text(f"🔍 Checking {len(ips)} IP(s)...")
        loop = asyncio.get_event_loop()
        for ip in ips:
            res  = await loop.run_in_executor(None, _check_ip, ip)
            text = _status_msg(ip, res)
            await update.message.reply_html(text)

    # ── /interval ────────────────────────────────────

    async def cmd_interval(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = str(update.effective_user.id)
        if not ctx.args:
            await update.message.reply_text("Usage: /interval <minutes>  (min: 5)")
            return
        try:
            mins = int(ctx.args[0])
        except ValueError:
            await update.message.reply_text("Please provide a number of minutes.")
            return
        if mins < 5:
            await update.message.reply_text("Minimum interval is 5 minutes.")
            return
        store, user = _get_user(uid)
        user["interval"] = mins
        _save(store)
        if user.get("active", True) and user.get("ips"):
            _schedule(ctx.job_queue, uid, mins)
        await update.message.reply_html(
            f"✅ Auto-check every <b>{mins} minutes</b>"
        )

    # ── /pause ───────────────────────────────────────

    async def cmd_pause(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = str(update.effective_user.id)
        store, user = _get_user(uid)
        user["active"] = False
        _save(store)
        for j in ctx.job_queue.get_jobs_by_name(f"fc_{uid}"):
            j.schedule_removal()
        await update.message.reply_text(
            "⏸ Auto-checks paused. Use /resume to restart."
        )

    # ── /resume ──────────────────────────────────────

    async def cmd_resume(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = str(update.effective_user.id)
        store, user = _get_user(uid)
        user["active"] = True
        interval = user.get("interval", 60)
        _save(store)
        if user.get("ips"):
            _schedule(ctx.job_queue, uid, interval)
        await update.message.reply_html(
            f"▶ Auto-checks resumed — every <b>{interval} min</b>"
        )

    # ── scheduled job ────────────────────────────────

    async def _job_check(ctx: ContextTypes.DEFAULT_TYPE):
        import asyncio
        uid   = ctx.job.data["uid"]
        store = _load()
        user  = store["users"].get(uid, {})
        if not user.get("active", True):
            return
        ips = user.get("ips", [])
        if not ips:
            return
        loop = asyncio.get_event_loop()
        for ip in ips:
            res  = await loop.run_in_executor(None, _check_ip, ip)
            text = _status_msg(ip, res)
            try:
                await ctx.bot.send_message(
                    chat_id=int(uid), text=text, parse_mode="HTML"
                )
            except Exception:
                pass

    # ── post_init: restore schedules ─────────────────

    async def _post_init(application):
        store = _load()
        for uid, user in store["users"].items():
            if user.get("active", True) and user.get("ips"):
                _schedule(
                    application.job_queue,
                    uid,
                    user.get("interval", 60),
                )

    app.post_init = _post_init

    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("add",      cmd_add))
    app.add_handler(CommandHandler("remove",   cmd_remove))
    app.add_handler(CommandHandler("list",     cmd_list))
    app.add_handler(CommandHandler("check",    cmd_check))
    app.add_handler(CommandHandler("interval", cmd_interval))
    app.add_handler(CommandHandler("pause",    cmd_pause))
    app.add_handler(CommandHandler("resume",   cmd_resume))

    return app


def run(token: str) -> None:
    app = _build_app(token)
    print("ForceCheck Bot started. Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


def main() -> None:
    from .colors import G, R, Y, C, N

    import argparse
    ap = argparse.ArgumentParser(
        prog="bot!",
        description="ForceCheck Telegram monitoring bot",
        epilog=(
            "Setup:\n"
            "  bot! --token <BOT_TOKEN>\n"
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
        print(f"  {R}Get a token from @BotFather on Telegram first.{N}")
        try:
            token = input(f"\n  Bot token: ").strip()
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
