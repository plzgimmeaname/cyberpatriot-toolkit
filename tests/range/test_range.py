"""Tests for the Practice range: add an image from a password-protected ZIP and
turn a QEMU screendump frame into a PNG.

    python3 -m unittest discover -s tests/range -v

Standard library only. The encrypted-archive test needs the `zip` command (it
creates the ZipCrypto password); it is skipped when that is not installed.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zipfile
import zlib
from functools import partial
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "range"))

import agent  # noqa: E402
import catalog  # noqa: E402
import providers  # noqa: E402
import screen  # noqa: E402


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # noqa: A003 - quiet test server
        pass


class _FileServer:
    """Serve a folder on loopback, so the catalog does a real HTTP download."""

    def __init__(self, directory: Path):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), partial(_QuietHandler, directory=str(directory)))
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.url = ""

    def __enter__(self) -> "_FileServer":
        self.thread.start()
        host, port = self.httpd.server_address
        self.url = f"http://{host}:{port}"
        return self

    def __exit__(self, *exc) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


@unittest.skipUnless(shutil.which("zip"), "the zip command is needed to build a password-protected archive")
class AddImageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        served = self.tmp / "served"
        served.mkdir()
        (served / "disk.qcow2").write_bytes(b"qcow2!" * 200_000)  # 1.2 MiB: pick_disk ignores tiny files
        subprocess.run(
            ["zip", "-q", "-e", "-P", "s3cret", "Mint21_Practice.zip", "disk.qcow2"],
            cwd=served,
            check=True,
        )
        self.server = _FileServer(served).__enter__()
        self.addCleanup(self.server.__exit__)
        self.data = self.tmp / "data"
        self.range = agent.Range(
            argparse.Namespace(repo=str(REPO), data=str(self.data), catalog=str(self.tmp / "images.json"))
        )
        self.addCleanup(self._stop_every_vm)

    def _stop_every_vm(self) -> None:
        """A test that boots a VM must never leave a QEMU running (each one reserves RAM)."""
        for sid in list(self.range.sessions):
            try:
                self.range.stop_session(sid)
            except Exception:
                pass
        deadline = time.time() + 15
        while self.range.session_cancels and time.time() < deadline:
            time.sleep(0.1)

    def _add(self, name: str, password: str) -> dict:
        return self.range.add_image(
            {
                "url": f"{self.server.url}/Mint21_Practice.zip",
                "name": name,
                "family": "linux",
                "keyFile": "~/.ssh/rampart_mint",
                "password": password,
            }
        )

    def _wait(self, image_id: str, timeout: float = 60.0) -> dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            state = self.range.catalog.state_of(image_id)
            if state.get("state") in {"ready", "error"}:
                return state
            time.sleep(0.05)
        self.fail(f"{image_id} never finished: {self.range.catalog.state_of(image_id)}")

    def test_password_protected_zip_becomes_ready(self) -> None:
        created = self._add("Mint 21 practice", "s3cret")
        state = self._wait(created["id"])

        self.assertEqual(state["state"], "ready", state.get("detail"))
        disk = self.range.catalog.base_disk(created["id"])
        self.assertIsNotNone(disk)
        self.assertEqual(disk.suffix, ".qcow2")
        self.assertEqual(disk.stat().st_size, 1_200_000)

        image = next(entry for entry in self.range.images() if entry["id"] == created["id"])
        self.assertTrue(image["addedFromPage"])
        self.assertEqual(image["state"], "ready")

        saved = (self.data / "images.local.json").read_text()
        self.assertIn(created["id"], saved)
        self.assertNotIn("s3cret", saved, "the unzip password must never be written to disk")

    def test_wrong_password_reports_it(self) -> None:
        created = self._add("Mint 21 wrong password", "not-the-password")
        state = self._wait(created["id"])

        self.assertEqual(state["state"], "error")
        self.assertIn("wrong unzip password", state["detail"])
        self.assertIsNone(self.range.catalog.base_disk(created["id"]))

    def test_reset_reboots_from_the_original_image(self) -> None:
        created = self._add("Mint 21 reset", "s3cret")
        self.assertEqual(self._wait(created["id"])["state"], "ready")

        first = self.range.boot_image(created["id"])["id"]
        second = self.range.reset_session(first)["id"]

        self.assertNotEqual(first, second)
        sessions = {session["id"] for session in self.range.sessions_public()}
        self.assertNotIn(first, sessions, "the reset VM is replaced, not kept next to the new one")
        self.assertIn(second, sessions)
        self.assertFalse((self.data / "sessions" / first).exists(), "the old overlay folder is deleted")

    def test_image_without_a_key_boots_as_desktop_only(self) -> None:
        created = self.range.add_image(
            {"url": f"{self.server.url}/Mint21_Practice.zip", "name": "stock", "family": "linux", "password": "s3cret"}
        )
        self.assertTrue(self.range.catalog.get(created["id"])["guest"]["desktopOnly"])
        self._wait(created["id"])

    def _plain_server(self) -> tuple[bytes, str]:
        payload = b"disk-bytes" * 200_000
        (self.tmp / "served" / "plain.qcow2").write_bytes(payload)
        return payload, f"{self.server.url}/plain.qcow2"

    def test_pasted_checksum_is_verified_while_downloading(self) -> None:
        payload, url = self._plain_server()
        for algo, text in (
            ("sha256", hashlib.sha256(payload).hexdigest().upper()),
            ("sha1", f"sha1: {hashlib.sha1(payload).hexdigest()}"),
            ("md5", f"{hashlib.md5(payload).hexdigest()}  *plain.qcow2"),
        ):
            with self.subTest(algo=algo):
                created = self.range.add_image(
                    {"url": url, "name": f"plain-{algo}", "family": "linux", "checksum": text}
                )
                state = self._wait(created["id"])
                self.assertEqual(state["state"], "ready", state)
                self.assertEqual(state["checksumVerified"], catalog.HASH_LABELS[algo])
                described = self.range.catalog.describe(self.range.catalog.get(created["id"]))
                self.assertEqual(described["checksumVerified"], catalog.HASH_LABELS[algo])

    def test_wrong_checksum_deletes_the_download(self) -> None:
        _, url = self._plain_server()
        created = self.range.add_image(
            {"url": url, "name": "plain-bad", "family": "linux", "checksum": "0" * 64}
        )
        state = self._wait(created["id"])
        self.assertEqual(state["state"], "error")
        self.assertIn("checksum mismatch (SHA-256)", state["error"])
        folder = self.range.catalog.image_dir(created["id"])
        self.assertEqual([p.name for p in folder.glob("plain*")], [])

    def test_a_typo_in_the_checksum_is_caught_before_downloading(self) -> None:
        _, url = self._plain_server()
        with self.assertRaises(ValueError):
            self.range.add_image({"url": url, "name": "typo", "family": "linux", "checksum": "not a hash"})

    def test_missing_password_says_so(self) -> None:
        created = self._add("Mint 21 no password", "")
        state = self._wait(created["id"])

        self.assertEqual(state["state"], "error")
        self.assertIn("password protected", state["detail"])


class PackageTest(unittest.TestCase):
    """The downloadable agent: one .pyz that runs far away from the repository."""

    def test_the_package_runs_on_its_own(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        built = subprocess.run(
            [sys.executable, str(REPO / "range" / "package.py"), "--no-site", "--out", str(tmp / "out")],
            capture_output=True, text=True,
        )
        self.assertEqual(built.returncode, 0, built.stderr)
        pyz = tmp / "out" / "rampart-range.pyz"
        bundle = tmp / "out" / "rampart-range.zip"
        self.assertTrue(pyz.is_file() and bundle.is_file())
        names = zipfile.ZipFile(bundle).namelist()
        for expected in ("rampart-range/rampart-range.pyz", "rampart-range/Start Range.command", "rampart-range/start-range.bat", "rampart-range/SHA256SUMS", "rampart-range/README.txt"):
            self.assertIn(expected, names)
        version = subprocess.run([sys.executable, str(pyz), "--version"], capture_output=True, text=True, cwd=tmp)
        self.assertIn("Rampart Range agent", version.stdout + version.stderr)

        port = providers.free_port()
        proc = subprocess.Popen(
            [sys.executable, str(pyz), "--data", str(tmp / "data"), "--port", str(port), "--no-open", "--token", "t0ken"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=tmp,
        )
        self.addCleanup(proc.wait)
        self.addCleanup(proc.terminate)
        deadline = time.time() + 15
        health = ""
        while time.time() < deadline and not health:
            try:
                import urllib.request
                health = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2).read().decode()
            except OSError:
                time.sleep(0.2)
        self.assertIn('"ok": true', health)
        unpacked = list((tmp / "data" / "app").glob("*/scripts/linux/harden.sh"))
        self.assertEqual(len(unpacked), 1, "the hardening scripts must be unpacked next to the agent")


class _FlakyServer:
    """Serves one file with Range support, but cuts the FIRST response off halfway."""

    def __init__(self, payload: bytes, resumable: bool = True):
        outer = self
        self.requests: list[tuple[str, int]] = []
        self.payload, self.resumable, self.cut_once = payload, resumable, True

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt: str, *args) -> None:
                pass

            def do_GET(self) -> None:  # noqa: N802
                start = 0
                header = self.headers.get("Range", "")
                if outer.resumable and header.startswith("bytes="):
                    start = int(header[6:].split("-")[0])
                outer.requests.append((header, start))
                body = outer.payload[start:]
                self.send_response(206 if start else 200)
                if start:
                    self.send_header("Content-Range", f"bytes {start}-{len(outer.payload) - 1}/{len(outer.payload)}")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if outer.cut_once:
                    outer.cut_once = False
                    self.wfile.write(body[: len(body) // 2])
                    self.wfile.flush()
                    self.connection.close()  # drop the connection mid-file
                    return
                self.wfile.write(body)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/Resume_Practice.qcow2"

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


class ResumeDownloadTest(unittest.TestCase):
    def _pull(self, resumable: bool) -> tuple["catalog.Catalog", _FlakyServer, bytes]:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        payload = os.urandom(3 << 20)
        server = _FlakyServer(payload, resumable)
        self.addCleanup(server.close)
        cat = catalog.Catalog(tmp / "none.json", tmp / "data")
        cat.add_image({
            "id": "resume1", "name": "r", "family": "linux", "script": "linux", "guest": {"user": "x"},
            "source": {"kind": "url", "url": server.url, "checksum": f"sha256:{hashlib.sha256(payload).hexdigest()}"},
        })
        cat.pull("resume1", lambda text: None)
        return cat, server, payload

    def test_a_dropped_connection_continues_where_it_stopped(self) -> None:
        cat, server, payload = self._pull(resumable=True)
        self.assertEqual(cat.state_of("resume1")["state"], "ready")
        self.assertEqual(Path(cat.state_of("resume1")["disk"]).read_bytes(), payload)
        self.assertEqual(cat.state_of("resume1")["checksumVerified"], "SHA-256")
        self.assertTrue(any(start > 0 for _, start in server.requests), "the second request must ask for the rest of the file")

    def test_a_server_without_range_support_still_finishes(self) -> None:
        cat, server, payload = self._pull(resumable=False)
        self.assertEqual(Path(cat.state_of("resume1")["disk"]).read_bytes(), payload)

    def test_deleting_an_image_frees_its_files(self) -> None:
        cat, _, _ = self._pull(resumable=True)
        folder = cat.image_dir("resume1")
        self.assertTrue(folder.exists())
        freed = cat.remove_image("resume1")
        self.assertGreaterEqual(freed, 3 << 20)
        self.assertFalse(folder.exists())
        self.assertIsNone(cat.get("resume1"))
        again = catalog.Catalog(cat.path, cat.data)
        self.assertIsNone(again.get("resume1"), "a deleted image must not come back after a restart")


class SetupCheckTest(unittest.TestCase):
    def test_every_check_says_how_to_fix_what_is_missing(self) -> None:
        checks = providers.setup_checks(Path(tempfile.gettempdir()))
        self.assertTrue(checks)
        for check in checks:
            self.assertIn(check["status"], {"ok", "warn", "missing"})
            if check["status"] != "ok" and check["id"] not in {"speed"}:
                self.assertTrue(check["fix"], check)


class PullProgressTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _catalog(self) -> "catalog.Catalog":
        return catalog.Catalog(self.tmp / "none.json", self.tmp / "data")

    @unittest.skipUnless(shutil.which("qemu-img"), "qemu-img converts the vmdk")
    def test_a_vmdk_is_converted_with_progress_and_no_partial_files(self) -> None:
        disk = self.tmp / "Win_Practice.vmdk"
        subprocess.run(["qemu-img", "create", "-q", "-f", "vmdk", "-o", "subformat=monolithicFlat", str(disk), "64M"], check=True)
        cat = self._catalog()
        cat.add_image({
            "id": "vmdk1", "name": "vmdk", "family": "linux", "script": "linux",
            "source": {"kind": "local", "path": str(self.tmp / "Win_Practice.vmdk")},
            "guest": {"user": "x"},
        })
        states: list[dict] = []
        original = cat.save_state
        cat.save_state = lambda image_id, **fields: (states.append(dict(fields)), original(image_id, **fields))[1]  # type: ignore[method-assign]
        cat.pull("vmdk1", lambda text: None)
        self.assertEqual(cat.state_of("vmdk1")["state"], "ready")
        self.assertTrue(any("converting" in str(f.get("detail", "")) for f in states))
        folder = cat.image_dir("vmdk1")
        self.assertEqual([p.name for p in folder.glob("*.part")], [])

    def test_an_interrupted_unpack_is_not_reused(self) -> None:
        cat = self._catalog()
        zip_path = self.tmp / "img.zip"
        payload = self.tmp / "disk.qcow2"
        payload.write_bytes(b"x" * (2 << 20))
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.write(payload, "disk.qcow2")
        cat.add_image({
            "id": "zip1", "name": "zip", "family": "linux", "script": "linux",
            "source": {"kind": "local", "path": str(zip_path)}, "guest": {"user": "x"},
        })
        stale = cat.image_dir("zip1") / "unpacked"
        stale.mkdir(parents=True)
        (stale / "disk.qcow2").write_bytes(b"truncated")  # what a killed unpack leaves behind, with no .complete marker
        cat.pull("zip1", lambda text: None)
        ready = Path(cat.state_of("zip1")["disk"])
        self.assertGreaterEqual(ready.stat().st_size, 2 << 20)

    def test_a_pull_cut_off_by_a_restart_does_not_say_pulling_forever(self) -> None:
        cat = self._catalog()
        cat.save_state("ghost", state="pulling", progress=40, detail="downloading")
        again = catalog.Catalog(self.tmp / "none.json", self.tmp / "data")
        self.assertEqual(again.state_of("ghost")["state"], "error")
        self.assertIn("press Pull again", again.state_of("ghost")["detail"])


class ChecksumParseTest(unittest.TestCase):
    H256 = "a" * 64

    def test_formats(self) -> None:
        cases = {
            self.H256.upper(): ("sha256", self.H256),
            f"sha256:{self.H256}": ("sha256", self.H256),
            f"SHA-256: {self.H256}": ("sha256", self.H256),
            f"SHA256 (Mint.zip) = {self.H256}": ("sha256", self.H256),
            f"{self.H256}  *Mint.zip": ("sha256", self.H256),
            ":".join(["ab"] * 32): ("sha256", "ab" * 32),
            "d41d8cd98f00b204e9800998ecf8427e": ("md5", "d41d8cd98f00b204e9800998ecf8427e"),
            "da39a3ee5e6b4b0d3255bfef95601890afd80709": ("sha1", "da39a3ee5e6b4b0d3255bfef95601890afd80709"),
            f"Algorithm Hash Path\n--------- ---- ----\nSHA256 {self.H256} C:\\x.zip": ("sha256", self.H256),
        }
        for text, expected in cases.items():
            with self.subTest(text=text[:30]):
                self.assertEqual(catalog.parse_checksum(text), expected)

    def test_empty_means_none_and_garbage_is_rejected(self) -> None:
        self.assertIsNone(catalog.parse_checksum("   "))
        for bad in ("hello", "abc123", "g" * 64):
            with self.subTest(bad=bad), self.assertRaises(catalog.CatalogError):
                catalog.parse_checksum(bad)

    def test_a_label_that_disagrees_with_the_length_is_rejected(self) -> None:
        with self.assertRaises(catalog.CatalogError):
            catalog.parse_checksum(f"md5: {self.H256}")


class DesktopTest(unittest.TestCase):
    """The live desktop: the page gets a loopback WebSocket address and a one-time password."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.range = agent.Range(
            argparse.Namespace(repo=str(REPO), data=str(self.tmp / "data"), catalog=str(self.tmp / "images.json"))
        )
        self.range.sessions["vm-1"] = {
            "id": "vm-1", "imageId": "x", "imageName": "x", "state": "running", "startedAt": "now",
            "stoppedAt": None, "detail": "", "provider": "qemu", "console": None, "host": None, "port": None,
            "runtime": {"vncWsPort": 5999, "pidfile": str(self.tmp / "qemu.pid")},
        }

    def test_desktop_needs_the_password_and_never_lists_it(self) -> None:
        with self.assertRaises(ValueError):
            self.range.session_desktop("vm-1")
        self.range.vnc_secrets["vm-1"] = "Abcd2345"
        info = self.range.session_desktop("vm-1")
        self.assertEqual((info["host"], info["port"], info["password"]), ("127.0.0.1", 5999, "Abcd2345"))
        public = self.range.public_session("vm-1")
        self.assertTrue(public["desktopAvailable"])
        self.assertNotIn("Abcd2345", repr(public))

    def test_a_dead_qemu_is_not_listed_as_running(self) -> None:
        gone = subprocess.Popen([sys.executable, "-c", "pass"])
        gone.wait()
        (self.tmp / "qemu.pid").write_text(str(gone.pid))
        self.range.vnc_secrets["vm-1"] = "Abcd2345"
        public = self.range.public_session("vm-1")
        self.assertEqual(public["state"], "stopped")
        self.assertFalse(public["desktopAvailable"])
        self.assertNotIn("vm-1", self.range.vnc_secrets)

    def test_vnc_password_fits_the_protocol(self) -> None:
        passwords = {providers.vnc_password() for _ in range(20)}
        self.assertTrue(all(len(p) == 8 and p.isalnum() for p in passwords))
        self.assertGreater(len(passwords), 15)


@unittest.skipUnless(
    shutil.which("qemu-system-x86_64") and shutil.which("qemu-img"), "QEMU is needed to boot a throw-away VM"
)
class QemuDesktopTest(unittest.TestCase):
    def test_qemu_serves_the_desktop_over_a_websocket(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        base = tmp / "blank.qcow2"
        subprocess.run(["qemu-img", "create", "-q", "-f", "qcow2", str(base), "64M"], check=True)
        run_dir = tmp / "run"
        run_dir.mkdir()
        image = {"id": "t", "family": "linux", "guest": {"waitForGuest": False, "accel": "tcg", "ramMb": 128, "cpus": 1}}
        provider = providers.QemuProvider()
        runtime = provider.start(image, base, run_dir, lambda text: None)
        self.addCleanup(provider.stop, runtime, lambda text: None)
        password = runtime["vncPassword"]
        self.assertEqual(len(password), 8)
        sock = socket.create_connection(("127.0.0.1", runtime["vncWsPort"]), timeout=10)
        key = base64.b64encode(os.urandom(16)).decode()
        sock.sendall(
            (
                "GET / HTTP/1.1\r\nHost: 127.0.0.1\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Protocol: binary\r\n\r\n"
            ).encode()
        )
        reply = sock.recv(512)
        sock.close()
        self.assertIn(b"101", reply.split(b"\r\n")[0], reply)


@unittest.skipUnless(
    shutil.which("qemu-system-x86_64") and shutil.which("qemu-img"), "QEMU is needed to boot a throw-away VM"
)
class SnapshotTest(unittest.TestCase):
    def test_save_replace_restore_and_delete_a_snapshot(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        base = tmp / "blank.qcow2"
        subprocess.run(["qemu-img", "create", "-q", "-f", "qcow2", str(base), "64M"], check=True)
        run_dir = tmp / "run"
        run_dir.mkdir()
        image = {"id": "t", "family": "linux", "guest": {"waitForGuest": False, "accel": "tcg", "ramMb": 128, "cpus": 1}}
        provider = providers.QemuProvider()
        runtime = provider.start(image, base, run_dir, lambda text: None)
        self.addCleanup(provider.stop, runtime, lambda text: None)

        self.assertEqual(providers.qemu_snapshots(runtime), [])
        providers.qemu_snapshot_save(runtime, "first")
        providers.qemu_snapshot_save(runtime, "second")
        providers.qemu_snapshot_save(runtime, "first")  # same name: replaced, not duplicated
        self.assertEqual(sorted(s["name"] for s in providers.qemu_snapshots(runtime)), ["first", "second"])
        providers.qemu_snapshot_restore(runtime, "second")
        providers.qemu_snapshot_delete(runtime, "second")
        self.assertEqual([s["name"] for s in providers.qemu_snapshots(runtime)], ["first"])
        with self.assertRaises(providers.ProviderError):
            providers.qemu_snapshot_restore(runtime, "nope")
        with self.assertRaises(providers.ProviderError):
            providers.qemu_snapshot_save(runtime, "bad name!")


class ScreenTest(unittest.TestCase):
    PIXELS = bytes([255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 255])

    def test_ppm_becomes_png_with_the_same_pixels(self) -> None:
        png = screen.ppm_to_png(b"P6\n2 2\n255\n" + self.PIXELS)

        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(struct.unpack(">II", png[16:24]), (2, 2))
        scanlines = zlib.decompress(self._chunks(png)[b"IDAT"])
        self.assertEqual(scanlines, b"\x00" + self.PIXELS[:6] + b"\x00" + self.PIXELS[6:])

    def test_rejects_a_text_ppm(self) -> None:
        with self.assertRaises(screen.ScreenError):
            screen.ppm_to_png(b"P3\n1 1\n255\n0 0 0\n")

    def test_rejects_a_truncated_frame(self) -> None:
        with self.assertRaises(screen.ScreenError):
            screen.ppm_to_png(b"P6\n4 4\n255\n" + b"\x00" * 8)

    @staticmethod
    def _chunks(png: bytes) -> dict[bytes, bytes]:
        found: dict[bytes, bytes] = {}
        index = 8
        while index < len(png):
            length = struct.unpack(">I", png[index:index + 4])[0]
            tag = png[index + 4:index + 8]
            found[tag] = png[index + 8:index + 8 + length]
            index += 12 + length
        return found


if __name__ == "__main__":
    unittest.main()
