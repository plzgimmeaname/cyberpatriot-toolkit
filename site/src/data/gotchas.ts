// Things that bite you on a specific image. Everything here comes from working
// the image or from the official documentation, never from an answer key.
// kind: trap = costs points if you get it wrong, warn = likely to waste time,
// note = worth knowing before you start.

export interface Gotcha {
  image: string;
  title: string;
  detail: string;
  kind: 'trap' | 'warn' | 'note';
}

export const IMAGE_ORDER = ['windows', 'server', 'mint', 'ubuntu', 'debian', 'freebsd'];

export const GOTCHAS: Gotcha[] = [
  // ---- Windows 10 / 11 ------------------------------------------------------
  {
    image: 'windows',
    kind: 'trap',
    title: 'Turning Defender off is a penalty, not a fix',
    detail:
      'Disabling real-time protection, the firewall or Windows Update to stop a popup costs points directly. Fix the cause instead, and if a tool is being quarantined, add an exclusion for that file only.',
  },
  {
    image: 'windows',
    kind: 'trap',
    title: 'Deleting the built-in Administrator or Guest is worse than disabling it',
    detail:
      'Some scored checks expect the account to exist and be disabled. Disable it, rename it if the README says so, and never leave Guest enabled.',
  },
  {
    image: 'windows',
    kind: 'warn',
    title: 'Windows 11 Home has no Local Security Policy',
    detail:
      'secpol.msc is missing on Home editions. `net accounts` still works there, as do Settings → Accounts → Sign-in options; use the registry under HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies for the rest. Server 2022 and Pro editions have secpol.msc.',
  },
  {
    image: 'windows',
    kind: 'warn',
    title: 'A pending restart hides your work',
    detail:
      'Many changes only score after a reboot: update installs, some policy settings and Defender state. Reboot once, then read the Scoring Report again before you call it done.',
  },
  {
    image: 'windows',
    kind: 'note',
    title: 'Bring Sysinternals with you',
    detail:
      'Autoruns and Process Explorer are the fastest way to find persistence, but the image may have no internet. Download them before the round and keep them on a USB stick.',
  },

  // ---- Windows Server -------------------------------------------------------
  {
    image: 'server',
    kind: 'trap',
    title: 'Domain policy overrides local policy',
    detail:
      'On a domain controller, changing Local Security Policy does nothing for domain accounts. Set the Default Domain Policy (or a new GPO) with Group Policy Management, then run gpupdate /force and check with Get-ADDefaultDomainPasswordPolicy.',
  },
  {
    image: 'server',
    kind: 'trap',
    title: 'Never stop DNS, DHCP, AD DS or Netlogon',
    detail:
      'They look like ordinary services and stopping them breaks the domain, the network and hundreds of points at once. If a service is required by a scored role, leave it running.',
  },
  {
    image: 'server',
    kind: 'warn',
    title: 'A tighter domain password policy can lock out service accounts',
    detail:
      'Raising the minimum length or lowering the lockout threshold applies to every domain account immediately. Check for accounts with old passwords before you tighten it, and keep the lockout duration sane (15 minutes).',
  },
  {
    image: 'server',
    kind: 'note',
    title: 'Know where the local accounts still matter',
    detail:
      'Member servers keep local users, and the domain controller keeps a DSRM password. Local Administrator on a DC is not the domain Administrator: check both.',
  },

  // ---- Linux Mint -----------------------------------------------------------
  {
    image: 'mint',
    kind: 'warn',
    title: 'Update Manager can undo your settings',
    detail:
      'Mint 21 pops up Update Manager and, if you accept its defaults, it may rewrite configuration you changed. Finish your hardening first, then install updates, then re-check the settings that matter.',
  },
  {
    image: 'mint',
    kind: 'warn',
    title: 'auth.log exists only if rsyslog is installed',
    detail:
      'A normal Mint 21.3 install includes rsyslog, so /var/log/auth.log is there. A minimized or container-based image may leave it out, and then the file simply does not exist while the logins are in the journal. Run `ls /var/log/auth.log` first; if it is missing, `journalctl -u ssh --since -1h` is the same evidence.',
  },
  {
    image: 'mint',
    kind: 'trap',
    title: 'The live-session user is your only way back in',
    detail:
      'Your account is in sudo and is usually the one the README names. Do not lock or delete it, and if you change its password, write the new one down before you log out.',
  },
  {
    image: 'mint',
    kind: 'note',
    title: 'Timeshift is already installed',
    detail:
      'Take a Timeshift snapshot before the first change. It is the fastest undo on this image, and it is also the answer to "restore a file you deleted".',
  },

  // ---- Ubuntu ---------------------------------------------------------------
  {
    image: 'ubuntu',
    kind: 'note',
    title: 'This is the State round image',
    detail:
      'Ubuntu 24.04 replaced Debian in the CP-19 lineup. The checklist is nearly identical to Mint, with ufw installed and sudo available for the first user.',
  },
  {
    image: 'ubuntu',
    kind: 'warn',
    title: 'auth.log exists only if rsyslog is installed',
    detail:
      'A standard Ubuntu 24.04 install ships rsyslog, so /var/log/auth.log is present. Minimal server images and containers leave rsyslog out. Check `ls /var/log/auth.log`; when it is absent, `journalctl -u ssh` has the same events.',
  },
  {
    image: 'ubuntu',
    kind: 'warn',
    title: 'ufw is installed but inactive',
    detail:
      '`ufw status` says inactive until you enable it, and enabling it without allowing SSH first can cut your own session. Allow the port, then enable, then verify.',
  },
  {
    image: 'ubuntu',
    kind: 'warn',
    title: 'Ubuntu Pro prompts are not a scored setting',
    detail:
      'The "software updates are no longer provided" banner is about ESM, not your security posture. Do not sign in with a personal account; install the pending security updates with apt and move on.',
  },

  // ---- Debian ---------------------------------------------------------------
  {
    image: 'debian',
    kind: 'trap',
    title: 'The installer user is not in sudo',
    detail:
      'On a default Debian 12 install only root can administer the machine. Use `su -` with the root password from the README. Adding the user to sudo is fine, but do it deliberately, and then use one method consistently.',
  },
  {
    image: 'debian',
    kind: 'trap',
    title: 'No firewall is installed',
    detail:
      'There is no ufw, no firewalld and no rules by default. `apt install ufw` first, then default-deny incoming, allow the SSH port, enable, and check with `ufw status verbose`.',
  },
  {
    image: 'debian',
    kind: 'trap',
    title: 'No /var/log/auth.log either',
    detail:
      'Debian 12 logs to journald unless rsyslog is installed. Read `journalctl -u ssh`; if a forensics question asks about log files, install rsyslog and check again.',
  },
  {
    image: 'debian',
    kind: 'warn',
    title: 'The browser is firefox-esr, and it is a package',
    detail:
      'There is no `firefox` package: it is `firefox-esr`. Browser policies go in /etc/firefox-esr/policies.json, and per-user settings in the profile\'s user.js.',
  },
  {
    image: 'debian',
    kind: 'note',
    title: 'libpam-pwquality is not installed',
    detail:
      'Password quality rules do nothing until you `apt install libpam-pwquality` and the pam_pwquality line is present in /etc/pam.d/common-password. Verify with `grep pwquality`.',
  },
  {
    image: 'debian',
    kind: 'note',
    title: 'AppArmor is on by default — verify, do not assume',
    detail:
      'Debian has enabled AppArmor since Debian 10, so on 12 it is normally loaded. Check `cat /sys/module/apparmor/parameters/enabled` (Y) and `aa-status`. Only if it is off — which happens on some VMs and containers — add apparmor=1 security=apparmor to GRUB, run update-grub and reboot.',
  },

  // ---- FreeBSD --------------------------------------------------------------
  {
    image: 'freebsd',
    kind: 'trap',
    title: 'There is no bash and no systemctl',
    detail:
      'The default shell is sh and services are started by rc. `service sshd status`, `sysrc sshd_enable=NO`. A Linux command you paste blindly will fail, and a "fix" that edits systemd units on FreeBSD edits nothing.',
  },
  {
    image: 'freebsd',
    kind: 'trap',
    title: 'You can lock yourself out with pf',
    detail:
      'Load the rules with `pfctl -f /etc/pf.conf` and check `pfctl -sr` before enabling pf in rc.conf. If SSH is not allowed in the rules, enabling pf ends your session and your round.',
  },
  {
    image: 'freebsd',
    kind: 'warn',
    title: 'freebsd-update and pkg are two different update systems',
    detail:
      'The base system patches with freebsd-update, third-party software with pkg. "Updates installed" on the Scoring Report usually wants both, and a reboot for the kernel.',
  },
  {
    image: 'freebsd',
    kind: 'note',
    title: 'Root over SSH is off by default',
    detail:
      'FreeBSD ships `#PermitRootLogin no`, and sshd_config(5) documents no as the default, so password root logins are refused until someone changes it. Some practice images set `yes`. Read the line before touching it, and run `sshd -t` before restarting sshd: a broken config ends the session.',
  },
];

export function gotchasFor(image: string): Gotcha[] {
  return GOTCHAS.filter((g) => g.image === image);
}
