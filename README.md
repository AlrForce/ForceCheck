# netcheck

Distributed **ping** from 200+ global nodes and **BGP** route lookup — straight from your terminal.

| Command | Source |
|---------|--------|
| `ping`  | [check-host.net](https://check-host.net) — up to 220 probe nodes worldwide |
| `bgp`   | [lg.sdv.fr](http://lg.sdv.fr) — AS8839 looking glass |

---

## Install

```bash
pip install git+https://github.com/YOUR_USERNAME/netcheck.git
```

> Requires Python 3.8+

---

## Usage

### ping

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

Options:

```
ping <host> [-n NODES]

  -n, --nodes N    number of probe nodes, 1-220 (default: 10)
```

---

### bgp

```bash
bgp 1.1.1.1
bgp 8.8.8.0/24
bgp 185.220.101.0/24
```

Queries the [lg.sdv.fr](http://lg.sdv.fr) looking glass (AS8839, France) and prints the BGP route output.

---

## Note on `ping` command

Installing this package adds a `ping` command via pip's script directory.  
On Linux, if `~/.local/bin` comes before `/bin` in your `PATH`, this will shadow the system `ping`.

To keep both, you can call the system ping explicitly:
```bash
/bin/ping 8.8.8.8        # system ping
ping 8.8.8.8             # this tool
```

---

## License

MIT
