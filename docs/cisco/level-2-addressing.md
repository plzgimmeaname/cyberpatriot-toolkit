# Level 2 — Addressing and routing: two networks that can talk

Round 1 and 2 Packet Tracer tasks usually come down to this: a few subnets, a router between
them, and a list of addresses you must match exactly. The skill is arithmetic plus discipline,
not cleverness.

## Subnetting without the panic

You need three numbers for any subnet: **network address**, **mask**, and **usable range**.

The quick method uses the **block size** of the last octet the mask changes:

| Mask | CIDR | Block size | Usable hosts |
|---|---|---|---|
| 255.255.255.0 | /24 | 256 | 254 |
| 255.255.255.128 | /25 | 128 | 126 |
| 255.255.255.192 | /26 | 64 | 62 |
| 255.255.255.224 | /27 | 32 | 30 |
| 255.255.255.240 | /28 | 16 | 14 |
| 255.255.255.248 | /29 | 8 | 6 |
| 255.255.255.252 | /30 | 4 | 2 |

For `192.168.10.0/26`: block size 64, so the subnets start at `.0`, `.64`, `.128`, `.192`. The
first subnet is `192.168.10.0` (network), `.1`–`.62` (hosts), `.63` (broadcast). The next is
`192.168.10.64`.

Two rules that save time:

- **Usable = 2^(host bits) − 2.** The network and broadcast addresses are not host addresses.
- **A router-to-router link is a `/30`** unless the instructions say otherwise: two addresses, no
  waste. Packet Tracer also accepts `/31` on some platforms, but `/30` is the safe answer.

Drill this in the [Networking quiz](/tools/networking-quiz/): it generates subnetting questions
forever, which is exactly the repetition you need.

## The addressing table

Before configuring anything, copy the instructions into a table like this on paper or in a text
file. Every later step reads from it, and it is the fastest way to spot a requirement you missed.

| Device | Interface | Address / mask | Gateway | VLAN |
|---|---|---|---|---|
| R1 | G0/0 | 192.168.10.1 /26 | — | — |
| R1 | G0/1 | 192.168.20.1 /24 | — | — |
| R1 | S0/0/0 | 10.0.0.1 /30 | — | — |
| R2 | S0/0/0 | 10.0.0.2 /30 | — | — |
| PC-A | NIC | 192.168.10.10 /26 | 192.168.10.1 | — |

If the instructions give you a table, use **their** addresses, not a tidier scheme of your own.
Graders check the address, not the neatness.

## Configuring router interfaces

```text
enable
configure terminal
hostname R1
interface g0/0
 description LAN-A
 ip address 192.168.10.1 255.255.255.192
 no shutdown
 exit
interface g0/1
 description LAN-B
 ip address 192.168.20.1 255.255.255.0
 no shutdown
 exit
end
```

`no shutdown` is the single most common miss: a router interface is administratively down until
you enable it, and every `ping` fails while it is. Check with `show ip interface brief`: you want
`up` and `up`, not `administratively down`.

On the PCs, set address, mask and **default gateway**. A PC with a correct address and a missing
gateway can reach its own subnet and nothing else — a very common half-score.

## Static routes

A router only knows the networks directly connected to it. For anything else it needs a route.

```text
ip route 192.168.20.0 255.255.255.0 10.0.0.2    ! send that network to the next hop
ip route 0.0.0.0 0.0.0.0 10.0.0.2               ! default route: everything else goes here
```

Read them back with `show ip route`. The codes matter:

| Code | Meaning |
|---|---|
| `C` | Connected: an interface on this router is in that network |
| `L` | Local: the router's own interface address (/32) |
| `S` | Static: a route you typed |
| `S*` | Static default route |

If a network is missing from `show ip route`, no amount of pinging will fix it: the route is the
problem, not the cable.

## DHCP and DNS on the router

Small activities often ask for DHCP instead of static addresses on the PCs.

```text
ip dhcp excluded-address 192.168.10.1 192.168.10.10
ip dhcp pool LAN-A
 network 192.168.10.0 255.255.255.192
 default-router 192.168.10.1
 dns-server 192.168.10.5
 exit
```

- **Exclude** the router address and any statically assigned device, or DHCP will hand them out
  twice.
- Set the PCs to **DHCP** in Packet Tracer's IP configuration, then check with `ipconfig` in the
  PC's command prompt.
- If the pool is wrong, `show ip dhcp binding` shows what was handed out.

DNS in Packet Tracer is a server: **Services → DNS**, add the name-to-address records the
instructions list, and point the DHCP pool's `dns-server` at it.

## Verification that proves it works

Work bottom-up, because each step depends on the one before:

1. `show ip interface brief` on every router — all required interfaces up/up with the right address.
2. `show ip route` on every router — connected networks plus the static routes you expect.
3. From a PC: `ping` its own gateway. If that fails, the PC or the router interface is wrong.
4. From a PC: `ping` a host in the other subnet. If the gateway answers but this fails, it is a
   routing or return-route problem.
5. `traceroute` from PC to PC to see which hop drops the packet.

## What to build

**Task 1 — two LANs, one router.** Two switches, two PCs, one router with two LAN interfaces.
Address everything from a table you wrote yourself, then prove PC-A can ping PC-B.

**Task 2 — three routers, static routes.** Add a `/30` serial link between two routers and a third
network behind the second router. Give each router the routes it needs in both directions. The
classic mistake is configuring only one direction and wondering why the ping fails.

**Task 3 — DHCP.** Delete the static addresses on the PCs, configure a pool with the router as
gateway and a DNS server, and confirm the PCs lease addresses. Then break the exclusion list on
purpose and see the conflict.

## Self-check

- `192.168.1.130/26`: what are the network address, usable range and broadcast?
- Which command shows an interface that is administratively down, and how do you fix it?
- A PC can ping its gateway but not a host two routers away. What do you check first?
- Why must a DHCP pool exclude the router's own address?
- What does `S*` in `show ip route` mean?

Next: [Level 3 — switching and services](level-3-switching.md).
