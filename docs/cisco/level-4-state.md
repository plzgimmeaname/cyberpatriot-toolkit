# Level 4 — State round: ACLs, NAT, OSPF, and finishing on time

The State Round Cisco task is worth 100 points and is usually one scenario with many
requirements: several networks, a router or two, a server, and a list of things that must work
and things that must not. Semifinals is the same at 240 points with more devices.

Nothing here is new theory. It is the same commands, applied to a bigger picture, under a
requirement list that grades each line separately. Read the requirements as a checklist, not as
a story.

## Access control lists

An ACL is a numbered or named list of `permit`/`deny` rules, applied to an interface in one
direction. Rules are read top to bottom and **the first match wins**. There is an invisible
`deny any` at the end.

**Standard** ACLs match only the source address. **Extended** ACLs match protocol, source,
destination and port.

```text
! standard: allow one subnet out, deny the rest
access-list 10 permit 192.168.10.0 0.0.0.255
interface g0/1
 ip access-group 10 out
 exit

! extended: web traffic to the server, everything else from that subnet denied
access-list 100 permit tcp 192.168.20.0 0.0.0.255 host 192.168.30.10 eq 80
access-list 100 deny ip any any
interface g0/0
 ip access-group 100 in
 exit
```

- The **wildcard mask** is the inverse of the subnet mask: `/24` → `0.0.0.255`.
- `host 192.168.30.10` means that single address; `any` means everything.
- **Placement:** standard ACLs close to the destination, extended ACLs close to the source. Put
  them where they filter the least unnecessary traffic.
- One ACL per interface, per direction, per protocol. Applying a second one replaces the first.

Verify with `show access-lists` (rule hit counts) and `show ip interface g0/0` (which ACL is
applied where). A wrong direction (`in` instead of `out`) is the classic error: the rules are
right and nothing is filtered.

> [!CAUTION]
> Adding `deny ip any any` at the end is good practice for clarity but it will also block your
> own management traffic if you apply the ACL to the wrong interface. Test with `ping` from both
> sides.

## NAT and PAT

NAT translates private addresses to a public one so inside hosts can reach an outside network.

```text
! 1. say which interfaces are inside and outside
interface g0/0
 ip nat inside
 exit
interface g0/1
 ip nat outside
 exit

! 2. say which traffic gets translated
access-list 1 permit 192.168.10.0 0.0.0.255

! 3. translate it to the outside interface address (PAT)
ip nat inside source list 1 interface g0/1 overload
```

- `overload` is PAT: many inside hosts share one public address, told apart by port numbers.
- The ACL for NAT is **not** a security ACL; it selects traffic. It does not need a `deny`.
- Verify with `show ip nat translations` after a ping from inside, and `show ip nat statistics`.
- If translations appear but pings fail, the problem is routing or the outside device, not NAT.

## OSPF, single area

When the scenario has several routers and says "dynamic routing", it usually means OSPF area 0.

```text
router ospf 1
 router-id 1.1.1.1
 network 192.168.10.0 0.0.0.255 area 0
 network 10.0.0.0 0.0.0.3 area 0
 passive-interface g0/0
 exit
```

- `network` takes a **wildcard** and the **area**, not a mask.
- `passive-interface` on LAN interfaces stops OSPF hello packets going to PCs while still
  advertising the network. It is a common requirement.
- The `router-id` should be unique per router; using the highest loopback address is the usual
  convention.
- Verify with `show ip ospf neighbor` (you want `FULL`), `show ip route ospf` (routes with `O`),
  and `show ip protocols`.

## The State-round workflow

Time is the requirement that fails most often. A workable split for a 100-point task:

| Minutes | Do |
|---|---|
| 0–5 | Read the requirements twice. Build the addressing table. Note every exact name, VLAN, password and subnet. |
| 5–10 | Cable the topology. Check link lights before configuring anything. |
| 10–30 | Configure device by device: hostnames, addresses, VLANs, routing. |
| 30–40 | Services: DHCP, DNS, NAT, ACLs, SSH, port security. |
| 40–50 | Verify end to end: ping every pair the requirements name, then `traceroute`. |
| 50–55 | Re-read the requirement list line by line and tick each one off. |
| 55–60 | `copy running-config startup-config` on every device, then re-check the requirement you are least sure about. |

Two habits that pay for themselves:

1. **Configure in the same order every time.** Same order means the same mistakes are found the
   same way.
2. **Save as you go**, not at the end. A crash or a reload at minute 50 is survivable if the work
   was saved at minute 30.

## When it does not work

Work down the layers instead of guessing. One command per step:

| Symptom | Check first | Likely cause |
|---|---|---|
| Interface is `administratively down` | `show ip interface brief` | Missing `no shutdown` |
| `up/down` on an interface | `show interfaces` | Cable, wrong port, or the far end is down |
| PC cannot ping its gateway | PC IP config, `show ip interface brief` | Wrong mask, wrong VLAN, port down |
| Gateway answers, remote subnet does not | `show ip route` on every router | Missing or wrong static route |
| Route exists, ping still fails | `show ip route` on the *return* path | Route missing in the other direction |
| VLAN hosts cannot reach each other | `show interfaces trunk`, `show vlan brief` | Trunk missing the VLAN, no subinterface |
| SSH refused | `show ip ssh`, `show running-config | section line vty` | No RSA key, `transport input telnet`, missing `login local` |
| Port dead after cabling a new PC | `show port-security interface` | Port security violation, port err-disabled |
| Web works, ping does not (or vice versa) | `show access-lists` | ACL order, direction, or implicit deny |
| NAT shows no translations | `show ip nat statistics` | Wrong inside/outside, or the NAT ACL matches nothing |
| OSPF neighbours not forming | `show ip ospf neighbor` | Mismatched area, wrong wildcard, passive on the wrong interface |

## What to build

**Task 1 — the full scenario.** Two routers, two switches, four VLANs, a server, OSPF between
the routers, PAT to an "internet" router, an extended ACL that allows only HTTP to the server
from one VLAN and blocks it from another, SSH on all devices, port security on access ports.
Write the requirements list yourself first, then grade your own work against it.

**Task 2 — break your own network.** Introduce one fault at a time (wrong mask, missing route,
ACL in the wrong direction, native VLAN mismatch) and find it using only `show` commands and
`ping`. This is the actual State-round skill.

**Task 3 — do Task 1 again in 45 minutes**, from an empty Packet Tracer, with the requirements
list only. Then in 30.

## Self-check

- Where do you place a standard ACL, and where an extended one, and why?
- What does the wildcard `0.0.0.255` match?
- Why does a NAT ACL not need a `deny` statement?
- Two routers are neighbours but routes are missing. What do you check?
- Which single command proves a configuration will survive a reload?

Back to the [overview](index.md), or use the [Networking quiz](/tools/networking-quiz/) and the
[Command finder](/tools/commands/?os=cisco) for the last pass before a round.
