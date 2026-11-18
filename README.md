# Rampart: CyberPatriot Toolkit

Beginner-friendly **checklists**, **guides** and **hardening scripts** for practicing CyberPatriot image challenges on Windows, Windows Server, Linux Mint, Debian, Ubuntu and FreeBSD.

> **New to this?** Use the website: **https://plzgimmeaname.github.io/cyberpatriot-toolkit/**, or start at **[docs/index.md](docs/index.md)** here on GitHub. Both walk you through everything in order.
>
> Started by **[@Ripper1004](https://github.com/Ripper1004/CyberPatriot-Toolkit)** — see [Credits](#credits).

---

## What's in here

### Checklists (one per operating system)
Every item says **what** to do, **why** it matters, how to do it by **clicking** and by **typing**, and how to **check it worked**.

| OS | CyberPatriot 19 (2026-27) rounds | Steps | Checklist |
|---|---|---|---|
| Windows 11 / 10 | Round 1, Round 2 | 65 | [docs/checklists/windows-10-11.md](docs/checklists/windows-10-11.md) |
| Windows Server 2022 / 2019 / 2016 | Round 2, State, Semifinals | 45 | [docs/checklists/windows-server.md](docs/checklists/windows-server.md) |
| Linux Mint 21 | Round 1, Round 2, State, Semifinals | 70 | [docs/checklists/linux-mint.md](docs/checklists/linux-mint.md) |
| Ubuntu 24 | State (22 in the training rounds) | 10 | [docs/checklists/ubuntu.md](docs/checklists/ubuntu.md) |
| Debian 12 | not in CP-19 — older images, full-depth walkthrough | 78 | [docs/checklists/debian.md](docs/checklists/debian.md) |
| FreeBSD | not in CP-19 (Semifinals on older seasons) | 34 | [docs/checklists/freebsd.md](docs/checklists/freebsd.md) |

### Beginner guides
- [What is CyberPatriot?](docs/start-here/what-is-cyberpatriot.md) · [Reading the README](docs/start-here/reading-the-readme.md) · [Round game plan](docs/start-here/round-game-plan.md)
- [Linux terminal basics](docs/start-here/linux-terminal-basics.md) · [PowerShell basics](docs/start-here/powershell-basics.md)
- [Things that lose points](docs/guides/things-that-lose-points.md) · [Forensics questions](docs/guides/forensics-questions.md) · [Linux service hardening](docs/guides/linux-service-hardening.md) · [Glossary](docs/guides/glossary.md)
- [For mentors and teachers](docs/guides/for-mentors-and-teachers.md): running practice sessions with this toolkit

### Scripts
| Script | Works on |
|---|---|
| [`scripts/linux/harden.sh`](scripts/linux/harden.sh) | Linux Mint 20–22, Debian 11–12, Ubuntu 20.04–24.04 |
| [`scripts/windows/Harden.ps1`](scripts/windows/Harden.ps1) | Windows 10/11, Windows Server 2016–2022 (Domain Controller aware) |
| [`scripts/freebsd/harden.sh`](scripts/freebsd/harden.sh) | FreeBSD 13–14 |

**How they work** (full guide: [Using the scripts safely](docs/start-here/using-the-scripts.md)):
1. They ask for the README's **authorized admins, users and critical services**, and never remove or disable anything you list.
2. **Audit mode** reports problems and changes nothing. **Apply mode** fixes them and asks before risky steps.
3. Every changed file or setting is **backed up** first.
4. You get a **findings report**: a to-do list of the things a human must decide, plus **one log file per kind of finding** (apps installed, apps removed, files found/deleted, open ports, processes, services, persistence, connections) so you can see exactly what it caught - and what it missed.

```bash
# Linux
sudo bash scripts/linux/harden.sh
```
```powershell
# Windows (PowerShell as Administrator)
powershell -ExecutionPolicy Bypass -File .\scripts\windows\Harden.ps1
```

---

## Website

**[https://plzgimmeaname.github.io/cyberpatriot-toolkit/](https://plzgimmeaname.github.io/cyberpatriot-toolkit/)** — [`site/`](site/) turns everything above into a website for people who don't use GitHub. It's built with Astro + Starlight and published to GitHub Pages by `.github/workflows/pages.yml`. To host it somewhere else, set `siteUrl` and `base` in `site/site.config.mjs`.

- **Two sections:** **Toolkit** (dashboard, checklists, tools, scripts, reference: no introductions) for people who know the game, and **Learn** (welcome, 7 lessons, glossary) for beginners. Switch with the tabs at the top.
- **Interactive checklists:** tick off steps, see your progress, jump to the next step, print, reset for a new image, and **Compact view** to hide the beginner explanations. Each one shows what has actually been tested (`site/src/data/verified.ts`) instead of claiming it works.
- **Field cards:** [one printable page per image](site/src/data/field-cards.ts) with the commands that decide the round — no prose, two columns, works offline.
- **Points map:** [every scored category mapped to the checklist section that covers it](site/src/pages/points-map.astro), generated from the checklists so it cannot drift.
- **What the scripts do:** an honest [breakdown of ✅ applied / 🔎 checked / ✋ by hand](site/src/pages/automation.astro), counted from the script tags in every step.
- **Practice range:** [boot the practice images from this page](site/src/pages/range.astro) through a small local agent (`range/agent.py`, QEMU/Hyper-V): pull your own copy, audit it, and read the per-kind reports in the browser.
- **Gotchas by image:** [the traps that only exist on one image](site/src/data/gotchas.ts) (Debian has no sudo, Mint has no `auth.log`, pf will lock you out…).
- **Score-dropped triage:** pick what you touched and see the likely cause, the command that confirms it, and how to put it back.
- **Round post-mortem:** what you missed, why, and what changes next round, exported as Markdown.
- **Offline and installable:** a service worker caches the checklists, so they open with no internet; a web app manifest makes the site installable. Progress can be moved between devices with a share link (no account, nothing uploaded).
- **⌘K / Ctrl-K palette** to jump to any page or any of the 306 checklist steps.
- **A 7-lesson learning path** for beginners.
- **Tools:**
  - README config builder: paste the README and get the script's config file
  - round timer with game-plan phases
  - command finder
  - glossary quiz
  - script downloads with checksums
  - a progress page with export/import
  - findings to-do list: paste the script's report and get a clickable list linked to the checklist
  - round log: write down each change and the score, and see which change caused a penalty
  - forensics helper: file hashes (MD5, SHA-1, SHA-256), file-type check, Base64 / hex / ROT13 / Caesar decoding
  - Cisco levels (basics → State), the Cisco & Packet Tracer guide, networking quiz and subnetting practice
- **Your names in commands:** checklist commands use the real README names you type once, including what the Copy buttons copy.
- **Search, dark mode, mobile layout.** No accounts and no tracking: progress is saved in the browser.

The pages are generated from `docs/` at build time, so **edit `docs/` and the website updates itself**. Setup and local preview: [site/README.md](site/README.md). Writing style, step format and the rules that are not negotiable: [CONTENT_STYLE.md](CONTENT_STYLE.md).

---

## How the scripts are tested

| Script | Tests |
|---|---|
| Linux | [`tests/linux/run-tests.sh`](tests/linux/run-tests.sh) builds a practice "image" in a **Debian 12, Ubuntu 22.04, Ubuntu 24.04 and Linux Mint 21.3** container, plants ~30 vulnerabilities (hidden root account, PAM backdoor, cron reverse shell, SUID `find`, fake sudo alias…), runs the script, and checks **77 results**, plus runs with no README list (nothing may be deleted) and under `umask 0000`, including real logins with `pamtester`. All pass. |
| Windows | [`tests/windows/Test-HardenLogic.ps1`](tests/windows/Test-HardenLogic.ps1) loads the script's functions with fake `secedit.exe` and checks 155 behaviours. The script also parses cleanly, has no PowerShell 5.1 syntax problems, and `Invoke-ScriptAnalyzer` reports nothing with [`tests/windows/PSScriptAnalyzerSettings.psd1`](tests/windows/PSScriptAnalyzerSettings.psd1) (that file turns off four style rules that do not suit a one-file interactive script, and says why for each). **It has not been run on a real Windows image yet.** Try **Audit** mode on a practice image first. |
| FreeBSD | [`tests/freebsd/test-harden-logic.sh`](tests/freebsd/test-harden-logic.sh) runs the script's decisions on Linux under `dash` with fake FreeBSD commands (`pw`, `sysrc`, `service`...) and checks 52 behaviours, including "never deletes users without a README list". `shellcheck -s sh` clean. **Not yet run on a real FreeBSD system.** |

```bash
bash tests/linux/run-tests.sh                 # needs Docker
pwsh tests/windows/Test-HardenLogic.ps1       # needs PowerShell 7
pwsh -c "Invoke-ScriptAnalyzer -Path scripts/windows/Harden.ps1 -Settings tests/windows/PSScriptAnalyzerSettings.psd1"   # needs the PSScriptAnalyzer module: Install-Module PSScriptAnalyzer -Scope CurrentUser
dash tests/freebsd/test-harden-logic.sh       # as root; no FreeBSD needed
```

### How the checklists are tested

[`tests/checklists/`](tests/checklists/README.md) checks the checklists themselves. The Linux ones are run command by command in a container with the practice problems planted (`linux_lab.py linux-mint`, `debian`, `ubuntu`). The Windows and FreeBSD ones are only syntax-checked (PowerShell parser, `dash`, `shellcheck`) and reviewed against the Microsoft and FreeBSD documentation, because no Windows or FreeBSD image is available to run them. Run them on a real image before relying on them.

```bash
python3 tests/checklists/check-format.py                        # numbering, unique step ids, script tags
bash tests/checklists/check-shell.sh                            # bash / sh syntax, <placeholders> (uses Docker for shellcheck if it isn't installed)
pwsh -NoProfile -File tests/checklists/check-powershell.ps1     # PowerShell syntax
python3 tests/checklists/linux_lab.py linux-mint                # needs Docker
```

---

## Plans
See [ROADMAP.md](ROADMAP.md): current status, how the scripts, checklists and website are designed, and what is left to do.

## Contributing
- Keep the checklist item format: **What · Why it matters · Clicking · Typing · Check it worked · Warning**.
- Under each step's `- [ ] Done`, keep one `**Script:**` line saying what the hardening script does for it: `✅` it does it fully, `🔎` it checks but a person decides, `✋` by hand. The website build stops if a checklist step has none. Only use ✅ if Apply mode really finishes the step.
- Write for someone who has never done this before. Short sentences, explain every acronym.
- Website changes: `cd site && npm install && npm test` (builds the site and checks every link). See [site/README.md](site/README.md).
- Script changes: add a planted problem to `tests/linux/plant-vulns.sh` and a check to `tests/linux/verify.sh`, then run the tests.
- Older versions of the scripts and checklists are in the git history.

## Credits

This project started as a copy of **[Ripper1004/CyberPatriot-Toolkit](https://github.com/Ripper1004/CyberPatriot-Toolkit)**, created in October 2024. The checklists, the lessons and the first hardening scripts came from there. Its commits are kept in this repository's history, so every original contribution is still visible in `git log` and `git log --author=Ripper1004`. The website, the later script versions and everything since then are maintained here.

Thanks to **CyberPatriot** (the Air & Space Forces Association) for running the competition and publishing the round schedule and scoring values that the season pages are checked against.

The upstream repository has no licence file, so no licence terms are inherited from it; this repository's code is provided "as is" (below). If you reuse this material, credit the original repository too.

## License
Provided "as is".
