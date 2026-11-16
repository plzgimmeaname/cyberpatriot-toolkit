# Ubuntu checklist (20.04 / 22.04 / 24.04, GNOME)

Ubuntu 24.04 is the **State round** image this season, and Ubuntu 22.04 is used in the training rounds. This page is complete on its own: the same 18 sections as the [Linux Mint](linux-mint.md) and [Debian](debian.md) checklists, with the Ubuntu differences written out where they matter (GNOME instead of Cinnamon, GDM instead of LightDM, snaps, `ssh.socket`, and the newer `ubuntu.sources` file).

**How to use this page**
- Work **top to bottom**. The order matches where points usually are.
- Each item has: **What** · **Why it matters** · **Clicking** (the GUI way) · **Typing** (terminal commands) · **Check it worked** · and sometimes a ⚠️ warning about when *not* to do it.
- `alice`, `bob` etc. are example names. **Use the names from your README.**
- New to the terminal? Read [Linux terminal basics](../start-here/linux-terminal-basics.md) first (10 minutes).
- The script `scripts/linux/harden.sh` detects Ubuntu automatically and can do a lot of this for you. Run it at [step 1.2](#12-fast-path-run-the-hardening-script), then skip the steps marked **Script: ✅**. See [Using the scripts](../start-here/using-the-scripts.md).

---

## 0. Before you touch anything

### 0.1 Read the README
- [ ] Done

**Script:** ✋ Not done by the script. Do this by hand.

Write down the admins, users, critical services, required software and prohibited items. See [Reading the README](../start-here/reading-the-readme.md).

### 0.2 Take a snapshot
- [ ] Done

**Script:** ✋ Not done by the script. Do this by hand.

**What:** Save the current state of the VM so you can go back if you break it.

**Clicking:** In VMware: **VM → Snapshot → Take Snapshot…**, name it "start".

> [!TIP]
> Take another snapshot whenever your score goes up a lot. If something breaks, **VM → Snapshot → Revert**. You lose the changes since that snapshot, but the scoring engine keeps the points you already earned.

### 0.3 Open a terminal and check you have admin rights
- [ ] Done

**Script:** ✋ Not done by the script. Do this by hand.

**Typing:** press **Ctrl + Alt + T**, then:
```bash
sudo -v        # asks for YOUR password; no error = you are an admin
whoami         # shows which user you are logged in as
```

### 0.4 Open the Scoring Report
- [ ] Done

**Script:** ✋ Not done by the script. Do this by hand.

Double-click **Scoring Report** on the desktop. Keep it open in a browser tab and refresh it as you work.

---

## 1. Forensics questions (do these FIRST)

### 1.1 Answer every forensics question before changing anything
- [ ] Done

**Script:** ✋ Not done by the script. Do this by hand.

**What:** Open each `Forensics Question N.txt` on the desktop, find the answer, and type it after `ANSWER:` in the file, then save.

**Why it matters:** They're often worth the most points, and fixing things (deleting users, files) can destroy the evidence you need.

**Typing (the most common tools):**
```bash
sudo find / -iname "*secret*" 2>/dev/null          # find a file by name
sudo grep -rIl "password" /home 2>/dev/null        # find files that contain a word
sha256sum /path/to/file                            # hash of a file
echo 'aGVsbG8=' | base64 -d                        # decode base64
sudo grep -E 'Accepted|Failed' /var/log/auth.log   # who logged in / failed to
```
More techniques: [Forensics questions guide](../guides/forensics-questions.md).

> [!WARNING]
> Answers must be **exact**: right spelling, capitals, and full paths when asked. Don't delete the "ANSWER:" line.

### 1.2 Fast path: run the hardening script
- [ ] Done

**What:** Once **every forensics question is answered**, run the toolkit's script `scripts/linux/harden.sh`. It fixes many of the steps below for you and gives you a to-do list for the rest.

**Why it matters:** The script does in a few minutes what takes an hour by hand, and it backs up every file before changing it. That leaves you more time for the steps that need a human.

**Typing:**
1. Get the script onto the image: open [Download the scripts](/downloads/) on this website and run the **Linux** download commands there. They save `harden.sh` and an example config in the `cp` folder inside your home folder (`~/cp`). No internet on the image? See [Using the scripts](../start-here/using-the-scripts.md).
2. Optional: make a config file with the [README config builder](/tools/config-builder/) and save it as `my.conf` in `~/cp`, next to `harden.sh`. No config? Leave out `--config my.conf` and the script asks you for the README names instead.
3. Run it in **audit** mode first (it changes nothing) and read every `REVIEW` line. Then run it in **apply** mode:
```bash
cd ~/cp
sudo bash harden.sh --audit --config my.conf        # report only: read the REVIEW lines
sudo bash harden.sh --apply --config my.conf        # make the changes (it asks before risky ones)
sudo cat /root/cyberpatriot/findings-*.txt          # your to-do list: every REVIEW item
```

**Check it worked:** The summary at the end shows mostly `OK` and `CHANGED`. Refresh the **Scoring Report**: your score should have gone up.

Every step below has a **Script:** line:
- **✅** the script does the whole step.
- **🔎** the script does part of it or only reports it. Finish it yourself.
- **✋** the script doesn't do it. Do it by hand.

Now skip every step marked **Script: ✅** below (on the website, press **Tick the script's ✅ steps** at the top of the page). Do the 🔎 and ✋ steps.

> [!WARNING]
> If any line says `FAILED`, do that step by hand. If your score goes **down**, find the change that caused it and undo it from the backups in `/root/cyberpatriot/backups/` (see [Using the scripts](../start-here/using-the-scripts.md#undoing-a-change)).

---

## 2. Users and groups

### 2.1 See every user on the computer
- [ ] Done

**Script:** 🔎 The script shows the users on this machine and flags every one that isn't in the README; you still type the README names in correctly.

**What:** Get the list of real (human) users and compare it with the README.

**Clicking:** **Settings → Users → Unlock** (enter your password). Every account is listed, with **Administrator** turned on or off.

**Typing:**
```bash
awk -F: '$3 >= 1000 && $3 < 65534 {print $1}' /etc/passwd
```
This prints every user with a user ID (UID) of 1000 or more, which means the real people.

### 2.2 Delete users who are not in the README
- [ ] Done

**Script:** ✅ Done by the script (`users` section).

**What:** Remove each account that isn't listed as an authorized admin or user.

**Why it matters:** An extra account is the easiest way for an attacker to get back in.

**Clicking:** In **Settings → Users**, select the user → **Remove User…** → keep or delete their files.

**Typing:**
```bash
sudo userdel mallory          # delete the account (keeps /home/mallory for now)
```

**Check it worked:** `id mallory` should say `no such user`.

> [!CAUTION]
> Check the spelling against the README **three times**. Deleting an authorized user is a penalty. Never delete yourself, `root`, or system accounts (UID below 1000 like `www-data`, `syslog`, `messagebus`).

### 2.3 Create users the README says should exist
- [ ] Done

**Script:** 🔎 The script creates missing README users (and makes README admins administrators), but they only get a password if you give it one (NEW_PASSWORD or when asked).

**Clicking:** **Settings → Users → Add User…**, choose **Standard** or **Administrator**, enter the name, then set a password.

**Typing:**
```bash
sudo adduser erin             # asks for a password and details
```

### 2.4 Fix who is an administrator
- [ ] Done

**Script:** ✅ Done by the script (`users` section).

**What:** Only the README's admins should be in the `sudo` group (that's what "Administrator" means on Ubuntu).

**Clicking:** In **Settings → Users**, select the user and turn **Administrator** on or off.

**Typing:**
```bash
getent group sudo                       # who has sudo now
sudo deluser bob sudo                   # take admin away from bob
sudo usermod -aG sudo alice             # give admin to alice
getent group adm                        # 'adm' can read logs - normally admins only
```

**Check it worked:** `getent group sudo` lists only the README admins.

### 2.5 Look for hidden root accounts and hidden users
- [ ] Done

**Script:** 🔎 The script finds UID-0 and hidden login accounts and offers to delete them or block their logins; you decide for each hidden user (say no if it belongs to a program).

**What:** Find accounts with UID 0 (secret root copies), and accounts with a low UID that can still log in.

**Why it matters:** `useradd -o -u 0 toor` makes a second root that doesn't show up in Users and Groups.

**Typing:**
```bash
awk -F: '$3 == 0 {print $1}' /etc/passwd                          # should print ONLY: root
awk -F: '$3 < 1000 && $7 !~ /(nologin|false|sync)$/ {print $1, $3, $7}' /etc/passwd
```
The second command lists low-UID accounts that have a real shell. Normally that's only `root` (and maybe `postgres` if PostgreSQL is installed).

**Fix:**
```bash
sudo userdel -f toor                            # delete a fake root
sudo usermod -s /usr/sbin/nologin mallory       # stop a hidden user from logging in
```

### 2.6 Check other powerful groups
- [ ] Done

**Script:** 🔎 The script removes non-admins from root, shadow, disk, kmem, docker and lxd (it asks first); check `sambashare` and any admins in these groups yourself.

**Typing:**
```bash
for g in root shadow disk lxd docker sambashare; do getent group $g; done
```
`shadow` can read password hashes. `disk` can read the raw hard drive. `lxd` and `docker` can become root. Normal users shouldn't be in them:
```bash
sudo gpasswd -d carol shadow
```

### 2.7 Give users strong passwords
- [ ] Done

**Script:** 🔎 The script gives every authorized user except you one strong password only if you set NEW_PASSWORD or type one when asked; otherwise do this by hand.

**What:** Change every authorized user's password (except your own, unless the README says so) to something strong.

**Why it matters:** Planted users often have passwords like `password` or `123456`.

**Clicking:** `Settings → Users` has no password editor on Ubuntu: use the `passwd` command below.

**Typing:**
```bash
sudo passwd bob
```
Use 12+ characters with upper case, lower case, a number and a symbol, e.g. `Blue-Train-42!x`. **Write it down.**

> [!WARNING]
> **Don't change your own password** unless the README asks. If you do, you must remember it, because the screen lock and `sudo` will ask for it.

### 2.8 Lock the root account
- [ ] Done

**Script:** ✅ Done by the script (`users` section).

**What:** Make sure nobody can log in directly as `root`. Admins use `sudo` instead.

**Typing:**
```bash
sudo passwd -S root      # "root L ..." = locked (good). "root P ..." = has a password
sudo passwd -l root      # lock it
```

**Check it worked:** `sudo passwd -S root` shows `L` after the name.

> [!CAUTION]
> Only do this if **you** can use `sudo` (step 0.3 worked). Otherwise you lock yourself out of admin.

### 2.9 Accounts with no password
- [ ] Done

**Script:** 🔎 The script lists every account with an empty password and locks the ones that aren't in the README (it asks first); README users with no password get one from you.

**What:** Find accounts that have **no password at all**, so anyone can log in as them by just pressing Enter.

**Why it matters:** An empty password is a common planted problem. Removing `nullok` (step 3.5) blocks these logins, but the account should still get a real password or be locked.

**Typing:**
```bash
sudo passwd -S -a | awk '$2 == "NP" {print $1}'   # NP = no password; should print nothing
sudo passwd bob                                    # README user: give them a strong password
sudo passwd -l mallory                             # account that shouldn't log in: lock it
```

**Check it worked:** the first command prints nothing.

---

## 3. Password and lockout policy

### 3.1 Password aging (how long passwords last)
- [ ] Done

**Script:** ✅ Done by the script (`passwords` section).

**What:** Passwords expire after 90 days, can't be changed again for 7 days, and users get 14 days' warning.

**Typing:**
```bash
sudo nano /etc/login.defs
```
Find these lines (Ctrl+W searches) and change them to:
```
PASS_MAX_DAYS   90
PASS_MIN_DAYS   7
PASS_WARN_AGE   14
```
Save with **Ctrl+O, Enter**, exit with **Ctrl+X**.

**Check it worked:** `grep ^PASS_ /etc/login.defs`

### 3.2 Apply aging to the users who already exist
- [ ] Done

**Script:** ✅ Done by the script (`passwords` section).

**Why:** `login.defs` only affects **new** users.

**Typing (repeat for each user):**
```bash
sudo chage -M 90 -m 7 -W 14 bob
sudo chage -l bob            # check: "Maximum number of days" = 90
```

### 3.3 Password complexity (pwquality)
- [ ] Done

**Script:** ✅ Done by the script (`passwords` section).

**What:** Make Linux reject weak passwords when someone changes theirs.

**Typing:**
```bash
sudo apt install libpam-pwquality
sudo nano /etc/security/pwquality.conf
```
Set (remove the `#` at the start of each line):
```
minlen = 12
ucredit = -1
lcredit = -1
dcredit = -1
ocredit = -1
difok = 3
maxrepeat = 3
usercheck = 1
dictcheck = 1
enforce_for_root
```
`-1` means "at least one" (upper case, lower case, digit, other symbol).

Also check the PAM line exists:
```bash
grep pwquality /etc/pam.d/common-password
```
It should look like: `password requisite pam_pwquality.so retry=3 ...`. You can add the same options to the end of that line (`minlen=12 ucredit=-1 lcredit=-1 dcredit=-1 ocredit=-1`).

### 3.4 Password history (no re-using old passwords)
- [ ] Done

**Script:** ✅ Done by the script (`passwords` section).

**Typing:**
```bash
sudo nano /etc/pam.d/common-password
```
Find the line containing `pam_unix.so` and add ` remember=5` to the end, e.g.:
```
password  [success=1 default=ignore]  pam_unix.so obscure use_authtok try_first_pass yescrypt remember=5
```

**Check it worked:** `grep remember /etc/pam.d/common-password` shows `remember=5`.

### 3.5 No logins with an empty password
- [ ] Done

**Script:** ✅ Done by the script (`passwords` section).

**What:** Remove the word `nullok` from `/etc/pam.d/common-auth`.

**Why:** `nullok` lets an account with an empty password log in without typing anything.

**Typing:**
```bash
grep nullok /etc/pam.d/common-auth
sudo sed -i 's/ nullok//' /etc/pam.d/common-auth
```

**Check it worked:** `grep -c nullok /etc/pam.d/common-auth` prints `0`.

### 3.6 Account lockout after failed logins (careful!)
- [ ] Done

**Script:** 🔎 The script turns on lockout only if ENABLE_LOCKOUT=yes or you answer yes when asked; then do the `su - bob` test in a new terminal.

**What:** Lock an account for 15 minutes after 5 wrong passwords.

**Why:** It stops attackers guessing passwords.

> [!CAUTION]
> PAM controls **every** login. One mistake here can stop *everyone* (including you) logging in. Before editing:
> 1. Open a **second terminal** and run `sudo -i`. Leave it open: it's your way back in.
> 2. Copy the file: `sudo cp /etc/pam.d/common-auth /etc/pam.d/common-auth.bak`
> 3. After editing, test in a **third terminal**: `su - bob`. If it fails, restore the copy from terminal 2.

1. Settings file:
   ```bash
   sudo nano /etc/security/faillock.conf
   ```
   Set `deny = 5`, `unlock_time = 900` and `fail_interval = 900` (remove the `#`).
2. Edit `/etc/pam.d/common-auth`. The **order matters**. Change the start of the "Primary" block to exactly this:
   ```
   auth    requisite                       pam_faillock.so preauth
   auth    [success=2 default=ignore]      pam_unix.so
   auth    [default=die]                   pam_faillock.so authfail
   auth    requisite                       pam_deny.so
   auth    optional                        pam_faillock.so authsucc
   auth    required                        pam_permit.so
   ```
   Note the `success=2` (it used to be `success=1`). It jumps over the `authfail` and `pam_deny` lines when the password is right.
3. Add this line to the **end** of `/etc/pam.d/common-account`:
   ```
   account required                        pam_faillock.so
   ```

**Check it worked:** `su - bob` with the right password works. `sudo faillock --user bob` shows failures. Locked out a user by testing? `sudo faillock --user bob --reset` unlocks them.

> [!NOTE]
> Ubuntu 20.04 is too old for `pam_faillock`. They use `pam_tally2` instead: add `auth required pam_tally2.so onerr=fail deny=5 unlock_time=900` as the **first** `auth` line in `common-auth`, and `account required pam_tally2.so` to the end of `common-account`.

---

## 4. Firewall (UFW)

### 4.1 Turn on the firewall
- [ ] Done

**Script:** ✅ Done by the script (`firewall` section).

**What:** Block every incoming connection except the ones the README needs.

**Clicking:** Ubuntu has no graphical firewall by default: `sudo apt install gufw` adds **Firewall Configuration** to the menu (or just use the commands below). Switch **Status** on, set **Incoming: Deny** and **Outgoing: Allow**.

**Typing:**
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh              # ONLY if SSH is a critical service in the README
sudo ufw enable
sudo ufw logging on
```

**Check it worked:** `sudo ufw status verbose` shows `Status: active` and `Default: deny (incoming)`.

### 4.2 Allow the critical services (and nothing else)
- [ ] Done

**Script:** 🔎 The script opens the ports for the critical services you entered (plus EXTRA_PORTS); check `sudo ufw status` matches the README, especially for services it doesn't know.

| README needs | Command |
|---|---|
| SSH | `sudo ufw allow 22/tcp` |
| Web server (Apache/Nginx) | `sudo ufw allow 80/tcp` and `sudo ufw allow 443/tcp` |
| FTP | `sudo ufw allow 21/tcp` |
| Samba (file sharing) | `sudo ufw allow samba` |
| MySQL from other computers | `sudo ufw allow 3306/tcp` |
| DNS server | `sudo ufw allow 53` |

### 4.3 Remove rules an attacker added
- [ ] Done

**Script:** 🔎 The script lists `allow` rules that aren't for a critical service under REVIEW; you decide which to delete.

**Typing:**
```bash
sudo ufw status numbered
sudo ufw delete 3            # delete rule number 3 (check the number first!)
```
Look for odd ports like 4444, 1337, 31337, 6667, or "ALLOW Anywhere" on a port no critical service uses.

---

## 5. Updates

> [!TIP]
> Start updates early: they can take 20+ minutes. You can keep working in another window while they run.

### 5.1 Install all updates
- [ ] Done

**Script:** 🔎 The script installs all updates only if FULL_UPGRADE=yes or you say yes when asked; otherwise do it here.

**Clicking:** **Software Updater** → **Install Now**. If it is not in the menu, run `update-manager` or use the commands below. If it asks to update itself first, say yes.

**Typing:**
```bash
sudo apt update
sudo apt full-upgrade -y
```

### 5.2 Turn on automatic updates
- [ ] Done

**Script:** 🔎 The script sets up `20auto-upgrades` and enables `unattended-upgrades`; just check that **Software & Updates → Updates** still says **Download and install automatically**.

**Clicking:** **Software & Updates → Updates** tab:
- **Subscribed to:** All updates
- **Automatically check for updates:** **Daily**
- **When there are security updates:** **Download and install automatically**

**Typing (the setting many scoring engines check):**
```bash
sudo apt install unattended-upgrades
sudo nano /etc/apt/apt.conf.d/20auto-upgrades
```
Make it contain:
```
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::Download-Upgradeable-Packages "1";
APT::Periodic::AutocleanInterval "7";
```

### 5.3 Check the software sources
- [ ] Done

**Script:** 🔎 The script flags unofficial sources, `[trusted=yes]` and a missing security source under REVIEW; you remove the bad ones.

**What:** Make sure updates come from the official Ubuntu servers only.

**Clicking:** **Software & Updates**. Look at **Ubuntu Software**, **Other Software** and **Updates**. Remove anything you don't recognise and make sure the official repositories are enabled.

**Typing:**
```bash
grep -rhv '^#' /etc/apt/sources.list /etc/apt/sources.list.d/ | grep .
```
Official addresses: `archive.ubuntu.com`, `security.ubuntu.com`, `ports.ubuntu.com` (or a country mirror such as `de.archive.ubuntu.com`). `[trusted=yes]` on a line is a **red flag**: it turns off signature checking.

> [!NOTE]
> Ubuntu 24.04 keeps its sources in **`/etc/apt/sources.list.d/ubuntu.sources`** (the newer deb822 format with `URIs:` and `Suites:` lines), and `/etc/apt/sources.list` is usually empty. The `grep` above reads every file, so check both.

### 5.4 Packages "held" back from updating
- [ ] Done

**Script:** ✅ Done by the script (`updates` section).

```bash
apt-mark showhold              # anything listed will never update
sudo apt-mark unhold firefox   # change firefox to each name the line above printed
```

**Check it worked:** `apt-mark showhold` prints nothing.

### 5.5 Update the apps the README mentions
- [ ] Done

**Script:** 🔎 Done only if the script installed all updates (FULL_UPGRADE=yes or you said yes); still check Firefox's version.

Firefox, Thunderbird, LibreOffice and any critical service are updated by 5.1 and 5.6. Check Firefox with **≡ → Help → About Firefox**.

On Ubuntu, Firefox is a **snap** (22.04 and newer), so `apt` never updates it — `sudo snap refresh firefox` does. `apt` packages and snaps show anything still out of date:
```bash
apt list --upgradable 2>/dev/null | grep -Ei 'thunderbird|libreoffice'   # anything listed is out of date
snap refresh --list                                                       # snaps with an update waiting
```
If **Software Updater** never offers an update for a program, check whether it is held back (5.4) or a snap pinned with `snap refresh --hold`.

### 5.6 Snap packages update separately
- [ ] Done

**Script:** 🔎 The script runs `snap refresh` only when it installs all updates, and removes prohibited snaps it knows; check `snap list` yourself.

**What:** On Ubuntu 22.04 and newer, **Firefox**, **Thunderbird** (24.04) and some other apps are snaps. `apt` does not update them, and a snap the README doesn't need is extra software.

**Typing:**
```bash
snap list                        # every snap app
sudo snap refresh                # update all of them (needs internet)
sudo snap remove steam           # remove a prohibited snap: change steam to the name from snap list
```

**Check it worked:** `snap list firefox` shows a version, and `snap refresh --list` prints nothing when everything is current.

---

## 6. Services

### 6.1 See what's running and listening
- [ ] Done

**Script:** 🔎 The script puts the running services and listening ports in the findings report; you still look through them for anything odd.

**Typing:**
```bash
systemctl list-units --type=service --state=running
sudo ss -tulpn             # programs listening on network ports
```

### 6.2 Turn off services the README doesn't need
- [ ] Done

**Script:** 🔎 The script offers to stop (or remove) known services the README doesn't list; SSH, uninstalling, and services it doesn't know about are your call.

**Typing:**
```bash
sudo systemctl disable --now vsftpd        # stop it now AND at boot
sudo apt purge vsftpd                      # remove it completely (if the README doesn't need it)
```

| Service | Package | Usually… |
|---|---|---|
| Telnet server | `telnetd`, `inetutils-telnetd` | **Remove** (sends passwords in plain text) |
| FTP server | `vsftpd`, `proftpd-core`, `pure-ftpd` | Remove unless the README needs FTP |
| Web server | `apache2`, `nginx` | Remove unless the README needs it |
| Database | `mysql-server`, `mariadb-server`, `postgresql` | Remove unless needed |
| Samba | `samba` | Remove unless file sharing is needed |
| SNMP | `snmpd` | Remove |
| NFS | `nfs-kernel-server`, `rpcbind` | Remove unless needed |
| Printing | `cups` | Disable unless printing is needed |
| Avahi (network discovery) | `avahi-daemon` | Disable |
| VNC / remote desktop | `x11vnc`, `vino`, `xrdp` | Remove unless needed |
| DNS server | `bind9` | Remove unless the README needs DNS |
| Mail server | `postfix`, `dovecot-core` | Remove unless the README needs mail |
| Web proxy | `squid` | Remove unless needed |
| Old insecure servers | `tftpd-hpa`, `xinetd`, `openbsd-inetd`, `rsh-server`, `nis` | **Remove** |
| SSH server | `openssh-server` | Keep **only** if the README mentions SSH |

> [!CAUTION]
> **Never** turn off a service the README lists as critical. Disabling a critical service is a penalty on almost every image.

### 6.3 Make sure the critical services are running
- [ ] Done

**Script:** 🔎 The script starts the critical services it recognises from your list; check each one with `systemctl status`.

```bash
systemctl status ssh             # "active (running)" in green = good
sudo systemctl enable --now ssh  # start it if it isn't
```

---

## 7. Prohibited software and files

### 7.1 Hacking tools
- [ ] Done

**Script:** 🔎 The script removes known hacking-tool packages (it asks first), but only reports `netcat-openbsd` and hand-copied tools; check its REVIEW lines.

**Clicking:** **Synaptic Package Manager** (`sudo apt install synaptic` if it is missing). Search each name, right-click → **Mark for Complete Removal** → **Apply**.

**Typing:**
```bash
dpkg -l | grep -Ei 'nmap|wireshark|john|hydra|aircrack|ophcrack|hashcat|nikto|sqlmap|ettercap|metasploit|netcat|ncat|medusa|kismet|dsniff'
sudo apt purge nmap wireshark john hydra
sudo apt autoremove
```

### 7.2 Games
- [ ] Done

**Script:** 🔎 The script removes the games on its list (it asks first); look for any others and run `sudo apt autoremove`.

```bash
dpkg -l | grep -Ei 'aisleriot|gnome-mines|gnome-sudoku|mahjongg|minetest|supertux|freeciv|0ad|wesnoth|bsdgames|steam'
sudo apt purge aisleriot gnome-mines
```

### 7.3 File-sharing and remote-access programs
- [ ] Done

**Script:** 🔎 The script removes known torrent and remote-access programs, snaps and flatpaks (it asks first); check its REVIEW lines for any it skipped.

```bash
dpkg -l | grep -Ei 'transmission|qbittorrent|deluge|frostwire|teamviewer|anydesk|x11vnc|tightvnc|vino'
flatpak list 2>/dev/null       # flatpak if someone installed it (not the default on Ubuntu)
snap list 2>/dev/null          # Firefox and some apps are snaps on Ubuntu
```
> [!NOTE]
> Ubuntu desktop installs **Transmission** (a torrent program) by default. Remove it unless the README needs it: `sudo apt purge transmission-gtk transmission-common`. Firefox is a **snap** on 22.04+, so prohibited snaps also need `snap remove` (5.6).

### 7.4 Media files (music and video)
- [ ] Done

**Script:** 🔎 The script lists media files and offers to delete them all at once; read the list first and say no if any must stay (forensics, a website).

**Typing:**
```bash
sudo find /home /root /tmp /srv /opt /var/www -type f \( -iname '*.mp3' -o -iname '*.mp4' -o -iname '*.wav' -o -iname '*.avi' -o -iname '*.mkv' -o -iname '*.mov' -o -iname '*.flac' -o -iname '*.ogg' -o -iname '*.wma' -o -iname '*.m4a' \) 2>/dev/null
sudo rm "/home/bob/Music/song.mp3"
```

> [!WARNING]
> Check the forensics questions first. A question might ask about one of these files.

### 7.5 Other files that break policy
- [ ] Done

**Script:** 🔎 The script lists password lists, packet captures and similar files under REVIEW; you open each one and decide.

Password lists, credit card or social security number files, packet captures (`.pcap`), and hacking scripts:
```bash
sudo find /home /root /tmp /opt -type f \( -iname '*password*' -o -iname '*.pcap' -o -iname '*creditcard*' -o -iname '*.kdbx' \) 2>/dev/null
sudo ls -la /home/*/ /tmp /var/tmp /opt     # look for anything odd, including hidden .files
```

---

## 8. Login screen and desktop

### 8.1 No automatic login and no user list on the login screen
- [ ] Done

**Script:** 🔎 The script turns off automatic login and hides the user list in the GDM and dconf files; check the `grep` line below.

**Clicking:** **Settings → Users** → **Unlock** → turn **Automatic Login** off. GNOME has no guest session, so there is nothing to disable there.

**Typing:**
```bash
sudo nano /etc/gdm3/custom.conf
```
Under `[daemon]`:
```
[daemon]
AutomaticLoginEnable=false
TimedLoginEnable=false
```
Then hide the list of users (the file `dpkg-reconfigure gdm3` writes):
```bash
sudo nano /etc/gdm3/greeter.dconf-defaults
```
Under `[org/gnome/login-screen]`:
```
[org/gnome/login-screen]
disable-user-list=true
```
The reliable way to apply it is the system dconf database:
```bash
sudo mkdir -p /etc/dconf/db/gdm.d
printf '[org/gnome/login-screen]\ndisable-user-list=true\n' | sudo tee /etc/dconf/db/gdm.d/00-login-screen
sudo dconf update
```

**Check it worked:** `grep -r 'AutomaticLogin\|disable-user-list' /etc/gdm3/ /etc/dconf/db/gdm.d/ 2>/dev/null` shows `AutomaticLoginEnable=false` and `disable-user-list=true`, with no user name after `AutomaticLogin=`.

> [!NOTE]
> Ubuntu 20.04, 22.04 and 24.04 all use `/etc/gdm3/`. A server install has no graphical login, so this section does not apply there.

### 8.2 Lock the screen when idle
- [ ] Done

**Script:** 🔎 The script sets a 5-minute screen lock for all users with dconf; run the `gsettings` check, and set it by hand if the script says REVIEW.

**Clicking:** **Settings → Power** → **Screen Blank: 5 minutes**. Then **Settings → Privacy → Screen Lock**: turn **Automatic Screen Lock** on and set **Lock Screen after Blank for** to **Screen Turns Off**.

**Typing:** run these in **your own** terminal, **without** `sudo` (`sudo gsettings` changes root's settings, not yours):
```bash
gsettings set org.gnome.desktop.session idle-delay 300            # 300 seconds = 5 minutes
gsettings set org.gnome.desktop.screensaver lock-enabled true
gsettings set org.gnome.desktop.screensaver lock-delay 0          # lock as soon as the screen blanks
```
If it says **The key is not writable**, the script has already set and locked this for every user. That's fine.

**Check it worked:** `gsettings get org.gnome.desktop.session idle-delay` prints `uint32 300` and `gsettings get org.gnome.desktop.screensaver lock-enabled` prints `true`.

### 8.3 Don't open USB drives and CDs automatically
- [ ] Done

**Script:** ✅ Done by the script (`desktop` section, for every user).

**What:** Stop Ubuntu from mounting, opening and running programs from a USB stick or CD the moment it is plugged in.

**Why it matters:** A planted USB stick can start malware on its own if autorun is on.

**Clicking:** **Settings → Removable Media** → set **Software**, **Photos**, **Music** and **Video** to **Never** (or **Ask what to do**).

**Typing:** in **your own** terminal, **without** `sudo` (if it says **The key is not writable**, the script has already set and locked it for every user):
```bash
gsettings set org.gnome.desktop.media-handling autorun-never true     # never run programs from media
gsettings set org.gnome.desktop.media-handling automount false        # don't mount drives by themselves
gsettings set org.gnome.desktop.media-handling automount-open false   # don't open a window for them
```

**Check it worked:** `gsettings get org.gnome.desktop.media-handling autorun-never` prints `true`.

> [!NOTE]
> With automount off, a USB stick still works: click it in the Files side bar to open it.

### 8.4 Ctrl + Alt + Delete doesn't restart the computer
- [ ] Done

**Script:** ✅ Done by the script (`desktop` section).

**What:** Stop **Ctrl + Alt + Delete** on a text console (Ctrl + Alt + F3 and similar) from rebooting the machine straight away.

**Why it matters:** Anyone at the keyboard could restart the computer without logging in.

**Typing:**
```bash
sudo systemctl mask ctrl-alt-del.target
```

**Check it worked:** `systemctl is-enabled ctrl-alt-del.target` prints `masked`. (Inside your desktop, Ctrl + Alt + Delete still opens GNOME's log-out window; that's normal.)

### 8.5 Turn off crash reporting (optional)
- [ ] Done

**Script:** ✋ Not done by the script. Do this by hand.

**What:** Ubuntu sends crash reports with `apport`/`whoopsie`. Nothing on a practice image needs that, and it is one more service running as root.

**Typing:**
```bash
sudo systemctl disable --now whoopsie apport 2>/dev/null
sudo sed -i 's/^enabled=1/enabled=0/' /etc/default/apport
```

**Check it worked:** `systemctl is-enabled whoopsie` prints `disabled` (or `masked`), and `grep enabled /etc/default/apport` prints `enabled=0`.

---

## 9. SSH server (only if installed)

```bash
dpkg -l openssh-server       # "ii" at the start = installed
```

### 9.1 Not needed? Remove it.
- [ ] Done

**Script:** 🔎 If the README doesn't list SSH, the script offers to stop and disable it, including `ssh.socket` (default no); removing `openssh-server` is up to you.

If the README doesn't mention SSH or remote logins:
```bash
sudo systemctl disable --now ssh
sudo apt purge openssh-server
```
On **Ubuntu 22.10 and newer**, SSH is started on demand by `ssh.socket`: if the README does not need SSH, disable both units and check with `systemctl is-enabled ssh.socket ssh.service`.

### 9.2 Needed? Make it safe.
- [ ] Done

**Script:** ✅ Done by the script (`ssh` section).

```bash
sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak
sudo nano /etc/ssh/sshd_config
```

| Setting | Value | Why |
|---|---|---|
| `PermitRootLogin` | `no` | Nobody logs in directly as root |
| `PermitEmptyPasswords` | `no` | No logins without a password |
| `MaxAuthTries` | `4` | Fewer password guesses per connection |
| `X11Forwarding` | `no` | Don't forward the desktop |
| `LoginGraceTime` | `60` | Drop slow, half-finished logins |
| `ClientAliveInterval` | `300` | Close idle sessions |
| `ClientAliveCountMax` | `3` | (with the line above) |
| `HostbasedAuthentication` | `no` | Old, weak login method |
| `IgnoreRhosts` | `yes` | Old, weak login method |
| `PermitUserEnvironment` | `no` | Users can't change SSH's environment |
| `AllowTcpForwarding` | `no` | No tunnelling through this computer |
| `LogLevel` | `VERBOSE` | Better logs |
| `Banner` | `/etc/issue.net` | Show a warning before login |

Then test and reload:
```bash
sudo sshd -t && sudo systemctl reload ssh       # sshd -t prints nothing if the file is OK
```
If `sshd -t` says **Missing privilege separation directory: /run/sshd**, SSH is stopped right now: run `sudo mkdir -p /run/sshd` and test again.

**Check it worked:** `sudo sshd -T | grep -Ei 'permitrootlogin|permitemptypasswords|maxauthtries'` shows `permitrootlogin no`, `permitemptypasswords no` and `maxauthtries 4`.

> [!WARNING]
> Leave `PasswordAuthentication yes` unless the README says otherwise. Nobody on a practice image has SSH keys set up, so turning passwords off locks everyone out.

### 9.3 Check for override files
- [ ] Done

**Script:** ✅ Done by the script (`ssh` section).

Files in `/etc/ssh/sshd_config.d/` are read **first**, and for SSH the first value wins, so they override everything above:
```bash
grep -r . /etc/ssh/sshd_config.d/ 2>/dev/null
sudo sshd -T | grep -Ei 'permitrootlogin|permitemptypasswords|passwordauthentication'   # the settings actually in use
```

### 9.4 Planted SSH keys
- [ ] Done

**Script:** 🔎 The script lists every `authorized_keys` file and offers to delete it (yes for root, no for others by default); you decide for each user.

```bash
sudo find / -name 'authorized_keys*' 2>/dev/null -exec ls -la {} \; -exec cat {} \;
```
A key in `/root/.ssh/authorized_keys` or in an unauthorized user's folder is almost certainly a backdoor. Delete the file (or the line).

---

## 10. Kernel and network settings (sysctl)

### 10.1 Turn on network and memory protections
- [ ] Done

**Script:** ✅ Done by the script (`kernel` section).

**Typing:**
```bash
sudo nano /etc/sysctl.conf
```
Add (or fix) these lines:
```
net.ipv4.tcp_syncookies = 1
net.ipv4.ip_forward = 0
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.all.log_martians = 1
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv6.conf.all.accept_redirects = 0
kernel.randomize_va_space = 2
kernel.dmesg_restrict = 1
kernel.kptr_restrict = 2
kernel.yama.ptrace_scope = 1
fs.suid_dumpable = 0
fs.protected_hardlinks = 1
fs.protected_symlinks = 1
```
Apply them now:
```bash
sudo sysctl -p
```

**Check:** `sysctl kernel.randomize_va_space` prints `= 2`. Also look for files in `/etc/sysctl.d/` that set the opposite (for example `ip_forward=1`): `grep -r . /etc/sysctl.d/`

### 10.2 Turn off core dumps
- [ ] Done

**Script:** ✅ Done by the script (`kernel` section).

**What:** Stop crashing programs from writing a "core dump" (a copy of everything in their memory) to disk.

**Why it matters:** A core dump can contain passwords and keys that were in the program's memory. `fs.suid_dumpable = 0` in 10.1 covers programs that run as root; this line covers everyone else.

**Typing:**
```bash
echo '* hard core 0' | sudo tee -a /etc/security/limits.conf
grep -rs core /etc/security/limits.conf /etc/security/limits.d/ | grep -v ':#'   # any other "core" line (e.g. "bob - core unlimited") overrides it: delete it
```

**Check it worked:** `sudo su - bob -c 'ulimit -Hc'` prints `0` (new logins pick it up; your open terminal keeps the old value). Don't check with `sudo -u bob`: `sudo` sets this limit by itself, so it can print `0` even when the setting is wrong.

---

## 11. File permissions

### 11.1 Password files
- [ ] Done

**Script:** ✅ Done by the script (`permissions` section).

```bash
ls -l /etc/passwd /etc/shadow /etc/group /etc/gshadow
sudo chmod 644 /etc/passwd /etc/group
sudo chmod 640 /etc/shadow /etc/gshadow
sudo chown root:shadow /etc/shadow /etc/gshadow
```

**Check it worked:** run the `ls -l` line again: `passwd` and `group` show `-rw-r--r-- root root`, `shadow` and `gshadow` show `-rw-r----- root shadow`.

### 11.2 SUID programs (run as root for anyone)
- [ ] Done

**Script:** 🔎 The script removes SUID from known-dangerous programs like `find` or `vim` (it asks first) and lists unknown ones under REVIEW for you to look up.

**Why:** If `find`, `vim`, `bash` or `python3` has the SUID bit, any user can become root with one command.

```bash
sudo find / -xdev -perm -4000 -type f 2>/dev/null
sudo chmod u-s /usr/bin/find
```
Normal SUID programs include `passwd`, `sudo`, `su`, `mount`, `umount`, `chsh`, `chfn`, `gpasswd`, `newgrp`, `pkexec`, `fusermount3` and `ssh-keysign`. Look up anything else.

### 11.3 Files anyone can change
- [ ] Done

**Script:** ✅ Done by the script (`permissions` section).

```bash
sudo find / -xdev -type f -perm -0002 ! -path '/proc/*' ! -path '/sys/*' 2>/dev/null
sudo chmod o-w /path/to/file
```

**Check it worked:** the `find` line prints nothing (files inside `/tmp` are OK).

### 11.4 Home folders
- [ ] Done

**Script:** ✅ Done by the script (`permissions` section).

```bash
ls -ld /home/*
sudo chmod 750 /home/bob        # other users can't look inside
```

**Check it worked:** in `ls -ld /home/*` every folder ends in `---`, e.g. `drwxr-x--- bob bob`. Each folder should also belong to its own user (`sudo chown bob: /home/bob` fixes one that doesn't).

---

## 12. Sudo rules

### 12.1 Check /etc/sudoers and /etc/sudoers.d/
- [ ] Done

**Script:** 🔎 The script removes `NOPASSWD` and `!authenticate` and offers to disable rules for non-admins; read the files again afterwards, because a rule can survive.

**Typing:**
```bash
sudo cat /etc/sudoers
sudo ls -la /etc/sudoers.d/ && sudo cat /etc/sudoers.d/*
```
Look for:
- `NOPASSWD`: sudo without a password. Remove it.
- Lines giving a **normal user** `ALL=(ALL) ALL`.
- `Defaults !authenticate`. Remove it.

**Edit only with visudo** (it checks for mistakes before saving):
```bash
sudo visudo                          # main file
sudo visudo -f /etc/sudoers.d/90-bob # a file in sudoers.d
```

> [!CAUTION]
> A typo in sudoers can break `sudo` for everyone. That's why you **always** use `visudo`.

---

## 13. Backdoors and malware

### 13.1 Scheduled jobs (cron)
- [ ] Done

**Script:** 🔎 The script removes cron jobs that look malicious (it asks first) and lists the rest under REVIEW; you check the others.

```bash
sudo ls -la /var/spool/cron/crontabs/                  # one file per user
for u in $(cut -d: -f1 /etc/passwd); do sudo crontab -l -u $u 2>/dev/null | grep -v '^#' | sed "s/^/$u: /"; done
cat /etc/crontab; ls -la /etc/cron.d /etc/cron.hourly /etc/cron.daily
sudo atq 2>/dev/null                                   # one-off "at" jobs (remove one: sudo atrm 3)
systemctl list-timers --all                            # systemd timers: another kind of scheduled job
```
Red flags: `nc`, `ncat`, `bash -i`, `/dev/tcp/`, `curl ... | bash`, `wget`, `base64 -d`, `python -c`, files in `/tmp`.

**Fix:** `sudo crontab -e -u bob` (delete the line), or `sudo rm /etc/cron.d/badfile`.

### 13.2 Services that start a backdoor at boot
- [ ] Done

**Script:** 🔎 The script lists services that didn't come from a package and offers to disable obviously bad ones; you check the rest and delete the unit files.

```bash
systemctl list-unit-files --type=service --state=enabled
ls -la /etc/systemd/system/ | grep -v '\.wants'
```
For any unit you don't recognise: `systemctl cat name.service` shows what it runs. Remove a bad one:
```bash
sudo systemctl disable --now evil.service && sudo rm /etc/systemd/system/evil.service && sudo systemctl daemon-reload
```

### 13.3 Programs listening for connections
- [ ] Done

**Script:** 🔎 The script offers to kill netcat-style listeners and lists every listening port under REVIEW; you still find what starts them.

```bash
sudo ss -tulpn
```
`nc`, `ncat`, `socat`, `python`, `perl` or `bash` listening on a port is almost always a backdoor. Note the PID, stop it (`sudo kill -9 PID`), **then find what starts it** (13.1, 13.2, 13.4).

### 13.4 Start-up files and fake commands
- [ ] Done

**Script:** 🔎 The script comments out suspicious lines and fake aliases in shell start-up files and in `/etc/rc.local`, which runs as root at every boot (it asks first); fake commands are only listed under REVIEW.

```bash
cat /etc/rc.local 2>/dev/null
ls /etc/profile.d/
grep -n 'alias' /home/*/.bashrc /root/.bashrc /etc/bash.bashrc
```
Watch for aliases that hijack commands, e.g. `alias sudo='...'` or `alias ls='...'`. Also check `/usr/local/bin` for programs named like system commands (a fake `ls` or `sudo`).

### 13.5 The hosts file
- [ ] Done

**Script:** ✅ Done by the script (`backdoors` section).

```bash
cat /etc/hosts
```
Only `127.0.0.1 localhost`, `127.0.1.1 <this computer's name>` and the `ip6-` lines are normal. A line like `10.6.6.6 www.google.com` sends that website to an attacker. Put `#` in front of it (`sudo nano /etc/hosts`).

**Check it worked:** `grep -v '^#' /etc/hosts` shows only the normal lines.

### 13.6 Hidden root-kit tricks
- [ ] Done

**Script:** 🔎 The script disables `/etc/ld.so.preload` and `auth sufficient pam_permit.so` lines (it asks first); still read `common-auth` for other `pam_permit` tricks.

```bash
cat /etc/ld.so.preload 2>/dev/null          # should not exist or be empty
grep -n 'pam_permit' /etc/pam.d/common-auth # "auth sufficient pam_permit.so" = anyone can log in
```

### 13.7 Programs that start when someone logs in
- [ ] Done

**Script:** 🔎 The script lists autostart entries under REVIEW; you decide which to remove.

**Clicking:** **GNOME Tweaks → Startup Applications** (`sudo apt install gnome-tweaks`), or just read the folders below.

**Typing:** `ls /etc/xdg/autostart/ /home/*/.config/autostart/`

### 13.8 Tampered system programs
- [ ] Done

**Script:** 🔎 The script reinstalls packages whose programs were changed (it asks first); other changed files in the `dpkg --verify` output are up to you.

```bash
sudo dpkg --verify | grep -v ' c '           # takes a minute or two; lines with a 5 = changed file
```
Fix by reinstalling the package that owns it: `dpkg -S /usr/bin/ls`, then `sudo apt install --reinstall coreutils`.

### 13.9 Malware scanners (optional, slow)
- [ ] Done

**Script:** ✋ Not done by the script. Do this by hand.

```bash
sudo apt install clamav rkhunter chkrootkit
sudo systemctl stop clamav-freshclam      # the updater service blocks a manual update while it runs
sudo freshclam                            # download the newest virus list
sudo systemctl start clamav-freshclam
sudo clamscan -ri /home                   # -r = every subfolder, -i = list only infected files
sudo rkhunter --check --sk                # --sk = don't stop for Enter after each part
sudo chkrootkit | grep INFECTED           # nothing printed = nothing found
```
These tools only **report**. Look at each file they name (forensics first!) before you delete it. Warnings from `rkhunter` and `chkrootkit` are often false alarms (for example `Linux.Xor.DDoS` for a harmless script in `/tmp`); `sudo less /var/log/rkhunter.log` shows the details.

---

## 14. Logging and auditing

### 14.1 System logs and the audit daemon
- [ ] Done

**Script:** ✅ Done by the script (`logging` section).

```bash
sudo apt install auditd rsyslog
sudo systemctl enable --now auditd rsyslog
```
Add audit rules that record changes to the password files:
```bash
echo '-w /etc/passwd -p wa -k identity
-w /etc/shadow -p wa -k identity
-w /etc/group -p wa -k identity
-w /etc/sudoers -p wa -k sudoers' | sudo tee /etc/audit/rules.d/50-practice.rules
sudo augenrules --load
```

**Check it worked:** `systemctl is-active auditd rsyslog` prints `active` twice, and `sudo auditctl -l` lists the `-w /etc/passwd` rules.

---

## 15. AppArmor

### 15.1 Make sure AppArmor is on
- [ ] Done

**Script:** ✅ Done by the script (`apparmor` section).

```bash
sudo aa-status
sudo systemctl enable --now apparmor
```
If a profile is in **complain** mode for no reason, enforce it (needs `sudo apt install apparmor-utils`):
```bash
sudo aa-enforce /usr/bin/man      # change /usr/bin/man to the name aa-status listed under "complain mode"
```

**Check it worked:** `sudo aa-status` starts with `apparmor module is loaded` and lists profiles `in enforce mode`; `systemctl is-enabled apparmor` prints `enabled`.

---

## 16. Critical services (only what the README lists)

If the README needs a web server, database, FTP, Samba or similar, **harden it instead of removing it**. Step-by-step: [Linux service hardening guide](../guides/linux-service-hardening.md).

---

## 17. Web browser (Firefox)

### 17.1 Firefox security settings
- [ ] Done

**Script:** 🔎 The script switches pop-up blocking, add-on install warnings and dangerous-site blocking back on when a user's Firefox files turn them off (`browser` section; Firefox must be closed). HTTPS-Only Mode, passwords and extensions are up to you.

**What:** Turn on Firefox's built-in protections. Images often switch them off.

**Why it matters:** Pop-ups, add-on installs and fake websites are how malware gets onto a desktop.

**Clicking:** open Firefox → **≡ → Settings → Privacy & Security**. Labels move between Firefox versions, so if you can't find one, type a word from it (`pop-up`, `add-ons`, `deceptive`, `HTTPS`) into the **Find in Settings** box at the top.
- **Block pop-up windows** ✔
- **Warn you when websites try to install add-ons** ✔
- **Block dangerous and deceptive content** ✔ (and the boxes under it)
- **HTTPS-Only Mode** → on in all windows
- **Passwords:** untick saving passwords unless the README needs it, and check **Saved passwords** for any that shouldn't be there

Then open **≡ → Add-ons and themes → Extensions** and remove any you don't recognise.

**Check it worked:** close and reopen Firefox, then look at the same page again: the boxes are still ticked. If a box is greyed out with "Your browser is being managed by your organization", look at `about:policies` to see which rule sets it.

> [!NOTE]
> Do this in the Firefox of the user you are logged in as. Each user has their own Firefox settings.

---

## 18. Final checks

- [ ] Every critical service is running: `systemctl status ssh` (repeat with each service the README lists)
- [ ] You can still use `sudo`
- [ ] The Scoring Report shows **no penalties**
- [ ] All forensics answers are saved
- [ ] Take a final snapshot
- [ ] **Don't reboot** unless you need to. If you must, reboot once and check everything still works.
