"""Practice-image catalog for the Rampart range.

An "image" is a virtual-machine disk plus the facts needed to run the hardening
script inside it (OS family, login). CyberPatriot does NOT publish public
download URLs: coaches get the practice images from the competition portal. So
this catalog is a list of *sources you own*:

  * "url"   - an HTTPS address (your file server, NAS, or a link a mentor sent),
              optionally protected by an archive password. A SHA-256 is always
              verified when one is given.
  * "local" - a disk image, .zip, .ova or .tar.gz already on the range host.

Images added from the Practice range page are stored in
<data>/images.local.json and merged with the catalog file, so the page can take
a pasted link without editing JSON by hand. Nothing is downloaded until you
press Pull (or "Download & boot"). The base disk is never modified: providers.py
makes a throw-away overlay for every run.

Archive passwords are used once, in memory, and never written to disk.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

DISK_SUFFIXES = (".qcow2", ".vmdk", ".vhdx", ".vhd", ".raw", ".img", ".qcow")
ARCHIVE_SUFFIXES = (".zip", ".tar", ".tar.gz", ".tgz", ".tar.xz", ".ova", ".7z", ".rar")
FAMILIES = {"windows", "linux", "freebsd"}
SCRIPTS = {"linux": "scripts/linux/harden.sh", "windows": "scripts/windows/Harden.ps1", "freebsd": "scripts/freebsd/harden.sh"}
EXTRACTORS = ("7z", "7zz", "7za", "unar")


class CatalogError(RuntimeError):
    """Something the person running the range can fix (wrong path, bad checksum...)."""


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    return hash_file(path, "sha256", chunk)


def hash_file(path: Path, algo: str, chunk: int = 1 << 20) -> str:
    h = hashlib.new(algo)
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


# hex length -> algorithm. A download page may give any of these.
HASH_BY_LENGTH = {32: "md5", 40: "sha1", 64: "sha256", 128: "sha512"}
HASH_LABELS = {"md5": "MD5", "sha1": "SHA-1", "sha256": "SHA-256", "sha512": "SHA-512"}


def parse_checksum(text: str) -> tuple[str, str] | None:
    """Understand whatever was pasted from a download page or a tool.

    Accepts a bare hash (any case, with spaces or colons between bytes), `sha256:HASH`,
    `SHA256 (file) = HASH`, `HASH  *file.zip` (sha256sum / md5sum output) and the
    PowerShell `Get-FileHash` table. The algorithm comes from the label when there is
    one, otherwise from the length (32 = MD5, 40 = SHA-1, 64 = SHA-256, 128 = SHA-512).
    Returns (algorithm, lowercase hex), or None for an empty string. Raises
    CatalogError when it cannot be a checksum, so a typo is caught before a long download.
    """
    raw = (text or "").strip()
    if not raw:
        return None
    label = None
    found = re.search(r"\b(md5|sha-?1|sha-?256|sha-?512)\b", raw, re.I)
    if found:
        label = found.group(1).lower().replace("-", "")
    candidate = None
    patterns = (
        r"(?<![0-9A-Za-z])[0-9a-fA-F]{32,128}(?![0-9A-Za-z])",          # a bare hash
        r"(?<![0-9A-Za-z])(?:[0-9a-fA-F]{2}[: ]){15,63}[0-9a-fA-F]{2}(?![0-9A-Za-z])",  # byte pairs, openssl style
    )
    for pattern in patterns:
        for match in re.finditer(pattern, raw):
            squeezed = re.sub(r"[ :]", "", match.group(0))
            if len(squeezed) in HASH_BY_LENGTH:
                candidate = squeezed.lower()
                break
        if candidate:
            break
    if candidate is None:
        raise CatalogError(
            "that does not look like a checksum: paste the MD5 (32), SHA-1 (40), SHA-256 (64) or SHA-512 (128) "
            "hexadecimal characters from the download page"
        )
    algo = HASH_BY_LENGTH[len(candidate)]
    if label and label != algo:
        raise CatalogError(f"the checksum is labelled {HASH_LABELS[label]} but has the length of a {HASH_LABELS[algo]}")
    return algo, candidate


def source_checksum(source: dict) -> tuple[str, str] | None:
    """The checksum stored for an image: `checksum` ("sha256:HEX") or the older `sha256` field."""
    value = source.get("checksum") or source.get("sha256")
    if not value:
        return None
    try:
        return parse_checksum(str(value))
    except CatalogError:
        return None


def expand(path: str, base: Path | None = None) -> Path:
    p = Path(os.path.expandvars(os.path.expanduser(path)))
    if not p.is_absolute() and base is not None:
        p = base / p
    return p.resolve()


def clean_id(text: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]", "-", text).strip(".-")
    return value[:48] or "image"


def guess_family(text: str) -> str:
    """Best guess from a file name or URL, so the page can preselect the OS."""
    t = text.lower()
    if "freebsd" in t:
        return "freebsd"
    if re.search(r"windows|win10|win11|win-1[01]|server-?(2016|2019|2022)", t):
        return "windows"
    return "linux"


def validate_entry(entry: object, index: int = 0) -> dict:
    if not isinstance(entry, dict):
        raise CatalogError(f"images[{index}] is not an object")
    for key in ("id", "name", "family", "script"):
        if not entry.get(key):
            raise CatalogError(f'images[{index}] is missing "{key}"')
    if not all(c.isalnum() or c in "-_." for c in str(entry["id"])):
        raise CatalogError(f'image id "{entry["id"]}" may only use letters, numbers, dot, dash and underscore')
    if entry["family"] not in FAMILIES:
        raise CatalogError(f'image {entry["id"]}: family must be one of {sorted(FAMILIES)}')
    if entry["script"] not in SCRIPTS:
        raise CatalogError(f'image {entry["id"]}: script must be one of {sorted(SCRIPTS)}')
    source = entry.get("source") or {}
    if source.get("kind") not in {"local", "url"}:
        raise CatalogError(f'image {entry["id"]}: source.kind must be "local" or "url"')
    if source.get("kind") == "url" and not source.get("url"):
        raise CatalogError(f'image {entry["id"]}: source.url is required for a url source')
    if source.get("kind") == "url" and not re.match(r"^https?://", str(source["url"])):
        raise CatalogError(f'image {entry["id"]}: only http:// and https:// links can be pulled')
    if source.get("kind") == "local" and not source.get("path"):
        raise CatalogError(f'image {entry["id"]}: source.path is required for a local source')
    for field in ("checksum", "sha256"):
        if source.get(field):
            try:
                parse_checksum(str(source[field]))
            except CatalogError as exc:
                raise CatalogError(f'image {entry["id"]}: source.{field}: {exc}') from exc
    return entry


def load_catalog(path: Path) -> list[dict]:
    if not path.exists():
        raise CatalogError(f"catalog not found: {path} (copy images.example.json to images.json, or add an image from the page)")
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise CatalogError(f"catalog is not valid JSON: {exc}") from exc
    images = data.get("images")
    if not isinstance(images, list):
        raise CatalogError('catalog has no "images" list')
    seen: set[str] = set()
    out = []
    for i, entry in enumerate(images):
        validate_entry(entry, i)
        if entry["id"] in seen:
            raise CatalogError(f'duplicate image id "{entry["id"]}"')
        seen.add(entry["id"])
        out.append(entry)
    return out


def list_files(dest: Path) -> list[Path]:
    return [p for p in dest.rglob("*") if p.is_file()]


def pick_disk(files: list[Path], wanted: str | None) -> Path:
    if wanted:
        for f in files:
            if f.name == wanted or str(f).endswith(wanted):
                return f
        raise CatalogError(f'the archive has no file named "{wanted}"')
    disks = sorted(
        (f for f in files if f.suffix.lower() in DISK_SUFFIXES and f.stat().st_size > 1024 * 1024),
        key=lambda f: f.stat().st_size,
        reverse=True,
    )
    if not disks:
        raise CatalogError("no disk image (*.qcow2, *.vmdk, *.vhdx, *.raw) found in the archive")
    return disks[0]


def disk_format(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    return {"qcow2": "qcow2", "qcow": "qcow2", "vmdk": "vmdk", "vhdx": "vhdx", "vhd": "vpc", "raw": "raw", "img": "raw"}.get(ext, "qcow2")


def _safe_extract_zip(zf: zipfile.ZipFile, dest: Path) -> None:
    root = dest.resolve()
    for member in zf.infolist():
        target = (dest / member.filename).resolve()
        if not str(target).startswith(str(root)):
            raise CatalogError(f"archive member escapes the folder: {member.filename}")
    zf.extractall(dest)


def _safe_extract_tar(tf: tarfile.TarFile, dest: Path) -> None:
    root = dest.resolve()
    for member in tf.getmembers():
        target = (dest / member.name).resolve()
        if not str(target).startswith(str(root)):
            raise CatalogError(f"archive member escapes the folder: {member.name}")
        if member.issym() or member.islnk():
            raise CatalogError(f"archive contains a link, refusing to extract: {member.name}")
    tf.extractall(dest)


def _extractor() -> str | None:
    for name in EXTRACTORS:
        found = shutil.which(name)
        if found:
            return found
    return None


def _extract_with_7z(archive: Path, dest: Path, password: str | None, log) -> None:
    tool = _extractor()
    if not tool:
        raise CatalogError(
            f"{archive.name} needs 7-Zip to unpack (AES encryption, .7z or .rar). Install it with "
            "'sudo apt install 7zip' (or 7zip-full) and press Pull again. Never hand this file to a "
            "site you do not trust."
        )
    dest.mkdir(parents=True, exist_ok=True)
    name = Path(tool).name
    if name == "unar":
        cmd = [tool, "-f", "-o", str(dest)]
        if password:
            cmd += ["-p", password]
    else:
        cmd = [tool, "x", "-y", f"-o{dest}"]
        if password:
            # 7-Zip has no stdin password option; this is visible in `ps` for a moment.
            cmd += [f"-p{password}"]
    cmd.append(str(archive))
    log(f"unpacking {archive.name} with {name}" + (" (password supplied)" if password else ""))
    result = subprocess.run(cmd, capture_output=True, text=True)
    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0 or re.search(r"wrong password|password is incorrect|Cannot open encrypted", output, re.I):
        raise CatalogError(f"unpacking failed ({result.returncode}): {output.splitlines()[-1] if output else 'no output'}")
    # A wrong password can "succeed" with an empty tree on some extractors.
    if not list_files(dest):
        raise CatalogError("unpacking produced no files - the archive password is probably wrong")


def extract_archive(archive: Path, dest: Path, password: str | None, log) -> list[Path]:
    """Unpack .zip/.tar/.ova/.7z/.rar, decrypting with `password` when needed."""
    dest.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            infos = zf.infolist()
            encrypted = any(i.flag_bits & 0x1 for i in infos)
            aes = any(i.compress_type == 99 for i in infos)  # WinZip AES marker
            if (encrypted or aes) and not password:
                raise CatalogError("this archive is password protected: paste the unzip password and try again")
            if aes:
                log("this ZIP uses AES encryption; stdlib cannot read it, using 7-Zip")
                _extract_with_7z(archive, dest, password, log)
                return list_files(dest)
            if encrypted:
                zf.setpassword(password.encode())
            try:
                _safe_extract_zip(zf, dest)
            except RuntimeError as exc:
                if "password" in str(exc).lower():
                    raise CatalogError("wrong unzip password") from exc
                raise
            return list_files(dest)
    if tarfile.is_tarfile(archive):
        with tarfile.open(archive) as tf:
            _safe_extract_tar(tf, dest)
        return list_files(dest)
    # .7z / .rar / anything else: one of the external extractors knows it.
    _extract_with_7z(archive, dest, password, log)
    return list_files(dest)


class Catalog:
    """Images on disk plus the state of each pull, kept in <data>/state.json."""

    def __init__(self, catalog_path: Path, data_dir: Path):
        self.path = Path(catalog_path).resolve()
        self.base = self.path.parent
        self.data = data_dir.resolve()
        self.images_dir = self.data / "images"
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data / "images-state.json"
        self.local_file = self.data / "images.local.json"
        self.base_entries: list[dict] = []
        if self.path.exists():
            self.base_entries = load_catalog(self.path)
        self.added: list[dict] = self._load_added()
        self.entries: list[dict] = list(self.base_entries)
        known = {e["id"] for e in self.entries}
        for entry in self.added:
            if entry["id"] in known:
                continue
            self.entries.append(entry)
            known.add(entry["id"])
        try:
            self.state = json.loads(self.state_file.read_text())
        except (OSError, json.JSONDecodeError):
            self.state = {}

    # -- queries ------------------------------------------------------------
    def _load_added(self) -> list[dict]:
        """Images added from the page. A broken file must not stop the agent."""
        try:
            data = json.loads(self.local_file.read_text()).get("images", [])
        except (OSError, json.JSONDecodeError):
            return []
        out = []
        for i, entry in enumerate(data):
            try:
                out.append(validate_entry(entry, i))
            except CatalogError:
                continue
        return out

    def add_image(self, entry: dict) -> dict:
        """Remember an image added from the page (persisted in the data folder)."""
        entry = validate_entry(entry)
        with_ids = {e["id"] for e in self.entries}
        if entry["id"] in with_ids:
            raise CatalogError(f'there is already an image with the id "{entry["id"]}"')
        self.added.append(entry)
        tmp = self.local_file.with_suffix(".tmp")
        tmp.write_text(json.dumps({"images": self.added}, indent=2))
        tmp.replace(self.local_file)
        self.entries.append(entry)
        return entry

    def get(self, image_id: str) -> dict | None:
        for entry in self.entries:
            if entry["id"] == image_id:
                return entry
        return None

    def image_dir(self, image_id: str) -> Path:
        return self.images_dir / image_id

    def state_of(self, image_id: str) -> dict:
        return self.state.get(image_id, {"state": "missing", "progress": 0, "detail": ""})

    def save_state(self, image_id: str, **fields) -> None:
        cur = dict(self.state_of(image_id))
        cur.update(fields)
        self.state[image_id] = cur
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=2, sort_keys=True))
        tmp.replace(self.state_file)

    def base_disk(self, image_id: str) -> Path | None:
        st = self.state_of(image_id)
        if st.get("state") != "ready" or not st.get("disk"):
            return None
        p = Path(st["disk"])
        return p if p.exists() else None

    def describe(self, entry: dict) -> dict:
        st = self.state_of(entry["id"])
        source = entry.get("source", {})
        return {
            "id": entry["id"],
            "name": entry["name"],
            "family": entry["family"],
            "osName": entry.get("osName", ""),
            "script": entry["script"],
            "notes": entry.get("notes", ""),
            "sourceKind": source.get("kind"),
            "sourceLabel": source.get("url") or source.get("path"),
            "checksum": bool(source_checksum(source)),
            "checksumAlgo": HASH_LABELS[source_checksum(source)[0]] if source_checksum(source) else "",
            "checksumVerified": st.get("checksumVerified", ""),
            "guest": {k: v for k, v in (entry.get("guest") or {}).items() if k != "password"},
            "state": st.get("state", "missing"),
            "progress": int(st.get("progress", 0)),
            "detail": st.get("detail", ""),
            "disk": st.get("disk"),
            "sizeBytes": st.get("sizeBytes"),
            "pulledAt": st.get("pulledAt"),
            "addedFromPage": any(e["id"] == entry["id"] for e in self.added),
        }

    # -- pulling ------------------------------------------------------------
    def pull(self, image_id: str, log, cancel=None, password: str | None = None) -> Path:
        """Make the base disk ready. Safe to call when it is already ready."""
        entry = self.get(image_id)
        if entry is None:
            raise CatalogError(f"no image called {image_id}")
        existing = self.base_disk(image_id)
        if existing:
            log(f"image {image_id} is already ready: {existing}")
            return existing

        source = entry["source"]
        dest = self.image_dir(image_id)
        dest.mkdir(parents=True, exist_ok=True)
        self.save_state(image_id, state="pulling", progress=0, detail="starting", error="", checksumVerified="")

        try:
            archive: Path
            if source["kind"] == "local":
                src = expand(source["path"], self.base)
                if not src.exists():
                    raise CatalogError(f"local source does not exist: {src}")
                log(f"using local source {src.name}")
                archive = src
                wanted = source_checksum(source)
                if wanted:
                    self.save_state(image_id, state="pulling", progress=0, detail=f"verifying {HASH_LABELS[wanted[0]]}")
                    actual = hash_file(src, wanted[0])
                    if actual != wanted[1]:
                        raise CatalogError(
                            f"checksum mismatch ({HASH_LABELS[wanted[0]]}): expected {wanted[1]}, got {actual}. "
                            "The file is not the one the checksum belongs to - do not boot it."
                        )
                    log(f"checksum verified ({HASH_LABELS[wanted[0]]})")
                    self.save_state(image_id, checksumVerified=HASH_LABELS[wanted[0]])
            else:
                url = source["url"]
                name = source.get("fileName") or Path(urllib.parse.urlparse(url).path).name or f"{image_id}.img"
                archive = dest / Path(name).name
                self._download(url, archive, image_id, source_checksum(source), log, cancel)

            disk = archive
            if archive.name.lower().endswith(ARCHIVE_SUFFIXES):
                extract_dir = dest / "unpacked"
                if not list_files(extract_dir):
                    self.save_state(image_id, state="pulling", progress=100, detail="unpacking")
                    log(f"unpacking {archive.name}")
                    extract_archive(archive, extract_dir, password, log)
                disk = pick_disk(list_files(extract_dir), (entry.get("disk") or {}).get("file"))

            fmt = (entry.get("disk") or {}).get("format") or disk_format(disk)
            if fmt != "qcow2":
                disk = self._convert_to_qcow2(disk, dest, log)
                fmt = "qcow2"
            size = disk.stat().st_size
            self.save_state(
                image_id,
                state="ready",
                progress=100,
                detail=f"{disk.name} ({size // (1024 * 1024)} MiB, {fmt})",
                disk=str(disk),
                format=fmt,
                sizeBytes=size,
                pulledAt=_now(),
                error="",
            )
            log(f"image {image_id} ready: {disk} ({size // (1024 * 1024)} MiB)")
            return disk
        except Exception as exc:
            self.save_state(image_id, state="error", detail=str(exc), error=str(exc))
            raise

    def _download(self, url: str, target: Path, image_id: str, checksum: tuple[str, str] | None, log, cancel) -> None:
        label = HASH_LABELS[checksum[0]] if checksum else ""
        if target.exists() and checksum and hash_file(target, checksum[0]) == checksum[1]:
            log(f"already downloaded and the {label} matches: {target}")
            self.save_state(image_id, checksumVerified=label)
            return
        part = target.with_suffix(target.suffix + ".part")
        log(f"downloading {urllib.parse.urlparse(url).netloc}{urllib.parse.urlparse(url).path}")
        request = urllib.request.Request(url, headers={"User-Agent": "rampart-range/1.0"})
        digest = hashlib.new(checksum[0]) if checksum else None  # hashed while it downloads: no second pass over a multi-GB file
        try:
            with urllib.request.urlopen(request, timeout=60) as response, part.open("wb") as out:
                total = int(response.headers.get("Content-Length") or 0)
                done = 0
                last = -1.0
                while True:
                    if cancel is not None and cancel.is_set():
                        raise CatalogError("cancelled")
                    block = response.read(1 << 20)
                    if not block:
                        break
                    out.write(block)
                    if digest is not None:
                        digest.update(block)
                    done += len(block)
                    pct = int(done * 100 / total) if total else 0
                    if pct != last:
                        last = pct
                        self.save_state(image_id, progress=pct, detail=f"downloading {done // (1024 * 1024)} MiB")
                        log(f"downloaded {pct}% ({done // (1024 * 1024)} MiB)")
        except (urllib.error.URLError, OSError) as exc:
            part.unlink(missing_ok=True)
            raise CatalogError(f"download failed: {exc}") from exc
        if checksum and digest is not None:
            actual = digest.hexdigest()
            if actual != checksum[1]:
                part.unlink(missing_ok=True)
                raise CatalogError(
                    f"checksum mismatch ({label}): expected {checksum[1]}, got {actual}. "
                    "The file is damaged or was replaced - it was deleted, do not boot it."
                )
            log(f"checksum verified ({label})")
            self.save_state(image_id, checksumVerified=label)
        elif str(target.name).lower().endswith(ARCHIVE_SUFFIXES):
            log("no checksum given for this image: the download was NOT verified")
        part.replace(target)

    def _convert_to_qcow2(self, disk: Path, dest: Path, log) -> Path:
        qemu_img = shutil.which("qemu-img")
        if not qemu_img:
            raise CatalogError(
                "this image is not qcow2 and qemu-img is not installed. Install qemu-utils "
                "(Debian/Ubuntu: sudo apt install qemu-utils) or convert the disk yourself."
            )
        target = dest / (disk.stem + ".qcow2")
        if target.exists():
            return target
        log(f"converting {disk.name} -> {target.name} (one time, can take a few minutes)")
        result = subprocess.run([qemu_img, "convert", "-O", "qcow2", str(disk), str(target)], capture_output=True, text=True)
        if result.returncode != 0:
            raise CatalogError(f"qemu-img convert failed: {result.stderr.strip()}")
        return target


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
