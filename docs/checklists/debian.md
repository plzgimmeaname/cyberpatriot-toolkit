# Debian checklist (Debian 11 / 12)

Debian 12 ("bookworm") is **not one of this season's images** (CyberPatriot 19 uses Linux Mint 21 and Ubuntu 24). Keep this checklist for older Debian images, and for practising the places where Debian differs from Mint.

This page is the **full job, start to finish**, the same way the [Linux Mint checklist](linux-mint.md) does it: every step says what to do, why it is scored, how to do it by clicking and by typing, and how to check it worked. Nothing here says "go read another page first".

> [!IMPORTANT]
> **The five big Debian differences** — read these before you start.
> 1. **`sudo` may not work.** If a root password was set when Debian was installed, your user isn't an admin. Use **`su -`** instead (step 0.4).
> 2. **No firewall is installed.** You must install and turn on `ufw` (section 4).
> 3. **No `/var/log/auth.log` on Debian 12.** Logs live in the **journal**, so use `journalctl` for forensics (step 1.1).
> 4. **Automatic updates are not installed** (section 5).
> 5. The desktop is **GNOME**, so the settings are in **Settings**, and the login screen is **GDM** (step 8.1), not Mint's tools.

Every step below has a **Script:** line:

- **✅** the script does the whole step.
- **🔎** the script does part of it or only reports it. Finish it yourself.
- **✋** the script doesn't do it. Do it by hand.

---

## 0. Before you touch anything

### 0.1 Read the README
- [ ] Done

**Script:** ✋ Not done by the script. Do this by hand.

**What:** Read the README.txt on the desktop **twice** and write down four lists on paper: authorized admins, authorized users, critical services, and anything the README forbids.

**Why it matters:** Every step below asks "is this in the README?". Getting those lists wrong is how teams lose points for deleting a user they were told to keep.

**Typing:** nothing yet. See [Reading the README](../start-here/reading-the-readme.md) for what to look for.

### 0.2 Take a snapshot
- [ ] Done

**Script:** ✋ Not done by the script. Do this by hand.

**What:** In VMware: **VM → Snapshot → Take Snapshot**. Name it `start`.

**Why it matters:** If a change makes your score go down, the snapshot is how you get back in under a minute.

**Clicking:** **VM → Snapshot → Take Snapshot…** → type `start` → **Take Snapshot**.

**Check it worked:** **VM → Snapshot → Snapshot Manager** lists `start`.

### 0.3 Open a terminal
- [ ] Done

**Script:** ✋ Not done by the script. Do this by hand.

**What:** Get a terminal window. Every "Typing" command on this page goes in it.

**Clicking:** In GNOME, press the **Super (Windows) key**, type `terminal`, press **Enter**. Or **Activities → Terminal**. Or `Ctrl + Alt + T`.

**Check it worked:** the window shows a prompt ending in `$` (normal user) or `#` (root).

### 0.4 Get admin rights: `sudo` or `su -`
- [ ] Done

**Script:** ✋ Not done by the script. Do this by hand.

**What:** Find out whether you can use `sudo`. This decides how every other command on this page is typed.

**Why it matters:** On Debian, the user you created during install is **not** an administrator unless the installer was given an empty root password. Commands like `usermod` and `ufw` just say "Permission denied" until you fix that.

**Typing:**
```bash
sudo -v
```
- **It asks for your password and then says nothing:** good. Use `sudo` in front of every command, like on Mint.
- **"user is not in the sudoers file", "may not run sudo" or "sudo: command not found":** become root with the README's root password:
  ```bash
  su -                # note the dash: it asks for ROOT's password
  ```
  Your prompt changes to `root@...#`. Now run every command on this page **without** `sudo`.

**Check it worked:** `id -u` prints `0` when you are root.

> [!WARNING]
> Use **`su -` with the dash**. Plain `su` keeps your own PATH, so commands such as `usermod`, `ufw` or `systemctl` answer "command not found".

> [!TIP]
> Working `sudo` is often scored, so it is worth installing it for the README's admins (this is also a real hardening step):
> ```bash
> apt install sudo
> usermod -aG sudo alice          # once per README admin, and never for anyone else
> ```
> They must **log out and back in** before `sudo` works.

### 0.5 Open the Scoring Report
- [ ] Done

**Script:** ✋ Not done by the script. Do this by hand.

**What:** Open the Scoring Report icon on the desktop and keep it open in another workspace.

**Why it matters:** It is the only honest answer to "did that help or hurt?". Refresh it after every section, not after every command.

**Clicking:** double-click the **Scoring Report** icon on the desktop. If it is not there, it is usually under **/root/Desktop** or **/home/*/Desktop**.

**Check it worked:** it shows a score and a list of categories with ✓ marks.

---

## 1. Forensics questions (do these FIRST)

### 1.1 Answer every forensics question before changing anything
- [ ] Done

**Script:** ✋ Not done by the script. Do this by hand.

**What:** Open the forensics questions in the competition interface and answer all of them **before** you delete users, remove files or install anything.

**Why it matters:** The questions are worth points on their own, and deleting the file (or the user) they ask about usually makes the question impossible to answer.

**Clicking:** in the competition window, the forensics questions are usually one tab; the Scoring Report shows how many of them are worth points.

**Typing:** the evidence is in the files, so this section is mostly searching. These four commands cover most questions. Use `sudo` (or run them as root after `su -`):
```bash
grep -rIl "password" /home /var/www 2>/dev/null | head -20     # files that mention a password
find /home -maxdepth 3 -type f -newer /etc/hostname | head    # files changed after install
sudo journalctl --list-boots | tail -5                         # boot history
last -a | head -20                                             # recent logins
```
For logs, Debian 12 has **no `/var/log/auth.log`** until you install `rsyslog` (step 14.1), so use the journal:
```bash
sudo journalctl _COMM=sshd | tail -50          # SSH logins and failures
sudo journalctl _COMM=sudo                     # every sudo command
sudo journalctl -u cron --since "2 days ago"   # cron jobs that ran
```
Without `sudo` (or root), `journalctl` shows only **your own** messages, so another user's login would be missing.

**Check it worked:** every forensics question is answered and saved **before** you run anything else.

> [!CAUTION]
> Answer the forensics questions first, then come back to section 2. If you already deleted something, the files in `/root/cyberpatriot/backups/` (made by the script) may still have it.

### 1.2 Fast path: run the hardening script
- [ ] Done

**What:** Once **every forensics question is answered**, run the toolkit's `scripts/linux/harden.sh`. It fixes many of the steps below and gives you a to-do list for the rest.

**Why it matters:** The script does in a few minutes what takes an hour by hand, and it backs up every file before changing it. That leaves your time for the steps that need a human.

**Typing:**
1. Get the script onto the image: open [Download the scripts](/downloads/) on this website and run the **Linux** download commands there. They save `harden.sh` and an example config in `~/cp`. No internet on the image? See [Using the scripts](../start-here/using-the-scripts.md).
2. Optional: make a config file with the [README config builder](/tools/config-builder/) and save it as `my.conf` in `~/cp`, next to `harden.sh`. No config? Leave out `--config my.conf` and the script asks for the README names instead.
3. Run it in **audit** mode first (it changes nothing) and read every `REVIEW` line. Then apply:
```bash
cd ~/cp
sudo bash harden.sh --audit --config my.conf        # report only: read the REVIEW lines
sudo bash harden.sh --apply --config my.conf        # make the changes (it asks before risky ones)
sudo cat /root/cyberpatriot/findings-*.txt          # your to-do list: every REVIEW item
```

**`sudo` doesn't work yet (step 0.4)?** Use `su -` and leave `sudo` out. `su -` takes you to root's home folder, so `cd` back first:
```bash
su -                                    # asks for ROOT's password
cd /home/alice/cp                       # your own user's home folder + /cp
bash harden.sh --apply --config my.conf
```
Run this way the script cannot tell who you are, so make sure **your own account** is in the README admin list you give it. It also will not lock root (step 2.8).

**Check it worked:** the summary at the end shows mostly `OK` and `CHANGED`. Refresh the **Scoring Report**: the score should have gone up.

Now skip every step marked **Script: ✅** (on the website, press **Tick the script's ✅ steps** at the top of the page) and do the 🔎 and ✋ steps.

> [!WARNING]
> If any line says `FAILED`, do that step by hand. If the score goes **down**, undo the change from the backups in `/root/cyberpatriot/backups/` (see [Using the scripts](../start-here/using-the-scripts.md#undoing-a-change)).

---

## 2. Users and groups

### 2.1 See every user on the computer
- [ ] Done

**Script:** 🔎 The script shows the users on this machine and flags every one that isn't in the README; you still type the README names in correctly.

**What:** Get the list of real (human) users and compare it with the README.

**Clicking:** **Settings → Users** → click **Unlock** (top right) and enter a password. Every account is listed with its account type.

**Typing:**
```bash
awk -F: '$3 >= 1000 && $3 < 65534 {print $1}' /etc/passwd
```
This prints every user with a user ID (UID) of 1000 or more, which means the real people.

**Check it worked:** the list matches the README's users and admins, or you now know exactly which names are extra.

### 2.2 Delete users who are not in the README
- [ ] Done

**Script:** ✅ Done by the script (`users` section).

**What:** Remove each account that isn't listed as an authorized admin or user.

**Why it matters:** An extra account is the easiest way for an attacker to get back in.

**Clicking:** **Settings → Users** → **Unlock** → click the user → **Remove User…**

**Typing:**
```bash
sudo deluser mallory          # or, as root: deluser mallory
```
`deluser` keeps the home folder by default. That's fine: the account is what is scored, and keeping the files helps if you need their files for a forensics question.

**Check it worked:** `id mallory` says `no such user`.

> [!CAUTION]
> Check the spelling against the README **three times**. Deleting an authorized user is a penalty. Never delete yourself, `root`, or system accounts (UID below 1000 like `www-data`, `syslog`, `messagebus`).

### 2.3 Create users the README says should exist
- [ ] Done

**Script:** 🔎 The script creates missing README users (and makes README admins administrators), but they only get a password if you give it one (NEW_PASSWORD or when asked).

**What:** Add every user the README lists but the computer doesn't have.

**Typing:**
```bash
sudo adduser erin            # asks for a password and the full-name fields
```
`adduser` is the Debian-friendly wrapper: it creates the home folder, sets the shell and asks for a password in one go.

**Check it worked:** `id erin` shows the account, and `ls /home` shows the home folder.

### 2.4 Fix who is an administrator
- [ ] Done

**Script:** ✅ Done by the script (`users` section).

**What:** Only the README's admins should be in the `sudo` group (that's what "Administrator" means on Debian).

**Clicking:** **Settings → Users** → click the user → toggle **Administrator**.

**Typing:**
```bash
getent group sudo                       # who has sudo now
sudo deluser bob sudo                   # take admin away from bob
sudo usermod -aG sudo alice             # give admin to alice
getent group adm                        # 'adm' can read logs - normally admins only
```

**Check it worked:** `getent group sudo` lists only the README admins. On Debian, `root` is not in that group, which is normal.

> [!NOTE]
> If `sudo` is not installed at all (step 0.4), a user cannot be an administrator yet: `apt install sudo` first, then add the admins to the group.

### 2.5 Look for hidden root accounts and hidden users
- [ ] Done

**Script:** 🔎 The script finds UID-0 and hidden login accounts and offers to delete them or block their logins; you decide for each hidden user (say no if it belongs to a program).

**What:** Look for a second account with UID 0 (a second root), and for accounts with a login shell that are not supposed to exist.

**Why it matters:** An attacker who adds a UID-0 account has root no matter what password you set on the real root.

**Typing:**
```bash
awk -F: '$3 == 0 {print $1}' /etc/passwd                       # every UID-0 account: only 'root' should appear
getent passwd | awk -F: '$7 !~ /(nologin|false)$/ {print $1, $3, $7}'   # accounts that can log in
ls -l /home                                                    # home folders nobody mentioned
```

**Check it worked:** only `root` has UID 0, and every account with a shell is one the README knows about.

> [!TIP]
> Deleting a UID-0 account that a program uses can break that program. If in doubt, block the login instead and write it on your to-do list:
> ```bash
> sudo usermod -L -s /usr/sbin/nologin sysbackup
> ```

### 2.6 Check other powerful groups
- [ ] Done

**Script:** 🔎 The script removes non-admins from root, shadow, disk, kmem, docker and lxd (it asks first); check `sambashare` and any admins in these groups yourself.

**What:** These groups give root-equivalent power without being called "sudo":

| Group | What it really means |
|---|---|
| `root` | same as root |
| `shadow` | can read password hashes |
| `disk` | can read the raw disk, ignoring file permissions |
| `kmem` | can read kernel memory |
| `docker`, `lxd` | can start a container that mounts `/` as root |

**Typing:**
```bash
for g in root shadow disk kmem docker lxd adm; do echo "$g: $(getent group $g | cut -d: -f4)"; done
sudo deluser bob shadow        # remove only people who are not README admins
```

**Check it worked:** only README admins appear in those groups (empty is fine).

### 2.7 Give users strong passwords
- [ ] Done

**Script:** 🔎 The script gives every authorized user except you one strong password only if you set NEW_PASSWORD or type one when asked; otherwise do this by hand.

**What:** Every account the README authorizes needs a password nobody will guess. Use **one** strong password for the team's accounts if the competition allows it, and write it down.

**Typing:**
```bash
sudo passwd bob                # type the new password twice (it is not echoed)
```
A strong password here means 12+ characters with upper case, lower case, a number and a symbol, e.g. `Cyb3r!Patr1ot#2026`.

**Check it worked:** log in as that user in a second terminal (`su - bob`) and then `exit`.

> [!CAUTION]
> Changing **your own** password is fine, but write the new one down immediately. Locking yourself out of the image costs the rest of the round.

### 2.8 The root account on Debian
- [ ] Done

**Script:** 🔎 The script locks root only if you ran it with `sudo` from an admin account; if you still need `su -`, give root a strong password yourself.

**What:** On Debian, **root may have a working password** (Mint and Ubuntu lock it). Decide which way you need it.

**Why it matters:** A working root password is a login an attacker can guess. But if no admin has `sudo`, locking root locks *everyone* out.

**Typing:**
```bash
sudo passwd -S root            # P = has a password, L = locked
```
- README admins can use `sudo` (step 0.4)? Lock root: `sudo passwd -l root`
- You still depend on `su -`? **Don't lock it.** Just make sure the password is strong: `passwd root`

**Check it worked:** `passwd -S root` prints `L` (locked) or `P` (has a password) and you know *why* it is what it is.

### 2.9 Accounts with no password
- [ ] Done

**Script:** 🔎 The script lists every account with an empty password and locks the ones that aren't in the README (it asks first); README users with no password get one from you.

**What:** Find accounts whose password field in `/etc/shadow` is empty: anyone can log in as them with no password at all.

**Typing:**
```bash
sudo awk -F: '$2 == "" {print $1}' /etc/shadow        # empty password field
sudo passwd -S alice                                  # 'NP' means no password
```
Fix each one: `sudo passwd <name>` for README users, or `sudo passwd -l <name>` for accounts nobody should use.

**Check it worked:** the `awk` line prints nothing.

---

## 3. Password and lockout policy

### 3.1 Password aging (how long passwords last)
- [ ] Done

**Script:** ✅ Done by the script (`passwords` section).

**What:** Make passwords expire after 90 days, refuse a change within 7 days of the last one, and warn 14 days before expiry.

**Why it matters:** It is a scored category on every Linux image, and the defaults on Debian are usually "never expires".

**Typing:**
```bash
sudo nano /etc/login.defs
```
Set these four lines (remove any `#` in front):
```
PASS_MAX_DAYS   90
PASS_MIN_DAYS   7
PASS_WARN_AGE   14
ENCRYPT_METHOD  SHA512
```
Or in one command:
```bash
sudo sed -i -E 's/^#?\s*PASS_MAX_DAYS.*/PASS_MAX_DAYS   90/; s/^#?\s*PASS_MIN_DAYS.*/PASS_MIN_DAYS   7/; s/^#?\s*PASS_WARN_AGE.*/PASS_WARN_AGE   14/' /etc/login.defs
```

**Check it worked:** `grep -E '^PASS_(MAX_DAYS|MIN_DAYS|WARN_AGE)' /etc/login.defs` shows 90, 7 and 14.

### 3.2 Apply aging to the users who already exist
- [ ] Done

**Script:** ✅ Done by the script (`passwords` section).

**What:** `login.defs` only affects **new** users. Existing accounts need `chage`.

**Typing:**
```bash
sudo chage -l alice                       # the current settings for one user
sudo chage -M 90 -m 7 -W 14 alice         # set max 90, min 7, warn 14
```
For every human account at once:
```bash
for u in $(awk -F: '$3 >= 1000 && $3 < 65534 {print $1}' /etc/passwd); do sudo chage -M 90 -m 7 -W 14 "$u"; done
```

**Check it worked:** `sudo chage -l alice` shows "Maximum number of days between password change : 90".

### 3.3 Password complexity (pwquality)
- [ ] Done

**Script:** ✅ Done by the script (`passwords` section).

**What:** Refuse short or simple passwords: at least 12 characters, with upper case, lower case, a digit and a symbol.

**Why it matters:** Complexity rules are a scored item, and they make the passwords you set in step 2.7 actually strong.

**Typing:** Debian doesn't install the module by default:
```bash
sudo apt install libpam-pwquality
sudo nano /etc/security/pwquality.conf
```
Set (remove the `#` in front of each):
```
minlen = 12
dcredit = -1
ucredit = -1
lcredit = -1
ocredit = -1
difok = 3
maxrepeat = 3
usercheck = 1
```
Then make PAM use it, at the top of the **password** stack:
```bash
grep -n pwquality /etc/pam.d/common-password      # is it already there?
```
If it is missing, add this line **above** the `pam_unix.so` line in `/etc/pam.d/common-password`:
```
password requisite pam_pwquality.so retry=3 enforce_for_root
```
and add `use_authtok` to the `pam_unix.so` line so it can't be bypassed.

**Check it worked:** `grep -E '^minlen' /etc/security/pwquality.conf` prints `minlen = 12`, and setting a 6-character password with `sudo passwd bob` is refused.

### 3.4 Password history (no re-using old passwords)
- [ ] Done

**Script:** ✅ Done by the script (`passwords` section).

**What:** Refuse the last 5 passwords when someone changes theirs.

**Typing:**
```bash
sudo nano /etc/pam.d/common-password
```
On the `pam_unix.so` line, add `remember=5` and `minlen=12` at the end:
```
password [success=1 default=ignore] pam_unix.so obscure yescrypt remember=5 minlen=12
```
Your line may say `sha512` instead of `yescrypt`, and `use_authtok` may already be there. Keep what is there and only add the two options.

**Check it worked:** `grep pam_unix /etc/pam.d/common-password` shows `remember=5` and `minlen=12`.

### 3.5 No logins with an empty password
- [ ] Done

**Script:** ✅ Done by the script (`passwords` section).

**What:** Remove `nullok` from the authentication stack so an account with an empty password can't log in.

**Typing:**
```bash
sudo sed -i 's/ nullok//g' /etc/pam.d/common-auth
grep pam_unix /etc/pam.d/common-auth        # no 'nullok' should be left
```
Then, for any account with an empty password (step 2.9), set one or lock it.

**Check it worked:** the `grep` prints a line with no `nullok` in it.

### 3.6 Account lockout after failed logins (careful!)
- [ ] Done

**Script:** 🔎 The script turns on lockout only if ENABLE_LOCKOUT=yes or you answer yes when asked; then do the `su - bob` test in a new terminal.

**What:** Lock an account for 15 minutes after 5 wrong passwords.

**Why it matters:** It stops an attacker guessing passwords at a keyboard.

> [!CAUTION]
> PAM controls **every** login. One mistake here can stop *everyone* (including you) logging in. Before editing:
> 1. Open a **second terminal** and run `sudo -i` (or `su -`). Leave it open: it is your way back in.
> 2. Copy the file: `sudo cp /etc/pam.d/common-auth /etc/pam.d/common-auth.bak`
> 3. After editing, test in a **third** terminal: `su - bob`. If that fails, restore the copy from terminal 2.

**Typing:** Debian 12 has `pam_faillock` (Debian 11 needs `pam_tally2`, see the note below).

1. Settings file:
   ```bash
   sudo nano /etc/security/faillock.conf
   ```
   Set `deny = 5`, `unlock_time = 900` and `fail_interval = 900` (remove the `#`).
2. Edit `/etc/pam.d/common-auth`. The **order matters**: the start of the "Primary" block becomes exactly this:
   ```
   auth    requisite                       pam_faillock.so preauth
   auth    [success=2 default=ignore]      pam_unix.so
   auth    [default=die]                   pam_faillock.so authfail
   auth    requisite                       pam_deny.so
   auth    optional                        pam_faillock.so authsucc
   auth    required                        pam_permit.so
   ```
   Note `success=2` (it was `success=1`): it skips over the `authfail` and `pam_deny` lines when the password is right.
3. Add to the **end** of `/etc/pam.d/common-account`:
   ```
   account required                        pam_faillock.so
   ```

**Check it worked:** `su - bob` with the right password works, and `sudo faillock --user bob` shows the failures. Locked someone out while testing? `sudo faillock --user bob --reset`.

> [!NOTE]
> Debian 11 (bullseye) is too old for `pam_faillock`: use `pam_tally2` instead — `auth required pam_tally2.so onerr=fail deny=5 unlock_time=900` as the **first** `auth` line in `common-auth`, and `account required pam_tally2.so` at the end of `common-account`.

---

## 4. Firewall

### 4.1 Install and turn on the firewall
- [ ] Done

**Script:** ✅ Done by the script (`firewall` section).

**What:** Block every incoming connection except the ones the README needs.

**Why it matters:** Debian ships with **no firewall turned on**, so this is a scored item and a real hole. Ubuntu and Mint have `ufw` ready to switch on; Debian needs it installed first.

**Typing:**
```bash
sudo apt install ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp            # ONLY if SSH is a critical service in the README
sudo ufw enable
sudo ufw logging on
```
`ufw enable` warns that it may disrupt SSH: answer `y` only if you already allowed port 22 for an SSH service you need.

**Clicking:** prefer clicking? `sudo apt install gufw`, then open **Firewall Configuration** from the menu, set **Incoming: Deny**, **Outgoing: Allow**, switch **Status** on.

**Check it worked:** `sudo ufw status verbose` shows `Status: active` and `Default: deny (incoming)`.

### 4.2 Allow the critical services (and nothing else)
- [ ] Done

**Script:** 🔎 The script opens the ports for the critical services you entered (plus EXTRA_PORTS); check `sudo ufw status` matches the README, especially for services it doesn't know.

**What:** Open a port only for a service the README says must keep running.

| README needs | Command |
|---|---|
| SSH | `sudo ufw allow 22/tcp` |
| Web server (Apache/Nginx) | `sudo ufw allow 80/tcp` and `sudo ufw allow 443/tcp` |
| FTP | `sudo ufw allow 21/tcp` |
| Samba (file sharing) | `sudo ufw allow samba` |
| MySQL from other computers | `sudo ufw allow 3306/tcp` |
| DNS server | `sudo ufw allow 53` |

**Check it worked:** `sudo ufw status numbered` lists exactly those ports and no others.

### 4.3 Remove rules an attacker added
- [ ] Done

**Script:** 🔎 The script lists `allow` rules that aren't for a critical service under REVIEW; you decide which to delete.

**What:** A rule that opens an odd port is either a backdoor or a leftover.

**Typing:**
```bash
sudo ufw status numbered
sudo ufw delete 3            # delete rule number 3 (check the number first!)
```
Look for odd ports like 4444, 1337, 31337, 6667, or "ALLOW Anywhere" on a port no critical service uses.

**Check it worked:** `sudo ufw status` shows only the README's services.

---

## 5. Updates

### 5.1 Check the software sources
- [ ] Done

**Script:** 🔎 The script flags unofficial sources, `[trusted=yes]` and a missing security source under REVIEW; you remove the bad ones.

**What:** Every line apt downloads programs from must be an official Debian mirror.

**Why it matters:** A source you don't recognise can install anything, and a missing security source means no security fixes at all.

**Typing:**
```bash
grep -rs '^[^#]' /etc/apt/sources.list*       # every source line, with the file it is in
```
The sources can be in `/etc/apt/sources.list` (one line per source: `deb http://... bookworm main`) or in a `.sources` file in `/etc/apt/sources.list.d/` (blocks of `URIs:`, `Suites:`, `Components:` lines). Check both. Ignore backup copies (`.save`, `.bak`, `~`): apt only reads `sources.list` and the `.list` / `.sources` files.

For Debian 12 you should see **`deb.debian.org/debian`** with **`bookworm`** and **`bookworm-updates`**, and **`security.debian.org/debian-security`** (or `deb.debian.org/debian-security`) with **`bookworm-security`**. Debian 11 says `bullseye` instead. Components are normally `main`; `non-free-firmware` is fine on Debian 12.

- A missing **security** source means no security updates: add it back.
- Anything with `[trusted=yes]` or `Trusted: yes`, or a mirror you don't recognise, should be removed unless the README needs it.
- A **`deb cdrom:`** line makes `apt update` fail or ask for the install disc. Put a `#` in front of it.

**Check it worked:** `sudo apt update` finishes without errors, and the security source is listed.

### 5.2 Install all updates
- [ ] Done

**Script:** 🔎 The script installs all updates only if FULL_UPGRADE=yes or you say yes when asked; otherwise do it here.

**What:** Bring every installed package up to date.

**Why it matters:** "Updates installed" is a scored category, and the missing security patches on a competition image are planted on purpose.

**Typing:**
```bash
sudo apt update
sudo apt full-upgrade -y
```
`full-upgrade` (not just `upgrade`) is what Debian wants when a package needs another one removed or installed to be updated.

**Check it worked:** run `apt list --upgradable` — it should print nothing but the "Listing…" line.

### 5.3 Turn on automatic updates
- [ ] Done

**Script:** ✅ Done by the script (`updates` section).

**What:** Install `unattended-upgrades` and switch on its daily timer.

**Why it matters:** It is a scored item on its own, and it means new security fixes install without anyone remembering.

**Typing:**
```bash
sudo apt install unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades       # answer Yes
cat /etc/apt/apt.conf.d/20auto-upgrades
```

**Check it worked:** the file contains `APT::Periodic::Update-Package-Lists "1";` and `APT::Periodic::Unattended-Upgrade "1";` (the script adds two more lines; that's fine). Also check the security origin is not commented out in `/etc/apt/apt.conf.d/50unattended-upgrades`:
```bash
grep -n 'security' /etc/apt/apt.conf.d/50unattended-upgrades | head -5
```

### 5.4 Packages "held" back from updating
- [ ] Done

**Script:** ✅ Done by the script (`updates` section).

**What:** A held package never updates, even during a full upgrade.

**Typing:**
```bash
apt-mark showhold              # anything listed will never update
sudo apt-mark unhold $(apt-mark showhold)      # release them all
```

**Check it worked:** `apt-mark showhold` prints nothing.

### 5.5 Update Firefox ESR and the README's apps
- [ ] Done

**Script:** 🔎 Done only if the script installed all updates (FULL_UPGRADE=yes or you said yes); still check these apps.

**What:** On Debian the browser package is **`firefox-esr`** (there is no `firefox` package, so `apt install firefox` fails). Thunderbird, LibreOffice and the README's critical services also update through `apt`.

**Typing:**
```bash
apt list --upgradable 2>/dev/null | grep -Ei 'firefox|thunderbird|libreoffice'   # anything listed is out of date
sudo apt install --only-upgrade firefox-esr thunderbird                          # skips any that aren't installed
```

**Check it worked:** the `apt list --upgradable` line prints nothing.

---

## 6. Services

### 6.1 See what's running and listening
- [ ] Done

**Script:** 🔎 The script puts the running services and listening ports in the findings report; you still look through them for anything odd.

**What:** Get two lists: services that are running, and sockets that are listening.

**Why it matters:** Every extra service is another way in. "Unnecessary services disabled" is one of the biggest categories on a Linux image.

**Typing:**
```bash
systemctl list-units --type=service --state=running
sudo ss -tulpn
```
`ss` shows what each process is listening on and which program owns it. `tcp`/`udp` and `LISTEN` mean "waiting for connections".

**Check it worked:** you can say, for every line, whether the README needs it.

### 6.2 Turn off services the README doesn't need
- [ ] Done

**Script:** 🔎 The script offers to stop (or remove) known services the README doesn't list; SSH, uninstalling, and services it doesn't know about are your call.

**What:** Stop (`disable --now`) and, where it is clearly not needed, remove (`purge`) the services the README doesn't mention.

**Why it matters:** A service you don't need is free points for the other team, and on Debian several of these are installed by default.

**Typing:**
```bash
sudo systemctl disable --now vsftpd     # change vsftpd to the service you are turning off
sudo apt purge vsftpd                   # remove it completely (change the name here too)
```
Common ones on Debian that are usually safe to stop when the README doesn't list them: `avahi-daemon`, `cups`, `bluetooth`, `rpcbind`, `nfs-server`, `vsftpd`, `xinetd`, `telnet`, `snmpd`, `squid`.

**Check it worked:** `systemctl is-enabled vsftpd` prints `disabled` or `masked`, and `ss -tulpn` no longer shows it.

> [!CAUTION]
> Never disable a service the README calls critical, and never disable networking (`networking`, `systemd-networkd`, `NetworkManager`) or you lose the network the scoring uses.

### 6.3 Make sure the critical services are running
- [ ] Done

**Script:** 🔎 The script starts the critical services it recognises from your list; check each one with `systemctl status`.

**What:** Every service the README calls critical must be running **and** enabled, or you lose those points.

**Typing:**
```bash
systemctl status apache2 --no-pager | head -5      # change apache2 to each critical service
sudo systemctl enable --now apache2
```

**Check it worked:** `systemctl is-active apache2` prints `active` and `systemctl is-enabled apache2` prints `enabled`.

---

## 7. Prohibited software and files

### 7.1 Hacking tools
- [ ] Done

**Script:** 🔎 The script removes known hacking-tool packages (it asks first), but only reports `netcat-openbsd` and hand-copied tools; check its REVIEW lines.

**What:** Remove the tools an attacker (or a scored checklist) would call "hacking software".

**Typing:**
```bash
dpkg -l | grep -Ei 'nmap|netcat|ncat|socat|john|hydra|aircrack|ettercap|wireshark|tcpdump|metasploit|nikto|sqlmap|crunch|medusa|hashcat'
sudo apt purge netcat-traditional netcat-openbsd nmap hydra john
```
Debian's standard install includes **`netcat-traditional`** (the `nc` command), a favourite for backdoors. Keep it only if the README's services need it.

**Check it worked:** the `dpkg -l` line shows nothing from that list, or only the ones the README needs.

### 7.2 Games
- [ ] Done

**Script:** 🔎 The script removes the games on its list (it asks first); look for any others and run `sudo apt autoremove`.

**What:** CyberPatriot images usually forbid games: they are free points and a distraction.

**Typing:** Debian's GNOME install can bring a whole set:
```bash
dpkg -l | grep -Ei 'gnome-games|aisleriot|mines|sudoku|mahjongg|chess|gnome-robots|tetravex|nibbles|klotski|quadrapassel|swell-foop|tali|four-in-a-row|five-or-more|hitori|iagno|lightsoff'
sudo apt purge gnome-games aisleriot gnome-mines gnome-sudoku
sudo apt autoremove --purge
```

**Check it worked:** the first command prints nothing.

### 7.3 File-sharing and remote-access programs
- [ ] Done

**Script:** 🔎 The script removes known torrent and remote-access programs, snaps and flatpaks (it asks first); check its REVIEW lines for any it skipped.

**What:** Remove programs that move files or give remote control unless the README needs them.

**Typing:**
```bash
dpkg -l | grep -Ei 'transmission|deluge|qbittorrent|rtorrent|vuze|teamviewer|anydesk|x11vnc|vnc4server|tightvnc|remmina|samba|cups'
sudo apt purge transmission-gtk qbittorrent
snap list 2>/dev/null; flatpak list 2>/dev/null      # only if those tools are installed
```

**Check it worked:** the list shows nothing except services the README requires.

### 7.4 Media files (music and video)
- [ ] Done

**Script:** 🔎 The script lists media files and offers to delete them all at once; read the list first and say no if any must stay (forensics, a website).

**What:** Competition images usually forbid music and video files.

**Typing:**
```bash
find /home /root -type f \( -iname '*.mp3' -o -iname '*.mp4' -o -iname '*.avi' -o -iname '*.mkv' -o -iname '*.wav' -o -iname '*.flac' -o -iname '*.mov' \) 2>/dev/null
sudo rm -v /home/bob/Music/song.mp3              # one file at a time, after reading the list
```

**Check it worked:** the `find` line prints nothing.

> [!CAUTION]
> A media file can be the answer to a forensics question ("what song is on the machine?"). Answer section 1 first, and check the list before deleting anything.

### 7.5 Other files that break policy
- [ ] Done

**Script:** 🔎 The script lists password lists, packet captures and similar files under REVIEW; you open each one and decide.

**What:** Files that are not programs but are still points to lose: password lists, `.pcap` captures, key files, torrents, hacking-tool source.

**Typing:**
```bash
find /home /root -type f \( -iname '*password*' -o -iname '*.pcap' -o -iname '*.kdbx' -o -iname '*.torrent' -o -iname '*.docx' \) 2>/dev/null | head -30
```
Open anything that looks interesting (it may be a forensics answer), then delete what the README forbids.

**Check it worked:** what is left is either needed by the README or needed for a forensics answer.

---

## 8. Login screen and desktop

### 8.1 No automatic login (GDM)
- [ ] Done

**Script:** ✅ Done by the script (`desktop` section).

**What:** Stop the computer logging a user in without a password.

**Why it matters:** Anyone who reboots the machine would land in a logged-in session with that user's files and privileges.

**Clicking:** **Settings → Users** → **Unlock** → turn off **Automatic Login** for every user.

**Typing:**
```bash
sudo nano /etc/gdm3/daemon.conf
```
In `[daemon]`:
```
AutomaticLoginEnable=false
TimedLoginEnable=false
```
In `[security]`: `DisallowTCP=true` (stops the old X11 remote login).

**Check it worked:**
```bash
grep -E 'AutomaticLogin|TimedLogin' /etc/gdm3/daemon.conf
```
shows `false` for both, with no user name left over.

### 8.2 Hide the list of users on the login screen
- [ ] Done

**Script:** ✅ Done by the script (`desktop` section).

**What:** Make the login screen ask for a user name instead of showing every account.

**Why it matters:** The list tells anyone at the keyboard which accounts exist, so they only have to guess a password.

**Typing:**
```bash
sudo sed -i 's/^# *disable-user-list=true/disable-user-list=true/' /etc/gdm3/greeter.dconf-defaults
grep disable-user-list /etc/gdm3/greeter.dconf-defaults      # disable-user-list=true, with no # in front
```
Or by hand: `sudo nano /etc/gdm3/greeter.dconf-defaults`, find `[org/gnome/login-screen]` and remove the `#` in front of `disable-user-list=true` (add the line under that heading if it isn't there).

**Check it worked:** the `grep` above. The login screen changes after the next restart.

> [!CAUTION]
> Don't run `systemctl restart gdm` to see it sooner: that logs you out at once and anything unsaved (like a forensics answer) is lost.

### 8.3 Lock the screen when idle
- [ ] Done

**Script:** 🔎 The script sets a 5-minute screen lock for all users with dconf; run the `gsettings` check, and set it by hand if the script says REVIEW.

**What:** After 5 minutes of no input, blank the screen and require the password again.

**Clicking:** **Settings → Privacy → Screen** (Debian 11: **Privacy → Screen Lock**): **Blank Screen Delay: 5 minutes**, **Automatic Screen Lock: On**, **Automatic Screen Lock Delay: Screen Turns Off**.

**Typing:** run these in **your own** terminal, **without** `sudo` (`sudo gsettings` changes root's settings, not yours):
```bash
gsettings set org.gnome.desktop.session idle-delay 300                 # 300 seconds = 5 minutes
gsettings set org.gnome.desktop.screensaver lock-enabled true
gsettings set org.gnome.desktop.screensaver lock-delay 0               # lock as soon as it starts
```
If it says **The key is not writable**, the script has already set and locked this for every user. That's fine.

**Check it worked:** `gsettings get org.gnome.desktop.session idle-delay` prints `uint32 300` and `gsettings get org.gnome.desktop.screensaver lock-enabled` prints `true`.

### 8.4 Don't open USB drives and CDs automatically
- [ ] Done

**Script:** ✅ Done by the script (`desktop` section, for every user).

**What:** Stop Debian from mounting, opening and running programs from a USB stick or CD the moment it is plugged in.

**Why it matters:** A planted USB stick can start malware on its own if autorun is on.

**Clicking:** in the Files app, open **Files → Preferences → Behaviour** and turn off the prompts that offer to run or open programs from removable media.

**Typing:** in **your own** terminal, **without** `sudo` (if it says **The key is not writable**, the script has already set and locked it):
```bash
gsettings set org.gnome.desktop.media-handling autorun-never true     # never run programs from media
gsettings set org.gnome.desktop.media-handling automount false        # don't mount drives by themselves
gsettings set org.gnome.desktop.media-handling automount-open false   # don't open a window for them
```

**Check it worked:** `gsettings get org.gnome.desktop.media-handling autorun-never` prints `true`.

> [!NOTE]
> With automount off, a USB stick still works: open it from the file manager's side bar.

### 8.5 Ctrl + Alt + Delete doesn't restart the computer
- [ ] Done

**Script:** ✅ Done by the script (`desktop` section).

**What:** Stop **Ctrl + Alt + Delete** on a text console (Ctrl + Alt + F3 and similar) from rebooting the machine straight away.

**Why it matters:** Anyone at the keyboard could restart the computer without logging in.

**Typing:**
```bash
sudo systemctl mask ctrl-alt-del.target
```

**Check it worked:** `systemctl is-enabled ctrl-alt-del.target` prints `masked`.

---

## 9. SSH server (only if installed)

```bash
dpkg -l openssh-server       # "ii" at the start = installed
```

### 9.1 Not needed? Remove it.
- [ ] Done

**Script:** 🔎 If the README doesn't list SSH, the script offers to stop and disable it, including `ssh.socket` (default no); removing `openssh-server` is up to you.

**What:** If the README doesn't call SSH a critical service, it must not be running.

**Typing:**
```bash
sudo systemctl disable --now ssh
sudo systemctl disable --now ssh.socket     # Debian 12 can listen through the socket instead
sudo apt purge openssh-server               # only if nothing else needs it
```

**Check it worked:** `ss -tulpn | grep ':22 '` prints nothing.

### 9.2 Needed? Make it safe.
- [ ] Done

**Script:** ✅ Done by the script (`ssh` section).

**What:** If SSH **is** critical, these settings must be right.

**Typing:**
```bash
sudo nano /etc/ssh/sshd_config
```
Set (or add):
```
PermitRootLogin no
PermitEmptyPasswords no
MaxAuthTries 4
X11Forwarding no
LoginGraceTime 30
```
Then, only if the README allows password logins for real users, leave `PasswordAuthentication yes`; otherwise `PasswordAuthentication no`.

**Check it worked:**
```bash
sudo sshd -t                 # no output = the config is valid
sudo sshd -T | grep -E 'permitrootlogin|permitemptypasswords|maxauthtries'
sudo systemctl restart ssh
```
`sshd -t` catching a typo *before* you restart is the difference between a fixed service and a dead one.

### 9.3 Check for override files
- [ ] Done

**Script:** ✅ Done by the script (`ssh` section).

**What:** Debian reads `/etc/ssh/sshd_config.d/*.conf` **before** `sshd_config`, and the first value wins.

**Typing:**
```bash
sudo grep -rs . /etc/ssh/sshd_config.d/ 2>/dev/null | head -30
sudo sshd -T | grep -E 'permitrootlogin|permitemptypasswords'    # what is really in effect
```

**Check it worked:** the second command shows the safe values, whatever the files contain. If an override file sets something unsafe, comment it out and restart SSH.

### 9.4 Planted SSH keys
- [ ] Done

**Script:** 🔎 The script lists every `authorized_keys` file and offers to delete it (yes for root, no for others by default); you decide for each user.

**What:** An `authorized_keys` file is a key that logs in without a password.

**Typing:**
```bash
sudo find /root /home -name authorized_keys 2>/dev/null -exec ls -l {} \;
sudo find /root /home -name authorized_keys 2>/dev/null -exec cat {} \;
```
Delete keys nobody recognises (yours start with `ssh-ed25519 AAAA…` and you know where they came from):
```bash
sudo rm -v /root/.ssh/authorized_keys
```

**Check it worked:** only keys your team owns are left, and `root` has none.

---

## 10. Kernel and network settings (sysctl)

### 10.1 Turn on network and memory protections
- [ ] Done

**Script:** ✅ Done by the script (`kernel` section).

**What:** A handful of kernel switches that stop common attacks (IP forwarding, source routing, SYN floods, ASLR off).

**Typing:**
```bash
sudo tee /etc/sysctl.d/99-cyberpatriot.conf >/dev/null <<'EOF'
net.ipv4.ip_forward = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.all.log_martians = 1
net.ipv4.tcp_syncookies = 1
net.ipv6.conf.all.accept_redirects = 0
kernel.randomize_va_space = 2
EOF
sudo sysctl --system
```

**Check it worked:** `sysctl net.ipv4.ip_forward kernel.randomize_va_space` shows `0` and `2`. Files planted in `/etc/sysctl.d/` or `/usr/lib/sysctl.d/` can override yours: `grep -rs ip_forward /etc/sysctl.conf /etc/sysctl.d/ /usr/lib/sysctl.d/` should show only your file.

### 10.2 Turn off core dumps
- [ ] Done

**Script:** ✅ Done by the script (`kernel` section).

**What:** Stop programs writing their memory to disk when they crash (that file can contain passwords).

**Typing:**
```bash
sudo tee /etc/security/limits.d/99-cyberpatriot.conf >/dev/null <<'EOF'
*    hard    core    0
*    soft    core    0
EOF
sudo sed -i -E 's/^[^#]*core[[:space:]]+unlimited/#&/' /etc/security/limits.conf
```

**Check it worked:** `ulimit -c` prints `0` after a new login, and `grep -rE '^[^#]*core' /etc/security/limits.conf /etc/security/limits.d/` shows nothing active.

---

## 11. File permissions

### 11.1 Password files
- [ ] Done

**Script:** ✅ Done by the script (`permissions` section).

**What:** Only root may read the password hashes.

**Typing:**
```bash
sudo chmod 640 /etc/shadow /etc/gshadow
sudo chmod 644 /etc/passwd /etc/group
sudo chown root:shadow /etc/shadow /etc/gshadow
sudo chown root:root /etc/passwd /etc/group
ls -l /etc/passwd /etc/shadow /etc/group /etc/gshadow
```

**Check it worked:** `/etc/shadow` is `-rw-r----- root shadow`, `/etc/passwd` is `-rw-r--r-- root root`.

### 11.2 SUID programs (run as root for anyone)
- [ ] Done

**Script:** 🔎 The script removes SUID from known-dangerous programs like `find` or `vim` (it asks first) and lists unknown ones under REVIEW for you to look up.

**What:** An SUID binary runs with the file owner's rights (usually root). A SUID `find`, `vim`, `python` or `nmap` is instant root for anyone.

**Typing:**
```bash
sudo find / -xdev -perm -4000 -type f 2>/dev/null | sort
sudo chmod u-s /usr/bin/find                     # remove SUID from the ones you know are wrong
```

**Check it worked:** the list contains only programs that are normally SUID on Debian (`passwd`, `su`, `mount`, `sudo`, `pkexec`, `chsh`, `gpasswd`, `newgrp`, `umount`, `fusermount3`…).

### 11.3 Files anyone can change
- [ ] Done

**Script:** ✅ Done by the script (world-writable scan), which asks first and skips `/proc`, `/sys` and `/dev`.

**What:** A world-writable file can be edited by any user, including a compromised service account.

**Typing:**
```bash
sudo find / -xdev -type f -perm -0002 ! -path '/proc/*' ! -path '/sys/*' ! -path '/dev/*' 2>/dev/null
sudo chmod o-w /etc/planted-ww.conf              # remove the write bit for "others"
```

**Check it worked:** the `find` list is empty (or only `/tmp`-style paths, which are fine).

### 11.4 Home folders
- [ ] Done

**Script:** ✅ Done by the script (`permissions` section).

**What:** Nobody else should be able to read another user's home folder.

**Typing:**
```bash
ls -ld /home/*
sudo chmod 750 /home/alice
sudo chown alice:alice /home/alice
```

**Check it worked:** `ls -ld /home/*` shows `drwxr-x---` (750) as the most permissive.

---

## 12. Sudo rules

### 12.1 Check /etc/sudoers and /etc/sudoers.d/
- [ ] Done

**Script:** 🔎 The script removes `NOPASSWD` and `!authenticate` and offers to disable rules for non-admins; read the files again afterwards, because a rule can survive.

**What:** Sudo rules that skip the password, or that let a normal user run anything, are as good as root.

**Typing:**
```bash
sudo cat /etc/sudoers
sudo ls -l /etc/sudoers.d/ && sudo cat /etc/sudoers.d/*
sudo grep -rE 'NOPASSWD|!authenticate|ALL=\(ALL' /etc/sudoers /etc/sudoers.d/
sudo visudo -c                                    # syntax check - a broken sudoers file locks everyone out
```
Remove or comment the bad lines, and always keep the last line of `/etc/sudoers`:
```
@includedir /etc/sudoers.d
```

**Check it worked:** `sudo visudo -c` says "parsed OK", `grep NOPASSWD` finds nothing, and `sudo -v` still works for a README admin.

---

## 13. Backdoors and malware

### 13.1 Scheduled jobs (cron)
- [ ] Done

**Script:** 🔎 The script removes cron jobs that look malicious (it asks first) and lists the rest under REVIEW; you check the others.

**What:** Cron runs commands on a schedule, as root if it is in a system file. It is the most common place to hide a backdoor.

**Typing:**
```bash
sudo ls -l /etc/cron.d /etc/cron.daily /etc/cron.hourly /etc/cron.weekly /etc/cron.monthly
sudo cat /etc/crontab /etc/cron.d/*
for u in $(cut -d: -f1 /etc/passwd); do sudo crontab -l -u "$u" 2>/dev/null | sed "s/^/$u: /"; done
```
Look for `nc`, `curl … | bash`, `base64 -d`, `/dev/tcp/`, `/tmp/.something`, or a job that downloads and runs something.

**Check it worked:** the only jobs left are ones you can explain, or `/etc/cron.d/updater` is gone.

### 13.2 Services that start a backdoor at boot
- [ ] Done

**Script:** 🔎 The script lists services that didn't come from a package and offers to disable obviously bad ones; you check the rest and delete the unit files.

**What:** A systemd unit that isn't owned by any package is suspicious: packages install their own units.

**Typing:**
```bash
sudo systemctl list-unit-files --type=service --state=enabled
dpkg -S /lib/systemd/system/*.service /etc/systemd/system/*.service 2>/dev/null | grep -v '^dpkg-query'
```
Anything that comes back "no path found" and isn't yours is worth reading:
```bash
sudo cat /etc/systemd/system/evil.service
sudo systemctl disable --now evil.service && sudo rm -v /etc/systemd/system/evil.service
```

**Check it worked:** every enabled unit belongs to a package you recognise.

### 13.3 Programs listening for connections
- [ ] Done

**Script:** 🔎 The script offers to kill netcat-style listeners and lists every listening port under REVIEW; you still find what starts them.

**What:** A shell listening on a port is an open door.

**Typing:**
```bash
sudo ss -tulpn
sudo lsof -i -P -n 2>/dev/null | head -20       # only if lsof is installed
```
A listener owned by `nc`, `ncat`, `socat`, `python`, `perl` or `/bin/sh` is a backdoor. Kill it and find what started it (cron, a service, `rc.local`):
```bash
sudo ss -tulpn | grep -E 'nc|socat|python|perl|sh '
sudo systemctl status $(sudo ss -tulpn | grep -o 'users:(("[^"]*"' | head -1 | cut -d'"' -f3)
```

**Check it worked:** every listening port belongs to a service the README needs.

### 13.4 Start-up files and fake commands
- [ ] Done

**Script:** 🔎 The script comments out suspicious lines and fake aliases in shell start-up files and in `/etc/rc.local`, which runs as root at every boot (it asks first); fake commands are only listed under REVIEW.

**What:** Attackers hide commands in files that run on every login or boot, and fake commands (`alias sudo='sudo -S'`) to capture passwords.

**Typing:**
```bash
grep -nE 'nc|/dev/tcp/|curl|wget|base64|chmod \+s|LD_PRELOAD' /etc/profile /etc/bash.bashrc /etc/profile.d/*.sh /etc/rc.local /root/.bashrc /home/*/.bashrc 2>/dev/null
grep -nE "^[[:space:]]*alias[[:space:]]+(sudo|su|ls|ps|cat|apt)" /etc/profile /etc/bash.bashrc /home/*/.bashrc 2>/dev/null
```
Put a `#` in front of anything you didn't put there. `/etc/rc.local` runs as **root** at boot, so a line there is worse than one in `.bashrc`.

**Check it worked:** both `grep` commands print nothing.

### 13.5 The hosts file
- [ ] Done

**Script:** ✅ Done by the script (`backdoors` section).

**What:** An entry in `/etc/hosts` can point a security site (or the scoring server) at an attacker's machine.

**Typing:**
```bash
cat /etc/hosts
sudo sed -i -E 's/^([^#].*\b(www\.google\.com|update\.microsoft\.com|security\.debian\.org))/#&/' /etc/hosts
```

**Check it worked:** `/etc/hosts` contains only `localhost`, the machine's own name and anything the README needs.

### 13.6 Hidden root-kit tricks
- [ ] Done

**Script:** 🔎 The script disables `/etc/ld.so.preload` and `auth sufficient pam_permit.so` lines (it asks first); still read `common-auth` for other `pam_permit` tricks.

**What:** Two classic tricks that make a machine stay compromised even after you fix everything else.

**Typing:**
```bash
cat /etc/ld.so.preload 2>/dev/null            # a preloaded library can hide processes and files
sudo rm -v /etc/ld.so.preload                 # Debian doesn't need this file
grep -n pam_permit /etc/pam.d/common-auth     # 'sufficient pam_permit.so' = any password works
```

**Check it worked:** `/etc/ld.so.preload` doesn't exist, and `common-auth` has no `pam_permit` before a `pam_unix` line.

### 13.7 Programs that start when someone logs in
- [ ] Done

**Script:** 🔎 The script lists autostart entries under REVIEW; you decide which to remove.

**What:** `~/.config/autostart` and the system-wide autostart folders run programs when a user logs in.

**Typing:**
```bash
grep -rl '^Exec=' /etc/xdg/autostart /home/*/.config/autostart 2>/dev/null
cat /home/bob/.config/autostart/*.desktop 2>/dev/null
```

**Check it worked:** every entry starts a program you recognise, or is deleted from `/home/<user>/.config/autostart`.

### 13.8 Tampered system programs
- [ ] Done

**Script:** 🔎 The script reinstalls packages whose programs were changed (it asks first); other changed files in the `dpkg --verify` output are up to you.

**What:** If `/usr/bin/passwd` or `/bin/ls` was replaced, everything you do on this machine can lie to you.

**Typing:**
```bash
sudo dpkg --verify 2>/dev/null | head -20        # files whose checksum changed
sudo apt install --reinstall coreutils passwd    # reinstall the package a changed file belongs to
```
Optional, faster to read: `sudo apt install debsums && sudo debsums -s`.

**Check it worked:** `dpkg --verify` prints nothing for the important packages.

### 13.9 Malware scanners (optional, slow)
- [ ] Done

**Script:** ✋ Not done by the script. Do this by hand, and only if you have time left.

**What:** Run a known scanner to catch rootkits the manual steps missed.

**Typing:**
```bash
sudo apt install rkhunter chkrootkit
sudo rkhunter --update --propupd
sudo rkhunter --check --sk 2>&1 | grep -i warning
sudo chkrootkit 2>&1 | grep -i infected
```
Read the warnings rather than deleting things blindly: rkhunter flags things like hidden files in `/tmp` that are often normal.

**Check it worked:** the summary says "no rootkits found", or you have a written list of the warnings you decided were false positives.

---

## 14. Logging and auditing

### 14.1 System logs and the audit daemon
- [ ] Done

**Script:** ✅ Done by the script (`logging` section).

**What:** Make sure lost logins and sudo commands are actually recorded, and install the audit daemon.

**Why it matters:** Debian 12 doesn't install `rsyslog` by default, so there is no `/var/log/auth.log` for forensics; and "logging enabled" is often scored.

**Typing:**
```bash
sudo apt install rsyslog auditd
sudo systemctl enable --now rsyslog auditd
sudo tee /etc/audit/rules.d/cyberpatriot.rules >/dev/null <<'EOF'
-w /etc/passwd -p wa -k identity
-w /etc/shadow -p wa -k identity
-w /etc/sudoers -p wa -k scope
-w /etc/sudoers.d/ -p wa -k scope
-w /etc/crontab -p wa -k cron
-w /var/log/lastlog -p wa -k logins
EOF
sudo augenrules --load && sudo auditctl -l | head
```

**Check it worked:** `sudo journalctl -u ssh --since today | head` shows events, `/var/log/auth.log` now exists for new logins, and `sudo auditctl -l` lists your rules.

> [!NOTE]
> `/var/log/auth.log` only contains events from the moment `rsyslog` was installed. Anything before that is in the journal only, so use `journalctl` for forensics (step 1.1).

---

## 15. AppArmor

### 15.1 Make sure AppArmor is on
- [ ] Done

**Script:** ✅ Done by the script (`apparmor` section).

**What:** AppArmor limits what each program may touch, even if it is running as root.

**Typing:**
```bash
sudo apt install apparmor apparmor-utils
sudo systemctl enable --now apparmor
sudo aa-status | head -20
```

**Check it worked:** `aa-status` says `apparmor module is loaded` and lists profiles in enforce mode. If it is "not loaded", add `apparmor=1 security=apparmor` to `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub`, run `sudo update-grub`, and reboot when the round allows it.

---

## 16. Critical services (only what the README lists)

Every service the README calls critical needs to be **running**, **enabled**, and **hardened**. Follow the [Linux service hardening guide](../guides/linux-service-hardening.md) for each one.

- [ ] Each critical service is running (`systemctl status <name>` → `active`)
- [ ] Each critical service is enabled (`systemctl is-enabled <name>` → `enabled`)
- [ ] Its web page (if it has one) opens from another machine
- [ ] The service's own config follows the hardening guide (banners, permissions, no anonymous access)

---

## 17. Web browser (Firefox ESR)

### 17.1 Firefox security settings
- [ ] Done

**Script:** 🔎 The script switches pop-up blocking, add-on install warnings and dangerous-site blocking back on when a user's Firefox files turn them off (`browser` section; Firefox must be closed). HTTPS-Only Mode, passwords and extensions are up to you.

**What:** Put back the safety settings an image may have turned off, and remember that Debian's browser package is **`firefox-esr`**.

**Typing:** first close Firefox, then edit the profile file:
```bash
ls -d /home/*/.mozilla/firefox/*.default* /root/.mozilla/firefox/*.default* 2>/dev/null
sudo tee -a /home/bob/.mozilla/firefox/abcd1234.default-release/user.js >/dev/null <<'EOF'
user_pref("browser.safebrowsing.malware.enabled", true);
user_pref("browser.safebrowsing.phishing.enabled", true);
user_pref("dom.disable_open_during_load", true);
user_pref("xpinstall.whitelist.required", true);
user_pref("browser.privatebrowsing.autostart", true);
EOF
```
Change the path to the profile you found above, and repeat for every user folder. (`user.js` is read at every start and overrides `prefs.js`, which is why it works even if the image reset the settings.)

**Check it worked:** open Firefox → **about:config** → search `safebrowsing.malware.enabled` → it is `true`.

---

## 18. Final checks

- [ ] Critical services running (`systemctl status <name>`)
- [ ] The README admins can use `sudo` (or you can still `su -`)
- [ ] `sudo ufw status` → active, and only the README's ports are open
- [ ] `sudo sshd -t` still passes if SSH is used
- [ ] `sudo visudo -c` says "parsed OK"
- [ ] `/etc/shadow` is 640 root:shadow
- [ ] Scoring Report shows **no penalties**
- [ ] Forensics answers saved, final snapshot taken
