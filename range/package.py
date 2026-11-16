#!/usr/bin/env python3
"""Build the downloadable Rampart Range agent.

    python3 range/package.py                    # -> range/out/rampart-range.pyz + rampart-range.zip
    python3 range/package.py --out some/folder
    python3 range/package.py --no-site          # leave the website out (smaller, needs --site <url>)

Produces:

  rampart-range.pyz   one file: the agent, the hardening scripts and the built website.
                      Needs only Python 3.9+. Run it with:  python3 rampart-range.pyz
  rampart-range.zip   the .pyz plus double-click launchers (macOS, Linux, Windows), a short
                      README and SHA256SUMS, ready to hand to a teammate.

Standard library only. The website comes from site/dist; if it has not been built and
Node.js is installed, it is built first (npm ci && npm run build).
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipapp
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
MODULES = ("agent.py", "catalog.py", "providers.py", "runner.py", "screen.py")
SCRIPT_FILES = (
    "scripts/linux/harden.sh",
    "scripts/linux/config.example.conf",
    "scripts/windows/Harden.ps1",
    "scripts/windows/config.example.psd1",
    "scripts/freebsd/harden.sh",
)

MAIN = '''import sys
import agent

sys.exit(agent.main(sys.argv[1:]))
'''

LAUNCHERS = {
    "Start Range.command": (
        True,
        '#!/bin/bash\n# Double-click on macOS: starts the range agent and opens the Practice range page, already connected.\n'
        'cd "$(dirname "$0")" || exit 1\n'
        'command -v qemu-system-x86_64 >/dev/null 2>&1 || echo "QEMU is not installed: the page will say so. On a Mac: brew install qemu"\n'
        'exec python3 rampart-range.pyz "$@"\n',
    ),
    "start-range.sh": (
        True,
        '#!/bin/sh\n# Linux: starts the range agent and opens the Practice range page, already connected.\n'
        'cd "$(dirname "$0")" || exit 1\n'
        'command -v qemu-system-x86_64 >/dev/null 2>&1 || echo "QEMU is not installed: Debian/Ubuntu: sudo apt install qemu-system-x86 qemu-utils"\n'
        'exec python3 rampart-range.pyz "$@"\n',
    ),
    "start-range.bat": (
        False,
        '@echo off\r\nrem Windows: double-click. Starts the range agent and opens the Practice range page, already connected.\r\n'
        'cd /d "%~dp0"\r\npython rampart-range.pyz %*\r\nif errorlevel 1 py -3 rampart-range.pyz %*\r\npause\r\n',
    ),
}

README = """Rampart Range agent {version}
==============================

Run CyberPatriot practice images from your browser. This small program runs on YOUR
computer, downloads and boots the image, and serves the Practice range page.

Start it
  macOS    double-click  "Start Range.command"   (first time: right-click > Open)
  Linux    run           ./start-range.sh
  Windows  double-click  start-range.bat
  Any      python3 rampart-range.pyz

Your browser opens on the Practice range page, already connected. Paste the download
link, the checksum and the unzip password, and press "Download & boot".

You need
  * Python 3.9 or newer   (python.org; preinstalled on most Macs and Linux systems)
  * QEMU to boot the images   macOS: brew install qemu
                              Debian/Ubuntu: sudo apt install qemu-system-x86 qemu-utils
                              (Windows can use Hyper-V instead)

Good to know
  * Nothing leaves your computer: the agent listens on 127.0.0.1 only.
  * Options: --no-open (do not open the browser)  --port 8787  --data DIR  --help
  * Your images and reports are kept in ~/.rampart-range
  * Verify this download: compare rampart-range.pyz with SHA256SUMS.
"""


def run(cmd: list[str], cwd: Path) -> bool:
    try:
        return subprocess.run(cmd, cwd=cwd).returncode == 0
    except OSError:
        return False


def ensure_site(no_site: bool) -> Path | None:
    dist = REPO / "site" / "dist"
    if no_site:
        return None
    if not (dist / "index.html").is_file():
        npm = shutil.which("npm")
        if npm:
            print("building the website once (npm ci && npm run build)...")
            run([npm, "ci"], REPO / "site") and run([npm, "run", "build"], REPO / "site")
    if (dist / "index.html").is_file():
        return dist
    print("warning: site/dist not found, the package will not include the website (use --site <url> to open a hosted copy)", file=sys.stderr)
    return None


def agent_version() -> str:
    found = re.search(r'^VERSION\s*=\s*"([^"]+)"', (HERE / "agent.py").read_text(), re.M)
    return found.group(1) if found else "0"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def build(out: Path, no_site: bool) -> tuple[Path, Path]:
    version = agent_version()
    dist = ensure_site(no_site)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / "stage"
        payload = stage / "payload"
        stage.mkdir()
        for name in MODULES:
            shutil.copy2(HERE / name, stage / name)
        (stage / "__main__.py").write_text(MAIN)
        for relative in SCRIPT_FILES:
            target = payload / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / relative, target)
        shutil.copy2(HERE / "images.example.json", payload / "images.example.json")
        config = REPO / "site" / "site.config.mjs"
        if config.is_file():
            (payload / "site").mkdir(parents=True, exist_ok=True)
            shutil.copy2(config, payload / "site" / "site.config.mjs")
        if dist is not None:
            shutil.copytree(dist, payload / "site" / "dist", ignore=shutil.ignore_patterns("files", "*.map"))
        # A new version of the agent, scripts or website must unpack again.
        digest = hashlib.sha256()
        for path in sorted(p for p in payload.rglob("*") if p.is_file()):
            digest.update(str(path.relative_to(payload)).encode())
            digest.update(path.read_bytes())
        for name in MODULES:
            digest.update((stage / name).read_bytes())
        (payload / "VERSION").write_text(f"{version}-{digest.hexdigest()[:10]}")

        pyz = out / "rampart-range.pyz"
        pyz.unlink(missing_ok=True)
        zipapp.create_archive(stage, pyz, interpreter="/usr/bin/env python3", compressed=True)
        pyz.chmod(pyz.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    bundle = out / "rampart-range.zip"
    bundle.unlink(missing_ok=True)
    sums = f"{sha256(pyz)}  rampart-range.pyz\n"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(pyz, "rampart-range/rampart-range.pyz")
        for name, (executable, text) in LAUNCHERS.items():
            info = zipfile.ZipInfo(f"rampart-range/{name}")
            info.external_attr = (0o755 if executable else 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, text)
        archive.writestr("rampart-range/README.txt", README.format(version=version))
        archive.writestr("rampart-range/SHA256SUMS", sums)
    (out / "rampart-range.sha256").write_text(f"{sha256(pyz)}  rampart-range.pyz\n{sha256(bundle)}  rampart-range.zip\n")
    return pyz, bundle


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build the downloadable Rampart Range agent.")
    parser.add_argument("--out", default=str(HERE / "out"), help="where to write rampart-range.pyz / .zip (default: range/out)")
    parser.add_argument("--no-site", action="store_true", help="do not include the website")
    args = parser.parse_args(argv)
    pyz, bundle = build(Path(args.out).expanduser().resolve(), args.no_site)
    for path in (pyz, bundle):
        print(f"{path}  {path.stat().st_size / (1024 * 1024):.1f} MiB  sha256 {sha256(path)[:16]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
