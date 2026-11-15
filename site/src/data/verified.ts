// What has actually been verified, and how. Kept in one place so no page can
// claim more than the test suite proves. Update the date when the suites are run.

export interface VerifiedState {
  level: 'tested' | 'partial' | 'untested';
  /** One line, shown under a checklist title and on the field card. */
  line: string;
  /** What was and was not checked. */
  detail: string;
}

export const VERIFIED_ON = '2026-11-15';

export const VERIFIED: Record<'linux' | 'windows' | 'freebsd', VerifiedState> = {
  linux: {
    level: 'tested',
    line: 'Script: 77 automated checks pass on Debian 12, Ubuntu 22.04, Ubuntu 24.04 and Mint 21.3.',
    detail:
      'Each run builds a real container image, plants the usual vulnerabilities (hidden root account, PAM backdoor, cron reverse shell, SUID find, fake sudo alias), runs the script and asserts 77 results, plus a run with no README list and one under umask 0000. The checklist commands themselves are run by hand and are not part of that suite.',
  },
  windows: {
    level: 'partial',
    line: 'Script: 82 logic tests pass and PSScriptAnalyzer is clean, but it has not been run on a real Windows image.',
    detail:
      'The tests exercise the decision logic (which service is safe to stop, which account is privileged, what the README means) against fixtures. Use -Audit first, and treat Apply as unrehearsed.',
  },
  freebsd: {
    level: 'untested',
    line: 'Script: shellcheck clean and logic tests pass, but it has not been run on a real FreeBSD system.',
    detail: 'Run it with --audit on a practice VM before a scored round, and read every diff it prints.',
  },
};

export function verifiedFor(family: string): VerifiedState {
  return VERIFIED[(family as keyof typeof VERIFIED) in VERIFIED ? (family as keyof typeof VERIFIED) : 'linux'];
}
