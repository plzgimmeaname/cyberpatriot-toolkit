# Level 3 — Switching and services: VLANs, trunks and locked-down ports

Round 2 and State scenarios add a switch layer: one physical switch carries several networks,
one cable carries them all to the router, and the ports have to stay locked down. This is where
teams start losing points to small details — a wrong VLAN number, a trunk without the VLAN
allowed, a port-security violation left in `err-disabled`.

## VLANs

A **VLAN** splits a switch into separate broadcast domains. Two PCs on the same switch in
different VLANs cannot talk without a router, exactly as if they were on different switches.

```text
enable
configure terminal
vlan 10
 name STAFF
 exit
vlan 20
 name STUDENTS
 exit
interface range fa0/1 - 10
 switchport mode access
 switchport access vlan 10
 exit
interface range fa0/11 - 20
 switchport mode access
 switchport access vlan 20
 exit
end
```

- A port is **access** (one VLAN, for a PC) or **trunk** (many VLANs, between switches or to a
  router).
- `switchport mode access` before assigning the VLAN, or the port may end up in the wrong mode.
- Verify with `show vlan brief`: each port must be listed under its VLAN, not under VLAN 1.

> [!WARNING]
> VLAN 1 is the default and cannot be deleted. Leaving unused ports in VLAN 1 is usually fine;
> putting the staff PCs there when the instructions say VLAN 10 is a lost requirement.

## Trunks

A **trunk** carries several VLANs between devices, tagging each frame with an 802.1Q header.

```text
interface g0/1
 switchport mode trunk
 switchport trunk allowed vlan 10,20
 switchport trunk native vlan 99
 exit
```

- `allowed vlan` is a common requirement: the trunk must carry exactly the VLANs asked for.
  Leaving it at "all" fails an activity that says "only VLANs 10 and 20".
- The **native VLAN** is the one sent untagged. If the instructions name it, set it on both
  ends; a mismatch is both a fault and a security issue.
- Verify with `show interfaces trunk`: you want the mode, the allowed list, and the native VLAN
  to match the instructions.

## Routing between VLANs: router-on-a-stick

To let VLAN 10 talk to VLAN 20 you need a router with one physical link carrying both. The
physical interface stays unaddressed; **subinterfaces** hold the gateway addresses.

```text
interface g0/0
 no shutdown
 exit
interface g0/0.10
 encapsulation dot1Q 10
 ip address 192.168.10.1 255.255.255.0
 exit
interface g0/0.20
 encapsulation dot1Q 20
 ip address 192.168.20.1 255.255.255.0
 exit
```

- The number after `dot1Q` is the VLAN ID and the subinterface number is only a label — but
  matching them keeps you sane.
- The switch port facing the router must be a trunk.
- Every PC's default gateway is its own VLAN's subinterface address.
- Verify with `show ip route` (both networks as connected) and a ping across VLANs.

## Port security

This is a scored security requirement, not a networking nicety.

```text
interface fa0/1
 switchport mode access
 switchport port-security
 switchport port-security maximum 1
 switchport port-security mac-address sticky
 switchport port-security violation shutdown
 exit
```

| Setting | What it does |
|---|---|
| `maximum 1` | Only one MAC address may use the port |
| `mac-address sticky` | Learns the first MAC and remembers it in the config |
| `violation shutdown` | Default: err-disables the port on a violation |
| `violation restrict` | Drops the traffic, logs it, port stays up |
| `violation protect` | Drops the traffic silently |

Verify with `show port-security interface fa0/1` and `show port-security address`.

**Recovering an err-disabled port** (you will need this after a violation):

```text
interface fa0/1
 shutdown
 no shutdown
 exit
```

Also useful, and often asked for: **BPDU guard** and **portfast** on access ports.

```text
interface range fa0/1 - 20
 spanning-tree portfast
 spanning-tree bpduguard enable
 exit
```

## SSH instead of Telnet

Plain Telnet sends passwords in clear text, so scenarios ask for SSH. Five parts, all needed:

```text
hostname R1
ip domain-name example.local
crypto key generate rsa modulus 2048
ip ssh version 2
username admin secret Adm1nPass!
line vty 0 4
 transport input ssh
 login local
 exit
```

- No domain name, no RSA key: the key generation needs a fully qualified name.
- `login local` plus a `username … secret …` is what authenticates the SSH session.
- `transport input ssh` refuses Telnet on those lines.
- Verify with `show ip ssh` (version 2 enabled) and `show running-config | section line vty`.

## Spanning tree, in one paragraph

Switches connected in a loop would broadcast forever. **STP** elects a root bridge and blocks the
redundant ports so there is exactly one path. In activities you rarely configure it; you read it
with `show spanning-tree` and you protect the edge with `portfast`/`bpduguard`. A port stuck in
`BLK` or `LSN` is usually STP doing its job, not a fault.

## What to build

**Task 1 — two VLANs, one trunk.** One switch, four PCs, two VLANs, a trunk to a router with two
subinterfaces. Prove PC in VLAN 10 can ping PC in VLAN 20.

**Task 2 — port security.** Lock one access port to a single sticky MAC with `violation shutdown`.
Connect a different PC to that port, watch the port err-disable, then recover it.

**Task 3 — SSH only.** Configure SSH with a local admin, set `transport input ssh`, and confirm
Telnet is refused while SSH works. Then break the domain name on purpose and see the key
generation fail.

## Self-check

- What is the difference between an access port and a trunk port?
- Why does the router use subinterfaces instead of one address on the physical port?
- You set `switchport trunk allowed vlan 10` and VLAN 20 stops working. Why?
- Port security err-disabled a port. What two commands bring it back?
- Name the five things SSH needs before a client can connect.

Next: [Level 4 — State round](level-4-state.md).
