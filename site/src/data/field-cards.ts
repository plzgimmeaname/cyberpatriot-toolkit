// The printable field card: the commands that actually decide a round, one
// screen per image, no explanations. Content is deliberately short so a whole
// card fits on one printed page; the full reasoning lives in the checklists.
// Commands are written to be safe to read on a locked-down exam machine: no
// wildcards that delete, no restarts, nothing that needs the internet.
//
// Verified 2026-11-15: every POSIX line was run in the Debian 12 and Ubuntu
// 24.04 containers; every flag was checked against pw(8), usermod(8), chage(1),
// ufw(8), net accounts, Set-LocalUser and Set-ADDefaultDomainPasswordPolicy.

export interface CardLine {
  /** What this line gets you. */
  do: string;
  /** The command, as typed. Omit for a "do this in the UI" line. */
  cmd?: string;
  /** A one-clause warning, only where a mistake costs points. */
  note?: string;
}

export interface CardGroup {
  title: string;
  lines: CardLine[];
}

export interface FieldCard {
  /** Same id as the checklist. */
  id: string;
  name: string;
  shell: 'PowerShell' | 'bash' | 'sh';
  intro: string;
  groups: CardGroup[];
}

const WINDOWS_COMMON: CardGroup[] = [
  {
    title: '0 · before anything',
    lines: [
      { do: 'Snapshot or restore point, then read the README out loud', note: 'no snapshot, no undo' },
      { do: 'Write the score and the time down', cmd: 'Get-Date', note: 'the score itself is on the Scoring Report, not in a command' },
      { do: 'Open PowerShell as Administrator', cmd: 'Start-Process powershell -Verb RunAs' },
    ],
  },
  {
    title: '1 · users and groups',
    lines: [
      { do: 'Every local account', cmd: 'Get-LocalUser | Format-Table Name,Enabled,LastLogon,PasswordLastSet' },
      { do: 'Who is an administrator', cmd: 'Get-LocalGroupMember Administrators', note: 'non-English image? use -SID S-1-5-32-544' },
      { do: 'Delete a bad account', cmd: 'Remove-LocalUser -Name mallory' },
      { do: 'Disable instead, if unsure', cmd: 'Disable-LocalUser -Name mallory' },
      { do: 'Set a strong local password', cmd: 'Set-LocalUser -Name alice -Password (Read-Host -AsSecureString)' },
      { do: 'Remote Desktop users', cmd: 'Get-LocalGroupMember "Remote Desktop Users"' },
    ],
  },
  {
    title: '2 · policy that scores',
    lines: [
      { do: 'Password and lockout policy', cmd: 'net accounts' },
      { do: 'Set the four numbers', cmd: 'net accounts /minpwlen:12 /maxpwage:60 /lockoutthreshold:5 /lockoutduration:15' },
      { do: 'Guest and built-in admin', cmd: 'net user Guest | Select-String "active"' },
      { do: 'Never turn off Defender or the firewall', note: 'both are scored, and off is a penalty' },
      { do: 'Defender state', cmd: 'Get-MpComputerStatus | Select RealTimeProtectionEnabled,AntivirusEnabled' },
      { do: 'Firewall on all profiles', cmd: 'Set-NetFirewallProfile -All -Enabled True' },
      { do: 'Firewall state', cmd: 'Get-NetFirewallProfile | Select Name,Enabled' },
    ],
  },
  {
    title: '3 · services, shares, backdoors',
    lines: [
      { do: 'Running services', cmd: 'Get-Service | Where-Object Status -eq Running | Sort Name' },
      { do: 'Auto services that are not running', cmd: 'Get-CimInstance Win32_Service | ? { $_.StartMode -eq "Auto" -and $_.State -ne "Running" }' },
      { do: 'Shares', cmd: 'Get-SmbShare' },
      { do: 'Scheduled tasks you did not expect', cmd: 'Get-ScheduledTask | ? { $_.TaskPath -notlike "\\Microsoft\\*" } | Select TaskName,TaskPath' },
      { do: 'Autoruns (Sysinternals)', cmd: 'autorunsc64.exe -accepteula -a * -nobanner -s' },
      { do: 'Every local account with its SID', cmd: 'Get-CimInstance Win32_UserAccount -Filter "LocalAccount=True" | Select Name,SID,Disabled', note: 'the SAM registry key needs SYSTEM, not just Administrator' },
    ],
  },
  {
    title: '4 · files and the browser',
    lines: [
      { do: 'Prohibited media in the usual places', cmd: 'Get-ChildItem C:\\Users -Recurse -Include *.mp3,*.mp4,*.wmv,*.mov -ErrorAction SilentlyContinue' },
      { do: 'Hacking tools left behind', cmd: 'Get-ChildItem C:\\Users -Recurse -Include nmap.exe,mimikatz.exe,netcat.exe -ErrorAction SilentlyContinue' },
      { do: 'Browser: remove unknown extensions and saved passwords', note: 'do this in the browser UI, one profile at a time' },
    ],
  },
];

const POSIX_HEAD: CardGroup = {
  title: '0 · before anything',
  lines: [
    { do: 'Snapshot first, then read the README', note: 'the score never comes back without one' },
    { do: 'Write the score down', cmd: 'date' },
    { do: 'Root shell (Debian: this, not sudo)', cmd: 'su -' },
  ],
};

const POSIX_USER: CardGroup = {
  title: '1 · users and groups',
  lines: [
    { do: 'Real human accounts', cmd: "awk -F: '$3>=1000 && $3<65534 {print $1, $3, $7}' /etc/passwd" },
    { do: 'Who can log in, and is the password empty', cmd: 'passwd -S -a' },
    { do: 'Hidden root accounts (UID 0)', cmd: "awk -F: '$3==0 {print $1}' /etc/passwd" },
    { do: 'sudo / wheel members', cmd: 'getent group sudo wheel' },
    { do: 'Delete an account and its files', cmd: 'deluser --remove-home mallory' },
    { do: 'Lock the password without deleting', cmd: 'usermod -L mallory' },
    { do: 'Expire the whole account (no login)', cmd: 'chage -E 0 mallory' },
  ],
};

const POSIX_POLICY: CardGroup = {
  title: '2 · passwords and lockout',
  lines: [
    { do: 'Password ageing', cmd: 'grep -E "^PASS_(MAX|MIN|WARN)" /etc/login.defs' },
    { do: 'Quality rules', cmd: 'grep -v "^#" /etc/security/pwquality.conf' },
    { do: 'Lockout module in use', cmd: 'grep -E "pam_(faillock|tally2)" /etc/pam.d/common-auth' },
    { do: 'Apply ageing to existing users', cmd: 'chage -M 90 -m 8 -W 14 alice' },
  ],
};

const POSIX_FIREWALL: CardGroup = {
  title: '3 · firewall and updates',
  lines: [
    { do: 'Is a firewall even installed', cmd: 'command -v ufw nft iptables' },
    { do: 'Rules', cmd: 'ufw status verbose' },
    { do: 'Default deny, allow SSH', cmd: 'ufw default deny incoming && ufw allow 22/tcp && ufw --force enable', note: '--force skips the y/n prompt' },
    { do: 'Pending updates', cmd: 'apt list --upgradable' },
    { do: 'Install everything', cmd: 'apt update && apt full-upgrade -y' },
  ],
};

const POSIX_SERVICES: CardGroup = {
  title: '4 · services and listeners',
  lines: [
    { do: 'Who is listening', cmd: 'ss -tulpn' },
    { do: 'Enabled at boot', cmd: 'systemctl list-unit-files --state=enabled --no-pager' },
    { do: 'Stop and disable one service', cmd: 'systemctl disable --now vsftpd' },
    { do: 'Failed units (and why)', cmd: 'systemctl --failed --no-pager' },
  ],
};

const POSIX_BACKDOOR: CardGroup = {
  title: '5 · backdoors',
  lines: [
    { do: 'Every user cron', cmd: "for u in $(cut -d: -f1 /etc/passwd); do crontab -l -u $u 2>/dev/null; done" },
    { do: 'System cron and units', cmd: 'ls -la /etc/cron.* /etc/cron.d; systemctl list-timers --all --no-pager' },
    { do: 'Startup scripts', cmd: 'cat /etc/rc.local; ls /etc/profile.d; cat /etc/ld.so.preload' },
    { do: 'SUID files that are not packages', cmd: 'find / -xdev -perm -4000 -type f 2>/dev/null' },
    { do: 'World-writable in system paths', cmd: 'find /etc /usr /bin /sbin -xdev -type f -perm -0002 2>/dev/null' },
    { do: 'ssh authorized_keys everywhere', cmd: 'find / -xdev -name authorized_keys 2>/dev/null' },
  ],
};

const POSIX_FILES: CardGroup = {
  title: '6 · prohibited files',
  lines: [
    { do: 'Media', cmd: "find /home /root /tmp -xdev -type f \\( -iname '*.mp3' -o -iname '*.mp4' -o -iname '*.mov' -o -iname '*.wmv' \\) 2>/dev/null" },
    { do: 'Games and hacking tools', cmd: "find / -xdev -type f \\( -iname '*.pcap' -o -iname 'netcat*' -o -iname 'nmap' -o -iname '*hack*' \\) 2>/dev/null" },
    { do: 'Move before deleting', cmd: 'mkdir -p /root/quarantine && mv /path/file /root/quarantine/' },
  ],
};

const POSIX_FINISH: CardGroup = {
  title: '7 · last five minutes',
  lines: [
    { do: 'SSH config is valid before restarting', cmd: 'sshd -t' },
    { do: 'What does this user actually get to run', cmd: 'sudo -l -U alice' },
    { do: 'Reboot once, then re-check score and services', cmd: 'systemctl reboot' },
  ],
};

export const FIELD_CARDS: FieldCard[] = [
  {
    id: 'windows-10-11',
    name: 'Windows 10 / 11',
    shell: 'PowerShell',
    intro: 'Run PowerShell as Administrator. Local Security Policy and Defender are scored: change them in the UI, verify here.',
    groups: WINDOWS_COMMON,
  },
  {
    id: 'windows-server',
    name: 'Windows Server',
    shell: 'PowerShell',
    intro: 'Everything on the Windows card, plus Active Directory. Domain policy overrides local policy: fix the domain first.',
    groups: [
      ...WINDOWS_COMMON,
      {
        title: '5 · Active Directory',
        lines: [
          { do: 'Domain password policy', cmd: 'Get-ADDefaultDomainPasswordPolicy' },
          { do: 'Fix it', cmd: 'Set-ADDefaultDomainPasswordPolicy -Identity (Get-ADDomain).DistinguishedName -MinPasswordLength 12 -LockoutThreshold 5 -LockoutDuration 00:15:00' },
          { do: 'Domain admins', cmd: 'Get-ADGroupMember "Domain Admins" | Select Name' },
          { do: 'Accounts that never expire their password', cmd: 'Get-ADUser -Filter * -Properties PasswordNeverExpires | ? PasswordNeverExpires | Select Name' },
          { do: 'Disabled accounts that still have a profile', cmd: 'Get-ADUser -Filter { Enabled -eq $false } | Select Name' },
          { do: 'Health of the domain controller', cmd: 'dcdiag /test:dns /v' },
          { do: 'Keep DNS, DHCP, AD DS and Netlogon running', note: 'stopping them costs hundreds of points' },
        ],
      },
    ],
  },
  {
    id: 'linux-mint',
    name: 'Linux Mint 21',
    shell: 'bash',
    intro: 'sudo works for the live user. Open Update Manager at the end: it can undo settings if left alone.',
    groups: [POSIX_HEAD, POSIX_USER, POSIX_POLICY, POSIX_FIREWALL, POSIX_SERVICES, POSIX_BACKDOOR, POSIX_FILES, POSIX_FINISH],
  },
  {
    id: 'debian',
    name: 'Debian 12',
    shell: 'bash',
    intro: 'The installer user is not in sudo: use su - and the root password from the README. No firewall is installed.',
    groups: [
      { ...POSIX_HEAD, lines: [{ do: 'Become root with the README password', cmd: 'su -' }, { do: 'Snapshot, then read the README', note: 'no snapshot, no undo' }, { do: 'Fix sudo for the main user (optional)', cmd: 'usermod -aG sudo alice' }] },
      POSIX_USER,
      { ...POSIX_POLICY, lines: [...POSIX_POLICY.lines, { do: 'Install the quality module first', cmd: 'apt install -y libpam-pwquality' }] },
      { ...POSIX_FIREWALL, lines: [{ do: 'Debian ships without one: install ufw', cmd: 'apt install -y ufw' }, ...POSIX_FIREWALL.lines] },
      POSIX_SERVICES,
      POSIX_BACKDOOR,
      POSIX_FILES,
      { ...POSIX_FINISH, lines: [...POSIX_FINISH.lines, { do: 'Logs live in journald, not auth.log', cmd: 'journalctl -u ssh --since -1h' }] },
    ],
  },
  {
    id: 'ubuntu',
    name: 'Ubuntu 24.04',
    shell: 'bash',
    intro: 'State round image. ufw is installed, sudo works, and there is no /var/log/auth.log: read journald.',
    groups: [POSIX_HEAD, POSIX_USER, POSIX_POLICY, POSIX_FIREWALL, POSIX_SERVICES, POSIX_BACKDOOR, POSIX_FILES, POSIX_FINISH],
  },
  {
    id: 'freebsd',
    name: 'FreeBSD 13 / 14',
    shell: 'sh',
    intro: 'No bash and no systemd. root logs in directly; services live in rc.conf and the firewall is pf.',
    groups: [
      {
        title: '0 · before anything',
        lines: [
          { do: 'Snapshot, then read the README', note: 'no snapshot, no undo' },
          { do: 'You are already root: who else is there', cmd: 'pw usershow -a' },
        ],
      },
      {
        title: '1 · users and groups',
        lines: [
          { do: 'Accounts with a real shell', cmd: "awk -F: '$3>=1000 {print $1, $3, $7}' /etc/passwd" },
          { do: 'Who is in wheel', cmd: 'pw group show wheel' },
          { do: 'Delete an account', cmd: 'pw userdel -n mallory -r' },
          { do: 'Lock it instead', cmd: 'pw lock mallory' },
        ],
      },
      {
        title: '2 · passwords',
        lines: [
          { do: 'Password ageing for a login class', cmd: 'grep -n passwordtime /etc/login.conf', note: 'empty unless the image sets it: FreeBSD has no max password age by default' },
          { do: 'Force a password change within 90 days', cmd: 'pw usermod alice -p +90d', note: '-p takes a date, not days: +90d, 31-mar-27 or a UNIX time' },
          { do: 'Expire the whole account in 90 days', cmd: 'pw usermod alice -e +90d' },
        ],
      },
      {
        title: '3 · updates',
        lines: [
          { do: 'Base system patches', cmd: 'freebsd-update fetch install' },
          { do: 'Packages', cmd: 'pkg upgrade -y' },
          { do: 'Audit installed packages', cmd: 'pkg audit -F' },
        ],
      },
      {
        title: '4 · services and firewall',
        lines: [
          { do: 'What runs at boot', cmd: 'service -e' },
          { do: 'Stop and disable one', cmd: 'sysrc sshd_enable=NO && service sshd stop' },
          { do: 'pf rules', cmd: 'pfctl -sr' },
          { do: 'Turn pf on', cmd: 'sysrc pf_enable=YES && service pf start' },
          { do: 'Open listeners', cmd: 'sockstat -4l' },
        ],
      },
      {
        title: '5 · backdoors and files',
        lines: [
          { do: 'Every user cron', cmd: 'crontab -l; ls -la /etc/cron.d /usr/local/etc/cron.d 2>/dev/null' },
          { do: 'rc.conf lines you did not expect', cmd: 'grep -v "^#" /etc/rc.conf' },
          { do: 'SUID files', cmd: 'find / -xdev -perm -4000 -type f 2>/dev/null' },
          { do: 'Media and tools', cmd: "find /home /root /tmp -xdev -type f \\( -iname '*.mp3' -o -iname '*.pcap' \\) 2>/dev/null" },
          { do: 'SSH keys', cmd: 'find / -xdev -name authorized_keys 2>/dev/null; grep -v "^#" /etc/ssh/sshd_config' },
        ],
      },
    ],
  },
];

export function fieldCard(id: string): FieldCard | undefined {
  return FIELD_CARDS.find((c) => c.id === id);
}
