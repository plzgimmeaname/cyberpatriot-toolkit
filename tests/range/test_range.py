"""Tests for the Practice range: add an image from a password-protected ZIP and
turn a QEMU screendump frame into a PNG.

    python3 -m unittest discover -s tests/range -v

Standard library only. The encrypted-archive test needs the `zip` command (it
creates the ZipCrypto password); it is skipped when that is not installed.
"""
from __future__ import annotations

import argparse
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zlib
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "range"))

import agent  # noqa: E402
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

    def test_missing_password_says_so(self) -> None:
        created = self._add("Mint 21 no password", "")
        state = self._wait(created["id"])

        self.assertEqual(state["state"], "error")
        self.assertIn("password protected", state["detail"])


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
