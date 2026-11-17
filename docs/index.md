# CyberPatriot Toolkit

Step-by-step checklists, beginner guides and hardening scripts for practicing **CyberPatriot** image challenges.

## New here? Start with these (in order)

1. [What is CyberPatriot?](start-here/what-is-cyberpatriot.md): how images, the README and scoring work
2. [Things that lose points](guides/things-that-lose-points.md): read this **before** touching an image
3. [Reading the README](start-here/reading-the-readme.md): the most important 10 minutes of a round
4. [Round game plan](start-here/round-game-plan.md): what to do in your 4 hours
5. Never used a terminal? [Linux terminal basics](start-here/linux-terminal-basics.md) · [PowerShell basics](start-here/powershell-basics.md)

## Pick your checklist

| Operating system | CyberPatriot 19 rounds | Points per round | Checklist |
|---|---|---|---|
| **Windows 11** (and 10) | Round 1, Round 2 | 100 | [Windows 10 / 11](checklists/windows-10-11.md) |
| **Windows Server 2022** (2016/2019) | Round 2, State, Semifinals | 100 | [Windows Server](checklists/windows-server.md) |
| **Linux Mint 21** | Round 1, Round 2, State, Semifinals | 100 | [Linux Mint](checklists/linux-mint.md) |
| **Ubuntu 24** | State round (22 in the training rounds) | 100 | [Ubuntu](checklists/ubuntu.md) |
| **Debian 12** | Not in CP-19 (older images) | — | [Debian](checklists/debian.md) |
| **FreeBSD** | Not in CP-19 | — | [FreeBSD](checklists/freebsd.md) |

The Cisco networking challenge is worth **30 points** in Round 1, **30** in Round 2, **100** in the State round and **240** in the Semifinals, plus **80** for the web-based challenge in the Semifinals. Totals: Round 1 **230**, Round 2 **330**, State **400**, Semifinals **620** (Platinum; 480 Gold, 300 Silver).

## Cisco networking, basics → State

A ladder of four levels, each with the commands, three things to build, and a self-check. Start at Level 1 even if you have done a round: that is where the CLI habits come from.

- [Overview and level ladder](cisco/index.md): what the Cisco part is, how it is scored, how to practise
- **Level 1 — Basics**: cables, IOS modes, a device that stays configured ([page](cisco/level-1-basics.md))
- **Level 2 — Addressing and routing**: subnetting, addressing tables, static routes, DHCP ([page](cisco/level-2-addressing.md))
- **Level 3 — Switching and services**: VLANs, trunks, router-on-a-stick, port security, SSH ([page](cisco/level-3-switching.md))
- **Level 4 — State round**: ACLs, NAT, OSPF, the State workflow and a troubleshooting table ([page](cisco/level-4-state.md))
- [Cisco networking and Packet Tracer reference](guides/cisco-networking.md): the long-form theory, OSI layers, ports and the full IOS cheat sheet

## Guides

- [Forensics questions](guides/forensics-questions.md): hashes, decoding, finding files, reading logs
- [Linux critical service hardening](guides/linux-service-hardening.md): Apache, Nginx, PHP, MySQL, FTP, Samba, DNS, Postfix
- [Glossary](guides/glossary.md): every acronym explained
- [For mentors and teachers](guides/for-mentors-and-teachers.md): running practice sessions with this toolkit

## Scripts

- [Using the scripts safely](start-here/using-the-scripts.md): **audit first, then apply**
- `scripts/linux/harden.sh`: Linux Mint, Debian, Ubuntu
- `scripts/windows/Harden.ps1`: Windows 10/11, Windows Server (Domain Controller aware)
- `scripts/freebsd/harden.sh`: FreeBSD

## Credits

This toolkit started as a copy of [Ripper1004/CyberPatriot-Toolkit](https://github.com/Ripper1004/CyberPatriot-Toolkit) (October 2024): the checklists, the lessons and the first hardening scripts came from there, and its commits are kept in this repository's history. Round dates, images and point values are checked against CyberPatriot's [published scoring values](https://www.uscyberpatriot.org/competition/current-competition/challenges-by-round).
