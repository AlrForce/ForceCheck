# ForceCheck

> **See your network from the world's eyes — right in your terminal.**

ForceCheck is a lightweight CLI tool for network engineers, sysadmins, and security researchers who want real-world network visibility without leaving the command line.

- **`ping!`** — distributed ping from 200+ nodes across 50+ countries via [check-host.net](https://check-host.net)
- **`tcp!`** — distributed TCP port reachability check from global nodes
- **`bgp!`** — BGP route lookup via [lg.sdv.fr](http://lg.sdv.fr) looking glass (AS8839)
- **`trace!`** — distributed traceroute from multiple global nodes
- **`http!`** — HTTP status and response time check from global nodes
- **`info!`** — IP and ASN WHOIS lookup via RDAP
- **`domain!`** — domain availability & WHOIS
- **`dns!`** — finds the fastest DNS with the best access to the outside, then sets it on your OS
- **`mtu!`** — finds the optimal MTU via Path MTU Discovery, then sets it on your interface
- **`checkall!`** — run all checks in parallel and display a unified summary
- **`ff`** — interactive menu for all tools

No account. No API key. One install.

--- 

## Install

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

> `irm` only exists in PowerShell. In cmd, use the second command above (it launches PowerShell for you).

> Requires Python 3.8+

---

## Usage

### Interactive menu

```bash
ff
```

```
╔══════════════════════════════════════════════════════╗
║               ForceCheck  v1.0.0                     ║
║    network diagnostics · from the world's eyes       ║
╚══════════════════════════════════════════════════════╝

  1  ping!        distributed ping
  2  bgp!         BGP route lookup
  3  trace!       distributed traceroute
  4  http!        HTTP check from global nodes
  5  whois!       IP / ASN WHOIS via RDAP
  6  checkall!    run all checks in parallel
  ──────────────────────────────────────────────────────
  u  update       download latest version from GitHub
  a  about        about & support
  x  uninstall    remove ForceCheck from this system
  0  exit

  Select:
```

### Direct commands

```bash
ping!     8.8.8.8
ping!     google.com -n 20

bgp!      1.1.1.1
bgp!      8.8.8.0/24

trace!    8.8.8.8
trace!    google.com -n 3

http!     https://example.com
http!     https://example.com -n 20

whois!    8.8.8.8
whois!    google.com
whois!    AS15169

checkall! 8.8.8.8
checkall! google.com
```

---

## License

MIT
