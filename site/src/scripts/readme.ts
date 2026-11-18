// Reads a pasted CyberPatriot README: authorized admins, other users and critical services.
// Shared by the README config builder and the Practice range page.
export type OS = 'linux' | 'windows' | 'freebsd';

// Words in a README's critical-services text -> keyword per OS
export const DETECT: [RegExp, Partial<Record<OS, string>>][] = [
  [/\b(open)?ssh|sshd\b/i, { linux: 'ssh', windows: 'ssh', freebsd: 'ssh' }],
  [/apache|httpd/i, { linux: 'apache', windows: 'apache', freebsd: 'apache' }],
  [/nginx/i, { linux: 'nginx', freebsd: 'nginx' }],
  [/\bphp\b/i, { linux: 'php' }],
  [/mariadb/i, { linux: 'mariadb', freebsd: 'mysql' }],
  [/mysql/i, { linux: 'mysql', windows: 'mysql', freebsd: 'mysql' }],
  [/postgres/i, { linux: 'postgresql', freebsd: 'postgresql' }],
  [/vsftpd/i, { linux: 'vsftpd', freebsd: 'ftp' }],
  [/proftpd/i, { linux: 'proftpd', freebsd: 'ftp' }],
  [/pure-?ftpd/i, { linux: 'pure-ftpd', freebsd: 'ftp' }],
  [/\bftp\b/i, { linux: 'ftp', windows: 'ftp', freebsd: 'ftp' }],
  [/samba|\bsmb\b|file shar/i, { linux: 'samba', windows: 'smb', freebsd: 'samba' }],
  [/\bdns\b|\bbind9?\b/i, { linux: 'dns', windows: 'dns', freebsd: 'dns' }],
  [/postfix|dovecot|\bmail\b|smtp|sendmail/i, { linux: 'mail', freebsd: 'mail' }],
  [/cups|print/i, { linux: 'cups', windows: 'print' }],
  [/\bnfs\b/i, { linux: 'nfs', freebsd: 'nfs' }],
  [/snmp/i, { linux: 'snmp', windows: 'snmp' }],
  [/\bvnc\b/i, { linux: 'vnc', windows: 'vnc' }],
  [/squid/i, { linux: 'squid' }],
  [/dhcp/i, { linux: 'dhcp', windows: 'dhcp' }],
  [/ldap/i, { linux: 'ldap' }],
  [/telnet/i, { linux: 'telnet', windows: 'telnet' }],
  [/remote desktop|\brdp\b/i, { windows: 'rdp' }],
  [/\biis\b|internet information/i, { windows: 'iis' }],
  [/active directory|domain controller|\bad ds\b/i, { windows: 'ad' }],
  [/winrm/i, { windows: 'winrm' }],
  [/sql server|mssql/i, { windows: 'sql' }],
];


/** Reads names and critical services out of pasted README text. */
export function parseReadme(text: string, os: OS) {
  const admins: string[] = [];
  const users: string[] = [];
  let me = '';
  let mode: 'admins' | 'users' | 'services' | null = null;
  let serviceText = '';
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (/authori[sz]ed\s+admin|^admin(istrator)?s?\s*:?$/i.test(line)) {
      mode = 'admins';
      continue;
    }
    if (/authori[sz]ed\s+users?|^(other\s+)?users?\s*:?$/i.test(line)) {
      mode = 'users';
      continue;
    }
    if (/critical\s+services?/i.test(line)) {
      mode = 'services';
      serviceText += ` ${line.replace(/.*critical\s+services?\s*:?/i, '')}`;
      continue;
    }
    if (!line) {
      if (mode === 'services' && serviceText.trim()) mode = null;
      continue;
    }
    if (mode === 'services') {
      serviceText += ` ${line}`;
      continue;
    }
    if (mode !== 'admins' && mode !== 'users') continue;
    if (/^password\s*:/i.test(line)) continue;
    if (/:\s*$/.test(line) || line.split(/\s+/).length > 3) {
      mode = null; // a new heading or a sentence ends the list
      continue;
    }
    const name = line.match(/^[-*•]?\s*([a-z_][a-z0-9._-]*\$?)/i)?.[1];
    if (!name) continue;
    if (/\(you\)/i.test(line)) me = name;
    const list = mode === 'admins' ? admins : users;
    if (!list.includes(name)) list.push(name);
  }
  const services = new Set<string>();
  for (const [re, map] of DETECT) if (re.test(serviceText) && map[os]) services.add(map[os] as string);
  // Prefer the specific FTP server over generic "ftp" on Linux
  if (os === 'linux' && ['vsftpd', 'proftpd', 'pure-ftpd'].some((k) => services.has(k))) services.delete('ftp');
  return { admins, users: users.filter((u) => !admins.includes(u)), me, services };
}
