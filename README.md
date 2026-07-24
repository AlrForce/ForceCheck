<div align="center">

# ⚡ ForceCheck

### See your network from the world's eyes — right in your terminal.

**Distributed network diagnostics + a Telegram monitor bot, built for the real internet (and its filters).**

![version](https://img.shields.io/badge/version-2.0-22c55e?style=for-the-badge)
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

Released under the [MIT License](LICENSE) © 2026 [AlrForce](https://github.com/AlrForce) — free to use, modify, and share.

<div align="center">

**Telegram** [@ThisChannelisX](https://t.me/ThisChannelisX) · **GitHub** [github.com/AlrForce](https://github.com/AlrForce)

</div>

---

<div dir="rtl" align="right">

## 🇮🇷 راهنمای فارسی

### شبکه‌ات را از نگاه کل دنیا ببین؛ همین‌جا در ترمینال.

**ForceCheck** یک ابزار خط فرمان برای عیب‌یابی شبکه به‌صورت توزیع‌شده است، به‌همراه یک **ربات مانیتورینگ تلگرام**. مخصوص اینترنت واقعی ساخته شده؛ همان اینترنتی که فیلترینگ و تحریم دارد.

بیشتر ابزارها اینترنت را فقط از دید دستگاه خودت می‌سنجند. ForceCheck اما هر بررسی را از **بیش از ۱۰۰ نود در سراسر جهان** (هم داخل ایران و هم بین‌المللی) انجام می‌دهد تا دقیقاً بفهمی یک سایت یا سرور در چه وضعیتی است:

> آیا **در کل دنیا** در دسترس است، **فقط داخل ایران** کار می‌کند، **فیلتر** شده، یا اصلاً **قطع** است؟

کارش فقط تشخیص نیست؛ چیزهایی را هم که بی‌سروصدا اتصالت را خراب می‌کنند (مثل DNS مسموم یا MTU اشتباه) **درست می‌کند**، سرعتت را می‌سنجد، و سرورها و تانل‌هایت را **شبانه‌روز** از داخل تلگرام زیر نظر می‌گیرد.

<br>

### چرا ForceCheck؟

| | |
|---|---|
| 🌍 | بررسی توزیع‌شده از بیش از ۱۰۰ نود جهانی |
| 🇮🇷 | تفکیک **ایران / جهانی** در هر نتیجه، برای تشخیص سریع فیلترینگ |
| 🧰 | ابزارهای اصلاح: پیدا و تنظیم **بهترین DNS**، **بهترین MTU**، و **تست سرعت** |
| 🤖 | ربات تلگرام: مانیتور زمان‌بندی‌شده، بررسی دامنه، و کنترل اتصال تانل |
| 🪶 | بدون نیاز به حساب کاربری یا کلید API؛ نصب فقط با یک خط دستور |

<br>

### نصب

**لینوکس و مک:**
```bash
curl -sSL https://raw.githubusercontent.com/AlrForce/ForceCheck/master/install.sh | bash
```

**ویندوز (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/AlrForce/ForceCheck/master/install.ps1 | iex
```

> به Python نسخه ۳.۸ یا بالاتر نیاز دارد.

<br>

### دستورها

با زدن دستور `ff` منوی تعاملی باز می‌شود، یا می‌توانی هر دستور را مستقیم اجرا کنی:

| دستور | کاری که انجام می‌دهد |
|---|---|
| `info!` | اطلاعات IP و ASN: کشور، اپراتور، منطقه زمانی |
| `ping!` | پینگ توزیع‌شده از نودهای جهانی، با تفکیک ایران و خارج |
| `tcp!` | بررسی باز بودن یک پورت TCP از سراسر دنیا |
| `http!` | بررسی کد وضعیت و زمان پاسخ HTTP |
| `trace!` | traceroute توزیع‌شده (حالت ایران / جهانی / کل دنیا) |
| `bgp!` | نمایش prefix و ASN مبدأ از مسیر BGP |
| `domain!` | بررسی در دسترس بودن و اطلاعات WHOIS دامنه |
| `dns!` | یافتن و تنظیم بهترین DNS با بیشترین دسترسی به خارج |
| `mtu!` | پیدا کردن و تنظیم بهترین MTU برای سرور |
| `speed!` | تست سرعت: دانلود، آپلود و پینگ |
| `checkall!` | اجرای همزمان info و ping و tcp و bgp روی یک هدف |
| `bot!` | اجرای ربات مانیتورینگ تلگرام |

<br>

### معنی نتیجه‌ها

هر نتیجه به دو بخش **ایران** و **جهانی** تقسیم می‌شود؛ این‌طوری فیلترینگ را از قطعی واقعی تشخیص می‌دهی:

| وضعیت | معنی |
|:--:|---|
| ✅ **در دسترس جهانی** | هم از ایران و هم از خارج کار می‌کند؛ بدون مشکل |
| 🔴 **فقط دسترسی ایران** | داخل ایران جواب می‌دهد ولی از خارج نه (سرور ایرانی یا تحریم‌شده) |
| ⚠️ **محدود / فیلترشده** | از خارج کار می‌کند ولی داخل ایران فیلتر است |
| ❌ **در دسترس نیست** | هیچ نودی جواب نگرفت؛ خاموش یا کاملاً مسدود |

<br>

### ربات تلگرام

ربات را با `ff → bot!` راه‌اندازی کن (توکن را از [@BotFather](https://t.me/BotFather) بگیر). می‌توانی آن را در همین ترمینال اجرا کنی یا با systemd به‌صورت دائمی روشن نگه داری. قابلیت‌ها:

- 📡 مانیتور زمان‌بندی‌شده‌ی IP و دامنه، همراه با گزارش وضعیت
- 🔔 اعلان هوشمند: همیشه، یا فقط وقتی هدف «فقط دسترسی ایران» شد
- 🌐 بررسی دامنه (WHOIS و در دسترس بودن) به‌صورت لحظه‌ای
- 🔌 **کنترل تانل**: چون تانل‌ها از IP پرایوت استفاده می‌کنند و check-host نمی‌تواند به آن‌ها برسد، ربات از **خود سرور** به آن IP پینگ می‌زند؛ اگر جواب داد یعنی تانل وصل است
- 🔒 حالت خصوصی: محدود کردن ربات به چت آیدی خودت

<br>

<div align="center">

ساخته‌شده با ❤️ توسط **[AlrForce](https://github.com/AlrForce)**

کانال تلگرام: **[@ThisChannelisX](https://t.me/ThisChannelisX)**

</div>

</div>
