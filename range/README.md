# Practice range

Run the CyberPatriot practice images **from the website**: pull an image onto one
computer (the "range host"), boot it, run the hardening script in Audit or Apply
mode inside it, and read every report — downloads, deleted apps, open ports,
processes — on the **Practice range** page (`/range/`).

It works like a small, self-hosted VA CyberRange: a local agent owns the VMs and
the browser is only a remote control. **Paste a download link and, if the archive
has one, the unzip password** — the agent downloads the image, verifies the
checksum (MD5, SHA-1, SHA-256 or SHA-512) when you give one, unpacks it, boots a throw-away copy and streams the
screen and console back to the page. Nothing is uploaded anywhere, and the agent
listens on `127.0.0.1` unless you tell it otherwise.

```
 website  ──HTTP (token)──▶  range/agent.py  ──QEMU / Hyper-V──▶  practice VM
 /range/                     catalog, runs        overlay disk      harden.sh
```

## Why there is no list of CyberPatriot download URLs

CyberPatriot gives the practice images to registered coaches through the
competition portal; they are not public downloads. This range therefore pulls
from **sources you own**:

* a ZIP / OVA / qcow2 you downloaded from the portal (`"kind": "local"`), or
* an address on your own file server / NAS (`"kind": "url"`, optionally with a
  SHA-256 that is always checked).

Do not put competition images on a public server: the rules forbid sharing them
outside your team.

## What you need (range host)

| Piece | Linux host | Windows host |
|---|---|---|
| Hypervisor | `qemu-system-x86` + `qemu-utils` (Debian/Ubuntu) | Hyper-V role, elevated PowerShell |
| Guest access | `ssh` and `scp` (OpenSSH client) | PowerShell + WinRM in the guest |
| Python | 3.9 or newer | 3.9 or newer |

No Python packages are needed.

**Prepare one template per image, once.** The range makes a throw-away overlay
disk for every run, so the base image must already be able to answer:

* **Linux / FreeBSD:** `sshd` running, and your public key in the template's
  `~/.ssh/authorized_keys` (for the user in `guest.user`), with `sudo -n`
  allowed for that user. Test it: `ssh -i ~/.ssh/rampart_mint student@127.0.0.1 -p 2222`.
* **Windows:** WinRM enabled (`Enable-PSRemoting -Force`), the Administrator
  password in an environment variable on the range host, and the range host's
  address trusted (`winrm set winrm/config/client @{TrustedHosts="..."}`).

Booting a stock CyberPatriot ZIP that has no key installed is not supported: the
agent will say so instead of guessing a password.

## Quick start: no terminal needed

**Double-click a launcher** and everything else happens on the page:

| Computer | Launcher |
|---|---|
| macOS | `range/Start Range.command` |
| Linux | `range/start-range.sh` |
| Windows | `range/start-range.bat` |

It starts the agent, serves the website from `site/dist` (building it once if Node.js
is installed), and opens your browser on the **Practice range** page **already
connected**: the token travels in the URL fragment, which never leaves the browser and
is removed from the address bar. On the page: paste the **download link**, the
**checksum** and the **unzip password**, press **Download & boot**, and the VM's desktop
opens when it is up. Pass `--no-open` to skip the browser, `--site https://...` to open a
hosted copy of the site instead.

## Quick start (by hand)

```bash
cp range/images.example.json range/images.json
$EDITOR range/images.json                 # paths, keys, checksums

python3 range/agent.py --catalog range/images.json
# Rampart Range agent 1.0.0
#   listening on http://127.0.0.1:8787
#   token:  <printed once, then stored in ~/.rampart-range/token>
```

Open the site, go to **Practice range**, paste the URL and token, then:

0. **Paste a download link** (and the unzip password if the ZIP is protected),
   choose the OS family and press **Download & boot**. It is saved to
   `~/.rampart-range/images.local.json`, so it is there next time without
   editing `images.json`. Progress is on the card and in
   `~/.rampart-range/images/<id>/pull.log`.
1. **Pull** a catalog image instead, if you already listed it (download →
   SHA-256 → unpack → convert to qcow2).
2. Fill in the README answers (admins, users, critical services) once.
3. **Boot** keeps the VM running; the page shows the VM's **live desktop** (real
   screen, keyboard and mouse, see below) and the serial console. **Boot desktop
   only** skips the wait for SSH/WinRM, so a stock CyberPatriot image with no key
   in it still boots and you work in it from the browser. **Reset to original** powers it off, deletes its overlay and
   boots the untouched base image again, so a broken practice VM is one click
   from the starting state. **Audit** then runs inside that same VM
   (`sessionId`), or boots one just for the run. **Apply** changes nothing on the base image but
   does modify the running VM (second confirmation).
4. Click a run to see the live log and, afterwards, one table per finding kind:
   `03-apps-installed`, `04-apps-removed`, `05-files-found`,
   `06-files-deleted`, `07-open-ports`, `08-processes`, `09-services`,
   `10-persistence`, `11-connections`. The to-do list is `01…`/findings.

The agent can be started by hand at any time; the site shows the same command if
it cannot reach one.

## Adding an image from the page (link + unzip password)

The **Add an image from a link** card sends one request:

```bash
curl -s -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"url":"https://files.example.org/Mint21_Practice.zip",
       "password":"the-zip-password",
       "family":"linux",
       "checksum":"sha256:c7b3330dcd88bd33...",
       "keyFile":"~/.ssh/rampart_mint",
       "boot":true}' \
  http://127.0.0.1:8787/api/images/add
```

**Checksum:** paste whatever the download page shows, in any of these forms. The type is
detected from the length (or the label), checked while the file downloads, and a download
that does not match is deleted, never unpacked or booted:

```
c7b3330dcd88bd33...                       bare hash, any case
sha256: c7b3330d...                       with a label
SHA256 (Mint21.zip) = c7b3330d...         openssl / BSD style
c7b3330d...  *Mint21.zip                  sha256sum / md5sum output
c7:b3:33:0d:...                           colon separated
```

MD5 (32 hex characters), SHA-1 (40), SHA-256 (64) and SHA-512 (128) are supported. The API
field is `checksum` (the older `sha256` still works). A pasted value that is not a checksum
is refused immediately, before anything downloads.

Accepted `url` schemes are `https`, `http`, `ftp` and `file`. The name comes from
the file, or from `name`; `family` picks the script (`linux`, `windows`,
`freebsd`) and can often be guessed from the name (`Mint`, `Ubuntu`, `Win10`...).
`keyFile` is the SSH key already installed in your template — a stock
CyberPatriot image does not have one, and the agent says so instead of guessing
a password.

Archives and formats handled: `.zip`, `.7z`, `.tar`, `.tar.gz`/`.tgz`, `.tar.xz`,
`.tar.bz2`, `.gz`, `.xz`, `.bz2`, plus raw `.qcow2`/`.img`/`.vmdk`/`.vdi`/`.vhd`
(converted to qcow2 with `qemu-img`). The disk inside an archive is found by
`disk.file`, or by the first disk-like extension.

**Passwords:**

* Plain ZIP passwords (ZipCrypto, what `zip -e` and most portals produce) use the
  Python standard library: nothing extra to install.
* AES-encrypted ZIPs, `.7z` and `.rar` need `7z`/`7zz`/`7za` (`p7zip-full` on
  Debian/Ubuntu) or `unar` on the range host. Without it the pull log says which
  program to install; the download is kept so you can retry.
* The password is held in memory for the pull only. It is never written to
  `images.local.json`, the pull log, the run folders or the site — the page also
  clears the field after sending it. Retrying a failed extraction after a
  restart needs the password again.
* A wrong password fails fast with `wrong unzip password`; it is not retried
  against the archive.

## The live desktop in the browser

With the QEMU provider the VM's display is **interactive on the page**, no VNC
client or extra server needed:

```
 browser (noVNC)  ──ws://127.0.0.1:<port>──▶  QEMU's built-in VNC WebSocket
```

* QEMU is started with `-vnc 127.0.0.1:N,websocket=PORT,password=on`, so it
  listens on loopback only and refuses every connection until the agent has set
  a random 8-character password through the QEMU monitor.
* The page fetches `GET /api/sessions/{id}/desktop` (needs the agent token) and
  gets the port and that password. The password lives in the agent's memory
  only: it is never written to `sessions.json`, the logs or the session list.
* noVNC (`@novnc/novnc`, bundled into the page, no CDN) draws it. There are
  buttons for Connect / Disconnect, Ctrl+Alt+Del and full screen. A USB tablet
  device is added so the mouse pointer lines up with the guest's.
* It works while the guest is still booting, so you can watch GRUB, the Windows
  logo and the login screen, and press keys in firmware menus.
* **Boot desktop only** (or an image added without an SSH key) does not wait for
  SSH/WinRM. Audits and runs need SSH/WinRM; the desktop does not.
* Same limits as the agent: loopback only. If the agent runs on another machine,
  tunnel both ports (`ssh -L 8787:127.0.0.1:8787 -L <wsport>:127.0.0.1:<wsport>`),
  or run the page on that machine.
* A VM that crashes or is killed is listed as stopped within a few seconds.

Why not run the VM inside the browser (v86, CheerpX, WebVM)? Those WebAssembly
emulators handle small Linux images; a multi-GB Windows 11 or Mint image would
be unusably slow and would have to be downloaded into the page. Streaming the
real VM from QEMU is the practical way to get "the VM in the browser".

## What a run does

1. `catalog.pull` makes sure the base disk exists (it never edits it).
2. `providers.QemuProvider` / `HyperVProvider` creates a **differencing overlay**
   and boots it headless. SSH and WinRM are forwarded to random loopback ports.
3. `runner.py` copies `scripts/<os>/harden.*` and a config file generated from
   your README answers into the guest, runs it (`--audit` or `--apply --yes`),
   streams the output to the run log, then tars back
   `/root/cyberpatriot/logs-*`, `findings-*` and the run log.
4. The agent stops and deletes the VM and its overlay. The base image, your
   data and the previous run's reports are untouched.

One run at a time per agent (a laptop cannot boot five VMs at once). Runs are
kept in `~/.rampart-range/runs/<id>/` until you delete them from the page.

`provider: "attach"` skips steps 1–2 and 4: it connects to a VM you started
yourself (`guest.host`). That is the safest way to try the page, and it works
with VirtualBox or VMware without any extra software.

## Catalog fields

```jsonc
{
  "id": "cp-mint21",                       // letters, digits, . _ - only
  "name": "Linux Mint 21 (practice)",
  "family": "linux",                       // windows | linux | freebsd
  "osName": "Linux Mint 21.3",
  "script": "linux",                       // which harden.sh / Harden.ps1 to run
  "provider": "qemu",                      // optional: qemu | hyperv | attach
  "source": {
    "kind": "local",                       // local | url
    "path": "~/CyberPatriot/Mint21.zip",   // relative paths are relative to images.json
    "sha256": "..."                        // optional, always checked when present
  },
  "disk": { "file": "Mint21.vmdk", "format": "vmdk" },  // file: inside the archive
  "guest": {
    "user": "student",
    "sshPort": 22,                         // or winrmPort for Windows
    "keyFile": "~/.ssh/rampart_mint",      // Linux/FreeBSD key auth
    "passwordEnv": "RAMPART_WIN_PASSWORD", // Windows: name of an env var, never a password
    "sudo": true,
    "ramMb": 4096,
    "cpus": 2,
    "bootTimeout": 300,
    "switchName": "Default Switch"         // Hyper-V
  },
  "notes": "what you changed to make it a template"
}
```

The catalog is validated on start: a typo in a field stops the agent with a
message naming the image, rather than failing half an hour into a run.

## API (for scripts and mentors)

All but `/api/health` need `Authorization: Bearer <token>`.

```
GET    /api/health
GET    /api/capabilities
GET    /api/images
POST   /api/images/add      {"url":"https://...","password":"...","family":"linux","keyFile":"~/.ssh/...","boot":true}
POST   /api/images/{id}/pull
POST   /api/images/{id}/boot        {"desktopOnly": true} to skip waiting for SSH/WinRM
GET    /api/sessions
GET    /api/sessions/{id}
GET    /api/sessions/{id}/console?offset=0
GET    /api/sessions/{id}/screen          one PNG frame (QEMU only)
GET    /api/sessions/{id}/desktop         {host, port, password} for the noVNC viewer (QEMU only)
POST   /api/sessions/{id}/reset        stop, drop the overlay, boot the base image again
POST   /api/sessions/{id}/stop
GET    /api/runs
POST   /api/runs            {"imageId":"cp-mint21","mode":"audit","config":{"admins":"alice","users":"bob","critical":"ssh"}}
GET    /api/runs/{id}
GET    /api/runs/{id}/log?offset=0
GET    /api/runs/{id}/logs
GET    /api/runs/{id}/findings
POST   /api/runs/{id}/stop
DELETE /api/runs/{id}
```

A booted VM stays up until you stop it and is reused by later runs: pass
`"sessionId": "vm-..."` in `POST /api/runs` to run the script inside that VM
instead of booting a new one. Apply needs `"confirmApply": true` in the body. Example from a terminal:

```bash
TOKEN=$(cat ~/.rampart-range/token)
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8787/api/images | jq .
```

## Safety rules this follows

* **Loopback by default.** `--host 0.0.0.0` prints a warning; anyone who reaches
  the port still needs the token. The token lives in `~/.rampart-range/token`
  (mode 600) and is never sent to the website's server — only to the page in
  your browser.
* **The base image is never written to.** Every run uses an overlay that is
  deleted afterwards; a booted VM you keep also runs on an overlay, and
  **Reset to original** throws that overlay away and boots the base image again.
* **Unzip passwords are not stored.** They exist in the agent's memory for the
  duration of the pull and never reach a file or the website.
* **The browser cannot choose commands.** It picks an image id and audit/apply;
  every command is built from fixed arguments in `runner.py`.
* **Guest passwords come from environment variables**, never from the catalog,
  the URL or a command line.
* **Apply is explicit twice**: the page asks, and the API needs `confirmApply`.
* Old reports are kept per run, so a change that loses points can be traced in
  `06-files-deleted.txt` / `04-apps-removed.txt` with the script's timestamps.

## Tests

```bash
python3 -m unittest discover -s tests/range -v
```

Eighteen checks, standard library only (the QEMU one is skipped without QEMU): adding an image from a **password-protected
ZIP** served over HTTP (right password → ready, wrong password → `wrong unzip
password`, no password → `password protected`), that the password never reaches
`images.local.json`, that a reset replaces the booted VM and deletes its overlay
folder, and that a QEMU screendump PPM becomes a PNG with the same pixels (plus
the two error cases), plus the live desktop: the password is never listed, a dead QEMU is not shown as running, and a real throw-away QEMU answers the WebSocket handshake. The archive test needs the `zip` command and
is skipped without it.

## Limits (read before trusting it)

* Only `qemu`, `hyperv` and `attach` are implemented. VirtualBox providers would
  be a small class in `providers.py` (`VBoxManage` has the same overlay idea).
* Windows needs WinRM and a password in an environment variable; there is no
  automatic key setup for Windows.
* A guest that needs a login prompt, a "press any key to boot" or a network
  bridge will time out — the run log says so and the console log is kept
  (`runs/<id>/console.log` on QEMU).
* The older live **frame** (`screendump`, every couple of seconds, read-only) is
  only shown when the live desktop is not available. Linux
  guests send text output on the serial console only when the kernel is told to
  (`console=ttyS0`), so a stock image often shows a blank console while the
  frame shows GRUB/the login screen. Hyper-V and `attach` have no frame — use
  RDP/SSH or the Hyper-V console there.
* The interactive desktop is QEMU-only. Hyper-V and `attach` VMs have no frame
  or desktop on the page (use the Hyper-V console, RDP or SSH); QEMU's own
  WebSocket VNC means no proxy is needed for QEMU.
* On an Apple Silicon Mac QEMU emulates x86 (TCG), which is slow: fine for
  trying the page, painfully slow for Windows. Use an x86 host with KVM/HVF.
* The agent has no user accounts of its own. Use it on a machine only you use,
  or run it with `--host 127.0.0.1` and reach it through an SSH tunnel.
* The site itself is static: the range page needs the agent running locally. It
  does not run VMs on the web server.
