#!/bin/sh
# Linux: starts the range agent and opens the Practice range page, already connected.
cd "$(dirname "$0")/.." || exit 1
if [ ! -f site/dist/index.html ] && command -v npm >/dev/null 2>&1; then
  echo "Building the website once (needs Node.js)..."
  npm --prefix site ci && npm --prefix site run build
fi
if ! command -v qemu-system-x86_64 >/dev/null 2>&1; then
  echo "QEMU is not installed: the page will say so. Debian/Ubuntu: sudo apt install qemu-system-x86 qemu-utils"
fi
exec python3 range/agent.py "$@"
