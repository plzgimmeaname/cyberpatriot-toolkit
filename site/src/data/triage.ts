// Score-dropped triage: when the Scoring Report loses points, the cause is
// almost always one of a short list of changes. Each area lists what to check
// and how to put it back. This is deliberately not a guess machine: it tells you
// where to look, and the round log tells you what you actually changed.

export interface Cause {
  /** The change people usually make that costs this category. */
  cause: string;
  /** The command or screen that confirms it. */
  check: string;
  /** How to put it back. */
  fix: string;
}

export interface TriageArea {
  id: string;
  label: string;
  blurb: string;
  causes: Cause[];
}

export const FIRST_MOVES = [
  'Stop changing things. Every extra change makes the cause harder to find.',
  'Write the score down, with the time. Read the Scoring Report line by line before touching anything.',
  'Open the round log: everything you changed since the last good score is a suspect.',
  'If the drop came right after a batch of changes, undo the batch, not one line at a time.',
  'Snapshot or restore point not taken? Say so out loud, then change only what you can reverse by hand.',
];

export const TRIAGE_AREAS: TriageArea[] = [
  {
    id: 'users',
    label: 'Users and groups',
    blurb: 'The most common self-inflicted drop: an account that a check expected to exist, or a group that lost its members.',
    causes: [
      {
        cause: 'You deleted an account that was supposed to stay (a scored user, or the account the README names).',
        check: 'Compare the README user list with the accounts on the machine.',
        fix: 'Re-create it with the README details, set the password, and put it back in the groups it was in. There is no undo for a deleted home directory unless you have a snapshot.',
      },
      {
        cause: 'You removed the last administrator, or removed yourself from sudo / Administrators.',
        check: 'Linux: `getent group sudo wheel`. Windows: `Get-LocalGroupMember -SID S-1-5-32-544` (works on non-English images).',
        fix: 'Re-add the account from another admin session. If there is none, boot the recovery/single-user mode from the snapshot.',
      },
      {
        cause: 'You disabled an account that was already correct (a service account, or a "keep" account in the README).',
        check: 'Look for accounts you disabled in the round log, then read the README again.',
        fix: 'Re-enable it. Disabling is reversible; deleting is not.',
      },
      {
        cause: 'You renamed an account a check matches by name.',
        check: 'The account list, next to the README list.',
        fix: 'Rename it back rather than creating a second account with the old name.',
      },
    ],
  },
  {
    id: 'firewall',
    label: 'Firewall',
    blurb: 'Two opposite mistakes: a firewall that is off (a direct penalty) or one that is on and blocking something that is scored.',
    causes: [
      {
        cause: 'You turned the firewall off to "fix" a connection problem.',
        check: 'Linux: `ufw status` / `nft list ruleset`. Windows: `Get-NetFirewallProfile`.',
        fix: 'Turn it back on and allow the specific port instead. Off is always worse than a wrong allow rule.',
      },
      {
        cause: 'You enabled a default-deny firewall without allowing the remote-access port, and lost your session.',
        check: 'Can you still reach the machine? If not, this is it.',
        fix: 'From the console, allow the port (`ufw allow 22/tcp`), then re-enable. If you have no console, restore the snapshot.',
      },
      {
        cause: 'You deleted the rules a scored service depends on (DNS, DHCP, file sharing).',
        check: 'Which service stopped working at the same time as the drop.',
        fix: 'Re-add the port for that service only, and confirm the service is still running.',
      },
    ],
  },
  {
    id: 'services',
    label: 'Services and roles',
    blurb: 'Stopping a service is fast and looks tidy. Stopping a scored one costs points, and stopping a role service takes the whole image with it.',
    causes: [
      {
        cause: 'You stopped a required service (DNS, DHCP, AD DS, Netlogon, sshd, the print spooler on some images).',
        check: '`systemctl --failed`, `Get-Service | ? Status -ne Running`.',
        fix: 'Start it and set it back to automatic/`enable`. Check the README for which services must stay up.',
      },
      {
        cause: 'You disabled a service that was supposed to be disabled already, but the startup type changed instead.',
        check: 'Startup type, not just state: `systemctl is-enabled`, `Get-CimInstance Win32_Service`.',
        fix: 'Set the startup type the check expects (usually Disabled for the bad ones, Automatic for the required ones).',
      },
      {
        cause: 'You uninstalled a package to remove a service.',
        check: '`dpkg -l | grep ^rc`; on Server, `Get-WindowsFeature` (not available on Windows 10/11).',
        fix: 'Reinstall it, then just stop and disable the service. Uninstalling breaks dependencies.',
      },
    ],
  },
  {
    id: 'permissions',
    label: 'Files and permissions',
    blurb: 'Prohibited-file points are easy; permission points are where recursive commands go wrong.',
    causes: [
      {
        cause: 'You deleted a file that was not prohibited (a config a service needs).',
        check: 'The service that started failing at the same time.',
        fix: 'Restore from the snapshot, or reinstall the package that owns it (`apt install --reinstall`).',
      },
      {
        cause: 'You ran a recursive chmod/chown over /etc or /home and broke ownership.',
        check: '`dpkg --verify` (Linux) or the service logs after the change.',
        fix: 'Snapshot restore is the honest fix. Hand-fixing ownership across /etc takes longer than the round.',
      },
      {
        cause: 'You removed SUID from a binary a scored check expects, or added it to one that should not have it.',
        check: '`find / -xdev -perm -4000 -type f` against the allow-list in the checklist.',
        fix: '`chmod u+s` back on the real ones (passwd, sudo, mount, su). Never add SUID to anything else.',
      },
    ],
  },
  {
    id: 'updates',
    label: 'Updates',
    blurb: 'A drop right after updates is usually a pending reboot, or a setting an update package reset.',
    causes: [
      {
        cause: 'Updates are installed but the machine has not rebooted, so they do not count yet.',
        check: '`/var/run/reboot-required` (Debian/Ubuntu), Windows Update history.',
        fix: 'Reboot once, wait for the Scoring Report, then re-check.',
      },
      {
        cause: 'An update reset a policy or reinstalled a service you had disabled.',
        check: 'Re-run the firewall, policy and service commands from the field card.',
        fix: 'Re-apply the setting, and note it in the round log so you do not chase it twice.',
      },
    ],
  },
  {
    id: 'remote',
    label: 'Remote access (SSH / RDP)',
    blurb: 'A broken sshd or RDP setting can drop points and your session at the same time.',
    causes: [
      {
        cause: 'You saved an sshd_config that sshd cannot parse.',
        check: '`sshd -t` (always run it before restarting).',
        fix: 'Fix the reported line, or restore the original from /etc/ssh/sshd_config.dpkg-old or the snapshot.',
      },
      {
        cause: 'You disabled RDP or its firewall rule while the README wanted it on (or vice versa).',
        check: '`Get-NetFirewallRule -DisplayGroup "Remote Desktop"`, System Properties → Remote.',
        fix: 'Match the README: usually RDP off but the rule and service state matter to different checks.',
      },
    ],
  },
  {
    id: 'desktop',
    label: 'Login screen and desktop',
    blurb: 'Locking down the desktop too hard can lock out the account that has to log in.',
    causes: [
      {
        cause: 'You set a shell of nologin, or expired the password, on the desktop account.',
        check: '`passwd -S alice` → must not say "NP" or "expired". `getent passwd alice`.',
        fix: '`chage -d today alice`, `usermod -s /bin/bash alice`, then log in to prove it.',
      },
      {
        cause: 'You restarted gdm/explorer mid-session and the greeter came up with settings that block login.',
        check: 'Log in on the console as the README user.',
        fix: 'Undo the greeter change from a TTY (Ctrl+Alt+F3) and restart the display manager.',
      },
    ],
  },
  {
    id: 'domain',
    label: 'Domain controller',
    blurb: 'On Server, a local-looking change can affect every domain account at once.',
    causes: [
      {
        cause: 'A tighter domain password policy locked out service accounts.',
        check: '`Get-ADDefaultDomainPasswordPolicy`, then the lockout state of the accounts.',
        fix: 'Unlock the account (`Unlock-ADAccount`) and relax the threshold or duration to something the accounts can live with.',
      },
      {
        cause: 'You stopped DNS, DHCP or Netlogon while tidying services.',
        check: '`Get-Service DNS,DHCP,Netlogon,ADWS`.',
        fix: 'Start them and set them Automatic. On a DC these are not optional services.',
      },
      {
        cause: 'You changed local policy on a DC and expected it to apply to domain users.',
        check: '`gpresult /r` — which GPO actually won.',
        fix: 'Change the domain policy instead, then `gpupdate /force`.',
      },
    ],
  },
  {
    id: 'browser',
    label: 'Browser and other settings',
    blurb: 'The long tail: a browser policy that is too strict, or a scored setting you disabled by accident.',
    causes: [
      {
        cause: 'You blocked something the browser check needs (an extension that is supposed to be allowed, or history).',
        check: 'The policies file (policies.json / registry) against the README.',
        fix: 'Remove the individual policy; do not turn off policy enforcement entirely.',
      },
      {
        cause: 'You changed a scored "on/off" setting and cannot remember which one.',
        check: 'The round log, newest first.',
        fix: 'Undo the last entry, wait for the score, then decide whether to redo it.',
      },
    ],
  },
];
