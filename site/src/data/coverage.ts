// Which scored category each checklist section covers, so the points map and
// the coverage bars are derived from the real checklists instead of a hand-made
// table that drifts. `match` is tested against a step's section heading.
// Category names follow the wording the Scoring Report uses where we know it.

export interface Category {
  id: string;
  label: string;
  /** What this usually looks like on the Scoring Report. */
  hint: string;
  match: RegExp;
}

export const CATEGORIES: Category[] = [
  { id: 'forensics', label: 'Forensics questions', hint: 'Answered questions', match: /forensic/i },
  { id: 'users', label: 'Users & groups', hint: 'Users, groups, administrators', match: /user|group|account/i },
  { id: 'password', label: 'Passwords & lockout', hint: 'Password policy, lockout policy', match: /password|lockout|ageing|aging/i },
  { id: 'firewall', label: 'Firewall', hint: 'Firewall profiles / rules', match: /firewall/i },
  { id: 'updates', label: 'Updates', hint: 'Updates installed, pending updates', match: /update|patch/i },
  { id: 'services', label: 'Services & roles', hint: 'Services, roles, daemons', match: /service|role|daemon/i },
  { id: 'files', label: 'Prohibited files', hint: 'Prohibited files, media', match: /prohibit|media|file/i },
  { id: 'login', label: 'Login screen & desktop', hint: 'Display, login, desktop settings', match: /login|display|screen|desktop|greeter/i },
  { id: 'remote', label: 'Remote access', hint: 'Remote Desktop, SSH', match: /ssh|remote|rdp/i },
  { id: 'permissions', label: 'Permissions & shares', hint: 'Permissions, shares, ACLs', match: /permission|suid|share|\bacl\b/i },
  { id: 'privilege', label: 'Admin rights (sudo / UAC)', hint: 'Administrator rights, sudo', match: /sudo|privilege|admin|uac/i },
  { id: 'persistence', label: 'Backdoors & persistence', hint: 'Malware, backdoors, startup items', match: /backdoor|persistence|autorun|scheduled|startup|cron/i },
  { id: 'logging', label: 'Logging & audit', hint: 'Auditing, logging', match: /log|audit/i },
  { id: 'protection', label: 'Antivirus & MAC', hint: 'Defender, AppArmor, SELinux', match: /apparmor|selinux|defender|antivirus/i },
  { id: 'browser', label: 'Browser', hint: 'Browser settings, extensions', match: /browser|firefox|edge|chrome/i },
  { id: 'prep', label: 'Before you touch anything', hint: '— (never scored, but decides the round)', match: /before you touch/i },
];
