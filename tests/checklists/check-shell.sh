#!/usr/bin/env bash
# Syntax-checks the shell blocks in the checklists: bash for the Linux ones,
# POSIX sh (dash + shellcheck) for FreeBSD. Also flags <placeholders> that a
# beginner would paste as-is (bash reads "<" as a redirect).
#   bash tests/checklists/check-shell.sh
#
# shellcheck is optional: if it is not installed, the Docker image is used. If
# neither is available the shellcheck part is skipped with a note, and the
# syntax and placeholder checks still run.
cd "$(dirname "$0")/../.." || exit 1
python3 - <<'PY'
import re, shutil, subprocess, sys
sys.path.insert(0, 'tests/checklists')
from extract import blocks

# Where does shellcheck come from? Local binary first, then Docker - and say so out loud.
sc = None
if shutil.which('shellcheck'):
    sc = ['shellcheck']
elif shutil.which('docker'):
    available = subprocess.run(['docker', 'info'], capture_output=True).returncode == 0
    if available:
        sc = ['docker', 'run', '--rm', '-i', 'koalaman/shellcheck:stable']
        print('note: shellcheck is not installed here - using the Docker image koalaman/shellcheck:stable')
    else:
        print('note: shellcheck is not installed and Docker is not running')
else:
    print('note: shellcheck is not installed and Docker was not found')
if not sc:
    print('      skipping the shellcheck part (the syntax and placeholder checks still run)')
    print('      to include it:  brew install shellcheck   or   sudo apt-get install shellcheck')

bad = n = checked_sc = 0
for f, shells in (('linux-mint', ('bash',)), ('debian', ('bash',)), ('ubuntu', ('bash',)), ('freebsd', ('sh',))):
    for b in blocks(f'docs/checklists/{f}.md'):
        if b['lang'] not in ('bash', 'sh'):
            continue
        n += 1
        # a <placeholder> outside quotes and comments
        for ln in b['code'].split('\n'):
            code = ln.split('#')[0]
            if re.search(r"<[A-Za-z][A-Za-z _-]*>", re.sub(r"(['\"]).*?\1", '', code)):
                bad += 1; print(f"PLACEHOLDER {f}.md:{b['line']} [{b['step']}] {ln.strip()[:80]}")
        interp = 'bash' if b['lang'] == 'bash' else 'dash'
        r = subprocess.run([interp, '-n'], input=b['code'], text=True, capture_output=True)
        if r.returncode and '<' not in b['code']:
            bad += 1; print(f"SYNTAX {f}.md:{b['line']} [{b['step']}] {r.stderr.strip().splitlines()[0]}")
        if b['lang'] == 'sh' and sc:
            checked_sc += 1
            r = subprocess.run(sc + ['-s', 'sh', '-S', 'error', '-'],
                               input='#!/bin/sh\n' + b['code'] + '\n', text=True, capture_output=True)
            if r.returncode:
                bad += 1
                out = (r.stdout + r.stderr).strip()
                print(f"SHELLCHECK {f}.md:{b['line']} [{b['step']}]\n{out[:400]}")
summary = f'checked {n} shell blocks: {bad} problem(s)'
summary += f', shellcheck on {checked_sc} of them' if sc else ' (shellcheck skipped)'
print(summary)
sys.exit(1 if bad else 0)
PY
