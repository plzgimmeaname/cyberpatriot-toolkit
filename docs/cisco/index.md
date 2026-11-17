# Cisco networking, level by level

The Cisco part of a CyberPatriot round is two things: a **quiz** on networking theory, and a
**Packet Tracer activity** where you are given a half-built network and a list of requirements.
It is worth real points every round, and it is the part teams most often leave to the last
twenty minutes.

This section is a ladder. Each level adds one skill set and ends with something you can build
and check yourself. Work up from Level 1 even if you have done a round before: Level 1 is
where the CLI habits come from, and everything above it assumes them.

| Level | You can already… | Typical round |
|---|---|---|
| [Level 1 — Basics](level-1-basics.md) | Cable a small network, move around IOS, secure a device, save your work | Round 1 |
| [Level 2 — Addressing and routing](level-2-addressing.md) | Subnet by hand, fill an addressing table, give two LANs a route to each other | Round 1–2 |
| [Level 3 — Switching and services](level-3-switching.md) | Segment a network with VLANs, trunk it, route between VLANs, lock down ports, enable SSH | Round 2 |
| [Level 4 — State round](level-4-state.md) | ACLs, NAT, OSPF, and a full scenario finished and verified inside the time | State |

## How the Cisco part is scored

The Cisco challenge is scored separately from the operating-system images, and it grows
through the season. These are the officially published CyberPatriot 19 values:

| Round | Cisco points | What that usually means |
|---|---|---|
| Round 1 | 30 | A quiz plus a small Packet Tracer task: addressing, basic device setup |
| Round 2 | 30 | Same shape, slightly deeper: routing between two networks |
| State Round | 100 | A single larger scenario with several requirements, all-or-nothing per requirement |
| Semifinals | 240 (Platinum) | Everything above, faster, with more devices and less instruction |

> [!IMPORTANT]
> The topics are announced per round to coaches, and they change. This ladder covers the
> skills those topics are always built from, not a guess at this year's exact task. Read the
> round's topic list first, then pick the level that matches it.

## What you need before Level 1

1. A free **Cisco Networking Academy** account at [netacad.com](https://www.netacad.com/). Packet
   Tracer is a free download for account holders, and it runs on Windows, macOS and Linux.
2. Packet Tracer installed and opened once, so the device palette is not a surprise in a round.
3. The habit of **saving**: `copy running-config startup-config` after every working change. A
   perfect configuration that was never saved scores nothing after a reload.

## How to practise

- Build every task in this section yourself. Reading a command list feels like learning and is
  not: the points come from typing the right command in the right mode, under time.
- Use the [Networking quiz](/tools/networking-quiz/) for the theory half. It has explanations and
  endless subnetting practice, so you can drill the arithmetic until it is automatic.
- Use the [Command finder](/tools/commands/?os=cisco) filtered to Cisco when you forget a command. It is faster
  than scrolling this section mid-round.
- The long-form theory — OSI layers, TCP and UDP, ports, addressing tables, the full IOS cheat
  sheet — is the [Cisco networking and Packet Tracer reference](../guides/cisco-networking.md).
  This section tells you what to do with it; the reference explains why.

## The one rule that decides Cisco scores

Read the requirements list twice, out loud, and turn it into an **addressing table** before you
touch a device. Almost every lost Cisco point is a detail from the instructions: a VLAN number,
a hostname, a subnet that had to be `/30`, a password that had to be exactly what was asked.
The devices will do exactly what you tell them, including the wrong thing.
