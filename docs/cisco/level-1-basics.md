# Level 1 — Basics: cables, the CLI, and a device that stays configured

This level is about the two things that make the rest possible: knowing what connects to what,
and being able to move around Cisco IOS without thinking. Everything here should take an
afternoon, and it is the difference between "I know what a VLAN is" and "I can configure one".

## Cables and ports

Packet Tracer marks a wrong cable, and a quiz will ask which cable goes where.

| Cable | Connects | Why |
|---|---|---|
| **Straight-through** | Unlike devices: PC–switch, switch–router, PC–router | Transmit on one pair meets receive on the other |
| **Crossover** | Like devices: switch–switch, router–router, PC–PC | Both ends transmit on the same pair, so the pairs are crossed |
| **Rollover (console)** | PC serial/USB port to a device's **console** port | Gives you the CLI before the device has any network settings |
| **Serial (DCE/DTE)** | Router–router WAN links | Older WAN links; in Packet Tracer the DCE end needs `clock rate` |

Real hardware has **auto-MDIX**, which makes straight-through work almost everywhere. Packet
Tracer still grades the cable type in some activities, so learn the rule rather than relying on
it.

A device's **console** port is for configuration; its **Ethernet** ports are for traffic. In
Packet Tracer, click a PC → **Desktop** → **Terminal** with 9600 baud, 8 data bits, no parity,
1 stop bit, no flow control, then press Enter to get a prompt.

## IOS modes

| Prompt | Mode | What it is for |
|---|---|---|
| `Router>` | User EXEC | Looking around. Almost nothing changes here. |
| `Router#` | Privileged EXEC | `show` commands, `copy`, `reload`, and the door to configuration |
| `Router(config)#` | Global configuration | Settings that apply to the whole device |
| `Router(config-if)#` | Interface configuration | One interface |
| `Router(config-line)#` | Line configuration | Console and VTY (remote) logins |

| From | To | Command |
|---|---|---|
| `>` | `#` | `enable` |
| `#` | `(config)#` | `configure terminal` |
| any config mode | one level up | `exit` |
| any config mode | `#` | `end` (or Ctrl+Z) |
| `(config-if)#` | run a show command | `do show ip interface brief` |

## A device you can leave alone

This is the minimum for any switch or router in a scored activity, in order:

```text
enable
configure terminal
hostname SW1
enable secret Str0ng!Pass
service password-encryption
no ip domain-lookup
banner motd #Authorised access only#
line console 0
 password C0nsole!Pass
 login
 exec-timeout 5 0
 logging synchronous
 exit
line vty 0 4
 password Vty!Pass
 login
 exec-timeout 5 0
 exit
end
copy running-config startup-config
```

What each line is for:

- **`hostname`** — the instructions usually name the device. Graders check the name.
- **`enable secret`** — protects privileged mode with a hash. Never use `enable password`: it is
  stored in clear text and is considered wrong in most activities.
- **`service password-encryption`** — hides the remaining plain-text passwords (weak, type 7, but
  commonly required).
- **`no ip domain-lookup`** — stops a mistyped command hanging while the device tries DNS.
- **`banner motd`** — the legal warning. The delimiter (`#`) cannot appear in the text.
- **`line console 0` / `line vty 0 4`** — console and remote logins. `login` is what makes the
  password actually be asked for; without it the password does nothing.
- **`exec-timeout 5 0`** — logs out idle sessions (minutes then seconds).
- **`logging synchronous`** — stops log messages cutting your typing in half.

> [!WARNING]
> `copy running-config startup-config` (or `write memory`) is not optional. Packet Tracer
> activities are graded on the running config, but a real device and some activities reload. If
> you configured for twenty minutes and did not save, you have configured for twenty minutes in
> a simulator's memory.

## Reading the device without breaking it

```text
show ip interface brief
show interfaces status
show running-config
show startup-config
show version
show mac address-table
show users
```

- `show ip interface brief` — every interface, its address, and **up/up** or down. This is the
  first command to run when something does not work.
- `show interfaces status` — switch ports: connected or not, VLAN, speed, duplex.
- `show running-config` — what the device is doing now. `show startup-config` — what it will do
  after a reload. If they differ, you have not saved.
- `show mac address-table` — which MAC address the switch has learned on which port.

## What to build

**Task 1 — two PCs and a switch.** Place two PCs and a 2960 switch, connect them with
straight-through cables, give the PCs `192.168.10.10` and `192.168.10.11` with mask
`255.255.255.0`, then `ping` one from the other. Then change one PC to `192.168.20.10` and watch
the ping fail: you have just demonstrated what a subnet is.

**Task 2 — secure a switch.** Apply the configuration above to the switch with the hostname
`SW1`. Check it with `show running-config`. Save. Then `reload` the switch and confirm the
hostname and passwords survived.

**Task 3 — break it and fix it.** Shut down an interface with `shutdown`, watch
`show ip interface brief` change, bring it back with `no shutdown`. Cable a PC to another PC with
a crossover, then with a straight-through, and explain the difference.

## Self-check

- Which cable connects a switch to another switch, and why?
- What is the difference between `enable secret` and `enable password`?
- You set a console password but the device never asks for it. What did you forget?
- Which command tells you whether an interface is up, and what does `up/down` mean?
- You changed the hostname, reloaded, and it is gone. Why?

Next: [Level 2 — addressing and routing](level-2-addressing.md).
