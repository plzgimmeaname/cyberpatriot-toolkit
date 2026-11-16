"""Where a practice image actually runs: QEMU/KVM, Hyper-V, or a VM you already started.

Every provider gets the SAME contract:

    runtime = provider.start(image, run_dir, log, cancel)
    ... guest is reachable on runtime["host"]:runtime["port"] ...
    provider.stop(runtime, log)

`start` never touches the base disk. QEMU and Hyper-V create a differencing /
overlay disk in the run folder, so a run that deletes half the image can be
thrown away by deleting that folder, and the next run starts clean again.
"""
from __future__ import annotations

import json
import os
import platform
import secrets
import shutil
import signal
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path


class ProviderError(RuntimeError):
    """Something the operator must install or configure."""


def qemu_screendump(runtime: dict, log=None) -> Path | None:
    """Ask a running QEMU for one frame of its display.

    Works with `-display none`: QEMU still keeps the VGA surface, so `screendump`
    on the monitor socket returns a PPM image without any display server.
    """
    monitor = runtime.get("monitor") or ""
    screen = Path(runtime.get("screen") or "")
    if not monitor or not str(screen):
        return None
    if not Path(monitor).exists():
        return None
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(5.0)
            sock.connect(monitor)
            sock.recv(65536)
            sock.sendall(b"screendump " + str(screen).encode() + b"\n")
            time.sleep(0.4)
            try:
                sock.recv(65536)
            except OSError:
                pass
    except OSError as exc:
        if log:
            log(f"screen: {exc}")
        return None
    return screen if screen.exists() else None


def qemu_monitor(monitor: str, command: str, timeout: float = 5.0) -> str:
    """Send one command to a QEMU human-monitor socket and return its reply."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect(monitor)
        sock.recv(65536)  # banner
        sock.sendall(command.encode() + b"\n")
        time.sleep(0.3)
        try:
            return sock.recv(65536).decode("utf-8", "replace")
        except OSError:
            return ""


def free_vnc_display() -> int:
    """A VNC display number whose TCP port (5900+n) is free on loopback."""
    for display in range(10, 90):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", 5900 + display))
            except OSError:
                continue
            return display
    raise ProviderError("no free VNC port between 5910 and 5989")


def vnc_password() -> str:
    """VNC passwords are cut to 8 characters by the protocol."""
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(8))


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_port(host: str, port: int, timeout: float, log, cancel=None) -> None:
    """Wait until something accepts TCP on host:port (SSH / WinRM in the guest)."""
    deadline = time.time() + timeout
    last_note = 0.0
    while time.time() < deadline:
        if cancel is not None and cancel.is_set():
            raise ProviderError("cancelled")
        try:
            with socket.create_connection((host, port), timeout=3):
                log(f"guest is reachable on {host}:{port}")
                return
        except OSError:
            if time.time() - last_note > 15:
                last_note = time.time()
                log(f"waiting for the guest to answer on {host}:{port}...")
            time.sleep(2)
    raise ProviderError(
        f"the VM did not answer on {host}:{port} within {int(timeout)}s. Check the console log "
        "(console.log / the Hyper-V console): the image may expect a login, a different network, "
        "or SSH/WinRM is not enabled in the template."
    )


def _powershell() -> str | None:
    return shutil.which("pwsh") or shutil.which("powershell")


def capabilities() -> dict:
    return {
        "qemu": shutil.which("qemu-system-x86_64") is not None,
        "qemu-img": shutil.which("qemu-img") is not None,
        "hyperv": _powershell() is not None and os.name == "nt",
        "ssh": shutil.which("ssh") is not None,
        "scp": shutil.which("scp") is not None,
        "powershell": _powershell(),
    }


class Provider:
    name = "base"

    def available(self) -> tuple[bool, str]:
        return False, "not implemented"

    def start(self, image: dict, base_disk: Path, run_dir: Path, log, cancel=None) -> dict:
        raise NotImplementedError

    def stop(self, runtime: dict, log) -> None:
        raise NotImplementedError


class QemuProvider(Provider):
    """Headless QEMU with user-mode networking.

    Works on Linux and macOS hosts. Needs qemu-system-x86_64 and qemu-img.
    SSH (and WinRM for Windows images) are forwarded to random loopback ports,
    so nothing in the guest is exposed to the network.
    """

    name = "qemu"

    def available(self) -> tuple[bool, str]:
        if not shutil.which("qemu-system-x86_64"):
            return False, "install QEMU (Debian/Ubuntu: sudo apt install qemu-system-x86 qemu-utils)"
        if not shutil.which("qemu-img"):
            return False, "install qemu-utils (needed to make the throw-away overlay disk)"
        return True, "ready"

    def start(self, image: dict, base_disk: Path, run_dir: Path, log, cancel=None, early=None) -> dict:
        ok, why = self.available()
        if not ok:
            raise ProviderError(f"QEMU is not usable: {why}")
        qemu_img = shutil.which("qemu-img")
        overlay = run_dir / "disk.qcow2"
        base_fmt = detect_format(base_disk)
        log(f"creating a copy-on-write overlay from {base_disk.name} (the base image is not modified)")
        result = subprocess.run(
            [qemu_img, "create", "-q", "-f", "qcow2", "-F", base_fmt, "-b", str(base_disk), str(overlay)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise ProviderError(f"qemu-img create failed: {result.stderr.strip()}")

        ssh_port = free_port()
        winrm_port = free_port()
        family = image.get("family")
        ram = int((image.get("guest") or {}).get("ramMb") or 4096)
        cpus = int((image.get("guest") or {}).get("cpus") or 2)
        accel = (image.get("guest") or {}).get("accel") or ("hvf:tcg" if platform.system() == "Darwin" else "kvm:tcg")
        netdev = f"user,id=net0,hostfwd=tcp:127.0.0.1:{ssh_port}-:22"
        if family == "windows":
            netdev += f",hostfwd=tcp:127.0.0.1:{winrm_port}-:5985"
        vnc_display = free_vnc_display()
        vnc_ws = free_port()
        pidfile = run_dir / "qemu.pid"
        console = run_dir / "console.log"
        # Unix sockets have a ~100 byte path limit (macOS 104): keep this one short, outside the run folder.
        monitor = Path(tempfile.mkdtemp(prefix="rg-", dir="/tmp" if os.name == "posix" else None)) / "m.sock"
        screen = run_dir / "screen.ppm"
        cmd = [
            "qemu-system-x86_64",
            "-name", f"rampart-{image['id']}",
            "-m", str(ram),
            "-smp", str(cpus),
            "-machine", f"accel={accel}",
            "-drive", f"file={overlay},if=virtio,format=qcow2",
            "-netdev", netdev,
            "-device", "virtio-net-pci,netdev=net0",
            # An absolute pointer, so the mouse in the browser lines up with the guest's pointer.
            "-device", "qemu-xhci",
            "-device", "usb-tablet",
            # The live desktop: VNC on loopback with a WebSocket the page's noVNC viewer connects to.
            # password=on: nothing can connect until a random per-session password is set below.
            "-vnc", f"127.0.0.1:{vnc_display},websocket={vnc_ws},password=on",
            "-serial", f"file:{console}",
            "-monitor", f"unix:{monitor},server,nowait",
            "-pidfile", str(pidfile),
        ]
        log("starting QEMU: " + " ".join(cmd[:6]) + " ...")
        # Not `-daemonize`: on macOS the forked QEMU dies on the first VNC WebSocket connection.
        # A detached child with its output in a log file behaves the same on every host.
        qemu_log = run_dir / "qemu.log"
        with open(qemu_log, "wb") as out:
            proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=out, stderr=out, start_new_session=True)
        threading.Thread(target=proc.wait, daemon=True).start()  # reap it when it exits
        for _ in range(40):  # up to ~10 s for QEMU to open its monitor, or to fail
            if proc.poll() is not None:
                tail = qemu_log.read_text(errors="replace").strip()[-600:]
                raise ProviderError(f"QEMU did not start: {tail or f'exit code {proc.returncode}'}")
            if Path(monitor).exists() and pidfile.exists():
                break
            time.sleep(0.25)
        runtime = {
            "provider": self.name,
            "overlay": str(overlay),
            "pidfile": str(pidfile),
            "console": str(console),
            "monitor": str(monitor),
            "screen": str(screen),
            "sshPort": ssh_port,
            "winrmPort": winrm_port if family == "windows" else None,
            "vncWsPort": vnc_ws,
        }
        password = vnc_password()
        for _ in range(20):
            if Path(monitor).exists():
                break
            time.sleep(0.25)
        try:
            qemu_monitor(str(monitor), f"set_password vnc {password}")
            runtime["vncPassword"] = password
        except OSError as exc:
            log(f"could not protect the live desktop with a password, so it is switched off: {exc}")
            runtime["vncWsPort"] = None
        if early is not None:
            early(dict(runtime))  # the live desktop is usable while the guest is still booting
        port = winrm_port if family == "windows" else ssh_port
        log(f"VM started (PID {pidfile.read_text().strip() if pidfile.exists() else '?'})")
        if (image.get("guest") or {}).get("waitForGuest") is False:
            log("desktop-only boot: not waiting for SSH/WinRM. Use the live desktop on the page; audits need SSH/WinRM.")
            return runtime
        log("waiting for the guest")
        wait_port("127.0.0.1", port, float((image.get("guest") or {}).get("bootTimeout") or 300), log, cancel)
        return runtime

    def stop(self, runtime: dict, log) -> None:
        pidfile = Path(runtime.get("pidfile") or "")
        if pidfile.exists():
            try:
                pid = int(pidfile.read_text().strip())
                os.kill(pid, signal.SIGTERM)
                for _ in range(20):
                    time.sleep(0.5)
                    os.kill(pid, 0)
                os.kill(pid, signal.SIGKILL)
            except (ValueError, ProcessLookupError):
                pass
            except OSError:
                pass
            log("VM stopped")
        _drop_monitor(runtime)
        overlay = Path(runtime.get("overlay") or "")
        if overlay.exists():
            overlay.unlink(missing_ok=True)
            log("throw-away overlay disk deleted; the base image is untouched")


class HyperVProvider(Provider):
    """Windows host: Hyper-V with a differencing VHD.

    Needs an elevated PowerShell and the Hyper-V module. The VM is connected to
    the virtual switch named in guest.switchName (default "Default Switch"),
    which gives it an address the host can reach directly.
    """

    name = "hyperv"

    def available(self) -> tuple[bool, str]:
        if os.name != "nt" or not _powershell():
            return False, "Hyper-V runs on a Windows host with PowerShell and the Hyper-V role"
        return True, "ready (requires an elevated PowerShell)"

    def _ps(self, script: str) -> str:
        ps = _powershell()
        assert ps
        result = subprocess.run([ps, "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True)
        if result.returncode != 0:
            raise ProviderError(result.stderr.strip() or result.stdout.strip() or "PowerShell failed")
        return result.stdout.strip()

    def start(self, image: dict, base_disk: Path, run_dir: Path, log, cancel=None) -> dict:
        ok, why = self.available()
        if not ok:
            raise ProviderError(f"Hyper-V is not usable: {why}")
        guest = image.get("guest") or {}
        switch = guest.get("switchName") or "Default Switch"
        generation = int(guest.get("generation") or 2)
        vm = f"rampart-{image['id']}-{run_dir.name}"
        overlay = run_dir / "disk.vhdx"
        script = (
            f"$ErrorActionPreference='Stop';"
            f"$vhd=New-VHD -Path '{overlay}' -ParentPath '{base_disk}' -Differencing;"
            f"$vm=New-VM -Name '{vm}' -MemoryStartupBytes {int(guest.get('ramMb') or 4096)}MB "
            f"-VHDPath '{overlay}' -Generation {generation} -SwitchName '{switch}';"
            f"Set-VMProcessor -VMName '{vm}' -Count {int(guest.get('cpus') or 2)};"
            f"Start-VM -Name '{vm}';"
            f"'STARTED ' + $vm.Name"
        )
        log(f"creating Hyper-V VM {vm} with a differencing disk (the base image is not modified)")
        self._ps(script)
        port = int(guest.get("winrmPort") or 5985) if image.get("family") == "windows" else int(guest.get("sshPort") or 22)
        deadline = time.time() + float(guest.get("bootTimeout") or 300)
        host = ""
        while time.time() < deadline:
            if cancel is not None and cancel.is_set():
                raise ProviderError("cancelled")
            out = self._ps(
                f"$a=Get-VMNetworkAdapter -VMName '{vm}' | Select-Object -ExpandProperty IPAddresses;"
                "$a | Where-Object { $_ -match '^[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+$' } | Select-Object -First 1"
            ).strip()
            if out:
                host = out
                break
            time.sleep(3)
        if not host:
            raise ProviderError("the Hyper-V VM has no IPv4 address yet; check that the virtual switch has internet access")
        log(f"VM address {host}; waiting for port {port}")
        wait_port(host, port, 120, log, cancel)
        return {"provider": self.name, "vm": vm, "host": host, "port": port, "overlay": str(overlay), "generation": generation}

    def stop(self, runtime: dict, log) -> None:
        vm = runtime.get("vm")
        if not vm:
            return
        try:
            self._ps(f"Stop-VM -Name '{vm}' -TurnOff -Force -ErrorAction SilentlyContinue; Remove-VM -Name '{vm}' -Force")
            log(f"VM {vm} stopped and removed")
        except ProviderError as exc:
            log(f"could not remove VM {vm}: {exc}")
        overlay = Path(runtime.get("overlay") or "")
        if overlay.exists():
            overlay.unlink(missing_ok=True)


class AttachProvider(Provider):
    """Use a VM you already started yourself (VirtualBox, VMware, a physical test box).

    The catalog entry must give guest.host (and guest.sshPort / guest.winrmPort).
    Nothing is booted or deleted, so this is the safe way to try the range.
    """

    name = "attach"

    def available(self) -> tuple[bool, str]:
        return True, "ready (connects to a VM you started yourself)"

    def start(self, image: dict, base_disk: Path, run_dir: Path, log, cancel=None) -> dict:
        guest = image.get("guest") or {}
        host = guest.get("host")
        if not host:
            raise ProviderError(
                "this image has no provider and no guest.host. Either install QEMU / use Hyper-V, "
                "or start the VM yourself and set guest.host in images.json."
            )
        family = image.get("family")
        port = int(guest.get("winrmPort") if family == "windows" else guest.get("sshPort") or (5985 if family == "windows" else 22))
        log(f"using the VM you started at {host}:{port}")
        wait_port(host, port, float(guest.get("bootTimeout") or 90), log, cancel)
        return {"provider": self.name, "host": host, "port": port}


def detect_format(path: Path) -> str:
    try:
        result = subprocess.run(["qemu-img", "info", "--output=json", str(path)], capture_output=True, text=True)
        if result.returncode == 0:
            return json.loads(result.stdout).get("format", "qcow2")
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    ext = path.suffix.lower().lstrip(".")
    return {"vmdk": "vmdk", "vhdx": "vhdx", "vhd": "vpc", "raw": "raw", "img": "raw"}.get(ext, "qcow2")


PROVIDERS = {"qemu": QemuProvider, "hyperv": HyperVProvider, "attach": AttachProvider}


def by_name(name: str | None) -> Provider | None:
    """The provider a booted session used, so it can be stopped later."""
    klass = PROVIDERS.get((name or "").lower())
    return klass() if klass else None


def _drop_monitor(runtime: dict) -> None:
    monitor = Path(runtime.get("monitor") or "")
    if monitor.name == "m.sock":
        monitor.unlink(missing_ok=True)
        try:
            monitor.parent.rmdir()
        except OSError:
            pass


def force_stop(runtime: dict) -> None:
    """Kill a VM left behind by an agent that was closed (best effort)."""
    pidfile = Path(runtime.get("pidfile") or "")
    if pidfile.exists():
        try:
            os.kill(int(pidfile.read_text().strip()), signal.SIGKILL)
        except (ValueError, OSError):
            pass
    _drop_monitor(runtime)
    overlay = Path(runtime.get("overlay") or "")
    if overlay.exists():
        overlay.unlink(missing_ok=True)


def for_image(image: dict) -> Provider:
    wanted = (image.get("provider") or "").lower()
    if wanted == "qemu":
        return QemuProvider()
    if wanted == "hyperv":
        return HyperVProvider()
    if wanted == "attach":
        return AttachProvider()
    if (image.get("guest") or {}).get("host"):
        return AttachProvider()
    qemu = QemuProvider()
    if qemu.available()[0]:
        return qemu
    if HyperVProvider().available()[0]:
        return HyperVProvider()
    return AttachProvider()
