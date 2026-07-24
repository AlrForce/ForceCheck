<div align="center">

# ⚡ ForceCheck

### See your network from the world's eyes — right in your terminal.

**Distributed network diagnostics + a Telegram monitor bot, built for the real internet (and its filters).**

![version](https://img.shields.io/badge/version-1.99-22c55e?style=for-the-badge)
![python](https://img.shields.io/badge/python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![platform](https://img.shields.io/badge/Linux_·_macOS_·_Windows-334155?style=for-the-badge)
![license](https://img.shields.io/badge/license-MIT-06b6d4?style=for-the-badge)

[**Install**](#-install) · [**Commands**](#-commands) · [**Telegram Bot**](#-telegram-bot) · [**فارسی**](#-فارسی)

</div>

---

## ✨ Why ForceCheck?

Most tools test the internet from **your** machine. ForceCheck tests it from **100+ probe nodes around the world** — Iranian *and* international — so you see what everyone else sees:

> Is a host up **globally**, only inside **Iran**, **filtered**, or completely **down**?

And it doesn't stop at diagnosis — it **fixes** the things that quietly break your connection (DNS poisoning, wrong MTU), benchmarks your speed, and watches your servers & tunnels **24/7** from Telegram.

| | |
|---|---|
| 🌍 | **Distributed** checks from 100+ global nodes (via check-host.net) |
| 🇮🇷 | **Iran vs Global** split on every result — spot filtering at a glance |
| 🧰 | **Fix-it tools** — best-DNS finder, optimal-MTU tuner, speed test |
| 🤖 | **Telegram bot** — scheduled monitoring, domain WHOIS, tunnel uptime |
| 🪶 | **No account, no API key**, one-line install, minimal dependencies |

---

## 🚀 Install

**Linux / macOS**
```bash
curl -sSL https://raw.githubusercontent.com/AlrForce/ForceCheck/master/install.sh | bash
```

**Windows — PowerShell**
```powershell
irm https://raw.githubusercontent.com/AlrForce/ForceCheck/master/install.ps1 | iex
```

**Windows — Command Prompt (cmd)**
```bat
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/AlrForce/ForceCheck/master/install.ps1 | iex"
```

> Requires **Python 3.8+**. `irm` exists only in PowerShell — in cmd use the command above (it launches PowerShell for you).

---

## 🧭 Commands

Run the interactive menu with **`ff`**, or call any command directly.

| Command | What it does |
|---|---|
| **`info!`** | IP & ASN intel — country, ISP, ASN, timezone, reverse DNS |
| **`ping!`** | Distributed ping from 100+ nodes, split **Iran / Global** |
| **`tcp!`** | Is a TCP port open? tested worldwide (`tcp! host 443`) |
| **`http!`** | HTTP status code & response time from global nodes |
| **`trace!`** | Distributed traceroute — **Iran / Global / World** modes |
| **`bgp!`** | BGP prefix & origin ASN lookup (RIPEstat) |
| **`domain!`** | Domain availability & WHOIS (registrar, dates, nameservers) |
| **`dns!`** | Benchmark Iranian + global resolvers, then **set the best** on your OS |
| **`mtu!`** | Find the **optimal MTU** via Path MTU Discovery, then set it |
| **`speed!`** | Internet speed test — download / upload / latency (Cloudflare) |
| **`checkall!`** | `info + ping + tcp + bgp` on one target, in parallel |
| **`bot!`** | Launch the Telegram monitoring bot |
| **`ff`** | Interactive menu for everything |

```console
$ ff

────────────────────────────────────────────────────────
   1  info!       IP & ASN intel
   2  ping!       global ping
   3  tcp!        port reachability
   4  http!       HTTP status
   5  trace!      path trace
   6  bgp!        BGP routing
   7  domain!     domain & WHOIS
   8  dns!        best DNS finder
   9  mtu!        optimal MTU finder
  10  speed!      internet speed test
  11  checkall!   all checks at once
  12  bot!        Telegram monitor
  ──────────────────────────────────────────────────────
  Enter a number above  —  or run any command directly:
  ping!  info!  tcp!  trace!  bgp!  domain!  dns!  mtu!  speed!
```

**Examples**
```bash
ping!     8.8.8.8              # is it reachable inside Iran and globally?
tcp!      example.com 443      # is HTTPS open worldwide?
dns!                           # find & set the fastest working DNS
mtu!                           # discover the best MTU for this server
speed!                         # download / upload / latency
checkall! google.com          # info + ping + tcp + bgp at once
```

---

## 🎯 What the results mean

Every reachability result is split into **Iran** and **Global** — that's how you tell filtering apart from a real outage.

| Status | Meaning |
|:--:|---|
| ✅ **Globally Accessible** | Works from **both** Iran and abroad — no blocking |
| 🔴 **Iran Access Only** | Answers **inside Iran** but not abroad (Iran-only server, or sanctioned/blocked globally) |
| ⚠️ **Restricted · Filtered** | Works **abroad** but blocked inside Iran — i.e. **filtered by Iran** |
| ❌ **Unreachable** | No node anywhere got a reply — down or fully blocked |

> A target counts as reachable only when **enough** nodes answer: **≥ 2** Iranian and/or **≥ 5** global — so one flaky node never gives a false result.

---

## 🤖 Telegram Bot

Turn ForceCheck into an always-on monitor. Set it up with **`ff → bot!`** (paste a token from [@BotFather](https://t.me/BotFather)) and run it in this terminal or **permanently via systemd**.

- 📡 **Watch IPs & domains** on a schedule and get status reports
- 🔔 **Smart alerts** — *always*, or *only when a target is Iran-Access-Only*
- 🌐 **Domain Check** — WHOIS & availability on demand
- 🔌 **Tunnel Check** — pings your tunnel's **private** IP from the server itself (check-host can't reach private IPs); a reply means the tunnel is up. Scheduled with an *on-down* alert policy.
- 🔒 **Private mode** — restrict the bot to your own chat IDs
- ⚙️ **Always-on** — one-tap systemd service that survives reboots

---

## 🛠 Under the hood

- **Distributed checks** via [check-host.net](https://check-host.net) · **BGP** via [RIPEstat](https://stat.ripe.net) · **WHOIS/RDAP** via [rdap.org](https://rdap.org) · **geo** via [ip-api.com](https://ip-api.com) · **DNS & MTU** probed directly, no dependencies
- Pure-Python, only needs `requests` (and `python-telegram-bot` for the bot)
- Self-updating: `ff → u` pulls the latest version from GitHub

---

## 📜 License

MIT © [AlrForce](https://github.com/AlrForce)

<div align="center">

**Telegram** [@ThisChannelisX](https://t.me/ThisChannelisX) · **GitHub** [github.com/AlrForce](https://github.com/AlrForce)

</div>

---

<div dir="rtl" align="right">

## 🇮🇷 فارسی

### شبکه‌ات را از چشم تمام دنیا ببین — مستقیم در ترمینال.

**ForceCheck** یک ابزار خط‌فرمان برای عیب‌یابی شبکه به‌صورت توزیع‌شده است، به‌همراه یک **ربات مانیتورینگ تلگرام** — ساخته‌شده برای اینترنت واقعی (و فیلترینگش).

اکثر ابزارها اینترنت را فقط از **دستگاه خودت** تست می‌کنند؛ ولی ForceCheck از **بیش از ۱۰۰ نود در سراسر دنیا** (ایرانی و بین‌المللی) تست می‌کند تا ببینی یک هاست **در کل دنیا** در دسترس است، **فقط داخل ایران**، **فیلتر** شده، یا کاملاً **قطع** است.

فقط تشخیص نمی‌دهد — چیزهایی که بی‌سروصدا اتصالت را خراب می‌کنند (DNS مسموم، MTU اشتباه) را هم **درست می‌کند**، سرعت را می‌سنجد، و سرورها و تانل‌هایت را **۲۴ ساعته** از تلگرام زیر نظر می‌گیرد.

**ویژگی‌ها:**
- 🌍 چک توزیع‌شده از بیش از ۱۰۰ نود جهانی
- 🇮🇷 تفکیک **ایران / جهانی** در هر نتیجه — تشخیص فوری فیلترینگ
- 🧰 ابزارهای اصلاح: **پیدا و ست کردن بهترین DNS**، **بهترین MTU**، **تست سرعت**
- 🤖 ربات تلگرام: مانیتور زمان‌بندی‌شده، WHOIS دامنه، **بررسی اتصال تانل**
- 🪶 بدون اکانت، بدون API key، نصب یک‌خطی

**نصب (لینوکس):**
```bash
curl -sSL https://raw.githubusercontent.com/AlrForce/ForceCheck/master/install.sh | bash
```

**نصب (ویندوز — PowerShell):**
```powershell
irm https://raw.githubusercontent.com/AlrForce/ForceCheck/master/install.ps1 | iex
```

**دستورها:** با زدن `ff` منوی تعاملی باز می‌شود، یا هر دستور را مستقیم اجرا کن:
`info!` اطلاعات IP و ASN ·
`ping!` پینگ توزیع‌شده ·
`tcp!` بررسی باز بودن پورت ·
`http!` وضعیت HTTP ·
`trace!` traceroute ·
`bgp!` مسیر BGP ·
`domain!` WHOIS دامنه ·
`dns!` بهترین DNS ·
`mtu!` بهترین MTU ·
`speed!` تست سرعت ·
`checkall!` همه با هم ·
`bot!` ربات تلگرام

**معنی نتایج:**
- ✅ **Globally Accessible** — هم از ایران هم از خارج کار می‌کند
- 🔴 **Iran Access Only** — فقط داخل ایران جواب می‌دهد
- ⚠️ **Restricted · Filtered** — از خارج کار می‌کند ولی **داخل ایران فیلتر** است
- ❌ **Unreachable** — هیچ نودی جواب نگرفت

**ربات تلگرام** با `ff → bot!` راه‌اندازی می‌شود؛ می‌تواند IP و دامنه را زمان‌بندی‌شده مانیتور کند، دامنه‌ها را WHOIS بگیرد، و **اتصال تانل** را (با پینگ لوکال IP پرایوت از خود سرور) بررسی کند — چون تانل‌ها از IP پرایوت استفاده می‌کنند که check-host نمی‌تواند به آن‌ها برسد.

ساخته‌شده با ❤️ توسط [AlrForce](https://github.com/AlrForce) — کانال تلگرام: [@ThisChannelisX](https://t.me/ThisChannelisX)

</div>
