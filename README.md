# ForceCheck

> **See your network from the world's eyes — right in your terminal.**

ForceCheck is a lightweight CLI tool for network engineers, sysadmins, and security researchers who want real-world network visibility without leaving the command line.

- **`ping`** — sends probes from 200+ nodes across 50+ countries simultaneously via [check-host.net](https://check-host.net), so you see latency and reachability as the world sees it — not just from your machine.
- **`bgp`** — queries the [lg.sdv.fr](http://lg.sdv.fr) looking glass (AS8839, France) to inspect live BGP routing paths, prefixes, and AS paths for any IP or subnet.

No account. No API key. One install.

---

## Install

```bash
pip install git+https://github.com/YOUR_USERNAME/ForceCheck.git
```

> Requires Python 3.8+

---

## Usage

### `ping` — Distributed Ping

Check reachability and latency from multiple locations worldwide.

```bash
ping 8.8.8.8
ping google.com
ping 1.1.1.1 -n 20
```

```
PING 8.8.8.8  —  check-host.net
10 probe nodes  |  https://check-host.net/check-report/...

  NODE                                 LOCATION                    RTT (ms)  STATUS
  ────────────────────────────────────────────────────────────────────────────────
  us1.node.check-host.net              Los Angeles, USA               12.3  OK
  de1.node.check-host.net              Frankfurt, Germany              8.7  OK
  ir1.node.check-host.net              Tehran, Iran                   21.4  OK
  ru1.node.check-host.net              Moscow, Russia                   —   timeout

  9/10 nodes responded (90%)
```

| Flag | Description |
|------|-------------|
| `-n`, `--nodes N` | Number of probe nodes, 1–220 (default: `10`) |

---

### `bgp` — BGP Route Lookup

Inspect BGP routing information for an IP, prefix, or AS number via the SdV looking glass.

```bash
bgp 1.1.1.1
bgp 8.8.8.0/24
bgp 185.220.101.0/24
```

---

## Why ForceCheck?

Most ping and BGP tools either require an account, hit rate limits, or only test from a single point. ForceCheck combines two reliable, open sources into a clean terminal interface — giving you a global perspective on any IP in seconds.

---

## Note on the `ping` command

This package installs a `ping` command. On Linux, if `~/.local/bin` is before `/bin` in your `$PATH`, it will shadow the system ping. To use the system ping explicitly:

```bash
/bin/ping 8.8.8.8    # system ping
ping 8.8.8.8         # ForceCheck
```

---

## License

MIT
